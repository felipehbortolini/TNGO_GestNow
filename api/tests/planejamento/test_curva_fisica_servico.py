"""Fachada da Curva S física (ISSUE-039): congelamento, consulta viva e carteira.

O cenário tem dois projetos com curva congelada e um sem curva. No projeto 1 os pacotes vão de
jan/26 a dez/26 (jan a jun, 60%; jul a dez, 40%) com medições datadas; no projeto 2 um pacote
único de mar/26 a nov/26, concluído em jun/26. A revisão 0 fica congelada em 25/09/2026; o
``create_revision`` gera a curva da revisão nova sem tocar na anterior. A carteira fecha em
75/25 pelos orçamentos dos dois projetos.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.rbac import Bond, GeneralProfile, User
from src.core.scope import Scope
from src.modulos.configuracoes.models import Collaborator, Project, Unit
from src.modulos.governanca.models import ChangeImpact, ChangeRequest
from src.modulos.planejamento import service, validation
from src.modulos.planejamento.models import (
    CurvaFisicaMonth,
    CurvaFisicaRevision,
    EapItem,
    EapMeasurement,
    EapRevision,
    EapRevisionItem,
)
from tests.apoio_6wla import HOJE
from tests.identidades import criar_colaborador, criar_projeto

D = Decimal
PORTFOLIO = Scope(project_id=None, source="padrao")

JAN = date(2026, 1, 1)
FEB = date(2026, 2, 1)
APR = date(2026, 4, 1)
JUL = date(2026, 7, 1)
AUG = date(2026, 8, 1)
SEP = date(2026, 9, 1)
DEC = date(2026, 12, 1)

SM = "SM-TN-2026-0390"
JUSTIFICATIVA = "Ajuste de peso aprovado na SM."
LIMITES = validation.RevisionLimits(max_package_weight=D(10), max_estimated_weight=D(5))


@dataclass(frozen=True)
class CenarioCurva:
    """Os projetos com e sem curva, as pessoas, o item do projeto 2 e a SM aprovada."""

    session: Session
    projeto: Project
    outro: Project
    sem_curva: Project
    unidade: Unit
    membro: Collaborator
    gestor: Collaborator
    visualizador: Collaborator
    itens: dict[str, EapItem]
    item_outro: EapItem
    revisao_zero: EapRevision

    @property
    def escopo(self) -> Scope:
        return Scope(project_id=self.projeto.id, source="url")

    @property
    def usuario_membro(self) -> User:
        return _usuario(self.membro, GeneralProfile.MEMBER)

    @property
    def usuario_gestor(self) -> User:
        return _usuario(self.gestor, GeneralProfile.MANAGER)


def _usuario(colaborador: Collaborator, perfil: GeneralProfile) -> User:
    return User(
        id=colaborador.id,
        person_id=colaborador.person_id,
        name="Pessoa de teste",
        email="pessoa@example.invalid",
        general_profile=perfil,
        bond=Bond(colaborador.bond),
    )


def _item(
    session: Session,
    project: Project,
    code: str,
    description: str,
    parent: EapItem | None = None,
    **fields: object,
) -> EapItem:
    item = EapItem(
        project_id=project.id,
        parent_id=parent.id if parent is not None else None,
        code=code,
        description=description,
        level=len(code.split(".")),
        **fields,
    )
    session.add(item)
    session.flush()
    return item


def _medicao(session: Session, autor: Collaborator, item: EapItem, dia: date, para: str) -> None:
    session.add(
        EapMeasurement(
            item_id=item.id,
            author_id=autor.person_id,
            measured_on=dia,
            from_pct=D("0"),
            to_pct=D(para),
            note="Boletim",
        )
    )
    session.flush()


def _montar_projeto(session: Session, projeto: Project, unidade: Unit) -> dict[str, EapItem]:
    obra = _item(session, projeto, "1", "Obra civil")
    fundacoes = _item(session, projeto, "1.1", "Fundações", obra)
    itens = {"1": obra, "1.1": fundacoes}
    itens["1.1.1"] = _item(
        session,
        projeto,
        "1.1.1",
        "Estacas",
        fundacoes,
        kind="Trabalho",
        criterion="Unidades",
        weight=D("60"),
        predicted=D("100"),
        start=date(2026, 1, 1),
        finish=date(2026, 6, 30),
        quantity=D("100"),
        executed=D("100"),
        unit_id=unidade.id,
    )
    itens["1.1.2"] = _item(
        session,
        projeto,
        "1.1.2",
        "Blocos",
        fundacoes,
        kind="Trabalho",
        criterion="Unidades",
        weight=D("40"),
        predicted=D("0"),
        start=date(2026, 7, 1),
        finish=date(2026, 12, 31),
        quantity=D("100"),
        executed=D("50"),
        unit_id=unidade.id,
    )
    return itens


def _montar_projeto_dois(session: Session, projeto: Project, unidade: Unit) -> EapItem:
    area = _item(session, projeto, "1", "Obra civil")
    sub = _item(session, projeto, "1.1", "Fundações", area)
    return _item(
        session,
        projeto,
        "1.1.1",
        "Estacas",
        sub,
        kind="Trabalho",
        criterion="Unidades",
        weight=D("100"),
        predicted=D("100"),
        start=date(2026, 3, 1),
        finish=date(2026, 11, 30),
        quantity=D("100"),
        executed=D("100"),
        unit_id=unidade.id,
    )


def _revisao(session: Session, projeto: Project, itens: dict[str, EapItem]) -> EapRevision:
    revisao = EapRevision(
        project_id=projeto.id,
        approved_by_id=projeto.manager_id,
        revision=0,
        revision_date=date(2026, 1, 5),
        alteration="Linha de base",
        justification="Linha de base aprovada no gate de investimento.",
    )
    session.add(revisao)
    session.flush()
    for item in itens.values():
        session.add(
            EapRevisionItem(revision_id=revisao.id, item_id=item.id, weight=item.weight or D(0))
        )
    session.flush()
    return revisao


def _mudanca(session: Session, projeto: Project, *, code: str) -> ChangeRequest:
    change = ChangeRequest(
        project_id=projeto.id,
        requester_id=projeto.manager_id,
        code=code,
        title=f"Mudança {code}",
        kind="Escopo",
        origin="Cliente",
        priority="Normal",
        request_date=date(2026, 9, 1),
        description="Descrição da mudança de teste.",
        situation="Aprovada",
    )
    session.add(change)
    session.flush()
    session.add(
        ChangeImpact(
            change_id=change.id,
            analyst_id=projeto.manager_id,
            analysis_date=date(2026, 9, 10),
            cost_cents=0,
            term_days=0,
            scope="Inclusão do pacote de tubulação",
            quality="Sem impacto",
            risks="Sem impacto",
            safety="Sem impacto",
            contract="Sem impacto",
            affects_contract_milestone=False,
        )
    )
    session.flush()
    return change


@pytest.fixture
def cenario_curva(sessao: Session) -> CenarioCurva:
    """Os dois projetos com a revisão 0 congelada e o projeto 3 sem curva, na transação do teste."""
    projeto = criar_projeto(sessao, codigo="TN-CURVA-001", nome="Fábrica da curva")
    outro = criar_projeto(sessao, codigo="TN-CURVA-002", nome="Caldeira da curva")
    sem_curva = criar_projeto(sessao, codigo="TN-CURVA-003", nome="Projeto sem curva")
    projeto.budget_cents = 75_000_000
    outro.budget_cents = 25_000_000
    sessao.flush()
    unidade = Unit(kind="medida", code="un", name="Unidade")
    sessao.add(unidade)
    membro = criar_colaborador(sessao, email="membro-curva@example.invalid", perfil="Membro")
    gestor = criar_colaborador(sessao, email="gestor-curva@example.invalid", perfil="Gestor")
    visualizador = criar_colaborador(
        sessao, email="visualizador-curva@example.invalid", perfil="Visualizador"
    )
    sessao.flush()
    itens = _montar_projeto(sessao, projeto, unidade)
    revisao_zero = _revisao(sessao, projeto, itens)
    _medicao(sessao, membro, itens["1.1.1"], date(2026, 2, 10), "50")
    _medicao(sessao, membro, itens["1.1.1"], date(2026, 4, 20), "100")
    _medicao(sessao, membro, itens["1.1.2"], date(2026, 8, 5), "50")
    service.freeze_curve(
        sessao, project_id=projeto.id, revision_id=revisao_zero.id, reference_date=HOJE
    )
    item_outro = _montar_projeto_dois(sessao, outro, unidade)
    revisao_outro = _revisao(sessao, outro, {"1.1.1": item_outro})
    _medicao(sessao, membro, item_outro, date(2026, 6, 15), "100")
    service.freeze_curve(
        sessao, project_id=outro.id, revision_id=revisao_outro.id, reference_date=HOJE
    )
    _mudanca(sessao, projeto, code=SM)
    return CenarioCurva(
        session=sessao,
        projeto=projeto,
        outro=outro,
        sem_curva=sem_curva,
        unidade=unidade,
        membro=membro,
        gestor=gestor,
        visualizador=visualizador,
        itens=itens,
        item_outro=item_outro,
        revisao_zero=revisao_zero,
    )


def _visao(cenario: CenarioCurva, scope: Scope | None = None) -> service.CurvaFisicaOverview:
    return service.curva_fisica_overview(
        cenario.session, scope=scope or cenario.escopo, reference_date=HOJE
    )


def _estados(cenario: CenarioCurva) -> dict[str, validation.PackageState]:
    return {
        code: validation.PackageState(
            code=item.code,
            level=item.level,
            kind=item.kind or "",
            criterion=item.criterion,
            weight=item.weight or D(0),
            quantity=item.quantity,
            executed=item.executed,
            start=item.start,
            finish=item.finish,
        )
        for code, item in cenario.itens.items()
    }


def _ajuste(cenario: CenarioCurva) -> validation.RevisionAdjustment:
    raw = {"sm": SM, "pacote": "1.1.1", "peso": "8.00", "justificativa": JUSTIFICATIVA}
    return validation.parse_revision_form(
        raw, packages=_estados(cenario), limits=LIMITES
    ).adjustment


def _revisar(cenario: CenarioCurva) -> service.RevisionResult:
    return service.create_revision(
        cenario.session,
        user=cenario.usuario_gestor,
        scope=cenario.escopo,
        request=service.RevisionRequest(
            change_code=SM, justification=JUSTIFICATIVA, adjustments=(_ajuste(cenario),)
        ),
        reference_date=HOJE,
    )


def _registrar(cenario: CenarioCurva, item: EapItem, **campos: str) -> service.ProgressView:
    return service.register_progress(
        cenario.session,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        item_id=item.id,
        form={"versao": str(item.version), **campos},
        reference_date=HOJE,
    )


def _curva_do_projeto(session: Session, project_id: int, revision: int) -> CurvaFisicaRevision:
    statement = (
        select(CurvaFisicaRevision)
        .join(EapRevision, EapRevision.id == CurvaFisicaRevision.eap_revision_id)
        .where(
            CurvaFisicaRevision.project_id == project_id,
            EapRevision.revision == revision,
        )
    )
    return session.scalars(statement).one()


def _meses(session: Session, curve: CurvaFisicaRevision) -> dict[date, Decimal]:
    rows = session.scalars(
        select(CurvaFisicaMonth)
        .where(CurvaFisicaMonth.revision_id == curve.id)
        .order_by(CurvaFisicaMonth.month)
    )
    return {row.month: row.baseline_pct for row in rows}


# ── O congelamento ───────────────────────────────────────────────────────


def test_o_congelamento_entra_na_revisao_e_grava_os_meses(cenario_curva: CenarioCurva) -> None:
    resultado = _revisar(cenario_curva)

    curva = _curva_do_projeto(cenario_curva.session, cenario_curva.projeto.id, resultado.revision)

    assert curva.eap_revision_id is not None
    assert curva.generated_at is not None
    meses = _meses(cenario_curva.session, curva)
    assert list(meses) == [
        JAN,
        FEB,
        date(2026, 3, 1),
        APR,
        date(2026, 5, 1),
        date(2026, 6, 1),
        JUL,
        AUG,
        SEP,
        date(2026, 10, 1),
        date(2026, 11, 1),
        DEC,
    ]
    assert meses[SEP] == D("51.2")


def test_a_base_da_revisao_anterior_nao_muda_com_a_revisao_nova(
    cenario_curva: CenarioCurva,
) -> None:
    anterior = _curva_do_projeto(cenario_curva.session, cenario_curva.projeto.id, 0)
    antes = _meses(cenario_curva.session, anterior)

    resultado = _revisar(cenario_curva)

    depois = _meses(cenario_curva.session, anterior)
    nova = _meses(
        cenario_curva.session,
        _curva_do_projeto(cenario_curva.session, cenario_curva.projeto.id, resultado.revision),
    )
    assert depois == antes
    assert antes[SEP] == D("78.8")
    assert nova[SEP] == D("51.2")


def test_uma_medicao_nova_muda_a_curva_na_consulta_seguinte(cenario_curva: CenarioCurva) -> None:
    antes = _visao(cenario_curva)

    _registrar(cenario_curva, cenario_curva.itens["1.1.2"], data="2026-09-20", executado="80")
    depois = _visao(cenario_curva)

    assert antes.indicators.actual == D("80.0")
    assert depois.indicators.actual == D("92.0")
    assert depois.indicators.spi == D("1.17")
    assert depois.series.baseline == antes.series.baseline


# ── O real do período ────────────────────────────────────────────────────


def test_o_real_do_periodo_e_a_soma_ponderada_das_medicoes_ate_o_fim_dele(
    cenario_curva: CenarioCurva,
) -> None:
    visao = _visao(cenario_curva)

    assert visao.series.months[0] == JAN
    assert visao.series.real[0] == D("0.0")
    assert visao.series.real[1] == D("30.0")
    assert visao.series.real[3] == D("60.0")
    assert visao.series.real[6] == D("60.0")
    assert visao.series.real[7] == D("80.0")
    assert visao.series.real[8] == D("80.0")
    assert visao.series.real[9] is None


def test_o_mes_do_corte_e_o_primeiro_depois_da_referencia(cenario_curva: CenarioCurva) -> None:
    visao = _visao(cenario_curva)

    assert visao.indicators.cut_month == SEP
    assert [point.month for point in visao.points if point.is_cut] == [SEP]
    assert visao.points[7].month_actual == D("20.0")
    assert visao.points[8].month_actual == D("0.0")
    assert visao.points[9].month_actual is None
    assert visao.points[9].trend == D("87.9")


# ── Os indicadores ───────────────────────────────────────────────────────


def test_os_indicadores_trazem_spi_desvio_e_termino_pela_tendencia(
    cenario_curva: CenarioCurva,
) -> None:
    indicadores = _visao(cenario_curva).indicators

    assert indicadores.predicted == D("78.8")
    assert indicadores.actual == D("80.0")
    assert indicadores.deviation_pp == D("1.2")
    assert indicadores.spi == D("1.02")
    assert indicadores.previous_predicted == D("73.3")
    assert indicadores.previous_actual == D("80.0")
    assert indicadores.previous_spi == D("1.09")
    assert indicadores.trend_finish == DEC
    assert indicadores.baseline_finish == DEC


# ── A carteira ───────────────────────────────────────────────────────────


def test_o_portfolio_pondera_pelos_pesos_da_carteira(cenario_curva: CenarioCurva) -> None:
    visao = _visao(cenario_curva, PORTFOLIO)

    assert visao.is_portfolio
    assert not visao.is_empty
    assert visao.project_id is None
    assert [(item.project_label, item.weight) for item in visao.composition] == [
        ("TN-CURVA-001 · Fábrica da curva", D("75.00")),
        ("TN-CURVA-002 · Caldeira da curva", D("25.00")),
    ]
    assert visao.indicators.predicted == D("78.1")
    assert visao.indicators.actual == D("85.0")
    assert visao.indicators.deviation_pp == D("6.9")
    assert visao.indicators.spi == D("1.09")
    fabrica, caldeira = visao.composition
    assert (fabrica.predicted, fabrica.actual, fabrica.spi) == (D("78.8"), D("80.0"), D("1.02"))
    assert (fabrica.deviation_pp, fabrica.contribution_pp) == (D("1.2"), D("0.90"))
    assert (caldeira.predicted, caldeira.actual, caldeira.spi) == (D("75.9"), D("100.0"), D("1.32"))
    assert (caldeira.deviation_pp, caldeira.contribution_pp) == (D("24.1"), D("6.03"))
    assert caldeira.trend_finish == SEP
    assert caldeira.baseline_finish == date(2026, 11, 1)
    soma = sum((item.weight * item.predicted for item in visao.composition), D(0))
    divisor = sum((item.weight for item in visao.composition), D(0))
    assert visao.indicators.predicted == (soma / divisor).quantize(D("0.1"))


# ── O vazio e o gráfico ──────────────────────────────────────────────────


def test_sem_revisao_congelada_a_visao_sai_vazia(cenario_curva: CenarioCurva) -> None:
    visao = service.curva_fisica_overview(
        cenario_curva.session,
        scope=Scope(project_id=cenario_curva.sem_curva.id, source="url"),
        reference_date=HOJE,
    )

    assert visao.is_empty
    assert visao.scope_label == "TN-CURVA-003 · Projeto sem curva"
    assert visao.series.months == ()
    assert visao.points == ()
    assert visao.indicators.spi is None
    assert visao.indicators.predicted == D("0")
    assert visao.chart["periodos"] == []


def test_o_grafico_sai_em_semanas_iso_com_real_so_ate_a_referencia(
    cenario_curva: CenarioCurva,
) -> None:
    grafico = _visao(cenario_curva).chart

    assert grafico["modo"] == "acumulado"
    assert grafico["formato"] == "pct"
    assert [serie["id"] for serie in grafico["series"]] == [
        "linha_base",
        "realizado",
        "tendencia",
    ]
    periodos = grafico["periodos"]
    assert len(periodos) == 53
    assert (periodos[0]["ano"], periodos[0]["mes"], periodos[0]["semana"]) == (2026, 1, 1)
    assert (periodos[-1]["ano"], periodos[-1]["mes"], periodos[-1]["semana"]) == (2026, 12, 53)
    com_real = [periodo for periodo in periodos if periodo["valores"]["realizado"] is not None]
    assert com_real[-1]["valores"]["realizado"] == 80.0
    assert com_real[-1]["valores"]["tendencia"] == 80.0
    depois = periodos[periodos.index(com_real[-1]) + 1]
    assert depois["valores"]["realizado"] is None
    assert depois["valores"]["tendencia"] is not None
    assert periodos[0]["valores"]["tendencia"] is None
    assert all(periodo["valores"]["linha_base"] is not None for periodo in periodos)
