"""Escopo (ISSUE-009, D8): Portfólio ou projeto, resolvido por requisição.

A URL vence o cookie e o Portfólio é o padrão. Valor que não nomeia um projeto
existente não é aceito em silêncio: a resolução cai na fonte seguinte e o texto
recusado volta no ``Scope`` para a tela avisar. A rota ``/api/nav`` grava o
cookie, e ``/api/escopo/projetos`` é a escolha de projeto do mecanismo de
inclusão: cada projeto é um link que reabre a tela com ``?acao=``.
"""

from __future__ import annotations

import azure.functions as func
import pytest
from sqlalchemy.orm import Session

from src.blueprints.nav import choose_project, main_nav
from src.core import scope
from src.core.errors import InvalidDataError
from src.modulos.configuracoes.models import Project
from tests.html_tags import find_all, parse_tags

PROJETOS_VALIDOS = {1, 2, 3}


def _req(
    *, projeto: str | None = None, cookie: str | None = None, url: str = "/api/nav"
) -> func.HttpRequest:
    headers = {"Cookie": cookie} if cookie is not None else {}
    params = {"projeto": projeto} if projeto is not None else {}
    return func.HttpRequest(
        method="GET", url=url, headers=headers, params=params, route_params={}, body=b""
    )


# ── Resolução: URL, cookie e padrão ──────────────────────────────────────


def test_url_com_projeto_define_o_escopo() -> None:
    escopo = scope.resolve_scope(_req(projeto="2"), PROJETOS_VALIDOS)

    assert (escopo.project_id, escopo.source, escopo.rejected) == (2, "url", None)
    assert not escopo.is_portfolio
    assert escopo.parameter == "2"


def test_url_com_portfolio_define_o_portfolio() -> None:
    escopo = scope.resolve_scope(_req(projeto="portfolio"), PROJETOS_VALIDOS)

    assert (escopo.project_id, escopo.source) == (None, "url")
    assert escopo.is_portfolio
    assert escopo.parameter == "portfolio"


def test_sem_url_vale_o_cookie() -> None:
    escopo = scope.resolve_scope(_req(cookie="gestnow_projeto=3"), PROJETOS_VALIDOS)

    assert (escopo.project_id, escopo.source) == (3, "cookie")


def test_a_url_vence_o_cookie() -> None:
    escopo = scope.resolve_scope(_req(projeto="1", cookie="gestnow_projeto=3"), PROJETOS_VALIDOS)

    assert (escopo.project_id, escopo.source) == (1, "url")


def test_sem_url_nem_cookie_o_padrao_e_o_portfolio() -> None:
    escopo = scope.resolve_scope(_req(), PROJETOS_VALIDOS)

    assert (escopo.project_id, escopo.source, escopo.rejected) == (None, "padrao", None)


def test_cookie_do_escopo_e_lido_no_meio_de_outros_cookies() -> None:
    cabecalho = "tema=claro; gestnow_projeto=2; outro=x"

    escopo = scope.resolve_scope(_req(cookie=cabecalho), PROJETOS_VALIDOS)

    assert (escopo.project_id, escopo.source) == (2, "cookie")


def test_portfolio_aceita_qualquer_caixa_e_espacos() -> None:
    escopo = scope.resolve_scope(_req(projeto="  PortFolio "), PROJETOS_VALIDOS)

    assert escopo.is_portfolio
    assert escopo.source == "url"


@pytest.mark.parametrize("valor", ["99", "abc", "-1", "1.5", "1e3", "٣", "9" * 40])
def test_url_com_projeto_inexistente_ou_invalido_cai_no_cookie_e_guarda_o_texto(
    valor: str,
) -> None:
    escopo = scope.resolve_scope(_req(projeto=valor, cookie="gestnow_projeto=2"), PROJETOS_VALIDOS)

    assert (escopo.project_id, escopo.source) == (2, "cookie")
    assert escopo.rejected == valor


def test_url_e_cookie_invalidos_caem_no_portfolio() -> None:
    escopo = scope.resolve_scope(
        _req(projeto="99", cookie="gestnow_projeto=lixo"), PROJETOS_VALIDOS
    )

    assert (escopo.project_id, escopo.source) == (None, "padrao")
    assert escopo.rejected == "99"


# ── Entrega às fachadas ──────────────────────────────────────────────────


def test_registro_exige_projeto_e_no_portfolio_a_fachada_recusa() -> None:
    no_portfolio = scope.Scope(project_id=None, source="padrao")
    no_projeto = scope.Scope(project_id=5, source="url")

    assert no_projeto.require_project() == 5
    with pytest.raises(InvalidDataError, match="projeto"):
        no_portfolio.require_project()


def test_scope_of_confere_o_projeto_no_cadastro(
    dois_projetos: tuple[Project, Project], rotas_na_transacao_do_teste: Session
) -> None:
    fabrica, _ = dois_projetos

    existente = scope.scope_of(rotas_na_transacao_do_teste, _req(projeto=str(fabrica.id)))
    inexistente = scope.scope_of(rotas_na_transacao_do_teste, _req(projeto="99999999"))

    assert existente.project_id == fabrica.id
    assert inexistente.is_portfolio
    assert inexistente.rejected == "99999999"


# ── O cookie ─────────────────────────────────────────────────────────────


def test_cookie_lembra_o_escopo_sem_expor_ao_javascript() -> None:
    cabecalho = scope.cookie_header(scope.Scope(project_id=2, source="url"), secure=False)

    atributos = cabecalho.split("; ")
    assert atributos[0] == "gestnow_projeto=2"
    assert {"Path=/", "SameSite=Lax", "HttpOnly"} <= set(atributos)
    assert "Secure" not in atributos


def test_cookie_do_portfolio_e_seguro_em_https() -> None:
    cabecalho = scope.cookie_header(scope.Scope(project_id=None, source="padrao"), secure=True)

    assert cabecalho.startswith("gestnow_projeto=portfolio; ")
    assert "Secure" in cabecalho.split("; ")


def test_https_vem_do_cabecalho_do_proxy_ou_da_url() -> None:
    assert scope.is_secure_request(
        func.HttpRequest(
            method="GET",
            url="/api/nav",
            headers={"X-Forwarded-Proto": "https, http"},
            params={},
            body=b"",
        )
    )
    assert scope.is_secure_request(_req(url="https://gestnow.example.invalid/api/nav"))
    assert not scope.is_secure_request(_req(url="http://localhost:4280/api/nav"))


# ── /api/nav: URL, cookie e padrão chegam à barra lateral ────────────────


def _nav(*, projeto: str | None = None, cookie: str | None = None) -> func.HttpResponse:
    headers = {"X-Alpine-Request": "true", "X-Alpine-Target": "main-nav module-tabs"}
    if cookie is not None:
        headers["Cookie"] = cookie
    params = {"caminho": "/"}
    if projeto is not None:
        params["projeto"] = projeto
    return main_nav(
        func.HttpRequest(
            method="GET", url="/api/nav", headers=headers, params=params, route_params={}, body=b""
        )
    )


def _escolhido(resposta: func.HttpResponse) -> list[str]:
    tags = parse_tags(resposta.get_body().decode())
    return [t.attrs["value"] for t in tags if t.name == "option" and "selected" in t.attrs]


def test_nav_resolve_o_escopo_pela_url_e_grava_o_cookie(
    dois_projetos: tuple[Project, Project],
) -> None:
    fabrica, _ = dois_projetos

    resposta = _nav(projeto=str(fabrica.id), cookie="gestnow_projeto=portfolio")

    assert _escolhido(resposta) == [str(fabrica.id)]
    cookie = resposta.headers.get("Set-Cookie")
    assert cookie is not None
    assert cookie.startswith(f"gestnow_projeto={fabrica.id}; ")
    assert resposta.headers.get("X-TN-Toast") is None


def test_nav_resolve_o_escopo_pelo_cookie_quando_a_url_nao_traz(
    dois_projetos: tuple[Project, Project],
) -> None:
    _, caldeira = dois_projetos

    resposta = _nav(cookie=f"gestnow_projeto={caldeira.id}")

    assert _escolhido(resposta) == [str(caldeira.id)]
    assert (resposta.headers.get("Set-Cookie") or "").startswith(f"gestnow_projeto={caldeira.id}")


@pytest.mark.usefixtures("rotas_na_transacao_do_teste")
def test_nav_sem_url_nem_cookie_abre_no_portfolio() -> None:
    resposta = _nav()

    assert _escolhido(resposta) == ["portfolio"]
    assert (resposta.headers.get("Set-Cookie") or "").startswith("gestnow_projeto=portfolio; ")


@pytest.mark.usefixtures("rotas_na_transacao_do_teste")
def test_nav_com_projeto_inexistente_mostra_o_portfolio_e_avisa() -> None:
    resposta = _nav(projeto="99999999")

    assert _escolhido(resposta) == ["portfolio"]
    assert resposta.headers.get("X-TN-Toast-Tipo") == "aviso"
    assert resposta.headers.get("X-TN-Toast")


# ── /api/escopo/projetos: a escolha da inclusão no Portfólio ─────────────


def _escolha(**params: str) -> func.HttpResponse:
    return choose_project(
        func.HttpRequest(
            method="GET",
            url="/api/escopo/projetos",
            headers={"X-Alpine-Request": "true", "X-Alpine-Target": "escopo-escolha"},
            params=params,
            route_params={},
            body=b"",
        )
    )


def test_escolha_de_projeto_reabre_a_tela_no_projeto_com_a_acao(
    dois_projetos: tuple[Project, Project],
) -> None:
    fabrica, caldeira = dois_projetos

    resposta = _escolha(caminho="/central-acoes/acoes", acao="nova")

    assert resposta.status_code == 200
    tags = parse_tags(resposta.get_body().decode())
    links = {t.attrs["href"] for t in find_all(tags, "a", "escopo-escolha__link")}
    assert f"/central-acoes/acoes?projeto={fabrica.id}&acao=nova" in links
    assert f"/central-acoes/acoes?projeto={caldeira.id}&acao=nova" in links
    assert all("data-tn-tela" in t.attrs for t in find_all(tags, "a", "escopo-escolha__link"))


def test_escolha_de_projeto_descarta_acao_que_nao_e_um_nome_simples(
    dois_projetos: tuple[Project, Project],
) -> None:
    fabrica, _ = dois_projetos

    resposta = _escolha(caminho="/central-acoes/acoes", acao='nova"><script>')

    corpo = resposta.get_body().decode()
    assert f"/central-acoes/acoes?projeto={fabrica.id}" in corpo
    assert "acao=" not in corpo
    assert "<script>" not in corpo


@pytest.mark.usefixtures("rotas_na_transacao_do_teste")
def test_escolha_de_projeto_com_tela_desconhecida_volta_ao_inicio(
    dois_projetos: tuple[Project, Project],
) -> None:
    fabrica, _ = dois_projetos

    resposta = _escolha(caminho="/nada/aqui", acao="nova")

    assert f'href="/?projeto={fabrica.id}&amp;acao=nova"' in resposta.get_body().decode()
