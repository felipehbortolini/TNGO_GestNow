"""Fachada da medição do avanço (ISSUE-037): registrar, estornar e importar.

O cenário tem um pacote de trabalho de cada critério (Unidades, Marco 0/100, Marco 50/50,
Etapas e Percentual estimado), o pacote de planejamento, o projeto vizinho e uma pessoa de cada
perfil. O real sai das entradas gravadas do critério; o acumulado não regride, o estorno exige
Gestor e justificativa, e a importação recusa cada linha com o motivo, sem estorno.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.errors import AccessDeniedError, InvalidDataError, VersionConflictError
from src.core.rbac import Bond, GeneralProfile, User
from src.core.scope import Scope
from src.modulos.configuracoes.models import Collaborator, Project, Unit
from src.modulos.planejamento import calculations, service, validation
from src.modulos.planejamento.models import EapItem, EapItemStep, EapMeasurement
from tests.apoio_6wla import HOJE
from tests.identidades import criar_colaborador, criar_projeto

D = Decimal
PORTFOLIO = Scope(project_id=None, source="padrao")


@dataclass(frozen=True)
class CenarioMedicao:
    """O projeto com um pacote de cada critério, o projeto vizinho e a pessoa de cada perfil."""

    session: Session
    projeto: Project
    outro: Project
    unidade: Unit
    membro: Collaborator
    gestor: Collaborator
    visualizador: Collaborator
    itens: dict[str, EapItem]
    item_outro: EapItem

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


def _montar_pacotes(
    session: Session, projeto: Project, unidade: Unit, autor: Collaborator
) -> dict[str, EapItem]:
    area = _item(session, projeto, "1", "Obra civil")
    sub = _item(session, projeto, "1.1", "Fundações", area)
    itens = {"1": area, "1.1": sub}
    itens["1.1.1"] = _item(
        session,
        projeto,
        "1.1.1",
        "Estacas",
        sub,
        kind="Trabalho",
        criterion="Unidades",
        weight=D("20"),
        predicted=D("92"),
        start=date(2026, 5, 2),
        finish=date(2026, 8, 30),
        quantity=D("100"),
        executed=D("90"),
        unit_id=unidade.id,
    )
    itens["1.1.2"] = _item(
        session,
        projeto,
        "1.1.2",
        "Blocos",
        sub,
        kind="Trabalho",
        criterion="Marco 0/100",
        weight=D("10"),
        predicted=D("2.1"),
        start=date(2026, 8, 1),
        finish=date(2026, 12, 1),
        state="Não iniciado",
    )
    itens["1.1.3"] = _item(
        session,
        projeto,
        "1.1.3",
        "Alinhamento",
        sub,
        kind="Trabalho",
        criterion="Marco 50/50",
        weight=D("5"),
        predicted=D("55"),
        start=date(2026, 6, 15),
        finish=date(2026, 12, 20),
        state="Iniciado",
    )
    itens["1.1.4"] = _item(
        session,
        projeto,
        "1.1.4",
        "Estruturas metálicas",
        sub,
        kind="Trabalho",
        criterion="Etapas",
        weight=D("15"),
        predicted=D("60"),
        start=date(2026, 3, 1),
        finish=date(2026, 9, 10),
    )
    itens["1.1.5"] = _item(
        session,
        projeto,
        "1.1.5",
        "Bomba principal",
        sub,
        kind="Trabalho",
        criterion="Percentual estimado",
        weight=D("2"),
        predicted=D("25"),
        estimated_pct=D("20"),
    )
    itens["1.1.6"] = _item(
        session,
        projeto,
        "1.1.6",
        "Comissionamento",
        sub,
        kind="Trabalho",
        criterion="Percentual estimado",
        weight=D("6"),
        predicted=D("0"),
        estimated_pct=D("0"),
    )
    itens["1.1.7"] = _item(
        session,
        projeto,
        "1.1.7",
        "Partida assistida",
        sub,
        kind="Planejamento",
        weight=D("3"),
        predicted=D("0"),
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
            EapItemStep(item_id=itens["1.1.4"].id, order=order, name=nome, weight=peso, pct=pct)
        )
    session.add(
        EapMeasurement(
            item_id=itens["1.1.1"].id,
            author_id=autor.person_id,
            measured_on=date(2026, 8, 10),
            from_pct=D("0"),
            to_pct=D("90"),
            note="Carga inicial",
        )
    )
    session.flush()
    return itens


@pytest.fixture
def cenario_medicao(sessao: Session) -> CenarioMedicao:
    """A EAP de medição do projeto 1 e o pacote do projeto 2, na transação do teste."""
    projeto = criar_projeto(sessao, codigo="TN-MED-001", nome="Fábrica de medição")
    outro = criar_projeto(sessao, codigo="TN-MED-002", nome="Caldeira vizinha")
    unidade = Unit(kind="medida", code="m", name="Metro")
    sessao.add(unidade)
    membro = criar_colaborador(
        sessao, email="membro-medicao@example.invalid", nome="Maria Medição", perfil="Membro"
    )
    gestor = criar_colaborador(
        sessao, email="gestor-medicao@example.invalid", nome="Gustavo Gestor", perfil="Gestor"
    )
    visualizador = criar_colaborador(
        sessao, email="visualizador-medicao@example.invalid", perfil="Visualizador"
    )
    sessao.flush()
    itens = _montar_pacotes(sessao, projeto, unidade, membro)
    item_outro = _item(
        sessao,
        outro,
        "1.1.1",
        "Fundação da caldeira",
        kind="Trabalho",
        criterion="Unidades",
        weight=D("50"),
        quantity=D("10"),
        executed=D("2"),
    )
    return CenarioMedicao(
        session=sessao,
        projeto=projeto,
        outro=outro,
        unidade=unidade,
        membro=membro,
        gestor=gestor,
        visualizador=visualizador,
        itens=itens,
        item_outro=item_outro,
    )


def _form(item: EapItem, **campos: str) -> dict[str, str]:
    return {"versao": str(item.version), **campos}


def _registrar(
    cenario: CenarioMedicao,
    item: EapItem,
    *,
    user: User | None = None,
    **campos: str,
) -> service.ProgressView:
    return service.register_progress(
        cenario.session,
        user=user or cenario.usuario_membro,
        scope=cenario.escopo,
        item_id=item.id,
        form=_form(item, **campos),
        reference_date=HOJE,
    )


def _medicoes(session: Session, item: EapItem) -> list[EapMeasurement]:
    return list(
        session.scalars(
            select(EapMeasurement)
            .where(EapMeasurement.item_id == item.id)
            .order_by(EapMeasurement.measured_on, EapMeasurement.id)
        )
    )


def _etapas(session: Session, item: EapItem) -> list[EapItemStep]:
    return list(
        session.scalars(
            select(EapItemStep)
            .where(EapItemStep.item_id == item.id)
            .order_by(EapItemStep.order, EapItemStep.id)
        )
    )


def _no_do_dicionario(cenario: CenarioMedicao, code: str) -> service.EapNode:
    visao = service.eap_overview(
        cenario.session,
        user=cenario.usuario_membro,
        scope=cenario.escopo,
        reference_date=HOJE,
    )
    return next(node for node in visao.nodes if node.code == code)


# ── Registrar avanço, por critério ────────────────────────────────────────


def test_registrar_por_unidades_grava_a_medicao_e_o_item(cenario_medicao: CenarioMedicao) -> None:
    item = cenario_medicao.itens["1.1.1"]
    versao = item.version

    visao = _registrar(
        cenario_medicao, item, data="2026-09-20", executado="95", obs="Boletim de setembro"
    )

    medicao = _medicoes(cenario_medicao.session, item)[-1]
    assert (visao.code, visao.from_pct, visao.to_pct, visao.is_reversal) == (
        "1.1.1",
        D("90.00"),
        D("95.00"),
        False,
    )
    assert visao.item is item
    assert item.executed == D("95")
    assert item.version == versao + 1
    assert (
        medicao.measured_on,
        medicao.from_pct,
        medicao.to_pct,
        medicao.author_id,
        medicao.note,
    ) == (
        date(2026, 9, 20),
        D("90.00"),
        D("95.00"),
        cenario_medicao.membro.person_id,
        "Boletim de setembro",
    )


def test_registrar_por_etapas_grava_o_percentual_de_cada_etapa(
    cenario_medicao: CenarioMedicao,
) -> None:
    item = cenario_medicao.itens["1.1.4"]

    visao = _registrar(
        cenario_medicao,
        item,
        data="2026-09-20",
        etapa0="100",
        etapa1="100",
        etapa2="50",
        obs="Relatório de campo",
    )

    assert (visao.from_pct, visao.to_pct) == (D("55.00"), D("85.00"))
    assert [etapa.pct for etapa in _etapas(cenario_medicao.session, item)] == [
        D(100),
        D(100),
        D(50),
    ]
    assert _medicoes(cenario_medicao.session, item)[-1].note == "Relatório de campo"


def test_registrar_por_marco_atualiza_a_situacao_e_o_real(cenario_medicao: CenarioMedicao) -> None:
    zero_a_cem = cenario_medicao.itens["1.1.2"]

    visao = _registrar(cenario_medicao, zero_a_cem, data="2026-09-20", estado="Concluído")

    assert (visao.from_pct, visao.to_pct) == (D("0.00"), D("100.00"))
    assert zero_a_cem.state == "Concluído"

    meio_a_cem = cenario_medicao.itens["1.1.3"]

    visao = _registrar(cenario_medicao, meio_a_cem, data="2026-09-20", estado="Concluído")

    assert (visao.from_pct, visao.to_pct) == (D("50.00"), D("100.00"))
    assert meio_a_cem.state == "Concluído"


def test_registrar_por_percentual_estimado_atualiza_o_real(
    cenario_medicao: CenarioMedicao,
) -> None:
    item = cenario_medicao.itens["1.1.5"]

    visao = _registrar(
        cenario_medicao, item, data="2026-09-20", estimadoPct="60", obs="Avanço estimado em campo"
    )

    assert (visao.from_pct, visao.to_pct) == (D("20.00"), D("60.00"))
    assert item.estimated_pct == D("60")


def test_estimado_acima_do_peso_do_parametro_e_recusado(cenario_medicao: CenarioMedicao) -> None:
    item = cenario_medicao.itens["1.1.6"]

    with pytest.raises(InvalidDataError) as recusa:
        _registrar(cenario_medicao, item, data="2026-09-20", estimadoPct="50")

    assert recusa.value.detail == {
        "estimadoPct": validation.ESTIMATED_WEIGHT_MESSAGE.format(maximum="5")
    }
    assert item.estimated_pct == D("0")


# ── Estorno e limites ─────────────────────────────────────────────────────


def test_regressao_sem_gestor_e_403(cenario_medicao: CenarioMedicao) -> None:
    item = cenario_medicao.itens["1.1.1"]
    antes = _medicoes(cenario_medicao.session, item)

    with pytest.raises(AccessDeniedError) as recusa:
        _registrar(cenario_medicao, item, data="2026-09-20", executado="50")

    assert str(recusa.value) == validation.REVERSAL_MANAGER_MESSAGE
    assert item.executed == D("90")
    assert _medicoes(cenario_medicao.session, item) == antes


def test_regressao_com_gestor_sem_justificativa_e_422(cenario_medicao: CenarioMedicao) -> None:
    item = cenario_medicao.itens["1.1.1"]

    with pytest.raises(InvalidDataError) as recusa:
        _registrar(
            cenario_medicao,
            item,
            user=cenario_medicao.usuario_gestor,
            data="2026-09-20",
            executado="50",
            justificativa="curta",
        )

    assert recusa.value.detail == {
        "justificativa": validation.REVERSAL_JUSTIFICATION_MESSAGE.format(
            from_pct="90", to_pct="50"
        )
    }
    assert item.executed == D("90")


def test_estorno_com_gestor_e_justificativa_grava_a_medicao(
    cenario_medicao: CenarioMedicao,
) -> None:
    item = cenario_medicao.itens["1.1.1"]

    visao = _registrar(
        cenario_medicao,
        item,
        user=cenario_medicao.usuario_gestor,
        data="2026-09-20",
        executado="50",
        justificativa="Retrabalho das estacas refeito",
    )

    medicao = _medicoes(cenario_medicao.session, item)[-1]
    assert visao.is_reversal
    assert (medicao.from_pct, medicao.to_pct, medicao.note) == (
        D("90.00"),
        D("50.00"),
        "Retrabalho das estacas refeito",
    )
    assert item.executed == D("50")

    no = _no_do_dicionario(cenario_medicao, "1.1.1")
    assert no.actual == D("50.00")
    assert no.measurements[-1].is_reversal


def test_data_futura_e_recusada(cenario_medicao: CenarioMedicao) -> None:
    item = cenario_medicao.itens["1.1.1"]

    with pytest.raises(InvalidDataError) as recusa:
        _registrar(cenario_medicao, item, data="2026-09-26", executado="95")

    assert recusa.value.detail == {"data": validation.MEASUREMENT_DATE_FUTURE_MESSAGE}


def test_executado_acima_da_linha_de_base_e_recusado_com_a_mensagem(
    cenario_medicao: CenarioMedicao,
) -> None:
    item = cenario_medicao.itens["1.1.1"]

    with pytest.raises(InvalidDataError) as recusa:
        _registrar(cenario_medicao, item, data="2026-09-20", executado="150")

    assert recusa.value.detail == {
        "executado": validation.EXECUTED_OVER_QUANTITY_MESSAGE.format(quantity="100", unit="m")
    }


def test_o_registro_recusa_portfolio_planejamento_outro_projeto_e_perfil(
    cenario_medicao: CenarioMedicao,
) -> None:
    item = cenario_medicao.itens["1.1.1"]
    formulario = _form(item, data="2026-09-20", executado="95")

    with pytest.raises(AccessDeniedError):
        service.register_progress(
            cenario_medicao.session,
            user=cenario_medicao.usuario_membro,
            scope=PORTFOLIO,
            item_id=item.id,
            form=formulario,
            reference_date=HOJE,
        )
    with pytest.raises(InvalidDataError):
        _registrar(cenario_medicao, cenario_medicao.itens["1.1.7"], data="2026-09-20")
    with pytest.raises(AccessDeniedError):
        _registrar(cenario_medicao, cenario_medicao.item_outro, data="2026-09-20", executado="3")
    with pytest.raises(InvalidDataError):
        _registrar(cenario_medicao, cenario_medicao.itens["1.1"], data="2026-09-20")
    with pytest.raises(AccessDeniedError):
        _registrar(
            cenario_medicao,
            item,
            user=cenario_medicao.usuario_visualizador,
            data="2026-09-20",
            executado="95",
        )


def test_versao_vencida_no_registro_e_conflito(cenario_medicao: CenarioMedicao) -> None:
    item = cenario_medicao.itens["1.1.1"]
    formulario = _form(item, data="2026-09-20", executado="95")
    formulario["versao"] = "999"

    with pytest.raises(VersionConflictError):
        service.register_progress(
            cenario_medicao.session,
            user=cenario_medicao.usuario_membro,
            scope=cenario_medicao.escopo,
            item_id=item.id,
            form=formulario,
            reference_date=HOJE,
        )


# ── Importação do avanço ──────────────────────────────────────────────────


def test_importacao_aplica_validas_recusa_invalidas_e_ignora_sem_mudanca(
    cenario_medicao: CenarioMedicao,
) -> None:
    sessao = cenario_medicao.session

    resultado = service.import_progress(
        sessao,
        user=cenario_medicao.usuario_membro,
        scope=cenario_medicao.escopo,
        rows=(
            validation.ImportRowInput(code="1.1.1", executed=D("95")),
            validation.ImportRowInput(code="1.1.4", percent=D("70")),
            validation.ImportRowInput(code="1.1.5", percent=D("30")),
            validation.ImportRowInput(code="1.1.1", executed=D("95")),
            validation.ImportRowInput(code="9.9.9", percent=D("50")),
            validation.ImportRowInput(code="1.1.7", percent=D("50")),
            validation.ImportRowInput(code="1.1.2", percent=D("50")),
        ),
        measurement_date=HOJE,
        reference_date=HOJE,
    )

    assert resultado.applied == 3
    assert resultado.errors == (
        validation.IMPORT_PACKAGE_NOT_FOUND_MESSAGE.format(code="9.9.9"),
        validation.IMPORT_PLANNING_MESSAGE.format(code="1.1.7"),
        f"1.1.2: {calculations.MILESTONE_0_100_OPTIONS_MESSAGE}",
    )

    medidas = _medicoes(sessao, cenario_medicao.itens["1.1.1"])
    assert len(medidas) == 2
    assert (
        medidas[-1].measured_on,
        medidas[-1].from_pct,
        medidas[-1].to_pct,
        medidas[-1].note,
        medidas[-1].author_id,
    ) == (
        HOJE,
        D("90.00"),
        D("95.00"),
        service.IMPORT_NOTE,
        cenario_medicao.membro.person_id,
    )
    assert cenario_medicao.itens["1.1.1"].executed == D("95")
    assert [etapa.pct for etapa in _etapas(sessao, cenario_medicao.itens["1.1.4"])] == [
        D(100),
        D(100),
        D(0),
    ]
    assert _medicoes(sessao, cenario_medicao.itens["1.1.4"])[-1].to_pct == D("70.00")
    assert cenario_medicao.itens["1.1.5"].estimated_pct == D("30")
    assert _medicoes(sessao, cenario_medicao.itens["1.1.5"])[-1].to_pct == D("30.00")


def test_importacao_recusa_regressao_sem_gravar(cenario_medicao: CenarioMedicao) -> None:
    item = cenario_medicao.itens["1.1.1"]

    resultado = service.import_progress(
        cenario_medicao.session,
        user=cenario_medicao.usuario_membro,
        scope=cenario_medicao.escopo,
        rows=(validation.ImportRowInput(code="1.1.1", executed=D("50")),),
        measurement_date=HOJE,
        reference_date=HOJE,
    )

    assert resultado.applied == 0
    assert resultado.errors == (
        validation.IMPORT_REGRESSION_MESSAGE.format(code="1.1.1", from_pct="90", to_pct="50"),
    )
    assert item.executed == D("90")
    assert len(_medicoes(cenario_medicao.session, item)) == 1


def test_importacao_recusa_data_futura(cenario_medicao: CenarioMedicao) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        service.import_progress(
            cenario_medicao.session,
            user=cenario_medicao.usuario_membro,
            scope=cenario_medicao.escopo,
            rows=(validation.ImportRowInput(code="1.1.1", executed=D("95")),),
            measurement_date=date(2026, 9, 26),
            reference_date=HOJE,
        )

    assert recusa.value.detail == {"data": validation.MEASUREMENT_DATE_FUTURE_MESSAGE}


def test_importacao_recusa_portfolio(cenario_medicao: CenarioMedicao) -> None:
    with pytest.raises(InvalidDataError):
        service.import_progress(
            cenario_medicao.session,
            user=cenario_medicao.usuario_membro,
            scope=PORTFOLIO,
            rows=(validation.ImportRowInput(code="1.1.1", executed=D("95")),),
            measurement_date=HOJE,
            reference_date=HOJE,
        )


# ── Histórico no dicionário ───────────────────────────────────────────────


def test_a_medicao_nova_aparece_no_dicionario_da_arvore(cenario_medicao: CenarioMedicao) -> None:
    item = cenario_medicao.itens["1.1.1"]
    _registrar(cenario_medicao, item, data="2026-09-20", executado="95", obs="Boletim 3")

    no = _no_do_dicionario(cenario_medicao, "1.1.1")

    assert no.actual == D("95.00")
    assert [
        (medicao.from_pct, medicao.to_pct, medicao.author, medicao.note)
        for medicao in no.measurements
    ] == [
        (D("0.00"), D("90.00"), "Maria Medição", "Carga inicial"),
        (D("90.00"), D("95.00"), "Maria Medição", "Boletim 3"),
    ]
    assert not any(medicao.is_reversal for medicao in no.measurements)
