"""As fachadas do plano de compras (ISSUE-058): leitura, vínculo, folga, congelamento e trilha.

A leitura usa o escopo do projeto e o Portfólio; a gravação passa pela fachada, com a trilha e a
versão. O saldo a comprometer vem da EAC pela fachada do Financeiro (D9); a LB congela a partir
da requisição com data real e a mudança permitida exige justificativa.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.errors import AccessDeniedError, InvalidDataError, VersionConflictError
from src.core.models import AuditEntry
from src.core.scope import Scope
from src.modulos.financeiro.models import EacItem
from src.modulos.suprimentos import calculations, service, validation
from src.modulos.suprimentos.models import PackageMilestone, PurchasePackage
from tests.apoio_pacotes import (
    ITEM_CODE,
    ITEM_COMMITTED_CENTS,
    ITEM_DESCRIPTION,
    PACKAGE_CODE,
    REFERENCIA,
    SUBPACKAGE_CODE,
    CenarioPlano,
    montar_cenario_do_plano,
    novo_pacote,
)


@pytest.fixture
def cenario(sessao: Session) -> CenarioPlano:
    """O cenário do plano no lugar do cenário de fornecedores do conftest."""
    return montar_cenario_do_plano(sessao)


def _scope(cenario: CenarioPlano, *, portfolio: bool = False) -> Scope:
    return Scope(project_id=None if portfolio else cenario.projeto.id, source="url")


def _listar(
    sessao: Session, cenario: CenarioPlano, *, user=None, portfolio: bool = False, **filtros
):
    return service.list_packages(
        sessao,
        user=user or cenario.ana,
        scope=_scope(cenario, portfolio=portfolio),
        filters=validation.PackageFilters(**filtros),  # type: ignore[arg-type]
        reference_date=REFERENCIA,
    )


def _criar(sessao: Session, cenario: CenarioPlano, **campos: object):
    return service.create_package(
        sessao,
        user=cenario.ana,
        project_id=cenario.projeto.id,
        data=novo_pacote(cenario, **campos),
        reference_date=REFERENCIA,
    )


def _historico(sessao: Session, pacote_id: int) -> list[dict[str, object]]:
    statement = (
        select(AuditEntry)
        .where(
            AuditEntry.entity == service.HISTORY_ENTITY,
            AuditEntry.record_id == pacote_id,
        )
        .order_by(AuditEntry.id)
    )
    return [entry.after or {} for entry in sessao.scalars(statement)]


# ── Leitura ──────────────────────────────────────────────────────────────────


def test_a_lista_traz_o_pacote_com_etapa_folga_e_desvio(
    sessao: Session, cenario: CenarioPlano
) -> None:
    listagem = _listar(sessao, cenario)

    assert listagem.total == 1
    linha = listagem.lines[0]
    assert linha.code == PACKAGE_CODE
    assert linha.scope == "Compressores de ar"
    assert linha.kind == "Equipamento"
    assert linha.eac_code == ITEM_CODE
    assert linha.eac_description == ITEM_DESCRIPTION
    assert linha.buyer == "Ana Admin"
    assert linha.discipline == "Mecânica de teste"
    assert linha.frozen is True
    assert linha.stage == "Requisição"
    assert linha.slack_days == 190
    assert linha.adjudication_deviation_days == 5
    assert linha.adjudication_overdue is True
    assert linha.adjudicated_cents is None, "o processo de compra (ISSUE-059) ainda não existe"
    assert linha.supplier is None and linha.saving_cents is None


def test_o_resumo_conta_o_universo_e_nao_o_filtro(sessao: Session, cenario: CenarioPlano) -> None:
    listagem = _listar(sessao, cenario, search="nada-encontra")

    assert listagem.total == 0
    assert listagem.summary.packages == 1
    assert listagem.summary.estimated_cents == 50_000_000
    assert listagem.summary.with_baseline == 1
    assert listagem.summary.forecast_until_reference == 1
    assert listagem.summary.overdue == 1
    assert listagem.summary.lli == 0 and listagem.summary.lli_critical == 0
    assert listagem.summary.adjudicated is None and listagem.summary.saving_cents is None


def test_o_escopo_do_projeto_enxerga_so_os_pacotes_dele(
    sessao: Session, cenario: CenarioPlano
) -> None:
    _criar_em_outro_projeto(sessao, cenario)

    no_projeto = _listar(sessao, cenario)
    na_carteira = _listar(sessao, cenario, portfolio=True)

    assert [line.code for line in no_projeto.lines] == [PACKAGE_CODE]
    assert [line.code for line in na_carteira.lines] == [PACKAGE_CODE, "PC-01"]
    assert na_carteira.lines[1].project_label.startswith("TN-PLA-002")
    assert na_carteira.lines[0].project_label.startswith("TN-PLA-001")


def test_o_visualizador_le_e_nao_grava(sessao: Session, cenario: CenarioPlano) -> None:
    assert _listar(sessao, cenario, user=cenario.vitor).total == 1

    with pytest.raises(AccessDeniedError):
        service.create_package(
            sessao,
            user=cenario.vitor,
            project_id=cenario.projeto.id,
            data=novo_pacote(cenario),
            reference_date=REFERENCIA,
        )


def test_o_pacote_fora_do_escopo_nao_e_encontrado(sessao: Session, cenario: CenarioPlano) -> None:
    assert (
        service.find_package(
            sessao,
            user=cenario.ana,
            scope=_scope(cenario, portfolio=True),
            package_id=cenario.pacote.id,
            reference_date=REFERENCIA,
        )
        is not None
    )
    assert (
        service.find_package(
            sessao,
            user=cenario.ana,
            scope=Scope(project_id=cenario.outro.id, source="url"),
            package_id=cenario.pacote.id,
            reference_date=REFERENCIA,
        )
        is None
    )


def test_as_opcoes_trazem_o_saldo_a_comprometer_do_item_nivel_3(
    sessao: Session, cenario: CenarioPlano
) -> None:
    options = service.package_options(
        sessao, user=cenario.ana, project_id=cenario.projeto.id, reference_date=REFERENCIA
    )

    por_codigo = options.eac_items_by_code
    assert por_codigo[ITEM_CODE].saldo_cents == 100_000_000 - ITEM_COMMITTED_CENTS
    assert por_codigo[ITEM_CODE].description == ITEM_DESCRIPTION
    assert SUBPACKAGE_CODE not in por_codigo, "o subpacote (nível 2) não é item de custo"
    assert [choice.name for choice in options.disciplines] == ["Mecânica de teste"]
    assert any(choice.id == cenario.ana.person_id for choice in options.buyers)


# ── Gravação ─────────────────────────────────────────────────────────────────


def test_o_pacote_nasce_com_o_codigo_o_plano_derivado_e_a_trilha(
    sessao: Session, cenario: CenarioPlano
) -> None:
    resultado = _criar(sessao, cenario)

    pacote = sessao.get(PurchasePackage, resultado.package_id)
    assert resultado.created is True
    assert pacote is not None
    assert resultado.code == "PC-02"
    marcos = sessao.scalars(
        select(PackageMilestone)
        .where(PackageMilestone.package_id == pacote.id)
        .order_by(PackageMilestone.id)
    ).all()
    assert [row.milestone for row in marcos] == list(calculations.MILESTONE_KEYS)
    assert [row.plan_date for row in marcos] == list(
        calculations.derived_plan_dates(
            requisition=date(2026, 10, 1),
            rfx=date(2026, 10, 15),
            adjudication=date(2026, 11, 20),
            order=date(2026, 11, 25),
        ).values()
    )
    assert all(row.real_date is None and row.forecast_date is None for row in marcos)
    historico = _historico(sessao, pacote.id)
    assert historico[-1]["campos"] == ["criacao"]
    assert historico[-1]["justificativa"] == service.INCLUSION_NOTE


def test_o_gate_lli_e_a_emergencia_ficam_na_linha_e_na_trilha(
    sessao: Session, cenario: CenarioPlano
) -> None:
    resultado = _criar(
        sessao,
        cenario,
        lli=True,
        anticipated_fid=True,
        gate_reference="Ata do comitê de investimentos",
        emergency=True,
        emergency_justification="Parada de produção exige a reposição imediata do equipamento.",
    )

    pacote = sessao.get(PurchasePackage, resultado.package_id)
    assert pacote is not None
    assert pacote.gate_lli_date == REFERENCIA
    assert pacote.gate_lli_reference == "Ata do comitê de investimentos"
    assert pacote.emergency is True
    historico = _historico(sessao, pacote.id)
    assert historico[-1]["justificativa_emergencial"] == (
        "Parada de produção exige a reposição imediata do equipamento."
    )


def test_o_pacote_sem_item_de_nivel_3_e_recusado(sessao: Session, cenario: CenarioPlano) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        _criar(sessao, cenario, eac_code=SUBPACKAGE_CODE)

    mensagens = recusa.value.messages()
    assert any(SUBPACKAGE_CODE in mensagem for mensagem in mensagens)
    assert (
        sessao.scalars(select(PurchasePackage).where(PurchasePackage.code == "PC-02")).first()
        is None
    )


def test_o_plano_nao_nasce_com_folga_negativa(sessao: Session, cenario: CenarioPlano) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        _criar(sessao, cenario, order=date(2027, 3, 31), ros=date(2027, 3, 30))

    assert any("folga negativa" in mensagem for mensagem in recusa.value.messages())


def test_as_datas_fora_de_ordem_sao_recusadas(sessao: Session, cenario: CenarioPlano) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        _criar(sessao, cenario, rfx=date(2026, 9, 30))

    assert any("crescentes" in mensagem for mensagem in recusa.value.messages())


def test_a_emergencia_sem_justificativa_e_recusada(sessao: Session, cenario: CenarioPlano) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        _criar(sessao, cenario, emergency=True, emergency_justification="urgente")

    assert any("emergencial" in mensagem for mensagem in recusa.value.messages())


def test_o_lli_antecipado_sem_o_gate_e_recusado(sessao: Session, cenario: CenarioPlano) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        _criar(sessao, cenario, lli=True, anticipated_fid=True)

    assert any("gate LLI" in mensagem for mensagem in recusa.value.messages())


def test_a_edicao_completa_muda_o_plano_antes_da_requisicao(
    sessao: Session, cenario: CenarioPlano
) -> None:
    resultado = _criar(sessao, cenario)
    linha = service.find_package(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        package_id=resultado.package_id,
        reference_date=REFERENCIA,
    )
    assert linha is not None

    service.update_package(
        sessao,
        user=cenario.ana,
        package_id=resultado.package_id,
        data=novo_pacote(
            cenario,
            scope="Compressores de ar revisados",
            order=date(2026, 12, 1),
            version=linha.version,
        ),
        reference_date=REFERENCIA,
    )

    pacote = sessao.get(PurchasePackage, resultado.package_id)
    assert pacote is not None and pacote.scope == "Compressores de ar revisados"
    pedido = sessao.scalars(
        select(PackageMilestone).where(
            PackageMilestone.package_id == pacote.id, PackageMilestone.milestone == "pedido"
        )
    ).one()
    assert pedido.plan_date == date(2026, 12, 1)
    assert pacote.version == linha.version + 1


def test_a_edicao_completa_de_pacote_congelado_e_recusada(
    sessao: Session, cenario: CenarioPlano
) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        service.update_package(
            sessao,
            user=cenario.ana,
            package_id=cenario.pacote.id,
            data=novo_pacote(cenario, version=cenario.pacote.version),
            reference_date=REFERENCIA,
        )

    assert any("congelada" in mensagem for mensagem in recusa.value.messages())


def test_a_mudanca_pos_requisicao_exige_justificativa(
    sessao: Session, cenario: CenarioPlano
) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        service.change_package(
            sessao,
            user=cenario.ana,
            package_id=cenario.pacote.id,
            data=validation.PackageChangeInput(
                scope="Compressores de ar revisados",
                buyer_id=cenario.ana.person_id,
                estimate_cents=45_000_000,
                ros=date(2027, 4, 15),
                justification="curta",
                version=cenario.pacote.version,
            ),
            reference_date=REFERENCIA,
        )

    assert any("Justifique" in mensagem for mensagem in recusa.value.messages())
    sessao.refresh(cenario.pacote)
    assert cenario.pacote.scope == "Compressores de ar"


def test_a_mudanca_pos_requisicao_grava_os_campos_permitidos_e_a_trilha(
    sessao: Session, cenario: CenarioPlano
) -> None:
    service.change_package(
        sessao,
        user=cenario.ana,
        package_id=cenario.pacote.id,
        data=validation.PackageChangeInput(
            scope="Compressores de ar revisados",
            buyer_id=cenario.ana.person_id,
            estimate_cents=45_000_000,
            ros=date(2027, 4, 15),
            justification="O ROS mudou com o cronograma e a estimativa foi ajustada.",
            version=cenario.pacote.version,
        ),
        reference_date=REFERENCIA,
    )

    sessao.refresh(cenario.pacote)
    assert cenario.pacote.scope == "Compressores de ar revisados"
    assert cenario.pacote.estimate_cents == 45_000_000
    assert cenario.pacote.ros == date(2027, 4, 15)
    assert cenario.pacote.version == 2
    historico = _historico(sessao, cenario.pacote.id)
    assert historico[-1]["campos"] == ["escopo", "estimativa", "ros"]
    assert historico[-1]["justificativa"] == (
        "O ROS mudou com o cronograma e a estimativa foi ajustada."
    )


def test_a_mudanca_sem_alteracao_nao_grava(sessao: Session, cenario: CenarioPlano) -> None:
    resultado = service.change_package(
        sessao,
        user=cenario.ana,
        package_id=cenario.pacote.id,
        data=validation.PackageChangeInput(
            scope=cenario.pacote.scope,
            buyer_id=cenario.pacote.buyer_id,
            estimate_cents=cenario.pacote.estimate_cents,
            ros=cenario.pacote.ros,
            justification="",
            version=cenario.pacote.version,
        ),
        reference_date=REFERENCIA,
    )

    sessao.refresh(cenario.pacote)
    assert resultado.created is False
    assert cenario.pacote.version == 1
    assert _historico(sessao, cenario.pacote.id) == []


def test_a_mudanca_em_pacote_sem_requisicao_real_e_recusada(
    sessao: Session, cenario: CenarioPlano
) -> None:
    resultado = _criar(sessao, cenario)

    with pytest.raises(InvalidDataError) as recusa:
        service.change_package(
            sessao,
            user=cenario.ana,
            package_id=resultado.package_id,
            data=validation.PackageChangeInput(
                scope="Outro escopo",
                buyer_id=cenario.ana.person_id,
                estimate_cents=10_000_000,
                ros=date(2027, 5, 1),
                justification="Tentativa de mudar antes da requisição.",
                version=1,
            ),
            reference_date=REFERENCIA,
        )

    assert any("editável" in mensagem for mensagem in recusa.value.messages())


def test_a_versao_antiga_da_mudanca_e_recusada(sessao: Session, cenario: CenarioPlano) -> None:
    with pytest.raises(VersionConflictError):
        service.change_package(
            sessao,
            user=cenario.ana,
            package_id=cenario.pacote.id,
            data=validation.PackageChangeInput(
                scope="Outro escopo",
                buyer_id=cenario.ana.person_id,
                estimate_cents=10_000_000,
                ros=date(2027, 5, 1),
                justification="Mudança com versão antiga da tela.",
                version=cenario.pacote.version + 5,
            ),
            reference_date=REFERENCIA,
        )


def test_o_item_da_eac_do_pacote_aponta_para_o_item_do_projeto(
    sessao: Session, cenario: CenarioPlano
) -> None:
    linha = _listar(sessao, cenario).lines[0]
    item = sessao.get(EacItem, linha.eac_item_id)
    assert item is not None
    assert (item.code, item.level) == (ITEM_CODE, 3)


def _criar_em_outro_projeto(sessao: Session, cenario: CenarioPlano) -> None:
    """Um pacote no outro projeto, com um item de custo próprio: o Portfólio soma os dois."""
    item = EacItem(
        project_id=cenario.outro.id, code=ITEM_CODE, description=ITEM_DESCRIPTION, level=3
    )
    sessao.add(item)
    sessao.flush()
    service.create_package(
        sessao,
        user=cenario.ana,
        project_id=cenario.outro.id,
        data=novo_pacote(cenario, eac_code=ITEM_CODE),
        reference_date=REFERENCIA,
    )
