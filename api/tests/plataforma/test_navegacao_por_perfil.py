"""A navegação recortada pelo perfil e pelo vínculo (ISSUE-011, D7), sem HTTP.

``navigation_view.build`` recebe o ``User`` da requisição e entrega só o que a
pessoa pode abrir, pelas mesmas regras que as rotas aplicam (``core.rbac``): o
que a barra lateral lista, as abas, para onde o shell é mandado quando a tela
não é da pessoa e o cartão do usuário. A barra é cortesia: a autoridade é a rota.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.core import navigation, navigation_view
from src.core.rbac import Bond, GeneralProfile, User
from src.core.scope import Scope

RAIZ_DO_REPOSITORIO = Path(__file__).resolve().parents[3]

PORTFOLIO = Scope(project_id=None, source="padrao")
PROGRAMACAO = "/programacao-semanal/programacao"


def _usuario(
    *,
    perfil: GeneralProfile = GeneralProfile.MEMBER,
    vinculo: Bond = Bond.TIMENOW,
    nome: str = "Maria da Silva Souza",
) -> User:
    return User(
        id=1,
        person_id=1,
        name=nome,
        email="maria@example.invalid",
        general_profile=perfil,
        bond=vinculo,
        company_id=7 if vinculo is Bond.SUPPLIER else None,
    )


def _titulos(visao: navigation_view.NavigationView) -> list[str]:
    return [modulo.title for modulo in visao.modules]


def test_sem_usuario_a_lista_vai_inteira() -> None:
    visao = navigation_view.build("/configuracoes/parametros", PORTFOLIO, [])

    assert len(visao.modules) == 10
    assert visao.user is None
    assert visao.demo is None


@pytest.mark.parametrize(
    ("perfil", "total"),
    [
        (GeneralProfile.VIEWER, 9),
        (GeneralProfile.MEMBER, 9),
        (GeneralProfile.MANAGER, 10),
        (GeneralProfile.ADMIN, 10),
    ],
)
def test_configuracoes_so_aparece_para_gestor_e_admin(perfil: GeneralProfile, total: int) -> None:
    visao = navigation_view.build("/", PORTFOLIO, [], _usuario(perfil=perfil))

    assert len(visao.modules) == total
    assert ("Configurações" in _titulos(visao)) == (total == 10)


@pytest.mark.parametrize("vinculo", [Bond.TIMENOW, Bond.CLIENT])
def test_cliente_e_timenow_veem_os_mesmos_modulos_pelo_perfil_geral(vinculo: Bond) -> None:
    visao = navigation_view.build(
        "/", PORTFOLIO, [], _usuario(perfil=GeneralProfile.VIEWER, vinculo=vinculo)
    )

    assert _titulos(visao) == [
        "Início",
        "Central de Ações",
        "Planejamento",
        "Gestão Financeira",
        "Suprimentos",
        "Gestão de Riscos",
        "Gestão da Qualidade",
        "HSE",
        "Governança",
    ]


def test_o_admin_ve_as_tres_telas_de_configuracoes_e_o_gestor_so_duas() -> None:
    gestor = navigation_view.build(
        "/configuracoes/parametros", PORTFOLIO, [], _usuario(perfil=GeneralProfile.MANAGER)
    )
    admin = navigation_view.build(
        "/configuracoes/parametros", PORTFOLIO, [], _usuario(perfil=GeneralProfile.ADMIN)
    )

    assert [aba.label for aba in gestor.tabs] == ["Parâmetros", "Cadastros"]
    assert [aba.label for aba in admin.tabs] == ["Parâmetros", "Colaboradores", "Cadastros"]


def test_fornecedor_tem_um_unico_item_com_as_telas_da_programacao_como_abas() -> None:
    fornecedor = _usuario(vinculo=Bond.SUPPLIER)

    visao = navigation_view.build("/programacao-semanal/governanca", PORTFOLIO, [], fornecedor)

    assert _titulos(visao) == ["Programação Semanal"]
    assert visao.modules[0].number is None
    assert visao.modules[0].icon == navigation_view.SUPPLIER_MODULE_ICON
    assert visao.modules[0].active
    assert visao.modules[0].url == f"{PROGRAMACAO}?projeto=portfolio"
    assert [aba.label for aba in visao.tabs] == [
        "Programação",
        "Dashboard",
        "Governança",
        "Importação",
        "Configuração",
    ]
    assert [aba.label for aba in visao.tabs if aba.is_active] == ["Governança"]
    assert visao.subtabs == ()
    assert visao.page_title == "Governança da programação · Programação Semanal · Timenow GestNow"


def test_para_o_fornecedor_o_inicio_vira_a_primeira_tela_que_ele_abre() -> None:
    fornecedor = _usuario(vinculo=Bond.SUPPLIER)

    for caminho in ("/", "/index.html", "/inicio"):
        visao = navigation_view.build(caminho, PORTFOLIO, [], fornecedor)

        assert visao.current_path == PROGRAMACAO
        assert visao.current_view == "/_views/programacao_semanal/programacao.html"


def test_o_inicio_continua_sendo_a_entrada_de_quem_pode_abri_lo() -> None:
    visao = navigation_view.build("/", PORTFOLIO, [], _usuario())

    assert visao.current_path == "/"
    assert visao.current_view == "/_views/inicio/home.html"


def test_tela_que_existe_e_a_pessoa_nao_abre_leva_ao_acesso_negado_e_nao_ao_desconhecido() -> None:
    membro = _usuario(perfil=GeneralProfile.MEMBER)

    negada = navigation_view.build("/configuracoes/parametros", PORTFOLIO, [], membro)
    desconhecida = navigation_view.build("/nada/aqui", PORTFOLIO, [], membro)

    assert negada.current_view == "/api/acesso-negado?caminho=/configuracoes/parametros"
    assert negada.current_path == "/configuracoes/parametros"
    assert negada.page_title == "Acesso negado · Timenow GestNow"
    assert not any(modulo.active for modulo in negada.modules)
    assert negada.tabs == ()
    assert negada.back is None
    assert negada.scope_destination == "/"
    assert desconhecida.current_view is None
    assert desconhecida.current_path is None


def test_fornecedor_em_tela_de_outro_modulo_cai_no_acesso_negado() -> None:
    visao = navigation_view.build("/financeiro/eac", PORTFOLIO, [], _usuario(vinculo=Bond.SUPPLIER))

    assert visao.current_view == "/api/acesso-negado?caminho=/financeiro/eac"
    assert not any(modulo.active for modulo in visao.modules)


def test_detalhe_continua_com_voltar_para_quem_abre_a_lista() -> None:
    visao = navigation_view.build("/central-acoes/ata", PORTFOLIO, [], _usuario())

    assert visao.back is not None
    assert visao.back.url == "/central-acoes/atas?projeto=portfolio"
    assert [modulo.title for modulo in visao.modules if modulo.active] == ["Central de Ações"]


def test_cartao_do_usuario_traz_iniciais_perfil_e_vinculo() -> None:
    visao = navigation_view.build(
        "/",
        PORTFOLIO,
        [],
        _usuario(perfil=GeneralProfile.MANAGER, vinculo=Bond.CLIENT, nome="maria da silva souza"),
    )

    assert visao.user == navigation_view.UserBadge(
        name="maria da silva souza",
        initials="MS",
        description="Gestor · Cliente",
        email="maria@example.invalid",
    )


@pytest.mark.parametrize(("nome", "iniciais"), [("Madonna", "M"), ("  ", "?"), ("Ana Lu", "AL")])
def test_iniciais_do_cartao(nome: str, iniciais: str) -> None:
    visao = navigation_view.build("/", PORTFOLIO, [], _usuario(nome=nome))

    assert visao.user is not None
    assert visao.user.initials == iniciais


def test_o_icone_do_item_do_fornecedor_existe_no_design_system() -> None:
    icones = (RAIZ_DO_REPOSITORIO / "app" / "ds" / "icons.js").read_text(encoding="utf-8")
    existentes = set(re.findall(r"^  (\w+): '<", icones, flags=re.MULTILINE))

    assert navigation_view.SUPPLIER_MODULE_ICON in existentes


def test_toda_tela_da_lista_tem_um_destino_para_cada_perfil() -> None:
    # Nenhuma combinação deixa a pessoa sem tela: ou abre, ou cai no acesso negado.
    for perfil in GeneralProfile:
        for vinculo in Bond:
            usuario = _usuario(perfil=perfil, vinculo=vinculo)
            for tela in navigation.screens():
                visao = navigation_view.build(navigation.public_path(tela), PORTFOLIO, [], usuario)

                assert visao.current_view is not None, (perfil, vinculo, tela.key)
