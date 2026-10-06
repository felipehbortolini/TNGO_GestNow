"""Fachada das revisões e do remanejamento da EAC (ISSUE-030, D5, D9).

O remanejamento nasce como SM do tipo "Remanejamento de orçamento": o valor fica reservado na
origem até a decisão, a aprovação aplica as transferências na EAC na mesma transação (conferindo
o saldo livre de novo) e a rejeição libera a reserva. A revisão exige SM aprovada com custo ainda
não incorporado, congela a linha de base de todos os itens de nível 3 e grava a revisão na SM.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.rbac import GeneralProfile
from src.core.scope import Scope
from src.modulos.financeiro import service
from src.modulos.financeiro.models import EacItem, EacReallocation, EacRevisionItem
from src.modulos.governanca import models as sm_models
from src.modulos.governanca import service as governanca
from src.modulos.governanca.models import ChangeReallocation, ChangeRequest
from tests.financeiro.conftest import EacScenario, user_of

HOJE = date(2026, 10, 6)
JUSTIFICATIVA = "Remanejamento aprovado na reunião de custos do projeto."
ORCAMENTO = 4_460_000_000


def _reais(cents: int) -> str:
    reais, rest = divmod(cents, 100)
    return f"{reais:,}".replace(",", ".") + f",{rest:02d}"


def _membro(cenario: EacScenario):
    return user_of(cenario.member, cenario.session, GeneralProfile.MEMBER)


def _gestor(cenario: EacScenario):
    return user_of(cenario.manager, cenario.session, GeneralProfile.MANAGER)


def _escopo(projeto) -> Scope:
    return Scope(project_id=projeto.id, source="url")


def _item_id(cenario: EacScenario, code: str) -> int:
    return cenario.items[f"{cenario.first.code}:{code}"]


def _view(cenario: EacScenario):
    return service.eac_view(
        cenario.session,
        user=_membro(cenario),
        scope=_escopo(cenario.first),
        filters=service.EacFilters(),
        reference_date=HOJE,
    )


def _bases(cenario: EacScenario) -> dict[str, int]:
    return {row.code: row.budget_cents for row in _view(cenario).rows}


def _remanejar(cenario: EacScenario, *, valor_cents: int, origem: str, destino: str, novo=None):
    return service.reallocate(
        cenario.session,
        user=_membro(cenario),
        scope=_escopo(cenario.first),
        request=service.ReallocationRequest(
            justification=JUSTIFICATIVA,
            transfers=(
                service.TransferRequest(
                    source_code=origem,
                    target_code=destino,
                    value_cents=valor_cents,
                    new_item=novo,
                ),
            ),
        ),
        reference_date=HOJE,
    )


def _na_pauta(
    cenario: EacScenario,
    change_id: int,
    *,
    transferencias: tuple[tuple[str, str, int], ...] = (),
    custo_cents: int = 0,
    itens: tuple[str, ...] = (),
) -> ChangeRequest:
    session = cenario.session
    usuario = _membro(cenario)
    change = session.get(ChangeRequest, change_id)
    governanca.start_analysis(
        session,
        user=usuario,
        code=change.code,
        form={
            "responsavel_id": str(usuario.person_id),
            "prazo": (HOJE + timedelta(days=10)).isoformat(),
            "versao": str(change.version),
        },
        reference_date=HOJE,
    )
    change = session.get(ChangeRequest, change_id)
    form: dict[str, str] = {
        "custo": _reais(custo_cents),
        "prazo_dias": "0",
        "marco_contratual": "nao",
        "escopo": "Análise do remanejamento entre itens da EAC.",
        "qualidade": "Sem impacto",
        "riscos": "Sem impacto",
        "sms": "Sem impacto",
        "contrato": "Sem impacto",
        "alcada": "Gerente do projeto",
        "fonte_recurso": "Aditivo de orçamento" if custo_cents > 0 else "",
        "itens_eac": ", ".join(itens),
        "versao": str(change.version),
    }
    for number, (origem, destino, valor) in enumerate(transferencias, start=1):
        form[f"remanejamento_origem_{number}"] = origem
        form[f"remanejamento_destino_{number}"] = destino
        form[f"remanejamento_valor_{number}"] = _reais(valor)
    governanca.conclude_analysis(
        session, user=usuario, code=change.code, form=form, reference_date=HOJE
    )
    return session.get(ChangeRequest, change_id)


def _decidir(cenario: EacScenario, change_id: int, *, resultado: str = "Aprovada") -> ChangeRequest:
    session = cenario.session
    change = session.get(ChangeRequest, change_id)
    governanca.decide_change(
        session,
        user=_gestor(cenario),
        code=change.code,
        form={
            "resultado": resultado,
            "data": HOJE.isoformat(),
            "participantes": [str(cenario.first.manager_id)],
            "justificativa": "Decisão registrada no teste da ISSUE-030.",
            "condicoes": "",
            "reapresentar_em": "",
            "ata_id": "",
            "acoes": [],
            "prevista": (HOJE + timedelta(days=10)).isoformat(),
            "versao": str(change.version),
        },
        reference_date=HOJE,
    )
    return session.get(ChangeRequest, change_id)


def _aprovar_remanejamento(
    cenario: EacScenario,
    change_id: int,
    *,
    transferencias: tuple[tuple[str, str, int], ...],
) -> ChangeRequest:
    _na_pauta(cenario, change_id, transferencias=transferencias)
    return _decidir(cenario, change_id)


def _sm_com_custo(cenario: EacScenario, *, valor_cents: int) -> ChangeRequest:
    session = cenario.session
    criada = governanca.create_change(
        session,
        user=_membro(cenario),
        scope=_escopo(cenario.first),
        form={
            "titulo": "Inclusão de escopo com custo",
            "tipo": "Custo",
            "origem": "Cliente",
            "prioridade": "Normal",
            "data_solicitacao": HOJE.isoformat(),
            "descricao": JUSTIFICATIVA,
        },
        reference_date=HOJE,
    )
    _na_pauta(cenario, criada.id, custo_cents=valor_cents)
    return _decidir(cenario, criada.id)


@pytest.fixture
def orcamento(cenario: EacScenario) -> EacScenario:
    """O projeto 1 com orçamento de cadastro, para a alçada do gerente do projeto."""
    cenario.first.budget_cents = ORCAMENTO
    cenario.session.flush()
    return cenario


# ── Saldo livre e reserva ────────────────────────────────────────────────


def test_saldo_livre_desconta_a_reserva_de_outra_sm(orcamento: EacScenario) -> None:
    _remanejar(orcamento, valor_cents=300_000, origem="1.1.1", destino="2.1.1")

    with pytest.raises(InvalidDataError) as recusa:
        _remanejar(orcamento, valor_cents=700_001, origem="1.1.1", destino="2.1.1")

    mensagem = recusa.value.detail["remanejamento_valor"]
    assert "saldo livre" in mensagem
    assert "1.1.1" in mensagem
    assert "R$ 7.000,00" in mensagem

    aceita = _remanejar(orcamento, valor_cents=700_000, origem="1.1.1", destino="2.1.1")

    assert aceita.code.startswith("SM-")


def test_a_reserva_aparece_como_pendente_com_o_saldo_livre(orcamento: EacScenario) -> None:
    criada = _remanejar(
        orcamento,
        valor_cents=300_000,
        origem="1.1.1",
        destino="2.1.1",
    )

    lista = service.reallocations(orcamento.session, project_id=orcamento.first.id)

    assert lista.applied == ()
    (pendente,) = lista.pending
    assert pendente.change_id == criada.id
    assert pendente.change_code == criada.code
    assert pendente.situation == sm_models.SITUATION_REGISTERED
    assert (pendente.source_code, pendente.target_code) == ("1.1.1", "2.1.1")
    assert pendente.value_cents == 300_000
    assert pendente.applied is False
    assert pendente.new_item is False
    assert pendente.free_balance_cents == 1_000_000

    segunda = _remanejar(orcamento, valor_cents=200_000, origem="1.1.1", destino="1.1.2")
    lista = service.reallocations(orcamento.session, project_id=orcamento.first.id)
    segunda_pendente = next(linha for linha in lista.pending if linha.change_id == segunda.id)
    assert segunda_pendente.free_balance_cents == 700_000


def test_remanejamento_para_item_inexistente_ou_de_outro_nivel_e_recusado(
    orcamento: EacScenario,
) -> None:
    with pytest.raises(InvalidDataError) as pacote:
        _remanejar(orcamento, valor_cents=100_000, origem="1.1.1", destino="1.1")
    assert "nível 3" in pacote.value.detail["remanejamentos"]

    with pytest.raises(InvalidDataError) as inexistente:
        _remanejar(orcamento, valor_cents=100_000, origem="1.1.1", destino="9.9.9")
    assert "9.9.9" in inexistente.value.detail["remanejamentos"]

    with pytest.raises(InvalidDataError) as mesmo_item:
        _remanejar(orcamento, valor_cents=100_000, origem="1.1.1", destino="1.1.1")
    assert "diferente da origem" in mesmo_item.value.detail["remanejamentos"]


# ── Aprovação e rejeição ─────────────────────────────────────────────────


def test_aprovacao_aplica_as_transferencias_e_marca_a_sm(orcamento: EacScenario) -> None:
    criada = _remanejar(orcamento, valor_cents=300_000, origem="1.1.1", destino="2.1.1")
    _aprovar_remanejamento(orcamento, criada.id, transferencias=(("1.1.1", "2.1.1", 300_000),))

    linhas = orcamento.session.scalars(
        select(EacReallocation).where(EacReallocation.change_id == criada.id)
    ).all()
    assert len(linhas) == 1
    assert linhas[0].revision == 0
    assert linhas[0].applied_on == HOJE
    assert linhas[0].applied_by_id == orcamento.manager.person_id
    assert linhas[0].justification == (
        "Remanejamento de R$ 3.000,00 do item 1.1.1 para o item 2.1.1"
    )

    bases = _bases(orcamento)
    assert bases["1.1.1"] == 700_000
    assert bases["2.1.1"] == 6_300_000
    assert bases["0"] == 7_001_000

    transferencia = orcamento.session.scalars(
        select(ChangeReallocation).where(ChangeReallocation.change_id == criada.id)
    ).one()
    assert transferencia.applied is True
    assert transferencia.applied_by_id == orcamento.manager.person_id
    assert transferencia.applied_on == HOJE
    assert transferencia.eac_revision == 0

    lista = service.reallocations(orcamento.session, project_id=orcamento.first.id)
    assert lista.pending == ()
    assert [(linha.source_code, linha.target_code) for linha in lista.applied] == [
        ("1.1.1", "2.1.1")
    ]
    assert lista.applied[0].change_code == criada.code
    assert lista.applied[0].revision == 0


def test_aprovacao_com_saldo_estourado_desfaz_tudo(orcamento: EacScenario) -> None:
    criada = governanca.create_change(
        orcamento.session,
        user=_membro(orcamento),
        scope=_escopo(orcamento.first),
        form={
            "titulo": "Remanejamento acima do saldo livre",
            "tipo": sm_models.TYPE_REALLOCATION,
            "origem": "Interna",
            "prioridade": "Normal",
            "data_solicitacao": HOJE.isoformat(),
            "descricao": JUSTIFICATIVA,
        },
        reference_date=HOJE,
    )
    _na_pauta(
        orcamento,
        criada.id,
        transferencias=(("1.1.1", "2.1.1", 2_000_000),),
    )

    with pytest.raises(InvalidDataError) as recusa, orcamento.session.begin_nested():
        _decidir(orcamento, criada.id)

    assert "saldo livre" in recusa.value.detail["remanejamento_valor"]
    change = orcamento.session.get(ChangeRequest, criada.id)
    assert change.situation == sm_models.SITUATION_AWAITING
    assert (
        orcamento.session.scalars(
            select(sm_models.ChangeDecision).where(sm_models.ChangeDecision.change_id == criada.id)
        ).all()
        == []
    )
    assert orcamento.session.scalars(select(EacReallocation)).all() == []
    transferencia = orcamento.session.scalars(
        select(ChangeReallocation).where(ChangeReallocation.change_id == criada.id)
    ).one()
    assert transferencia.applied is False
    assert transferencia.applied_by_id is None


def test_rejeicao_libera_a_reserva(orcamento: EacScenario) -> None:
    criada = _remanejar(orcamento, valor_cents=700_000, origem="1.1.1", destino="2.1.1")
    _na_pauta(orcamento, criada.id, transferencias=(("1.1.1", "2.1.1", 700_000),))
    _decidir(orcamento, criada.id, resultado="Rejeitada")

    assert service.reallocations(orcamento.session, project_id=orcamento.first.id).pending == ()

    segunda = _remanejar(orcamento, valor_cents=700_000, origem="1.1.1", destino="2.1.1")

    assert segunda.id != criada.id


# ── Item novo por remanejamento ──────────────────────────────────────────


def test_item_novo_nasce_na_requisicao_com_base_zero_e_recebe_o_valor_na_aprovacao(
    orcamento: EacScenario,
) -> None:
    spec = service.NewItemRequest(
        code="2.1.2",
        description="Bombas reserva",
        parent_id=_item_id(orcamento, "2.1"),
        cost_type="Equipamento",
        capex=True,
    )
    criada = _remanejar(orcamento, valor_cents=500_000, origem="2.1.1", destino="2.1.2", novo=spec)

    item = orcamento.session.scalars(
        select(EacItem).where(EacItem.project_id == orcamento.first.id, EacItem.code == "2.1.2")
    ).one()
    assert item.level == 3
    assert item.quantity is None
    assert item.unit_price_cents is None
    bases = _bases(orcamento)
    assert bases["2.1.2"] == 0
    assert bases["0"] == 7_001_000

    _aprovar_remanejamento(orcamento, criada.id, transferencias=(("2.1.1", "2.1.2", 500_000),))

    bases = _bases(orcamento)
    assert bases["2.1.1"] == 5_500_000
    assert bases["2.1.2"] == 500_000
    assert bases["0"] == 7_001_000
    (aplicada,) = orcamento.session.scalars(
        select(EacReallocation).where(EacReallocation.change_id == criada.id)
    ).all()
    assert aplicada.target_item_id == item.id
    assert aplicada.new_item is True


def test_codigo_de_item_novo_ja_usado_e_recusado(orcamento: EacScenario) -> None:
    spec = service.NewItemRequest(code="1.1.1", description="Repetido")

    with pytest.raises(InvalidDataError) as recusa:
        _remanejar(orcamento, valor_cents=100_000, origem="1.1.2", destino="1.1.1", novo=spec)

    assert "já existe" in recusa.value.detail["remanejamentos"].lower()


# ── Revisões ─────────────────────────────────────────────────────────────


def test_revisao_sem_sm_aprovada_com_custo_e_recusada(orcamento: EacScenario) -> None:
    criada = governanca.create_change(
        orcamento.session,
        user=_membro(orcamento),
        scope=_escopo(orcamento.first),
        form={
            "titulo": "Inclusão de escopo com custo",
            "tipo": "Custo",
            "origem": "Cliente",
            "prioridade": "Normal",
            "data_solicitacao": HOJE.isoformat(),
            "descricao": JUSTIFICATIVA,
        },
        reference_date=HOJE,
    )

    with pytest.raises(InvalidDataError) as recusa:
        service.create_revision(
            orcamento.session,
            user=_gestor(orcamento),
            scope=_escopo(orcamento.first),
            request=service.RevisionRequest(
                change_id=criada.id, justification="Revisão sem SM aprovada"
            ),
            reference_date=HOJE,
        )

    assert "SM aprovada com custo" in recusa.value.detail["mudanca_id"]


def test_revisao_exige_gestor(orcamento: EacScenario) -> None:
    change = _sm_com_custo(orcamento, valor_cents=200_000)

    with pytest.raises(AccessDeniedError):
        service.create_revision(
            orcamento.session,
            user=_membro(orcamento),
            scope=_escopo(orcamento.first),
            request=service.RevisionRequest(change_id=change.id, justification=JUSTIFICATIVA),
            reference_date=HOJE,
        )


def test_revisao_cria_a_rev_zero_congela_as_linhas_e_incorpora_a_sm(
    orcamento: EacScenario,
) -> None:
    change = _sm_com_custo(orcamento, valor_cents=200_000)

    revisao = service.create_revision(
        orcamento.session,
        user=_gestor(orcamento),
        scope=_escopo(orcamento.first),
        request=service.RevisionRequest(
            change_id=change.id,
            justification="Ajuste aprovado na SM de custo.",
            adjustments=(service.AdjustmentRequest(code="1.1.1", delta_cents=100_000),),
        ),
        reference_date=HOJE,
    )

    assert revisao.revision == 0
    assert revisao.change_code == change.code
    assert revisao.total_cents == 7_101_000
    linhas = orcamento.session.scalars(
        select(EacRevisionItem).where(EacRevisionItem.revision_id == revisao.id)
    ).all()
    bases = {linha.item_id: linha.base_cents for linha in linhas}
    assert len(linhas) == 3
    assert bases[_item_id(orcamento, "1.1.1")] == 1_100_000
    assert bases[_item_id(orcamento, "1.1.2")] == 1_000
    assert bases[_item_id(orcamento, "2.1.1")] == 6_000_000
    assert change.eac_revision == 0
    assert _bases(orcamento)["1.1.1"] == 1_100_000

    ficha = governanca.find_change_sheet(
        orcamento.session, user=_gestor(orcamento), code=change.code, reference_date=HOJE
    )
    assert ficha is not None
    assert ficha.pending_eac_revision is False

    segunda_sm = _sm_com_custo(orcamento, valor_cents=50_000)
    segunda = service.create_revision(
        orcamento.session,
        user=_gestor(orcamento),
        scope=_escopo(orcamento.first),
        request=service.RevisionRequest(
            change_id=segunda_sm.id,
            justification="Segundo ajuste aprovado na SM de custo.",
            adjustments=(service.AdjustmentRequest(code="2.1.1", delta_cents=50_000),),
        ),
        reference_date=HOJE,
    )

    assert segunda.revision == 1
    assert segunda.total_cents == 7_151_000
    listadas = service.revisions(orcamento.session, project_id=orcamento.first.id)
    assert [(item.revision, item.total_cents) for item in listadas] == [
        (0, 7_101_000),
        (1, 7_151_000),
    ]


def test_revisao_recusa_acrescimo_acima_do_custo_aprovado(orcamento: EacScenario) -> None:
    change = _sm_com_custo(orcamento, valor_cents=100_000)

    with pytest.raises(InvalidDataError) as recusa:
        service.create_revision(
            orcamento.session,
            user=_gestor(orcamento),
            scope=_escopo(orcamento.first),
            request=service.RevisionRequest(
                change_id=change.id,
                justification="Acréscimo acima do custo aprovado.",
                adjustments=(service.AdjustmentRequest(code="1.1.1", delta_cents=100_001),),
            ),
            reference_date=HOJE,
        )

    assert "custo aprovado na SM" in recusa.value.detail["item_novo_valor"]


def test_revisao_consolida_os_remanejamentos_aplicados(orcamento: EacScenario) -> None:
    criada = _remanejar(orcamento, valor_cents=300_000, origem="1.1.1", destino="1.1.2")
    _aprovar_remanejamento(orcamento, criada.id, transferencias=(("1.1.1", "1.1.2", 300_000),))

    revisao = service.create_revision(
        orcamento.session,
        user=_gestor(orcamento),
        scope=_escopo(orcamento.first),
        request=service.RevisionRequest(
            change_id=_sm_com_custo(orcamento, valor_cents=100_000).id,
            justification="Revisão que consolida o remanejamento aplicado.",
        ),
        reference_date=HOJE,
    )

    linhas = orcamento.session.scalars(
        select(EacRevisionItem).where(EacRevisionItem.revision_id == revisao.id)
    ).all()
    bases = {linha.item_id: linha.base_cents for linha in linhas}
    assert bases[_item_id(orcamento, "1.1.1")] == 700_000
    assert bases[_item_id(orcamento, "1.1.2")] == 301_000
    assert revisao.total_cents == 7_001_000
    assert _bases(orcamento)["1.1.1"] == 700_000
    assert _bases(orcamento)["1.1.2"] == 301_000


def test_revisao_cria_item_novo_com_o_custo_da_sm(orcamento: EacScenario) -> None:
    change = _sm_com_custo(orcamento, valor_cents=300_000)

    revisao = service.create_revision(
        orcamento.session,
        user=_gestor(orcamento),
        scope=_escopo(orcamento.first),
        request=service.RevisionRequest(
            change_id=change.id,
            justification="Item novo financiado pela SM de custo.",
            new_items=(
                service.RevisionItemRequest(
                    code="2.1.2",
                    description="Sistema de tratamento",
                    base_cents=300_000,
                    parent_id=_item_id(orcamento, "2.1"),
                    cost_type="Serviço",
                ),
            ),
        ),
        reference_date=HOJE,
    )

    item = orcamento.session.scalars(
        select(EacItem).where(EacItem.project_id == orcamento.first.id, EacItem.code == "2.1.2")
    ).one()
    assert item.level == 3
    congelada = orcamento.session.scalars(
        select(EacRevisionItem).where(
            EacRevisionItem.revision_id == revisao.id, EacRevisionItem.item_id == item.id
        )
    ).one()
    assert congelada.base_cents == 300_000
    assert revisao.total_cents == 7_301_000
    assert _bases(orcamento)["2.1.2"] == 300_000
    assert _bases(orcamento)["0"] == 7_301_000


# ── As três ligações com a SM ────────────────────────────────────────────


def test_analise_de_impacto_recusa_item_fora_do_nivel_3(orcamento: EacScenario) -> None:
    criada = governanca.create_change(
        orcamento.session,
        user=_membro(orcamento),
        scope=_escopo(orcamento.first),
        form={
            "titulo": "Inclusão de escopo com custo",
            "tipo": "Custo",
            "origem": "Cliente",
            "prioridade": "Normal",
            "data_solicitacao": HOJE.isoformat(),
            "descricao": JUSTIFICATIVA,
        },
        reference_date=HOJE,
    )

    with pytest.raises(InvalidDataError) as recusa:
        _na_pauta(orcamento, criada.id, custo_cents=100_000, itens=("1",))

    assert "nível 3" in recusa.value.detail["itens_eac"]


def test_sm_aprovada_com_custo_fica_pendente_ate_a_revisao(orcamento: EacScenario) -> None:
    change = _sm_com_custo(orcamento, valor_cents=200_000)

    ficha = governanca.find_change_sheet(
        orcamento.session, user=_gestor(orcamento), code=change.code, reference_date=HOJE
    )
    assert ficha is not None
    assert ficha.pending_eac_revision is True

    service.create_revision(
        orcamento.session,
        user=_gestor(orcamento),
        scope=_escopo(orcamento.first),
        request=service.RevisionRequest(change_id=change.id, justification=JUSTIFICATIVA),
        reference_date=HOJE,
    )

    ficha = governanca.find_change_sheet(
        orcamento.session, user=_gestor(orcamento), code=change.code, reference_date=HOJE
    )
    assert ficha is not None
    assert ficha.pending_eac_revision is False


def test_encerramento_recusado_ate_incorporar_a_revisao(orcamento: EacScenario) -> None:
    change = _sm_com_custo(orcamento, valor_cents=200_000)

    with pytest.raises(InvalidDataError) as recusa:
        governanca.close_change(
            orcamento.session,
            user=_gestor(orcamento),
            code=change.code,
            form={
                "data": HOJE.isoformat(),
                "observacao": "Encerramento pedido no teste.",
                "versao": str(change.version),
            },
            reference_date=HOJE,
        )

    assert "revisão da EAC" in str(recusa.value)

    service.create_revision(
        orcamento.session,
        user=_gestor(orcamento),
        scope=_escopo(orcamento.first),
        request=service.RevisionRequest(change_id=change.id, justification=JUSTIFICATIVA),
        reference_date=HOJE,
    )
    change = orcamento.session.get(ChangeRequest, change.id)

    resultado = governanca.close_change(
        orcamento.session,
        user=_gestor(orcamento),
        code=change.code,
        form={
            "data": HOJE.isoformat(),
            "observacao": "Encerramento depois da revisão.",
            "versao": str(change.version),
        },
        reference_date=HOJE,
    )

    assert resultado.code == change.code
    assert change.situation == sm_models.SITUATION_CLOSED
    assert change.eac_revision == 0
