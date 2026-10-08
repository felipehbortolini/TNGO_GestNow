"""Governance of the Weekly Scheduling: the panel, the queue and the change requests (D10).

The numbers are the app's (``dados.governanca``): one line per company and week, the
weighted adherence, the pending approvals that already have done work and the last
non-empty inspector; the queue is the app's Request → Apply, with the decision reopening
the activity. The tests build the scenario of ``tests.cenario_programacao`` and compare
the facade with what the app would print for the same data.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from src.core import calendario
from src.core.errors import AccessDeniedError, InvalidDataError, VersionConflictError
from src.core.models import AuditEntry
from src.modulos.programacao_semanal import calculations, service, weeks
from src.modulos.programacao_semanal.models import Activity, ChangeRequest
from src.modulos.programacao_semanal.service import NewActivity
from src.modulos.programacao_semanal.validation import DecisionForm, DoneForm
from tests.cenario_programacao import WEEK, Scenario

PENDING = service.REQUEST_PENDING
APPLIED = service.REQUEST_APPLIED
REJECTED = service.REQUEST_REJECTED
AUTO_INSPECTOR = -1
LONG_REASON = "A medição de quarta saiu trocada com a de quinta na conferência."


def _store(
    scenario: Scenario,
    *,
    unique_id: str = "G-1",
    company_id: int | None = None,
    week: str = WEEK,
    item: int = 1,
    situation: str = calculations.SITUATION_DRAFT,
    approval: str = calculations.APPROVAL_PENDING,
    planned: float = 100.0,
    done: float = 0.0,
    inspector_id: int = AUTO_INSPECTOR,
) -> object:
    """One activity of the scenario with the numbers each governance case needs."""
    validated = situation != calculations.SITUATION_DRAFT
    if inspector_id == AUTO_INSPECTOR:
        inspector = scenario.fiscal.person_id if validated else None
    else:
        inspector = inspector_id
    return service.store_activity(
        scenario.session,
        author_id=scenario.author_id,
        new=NewActivity(
            project_id=scenario.project_id,
            company_id=company_id or scenario.company_a,
            week=week,
            unique_id=unique_id,
            item=item,
            description=f"Serviço {unique_id}",
            planned_headline=planned,
            author_person_id=scenario.planner.person_id,
            at=calendario.now(),
            location_id=scenario.location_id,
            unit_id=scenario.unit_id,
            foreman_id=scenario.foreman_a,
            inspector_id=inspector,
            planned_days=(planned, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            day_shift=(done, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            situation=situation,
            approval=approval,
            approved_at=calendario.now() if approval == calculations.APPROVAL_APPROVED else None,
        ),
    )


def _closed(scenario: Scenario, *, unique_id: str = "C-1", company_id: int | None = None):
    """An activity where the app offers the change request: published with approved done."""
    return _store(
        scenario,
        unique_id=unique_id,
        company_id=company_id,
        situation=calculations.SITUATION_PUBLISHED,
        approval=calculations.APPROVAL_APPROVED,
        planned=100.0,
        done=100.0,
    )


def _requests(scenario: Scenario) -> int:
    return scenario.session.scalar(select(func.count()).select_from(ChangeRequest)) or 0


# ── O painel: os mesmos números do app ──────────────────────────────────


def test_the_panel_numbers_are_the_apps(scenario: Scenario) -> None:
    """Agrupa por empresa e semana, pondera a aderência e conta a pendência com realizado."""
    service.store_settings(
        scenario.session,
        author_id=scenario.author_id,
        project_id=scenario.project_id,
        parameters=service.ScheduleParameters(reference_week=WEEK),
    )
    _store(
        scenario,
        unique_id="A-1",
        item=1,
        situation=calculations.SITUATION_PUBLISHED,
        approval=calculations.APPROVAL_APPROVED,
        planned=100.0,
        done=100.0,
    )
    _store(
        scenario,
        unique_id="A-2",
        item=2,
        situation=calculations.SITUATION_VALIDATED,
        approval=calculations.APPROVAL_PENDING,
        planned=50.0,
        done=30.0,
        inspector_id=scenario.foreman_a,
    )
    _store(
        scenario,
        unique_id="B-1",
        company_id=scenario.company_b,
        item=1,
        situation=calculations.SITUATION_VALIDATED,
        approval=calculations.APPROVAL_APPROVED,
        planned=50.0,
        done=40.0,
    )

    panel = service.governance_panel(scenario.session, caller=scenario.caller(scenario.planner))

    assert (panel.reference_week, panel.reference_period) == (WEEK, weeks.period_label(WEEK))
    assert (len(panel.lines), panel.active_companies, panel.open_windows) == (2, 2, 1)
    assert panel.is_portfolio is False
    assert panel.can_decide is True
    assert panel.can_view_trail is True

    # Ordenadas da semana mais recente para a mais antiga e, na semana, pela empresa.
    company_b, company_a = panel.lines[0], panel.lines[1]
    assert company_b.company == "Empresa B"
    assert (company_b.total, company_b.validated, company_b.adherence) == (1, 1, 80.0)
    assert company_a.company == "Empresa A"
    assert (
        company_a.total,
        company_a.published,
        company_a.validated,
        company_a.pending,
        company_a.adherence,
    ) == (2, 1, 1, 1, 86.67)
    assert company_a.inspector == "ps-enc-a"
    assert company_a.updated_at_text

    counts = panel.situations
    assert (
        counts.total,
        counts.draft,
        counts.validated,
        counts.published,
        counts.approved,
        counts.pending,
        counts.no_done,
    ) == (3, 0, 2, 1, 2, 1, 0)

    window = panel.windows[0]
    assert (window.company, window.is_open, window.released_count, window.extras) == (
        "Empresa A",
        True,
        1,
        0,
    )
    assert (window.weekday_label, window.opens, window.closes) == ("Sexta-feira", "08:00", "15:00")


def test_the_panel_of_the_portfolio_and_of_the_supplier_cut_what_they_show(
    scenario: Scenario,
) -> None:
    _store(scenario, unique_id="A-1")
    _store(scenario, unique_id="B-1", company_id=scenario.company_b)

    supplier = service.governance_panel(
        scenario.session, caller=scenario.caller(scenario.supplier_a)
    )
    assert {line.company for line in supplier.lines} == {"Empresa A"}
    assert supplier.situations.total == 1
    assert supplier.can_decide is False
    assert supplier.can_view_trail is False


# ── Abrir o pedido ──────────────────────────────────────────────────────


def test_a_request_is_recorded_with_its_reason_and_before_and_after(scenario: Scenario) -> None:
    activity = _closed(scenario)

    request = service.request_change(
        scenario.session,
        caller=scenario.caller(scenario.supplier_a),
        activity_id=activity.id,
        reason=LONG_REASON,
    )

    assert (request.situation, request.reason) == (PENDING, LONG_REASON)
    assert request.requested_by_id == scenario.supplier_a.person_id
    entry = scenario.session.scalars(
        select(AuditEntry).where(
            AuditEntry.entity == ChangeRequest.__tablename__,
            AuditEntry.record_id == request.id,
        )
    ).one()
    assert entry.action == "criado"
    assert entry.before is None
    assert entry.after is not None and entry.after["situacao"] == PENDING
    assert entry.project_id == scenario.project_id


def test_a_short_reason_is_refused_with_422(scenario: Scenario) -> None:
    activity = _closed(scenario)

    with pytest.raises(InvalidDataError) as refused:
        service.request_change(
            scenario.session,
            caller=scenario.caller(scenario.supplier_a),
            activity_id=activity.id,
            reason="curto",
        )

    assert "motivo" in refused.value.detail
    assert _requests(scenario) == 0


def test_a_request_on_an_editable_activity_is_refused(scenario: Scenario) -> None:
    activity = _store(scenario)

    with pytest.raises(InvalidDataError) as refused:
        service.request_change(
            scenario.session,
            caller=scenario.caller(scenario.supplier_a),
            activity_id=activity.id,
            reason=LONG_REASON,
        )

    assert "aberta para edição" in str(refused.value)
    assert _requests(scenario) == 0


def test_the_supplier_does_not_ask_for_another_company(scenario: Scenario) -> None:
    other = _closed(scenario, unique_id="B-1", company_id=scenario.company_b)

    with pytest.raises(AccessDeniedError):
        service.request_change(
            scenario.session,
            caller=scenario.caller(scenario.supplier_a),
            activity_id=other.id,
            reason=LONG_REASON,
        )

    assert _requests(scenario) == 0


def test_a_request_in_the_portfolio_is_refused(scenario: Scenario) -> None:
    activity = _closed(scenario)

    with pytest.raises(InvalidDataError):
        service.request_change(
            scenario.session,
            caller=scenario.caller(scenario.supplier_a, project=False),
            activity_id=activity.id,
            reason=LONG_REASON,
        )

    assert _requests(scenario) == 0


# ── Aplicar e recusar ───────────────────────────────────────────────────


def _request(scenario: Scenario, *, unique_id: str = "C-1") -> ChangeRequest:
    activity = _closed(scenario, unique_id=unique_id)
    return service.request_change(
        scenario.session,
        caller=scenario.caller(scenario.supplier_a),
        activity_id=activity.id,
        reason=LONG_REASON,
    )


def test_applying_reopens_the_activity_with_the_comment_and_the_trail(scenario: Scenario) -> None:
    request = _request(scenario)
    activity_id = request.activity_id

    decided = service.decide_request(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        request_id=request.id,
        form=DecisionForm(
            apply=True, answer="Liberado: ajuste o previsto.", version=str(request.version)
        ),
    )

    assert decided.situation == APPLIED
    assert decided.decided_by == scenario.planner.name
    assert decided.answer == "Liberado: ajuste o previsto."
    assert decided.decided_at_text

    activity = scenario.session.get(Activity, activity_id)
    assert activity.approval == calculations.APPROVAL_PENDING
    assert "Pedido de alteração liberado para alteração" in (activity.timenow_comments or "")
    assert "Liberado: ajuste o previsto." in (activity.timenow_comments or "")

    entries = scenario.session.scalars(
        select(AuditEntry)
        .where(
            AuditEntry.entity == ChangeRequest.__tablename__,
            AuditEntry.record_id == request.id,
        )
        .order_by(AuditEntry.id)
    ).all()
    assert [entry.action for entry in entries] == ["criado", "alterado"]
    assert entries[1].before is not None and entries[1].before["situacao"] == PENDING
    assert entries[1].after is not None and entries[1].after["situacao"] == APPLIED

    labels = [
        event.label for event in service.detail_events(scenario.session, activity_id=activity_id)
    ]
    assert labels == ["Realizado reaberto", "Atividade criada"]


def test_refusing_needs_an_answer_and_keeps_the_activity_closed(scenario: Scenario) -> None:
    request = _request(scenario)

    with pytest.raises(InvalidDataError) as refused:
        service.decide_request(
            scenario.session,
            caller=scenario.caller(scenario.planner),
            request_id=request.id,
            form=DecisionForm(apply=False, answer="não", version=str(request.version)),
        )
    assert "resposta" in refused.value.detail
    assert request.situation == PENDING

    decided = service.decide_request(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        request_id=request.id,
        form=DecisionForm(
            apply=False,
            answer="O item está publicado e medido.",
            version=str(request.version),
        ),
    )

    assert decided.situation == REJECTED
    assert request.answer == "O item está publicado e medido."
    activity = scenario.session.get(Activity, request.activity_id)
    assert activity.approval == calculations.APPROVAL_APPROVED
    assert "Pedido de alteração recusado" in (activity.timenow_comments or "")
    labels = [
        event.label
        for event in service.detail_events(scenario.session, activity_id=request.activity_id)
    ]
    assert labels == ["Pedido de alteração recusado", "Atividade criada"]


def test_a_reopened_activity_accepts_the_done_again(scenario: Scenario) -> None:
    request = _request(scenario)
    activity_id = request.activity_id
    service.decide_request(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        request_id=request.id,
        form=DecisionForm(apply=True, version=str(request.version)),
    )

    service.report_done(
        scenario.session,
        caller=scenario.caller(scenario.supplier_a),
        activity_id=activity_id,
        form=DoneForm(day_shift=(10.0,) * calculations.DAYS, notes="Retomada após a liberação."),
        version=str(scenario.session.get(Activity, activity_id).version),
    )

    view = service.get_activity(
        scenario.session, caller=scenario.caller(scenario.planner), activity_id=activity_id
    )
    assert view.figures.done_total == pytest.approx(70.0)


def test_deciding_is_only_for_the_planner_or_the_admin(scenario: Scenario) -> None:
    for index, user in enumerate(
        (scenario.fiscal, scenario.foreman, scenario.supplier_a, scenario.viewer)
    ):
        request = _request(scenario, unique_id=f"F-{index}")
        with pytest.raises(AccessDeniedError):
            service.decide_request(
                scenario.session,
                caller=scenario.caller(user),
                request_id=request.id,
                form=DecisionForm(apply=True, version=str(request.version)),
            )
        assert request.situation == PENDING

    request = _request(scenario, unique_id="F-9")
    decided = service.decide_request(
        scenario.session,
        caller=scenario.caller(scenario.admin),
        request_id=request.id,
        form=DecisionForm(apply=True, version=str(request.version)),
    )
    assert decided.situation == APPLIED


def test_an_already_decided_request_is_refused(scenario: Scenario) -> None:
    request = _request(scenario)
    service.decide_request(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        request_id=request.id,
        form=DecisionForm(apply=True, version=str(request.version)),
    )

    with pytest.raises(InvalidDataError) as refused:
        service.decide_request(
            scenario.session,
            caller=scenario.caller(scenario.planner),
            request_id=request.id,
            form=DecisionForm(apply=False, answer="Já decidido.", version=str(request.version)),
        )

    assert "já foi decidido" in str(refused.value)


def test_a_stale_version_is_a_conflict(scenario: Scenario) -> None:
    request = _request(scenario)

    with pytest.raises(VersionConflictError):
        service.decide_request(
            scenario.session,
            caller=scenario.caller(scenario.planner),
            request_id=request.id,
            form=DecisionForm(apply=True, version="0"),
        )


# ── A fila ──────────────────────────────────────────────────────────────


def test_the_queue_splits_pending_and_resolved_and_cuts_by_company(scenario: Scenario) -> None:
    first = _request(scenario, unique_id="Q-1")
    second = _request(scenario, unique_id="Q-2")
    service.decide_request(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        request_id=second.id,
        form=DecisionForm(apply=False, answer="Sem mudança.", version=str(second.version)),
    )
    other = _closed(scenario, unique_id="B-1", company_id=scenario.company_b)
    third = service.request_change(
        scenario.session,
        caller=scenario.caller(scenario.supplier_b),
        activity_id=other.id,
        reason=LONG_REASON,
    )

    queue = service.request_queue(scenario.session, caller=scenario.caller(scenario.planner))
    assert queue.total_pending == 2
    assert {view.id for view in queue.pending} == {first.id, third.id}
    assert [view.id for view in queue.resolved] == [second.id]
    assert queue.resolved[0].situation == REJECTED

    supplier_a = service.request_queue(
        scenario.session, caller=scenario.caller(scenario.supplier_a)
    )
    assert supplier_a.total_pending == 1
    assert [view.unique_id for view in supplier_a.pending] == ["Q-1"]
    assert [view.unique_id for view in supplier_a.resolved] == ["Q-2"]

    supplier_b = service.request_queue(
        scenario.session, caller=scenario.caller(scenario.supplier_b)
    )
    assert [view.unique_id for view in supplier_b.pending] == ["B-1"]
    assert supplier_b.resolved == []


def test_the_resolved_list_keeps_the_apps_limit(scenario: Scenario) -> None:
    assert service.REQUEST_RESOLVED_LIMIT == 20
    for index in range(service.REQUEST_RESOLVED_LIMIT + 1):
        request = service.request_change(
            scenario.session,
            caller=scenario.caller(scenario.supplier_a),
            activity_id=_closed(scenario, unique_id=f"C-{index}").id,
            reason=LONG_REASON,
        )
        service.decide_request(
            scenario.session,
            caller=scenario.caller(scenario.planner),
            request_id=request.id,
            form=DecisionForm(apply=True, version=str(request.version)),
        )

    queue = service.request_queue(scenario.session, caller=scenario.caller(scenario.planner))

    assert len(queue.resolved) == service.REQUEST_RESOLVED_LIMIT


# ── A trilha ────────────────────────────────────────────────────────────


def test_the_trail_filters_the_module_and_leaves_the_days_out(scenario: Scenario) -> None:
    request = _request(scenario)
    service.decide_request(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        request_id=request.id,
        form=DecisionForm(apply=True, version=str(request.version)),
    )

    trail = service.governance_trail(scenario.session, caller=scenario.caller(scenario.planner))

    # As linhas da atividade e da janela vêm do registrador da plataforma (carimbo do
    # relógio real, mais novo); as do pedido carregam o instante do chamador, mais antigo.
    assert [event.label for event in trail] == [
        "Realizado reaberto",
        "Atividade criada",
        "Janela de programação criada",
        "Pedido de alteração aplicado",
        "Pedido de alteração aberto",
    ]
    assert trail[3].actor == scenario.planner.name
    assert trail[3].when
    assert trail[4].summary == LONG_REASON


def test_the_trail_is_only_for_the_planner(scenario: Scenario) -> None:
    for user in (scenario.fiscal, scenario.supplier_a, scenario.viewer):
        with pytest.raises(AccessDeniedError):
            service.governance_trail(scenario.session, caller=scenario.caller(user))
