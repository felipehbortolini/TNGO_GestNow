"""A lição aplicada cria o risco pela fachada da Riscos (ISSUE-067, D9).

"Aplicar em projeto" com "gerar risco" cria o risco Identificado (ameaça para "A evitar",
oportunidade para "A repetir"), com a categoria da RBS escolhida, o dono, o texto da lição e sem
avaliação; o id fica em ``licao_aplicacao.risco_id`` (a FK chega com a fatia). A lição também
aceita a origem "Risco encerrado" com o número conferido pela fachada da Riscos e os links de
origem resolvem para a ficha do risco.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import origin_links
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.models import Discipline
from src.modulos.governanca import lessons_service
from src.modulos.governanca.lessons_models import Lesson, LessonApplication
from src.modulos.riscos import ficha_service
from src.modulos.riscos import service as riscos
from src.modulos.riscos import validation as riscos_validation
from src.modulos.riscos.models import Risk, RiskAssessment, RiskCategory
from tests.governanca.apoio import (
    GESTOR,
    HOJE,
    MEMBRO,
    colaborador,
    escopo_do_projeto,
    projeto_com_orcamento,
    usuario_de,
)

DISCIPLINA = "Civil"
TITULO = "Sondagem antes da fundação"
ACONTECEU = "A fundação encontrou interferência não mapeada e atrasou a obra."
CAUSA = "Cadastro de interferências incompleto."
RECOMENDACAO = "Exigir sondagem e varredura antes de liberar a fundação."


def _cenario(session: Session):
    session.add(Discipline(name=DISCIPLINA))
    projeto = projeto_com_orcamento(session)
    membro = usuario_de(colaborador(session, MEMBRO), nome="Marina Membro")
    gestor = usuario_de(colaborador(session, GESTOR, "Gestor"), nome="Gabriel Gestor")
    configuracoes.seed_initial_parameters(session, author_id=membro.id, effective_from=HOJE)
    categoria = RiskCategory(group="Técnico", name="Prazo")
    session.add(categoria)
    session.flush()
    return projeto, membro, gestor, categoria


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


def _publicar(session: Session, membro, gestor, criada) -> None:
    lessons_service.send_for_validation(session, user=membro, code=criada.code, version=None)
    lessons_service.decide_validation(
        session,
        user=gestor,
        code=criada.code,
        form={"resultado": "Publicada", "aplicabilidade": "Corporativa"},
    )


def test_aplicar_com_risco_cria_o_risco_identificado_pela_fachada(sessao: Session) -> None:
    projeto, membro, gestor, categoria = _cenario(sessao)
    criada = lessons_service.create_lesson(
        sessao, user=membro, scope=escopo_do_projeto(projeto), form=_form(), reference_date=HOJE
    )
    _publicar(sessao, membro, gestor, criada)

    lessons_service.apply_lesson(
        sessao,
        user=membro,
        code=criada.code,
        form={
            "projeto_id": str(projeto.id),
            "data": HOJE.isoformat(),
            "como": "Revisar o plano de escavação com a sondagem da lição.",
            "gerar": "risco",
            "categoria": str(categoria.id),
            "dono_id": str(membro.person_id),
        },
        reference_date=HOJE,
    )

    licao = sessao.scalars(select(Lesson).where(Lesson.code == criada.code)).one()
    aplicacao = sessao.scalars(
        select(LessonApplication).where(LessonApplication.lesson_id == licao.id)
    ).one()
    assert aplicacao.risk_id is not None, "o reuso guarda o vínculo com o risco"

    risk = sessao.get(Risk, aplicacao.risk_id)
    assert risk is not None
    assert risk.situation == "Identificado"
    assert risk.nature == "Ameaça", "lição A evitar gera ameaça"
    assert (risk.origin_type, risk.origin) == ("Lições aprendidas", f"Lição {criada.code}")
    assert risk.title == TITULO
    assert risk.consequence == ACONTECEU
    assert risk.cause == CAUSA
    assert risk.description is not None and RECOMENDACAO in risk.description
    assert risk.owner_id == membro.person_id
    assert risk.schedule_impact_days == 5, "o impacto da lição entra no risco"
    assert risk.cost_impact_cents == 100_000
    assert (
        sessao.scalars(select(RiskAssessment).where(RiskAssessment.risk_id == risk.id)).all() == []
    ), "o risco da lição nasce sem avaliação"

    ficha_risco = ficha_service.find_risk_sheet(
        sessao, user=membro, code=risk.code, reference_date=HOJE
    )
    assert ficha_risco is not None
    assert ficha_risco.line.origin == f"Lição {criada.code}"

    sheet = lessons_service.find_lesson_sheet(sessao, user=membro, code=criada.code)
    assert sheet is not None
    assert sheet.applications[0].risk_code == risk.code, "a ficha da lição mostra o risco gerado"


def test_a_licao_aceita_a_origem_risco_encerrado(sessao: Session) -> None:
    projeto, membro, _, categoria = _cenario(sessao)
    result = riscos.save_risk(
        sessao,
        user=membro,
        data=riscos_validation.RiskInput(
            nature="Ameaça",
            category_id=categoria.id,
            cause="Atraso na liberação dos desenhos de detalhamento.",
            title="Atraso na liberação dos desenhos",
            consequence="A montagem mecânica atrasa e o comissionamento escorrega.",
            owner_id=membro.person_id,
            identified_on=HOJE,
            origin_type="Manual",
            project_id=projeto.id,
        ),
        reference_date=HOJE,
    )

    criada = lessons_service.create_lesson(
        sessao,
        user=membro,
        scope=escopo_do_projeto(projeto),
        form=_form(origem="Risco", origem_ref=result.code),
        reference_date=HOJE,
    )

    licao = sessao.scalars(select(Lesson).where(Lesson.code == criada.code)).one()
    assert (licao.origin, licao.origin_ref) == ("Risco", result.code)

    link = origin_links.resolve("Risco", result.code)
    assert link.has_link, "a origem Risco resolve para a ficha (registrada na 064/065)"
    assert f"/riscos/ficha?codigo={result.code}" in (link.url or "")

    ficha_risco = ficha_service.find_risk_sheet(
        sessao, user=membro, code=result.code, reference_date=HOJE
    )
    assert ficha_risco is not None
    assert ficha_risco.line.origin_type == "Manual"

    sheet = lessons_service.find_lesson_sheet(sessao, user=membro, code=criada.code)
    assert sheet is not None
    assert sheet.row.origin_url is not None
    assert result.code in sheet.row.origin_url
