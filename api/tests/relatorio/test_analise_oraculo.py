"""Oráculo da Análise do período (ISSUE-081/ISSUE-082): as análises do protótipo em 25/09/2026.

Para cada análise dos módulos 02, 03 e 04 — de projeto ou do Portfólio — a detecção no período
devolve as chaves do mock, menos as que os dados não sustentam (``UNSUPPORTED_KEYS``, com a
divergência em ``docs/DIVERGENCIAS-DO-PROTOTIPO.md``). Em 05 e 07 a detecção é vazia: só o texto
é exigido, como no protótipo. No 06 o mock não guarda detecção — o comentário é opcional e
nenhum foi salvo —, então o oráculo afirma as chaves que os dados da demonstração sustentam. A
carga da 082 grava as 18 análises novas (12 de projeto e 6 do Portfólio).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from src.carga import prototype_collection
from src.core.auth import _user_of
from src.core.rbac import GeneralProfile, User
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.relatorio import service
from tests.oraculo import OracleContext, harness, register_check

PORTFOLIO = "(portfólio)"

PROJECT_1 = "TN-2026-014"

# Chaves do mock que o motor do próprio protótipo não produz com os dados do mock-base (CPI 1,02
# e projeção dentro do orçamento no projeto 2, avanço do período acima do previsto, sem entregas
# até o corte, o único marco atrasado fora do período e as áreas do projeto 3 todas acima; no
# Portfólio, o avanço do período da carteira e a aderência/OTD de agosto): divergência registrada
# em ``docs/DIVERGENCIAS-DO-PROTOTIPO.md``; a detecção do GestNow segue o motor e o oráculo
# afirma as chaves sustentadas pelos dados.
UNSUPPORTED_KEYS: Mapping[tuple[str, str, str, str], frozenset[str]] = {
    ("TN-2026-021", "planejamento", "Semanal", "2026-S38"): frozenset({"avanco_periodo"}),
    ("TN-2026-021", "financeiro", "Semanal", "2026-S38"): frozenset({"cpi", "vac"}),
    ("TN-2026-021", "financeiro", "Mensal", "2026-08"): frozenset({"cpi", "vac"}),
    ("TN-2026-021", "suprimentos", "Semanal", "2026-S38"): frozenset({"marcos_atrasados", "otd"}),
    ("TN-2026-021", "suprimentos", "Mensal", "2026-08"): frozenset(
        {"aderencia", "marcos_atrasados", "otd"}
    ),
    ("TN-2026-027", "planejamento", "Semanal", "2026-S38"): frozenset({"areas"}),
    (PORTFOLIO, "planejamento", "Semanal", "2026-S38"): frozenset({"avanco_periodo"}),
    (PORTFOLIO, "suprimentos", "Mensal", "2026-08"): frozenset({"aderencia", "otd"}),
}

# As chaves que os dados da demonstração sustentam no 06, por (projeto, tipo, período): a
# detecção, não o comentário (o mock não a guarda porque nenhum comentário foi salvo).
QUALITY_KEYS: Mapping[tuple[str, str, str], frozenset[str]] = {
    (PROJECT_1, "Semanal", "2026-S38"): frozenset(
        {"rnc_vencidas", "aprovacao_inspecao", "conformidade_auditoria", "auditorias_atrasadas"}
    ),
    (PROJECT_1, "Mensal", "2026-08"): frozenset({"aprovacao_inspecao"}),
    (PORTFOLIO, "Semanal", "2026-S38"): frozenset(
        {"rnc_vencidas", "aprovacao_inspecao", "conformidade_auditoria", "auditorias_atrasadas"}
    ),
    (PORTFOLIO, "Mensal", "2026-08"): frozenset({"aprovacao_inspecao", "conformidade_auditoria"}),
}

MODULES_050607 = ("riscos", "qualidade", "hse")


def _user_and_projects(
    context: OracleContext,
) -> tuple[User, dict[str, int], dict[int, str]]:
    """O Admin do oráculo, os projetos por código e os códigos por id do protótipo."""
    admin = next(
        access
        for access in configuracoes.list_active_access(context.session)
        if access.general_profile == GeneralProfile.ADMIN
    )
    projects = {
        project.code: project.id for project in configuracoes.list_projects(context.session)
    }
    codes = {source["id"]: source["codigo"] for source in prototype_collection("projetos")}
    return _user_of(admin), projects, codes


def _scope_of(source: Mapping[str, Any], projects: dict[str, int], codes: dict[int, str]) -> Scope:
    """O escopo da análise: o projeto do mock, ou o Portfólio quando ``projetoId`` é nulo."""
    project_id = source.get("projetoId")
    if project_id is None:
        return Scope(project_id=None, source="url")
    return Scope(project_id=projects[codes[int(project_id)]], source="url")


def _expected() -> dict[tuple[str, str, str, str], frozenset[str]]:
    """As chaves de desvio do mock, por (projeto, módulo, tipo, período), dos módulos 02, 03 e 04."""
    codes = {source["id"]: source["codigo"] for source in prototype_collection("projetos")}
    expected: dict[tuple[str, str, str, str], frozenset[str]] = {}
    for source in prototype_collection("analisesPeriodo"):
        if source["modulo"] not in ("planejamento", "financeiro", "suprimentos"):
            continue
        project_id = source.get("projetoId")
        code = PORTFOLIO if project_id is None else codes[int(project_id)]
        key = (code, source["modulo"], source["tipo"], source["periodo"])
        keys = frozenset(item["chave"] for item in source.get("desvios") or ())
        expected[key] = keys - UNSUPPORTED_KEYS.get(key, frozenset())
    return expected


def _afirmar_deteccao_do_mock(context: OracleContext) -> None:
    user, projects, _ = _user_and_projects(context)
    failures: list[str] = []
    for (code, module, kind, period), keys in _expected().items():
        project_id = None if code == PORTFOLIO else projects[code]
        view = service.analysis_view(
            context.session,
            user=user,
            scope=Scope(project_id=project_id, source="url"),
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


def _afirmar_deteccao_dos_050607(context: OracleContext) -> None:
    """05 e 07 sem detecção; no 06 as chaves que os dados da demonstração sustentam."""
    user, projects, codes = _user_and_projects(context)
    failures: list[str] = []
    for source in prototype_collection("analisesPeriodo"):
        module = source["modulo"]
        if module not in MODULES_050607:
            continue
        view = service.analysis_view(
            context.session,
            user=user,
            scope=_scope_of(source, projects, codes),
            module=module,
            kind=source["tipo"],
            period=source["periodo"],
            reference_date=context.reference_date,
        )
        found = frozenset(deviation.key for deviation in view.deviations)
        if module == "qualidade":
            project_id = source.get("projetoId")
            code = PORTFOLIO if project_id is None else codes[int(project_id)]
            expected = QUALITY_KEYS.get((code, source["tipo"], source["periodo"]), frozenset())
        else:
            expected = frozenset()
        if found != expected:
            failures.append(
                f"{source.get('projetoId')} {module} {source['tipo']} {source['periodo']}: "
                f"detectado {sorted(found)}; esperado {sorted(expected)}"
            )
    assert not failures, "Deteccao divergente nos 05/06/07:\n" + "\n".join(failures)


def _afirmar_as_analises_da_carga(context: OracleContext) -> None:
    """As 18 análises dos 05/06/07 existem na demonstração, com projeto nulo no Portfólio."""
    _, projects, codes = _user_and_projects(context)
    failures: list[str] = []
    count = 0
    for source in prototype_collection("analisesPeriodo"):
        if source["modulo"] not in MODULES_050607:
            continue
        count += 1
        project_id = source.get("projetoId")
        record = service.analysis_record(
            context.session,
            project_id=None if project_id is None else projects[codes[int(project_id)]],
            module=source["modulo"],
            kind=source["tipo"],
            period=source["periodo"],
        )
        if record is None:
            failures.append(
                f"{source.get('projetoId')} {source['modulo']} "
                f"{source['tipo']} {source['periodo']}: análise ausente"
            )
    assert count == 18, f"o mock tem {count} análises dos 05/06/07; esperado 18"
    assert not failures, "Analises ausentes na demonstracao:\n" + "\n".join(failures)


register_check("analise do periodo: desvios do mock dos 3 modulos", _afirmar_deteccao_do_mock)
register_check(
    "analise do periodo: desvios dos 05/06/07 e do Portfolio", _afirmar_deteccao_dos_050607
)
register_check("analise do periodo: as 18 analises novas da carga", _afirmar_as_analises_da_carga)


def test_oraculo_da_analise_do_periodo(db_session: Session) -> None:
    context = harness.load_demonstration(db_session)

    _afirmar_deteccao_do_mock(context)
    _afirmar_deteccao_dos_050607(context)
    _afirmar_as_analises_da_carga(context)
