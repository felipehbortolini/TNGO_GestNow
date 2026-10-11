"""Oráculo da Análise do período (ISSUE-081): as análises do protótipo em 25/09/2026.

Para cada análise dos módulos 02, 03 e 04 do mock, a detecção no período devolve exatamente as
chaves do mock (a carga do oráculo roda com a data do protótipo, sem deslocamento). As análises
do Portfólio (seis registros) ficam para a ISSUE-082.
"""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy.orm import Session

from src.carga import prototype_collection
from src.core.auth import _user_of
from src.core.rbac import GeneralProfile
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.relatorio import service
from tests.oraculo import OracleContext, harness, register_check

# Chaves do mock que o motor do próprio protótipo não produz com os dados do mock-base (CPI 1,02
# e projeção dentro do orçamento no projeto 2, avanço do período acima do previsto, sem entregas
# até o corte, o único marco atrasado fora do período e as áreas do projeto 3 todas acima):
# divergência registrada em ``docs/DIVERGENCIAS-DO-PROTOTIPO.md``; a detecção do GestNow segue o
# motor e o oráculo afirma as chaves sustentadas pelos dados.
UNSUPPORTED_KEYS: Mapping[tuple[str, str, str, str], frozenset[str]] = {
    ("TN-2026-021", "planejamento", "Semanal", "2026-S38"): frozenset({"avanco_periodo"}),
    ("TN-2026-021", "financeiro", "Semanal", "2026-S38"): frozenset({"cpi", "vac"}),
    ("TN-2026-021", "financeiro", "Mensal", "2026-08"): frozenset({"cpi", "vac"}),
    ("TN-2026-021", "suprimentos", "Semanal", "2026-S38"): frozenset({"marcos_atrasados", "otd"}),
    ("TN-2026-021", "suprimentos", "Mensal", "2026-08"): frozenset(
        {"aderencia", "marcos_atrasados", "otd"}
    ),
    ("TN-2026-027", "planejamento", "Semanal", "2026-S38"): frozenset({"areas"}),
}


def _expected() -> dict[tuple[str, str, str, str], frozenset[str]]:
    """As chaves de desvio do mock, por (projeto, módulo, tipo, período), dos módulos da 081."""
    codes = {source["id"]: source["codigo"] for source in prototype_collection("projetos")}
    expected: dict[tuple[str, str, str, str], frozenset[str]] = {}
    for source in prototype_collection("analisesPeriodo"):
        if source["modulo"] not in service.ANALYSIS_MODULES or source.get("projetoId") is None:
            continue
        key = (codes[source["projetoId"]], source["modulo"], source["tipo"], source["periodo"])
        keys = frozenset(item["chave"] for item in source.get("desvios") or ())
        expected[key] = keys - UNSUPPORTED_KEYS.get(key, frozenset())
    return expected


def _afirmar_deteccao_do_mock(context: OracleContext) -> None:
    session = context.session
    admin = next(
        access
        for access in configuracoes.list_active_access(session)
        if access.general_profile == GeneralProfile.ADMIN
    )
    user = _user_of(admin)
    projects = {project.code: project.id for project in configuracoes.list_projects(session)}
    failures: list[str] = []
    for (code, module, kind, period), keys in _expected().items():
        view = service.analysis_view(
            session,
            user=user,
            scope=Scope(project_id=projects[code], source="url"),
            module=module,
            kind=kind,
            period=period,
            reference_date=context.reference_date,
        )
        found = frozenset(deviation.key for deviation in view.deviations)
        if found != keys:
            failures.append(
                f"{code} {module} {kind} {period}: detectado {sorted(found)}; mock {sorted(keys)}"
            )
    assert not failures, "Deteccao divergente do mock:\n" + "\n".join(failures)


register_check("analise do periodo: desvios do mock dos 3 modulos", _afirmar_deteccao_do_mock)


def test_oraculo_da_analise_do_periodo(db_session: Session) -> None:
    context = harness.load_demonstration(db_session)

    _afirmar_deteccao_do_mock(context)
