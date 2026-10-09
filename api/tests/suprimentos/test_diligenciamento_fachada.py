"""As fachadas do diligenciamento (ISSUE-061): marcos, recebimento, importação e ação.

O cenário tem um pedido emitido com os seis marcos de fabricação, na transação do teste: a
realização com o marco anterior e a data até a referência, a previsão fora do passado com a
cascata, o recebimento exigindo o embarque e gravando a evidência (D5a), a importação do ERP
linha a linha e a ação de diligenciamento que nunca duplica. O Visualizador recebe 403.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import importing
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.models import AuditEntry
from src.core.scope import Scope
from src.modulos.central_acoes.models import Action
from src.modulos.suprimentos import service, validation
from src.modulos.suprimentos.models import (
    DeliveryReceipt,
    PurchaseOrder,
    PurchaseOrderMilestone,
)
from tests.apoio_diligenciamento import (
    CONTRACTUAL,
    CRITICAL_ROS,
    EMISSION,
    REFERENCIA,
    ROS,
    CenarioDiligenciamento,
    montar_cenario_diligenciamento,
    tornar_critico,
)
from tests.armazenamento_falso import ArmazenamentoEmMemoria

ENTREGA = date(2026, 9, 25)
EMBARQUE = date(2026, 9, 24)


@pytest.fixture
def cenario(sessao: Session) -> CenarioDiligenciamento:
    """O pedido do cenário com os seis marcos de fabricação, na sessão do teste."""
    return montar_cenario_diligenciamento(sessao)


def _scope(cenario: CenarioDiligenciamento, *, portfolio: bool = False) -> Scope:
    return Scope(project_id=None if portfolio else cenario.projeto.id, source="url")


def _linha(sessao: Session, cenario: CenarioDiligenciamento) -> service.OrderLine:
    line = service.find_order(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        order_id=cenario.pedido.id,
        reference_date=REFERENCIA,
    )
    assert line is not None
    return line


def _realizar(
    sessao: Session,
    cenario: CenarioDiligenciamento,
    position: int,
    quando: date,
) -> service.OrderSave:
    return service.update_order_milestone(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        order_id=cenario.pedido.id,
        data=validation.MilestoneInput(
            index=position, kind=validation.MILESTONE_DONE, realized=quando
        ),
        reference_date=REFERENCIA,
    )


def _prever(
    sessao: Session,
    cenario: CenarioDiligenciamento,
    position: int,
    quando: date,
    *,
    cascade: bool = True,
) -> service.OrderSave:
    return service.update_order_milestone(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        order_id=cenario.pedido.id,
        data=validation.MilestoneInput(
            index=position,
            kind=validation.MILESTONE_FORECAST,
            forecast=quando,
            cascade=cascade,
        ),
        reference_date=REFERENCIA,
    )


def _milestones(sessao: Session, cenario: CenarioDiligenciamento) -> list[PurchaseOrderMilestone]:
    return list(
        sessao.scalars(
            select(PurchaseOrderMilestone)
            .where(PurchaseOrderMilestone.order_id == cenario.pedido.id)
            .order_by(PurchaseOrderMilestone.position)
        )
    )


def _historico(sessao: Session, cenario: CenarioDiligenciamento) -> list[dict[str, object]]:
    statement = (
        select(AuditEntry)
        .where(
            AuditEntry.entity == service.ORDER_HISTORY_ENTITY,
            AuditEntry.record_id == cenario.pedido.id,
        )
        .order_by(AuditEntry.id)
    )
    return [entry.after or {} for entry in sessao.scalars(statement)]


# ── Leitura ──────────────────────────────────────────────────────────────────────────────────


def test_a_leitura_calcula_a_folga_o_proximo_marco_e_a_situacao(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    linha = _linha(sessao, cenario)

    assert linha.slack_days == 47, "ROS 15/02/2027 menos a previsão de entrega 30/12/2026"
    assert linha.band == "ok"
    assert linha.situation == "No prazo"
    assert linha.critical is False
    assert linha.next_milestone is not None
    assert linha.next_milestone.position == 1
    assert [marco.name for marco in linha.milestones] == [
        "Aprovação de documentos",
        "Matéria-prima",
        "Fabricação",
        "Inspeção / FAT",
        "Embarque",
        "Entrega",
    ]
    assert linha.milestones[0].situation == "a-vencer"
    assert linha.milestones[0].baseline == date(2026, 10, 5)

    listing = service.list_orders(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        filters=validation.OrderFilters(situation="todos"),
        reference_date=REFERENCIA,
    )
    assert [item.number for item in listing.lines] == ["PED-2026-0001"]
    assert listing.summary.open_orders == 1
    assert listing.summary.otd is None, "sem entrega, sem OTD"


def test_a_leitura_no_portfolio_alcanca_os_projetos(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    portfolio = service.find_order(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario, portfolio=True),
        number="PED-2026-0001",
        reference_date=REFERENCIA,
    )
    assert portfolio is not None

    fora = service.find_order(
        sessao,
        user=cenario.ana,
        scope=Scope(project_id=cenario.outro.id, source="url"),
        number="PED-2026-0001",
        reference_date=REFERENCIA,
    )
    assert fora is None, "o pedido é do outro projeto"


# ── Atualizar marco ──────────────────────────────────────────────────────────────────────────


def test_a_realizacao_exige_o_marco_anterior(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        _realizar(sessao, cenario, 2, date(2026, 9, 21))

    assert any(
        "Registre antes o marco anterior (Aprovação de documentos)." in msg
        for msg in recusa.value.messages()
    )

    _realizar(sessao, cenario, 1, date(2026, 9, 20))
    _realizar(sessao, cenario, 2, date(2026, 9, 21))

    marcos = _milestones(sessao, cenario)
    assert marcos[0].real_date == date(2026, 9, 20)
    assert marcos[1].real_date == date(2026, 9, 21)
    assert marcos[1].forecast_date == date(2026, 9, 21)
    textos = [linha["texto"] for linha in _historico(sessao, cenario)]
    assert "Aprovação de documentos realizado." in textos
    assert "Matéria-prima realizado." in textos
    linha = _linha(sessao, cenario)
    assert linha.next_milestone is not None and linha.next_milestone.position == 3
    assert sessao.scalars(select(Action)).all() == [], "com folga positiva, sem ação"


def test_a_realizacao_recusa_data_futura_e_anterior_ao_marco_anterior(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    with pytest.raises(InvalidDataError) as futura:
        _realizar(sessao, cenario, 1, date(2026, 10, 1))

    assert any("posterior à data de referência" in msg for msg in futura.value.messages())

    _realizar(sessao, cenario, 1, date(2026, 9, 21))
    with pytest.raises(InvalidDataError) as anterior:
        _realizar(sessao, cenario, 2, date(2026, 9, 20))

    assert any("anterior à do marco anterior" in msg for msg in anterior.value.messages())


def test_a_entrega_nao_se_realiza_pela_atualizacao_do_marco(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        _realizar(sessao, cenario, 6, date(2026, 9, 20))

    assert any("Registrar recebimento" in msg for msg in recusa.value.messages())


def test_a_previsao_nao_fica_no_passado_e_a_cascata_desloca_os_seguintes(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    with pytest.raises(InvalidDataError) as passado:
        _prever(sessao, cenario, 1, date(2026, 9, 24))

    assert any(
        "não pode ser anterior à data de referência" in msg for msg in passado.value.messages()
    )

    original = [marco.forecast_date for marco in _milestones(sessao, cenario)]
    assert original[0] == date(2026, 10, 5)
    assert original[5] == CONTRACTUAL

    _prever(sessao, cenario, 1, date(2026, 10, 20))

    marcos = _milestones(sessao, cenario)
    delta = date(2026, 10, 20) - original[0]
    assert delta.days == 15
    assert marcos[0].forecast_date == date(2026, 10, 20)
    for position in range(1, 6):
        assert marcos[position].forecast_date == original[position] + delta
    assert marcos[5].forecast_date == CONTRACTUAL + delta
    assert cenario.pedido.forecast == marcos[5].forecast_date
    assert any(
        "Previsão de Aprovação de documentos" in linha["texto"]
        for linha in _historico(sessao, cenario)
    )


def test_a_previsao_sem_cascata_nao_mexe_nos_seguintes(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    original = [marco.forecast_date for marco in _milestones(sessao, cenario)]

    _prever(sessao, cenario, 1, date(2026, 9, 26), cascade=False)

    marcos = _milestones(sessao, cenario)
    assert marcos[0].forecast_date == date(2026, 9, 26)
    assert [marco.forecast_date for marco in marcos[1:]] == original[1:]


# ── Recebimento ──────────────────────────────────────────────────────────────────────────────


def test_o_recebimento_exige_o_embarque(sessao: Session, cenario: CenarioDiligenciamento) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        service.register_receipt(
            sessao,
            user=cenario.ana,
            scope=_scope(cenario),
            order_id=cenario.pedido.id,
            data=validation.ReceiptInput(date=EMBARQUE, checked=True, damaged=False),
            reference_date=REFERENCIA,
        )

    assert any("Registre o embarque" in msg for msg in recusa.value.messages())


def test_o_recebimento_grava_a_entrega_e_a_evidencia(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    _realizar(sessao, cenario, 1, date(2026, 9, 20))
    _realizar(sessao, cenario, 2, date(2026, 9, 21))
    _realizar(sessao, cenario, 3, date(2026, 9, 22))
    _realizar(sessao, cenario, 4, date(2026, 9, 23))
    _realizar(sessao, cenario, 5, EMBARQUE)

    service.register_receipt(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        order_id=cenario.pedido.id,
        data=validation.ReceiptInput(
            date=ENTREGA, checked=True, damaged=False, pending="Certificados pendentes."
        ),
        reference_date=REFERENCIA,
        file_name="romaneio.pdf",
        content=b"%PDF-1.7 romaneio",
        storage=ArmazenamentoEmMemoria(),
    )

    assert cenario.pedido.delivery == ENTREGA
    assert cenario.pedido.forecast == ENTREGA
    marcos = _milestones(sessao, cenario)
    assert marcos[5].real_date == ENTREGA
    recebimento = sessao.scalars(select(DeliveryReceipt)).one()
    assert recebimento.on == ENTREGA
    assert recebimento.checked is True
    assert recebimento.damaged is False
    assert recebimento.pending == "Certificados pendentes."
    linha = _linha(sessao, cenario)
    assert linha.delivered is True
    assert linha.situation == "Entregue"
    assert linha.receipt is not None and linha.receipt.pending == "Certificados pendentes."

    with pytest.raises(InvalidDataError) as repetido:
        service.register_receipt(
            sessao,
            user=cenario.ana,
            scope=_scope(cenario),
            order_id=cenario.pedido.id,
            data=validation.ReceiptInput(date=ENTREGA, checked=True, damaged=False),
            reference_date=REFERENCIA,
        )

    assert any("Pedido já recebido." in msg for msg in repetido.value.messages())


def test_o_recebimento_com_avarias_exige_a_descricao(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    _realizar(sessao, cenario, 1, date(2026, 9, 20))
    _realizar(sessao, cenario, 2, date(2026, 9, 21))
    _realizar(sessao, cenario, 3, date(2026, 9, 22))
    _realizar(sessao, cenario, 4, date(2026, 9, 23))
    _realizar(sessao, cenario, 5, EMBARQUE)

    with pytest.raises(InvalidDataError) as recusa:
        service.register_receipt(
            sessao,
            user=cenario.ana,
            scope=_scope(cenario),
            order_id=cenario.pedido.id,
            data=validation.ReceiptInput(
                date=ENTREGA, checked=True, damaged=True, damage_description="curta"
            ),
            reference_date=REFERENCIA,
        )

    assert any("Descreva as avarias" in msg for msg in recusa.value.messages())

    service.register_receipt(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        order_id=cenario.pedido.id,
        data=validation.ReceiptInput(
            date=ENTREGA,
            checked=True,
            damaged=True,
            damage_description="Amassado no painel lateral esquerdo.",
        ),
        reference_date=REFERENCIA,
    )
    recebimento = sessao.scalars(select(DeliveryReceipt)).one()
    assert recebimento.damaged is True


# ── A ação na Central ────────────────────────────────────────────────────────────────────────


def test_a_folga_negativa_abre_uma_unica_acao(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    tornar_critico(cenario, sessao)

    primeira = _prever(sessao, cenario, 1, date(2026, 10, 20))

    assert primeira.action_created is True
    acao = sessao.scalars(select(Action)).one()
    assert acao.origin == "Suprimentos"
    assert acao.origin_ref == "PED-2026-0001"
    assert acao.group == "Diligenciamento"
    assert acao.subject == "Recuperar a folga do pedido PED-2026-0001"
    assert acao.responsible_id == cenario.ana.person_id, "o responsável é o comprador"
    assert acao.planned_date is not None
    assert (acao.planned_date - REFERENCIA).days == 7
    folga = (CRITICAL_ROS - cenario.pedido.forecast).days
    assert f"folga de {folga} dias" in (acao.description or "")

    segunda = _prever(sessao, cenario, 2, date(2027, 1, 10))

    assert segunda.action_created is False
    assert len(sessao.scalars(select(Action)).all()) == 1, "não duplica a ação"

    with pytest.raises(InvalidDataError) as existente:
        service.open_diligence_action(
            sessao,
            user=cenario.ana,
            scope=_scope(cenario),
            order_id=cenario.pedido.id,
            reference_date=REFERENCIA,
        )

    assert any("Já existe ação aberta" in msg for msg in existente.value.messages())
    linha = _linha(sessao, cenario)
    assert linha.action is not None
    assert linha.action.subject == "Recuperar a folga do pedido PED-2026-0001"


def test_a_acao_por_mao_abre_no_pedido_critico(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    tornar_critico(cenario, sessao)

    resultado = service.open_diligence_action(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        order_id=cenario.pedido.id,
        reference_date=REFERENCIA,
    )

    assert resultado.action_created is True
    assert len(sessao.scalars(select(Action)).all()) == 1


# ── A importação do ERP ──────────────────────────────────────────────────────────────────────


def test_a_importacao_do_erp_grava_a_previsao_e_a_realizacao(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    assert importing.find("diligenciamento") is not None, "o importador registrado"

    assert service.order_import_problems(
        sessao,
        scope=_scope(cenario),
        number="PED-2026-9999",
        milestone="Embarque",
        forecast=date(2026, 10, 1),
        realized=None,
        reference_date=REFERENCIA,
    ) == {"pedido": "pedido PED-2026-9999 não encontrado."}
    assert service.order_import_problems(
        sessao,
        scope=_scope(cenario),
        number="PED-2026-0001",
        milestone="Pintura",
        forecast=date(2026, 10, 1),
        realized=None,
        reference_date=REFERENCIA,
    ) == {"marco": "marco inválido."}
    assert service.order_import_problems(
        sessao,
        scope=_scope(cenario),
        number="PED-2026-0001",
        milestone="Embarque",
        forecast=None,
        realized=date(2026, 10, 1),
        reference_date=REFERENCIA,
    ) == {"realizada": "data realizada futura."}
    assert service.order_import_problems(
        sessao,
        scope=_scope(cenario),
        number="PED-2026-0001",
        milestone="Embarque",
        forecast=date(2026, 9, 24),
        realized=None,
        reference_date=REFERENCIA,
    ) == {"previsao": "previsão anterior à data de referência."}

    service.apply_order_import_row(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        number="PED-2026-0001",
        milestone="Fabricação",
        forecast=date(2026, 10, 20),
        realized=None,
        reference_date=REFERENCIA,
    )
    marcos = _milestones(sessao, cenario)
    assert marcos[2].forecast_date == date(2026, 10, 20)
    assert cenario.pedido.forecast == CONTRACTUAL, "a entrega não se moveu"

    service.apply_order_import_row(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        number="PED-2026-0001",
        milestone="Embarque",
        forecast=None,
        realized=EMBARQUE,
        reference_date=REFERENCIA,
    )
    marcos = _milestones(sessao, cenario)
    assert marcos[4].real_date == EMBARQUE

    service.apply_order_import_row(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        number="PED-2026-0001",
        milestone="Entrega",
        forecast=None,
        realized=ENTREGA,
        reference_date=REFERENCIA,
    )
    assert cenario.pedido.delivery == ENTREGA
    recebimento = sessao.scalars(select(DeliveryReceipt)).one()
    assert recebimento.checked is False
    assert "Conferência pendente" in (recebimento.pending or "")
    textos = [linha["texto"] for linha in _historico(sessao, cenario)]
    assert "Atualizado pela importação do ERP (Fabricação)." in textos
    assert "Atualizado pela importação do ERP (Entrega)." in textos


# ── Permissão ────────────────────────────────────────────────────────────────────────────────


def test_o_visualizador_nao_atualiza_marco_nem_registra_recebimento(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    with pytest.raises(AccessDeniedError):
        service.update_order_milestone(
            sessao,
            user=cenario.vitor,
            scope=_scope(cenario),
            order_id=cenario.pedido.id,
            data=validation.MilestoneInput(
                index=1, kind=validation.MILESTONE_DONE, realized=date(2026, 8, 10)
            ),
            reference_date=REFERENCIA,
        )

    with pytest.raises(AccessDeniedError):
        service.register_receipt(
            sessao,
            user=cenario.vitor,
            scope=_scope(cenario),
            order_id=cenario.pedido.id,
            data=validation.ReceiptInput(date=EMBARQUE, checked=True, damaged=False),
            reference_date=REFERENCIA,
        )

    assert _milestones(sessao, cenario)[0].real_date is None
    assert sessao.scalars(select(PurchaseOrder)).one().delivery is None


def test_o_escopo_nao_alcanca_o_pedido_de_outro_projeto(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        service.update_order_milestone(
            sessao,
            user=cenario.ana,
            scope=Scope(project_id=cenario.outro.id, source="url"),
            order_id=cenario.pedido.id,
            data=validation.MilestoneInput(
                index=1, kind=validation.MILESTONE_DONE, realized=date(2026, 8, 10)
            ),
            reference_date=REFERENCIA,
        )

    assert any("Pedido não encontrado." in msg for msg in recusa.value.messages())


def test_o_cenario_carrega_o_cronograma_padrao(cenario: CenarioDiligenciamento) -> None:
    assert cenario.pedido.emission == EMISSION
    assert cenario.pedido.ros == ROS
