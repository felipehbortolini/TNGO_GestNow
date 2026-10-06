"""Fachada do HSE (ISSUE-072, D5): HHT e fechamento mensal, com importação por planilha.

O HHT é um registro por mês e empresa — gravar de novo atualiza, sem duplicar; o fechamento é um
por mês. A importação confere linha a linha e só grava na confirmação; uma linha inválida é
recusada com a mensagem, e no Portfólio a importação é recusada de saída.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from src.core.errors import InvalidDataError
from src.core.importing import ImportContext
from src.core.scope import Scope
from src.modulos.hse import importers, service
from tests.apoio_hse import REFERENCIA, Cenario, fechamento_de, horas_de


def _escopo(cenario: Cenario) -> Scope:
    return Scope(project_id=cenario.projeto.id, source="url")


def _contexto(cenario: Cenario, *, portfolio: bool = False) -> ImportContext:
    return ImportContext(
        user=cenario.maria,
        scope=Scope(project_id=None if portfolio else cenario.projeto.id, source="padrao"),
        reference_date=REFERENCIA,
    )


# ── HHT ──────────────────────────────────────────────────────────────────────────────────────


def test_gravar_o_mesmo_mes_e_empresa_atualiza_sem_duplicar(
    sessao: Session, cenario: Cenario
) -> None:
    primeira = service.save_hours(
        sessao, user=cenario.maria, data=horas_de(cenario), reference_date=REFERENCIA
    )
    segunda = service.save_hours(
        sessao,
        user=cenario.maria,
        data=horas_de(cenario, headcount=55, hours=Decimal("12000")),
        reference_date=REFERENCIA,
    )

    linhas = service.list_hours(sessao, scope=_escopo(cenario))
    assert primeira.created
    assert not segunda.created
    assert len(linhas) == 1
    assert (linhas[0].headcount, linhas[0].hours) == (55, Decimal("12000"))
    assert linhas[0].hours_per_person == 218  # 12.000 / 55 = 218,18


def test_o_mesmo_mes_de_outra_empresa_e_outro_registro(sessao: Session, cenario: Cenario) -> None:
    service.save_hours(
        sessao, user=cenario.maria, data=horas_de(cenario), reference_date=REFERENCIA
    )
    service.save_hours(
        sessao,
        user=cenario.maria,
        data=horas_de(cenario, company_id=cenario.beta.id),
        reference_date=REFERENCIA,
    )

    assert len(service.list_hours(sessao, scope=_escopo(cenario))) == 2


def test_mes_futuro_e_recusado(sessao: Session, cenario: Cenario) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        service.save_hours(
            sessao,
            user=cenario.maria,
            data=horas_de(cenario, month=date(2026, 10, 1)),
            reference_date=REFERENCIA,
        )

    assert "futuro" in str(recusa.value)


# ── Fechamento mensal ────────────────────────────────────────────────────────────────────────


def test_o_fechamento_e_um_por_mes(sessao: Session, cenario: Cenario) -> None:
    primeira = service.save_closing(
        sessao, user=cenario.maria, data=fechamento_de(cenario), reference_date=REFERENCIA
    )
    segunda = service.save_closing(
        sessao,
        user=cenario.maria,
        data=fechamento_de(cenario, held_dds=22, conforming_items=60),
        reference_date=REFERENCIA,
    )

    linhas = service.list_closings(sessao, scope=_escopo(cenario))
    assert primeira.created
    assert not segunda.created
    assert len(linhas) == 1
    assert (linhas[0].held_dds, linhas[0].conforming_items) == (22, 60)
    assert linhas[0].dds_rate == Decimal("100.0")
    assert linhas[0].conformity_rate == Decimal("100.0")


def test_dds_realizados_nao_superam_os_programados(sessao: Session, cenario: Cenario) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        service.save_closing(
            sessao,
            user=cenario.maria,
            data=fechamento_de(cenario, held_dds=30),
            reference_date=REFERENCIA,
        )

    assert "programado" in str(recusa.value)


# ── Importação ───────────────────────────────────────────────────────────────────────────────


def _linha_valida() -> dict[str, object]:
    return {
        "month": date(2026, 8, 1),
        "company": "Alfa Montagens",
        "headcount": 60,
        "hours": Decimal("13080"),
    }


def test_a_importacao_recusa_a_linha_invalida_e_nao_grava(
    sessao: Session, cenario: Cenario
) -> None:
    importer = importers.hours_importer()
    invalida = {"month": None, "company": "Inexistente", "headcount": None, "hours": None}

    conferencia = importer.validate(sessao, values=invalida, context=_contexto(cenario))

    assert conferencia.errors
    assert any("Empresa" in erro for erro in conferencia.errors)
    assert service.list_hours(sessao, scope=_escopo(cenario)) == []


def test_a_importacao_grava_as_validas_so_na_confirmacao(sessao: Session, cenario: Cenario) -> None:
    importer = importers.hours_importer()

    conferencia = importer.validate(sessao, values=_linha_valida(), context=_contexto(cenario))
    assert not conferencia.errors
    assert service.list_hours(sessao, scope=_escopo(cenario)) == []

    importer.save(sessao, values=_linha_valida(), context=_contexto(cenario))

    linhas = service.list_hours(sessao, scope=_escopo(cenario))
    assert len(linhas) == 1
    assert linhas[0].hours == Decimal("13080")


def test_a_importacao_no_portfolio_e_recusada(sessao: Session, cenario: Cenario) -> None:
    importer = importers.hours_importer()

    with pytest.raises(InvalidDataError) as recusa:
        importer.validate(
            sessao, values=_linha_valida(), context=_contexto(cenario, portfolio=True)
        )

    assert "projeto" in str(recusa.value).lower()
