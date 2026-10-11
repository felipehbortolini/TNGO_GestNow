"""Funções puras do Início (D6): os formatadores e os tons que a tela lê.

Nada aqui toca banco, sessão ou relógio: recebe valor, devolve texto. O
``format_value`` da exportação é a fonte dos números — o mesmo formato vale na
tela, no Excel e no papel —, e o compacto de dinheiro segue a leitura dos
cards do protótipo (``R$ 44,6 mi``). Os limiares dos índices de desempenho são
os do protótipo: 1,00 ou mais é o plano; de 0,95 a 0,99 é atenção; abaixo
disso, crítico.
"""

from __future__ import annotations

from decimal import Decimal

from src.core.export_document import ValueKind, format_value

# Limiares de leitura do SPI e do CPI (home.js do protótipo).
ATTENTION_INDEX = Decimal("0.95")

_BILLION = Decimal(1_000_000_000)
_MILLION = Decimal(1_000_000)
_THOUSAND = Decimal(1_000)
_HUNDRED = Decimal(100)


def integer_text(value: int) -> str:
    """``1.240``: a contagem como a tela e o Excel a escrevem."""
    return format_value(ValueKind.INTEGER, value)


def index_text(value: Decimal | None) -> str:
    """``0,94``: o índice com duas casas; sem valor, ``sem dados``."""
    if value is None:
        return "sem dados"
    return format_value(ValueKind.DECIMAL, value, digits=2)


def decimal_text(value: Decimal | None, digits: int = 2) -> str:
    """``0,00``: o número decimal no formato de leitura; sem valor, travessão."""
    if value is None:
        return "-"
    return format_value(ValueKind.DECIMAL, value, digits=digits)


def percent_text(value: Decimal | None, digits: int = 1) -> str:
    """``61,8%``: pontos percentuais no formato de leitura; sem valor, travessão."""
    if value is None:
        return "-"
    return format_value(ValueKind.PERCENT, value, digits=digits)


def compact_brl(cents: int | None) -> str:
    """``R$ 44,6 mi``, ``R$ 12 mil``, ``R$ 950``: o dinheiro compacto dos cards."""
    if cents is None:
        return "-"
    reais = Decimal(cents) / _HUNDRED
    for limit, suffix in ((_BILLION, "bi"), (_MILLION, "mi"), (_THOUSAND, "mil")):
        if abs(reais) >= limit:
            return f"R$ {_one_decimal(reais / limit)} {suffix}"
    return f"R$ {_one_decimal(reais)}"


def signed_percent_text(value: Decimal | None, digits: int = 1) -> str:
    """``+1,5%`` ou ``-0,8%``: o desvio com o sinal explícito."""
    if value is None:
        return "-"
    text = format_value(ValueKind.PERCENT, value, digits=digits)
    return text if value < 0 else f"+{text}"


def delta_text(current: Decimal | None, previous: Decimal | None) -> str:
    """``0,02 acima vs. mês anterior``: a leitura do índice contra o mês anterior.

    O protótipo mostrava uma seta; aqui a direção vai por extenso, porque cor e
    seta nunca são o único sinal. Sem um dos lados, o texto fica vazio.
    """
    if current is None or previous is None:
        return ""
    difference = current - previous
    if difference == 0:
        return "estável vs. mês anterior"
    direction = "acima" if difference > 0 else "abaixo"
    return (
        f"{format_value(ValueKind.DECIMAL, abs(difference), digits=2)} {direction} vs. mês anterior"
    )


def index_tone(value: Decimal | None) -> str:
    """O tom do índice: ``ok``, ``warn``, ``erro`` ou ``info`` quando não há dado."""
    if value is None:
        return "info"
    if value >= 1:
        return "ok"
    return "warn" if value >= ATTENTION_INDEX else "erro"


def plural(count: int, singular: str, plural_text: str | None = None) -> str:
    """``1 dia``, ``2 dias``: a contagem com o substantivo no número certo."""
    noun = singular if count == 1 else (plural_text or f"{singular}s")
    return f"{integer_text(count)} {noun}"


def _one_decimal(value: Decimal) -> str:
    text = f"{value:.1f}".replace(".", ",")
    return text.removesuffix(",0")
