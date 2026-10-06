"""Parte do módulo HSE na carga de demonstração (ISSUE-072, D6).

Lê as coleções ``hht`` e ``hseMensal`` do protótipo e grava pela fachada do módulo, uma linha por
mês e empresa (HHT) e uma por mês (consolidado). O protótipo não traz inspeções, observações nem DDS
individuais (só o consolidado mensal), então nenhum desses registros nasce aqui. Os meses são
deslocados pela distância em meses até setembro de 2026 (a âncora do protótipo, ``DEMO_ANCHOR``),
contada a partir do mês da data de referência: ``shift_date`` de dias poderia levar dois meses ao
mesmo mês. O histograma de mão de obra não é gravado: é calculado do HHT e da Curva S.
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
from src.modulos.hse import service
from src.modulos.hse.validation import ClosingInput, HoursInput

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


register(PART_NAME, load)
