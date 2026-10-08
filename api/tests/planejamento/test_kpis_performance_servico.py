"""Fachada dos KPIs de performance (ISSUE-048): blocos, filtro, tendência e o plano na Central.

O cenário mínimo vem de ``apoio_produtividade``; a data de referência é injetada (25/09/2026).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core import origin_links
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.scope import Scope
from src.modulos.central_acoes.models import Action
from src.modulos.central_acoes.service import complete_action
from src.modulos.central_acoes.validation import CompletionRequest
from src.modulos.planejamento import service, validation
from src.modulos.planejamento.models import ProductivityItem
from tests.apoio_produtividade import (
    HOJE,
    Cenario,
    form_amostra,
    form_item,
    form_jornada,
    form_paralisacao,
    form_plano,
    montar_cenario,
)
from tests.identidades import criar_projeto

D = Decimal


@pytest.fixture
def cenario(sessao: Session) -> Cenario:
    return montar_cenario(sessao)


def _item_aprovado(cenario: Cenario, sessao: Session, **overrides: str) -> ProductivityItem:
    item = service.save_item(
        sessao,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        item_id=None,
        form=form_item(cenario, **overrides),
        reference_date=HOJE,
    )
    return service.approve_item(
        sessao,
        user=cenario.usuario_gestor,
        scope=cenario.escopo,
        item_id=item.id,
        version=str(item.version),
        reference_date=HOJE,
    )


def _apontar(
    cenario: Cenario, sessao: Session, item: ProductivityItem, *, semana: str = "2026-S38"
) -> None:
    service.register_entries(
        sessao,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        company_id=cenario.empresa.id,
        form=validation.EntryForm(week=semana, lines={item.id: ("10", "120")}),
        reference_date=HOJE,
    )


def _campo(cenario: Cenario, sessao: Session) -> None:
    service.save_field_day(
        sessao,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        day_id=None,
        form=form_jornada(cenario, data="2026-09-24"),
        reference_date=HOJE,
    )
    service.save_work_sample(
        sessao,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        sample_id=None,
        form=form_amostra(cenario, data="2026-09-24", parado={0: "6"}),
        reference_date=HOJE,
    )
    service.save_stoppage(
        sessao,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        stoppage_id=None,
        form=form_paralisacao(cenario, data="2026-09-24"),
        reference_date=HOJE,
    )


def _aba(
    cenario: Cenario,
    sessao: Session,
    *,
    empresa: int | None = None,
    corte: str = "",
    usuario: str = "membro",
) -> service.PerformanceOverview:
    user = cenario.usuario_visualizador if usuario == "visualizador" else cenario.usuario_membro
    return service.performance_overview(
        sessao,
        user=user,
        scope=cenario.escopo,
        performance_filter=service.PerformanceFilter(company_id=empresa, cut_week=corte),
        reference_date=HOJE,
    )


def _plano(
    cenario: Cenario, sessao: Session, *, usuario: str = "membro", **overrides: str
) -> service.PerformanceActionRef:
    user = cenario.usuario_visualizador if usuario == "visualizador" else cenario.usuario_membro
    return service.create_performance_action(
        sessao,
        user=user,
        scope=cenario.escopo,
        form=form_plano(cenario, **overrides),
        cut_week="2026-S39",
        reference_date=HOJE,
    )


def test_a_aba_traz_o_geral_e_o_bloco_da_empresa(cenario: Cenario, sessao: Session) -> None:
    item = _item_aprovado(cenario, sessao)
    _apontar(cenario, sessao, item)
    _campo(cenario, sessao)

    visao = _aba(cenario, sessao)

    assert visao.cut_week == "2026-S39"
    assert len(visao.window_weeks) == 4
    assert len(visao.trend_weeks) == 12
    assert len(visao.companies) == 1
    geral = visao.general
    assert (geral.quantities.pct_real, geral.quantities.pct_prev) == (D("10.0"), D("40.0"))
    assert geral.quantities.spi == D("0.25")
    assert geral.quantities.pf_window == D("1.20")
    assert geral.quantities.window_adherence == D("25.0")
    assert geral.schedule.spi_t == D("0.25")
    assert geral.capacity.capacity == D("7.33")
    assert geral.sample.working_pct == D("62.50")
    assert geral.stoppages.crew_hours == D("53.3")
    assert geral.stoppage_share == D("50.47")
    assert geral.alerts == ("adherence", "pf", "spi")
    assert geral.has_attention
    assert visao.selected is geral
    empresa = visao.companies[0]
    assert empresa.company_id == cenario.empresa.id
    assert empresa.company_name == "Montadora Alfa"
    assert empresa.trend[-1].week == "2026-S39"


def test_o_filtro_de_empresa_seleciona_o_bloco(cenario: Cenario, sessao: Session) -> None:
    item = _item_aprovado(cenario, sessao)
    _apontar(cenario, sessao, item)

    escolhido = _aba(cenario, sessao, empresa=cenario.empresa.id)
    desconhecido = _aba(cenario, sessao, empresa=999)

    assert escolhido.selected.company_id == cenario.empresa.id
    assert desconhecido.selected is desconhecido.general


def test_o_plano_grava_uma_vez_por_empresa_e_semana(cenario: Cenario, sessao: Session) -> None:
    criada = _plano(cenario, sessao)

    referencia = f"PRD-2026-S39-{cenario.empresa.id:02d}"
    assert criada.reference == referencia
    acao = sessao.scalars(select(Action)).one()
    assert (acao.origin, acao.origin_ref, acao.group) == (
        "Produtividade",
        referencia,
        "Produtividade",
    )
    assert acao.project_id == cenario.projeto.id
    assert acao.requester_id == cenario.membro.person_id
    assert acao.responsible_id == cenario.gestor.person_id

    with pytest.raises(InvalidDataError) as recusa:
        _plano(cenario, sessao)

    assert service.ACTION_ALREADY_OPEN_MESSAGE in str(recusa.value)
    assert sessao.scalar(select(func.count()).select_from(Action)) == 1


def test_a_acao_concluida_libera_o_plano_da_mesma_semana(cenario: Cenario, sessao: Session) -> None:
    criada = _plano(cenario, sessao)
    acao = sessao.scalars(select(Action)).one()
    complete_action(
        sessao,
        user=cenario.usuario_membro,
        request=CompletionRequest(action_id=acao.id, completed_on=HOJE, version=acao.version),
        reference_date=HOJE,
    )

    segunda = _plano(cenario, sessao)

    assert segunda.reference == criada.reference
    assert sessao.scalar(select(func.count()).select_from(Action)) == 2


def test_o_link_da_acao_volta_para_a_aba_com_a_empresa_e_a_semana(
    cenario: Cenario, sessao: Session
) -> None:
    _item_aprovado(cenario, sessao)
    criada = _plano(cenario, sessao)

    link = origin_links.resolve("Produtividade", criada.reference)

    assert link.has_link
    assert link.url is not None
    assert "aba=kpis" in link.url
    assert f"empresa={cenario.empresa.id}" in link.url
    assert "corte=2026-S39" in link.url

    visao = _aba(cenario, sessao)
    empresa = visao.companies[0]
    assert empresa.action is not None
    assert empresa.action.reference == criada.reference
    assert empresa.action.url is not None
    assert "central-acoes/acoes" in empresa.action.url
    assert f"busca={criada.reference}" in empresa.action.url


def test_o_corte_anterior_acha_a_acao_da_semana(cenario: Cenario, sessao: Session) -> None:
    _item_aprovado(cenario, sessao)
    service.create_performance_action(
        sessao,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        form=form_plano(cenario),
        cut_week="2026-S38",
        reference_date=HOJE,
    )

    anterior = _aba(cenario, sessao, corte="2026-S38")
    atual = _aba(cenario, sessao, corte="2026-S39")

    referencia = f"PRD-2026-S38-{cenario.empresa.id:02d}"
    assert anterior.companies[0].action is not None
    assert anterior.companies[0].action.reference == referencia
    assert atual.companies[0].action is None


def test_o_formulario_do_plano_sugere_os_indicadores_fora_da_faixa(
    cenario: Cenario, sessao: Session
) -> None:
    item = _item_aprovado(cenario, sessao)
    _apontar(cenario, sessao, item)
    visao = _aba(cenario, sessao)

    formulario = service.performance_action_form(
        sessao,
        user=cenario.usuario_membro,
        block=visao.companies[0],
        cut_week=visao.cut_week,
        window_weeks=visao.parameters.window_weeks,
        form=None,
        reference_date=HOJE,
    )

    assert formulario.fields[validation.FIELD_PLAN_COMPANY] == str(cenario.empresa.id)
    assert "Recuperar a produtividade" in formulario.fields[validation.FIELD_PLAN_SUBJECT]
    assert "S39" in formulario.fields[validation.FIELD_PLAN_SUBJECT]
    assert "aderência 25%" in formulario.fields[validation.FIELD_PLAN_DESCRIPTION]
    assert "fator de produtividade 1,20" in formulario.fields[validation.FIELD_PLAN_DESCRIPTION]
    assert formulario.fields[validation.FIELD_PLAN_DATE] == "2026-10-09"
    assert [opcao.id for opcao in formulario.options.companies]
    assert [opcao.id for opcao in formulario.options.people]


def test_o_visualizador_le_mas_nao_grava(cenario: Cenario, sessao: Session) -> None:
    visao = _aba(cenario, sessao, usuario="visualizador")

    assert visao.can_write is False
    with pytest.raises(AccessDeniedError):
        _plano(cenario, sessao, usuario="visualizador")


def test_o_portfolio_traz_uma_linha_por_projeto_e_empresa(
    cenario: Cenario, sessao: Session
) -> None:
    outro = criar_projeto(sessao, codigo="TN-PROD-002", nome="Fábrica 2")
    escopo_outro = Scope(project_id=outro.id, source="url")
    for escopo in (cenario.escopo, escopo_outro):
        item = service.save_item(
            sessao,
            user=cenario.usuario_membro,
            scope=escopo,
            item_id=None,
            form=form_item(cenario),
            reference_date=HOJE,
        )
        service.approve_item(
            sessao,
            user=cenario.usuario_gestor,
            scope=escopo,
            item_id=item.id,
            version=str(item.version),
            reference_date=HOJE,
        )

    carteira = service.performance_overview(
        sessao,
        user=cenario.usuario_membro,
        scope=Scope(project_id=None, source="padrao"),
        reference_date=HOJE,
    )

    assert carteira.is_portfolio
    assert [bloco.project_code for bloco in carteira.companies] == ["TN-PROD-001", "TN-PROD-002"]
    assert all(bloco.project_label for bloco in carteira.companies)
