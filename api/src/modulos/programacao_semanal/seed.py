"""Part of the Weekly Scheduling in the demonstration load (ISSUE-051).

The data is the demonstration of the app ``Timenow - Programação Semanal`` (its
``demo-obra`` environment), converted to the tables and put in one project of the
portfolio, the "ambiente" of the app being the project here (D10). The file
``demonstracao.json`` next to this one is the versioned copy; the app is read-only
reference. Every date, and every week reference, is shifted by the same number of days
(``shift_date``), so the demonstration always has a current week.

Companies, locations, units and people belong to Configurações: they are asked of its
facade (``ensure_*``). The activities, the window of each company and the parameters
go through the facade of this module, with the trail.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from src.carga import register, shift_date
from src.carga.plataforma import ADMIN_EMAIL
from src.modulos.configuracoes import service as registers_facade
from src.modulos.programacao_semanal import service, weeks
from src.modulos.programacao_semanal import window as window_rules
from src.modulos.programacao_semanal.service import NewActivity, ScheduleParameters

PART_NAME = "programacao_semanal"
DATA_PATH = Path(__file__).resolve().parent / "demonstracao.json"

# The project of the portfolio that receives the demonstration: the first of the platform load.
PROJECT_CODE = "TN-2026-014"

GENERAL_PROFILE = "Membro"
ROLE_OF_PROFILE = {
    "planejador": "Planejador",
    "fiscal": "Fiscal",
    "encarregado": "Encarregado",
    "fornecedor": "Fornecedor",
}
BOND_OF_SOURCE = {"timenow": "Timenow", "fornecedor": "Fornecedor"}
COMPANY_KIND = "Contratada"
WEEKDAY_OF_NAME = {"seg": 1, "ter": 2, "qua": 3, "qui": 4, "sex": 5, "sab": 6, "dom": 7}
FALLBACK_SUPPLIER_PROFILE = "fornecedor"


@dataclass(frozen=True)
class Registers:
    """The ids the activities point to, by the names the app used."""

    project_id: int
    author_id: int
    companies: dict[str, int]
    locations: dict[str, int]
    units: dict[str, int]
    people: dict[str, int]
    person_by_email: dict[str, int]
    supplier_of_company: dict[str, int]


def load(session: Session, reference_date: date) -> None:
    """Write the whole part inside the caller's transaction."""
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    registers = _load_registers(session, data)
    service.store_settings(
        session,
        author_id=registers.author_id,
        project_id=registers.project_id,
        parameters=_parameters(data["parametros"], reference_date),
    )
    for source in data["janelas"]:
        company_id = registers.companies[source["empresa"]]
        service.store_window(
            session,
            author_id=registers.author_id,
            project_id=registers.project_id,
            rules=_window(source, company_id, reference_date),
        )
    ordered = sorted(data["atividades"], key=lambda a: (weeks.sort_key(a["semana"]), a["item"]))
    for source in ordered:
        service.store_activity(
            session,
            author_id=registers.author_id,
            new=_new_activity(source, registers, reference_date),
        )


def _load_registers(session: Session, data: dict[str, Any]) -> Registers:
    """Companies, locations, units and the people of the demonstration, by name."""
    author = registers_facade.find_access_by_email(session, ADMIN_EMAIL)
    project_id = registers_facade.find_project_id(session, PROJECT_CODE)
    if author is None or project_id is None:
        message = "A parte da plataforma precisa rodar antes da Programação Semanal."
        raise RuntimeError(message)
    author_id = author.id
    cadastros = data["cadastros"]
    companies = {
        name: registers_facade.ensure_company(
            session, author_id=author_id, name=name, kind=COMPANY_KIND
        )
        for name in cadastros["empresas"]
    }
    locations = {
        name: registers_facade.ensure_location(
            session, author_id=author_id, project_id=project_id, name=name
        )
        for name in cadastros["locais"]
    }
    units = {
        code: registers_facade.ensure_measure_unit(
            session, author_id=author_id, code=code, name=code
        )
        for code in cadastros["unidades"]
    }
    people, by_email, suppliers = _load_people(
        session, data["colaboradores"], author_id, project_id, companies
    )
    return Registers(
        project_id=project_id,
        author_id=author_id,
        companies=companies,
        locations=locations,
        units=units,
        people=people,
        person_by_email=by_email,
        supplier_of_company=suppliers,
    )


def _load_people(
    session: Session,
    sources: list[dict[str, Any]],
    author_id: int,
    project_id: int,
    companies: dict[str, int],
) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    """The planner, inspectors, foremen and suppliers, each with its role in the project.

    The Admin and the client viewer of the app are not brought: the platform load has its own.
    """
    people: dict[str, int] = {}
    by_email: dict[str, int] = {}
    suppliers: dict[str, int] = {}
    for source in sources:
        role = ROLE_OF_PROFILE.get(source["perfil"])
        if role is None:
            continue
        company_id = companies.get(source["empresa"]) if source["empresa"] else None
        person_id, collaborator_id = registers_facade.ensure_collaborator(
            session,
            author_id=author_id,
            name=source["nome"],
            email=source["email"],
            role=source["cargo"],
            company_id=company_id,
            profile=GENERAL_PROFILE,
            bond=BOND_OF_SOURCE[source["vinculo"]],
        )
        registers_facade.grant_schedule_role(
            session, collaborator_id=collaborator_id, project_id=project_id, role=role
        )
        people[source["nome"]] = person_id
        by_email[source["email"].lower()] = person_id
        if source["perfil"] == FALLBACK_SUPPLIER_PROFILE and source["empresa"]:
            suppliers[source["empresa"]] = person_id
    return people, by_email, suppliers


def _parameters(source: dict[str, Any], reference_date: date) -> ScheduleParameters:
    """The parameters of the app (targets and deviation rule) as the project's row."""
    reference = source.get("semana_referencia") or ""
    return ScheduleParameters(
        adherence_target=float(source["meta_aderencia"]),
        ppc_target=float(source["meta_ppc"]),
        reference_week=_shift_week(reference, reference_date) if reference else "",
        requires_deviation_note=bool(source["exige_justificativa_desvio"]),
        deviation_limit=float(source["limite_desvio_justificativa"]),
    )


def _window(source: dict[str, Any], company_id: int, reference_date: date) -> window_rules.Window:
    """The window of a company: its weekdays and hours and the weeks released, shifted."""
    days = tuple(
        window_rules.WindowDay(
            weekday=WEEKDAY_OF_NAME[rule["dia"]],
            opens=time.fromisoformat(rule["abre"]),
            closes=time.fromisoformat(rule["fecha"]),
        )
        for rule in source["dias"]
    )
    released = frozenset(_shift_week(week, reference_date) for week in source["semanas_liberadas"])
    return window_rules.Window(company_id=company_id, days=days, weeks=released)


def _new_activity(source: dict[str, Any], known: Registers, reference_date: date) -> NewActivity:
    """One activity of the app as the facade writes it, with its dates and week shifted."""
    created_at = _shift_moment(source["criado_em"], reference_date)
    updated_at = _shift_moment(source["atualizado_em"], reference_date)
    approved = source["aprovacao_realizado"] == "aprovado"
    published = source["situacao"] == "publicada"
    inspector = known.people.get(source["responsavel"]) if source["responsavel"] else None
    author = known.person_by_email.get(
        str(source["criado_por"]).lower(), known.supplier_of_company[source["empresa"]]
    )
    return NewActivity(
        project_id=known.project_id,
        company_id=known.companies[source["empresa"]],
        week=_shift_week(source["semana"], reference_date),
        unique_id=source["id_exclusiva"],
        item=source["item"],
        description=source["atividade"],
        planned_headline=float(source["prod_prevista"]),
        author_person_id=author,
        at=created_at,
        location_id=known.locations[source["local"]],
        unit_id=known.units[source["unidade"]],
        inspector_id=inspector,
        foreman_id=known.people[source["encarregado"]],
        planned_days=tuple(source["dias_previsto"]),
        day_shift=tuple(source["dias_realizado"]),
        night_shift=tuple(source["dias_noite"]),
        situation=source["situacao"],
        approval=source["aprovacao_realizado"],
        supplier_notes=source["observacoes_fornecedor"],
        approved_at=updated_at if approved else None,
        published_at=updated_at if published else None,
    )


def _shift_week(week: str, reference_date: date) -> str:
    """The week that holds the Monday of ``week`` moved by the shift of the load."""
    monday = weeks.start(week)
    if monday is None:
        return week
    return weeks.of_date(shift_date(monday, reference_date))


def _shift_moment(text: str, reference_date: date) -> datetime:
    """An instant of the app moved by the shift, keeping the time of day and the zone."""
    moment = datetime.fromisoformat(text)
    return datetime.combine(shift_date(moment.date(), reference_date), moment.timetz())


register(PART_NAME, load)
