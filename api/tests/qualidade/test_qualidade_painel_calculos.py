"""Os cálculos do painel da Qualidade (ISSUE-071): as fronteiras das fórmulas, o Pareto e a série.

Os testes chamam o serviço direto, com o cenário na transação do teste e a data de referência
25/09/2026; a reincidência nasce do fluxo real (verificação ineficaz), nunca de um campo.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core.scope import Scope
from src.modulos.central_acoes import service as actions
from src.modulos.central_acoes.validation import CompletionRequest
from src.modulos.configuracoes.models import Discipline
from src.modulos.qualidade import calculations, painel_service, service
from src.modulos.qualidade.validation import (
    ActionInput,
    AnalysisInput,
    ResponsibleInput,
)
from tests.apoio_qualidade import (
    REFERENCIA,
    Cenario,
    itp_aprovado,
    nova_abertura,
    nova_inspecao,
    nova_verificacao,
)


def _escopo(cenario: Cenario) -> Scope:
    return Scope(project_id=cenario.projeto.id, source="padrao")


def _painel(sessao: Session, cenario: Cenario) -> painel_service.QualityPanel:
    return painel_service.quality_panel(
        sessao, user=cenario.mario, scope=_escopo(cenario), reference_date=REFERENCIA
    )


def _abrir(sessao: Session, cenario: Cenario, **campos: object) -> str:
    resultado = service.open_rnc(
        sessao,
        user=cenario.mario,
        data=nova_abertura(cenario, **campos),
        reference_date=REFERENCIA,
    )
    return resultado.code


def _analisar(sessao: Session, cenario: Cenario, codigo: str, *, custo: int = 0) -> None:
    service.assign_analysis(
        sessao,
        user=cenario.mario,
        code=codigo,
        data=ResponsibleInput(responsible_id=cenario.mario.person_id),
        reference_date=REFERENCIA,
    )
    service.record_analysis(
        sessao,
        user=cenario.mario,
        code=codigo,
        data=AnalysisInput(
            method="5 porquês",
            root_cause="Soldador sem qualificação para o processo e a espessura da junta.",
            disposition="Retrabalho",
            actions=(
                ActionInput(
                    subject="Refazer o serviço reprovado da frente de teste",
                    responsible_id=cenario.mario.person_id,
                    planned_date=REFERENCIA + timedelta(days=5),
                    description="",
                ),
            ),
            cost_cents=custo,
        ),
        reference_date=REFERENCIA,
    )


def _concluir_acoes(sessao: Session, cenario: Cenario, codigo: str) -> None:
    for acao in actions.actions_of_origin(
        sessao, user=cenario.mario, origin_kind="RNC", reference=codigo, reference_date=REFERENCIA
    ):
        actions.complete_action(
            sessao,
            user=cenario.mario,
            request=CompletionRequest(
                action_id=acao.id, completed_on=REFERENCIA, version=acao.version
            ),
            reference_date=REFERENCIA,
        )


def _encerrar(sessao: Session, cenario: Cenario, codigo: str, *, eficaz: bool = True) -> None:
    """Encerra a RNC pelo fluxo; ineficaz na primeira verificação deixa a reincidência."""
    _analisar(sessao, cenario, codigo)
    _concluir_acoes(sessao, cenario, codigo)
    service.send_to_verification(
        sessao, user=cenario.mario, code=codigo, version=None, reference_date=REFERENCIA
    )
    if not eficaz:
        service.verify_effectiveness(
            sessao,
            user=cenario.gil,
            code=codigo,
            data=nova_verificacao(
                effective=False, text="A ação não resolveu o problema; nova tentativa."
            ),
            reference_date=REFERENCIA,
        )
        service.send_to_verification(
            sessao, user=cenario.mario, code=codigo, version=None, reference_date=REFERENCIA
        )
    service.verify_effectiveness(
        sessao, user=cenario.gil, code=codigo, data=nova_verificacao(), reference_date=REFERENCIA
    )


def _inspecionar(
    sessao: Session, cenario: Cenario, itp: object, ponto: object, resultado: str, **campos: object
) -> None:
    service.record_inspection(
        sessao,
        user=cenario.mario,
        data=nova_inspecao(
            itp_id=itp.id,  # type: ignore[attr-defined]
            point_id=ponto.id,  # type: ignore[attr-defined]
            inspector_id=cenario.mario.person_id,
            result=resultado,
            **campos,
        ),
        reference_date=REFERENCIA,
    )


# ── Fronteiras dos indicadores ───────────────────────────────────────────────────────────────


def test_sem_registros_os_indicadores_sao_nulos(sessao: Session, cenario: Cenario) -> None:
    indicators = painel_service.quality_indicators(
        sessao, user=cenario.mario, scope=_escopo(cenario), reference_date=REFERENCIA
    )

    assert indicators.open_rncs == 0
    assert indicators.average_treatment_days is None
    assert indicators.first_time_effectiveness_pct is None
    assert indicators.inspection_approval_pct is None
    assert indicators.audit_conformity_pct is None
    assert indicators.audit_program_adherence_pct is None
    assert indicators.non_quality_cost_cents == 0
    assert _painel(sessao, cenario).is_empty


def test_a_ressalva_conta_como_aprovada(sessao: Session, cenario: Cenario) -> None:
    itp = itp_aprovado(sessao, cenario)
    ponto = itp.points[0]

    _inspecionar(sessao, cenario, itp, ponto, "Aprovado")
    _inspecionar(
        sessao,
        cenario,
        itp,
        ponto,
        "Aprovado com ressalva",
        observation="Liberado com acompanhamento reforçado da solda.",
    )
    _inspecionar(
        sessao,
        cenario,
        itp,
        ponto,
        "Reprovado",
        observation="Fora do critério do ITP no ultrassom.",
        severity="Maior",
        containment="Frente bloqueada até o retrabalho da junta.",
    )

    indicators = painel_service.quality_indicators(
        sessao, user=cenario.mario, scope=_escopo(cenario), reference_date=REFERENCIA
    )

    assert (indicators.inspections, indicators.rejected_inspections) == (3, 1)
    assert indicators.inspection_approval_pct == Decimal("66.7")


def test_a_reincidencia_derruba_a_eficacia(sessao: Session, cenario: Cenario) -> None:
    primeira = _abrir(sessao, cenario)
    _encerrar(sessao, cenario, primeira)
    segunda = _abrir(sessao, cenario)
    _encerrar(sessao, cenario, segunda, eficaz=False)

    indicators = painel_service.quality_indicators(
        sessao, user=cenario.mario, scope=_escopo(cenario), reference_date=REFERENCIA
    )

    assert indicators.closed_rncs == 2
    assert indicators.first_time_effectiveness_pct == Decimal("50.0")
    assert calculations.first_time_effectiveness_pct([]) is None
    assert calculations.first_time_effectiveness_pct([0, 1, 1]) == Decimal("33.3")


# ── Pareto e série ───────────────────────────────────────────────────────────────────────────


def test_o_pareto_desempata_pelo_custo_e_acumula(sessao: Session, cenario: Cenario) -> None:
    sessao.add_all([Discipline(name="Civil"), Discipline(name="Tubulação")])
    sessao.flush()
    for _ in range(2):
        _abrir(sessao, cenario, discipline="Mecânica")
    civis = [_abrir(sessao, cenario, discipline="Civil") for _ in range(2)]
    _analisar(sessao, cenario, civis[0], custo=100_000)

    panel = _painel(sessao, cenario)

    assert [linha.name for linha in panel.by_discipline] == ["Civil", "Mecânica"]
    assert [linha.total for linha in panel.by_discipline] == [2, 2]
    assert panel.by_discipline[0].cost_cents == 100_000
    assert panel.by_discipline[0].pct == Decimal("50.0")
    assert panel.by_discipline[0].accumulated_pct == Decimal("50.0")
    assert panel.by_discipline[1].accumulated_pct == Decimal("100.0")
    assert [linha.name for linha in panel.by_origin] == ["Inspeção"]


def test_a_serie_tem_seis_meses_e_fecha_na_referencia(sessao: Session, cenario: Cenario) -> None:
    _abrir(sessao, cenario, rnc_date=date(2026, 8, 10))
    _abrir(sessao, cenario, rnc_date=REFERENCIA)
    encerrada = _abrir(sessao, cenario, rnc_date=date(2026, 7, 1))
    _encerrar(sessao, cenario, encerrada)
    itp = itp_aprovado(sessao, cenario)
    _inspecionar(sessao, cenario, itp, itp.points[0], "Aprovado", inspection_date=date(2026, 9, 10))

    panel = _painel(sessao, cenario)

    assert [ponto.month for ponto in panel.series] == [
        "2026-04",
        "2026-05",
        "2026-06",
        "2026-07",
        "2026-08",
        "2026-09",
    ]
    primeiro = panel.series[0]
    assert (primeiro.opened, primeiro.closed, primeiro.open, primeiro.inspections) == (0, 0, 0, 0)
    assert primeiro.approval_pct is None
    julho = panel.series[3]
    assert (julho.opened, julho.open) == (1, 1)
    setembro = panel.series[-1]
    assert (setembro.opened, setembro.closed, setembro.open) == (1, 1, 2)
    assert (setembro.inspections, setembro.approval_pct) == (1, Decimal("100.0"))
    agosto = panel.series[4]
    assert (agosto.opened, agosto.open) == (1, 2)


def test_a_pauta_lista_os_motivos_e_ordena_pelo_atraso(sessao: Session, cenario: Cenario) -> None:
    vencida = _abrir(sessao, cenario, severity="Menor", rnc_date=REFERENCIA - timedelta(days=90))
    _analisar(sessao, cenario, vencida)
    critica = _abrir(sessao, cenario, severity="Crítica")
    verificacao = _abrir(sessao, cenario)
    _analisar(sessao, cenario, verificacao)
    _concluir_acoes(sessao, cenario, verificacao)
    service.send_to_verification(
        sessao, user=cenario.mario, code=verificacao, version=None, reference_date=REFERENCIA
    )

    panel = _painel(sessao, cenario)
    depois = painel_service.quality_panel(
        sessao,
        user=cenario.mario,
        scope=_escopo(cenario),
        reference_date=REFERENCIA + timedelta(days=60),
    )

    por_codigo = {entry.line.code: entry for entry in panel.agenda}
    assert set(por_codigo) == {vencida, critica}
    assert por_codigo[vencida].reasons == ("prazo de tratamento vencido há 45 dias",)
    assert por_codigo[critica].reasons == ("severidade crítica",)
    assert panel.agenda[0].line.code == vencida
    vencida_depois = next(entry for entry in depois.agenda if entry.line.code == verificacao)
    assert vencida_depois.reasons == ("verificação de eficácia vencida",)
