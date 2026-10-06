"""Versão imprimível (ISSUE-017, D12): a folha que o botão PDF monta e o navegador imprime.

Não há biblioteca de PDF: o servidor renderiza a folha da tela (cabeçalho com o logo e o
contexto, indicadores com a referência de gestão, gráficos e tabelas) e a folha de
impressão do Design System (``app/ds/print.css``) a põe no papel. O teste confere as duas
metades. Na do servidor, o fragmento: sem barra lateral nem navegação, a coluna Projeto
no Portfólio, o cabeçalho de cada tabela num ``thead`` e a linha de totais num ``tfoot``,
o papel A3 quando o documento pede e o texto sempre escapado. Na do papel, as regras do
CSS que fazem a folha sair como a spec manda: ``@page`` A4 paisagem (A3 quando pede), só a
folha no papel, cabeçalho de tabela repetido, linha que não parte e fundos preservados.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import azure.functions as func
import pytest

from src.core import printable
from src.core.export_document import Chart, Column, Kpi, Paper, Table, row
from tests.documentos_de_exportacao import CALDEIRA, FABRICA, GRAFICO
from tests.documentos_de_exportacao import documento as _documento
from tests.html_tags import Tag, find_all, find_by_id, parse_tags

RAIZ = Path(__file__).resolve().parents[3]
PRINT_CSS = RAIZ / "app" / "ds" / "print.css"
SHELL_CSS = RAIZ / "app" / "ds" / "shell.css"
INDEX_HTML = RAIZ / "app" / "index.html"
UI_JS = RAIZ / "app" / "ds" / "ui.js"

ID_DA_FOLHA = "folha-impressao"
COLUNAS_NO_PORTFOLIO = 7
COLUNAS_DO_PROJETO = 6


def _requisicao(alvo: str | None = ID_DA_FOLHA) -> func.HttpRequest:
    """O pedido do botão PDF: com o cabeçalho do Alpine e o alvo da folha."""
    cabecalhos = {"X-Alpine-Request": "true"}
    if alvo is not None:
        cabecalhos["X-Alpine-Target"] = alvo
    return func.HttpRequest(
        method="GET",
        url="/api/modulo/tela/imprimivel",
        headers=cabecalhos,
        params={},
        route_params={},
        body=b"",
    )


def _html(*, alvo: str | None = ID_DA_FOLHA, **opcoes: Any) -> str:
    resposta = printable.printable_response(_documento(**opcoes), _requisicao(alvo))
    assert resposta.status_code == 200
    return resposta.get_body().decode()


def _folha(**opcoes: Any) -> list[Tag]:
    return parse_tags(_html(**opcoes))


def _tabelas(tags: list[Tag]) -> list[list[Tag]]:
    """Os tags de cada ``<table>``: de uma tabela até a seguinte (as seções são irmãs)."""
    inicios = [posicao for posicao, tag in enumerate(tags) if tag.name == "table"]
    fins = [*inicios[1:], len(tags)]
    return [tags[inicio:fim] for inicio, fim in zip(inicios, fins, strict=True)]


def _textos(tags: list[Tag], nome: str, classe: str | None = None) -> list[str]:
    return [tag.clean_text() for tag in find_all(tags, nome, classe)]


def _linhas_de_celulas(tabela: list[Tag], colunas: int) -> list[list[str]]:
    celulas = [tag.clean_text() for tag in tabela if tag.name == "td"]
    return [celulas[inicio : inicio + colunas] for inicio in range(0, len(celulas), colunas)]


def _regra(css: str, seletor: str) -> str:
    """As declarações da regra de ``seletor``, sem comentários e com um espaço entre as palavras."""
    limpo = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    achado = re.search(rf"(?:^|[{{}};])\s*{re.escape(seletor)}\s*\{{([^{{}}]*)\}}", limpo)
    assert achado is not None, seletor
    return " ".join(achado.group(1).split())


# ── O fragmento que o servidor entrega ───────────────────────────────────


def test_a_folha_e_um_fragmento_comum_sem_link_estilo_nem_script() -> None:
    nomes = {tag.name for tag in _folha(charts=(GRAFICO,))}

    assert nomes.isdisjoint({"link", "style", "script", "html", "head", "body"})


def test_a_resposta_e_html_e_nao_fica_em_cache() -> None:
    resposta = printable.printable_response(_documento(), _requisicao())

    assert resposta.mimetype == "text/html"
    assert resposta.headers["Cache-Control"] == "no-cache"


def test_a_raiz_leva_o_alvo_que_o_botao_pediu_o_papel_e_o_titulo_do_pdf() -> None:
    raiz = find_by_id(_folha(), ID_DA_FOLHA)

    assert raiz is not None
    assert raiz.name == "div"
    assert raiz.classes == {"folha", "folha--a4"}
    assert raiz.attrs["data-titulo"] == "Mapa de controle - Portfólio - 2026-10-05"
    assert raiz.attrs["data-animar"] == "nao"


def test_sem_o_alvo_a_raiz_tem_o_id_da_folha_e_com_outro_alvo_leva_o_dele() -> None:
    sem_alvo = parse_tags(_html(alvo=None))
    com_outro = parse_tags(_html(alvo="outro-alvo"))

    assert find_by_id(sem_alvo, ID_DA_FOLHA) is not None
    assert find_by_id(com_outro, "outro-alvo") is not None
    assert find_by_id(com_outro, ID_DA_FOLHA) is None


@pytest.mark.parametrize(("papel", "classe"), [(Paper.A4, "folha--a4"), (Paper.A3, "folha--a3")])
def test_o_papel_do_documento_vira_a_classe_da_folha(papel: Paper, classe: str) -> None:
    raiz = find_by_id(_folha(paper=papel), ID_DA_FOLHA)

    assert raiz is not None
    assert raiz.classes == {"folha", classe}


def test_sem_barra_lateral_nem_navegacao() -> None:
    tags = _folha(charts=(GRAFICO,))

    for nome in ("a", "nav", "aside", "button", "form", "input", "select", "textarea", "iframe"):
        assert find_all(tags, nome) == [], nome
    interface = {"sidebar", "module-tabs", "tab", "skip-link", "page-head__actions", "btn"}
    for tag in tags:
        assert tag.classes.isdisjoint(interface), tag.attrs
        assert not [nome for nome in tag.attrs if nome.startswith(("x-", "@", ":"))], tag.attrs
        assert "data-tn-tela" not in tag.attrs


def test_o_cabecalho_traz_o_logo_a_marca_a_emissao_o_titulo_e_o_contexto() -> None:
    tags = _folha()

    logo = find_all(tags, "img", "folha__logo")
    assert [imagem.attrs["src"] for imagem in logo] == ["/ds/assets/favicon-timenow.png"]
    assert logo[0].attrs["alt"] == ""
    assert _textos(tags, "span", "folha__produto") == ["Timenow GestNow"]
    assert _textos(tags, "p", "folha__emissao") == ["Gerado em 05/10/2026"]
    assert _textos(tags, "h1", "folha__titulo") == ["Mapa de controle"]
    contexto = list(zip(_textos(tags, "dt"), _textos(tags, "dd"), strict=True))
    assert contexto == [("Escopo", "Portfólio"), ("Período", "S40/2026")]


def test_o_escopo_de_um_projeto_aparece_no_contexto() -> None:
    tags = _folha(portfolio=False)

    assert _textos(tags, "dt")[0] == "Escopo"
    assert _textos(tags, "dd")[0] == FABRICA


def test_os_indicadores_trazem_valor_situacao_e_a_referencia_de_gestao() -> None:
    tags = _folha()

    assert _textos(tags, "span", "folha__kpi-rotulo") == [
        "Avanço",
        "Desembolso",
        "Concluídas",
        "Próximo marco",
    ]
    assert _textos(tags, "strong", "folha__kpi-valor") == [
        "87,5%",
        "R$ 1.250.000,00",
        "18",
        "19/10/2026",
    ]
    assert _textos(tags, "span", "folha__kpi-situacao") == ["Atenção", "Dentro do orçado", "Futuro"]
    assert _textos(tags, "span", "folha__kpi-referencia") == [
        "Referência: Meta: 90%",
        "Referência: Orçado: R$ 1.500.000,00",
        "Referência: Previsto: 20",
        "Referência: Data prevista",
    ]
    assert [sorted(kpi.classes) for kpi in find_all(tags, "div", "folha__kpi")] == [
        ["folha__kpi", "folha__kpi--warn"],
        ["folha__kpi", "folha__kpi--ok"],
        ["folha__kpi"],
        ["folha__kpi", "folha__kpi--info"],
    ]


def test_indicador_sem_valor_sai_em_branco_e_mantem_a_referencia() -> None:
    sem_dado = (Kpi("Sem dado", None, "Meta: 90%"),)

    tags = _folha(kpis=sem_dado)

    assert _textos(tags, "strong", "folha__kpi-valor") == [""]
    assert _textos(tags, "span", "folha__kpi-referencia") == ["Referência: Meta: 90%"]


def test_documento_sem_indicadores_nao_traz_a_secao() -> None:
    tags = _folha(kpis=())

    assert find_all(tags, "section", "folha__kpis") == []


def test_o_grafico_vai_em_atributos_para_o_motor_desenhar() -> None:
    tags = _folha(charts=(GRAFICO,))

    assert _textos(tags, "figcaption", "folha__grafico-titulo") == ["Linha de base x Atual"]
    (host,) = [tag for tag in tags if "data-grafico" in tag.attrs]
    assert host.attrs["data-grafico"] == "comparativo-barras"
    assert json.loads(host.attrs["data-dados"]) == GRAFICO.data


def test_o_dado_do_grafico_nao_escapa_do_atributo() -> None:
    perigoso = Chart("Perigoso", "comparativo-barras", {"titulo": "a'b<c>&d\"e"})

    html = _html(charts=(perigoso,))

    (host,) = [tag for tag in parse_tags(html) if "data-grafico" in tag.attrs]
    assert json.loads(host.attrs["data-dados"]) == perigoso.data
    assert "a'b<c>" not in html


# ── As tabelas: cabeçalho que repete, totais uma vez ─────────────────────


def test_cada_tabela_tem_o_cabecalho_num_thead_e_os_totais_num_tfoot() -> None:
    atividades, legenda = _tabelas(_folha())

    assert [tag.name for tag in atividades if tag.name in {"thead", "tbody", "tfoot"}] == [
        "thead",
        "tbody",
        "tfoot",
    ]
    assert [tag.name for tag in legenda if tag.name in {"thead", "tbody", "tfoot"}] == [
        "thead",
        "tbody",
    ]
    assert len([tag for tag in atividades if tag.name == "tr"]) == 1 + 3 + 1
    assert len([tag for tag in legenda if tag.name == "tr"]) == 1 + 2


def test_o_titulo_de_cada_tabela_vem_antes_dela() -> None:
    assert _textos(_folha(), "h2", "folha__secao-titulo") == ["Atividades", "Legenda"]


def test_no_portfolio_a_tabela_por_projeto_abre_com_a_coluna_projeto() -> None:
    atividades, legenda = _tabelas(_folha())

    cabecalho = [tag for tag in atividades if tag.name == "th"]
    assert [coluna.clean_text() for coluna in cabecalho] == [
        "Projeto",
        "Atividade",
        "Início",
        "Quantidade",
        "Avanço",
        "Valor",
        "Situação",
    ]
    assert all(coluna.attrs["scope"] == "col" for coluna in cabecalho)
    assert [tag.clean_text() for tag in legenda if tag.name == "th"] == ["Situação", "Significado"]
    projetos = [linha[0] for linha in _linhas_de_celulas(atividades, COLUNAS_NO_PORTFOLIO)]
    assert projetos == [FABRICA, FABRICA, CALDEIRA, ""]


def test_fora_do_portfolio_a_folha_nao_tem_a_coluna_projeto() -> None:
    atividades, _ = _tabelas(_folha(portfolio=False))

    assert [tag.clean_text() for tag in atividades if tag.name == "th"][:2] == [
        "Atividade",
        "Início",
    ]
    assert len([tag for tag in atividades if tag.name == "th"]) == COLUNAS_DO_PROJETO


def test_as_celulas_saem_formatadas_como_a_pessoa_le() -> None:
    atividades, _ = _tabelas(_folha())

    assert _linhas_de_celulas(atividades, COLUNAS_NO_PORTFOLIO) == [
        [FABRICA, "Concretagem", "05/09/2026", "120", "100,0%", "R$ 450.000,00", "No prazo"],
        [FABRICA, "Montagem", "25/09/2026", "80", "62,5%", "R$ 275.000,00", "Atenção"],
        [CALDEIRA, "Testes", "10/10/2026", "40", "10,0%", "R$ 100.000,00", "Atrasada"],
        ["", "Total", "", "240", "", "R$ 825.000,00", ""],
    ]


def test_o_alinhamento_e_o_tom_vao_por_classe() -> None:
    atividades, _ = _tabelas(_folha())

    cabecalho = [tag.attrs["class"] for tag in atividades if tag.name == "th"]
    assert cabecalho == [
        "folha__th",
        "folha__th",
        "folha__th folha__th--centro",
        "folha__th folha__th--direita",
        "folha__th folha__th--direita",
        "folha__th folha__th--direita",
        "folha__th",
    ]
    celulas = [tag.attrs["class"] for tag in atividades if tag.name == "td"]
    assert celulas[:7] == [
        "folha__td",
        "folha__td",
        "folha__td folha__td--centro",
        "folha__td folha__td--direita",
        "folha__td folha__td--direita",
        "folha__td folha__td--direita",
        "folha__td folha__td--ok",
    ]
    assert celulas[13] == "folha__td folha__td--warn"
    assert celulas[20] == "folha__td folha__td--erro"
    # A linha de totais: a classe do total em cada célula, o alinhamento do tipo.
    assert celulas[-7:] == [
        "folha__td folha__td--total",
        "folha__td folha__td--total",
        "folha__td folha__td--centro folha__td--total",
        "folha__td folha__td--direita folha__td--total",
        "folha__td folha__td--direita folha__td--total",
        "folha__td folha__td--direita folha__td--total",
        "folha__td folha__td--total",
    ]


def test_tabela_sem_linhas_diz_que_nao_ha_registro_e_ocupa_a_largura_toda() -> None:
    vazia = Table(title="Vazia", columns=(Column("A"), Column("B")), rows=())

    tags = _folha(portfolio=False, tables=(vazia,))

    (celula,) = find_all(tags, "td", "folha__vazio")
    assert celula.clean_text() == "Nenhum registro."
    assert celula.attrs["colspan"] == "2"
    assert find_all(tags, "tfoot") == []


def test_no_portfolio_o_vazio_ocupa_tambem_a_coluna_projeto() -> None:
    vazia = Table(title="Vazia", columns=(Column("A"),), rows=())

    tags = _folha(portfolio=True, tables=(vazia,))

    assert _textos(tags, "th") == ["Projeto", "A"]
    assert find_all(tags, "td", "folha__vazio")[0].attrs["colspan"] == "2"


def test_o_texto_do_documento_sai_escapado() -> None:
    tabela = Table(
        title="<b>Título</b>", columns=(Column("A"),), rows=(row("<script>alert(1)</script>"),)
    )

    html = _html(portfolio=False, tables=(tabela,))

    assert "<script" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert find_all(parse_tags(html), "b") == []


def test_a_folha_do_documento_vem_formatada_para_o_template() -> None:
    folha = printable.build_sheet(_documento())

    assert folha.generated_on == "05/10/2026"
    assert folha.paper == "a4"
    assert folha.file_title == "Mapa de controle - Portfólio - 2026-10-05"
    assert [tabela.title for tabela in folha.tables] == ["Atividades", "Legenda"]
    assert folha.tables[0].columns[0].header == "Projeto"


# ── A folha de impressão do Design System (print.css) ────────────────────


def test_a_pagina_e_a4_paisagem_e_a3_paisagem_quando_a_folha_pede() -> None:
    css = PRINT_CSS.read_text(encoding="utf-8")

    assert "size: A4 landscape" in _regra(css, "@page")
    assert "size: A3 landscape" in _regra(css, "@page folha-a3")
    assert _regra(css, ".folha--a3") == "page: folha-a3;"


def test_no_papel_so_a_folha_sai_e_a_navegacao_nao() -> None:
    css = PRINT_CSS.read_text(encoding="utf-8")
    shell = SHELL_CSS.read_text(encoding="utf-8")

    assert _regra(css, "body.imprimindo > :not(.folha)") == "display: none;"
    assert _regra(shell, ".skip-link, .sidebar, .module-tabs") == "display: none;"


def test_o_cabecalho_da_tabela_repete_a_linha_nao_parte_e_o_total_sai_uma_vez() -> None:
    css = PRINT_CSS.read_text(encoding="utf-8")

    assert _regra(css, ".folha__tbl thead") == "display: table-header-group;"
    assert _regra(css, ".folha__tbl tfoot") == "display: table-row-group;"
    linha = _regra(css, ".folha__tbl tr")
    assert "break-inside: avoid" in linha
    assert "page-break-inside: avoid" in linha
    assert "break-after: avoid" in _regra(css, ".folha__secao-titulo")


def test_os_fundos_e_as_cores_saem_como_na_tela() -> None:
    css = PRINT_CSS.read_text(encoding="utf-8")

    regra = _regra(css, "html")
    assert "print-color-adjust: exact" in regra
    assert "-webkit-print-color-adjust: exact" in regra


def test_numa_tela_comum_impressa_a_tabela_do_design_system_tambem_repete_o_cabecalho() -> None:
    css = PRINT_CSS.read_text(encoding="utf-8")

    assert _regra(css, ".tbl thead") == "display: table-header-group;"
    assert "break-inside: avoid" in _regra(css, ".tbl tr, .kpi")


def test_a_folha_espera_fora_da_vista_na_tela_com_a_largura_do_papel() -> None:
    shell = SHELL_CSS.read_text(encoding="utf-8")

    assert re.search(r"@media screen\s*\{\s*\.folha\s*\{", shell) is not None
    espera = _regra(shell, ".folha")
    assert "position: fixed" in espera
    assert "visibility: hidden" in espera
    assert "width: var(--folha-largura)" in espera
    assert _regra(shell, ".folha--a3") == "--folha-largura: 400mm;"


def test_a_folha_de_impressao_usa_so_tokens() -> None:
    css = PRINT_CSS.read_text(encoding="utf-8")
    sem_comentarios = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)

    assert re.search(r"#[0-9A-Fa-f]{3,8}\b", sem_comentarios) is None
    assert re.search(r"\b(?:rgb|rgba|hsl|hsla)\(", sem_comentarios) is None


# ── A ligação no shell e o botão ─────────────────────────────────────────


def test_o_shell_liga_a_folha_de_impressao_so_para_o_papel_e_so_uma_vez() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")

    ligacoes = re.findall(r'<link\b[^>]*href="/ds/print\.css"[^>]*>', html)
    assert len(ligacoes) == 1
    assert 'rel="stylesheet"' in ligacoes[0]
    assert 'media="print"' in ligacoes[0]
    assert html.index("/ds/patterns.css") < html.index("/ds/print.css")


def test_o_botao_pdf_aciona_a_impressao_do_navegador_e_o_excel_baixa_o_arquivo() -> None:
    js = UI_JS.read_text(encoding="utf-8")

    assert "data-tn-pdf" in js
    assert "data-tn-excel" in js
    assert "window.print()" in js
    assert "afterprint" in js
    # O fragmento passa pelo gate do Alpine, que o botão imita ao buscar a folha.
    assert '"X-Alpine-Request": "true"' in js
