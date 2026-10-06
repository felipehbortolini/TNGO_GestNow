"""Rotas da EAP (ISSUE-036, D8, D12, D14): conteúdo, dicionário e as duas exportações.

Costura HTTP: o handler é chamado com a ``HttpRequest`` montada no teste, como o Azure a
entregaria. A tela é um fragmento (gate do Alpine); o Excel é um download (sem o gate). No
Portfólio a árvore é só leitura (projeto e pacote principal) e as exportações trazem a coluna
Projeto. O cenário e os números esperados vêm de ``tests/apoio_eap.py``.
"""

from __future__ import annotations

from collections.abc import Mapping
from io import BytesIO

import azure.functions as func
import pytest
from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet
from sqlalchemy.orm import Session

from src.core import auth
from src.modulos.planejamento import eap_routes as routes
from src.modulos.planejamento.models import EapItem
from tests.apoio_eap import MEMBER_EMAIL, SUPPLIER_EMAIL, VIEWER_EMAIL, EapCadastro, montar_eap
from tests.html_tags import Tag, find_all, find_by_id, parse_tags
from tests.identidades import cabecalho_do_principal

TARGET = "eap-conteudo"
TREE_SHEET = "Estrutura analítica do projeto"
PORTFOLIO_TREE_SHEET = "Estrutura analítica da carteira"


@pytest.fixture
def eap(sessao: Session) -> EapCadastro:
    return montar_eap(sessao)


def _request(
    path: str,
    *,
    email: str = MEMBER_EMAIL,
    route: Mapping[str, str] | None = None,
    target: str | None = TARGET,
    **query: str,
) -> func.HttpRequest:
    """A request as the browser or the shell sends it; ``target=None`` is a plain link (no Alpine)."""
    headers = {auth.PRINCIPAL_HEADER: cabecalho_do_principal(email)}
    if target is not None:
        headers["X-Alpine-Request"] = "true"
        headers["X-Alpine-Target"] = target
    return func.HttpRequest(
        method="GET",
        url=path,
        headers=headers,
        params=dict(query),
        route_params=dict(route or {}),
        body=b"",
    )


def _content(*, email: str = MEMBER_EMAIL, **params: str) -> func.HttpResponse:
    return routes.eap_content(_request("/api/planejamento/eap", email=email, **params))


def _tags(response: func.HttpResponse) -> list[Tag]:
    return parse_tags(response.get_body().decode())


def _codes(response: func.HttpResponse) -> list[str]:
    return [tag.attrs["data-codigo"] for tag in _tags(response) if "data-codigo" in tag.attrs]


def _marker(response: func.HttpResponse) -> Tag:
    return next(tag for tag in _tags(response) if "data-resultado" in tag.attrs)


# ── O conteúdo da tela ───────────────────────────────────────────────────


def test_conteudo_do_projeto_traz_a_arvore_com_a_linha_zero_e_os_totais(eap: EapCadastro) -> None:
    response = _content(projeto=str(eap.first.id))

    assert response.status_code == 200
    assert _codes(response) == [
        "0", "1", "1.1", "1.1.1", "1.1.2", "1.1.3", "2", "2.1", "2.1.1",
    ]  # fmt: skip
    assert find_by_id(_tags(response), TARGET) is not None
    marker = _marker(response)
    assert marker.attrs["data-resultado"] == "conteudo"
    assert marker.attrs["data-carteira"] == "nao"
    body = response.get_body().decode()
    for text in ("Fundações", "59,0%", "62,0%", "-3,0", "Critério de medição", "Unidades (m³)"):
        assert text in body


def test_conteudo_traz_os_tres_indicadores_com_o_que_se_espera(eap: EapCadastro) -> None:
    body = _content(projeto=str(eap.first.id)).get_body().decode()

    assert "Avanço físico real" in body
    assert "Pacotes de trabalho" in body
    assert "Linha de base 4" in body  # os pacotes com peso congelado na Rev 1
    assert "2 áreas · 2 subáreas · 1 de planejamento (10,00%)" in body
    assert "Término vencido" in body
    assert "1 pacotes com desvio abaixo de -5 p.p." in body


def test_conteudo_marca_o_pacote_vencido_e_o_de_planejamento(eap: EapCadastro) -> None:
    tags = _tags(_content(projeto=str(eap.first.id)))

    overdue = [tag for tag in find_all(tags, "span", "pill--erro") if tag.clean_text() == "vencido"]
    planning = [
        tag for tag in find_all(tags, "span", "pill--info") if tag.clean_text() == "Planejamento"
    ]
    assert len(overdue) == 1
    assert len(planning) == 1


def test_cada_pacote_tem_o_link_do_dicionario_e_area_e_subarea_nao(eap: EapCadastro) -> None:
    tags = _tags(_content(projeto=str(eap.first.id)))

    links = [tag for tag in tags if "data-dicionario" in tag.attrs]
    assert len(links) == 4
    assert all(link.attrs["x-target"] == "eap-dicionario" for link in links)
    assert links[0].attrs["href"] == (
        f"/api/planejamento/eap/pacotes/{eap.item(eap.first, '1.1.1')}/dicionario"
    )


def test_conteudo_traz_as_revisoes_e_o_desdobramento_da_vigente(eap: EapCadastro) -> None:
    body = _content(projeto=str(eap.first.id)).get_body().decode()

    for text in (
        "Revisões da EAP",
        "Rev 1",
        "Vigente",
        "Pacote 1.1.3 incluído",
        "Desdobramentos da revisão vigente",
        "2.1.1 Comissionamento a detalhar",
        "1.1.3 Projeto de processo",
        "Plano detalhado.",
    ):
        assert text in body


def test_a_regra_dos_100_avisa_quando_os_pesos_nao_fecham(eap: EapCadastro) -> None:
    assert "Regra dos 100%" not in _content(projeto=str(eap.first.id)).get_body().decode()
    item = eap.session.get(EapItem, eap.item(eap.first, "1.1.1"))
    assert item is not None
    item.weight = item.weight - 1
    eap.session.flush()

    body = _content(projeto=str(eap.first.id)).get_body().decode()

    assert "Regra dos 100%" in body
    assert "99,00%" in body


def test_conteudo_do_portfolio_e_so_leitura_com_projeto_e_pacote_principal(
    eap: EapCadastro,
) -> None:
    response = _content(projeto="portfolio")

    assert _codes(response) == ["0", "1", "1.1", "1.2", "2", "2.1"]
    tags = _tags(response)
    assert _marker(response).attrs["data-carteira"] == "sim"
    assert not [tag for tag in tags if "data-dicionario" in tag.attrs]
    open_links = [
        tag for tag in tags if tag.attrs.get("href", "").startswith("/planejamento/eap?projeto=")
    ]
    assert len(open_links) == 2  # um "Abrir" por projeto
    body = response.get_body().decode()
    for text in (
        "Peso na carteira",
        "Peso no projeto",
        "45,00%",
        "TN-EAP-001 · Fábrica EAP",
        "Avanço físico ponderado",
        "Revisão vigente da EAP por projeto",
    ):
        assert text in body
    assert "Desdobramentos da revisão vigente" not in body
    assert "Critério de medição" not in body.split("<tbody>")[0]
    assert eap.second.code in body


def test_o_escopo_vem_do_cookie_quando_a_url_nao_o_traz(eap: EapCadastro) -> None:
    plain = _request("/api/planejamento/eap")
    request = func.HttpRequest(
        method="GET",
        url="/api/planejamento/eap",
        headers={**dict(plain.headers), "Cookie": f"gestnow_projeto={eap.second.id}"},
        params={},
        route_params={},
        body=b"",
    )

    assert _codes(routes.eap_content(request)) == ["0", "1", "1.1", "1.1.1"]


def test_filtros_da_url_chegam_a_arvore(eap: EapCadastro) -> None:
    by_search = _content(projeto=str(eap.first.id), busca="LICENCA")
    by_criterion = _content(projeto=str(eap.first.id), criterio="Etapas")
    by_situation = _content(projeto=str(eap.first.id), situacao="vencido")

    assert _codes(by_search) == ["0", "1", "1.1", "1.1.2"]
    assert _codes(by_criterion) == ["0", "1", "1.1", "1.1.3"]
    assert _codes(by_situation) == ["0", "1", "1.1", "1.1.1"]


def test_filtro_ilegivel_na_url_nao_filtra(eap: EapCadastro) -> None:
    response = _content(
        projeto=str(eap.first.id), nivel="abc", criterio="Invenção", situacao="qualquer"
    )

    assert len(_codes(response)) == 9


def test_nivel_da_url_corta_a_profundidade(eap: EapCadastro) -> None:
    assert _codes(_content(projeto=str(eap.first.id), nivel="1")) == ["0", "1", "2"]
    assert _codes(_content(projeto="portfolio", nivel="1")) == ["0", "1", "2"]


def test_filtro_sem_resultado_e_vazio_por_filtro(eap: EapCadastro) -> None:
    response = _content(projeto=str(eap.first.id), busca="zzz")

    assert _marker(response).attrs["data-resultado"] == "vazio-filtro"


def test_projeto_sem_eap_e_vazio_de_origem(eap: EapCadastro) -> None:
    eap.session.query(EapItem).filter(EapItem.project_id == eap.second.id).delete()

    response = _content(projeto=str(eap.second.id))

    assert _marker(response).attrs["data-resultado"] == "vazio-origem"


def test_sem_o_cabecalho_do_alpine_a_rota_manda_para_o_shell(eap: EapCadastro) -> None:
    response = routes.eap_content(
        _request("/api/planejamento/eap", target=None, projeto=str(eap.first.id))
    )

    assert response.status_code == 302


@pytest.mark.usefixtures("eap")
def test_quem_nao_esta_no_cadastro_recebe_403() -> None:
    assert _content(email="intruso@example.invalid").status_code == 403


def test_visualizador_le_e_fornecedor_e_recusado(eap: EapCadastro) -> None:
    assert _content(email=VIEWER_EMAIL, projeto=str(eap.first.id)).status_code == 200
    assert _content(email=SUPPLIER_EMAIL, projeto=str(eap.first.id)).status_code == 403


# ── O dicionário do pacote ───────────────────────────────────────────────


def _dictionary(
    eap: EapCadastro, code: str, *, email: str = MEMBER_EMAIL, **params: str
) -> func.HttpResponse:
    request = _request(
        "/api/planejamento/eap/pacotes/x/dicionario",
        email=email,
        route={"item_id": str(eap.item(eap.first, code))},
        target="eap-dicionario",
        **params,
    )
    return routes.eap_dictionary(request)


def test_dicionario_traz_a_ficha_as_etapas_e_as_medicoes(eap: EapCadastro) -> None:
    response = _dictionary(eap, "1.1.3", projeto=str(eap.first.id))

    assert response.status_code == 200
    assert find_by_id(_tags(response), "eap-dicionario") is not None
    body = response.get_body().decode()
    for text in (
        "Dicionário da EAP · 1.1.3",
        "Pacote de trabalho",
        "Etapas · Engenharia (documentos)",
        "Entregável de teste",
        "Aceite de teste",
        "Montadora EAP",
        "Maria Membro",
        "Sem vínculo com a EAC",
        "Elaboração",
        "Medições",
        "20/09/2026",
        "Medição de teste.",
        "previsto 20,0% · real 40,0% · desvio +20,0 p.p.",
    ):
        assert text in body


def test_dicionario_de_unidades_mostra_a_quantidade_executada(eap: EapCadastro) -> None:
    body = _dictionary(eap, "1.1.1", projeto=str(eap.first.id)).get_body().decode()

    assert "50 de 100 m³" in body
    assert "Etapas</h3>" not in body


def test_dicionario_do_pacote_de_planejamento_diz_que_nao_mede(eap: EapCadastro) -> None:
    body = _dictionary(eap, "2.1.1", projeto=str(eap.first.id)).get_body().decode()

    assert "Pacote de planejamento (peso reservado, sem medição)" in body
    assert "Nenhuma medição registrada para este pacote." in body


def test_dicionario_no_portfolio_ou_de_outro_projeto_e_403(eap: EapCadastro) -> None:
    assert _dictionary(eap, "1.1.1", projeto="portfolio").status_code == 403
    assert _dictionary(eap, "1.1.1", projeto=str(eap.second.id)).status_code == 403


def test_dicionario_de_area_ou_de_id_ilegivel_e_422(eap: EapCadastro) -> None:
    assert _dictionary(eap, "1.1", projeto=str(eap.first.id)).status_code == 422
    request = _request(
        "/api/planejamento/eap/pacotes/x/dicionario",
        route={"item_id": "abc"},
        target="eap-dicionario",
        projeto=str(eap.first.id),
    )

    assert routes.eap_dictionary(request).status_code == 422


def test_dicionario_e_so_leitura_nao_traz_formulario(eap: EapCadastro) -> None:
    tags = _tags(_dictionary(eap, "1.1.1", projeto=str(eap.first.id)))

    assert not find_all(tags, "form")
    assert not [tag for tag in tags if tag.name in {"input", "textarea", "select"}]


# ── Excel e PDF ──────────────────────────────────────────────────────────


def _sheets(response: func.HttpResponse) -> dict[str, Worksheet]:
    book = load_workbook(BytesIO(response.get_body()))
    return {sheet.title: sheet for sheet in book.worksheets}


def _header_row(sheet: Worksheet) -> tuple[int, list[object]]:
    first_row = int(sheet.auto_filter.ref.split(":")[0].lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
    width = sheet.max_column
    return first_row, [
        sheet.cell(row=first_row, column=column).value for column in range(1, width + 1)
    ]


def _excel(**params: str) -> func.HttpResponse:
    return routes.eap_excel(_request("/api/planejamento/eap/excel", target=None, **params))


def test_excel_do_projeto_tem_as_colunas_da_tela_e_a_arvore_inteira(eap: EapCadastro) -> None:
    response = _excel(projeto=str(eap.first.id))

    assert response.status_code == 200
    sheets = _sheets(response)
    assert list(sheets)[:3] == ["Resumo", TREE_SHEET, "Revisões da EAP"]
    sheet = sheets[TREE_SHEET]
    first_row, header = _header_row(sheet)
    assert header == [
        "Código",
        "Descrição",
        "Critério de medição",
        "Un.",
        "Qtd.",
        "Executado",
        "Peso",
        "Peso no nível acima",
        "Início LB",
        "Término LB",
        "Previsto",
        "Real",
        "Desvio (p.p.)",
        "Item da EAC",
        "Empresa",
        "Responsável",
    ]
    codes = [sheet.cell(row=first_row + offset, column=1).value for offset in range(1, 10)]
    assert codes == ["0", "1", "1.1", "1.1.1", "1.1.2", "1.1.3", "2", "2.1", "2.1.1"]
    column = {name: index + 1 for index, name in enumerate(header)}
    root, foundations = first_row + 1, first_row + 4
    assert sheet.cell(row=root, column=column["Peso"]).value == pytest.approx(1.0)
    assert sheet.cell(row=root, column=column["Real"]).value == pytest.approx(0.59)
    assert sheet.cell(row=root, column=column["Previsto"]).value == pytest.approx(0.62)
    assert sheet.cell(row=foundations, column=column["Critério de medição"]).value == (
        "Unidades (m³)"
    )
    assert sheet.cell(row=foundations, column=column["Término LB"]).value == "01/09/2026 (vencido)"
    assert sheets["Resumo"]["A3"].value == "Escopo: TN-EAP-001 · Fábrica EAP"


def test_excel_traz_as_revisoes_e_os_desdobramentos(eap: EapCadastro) -> None:
    sheets = _sheets(_excel(projeto=str(eap.first.id)))

    revisions = sheets["Revisões da EAP"]
    first_row, header = _header_row(revisions)
    assert header[:3] == ["Revisão", "Data", "Pacotes"]
    assert [revisions.cell(row=first_row + offset, column=1).value for offset in (1, 2)] == [
        "Rev 1",
        "Rev 0",
    ]
    assert revisions.cell(row=first_row + 1, column=3).value == 4
    assert revisions.cell(row=first_row + 1, column=8).value == "Vigente"
    assert len(sheets) == 4


def test_excel_do_portfolio_abre_com_projeto_e_traz_o_peso(eap: EapCadastro) -> None:
    sheets = _sheets(_excel(projeto="portfolio"))

    sheet = sheets[PORTFOLIO_TREE_SHEET]
    first_row, header = _header_row(sheet)
    assert header[0] == "Projeto"
    assert "Peso na carteira" in header
    assert "Peso no projeto" in header
    projects = {sheet.cell(row=first_row + offset, column=1).value for offset in range(2, 7)}
    assert projects == {"TN-EAP-001 · Fábrica EAP", "TN-EAP-002 · Caldeira EAP"}
    weight = sheet.cell(row=first_row + 2, column=header.index("Peso na carteira") + 1).value
    assert weight == pytest.approx(0.5)
    assert len(sheets) == 3  # resumo, estrutura e revisão vigente: a carteira não tem desdobramento
    assert eap.first.code


def test_excel_leva_os_filtros(eap: EapCadastro) -> None:
    sheet = _sheets(_excel(projeto=str(eap.first.id), situacao="planejamento"))[TREE_SHEET]

    first_row, _ = _header_row(sheet)
    codes = [sheet.cell(row=first_row + offset, column=1).value for offset in range(1, 5)]
    assert codes == ["0", "2", "2.1", "2.1.1"]


@pytest.mark.usefixtures("eap")
def test_excel_nao_depende_do_cabecalho_do_alpine_e_recusa_quem_nao_esta_no_cadastro() -> None:
    refused = routes.eap_excel(
        _request("/api/planejamento/eap/excel", email="intruso@example.invalid", target=None)
    )

    assert refused.status_code == 403
    assert refused.headers["Content-Type"].startswith("text/plain")


def test_versao_imprimivel_traz_o_mesmo_conteudo_do_excel(eap: EapCadastro) -> None:
    response = routes.eap_printable(
        _request(
            "/api/planejamento/eap/imprimivel",
            target="folha-impressao",
            projeto=str(eap.first.id),
        )
    )

    assert response.status_code == 200
    body = response.get_body().decode()
    for text in (
        "EAP: estrutura analítica do projeto",
        "Fundações",
        "Unidades (m³)",
        "Revisões da EAP",
        "Desdobramentos da revisão vigente",
        "Avanço físico real",
        "Término vencido",
    ):
        assert text in body
    headers = [tag.clean_text() for tag in find_all(parse_tags(body), "th")]
    assert "Critério de medição" in headers
    assert "Real" in headers
    assert "Responsável" in headers


def test_versao_imprimivel_do_portfolio_abre_cada_tabela_com_projeto(eap: EapCadastro) -> None:
    response = routes.eap_printable(
        _request("/api/planejamento/eap/imprimivel", target="folha-impressao", projeto="portfolio")
    )

    headers = [tag.clean_text() for tag in find_all(_tags(response), "th")]
    assert headers.count("Projeto") == 2
    assert "EAP da carteira: projetos e pacotes principais" in response.get_body().decode()
    assert eap.first.code in response.get_body().decode()
