"""Apoio dos testes do diligenciamento: o cenário com um pedido emitido na transação do teste.

O cenário parte do processo de compra (dois projetos, Admin e Visualizador, disciplina, item da
EAC, pacote congelado, fornecedores) e acrescenta um pedido com os seis marcos de fabricação do
cronograma padrão, com folga positiva contra o ROS. ``tornar_critico`` o deixa com folga negativa
para os testes da ação na Central. As identidades de partida deixam cada teste mudar só o que
importa.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from src.core.rbac import User
from src.modulos.configuracoes.models import Company, Discipline, Project
from src.modulos.financeiro.models import EacItem
from src.modulos.suprimentos import calculations
from src.modulos.suprimentos.models import (
    PurchaseOrder,
    PurchaseOrderMilestone,
    PurchasePackage,
)
from tests.apoio_processos import CenarioProcessos, montar_cenario_processos

REFERENCIA = date(2026, 9, 25)
EMISSION = date(2026, 9, 20)
CONTRACTUAL = date(2026, 12, 30)
FORECAST = date(2026, 12, 30)
ROS = date(2027, 2, 15)
CRITICAL_ROS = date(2026, 12, 1)
ORDER_NUMBER = "PED-2026-0001"
ORDER_VALUE_CENTS = 40_000_000


@dataclass(frozen=True)
class CenarioDiligenciamento:
    """O cenário do processo mais o pedido emitido com os seis marcos de fabricação."""

    projeto: Project
    outro: Project
    ana: User
    vitor: User
    disciplina: Discipline
    item: EacItem
    pacote: PurchasePackage
    planejado: PurchasePackage
    fornecedores: tuple[Company, ...]
    bloqueada: Company
    pedido: PurchaseOrder


def montar_cenario_diligenciamento(session: Session) -> CenarioDiligenciamento:
    """Cria o cenário do processo e o pedido do pacote congelado, com os seis marcos."""
    cenario: CenarioProcessos = montar_cenario_processos(session)
    pedido = PurchaseOrder(
        project_id=cenario.projeto.id,
        package_id=cenario.pacote.id,
        company_id=cenario.fornecedores[0].id,
        number=ORDER_NUMBER,
        description=cenario.pacote.scope,
        value_cents=ORDER_VALUE_CENTS,
        lli=False,
        emission=EMISSION,
        contractual_date=CONTRACTUAL,
        forecast=FORECAST,
        ros=ROS,
        version=1,
    )
    session.add(pedido)
    session.flush()
    for position, (name, planned) in enumerate(
        calculations.manufacturing_schedule(EMISSION, CONTRACTUAL), start=1
    ):
        session.add(
            PurchaseOrderMilestone(
                order_id=pedido.id,
                position=position,
                name=name,
                baseline_date=planned,
                forecast_date=planned,
                version=1,
            )
        )
    session.flush()
    return CenarioDiligenciamento(
        projeto=cenario.projeto,
        outro=cenario.outro,
        ana=cenario.ana,
        vitor=cenario.vitor,
        disciplina=cenario.disciplina,
        item=cenario.item,
        pacote=cenario.pacote,
        planejado=cenario.planejado,
        fornecedores=cenario.fornecedores,
        bloqueada=cenario.bloqueada,
        pedido=pedido,
    )


def tornar_critico(cenario: CenarioDiligenciamento, session: Session) -> None:
    """Move o ROS para depois da previsão: o pedido passa a ter folga negativa."""
    cenario.pedido.ros = CRITICAL_ROS
    session.flush()
