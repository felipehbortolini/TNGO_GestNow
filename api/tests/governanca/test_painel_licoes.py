"""Painel de lições (ISSUE-028): dias sem registro, taxa de reuso, contagens e projetos sem registro.

As fórmulas são puras (``lessons_calculations``) e a fachada só as alimenta com as lições do escopo;
a janela do alerta é o parâmetro do projeto (90 dias), com a fronteira do protótipo.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from src.modulos.configuracoes.models import Discipline
from src.modulos.governanca import lessons_calculations as calc
from src.modulos.governanca import lessons_routes, lessons_service
from tests.governanca.apoio import (
    GESTOR,
    HOJE,
    MEMBRO,
    PORTFOLIO,
    colaborador,
    escopo_do_projeto,
    projeto_com_orcamento,
    usuario_de,
)
from tests.identidades import requisicao

DISCIPLINA = "Civil"
RECOMENDACAO = "Exigir sondagem e varredura antes de liberar a fundação."


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
        "recomendacao": RECOMENDACAO,
        "palavras_chave": "sondagem, fundação",
        "aplicabilidade": "Projeto",
    }
    campos.update(mudancas)
    return campos


def _cenario(sessao: Session):
    sessao.add(Discipline(name=DISCIPLINA))
    projeto = projeto_com_orcamento(sessao)
    membro = usuario_de(colaborador(sessao, MEMBRO), nome="Marina Membro")
    gestor = usuario_de(colaborador(sessao, GESTOR, "Gestor"), nome="Gabriel Gestor")
    return projeto, membro, gestor


def _criar(sessao: Session, projeto, usuario, **mudancas: str):
    return lessons_service.create_lesson(
        sessao,
        user=usuario,
        scope=escopo_do_projeto(projeto),
        form=_form(**mudancas),
        reference_date=HOJE,
    )


def _publicar(sessao: Session, membro, gestor, criada) -> None:
    lessons_service.send_for_validation(sessao, user=membro, code=criada.code, version=None)
    lessons_service.decide_validation(
        sessao,
        user=gestor,
        code=criada.code,
        form={"resultado": "Publicada", "aplicabilidade": "Corporativa"},
    )


# ── Fórmulas ────────────────────────────────────────────────────────────────────────────────


def test_dias_desde_a_ultima_licao_e_o_alerta_no_limite() -> None:
    assert calc.days_since_last(None, HOJE) is None
    assert calc.days_since_last(HOJE - timedelta(days=5), HOJE) == 5

    assert calc.is_registration_alert(None, HOJE, 90), "sem lição é alerta"
    assert not calc.is_registration_alert(HOJE - timedelta(days=90), HOJE, 90), (
        "no limite ainda não é alerta"
    )
    assert calc.is_registration_alert(HOJE - timedelta(days=91), HOJE, 90), "um dia além é alerta"


def test_taxa_de_reuso() -> None:
    assert calc.reuse_rate(published=4, reused=3) == Decimal("75.0")
    assert calc.reuse_rate(published=4, reused=0) == Decimal("0.0")
    assert calc.reuse_rate(published=0, reused=0) is None


def test_fases_ficam_zeradas_e_areas_ordenam_pelo_total() -> None:
    facts = [
        ("Engenharia", "A evitar", "Rascunho"),
        ("Engenharia", "A repetir", "Publicada"),
        ("Suprimentos", "A repetir", "Publicada"),
        ("Riscos", "A repetir", "Publicada"),
    ]

    fases = calc.lines_by_phase(facts)
    assert [
        (line.label, line.total, line.to_repeat, line.to_avoid, line.published) for line in fases
    ] == [
        ("Iniciação", 0, 0, 0, 0),
        ("Engenharia", 2, 1, 1, 1),
        ("Suprimentos", 1, 1, 0, 1),
        ("Construção", 0, 0, 0, 0),
        ("Comissionamento", 0, 0, 0, 0),
        ("Encerramento", 0, 0, 0, 0),
    ]

    areas = calc.lines_by_area(
        [
            ("Riscos", "A repetir", "Publicada"),
            ("Riscos", "A evitar", "Publicada"),
            ("Cronograma", "A evitar", "Rascunho"),
            ("Cronograma", "A repetir", "Publicada"),
            ("Custos", "A repetir", "Publicada"),
            ("Custos", "A repetir", "Publicada"),
            ("Custos", "A repetir", "Publicada"),
        ]
    )
    assert [(line.label, line.total) for line in areas] == [
        ("Custos", 3),
        ("Cronograma", 2),
        ("Riscos", 2),
    ]


def test_projetos_sem_registro_na_janela() -> None:
    records = {
        1: HOJE - timedelta(days=90),
        2: HOJE - timedelta(days=91),
        3: None,
    }

    assert calc.projects_without_record(
        records=records, project_ids=[1, 2, 3], reference_date=HOJE, alert_days=90
    ) == (2, 3)


# ── Fachada ─────────────────────────────────────────────────────────────────────────────────


def test_o_painel_do_projeto_conta_o_acervo(sessao: Session) -> None:
    projeto, membro, gestor = _cenario(sessao)
    _criar(sessao, projeto, membro)
    publicada = _criar(sessao, projeto, membro, tipo="A repetir")
    _publicar(sessao, membro, gestor, publicada)
    lessons_service.apply_lesson(
        sessao,
        user=membro,
        code=publicada.code,
        form={
            "projeto_id": str(projeto.id),
            "data": HOJE.isoformat(),
            "como": "Incluir a sondagem no plano de escavação da fundação.",
            "gerar": "nada",
        },
        reference_date=HOJE,
    )

    painel = lessons_service.lesson_panel(
        sessao, user=membro, scope=escopo_do_projeto(projeto), reference_date=HOJE
    )

    assert painel.total == 2
    assert painel.published == 1
    assert painel.in_flow == 1
    assert painel.validating == 0
    assert painel.to_repeat == 1 and painel.to_avoid == 1
    assert painel.reuses == 1
    assert painel.reuse_rate == Decimal("100.0")
    assert painel.last_lesson == HOJE
    assert painel.days_without_record == 0
    assert not painel.registration_alert
    assert [item.code for item in painel.most_reused] == [publicada.code]
    assert painel.projects_without_record == ()
    assert [(line.label, line.total) for line in painel.by_situation] == [
        ("Rascunho", 1),
        ("Publicada", 1),
    ]


def test_o_painel_do_portfolio_lista_os_projetos_sem_registro(sessao: Session) -> None:
    projeto, membro, _ = _cenario(sessao)
    outro = projeto_com_orcamento(sessao, codigo="TN-2026-021", padrao="CB-2026")
    _criar(sessao, projeto, membro)

    painel = lessons_service.lesson_panel(sessao, user=membro, scope=PORTFOLIO, reference_date=HOJE)

    assert painel.total == 1
    assert [item.code for item in painel.projects_without_record] == [outro.code]


# ── Tela e exportação ───────────────────────────────────────────────────────────────────────


def test_o_acervo_traz_a_aba_do_painel(sessao: Session) -> None:
    projeto, membro, _ = _cenario(sessao)
    _criar(sessao, projeto, membro)

    resposta = lessons_routes.lesson_acervo(
        requisicao("/api/governanca/licoes", email=MEMBRO, params={"projeto": str(projeto.id)})
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "Painel" in corpo
    assert "Lições por fase" in corpo
    assert "Projetos sem registro" in corpo
    assert 'data-grafico="comparativo-barras"' in corpo


def test_o_excel_do_acervo_traz_as_tabelas_do_painel(sessao: Session) -> None:
    projeto, membro, _ = _cenario(sessao)
    _criar(sessao, projeto, membro)

    resposta = lessons_routes.lesson_acervo_excel(
        requisicao(
            "/api/governanca/licoes/excel", email=MEMBRO, params={"projeto": str(projeto.id)}
        )
    )

    assert resposta.status_code == 200
    assert "spreadsheet" in resposta.headers["Content-Type"]
    assert resposta.get_body(), "a planilha do acervo não pode sair vazia"


def test_o_painel_usa_a_janela_do_parametro(sessao: Session) -> None:
    projeto, membro, _ = _cenario(sessao)
    _criar(sessao, projeto, membro)

    painel = lessons_service.lesson_panel(
        sessao, user=membro, scope=escopo_do_projeto(projeto), reference_date=HOJE
    )

    assert painel.alert_days == 90, "o padrão do protótipo (licoes.alertaSemRegistroDias)"
    assert painel.published_in_period == 0, "a lição de hoje é Rascunho, não Publicada"
