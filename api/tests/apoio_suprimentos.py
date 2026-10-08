"""Apoio dos testes do cadastro de fornecedores: o cenário (empresas, contrato e avaliação).

O cenário vive na transação do teste: dois projetos, um colaborador de cada perfil (Admin,
Gestor, Membro e Visualizador), a versão 1 dos parâmetros, três empresas do cadastro (uma
qualificada com documentos vencendo e vencido, uma sem qualificação e a Gerenciadora, que não é
fornecedor), um contrato da qualificada no projeto 1 e uma avaliação mensal dele, para o
desempenho. As identidades de partida deixam cada teste mudar só o que importa.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date

from sqlalchemy.orm import Session

from src.core.rbac import Bond, GeneralProfile, User
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.models import Collaborator, Company, Project
from src.modulos.financeiro.models import Contract, ContractEvaluation, ContractEvaluationCriterion
from src.modulos.suprimentos.models import (
    Supplier,
    SupplierCategory,
    SupplierDocument,
    SupplierHistory,
)
from src.modulos.suprimentos.validation import (
    DocumentInput,
    QualificationInput,
    SupplierInput,
)
from tests.identidades import criar_colaborador, criar_empresa, criar_projeto

REFERENCIA = date(2026, 9, 25)
ADA = "ada.admin@suprimentos.example.invalid"
GIL = "gil.gestor@suprimentos.example.invalid"
MARIO = "mario.membro@suprimentos.example.invalid"
VERA = "vera.visualizadora@suprimentos.example.invalid"

CONTRACT_NUMBER = "CT-2026-900"
CONTRACT_CENTS = 50_000_000
EVALUATION_WEIGHTS = {
    "hse": 25,
    "qualidade": 20,
    "prazo": 20,
    "gestao": 15,
    "recursos": 10,
    "documentacao": 10,
}
VALID_DOCUMENT = "Certidão negativa de débitos federais"
EXPIRED_DOCUMENT = "Certidão negativa de débitos trabalhistas"


@dataclass(frozen=True)
class Cenario:
    """Dois projetos, as pessoas do teste, as empresas e o contrato avaliado."""

    projeto: Project
    outro: Project
    ada: User
    gil: User
    mario: User
    vera: User
    qualificada: Company
    sem_qualificacao: Company
    gerenciadora: Company
    fornecedor: Supplier
    contrato: Contract


def usuario_de(session: Session, colaborador: Collaborator) -> User:
    """O ``User`` que a plataforma monta para um colaborador do cadastro."""
    acesso = configuracoes.find_access(session, colaborador.id)
    if acesso is None:
        message = f"Colaborador {colaborador.id} fora do cadastro."
        raise LookupError(message)
    return User(
        id=acesso.id,
        person_id=acesso.person_id,
        name=acesso.name,
        email=acesso.email,
        general_profile=GeneralProfile(acesso.general_profile),
        bond=Bond(acesso.bond),
        company_id=acesso.company_id,
    )


def montar_cenario(session: Session) -> Cenario:
    """Cria projetos, colaboradores, parâmetros, empresas, fornecedor e contrato no teste."""
    projeto = criar_projeto(session, codigo="TN-SUP-001", nome="Planta de teste")
    outro = criar_projeto(session, codigo="TN-SUP-002", nome="Área de teste")
    ada = usuario_de(
        session, criar_colaborador(session, email=ADA, nome="Ada Admin", perfil="Admin")
    )
    gil = usuario_de(
        session, criar_colaborador(session, email=GIL, nome="Gil Gestor", perfil="Gestor")
    )
    mario = usuario_de(session, criar_colaborador(session, email=MARIO, nome="Mário Membro"))
    vera = usuario_de(
        session,
        criar_colaborador(session, email=VERA, nome="Vera Visualizadora", perfil="Visualizador"),
    )
    configuracoes.seed_initial_parameters(session, author_id=gil.id, effective_from=REFERENCIA)

    qualificada = criar_empresa(session, "Alfa Montagens de teste")
    qualificada.kind = "Contratada"
    sem_qualificacao = criar_empresa(session, "Beta Fornecimentos de teste")
    sem_qualificacao.kind = "Fornecedor"
    gerenciadora = criar_empresa(session, "Timenow Gerenciadora de teste")
    gerenciadora.kind = "Gerenciadora"
    session.flush()

    fornecedor = Supplier(
        company_id=qualificada.id,
        situation="Qualificado",
        validity=date(2027, 3, 31),
        observation=None,
        version=1,
    )
    session.add(fornecedor)
    session.flush()
    session.add_all(
        [
            SupplierCategory(supplier_id=fornecedor.id, category="Montagem eletromecânica"),
            SupplierCategory(supplier_id=fornecedor.id, category="Estruturas metálicas"),
        ]
    )
    session.add_all(
        [
            SupplierDocument(
                supplier_id=fornecedor.id,
                name=VALID_DOCUMENT,
                validity=date(2026, 10, 5),
                version=1,
            ),
            SupplierDocument(
                supplier_id=fornecedor.id,
                name=EXPIRED_DOCUMENT,
                validity=date(2026, 9, 24),
                version=1,
            ),
        ]
    )
    session.add(
        SupplierHistory(
            supplier_id=fornecedor.id,
            by_id=gil.person_id,
            on=date(2026, 8, 20),
            from_situation=None,
            to_situation="Qualificado",
            justification="Cadastro inicial.",
        )
    )
    contract = Contract(
        project_id=projeto.id,
        company_id=qualificada.id,
        manager_id=gil.person_id,
        fiscal_id=gil.person_id,
        number=CONTRACT_NUMBER,
        object="Obra de teste",
        modality="Preço unitário",
        original_value_cents=CONTRACT_CENTS,
        start=date(2026, 1, 5),
        original_end=date(2027, 3, 31),
        current_end=date(2027, 3, 31),
        retention_pct=5,
        claim_notice_days=30,
        situation="Em execução",
        version=1,
    )
    session.add(contract)
    session.flush()
    version = configuracoes.current_version(
        session, group="avaliacaoContratada", reference_date=REFERENCIA
    )
    if version is None:
        message = "A versão vigente dos parâmetros de avaliação não está na carga do teste."
        raise LookupError(message)
    evaluation = ContractEvaluation(
        contract_id=contract.id,
        evaluator_id=gil.person_id,
        parameter_version_id=version.id,
        period=date(2026, 8, 1),
        kind="Mensal",
        comment="Mobilização dentro do plano.",
        version=1,
    )
    session.add(evaluation)
    session.flush()
    session.add_all(
        ContractEvaluationCriterion(
            evaluation_id=evaluation.id,
            criterion=criterion,
            weight=weight,
            note=4,
        )
        for criterion, weight in EVALUATION_WEIGHTS.items()
    )
    session.flush()
    return Cenario(
        projeto=projeto,
        outro=outro,
        ada=ada,
        gil=gil,
        mario=mario,
        vera=vera,
        qualificada=qualificada,
        sem_qualificacao=sem_qualificacao,
        gerenciadora=gerenciadora,
        fornecedor=fornecedor,
        contrato=contract,
    )


def novo_fornecedor(**campos: object) -> SupplierInput:
    """Um fornecedor de partida: empresa nova com categoria e um documento com validade."""
    base = SupplierInput(
        name="Gama Serviços de teste",
        kind="Fornecedor",
        categories=("Instrumentação",),
        documents=(
            DocumentInput(name=VALID_DOCUMENT, validity=date(2027, 1, 31)),
            DocumentInput(name=EXPIRED_DOCUMENT),
        ),
        observation="",
    )
    return replace(base, **campos)  # type: ignore[arg-type]


def qualificacao(**campos: object) -> QualificationInput:
    """Uma qualificação de partida: mantém Qualificado, com a validade futura e a categoria."""
    base = QualificationInput(
        situation="Qualificado",
        categories=("Montagem eletromecânica", "Estruturas metálicas"),
        documents=(),
        validity=date(2027, 3, 31),
        observation="",
        justification="",
        version=1,
    )
    return replace(base, **campos)  # type: ignore[arg-type]
