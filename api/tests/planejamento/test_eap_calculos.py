"""Cálculos puros da EAP (ISSUE-036, D6): avanço pelo critério, desvio, vencimento e árvore.

Cada critério de medição tem o seu teste e cada faixa tem o caso de fronteira. A data de
referência entra como argumento; nada aqui lê o relógio. Os números da árvore são feitos à mão
(veja o comentário de ``tests/apoio_eap.py``).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.modulos.planejamento import eap_calculations as calc
from src.modulos.planejamento.eap_calculations import (
    EapLine,
    PackageEntries,
    PortfolioEap,
    ProjectIdentity,
    Rules,
    StageLine,
    TreeRow,
)

D = Decimal
REFERENCE = date(2026, 9, 25)
BANDS = (D(2), D(5))
RULES = Rules(bands=BANDS, reference_date=REFERENCE)
MODEL = (
    StageLine("Pedido emitido", D(10)),
    StageLine("Documentos aprovados", D(15)),
    StageLine("Fabricação", D(45)),
    StageLine("Inspeção e FAT", D(10)),
    StageLine("Entrega na obra", D(20)),
)


# ── Arredondamento do protótipo ──────────────────────────────────────────


@pytest.mark.parametrize(
    ("value", "places", "expected"),
    [
        ("2.5", 0, "3"),
        ("-2.5", 0, "-2"),
        ("1.005", 2, "1.01"),
        ("73.3333", 2, "73.33"),
        ("-6.66", 1, "-6.7"),
        ("-3.33", 1, "-3.3"),
        ("0.004", 2, "0.00"),
    ],
)
def test_arredondamento_repete_o_math_round_do_prototipo(
    value: str, places: int, expected: str
) -> None:
    assert calc.round_places(D(value), places) == D(expected)


def test_codigo_ordena_como_numero_e_nao_como_texto() -> None:
    codes = ["1.10", "1.2", "1", "1.2.1"]

    assert sorted(codes, key=calc.code_key) == ["1", "1.2", "1.2.1", "1.10"]


# ── Avanço do pacote: um teste por critério ──────────────────────────────


def _progress(
    criterion: str | None,
    percent: str | None,
    *,
    kind: str = calc.WORK,
    quantity: str | None = None,
    stages: tuple[StageLine, ...] = (),
) -> Decimal:
    return calc.progress_from_measurement(
        kind=kind,
        criterion=criterion,
        quantity=D(quantity) if quantity else None,
        stages=stages,
        measured_percent=D(percent) if percent is not None else None,
    )


def test_etapas_preenche_em_sequencia_e_o_real_e_a_soma_ponderada() -> None:
    state = calc.package_state(
        kind=calc.WORK,
        criterion=calc.STAGES,
        quantity=None,
        stages=MODEL,
        measured_percent=D(80),
    )

    assert [stage.percent for stage in state.entries.stages] == [D(100), D(100), D(100), D(100), 0]
    assert state.real == D("80.00")


def test_etapas_com_etapa_parcial_converte_o_percentual_na_etapa() -> None:
    state = calc.package_state(
        kind=calc.WORK,
        criterion=calc.STAGES,
        quantity=None,
        stages=MODEL,
        measured_percent=D(30),
    )

    assert [stage.percent for stage in state.entries.stages][:3] == [D(100), D(100), D("11.11")]
    assert state.real == D("30.00")


def test_etapas_com_todas_concluidas_e_100_e_sem_medicao_e_zero() -> None:
    assert _progress(calc.STAGES, "100", stages=MODEL) == D(100)
    assert _progress(calc.STAGES, None, stages=MODEL) == 0


def test_etapas_calcula_o_real_das_entradas_do_protototipo_sem_sequencia() -> None:
    entries = PackageEntries(
        stages=(
            StageLine("A", D(40), D(100)),
            StageLine("B", D(30), D(50)),
            StageLine("C", D(30), D(0)),
        )
    )

    real = calc.package_progress(
        kind=calc.WORK, criterion=calc.STAGES, quantity=None, entries=entries
    )

    assert real == D("55.00")


def test_unidades_e_o_executado_sobre_a_quantidade_da_linha_de_base() -> None:
    assert _progress(calc.UNITS, "90", quantity="1400") == D("90.00")
    assert _progress(calc.UNITS, "7.5", quantity="160") == D("7.50")


def test_unidades_nao_passa_de_100_nem_divide_por_quantidade_zero() -> None:
    entries = PackageEntries(executed=D(150))

    over = calc.package_progress(
        kind=calc.WORK, criterion=calc.UNITS, quantity=D(100), entries=entries
    )
    empty = calc.package_progress(
        kind=calc.WORK, criterion=calc.UNITS, quantity=D(0), entries=entries
    )

    assert over == D(100)
    assert empty == 0


def test_unidades_converte_o_percentual_em_quantidade_executada() -> None:
    state = calc.package_state(
        kind=calc.WORK,
        criterion=calc.UNITS,
        quantity=D(1400),
        stages=(),
        measured_percent=D(90),
    )

    assert state.entries.executed == D("1260.00")


def test_marco_0_100_so_vale_100_quando_concluido() -> None:
    assert _progress(calc.MILESTONE_0_100, "100") == D(100)
    assert _progress(calc.MILESTONE_0_100, "99.99") == 0
    assert _progress(calc.MILESTONE_0_100, "50") == 0
    assert _progress(calc.MILESTONE_0_100, None) == 0


def test_marco_50_50_tem_os_degraus_0_50_e_100() -> None:
    assert _progress(calc.MILESTONE_50_50, "0") == 0
    assert _progress(calc.MILESTONE_50_50, "49.99") == 0
    assert _progress(calc.MILESTONE_50_50, "50") == D(50)
    assert _progress(calc.MILESTONE_50_50, "100") == D(100)


def test_marco_50_50_guarda_o_estado_do_marco() -> None:
    def state_of(percent: str) -> str | None:
        return calc.package_state(
            kind=calc.WORK,
            criterion=calc.MILESTONE_50_50,
            quantity=None,
            stages=(),
            measured_percent=D(percent),
        ).entries.state

    assert state_of("0") == calc.NOT_STARTED
    assert state_of("50") == calc.STARTED
    assert state_of("100") == calc.DONE


def test_percentual_estimado_e_o_proprio_percentual_limitado_a_100() -> None:
    assert _progress(calc.ESTIMATED, "4.5") == D("4.50")
    entries = PackageEntries(estimated_percent=D(130))
    assert (
        calc.package_progress(
            kind=calc.WORK, criterion=calc.ESTIMATED, quantity=None, entries=entries
        )
        == 100
    )


def test_pacote_de_planejamento_nao_mede_avanco() -> None:
    assert _progress(calc.UNITS, "80", kind=calc.PLANNING, quantity="10") == 0
    assert _progress(None, "80", kind=calc.PLANNING) == 0


def test_criterio_desconhecido_ou_vazio_nao_gera_avanco() -> None:
    assert _progress(None, "50") == 0
    assert _progress("Outro", "50") == 0


# ── Desvio e faixas ──────────────────────────────────────────────────────


def test_desvio_e_real_menos_previsto_com_uma_casa() -> None:
    assert calc.deviation_pp(D("61.8"), D("65.7")) == D("-3.9")
    assert calc.deviation_pp(D("66.67"), D("73.33")) == D("-6.7")
    assert calc.deviation_pp(D("34.14"), D("33.15")) == D("1.0")


@pytest.mark.parametrize(
    ("deviation", "expected"),
    [
        ("1.0", calc.OK),
        ("0", calc.OK),
        ("-2.0", calc.OK),
        ("-2.1", calc.WARNING),
        ("-5.0", calc.WARNING),
        ("-5.1", calc.DANGER),
        ("-8", calc.DANGER),
    ],
)
def test_faixa_do_desvio_usa_os_limites_dos_parametros(deviation: str, expected: str) -> None:
    assert calc.deviation_band(D(deviation), BANDS) == expected


def test_faixa_segue_os_parametros_quando_mudam() -> None:
    assert calc.deviation_band(D("-3"), (D(3), D(6))) == calc.OK
    assert calc.deviation_band(D("-3.1"), (D(3), D(6))) == calc.WARNING


def test_faixa_sem_desvio_e_vazia() -> None:
    assert calc.deviation_band(None, BANDS) is None


# ── Término vencido ──────────────────────────────────────────────────────


def _overdue(end: date | None, real: str, kind: str = calc.WORK) -> bool:
    return calc.package_is_overdue(kind=kind, end_date=end, real=D(real), reference_date=REFERENCE)


def test_vencido_e_termino_antes_da_referencia_com_real_abaixo_de_100() -> None:
    assert _overdue(date(2026, 9, 24), "99.99")
    assert _overdue(date(2026, 9, 15), "80")


def test_o_proprio_dia_do_termino_nao_vence() -> None:
    assert not _overdue(REFERENCE, "10")


def test_pacote_concluido_nao_vence_e_planejamento_tambem_nao() -> None:
    assert not _overdue(date(2026, 1, 1), "100")
    assert not _overdue(date(2026, 1, 1), "0", kind=calc.PLANNING)
    assert not _overdue(None, "0")


# ── Regra dos 100% e média ponderada ─────────────────────────────────────


def test_regra_dos_100_fecha_so_com_100_exatos() -> None:
    assert calc.weights_close_at_100(D("100.00"))
    assert not calc.weights_close_at_100(D("99.99"))
    assert not calc.weights_close_at_100(D("100.01"))


def test_media_ponderada_pelo_peso_e_zero_sem_peso() -> None:
    assert calc.weighted_average([(D(60), D(50)), (D(30), D(100))]) == D("66.67")
    assert calc.weighted_average([(D(0), D(50))]) == 0
    assert calc.weighted_average([]) == 0


# ── Árvore do projeto ────────────────────────────────────────────────────


def _lines() -> list[EapLine]:
    return [
        EapLine(1, None, "1", "Engenharia", 1),
        EapLine(2, 1, "1.1", "Projeto básico", 2),
        EapLine(
            3,
            2,
            "1.1.1",
            "Fundações",
            3,
            kind=calc.WORK,
            criterion=calc.UNITS,
            unit="m³",
            quantity=D(100),
            executed=D(50),
            weight=D(50),
            planned=D(60),
            real=D(50),
            start_date=date(2026, 1, 5),
            end_date=date(2026, 9, 1),
        ),
        EapLine(
            4,
            2,
            "1.1.2",
            "Licença",
            3,
            kind=calc.WORK,
            criterion=calc.MILESTONE_0_100,
            weight=D(30),
            planned=D(100),
            real=D(100),
            start_date=date(2026, 1, 5),
            end_date=date(2026, 8, 1),
        ),
        EapLine(
            5,
            2,
            "1.1.3",
            "Projeto de processo",
            3,
            kind=calc.WORK,
            criterion=calc.STAGES,
            weight=D(10),
            planned=D(20),
            real=D(40),
            start_date=date(2026, 3, 2),
            end_date=date(2026, 12, 31),
        ),
        EapLine(6, None, "2", "Montagem", 1),
        EapLine(7, 6, "2.1", "Montagem futura", 2),
        EapLine(
            8,
            7,
            "2.1.1",
            "Comissionamento",
            3,
            kind=calc.PLANNING,
            weight=D(10),
            planned=D(0),
            start_date=date(2026, 11, 1),
            end_date=date(2027, 3, 31),
        ),
    ]


IDENTITY = ProjectIdentity(
    project_id=1, label="TN-1 · Fábrica", description="Fábrica", manager="Gil"
)


def _rows(lines: list[EapLine] | None = None) -> dict[str, TreeRow]:
    tree = calc.build_project_tree(lines or _lines(), identity=IDENTITY, rules=RULES)
    return {row.code: row for row in tree}


def test_a_linha_zero_traz_o_projeto_com_peso_100_e_o_avanco_consolidado() -> None:
    root = _rows()["0"]

    assert root.is_root
    assert root.description == "Fábrica"
    assert root.responsible == "Gil"
    assert (root.weight, root.planned, root.real) == (D(100), D("62.00"), D("59.00"))
    assert root.deviation == D("-3.0")
    assert root.band == calc.WARNING
    assert (root.start_date, root.end_date) == (date(2026, 1, 5), date(2027, 3, 31))


def test_o_peso_de_cada_nivel_e_a_soma_dos_filhos() -> None:
    rows = _rows()

    assert rows["1.1"].weight == D(90)
    assert rows["1"].weight == D(90)
    assert rows["2.1"].weight == D(10)
    assert rows["0"].weight == rows["1"].weight + rows["2"].weight == D(100)


def test_previsto_e_real_das_areas_sao_media_ponderada_pelo_peso() -> None:
    rows = _rows()

    assert (rows["1.1"].planned, rows["1.1"].real) == (D("68.89"), D("65.56"))
    assert (rows["1"].planned, rows["1"].real) == (D("68.89"), D("65.56"))
    assert rows["1.1"].deviation == D("-3.3")
    assert rows["1.1"].band == calc.WARNING
    assert (rows["2"].planned, rows["2"].real) == (0, 0)
    assert rows["2"].band == calc.OK


def test_peso_no_nivel_acima_e_a_parte_do_pacote_na_subarea() -> None:
    rows = _rows()

    assert rows["1.1.1"].weight_in_parent == D("55.6")
    assert rows["1.1.2"].weight_in_parent == D("33.3")
    assert rows["1.1.3"].weight_in_parent == D("11.1")
    assert rows["1.1"].weight_in_parent == D("100.0")
    assert rows["1"].weight_in_parent is None


def test_pacote_traz_datas_criterio_e_vencimento() -> None:
    rows = _rows()

    foundations = rows["1.1.1"]
    assert foundations.is_work
    assert foundations.criterion == calc.UNITS
    assert foundations.is_overdue
    assert not rows["1.1.2"].is_overdue
    assert not rows["1.1.3"].is_overdue
    assert (rows["1.1"].start_date, rows["1.1"].end_date) == (date(2026, 1, 5), date(2026, 12, 31))


def test_pacote_de_planejamento_conta_a_parte_e_nao_tem_criterio() -> None:
    rows = _rows()

    planning = rows["2.1.1"]
    assert not planning.is_work
    assert planning.criterion is None
    assert planning.real == 0
    assert (rows["0"].work_count, rows["0"].planning_count, rows["0"].overdue_count) == (3, 1, 1)


def test_a_arvore_vem_na_ordem_dos_codigos_com_a_raiz_primeiro() -> None:
    tree = calc.build_project_tree(_lines(), identity=IDENTITY, rules=RULES)

    assert [row.code for row in tree] == [
        "0", "1", "1.1", "1.1.1", "1.1.2", "1.1.3", "2", "2.1", "2.1.1",
    ]  # fmt: skip


def test_projeto_sem_peso_nao_divide_por_zero() -> None:
    rows = _rows([EapLine(1, None, "1", "Área vazia", 1)])

    assert rows["0"].weight == 0
    assert (rows["0"].planned, rows["0"].real) == (0, 0)


# ── Indicadores ──────────────────────────────────────────────────────────


def test_indicadores_do_projeto() -> None:
    tree = calc.build_project_tree(_lines(), identity=IDENTITY, rules=RULES)

    summary = calc.summarize(tree, portfolio=False)

    assert (summary.planned, summary.real, summary.deviation) == (D("62.00"), D("59.00"), D("-3.0"))
    assert summary.band == calc.WARNING
    assert (summary.work_count, summary.planning_count) == (3, 1)
    assert summary.planning_weight == D(10)
    assert (summary.area_count, summary.subarea_count) == (2, 2)
    assert summary.overdue_count == 1
    assert summary.behind_count == 1  # 1.1.1: real 50 contra previsto 60, desvio -10,0
    assert summary.weight_total == D(100)


def test_desvio_no_limite_da_faixa_nao_conta_como_atrasado() -> None:
    lines = _lines()
    lines[2] = EapLine(
        3,
        2,
        "1.1.1",
        "Fundações",
        3,
        kind=calc.WORK,
        criterion=calc.UNITS,
        weight=D(50),
        planned=D(55),
        real=D(50),
        end_date=date(2027, 1, 1),
    )

    summary = calc.summarize(
        calc.build_project_tree(lines, identity=IDENTITY, rules=RULES), portfolio=False
    )

    assert summary.behind_count == 0  # -5,0 p.p. ainda é a faixa de atenção
    assert summary.overdue_count == 0


# ── Filtros ──────────────────────────────────────────────────────────────


def _codes(rows: tuple[TreeRow, ...]) -> list[str]:
    return [row.code for row in rows]


def _full() -> tuple[TreeRow, ...]:
    return calc.build_project_tree(_lines(), identity=IDENTITY, rules=RULES)


def test_filtro_sem_nada_mostra_tudo_ate_o_nivel() -> None:
    assert len(calc.filter_tree(_full())) == 9
    assert _codes(calc.filter_tree(_full(), max_level=2)) == ["0", "1", "1.1", "2", "2.1"]
    assert _codes(calc.filter_tree(_full(), max_level=1)) == ["0", "1", "2"]


def test_busca_ignora_acento_e_caixa_e_mantem_os_ancestrais() -> None:
    rows = calc.filter_tree(_full(), search="FUNDACOES")

    assert _codes(rows) == ["0", "1", "1.1", "1.1.1"]


def test_busca_pelo_codigo() -> None:
    assert _codes(calc.filter_tree(_full(), search="2.1.1")) == ["0", "2", "2.1", "2.1.1"]


def test_filtro_de_criterio_mantem_so_os_pacotes_do_criterio() -> None:
    rows = calc.filter_tree(_full(), leaf_filters={"criterio": calc.MILESTONE_0_100})

    assert _codes(rows) == ["0", "1", "1.1", "1.1.2"]


def test_filtro_de_criterio_planejamento_traz_os_sem_medicao() -> None:
    rows = calc.filter_tree(_full(), leaf_filters={"criterio": calc.FILTER_PLANNING})

    assert _codes(rows) == ["0", "2", "2.1", "2.1.1"]


def test_filtro_de_situacao_vencido_atrasado_e_planejamento() -> None:
    overdue = calc.filter_tree(_full(), leaf_filters={"situacao": calc.SITUATION_OVERDUE})
    planning = calc.filter_tree(_full(), leaf_filters={"situacao": calc.SITUATION_PLANNING})
    behind = calc.filter_tree(_full(), leaf_filters={"situacao": calc.SITUATION_BEHIND})

    assert _codes(overdue) == ["0", "1", "1.1", "1.1.1"]
    assert _codes(planning) == ["0", "2", "2.1", "2.1.1"]
    assert _codes(behind) == ["0", "1", "1.1", "1.1.1"]


def test_filtro_sem_resultado_deixa_so_a_raiz() -> None:
    assert _codes(calc.filter_tree(_full(), search="zzz")) == ["0"]


def test_pais_que_recebem_a_seta_de_recolher() -> None:
    parents = calc.parent_codes(_full())

    assert parents == {"0", "1", "1.1", "2", "2.1"}
    assert calc.parent_codes(()) == frozenset()


# ── Carteira ─────────────────────────────────────────────────────────────


def _second_lines() -> list[EapLine]:
    return [
        EapLine(1, None, "1", "Obra civil", 1),
        EapLine(2, 1, "1.1", "Fundações", 2),
        EapLine(
            3,
            2,
            "1.1.1",
            "Estacas",
            3,
            kind=calc.WORK,
            criterion=calc.ESTIMATED,
            weight=D(100),
            planned=D(100),
            real=D(100),
            start_date=date(2026, 2, 1),
            end_date=date(2026, 8, 1),
        ),
    ]


def _portfolio() -> dict[str, TreeRow]:
    second = ProjectIdentity(project_id=2, label="TN-2 · Caldeira", description="Caldeira")
    projects = [
        PortfolioEap(number=1, identity=IDENTITY, rows=_full(), weight=D(60)),
        PortfolioEap(
            number=2,
            identity=second,
            rows=calc.build_project_tree(_second_lines(), identity=second, rules=RULES),
            weight=D(40),
        ),
    ]
    tree = calc.build_portfolio_tree(
        projects, root_description="Portfólio de projetos", rules=RULES
    )
    return {row.code: row for row in tree}


def test_carteira_tem_linha_zero_projeto_e_pacote_principal() -> None:
    rows = _portfolio()

    assert list(rows) == ["0", "1", "1.1", "1.2", "2", "2.1"]
    assert [rows[code].level for code in rows] == [0, 1, 2, 2, 1, 2]


def test_peso_na_carteira_e_o_peso_do_projeto_vezes_o_da_area() -> None:
    rows = _portfolio()

    assert rows["1"].weight == D(60)
    assert rows["2"].weight == D(40)
    assert rows["1.1"].weight == D("54.00")
    assert rows["1.2"].weight == D("6.00")
    assert rows["2.1"].weight == D("40.00")
    assert rows["1.1"].weight_in_parent == D(90)
    assert rows["0"].weight == D(100)


def test_avanco_da_carteira_e_ponderado_pelo_peso_dos_projetos() -> None:
    rows = _portfolio()

    assert (rows["0"].planned, rows["0"].real) == (D("77.20"), D("75.40"))
    assert rows["0"].deviation == D("-1.8")
    assert rows["0"].band == calc.OK
    assert (rows["1"].planned, rows["1"].real) == (D("62.00"), D("59.00"))


def test_carteira_soma_os_pacotes_e_os_vencidos_dos_projetos() -> None:
    rows = _portfolio()
    tree = tuple(rows.values())

    summary = calc.summarize(tree, portfolio=True)

    assert summary.project_count == 2
    assert summary.work_count == 4
    assert summary.planning_count == 1
    assert summary.area_count == 3
    assert summary.overdue_count == 1
    assert summary.weight_total == D(100)


def test_projeto_sem_eap_nao_aparece_mas_o_numero_dos_outros_nao_muda() -> None:
    empty = PortfolioEap(number=1, identity=IDENTITY, rows=(), weight=D(50))
    second = ProjectIdentity(project_id=2, label="TN-2", description="Caldeira")
    filled = PortfolioEap(
        number=2,
        identity=second,
        rows=calc.build_project_tree(_second_lines(), identity=second, rules=RULES),
        weight=D(50),
    )

    tree = calc.build_portfolio_tree([empty, filled], root_description="P", rules=RULES)

    assert [row.code for row in tree] == ["0", "2", "2.1"]


def test_carteira_vazia_tem_so_a_raiz_com_pesos_zerados() -> None:
    tree = calc.build_portfolio_tree([], root_description="P", rules=RULES)

    assert [row.code for row in tree] == ["0"]
    assert tree[0].weight == 0


# ── Revisão ──────────────────────────────────────────────────────────────


def test_pacotes_da_revisao_sao_os_que_tem_peso_congelado() -> None:
    assert calc.revision_package_count([D(50), D(30), D(0), D("0.8")]) == 3
    assert calc.revision_package_count([]) == 0
