"""Part of the Riscos register in the demonstration load (ISSUE-064, D6/Q15).

The 19 risks of the prototype (``riscos``) and the RBS catalogue (``riscoCategorias``) enter
through the facade (``service.create_category`` and ``service.record_history``), with the
history they had: the newest inherent and residual assessments (with their six dimensions), the
timeline of reviews and the approval of the response plan. Every date is shifted by
``shift_date``; on 25/09/2026 (the oracle) nothing moves and the numbers of the prototype come
out whole.

Not loaded here, because the owners of the tables arrive later: the link to the minutes
(``ata_id`` keeps the id the prototype gave the minutes, as the actions do), to the change
request (``smRef``) and to the lesson (``licaoRef``), and the actions, which the Central
de Ações seeds with origin ``Risco``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any

from sqlalchemy.orm import Session

from src.carga import prototype_collection, register, shift_date
from src.carga.plataforma import ADMIN_EMAIL
from src.core.rbac import Bond, GeneralProfile, User
from src.modulos.configuracoes import service as configuracoes
from src.modulos.riscos import service
from src.modulos.riscos.models import (
    Risk,
    RiskAssessment,
    RiskPlanApproval,
    RiskReview,
)
from src.modulos.riscos.validation import INHERENT, RESIDUAL

PART_NAME = "riscos"
DIMENSION_COLUMNS = {
    "prazo": "schedule_dimension",
    "custo": "cost_dimension",
    "escopo": "scope_dimension",
    "sms": "safety_dimension",
    "imagem": "image_dimension",
    "legal": "legal_dimension",
}
APPROVAL_HOUR = time(9, 0)


@dataclass(frozen=True)
class _Lookups:
    """What the conversion needs to turn ids of the prototype into ids of the database."""

    user: User
    reference_date: date
    people: Mapping[int, int]
    projects: Mapping[int, int]
    categories: Mapping[tuple[str, str], int]

    def shifted(self, value: str | None) -> date | None:
        """A date of the prototype moved to the reference date of the run."""
        if not value:
            return None
        return shift_date(date.fromisoformat(value), self.reference_date)

    def moment(self, value: str | None) -> datetime | None:
        """A date of the prototype as a moment of the day, in UTC."""
        day = self.shifted(value)
        return None if day is None else datetime.combine(day, APPROVAL_HOUR, tzinfo=UTC)

    def person(self, mock_id: int | None) -> int | None:
        """The person of the register behind an id of the prototype."""
        return None if mock_id is None else self.people[mock_id]


def load(session: Session, reference_date: date) -> None:
    """Write the catalogue and the risks of the prototype, with their history."""
    lookups = _lookups(session, reference_date)
    for source in prototype_collection("riscos"):
        _record(session, lookups, source)


def _lookups(session: Session, reference_date: date) -> _Lookups:
    access = configuracoes.find_access_by_email(session, ADMIN_EMAIL)
    if access is None:
        message = f"O Admin da demonstração ({ADMIN_EMAIL}) não está no cadastro."
        raise LookupError(message)
    user = User(
        id=access.id,
        person_id=access.person_id,
        name=access.name,
        email=access.email,
        general_profile=GeneralProfile(access.general_profile),
        bond=Bond(access.bond),
        company_id=access.company_id,
    )
    categories = {
        (item["grupo"], item["nome"]): service.create_category(
            session, user=user, group=item["grupo"], name=item["nome"]
        ).id
        for item in prototype_collection("riscoCategorias")
    }
    ids_by_email = {
        person.email.lower(): person.id for person in configuracoes.list_people(session)
    }
    ids_by_code = {project.code: project.id for project in configuracoes.list_projects(session)}
    return _Lookups(
        user=user,
        reference_date=reference_date,
        people={
            person["id"]: ids_by_email[person["email"].lower()]
            for person in prototype_collection("pessoas")
        },
        projects={
            project["id"]: ids_by_code[project["codigo"]]
            for project in prototype_collection("projetos")
        },
        categories=categories,
    )


def _record(session: Session, lookups: _Lookups, source: Mapping[str, Any]) -> None:
    history = service.RiskHistory(
        risk=_risk_of(lookups, source),
        assessments=_assessments_of(lookups, source),
        reviews=_reviews_of(lookups, source.get("revisoes") or ()),
        approvals=_approvals_of(lookups, source.get("aprovacao") or {}),
    )
    service.record_history(session, user=lookups.user, history=history)


def _risk_of(lookups: _Lookups, source: Mapping[str, Any]) -> Risk:
    """One risk of the mock as the table keeps it: identification, plan and closing."""
    closing = source.get("encerramento") or {}
    category = lookups.categories[(source["categoria"], source["subcategoria"])]
    return Risk(
        project_id=lookups.projects[source["projetoId"]],
        category_id=category,
        owner_id=lookups.person(source["donoId"]),
        identified_by_id=lookups.person(source["identificadoPorId"]),
        ata_id=source.get("ataId"),
        plan_responsible_id=lookups.person(source.get("responsavelPlanoId")),
        closed_by_id=lookups.person(closing.get("porId")),
        code=source["codigo"],
        title=source["titulo"],
        nature=source["natureza"],
        origin_type=source["origemTipo"],
        origin=source.get("origem"),
        cause=source["causa"],
        consequence=source["consequencia"],
        description=source.get("descricao"),
        trigger=source.get("gatilho"),
        life_risk=bool(source.get("riscoVida")),
        dimension=source.get("dimensao"),
        schedule_impact_days=source.get("impactoPrazoDias") or 0,
        cost_impact_cents=source.get("impactoCustoCentavos") or 0,
        strategy=source.get("estrategia"),
        plan=source.get("plano"),
        target_severity=source.get("severidadeAlvo"),
        target_date=lookups.shifted(source.get("prazoAlvo")),
        response_cost_cents=source.get("custoRespostaCentavos"),
        instrument=source.get("instrumento"),
        cadence_days=source.get("cadenciaDias"),
        last_review=lookups.shifted(source.get("ultimaRevisao")),
        next_review=lookups.shifted(source.get("proximaRevisao")),
        situation=source["situacao"],
        closing_reason=closing.get("motivo"),
        closing_date=lookups.shifted(closing.get("data")),
        closing_schedule_impact_days=closing.get("impactoRealPrazoDias"),
        closing_cost_impact_cents=closing.get("impactoRealCustoCentavos"),
        identified_on=lookups.shifted(source["identificadoEm"]),
    )


def _assessments_of(lookups: _Lookups, source: Mapping[str, Any]) -> list[RiskAssessment]:
    """The current inherent and residual assessments, dated by the review that recorded them."""
    result: list[RiskAssessment] = []
    for kind in (INHERENT, RESIDUAL):
        current = source.get(kind)
        if not current:
            continue
        entry = _last_review_of_kind(source.get("revisoes") or (), kind)
        author = entry["porId"] if entry else source["identificadoPorId"]
        when = entry["data"] if entry else source["identificadoEm"]
        columns = {
            DIMENSION_COLUMNS[key]: level
            for key, level in (current.get("dimensoes") or {}).items()
            if key in DIMENSION_COLUMNS
        }
        result.append(
            RiskAssessment(
                author_id=lookups.person(author),
                kind=kind,
                probability=current["p"],
                impact=current["i"],
                assessed_on=lookups.shifted(when),
                **columns,
            )
        )
    return result


def _last_review_of_kind(
    reviews: Sequence[Mapping[str, Any]], kind: str
) -> Mapping[str, Any] | None:
    """The newest timeline entry of the kind (the mock lists the newest first)."""
    return next((entry for entry in reviews if entry["tipo"] == kind), None)


def _reviews_of(lookups: _Lookups, reviews: Sequence[Mapping[str, Any]]) -> list[RiskReview]:
    """The timeline, oldest first, so the ids follow the dates."""
    return [
        RiskReview(
            author_id=lookups.person(entry["porId"]),
            reviewed_on=lookups.shifted(entry["data"]),
            kind=entry["tipo"],
            assessed_situation=entry["situacaoApurada"],
            score_from=entry.get("de"),
            score_to=entry["para"],
            probability=entry["p"],
            impact=entry["i"],
            trigger_occurred=bool(entry.get("gatilho")),
            body=entry.get("texto"),
        )
        for entry in reversed(reviews)
    ]


def _approvals_of(lookups: _Lookups, approval: Mapping[str, Any]) -> list[RiskPlanApproval]:
    """The approval request of the plan, when the prototype asked for one."""
    if not approval.get("exigida"):
        return []
    decided = approval.get("situacao") != service.APPROVAL_PENDING
    return [
        RiskPlanApproval(
            by_id=lookups.person(approval.get("porId")),
            situation=approval["situacao"],
            requested_at=lookups.moment(approval.get("solicitadaEm")),
            decided_at=lookups.moment(approval.get("data")) if decided else None,
        )
    ]


register(PART_NAME, load)
