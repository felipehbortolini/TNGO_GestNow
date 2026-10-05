"""Rotas do acesso (ISSUE-011): gate, perfis e vínculo na barra lateral e nas rotas.

Costura HTTP: o handler é chamado com a ``HttpRequest`` montada no teste, com o
cabeçalho do principal simulado (``x-ms-client-principal``) ou, na demonstração,
com o cookie do seletor de perfil. Afirma o que a pessoa vê: o status (200, 302,
403, 422), o que a barra lateral lista, para onde o shell é mandado e o que a
tela de acesso negado diz. O teste transversal de vínculo da spec está no fim.
"""

from __future__ import annotations

import html
import inspect
from collections.abc import Callable

import azure.functions as func
import pytest
from sqlalchemy.orm import Session

from src.blueprints.acesso import denied_screen, switch_demo_profile
from src.blueprints.nav import choose_project, glossary, main_nav
from src.core import auth, config, rbac, routing
from src.core.rbac import Permission, ScheduleRole
from src.core.routing import OPEN, Access, RequestContext, fragment_route
from src.modulos.configuracoes.models import Project
from tests.html_tags import find_all, find_by_id, parse_tags
from tests.identidades import (
    criar_colaborador,
    criar_empresa,
    criar_projeto,
    requisicao,
)

TODOS_OS_MODULOS = [
    "inicio",
    "central_acoes",
    "planejamento",
    "programacao_semanal",
    "financeiro",
    "suprimentos",
    "riscos",
    "qualidade",
    "hse",
    "governanca",
    "configuracoes",
    "relatorio",
]
ABAS_DA_PROGRAMACAO = ["Programação", "Dashboard", "Governança", "Importação", "Configuração"]
RAIZ_DE_TELA = "app-shell"


def _nav(
    caminho: str = "/",
    *,
    email: str | None = None,
    cookies: dict[str, str] | None = None,
) -> func.HttpResponse:
    return main_nav(
        requisicao(
            "/api/nav",
            email=email,
            cookies=cookies,
            params={"caminho": caminho, "projeto": "portfolio"},
        )
    )


def _negado(
    caminho: str | None = None,
    *,
    email: str | None = None,
    cookies: dict[str, str] | None = None,
) -> func.HttpResponse:
    params = {"caminho": caminho} if caminho is not None else {}
    return denied_screen(
        requisicao(
            "/api/acesso-negado",
            email=email,
            cookies=cookies,
            alvo=RAIZ_DE_TELA,
            params=params,
        )
    )


def _corpo(resposta: func.HttpResponse) -> str:
    """The body as a person reads it: with the HTML entities of the autoescape undone."""
    return html.unescape(resposta.get_body().decode())


def _itens(resposta: func.HttpResponse) -> list[str]:
    tags = parse_tags(resposta.get_body().decode())
    return [item.attrs["aria-label"] for item in find_all(tags, "a", "sidebar__item")]


def _abas(resposta: func.HttpResponse) -> list[str]:
    tags = parse_tags(resposta.get_body().decode())
    return [aba.clean_text() for aba in find_all(tags, "a", "tab") if "data-tn-tela" in aba.attrs]


@pytest.fixture
def fornecedor(sessao_das_rotas: Session) -> str:
    """A supplier with a company: returns its e-mail, which is the principal of the tests."""
    empresa = criar_empresa(sessao_das_rotas, "Contratada Alfa")
    criar_colaborador(
        sessao_das_rotas,
        email="fabio.fornecedor@example.invalid",
        nome="Fábio Fornecedor",
        perfil="Membro",
        vinculo="Fornecedor",
        empresa=empresa,
    )
    return "fabio.fornecedor@example.invalid"


# ── Entrar: o cadastro de Colaboradores decide ───────────────────────────


def test_email_cadastrado_entra_e_ve_os_modulos_do_perfil(sessao_das_rotas: Session) -> None:
    criar_colaborador(sessao_das_rotas, email="gestor@example.invalid", perfil="Gestor")

    resposta = _nav(email="gestor@example.invalid")

    assert resposta.status_code == 200
    assert _itens(resposta) == [
        "Início",
        "01 Central de Ações",
        "02 Planejamento",
        "03 Gestão Financeira",
        "04 Suprimentos",
        "05 Gestão de Riscos",
        "06 Gestão da Qualidade",
        "07 HSE",
        "08 Governança",
        "Configurações",
    ]


@pytest.mark.usefixtures("sessao_das_rotas")
def test_email_fora_do_cadastro_ve_o_acesso_negado_com_a_orientacao() -> None:
    resposta = _negado(email="intruso@example.invalid")

    assert resposta.status_code == 403
    corpo = _corpo(resposta)
    tags = parse_tags(resposta.get_body().decode())
    raiz = find_by_id(tags, RAIZ_DE_TELA)
    assert raiz is not None
    assert raiz.name == "main"
    assert raiz.has_class("content")
    assert len(find_all(tags, "div", "guard")) == 1
    assert auth.NOT_REGISTERED_MESSAGE in corpo
    assert auth.ORIENTATION in corpo
    assert "administrador do GestNow" in corpo
    assert "intruso@example.invalid" in corpo


@pytest.mark.usefixtures("sessao_das_rotas")
def test_nav_de_email_fora_do_cadastro_devolve_403_e_uma_barra_minima() -> None:
    resposta = _nav(email="intruso@example.invalid")

    assert resposta.status_code == 403
    tags = parse_tags(resposta.get_body().decode())
    barra = find_by_id(tags, "main-nav")
    abas = find_by_id(tags, "module-tabs")
    # Os dois alvos que o shell pediu voltam, para nenhum ficar vazio.
    assert barra is not None
    assert abas is not None
    assert "hidden" in abas.attrs
    assert barra.attrs["data-tela"] == "/api/acesso-negado"
    assert find_all(tags, "a", "sidebar__item") == []
    assert "intruso@example.invalid" in resposta.get_body().decode()


def test_colaborador_desativado_ve_o_acesso_negado_que_diz_que_o_acesso_foi_desativado(
    sessao_das_rotas: Session,
) -> None:
    criar_colaborador(sessao_das_rotas, email="desligado@example.invalid", ativo=False)

    resposta = _negado(email="desligado@example.invalid")

    assert resposta.status_code == 403
    assert auth.INACTIVE_MESSAGE in _corpo(resposta)
    assert auth.ORIENTATION in _corpo(resposta)


@pytest.mark.usefixtures("sessao_das_rotas")
def test_sem_identidade_em_producao_a_rota_pede_o_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(config.APP_MODE_VARIABLE, config.PRODUCTION)

    nav = _nav()
    guarda = _negado()

    assert nav.status_code == 403
    assert guarda.status_code == 403
    assert auth.SIGN_IN_MESSAGE in _corpo(guarda)
    assert 'href="/.auth/login/aad"' in _corpo(guarda)


def test_principal_malformado_nao_entra(sessao_das_rotas: Session) -> None:
    criar_colaborador(sessao_das_rotas, email="admin@example.invalid", perfil="Admin")

    resposta = main_nav(requisicao("/api/nav", cabecalho_bruto="%%%", params={"caminho": "/"}))

    assert resposta.status_code == 403


@pytest.mark.parametrize("rota", [choose_project, glossary])
def test_rotas_do_shell_pedem_so_identidade_e_recusam_quem_nao_esta_no_cadastro(
    sessao_das_rotas: Session, rota: Callable[[func.HttpRequest], func.HttpResponse]
) -> None:
    criar_colaborador(
        sessao_das_rotas, email="cliente@example.invalid", perfil="Visualizador", vinculo="Cliente"
    )

    de_fora = rota(requisicao("/api/x", email="intruso@example.invalid", alvo="x"))
    de_dentro = rota(requisicao("/api/x", email="cliente@example.invalid", alvo="x"))

    assert de_fora.status_code == 403
    assert de_dentro.status_code == 200


def test_cartao_do_usuario_traz_nome_perfil_e_vinculo_do_cadastro(
    sessao_das_rotas: Session,
) -> None:
    criar_colaborador(
        sessao_das_rotas,
        email="gestor@example.invalid",
        nome="Gil Gestor",
        perfil="Gestor",
        vinculo="Cliente",
    )

    tags = parse_tags(_nav(email="gestor@example.invalid").get_body().decode())

    assert [t.clean_text() for t in find_all(tags, "div", "userchip__name")] == ["Gil Gestor"]
    funcao = find_all(tags, "div", "userchip__role")
    assert [t.clean_text() for t in funcao] == ["Gestor · Cliente"]
    assert funcao[0].attrs["title"] == "gestor@example.invalid"
    assert [t.clean_text() for t in find_all(tags, "div", "avatar")] == ["GG"]
    sair = [t for t in find_all(tags, "a", "iconbtn") if t.attrs.get("aria-label") == "Sair"]
    assert [t.attrs["href"] for t in sair] == ["/.auth/logout"]


# ── Demonstração: o seletor de perfil troca a pessoa ─────────────────────


def test_em_demonstracao_o_seletor_troca_a_pessoa_e_a_tela_reflete_o_perfil(
    sessao_das_rotas: Session,
) -> None:
    criar_colaborador(sessao_das_rotas, email="admin@example.invalid", perfil="Admin")
    cliente = criar_colaborador(
        sessao_das_rotas,
        email="cliente@example.invalid",
        nome="Clara Cliente",
        perfil="Visualizador",
        vinculo="Cliente",
    )
    antes = _nav()
    assert "Configurações" in _itens(antes)

    troca = switch_demo_profile(
        requisicao(
            "/api/demonstracao/perfil",
            metodo="POST",
            corpo={"colaborador": str(cliente.id)},
        )
    )

    assert troca.status_code == 200
    assert (troca.headers.get("Set-Cookie") or "").startswith(f"gestnow_demo_perfil={cliente.id}; ")
    depois = _nav(cookies={auth.DEMO_COOKIE: str(cliente.id)})
    assert "Configurações" not in _itens(depois)
    tags = parse_tags(depois.get_body().decode())
    assert [t.clean_text() for t in find_all(tags, "div", "userchip__name")] == ["Clara Cliente"]
    assert [t.clean_text() for t in find_all(tags, "div", "userchip__role")] == [
        "Visualizador · Cliente"
    ]


def test_nav_em_demonstracao_traz_o_seletor_com_a_pessoa_atual(sessao_das_rotas: Session) -> None:
    admin = criar_colaborador(sessao_das_rotas, email="admin@example.invalid", perfil="Admin")
    outra = criar_colaborador(sessao_das_rotas, email="outra@example.invalid", nome="Olga Outra")

    tags = parse_tags(_nav(cookies={auth.DEMO_COOKIE: str(outra.id)}).get_body().decode())

    seletor = find_by_id(tags, "perfil-seletor")
    assert seletor is not None
    assert seletor.attrs["data-atual"] == str(outra.id)
    valores = [t.attrs["value"] for t in tags if t.name == "option"]
    assert str(admin.id) in valores
    assert str(outra.id) in valores
    # Só o seletor de escopo marca opção no fragmento: o de perfil usa data-atual.
    marcadas = [t for t in tags if t.name == "option" and "selected" in t.attrs]
    assert [t.attrs["value"] for t in marcadas] == ["portfolio"]


def test_nav_com_login_microsoft_nao_traz_o_seletor_de_perfil(sessao_das_rotas: Session) -> None:
    criar_colaborador(sessao_das_rotas, email="gestor@example.invalid", perfil="Gestor")

    tags = parse_tags(_nav(email="gestor@example.invalid").get_body().decode())

    assert find_by_id(tags, "perfil-seletor") is None


def test_nav_em_producao_nao_traz_o_seletor_de_perfil(
    sessao_das_rotas: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(config.APP_MODE_VARIABLE, config.PRODUCTION)
    criar_colaborador(sessao_das_rotas, email="gestor@example.invalid", perfil="Gestor")

    tags = parse_tags(_nav(email="gestor@example.invalid").get_body().decode())

    assert find_by_id(tags, "perfil-seletor") is None


def _trocar(corpo: dict[str, str], *, email: str | None = None) -> func.HttpResponse:
    return switch_demo_profile(
        requisicao("/api/demonstracao/perfil", metodo="POST", email=email, corpo=corpo)
    )


def test_troca_de_perfil_para_quem_nao_esta_no_cadastro_e_recusada_com_422(
    sessao_das_rotas: Session,
) -> None:
    desligado = criar_colaborador(sessao_das_rotas, email="desligado@example.invalid", ativo=False)

    for invalida in (str(desligado.id), "99999999", "abc", ""):
        resposta = _trocar({"colaborador": invalida})

        assert resposta.status_code == 422
        assert auth.DEMO_CHOICE_MESSAGE in resposta.get_body().decode()
        assert resposta.headers.get("Set-Cookie") is None


def test_troca_de_perfil_e_recusada_em_producao(
    sessao_das_rotas: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    pessoa = criar_colaborador(sessao_das_rotas, email="pessoa@example.invalid")
    monkeypatch.setenv(config.APP_MODE_VARIABLE, config.PRODUCTION)

    resposta = _trocar({"colaborador": str(pessoa.id)})

    assert resposta.status_code == 403
    assert resposta.headers.get("Set-Cookie") is None


def test_troca_de_perfil_e_recusada_com_login_microsoft(sessao_das_rotas: Session) -> None:
    pessoa = criar_colaborador(sessao_das_rotas, email="pessoa@example.invalid")

    resposta = _trocar({"colaborador": str(pessoa.id)}, email="pessoa@example.invalid")

    assert resposta.status_code == 403
    assert resposta.headers.get("Set-Cookie") is None


def test_troca_de_perfil_sem_o_cabecalho_do_alpine_redireciona_para_o_shell() -> None:
    req = func.HttpRequest(
        method="POST", url="/api/demonstracao/perfil", headers={}, params={}, body=b""
    )

    resposta = switch_demo_profile(req)

    assert resposta.status_code == 302
    assert resposta.headers.get("Location") == "/index.html"


# ── Perfil geral: o que a barra lateral mostra ───────────────────────────


@pytest.mark.parametrize(
    ("perfil", "aparece"),
    [("Visualizador", False), ("Membro", False), ("Gestor", True), ("Admin", True)],
)
def test_configuracoes_aparece_so_para_gestor_e_admin(
    sessao_das_rotas: Session, perfil: str, *, aparece: bool
) -> None:
    criar_colaborador(sessao_das_rotas, email="pessoa@example.invalid", perfil=perfil)

    itens = _itens(_nav(email="pessoa@example.invalid"))

    assert ("Configurações" in itens) is aparece
    assert len(itens) == (10 if aparece else 9)


def test_gestor_ve_parametros_e_cadastros_e_o_admin_ve_tambem_colaboradores(
    sessao_das_rotas: Session,
) -> None:
    criar_colaborador(sessao_das_rotas, email="gestor@example.invalid", perfil="Gestor")
    criar_colaborador(sessao_das_rotas, email="admin@example.invalid", perfil="Admin")

    do_gestor = _abas(_nav("/configuracoes/parametros", email="gestor@example.invalid"))
    do_admin = _abas(_nav("/configuracoes/parametros", email="admin@example.invalid"))

    assert do_gestor == ["Parâmetros", "Cadastros"]
    assert do_admin == ["Parâmetros", "Colaboradores", "Cadastros"]


def test_tela_fora_do_perfil_abre_o_acesso_negado_no_lugar_da_tela(
    sessao_das_rotas: Session,
) -> None:
    criar_colaborador(sessao_das_rotas, email="membro@example.invalid", perfil="Membro")

    resposta = _nav("/configuracoes/parametros", email="membro@example.invalid")

    assert resposta.status_code == 200
    tags = parse_tags(resposta.get_body().decode())
    barra = find_by_id(tags, "main-nav")
    assert barra is not None
    assert barra.attrs["data-tela"] == "/api/acesso-negado?caminho=/configuracoes/parametros"
    assert barra.attrs["data-caminho"] == "/configuracoes/parametros"
    assert barra.attrs["data-titulo"] == "Acesso negado · Timenow GestNow"
    assert not any(item.has_class("is-active") for item in find_all(tags, "a", "sidebar__item"))
    abas = find_by_id(tags, "module-tabs")
    assert abas is not None
    assert "hidden" in abas.attrs

    guarda = _negado("/configuracoes/parametros", email="membro@example.invalid")

    assert guarda.status_code == 403
    assert "A tela «Parâmetros do sistema» exige o perfil Gestor ou Admin." in _corpo(guarda)
    assert "O seu perfil é Membro." in _corpo(guarda)


def test_o_acesso_negado_de_tela_permitida_manda_para_a_tela(sessao_das_rotas: Session) -> None:
    criar_colaborador(sessao_das_rotas, email="gestor@example.invalid", perfil="Gestor")

    resposta = _negado("/configuracoes/parametros", email="gestor@example.invalid")

    assert resposta.status_code == 302
    assert resposta.headers.get("Location") == "/configuracoes/parametros?projeto=portfolio"


def test_o_acesso_negado_de_endereco_desconhecido_volta_ao_inicio(
    sessao_das_rotas: Session,
) -> None:
    criar_colaborador(sessao_das_rotas, email="gestor@example.invalid", perfil="Gestor")

    resposta = _negado("/nada/aqui", email="gestor@example.invalid")

    assert resposta.status_code == 302
    assert resposta.headers.get("Location") == "/"


# ── Vínculo: o que o fornecedor vê na barra lateral ──────────────────────


def test_fornecedor_ve_so_a_programacao_semanal_na_barra_lateral(fornecedor: str) -> None:
    resposta = _nav("/programacao-semanal/dashboard", email=fornecedor)

    assert _itens(resposta) == ["Programação Semanal"]
    # As cinco telas da programação são as abas, sem a aba de grupo do módulo 02.
    assert _abas(resposta) == ABAS_DA_PROGRAMACAO
    tags = parse_tags(resposta.get_body().decode())
    ativos = [item for item in find_all(tags, "a", "sidebar__item") if item.has_class("is-active")]
    assert [item.attrs["aria-label"] for item in ativos] == ["Programação Semanal"]
    atuais = [aba for aba in find_all(tags, "a", "tab") if aba.attrs.get("aria-current") == "page"]
    assert [aba.clean_text() for aba in atuais] == ["Dashboard"]


def test_fornecedor_que_abre_o_inicio_entra_pela_programacao_semanal(fornecedor: str) -> None:
    barra = find_by_id(parse_tags(_nav("/", email=fornecedor).get_body().decode()), "main-nav")

    assert barra is not None
    assert barra.attrs["data-caminho"] == "/programacao-semanal/programacao"
    assert barra.attrs["data-tela"] == "/_views/programacao_semanal/programacao.html"


def test_fornecedor_em_outra_tela_cai_no_acesso_negado(fornecedor: str) -> None:
    barra = find_by_id(
        parse_tags(_nav("/financeiro/eac", email=fornecedor).get_body().decode()), "main-nav"
    )
    assert barra is not None
    assert barra.attrs["data-tela"] == "/api/acesso-negado?caminho=/financeiro/eac"

    guarda = _negado("/financeiro/eac", email=fornecedor)

    assert guarda.status_code == 403
    assert rbac.SUPPLIER_SCOPE_MESSAGE in _corpo(guarda)
    assert 'href="/"' in _corpo(guarda)


# ── O decorador: usuário, escopo e permissão antes do handler ────────────


def _rota(modulo: str | None = None, permissao: Permission | None = None, texto: str = "ok"):
    @fragment_route(access=Access(module=modulo, permission=permissao))
    def rota(_req: func.HttpRequest, _session, _contexto: RequestContext) -> func.HttpResponse:
        return func.HttpResponse(texto)

    return rota


def _chamar(rota, **identidade) -> func.HttpResponse:
    return rota(requisicao("/api/teste", alvo="conteudo", **identidade))


def test_rota_com_access_entrega_o_usuario_e_o_escopo_ao_handler(
    sessao_das_rotas: Session,
) -> None:
    fabrica = criar_projeto(sessao_das_rotas, codigo="TN-ACESSO-001", nome="Projeto do acesso")
    criar_colaborador(sessao_das_rotas, email="gestor@example.invalid", nome="Gil Gestor")

    @fragment_route(access=Access())
    def rota(_req: func.HttpRequest, _session, contexto: RequestContext) -> func.HttpResponse:
        return func.HttpResponse(f"{contexto.user.name}|{contexto.scope.project_id}")

    resposta = rota(
        requisicao(
            "/api/teste",
            email="gestor@example.invalid",
            alvo="conteudo",
            params={"projeto": str(fabrica.id)},
        )
    )

    assert resposta.status_code == 200
    assert resposta.get_body().decode() == f"Gil Gestor|{fabrica.id}"


def test_rota_nao_chama_o_handler_quando_o_acesso_e_recusado(sessao_das_rotas: Session) -> None:
    chamadas: list[bool] = []

    @fragment_route(access=Access(module="configuracoes"))
    def rota(_req: func.HttpRequest, _session, _contexto: RequestContext) -> func.HttpResponse:
        chamadas.append(True)
        return func.HttpResponse("ok")

    criar_colaborador(sessao_das_rotas, email="membro@example.invalid", perfil="Membro")

    resposta = _chamar(rota, email="membro@example.invalid")

    assert resposta.status_code == 403
    assert "Esta operação exige o perfil Gestor ou Admin." in _corpo(resposta)
    assert chamadas == []


def test_rota_que_grava_recusa_o_visualizador_e_aceita_o_membro(sessao_das_rotas: Session) -> None:
    criar_colaborador(sessao_das_rotas, email="vendo@example.invalid", perfil="Visualizador")
    criar_colaborador(sessao_das_rotas, email="gravando@example.invalid", perfil="Membro")
    grava = _rota("financeiro", Permission.WRITE)

    recusada = _chamar(grava, email="vendo@example.invalid")
    aceita = _chamar(grava, email="gravando@example.invalid")

    assert recusada.status_code == 403
    assert "O seu perfil é Visualizador." in _corpo(recusada)
    assert aceita.status_code == 200


@pytest.mark.usefixtures("sessao_das_rotas")
def test_rota_de_quem_nao_esta_no_cadastro_devolve_403_sem_chamar_o_handler() -> None:
    resposta = _chamar(_rota("financeiro"), email="intruso@example.invalid")

    assert resposta.status_code == 403
    assert auth.NOT_REGISTERED_MESSAGE in _corpo(resposta)


def test_rota_sem_o_cabecalho_do_alpine_redireciona_antes_de_resolver_o_usuario() -> None:
    rota = _rota("financeiro")
    req = func.HttpRequest(method="GET", url="/api/teste", headers={}, params={}, body=b"")

    resposta = rota(req)

    assert resposta.status_code == 302
    assert resposta.headers.get("Location") == "/index.html"


def test_rota_aberta_nao_resolve_usuario_e_continua_recebendo_req_e_session() -> None:
    recebido: list[int] = []

    @fragment_route(access=OPEN)
    def rota(_req: func.HttpRequest, *argumentos: object) -> func.HttpResponse:
        recebido.append(len(argumentos))
        return func.HttpResponse("ok")

    resposta = rota(requisicao("/api/teste", alvo="x"))

    assert resposta.status_code == 200
    assert recebido == [1]


# ── Papel da Programação Semanal, por projeto, na rota ───────────────────


def test_papel_da_programacao_semanal_vale_so_no_projeto_em_que_foi_dado_na_rota(
    sessao_das_rotas: Session,
) -> None:
    fabrica = criar_projeto(sessao_das_rotas, codigo="TN-ACESSO-001", nome="Projeto do acesso")
    caldeira = criar_projeto(sessao_das_rotas, codigo="TN-ACESSO-002", nome="Outro projeto")
    criar_colaborador(
        sessao_das_rotas,
        email="planejadora@example.invalid",
        perfil="Visualizador",
        papeis=[(fabrica.id, "Planejador")],
    )

    @fragment_route(access=Access(module="programacao_semanal"))
    def publicar(_req: func.HttpRequest, _session, contexto: RequestContext) -> func.HttpResponse:
        projeto = contexto.scope.require_project()
        rbac.require_schedule_role(contexto.user, projeto, ScheduleRole.PLANNER)
        return func.HttpResponse("publicada")

    def no_projeto(projeto: Project) -> func.HttpResponse:
        return publicar(
            requisicao(
                "/api/teste",
                email="planejadora@example.invalid",
                alvo="conteudo",
                params={"projeto": str(projeto.id)},
            )
        )

    assert no_projeto(fabrica).status_code == 200
    fora = no_projeto(caldeira)
    assert fora.status_code == 403
    assert "papel de Planejador" in _corpo(fora)


# ── Teste transversal de vínculo (spec, Testing Decisions) ───────────────


@pytest.mark.parametrize("modulo", TODOS_OS_MODULOS)
def test_vinculo_fornecedor_recebe_403_em_toda_rota_que_nao_e_da_programacao_semanal(
    fornecedor: str, modulo: str
) -> None:
    resposta = _chamar(_rota(modulo), email=fornecedor)

    if modulo == "programacao_semanal":
        assert resposta.status_code == 200
    else:
        assert resposta.status_code == 403
        assert rbac.SUPPLIER_SCOPE_MESSAGE in _corpo(resposta)


@pytest.mark.parametrize("permissao", list(Permission))
def test_vinculo_fornecedor_nao_ganha_permissao_geral_nem_na_programacao_semanal(
    fornecedor: str, permissao: Permission
) -> None:
    resposta = _chamar(_rota("programacao_semanal", permissao), email=fornecedor)

    assert resposta.status_code == 403


def test_vinculo_fornecedor_so_recebe_a_programacao_semanal_da_propria_empresa(
    sessao_das_rotas: Session,
) -> None:
    propria = criar_empresa(sessao_das_rotas, "Contratada Alfa")
    outra = criar_empresa(sessao_das_rotas, "Contratada Beta")
    criar_colaborador(
        sessao_das_rotas,
        email="fornecedor@example.invalid",
        vinculo="Fornecedor",
        empresa=propria,
    )

    @fragment_route(access=Access(module="programacao_semanal"))
    def atividades(req: func.HttpRequest, _session, contexto: RequestContext) -> func.HttpResponse:
        # O que a fachada da programação faz: corta a consulta pela empresa do
        # fornecedor e recusa quem pede a de outra.
        rbac.require_company(contexto.user, int(req.params.get("empresa", "0")))
        return func.HttpResponse(str(rbac.company_scope(contexto.user)))

    def da_empresa(empresa_id: int) -> func.HttpResponse:
        return atividades(
            requisicao(
                "/api/teste",
                email="fornecedor@example.invalid",
                alvo="conteudo",
                params={"empresa": str(empresa_id)},
            )
        )

    propria_resposta = da_empresa(propria.id)
    assert propria_resposta.status_code == 200
    assert propria_resposta.get_body().decode() == str(propria.id)
    de_outra = da_empresa(outra.id)
    assert de_outra.status_code == 403
    assert rbac.OWN_COMPANY_MESSAGE in _corpo(de_outra)


def test_vinculo_cliente_visualizador_ve_os_modulos_e_nao_grava(sessao_das_rotas: Session) -> None:
    criar_colaborador(
        sessao_das_rotas,
        email="cliente@example.invalid",
        perfil="Visualizador",
        vinculo="Cliente",
    )

    for modulo in TODOS_OS_MODULOS:
        resposta = _chamar(_rota(modulo), email="cliente@example.invalid")
        assert resposta.status_code == (403 if modulo == "configuracoes" else 200), modulo
    grava = _chamar(_rota("financeiro", Permission.WRITE), email="cliente@example.invalid")
    assert grava.status_code == 403
    assert "O seu perfil é Visualizador." in _corpo(grava)


def test_vinculo_cliente_com_perfil_de_gestor_abre_configuracoes(sessao_das_rotas: Session) -> None:
    criar_colaborador(
        sessao_das_rotas, email="cliente@example.invalid", perfil="Gestor", vinculo="Cliente"
    )

    resposta = _chamar(_rota("configuracoes"), email="cliente@example.invalid")

    assert resposta.status_code == 200


# ── O que o Azure Functions enxerga ──────────────────────────────────────

ROTAS_PUBLICAS_POR_NATUREZA = {"health"}


def test_toda_rota_registrada_declara_a_politica_de_acesso(funcoes_registradas: list) -> None:
    sem_politica = [
        funcao.get_function_name()
        for funcao in funcoes_registradas
        if funcao.get_function_name() not in ROTAS_PUBLICAS_POR_NATUREZA
        and not isinstance(
            funcao.get_user_function().__dict__.get(routing.ACCESS_ATTRIBUTE), Access
        )
    ]

    assert sem_politica == []


def test_a_assinatura_que_o_azure_functions_enxerga_de_cada_rota_e_so_o_req(
    funcoes_registradas: list,
) -> None:
    for funcao in funcoes_registradas:
        parametros = list(inspect.signature(funcao.get_user_function()).parameters)
        assert parametros == ["req"], funcao.get_function_name()


def test_o_decorador_esconde_session_e_contexto_da_assinatura_da_rota() -> None:
    com_acesso = _rota("financeiro")

    @fragment_route
    def sem_acesso(_req: func.HttpRequest, _session) -> func.HttpResponse:
        return func.HttpResponse("ok")

    for rota in (com_acesso, sem_acesso):
        assinatura = inspect.signature(rota)
        assert list(assinatura.parameters) == ["req"]
        assert assinatura.parameters["req"].annotation is func.HttpRequest
        assert assinatura.return_annotation is func.HttpResponse
