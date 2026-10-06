"""Apoio dos testes das lições: a disciplina, o formulário válido e uma lição Em validação."""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.core.rbac import User
from src.modulos.configuracoes.models import Discipline, Project
from src.modulos.governanca import lessons_service
from tests.governanca import apoio
from tests.governanca.apoio import HOJE


def disciplina(session: Session, nome: str = "Civil") -> Discipline:
    """Uma disciplina do cadastro de apoio."""
    existente = session.query(Discipline).filter_by(name=nome).one_or_none()
    if existente is not None:
        return existente
    item = Discipline(name=nome)
    session.add(item)
    session.flush()
    return item


def licao_valida(**mudancas: str) -> dict[str, str]:
    """O formulário de uma lição de registro direto que passa em todas as regras."""
    campos = {
        "titulo": "Cadastro de interferências antes da escavação",
        "tipo": "A evitar",
        "fase": "Construção",
        "area": "Riscos",
        "disciplina": "Civil",
        "origem": "Registro direto",
        "aconteceu": "Interferência não mapeada gerou 21 dias de atraso.",
        "causa": "Cadastro de interferências incompleto.",
        "impacto_prazo_dias": "21",
        "impacto_custo": "400000,00",
        "recomendacao": "Exigir varredura com georradar antes de liberar fundações.",
        "palavras_chave": "interferência, fundação",
        "aplicabilidade": "Corporativa",
    }
    campos.update(mudancas)
    return campos


def registrar_licao(
    session: Session, usuario: User, projeto: Project, **mudancas: str
) -> lessons_service.CreatedLesson:
    """Registra uma lição válida no projeto pela fachada."""
    disciplina(session)
    return lessons_service.create_lesson(
        session,
        user=usuario,
        scope=apoio.escopo_do_projeto(projeto),
        form=licao_valida(**mudancas),
        reference_date=HOJE,
    )


def licao_em_validacao(
    session: Session, autor: User, projeto: Project, **mudancas: str
) -> lessons_service.CreatedLesson:
    """Uma lição registrada já enviada para validação."""
    return registrar_licao(session, autor, projeto, enviar="sim", **mudancas)
