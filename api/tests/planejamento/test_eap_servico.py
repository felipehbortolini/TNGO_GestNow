"""Fachada da EAP (ISSUE-036): a árvore, o dicionário e a visão carteira.

O cenário repete o projeto 1 da demonstração em pequena escala: duas áreas, três subáreas, oito
pacotes (um de planejamento), dois vencidos, a Rev 1 vigente ligada à SM e o desdobramento
2.1.2 > 2.1.5. O real de cada pacote sai das entradas gravadas do critério, as somas são
ponderadas pelo peso e as faixas usam os parâmetros vigentes (2 e 5 p.p. quando não há versão).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from src.core.errors import AccessDeniedError, InvalidDataError, VersionConflictError
from src.core.rbac import Bond, GeneralProfile, User
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.models import Collaborator, Company, Person, Project, Unit
from src.modulos.financeiro.models import EacItem
from src.modulos.governanca.models import ChangeImpact, ChangeRequest
from src.modulos.planejamento import service
from src.modulos.planejamento.models import (
    EapBreakdown,
    EapItem,
    EapItemStep,
    EapMeasurement,
    EapRevision,
    EapRevisionItem,
)
from tests.apoio_6wla import HOJE
from tests.identidades import criar_colaborador, criar_empresa, criar_projeto

D = Decimal
PORTFOLIO = Scope(project_id=None, source="padrao")


@dataclass(frozen=True)
class CenarioEap:
    """Os projetos com EAP, o projeto sem EAP, as pessoas, a EAC e os itens do cenário."""

    session: Session
    projeto: Project
    outro: Project
    sem_eap: Project
    empresa: Company
    responsavel: Person
    unidade: Unit
    membro: Collaborator
    visualizador: Collaborator
    fornecedor: Collaborator
    itens: dict[str, EapItem]
    item_outro: EapItem
    eac: dict[str, EacItem]

    @property
    def escopo(self) -> Scope:
        return Scope(project_id=self.projeto.id, source="url")

    @property
    def usuario_membro(self) -> User:
        return _usuario(self.membro, GeneralProfile.MEMBER)

    @property
    def usuario_visualizador(self) -> User:
        return _usuario(self.visualizador, GeneralProfile.VIEWER)

    @property
    def usuario_fornecedor(self) -> User:
        return _usuario(self.fornecedor, GeneralProfile.MEMBER)


@dataclass(frozen=True)
class _Insumos:
    """Os registros que os pacotes do projeto 1 mencionam: empresa, responsável, unidade e EAC."""

    empresa: Company
    responsavel: Person
    unidade: Unit
    eac: dict[str, EacItem]


def _usuario(colaborador: Collaborator, perfil: GeneralProfile) -> User:
    return User(
        id=colaborador.id,
        person_id=colaborador.person_id,
        name="Pessoa de teste",
        email="pessoa@example.invalid",
        general_profile=perfil,
        bond=Bond(colaborador.bond),
    )


def _eac(
    session: Session,
    project: Project,
    code: str,
    description: str,
    parent: EacItem | None = None,
    **fields: object,
) -> EacItem:
    item = EacItem(
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


def _mudanca(
    session: Session,
    project: Project,
    *,
    code: str,
    situation: str,
    responsavel: Person,
) -> ChangeRequest:
    change = ChangeRequest(
        project_id=project.id,
        requester_id=responsavel.id,
        code=code,
        title=f"Mudança {code}",
        kind="Escopo",
        origin="Cliente",
        priority="Normal",
        request_date=date(2026, 5, 1),
        description="Descrição da mudança de teste.",
        situation=situation,
    )
    session.add(change)
    session.flush()
    return change


def _impacto(
    session: Session, change: ChangeRequest, responsavel: Person, *, scope: str
) -> ChangeImpact:
    impact = ChangeImpact(
        change_id=change.id,
        analyst_id=responsavel.id,
        analysis_date=date(2026, 5, 5),
        cost_cents=0,
        term_days=0,
        scope=scope,
        quality="Sem impacto",
        risks="Sem impacto",
        safety="Sem impacto",
        contract="Sem impacto",
        affects_contract_milestone=False,
    )
    session.add(impact)
    session.flush()
    return impact


def _montar_eac(session: Session, projeto: Project) -> dict[str, EacItem]:
    raiz = _eac(session, projeto, "1", "Engenharia")
    sub = _eac(session, projeto, "1.1", "Projeto básico", raiz)
    return {
        "1.1.1": _eac(
            session, projeto, "1.1.1", "Estacas", sub, quantity=D("100"), unit_price_cents=500_000
        ),
        "1.1.2": _eac(
            session, projeto, "1.1.2", "Blocos", sub, quantity=D("50"), unit_price_cents=500_000
        ),
    }


def _montar_pacotes(session: Session, projeto: Project, insumos: _Insumos) -> dict[str, EapItem]:
    obra = _item(session, projeto, "1", "Obra civil")
    montagem = _item(session, projeto, "2", "Montagem")
    fundacoes = _item(session, projeto, "1.1", "Fundações", obra)
    estruturas = _item(session, projeto, "1.2", "Estruturas", obra)
    equipamentos = _item(session, projeto, "2.1", "Equipamentos", montagem)
    itens = {
        "1": obra,
        "2": montagem,
        "1.1": fundacoes,
        "1.2": estruturas,
        "2.1": equipamentos,
    }
    itens["1.1.1"] = _item(
        session,
        projeto,
        "1.1.1",
        "Estacas",
        fundacoes,
        kind="Trabalho",
        criterion="Unidades",
        weight=D("20"),
        predicted=D("92"),
        start=date(2026, 5, 2),
        finish=date(2026, 8, 30),
        quantity=D("100"),
        executed=D("90"),
        unit_id=insumos.unidade.id,
        eac_item_id=insumos.eac["1.1.1"].id,
        company_id=insumos.empresa.id,
        owner_id=insumos.responsavel.id,
    )
    itens["1.1.2"] = _item(
        session,
        projeto,
        "1.1.2",
        "Blocos",
        fundacoes,
        kind="Trabalho",
        criterion="Marco 0/100",
        weight=D("10"),
        predicted=D("2.1"),
        start=date(2026, 8, 1),
        finish=date(2026, 12, 1),
        state="Não iniciado",
    )
    itens["1.2.1"] = _item(
        session,
        projeto,
        "1.2.1",
        "Estruturas metálicas",
        estruturas,
        kind="Trabalho",
        criterion="Etapas",
        model="engenharia",
        weight=D("30"),
        predicted=D("60"),
        start=date(2026, 3, 1),
        finish=date(2026, 9, 10),
        deliverable="Estruturas montadas",
        acceptance="Relatório de inspeção aprovado",
    )
    itens["2.1.1"] = _item(
        session,
        projeto,
        "2.1.1",
        "Bomba principal",
        equipamentos,
        kind="Trabalho",
        criterion="Percentual estimado",
        weight=D("10"),
        predicted=D("25"),
        start=date(2026, 7, 1),
        finish=date(2026, 11, 1),
        estimated_pct=D("20"),
    )
    itens["2.1.2"] = _item(
        session,
        projeto,
        "2.1.2",
        "Partida assistida",
        equipamentos,
        kind="Planejamento",
        weight=D("3"),
        predicted=D("0"),
        start=date(2026, 6, 1),
        finish=date(2027, 2, 1),
    )
    itens["2.1.3"] = _item(
        session,
        projeto,
        "2.1.3",
        "Alinhamento",
        equipamentos,
        kind="Trabalho",
        criterion="Marco 50/50",
        weight=D("15"),
        predicted=D("55.1"),
        start=date(2026, 6, 15),
        finish=date(2026, 12, 20),
        state="Iniciado",
    )
    itens["2.1.4"] = _item(
        session,
        projeto,
        "2.1.4",
        "Comissionamento",
        equipamentos,
        kind="Trabalho",
        criterion="Marco 0/100",
        weight=D("10"),
        predicted=D("95"),
        start=date(2026, 4, 1),
        finish=date(2026, 9, 1),
        state="Concluído",
    )
    itens["2.1.5"] = _item(
        session,
        projeto,
        "2.1.5",
        "Inspeção final",
        equipamentos,
        kind="Trabalho",
        criterion="Percentual estimado",
        weight=D("2"),
        predicted=D("0"),
        estimated_pct=D("0"),
    )
    for order, (nome, peso, pct) in enumerate(
        (
            ("Elaboração", D("40"), D("100")),
            ("Emissão", D("30"), D("50")),
            ("Construção", D("30"), D("0")),
        ),
        start=1,
    ):
        session.add(
            EapItemStep(item_id=itens["1.2.1"].id, order=order, name=nome, weight=peso, pct=pct)
        )
    for measured_on, from_pct, to_pct, note in (
        (date(2026, 8, 10), D("0"), D("50"), "Boletim 1"),
        (date(2026, 9, 12), D("50"), D("90"), "Boletim 2"),
    ):
        session.add(
            EapMeasurement(
                item_id=itens["1.1.1"].id,
                author_id=insumos.responsavel.id,
                measured_on=measured_on,
                from_pct=from_pct,
                to_pct=to_pct,
                note=note,
            )
        )
    session.flush()
    return itens


def _montar_revisoes(
    session: Session, projeto: Project, itens: dict[str, EapItem], responsavel: Person
) -> None:
    session.add(
        EapRevision(
            project_id=projeto.id,
            approved_by_id=responsavel.id,
            revision=0,
            revision_date=date(2026, 1, 5),
            alteration="Linha de base",
            justification="Linha de base aprovada no gate de investimento.",
        )
    )
    session.flush()
    sm = _mudanca(
        session, projeto, code="SM-TN-2026-0002", situation="Encerrada", responsavel=responsavel
    )
    revisao = EapRevision(
        project_id=projeto.id,
        change_id=sm.id,
        approved_by_id=responsavel.id,
        revision=1,
        revision_date=date(2026, 7, 10),
        alteration="Peso de 1.2.1 ajustado; demais pesos reescalados",
        justification="Reforço das fundações por interferência no subsolo.",
    )
    session.add(revisao)
    session.flush()
    for code in ("1.1.1", "1.1.2", "1.2.1", "2.1.1", "2.1.2", "2.1.3", "2.1.4"):
        session.add(
            EapRevisionItem(
                revision_id=revisao.id, item_id=itens[code].id, weight=itens[code].weight
            )
        )
    for revision, weight, applied_on in (
        (1, D("2"), date(2026, 9, 10)),
        (0, D("1"), date(2026, 1, 6)),
    ):
        session.add(
            EapBreakdown(
                project_id=projeto.id,
                source_item_id=itens["2.1.2"].id,
                target_item_id=itens["2.1.5"].id,
                by_id=responsavel.id,
                revision=revision,
                applied_on=applied_on,
                weight=weight,
                justification="Plano de comissionamento detalhado.",
            )
        )
    pendente = _mudanca(
        session,
        projeto,
        code="SM-TN-2026-0004",
        situation="Em implementação",
        responsavel=responsavel,
    )
    _impacto(session, pendente, responsavel, scope="120 t de estruturas")
    sem_impacto = _mudanca(
        session, projeto, code="SM-TN-2026-0005", situation="Aprovada", responsavel=responsavel
    )
    _impacto(session, sem_impacto, responsavel, scope="Sem impacto")
    session.flush()


def _montar_projeto_dois(session: Session, projeto: Project, responsavel: Person) -> EapItem:
    area = _item(session, projeto, "1", "Obra civil")
    sub = _item(session, projeto, "1.1", "Fundações", area)
    item = _item(
        session,
        projeto,
        "1.1.1",
        "Estacas",
        sub,
        kind="Trabalho",
        criterion="Marco 0/100",
        weight=D("60"),
        predicted=D("100"),
        start=date(2026, 2, 1),
        finish=date(2026, 6, 30),
        state="Concluído",
    )
    _item(
        session,
        projeto,
        "1.1.2",
        "Blocos",
        sub,
        kind="Trabalho",
        criterion="Marco 0/100",
        weight=D("40"),
        predicted=D("50"),
        start=date(2026, 8, 1),
        finish=date(2027, 1, 1),
        state="Não iniciado",
    )
    session.add(
        EapRevision(
            project_id=projeto.id,
            approved_by_id=responsavel.id,
            revision=0,
            revision_date=date(2026, 3, 2),
            alteration="Linha de base",
            justification="Linha de base aprovada no gate de investimento.",
        )
    )
    session.flush()
    return item


@pytest.fixture
def cenario_eap(sessao: Session) -> CenarioEap:
    """A EAP do projeto 1 com a Rev 1 vigente e o projeto 2; o projeto 3 fica sem EAP."""
    projeto = criar_projeto(sessao, codigo="TN-EAP-001", nome="Fábrica de teste")
    outro = criar_projeto(sessao, codigo="TN-EAP-002", nome="Caldeira de teste")
    sem_eap = criar_projeto(sessao, codigo="TN-EAP-003", nome="Projeto sem EAP")
    outro.budget_cents = 25_000_000
    sessao.flush()
    empresa = criar_empresa(sessao, "Montadora Alfa")
    membro = criar_colaborador(
        sessao, email="membro-eap@example.invalid", nome="Maria Medição", perfil="Membro"
    )
    visualizador = criar_colaborador(
        sessao, email="visualizador-eap@example.invalid", perfil="Visualizador"
    )
    fornecedor = criar_colaborador(
        sessao,
        email="fornecedor-eap@example.invalid",
        perfil="Membro",
        vinculo="Fornecedor",
        empresa=empresa,
    )
    sessao.flush()
    responsavel = sessao.get(Person, membro.person_id)
    assert responsavel is not None
    unidade = Unit(kind="medida", code="un", name="Unidade")
    sessao.add(unidade)
    sessao.flush()

    eac = _montar_eac(sessao, projeto)
    insumos = _Insumos(empresa=empresa, responsavel=responsavel, unidade=unidade, eac=eac)
    itens = _montar_pacotes(sessao, projeto, insumos)
    _montar_revisoes(sessao, projeto, itens, responsavel)
    item_outro = _montar_projeto_dois(sessao, outro, responsavel)
    return CenarioEap(
        session=sessao,
        projeto=projeto,
        outro=outro,
        sem_eap=sem_eap,
        empresa=empresa,
        responsavel=responsavel,
        unidade=unidade,
        membro=membro,
        visualizador=visualizador,
        fornecedor=fornecedor,
        itens=itens,
        item_outro=item_outro,
        eac=eac,
    )


def _visao(cenario: CenarioEap, scope: Scope | None = None) -> service.EapOverview:
    return service.eap_overview(
        cenario.session,
        user=cenario.usuario_membro,
        scope=scope or cenario.escopo,
        reference_date=HOJE,
    )


def _no(visao: service.EapOverview, code: str) -> service.EapNode:
    return next(node for node in visao.nodes if node.code == code)


def _dicionario(cenario: CenarioEap) -> dict[str, str]:
    item = cenario.itens["1.1.1"]
    return {
        "descricao": item.description,
        "entregavel": item.deliverable or "",
        "aceitacao": item.acceptance or "",
        "empresa": str(cenario.empresa.id),
        "responsavel": str(cenario.responsavel.id),
        "eac": "",
        "versao": str(item.version),
    }


# ── A árvore do projeto ───────────────────────────────────────────────────


def test_arvore_do_projeto_soma_os_filhos_e_fecha_em_100(cenario_eap: CenarioEap) -> None:
    visao = _visao(cenario_eap)

    assert not visao.is_portfolio
    assert not visao.is_empty
    assert visao.can_edit
    assert not visao.can_manage
    assert visao.scope_label == "TN-EAP-001 · Fábrica de teste"
    assert [node.code for node in visao.nodes] == [
        "0",
        "1",
        "1.1",
        "1.1.1",
        "1.1.2",
        "1.2",
        "1.2.1",
        "2",
        "2.1",
        "2.1.1",
        "2.1.2",
        "2.1.3",
        "2.1.4",
        "2.1.5",
    ]

    raiz = visao.root
    assert (raiz.level, raiz.weight) == (0, D("100.00"))
    assert (raiz.predicted, raiz.actual) == (D("56.88"), D("54.00"))
    assert (raiz.deviation_pp, raiz.band) == (D("-2.9"), "warning")
    assert (raiz.start, raiz.finish) == (date(2026, 3, 1), date(2027, 2, 1))
    assert raiz.description == "Fábrica de teste"

    assert _no(visao, "1").weight == D("60.00")
    assert _no(visao, "2").weight == D("40.00")
    assert _no(visao, "1.1").weight == D("30.00")
    assert (_no(visao, "1.1").predicted, _no(visao, "1.1").actual) == (D("62.03"), D("60.00"))
    assert _no(visao, "1.1").weight_in_parent == D("50.0")
    assert _no(visao, "1.1.1").weight_in_parent == D("66.7")
    assert _no(visao, "1").weight_in_parent is None


def test_o_gestor_pode_gerir_a_revisao_e_o_desdobramento(cenario_eap: CenarioEap) -> None:
    gestor = criar_colaborador(
        cenario_eap.session, email="gabriel.gestor@example.invalid", perfil="Gestor"
    )

    visao = service.eap_overview(
        cenario_eap.session,
        user=_usuario(gestor, GeneralProfile.MANAGER),
        scope=cenario_eap.escopo,
        reference_date=HOJE,
    )

    assert visao.can_edit
    assert visao.can_manage


def test_o_real_de_cada_pacote_sai_das_entradas_do_criterio(cenario_eap: CenarioEap) -> None:
    visao = _visao(cenario_eap)

    assert _no(visao, "1.1.1").actual == D("90.00")
    assert _no(visao, "1.1.2").actual == D("0.00")
    assert _no(visao, "1.2.1").actual == D("55.00")
    assert _no(visao, "2.1.1").actual == D("20.00")
    assert _no(visao, "2.1.2").actual == D("0.00")
    assert _no(visao, "2.1.3").actual == D("50.00")
    assert _no(visao, "2.1.4").actual == D("100.00")
    assert [(etapa.name, etapa.weight, etapa.pct) for etapa in _no(visao, "1.2.1").steps] == [
        ("Elaboração", D("40.00"), D("100.00")),
        ("Emissão", D("30.00"), D("50.00")),
        ("Construção", D("30.00"), D("0.00")),
    ]
    assert _no(visao, "1.2.1").model == "Engenharia (documentos)"


def test_as_faixas_do_desvio_batem_nas_fronteiras(cenario_eap: CenarioEap) -> None:
    visao = _visao(cenario_eap)

    assert (_no(visao, "1.1.1").deviation_pp, _no(visao, "1.1.1").band) == (D("-2.0"), "success")
    assert (_no(visao, "1.1.2").deviation_pp, _no(visao, "1.1.2").band) == (D("-2.1"), "warning")
    assert (_no(visao, "1.2.1").deviation_pp, _no(visao, "1.2.1").band) == (D("-5.0"), "warning")
    assert (_no(visao, "2.1.3").deviation_pp, _no(visao, "2.1.3").band) == (D("-5.1"), "danger")
    assert (_no(visao, "2.1.4").deviation_pp, _no(visao, "2.1.4").band) == (D("5.0"), "success")


def test_indicadores_marcam_dois_vencidos_no_projeto_1(cenario_eap: CenarioEap) -> None:
    visao = _visao(cenario_eap)
    indicadores = visao.indicators

    assert (indicadores.work_packages, indicadores.planning_packages) == (7, 1)
    assert indicadores.planning_weight == D("3.00")
    assert (indicadores.areas, indicadores.subareas) == (2, 3)
    assert indicadores.overdue == 2
    assert indicadores.not_started == 1
    assert indicadores.late == 1
    assert indicadores.spi == D("0.95")
    assert indicadores.projects == 1
    assert _no(visao, "1.1.1").overdue
    assert _no(visao, "1.2.1").overdue
    assert not _no(visao, "1.1.2").overdue
    assert _no(visao, "1.1.2").not_started


def test_o_dicionario_traz_eac_unidade_empresa_e_medicoes(cenario_eap: CenarioEap) -> None:
    visao = _visao(cenario_eap)
    no = _no(visao, "1.1.1")

    assert (no.eac_code, no.unit, no.company_name, no.owner_name) == (
        "1.1.1",
        "un",
        "Montadora Alfa",
        "Maria Medição",
    )
    assert [
        (medicao.measured_on, medicao.from_pct, medicao.to_pct, medicao.author, medicao.note)
        for medicao in no.measurements
    ] == [
        (date(2026, 8, 10), D("0.00"), D("50.00"), "Maria Medição", "Boletim 1"),
        (date(2026, 9, 12), D("50.00"), D("90.00"), "Maria Medição", "Boletim 2"),
    ]
    assert not any(medicao.is_reversal for medicao in no.measurements)


def test_a_revisao_vigente_os_desdobramentos_e_as_sms_a_incorporar(
    cenario_eap: CenarioEap,
) -> None:
    visao = _visao(cenario_eap)

    assert [revisao.revision for revisao in visao.revisions] == [0, 1]
    vigente = visao.current_revision
    assert vigente is not None
    assert (vigente.revision, vigente.package_count) == (1, 7)
    assert (vigente.change_code, vigente.approved_by) == ("SM-TN-2026-0002", "Maria Medição")
    assert vigente.revision_date == date(2026, 7, 10)
    assert [
        (linha.source_code, linha.target_code, linha.weight, linha.author)
        for linha in visao.breakdowns
    ] == [("2.1.2", "2.1.5", D("2.00"), "Maria Medição")]
    assert [(pendente.code, pendente.project_label) for pendente in visao.pending_changes] == [
        ("SM-TN-2026-0004", "TN-EAP-001 · Fábrica de teste")
    ]


def test_a_faixa_usa_o_parametro_vigente(cenario_eap: CenarioEap) -> None:
    sessao = cenario_eap.session
    configuracoes.seed_initial_parameters(
        sessao, author_id=cenario_eap.membro.id, effective_from=date(2026, 1, 1)
    )
    valores = dict(configuracoes.INITIAL_PARAMETERS["eap"])
    valores["faixasDesvioPP"] = [1, 3]
    configuracoes.save_parameter_group(
        sessao,
        author_id=cenario_eap.membro.id,
        group="eap",
        values=valores,
        effective_from=HOJE,
        justification="Faixas mais rígidas para o teste da fachada.",
    )

    visao = _visao(cenario_eap)

    assert (_no(visao, "1.1.1").deviation_pp, _no(visao, "1.1.1").band) == (D("-2.0"), "warning")
    assert (_no(visao, "1.2.1").deviation_pp, _no(visao, "1.2.1").band) == (D("-5.0"), "danger")


# ── O Portfólio ───────────────────────────────────────────────────────────


def test_o_portfolio_e_somente_leitura_e_pondera_pelo_peso_na_carteira(
    cenario_eap: CenarioEap,
) -> None:
    visao = _visao(cenario_eap, PORTFOLIO)

    assert visao.is_portfolio
    assert not visao.can_edit
    assert not visao.can_manage
    assert visao.scope_label == "Portfólio"
    assert visao.current_revision is None
    assert visao.breakdowns == ()
    assert [node.code for node in visao.nodes] == ["0", "1", "1.1", "1.2", "2", "2.1"]

    raiz = visao.root
    assert (raiz.weight, raiz.predicted, raiz.actual) == (D("100.00"), D("62.66"), D("55.50"))
    projeto = _no(visao, "1")
    assert (projeto.weight, projeto.weight_in_parent, projeto.actual) == (
        D("75.00"),
        D("75.00"),
        D("54.00"),
    )
    area = _no(visao, "1.1")
    assert (area.weight, area.weight_in_parent, area.weight_in_project) == (
        D("45.00"),
        D("60.00"),
        D("60.00"),
    )
    assert _no(visao, "2.1").weight == D("25.00")
    assert [revisao.project_label for revisao in visao.revisions] == [
        "TN-EAP-001 · Fábrica de teste",
        "TN-EAP-002 · Caldeira de teste",
    ]
    assert [revisao.revision_count for revisao in visao.revisions] == [2, 1]

    indicadores = visao.indicators
    assert (indicadores.work_packages, indicadores.planning_packages) == (9, 1)
    assert (indicadores.areas, indicadores.subareas) == (3, 4)
    assert (indicadores.overdue, indicadores.not_started, indicadores.late) == (2, 2, 2)
    assert indicadores.planning_weight is None
    assert indicadores.projects == 2
    assert [(pendente.code, pendente.project_label) for pendente in visao.pending_changes] == [
        ("SM-TN-2026-0004", "TN-EAP-001 · Fábrica de teste")
    ]


def test_o_portfolio_recusa_o_dicionario(cenario_eap: CenarioEap) -> None:
    with pytest.raises(AccessDeniedError):
        service.update_dictionary(
            cenario_eap.session,
            user=cenario_eap.usuario_membro,
            scope=PORTFOLIO,
            item_id=cenario_eap.itens["1.1.1"].id,
            form=_dicionario(cenario_eap),
        )


# ── O dicionário ──────────────────────────────────────────────────────────


def test_o_dicionario_grava_e_nao_mexe_na_linha_de_base(cenario_eap: CenarioEap) -> None:
    item = cenario_eap.itens["1.1.1"]
    versao = item.version
    formulario = _dicionario(cenario_eap)
    formulario.update(
        descricao="Estacas executadas",
        entregavel="Estacas concretadas",
        aceitacao="Laudo de integridade",
        eac="1.1.2",
        peso="99",
        inicio="2020-01-01",
        criterio="Etapas",
    )

    gravado = service.update_dictionary(
        cenario_eap.session,
        user=cenario_eap.usuario_membro,
        scope=cenario_eap.escopo,
        item_id=item.id,
        form=formulario,
    )

    assert (gravado.description, gravado.deliverable, gravado.acceptance) == (
        "Estacas executadas",
        "Estacas concretadas",
        "Laudo de integridade",
    )
    assert (gravado.company_id, gravado.owner_id) == (
        cenario_eap.empresa.id,
        cenario_eap.responsavel.id,
    )
    assert gravado.eac_item_id == cenario_eap.eac["1.1.2"].id
    assert (gravado.weight, gravado.start, gravado.criterion) == (
        D("20.00"),
        date(2026, 5, 2),
        "Unidades",
    )
    assert gravado.version == versao + 1


def test_o_dicionario_recusa_perfil_portfolio_outro_projeto_e_nivel_2(
    cenario_eap: CenarioEap,
) -> None:
    formulario = _dicionario(cenario_eap)

    with pytest.raises(AccessDeniedError):
        service.update_dictionary(
            cenario_eap.session,
            user=cenario_eap.usuario_visualizador,
            scope=cenario_eap.escopo,
            item_id=cenario_eap.itens["1.1.1"].id,
            form=formulario,
        )
    with pytest.raises(AccessDeniedError):
        service.update_dictionary(
            cenario_eap.session,
            user=cenario_eap.usuario_membro,
            scope=cenario_eap.escopo,
            item_id=cenario_eap.item_outro.id,
            form=formulario,
        )
    with pytest.raises(InvalidDataError):
        service.update_dictionary(
            cenario_eap.session,
            user=cenario_eap.usuario_membro,
            scope=cenario_eap.escopo,
            item_id=cenario_eap.itens["1.1"].id,
            form=formulario,
        )


def test_o_dicionario_recusa_eac_desconhecida_e_descricao_curta(
    cenario_eap: CenarioEap,
) -> None:
    formulario = _dicionario(cenario_eap)
    formulario["eac"] = "9.9.9"

    with pytest.raises(InvalidDataError) as recusa:
        service.update_dictionary(
            cenario_eap.session,
            user=cenario_eap.usuario_membro,
            scope=cenario_eap.escopo,
            item_id=cenario_eap.itens["1.1.1"].id,
            form=formulario,
        )

    assert isinstance(recusa.value.detail, dict)
    assert "eac" in recusa.value.detail

    formulario = _dicionario(cenario_eap)
    formulario["descricao"] = "ab"

    with pytest.raises(InvalidDataError) as recusa:
        service.update_dictionary(
            cenario_eap.session,
            user=cenario_eap.usuario_membro,
            scope=cenario_eap.escopo,
            item_id=cenario_eap.itens["1.1.1"].id,
            form=formulario,
        )

    assert "descricao" in recusa.value.detail


def test_o_dicionario_com_versao_vencida_e_conflito(cenario_eap: CenarioEap) -> None:
    formulario = _dicionario(cenario_eap)
    formulario["versao"] = "999"

    with pytest.raises(VersionConflictError):
        service.update_dictionary(
            cenario_eap.session,
            user=cenario_eap.usuario_membro,
            scope=cenario_eap.escopo,
            item_id=cenario_eap.itens["1.1.1"].id,
            form=formulario,
        )


def test_a_leitura_exige_o_modulo_e_recusa_projeto_desconhecido(cenario_eap: CenarioEap) -> None:
    with pytest.raises(AccessDeniedError):
        service.eap_overview(
            cenario_eap.session,
            user=cenario_eap.usuario_fornecedor,
            scope=cenario_eap.escopo,
            reference_date=HOJE,
        )
    with pytest.raises(InvalidDataError):
        service.eap_overview(
            cenario_eap.session,
            user=cenario_eap.usuario_membro,
            scope=Scope(project_id=999_999, source="url"),
            reference_date=HOJE,
        )
