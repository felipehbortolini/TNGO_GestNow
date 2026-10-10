"""Rotas das Ocorrências do HSE (ISSUE-073, D14): a tela, a ficha, os formulários e as recusas.

O handler é chamado com a requisição de Alpine, o cookie da demonstração identificando a pessoa e
a unidade de trabalho do teste (fixture ``sessao``). O campo restrito (Q35) e o download dos
anexos com dados pessoais exigem Gestor ou Admin: qualquer outro recebe 403.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from urllib.parse import unquote, urlencode

import azure.functions as func
import pytest
from sqlalchemy.orm import Session

from src.blueprints.attachments import download_attachment
from src.core import attachments, config
from src.core.auth import DEMO_COOKIE
from src.core.rbac import User
from src.modulos.hse import ocorrencias_routes as routes
from src.modulos.hse import service
from src.modulos.hse.validation import CorrectiveActionInput, InvestigationInput
from tests.apoio_hse import REFERENCIA, Cenario, ocorrencia_de

ALVO = "ocorrencias-conteudo"
MODAL = "ocorrencias-modal-corpo"
RESTRITO = "ocorrencia-restrito"


def _requisicao(
    usuario: User,
    *,
    metodo: str = "GET",
    params: Mapping[str, str] | None = None,
    corpo: Mapping[str, str] | None = None,
    rota: Mapping[str, str] | None = None,
) -> func.HttpRequest:
    headers = {
        "X-Alpine-Request": "true",
        "X-Alpine-Target": ALVO,
        "Cookie": f"{DEMO_COOKIE}={usuario.id}",
    }
    if corpo is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    return func.HttpRequest(
        method=metodo,
        url="/api/hse/ocorrencias",
        headers=headers,
        params=dict(params or {}),
        route_params=dict(rota or {}),
        body=urlencode(corpo).encode() if corpo is not None else b"",
    )


def _corpo_nova(cenario: Cenario, **campos: str) -> dict[str, str]:
    dados = ocorrencia_de(cenario)
    corpo = {
        "data": dados.happened_on.isoformat(),
        "hora": dados.happened_time,
        "area": dados.area,
        "empresa": str(dados.company_id),
        "tipo": dados.kind,
        "descricao": dados.description,
        "pessoas": str(dados.people_involved),
        "potencial_p": str(dados.potential_p),
        "potencial_i": str(dados.potential_i),
        "gravidade": str(dados.real_gravity),
        "causa_imediata": dados.immediate_cause,
        "comunicacao": str(dados.communication_hours),
        "nome": dados.name,
        "descricao_medica": dados.medical_notes,
        "consulta": "",
    }
    corpo.update(campos)
    return corpo


def _registrar(sessao: Session, cenario: Cenario, **campos: object) -> str:
    salva = service.save_occurrence(
        sessao, user=cenario.maria, data=ocorrencia_de(cenario, **campos), reference_date=REFERENCIA
    )
    return salva.code


def _investigar(sessao: Session, cenario: Cenario, codigo: str) -> None:
    service.record_investigation(
        sessao,
        user=cenario.maria,
        code=codigo,
        data=InvestigationInput(
            method="Árvore de causas",
            root_cause="Ferramenta sem amarração na plataforma de trabalho em altura.",
            investigated_on=REFERENCIA,
        ),
        reference_date=REFERENCIA,
    )


def _definir_acao(sessao: Session, cenario: Cenario, codigo: str) -> None:
    service.define_corrective_actions(
        sessao,
        user=cenario.maria,
        code=codigo,
        actions_input=(
            CorrectiveActionInput(
                subject="Inspeção diária de talabartes",
                responsible_id=cenario.gil.person_id,
                planned_date=REFERENCIA,
            ),
        ),
        reference_date=REFERENCIA,
    )


@pytest.fixture
def pasta_de_anexos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """O armazenamento local dos anexos aponta para uma pasta do teste."""
    monkeypatch.setenv(config.ATTACHMENT_STORAGE_VARIABLE, config.ATTACHMENT_STORAGE_LOCAL)
    monkeypatch.setenv(config.ATTACHMENT_FOLDER_VARIABLE, str(tmp_path))
    return tmp_path


# ── A tela e as exportações ─────────────────────────────────────────────────────────────────


def test_a_tela_traz_os_indicadores_e_a_ocorrencia(sessao: Session, cenario: Cenario) -> None:
    codigo = _registrar(sessao, cenario, hipo=True)

    resposta = routes.occurrence_list_screen(
        _requisicao(cenario.maria, params={"projeto": str(cenario.projeto.id)})
    )
    corpo = resposta.get_body().decode()

    assert resposta.status_code == 200
    assert "Ocorrências no projeto" in corpo
    assert "Alto potencial (HiPo) em aberto" in corpo
    assert "Fora do prazo" in corpo
    assert codigo in corpo
    assert "Nova ocorrência" in corpo


def test_a_tela_no_portfolio_traz_a_coluna_de_projeto(sessao: Session, cenario: Cenario) -> None:
    _registrar(sessao, cenario)

    corpo = routes.occurrence_list_screen(_requisicao(cenario.maria)).get_body().decode()

    assert ">Projeto</th>" in corpo
    assert "TN-HSE-001" in corpo


def test_os_filtros_da_tela_recortam_a_lista(sessao: Session, cenario: Cenario) -> None:
    com_hipo = _registrar(sessao, cenario, hipo=True)
    _registrar(sessao, cenario, happened_time="11:00")

    resposta = routes.occurrence_list_screen(
        _requisicao(cenario.maria, params={"projeto": str(cenario.projeto.id), "hipo": "1"})
    )
    corpo = resposta.get_body().decode()

    assert com_hipo in corpo
    assert "1 ocorrência encontrada" in corpo


def test_o_excel_e_o_imprimivel_saem_no_mesmo_filtro(sessao: Session, cenario: Cenario) -> None:
    codigo = _registrar(sessao, cenario)

    excel = routes.occurrence_list_excel(
        _requisicao(cenario.maria, params={"projeto": str(cenario.projeto.id)})
    )
    imprimivel = routes.occurrence_list_printable(
        _requisicao(cenario.maria, params={"projeto": str(cenario.projeto.id)})
    )

    assert excel.status_code == 200
    assert excel.get_body().startswith(b"PK")
    assert imprimivel.status_code == 200
    assert "Ocorrências HSE" in imprimivel.get_body().decode()
    assert codigo in imprimivel.get_body().decode()


def test_o_imprimivel_no_portfolio_traz_a_coluna_de_projeto(
    sessao: Session, cenario: Cenario
) -> None:
    _registrar(sessao, cenario)

    imprimivel = routes.occurrence_list_printable(_requisicao(cenario.maria))

    assert ">Projeto</th>" in imprimivel.get_body().decode()


# ── A ficha (modal) ─────────────────────────────────────────────────────────────────────────


def test_a_ficha_traz_a_investigacao_e_a_acao_do_fluxo(sessao: Session, cenario: Cenario) -> None:
    codigo = _registrar(sessao, cenario)
    _investigar(sessao, cenario, codigo)

    resposta = routes.occurrence_sheet_fragment(_requisicao(cenario.maria, rota={"codigo": codigo}))
    corpo = resposta.get_body().decode()

    assert resposta.status_code == 200
    assert MODAL in corpo
    assert "Árvore de causas" in corpo
    assert "Ferramenta sem amarração" in corpo
    assert "Nova ação corretiva" in corpo
    assert "Evidências" in corpo
    assert "Dado restrito" not in corpo, "o bloco restrito é da rota própria (Q35)"


# ── O campo restrito (Q35) ──────────────────────────────────────────────────────────────────


def test_o_bloco_restrito_recusa_quem_nao_e_gestor_ou_admin(
    sessao: Session, cenario: Cenario
) -> None:
    codigo = _registrar(sessao, cenario)

    recusada = routes.occurrence_restricted_fragment(
        _requisicao(cenario.maria, rota={"codigo": codigo})
    )
    do_gestor = routes.occurrence_restricted_fragment(
        _requisicao(cenario.gil, rota={"codigo": codigo})
    )
    do_admin = routes.occurrence_restricted_fragment(
        _requisicao(cenario.ada, rota={"codigo": codigo})
    )

    assert recusada.status_code == 403
    assert "Gestor ou Admin" in recusada.get_body().decode()
    assert do_gestor.status_code == 200
    assert RESTRITO in do_gestor.get_body().decode()
    assert "João da Silva" in do_gestor.get_body().decode()
    assert "Sem lesão" in do_gestor.get_body().decode()
    assert do_admin.status_code == 200


def test_a_ficha_do_gestor_carrega_o_bloco_restrito_pela_rota_propria(
    sessao: Session, cenario: Cenario
) -> None:
    codigo = _registrar(sessao, cenario)

    corpo = (
        routes.occurrence_sheet_fragment(_requisicao(cenario.gil, rota={"codigo": codigo}))
        .get_body()
        .decode()
    )

    assert f'id="{RESTRITO}"' in corpo
    assert f"/api/hse/ocorrencias/{codigo}/restrito" in corpo


def test_quem_nao_e_gestor_no_bloco_restrito_recebe_a_mensagem_no_modal(
    sessao: Session, cenario: Cenario
) -> None:
    codigo = _registrar(sessao, cenario)

    resposta = routes.occurrence_restricted_fragment(
        _requisicao(cenario.maria, rota={"codigo": codigo})
    )

    assert resposta.status_code == 403
    assert MODAL in resposta.get_body().decode()
    assert resposta.headers.get("X-TN-Toast") is not None


# ── O download dos anexos com dado pessoal (Q35) ───────────────────────────────────────────


@pytest.mark.usefixtures("pasta_de_anexos")
def test_o_download_do_anexo_e_403_ao_membro_e_liberado_ao_gestor(
    sessao: Session, cenario: Cenario
) -> None:
    codigo = _registrar(sessao, cenario)
    ocorrencia = service.occurrence_by_code(sessao, codigo)
    assert ocorrencia is not None
    conteudo = b"%PDF-1.7 atestado de dados pessoais"
    anexo = attachments.upload(
        sessao,
        user=cenario.maria,
        new=attachments.NewAttachment(
            origin_table="ocorrencia",
            origin_record_id=ocorrencia.id,
            file_name="atestado.pdf",
            content=conteudo,
        ),
        reference_date=REFERENCIA,
    )

    do_membro = download_attachment(_requisicao(cenario.maria, rota={"anexo_id": str(anexo.id)}))
    do_gestor = download_attachment(_requisicao(cenario.gil, rota={"anexo_id": str(anexo.id)}))

    assert do_membro.status_code == 403
    assert "Gestor ou Admin" in do_membro.get_body().decode()
    assert do_gestor.status_code == 200
    assert do_gestor.get_body() == conteudo


# ── Os formulários do fluxo ─────────────────────────────────────────────────────────────────


def test_o_formulario_da_nova_recusa_sem_descricao_e_volta_no_modal(
    sessao: Session, cenario: Cenario
) -> None:
    corpo = _corpo_nova(cenario)
    corpo["descricao"] = "curta"

    resposta = routes.occurrence_new_save(
        _requisicao(
            cenario.maria,
            metodo="POST",
            params={"projeto": str(cenario.projeto.id)},
            corpo=corpo,
        )
    )

    assert resposta.status_code == 422
    assert MODAL in resposta.get_body().decode()
    assert "Descreva o ocorrido" in resposta.get_body().decode()
    assert service.occurrence_by_code(sessao, "OCR-TN-2026-0001") is None


def test_a_nova_grava_e_devolve_a_lista_com_a_ficha_para_reabrir(cenario: Cenario) -> None:
    resposta = routes.occurrence_new_save(
        _requisicao(
            cenario.maria,
            metodo="POST",
            params={"projeto": str(cenario.projeto.id)},
            corpo=_corpo_nova(cenario),
        )
    )
    corpo = resposta.get_body().decode()

    assert resposta.status_code == 200
    assert ALVO in corpo
    assert "OCR-TN-2026-0001" in corpo
    assert 'data-ocorrencias-abrir-ficha="OCR-TN-2026-0001"' in corpo
    tosta = unquote(resposta.headers.get("X-TN-Toast", ""))
    assert tosta.startswith("Ocorrência OCR-TN-2026-0001 registrada")


def test_o_envio_da_acao_cria_na_central_e_atualiza_a_lista(
    sessao: Session, cenario: Cenario
) -> None:
    codigo = _registrar(sessao, cenario)
    _investigar(sessao, cenario, codigo)

    resposta = routes.occurrence_action_save(
        _requisicao(
            cenario.maria,
            metodo="POST",
            params={"projeto": str(cenario.projeto.id)},
            rota={"codigo": codigo},
            corpo={
                "assunto": "Inspeção diária de talabartes",
                "descricao": "Verificação com registro em lista.",
                "responsavel": str(cenario.gil.person_id),
                "prevista": REFERENCIA.isoformat(),
                "consulta": "",
            },
        )
    )

    assert resposta.status_code == 200
    assert unquote(resposta.headers.get("X-TN-Toast", "")) == "Ação corretiva criada na Central."
    assert f'data-ocorrencias-abrir-ficha="{codigo}"' in resposta.get_body().decode()
    sheet = service.occurrence_sheet(
        sessao, user=cenario.gil, code=codigo, reference_date=REFERENCIA
    )
    assert sheet is not None and len(sheet.actions) == 1


def test_encerrar_exige_gestor_na_rota(sessao: Session, cenario: Cenario) -> None:
    codigo = _registrar(sessao, cenario)

    recusada = routes.occurrence_close_form(_requisicao(cenario.maria, rota={"codigo": codigo}))
    do_gestor = routes.occurrence_close_form(_requisicao(cenario.gil, rota={"codigo": codigo}))

    assert recusada.status_code == 403
    assert do_gestor.status_code == 200
    assert "Verificação de eficácia" in do_gestor.get_body().decode()


def test_a_investigacao_pela_rota_move_a_ocorrencia(sessao: Session, cenario: Cenario) -> None:
    codigo = _registrar(sessao, cenario)

    resposta = routes.occurrence_investigate_save(
        _requisicao(
            cenario.maria,
            metodo="POST",
            params={"projeto": str(cenario.projeto.id)},
            rota={"codigo": codigo},
            corpo={
                "metodo": "5 porquês",
                "causa_raiz": "Ferramenta sem amarração durante o trabalho em altura.",
                "data": REFERENCIA.isoformat(),
                "consulta": "",
            },
        )
    )

    ocorrencia = service.occurrence_by_code(sessao, codigo)
    assert resposta.status_code == 200
    assert ocorrencia is not None and ocorrencia.situation == "Em investigação"
