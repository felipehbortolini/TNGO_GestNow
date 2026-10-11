"""As rotas da tela Cadastros de apoio (ISSUE-078): tela, modais, gravação, exclusão e exports.

O handler é chamado com a requisição de Alpine, o cookie da demonstração identificando a pessoa
e a unidade de trabalho do teste (fixture ``sessao``). Só Gestor e Admin alcançam a tela
(``Permission.CONFIGURE``); a gravação de um projeto cria a configuração padrão da Programação
Semanal, reusa ou cria o cliente e grava as notas na versão vigente do portfólio; a exclusão em
uso é recusada com a mensagem de onde o registro é usado.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from urllib.parse import unquote, urlencode

import azure.functions as func
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import audit
from src.core.auth import DEMO_COOKIE
from src.core.models import AuditEntry, Client
from src.core.rbac import User
from src.modulos.configuracoes import routes, service
from src.modulos.configuracoes.models import (
    Collaborator,
    Company,
    Discipline,
    Location,
    Person,
    Project,
    Unit,
)
from src.modulos.configuracoes.models import (
    System as SupportSystem,
)
from src.modulos.planejamento.models import EapItem
from src.modulos.programacao_semanal import repository as programacao_repository
from src.modulos.qualidade.models import Itp
from tests.apoio_riscos import REFERENCIA, Cenario, usuario_de
from tests.identidades import criar_colaborador, criar_empresa, criar_projeto

TELA = "/api/configuracoes/cadastros"
MODAL = "cadastros-modal-corpo"
CONTEUDO = "cadastros-conteudo"

MODELOS = {
    "empresa": Company,
    "pessoa": Person,
    "projeto": Project,
    "sistema": SupportSystem,
    "unidade": Unit,
    "local": Location,
    "disciplina": Discipline,
}


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


def _gravar(
    cenario: Cenario,
    tipo: str,
    corpo: Mapping[str, str | Sequence[str]],
    usuario: User | None = None,
) -> func.HttpResponse:
    return routes.registers_save(
        _requisicao(
            usuario or cenario.gil,
            metodo="POST",
            caminho=f"{TELA}/{tipo}",
            rota={"tipo": tipo},
            corpo=corpo,
            alvo=MODAL,
        )
    )


def _atualizar(
    cenario: Cenario,
    tipo: str,
    registro_id: int,
    corpo: Mapping[str, str | Sequence[str]],
    usuario: User | None = None,
) -> func.HttpResponse:
    return routes.registers_update(
        _requisicao(
            usuario or cenario.gil,
            metodo="POST",
            caminho=f"{TELA}/{tipo}/{registro_id}",
            rota={"tipo": tipo, "id": str(registro_id)},
            corpo=corpo,
            alvo=MODAL,
        )
    )


def _excluir(
    cenario: Cenario, tipo: str, registro_id: int, usuario: User | None = None
) -> func.HttpResponse:
    return routes.registers_delete(
        _requisicao(
            usuario or cenario.gil,
            metodo="POST",
            caminho=f"{TELA}/{tipo}/{registro_id}/excluir",
            rota={"tipo": tipo, "id": str(registro_id)},
        )
    )


def _formulario(
    cenario: Cenario, tipo: str, *, registro_id: int | None = None, **params: str
) -> func.HttpResponse:
    caminho = f"{TELA}/{tipo}/{'novo' if registro_id is None else f'{registro_id}/editar'}"
    rota = {"tipo": tipo} if registro_id is None else {"tipo": tipo, "id": str(registro_id)}
    return (routes.registers_new_form if registro_id is None else routes.registers_edit_form)(
        _requisicao(cenario.gil, caminho=caminho, rota=rota, params=params, alvo=MODAL)
    )


def _corpo_empresa(**mudancas: str) -> dict[str, str]:
    base = {"nome": "Contratada Alfa", "tipo": "Contratada"}
    base.update(mudancas)
    return base


def _corpo_pessoa(**mudancas: str) -> dict[str, str]:
    base = {
        "nome": "Nina Nova",
        "funcao": "Engenheira",
        "empresa": "",
        "email": "nina@example.invalid",
    }
    base.update(mudancas)
    return base


def _corpo_projeto(cenario: Cenario, **mudancas: str) -> dict[str, str]:
    base = {
        "codigo": "TN-900",
        "nome": "Projeto de teste",
        "cliente_nome": "Cliente de teste",
        "cliente_sigla": "CT",
        "gerente": str(cenario.mario.person_id),
        "pep": "PEP-900",
        "apetite": "moderado",
        "inicio": "2026-10-01",
        "termino_previsto": "2027-10-01",
        "orcamento": "R$ 1.234,56",
        "padrao_ata": "",
        "padrao_risco": "",
        "padrao_punch": "",
        "nota_estrategico": "4",
        "nota_complexidade": "3",
    }
    base.update(mudancas)
    return base


def _corpo_sistema(cenario: Cenario, **mudancas: str) -> dict[str, str]:
    base = {
        "projeto": str(cenario.projeto.id),
        "codigo": "SIS-01",
        "nome": "Sistema de teste",
        "area": "Área 100",
    }
    base.update(mudancas)
    return base


def _corpo_unidade(**mudancas: str) -> dict[str, str]:
    base = {"tipo": "medida", "codigo": "cx", "nome": "Caixa"}
    base.update(mudancas)
    return base


def _corpo_local(cenario: Cenario, **mudancas: str) -> dict[str, str]:
    base = {"projeto": str(cenario.projeto.id), "codigo": "L-01", "nome": "Pátio"}
    base.update(mudancas)
    return base


def _corpo_disciplina(**mudancas: str) -> dict[str, str]:
    base = {"nome": "Elétrica"}
    base.update(mudancas)
    return base


def _trilha(sessao: Session, entidade: str, acao: str) -> list[AuditEntry]:
    statement = select(AuditEntry).where(AuditEntry.entity == entidade, AuditEntry.action == acao)
    return list(sessao.scalars(statement))


def _notas(sessao: Session, project_id: int) -> dict[str, int]:
    return service.portfolio_grades(sessao, reference_date=REFERENCIA).get(project_id, {})


# ── O acesso ─────────────────────────────────────────────────────────────────────────────────


def test_gestor_e_admin_chegam_a_tela_e_as_gravacoes(cenario: Cenario) -> None:
    tela = routes.registers_screen(_requisicao(cenario.gil))
    tela_admin = routes.registers_screen(_requisicao(cenario.ada))
    gravacao = _gravar(cenario, "empresa", _corpo_empresa())

    assert tela.status_code == 200
    assert tela_admin.status_code == 200
    assert gravacao.status_code == 200


def test_o_fornecedor_nao_alcanca_a_tela_nem_as_gravacoes(
    sessao: Session, cenario: Cenario
) -> None:
    empresa = criar_empresa(sessao, "Contratada Fornecedor")
    fornecedor = usuario_de(
        sessao,
        criar_colaborador(
            sessao,
            email="fornecedor@example.invalid",
            nome="Fábio Fornecedor",
            vinculo="Fornecedor",
            empresa=empresa,
        ),
    )

    tela = routes.registers_screen(_requisicao(fornecedor))
    gravacao = _gravar(cenario, "empresa", _corpo_empresa(), usuario=fornecedor)

    assert tela.status_code == 403
    assert gravacao.status_code == 403


@pytest.mark.parametrize("perfil", ["mario", "vera"])
def test_quem_nao_configura_recebe_403(cenario: Cenario, perfil: str) -> None:
    usuario: User = getattr(cenario, perfil)

    tela = routes.registers_screen(_requisicao(usuario))
    gravacao = _gravar(cenario, "empresa", _corpo_empresa(), usuario=usuario)

    assert tela.status_code == 403
    assert gravacao.status_code == 403


def test_sem_o_cabecalho_do_alpine_a_tela_manda_para_o_shell(cenario: Cenario) -> None:
    resposta = routes.registers_screen(_requisicao(cenario.gil, cabecalho=False))

    assert resposta.status_code == 302


# ── A tela ───────────────────────────────────────────────────────────────────────────────────


def test_a_tela_lista_os_sete_cadastros(cenario: Cenario) -> None:
    resposta = routes.registers_screen(_requisicao(cenario.gil))

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    for titulo in (
        "Empresas",
        "Pessoas",
        "Projetos",
        "Sistemas",
        "Unidades",
        "Locais",
        "Disciplinas",
    ):
        assert f'<h2 class="h-card4">{titulo}</h2>' in corpo
    assert (
        corpo.count("Nada cadastrado ainda.") == 5
    )  # empresas, sistemas, unidades, locais e disciplinas
    assert 'data-tn-excel="/api/configuracoes/cadastros/excel"' in corpo
    assert 'data-tn-pdf="/api/configuracoes/cadastros/imprimivel"' in corpo
    assert f'data-cadastros-modal-url="{TELA}/empresa/novo"' in corpo
    assert f'data-cadastros-modal-url="{TELA}/projeto/novo"' in corpo


def test_a_tela_mostra_os_registros_do_cenario(cenario: Cenario) -> None:
    resposta = routes.registers_screen(_requisicao(cenario.gil))

    corpo = resposta.get_body().decode()
    assert cenario.projeto.code in corpo
    assert "Cliente TN-RSK-001" in corpo
    assert "Gerente TN-RSK-001" in corpo
    assert "Ada Admin" in corpo  # a pessoa do cenário
    assert f'data-cadastros-excluir-url="{TELA}/projeto/{cenario.projeto.id}/excluir"' in corpo
    assert f'data-cadastros-modal-url="{TELA}/projeto/{cenario.projeto.id}/editar"' in corpo


# ── Os modais ────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("tipo", "marcas"),
    [
        ("empresa", ("Nome da empresa", "Tipo")),
        ("pessoa", ("E-mail", "Empresa")),
        ("projeto", ("Código", "Gerente do projeto", "Apetite a risco", "Orçamento")),
        ("sistema", ("Projeto", "Área")),
        ("unidade", ("Tipo", "Código")),
        ("local", ("Projeto", "Código")),
        ("disciplina", ("Nome da disciplina",)),
    ],
)
def test_o_modal_novo_de_cada_tipo_traz_os_campos(
    cenario: Cenario, tipo: str, marcas: tuple[str, ...]
) -> None:
    resposta = _formulario(cenario, tipo)

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert f'action="{TELA}/{tipo}"' in corpo
    assert 'id="cadastros-modal-corpo"' in corpo
    for marca in marcas:
        assert marca in corpo
    assert "Cancelar" in corpo


def test_o_modal_do_sistema_e_do_local_ja_vem_com_o_projeto_do_escopo(cenario: Cenario) -> None:
    sistema = _formulario(cenario, "sistema", projeto=str(cenario.projeto.id))
    local = _formulario(cenario, "local", projeto=str(cenario.projeto.id))

    assert f'value="{cenario.projeto.id}" selected' in sistema.get_body().decode()
    assert f'value="{cenario.projeto.id}" selected' in local.get_body().decode()


def test_o_modal_de_edicao_do_projeto_traz_os_campos_e_as_notas(
    sessao: Session, cenario: Cenario
) -> None:
    _gravar(cenario, "projeto", _corpo_projeto(cenario))
    projeto = service.find_project_id(sessao, "TN-900")
    assert projeto is not None

    resposta = _formulario(cenario, "projeto", registro_id=projeto)

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert f'action="{TELA}/projeto/{projeto}"' in corpo
    assert 'value="TN-900"' in corpo
    assert 'value="Cliente de teste"' in corpo
    assert 'value="CT"' in corpo
    assert 'value="R$ 1.234,56"' in corpo
    assert f'value="{cenario.mario.person_id}" selected' in corpo
    assert 'value="moderado" selected' in corpo
    assert 'name="nota_estrategico"' in corpo
    assert 'value="4"' in corpo
    assert "Salvar alterações" in corpo


def test_modal_de_registro_fora_do_cadastro_volta_no_modal(cenario: Cenario) -> None:
    resposta = _formulario(cenario, "empresa", registro_id=999_999)

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 422
    assert service.REGISTER_RECORD_NOT_FOUND in corpo
    assert f'id="{MODAL}"' in corpo


def test_tipo_desconhecido_e_recusado(cenario: Cenario) -> None:
    resposta = _formulario(cenario, "pais")

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 422
    assert service.REGISTER_NOT_FOUND in corpo
    assert f'id="{MODAL}"' in corpo


# ── Empresas ─────────────────────────────────────────────────────────────────────────────────


def test_gravar_uma_empresa_cria_e_edita(sessao: Session, cenario: Cenario) -> None:
    resposta = _gravar(cenario, "empresa", _corpo_empresa(nome="  Contratada Alfa "))
    empresa = service.find_company_id_by_name(sessao, "contratada alfa")
    assert empresa is not None

    assert resposta.status_code == 200
    assert (
        unquote(resposta.headers["X-TN-Toast"]) == "Cadastro de empresa gravado: “Contratada Alfa”."
    )
    assert sessao.get(Company, empresa).kind == "Contratada"
    assert _trilha(sessao, "empresa", audit.CREATED)

    atualizacao = _atualizar(cenario, "empresa", empresa, _corpo_empresa(tipo="Gerenciadora"))

    assert atualizacao.status_code == 200
    assert sessao.get(Company, empresa).kind == "Gerenciadora"
    assert _trilha(sessao, "empresa", audit.UPDATED)


@pytest.mark.parametrize(
    ("corpo", "mensagem"),
    [
        (_corpo_empresa(nome=""), "Informe o nome da empresa."),
        (_corpo_empresa(tipo=""), "Escolha o tipo da empresa."),
        (_corpo_empresa(tipo="Parceira"), "Escolha o tipo da empresa."),
    ],
)
def test_empresa_com_campo_invalido_e_recusada(
    cenario: Cenario, corpo: Mapping[str, str], mensagem: str
) -> None:
    resposta = _gravar(cenario, "empresa", corpo)

    assert resposta.status_code == 422
    assert mensagem in resposta.get_body().decode()


def test_empresa_com_nome_repetido_e_recusada(sessao: Session, cenario: Cenario) -> None:
    _gravar(cenario, "empresa", _corpo_empresa(nome="Contratada Alfa"))

    resposta = _gravar(cenario, "empresa", _corpo_empresa(nome="contratada alfa"))

    assert resposta.status_code == 422
    assert "Já existe uma empresa com este nome." in resposta.get_body().decode()
    assert len(_trilha(sessao, "empresa", audit.CREATED)) == 1


# ── Pessoas ──────────────────────────────────────────────────────────────────────────────────


def test_gravar_uma_pessoa_cria_e_edita(sessao: Session, cenario: Cenario) -> None:
    resposta = _gravar(cenario, "pessoa", _corpo_pessoa(email="NINA@example.invalid"))
    pessoa = service.find_person_id_by_email(sessao, "nina@example.invalid")
    assert pessoa is not None

    assert resposta.status_code == 200
    assert unquote(resposta.headers["X-TN-Toast"]) == "Cadastro de pessoa gravado: “Nina Nova”."
    registro = sessao.get(Person, pessoa)
    assert registro is not None and registro.email == "nina@example.invalid"

    atualizacao = _atualizar(
        cenario, "pessoa", pessoa, _corpo_pessoa(nome="Nina Editada", email="nina@example.invalid")
    )

    assert atualizacao.status_code == 200
    assert sessao.get(Person, pessoa).name == "Nina Editada"


def test_pessoa_com_email_invalido_e_recusada(cenario: Cenario) -> None:
    resposta = _gravar(cenario, "pessoa", _corpo_pessoa(email="sem-arroba"))

    assert resposta.status_code == 422
    assert "Informe um e-mail válido." in resposta.get_body().decode()


def test_pessoa_com_email_repetido_e_recusada(cenario: Cenario) -> None:
    resposta = _gravar(cenario, "pessoa", _corpo_pessoa(email=cenario.mario.email.upper()))

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 422
    assert "Já existe uma pessoa com este e-mail." in corpo
    assert 'id="erro-email"' in corpo


def test_pessoa_com_empresa_fora_do_cadastro_e_recusada(cenario: Cenario) -> None:
    resposta = _gravar(cenario, "pessoa", _corpo_pessoa(empresa="999999"))

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 422
    assert "Empresa fora do cadastro." in corpo
    assert 'id="erro-empresa"' in corpo


def test_pessoa_aceita_empresa_do_cadastro(sessao: Session, cenario: Cenario) -> None:
    empresa = criar_empresa(sessao, "Contratada Beta")

    resposta = _gravar(cenario, "pessoa", _corpo_pessoa(empresa=str(empresa.id)))

    pessoa = service.find_person_id_by_email(sessao, "nina@example.invalid")
    assert resposta.status_code == 200
    assert pessoa is not None and sessao.get(Person, pessoa).company_id == empresa.id


# ── Projetos ─────────────────────────────────────────────────────────────────────────────────


def test_gravar_um_projeto_cria_cliente_configuracao_e_notas(
    sessao: Session, cenario: Cenario
) -> None:
    resposta = _gravar(cenario, "projeto", _corpo_projeto(cenario))
    projeto_id = service.find_project_id(sessao, "TN-900")
    assert projeto_id is not None

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert unquote(resposta.headers["X-TN-Toast"]) == "Cadastro de projeto gravado: “TN-900”."
    assert "TN-900" in corpo
    projeto = sessao.get(Project, projeto_id)
    assert projeto is not None
    assert projeto.pep == "PEP-900"
    assert projeto.budget_cents == 123_456
    assert projeto.start_date is not None and projeto.start_date.isoformat() == "2026-10-01"
    cliente = sessao.get(Client, projeto.client_id)
    assert cliente is not None and cliente.name == "Cliente de teste" and cliente.acronym == "CT"
    assert projeto.manager_id == cenario.mario.person_id
    assert projeto.risk_appetite == "moderado"

    configuracao = programacao_repository.settings_of(sessao, projeto_id)
    assert configuracao is not None
    assert (
        configuracao.adherence_target,
        configuracao.ppc_target,
        configuracao.deviation_limit,
    ) == (60.0, 75.0, 15.0)
    assert configuracao.requires_deviation_note is True
    assert _trilha(sessao, "projeto", audit.CREATED)

    assert _notas(sessao, projeto_id) == {"estrategico": 4, "complexidade": 3}


def test_projeto_reusa_o_cliente_existente_pelo_nome(sessao: Session, cenario: Cenario) -> None:
    antes = list(sessao.scalars(select(Client)).all())

    resposta = _gravar(
        cenario,
        "projeto",
        _corpo_projeto(
            cenario,
            codigo="TN-901",
            cliente_nome="cliente tn-rsk-001",
            cliente_sigla="",
        ),
    )

    projeto_id = service.find_project_id(sessao, "TN-901")
    assert resposta.status_code == 200
    assert projeto_id is not None
    projeto = sessao.get(Project, projeto_id)
    assert projeto is not None and projeto.client_id == cenario.projeto.client_id
    assert len(list(sessao.scalars(select(Client)).all())) == len(antes)


def test_projeto_novo_exige_sigla_e_cria_cliente(sessao: Session, cenario: Cenario) -> None:
    sem_sigla = _gravar(
        cenario,
        "projeto",
        _corpo_projeto(
            cenario, codigo="TN-902", cliente_nome="Cliente Sem Sigla", cliente_sigla=""
        ),
    )

    corpo = sem_sigla.get_body().decode()
    assert sem_sigla.status_code == 422
    assert "Informe a sigla do cliente novo." in corpo
    assert 'id="erro-cliente"' in corpo
    assert service.find_project_id(sessao, "TN-902") is None

    com_sigla = _gravar(
        cenario,
        "projeto",
        _corpo_projeto(
            cenario, codigo="TN-902", cliente_nome="Cliente Sem Sigla", cliente_sigla="CSS"
        ),
    )

    assert com_sigla.status_code == 200
    projeto_id = service.find_project_id(sessao, "TN-902")
    assert projeto_id is not None
    cliente = sessao.get(Client, sessao.get(Project, projeto_id).client_id)
    assert cliente is not None and cliente.acronym == "CSS"


@pytest.mark.parametrize(
    ("mudancas", "mensagem", "campo"),
    [
        ({"codigo": ""}, "Informe o código do projeto.", "codigo"),
        ({"nome": ""}, "Informe o nome do projeto.", "nome"),
        ({"cliente_nome": ""}, "Informe o cliente do projeto.", "cliente"),
        ({"gerente": "999999"}, "Escolha o gerente do projeto.", "gerente"),
        ({"apetite": "extremo"}, "Escolha um apetite da escala vigente.", "apetite"),
        (
            {"inicio": "2027-01-01", "termino_previsto": "2026-01-01"},
            "O término não pode ser anterior ao início.",
            "termino",
        ),
        ({"orcamento": "mil reais"}, "Informe um valor em reais (ex.: 1.234,56).", "orcamento"),
        ({"nota_estrategico": "9"}, "Informe uma nota de 1 a 5.", "nota_estrategico"),
    ],
)
def test_projeto_com_campo_invalido_e_recusado(
    cenario: Cenario, mudancas: Mapping[str, str], mensagem: str, campo: str
) -> None:
    resposta = _gravar(cenario, "projeto", _corpo_projeto(cenario, **mudancas))

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 422
    assert mensagem in corpo
    assert f'id="erro-{campo}"' in corpo


def test_projeto_com_codigo_repetido_e_recusado(cenario: Cenario) -> None:
    resposta = _gravar(cenario, "projeto", _corpo_projeto(cenario, codigo=cenario.projeto.code))

    assert resposta.status_code == 422
    assert "Já existe um projeto com este código." in resposta.get_body().decode()


def test_editar_um_projeto_sem_mexer_na_configuracao_da_programacao(
    sessao: Session, cenario: Cenario
) -> None:
    _gravar(cenario, "projeto", _corpo_projeto(cenario))
    projeto_id = service.find_project_id(sessao, "TN-900")
    assert projeto_id is not None
    configuracao = programacao_repository.settings_of(sessao, projeto_id)
    assert configuracao is not None
    linha_antes = configuracao.id

    resposta = _atualizar(
        cenario,
        "projeto",
        projeto_id,
        _corpo_projeto(
            cenario,
            nome="Projeto renomeado",
            nota_estrategico="2",
            nota_complexidade="",
        ),
    )

    assert resposta.status_code == 200
    projeto = sessao.get(Project, projeto_id)
    assert projeto is not None and projeto.name == "Projeto renomeado"
    configuracao_depois = programacao_repository.settings_of(sessao, projeto_id)
    assert configuracao_depois is not None
    assert configuracao_depois.id == linha_antes
    assert configuracao_depois.adherence_target == 60.0
    assert _notas(sessao, projeto_id) == {"estrategico": 2}


# ── Sistemas, unidades, locais e disciplinas ─────────────────────────────────────────────────


def test_gravar_um_sistema_cria_e_edita(sessao: Session, cenario: Cenario) -> None:
    resposta = _gravar(cenario, "sistema", _corpo_sistema(cenario))

    sistema = sessao.scalars(select(SupportSystem).where(SupportSystem.code == "SIS-01")).first()
    assert resposta.status_code == 200
    assert sistema is not None
    assert sistema.project_id == cenario.projeto.id and sistema.area == "Área 100"

    atualizacao = _atualizar(
        cenario, "sistema", sistema.id, _corpo_sistema(cenario, nome="Sistema editado", area="")
    )

    assert atualizacao.status_code == 200
    assert sessao.get(SupportSystem, sistema.id).name == "Sistema editado"


def test_sistema_com_codigo_repetido_no_projeto_e_recusado(cenario: Cenario) -> None:
    _gravar(cenario, "sistema", _corpo_sistema(cenario))

    resposta = _gravar(cenario, "sistema", _corpo_sistema(cenario, nome="Outro"))

    assert resposta.status_code == 422
    assert "Já existe um sistema com este código neste projeto." in resposta.get_body().decode()


def test_sistema_com_projeto_fora_do_cadastro_e_recusado(cenario: Cenario) -> None:
    resposta = _gravar(cenario, "sistema", _corpo_sistema(cenario, projeto="999999"))

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 422
    assert "Escolha o projeto." in corpo
    assert 'id="erro-projeto"' in corpo


def test_gravar_uma_unidade_de_cada_tipo(sessao: Session, cenario: Cenario) -> None:
    medida = _gravar(cenario, "unidade", _corpo_unidade(tipo="medida", codigo="cx", nome="Caixa"))
    organizacional = _gravar(
        cenario,
        "unidade",
        _corpo_unidade(tipo="organizacional", codigo="ENG", nome="Engenharia"),
    )

    assert medida.status_code == 200 and organizacional.status_code == 200
    unidades = {(linha.kind, linha.code) for linha in sessao.scalars(select(Unit)).all()}
    assert ("medida", "cx") in unidades
    assert ("organizacional", "ENG") in unidades


def test_unidade_com_codigo_repetido_no_tipo_e_recusada(cenario: Cenario) -> None:
    _gravar(cenario, "unidade", _corpo_unidade())

    resposta = _gravar(cenario, "unidade", _corpo_unidade(nome="Outra caixa"))

    assert resposta.status_code == 422
    assert "Já existe uma unidade com este código neste tipo." in resposta.get_body().decode()

    outra = _gravar(cenario, "unidade", _corpo_unidade(tipo="organizacional", nome="Outra caixa"))
    assert outra.status_code == 200


def test_unidade_com_tipo_desconhecido_e_recusada(cenario: Cenario) -> None:
    resposta = _gravar(cenario, "unidade", _corpo_unidade(tipo="financeira"))

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 422
    assert "Escolha o tipo da unidade." in corpo
    assert 'id="erro-tipo"' in corpo


def test_gravar_um_local_cria_e_edita(sessao: Session, cenario: Cenario) -> None:
    resposta = _gravar(cenario, "local", _corpo_local(cenario))

    local = sessao.scalars(select(Location).where(Location.code == "L-01")).first()
    assert resposta.status_code == 200
    assert local is not None and local.project_id == cenario.projeto.id

    atualizacao = _atualizar(cenario, "local", local.id, _corpo_local(cenario, nome="Pátio Norte"))

    assert atualizacao.status_code == 200
    assert sessao.get(Location, local.id).name == "Pátio Norte"


def test_local_com_codigo_repetido_no_projeto_e_recusado(cenario: Cenario) -> None:
    _gravar(cenario, "local", _corpo_local(cenario))

    resposta = _gravar(cenario, "local", _corpo_local(cenario, nome="Outro pátio"))

    assert resposta.status_code == 422
    assert "Já existe um local com este código neste projeto." in resposta.get_body().decode()


def test_gravar_uma_disciplina_cria_e_edita(sessao: Session, cenario: Cenario) -> None:
    resposta = _gravar(cenario, "disciplina", _corpo_disciplina())

    disciplina = sessao.scalars(select(Discipline).where(Discipline.name == "Elétrica")).first()
    assert resposta.status_code == 200
    assert disciplina is not None

    atualizacao = _atualizar(
        cenario, "disciplina", disciplina.id, _corpo_disciplina(nome="Elétrica e automação")
    )

    assert atualizacao.status_code == 200
    assert sessao.get(Discipline, disciplina.id).name == "Elétrica e automação"


def test_disciplina_com_nome_repetido_e_recusada(sessao: Session, cenario: Cenario) -> None:
    _gravar(cenario, "disciplina", _corpo_disciplina())

    resposta = _gravar(cenario, "disciplina", _corpo_disciplina(nome="elétrica"))

    assert resposta.status_code == 422
    assert "Já existe uma disciplina com este nome." in resposta.get_body().decode()
    assert len(sessao.scalars(select(Discipline)).all()) == 1


# ── A exclusão ───────────────────────────────────────────────────────────────────────────────


def test_excluir_empresa_sem_uso_apaga_a_linha(sessao: Session, cenario: Cenario) -> None:
    _gravar(cenario, "empresa", _corpo_empresa())
    empresa = service.find_company_id_by_name(sessao, "Contratada Alfa")
    assert empresa is not None

    resposta = _excluir(cenario, "empresa", empresa)

    assert resposta.status_code == 200
    assert (
        unquote(resposta.headers["X-TN-Toast"])
        == "Cadastro de empresa excluído: “Contratada Alfa”."
    )
    assert sessao.get(Company, empresa) is None
    assert _trilha(sessao, "empresa", audit.DELETED)


def test_excluir_empresa_em_uso_por_pessoa_e_recusado(sessao: Session, cenario: Cenario) -> None:
    empresa = criar_empresa(sessao, "Contratada em uso")
    criar_colaborador(sessao, email="pessoa@example.invalid", nome="Pessoa", empresa=empresa)

    resposta = _excluir(cenario, "empresa", empresa.id)

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 422
    assert unquote(resposta.headers["X-TN-Toast"]).startswith(
        "“Contratada em uso” está em uso por 1 pessoa do cadastro"
    )
    assert 'id="cadastros-conteudo"' in corpo
    assert sessao.get(Company, empresa.id) is not None


def test_excluir_pessoa_com_colaborador_e_recusado(sessao: Session, cenario: Cenario) -> None:
    colaborador = criar_colaborador(sessao, email="pessoa@example.invalid", nome="Pessoa Nova")
    pessoa_id = service.find_person_id_by_email(sessao, "pessoa@example.invalid")
    assert pessoa_id is not None

    resposta = _excluir(cenario, "pessoa", pessoa_id)

    assert resposta.status_code == 422
    assert "está em uso por 1 colaborador" in unquote(resposta.headers["X-TN-Toast"])
    assert sessao.get(Person, pessoa_id) is not None
    assert sessao.get(Collaborator, colaborador.id) is not None


def test_excluir_pessoa_que_e_gerente_de_projeto_e_recusado(cenario: Cenario) -> None:
    resposta = _excluir(cenario, "pessoa", cenario.projeto.manager_id)

    assert resposta.status_code == 422
    assert "projeto em que é gerente" in unquote(resposta.headers["X-TN-Toast"])


def test_excluir_projeto_com_sistema_e_recusado(cenario: Cenario) -> None:
    _gravar(cenario, "sistema", _corpo_sistema(cenario))

    resposta = _excluir(cenario, "projeto", cenario.projeto.id)

    assert resposta.status_code == 422
    assert "está em uso por 1 sistema" in unquote(resposta.headers["X-TN-Toast"])


def test_excluir_registro_fora_do_cadastro_e_recusado(cenario: Cenario) -> None:
    resposta = _excluir(cenario, "disciplina", 999_999)

    assert resposta.status_code == 422
    assert unquote(resposta.headers["X-TN-Toast"]) == service.REGISTER_RECORD_NOT_FOUND


def test_excluir_unidade_em_uso_por_item_da_eap_e_recusado(
    sessao: Session, cenario: Cenario
) -> None:
    _gravar(cenario, "unidade", _corpo_unidade())
    unidade = sessao.scalars(select(Unit).where(Unit.code == "cx")).first()
    assert unidade is not None
    sessao.add(
        EapItem(
            project_id=cenario.projeto.id,
            unit_id=unidade.id,
            code="1.1",
            description="Pacote de teste",
            level=3,
        )
    )
    sessao.flush()

    resposta = _excluir(cenario, "unidade", unidade.id)

    assert resposta.status_code == 422
    assert (
        unquote(resposta.headers["X-TN-Toast"])
        == "“Caixa” está em uso por registros de item da EAP e não pode ser excluído."
    )
    assert sessao.get(Unit, unidade.id) is not None


def test_excluir_disciplina_em_uso_por_itp_e_recusado(sessao: Session, cenario: Cenario) -> None:
    _gravar(cenario, "disciplina", _corpo_disciplina())
    disciplina = sessao.scalars(select(Discipline).where(Discipline.name == "Elétrica")).first()
    empresa = criar_empresa(sessao, "Contratada ITP")
    assert disciplina is not None
    sessao.add(
        Itp(
            project_id=cenario.projeto.id,
            discipline_id=disciplina.id,
            company_id=empresa.id,
            code="ITP-001",
            title="ITP de teste",
        )
    )
    sessao.flush()

    resposta = _excluir(cenario, "disciplina", disciplina.id)

    assert resposta.status_code == 422
    assert (
        unquote(resposta.headers["X-TN-Toast"])
        == "“Elétrica” está em uso por registros de ITP e não pode ser excluído."
    )
    assert sessao.get(Discipline, disciplina.id) is not None


def test_excluir_projeto_sem_registros_apaga_a_linha(sessao: Session, cenario: Cenario) -> None:
    projeto = criar_projeto(sessao, codigo="TN-903", nome="Projeto descartável")

    resposta = _excluir(cenario, "projeto", projeto.id)

    assert resposta.status_code == 200
    assert unquote(resposta.headers["X-TN-Toast"]) == "Cadastro de projeto excluído: “TN-903”."
    assert sessao.get(Project, projeto.id) is None


def test_excluir_projeto_com_configuracao_e_recusado_pela_trilha(
    sessao: Session, cenario: Cenario
) -> None:
    # A configuração da programação deixa trilha com o projeto (ISSUE-054) e a
    # trilha é só de inclusão (D5b): o projeto que já gravou não sai do cadastro.
    _gravar(
        cenario,
        "projeto",
        _corpo_projeto(cenario, nota_estrategico="", nota_complexidade=""),
    )
    projeto_id = service.find_project_id(sessao, "TN-900")
    assert projeto_id is not None
    configuracao = programacao_repository.settings_of(sessao, projeto_id)
    assert configuracao is not None

    resposta = _excluir(cenario, "projeto", projeto_id)

    assert resposta.status_code == 422
    assert (
        unquote(resposta.headers["X-TN-Toast"])
        == "“TN-900” está em uso pela trilha de auditoria e não pode ser excluído."
    )
    assert sessao.get(Project, projeto_id) is not None
    assert programacao_repository.settings_of(sessao, projeto_id) is not None


@pytest.mark.parametrize(
    ("tipo", "criar"),
    [
        ("empresa", lambda _: _corpo_empresa()),
        ("pessoa", lambda _: _corpo_pessoa()),
        ("sistema", _corpo_sistema),
        ("unidade", lambda _: _corpo_unidade()),
        ("local", _corpo_local),
        ("disciplina", lambda _: _corpo_disciplina()),
    ],
)
def test_excluir_cada_cadastro_sem_uso_apaga_a_linha(
    sessao: Session, cenario: Cenario, tipo: str, criar: Callable[[Cenario], dict[str, str]]
) -> None:
    _gravar(cenario, tipo, criar(cenario))
    registro = sessao.scalars(select(MODELOS[tipo]).order_by(MODELOS[tipo].id.desc())).first()
    assert registro is not None

    resposta = _excluir(cenario, tipo, registro.id)

    assert resposta.status_code == 200
    assert sessao.get(MODELOS[tipo], registro.id) is None


# ── As exportações ───────────────────────────────────────────────────────────────────────────


def test_excel_e_imprimivel_saem_com_os_sete_cadastros(sessao: Session, cenario: Cenario) -> None:
    empresa = criar_empresa(sessao, "Contratada Exportada")

    excel = routes.registers_excel(_requisicao(cenario.gil, caminho=f"{TELA}/excel", alvo=CONTEUDO))
    imprimivel = routes.registers_printable(
        _requisicao(cenario.gil, caminho=f"{TELA}/imprimivel", alvo=CONTEUDO)
    )

    assert excel.status_code == 200
    assert excel.get_body().startswith(b"PK")
    texto = imprimivel.get_body().decode()
    assert imprimivel.status_code == 200
    for titulo in (
        "Empresas",
        "Pessoas",
        "Projetos",
        "Sistemas",
        "Unidades",
        "Locais",
        "Disciplinas",
    ):
        assert titulo in texto
    assert empresa.name in texto
    assert cenario.projeto.code in texto
    assert cenario.projeto.name in texto
    assert "<script" not in texto
