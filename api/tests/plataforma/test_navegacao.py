"""Navegação (ISSUE-009): a lista única de dois níveis e o que o /api/nav serve a partir dela.

Três costuras: a lista e as suas buscas (puras), a decisão do que a barra
lateral e as abas mostram (pura, sem HTTP) e a rota ``/api/nav`` (contrato:
status, alvos do fragmento, item ativo, Voltar). O que a pessoa vê é o que se
afirma: qual item está ativo, quais abas existem, para onde cada link leva.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import azure.functions as func
import pytest

from src.blueprints.nav import main_nav
from src.core import navigation, navigation_view
from src.core.scope import Scope
from src.modulos.configuracoes.models import Project
from tests.html_tags import find_all, find_by_id, parse_tags

RAIZ_DO_REPOSITORIO = Path(__file__).resolve().parents[3]

PORTFOLIO = Scope(project_id=None, source="padrao")
NO_PROJETO_7 = Scope(project_id=7, source="url")


@dataclass(frozen=True)
class ProjetoDeTeste:
    id: int
    code: str
    name: str


PROJETOS = (
    ProjetoDeTeste(id=7, code="TN-2026-014", name="Construção de uma nova fábrica"),
    ProjetoDeTeste(id=8, code="TN-2026-021", name="Construção de uma nova caldeira"),
)


def _abas(visao: navigation_view.NavigationView) -> list[str]:
    return [aba.label for aba in visao.tabs]


# ── A lista ──────────────────────────────────────────────────────────────


def test_lista_tem_inicio_oito_modulos_numerados_e_configuracoes() -> None:
    modulos = navigation.modules()

    assert [modulo.id for modulo in modulos] == [
        "inicio",
        "central_acoes",
        "planejamento",
        "financeiro",
        "suprimentos",
        "riscos",
        "qualidade",
        "hse",
        "governanca",
        "configuracoes",
    ]
    assert [modulo.number for modulo in modulos] == [
        None,
        "01",
        "02",
        "03",
        "04",
        "05",
        "06",
        "07",
        "08",
        None,
    ]


def test_lista_tem_as_51_telas_do_produto() -> None:
    # 45 do protótipo, menos a tela única de Programação Semanal, mais as 5 do
    # app (D10) e mais Colaboradores e Cadastros ao lado de Parâmetros.
    assert len(navigation.screens()) == 45 - 1 + 5 + 2


def test_telas_de_detalhe_apontam_a_lista_de_origem() -> None:
    detalhes = {tela.key: tela.detail_of for tela in navigation.screens() if tela.is_detail}

    assert detalhes == {
        "relatorio/gerencial": "inicio/home",
        "central_acoes/ata": "central_acoes/atas",
        "financeiro/contrato": "financeiro/contratos",
        "riscos/ficha": "riscos/registro",
        "governanca/mudanca": "governanca/mudancas",
    }


def test_programacao_semanal_e_submodulo_do_planejamento() -> None:
    telas = [tela for tela in navigation.screens() if tela.module == "programacao_semanal"]

    assert [tela.id for tela in telas] == [
        "programacao",
        "dashboard",
        "governanca",
        "importacao",
        "configuracao",
    ]
    assert {tela.nav_module for tela in telas} == {"planejamento"}
    assert {tela.group for tela in telas} == {"Programação Semanal"}


def test_configuracoes_tem_tres_telas() -> None:
    modulo = next(m for m in navigation.modules() if m.id == "configuracoes")

    assert [tela.id for tela in modulo.screens] == ["parametros", "colaboradores", "cadastros"]


def test_endereco_publico_vai_e_volta_para_toda_tela() -> None:
    for tela in navigation.screens():
        assert navigation.screen_for_path(navigation.public_path(tela)) == tela
        assert navigation.view_path(tela) == f"/_views/{tela.module}/{tela.id}.html"


def test_enderecos_conhecidos_e_desconhecidos() -> None:
    inicio = navigation.find_screen("inicio/home")

    assert navigation.public_path(inicio) == "/"
    assert navigation.screen_for_path("/") == inicio
    assert navigation.screen_for_path("/index.html") == inicio
    assert navigation.screen_for_path("/Central-Acoes/ATAS/?projeto=2").key == "central_acoes/atas"
    assert navigation.screen_for_path("/central-acoes/nao-existe") is None
    assert navigation.screen_for_path("/api/nav") is None
    assert navigation.screen_for_path(None) is None


def test_todo_icone_da_lista_existe_no_design_system() -> None:
    icones = (RAIZ_DO_REPOSITORIO / "app" / "ds" / "icons.js").read_text(encoding="utf-8")
    existentes = set(re.findall(r"^  (\w+): '<", icones, flags=re.MULTILINE))

    assert {modulo.icon for modulo in navigation.modules()} <= existentes


def _lista_invalida(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, telas: list[dict]) -> None:
    arquivo = tmp_path / "navegacao.json"
    modulo = {"id": "a", "titulo": "A", "icone": "home", "telas": telas}
    arquivo.write_text(json.dumps({"modulos": [modulo]}), encoding="utf-8")
    monkeypatch.setattr(navigation, "NAVIGATION_FILE", arquivo)
    navigation.modules.cache_clear()


def test_detalhe_sem_origem_na_lista_falha_alto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _lista_invalida(
        tmp_path,
        monkeypatch,
        [
            {"id": "lista", "titulo": "Lista"},
            {"id": "ficha", "titulo": "Ficha", "detalhe_de": "a/nao_existe"},
        ],
    )

    with pytest.raises(navigation.InvalidNavigationError, match="detalhe_de"):
        navigation.modules()


def test_grupo_separado_por_outra_tela_falha_alto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _lista_invalida(
        tmp_path,
        monkeypatch,
        [
            {"id": "um", "titulo": "Um", "grupo": "G"},
            {"id": "dois", "titulo": "Dois"},
            {"id": "tres", "titulo": "Três", "grupo": "G"},
        ],
    )

    with pytest.raises(navigation.InvalidNavigationError, match="contiguo"):
        navigation.modules()


# ── O que a barra lateral e as abas mostram ──────────────────────────────


def test_modulo_da_tela_aberta_fica_destacado_e_todo_link_leva_o_escopo() -> None:
    visao = navigation_view.build("/planejamento/eap", NO_PROJETO_7, PROJETOS)

    assert len(visao.modules) == 10
    assert [m.title for m in visao.modules if m.active] == ["Planejamento"]
    assert visao.modules[2].url == "/planejamento/eap?projeto=7"
    assert all(modulo.url.endswith("?projeto=7") for modulo in visao.modules)
    assert visao.home_url == "/?projeto=7"


def test_abas_do_modulo_juntam_as_telas_da_programacao_semanal_numa_so() -> None:
    visao = navigation_view.build("/planejamento/eap", PORTFOLIO, PROJETOS)

    assert _abas(visao) == [
        "EAP",
        "Curva S",
        "KPIs",
        "Relato do período",
        "6WLA",
        "Programação Semanal",
        "Produtividade",
        "Punch list",
    ]
    assert [aba.label for aba in visao.tabs if aba.is_active] == ["EAP"]
    assert visao.subtabs == ()


def test_dentro_da_programacao_semanal_a_aba_do_grupo_acende_e_surgem_as_subabas() -> None:
    visao = navigation_view.build("/programacao-semanal/dashboard", PORTFOLIO, PROJETOS)

    grupo = next(aba for aba in visao.tabs if aba.label == "Programação Semanal")
    assert grupo.current == "true"
    assert grupo.url == "/programacao-semanal/programacao?projeto=portfolio"
    assert visao.subtabs_label == "Programação Semanal"
    assert [aba.label for aba in visao.subtabs] == [
        "Programação",
        "Dashboard",
        "Governança",
        "Importação",
        "Configuração",
    ]
    assert [aba.label for aba in visao.subtabs if aba.current == "page"] == ["Dashboard"]


def test_aba_de_nome_curto_guarda_o_titulo_completo() -> None:
    visao = navigation_view.build("/financeiro/eac", PORTFOLIO, PROJETOS)

    desembolso = next(aba for aba in visao.tabs if aba.label == "Desembolso")
    assert desembolso.title == "Cronograma de desembolso"
    assert desembolso.is_abbreviated
    assert not next(aba for aba in visao.tabs if aba.label == "EAC").is_abbreviated


def test_tela_de_detalhe_destaca_o_modulo_de_origem_e_oferece_voltar_para_a_lista() -> None:
    visao = navigation_view.build("/central-acoes/ata", NO_PROJETO_7, PROJETOS)

    assert [m.title for m in visao.modules if m.active] == ["Central de Ações"]
    assert visao.tabs == ()
    assert visao.back is not None
    assert (visao.back.title, visao.back.url) == ("Atas", "/central-acoes/atas?projeto=7")
    assert visao.has_bar
    # Trocar o escopo no detalhe volta para a lista (D8).
    assert visao.scope_destination == "/central-acoes/atas"


def test_relatorio_gerencial_e_detalhe_do_inicio() -> None:
    visao = navigation_view.build("/relatorio/gerencial", PORTFOLIO, PROJETOS)

    assert [m.title for m in visao.modules if m.active] == ["Início"]
    assert visao.back is not None
    assert visao.back.url == "/?projeto=portfolio"
    assert visao.page_title == "Relatório gerencial · Início · Timenow GestNow"


def test_inicio_nao_tem_barra_de_abas() -> None:
    visao = navigation_view.build("/", PORTFOLIO, PROJETOS)

    assert not visao.has_bar
    assert visao.current_view == "/_views/inicio/home.html"
    assert visao.page_title == "Início · Timenow GestNow"


def test_endereco_desconhecido_deixa_a_barra_vazia_e_nenhuma_tela_aberta() -> None:
    visao = navigation_view.build("/nada/aqui", PORTFOLIO, PROJETOS)

    assert visao.current_view is None
    assert visao.current_path is None
    assert not any(modulo.active for modulo in visao.modules)
    assert not visao.has_bar
    assert visao.scope_destination == "/"


def test_seletor_de_escopo_lista_o_portfolio_e_os_projetos() -> None:
    visao = navigation_view.build("/", NO_PROJETO_7, PROJETOS)

    assert [(o.value, o.label, o.selected) for o in visao.scope_options] == [
        ("portfolio", "Portfólio (2 projetos)", False),
        ("7", "TN-2026-014 · Construção de uma nova fábrica", True),
        ("8", "TN-2026-021 · Construção de uma nova caldeira", False),
    ]
    assert visao.scope_parameter == "7"
    assert visao.scope_icon == "building"


def test_portfolio_com_um_projeto_fala_no_singular() -> None:
    visao = navigation_view.build("/", PORTFOLIO, PROJETOS[:1])

    assert visao.scope_options[0].label == "Portfólio (1 projeto)"
    assert visao.scope_icon == "layers"


# ── A rota /api/nav ──────────────────────────────────────────────────────


def _requisicao(
    caminho: str | None = None, *, projeto: str | None = None, alpine: bool = True
) -> func.HttpRequest:
    headers = {"X-Alpine-Target": "main-nav module-tabs"}
    if alpine:
        headers["X-Alpine-Request"] = "true"
    params = {}
    if caminho is not None:
        params["caminho"] = caminho
    if projeto is not None:
        params["projeto"] = projeto
    return func.HttpRequest(
        method="GET", url="/api/nav", headers=headers, params=params, route_params={}, body=b""
    )


def test_nav_sem_o_cabecalho_do_alpine_redireciona_para_o_shell() -> None:
    resposta = main_nav(_requisicao("/", alpine=False))

    assert resposta.status_code == 302
    assert resposta.headers.get("Location") == "/index.html"


@pytest.mark.usefixtures("rotas_na_transacao_do_teste")
def test_nav_devolve_a_barra_lateral_e_as_abas_no_mesmo_fragmento() -> None:
    resposta = main_nav(_requisicao("/planejamento/eap", projeto="portfolio"))

    assert resposta.status_code == 200
    tags = parse_tags(resposta.get_body().decode())
    barra = find_by_id(tags, "main-nav")
    abas = find_by_id(tags, "module-tabs")
    assert barra is not None
    assert abas is not None
    assert barra.attrs["data-tela"] == "/_views/planejamento/eap.html"
    assert barra.attrs["data-caminho"] == "/planejamento/eap"
    assert barra.attrs["data-escopo"] == "portfolio"
    assert "hidden" not in abas.attrs


@pytest.mark.usefixtures("rotas_na_transacao_do_teste")
def test_nav_lista_os_modulos_e_destaca_o_ativo() -> None:
    resposta = main_nav(_requisicao("/planejamento/eap", projeto="portfolio"))

    tags = parse_tags(resposta.get_body().decode())
    itens = find_all(tags, "a", "sidebar__item")
    assert [item.attrs["aria-label"] for item in itens] == [
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
    ativos = [item for item in itens if item.has_class("is-active")]
    assert [item.attrs["aria-label"] for item in ativos] == ["02 Planejamento"]
    assert ativos[0].attrs["aria-current"] == "true"
    assert all("data-tn-tela" in item.attrs for item in itens)
    # O trilho de ícones mostra o nome na dica: todo item o carrega.
    assert all(item.attrs["data-dica-trilho"] == item.attrs["aria-label"] for item in itens)


@pytest.mark.usefixtures("rotas_na_transacao_do_teste")
def test_nav_abas_do_modulo_marcam_a_tela_aberta() -> None:
    resposta = main_nav(_requisicao("/financeiro/kpis", projeto="portfolio"))

    tags = parse_tags(resposta.get_body().decode())
    abas = [tag for tag in find_all(tags, "a", "tab") if "data-tn-tela" in tag.attrs]
    assert [aba.clean_text() for aba in abas] == [
        "EAC",
        "Mapa de controle",
        "Desembolso",
        "KPIs",
        "Curva S",
        "Contingência",
        "Contratos",
    ]
    atual = [aba for aba in abas if aba.attrs.get("aria-current") == "page"]
    assert [aba.clean_text() for aba in atual] == ["KPIs"]
    assert atual[0].attrs["aria-label"] == "KPIs de custo"
    assert atual[0].attrs["href"] == "/financeiro/kpis?projeto=portfolio"


@pytest.mark.usefixtures("rotas_na_transacao_do_teste")
def test_nav_em_tela_de_detalhe_mostra_o_voltar_e_destaca_a_origem() -> None:
    resposta = main_nav(_requisicao("/central-acoes/ata", projeto="portfolio"))

    tags = parse_tags(resposta.get_body().decode())
    voltar = find_all(tags, "a", "module-tabs__voltar")
    assert len(voltar) == 1
    assert voltar[0].attrs["href"] == "/central-acoes/atas?projeto=portfolio"
    assert voltar[0].attrs["aria-label"] == "Voltar para Atas"
    assert find_all(tags, "a", "tab") == []
    ativos = [item for item in find_all(tags, "a", "sidebar__item") if item.has_class("is-active")]
    assert [item.attrs["aria-label"] for item in ativos] == ["01 Central de Ações"]


@pytest.mark.usefixtures("rotas_na_transacao_do_teste")
def test_nav_no_inicio_a_barra_de_abas_fica_oculta() -> None:
    resposta = main_nav(_requisicao("/", projeto="portfolio"))

    abas = find_by_id(parse_tags(resposta.get_body().decode()), "module-tabs")
    assert abas is not None
    assert "hidden" in abas.attrs


@pytest.mark.usefixtures("rotas_na_transacao_do_teste")
def test_nav_de_endereco_desconhecido_nao_indica_tela_para_abrir() -> None:
    resposta = main_nav(_requisicao("/nada/aqui"))

    barra = find_by_id(parse_tags(resposta.get_body().decode()), "main-nav")
    assert barra is not None
    assert barra.attrs["data-tela"] == ""
    assert barra.attrs["data-caminho"] == ""


def test_nav_seletor_de_escopo_sai_com_os_projetos_do_cadastro(
    dois_projetos: tuple[Project, Project],
) -> None:
    fabrica, caldeira = dois_projetos

    resposta = main_nav(_requisicao("/central-acoes/ata", projeto=str(caldeira.id)))

    tags = parse_tags(resposta.get_body().decode())
    seletor = find_by_id(tags, "escopo-seletor")
    opcoes = [tag for tag in tags if tag.name == "option"]
    assert seletor is not None
    assert str(fabrica.id) in [opcao.attrs["value"] for opcao in opcoes]
    escolhidas = [opcao for opcao in opcoes if "selected" in opcao.attrs]
    assert [opcao.attrs["value"] for opcao in escolhidas] == [str(caldeira.id)]
    # O seletor num detalhe leva à lista de origem, e o servidor é quem diz.
    caixa = find_all(tags, "div", "sidebar__escopo")[0]
    assert caixa.attrs["data-destino"] == "/central-acoes/atas"
    # Todo link de navegação carrega o escopo, para o link copiado abrir igual.
    itens = find_all(tags, "a", "sidebar__item")
    assert all(item.attrs["href"].endswith(f"?projeto={caldeira.id}") for item in itens)
