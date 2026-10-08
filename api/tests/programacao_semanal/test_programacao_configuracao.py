"""Configuration of the Weekly Scheduling: parameters and windows, one per project (D10).

The rules of ISSUE-054: the Planner of the project or the Admin edit, effective at once
and with before and after in the single trail; a project without a row reads the app's
defaults, and ``ensure_settings`` creates it with them for the creation of a project
(ISSUE-078); the Portfólio is read-only and the supplier sees only its own window.
"""

from __future__ import annotations

from datetime import time

import pytest
from sqlalchemy import select

from src.core.errors import AccessDeniedError, InvalidDataError, VersionConflictError
from src.core.models import AuditEntry
from src.core.rbac import Bond, GeneralProfile, ScheduleRole, User
from src.modulos.configuracoes.models import Person
from src.modulos.programacao_semanal import calculations, repository, service
from src.modulos.programacao_semanal import window as window_rules
from src.modulos.programacao_semanal.models import Activity, ScheduleSettings, ScheduleWindow
from src.modulos.programacao_semanal.service import NewActivity
from src.modulos.programacao_semanal.validation import (
    DoneForm,
    ScheduleSettingsForm,
    WindowForm,
)
from tests.cenario_programacao import FRIDAY_MORNING, WEEK, Scenario
from tests.identidades import criar_colaborador

SETTINGS_ENTITY = ScheduleSettings.__tablename__
WINDOW_ENTITY = ScheduleWindow.__tablename__
EXTRA_CLOSES = "2026-07-26T18:00"
EXTRA_OPENS = "2026-07-25T08:00"


def _planner_of_another_project(scenario: Scenario, email: str = "ps-fora@example.invalid") -> User:
    """A person whose Planner role belongs to another project, to prove the role's reach."""
    collaborator = criar_colaborador(
        scenario.session, email=email, papeis=[(scenario.other_project_id, "Planejador")]
    )
    person = scenario.session.get(Person, collaborator.person_id)
    assert person is not None
    return User(
        id=collaborator.id,
        person_id=person.id,
        name=person.name,
        email=person.email,
        general_profile=GeneralProfile(collaborator.general_profile),
        bond=Bond(collaborator.bond),
        company_id=collaborator.company_id,
        schedule_roles=frozenset({(scenario.other_project_id, ScheduleRole.PLANNER)}),
    )


def _trail(scenario: Scenario, entity: str) -> list[AuditEntry]:
    statement = select(AuditEntry).where(AuditEntry.entity == entity).order_by(AuditEntry.id)
    return list(scenario.session.scalars(statement))


def _validated_activity(scenario: Scenario, *, unique_id: str = "CFG-1") -> Activity:
    """A validated activity of the week, ready for the done work (the deviation rule needs one)."""
    return service.store_activity(
        scenario.session,
        author_id=scenario.author_id,
        new=NewActivity(
            project_id=scenario.project_id,
            company_id=scenario.company_a,
            week=WEEK,
            unique_id=unique_id,
            item=1,
            description="Serviço da configuração",
            planned_headline=100.0,
            author_person_id=scenario.planner.person_id,
            at=scenario.caller(scenario.planner).now,
            location_id=scenario.location_id,
            unit_id=scenario.unit_id,
            foreman_id=scenario.foreman_a,
            inspector_id=scenario.fiscal.person_id,
            planned_days=(100.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            situation=calculations.SITUATION_VALIDATED,
        ),
    )


# ── A função de padrões ────────────────────────────────────────────────


def test_ensure_settings_creates_the_row_with_the_apps_defaults(scenario: Scenario) -> None:
    row = service.ensure_settings(
        scenario.session, author_id=scenario.author_id, project_id=scenario.other_project_id
    )

    assert (row.adherence_target, row.ppc_target, row.deviation_limit) == (60.0, 75.0, 15.0)
    assert row.requires_deviation_note is True
    assert row.reference_week is None
    entries = _trail(scenario, SETTINGS_ENTITY)
    assert [entry.action for entry in entries] == ["criado"]
    assert entries[0].project_id == scenario.other_project_id
    assert entries[0].after is not None and entries[0].after["meta_aderencia"] == 60.0

    again = service.ensure_settings(
        scenario.session, author_id=scenario.author_id, project_id=scenario.other_project_id
    )
    assert again.id == row.id
    assert len(_trail(scenario, SETTINGS_ENTITY)) == 1


def test_a_project_without_a_row_reads_the_defaults(scenario: Scenario) -> None:
    configuration = service.configuration_of(
        scenario.session, caller=scenario.caller(scenario.planner, project=False)
    )
    assert configuration.is_portfolio is True

    configuration = service.configuration_of(
        scenario.session, caller=scenario.caller(scenario.planner)
    )
    assert (configuration.has_row, configuration.can_edit) == (False, True)
    parameters = configuration.parameters
    assert (parameters.adherence_target, parameters.ppc_target, parameters.deviation_limit) == (
        60.0,
        75.0,
        15.0,
    )
    assert {window.company for window in configuration.windows} == {"Empresa A", "Empresa B"}
    assert all(not window.is_open for window in configuration.windows)


# ── Permissão por papel no projeto ─────────────────────────────────────


def test_the_planner_of_the_project_and_the_admin_edit_the_parameters(scenario: Scenario) -> None:
    version: str | None = None
    for user in (scenario.planner, scenario.admin):
        row = service.save_parameters(
            scenario.session,
            caller=scenario.caller(user),
            form=ScheduleSettingsForm(adherence_target=70.0),
            version=version,
        )
        assert row.adherence_target == 70.0
        version = str(row.version)


def test_the_other_profiles_do_not_edit_the_parameters(scenario: Scenario) -> None:
    for user in (scenario.fiscal, scenario.foreman, scenario.supplier_a, scenario.viewer):
        with pytest.raises(AccessDeniedError):
            service.save_parameters(
                scenario.session,
                caller=scenario.caller(user),
                form=ScheduleSettingsForm(adherence_target=70.0),
                version=None,
            )

    assert repository.settings_of(scenario.session, scenario.project_id) is None


def test_the_planner_of_another_project_does_not_edit_here(scenario: Scenario) -> None:
    outsider = _planner_of_another_project(scenario)

    with pytest.raises(AccessDeniedError):
        service.save_parameters(
            scenario.session,
            caller=scenario.caller(outsider),
            form=ScheduleSettingsForm(adherence_target=70.0),
            version=None,
        )

    assert repository.settings_of(scenario.session, scenario.project_id) is None


def test_the_supplier_only_sees_its_own_window(scenario: Scenario) -> None:
    service.save_parameters(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        form=ScheduleSettingsForm(reference_week=WEEK),
        version=None,
    )

    configuration = service.configuration_of(
        scenario.session, caller=scenario.caller(scenario.supplier_a, now=FRIDAY_MORNING)
    )

    assert configuration.can_edit is False
    assert [window.company for window in configuration.windows] == ["Empresa A"]
    assert configuration.windows[0].is_open is True


# ── Efeito imediato e trilha ───────────────────────────────────────────


def test_the_saved_parameters_are_effective_on_the_next_read(scenario: Scenario) -> None:
    service.save_parameters(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        form=ScheduleSettingsForm(
            adherence_target=80.0, ppc_target=90.0, reference_week=WEEK, deviation_limit=5.0
        ),
        version=None,
    )

    parameters = service.parameters_of(scenario.session, scenario.project_id)
    assert (parameters.adherence_target, parameters.ppc_target) == (80.0, 90.0)
    assert (parameters.reference_week, parameters.deviation_limit) == (WEEK, 5.0)
    assert service.default_week(scenario.session, caller=scenario.caller(scenario.planner)) == WEEK


def test_the_new_deviation_limit_binds_the_next_report(scenario: Scenario) -> None:
    activity = _validated_activity(scenario)
    done = DoneForm(day_shift=(90.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0))
    service.save_parameters(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        form=ScheduleSettingsForm(deviation_limit=5.0),
        version=None,
    )

    with pytest.raises(InvalidDataError) as refused:
        service.report_done(
            scenario.session,
            caller=scenario.caller(scenario.supplier_a),
            activity_id=activity.id,
            form=done,
            version=str(activity.version),
        )
    assert "observacoes" in refused.value.detail


def test_the_trail_of_the_parameters_keeps_before_and_after(scenario: Scenario) -> None:
    first = service.save_parameters(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        form=ScheduleSettingsForm(adherence_target=70.0),
        version=None,
    )
    service.save_parameters(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        form=ScheduleSettingsForm(adherence_target=80.0),
        version=str(first.version),
    )

    entries = _trail(scenario, SETTINGS_ENTITY)
    assert [entry.action for entry in entries] == ["criado", "alterado"]
    assert entries[1].before is not None and entries[1].before["meta_aderencia"] == 70.0
    assert entries[1].after is not None and entries[1].after["meta_aderencia"] == 80.0
    assert entries[1].project_id == scenario.project_id


def test_a_stale_settings_version_is_a_conflict(scenario: Scenario) -> None:
    service.save_parameters(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        form=ScheduleSettingsForm(adherence_target=70.0),
        version=None,
    )

    with pytest.raises(VersionConflictError):
        service.save_parameters(
            scenario.session,
            caller=scenario.caller(scenario.planner),
            form=ScheduleSettingsForm(adherence_target=90.0),
            version="0",
        )


def test_the_parameters_out_of_range_are_refused(scenario: Scenario) -> None:
    with pytest.raises(InvalidDataError) as refused:
        service.save_parameters(
            scenario.session,
            caller=scenario.caller(scenario.planner),
            form=ScheduleSettingsForm(adherence_target=150.0, reference_week="semana"),
            version=None,
        )

    assert set(refused.value.detail) == {"meta_aderencia", "semana_referencia"}
    assert repository.settings_of(scenario.session, scenario.project_id) is None


# ── As janelas ─────────────────────────────────────────────────────────


def test_a_window_is_created_with_its_rules_and_the_trail(scenario: Scenario) -> None:
    row = service.save_window(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        form=WindowForm(
            company_id=scenario.company_b,
            weekday="5",
            opens="08:00",
            closes="15:00",
            weeks=(WEEK,),
        ),
        version=None,
    )

    window = repository.window_of_row(scenario.session, row)
    assert window.days == (window_rules.WindowDay(weekday=5, opens=time(8, 0), closes=time(15, 0)),)
    assert window.weeks == frozenset({WEEK})
    entries = _trail(scenario, WINDOW_ENTITY)
    assert [entry.action for entry in entries] == ["criado", "criado"]
    assert entries[1].before is None
    assert entries[1].after is not None
    assert entries[1].after["empresa_id"] == scenario.company_b
    assert entries[1].after["dias"] == [{"dia_semana": 5, "abre": "08:00", "fecha": "15:00"}]


def test_a_window_edited_replaces_the_rules_and_demands_the_version(scenario: Scenario) -> None:
    current = repository.window_row_of(
        scenario.session, project_id=scenario.project_id, company_id=scenario.company_a
    )
    assert current is not None
    monday = WindowForm(
        company_id=scenario.company_a, weekday="1", opens="09:00", closes="17:00", weeks=(WEEK,)
    )

    service.save_window(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        form=monday,
        version=str(current.version),
    )

    window = repository.window_of_row(scenario.session, current)
    assert window.days == (window_rules.WindowDay(weekday=1, opens=time(9, 0), closes=time(17, 0)),)

    with pytest.raises(VersionConflictError):
        service.save_window(
            scenario.session,
            caller=scenario.caller(scenario.planner),
            form=monday,
            version="0",
        )


def test_the_trail_of_a_window_keeps_before_and_after_with_the_rules(scenario: Scenario) -> None:
    current = repository.window_row_of(
        scenario.session, project_id=scenario.project_id, company_id=scenario.company_a
    )
    assert current is not None
    service.save_window(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        form=WindowForm(
            company_id=scenario.company_a, weekday="5", opens="00:01", closes="23:59", weeks=(WEEK,)
        ),
        version=str(current.version),
    )

    entries = [entry for entry in _trail(scenario, WINDOW_ENTITY) if entry.action == "alterado"]
    assert len(entries) == 1
    before, after = entries[0].before, entries[0].after
    assert before is not None and after is not None
    assert before["versao"] == current.version - 1
    assert before["dias"][0]["abre"] == "08:00"
    assert after["dias"][0]["abre"] == "00:01"
    assert before["semanas"] == [WEEK]


def test_the_extra_release_is_added_replaced_and_removed(scenario: Scenario) -> None:
    current = repository.window_row_of(
        scenario.session, project_id=scenario.project_id, company_id=scenario.company_a
    )
    assert current is not None
    service.save_window(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        form=WindowForm(
            company_id=scenario.company_a,
            weekday="5",
            opens="08:00",
            closes="15:00",
            weeks=(WEEK,),
            extra_week=WEEK,
            extra_opens=EXTRA_OPENS,
            extra_closes=EXTRA_CLOSES,
        ),
        version=str(current.version),
    )
    window = repository.window_of_row(scenario.session, current)
    assert len(window.extras) == 1
    assert window.extras[0].week == WEEK
    assert (window.extras[0].opens.hour, window.extras[0].closes.hour) == (8, 18)

    service.save_window(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        form=WindowForm(
            company_id=scenario.company_a,
            weekday="5",
            opens="08:00",
            closes="15:00",
            weeks=(WEEK,),
            remove_extra=WEEK,
        ),
        version=str(current.version),
    )
    assert repository.window_of_row(scenario.session, current).extras == ()


def test_a_saved_window_opens_the_supplier(scenario: Scenario) -> None:
    service.save_window(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        form=WindowForm(
            company_id=scenario.company_b,
            weekday="5",
            opens="08:00",
            closes="15:00",
            weeks=(WEEK,),
        ),
        version=None,
    )

    status = service.window_status(
        scenario.session, caller=scenario.caller(scenario.supplier_b), week=WEEK
    )
    assert status.is_open is True
    assert status.can_create is True


def test_a_window_of_an_unregistered_company_is_refused(scenario: Scenario) -> None:
    with pytest.raises(InvalidDataError) as refused:
        service.save_window(
            scenario.session,
            caller=scenario.caller(scenario.planner),
            form=WindowForm(company_id=999_999, weekday="1", opens="08:00", closes="15:00"),
            version=None,
        )

    assert "empresa" in refused.value.detail
    assert (
        repository.window_row_of(
            scenario.session, project_id=scenario.project_id, company_id=999_999
        )
        is None
    )


def test_the_window_form_refuses_bad_times_and_weeks(scenario: Scenario) -> None:
    with pytest.raises(InvalidDataError) as refused:
        service.save_window(
            scenario.session,
            caller=scenario.caller(scenario.planner),
            form=WindowForm(
                company_id=scenario.company_b,
                weekday="5",
                opens="25:00",
                closes="",
                weeks=("S.99/2026",),
                extra_week=WEEK,
            ),
            version=None,
        )

    assert set(refused.value.detail) == {"abre", "fecha", "semanas", "extra_abre", "extra_fecha"}


def test_nobody_but_the_planner_or_the_admin_saves_a_window(scenario: Scenario) -> None:
    form = WindowForm(company_id=scenario.company_b, weekday="5", opens="08:00", closes="15:00")

    for user in (scenario.fiscal, scenario.supplier_a, scenario.viewer):
        with pytest.raises(AccessDeniedError):
            service.save_window(
                scenario.session, caller=scenario.caller(user), form=form, version=None
            )

    service.save_window(
        scenario.session, caller=scenario.caller(scenario.admin), form=form, version=None
    )
    assert (
        repository.window_row_of(
            scenario.session, project_id=scenario.project_id, company_id=scenario.company_b
        )
        is not None
    )


# ── O Portfólio ────────────────────────────────────────────────────────


def test_the_portfolio_is_read_only_and_asks_for_a_project(scenario: Scenario) -> None:
    configuration = service.configuration_of(
        scenario.session, caller=scenario.caller(scenario.planner, project=False)
    )
    assert (configuration.is_portfolio, configuration.can_edit) == (True, False)
    assert configuration.windows == []

    with pytest.raises(InvalidDataError):
        service.save_parameters(
            scenario.session,
            caller=scenario.caller(scenario.planner, project=False),
            form=ScheduleSettingsForm(),
            version=None,
        )
    with pytest.raises(InvalidDataError):
        service.save_window(
            scenario.session,
            caller=scenario.caller(scenario.planner, project=False),
            form=WindowForm(company_id=scenario.company_a),
            version=None,
        )


def test_the_window_opens_with_the_reference_week(scenario: Scenario) -> None:
    service.save_parameters(
        scenario.session,
        caller=scenario.caller(scenario.planner),
        form=ScheduleSettingsForm(reference_week=WEEK),
        version=None,
    )

    configuration = service.configuration_of(
        scenario.session, caller=scenario.caller(scenario.planner, now=FRIDAY_MORNING)
    )

    windows = {window.company: window for window in configuration.windows}
    assert windows["Empresa A"].is_open is True
    assert windows["Empresa A"].days == (
        window_rules.WindowDay(weekday=5, opens=time(8, 0), closes=time(15, 0)),
    )
    assert windows["Empresa A"].weeks == (WEEK,)
    assert windows["Empresa B"].is_open is False
    assert "sem janela cadastrada" in windows["Empresa B"].reason


def test_the_configuration_refuses_an_unreadable_reference_week(scenario: Scenario) -> None:
    with pytest.raises(InvalidDataError) as refused:
        service.save_parameters(
            scenario.session,
            caller=scenario.caller(scenario.planner),
            form=ScheduleSettingsForm(reference_week="S.99/2026"),
            version=None,
        )

    assert "semana_referencia" in refused.value.detail
