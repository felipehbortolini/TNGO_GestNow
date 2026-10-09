"""Fachada da matriz e do painel de riscos (ISSUE-066, D6, D11, D12).

A matriz conta o mesmo que o registro filtrado e leva à célula; o painel reconstrói a evolução
mensal do histórico (sem série gravada) e monta as categorias e a pauta; o envio da pauta passa
pela porta de notificação e fica na trilha como simulado.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.models import AuditEntry, Notification
from src.core.notification import RISK_AGENDA, SIMULATED
from src.core.scope import Scope
from src.modulos.configuracoes.models import Person
from src.modulos.riscos import panel_service, service
from src.modulos.riscos.models import Risk, RiskAssessment
from src.modulos.riscos.validation import RiskFilters
from tests.apoio_riscos import REFERENCIA, Cenario
from tests.identidades import criar_projeto

ENVIOS = "gerente-tn-rsk-001@example.invalid"


def _escopo(cenario: Cenario) -> Scope:
    return Scope(project_id=cenario.projeto.id, source="url")


def _registrar(
    sessao: Session,
    cenario: Cenario,
    *,
    codigo: str,
    avaliacoes: list[tuple[date, int, int, str]],
    natureza: str = "Ameaça",
    situacao: str = "Em tratamento",
    identificado_em: date = date(2026, 4, 1),
    estrategia: str | None = None,
    alvo: str | None = None,
) -> Risk:
    """Grava um risco com o histórico conhecido, do jeito que a carga de demonstração grava."""
    risco = Risk(
        project_id=cenario.projeto.id,
        category_id=cenario.categorias[0].id,
        owner_id=cenario.mario.person_id,
        identified_by_id=cenario.mario.person_id,
        code=codigo,
        title=f"Risco {codigo}",
        nature=natureza,
        origin_type="Manual",
        cause="Causa do risco registrado no teste.",
        consequence="Consequência do risco registrado no teste.",
        situation=situacao,
        identified_on=identificado_em,
        strategy=estrategia,
        plan="Plano de resposta registrado no teste." if estrategia else None,
        target_severity=alvo,
        target_date=date(2027, 1, 15) if alvo else None,
    )
    fatos = [
        RiskAssessment(
            author_id=cenario.mario.person_id,
            kind=kind,
            probability=probability,
            impact=impact,
            assessed_on=when,
        )
        for when, probability, impact, kind in avaliacoes
    ]
    service.record_history(
        sessao, user=cenario.mario, history=service.RiskHistory(risk=risco, assessments=fatos)
    )
    return risco


# ── Matriz: as contagens batem com o registro filtrado ──────────────────────────────────────


def test_a_matriz_conta_o_mesmo_que_o_registro_filtrado(sessao: Session, cenario: Cenario) -> None:
    _registrar(
        sessao,
        cenario,
        codigo="RSK-0001",
        avaliacoes=[(date(2026, 5, 2), 3, 4, "inerente")],
    )
    _registrar(
        sessao,
        cenario,
        codigo="RSK-0002",
        avaliacoes=[
            (date(2026, 6, 1), 2, 2, "inerente"),
            (date(2026, 8, 1), 1, 3, "residual"),
        ],
    )
    _registrar(sessao, cenario, codigo="RSK-0003", avaliacoes=[], situacao="Identificado")

    matriz = panel_service.risk_matrix(
        sessao,
        user=cenario.mario,
        scope=_escopo(cenario),
        assessment="residual",
        nature="",
        reference_date=REFERENCIA,
    )

    assert matriz.total == 2
    assert matriz.unassessed == 1
    celulas = {(cell.probability, cell.impact): cell for cell in matriz.cells}
    assert [risk.code for risk in celulas[(3, 4)].risks] == ["RSK-0001"]
    assert [risk.code for risk in celulas[(1, 3)].risks] == ["RSK-0002"]
    assert celulas[(2, 2)].risks == ()

    assert celulas[(3, 4)].href is not None
    assert "celula=p3%7Ci4" in celulas[(3, 4)].href
    assert celulas[(2, 2)].href is None

    listagem = service.list_risks(
        sessao,
        user=cenario.mario,
        scope=_escopo(cenario),
        filters=RiskFilters(probability=3, impact=4),
        reference_date=REFERENCIA,
    )
    assert [line.code for line in listagem.lines] == ["RSK-0001"]


def test_a_movimentacao_traz_o_inerente_o_residual_e_a_sem_reducao(
    sessao: Session, cenario: Cenario
) -> None:
    _registrar(
        sessao,
        cenario,
        codigo="RSK-0001",
        avaliacoes=[
            (date(2026, 5, 2), 4, 4, "inerente"),
            (date(2026, 6, 2), 4, 4, "residual"),
        ],
        estrategia="Mitigar",
        alvo="moderado",
    )

    matriz = panel_service.risk_matrix(
        sessao,
        user=cenario.mario,
        scope=_escopo(cenario),
        assessment="residual",
        nature="",
        reference_date=REFERENCIA,
    )

    assert len(matriz.movement) == 1
    movimento = matriz.movement[0]
    assert (movimento.inherent_score, movimento.residual_score) == (16, 16)
    assert movimento.no_reduction
    assert "Sem redução após o plano" in matriz.movement_note


# ── Painel: evolução reconstruída e categorias ──────────────────────────────────────────────


def test_a_evolucao_mensal_vem_do_historico(sessao: Session, cenario: Cenario) -> None:
    _registrar(
        sessao,
        cenario,
        codigo="RSK-0001",
        avaliacoes=[
            (date(2026, 4, 10), 3, 4, "inerente"),
            (date(2026, 7, 5), 2, 3, "residual"),
        ],
    )

    painel = panel_service.risk_panel(
        sessao, user=cenario.mario, scope=_escopo(cenario), reference_date=REFERENCIA
    )

    assert [(point.month, point.score) for point in painel.evolution] == [
        ("2026-04", 12),
        ("2026-05", 12),
        ("2026-06", 12),
        ("2026-07", 6),
        ("2026-08", 6),
        ("2026-09", 6),
    ]
    assert painel.evolution[-1].current


def test_a_exposicao_por_categoria_soma_o_score_das_ameacas(
    sessao: Session, cenario: Cenario
) -> None:
    _registrar(
        sessao,
        cenario,
        codigo="RSK-0001",
        avaliacoes=[(date(2026, 5, 2), 3, 4, "inerente")],
    )
    _registrar(
        sessao,
        cenario,
        codigo="RSK-0002",
        avaliacoes=[(date(2026, 5, 3), 2, 3, "inerente")],
    )

    painel = panel_service.risk_panel(
        sessao, user=cenario.mario, scope=_escopo(cenario), reference_date=REFERENCIA
    )

    assert len(painel.categories) == 1
    categoria = painel.categories[0]
    assert (categoria.group, categoria.score, categoria.risks) == ("Técnico", 18, 2)
    assert "categoria=T%C3%A9cnico" in categoria.href


def test_a_pauta_traz_os_riscos_com_motivo(sessao: Session, cenario: Cenario) -> None:
    _registrar(sessao, cenario, codigo="RSK-0001", avaliacoes=[], situacao="Identificado")

    painel = panel_service.risk_panel(
        sessao, user=cenario.mario, scope=_escopo(cenario), reference_date=REFERENCIA
    )

    assert [item.code for item in painel.agenda] == ["RSK-0001"]
    assert painel.agenda[0].reasons == ("Identificado sem avaliação",)
    assert painel.agenda[0].score is None


# ── Envio da pauta pela porta de notificação ────────────────────────────────────────────────


def test_o_envio_da_pauta_registra_na_trilha_com_simulado(
    sessao: Session, cenario: Cenario
) -> None:
    _registrar(sessao, cenario, codigo="RSK-0001", avaliacoes=[], situacao="Identificado")

    resultado = panel_service.send_risk_agenda(
        sessao,
        user=cenario.mario,
        scope=_escopo(cenario),
        reference_date=REFERENCIA,
    )

    assert resultado.situation == SIMULATED
    assert "simulado" in resultado.notice.lower()
    assert resultado.toast_kind == "aviso"

    registro = sessao.get(Notification, resultado.notification_id)
    assert registro is not None
    assert registro.kind == RISK_AGENDA
    assert registro.project_id == cenario.projeto.id
    assert registro.recipients == ENVIOS
    assert "Pauta de escalonamento" in registro.subject
    assert "RSK-0001" in registro.body
    assert "Identificado sem avaliação" in registro.body

    linhas = sessao.scalars(
        select(AuditEntry).where(
            AuditEntry.entity == "notificacao",
            AuditEntry.record_id == resultado.notification_id,
        )
    ).all()
    assert len(linhas) == 1
    assert linhas[0].after is not None
    assert linhas[0].after["situacao"] == "simulado"
    assert linhas[0].after["destinatarios"] == ENVIOS


def test_o_envio_recusa_a_pauta_vazia(sessao: Session, cenario: Cenario) -> None:
    _registrar(
        sessao,
        cenario,
        codigo="RSK-0001",
        avaliacoes=[(date(2026, 5, 2), 3, 4, "inerente")],
    )

    with pytest.raises(InvalidDataError):
        panel_service.send_risk_agenda(
            sessao,
            user=cenario.mario,
            scope=_escopo(cenario),
            reference_date=REFERENCIA,
        )


def test_o_envio_no_portfolio_pede_o_projeto(sessao: Session, cenario: Cenario) -> None:
    _registrar(sessao, cenario, codigo="RSK-0001", avaliacoes=[], situacao="Identificado")

    with pytest.raises(InvalidDataError):
        panel_service.send_risk_agenda(
            sessao,
            user=cenario.mario,
            scope=Scope(project_id=None, source="padrao"),
            reference_date=REFERENCIA,
        )


def test_o_envio_exige_perfil_com_escrita(sessao: Session, cenario: Cenario) -> None:
    _registrar(sessao, cenario, codigo="RSK-0001", avaliacoes=[], situacao="Identificado")

    with pytest.raises(AccessDeniedError):
        panel_service.send_risk_agenda(
            sessao,
            user=cenario.vera,
            scope=_escopo(cenario),
            reference_date=REFERENCIA,
        )


def test_o_envio_sem_gerente_com_email_e_recusado(sessao: Session, cenario: Cenario) -> None:
    sem_email = criar_projeto(sessao, codigo="TN-RSK-003", nome="Projeto sem gerente")
    gerente = sessao.get(Person, sem_email.manager_id)
    if gerente is not None:
        gerente.email = ""
    risco = Risk(
        project_id=sem_email.id,
        category_id=cenario.categorias[0].id,
        owner_id=cenario.mario.person_id,
        identified_by_id=cenario.mario.person_id,
        code="RSK-0100",
        title="Risco sem gerente",
        nature="Ameaça",
        origin_type="Manual",
        cause="Causa do risco sem gerente.",
        consequence="Consequência do risco sem gerente.",
        situation="Identificado",
        identified_on=REFERENCIA,
    )
    service.record_history(sessao, user=cenario.mario, history=service.RiskHistory(risk=risco))

    with pytest.raises(InvalidDataError):
        panel_service.send_risk_agenda(
            sessao,
            user=cenario.mario,
            scope=Scope(project_id=sem_email.id, source="url"),
            reference_date=REFERENCIA,
        )
