"""Partes do HSE na carga de demonstração (ISSUE-072 e ISSUE-073, D6/Q15).

``hse``: o HHT de cada mês e empresa (``hht``) e o fechamento mensal da segurança proativa
(``hseMensal``) entram pela fachada (``service.save_hours`` e ``service.save_closing``), com os
meses deslocados por ``shift_date``; na âncora (25/09/2026) nada muda. O protótipo não tinha
inspeção, observação nem DDS individuais: a tela do HSE mostrava o consolidado do mês, e é ele
que a carga traz. O histograma de mão de obra também não é gravado — é calculado do HHT e da
Curva S física pelo servidor; o oráculo confere o previsto contra ``histogramaMaoDeObra``.

``hse-ocorrencias`` (registrada depois de ``hse``): as ocorrências do protótipo (``ocorrencias``,
a lista de ``mock-hse`` mais a de ``mock-portfolio``), com o cenário do mock reproduzido — a
situação calculada pela idade contra a data de referência vira o estado do fluxo, e o que
avançou de Registrada ganha a investigação (método do mock, ou ``5 porquês``) e o encerramento
com a eficácia. O dado restrito entra com o que o mock tem (sem nome, por LGPD: o mock só guarda
função e empresa); o prazo de cada ocorrência é o vigente na data da carga (D5b). A numeração de
cada projeto continua do maior código carregado, então a primeira ocorrência que uma pessoa
registra não colide com a demonstração.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.carga import prototype_collection, register, shift_date
from src.carga.plataforma import ADMIN_EMAIL
from src.core import calendario, numbering, recording
from src.core.rbac import Bond, GeneralProfile, User
from src.modulos.configuracoes import service as configuracoes
from src.modulos.hse import calculations, models, service
from src.modulos.hse.validation import ClosingInput, HoursInput

PART_NAME = "hse"
PART_OCORRENCIAS = "hse-ocorrencias"
INVESTIGATION_METHOD_DEFAULT = "5 porquês"
CLOSING_EFICACIA = "Ações corretivas concluídas e verificadas no acompanhamento de campo."
CLOSING_OFFSET_DAYS = 20
INVESTIGATION_OFFSET_DAYS = 1
HISTORY_HOUR = 9


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


@dataclass(frozen=True)
class _Lookups:
    """O que a conversão das ocorrências precisa: a pessoa, a data e os mapas do protótipo."""

    user: User
    reference_date: date
    deadlines: calculations.DeadlinePolicy
    projects: Mapping[int, int]
    companies: Mapping[int, int]


def load_ocorrencias(session: Session, reference_date: date) -> None:
    """Escreve as ocorrências do protótipo, com o restrito, a investigação e o encerramento."""
    lookups = _Lookups(
        user=_admin(session),
        reference_date=reference_date,
        deadlines=service.deadlines_in_force(session, reference_date=reference_date),
        projects=_projects_by_mock_id(session),
        companies=_companies_by_mock_id(session),
    )
    for source in prototype_collection("ocorrencias"):
        _occurrence(session, source, lookups)
    _start_occurrence_numbering(session)


def _occurrence(session: Session, source: Mapping[str, Any], lookups: _Lookups) -> None:
    environmental = bool(source["ambiental"])
    situation = source["situacao"]
    happened_at = _local_datetime(source["dataHora"], lookups.reference_date)
    event_date = happened_at.date()
    potential = source.get("potencial") or {}
    closed_on = (
        event_date + timedelta(days=CLOSING_OFFSET_DAYS)
        if situation == models.SITUATION_CLOSED
        else None
    )
    record = models.Occurrence(
        project_id=lookups.projects[source["projetoId"]],
        company_id=lookups.companies[source["empresaId"]],
        code=source["codigo"],
        happened_at=happened_at,
        kind=source["tipo"],
        subtype=source.get("subtipo"),
        area=source["area"],
        place=None,
        description=source.get("descricao") or "",
        role=source.get("funcao"),
        people_involved=int(source.get("pessoasEnvolvidas") or 0),
        potential_p=None if environmental else potential.get("p"),
        potential_i=None if environmental else potential.get("i"),
        hipo=bool(source.get("hipo")),
        environmental=environmental,
        environmental_severity=source.get("severidadeAmbiental"),
        immediate_cause=source.get("causaImediata"),
        communication_hours=int(source.get("comunicacaoHoras") or 0),
        communication_deadline_hours=lookups.deadlines.communication_hours,
        investigation_deadline_hours=lookups.deadlines.investigation_hours,
        report_deadline_days=lookups.deadlines.report_days,
        situation=situation,
        closed_on=closed_on,
        effectiveness=CLOSING_EFICACIA if closed_on is not None else None,
    )
    recording.create(session, user_id=lookups.user.id, record=record)
    recording.create(
        session,
        user_id=lookups.user.id,
        record=models.OccurrenceRestricted(
            occurrence_id=record.id,
            name=None,
            real_gravity=source.get("gravidadeReal"),
            days_lost=int(source.get("diasPerdidos") or 0),
            days_charged=int(source.get("diasDebitados") or 0),
            cat=bool(source.get("cat")),
            medical_notes=None,
        ),
    )
    service._append_history(
        session,
        user=lookups.user,
        occurrence=record,
        text="Ocorrência registrada.",
        moment=happened_at,
    )
    if situation != models.SITUATION_REGISTERED:
        _investigation(session, record, source, lookups)
    if closed_on is not None:
        service._append_history(
            session,
            user=lookups.user,
            occurrence=record,
            text=f"Ocorrência encerrada. Eficácia: {CLOSING_EFICACIA}",
            moment=_moment_of(closed_on),
        )


def _investigation(
    session: Session, record: models.Occurrence, source: Mapping[str, Any], lookups: _Lookups
) -> None:
    """A investigação que o estado do cenário exige: o mock não guarda o texto, só o método."""
    method = source.get("metodo") or INVESTIGATION_METHOD_DEFAULT
    happened_on = record.happened_at.date() + timedelta(days=INVESTIGATION_OFFSET_DAYS)
    cause = source.get("causaImediata") or "Condição insegura do local"
    root_cause = f"Causa raiz apurada na investigação preliminar: {cause.lower()}."
    recording.create(
        session,
        user_id=lookups.user.id,
        record=models.OccurrenceInvestigation(
            occurrence_id=record.id,
            responsible_id=lookups.user.person_id,
            method=method,
            root_cause=root_cause,
            investigated_on=happened_on,
        ),
    )
    service._append_history(
        session,
        user=lookups.user,
        occurrence=record,
        text=f"Investigação registrada ({method}). Causa raiz: {root_cause}",
        moment=_moment_of(happened_on),
    )


def _local_datetime(label: str, reference_date: date) -> datetime:
    """Um instante local do protótipo (``2026-09-12T09:25``) deslocado, no fuso do produto."""
    moment = datetime.fromisoformat(label)
    shifted = shift_date(moment.date(), reference_date)
    return datetime.combine(shifted, moment.time(), tzinfo=calendario.PRODUCT_TIMEZONE)


def _moment_of(day: date) -> datetime:
    """O instante de uma data da carga, na hora fixa do histórico (9:00 do produto)."""
    return datetime.combine(
        day, datetime.min.time().replace(hour=HISTORY_HOUR), tzinfo=calendario.PRODUCT_TIMEZONE
    )


def _start_occurrence_numbering(session: Session) -> None:
    """Continua a série de ocorrências de cada projeto depois do maior código carregado."""
    rows = session.execute(select(models.Occurrence.project_id, models.Occurrence.code)).all()
    last_by_project: dict[int, int] = {}
    for project_id, code in rows:
        suffix = code.rpartition("-")[2]
        if suffix.isdigit():
            last_by_project[project_id] = max(last_by_project.get(project_id, 0), int(suffix))
    for project_id, last in sorted(last_by_project.items()):
        project = configuracoes.find_project(session, project_id)
        if project is not None:
            numbering.start_after(session, project=project, kind="ocorrencia", last_number=last)


register(PART_NAME, load)
register(PART_OCORRENCIAS, load_ocorrencias)
