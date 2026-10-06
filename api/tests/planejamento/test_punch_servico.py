"""Fachada da Punch list (ISSUE-049, HU-068, HU-069): fluxo, evidência, segregação, bloqueio e ação.

O cenário é o do 6WLA com dois sistemas: o membro é o executante (a pessoa responsável pelos
itens) e o admin é o verificador. O dia é parado em 25/09/2026.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import origin_links
from src.core.errors import AccessDeniedError, InvalidDataError, VersionConflictError
from src.core.models import Attachment
from src.core.scope import Scope
from src.modulos.central_acoes import service as central_acoes
from src.modulos.central_acoes.service import OriginChanges
from src.modulos.central_acoes.validation import CompletionRequest
from src.modulos.planejamento import punch_calculations as calc
from src.modulos.planejamento import punch_service as service
from src.modulos.planejamento.models import PunchItem
from src.modulos.planejamento.punch_validation import APPROVED, REJECTED
from tests.apoio_6wla import HOJE, Cadastro
from tests.apoio_punch import (
    CenarioPunch,
    abrir,
    acao_do_item,
    anexar_evidencia,
    campos,
    levar_a_verificacao,
    montar_cenario,
)


@pytest.fixture
def cenario(sessao: Session, cadastro: Cadastro) -> CenarioPunch:
    """O cadastro do 6WLA com a numeração do projeto e dois sistemas."""
    return montar_cenario(sessao, cadastro)


def _verificar(
    session: Session,
    cenario: CenarioPunch,
    item_id: int,
    *,
    result: str,
    version: int,
    **extra: str,
) -> PunchItem:
    return service.verify_item(
        session,
        user=cenario.verificador,
        scope=cenario.escopo,
        request=service.VerificationRequest(
            item_id=item_id, result=result, comment=extra.get("comment", ""), version=str(version)
        ),
        reference_date=HOJE,
    )


# ── Abertura e ação da Central ────────────────────────────────────────────


def test_abrir_numera_pelo_padrao_do_projeto_e_cria_a_acao_na_central(
    sessao: Session, cenario: CenarioPunch
) -> None:
    primeiro = abrir(sessao, cenario)
    segundo = abrir(sessao, cenario, tag="PN-210-02")

    assert primeiro.code == "PL-TN-2026-0001"
    assert segundo.code == "PL-TN-2026-0002"
    assert primeiro.situation == calc.OPEN
    assert primeiro.opened_on == HOJE
    acao = acao_do_item(sessao, primeiro)
    assert acao.planned_date == primeiro.due_date
    assert acao.completed_on is None
    assert "categoria A" in (acao.description or "")
    assert acao.responsible_id == cenario.cadastro.responsavel.id


def test_visualizador_nao_abre_item(sessao: Session, cenario: CenarioPunch) -> None:
    with pytest.raises(AccessDeniedError):
        service.create_item(
            sessao,
            user=cenario.visualizador,
            scope=cenario.escopo,
            data=campos(cenario),
            reference_date=HOJE,
        )


def test_abrir_no_portfolio_pede_o_projeto(sessao: Session, cenario: CenarioPunch) -> None:
    with pytest.raises(InvalidDataError):
        service.create_item(
            sessao,
            user=cenario.executante,
            scope=cenario.portfolio,
            data=campos(cenario),
            reference_date=HOJE,
        )


def test_abrir_com_dados_invalidos_devolve_uma_mensagem_por_campo(
    sessao: Session, cenario: CenarioPunch
) -> None:
    with pytest.raises(InvalidDataError) as erro:
        abrir(sessao, cenario, category="Z", tag="")
    assert set(erro.value.detail) == {"categoria", "tag"}


def test_editar_leva_prazo_e_responsavel_para_a_acao(
    sessao: Session, cenario: CenarioPunch
) -> None:
    item = abrir(sessao, cenario)
    novo_prazo = HOJE + timedelta(days=30)

    service.update_item(
        sessao,
        user=cenario.executante,
        scope=cenario.escopo,
        edit=service.ItemEdit(
            item_id=item.id,
            data=campos(cenario, due_date=novo_prazo, description="Nova descrição"),
            version=str(item.version),
        ),
    )

    acao = acao_do_item(sessao, item)
    assert acao.planned_date == novo_prazo
    assert acao.subject == "Nova descrição"


def test_editar_com_versao_velha_e_conflito(sessao: Session, cenario: CenarioPunch) -> None:
    item = abrir(sessao, cenario)
    versao_da_tela = item.version
    service.start_treatment(
        sessao,
        user=cenario.executante,
        scope=cenario.escopo,
        item_id=item.id,
        version=str(versao_da_tela),
    )
    with pytest.raises(VersionConflictError):
        service.update_item(
            sessao,
            user=cenario.executante,
            scope=cenario.escopo,
            edit=service.ItemEdit(
                item_id=item.id, data=campos(cenario), version=str(versao_da_tela)
            ),
        )


# ── Fluxo, evidência e segregação ─────────────────────────────────────────


def test_fluxo_completo_fecha_o_item_e_conclui_a_acao(
    sessao: Session, cenario: CenarioPunch
) -> None:
    item = abrir(sessao, cenario)
    levar_a_verificacao(sessao, cenario, item)
    assert item.situation == calc.AWAITING_VERIFICATION

    _verificar(sessao, cenario, item.id, result=APPROVED, version=item.version)

    assert item.situation == calc.CLOSED
    assert item.closed_on == HOJE
    assert item.verified_by_id == cenario.cadastro.admin.person_id
    assert acao_do_item(sessao, item).completed_on == HOJE


def test_fechamento_sem_anexo_e_recusado(sessao: Session, cenario: CenarioPunch) -> None:
    item = abrir(sessao, cenario)
    levar_a_verificacao(sessao, cenario, item)
    for anexo in list(sessao.scalars(select(Attachment))):
        sessao.delete(anexo)
    sessao.flush()

    with pytest.raises(InvalidDataError) as erro:
        _verificar(sessao, cenario, item.id, result=APPROVED, version=item.version)

    assert "anexo" in erro.value.detail
    assert item.situation == calc.AWAITING_VERIFICATION


def test_enviar_para_verificacao_sem_anexo_e_recusado(
    sessao: Session, cenario: CenarioPunch
) -> None:
    item = abrir(sessao, cenario)
    service.start_treatment(
        sessao,
        user=cenario.executante,
        scope=cenario.escopo,
        item_id=item.id,
        version=str(item.version),
    )
    with pytest.raises(InvalidDataError) as erro:
        service.submit_for_verification(
            sessao,
            user=cenario.executante,
            scope=cenario.escopo,
            request=service.TreatmentRequest(
                item_id=item.id, comment="Feito.", version=str(item.version)
            ),
        )
    assert "anexo" in erro.value.detail


def test_verificador_igual_ao_executante_recebe_403(sessao: Session, cenario: CenarioPunch) -> None:
    item = abrir(sessao, cenario)
    levar_a_verificacao(sessao, cenario, item)

    with pytest.raises(AccessDeniedError):
        service.verify_item(
            sessao,
            user=cenario.executante,
            scope=cenario.escopo,
            request=service.VerificationRequest(
                item_id=item.id, result=APPROVED, version=str(item.version)
            ),
            reference_date=HOJE,
        )
    assert item.situation == calc.AWAITING_VERIFICATION
    assert acao_do_item(sessao, item).completed_on is None


def test_reprovar_volta_para_tratamento_e_pede_o_motivo(
    sessao: Session, cenario: CenarioPunch
) -> None:
    item = abrir(sessao, cenario)
    levar_a_verificacao(sessao, cenario, item)

    with pytest.raises(InvalidDataError):
        _verificar(sessao, cenario, item.id, result=REJECTED, version=item.version)
    _verificar(
        sessao, cenario, item.id, result=REJECTED, version=item.version, comment="Cabo errado"
    )

    assert item.situation == calc.IN_TREATMENT
    assert item.rejections == 1
    assert item.verification_comment == "Cabo errado"
    assert acao_do_item(sessao, item).completed_on is None


def test_passo_fora_de_ordem_e_recusado(sessao: Session, cenario: CenarioPunch) -> None:
    item = abrir(sessao, cenario)
    with pytest.raises(InvalidDataError):
        _verificar(sessao, cenario, item.id, result=APPROVED, version=item.version)


def test_cancelar_pede_justificativa_e_conclui_a_acao(
    sessao: Session, cenario: CenarioPunch
) -> None:
    item = abrir(sessao, cenario)
    with pytest.raises(InvalidDataError):
        service.cancel_item(
            sessao,
            user=cenario.executante,
            scope=cenario.escopo,
            request=service.CancellationRequest(
                item_id=item.id, justification="curto", version=str(item.version)
            ),
            reference_date=HOJE,
        )

    service.cancel_item(
        sessao,
        user=cenario.executante,
        scope=cenario.escopo,
        request=service.CancellationRequest(
            item_id=item.id, justification="Item duplicado do walkdown", version=str(item.version)
        ),
        reference_date=HOJE,
    )

    assert item.situation == calc.CANCELLED
    assert item.cancellation_reason == "Item duplicado do walkdown"
    assert acao_do_item(sessao, item).completed_on == HOJE


def test_item_fechado_nao_se_edita_nem_se_cancela(sessao: Session, cenario: CenarioPunch) -> None:
    item = abrir(sessao, cenario)
    levar_a_verificacao(sessao, cenario, item)
    _verificar(sessao, cenario, item.id, result=APPROVED, version=item.version)

    with pytest.raises(InvalidDataError):
        service.update_item(
            sessao,
            user=cenario.executante,
            scope=cenario.escopo,
            edit=service.ItemEdit(item_id=item.id, data=campos(cenario), version=str(item.version)),
        )


# ── Bloqueio de sistema e lista ───────────────────────────────────────────


def _board(session: Session, cenario: CenarioPunch, **filters: object) -> service.PunchBoard:
    return service.punch_board(
        session,
        user=cenario.verificador,
        scope=cenario.escopo,
        reference_date=HOJE,
        filters=service.PunchFilter(**filters),
    )


def test_item_a_aberto_bloqueia_o_sistema_para_o_marco_vinculado(
    sessao: Session, cenario: CenarioPunch
) -> None:
    item = abrir(sessao, cenario, milestone="Comissionamento")
    abrir(sessao, cenario, system_id=cenario.outro_sistema.id, category="B")

    board = _board(sessao, cenario)

    assert board.blocked_systems == ("210 Moagem",)
    por_sistema = {row.label: row.blocks for row in board.systems}
    assert por_sistema["210 Moagem"] == (0, 1, 1)
    assert por_sistema["310 Flotação"] == (0, 0, 1)

    levar_a_verificacao(sessao, cenario, item)
    _verificar(sessao, cenario, item.id, result=APPROVED, version=item.version)

    assert _board(sessao, cenario).blocked_systems == ()


def test_a_lista_padrao_mostra_so_os_abertos_e_os_indicadores_contam_tudo(
    sessao: Session, cenario: CenarioPunch
) -> None:
    aberto = abrir(sessao, cenario, due_date=HOJE - timedelta(days=1))
    fechado = abrir(sessao, cenario, category="B", tag="XY-9")
    levar_a_verificacao(sessao, cenario, fechado)
    _verificar(sessao, cenario, fechado.id, result=APPROVED, version=fechado.version)

    board = _board(sessao, cenario)

    assert [row.code for row in board.rows] == [aberto.code]
    assert board.total == 2
    assert board.figures.open == 1
    assert board.figures.open_a == 1
    assert board.figures.overdue == 1
    assert board.figures.closed == 1
    assert board.figures.valid == 2
    assert board.figures.closed_percentage == 50
    assert len(_board(sessao, cenario, situation="").rows) == 2
    assert [row.code for row in _board(sessao, cenario, search="xy-9", situation="").rows] == [
        fechado.code
    ]


def test_o_escopo_de_um_projeto_nao_enxerga_o_outro(sessao: Session, cenario: CenarioPunch) -> None:
    item = abrir(sessao, cenario)
    outro = service.PunchFilter(situation="")
    board = service.punch_board(
        sessao,
        user=cenario.verificador,
        scope=Scope(project_id=cenario.cadastro.outro_projeto.id, source="url"),
        reference_date=HOJE,
        filters=outro,
    )
    assert board.total == 0
    with pytest.raises(InvalidDataError):
        service.find_item(
            sessao,
            user=cenario.verificador,
            scope=Scope(project_id=cenario.cadastro.outro_projeto.id, source="url"),
            item_id=item.id,
            reference_date=HOJE,
        )


# ── Sincronização com a Central, nos dois sentidos ────────────────────────


def test_a_central_recusa_concluir_a_acao_do_item_e_o_item_nao_muda(
    sessao: Session, cenario: CenarioPunch
) -> None:
    item = abrir(sessao, cenario)
    acao = acao_do_item(sessao, item)

    with pytest.raises(InvalidDataError):
        central_acoes.complete_action(
            sessao,
            user=cenario.verificador,
            request=CompletionRequest(
                action_id=acao.id, completed_on=HOJE, version=str(acao.version)
            ),
            reference_date=HOJE,
        )

    assert item.situation == calc.OPEN
    assert acao_do_item(sessao, item).completed_on is None


def test_a_acao_repete_a_situacao_do_item_e_aponta_de_volta_para_ele(
    sessao: Session, cenario: CenarioPunch
) -> None:
    item = abrir(sessao, cenario)
    levar_a_verificacao(sessao, cenario, item)

    assert (acao_do_item(sessao, item).description or "").endswith(calc.AWAITING_VERIFICATION)
    link = origin_links.resolve("Punch list", item.code)
    assert link.url == f"/planejamento/punch-list?item={item.code}"


def test_atualizar_a_acao_pela_origem_so_mexe_nos_campos_repetidos(
    sessao: Session, cenario: CenarioPunch
) -> None:
    item = abrir(sessao, cenario)
    mudados = central_acoes.update_from_origin(
        sessao,
        user=cenario.executante,
        origin=origin_links.OriginRef(kind="Punch list", reference=item.code),
        changes=OriginChanges(
            subject="Outro assunto",
            description=None,
            group="Grupo",
            requester_id=cenario.cadastro.admin.person_id,
            responsible_id=cenario.cadastro.responsavel.id,
            planned_date=HOJE + timedelta(days=3),
        ),
    )
    assert mudados == 1
    assert acao_do_item(sessao, item).group == "Grupo"


def test_anexar_evidencia_nao_fecha_o_item(sessao: Session, cenario: CenarioPunch) -> None:
    item = abrir(sessao, cenario)
    anexar_evidencia(sessao, cenario, item)
    assert item.situation == calc.OPEN
