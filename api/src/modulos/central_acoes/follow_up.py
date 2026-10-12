"""The text of the follow-up: what each responsible reads about the open actions (HU-049).

The wording is the prototype's. The text is built here and not in the route so the preview of
the screen and the message the port sends are the same string. The language of the request
(D13) decides the wording: the message goes out in the language the sender is using.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from src.core import notification, translations
from src.modulos.central_acoes.calculations import ActionStatus, FollowUpAction, FollowUpGroup

SUBJECT_PREFIX = "Follow-up de ações em aberto"
SIGNATURE = "PMO · Gestão Integrada AMT"
REQUEST = "Por favor, atualize o andamento ou registre o replanejamento com justificativa."


def _label(text: str, idioma: str) -> str:
    """O texto de interface da Central no idioma do request (D13)."""
    return translations.translate("central_acoes", text, idioma)


def message_subject(group: FollowUpGroup, idioma: str = "pt") -> str:
    """One line: how many actions are open and how many of them are overdue."""
    total = len(group.actions)
    noun = _label("ação" if total == 1 else "ações", idioma)
    overdue = group.overdue_count
    tail = ""
    if overdue:
        template = _label(", {value} atrasada" if overdue == 1 else ", {value} atrasadas", idioma)
        tail = template.format(value=overdue)
    return f"{_label(SUBJECT_PREFIX, idioma)}: {total} {noun}{tail}"


def message_body(
    group: FollowUpGroup, *, name: str, reference_date: date, idioma: str = "pt"
) -> str:
    """The message to one responsible: greeting, one line per action, the request, the signature."""
    first_name = name.split()[0] if name.split() else name
    lines = [_action_line(item, idioma) for item in group.actions]
    return "\n".join(
        [
            _label("Olá, {name}.", idioma).format(name=first_name),
            "",
            _label(
                "Seguem suas ações em aberto na Central de Ações (referência {date}):", idioma
            ).format(date=_date(reference_date, idioma)),
            "",
            *lines,
            "",
            _label(REQUEST, idioma),
            "",
            SIGNATURE,
        ]
    )


def _action_line(item: FollowUpAction, idioma: str) -> str:
    due = _date(item.due_date, idioma) if item.due_date is not None else _label("sem prazo", idioma)
    late = ""
    if item.status is ActionStatus.OVERDUE:
        unit = _label("dia" if item.days_overdue == 1 else "dias", idioma)
        late = _label(" (ATRASADA há {value} {unit})", idioma).format(
            value=item.days_overdue, unit=unit
        )
    return _label("* {label}: {subject} · prazo {due}{late}", idioma).format(
        label=item.label, subject=item.subject, due=due, late=late
    )


def _date(value: date, idioma: str) -> str:
    return translations.format_date(value, idioma)


def result_notice(
    situations: Sequence[str], without_address: Sequence[str], idioma: str = "pt"
) -> tuple[str, str]:
    """The notice and the toast kind of a send, from the situation of each notification.

    Simulated says so (nothing left the process); a failure is named with the count; people with
    no address in the register are listed after the result.
    """
    total = len(situations)
    failed = sum(1 for item in situations if item == notification.FAILED)
    simulated = sum(1 for item in situations if item == notification.SIMULATED)
    noun = _label("follow-up" if total == 1 else "follow-ups", idioma)
    if failed:
        text = _label(
            "{failed} de {total} {noun} não foram enviados; o registro ficou na trilha.", idioma
        ).format(failed=failed, total=total, noun=noun)
        kind = notification.TOAST_KIND[notification.FAILED]
    elif simulated:
        text = _label(
            "Envio simulado: {total} {noun} registrado{s} na trilha; nada foi enviado por e-mail.",
            idioma,
        ).format(total=total, noun=noun, s="" if total == 1 else "s")
        kind = notification.TOAST_KIND[notification.SIMULATED]
    else:
        text = _label("{total} {noun} enviado{s} por e-mail.", idioma).format(
            total=total, noun=noun, s="" if total == 1 else "s"
        )
        kind = notification.TOAST_KIND[notification.SENT]
    if without_address:
        text += " " + _label("Sem e-mail cadastrado: {names}.", idioma).format(
            names=", ".join(without_address)
        )
    return text, kind
