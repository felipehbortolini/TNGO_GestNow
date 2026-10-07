"""Parte do módulo Planejamento na carga de demonstração (D6, ISSUE-008).

Cada issue do módulo acrescenta aqui a sua parte, como uma função chamada por ``load``:
o 6WLA (ISSUE-045) grava as atividades, as semanas e as restrições do protótipo
(``lookahead``) e o Relato do período (ISSUE-044) grava os relatos (``seed_relato``). Os cadastros que o protótipo numera (projeto, empresa, pessoa) são
achados pela chave de negócio (código, nome), porque os ids do banco não são os do mock.
As datas das restrições andam com ``shift_date``; o início do horizonte não é gravado,
sai do calendário (``calculations.lookahead_window_start``).

A EAP (ISSUE-036) é a parte ``planejamento-eap``: a árvore de níveis 1 a 3 do mock (pai pelo
código), as etapas dos pacotes de Etapas, as revisões e o desdobramento. Ela roda
depois de Financeiro e Governança, porque o item aponta o item da EAC pelo ``eacCodigo`` e a
revisão aponta a SM pelo ``smRef``, e as duas fachadas são lidas, nunca as tabelas alheias (D9).
As revisões congelam os pesos correntes de todos os pacotes do projeto; o mock conta 35 na Rev 0
e 37 na Rev 2 do projeto 1 enquanto a EAP corrente tem 38 pacotes, porque o mock não guarda o
histórico de pesos — o vigente vem do próprio item e o número de pacotes da revisão sai dos
pesos congelados (D5b). As datas andam com ``shift_date``, como nas demais partes.

A Curva S física (ISSUE-039) é a parte ``planejamento-curva``: a linha de base do mock é
congelada em cada revisão da EAP semeada e cada pacote com real corrente recebe uma medição por
mês, proporcional à série do protótipo e fechando o real no corte. O mock fecha 65,7% no corte
do projeto 1, mas a distribuição linear das datas da EAP daria 69,2%: a carga congela o número
do protótipo (Q31) e o mecanismo de geração vale para as revisões novas em runtime; a diferença
está registrada em ``docs/DIVERGENCIAS-DO-PROTOTIPO.md``. A parte roda depois da EAP e substitui
as medições que a carga antiga tinha deixado, para a série fechar.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.carga import prototype_collection, register, shift_date
from src.core import calendario, recording
from src.modulos.configuracoes import service as configuracoes
from src.modulos.planejamento import calculations, seed_relato, service
from src.modulos.planejamento.models import (
    CurvaFisicaMonth,
    CurvaFisicaRevision,
    EapBreakdown,
    EapItem,
    EapItemStep,
    EapMeasurement,
    EapRevision,
    EapRevisionItem,
)

PART_NAME = "planejamento"
EAP_PART_NAME = "planejamento-eap"
CURVA_PART_NAME = "planejamento-curva"
ADMIN_PROFILE = "Admin"
TWO_PLACES = Decimal("0.01")


def load(session: Session, reference_date: date) -> None:
    """Write the part of the Planning module, inside the caller's transaction."""
    _load_lookahead(session, reference_date)
    seed_relato.load_reports(session, reference_date)


def _load_lookahead(session: Session, reference_date: date) -> None:
    """The 6WLA of the prototype: ``lookahead`` with its weeks and restrictions."""
    author = _author(session)
    ids = _RegisterIds.read(session)
    for source in prototype_collection("lookahead"):
        service.load_activity(
            session,
            author_id=author.id,
            data=service.LoadedActivity(
                project_id=ids.project(source["projetoId"]),
                company_id=ids.company(source["empresaId"]),
                owner_id=ids.person(source["responsavelId"]),
                code=source["codigo"],
                activity=source["atividade"],
                area=source["area"],
                discipline=source["disciplina"],
                planned=tuple(bool(mark) for mark in source["semanas"]),
                constraints=tuple(
                    _constraint(item, ids, reference_date) for item in source["restricoes"]
                ),
            ),
        )


def _author(session: Session) -> configuracoes.CollaboratorAccess:
    """O Admin da demonstração, autor dos registros que a carga grava."""
    return next(
        item
        for item in configuracoes.list_active_access(session)
        if item.general_profile == ADMIN_PROFILE
    )


def _constraint(
    source: dict[str, Any], ids: _RegisterIds, reference_date: date
) -> service.LoadedConstraint:
    removal = source["remocao"]
    return service.LoadedConstraint(
        kind=source["tipo"],
        owner_id=ids.person(source["responsavelId"]),
        description=source["descricao"],
        due_date=shift_date(date.fromisoformat(source["necessaria"]), reference_date),
        removal_date=shift_date(date.fromisoformat(removal), reference_date) if removal else None,
    )


class _RegisterIds:
    """The ids of this database for the mock ids: projects by code, companies and people by name."""

    def __init__(
        self, projects: dict[int, int], companies: dict[int, int], people: dict[int, int]
    ) -> None:
        self._projects = projects
        self._companies = companies
        self._people = people

    @classmethod
    def read(cls, session: Session) -> _RegisterIds:
        project_by_code = {item.code: item.id for item in configuracoes.list_projects(session)}
        company_by_name = {
            item.name: item.id for item in configuracoes.list_company_options(session)
        }
        person_by_name = {item.name: item.id for item in configuracoes.list_person_options(session)}
        return cls(
            projects={
                source["id"]: project_by_code[source["codigo"]]
                for source in prototype_collection("projetos")
            },
            companies={
                source["id"]: company_by_name[source["nome"]]
                for source in prototype_collection("empresas")
            },
            people={
                source["id"]: person_by_name[source["nome"]]
                for source in prototype_collection("pessoas")
            },
        )

    def project(self, mock_id: int) -> int:
        return self._projects[mock_id]

    def company(self, mock_id: int | None) -> int | None:
        return self._companies[mock_id] if mock_id is not None else None

    def person(self, mock_id: int | None) -> int | None:
        return self._people[mock_id] if mock_id is not None else None


# ── EAP: árvore, revisões e desdobramento (ISSUE-036) ────────────────────


@dataclass(frozen=True)
class _EapLoad:
    """O que toda parte da EAP carrega: o autor, os ids resolvidos e a data da carga."""

    author_id: int
    ids: _RegisterIds
    reference_date: date


def load_eap(session: Session, reference_date: date) -> None:
    """Grava a EAP do protótipo, dentro da transação de quem chama.

    A árvore vem do mock com o pai pelo código; as etapas, as medições, as revisões e o
    desdobramento vêm nas coleções próprias. O item da EAC e a SM das revisões são achados
    pelas fachadas do Financeiro e da Governança (D9), que já rodaram.
    """
    author = _author(session)
    load = _EapLoad(
        author_id=author.id,
        ids=_RegisterIds.read(session),
        reference_date=reference_date,
    )
    items = _load_eap_items(session, load)
    _load_eap_revisions(session, load, items=items)
    _load_eap_breakdowns(session, load, items=items)


def _load_eap_items(session: Session, load: _EapLoad) -> dict[tuple[int, str], EapItem]:
    """Grava a árvore inteira e devolve cada item pelo projeto e código."""
    ids = load.ids
    units = {item.code: item.id for item in configuracoes.list_measure_units(session)}
    eac_ids = _eac_ids(session, ids=ids)
    created: dict[tuple[int, str], EapItem] = {}
    sources = sorted(
        prototype_collection("eap"),
        key=lambda source: (source["projetoId"], _code_key(source["codigo"])),
    )
    for source in sources:
        project_id = ids.project(source["projetoId"])
        parent = created.get((project_id, _parent_code(source["codigo"])))
        item = recording.create(
            session,
            user_id=load.author_id,
            record=EapItem(
                project_id=project_id,
                parent_id=None if parent is None else parent.id,
                eac_item_id=eac_ids.get((source["projetoId"], source.get("eacCodigo") or "")),
                unit_id=units.get(source.get("unidade") or ""),
                company_id=ids.company(source.get("empresaId")),
                owner_id=ids.person(source.get("responsavelId")),
                code=source["codigo"],
                description=source["descricao"],
                level=source["nivel"],
                kind=source.get("tipo"),
                criterion=source.get("criterio"),
                model=source.get("modelo"),
                quantity=_decimal_or_none(source.get("quantidade")),
                executed=_decimal_or_none(source.get("executado")),
                state=source.get("estado"),
                estimated_pct=_decimal_or_none(source.get("estimadoPct")),
                weight=_decimal_or_none(source.get("peso")),
                predicted=_decimal_or_none(source.get("previsto")),
                start=_shifted_date(source.get("inicio"), load.reference_date),
                finish=_shifted_date(source.get("termino"), load.reference_date),
                deliverable=source.get("entregavel"),
                acceptance=source.get("aceitacao"),
            ),
        )
        created[(project_id, source["codigo"])] = item
        _load_eap_steps(session, item=item, source=source)
    session.flush()
    return created


def _load_eap_steps(session: Session, *, item: EapItem, source: dict[str, Any]) -> None:
    """As etapas do critério Etapas, na ordem do mock, com o percentual corrente."""
    for order, step in enumerate(source.get("etapas") or (), start=1):
        session.add(
            EapItemStep(
                item_id=item.id,
                order=order,
                name=step["nome"],
                weight=Decimal(str(step["peso"])),
                pct=Decimal(str(step["pct"])),
            )
        )


def _load_eap_revisions(
    session: Session, load: _EapLoad, *, items: dict[tuple[int, str], EapItem]
) -> None:
    """As revisões do mock, cada uma congelando os pesos correntes dos pacotes do projeto."""
    from src.modulos.governanca import service as governanca

    ids = load.ids
    changes = governanca.change_ids_by_code(
        session,
        codes=[
            source["smRef"] for source in prototype_collection("eapRevisoes") if source.get("smRef")
        ],
    )
    packages = _packages_by_project(items)
    for source in prototype_collection("eapRevisoes"):
        project_id = ids.project(source["projetoId"])
        revision = recording.create(
            session,
            user_id=load.author_id,
            record=EapRevision(
                project_id=project_id,
                change_id=changes.get(source.get("smRef") or ""),
                approved_by_id=ids.person(source["aprovadoPorId"]) or load.author_id,
                revision=source["revisao"],
                revision_date=shift_date(date.fromisoformat(source["data"]), load.reference_date),
                alteration=source["alteracao"],
                justification=source["justificativa"],
            ),
        )
        session.add_all(
            EapRevisionItem(
                revision_id=revision.id,
                item_id=item.id,
                weight=item.weight or Decimal(0),
            )
            for item in packages.get(project_id, ())
        )
        session.flush()


def _load_eap_breakdowns(
    session: Session, load: _EapLoad, *, items: dict[tuple[int, str], EapItem]
) -> None:
    """O desdobramento do mock: do pacote de planejamento para o pacote de trabalho."""
    ids = load.ids
    for source in prototype_collection("eapDesdobramentos"):
        project_id = ids.project(source["projetoId"])
        recording.create(
            session,
            user_id=load.author_id,
            record=EapBreakdown(
                project_id=project_id,
                source_item_id=items[(project_id, source["origem"])].id,
                target_item_id=items[(project_id, source["destino"])].id,
                by_id=ids.person(source["porId"]) or load.author_id,
                revision=source["revisao"],
                applied_on=shift_date(date.fromisoformat(source["data"]), load.reference_date),
                weight=Decimal(str(source["peso"])),
                justification=source["justificativa"],
            ),
        )


def _packages_by_project(
    items: dict[tuple[int, str], EapItem],
) -> dict[int, tuple[EapItem, ...]]:
    """Os pacotes (nível 3) de cada projeto, na ordem em que a árvore os gravou."""
    grouped: dict[int, list[EapItem]] = {}
    for (project_id, _code), item in items.items():
        if item.level == service.LEVEL_PACKAGE:
            grouped.setdefault(project_id, []).append(item)
    return {project_id: tuple(group) for project_id, group in grouped.items()}


def _eac_ids(session: Session, *, ids: _RegisterIds) -> dict[tuple[int, str], int]:
    """O id de cada item da EAC que o mock aponta, pelo projeto e código (fachada do Financeiro)."""
    from src.modulos.financeiro import service as financeiro

    eac: dict[tuple[int, str], int] = {}
    sources = prototype_collection("eap")
    for mock_project_id in sorted({source["projetoId"] for source in sources}):
        codes = [
            source["eacCodigo"]
            for source in sources
            if source["projetoId"] == mock_project_id and source.get("eacCodigo")
        ]
        found = financeiro.eac_item_ids_by_code(
            session, project_id=ids.project(mock_project_id), codes=codes
        )
        eac.update({(mock_project_id, code): item_id for code, item_id in found.items()})
    return eac


# ── Curva S física: linha de base congelada e medições (ISSUE-039) ───────


@dataclass(frozen=True)
class _CurvaLoad:
    """O que a parte da Curva S carrega: os ids resolvidos, os autores e a data da carga."""

    ids: _RegisterIds
    admin_id: int
    author_id: int
    reference_date: date


def load_curva(session: Session, reference_date: date) -> None:
    """Grava a Curva S física do protótipo, dentro da transação de quem chama.

    A linha de base do mock (Q31) é congelada em cada revisão da EAP semeada do projeto, porque
    o número do protótipo não é a distribuição linear das datas da EAP (69,2% contra 65,7% no
    corte do projeto 1); o mecanismo de geração do ``freeze_curve`` vale para as revisões novas
    em runtime. O real sai das medições: cada pacote com real corrente > 0 recebe uma medição
    por mês, proporcional à série do mock e fechando o real corrente no corte, para a soma
    ponderada reproduzir a série do protótipo.
    """
    author = _author(session)
    load = _CurvaLoad(
        ids=_RegisterIds.read(session),
        admin_id=author.id,
        author_id=author.person_id,
        reference_date=reference_date,
    )
    _discard_previous_measurements(session, load)
    managers = _managers_by_project(load.ids)
    for source in prototype_collection("curvaFisica"):
        _load_project_curve(
            session,
            load,
            project_id=load.ids.project(source["projetoId"]),
            source=source,
            author_id=managers.get(source["projetoId"]) or load.author_id,
        )
    session.flush()


def _load_project_curve(
    session: Session,
    load: _CurvaLoad,
    *,
    project_id: int,
    source: dict[str, Any],
    author_id: int,
) -> None:
    """A curva de um projeto: a base do mock em cada revisão e as medições da série real."""
    months = _curve_months(source["meses"], load.reference_date)
    baseline = tuple(Decimal(str(value)) for value in source["baseline"])
    for revision_id in _eap_revision_ids(session, project_id=project_id):
        _freeze_mock_curve(
            session,
            project_id=project_id,
            revision_id=revision_id,
            months=months,
            baseline=baseline,
        )
    _seed_curve_measurements(
        session, load, project_id=project_id, source=source, author_id=author_id
    )


def _freeze_mock_curve(
    session: Session,
    *,
    project_id: int,
    revision_id: int,
    months: tuple[date, ...],
    baseline: tuple[Decimal, ...],
) -> None:
    """Congela a linha de base do mock numa revisão da EAP, mês a mês, sem recálculo."""
    record = CurvaFisicaRevision(
        project_id=project_id,
        eap_revision_id=revision_id,
        generated_at=calendario.now(),
    )
    session.add(record)
    session.flush()
    session.add_all(
        CurvaFisicaMonth(revision_id=record.id, month=month, baseline_pct=pct)
        for month, pct in zip(months, baseline, strict=True)
    )
    session.flush()


def _seed_curve_measurements(
    session: Session,
    load: _CurvaLoad,
    *,
    project_id: int,
    source: dict[str, Any],
    author_id: int,
) -> None:
    """As medições datadas do projeto, proporcionais à série real do mock até o corte."""
    reals = tuple(Decimal(str(value)) for value in source["real"] if value is not None)
    if not reals:
        return
    months = _curve_months(source["meses"], load.reference_date)[: len(reals)]
    cut = reals[-1]
    for item, current in _package_progress(session, project_id=project_id):
        if current <= 0:
            continue
        previous = Decimal(0)
        for index, month in enumerate(months):
            target = (
                current if index == len(months) - 1 else _proportional(current, reals[index], cut)
            )
            recording.create(
                session,
                user_id=load.admin_id,
                record=EapMeasurement(
                    item_id=item.id,
                    author_id=author_id,
                    measured_on=month,
                    from_pct=previous,
                    to_pct=target,
                ),
            )
            previous = target


def _discard_previous_measurements(session: Session, load: _CurvaLoad) -> None:
    """Apaga as medições que a carga antiga semeava do mock, agora substituídas pela série.

    A 036/037 gravava o punhado de ``medicoes`` de cada pacote; a série proporcional é a nova
    fonte do real da curva. A remoção casa item, data e percentuais, para não tocar em medição
    que a pessoa tenha registrado depois.
    """
    for source in prototype_collection("eap"):
        measurements = source.get("medicoes") or ()
        if not measurements:
            continue
        item_id = session.scalar(
            select(EapItem.id).where(
                EapItem.project_id == load.ids.project(source["projetoId"]),
                EapItem.code == source["codigo"],
            )
        )
        if item_id is None:
            continue
        for measurement in measurements:
            session.execute(
                delete(EapMeasurement).where(
                    EapMeasurement.item_id == item_id,
                    EapMeasurement.measured_on
                    == shift_date(date.fromisoformat(measurement["data"]), load.reference_date),
                    EapMeasurement.from_pct == Decimal(str(measurement["de"])),
                    EapMeasurement.to_pct == Decimal(str(measurement["para"])),
                )
            )


def _package_progress(session: Session, *, project_id: int) -> tuple[tuple[EapItem, Decimal], ...]:
    """O real corrente de cada pacote (nível 3) do projeto, na ordem da árvore (D5b)."""
    items = tuple(
        session.scalars(
            select(EapItem)
            .where(EapItem.project_id == project_id, EapItem.level == service.LEVEL_PACKAGE)
            .order_by(EapItem.id)
        )
    )
    if not items:
        return ()
    steps: dict[int, list[EapItemStep]] = {}
    for step in session.scalars(
        select(EapItemStep)
        .where(EapItemStep.item_id.in_([item.id for item in items]))
        .order_by(EapItemStep.item_id, EapItemStep.order)
    ):
        steps.setdefault(step.item_id, []).append(step)
    return tuple((item, _item_progress(item, steps.get(item.id, ()))) for item in items)


def _item_progress(item: EapItem, steps: Sequence[EapItemStep]) -> Decimal:
    """O real corrente do pacote, calculado das entradas do critério, como a fachada lê."""
    return calculations.eap_package_progress(
        item.criterion,
        etapas=tuple(
            calculations.EapStep(name=step.name, weight=step.weight, pct=step.pct) for step in steps
        ),
        quantity=item.quantity,
        executed=item.executed,
        state=item.state,
        estimated_pct=item.estimated_pct,
    )


def _proportional(current: Decimal, real: Decimal, cut: Decimal) -> Decimal:
    """A parcela do real corrente num mês: o real do mês sobre o do corte, com 2 casas."""
    return (current * real / cut).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _curve_months(texts: Sequence[str], reference_date: date) -> tuple[date, ...]:
    """Os meses do mock como o primeiro dia do mês deslocado, como o resto da carga."""
    return tuple(
        shift_date(date.fromisoformat(f"{text}-01"), reference_date).replace(day=1)
        for text in texts
    )


def _eap_revision_ids(session: Session, *, project_id: int) -> tuple[int, ...]:
    """Os ids das revisões da EAP do projeto, da linha de base à vigente."""
    statement = (
        select(EapRevision.id)
        .where(EapRevision.project_id == project_id)
        .order_by(EapRevision.revision)
    )
    return tuple(session.scalars(statement))


def _managers_by_project(ids: _RegisterIds) -> dict[int, int | None]:
    """A pessoa gerente de cada projeto do mock, autora das medições da curva."""
    return {
        source["id"]: ids.person(source["gerenteId"]) for source in prototype_collection("projetos")
    }


def _parent_code(code: str) -> str:
    return code.rsplit(".", maxsplit=1)[0]


def _code_key(code: str) -> tuple[int, ...]:
    return tuple(int(part) for part in code.split("."))


def _decimal_or_none(value: Any) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _shifted_date(value: str | None, reference_date: date) -> date | None:
    return None if value is None else shift_date(date.fromisoformat(value), reference_date)


register(PART_NAME, load)
register(EAP_PART_NAME, load_eap)
register(CURVA_PART_NAME, load_curva)
