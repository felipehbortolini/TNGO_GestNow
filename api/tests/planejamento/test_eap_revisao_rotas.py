"""Rotas da revisão da EAP e do desdobramento (ISSUE-038): formulários, gravação e importação.

Costura HTTP: o handler é chamado com a ``HttpRequest`` que o navegador montaria, como em
``test_eap_revisao_servico.py`` e ``test_eap_medicao_rotas.py``. O cenário tem a EAP da revisão
do serviço (cinco pacotes de nível 3, um de planejamento), a Rev 0 e a SM aprovada com impacto
em escopo pendente. Os formulários abrem por recurso; a gravação responde o conteúdo e o
formulário no mesmo pedido; o 422 marca o campo; a revisão sem Gestor é 403 no lugar; a
importação confere a planilha sem gravar e só a confirmação cria a revisão vinculada à SM.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from urllib.parse import unquote

import azure.functions as func
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.blueprints.importing import import_confirm as generic_confirm
from src.core import auth, importing
from src.core.rbac import Bond, GeneralProfile, User
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.models import Collaborator, Company, Person, Project, Unit
from src.modulos.financeiro.models import EacItem
from src.modulos.governanca.models import ChangeImpact, ChangeRequest
from src.modulos.planejamento import importers, routes, service, validation
from src.modulos.planejamento.models import EapItem, EapItemStep, EapRevision
from tests.apoio_6wla import HOJE, Envio, pedido
from tests.html_tags import find_by_id, parse_tags
from tests.identidades import (
    cabecalho_do_principal,
    criar_colaborador,
    criar_empresa,
    criar_projeto,
)
from tests.importadores_de_teste import corpo_multipart, planilha

D = Decimal
BASE = "/api/planejamento/eap"
EMAIL_MEMBRO = "membro-revisao-rotas@example.invalid"
EMAIL_GESTOR = "gestor-revisao-rotas@example.invalid"
EMAIL_VISUALIZADOR = "visualizador-revisao-rotas@example.invalid"
ALVO_CONTEUDO = "eap-conteudo"
ALVO_FORMULARIO = "eap-formulario"
ALVO_RESULTADO = "eap-pacotes-importacao-resultado"
SM = "SM-TN-2026-0201"
JUSTIFICATIVA = "Acréscimo de escopo aprovado na SM."
PACKAGE_HEADERS = tuple(importers.PACKAGE_HEADERS.values())


@dataclass(frozen=True)
class CenarioRevisaoRotas:
    """A EAP da revisão com a Rev 0, a SM pendente e a pessoa de cada perfil."""

    session: Session
    projeto: Project
    empresa: Company
    unidade: Unit
    responsavel: Person
    membro: Collaborator
    gestor: Collaborator
    visualizador: Collaborator
    itens: dict[str, EapItem]
    sm: ChangeRequest
    revisao_zero: EapRevision

    @property
    def params(self) -> dict[str, str]:
        return {"projeto": str(self.projeto.id)}

    @property
    def usuario_membro(self) -> User:
        return _usuario(self.membro, GeneralProfile.MEMBER)


def _usuario(colaborador: Collaborator, perfil: GeneralProfile) -> User:
    return User(
        id=colaborador.id,
        person_id=colaborador.person_id,
        name="Pessoa de teste",
        email="pessoa@example.invalid",
        general_profile=perfil,
        bond=Bond(colaborador.bond),
    )


def _item(
    session: Session,
    projeto: Project,
    code: str,
    description: str,
    parent: EapItem | None = None,
    **fields: object,
) -> EapItem:
    item = EapItem(
        project_id=projeto.id,
        parent_id=parent.id if parent is not None else None,
        code=code,
        description=description,
        level=len(code.split(".")),
        **fields,
    )
    session.add(item)
    session.flush()
    return item


def _eac(
    session: Session, projeto: Project, code: str, description: str, parent: EacItem | None = None
) -> EacItem:
    item = EacItem(
        project_id=projeto.id,
        parent_id=parent.id if parent is not None else None,
        code=code,
        description=description,
        level=len(code.split(".")),
    )
    session.add(item)
    session.flush()
    return item


def _mudanca(session: Session, projeto: Project, *, code: str, scope: str) -> ChangeRequest:
    change = ChangeRequest(
        project_id=projeto.id,
        requester_id=projeto.manager_id,
        code=code,
        title=f"Mudança {code}",
        kind="Escopo",
        origin="Cliente",
        priority="Normal",
        request_date=date(2026, 9, 1),
        description="Descrição da mudança de teste.",
        situation="Aprovada",
    )
    session.add(change)
    session.flush()
    session.add(
        ChangeImpact(
            change_id=change.id,
            analyst_id=projeto.manager_id,
            analysis_date=date(2026, 9, 10),
            cost_cents=0,
            term_days=0,
            scope=scope,
            quality="Sem impacto",
            risks="Sem impacto",
            safety="Sem impacto",
            contract="Sem impacto",
            affects_contract_milestone=False,
        )
    )
    session.flush()
    return change


def _montar_itens(
    session: Session, projeto: Project, unidade: Unit, responsavel: Person
) -> dict[str, EapItem]:
    obra = _item(session, projeto, "1", "Obra civil")
    montagem = _item(session, projeto, "2", "Montagem")
    fundacoes = _item(session, projeto, "1.1", "Fundações", obra)
    equipamentos = _item(session, projeto, "2.1", "Equipamentos", montagem)
    itens = {"1": obra, "2": montagem, "1.1": fundacoes, "2.1": equipamentos}
    itens["1.1.1"] = _item(
        session,
        projeto,
        "1.1.1",
        "Estacas",
        fundacoes,
        kind="Trabalho",
        criterion="Unidades",
        weight=D("20"),
        predicted=D("92"),
        start=date(2026, 5, 2),
        finish=date(2026, 8, 30),
        quantity=D("100"),
        executed=D("40"),
        unit_id=unidade.id,
        owner_id=responsavel.id,
    )
    itens["1.1.2"] = _item(
        session,
        projeto,
        "1.1.2",
        "Blocos",
        fundacoes,
        kind="Trabalho",
        criterion="Percentual estimado",
        weight=D("10"),
        predicted=D("2.1"),
        start=date(2026, 8, 1),
        finish=date(2026, 12, 1),
        estimated_pct=D("0"),
        owner_id=responsavel.id,
    )
    itens["1.1.3"] = _item(
        session,
        projeto,
        "1.1.3",
        "Partida assistida",
        fundacoes,
        kind="Planejamento",
        weight=D("5"),
        predicted=D("42.5"),
        start=date(2026, 6, 1),
        finish=date(2027, 2, 1),
        owner_id=responsavel.id,
    )
    itens["2.1.1"] = _item(
        session,
        projeto,
        "2.1.1",
        "Estruturas metálicas",
        equipamentos,
        kind="Trabalho",
        criterion="Etapas",
        model="engenharia",
        weight=D("30"),
        predicted=D("60"),
        start=date(2026, 3, 1),
        finish=date(2026, 9, 10),
        owner_id=responsavel.id,
    )
    itens["2.1.2"] = _item(
        session,
        projeto,
        "2.1.2",
        "Comissionamento",
        equipamentos,
        kind="Trabalho",
        criterion="Marco 0/100",
        weight=D("35"),
        predicted=D("95"),
        start=date(2026, 4, 1),
        finish=date(2026, 9, 1),
        state="Concluído",
        owner_id=responsavel.id,
    )
    session.add(
        EapItemStep(
            item_id=itens["2.1.1"].id, order=1, name="Elaboração", weight=D("100"), pct=D("0")
        )
    )
    session.flush()
    return itens


@pytest.fixture
def cenario_revisao_rotas(sessao: Session) -> CenarioRevisaoRotas:
    """A EAP da revisão do projeto, com a Rev 0, a SM pendente e o cadastro da importação."""
    projeto = criar_projeto(sessao, codigo="TN-REV-ROTA-001", nome="Fábrica de rotas de revisão")
    empresa = criar_empresa(sessao, "Montadora de rotas")
    unidade = Unit(kind="medida", code="un", name="Unidade")
    sessao.add(unidade)
    membro = criar_colaborador(sessao, email=EMAIL_MEMBRO, nome="Maria Medição", perfil="Membro")
    gestor = criar_colaborador(sessao, email=EMAIL_GESTOR, nome="Gustavo Gestor", perfil="Gestor")
    visualizador = criar_colaborador(sessao, email=EMAIL_VISUALIZADOR, perfil="Visualizador")
    sessao.flush()
    responsavel = sessao.get(Person, membro.person_id)
    assert responsavel is not None
    itens = _montar_itens(sessao, projeto, unidade, responsavel)
    revisao_zero = EapRevision(
        project_id=projeto.id,
        approved_by_id=responsavel.id,
        revision=0,
        revision_date=date(2026, 1, 5),
        alteration="Linha de base",
        justification="Linha de base aprovada no gate de investimento.",
    )
    sessao.add(revisao_zero)
    sessao.flush()
    sm = _mudanca(sessao, projeto, code=SM, scope="Inclusão do pacote de tubulação")
    raiz = _eac(sessao, projeto, "3", "Equipamentos")
    sub = _eac(sessao, projeto, "3.2", "Tubulação", raiz)
    _eac(sessao, projeto, "3.2.4", "Pipe rack", sub)
    return CenarioRevisaoRotas(
        session=sessao,
        projeto=projeto,
        empresa=empresa,
        unidade=unidade,
        responsavel=responsavel,
        membro=membro,
        gestor=gestor,
        visualizador=visualizador,
        itens=itens,
        sm=sm,
        revisao_zero=revisao_zero,
    )


def _texto(resposta: func.HttpResponse) -> str:
    return unquote(resposta.get_body().decode())


def _toast(resposta: func.HttpResponse) -> str:
    return unquote(resposta.headers["X-TN-Toast"])


def _pacotes(session: Session, projeto: Project) -> list[EapItem]:
    return list(
        session.scalars(
            select(EapItem).where(
                EapItem.project_id == projeto.id, EapItem.level == service.LEVEL_PACKAGE
            )
        )
    )


def _revisoes(session: Session, projeto: Project) -> list[EapRevision]:
    return list(
        session.scalars(
            select(EapRevision)
            .where(EapRevision.project_id == projeto.id)
            .order_by(EapRevision.revision)
        )
    )


def _visao(cenario: CenarioRevisaoRotas) -> service.EapOverview:
    return service.eap_overview(
        cenario.session,
        user=cenario.usuario_membro,
        scope=Scope(project_id=cenario.projeto.id, source="url"),
        reference_date=HOJE,
    )


def _chamar_formulario_pacote(
    cenario: CenarioRevisaoRotas,
    recurso: str = "desdobramento",
    *,
    email: str = EMAIL_MEMBRO,
    alpine: bool = True,
) -> func.HttpResponse:
    return routes.eap_package_form(
        pedido(
            f"{BASE}/pacotes/novo",
            email=email,
            envio=Envio(
                params={**cenario.params, "recurso": recurso},
                alvo=ALVO_FORMULARIO,
                alpine=alpine,
            ),
        )
    )


def _salvar_pacote(
    cenario: CenarioRevisaoRotas,
    campos: Mapping[str, str],
    *,
    email: str = EMAIL_MEMBRO,
    alpine: bool = True,
) -> func.HttpResponse:
    return routes.eap_package_save(
        pedido(
            f"{BASE}/pacotes",
            email=email,
            envio=Envio(
                metodo="POST",
                campos=campos,
                params=cenario.params,
                alvo=f"{ALVO_FORMULARIO} {ALVO_CONTEUDO}",
                alpine=alpine,
            ),
        )
    )


def _chamar_formulario_revisao(
    cenario: CenarioRevisaoRotas, *, email: str = EMAIL_MEMBRO, alpine: bool = True
) -> func.HttpResponse:
    return routes.eap_revision_form(
        pedido(
            f"{BASE}/revisoes/nova",
            email=email,
            envio=Envio(params=cenario.params, alvo=ALVO_FORMULARIO, alpine=alpine),
        )
    )


def _salvar_revisao(
    cenario: CenarioRevisaoRotas,
    campos: Mapping[str, str],
    *,
    email: str = EMAIL_MEMBRO,
    alpine: bool = True,
) -> func.HttpResponse:
    return routes.eap_revision_save(
        pedido(
            f"{BASE}/revisoes",
            email=email,
            envio=Envio(
                metodo="POST",
                campos=campos,
                params=cenario.params,
                alvo=f"{ALVO_FORMULARIO} {ALVO_CONTEUDO}",
                alpine=alpine,
            ),
        )
    )


def _campos_desdobramento(cenario: CenarioRevisaoRotas, **alteracoes: str) -> dict[str, str]:
    campos = {
        "recurso": "desdobramento",
        "origem": "1.1.3",
        "pai": "1.1",
        "descricao": "Partida detalhada",
        "criterio": "Percentual estimado",
        "modelo": "",
        "unidade": "",
        "quantidade": "",
        "peso": "5",
        "inicio": "2026-10-01",
        "termino": "2027-01-29",
        "empresa": "",
        "responsavel": str(cenario.responsavel.id),
        "eac": "",
        "entregavel": "",
        "aceitacao": "",
        "justificativa": JUSTIFICATIVA,
    }
    campos.update(alteracoes)
    return campos


def _campos_pacote_novo(cenario: CenarioRevisaoRotas, **alteracoes: str) -> dict[str, str]:
    campos = {
        "recurso": "revisao",
        "sm": SM,
        "origem": "",
        "tipo": "Trabalho",
        "pai": "2.1",
        "descricao": "Pipe rack PR-03",
        "criterio": "Unidades",
        "modelo": "",
        "unidade": "un",
        "quantidade": "120",
        "peso": "3",
        "inicio": "2026-09-01",
        "termino": "2026-12-01",
        "empresa": "",
        "responsavel": str(cenario.responsavel.id),
        "eac": "3.2.4",
        "entregavel": "",
        "aceitacao": "",
        "justificativa": JUSTIFICATIVA,
    }
    campos.update(alteracoes)
    return campos


def _campos_ajuste(**alteracoes: str) -> dict[str, str]:
    campos = {
        "sm": SM,
        "pacote": "1.1.1",
        "peso": "8",
        "quantidade": "150",
        "termino": "2026-09-30",
        "justificativa": JUSTIFICATIVA,
    }
    campos.update(alteracoes)
    return campos


def _planilha(*linhas: tuple[object, ...]) -> bytes:
    return planilha(linhas, cabecalho=PACKAGE_HEADERS)


def _pedido_com_arquivo(
    caminho: str,
    conteudo: bytes,
    campos: Mapping[str, str],
    *,
    params: Mapping[str, str],
    email: str = EMAIL_MEMBRO,
) -> func.HttpRequest:
    body, content_type = corpo_multipart(campos, ("pacotes.xlsx", conteudo))
    return func.HttpRequest(
        method="POST",
        url=caminho,
        headers={
            auth.PRINCIPAL_HEADER: cabecalho_do_principal(email),
            "Content-Type": content_type,
            "X-Alpine-Request": "true",
            "X-Alpine-Target": ALVO_RESULTADO,
        },
        params=dict(params),
        route_params={},
        body=body,
    )


def _conferir(
    cenario: CenarioRevisaoRotas,
    conteudo: bytes,
    *,
    campos: Mapping[str, str] | None = None,
    email: str = EMAIL_MEMBRO,
    params: Mapping[str, str] | None = None,
) -> func.HttpResponse:
    return routes.eap_package_import_check(
        _pedido_com_arquivo(
            f"{BASE}/pacotes/importar/conferir",
            conteudo,
            dict(campos or {}),
            params=params if params is not None else cenario.params,
            email=email,
        )
    )


def _confirmar(
    cenario: CenarioRevisaoRotas,
    conteudo: bytes,
    *,
    campos: Mapping[str, str] | None = None,
    email: str = EMAIL_MEMBRO,
    params: Mapping[str, str] | None = None,
) -> func.HttpResponse:
    digest = importing.digest_of(importing.Upload(name="pacotes.xlsx", content=conteudo))
    dados = {
        "conferido": digest,
        "ciente": "sim",
        "sm": SM,
        "justificativa": JUSTIFICATIVA,
    }
    dados.update(campos or {})
    return routes.eap_package_import_confirm(
        _pedido_com_arquivo(
            f"{BASE}/pacotes/importar/confirmar",
            conteudo,
            dados,
            params=params if params is not None else cenario.params,
            email=email,
        )
    )


# ── Os formulários ───────────────────────────────────────────────────────


@pytest.mark.parametrize("recurso", ("desdobramento", "revisao"))
def test_o_formulario_do_pacote_novo_abre_por_recurso(
    cenario_revisao_rotas: CenarioRevisaoRotas, recurso: str
) -> None:
    resposta = _chamar_formulario_pacote(cenario_revisao_rotas, recurso)

    texto = _texto(resposta)
    names = {
        tag.attrs.get("name")
        for tag in parse_tags(texto)
        if tag.name in {"input", "textarea", "select"}
    }
    assert resposta.status_code == 200
    assert find_by_id(parse_tags(texto), ALVO_FORMULARIO) is not None
    assert {
        "recurso",
        "origem",
        "sm",
        "tipo",
        "pai",
        "descricao",
        "criterio",
        "modelo",
        "unidade",
        "quantidade",
        "peso",
        "inicio",
        "termino",
        "empresa",
        "responsavel",
        "eac",
        "justificativa",
    } <= names
    assert "1.1.3 · Partida assistida · 5% a desdobrar" in texto
    assert SM in texto
    assert "Engenharia (documentos)" in texto
    assert "3.2.4" in texto


def test_o_formulario_da_revisao_abre_com_a_sm_e_os_pacotes(
    cenario_revisao_rotas: CenarioRevisaoRotas,
) -> None:
    resposta = _chamar_formulario_revisao(cenario_revisao_rotas)

    texto = _texto(resposta)
    names = {
        tag.attrs.get("name")
        for tag in parse_tags(texto)
        if tag.name in {"input", "textarea", "select"}
    }
    assert resposta.status_code == 200
    assert find_by_id(parse_tags(texto), ALVO_FORMULARIO) is not None
    assert {"sm", "pacote", "peso", "quantidade", "termino", "justificativa"} <= names
    assert SM in texto
    assert "1.1.1 · Estacas" in texto
    assert "Rev 1" in texto


def test_o_visualizador_recebe_403_nos_formularios(
    cenario_revisao_rotas: CenarioRevisaoRotas,
) -> None:
    pacote = _chamar_formulario_pacote(cenario_revisao_rotas, email=EMAIL_VISUALIZADOR)
    revisao = _chamar_formulario_revisao(cenario_revisao_rotas, email=EMAIL_VISUALIZADOR)

    assert pacote.status_code == 403
    assert revisao.status_code == 403


@pytest.mark.usefixtures("cenario_revisao_rotas")
def test_o_portfolio_e_recusado() -> None:
    formulario = routes.eap_package_form(
        pedido(f"{BASE}/pacotes/novo", email=EMAIL_MEMBRO, envio=Envio(alvo=ALVO_FORMULARIO))
    )
    revisao = routes.eap_revision_form(
        pedido(f"{BASE}/revisoes/nova", email=EMAIL_MEMBRO, envio=Envio(alvo=ALVO_FORMULARIO))
    )
    gravacao = routes.eap_revision_save(
        pedido(
            f"{BASE}/revisoes",
            email=EMAIL_MEMBRO,
            envio=Envio(
                metodo="POST",
                campos=_campos_ajuste(),
                alvo=f"{ALVO_FORMULARIO} {ALVO_CONTEUDO}",
            ),
        )
    )

    assert formulario.status_code == 403
    assert service.EAP_PORTFOLIO_READ_ONLY_MESSAGE in _texto(formulario)
    assert revisao.status_code == 403
    assert gravacao.status_code == 403


def test_sem_o_cabecalho_do_alpine_as_rotas_mandam_para_o_shell(
    cenario_revisao_rotas: CenarioRevisaoRotas,
) -> None:
    formulario = _chamar_formulario_pacote(cenario_revisao_rotas, alpine=False)
    gravacao = _salvar_revisao(cenario_revisao_rotas, _campos_ajuste(), alpine=False)

    assert formulario.status_code == 302
    assert gravacao.status_code == 302


# ── O desdobramento ──────────────────────────────────────────────────────


def test_o_desdobramento_cria_o_pacote_e_responde_o_conteudo_com_toast(
    cenario_revisao_rotas: CenarioRevisaoRotas,
) -> None:
    resposta = _salvar_pacote(cenario_revisao_rotas, _campos_desdobramento(cenario_revisao_rotas))

    texto = _texto(resposta)
    tags = parse_tags(texto)
    assert resposta.status_code == 200
    assert find_by_id(tags, ALVO_CONTEUDO) is not None
    formulario = find_by_id(tags, ALVO_FORMULARIO)
    assert formulario is not None
    assert formulario.clean_text() == ""
    assert _toast(resposta) == (
        "Pacote 1.1.4 criado com peso desdobrado de 1.1.3 (pacote de planejamento encerrado)."
    )
    origem = cenario_revisao_rotas.session.get(EapItem, cenario_revisao_rotas.itens["1.1.3"].id)
    assert origem is not None
    assert origem.weight == D("0")
    novo = cenario_revisao_rotas.session.scalars(
        select(EapItem).where(
            EapItem.project_id == cenario_revisao_rotas.projeto.id, EapItem.code == "1.1.4"
        )
    ).one()
    assert (novo.kind, novo.criterion, novo.weight, novo.predicted) == (
        "Trabalho",
        "Percentual estimado",
        D("5.00"),
        D("42.5"),
    )
    assert sum(
        item.weight or D(0)
        for item in _pacotes(cenario_revisao_rotas.session, cenario_revisao_rotas.projeto)
    ) == D("100.00")


def test_o_desdobramento_acima_do_peso_da_origem_volta_422_no_campo(
    cenario_revisao_rotas: CenarioRevisaoRotas,
) -> None:
    resposta = _salvar_pacote(
        cenario_revisao_rotas, _campos_desdobramento(cenario_revisao_rotas, peso="6")
    )

    texto = _texto(resposta)
    assert resposta.status_code == 422
    assert find_by_id(parse_tags(texto), ALVO_FORMULARIO) is not None
    assert validation.BREAKDOWN_WEIGHT_MESSAGE.format(code="1.1.3", weight="5") in texto
    assert "input--erro" in texto
    assert _revisao_nova_ausente(cenario_revisao_rotas)


def _revisao_nova_ausente(cenario: CenarioRevisaoRotas) -> bool:
    return _revisoes(cenario.session, cenario.projeto) == [cenario.revisao_zero]


# ── A revisão ────────────────────────────────────────────────────────────


def test_a_revisao_com_pacote_novo_cria_a_rev_e_o_pacote(
    cenario_revisao_rotas: CenarioRevisaoRotas,
) -> None:
    resposta = _salvar_pacote(
        cenario_revisao_rotas, _campos_pacote_novo(cenario_revisao_rotas), email=EMAIL_GESTOR
    )

    texto = _texto(resposta)
    tags = parse_tags(texto)
    assert resposta.status_code == 200
    assert find_by_id(tags, ALVO_CONTEUDO) is not None
    formulario = find_by_id(tags, ALVO_FORMULARIO)
    assert formulario is not None
    assert formulario.clean_text() == ""
    assert _toast(resposta) == "Pacote 2.1.3 incluído na Rev 1; demais pesos reescalados."
    novo = cenario_revisao_rotas.session.scalars(
        select(EapItem).where(
            EapItem.project_id == cenario_revisao_rotas.projeto.id, EapItem.code == "2.1.3"
        )
    ).one()
    assert (novo.kind, novo.criterion, novo.weight) == ("Trabalho", "Unidades", D("3.00"))
    assert novo.company_id is None
    assert novo.owner_id == cenario_revisao_rotas.responsavel.id
    assert [
        revisao.revision
        for revisao in _revisoes(cenario_revisao_rotas.session, cenario_revisao_rotas.projeto)
    ] == [0, 1]
    assert "Rev 1" in texto


def test_a_revisao_por_unidades_ajusta_peso_quantidade_e_termino(
    cenario_revisao_rotas: CenarioRevisaoRotas,
) -> None:
    resposta = _salvar_revisao(cenario_revisao_rotas, _campos_ajuste(), email=EMAIL_GESTOR)

    texto = _texto(resposta)
    tags = parse_tags(texto)
    assert resposta.status_code == 200
    assert find_by_id(tags, ALVO_CONTEUDO) is not None
    assert find_by_id(tags, ALVO_FORMULARIO) is not None
    assert _toast(resposta) == "Rev 1 da EAP criada."
    ajustado = cenario_revisao_rotas.session.get(EapItem, cenario_revisao_rotas.itens["1.1.1"].id)
    assert ajustado is not None
    assert (ajustado.weight, ajustado.quantity, ajustado.finish) == (
        D("8.00"),
        D("150"),
        date(2026, 9, 30),
    )
    assert sum(
        item.weight or D(0)
        for item in _pacotes(cenario_revisao_rotas.session, cenario_revisao_rotas.projeto)
    ) == D("100.00")


def test_o_conteudo_perde_a_sm_pendente_e_ganha_a_revisao_nova(
    cenario_revisao_rotas: CenarioRevisaoRotas,
) -> None:
    antes = _visao(cenario_revisao_rotas)
    assert [pendente.code for pendente in antes.pending_changes] == [SM]

    resposta = _salvar_revisao(cenario_revisao_rotas, _campos_ajuste(), email=EMAIL_GESTOR)

    depois = _visao(cenario_revisao_rotas)
    vigente = depois.current_revision
    assert resposta.status_code == 200
    assert depois.pending_changes == ()
    assert vigente is not None
    assert (vigente.revision, vigente.change_id, vigente.change_code) == (
        1,
        cenario_revisao_rotas.sm.id,
        SM,
    )
    assert cenario_revisao_rotas.sm.eap_revision == 1


def test_peso_acima_do_maximo_volta_422_com_o_formulario_preenchido(
    cenario_revisao_rotas: CenarioRevisaoRotas,
) -> None:
    resposta = _salvar_revisao(cenario_revisao_rotas, _campos_ajuste(peso="12"), email=EMAIL_GESTOR)

    texto = _texto(resposta)
    assert resposta.status_code == 422
    assert find_by_id(parse_tags(texto), ALVO_FORMULARIO) is not None
    assert validation.REVISION_WEIGHT_MAX_MESSAGE.format(maximum="10") in texto
    assert 'value="12"' in texto
    assert _revisao_nova_ausente(cenario_revisao_rotas)


def test_a_soma_fixa_de_cem_volta_422(cenario_revisao_rotas: CenarioRevisaoRotas) -> None:
    sessao = cenario_revisao_rotas.session
    configuracoes.seed_initial_parameters(
        sessao, author_id=cenario_revisao_rotas.membro.id, effective_from=date(2026, 1, 1)
    )
    valores = dict(configuracoes.INITIAL_PARAMETERS["eap"])
    valores["pesoMaximoPacotePct"] = 100
    configuracoes.save_parameter_group(
        sessao,
        author_id=cenario_revisao_rotas.membro.id,
        group="eap",
        values=valores,
        effective_from=HOJE,
        justification="Peso máximo flexível para o teste da soma fixa.",
    )

    resposta = _salvar_revisao(
        cenario_revisao_rotas, _campos_ajuste(peso="100"), email=EMAIL_GESTOR
    )

    assert resposta.status_code == 422
    assert validation.REVISION_FIXED_WEIGHT_MESSAGE in _texto(resposta)


def test_a_revisao_sem_gestor_volta_403_com_a_mensagem_no_formulario(
    cenario_revisao_rotas: CenarioRevisaoRotas,
) -> None:
    resposta = _salvar_revisao(cenario_revisao_rotas, _campos_ajuste())

    texto = _texto(resposta)
    assert resposta.status_code == 403
    assert service.REVISION_MANAGER_MESSAGE in texto
    assert find_by_id(parse_tags(texto), ALVO_FORMULARIO) is not None
    assert _revisao_nova_ausente(cenario_revisao_rotas)


def test_a_justificativa_curta_volta_422_no_campo(
    cenario_revisao_rotas: CenarioRevisaoRotas,
) -> None:
    resposta = _salvar_revisao(
        cenario_revisao_rotas, _campos_ajuste(justificativa="curta"), email=EMAIL_GESTOR
    )

    texto = _texto(resposta)
    assert resposta.status_code == 422
    assert validation.REVISION_JUSTIFICATION_MESSAGE in texto


# ── A importação dos pacotes ─────────────────────────────────────────────


def test_o_formulario_da_importacao_traz_a_sm_e_o_modelo(
    cenario_revisao_rotas: CenarioRevisaoRotas,
) -> None:
    resposta = routes.eap_package_import_form(
        pedido(
            f"{BASE}/pacotes/importar/formulario",
            email=EMAIL_MEMBRO,
            envio=Envio(params=cenario_revisao_rotas.params, alvo=ALVO_FORMULARIO),
        )
    )

    texto = _texto(resposta)
    names = {
        tag.attrs.get("name")
        for tag in parse_tags(texto)
        if tag.name in {"input", "textarea", "select"}
    }
    assert resposta.status_code == 200
    assert find_by_id(parse_tags(texto), ALVO_FORMULARIO) is not None
    assert {"sm", "justificativa", "arquivo"} <= names
    assert SM in texto
    assert f"/api/importacao/{importers.PACKAGES_KEY}/modelo" in texto


def test_a_importacao_de_pacotes_confere_sem_gravar_e_mostra_os_erros_por_linha(
    cenario_revisao_rotas: CenarioRevisaoRotas,
) -> None:
    antes = _pacotes(cenario_revisao_rotas.session, cenario_revisao_rotas.projeto)
    conteudo = _planilha(
        (
            "2.1.3",
            "Pipe rack PR-03",
            "Trabalho",
            "Unidades",
            "",
            "un",
            120,
            3,
            "2026-10-01",
            "2026-12-01",
            "Maria Medição",
            "",
            "3.2.4",
        ),
        (
            "1.1.3",
            "Partida repetida",
            "Planejamento",
            "",
            "",
            "",
            "",
            2,
            "2026-10-01",
            "2026-12-01",
            "Maria Medição",
            "",
            "",
        ),
        (
            "2.1.4",
            "Estrutura extra",
            "Trabalho",
            "Etapas",
            "Engenharia (documentos)",
            "",
            "",
            4,
            "2026-10-01",
            "2026-12-01",
            "Fulano de Tal",
            "Fornecedor Fantasma",
            "9.9.9",
        ),
        (
            "2.1.3",
            "Pipe rack repetido",
            "Trabalho",
            "Unidades",
            "",
            "un",
            120,
            3,
            "2026-10-01",
            "2026-12-01",
            "Maria Medição",
            "",
            "3.2.4",
        ),
    )

    resposta = _conferir(cenario_revisao_rotas, conteudo)

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert find_by_id(parse_tags(texto), ALVO_RESULTADO) is not None
    assert "Vão ser gravadas" in texto
    assert importers.EXISTING_MESSAGE.format(code="1.1.3") in texto
    assert importers.OWNER_MESSAGE.format(name="Fulano de Tal") in texto
    assert importers.COMPANY_MESSAGE.format(name="Fornecedor Fantasma") in texto
    assert importers.EAC_MESSAGE.format(code="9.9.9") in texto
    assert "repete a linha 2" in texto
    assert _pacotes(cenario_revisao_rotas.session, cenario_revisao_rotas.projeto) == antes
    assert _revisao_nova_ausente(cenario_revisao_rotas)


def test_a_importacao_confirmada_cria_a_revisao_com_os_pacotes_validos(
    cenario_revisao_rotas: CenarioRevisaoRotas,
) -> None:
    conteudo = _planilha(
        (
            "2.1.7",
            "Pipe rack PR-03",
            "Trabalho",
            "Unidades",
            "",
            "un",
            120,
            3,
            "2026-10-01",
            "2026-12-01",
            "Maria Medição",
            "",
            "3.2.4",
        ),
        (
            "2.1.4",
            "Estrutura extra",
            "Trabalho",
            "Etapas",
            "Engenharia (documentos)",
            "",
            "",
            4,
            "2026-10-01",
            "2026-12-01",
            "Maria Medição",
            "",
            "",
        ),
        (
            "1.1.3",
            "Partida repetida",
            "Planejamento",
            "",
            "",
            "",
            "",
            2,
            "2026-10-01",
            "2026-12-01",
            "Maria Medição",
            "",
            "",
        ),
    )

    resposta = _confirmar(cenario_revisao_rotas, conteudo, email=EMAIL_GESTOR)

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert find_by_id(parse_tags(texto), ALVO_RESULTADO) is not None
    assert find_by_id(parse_tags(texto), ALVO_CONTEUDO) is not None
    assert "Rev 1 criada com 2 pacote(s) novo(s)" in texto
    assert "Linhas que ficaram de fora" in texto
    assert importers.EXISTING_MESSAGE.format(code="1.1.3") in texto
    assert _toast(resposta) == "Rev 1 criada: 2 pacotes novos. 1 linha com erro não entrou."
    sessao = cenario_revisao_rotas.session
    assert (
        sessao.scalars(
            select(EapItem).where(
                EapItem.project_id == cenario_revisao_rotas.projeto.id,
                EapItem.code == "2.1.3",
            )
        ).one_or_none()
        is None
    )
    importado = sessao.scalars(
        select(EapItem).where(
            EapItem.project_id == cenario_revisao_rotas.projeto.id,
            EapItem.code == "2.1.7",
        )
    ).one()
    assert (importado.kind, importado.criterion, importado.weight) == (
        "Trabalho",
        "Unidades",
        D("3.00"),
    )
    novo = sessao.scalars(
        select(EapItem).where(
            EapItem.project_id == cenario_revisao_rotas.projeto.id,
            EapItem.code == "2.1.4",
        )
    ).one()
    passos = sessao.scalars(
        select(EapItemStep).where(EapItemStep.item_id == novo.id).order_by(EapItemStep.order)
    ).all()
    assert [(passo.name, passo.pct) for passo in passos] == [
        ("Elaboração", D("0")),
        ("Emissão para comentários", D("0")),
        ("Emissão para construção", D("0")),
    ]
    assert [revisao.revision for revisao in _revisoes(sessao, cenario_revisao_rotas.projeto)] == [
        0,
        1,
    ]
    assert cenario_revisao_rotas.sm.eap_revision == 1


def test_o_importador_de_pacotes_recusa_o_fluxo_generico(
    cenario_revisao_rotas: CenarioRevisaoRotas,
) -> None:
    assert importing.find(importers.PACKAGES_KEY) is not None
    conteudo = _planilha(
        (
            "2.1.3",
            "Pipe rack PR-03",
            "Trabalho",
            "Unidades",
            "",
            "un",
            120,
            3,
            "2026-10-01",
            "2026-12-01",
            "Maria Medição",
            "",
            "3.2.4",
        )
    )
    digest = importing.digest_of(importing.Upload(name="pacotes.xlsx", content=conteudo))
    body, content_type = corpo_multipart(
        {"conferido": digest, "ciente": "sim"}, ("pacotes.xlsx", conteudo)
    )
    request = func.HttpRequest(
        method="POST",
        url=f"/api/importacao/{importers.PACKAGES_KEY}/confirmar",
        headers={
            auth.PRINCIPAL_HEADER: cabecalho_do_principal(EMAIL_GESTOR),
            "Content-Type": content_type,
            "X-Alpine-Request": "true",
            "X-Alpine-Target": ALVO_RESULTADO,
        },
        params=dict(cenario_revisao_rotas.params),
        route_params={"chave": importers.PACKAGES_KEY},
        body=body,
    )

    resposta = generic_confirm(request)

    assert resposta.status_code == 422
    assert importers.PACKAGES_CONFIRMATION_MESSAGE in _texto(resposta)
    assert _revisao_nova_ausente(cenario_revisao_rotas)
