"""Week references — the calendar spine of the application.

A week is written ``S.30/2026`` everywhere: interface, storage, filename
and spreadsheet. This module is the only place that knows how to build
one, read one and turn one into real dates.

The ISO calendar is the source of truth: week 1 of a year is the one that
contains its first Thursday, and Monday opens the week. Nothing here
invents its own arithmetic.
"""

from datetime import UTC, date, datetime, timedelta

FORMATO = "S.{numero:02d}/{ano}"


def referencia(ano: int, numero: int) -> str:
    """Build the canonical week reference."""
    return FORMATO.format(numero=numero, ano=ano)


def partes(semana: str) -> tuple[int, int]:
    """Split a reference into (year, week number). (0, 0) when unreadable."""
    if "/" not in str(semana):
        return (0, 0)
    cabeca, cauda = str(semana).split("/", 1)
    numero = "".join(ch for ch in cabeca if ch.isdigit())
    ano = "".join(ch for ch in cauda if ch.isdigit())
    if not numero or not ano:
        return (0, 0)
    return (int(ano), int(numero))


def ordem(semana: str) -> tuple[int, int]:
    """Chronological sort key across year boundaries."""
    return partes(semana)


def semanas_no_ano(ano: int) -> int:
    """52 or 53, whichever the ISO calendar says for this year."""
    return date(ano, 12, 28).isocalendar().week


def inicio(semana: str) -> date | None:
    """Monday of the week, or None when the reference is unreadable."""
    ano, numero = partes(semana)
    if not ano or not numero or numero > semanas_no_ano(ano):
        return None
    return date.fromisocalendar(ano, numero, 1)


def fim(semana: str) -> date | None:
    """Sunday of the week."""
    abertura = inicio(semana)
    return abertura + timedelta(days=6) if abertura else None


def datas_dos_dias(semana: str) -> list[date]:
    """The seven dates of the week, Monday first. Empty when unreadable."""
    abertura = inicio(semana)
    if not abertura:
        return []
    return [abertura + timedelta(days=i) for i in range(7)]


def periodo(semana: str) -> str:
    """Human range: "20/07 a 26/07/2026"."""
    abertura, fechamento = inicio(semana), fim(semana)
    if not abertura or not fechamento:
        return ""
    return (
        f"{abertura.day:02d}/{abertura.month:02d} a "
        f"{fechamento.day:02d}/{fechamento.month:02d}/{fechamento.year}"
    )


def descrever(semana: str) -> dict:
    """Everything a screen needs to render one week reference."""
    abertura, fechamento = inicio(semana), fim(semana)
    ano, numero = partes(semana)
    return {
        "id": semana,
        "ano": ano,
        "numero": numero,
        "inicio": abertura.isoformat() if abertura else "",
        "fim": fechamento.isoformat() if fechamento else "",
        "periodo": periodo(semana),
        "mes": abertura.month if abertura else 0,
        "valida": abertura is not None,
    }


def da_data(dia: date) -> str:
    """Week reference that contains a given date."""
    iso = dia.isocalendar()
    return referencia(iso.year, iso.week)


def atual(agora: datetime | None = None) -> str:
    """Week reference of today."""
    momento = agora or datetime.now(UTC)
    return da_data(momento.date())


def deslocar(semana: str, passos: int) -> str:
    """Move ``passos`` weeks forward (positive) or back (negative)."""
    abertura = inicio(semana)
    if not abertura:
        return semana
    return da_data(abertura + timedelta(weeks=passos))


def janela_de_semanas(semana: str, atras: int = 5, adiante: int = 2) -> list[str]:
    """A contiguous horizon around one week, oldest first."""
    return [deslocar(semana, p) for p in range(-atras, adiante + 1)]


def listar_ano(ano: int) -> list[dict]:
    """Every ISO week of a year, described."""
    return [descrever(referencia(ano, n)) for n in range(1, semanas_no_ano(ano) + 1)]
