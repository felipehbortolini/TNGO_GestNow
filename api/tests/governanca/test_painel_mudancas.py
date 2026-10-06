"""Painel de mudanças (ISSUE-026): taxa de aprovação, Pareto e acumulados por mês.

As fórmulas são puras (``calculations``) e a fachada só as alimenta com os fatos do escopo; o
Pareto sai em ordem decrescente e o acumulado fecha em 100%; os acumulados por mês somam as
aprovadas, pelo mês da decisão.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core.scope import Scope
from src.modulos.governanca import calculations, models, routes, service
from tests.governanca import apoio
from tests.governanca.apoio import HOJE
from tests.identidades import requisicao


def _figura(**campos: object) -> calculations.ChangeFigures:
    base: dict[str, object] = {
        "situation": models.SITUATION_APPROVED,
        "request_date": HOJE,
        "origin": "Cliente",
        "kind": "Escopo",
        "cost_cents": 100_000,
        "term_days": 5,
        "decision_date": HOJE + timedelta(days=10),
    }
    base.update(campos)
    return calculations.ChangeFigures(**base)  # type: ignore[arg-type]


# ── Fórmulas ────────────────────────────────────────────────────────────────────────────────


def test_taxa_de_aprovacao_ignora_as_adiadas() -> None:
    figures = [
        _figura(),
        _figura(situation=models.SITUATION_APPROVED_WITH_CONDITIONS),
        _figura(situation=models.SITUATION_REJECTED),
        _figura(situation=models.SITUATION_POSTPONED),
    ]

    assert calculations.approval_rate(figures) == Decimal("66.7")
    assert calculations.approval_rate([_figura(situation=models.SITUATION_POSTPONED)]) is None
    assert calculations.approval_rate([]) is None


def test_contagens_seguem_a_ordem_fixa() -> None:
    lines = calculations.count_lines(
        ["Rejeitada", "Registrada", "Rejeitada"], models.CHANGE_SITUATIONS
    )

    assert [(line.label, line.total) for line in lines] == [("Registrada", 1), ("Rejeitada", 2)]


def test_pareto_desce_com_o_acumulado_ate_cem() -> None:
    lines = calculations.count_lines(["A", "A", "A", "A", "B", "B", "B", "C"], ())

    pareto = calculations.pareto_lines(lines)

    assert [(line.label, line.total) for line in pareto] == [("A", 4), ("B", 3), ("C", 1)]
    assert [line.percent for line in pareto] == [
        Decimal("50.0"),
        Decimal("37.5"),
        Decimal("12.5"),
    ]
    assert [line.cumulative for line in pareto] == [
        Decimal("50.0"),
        Decimal("87.5"),
        Decimal("100.0"),
    ]


def test_acumulados_por_mes_somam_as_aprovadas() -> None:
    figures = [
        _figura(
            request_date=date(2026, 8, 5),
            decision_date=date(2026, 8, 20),
            cost_cents=1_000,
            term_days=2,
        ),
        _figura(
            request_date=date(2026, 9, 2),
            decision_date=date(2026, 9, 10),
            cost_cents=2_000,
            term_days=3,
        ),
        _figura(
            situation=models.SITUATION_REGISTERED,
            request_date=date(2026, 9, 8),
            decision_date=None,
        ),
    ]

    months = calculations.approved_monthly(figures, date(2026, 9, 25))

    assert [
        (item.month.isoformat(), item.approved, item.requested, item.value_cents, item.term_days)
        for item in months
    ] == [
        ("2026-08-01", 1, 1, 1_000, 2),
        ("2026-09-01", 1, 2, 3_000, 5),
    ]


def test_acumulados_sem_solicitacao_sao_vazios() -> None:
    assert calculations.approved_monthly([], HOJE) == ()


# ── Fachada ─────────────────────────────────────────────────────────────────────────────────


def test_o_painel_do_projeto_conta_as_solicitacoes(sessao: Session) -> None:
    projeto = apoio.projeto_com_orcamento(sessao)
    membro = apoio.colaborador(sessao, apoio.MEMBRO)
    usuario = apoio.usuario_de(membro)
    apoio.registrar(sessao, usuario, projeto)
    apoio.registrar(sessao, usuario, projeto, origem="Interna")

    painel = service.change_panel(
        sessao,
        user=usuario,
        scope=Scope(project_id=projeto.id, source="url"),
        reference_date=HOJE,
    )

    assert painel.summary.total == 2
    assert [(line.label, line.total) for line in painel.situations] == [("Registrada", 2)]
    assert [(line.label, line.total) for line in painel.origins] == [
        ("Cliente", 1),
        ("Interna", 1),
    ]
    assert painel.approval_rate is None
    assert painel.mean_decision_days is None
    assert painel.months
    assert painel.months[-1].requested == 2


# ── Tela ────────────────────────────────────────────────────────────────────────────────────


def test_o_registro_traz_a_aba_do_painel(sessao: Session) -> None:
    projeto = apoio.projeto_com_orcamento(sessao)
    membro = apoio.colaborador(sessao, apoio.MEMBRO)
    usuario = apoio.usuario_de(membro)
    apoio.registrar(sessao, usuario, projeto)

    resposta = routes.change_register(
        requisicao(
            "/api/governanca/mudancas", email=apoio.MEMBRO, params={"projeto": str(projeto.id)}
        )
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "Painel" in corpo
    assert "Pareto por origem" in corpo
    assert 'data-grafico="pareto"' in corpo
    assert "Taxa de aprovação" in corpo


def test_o_excel_do_registro_traz_as_tabelas_do_painel(sessao: Session) -> None:
    projeto = apoio.projeto_com_orcamento(sessao)
    membro = apoio.colaborador(sessao, apoio.MEMBRO)
    usuario = apoio.usuario_de(membro)
    apoio.registrar(sessao, usuario, projeto)

    resposta = routes.change_register_excel(
        requisicao(
            "/api/governanca/mudancas/excel",
            email=apoio.MEMBRO,
            params={"projeto": str(projeto.id)},
        )
    )

    assert resposta.status_code == 200
    assert "spreadsheet" in resposta.headers["Content-Type"]
    assert resposta.get_body(), "a planilha do registro não pode sair vazia"
