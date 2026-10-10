"""Cálculos puros do painel HSE (ISSUE-075, D6): as taxas, a pirâmide, o relato e a nota sugerida.

As taxas são ``eventos x base ÷ HHT`` sem arredondamento (quem formata decide as casas) e valem
``None`` sem HHT; os dias sem afastamento contam da última LTI ou do início do projeto; a
referência da pirâmide é a Bird ou a Heinrich, com o valor de referência do relato de quase
acidentes; a nota HSE sugerida sai da TRIF da empresa contra a do projeto, limitada a 2 pela LTI.
Nada aqui lê o relógio nem o banco.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from src.modulos.hse.calculations import (
    ActionDueLine,
    ClosingLine,
    HseWindow,
    OccurrenceFact,
    actions_on_time,
    almost_miss_report,
    days_without_leave,
    pyramid_chart_label,
    pyramid_reference,
    quantize_half_up,
    rate_base_name,
    rate_hse,
    suggested_hse_note,
    summarize_window,
)

REFERENCIA = date(2026, 9, 25)
HHT_DA_JANELA = Decimal("788070")


# ── Taxas ────────────────────────────────────────────────────────────────────────────────────


def test_taxa_sem_hht_nao_existe() -> None:
    assert rate_hse(7, Decimal(0), 1_000_000) is None


def test_taxa_nao_arredonda_e_escala_com_a_base() -> None:
    esperada = Decimal(7) * Decimal(1_000_000) / HHT_DA_JANELA

    assert rate_hse(7, HHT_DA_JANELA, 1_000_000) == esperada
    assert rate_hse(7, HHT_DA_JANELA, 200_000) == esperada / 5


def test_nome_da_base_das_taxas() -> None:
    assert rate_base_name(1_000_000) == "NBR 14280"
    assert rate_base_name(200_000) == "OSHA"


@pytest.mark.parametrize(
    ("value", "digits", "expected"),
    [
        (Decimal("8.8821"), 2, Decimal("8.88")),
        (Decimal("8.885"), 2, Decimal("8.89")),
        (Decimal("0.05"), 1, Decimal("0.1")),
        (Decimal(0), 2, Decimal("0.00")),
    ],
)
def test_arredondamento_meio_para_cima(value: Decimal, digits: int, expected: Decimal) -> None:
    assert quantize_half_up(value, digits) == expected
    assert quantize_half_up(None, digits) is None


# ── Dias sem afastamento ─────────────────────────────────────────────────────────────────────


def test_dias_sem_afastamento_conta_da_ultima_lti() -> None:
    assert days_without_leave(date(2026, 9, 20), date(2026, 1, 5), REFERENCIA) == 5


def test_sem_lti_conta_do_inicio_do_projeto() -> None:
    assert days_without_leave(None, date(2026, 1, 5), REFERENCIA) == 263


def test_sem_lti_nem_inicio_nao_ha_contagem() -> None:
    assert days_without_leave(None, None, REFERENCIA) is None


def test_dias_sem_afastamento_nunca_e_negativo() -> None:
    assert days_without_leave(date(2026, 9, 26), None, REFERENCIA) == 0


# ── Referência da pirâmide ───────────────────────────────────────────────────────────────────


def test_a_referencia_padrao_e_a_bird() -> None:
    bird = pyramid_reference(None)

    assert bird.kind == "bird"
    assert [termo.value for termo in bird.terms] == [1, 10, 30, 600]
    assert bird.almost_miss_ratio == Decimal("54.5")
    assert bird.chart() == {
        "nome": "Bird",
        "termos": [
            {"niveis": ["grave"], "valor": 1},
            {"niveis": ["leve"], "valor": 10},
            {"niveis": ["dano"], "valor": 30},
            {"niveis": ["quase"], "valor": 600},
        ],
        "nota": "",
    }


def test_a_referencia_heinrich_soma_dano_e_quase_acidente() -> None:
    heinrich = pyramid_reference("heinrich")

    assert heinrich.kind == "heinrich"
    assert heinrich.almost_miss_ratio == Decimal("10")
    assert heinrich.chart()["termos"][-1] == {"niveis": ["dano", "quase"], "valor": 300}
    assert heinrich.chart()["nota"] == "níveis 3 e 4 somados"


def test_referencia_desconhecida_cai_na_bird() -> None:
    assert pyramid_reference("xyz").kind == "bird"


def test_rotulo_plural_do_grafico() -> None:
    assert pyramid_chart_label(1) == "Lesões graves"
    assert pyramid_chart_label(5) == "Desvios"
    assert pyramid_chart_label(None) == ""


# ── Relato de quase acidentes ────────────────────────────────────────────────────────────────


def test_relato_de_quase_acidentes_por_lesao_registravel() -> None:
    assert almost_miss_report(190, 7) == Decimal("27.1")
    assert almost_miss_report(10, 0) is None


# ── Ações no prazo ───────────────────────────────────────────────────────────────────────────


def test_acoes_vencidas_e_concluidas_no_prazo() -> None:
    facts = (
        ActionDueLine(date(2026, 9, 20), None),
        ActionDueLine(date(2026, 9, 23), date(2026, 9, 23)),
        ActionDueLine(date(2026, 9, 26), None),
        ActionDueLine(None, date(2026, 9, 1)),
        ActionDueLine(date(2026, 9, 10), date(2026, 9, 12)),
    )

    assert actions_on_time(facts, REFERENCIA) == (3, 1)


# ── Nota HSE sugerida ────────────────────────────────────────────────────────────────────────


def test_sem_trif_da_empresa_nao_ha_nota() -> None:
    assert suggested_hse_note(None, Decimal("8.88"), 0) is None


@pytest.mark.parametrize(
    ("company_trif", "project_trif", "expected"),
    [
        (Decimal("0.00"), Decimal("8.88"), 5),
        (Decimal("0.00"), Decimal("0.00"), 5),
        (Decimal("8.00"), Decimal("8.00"), 4),
        (Decimal("8.88"), Decimal("8.88"), 4),
        (Decimal("16.00"), Decimal("8.00"), 3),
        (Decimal("8.95"), Decimal("8.88"), 3),
        (Decimal("32.00"), Decimal("8.00"), 2),
        (Decimal("32.01"), Decimal("8.00"), 1),
        (Decimal("0.01"), Decimal("0.00"), 1),
    ],
)
def test_nota_sugerida_nas_fronteiras(
    company_trif: Decimal, project_trif: Decimal, expected: int
) -> None:
    assert suggested_hse_note(company_trif, project_trif, 0) == expected


def test_a_lti_limita_a_nota_a_dois() -> None:
    assert suggested_hse_note(Decimal("8.00"), Decimal("8.00"), 1) == 2
    assert suggested_hse_note(Decimal("0.00"), Decimal("8.88"), 1) == 2


def test_a_base_trocada_muda_a_nota_na_fronteira_do_arredondamento() -> None:
    # 0,67 > 2 x 0,33 (base de um milhão) → nota 2; com a base de 200 mil os mesmos fatos leem
    # 0,13 contra 0,07 e 0,13 ≤ 2 x 0,07 → nota 3. A comparação usa as TRIF como a tela as lê.
    assert suggested_hse_note(Decimal("0.67"), Decimal("0.33"), 0) == 2
    assert suggested_hse_note(Decimal("0.13"), Decimal("0.07"), 0) == 3


# ── Indicadores da janela ────────────────────────────────────────────────────────────────────


def _fact(**campos: object) -> OccurrenceFact:
    base = OccurrenceFact(
        day=REFERENCIA,
        kind="Quase acidente",
        area="Moagem 210",
        company_id=1,
        environmental=False,
        hipo=False,
        days_lost=0,
        days_charged=0,
    )
    return replace(base, **campos)  # type: ignore[arg-type]


def _closing(**campos: object) -> ClosingLine:
    base = ClosingLine(
        project_id=1,
        month=date(2026, 9, 1),
        deviations=0,
        observations=0,
        planned_dds=0,
        held_dds=0,
        inspected_items=0,
        conforming_items=0,
    )
    return replace(base, **campos)  # type: ignore[arg-type]


def test_janela_sem_hht_zera_as_taxas() -> None:
    indicadores = summarize_window(
        HseWindow(
            facts=(),
            closings=(),
            actions=(),
            hours=Decimal(0),
            deviations=0,
            base=1_000_000,
            recommendations_pct=None,
            reference_date=REFERENCIA,
        )
    )

    assert (indicadores.tf, indicadores.trif, indicadores.tg) == (None, None, None)
    assert indicadores.observations_per_10k is None
    assert indicadores.pyramid == (0, 0, 0, 0, 0)


def test_janela_soma_os_indicadores_do_prototipo() -> None:
    facts = (
        _fact(kind="Trabalho restrito"),
        _fact(kind="Tratamento médico", hipo=True),
        _fact(kind="Primeiros socorros"),
        _fact(kind="Dano material", days_lost=3),
        _fact(kind="Quase acidente", days_charged=2),
        _fact(kind="Ambiental", environmental=True),
    )
    indicadores = summarize_window(
        HseWindow(
            facts=facts,
            closings=(
                _closing(
                    deviations=10,
                    observations=30,
                    planned_dds=20,
                    held_dds=19,
                    inspected_items=50,
                    conforming_items=45,
                ),
            ),
            actions=(
                ActionDueLine(date(2026, 9, 20), None),
                ActionDueLine(date(2026, 9, 21), date(2026, 9, 21)),
            ),
            hours=Decimal("100000"),
            deviations=10,
            base=1_000_000,
            recommendations_pct=Decimal("52.9"),
            reference_date=REFERENCIA,
            last_lti=None,
            project_start=date(2026, 1, 5),
        )
    )

    assert (indicadores.lti, indicadores.registrable) == (0, 2)
    assert (indicadores.tf, indicadores.trif) == (Decimal("0.00"), Decimal("20.00"))
    assert indicadores.tg == Decimal("50.0")  # 5 dias x 1.000.000 / 100.000
    assert (indicadores.hipo, indicadores.environmental) == (1, 1)
    assert indicadores.pyramid == (0, 3, 1, 1, 10)
    assert indicadores.almost_miss_report == Decimal("0.5")
    assert (indicadores.dds_pct, indicadores.conformity_pct) == (
        Decimal("95.0"),
        Decimal("90.0"),
    )
    assert indicadores.observations_per_10k == Decimal("3.0")
    assert indicadores.recommendations_pct == Decimal("52.9")
    assert indicadores.actions_on_time_pct == Decimal("50.0")
    assert indicadores.days_without_leave == 263
