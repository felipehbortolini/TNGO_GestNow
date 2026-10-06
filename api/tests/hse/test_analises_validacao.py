"""Validação das análises de risco (ISSUE-074): o que a pessoa digita e o que o estudo exige."""

from __future__ import annotations

from datetime import date

from src.modulos.hse import validation
from src.modulos.hse.validation import (
    AnalysisInput,
    ClosingRecommendationInput,
    RecommendationInput,
    RegisterChoices,
)

REFERENCIA = date(2026, 9, 25)
CHOICES = RegisterChoices(company_ids={1}, person_ids={10, 11})


def _rec(**fields: object) -> RecommendationInput:
    base = RecommendationInput(
        description="Plano de rigging assinado.", responsible_id=10, due_date=date(2026, 10, 3)
    )
    return RecommendationInput(**{**base.__dict__, **fields})  # type: ignore[arg-type]


def _study(**fields: object) -> AnalysisInput:
    base = AnalysisInput(
        project_id=1,
        kind="APR",
        area="Moagem 210",
        title="Içamento da carcaça",
        studied_on=date(2026, 9, 15),
        participant_ids=(10, 11),
        recommendations=(_rec(),),
    )
    return AnalysisInput(**{**base.__dict__, **fields})  # type: ignore[arg-type]


def _problems(**fields: object) -> dict[str, str]:
    return validation.analysis_problems(_study(**fields), CHOICES, reference_date=REFERENCIA)


def test_estudo_completo_nao_tem_problema() -> None:
    assert _problems() == {}


def test_tipo_area_titulo_e_data_sao_obrigatorios() -> None:
    problems = _problems(kind="", area=" ", title="curto", studied_on=None)

    assert set(problems) == {"tipo", "area", "titulo", "data"}


def test_titulo_aceita_de_5_a_150_caracteres() -> None:
    assert "titulo" not in _problems(title="x" * 5)
    assert "titulo" in _problems(title="x" * 4)
    assert "titulo" not in _problems(title="x" * 150)
    assert "titulo" in _problems(title="x" * 151)


def test_data_no_dia_da_referencia_vale_e_depois_nao() -> None:
    assert "data" not in _problems(studied_on=REFERENCIA)
    assert "data" in _problems(studied_on=date(2026, 9, 26))


def test_participante_e_obrigatorio_e_precisa_estar_no_cadastro() -> None:
    assert "participantes" in _problems(participant_ids=())
    assert "participantes" in _problems(participant_ids=(10, 99))


def test_estudo_sem_recomendacao_e_recusado() -> None:
    assert "recomendacoes" in _problems(recommendations=())


def test_a_recomendacao_diz_o_numero_e_o_que_falta() -> None:
    problems = _problems(
        recommendations=(
            _rec(),
            _rec(responsible_id=None),
            _rec(due_date=None),
            _rec(responsible_id=99),
        )
    )

    assert "recomendacao_1" not in problems
    assert problems["recomendacao_2"].startswith("Recomendação 2:")
    assert "responsável" in problems["recomendacao_2"]
    assert "prazo" in problems["recomendacao_3"]
    assert "cadastro" in problems["recomendacao_4"]


def test_descricao_da_recomendacao_aceita_ate_300_caracteres() -> None:
    assert "recomendacao_1" not in _problems(recommendations=(_rec(description="x" * 300),))
    assert "recomendacao_1" in _problems(recommendations=(_rec(description="x" * 301),))


def test_situacao_da_recomendacao_e_aberta_ou_fechada() -> None:
    assert "recomendacao_1" not in _problems(recommendations=(_rec(status="Fechada"),))
    assert "recomendacao_1" in _problems(recommendations=(_rec(status="Cancelada"),))


def test_fechar_pede_a_data_e_nao_aceita_data_futura() -> None:
    closing = validation.recommendation_closing_problems

    assert (
        closing(ClosingRecommendationInput(closed_on=REFERENCIA), reference_date=REFERENCIA) == {}
    )
    assert "data" in closing(ClosingRecommendationInput(closed_on=None), reference_date=REFERENCIA)
    assert "data" in closing(
        ClosingRecommendationInput(closed_on=date(2026, 9, 26)), reference_date=REFERENCIA
    )


def test_evidencia_aceita_ate_300_caracteres() -> None:
    closing = validation.recommendation_closing_problems

    ok = ClosingRecommendationInput(closed_on=REFERENCIA, evidence="x" * 300)
    long = ClosingRecommendationInput(closed_on=REFERENCIA, evidence="x" * 301)
    assert closing(ok, reference_date=REFERENCIA) == {}
    assert "evidencia" in closing(long, reference_date=REFERENCIA)
