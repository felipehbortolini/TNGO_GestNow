"""Fachada da revisão da EAP e do desdobramento (ISSUE-038).

O cenário tem um projeto com cinco pacotes de nível 3 (um de planejamento), a Rev 0 da linha
de base e uma SM aprovada com impacto em escopo pendente de incorporação. A revisão ajusta
peso, quantidade e término, inclui pacotes novos e reescala os pesos livres para fechar 100
exatos; o desdobramento tira o peso da origem, encerra o pacote de planejamento zerado e
mantém o total do projeto.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.rbac import Bond, GeneralProfile, User
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.models import Collaborator, Person, Project, Unit
from src.modulos.governanca.models import ChangeImpact, ChangeRequest
from src.modulos.planejamento import service, validation
from src.modulos.planejamento.models import (
    EapBreakdown,
    EapItem,
    EapItemStep,
    EapRevision,
    EapRevisionItem,
)
from tests.apoio_6wla import HOJE
from tests.identidades import criar_colaborador, criar_projeto

D = Decimal
PORTFOLIO = Scope(project_id=None, source="padrao")
LIMITES = validation.RevisionLimits(max_package_weight=D(10), max_estimated_weight=D(5))
SM = "SM-TN-2026-0101"
JUSTIFICATIVA = "Acréscimo de escopo aprovado na SM."
PESOS_REESCALADOS = {
    "1.1.2": D("11.50"),
    "1.1.3": D("5.75"),
    "2.1.1": D("34.50"),
    "2.1.2": D("40.25"),
}


@dataclass(frozen=True)
class CenarioRevisao:
    """O projeto com a Rev 0, a SM pendente e a pessoa de cada perfil."""

    session: Session
    projeto: Project
    responsavel: Person
    unidade: Unit
    membro: Collaborator
    gestor: Collaborator
    visualizador: Collaborator
    itens: dict[str, EapItem]
    sm: ChangeRequest
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

    @property
    def usuario_visualizador(self) -> User:
        return _usuario(self.visualizador, GeneralProfile.VIEWER)


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


def _mudanca(
    session: Session,
    project: Project,
    *,
    code: str,
    scope: str | None = None,
    eap_revision: int | None = None,
) -> ChangeRequest:
    change = ChangeRequest(
        project_id=project.id,
        requester_id=project.manager_id,
        code=code,
        title=f"Mudança {code}",
        kind="Escopo",
        origin="Cliente",
        priority="Normal",
        request_date=date(2026, 9, 1),
        description="Descrição da mudança de teste.",
        situation="Aprovada",
        eap_revision=eap_revision,
    )
    session.add(change)
    session.flush()
    if scope is not None:
        session.add(
            ChangeImpact(
                change_id=change.id,
                analyst_id=project.manager_id,
                analysis_date=date(2026, 9, 10),
                cost_cents=0,
                term_days=0,
                scope=scope,
                quality="Sem impacto",
                risks="Sem impacto",
                safety="Sem impacto",
                contract="Sem impacto",
                affects_contract_milestone=False,
            )
        )
        session.flush()
    return change


def _montar_itens(
    session: Session, projeto: Project, unidade: Unit, responsavel: Person
) -> dict[str, EapItem]:
    obra = _item(session, projeto, "1", "Obra civil")
    montagem = _item(session, projeto, "2", "Montagem")
    fundacoes = _item(session, projeto, "1.1", "Fundações", obra)
    equipamentos = _item(session, projeto, "2.1", "Equipamentos", montagem)
    itens = {"1": obra, "2": montagem, "1.1": fundacoes, "2.1": equipamentos}
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
        executed=D("40"),
        unit_id=unidade.id,
        owner_id=responsavel.id,
    )
    itens["1.1.2"] = _item(
        session,
        projeto,
        "1.1.2",
        "Blocos",
        fundacoes,
        kind="Trabalho",
        criterion="Percentual estimado",
        weight=D("10"),
        predicted=D("2.1"),
        start=date(2026, 8, 1),
        finish=date(2026, 12, 1),
        estimated_pct=D("0"),
        owner_id=responsavel.id,
    )
    itens["1.1.3"] = _item(
        session,
        projeto,
        "1.1.3",
        "Partida assistida",
        fundacoes,
        kind="Planejamento",
        weight=D("5"),
        predicted=D("42.5"),
        start=date(2026, 6, 1),
        finish=date(2027, 2, 1),
        owner_id=responsavel.id,
    )
    itens["2.1.1"] = _item(
        session,
        projeto,
        "2.1.1",
        "Estruturas metálicas",
        equipamentos,
        kind="Trabalho",
        criterion="Etapas",
        model="engenharia",
        weight=D("30"),
        predicted=D("60"),
        start=date(2026, 3, 1),
        finish=date(2026, 9, 10),
        owner_id=responsavel.id,
    )
    itens["2.1.2"] = _item(
        session,
        projeto,
        "2.1.2",
        "Comissionamento",
        equipamentos,
        kind="Trabalho",
        criterion="Marco 0/100",
        weight=D("35"),
        predicted=D("95"),
        start=date(2026, 4, 1),
        finish=date(2026, 9, 1),
        state="Concluído",
        owner_id=responsavel.id,
    )
    for order, (nome, peso, pct) in enumerate(
        (
            ("Elaboração", D("40"), D("100")),
            ("Emissão para comentários", D("30"), D("50")),
            ("Emissão para construção", D("30"), D("0")),
        ),
        start=1,
    ):
        session.add(
            EapItemStep(item_id=itens["2.1.1"].id, order=order, name=nome, weight=peso, pct=pct)
        )
    session.flush()
    return itens


@pytest.fixture
def cenario_revisao(sessao: Session) -> CenarioRevisao:
    """A EAP de revisão do projeto 1, com a Rev 0 e a SM aprovada pendente de incorporação."""
    projeto = criar_projeto(sessao, codigo="TN-REV-001", nome="Fábrica de revisão")
    unidade = Unit(kind="medida", code="un", name="Unidade")
    sessao.add(unidade)
    membro = criar_colaborador(
        sessao, email="membro-revisao@example.invalid", nome="Maria Medição", perfil="Membro"
    )
    gestor = criar_colaborador(
        sessao, email="gestor-revisao@example.invalid", nome="Gustavo Gestor", perfil="Gestor"
    )
    visualizador = criar_colaborador(
        sessao, email="visualizador-revisao@example.invalid", perfil="Visualizador"
    )
    sessao.flush()
    responsavel = sessao.get(Person, membro.person_id)
    assert responsavel is not None
    itens = _montar_itens(sessao, projeto, unidade, responsavel)
    revisao_zero = EapRevision(
        project_id=projeto.id,
        approved_by_id=responsavel.id,
        revision=0,
        revision_date=date(2026, 1, 5),
        alteration="Linha de base",
        justification="Linha de base aprovada no gate de investimento.",
    )
    sessao.add(revisao_zero)
    sessao.flush()
    sm = _mudanca(sessao, projeto, code=SM, scope="Inclusão do pacote de tubulação")
    return CenarioRevisao(
        session=sessao,
        projeto=projeto,
        responsavel=responsavel,
        unidade=unidade,
        membro=membro,
        gestor=gestor,
        visualizador=visualizador,
        itens=itens,
        sm=sm,
        revisao_zero=revisao_zero,
    )


def _estados(cenario: CenarioRevisao) -> dict[str, validation.PackageState]:
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


def _modelos() -> tuple[dict[str, object], ...]:
    return tuple(configuracoes.INITIAL_PARAMETERS["eap"]["modelosEtapas"])


def _novo(cenario: CenarioRevisao, **alteracoes: str) -> validation.NewPackageData:
    raw = {
        "recurso": validation.REVISION,
        "sm": SM,
        "tipo": "Trabalho",
        "pai": "2.1",
        "descricao": "Pipe rack PR-03",
        "criterio": "Unidades",
        "unidade": "un",
        "quantidade": "120",
        "peso": "3.00",
        "inicio": "2026-09-01",
        "termino": "2026-12-01",
        "responsavel": str(cenario.responsavel.id),
        "justificativa": JUSTIFICATIVA,
    }
    raw.update(alteracoes)
    return validation.parse_package_form(
        raw,
        packages=_estados(cenario),
        limits=LIMITES,
        stage_models=_modelos(),
    )


def _ajuste(cenario: CenarioRevisao, **alteracoes: str) -> validation.RevisionAdjustment:
    raw = {
        "sm": SM,
        "pacote": "1.1.1",
        "peso": "8.00",
        "justificativa": JUSTIFICATIVA,
    }
    raw.update(alteracoes)
    return validation.parse_revision_form(
        raw, packages=_estados(cenario), limits=LIMITES
    ).adjustment


def _revisar(
    cenario: CenarioRevisao,
    *,
    ajustes: tuple[validation.RevisionAdjustment, ...] = (),
    novos: tuple[validation.NewPackageData, ...] = (),
    usuario: User | None = None,
    escopo: Scope | None = None,
) -> service.RevisionResult:
    return service.create_revision(
        cenario.session,
        user=usuario or cenario.usuario_gestor,
        scope=escopo or cenario.escopo,
        request=service.RevisionRequest(
            change_code=cenario.sm.code,
            justification=JUSTIFICATIVA,
            adjustments=ajustes,
            new_packages=novos,
        ),
        reference_date=HOJE,
    )


def _revisar_sm(
    cenario: CenarioRevisao, *, change_code: str, ajuste: validation.RevisionAdjustment
) -> service.RevisionResult:
    return service.create_revision(
        cenario.session,
        user=cenario.usuario_gestor,
        scope=cenario.escopo,
        request=service.RevisionRequest(
            change_code=change_code,
            justification=JUSTIFICATIVA,
            adjustments=(ajuste,),
        ),
        reference_date=HOJE,
    )


def _visao(cenario: CenarioRevisao) -> service.EapOverview:
    return service.eap_overview(
        cenario.session, user=cenario.usuario_membro, scope=cenario.escopo, reference_date=HOJE
    )


# ── A revisão ─────────────────────────────────────────────────────────────


def test_revisao_ajusta_peso_quantidade_e_termino_e_reescala_fechando_cem(
    cenario_revisao: CenarioRevisao,
) -> None:
    ajuste = _ajuste(cenario_revisao, quantidade="150", termino="2026-09-30")

    resultado = _revisar(cenario_revisao, ajustes=(ajuste,))

    assert resultado.revision == 1
    assert resultado.change_code == SM
    assert resultado.adjusted_codes == ("1.1.1",)
    assert resultado.new_codes == ()
    assert resultado.alteration == "Pacote 1.1.1 ajustado; demais pesos reescalados"
    sessao = cenario_revisao.session
    ajustado = sessao.get(EapItem, cenario_revisao.itens["1.1.1"].id)
    assert ajustado is not None
    assert (ajustado.weight, ajustado.quantity, ajustado.finish) == (
        D("8.00"),
        D("150"),
        date(2026, 9, 30),
    )
    for code, peso in PESOS_REESCALADOS.items():
        item = sessao.get(EapItem, cenario_revisao.itens[code].id)
        assert item is not None
        assert item.weight == peso
    pesos = [
        item.weight
        for item in cenario_revisao.itens.values()
        if item.level == service.LEVEL_PACKAGE
    ]
    assert sum(pesos) == D("100.00")


def test_revisao_inclui_pacote_novo_com_codigo_da_subarea_e_previsto_linear(
    cenario_revisao: CenarioRevisao,
) -> None:
    dado = _novo(
        cenario_revisao,
        criterio="Etapas",
        modelo="engenharia",
        unidade="",
        quantidade="",
        peso="3.00",
    )

    resultado = _revisar(cenario_revisao, novos=(dado,))

    assert resultado.new_codes == ("2.1.3",)
    assert resultado.alteration == "Pacote 2.1.3 incluído; demais pesos reescalados"
    sessao = cenario_revisao.session
    novo = sessao.scalars(
        select(EapItem).where(
            EapItem.project_id == cenario_revisao.projeto.id, EapItem.code == "2.1.3"
        )
    ).one()
    assert (novo.kind, novo.criterion, novo.model, novo.weight) == (
        "Trabalho",
        "Etapas",
        "engenharia",
        D("3.00"),
    )
    assert novo.predicted == D("26.4")
    assert novo.parent_id == cenario_revisao.itens["2.1"].id
    passos = sessao.scalars(
        select(EapItemStep).where(EapItemStep.item_id == novo.id).order_by(EapItemStep.order)
    ).all()
    assert [(passo.name, passo.weight, passo.pct) for passo in passos] == [
        ("Elaboração", D(40), D(0)),
        ("Emissão para comentários", D(30), D(0)),
        ("Emissão para construção", D(30), D(0)),
    ]
    pesos = [
        sessao.get(EapItem, item.id).weight
        for item in cenario_revisao.itens.values()
        if item.level == service.LEVEL_PACKAGE
    ]
    assert sum(pesos) + novo.weight == D("100.00")


def test_revisao_cria_o_pacote_novo_com_o_codigo_informado(
    cenario_revisao: CenarioRevisao,
) -> None:
    dado = replace(_novo(cenario_revisao), code="2.1.9")

    resultado = _revisar(cenario_revisao, novos=(dado,))

    assert resultado.new_codes == ("2.1.9",)
    novo = cenario_revisao.session.scalars(
        select(EapItem).where(
            EapItem.project_id == cenario_revisao.projeto.id, EapItem.code == "2.1.9"
        )
    ).one()
    assert (novo.kind, novo.criterion, novo.weight, novo.parent_id) == (
        "Trabalho",
        "Unidades",
        D("3.00"),
        cenario_revisao.itens["2.1"].id,
    )
    assert (
        cenario_revisao.session.scalars(
            select(EapItem).where(
                EapItem.project_id == cenario_revisao.projeto.id, EapItem.code == "2.1.3"
            )
        ).one_or_none()
        is None
    )


def test_revisao_recusa_o_codigo_informado_repetido_ou_fora_da_subarea(
    cenario_revisao: CenarioRevisao,
) -> None:
    dado = _novo(cenario_revisao)
    with pytest.raises(InvalidDataError) as repetido:
        _revisar(cenario_revisao, novos=(replace(dado, code="2.1.1"),))
    assert validation.REVISION_CODE_DUPLICATE_MESSAGE.format(code="2.1.1") in str(repetido.value)

    with pytest.raises(InvalidDataError) as malformado:
        _revisar(cenario_revisao, novos=(replace(dado, code="2.1"),))
    assert validation.REVISION_CODE_LEVELS_MESSAGE in str(malformado.value)

    with pytest.raises(InvalidDataError) as sem_subarea:
        _revisar(cenario_revisao, novos=(replace(dado, code="9.9.9"),))
    assert validation.REVISION_CODE_PARENT_MESSAGE.format(code="9.9") in str(sem_subarea.value)

    assert (
        cenario_revisao.session.scalars(
            select(EapItem).where(
                EapItem.project_id == cenario_revisao.projeto.id,
                EapItem.code.in_(("2.1.9", "9.9.9")),
            )
        ).all()
        == []
    )


def test_revisao_congela_o_peso_de_todos_os_pacotes_de_nivel_tres(
    cenario_revisao: CenarioRevisao,
) -> None:
    resultado = _revisar(cenario_revisao, ajustes=(_ajuste(cenario_revisao),))

    sessao = cenario_revisao.session
    revisao = sessao.scalars(
        select(EapRevision).where(
            EapRevision.project_id == cenario_revisao.projeto.id,
            EapRevision.revision == resultado.revision,
        )
    ).one()
    assert revisao.change_id == cenario_revisao.sm.id
    assert revisao.approved_by_id == cenario_revisao.gestor.person_id
    assert revisao.revision_date == HOJE
    congelados = {
        linha.item_id: linha.weight
        for linha in sessao.scalars(
            select(EapRevisionItem).where(EapRevisionItem.revision_id == revisao.id)
        )
    }
    assert len(congelados) == 5
    assert congelados[cenario_revisao.itens["1.1.1"].id] == D("8.00")
    for code, peso in PESOS_REESCALADOS.items():
        assert congelados[cenario_revisao.itens[code].id] == peso


def test_a_sm_incorporada_sai_dos_pendentes_e_a_revisao_entra_na_ficha(
    cenario_revisao: CenarioRevisao,
) -> None:
    antes = _visao(cenario_revisao)
    assert [pendente.code for pendente in antes.pending_changes] == [SM]

    resultado = _revisar(cenario_revisao, ajustes=(_ajuste(cenario_revisao),))

    depois = _visao(cenario_revisao)
    assert depois.pending_changes == ()
    vigente = depois.current_revision
    assert vigente is not None
    assert (vigente.revision, vigente.change_id, vigente.change_code) == (
        resultado.revision,
        cenario_revisao.sm.id,
        SM,
    )
    assert cenario_revisao.sm.eap_revision == resultado.revision


def test_revisao_recusa_sem_gestor_e_no_portfolio(cenario_revisao: CenarioRevisao) -> None:
    with pytest.raises(AccessDeniedError) as sem_gestor:
        _revisar(
            cenario_revisao,
            ajustes=(_ajuste(cenario_revisao),),
            usuario=cenario_revisao.usuario_membro,
        )
    assert "Gestor" in str(sem_gestor.value)

    with pytest.raises(AccessDeniedError):
        _revisar(cenario_revisao, ajustes=(_ajuste(cenario_revisao),), escopo=PORTFOLIO)


def test_revisao_recusa_sm_ausente_sem_impacto_ou_incorporada(
    cenario_revisao: CenarioRevisao,
) -> None:
    ajuste = _ajuste(cenario_revisao)
    with pytest.raises(InvalidDataError) as ausente:
        _revisar_sm(cenario_revisao, change_code="SM-NAO-EXISTE", ajuste=ajuste)
    assert "SM aprovada com impacto em escopo" in str(ausente.value)

    sem_impacto = _mudanca(
        cenario_revisao.session,
        cenario_revisao.projeto,
        code="SM-TN-2026-0102",
        scope="Sem impacto",
    )
    with pytest.raises(InvalidDataError):
        _revisar_sm(cenario_revisao, change_code=sem_impacto.code, ajuste=ajuste)

    incorporada = _mudanca(
        cenario_revisao.session,
        cenario_revisao.projeto,
        code="SM-TN-2026-0103",
        scope="Impacto já incorporado",
        eap_revision=0,
    )
    with pytest.raises(InvalidDataError):
        _revisar_sm(cenario_revisao, change_code=incorporada.code, ajuste=ajuste)


def test_revisao_recusa_peso_acima_do_maximo_e_soma_fixa_cem(
    cenario_revisao: CenarioRevisao,
) -> None:
    acima = replace(_ajuste(cenario_revisao), weight=D("10.01"))
    with pytest.raises(InvalidDataError) as recusa:
        _revisar(cenario_revisao, ajustes=(acima,))
    assert "máximo" in str(recusa.value)

    sessao = cenario_revisao.session
    configuracoes.seed_initial_parameters(
        sessao, author_id=cenario_revisao.membro.id, effective_from=date(2026, 1, 1)
    )
    valores = dict(configuracoes.INITIAL_PARAMETERS["eap"])
    valores["pesoMaximoPacotePct"] = 100
    configuracoes.save_parameter_group(
        sessao,
        author_id=cenario_revisao.membro.id,
        group="eap",
        values=valores,
        effective_from=HOJE,
        justification="Peso máximo flexível para o teste da soma fixa.",
    )
    limite = validation.RevisionLimits(max_package_weight=D(100), max_estimated_weight=D(5))
    inteiro = validation.parse_revision_form(
        {"sm": SM, "pacote": "1.1.1", "peso": "100", "justificativa": JUSTIFICATIVA},
        packages=_estados(cenario_revisao),
        limits=limite,
    )
    with pytest.raises(InvalidDataError) as soma:
        _revisar(cenario_revisao, ajustes=(inteiro.adjustment,))
    assert "somam 100%" in str(soma.value)


# ── O desdobramento ───────────────────────────────────────────────────────


def _desdobrar(
    cenario: CenarioRevisao, dado: validation.NewPackageData, usuario: User | None = None
) -> service.BreakdownResult:
    return service.breakdown_package(
        cenario.session,
        user=usuario or cenario.usuario_membro,
        scope=cenario.escopo,
        request=service.BreakdownRequest(package=dado),
        reference_date=HOJE,
    )


def test_desdobramento_mantem_o_total_e_encerra_a_origem(
    cenario_revisao: CenarioRevisao,
) -> None:
    antes = _visao(cenario_revisao)
    dado = _novo(
        cenario_revisao,
        recurso=validation.BREAKDOWN,
        sm="",
        origem="1.1.3",
        pai="1.1",
        criterio="Percentual estimado",
        unidade="",
        quantidade="",
        peso="5.00",
        inicio="2026-10-01",
        termino="2027-01-29",
    )

    resultado = _desdobrar(cenario_revisao, dado)

    assert (resultado.code, resultado.source_code, resultado.source_closed) == (
        "1.1.4",
        "1.1.3",
        True,
    )
    depois = _visao(cenario_revisao)
    assert depois.root.weight == antes.root.weight == D("100.00")
    assert depois.root.predicted == antes.root.predicted
    codigos = [node.code for node in depois.nodes]
    assert "1.1.3" not in codigos
    assert "1.1.4" in codigos
    origem = cenario_revisao.session.get(EapItem, cenario_revisao.itens["1.1.3"].id)
    assert origem is not None
    assert origem.weight == D("0")
    novo = cenario_revisao.session.scalars(
        select(EapItem).where(
            EapItem.project_id == cenario_revisao.projeto.id, EapItem.code == "1.1.4"
        )
    ).one()
    assert novo.predicted == D("42.5")
    linhas = depois.breakdowns
    assert [
        (
            linha.source_code,
            linha.target_code,
            linha.weight,
            linha.source_closed,
            linha.justification,
        )
        for linha in linhas
    ] == [("1.1.3", "1.1.4", D("5.00"), True, JUSTIFICATIVA)]
    gravado = cenario_revisao.session.scalars(
        select(EapBreakdown).where(EapBreakdown.project_id == cenario_revisao.projeto.id)
    ).one()
    assert (gravado.revision, gravado.applied_on, gravado.by_id) == (
        0,
        HOJE,
        cenario_revisao.membro.person_id,
    )


def test_desdobramento_acima_do_peso_da_origem_e_recusado(
    cenario_revisao: CenarioRevisao,
) -> None:
    dado = _novo(
        cenario_revisao,
        recurso=validation.BREAKDOWN,
        sm="",
        origem="1.1.3",
        pai="1.1",
        criterio="Percentual estimado",
        unidade="",
        quantidade="",
        peso="5.00",
        inicio="2026-10-01",
        termino="2027-01-29",
    )

    with pytest.raises(InvalidDataError) as recusa:
        _desdobrar(cenario_revisao, replace(dado, weight=D("5.01")))

    assert "1.1.3" in str(recusa.value)
    origem = cenario_revisao.session.get(EapItem, cenario_revisao.itens["1.1.3"].id)
    assert origem is not None
    assert origem.weight == D("5.00")
