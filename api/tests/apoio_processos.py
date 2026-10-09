"""Apoio dos testes dos processos de compra: o cenário (pacotes, fornecedores e parâmetros).

O cenário vive na transação do teste e parte do cenário do plano (dois projetos, um Admin e um
Visualizador, disciplina, item de custo da EAC, um pacote congelado na requisição e um pacote
planejado), acrescentando a versão 1 dos parâmetros, três fornecedores qualificados e uma empresa
bloqueada. As identidades de partida deixam cada teste mudar só o que importa.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date

from sqlalchemy.orm import Session

from src.core.rbac import User
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.models import Company, Discipline, Project
from src.modulos.financeiro.models import EacItem
from src.modulos.suprimentos import service
from src.modulos.suprimentos.models import PurchasePackage, Supplier
from src.modulos.suprimentos.validation import ProposalInput, RequisitionInput, RfxInput
from tests.apoio_pacotes import REFERENCIA, montar_cenario_do_plano, novo_pacote
from tests.identidades import criar_empresa

QUALIFICADO_ATE = date(2027, 3, 31)
FORNECEDORES = (
    "Alfa Fornecimentos de teste",
    "Beta Fornecimentos de teste",
    "Gama Fornecimentos de teste",
)
BLOQUEADA = "Delta Bloqueada de teste"


@dataclass(frozen=True)
class CenarioProcessos:
    """O cenário do plano mais os fornecedores do processo e o pacote planejado."""

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


def montar_cenario_processos(session: Session) -> CenarioProcessos:
    """Cria o cenário do plano, os parâmetros, os fornecedores e o pacote planejado."""
    plano = montar_cenario_do_plano(session)
    configuracoes.seed_initial_parameters(
        session, author_id=plano.ana.id, effective_from=REFERENCIA
    )
    fornecedores: list[Company] = []
    for nome in FORNECEDORES:
        empresa = criar_empresa(session, nome)
        empresa.kind = "Fornecedor"
        session.flush()
        session.add(
            Supplier(
                company_id=empresa.id,
                situation="Qualificado",
                validity=QUALIFICADO_ATE,
                observation=None,
                version=1,
            )
        )
        fornecedores.append(empresa)
    bloqueada = criar_empresa(session, BLOQUEADA)
    bloqueada.kind = "Fornecedor"
    session.flush()
    session.add(
        Supplier(
            company_id=bloqueada.id,
            situation="Bloqueado",
            validity=QUALIFICADO_ATE,
            observation=None,
            version=1,
        )
    )
    session.flush()
    planejado = service.create_package(
        session,
        user=plano.ana,
        project_id=plano.projeto.id,
        data=novo_pacote(plano, scope="Compressores de ar reserva"),
        reference_date=REFERENCIA,
    )
    pacote = session.get(PurchasePackage, planejado.package_id)
    if pacote is None:
        message = "O pacote planejado não foi criado no cenário."
        raise LookupError(message)
    return CenarioProcessos(
        projeto=plano.projeto,
        outro=plano.outro,
        ana=plano.ana,
        vitor=plano.vitor,
        disciplina=plano.disciplina,
        item=plano.item,
        pacote=plano.pacote,
        planejado=pacote,
        fornecedores=tuple(fornecedores),
        bloqueada=bloqueada,
    )


def requisicao(**campos: object) -> RequisitionInput:
    """Uma requisição de partida: a data de referência, sem documento."""
    base = RequisitionInput(date=REFERENCIA)
    return replace(base, **campos)  # type: ignore[arg-type]


def rfx_do_cenario(cenario: CenarioProcessos, **campos: object) -> RfxInput:
    """Uma RFx de partida: os três fornecedores qualificados, pesos 40/60 e prazo no mês."""
    base = RfxInput(
        date=date(2026, 8, 10),
        deadline=date(2026, 8, 31),
        weight_technical=40,
        weight_commercial=60,
        invitees=tuple(empresa.id for empresa in cenario.fornecedores),
    )
    return replace(base, **campos)  # type: ignore[arg-type]


def proposta_do_cenario(cenario: CenarioProcessos, **campos: object) -> ProposalInput:
    """Uma proposta de partida: o primeiro fornecedor, valor e prazo válidos."""
    base = ProposalInput(
        company_id=cenario.fornecedores[0].id,
        name="",
        received=date(2026, 8, 20),
        value_cents=50_000_000,
        deadline_days=90,
    )
    return replace(base, **campos)  # type: ignore[arg-type]
