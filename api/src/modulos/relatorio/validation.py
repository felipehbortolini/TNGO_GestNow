"""Input validation for the Management reporting module.

Análise do período (ISSUE-081): o módulo, o tipo, o período, o texto (150 a 2.500 caracteres)
e o comentário de cada desvio detectado (20 a 600), com as mensagens do protótipo. The period
bounds are the Planning calculations' own; here the field and the message of the form live.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence

from src.core import calendario

WEEKLY = calendario.WEEKLY

MONTHLY = calendario.MONTHLY

KINDS = (WEEKLY, MONTHLY)

MIN_TEXT = 150

MAX_TEXT = 2500

MIN_COMMENT = 20

MAX_COMMENT = 600

FIELD_MODULE = "modulo"

FIELD_KIND = "tipo"

FIELD_PERIOD = "periodo"

FIELD_TEXT = "analise"

FIELD_SECTIONS = "secoes"

MODULE_MESSAGE = "Módulo inválido."

CHOOSE_MESSAGE = "Escolha o tipo e o período."

SECTION_MESSAGE = "Escolha ao menos uma seção."

TEXT_SHORT_MESSAGE = (
    "A análise deve ter ao menos 150 caracteres: panorama, desempenho dos períodos "
    "anteriores, causas e tendência."
)

TEXT_LONG_MESSAGE = "Até 2.500 caracteres."

COMMENT_SHORT_MESSAGE = (
    "Todo desvio negativo exige comentário (mínimo de 20 caracteres): causa, efeito e ação."
)

COMMENT_LONG_MESSAGE = "Até 600 caracteres."

LIMITS: Mapping[str, int] = {
    "texto_min": MIN_TEXT,
    "texto_max": MAX_TEXT,
    "comentario_min": MIN_COMMENT,
    "comentario_max": MAX_COMMENT,
}


def comment_field(index: int) -> str:
    """O nome do campo de um comentário no formulário: ``desvio_0``."""
    return f"desvio_{index}"


def clean_text(raw: str | None) -> str:
    """O texto com os espaços das pontas cortados, como ele é gravado."""
    return (raw or "").strip()


def validate_module(module: str, modules: Collection[str]) -> dict[str, str]:
    """A mensagem do módulo quando ele não é um dos módulos analisados."""
    return {} if module in modules else {FIELD_MODULE: MODULE_MESSAGE}


def validate_kind(kind: str) -> dict[str, str]:
    """A mensagem do tipo quando ele não é Semanal nem Mensal."""
    return {} if kind in KINDS else {FIELD_KIND: CHOOSE_MESSAGE}


def validate_period(kind: str, period: str, *, problem: str | None) -> dict[str, str]:
    """A mensagem do período: a escolha obrigatória ou o problema que o intervalo do projeto deu.

    O problema (inválido, anterior ao início do projeto ou futuro) vem do cálculo do dono; aqui
    ficam o campo e a mensagem de escolha do formulário.
    """
    if kind not in KINDS or not calendario.valid_period(kind, period):
        return {FIELD_PERIOD: CHOOSE_MESSAGE}
    return {FIELD_PERIOD: problem} if problem else {}


def validate_text(text: str) -> dict[str, str]:
    """O texto da análise contra os limites: 150 a 2.500 caracteres."""
    if len(text) < MIN_TEXT:
        return {FIELD_TEXT: TEXT_SHORT_MESSAGE}
    if len(text) > MAX_TEXT:
        return {FIELD_TEXT: TEXT_LONG_MESSAGE}
    return {}


def validate_comments(
    keys: Sequence[str], comments: Mapping[str, str], *, required: bool
) -> dict[str, str]:
    """O comentário de cada desvio detectado contra os limites: 20 a 600 caracteres.

    Comentário obrigatório vazio ou curto recebe a mensagem do protótipo; comentário longo
    recebe o teto, obrigatório ou não.
    """
    errors: dict[str, str] = {}
    for index, key in enumerate(keys):
        comment = clean_text(comments.get(key, ""))
        if required and len(comment) < MIN_COMMENT:
            errors[comment_field(index)] = COMMENT_SHORT_MESSAGE
        elif len(comment) > MAX_COMMENT:
            errors[comment_field(index)] = COMMENT_LONG_MESSAGE
    return errors
