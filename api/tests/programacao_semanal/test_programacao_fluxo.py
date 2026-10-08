"""Flow of five steps of the Weekly Scheduling: roles, transitions and the deviation rule.

The queue of the next action is ported from the app's ``test_dominio.py`` (profile against
state) and adapted to the per-project roles of D7; the transitions and the deviation rule
come from ``core/dados.py`` and the blueprints of the app (validar, realizado, aprovar,
reabrir, publicar), with the names of the code in English.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from src.core import calendario
from src.core.errors import AccessDeniedError, InvalidDataError, VersionConflictError
from src.core.models import AuditEntry
from src.modulos.programacao_semanal import calculations, permissions, service
from src.modulos.programacao_semanal.models import Activity, ActivityDay
from src.modulos.programacao_semanal.service import NewActivity
from src.modulos.programacao_semanal.validation import ApprovalForm, DoneForm, ValidationForm
from tests.cenario_programacao import WEEK, Scenario

SITUATIONS = calculations.SITUATIONS
APPROVALS = calculations.APPROVALS


def _store(
    scenario: Scenario,
    *,
    unique_id: str = "A-1",
    company_id: int | None = None,
    situation: str = calculations.SITUATION_DRAFT,
    approval: str = calculations.APPROVAL_PENDING,
    day_shift: tuple[float, ...] = (0.0,) * calculations.DAYS,
    night_shift: tuple[float, ...] = (0.0,) * calculations.DAYS,
    notes: str = "",
    item: int = 1,
) -> Activity:
    """One activity of the scenario in any state of the flow, written by the facade."""
    validated = situation != calculations.SITUATION_DRAFT
    return service.store_activity(
        scenario.session,
        author_id=scenario.author_id,
        new=NewActivity(
            project_id=scenario.project_id,
            company_id=company_id or scenario.company_a,
            week=WEEK,
            unique_id=unique_id,
            item=item,
            description=f"Serviço {unique_id}",
            planned_headline=70.0,
            author_person_id=scenario.planner.person_id,
            at=calendario.now(),
            location_id=scenario.location_id,
            unit_id=scenario.unit_id,
            foreman_id=scenario.foreman_a,
            inspector_id=scenario.fiscal.person_id if validated else None,
            planned_days=(10.0,) * calculations.DAYS,
            day_shift=day_shift,
            night_shift=night_shift,
            situation=situation,
            approval=approval,
            supplier_notes=notes,
            approved_at=calendario.now() if approval == calculations.APPROVAL_APPROVED else None,
        ),
    )


def _form_state(*, situation: str, approval: str, has_done: bool) -> dict[str, object]:
    return {
        "situation": situation,
        "approval": approval,
        "has_done": has_done,
    }


# ── Próxima ação: o botão principal da linha ────────────────────────────


def test_fiscal_ve_aprovar_onde_a_contratada_ve_lancar(scenario: Scenario) -> None:
    """O mesmo estado, o botão de cada um."""
    state = _form_state(
        situation=calculations.SITUATION_VALIDATED,
        approval=calculations.APPROVAL_PENDING,
        has_done=True,
    )
    assert permissions.next_action(scenario.fiscal, scenario.project_id, **state) == "aprovar"
    assert permissions.next_action(scenario.supplier_a, scenario.project_id, **state) == "lancar"


def test_visualizador_so_ve(scenario: Scenario) -> None:
    """Sem papel de nenhum degrau, o botão é sempre o de leitura."""
    for situation in SITUATIONS:
        for approval in APPROVALS:
            state = _form_state(situation=situation, approval=approval, has_done=True)
            assert permissions.next_action(scenario.viewer, scenario.project_id, **state) == "ver"


def test_realizado_aprovado_vira_publicar(scenario: Scenario) -> None:
    """Lançado e aprovado: o que falta é liberar a semana."""
    state = _form_state(
        situation=calculations.SITUATION_VALIDATED,
        approval=calculations.APPROVAL_APPROVED,
        has_done=True,
    )
    assert permissions.next_action(scenario.planner, scenario.project_id, **state) == "publicar"
    assert permissions.next_action(scenario.admin, scenario.project_id, **state) == "publicar"


def test_publicada_nao_oferece_publicar_de_novo(scenario: Scenario) -> None:
    state = _form_state(
        situation=calculations.SITUATION_PUBLISHED,
        approval=calculations.APPROVAL_APPROVED,
        has_done=True,
    )
    assert permissions.next_action(scenario.planner, scenario.project_id, **state) == "ver"


def test_administrador_percorre_a_fila_na_ordem_do_fluxo(scenario: Scenario) -> None:
    """Quem pode tudo recebe um degrau de cada vez, na ordem do processo.

    É o caso que a ordem dos testes dentro de ``next_action`` protege: com aprovar
    depois de lançar, o administrador veria "Lançar" sobre um realizado que já está
    pronto e parado esperando o fiscal.
    """
    esperado = [
        (calculations.SITUATION_DRAFT, calculations.APPROVAL_PENDING, False, "validar"),
        (calculations.SITUATION_VALIDATED, calculations.APPROVAL_PENDING, False, "lancar"),
        (calculations.SITUATION_VALIDATED, calculations.APPROVAL_PENDING, True, "aprovar"),
        (calculations.SITUATION_VALIDATED, calculations.APPROVAL_APPROVED, True, "publicar"),
        (calculations.SITUATION_PUBLISHED, calculations.APPROVAL_APPROVED, True, "ver"),
    ]
    assert [
        permissions.next_action(
            scenario.admin,
            scenario.project_id,
            **_form_state(situation=situation, approval=approval, has_done=has_done),
        )
        for situation, approval, has_done, _ in esperado
    ] == [action for _, _, _, action in esperado]


def test_the_queue_does_not_cross_projects(scenario: Scenario) -> None:
    """O papel vale só no projeto em que foi dado (D7)."""
    state = _form_state(
        situation=calculations.SITUATION_DRAFT,
        approval=calculations.APPROVAL_PENDING,
        has_done=False,
    )
    assert permissions.next_action(scenario.planner, scenario.other_project_id, **state) == "ver"


# ── Validar ─────────────────────────────────────────────────────────────


def test_validation_names_the_inspector_and_leaves_the_comments(scenario: Scenario) -> None:
    activity = _store(scenario)

    service.validate_activity(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        activity_id=activity.id,
        form=ValidationForm(inspector_id=scenario.fiscal.person_id, comments="Conferido em campo."),
        version=str(activity.version),
    )

    assert activity.situation == calculations.SITUATION_VALIDATED
    assert activity.inspector_id == scenario.fiscal.person_id
    assert "Conferido em campo." in (activity.timenow_comments or "")


def test_validation_without_the_inspector_is_422(scenario: Scenario) -> None:
    activity = _store(scenario)

    with pytest.raises(InvalidDataError) as refused:
        service.validate_activity(
            scenario.session,
            caller=scenario.caller(scenario.planner),
            activity_id=activity.id,
            form=ValidationForm(),
            version=str(activity.version),
        )

    assert "responsavel" in refused.value.detail


def test_validation_of_an_already_validated_activity_is_422(scenario: Scenario) -> None:
    activity = _store(
        scenario, situation=calculations.SITUATION_VALIDATED, approval=calculations.APPROVAL_PENDING
    )

    with pytest.raises(InvalidDataError) as refused:
        service.validate_activity(
            scenario.session,
            caller=scenario.caller(scenario.planner),
            activity_id=activity.id,
            form=ValidationForm(inspector_id=scenario.fiscal.person_id),
            version=str(activity.version),
        )

    assert "em elaboração" in str(refused.value)


def test_validation_by_the_wrong_role_is_403(scenario: Scenario) -> None:
    activity = _store(scenario)

    with pytest.raises(AccessDeniedError):
        service.validate_activity(
            scenario.session,
            caller=scenario.caller(scenario.supplier_a),
            activity_id=activity.id,
            form=ValidationForm(inspector_id=scenario.fiscal.person_id),
            version=str(activity.version),
        )


def test_validation_with_a_stale_version_is_409(scenario: Scenario) -> None:
    activity = _store(scenario)

    with pytest.raises(VersionConflictError):
        service.validate_activity(
            scenario.session,
            caller=scenario.caller(scenario.planner),
            activity_id=activity.id,
            form=ValidationForm(inspector_id=scenario.fiscal.person_id),
            version="0",
        )


# ── Lançar o realizado ──────────────────────────────────────────────────


def test_report_writes_the_two_shifts_of_every_day(scenario: Scenario) -> None:
    activity = _store(scenario, situation=calculations.SITUATION_VALIDATED)

    service.report_done(
        scenario.session,
        caller=scenario.caller(scenario.supplier_a),
        activity_id=activity.id,
        form=DoneForm(day_shift=(9.0,) * 7, night_shift=(1.0,) * 7),
        version=str(activity.version),
    )

    days = scenario.session.scalars(
        select(ActivityDay).where(ActivityDay.activity_id == activity.id).order_by(ActivityDay.day)
    ).all()
    assert [(day.done_day_shift, day.done_night_shift) for day in days] == [(9.0, 1.0)] * 7


def test_the_foreman_reports_as_well(scenario: Scenario) -> None:
    activity = _store(scenario, situation=calculations.SITUATION_VALIDATED)

    service.report_done(
        scenario.session,
        caller=scenario.caller(scenario.foreman),
        activity_id=activity.id,
        form=DoneForm(day_shift=(10.0,) * 7),
        version=str(activity.version),
    )

    assert service.get_activity(
        scenario.session, caller=scenario.caller(scenario.planner), activity_id=activity.id
    ).figures.done_total == pytest.approx(70.0)


def test_report_negative_quantity_is_422(scenario: Scenario) -> None:
    activity = _store(scenario, situation=calculations.SITUATION_VALIDATED)

    with pytest.raises(InvalidDataError) as refused:
        service.report_done(
            scenario.session,
            caller=scenario.caller(scenario.supplier_a),
            activity_id=activity.id,
            form=DoneForm(day_shift=(-1.0,) * 7),
            version=str(activity.version),
        )

    assert "dias_realizado" in refused.value.detail


def test_report_before_the_validation_is_403(scenario: Scenario) -> None:
    activity = _store(scenario)

    with pytest.raises(AccessDeniedError):
        service.report_done(
            scenario.session,
            caller=scenario.caller(scenario.supplier_a),
            activity_id=activity.id,
            form=DoneForm(day_shift=(1.0,) * 7),
            version=str(activity.version),
        )


def test_report_of_an_approved_done_is_403(scenario: Scenario) -> None:
    activity = _store(
        scenario,
        situation=calculations.SITUATION_VALIDATED,
        approval=calculations.APPROVAL_APPROVED,
        day_shift=(5.0,) * 7,
    )

    with pytest.raises(AccessDeniedError):
        service.report_done(
            scenario.session,
            caller=scenario.caller(scenario.supplier_a),
            activity_id=activity.id,
            form=DoneForm(day_shift=(8.0,) * 7),
            version=str(activity.version),
        )


def test_report_for_another_company_is_403(scenario: Scenario) -> None:
    other = _store(
        scenario,
        unique_id="B-1",
        company_id=scenario.company_b,
        situation=calculations.SITUATION_VALIDATED,
    )

    with pytest.raises(AccessDeniedError):
        service.report_done(
            scenario.session,
            caller=scenario.caller(scenario.supplier_a),
            activity_id=other.id,
            form=DoneForm(day_shift=(5.0,) * 7),
            version=str(other.version),
        )


def test_report_by_the_wrong_role_is_403(scenario: Scenario) -> None:
    activity = _store(scenario, situation=calculations.SITUATION_VALIDATED)

    with pytest.raises(AccessDeniedError):
        service.report_done(
            scenario.session,
            caller=scenario.caller(scenario.fiscal),
            activity_id=activity.id,
            form=DoneForm(day_shift=(5.0,) * 7),
            version=str(activity.version),
        )


# ── O desvio acima do limite exige observação ───────────────────────────


def test_a_deviation_past_the_limit_demands_a_note(scenario: Scenario) -> None:
    activity = _store(scenario, situation=calculations.SITUATION_VALIDATED)

    with pytest.raises(InvalidDataError) as refused:
        service.report_done(
            scenario.session,
            caller=scenario.caller(scenario.supplier_a),
            activity_id=activity.id,
            form=DoneForm(day_shift=(0.0,) * 7),
            version=str(activity.version),
        )

    assert "Explique o desvio" in str(refused.value)
    assert "15%" in str(refused.value)


def test_a_deviation_inside_the_limit_needs_no_note(scenario: Scenario) -> None:
    activity = _store(scenario, situation=calculations.SITUATION_VALIDATED)

    service.report_done(
        scenario.session,
        caller=scenario.caller(scenario.supplier_a),
        activity_id=activity.id,
        form=DoneForm(day_shift=(11.0,) * 7),
        version=str(activity.version),
    )

    assert activity.supplier_notes in ("", None)


def test_the_note_frees_the_deviation_and_is_kept(scenario: Scenario) -> None:
    activity = _store(scenario, situation=calculations.SITUATION_VALIDATED)

    service.report_done(
        scenario.session,
        caller=scenario.caller(scenario.supplier_a),
        activity_id=activity.id,
        form=DoneForm(day_shift=(1.0,) * 7, notes="Chuva na terça e quarta."),
        version=str(activity.version),
    )

    assert activity.supplier_notes == "Chuva na terça e quarta."


def test_the_deviation_rule_can_be_off_for_the_project(scenario: Scenario) -> None:
    service.store_settings(
        scenario.session,
        author_id=scenario.author_id,
        project_id=scenario.project_id,
        parameters=service.ScheduleParameters(requires_deviation_note=False),
    )
    activity = _store(scenario, situation=calculations.SITUATION_VALIDATED)

    service.report_done(
        scenario.session,
        caller=scenario.caller(scenario.supplier_a),
        activity_id=activity.id,
        form=DoneForm(day_shift=(0.0,) * 7),
        version=str(activity.version),
    )

    assert activity.supplier_notes in ("", None)


def test_deviation_percent_is_the_apps_formula() -> None:
    assert calculations.deviation_percent(70.0, 100.0) == pytest.approx(30.0)
    assert calculations.deviation_percent(100.0, 100.0) == 0.0
    assert calculations.deviation_percent(0.0, 0.0) == 0.0
    assert calculations.deviation_percent(115.0, 100.0) == pytest.approx(15.0)


# ── Aprovar e reabrir ───────────────────────────────────────────────────


def test_approval_stamps_the_inspector_and_freezes_the_done(scenario: Scenario) -> None:
    activity = _store(scenario, situation=calculations.SITUATION_VALIDATED, day_shift=(5.0,) * 7)

    service.approve_activity(
        scenario.session,
        caller=scenario.caller(scenario.fiscal),
        activity_id=activity.id,
        form=ApprovalForm(comments="Conferido em campo."),
        version=str(activity.version),
    )

    assert activity.approval == calculations.APPROVAL_APPROVED
    assert activity.approved_by_id == scenario.fiscal.person_id
    assert activity.approved_at is not None
    assert "Conferido em campo." in (activity.timenow_comments or "")
    with pytest.raises(AccessDeniedError):
        service.report_done(
            scenario.session,
            caller=scenario.caller(scenario.supplier_a),
            activity_id=activity.id,
            form=DoneForm(day_shift=(8.0,) * 7),
            version=str(activity.version),
        )


def test_approval_without_done_is_422(scenario: Scenario) -> None:
    activity = _store(scenario, situation=calculations.SITUATION_VALIDATED)

    with pytest.raises(InvalidDataError) as refused:
        service.approve_activity(
            scenario.session,
            caller=scenario.caller(scenario.fiscal),
            activity_id=activity.id,
            form=ApprovalForm(),
            version=str(activity.version),
        )

    assert "realizado registrado" in str(refused.value)


def test_approval_before_the_validation_is_422(scenario: Scenario) -> None:
    activity = _store(scenario, day_shift=(5.0,) * 7)

    with pytest.raises(InvalidDataError) as refused:
        service.approve_activity(
            scenario.session,
            caller=scenario.caller(scenario.fiscal),
            activity_id=activity.id,
            form=ApprovalForm(),
            version=str(activity.version),
        )

    assert "validação" in str(refused.value)


def test_approval_by_the_wrong_role_is_403(scenario: Scenario) -> None:
    activity = _store(scenario, situation=calculations.SITUATION_VALIDATED, day_shift=(5.0,) * 7)

    with pytest.raises(AccessDeniedError):
        service.approve_activity(
            scenario.session,
            caller=scenario.caller(scenario.supplier_a),
            activity_id=activity.id,
            form=ApprovalForm(),
            version=str(activity.version),
        )


def test_reopen_demands_a_reason(scenario: Scenario) -> None:
    activity = _store(
        scenario,
        situation=calculations.SITUATION_VALIDATED,
        approval=calculations.APPROVAL_APPROVED,
        day_shift=(5.0,) * 7,
    )

    with pytest.raises(InvalidDataError) as refused:
        service.reopen_activity(
            scenario.session,
            caller=scenario.caller(scenario.fiscal),
            activity_id=activity.id,
            form=ApprovalForm(),
            version=str(activity.version),
        )

    assert "motivo" in refused.value.detail


def test_reopen_of_a_pending_done_is_422(scenario: Scenario) -> None:
    activity = _store(scenario, situation=calculations.SITUATION_VALIDATED, day_shift=(5.0,) * 7)

    with pytest.raises(InvalidDataError):
        service.reopen_activity(
            scenario.session,
            caller=scenario.caller(scenario.fiscal),
            activity_id=activity.id,
            form=ApprovalForm(reason="Erro de digitação."),
            version=str(activity.version),
        )


def test_reopen_returns_to_pending_with_the_reason(scenario: Scenario) -> None:
    activity = _store(
        scenario,
        situation=calculations.SITUATION_VALIDATED,
        approval=calculations.APPROVAL_APPROVED,
        day_shift=(5.0,) * 7,
    )

    service.reopen_activity(
        scenario.session,
        caller=scenario.caller(scenario.fiscal),
        activity_id=activity.id,
        form=ApprovalForm(reason="A quarta saiu trocada com a quinta."),
        version=str(activity.version),
    )

    assert activity.approval == calculations.APPROVAL_PENDING
    assert "Realizado reaberto: A quarta saiu trocada com a quinta." in (
        activity.timenow_comments or ""
    )


def test_reopen_by_the_wrong_role_is_403(scenario: Scenario) -> None:
    activity = _store(
        scenario,
        situation=calculations.SITUATION_VALIDATED,
        approval=calculations.APPROVAL_APPROVED,
        day_shift=(5.0,) * 7,
    )

    with pytest.raises(AccessDeniedError):
        service.reopen_activity(
            scenario.session,
            caller=scenario.caller(scenario.supplier_a),
            activity_id=activity.id,
            form=ApprovalForm(reason="Quero corrigir."),
            version=str(activity.version),
        )


# ── Publicar ────────────────────────────────────────────────────────────


def test_publish_requires_a_validated_activity(scenario: Scenario) -> None:
    activity = _store(scenario)

    with pytest.raises(InvalidDataError):
        service.publish_activity(
            scenario.session,
            caller=scenario.caller(scenario.planner),
            activity_id=activity.id,
            version=str(activity.version),
        )


def test_publish_stamps_the_moment_and_closes_the_edition(scenario: Scenario) -> None:
    activity = _store(
        scenario,
        situation=calculations.SITUATION_VALIDATED,
        approval=calculations.APPROVAL_APPROVED,
        day_shift=(5.0,) * 7,
    )

    service.publish_activity(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        activity_id=activity.id,
        version=str(activity.version),
    )

    assert activity.situation == calculations.SITUATION_PUBLISHED
    assert activity.published_at is not None
    with pytest.raises(AccessDeniedError) as refused:
        service.update_activity(
            scenario.session,
            caller=scenario.caller(scenario.supplier_a),
            activity_id=activity.id,
            form=service.form_of(
                service.get_activity(
                    scenario.session,
                    caller=scenario.caller(scenario.planner),
                    activity_id=activity.id,
                )
            ),
            version=str(activity.version),
        )
    assert "publicada" in str(refused.value)


def test_publish_by_the_wrong_role_is_403(scenario: Scenario) -> None:
    activity = _store(
        scenario,
        situation=calculations.SITUATION_VALIDATED,
        approval=calculations.APPROVAL_APPROVED,
        day_shift=(5.0,) * 7,
    )

    with pytest.raises(AccessDeniedError):
        service.publish_activity(
            scenario.session,
            caller=scenario.caller(scenario.supplier_a),
            activity_id=activity.id,
            version=str(activity.version),
        )


def test_publish_week_publishes_only_the_validated_ones(scenario: Scenario) -> None:
    _store(scenario, unique_id="D-1", situation=calculations.SITUATION_DRAFT)
    first = _store(scenario, unique_id="V-1", situation=calculations.SITUATION_VALIDATED, item=2)
    second = _store(
        scenario,
        unique_id="V-2",
        situation=calculations.SITUATION_VALIDATED,
        approval=calculations.APPROVAL_APPROVED,
        item=3,
    )
    published = _store(
        scenario, unique_id="P-1", situation=calculations.SITUATION_PUBLISHED, item=4
    )

    count = service.publish_week(
        scenario.session, caller=scenario.caller(scenario.planner), week=WEEK
    )

    assert count == 2
    assert (first.situation, second.situation) == (
        calculations.SITUATION_PUBLISHED,
        calculations.SITUATION_PUBLISHED,
    )
    assert published.situation == calculations.SITUATION_PUBLISHED


def test_publish_week_is_refused_for_the_wrong_role(scenario: Scenario) -> None:
    with pytest.raises(AccessDeniedError):
        service.publish_week(
            scenario.session, caller=scenario.caller(scenario.supplier_a), week=WEEK
        )


# ── A trilha ────────────────────────────────────────────────────────────


def test_every_transition_leaves_a_trail_line(scenario: Scenario) -> None:
    activity = _store(scenario)
    caller = scenario.caller(scenario.planner)
    before = scenario.session.scalar(
        select(func.count())
        .select_from(AuditEntry)
        .where(
            AuditEntry.entity == Activity.__tablename__,
            AuditEntry.record_id == activity.id,
        )
    )

    service.validate_activity(
        scenario.session,
        caller=caller,
        activity_id=activity.id,
        form=ValidationForm(inspector_id=scenario.fiscal.person_id),
        version=str(activity.version),
    )
    after = scenario.session.scalar(
        select(func.count())
        .select_from(AuditEntry)
        .where(
            AuditEntry.entity == Activity.__tablename__,
            AuditEntry.record_id == activity.id,
        )
    )

    assert after == before + 1
