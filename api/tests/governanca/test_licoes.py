"""Fachada e rotas das lições (ISSUE-027): segregação, fluxo, origem, aplicação, visibilidade, 403."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.errors import AccessDeniedError, InvalidDataError
from src.modulos.governanca import lessons_models as lm
from src.modulos.governanca import lessons_routes, lessons_service
from tests.governanca import apoio, apoio_licoes
from tests.governanca.apoio import HOJE
from tests.identidades import requisicao

OUTRO_GESTOR = "graça.gestora@example.invalid"


def _cenario(sessao: Session):
    projeto = apoio.projeto_com_orcamento(sessao)
    autor = apoio.usuario_de(apoio.colaborador(sessao, apoio.MEMBRO))
    gestor = apoio.usuario_de(apoio.colaborador(sessao, apoio.GESTOR, perfil="Gestor"))
    return projeto, autor, gestor


def _situacao(sessao: Session, codigo: str) -> str:
    return sessao.scalars(select(lm.Lesson).where(lm.Lesson.code == codigo)).one().situation


def _historico(sessao: Session, codigo: str) -> list[str]:
    licao = sessao.scalars(select(lm.Lesson).where(lm.Lesson.code == codigo)).one()
    notas = sessao.scalars(
        select(lm.LessonHistory).where(lm.LessonHistory.lesson_id == licao.id)
    ).all()
    return [nota.text for nota in notas]


def test_numero_da_licao_segue_o_padrao_do_projeto(sessao: Session) -> None:
    projeto, autor, _ = _cenario(sessao)
    criada = apoio_licoes.registrar_licao(sessao, autor, projeto)
    assert criada.code == "LA-TN-2026-0001"
    assert _situacao(sessao, criada.code) == lm.SITUATION_DRAFT


def test_validador_igual_ao_autor_e_recusado_com_403(sessao: Session) -> None:
    projeto, _, gestor = _cenario(sessao)
    criada = apoio_licoes.licao_em_validacao(sessao, gestor, projeto)
    with pytest.raises(AccessDeniedError) as erro:
        lessons_service.decide_validation(
            sessao, user=gestor, code=criada.code, form={"resultado": "Validada"}
        )
    assert lessons_service.SELF_VALIDATION_MESSAGE in str(erro.value)
    assert _situacao(sessao, criada.code) == lm.SITUATION_VALIDATING


def test_membro_nao_valida(sessao: Session) -> None:
    projeto, autor, _ = _cenario(sessao)
    criada = apoio_licoes.licao_em_validacao(sessao, autor, projeto)
    with pytest.raises(AccessDeniedError):
        lessons_service.decide_validation(
            sessao, user=autor, code=criada.code, form={"resultado": "Validada"}
        )


def test_devolucao_volta_a_rascunho_com_o_comentario_no_historico(sessao: Session) -> None:
    projeto, autor, gestor = _cenario(sessao)
    criada = apoio_licoes.licao_em_validacao(sessao, autor, projeto)
    lessons_service.decide_validation(
        sessao,
        user=gestor,
        code=criada.code,
        form={"resultado": "Devolvida", "comentario": "Detalhar a causa raiz da interferência."},
    )
    assert _situacao(sessao, criada.code) == lm.SITUATION_DRAFT
    assert any("Detalhar a causa raiz" in texto for texto in _historico(sessao, criada.code))


def test_devolucao_sem_comentario_de_10_caracteres_e_422(sessao: Session) -> None:
    projeto, autor, gestor = _cenario(sessao)
    criada = apoio_licoes.licao_em_validacao(sessao, autor, projeto)
    with pytest.raises(InvalidDataError):
        lessons_service.decide_validation(
            sessao,
            user=gestor,
            code=criada.code,
            form={"resultado": "Devolvida", "comentario": "curto"},
        )


def test_validar_e_publicar_leva_a_lição_ao_acervo(sessao: Session) -> None:
    projeto, autor, gestor = _cenario(sessao)
    criada = apoio_licoes.licao_em_validacao(sessao, autor, projeto)
    lessons_service.decide_validation(
        sessao,
        user=gestor,
        code=criada.code,
        form={"resultado": "Publicada", "aplicabilidade": "Corporativa"},
    )
    assert _situacao(sessao, criada.code) == lm.SITUATION_PUBLISHED


def test_origem_de_modulo_com_numero_inexistente_e_422(sessao: Session) -> None:
    projeto, autor, _ = _cenario(sessao)
    with pytest.raises(InvalidDataError) as erro:
        apoio_licoes.registrar_licao(
            sessao, autor, projeto, origem="Mudança", origem_ref="SM-TN-2026-0099"
        )
    assert "SM-TN-2026-0099" in " ".join(erro.value.messages())


def test_origem_de_modulo_sem_numero_e_422(sessao: Session) -> None:
    projeto, autor, _ = _cenario(sessao)
    with pytest.raises(InvalidDataError):
        apoio_licoes.registrar_licao(sessao, autor, projeto, origem="Mudança")


def test_origem_mudanca_existente_e_aceita_e_o_rascunho_da_fachada_nasce_em_rascunho(
    sessao: Session,
) -> None:
    projeto, autor, _ = _cenario(sessao)
    sm = apoio.registrar(sessao, autor, projeto)
    apoio_licoes.disciplina(sessao)
    criada = lessons_service.create_draft_lesson(
        sessao,
        user=autor,
        project_id=projeto.id,
        draft=lessons_service.validation.DraftInput(
            title="Mudança de escopo encerrada",
            kind="A repetir",
            phase="Encerramento",
            area="Escopo",
            origin="Mudança",
            origin_ref=sm.code,
            what_happened="Texto do que aconteceu na mudança.",
            cause="Mudança escopo de origem cliente.",
            recommendation="Registrar o que a mudança ensinou ao projeto.",
        ),
        reference_date=HOJE,
    )
    assert _situacao(sessao, criada.code) == lm.SITUATION_DRAFT
    assert any(sm.code in texto for texto in _historico(sessao, criada.code))


def test_aplicar_registra_o_reuso_e_cria_a_acao_com_link_de_volta(sessao: Session) -> None:
    projeto, autor, gestor = _cenario(sessao)
    criada = apoio_licoes.licao_em_validacao(sessao, autor, projeto)
    lessons_service.decide_validation(
        sessao, user=gestor, code=criada.code, form={"resultado": "Publicada"}
    )
    lessons_service.apply_lesson(
        sessao,
        user=gestor,
        code=criada.code,
        form={
            "projeto_id": str(projeto.id),
            "data": HOJE.isoformat(),
            "como": "Exigir georradar na liberação das fundações do projeto.",
            "gerar": "acao",
            "responsavel_id": str(autor.person_id),
            "prevista": HOJE.isoformat(),
        },
        reference_date=HOJE,
    )
    reusos = sessao.scalars(select(lm.LessonApplication)).all()
    assert len(reusos) == 1
    assert reusos[0].action_id is not None


def test_aplicar_lição_nao_publicada_e_recusado(sessao: Session) -> None:
    projeto, autor, _ = _cenario(sessao)
    criada = apoio_licoes.registrar_licao(sessao, autor, projeto)
    with pytest.raises(InvalidDataError):
        lessons_service.apply_lesson(
            sessao,
            user=autor,
            code=criada.code,
            form={
                "projeto_id": str(projeto.id),
                "data": HOJE.isoformat(),
                "como": "Exigir georradar na liberação das fundações.",
            },
            reference_date=HOJE,
        )


def test_licao_de_projeto_nao_aparece_no_acervo_de_outro_projeto_e_a_corporativa_sim(
    sessao: Session,
) -> None:
    projeto, autor, gestor = _cenario(sessao)
    outro = apoio.projeto_com_orcamento(sessao, codigo="TN-2026-021")
    corporativa = apoio_licoes.licao_em_validacao(sessao, autor, projeto)
    lessons_service.decide_validation(
        sessao, user=gestor, code=corporativa.code, form={"resultado": "Publicada"}
    )
    local = apoio_licoes.licao_em_validacao(
        sessao, autor, projeto, titulo="Lição só deste projeto, publicada", aplicabilidade="Projeto"
    )
    lessons_service.decide_validation(
        sessao, user=gestor, code=local.code, form={"resultado": "Publicada"}
    )
    visao = lessons_service.acervo(
        sessao,
        user=gestor,
        scope=apoio.escopo_do_projeto(outro),
        filters=lessons_service.LessonFilter(),
    )
    assert [linha.code for linha in visao.rows] == [corporativa.code]
    portfolio = lessons_service.acervo(
        sessao, user=gestor, scope=apoio.PORTFOLIO, filters=lessons_service.LessonFilter()
    )
    assert len(portfolio.rows) == 2


def test_rota_de_validacao_do_proprio_autor_devolve_403(sessao: Session) -> None:
    projeto, _, gestor = _cenario(sessao)
    criada = apoio_licoes.licao_em_validacao(sessao, gestor, projeto)
    resposta = lessons_routes.lesson_validate(
        requisicao(
            "/api/governanca/licoes/validar",
            metodo="POST",
            email=apoio.GESTOR,
            params={"projeto": str(projeto.id)},
            corpo={"codigo": criada.code, "resultado": "Validada"},
        )
    )
    assert resposta.status_code == 403
    assert lessons_service.SELF_VALIDATION_MESSAGE in resposta.get_body().decode()


def test_rota_de_nova_licao_do_visualizador_e_403(sessao: Session) -> None:
    projeto, _, _ = _cenario(sessao)
    apoio.colaborador(sessao, apoio.VISUALIZADOR, perfil="Visualizador")
    resposta = lessons_routes.lesson_register(
        requisicao(
            "/api/governanca/licoes",
            metodo="POST",
            email=apoio.VISUALIZADOR,
            params={"projeto": str(projeto.id)},
            corpo=apoio_licoes.licao_valida(),
        )
    )
    assert resposta.status_code == 403
