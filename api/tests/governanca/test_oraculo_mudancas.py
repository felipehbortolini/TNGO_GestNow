"""Oráculo da Governança (ISSUE-023): lista e KPIs de mudanças da demonstração, em 25/09/2026.

Os números saem de ``resumoMudancasDe`` e ``listarMudancasDe`` do protótipo (``api.js``) aplicados ao
``mock-governanca.js`` com a data de referência 25/09/2026 (11 SMs, todas do projeto TN-2026-014, orçamento
de 4.460.000.000 centavos). Sem divergência com o protótipo.
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal

from sqlalchemy import select

from src.carga.plataforma import ADMIN_EMAIL
from src.core.scope import Scope
from src.modulos.configuracoes.models import Collaborator, Person, Project
from src.modulos.governanca import service
from tests.governanca.apoio import usuario_de
from tests.oraculo import OracleContext, register_check

SITUACOES_DO_PROTOTIPO = {
    "Encerrada": 4,
    "Aguardando comitê": 3,
    "Em análise de impacto": 2,
    "Em implementação": 1,
    "Rejeitada": 1,
}


def _visao(context: OracleContext, **filtros: str) -> service.RegisterOverview:
    session = context.session
    admin = session.scalars(
        select(Collaborator)
        .join(Person, Person.id == Collaborator.person_id)
        .where(Person.email == ADMIN_EMAIL)
    ).one()
    projeto = session.scalars(select(Project).where(Project.code == "TN-2026-014")).one()
    return service.register_overview(
        session,
        user=usuario_de(admin),
        scope=Scope(project_id=projeto.id, source="url"),
        filters=service.ChangeFilter(**filtros),
        reference_date=context.reference_date,
    )


def _afirmar_lista_por_situacao(context: OracleContext) -> None:
    visao = _visao(context)
    assert visao.total_in_scope == 11, "11 SMs da demonstracao"
    assert Counter(linha.situation for linha in visao.rows) == SITUACOES_DO_PROTOTIPO
    codigos = [linha.code for linha in visao.rows]
    assert codigos[0] == "SM-TN-2026-0011" and codigos[-1] == "SM-TN-2026-0001", "numeracao do mock"
    aprovadas = _visao(context, situation=service.SITUATION_GROUP_APPROVED)
    assert len(aprovadas.rows) == 5, "aprovadas: 4 encerradas e 1 em implementacao"
    assert len(_visao(context, situation=service.SITUATION_GROUP_ANALYSIS).rows) == 2


def _afirmar_kpis_de_mudancas(context: OracleContext) -> None:
    resumo = _visao(context).summary
    assert resumo.in_analysis == 2, "em analise"
    assert resumo.overdue_analysis == 0, "analises vencidas em 25/09 (prazos 02 e 05/10)"
    assert resumo.awaiting_committee == 3, "aguardando comite"
    assert resumo.postponed == 0, "adiadas"
    assert resumo.implementing == 1, "em implementacao"
    assert resumo.approved == 5, "aprovadas (inclui encerradas)"
    assert resumo.approved_in_year == 5, "aprovadas em 2026"
    assert resumo.approved_value_cents == 120_000_000, "valor aprovado acumulado"
    assert resumo.approved_value_percent == Decimal("2.7"), "% do orcamento"
    assert resumo.approved_term_days == 42, "impacto de prazo acumulado"
    assert resumo.mean_decision_days == 33, "tempo medio de decisao"
    assert resumo.pending_emergencies == 0, "emergenciais sem ratificacao"


register_check("mudancas: lista por situacao", _afirmar_lista_por_situacao)
register_check("mudancas: KPIs do registro", _afirmar_kpis_de_mudancas)
