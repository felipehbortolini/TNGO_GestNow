"""As rotas da tela Colaboradores (ISSUE-077): tela, filtros, gravação, papéis, último Admin e revogação.

O handler é chamado com a requisição de Alpine, o cookie da demonstração identificando a pessoa
e a unidade de trabalho do teste (fixture ``sessao``). Só o Admin alcança a tela e as gravações
(``Permission.ADMINISTER``); a fachada de gravação é exercitada pela rota, com a trilha e o gate
lidos no banco do teste.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from urllib.parse import unquote, urlencode

import azure.functions as func
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import audit, auth
from src.core.auth import DEMO_COOKIE
from src.core.models import AuditEntry
from src.core.rbac import User
from src.modulos.configuracoes import routes, service
from src.modulos.configuracoes.models import CollaboratorScheduleRole, Person
from tests.apoio_riscos import Cenario
from tests.identidades import criar_colaborador, criar_empresa, requisicao

TELA = "/api/configuracoes/colaboradores"
MODAL = "colaboradores-modal-corpo"
CONTEUDO = "colaboradores-conteudo"
ULTIMO_ADMIN = service.LAST_ADMIN_MESSAGE


def _requisicao(
    usuario: User,
    *,
    metodo: str = "GET",
    caminho: str = TELA,
    params: Mapping[str, str] | None = None,
    rota: Mapping[str, str] | None = None,
    corpo: Mapping[str, str | Sequence[str]] | None = None,
    alvo: str = CONTEUDO,
    cabecalho: bool = True,
) -> func.HttpRequest:
    headers = {"X-Alpine-Target": alvo, "Cookie": f"{DEMO_COOKIE}={usuario.id}"}
    if cabecalho:
        headers["X-Alpine-Request"] = "true"
    if corpo is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    return func.HttpRequest(
        method=metodo,
        url=caminho,
        headers=headers,
        params=dict(params or {}),
        route_params=dict(rota or {}),
        body=urlencode(corpo, doseq=True).encode() if corpo is not None else b"",
    )


def _corpo(**mudancas: str | Sequence[str]) -> dict[str, str | Sequence[str]]:
    base: dict[str, str | Sequence[str]] = {
        "nome": "Nina Nova",
        "email": "nina.nova@example.invalid",
        "funcao": "Fiscal de campo",
        "perfil": "Membro",
        "vinculo": "Timenow",
        "empresa": "",
        "ativo": "sim",
    }
    base.update(mudancas)
    return base


def _gravar(
    cenario: Cenario, corpo: Mapping[str, str | Sequence[str]], usuario: User | None = None
) -> func.HttpResponse:
    return routes.collaborators_save(
        _requisicao(usuario or cenario.ada, metodo="POST", corpo=corpo, alvo=MODAL)
    )


def _atualizar(
    cenario: Cenario,
    colaborador_id: int,
    corpo: Mapping[str, str | Sequence[str]],
    usuario: User | None = None,
) -> func.HttpResponse:
    return routes.collaborators_update(
        _requisicao(
            usuario or cenario.ada,
            metodo="POST",
            caminho=f"{TELA}/{colaborador_id}",
            rota={"id": str(colaborador_id)},
            corpo=corpo,
            alvo=MODAL,
        )
    )


def _revogar(
    cenario: Cenario, colaborador_id: int, usuario: User | None = None
) -> func.HttpResponse:
    return routes.collaborators_revoke(
        _requisicao(
            usuario or cenario.ada,
            metodo="POST",
            caminho=f"{TELA}/{colaborador_id}/revogar",
            rota={"id": str(colaborador_id)},
        )
    )


def _papeis(sessao: Session, colaborador_id: int) -> list[tuple[int, str]]:
    statement = (
        select(CollaboratorScheduleRole.project_id, CollaboratorScheduleRole.role)
        .where(CollaboratorScheduleRole.collaborator_id == colaborador_id)
        .order_by(CollaboratorScheduleRole.project_id, CollaboratorScheduleRole.role)
    )
    return [(row.project_id, row.role) for row in sessao.execute(statement)]


def _trilha(sessao: Session, entidade: str, acao: str) -> list[AuditEntry]:
    statement = select(AuditEntry).where(AuditEntry.entity == entidade, AuditEntry.action == acao)
    return list(sessao.scalars(statement))


# ── O acesso ─────────────────────────────────────────────────────────────────────────────────


def test_o_admin_chega_a_tela_e_as_outras_pessoas_recebem_403(cenario: Cenario) -> None:
    tela = routes.collaborators_screen(_requisicao(cenario.ada))
    gravacao = _gravar(cenario, _corpo())
    revogacao = _revogar(cenario, cenario.mario.id)

    assert tela.status_code == 200
    assert gravacao.status_code == 200
    assert revogacao.status_code == 200


@pytest.mark.parametrize("perfil", ["gil", "mario", "vera"])
def test_quem_nao_e_admin_recebe_403_na_tela_na_gravacao_e_na_revogacao(
    cenario: Cenario, perfil: str
) -> None:
    usuario: User = getattr(cenario, perfil)

    tela = routes.collaborators_screen(_requisicao(usuario))
    gravacao = _gravar(cenario, _corpo(), usuario=usuario)
    revogacao = _revogar(cenario, cenario.mario.id, usuario=usuario)

    assert tela.status_code == 403
    assert gravacao.status_code == 403
    assert revogacao.status_code == 403
    assert "exige o perfil" in tela.get_body().decode()


def test_sem_o_cabecalho_do_alpine_a_tela_manda_para_o_shell(cenario: Cenario) -> None:
    resposta = routes.collaborators_screen(_requisicao(cenario.ada, cabecalho=False))

    assert resposta.status_code == 302


# ── A tela ───────────────────────────────────────────────────────────────────────────────────


def test_a_tela_lista_os_colaboradores_os_kpis_e_os_avisos(cenario: Cenario) -> None:
    resposta = routes.collaborators_screen(_requisicao(cenario.ada))

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    for nome in ("Ada Admin", "Gil Gestor", "Mário Membro", "Vera Visualizadora"):
        assert nome in corpo
    assert "Esta tela controla quem entra no sistema." in corpo
    assert "Fiscais e encarregados saem daqui." in corpo
    assert "Quem tem acesso hoje" in corpo
    assert "Liberar acesso" in corpo
    assert 'data-situacao="conteudo"' in corpo
    assert 'data-tn-excel="/api/configuracoes/colaboradores/excel"' in corpo
    assert 'data-tn-pdf="/api/configuracoes/colaboradores/imprimivel"' in corpo


def test_a_busca_filtra_no_servidor_por_nome_e_por_email(cenario: Cenario) -> None:
    por_nome = routes.collaborators_screen(_requisicao(cenario.ada, params={"busca": "vera"}))
    por_email = routes.collaborators_screen(
        _requisicao(cenario.ada, params={"busca": "mario.membro"})
    )

    texto_do_nome = por_nome.get_body().decode()
    assert "Vera Visualizadora" in texto_do_nome
    assert "Gil Gestor" not in texto_do_nome
    texto_do_email = por_email.get_body().decode()
    assert "Mário Membro" in texto_do_email
    assert "Vera Visualizadora" not in texto_do_email


def test_o_filtro_de_perfil_e_de_vinculo_filtra_no_servidor(
    sessao: Session, cenario: Cenario
) -> None:
    criar_colaborador(
        sessao, email="cliente@example.invalid", nome="Clara Cliente", vinculo="Cliente"
    )

    por_perfil = routes.collaborators_screen(
        _requisicao(cenario.ada, params={"perfil": "Visualizador"})
    )
    por_vinculo = routes.collaborators_screen(
        _requisicao(cenario.ada, params={"vinculo": "Cliente"})
    )

    texto_do_perfil = por_perfil.get_body().decode()
    assert "Vera Visualizadora" in texto_do_perfil
    assert "Ada Admin" not in texto_do_perfil
    assert 'value="Visualizador" selected' in texto_do_perfil
    texto_do_vinculo = por_vinculo.get_body().decode()
    assert "Clara Cliente" in texto_do_vinculo
    assert "Ada Admin" not in texto_do_vinculo


def test_filtro_sem_resultado_mostra_o_vazio_por_filtro(cenario: Cenario) -> None:
    resposta = routes.collaborators_screen(_requisicao(cenario.ada, params={"busca": "zzz"}))

    corpo = resposta.get_body().decode()
    assert 'data-situacao="vazio-filtro"' in corpo
    assert "Nenhum colaborador encontrado com os filtros atuais" in corpo


# ── A gravação ───────────────────────────────────────────────────────────────────────────────


def test_fornecedor_sem_empresa_e_recusado(sessao: Session, cenario: Cenario) -> None:
    resposta = _gravar(cenario, _corpo(vinculo="Fornecedor", empresa=""))

    assert resposta.status_code == 422
    assert "Escolha a empresa da pessoa." in resposta.get_body().decode()
    assert service.find_access_by_email(sessao, "nina.nova@example.invalid") is None


def test_empresa_fora_do_cadastro_e_recusada(cenario: Cenario) -> None:
    resposta = _gravar(cenario, _corpo(vinculo="Fornecedor", empresa="999999"))

    assert resposta.status_code == 422
    assert "Empresa fora do cadastro." in resposta.get_body().decode()


def test_email_invalido_e_recusado(cenario: Cenario) -> None:
    resposta = _gravar(cenario, _corpo(email="sem-arroba"))

    assert resposta.status_code == 422
    assert "Informe um e-mail corporativo válido." in resposta.get_body().decode()


def test_email_de_quem_ja_tem_acesso_e_recusado(sessao: Session, cenario: Cenario) -> None:
    resposta = _gravar(cenario, _corpo(email=cenario.gil.email))

    assert resposta.status_code == 422
    assert "Já existe um acesso com este e-mail." in resposta.get_body().decode()
    assert service.find_access_by_email(sessao, "nina.nova@example.invalid") is None


def test_perfil_e_vinculo_fora_da_lista_sao_recusados(cenario: Cenario) -> None:
    perfil = _gravar(cenario, _corpo(perfil="Supervisor"))
    vinculo = _gravar(cenario, _corpo(vinculo="Parceiro"))

    assert perfil.status_code == 422
    assert "Escolha um perfil." in perfil.get_body().decode()
    assert vinculo.status_code == 422
    assert "Escolha o vínculo." in vinculo.get_body().decode()


def test_gravar_cria_a_pessoa_o_acesso_e_os_papeis(sessao: Session, cenario: Cenario) -> None:
    resposta = _gravar(
        cenario,
        _corpo(
            nome="  Nina Nova ",
            email="NINA.NOVA@example.invalid",
            papeis=[
                f"{cenario.outro.id}:Encarregado",
                f"{cenario.projeto.id}:Fiscal",
                f"{cenario.projeto.id}:Fiscal",
            ],
        ),
    )

    assert resposta.status_code == 200
    assert unquote(resposta.headers["X-TN-Toast"]) == "Acesso de Nina Nova liberado."
    acesso = service.find_access_by_email(sessao, "nina.nova@example.invalid")
    assert acesso is not None
    assert acesso.name == "Nina Nova"
    assert acesso.email == "nina.nova@example.invalid"
    assert acesso.general_profile == "Membro"
    assert acesso.bond == "Timenow"
    assert acesso.active is True
    assert acesso.schedule_roles == (
        (cenario.projeto.id, "Fiscal"),
        (cenario.outro.id, "Encarregado"),
    )
    pessoa = sessao.get(Person, acesso.person_id)
    assert pessoa is not None and pessoa.role == "Fiscal de campo"
    assert _trilha(sessao, "colaborador", audit.CREATED)
    assert _trilha(sessao, "pessoa", audit.CREATED)


def test_o_colaborador_novo_entra_na_requisicao_seguinte(sessao: Session, cenario: Cenario) -> None:
    _gravar(cenario, _corpo(email="nina.nova@example.invalid"))

    acesso = service.find_access_by_email(sessao, "nina.nova@example.invalid")
    assert acesso is not None
    usuario = auth.resolve_user(
        sessao, requisicao("/api/nav", cookies={DEMO_COOKIE: str(acesso.id)})
    )
    assert usuario.id == acesso.id


def test_atualizar_muda_o_acesso_e_a_pessoa(sessao: Session, cenario: Cenario) -> None:
    resposta = _atualizar(
        cenario,
        cenario.mario.id,
        _corpo(
            nome="Mário Editado",
            email=cenario.mario.email,
            funcao="Coordenador",
            perfil="Gestor",
            vinculo="Cliente",
        ),
    )

    assert resposta.status_code == 200
    assert unquote(resposta.headers["X-TN-Toast"]) == "Acesso de Mário Editado atualizado."
    acesso = service.find_access(sessao, cenario.mario.id)
    assert acesso is not None
    assert acesso.general_profile == "Gestor"
    assert acesso.bond == "Cliente"
    assert acesso.schedule_roles == ()
    pessoa = sessao.get(Person, cenario.mario.person_id)
    assert pessoa is not None
    assert pessoa.name == "Mário Editado"
    assert pessoa.role == "Coordenador"
    assert _trilha(sessao, "colaborador", audit.UPDATED)


def test_editar_sem_empresa_limpa_a_empresa_do_fornecedor(
    sessao: Session, cenario: Cenario
) -> None:
    empresa = criar_empresa(sessao, "Contratada Alfa")
    fornecedor = service.save_collaborator(
        sessao,
        author_id=cenario.ada.id,
        collaborator_id=None,
        name="Fábio Fornecedor",
        email="fabio@example.invalid",
        role="Encarregado",
        profile="Membro",
        bond="Fornecedor",
        company_id=empresa.id,
        active=True,
        roles=[],
    )

    _atualizar(
        cenario,
        fornecedor.id,
        _corpo(
            nome="Fábio Fornecedor",
            email="fabio@example.invalid",
            perfil="Membro",
            vinculo="Timenow",
        ),
    )

    acesso = service.find_access(sessao, fornecedor.id)
    assert acesso is not None and acesso.company_id is None


# ── Os papéis por projeto ────────────────────────────────────────────────────────────────────


def test_regravar_os_mesmos_papeis_nao_duplica(sessao: Session, cenario: Cenario) -> None:
    corpo = _corpo(papeis=[f"{cenario.projeto.id}:Fiscal", f"{cenario.outro.id}:Encarregado"])
    primeira = _gravar(cenario, corpo)
    acesso = service.find_access_by_email(sessao, "nina.nova@example.invalid")
    assert acesso is not None

    segunda = _atualizar(cenario, acesso.id, corpo)

    assert primeira.status_code == 200 and segunda.status_code == 200
    assert _papeis(sessao, acesso.id) == [
        (cenario.projeto.id, "Fiscal"),
        (cenario.outro.id, "Encarregado"),
    ]


def test_remover_um_papel_apaga_so_ele(sessao: Session, cenario: Cenario) -> None:
    _gravar(
        cenario,
        _corpo(papeis=[f"{cenario.projeto.id}:Fiscal", f"{cenario.outro.id}:Encarregado"]),
    )
    acesso = service.find_access_by_email(sessao, "nina.nova@example.invalid")
    assert acesso is not None

    resposta = _atualizar(
        cenario,
        acesso.id,
        _corpo(
            nome="Nina Nova",
            email="nina.nova@example.invalid",
            papeis=[f"{cenario.outro.id}:Encarregado"],
        ),
    )

    assert resposta.status_code == 200
    assert _papeis(sessao, acesso.id) == [(cenario.outro.id, "Encarregado")]


def test_papel_invalido_e_recusado_sem_gravar(sessao: Session, cenario: Cenario) -> None:
    resposta = _gravar(cenario, _corpo(papeis=[f"{cenario.projeto.id}:Diretor"]))

    assert resposta.status_code == 422
    assert "Escolha um papel da Programação Semanal." in resposta.get_body().decode()
    assert service.find_access_by_email(sessao, "nina.nova@example.invalid") is None


def test_projeto_fora_do_cadastro_e_recusado(cenario: Cenario) -> None:
    resposta = _gravar(cenario, _corpo(papeis=["999999:Fiscal"]))

    assert resposta.status_code == 422
    assert "Projeto fora do cadastro." in resposta.get_body().decode()


# ── O último Admin ───────────────────────────────────────────────────────────────────────────


def test_rebaixar_o_ultimo_admin_e_recusado(sessao: Session, cenario: Cenario) -> None:
    resposta = _atualizar(
        cenario,
        cenario.ada.id,
        _corpo(nome="Ada Admin", email=cenario.ada.email, perfil="Gestor"),
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 422
    assert ULTIMO_ADMIN in corpo
    assert 'id="erro-perfil"' in corpo
    acesso = service.find_access(sessao, cenario.ada.id)
    assert acesso is not None and acesso.general_profile == "Admin"


def test_desativar_o_ultimo_admin_e_recusado(sessao: Session, cenario: Cenario) -> None:
    corpo_da_edicao = _corpo(nome="Ada Admin", email=cenario.ada.email, perfil="Admin")
    corpo_da_edicao.pop("ativo")

    resposta = _atualizar(cenario, cenario.ada.id, corpo_da_edicao)

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 422
    assert ULTIMO_ADMIN in corpo
    assert 'id="erro-ativo"' in corpo
    acesso = service.find_access(sessao, cenario.ada.id)
    assert acesso is not None and acesso.active is True


def test_revogar_o_ultimo_admin_e_recusado(sessao: Session, cenario: Cenario) -> None:
    resposta = _revogar(cenario, cenario.ada.id)

    assert resposta.status_code == 422
    assert unquote(resposta.headers["X-TN-Toast"]) == ULTIMO_ADMIN
    assert service.find_access(sessao, cenario.ada.id) is not None


def test_com_dois_admins_ativos_rebaixar_um_passa(sessao: Session, cenario: Cenario) -> None:
    criar_colaborador(sessao, email="novo.admin@example.invalid", nome="Novo Admin", perfil="Admin")

    resposta = _atualizar(
        cenario,
        cenario.ada.id,
        _corpo(nome="Ada Admin", email=cenario.ada.email, perfil="Gestor"),
    )

    assert resposta.status_code == 200
    acesso = service.find_access(sessao, cenario.ada.id)
    assert acesso is not None and acesso.general_profile == "Gestor"


def test_com_dois_admins_ativos_revogar_um_passa(sessao: Session, cenario: Cenario) -> None:
    segundo = criar_colaborador(
        sessao, email="novo.admin@example.invalid", nome="Novo Admin", perfil="Admin"
    )

    resposta = _revogar(cenario, segundo.id)

    assert resposta.status_code == 200
    assert service.find_access(sessao, segundo.id) is None
    acesso = service.find_access(sessao, cenario.ada.id)
    assert acesso is not None and acesso.general_profile == "Admin"


def test_revogar_quem_ja_deixou_trilha_e_recusado_com_a_orientacao_de_suspender(
    sessao: Session, cenario: Cenario
) -> None:
    criar_colaborador(sessao, email="novo.admin@example.invalid", nome="Novo Admin", perfil="Admin")

    resposta = _revogar(cenario, cenario.ada.id)

    assert resposta.status_code == 422
    assert unquote(resposta.headers["X-TN-Toast"]) == service.REVOKE_REFERENCED_MESSAGE
    acesso = service.find_access(sessao, cenario.ada.id)
    assert acesso is not None and acesso.active is True


# ── A revogação ──────────────────────────────────────────────────────────────────────────────


def test_revogar_apaga_o_acesso_e_os_papeis_e_a_pessoa_fica(
    sessao: Session, cenario: Cenario
) -> None:
    _gravar(
        cenario, _corpo(email="nina.nova@example.invalid", papeis=[f"{cenario.projeto.id}:Fiscal"])
    )
    acesso = service.find_access_by_email(sessao, "nina.nova@example.invalid")
    assert acesso is not None

    resposta = _revogar(cenario, acesso.id)

    assert resposta.status_code == 200
    assert (
        unquote(resposta.headers["X-TN-Toast"]) == "Acesso de nina.nova@example.invalid revogado."
    )
    assert service.find_access(sessao, acesso.id) is None
    assert service.find_access_by_email(sessao, "nina.nova@example.invalid") is None
    assert _papeis(sessao, acesso.id) == []
    assert sessao.get(Person, acesso.person_id) is not None
    with pytest.raises(auth.NotRegisteredError):
        auth.resolve_user(sessao, requisicao("/api/nav", email="nina.nova@example.invalid"))


def test_revogar_um_fornecedor_com_empresa_e_aceito(sessao: Session, cenario: Cenario) -> None:
    empresa = criar_empresa(sessao, "Contratada Beta")
    fornecedor = service.save_collaborator(
        sessao,
        author_id=cenario.ada.id,
        collaborator_id=None,
        name="Fábio Fornecedor",
        email="fabio@example.invalid",
        role="",
        profile="Membro",
        bond="Fornecedor",
        company_id=empresa.id,
        active=True,
        roles=[],
    )

    resposta = _revogar(cenario, fornecedor.id)

    assert resposta.status_code == 200
    assert service.find_access(sessao, fornecedor.id) is None


# ── O modal ──────────────────────────────────────────────────────────────────────────────────


def test_o_modal_novo_traz_os_campos_vazios_e_os_projetos(cenario: Cenario) -> None:
    resposta = routes.collaborators_new_form(_requisicao(cenario.ada, alvo=MODAL))

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert 'action="/api/configuracoes/colaboradores"' in corpo
    assert "Liberar um novo acesso" not in corpo  # o título é do modal, não do corpo
    assert "Papéis na Programação Semanal" in corpo
    assert cenario.projeto.code in corpo
    assert "Liberar acesso" in corpo


def test_o_modal_de_edicao_bloqueia_o_email_e_traz_os_papeis(
    sessao: Session, cenario: Cenario
) -> None:
    _gravar(
        cenario,
        _corpo(
            nome="Nina Nova",
            email="nina.nova@example.invalid",
            papeis=[f"{cenario.projeto.id}:Fiscal"],
        ),
    )
    acesso = service.find_access_by_email(sessao, "nina.nova@example.invalid")
    assert acesso is not None

    resposta = routes.collaborators_edit_form(
        _requisicao(
            cenario.ada,
            caminho=f"{TELA}/{acesso.id}/editar",
            rota={"id": str(acesso.id)},
            alvo=MODAL,
        )
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert f'action="{TELA}/{acesso.id}"' in corpo
    assert "readonly" in corpo
    assert "Salvar alterações" in corpo
    assert "Nina Nova" in corpo
    assert cenario.projeto.code in corpo
    assert 'data-vinculo="Timenow"' in corpo


def test_modal_de_uma_pessoa_fora_do_cadastro_volta_no_modal(cenario: Cenario) -> None:
    resposta = routes.collaborators_edit_form(
        _requisicao(cenario.ada, caminho=f"{TELA}/999999/editar", rota={"id": "999999"}, alvo=MODAL)
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 422
    assert service.COLLABORATOR_NOT_FOUND in corpo
    assert f'id="{MODAL}"' in corpo
    assert 'id="parametros-modal-corpo"' not in corpo


# ── As exportações ───────────────────────────────────────────────────────────────────────────


def test_excel_e_imprimivel_saem_com_a_lista(cenario: Cenario) -> None:
    excel = routes.collaborators_excel(
        _requisicao(cenario.ada, caminho=f"{TELA}/excel", alvo=CONTEUDO)
    )
    imprimivel = routes.collaborators_printable(
        _requisicao(cenario.ada, caminho=f"{TELA}/imprimivel", alvo=CONTEUDO)
    )

    assert excel.status_code == 200
    assert excel.get_body().startswith(b"PK")
    texto = imprimivel.get_body().decode()
    assert imprimivel.status_code == 200
    assert "Quem tem acesso hoje" in texto
    assert "Ada Admin" in texto
    assert "Suspenso" not in texto
    assert "<script" not in texto


def test_o_imprimivel_marca_a_situacao_e_os_papeis(cenario: Cenario) -> None:
    _gravar(
        cenario,
        _corpo(
            nome="Nina Nova",
            email="nina.nova@example.invalid",
            papeis=[f"{cenario.projeto.id}:Fiscal"],
        ),
    )

    resposta = routes.collaborators_printable(
        _requisicao(cenario.ada, caminho=f"{TELA}/imprimivel", alvo=CONTEUDO)
    )

    texto = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "Nina Nova" in texto
    assert f"{cenario.projeto.code} · Fiscal" in texto
    assert "Ativo" in texto
