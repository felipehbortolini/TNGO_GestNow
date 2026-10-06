"""Itens e revisões da ata (ISSUE-022): numeração por grupo, costura da Central, revisão e histórico.

A anotação é um item da ata (``Informação``) e a ação nasce pela costura da Central (origem ``Ata``),
com o link de volta para a ficha. A nova revisão mantém a linhagem, copia as listas e os itens, e a
lista de atas passa a mostrar só ela; a anterior fica somente leitura.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from urllib.parse import unquote, urlencode

import azure.functions as func
import pytest
from sqlalchemy.orm import Session

from src.core.auth import DEMO_COOKIE
from src.core.errors import InvalidDataError
from src.core.rbac import User
from src.core.scope import Scope
from src.modulos.central_acoes import minutes_routes, minutes_service, service
from src.modulos.central_acoes.calculations import ACTION, INFORMATION, StatusFilter
from src.modulos.central_acoes.models import Action
from src.modulos.central_acoes.validation import (
    ActionFilters,
    ItemInput,
    MinutesFilters,
    NewMinutes,
    ReplanRequest,
    RevisionInput,
)
from src.modulos.configuracoes.models import Unit
from tests.apoio_acoes import REFERENCIA, Cenario


def _unidade(sessao: Session) -> Unit:
    unidade = Unit(kind="organizacional", code="F1", name="Frente 1")
    sessao.add(unidade)
    sessao.flush()
    return unidade


def _ata(sessao: Session, cenario: Cenario, **campos: object) -> minutes_service.MinutesRecord:
    base: dict[str, object] = {
        "project_id": cenario.projeto_a.id,
        "meeting_date": REFERENCIA,
        "meeting_type": "Coordenação de obra",
        "board": "Diretoria de obras",
        "unit_id": _unidade(sessao).id,
        "prepared_by_id": cenario.gil.person_id,
        "subject": "Reunião de coordenação",
        "participant_ids": (cenario.mario.person_id,),
    }
    base.update(campos)
    return minutes_service.create_minutes(
        sessao,
        user=cenario.gil,
        new=NewMinutes(**base),
        reference_date=REFERENCIA,  # type: ignore[arg-type]
    )


def _item(
    sessao: Session, cenario: Cenario, ata: minutes_service.MinutesRecord, **campos: object
) -> minutes_service.ItemRow:
    base: dict[str, object] = {
        "kind": ACTION,
        "group": "Riscos",
        "subject": "Protocolar o monitoramento",
        "description": "Condicionante da licença de operação.",
        "requester_id": cenario.gil.person_id,
        "responsible_id": cenario.mario.person_id,
        "planned_date": REFERENCIA + timedelta(days=10),
        "completed_on": None,
    }
    base.update(campos)
    return minutes_service.save_item(
        sessao,
        user=cenario.gil,
        ref=minutes_service.ItemRef(ata.id, None),
        data=ItemInput(**base),  # type: ignore[arg-type]
        reference_date=REFERENCIA,
    )


def _editar(
    sessao: Session,
    cenario: Cenario,
    ata: minutes_service.MinutesRecord,
    item: minutes_service.ItemRow,
    **campos: object,
) -> minutes_service.ItemRow:
    base: dict[str, object] = {
        "kind": item.kind,
        "group": item.group,
        "subject": item.subject,
        "description": item.description,
        "requester_id": item.requester_id,
        "responsible_id": item.responsible_id,
        "planned_date": item.planned_date,
        "completed_on": item.completed_on,
        "version": sessao.get(Action, item.id).version,  # type: ignore[union-attr]
    }
    base.update(campos)
    return minutes_service.save_item(
        sessao,
        user=cenario.gil,
        ref=minutes_service.ItemRef(ata.id, item.id),
        data=ItemInput(**base),  # type: ignore[arg-type]
        reference_date=REFERENCIA,
    )


# ── Numeração por grupo ──────────────────────────────────────────────────────────────────────


def test_os_itens_saem_numerados_por_grupo(sessao: Session, cenario: Cenario) -> None:
    ata = _ata(sessao, cenario)

    primeiro = _item(sessao, cenario, ata)
    segundo = _item(sessao, cenario, ata, kind=INFORMATION)
    terceiro = _item(sessao, cenario, ata, group="Prazo")

    assert (primeiro.item, segundo.item, terceiro.item) == ("1.1", "1.2", "2.1")

    listing = minutes_service.list_items(
        sessao, user=cenario.gil, minutes_id=ata.id, reference_date=REFERENCIA
    )
    assert [
        (grupo.number, grupo.name, [item.item for item in grupo.items]) for grupo in listing.groups
    ] == [
        ("1", "Riscos", ["1.1", "1.2"]),
        ("2", "Prazo", ["2.1"]),
    ]
    assert (listing.summary.total, listing.summary.information) == (3, 1)


def test_mudar_o_grupo_renumera_o_item(sessao: Session, cenario: Cenario) -> None:
    ata = _ata(sessao, cenario)
    primeiro = _item(sessao, cenario, ata)
    _item(sessao, cenario, ata, group="Prazo")

    movido = _editar(sessao, cenario, ata, primeiro, group="Prazo")

    assert movido.item == "2.2"
    listing = minutes_service.list_items(
        sessao, user=cenario.gil, minutes_id=ata.id, reference_date=REFERENCIA
    )
    assert [
        (grupo.number, grupo.name, [item.item for item in grupo.items]) for grupo in listing.groups
    ] == [
        ("2", "Prazo", ["2.1", "2.2"]),
    ]


# ── Costura da Central ───────────────────────────────────────────────────────────────────────


def test_a_acao_da_ata_aparece_na_central_com_link_de_volta(
    sessao: Session, cenario: Cenario
) -> None:
    ata = _ata(sessao, cenario)
    item = _item(sessao, cenario, ata)

    listing = service.list_actions(
        sessao,
        user=cenario.gil,
        scope=Scope(project_id=cenario.projeto_a.id, source="url"),
        filters=ActionFilters(origin="Ata", status=StatusFilter.ALL),
        reference_date=REFERENCIA,
    )

    linha = next(line for line in listing.rows if line.record.id == item.id)
    assert linha.record.origin == "Ata"
    assert linha.record.origin_ref == ata.number
    assert linha.link.url == f"/central-acoes/ata?id={ata.id}"


def test_a_anotacao_nao_entra_na_lista_da_central(sessao: Session, cenario: Cenario) -> None:
    ata = _ata(sessao, cenario)
    anotacao = _item(sessao, cenario, ata, kind=INFORMATION)

    listing = service.list_actions(
        sessao,
        user=cenario.gil,
        scope=Scope(project_id=cenario.projeto_a.id, source="url"),
        filters=ActionFilters(origin="Ata", status=StatusFilter.ALL),
        reference_date=REFERENCIA,
    )

    assert all(line.record.id != anotacao.id for line in listing.rows)


# ── Nova revisão ─────────────────────────────────────────────────────────────────────────────


def test_a_nova_revisao_mantem_a_linhagem_e_copia_os_itens(
    sessao: Session, cenario: Cenario
) -> None:
    ata = _ata(sessao, cenario)
    _item(sessao, cenario, ata)

    nova = minutes_service.generate_revision(
        sessao,
        user=cenario.gil,
        minutes_id=ata.id,
        data=RevisionInput(meeting_date=REFERENCIA + timedelta(days=7), version=ata.version),
        reference_date=REFERENCIA,
    )

    assert (nova.number, nova.revision) == (ata.number, 1)
    ficha = minutes_service.find_minutes(
        sessao, user=cenario.gil, minutes_id=nova.id, reference_date=REFERENCIA
    )
    assert ficha is not None
    assert len(ficha.attendees) == 2  # elaborado por + convidado
    itens = minutes_service.list_items(
        sessao, user=cenario.gil, minutes_id=nova.id, reference_date=REFERENCIA
    )
    assert [item.item for grupo in itens.groups for item in grupo.items] == ["1.1"]

    listing = minutes_service.list_minutes(
        sessao,
        user=cenario.gil,
        scope=Scope(project_id=cenario.projeto_a.id, source="url"),
        filters=MinutesFilters(),
        reference_date=REFERENCIA,
    )
    assert [line.record.id for line in listing.rows] == [nova.id]


def test_a_revisao_anterior_fica_somente_leitura(sessao: Session, cenario: Cenario) -> None:
    ata = _ata(sessao, cenario)
    minutes_service.generate_revision(
        sessao,
        user=cenario.gil,
        minutes_id=ata.id,
        data=RevisionInput(meeting_date=REFERENCIA + timedelta(days=7), version=ata.version),
        reference_date=REFERENCIA,
    )

    with pytest.raises(InvalidDataError) as recusa:
        _item(sessao, cenario, ata)

    assert "somente leitura" in str(recusa.value)


def test_o_historico_lista_as_revisoes_com_a_vigente_marcada(
    sessao: Session, cenario: Cenario
) -> None:
    ata = _ata(sessao, cenario)
    nova = minutes_service.generate_revision(
        sessao,
        user=cenario.gil,
        minutes_id=ata.id,
        data=RevisionInput(meeting_date=REFERENCIA + timedelta(days=7), version=ata.version),
        reference_date=REFERENCIA,
    )

    historico = minutes_service.revision_history(sessao, user=cenario.gil, minutes_id=nova.id)

    assert [(linha.revision, linha.is_latest) for linha in historico] == [(1, True), (0, False)]


# ── Replanejamento e justificativas ──────────────────────────────────────────────────────────


def test_o_replanejamento_do_item_guarda_autor_data_e_justificativa(
    sessao: Session, cenario: Cenario
) -> None:
    ata = _ata(sessao, cenario)
    item = _item(sessao, cenario, ata)
    acao = sessao.get(Action, item.id)
    assert acao is not None
    nova_data = REFERENCIA + timedelta(days=20)

    minutes_service.replan_item(
        sessao,
        user=cenario.gil,
        ref=minutes_service.ItemRef(ata.id, item.id),
        request=ReplanRequest(
            action_id=item.id,
            new_date=nova_data,
            justification="Aguardando a liberação do fornecedor.",
            version=acao.version,
        ),
        reference_date=REFERENCIA,
    )

    atualizado = minutes_service.find_item(
        sessao, user=cenario.gil, minutes_id=ata.id, item_id=item.id, reference_date=REFERENCIA
    )
    assert atualizado is not None
    assert atualizado.replanned_date == nova_data
    assert atualizado.has_replans
    replans = minutes_service.item_justifications(
        sessao, user=cenario.gil, minutes_id=ata.id, item_id=item.id
    )
    assert len(replans) == 1
    assert replans[0].author_name == "Gil Gestor"
    assert replans[0].registered_on == REFERENCIA
    assert replans[0].justification == "Aguardando a liberação do fornecedor."


# ── Validação ────────────────────────────────────────────────────────────────────────────────


def test_a_acao_exige_data_prevista(sessao: Session, cenario: Cenario) -> None:
    ata = _ata(sessao, cenario)

    with pytest.raises(InvalidDataError) as recusa:
        _item(sessao, cenario, ata, planned_date=None)

    assert "prevista" in str(recusa.value)


def test_o_responsavel_precisa_estar_na_lista_de_presenca(
    sessao: Session, cenario: Cenario
) -> None:
    ata = _ata(sessao, cenario)

    with pytest.raises(InvalidDataError) as recusa:
        _item(sessao, cenario, ata, responsible_id=cenario.vera.person_id)

    assert "presença" in str(recusa.value)


# ── Rotas ────────────────────────────────────────────────────────────────────────────────────


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
        "X-Alpine-Target": "ata-ficha",
        "Cookie": f"{DEMO_COOKIE}={usuario.id}",
    }
    if corpo is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    return func.HttpRequest(
        method=metodo,
        url="/api/central-acoes/ata",
        headers=headers,
        params=dict(params or {}),
        route_params=dict(rota or {}),
        body=urlencode(corpo).encode() if corpo is not None else b"",
    )


def test_a_ficha_mostra_a_aba_de_itens_e_o_formulario(sessao: Session, cenario: Cenario) -> None:
    ata = _ata(sessao, cenario)
    item = _item(sessao, cenario, ata)

    ficha = minutes_routes.minutes_sheet(
        _requisicao(cenario.gil, params={"id": str(ata.id), "aba": "itens"})
    )
    formulario = minutes_routes.item_new_form(
        _requisicao(cenario.gil, params={"id": str(ata.id), "aba": "itens"})
    )

    corpo = ficha.get_body().decode()
    assert ficha.status_code == 200
    assert "Anotações e Ações" in corpo
    assert item.item in corpo and item.subject in corpo
    assert formulario.status_code == 200
    assert 'name="grupo"' in formulario.get_body().decode()


def test_a_rota_do_item_salva_e_devolve_a_ficha(sessao: Session, cenario: Cenario) -> None:
    ata = _ata(sessao, cenario)

    resposta = minutes_routes.item_save(
        _requisicao(
            cenario.gil,
            metodo="POST",
            corpo={
                "id": str(ata.id),
                "aba": "itens",
                "tipo": ACTION,
                "grupo": "Riscos",
                "assunto": "Protocolar o monitoramento",
                "descricao": "Condicionante da licença de operação.",
                "solicitante": str(cenario.gil.person_id),
                "responsavel": str(cenario.mario.person_id),
                "prevista": (REFERENCIA + timedelta(days=10)).isoformat(),
                "conclusao": "",
                "versao": str(ata.version),
            },
        )
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "Item salvo." in unquote(resposta.headers.get("X-TN-Toast", ""))
    assert "1.1" in corpo
