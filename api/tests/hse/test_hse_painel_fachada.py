"""Fachada do painel HSE (ISSUE-075, D6, D9): as janelas, os indicadores, as ações e a nota sugerida.

O painel do cenário vive na transação do teste, com o relógio em 25/09/2026. O mês padrão é o
último com HHT e o acumulado vai do primeiro mês com HHT até ele; a base e a referência da
pirâmide vêm do parâmetro vigente (e recalculam quando ele muda); as ações de HSE contam pela
origem ``HSE`` ou pelo grupo ``HSE`` do escopo, lidas pela fachada da Central; e a nota sugerida
de uma empresa sai da TRIF dela contra a do projeto, limitada a 2 pela LTI.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core.scope import Scope
from src.modulos.central_acoes import service as central
from src.modulos.central_acoes.calculations import ACTION
from src.modulos.central_acoes.validation import NewAction
from src.modulos.configuracoes import service as configuracoes
from src.modulos.hse import painel_service, service
from tests.apoio_hse import REFERENCIA, Cenario, fechamento_de, horas_de, ocorrencia_de

JULHO = date(2026, 7, 1)
AGOSTO = date(2026, 8, 1)
INICIO_DO_PROJETO = date(2026, 1, 5)


def _escopo(cenario: Cenario, *, portfolio: bool = False) -> Scope:
    return Scope(project_id=None if portfolio else cenario.projeto.id, source="url")


def _painel(
    sessao: Session,
    cenario: Cenario,
    *,
    month: date | None = None,
    pyramid_kind: str | None = None,
    portfolio: bool = False,
) -> painel_service.HsePanel:
    return painel_service.panel(
        sessao,
        user=cenario.gil,
        scope=_escopo(cenario, portfolio=portfolio),
        reference_date=REFERENCIA,
        month=month,
        pyramid_kind=pyramid_kind,
    )


def _hht(sessao: Session, cenario: Cenario, **campos: object) -> None:
    service.save_hours(
        sessao, user=cenario.maria, data=horas_de(cenario, **campos), reference_date=REFERENCIA
    )


def _ocorrencia(sessao: Session, cenario: Cenario, **campos: object) -> None:
    service.save_occurrence(
        sessao,
        user=cenario.maria,
        data=ocorrencia_de(cenario, role="Operador de moinho", **campos),
        reference_date=REFERENCIA,
    )


def _fechamento(sessao: Session, cenario: Cenario, **campos: object) -> None:
    service.save_closing(
        sessao, user=cenario.maria, data=fechamento_de(cenario, **campos), reference_date=REFERENCIA
    )


def _acao_hse(sessao: Session, cenario: Cenario, **campos: object) -> central.ActionRecord:
    base = NewAction(
        project_id=cenario.projeto.id,
        origin="HSE",
        origin_ref="OCR-TESTE-0001",
        subject="Ação corretiva de HSE",
        requester_id=cenario.maria.person_id,
        responsible_id=cenario.gil.person_id,
        planned_date=REFERENCIA,
        kind=ACTION,
        group="Ação corretiva",
    )
    return central.create_action(
        sessao,
        user=cenario.gil,
        new=replace(base, **campos),  # type: ignore[arg-type]
        reference_date=REFERENCIA,
    )


def _salvar_base(sessao: Session, cenario: Cenario, *, base: int) -> None:
    configuracoes.save_parameter_group(
        sessao,
        author_id=cenario.gil.id,
        group="hse",
        values={**configuracoes.INITIAL_PARAMETERS["hse"], "baseTaxa": base},
        effective_from=REFERENCIA,
        justification="Base das taxas trocada para o teste do painel.",
    )


def _salvar_referencia(sessao: Session, cenario: Cenario, *, referencia: str) -> None:
    configuracoes.save_parameter_group(
        sessao,
        author_id=cenario.gil.id,
        group="hse",
        values={**configuracoes.INITIAL_PARAMETERS["hse"], "referenciaPiramide": referencia},
        effective_from=REFERENCIA,
        justification="Referência da pirâmide trocada para o teste do painel.",
    )


# ── Meses e janelas ──────────────────────────────────────────────────────────────────────────


def test_sem_hht_o_painel_e_o_vazio_de_origem(sessao: Session, cenario: Cenario) -> None:
    painel = _painel(sessao, cenario)

    assert painel.is_empty
    assert painel.months == ()
    assert painel.month is None
    assert painel.month_indicators is None
    assert painel.accumulated_indicators is None
    assert painel_service.panel_months(sessao, scope=_escopo(cenario)) == []


def test_o_mes_padrao_e_o_ultimo_com_hht_e_o_acumulado_vai_do_primeiro(
    sessao: Session, cenario: Cenario
) -> None:
    _hht(sessao, cenario, month=JULHO)
    _hht(sessao, cenario, month=AGOSTO)

    painel = _painel(sessao, cenario)

    assert painel.months == (JULHO, AGOSTO)
    assert painel.month == AGOSTO
    assert (painel.window_start, painel.window_end) == (JULHO, AGOSTO)
    assert [point.month for point in painel.evolution] == [JULHO, AGOSTO]
    assert painel.month_options == (
        painel_service.HseMonthOption(value="2026-07", label="Jul"),
        painel_service.HseMonthOption(value="2026-08", label="Ago"),
    )
    assert painel.years == ("2026",)


def test_o_mes_pedido_fora_dos_meses_cai_no_ultimo(sessao: Session, cenario: Cenario) -> None:
    _hht(sessao, cenario, month=JULHO)
    _hht(sessao, cenario, month=AGOSTO)

    assert _painel(sessao, cenario, month=date(2026, 1, 1)).month == AGOSTO
    assert _painel(sessao, cenario, month=JULHO).month == JULHO


def test_resolve_month_respeita_o_ano_e_o_mes_pedido() -> None:
    months = [date(2025, 12, 1), date(2026, 1, 1), date(2026, 7, 1), date(2026, 8, 1)]

    assert painel_service.resolve_month(months, year=None, requested=None) == date(2026, 8, 1)
    assert painel_service.resolve_month(months, year=None, requested=JULHO) == JULHO
    assert painel_service.resolve_month(months, year="2025", requested=JULHO) == date(2025, 12, 1)
    assert painel_service.resolve_month(months, year="2024", requested=None) == date(2026, 8, 1)
    assert painel_service.resolve_month([], year="2026", requested=None) is None


# ── Indicadores ──────────────────────────────────────────────────────────────────────────────


def test_os_indicadores_do_mes_e_do_acumulado(sessao: Session, cenario: Cenario) -> None:
    _hht(sessao, cenario, month=JULHO, hours=Decimal("100000"))
    _hht(sessao, cenario, month=AGOSTO, hours=Decimal("100000"))
    _ocorrencia(sessao, cenario, kind="Trabalho restrito", happened_on=JULHO)
    _ocorrencia(sessao, cenario, kind="Quase acidente", happened_on=AGOSTO)
    _fechamento(sessao, cenario, month=JULHO, deviations=10, observations=30)
    _fechamento(sessao, cenario, month=AGOSTO, deviations=20, observations=30)

    painel = _painel(sessao, cenario)
    mes = painel.month_indicators
    acumulado = painel.accumulated_indicators
    assert mes is not None and acumulado is not None

    assert (mes.tf, mes.trif, mes.tg) == (Decimal("0.00"), Decimal("0.00"), Decimal("0.0"))
    assert mes.pyramid == (0, 0, 0, 1, 20)
    assert (acumulado.tf, acumulado.trif, acumulado.tg) == (
        Decimal("0.00"),
        Decimal("5.00"),
        Decimal("0.0"),
    )
    assert acumulado.pyramid == (0, 1, 0, 1, 30)
    assert acumulado.registrable == 1
    assert acumulado.observations_per_10k == Decimal("3.0")
    assert acumulado.days_without_leave is None  # sem início de projeto nem LTI

    assert [(point.tf, point.trif) for point in painel.evolution] == [
        (Decimal("0.00"), Decimal("10.00")),
        (Decimal("0.00"), Decimal("0.00")),
    ]


def test_por_area_e_por_empresa_agregam_o_acumulado_sem_os_ambientais(
    sessao: Session, cenario: Cenario
) -> None:
    _hht(sessao, cenario, month=AGOSTO)
    _ocorrencia(sessao, cenario, area="Moagem 210", happened_on=AGOSTO)
    _ocorrencia(sessao, cenario, area="Moagem 210", company_id=cenario.beta.id, happened_on=AGOSTO)
    _ocorrencia(sessao, cenario, area="Canteiro", company_id=cenario.beta.id, happened_on=AGOSTO)
    _ocorrencia(
        sessao,
        cenario,
        kind="Ambiental",
        subtype="Vazamento",
        environmental_severity="Baixa",
        area="Canteiro",
        happened_on=AGOSTO,
    )

    painel = _painel(sessao, cenario)

    assert [(line.name, line.total) for line in painel.by_area] == [
        ("Moagem 210", 2),
        ("Canteiro", 1),
    ]
    assert [(line.name, line.total) for line in painel.by_company] == [
        ("Beta Serviços", 2),
        ("Alfa Montagens", 1),
    ]


def test_dias_sem_afastamento_contam_do_inicio_do_projeto(
    sessao: Session, cenario: Cenario
) -> None:
    cenario.projeto.start_date = INICIO_DO_PROJETO
    sessao.flush()
    _hht(sessao, cenario, month=AGOSTO)

    painel = _painel(sessao, cenario)
    acumulado = painel.accumulated_indicators
    assert acumulado is not None

    assert painel.project_start == INICIO_DO_PROJETO
    assert painel.last_lti is None
    assert acumulado.days_without_leave == 263


def test_a_ultima_lti_reinicia_a_contagem(sessao: Session, cenario: Cenario) -> None:
    cenario.projeto.start_date = INICIO_DO_PROJETO
    sessao.flush()
    _hht(sessao, cenario, month=AGOSTO)
    _ocorrencia(sessao, cenario, kind="Acidente com afastamento", happened_on=date(2026, 9, 10))

    painel = _painel(sessao, cenario)
    acumulado = painel.accumulated_indicators
    assert acumulado is not None

    assert painel.last_lti == date(2026, 9, 10)
    assert acumulado.days_without_leave == 15


def test_acoes_de_hse_no_prazo_pela_origem_ou_pelo_grupo(sessao: Session, cenario: Cenario) -> None:
    _hht(sessao, cenario, month=AGOSTO)
    _acao_hse(sessao, cenario, planned_date=date(2026, 9, 20))
    _acao_hse(
        sessao,
        cenario,
        origin="Ata",
        origin_ref="ATA-1",
        group="HSE",
        planned_date=date(2026, 9, 21),
        completed_on=date(2026, 9, 21),
    )
    _acao_hse(sessao, cenario, planned_date=date(2026, 10, 1))
    _acao_hse(sessao, cenario, origin="Risco", origin_ref="RSK-1", group="Plano de resposta")
    central.create_action(
        sessao,
        user=cenario.gil,
        new=NewAction(
            project_id=cenario.outro.id,
            origin="HSE",
            origin_ref="OCR-TESTE-0002",
            subject="Ação de outro projeto",
            requester_id=cenario.maria.person_id,
            responsible_id=cenario.gil.person_id,
            planned_date=date(2026, 9, 20),
            kind=ACTION,
        ),
        reference_date=REFERENCIA,
    )

    painel = _painel(sessao, cenario)
    acumulado = painel.accumulated_indicators
    assert acumulado is not None

    assert acumulado.actions_on_time_pct == Decimal("50.0")


# ── Parâmetros ───────────────────────────────────────────────────────────────────────────────


def test_a_base_do_parametro_recalcula_as_taxas(sessao: Session, cenario: Cenario) -> None:
    _hht(sessao, cenario, month=AGOSTO, hours=Decimal("100000"))
    _ocorrencia(sessao, cenario, kind="Trabalho restrito", happened_on=AGOSTO)

    antes = _painel(sessao, cenario).accumulated_indicators
    _salvar_base(sessao, cenario, base=200_000)
    depois = _painel(sessao, cenario).accumulated_indicators
    assert antes is not None and depois is not None

    assert (antes.trif, depois.trif) == (Decimal("10.00"), Decimal("2.00"))
    assert _painel(sessao, cenario).base == 200_000


def test_a_referencia_do_parametro_vale_e_a_query_sobrepoe(
    sessao: Session, cenario: Cenario
) -> None:
    _hht(sessao, cenario, month=AGOSTO)

    assert _painel(sessao, cenario).reference.kind == "bird"

    _salvar_referencia(sessao, cenario, referencia="heinrich")
    assert _painel(sessao, cenario).reference.kind == "heinrich"
    assert _painel(sessao, cenario, pyramid_kind="bird").reference.kind == "bird"


def test_o_portfolio_agrega_os_projetos(sessao: Session, cenario: Cenario) -> None:
    _hht(sessao, cenario, month=AGOSTO, hours=Decimal("100000"))
    _hht(sessao, cenario, month=AGOSTO, company_id=cenario.beta.id, hours=Decimal("50000"))
    service.save_hours(
        sessao,
        user=cenario.maria,
        data=horas_de(cenario, project_id=cenario.outro.id, hours=Decimal("50000")),
        reference_date=REFERENCIA,
    )
    _ocorrencia(sessao, cenario, kind="Trabalho restrito", happened_on=AGOSTO)

    painel = _painel(sessao, cenario, portfolio=True)
    acumulado = painel.accumulated_indicators
    assert acumulado is not None

    assert painel.month == AGOSTO
    assert acumulado.hours == Decimal("200000")
    assert acumulado.trif == Decimal("5.00")


# ── Nota HSE sugerida ────────────────────────────────────────────────────────────────────────


def test_a_nota_sugerida_sai_da_trif_da_empresa_contra_a_do_projeto(
    sessao: Session, cenario: Cenario
) -> None:
    _hht(sessao, cenario, month=AGOSTO, hours=Decimal("100000"))
    _hht(sessao, cenario, month=AGOSTO, company_id=cenario.beta.id, hours=Decimal("50000"))
    _ocorrencia(sessao, cenario, kind="Trabalho restrito", happened_on=AGOSTO)

    nota = painel_service.company_note_suggestion(
        sessao, company_id=cenario.alfa.id, scope=_escopo(cenario), reference_date=REFERENCIA
    )

    assert nota is not None
    assert (nota.note, nota.trif, nota.project_trif) == (
        3,
        Decimal("10.00"),
        Decimal("6.67"),
    )
    assert (nota.hours, nota.registrable, nota.lti) == (Decimal("100000.00"), 1, 0)


def test_sem_hht_da_empresa_nao_ha_sugestao(sessao: Session, cenario: Cenario) -> None:
    _hht(sessao, cenario, month=AGOSTO, company_id=cenario.beta.id)

    assert (
        painel_service.company_note_suggestion(
            sessao,
            company_id=cenario.alfa.id,
            scope=_escopo(cenario),
            reference_date=REFERENCIA,
        )
        is None
    )
    assert (
        painel_service.company_note_suggestion(
            sessao,
            company_id=cenario.alfa.id,
            scope=_escopo(cenario, portfolio=True),
            reference_date=REFERENCIA,
        )
        is None
    )


def test_a_lti_da_empresa_limita_a_nota(sessao: Session, cenario: Cenario) -> None:
    _hht(sessao, cenario, month=AGOSTO, hours=Decimal("100000"))
    _ocorrencia(sessao, cenario, kind="Acidente com afastamento", happened_on=AGOSTO)

    nota = painel_service.company_note_suggestion(
        sessao, company_id=cenario.alfa.id, scope=_escopo(cenario), reference_date=REFERENCIA
    )

    assert nota is not None
    assert (nota.note, nota.lti) == (2, 1)


def test_a_base_trocada_muda_a_nota_na_fronteira_do_arredondamento(
    sessao: Session, cenario: Cenario
) -> None:
    # 3,33 contra 1,67 (base de um milhão) → 3,33 ≤ 2 x 1,67 → nota 3; com a base de 200 mil os
    # mesmos fatos leem 0,67 contra 0,33 e 0,67 > 2 x 0,33 → nota 2. A comparação usa as TRIF
    # como a tela as mostra.
    _hht(sessao, cenario, month=AGOSTO, hours=Decimal("600000"))
    _hht(sessao, cenario, month=AGOSTO, company_id=cenario.beta.id, hours=Decimal("600000"))
    _ocorrencia(sessao, cenario, kind="Trabalho restrito", happened_on=AGOSTO)
    _ocorrencia(sessao, cenario, kind="Trabalho restrito", happened_on=AGOSTO)

    antes = painel_service.company_note_suggestion(
        sessao, company_id=cenario.alfa.id, scope=_escopo(cenario), reference_date=REFERENCIA
    )
    _salvar_base(sessao, cenario, base=200_000)
    depois = painel_service.company_note_suggestion(
        sessao, company_id=cenario.alfa.id, scope=_escopo(cenario), reference_date=REFERENCIA
    )

    assert antes is not None and depois is not None
    assert (antes.note, antes.trif, antes.project_trif) == (
        3,
        Decimal("3.33"),
        Decimal("1.67"),
    )
    assert (depois.note, depois.trif, depois.project_trif) == (
        2,
        Decimal("0.67"),
        Decimal("0.33"),
    )
