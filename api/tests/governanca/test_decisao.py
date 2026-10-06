"""Fachada da decisão e do encerramento da SM (ISSUE-025): quórum, ações, atomicidade e lição.

A decisão exige Gestor, confere o decisor (o gerente do projeto ou o quórum do Comitê) e, na
aprovação, cria as ações de implementação na Central (origem Mudança) na mesma transação. A
reapresentação devolve a adiada à pauta; o encerramento exige as confirmações do impacto e cria a
lição opcional em Rascunho.
"""

from __future__ import annotations

from datetime import date, timedelta
from urllib.parse import unquote, urlencode

import azure.functions as func
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.auth import PRINCIPAL_HEADER
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.scope import Scope
from src.modulos.central_acoes import service as central_acoes
from src.modulos.central_acoes.calculations import StatusFilter
from src.modulos.central_acoes.validation import ActionFilters
from src.modulos.governanca import calculations, lessons_models, models, routes, service
from tests.governanca import apoio
from tests.governanca.apoio import HOJE
from tests.identidades import cabecalho_do_principal


def _cenario(session: Session):
    projeto = apoio.projeto_com_orcamento(session)
    membro = apoio.colaborador(session, apoio.MEMBRO)
    gestor = apoio.colaborador(session, apoio.GESTOR, "Gestor")
    return projeto, apoio.usuario_de(membro), apoio.usuario_de(gestor, nome="Gabriel Gestor")


def _analise_valida(mudanca: models.ChangeRequest, **campos: str) -> dict[str, str]:
    base = {
        "custo": "1.000,00",
        "prazo_dias": "5",
        "marco_contratual": "nao",
        "escopo": "Inclui o novo pacote de tratamento.",
        "qualidade": "Sem impacto",
        "riscos": "Sem impacto",
        "sms": "Sem impacto",
        "contrato": "Sem impacto",
        "alcada": "Gerente do projeto",
        "fonte_recurso": "Aditivo de orçamento",
        "itens_eac": "",
        "versao": str(mudanca.version),
    }
    base.update(campos)
    return base


def _aguardando(
    session: Session, usuario, projeto, *, emergencia: bool = False, **impacto: str
) -> models.ChangeRequest:
    """Uma SM na pauta: registrada, analisada e Aguardando comitê."""
    campos = {}
    if emergencia:
        campos = {
            "data_solicitacao": "2026-09-20",
            "prioridade": "Emergencial",
            "execucao_antecipada": "sim",
            "inicio_emergencia": "2026-09-20",
            "justificativa_emergencia": "Parada de produção exige a mudança imediata.",
        }
    criada = apoio.registrar(session, usuario, projeto, **campos)
    mudanca = session.get(models.ChangeRequest, criada.id)
    assert mudanca is not None
    service.start_analysis(
        session,
        user=usuario,
        code=mudanca.code,
        form={
            "responsavel_id": str(usuario.person_id),
            "prazo": "2026-10-16",
            "versao": str(mudanca.version),
        },
        reference_date=HOJE,
    )
    mudanca = session.get(models.ChangeRequest, criada.id)
    assert mudanca is not None
    service.conclude_analysis(
        session,
        user=usuario,
        code=mudanca.code,
        form=_analise_valida(mudanca, **impacto),
        reference_date=HOJE,
    )
    atual = session.get(models.ChangeRequest, criada.id)
    assert atual is not None
    assert atual.situation == models.SITUATION_AWAITING
    return atual


def _decisao(mudanca: models.ChangeRequest, **campos: object) -> dict[str, object]:
    base: dict[str, object] = {
        "resultado": "Aprovada",
        "data": HOJE.isoformat(),
        "participantes": [],
        "justificativa": "Aprovada com base na análise de impacto.",
        "condicoes": "",
        "reapresentar_em": "",
        "ata_id": "",
        "acoes": [],
        "prevista": (HOJE + timedelta(days=15)).isoformat(),
        "versao": str(mudanca.version),
    }
    base.update(campos)
    return base


def _ficha(session: Session, usuario, mudanca: models.ChangeRequest) -> service.ChangeSheet:
    ficha = service.find_change_sheet(session, user=usuario, code=mudanca.code, reference_date=HOJE)
    assert ficha is not None
    return ficha


def _acoes_da_mudanca(session: Session, usuario, mudanca: models.ChangeRequest):
    listing = central_acoes.list_actions(
        session,
        user=usuario,
        scope=Scope(project_id=mudanca.project_id, source="url"),
        filters=ActionFilters(origin="Mudança", status=StatusFilter.ALL),
        reference_date=HOJE,
    )
    return [line for line in listing.rows if line.record.origin_ref == mudanca.code]


# ── Quórum e decisor ────────────────────────────────────────────────────────────────────────


def test_decisao_do_comite_sem_quorum_e_recusada(sessao: Session) -> None:
    projeto, membro, gestor = _cenario(sessao)
    mudanca = _aguardando(sessao, membro, projeto, alcada="Comitê")
    assert mudanca.authority == "Comitê"

    with pytest.raises(InvalidDataError) as recusa:
        service.decide_change(
            sessao,
            user=gestor,
            code=mudanca.code,
            form=_decisao(mudanca, participantes=[str(projeto.manager_id), str(membro.person_id)]),
            reference_date=HOJE,
        )

    assert "quórum" in str(recusa.value)


def test_decisao_do_gerente_exige_o_gerente_do_projeto(sessao: Session) -> None:
    projeto, membro, gestor = _cenario(sessao)
    mudanca = _aguardando(sessao, membro, projeto)

    with pytest.raises(InvalidDataError) as recusa:
        service.decide_change(
            sessao,
            user=gestor,
            code=mudanca.code,
            form=_decisao(mudanca, participantes=[str(membro.person_id)]),
            reference_date=HOJE,
        )

    assert "precisa constar como decisor" in str(recusa.value)


def test_membro_nao_decide(sessao: Session) -> None:
    projeto, membro, _ = _cenario(sessao)
    mudanca = _aguardando(sessao, membro, projeto)

    with pytest.raises(AccessDeniedError):
        service.decide_change(
            sessao,
            user=membro,
            code=mudanca.code,
            form=_decisao(mudanca, participantes=[str(projeto.manager_id)]),
            reference_date=HOJE,
        )


# ── Aprovação e ações de implementação ──────────────────────────────────────────────────────


def test_aprovacao_cria_as_acoes_de_implementacao_na_central(sessao: Session) -> None:
    projeto, membro, gestor = _cenario(sessao)
    mudanca = _aguardando(sessao, membro, projeto, riscos="Novo risco de atraso na montagem.")

    resultado = service.decide_change(
        sessao,
        user=gestor,
        code=mudanca.code,
        form=_decisao(
            mudanca,
            participantes=[str(projeto.manager_id)],
            acoes=["eac", "cronograma", "riscos"],
        ),
        reference_date=HOJE,
    )

    assert resultado.actions_created == 3
    assert mudanca.situation == models.SITUATION_IMPLEMENTING
    acoes = _acoes_da_mudanca(sessao, gestor, mudanca)
    assert [acao.record.item for acao in acoes] == ["1", "2", "3"]
    assert all(acao.record.group == "Implementação" for acao in acoes)
    assert all(acao.record.origin == "Mudança" for acao in acoes)
    assert all(acao.link.url == f"/governanca/mudanca?codigo={mudanca.code}" for acao in acoes)
    ficha = _ficha(sessao, gestor, mudanca)
    assert ficha.decision is not None
    assert len(ficha.decision.participants) == 1
    assert ficha.decision.decision.result == "Aprovada"


def test_a_falha_depois_das_acoes_desfaz_a_decisao_e_as_acoes(
    sessao: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    projeto, membro, gestor = _cenario(sessao)
    mudanca = _aguardando(sessao, membro, projeto)
    chamadas = {"total": 0}
    original = service.central_acoes.create_action

    def falha_na_segunda(*args: object, **kwargs: object):
        chamadas["total"] += 1
        if chamadas["total"] == 2:
            message = "falha provocada no meio da aprovação"
            raise RuntimeError(message)
        return original(*args, **kwargs)

    monkeypatch.setattr(service.central_acoes, "create_action", falha_na_segunda)
    with pytest.raises(RuntimeError), sessao.begin_nested():
        service.decide_change(
            sessao,
            user=gestor,
            code=mudanca.code,
            form=_decisao(
                mudanca,
                participantes=[str(projeto.manager_id)],
                acoes=["eac", "cronograma"],
            ),
            reference_date=HOJE,
        )

    assert mudanca.situation == models.SITUATION_AWAITING
    assert sessao.scalars(select(models.ChangeDecision)).all() == []
    assert _acoes_da_mudanca(sessao, gestor, mudanca) == []


# ── Adiada e reapresentação ─────────────────────────────────────────────────────────────────


def test_adiada_volta_a_pauta_por_reapresentar(sessao: Session) -> None:
    projeto, membro, gestor = _cenario(sessao)
    mudanca = _aguardando(sessao, membro, projeto)

    service.decide_change(
        sessao,
        user=gestor,
        code=mudanca.code,
        form=_decisao(
            mudanca,
            resultado="Adiada",
            participantes=[str(projeto.manager_id)],
            reapresentar_em=(HOJE + timedelta(days=7)).isoformat(),
        ),
        reference_date=HOJE,
    )
    assert mudanca.situation == models.SITUATION_POSTPONED
    ficha = _ficha(sessao, gestor, mudanca)
    assert ficha.decision is not None
    assert ficha.decision.decision.reappear_on == HOJE + timedelta(days=7)

    service.resubmit_change(sessao, user=membro, code=mudanca.code, reference_date=HOJE)

    assert mudanca.situation == models.SITUATION_AWAITING
    ficha = _ficha(sessao, gestor, mudanca)
    assert ficha.decision is not None
    assert ficha.decision.decision.result == "Adiada"


# ── Emergencial ─────────────────────────────────────────────────────────────────────────────


def test_emergencial_com_ratificacao_vencida(sessao: Session) -> None:
    projeto, membro, _ = _cenario(sessao)
    mudanca = _aguardando(sessao, membro, projeto, emergencia=True)

    ficha = _ficha(sessao, membro, mudanca)

    assert ficha.emergency_start == date(2026, 9, 20)
    assert ficha.ratification_due == date(2026, 9, 27)
    assert calculations.is_emergency_pending(
        emergency=True, has_decision=False, situation=mudanca.situation
    )
    assert calculations.is_ratification_overdue(
        pending=True, due_date=ficha.ratification_due, reference_date=HOJE
    )


# ── Encerramento ────────────────────────────────────────────────────────────────────────────


def _encerrar(mudanca: models.ChangeRequest, **campos: str) -> dict[str, str]:
    base = {
        "data": HOJE.isoformat(),
        "observacao": "Linhas de base conferidas.",
        "versao": str(mudanca.version),
    }
    base.update(campos)
    return base


def test_encerramento_com_acao_aberta_e_recusado(sessao: Session) -> None:
    projeto, membro, gestor = _cenario(sessao)
    mudanca = _aguardando(sessao, membro, projeto, riscos="Novo risco de atraso na montagem.")
    service.decide_change(
        sessao,
        user=gestor,
        code=mudanca.code,
        form=_decisao(
            mudanca,
            participantes=[str(projeto.manager_id)],
            acoes=["eac", "cronograma"],
        ),
        reference_date=HOJE,
    )
    mudanca = sessao.get(models.ChangeRequest, mudanca.id)
    assert mudanca is not None

    with pytest.raises(InvalidDataError) as recusa:
        service.close_change(
            sessao,
            user=gestor,
            code=mudanca.code,
            form=_encerrar(mudanca, cronograma="sim", contrato="sim", riscos="sim"),
            reference_date=HOJE,
        )

    assert "em aberto" in str(recusa.value)


def test_encerramento_exige_as_confirmacoes_do_impacto(sessao: Session) -> None:
    projeto, membro, gestor = _cenario(sessao)
    mudanca = _aguardando(sessao, membro, projeto, custo="0", prazo_dias="5")
    service.decide_change(
        sessao,
        user=gestor,
        code=mudanca.code,
        form=_decisao(mudanca, participantes=[str(projeto.manager_id)]),
        reference_date=HOJE,
    )
    mudanca = sessao.get(models.ChangeRequest, mudanca.id)
    assert mudanca is not None

    with pytest.raises(InvalidDataError) as recusa:
        service.close_change(
            sessao,
            user=gestor,
            code=mudanca.code,
            form=_encerrar(mudanca),
            reference_date=HOJE,
        )

    assert "cronograma" in str(recusa.value)


def test_encerramento_cria_a_licao_em_rascunho(sessao: Session) -> None:
    projeto, membro, gestor = _cenario(sessao)
    mudanca = _aguardando(sessao, membro, projeto, custo="0", prazo_dias="0", riscos="Sem impacto")
    service.decide_change(
        sessao,
        user=gestor,
        code=mudanca.code,
        form=_decisao(mudanca, participantes=[str(projeto.manager_id)]),
        reference_date=HOJE,
    )
    mudanca = sessao.get(models.ChangeRequest, mudanca.id)
    assert mudanca is not None

    resultado = service.close_change(
        sessao,
        user=gestor,
        code=mudanca.code,
        form=_encerrar(
            mudanca,
            registrar_licao="sim",
            licao_titulo="Inclusão do pacote de tratamento",
            licao_tipo="A repetir",
            licao_fase="Engenharia",
            licao_disciplina="Civil",
            licao_recomendacao="Manter a análise de impacto antes de aprovar o pacote.",
        ),
        reference_date=HOJE,
    )

    assert mudanca.situation == models.SITUATION_CLOSED
    assert mudanca.closed_by_id == gestor.person_id
    assert mudanca.closing_date == HOJE
    assert resultado.lesson_code is not None
    licao = sessao.get(lessons_models.Lesson, mudanca.lesson_id)
    assert licao is not None
    assert licao.situation == lessons_models.SITUATION_DRAFT
    assert licao.origin == lessons_models.ORIGIN_CHANGE
    assert licao.origin_ref == mudanca.code
    assert licao.area == "Escopo"


# ── Rotas ────────────────────────────────────────────────────────────────────────────────────


def _requisicao(email: str, corpo: list[tuple[str, str]]) -> func.HttpRequest:
    headers = {
        "X-Alpine-Request": "true",
        "X-Alpine-Target": "mudanca-ficha",
        "Content-Type": "application/x-www-form-urlencoded",
        PRINCIPAL_HEADER: cabecalho_do_principal(email),
    }
    return func.HttpRequest(
        method="POST",
        url="/api/governanca/mudanca/decisao",
        headers=headers,
        params={},
        route_params={},
        body=urlencode(corpo).encode(),
    )


def _corpo_da_decisao(mudanca: models.ChangeRequest, gestor, projeto) -> list[tuple[str, str]]:
    return [
        ("codigo", mudanca.code),
        ("resultado", "Aprovada"),
        ("data", HOJE.isoformat()),
        ("participantes", str(projeto.manager_id)),
        ("participantes", str(gestor.person_id)),
        ("justificativa", "Aprovada com base na análise de impacto."),
        ("versao", str(mudanca.version)),
        ("prevista", (HOJE + timedelta(days=15)).isoformat()),
    ]


def test_a_rota_da_decisao_do_membro_e_403(sessao: Session) -> None:
    projeto, membro, gestor = _cenario(sessao)
    mudanca = _aguardando(sessao, membro, projeto)

    resposta = routes.decide_change_request(
        _requisicao(apoio.MEMBRO, _corpo_da_decisao(mudanca, gestor, projeto))
    )

    assert resposta.status_code == 403
    assert mudanca.situation == models.SITUATION_AWAITING


def test_a_rota_da_decisao_do_gestor_devolve_a_ficha(sessao: Session) -> None:
    projeto, membro, gestor = _cenario(sessao)
    mudanca = _aguardando(sessao, membro, projeto, riscos="Novo risco de atraso na montagem.")
    corpo = [*_corpo_da_decisao(mudanca, gestor, projeto), ("acoes", "riscos")]

    resposta = routes.decide_change_request(_requisicao(apoio.GESTOR, corpo))

    corpo_resposta = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "Decisão registrada." in unquote(resposta.headers.get("X-TN-Toast", ""))
    assert "Em implementação" in corpo_resposta
    assert _acoes_da_mudanca(sessao, gestor, mudanca) != []
