"""The Jinja2 environment — and the small vocabulary every template shares.

Formatting a number, naming a state and asking whether the user may see a
button are three things that appear on nearly every screen. They live
here so no template invents its own version, and so a change of format is
one edit instead of forty.

Autoescape is on. The only value that ever reaches a template pre-escaped
is a chart payload, and that one goes through ``|tojson`` inside a
``<script type="application/json">`` block, which Jinja escapes correctly
for that context.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader

from src.core import ambiente, calculos, rbac, semanas

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=True,
    trim_blocks=True,
    lstrip_blocks=True,
)


def _numero_br(valor, casas: int = 1) -> str:
    """1234.5 → "1.234,5" — pt-BR, and never "1234.5" on a report."""
    try:
        numero = float(valor or 0)
    except (TypeError, ValueError):
        return "—"
    inteiro = f"{numero:,.{casas}f}"
    return inteiro.replace(",", " ").replace(".", ",").replace(" ", ".")


def _quantidade(valor) -> str:
    """Quantities drop the decimal when there is nothing after it."""
    numero = calculos.numero(valor)
    return _numero_br(numero, 0 if abs(numero - round(numero)) < 0.05 else 1)


# Unidades contáveis: meia unidade e meio transformador não existem.
UNIDADES_INTEIRAS = {"und", "unid", "un", "pç", "pc", "peça", "peca"}


def _medida(valor, unidade: str = "") -> str:
    """Format a quantity for a cell that is 60 pixels wide.

    A unidade muda a leitura, e por isso muda o formato:

    * contável (``und``) nunca leva decimal — "2,0 und" é ruído;
    * de 100 para cima o decimal não informa: "1.234,5 kg" numa célula
      estreita rouba espaço de dígito que importa;
    * abaixo de 100 o decimal é a informação: 2,5 m³ não é 3 m³;
    * acima de cem mil vira "123 mil", senão o número não cabe e a
      célula quebra a linha no meio do valor.

    Zero sai como travessão, e não como "0": a diferença entre "não
    produziu" e "não havia previsão" é o que a matriz precisa mostrar.
    """
    numero = calculos.numero(valor)
    if numero == 0:
        return "—"
    if abs(numero) >= 100_000:
        return _numero_br(numero / 1000, 0) + " mil"
    if (unidade or "").strip().lower() in UNIDADES_INTEIRAS:
        return _numero_br(numero, 0)
    if abs(numero) >= 100 or abs(numero - round(numero)) < 0.05:
        return _numero_br(numero, 0)
    return _numero_br(numero, 1)


def _intensidade_calor(percentual) -> str:
    """Where a percentage sits on the heat ramp, from ``0`` to ``1``.

    O mapa de calor pinta por interpolação, não por cinco caixinhas de
    cor chapada: 48% e 52% cruzavam uma fronteira de faixa e mudavam de
    laranja para amarelo como se fossem coisas diferentes, enquanto 26%
    e 49% dividiam exatamente a mesma cor. Uma rampa contínua devolve à
    cor a relação que ela deveria ter com o número.

    O topo da rampa é 100%: entregar 130% do previsto do dia não é
    "mais verde" que entregar 100%, é a mesma coisa boa — e deixar a
    escala aberta faria um dia excepcional achatar todos os outros.

    Devolve texto, e não float, porque o destino é uma custom property
    do CSS: ``0.62`` entra em ``--t`` e o ``color-mix`` faz o resto.
    """
    if percentual is None:
        return "0"
    valor = calculos.numero(percentual)
    return f"{min(max(valor, 0.0), 100.0) / 100:.3f}"


def _nivel_calor(percentual) -> int:
    """Heat band of a percentage. 0 means "there was no plan that day".

    Continua existindo para a única distinção que a rampa contínua NÃO
    consegue fazer: "sem previsão para o dia" não é 0% de aderência, é
    ausência de plano, e precisa de um tratamento à parte — cinza, não a
    ponta vermelha da escala.
    """
    if percentual is None:
        return 0
    valor = calculos.numero(percentual)
    if valor >= 100:
        return 5
    if valor >= 75:
        return 4
    if valor >= 50:
        return 3
    if valor >= 25:
        return 2
    return 1


def _percentual(valor, casas: int = 0) -> str:
    return f"{_numero_br(valor, casas)}%"


def _data_br(valor, *, com_hora: bool = False) -> str:
    if not valor:
        return "—"
    texto = str(valor)
    try:
        momento = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        return texto[:16]
    formato = "%d/%m/%Y %H:%M" if com_hora else "%d/%m/%Y"
    return momento.strftime(formato)


def _agora_br() -> str:
    return datetime.now(UTC).strftime("%d/%m/%Y às %H:%M")


def _chave_url(valor) -> str:
    """Activity keys carry a slash (S.30/2026::PS1-…) — encode it."""
    return quote(str(valor), safe="")


def _slug_do_ambiente() -> str:
    """The active environment's slug — for the links that leave Alpine.

    The two downloads and the printable report are real browser
    navigations without the Alpine header that carries the environment;
    their links take the slug in the query instead. Raising outside any
    environment is on purpose: a link rendered without one would mean a
    template serving downloads outside the seam that opens it.
    """
    return ambiente.slug_ativo()


def _pode(user, permissao: str) -> bool:
    return rbac.pode(user, permissao)


def _qualquer(user, *permissoes: str) -> bool:
    return rbac.qualquer(user, *permissoes)


# Anotados como dict[str, Any] porque os dois carregam valores de tipos
# diferentes — função, tupla, número. Sem a anotação o verificador infere
# uma união a partir do conteúdo e recusa o update, que aceita Any.
GLOBAIS: dict[str, Any] = {
    "pode": _pode,
    "qualquer": _qualquer,
    "agora_br": _agora_br,
    "slug_do_ambiente": _slug_do_ambiente,
    "DIAS": calculos.DIAS_ROTULO,
    "DIAS_NOME": calculos.DIAS_NOME,
    "FAIXA_ALTA": calculos.FAIXA_ALTA,
    "FAIXA_MEDIA": calculos.FAIXA_MEDIA,
    "proxima_acao": rbac.proxima_acao,
    "rotulo_perfil": rbac.rotulo,
    "rotulo_vinculo": rbac.rotulo_vinculo,
    "periodo_semana": semanas.periodo,
}

FILTROS: dict[str, Any] = {
    "num": _numero_br,
    "qtd": _quantidade,
    "medida": _medida,
    "nivel_calor": _nivel_calor,
    "intensidade_calor": _intensidade_calor,
    "pct": _percentual,
    "data_br": _data_br,
    "chave_url": _chave_url,
    "situacao": calculos.situacao_label,
    "aprovacao": calculos.aprovacao_label,
    "faixa": calculos.faixa,
}

jinja_env.globals.update(GLOBAIS)
jinja_env.filters.update(FILTROS)
