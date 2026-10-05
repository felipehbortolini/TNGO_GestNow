"""The notification port: the one seam for every send the prototype simulated (D12).

Follow-up of actions, the risk agenda to the project manager and the send to
the treasury all go through ``send``. The environment picks the channel:

* e-mail sending off (the default): nothing leaves the process. The send is
  recorded as ``simulado`` and the outcome carries the "simulado" notice for
  the screen;
* e-mail sending on (``GESTNOW_ENVIO_EMAIL=ligado``): the e-mail goes out by
  Microsoft Graph (``graph_mail``), with no change of code.

Either way a send leaves one ``notificacao`` row and one trail line, written
in the same transaction as the record that asked for it. A delivery failure
never propagates: it is recorded with its error and the outcome says
``erro``, so the caller's transaction commits as usual and the record that
asked for the notification is not lost.

An e-mail that already left cannot be taken back by a rollback, so call
``send`` as the last step of the facade flow::

    outcome = notification.send(
        session,
        user_id=user.id,
        request=notification.NotificationRequest(
            kind=notification.FOLLOW_UP,
            project_id=project.id,
            recipients=[person.email],
            subject="Follow-up das ações",
            body=text,
            reference_entity="acao",
            reference_record_id=action.id,
        ),
    )
    return AlpineAjaxResponse(..., toast=outcome.notice, toast_tipo=outcome.toast_kind)

Recipients come from the registers (people, the project manager, the
treasury), never from a free field on the screen: the port refuses malformed
addresses but cannot tell who may be written to.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Protocol

from sqlalchemy.orm import Session

from src.core import audit, config
from src.core.errors import InvalidDataError
from src.core.models import Notification

if TYPE_CHECKING:
    from src.core.graph_mail import HttpClient

logger = logging.getLogger(__name__)

# What a notification is about: the three sends of the prototype (D12).
FOLLOW_UP = "follow_up"
RISK_AGENDA = "pauta_riscos"
TREASURY = "tesouraria"
KINDS = frozenset({FOLLOW_UP, RISK_AGENDA, TREASURY})

# The medium. Whether the e-mail really left is the situation's job, below.
CHANNEL_EMAIL = "email"

# ``notificacao.situacao`` (docs/MODELO-DE-DADOS.md).
SIMULATED = "simulado"
SENT = "enviado"
FAILED = "erro"

# Toast kinds of ``ds/ui.js`` by situation: a simulated send is a warning, not
# a success, because nothing reached the recipient.
TOAST_KIND = {SIMULATED: "aviso", SENT: "ok", FAILED: "erro"}

NOTICE_SIMULATED = (
    "Envio simulado: nada foi enviado por e-mail. O registro ficou na trilha de auditoria."
)
NOTICE_FAILURE_KEPT = "O registro foi mantido e a falha ficou na trilha de auditoria."
UNEXPECTED_FAILURE = "O e-mail não foi enviado: falha inesperada no envio."

# The trail keeps the whole error; the cap only protects the row from a runaway message.
MAX_TRAIL_ERROR_CHARS = 1000

# 254 is the longest address SMTP allows; checking it first also keeps the pattern cheap.
MAX_ADDRESS_CHARS = 254
_ADDRESS = re.compile(r"[^\s@,;<>\x00-\x1f]+@[^\s@,;<>\x00-\x1f]+\.[^\s@,;<>\x00-\x1f]+")


class DeliveryError(Exception):
    """A channel could not deliver: the port records it instead of raising it further.

    ``summary`` is a sentence in Portuguese the screen may show; ``detail`` is the
    service's own words and goes to the trail only. Neither may carry a secret.
    """

    def __init__(self, summary: str, detail: str = "") -> None:
        self.summary = summary
        self.detail = detail
        super().__init__(summary, detail)

    def __str__(self) -> str:
        return f"{self.summary} {self.detail}".strip()


@dataclass(frozen=True)
class NotificationRequest:
    """What a module asks the port to send: who, what and which record asked."""

    kind: str
    project_id: int
    recipients: Sequence[str]
    subject: str
    body: str
    reference_entity: str | None = None
    reference_record_id: int | None = None


@dataclass(frozen=True)
class NotificationOutcome:
    """What the screen needs after a send: the notice, its toast kind and the row written."""

    notification_id: int
    situation: str
    notice: str
    toast_kind: str
    error: str | None = None


class NotificationChannel(Protocol):
    """Where a notification goes: the seam of the port, with two real adapters.

    ``situation`` is what a successful delivery leaves in the register. ``deliver``
    raises ``DeliveryError`` when the notification could not be delivered.
    """

    situation: str

    def deliver(self, request: NotificationRequest) -> None:
        """Deliver the notification, or raise ``DeliveryError``."""


class SimulatedChannel:
    """The default channel: nothing leaves the process and the send is recorded as simulated."""

    situation = SIMULATED

    def deliver(self, request: NotificationRequest) -> None:
        # Kind and count only: the recipients are in the register, not in the log.
        logger.info(
            "Envio de e-mail simulado (%s, %d destinatário(s)).",
            request.kind,
            len(request.recipients),
        )


def configured_channel(*, http_client: HttpClient | None = None) -> NotificationChannel:
    """The channel the environment selects: simulated unless e-mail sending is switched on."""
    if config.email_sending() != config.EMAIL_SENDING_ON:
        return SimulatedChannel()
    # Imported here because graph_mail needs this module's request and error types.
    from src.core import graph_mail

    return graph_mail.GraphMailChannel(
        graph_mail.GraphSettings.from_environment(),
        http_client if http_client is not None else graph_mail.StdlibHttpClient(),
    )


def send(
    session: Session,
    *,
    user_id: int,
    request: NotificationRequest,
    channel: NotificationChannel | None = None,
) -> NotificationOutcome:
    """Deliver through the configured channel, record the send and say what happened.

    A request that is not worth sending raises ``InvalidDataError`` (422) before
    anything is written, and an unknown ``GESTNOW_ENVIO_EMAIL`` raises
    ``config.InvalidEmailSendingError``: both are mistakes to fix, not outcomes.
    A delivery failure is not an exception: it comes back as an outcome in the
    ``erro`` situation, with the error in the trail. ``channel`` replaces the
    environment's choice, which is how the tests inject a fake.
    """
    valid = _validated(request)
    chosen = configured_channel() if channel is None else channel
    failure = _attempt(chosen, valid)
    situation = FAILED if failure is not None else chosen.situation
    toast_kind = TOAST_KIND[situation]
    notification = _record(
        session, user_id=user_id, request=valid, situation=situation, failure=failure
    )
    return NotificationOutcome(
        notification_id=notification.id,
        situation=situation,
        notice=_notice(valid, failure, situation),
        toast_kind=toast_kind,
        error=_trail_error(failure) if failure is not None else None,
    )


def _attempt(channel: NotificationChannel, request: NotificationRequest) -> DeliveryError | None:
    """Try the delivery; a failure comes back as a value, never as an exception."""
    try:
        channel.deliver(request)
    except DeliveryError as error:
        logger.warning("O envio de e-mail falhou: %s", error)
        return error
    except Exception as error:
        # Last resort: whatever the channel did wrong, the record that asked for
        # the notification must not be lost to it. The traceback goes to the log.
        logger.exception("Falha inesperada no envio da notificação.")
        return DeliveryError(UNEXPECTED_FAILURE, detail=type(error).__name__)
    return None


def _record(
    session: Session,
    *,
    user_id: int,
    request: NotificationRequest,
    situation: str,
    failure: DeliveryError | None,
) -> Notification:
    """Write the ``notificacao`` row and its trail line in the caller's transaction.

    The error of a failed send has no column: it lives in the trail line, next
    to the recipients and the subject, which is where the people who look into
    a failure already read.
    """
    notification = Notification(
        project_id=request.project_id,
        originated_by_id=user_id,
        kind=request.kind,
        channel=CHANNEL_EMAIL,
        recipients=", ".join(request.recipients),
        subject=request.subject,
        body=request.body,
        situation=situation,
        reference_entity=request.reference_entity,
        reference_record_id=request.reference_record_id,
    )
    session.add(notification)
    session.flush()
    after = audit.snapshot(notification)
    if failure is not None:
        after["erro"] = _trail_error(failure)
    audit.append(
        session,
        audit.TrailLine(
            user_id=user_id,
            entity=notification.__tablename__,
            record_id=notification.id,
            action=audit.CREATED,
            after=after,
            project_id=request.project_id,
        ),
    )
    return notification


def _notice(request: NotificationRequest, failure: DeliveryError | None, situation: str) -> str:
    """The sentence the screen shows for the outcome."""
    if failure is not None:
        return f"{failure.summary} {NOTICE_FAILURE_KEPT}"
    if situation == SIMULATED:
        return NOTICE_SIMULATED
    count = len(request.recipients)
    noun = "destinatário" if count == 1 else "destinatários"
    return f"E-mail enviado a {count} {noun}."


def _trail_error(failure: DeliveryError) -> str:
    return str(failure)[:MAX_TRAIL_ERROR_CHARS]


def _validated(request: NotificationRequest) -> NotificationRequest:
    """The request cleaned for sending, or ``InvalidDataError`` naming what is wrong."""
    if request.kind not in KINDS:
        message = f"Tipo de notificação desconhecido: {request.kind!r}."
        raise ValueError(message)
    recipients, recipients_problem = _clean_recipients(request.recipients)
    # A subject is one line: any run of white space, line breaks included, becomes one space.
    subject = " ".join(request.subject.split())
    body = request.body.strip()
    problems = {
        "destinatarios": recipients_problem,
        "assunto": "" if subject else "Informe o assunto da notificação.",
        "corpo": "" if body else "Informe o corpo da notificação.",
    }
    if any(problems.values()):
        raise InvalidDataError(problems)
    return replace(request, recipients=recipients, subject=subject, body=body)


def _clean_recipients(raw: Sequence[str]) -> tuple[tuple[str, ...], str]:
    """The addresses without repeats (any case), and the problem found, if any."""
    if isinstance(raw, str):
        # A string is a sequence of strings too: without this it would be read letter by letter.
        message = "Os destinatários vão numa lista de endereços, não numa string."
        raise TypeError(message)
    cleaned = [address.strip() for address in raw]
    if not cleaned:
        return (), "Informe ao menos um destinatário."
    invalid = [address for address in cleaned if not _is_address(address)]
    if invalid:
        shown = ", ".join(address or "(em branco)" for address in invalid)
        return (), f"E-mail de destinatário inválido: {shown}."
    first_spelling: dict[str, str] = {}
    for address in cleaned:
        first_spelling.setdefault(address.lower(), address)
    return tuple(first_spelling.values()), ""


def _is_address(address: str) -> bool:
    return len(address) <= MAX_ADDRESS_CHARS and _ADDRESS.fullmatch(address) is not None
