"""A importação do plano de compras (ISSUE-058): as regras da linha e a gravação pela fachada.

A linha chega já convertida pelo fluxo genérico (``core.importing``): a estimativa em centavos,
as datas em ``date`` e os nomes como o cadastro os escreve. O importador resolve o item da EAC,
o comprador e a disciplina do projeto e recusa o que o formulário recusaria; a gravação passa
por ``service.create_package``, com a nota de importação na trilha.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import importing
from src.core.importing import ImportContext
from src.core.models import AuditEntry
from src.core.scope import Scope
from src.modulos.suprimentos import importers, service
from src.modulos.suprimentos.models import PurchasePackage
from tests.apoio_pacotes import (
    ITEM_CODE,
    REFERENCIA,
    SUBPACKAGE_CODE,
    CenarioPlano,
    montar_cenario_do_plano,
)


@pytest.fixture
def cenario(sessao: Session) -> CenarioPlano:
    """O cenário do plano, no lugar do cenário de fornecedores do conftest."""
    return montar_cenario_do_plano(sessao)


def _context(cenario: CenarioPlano) -> ImportContext:
    return ImportContext(
        user=cenario.ana,
        scope=Scope(project_id=cenario.projeto.id, source="url"),
        reference_date=REFERENCIA,
    )


def _values(**extras: object) -> dict[str, object]:
    base: dict[str, object] = {
        "escopo": "Compressores de ar",
        "tipo": "Equipamento",
        "modalidade": "Preço global",
        "disciplina": "Mecânica de teste",
        "eac": ITEM_CODE,
        "estimativa": 50_000_000,
        "comprador": "Ana Admin",
        "requisicao": date(2026, 10, 1),
        "rfx": date(2026, 10, 15),
        "adjudicacao": date(2026, 11, 20),
        "pedido": date(2026, 11, 25),
        "ros": date(2027, 3, 15),
        "lli": "Não",
    }
    base.update(extras)
    return base


def test_o_importador_do_plano_esta_registrado() -> None:
    importers.register_importers()

    registrado = importing.find("plano-de-compras")
    assert registrado is not None
    assert registrado.title == "Plano de compras"
    assert registrado.module == "suprimentos"
    assert [column.header for column in registrado.columns] == [
        "Escopo",
        "Tipo",
        "Modalidade",
        "Disciplina",
        "Item da EAC",
        "Estimativa (R$)",
        "Comprador",
        "Requisição",
        "RFx",
        "Adjudicação",
        "Pedido",
        "ROS",
        "LLI",
    ]


def test_a_linha_valida_passa_e_grava_com_a_nota_de_importacao(
    sessao: Session, cenario: CenarioPlano
) -> None:
    importador = importers.packages_importer()

    veredito = importador.validate(sessao, values=_values(), context=_context(cenario))
    assert veredito.errors == ()
    importador.save(sessao, values=_values(), context=_context(cenario))

    pacote = sessao.scalars(select(PurchasePackage).where(PurchasePackage.code == "PC-02")).one()
    assert pacote.scope == "Compressores de ar"
    assert pacote.buyer_id == cenario.ana.person_id
    assert pacote.discipline_id == cenario.disciplina.id
    assert pacote.estimate_cents == 50_000_000
    historico = sessao.scalars(
        select(AuditEntry)
        .where(
            AuditEntry.entity == service.HISTORY_ENTITY,
            AuditEntry.record_id == pacote.id,
        )
        .order_by(AuditEntry.id)
    ).all()
    assert (historico[-1].after or {})["campos"] == ["importacao"]
    assert (historico[-1].after or {})["justificativa"] == service.IMPORT_NOTE


def test_a_linha_com_item_de_nivel_2_e_recusada(sessao: Session, cenario: CenarioPlano) -> None:
    veredito = importers.packages_importer().validate(
        sessao, values=_values(eac=SUBPACKAGE_CODE), context=_context(cenario)
    )

    assert any(SUBPACKAGE_CODE in erro for erro in veredito.errors)


def test_a_linha_com_disciplina_desconhecida_fala_o_nome_da_planilha(
    sessao: Session, cenario: CenarioPlano
) -> None:
    veredito = importers.packages_importer().validate(
        sessao, values=_values(disciplina="Inexistente"), context=_context(cenario)
    )

    assert veredito.errors == ("A disciplina “Inexistente” não está no cadastro.",)


def test_a_linha_com_folga_negativa_e_recusada(sessao: Session, cenario: CenarioPlano) -> None:
    veredito = importers.packages_importer().validate(
        sessao,
        values=_values(pedido=date(2027, 3, 31), ros=date(2027, 3, 30)),
        context=_context(cenario),
    )

    assert any("folga negativa" in erro for erro in veredito.errors)
