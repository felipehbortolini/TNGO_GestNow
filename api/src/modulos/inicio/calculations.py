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

from src.core import translations
from src.core.export_document import ValueKind, format_value

# Limiares de leitura do SPI e do CPI (home.js do protótipo).
ATTENTION_INDEX = Decimal("0.95")

# As faixas da situação da carteira (ISSUE-080, home.js): SPI e CPI têm as suas.
SPI_ATTENTION = Decimal("0.95")
SPI_CRITICAL = Decimal("0.90")
CPI_ATTENTION = Decimal("0.98")
CPI_CRITICAL = Decimal("0.93")

# A ordem do pior para o melhor e o rótulo que a tela imprime.
HEALTH_ORDER: dict[str, int] = {"ok": 0, "warn": 1, "erro": 2}
HEALTH_LABELS: dict[str, str] = {"ok": "Em dia", "warn": "Atenção", "erro": "Crítico"}

_BILLION = Decimal(1_000_000_000)
_MILLION = Decimal(1_000_000)
_THOUSAND = Decimal(1_000)
_HUNDRED = Decimal(100)


def integer_text(value: int) -> str:
    """``1.240``: a contagem como a tela e o Excel a escrevem."""
    return format_value(ValueKind.INTEGER, value)


def index_text(value: Decimal | None, idioma: str = "pt") -> str:
    """``0,94``: o índice com duas casas; sem valor, ``sem dados``."""
    if value is None:
        return translations.translate("inicio", "sem dados", idioma)
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


def delta_text(current: Decimal | None, previous: Decimal | None, idioma: str = "pt") -> str:
    """``0,02 acima vs. mês anterior``: a leitura do índice contra o mês anterior.

    O protótipo mostrava uma seta; aqui a direção vai por extenso, porque cor e
    seta nunca são o único sinal. Sem um dos lados, o texto fica vazio.
    """
    if current is None or previous is None:
        return ""
    difference = current - previous
    if difference == 0:
        return translations.translate("inicio", "estável vs. mês anterior", idioma)
    direction = translations.translate("inicio", "acima" if difference > 0 else "abaixo", idioma)
    template = translations.translate("inicio", "{value} {direction} vs. mês anterior", idioma)
    return template.format(
        value=format_value(ValueKind.DECIMAL, abs(difference), digits=2), direction=direction
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


def index_band(value: Decimal | None, attention: Decimal, critical: Decimal) -> str | None:
    """A faixa de um índice: ``ok`` no plano, ``warn`` na atenção, ``erro`` abaixo dela."""
    if value is None:
        return None
    if value >= attention:
        return "ok"
    return "warn" if value >= critical else "erro"


def health_band(spi: Decimal | None, cpi: Decimal | None) -> str | None:
    """A situação do projeto: o pior entre o SPI e o CPI, pelas faixas do protótipo.

    O SPI vale no plano a partir de 0,95 e é crítico abaixo de 0,90; o CPI, a
    partir de 0,98 e abaixo de 0,93. Sem um dos índices, vale o outro; sem os
    dois, não há situação.
    """
    bands = [
        band
        for band in (
            index_band(spi, SPI_ATTENTION, SPI_CRITICAL),
            index_band(cpi, CPI_ATTENTION, CPI_CRITICAL),
        )
        if band is not None
    ]
    if not bands:
        return None
    return max(bands, key=HEALTH_ORDER.__getitem__)


def health_label(health: str | None, idioma: str = "pt") -> str:
    """``Em dia``, ``Atenção`` ou ``Crítico``: o rótulo da situação (vazio sem ela)."""
    label = HEALTH_LABELS.get(health or "", "")
    return translations.translate("inicio", label, idioma) if label else ""


def input_number(value: Decimal) -> str:
    """``60``, ``25.5``, ``0.1``: o número no campo do formulário, sem zeros à direita."""
    return format(value.normalize(), "f")


def _one_decimal(value: Decimal) -> str:
    text = f"{value:.1f}".replace(".", ",")
    return text.removesuffix(",0")
