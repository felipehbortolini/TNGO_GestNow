"""O risco sugerido pelo diligenciamento (ISSUE-067, D9).

O pedido crítico propõe um risco pelo modal; a fachada de Suprimentos chama a fachada da Riscos,
na mesma transação: o risco entra Em análise, com a categoria Suprimentos > Fornecedores, a origem
``Diligenciamento PED-...``, a dimensão Prazo, o impacto em prazo da folga negativa e a avaliação
inerente com o texto da linha do tempo. A ficha do pedido passa a mostrar o risco, resolvido pela
origem; o mesmo pedido não sugere duas vezes e o Visualizador não registra.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.scope import Scope
from src.modulos.riscos import ficha_service
from src.modulos.riscos import service as riscos
from src.modulos.riscos.models import Risk
from src.modulos.suprimentos import service, validation
from tests.apoio_diligenciamento import (
    ORDER_NUMBER,
    CenarioDiligenciamento,
    montar_cenario_diligenciamento,
    tornar_critico,
)
from tests.apoio_pacotes import REFERENCIA


@pytest.fixture
def cenario(sessao) -> CenarioDiligenciamento:
    """O pedido emitido do cenário do processo, no projeto 1."""
    return montar_cenario_diligenciamento(sessao)


def _scope(cenario: CenarioDiligenciamento) -> Scope:
    return Scope(project_id=cenario.projeto.id, source="url")


def _registrar(sessao, cenario: CenarioDiligenciamento, **campos: object) -> service.OrderSave:
    base: dict[str, object] = {
        "title": "Atraso na entrega dos transformadores compromete a montagem",
        "owner_id": cenario.ana.person_id,
        "probability": 4,
        "impact": 4,
        "cost_cents": 5_000_000,
        "cause": "Fabricação atrasada no fornecedor Alfa Fornecimentos de teste.",
        "consequence": "Frente de montagem parada aguardando o equipamento.",
    }
    base.update(campos)
    return service.register_suggested_risk(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        order_id=cenario.pedido.id,
        data=validation.SuggestedRiskInput(**base),  # type: ignore[arg-type]
        reference_date=REFERENCIA,
    )


def test_o_risco_sugerido_entra_em_analise_com_a_avaliacao_inerente(
    sessao, cenario: CenarioDiligenciamento
) -> None:
    tornar_critico(cenario, sessao)

    defaults = service.suggested_risk_defaults(
        sessao, scope=_scope(cenario), order_id=cenario.pedido.id
    )
    assert defaults.slack_days == -29, "o ROS de 01/12 contra a previsão de 30/12"
    assert defaults.impact == 4, "folga abaixo de -14 eleva o impacto de partida"
    assert defaults.owner_id is not None, "o comprador do pacote é o dono de partida"

    saved = _registrar(sessao, cenario)

    assert saved.risk_code.startswith("RSK-"), "o código do projeto"
    risk = sessao.scalars(select(Risk).where(Risk.code == saved.risk_code)).one()
    assert risk.situation == "Em análise"
    assert risk.origin_type == "Diligenciamento"
    assert risk.origin == f"Diligenciamento {ORDER_NUMBER}"
    assert risk.dimension == "Prazo"
    assert risk.schedule_impact_days == 29, "max(0, -folga)"
    assert risk.trigger == "Previsão de entrega depois do ROS."
    assert risk.cadence_days is not None, "a cadência sai da severidade"

    linha = riscos.find_risk(
        sessao, user=cenario.ana, code=saved.risk_code, reference_date=REFERENCIA
    )
    assert linha is not None
    assert linha.inherent is not None
    assert linha.inherent.dimensions["prazo"] == 4, "a avaliação inerente tem a dimensão prazo"
    assert linha.category_group == "Suprimentos"
    assert linha.category_name == "Fornecedores"

    sheet = ficha_service.find_risk_sheet(
        sessao, user=cenario.ana, code=saved.risk_code, reference_date=REFERENCIA
    )
    assert sheet is not None
    assert sheet.reviews[-1].kind == "inerente"
    assert sheet.reviews[-1].body == "Avaliação inicial a partir do diligenciamento."
    assert any(
        linha.text.startswith("Risco criado pelo diligenciamento do pedido")
        for linha in sheet.history
    ), "o histórico guarda o texto do protótipo"

    ordem = service.find_order(
        sessao,
        user=cenario.ana,
        scope=_scope(cenario),
        order_id=cenario.pedido.id,
        reference_date=REFERENCIA,
    )
    assert ordem is not None
    assert ordem.risk is not None
    assert ordem.risk.code == saved.risk_code, "a ficha do pedido resolve o risco pela origem"


def test_o_mesmo_pedido_nao_sugere_dois_riscos(sessao, cenario: CenarioDiligenciamento) -> None:
    tornar_critico(cenario, sessao)
    _registrar(sessao, cenario)

    with pytest.raises(InvalidDataError) as recusa:
        _registrar(sessao, cenario)

    assert any("Já existe risco sugerido" in msg for msg in recusa.value.messages())
    assert len(sessao.scalars(select(Risk)).all()) == 1


def test_o_visualizador_nao_registra_o_risco_sugerido(
    sessao, cenario: CenarioDiligenciamento
) -> None:
    tornar_critico(cenario, sessao)

    with pytest.raises(AccessDeniedError):
        service.register_suggested_risk(
            sessao,
            user=cenario.vitor,
            scope=_scope(cenario),
            order_id=cenario.pedido.id,
            data=validation.SuggestedRiskInput(
                title="Atraso na entrega dos transformadores compromete a montagem",
                owner_id=cenario.ana.person_id,
                probability=4,
                impact=4,
            ),
            reference_date=REFERENCIA,
        )

    assert sessao.scalars(select(Risk)).all() == []
