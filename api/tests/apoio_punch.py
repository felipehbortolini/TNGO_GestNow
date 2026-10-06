"""Apoio dos testes da Punch list (ISSUE-049): o cenário mínimo e os atalhos da fachada.

Sobre o cadastro do 6WLA (dois projetos, uma empresa, uma pessoa de cada perfil) acrescenta o
padrão de numeração do projeto, dois sistemas e os dois papéis da verificação: o executante
(a pessoa do membro, responsável pelos itens) e o verificador (o admin, outra pessoa).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import attachments
from src.core.rbac import GeneralProfile, User
from src.core.scope import Scope
from src.modulos.central_acoes.models import Action
from src.modulos.configuracoes.models import System
from src.modulos.planejamento import punch_service as service
from src.modulos.planejamento.models import PunchItem
from src.modulos.planejamento.punch_validation import ItemInput
from tests.apoio_6wla import HOJE, Cadastro
from tests.armazenamento_falso import ArmazenamentoEmMemoria

PADRAO = "PL-TN-2026"


@dataclass(frozen=True)
class CenarioPunch:
    """O cadastro, os dois sistemas do projeto e quem faz o quê."""

    cadastro: Cadastro
    sistema: System
    outro_sistema: System
    armazenamento: ArmazenamentoEmMemoria

    @property
    def escopo(self) -> Scope:
        """O escopo do projeto do cadastro."""
        return Scope(project_id=self.cadastro.projeto.id, source="url")

    @property
    def portfolio(self) -> Scope:
        """O escopo do Portfólio."""
        return Scope(project_id=None, source="url")

    @property
    def executante(self) -> User:
        """Quem executa: o membro, cuja pessoa é a responsável pelos itens."""
        return self.cadastro.usuario(self.cadastro.membro, GeneralProfile.MEMBER)

    @property
    def verificador(self) -> User:
        """Quem verifica: o admin, outra pessoa."""
        return self.cadastro.usuario(self.cadastro.admin, GeneralProfile.ADMIN)

    @property
    def visualizador(self) -> User:
        """Quem só lê."""
        return self.cadastro.usuario_visualizador


def montar_cenario(session: Session, cadastro: Cadastro) -> CenarioPunch:
    """Acrescenta ao cadastro o padrão do projeto e dois sistemas."""
    cadastro.projeto.punch_pattern = PADRAO
    sistema = System(
        project_id=cadastro.projeto.id, code="210", name="Moagem", area="Beneficiamento"
    )
    outro = System(
        project_id=cadastro.projeto.id, code="310", name="Flotação", area="Beneficiamento"
    )
    session.add_all([sistema, outro])
    session.flush()
    return CenarioPunch(cadastro, sistema, outro, ArmazenamentoEmMemoria())


def campos(cenario: CenarioPunch, **mudancas: object) -> ItemInput:
    """Os campos de um item válido, com o que o teste quiser mudar."""
    base = ItemInput(
        system_id=cenario.sistema.id,
        subsystem="Painéis",
        tag="PN-210-01",
        discipline="Elétrica",
        category="A",
        milestone="Comissionamento",
        origin="Walkdown",
        description="Falta identificação dos cabos no painel.",
        company_id=cenario.cadastro.empresa.id,
        responsible_id=cenario.cadastro.responsavel.id,
        identified_by_id=cenario.cadastro.admin.person_id,
        due_date=HOJE + timedelta(days=10),
    )
    return replace(base, **mudancas)


def abrir(session: Session, cenario: CenarioPunch, **mudancas: object) -> PunchItem:
    """Abre um item pela fachada, como o membro."""
    return service.create_item(
        session,
        user=cenario.executante,
        scope=cenario.escopo,
        data=campos(cenario, **mudancas),
        reference_date=HOJE,
    )


def anexar_evidencia(session: Session, cenario: CenarioPunch, item: PunchItem) -> None:
    """Grava uma evidência (um anexo) no item."""
    attachments.upload(
        session,
        user=cenario.executante,
        new=attachments.NewAttachment(
            origin_table=service.ATTACHMENT_TABLE,
            origin_record_id=item.id,
            file_name="foto-do-fechamento.jpg",
            content=b"conteudo da foto",
        ),
        reference_date=HOJE,
        storage=cenario.armazenamento,
    )


def levar_a_verificacao(session: Session, cenario: CenarioPunch, item: PunchItem) -> PunchItem:
    """Trata o item, anexa a evidência e o envia para verificação."""
    service.start_treatment(
        session,
        user=cenario.executante,
        scope=cenario.escopo,
        item_id=item.id,
        version=str(item.version),
    )
    anexar_evidencia(session, cenario, item)
    return service.submit_for_verification(
        session,
        user=cenario.executante,
        scope=cenario.escopo,
        request=service.TreatmentRequest(
            item_id=item.id, comment="Cabos identificados.", version=str(item.version)
        ),
    )


def acao_do_item(session: Session, item: PunchItem) -> Action:
    """A ação da Central que o item gerou (uma só, origem Punch list)."""
    return session.scalars(
        select(Action).where(Action.origin == "Punch list", Action.origin_ref == item.code)
    ).one()


def hoje() -> date:
    """O dia parado dos testes."""
    return HOJE
