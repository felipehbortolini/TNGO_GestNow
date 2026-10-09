"""As rotas da recomendação, da aprovação e da emissão (ISSUE-060): formulários, recusas e 403.

A rota roda na transação do teste (fixture ``sessao``), no modo demonstração e com o relógio em
25/09/2026. O processo é conduzido pela fachada até a etapa do formulário e a requisição é
montada como o shell a envia: cabeçalho do Alpine AJAX, o principal do colaborador e o escopo no
parâmetro ``projeto``.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.scope import Scope
from src.modulos.suprimentos import routes, service, validation
from src.modulos.suprimentos.models import (
    PackageMilestone,
    ProcessProposal,
    PurchaseOrder,
    PurchaseProcess,
)
from tests.apoio_pacotes import REFERENCIA
from tests.apoio_processos import (
    CenarioProcessos,
    montar_cenario_processos,
    proposta_do_cenario,
    rfx_do_cenario,
)
from tests.armazenamento_falso import ArmazenamentoEmMemoria
from tests.identidades import requisicao

ANA = "ana.admin@plano.example.invalid"
VITOR = "vitor.visualizador@plano.example.invalid"


@pytest.fixture
def cenario_processos(sessao: Session) -> CenarioProcessos:
    """O cenário do processo na sessão do teste, servindo as rotas pela unidade de trabalho."""
    return montar_cenario_processos(sessao)


def _params(cenario: CenarioProcessos) -> dict[str, str]:
    return {"projeto": str(cenario.projeto.id)}


def _post(cenario: CenarioProcessos, nome: str, **corpo: str):
    return requisicao(
        f"/api/suprimentos/processos/{cenario.pacote.id}/acao/{nome}",
        metodo="POST",
        email=ANA,
        params=_params(cenario),
        rota={"pacote_id": str(cenario.pacote.id), "nome": nome},
        corpo=corpo,
        alvo="processo-modal-corpo",
    )


def _scope(cenario: CenarioProcessos) -> Scope:
    return Scope(project_id=cenario.projeto.id, source="url")


def _registrar_proposta(sessao: Session, cenario: CenarioProcessos, **campos: object) -> None:
    service.register_proposal(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        package_id=cenario.pacote.id,
        data=proposta_do_cenario(cenario, **campos),
        reference_date=REFERENCIA,
        file_name="proposta.pdf",
        content=b"%PDF-1.7 proposta",
        storage=ArmazenamentoEmMemoria(),
    )


def _processo(sessao: Session, cenario: CenarioProcessos) -> PurchaseProcess:
    return sessao.scalars(
        select(PurchaseProcess).where(PurchaseProcess.package_id == cenario.pacote.id)
    ).one()


def _fluxo_ate_negociacao(sessao: Session, cenario: CenarioProcessos) -> None:
    service.issue_rfx(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        package_id=cenario.pacote.id,
        data=rfx_do_cenario(cenario),
        reference_date=REFERENCIA,
    )
    _registrar_proposta(sessao, cenario, value_cents=40_000_000)
    _registrar_proposta(
        sessao, cenario, company_id=cenario.fornecedores[1].id, value_cents=45_000_000
    )
    _registrar_proposta(
        sessao, cenario, company_id=cenario.fornecedores[2].id, value_cents=38_000_000
    )
    service.close_receipt(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        package_id=cenario.pacote.id,
        data=validation.ClosingInput(date=date(2026, 8, 31)),
        reference_date=REFERENCIA,
    )
    line = service.find_process(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        package_id=cenario.pacote.id,
        reference_date=REFERENCIA,
    )
    assert line is not None
    items = tuple(
        validation.TechnicalEvaluation(
            proposal_id=proposal.id,
            score=score,
            approved=approved,
            deviations="Sem desvios.",
            version=proposal.version,
        )
        for proposal, (score, approved) in zip(
            line.proposals, [(90, True), (80, True), (70, False)], strict=False
        )
    )
    service.equalize_technically(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        package_id=cenario.pacote.id,
        data=validation.TechnicalInput(
            date=date(2026, 9, 10),
            evaluations=items,
            justification="Mercado local com poucos fornecedores para o escopo completo.",
        ),
        reference_date=REFERENCIA,
    )
    service.equalize_commercially(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        package_id=cenario.pacote.id,
        data=validation.CommercialInput(
            date=date(2026, 9, 15),
            weight_technical=50,
            weight_commercial=50,
            version=_processo(sessao, cenario).version,
        ),
        reference_date=REFERENCIA,
    )


def _recomendar(sessao: Session, cenario: CenarioProcessos, *, posicao: int = 0) -> None:
    line = service.find_process(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        package_id=cenario.pacote.id,
        reference_date=REFERENCIA,
    )
    assert line is not None
    proposta = line.proposals[posicao]
    service.recommend_award(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        package_id=cenario.pacote.id,
        data=validation.RecommendationInput(
            proposal_id=proposta.id, value_cents=40_000_000, date=date(2026, 9, 20)
        ),
        reference_date=REFERENCIA,
    )


def _aprovar(sessao: Session, cenario: CenarioProcessos) -> None:
    service.approve_award(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        package_id=cenario.pacote.id,
        data=validation.ApprovalInput(approver_id=cenario.vitor.person_id, date=date(2026, 9, 22)),
        reference_date=REFERENCIA,
    )


def test_o_formulario_da_recomendacao_lista_as_aprovadas(
    sessao: Session, cenario_processos: CenarioProcessos
) -> None:
    _fluxo_ate_negociacao(sessao, cenario_processos)

    resposta = routes.process_action_form(
        requisicao(
            f"/api/suprimentos/processos/{cenario_processos.pacote.id}/acao/recomendacao",
            email=ANA,
            params=_params(cenario_processos),
            rota={"pacote_id": str(cenario_processos.pacote.id), "nome": "recomendacao"},
            alvo="processo-modal-corpo",
        )
    )

    assert resposta.status_code == 200
    corpo = resposta.get_body().decode()
    assert "Recomendar adjudicação" in corpo
    assert "Alfa Fornecimentos de teste" in corpo
    assert "Melhor nota final" in corpo


def test_o_post_da_recomendacao_de_outra_nota_sem_justificativa_e_recusado(
    sessao: Session, cenario_processos: CenarioProcessos
) -> None:
    _fluxo_ate_negociacao(sessao, cenario_processos)
    linha = service.find_process(
        sessao,
        user=cenario_processos.ana,
        scope=_scope(cenario_processos),
        package_id=cenario_processos.pacote.id,
        reference_date=REFERENCIA,
    )
    assert linha is not None
    beta = linha.proposals[1]

    resposta = routes.process_action_save(
        _post(
            cenario_processos,
            "recomendacao",
            proposta=str(beta.id),
            valor="440.000,00",
            data="2026-09-20",
            justificativa="curta",
            consulta="",
        )
    )

    assert resposta.status_code == 422
    corpo = resposta.get_body().decode()
    assert 'id="processo-modal-corpo"' in corpo
    assert "melhor nota final" in corpo
    assert _processo(sessao, cenario_processos).recommendation_on is None


def test_o_post_da_recomendacao_grava_e_a_ficha_mostra_a_linha(
    sessao: Session, cenario_processos: CenarioProcessos
) -> None:
    _fluxo_ate_negociacao(sessao, cenario_processos)
    proposta = sessao.scalars(select(ProcessProposal).order_by(ProcessProposal.id)).first()
    assert proposta is not None

    resposta = routes.process_action_save(
        _post(
            cenario_processos,
            "recomendacao",
            proposta=str(proposta.id),
            valor="400.000,00",
            data="2026-09-20",
            justificativa="",
            consulta="",
        )
    )

    assert resposta.status_code == 200
    processo = _processo(sessao, cenario_processos)
    assert processo.recommendation_on == date(2026, 9, 20)
    assert processo.recommendation_value_cents == 40_000_000
    assert "Recomendação" in resposta.get_body().decode()


def test_o_post_da_aprovacao_com_o_comprador_recebe_403(
    sessao: Session, cenario_processos: CenarioProcessos
) -> None:
    _fluxo_ate_negociacao(sessao, cenario_processos)
    _recomendar(sessao, cenario_processos)

    resposta = routes.process_action_save(
        _post(
            cenario_processos,
            "aprovar",
            aprovador=str(cenario_processos.ana.person_id),
            data="2026-09-22",
            parecer="",
            consulta="",
        )
    )

    assert resposta.status_code == 403
    assert "segregação" in resposta.get_body().decode()
    assert _processo(sessao, cenario_processos).approval_on is None


def test_o_post_da_aprovacao_grava_a_alcada(
    sessao: Session, cenario_processos: CenarioProcessos
) -> None:
    _fluxo_ate_negociacao(sessao, cenario_processos)
    _recomendar(sessao, cenario_processos)

    resposta = routes.process_action_save(
        _post(
            cenario_processos,
            "aprovar",
            aprovador=str(cenario_processos.vitor.person_id),
            data="2026-09-22",
            parecer="Aprovado.",
            consulta="",
        )
    )

    assert resposta.status_code == 200
    assert _processo(sessao, cenario_processos).approval_band == "Gerente de suprimentos"
    assert "Gerente de suprimentos" in resposta.get_body().decode()


def test_o_formulario_da_emissao_do_pedido_traz_o_prazo(
    sessao: Session, cenario_processos: CenarioProcessos
) -> None:
    _fluxo_ate_negociacao(sessao, cenario_processos)
    _recomendar(sessao, cenario_processos)
    _aprovar(sessao, cenario_processos)

    resposta = routes.process_action_form(
        requisicao(
            f"/api/suprimentos/processos/{cenario_processos.pacote.id}/acao/emitir",
            email=ANA,
            params=_params(cenario_processos),
            rota={"pacote_id": str(cenario_processos.pacote.id), "nome": "emitir"},
            alvo="processo-modal-corpo",
        )
    )

    assert resposta.status_code == 200
    corpo = resposta.get_body().decode()
    assert "Emitir pedido" in corpo
    assert "Prazo de entrega" in corpo
    assert "90" in corpo, "o prazo padrão vem da proposta"


def test_o_post_da_emissao_cria_o_pedido_e_a_ficha_mostra_o_numero(
    sessao: Session, cenario_processos: CenarioProcessos
) -> None:
    _fluxo_ate_negociacao(sessao, cenario_processos)
    _recomendar(sessao, cenario_processos)
    _aprovar(sessao, cenario_processos)

    resposta = routes.process_action_save(
        _post(cenario_processos, "emitir", data="2026-09-24", prazo="90", consulta="")
    )

    assert resposta.status_code == 200
    assert sessao.scalars(select(PurchaseOrder)).one().number == "PED-2026-0001"
    marco = sessao.scalars(
        select(PackageMilestone).where(
            PackageMilestone.package_id == cenario_processos.pacote.id,
            PackageMilestone.milestone == "pedido",
        )
    ).one()
    assert marco.real_date == date(2026, 9, 24)
    corpo = resposta.get_body().decode()
    assert "Pedido PED-2026-0001" in corpo


def test_o_visualizador_recebe_403_na_recomendacao(
    sessao: Session, cenario_processos: CenarioProcessos
) -> None:
    _fluxo_ate_negociacao(sessao, cenario_processos)

    resposta = routes.process_action_save(
        requisicao(
            f"/api/suprimentos/processos/{cenario_processos.pacote.id}/acao/recomendacao",
            metodo="POST",
            email=VITOR,
            params=_params(cenario_processos),
            rota={"pacote_id": str(cenario_processos.pacote.id), "nome": "recomendacao"},
            corpo={"proposta": "1", "valor": "400.000,00", "data": "2026-09-20"},
            alvo="processo-modal-corpo",
        )
    )

    assert resposta.status_code == 403
    assert _processo(sessao, cenario_processos).recommendation_on is None
