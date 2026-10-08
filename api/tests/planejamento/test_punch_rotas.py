"""Rotas da Punch list (ISSUE-049): tela, modais, fluxo, segregação, importação e exportação.

A costura é HTTP: o handler recebe a ``HttpRequest`` do navegador e a resposta é lida como a
pessoa a veria (status, texto, cabeçalho do aviso).
"""

from __future__ import annotations

import html

import azure.functions as func
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import importing
from src.modulos.central_acoes.models import Action
from src.modulos.planejamento import routes, service, validation
from src.modulos.planejamento.models import PunchItem
from tests.apoio_produtividade import Envio, pedido
from tests.apoio_punch import (
    HOJE,
    Cenario,
    campos_do_item,
    enviar_anexo,
    form_item,
    linha_punch,
    montar_cenario,
    planilha_punch,
)
from tests.armazenamento_falso import ArmazenamentoEmMemoria
from tests.identidades import cabecalho_do_principal
from tests.importadores_de_teste import corpo_multipart

BASE = "/api/planejamento/punch"
IMPORTACAO = "/api/importacao/punch-itens"
EMAIL_MEMBRO = "membro-punch@example.invalid"
EMAIL_GESTOR = "gestor-punch@example.invalid"
ALVO_TELA = "punch-filtros punch-conteudo"
ALVO_TRES = "punch-modal punch-filtros punch-conteudo"


def _texto(resposta: func.HttpResponse) -> str:
    return html.unescape(resposta.get_body().decode())


def _projeto(cenario: Cenario) -> dict[str, str]:
    return {"projeto": str(cenario.projeto.id)}


@pytest.fixture
def cenario(sessao: Session) -> Cenario:
    return montar_cenario(sessao)


def _criar(cenario: Cenario, sessao: Session, **overrides: object) -> PunchItem:
    return service.create_punch_item(
        sessao,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        form=form_item(cenario, **overrides),
        reference_date=HOJE,
    )


def _ate_a_verificacao(cenario: Cenario, sessao: Session) -> PunchItem:
    item = _criar(cenario, sessao)
    service.treat_punch_item(
        sessao,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        item_id=item.id,
        version=str(item.version),
        reference_date=HOJE,
    )
    return service.send_punch_item_to_verification(
        sessao,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        item_id=item.id,
        version=str(item.version),
        reference_date=HOJE,
    )


def _ocultos() -> dict[str, str]:
    return {"f_situacao": "abertos", "f_busca": "", "f_categoria": "", "f_vencidos": ""}


def _pedido_planilha(
    caminho: str,
    *,
    conteudo: bytes,
    cenario: Cenario,
    campos: dict[str, str] | None = None,
    alvo: str = "punch-modal",
) -> func.HttpRequest:
    """Um POST com a planilha em ``multipart/form-data``, como o navegador o envia."""
    corpo, content_type = corpo_multipart(campos or {}, ("itens.xlsx", conteudo))
    return func.HttpRequest(
        method="POST",
        url=caminho,
        headers={
            "x-ms-client-principal": cabecalho_do_principal(EMAIL_MEMBRO),
            "X-Alpine-Request": "true",
            "X-Alpine-Target": alvo,
            "Content-Type": content_type,
        },
        params=_projeto(cenario),
        route_params={"chave": "punch-itens"},
        body=corpo,
    )


def test_a_tela_traz_a_barra_e_a_lista(sessao: Session, cenario: Cenario) -> None:
    _criar(cenario, sessao)

    resposta = routes.punch_screen(
        pedido(BASE, email=EMAIL_MEMBRO, envio=Envio(params=_projeto(cenario), alvo=ALVO_TELA))
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert 'id="punch-filtros"' in texto
    assert 'id="punch-conteudo"' in texto
    assert 'data-punch-resultado="conteudo"' in texto
    assert "Itens da Punch list" in texto
    assert "PL-TN-2026-0001" in texto
    assert "Categoria A abertos" in texto


def test_o_portfolio_traz_a_coluna_projeto(sessao: Session, cenario: Cenario) -> None:
    _criar(cenario, sessao)

    resposta = routes.punch_screen(
        pedido(
            BASE,
            email=EMAIL_MEMBRO,
            envio=Envio(params={"projeto": "portfolio"}, alvo=ALVO_TELA),
        )
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert "Projeto" in texto
    assert "TN-PUNCH-001" in texto


def test_o_formulario_novo_abre_no_modal(cenario: Cenario) -> None:
    resposta = routes.punch_new_item(
        pedido(
            f"{BASE}/itens/novo",
            email=EMAIL_MEMBRO,
            envio=Envio(params=_projeto(cenario), alvo="punch-modal"),
        )
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert 'id="punch-modal"' in texto
    assert "Novo item" in texto
    assert "Sistema" in texto
    assert "Abrir item" in texto


def test_a_criacao_grava_e_responde_os_tres_alvos(sessao: Session, cenario: Cenario) -> None:
    campos = {**campos_do_item(cenario), **_ocultos()}

    resposta = routes.punch_create_item(
        pedido(
            f"{BASE}/itens",
            email=EMAIL_MEMBRO,
            envio=Envio(metodo="POST", campos=campos, params=_projeto(cenario), alvo=ALVO_TRES),
        )
    )

    texto = _texto(resposta)
    assert resposta.status_code == 200
    assert resposta.headers.get("X-TN-Toast")
    assert "data-punch-salvo" in texto
    assert 'id="punch-conteudo"' in texto
    assert 'id="punch-modal"' in texto
    item = sessao.scalars(select(PunchItem)).one()
    assert item.code == "PL-TN-2026-0001"
    acao = sessao.scalars(select(Action)).one()
    assert (acao.origin, acao.origin_ref) == ("Punch list", item.code)


def test_a_criacao_invalida_volta_422_com_a_mensagem(sessao: Session, cenario: Cenario) -> None:
    campos = {**campos_do_item(cenario, sistema=""), **_ocultos()}

    resposta = routes.punch_create_item(
        pedido(
            f"{BASE}/itens",
            email=EMAIL_MEMBRO,
            envio=Envio(metodo="POST", campos=campos, params=_projeto(cenario), alvo=ALVO_TRES),
        )
    )

    assert resposta.status_code == 422
    assert "Informe o sistema." in _texto(resposta)
    assert sessao.scalars(select(PunchItem)).all() == []


def test_a_verificacao_com_o_executante_volta_403(sessao: Session, cenario: Cenario) -> None:
    item = _ate_a_verificacao(cenario, sessao)
    campos = {
        validation.FIELD_PUNCH_RESULT: validation.PUNCH_RESULT_APPROVED,
        validation.FIELD_PUNCH_VERIFIER: str(cenario.executante.person_id),
        validation.FIELD_PUNCH_COMMENT: "",
        "versao": str(item.version),
        **_ocultos(),
    }

    resposta = routes.punch_verify_item(
        pedido(
            f"{BASE}/itens/{item.id}/verificacao",
            email=EMAIL_GESTOR,
            envio=Envio(
                metodo="POST",
                campos=campos,
                params=_projeto(cenario),
                rota={"item_id": str(item.id)},
                alvo=ALVO_TRES,
            ),
        )
    )

    assert resposta.status_code == 403
    assert "não pode ser o executante" in _texto(resposta)
    assert item.situation == validation.PUNCH_VERIFYING


def test_o_fechamento_sem_anexo_volta_422(sessao: Session, cenario: Cenario) -> None:
    item = _ate_a_verificacao(cenario, sessao)
    campos = {
        validation.FIELD_PUNCH_RESULT: validation.PUNCH_RESULT_APPROVED,
        validation.FIELD_PUNCH_VERIFIER: str(cenario.gestor.person_id),
        validation.FIELD_PUNCH_COMMENT: "",
        "versao": str(item.version),
        **_ocultos(),
    }

    resposta = routes.punch_verify_item(
        pedido(
            f"{BASE}/itens/{item.id}/verificacao",
            email=EMAIL_GESTOR,
            envio=Envio(
                metodo="POST",
                campos=campos,
                params=_projeto(cenario),
                rota={"item_id": str(item.id)},
                alvo=ALVO_TRES,
            ),
        )
    )

    assert resposta.status_code == 422
    assert service.PUNCH_EVIDENCE_MESSAGE in _texto(resposta)


def test_o_fechamento_com_anexo_fecha_e_conclui_a_acao(sessao: Session, cenario: Cenario) -> None:
    item = _ate_a_verificacao(cenario, sessao)
    enviar_anexo(
        sessao,
        user=cenario.usuario_membro,
        item_id=item.id,
        armazenamento=ArmazenamentoEmMemoria(),
    )
    campos = {
        validation.FIELD_PUNCH_RESULT: validation.PUNCH_RESULT_APPROVED,
        validation.FIELD_PUNCH_VERIFIER: str(cenario.gestor.person_id),
        validation.FIELD_PUNCH_COMMENT: "Conferido em campo.",
        "versao": str(item.version),
        **_ocultos(),
    }

    resposta = routes.punch_verify_item(
        pedido(
            f"{BASE}/itens/{item.id}/verificacao",
            email=EMAIL_GESTOR,
            envio=Envio(
                metodo="POST",
                campos=campos,
                params=_projeto(cenario),
                rota={"item_id": str(item.id)},
                alvo=ALVO_TRES,
            ),
        )
    )

    assert resposta.status_code == 200
    assert "data-punch-salvo" in _texto(resposta)
    assert item.situation == validation.PUNCH_CLOSED
    assert sessao.scalars(select(Action)).one().completed_on == HOJE


def test_o_cancelamento_com_justificativa_curta_volta_422(
    sessao: Session, cenario: Cenario
) -> None:
    item = _criar(cenario, sessao)
    campos = {
        validation.FIELD_PUNCH_JUSTIFICATION: "curta",
        "versao": str(item.version),
        **_ocultos(),
    }

    resposta = routes.punch_cancel_item(
        pedido(
            f"{BASE}/itens/{item.id}/cancelamento",
            email=EMAIL_MEMBRO,
            envio=Envio(
                metodo="POST",
                campos=campos,
                params=_projeto(cenario),
                rota={"item_id": str(item.id)},
                alvo=ALVO_TRES,
            ),
        )
    )

    assert resposta.status_code == 422
    assert validation.PUNCH_JUSTIFICATION_MESSAGE in _texto(resposta)
    assert item.situation == validation.PUNCH_OPEN


def test_o_modal_de_filtros_traz_as_escolhas_e_a_lista_recorta(
    sessao: Session, cenario: Cenario
) -> None:
    _criar(cenario, sessao, categoria="A", tag="310-P-050", descricao="Aterramento incompleto.")
    _criar(cenario, sessao, categoria="B", tag="310-P-051", descricao="Pintura de acabamento.")

    modal = routes.punch_filters(
        pedido(
            f"{BASE}/filtros",
            email=EMAIL_MEMBRO,
            envio=Envio(params=_projeto(cenario), alvo="punch-modal"),
        )
    )
    recorte = routes.punch_screen(
        pedido(
            BASE,
            email=EMAIL_MEMBRO,
            envio=Envio(params={**_projeto(cenario), "categoria": "A"}, alvo=ALVO_TELA),
        )
    )

    texto_modal = _texto(modal)
    assert modal.status_code == 200
    assert 'id="punch-modal"' in texto_modal
    assert 'name="situacao"' in texto_modal
    assert 'name="disciplina"' in texto_modal
    assert "310 Flotação" in texto_modal
    texto_recorte = _texto(recorte)
    assert "310-P-050" in texto_recorte
    assert "310-P-051" not in texto_recorte


def test_a_importacao_grava_so_na_confirmacao(sessao: Session, cenario: Cenario) -> None:
    from src.blueprints.importing import import_check, import_confirm

    conteudo = planilha_punch(linha_punch(cenario))
    conferir = _pedido_planilha(f"{IMPORTACAO}/conferir", conteudo=conteudo, cenario=cenario)

    resposta_conferencia = import_check(conferir)
    texto = _texto(resposta_conferencia)
    assert resposta_conferencia.status_code == 200
    assert "Vão ser gravadas" in texto
    assert "Importar 1 linha(s)" in texto
    assert sessao.scalars(select(PunchItem)).all() == []

    digest = importing.digest_of(importing.Upload(name="itens.xlsx", content=conteudo))
    confirmar = _pedido_planilha(
        f"{IMPORTACAO}/confirmar",
        conteudo=conteudo,
        cenario=cenario,
        campos={"conferido": digest, "ciente": "sim"},
    )
    resposta_confirmacao = import_confirm(confirmar)

    assert resposta_confirmacao.status_code == 200
    item = sessao.scalars(select(PunchItem)).one()
    assert item.code == "PL-TN-2026-0001"
    assert sessao.scalars(select(Action)).one().origin_ref == item.code


def test_a_importacao_recusa_a_linha_invalida_e_grava_a_valida_so_na_confirmacao(
    sessao: Session, cenario: Cenario
) -> None:
    from src.blueprints.importing import import_check, import_confirm

    conteudo = planilha_punch(
        linha_punch(cenario, sistema="999", tag="310-P-060"),
        linha_punch(cenario, tag="310-P-061"),
    )
    conferir = _pedido_planilha(f"{IMPORTACAO}/conferir", conteudo=conteudo, cenario=cenario)

    resposta_conferencia = import_check(conferir)
    assert resposta_conferencia.status_code == 200
    assert "não está no cadastro do projeto" in _texto(resposta_conferencia)
    assert sessao.scalars(select(PunchItem)).all() == []

    digest = importing.digest_of(importing.Upload(name="itens.xlsx", content=conteudo))
    sem_ciente = _pedido_planilha(
        f"{IMPORTACAO}/confirmar",
        conteudo=conteudo,
        cenario=cenario,
        campos={"conferido": digest},
    )
    assert import_confirm(sem_ciente).status_code == 422
    assert sessao.scalars(select(PunchItem)).all() == []

    com_ciente = _pedido_planilha(
        f"{IMPORTACAO}/confirmar",
        conteudo=conteudo,
        cenario=cenario,
        campos={"conferido": digest, "ciente": "sim"},
    )
    resposta = import_confirm(com_ciente)

    assert resposta.status_code == 200
    itens = sessao.scalars(select(PunchItem).order_by(PunchItem.code)).all()
    assert [item.tag for item in itens] == ["310-P-061"]
    assert itens[0].code == "PL-TN-2026-0001"


def test_o_excel_e_o_imprimivel_da_lista(sessao: Session, cenario: Cenario) -> None:
    _criar(cenario, sessao)

    excel = routes.punch_excel(
        pedido(
            f"{BASE}/excel",
            email=EMAIL_MEMBRO,
            envio=Envio(params=_projeto(cenario), alpine=False),
        )
    )
    imprimivel = routes.punch_printable(
        pedido(
            f"{BASE}/imprimivel",
            email=EMAIL_MEMBRO,
            envio=Envio(params={"projeto": "portfolio"}),
        )
    )

    assert excel.status_code == 200
    assert "spreadsheetml" in excel.mimetype
    assert excel.get_body()[:2] == b"PK"
    texto = _texto(imprimivel)
    assert imprimivel.status_code == 200
    assert "Itens da Punch list" in texto
    assert "PL-TN-2026-0001" in texto
    assert "Projeto" in texto


def test_o_visualizador_le_mas_nao_grava(sessao: Session, cenario: Cenario) -> None:
    _criar(cenario, sessao)
    leitura = routes.punch_screen(
        pedido(
            BASE,
            email="visualizador-punch@example.invalid",
            envio=Envio(params=_projeto(cenario), alvo=ALVO_TELA),
        )
    )
    gravacao = routes.punch_create_item(
        pedido(
            f"{BASE}/itens",
            email="visualizador-punch@example.invalid",
            envio=Envio(
                metodo="POST",
                campos={**campos_do_item(cenario), **_ocultos()},
                params=_projeto(cenario),
                alvo=ALVO_TRES,
            ),
        )
    )

    assert leitura.status_code == 200
    assert gravacao.status_code == 403
