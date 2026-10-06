"""Part of the Governança module in the demonstration load (ISSUE-023, D6).

Reads the changes (``mudancas``) of the prototype mocks, already converted (``prototype_collection``),
and writes them through the facade of the module, in the name of the demonstration Admin, with every date
moved to the reference date of the run (``shift_date``). The code of each change is reserved from the
sequence of its project and must be the prototype's (``DemonstrationNumberError`` otherwise), so the
first real request continues the numbering (``SM-TN-2026-0012``).

Two things of the prototype are not written yet because the table they point to belongs to a module
that arrives later (D9): the transfers between EAC items (``remanejamentos``) and the EAC items of the
impact (``eacItens``) wait for Financeiro, which owns ``eac_item``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from src.carga import prototype_collection, register, shift_date
from src.carga.plataforma import ADMIN_EMAIL
from src.core import calendario
from src.modulos.configuracoes import service as configuracoes
from src.modulos.governanca import lessons_calculations as lessons_calc
from src.modulos.governanca import lessons_service, service
from src.modulos.governanca.service import (
    SeedAnalysis,
    SeedChange,
    SeedClosing,
    SeedDecision,
    SeedImpact,
)

type Mover = Callable[[str], date]

PART_NAME = "governanca"
DEFAULT_ANALYSIS_DAYS = 10


def load(session: Session, reference_date: date) -> None:
    """Write every change of the demonstration, in the order of the prototype."""
    author = configuracoes.find_access_by_email(session, ADMIN_EMAIL)
    if author is None:
        message = "O Admin da demonstração não está no cadastro: a parte da plataforma roda antes."
        raise LookupError(message)
    lookup = _Lookup.build(session)
    analysis_days = _analysis_days()
    for source in prototype_collection("mudancas"):
        seed = _seed_change(
            source, lookup=lookup, reference_date=reference_date, analysis_days=analysis_days
        )
        service.load_demonstration_change(
            session, author_id=author.id, seed=seed, reference_date=reference_date
        )
    for source in prototype_collection("licoes"):
        lessons_service.load_demonstration_lesson(
            session,
            author_id=author.id,
            seed=_seed_lesson(source, lookup=lookup, reference_date=reference_date),
            reference_date=reference_date,
        )


class _Lookup:
    """The ids of the register the prototype points to: projects by its id, people by its id."""

    def __init__(
        self,
        projects: Mapping[int, int],
        people: Mapping[int, int],
        eac_revisions: Mapping[str, int],
        eap_revisions: Mapping[str, int],
    ) -> None:
        self.projects = projects
        self.people = people
        self.eac_revisions = eac_revisions
        self.eap_revisions = eap_revisions

    @classmethod
    def build(cls, session: Session) -> _Lookup:
        real_projects = {item.code: item.id for item in configuracoes.list_project_details(session)}
        projects = {
            source["id"]: real_projects[source["codigo"]]
            for source in prototype_collection("projetos")
        }
        people = {
            source["id"]: person_id
            for source in prototype_collection("pessoas")
            if (person_id := configuracoes.find_person_id_by_email(session, source["email"]))
        }
        return cls(
            projects=projects,
            people=people,
            eac_revisions=_revisions("eacRevisoes"),
            eap_revisions=_revisions("eapRevisoes"),
        )


def _revisions(collection: str) -> dict[str, int]:
    """The revision of the baseline each change generated: ``smRef`` of the revision, by code."""
    return {
        source["smRef"]: source["revisao"]
        for source in prototype_collection(collection)
        if source.get("smRef")
    }


def _analysis_days() -> int:
    parameters = prototype_collection("parametros").get("mudancas", {})
    return int(parameters.get("prazoAnaliseDias", DEFAULT_ANALYSIS_DAYS))


def _seed_change(
    source: Mapping[str, Any], *, lookup: _Lookup, reference_date: date, analysis_days: int
) -> SeedChange:
    def moved(text: str) -> date:
        return shift_date(date.fromisoformat(text), reference_date)

    request_date = moved(source["dataSolicitacao"])
    emergency = source.get("emergencia") or {}
    closing = source.get("encerramentoDetalhe") or {}
    code = source["codigo"]
    return SeedChange(
        project_id=lookup.projects[source["projetoId"]],
        code=code,
        requester_person_id=lookup.people[source["solicitanteId"]],
        title=source["titulo"],
        kind=source["tipo"],
        origin=source["origem"],
        priority=source["prioridade"],
        request_date=request_date,
        description=source["descricao"],
        situation=source["situacao"],
        resource_source=source.get("fonteRecurso"),
        authority=source.get("alcada"),
        emergency_start=moved(emergency["inicio"]) if emergency else None,
        emergency_justification=emergency.get("justificativa"),
        implementation_start=_optional(source.get("implementacao"), "inicio", moved),
        closing_date=moved(source["encerramento"]) if source.get("encerramento") else None,
        closing=SeedClosing(
            closed_by_person_id=lookup.people.get(closing.get("porId")),
            schedule=closing.get("cronograma"),
            contract=closing.get("contrato"),
            risks=closing.get("riscos"),
            note=closing.get("observacao") or None,
        ),
        eac_revision=lookup.eac_revisions.get(code, closing.get("eacRevisao")),
        eap_revision=lookup.eap_revisions.get(code, closing.get("eapRevisao")),
        analysis=_seed_analysis(source, lookup, request_date, analysis_days, moved),
        impact=_seed_impact(source.get("impacto"), lookup, moved),
        decision=_seed_decision(source.get("decisao"), lookup, moved),
    )


def _optional(block: Mapping[str, Any] | None, key: str, moved: Mover) -> date | None:
    if not block or not block.get(key):
        return None
    return moved(block[key])


def _seed_analysis(
    source: Mapping[str, Any],
    lookup: _Lookup,
    request_date: date,
    analysis_days: int,
    moved: Mover,
) -> SeedAnalysis | None:
    """The analysis in progress; its start is the deadline less the usual days, never before the request."""
    block = source.get("analise")
    if not block:
        return None
    deadline = moved(block["prazo"])
    start = max(request_date, calendario.add_days(deadline, -analysis_days))
    return SeedAnalysis(
        responsible_person_id=lookup.people[block["responsavelId"]],
        start_date=start,
        deadline=deadline,
    )


def _seed_impact(
    block: Mapping[str, Any] | None, lookup: _Lookup, moved: Mover
) -> SeedImpact | None:
    if not block:
        return None
    return SeedImpact(
        analyst_person_id=lookup.people[block["analistaId"]],
        analysis_date=moved(block["dataAnalise"]),
        cost_cents=int(block["custoCentavos"]),
        term_days=int(block["prazoDias"]),
        scope=block["escopo"],
        quality=block["qualidade"],
        risks=block["riscos"],
        safety=block["sms"],
        contract=block["contrato"],
        affects_contract_milestone=bool(block["afetaMarcoContratual"]),
        activities=block.get("atividades") or None,
    )


def _seed_decision(
    block: Mapping[str, Any] | None, lookup: _Lookup, moved: Mover
) -> SeedDecision | None:
    if not block:
        return None
    return SeedDecision(
        decision_date=moved(block["data"]),
        result=block["resultado"],
        conditions=block.get("condicoes") or None,
        justification=block["justificativa"],
        participant_person_ids=tuple(lookup.people[pid] for pid in block["participantesIds"]),
    )


def _seed_lesson(
    source: Mapping[str, Any], *, lookup: _Lookup, reference_date: date
) -> lessons_service.SeedLesson:
    """A lesson of ``mock-governanca``: the free text of the origin becomes origin and number."""
    origin, reference = lessons_calc.origin_of_text(source["origem"])
    return lessons_service.SeedLesson(
        project_id=lookup.projects[source["projetoId"]],
        code=source["codigo"],
        author_person_id=lookup.people[source["autorId"]],
        discipline=source["disciplina"],
        registered_on=shift_date(date.fromisoformat(source["data"]), reference_date),
        reuses=int(source.get("reusos", 0)),
        columns={
            "title": source["titulo"],
            "kind": source["tipo"],
            "phase": source["fase"],
            "area": source["area"],
            "origin": origin,
            "origin_ref": reference,
            "what_happened": source["aconteceu"],
            "cause": source["causa"],
            "term_impact_days": source["impactoPrazoDias"],
            "cost_impact_cents": source["impactoCustoCentavos"],
            "recommendation": source["recomendacao"],
            "applicability": source["aplicabilidade"],
            "situation": source["situacao"],
        },
        keywords=tuple(source["palavrasChave"]),
    )


register(PART_NAME, load)
