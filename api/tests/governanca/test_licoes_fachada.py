"""Fachada das Lições aprendidas (ISSUE-027, HU-129): fluxo, segregação, origem e aplicação.

O fluxo é Rascunho → Em validação → Validada/Publicada, com a devolução voltando a Rascunho com
comentário no histórico; o validador é Gestor e não pode ser o autor (D7); a origem de módulo
confere o número pela fachada do dono; aplicar em projeto registra o reuso e cria a ação na
Central. O rascunho com origem (`create_draft_lesson`) é o que os outros módulos chamam.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.errors import AccessDeniedError, InvalidDataError
from src.modulos.central_acoes.models import Action
from src.modulos.configuracoes.models import Discipline, Person
from src.modulos.governanca import lessons_models as lm
from src.modulos.governanca import lessons_service
from src.modulos.governanca.lessons_models import Lesson, LessonApplication
from src.modulos.governanca.lessons_service import LessonFilter
from src.modulos.governanca.lessons_validation import DraftInput
from tests.governanca.apoio import (
    GESTOR,
    HOJE,
    MEMBRO,
    PORTFOLIO,
    colaborador,
    escopo_do_projeto,
    projeto_com_orcamento,
    registrar,
    usuario_de,
)

DISCIPLINA = "Civil"
TITULO = "Sondagem antes da fundação"
ACONTECEU = "A fundação encontrou interferência não mapeada e atrasou a obra."
CAUSA = "Cadastro de interferências incompleto."
RECOMENDACAO = "Exigir sondagem e varredura antes de liberar a fundação."
DEVOLUCAO = "Detalhe a causa raiz com as evidências da ocorrência."


def _cenario(session: Session):
    session.add(Discipline(name=DISCIPLINA))
    projeto = projeto_com_orcamento(session)
    outro = projeto_com_orcamento(session, codigo="TN-2026-021", padrao="CB-2026")
    membro = usuario_de(colaborador(session, MEMBRO), nome="Marina Membro")
    gestor = usuario_de(colaborador(session, GESTOR, "Gestor"), nome="Gabriel Gestor")
    return projeto, outro, membro, gestor


def _form(**mudancas: str) -> dict[str, str]:
    campos = {
        "titulo": TITULO,
        "tipo": "A evitar",
        "fase": "Engenharia",
        "area": "Riscos",
        "disciplina": DISCIPLINA,
        "origem": "Registro direto",
        "aconteceu": ACONTECEU,
        "causa": CAUSA,
        "impacto_prazo_dias": "5",
        "impacto_custo": "1.000,00",
        "recomendacao": RECOMENDACAO,
        "palavras_chave": "sondagem, fundação",
        "aplicabilidade": "Projeto",
    }
    campos.update(mudancas)
    return campos


def _criar(session: Session, projeto, usuario, **mudancas: str) -> lessons_service.CreatedLesson:
    return lessons_service.create_lesson(
        session,
        user=usuario,
        scope=escopo_do_projeto(projeto),
        form=_form(**mudancas),
        reference_date=HOJE,
    )


def _publicar(session: Session, membro, gestor, criada: lessons_service.CreatedLesson) -> None:
    lessons_service.send_for_validation(session, user=membro, code=criada.code, version=None)
    lessons_service.decide_validation(
        session,
        user=gestor,
        code=criada.code,
        form={"resultado": "Publicada", "aplicabilidade": "Corporativa"},
    )


# ── Fluxo e segregação ───────────────────────────────────────────────────────────────────────


def test_validador_igual_ao_autor_e_recusado_com_403(sessao: Session) -> None:
    projeto, _, _, gestor = _cenario(sessao)
    criada = _criar(sessao, projeto, gestor)
    lessons_service.send_for_validation(sessao, user=gestor, code=criada.code, version=None)

    with pytest.raises(AccessDeniedError) as recusa:
        lessons_service.decide_validation(
            sessao,
            user=gestor,
            code=criada.code,
            form={"resultado": "Validada", "aplicabilidade": "Projeto"},
        )

    assert "própria lição" in str(recusa.value)
    licao = sessao.scalars(select(Lesson).where(Lesson.code == criada.code)).one()
    assert licao.situation == lm.SITUATION_VALIDATING


def test_devolucao_volta_a_rascunho_com_o_comentario_no_historico(sessao: Session) -> None:
    projeto, _, membro, gestor = _cenario(sessao)
    criada = _criar(sessao, projeto, membro)
    lessons_service.send_for_validation(sessao, user=membro, code=criada.code, version=None)

    lessons_service.decide_validation(
        sessao,
        user=gestor,
        code=criada.code,
        form={"resultado": "Devolvida", "comentario": DEVOLUCAO},
    )

    licao = sessao.scalars(select(Lesson).where(Lesson.code == criada.code)).one()
    ficha = lessons_service.find_lesson_sheet(sessao, user=gestor, code=criada.code)
    assert licao.situation == lm.SITUATION_DRAFT
    assert ficha is not None
    assert any(DEVOLUCAO in linha.text for linha in ficha.history)
    assert ficha.return_note == DEVOLUCAO


def test_publicar_exige_gestor_e_licao_validada(sessao: Session) -> None:
    projeto, _, membro, gestor = _cenario(sessao)
    criada = _criar(sessao, projeto, membro)

    with pytest.raises(AccessDeniedError):
        lessons_service.publish_lesson(sessao, user=membro, code=criada.code, version=None)

    lessons_service.send_for_validation(sessao, user=membro, code=criada.code, version=None)
    lessons_service.decide_validation(
        sessao,
        user=gestor,
        code=criada.code,
        form={"resultado": "Validada", "aplicabilidade": "Corporativa"},
    )
    lessons_service.publish_lesson(sessao, user=gestor, code=criada.code, version=None)

    licao = sessao.scalars(select(Lesson).where(Lesson.code == criada.code)).one()
    assert licao.situation == lm.SITUATION_PUBLISHED


# ── Origem rastreável ────────────────────────────────────────────────────────────────────────


def test_origem_de_modulo_com_numero_inexistente_e_recusada_com_422(sessao: Session) -> None:
    projeto, _, membro, _ = _cenario(sessao)

    with pytest.raises(InvalidDataError) as recusa:
        _criar(sessao, projeto, membro, origem="Mudança", origem_ref="SM-TN-2026-9999")

    assert "não encontrado no módulo de origem" in str(recusa.value)


def test_origem_de_modulo_com_numero_existente_e_aceita(sessao: Session) -> None:
    projeto, _, membro, _ = _cenario(sessao)
    mudanca = registrar(sessao, membro, projeto)

    criada = _criar(sessao, projeto, membro, origem="Mudança", origem_ref=mudanca.code)

    licao = sessao.scalars(select(Lesson).where(Lesson.code == criada.code)).one()
    assert (licao.origin, licao.origin_ref) == ("Mudança", mudanca.code)


def test_rascunho_com_origem_e_o_que_os_outros_modulos_chamam(sessao: Session) -> None:
    projeto, _, membro, _ = _cenario(sessao)
    mudanca = registrar(sessao, membro, projeto)
    draft = DraftInput(
        title=TITULO,
        kind="A repetir",
        phase="Engenharia",
        area="Escopo",
        origin="Mudança",
        origin_ref=mudanca.code,
        what_happened=ACONTECEU,
        cause=CAUSA,
        recommendation=RECOMENDACAO,
        discipline=DISCIPLINA,
    )

    criada = lessons_service.create_draft_lesson(
        sessao, user=membro, project_id=projeto.id, draft=draft, reference_date=HOJE
    )

    licao = sessao.get(Lesson, criada.id)
    assert licao is not None
    assert (licao.situation, licao.origin, licao.origin_ref) == (
        lm.SITUATION_DRAFT,
        "Mudança",
        mudanca.code,
    )


def test_rascunho_com_origem_de_modulo_sem_numero_e_recusado(sessao: Session) -> None:
    projeto, _, membro, _ = _cenario(sessao)
    draft = DraftInput(
        title=TITULO,
        kind="A repetir",
        phase="Engenharia",
        area="Escopo",
        origin="Mudança",
        origin_ref=None,
        what_happened=ACONTECEU,
        cause=CAUSA,
        recommendation=RECOMENDACAO,
    )

    with pytest.raises(InvalidDataError) as recusa:
        lessons_service.create_draft_lesson(
            sessao, user=membro, project_id=projeto.id, draft=draft, reference_date=HOJE
        )

    assert "número do registro de origem" in str(recusa.value)


# ── Aplicação em projeto ─────────────────────────────────────────────────────────────────────


def test_aplicar_em_projeto_registra_o_reuso_e_cria_a_acao_na_central(sessao: Session) -> None:
    projeto, _, membro, gestor = _cenario(sessao)
    criada = _criar(sessao, projeto, membro)
    _publicar(sessao, membro, gestor, criada)
    responsavel = sessao.get(Person, membro.person_id)
    assert responsavel is not None

    lessons_service.apply_lesson(
        sessao,
        user=membro,
        code=criada.code,
        form={
            "projeto_id": str(projeto.id),
            "data": HOJE.isoformat(),
            "como": "Incluir a sondagem no plano de escavação da fundação.",
            "gerar": "acao",
            "responsavel_id": str(responsavel.id),
            "prevista": (HOJE + timedelta(days=10)).isoformat(),
        },
        reference_date=HOJE,
    )

    licao = sessao.scalars(select(Lesson).where(Lesson.code == criada.code)).one()
    aplicacao = sessao.scalars(
        select(LessonApplication).where(LessonApplication.lesson_id == licao.id)
    ).one()
    acao = sessao.get(Action, aplicacao.action_id)
    assert acao is not None
    assert (acao.origin, acao.origin_ref) == ("Lição", criada.code)
    assert acao.responsible_id == responsavel.id
    assert acao.planned_date == HOJE + timedelta(days=10)


# ── Visibilidade ─────────────────────────────────────────────────────────────────────────────


def test_licao_de_projeto_aparece_no_projeto_e_a_corporativa_em_todo_o_acervo(
    sessao: Session,
) -> None:
    projeto_a, projeto_b, membro, gestor = _cenario(sessao)
    do_projeto = _criar(sessao, projeto_a, membro, aplicabilidade="Projeto")
    corporativa = _criar(sessao, projeto_b, membro, aplicabilidade="Corporativa")
    _publicar(sessao, membro, gestor, corporativa)

    acervo_a = lessons_service.acervo(
        sessao, user=membro, scope=escopo_do_projeto(projeto_a), filters=LessonFilter()
    )
    acervo_b = lessons_service.acervo(
        sessao, user=membro, scope=escopo_do_projeto(projeto_b), filters=LessonFilter()
    )
    acervo_portfolio = lessons_service.acervo(
        sessao, user=membro, scope=PORTFOLIO, filters=LessonFilter()
    )

    codigos_a = {row.code for row in acervo_a.rows}
    codigos_b = {row.code for row in acervo_b.rows}
    codigos_portfolio = {row.code for row in acervo_portfolio.rows}
    assert do_projeto.code in codigos_a
    assert corporativa.code in codigos_a  # publicada por outro projeto, Corporativa
    assert do_projeto.code not in codigos_b  # a lição de projeto não sai do projeto dela
    assert corporativa.code in codigos_b
    assert {do_projeto.code, corporativa.code} <= codigos_portfolio
