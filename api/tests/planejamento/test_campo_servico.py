"""Fachada das horas efetivas (ISSUE-047): jornada, amostragem, paralisação e leituras.

O cenário mínimo vem de ``apoio_produtividade``; a data de referência é injetada (25/09/2026).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.errors import AccessDeniedError, InvalidDataError, VersionConflictError
from src.core.scope import Scope
from src.modulos.planejamento import calculations, service, validation
from src.modulos.planejamento.models import (
    FieldDay,
    Stoppage,
    WorkSample,
    WorkSampleReason,
)
from tests.apoio_produtividade import (
    HOJE,
    Cenario,
    form_amostra,
    form_jornada,
    form_paralisacao,
    montar_cenario,
)

D = Decimal


@pytest.fixture
def cenario(sessao: Session) -> Cenario:
    return montar_cenario(sessao)


def _jornada(
    cenario: Cenario, sessao: Session, *, usuario: str = "membro", **overrides: str
) -> FieldDay:
    user = cenario.usuario_gestor if usuario == "gestor" else cenario.usuario_membro
    return service.save_field_day(
        sessao,
        user=user,
        scope=cenario.escopo,
        day_id=None,
        form=form_jornada(cenario, **overrides),
        reference_date=HOJE,
    )


def _amostra(
    cenario: Cenario,
    sessao: Session,
    *,
    parado: Mapping[int, str] | None = None,
    transito: Mapping[int, str] | None = None,
    **overrides: str,
) -> WorkSample:
    return service.save_work_sample(
        sessao,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        sample_id=None,
        form=form_amostra(cenario, parado=parado, transito=transito, **overrides),
        reference_date=HOJE,
    )


def _paralisacao(cenario: Cenario, sessao: Session, **overrides: str) -> Stoppage:
    return service.save_stoppage(
        sessao,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        stoppage_id=None,
        form=form_paralisacao(cenario, **overrides),
        reference_date=HOJE,
    )


def _aba(
    cenario: Cenario,
    sessao: Session,
    *,
    period: str = calculations.PERIOD_WINDOW,
    **filtro: str | int | None,
) -> service.HoursOverview:
    return service.hours_overview(
        sessao,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        hours_filter=service.HoursFilter(period=period, **filtro),
        reference_date=HOJE,
    )


def test_a_jornada_grava_e_a_aba_mostra_a_capacidade(cenario: Cenario, sessao: Session) -> None:
    registro = _jornada(cenario, sessao)

    assert registro.recorded_by_id == cenario.membro.person_id
    assert registro.version == 1
    visao = _aba(cenario, sessao, period=calculations.PERIOD_ALL)
    assert visao.capacity.records == 1
    assert visao.capacity.capacity == D("7.33")
    assert visao.capacity.utilization == D("83.3")
    assert visao.capacity.effective_hh == D("88.0")
    assert visao.field_days[0].foreman == "Sérgio Pinto"


def test_a_segunda_jornada_da_mesma_frente_e_dia_e_recusada(
    cenario: Cenario, sessao: Session
) -> None:
    _jornada(cenario, sessao)

    with pytest.raises(InvalidDataError) as recusa:
        _jornada(cenario, sessao)

    assert "desta frente" in str(recusa.value)
    outra_frente = _jornada(cenario, sessao, encarregado="Wagner Luz")
    assert outra_frente.id != 0
    outra_area = _jornada(cenario, sessao, area="Moagem 210")
    assert outra_area.id != 0


def test_a_jornada_de_outro_dia_e_aceita(cenario: Cenario, sessao: Session) -> None:
    _jornada(cenario, sessao)
    outra = _jornada(cenario, sessao, data="2026-09-24")

    assert outra.day == date(2026, 9, 24)


def test_a_jornada_futura_e_recusada(cenario: Cenario, sessao: Session) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        _jornada(cenario, sessao, data="2026-09-26")

    assert recusa.value.detail == {"data": validation.FUTURE_DATE_MESSAGE}


def test_os_horarios_fora_de_ordem_sao_recusados(cenario: Cenario, sessao: Session) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        _jornada(cenario, sessao, mInicio="07:00")

    assert "ordem" in str(recusa.value)


def test_a_jornada_atualiza_com_a_versao(cenario: Cenario, sessao: Session) -> None:
    registro = _jornada(cenario, sessao)
    atualizado = service.save_field_day(
        sessao,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        day_id=registro.id,
        form=validation.FieldDayForm(
            fields={
                **form_jornada(cenario).fields,
                "efetivo": "20",
                "versao": str(registro.version),
            }
        ),
        reference_date=HOJE,
    )

    assert atualizado.crew == 20
    assert atualizado.version == 2


def test_a_versao_vencida_da_jornada_e_recusada(cenario: Cenario, sessao: Session) -> None:
    registro = _jornada(cenario, sessao)

    with pytest.raises(VersionConflictError):
        service.save_field_day(
            sessao,
            user=cenario.usuario_membro,
            scope=cenario.escopo,
            day_id=registro.id,
            form=validation.FieldDayForm(fields={**form_jornada(cenario).fields, "versao": "99"}),
            reference_date=HOJE,
        )


def test_a_rodada_grava_os_motivos_e_soma_as_paradas(cenario: Cenario, sessao: Session) -> None:
    registro = _amostra(cenario, sessao, parado={0: "6", 2: "5"}, transito={0: "2"})

    assert (registro.working, registro.stopped, registro.transit) == (10, 11, 2)
    motivos = list(
        sessao.scalars(select(WorkSampleReason).where(WorkSampleReason.sample_id == registro.id))
    )
    assert {(motivo.kind, motivo.reason, motivo.quantity) for motivo in motivos} == {
        (calculations.SAMPLE_STOPPED, calculations.STOP_REASONS[0], 6),
        (calculations.SAMPLE_STOPPED, calculations.STOP_REASONS[2], 5),
        (calculations.SAMPLE_TRANSIT, calculations.TRANSIT_REASONS[0], 2),
    }
    visao = _aba(cenario, sessao, period=calculations.PERIOD_ALL)
    assert visao.sample_summary.people == 23
    assert visao.stop_reasons[0].reason == calculations.STOP_REASONS[0]
    assert visao.stop_reasons[0].total == 6
    assert visao.stop_reasons[-1].total == 5


def test_a_rodada_sem_pessoas_observadas_e_recusada(cenario: Cenario, sessao: Session) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        _amostra(cenario, sessao, trabalhando="0")

    assert recusa.value.detail == {validation.FIELD_SAMPLE_WORKING: validation.OBSERVED_MESSAGE}


def test_a_rodada_atualiza_trocando_os_motivos(cenario: Cenario, sessao: Session) -> None:
    registro = _amostra(cenario, sessao, parado={0: "6"})
    service.save_work_sample(
        sessao,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        sample_id=registro.id,
        form=validation.WorkSampleForm(
            fields={
                **form_amostra(cenario).fields,
                "versao": str(registro.version),
            },
            stopped={1: "3"},
            transit={4: "1"},
        ),
        reference_date=HOJE,
    )

    motivos = list(
        sessao.scalars(select(WorkSampleReason).where(WorkSampleReason.sample_id == registro.id))
    )
    assert [(motivo.reason, motivo.quantity) for motivo in motivos] == [
        (calculations.STOP_REASONS[1], 3),
        (calculations.TRANSIT_REASONS[4], 1),
    ]


def test_as_paralisacoes_de_efetivo_e_de_maquina_entram_no_resumo(
    cenario: Cenario, sessao: Session
) -> None:
    _paralisacao(cenario, sessao, responsabilidade="Cliente")
    _paralisacao(
        cenario,
        sessao,
        tipo="Máquina/Equipamento",
        recurso="Guindaste 90 t",
        quantidade="1",
        motivo="Quebra de máquina / equipamento",
        responsabilidade="Terceiros",
    )

    visao = _aba(cenario, sessao, period=calculations.PERIOD_ALL)
    assert visao.stoppage_summary.events == 2
    assert visao.stoppage_summary.crew_hours == D("53.3")
    assert visao.stoppage_summary.machine_hours == D("3.3")
    assert visao.stoppage_summary.client_hours == D("53.3")
    assert visao.stoppage_summary.external_hours == D("53.3")


def test_o_filtro_recorta_por_empresa_area_encarregado_e_periodo(
    cenario: Cenario, sessao: Session
) -> None:
    _jornada(cenario, sessao, data="2026-09-24", area="Flotação 310")
    _jornada(cenario, sessao, data="2026-09-10", area="Moagem 210", encarregado="Mário Castro")

    semana = _aba(cenario, sessao, period=calculations.PERIOD_WEEK)
    assert [registro.area for registro in semana.field_days] == ["Flotação 310"]
    area = _aba(cenario, sessao, period=calculations.PERIOD_ALL, area="Moagem 210")
    assert [registro.area for registro in area.field_days] == ["Moagem 210"]
    encarregado = _aba(cenario, sessao, period=calculations.PERIOD_ALL, foreman="Mário Castro")
    assert len(encarregado.field_days) == 1
    outra_empresa = _aba(cenario, sessao, period=calculations.PERIOD_ALL, company_id=999)
    assert outra_empresa.field_days == ()


def test_o_portfolio_ve_os_registros_dos_projetos(cenario: Cenario, sessao: Session) -> None:
    from tests.identidades import criar_projeto

    outro = criar_projeto(sessao, codigo="TN-PROD-002", nome="Fábrica 2")
    _jornada(cenario, sessao)
    service.save_field_day(
        sessao,
        user=cenario.usuario_membro,
        scope=Scope(project_id=outro.id, source="url"),
        day_id=None,
        form=form_jornada(cenario),
        reference_date=HOJE,
    )

    carteira = service.hours_overview(
        sessao,
        user=cenario.usuario_membro,
        scope=Scope(project_id=None, source="padrao"),
        hours_filter=service.HoursFilter(period=calculations.PERIOD_ALL),
        reference_date=HOJE,
    )

    assert carteira.is_portfolio
    assert len(carteira.field_days) == 2
    assert {registro.project_code for registro in carteira.field_days} == {
        "TN-PROD-001",
        "TN-PROD-002",
    }


def test_o_registro_de_outro_projeto_e_recusado(cenario: Cenario, sessao: Session) -> None:
    from tests.identidades import criar_projeto

    outro = criar_projeto(sessao, codigo="TN-PROD-002", nome="Fábrica 2")
    registro = _jornada(cenario, sessao)

    with pytest.raises(InvalidDataError) as recusa:
        service.save_field_day(
            sessao,
            user=cenario.usuario_membro,
            scope=Scope(project_id=outro.id, source="url"),
            day_id=registro.id,
            form=form_jornada(cenario),
            reference_date=HOJE,
        )

    assert recusa.value.detail == service.FIELD_PROJECT_MESSAGE


def test_o_visualizador_le_mas_nao_grava(cenario: Cenario, sessao: Session) -> None:
    _jornada(cenario, sessao)
    visao = service.hours_overview(
        sessao,
        user=cenario.usuario_visualizador,
        scope=cenario.escopo,
        reference_date=HOJE,
    )

    assert visao.can_write is False
    with pytest.raises(AccessDeniedError):
        service.save_field_day(
            sessao,
            user=cenario.usuario_visualizador,
            scope=cenario.escopo,
            day_id=None,
            form=form_jornada(cenario, data="2026-09-24"),
            reference_date=HOJE,
        )
