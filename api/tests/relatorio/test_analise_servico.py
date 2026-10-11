"""Fachada da Análise do período (ISSUE-081): período, texto, comentários, pendência, cópia e perfis."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from src.core import calendario
from src.core.errors import AccessDeniedError, InvalidDataError, VersionConflictError
from src.core.scope import PROJECT_REQUIRED_MESSAGE, Scope
from src.modulos.planejamento.models import EapItem, EapMeasurement
from src.modulos.planejamento.validation import MONTHLY, WEEKLY
from src.modulos.relatorio import service, validation
from src.modulos.relatorio.models import Analysis
from tests.relatorio.conftest import Cenario, Demonstracao

TEXTO = "Panorama, desempenho dos períodos anteriores, causas e tendência. " * 4

TEXTO_ANTERIOR = "Texto do período anterior com panorama e tendência. " * 6

COMENTARIO = "Causa, efeito e ação do desvio no período."


def _hoje() -> date:
    return calendario.today()


def _periodo(kind: str, deslocamento: int = 0) -> str:
    return calendario.add_periods(kind, calendario.period_of(kind, _hoje()), deslocamento) or ""


def _gravar(
    cenario: Cenario,
    *,
    module: str = "planejamento",
    kind: str = WEEKLY,
    period: str | None = None,
    text: str = TEXTO,
    comments: dict[str, str] | None = None,
    analysis_id: int | None = None,
    version: str | None = None,
    user: object | None = None,
) -> service.AnalysisView:
    return service.save_analysis(
        cenario.session,
        user=user or cenario.membro,  # type: ignore[arg-type]
        scope=cenario.scope,
        request=service.AnalysisRequest(
            module=module,
            kind=kind,
            period=period if period is not None else _periodo(kind),
            analysis_id=analysis_id,
            version=version,
            text=text,
            comments=comments or {},
        ),
        reference_date=_hoje(),
    )


def _erros(cenario: Cenario, **mudancas: object) -> dict[str, str]:
    with pytest.raises(InvalidDataError) as erro:
        _gravar(cenario, **mudancas)  # type: ignore[arg-type]
    assert isinstance(erro.value.detail, dict)
    return dict(erro.value.detail)


# ── Período, texto e duplicidade (projeto sem desvios) ─────────────────────


def test_membro_grava_a_analise_do_periodo_corrente(cenario: Cenario) -> None:
    salvo = _gravar(cenario)

    assert salvo.record is not None
    assert salvo.record.text == TEXTO.strip()
    assert salvo.record.updated_by == "membro"
    assert (salvo.module, salvo.kind, salvo.period) == ("planejamento", WEEKLY, _periodo(WEEKLY))
    assert salvo.deviations == ()
    assert salvo.pending == 0


def test_semanal_e_mensal_do_mesmo_periodo_sao_registros_distintos(cenario: Cenario) -> None:
    semanal = _gravar(cenario, kind=WEEKLY)
    mensal = _gravar(cenario, kind=MONTHLY, period=_periodo(MONTHLY))

    assert semanal.record is not None and mensal.record is not None
    assert semanal.record.id != mensal.record.id
    assert (
        service.analysis_record(
            cenario.session,
            project_id=cenario.project.id,
            module="planejamento",
            kind=MONTHLY,
            period=_periodo(MONTHLY),
        )
        is not None
    )


def test_periodo_futuro_e_anterior_ao_inicio_sao_recusados(cenario: Cenario) -> None:
    futuro = _erros(cenario, period=_periodo(WEEKLY, 1))
    anterior = _erros(cenario, period=_periodo(WEEKLY, -20))

    assert futuro[validation.FIELD_PERIOD] == (
        "O período ainda não começou; registre a partir do período corrente."
    )
    assert anterior[validation.FIELD_PERIOD] == "O período é anterior ao início do projeto."


def test_texto_fora_dos_limites_e_recusado(cenario: Cenario) -> None:
    curto = _erros(cenario, text="curto")
    longo = _erros(cenario, text="a" * 2501)

    assert curto[validation.FIELD_TEXT] == validation.TEXT_SHORT_MESSAGE
    assert longo[validation.FIELD_TEXT] == validation.TEXT_LONG_MESSAGE


def test_analise_duplicada_e_recusada_e_manda_editar_a_existente(cenario: Cenario) -> None:
    _gravar(cenario)

    erros = _erros(cenario)

    assert erros[validation.FIELD_PERIOD] == (
        "Já existe análise semanal para este período; edite o registro existente."
    )


def test_modulo_invalido_e_recusado(cenario: Cenario) -> None:
    erros = _erros(cenario, module="inicio")

    assert erros[validation.FIELD_MODULE] == validation.MODULE_MESSAGE


def test_no_portfolio_o_projeto_e_exigido_antes_de_gravar(cenario: Cenario) -> None:
    with pytest.raises(InvalidDataError) as erro:
        service.save_analysis(
            cenario.session,
            user=cenario.membro,
            scope=Scope(project_id=None, source="url"),
            request=service.AnalysisRequest(
                module="planejamento", kind=WEEKLY, period=_periodo(WEEKLY)
            ),
            reference_date=_hoje(),
        )

    assert erro.value.detail == PROJECT_REQUIRED_MESSAGE


# ── Edição, versão e exclusão ──────────────────────────────────────────────


def test_edicao_mantem_modulo_tipo_e_periodo_e_troca_o_texto(cenario: Cenario) -> None:
    criado = _gravar(cenario)
    assert criado.record is not None

    editado = _gravar(
        cenario,
        module="suprimentos",
        kind=MONTHLY,
        period=_periodo(MONTHLY, -1),
        text=TEXTO_ANTERIOR,
        analysis_id=criado.record.id,
        version=str(criado.record.version),
    )

    assert (editado.module, editado.kind, editado.period) == (
        "planejamento",
        WEEKLY,
        _periodo(WEEKLY),
    )
    assert editado.record is not None
    assert editado.record.text == TEXTO_ANTERIOR.strip()
    assert editado.record.version > criado.record.version


def test_edicao_com_versao_vencida_e_recusada(cenario: Cenario) -> None:
    criado = _gravar(cenario)
    assert criado.record is not None
    _gravar(cenario, analysis_id=criado.record.id, version=str(criado.record.version))

    with pytest.raises(VersionConflictError):
        _gravar(cenario, analysis_id=criado.record.id, version=str(criado.record.version))


def test_gestor_exclui_e_o_periodo_volta_a_ficar_livre(cenario: Cenario) -> None:
    criado = _gravar(cenario)
    assert criado.record is not None

    excluido = service.delete_analysis(
        cenario.session,
        user=cenario.gestor,
        scope=cenario.scope,
        analysis_id=criado.record.id,
        version=str(criado.record.version),
    )

    assert excluido.period == _periodo(WEEKLY)
    assert _gravar(cenario).record is not None


def test_membro_nao_exclui_e_visualizador_nao_grava(cenario: Cenario) -> None:
    criado = _gravar(cenario)
    assert criado.record is not None

    with pytest.raises(AccessDeniedError):
        service.delete_analysis(
            cenario.session,
            user=cenario.membro,
            scope=cenario.scope,
            analysis_id=criado.record.id,
            version=None,
        )
    with pytest.raises(AccessDeniedError):
        _gravar(cenario, period=_periodo(WEEKLY, -1), user=cenario.visualizador)


# ── Copiar do período imediatamente anterior ───────────────────────────────


def test_copiar_traz_o_texto_do_periodo_imediatamente_anterior(cenario: Cenario) -> None:
    anterior = _periodo(WEEKLY, -1)
    _gravar(cenario, period=anterior, text=TEXTO_ANTERIOR)

    visao = service.analysis_view(
        cenario.session,
        user=cenario.membro,
        scope=cenario.scope,
        module="planejamento",
        kind=WEEKLY,
        period=_periodo(WEEKLY),
        reference_date=_hoje(),
    )

    assert visao.previous is not None
    assert visao.previous.period == anterior
    assert visao.previous.text == TEXTO_ANTERIOR.strip()


def test_sem_analise_do_periodo_anterior_nao_ha_o_que_copiar(cenario: Cenario) -> None:
    visao = service.analysis_view(
        cenario.session,
        user=cenario.membro,
        scope=cenario.scope,
        module="planejamento",
        kind=WEEKLY,
        period=_periodo(WEEKLY),
        reference_date=_hoje(),
    )

    assert visao.previous is None


# ── Desvios e comentários (demonstração, projeto 1) ────────────────────────


def _escopo(demonstracao: Demonstracao) -> Scope:
    return Scope(project_id=demonstracao.project_id, source="url")


def _visao(
    demonstracao: Demonstracao, *, module: str, kind: str, period: str
) -> service.AnalysisView:
    return service.analysis_view(
        demonstracao.session,
        user=demonstracao.admin,
        scope=_escopo(demonstracao),
        module=module,
        kind=kind,
        period=period,
        reference_date=demonstracao.reference_date,
    )


def _salvar(
    demonstracao: Demonstracao,
    *,
    module: str,
    kind: str,
    period: str,
    comments: dict[str, str],
    analysis_id: int | None = None,
    version: str | None = None,
) -> service.AnalysisView:
    return service.save_analysis(
        demonstracao.session,
        user=demonstracao.admin,
        scope=_escopo(demonstracao),
        request=service.AnalysisRequest(
            module=module,
            kind=kind,
            period=period,
            analysis_id=analysis_id,
            version=version,
            text=TEXTO,
            comments=comments,
        ),
        reference_date=demonstracao.reference_date,
    )


def _registro_da_carga(
    demonstracao: Demonstracao, *, module: str, kind: str, period: str
) -> Analysis:
    """A análise que a carga de demonstração gravou para o projeto 1 no período."""
    record = service.analysis_record(
        demonstracao.session,
        project_id=demonstracao.project_id,
        module=module,
        kind=kind,
        period=period,
    )
    assert record is not None
    return record


def test_comentario_curto_e_recusado_quando_obrigatorio(demonstracao: Demonstracao) -> None:
    visao = _visao(demonstracao, module="planejamento", kind=WEEKLY, period="2026-S38")
    assert visao.deviations, "o periodo do mock tem desvios"
    record = _registro_da_carga(demonstracao, module="planejamento", kind=WEEKLY, period="2026-S38")

    with pytest.raises(InvalidDataError) as erro:
        _salvar(
            demonstracao,
            module="planejamento",
            kind=WEEKLY,
            period="2026-S38",
            comments={deviation.key: "curto" for deviation in visao.deviations},
            analysis_id=record.id,
            version=str(record.version),
        )

    assert validation.COMMENT_SHORT_MESSAGE in dict(erro.value.detail).values()


def test_desvio_novo_surgido_dos_dados_aparece_pendente(demonstracao: Demonstracao) -> None:
    session = demonstracao.session
    visao = _visao(demonstracao, module="planejamento", kind=WEEKLY, period="2026-S38")
    record = _registro_da_carga(demonstracao, module="planejamento", kind=WEEKLY, period="2026-S38")
    comentarios = {deviation.key: COMENTARIO for deviation in visao.deviations}
    salvo = _salvar(
        demonstracao,
        module="planejamento",
        kind=WEEKLY,
        period="2026-S38",
        comments=comentarios,
        analysis_id=record.id,
        version=str(record.version),
    )
    assert salvo.pending == 0

    item = session.scalars(
        select(EapItem)
        .where(EapItem.project_id == demonstracao.project_id, EapItem.level == 3)
        .order_by(EapItem.weight.desc())
    ).first()
    assert item is not None
    ultima = session.scalars(
        select(EapMeasurement)
        .where(EapMeasurement.item_id == item.id)
        .order_by(EapMeasurement.measured_on.desc())
    ).first()
    assert ultima is not None and ultima.to_pct > Decimal(5)
    session.add(
        EapMeasurement(
            item_id=item.id,
            author_id=demonstracao.admin.person_id,
            measured_on=date(2026, 9, 18),
            from_pct=ultima.to_pct,
            to_pct=ultima.to_pct - Decimal(5),
        )
    )
    session.flush()

    depois = _visao(demonstracao, module="planejamento", kind=WEEKLY, period="2026-S38")

    assert "avanco_periodo" in {deviation.key for deviation in depois.deviations}
    assert depois.pending == 1

    with pytest.raises(InvalidDataError) as erro:
        _salvar(
            demonstracao,
            module="planejamento",
            kind=WEEKLY,
            period="2026-S38",
            comments={
                deviation.key: COMENTARIO
                for deviation in depois.deviations
                if deviation.key != "avanco_periodo"
            },
            analysis_id=salvo.record.id if salvo.record else None,
            version=str(salvo.record.version) if salvo.record else None,
        )

    assert validation.COMMENT_SHORT_MESSAGE in dict(erro.value.detail).values()


def test_marcos_atrasados_so_entram_dentro_do_periodo(demonstracao: Demonstracao) -> None:
    semanal = _visao(demonstracao, module="suprimentos", kind=WEEKLY, period="2026-S38")
    mensal = _visao(demonstracao, module="suprimentos", kind=MONTHLY, period="2026-08")

    marcos_semana = next(
        deviation for deviation in semanal.deviations if deviation.key == "marcos_atrasados"
    )
    assert "PED-2026-0002" in marcos_semana.description
    assert "PED-2026-0001" not in marcos_semana.description

    marcos_mes = next(
        deviation for deviation in mensal.deviations if deviation.key == "marcos_atrasados"
    )
    for numero in ("PED-2026-0001", "PED-2026-0003", "PED-2026-0006", "PED-2026-0010"):
        assert numero in marcos_mes.description
