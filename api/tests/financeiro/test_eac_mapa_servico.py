"""Fachada do mapa de controle, da projeção no término e dos custos do ERP (ISSUE-031).

A projeção de um item entra como fato manual com justificativa e histórico; sem justificativa é
recusada e nada grava. A importação do ERP grava comprometido, realizado e projeção por item e mês,
substituindo o mês reimportado. O mapa traz as três fórmulas — orçado atual = orçado + remanejamentos,
saldo a comprometer = orçado atual menos comprometido e desvio = projeção menos orçado atual, com o
positivo sendo sobrecusto —, a faixa do mapa de calor pelos parâmetros vigentes e a carteira com um
registro por projeto.

O oráculo afirma a projeção no término do projeto 1 da demonstração: o mock do protótipo fecha
``curvaFinanceira.projecao`` em 4.525.500.000 centavos (R$ 45,255 mi), que é a soma das projeções
por item; apresentada em milhões com duas casas, ela é os R$ 45,26 mi do cenário.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.carga import plataforma, prototype_collection
from src.carga.registro import DEMO_ANCHOR
from src.core import recording
from src.core.errors import InvalidDataError
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.models import Project
from src.modulos.financeiro import calculations, seed, service, validation
from src.modulos.financeiro.models import EacProjection, EacReallocation, ErpCost
from tests.financeiro.conftest import REFERENCE_DATE, EacScenario

D = Decimal
HOJE = REFERENCE_DATE
PORTFOLIO = Scope(project_id=None, source="padrao")
MOCK_PROJECT = 1
PROJECT_CODE = "TN-2026-014"
PROJECTION_TOTAL_CENTS = 4_525_500_000
PROJECTION_TOTAL_MI = D("45.26")
JUSTIFICATIVA = "Premissas revisadas com o fornecedor."


def _escopo(project: Project) -> Scope:
    return Scope(project_id=project.id, source="url")


def _mapa(cenario: EacScenario, scope: Scope | None = None) -> service.MapaControleView:
    return service.mapa_controle(
        cenario.session, scope=scope or _escopo(cenario.first), reference_date=HOJE
    )


def _linha(view: service.MapaControleView, code: str) -> service.MapaRow:
    return next(row for row in view.rows if row.code == code)


def _item(cenario: EacScenario, code: str) -> int:
    return cenario.items[f"TN-EAC-001:{code}"]


def _remanejado(cenario: EacScenario, *, origin: str, target: str, value_cents: int) -> None:
    recording.create(
        cenario.session,
        user_id=cenario.member.id,
        record=EacReallocation(
            project_id=cenario.first.id,
            source_item_id=_item(cenario, origin),
            target_item_id=_item(cenario, target),
            applied_by_id=cenario.member.person_id,
            revision=0,
            applied_on=HOJE,
            value_cents=value_cents,
            new_item=False,
            justification="Remanejamento aplicado no teste do mapa.",
        ),
    )


# ── Projeção no término ──────────────────────────────────────────────────


def test_projecao_grava_historico_e_aparece_no_mapa(cenario: EacScenario) -> None:
    item_id = _item(cenario, "1.1.1")

    view = service.update_projection(
        cenario.session,
        item_id=item_id,
        valor_centavos=1_050_000,
        justificativa=JUSTIFICATIVA,
        autor_id=cenario.member.person_id,
        hoje=HOJE,
    )

    assert (view.item_id, view.value_cents, view.origin) == (
        item_id,
        1_050_000,
        calculations.MANUAL_ORIGIN,
    )
    assert view.on == HOJE
    assert view.author == "Maria Membro"
    (record,) = cenario.session.scalars(select(EacProjection)).all()
    assert (record.author_id, record.justification) == (cenario.member.person_id, JUSTIFICATIVA)

    depois = service.update_projection(
        cenario.session,
        item_id=item_id,
        valor_centavos=1_100_000,
        justificativa="Segunda premissa revisada.",
        autor_id=cenario.member.person_id,
        hoje=date(2026, 9, 28),
    )

    assert depois.value_cents == 1_100_000
    assert len(cenario.session.scalars(select(EacProjection)).all()) == 2
    linha = _linha(_mapa(cenario), "1.1.1")
    assert linha.projection_cents == 1_100_000
    assert linha.deviation_cents == 100_000


def test_projecao_sem_justificativa_e_recusada_e_nada_grava(cenario: EacScenario) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        service.update_projection(
            cenario.session,
            item_id=_item(cenario, "1.1.1"),
            valor_centavos=1_000_000,
            justificativa="   ",
            autor_id=cenario.member.person_id,
            hoje=HOJE,
        )

    assert "justificativa da projeção" in recusa.value.detail[validation.FIELD_JUSTIFICATION]
    assert cenario.session.scalars(select(EacProjection)).all() == []


def test_projecao_abaixo_do_realizado_do_erp_e_recusada(cenario: EacScenario) -> None:
    item_id = _item(cenario, "1.1.1")
    service.import_erp_costs(
        cenario.session,
        projeto_id=cenario.first.id,
        linhas=(
            service.ErpCostLine(item_id=item_id, month=date(2026, 8, 1), actual_cents=900_000),
        ),
        importado_por_id=cenario.member.person_id,
        hoje=HOJE,
    )

    with pytest.raises(InvalidDataError) as recusa:
        service.update_projection(
            cenario.session,
            item_id=item_id,
            valor_centavos=800_000,
            justificativa=JUSTIFICATIVA,
            autor_id=cenario.member.person_id,
            hoje=HOJE,
        )

    assert "menor que o realizado" in recusa.value.detail[validation.FIELD_PROJECTION]


# ── Custos do ERP ────────────────────────────────────────────────────────


def test_importacao_de_custos_grava_e_substitui_por_item_e_mes(cenario: EacScenario) -> None:
    item_a = _item(cenario, "1.1.1")
    item_b = _item(cenario, "2.1.1")

    gravados = service.import_erp_costs(
        cenario.session,
        projeto_id=cenario.first.id,
        linhas=(
            service.ErpCostLine(
                item_id=item_a,
                month=date(2026, 8, 15),
                committed_cents=400_000,
                actual_cents=300_000,
                projection_cents=1_200_000,
            ),
            service.ErpCostLine(item_id=item_b, month=date(2026, 8, 1), committed_cents=5_000_000),
        ),
        importado_por_id=cenario.member.person_id,
        hoje=HOJE,
    )

    assert gravados == 2
    rows = cenario.session.scalars(select(ErpCost).order_by(ErpCost.item_id, ErpCost.month)).all()
    assert [(row.item_id, row.month) for row in rows] == [
        (item_a, date(2026, 8, 1)),
        (item_b, date(2026, 8, 1)),
    ]
    assert rows[0].imported_at is not None

    service.import_erp_costs(
        cenario.session,
        projeto_id=cenario.first.id,
        linhas=(
            service.ErpCostLine(
                item_id=item_a,
                month=date(2026, 8, 20),
                committed_cents=450_000,
                actual_cents=320_000,
                projection_cents=1_250_000,
            ),
        ),
        importado_por_id=cenario.member.person_id,
        hoje=HOJE,
    )

    (substituido,) = cenario.session.scalars(select(ErpCost).where(ErpCost.item_id == item_a)).all()
    assert (
        substituido.month,
        substituido.committed_cents,
        substituido.actual_cents,
        substituido.projection_cents,
    ) == (date(2026, 8, 1), 450_000, 320_000, 1_250_000)
    assert substituido.imported_at >= rows[0].imported_at


def test_importacao_recusa_item_fora_do_nivel_3_e_mes_futuro(cenario: EacScenario) -> None:
    with pytest.raises(InvalidDataError) as pacote:
        service.import_erp_costs(
            cenario.session,
            projeto_id=cenario.first.id,
            linhas=(
                service.ErpCostLine(
                    item_id=_item(cenario, "1.1"), month=date(2026, 8, 1), committed_cents=1
                ),
            ),
            importado_por_id=cenario.member.person_id,
            hoje=HOJE,
        )
    assert "nível 3" in pacote.value.detail[validation.FIELD_ERP_ITEM]

    with pytest.raises(InvalidDataError) as futuro:
        service.import_erp_costs(
            cenario.session,
            projeto_id=cenario.first.id,
            linhas=(
                service.ErpCostLine(
                    item_id=_item(cenario, "1.1.1"), month=date(2026, 10, 1), committed_cents=1
                ),
            ),
            importado_por_id=cenario.member.person_id,
            hoje=HOJE,
        )
    assert "mês futuro" in futuro.value.detail[validation.FIELD_ERP_MONTH]
    assert cenario.session.scalars(select(ErpCost)).all() == []


# ── As colunas do mapa ───────────────────────────────────────────────────


def test_as_tres_formulas_do_mapa_com_numeros_conferidos_a_mao(cenario: EacScenario) -> None:
    _remanejado(cenario, origin="2.1.1", target="1.1.1", value_cents=100_000)
    service.import_erp_costs(
        cenario.session,
        projeto_id=cenario.first.id,
        linhas=(
            service.ErpCostLine(
                item_id=_item(cenario, "1.1.1"),
                month=date(2026, 8, 1),
                committed_cents=400_000,
                actual_cents=300_000,
                projection_cents=1_200_000,
            ),
            service.ErpCostLine(
                item_id=_item(cenario, "1.1.2"),
                month=date(2026, 8, 1),
                committed_cents=500,
                actual_cents=500,
                projection_cents=900,
            ),
            service.ErpCostLine(
                item_id=_item(cenario, "2.1.1"),
                month=date(2026, 8, 1),
                committed_cents=5_000_000,
                actual_cents=4_000_000,
                projection_cents=5_500_000,
            ),
        ),
        importado_por_id=cenario.member.person_id,
        hoje=HOJE,
    )

    view = _mapa(cenario)

    linha = _linha(view, "1.1.1")
    assert (linha.baseline_cents, linha.reallocation_cents, linha.current_cents) == (
        1_000_000,
        100_000,
        1_100_000,
    )
    assert (linha.committed_cents, linha.actual_cents, linha.saldo_cents) == (
        400_000,
        300_000,
        700_000,
    )
    assert (linha.projection_cents, linha.deviation_cents, linha.deviation_percent) == (
        1_200_000,
        100_000,
        D("9.1"),
    )
    assert (linha.band.key, linha.band.tone) == ("sobrecusto-2", "erro")

    pacote = _linha(view, "1.1")
    assert (pacote.baseline_cents, pacote.current_cents, pacote.projection_cents) == (
        1_001_000,
        1_101_000,
        1_200_900,
    )

    outra = _linha(view, "2.1.1")
    assert (outra.baseline_cents, outra.reallocation_cents, outra.current_cents) == (
        6_000_000,
        -100_000,
        5_900_000,
    )
    assert (outra.deviation_cents, outra.deviation_percent) == (-400_000, D("-6.8"))
    assert (outra.band.key, outra.band.tone) == ("economia-2", "ok")

    assert view.total.baseline_cents == 7_001_000
    assert view.total.reallocation_cents == 0
    assert view.total.current_cents == 7_001_000
    assert view.total.committed_cents == 5_400_500
    assert view.total.projection_cents == 6_700_900
    assert view.total.deviation_cents == -300_100


def test_faixa_do_mapa_muda_quando_o_parametro_muda(cenario: EacScenario) -> None:
    session = cenario.session
    configuracoes.seed_initial_parameters(
        session, author_id=cenario.member.id, effective_from=date(2026, 1, 1)
    )
    service.import_erp_costs(
        session,
        projeto_id=cenario.first.id,
        linhas=(
            service.ErpCostLine(
                item_id=_item(cenario, "1.1.1"),
                month=date(2026, 8, 1),
                projection_cents=1_020_000,
            ),
        ),
        importado_por_id=cenario.member.person_id,
        hoje=HOJE,
    )

    linha = _linha(_mapa(cenario), "1.1.1")
    assert linha.deviation_percent == D("2.0")
    assert linha.band.key == "sobrecusto-1"

    configuracoes.save_parameter_group(
        session,
        author_id=cenario.member.id,
        group="financeiro",
        values={
            "faixasDesvio": [3, 5, 10],
            "contingencia": {"toleranciaConsumoPP": 10, "coberturaMinimaPct": 100},
        },
        effective_from=date(2026, 9, 1),
        justification="Ajuste das faixas do desvio do mapa.",
    )

    view = _mapa(cenario)
    assert view.bands == (D("3"), D("5"), D("10"))
    assert _linha(view, "1.1.1").band.key == "neutro"


def test_carteira_tem_um_registro_por_projeto(cenario: EacScenario) -> None:
    sem_eac = Project(
        client_id=cenario.first.client_id,
        manager_id=cenario.first.manager_id,
        code="TN-SEM-EAC-MAPA",
        name="Sem EAC",
    )
    cenario.session.add(sem_eac)
    cenario.session.flush()

    view = _mapa(cenario, PORTFOLIO)

    assert view.is_portfolio
    assert view.scope_label == "Portfólio"
    assert [row.project_id for row in view.rows] == [cenario.first.id, cenario.second.id]
    assert all(row.level == 1 for row in view.rows)
    assert view.rows[0].description == "TN-EAC-001 · Fábrica de teste"
    assert view.total.description == "Portfólio de projetos"
    assert view.total.baseline_cents == 12_001_000
    assert view.total.projection_cents == 12_001_000


# ── O oráculo da projeção ────────────────────────────────────────────────


def test_o_total_de_projecao_do_projeto_1_da_demonstracao_fecha_45_26_mi(
    db_session: Session,
) -> None:
    plataforma.load(db_session, DEMO_ANCHOR)
    seed.load(db_session, DEMO_ANCHOR)
    admin = configuracoes.find_access_by_email(db_session, plataforma.ADMIN_EMAIL)
    assert admin is not None
    project = db_session.scalars(select(Project).where(Project.code == PROJECT_CODE)).one()
    leaves = {
        source["codigo"]: int(source["projecao"])
        for source in prototype_collection("eac")
        if source["projetoId"] == MOCK_PROJECT and source["nivel"] == calculations.LEAF_LEVEL
    }
    ids = service.eac_item_ids_by_code(db_session, project_id=project.id, codes=list(leaves))
    assert len(ids) == len(leaves)

    for code, item_id in ids.items():
        service.update_projection(
            db_session,
            item_id=item_id,
            valor_centavos=leaves[code],
            justificativa="Projeção da carga de demonstração.",
            autor_id=admin.person_id,
            hoje=DEMO_ANCHOR,
        )

    view = service.mapa_controle(
        db_session,
        scope=Scope(project_id=project.id, source="url"),
        reference_date=DEMO_ANCHOR,
    )

    assert sum(leaves.values()) == PROJECTION_TOTAL_CENTS
    assert view.total.projection_cents == PROJECTION_TOTAL_CENTS
    millions = (D(view.total.projection_cents) / D(100_000_000)).quantize(
        D("0.01"), rounding=ROUND_HALF_UP
    )
    assert millions == PROJECTION_TOTAL_MI
