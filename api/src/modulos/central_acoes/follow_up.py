"""The text of the follow-up: what each responsible reads about the open actions (HU-049).

The wording is the prototype's. The text is built here and not in the route so the preview of
the screen and the message the port sends are the same string.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from src.core import notification
from src.core.export_document import ValueKind, format_value
from src.modulos.central_acoes.calculations import ActionStatus, FollowUpAction, FollowUpGroup

SUBJECT_PREFIX = "Follow-up de ações em aberto"
SIGNATURE = "PMO · Gestão Integrada AMT"
REQUEST = "Por favor, atualize o andamento ou registre o replanejamento com justificativa."


def message_subject(group: FollowUpGroup) -> str:
    """One line: how many actions are open and how many of them are overdue."""
    total = len(group.actions)
    noun = "ação" if total == 1 else "ações"
    overdue = group.overdue_count
    tail = f", {overdue} atrasada{'s' if overdue != 1 else ''}" if overdue else ""
    return f"{SUBJECT_PREFIX}: {total} {noun}{tail}"


def message_body(group: FollowUpGroup, *, name: str, reference_date: date) -> str:
    """The message to one responsible: greeting, one line per action, the request, the signature."""
    first_name = name.split()[0] if name.split() else name
    lines = [_action_line(item) for item in group.actions]
    return "\n".join(
        [
            f"Olá, {first_name}.",
            "",
            (
                "Seguem suas ações em aberto na Central de Ações "
                f"(referência {_date(reference_date)}):"
            ),
            "",
            *lines,
            "",
            REQUEST,
            "",
            SIGNATURE,
        ]
    )


def _action_line(item: FollowUpAction) -> str:
    due = _date(item.due_date) if item.due_date is not None else "sem prazo"
    late = ""
    if item.status is ActionStatus.OVERDUE:
        late = f" (ATRASADA há {item.days_overdue} {'dia' if item.days_overdue == 1 else 'dias'})"
    return f"* {item.label}: {item.subject} · prazo {due}{late}"


def _date(value: date) -> str:
    return format_value(ValueKind.DATE, value)


def result_notice(situations: Sequence[str], without_address: Sequence[str]) -> tuple[str, str]:
    """The notice and the toast kind of a send, from the situation of each notification.

    Simulated says so (nothing left the process); a failure is named with the count; people with
    no address in the register are listed after the result.
    """
    total = len(situations)
    failed = sum(1 for item in situations if item == notification.FAILED)
    simulated = sum(1 for item in situations if item == notification.SIMULATED)
    noun = "follow-up" if total == 1 else "follow-ups"
    if failed:
        text = f"{failed} de {total} {noun} não foram enviados; o registro ficou na trilha."
        kind = notification.TOAST_KIND[notification.FAILED]
    elif simulated:
        text = (
            f"Envio simulado: {total} {noun} registrado{'s' if total != 1 else ''} na trilha; "
            "nada foi enviado por e-mail."
        )
        kind = notification.TOAST_KIND[notification.SIMULATED]
    else:
        text = f"{total} {noun} enviado{'s' if total != 1 else ''} por e-mail."
        kind = notification.TOAST_KIND[notification.SENT]
    if without_address:
        text += f" Sem e-mail cadastrado: {', '.join(without_address)}."
    return text, kind
