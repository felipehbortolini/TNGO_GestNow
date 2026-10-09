"""As fórmulas da emissão do processo de compra (ISSUE-060): cronograma, folga e numeração.

Todas as funções são puras; os casos de fronteira são o arredondamento do cronograma padrão de
fabricação, o valor no próprio teto da alçada e no próprio saldo da EAC, a folga que zera e a
série de numeração que vira a centena.
"""

from __future__ import annotations

from datetime import date

from src.core import numbering
from src.modulos.suprimentos import calculations, validation


def test_o_cronograma_de_fabricacao_distribui_os_seis_marcos_na_janela() -> None:
    schedule = calculations.manufacturing_schedule(date(2026, 9, 1), date(2026, 11, 30))

    assert [name for name, _ in schedule] == [
        "Aprovação de documentos",
        "Matéria-prima",
        "Fabricação",
        "Inspeção / FAT",
        "Embarque",
        "Entrega",
    ]
    assert [planned for _, planned in schedule] == [
        date(2026, 9, 15),
        date(2026, 9, 28),
        date(2026, 11, 8),
        date(2026, 11, 17),
        date(2026, 11, 24),
        date(2026, 11, 30),
    ], "as proporções do protótipo, arredondadas para cima na metade"


def test_o_cronograma_de_uma_janela_curta_nao_passa_da_entrega() -> None:
    schedule = calculations.manufacturing_schedule(date(2026, 9, 1), date(2026, 9, 2))

    assert all(date(2026, 9, 1) <= planned <= date(2026, 9, 2) for _, planned in schedule)
    assert schedule[-1][1] == date(2026, 9, 2)


def test_a_folga_do_pedido_e_o_ros_menos_a_previsao() -> None:
    assert calculations.delivery_slack_days(date(2026, 11, 20), date(2026, 11, 5)) == 15
    assert calculations.delivery_slack_days(date(2026, 11, 5), date(2026, 11, 5)) == 0, (
        "a fronteira é o zero"
    )
    assert calculations.delivery_slack_days(date(2026, 11, 5), date(2026, 11, 6)) == -1
    assert calculations.delivery_slack_days(None, date(2026, 11, 5)) is None
    assert calculations.delivery_slack_days(date(2026, 11, 5), None) is None


def test_a_recomendacao_exige_justificativa_fora_da_melhor_nota_ou_qualificacao() -> None:
    assert calculations.recommendation_requires_justification(1, calculations.QUALIFIED) is False
    assert calculations.recommendation_requires_justification(2, calculations.QUALIFIED) is True
    assert calculations.recommendation_requires_justification(None, None) is True
    assert (
        calculations.recommendation_requires_justification(1, calculations.IN_QUALIFICATION) is True
    ), "não qualificado exige justificativa mesmo sendo a melhor nota"
    assert calculations.recommendation_requires_justification(1, calculations.BLOCKED) is True


def test_o_lli_antes_do_gate_exige_a_aprovacao_especifica() -> None:
    requisicao = date(2026, 8, 1)
    inicio = date(2026, 8, 15)

    assert (
        calculations.lli_before_gate(
            lli=True, requisition=requisicao, project_start=inicio, gate_date=None
        )
        is True
    )
    assert (
        calculations.lli_before_gate(
            lli=True, requisition=requisicao, project_start=inicio, gate_date=date(2026, 8, 5)
        )
        is False
    ), "com o gate registrado a aprovação segue"
    assert (
        calculations.lli_before_gate(
            lli=False, requisition=requisicao, project_start=inicio, gate_date=None
        )
        is False
    )
    assert (
        calculations.lli_before_gate(
            lli=True, requisition=date(2026, 8, 15), project_start=inicio, gate_date=None
        )
        is False
    ), "no próprio dia do início não está antes do gate"
    assert (
        calculations.lli_before_gate(
            lli=True, requisition=requisicao, project_start=None, gate_date=None
        )
        is False
    )


def test_a_numeracao_do_pedido_e_do_contrato_e_global_por_ano() -> None:
    assert numbering.next_series_number([], prefix="PED", year=2026, digits=4) == "PED-2026-0001"
    assert (
        numbering.next_series_number(
            ["PED-2026-0014", "PED-2026-0002", "CT-2026-028"],
            prefix="PED",
            year=2026,
            digits=4,
        )
        == "PED-2026-0015"
    ), "o maior número do prefixo e do ano, como o protótipo"
    assert (
        numbering.next_series_number(["PED-2025-099"], prefix="PED", year=2026, digits=4)
        == "PED-2026-0001"
    ), "o ano separa as séries"
    assert numbering.next_series_number(["CT-2026-028"], prefix="CT", year=2026) == "CT-2026-029"
    assert (
        numbering.next_series_number(["PED-2026-999"], prefix="PED", year=2026, digits=4)
        == "PED-2026-1000"
    ), "do milésimo em diante o número cresce"


def test_a_justificativa_da_recomendacao_tem_a_mensagem_do_caso() -> None:
    entrada = validation.RecommendationInput(
        proposal_id=1, value_cents=1_000, date=date(2026, 9, 20)
    )

    fora_da_melhor = validation.recommendation_problems(
        entrada,
        reference_date=date(2026, 9, 25),
        situation=validation.ProposalSituation(
            approved=True,
            registered=True,
            blocked=False,
            name="Alfa",
            not_best=True,
            needs_justification=True,
        ),
    )
    assert "melhor nota final" in (fora_da_melhor.get("justificativa") or "")

    sem_qualificacao = validation.recommendation_problems(
        entrada,
        reference_date=date(2026, 9, 25),
        situation=validation.ProposalSituation(
            approved=True,
            registered=True,
            blocked=False,
            name="Alfa",
            not_best=False,
            needs_justification=True,
        ),
    )
    assert "não está qualificado" in (sem_qualificacao.get("justificativa") or "")


def test_o_limite_do_saldo_da_eac_avisa_so_quando_supera() -> None:
    assert (
        validation.eac_balance_problem(
            code="2.1.1", balance_cents=60_000_000, value_cents=60_000_000
        )
        is None
    ), "o valor no próprio saldo passa"
    over = validation.eac_balance_problem(
        code="2.1.1", balance_cents=60_000_000, value_cents=60_000_001
    )
    assert over is not None
    assert "2.1.1" in over
    assert "R$ 600.000,00" in over
