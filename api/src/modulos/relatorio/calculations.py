"""Pure calculations for the Management reporting module.

Análise do período (ISSUE-081/ISSUE-082, D6): a detecção dos desvios negativos de cada módulo
(02, 03, 04 e 06 — em 05 e 07 só o texto é exigido) a partir dos números que as fachadas donas
devolvem, os textos numéricos de cada desvio (o mesmo formato do protótipo, reutilizável pela
083), o resumo de indicadores do período e o mês de competência do custo. Nada aqui lê o banco
nem o relógio: as figuras chegam prontas e a data de referência vem como argumento. The period
labels are the report's own, read from the Planning calculations (the owner of the format),
never reimplemented here.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
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


def _round_one(value: Decimal) -> Decimal:
    """O valor com uma casa, como o dono arredonda as séries da curva."""
    return Decimal(value).quantize(ONE_PLACE, rounding=ROUND_HALF_UP)


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


def format_percent_signed(value: Decimal | None) -> str:
    """O percentual com sinal de mais quando positivo (``+5,5%``); nulo vira ``·``."""
    return "·" if value is None else f"{_signed(value, 1)}%"


def format_month(value: date | None) -> str:
    """O formatador de mês que o template usa (``set/26``)."""
    return _mes_curto(value)


def format_money(value: int | None) -> str:
    """O formatador de dinheiro que o template usa (``R$ 1.234,56``)."""
    return _dinheiro(value)


def format_thousands(value: int | None) -> str:
    """O dinheiro em R$ mil que as tabelas do relatório usam (``44.600``); nulo vira ``·``."""
    if value is None:
        return "·"
    mil = (Decimal(value) / Decimal(100000)).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return f"{mil:,}".replace(",", ".")


def format_money_thousands(value: int | None) -> str:
    """O dinheiro em R$ mil com a unidade (``R$ 44.600 mil``); nulo vira ``·``.

    É o formato dos rodapés dos KPIs das folhas Financeiro e Suprimentos: os valores são
    grandes demais para o reais por extenso e o ``R$`` fica explícito no rótulo.
    """
    if value is None:
        return "·"
    return f"R$ {format_thousands(value)} mil"


def format_number(value: int | None) -> str:
    """O formatador de contagem que o template usa; nulo vira ``·``."""
    return "·" if value is None else f"{int(value)}"


def format_number0(value: Decimal | None) -> str:
    """O formatador de quantidade sem casas que a folha usa (``481``); nulo vira ``·``."""
    return "·" if value is None else _plain(value, 0)


def format_number1(value: Decimal | None) -> str:
    """O formatador de quantidade com uma casa que a folha usa (``11,5``); nulo vira ``·``."""
    return "·" if value is None else _plain(value, 1)


def format_date(value: date | datetime | None) -> str:
    """A data que o template mostra (``21/09/2026``); um instante passa pelo fuso do produto."""
    if value is None:
        return "·"
    if isinstance(value, datetime):
        value = calendario.in_product_timezone(value).date()
    return f"{value:%d/%m/%Y}"


def format_number2(value: Decimal | None) -> str:
    """O formatador das taxas do HSE que o template usa: duas casas fixas (``6,80``)."""
    return "·" if value is None else _plain(value, 2)


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
    """Os indicadores de produtividade no corte, com as metas vigentes e a janela de semanas.

    ``stoppage_hours`` e ``stoppage_share`` são as HH paralisadas da janela e a sua fatia das
    HH disponíveis; ``alert_companies`` são as empresas com indicador em alerta e ``bands`` as
    faixas (success, warning ou danger) de cada indicador — a folha 1 do relatório as usa.
    """

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
    stoppage_hours: Decimal | None = None
    stoppage_share: Decimal | None = None
    alert_companies: tuple[str, ...] = ()
    bands: planning_calculations.PerformanceBands | None = None


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

    @property
    def predicted_period(self) -> Decimal:
        """O previsto do período: o avanço esperado entre a posição anterior e o corte."""
        return self.predicted - self.previous_predicted

    @property
    def actual_period(self) -> Decimal:
        """O real do período: o avanço medido entre a posição anterior e o corte."""
        return self.actual - self.previous_actual


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
class OverdueItem:
    """Um item vencido no corte: o código e os dias de atraso (positivos)."""

    code: str
    days: int


@dataclass(frozen=True)
class RiskFigures:
    """Os números de riscos no corte: o resumo do painel e as contagens do período."""

    active: int
    top_band: str
    top_total: int
    exposure_cents: int
    overdue_reviews: int
    identified: int
    closed: int
    reduction_avg_pct: int | None


@dataclass(frozen=True)
class QualityFigures:
    """Os números da qualidade no corte: RNC, inspeções, auditorias, custo e vencidos."""

    open_in_period: int
    closed_in_period: int
    open_at_cut: int
    approval_pct: Decimal | None
    approval_meta: Decimal | None
    approval_rejected: int
    approval_total: int
    conformity_pct: Decimal | None
    conformity_meta: Decimal | None
    non_quality_cost_cents: int
    overdue: tuple[OverdueItem, ...]
    late_audits: tuple[OverdueItem, ...]


@dataclass(frozen=True)
class HseFigures:
    """Os números do HSE no corte: as taxas do mês e da carteira e o período."""

    tf: Decimal | None
    trif: Decimal | None
    accumulated_trif: Decimal | None
    days_without_leave: int | None
    hipo: int
    hours: Decimal | None
    occurrences: int


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
    real_period = figures.actual_period
    predicted_period = figures.predicted_period
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


def quality_deviations(figures: QualityFigures) -> tuple[Deviation, ...]:
    """Os desvios negativos da qualidade no corte, na ordem do protótipo.

    A RNC vencida e a auditoria atrasada entram pelos itens vencidos na data de referência; a
    aprovação em inspeções e a conformidade em auditorias entram só quando o percentual existe e
    fica abaixo da meta vigente (no limite, não é desvio). Riscos e HSE não têm detecção: neles
    só o texto é exigido.
    """
    deviations: list[Deviation] = []
    if figures.overdue:
        deviations.append(
            Deviation(
                key="rnc_vencidas",
                indicator="RNC com prazo de tratamento vencido",
                data={"itens": figures.overdue},
            )
        )
    if (
        figures.approval_pct is not None
        and figures.approval_meta is not None
        and figures.approval_pct < figures.approval_meta
    ):
        deviations.append(
            Deviation(
                key="aprovacao_inspecao",
                indicator="Aprovação em inspeções",
                data={
                    "pct": figures.approval_pct,
                    "meta": figures.approval_meta,
                    "reprovadas": figures.approval_rejected,
                    "total": figures.approval_total,
                },
            )
        )
    if (
        figures.conformity_pct is not None
        and figures.conformity_meta is not None
        and figures.conformity_pct < figures.conformity_meta
    ):
        deviations.append(
            Deviation(
                key="conformidade_auditoria",
                indicator="Conformidade em auditorias",
                data={"pct": figures.conformity_pct, "meta": figures.conformity_meta},
            )
        )
    if figures.late_audits:
        deviations.append(
            Deviation(
                key="auditorias_atrasadas",
                indicator="Auditorias atrasadas",
                data={"itens": figures.late_audits},
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


def _description_rnc_vencidas(data: Mapping[str, Any]) -> str:
    return "; ".join(f"{item.code} ({_dias(item.days)})" for item in data["itens"])


def _description_aprovacao_inspecao(data: Mapping[str, Any]) -> str:
    rejected = int(data["reprovadas"])
    noun = "reprovada em" if rejected == 1 else "reprovadas em"
    return (
        f"{_pct(data['pct'])} (meta {_pct(data['meta'], 0)}) · "
        f"{rejected} {noun} {int(data['total'])}"
    )


def _description_conformidade_auditoria(data: Mapping[str, Any]) -> str:
    return f"{_pct(data['pct'])} (meta {_pct(data['meta'], 0)})"


def _description_auditorias_atrasadas(data: Mapping[str, Any]) -> str:
    return "; ".join(f"{item.code} ({_dias(item.days)})" for item in data["itens"])


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
    "rnc_vencidas": _description_rnc_vencidas,
    "aprovacao_inspecao": _description_aprovacao_inspecao,
    "conformidade_auditoria": _description_conformidade_auditoria,
    "auditorias_atrasadas": _description_auditorias_atrasadas,
}


def deviation_description(deviation: Deviation) -> str:
    """A descrição numérica do desvio, no formato do protótipo, pela chave (vazio se não houver)."""
    builder = _DESCRIPTIONS.get(deviation.key)
    return "" if builder is None else builder(deviation.data)


# ── Resumo do passo 2 ──────────────────────────────────────────────────────


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


def _risk_summary(figures: RiskFigures) -> tuple[SummaryItem, ...]:
    """O resumo de riscos do protótipo: a faixa mais alta vira um rótulo plural (``Críticos``)."""
    return (
        SummaryItem("Riscos ativos", figures.active, "num"),
        SummaryItem(f"{figures.top_band}s", figures.top_total, "num"),
        SummaryItem("Exposição (VME)", figures.exposure_cents, "moeda"),
        SummaryItem("Revisão vencida", figures.overdue_reviews, "num"),
        SummaryItem("Identificados no período", figures.identified, "num"),
        SummaryItem("Redução média", figures.reduction_avg_pct, "pct"),
    )


def _quality_summary(figures: QualityFigures) -> tuple[SummaryItem, ...]:
    return (
        SummaryItem("RNC abertas no período", figures.open_in_period, "num"),
        SummaryItem("RNC encerradas no período", figures.closed_in_period, "num"),
        SummaryItem("RNC em aberto no corte", figures.open_at_cut, "num"),
        SummaryItem("Aprovação em inspeções", figures.approval_pct, "pct"),
        SummaryItem("Conformidade em auditorias", figures.conformity_pct, "pct"),
        SummaryItem("Custo da não qualidade acumulado", figures.non_quality_cost_cents, "moeda"),
    )


def _hse_summary(figures: HseFigures) -> tuple[SummaryItem, ...]:
    """O resumo do HSE: as taxas com duas casas fixas (``num2``) e as contagens do mês."""
    return (
        SummaryItem("TF no mês", figures.tf, "num2"),
        SummaryItem("TRIF no mês", figures.trif, "num2"),
        SummaryItem("TRIF acumulada", figures.accumulated_trif, "num2"),
        SummaryItem("Dias sem afastamento", figures.days_without_leave, "num"),
        SummaryItem("HiPo no mês", figures.hipo, "num"),
        SummaryItem("HHT no mês", figures.hours, "num"),
        SummaryItem("Ocorrências no período", figures.occurrences, "num"),
    )


_SUMMARY_BUILDERS: Mapping[tuple[str, type], Callable[[Any], tuple[SummaryItem, ...]]] = {
    ("planejamento", PlanningFigures): _planning_summary,
    ("financeiro", CostFigures): _cost_summary,
    ("suprimentos", ProcurementFigures): _procurement_summary,
    ("riscos", RiskFigures): _risk_summary,
    ("qualidade", QualityFigures): _quality_summary,
    ("hse", HseFigures): _hse_summary,
}


def analysis_summary(
    module: str,
    figures: PlanningFigures
    | CostFigures
    | ProcurementFigures
    | RiskFigures
    | QualityFigures
    | HseFigures,
) -> tuple[SummaryItem, ...]:
    """Os indicadores do período que o resumo do formulário mostra, por módulo."""
    builder = _SUMMARY_BUILDERS.get((module, type(figures)))
    return () if builder is None else builder(figures)


# ── Motor de corte do relatório gerencial (ISSUE-083) ──────────────────────

# Quantas barras o avanço por período mostra: 8 semanas ou 6 meses até o corte.
BAR_PERIODS: Mapping[str, int] = {calendario.WEEKLY: 8, calendario.MONTHLY: 6}


def report_period_cutoff(kind: str, period: str, reference_date: date) -> date | None:
    """O corte do relatório: o fim do período limitado à data de referência.

    É o corte que todas as folhas usam — o período em andamento vale até a referência.
    """
    return calendario.cut_date(kind, period, reference_date)


def is_partial_period(kind: str, period: str, reference_date: date) -> bool:
    """Se o período ainda está em andamento na data de referência (sai marcado parcial)."""
    return calendario.is_partial(kind, period, reference_date)


def report_horizon(kind: str, period: str) -> tuple[date, date] | None:
    """O horizonte dos previstos de suprimentos: do dia seguinte ao fim do período em diante.

    No Semanal são as 4 semanas seguintes ao fim do período (28 dias, até o domingo da quarta
    semana); no Mensal é o mês seguinte inteiro, como o lookahead do protótipo. Rótulo inválido
    não tem horizonte.
    """
    bounds = calendario.period_bounds(kind, period)
    if bounds is None:
        return None
    end = bounds[1]
    if kind == calendario.WEEKLY:
        return calendario.add_days(end, 1), calendario.add_days(end, 28)
    following = calendario.add_periods(calendario.MONTHLY, period, 1)
    next_bounds = calendario.period_bounds(calendario.MONTHLY, following) if following else None
    return calendario.add_days(end, 1), next_bounds[1] if next_bounds else end


@dataclass(frozen=True)
class PeriodBar:
    """Uma barra do avanço por período: o período, o rótulo curto e o incremento em p.p."""

    period: str
    label: str
    predicted: Decimal | None
    actual: Decimal | None


def bar_periods(
    kind: str, period: str, *, reference_date: date, project_start: date | None
) -> tuple[str, ...]:
    """Os períodos das barras do avanço: as últimas 8 semanas ou 6 meses até o corte.

    Só entram períodos do projeto — os anteriores ao início ficam de fora —, em ordem de
    calendário. Sem corte válido (rótulo de período inválido), não há barras.
    """
    size = BAR_PERIODS.get(kind)
    if size is None:
        return ()
    cut = report_period_cutoff(kind, period, reference_date)
    if cut is None:
        return ()
    last = calendario.period_of(kind, cut)
    first = calendario.period_of(kind, project_start) if project_start is not None else None
    periods: list[str] = []
    label: str | None = last
    while label is not None and len(periods) < size and (first is None or label >= first):
        periods.append(label)
        label = calendario.add_periods(kind, label, -1)
    return tuple(reversed(periods))


def period_bars(
    kind: str,
    periods: Sequence[str],
    cumulative: Sequence[tuple[str, Decimal | None, Decimal | None]],
) -> tuple[PeriodBar, ...]:
    """As barras do avanço por período: o incremento entre um ponto acumulado e o anterior.

    ``cumulative`` são os pontos do dono — o rótulo do período e o previsto e o real
    acumulados, em ordem de calendário —, e a barra é a diferença entre o ponto do período e
    o do anterior, como o protótipo lia a série. O real da barra só existe quando os dois
    pontos têm real; o ponto anterior que não veio vale zero (o primeiro período do projeto).
    """
    points = {label: (predicted, actual) for label, predicted, actual in cumulative}
    bars: list[PeriodBar] = []
    for label in periods:
        predicted, actual = points.get(label, (None, None))
        earlier = calendario.add_periods(kind, label, -1)
        previous = points.get(earlier) if earlier is not None else None
        previous_predicted = (
            previous[0] if previous is not None and previous[0] is not None else ZERO
        )
        previous_actual = previous[1] if previous is not None and previous[1] is not None else ZERO
        bars.append(
            PeriodBar(
                period=label,
                label=planning_calculations.short_period_name(kind, label),
                predicted=(
                    None if predicted is None else _round_one(predicted - previous_predicted)
                ),
                actual=None if actual is None else _round_one(actual - previous_actual),
            )
        )
    return tuple(bars)


@dataclass(frozen=True)
class ChartReading:
    """A leitura da curva do dono num dia: o previsto e o real acumulados e os índices."""

    predicted: Decimal
    actual: Decimal | None
    deviation_pp: Decimal | None
    spi: Decimal | None


def chart_reading(periods: Sequence[Mapping[str, Any]], *, day: date) -> ChartReading:
    """A posição acumulada de um dia na leitura semanal do dono (o gráfico da Curva S).

    As semanas do gráfico trazem o previsto interpolado dentro do mês congelado e o real
    medido até o fim da semana; a semana do dia é a que o contém e fora do intervalo valem
    zero (antes do primeiro ponto) ou o último ponto. É a regra do relatório no semanal — no
    mensal vale o ponto do mês da série, como nas telas.
    """
    if not periods:
        return ChartReading(predicted=ZERO, actual=None, deviation_pp=None, spi=None)
    year, week, _ = day.isocalendar()
    chosen: Mapping[str, Any] | None = None
    for item in periods:
        if (int(item["ano"]), int(item["semana"])) <= (year, week):
            chosen = item
        else:
            break
    if chosen is None:
        return ChartReading(predicted=ZERO, actual=None, deviation_pp=None, spi=None)
    values = chosen.get("valores", {})
    base = values.get("linha_base")
    realized = values.get("realizado")
    predicted = ZERO if base is None else _round_one(Decimal(str(base)))
    actual = None if realized is None else _round_one(Decimal(str(realized)))
    deviation = None if actual is None else _round_one(actual - predicted)
    spi = (
        None
        if actual is None or predicted <= ZERO
        else (actual / predicted).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    )
    return ChartReading(predicted=predicted, actual=actual, deviation_pp=deviation, spi=spi)


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
