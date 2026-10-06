"""Parte do HSE na carga de demonstração (ISSUE-072, D6/Q15).

O HHT de cada mês e empresa (``hht``) e o fechamento mensal da segurança proativa
(``hseMensal``) entram pela fachada (``service.save_hours`` e ``service.save_closing``), com os
meses deslocados por ``shift_date``; na âncora (25/09/2026) nada muda. O protótipo não tinha
inspeção, observação nem DDS individuais: a tela do HSE mostrava o consolidado do mês, e é ele
que a carga traz. O histograma de mão de obra também não é gravado — é calculado do HHT e da
Curva S física pelo servidor; o oráculo confere o previsto contra ``histogramaMaoDeObra``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.carga import prototype_collection, register, shift_date
from src.carga.plataforma import ADMIN_EMAIL
from src.core.rbac import Bond, GeneralProfile, User
from src.modulos.configuracoes import service as configuracoes
from src.modulos.hse import calculations, service
from src.modulos.hse.validation import ClosingInput, HoursInput

PART_NAME = "hse"


def load(session: Session, reference_date: date) -> None:
    """Escreve o HHT e o fechamento mensal do protótipo, com os meses deslocados para hoje."""
    user = _admin(session)
    projects = _projects_by_mock_id(session)
    companies = _companies_by_mock_id(session)
    for source in prototype_collection("hht"):
        service.save_hours(
            session,
            user=user,
            data=HoursInput(
                project_id=projects[source["projetoId"]],
                month=_month(source["mes"], reference_date),
                company_id=companies[source["empresaId"]],
                headcount=int(source["efetivoMedio"]),
                hours=Decimal(str(source["hht"])),
            ),
            reference_date=reference_date,
        )
    for source in prototype_collection("hseMensal"):
        service.save_closing(
            session,
            user=user,
            data=ClosingInput(
                project_id=projects[source["projetoId"]],
                month=_month(source["mes"], reference_date),
                deviations=int(source["desvios"]),
                observations=int(source["observacoes"]),
                planned_dds=int(source["ddsProgramados"]),
                held_dds=int(source["ddsRealizados"]),
                inspected_items=int(source["itensInspecionados"]),
                conforming_items=int(source["itensConformes"]),
            ),
            reference_date=reference_date,
        )


def _admin(session: Session) -> User:
    access = configuracoes.find_access_by_email(session, ADMIN_EMAIL)
    if access is None:
        message = f"O Admin da demonstração ({ADMIN_EMAIL}) não está no cadastro."
        raise LookupError(message)
    return User(
        id=access.id,
        person_id=access.person_id,
        name=access.name,
        email=access.email,
        general_profile=GeneralProfile(access.general_profile),
        bond=Bond(access.bond),
        company_id=access.company_id,
    )


def _projects_by_mock_id(session: Session) -> dict[int, int]:
    """O id de cada projeto do protótipo no banco, pelo código."""
    ids_by_code = {project.code: project.id for project in configuracoes.list_projects(session)}
    return {
        project["id"]: ids_by_code[project["codigo"]]
        for project in prototype_collection("projetos")
    }


def _companies_by_mock_id(session: Session) -> dict[int, int]:
    """O id de cada empresa do protótipo no banco, pelo nome."""
    ids_by_name = {option.name: option.id for option in configuracoes.list_company_options(session)}
    return {
        company["id"]: ids_by_name[company["nome"]] for company in prototype_collection("empresas")
    }


def _month(label: str, reference_date: date) -> date:
    """O mês ``AAAA-MM`` do protótipo, deslocado para a data da execução."""
    month = calculations.parse_month(label)
    if month is None:
        message = f"Mês inválido na carga do HSE: {label!r}."
        raise ValueError(message)
    return calculations.month_of(shift_date(month, reference_date))


register(PART_NAME, load)
