"""Documento de exportação (ISSUE-017, D12): a descrição única que alimenta o Excel e a folha.

Toda conta de apresentação (``format_value``) tem o seu caso de fronteira: o
arredondamento (metade para cima), o negativo que arredonda a zero, a ausência,
o dinheiro em centavos e a data. O contrato do documento falha alto quando a
tela que o montou se engana: linha com o número errado de células, linha do
Portfólio sem projeto e texto numa coluna de número. No Portfólio, toda tabela
por projeto abre com a coluna Projeto (HU-016).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest

from src.core.export_document import (
    PORTFOLIO_LABEL,
    PROJECT_HEADER,
    Cell,
    CellValue,
    Column,
    Document,
    InvalidDocumentError,
    Row,
    Table,
    Tone,
    ValueKind,
    cents_of,
    date_of,
    describe_scope,
    format_value,
    number_of,
    project_label,
    resolve_tables,
    row,
)
from src.core.scope import Scope

HOJE = date(2026, 10, 5)
FABRICA = "TN-001 · Fábrica"
CALDEIRA = "TN-002 · Caldeira"
COLUNAS = (Column("Atividade"), Column("Quantidade", ValueKind.INTEGER))


@dataclass(frozen=True)
class _Projeto:
    id: int
    code: str
    name: str


def _documento(*tabelas: Table, portfolio: bool) -> Document:
    return Document(
        title="Teste",
        scope_label=PORTFOLIO_LABEL if portfolio else FABRICA,
        generated_on=HOJE,
        portfolio=portfolio,
        tables=tabelas,
    )


def _tabela_por_projeto(
    *, rows: tuple[Row, ...] | None = None, totals: tuple[Cell, ...] | None = None
) -> Table:
    """Duas atividades, uma em cada projeto, como a tela de um módulo as montaria."""
    padrao = (row("Concretagem", 10, project=FABRICA), row("Montagem", 20, project=CALDEIRA))
    return Table(
        title="Atividades",
        columns=COLUNAS,
        rows=padrao if rows is None else rows,
        totals=totals,
    )


# ── Como um valor chega a quem lê ────────────────────────────────────────


@pytest.mark.parametrize(
    ("tipo", "valor", "digitos", "esperado"),
    [
        (ValueKind.TEXT, "Concretagem", 2, "Concretagem"),
        (ValueKind.TEXT, None, 2, ""),
        (ValueKind.INTEGER, 1234567, 2, "1.234.567"),
        (ValueKind.INTEGER, 0, 2, "0"),
        (ValueKind.INTEGER, -1500, 2, "-1.500"),
        (ValueKind.INTEGER, 2.5, 2, "3"),
        (ValueKind.INTEGER, -2.5, 2, "-3"),
        (ValueKind.DECIMAL, Decimal("1234.5"), 2, "1.234,50"),
        (ValueKind.DECIMAL, 0.005, 2, "0,01"),
        (ValueKind.DECIMAL, 0.004, 2, "0,00"),
        (ValueKind.DECIMAL, -0.004, 2, "0,00"),
        (ValueKind.DECIMAL, -1234.567, 1, "-1.234,6"),
        (ValueKind.DECIMAL, 1_000_000_000_000, 0, "1.000.000.000.000"),
        (ValueKind.PERCENT, 45.3, 1, "45,3%"),
        (ValueKind.PERCENT, 100, 1, "100,0%"),
        (ValueKind.PERCENT, 0, 1, "0,0%"),
        (ValueKind.PERCENT, -0.04, 1, "0,0%"),
        (ValueKind.MONEY, 123456, 2, "R$ 1.234,56"),
        (ValueKind.MONEY, 0, 2, "R$ 0,00"),
        (ValueKind.MONEY, 1, 2, "R$ 0,01"),
        (ValueKind.MONEY, -5, 2, "-R$ 0,05"),
        (ValueKind.MONEY, 125_000_000, 2, "R$ 1.250.000,00"),
        (ValueKind.DATE, date(2026, 10, 5), 2, "05/10/2026"),
        (ValueKind.DATE, date(2026, 1, 1), 2, "01/01/2026"),
        (ValueKind.DATE, None, 2, ""),
    ],
)
def test_valor_e_escrito_como_o_brasil_le(
    tipo: ValueKind, valor: CellValue, digitos: int, esperado: str
) -> None:
    assert format_value(tipo, valor, digitos) == esperado


@pytest.mark.parametrize(
    ("tipo", "valor"),
    [
        (ValueKind.INTEGER, "12"),
        (ValueKind.INTEGER, True),
        (ValueKind.DECIMAL, float("nan")),
        (ValueKind.DECIMAL, float("inf")),
        (ValueKind.PERCENT, "45%"),
        (ValueKind.MONEY, 123.5),
        (ValueKind.MONEY, "R$ 10,00"),
        (ValueKind.DATE, "05/10/2026"),
        (ValueKind.DATE, 20261005),
    ],
)
def test_valor_de_outro_tipo_na_coluna_falha_alto(tipo: ValueKind, valor: CellValue) -> None:
    with pytest.raises(InvalidDocumentError):
        format_value(tipo, valor)


def test_dinheiro_e_em_centavos_inteiros_e_aceita_o_decimal_inteiro() -> None:
    assert cents_of(100) == 100
    assert cents_of(100.0) == 100
    assert cents_of(Decimal("100.0")) == 100
    with pytest.raises(InvalidDocumentError, match="centavos"):
        cents_of(Decimal("100.5"))


def test_numero_nao_aceita_texto_nem_booleano() -> None:
    assert number_of(Decimal("1.5")) == Decimal("1.5")
    for invalido in ("1", True, None):
        with pytest.raises(InvalidDocumentError):
            number_of(invalido)


def test_data_so_aceita_data() -> None:
    assert date_of(HOJE) == HOJE
    with pytest.raises(InvalidDocumentError, match="Data esperada"):
        date_of("2026-10-05")


# ── A linha e o escopo ───────────────────────────────────────────────────


def test_row_embrulha_o_valor_e_preserva_a_celula_com_tom() -> None:
    linha = row("A", 1, Cell(2, Tone.OK), project=FABRICA)

    assert linha.cells == (Cell("A"), Cell(1), Cell(2, Tone.OK))
    assert linha.project == FABRICA


def test_projeto_aparece_como_codigo_e_nome() -> None:
    assert project_label(_Projeto(1, "TN-001", "Fábrica")) == FABRICA


def test_o_escopo_do_cabecalho_e_o_portfolio_ou_o_projeto() -> None:
    projetos = [_Projeto(1, "TN-001", "Fábrica"), _Projeto(2, "TN-002", "Caldeira")]

    assert describe_scope(Scope(project_id=None, source="padrao"), projetos) == "Portfólio"
    assert describe_scope(Scope(project_id=2, source="url"), projetos) == CALDEIRA


def test_escopo_de_projeto_que_a_lista_nao_traz_nao_some_em_silencio() -> None:
    assert describe_scope(Scope(project_id=99, source="url"), []) == "Projeto 99"


# ── No Portfólio, a coluna Projeto (HU-016) ──────────────────────────────


def test_no_portfolio_a_tabela_abre_com_a_coluna_projeto_de_cada_linha() -> None:
    documento = _documento(_tabela_por_projeto(), portfolio=True)

    (tabela,) = resolve_tables(documento)

    assert [coluna.header for coluna in tabela.columns] == [
        PROJECT_HEADER,
        "Atividade",
        "Quantidade",
    ]
    assert [item.cells[0].value for item in tabela.rows] == [FABRICA, CALDEIRA]
    assert all(len(item.cells) == len(tabela.columns) for item in tabela.rows)


def test_fora_do_portfolio_a_tabela_sai_como_foi_montada() -> None:
    tabela = _tabela_por_projeto()
    documento = _documento(tabela, portfolio=False)

    assert resolve_tables(documento) == (tabela,)


def test_tabela_que_nao_e_por_projeto_nao_ganha_a_coluna_no_portfolio() -> None:
    legenda = Table(title="Legenda", columns=COLUNAS, rows=(row("A", 1),), per_project=False)
    documento = _documento(legenda, portfolio=True)

    assert resolve_tables(documento) == (legenda,)


def test_tabela_que_ja_tem_a_coluna_projeto_nao_ganha_outra() -> None:
    propria = Table(
        title="Contratos",
        columns=(Column("Projeto"), Column("Valor", ValueKind.MONEY)),
        rows=(row(FABRICA, 100),),
    )
    documento = _documento(propria, portfolio=True)

    (resolvida,) = resolve_tables(documento)

    assert [coluna.header for coluna in resolvida.columns] == ["Projeto", "Valor"]


def test_a_linha_de_totais_ganha_a_celula_vazia_da_coluna_projeto() -> None:
    totais = (Cell("Total"), Cell(30))
    documento = _documento(_tabela_por_projeto(totals=totais), portfolio=True)

    (tabela,) = resolve_tables(documento)

    assert tabela.totals == (Cell(), Cell("Total"), Cell(30))


def test_portfolio_sem_projetos_tem_tabela_vazia_valida() -> None:
    documento = _documento(_tabela_por_projeto(rows=()), portfolio=True)

    (tabela,) = resolve_tables(documento)

    assert tabela.rows == ()
    assert tabela.columns[0].header == PROJECT_HEADER


# ── O contrato: erro de quem monta a tela falha alto ─────────────────────


def test_linha_com_numero_errado_de_celulas_falha_dizendo_qual_e_a_linha() -> None:
    tabela = _tabela_por_projeto(rows=(row("A", 1, project=FABRICA), row("B", project=FABRICA)))

    with pytest.raises(
        InvalidDocumentError, match=r"Tabela «Atividades», linha 2: 1 células para 2"
    ):
        _documento(tabela, portfolio=False)


def test_no_portfolio_linha_sem_projeto_falha() -> None:
    tabela = _tabela_por_projeto(rows=(row("A", 1),))

    with pytest.raises(InvalidDocumentError, match="no Portfólio toda linha traz o projeto"):
        _documento(tabela, portfolio=True)


def test_fora_do_portfolio_a_linha_nao_precisa_de_projeto() -> None:
    documento = _documento(_tabela_por_projeto(rows=(row("A", 1),)), portfolio=False)

    assert len(documento.tables[0].rows) == 1


def test_linha_de_totais_com_o_numero_errado_de_celulas_falha() -> None:
    tabela = _tabela_por_projeto(totals=(Cell("Total"),))

    with pytest.raises(InvalidDocumentError, match="linha de totais"):
        _documento(tabela, portfolio=False)
