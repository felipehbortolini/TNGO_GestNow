"""Rotas das Lições aprendidas (ISSUE-027): o acervo, o 422 do formulário e os 403 da validação.

O handler é chamado com a requisição de Alpine e o e-mail de quem está logado; a sessão do teste
serve a rota (fixture ``sessao``).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.modulos.configuracoes.models import Discipline
from src.modulos.governanca import lessons_routes as routes
from src.modulos.governanca import lessons_service
from tests.governanca import apoio
from tests.identidades import requisicao

DISCIPLINA = "Civil"


def _cenario(sessao: Session):
    sessao.add(Discipline(name=DISCIPLINA))
    projeto = apoio.projeto_com_orcamento(sessao)
    return (
        projeto,
        apoio.colaborador(sessao, apoio.MEMBRO),
        apoio.colaborador(sessao, apoio.GESTOR, "Gestor"),
    )


def _form(**mudancas: str) -> dict[str, str]:
    campos = {
        "titulo": "Sondagem antes da fundação",
        "tipo": "A evitar",
        "fase": "Engenharia",
        "area": "Riscos",
        "disciplina": DISCIPLINA,
        "origem": "Registro direto",
        "aconteceu": "A fundação encontrou interferência não mapeada e atrasou a obra.",
        "causa": "Cadastro de interferências incompleto.",
        "impacto_prazo_dias": "5",
        "impacto_custo": "1.000,00",
        "recomendacao": "Exigir sondagem e varredura antes de liberar a fundação.",
        "palavras_chave": "sondagem, fundação",
        "aplicabilidade": "Projeto",
    }
    campos.update(mudancas)
    return campos


def test_o_acervo_mostra_a_licao_do_projeto(sessao: Session) -> None:
    projeto, membro, _ = _cenario(sessao)
    usuario = apoio.usuario_de(membro)
    criada = lessons_service.create_lesson(
        sessao,
        user=usuario,
        scope=apoio.escopo_do_projeto(projeto),
        form=_form(),
        reference_date=apoio.HOJE,
    )

    resposta = routes.lesson_acervo(
        requisicao(
            "/api/governanca/licoes", email=apoio.MEMBRO, params={"projeto": str(projeto.id)}
        )
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert criada.code in corpo
    assert "Sondagem antes da fundação" in corpo


def test_o_formulario_com_erro_volta_422_com_a_mensagem(sessao: Session) -> None:
    projeto, _, _ = _cenario(sessao)

    resposta = routes.lesson_register(
        requisicao(
            "/api/governanca/licoes",
            metodo="POST",
            email=apoio.MEMBRO,
            params={"projeto": str(projeto.id)},
            corpo=_form(titulo=""),
        )
    )

    assert resposta.status_code == 422
    assert "Título é obrigatório." in resposta.get_body().decode()


def test_o_visualizador_nao_cria_licao(sessao: Session) -> None:
    projeto, _, _ = _cenario(sessao)
    apoio.colaborador(sessao, apoio.VISUALIZADOR, "Visualizador")

    resposta = routes.lesson_register(
        requisicao(
            "/api/governanca/licoes",
            metodo="POST",
            email=apoio.VISUALIZADOR,
            params={"projeto": str(projeto.id)},
            corpo=_form(),
        )
    )

    assert resposta.status_code == 403


def test_o_autor_gestor_nao_valida_a_propria_licao(sessao: Session) -> None:
    projeto, _, gestor = _cenario(sessao)
    usuario = apoio.usuario_de(gestor, nome="Gabriel Gestor")
    criada = lessons_service.create_lesson(
        sessao,
        user=usuario,
        scope=apoio.escopo_do_projeto(projeto),
        form=_form(),
        reference_date=apoio.HOJE,
    )
    lessons_service.send_for_validation(sessao, user=usuario, code=criada.code, version=None)

    resposta = routes.lesson_validate(
        requisicao(
            "/api/governanca/licoes/validar",
            metodo="POST",
            email=apoio.GESTOR,
            corpo={"codigo": criada.code, "resultado": "Validada", "aplicabilidade": "Projeto"},
        )
    )

    assert resposta.status_code == 403
