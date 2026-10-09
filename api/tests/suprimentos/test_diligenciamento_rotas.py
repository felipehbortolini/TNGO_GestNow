"""As rotas do diligenciamento (ISSUE-061): a tela, os formulários, as recusas e o 403.

A rota roda na transação do teste (fixture ``sessao``), no modo demonstração e com o relógio em
25/09/2026. A requisição é montada como o shell a envia: cabeçalho do Alpine AJAX, o principal do
colaborador e o escopo no parâmetro ``projeto``; o recebimento é um ``multipart/form-data`` com a
evidência.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from urllib.parse import unquote

import azure.functions as func
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import auth, file_storage
from src.core.models import Attachment
from src.core.scope import Scope
from src.modulos.central_acoes.models import Action
from src.modulos.suprimentos import routes, service, validation
from src.modulos.suprimentos.models import DeliveryReceipt, PurchaseOrderMilestone
from tests.apoio_diligenciamento import (
    REFERENCIA,
    CenarioDiligenciamento,
    montar_cenario_diligenciamento,
    tornar_critico,
)
from tests.armazenamento_falso import ArmazenamentoEmMemoria
from tests.identidades import cabecalho_do_principal, requisicao

ANA = "ana.admin@plano.example.invalid"
VITOR = "vitor.visualizador@plano.example.invalid"
BOUNDARY = "fronteira-do-teste-do-diligenciamento"
EMBARQUE = date(2026, 9, 24)
ENTREGA = date(2026, 9, 25)


@pytest.fixture
def cenario(sessao: Session) -> CenarioDiligenciamento:
    """O cenário do diligenciamento na sessão do teste, servindo as rotas pela unidade de trabalho."""
    return montar_cenario_diligenciamento(sessao)


@pytest.fixture
def armazenamento(monkeypatch: pytest.MonkeyPatch) -> ArmazenamentoEmMemoria:
    """A evidência do recebimento fica na memória: o teste lê o que foi guardado."""
    storage = ArmazenamentoEmMemoria()
    monkeypatch.setattr(file_storage, "configured_storage", lambda: storage)
    return storage


def _params(cenario: CenarioDiligenciamento) -> dict[str, str]:
    return {"projeto": str(cenario.projeto.id)}


def _rota(cenario: CenarioDiligenciamento, nome: str) -> dict[str, str]:
    return {"pedido_id": str(cenario.pedido.id), "nome": nome}


def _get(cenario: CenarioDiligenciamento, caminho: str, *, nome: str | None = None, **params: str):
    return requisicao(
        caminho,
        email=ANA,
        params={**_params(cenario), **params},
        rota=_rota(cenario, nome) if nome is not None else {},
        alvo="diligenciamento-modal-corpo" if nome is not None else "diligenciamento-conteudo",
    )


def _post(cenario: CenarioDiligenciamento, nome: str, **corpo: str):
    return requisicao(
        f"/api/suprimentos/diligenciamento/{cenario.pedido.id}/{nome}",
        metodo="POST",
        email=ANA,
        params=_params(cenario),
        rota={"pedido_id": str(cenario.pedido.id)},
        corpo=corpo,
        alvo="diligenciamento-modal-corpo" if nome != "acao" else "diligenciamento-conteudo",
    )


def _multipart(
    fields: Mapping[str, str], files: tuple[str, bytes] | None = None
) -> tuple[bytes, str]:
    """A ``multipart/form-data`` body as the browser sends it, and its Content-Type."""
    parts = [
        f'--{BOUNDARY}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        for name, value in fields.items()
    ]
    if files is not None:
        name, content = files
        header = (
            f"--{BOUNDARY}\r\n"
            f'Content-Disposition: form-data; name="arquivo"; filename="{name}"\r\n'
            "Content-Type: application/pdf\r\n\r\n"
        )
        parts.append(header.encode() + content + b"\r\n")
    parts.append(f"--{BOUNDARY}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={BOUNDARY}"


def _post_recebimento(
    cenario: CenarioDiligenciamento, *, email: str = ANA, com_arquivo: bool = True, **campos: str
) -> func.HttpRequest:
    fields = {
        "data": ENTREGA.isoformat(),
        "conferido": "1",
        "pendencias": "",
        "consulta": "",
        **campos,
    }
    files = ("romaneio.pdf", b"%PDF-1.7 romaneio") if com_arquivo else None
    body, content_type = _multipart(fields, files)
    return func.HttpRequest(
        method="POST",
        url=f"/api/suprimentos/diligenciamento/{cenario.pedido.id}/recebimento",
        headers={
            "X-Alpine-Request": "true",
            "X-Alpine-Target": "diligenciamento-modal-corpo",
            auth.PRINCIPAL_HEADER: cabecalho_do_principal(email),
            "Content-Type": content_type,
        },
        params=_params(cenario),
        route_params={"pedido_id": str(cenario.pedido.id)},
        body=body,
    )


def _scope(cenario: CenarioDiligenciamento) -> Scope:
    return Scope(project_id=cenario.projeto.id, source="url")


def _realizar(
    sessao: Session, cenario: CenarioDiligenciamento, position: int, quando: date
) -> None:
    service.update_order_milestone(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        order_id=cenario.pedido.id,
        data=validation.MilestoneInput(index=position, kind="realizado", realized=quando),
        reference_date=REFERENCIA,
    )


def _milestone(
    sessao: Session, cenario: CenarioDiligenciamento, position: int
) -> PurchaseOrderMilestone:
    return sessao.scalars(
        select(PurchaseOrderMilestone).where(
            PurchaseOrderMilestone.order_id == cenario.pedido.id,
            PurchaseOrderMilestone.position == position,
        )
    ).one()


# ── A tela ───────────────────────────────────────────────────────────────────────────────────


def test_a_rota_da_lista_responde_o_fragmento_da_tela(cenario: CenarioDiligenciamento) -> None:
    resposta = routes.order_list(_get(cenario, "/api/suprimentos/diligenciamento"))

    assert resposta.status_code == 200
    corpo = resposta.get_body().decode()
    assert 'id="diligenciamento-conteudo"' in corpo
    assert "PED-2026-0001" in corpo
    assert "Aprovação de documentos" in corpo
    assert "Entrega no prazo (OTD)" in corpo


def test_a_rota_da_lista_no_portfolio_traz_a_coluna_projeto(
    cenario: CenarioDiligenciamento,
) -> None:
    assert cenario.pedido.number == "PED-2026-0001"
    resposta = routes.order_list(
        requisicao(
            "/api/suprimentos/diligenciamento",
            email=ANA,
            alvo="diligenciamento-conteudo",
        )
    )

    assert resposta.status_code == 200
    assert "Projeto" in resposta.get_body().decode()


def test_o_excel_e_o_imprimivel_saem(cenario: CenarioDiligenciamento) -> None:
    excel = routes.order_list_excel(_get(cenario, "/api/suprimentos/diligenciamento/excel"))
    assert excel.status_code == 200
    assert excel.headers.get("Content-Type", "").startswith("application/vnd.openxmlformats")

    pdf = routes.order_list_printable(_get(cenario, "/api/suprimentos/diligenciamento/imprimivel"))
    assert pdf.status_code == 200
    assert "Pedidos em diligenciamento" in pdf.get_body().decode()


# ── Atualizar marco ──────────────────────────────────────────────────────────────────────────


def test_o_formulario_do_marco_lista_os_pendentes(cenario: CenarioDiligenciamento) -> None:
    resposta = routes.order_milestone_form(
        _get(cenario, f"/api/suprimentos/diligenciamento/{cenario.pedido.id}/marco", nome="marco")
    )

    assert resposta.status_code == 200
    corpo = resposta.get_body().decode()
    assert "Salvar marco" in corpo
    assert "Nova previsão" in corpo
    assert "Aprovação de documentos" in corpo
    assert "Entrega" in corpo


def test_o_post_do_marco_sem_o_anterior_devolve_o_formulario(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    resposta = routes.order_milestone_save(
        _post(
            cenario,
            "marco",
            marco="2",
            tipo="realizado",
            realizada="2026-09-21",
            comentario="",
            consulta="",
        )
    )

    assert resposta.status_code == 422
    corpo = resposta.get_body().decode()
    assert 'id="diligenciamento-modal-corpo"' in corpo
    assert "Registre antes o marco anterior" in corpo
    assert _milestone(sessao, cenario, 2).real_date is None


def test_o_post_do_marco_grava_e_atualiza_a_tela(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    resposta = routes.order_milestone_save(
        _post(
            cenario,
            "marco",
            marco="1",
            tipo="realizado",
            realizada="2026-09-20",
            comentario="Visita à fábrica.",
            consulta="",
        )
    )

    assert resposta.status_code == 200
    assert _milestone(sessao, cenario, 1).real_date == date(2026, 9, 20)
    assert 'id="diligenciamento-conteudo"' in resposta.get_body().decode()


def test_o_post_da_acao_cria_e_nao_duplica(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    tornar_critico(cenario, sessao)

    primeira = routes.order_action_save(_post(cenario, "acao", consulta=""))

    assert primeira.status_code == 200
    assert len(sessao.scalars(select(Action)).all()) == 1

    segunda = routes.order_action_save(_post(cenario, "acao", consulta=""))

    assert segunda.status_code == 422
    assert "Já existe ação aberta" in segunda.get_body().decode()
    assert len(sessao.scalars(select(Action)).all()) == 1


# ── Registrar recebimento ────────────────────────────────────────────────────────────────────


def test_o_formulario_do_recebimento_mostra_o_embarque(
    cenario: CenarioDiligenciamento,
) -> None:
    resposta = routes.order_receipt_form(
        _get(
            cenario,
            f"/api/suprimentos/diligenciamento/{cenario.pedido.id}/recebimento",
            nome="recebimento",
        )
    )

    assert resposta.status_code == 200
    corpo = resposta.get_body().decode()
    assert "Data do recebimento" in corpo
    assert "Conferência de quantidade" in corpo
    assert "Registrar recebimento" in corpo


def test_o_post_do_recebimento_sem_embarque_e_recusado(
    sessao: Session, cenario: CenarioDiligenciamento
) -> None:
    resposta = routes.order_receipt_save(_post_recebimento(cenario))

    assert resposta.status_code == 422
    assert "Registre o embarque" in resposta.get_body().decode()
    assert sessao.scalars(select(DeliveryReceipt)).all() == []


def test_o_post_do_recebimento_grava_a_entrega_e_a_evidencia(
    sessao: Session,
    cenario: CenarioDiligenciamento,
    armazenamento: ArmazenamentoEmMemoria,
) -> None:
    _realizar(sessao, cenario, 1, date(2026, 9, 20))
    _realizar(sessao, cenario, 2, date(2026, 9, 21))
    _realizar(sessao, cenario, 3, date(2026, 9, 22))
    _realizar(sessao, cenario, 4, date(2026, 9, 23))
    _realizar(sessao, cenario, 5, EMBARQUE)

    resposta = routes.order_receipt_save(_post_recebimento(cenario))

    assert resposta.status_code == 200
    assert cenario.pedido.delivery == ENTREGA
    assert sessao.scalars(select(DeliveryReceipt)).one().on == ENTREGA
    assert sessao.scalars(select(Attachment)).one().origin_table == "recebimento"
    assert armazenamento.arquivos
    assert "Recebimento de PED-2026-0001" in unquote(resposta.headers.get("X-TN-Toast", ""))
    assert "Entregue" in resposta.get_body().decode()


# ── Permissão ────────────────────────────────────────────────────────────────────────────────


def test_o_visualizador_recebe_403_no_marco(cenario: CenarioDiligenciamento) -> None:
    resposta = routes.order_milestone_save(
        requisicao(
            f"/api/suprimentos/diligenciamento/{cenario.pedido.id}/marco",
            metodo="POST",
            email=VITOR,
            params=_params(cenario),
            rota={"pedido_id": str(cenario.pedido.id)},
            corpo={"marco": "1", "tipo": "realizado", "realizada": "2026-09-20", "consulta": ""},
            alvo="diligenciamento-modal-corpo",
        )
    )

    assert resposta.status_code == 403


def test_o_visualizador_recebe_403_no_recebimento(cenario: CenarioDiligenciamento) -> None:
    resposta = routes.order_receipt_save(_post_recebimento(cenario, email=VITOR))

    assert resposta.status_code == 403
