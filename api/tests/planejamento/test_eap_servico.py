"""Fachada da EAP (ISSUE-036, D5, D6, D8): o real pelo critério, a árvore, o escopo e o dicionário.

O cenário vem de ``apoio_eap`` (os números esperados estão no comentário de lá); a data de hoje
é injetada (25/09/2026). O real de nenhum pacote é gravado: ele sai da última medição.
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.models import AuditEntry
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.planejamento import eap_calculations as calc
from src.modulos.planejamento import eap_service as service
from src.modulos.planejamento.eap_calculations import TreeRow
from src.modulos.planejamento.eap_service import EapFilters, EapView
from src.modulos.planejamento.models import EapItem
from tests.apoio_eap import HOJE, EapCadastro, montar_eap

D = Decimal


@pytest.fixture
def eap(db_session: Session) -> EapCadastro:
    return montar_eap(db_session)


def _scope(project_id: int | None) -> Scope:
    return Scope(project_id=project_id, source="url")


def _view(
    eap: EapCadastro,
    project_id: int | None,
    *,
    filters: EapFilters | None = None,
    reference_date: date = HOJE,
) -> EapView:
    return service.eap_view(
        eap.session,
        user=eap.member,
        scope=_scope(project_id),
        filters=filters or EapFilters(),
        reference_date=reference_date,
    )


def _rows(view: EapView) -> dict[str, TreeRow]:
    return {row.code: row for row in view.rows}


# ── O real sai da última medição pelo critério ───────────────────────────


def test_o_real_de_cada_pacote_sai_da_ultima_medicao_pelo_criterio(eap: EapCadastro) -> None:
    rows = _rows(_view(eap, eap.first.id))

    assert rows["1.1.1"].real == D("50.00")  # Unidades: 50 de 100 m³
    assert rows["1.1.2"].real == D("100.00")  # Marco 0/100 concluído
    assert rows["1.1.3"].real == D("40.00")  # Etapas: a primeira etapa (40) concluída
    assert rows["2.1.1"].real == 0  # planejamento não mede


def test_unidades_mostra_a_quantidade_executada_derivada_da_medicao(eap: EapCadastro) -> None:
    rows = _rows(_view(eap, eap.first.id))

    assert rows["1.1.1"].executed == D("50.00")
    assert rows["1.1.1"].quantity == D(100)
    assert rows["1.1.1"].unit == "m³"
    assert rows["1.1.2"].executed is None


def test_pacote_sem_medicao_tem_real_zero_e_desvio_negativo(eap: EapCadastro) -> None:
    rows = _rows(_view(eap, eap.second.id))

    assert rows["1.1.1"].real == 0
    assert rows["1.1.1"].deviation == D("-50.0")
    assert rows["1.1.1"].band == calc.DANGER


def test_a_ultima_medicao_vale_pela_data_e_nao_pela_ordem_de_gravacao(eap: EapCadastro) -> None:
    item_id = eap.item(eap.first, "1.1.3")
    service.add_measurement(
        eap.session,
        user_id=eap.member.id,
        new=service.NewMeasurement(
            item_id=item_id,
            measured_on=date(2026, 9, 1),
            from_percent=D(0),
            to_percent=D(90),
        ),
    )

    assert _rows(_view(eap, eap.first.id))["1.1.3"].real == D("40.00")


def test_medicao_nova_com_data_posterior_muda_o_real(eap: EapCadastro) -> None:
    item_id = eap.item(eap.first, "1.1.3")
    service.add_measurement(
        eap.session,
        user_id=eap.member.id,
        new=service.NewMeasurement(
            item_id=item_id,
            measured_on=date(2026, 9, 24),
            from_percent=D(40),
            to_percent=D(70),
        ),
    )

    assert _rows(_view(eap, eap.first.id))["1.1.3"].real == D("70.00")


# ── A árvore e os totais ─────────────────────────────────────────────────


def test_a_arvore_do_projeto_tem_a_linha_zero_e_os_codigos_em_ordem(eap: EapCadastro) -> None:
    view = _view(eap, eap.first.id)

    assert [row.code for row in view.rows] == [
        "0", "1", "1.1", "1.1.1", "1.1.2", "1.1.3", "2", "2.1", "2.1.1",
    ]  # fmt: skip
    assert view.scope_label == "TN-EAP-001 · Fábrica EAP"
    assert not view.is_portfolio
    assert view.max_level == 3


def test_areas_subareas_e_projeto_somam_pesos_e_ponderam_o_avanco(eap: EapCadastro) -> None:
    rows = _rows(_view(eap, eap.first.id))

    assert rows["0"].weight == D(100)
    assert (rows["0"].planned, rows["0"].real, rows["0"].deviation) == (
        D("62.00"),
        D("59.00"),
        D("-3.0"),
    )
    assert rows["1.1"].weight == D(90)
    assert (rows["1.1"].planned, rows["1.1"].real) == (D("68.89"), D("65.56"))
    assert rows["2.1"].weight == D(10)
    assert rows["0"].responsible is not None


def test_o_dicionario_chega_na_linha_com_empresa_responsavel_e_item_da_eac(
    eap: EapCadastro,
) -> None:
    row = _rows(_view(eap, eap.first.id))["1.1.1"]

    assert row.company == "Montadora EAP"
    assert row.responsible == "Maria Membro"
    assert row.eac_code is None


def test_indicadores_do_projeto(eap: EapCadastro) -> None:
    summary = _view(eap, eap.first.id).summary

    assert (summary.work_count, summary.planning_count) == (3, 1)
    assert summary.planning_weight == D(10)
    assert (summary.area_count, summary.subarea_count) == (2, 2)
    assert summary.overdue_count == 1  # 1.1.1: término em 01/09 e real 50
    assert summary.behind_count == 1  # 1.1.1: desvio -10,0
    assert summary.band == calc.WARNING


def test_a_regra_dos_100_confere_e_avisa_quando_nao_fecha(eap: EapCadastro) -> None:
    assert _view(eap, eap.first.id).weight_rule_holds

    item = eap.session.get(EapItem, eap.item(eap.first, "1.1.1"))
    assert item is not None
    item.weight = D("49.99")
    eap.session.flush()
    view = _view(eap, eap.first.id)

    assert not view.weight_rule_holds
    assert view.summary.weight_total == D("99.99")


def test_projeto_sem_eap_e_vazio_de_origem(eap: EapCadastro) -> None:
    eap.session.query(EapItem).filter(EapItem.project_id == eap.second.id).delete()

    view = _view(eap, eap.second.id)

    assert view.is_empty
    assert not view.has_no_match


# ── Desvio com as faixas dos parâmetros ──────────────────────────────────


def test_as_faixas_do_desvio_vem_dos_parametros_em_vigor(eap: EapCadastro) -> None:
    assert _view(eap, eap.first.id).bands == (D(2), D(5))
    values = deepcopy(configuracoes.INITIAL_PARAMETERS["eap"])
    values["faixasDesvioPP"] = [3, 6]
    configuracoes.save_parameter_group(
        eap.session,
        author_id=eap.member.id,
        group="eap",
        values=values,
        effective_from=HOJE,
        justification="Faixas mais largas para o teste.",
    )

    view = _view(eap, eap.first.id)

    assert view.bands == (D(3), D(6))
    assert _rows(view)["0"].band == calc.OK  # -3,0 cabe na faixa de 3 p.p.
    assert _rows(view)["1.1.1"].band == calc.DANGER  # -10,0 passa de 6 p.p.


# ── Filtros ──────────────────────────────────────────────────────────────


def _codes(view: EapView) -> list[str]:
    return [row.code for row in view.rows]


def test_busca_e_nivel_filtram_a_arvore_mas_nao_os_indicadores(eap: EapCadastro) -> None:
    view = _view(eap, eap.first.id, filters=EapFilters(search="licenca", level=3))

    assert _codes(view) == ["0", "1", "1.1", "1.1.2"]
    assert view.summary.work_count == 3
    assert _codes(_view(eap, eap.first.id, filters=EapFilters(level=1))) == ["0", "1", "2"]


def test_filtro_de_criterio_e_de_situacao(eap: EapCadastro) -> None:
    by_criterion = _view(eap, eap.first.id, filters=EapFilters(criterion=calc.STAGES))
    overdue = _view(eap, eap.first.id, filters=EapFilters(situation=calc.SITUATION_OVERDUE))
    planning = _view(eap, eap.first.id, filters=EapFilters(situation=calc.SITUATION_PLANNING))

    assert _codes(by_criterion) == ["0", "1", "1.1", "1.1.3"]
    assert _codes(overdue) == ["0", "1", "1.1", "1.1.1"]
    assert _codes(planning) == ["0", "2", "2.1", "2.1.1"]


def test_filtro_sem_resultado_e_vazio_por_filtro_e_o_nivel_fica_no_limite(
    eap: EapCadastro,
) -> None:
    view = _view(eap, eap.first.id, filters=EapFilters(search="zzz", level=9))

    assert view.has_no_match
    assert view.filters.level == 3
    assert view.filters.is_active


# ── Portfólio: somente leitura, projeto e pacotes principais ─────────────


def test_portfolio_traz_projeto_e_pacote_principal_com_o_peso_da_carteira(
    eap: EapCadastro,
) -> None:
    view = _view(eap, None)

    assert view.is_portfolio
    assert view.max_level == 2
    assert [row.code for row in view.rows] == ["0", "1", "1.1", "1.2", "2", "2.1"]
    rows = _rows(view)
    assert rows["1"].weight == D("50.00")  # sem orçamento nas EAC, a carteira reparte igual
    assert rows["1.1"].weight == D("45.00")
    assert rows["1.2"].weight == D("5.00")
    assert rows["2.1"].weight == D("50.00")
    assert rows["1"].description == "TN-EAP-001 · Fábrica EAP"


def test_portfolio_pondera_o_avanco_e_soma_os_pacotes_dos_projetos(eap: EapCadastro) -> None:
    view = _view(eap, None)
    root = _rows(view)["0"]

    assert (root.planned, root.real, root.deviation) == (D("56.00"), D("29.50"), D("-26.5"))
    assert root.band == calc.DANGER
    assert view.summary.project_count == 2
    assert view.summary.work_count == 4
    assert view.summary.overdue_count == 1
    assert view.summary.behind_count == 2  # 1.1.1 do projeto A e 1.1.1 do projeto B


def test_portfolio_lista_so_a_revisao_vigente_de_cada_projeto_e_nenhum_desdobramento(
    eap: EapCadastro,
) -> None:
    view = _view(eap, None)

    assert [(item.project_label[:10], item.number) for item in view.revisions] == [
        ("TN-EAP-001", 1),
        ("TN-EAP-002", 0),
    ]
    assert all(item.is_current for item in view.revisions)
    assert view.splits == ()


def test_projeto_do_escopo_que_nao_existe_e_422(eap: EapCadastro) -> None:
    with pytest.raises(InvalidDataError):
        _view(eap, 999_999_999)


# ── Revisões e desdobramentos ────────────────────────────────────────────


def test_revisoes_do_projeto_a_mais_nova_primeiro_e_a_vigente_marcada(eap: EapCadastro) -> None:
    view = _view(eap, eap.first.id)

    assert [(item.number, item.is_current) for item in view.revisions] == [(1, True), (0, False)]
    assert view.current_revision is not None
    assert view.current_revision.number == 1


def test_a_contagem_de_pacotes_vem_dos_pesos_congelados(eap: EapCadastro) -> None:
    revisions = {item.number: item for item in _view(eap, eap.first.id).revisions}

    assert revisions[1].package_count == 4
    assert revisions[0].package_count is None  # sem pesos congelados, sem contagem inventada


def test_desdobramentos_da_revisao_vigente(eap: EapCadastro) -> None:
    splits = _view(eap, eap.first.id).splits

    assert len(splits) == 1
    assert splits[0].source == "2.1.1 Comissionamento a detalhar"
    assert splits[0].target == "1.1.3 Projeto de processo"
    assert splits[0].weight == D("0.8")
    assert splits[0].justification == "Plano detalhado."


# ── Dicionário do pacote ─────────────────────────────────────────────────


def _dictionary(
    eap: EapCadastro, code: str, *, project_id: int | None = None, project_code: str = "first"
) -> service.PackageDictionary:
    project = eap.first if project_code == "first" else eap.second
    return service.package_dictionary(
        eap.session,
        user=eap.member,
        scope=_scope(project.id if project_id is None else project_id),
        item_id=eap.item(project, code),
        reference_date=HOJE,
    )


def test_dicionario_traz_entregavel_aceitacao_empresa_responsavel_e_medicoes(
    eap: EapCadastro,
) -> None:
    dictionary = _dictionary(eap, "1.1.3")

    assert dictionary.deliverable == "Entregável de teste"
    assert dictionary.acceptance == "Aceite de teste"
    assert dictionary.row.company == "Montadora EAP"
    assert dictionary.row.responsible == "Maria Membro"
    assert dictionary.stage_model == "Engenharia (documentos)"
    assert [(item.measured_on, item.to_percent) for item in dictionary.measurements] == [
        (date(2026, 9, 20), D("40.00")),
        (date(2026, 9, 10), D("20.00")),
    ]
    assert dictionary.measurements[0].author == "Maria Membro"


def test_dicionario_das_etapas_mostra_o_concluido_de_cada_uma(eap: EapCadastro) -> None:
    stages = _dictionary(eap, "1.1.3").stages

    assert [(stage.name, stage.weight, stage.percent) for stage in stages] == [
        ("Elaboração", D(40), D(100)),
        ("Emissão para comentários", D(30), D(0)),
        ("Emissão", D(30), D(0)),
    ]


def test_dicionario_de_criterio_sem_etapas_nao_traz_etapas(eap: EapCadastro) -> None:
    assert _dictionary(eap, "1.1.1").stages == ()


@pytest.mark.parametrize(
    "check",
    [
        pytest.param(
            lambda eap: service.package_dictionary(
                eap.session,
                user=eap.member,
                scope=_scope(None),
                item_id=eap.item(eap.first, "1.1.1"),
                reference_date=HOJE,
            ),
            id="portfolio",
        ),
        pytest.param(
            lambda eap: service.package_dictionary(
                eap.session,
                user=eap.member,
                scope=_scope(eap.second.id),
                item_id=eap.item(eap.first, "1.1.1"),
                reference_date=HOJE,
            ),
            id="outro-projeto",
        ),
    ],
)
def test_dicionario_no_portfolio_ou_de_outro_projeto_e_403(
    eap: EapCadastro, check: Callable[[EapCadastro], object]
) -> None:
    with pytest.raises(AccessDeniedError):
        check(eap)


def test_dicionario_de_area_ou_de_item_que_nao_existe_e_422(eap: EapCadastro) -> None:
    with pytest.raises(InvalidDataError):
        _dictionary(eap, "1.1")
    with pytest.raises(InvalidDataError):
        service.package_dictionary(
            eap.session,
            user=eap.member,
            scope=_scope(eap.first.id),
            item_id=999_999_999,
            reference_date=HOJE,
        )


# ── Perfis e trilha ──────────────────────────────────────────────────────


def test_visualizador_le_a_eap(eap: EapCadastro) -> None:
    view = service.eap_view(
        eap.session,
        user=eap.viewer,
        scope=_scope(eap.first.id),
        filters=EapFilters(),
        reference_date=HOJE,
    )

    assert len(view.rows) == 9


def test_fornecedor_nao_alcanca_o_modulo(eap: EapCadastro) -> None:
    with pytest.raises(AccessDeniedError):
        service.eap_view(
            eap.session,
            user=eap.supplier,
            scope=_scope(eap.first.id),
            filters=EapFilters(),
            reference_date=HOJE,
        )


def test_a_carga_deixa_a_trilha_de_cada_registro(eap: EapCadastro) -> None:
    def trail(entity: str) -> int:
        return (
            eap.session.scalar(
                select(func.count()).select_from(AuditEntry).where(AuditEntry.entity == entity)
            )
            or 0
        )

    assert trail("eap_item") == 4 + 4 + 3  # áreas, subáreas e pacotes dos dois projetos
    assert trail("eap_medicao") == 4
    assert trail("eap_item_etapa") == 3
    assert trail("eap_revisao") == 3
    assert trail("eap_revisao_item") == 5
    assert trail("eap_desdobramento") == 1
    assert service.package_count(eap.session, project_id=eap.first.id) == 4
