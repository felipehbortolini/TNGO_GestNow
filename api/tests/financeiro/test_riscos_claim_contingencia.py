"""Integrações que chegam aos riscos pelo Financeiro (ISSUE-067, D9).

O claim grava o ``risco_id`` pela fachada da Riscos e o vínculo aparece nos dois sentidos (a
tabela do contrato e a ficha do risco, lidas por fachada); o risco de outro projeto é recusado.
A cobertura da contingência é o saldo sobre o VME das ameaças ativas, lido pela fachada da Riscos,
contra a meta do grupo ``financeiro``: os riscos não-ameaça e os encerrados ficam fora e o alerta
aparece abaixo da meta.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pytest
from sqlalchemy import select

from src.core.errors import InvalidDataError
from src.core.rbac import GeneralProfile, User
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.financeiro import calculations, service, validation
from src.modulos.financeiro.models import Contract, ContractClaim, Reserve, ReserveMovement
from src.modulos.riscos import ficha_service
from src.modulos.riscos import service as riscos
from src.modulos.riscos import validation as riscos_validation
from src.modulos.riscos.models import RiskCategory
from tests.financeiro.conftest import REFERENCE_DATE, EacScenario, user_of
from tests.identidades import criar_empresa

HOJE = REFERENCE_DATE
ORIGINAL_CENTS = 100_000_000
CONTRACT_END = date(2026, 10, 30)


@pytest.fixture(autouse=True)
def parametros(cenario: EacScenario) -> None:
    """A versão 1 dos parâmetros, que o risco e a contingência leem (a meta vem do financeiro)."""
    configuracoes.seed_initial_parameters(
        cenario.session, author_id=cenario.member.id, effective_from=date(2026, 1, 1)
    )


def _escopo(cenario: EacScenario) -> Scope:
    return Scope(project_id=cenario.first.id, source="url")


def _membro(cenario: EacScenario) -> User:
    return user_of(cenario.member, cenario.session, GeneralProfile.MEMBER)


def _gestor(cenario: EacScenario) -> User:
    return user_of(cenario.manager, cenario.session, GeneralProfile.MANAGER)


def _criar_contrato(cenario: EacScenario) -> Contract:
    session = cenario.session
    empresa = criar_empresa(session, "Contratada das integrações")
    contract = Contract(
        project_id=cenario.first.id,
        company_id=empresa.id,
        eac_item_id=cenario.items["TN-EAC-001:1.1.1"],
        manager_id=cenario.responsible.id,
        fiscal_id=cenario.responsible.id,
        number="CT-2026-900",
        object="Obra das integrações",
        modality="Preço unitário",
        original_value_cents=ORIGINAL_CENTS,
        start=date(2026, 1, 5),
        original_end=CONTRACT_END,
        current_end=CONTRACT_END,
        retention_pct=5,
        claim_notice_days=30,
        situation="Em execução",
    )
    session.add(contract)
    session.flush()
    return contract


def _categoria(cenario: EacScenario) -> int:
    existente = cenario.session.scalars(select(RiskCategory).limit(1)).first()
    if existente is not None:
        return existente.id
    category = RiskCategory(group="Técnico", name="Prazo")
    cenario.session.add(category)
    cenario.session.flush()
    return category.id


def _criar_risco(
    cenario: EacScenario,
    *,
    nature: str = "Ameaça",
    project_id: int | None = None,
) -> str:
    """Um risco pela fachada da Riscos, avaliado com P3 x I4 e R$ 100 mil de impacto em custo."""
    project = project_id or cenario.first.id
    result = riscos.save_risk(
        cenario.session,
        user=_membro(cenario),
        data=riscos_validation.RiskInput(
            nature=nature,
            category_id=_categoria(cenario),
            cause="Atraso na liberação dos desenhos de detalhamento.",
            title="Atraso na liberação dos desenhos",
            consequence="A montagem mecânica atrasa e o comissionamento escorrega.",
            owner_id=cenario.member.person_id,
            identified_on=HOJE,
            origin_type="Manual",
            project_id=project,
        ),
        reference_date=HOJE,
    )
    riscos.assess_risk(
        cenario.session,
        user=_membro(cenario),
        code=result.code,
        data=riscos_validation.AssessmentInput(
            kind="inerente",
            probability=3,
            impact=4,
            dimensions={"prazo": 4, "custo": 2},
            cost_impact_cents=10_000_000,
        ),
        reference_date=HOJE,
    )
    return result.code


def _reservar(cenario: EacScenario, *, value_cents: int) -> None:
    reserve = Reserve(
        project_id=cenario.first.id,
        kind=calculations.RESERVE_CONTINGENCY,
        calculation_basis="Constituída na linha de base do projeto.",
    )
    cenario.session.add(reserve)
    cenario.session.flush()
    cenario.session.add(
        ReserveMovement(
            reserve_id=reserve.id,
            change_id=None,
            registered_by_id=cenario.member.person_id,
            kind=calculations.MOVEMENT_CONSTITUTION,
            registered_on=date(2026, 1, 5),
            value_cents=value_cents,
            justification="Constituída na linha de base do projeto.",
        )
    )
    cenario.session.flush()


def _visao(cenario: EacScenario) -> service.ContingencyOverview:
    return service.contingency_overview(
        cenario.session, user=_membro(cenario), scope=_escopo(cenario), reference_date=HOJE
    )


def _form_claim(**extra: str) -> dict[str, str]:
    form = {
        "direcao": "Da contratada",
        "tipo": "Custo",
        "causa": "Outros",
        "clausula": "18.1",
        "descricao": "Back-charge do retrabalho de solda da linha.",
        "evento": "2026-08-19",
        "notificacao": "2026-08-26",
        "valor": "34.000,00",
        "dias": "0",
    }
    form.update(extra)
    return form


# ── Claim ↔ risco ────────────────────────────────────────────────────────


def test_o_claim_grava_o_risco_e_o_vinculo_aparece_nos_dois_sentidos(
    cenario: EacScenario,
) -> None:
    contract = _criar_contrato(cenario)
    code = _criar_risco(cenario)

    claim = service.create_claim(
        cenario.session,
        user=_gestor(cenario),
        scope=_escopo(cenario),
        contract_id=contract.id,
        form=_form_claim(risco=code),
    )

    assert claim.risk_code == code, "a visão do claim mostra o risco vinculado"
    row = cenario.session.scalars(select(ContractClaim)).one()
    assert row.risk_id is not None, "a FK risco_id é gravada pela fachada"

    ficha = service.contract_detail(cenario.session, user=_membro(cenario), contract_id=contract.id)
    assert ficha.claims[0].risk_code == code

    vinculos = service.claims_of_risk(cenario.session, risk_id=row.risk_id or 0)
    assert [item.code for item in vinculos] == [claim.code], "o risco mostra o claim pela fachada"

    sheet = ficha_service.find_risk_sheet(
        cenario.session, user=_membro(cenario), code=code, reference_date=HOJE
    )
    assert sheet is not None
    assert [item.code for item in sheet.claims] == [claim.code], (
        "a ficha do risco lista os claims vinculados"
    )


def test_o_claim_com_risco_de_outro_projeto_e_recusado(cenario: EacScenario) -> None:
    contract = _criar_contrato(cenario)
    outro = _criar_risco(cenario, project_id=cenario.second.id)

    with pytest.raises(InvalidDataError) as recusa:
        service.create_claim(
            cenario.session,
            user=_gestor(cenario),
            scope=_escopo(cenario),
            contract_id=contract.id,
            form=_form_claim(risco=outro),
        )

    assert recusa.value.detail == {"risco": validation.CLAIM_RISK_NOT_FOUND}
    assert cenario.session.scalars(select(ContractClaim)).all() == []


# ── Contingência ↔ cobertura ─────────────────────────────────────────────


def test_a_cobertura_usa_o_vme_das_ameacas_ativas(cenario: EacScenario) -> None:
    _reservar(cenario, value_cents=20_000_000)
    code = _criar_risco(cenario)
    _criar_risco(cenario, nature="Oportunidade")

    linha = riscos.find_risk(cenario.session, user=_membro(cenario), code=code, reference_date=HOJE)
    assert linha is not None

    view = _visao(cenario)

    assert linha.vme_cents > 0
    assert view.exposure_cents == linha.vme_cents, "só o VME da ameaça ativa entra na exposição"
    expected = (Decimal(20_000_000) / Decimal(linha.vme_cents) * 100).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )
    assert view.coverage_pct == expected, "saldo sobre a exposição"
    assert view.coverage_minimum_pct == 100, "a meta do grupo financeiro"
    assert [threat.code for threat in view.threats] == [code]
    assert view.alerts == (), "acima da meta, sem alerta de cobertura"


def test_o_risco_encerrado_sai_da_cobertura(cenario: EacScenario) -> None:
    _reservar(cenario, value_cents=20_000_000)
    code = _criar_risco(cenario)
    linha = riscos.find_risk(cenario.session, user=_membro(cenario), code=code, reference_date=HOJE)
    assert linha is not None

    view = _visao(cenario)
    assert view.exposure_cents == linha.vme_cents

    ficha_service.close_risk(
        cenario.session,
        user=_gestor(cenario),
        code=code,
        data=riscos_validation.ClosingInput(
            reason="Não se materializou",
            closed_on=HOJE,
            lesson="O acompanhamento semanal do fornecedor reduziu a exposição ao atraso.",
            version=linha.version,
        ),
        reference_date=HOJE,
    )

    depois = _visao(cenario)
    assert depois.exposure_cents == 0, "risco encerrado não é ameaça ativa"
    assert depois.coverage_pct is None, "sem exposição não há cobertura"
    assert depois.threats == ()


def test_a_meta_da_cobertura_vem_do_parametro(cenario: EacScenario) -> None:
    session = cenario.session
    _reservar(cenario, value_cents=5_000_000)
    _criar_risco(cenario)

    view = _visao(cenario)
    assert view.coverage_minimum_pct == 100

    configuracoes.save_parameter_group(
        session,
        author_id=cenario.member.id,
        group="financeiro",
        values={
            "faixasDesvio": [1, 5, 10],
            "contingencia": {"toleranciaConsumoPP": 10, "coberturaMinimaPct": 150},
        },
        effective_from=HOJE,
        justification="Ajuste da meta da cobertura da contingência.",
    )

    depois = _visao(cenario)
    assert depois.coverage_minimum_pct == 150
    kinds = [alert.kind for alert in depois.alerts]
    assert service.RESERVE_ALERT_COVERAGE in kinds, "abaixo da meta, o alerta aparece"
    texto = next(
        alert.text for alert in depois.alerts if alert.kind == service.RESERVE_ALERT_COVERAGE
    )
    assert "da exposição das ameaças ativas (meta 150%)" in texto
