"""Permissões em dois eixos (ISSUE-011, D7): perfil geral, papéis por projeto, vínculo e segregação.

Costura pura, sem HTTP e sem banco: o ``User`` é montado no teste e as funções de
``core.rbac`` respondem ou recusam com 403 (``AccessDeniedError``) e a mensagem
que a pessoa lê. O que se afirma é o comportamento: quem pode, quem não pode e o
que a recusa diz, com o caso de fronteira de cada regra.
"""

from __future__ import annotations

import pytest

from src.core import navigation, rbac
from src.core.errors import AccessDeniedError
from src.core.rbac import Bond, Conflict, GeneralProfile, Permission, ScheduleRole, User

MODULOS_DE_PROJETO = [
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
    "relatorio",
]


def _usuario(
    *,
    perfil: GeneralProfile = GeneralProfile.MEMBER,
    vinculo: Bond = Bond.TIMENOW,
    empresa: int | None = None,
    papeis: frozenset[tuple[int, ScheduleRole]] = frozenset(),
    pessoa: int = 10,
) -> User:
    return User(
        id=pessoa + 100,
        person_id=pessoa,
        name="Pessoa de Teste",
        email="pessoa@example.invalid",
        general_profile=perfil,
        bond=vinculo,
        company_id=empresa,
        schedule_roles=papeis,
    )


def _tela(chave: str) -> navigation.Screen:
    tela = navigation.find_screen(chave)
    assert tela is not None
    return tela


# ── Perfil geral: o conjunto de permissões de cada um ────────────────────


@pytest.mark.parametrize(
    ("perfil", "permissao", "esperado"),
    [
        (GeneralProfile.VIEWER, Permission.VIEW, True),
        (GeneralProfile.VIEWER, Permission.WRITE, False),
        (GeneralProfile.MEMBER, Permission.VIEW, True),
        (GeneralProfile.MEMBER, Permission.WRITE, True),
        (GeneralProfile.MEMBER, Permission.MANAGE, False),
        # Membro preenche, mas só Gestor e Admin leem o campo restrito do HSE (Q35).
        (GeneralProfile.MEMBER, Permission.VIEW_RESTRICTED, False),
        (GeneralProfile.MANAGER, Permission.MANAGE, True),
        (GeneralProfile.MANAGER, Permission.VIEW_RESTRICTED, True),
        (GeneralProfile.MANAGER, Permission.CONFIGURE, True),
        (GeneralProfile.MANAGER, Permission.ADMINISTER, False),
        (GeneralProfile.ADMIN, Permission.ADMINISTER, True),
    ],
)
def test_cada_perfil_geral_tem_o_seu_conjunto_de_permissoes(
    perfil: GeneralProfile, permissao: Permission, *, esperado: bool
) -> None:
    assert rbac.can(_usuario(perfil=perfil), permissao) is esperado


def test_admin_tem_todas_as_permissoes() -> None:
    admin = _usuario(perfil=GeneralProfile.ADMIN)

    assert all(rbac.can(admin, permissao) for permissao in Permission)


def test_recusa_por_perfil_diz_quem_pode_e_qual_e_o_perfil_da_pessoa() -> None:
    with pytest.raises(AccessDeniedError) as erro:
        rbac.require(_usuario(perfil=GeneralProfile.MEMBER), Permission.MANAGE)

    assert str(erro.value) == "Esta operação exige o perfil Gestor ou Admin. O seu perfil é Membro."


def test_recusa_de_gravacao_lista_os_tres_perfis_que_gravam() -> None:
    with pytest.raises(AccessDeniedError) as erro:
        rbac.require(_usuario(perfil=GeneralProfile.VIEWER), Permission.WRITE)

    assert str(erro.value) == (
        "Esta operação exige o perfil Membro, Gestor ou Admin. O seu perfil é Visualizador."
    )


def test_quem_tem_a_permissao_nao_e_recusado() -> None:
    rbac.require(_usuario(perfil=GeneralProfile.MANAGER), Permission.MANAGE)


# ── Módulos e telas ──────────────────────────────────────────────────────


@pytest.mark.parametrize("vinculo", [Bond.TIMENOW, Bond.CLIENT])
@pytest.mark.parametrize("perfil", list(GeneralProfile))
@pytest.mark.parametrize("modulo", MODULOS_DE_PROJETO)
def test_todo_perfil_de_timenow_ou_cliente_abre_os_modulos_de_projeto(
    modulo: str, perfil: GeneralProfile, vinculo: Bond
) -> None:
    assert rbac.can_use_module(_usuario(perfil=perfil, vinculo=vinculo), modulo)


@pytest.mark.parametrize(
    ("perfil", "esperado"),
    [
        (GeneralProfile.VIEWER, False),
        (GeneralProfile.MEMBER, False),
        (GeneralProfile.MANAGER, True),
        (GeneralProfile.ADMIN, True),
    ],
)
def test_configuracoes_aparece_so_para_gestor_e_admin(
    perfil: GeneralProfile, *, esperado: bool
) -> None:
    assert rbac.can_use_module(_usuario(perfil=perfil), "configuracoes") is esperado


def test_recusa_de_modulo_diz_o_perfil_que_abre() -> None:
    with pytest.raises(AccessDeniedError) as erro:
        rbac.require_module(_usuario(perfil=GeneralProfile.MEMBER), "configuracoes")

    assert str(erro.value) == "Esta operação exige o perfil Gestor ou Admin. O seu perfil é Membro."


def test_colaboradores_e_so_do_admin_e_parametros_e_do_gestor() -> None:
    gestor = _usuario(perfil=GeneralProfile.MANAGER)
    admin = _usuario(perfil=GeneralProfile.ADMIN)

    assert rbac.can_open_screen(gestor, _tela("configuracoes/parametros"))
    assert not rbac.can_open_screen(gestor, _tela("configuracoes/colaboradores"))
    assert rbac.can_open_screen(admin, _tela("configuracoes/colaboradores"))


def test_recusa_de_tela_cita_a_tela_e_o_perfil() -> None:
    gestor = _usuario(perfil=GeneralProfile.MANAGER)

    with pytest.raises(AccessDeniedError) as erro:
        rbac.require_screen(gestor, _tela("configuracoes/colaboradores"))

    assert str(erro.value) == (
        "A tela «Colaboradores» exige o perfil Admin. O seu perfil é Gestor."
    )


# ── Vínculo: o fornecedor só tem a Programação Semanal ───────────────────


@pytest.mark.parametrize("perfil", list(GeneralProfile))
def test_fornecedor_so_abre_a_programacao_semanal_qualquer_que_seja_o_perfil(
    perfil: GeneralProfile,
) -> None:
    fornecedor = _usuario(perfil=perfil, vinculo=Bond.SUPPLIER, empresa=7)

    abre = {tela.key for tela in navigation.screens() if rbac.can_open_screen(fornecedor, tela)}

    assert abre == {
        tela.key for tela in navigation.screens() if tela.module == "programacao_semanal"
    }
    assert rbac.can_use_module(fornecedor, "programacao_semanal")
    assert not any(rbac.can_use_module(fornecedor, modulo) for modulo in MODULOS_DE_PROJETO[:3])


def test_fornecedor_nao_tem_permissao_geral_nem_com_perfil_admin() -> None:
    fornecedor = _usuario(perfil=GeneralProfile.ADMIN, vinculo=Bond.SUPPLIER, empresa=7)

    assert not any(rbac.can(fornecedor, permissao) for permissao in Permission)


def test_recusa_do_fornecedor_diz_o_que_ele_alcanca() -> None:
    fornecedor = _usuario(vinculo=Bond.SUPPLIER, empresa=7)

    with pytest.raises(AccessDeniedError) as erro:
        rbac.require_module(fornecedor, "financeiro")

    assert str(erro.value) == rbac.SUPPLIER_SCOPE_MESSAGE
    with pytest.raises(AccessDeniedError, match="Programação Semanal"):
        rbac.require_screen(fornecedor, _tela("financeiro/eac"))


def test_cliente_visualizador_ve_os_modulos_e_nao_grava() -> None:
    cliente = _usuario(perfil=GeneralProfile.VIEWER, vinculo=Bond.CLIENT)

    assert rbac.can_use_module(cliente, "financeiro")
    assert rbac.can_open_screen(cliente, _tela("riscos/registro"))
    assert not rbac.can(cliente, Permission.WRITE)
    with pytest.raises(AccessDeniedError, match="O seu perfil é Visualizador"):
        rbac.require(cliente, Permission.WRITE)


# ── Vínculo: a empresa do fornecedor ─────────────────────────────────────


def test_fornecedor_so_enxerga_a_propria_empresa() -> None:
    fornecedor = _usuario(vinculo=Bond.SUPPLIER, empresa=7)

    assert rbac.company_scope(fornecedor) == 7
    rbac.require_company(fornecedor, 7)
    with pytest.raises(AccessDeniedError) as erro:
        rbac.require_company(fornecedor, 8)
    assert str(erro.value) == rbac.OWN_COMPANY_MESSAGE


def test_registro_sem_empresa_nao_e_do_fornecedor() -> None:
    fornecedor = _usuario(vinculo=Bond.SUPPLIER, empresa=7)

    with pytest.raises(AccessDeniedError):
        rbac.require_company(fornecedor, None)


@pytest.mark.parametrize("vinculo", [Bond.TIMENOW, Bond.CLIENT])
def test_quem_nao_e_fornecedor_nao_tem_recorte_de_empresa(vinculo: Bond) -> None:
    pessoa = _usuario(vinculo=vinculo, empresa=7)

    assert rbac.company_scope(pessoa) is None
    rbac.require_company(pessoa, 8)


def test_fornecedor_sem_empresa_e_recusado_em_vez_de_ver_tudo() -> None:
    fornecedor = _usuario(vinculo=Bond.SUPPLIER, empresa=None)

    with pytest.raises(AccessDeniedError) as erro:
        rbac.company_scope(fornecedor)

    assert str(erro.value) == rbac.COMPANY_MISSING_MESSAGE


# ── Papéis da Programação Semanal, por projeto ───────────────────────────


def _com_papeis() -> User:
    return _usuario(
        papeis=frozenset({(1, ScheduleRole.PLANNER), (3, ScheduleRole.INSPECTOR)}),
    )


def test_papel_da_programacao_semanal_vale_so_no_projeto_em_que_foi_dado() -> None:
    usuario = _com_papeis()

    assert rbac.has_schedule_role(usuario, 1, ScheduleRole.PLANNER)
    assert not rbac.has_schedule_role(usuario, 2, ScheduleRole.PLANNER)
    assert not rbac.has_schedule_role(usuario, 3, ScheduleRole.PLANNER)
    assert rbac.schedule_roles_in(usuario, 3) == frozenset({ScheduleRole.INSPECTOR})
    assert rbac.schedule_roles_in(usuario, 2) == frozenset()


def test_pessoa_pode_ser_fiscal_num_projeto_e_nao_em_outro() -> None:
    usuario = _com_papeis()

    rbac.require_schedule_role(usuario, 3, ScheduleRole.INSPECTOR)
    with pytest.raises(AccessDeniedError) as erro:
        rbac.require_schedule_role(usuario, 1, ScheduleRole.INSPECTOR)

    assert str(erro.value) == (
        "Esta operação exige o papel de Fiscal na Programação Semanal deste projeto."
    )


def test_um_dos_papeis_pedidos_basta_e_a_recusa_lista_todos() -> None:
    usuario = _com_papeis()

    rbac.require_schedule_role(usuario, 1, ScheduleRole.PLANNER, ScheduleRole.INSPECTOR)
    with pytest.raises(AccessDeniedError, match="Planejador ou Fiscal"):
        rbac.require_schedule_role(usuario, 2, ScheduleRole.PLANNER, ScheduleRole.INSPECTOR)


def test_papel_da_programacao_nao_depende_do_perfil_geral() -> None:
    visualizador = _usuario(
        perfil=GeneralProfile.VIEWER,
        papeis=frozenset({(1, ScheduleRole.PLANNER)}),
    )

    assert rbac.has_schedule_role(visualizador, 1, ScheduleRole.PLANNER)
    assert not rbac.can(visualizador, Permission.WRITE)


def test_sem_papel_nenhum_a_pessoa_nao_tem_papel_em_projeto_algum() -> None:
    assert not rbac.has_schedule_role(_usuario(), 1, ScheduleRole.PLANNER)


# ── Segregação de funções ────────────────────────────────────────────────

LB_MENSAGEM = "Quem elabora a linha de base não pode aprová-la."


def test_segregacao_recusa_quando_quem_age_e_quem_fez_o_outro_passo() -> None:
    autor = _usuario(pessoa=10)

    with pytest.raises(AccessDeniedError) as erro:
        rbac.require_segregation(autor, Conflict(person_id=10, message=LB_MENSAGEM))

    assert str(erro.value) == LB_MENSAGEM


def test_segregacao_deixa_passar_outra_pessoa() -> None:
    rbac.require_segregation(_usuario(pessoa=10), Conflict(person_id=11, message=LB_MENSAGEM))


def test_segregacao_nao_recusa_enquanto_o_outro_passo_nao_foi_dado() -> None:
    rbac.require_segregation(_usuario(pessoa=10), Conflict(person_id=None, message=LB_MENSAGEM))


def test_segregacao_com_dois_conflitos_diz_qual_deles_aconteceu() -> None:
    comprador = Conflict(person_id=20, message="O aprovador não pode ser o comprador.")
    recomendou = Conflict(person_id=10, message="O aprovador não pode ser quem recomendou.")

    with pytest.raises(AccessDeniedError) as erro:
        rbac.require_segregation(_usuario(pessoa=10), comprador, recomendou)
    assert str(erro.value) == "O aprovador não pode ser quem recomendou."
    with pytest.raises(AccessDeniedError) as erro:
        rbac.require_segregation(_usuario(pessoa=20), comprador, recomendou)
    assert str(erro.value) == "O aprovador não pode ser o comprador."
    rbac.require_segregation(_usuario(pessoa=30), comprador, recomendou)
