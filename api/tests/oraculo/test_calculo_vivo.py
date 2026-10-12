"""O cálculo vivo (ISSUE-089, D6): a data de hoje movendo o cenário e a medição movendo o SPI.

A demonstração convertida é o cenário do protótipo ancorado em 25/09/2026; a leitura
com a data de hoje do relógio da plataforma (``calendario.today()``, fuso
``America/Sao_Paulo``) é a do app, e os números andam com o tempo: as ações que
venceram depois da âncora e os dias sem afastamento desde o início do projeto. (A
carga de demonstração desloca as datas para hoje junto com a referência; a
translação exata preserva esses dois números, e o deslocamento da carga já tem
teste próprio em ``tests/plataforma``.)

O SPI de custo é lido na fachada do Financeiro e, numa medição nova registrada num
pacote da EAP pela fachada do Planejamento, na mesma transação do teste, a leitura
seguinte já vem diferente — sem nenhum passo de recálculo, porque o indicador é
calculado a cada leitura.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.carga import run_demonstration
from src.carga.plataforma import ADMIN_EMAIL
from src.core import calendario
from src.core.auth import _user_of
from src.core.rbac import User
from src.core.scope import Scope
from src.modulos.central_acoes import service as central_acoes
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.models import Project
from src.modulos.financeiro import service as financeiro
from src.modulos.hse import painel_service
from src.modulos.planejamento import service as planejamento
from src.modulos.planejamento.models import EapItem
from tests.oraculo import ORACLE_DATE

D = Decimal
PROJECT_CODE = "TN-2026-014"
LEVEL_PACKAGE = 3
ANCHOR_OVERDUE_ACTIONS = 8
ANCHOR_DAYS_WITHOUT_LEAVE = 263
ANCHOR_SPI = D("0.94")


def _project(session: Session) -> Project:
    return session.scalars(select(Project).where(Project.code == PROJECT_CODE)).one()


def _scope(session: Session) -> Scope:
    return Scope(project_id=_project(session).id, source="url")


def _admin(session: Session) -> User:
    access = configuracoes.find_access_by_email(session, ADMIN_EMAIL)
    assert access is not None, "admin da demonstracao"
    return _user_of(access)


def _manager(session: Session) -> User:
    access = next(
        item
        for item in configuracoes.list_active_access(session)
        if item.general_profile == "Gestor"
    )
    return _user_of(access)


def _overdue_actions(session: Session, reference: date) -> int:
    counts = central_acoes.count_by_status(
        session,
        user=_admin(session),
        scope=_scope(session),
        reference_date=reference,
    )
    return counts.overdue


def _days_without_leave(session: Session, reference: date) -> int:
    panel = painel_service.panel(
        session,
        user=_manager(session),
        scope=_scope(session),
        reference_date=reference,
        month=None,
        pyramid_kind=None,
    )
    indicators = panel.accumulated_indicators
    assert indicators is not None and indicators.days_without_leave is not None
    return indicators.days_without_leave


def _spi(session: Session, reference: date) -> Decimal:
    view = financeiro.cost_kpis_overview(session, scope=_scope(session), reference_date=reference)
    assert view.indicators is not None
    return view.indicators.spi


def test_a_leitura_com_a_data_de_hoje_difere_da_ancora(db_session: Session) -> None:
    today = calendario.today()
    assert today > ORACLE_DATE, "o relogio da plataforma ja passou da ancora do prototipo"
    run_demonstration(db_session, reference_date=ORACLE_DATE)

    assert _overdue_actions(db_session, ORACLE_DATE) == ANCHOR_OVERDUE_ACTIONS
    assert _days_without_leave(db_session, ORACLE_DATE) == ANCHOR_DAYS_WITHOUT_LEAVE

    assert _overdue_actions(db_session, today) != ANCHOR_OVERDUE_ACTIONS, (
        "as acoes vencidas depois da ancora aparecem na leitura de hoje"
    )
    assert _days_without_leave(db_session, today) != ANCHOR_DAYS_WITHOUT_LEAVE, (
        "os dias sem afastamento contam da data de hoje"
    )


def test_a_medicao_nova_muda_o_spi_sem_recalculo(db_session: Session) -> None:
    run_demonstration(db_session, reference_date=ORACLE_DATE)
    project = _project(db_session)

    before = _spi(db_session, ORACLE_DATE)
    assert before == ANCHOR_SPI, "o SPI de custo do corte na ancora"

    package = db_session.scalars(
        select(EapItem)
        .where(
            EapItem.project_id == project.id,
            EapItem.level == LEVEL_PACKAGE,
            EapItem.kind == "Trabalho",
            EapItem.criterion == "Unidades",
            EapItem.executed < EapItem.quantity,
        )
        .order_by(EapItem.weight.desc(), EapItem.code)
    ).first()
    assert package is not None, "um pacote de trabalho com quantidade a medir"

    progress = planejamento.register_progress(
        db_session,
        user=_admin(db_session),
        scope=_scope(db_session),
        item_id=package.id,
        form={
            "versao": str(package.version),
            "data": ORACLE_DATE.isoformat(),
            "executado": str((package.executed + package.quantity) / 2),
            "obs": "Medição viva do teste do oráculo",
        },
        reference_date=ORACLE_DATE,
    )
    assert progress.to_pct > progress.from_pct

    after = _spi(db_session, ORACLE_DATE)
    assert after != before, "a leitura seguinte do SPI ja vem com a medicao nova"
    assert after > before, "o avanço novo sobe o valor agregado"
