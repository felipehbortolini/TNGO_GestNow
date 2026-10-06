"""Parte do módulo HSE na carga de demonstração (ISSUE-072 e ISSUE-074, D6).

Lê as coleções ``hht`` e ``hseMensal`` do protótipo e grava pela fachada do módulo, uma linha por
mês e empresa (HHT) e uma por mês (consolidado). O protótipo não traz inspeções, observações nem DDS
individuais (só o consolidado mensal), então nenhum desses registros nasce aqui. Os meses são
deslocados pela distância em meses até setembro de 2026 (a âncora do protótipo, ``DEMO_ANCHOR``),
contada a partir do mês da data de referência: ``shift_date`` de dias poderia levar dois meses ao
mesmo mês. O histograma de mão de obra não é gravado: é calculado do HHT e da Curva S.

Lê também a coleção ``analisesRisco`` (ISSUE-074): cada estudo entra pela fachada com o código do
protótipo, as datas deslocadas por ``shift_date`` e as recomendações com a situação do protótipo; o
protótipo não traz data de conclusão nem ação criada nas recomendações, então nenhuma nasce aqui.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.carga import prototype_collection, register
from src.carga.plataforma import ADMIN_EMAIL
from src.carga.registro import DEMO_ANCHOR, shift_date
from src.core.rbac import Bond, GeneralProfile, User
from src.modulos.configuracoes import service as configuracoes
from src.modulos.hse import analysis_service, service
from src.modulos.hse.validation import (
    AnalysisInput,
    ClosingInput,
    HoursInput,
    RecommendationInput,
)

PART_NAME = "hse"


def _month_index(value: date) -> int:
    return value.year * 12 + value.month - 1


def _shifted_month(mock_month: str, reference_date: date) -> date:
    """``2026-05`` do protótipo no mês equivalente em relação à data de referência."""
    year, month = (int(part) for part in mock_month.split("-"))
    back = _month_index(DEMO_ANCHOR) - _month_index(date(year, month, 1))
    index = _month_index(shift_date(DEMO_ANCHOR, reference_date)) - back
    return date(index // 12, index % 12 + 1, 1)


def load(session: Session, reference_date: date) -> None:
    """Grava o HHT e o consolidado mensal dos projetos do protótipo, na transação do chamador."""
    access = configuracoes.find_access_by_email(session, ADMIN_EMAIL)
    if access is None:
        return
    user = User(
        id=access.id,
        person_id=access.person_id,
        name=access.name,
        email=access.email,
        general_profile=GeneralProfile(access.general_profile),
        bond=Bond(access.bond),
        company_id=access.company_id,
    )
    project_ids = {project.code: project.id for project in configuracoes.list_projects(session)}
    mock_codes = {item["id"]: item["codigo"] for item in prototype_collection("projetos")}
    mock_companies = {item["id"]: item["nome"] for item in prototype_collection("empresas")}
    for source in prototype_collection("hht"):
        company_id = service.company_id_by_name(session, mock_companies[source["empresaId"]])
        service.save_hours(
            session,
            user=user,
            data=HoursInput(
                project_id=project_ids[mock_codes[source["projetoId"]]],
                month=_shifted_month(source["mes"], reference_date),
                company_id=company_id,
                headcount=source["efetivoMedio"],
                hours=Decimal(source["hht"]),
            ),
            reference_date=reference_date,
        )
    for source in prototype_collection("hseMensal"):
        service.save_closing(
            session,
            user=user,
            data=ClosingInput(
                project_id=project_ids[mock_codes[source["projetoId"]]],
                month=_shifted_month(source["mes"], reference_date),
                deviations=source["desvios"],
                observations=source["observacoes"],
                planned_dds=source["ddsProgramados"],
                held_dds=source["ddsRealizados"],
                inspected_items=source["itensInspecionados"],
                conforming_items=source["itensConformes"],
            ),
            reference_date=reference_date,
        )
    _load_analyses(session, user=user, reference_date=reference_date, project_ids=project_ids)


def _load_analyses(
    session: Session, *, user: User, reference_date: date, project_ids: dict[str, int]
) -> None:
    """Grava os estudos APR/HAZOP do protótipo com as recomendações e a situação de cada uma."""
    mock_codes = {item["id"]: item["codigo"] for item in prototype_collection("projetos")}
    ids_by_email = {
        person.email.lower(): person.id for person in configuracoes.list_people(session)
    }
    people = {
        person["id"]: ids_by_email[person["email"].lower()]
        for person in prototype_collection("pessoas")
    }
    for source in prototype_collection("analisesRisco"):
        analysis_service.save_analysis(
            session,
            user=user,
            data=AnalysisInput(
                project_id=project_ids[mock_codes[source["projetoId"]]],
                kind=source["tipo"],
                area=source["area"],
                title=source["titulo"],
                studied_on=shift_date(date.fromisoformat(source["data"]), reference_date),
                participant_ids=tuple(people[item] for item in source["participantesIds"]),
                recommendations=tuple(
                    RecommendationInput(
                        description=item["descricao"],
                        responsible_id=people[item["responsavelId"]],
                        due_date=shift_date(date.fromisoformat(item["prazo"]), reference_date),
                        status=item["situacao"],
                    )
                    for item in source["recomendacoes"]
                ),
                code=source["codigo"],
            ),
            reference_date=reference_date,
        )


register(PART_NAME, load)
