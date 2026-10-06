"""Apoio dos testes das atas: a unidade organizacional e uma ata de partida (ISSUE-021)."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from sqlalchemy.orm import Session

from src.modulos.central_acoes import minutes_service
from src.modulos.central_acoes.validation import NewMinutes
from src.modulos.configuracoes.models import Unit
from tests.apoio_acoes import REFERENCIA, Cenario


def criar_unidade(session: Session, nome: str = "Unidade de teste") -> Unit:
    """Uma unidade organizacional do cadastro, para o campo Unidade da ata."""
    unidade = Unit(kind="organizacional", code=nome, name=nome)
    session.add(unidade)
    session.flush()
    return unidade


def nova_ata(cenario: Cenario, unidade: Unit, **campos: object) -> NewMinutes:
    """Uma ata de partida no projeto A, elaborada pelo Mário, de coordenação de obra."""
    base = NewMinutes(
        project_id=cenario.projeto_a.id,
        meeting_date=REFERENCIA - timedelta(days=2),
        meeting_type="Coordenação de obra",
        board="Diretoria de Projetos",
        unit_id=unidade.id,
        prepared_by_id=cenario.mario.person_id,
        subject="Coordenação quinzenal de obra",
    )
    return replace(base, **campos)  # type: ignore[arg-type]


def criar_ata(
    session: Session, cenario: Cenario, unidade: Unit, **campos: object
) -> minutes_service.MinutesRecord:
    """Gera a ata de partida pela fachada, como o Gil (Gestor)."""
    return minutes_service.create_minutes(
        session,
        user=cenario.gil,
        new=nova_ata(cenario, unidade, **campos),
        reference_date=REFERENCIA,
    )
