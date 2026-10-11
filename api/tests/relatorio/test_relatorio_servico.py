"""Fachada do relatório gerencial (ISSUE-083): situação do modal, folhas e escopo.

O modal mostra a situação real do relato e da análise de cada módulo sem exigir WRITE — um
Visualizador o vê. As folhas saem no corte do período, com a posição do dono, a produtividade
da janela, as barras do avanço por período e a análise e o relato do período. No Portfólio a
situação do relato sai por projeto e a folha 2 consolida os pontos de atenção.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from src.core import calendario
from src.core.errors import InvalidDataError
from src.core.scope import Scope
from src.modulos.planejamento import service as planejamento
from src.modulos.planejamento.models import EapItem, EapMeasurement
from src.modulos.planejamento.validation import MONTHLY, WEEKLY
from src.modulos.relatorio import service, validation
from tests.relatorio.conftest import Cenario, Demonstracao

PORTFOLIO = Scope(project_id=None, source="url")

D = Decimal


def _periodo(kind: str, deslocamento: int = 0) -> str:
    return (
        calendario.add_periods(kind, calendario.period_of(kind, calendario.today()), deslocamento)
        or ""
    )


def _escopo(demonstracao: Demonstracao) -> Scope:
    return Scope(project_id=demonstracao.project_id, source="url")


def _status(
    cenario: Cenario,
    *,
    user: object | None = None,
    scope: Scope | None = None,
    kind: str = WEEKLY,
    period: str = "",
    sections: tuple[str, ...] = (),
) -> service.ReportStatusView:
    return service.report_status(
        cenario.session,
        user=user or cenario.visualizador,  # type: ignore[arg-type]
        scope=scope or cenario.scope,
        kind=kind,
        period=period,
        reference_date=calendario.today(),
        sections=sections,
    )


def _gravar_relato(cenario: Cenario, *, kind: str = WEEKLY, period: str) -> None:
    planejamento.save_report(
        cenario.session,
        user=cenario.membro,
        scope=cenario.scope,
        request=planejamento.SaveRequest(
            draft=planejamento.ReportDraft(
                kind=kind,
                period=period,
                activities=("Concluída a fundação do prédio da moagem.",),
                next_activities=("Iniciar a montagem das estruturas.",),
            )
        ),
        reference_date=calendario.today(),
    )


def _folhas(
    demonstracao: Demonstracao,
    *,
    scope: Scope | None = None,
    kind: str = WEEKLY,
    period: str = "2026-S38",
    sections: tuple[str, ...] = (),
) -> service.ReportSheets:
    return service.report_view(
        demonstracao.session,
        user=demonstracao.admin,
        scope=scope or _escopo(demonstracao),
        kind=kind,
        period=period,
        sections=sections,
        reference_date=demonstracao.reference_date,
    )


# ── O escopo do relatório ──────────────────────────────────────────────────


def test_escopo_do_relatorio_e_o_pedido_ou_o_do_request(cenario: Cenario) -> None:
    assert service.report_scope(
        cenario.session, fallback=cenario.scope, requested="portfolio"
    ).is_portfolio
    assert (
        service.report_scope(
            cenario.session, fallback=cenario.scope, requested=str(cenario.project.id)
        ).project_id
        == cenario.project.id
    )
    assert (
        service.report_scope(cenario.session, fallback=cenario.scope, requested="").project_id
        == cenario.project.id
    )


def test_escopo_de_projeto_desconhecido_e_recusado(cenario: Cenario) -> None:
    with pytest.raises(InvalidDataError) as erro:
        service.report_scope(cenario.session, fallback=cenario.scope, requested="99999")

    assert service.UNKNOWN_PROJECT_MESSAGE in str(erro.value)


# ── O modal de emissão ─────────────────────────────────────────────────────


def test_modal_abre_para_visualizador_com_os_padroes(cenario: Cenario) -> None:
    status = _status(cenario)

    assert status.kind == WEEKLY
    assert status.period == _periodo(WEEKLY, -1)
    assert status.in_progress is False
    assert status.relato is not None and status.relato.registered is False
    assert status.project_options[0].value == "portfolio"
    assert status.project_options[0].selected is False
    assert status.project_options[1].value == str(cenario.project.id)
    assert status.project_options[1].selected is True
    assert status.period_options[0].period == _periodo(WEEKLY)
    assert len(status.analyses) == 6
    assert {analise.situation for analise in status.analyses} == {"missing"}
    assert all(analise.url.startswith("/") for analise in status.analyses)
    assert [secao.key for secao in status.sections] == ["planejamento"]


def test_modal_mostra_o_relato_registrado_com_o_link(cenario: Cenario) -> None:
    _gravar_relato(cenario, period=_periodo(WEEKLY, -1))

    status = _status(cenario)

    assert status.relato is not None
    assert status.relato.registered is True
    assert status.relato.url == (
        f"/planejamento/relato?abrir=1&tipo={WEEKLY}&periodo={_periodo(WEEKLY, -1)}"
    )


def test_modal_do_portfolio_lista_o_relato_por_projeto(cenario: Cenario) -> None:
    status = _status(cenario, scope=PORTFOLIO)

    assert status.relato is None
    assert len(status.project_relatos) == 1
    projeto = status.project_relatos[0]
    assert projeto.registered is False
    assert f"projeto={cenario.project.id}" in projeto.url
    assert all(analise.url.endswith("projeto=portfolio") for analise in status.analyses)


def test_modal_mostra_a_analise_registrada_e_o_desvio_novo_pendente(
    demonstracao: Demonstracao,
) -> None:
    session = demonstracao.session
    item = session.scalars(
        select(EapItem)
        .where(EapItem.project_id == demonstracao.project_id, EapItem.level == 3)
        .order_by(EapItem.weight.desc())
    ).first()
    assert item is not None
    ultima = session.scalars(
        select(EapMeasurement)
        .where(EapMeasurement.item_id == item.id)
        .order_by(EapMeasurement.measured_on.desc())
    ).first()
    assert ultima is not None and ultima.to_pct > D("5")
    session.add(
        EapMeasurement(
            item_id=item.id,
            author_id=demonstracao.admin.person_id,
            measured_on=date(2026, 9, 18),
            from_pct=ultima.to_pct,
            to_pct=ultima.to_pct - D("5"),
        )
    )
    session.flush()

    status = service.report_status(
        session,
        user=demonstracao.admin,
        scope=_escopo(demonstracao),
        kind=WEEKLY,
        period="2026-S38",
        reference_date=demonstracao.reference_date,
    )

    planejamento_status = next(a for a in status.analyses if a.module == "planejamento")
    assert planejamento_status.registered is True
    assert planejamento_status.deviations >= 1
    assert planejamento_status.pending == 1
    assert planejamento_status.situation == "deviations"
    assert planejamento_status.url == (
        "/planejamento/relato?analise=1&tipo=Semanal&periodo=2026-S38"
    )


# ── As folhas ──────────────────────────────────────────────────────────────


def test_folhas_de_projeto_sem_curva_mostram_os_avisos(cenario: Cenario) -> None:
    visao = service.report_view(
        cenario.session,
        user=cenario.visualizador,
        scope=cenario.scope,
        kind=WEEKLY,
        period=_periodo(WEEKLY, -1),
        sections=(),
        reference_date=calendario.today(),
    )

    assert visao.planning is not None
    assert visao.planning.empty is True
    assert visao.planning.bars == ()
    assert visao.planning.predicted_period is None
    assert visao.analysis is not None and visao.analysis.record is None
    assert visao.relato is None
    assert visao.relato_url.startswith("/planejamento/relato?abrir=1")


def test_folhas_do_projeto_1_no_corte_da_semana_38(demonstracao: Demonstracao) -> None:
    visao = _folhas(demonstracao)

    assert visao.cut == date(2026, 9, 20)
    assert visao.in_progress is False
    assert visao.scope_label == "TN-2026-014 · Construção de uma nova fábrica"
    assert visao.sections == ("planejamento",)
    planejamento_folha = visao.planning
    assert planejamento_folha is not None
    assert planejamento_folha.empty is False
    assert planejamento_folha.figures.predicted == D("61.7")
    assert planejamento_folha.figures.actual == D("61.8")
    assert planejamento_folha.figures.spi == D("1.00")
    assert planejamento_folha.figures.deviation_pp == D("0.1")
    assert planejamento_folha.figures.previous_spi == D("1.05")
    assert planejamento_folha.figures.trend_finish == date(2027, 4, 1)
    assert planejamento_folha.figures.baseline_finish == date(2027, 3, 1)
    assert planejamento_folha.week_label == "S38"
    assert [linha.code for linha in planejamento_folha.rows] == ["1", "2", "3", "4", "5"]
    produtividade = planejamento_folha.figures.productivity
    assert produtividade is not None
    assert produtividade.spi == D("0.89")
    assert produtividade.pf_window == D("1.10")
    assert produtividade.adherence == D("83.9")
    assert produtividade.working_pct == D("55.20")
    assert produtividade.utilization == D("77.2")
    assert produtividade.stoppage_hours == D("480.7")
    assert produtividade.stoppage_share == D("2.17")
    assert produtividade.alert_companies == ("Alfa Montagens",)
    assert len(planejamento_folha.bars) == 8
    assert planejamento_folha.bars[0].period == "2026-S31"
    assert planejamento_folha.bars[-1].period == "2026-S38"
    assert planejamento_folha.predicted_period == D("2.9")
    assert planejamento_folha.actual_period == D("0.0")
    assert visao.analysis is not None and visao.analysis.record is not None
    assert visao.analysis_url == "/planejamento/relato?analise=1&tipo=Semanal&periodo=2026-S38"
    assert visao.relato is not None
    assert visao.relato.activities


def test_folhas_do_mensal_do_projeto_1(demonstracao: Demonstracao) -> None:
    visao = _folhas(demonstracao, kind=MONTHLY, period="2026-08")

    assert visao.cut == date(2026, 8, 31)
    planejamento_folha = visao.planning
    assert planejamento_folha is not None
    assert planejamento_folha.figures.predicted == D("54.00")
    assert planejamento_folha.figures.actual == D("50.3")
    assert planejamento_folha.figures.spi == D("0.93")
    assert [bar.period for bar in planejamento_folha.bars] == [
        "2026-03",
        "2026-04",
        "2026-05",
        "2026-06",
        "2026-07",
        "2026-08",
    ]
    assert planejamento_folha.predicted_period == D("11.9")
    assert planejamento_folha.actual_period == D("11.3")


def test_folhas_do_portfolio_consolidam_os_relatos(demonstracao: Demonstracao) -> None:
    visao = _folhas(demonstracao, scope=PORTFOLIO)

    assert visao.is_portfolio is True
    assert visao.scope_label == "Portfólio · 3 projetos"
    assert visao.planning is not None and visao.planning.is_portfolio is True
    assert visao.relato is None
    assert len(visao.project_relatos) == 3
    assert visao.relato_points
    assert all(linha.project_label for linha in visao.project_relatos if linha.registered)


def test_folhas_do_periodo_em_andamento_saem_parciais(cenario: Cenario) -> None:
    visao = service.report_view(
        cenario.session,
        user=cenario.membro,
        scope=cenario.scope,
        kind=WEEKLY,
        period=_periodo(WEEKLY),
        sections=(),
        reference_date=calendario.today(),
    )

    assert visao.in_progress is True
    assert visao.cut == calendario.today()


def test_folhas_recusam_tipo_periodo_e_secao(cenario: Cenario) -> None:
    with pytest.raises(InvalidDataError) as tipo:
        service.report_view(
            cenario.session,
            user=cenario.membro,
            scope=cenario.scope,
            kind="Trimestral",
            period=_periodo(WEEKLY),
            sections=(),
            reference_date=calendario.today(),
        )
    with pytest.raises(InvalidDataError) as periodo:
        service.report_view(
            cenario.session,
            user=cenario.membro,
            scope=cenario.scope,
            kind=WEEKLY,
            period="",
            sections=(),
            reference_date=calendario.today(),
        )
    with pytest.raises(InvalidDataError) as secao:
        service.report_view(
            cenario.session,
            user=cenario.membro,
            scope=cenario.scope,
            kind=WEEKLY,
            period=_periodo(WEEKLY),
            sections=("financeiro",),
            reference_date=calendario.today(),
        )

    assert validation.FIELD_KIND in dict(tipo.value.detail)  # type: ignore[arg-type]
    assert validation.FIELD_PERIOD in dict(periodo.value.detail)  # type: ignore[arg-type]
    assert dict(secao.value.detail)[validation.FIELD_SECTIONS] == validation.SECTION_MESSAGE  # type: ignore[arg-type]
