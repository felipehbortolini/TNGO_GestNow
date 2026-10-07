"""Rotas da medição do avanço (ISSUE-037): formulário por critério, estorno e importação.

Costura HTTP: o handler é chamado com a ``HttpRequest`` que o navegador montaria, como em
``test_eap_rotas.py``. O cenário tem um pacote de cada critério, o pacote de planejamento e uma
pessoa de cada perfil. O formulário traz as entradas do critério; a gravação responde o conteúdo
e o formulário no mesmo pedido; o estorno sem Gestor é 403 no lugar; a importação confere a
planilha sem gravar e só a confirmação escreve o avanço, com o relatório das linhas recusadas.
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
from src.modulos.configuracoes.models import Project, Unit
from src.modulos.planejamento import importers, routes, service, validation
from src.modulos.planejamento.models import EapItem, EapItemStep, EapMeasurement
from tests.apoio_6wla import HOJE, Envio, pedido
from tests.html_tags import find_by_id, parse_tags
from tests.identidades import cabecalho_do_principal, criar_colaborador, criar_projeto
from tests.importadores_de_teste import corpo_multipart, planilha

D = Decimal
BASE = "/api/planejamento/eap"
EMAIL_MEMBRO = "membro-avanco-rotas@example.invalid"
EMAIL_GESTOR = "gestor-avanco-rotas@example.invalid"
EMAIL_VISUALIZADOR = "visualizador-avanco-rotas@example.invalid"
ALVO_CONTEUDO = "eap-conteudo"
ALVO_FORMULARIO = "eap-formulario"
ALVO_RESULTADO = "eap-importacao-resultado"
AVANCO_HEADERS = ("Código do pacote", "Avanço acumulado (%)", "Quantidade executada")


@dataclass(frozen=True)
class CenarioAvanco:
    """O projeto com um pacote de cada critério e o pacote de planejamento."""

    session: Session
    projeto: Project
    unidade: Unit
    itens: dict[str, EapItem]

    @property
    def params(self) -> dict[str, str]:
        return {"projeto": str(self.projeto.id)}


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


@pytest.fixture
def cenario_avanco(sessao: Session) -> CenarioAvanco:
    """Os pacotes do avanço, na transação do teste, com a pessoa de cada perfil."""
    projeto = criar_projeto(sessao, codigo="TN-AVANCO-001", nome="Fábrica do avanço")
    unidade = Unit(kind="medida", code="m", name="Metro")
    sessao.add(unidade)
    criar_colaborador(sessao, email=EMAIL_MEMBRO, nome="Maria Avanço", perfil="Membro")
    criar_colaborador(sessao, email=EMAIL_GESTOR, nome="Gustavo Avanço", perfil="Gestor")
    criar_colaborador(sessao, email=EMAIL_VISUALIZADOR, perfil="Visualizador")
    area = _item(sessao, projeto, "1", "Obra civil")
    sub = _item(sessao, projeto, "1.1", "Fundações", area)
    itens = {
        "1": area,
        "1.1": sub,
        "1.1.1": _item(
            sessao,
            projeto,
            "1.1.1",
            "Estacas",
            sub,
            kind="Trabalho",
            criterion="Unidades",
            weight=D("20"),
            predicted=D("90"),
            start=date(2026, 5, 2),
            finish=date(2026, 8, 30),
            quantity=D("100"),
            executed=D("90"),
            unit_id=unidade.id,
        ),
        "1.1.2": _item(
            sessao,
            projeto,
            "1.1.2",
            "Blocos",
            sub,
            kind="Trabalho",
            criterion="Marco 0/100",
            weight=D("10"),
            predicted=D("2.1"),
            start=date(2026, 8, 1),
            finish=date(2026, 12, 1),
            state="Não iniciado",
        ),
        "1.1.3": _item(
            sessao,
            projeto,
            "1.1.3",
            "Alinhamento",
            sub,
            kind="Trabalho",
            criterion="Marco 50/50",
            weight=D("5"),
            predicted=D("55"),
            start=date(2026, 6, 15),
            finish=date(2026, 12, 20),
            state="Iniciado",
        ),
        "1.1.4": _item(
            sessao,
            projeto,
            "1.1.4",
            "Estruturas metálicas",
            sub,
            kind="Trabalho",
            criterion="Etapas",
            weight=D("15"),
            predicted=D("60"),
            start=date(2026, 3, 1),
            finish=date(2026, 9, 10),
        ),
        "1.1.5": _item(
            sessao,
            projeto,
            "1.1.5",
            "Bomba principal",
            sub,
            kind="Trabalho",
            criterion="Percentual estimado",
            weight=D("2"),
            predicted=D("25"),
            estimated_pct=D("20"),
        ),
        "1.1.6": _item(
            sessao,
            projeto,
            "1.1.6",
            "Comissionamento",
            sub,
            kind="Trabalho",
            criterion="Percentual estimado",
            weight=D("6"),
            predicted=D("0"),
            estimated_pct=D("0"),
        ),
        "1.1.7": _item(
            sessao,
            projeto,
            "1.1.7",
            "Partida assistida",
            sub,
            kind="Planejamento",
            weight=D("3"),
            predicted=D("0"),
        ),
    }
    for order, (nome, peso, pct) in enumerate(
        (
            ("Elaboração", D("40"), D("100")),
            ("Emissão", D("30"), D("50")),
            ("Construção", D("30"), D("0")),
        ),
        start=1,
    ):
        sessao.add(
            EapItemStep(item_id=itens["1.1.4"].id, order=order, name=nome, weight=peso, pct=pct)
        )
    sessao.flush()
    return CenarioAvanco(session=sessao, projeto=projeto, unidade=unidade, itens=itens)


def _texto(resposta: func.HttpResponse) -> str:
    return resposta.get_body().decode()


def _toast(resposta: func.HttpResponse) -> str:
    return unquote(resposta.headers["X-TN-Toast"])


def _medicoes(session: Session, item: EapItem) -> list[EapMeasurement]:
    return list(
        session.scalars(
            select(EapMeasurement)
            .where(EapMeasurement.item_id == item.id)
            .order_by(EapMeasurement.id)
        )
    )


def _form(item: EapItem, **campos: str) -> dict[str, str]:
    return {"versao": str(item.version), "data": "2026-09-20", **campos}


def _chamar_formulario(
    cenario: CenarioAvanco, item: EapItem, *, email: str = EMAIL_MEMBRO, alpine: bool = True
) -> func.HttpResponse:
    return routes.eap_progress_form(
        pedido(
            f"{BASE}/itens/{item.id}/avanco",
            email=email,
            envio=Envio(
                params=cenario.params,
                alvo=ALVO_FORMULARIO,
                rota={"item_id": str(item.id)},
                alpine=alpine,
            ),
        )
    )


def _chamar_gravacao(
    cenario: CenarioAvanco,
    item: EapItem,
    campos: Mapping[str, str],
    *,
    email: str = EMAIL_MEMBRO,
    alpine: bool = True,
) -> func.HttpResponse:
    return routes.eap_progress_save(
        pedido(
            f"{BASE}/itens/{item.id}/avanco",
            email=email,
            envio=Envio(
                metodo="POST",
                campos=campos,
                params=cenario.params,
                rota={"item_id": str(item.id)},
                alvo=f"{ALVO_FORMULARIO} {ALVO_CONTEUDO}",
                alpine=alpine,
            ),
        )
    )


def _planilha(*linhas: tuple[object, ...]) -> bytes:
    return planilha(linhas, cabecalho=AVANCO_HEADERS)


def _pedido_com_arquivo(
    caminho: str,
    conteudo: bytes,
    campos: Mapping[str, str],
    *,
    params: Mapping[str, str],
    email: str = EMAIL_MEMBRO,
) -> func.HttpRequest:
    body, content_type = corpo_multipart(campos, ("avanco.xlsx", conteudo))
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
    cenario: CenarioAvanco,
    conteudo: bytes,
    *,
    campos: Mapping[str, str] | None = None,
    email: str = EMAIL_MEMBRO,
    params: Mapping[str, str] | None = None,
) -> func.HttpResponse:
    dados = {"data": "2026-09-20"}
    dados.update(campos or {})
    return routes.eap_progress_import_check(
        _pedido_com_arquivo(
            f"{BASE}/importar/conferir",
            conteudo,
            dados,
            params=params if params is not None else cenario.params,
            email=email,
        )
    )


def _confirmar(
    cenario: CenarioAvanco,
    conteudo: bytes,
    *,
    campos: Mapping[str, str] | None = None,
    email: str = EMAIL_MEMBRO,
) -> func.HttpResponse:
    digest = importing.digest_of(importing.Upload(name="avanco.xlsx", content=conteudo))
    dados = {"data": "2026-09-20", "conferido": digest, "ciente": "sim"}
    dados.update(campos or {})
    return routes.eap_progress_import_confirm(
        _pedido_com_arquivo(
            f"{BASE}/importar/confirmar", conteudo, dados, params=cenario.params, email=email
        )
    )


# ── O formulário, por critério ───────────────────────────────────────────


@pytest.mark.parametrize(
    ("codigo", "campo"),
    (
        ("1.1.1", "executado"),
        ("1.1.2", "estado"),
        ("1.1.3", "estado"),
        ("1.1.4", "etapa0"),
        ("1.1.5", "estimadoPct"),
    ),
)
def test_o_formulario_do_avanco_traz_a_entrada_do_criterio(
    cenario_avanco: CenarioAvanco, codigo: str, campo: str
) -> None:
    item = cenario_avanco.itens[codigo]

    resposta = _chamar_formulario(cenario_avanco, item)

    texto = _texto(resposta)
    names = {
        tag.attrs.get("name")
        for tag in parse_tags(texto)
        if tag.name in {"input", "textarea", "select"}
    }
    assert resposta.status_code == 200
    assert find_by_id(parse_tags(texto), ALVO_FORMULARIO) is not None
    assert {"data", "versao", "obs", "justificativa", campo} <= names
    assert "Registrar avanço" in texto
    assert HOJE.isoformat() in texto


def test_o_formulario_do_avanco_recusa_o_pacote_de_planejamento(
    cenario_avanco: CenarioAvanco,
) -> None:
    resposta = _chamar_formulario(cenario_avanco, cenario_avanco.itens["1.1.7"])

    assert resposta.status_code == 422
    assert service.PLANNING_PACKAGE_PROGRESS_MESSAGE in _texto(resposta)


def test_o_avanco_recusa_o_portfolio(cenario_avanco: CenarioAvanco) -> None:
    item = cenario_avanco.itens["1.1.1"]

    formulario = routes.eap_progress_form(
        pedido(
            f"{BASE}/itens/{item.id}/avanco",
            email=EMAIL_MEMBRO,
            envio=Envio(alvo=ALVO_FORMULARIO, rota={"item_id": str(item.id)}),
        )
    )
    gravacao = routes.eap_progress_save(
        pedido(
            f"{BASE}/itens/{item.id}/avanco",
            email=EMAIL_MEMBRO,
            envio=Envio(
                metodo="POST",
                campos=_form(item, executado="95"),
                rota={"item_id": str(item.id)},
                alvo=f"{ALVO_FORMULARIO} {ALVO_CONTEUDO}",
            ),
        )
    )

    assert formulario.status_code == 403
    assert gravacao.status_code == 403
    assert _medicoes(cenario_avanco.session, item) == []


def test_sem_o_cabecalho_do_alpine_a_rota_manda_para_o_shell(
    cenario_avanco: CenarioAvanco,
) -> None:
    item = cenario_avanco.itens["1.1.1"]

    formulario = _chamar_formulario(cenario_avanco, item, alpine=False)
    gravacao = _chamar_gravacao(cenario_avanco, item, _form(item, executado="95"), alpine=False)

    assert formulario.status_code == 302
    assert gravacao.status_code == 302


# ── A gravação, por critério ─────────────────────────────────────────────


def test_registrar_por_unidades_responde_o_conteudo_e_fecha_o_formulario(
    cenario_avanco: CenarioAvanco,
) -> None:
    item = cenario_avanco.itens["1.1.1"]

    resposta = _chamar_gravacao(cenario_avanco, item, _form(item, executado="95", obs="Boletim 3"))

    texto = _texto(resposta)
    tags = parse_tags(texto)
    assert resposta.status_code == 200
    assert find_by_id(tags, ALVO_CONTEUDO) is not None
    formulario = find_by_id(tags, ALVO_FORMULARIO)
    assert formulario is not None
    assert formulario.clean_text() == ""
    assert _toast(resposta) == "Avanço de 1.1.1 registrado: 90,0% para 95,0%."
    cenario_avanco.session.refresh(item)
    assert item.executed == D("95")
    medicao = _medicoes(cenario_avanco.session, item)[-1]
    assert (medicao.from_pct, medicao.to_pct, medicao.measured_on, medicao.note) == (
        D("90.00"),
        D("95.00"),
        date(2026, 9, 20),
        "Boletim 3",
    )


def test_registrar_por_marco_0_100_atualiza_a_situacao(cenario_avanco: CenarioAvanco) -> None:
    item = cenario_avanco.itens["1.1.2"]

    resposta = _chamar_gravacao(cenario_avanco, item, _form(item, estado="Concluído"))

    assert resposta.status_code == 200
    cenario_avanco.session.refresh(item)
    assert item.state == "Concluído"
    assert item.version > 0
    medicao = _medicoes(cenario_avanco.session, item)[-1]
    assert (medicao.from_pct, medicao.to_pct) == (D("0.00"), D("100.00"))


def test_registrar_por_marco_50_50_atualiza_a_situacao(cenario_avanco: CenarioAvanco) -> None:
    item = cenario_avanco.itens["1.1.3"]

    resposta = _chamar_gravacao(cenario_avanco, item, _form(item, estado="Concluído"))

    assert resposta.status_code == 200
    cenario_avanco.session.refresh(item)
    assert item.state == "Concluído"
    medicao = _medicoes(cenario_avanco.session, item)[-1]
    assert (medicao.from_pct, medicao.to_pct) == (D("50.00"), D("100.00"))


def test_registrar_por_etapas_grava_o_percentual_de_cada_etapa(
    cenario_avanco: CenarioAvanco,
) -> None:
    item = cenario_avanco.itens["1.1.4"]

    resposta = _chamar_gravacao(
        cenario_avanco,
        item,
        _form(item, etapa0="100", etapa1="100", etapa2="50"),
    )

    assert resposta.status_code == 200
    etapas = list(
        cenario_avanco.session.scalars(
            select(EapItemStep).where(EapItemStep.item_id == item.id).order_by(EapItemStep.order)
        )
    )
    assert [etapa.pct for etapa in etapas] == [D(100), D(100), D(50)]
    medicao = _medicoes(cenario_avanco.session, item)[-1]
    assert (medicao.from_pct, medicao.to_pct) == (D("55.00"), D("85.00"))


def test_registrar_por_percentual_estimado_atualiza_o_real(
    cenario_avanco: CenarioAvanco,
) -> None:
    item = cenario_avanco.itens["1.1.5"]

    resposta = _chamar_gravacao(
        cenario_avanco, item, _form(item, estimadoPct="60", obs="Avanço estimado em campo")
    )

    assert resposta.status_code == 200
    cenario_avanco.session.refresh(item)
    assert item.estimated_pct == D("60")
    medicao = _medicoes(cenario_avanco.session, item)[-1]
    assert (medicao.from_pct, medicao.to_pct) == (D("20.00"), D("60.00"))


# ── As recusas por campo e o estorno ─────────────────────────────────────


def test_executado_acima_da_linha_de_base_volta_422_com_a_mensagem_no_campo(
    cenario_avanco: CenarioAvanco,
) -> None:
    item = cenario_avanco.itens["1.1.1"]

    resposta = _chamar_gravacao(cenario_avanco, item, _form(item, executado="150"))

    texto = _texto(resposta)
    assert resposta.status_code == 422
    assert validation.EXECUTED_OVER_QUANTITY_MESSAGE.format(quantity="100", unit="m") in texto
    assert find_by_id(parse_tags(texto), ALVO_FORMULARIO) is not None
    assert "input--erro" in texto
    cenario_avanco.session.refresh(item)
    assert item.executed == D("90")
    assert _medicoes(cenario_avanco.session, item) == []


def test_marco_fora_dos_degraus_volta_422(cenario_avanco: CenarioAvanco) -> None:
    item = cenario_avanco.itens["1.1.2"]

    resposta = _chamar_gravacao(cenario_avanco, item, _form(item, estado="Meio"))

    texto = _texto(resposta)
    assert resposta.status_code == 422
    assert validation.MILESTONE_STATE_MESSAGE in texto
    assert find_by_id(parse_tags(texto), ALVO_FORMULARIO) is not None
    assert _medicoes(cenario_avanco.session, item) == []


def test_estimado_acima_do_peso_maximo_volta_422(cenario_avanco: CenarioAvanco) -> None:
    item = cenario_avanco.itens["1.1.6"]

    resposta = _chamar_gravacao(cenario_avanco, item, _form(item, estimadoPct="50"))

    texto = _texto(resposta)
    assert resposta.status_code == 422
    assert validation.ESTIMATED_WEIGHT_MESSAGE.format(maximum="5") in texto
    assert _medicoes(cenario_avanco.session, item) == []


def test_estorno_sem_gestor_volta_403_com_a_mensagem_no_lugar(
    cenario_avanco: CenarioAvanco,
) -> None:
    item = cenario_avanco.itens["1.1.1"]

    resposta = _chamar_gravacao(cenario_avanco, item, _form(item, executado="50"))

    texto = _texto(resposta)
    tags = parse_tags(texto)
    assert resposta.status_code == 403
    assert validation.REVERSAL_MANAGER_MESSAGE in texto
    assert find_by_id(tags, ALVO_FORMULARIO) is not None
    assert find_by_id(tags, ALVO_CONTEUDO) is not None
    cenario_avanco.session.refresh(item)
    assert item.executed == D("90")
    assert _medicoes(cenario_avanco.session, item) == []


def test_estorno_com_gestor_e_justificativa_grava_a_medicao(
    cenario_avanco: CenarioAvanco,
) -> None:
    item = cenario_avanco.itens["1.1.1"]

    resposta = _chamar_gravacao(
        cenario_avanco,
        item,
        _form(item, executado="50", justificativa="Retrabalho das estacas refeito"),
        email=EMAIL_GESTOR,
    )

    assert resposta.status_code == 200
    cenario_avanco.session.refresh(item)
    assert item.executed == D("50")
    medicao = _medicoes(cenario_avanco.session, item)[-1]
    assert (medicao.from_pct, medicao.to_pct, medicao.note) == (
        D("90.00"),
        D("50.00"),
        "Retrabalho das estacas refeito",
    )


def test_a_versao_vencida_volta_409(cenario_avanco: CenarioAvanco) -> None:
    item = cenario_avanco.itens["1.1.1"]

    resposta = _chamar_gravacao(
        cenario_avanco, item, {**_form(item, executado="95"), "versao": "999"}
    )

    assert resposta.status_code == 409
    assert _medicoes(cenario_avanco.session, item) == []


def test_o_visualizador_recebe_403_no_formulario_e_na_gravacao(
    cenario_avanco: CenarioAvanco,
) -> None:
    item = cenario_avanco.itens["1.1.1"]

    formulario = _chamar_formulario(cenario_avanco, item, email=EMAIL_VISUALIZADOR)
    gravacao = _chamar_gravacao(
        cenario_avanco, item, _form(item, executado="95"), email=EMAIL_VISUALIZADOR
    )

    assert formulario.status_code == 403
    assert gravacao.status_code == 403


# ── A importação do avanço ───────────────────────────────────────────────


def test_o_formulario_da_importacao_traz_a_data_e_o_modelo(
    cenario_avanco: CenarioAvanco,
) -> None:
    resposta = routes.eap_progress_import_form(
        pedido(
            f"{BASE}/importar/formulario",
            email=EMAIL_MEMBRO,
            envio=Envio(params=cenario_avanco.params, alvo=ALVO_FORMULARIO),
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
    assert {"data", "arquivo"} <= names
    assert f"/api/importacao/{importers.PROGRESS_KEY}/modelo" in texto


def test_a_importacao_confere_sem_gravar_e_mostra_os_erros_por_linha(
    cenario_avanco: CenarioAvanco,
) -> None:
    item = cenario_avanco.itens["1.1.1"]
    conteudo = _planilha(
        ("1.1.1", None, 95),
        ("1.1.3", 0, None),
        ("1.1.7", 50, None),
        ("9.9.9", 50, None),
    )

    resposta = _conferir(cenario_avanco, conteudo)

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert find_by_id(parse_tags(texto), ALVO_RESULTADO) is not None
    assert "Vão ser gravadas" in texto
    assert "1.1.1" in texto
    assert (
        validation.IMPORT_REGRESSION_MESSAGE.format(code="1.1.3", from_pct="50", to_pct="0")
        in texto
    )
    assert validation.IMPORT_PLANNING_MESSAGE.format(code="1.1.7") in texto
    assert validation.IMPORT_PACKAGE_NOT_FOUND_MESSAGE.format(code="9.9.9") in texto
    assert _medicoes(cenario_avanco.session, item) == []


def test_a_importacao_grava_as_validas_so_na_confirmacao_com_o_relatorio_de_erros(
    cenario_avanco: CenarioAvanco,
) -> None:
    item = cenario_avanco.itens["1.1.1"]
    conteudo = _planilha(("1.1.1", None, 95), ("9.9.9", 50, None))

    resposta = _confirmar(cenario_avanco, conteudo)

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert "1 linha(s) de Avanço da EAP importada(s)" in texto
    assert validation.IMPORT_PACKAGE_NOT_FOUND_MESSAGE.format(code="9.9.9") in texto
    medicao = _medicoes(cenario_avanco.session, item)[-1]
    assert (
        medicao.from_pct,
        medicao.to_pct,
        medicao.measured_on,
        medicao.note,
    ) == (D("90.00"), D("95.00"), date(2026, 9, 20), service.IMPORT_NOTE)
    cenario_avanco.session.refresh(item)
    assert item.executed == D("95")


def test_a_importacao_recusa_a_data_futura(cenario_avanco: CenarioAvanco) -> None:
    resposta = _conferir(
        cenario_avanco, _planilha(("1.1.1", None, 95)), campos={"data": "2026-09-26"}
    )

    assert resposta.status_code == 422
    assert validation.MEASUREMENT_DATE_FUTURE_MESSAGE in _texto(resposta)


def test_a_importacao_recusa_o_portfolio(cenario_avanco: CenarioAvanco) -> None:
    formulario = routes.eap_progress_import_form(
        pedido(f"{BASE}/importar/formulario", email=EMAIL_MEMBRO, envio=Envio())
    )
    conferencia = _conferir(cenario_avanco, _planilha(("1.1.1", None, 95)), params={})

    assert formulario.status_code == 422
    assert "Escolha um projeto" in _texto(formulario)
    assert conferencia.status_code == 422
    assert "Escolha um projeto" in _texto(conferencia)


def test_o_importador_do_avanco_grava_pelo_fluxo_generico(cenario_avanco: CenarioAvanco) -> None:
    assert importing.find(importers.PROGRESS_KEY) is not None
    item = cenario_avanco.itens["1.1.1"]
    conteudo = _planilha(("1.1.1", None, 95))
    digest = importing.digest_of(importing.Upload(name="avanco.xlsx", content=conteudo))
    body, content_type = corpo_multipart(
        {"conferido": digest, "ciente": "sim"}, ("avanco.xlsx", conteudo)
    )
    request = func.HttpRequest(
        method="POST",
        url=f"/api/importacao/{importers.PROGRESS_KEY}/confirmar",
        headers={
            auth.PRINCIPAL_HEADER: cabecalho_do_principal(EMAIL_MEMBRO),
            "Content-Type": content_type,
            "X-Alpine-Request": "true",
            "X-Alpine-Target": ALVO_RESULTADO,
        },
        params=dict(cenario_avanco.params),
        route_params={"chave": importers.PROGRESS_KEY},
        body=body,
    )

    resposta = generic_confirm(request)

    assert resposta.status_code == 200
    medicao = _medicoes(cenario_avanco.session, item)[-1]
    assert (medicao.to_pct, medicao.measured_on, medicao.note) == (
        D("95.00"),
        HOJE,
        service.IMPORT_NOTE,
    )
