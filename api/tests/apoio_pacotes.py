"""Apoio dos testes do plano de compras: o cenário (projetos, EAC, cadastros e um pacote).

O cenário vive na transação do teste: dois projetos, um Admin e um Visualizador, uma disciplina
do cadastro, um item de custo (nível 3) com orçado e comprometido do ERP, um subpacote (nível 2)
que não é item de custo e um pacote congelado (a requisição tem data real) com os sete marcos de
aquisição. As identidades de partida deixam cada teste mudar só o que importa.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.core.rbac import User
from src.modulos.configuracoes.models import Discipline, Project
from src.modulos.financeiro.models import EacItem, ErpCost
from src.modulos.suprimentos.models import PackageMilestone, PurchasePackage
from src.modulos.suprimentos.validation import PackageInput
from tests.apoio_suprimentos import usuario_de
from tests.identidades import criar_colaborador, criar_projeto

REFERENCIA = date(2026, 9, 25)
ANA = "ana.admin@plano.example.invalid"
VITOR = "vitor.visualizador@plano.example.invalid"

ITEM_CODE = "2.1.1"
ITEM_DESCRIPTION = "Compressores de ar"
ITEM_BASE_CENTS = 100_000_000
ITEM_COMMITTED_CENTS = 40_000_000
SUBPACKAGE_CODE = "1.2"

PACKAGE_CODE = "PC-01"
PACKAGE_SCOPE = "Compressores de ar"
PACKAGE_ESTIMATE_CENTS = 50_000_000
PACKAGE_ROS = date(2027, 3, 31)
PLAN = {
    "requisicao": date(2026, 8, 1),
    "rfx": date(2026, 8, 10),
    "propostas": date(2026, 8, 31),
    "eqTecnica": date(2026, 9, 5),
    "eqComercial": date(2026, 9, 15),
    "adjudicacao": date(2026, 9, 20),
    "pedido": date(2026, 9, 22),
}


@dataclass(frozen=True)
class CenarioPlano:
    """Os dois projetos, as pessoas do teste, a disciplina, os itens da EAC e o pacote."""

    projeto: Project
    outro: Project
    ana: User
    vitor: User
    disciplina: Discipline
    item: EacItem
    subpacote: EacItem
    pacote: PurchasePackage


def montar_cenario_do_plano(session: Session) -> CenarioPlano:
    """Cria projetos, pessoas, disciplina, itens da EAC e o pacote congelado no teste."""
    projeto = criar_projeto(session, codigo="TN-PLA-001", nome="Planta do plano")
    outro = criar_projeto(session, codigo="TN-PLA-002", nome="Área do plano")
    ana = usuario_de(
        session, criar_colaborador(session, email=ANA, nome="Ana Admin", perfil="Admin")
    )
    vitor = usuario_de(
        session,
        criar_colaborador(session, email=VITOR, nome="Vitor Visualizador", perfil="Visualizador"),
    )
    disciplina = Discipline(name="Mecânica de teste")
    session.add(disciplina)
    session.flush()
    item = EacItem(
        project_id=projeto.id,
        code=ITEM_CODE,
        description=ITEM_DESCRIPTION,
        level=3,
        quantity=Decimal(1),
        unit_price_cents=ITEM_BASE_CENTS,
    )
    subpacote = EacItem(
        project_id=projeto.id,
        code=SUBPACKAGE_CODE,
        description="Subpacote de teste",
        level=2,
    )
    session.add_all([item, subpacote])
    session.flush()
    session.add(
        ErpCost(
            project_id=projeto.id,
            item_id=item.id,
            imported_by_id=ana.person_id,
            month=date(2026, 9, 1),
            committed_cents=ITEM_COMMITTED_CENTS,
        )
    )
    session.flush()
    pacote = _pacote_congelado(
        session, projeto=projeto, item=item, buyer_id=ana.person_id, discipline_id=disciplina.id
    )
    return CenarioPlano(
        projeto=projeto,
        outro=outro,
        ana=ana,
        vitor=vitor,
        disciplina=disciplina,
        item=item,
        subpacote=subpacote,
        pacote=pacote,
    )


def _pacote_congelado(
    session: Session, *, projeto: Project, item: EacItem, buyer_id: int, discipline_id: int
) -> PurchasePackage:
    """Um pacote com a requisição real: a LB já congelada, pronto para os testes de mudança."""
    pacote = PurchasePackage(
        project_id=projeto.id,
        eac_item_id=item.id,
        buyer_id=buyer_id,
        discipline_id=discipline_id,
        code=PACKAGE_CODE,
        scope=PACKAGE_SCOPE,
        kind="Equipamento",
        modality="Preço global",
        lli=False,
        estimate_cents=PACKAGE_ESTIMATE_CENTS,
        ros=PACKAGE_ROS,
        emergency=False,
        version=1,
    )
    session.add(pacote)
    session.flush()
    for milestone, plan in PLAN.items():
        session.add(
            PackageMilestone(
                package_id=pacote.id,
                milestone=milestone,
                plan_date=plan,
                real_date=plan if milestone == "requisicao" else None,
                version=1,
            )
        )
    session.flush()
    return pacote


def novo_pacote(cenario: CenarioPlano, **campos: object) -> PackageInput:
    """Um pacote de partida: datas em ordem e com folga positiva contra o ROS."""
    base = PackageInput(
        scope=PACKAGE_SCOPE,
        kind="Equipamento",
        modality="Preço global",
        discipline_id=cenario.disciplina.id,
        buyer_id=cenario.ana.person_id,
        eac_code=ITEM_CODE,
        estimate_cents=PACKAGE_ESTIMATE_CENTS,
        requisition=date(2026, 10, 1),
        rfx=date(2026, 10, 15),
        adjudication=date(2026, 11, 20),
        order=date(2026, 11, 25),
        ros=date(2027, 3, 15),
    )
    return replace(base, **campos)  # type: ignore[arg-type]
