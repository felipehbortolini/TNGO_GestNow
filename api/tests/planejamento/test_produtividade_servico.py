"""Fachada da Produtividade (ISSUE-046): ciclo da LB, segregação, revisão e apontamento.

O cenário mínimo vem de ``apoio_produtividade``; a data de referência é injetada (25/09/2026).
O ciclo: item em elaboração, aprovação pelo Gestor (quem elaborou não aprova), revisão só com
SM aprovada e apontamento semanal com upsert e limites.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.errors import AccessDeniedError, InvalidDataError
from src.modulos.planejamento import calculations, service, validation
from src.modulos.planejamento.models import ProductivityEntry, ProductivityItem
from tests.apoio_produtividade import (
    HOJE,
    SEMANA_ATUAL,
    Cenario,
    form_item,
    form_revisao,
    montar_cenario,
)

D = Decimal


@pytest.fixture
def cenario(sessao: Session) -> Cenario:
    return montar_cenario(sessao)


def _criar(cenario: Cenario, sessao: Session, **overrides: str) -> ProductivityItem:
    return service.save_item(
        sessao,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        item_id=None,
        form=form_item(cenario, **overrides),
        reference_date=HOJE,
    )


def _aprovar(cenario: Cenario, sessao: Session, item: ProductivityItem) -> ProductivityItem:
    return service.approve_item(
        sessao,
        user=cenario.usuario_gestor,
        scope=cenario.escopo,
        item_id=item.id,
        version=str(item.version),
        reference_date=HOJE,
    )


def _apontar(
    cenario: Cenario,
    sessao: Session,
    item: ProductivityItem,
    *,
    semana: str = "2026-S38",
    realizado: str = "10",
    hh: str = "100",
) -> int:
    return service.register_entries(
        sessao,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        company_id=cenario.empresa.id,
        form=validation.EntryForm(week=semana, lines={item.id: (realizado, hh)}),
        reference_date=HOJE,
    )


def test_o_item_nasce_em_elaboracao_com_a_revisao_zero(cenario: Cenario, sessao: Session) -> None:
    item = _criar(cenario, sessao)

    assert (item.code, item.situation, item.revision) == ("QTD-01", calculations.ITEM_DRAFT, 0)
    assert item.approved_by_id is None
    assert item.start.isocalendar()[1] == 38
    revisao = item.revisions[0]
    assert revisao.by_id == cenario.membro.person_id
    assert sum((line.planned for line in revisao.distributions), D(0)) == item.total


def test_o_codigo_e_sequencial_por_projeto(cenario: Cenario, sessao: Session) -> None:
    primeiro = _criar(cenario, sessao)
    segundo = _criar(cenario, sessao, tipo="Tubulação montada")

    assert (primeiro.code, segundo.code) == ("QTD-01", "QTD-02")


def test_quem_elaborou_nao_aprova(cenario: Cenario, sessao: Session) -> None:
    item = _criar(cenario, sessao)

    with pytest.raises(AccessDeniedError):
        service.approve_item(
            sessao,
            user=cenario.usuario_membro,
            scope=cenario.escopo,
            item_id=item.id,
            version=str(item.version),
            reference_date=HOJE,
        )

    aprovado = service.approve_item(
        sessao,
        user=cenario.usuario_gestor,
        scope=cenario.escopo,
        item_id=item.id,
        version=str(item.version),
        reference_date=HOJE,
    )
    assert aprovado.situation == calculations.ITEM_APPROVED
    assert aprovado.approved_by_id == cenario.gestor.person_id
    assert aprovado.approved_on == HOJE


def test_a_lb_aprovada_so_aceita_observacoes(cenario: Cenario, sessao: Session) -> None:
    item = _aprovar(cenario, sessao, _criar(cenario, sessao))

    editado = service.save_item(
        sessao,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        item_id=item.id,
        form=form_item(cenario, version=item.version, total="999", planned={}),
        reference_date=HOJE,
    )

    assert editado.total == D(100), "o total da LB aprovada não muda por edição"
    assert not editado.notes
    com_observacao = service.save_item(
        sessao,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        item_id=item.id,
        form=validation.ItemForm(
            fields={"observacoes": "Ajuste combinado", "versao": str(editado.version)}, planned={}
        ),
        reference_date=HOJE,
    )
    assert com_observacao.notes == "Ajuste combinado"


def test_a_revisao_sem_sm_aprovada_e_recusada(cenario: Cenario, sessao: Session) -> None:
    item = _aprovar(cenario, sessao, _criar(cenario, sessao))

    with pytest.raises(InvalidDataError) as recusa:
        service.revise_item(
            sessao,
            user=cenario.usuario_membro,
            scope=cenario.escopo,
            item_id=item.id,
            form=form_revisao(cenario, version=item.version, sm="SM-QUE-NAO-EXISTE"),
            reference_date=HOJE,
        )

    assert "smRef" in recusa.value.detail


def test_a_revisao_com_sm_congela_o_passado_e_redistribui_o_saldo(
    cenario: Cenario, sessao: Session
) -> None:
    item = _aprovar(cenario, sessao, _criar(cenario, sessao))
    _apontar(cenario, sessao, item, semana="2026-S38", realizado="15", hh="150")
    _apontar(cenario, sessao, item, semana="2026-S39", realizado="20", hh="200")
    free = dict.fromkeys(calculations.list_weeks("2026-S40", "2026-S43"), "20")

    revisado = service.revise_item(
        sessao,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        item_id=item.id,
        form=form_revisao(cenario, version=item.version, total="120", fim="2026-S43", planned=free),
        reference_date=HOJE,
    )

    assert revisado.total == D(120)
    assert revisado.revision == 1
    atual = revisado.revisions[-1]
    assert atual.previous_total == D(100)
    assert atual.change_id == cenario.sm.id
    assert atual.since == "2026-S40"
    congeladas = {
        line.week: line.planned for line in atual.distributions if line.week <= SEMANA_ATUAL
    }
    assert congeladas == {"2026-S38": D(20), "2026-S39": D(20)}
    assert sum((line.planned for line in atual.distributions), D(0)) == D(120)


def test_o_apontamento_atualiza_a_semana_existente(cenario: Cenario, sessao: Session) -> None:
    item = _aprovar(cenario, sessao, _criar(cenario, sessao))

    _apontar(cenario, sessao, item, realizado="10", hh="100")
    _apontar(cenario, sessao, item, realizado="12", hh="120")

    entradas = list(
        sessao.scalars(select(ProductivityEntry).where(ProductivityEntry.item_id == item.id))
    )
    assert len(entradas) == 1
    assert (entradas[0].realized, entradas[0].hh) == (D(12), D(120))


def test_o_apontamento_recusa_o_acumulado_acima_da_lb(cenario: Cenario, sessao: Session) -> None:
    item = _aprovar(cenario, sessao, _criar(cenario, sessao))
    _apontar(cenario, sessao, item, semana="2026-S38", realizado="95", hh="950")

    with pytest.raises(InvalidDataError) as recusa:
        _apontar(cenario, sessao, item, semana="2026-S39", realizado="10", hh="100")

    assert f"realizado_{item.id}" in recusa.value.detail
    assert "passa o total da LB" in str(recusa.value)


def test_o_apontamento_recusa_semana_futura(cenario: Cenario, sessao: Session) -> None:
    item = _aprovar(cenario, sessao, _criar(cenario, sessao))

    with pytest.raises(InvalidDataError) as recusa:
        _apontar(cenario, sessao, item, semana="2026-S40", realizado="10", hh="100")

    assert recusa.value.detail == {"semana": "Não é possível apontar semana futura."}


def test_o_apontamento_recusa_realizado_sem_hh(cenario: Cenario, sessao: Session) -> None:
    item = _aprovar(cenario, sessao, _criar(cenario, sessao))

    with pytest.raises(InvalidDataError) as recusa:
        _apontar(cenario, sessao, item, realizado="10", hh="0")

    assert f"hh_{item.id}" in recusa.value.detail


def test_o_item_em_elaboracao_fica_fora_dos_indicadores(cenario: Cenario, sessao: Session) -> None:
    _criar(cenario, sessao)
    aprovado = _aprovar(cenario, sessao, _criar(cenario, sessao, tipo="Tubulação montada"))

    visao = service.quantities_overview(
        sessao, user=cenario.usuario_membro, scope=cenario.escopo, reference_date=HOJE
    )

    assert visao.draft_count == 1
    assert len(visao.items) == 2
    assert visao.indicators.items == 1
    assert aprovado.code == "QTD-02"


def test_excluir_item_aprovado_e_recusado(cenario: Cenario, sessao: Session) -> None:
    aprovado = _aprovar(cenario, sessao, _criar(cenario, sessao))

    with pytest.raises(InvalidDataError):
        service.delete_item(
            sessao,
            user=cenario.usuario_membro,
            scope=cenario.escopo,
            item_id=aprovado.id,
            version=str(aprovado.version),
        )

    em_elaboracao = _criar(cenario, sessao, tipo="Tubulação montada")
    service.delete_item(
        sessao,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        item_id=em_elaboracao.id,
        version=str(em_elaboracao.version),
    )
    assert sessao.get(ProductivityItem, em_elaboracao.id) is None
