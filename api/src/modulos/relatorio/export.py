"""Exportação do relatório gerencial (ISSUE-086, D12): um documento, o Excel.

O documento leva o que as folhas mostram — os indicadores de todas as folhas presentes,
prefixados pela folha, e uma tabela por tabela exibida — mais as duas abas de fechamento do
protótipo: ``Análises do período``, com uma linha por folha que tem análise, e ``Desvios
negativos e comentários``, com uma linha por desvio detectado. O Excel sai daqui pela porta
canônica (``core.excel``): colunas tipadas, dinheiro em centavos, datas como datas e os tons
do Design System; a impressão do relatório é a do navegador, pela tela (ISSUE-083), e não
passa por este módulo.

As linhas já trazem o código do projeto onde a folha mistura projetos (a carteira, os eventos
de suprimentos e os pontos de atenção do Portfólio), então nenhuma tabela pede a coluna
``Projeto`` automática do Portfólio (``per_project=False``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any

from src.core import calendario, translations
from src.core.export_document import (
    Cell,
    Column,
    Document,
    Kpi,
    Paper,
    Row,
    Table,
    Tone,
    ValueKind,
    format_value,
    row,
)
from src.modulos.relatorio import calculations, service

TITLE_WEEKLY = "Relatório gerencial semanal"
TITLE_MONTHLY = "Relatório gerencial mensal"


def _label(text: str, idioma: str) -> str:
    """O texto de interface do relatório no idioma do request (D13)."""
    return translations.translate("relatorio", text, idioma)


def _label_parts(text: str, idioma: str) -> str:
    """Um rótulo composto por ``·``: cada parte passa pelo catálogo, a composição fica igual."""
    if idioma == translations.DEFAULT_LANGUAGE or not text:
        return text
    return " · ".join(_label(part, idioma) for part in text.split(" · "))


# O prefixo de cada folha nos rótulos dos indicadores do Resumo.
SHEET_CARTEIRA = "Carteira"
SHEET_PLANEJAMENTO = "Planejamento"
SHEET_FINANCEIRO = "Financeiro"
SHEET_SUPRIMENTOS = "Suprimentos"
SHEET_RISCOS = "Riscos"
SHEET_QUALIDADE = "Qualidade"
SHEET_HSE = "HSE"

# Os tons da tela (os sufixos do DS) como as cores da exportação: alerta e atenção
# compartilham o âmbar, o previsto lê como info e o real, como ok — o mesmo critério do
# painel de riscos, porque o papel não tem o azul da linha de base.
_TONES: Mapping[str, Tone] = {
    "ok": Tone.OK,
    "success": Tone.OK,
    "real": Tone.OK,
    "warn": Tone.WARN,
    "warning": Tone.WARN,
    "alerta": Tone.WARN,
    "atencao": Tone.WARN,
    "erro": Tone.ERROR,
    "danger": Tone.ERROR,
    "info": Tone.INFO,
    "previsto": Tone.INFO,
    "neutro": Tone.NEUTRAL,
}

# A cor de um índice no padrão da folha (o macro ``cor_indice``): 1,00 ou mais é ok;
# de 0,95 a 0,99 é atenção; abaixo, crítico.
_INDEX_ATTENTION = Decimal("0.95")

# A fonte dos critérios da ponderação como a folha a escreve.
_SOURCE_TEXT = {"orcamento": "orçamento vigente (EAC)", "nota": "nota de 1 a 5 por projeto"}

# O menos de verdade (U+2212) das folhas, escrito em escape para o linter não o ler ambíguo.
_MINUS = "\u2212"


def build_document(*, sheets: service.ReportSheets, today: date, idioma: str = "pt") -> Document:
    """O documento do relatório no escopo da requisição; a data de geração vem da rota."""
    kpis: list[Kpi] = []
    tables: list[Table] = []
    if sheets.carteira is not None:
        kpis.extend(_carteira_kpis(sheets.carteira))
        tables.extend(_carteira_tables(sheets.carteira))
    kpis.extend(_planning_kpis(sheets))
    if sheets.planning is not None:
        tables.extend(_planning_tables(sheets))
    if sheets.financeiro is not None:
        kpis.extend(_financeiro_kpis(sheets.financeiro))
        tables.extend(_financeiro_tables(sheets.financeiro))
    if sheets.suprimentos is not None:
        kpis.extend(_procurement_kpis(sheets.suprimentos))
        tables.extend(_procurement_tables(sheets.suprimentos))
    if sheets.riscos is not None:
        kpis.extend(_risk_kpis(sheets.riscos))
        tables.extend(_risk_tables(sheets.riscos))
    if sheets.qualidade is not None:
        kpis.extend(_quality_kpis(sheets.qualidade))
        tables.extend(_quality_tables(sheets.qualidade))
    if sheets.hse is not None:
        kpis.extend(_hse_kpis(sheets.hse))
    tables.extend(_analysis_tables(sheets))
    if idioma != translations.DEFAULT_LANGUAGE:
        kpis = [
            replace(
                kpi,
                label=_label_parts(kpi.label, idioma),
                reference=_label_parts(kpi.reference, idioma),
                status=_label(kpi.status, idioma) if kpi.status else kpi.status,
            )
            for kpi in kpis
        ]
    return Document(
        namespace="relatorio",
        idioma=idioma,
        title=_label(TITLE_WEEKLY if sheets.kind == calendario.WEEKLY else TITLE_MONTHLY, idioma),
        scope_label=sheets.scope_label,
        generated_on=today,
        portfolio=sheets.is_portfolio,
        context=_context(sheets, idioma),
        kpis=tuple(kpis),
        tables=tuple(tables),
        paper=Paper.A4,
    )


# ── Helpers ────────────────────────────────────────────────────────────────


def _context(sheets: service.ReportSheets, idioma: str = "pt") -> tuple[tuple[str, str], ...]:
    """As linhas do cabeçalho: o tipo, o período, o corte, a referência e quem emitiu."""
    suffix = _label(" (em andamento)", idioma) if sheets.in_progress else ""
    period = sheets.period_label + suffix
    return (
        (_label("Tipo", idioma), _label(sheets.kind, idioma)),
        (_label("Período", idioma), period),
        (_label("Corte", idioma), format_value(ValueKind.DATE, sheets.cut, idioma=idioma)),
        (
            _label("Referência", idioma),
            format_value(ValueKind.DATE, sheets.reference_date, idioma=idioma),
        ),
        (_label("Emitido por", idioma), sheets.emitted_by),
    )


def _tone(value: str | None) -> Tone | None:
    """O tom do DS a partir do sufixo da tela; texto sem situação fica sem cor."""
    return _TONES.get(value or "")


def _joined(*parts: str) -> str:
    """As partes de uma referência, unidas por ``·`` e com as vazias fora."""
    return " · ".join(part for part in parts if part)


def _index_band(value: Decimal | None) -> str:
    """A cor de um índice no padrão da folha (o macro ``cor_indice``)."""
    if value is None:
        return "info"
    if value >= 1:
        return "success"
    return "warning" if value >= _INDEX_ATTENTION else "danger"


def _meta_band(value: Decimal | None, meta: Decimal | int | None) -> str:
    """A cor de um percentual contra a meta: ok quando alcança; sem meta ou sem valor, atenção."""
    if value is None:
        return "info"
    return "success" if meta is not None and value >= meta else "warning"


def _below_one(value: Decimal | None) -> Tone | None:
    """O vermelho dos índices abaixo de 1 na carteira e no valor agregado."""
    if value is None or value >= 1:
        return None
    return Tone.ERROR


def _vac_text(cents: int | None) -> str:
    """O VAC como a folha o mostra: ``+R$ 96,5 mi x orçamento``, com o sinal do sobrecusto."""
    if cents is None:
        return "· x orçamento"
    sign = "+" if cents < 0 else _MINUS
    return f"{sign}{calculations.format_money_compact(abs(cents))} x orçamento"


def _limit_text(cents: int | None) -> str:
    """O limite da exposição como a folha o mostra: ``≤ R$ 96,5 mi``; sem saldo, ``·``."""
    return "·" if cents is None else f"≤ {calculations.format_money_compact(cents)}"


def _delay_tone(days: int | None) -> Tone | None:
    """O vermelho do desvio positivo (atraso); sem desvio ou adiantado, sem cor."""
    if days is None or days <= 0:
        return None
    return Tone.ERROR


def _nature_tone(nature: str) -> Tone | None:
    """O tom do risco no ponto de atenção: oportunidade em verde, ameaça em âmbar."""
    if not nature:
        return None
    return Tone.OK if nature == "Oportunidade" else Tone.WARN


def _meta_text(value: Decimal | None) -> str:
    """O número de uma meta como a folha o mostra: sem meta vigente, zero."""
    return calculations.format_number0(value if value is not None else Decimal(0))


# ── Carteira de projetos (só no Portfólio) ─────────────────────────────────


def _carteira_kpis(c: service.CarteiraSheet) -> tuple[Kpi, ...]:
    """Os indicadores da carteira na data de referência, com a referência de gestão."""
    sobre = c.vac_cents is not None and c.vac_cents < 0
    return (
        Kpi(
            f"{SHEET_CARTEIRA} · Projetos na carteira",
            c.project_count,
            _joined(
                f"Referência de {c.project_count} cadastrados",
                "ponderação composta configurável",
            ),
            ValueKind.INTEGER,
            tone=Tone.INFO,
        ),
        Kpi(
            f"{SHEET_CARTEIRA} · Orçamento da carteira (BAC)",
            c.budget_cents,
            _joined(
                f"Linha de base {calculations.format_money_thousands(c.budget_baseline_cents)}",
                "soma das EAC vigentes",
            ),
            ValueKind.MONEY,
            tone=Tone.INFO,
        ),
        Kpi(
            f"{SHEET_CARTEIRA} · Avanço ponderado",
            c.actual,
            _joined(
                f"Previsto {calculations.format_percent(c.predicted)}",
                f"desvio {calculations.format_pp(c.deviation_pp)}",
            ),
            ValueKind.PERCENT,
            digits=1,
            tone=Tone.OK,
        ),
        Kpi(
            f"{SHEET_CARTEIRA} · SPI físico ponderado",
            c.spi,
            _joined(
                "Meta ≥ 1,00",
                f"término {calculations.format_month(c.trend_finish)} x LB "
                f"{calculations.format_month(c.baseline_finish)}",
            ),
            ValueKind.DECIMAL,
            tone=_tone(c.spi_tone),
        ),
        Kpi(
            f"{SHEET_CARTEIRA} · CPI da carteira",
            c.cpi,
            _joined("Meta ≥ 1,00", "EV ÷ AC somados dos projetos"),
            ValueKind.DECIMAL,
            tone=_tone(c.cpi_tone),
        ),
        Kpi(
            f"{SHEET_CARTEIRA} · Projeção no término",
            c.projection_cents,
            _joined(
                f"Orçado {calculations.format_money_thousands(c.budget_cents)}",
                _vac_text(c.vac_cents),
            ),
            ValueKind.MONEY,
            tone=Tone.ERROR if sobre else Tone.OK,
        ),
    )


def _carteira_tables(c: service.CarteiraSheet) -> tuple[Table, ...]:
    """A tabela por projeto (com o rodapé da carteira) e os critérios de ponderação."""
    return (_carteira_projects_table(c), _carteira_criteria_table(c))


def _carteira_projects_table(c: service.CarteiraSheet) -> Table:
    """Os projetos da carteira: peso, BAC, avanço, índices, projeção, VAC, términos e situação."""
    return Table(
        title="Projetos da carteira",
        columns=(
            Column("Projeto", width=32),
            Column("Peso", ValueKind.PERCENT, digits=2),
            Column("BAC", ValueKind.MONEY),
            Column("Previsto", ValueKind.PERCENT, digits=1),
            Column("Real", ValueKind.PERCENT, digits=1),
            Column("SPI", ValueKind.DECIMAL, digits=2),
            Column("CPI", ValueKind.DECIMAL, digits=2),
            Column("Projeção", ValueKind.MONEY),
            Column("VAC", ValueKind.MONEY),
            Column("Término (LB)", ValueKind.DATE),
            Column("Término (tendência)", ValueKind.DATE),
            Column("Riscos críticos", ValueKind.INTEGER),
            Column("Pedidos críticos", ValueKind.INTEGER),
            Column("Ações atrasadas", ValueKind.INTEGER),
            Column("Situação", width=12),
        ),
        rows=tuple(
            row(
                f"{item.code} · {item.name}",
                item.weight,
                item.budget_cents,
                item.predicted,
                item.actual,
                Cell(item.spi, _below_one(item.spi)),
                Cell(item.cpi, _below_one(item.cpi)),
                item.projection_cents,
                item.vac_cents,
                item.baseline_finish,
                item.trend_finish,
                item.critical_risks,
                item.critical_orders,
                item.overdue_actions,
                Cell(item.health_label, _tone(item.health)),
            )
            for item in c.projects
        ),
        totals=_carteira_totals(c),
        per_project=False,
    )


def _carteira_totals(c: service.CarteiraSheet) -> tuple[Cell, ...]:
    """O rodapé da carteira: o peso fecha em 100,00% e os números são os consolidados do dono."""
    return (
        Cell("Total da carteira", Tone.NEUTRAL),
        Cell(Decimal(100)),
        Cell(c.budget_cents),
        Cell(c.predicted),
        Cell(c.actual),
        Cell(c.spi),
        Cell(c.cpi),
        Cell(c.projection_cents),
        Cell(c.vac_cents),
        Cell(c.baseline_finish),
        Cell(c.trend_finish),
        Cell(c.critical_risks),
        Cell(c.critical_orders),
        Cell(c.overdue_actions),
        Cell(),
    )


def _carteira_criteria_table(c: service.CarteiraSheet) -> Table:
    """Os critérios da ponderação vigente: o nome, o peso e a fonte."""
    return Table(
        title="Critérios de ponderação",
        columns=(
            Column("Critério", width=48),
            Column("Peso", ValueKind.PERCENT, digits=0),
            Column("Fonte", width=40),
        ),
        rows=tuple(
            row(item.name, item.weight, _SOURCE_TEXT.get(item.source, item.source))
            for item in c.criteria
        ),
        per_project=False,
    )


# ── Planejamento ───────────────────────────────────────────────────────────


def _planning_kpis(sheets: service.ReportSheets) -> tuple[Kpi, ...]:
    """Os indicadores do Planejamento: a posição no corte e a produtividade da janela."""
    sheet = sheets.planning
    if sheet is None or sheet.empty:
        return ()
    return (
        *_planning_position_kpis(sheets, sheet),
        *_productivity_kpis(sheet.figures.productivity),
    )


def _planning_position_kpis(
    sheets: service.ReportSheets, sheet: service.PlanningSheet
) -> tuple[Kpi, ...]:
    """A posição no corte: o previsto, o real, o SPI, o avanço do período, o término e o desvio."""
    figures = sheet.figures
    actual = sheet.actual_period
    predicted = sheet.predicted_period
    deviation = None if actual is None or predicted is None else actual - predicted
    return (
        Kpi(
            f"{SHEET_PLANEJAMENTO} · Avanço previsto (acumulado)",
            figures.predicted,
            _joined("Linha de base", calculations.format_date(sheets.cut)),
            ValueKind.PERCENT,
            digits=1,
            tone=Tone.INFO,
        ),
        Kpi(
            f"{SHEET_PLANEJAMENTO} · Avanço real (acumulado)",
            figures.actual,
            _joined(
                f"Previsto {calculations.format_percent(figures.predicted)}",
                f"desvio {calculations.format_pp(figures.deviation_pp)}",
            ),
            ValueKind.PERCENT,
            digits=1,
            tone=Tone.OK,
        ),
        Kpi(
            f"{SHEET_PLANEJAMENTO} · SPI físico",
            figures.spi,
            _joined(
                "Meta ≥ 1,00",
                f"período anterior {calculations.format_index(figures.previous_spi)}"
                if figures.previous_spi is not None
                else "real ÷ previsto",
            ),
            ValueKind.DECIMAL,
            tone=_tone(_index_band(figures.spi)),
        ),
        Kpi(
            f"{SHEET_PLANEJAMENTO} · Avanço na "
            f"{'semana' if sheets.kind == calendario.WEEKLY else 'mês'}",
            actual,
            _joined(
                f"Previsto {calculations.format_number1(predicted)} p.p.",
                f"desvio {calculations.format_pp(deviation)}" if deviation is not None else "",
            ),
            ValueKind.DECIMAL,
            digits=1,
            tone=_tone(
                "info" if deviation is None else ("success" if deviation >= 0 else "danger")
            ),
        ),
        Kpi(
            f"{SHEET_PLANEJAMENTO} · Término pela tendência",
            figures.trend_finish,
            _joined("Linha de base", calculations.format_month(figures.baseline_finish)),
            ValueKind.DATE,
            tone=_tone(_trend_band(figures)),
        ),
        Kpi(
            f"{SHEET_PLANEJAMENTO} · Desvio acumulado",
            figures.deviation_pp,
            _joined(
                "Meta ≥ 0",
                f"faixas {_MINUS}{calculations.format_number0(sheet.deviation_bands[0])} e "
                f"{_MINUS}{calculations.format_number0(sheet.deviation_bands[1])} p.p.",
            ),
            ValueKind.DECIMAL,
            digits=1,
            tone=Tone.ERROR if figures.deviation_pp < 0 else Tone.OK,
        ),
    )


def _trend_band(figures: calculations.PlanningFigures) -> str:
    """A cor do término pela tendência: vermelho quando passa da linha de base."""
    late = (
        figures.trend_finish is not None
        and figures.baseline_finish is not None
        and figures.trend_finish > figures.baseline_finish
    )
    return "danger" if late else "success"


def _productivity_kpis(
    productivity: calculations.ProductivityFigure | None,
) -> tuple[Kpi, ...]:
    """A produtividade da janela, com as metas vigentes e as faixas que o dono calcula."""
    if productivity is None:
        return ()
    bands = productivity.bands
    spi_band = (bands.spi if bands else None) or _index_band(productivity.spi)
    pf_band = (bands.pf if bands else None) or "info"
    adherence_band = (bands.adherence if bands else None) or "info"
    working_band = (bands.working if bands else None) or "info"
    utilization_band = (bands.utilization if bands else None) or "info"
    stoppage = productivity.stoppage_share is not None and productivity.stoppage_share > 5
    return (
        Kpi(
            f"{SHEET_PLANEJAMENTO} · SPI de quantidades",
            productivity.spi,
            _joined("Meta ≥ 1,00", "horas ganhas ÷ planejadas"),
            ValueKind.DECIMAL,
            tone=_tone(spi_band),
        ),
        Kpi(
            f"{SHEET_PLANEJAMENTO} · Fator de produtividade (FP)",
            productivity.pf_window,
            _joined(
                f"Meta ≤ {calculations.format_index(productivity.meta_pf)}",
                "HH aprop. ÷ ganhas",
            ),
            ValueKind.DECIMAL,
            tone=_tone(pf_band),
        ),
        Kpi(
            f"{SHEET_PLANEJAMENTO} · Aderência semanal",
            productivity.adherence,
            _joined(
                f"Meta ≥ {calculations.format_number0(productivity.meta_adherence)}%",
                "real ÷ LB",
            ),
            ValueKind.PERCENT,
            digits=1,
            tone=_tone(adherence_band),
        ),
        Kpi(
            f"{SHEET_PLANEJAMENTO} · Pessoas trabalhando",
            productivity.working_pct,
            _joined(
                f"Meta ≥ {calculations.format_number0(productivity.meta_working)}%",
                "amostragem",
            ),
            ValueKind.PERCENT,
            digits=1,
            tone=_tone(working_band),
        ),
        Kpi(
            f"{SHEET_PLANEJAMENTO} · Utilização da jornada",
            productivity.utilization,
            _joined(
                f"Meta ≥ {calculations.format_number0(productivity.meta_utilization)}%",
                "horas efetivas",
            ),
            ValueKind.PERCENT,
            digits=1,
            tone=_tone(utilization_band),
        ),
        Kpi(
            f"{SHEET_PLANEJAMENTO} · HH paralisadas",
            productivity.stoppage_share,
            _joined(
                "Limite ≤ 5%",
                f"{calculations.format_number0(productivity.stoppage_hours)} HH na janela",
            ),
            ValueKind.PERCENT,
            digits=1,
            tone=Tone.WARN if stoppage else Tone.OK,
        ),
    )


def _planning_tables(sheets: service.ReportSheets) -> tuple[Table, ...]:
    """O avanço por área (ou por projeto) e as tabelas do relato da folha 2."""
    sheet = sheets.planning
    if sheet is None:
        return ()
    tables: list[Table] = []
    if not sheet.empty:
        tables.append(_areas_table(sheet))
    if sheets.is_portfolio:
        tables.append(_project_relatos_table(sheets.project_relatos, kind=sheets.kind))
        if sheets.relato_points:
            tables.append(_portfolio_points_table(sheets.relato_points))
    elif sheets.relato is not None:
        tables.extend(_relato_tables(sheets.relato))
    return tuple(tables)


def _areas_table(sheet: service.PlanningSheet) -> Table:
    """O avanço por área (no projeto) ou por projeto (no Portfólio), com o desvio em p.p."""
    portfolio = sheet.is_portfolio
    return Table(
        title="Avanço por projeto" if portfolio else "Avanço por área",
        columns=(
            Column("Projeto" if portfolio else "Área", width=32),
            Column("Peso", ValueKind.PERCENT, digits=0),
            Column("Previsto", ValueKind.PERCENT, digits=0),
            Column("Real", ValueKind.PERCENT, digits=0),
            Column("Desvio (p.p.)", ValueKind.DECIMAL, digits=1),
        ),
        rows=tuple(_area_row(item, portfolio=portfolio) for item in sheet.rows),
        per_project=False,
    )


def _area_row(item: Any, *, portfolio: bool) -> Row:
    """Uma linha do avanço: no Portfólio o código do projeto abre o nome da linha."""
    name = f"{item.code} · {item.name}" if portfolio else item.name
    return row(
        name,
        item.weight,
        item.predicted,
        item.actual,
        Cell(item.deviation_pp, Tone.ERROR if item.deviation_pp < 0 else None),
    )


def _project_relatos_table(relatos: Sequence[service.ProjectRelatoSheet], *, kind: str) -> Table:
    """Os relatos dos projetos no Portfólio: quando foi registrado e quantos pontos tem."""
    header = f"Relato {'semanal' if kind == calendario.WEEKLY else 'mensal'}"
    return Table(
        title="Relatos dos projetos",
        columns=(
            Column("Projeto", width=32),
            Column(header, width=24),
            Column("Pontos", ValueKind.INTEGER),
        ),
        rows=tuple(
            row(
                item.project_label,
                item.updated if item.registered else Cell("pendente", Tone.ERROR),
                len(item.points) if item.registered else None,
            )
            for item in relatos
        ),
        per_project=False,
    )


def _portfolio_points_table(points: Sequence[tuple[str, Any]]) -> Table:
    """Os pontos de atenção dos relatos dos projetos, até os oito do protótipo."""
    return Table(
        title="Pontos de atenção e riscos dos projetos",
        columns=(
            Column("Nº", ValueKind.INTEGER, width=6),
            Column("Projeto", width=32),
            Column("Ponto de atenção", width=60),
            Column("Risco", width=14),
            Column("Descrição do risco", width=48),
        ),
        rows=tuple(
            row(
                index,
                project,
                point.description,
                Cell(point.nature, _nature_tone(point.nature)),
                point.risk,
            )
            for index, (project, point) in enumerate(points[:8], start=1)
        ),
        per_project=False,
    )


def _relato_tables(relato: Any) -> tuple[Table, ...]:
    """O relato do projeto: as atividades do período e do próximo e os pontos de atenção."""
    tables: list[Table] = []
    if relato.activities:
        tables.append(_activities_table("Atividades do período", relato.activities))
    if relato.next_activities:
        tables.append(_activities_table("Atividades do próximo período", relato.next_activities))
    if relato.points:
        tables.append(_points_table(relato.points))
    return tuple(tables)


def _activities_table(title: str, activities: Sequence[str]) -> Table:
    """Uma lista de atividades do relato como tabela de uma coluna."""
    return Table(
        title=title,
        columns=(Column("Atividade", width=90),),
        rows=tuple(row(text) for text in activities),
        per_project=False,
    )


def _points_table(points: Sequence[Any]) -> Table:
    """Os pontos de atenção do relato do projeto, com a natureza e o risco atrelado."""
    return Table(
        title="Pontos de atenção e riscos",
        columns=(
            Column("Nº", ValueKind.INTEGER, width=6),
            Column("Ponto de atenção", width=60),
            Column("Risco", width=14),
            Column("Descrição do risco", width=48),
        ),
        rows=tuple(
            row(
                index,
                point.description,
                Cell(point.nature, _nature_tone(point.nature)),
                point.risk,
            )
            for index, point in enumerate(points, start=1)
        ),
        per_project=False,
    )


# ── Financeiro ─────────────────────────────────────────────────────────────


def _financeiro_kpis(f: service.FinanceiroSheet) -> tuple[Kpi, ...]:
    """Os indicadores de custo no mês de competência; sem fechamento, a folha não os tem."""
    if f.empty:
        return ()
    sobre = f.vac_cents is not None and f.vac_cents < 0
    return (
        Kpi(
            f"{SHEET_FINANCEIRO} · Orçamento vigente (BAC)",
            f.budget_cents,
            "EAC revisão vigente",
            ValueKind.MONEY,
            tone=Tone.INFO,
        ),
        Kpi(
            f"{SHEET_FINANCEIRO} · Realizado acumulado",
            f.actual_cents,
            _joined(
                f"Previsto {calculations.format_money_thousands(f.pv_cents)}",
                f"{calculations.format_money_thousands(f.actual_month_cents)} no mês · plan. "
                f"{calculations.format_money_thousands(f.planned_month_cents)}",
            ),
            ValueKind.MONEY,
            tone=Tone.OK,
        ),
        Kpi(
            f"{SHEET_FINANCEIRO} · Valor agregado (EV)",
            f.ev_cents,
            _joined(
                f"Previsto {calculations.format_money_thousands(f.pv_cents)}",
                "planejado (PV)",
            ),
            ValueKind.MONEY,
            tone=Tone.OK,
        ),
        Kpi(
            f"{SHEET_FINANCEIRO} · CPI",
            f.cpi,
            _joined(
                "Meta ≥ 1,00",
                f"mês anterior {calculations.format_index(f.previous_cpi)} · "
                f"SPI {calculations.format_index(f.spi)}",
            ),
            ValueKind.DECIMAL,
            tone=_tone(_index_band(f.cpi)),
        ),
        Kpi(
            f"{SHEET_FINANCEIRO} · Projeção no término",
            f.projection_cents,
            _joined(
                f"Orçado {calculations.format_money_thousands(f.budget_cents)}",
                _vac_text(f.vac_cents),
            ),
            ValueKind.MONEY,
            tone=Tone.ERROR if sobre else Tone.OK,
        ),
        Kpi(
            f"{SHEET_FINANCEIRO} · Contingência consumida",
            f.contingency_pct,
            _joined(
                f"{calculations.format_money_thousands(f.contingency_consumed_cents)} de "
                f"{calculations.format_money_thousands(f.contingency_total_cents)}"
            ),
            ValueKind.PERCENT,
            digits=1,
            tone=Tone.INFO,
        ),
    )


def _financeiro_tables(f: service.FinanceiroSheet) -> tuple[Table, ...]:
    """O valor agregado mês a mês e a EAC por pacote (ou por projeto, no Portfólio)."""
    if f.empty:
        return ()
    tables: list[Table] = []
    if f.history:
        tables.append(_value_months_table(f.history))
    if f.packages or f.total is not None:
        tables.append(_packages_table(f))
    return tuple(tables)


def _value_months_table(history: Sequence[service.CostValueMonth]) -> Table:
    """O valor agregado dos últimos meses: PV, EV e AC com o CPI e o SPI de cada mês."""
    return Table(
        title="Valor agregado mês a mês",
        columns=(
            Column("Mês", ValueKind.DATE, width=12),
            Column("Planejado (PV)", ValueKind.MONEY),
            Column("Agregado (EV)", ValueKind.MONEY),
            Column("Real (AC)", ValueKind.MONEY),
            Column("CPI", ValueKind.DECIMAL, digits=2),
            Column("SPI", ValueKind.DECIMAL, digits=2),
        ),
        rows=tuple(
            row(
                item.month,
                item.pv_cents,
                item.ev_cents,
                item.ac_cents,
                Cell(item.cpi, _below_one(item.cpi)),
                Cell(item.spi, _below_one(item.spi)),
            )
            for item in history
        ),
        per_project=False,
    )


def _packages_table(f: service.FinanceiroSheet) -> Table:
    """A EAC por pacote (nível 1) do projeto, ou por projeto no Portfólio, com o total no rodapé."""
    return Table(
        title="EAC por projeto" if f.is_portfolio else "EAC por pacote",
        columns=(
            Column("Projeto" if f.is_portfolio else "Pacote", width=40),
            Column("Orçado", ValueKind.MONEY),
            Column("Comprometido", ValueKind.MONEY),
            Column("Realizado", ValueKind.MONEY),
            Column("Projeção", ValueKind.MONEY),
            Column("Desvio", ValueKind.PERCENT, digits=1),
        ),
        rows=tuple(_package_row(item, portfolio=f.is_portfolio) for item in f.packages),
        totals=None if f.total is None else _package_totals(f.total, portfolio=f.is_portfolio),
        per_project=False,
    )


def _package_row(item: service.CostPackageRow, *, portfolio: bool) -> Row:
    """Uma linha da EAC: no projeto o código do pacote abre a descrição; a faixa pinta o desvio."""
    name = item.description if portfolio or not item.code else f"{item.code} {item.description}"
    return row(
        name,
        item.current_cents,
        item.committed_cents,
        item.actual_cents,
        item.projection_cents,
        Cell(item.deviation_percent, _tone(item.band_tone)),
    )


def _package_totals(total: service.CostPackageRow, *, portfolio: bool) -> tuple[Cell, ...]:
    """O rodapé da EAC: o total do projeto (ou da carteira) com o desvio da faixa."""
    return (
        Cell("Total da carteira" if portfolio else "Total do projeto"),
        Cell(total.current_cents),
        Cell(total.committed_cents),
        Cell(total.actual_cents),
        Cell(total.projection_cents),
        Cell(total.deviation_percent, _tone(total.band_tone)),
    )


# ── Suprimentos ────────────────────────────────────────────────────────────


def _procurement_kpis(s: service.ProcurementSheet) -> tuple[Kpi, ...]:
    """Os indicadores do painel de suprimentos no corte, com as metas vigentes."""
    return (
        Kpi(
            f"{SHEET_SUPRIMENTOS} · Aderência ao plano de compras",
            s.adherence_pct,
            _joined(
                f"Meta ≥ {calculations.format_number(s.adherence_target)}%",
                f"{calculations.format_number(s.adjudicated)} de "
                f"{calculations.format_number(s.planned)} previstos até o corte",
            ),
            ValueKind.PERCENT,
            digits=1,
            tone=_tone(_meta_band(s.adherence_pct, s.adherence_target)),
        ),
        Kpi(
            f"{SHEET_SUPRIMENTOS} · Pacotes adjudicados",
            s.adjudicated,
            _joined(
                f"de {calculations.format_number(s.packages_total)}",
                f"Previsto {calculations.format_number(s.planned)}",
                f"{calculations.format_money_thousands(s.adjudicated_cents)} adjudicados",
            ),
            ValueKind.INTEGER,
            tone=Tone.OK,
        ),
        Kpi(
            f"{SHEET_SUPRIMENTOS} · Saving",
            s.saving_pct,
            _joined(
                "Meta ≥ 0%",
                f"{calculations.format_money_thousands(s.saving_cents)} sobre a estimativa",
            ),
            ValueKind.PERCENT,
            digits=1,
            tone=Tone.OK,
        ),
        Kpi(
            f"{SHEET_SUPRIMENTOS} · Entregas no prazo (OTD)",
            s.otd_pct,
            _joined(
                f"Meta ≥ {calculations.format_number(s.otd_target)}%",
                f"{calculations.format_number(s.delivered_on_time)} de "
                f"{calculations.format_number(s.delivered)} entregas até o corte",
            ),
            ValueKind.PERCENT,
            digits=1,
            tone=_tone(_meta_band(s.otd_pct, s.otd_target)),
        ),
        Kpi(
            f"{SHEET_SUPRIMENTOS} · Pedidos críticos",
            s.critical,
            _joined(
                "Esperado 0",
                f"folga negativa · {calculations.format_number(s.warning)} em atenção",
            ),
            ValueKind.INTEGER,
            tone=Tone.ERROR if s.critical else Tone.OK,
        ),
        Kpi(
            f"{SHEET_SUPRIMENTOS} · Pedidos emitidos",
            s.emitted,
            _joined(
                f"Linha de base {calculations.format_number(s.emitted_planned)}",
                "até o corte",
            ),
            ValueKind.INTEGER,
            tone=Tone.OK,
        ),
    )


def _procurement_tables(s: service.ProcurementSheet) -> tuple[Table, ...]:
    """Os pedidos críticos, os marcos realizados no período e os previstos do horizonte."""
    tables: list[Table] = []
    if s.criticals:
        tables.append(_criticals_table(s))
    if s.events:
        tables.append(_events_table("Realizado no período", s.events[:5], portfolio=s.is_portfolio))
    if s.forecasts:
        title = "Previsto nas próximas 4 semanas" if s.weekly else "Previsto no próximo mês"
        tables.append(_events_table(title, s.forecasts[:5], portfolio=s.is_portfolio))
    return tuple(tables)


def _criticals_table(s: service.ProcurementSheet) -> Table:
    """Os pedidos críticos da folha, até os quatro que ela mostra, com a folga negativa."""
    return Table(
        title="Pedidos críticos",
        columns=(
            Column("Pedido", width=20),
            Column("Item", width=48),
            Column("ROS", ValueKind.DATE, width=12),
            Column("Previsão", ValueKind.DATE, width=12),
            Column("Folga", ValueKind.INTEGER, width=10),
        ),
        rows=tuple(
            row(
                f"{item.number} (LLI)" if item.lli else item.number,
                _item_text(item.description, item.project_code, portfolio=s.is_portfolio),
                item.ros,
                item.forecast,
                Cell(item.slack_days, Tone.ERROR),
            )
            for item in s.criticals[:4]
        ),
        per_project=False,
    )


def _events_table(
    title: str, events: Sequence[service.ProcurementEventRow], *, portfolio: bool
) -> Table:
    """Uma tabela de eventos de suprimentos: a data, o marco, o pedido e o desvio em dias."""
    return Table(
        title=title,
        columns=(
            Column("Data", ValueKind.DATE, width=12),
            Column("Marco", width=16),
            Column("Pedido / pacote", width=20),
            Column("Item", width=48),
            Column("Desvio", ValueKind.INTEGER, width=10),
        ),
        rows=tuple(
            row(
                item.date,
                item.kind,
                item.code,
                _item_text(item.description, item.project_code, portfolio=portfolio),
                Cell(item.deviation_days, _delay_tone(item.deviation_days)),
            )
            for item in events
        ),
        per_project=False,
    )


def _item_text(description: str, project_code: str, *, portfolio: bool) -> str:
    """O item da linha: no Portfólio o código do projeto abre a descrição."""
    return f"{project_code} · {description}" if portfolio and project_code else description


# ── Riscos ─────────────────────────────────────────────────────────────────


def _risk_kpis(r: service.RiskSheet) -> tuple[Kpi, ...]:
    """Os indicadores do painel de riscos na data de referência, com a meta e a natureza."""
    kpis = [
        Kpi(
            f"{SHEET_RISCOS} · Riscos ativos",
            r.active,
            _joined(
                f"Referência de {calculations.format_number(r.registered)} cadastrados",
                f"{calculations.format_number(r.threats)} ameaças · "
                f"{calculations.format_number(r.opportunities)} oportunidades",
            ),
            ValueKind.INTEGER,
            tone=Tone.INFO,
        ),
        _risk_band_kpi(r.top, heavy=True),
    ]
    if r.second is not None:
        kpis.append(_risk_band_kpi(r.second, heavy=False))
    kpis.extend(
        (
            Kpi(
                f"{SHEET_RISCOS} · Exposição (VME)",
                r.exposure_cents,
                _joined(f"Limite {_limit_text(r.exposure_limit_cents)}", "ameaças ativas"),
                ValueKind.MONEY,
                tone=Tone.INFO,
            ),
            Kpi(
                f"{SHEET_RISCOS} · Revisão vencida",
                r.overdue_reviews,
                _joined(
                    "Esperado 0",
                    f"{calculations.format_number(r.agenda)} na pauta de escalonamento",
                ),
                ValueKind.INTEGER,
                tone=Tone.ERROR if r.overdue_reviews else Tone.OK,
            ),
            Kpi(
                f"{SHEET_RISCOS} · Identificados no período",
                r.identified,
                _joined(
                    f"Referência de {calculations.format_number(r.registered)} cadastrados",
                    f"{calculations.format_number(r.closed)} encerrados no período",
                ),
                ValueKind.INTEGER,
                tone=Tone.INFO,
            ),
        )
    )
    return tuple(kpis)


def _risk_band_kpi(band: service.RiskBandView, *, heavy: bool) -> Kpi:
    """Um indicador de faixa do painel: o total, a meta e a natureza dos riscos."""
    tone = Tone.OK if not band.total else Tone.ERROR if heavy else Tone.WARN
    return Kpi(
        f"{SHEET_RISCOS} · {band.name}s",
        band.total,
        _joined(
            f"Meta {calculations.format_number(band.goal)}",
            f"{calculations.format_number(band.threats)} ameaças · "
            f"{calculations.format_number(band.opportunities)} oportunidades",
        ),
        ValueKind.INTEGER,
        tone=tone,
    )


def _risk_tables(r: service.RiskSheet) -> tuple[Table, ...]:
    """Os principais riscos da folha, até os cinco de maior score residual."""
    if not r.principais:
        return ()
    return (
        Table(
            title="Principais riscos",
            columns=(
                Column("Nº", width=20),
                Column("Risco", width=60),
                Column("Residual", width=20),
                Column("Estratégia", width=20),
                Column("Dono", width=22),
                Column("Próx. revisão", ValueKind.DATE, width=14),
            ),
            rows=tuple(
                row(
                    item.number,
                    f"{item.title} · {item.nature}",
                    Cell(f"{item.score} {item.severity}", _tone(item.tone)),
                    item.strategy or "·",
                    item.owner_name,
                    Cell(item.next_review, Tone.ERROR if item.review_overdue else None),
                )
                for item in r.principais
            ),
            per_project=False,
        ),
    )


# ── Qualidade ──────────────────────────────────────────────────────────────


def _quality_kpis(q: service.QualitySheet) -> tuple[Kpi, ...]:
    """Os indicadores de RNC, inspeções e auditorias da folha, com as metas vigentes."""
    if q.critical_at_cut or q.overdue_at_reference:
        open_band = "danger"
    else:
        open_band = "warning" if q.open_at_cut else "success"
    discipline = q.discipline[0] if q.discipline else None
    return (
        Kpi(
            f"{SHEET_QUALIDADE} · RNC em aberto no corte",
            q.open_at_cut,
            _joined(
                "Esperado 0",
                f"{calculations.format_number(q.critical_at_cut)} críticas · "
                f"{calculations.format_number(q.overdue_at_reference)} vencidas",
            ),
            ValueKind.INTEGER,
            tone=_tone(open_band),
        ),
        Kpi(
            f"{SHEET_QUALIDADE} · RNC abertas no período",
            q.opened_period,
            _joined(
                "Esperado 0",
                f"{calculations.format_number(q.closed_period)} encerradas no período",
            ),
            ValueKind.INTEGER,
            tone=Tone.WARN if q.opened_period else Tone.OK,
        ),
        Kpi(
            f"{SHEET_QUALIDADE} · Aprovação em inspeções",
            q.approval_pct,
            _joined(
                f"Meta ≥ {_meta_text(q.approval_meta)}%",
                f"{calculations.format_number(len(q.rejected))} reprovadas em "
                f"{calculations.format_number(q.inspections)} inspeções",
            ),
            ValueKind.PERCENT,
            digits=1,
            tone=_tone(_meta_band(q.approval_pct, q.approval_meta)),
        ),
        Kpi(
            f"{SHEET_QUALIDADE} · Conformidade em auditorias",
            q.conformity_pct,
            _joined(
                f"Meta ≥ {_meta_text(q.conformity_meta)}%",
                f"{calculations.format_number(q.audits_period)} auditorias no período · "
                f"{calculations.format_number(q.late_audits)} atrasadas",
            ),
            ValueKind.PERCENT,
            digits=1,
            tone=_tone(_meta_band(q.conformity_pct, q.conformity_meta)),
        ),
        Kpi(
            f"{SHEET_QUALIDADE} · Custo da não qualidade",
            q.cost_accumulated_cents,
            _joined(
                f"Esperado {calculations.format_money(0)}",
                f"{calculations.format_money(q.cost_period_cents)} em RNC do período",
            ),
            ValueKind.MONEY,
            tone=Tone.ERROR if q.cost_accumulated_cents else Tone.OK,
        ),
        Kpi(
            f"{SHEET_QUALIDADE} · Disciplina com mais RNC",
            discipline.name if discipline is not None else "·",
            _joined(
                f"Referência de {calculations.format_number(q.discipline_total)} RNCs",
                f"{calculations.format_number(discipline.total)} RNC · "
                f"{calculations.format_percent(discipline.pct)} do total"
                if discipline is not None
                else "",
            ),
            ValueKind.TEXT,
            tone=Tone.INFO,
        ),
    )


def _quality_tables(q: service.QualitySheet) -> tuple[Table, ...]:
    """As inspeções reprovadas do período e a pauta de tratamento da data de referência."""
    tables: list[Table] = []
    if q.rejected:
        tables.append(_rejected_table(q.rejected))
    if q.agenda:
        tables.append(_agenda_table(q.agenda))
    return tuple(tables)


def _rejected_table(rejected: Sequence[service.QualityRejectedRow]) -> Table:
    """As inspeções reprovadas, até as cinco que a folha mostra, com o ITP no ponto."""
    return Table(
        title="Inspeções reprovadas no período",
        columns=(
            Column("Data", ValueKind.DATE, width=12),
            Column("Ponto", width=40),
            Column("Empresa", width=28),
            Column("RNC", width=20),
        ),
        rows=tuple(
            row(item.date, _point_text(item), item.company_name, item.rnc_code or "·")
            for item in rejected[:5]
        ),
        per_project=False,
    )


def _point_text(item: service.QualityRejectedRow) -> str:
    """O ponto da inspeção com o ITP ao lado, quando há um."""
    return f"{item.point} ({item.itp_code})" if item.itp_code else item.point


def _agenda_table(agenda: Sequence[service.QualityAgendaRow]) -> Table:
    """A pauta de tratamento, até as cinco RNC que a folha mostra, com os motivos do dono."""
    return Table(
        title="Pauta de tratamento",
        columns=(
            Column("RNC", width=20),
            Column("Não conformidade", width=60),
            Column("Severidade", width=12),
            Column("Situação", width=16),
            Column("Motivo", width=48),
        ),
        rows=tuple(
            row(
                item.code,
                item.description,
                item.severity,
                item.situation,
                Cell("; ".join(item.reasons), Tone.ERROR if item.reasons else None),
            )
            for item in agenda[:5]
        ),
        per_project=False,
    )


# ── HSE ────────────────────────────────────────────────────────────────────


def _hse_kpis(h: service.HseSheet) -> tuple[Kpi, ...]:
    """Os indicadores do HSE no mês do corte, com o acumulado e os proativos."""
    if h.empty:
        return ()
    return (*_hse_month_kpis(h), *_hse_proactive_kpis(h))


def _hse_month_kpis(h: service.HseSheet) -> tuple[Kpi, ...]:
    """As taxas do mês e do acumulado, os dias sem afastamento e o HHT ou as ocorrências."""
    month = h.month_indicators
    accumulated = h.accumulated
    kpis = [
        Kpi(
            f"{SHEET_HSE} · Taxa de frequência (TF)",
            month.tf,
            _joined(
                f"Esperado {calculations.format_number2(Decimal(0))}",
                f"no mês · acumulado {calculations.format_number2(accumulated.tf)}",
            ),
            ValueKind.DECIMAL,
            digits=2,
            tone=Tone.ERROR if month.lti else Tone.OK,
        ),
        Kpi(
            f"{SHEET_HSE} · Lesões registráveis (TRIF)",
            month.trif,
            _joined(
                f"Esperado {calculations.format_number2(Decimal(0))}",
                f"no mês · acumulado {calculations.format_number2(accumulated.trif)}",
            ),
            ValueKind.DECIMAL,
            digits=2,
            tone=Tone.WARN if month.registrable else Tone.OK,
        ),
        Kpi(
            f"{SHEET_HSE} · Taxa de gravidade (TG)",
            month.tg,
            _joined(
                f"Esperado {calculations.format_number1(Decimal(0))}",
                f"no mês · acumulado {calculations.format_number1(accumulated.tg)}",
            ),
            ValueKind.DECIMAL,
            digits=1,
            tone=Tone.INFO,
        ),
        Kpi(
            f"{SHEET_HSE} · Alto potencial (HiPo)",
            month.hipo,
            _joined(
                "Esperado 0",
                f"no mês · {calculations.format_number(accumulated.hipo)} no acumulado",
            ),
            ValueKind.INTEGER,
            tone=Tone.ERROR if month.hipo else Tone.OK,
        ),
        Kpi(
            f"{SHEET_HSE} · Dias sem afastamento",
            accumulated.days_without_leave,
            _joined(
                f"Esperado {calculations.format_number(h.days_expected)}",
                f"no corte · desde {calculations.format_date(h.days_since)}",
            ),
            ValueKind.INTEGER,
            tone=Tone.INFO,
        ),
    ]
    if h.weekly:
        almost = h.occurrence_levels[3] if len(h.occurrence_levels) > 3 else 0
        kpis.append(
            Kpi(
                f"{SHEET_HSE} · Ocorrências na semana",
                h.occurrences,
                _joined(
                    f"Referência de {calculations.format_number(h.month_occurrences)} no mês",
                    f"{calculations.format_number(almost)} "
                    f"{'quase acidente' if almost == 1 else 'quase acidentes'}",
                ),
                ValueKind.INTEGER,
                tone=Tone.ERROR if h.hipo_period else Tone.INFO,
            )
        )
    else:
        kpis.append(
            Kpi(
                f"{SHEET_HSE} · HHT no mês",
                month.hours,
                _joined(
                    f"Previsto {calculations.format_number(h.hours_expected)}",
                    f"{calculations.format_number(accumulated.hours)} HHT no acumulado",
                ),
                ValueKind.DECIMAL,
                digits=0,
                tone=Tone.INFO,
            )
        )
    return tuple(kpis)


def _hse_proactive_kpis(h: service.HseSheet) -> tuple[Kpi, ...]:
    """Os seis indicadores proativos no acumulado do primeiro mês com HHT, com o mês ao lado."""
    month = h.month_indicators
    accumulated = h.accumulated
    return (
        Kpi(
            f"{SHEET_HSE} · DDS realizados",
            accumulated.dds_pct,
            _joined("Meta 100%", f"no mês {calculations.format_percent(month.dds_pct)}"),
            ValueKind.PERCENT,
            digits=1,
            tone=Tone.INFO,
        ),
        Kpi(
            f"{SHEET_HSE} · Conformidade em inspeções",
            accumulated.conformity_pct,
            _joined("Esperado 100%", f"no mês {calculations.format_percent(month.conformity_pct)}"),
            ValueKind.PERCENT,
            digits=1,
            tone=Tone.INFO,
        ),
        Kpi(
            f"{SHEET_HSE} · Observações / 10 mil HHT",
            accumulated.observations_per_10k,
            _joined(
                f"Meta ≥ {calculations.format_number(h.observations_target)}",
                "abordagens comportamentais",
            ),
            ValueKind.DECIMAL,
            digits=1,
            tone=Tone.INFO,
        ),
        Kpi(
            f"{SHEET_HSE} · Relato de quase acidentes",
            accumulated.almost_miss_report,
            _joined(
                f"Referência {calculations.format_number1(h.reference_ratio)}",
                "por lesão registrável",
            ),
            ValueKind.DECIMAL,
            digits=1,
            tone=Tone.INFO,
        ),
        Kpi(
            f"{SHEET_HSE} · Recomendações fechadas",
            accumulated.recommendations_pct,
            _joined("Esperado 100%", "APR e HAZOP"),
            ValueKind.PERCENT,
            digits=1,
            tone=Tone.INFO,
        ),
        Kpi(
            f"{SHEET_HSE} · Incidentes ambientais",
            accumulated.environmental,
            _joined("Esperado 0", f"{calculations.format_number(month.environmental)} no mês"),
            ValueKind.INTEGER,
            tone=Tone.WARN if accumulated.environmental else Tone.OK,
        ),
    )


# ── Análises do período e desvios negativos ────────────────────────────────


def _analysis_tables(sheets: service.ReportSheets) -> tuple[Table, ...]:
    """As abas do protótipo: a análise de cada folha e os desvios negativos com o comentário."""
    views = _analysis_views(sheets)
    if not views:
        return ()
    tables = [_analysis_table(views)]
    deviations = _deviation_rows(views)
    if deviations:
        tables.append(_deviations_table(deviations))
    return tuple(tables)


def _analysis_views(sheets: service.ReportSheets) -> tuple[service.AnalysisView, ...]:
    """As análises das folhas presentes, na ordem das folhas."""
    views: list[service.AnalysisView] = []
    if sheets.planning is not None and sheets.analysis is not None:
        views.append(sheets.analysis)
    for sheet in (
        sheets.financeiro,
        sheets.suprimentos,
        sheets.riscos,
        sheets.qualidade,
        sheets.hse,
    ):
        if sheet is not None:
            views.append(sheet.analysis)
    return tuple(views)


def _analysis_table(views: Sequence[service.AnalysisView]) -> Table:
    """Uma linha por folha com análise: o módulo, o tipo, o período, o texto e a atualização."""
    return Table(
        title="Análises do período",
        columns=(
            Column("Módulo", width=28),
            Column("Tipo", width=10),
            Column("Período", width=14),
            Column("Análise", width=90),
            Column("Atualizada", width=32),
        ),
        rows=tuple(
            row(
                view.module_label,
                view.kind,
                view.period_label,
                view.record.text if view.record is not None else "Não registrada",
                _updated_text(view.record),
            )
            for view in views
        ),
        per_project=False,
    )


def _updated_text(record: service.AnalysisRecordView | None) -> str:
    """Quando e por quem a análise foi atualizada; sem registro, vazio."""
    if record is None:
        return ""
    return f"{calculations.format_date(record.updated_at)} · {record.updated_by}"


def _deviation_rows(views: Sequence[service.AnalysisView]) -> tuple[Row, ...]:
    """Uma linha por desvio detectado, na ordem das folhas, com o comentário ou a pendência."""
    return tuple(
        row(
            view.module_label,
            deviation.indicator,
            deviation.description,
            _comment_text(deviation, required=view.deviation_required),
        )
        for view in views
        for deviation in view.deviations
    )


def _comment_text(deviation: service.AnalysisDeviationView, *, required: bool) -> str:
    """O comentário do desvio; vazio é pendente nos módulos que exigem o comentário."""
    if deviation.comment:
        return deviation.comment
    return "Comentário pendente" if required else "Sem comentário"


def _deviations_table(deviations: Sequence[Row]) -> Table:
    """Os desvios negativos de todas as folhas, com o comentário de cada um."""
    return Table(
        title="Desvios negativos e comentários",
        columns=(
            Column("Módulo", width=28),
            Column("Indicador", width=28),
            Column("Desvio", width=60),
            Column("Comentário", width=60),
        ),
        rows=tuple(deviations),
        per_project=False,
    )
