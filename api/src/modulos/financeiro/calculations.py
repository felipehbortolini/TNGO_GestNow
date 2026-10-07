"""Pure calculations of the Financeiro module (D6).

Every rule is one function, named after the business term in ``LEIA-ME.md``; nothing here reads
the clock, the database or the request. Money is integer cents (D5).
"""

from __future__ import annotations

import math
from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Any

from src.core.import_values import normalize_text

LEAF_LEVEL = 3
PORTFOLIO_MAIN_LEVEL = 2
WEIGHT_TOTAL = Decimal(100)
HUNDREDTHS = Decimal(100)
TWO_PLACES = Decimal("0.01")
ONE_PLACE = Decimal("0.1")
BUDGET_SOURCE = "orcamento"
EQUAL_SHARE_FALLBACK = Decimal(1)
CODE_SEPARATOR = "."
ROOT_CODE = "0"
MANUAL_ORIGIN = "Manual"
ERP_ORIGIN = "ERP"
DEFAULT_DEVIATION_BANDS: tuple[int, int, int] = (1, 5, 10)
NEUTRAL_KEY = "neutro"
OVERCOST_KEY = "sobrecusto"
SAVING_KEY = "economia"
OVERCOST_TONE = "erro"
SAVING_TONE = "ok"
NEUTRAL_TONE = "neutro"
OVERCOST_ICON = "sobe"
SAVING_ICON = "desce"
NEUTRAL_ICON = "igual"
DEVIATION_BANDS_MESSAGE = "As faixas do desvio precisam de três limites."


# ── Valor orçado ─────────────────────────────────────────────────────────


def budgeted_cents(quantity: Decimal | None, unit_price_cents: int | None) -> int:
    """Valor orçado: quantidade x preço unitário, in whole cents, half a cent rounding up."""
    if quantity is None or unit_price_cents is None:
        return 0
    return int((quantity * unit_price_cents).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def code_key(code: str) -> tuple[int, ...]:
    """The sort key of a code: ``1.10`` comes after ``1.2``, as the numbers say."""
    return tuple(int(part) if part.isdigit() else 0 for part in code.split(CODE_SEPARATOR))


# ── Árvore da EAC ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ItemLine:
    """An item of the breakdown as the tree needs it, with the names already resolved."""

    id: int
    parent_id: int | None
    code: str
    description: str
    level: int
    cost_type: str | None = None
    unit: str | None = None
    quantity: Decimal | None = None
    unit_price_cents: int | None = None
    base_cents: int | None = None
    capex: bool | None = None
    cost_center: str | None = None
    responsible: str | None = None
    version: int = 1


@dataclass(frozen=True)
class TreeRow:
    """A line of the tree: what the table, the Excel and the printable version print.

    ``level`` is 0 for the root line (the project, or the portfolio), 1 to 3 for package,
    subpackage and item. In the Portfólio the levels mean portfolio, project and main package.
    ``item_id`` is set only for a line that is an item of a project.
    """

    code: str
    description: str
    level: int
    budget_cents: int
    item_id: int | None = None
    project_id: int | None = None
    project_label: str | None = None
    cost_type: str | None = None
    unit: str | None = None
    quantity: Decimal | None = None
    unit_price_cents: int | None = None
    capex: bool | None = None
    cost_center: str | None = None
    responsible: str | None = None
    version: int | None = None
    weight: Decimal | None = None
    is_root: bool = False


def item_totals(items: Sequence[ItemLine]) -> dict[int, int]:
    """Valor orçado of every item: the product for an item, the sum of its children for the rest.

    Packages and subpackages add up on the server, in cents, from the items below them; a
    package without items is worth zero. An item with a frozen base (a revision) uses it
    instead of the product: that is the value in force of the revision.
    """
    children: dict[int | None, list[ItemLine]] = {}
    for item in items:
        children.setdefault(item.parent_id, []).append(item)
    totals: dict[int, int] = {}

    def total_of(item: ItemLine) -> int:
        if item.level >= LEAF_LEVEL:
            totals[item.id] = (
                item.base_cents
                if item.base_cents is not None
                else budgeted_cents(item.quantity, item.unit_price_cents)
            )
        else:
            totals[item.id] = sum(total_of(child) for child in children.get(item.id, ()))
        return totals[item.id]

    for item in children.get(None, ()):
        total_of(item)
    return totals


def project_total_cents(items: Sequence[ItemLine]) -> int:
    """Orçamento vigente of the project on the EAC: the sum of its packages (level 1)."""
    totals = item_totals(items)
    return sum(totals.get(item.id, 0) for item in items if item.level == 1)


def build_project_tree(
    items: Sequence[ItemLine], *, project_id: int, project_label: str, root_description: str
) -> tuple[TreeRow, ...]:
    """The tree of a project: the root line (code 0) with the total, then every item by code."""
    totals = item_totals(items)
    ordered = sorted(items, key=lambda item: code_key(item.code))
    rows = tuple(
        TreeRow(
            code=item.code,
            description=item.description,
            level=item.level,
            budget_cents=totals.get(item.id, 0),
            item_id=item.id,
            project_id=project_id,
            project_label=project_label,
            cost_type=item.cost_type,
            unit=item.unit,
            quantity=item.quantity,
            unit_price_cents=item.unit_price_cents,
            capex=item.capex if item.level >= LEAF_LEVEL else None,
            cost_center=item.cost_center,
            responsible=item.responsible,
            version=item.version,
        )
        for item in ordered
    )
    root = TreeRow(
        code=ROOT_CODE,
        description=root_description,
        level=0,
        budget_cents=sum(row.budget_cents for row in rows if row.level == 1),
        project_id=project_id,
        project_label=project_label,
        is_root=True,
    )
    return (root, *rows)


@dataclass(frozen=True)
class PortfolioProject:
    """A project of the portfolio as the portfolio tree needs it."""

    id: int
    label: str
    manager: str | None
    items: Sequence[ItemLine]
    weight: Decimal | None = None


def build_portfolio_tree(
    projects: Sequence[PortfolioProject], *, root_description: str
) -> tuple[TreeRow, ...]:
    """The tree of the Portfólio: line 0 is the portfolio, level 1 each project, level 2 its packages.

    The projects without items do not appear. The codes are the numbering of the portfolio: the
    project is ``1``, ``2``..., and its packages ``1.1``, ``1.2``... in the order of the projects.
    """
    rows: list[TreeRow] = []
    number = 0
    for project in projects:
        if not project.items:
            continue
        number += 1
        rows.extend(_project_lines(project, number))
    root = TreeRow(
        code=ROOT_CODE,
        description=root_description,
        level=0,
        budget_cents=sum(row.budget_cents for row in rows if row.level == 1),
        is_root=True,
    )
    return (root, *rows)


def _project_lines(project: PortfolioProject, number: int) -> list[TreeRow]:
    totals = item_totals(project.items)
    packages = sorted(
        (item for item in project.items if item.level == 1),
        key=lambda item: code_key(item.code),
    )
    lines = [
        TreeRow(
            code=str(number),
            description=project.label,
            level=1,
            budget_cents=sum(totals.get(package.id, 0) for package in packages),
            project_id=project.id,
            project_label=project.label,
            responsible=project.manager,
            weight=project.weight,
        )
    ]
    lines.extend(
        TreeRow(
            code=f"{number}{CODE_SEPARATOR}{package.code}",
            description=package.description,
            level=PORTFOLIO_MAIN_LEVEL,
            budget_cents=totals.get(package.id, 0),
            project_id=project.id,
            project_label=project.label,
            responsible=package.responsible,
        )
        for package in packages
    )
    return lines


def filter_tree(
    rows: Sequence[TreeRow],
    *,
    search: str = "",
    max_level: int = LEAF_LEVEL,
    cost_type: str = "",
) -> tuple[TreeRow, ...]:
    """The lines that match the search and the cost type, with their ancestors, down to the level.

    The root line always stays, filter or not. A line matches when the search is inside its code
    and description (accents and case ignored) and, if a cost type was chosen, when it is an item
    of that type. The ancestors of a match stay so the tree still reads as a tree.
    """
    needle = normalize_text(search)
    roots = tuple(row for row in rows if row.is_root)
    body = [row for row in rows if not row.is_root and row.level <= max_level]
    if not needle and not cost_type:
        return (*roots, *body)
    wanted: set[str] = set()
    for row in body:
        if _matches(row, needle, cost_type):
            wanted.add(row.code)
            wanted.update(_ancestor_codes(row.code))
    return (*roots, *(row for row in body if row.code in wanted))


def _matches(row: TreeRow, needle: str, cost_type: str) -> bool:
    text_matches = not needle or needle in normalize_text(f"{row.code} {row.description}")
    type_matches = not cost_type or (row.level >= LEAF_LEVEL and row.cost_type == cost_type)
    return text_matches and type_matches


def _ancestor_codes(code: str) -> list[str]:
    parts = code.split(CODE_SEPARATOR)
    return [CODE_SEPARATOR.join(parts[:size]) for size in range(1, len(parts))]


def filtered_total_cents(rows: Sequence[TreeRow]) -> int:
    """Total filtrado: the sum of the items shown, or of the shallowest level when none is shown."""
    body = [row for row in rows if not row.is_root]
    items = [row for row in body if row.level >= LEAF_LEVEL]
    if items:
        return sum(row.budget_cents for row in items)
    if not body:
        return 0
    shallowest = min(row.level for row in body)
    return sum(row.budget_cents for row in body if row.level == shallowest)


def parent_codes(rows: Sequence[TreeRow]) -> frozenset[str]:
    """The codes of the lines that have lines below them: the ones that get the toggle arrow."""
    parents = {CODE_SEPARATOR.join(row.code.split(CODE_SEPARATOR)[:-1]) for row in rows}
    parents.discard("")
    if any(row.is_root for row in rows) and any(not row.is_root for row in rows):
        parents.add(ROOT_CODE)
    return frozenset(parents)


# ── Orçado atual, saldo livre e item novo ────────────────────────────────


@dataclass(frozen=True)
class ReallocationLine:
    """Um remanejamento aplicado: de onde saiu, para onde foi, quanto e a revisão que o consolida."""

    source_item_id: int
    target_item_id: int
    value_cents: int
    revision: int


def current_base_cents(
    items: Sequence[ItemLine],
    *,
    revision_bases: Mapping[int, int],
    latest_revision: int | None,
    reallocations: Sequence[ReallocationLine] = (),
) -> dict[int, int]:
    """Orçado atual de cada item: a base da última revisão mais os remanejamentos aplicados.

    Sem revisão alguma a base é quantidade x preço; com revisão, é a linha congelada de
    ``eac_revisao_item`` e zero para o item que não está nela. Os remanejamentos aplicados e
    ainda não consolidados (``revisao`` igual à próxima revisão; zero sem revisão) tiram o
    valor da origem e o põem no destino.
    """
    next_revision = 0 if latest_revision is None else latest_revision + 1
    bases = {
        item.id: (
            revision_bases.get(item.id, 0)
            if latest_revision is not None
            else budgeted_cents(item.quantity, item.unit_price_cents)
        )
        for item in items
    }
    for line in reallocations:
        if line.revision != next_revision:
            continue
        if line.source_item_id in bases:
            bases[line.source_item_id] -= line.value_cents
        if line.target_item_id in bases:
            bases[line.target_item_id] += line.value_cents
    return bases


@dataclass(frozen=True)
class ReservationLine:
    """Reserva de saldo: a transferência de uma SM aberta que ainda não foi aplicada."""

    source_item_id: int
    value_cents: int


def free_balance_cents(
    item_id: int,
    *,
    base_cents: int,
    committed_cents: int,
    reservations: Sequence[ReservationLine],
) -> int:
    """Saldo livre do item: orçado atual menos comprometido menos o reservado em outras SMs abertas."""
    reserved = sum(line.value_cents for line in reservations if line.source_item_id == item_id)
    return base_cents - committed_cents - reserved


def next_item_code(parent_code: str | None, codes: Sequence[str]) -> str:
    """Código do item novo: o próximo número livre entre os irmãos, sob o pai informado.

    Sem pai, o item é um pacote novo e a numeração é a da raiz; códigos que não são filhos
    diretos do pai (netos, por exemplo) não entram na conta.
    """
    prefix = f"{parent_code}{CODE_SEPARATOR}" if parent_code else ""
    siblings = [
        int(code[len(prefix) :])
        for code in codes
        if code.startswith(prefix) and code[len(prefix) :].isdigit()
    ]
    return f"{prefix}{max(siblings, default=0) + 1}"


# ── Ponderação da carteira ───────────────────────────────────────────────


@dataclass(frozen=True)
class WeightCriterion:
    """A criterion of the weighting: its id, its weight (%) and where its value comes from."""

    id: str
    weight: Decimal
    source: str


@dataclass(frozen=True)
class WeightInput:
    """What the weighting reads of a project: the budget in force on the EAC and its grades."""

    project_id: int
    budget_cents: int
    grades: Mapping[str, int]


@dataclass(frozen=True)
class ProjectWeight:
    """The weight of the project in the portfolio (%, two places) and each criterion's share."""

    weight: Decimal
    shares: Mapping[str, Decimal]


def largest_remainder[Key: Hashable](
    raw: Mapping[Key, Decimal], total: Decimal = WEIGHT_TOTAL
) -> dict[Key, Decimal]:
    """Maior resto: scale the values to the total in hundredths, so the sum is always exact.

    Each value is floored to hundredths and the hundredths that are missing go, one each, to the
    values with the largest remainders (a tie keeps the order of the input). When every value
    is zero the total is split equally, so the sum still closes.
    """
    if not raw:
        return {}
    target = int(total * HUNDREDTHS)
    values = raw if sum(raw.values(), Decimal(0)) > 0 else dict.fromkeys(raw, EQUAL_SHARE_FALLBACK)
    sum_values = sum(values.values(), Decimal(0))
    scaled = {key: value / sum_values * target for key, value in values.items()}
    floors = {
        key: int(value.to_integral_value(rounding=ROUND_FLOOR)) for key, value in scaled.items()
    }
    missing = target - sum(floors.values())
    by_remainder = sorted(scaled, key=lambda key: scaled[key] - floors[key], reverse=True)
    for key in by_remainder[:missing]:
        floors[key] += 1
    return {key: Decimal(cents) / HUNDREDTHS for key, cents in floors.items()}


def portfolio_weights(
    projects: Sequence[WeightInput], criteria: Sequence[WeightCriterion]
) -> dict[int, ProjectWeight]:
    """Ponderação da carteira: the weight of each project, closed at 100,00 by the largest remainder.

    The share of a project in a criterion is its value over the sum of the portfolio: the budget
    in force on the EAC for a criterion whose source is the budget, the grade (1 to 5) for the
    others; with a zero sum the shares are equal. The weight is the sum of the criteria weights
    times the shares, over the sum of the criteria weights.
    """
    shares = _criterion_shares(projects, criteria)
    criteria_sum = sum((criterion.weight for criterion in criteria), Decimal(0)) or Decimal(1)
    raw = {
        project.project_id: sum(
            (
                criterion.weight * shares[project.project_id][criterion.id] / HUNDREDTHS
                for criterion in criteria
            ),
            Decimal(0),
        )
        / criteria_sum
        * HUNDREDTHS
        for project in projects
    }
    weights = largest_remainder(raw)
    return {
        project.project_id: ProjectWeight(
            weight=weights[project.project_id],
            shares={
                key: share.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
                for key, share in shares[project.project_id].items()
            },
        )
        for project in projects
    }


def _criterion_shares(
    projects: Sequence[WeightInput], criteria: Sequence[WeightCriterion]
) -> dict[int, dict[str, Decimal]]:
    shares: dict[int, dict[str, Decimal]] = {project.project_id: {} for project in projects}
    for criterion in criteria:
        values = {project.project_id: _value_of(project, criterion) for project in projects}
        total = sum(values.values(), Decimal(0))
        for project in projects:
            shares[project.project_id][criterion.id] = (
                values[project.project_id] / total * HUNDREDTHS
                if total
                else HUNDREDTHS / len(projects)
            )
    return shares


def _value_of(project: WeightInput, criterion: WeightCriterion) -> Decimal:
    if criterion.source == BUDGET_SOURCE:
        return Decimal(project.budget_cents)
    return Decimal(project.grades.get(criterion.id, 0))


# ── Projeção, desvio e faixas do mapa de calor (ISSUE-031) ───────────────


def baseline_base_cents(
    items: Sequence[ItemLine],
    *,
    revision_bases: Mapping[int, int],
    latest_revision: int | None,
) -> dict[int, int]:
    """Linha de base de cada item: a base congelada da última revisão, ou quantidade x preço.

    É o valor de antes dos remanejamentos aplicados e ainda não consolidados: sem revisão alguma
    a base é quantidade x preço; com revisão, é a linha congelada de ``eac_revisao_item`` e zero
    para o item que não está nela.
    """
    return current_base_cents(items, revision_bases=revision_bases, latest_revision=latest_revision)


def reallocation_cents(current_cents: int, baseline_cents: int) -> int:
    """Remanejamentos não consolidados: o orçado atual menos a linha de base do item."""
    return current_cents - baseline_cents


def saldo_a_comprometer_cents(current_cents: int, committed_cents: int) -> int:
    """Saldo a comprometer: o orçado atual menos o comprometido; negativo é sobrecusto."""
    return current_cents - committed_cents


def deviation_cents(projection_cents: int, current_cents: int) -> int:
    """Desvio do item: a projeção no término menos o orçado atual; positivo é sobrecusto."""
    return projection_cents - current_cents


def deviation_percent(deviation: int, current_cents: int) -> Decimal | None:
    """Desvio percentual sobre o orçado atual, com uma casa; nenhum quando o orçado atual é zero."""
    if current_cents == 0:
        return None
    return (Decimal(deviation) / Decimal(current_cents) * HUNDREDTHS).quantize(
        ONE_PLACE, rounding=ROUND_HALF_UP
    )


@dataclass(frozen=True)
class DeviationBand:
    """A faixa do desvio no mapa de calor: chave, tom do Design System, nível e rótulo."""

    key: str
    tone: str
    level: int
    label: str


def deviation_band(
    percent: Decimal | None, bands: Sequence[Decimal | int | float] = DEFAULT_DEVIATION_BANDS
) -> DeviationBand:
    """Faixa do desvio pelas faixas vigentes dos parâmetros, na semântica do protótipo.

    Dentro da primeira faixa o desvio é neutro; a partir dela o nível cresce com o segundo e o
    terceiro limites: até o segundo é 1, até o terceiro é 2 e acima dele é 3. Sobrecusto usa a
    família ``erro`` do Design System e economia a família ``ok``; o tom é acompanhado do sinal
    no valor e do ícone na célula.
    """
    limits = tuple(_limit_of(band) for band in bands)
    if len(limits) != 3:
        raise ValueError(DEVIATION_BANDS_MESSAGE)
    if percent is None:
        return DeviationBand(key=NEUTRAL_KEY, tone=NEUTRAL_TONE, level=0, label="Sem desvio")
    first, middle, last = limits
    magnitude = abs(percent)
    if magnitude < first:
        return DeviationBand(
            key=NEUTRAL_KEY, tone=NEUTRAL_TONE, level=0, label=f"Até {_limit_text(first)}%"
        )
    over = percent > 0
    level = 3 if magnitude > last else 2 if magnitude > middle else 1
    family = OVERCOST_KEY if over else SAVING_KEY
    return DeviationBand(
        key=f"{family}-{level}",
        tone=OVERCOST_TONE if over else SAVING_TONE,
        level=level,
        label=_band_label(family, level, limits=limits),
    )


def _limit_of(band: Decimal | int | float) -> Decimal:
    return band if isinstance(band, Decimal) else Decimal(str(band))


def _limit_text(limit: Decimal) -> str:
    return format(limit.normalize(), "f")


def _band_label(family: str, level: int, *, limits: tuple[Decimal, Decimal, Decimal]) -> str:
    name = "Sobrecusto" if family == OVERCOST_KEY else "Economia"
    first, middle, last = limits
    if level == 1:
        return f"{name} de {_limit_text(first)}% a {_limit_text(middle)}%"
    if level == 2:
        return f"{name} de {_limit_text(middle)}% a {_limit_text(last)}%"
    return f"{name} acima de {_limit_text(last)}%"


def _heatmap_faixa(
    limites: Mapping[str, float], *, tom: str, nivel: int, icone: str, rotulo: str
) -> dict[str, object]:
    return {**limites, "tom": tom, "nivel": nivel, "icone": icone, "rotulo": rotulo}


def deviation_heatmap_faixas(
    bands: Sequence[Decimal | int | float] = DEFAULT_DEVIATION_BANDS,
) -> tuple[dict[str, object], ...]:
    """As faixas do desvio no contrato do visual Tabela Heatmap (D11).

    Os limites são os parâmetros vigentes e a classificação é a mesma de ``deviation_band``:
    dentro da primeira faixa o desvio é neutro, até o segundo limite é nível 1, até o terceiro
    é 2 e acima dele é 3. Sobrecusto usa a família ``erro`` e economia a ``ok``; o ícone
    (``sobe``, ``desce`` ou ``igual``) é o sinal além da cor. A lista vai da faixa mais
    específica para a mais geral, como o visual procura a faixa do valor.
    """
    limits = tuple(_limit_of(band) for band in bands)
    if len(limits) != 3:
        raise ValueError(DEVIATION_BANDS_MESSAGE)
    first, middle, last = limits
    return (
        _heatmap_faixa(
            {"maior_que": float(last)},
            tom=OVERCOST_TONE,
            nivel=3,
            icone=OVERCOST_ICON,
            rotulo=_band_label(OVERCOST_KEY, 3, limits=limits),
        ),
        _heatmap_faixa(
            {"maior_que": float(middle), "ate": float(last)},
            tom=OVERCOST_TONE,
            nivel=2,
            icone=OVERCOST_ICON,
            rotulo=_band_label(OVERCOST_KEY, 2, limits=limits),
        ),
        _heatmap_faixa(
            {"de": float(first), "ate": float(middle)},
            tom=OVERCOST_TONE,
            nivel=1,
            icone=OVERCOST_ICON,
            rotulo=_band_label(OVERCOST_KEY, 1, limits=limits),
        ),
        _heatmap_faixa(
            {"maior_que": float(-first), "menor_que": float(first)},
            tom=NEUTRAL_TONE,
            nivel=1,
            icone=NEUTRAL_ICON,
            rotulo=f"Até {_limit_text(first)}%",
        ),
        _heatmap_faixa(
            {"menor_que": float(-last)},
            tom=SAVING_TONE,
            nivel=3,
            icone=SAVING_ICON,
            rotulo=_band_label(SAVING_KEY, 3, limits=limits),
        ),
        _heatmap_faixa(
            {"de": float(-last), "menor_que": float(-middle)},
            tom=SAVING_TONE,
            nivel=2,
            icone=SAVING_ICON,
            rotulo=_band_label(SAVING_KEY, 2, limits=limits),
        ),
        _heatmap_faixa(
            {"de": float(-middle), "ate": float(-first)},
            tom=SAVING_TONE,
            nivel=1,
            icone=SAVING_ICON,
            rotulo=_band_label(SAVING_KEY, 1, limits=limits),
        ),
    )


@dataclass(frozen=True)
class ProjectionFact:
    """Uma projeção no término do item: o valor, a data do fato e de onde ele veio."""

    item_id: int
    value_cents: int
    on: date
    origin: str = MANUAL_ORIGIN


def latest_projections(facts: Sequence[ProjectionFact]) -> dict[int, ProjectionFact]:
    """A projeção vigente de cada item: o fato de data mais recente; no empate, o do ERP.

    A projeção manual e a do fechamento do ERP convivem no histórico; o fato mais recente vence.
    Data igual resolve para o ERP, porque o fechamento é o número oficial do mês; entre fatos de
    mesma data e mesma origem fica o último da sequência, que é o último gravado.
    """
    latest: dict[int, ProjectionFact] = {}
    for fact in facts:
        current = latest.get(fact.item_id)
        if current is None or _projection_order(fact) >= _projection_order(current):
            latest[fact.item_id] = fact
    return latest


def _projection_order(fact: ProjectionFact) -> tuple[date, int]:
    return (fact.on, 1 if fact.origin == ERP_ORIGIN else 0)


@dataclass(frozen=True)
class ProjectedTotal:
    """A projeção no término por item e o total do projeto, como o mapa de controle os lê."""

    by_item: Mapping[int, int]
    total_cents: int


def projected_total_cents(
    items: Sequence[ItemLine],
    *,
    current_bases: Mapping[int, int],
    facts: Sequence[ProjectionFact],
) -> ProjectedTotal:
    """Projeção no término de cada item e do projeto, em centavos.

    A projeção vigente de um item é a do fato mais recente; sem fato algum vale o orçado atual,
    que é o desvio zero de quem ainda não se pronunciou. Os pacotes e subpacotes somam os filhos
    e o total do projeto é a soma dos pacotes (nível 1).
    """
    vigentes = {item_id: fact.value_cents for item_id, fact in latest_projections(facts).items()}
    children: dict[int | None, list[ItemLine]] = {}
    for item in items:
        children.setdefault(item.parent_id, []).append(item)
    by_item: dict[int, int] = {}

    def total_of(item: ItemLine) -> int:
        if item.level >= LEAF_LEVEL:
            by_item[item.id] = vigentes.get(item.id, current_bases.get(item.id, 0))
        else:
            by_item[item.id] = sum(total_of(child) for child in children.get(item.id, ()))
        return by_item[item.id]

    for item in children.get(None, ()):
        total_of(item)
    return ProjectedTotal(
        by_item=by_item,
        total_cents=sum(by_item.get(item.id, 0) for item in items if item.level == 1),
    )


@dataclass(frozen=True)
class ErpCostFact:
    """Um mês de custo do ERP de um item: comprometido e realizado do mês e projeção do fechamento."""

    item_id: int
    month: date
    committed_cents: int | None = None
    actual_cents: int | None = None
    projection_cents: int | None = None


@dataclass(frozen=True)
class ErpTotals:
    """O acumulado de comprometido e realizado dos fatos do ERP até a data de corte."""

    committed_cents: int
    actual_cents: int


def erp_totals_until(facts: Sequence[ErpCostFact], *, cutoff: date) -> dict[int, ErpTotals]:
    """Custo do ERP por item até a data de corte: soma os fatos dos meses do corte para trás.

    Cada fato é o movimento do mês, não o acumulado; o acumulado é a soma, como o protótipo
    mostrava no mapa de controle. O mês do corte entra e os meses futuros ficam de fora.
    """
    totals: dict[int, ErpTotals] = {}
    for fact in facts:
        if fact.month > cutoff:
            continue
        previous = totals.get(fact.item_id, ErpTotals(committed_cents=0, actual_cents=0))
        totals[fact.item_id] = ErpTotals(
            committed_cents=previous.committed_cents + (fact.committed_cents or 0),
            actual_cents=previous.actual_cents + (fact.actual_cents or 0),
        )
    return totals


# ── Ficha do contrato: valor, medido, saldo e término (ISSUE-032) ────────


SITUATION_UNDER_REVIEW = "Em análise"
SITUATION_APPROVED = "Aprovada"
SITUATION_INVOICED = "Faturada"
SITUATION_PAID = "Paga"
SITUATION_RETURNED = "Devolvida"
MEASUREMENT_SITUATIONS = (
    SITUATION_UNDER_REVIEW,
    SITUATION_APPROVED,
    SITUATION_INVOICED,
    SITUATION_PAID,
    SITUATION_RETURNED,
)
MEASURED_SITUATIONS = (SITUATION_APPROVED, SITUATION_INVOICED, SITUATION_PAID)

CASCADE_ORIGINAL = "original"
CASCADE_ADDENDA = "aditivos"
CASCADE_CURRENT = "atual"
CASCADE_MEASURED = "medido"
CASCADE_BALANCE = "saldo"


@dataclass(frozen=True)
class ContractAddendumLine:
    """Um aditivo do contrato: valor em centavos (negativo é supressão) e dias de prorrogação."""

    value_cents: int = 0
    days: int = 0


@dataclass(frozen=True)
class ContractMeasurementLine:
    """Uma medição do contrato: valor bruto em centavos e a situação do fluxo."""

    value_cents: int
    situation: str


def contract_current_value_cents(
    original_cents: int, addenda: Sequence[ContractAddendumLine]
) -> int:
    """Valor atual do contrato: o valor original mais os aditivos aprovados."""
    return original_cents + sum(addendum.value_cents for addendum in addenda)


def contract_measured_cents(measurements: Sequence[ContractMeasurementLine]) -> int:
    """Medido aprovado: a soma do bruto das medições Aprovada, Faturada ou Paga."""
    return sum(
        measurement.value_cents
        for measurement in measurements
        if measurement.situation in MEASURED_SITUATIONS
    )


def contract_balance_to_invoice_cents(current_value_cents: int, measured_cents: int) -> int:
    """Saldo a faturar: o valor atual menos o medido aprovado."""
    return current_value_cents - measured_cents


def contract_current_end_date(original_end: date, addenda: Sequence[ContractAddendumLine]) -> date:
    """Término vigente: o término original mais os dias dos aditivos."""
    return original_end + timedelta(days=sum(addendum.days for addendum in addenda))


def contract_cascade_steps(
    *,
    original_cents: int,
    addenda: Sequence[ContractAddendumLine],
    measurements: Sequence[ContractMeasurementLine],
) -> tuple[dict[str, Any], ...]:
    """Degraus da cascata do contrato no contrato de dados do visual ``cascata-contrato``.

    O valor original é um total; os aditivos aprovados são a variação (negativa na supressão);
    o valor atual e o saldo a faturar são totais; o medido é a redução, com o sinal que o
    visual lê.
    """
    current_cents = contract_current_value_cents(original_cents, addenda)
    measured_cents = contract_measured_cents(measurements)
    return (
        {
            "id": CASCADE_ORIGINAL,
            "rotulo": "Valor original",
            "tipo": "total",
            "valor": original_cents,
        },
        {
            "id": CASCADE_ADDENDA,
            "rotulo": "Aditivos aprovados",
            "valor": sum(addendum.value_cents for addendum in addenda),
        },
        {
            "id": CASCADE_CURRENT,
            "rotulo": "Valor atual",
            "tipo": "total",
            "valor": current_cents,
        },
        {
            "id": CASCADE_MEASURED,
            "rotulo": "Medido",
            "valor": -measured_cents,
        },
        {
            "id": CASCADE_BALANCE,
            "rotulo": "Saldo a faturar",
            "tipo": "total",
            "valor": contract_balance_to_invoice_cents(current_cents, measured_cents),
        },
    )


# ── Marcos, claims e EOT (ISSUE-033) ─────────────────────────────────────


MILESTONE_PCT_TOTAL = 100

MILESTONE_FORECAST = "Previsto"
MILESTONE_EVIDENCE_SENT = "Evidência enviada"
MILESTONE_APPROVED = "Aprovado"
MILESTONE_INVOICED = "Faturado"
MILESTONE_PAID = "Pago"

MILESTONE_PENDING_SITUATIONS = (MILESTONE_FORECAST, MILESTONE_EVIDENCE_SENT)

CLAIM_NOTIFIED = "Notificado"
CLAIM_UNDER_REVIEW = "Em análise"
CLAIM_IN_NEGOTIATION = "Em negociação"
CLAIM_AGREED = "Acordado"
CLAIM_REJECTED = "Rejeitado"
CLAIM_IN_DISPUTE = "Em disputa"
CLAIM_CLOSED = "Encerrado"

EXTENSION_REQUESTED = "Solicitada"
EXTENSION_UNDER_REVIEW = "Em análise"
EXTENSION_GRANTED = "Concedida"
EXTENSION_PARTIALLY_GRANTED = "Concedida parcialmente"
EXTENSION_DENIED = "Negada"


def milestone_value_cents(current_value_cents: int, pct: int) -> int:
    """Valor do marco: o percentual sobre o valor atual do contrato, meio centavo para cima."""
    return int(
        (Decimal(current_value_cents * pct) / HUNDREDTHS).quantize(
            Decimal(1), rounding=ROUND_HALF_UP
        )
    )


def milestone_retention_cents(value_cents: int, retention_pct: int) -> int:
    """Retenção do marco: o valor do marco pela retenção do contrato, meio centavo para cima."""
    return int(
        (Decimal(value_cents * retention_pct) / HUNDREDTHS).quantize(
            Decimal(1), rounding=ROUND_HALF_UP
        )
    )


def milestone_pct_total(pcts: Sequence[int]) -> int:
    """Soma dos percentuais dos marcos de um contrato, para a conferência dos 100%."""
    return sum(pcts)


def milestone_pct_complete(pcts: Sequence[int]) -> bool:
    """A soma dos percentuais fecha os 100% exigidos do contrato?"""
    return milestone_pct_total(pcts) == MILESTONE_PCT_TOTAL


def milestone_is_late(expected_on: date, situation: str, reference_date: date) -> bool:
    """Marco pendente com a data prevista vencida: o atraso que o protótipo alerta.

    Só um marco Previsto ou com Evidência enviada atrasa; um marco já aprovado, faturado ou
    pago ficou para trás da data prevista sem que o atraso importe.
    """
    return situation in MILESTONE_PENDING_SITUATIONS and expected_on < reference_date


def milestone_late_days(expected_on: date, reference_date: date) -> int:
    """Dias de atraso do marco: a data de referência menos a data prevista."""
    return (reference_date - expected_on).days


def claim_notification_deadline(event_date: date, notice_days: int) -> date:
    """Último dia do prazo de notificação: a data do evento mais os dias do contrato.

    Notificar no próprio último dia está dentro do prazo; o atraso começa no dia seguinte.
    """
    return event_date + timedelta(days=notice_days)


def claim_notification_late(notification_date: date, deadline: date) -> bool:
    """A notificação passou do prazo contratual? O último dia ainda não é atraso."""
    return notification_date > deadline


def extension_new_end_date(current_end: date, granted_days: int) -> date:
    """Término vigente prorrogado pela EOT: a data vigente mais os dias concedidos."""
    return current_end + timedelta(days=granted_days)


# ── Avaliação de desempenho da contratada (ISSUE-034) ────────────────────


EVALUATION_KIND_MONTHLY = "Mensal"
EVALUATION_KIND_FINAL = "Final"
EVALUATION_KINDS = (EVALUATION_KIND_MONTHLY, EVALUATION_KIND_FINAL)
EVALUATION_MAX_NOTE = 5
EVALUATION_SCORE_TOTAL = Decimal(100)
EVALUATION_HALF = Decimal("0.5")


@dataclass(frozen=True)
class EvaluationClass:
    """Uma classe da avaliação dos parâmetros: nome, nota mínima e descrição."""

    name: str
    minimum: int
    description: str = ""


def evaluation_weighted_score(notas: Mapping[str, int], pesos: Mapping[str, int]) -> int | None:
    """Nota ponderada de 0 a 100, meio para cima, ou ``None`` sem critério com nota.

    Soma as notas pelos pesos gravados na avaliação, divide pelo peso somado e pela escala de 1
    a 5, como o protótipo (o arredondamento do JavaScript é o meio para cima); o critério sem
    nota não conta nem o seu peso, e sem peso algum não há nota.
    """
    weighted = 0
    total = 0
    for criterion, weight in pesos.items():
        note = notas.get(criterion)
        if not note:
            continue
        weighted += note * weight
        total += weight
    if not total:
        return None
    score = Decimal(weighted) / total / EVALUATION_MAX_NOTE * EVALUATION_SCORE_TOTAL
    return math.floor(score + EVALUATION_HALF)


def evaluation_class(
    score: int | None, classes: Sequence[EvaluationClass]
) -> EvaluationClass | None:
    """Classe da nota: a de maior mínimo que ela alcança; no empate, a primeira da lista.

    No protótipo A começa em 85, B em 70, C em 50 e D em 0; a nota no próprio mínimo entra na
    classe (a comparação é ``>=``). Sem nota não há classe.
    """
    if score is None:
        return None
    chosen: EvaluationClass | None = None
    for candidate in classes:
        if score >= candidate.minimum and (chosen is None or candidate.minimum > chosen.minimum):
            chosen = candidate
    return chosen


def evaluation_requires_plan(notas: Mapping[str, int], limite: int) -> bool:
    """Alguma nota alcança o limite que exige plano de melhoria (nota 1 ou 2 nos parâmetros)."""
    return any(note and note <= limite for note in notas.values())


@dataclass(frozen=True)
class EvaluationFact:
    """Uma avaliação gravada: o período, as notas e os pesos congelados dos critérios."""

    period: date
    notes: Mapping[str, int]
    weights: Mapping[str, int]


def evaluation_trend_points(evaluations: Sequence[EvaluationFact]) -> tuple[dict[str, int], ...]:
    """Série do Gráfico de Áreas de Avaliação: um ponto por avaliação, em ordem de período.

    Cada ponto leva o ano, o mês e a nota ponderada; a avaliação sem nota ponderada fica de fora.
    """
    points: list[dict[str, int]] = []
    for evaluation in sorted(evaluations, key=lambda item: item.period):
        score = evaluation_weighted_score(evaluation.notes, evaluation.weights)
        if score is None:
            continue
        points.append(
            {"ano": evaluation.period.year, "mes": evaluation.period.month, "valor": score}
        )
    return tuple(points)
