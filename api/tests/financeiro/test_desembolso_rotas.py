"""Rotas do Cronograma de desembolso (ISSUE-043, HU-091, D12, D14).

Costura HTTP: o handler é chamado com a ``HttpRequest`` que o navegador montaria, como em
``test_contingencia_rotas.py``. A carga de demonstração é a base do escopo, com a âncora mais
cinco dias injetada no relógio: o projeto 1 tem os números do mock (realizado de R$ 28,7 mi,
projeção no término de R$ 45,255 mi e saldo a desembolsar de R$ 16,555 mi, distribuído de out/26
em diante). O fragmento traz os KPIs com o previsto, o gráfico das três séries (com o
``data-dados`` que a biblioteca lê) e a tabela saldo a pagar por mês — no Portfólio com a coluna
Projeto. O Excel e o imprimível levam o mesmo conteúdo, incluindo os números do gráfico; o envio
à tesouraria abre no modal preenchido, registra na trilha como simulado e recusa o e-mail
inválido, o Portfólio e quem não tem escrita.
"""

from __future__ import annotations

import json
from datetime import timedelta
from io import BytesIO
from urllib.parse import unquote, urlencode

import azure.functions as func
import pytest
from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.carga import DEMO_ANCHOR, run_demonstration
from src.core import auth, calendario
from src.core.models import AuditEntry, Notification
from src.modulos.configuracoes.models import Project
from src.modulos.financeiro import routes
from tests.financeiro.conftest import MEMBER_EMAIL, EacScenario
from tests.html_tags import Tag, find_by_id, parse_tags
from tests.identidades import cabecalho_do_principal

ADMIN_EMAIL = "leonardo.gomes@exemplo.com"
VIEWER_EMAIL = "visualizador@cliente.demo"
SUPPLIER_EMAIL = "carlos.nunes@exemplo.com"
PROJECT_CODE = "TN-2026-014"
REFERENCE_DATE = DEMO_ANCHOR + timedelta(days=5)
PATH = "/api/financeiro/desembolso"
SEND_PATH = PATH + "/enviar"
CONTENT_TARGET = "desembolso-conteudo"
MODAL_TARGET = "desembolso-modal"
FOLHA_TARGET = "folha-impressao"

KPI_LABELS = (
    "Realizado até o corte",
    "Saldo a desembolsar",
    "Próximos 3 meses",
    "Mês de corte",
)
SERIES = ["previsto", "realizado", "projetado"]
BALANCE_HEADERS = ("Código", "Descrição", "Saldo a pagar", "out/26", "nov/26")
MONTH_HEADERS = ("Mês", "Previsto", "Realizado", "Projetado")
SALDO = "R$ 16.555.000,00"
CARTEIRA_SALDO = "R$ 33.995.000,00"


@pytest.fixture(autouse=True)
def data_de_referencia(monkeypatch: pytest.MonkeyPatch) -> None:
    """O relógio parado na âncora mais cinco dias: os números do mock não mudam."""
    monkeypatch.setattr(calendario, "today", lambda: REFERENCE_DATE)


@pytest.fixture
def carga(rotas_na_transacao: Session) -> Session:
    """A base de demonstração na transação do teste, com as rotas lendo a mesma sessão."""
    run_demonstration(rotas_na_transacao, reference_date=REFERENCE_DATE)
    return rotas_na_transacao


def _request(
    path: str,
    *,
    email: str = ADMIN_EMAIL,
    form: dict[str, str] | None = None,
    target: str | None = CONTENT_TARGET,
    **params: str,
) -> func.HttpRequest:
    """A request como o navegador a envia; ``target=None`` é um link puro (sem Alpine)."""
    headers = {auth.PRINCIPAL_HEADER: cabecalho_do_principal(email)}
    body = b""
    if form is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        body = urlencode(form).encode()
    if target is not None:
        headers["X-Alpine-Request"] = "true"
        headers["X-Alpine-Target"] = target
    return func.HttpRequest(
        method="POST" if form is not None else "GET",
        url=path,
        headers=headers,
        params=dict(params),
        route_params={},
        body=body,
    )


def _body(response: func.HttpResponse) -> str:
    return response.get_body().decode()


def _tags(response: func.HttpResponse) -> list[Tag]:
    return parse_tags(_body(response))


def _toast(response: func.HttpResponse) -> str:
    return unquote(response.headers["X-TN-Toast"])


def _table_text(response: func.HttpResponse, attr: str) -> str:
    """O texto de dentro da tabela marcada com o atributo (``data-saldo``...)."""
    table = next(tag for tag in _tags(response) if tag.name == "table" and attr in tag.attrs)
    return table.clean_text()


def _headers(response: func.HttpResponse) -> list[str]:
    """O texto de cada cabeçalho de coluna do fragmento."""
    return [tag.clean_text() for tag in _tags(response) if tag.name == "th"]


def _chart(response: func.HttpResponse) -> dict:
    """O ``data-dados`` do gráfico do desembolso, como a biblioteca o lê."""
    (host,) = [
        tag for tag in _tags(response) if tag.attrs.get("data-grafico") == "curva-s-barra-linha"
    ]
    return json.loads(host.attrs["data-dados"])


def _projeto(session: Session) -> Project:
    return session.scalars(select(Project).where(Project.code == PROJECT_CODE)).one()


def _sheets(response: func.HttpResponse) -> dict[str, Worksheet]:
    book = load_workbook(BytesIO(response.get_body()))
    return {sheet.title: sheet for sheet in book.worksheets}


def _header_row(sheet: Worksheet) -> int:
    return int(sheet.auto_filter.ref.split(":")[0].lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))


def _codes(sheet: Worksheet) -> set[str]:
    """Os códigos da primeira coluna de uma folha, sem a linha de totais vazia."""
    header = _header_row(sheet)
    return {
        str(sheet.cell(row=row, column=1).value)
        for row in range(header + 1, sheet.max_row + 1)
        if sheet.cell(row=row, column=1).value
    }


# ── Leitura do fragmento ─────────────────────────────────────────────────


def test_o_cronograma_do_projeto_traz_kpis_grafico_e_tabela(carga: Session) -> None:
    project = _projeto(carga)

    response = routes.desembolso_content(_request(PATH, projeto=str(project.id)))

    assert response.status_code == 200
    body = _body(response)
    assert find_by_id(_tags(response), CONTENT_TARGET) is not None
    assert 'data-situacao="conteudo"' in body
    assert 'data-carteira="nao"' in body
    for rotulo in KPI_LABELS:
        assert rotulo in body
    assert "R$ 28.700.000,00" in body, "o realizado até o corte"
    assert SALDO in body, "o saldo a desembolsar"
    assert "Previsto: R$ 15.297.800,00" in body, "o previsto do saldo"
    assert "63,4% da projeção no término" in body
    assert "Corte em set/26" in body and "pico out/26" in body

    assert 'data-grafico="curva-s-barra-linha"' in body
    dados = _chart(response)
    assert [serie["id"] for serie in dados["series"]] == SERIES
    assert [serie["papel"] for serie in dados["series"]] == [
        "previsto",
        "realizado",
        "tendencia",
    ]
    periodos = dados["periodos"]
    assert len(periodos) == 16, "os meses do mock convertido"
    setembro = next(item for item in periodos if item["ano"] == 2026 and item["mes"] == 9)
    assert setembro["valores"]["realizado"] == 5900.0, "o realizado de set/26 do fechamento"
    assert setembro["valores"]["projetado"] is None, "o projetado só existe depois do corte"
    outubro = next(item for item in periodos if item["ano"] == 2026 and item["mes"] == 10)
    assert outubro["valores"]["previsto"] == 4504.6
    assert outubro["valores"]["realizado"] is None, "depois do corte não há realizado"
    assert outubro["valores"]["projetado"] is not None, "a tendência mensal entra como projetado"

    saldo = _table_text(response, "data-saldo")
    for coluna in BALANCE_HEADERS:
        assert coluna in saldo
    assert SALDO in saldo
    assert "1.1" in saldo and "Projeto básico" in saldo
    assert "Total" in saldo
    assert "Projeto" not in _headers(response), "a coluna Projeto só entra no Portfólio"


@pytest.mark.usefixtures("carga")
def test_a_carteira_traz_a_coluna_projeto_e_soma_os_projetos() -> None:
    response = routes.desembolso_content(_request(PATH, projeto="portfolio"))

    assert response.status_code == 200
    body = _body(response)
    assert 'data-carteira="sim"' in body
    assert "soma dos projetos da carteira" in body
    assert CARTEIRA_SALDO in body, "16,555 + 12,430 + 5,010 mi da carteira"

    saldo = _table_text(response, "data-saldo")
    assert "Projeto" in _headers(response)
    assert "TN-2026-014" in saldo and "TN-2026-021" in saldo and "TN-2026-027" in saldo

    setembro = next(
        item for item in _chart(response)["periodos"] if item["ano"] == 2026 and item["mes"] == 9
    )
    assert setembro["valores"]["realizado"] == 8550.0, (
        "o realizado do mês na carteira: 3.717 - 2.862 mi"
    )


@pytest.mark.usefixtures("carga")
def test_sem_o_cabecalho_do_alpine_o_cronograma_manda_para_o_shell() -> None:
    response = routes.desembolso_content(_request(PATH, target=None, projeto="1"))

    assert response.status_code == 302


def test_o_nivel_do_seletor_filtra_a_tabela(carga: Session) -> None:
    """O "Mostrar até" do protótipo: 1 pacotes, 2 subpacotes (default) e 3 itens."""
    project = _projeto(carga)

    pacotes = routes.desembolso_content(_request(PATH, projeto=str(project.id), nivel="1"))
    subpacotes = routes.desembolso_content(_request(PATH, projeto=str(project.id), nivel="2"))
    itens = routes.desembolso_content(_request(PATH, projeto=str(project.id), nivel="3"))

    for response in (pacotes, subpacotes, itens):
        assert response.status_code == 200
        assert SALDO in _body(response), "os KPIs e o gráfico não mudam com o nível"

    assert "Projeto básico" not in _table_text(pacotes, "data-saldo")
    assert "Projeto básico de processo" not in _table_text(pacotes, "data-saldo")

    assert "Projeto básico" in _table_text(subpacotes, "data-saldo")
    assert "Projeto básico de processo" not in _table_text(subpacotes, "data-saldo")

    assert "Projeto básico de processo" in _table_text(itens, "data-saldo")
    assert "R$ 23.000,00" in _table_text(itens, "data-saldo"), "o saldo do item 1.1.1"


@pytest.mark.parametrize("nivel", ["0", "4", "abc"])
def test_nivel_fora_da_faixa_volta_422(carga: Session, nivel: str) -> None:
    project = _projeto(carga)

    response = routes.desembolso_content(_request(PATH, projeto=str(project.id), nivel=nivel))

    assert response.status_code == 422
    assert "Informe um nível de 1 a 3." in _body(response)


def test_o_excel_e_o_imprimivel_recusam_o_nivel_invalido(carga: Session) -> None:
    project = _projeto(carga)

    excel = routes.desembolso_excel(
        _request(PATH + "/excel", target=None, projeto=str(project.id), nivel="9")
    )
    assert excel.status_code == 422
    assert excel.headers["Content-Type"].startswith("text/plain")
    assert "Informe um nível de 1 a 3." in _body(excel)

    imprimivel = routes.desembolso_printable(
        _request(PATH + "/imprimivel", target=FOLHA_TARGET, projeto=str(project.id), nivel="9")
    )
    assert imprimivel.status_code == 422
    assert "Informe um nível de 1 a 3." in _body(imprimivel)


def test_escopo_sem_curva_mostra_o_vazio_de_origem(cenario: EacScenario) -> None:
    response = routes.desembolso_content(
        _request(PATH, email=MEMBER_EMAIL, projeto=str(cenario.first.id))
    )

    assert response.status_code == 200
    body = _body(response)
    assert 'data-situacao="vazio-origem"' in body
    assert "Este projeto ainda não tem curva financeira cadastrada." in body
    assert "Saldo a desembolsar" not in body


# ── Permissões ───────────────────────────────────────────────────────────


def test_o_visualizador_le_o_cronograma(carga: Session) -> None:
    project = _projeto(carga)

    response = routes.desembolso_content(
        _request(PATH, email=VIEWER_EMAIL, projeto=str(project.id))
    )

    assert response.status_code == 200
    assert "Saldo a desembolsar" in _body(response)


def test_o_fornecedor_nao_le_nem_baixa_o_excel(carga: Session) -> None:
    project = _projeto(carga)

    conteudo = routes.desembolso_content(
        _request(PATH, email=SUPPLIER_EMAIL, projeto=str(project.id))
    )
    assert conteudo.status_code == 403

    excel = routes.desembolso_excel(
        _request(PATH + "/excel", email=SUPPLIER_EMAIL, target=None, projeto=str(project.id))
    )
    assert excel.status_code == 403


# ── Excel e imprimível ───────────────────────────────────────────────────


def test_o_excel_traz_o_resumo_o_mensal_e_a_serie_projetado(carga: Session) -> None:
    project = _projeto(carga)

    response = routes.desembolso_excel(
        _request(PATH + "/excel", target=None, projeto=str(project.id))
    )

    assert response.status_code == 200
    assert response.headers["Content-Disposition"].startswith(
        'attachment; filename="cronograma-de-desembolso-'
    )
    sheets = _sheets(response)
    assert list(sheets) == ["Resumo", "Desembolso mensal", "Saldo a pagar por mês"]

    labels = {
        sheets["Resumo"].cell(row=row, column=1).value
        for row in range(1, sheets["Resumo"].max_row + 1)
    }
    assert set(KPI_LABELS) <= labels

    mensal = sheets["Desembolso mensal"]
    first_row = _header_row(mensal)
    assert [mensal.cell(row=first_row, column=column).value for column in range(1, 5)] == list(
        MONTH_HEADERS
    )
    setembro = first_row + 9
    assert mensal.cell(row=setembro, column=1).value == "set/26"
    assert mensal.cell(row=setembro, column=3).value == 5_900_000.0, "R$ 5,9 mi do realizado"
    assert mensal.cell(row=setembro, column=4).value is None, "sem projetado no corte"
    outubro = setembro + 1
    assert mensal.cell(row=outubro, column=3).value is None, "sem realizado depois do corte"
    assert mensal.cell(row=outubro, column=4).value is not None, "a série Projetado do mês"

    saldo = sheets["Saldo a pagar por mês"]
    header = _header_row(saldo)
    assert [saldo.cell(row=header, column=column).value for column in range(1, 6)] == list(
        BALANCE_HEADERS
    )
    assert saldo.cell(row=header + 1, column=3).value == 855_000.0, "o pacote 1 da EAC"
    assert saldo.cell(row=saldo.max_row, column=3).value == 16_555_000.0, SALDO


@pytest.mark.usefixtures("carga")
def test_o_excel_da_carteira_traz_a_coluna_projeto() -> None:
    response = routes.desembolso_excel(_request(PATH + "/excel", target=None, projeto="portfolio"))

    sheets = _sheets(response)
    saldo = sheets["Saldo a pagar por mês"]
    header = _header_row(saldo)
    assert saldo.cell(row=header, column=1).value == "Projeto"
    codes = {saldo.cell(row=row, column=1).value for row in range(header + 1, saldo.max_row + 1)}
    assert any(str(code).startswith("TN-2026-014 · ") for code in codes)


def test_o_excel_respeita_o_nivel(carga: Session) -> None:
    project = _projeto(carga)

    pacotes = _sheets(
        routes.desembolso_excel(
            _request(PATH + "/excel", target=None, projeto=str(project.id), nivel="1")
        )
    )
    codes = _codes(pacotes["Saldo a pagar por mês"])
    assert "1" in codes and all("." not in code for code in codes)

    itens = _sheets(
        routes.desembolso_excel(
            _request(PATH + "/excel", target=None, projeto=str(project.id), nivel="3")
        )
    )
    assert "1.1.1" in _codes(itens["Saldo a pagar por mês"])


def test_o_imprimivel_respeita_o_nivel(carga: Session) -> None:
    project = _projeto(carga)

    response = routes.desembolso_printable(
        _request(PATH + "/imprimivel", target=FOLHA_TARGET, projeto=str(project.id), nivel="1")
    )

    assert response.status_code == 200
    body = _body(response)
    assert "Saldo a pagar por mês" in body
    assert "Projeto básico" not in body, "com o nível 1, os subpacotes ficam fora"


def test_o_imprimivel_traz_o_mesmo_conteudo_do_excel(carga: Session) -> None:
    project = _projeto(carga)

    response = routes.desembolso_printable(
        _request(PATH + "/imprimivel", target=FOLHA_TARGET, projeto=str(project.id))
    )

    assert response.status_code == 200
    body = _body(response)
    for texto in (
        "Cronograma de desembolso",
        *KPI_LABELS,
        "Desembolso mensal",
        "Saldo a pagar por mês",
        SALDO,
    ):
        assert texto in body
    assert 'data-grafico="curva-s-barra-linha"' in body


# ── Envio à tesouraria ───────────────────────────────────────────────────


def test_o_formulario_de_envio_vem_preenchido_do_cronograma(carga: Session) -> None:
    project = _projeto(carga)

    response = routes.desembolso_envio_form(
        _request(SEND_PATH, target=MODAL_TARGET, projeto=str(project.id))
    )

    assert response.status_code == 200
    body = _body(response)
    assert find_by_id(_tags(response), MODAL_TARGET) is not None
    assert 'name="para"' in body and 'value="tesouraria@exemplo.com"' in body
    assert 'name="mensagem"' in body
    assert (
        f"Cronograma de desembolso atualizado com o fechamento de set/26. Saldo a desembolsar: {SALDO}."
        in body
    )
    assert 'action="/api/financeiro/desembolso/enviar"' in body


def test_o_envio_registra_na_trilha_com_simulado_e_o_toast(carga: Session) -> None:
    project = _projeto(carga)

    response = routes.desembolso_envio_send(
        _request(
            SEND_PATH,
            form={"para": "tesouraria@exemplo.com", "mensagem": ""},
            target=MODAL_TARGET,
            projeto=str(project.id),
        )
    )

    assert response.status_code == 200
    assert response.headers["X-TN-Toast-Tipo"] == "aviso"
    assert _toast(response) == "Cronograma enviado para tesouraria@exemplo.com (envio simulado)."
    body = _body(response)
    assert "aviso--warn" in body
    assert "simulado" in body
    assert find_by_id(_tags(response), MODAL_TARGET) is not None

    registro = carga.scalars(select(Notification)).one()
    assert registro.kind == "tesouraria"
    assert registro.project_id == project.id
    assert registro.recipients == "tesouraria@exemplo.com"
    assert registro.body == (
        f"Cronograma de desembolso atualizado com o fechamento de set/26. "
        f"Saldo a desembolsar: {SALDO}."
    )
    linha = carga.scalars(
        select(AuditEntry).where(
            AuditEntry.entity == "notificacao", AuditEntry.record_id == registro.id
        )
    ).one()
    assert linha.after is not None and linha.after["situacao"] == "simulado"


def test_o_envio_usa_o_destinatario_e_a_mensagem_do_formulario(carga: Session) -> None:
    project = _projeto(carga)

    response = routes.desembolso_envio_send(
        _request(
            SEND_PATH,
            form={"para": "financeiro@cliente.exemplo", "mensagem": "Segue o cronograma revisado."},
            target=MODAL_TARGET,
            projeto=str(project.id),
        )
    )

    assert response.status_code == 200
    assert (
        _toast(response) == "Cronograma enviado para financeiro@cliente.exemplo (envio simulado)."
    )
    registro = carga.scalars(select(Notification)).one()
    assert registro.recipients == "financeiro@cliente.exemplo"
    assert registro.body == "Segue o cronograma revisado."


def test_o_envio_com_email_invalido_volta_422_e_nada_grava(carga: Session) -> None:
    project = _projeto(carga)

    response = routes.desembolso_envio_send(
        _request(
            SEND_PATH,
            form={"para": "sem-arroba", "mensagem": ""},
            target=MODAL_TARGET,
            projeto=str(project.id),
        )
    )

    assert response.status_code == 422
    assert response.headers["X-TN-Toast-Tipo"] == "erro"
    assert "Informe um e-mail válido." in _body(response)
    assert carga.scalars(select(Notification)).all() == []


def test_o_envio_no_portfolio_e_recusado(carga: Session) -> None:
    response = routes.desembolso_envio_send(
        _request(
            SEND_PATH,
            form={"para": "tesouraria@exemplo.com", "mensagem": ""},
            target=MODAL_TARGET,
            projeto="portfolio",
        )
    )

    assert response.status_code == 422
    assert "Escolha um projeto" in _body(response)
    assert carga.scalars(select(Notification)).all() == []


def test_o_envio_sem_cronograma_e_recusado(cenario: EacScenario) -> None:
    response = routes.desembolso_envio_form(
        _request(SEND_PATH, email=MEMBER_EMAIL, target=MODAL_TARGET, projeto=str(cenario.first.id))
    )

    assert response.status_code == 422
    assert "não tem cronograma de desembolso para enviar" in _body(response)


def test_o_visualizador_nao_envia(carga: Session) -> None:
    project = _projeto(carga)

    response = routes.desembolso_envio_send(
        _request(
            SEND_PATH,
            email=VIEWER_EMAIL,
            form={"para": "tesouraria@exemplo.com", "mensagem": ""},
            target=MODAL_TARGET,
            projeto=str(project.id),
        )
    )

    assert response.status_code == 403
    assert carga.scalars(select(Notification)).all() == []
