"""Fachada da avaliação de desempenho da contratada (ISSUE-034).

A avaliação mensal grava os pesos congelados dos parâmetros vigentes em cada critério, então
mudar a versão do grupo depois não muda a nota da avaliação já gravada. Nota 1 ou 2 em algum
critério exige anexo de evidência e abre a ação de plano de melhoria na Central, com origem
Contrato e vínculo no número do contrato; a avaliação final abre a lição em Rascunho pela
fachada de Lições, com origem no contrato, na mesma transação. A ficha do contrato traz as
avaliações e a série do Gráfico de Áreas de Avaliação em ordem de período.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.models import Attachment
from src.core.rbac import GeneralProfile, User
from src.core.scope import Scope
from src.modulos.central_acoes.models import Action
from src.modulos.configuracoes import service as configuracoes
from src.modulos.financeiro import calculations, service, validation
from src.modulos.financeiro.models import Contract, ContractEvaluation, ContractEvaluationCriterion
from src.modulos.governanca import lessons_models
from src.modulos.governanca.lessons_models import Lesson
from tests.armazenamento_falso import ArmazenamentoEmMemoria
from tests.financeiro.conftest import REFERENCE_DATE, EacScenario, user_of
from tests.identidades import criar_empresa

HOJE = REFERENCE_DATE
ORIGINAL_CENTS = 100_000_000
CONTRACT_END = date(2026, 10, 30)
EVIDENCE_BYTES = b"%PDF-1.7 evidencia da avaliacao"
PARAMETERS_FROM = date(2026, 1, 1)
NOTES = {"hse": 4, "qualidade": 4, "prazo": 3, "gestao": 3, "recursos": 4, "documentacao": 3}


@dataclass(frozen=True)
class AvaliacaoPedido:
    """O que o teste pede à fachada: o período, o tipo, as notas, a evidência e o perfil."""

    periodo: str = "2026-08"
    tipo: str = calculations.EVALUATION_KIND_MONTHLY
    notas: dict[str, int] | None = None
    com_anexo: bool = False
    storage: ArmazenamentoEmMemoria | None = None
    perfil: GeneralProfile = GeneralProfile.MANAGER


def _escopo(cenario: EacScenario) -> Scope:
    return Scope(project_id=cenario.first.id, source="url")


def _usuario(cenario: EacScenario, perfil: GeneralProfile) -> User:
    colaborador = {
        GeneralProfile.VIEWER: cenario.viewer,
        GeneralProfile.MEMBER: cenario.member,
        GeneralProfile.MANAGER: cenario.manager,
    }[perfil]
    return user_of(colaborador, cenario.session, perfil)


def _semear_parametros(cenario: EacScenario) -> None:
    configuracoes.seed_initial_parameters(
        cenario.session, author_id=cenario.manager.id, effective_from=PARAMETERS_FROM
    )


def _criar_contrato(cenario: EacScenario, *, project=None) -> Contract:
    session = cenario.session
    projeto = project or cenario.first
    empresa = criar_empresa(session, "Contratada de teste")
    count = session.scalar(select(func.count()).select_from(Contract)) or 0
    contract = Contract(
        project_id=projeto.id,
        company_id=empresa.id,
        manager_id=cenario.responsible.id,
        fiscal_id=cenario.responsible.id,
        number=f"CT-2026-{count + 1:03d}",
        object="Obra de teste",
        modality="Preço unitário",
        original_value_cents=ORIGINAL_CENTS,
        start=date(2026, 1, 5),
        original_end=CONTRACT_END,
        current_end=CONTRACT_END,
        retention_pct=5,
        claim_notice_days=30,
        situation="Em execução",
    )
    session.add(contract)
    session.flush()
    return contract


def _criar_avaliacao(
    cenario: EacScenario, contract: Contract, pedido: AvaliacaoPedido | None = None
) -> service.EvaluationView:
    escolha = pedido or AvaliacaoPedido()
    form: dict[str, str] = {
        "periodo": escolha.periodo,
        "tipo": escolha.tipo,
        "comentario": "Avaliação de teste.",
    }
    for criterio, nota in (escolha.notas or NOTES).items():
        form[criterio] = str(nota)
    return service.create_evaluation(
        cenario.session,
        user=_usuario(cenario, escolha.perfil),
        scope=_escopo(cenario),
        contract_id=contract.id,
        form=form,
        reference_date=HOJE,
        file_name="evidencia.pdf" if escolha.com_anexo else None,
        content=EVIDENCE_BYTES if escolha.com_anexo else b"",
        storage=escolha.storage,
    )


def _ficha(cenario: EacScenario, contract: Contract) -> service.ContractView:
    return service.contract_detail(
        cenario.session,
        user=_usuario(cenario, GeneralProfile.VIEWER),
        contract_id=contract.id,
    )


# ── Pesos gravados e nota da avaliação ───────────────────────────────────


def test_avaliacao_mensal_grava_os_pesos_e_a_nota(cenario: EacScenario) -> None:
    session = cenario.session
    _semear_parametros(cenario)
    contract = _criar_contrato(cenario)

    avaliacao = _criar_avaliacao(cenario, contract)

    assert (avaliacao.period, avaliacao.kind, avaliacao.evaluator) == (
        date(2026, 8, 1),
        calculations.EVALUATION_KIND_MONTHLY,
        "Gil Gestor",
    )
    assert (avaliacao.score, avaliacao.score_class, avaliacao.class_description) == (
        71,
        "B",
        "Aprovada",
    )
    assert not avaliacao.requires_plan
    assert not avaliacao.has_evidence
    assert [(item.criterion, item.weight, item.note) for item in avaliacao.criteria] == [
        ("hse", 25, 4),
        ("qualidade", 20, 4),
        ("prazo", 20, 3),
        ("gestao", 15, 3),
        ("recursos", 10, 4),
        ("documentacao", 10, 3),
    ]

    version = configuracoes.current_version(
        session, group=service.EVALUATION_GROUP, reference_date=HOJE
    )
    assert version is not None
    registro = session.scalars(select(ContractEvaluation)).one()
    assert registro.parameter_version_id == version.id
    criterios = session.scalars(
        select(ContractEvaluationCriterion).order_by(ContractEvaluationCriterion.id)
    ).all()
    assert len(criterios) == 6
    assert (criterios[0].weight, criterios[0].note) == (25, 4)

    ficha = _ficha(cenario, contract)
    assert ficha.evaluations == (avaliacao,)
    assert ficha.evaluation_trend == ({"ano": 2026, "mes": 8, "valor": 71},)
    assert session.scalars(select(Action)).all() == []
    assert session.scalars(select(Lesson)).all() == []


def test_mudar_o_parametro_depois_nao_muda_a_avaliacao_gravada(cenario: EacScenario) -> None:
    session = cenario.session
    _semear_parametros(cenario)
    contract = _criar_contrato(cenario)
    _criar_avaliacao(cenario, contract, AvaliacaoPedido(periodo="2026-07"))

    valores = deepcopy(configuracoes.INITIAL_PARAMETERS[service.EVALUATION_GROUP])
    for criterio in valores["criterios"]:
        criterio["peso"] = 50 if criterio["id"] == "hse" else 10
    configuracoes.save_parameter_group(
        session,
        author_id=cenario.manager.id,
        group=service.EVALUATION_GROUP,
        values=valores,
        effective_from=HOJE,
        justification="Revisão dos pesos da avaliação de contratada.",
    )

    gravada = _ficha(cenario, contract).evaluations[0]

    assert (gravada.score, gravada.score_class) == (71, "B")
    assert [item.weight for item in gravada.criteria] == [25, 20, 20, 15, 10, 10]

    nova = _criar_avaliacao(cenario, contract, AvaliacaoPedido(periodo="2026-08"))

    assert nova.score == 74
    assert [item.weight for item in nova.criteria] == [50, 10, 10, 10, 10, 10]


# ── Evidência, ação e lição ──────────────────────────────────────────────


def test_nota_baixa_sem_anexo_e_recusada_e_com_anexo_cria_acao_na_central(
    cenario: EacScenario,
) -> None:
    session = cenario.session
    _semear_parametros(cenario)
    contract = _criar_contrato(cenario)
    notas = {**NOTES, "prazo": 2}

    with pytest.raises(InvalidDataError) as erro:
        _criar_avaliacao(cenario, contract, AvaliacaoPedido(notas=notas))

    assert "anexo de evidência" in erro.value.detail[service.EVALUATION_EVIDENCE_FIELD]
    assert session.scalars(select(ContractEvaluation)).all() == []
    assert (session.scalar(select(func.count()).select_from(Action)) or 0) == 0

    armazenamento = ArmazenamentoEmMemoria()
    avaliacao = _criar_avaliacao(
        cenario,
        contract,
        AvaliacaoPedido(notas=notas, com_anexo=True, storage=armazenamento),
    )

    assert (
        avaliacao.score,
        avaliacao.score_class,
        avaliacao.requires_plan,
        avaliacao.has_evidence,
    ) == (67, "C", True, True)
    anexo = session.scalars(select(Attachment)).one()
    assert (anexo.origin_table, anexo.origin_record_id, anexo.project_id) == (
        service.EVALUATION_ATTACHMENT_TABLE,
        avaliacao.id,
        cenario.first.id,
    )
    assert armazenamento.arquivos == {f"{cenario.first.id}/{anexo.id}": EVIDENCE_BYTES}

    acao = session.scalars(select(Action)).one()
    assert (acao.origin, acao.origin_ref, acao.group, acao.project_id) == (
        service.EVALUATION_ACTION_ORIGIN,
        contract.number,
        service.EVALUATION_ACTION_GROUP,
        cenario.first.id,
    )
    assert acao.subject == "Plano de melhoria da Contratada de teste"
    assert "Prazo" in (acao.description or "")
    assert (acao.requester_id, acao.responsible_id) == (
        _usuario(cenario, GeneralProfile.MANAGER).person_id,
        contract.manager_id,
    )
    assert acao.planned_date == HOJE + timedelta(days=service.EVALUATION_PLAN_DAYS)


def test_avaliacao_final_cria_licao_em_rascunho_com_origem_no_contrato(
    cenario: EacScenario,
) -> None:
    session = cenario.session
    _semear_parametros(cenario)
    contract = _criar_contrato(cenario)
    _criar_avaliacao(cenario, contract, AvaliacaoPedido(periodo="2026-08"))

    final = _criar_avaliacao(
        cenario,
        contract,
        AvaliacaoPedido(periodo="2026-09", tipo=calculations.EVALUATION_KIND_FINAL),
    )

    assert final.kind == calculations.EVALUATION_KIND_FINAL
    licao = session.scalars(select(Lesson)).one()
    assert (licao.situation, licao.origin, licao.origin_ref) == (
        lessons_models.SITUATION_DRAFT,
        lessons_models.ORIGIN_CONTRACT,
        contract.number,
    )
    assert (licao.project_id, licao.author_id) == (
        cenario.first.id,
        _usuario(cenario, GeneralProfile.MANAGER).person_id,
    )
    assert licao.title == f"Avaliação final do contrato {contract.number}"


# ── Série do gráfico, duplicidade e permissões ───────────────────────────


def test_serie_do_grafico_fica_em_ordem_de_periodo(cenario: EacScenario) -> None:
    _semear_parametros(cenario)
    contract = _criar_contrato(cenario)
    boas = dict.fromkeys(NOTES, 4)
    todas_altas = dict.fromkeys(NOTES, 5)
    _criar_avaliacao(cenario, contract, AvaliacaoPedido(periodo="2026-08", notas=boas))
    _criar_avaliacao(cenario, contract, AvaliacaoPedido(periodo="2026-07", notas=todas_altas))

    ficha = _ficha(cenario, contract)

    assert [item.period for item in ficha.evaluations] == [date(2026, 8, 1), date(2026, 7, 1)]
    assert ficha.evaluation_trend == (
        {"ano": 2026, "mes": 7, "valor": 100},
        {"ano": 2026, "mes": 8, "valor": 80},
    )


def test_duplicidade_nota_fora_da_escala_e_permissao_sao_recusadas(
    cenario: EacScenario,
) -> None:
    _semear_parametros(cenario)
    contract = _criar_contrato(cenario)
    _criar_avaliacao(cenario, contract)

    with pytest.raises(InvalidDataError) as duplicada:
        _criar_avaliacao(cenario, contract, AvaliacaoPedido(notas={**NOTES, "hse": 5}))

    assert (
        "Já existe avaliação mensal" in duplicada.value.detail[validation.FIELD_EVALUATION_PERIOD]
    )

    with pytest.raises(InvalidDataError) as fora_da_escala:
        _criar_avaliacao(
            cenario,
            contract,
            AvaliacaoPedido(periodo="2026-07", notas={**NOTES, "hse": 6}),
        )

    assert fora_da_escala.value.detail["hse"]

    with pytest.raises(AccessDeniedError):
        _criar_avaliacao(cenario, contract, AvaliacaoPedido(perfil=GeneralProfile.MEMBER))

    contrato_alheio = _criar_contrato(cenario, project=cenario.second)
    with pytest.raises(AccessDeniedError):
        _criar_avaliacao(cenario, contrato_alheio)


def test_sem_parametros_do_grupo_a_avaliacao_e_recusada(cenario: EacScenario) -> None:
    contract = _criar_contrato(cenario)

    with pytest.raises(InvalidDataError) as erro:
        _criar_avaliacao(cenario, contract)

    assert service.EVALUATION_PARAMETERS_MISSING in str(erro.value)
