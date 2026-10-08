"""Apoio dos testes da Punch list (ISSUE-049): cenário mínimo, formulários, anexo e planilha.

O cenário tem projeto (com o padrão de numeração da punch list), empresa, dois sistemas do
cadastro de apoio, disciplinas e pessoas com cada perfil, tudo dentro da transação do teste.
Os formulários são montados como a tela os enviaria e a planilha da importação usa openpyxl,
como o leitor do servidor.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date

from openpyxl import Workbook
from sqlalchemy.orm import Session

from src.core import attachments
from src.core.attachments import NewAttachment
from src.core.rbac import Bond, GeneralProfile, User
from src.core.scope import Scope
from src.modulos.configuracoes.models import Collaborator, Company, Discipline, Project, System
from src.modulos.planejamento import validation
from tests.armazenamento_falso import ArmazenamentoEmMemoria
from tests.identidades import criar_colaborador, criar_empresa, criar_projeto

HOJE = date(2026, 9, 25)


@dataclass(frozen=True)
class Cenario:
    """O cenário mínimo da punch list, na transação do teste."""

    projeto: Project
    empresa: Company
    sistema: System
    outro_sistema: System
    membro: Collaborator
    gestor: Collaborator
    visualizador: Collaborator
    executante: Collaborator

    @property
    def escopo(self) -> Scope:
        return Scope(project_id=self.projeto.id, source="url")

    def _usuario(self, colaborador: Collaborator, perfil: GeneralProfile) -> User:
        return User(
            id=colaborador.id,
            person_id=colaborador.person_id,
            name="Pessoa de teste",
            email="pessoa@example.invalid",
            general_profile=perfil,
            bond=Bond.TIMENOW,
        )

    @property
    def usuario_membro(self) -> User:
        return self._usuario(self.membro, GeneralProfile.MEMBER)

    @property
    def usuario_gestor(self) -> User:
        return self._usuario(self.gestor, GeneralProfile.MANAGER)

    @property
    def usuario_visualizador(self) -> User:
        return self._usuario(self.visualizador, GeneralProfile.VIEWER)


def montar_cenario(session: Session) -> Cenario:
    """Cria o cenário mínimo dentro da transação do teste."""
    session.add_all([Discipline(name="Elétrica"), Discipline(name="Mecânica")])
    empresa = criar_empresa(session, "Montadora Alfa")
    projeto = criar_projeto(session, codigo="TN-PUNCH-001", nome="Projeto da punch list")
    projeto.punch_pattern = "PL-TN-2026"
    sistema = System(project_id=projeto.id, code="310", name="Flotação", area="Beneficiamento")
    outro_sistema = System(
        project_id=projeto.id, code="420", name="Subestação unitária", area="Elétrica"
    )
    session.add_all([sistema, outro_sistema])
    membro = criar_colaborador(
        session, email="membro-punch@example.invalid", nome="Maria Membro", perfil="Membro"
    )
    gestor = criar_colaborador(
        session, email="gestor-punch@example.invalid", nome="Gabriel Gestor", perfil="Gestor"
    )
    visualizador = criar_colaborador(
        session, email="visualizador-punch@example.invalid", perfil="Visualizador"
    )
    executante = criar_colaborador(
        session, email="executante-punch@example.invalid", nome="Elias Executante", perfil="Membro"
    )
    session.flush()
    return Cenario(
        projeto=projeto,
        empresa=empresa,
        sistema=sistema,
        outro_sistema=outro_sistema,
        membro=membro,
        gestor=gestor,
        visualizador=visualizador,
        executante=executante,
    )


def campos_do_item(cenario: Cenario, **overrides: object) -> dict[str, str]:
    """Os campos do formulário do item, como a tela os envia."""
    campos: dict[str, str] = {
        validation.FIELD_PUNCH_SYSTEM: str(cenario.sistema.id),
        validation.FIELD_PUNCH_SUBSYSTEM: "Tubulação",
        validation.FIELD_PUNCH_TAG: "310-P-030",
        validation.FIELD_PUNCH_DISCIPLINE: "Elétrica",
        validation.FIELD_PUNCH_CATEGORY: "B",
        validation.FIELD_PUNCH_MILESTONE: "Aceite provisório",
        validation.FIELD_PUNCH_ORIGIN: "Walkdown",
        validation.FIELD_PUNCH_DESCRIPTION: "Isolamento térmico incompleto no trecho final.",
        validation.FIELD_PUNCH_COMPANY: str(cenario.empresa.id),
        validation.FIELD_PUNCH_OWNER: str(cenario.executante.person_id),
        validation.FIELD_PUNCH_IDENTIFIED: str(cenario.membro.person_id),
        validation.FIELD_PUNCH_DUE: "2026-10-10",
    }
    campos.update({chave: str(valor) for chave, valor in overrides.items()})
    return campos


def form_item(cenario: Cenario, **overrides: object) -> validation.PunchItemForm:
    """O formulário do item com os campos padrão do cenário."""
    return validation.PunchItemForm(fields=campos_do_item(cenario, **overrides))


def form_verificacao(
    cenario: Cenario,
    *,
    resultado: str = validation.PUNCH_RESULT_APPROVED,
    verificador: int | None = None,
    comentario: str = "",
) -> validation.PunchVerificationForm:
    """O formulário do fechamento com verificação."""
    return validation.PunchVerificationForm(
        fields={
            validation.FIELD_PUNCH_RESULT: resultado,
            validation.FIELD_PUNCH_VERIFIER: str(
                cenario.gestor.person_id if verificador is None else verificador
            ),
            validation.FIELD_PUNCH_COMMENT: comentario,
        }
    )


def form_cancelamento(
    justificativa: str = "Registrado em duplicidade com outro item da mesma TAG.",
) -> validation.PunchCancellationForm:
    """O formulário do cancelamento."""
    return validation.PunchCancellationForm(
        fields={validation.FIELD_PUNCH_JUSTIFICATION: justificativa}
    )


def enviar_anexo(
    session: Session,
    *,
    user: User,
    item_id: int,
    armazenamento: ArmazenamentoEmMemoria,
    nome: str = "evidencia.jpg",
) -> None:
    """Grava um anexo de evidência no item, como o painel genérico faria."""
    attachments.upload(
        session,
        user=user,
        new=NewAttachment(
            origin_table="punch_item",
            origin_record_id=item_id,
            file_name=nome,
            content=b"conteudo da evidencia",
        ),
        reference_date=HOJE,
        storage=armazenamento,
    )


def planilha_punch(*linhas: dict[str, object], cabecalho_extra: str | None = None) -> bytes:
    """A planilha .xlsx da importação com o cabeçalho do modelo e as linhas pedidas."""
    headers = [
        "Sistema",
        "Subsistema",
        "TAG",
        "Disciplina",
        "Categoria",
        "Marco",
        "Origem",
        "Descrição",
        "Empresa",
        "Responsável",
        "Prazo",
    ]
    if cabecalho_extra:
        headers.append(cabecalho_extra)
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headers)
    for linha in linhas:
        sheet.append([linha.get(header) for header in headers])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def linha_punch(
    cenario: Cenario,
    *,
    sistema: str | None = None,
    tag: str = "310-P-030",
    categoria: str = "B",
    marco: str = "Aceite provisório",
    descricao: str = "Item importado do walkdown.",
    responsavel: str | None = None,
    prazo: date | None = None,
) -> dict[str, object]:
    """Uma linha da planilha, com os nomes que o modelo pede."""
    return {
        "Sistema": sistema or cenario.sistema.code,
        "Subsistema": "Tubulação",
        "TAG": tag,
        "Disciplina": "Elétrica",
        "Categoria": categoria,
        "Marco": marco,
        "Origem": "Walkdown",
        "Descrição": descricao,
        "Empresa": cenario.empresa.name,
        "Responsável": responsavel or "Elias Executante",
        "Prazo": prazo or date(2026, 10, 10),
    }
