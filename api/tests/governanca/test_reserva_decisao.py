"""Reservas na análise e na decisão da SM (ISSUE-041, HU-094).

A análise e a decisão conferem o saldo da reserva da fonte do consumo e da liberação; a decisão
acima do saldo é recusada e o pedido igual ao saldo passa. A aprovação grava o movimento da
reserva (consumo negativo do custo ou liberação negativa do valor) na mesma transação, com a
data da decisão; a SM sem reserva envolvida não grava movimento.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.errors import InvalidDataError
from src.core.scope import Scope
from src.modulos.financeiro import calculations as financeiro_calculations
from src.modulos.financeiro import service as financeiro
from src.modulos.financeiro.models import ReserveMovement
from src.modulos.governanca import models, routes, service
from tests.governanca import apoio
from tests.governanca.apoio import HOJE
from tests.identidades import requisicao


def _cenario(session: Session):
    projeto = apoio.projeto_com_orcamento(session)
    membro = apoio.colaborador(session, apoio.MEMBRO)
    gestor = apoio.colaborador(session, apoio.GESTOR, "Gestor")
    return projeto, apoio.usuario_de(membro), apoio.usuario_de(gestor, nome="Gabriel Gestor")


def _analise(mudanca: models.ChangeRequest, **campos: str) -> dict[str, str]:
    base = {
        "custo": "1.000,00",
        "prazo_dias": "0",
        "marco_contratual": "nao",
        "escopo": "Inclui o novo pacote de tratamento.",
        "qualidade": "Sem impacto",
        "riscos": "Sem impacto",
        "sms": "Sem impacto",
        "contrato": "Sem impacto",
        "alcada": "Gerente do projeto",
        "fonte_recurso": "Aditivo de orçamento",
        "itens_eac": "",
        "versao": str(mudanca.version),
    }
    base.update(campos)
    return base


def _iniciar(session: Session, usuario, mudanca: models.ChangeRequest) -> None:
    service.start_analysis(
        session,
        user=usuario,
        code=mudanca.code,
        form={
            "responsavel_id": str(usuario.person_id),
            "prazo": "2026-10-16",
            "versao": str(mudanca.version),
        },
        reference_date=HOJE,
    )


def _concluir(
    session: Session, usuario, mudanca: models.ChangeRequest, **campos: str
) -> models.ChangeRequest:
    return service.conclude_analysis(
        session,
        user=usuario,
        code=mudanca.code,
        form=_analise(mudanca, **campos),
        reference_date=HOJE,
    )


def _aguardando(
    session: Session,
    usuario,
    projeto,
    *,
    tipo: str = "Custo",
    analise: Mapping[str, str] | None = None,
    **liberacao: str,
) -> models.ChangeRequest:
    campos = {
        "custo": "1.000,00",
        "fonte_recurso": financeiro_calculations.RESERVE_SOURCE_CONTINGENCY,
        "alcada": "Gerente do projeto",
        **(analise or {}),
    }
    criada = apoio.registrar(session, usuario, projeto, tipo=tipo)
    mudanca = session.get(models.ChangeRequest, criada.id)
    assert mudanca is not None
    _iniciar(session, usuario, mudanca)
    _concluir(session, usuario, mudanca, **campos, **liberacao)
    atual = session.get(models.ChangeRequest, criada.id)
    assert atual is not None
    assert atual.situation == models.SITUATION_AWAITING
    return atual


def _decisao(mudanca: models.ChangeRequest, projeto, **campos: object) -> dict[str, object]:
    base: dict[str, object] = {
        "resultado": "Aprovada",
        "data": HOJE.isoformat(),
        "participantes": [str(projeto.manager_id)],
        "justificativa": "Aprovada com base na análise de impacto.",
        "condicoes": "",
        "reapresentar_em": "",
        "ata_id": "",
        "acoes": [],
        "prevista": (HOJE + timedelta(days=15)).isoformat(),
        "versao": str(mudanca.version),
    }
    base.update(campos)
    return base


def _movimentos(session: Session, *, kind: str) -> list[ReserveMovement]:
    return list(
        session.scalars(
            select(ReserveMovement).where(ReserveMovement.kind == kind).order_by(ReserveMovement.id)
        )
    )


def _saldo_contingencia(session: Session, projeto) -> int:
    entry = financeiro.reserve_state(session, project_id=projeto.id).entry(
        financeiro_calculations.RESERVE_CONTINGENCY
    )
    assert entry is not None
    return entry.balance_cents


# ── Análise ──────────────────────────────────────────────────────────────


def test_concluir_analise_acima_do_saldo_e_recusada(sessao: Session) -> None:
    projeto, membro, _ = _cenario(sessao)
    apoio.constituir_reservas(sessao, projeto, contingencia_cents=20_000_00)
    criada = apoio.registrar(sessao, membro, projeto)
    mudanca = sessao.get(models.ChangeRequest, criada.id)
    assert mudanca is not None
    _iniciar(sessao, membro, mudanca)

    with pytest.raises(InvalidDataError) as recusa:
        _concluir(
            sessao, membro, mudanca, custo="20.000,01", fonte_recurso="Reserva de contingência"
        )

    assert "reserva de contingência" in str(recusa.value)
    assert sessao.scalars(select(models.ChangeImpact)).all() == []
    assert mudanca.situation == models.SITUATION_ANALYSIS


def test_concluir_analise_sem_reserva_constituida_e_recusada(sessao: Session) -> None:
    projeto, membro, _ = _cenario(sessao)
    criada = apoio.registrar(sessao, membro, projeto)
    mudanca = sessao.get(models.ChangeRequest, criada.id)
    assert mudanca is not None
    _iniciar(sessao, membro, mudanca)

    with pytest.raises(InvalidDataError) as recusa:
        _concluir(
            sessao, membro, mudanca, custo="1.000,00", fonte_recurso="Reserva de contingência"
        )

    assert "não tem reservas constituídas" in str(recusa.value)


def test_liberacao_sem_reserva_constituida_e_recusada(sessao: Session) -> None:
    projeto, membro, _ = _cenario(sessao)
    criada = apoio.registrar(sessao, membro, projeto, tipo=models.TYPE_RESERVE_RELEASE)
    mudanca = sessao.get(models.ChangeRequest, criada.id)
    assert mudanca is not None
    _iniciar(sessao, membro, mudanca)

    with pytest.raises(InvalidDataError) as recusa:
        _concluir(
            sessao,
            membro,
            mudanca,
            custo="0",
            fonte_recurso="",
            alcada="Comitê",
            liberacao_reserva="Contingência",
            liberacao_valor="5.000,00",
        )

    assert "não tem reservas constituídas" in str(recusa.value)


# ── Decisão e movimento ──────────────────────────────────────────────────


def test_decisao_acima_do_saldo_e_recusada_e_igual_passa(sessao: Session) -> None:
    projeto, membro, gestor = _cenario(sessao)
    apoio.constituir_reservas(sessao, projeto, contingencia_cents=20_000_00)
    primeira = _aguardando(sessao, membro, projeto, analise={"custo": "15.000,00"})
    segunda = _aguardando(sessao, membro, projeto, analise={"custo": "15.000,00"})
    limite = _aguardando(sessao, membro, projeto, analise={"custo": "5.000,00"})

    service.decide_change(
        sessao,
        user=gestor,
        code=primeira.code,
        form=_decisao(primeira, projeto),
        reference_date=HOJE,
    )

    with pytest.raises(InvalidDataError) as recusa:
        service.decide_change(
            sessao,
            user=gestor,
            code=segunda.code,
            form=_decisao(segunda, projeto),
            reference_date=HOJE,
        )

    assert "Saldo da reserva de contingência insuficiente" in str(recusa.value)
    assert segunda.situation == models.SITUATION_AWAITING
    consumos = _movimentos(sessao, kind=financeiro_calculations.MOVEMENT_CONSUMPTION)
    assert [movement.value_cents for movement in consumos] == [-15_000_00]

    service.decide_change(
        sessao,
        user=gestor,
        code=limite.code,
        form=_decisao(limite, projeto),
        reference_date=HOJE,
    )

    consumos = _movimentos(sessao, kind=financeiro_calculations.MOVEMENT_CONSUMPTION)
    assert [movement.value_cents for movement in consumos] == [-15_000_00, -5_000_00]
    assert limite.situation == models.SITUATION_IMPLEMENTING
    assert _saldo_contingencia(sessao, projeto) == 0


def test_aprovacao_grava_o_movimento_de_consumo(sessao: Session) -> None:
    projeto, membro, gestor = _cenario(sessao)
    apoio.constituir_reservas(sessao, projeto, contingencia_cents=20_000_00)
    mudanca = _aguardando(sessao, membro, projeto, analise={"custo": "4.000,00"})

    service.decide_change(
        sessao,
        user=gestor,
        code=mudanca.code,
        form=_decisao(mudanca, projeto),
        reference_date=HOJE,
    )

    (movement,) = _movimentos(sessao, kind=financeiro_calculations.MOVEMENT_CONSUMPTION)
    assert movement.value_cents == -4_000_00
    assert movement.change_id == mudanca.id
    assert movement.registered_on == HOJE
    assert movement.registered_by_id == gestor.person_id
    assert movement.justification == mudanca.title
    assert _saldo_contingencia(sessao, projeto) == 16_000_00


def test_aprovacao_sem_reserva_nao_grava_movimento(sessao: Session) -> None:
    projeto, membro, gestor = _cenario(sessao)
    apoio.constituir_reservas(sessao, projeto, contingencia_cents=20_000_00)
    mudanca = _aguardando(
        sessao,
        membro,
        projeto,
        analise={"custo": "4.000,00", "fonte_recurso": "Aditivo de orçamento"},
    )

    service.decide_change(
        sessao,
        user=gestor,
        code=mudanca.code,
        form=_decisao(mudanca, projeto),
        reference_date=HOJE,
    )

    movimentos = sessao.scalars(
        select(ReserveMovement).where(
            ReserveMovement.kind != financeiro_calculations.MOVEMENT_CONSTITUTION
        )
    ).all()
    assert movimentos == []


def test_liberacao_acima_do_saldo_menos_o_pedido_e_recusada(sessao: Session) -> None:
    projeto, membro, gestor = _cenario(sessao)
    apoio.constituir_reservas(sessao, projeto, contingencia_cents=20_000_00)
    primeira = _aguardando(
        sessao,
        membro,
        projeto,
        tipo=models.TYPE_RESERVE_RELEASE,
        analise={"custo": "0", "fonte_recurso": "", "alcada": "Comitê"},
        liberacao_reserva="Contingência",
        liberacao_valor="5.000,00",
    )
    segunda = _aguardando(
        sessao,
        membro,
        projeto,
        tipo=models.TYPE_RESERVE_RELEASE,
        analise={"custo": "0", "fonte_recurso": "", "alcada": "Comitê"},
        liberacao_reserva="Contingência",
        liberacao_valor="10.000,00",
    )
    criada = apoio.registrar(sessao, membro, projeto, tipo=models.TYPE_RESERVE_RELEASE)
    terceira = sessao.get(models.ChangeRequest, criada.id)
    assert terceira is not None
    _iniciar(sessao, membro, terceira)

    with pytest.raises(InvalidDataError) as recusa:
        _concluir(
            sessao,
            membro,
            terceira,
            custo="0",
            fonte_recurso="",
            alcada="Comitê",
            liberacao_reserva="Contingência",
            liberacao_valor="6.000,00",
        )

    assert "livres para liberar" in str(recusa.value)
    assert "R$ 5.000,00" in str(recusa.value)

    _concluir(
        sessao,
        membro,
        terceira,
        custo="0",
        fonte_recurso="",
        alcada="Comitê",
        liberacao_reserva="Contingência",
        liberacao_valor="5.000,00",
    )
    terceira = sessao.get(models.ChangeRequest, criada.id)
    assert terceira is not None
    participantes = [str(projeto.manager_id), str(membro.person_id), str(gestor.person_id)]
    service.decide_change(
        sessao,
        user=gestor,
        code=terceira.code,
        form=_decisao(terceira, projeto, participantes=participantes),
        reference_date=HOJE,
    )

    (movement,) = _movimentos(sessao, kind=financeiro_calculations.MOVEMENT_RELEASE)
    assert movement.value_cents == -5_000_00
    assert movement.change_id == terceira.id
    assert _saldo_contingencia(sessao, projeto) == 15_000_00
    assert primeira.situation == models.SITUATION_AWAITING
    assert segunda.situation == models.SITUATION_AWAITING


# ── Painel ───────────────────────────────────────────────────────────────


def test_painel_mostra_o_consumo_da_contingencia(sessao: Session) -> None:
    projeto, membro, _ = _cenario(sessao)
    reserves = apoio.constituir_reservas(sessao, projeto, contingencia_cents=20_000_00)
    sessao.add(
        ReserveMovement(
            reserve_id=reserves[financeiro_calculations.RESERVE_CONTINGENCY].id,
            change_id=None,
            registered_by_id=membro.person_id,
            kind=financeiro_calculations.MOVEMENT_CONSUMPTION,
            registered_on=HOJE,
            value_cents=-3_000_00,
            justification="Consumo aprovado na demonstração.",
        )
    )
    sessao.flush()

    painel = service.change_panel(
        sessao,
        user=membro,
        scope=Scope(project_id=projeto.id, source="url"),
        reference_date=HOJE,
    )

    assert painel.contingency is not None
    assert (
        painel.contingency.total_cents,
        painel.contingency.consumed_cents,
        painel.contingency.balance_cents,
    ) == (20_000_00, 3_000_00, 17_000_00)

    resposta = routes.change_register(
        requisicao(
            "/api/governanca/mudancas", email=apoio.MEMBRO, params={"projeto": str(projeto.id)}
        )
    )
    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "Reserva de contingência consumida" in corpo
    assert "R$ 3.000,00" in corpo
