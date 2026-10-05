"""Quem está chamando (ISSUE-011, D7): o principal do Static Web Apps e o seletor da demonstração.

O cadastro de Colaboradores é a fonte de verdade do acesso: conta Microsoft
sem cadastro não entra. Sem principal, só a demonstração tem identidade, pelo
cookie do seletor de perfil; em produção, não ter principal é não entrar.
Costura da fachada de identidade (``core.auth``), com o banco de teste e a
transação desfeita no fim de cada teste.
"""

from __future__ import annotations

import base64

import pytest
from sqlalchemy.orm import Session

from src.core import auth, config
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.rbac import Bond, GeneralProfile, ScheduleRole
from src.modulos.configuracoes.models import Person, Project
from tests.identidades import (
    cabecalho_do_principal,
    cookie_do_seletor,
    criar_colaborador,
    criar_empresa,
    criar_projeto,
    requisicao,
)


@pytest.fixture
def projeto(sessao_das_rotas: Session) -> Project:
    return criar_projeto(sessao_das_rotas, codigo="TN-ACESSO-001", nome="Projeto do acesso")


# ── O principal do Static Web Apps ───────────────────────────────────────


def test_sem_o_cabecalho_nao_ha_principal() -> None:
    assert auth.principal_email(requisicao()) is None


def test_principal_entrega_o_email_em_minusculas() -> None:
    assert auth.principal_email(requisicao(email="  Maria.Souza@Exemplo.COM ")) == (
        "maria.souza@exemplo.com"
    )


@pytest.mark.parametrize(
    "cabecalho",
    [
        "isto não é base64 %%%",
        base64.b64encode(b"base64 valido, mas sem JSON").decode(),
        base64.b64encode(b'["um", "array", "nao", "e", "principal"]').decode(),
        cabecalho_do_principal(None),
        cabecalho_do_principal("fulano-sem-arroba"),
        cabecalho_do_principal("com espaco@exemplo.com"),
    ],
)
def test_principal_malformado_ou_sem_email_e_recusado(cabecalho: str) -> None:
    with pytest.raises(auth.SignInRequiredError):
        auth.principal_email(requisicao(cabecalho_bruto=cabecalho))


def test_pedir_login_e_uma_recusa_de_acesso_com_a_mensagem() -> None:
    erro = auth.SignInRequiredError()

    assert isinstance(erro, AccessDeniedError)
    assert str(erro) == auth.SIGN_IN_MESSAGE


# ── O cadastro de Colaboradores decide ───────────────────────────────────


def test_email_cadastrado_entra_com_perfil_vinculo_empresa_e_papeis(
    sessao_das_rotas: Session, projeto: Project
) -> None:
    empresa = criar_empresa(sessao_das_rotas)
    colaborador = criar_colaborador(
        sessao_das_rotas,
        email="Carlos.Nunes@Exemplo.com",
        nome="Carlos Nunes",
        perfil="Membro",
        vinculo="Fornecedor",
        empresa=empresa,
        papeis=[(projeto.id, "Encarregado")],
    )

    usuario = auth.resolve_user(sessao_das_rotas, requisicao(email="carlos.nunes@exemplo.com"))

    assert usuario.id == colaborador.id
    assert usuario.person_id == colaborador.person_id
    assert usuario.name == "Carlos Nunes"
    assert usuario.general_profile is GeneralProfile.MEMBER
    assert usuario.bond is Bond.SUPPLIER
    assert usuario.company_id == empresa.id
    assert usuario.schedule_roles == frozenset({(projeto.id, ScheduleRole.FOREMAN)})


def test_email_fora_do_cadastro_e_recusado_com_a_conta_usada(sessao_das_rotas: Session) -> None:
    with pytest.raises(auth.NotRegisteredError) as erro:
        auth.resolve_user(sessao_das_rotas, requisicao(email="intruso@example.invalid"))

    assert isinstance(erro.value, AccessDeniedError)
    assert erro.value.email == "intruso@example.invalid"
    assert str(erro.value) == auth.NOT_REGISTERED_MESSAGE


def test_pessoa_do_cadastro_sem_colaborador_nao_entra(sessao_das_rotas: Session) -> None:
    sessao_das_rotas.add(Person(name="Só pessoa", email="so.pessoa@example.invalid"))
    sessao_das_rotas.flush()

    with pytest.raises(auth.NotRegisteredError):
        auth.resolve_user(sessao_das_rotas, requisicao(email="so.pessoa@example.invalid"))


def test_colaborador_desativado_nao_entra_e_a_mensagem_diz_isso(sessao_das_rotas: Session) -> None:
    criar_colaborador(sessao_das_rotas, email="desligado@example.invalid", ativo=False)

    with pytest.raises(auth.NotRegisteredError) as erro:
        auth.resolve_user(sessao_das_rotas, requisicao(email="desligado@example.invalid"))

    assert erro.value.email == "desligado@example.invalid"
    assert str(erro.value) == auth.INACTIVE_MESSAGE


def test_perfil_que_o_cadastro_traz_e_a_plataforma_desconhece_falha_fechado(
    sessao_das_rotas: Session,
) -> None:
    criar_colaborador(sessao_das_rotas, email="estranho@example.invalid", perfil="Superusuário")

    with pytest.raises(auth.NotRegisteredError) as erro:
        auth.resolve_user(sessao_das_rotas, requisicao(email="estranho@example.invalid"))

    assert str(erro.value) == auth.UNKNOWN_PROFILE_MESSAGE


# ── Produção: sem principal não se entra ─────────────────────────────────


def test_em_producao_sem_principal_exige_login_mesmo_com_cookie_do_seletor(
    sessao_das_rotas: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(config.APP_MODE_VARIABLE, config.PRODUCTION)
    admin = criar_colaborador(sessao_das_rotas, email="admin@example.invalid", perfil="Admin")

    with pytest.raises(auth.SignInRequiredError):
        auth.resolve_user(sessao_das_rotas, requisicao(cookies=cookie_do_seletor(admin)))


def test_em_producao_o_principal_cadastrado_entra(
    sessao_das_rotas: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(config.APP_MODE_VARIABLE, config.PRODUCTION)
    gestor = criar_colaborador(sessao_das_rotas, email="gestor@example.invalid", perfil="Gestor")

    usuario = auth.resolve_user(sessao_das_rotas, requisicao(email="gestor@example.invalid"))

    assert usuario.id == gestor.id


# ── Demonstração: o seletor de perfil ────────────────────────────────────


def test_demonstracao_sem_escolha_entra_como_o_primeiro_admin_ativo(
    sessao_das_rotas: Session,
) -> None:
    criar_colaborador(sessao_das_rotas, email="membro@example.invalid", perfil="Membro")
    criar_colaborador(sessao_das_rotas, email="velho@example.invalid", perfil="Admin", ativo=False)
    primeiro = criar_colaborador(sessao_das_rotas, email="primeiro@example.invalid", perfil="Admin")
    criar_colaborador(sessao_das_rotas, email="segundo@example.invalid", perfil="Admin")

    usuario = auth.resolve_user(sessao_das_rotas, requisicao())

    assert usuario.id == primeiro.id


def test_demonstracao_com_escolha_entra_como_a_pessoa_do_cookie(sessao_das_rotas: Session) -> None:
    criar_colaborador(sessao_das_rotas, email="admin@example.invalid", perfil="Admin")
    escolhida = criar_colaborador(
        sessao_das_rotas, email="cliente@example.invalid", perfil="Visualizador", vinculo="Cliente"
    )

    usuario = auth.resolve_user(sessao_das_rotas, requisicao(cookies=cookie_do_seletor(escolhida)))

    assert usuario.id == escolhida.id
    assert usuario.general_profile is GeneralProfile.VIEWER
    assert usuario.bond is Bond.CLIENT


@pytest.mark.parametrize("cookie", ["abc", "-1", "99999999999", "9" * 40, ""])
def test_cookie_do_seletor_que_nao_nomeia_ninguem_volta_ao_admin(
    sessao_das_rotas: Session, cookie: str
) -> None:
    admin = criar_colaborador(sessao_das_rotas, email="admin@example.invalid", perfil="Admin")

    usuario = auth.resolve_user(sessao_das_rotas, requisicao(cookies={auth.DEMO_COOKIE: cookie}))

    assert usuario.id == admin.id


def test_cookie_de_colaborador_desativado_volta_ao_admin(sessao_das_rotas: Session) -> None:
    admin = criar_colaborador(sessao_das_rotas, email="admin@example.invalid", perfil="Admin")
    desligado = criar_colaborador(sessao_das_rotas, email="desligado@example.invalid", ativo=False)

    usuario = auth.resolve_user(sessao_das_rotas, requisicao(cookies=cookie_do_seletor(desligado)))

    assert usuario.id == admin.id


def test_demonstracao_sem_nenhum_admin_ativo_nao_entra(sessao_das_rotas: Session) -> None:
    criar_colaborador(sessao_das_rotas, email="membro@example.invalid", perfil="Membro")

    with pytest.raises(auth.NotRegisteredError) as erro:
        auth.resolve_user(sessao_das_rotas, requisicao())

    assert erro.value.email is None
    assert str(erro.value) == auth.EMPTY_REGISTER_MESSAGE


def test_o_principal_vence_o_seletor_mesmo_na_demonstracao(sessao_das_rotas: Session) -> None:
    do_principal = criar_colaborador(sessao_das_rotas, email="principal@example.invalid")
    do_seletor = criar_colaborador(sessao_das_rotas, email="seletor@example.invalid")

    usuario = auth.resolve_user(
        sessao_das_rotas,
        requisicao(email="principal@example.invalid", cookies=cookie_do_seletor(do_seletor)),
    )

    assert usuario.id == do_principal.id


def test_cabecalho_malformado_nao_cai_no_seletor(sessao_das_rotas: Session) -> None:
    escolhida = criar_colaborador(sessao_das_rotas, email="escolhida@example.invalid")

    with pytest.raises(auth.SignInRequiredError):
        auth.resolve_user(
            sessao_das_rotas,
            requisicao(cabecalho_bruto="%%%", cookies=cookie_do_seletor(escolhida)),
        )


def test_seletor_oferece_so_colaboradores_ativos_e_marca_quem_esta_logado(
    sessao_das_rotas: Session,
) -> None:
    ativa = criar_colaborador(
        sessao_das_rotas, email="ativa@example.invalid", nome="Ana Ativa", perfil="Gestor"
    )
    criar_colaborador(
        sessao_das_rotas, email="inativa@example.invalid", nome="Iná Inativa", ativo=False
    )
    req = requisicao(cookies=cookie_do_seletor(ativa))
    usuario = auth.resolve_user(sessao_das_rotas, req)

    seletor = auth.demo_selector(sessao_das_rotas, req, usuario)

    assert seletor is not None
    assert seletor.current_id == ativa.id
    rotulos = {opcao.id: opcao.label for opcao in seletor.options}
    assert rotulos[ativa.id] == "Ana Ativa · Gestor · Timenow"
    assert not any("Iná Inativa" in rotulo for rotulo in rotulos.values())


def test_seletor_nao_existe_com_principal_nem_em_producao(
    sessao_das_rotas: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    pessoa = criar_colaborador(sessao_das_rotas, email="pessoa@example.invalid")
    com_principal = requisicao(email="pessoa@example.invalid")
    usuario = auth.resolve_user(sessao_das_rotas, com_principal)

    assert auth.demo_selector(sessao_das_rotas, com_principal, usuario) is None
    with pytest.raises(AccessDeniedError, match="só existe no modo demonstração"):
        auth.require_demo_selector(com_principal)

    monkeypatch.setenv(config.APP_MODE_VARIABLE, config.PRODUCTION)
    assert not auth.demo_selector_enabled(requisicao(cookies=cookie_do_seletor(pessoa)))


def test_escolha_do_seletor_exige_pessoa_cadastrada_e_ativa(sessao_das_rotas: Session) -> None:
    ativa = criar_colaborador(sessao_das_rotas, email="ativa@example.invalid")
    inativa = criar_colaborador(sessao_das_rotas, email="inativa@example.invalid", ativo=False)

    assert auth.choose_demo_collaborator(sessao_das_rotas, str(ativa.id)).id == ativa.id
    for invalida in (str(inativa.id), "99999999", "abc", "", None):
        with pytest.raises(InvalidDataError) as erro:
            auth.choose_demo_collaborator(sessao_das_rotas, invalida)
        assert erro.value.messages() == [auth.DEMO_CHOICE_MESSAGE]


def test_cookie_do_seletor_guarda_a_pessoa_so_ate_fechar_o_navegador() -> None:
    atributos = auth.demo_cookie_header(7, secure=False).split("; ")

    assert atributos[0] == "gestnow_demo_perfil=7"
    assert {"Path=/", "SameSite=Lax", "HttpOnly"} <= set(atributos)
    assert not any(atributo.startswith("Max-Age") for atributo in atributos)
    assert "Secure" not in atributos
    assert "Secure" in auth.demo_cookie_header(7, secure=True).split("; ")
