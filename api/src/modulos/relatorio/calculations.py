"""Pure calculations for the Management reporting module.

Análise do período (ISSUE-081, D6): a detecção dos desvios negativos de cada módulo (02, 03 e
04) a partir dos números que as fachadas donas devolvem, os textos numéricos de cada desvio
(o mesmo formato do protótipo, reutilizável pela 083), o resumo de indicadores do período e o
mês de competência do custo. Nada aqui lê o banco nem o relógio: as figuras chegam prontas e
a data de referência vem como argumento. The period labels are the report's own, read from
the Planning calculations (the owner of the format), never reimplemented here.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from src.core import calendario
from src.core.money import format_brl
from src.modulos.planejamento import calculations as planning_calculations
from src.modulos.relatorio import validation

ZERO = Decimal(0)

ONE_PLACE = Decimal("0.1")

TWO_PLACES = Decimal("0.01")

MONTH_NAMES = planning_calculations.MONTH_NAMES

MONTH_ABBREVIATION_LENGTH = 3

PERCENT_KINDS = frozenset({"aderencia", "trabalhando", "utilizacao"})


# ── Formatadores ───────────────────────────────────────────────────────────


def _plain(value: Decimal | int, places: int) -> str:
    """O número com as casas pedidas e vírgula decimal: ``61,8``."""
    quantized = Decimal(value).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    return f"{quantized:.{places}f}".replace(".", ",")


def _signed(value: Decimal | int, places: int) -> str:
    """O número com sinal de mais quando positivo: ``+1,2`` ou ``-3,9``."""
    prefix = "+" if Decimal(value) > ZERO else ""
    return prefix + _plain(value, places)


def _pct(value: Decimal | None, places: int = 1) -> str:
    """O percentual com uma casa (o padrão do protótipo): ``61,8%``; nulo vira ``·``."""
    return "·" if value is None else f"{_plain(value, places)}%"


def _indice(value: Decimal | None) -> str:
    """O índice com duas casas fixas: ``0,94``; nulo vira ``·``."""
    return "·" if value is None else _plain(value, 2)


def _pp(value: Decimal | None, *, sign: bool = False) -> str:
    """O desvio em p.p. com uma casa e sinal opcional: ``-3,9 p.p.`` ou ``+1,2 p.p.``."""
    if value is None:
        return "·"
    return f"{_signed(value, 1) if sign else _plain(value, 1)} p.p."


def _mes_curto(value: date | None) -> str:
    """O mês em ``mmm/aa`` (o ``mesCurto`` do protótipo): ``set/26``; nulo vira ``·``."""
    if value is None:
        return "·"
    month = MONTH_NAMES[value.month - 1][:MONTH_ABBREVIATION_LENGTH].lower()
    return f"{month}/{value.year % 100:02d}"


def _dinheiro(cents: int | None, *, sign: bool = False) -> str:
    """O dinheiro em reais com sinal de mais opcional: ``-R$ 1.234,56`` ou ``+R$ 10,00``."""
    if cents is None:
        return "·"
    prefix = "+" if sign and cents > 0 else ""
    return prefix + format_brl(cents)


def _dias(value: int | None) -> str:
    """Os dias com sinal: ``-5 d`` ou ``+3 d``; nulo vira ``·``."""
    return "·" if value is None else f"{_signed(value, 0)} d"


def format_percent(value: Decimal | None) -> str:
    """O formatador de percentual que o template usa (``61,8%``)."""
    return _pct(value)


def format_index(value: Decimal | None) -> str:
    """O formatador de índice que o template usa (``0,94``)."""
    return _indice(value)


def format_pp(value: Decimal | None) -> str:
    """O formatador de p.p. que o template usa (``-3,9 p.p.``)."""
    return _pp(value)


def format_month(value: date | None) -> str:
    """O formatador de mês que o template usa (``set/26``)."""
    return _mes_curto(value)


def format_money(value: int | None) -> str:
    """O formatador de dinheiro que o template usa (``R$ 1.234,56``)."""
    return _dinheiro(value)


def format_number(value: int | None) -> str:
    """O formatador de contagem que o template usa; nulo vira ``·``."""
    return "·" if value is None else f"{int(value)}"


# ── Figuras de entrada ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class AreaFigure:
    """Uma área da EAP na leitura do desvio: o nome e o desvio em p.p."""

    name: str
    deviation_pp: Decimal


@dataclass(frozen=True)
class ProductivityItem:
    """Um indicador de produtividade fora da meta: a chave, o valor e a meta vigente."""

    key: str
    value: Decimal
    target: Decimal


@dataclass(frozen=True)
class ProductivityFigure:
    """Os indicadores de produtividade no corte, com as metas vigentes e a janela de semanas."""

    spi: Decimal | None
    pf_window: Decimal | None
    adherence: Decimal | None
    working_pct: Decimal | None
    utilization: Decimal | None
    meta_pf: Decimal
    meta_adherence: Decimal
    meta_working: Decimal
    meta_utilization: Decimal
    weeks: int


@dataclass(frozen=True)
class PlanningFigures:
    """Os números do planejamento no corte: posição, posição anterior, términos, áreas e produtividade."""

    predicted: Decimal
    actual: Decimal
    deviation_pp: Decimal
    spi: Decimal | None
    previous_predicted: Decimal
    previous_actual: Decimal
    previous_spi: Decimal | None
    trend_finish: date | None
    baseline_finish: date | None
    areas: tuple[AreaFigure, ...]
    productivity: ProductivityFigure | None


@dataclass(frozen=True)
class CostPackageFigure:
    """Um pacote de nível 1 com sobrecusto projetado: o código, a descrição e o desvio."""

    code: str
    description: str
    deviation_cents: int
    deviation_percent: Decimal | None


@dataclass(frozen=True)
class CostFigures:
    """Os números do financeiro no mês de competência: valor agregado, projeção e pacotes."""

    closed: bool
    cpi: Decimal | None = None
    spi: Decimal | None = None
    cv_cents: int = 0
    sv_cents: int = 0
    ev_cents: int = 0
    ac_cents: int = 0
    previous_cpi: Decimal | None = None
    budget_cents: int = 0
    projection_cents: int | None = None
    vac_cents: int | None = None
    deviation_percent: Decimal | None = None
    contingency_pct: Decimal | None = None
    packages: tuple[CostPackageFigure, ...] = ()


@dataclass(frozen=True)
class CriticalOrderFigure:
    """Um pedido crítico: o número, a descrição e a folga em dias (negativa)."""

    number: str
    description: str
    slack_days: int | None


@dataclass(frozen=True)
class LateMilestoneFigure:
    """Um marco de pedido realizado com atraso dentro do período: o pedido, o marco e os dias."""

    code: str
    milestone: str
    days: int


@dataclass(frozen=True)
class ProcurementFigures:
    """Os números de suprimentos no corte: aderência, saving, OTD, críticos e marcos atrasados."""

    adherence_pct: Decimal | None
    adjudicated: int
    planned: int
    saving_pct: Decimal | None
    otd_pct: Decimal | None
    on_time: int
    deliveries: int
    warning: int
    critical_orders: tuple[CriticalOrderFigure, ...]
    late_milestones: tuple[LateMilestoneFigure, ...]


@dataclass(frozen=True)
class SummaryItem:
    """Um indicador do resumo do período: o rótulo, o valor cru e o tipo de formatação."""

    label: str
    value: Any
    kind: str


@dataclass(frozen=True)
class Deviation:
    """Um desvio negativo detectado: a chave, o indicador e os dados do texto numérico."""

    key: str
    indicator: str
    data: Mapping[str, Any]


# ── Detecção dos desvios ───────────────────────────────────────────────────


def planning_deviations(figures: PlanningFigures) -> tuple[Deviation, ...]:
    """Os desvios negativos do planejamento no corte, na ordem do protótipo."""
    deviations: list[Deviation] = []
    if figures.deviation_pp < ZERO:
        deviations.append(
            Deviation(
                key="avanco",
                indicator="Avanço físico acumulado",
                data={
                    "real": figures.actual,
                    "previsto": figures.predicted,
                    "desvio": figures.deviation_pp,
                    "spi": figures.spi,
                },
            )
        )
    real_period = figures.actual - figures.previous_actual
    predicted_period = figures.predicted - figures.previous_predicted
    if real_period < predicted_period:
        deviations.append(
            Deviation(
                key="avanco_periodo",
                indicator="Avanço no período",
                data={"real": real_period, "previsto": predicted_period},
            )
        )
    if (
        figures.trend_finish is not None
        and figures.baseline_finish is not None
        and figures.trend_finish > figures.baseline_finish
    ):
        deviations.append(
            Deviation(
                key="termino",
                indicator="Término pela tendência",
                data={"tendencia": figures.trend_finish, "baseline": figures.baseline_finish},
            )
        )
    areas = tuple(area for area in figures.areas if area.deviation_pp < ZERO)
    if areas:
        deviations.append(
            Deviation(
                key="areas",
                indicator="Avanço por área",
                data={"itens": areas},
            )
        )
    if figures.productivity is not None:
        items = _productivity_items(figures.productivity)
        if items:
            deviations.append(
                Deviation(
                    key="produtividade",
                    indicator="Produtividade",
                    data={"itens": items, "semanas": figures.productivity.weeks},
                )
            )
    return tuple(deviations)


def _productivity_items(figures: ProductivityFigure | None) -> tuple[ProductivityItem, ...]:
    """Os indicadores de produtividade fora da meta, na ordem do protótipo."""
    if figures is None:
        return ()
    items: list[ProductivityItem] = []
    if figures.spi is not None and figures.spi < Decimal(1):
        items.append(ProductivityItem(key="spi", value=figures.spi, target=Decimal(1)))
    if figures.pf_window is not None and figures.pf_window > figures.meta_pf:
        items.append(ProductivityItem(key="pf", value=figures.pf_window, target=figures.meta_pf))
    if figures.adherence is not None and figures.adherence < figures.meta_adherence:
        items.append(
            ProductivityItem(
                key="aderencia", value=figures.adherence, target=figures.meta_adherence
            )
        )
    if figures.working_pct is not None and figures.working_pct < figures.meta_working:
        items.append(
            ProductivityItem(
                key="trabalhando", value=figures.working_pct, target=figures.meta_working
            )
        )
    if figures.utilization is not None and figures.utilization < figures.meta_utilization:
        items.append(
            ProductivityItem(
                key="utilizacao", value=figures.utilization, target=figures.meta_utilization
            )
        )
    return tuple(items)


def cost_deviations(figures: CostFigures) -> tuple[Deviation, ...]:
    """Os desvios negativos do financeiro no mês de competência; sem fechamento, nenhum."""
    if not figures.closed:
        return ()
    deviations: list[Deviation] = []
    if figures.cpi is not None and figures.cpi < Decimal(1):
        deviations.append(
            Deviation(
                key="cpi",
                indicator="CPI (desempenho de custo)",
                data={
                    "cpi": figures.cpi,
                    "cv": figures.cv_cents,
                    "ev": figures.ev_cents,
                    "ac": figures.ac_cents,
                },
            )
        )
    if figures.spi is not None and figures.spi < Decimal(1):
        deviations.append(
            Deviation(
                key="spi_custo",
                indicator="SPI de custo (valor agregado)",
                data={"spi": figures.spi, "sv": figures.sv_cents},
            )
        )
    if figures.vac_cents is not None and figures.vac_cents < 0:
        deviations.append(
            Deviation(
                key="vac",
                indicator="Projeção no término",
                data={
                    "projecao": figures.projection_cents,
                    "bac": figures.budget_cents,
                    "vac": figures.vac_cents,
                    "pct": figures.deviation_percent,
                },
            )
        )
    packages = tuple(package for package in figures.packages if package.deviation_cents > 0)
    if packages:
        deviations.append(
            Deviation(
                key="pacotes",
                indicator="Pacotes com sobrecusto projetado",
                data={"itens": packages},
            )
        )
    return tuple(deviations)


def procurement_deviations(figures: ProcurementFigures) -> tuple[Deviation, ...]:
    """Os desvios negativos de suprimentos no corte, na ordem do protótipo."""
    deviations: list[Deviation] = []
    if figures.adherence_pct is not None and figures.adherence_pct < Decimal(100):
        deviations.append(
            Deviation(
                key="aderencia",
                indicator="Aderência ao plano de compras",
                data={
                    "adjudicados": figures.adjudicated,
                    "planejados": figures.planned,
                    "pct": figures.adherence_pct,
                },
            )
        )
    if figures.otd_pct is not None and figures.otd_pct < Decimal(100):
        deviations.append(
            Deviation(
                key="otd",
                indicator="Entregas no prazo (OTD)",
                data={
                    "noPrazo": figures.on_time,
                    "total": figures.deliveries,
                    "pct": figures.otd_pct,
                },
            )
        )
    if figures.critical_orders:
        deviations.append(
            Deviation(
                key="criticos",
                indicator="Pedidos críticos",
                data={"itens": figures.critical_orders},
            )
        )
    if figures.late_milestones:
        deviations.append(
            Deviation(
                key="marcos_atrasados",
                indicator="Marcos realizados com atraso no período",
                data={"itens": figures.late_milestones},
            )
        )
    return tuple(deviations)


# ── Textos dos desvios ─────────────────────────────────────────────────────

PRODUCTIVITY_LABELS: Mapping[str, str] = {
    "spi": "SPI de quantidades",
    "pf": "Fator de produtividade",
    "aderencia": "Aderência semanal",
    "trabalhando": "Pessoas trabalhando",
    "utilizacao": "Utilização da jornada",
}


def _package_text(item: CostPackageFigure) -> str:
    """Um pacote no texto do desvio: ``COD descrição +R$ ... (12,3%)``, sem o percentual nulo."""
    text = f"{item.code} {item.description} {_dinheiro(item.deviation_cents, sign=True)}"
    if item.deviation_percent is None:
        return text
    return f"{text} ({_plain(item.deviation_percent, 1)}%)"


def _description_avanco(data: Mapping[str, Any]) -> str:
    return (
        f"Real {_pct(data['real'])} x previsto {_pct(data['previsto'])} "
        f"({_pp(data['desvio'], sign=True)}; SPI {_indice(data['spi'])})"
    )


def _description_avanco_periodo(data: Mapping[str, Any]) -> str:
    real, predicted = Decimal(data["real"]), Decimal(data["previsto"])
    return (
        f"No período: real {_pp(real, sign=True)} x previsto {_pp(predicted, sign=True)} "
        f"({_pp(real - predicted, sign=True)})"
    )


def _description_termino(data: Mapping[str, Any]) -> str:
    return (
        f"Tendência {_mes_curto(data['tendencia'])} x linha de base {_mes_curto(data['baseline'])}"
    )


def _description_areas(data: Mapping[str, Any]) -> str:
    return "; ".join(f"{item.name} {_pp(item.deviation_pp, sign=True)}" for item in data["itens"])


def _description_produtividade(data: Mapping[str, Any]) -> str:
    parts = []
    for item in data["itens"]:
        label = PRODUCTIVITY_LABELS.get(item.key, item.key)
        if item.key in PERCENT_KINDS:
            value, target = _pct(item.value), _pct(item.target, 0)
        else:
            value, target = _indice(item.value), _indice(item.target)
        prefix = "≤ " if item.key == "pf" else ""
        parts.append(f"{label} {value} (meta {prefix}{target})")
    return "; ".join(parts) + f" · últimas {data['semanas']} semanas"


def _description_cpi(data: Mapping[str, Any]) -> str:
    return (
        f"CPI {_indice(data['cpi'])} · CV {_dinheiro(data['cv'])} "
        f"(EV {_dinheiro(data['ev'])} x AC {_dinheiro(data['ac'])})"
    )


def _description_spi_custo(data: Mapping[str, Any]) -> str:
    return f"SPI de custo {_indice(data['spi'])} · SV {_dinheiro(data['sv'])}"


def _description_vac(data: Mapping[str, Any]) -> str:
    suffix = f"; {_signed(data['pct'], 1)}%" if data["pct"] is not None else ""
    return (
        f"Projeção {_dinheiro(data['projecao'])} x orçamento {_dinheiro(data['bac'])} "
        f"(VAC {_dinheiro(data['vac'])}{suffix})"
    )


def _description_pacotes(data: Mapping[str, Any]) -> str:
    return "; ".join(_package_text(item) for item in data["itens"])


def _description_aderencia(data: Mapping[str, Any]) -> str:
    return (
        f"{int(data['adjudicados'])} de {int(data['planejados'])} pacotes adjudicados "
        f"até o corte ({_pct(data['pct'])})"
    )


def _description_otd(data: Mapping[str, Any]) -> str:
    return f"{int(data['noPrazo'])} de {int(data['total'])} entregas no prazo ({_pct(data['pct'])})"


def _description_criticos(data: Mapping[str, Any]) -> str:
    return "; ".join(
        f"{item.number} {item.description} (folga {_dias(item.slack_days)})"
        for item in data["itens"]
    )


def _description_marcos_atrasados(data: Mapping[str, Any]) -> str:
    return "; ".join(f"{item.code} {item.milestone} ({_dias(item.days)})" for item in data["itens"])


_DESCRIPTIONS: Mapping[str, Callable[[Mapping[str, Any]], str]] = {
    "avanco": _description_avanco,
    "avanco_periodo": _description_avanco_periodo,
    "termino": _description_termino,
    "areas": _description_areas,
    "produtividade": _description_produtividade,
    "cpi": _description_cpi,
    "spi_custo": _description_spi_custo,
    "vac": _description_vac,
    "pacotes": _description_pacotes,
    "aderencia": _description_aderencia,
    "otd": _description_otd,
    "criticos": _description_criticos,
    "marcos_atrasados": _description_marcos_atrasados,
}


def deviation_description(deviation: Deviation) -> str:
    """A descrição numérica do desvio, no formato do protótipo, pela chave (vazio se não houver)."""
    builder = _DESCRIPTIONS.get(deviation.key)
    return "" if builder is None else builder(deviation.data)


# ── Resumo do passo 2 ──────────────────────────────────────────────────────


def analysis_summary(
    module: str,
    figures: PlanningFigures | CostFigures | ProcurementFigures,
) -> tuple[SummaryItem, ...]:
    """Os indicadores do período que o resumo do formulário mostra, por módulo."""
    if module == "planejamento" and isinstance(figures, PlanningFigures):
        return _planning_summary(figures)
    if module == "financeiro" and isinstance(figures, CostFigures):
        return _cost_summary(figures)
    if module == "suprimentos" and isinstance(figures, ProcurementFigures):
        return _procurement_summary(figures)
    return ()


def _planning_summary(figures: PlanningFigures) -> tuple[SummaryItem, ...]:
    items = [
        SummaryItem("Avanço previsto", figures.predicted, "pct"),
        SummaryItem("Avanço real", figures.actual, "pct"),
        SummaryItem("SPI físico", figures.spi, "indice"),
        SummaryItem("SPI físico do período anterior", figures.previous_spi, "indice"),
        SummaryItem("Avanço no período (real)", figures.actual - figures.previous_actual, "pp"),
        SummaryItem(
            "Avanço no período (previsto)", figures.predicted - figures.previous_predicted, "pp"
        ),
        SummaryItem("Término pela tendência", figures.trend_finish, "mes"),
        SummaryItem("Término da linha de base", figures.baseline_finish, "mes"),
    ]
    if figures.productivity is not None:
        items.extend(
            [
                SummaryItem("SPI de quantidades", figures.productivity.spi, "indice"),
                SummaryItem("Fator de produtividade", figures.productivity.pf_window, "indice"),
                SummaryItem("Aderência semanal", figures.productivity.adherence, "pct"),
            ]
        )
    return tuple(items)


def _cost_summary(figures: CostFigures) -> tuple[SummaryItem, ...]:
    if not figures.closed:
        return ()
    return (
        SummaryItem("Orçamento vigente (BAC)", figures.budget_cents, "moeda"),
        SummaryItem("Realizado acumulado", figures.ac_cents, "moeda"),
        SummaryItem("Valor agregado (EV)", figures.ev_cents, "moeda"),
        SummaryItem("CPI", figures.cpi, "indice"),
        SummaryItem("CPI do mês anterior", figures.previous_cpi, "indice"),
        SummaryItem("SPI de custo", figures.spi, "indice"),
        SummaryItem("Projeção no término", figures.projection_cents, "moeda"),
        SummaryItem("Contingência consumida", figures.contingency_pct, "pct"),
    )


def _procurement_summary(figures: ProcurementFigures) -> tuple[SummaryItem, ...]:
    return (
        SummaryItem("Aderência ao plano de compras", figures.adherence_pct, "pct"),
        SummaryItem("Saving", figures.saving_pct, "pct"),
        SummaryItem("Entregas no prazo (OTD)", figures.otd_pct, "pct"),
        SummaryItem("Pedidos críticos", len(figures.critical_orders), "num"),
        SummaryItem("Pedidos em atenção", figures.warning, "num"),
        SummaryItem("Pacotes adjudicados", figures.adjudicated, "num"),
    )


# ── Períodos e termos ──────────────────────────────────────────────────────


def competence_month(kind: str, period: str) -> date:
    """O mês de competência do custo: no Mensal o próprio mês; no Semanal o último fechado.

    No Semanal é o mês cujo último dia não passa do fim do período; sem esse, o mês anterior
    (o ``mesFinanceiroRg`` do protótipo). Devolve o primeiro dia do mês de competência.
    """
    bounds = calendario.period_bounds(kind, period)
    if bounds is None:
        return date(1970, 1, 1)
    if kind == calendario.MONTHLY:
        return bounds[0]
    end = bounds[1]
    label = f"{end.year}-{end.month:02d}"
    last = calendario.month_end(label)
    if last is not None and last <= end:
        return date(end.year, end.month, 1)
    previous = calendario.add_periods(calendario.MONTHLY, label, -1)
    return date.fromisoformat(f"{previous}-01") if previous is not None else end.replace(day=1)


def finish_month(months: Sequence[date], values: Sequence[Decimal | None]) -> date | None:
    """O primeiro mês em que a série chega a 100%; sem chegar, ``None`` (não há término)."""
    return next(
        (
            month
            for month, value in zip(months, values, strict=True)
            if value is not None and value >= Decimal(100)
        ),
        None,
    )


def trend_finish(months: Sequence[date], values: Sequence[Decimal | None]) -> date | None:
    """O término pela tendência: o primeiro mês que chega a 100; sem chegar, o último com valor.

    A tendência do GestNow segue o ritmo da linha de base a partir do real do corte e, num
    projeto atrasado, fica abaixo de 100 no fim do calendário congelado: o término cai além
    dele e o último mês conhecido é a resposta (o término do protótipo, que chegava a 100 no
    próprio calendário).
    """
    finished = finish_month(months, values)
    if finished is not None:
        return finished
    known = [month for month, value in zip(months, values, strict=True) if value is not None]
    return known[-1] if known else None


def period_name(kind: str, period: str) -> str:
    """O período como uma pessoa o lê, no padrão do relato: ``Semana 38 · 14/09 a 20/09/2026``."""
    return planning_calculations.period_name(kind, period)


def short_month(kind: str, period: str) -> str:
    """O rótulo curto do período, no padrão do relato: ``S38`` ou ``ago/26``."""
    return planning_calculations.short_period_name(kind, period)


def period_options(
    kind: str,
    *,
    project_start: date | None,
    reference_date: date,
    taken: Iterable[str],
) -> list[planning_calculations.PeriodOption]:
    """Os períodos do início do projeto ao corrente, o mais recente primeiro, com a situação."""
    return planning_calculations.period_options(
        kind, project_start=project_start, reference_date=reference_date, taken=taken
    )


def previous_period(kind: str, period: str) -> str | None:
    """O período imediatamente anterior, ou ``None`` quando o rótulo não é válido."""
    return calendario.add_periods(kind, period, -1)


def period_error(
    kind: str,
    period: str,
    *,
    project_start: date | None,
    reference_date: date,
) -> str | None:
    """A mensagem do período da análise: inválido, anterior ao início do projeto ou futuro."""
    if not calendario.valid_period(kind, period):
        return validation.CHOOSE_MESSAGE
    return planning_calculations.report_period_error(
        kind, period, project_start=project_start, reference_date=reference_date
    )
