"""Validação do Registro de riscos (ISSUE-064): avaliação, exclusão e categoria."""

from __future__ import annotations

from src.modulos.riscos import validation
from src.modulos.riscos.validation import AssessmentInput, DeletionInput

DIMENSOES = {"prazo": 2, "custo": 4, "escopo": None, "sms": None, "imagem": None, "legal": None}


def _avaliacao(**mudancas: object) -> AssessmentInput:
    base: dict[str, object] = {
        "kind": "inerente",
        "probability": 3,
        "impact": 4,
        "dimensions": DIMENSOES,
    }
    return AssessmentInput(**{**base, **mudancas})  # type: ignore[arg-type]


def test_avaliacao_valida_nao_tem_problema() -> None:
    assert validation.assessment_problems(_avaliacao()) == {}


def test_impacto_elevado_acima_do_pior_caso_e_aceito() -> None:
    assert validation.assessment_problems(_avaliacao(impact=5)) == {}


def test_impacto_menor_que_a_maior_dimensao_e_recusado() -> None:
    problemas = validation.assessment_problems(_avaliacao(impact=3))

    assert "i" in problemas
    assert "(4)" in problemas["i"]


def test_sem_dimensao_avaliada_e_recusado() -> None:
    problemas = validation.assessment_problems(_avaliacao(dimensions={"prazo": None}))

    assert "dimensoes" in problemas


def test_probabilidade_fora_de_um_a_cinco_e_recusada() -> None:
    assert "p" in validation.assessment_problems(_avaliacao(probability=0))
    assert "p" in validation.assessment_problems(_avaliacao(probability=6))
    assert "p" in validation.assessment_problems(_avaliacao(probability=None))


def test_prazo_e_custo_negativos_sao_recusados() -> None:
    problemas = validation.assessment_problems(
        _avaliacao(schedule_impact_days=1000, cost_impact_cents=-1)
    )

    assert set(problemas) == {"impactoPrazoDias", "impactoCustoCentavos"}


def test_exclusao_exige_um_motivo_da_lista() -> None:
    assert "motivo" in validation.deletion_problems(DeletionInput(reason=""))
    assert validation.deletion_problems(DeletionInput(reason=validation.DELETION_REASONS[0])) == {}


def test_exclusao_por_outro_exige_o_detalhe() -> None:
    curto = DeletionInput(reason=validation.OTHER_REASON, note="curto")
    completo = DeletionInput(reason=validation.OTHER_REASON, note="registrado por engano na ata")

    assert "observacao" in validation.deletion_problems(curto)
    assert validation.deletion_problems(completo) == {}


def test_texto_do_motivo_leva_o_detalhe_quando_ha() -> None:
    motivo = validation.DELETION_REASONS[0]

    assert validation.deletion_reason_text(DeletionInput(reason=motivo)) == motivo
    assert (
        validation.deletion_reason_text(DeletionInput(reason=motivo, note=" x ")) == f"{motivo}: x"
    )


def test_filtros_da_consulta_padrao_mostram_so_os_ativos_pelo_residual() -> None:
    filtros = validation.parse_filters({})

    assert filtros.situation == validation.SITUATION_ACTIVE
    assert filtros.assessment == validation.RESIDUAL
    assert filtros.page == 1


def test_leitores_de_campo_tratam_o_texto_do_formulario() -> None:
    assert validation.parse_id("12") == 12
    assert validation.parse_id("x") is None
    assert validation.parse_level("5") == 5
    assert validation.parse_cents("1.850.000,00") == 185_000_000
    assert validation.parse_cents("") is None
    assert validation.parse_days("30") == 30
