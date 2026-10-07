"""Part of the Financeiro module in the demonstration load (ISSUE-029 a ISSUE-031, D6).

Reads the ``eac`` collection of the prototype and writes the tree of each project through the
facade. The quantity and the unit price of the prototype are kept as they are, and the budgeted
value is their product, as in the product (the prototype also stored a ``base`` that rounded the
last cents; see ``docs/DIVERGENCIAS-DO-PROTOTIPO.md``). The items carry no date, so there is
nothing to shift with ``shift_date``.

:func:`load_revisions` is the part of ISSUE-030: it writes the revisions of ``eacRevisoes`` with
the frozen baseline of every item, and the applied reallocations of ``eacRemanejamentos``. It is
called by the ``governanca-eac`` part (``governanca/seed.py``), which runs after ``governanca``:
the revisions point at the SMs that originated them and the applied reallocations at the SMs that
were decided, and those only exist after the changes are loaded.

:func:`load_erp_costs` is the part of ISSUE-031: the commitments, the realized values and the
projections of the prototype enter as the monthly closing of the ERP, one fact per cost item in
the month of the run's reference date. The prototype has no ``historicoProjecao``, so the load
writes no ``eac_projecao``.

:func:`load_contracts` is the part of ISSUE-032: the contracts of ``contratos`` with their addenda
and measurements. It is registered by ``governanca/seed.py`` (the ``financeiro-contratos`` part)
because the addendum points at the SM that originated it, and the changes only exist after
``governanca`` — the same reason ``load_revisions`` runs in the ``governanca-eac`` part. The
measurements do **not** feed ``custo_erp``: in the mock the realized value of the item already
comes from the ERP closing, and it is the approval through the screen that adds the gross value
(``service.transition_measurement``).

:func:`load_contract_flows` is the part of ISSUE-033: the payment milestones of ``marcosPagamento``,
the claims of ``claims`` and the time extensions of ``extensoesPrazo``, with the dates shifted by
the anchor. It also closes what the previous part left open: the measurements are linked to their
milestone (``marcoId``), the addenda and the claims to their claim (``claimRef``), the claims to
their change (``smRef``) and to their risk (``riscoRef``). It is registered by ``riscos/seed.py``
because the claim points at the risk by code, and the risks only exist after the ``riscos`` part;
the flow part is the last of the demonstration.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.carga import prototype_collection, register, shift_date
from src.carga.plataforma import ADMIN_EMAIL
from src.core import calendario, recording
from src.core.rbac import Bond, GeneralProfile, User
from src.modulos.configuracoes import service as configuracoes
from src.modulos.financeiro import service
from src.modulos.financeiro.calculations import CODE_SEPARATOR, LEAF_LEVEL, code_key
from src.modulos.financeiro.models import (
    Contract,
    ContractAddendum,
    ContractClaim,
    ContractMeasurement,
    ContractPaymentMilestone,
    ContractTimeExtension,
    EacReallocation,
    EacRevision,
    EacRevisionItem,
    ErpCost,
)

PART_NAME = "financeiro"
ERP_PART_NAME = "financeiro-custos"
CONTRACTS_PART_NAME = "financeiro-contratos"
FLOWS_PART_NAME = "financeiro-contratos-fluxos"


def load(session: Session, _reference_date: date) -> None:
    """Write the EAC tree of every project of the prototype, inside the caller's transaction."""
    admin = configuracoes.find_access_by_email(session, ADMIN_EMAIL)
    if admin is None:
        return
    project_ids = {project.code: project.id for project in configuracoes.list_projects(session)}
    mock_codes = {project["id"]: project["codigo"] for project in prototype_collection("projetos")}
    mock_emails = {person["id"]: person["email"] for person in prototype_collection("pessoas")}
    people = {person.email: person.id for person in configuracoes.list_people(session)}
    units = {unit.code: unit.id for unit in configuracoes.list_measure_units(session)}
    created: dict[tuple[int, str], int] = {}
    sources = sorted(
        prototype_collection("eac"), key=lambda item: (item["projetoId"], code_key(item["codigo"]))
    )
    for source in sources:
        project_id = project_ids[mock_codes[source["projetoId"]]]
        parent_code = CODE_SEPARATOR.join(source["codigo"].split(CODE_SEPARATOR)[:-1])
        responsible = source.get("responsavelId")
        created[(project_id, source["codigo"])] = service.create_item(
            session,
            user_id=admin.id,
            new=_new_item(
                source,
                project_id=project_id,
                parent_id=created.get((project_id, parent_code)),
                unit_id=units.get(source.get("unidade") or ""),
                responsible_id=people.get(mock_emails[responsible]) if responsible else None,
            ),
        )


def _new_item(
    source: dict[str, Any],
    *,
    project_id: int,
    parent_id: int | None,
    unit_id: int | None,
    responsible_id: int | None,
) -> service.NewItem:
    quantity = source.get("quantidade")
    return service.NewItem(
        project_id=project_id,
        code=source["codigo"],
        description=source["descricao"],
        level=source["nivel"],
        parent_id=parent_id,
        unit_id=unit_id,
        responsible_id=responsible_id,
        cost_type=source.get("tipoCusto"),
        quantity=Decimal(str(quantity)) if quantity is not None else None,
        unit_price_cents=source.get("precoUnitario"),
        capex=source.get("capex"),
        cost_center=source.get("centroCusto"),
    )


# ── Revisões e remanejamentos aplicados (ISSUE-030) ──────────────────────


@dataclass(frozen=True)
class _EacLookup:
    """Os ids reais que o mock aponta: projeto, pessoa, SM e item da EAC por código."""

    projects: Mapping[int, int]
    people: Mapping[int, int]
    changes: Mapping[str, int]
    items: Mapping[tuple[int, str], int]

    @classmethod
    def build(cls, session: Session) -> _EacLookup:
        from src.modulos.governanca import service as governanca

        real_projects = {
            project.code: project.id for project in configuracoes.list_projects(session)
        }
        projects = {
            source["id"]: real_projects[source["codigo"]]
            for source in prototype_collection("projetos")
        }
        people = {
            source["id"]: person_id
            for source in prototype_collection("pessoas")
            if (person_id := configuracoes.find_person_id_by_email(session, source["email"]))
        }
        changes = governanca.change_ids_by_code(
            session, codes=[source["codigo"] for source in prototype_collection("mudancas")]
        )
        items: dict[tuple[int, str], int] = {}
        for mock_project_id, project_id in projects.items():
            codes = [
                source["codigo"]
                for source in prototype_collection("eac")
                if source["projetoId"] == mock_project_id and source["nivel"] == 3
            ]
            found = service.eac_item_ids_by_code(session, project_id=project_id, codes=codes)
            items.update({(mock_project_id, code): item_id for code, item_id in found.items()})
        return cls(projects=projects, people=people, changes=changes, items=items)


@dataclass(frozen=True)
class _LoadContext:
    """O que a escrita de cada revisão e de cada remanejamento precisa, resolvido uma vez."""

    admin_id: int
    lookup: _EacLookup
    deltas: Mapping[str, Mapping[str, int]]
    mock_items: Mapping[int, Mapping[str, int]]
    reference_date: date


def load_revisions(session: Session, reference_date: date) -> None:
    """Write the revisions with the frozen baseline and the applied reallocations of the prototype.

    The latest revision of each project freezes the ``base`` of the mock; each earlier one is the
    next minus the cost of the SM that generated the next (``eacItens`` of its impact), so the
    sums match the totals of ``eacRevisoes``. The applied reallocations point at the next revision
    (the one that will consolidate them), not at the revision in force when they were applied.
    """
    admin = configuracoes.find_access_by_email(session, ADMIN_EMAIL)
    if admin is None:
        return
    context = _LoadContext(
        admin_id=admin.id,
        lookup=_EacLookup.build(session),
        deltas=_impact_deltas(),
        mock_items=_mock_items(),
        reference_date=reference_date,
    )
    for mock_project_id, sources in _revisions_by_project().items():
        _load_project_revisions(session, context, mock_project_id=mock_project_id, sources=sources)
    for source in prototype_collection("eacRemanejamentos"):
        _load_reallocation(session, context, source=source)


def _load_project_revisions(
    session: Session,
    context: _LoadContext,
    *,
    mock_project_id: int,
    sources: Sequence[Mapping[str, Any]],
) -> None:
    lookup = context.lookup
    project_id = lookup.projects[mock_project_id]
    ordered = sorted(sources, key=lambda source: source["revisao"])
    bases = dict(context.mock_items[mock_project_id])
    for index in range(len(ordered) - 1, -1, -1):
        source = ordered[index]
        if index < len(ordered) - 1:
            bases = _previous_bases(
                bases, sm_ref=ordered[index + 1].get("smRef"), deltas=context.deltas
            )
        record = recording.create(
            session,
            user_id=context.admin_id,
            record=EacRevision(
                project_id=project_id,
                change_id=lookup.changes.get(source.get("smRef") or ""),
                approved_by_id=lookup.people.get(source["aprovadoPorId"], context.admin_id),
                revision=source["revisao"],
                revision_date=shift_date(
                    date.fromisoformat(source["data"]), context.reference_date
                ),
                justification=source["justificativa"],
            ),
        )
        session.add_all(
            EacRevisionItem(
                revision_id=record.id,
                item_id=lookup.items[(mock_project_id, code)],
                base_cents=base_cents,
            )
            for code, base_cents in bases.items()
        )
        session.flush()


def _previous_bases(
    bases: Mapping[str, int], *, sm_ref: str | None, deltas: Mapping[str, Mapping[str, int]]
) -> dict[str, int]:
    """A linha de base anterior: a atual menos o que a SM que gerou a revisão acrescentou."""
    if not sm_ref or sm_ref not in deltas:
        message = (
            f"A revisão anterior da demonstração precisa da SM {sm_ref!r} com impacto em custo."
        )
        raise LookupError(message)
    previous = dict(bases)
    for code, value_cents in deltas[sm_ref].items():
        previous[code] = previous.get(code, 0) - value_cents
    return previous


def _load_reallocation(
    session: Session, context: _LoadContext, *, source: Mapping[str, Any]
) -> None:
    lookup = context.lookup
    mock_project_id = source["projetoId"]
    project_id = lookup.projects[mock_project_id]
    latest = session.scalar(
        select(func.max(EacRevision.revision)).where(EacRevision.project_id == project_id)
    )
    recording.create(
        session,
        user_id=context.admin_id,
        record=EacReallocation(
            project_id=project_id,
            source_item_id=lookup.items[(mock_project_id, source["origem"])],
            target_item_id=lookup.items[(mock_project_id, source["destino"])],
            applied_by_id=lookup.people.get(source["porId"], context.admin_id),
            change_id=lookup.changes.get(source["smRef"]),
            revision=(latest or 0) + 1,
            applied_on=shift_date(date.fromisoformat(source["data"]), context.reference_date),
            value_cents=int(source["valorCentavos"]),
            new_item=bool(source.get("novoItem")),
            justification=source.get("justificativa"),
        ),
    )


def _revisions_by_project() -> dict[int, list[Mapping[str, Any]]]:
    grouped: dict[int, list[Mapping[str, Any]]] = {}
    for source in prototype_collection("eacRevisoes"):
        grouped.setdefault(source["projetoId"], []).append(source)
    return grouped


def _mock_items() -> dict[int, dict[str, int]]:
    """A base vigente do mock de cada item de nível 3, por projeto: a linha de base da última revisão."""
    items: dict[int, dict[str, int]] = {}
    for source in prototype_collection("eac"):
        if source["nivel"] != 3:
            continue
        items.setdefault(source["projetoId"], {})[source["codigo"]] = int(source["base"])
    return items


def _impact_deltas() -> dict[str, dict[str, int]]:
    """O valor que cada SM aprovada acrescentou à EAC, por item afetado (``eacItens``)."""
    deltas: dict[str, dict[str, int]] = {}
    for source in prototype_collection("mudancas"):
        impact = source.get("impacto") or {}
        cost_cents = int(impact.get("custoCentavos") or 0)
        codes = tuple(impact.get("eacItens") or ())
        if cost_cents <= 0 or not codes:
            continue
        share, remainder = divmod(cost_cents, len(codes))
        deltas[source["codigo"]] = {
            code: share + (remainder if index == 0 else 0) for index, code in enumerate(codes)
        }
    return deltas


# ── Custos do ERP (ISSUE-031) ────────────────────────────────────────────


def load_erp_costs(session: Session, reference_date: date) -> None:
    """Grava o fechamento do ERP do protótipo: um fato por item de custo, no mês da data de corte.

    O mock guarda comprometido, realizado e projeção por item; as datas da carga são deslocadas
    pela âncora, então todos os fatos caem no mês da data de referência e a projeção no término do
    projeto 1 fecha ``4.525.500.000`` centavos (os R$ 45,26 mi do oráculo).
    """
    admin = configuracoes.find_access_by_email(session, ADMIN_EMAIL)
    if admin is None:
        return
    project_ids = {project.code: project.id for project in configuracoes.list_projects(session)}
    mock_codes = {project["id"]: project["codigo"] for project in prototype_collection("projetos")}
    month = reference_date.replace(day=1)
    imported_at = calendario.now()
    for source in prototype_collection("eac"):
        if source["nivel"] != LEAF_LEVEL:
            continue
        project_id = project_ids[mock_codes[source["projetoId"]]]
        item_id = service.eac_item_ids_by_code(
            session, project_id=project_id, codes=[source["codigo"]]
        ).get(source["codigo"])
        if item_id is None:
            continue
        recording.create(
            session,
            user_id=admin.id,
            record=ErpCost(
                project_id=project_id,
                item_id=item_id,
                imported_by_id=admin.person_id,
                month=month,
                committed_cents=int(source["comprometido"]),
                actual_cents=int(source["realizado"]),
                projection_cents=int(source["projecao"]),
                imported_at=imported_at,
            ),
        )


# ── Contratos, aditivos e medições (ISSUE-032) ───────────────────────────


@dataclass(frozen=True)
class _ContractLookup:
    """Os ids reais que o mock dos contratos aponta: projeto, pessoa, empresa e SM por código."""

    projects: Mapping[int, int]
    people: Mapping[int, int]
    companies: Mapping[int, int]
    changes: Mapping[str, int]

    @classmethod
    def build(cls, session: Session) -> _ContractLookup:
        from src.modulos.governanca import service as governanca

        real_projects = {
            project.code: project.id for project in configuracoes.list_projects(session)
        }
        projects = {
            source["id"]: real_projects[source["codigo"]]
            for source in prototype_collection("projetos")
        }
        people = {
            source["id"]: person_id
            for source in prototype_collection("pessoas")
            if (person_id := configuracoes.find_person_id_by_email(session, source["email"]))
        }
        real_companies = {
            option.name: option.id for option in configuracoes.list_company_options(session)
        }
        companies = {
            source["id"]: real_companies[source["nome"]]
            for source in prototype_collection("empresas")
        }
        changes = governanca.change_ids_by_code(
            session, codes=[source["codigo"] for source in prototype_collection("mudancas")]
        )
        return cls(projects=projects, people=people, companies=companies, changes=changes)


def load_contracts(session: Session, reference_date: date) -> None:
    """Grava os contratos do protótipo, com os aditivos e as medições, no modo demonstração.

    O contrato nasce da adjudicação no 04 (ISSUE-060); na demonstração ele vem do mock, com o
    item da EAC ligado pelo código (``eacCodigo``) e o ``pacoteCompra`` nulo — a ``pacote_compra``
    só nasce na ISSUE-058/060. O aditivo liga à SM pelo código (``smRef``) e o ``claimRef`` fica
    sem vínculo até a ISSUE-033 criar ``contrato_claim``; o marco da medição fica nulo até a
    parte da carga da ISSUE-033 gravar ``contrato_marco_pagamento``, porque a chave estrangeira
    que a m033 acrescenta exige o marco existente. O ``terminoVigente`` do mock é gravado
    como está: os aditivos da carga não recalculam o término. As medições entram com a situação
    do protótipo e não alimentam ``custo_erp``: no mock o realizado do item já vem do fechamento
    do ERP, e é a aprovação pela tela que soma o bruto ao realizado (``service``).
    """
    admin = configuracoes.find_access_by_email(session, ADMIN_EMAIL)
    if admin is None:
        return
    lookup = _ContractLookup.build(session)
    contracts: dict[int, int] = {}
    for source in prototype_collection("contratos"):
        project_id = lookup.projects[source["projetoId"]]
        item_id = service.eac_item_ids_by_code(
            session, project_id=project_id, codes=[source["eacCodigo"]]
        ).get(source["eacCodigo"])
        record = recording.create(
            session,
            user_id=admin.id,
            record=Contract(
                project_id=project_id,
                company_id=lookup.companies[source["empresaId"]],
                eac_item_id=item_id,
                purchase_package_id=None,
                manager_id=lookup.people[source["gestorId"]],
                fiscal_id=lookup.people[source["fiscalId"]],
                number=source["numero"],
                object=source["objeto"],
                modality=source["modalidade"],
                original_value_cents=int(source["valorOriginalCentavos"]),
                start=shift_date(date.fromisoformat(source["inicio"]), reference_date),
                original_end=shift_date(
                    date.fromisoformat(source["terminoOriginal"]), reference_date
                ),
                current_end=shift_date(
                    date.fromisoformat(source["terminoVigente"]), reference_date
                ),
                retention_pct=int(source["retencaoPct"]),
                claim_notice_days=int(source["prazoNotificacaoClaimDias"]),
                situation=source["situacao"],
            ),
        )
        contracts[source["id"]] = record.id
    for source in prototype_collection("aditivos"):
        recording.create(
            session,
            user_id=admin.id,
            record=ContractAddendum(
                contract_id=contracts[source["contratoId"]],
                change_id=lookup.changes.get(source.get("smRef") or ""),
                claim_id=None,
                number=source["numero"],
                signed_on=shift_date(date.fromisoformat(source["data"]), reference_date),
                value_cents=int(source["valorCentavos"]),
                days=int(source["dias"]),
                reason=source["motivo"],
            ),
        )
    for source in prototype_collection("medicoes"):
        period = shift_date(date.fromisoformat(f"{source['periodo']}-01"), reference_date)
        recording.create(
            session,
            user_id=admin.id,
            record=ContractMeasurement(
                contract_id=contracts[source["contratoId"]],
                milestone_id=None,
                number=source["numero"],
                period=period.replace(day=1),
                gross_cents=int(source["brutoCentavos"]),
                situation=source["situacao"],
                return_reason=None,
            ),
        )


register(PART_NAME, load)
register(ERP_PART_NAME, load_erp_costs)


# ── Marcos, claims e EOT (ISSUE-033) ─────────────────────────────────────


def load_contract_flows(session: Session, reference_date: date) -> None:
    """Grava os marcos, claims e EOTs do protótipo e religa medições, aditivos e riscos.

    A parte roda depois de ``financeiro-contratos`` (os contratos, aditivos e medições existem) e
    depois de ``riscos`` (o ``riscoRef`` do claim aponta para o risco pelo código): a Governança
    registra a parte anterior e os Riscos registram esta. As datas vêm deslocadas pela âncora; o
    ``valorCentavos`` do marco é ignorado, porque o valor sai do percentual sobre o valor atual
    (D5b). O ``terminoVigente`` do mock fica como está, como nos aditivos: a EOT concedida da
    carga não recalcula a data. As medições de marco deixam de ficar nulas e recebem o vínculo.
    """
    admin = configuracoes.find_access_by_email(session, ADMIN_EMAIL)
    if admin is None:
        return
    lookup = _ContractLookup.build(session)
    contracts = _contract_ids(session)
    milestones = _load_milestones(
        session, admin=admin, contracts=contracts, reference_date=reference_date
    )
    claims = _load_claims(
        session,
        admin=admin,
        lookup=lookup,
        contracts=contracts,
        reference_date=reference_date,
    )
    _load_extensions(
        session,
        admin=admin,
        contracts=contracts,
        claims=claims,
        reference_date=reference_date,
    )
    _link_measurements(session, contracts=contracts, milestones=milestones)
    _link_addenda(session, contracts=contracts, claims=claims)


def _contract_ids(session: Session) -> dict[int, int]:
    """O id real de cada contrato do mock, pelo número que a carga anterior gravou."""
    numbers = {source["id"]: source["numero"] for source in prototype_collection("contratos")}
    real = {
        number: contract_id
        for contract_id, number in session.execute(select(Contract.id, Contract.number))
    }
    return {mock_id: real[number] for mock_id, number in numbers.items()}


def _load_milestones(
    session: Session,
    *,
    admin: configuracoes.CollaboratorAccess,
    contracts: Mapping[int, int],
    reference_date: date,
) -> dict[int, int]:
    """Grava os marcos de pagamento do mock, na ordem em que o protótipo os lista."""
    created: dict[int, int] = {}
    for source in prototype_collection("marcosPagamento"):
        completed = source.get("conclusao")
        record = recording.create(
            session,
            user_id=admin.id,
            record=ContractPaymentMilestone(
                contract_id=contracts[source["contratoId"]],
                attachment_id=None,
                number=source["numero"],
                description=source["descricao"],
                acceptance_criteria=source["criterio"],
                pct=int(source["pct"]),
                expected_on=shift_date(date.fromisoformat(source["prevista"]), reference_date),
                completed_on=(
                    shift_date(date.fromisoformat(completed), reference_date) if completed else None
                ),
                situation=source["situacao"],
            ),
        )
        created[source["id"]] = record.id
    return created


def _load_claims(
    session: Session,
    *,
    admin: configuracoes.CollaboratorAccess,
    lookup: _ContractLookup,
    contracts: Mapping[int, int],
    reference_date: date,
) -> dict[str, int]:
    """Grava os claims do mock, com a SM e o risco de origem quando o protótipo os aponta."""
    risks = _risk_ids(
        session,
        reference_date=reference_date,
        codes=[
            source["riscoRef"]
            for source in prototype_collection("claims")
            if source.get("riscoRef")
        ],
    )
    created: dict[str, int] = {}
    for source in prototype_collection("claims"):
        recognized = source.get("reconhecidoCentavos")
        recognized_days = source.get("diasReconhecidos")
        closed = source.get("encerramento")
        record = recording.create(
            session,
            user_id=admin.id,
            record=ContractClaim(
                contract_id=contracts[source["contratoId"]],
                risk_id=risks.get(source.get("riscoRef") or ""),
                change_id=lookup.changes.get(source.get("smRef") or ""),
                code=source["codigo"],
                direction=source["direcao"],
                kind=source["tipo"],
                cause=source["causa"],
                description=source["descricao"],
                clause=source.get("clausula"),
                event_date=shift_date(date.fromisoformat(source["evento"]), reference_date),
                notification_date=shift_date(
                    date.fromisoformat(source["notificacao"]), reference_date
                ),
                claimed_cents=int(source["pleiteadoCentavos"]),
                claimed_days=int(source.get("diasPleiteados") or 0),
                recognized_cents=int(recognized) if recognized is not None else None,
                recognized_days=int(recognized_days) if recognized_days is not None else None,
                situation=source["situacao"],
                closed_on=(
                    shift_date(date.fromisoformat(closed), reference_date) if closed else None
                ),
            ),
        )
        created[source["codigo"]] = record.id
    return created


def _risk_ids(session: Session, *, reference_date: date, codes: Sequence[str]) -> dict[str, int]:
    """O id de cada risco do mock pelo código, pela fachada da Riscos (D9)."""
    from src.modulos.riscos import service as riscos

    user = _admin_user(session)
    if user is None:
        return {}
    found: dict[str, int] = {}
    for code in codes:
        risk = riscos.find_risk(session, user=user, code=code, reference_date=reference_date)
        if risk is not None:
            found[code] = risk.id
    return found


def _admin_user(session: Session) -> User | None:
    """O Admin da demonstração como a fachada da Riscos o lê."""
    access = configuracoes.find_access_by_email(session, ADMIN_EMAIL)
    if access is None:
        return None
    return User(
        id=access.id,
        person_id=access.person_id,
        name=access.name,
        email=access.email,
        general_profile=GeneralProfile(access.general_profile),
        bond=Bond(access.bond),
        company_id=access.company_id,
    )


def _load_extensions(
    session: Session,
    *,
    admin: configuracoes.CollaboratorAccess,
    contracts: Mapping[int, int],
    claims: Mapping[str, int],
    reference_date: date,
) -> None:
    """Grava as extensões de prazo do mock, ligadas ao claim de origem quando ele existe."""
    for source in prototype_collection("extensoesPrazo"):
        granted = source.get("diasConcedidos")
        decided = source.get("decisao")
        recording.create(
            session,
            user_id=admin.id,
            record=ContractTimeExtension(
                contract_id=contracts[source["contratoId"]],
                claim_id=claims.get(source.get("claimRef") or ""),
                change_id=None,
                code=source["codigo"],
                event=source["evento"],
                requested_days=int(source["diasSolicitados"]),
                granted_days=int(granted) if granted is not None else None,
                classification=source.get("classificacao"),
                method=source["metodo"],
                affected_milestone=source["marcoAfetado"],
                requested_on=shift_date(date.fromisoformat(source["data"]), reference_date),
                decided_on=(
                    shift_date(date.fromisoformat(decided), reference_date) if decided else None
                ),
                situation=source["situacao"],
            ),
        )


def _link_measurements(
    session: Session, *, contracts: Mapping[int, int], milestones: Mapping[int, int]
) -> None:
    """Religa a medição de marco ao marco gravado, revertendo o ``milestone_id`` nulo provisório."""
    for source in prototype_collection("medicoes"):
        mock_milestone = source.get("marcoId")
        if mock_milestone is None:
            continue
        record = session.scalars(
            select(ContractMeasurement).where(
                ContractMeasurement.contract_id == contracts[source["contratoId"]],
                ContractMeasurement.number == source["numero"],
            )
        ).one_or_none()
        if record is not None:
            record.milestone_id = milestones[mock_milestone]
    session.flush()


def _link_addenda(
    session: Session, *, contracts: Mapping[int, int], claims: Mapping[str, int]
) -> None:
    """Religa o aditivo ao claim de origem, revertendo o ``claim_id`` nulo provisório."""
    for source in prototype_collection("aditivos"):
        claim_code = source.get("claimRef")
        if not claim_code:
            continue
        record = session.scalars(
            select(ContractAddendum).where(
                ContractAddendum.contract_id == contracts[source["contratoId"]],
                ContractAddendum.number == source["numero"],
            )
        ).one_or_none()
        if record is not None:
            record.claim_id = claims[claim_code]
    session.flush()
