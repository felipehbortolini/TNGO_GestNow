"""As rotas dos processos de compra (ISSUE-059): a tela, a ficha, os formulários e as recusas.

A rota roda na transação do teste (fixture ``sessao``), no modo demonstração e com o relógio em
25/09/2026. A requisição é montada como o shell a envia: cabeçalho do Alpine AJAX, o principal do
colaborador e o escopo no parâmetro ``projeto``; a proposta é um ``multipart/form-data`` com o
PDF.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from urllib.parse import urlencode

import azure.functions as func
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import auth, file_storage
from src.core.models import Attachment
from src.core.scope import Scope
from src.modulos.suprimentos import routes, service, validation
from src.modulos.suprimentos.models import PackageMilestone, ProcessProposal
from tests.apoio_pacotes import REFERENCIA
from tests.apoio_processos import CenarioProcessos, montar_cenario_processos
from tests.armazenamento_falso import ArmazenamentoEmMemoria
from tests.identidades import cabecalho_do_principal, requisicao

ANA = "ana.admin@plano.example.invalid"
VITOR = "vitor.visualizador@plano.example.invalid"
BOUNDARY = "fronteira-do-teste-dos-processos"


@pytest.fixture
def cenario_processos(sessao: Session) -> CenarioProcessos:
    """O cenário do processo na sessão do teste, servindo as rotas pela unidade de trabalho."""
    return montar_cenario_processos(sessao)


@pytest.fixture
def armazenamento(monkeypatch: pytest.MonkeyPatch) -> ArmazenamentoEmMemoria:
    """O PDF da proposta fica na memória: o teste lê o que foi guardado."""
    storage = ArmazenamentoEmMemoria()
    monkeypatch.setattr(file_storage, "configured_storage", lambda: storage)
    return storage


def _params(cenario: CenarioProcessos) -> dict[str, str]:
    return {"projeto": str(cenario.projeto.id)}


def _post(cenario: CenarioProcessos, caminho: str, nome: str | None = None, **corpo: str):
    rota = {"pacote_id": str(cenario.pacote.id), "nome": nome} if nome is not None else {}
    return requisicao(
        caminho,
        metodo="POST",
        email=ANA,
        params=_params(cenario),
        rota=rota,
        corpo=corpo,
        alvo="processo-modal-corpo",
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


def _post_proposta(
    cenario: CenarioProcessos, *, email: str = ANA, com_arquivo: bool = True
) -> func.HttpRequest:
    fields = {
        "empresa": str(cenario.fornecedores[0].id),
        "nome": "",
        "data": date(2026, 8, 20).isoformat(),
        "valor": "400.000,00",
        "prazo": "90",
        "consulta": "",
    }
    files = ("proposta.pdf", b"%PDF-1.7 proposta") if com_arquivo else None
    body, content_type = _multipart(fields, files)
    return func.HttpRequest(
        method="POST",
        url=f"/api/suprimentos/processos/{cenario.pacote.id}/acao/proposta",
        headers={
            "X-Alpine-Request": "true",
            "X-Alpine-Target": "processo-modal-corpo",
            auth.PRINCIPAL_HEADER: cabecalho_do_principal(email),
            "Content-Type": content_type,
        },
        params=_params(cenario),
        route_params={"pacote_id": str(cenario.pacote.id), "nome": "proposta"},
        body=body,
    )


def _emitir_rfx(sessao: Session, cenario: CenarioProcessos) -> None:
    service.issue_rfx(
        sessao,
        user=cenario.ana,
        scope=Scope(project_id=cenario.projeto.id, source="url"),
        package_id=cenario.pacote.id,
        data=validation.RfxInput(
            date=date(2026, 8, 10),
            deadline=date(2026, 8, 31),
            weight_technical=40,
            weight_commercial=60,
            invitees=tuple(empresa.id for empresa in cenario.fornecedores),
        ),
        reference_date=REFERENCIA,
    )


def test_a_rota_da_lista_responde_o_fragmento_da_tela(cenario_processos: CenarioProcessos) -> None:
    resposta = routes.process_list(
        requisicao(
            "/api/suprimentos/processos",
            email=ANA,
            params=_params(cenario_processos),
            alvo="processos-conteudo",
        )
    )

    assert resposta.status_code == 200
    corpo = resposta.get_body().decode()
    assert 'id="processos-conteudo"' in corpo
    assert 'data-grafico="etapas"' in corpo
    assert "PC-01" in corpo


def test_a_rota_da_ficha_traz_o_mapa_e_o_historico(cenario_processos: CenarioProcessos) -> None:
    resposta = routes.process_sheet(
        requisicao(
            "/api/suprimentos/processos/ficha",
            email=ANA,
            params={**_params(cenario_processos), "pacote": str(cenario_processos.pacote.id)},
            alvo="processo-ficha",
        )
    )

    assert resposta.status_code == 200
    corpo = resposta.get_body().decode()
    assert 'id="processo-ficha"' in corpo
    assert "Mapa de equalização" in corpo
    assert "Histórico do processo" in corpo


def test_a_rota_da_requisicao_desenha_o_formulario(cenario_processos: CenarioProcessos) -> None:
    resposta = routes.process_requisition_form(
        requisicao(
            "/api/suprimentos/processos/requisicao",
            email=ANA,
            params=_params(cenario_processos),
            alvo="processo-modal-corpo",
        )
    )

    assert resposta.status_code == 200
    corpo = resposta.get_body().decode()
    assert "Pacote do plano de compras" in corpo
    assert "PC-02" in corpo


def test_o_post_da_requisicao_cria_o_marco(
    sessao: Session, cenario_processos: CenarioProcessos
) -> None:
    resposta = routes.process_requisition_save(
        _post(
            cenario_processos,
            "/api/suprimentos/processos/requisicao",
            pacote=str(cenario_processos.planejado.id),
            data=REFERENCIA.isoformat(),
            documento="RM-MEC-0042 rev. 0",
            observacao="",
            consulta="",
        )
    )

    assert resposta.status_code == 200
    marco = sessao.scalars(
        select(PackageMilestone).where(
            PackageMilestone.package_id == cenario_processos.planejado.id,
            PackageMilestone.milestone == "requisicao",
        )
    ).one()
    assert marco.real_date == REFERENCIA


def test_a_rota_rfx_desenha_o_formulario(cenario_processos: CenarioProcessos) -> None:
    resposta = routes.process_action_form(
        requisicao(
            f"/api/suprimentos/processos/{cenario_processos.pacote.id}/acao/rfx",
            email=ANA,
            params=_params(cenario_processos),
            rota={"pacote_id": str(cenario_processos.pacote.id), "nome": "rfx"},
            alvo="processo-modal-corpo",
        )
    )

    assert resposta.status_code == 200
    corpo = resposta.get_body().decode()
    assert "Emitir RFx" in corpo
    assert "Alfa Fornecimentos de teste" in corpo


def test_o_post_da_rfx_invalido_devolve_o_formulario_no_modal(
    cenario_processos: CenarioProcessos,
) -> None:
    resposta = routes.process_action_save(
        _post(
            cenario_processos,
            f"/api/suprimentos/processos/{cenario_processos.pacote.id}/acao/rfx",
            nome="rfx",
            data="2026-08-10",
            dataLimite="2026-08-31",
            pesoTecnico="40",
            pesoComercial="60",
            convidados=str(cenario_processos.fornecedores[0].id),
            consulta="",
        )
    )

    assert resposta.status_code == 422
    corpo = resposta.get_body().decode()
    assert 'id="processo-modal-corpo"' in corpo
    assert "Convide ao menos" in corpo


def test_o_post_da_proposta_grava_o_anexo(
    sessao: Session, cenario_processos: CenarioProcessos, armazenamento: ArmazenamentoEmMemoria
) -> None:
    _emitir_rfx(sessao, cenario_processos)

    resposta = routes.process_action_save(_post_proposta(cenario_processos))

    assert resposta.status_code == 200
    proposta = sessao.scalars(select(ProcessProposal)).one()
    anexo = sessao.scalars(
        select(Attachment).where(Attachment.origin_table == service.PROPOSAL_ATTACHMENT_TABLE)
    ).one()
    assert anexo.origin_record_id == proposta.id
    assert anexo.name == "proposta.pdf"
    assert armazenamento.arquivos


def test_a_proposta_sem_arquivo_devolve_o_formulario_no_modal(
    sessao: Session, cenario_processos: CenarioProcessos
) -> None:
    _emitir_rfx(sessao, cenario_processos)

    resposta = routes.process_action_save(_post_proposta(cenario_processos, com_arquivo=False))

    assert resposta.status_code == 422
    assert "arquivo" in resposta.get_body().decode().lower()
    assert sessao.scalars(select(ProcessProposal)).all() == []


def test_o_visualizador_recebe_403_na_gravacao(cenario_processos: CenarioProcessos) -> None:
    resposta = routes.process_action_save(
        requisicao(
            f"/api/suprimentos/processos/{cenario_processos.pacote.id}/acao/rfx",
            metodo="POST",
            email=VITOR,
            params=_params(cenario_processos),
            rota={"pacote_id": str(cenario_processos.pacote.id), "nome": "rfx"},
            corpo={"data": "2026-08-10", "dataLimite": "2026-08-31"},
            alvo="processo-modal-corpo",
        )
    )

    assert resposta.status_code == 403


def test_o_excel_da_lista_e_um_arquivo(cenario_processos: CenarioProcessos) -> None:
    resposta = routes.process_list_excel(
        requisicao(
            "/api/suprimentos/processos/excel",
            email=ANA,
            params=_params(cenario_processos),
            alvo="processos-conteudo",
        )
    )

    assert resposta.status_code == 200
    assert resposta.get_body().startswith(b"PK"), "o .xlsx é um zip"


def test_a_consulta_da_lista_chega_as_rotas(cenario_processos: CenarioProcessos) -> None:
    consulta = urlencode({"busca": "PC-01", "situacao": "todos"})
    resposta = routes.process_list(
        requisicao(
            "/api/suprimentos/processos",
            email=ANA,
            params={**_params(cenario_processos), "busca": "PC-01", "situacao": "todos"},
            alvo="processos-conteudo",
        )
    )

    assert resposta.status_code == 200
    corpo = resposta.get_body().decode()
    assert "PC-01" in corpo
    assert consulta.split("&")[0] in corpo, "a consulta viaja nos links e formulários"
