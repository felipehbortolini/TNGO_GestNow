"""Ligação da Governança com a EAP (ISSUE-038): fonte, incorporação, ficha e encerramento.

A SM aprovada com impacto em escopo é o que a revisão da EAP consome; a fonte diz se o impacto
está pendente, a incorporação grava o número da revisão na SM, a ficha e o próximo passo apontam
a revisão e o encerramento só passa depois de incorporada.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from src.core.errors import InvalidDataError
from src.modulos.configuracoes.models import Project
from src.modulos.governanca import calculations, models, service
from src.modulos.governanca.models import ChangeImpact, ChangeRequest
from tests.governanca import apoio
from tests.governanca.apoio import HOJE

ESCOPO = "Inclusão do pacote de tratamento"


def _sm(
    session: Session,
    projeto: Project,
    codigo: str,
    situacao: str = models.SITUATION_APPROVED,
    **mudancas: object,
) -> ChangeRequest:
    pessoa_id = projeto.manager_id
    escopo = mudancas.get("escopo", ESCOPO)
    change = ChangeRequest(
        project_id=projeto.id,
        requester_id=pessoa_id,
        code=codigo,
        title=f"Solicitação {codigo}",
        kind="Escopo",
        origin="Cliente",
        priority="Normal",
        request_date=date(2026, 9, 1),
        description="Descrição da solicitação de teste.",
        situation=situacao,
        eap_revision=mudancas.get("eap_revision"),
    )
    session.add(change)
    session.flush()
    if escopo is not None:
        session.add(
            ChangeImpact(
                change_id=change.id,
                analyst_id=pessoa_id,
                analysis_date=date(2026, 9, 10),
                cost_cents=0,
                term_days=0,
                scope=escopo,
                quality="Sem impacto",
                risks="Sem impacto",
                safety="Sem impacto",
                contract="Sem impacto",
                affects_contract_milestone=False,
            )
        )
        session.flush()
    return change


def _gestor(session: Session):
    return apoio.usuario_de(apoio.colaborador(session, apoio.GESTOR, perfil="Gestor"))


# ── has_scope_impact ──────────────────────────────────────────────────────


def test_has_scope_impact_ignora_vazio_e_sem_impacto() -> None:
    assert calculations.has_scope_impact("Acréscimo de escopo")
    assert not calculations.has_scope_impact("")
    assert not calculations.has_scope_impact("   ")
    assert not calculations.has_scope_impact("Sem impacto")
    assert not calculations.has_scope_impact("SEM IMPACTO")
    assert not calculations.has_scope_impact("sem impacto ")


# ── change_eap_source ─────────────────────────────────────────────────────


def test_change_eap_source_le_aprovacao_escopo_e_incorporacao(sessao: Session) -> None:
    projeto = apoio.projeto_com_orcamento(sessao)
    pendente = _sm(sessao, projeto, "SM-TN-2026-0001")
    sem_impacto = _sm(sessao, projeto, "SM-TN-2026-0002", escopo="Sem impacto")
    incorporada = _sm(sessao, projeto, "SM-TN-2026-0003", eap_revision=2)

    fonte = service.change_eap_source(sessao, change_id=pendente.id)

    assert fonte is not None
    assert (fonte.change_id, fonte.project_id, fonte.code) == (
        pendente.id,
        projeto.id,
        "SM-TN-2026-0001",
    )
    assert fonte.approved
    assert fonte.scope_impact
    assert fonte.incorporated_revision is None

    sem = service.change_eap_source(sessao, change_id=sem_impacto.id)
    assert sem is not None
    assert not sem.scope_impact

    gravada = service.change_eap_source(sessao, change_id=incorporada.id)
    assert gravada is not None
    assert gravada.incorporated_revision == 2

    assert service.change_eap_source(sessao, change_id=999_999) is None


def test_eap_revision_sources_lista_as_pendentes_mais_antigas_primeiro(sessao: Session) -> None:
    projeto = apoio.projeto_com_orcamento(sessao)
    primeira = _sm(sessao, projeto, "SM-TN-2026-0001")
    _sm(sessao, projeto, "SM-TN-2026-0002", escopo="Sem impacto")
    _sm(sessao, projeto, "SM-TN-2026-0003", eap_revision=1)
    segunda = _sm(sessao, projeto, "SM-TN-2026-0004")
    _sm(sessao, projeto, "SM-TN-2026-0005", models.SITUATION_REGISTERED)

    fontes = service.eap_revision_sources(sessao, project_id=projeto.id)

    assert [fonte.code for fonte in fontes] == [primeira.code, segunda.code]
    assert all(fonte.approved and fonte.scope_impact for fonte in fontes)
    assert all(fonte.incorporated_revision is None for fonte in fontes)


def test_incorporate_eap_revision_grava_o_numero_na_sm(sessao: Session) -> None:
    projeto = apoio.projeto_com_orcamento(sessao)
    gestor = _gestor(sessao)
    mudanca = _sm(sessao, projeto, "SM-TN-2026-0001")

    service.incorporate_eap_revision(sessao, user=gestor, change_id=mudanca.id, revision=3)

    assert mudanca.eap_revision == 3
    fonte = service.change_eap_source(sessao, change_id=mudanca.id)
    assert fonte is not None
    assert fonte.incorporated_revision == 3
    with pytest.raises(InvalidDataError):
        service.incorporate_eap_revision(sessao, user=gestor, change_id=999_999, revision=1)


# ── Ficha e próxima etapa ─────────────────────────────────────────────────


def test_a_ficha_e_o_proximo_passo_pedem_a_revisao_da_eap(sessao: Session) -> None:
    projeto = apoio.projeto_com_orcamento(sessao)
    usuario = apoio.usuario_de(apoio.colaborador(sessao, apoio.MEMBRO))
    mudanca = _sm(sessao, projeto, "SM-TN-2026-0001", models.SITUATION_IMPLEMENTING)

    ficha = service.find_change_sheet(sessao, user=usuario, code=mudanca.code, reference_date=HOJE)

    assert ficha is not None
    assert ficha.pending_eap_revision
    assert not ficha.pending_eac_revision
    assert ficha.row.next_step == "Incorporar a SM na EAP (nova revisão)"

    service.incorporate_eap_revision(sessao, user=_gestor(sessao), change_id=mudanca.id, revision=1)

    depois = service.find_change_sheet(sessao, user=usuario, code=mudanca.code, reference_date=HOJE)
    assert depois is not None
    assert not depois.pending_eap_revision
    assert depois.row.next_step == "Encerrar a mudança"


# ── Encerramento ──────────────────────────────────────────────────────────


def test_encerramento_recusa_sem_a_revisao_da_eap_e_passa_depois(sessao: Session) -> None:
    projeto = apoio.projeto_com_orcamento(sessao)
    gestor = _gestor(sessao)
    mudanca = _sm(sessao, projeto, "SM-TN-2026-0001", models.SITUATION_IMPLEMENTING)
    formulario = {
        "data": HOJE.isoformat(),
        "observacao": "Linhas de base conferidas.",
        "versao": str(mudanca.version),
    }

    with pytest.raises(InvalidDataError) as recusa:
        service.close_change(
            sessao, user=gestor, code=mudanca.code, form=formulario, reference_date=HOJE
        )

    assert "EAP" in str(recusa.value)

    service.incorporate_eap_revision(sessao, user=gestor, change_id=mudanca.id, revision=1)
    formulario["versao"] = str(mudanca.version)

    resultado = service.close_change(
        sessao, user=gestor, code=mudanca.code, form=formulario, reference_date=HOJE
    )

    assert resultado.code == mudanca.code
    assert mudanca.situation == models.SITUATION_CLOSED
    assert mudanca.eap_revision == 1
