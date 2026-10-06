"""Fachada do Relato do período (ISSUE-044, HU-046): período, duplicidade, limites, cópia e perfis."""

from __future__ import annotations

from datetime import date

import pytest

from src.core import calendario
from src.core.errors import AccessDeniedError, InvalidDataError, VersionConflictError
from src.core.scope import Scope
from src.modulos.planejamento import calculations, service, validation
from src.modulos.planejamento.validation import MONTHLY, WEEKLY, PointInput
from tests.planejamento.conftest import Cenario

PONTO = PointInput(
    description="Chuva forte prevista para a semana",
    nature="Ameaça",
    risk="Atraso na concretagem por chuva acima da média",
)


def _hoje() -> date:
    return calendario.today()


def _periodo(kind: str, deslocamento: int = 0) -> str:
    return calendario.add_periods(kind, calendario.period_of(kind, _hoje()), deslocamento) or ""


def _rascunho(
    kind: str = WEEKLY, period: str | None = None, **mudancas: object
) -> service.ReportDraft:
    base: dict[str, object] = {
        "kind": kind,
        "period": period if period is not None else _periodo(kind),
        "activities": ("Concretagem do bloco A",),
        "next_activities": ("Armação do bloco B",),
        "points": (PONTO,),
    }
    base.update(mudancas)
    return service.ReportDraft(**base)  # type: ignore[arg-type]


def _gravar(cenario: Cenario, rascunho: service.ReportDraft, **extra: object) -> service.ReportView:
    return service.save_report(
        cenario.session,
        user=cenario.membro,
        scope=cenario.scope,
        request=service.SaveRequest(draft=rascunho, **extra),  # type: ignore[arg-type]
        reference_date=_hoje(),
    )


def _erros(cenario: Cenario, rascunho: service.ReportDraft) -> dict[str, str]:
    with pytest.raises(InvalidDataError) as erro:
        _gravar(cenario, rascunho)
    assert isinstance(erro.value.detail, dict)
    return dict(erro.value.detail)


# ── Período e duplicidade ──────────────────────────────────────────────────


def test_membro_grava_o_relato_do_periodo_corrente(cenario: Cenario) -> None:
    relato = _gravar(cenario, _rascunho())

    assert (relato.kind, relato.period) == (WEEKLY, _periodo(WEEKLY))
    assert relato.activities == ("Concretagem do bloco A",)
    assert relato.next_activities == ("Armação do bloco B",)
    assert (relato.threats, relato.opportunities) == (1, 0)
    assert relato.updated_by == "membro"


def test_semanal_e_mensal_do_mesmo_periodo_sao_registros_distintos(cenario: Cenario) -> None:
    semanal = _gravar(cenario, _rascunho(WEEKLY))
    mensal = _gravar(cenario, _rascunho(MONTHLY))

    assert semanal.id != mensal.id
    assert len(service.list_reports(cenario.session, user=cenario.membro, scope=cenario.scope)) == 2


def test_periodo_futuro_e_recusado_com_a_mensagem(cenario: Cenario) -> None:
    erros = _erros(cenario, _rascunho(WEEKLY, _periodo(WEEKLY, 1)))

    assert erros[validation.FIELD_PERIOD] == calculations.NOT_STARTED_MESSAGE


def test_periodo_anterior_ao_inicio_do_projeto_e_recusado(cenario: Cenario) -> None:
    erros = _erros(cenario, _rascunho(WEEKLY, _periodo(WEEKLY, -20)))

    assert erros[validation.FIELD_PERIOD] == calculations.BEFORE_PROJECT_MESSAGE


def test_periodo_duplicado_e_recusado_e_manda_editar_o_existente(cenario: Cenario) -> None:
    _gravar(cenario, _rascunho())

    erros = _erros(cenario, _rascunho())

    assert erros[validation.FIELD_PERIOD] == (
        "Já existe relato semanal para este período; edite o registro existente."
    )


def test_tipo_invalido_e_recusado(cenario: Cenario) -> None:
    erros = _erros(cenario, _rascunho("Diário", "2026-09-25"))

    assert validation.FIELD_KIND in erros


def test_no_portfolio_o_projeto_e_exigido_antes_de_gravar(cenario: Cenario) -> None:
    with pytest.raises(InvalidDataError):
        service.save_report(
            cenario.session,
            user=cenario.membro,
            scope=Scope(project_id=None, source="url"),
            request=service.SaveRequest(draft=_rascunho()),
            reference_date=_hoje(),
        )


# ── Limites (422 por campo) ────────────────────────────────────────────────


def test_atividades_exigem_ao_menos_uma_linha(cenario: Cenario) -> None:
    erros = _erros(cenario, _rascunho(activities=("  ", ""), next_activities=()))

    assert erros[validation.FIELD_ACTIVITIES] == validation.ACTIVITY_REQUIRED_MESSAGE
    assert erros[validation.FIELD_NEXT_ACTIVITIES] == validation.ACTIVITY_REQUIRED_MESSAGE


def test_atividades_aceitam_20_linhas_e_300_caracteres_e_recusam_mais(cenario: Cenario) -> None:
    ok = _gravar(cenario, _rascunho(activities=tuple("a" * 300 for _ in range(20))))
    assert len(ok.activities) == 20

    outro = _rascunho(WEEKLY, _periodo(WEEKLY, -1))
    erros = _erros(
        cenario, _rascunho(outro.kind, outro.period, activities=tuple("a" for _ in range(21)))
    )
    assert "20 linhas" in erros[validation.FIELD_ACTIVITIES]

    erros = _erros(cenario, _rascunho(WEEKLY, outro.period, next_activities=("a" * 301,)))
    assert erros[validation.FIELD_NEXT_ACTIVITIES] == validation.LINE_TOO_LONG_MESSAGE


def test_pontos_de_atencao_ate_12_com_descricao_e_risco_de_10_a_400(cenario: Cenario) -> None:
    doze = tuple(PONTO for _ in range(12))
    assert len(_gravar(cenario, _rascunho(points=doze)).points) == 12

    periodo = _periodo(WEEKLY, -1)
    erros = _erros(cenario, _rascunho(WEEKLY, periodo, points=(*doze, PONTO)))
    assert erros[validation.FIELD_POINTS] == validation.TOO_MANY_POINTS_MESSAGE

    curto = PointInput(description="curto", nature="Ameaça", risk="Risco com texto suficiente")
    erros = _erros(cenario, _rascunho(WEEKLY, periodo, points=(curto,)))
    assert (
        erros[validation.point_field(0, "descricao")] == validation.POINT_DESCRIPTION_SHORT_MESSAGE
    )

    nove = PointInput(description="a" * 9, nature="Ameaça", risk="r" * 10)
    dez = PointInput(description="a" * 10, nature="Oportunidade", risk="r" * 400)
    assert validation.point_field(0, "descricao") in _erros(
        cenario, _rascunho(WEEKLY, periodo, points=(nove,))
    )
    assert len(_gravar(cenario, _rascunho(WEEKLY, periodo, points=(dez,))).points) == 1

    longo = PointInput(description="a" * 401, nature="Ameaça", risk="r" * 10)
    erros = _erros(cenario, _rascunho(WEEKLY, _periodo(WEEKLY, -2), points=(longo,)))
    assert erros[validation.point_field(0, "descricao")] == validation.POINT_TOO_LONG_MESSAGE


def test_natureza_do_ponto_e_ameaca_ou_oportunidade(cenario: Cenario) -> None:
    ponto = PointInput(description="a" * 10, nature="Neutro", risk="r" * 10)

    erros = _erros(cenario, _rascunho(points=(ponto,)))

    assert erros[validation.point_field(0, "natureza")] == validation.POINT_NATURE_MESSAGE


def test_linha_de_ponto_em_branco_nao_conta(cenario: Cenario) -> None:
    relato = _gravar(cenario, _rascunho(points=(PointInput(), PONTO)))

    assert len(relato.points) == 1


def test_relato_sem_pontos_de_atencao_e_valido(cenario: Cenario) -> None:
    assert _gravar(cenario, _rascunho(points=())).points == ()


# ── Edição e exclusão ──────────────────────────────────────────────────────


def test_edicao_mantem_tipo_e_periodo_e_troca_o_conteudo(cenario: Cenario) -> None:
    criado = _gravar(cenario, _rascunho())

    editado = _gravar(
        cenario,
        _rascunho(MONTHLY, _periodo(MONTHLY, -1), activities=("Nova atividade",)),
        report_id=criado.id,
        version=str(criado.version),
    )

    assert (editado.kind, editado.period) == (criado.kind, criado.period)
    assert editado.activities == ("Nova atividade",)
    assert editado.version > criado.version


def test_edicao_com_versao_vencida_e_recusada(cenario: Cenario) -> None:
    criado = _gravar(cenario, _rascunho())
    _gravar(cenario, _rascunho(), report_id=criado.id, version=str(criado.version))

    with pytest.raises(VersionConflictError):
        _gravar(cenario, _rascunho(), report_id=criado.id, version=str(criado.version))


def test_gestor_exclui_e_o_periodo_volta_a_ficar_livre(cenario: Cenario) -> None:
    criado = _gravar(cenario, _rascunho())

    service.delete_report(
        cenario.session,
        user=cenario.gestor,
        scope=cenario.scope,
        report_id=criado.id,
        version=str(criado.version),
    )

    assert service.list_reports(cenario.session, user=cenario.membro, scope=cenario.scope) == []
    assert _gravar(cenario, _rascunho()).id != criado.id


def test_membro_nao_exclui_e_visualizador_nao_grava(cenario: Cenario) -> None:
    criado = _gravar(cenario, _rascunho())

    with pytest.raises(AccessDeniedError):
        service.delete_report(
            cenario.session,
            user=cenario.membro,
            scope=cenario.scope,
            report_id=criado.id,
            version=None,
        )
    with pytest.raises(AccessDeniedError):
        service.save_report(
            cenario.session,
            user=cenario.visualizador,
            scope=cenario.scope,
            request=service.SaveRequest(draft=_rascunho(WEEKLY, _periodo(WEEKLY, -1))),
            reference_date=_hoje(),
        )
    assert (
        len(service.list_reports(cenario.session, user=cenario.visualizador, scope=cenario.scope))
        == 1
    )


def test_excluir_relato_inexistente_e_recusado(cenario: Cenario) -> None:
    with pytest.raises(InvalidDataError):
        service.delete_report(
            cenario.session,
            user=cenario.gestor,
            scope=cenario.scope,
            report_id=999999,
            version=None,
        )


# ── Copiar do período anterior ─────────────────────────────────────────────


def test_copiar_traz_o_ultimo_relato_anterior_do_mesmo_tipo(cenario: Cenario) -> None:
    antigo = _periodo(WEEKLY, -3)
    recente = _periodo(WEEKLY, -1)
    _gravar(cenario, _rascunho(WEEKLY, antigo, next_activities=("Do antigo",)))
    _gravar(
        cenario,
        _rascunho(
            WEEKLY, recente, next_activities=("Do recente 1", "Do recente 2"), points=(PONTO,)
        ),
    )
    _gravar(cenario, _rascunho(MONTHLY, _periodo(MONTHLY, 0), next_activities=("Do mensal",)))

    anterior = service.previous_report(
        cenario.session,
        user=cenario.membro,
        scope=cenario.scope,
        request=service.SaveRequest(
            draft=service.ReportDraft(kind=WEEKLY, period=_periodo(WEEKLY))
        ),
    )

    assert anterior is not None
    assert anterior.period == recente
    assert anterior.next_activities == ("Do recente 1", "Do recente 2")
    assert anterior.points == (PONTO,)


def test_copiar_sem_relato_anterior_devolve_nada(cenario: Cenario) -> None:
    _gravar(cenario, _rascunho())

    anterior = service.previous_report(
        cenario.session,
        user=cenario.membro,
        scope=cenario.scope,
        request=service.SaveRequest(
            draft=service.ReportDraft(kind=WEEKLY, period=_periodo(WEEKLY))
        ),
    )

    assert anterior is None


def test_copiar_exige_membro(cenario: Cenario) -> None:
    with pytest.raises(AccessDeniedError):
        service.previous_report(
            cenario.session,
            user=cenario.visualizador,
            scope=cenario.scope,
            request=service.SaveRequest(
                draft=service.ReportDraft(kind=WEEKLY, period=_periodo(WEEKLY))
            ),
        )


# ── Leitura, filtro e indicadores ──────────────────────────────────────────


def test_filtro_por_tipo_e_busca(cenario: Cenario) -> None:
    _gravar(cenario, _rascunho(WEEKLY, activities=("Montagem do guindaste",)))
    _gravar(cenario, _rascunho(MONTHLY, activities=("Fechamento da medição",)))
    listar = lambda filtro: service.list_reports(  # noqa: E731
        cenario.session, user=cenario.visualizador, scope=cenario.scope, report_filter=filtro
    )

    assert [r.kind for r in listar(service.ReportFilter(kind=MONTHLY))] == [MONTHLY]
    assert [r.kind for r in listar(service.ReportFilter(search="guindaste"))] == [WEEKLY]
    assert listar(service.ReportFilter(search="inexistente")) == []
    assert len(listar(service.ReportFilter())) == 2


def test_indicadores_contam_relatos_e_pendencias(cenario: Cenario) -> None:
    hoje = _hoje()
    anterior = _periodo(WEEKLY, -1)
    antes = _periodo(WEEKLY, -2)
    _gravar(cenario, _rascunho(WEEKLY, antes, points=(PONTO,)))
    _gravar(cenario, _rascunho(WEEKLY, anterior, points=(PONTO, PONTO, PONTO)))

    resumo = service.report_summary(
        cenario.session, user=cenario.visualizador, scope=cenario.scope, reference_date=hoje
    )

    assert (resumo.total, resumo.weekly_total, resumo.monthly_total) == (2, 2, 0)
    assert resumo.previous_week.period == anterior
    assert (resumo.previous_week.registered, resumo.previous_week.expected) == (1, 1)
    assert resumo.previous_week.is_complete
    assert not resumo.previous_month.is_complete
    assert resumo.last_weekly is not None and resumo.last_weekly.period == anterior
    assert resumo.reference_points == 1
