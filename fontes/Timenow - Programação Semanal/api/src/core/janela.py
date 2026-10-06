"""Programming window — when a contractor may write its own schedule.

The rule belongs to the CONTRACTOR, not to the individual user: everyone
from M. Roscoe shares one window. The Administrator opens and closes it.

Three ways in, checked in this order:

1. **Liberação extraordinária** — an absolute interval opened for one
   week. It overrides everything else, in both directions: inside the
   interval the window is open even on the wrong weekday; outside it, the
   week is closed even if the regular rule would allow it. That is the
   point of an exception.
2. **Semanas liberadas** — the set of week references the contractor may
   touch at all.
3. **Janela regular** — weekday plus opening hours (Friday, 09:00 to 15:00).

Shape of a window record::

    {
        "empresa": "M. Roscoe",
        "dias": [{"dia": "sex", "abre": "00:01", "fecha": "15:00"}],
        "semanas_liberadas": ["S.30/2026", "S.31/2026"],
        "extra": [{"semana": "S.29/2026", "abre": "...", "fecha": "..."}]
    }
"""

from datetime import datetime

DIAS_SEMANA = (
    ("seg", "Segunda-feira"),
    ("ter", "Terça-feira"),
    ("qua", "Quarta-feira"),
    ("qui", "Quinta-feira"),
    ("sex", "Sexta-feira"),
    ("sab", "Sábado"),
    ("dom", "Domingo"),
)

_PARA_WEEKDAY = {sigla: i for i, (sigla, _) in enumerate(DIAS_SEMANA)}
_ROTULOS = dict(DIAS_SEMANA)


def rotulo_dia(sigla: str) -> str:
    return _ROTULOS.get(sigla, sigla)


def janela_vazia(empresa: str) -> dict:
    return {"empresa": empresa, "dias": [], "semanas_liberadas": [], "extra": []}


def _hora(valor: str) -> tuple[int, int]:
    partes = str(valor or "0:0").split(":")
    try:
        return (int(partes[0]), int(partes[1]) if len(partes) > 1 else 0)
    except ValueError:
        return (0, 0)


def _dentro_do_horario(agora: datetime, abre: str, fecha: str) -> bool:
    return _hora(abre) <= (agora.hour, agora.minute) <= _hora(fecha)


def _extra_vigente(extra: dict, agora: datetime) -> bool:
    """An extraordinary release is an absolute interval, not a weekday."""
    try:
        abertura = datetime.fromisoformat(str(extra["abre"]))
        fechamento = datetime.fromisoformat(str(extra["fecha"]))
    except (KeyError, TypeError, ValueError):
        return False
    if abertura.tzinfo and not agora.tzinfo:
        agora = agora.replace(tzinfo=abertura.tzinfo)
    return abertura <= agora <= fechamento


def _decidir_extraordinaria(semana: str, janela: dict, agora: datetime) -> tuple[bool, str] | None:
    """The exception, when there is one for this week. None otherwise."""
    for extra in janela.get("extra") or []:
        if extra.get("semana") != semana:
            continue
        if _extra_vigente(extra, agora):
            return True, "Liberação extraordinária ativa."
        return False, "Fora do período da liberação extraordinária."
    return None


def _decidir_pelo_dia(janela: dict, agora: datetime) -> tuple[bool, str]:
    """Weekday and opening hours — the regular rule."""
    for regra in janela.get("dias") or []:
        if _PARA_WEEKDAY.get(regra.get("dia")) != agora.weekday():
            continue
        if _dentro_do_horario(agora, regra.get("abre"), regra.get("fecha")):
            return True, f"Janela aberta até {regra.get('fecha')}."
        return False, (
            f"Janela fechada agora — hoje ela vale das {regra.get('abre')} às {regra.get('fecha')}."
        )

    dias = ", ".join(rotulo_dia(r.get("dia")) for r in janela.get("dias") or [])
    if not dias:
        return True, "Sem restrição de dia — qualquer dia das semanas liberadas."
    return False, f"Hoje não é dia de programar. Dia liberado: {dias}."


def janela_aberta(
    semana: str, janela: dict | None, agora: datetime | None = None
) -> tuple[bool, str]:
    """Is the window open for ``semana``? Returns (open, reason).

    ``agora`` is injectable so tests do not depend on the wall clock.
    """
    momento = agora or datetime.now()  # noqa: DTZ005 — regra local do contrato

    if not janela:
        return False, "Fornecedor sem janela cadastrada."

    excecao = _decidir_extraordinaria(semana, janela, momento)
    if excecao is not None:
        return excecao

    if semana not in (janela.get("semanas_liberadas") or []):
        return False, f"A semana {semana} não está liberada para esta empresa."

    return _decidir_pelo_dia(janela, momento)


def resumo(janela: dict | None, semana: str, agora: datetime | None = None) -> dict:
    """Everything the configuration screen shows about one window."""
    aberta, motivo = janela_aberta(semana, janela, agora)
    janela = janela or {}
    dias = janela.get("dias") or []
    return {
        "empresa": janela.get("empresa", ""),
        "aberta": aberta,
        "motivo": motivo,
        "dias": dias,
        "dia_rotulo": rotulo_dia(dias[0]["dia"]) if dias else "",
        "abre": dias[0]["abre"] if dias else "",
        "fecha": dias[0]["fecha"] if dias else "",
        "semanas_liberadas": sorted(janela.get("semanas_liberadas") or []),
        "quantidade_semanas": len(janela.get("semanas_liberadas") or []),
        "extra": janela.get("extra") or [],
    }
