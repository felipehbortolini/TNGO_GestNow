"""As fachadas do cadastro de fornecedores (ISSUE-057): a qualificação, a validade e a avaliação.

A leitura usa o escopo do projeto e o Portfólio; a gravação passa pela fachada, com a trilha e a
versão. A ligação com o Financeiro (D9) é exercitada pela avaliação final de contrato, que
atualiza a qualificação existente na mesma transação.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.errors import AccessDeniedError, InvalidDataError, VersionConflictError
from src.core.scope import Scope
from src.modulos.configuracoes.models import Company
from src.modulos.financeiro import service as financeiro
from src.modulos.financeiro.models import Contract
from src.modulos.suprimentos import service, validation
from src.modulos.suprimentos.models import Supplier, SupplierDocument, SupplierHistory
from tests.apoio_suprimentos import (
    EVALUATION_WEIGHTS,
    EXPIRED_DOCUMENT,
    REFERENCIA,
    VALID_DOCUMENT,
    Cenario,
    novo_fornecedor,
    qualificacao,
)
from tests.armazenamento_falso import ArmazenamentoEmMemoria


def _scope(cenario: Cenario, *, portfolio: bool = False) -> Scope:
    return Scope(project_id=None if portfolio else cenario.projeto.id, source="url")


def _encontrar(sessao: Session, cenario: Cenario, company_id: int, *, portfolio: bool = False):
    return service.find_supplier(
        sessao,
        user=cenario.mario,
        scope=_scope(cenario, portfolio=portfolio),
        company_id=company_id,
        reference_date=REFERENCIA,
    )


def _listar(sessao: Session, cenario: Cenario, **filtros: object):
    return service.list_suppliers(
        sessao,
        user=cenario.mario,
        scope=_scope(cenario, portfolio=bool(filtros.pop("portfolio", False))),
        filters=validation.SupplierFilters(**filtros),  # type: ignore[arg-type]
        reference_date=REFERENCIA,
    )


# ── Leitura ──────────────────────────────────────────────────────────────


def test_a_lista_traz_a_empresa_qualificada_com_documentos_e_desempenho(
    sessao: Session, cenario: Cenario
) -> None:
    listagem = _listar(sessao, cenario)
    linha = next(item for item in listagem.lines if item.company_id == cenario.qualificada.id)

    assert linha.registered is True
    assert linha.situation == "Qualificado"
    assert linha.categories == ("Estruturas metálicas", "Montagem eletromecânica")
    assert linha.documents_up_to_date is False
    assert [document.name for document in linha.expired_documents] == [EXPIRED_DOCUMENT]
    valid = next(item for item in linha.documents if item.name == VALID_DOCUMENT)
    assert (valid.expired, valid.expiring) == (False, True)
    assert linha.contracted_cents == 50_000_000
    assert linha.last_evaluation is not None
    assert (linha.last_evaluation.score, linha.last_evaluation.score_class) == (80, "B")
    assert linha.mean_score == Decimal("80.0")
    assert listagem.summary.registered == 1
    assert listagem.summary.qualified == 1
    assert listagem.summary.expired_documents == 1
    assert listagem.summary.unregistered == 1


def test_a_gerenciadora_nao_entra_no_cadastro(sessao: Session, cenario: Cenario) -> None:
    listagem = _listar(sessao, cenario)

    assert {line.company_id for line in listagem.lines} == {
        cenario.qualificada.id,
        cenario.sem_qualificacao.id,
    }


def test_o_desempenho_segue_o_escopo_do_projeto(sessao: Session, cenario: Cenario) -> None:
    contrato = Contract(
        project_id=cenario.outro.id,
        company_id=cenario.qualificada.id,
        manager_id=cenario.gil.person_id,
        fiscal_id=cenario.gil.person_id,
        number="CT-2026-901",
        object="Serviço do outro projeto",
        modality="Preço unitário",
        original_value_cents=10_000_000,
        start=date(2026, 2, 1),
        original_end=date(2027, 2, 1),
        current_end=date(2027, 2, 1),
        retention_pct=5,
        claim_notice_days=30,
        situation="Em execução",
        version=1,
    )
    sessao.add(contrato)
    sessao.flush()

    no_projeto = _encontrar(sessao, cenario, cenario.qualificada.id)
    na_carteira = _encontrar(sessao, cenario, cenario.qualificada.id, portfolio=True)

    assert no_projeto is not None and na_carteira is not None
    assert no_projeto.contracted_cents == 50_000_000
    assert na_carteira.contracted_cents == 60_000_000
    assert [item.number for item in na_carteira.contracts] == ["CT-2026-900", "CT-2026-901"]


def test_os_filtros_de_situacao_categoria_e_busca(sessao: Session, cenario: Cenario) -> None:
    sem = _listar(sessao, cenario, situation="Sem qualificação")
    assert [line.company_id for line in sem.lines] == [cenario.sem_qualificacao.id]

    categoria = _listar(sessao, cenario, category="Montagem eletromecânica")
    assert [line.company_id for line in categoria.lines] == [cenario.qualificada.id]

    busca = _listar(sessao, cenario, search="alfa montagens")
    assert [line.company_id for line in busca.lines] == [cenario.qualificada.id]


def test_o_documento_vence_no_dia_seguinte_a_validade(sessao: Session, cenario: Cenario) -> None:
    documento = sessao.scalars(
        select(SupplierDocument).where(SupplierDocument.name == EXPIRED_DOCUMENT)
    ).one()
    documento.validity = REFERENCIA
    sessao.flush()

    linha = _encontrar(sessao, cenario, cenario.qualificada.id)

    assert linha is not None
    assert linha.documents_up_to_date is True
    assert linha.expired_documents == ()


# ── Gravação ─────────────────────────────────────────────────────────────


def test_cadastro_novo_cria_a_empresa_o_fornecedor_e_o_historico(
    sessao: Session, cenario: Cenario
) -> None:
    resultado = service.create_supplier(
        sessao, user=cenario.mario, data=novo_fornecedor(), reference_date=REFERENCIA
    )

    empresa = sessao.get(Company, resultado.company_id)
    fornecedor = sessao.scalars(
        select(Supplier).where(Supplier.company_id == resultado.company_id)
    ).one()
    historico = sessao.scalars(
        select(SupplierHistory).where(SupplierHistory.supplier_id == fornecedor.id)
    ).one()
    assert resultado.created is True
    assert empresa is not None and (empresa.name, empresa.kind) == (
        "Gama Serviços de teste",
        "Fornecedor",
    )
    assert (fornecedor.situation, fornecedor.validity) == ("Em qualificação", None)
    assert historico.from_situation is None
    assert (historico.to_situation, historico.justification) == (
        "Em qualificação",
        service.INITIAL_JUSTIFICATION,
    )


def test_nome_repetido_e_nome_curto_sao_recusados(sessao: Session, cenario: Cenario) -> None:
    with pytest.raises(InvalidDataError) as repetido:
        service.create_supplier(
            sessao,
            user=cenario.mario,
            data=novo_fornecedor(name="Alfa Montagens de teste"),
            reference_date=REFERENCIA,
        )
    assert service.DUPLICATE_COMPANY_MESSAGE in str(repetido.value)

    with pytest.raises(InvalidDataError) as curto:
        service.create_supplier(
            sessao,
            user=cenario.mario,
            data=novo_fornecedor(name="Ab"),
            reference_date=REFERENCIA,
        )
    assert "pelo menos" in str(curto.value)


def test_a_mudanca_de_situacao_exige_justificativa(sessao: Session, cenario: Cenario) -> None:
    with pytest.raises(InvalidDataError) as sem:
        service.save_qualification(
            sessao,
            user=cenario.mario,
            company_id=cenario.qualificada.id,
            data=qualificacao(
                situation="Restrito",
                observation="Certificados divergentes no recebimento.",
                justification="",
            ),
            reference_date=REFERENCIA,
        )
    assert validation.JUSTIFICATION_REQUIRED in str(sem.value)

    resultado = service.save_qualification(
        sessao,
        user=cenario.mario,
        company_id=cenario.qualificada.id,
        data=qualificacao(
            situation="Restrito",
            observation="Certificados divergentes no recebimento.",
            justification="Certificados de válvulas divergentes no recebimento (RNC-0003).",
        ),
        reference_date=REFERENCIA,
    )

    fornecedor = sessao.get(Supplier, cenario.fornecedor.id)
    assert resultado.created is False
    assert fornecedor is not None and fornecedor.situation == "Restrito"
    mudancas = sessao.scalars(
        select(SupplierHistory)
        .where(SupplierHistory.supplier_id == fornecedor.id)
        .order_by(SupplierHistory.id)
    ).all()
    assert (mudancas[-1].from_situation, mudancas[-1].to_situation) == ("Qualificado", "Restrito")
    assert mudancas[-1].by_id == cenario.mario.person_id


def test_restrito_sem_motivo_nem_justificativa_e_recusado(
    sessao: Session, cenario: Cenario
) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        service.save_qualification(
            sessao,
            user=cenario.mario,
            company_id=cenario.qualificada.id,
            data=qualificacao(situation="Restrito", observation="", justification=""),
            reference_date=REFERENCIA,
        )

    detail = recusa.value.detail
    assert isinstance(detail, dict)
    assert validation.REASON_REQUIRED in detail.values()
    assert validation.JUSTIFICATION_REQUIRED in detail.values()


def test_qualificado_sem_validade_e_validade_vencida_sao_recusados(
    sessao: Session, cenario: Cenario
) -> None:
    with pytest.raises(InvalidDataError) as sem:
        service.save_qualification(
            sessao,
            user=cenario.mario,
            company_id=cenario.qualificada.id,
            data=qualificacao(validity=None),
            reference_date=REFERENCIA,
        )
    assert validation.VALIDITY_REQUIRED in str(sem.value)

    with pytest.raises(InvalidDataError) as vencida:
        service.save_qualification(
            sessao,
            user=cenario.mario,
            company_id=cenario.qualificada.id,
            data=qualificacao(validity=date(2026, 9, 24)),
            reference_date=REFERENCIA,
        )
    assert validation.VALIDITY_IN_THE_PAST in str(vencida.value)


def test_a_versao_desatualizada_recusa_a_qualificacao(sessao: Session, cenario: Cenario) -> None:
    with pytest.raises(VersionConflictError):
        service.save_qualification(
            sessao,
            user=cenario.mario,
            company_id=cenario.qualificada.id,
            data=qualificacao(version=99, observation="Contato atualizado."),
            reference_date=REFERENCIA,
        )


def test_a_mesma_situacao_nao_gera_historico(sessao: Session, cenario: Cenario) -> None:
    service.save_qualification(
        sessao,
        user=cenario.mario,
        company_id=cenario.qualificada.id,
        data=qualificacao(observation="Contato atualizado."),
        reference_date=REFERENCIA,
    )

    fornecedor = sessao.get(Supplier, cenario.fornecedor.id)
    assert fornecedor is not None
    assert (
        len(
            sessao.scalars(
                select(SupplierHistory).where(SupplierHistory.supplier_id == fornecedor.id)
            ).all()
        )
        == 1
    )


# ── A avaliação final do contrato (D9) ───────────────────────────────────


def _avaliacao_final(
    sessao: Session,
    cenario: Cenario,
    *,
    notas: dict[str, int],
    periodo: str,
    contrato: Contract | None = None,
    armazenamento: ArmazenamentoEmMemoria | None = None,
):
    form = {"periodo": periodo, "tipo": "Final", "comentario": ""}
    form.update({criterio: str(nota) for criterio, nota in notas.items()})
    return financeiro.create_evaluation(
        sessao,
        user=cenario.gil,
        scope=_scope(cenario),
        contract_id=(contrato or cenario.contrato).id,
        form=form,
        reference_date=REFERENCIA,
        file_name="evidencia.pdf" if armazenamento else None,
        content=b"%PDF-1.7 evidencia" if armazenamento else b"",
        storage=armazenamento,
    )


def test_a_avaliacao_final_de_classe_a_requalifica(sessao: Session, cenario: Cenario) -> None:
    fornecedor = sessao.get(Supplier, cenario.fornecedor.id)
    assert fornecedor is not None
    fornecedor.situation = "Restrito"
    fornecedor.version += 1
    sessao.flush()

    _avaliacao_final(sessao, cenario, notas=dict.fromkeys(EVALUATION_WEIGHTS, 5), periodo="2026-09")

    assert fornecedor.situation == "Qualificado"
    historico = sessao.scalars(
        select(SupplierHistory)
        .where(SupplierHistory.supplier_id == fornecedor.id)
        .order_by(SupplierHistory.id)
    ).all()
    assert historico[-1].to_situation == "Qualificado"
    assert "CT-2026-900" in historico[-1].justification
    assert "(classe A)" in historico[-1].justification


def test_a_avaliacao_final_de_classe_d_bloqueia(sessao: Session, cenario: Cenario) -> None:
    _avaliacao_final(
        sessao,
        cenario,
        notas=dict.fromkeys(EVALUATION_WEIGHTS, 1),
        periodo="2026-09",
        armazenamento=ArmazenamentoEmMemoria(),
    )

    fornecedor = sessao.get(Supplier, cenario.fornecedor.id)
    assert fornecedor is not None and fornecedor.situation == "Bloqueado"


def test_a_avaliacao_mensal_nao_mexe_na_qualificacao(sessao: Session, cenario: Cenario) -> None:
    form = {
        "periodo": "2026-09",
        "tipo": "Mensal",
        "comentario": "",
        "hse": "5",
        "qualidade": "5",
        "prazo": "5",
        "gestao": "5",
        "recursos": "5",
        "documentacao": "5",
    }
    financeiro.create_evaluation(
        sessao,
        user=cenario.gil,
        scope=_scope(cenario),
        contract_id=cenario.contrato.id,
        form=form,
        reference_date=REFERENCIA,
    )

    fornecedor = sessao.get(Supplier, cenario.fornecedor.id)
    assert fornecedor is not None and fornecedor.situation == "Qualificado"
    assert (
        len(
            sessao.scalars(
                select(SupplierHistory).where(SupplierHistory.supplier_id == fornecedor.id)
            ).all()
        )
        == 1
    )


def test_a_avaliacao_final_de_empresa_sem_qualificacao_nao_cria_cadastro(
    sessao: Session, cenario: Cenario
) -> None:
    contrato = Contract(
        project_id=cenario.projeto.id,
        company_id=cenario.sem_qualificacao.id,
        manager_id=cenario.gil.person_id,
        fiscal_id=cenario.gil.person_id,
        number="CT-2026-902",
        object="Serviço da empresa sem cadastro",
        modality="Preço unitário",
        original_value_cents=1_000_000,
        start=date(2026, 2, 1),
        original_end=date(2027, 2, 1),
        current_end=date(2027, 2, 1),
        retention_pct=5,
        claim_notice_days=30,
        situation="Em execução",
        version=1,
    )
    sessao.add(contrato)
    sessao.flush()

    _avaliacao_final(
        sessao,
        cenario,
        notas={"hse": 2, "qualidade": 3, "prazo": 3, "gestao": 3, "recursos": 3, "documentacao": 3},
        periodo="2026-09",
        contrato=contrato,
        armazenamento=ArmazenamentoEmMemoria(),
    )

    assert (
        sessao.scalars(
            select(Supplier).where(Supplier.company_id == cenario.sem_qualificacao.id)
        ).one_or_none()
        is None
    )


def test_o_visualizador_nao_grava(sessao: Session, cenario: Cenario) -> None:
    with pytest.raises(AccessDeniedError):
        service.save_qualification(
            sessao,
            user=cenario.vera,
            company_id=cenario.qualificada.id,
            data=qualificacao(),
            reference_date=REFERENCIA,
        )
