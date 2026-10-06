"""Cálculos puros da EAC (ISSUE-029, D6): valor orçado, totais da árvore, filtro e ponderação.

Toda fórmula tem o caso de fronteira: meio centavo, pacote sem item, código ``1.10``,
soma dos pesos sempre 100,00 pelo maior resto, empate, tudo zero e projeto sem nota.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from src.modulos.financeiro.calculations import (
    ItemLine,
    PortfolioProject,
    WeightCriterion,
    WeightInput,
    budgeted_cents,
    build_portfolio_tree,
    build_project_tree,
    code_key,
    filter_tree,
    filtered_total_cents,
    item_totals,
    largest_remainder,
    parent_codes,
    portfolio_weights,
    project_total_cents,
)

D = Decimal


def _package(identifier: int, code: str, description: str = "Pacote") -> ItemLine:
    return ItemLine(id=identifier, parent_id=None, code=code, description=description, level=1)


def _subpackage(identifier: int, parent: int, code: str) -> ItemLine:
    return ItemLine(id=identifier, parent_id=parent, code=code, description="Subpacote", level=2)


def _item(identifier: int, parent: int, code: str, quantity: str, price: int) -> ItemLine:
    return ItemLine(
        id=identifier,
        parent_id=parent,
        code=code,
        description="Item",
        level=3,
        cost_type="Serviço",
        unit="un",
        quantity=D(quantity),
        unit_price_cents=price,
        capex=True,
        responsible="Ana",
    )


@pytest.fixture
def tree_items() -> list[ItemLine]:
    """Two packages: 1 has two subpackages with two items and one item; 2 has no item."""
    return [
        _package(1, "1", "Engenharia"),
        _subpackage(2, 1, "1.1"),
        replace(_item(3, 2, "1.1.1", "10", 1_000), description="Projeto básico"),
        replace(_item(4, 2, "1.1.2", "2.5", 400), cost_type="Material"),
        _subpackage(5, 1, "1.2"),
        replace(_item(6, 5, "1.2.1", "1", 5_000), description="Detalhamento"),
        _package(7, "2", "Suprimentos"),
    ]


# ── Valor orçado ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("quantity", "price", "expected"),
    [
        ("10", 1_000, 10_000),
        ("2.5", 400, 1_000),
        ("0", 1_000, 0),
        ("1.5", 3, 5),  # 4,5 centavos: o meio centavo sobe
        ("1.49", 3, 4),  # 4,47 centavos: abaixo do meio, desce
        ("0.0001", 1, 0),  # fração mínima da coluna: menos de meio centavo
        ("0.5", 1, 1),  # exatamente meio centavo sobe
        ("1200", 108_333, 129_999_600),  # o caso do protótipo: não arredonda para 130.000.000
    ],
)
def test_valor_orcado_e_quantidade_vezes_preco_em_centavos(
    quantity: str, price: int, expected: int
) -> None:
    assert budgeted_cents(D(quantity), price) == expected


def test_valor_orcado_sem_quantidade_ou_sem_preco_vale_zero() -> None:
    assert budgeted_cents(None, 1_000) == 0
    assert budgeted_cents(D("3"), None) == 0


# ── Totais da árvore ─────────────────────────────────────────────────────


def test_pacote_e_subpacote_somam_os_itens_em_centavos(tree_items: list[ItemLine]) -> None:
    totals = item_totals(tree_items)

    assert totals[3] == 10_000
    assert totals[4] == 1_000
    assert totals[2] == 11_000  # subpacote 1.1
    assert totals[5] == 5_000  # subpacote 1.2
    assert totals[1] == 16_000  # pacote 1
    assert totals[7] == 0  # pacote sem item vale zero


def test_orcamento_vigente_do_projeto_e_a_soma_dos_pacotes(tree_items: list[ItemLine]) -> None:
    assert project_total_cents(tree_items) == 16_000
    assert project_total_cents([]) == 0


def test_codigo_ordena_pelos_numeros_e_nao_pelo_texto() -> None:
    codes = ["1.10", "1.2", "1", "10", "2", "1.2.1"]

    assert sorted(codes, key=code_key) == ["1", "1.2", "1.2.1", "1.10", "2", "10"]


def test_arvore_do_projeto_abre_com_a_linha_zero_e_o_total(tree_items: list[ItemLine]) -> None:
    rows = build_project_tree(
        tree_items, project_id=9, project_label="TN-1 · Fábrica", root_description="Fábrica"
    )

    assert [row.code for row in rows] == ["0", "1", "1.1", "1.1.1", "1.1.2", "1.2", "1.2.1", "2"]
    root = rows[0]
    assert (root.is_root, root.level, root.description) == (True, 0, "Fábrica")
    assert root.budget_cents == 16_000
    assert sum(row.budget_cents for row in rows if row.level == 1) == root.budget_cents
    leaf = next(row for row in rows if row.code == "1.1.2")
    assert (leaf.quantity, leaf.unit_price_cents, leaf.budget_cents) == (D("2.5"), 400, 1_000)
    assert next(row for row in rows if row.code == "1").capex is None  # só o item é CAPEX/OPEX


def test_arvore_de_projeto_sem_item_so_tem_a_linha_zero() -> None:
    rows = build_project_tree([], project_id=1, project_label="", root_description="Vazio")

    assert [row.code for row in rows] == ["0"]
    assert rows[0].budget_cents == 0


def test_arvore_da_carteira_tem_portfolio_projeto_e_pacote_principal(
    tree_items: list[ItemLine],
) -> None:
    second = [_package(1, "1", "Obra civil"), _subpackage(2, 1, "1.1")]
    second.append(_item(3, 2, "1.1.1", "1", 4_000))
    projects = [
        PortfolioProject(
            id=1, label="TN-1 · Fábrica", manager="Gerente A", items=tree_items, weight=D("80")
        ),
        PortfolioProject(id=2, label="TN-2 · Vazio", manager=None, items=[]),
        PortfolioProject(id=3, label="TN-3 · Caldeira", manager="Gerente C", items=second),
    ]

    rows = build_portfolio_tree(projects, root_description="Portfólio de projetos")

    assert [(row.code, row.level) for row in rows] == [
        ("0", 0),
        ("1", 1),
        ("1.1", 2),
        ("1.2", 2),
        ("2", 1),  # o projeto sem item não entra e a numeração segue sem buraco
        ("2.1", 2),
    ]
    assert rows[0].budget_cents == 20_000
    assert (rows[1].description, rows[1].responsible, rows[1].weight) == (
        "TN-1 · Fábrica",
        "Gerente A",
        D("80"),
    )
    assert rows[1].budget_cents == 16_000
    assert [row.budget_cents for row in rows if row.level == 2] == [16_000, 0, 4_000]
    assert all(row.item_id is None for row in rows)


# ── Filtro e recolher ────────────────────────────────────────────────────


@pytest.fixture
def rows(tree_items: list[ItemLine]) -> tuple:
    return build_project_tree(
        tree_items, project_id=1, project_label="P", root_description="Projeto"
    )


def test_filtro_sem_criterio_so_corta_pelo_nivel(rows: tuple) -> None:
    packages = filter_tree(rows, max_level=1)
    subpackages = filter_tree(rows, max_level=2)

    assert [row.code for row in packages] == ["0", "1", "2"]
    assert [row.code for row in subpackages] == ["0", "1", "1.1", "1.2", "2"]
    assert len(filter_tree(rows)) == len(rows)


def test_busca_ignora_acento_e_caixa_e_mantem_os_ancestrais(rows: tuple) -> None:
    found = filter_tree(rows, search="DETALHAMENTO")

    assert [row.code for row in found] == ["0", "1", "1.2", "1.2.1"]
    assert [row.code for row in filter_tree(rows, search="projeto basico")] == [
        "0",
        "1",
        "1.1",
        "1.1.1",
    ]


def test_busca_tambem_casa_o_codigo(rows: tuple) -> None:
    assert [row.code for row in filter_tree(rows, search="1.1.2")] == ["0", "1", "1.1", "1.1.2"]


def test_a_linha_zero_fica_mesmo_quando_nada_casa(rows: tuple) -> None:
    assert [row.code for row in filter_tree(rows, search="não existe")] == ["0"]


def test_filtro_por_tipo_de_custo_so_pega_itens_do_tipo(rows: tuple) -> None:
    found = filter_tree(rows, cost_type="Material")

    assert [row.code for row in found] == ["0", "1", "1.1", "1.1.2"]
    assert [row.code for row in filter_tree(rows, cost_type="Equipamento")] == ["0"]


def test_total_filtrado_soma_os_itens_e_na_falta_deles_o_nivel_mais_raso(rows: tuple) -> None:
    only_material = filter_tree(rows, cost_type="Material")
    packages = filter_tree(rows, max_level=1)

    assert filtered_total_cents(only_material) == 1_000
    assert filtered_total_cents(packages) == 16_000  # pacotes 1 (16.000) e 2 (0)
    assert filtered_total_cents(filter_tree(rows, search="não existe")) == 0


def test_so_a_linha_com_filhas_ganha_a_seta_de_recolher(rows: tuple) -> None:
    parents = parent_codes(filter_tree(rows, max_level=2))

    assert parents == {"0", "1"}  # 1.1 e 1.2 ficaram sem itens abaixo: sem seta
    assert "0" not in parent_codes(filter_tree(rows, search="não existe"))


# ── Maior resto ──────────────────────────────────────────────────────────


def test_maior_resto_fecha_cem_com_tres_partes_iguais() -> None:
    result = largest_remainder({"a": D(1), "b": D(1), "c": D(1)})

    assert result == {"a": D("33.34"), "b": D("33.33"), "c": D("33.33")}  # o empate vai ao 1º
    assert sum(result.values()) == D(100)


def test_maior_resto_da_o_centavo_que_falta_a_quem_tem_o_maior_resto() -> None:
    # 55,3545 / 29,3434 / 15,3021: os pisos somam 99,99 e o resto maior é o do primeiro.
    result = largest_remainder(
        {1: D("55.3545066045"), 2: D("29.3434343434"), 3: D("15.3020590521")}
    )

    assert result == {1: D("55.36"), 2: D("29.34"), 3: D("15.30")}


@pytest.mark.parametrize("count", range(1, 13))
def test_maior_resto_sempre_soma_exatamente_cem(count: int) -> None:
    for seed in range(1, 40):
        raw = {index: D(((index + 3) * seed * 7919) % 1013 + 1) for index in range(count)}

        result = largest_remainder(raw)

        assert sum(result.values()) == D(100), (count, seed)
        assert all(value >= 0 for value in result.values())


def test_maior_resto_com_um_unico_valor_e_cem() -> None:
    assert largest_remainder({"unico": D("0.01")}) == {"unico": D(100)}


def test_maior_resto_de_tudo_zero_divide_igualmente() -> None:
    result = largest_remainder({"a": D(0), "b": D(0), "c": D(0), "d": D(0)})

    assert result == {"a": D(25), "b": D(25), "c": D(25), "d": D(25)}


def test_maior_resto_sem_valores_devolve_vazio() -> None:
    assert largest_remainder({}) == {}


def test_maior_resto_aceita_outro_total() -> None:
    result = largest_remainder({"a": D(1), "b": D(2)}, total=D(10))

    assert result == {"a": D("3.33"), "b": D("6.67")}


# ── Ponderação da carteira ───────────────────────────────────────────────

CRITERIA = (
    WeightCriterion(id="valor", weight=D(60), source="orcamento"),
    WeightCriterion(id="estrategico", weight=D(25), source="nota"),
    WeightCriterion(id="complexidade", weight=D(15), source="nota"),
)

PROTOTYPE_PROJECTS = (
    WeightInput(1, 4_460_000_000, {"estrategico": 5, "complexidade": 5}),
    WeightInput(2, 1_820_000_000, {"estrategico": 4, "complexidade": 4}),
    WeightInput(3, 740_000_000, {"estrategico": 3, "complexidade": 2}),
)


def test_ponderacao_da_carteira_do_prototipo_da_55_36_29_34_15_30() -> None:
    weights = portfolio_weights(PROTOTYPE_PROJECTS, CRITERIA)

    assert {key: value.weight for key, value in weights.items()} == {
        1: D("55.36"),
        2: D("29.34"),
        3: D("15.30"),
    }
    assert sum(value.weight for value in weights.values()) == D(100)


def test_ponderacao_guarda_a_participacao_de_cada_criterio() -> None:
    weights = portfolio_weights(PROTOTYPE_PROJECTS, CRITERIA)

    assert weights[1].shares == {
        "valor": D("63.53"),  # 4.460 / 7.020
        "estrategico": D("41.67"),  # 5 / 12
        "complexidade": D("45.45"),  # 5 / 11
    }
    assert weights[3].shares["complexidade"] == D("18.18")  # 2 / 11


def test_ponderacao_so_pelo_orcamento_e_a_participacao_do_orcamento() -> None:
    only_budget = (WeightCriterion(id="valor", weight=D(100), source="orcamento"),)

    weights = portfolio_weights(PROTOTYPE_PROJECTS, only_budget)

    assert {key: value.weight for key, value in weights.items()} == {
        1: D("63.53"),
        2: D("25.93"),
        3: D("10.54"),
    }


def test_ponderacao_divide_pela_soma_dos_pesos_dos_criterios() -> None:
    doubled = tuple(
        WeightCriterion(id=c.id, weight=c.weight * 2, source=c.source) for c in CRITERIA
    )

    assert portfolio_weights(PROTOTYPE_PROJECTS, doubled) == portfolio_weights(
        PROTOTYPE_PROJECTS, CRITERIA
    )


def test_projeto_sem_nota_pesa_zero_no_criterio_de_nota() -> None:
    projects = (
        WeightInput(1, 1_000, {"estrategico": 4}),
        WeightInput(2, 1_000, {}),
    )
    criteria = (WeightCriterion(id="estrategico", weight=D(100), source="nota"),)

    weights = portfolio_weights(projects, criteria)

    assert (weights[1].weight, weights[2].weight) == (D(100), D(0))


def test_ponderacao_com_soma_zero_divide_igualmente_entre_os_projetos() -> None:
    projects = (WeightInput(1, 0, {}), WeightInput(2, 0, {}), WeightInput(3, 0, {}))

    weights = portfolio_weights(projects, CRITERIA)

    assert sorted(value.weight for value in weights.values()) == [
        D("33.33"),
        D("33.33"),
        D("33.34"),
    ]
    assert sum(value.weight for value in weights.values()) == D(100)
    assert weights[1].shares["valor"] == D("33.33")


def test_ponderacao_de_um_projeto_so_e_cem() -> None:
    weights = portfolio_weights((WeightInput(7, 5, {"estrategico": 3}),), CRITERIA)

    assert weights[7].weight == D(100)


def test_ponderacao_sem_projetos_e_vazia() -> None:
    assert portfolio_weights((), CRITERIA) == {}
