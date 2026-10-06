"""Fachada da EAC (ISSUE-029, D5, D8): a árvore por escopo, a ponderação e o cadastro do item.

O que muda valor não está aqui (é da ISSUE-030). O cadastro do item dispensa SM, mas sem
justificativa é recusado, e com justificativa fica no histórico do item, junto da trilha.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from src.core import audit
from src.core.errors import AccessDeniedError, InvalidDataError, VersionConflictError
from src.core.models import AuditEntry
from src.core.rbac import GeneralProfile
from src.core.scope import Scope
from src.modulos.configuracoes import service as configuracoes
from src.modulos.configuracoes.models import Person, PortfolioWeight, Project
from src.modulos.financeiro import service
from src.modulos.financeiro.models import EacItem
from src.modulos.financeiro.service import EacFilters
from tests.financeiro.conftest import REFERENCE_DATE, EacScenario, user_of

D = Decimal
PORTFOLIO = Scope(project_id=None, source="padrao")


def _project_scope(project: Project) -> Scope:
    return Scope(project_id=project.id, source="url")


def _view(scenario: EacScenario, scope: Scope, filters: EacFilters | None = None, **kwargs):
    profile = kwargs.get("profile", GeneralProfile.MEMBER)
    collaborator = kwargs.get("collaborator", scenario.member)
    return service.eac_view(
        scenario.session,
        user=user_of(collaborator, scenario.session, profile),
        scope=scope,
        filters=filters or EacFilters(),
        reference_date=REFERENCE_DATE,
    )


def _form(**changes: str) -> dict[str, str]:
    form = {
        "descricao": "Engenharia civil",
        "tipo_custo": "Serviço",
        "classificacao": "CAPEX",
        "centro_custo": "CC-1",
        "justificativa": "Reclassificação pedida pelo controller.",
    }
    form.update(changes)
    return form


def _edit(
    scenario: EacScenario, item_code: str, form: dict[str, str], *, project: Project | None = None
):
    chosen = project or scenario.first
    item_id = scenario.items[f"{chosen.code}:{item_code}"]
    item = scenario.session.get(EacItem, item_id)
    assert item is not None
    form.setdefault("responsavel", str(scenario.responsible.id))
    form.setdefault("versao", str(item.version))
    return service.edit_item_registry(
        scenario.session,
        user=user_of(scenario.member, scenario.session, GeneralProfile.MEMBER),
        scope=_project_scope(chosen),
        item_id=item_id,
        form=form,
    )


# ── A árvore do projeto ──────────────────────────────────────────────────


def test_arvore_do_projeto_soma_os_totais_no_servidor_em_centavos(cenario: EacScenario) -> None:
    view = _view(cenario, _project_scope(cenario.first))

    by_code = {row.code: row for row in view.rows}
    assert by_code["0"].is_root
    assert by_code["0"].budget_cents == 7_001_000
    assert by_code["1"].budget_cents == 1_001_000
    assert by_code["1.1"].budget_cents == 1_001_000
    assert by_code["2"].budget_cents == 6_000_000
    assert by_code["1.1.2"].budget_cents == 1_000  # 2,5 x R$ 4,00
    assert by_code["1.1.1"].unit == "un"
    assert by_code["1.1.1"].responsible == "Maria Membro"
    assert view.summary.budget_cents == 7_001_000
    assert (view.summary.item_count, view.summary.package_count) == (3, 2)
    assert view.scope_label == "TN-EAC-001 · Fábrica de teste"


def test_arvore_do_projeto_so_traz_os_itens_do_proprio_projeto(cenario: EacScenario) -> None:
    view = _view(cenario, _project_scope(cenario.second))

    assert [row.code for row in view.rows] == ["0", "1", "1.1", "1.1.1"]
    assert view.rows[0].budget_cents == 5_000_000
    assert view.rows[0].description == "Caldeira de teste"


def test_projeto_sem_eac_e_vazio_de_origem(cenario: EacScenario) -> None:
    vazio = Project(
        client_id=cenario.first.client_id,
        manager_id=cenario.first.manager_id,
        code="TN-VAZIO",
        name="Vazio",
    )
    cenario.session.add(vazio)
    cenario.session.flush()

    view = _view(cenario, _project_scope(vazio))

    assert view.is_empty
    assert not view.has_no_match
    assert view.rows == ()


def test_filtro_que_esconde_tudo_e_vazio_por_filtro_e_nao_de_origem(cenario: EacScenario) -> None:
    view = _view(cenario, _project_scope(cenario.first), EacFilters(search="nada disso"))

    assert not view.is_empty
    assert view.has_no_match
    assert [row.code for row in view.rows] == ["0"]
    assert view.filtered_total_cents == 0


def test_filtro_de_busca_traz_o_total_filtrado(cenario: EacScenario) -> None:
    view = _view(cenario, _project_scope(cenario.first), EacFilters(search="bombas"))

    assert [row.code for row in view.rows] == ["0", "2", "2.1", "2.1.1"]
    assert view.filtered_total_cents == 6_000_000
    assert view.rows[0].budget_cents == 7_001_000  # a linha 0 mantém o total do projeto


def test_nivel_do_filtro_corta_a_profundidade_e_o_total_nao_muda(cenario: EacScenario) -> None:
    view = _view(cenario, _project_scope(cenario.first), EacFilters(level=1))

    assert [row.code for row in view.rows] == ["0", "1", "2"]
    assert view.filters.level == 1
    assert view.rows[0].budget_cents == 7_001_000


def test_gestor_e_membro_editam_e_visualizador_so_le(cenario: EacScenario) -> None:
    scope = _project_scope(cenario.first)

    assert _view(cenario, scope).can_edit
    assert _view(
        cenario, scope, profile=GeneralProfile.MANAGER, collaborator=cenario.manager
    ).can_edit
    assert not _view(
        cenario, scope, profile=GeneralProfile.VIEWER, collaborator=cenario.viewer
    ).can_edit


# ── A árvore da carteira ─────────────────────────────────────────────────


def test_carteira_tem_linha_zero_projeto_e_pacote_principal_e_so_leitura(
    cenario: EacScenario,
) -> None:
    view = _view(cenario, PORTFOLIO)

    assert view.is_portfolio
    assert not view.can_edit
    assert [(row.code, row.level) for row in view.rows] == [
        ("0", 0),
        ("1", 1),
        ("1.1", 2),
        ("1.2", 2),
        ("2", 1),
        ("2.1", 2),
    ]
    root, first, _, _, second, _ = view.rows
    assert root.description == "Portfólio de projetos"
    assert root.budget_cents == 12_001_000
    assert first.description == "TN-EAC-001 · Fábrica de teste"  # código · nome
    assert (first.budget_cents, second.budget_cents) == (7_001_000, 5_000_000)
    assert all(row.item_id is None for row in view.rows)  # nada de item: não há o que editar


def test_carteira_limita_a_profundidade_ao_pacote_principal(cenario: EacScenario) -> None:
    view = _view(cenario, PORTFOLIO, EacFilters(level=3))

    assert view.max_level == 2
    assert view.filters.level == 2
    assert max(row.level for row in view.rows) == 2


def test_carteira_traz_o_gerente_do_projeto_como_responsavel_da_linha_do_projeto(
    cenario: EacScenario,
) -> None:
    view = _view(cenario, PORTFOLIO)

    assert view.rows[1].responsible == "Gerente TN-EAC-001"


def test_carteira_traz_o_peso_do_projeto_na_linha_do_projeto(cenario: EacScenario) -> None:
    view = _view(cenario, PORTFOLIO)

    projects = [row for row in view.rows if row.level == 1]
    assert sum(row.weight for row in projects) == D(100)
    # sem parâmetro de ponderação o único critério é o orçamento vigente da EAC
    assert [row.weight for row in projects] == [D("58.34"), D("41.66")]


# ── Ponderação ───────────────────────────────────────────────────────────


def test_ponderacao_sem_parametro_usa_so_o_orcamento_vigente_da_eac(cenario: EacScenario) -> None:
    weights = service.portfolio_weights(cenario.session, reference_date=REFERENCE_DATE)

    # 7.001.000 / 12.001.000 = 58,3368%: o piso soma 99,99 e o centavo que falta vai ao maior resto
    assert weights[cenario.first.id].weight == D("58.34")
    assert weights[cenario.second.id].weight == D("41.66")
    assert sum(value.weight for value in weights.values()) == D(100)


def test_ponderacao_com_os_parametros_e_as_notas_da_versao_vigente(cenario: EacScenario) -> None:
    session = cenario.session
    configuracoes.seed_initial_parameters(
        session, author_id=cenario.member.id, effective_from=date(2026, 1, 1)
    )
    portfolio_version = configuracoes.current_version(
        session, group="portfolio", reference_date=REFERENCE_DATE
    )
    assert portfolio_version is not None
    for project, estrategico, complexidade in ((cenario.first, 5, 5), (cenario.second, 4, 4)):
        for criterion, grade in (("estrategico", estrategico), ("complexidade", complexidade)):
            session.add(
                PortfolioWeight(
                    version_id=portfolio_version.id,
                    project_id=project.id,
                    criterion=criterion,
                    grade=grade,
                )
            )
    session.flush()

    weights = service.portfolio_weights(session, reference_date=REFERENCE_DATE)

    # 60% pelo orçamento (58,34 e 41,66), 25% e 15% pelas notas (5/9 e 4/9)
    assert sum(value.weight for value in weights.values()) == D(100)
    assert weights[cenario.first.id].weight > weights[cenario.second.id].weight
    assert weights[cenario.first.id].shares["estrategico"] == D("55.56")
    assert weights[cenario.second.id].shares["valor"] == D("41.66")


def test_orcamento_vigente_cai_no_orcamento_do_cadastro_quando_nao_ha_eac(
    cenario: EacScenario,
) -> None:
    cenario.second.budget_cents = 9_999_900
    sem_eac = Project(
        client_id=cenario.first.client_id,
        manager_id=cenario.first.manager_id,
        code="TN-SEM-EAC",
        name="Sem EAC",
        budget_cents=1_234_500,
    )
    cenario.session.add(sem_eac)
    cenario.session.flush()

    budgets = service.current_budgets(cenario.session)

    assert budgets[cenario.first.id] == 7_001_000
    assert budgets[cenario.second.id] == 5_000_000  # a EAC vale mais que o cadastro
    assert budgets[sem_eac.id] == 1_234_500


# ── Cadastro do item ─────────────────────────────────────────────────────


def test_edicao_sem_justificativa_e_recusada_e_nada_muda(cenario: EacScenario) -> None:
    with pytest.raises(InvalidDataError) as refusal:
        _edit(cenario, "1.1.1", _form(descricao="Engenharia civil e estrutural", justificativa=""))

    detail = refusal.value.detail
    assert isinstance(detail, dict)
    assert list(detail) == ["justificativa"]
    item = cenario.session.get(EacItem, cenario.items["TN-EAC-001:1.1.1"])
    assert item is not None
    assert item.description == "Engenharia civil"
    assert item.version == 1
    assert service.item_history(cenario.session, item_id=item.id) == ()


def test_justificativa_curta_demais_tambem_e_recusada(cenario: EacScenario) -> None:
    with pytest.raises(InvalidDataError) as refusal:
        _edit(cenario, "1.1.1", _form(descricao="Outro nome", justificativa="curta"))

    assert "mínimo de 10 caracteres" in str(refusal.value)


def test_edicao_com_justificativa_grava_e_fica_no_historico_do_item(cenario: EacScenario) -> None:
    result = _edit(
        cenario,
        "1.1.1",
        _form(
            descricao="Engenharia civil e estrutural",
            tipo_custo="Mão de obra",
            classificacao="OPEX",
            centro_custo="CC-9",
        ),
    )

    assert set(result.changed_fields) == {
        "descrição",
        "tipo de custo",
        "classificação",
        "centro de custo",
    }
    item = cenario.session.get(EacItem, result.item_id)
    assert item is not None
    assert (item.description, item.cost_type, item.capex, item.cost_center) == (
        "Engenharia civil e estrutural",
        "Mão de obra",
        False,
        "CC-9",
    )
    assert item.version == 2
    (entry,) = service.item_history(cenario.session, item_id=item.id)
    assert entry.justification == "Reclassificação pedida pelo controller."
    assert entry.author == "Maria Membro"
    assert set(entry.fields) == set(result.changed_fields)
    assert isinstance(entry.occurred_on, date)


def test_edicao_cadastral_nao_muda_o_valor_orcado(cenario: EacScenario) -> None:
    antes = _view(cenario, _project_scope(cenario.first)).summary.budget_cents

    _edit(cenario, "1.1.1", _form(descricao="Outro nome do item"))

    assert _view(cenario, _project_scope(cenario.first)).summary.budget_cents == antes


def test_trilha_da_plataforma_guarda_o_antes_e_o_depois_do_registro(cenario: EacScenario) -> None:
    _edit(cenario, "1.1.1", _form(descricao="Engenharia civil e estrutural"))

    item_id = cenario.items["TN-EAC-001:1.1.1"]
    lines = cenario.session.scalars(
        select(AuditEntry).where(AuditEntry.record_id == item_id).order_by(AuditEntry.id)
    ).all()
    standard = [
        line for line in lines if line.entity == "eac_item" and line.action == audit.UPDATED
    ]
    assert len(standard) == 1
    assert (standard[0].before or {})["descricao"] == "Engenharia civil"
    assert (standard[0].after or {})["descricao"] == "Engenharia civil e estrutural"
    registry = [line for line in lines if line.entity == service.REGISTRY_ENTITY]
    assert len(registry) == 1
    assert registry[0].project_id == cenario.first.id
    assert registry[0].before == {"descrição": "Engenharia civil"}
    assert (registry[0].after or {})["justificativa"] == "Reclassificação pedida pelo controller."


def test_historico_vem_do_mais_recente_para_o_mais_antigo(cenario: EacScenario) -> None:
    _edit(
        cenario,
        "1.1.1",
        _form(descricao="Primeira mudança", justificativa="Primeira justificativa."),
    )
    _edit(
        cenario, "1.1.1", _form(descricao="Segunda mudança", justificativa="Segunda justificativa.")
    )

    history = service.item_history(cenario.session, item_id=cenario.items["TN-EAC-001:1.1.1"])

    assert [entry.justification for entry in history] == [
        "Segunda justificativa.",
        "Primeira justificativa.",
    ]


def test_edicao_sem_diferenca_nao_grava_nada(cenario: EacScenario) -> None:
    result = _edit(cenario, "1.1.1", _form())

    assert result.changed_fields == ()
    item = cenario.session.get(EacItem, result.item_id)
    assert item is not None
    assert item.version == 1
    assert service.item_history(cenario.session, item_id=item.id) == ()


def test_troca_de_responsavel_vai_para_o_historico_com_o_nome(cenario: EacScenario) -> None:
    other = Person(name="Outra Pessoa", email="outra-eac@example.invalid")
    cenario.session.add(other)
    cenario.session.flush()

    result = _edit(cenario, "1.1.1", _form(responsavel=str(other.id)))

    assert result.changed_fields == ("responsável",)
    item = cenario.session.get(EacItem, result.item_id)
    assert item is not None
    assert item.responsible_id == other.id
    registry = cenario.session.scalars(
        select(AuditEntry).where(AuditEntry.entity == service.REGISTRY_ENTITY)
    ).one()
    assert registry.before == {"responsável": "Maria Membro"}
    assert (registry.after or {})["responsável"] == "Outra Pessoa"


@pytest.mark.parametrize(
    ("campo", "valor", "mensagem"),
    [
        ("descricao", "ab", "Informe a descrição"),
        ("descricao", "x" * 121, "até 120 caracteres"),
        ("tipo_custo", "Invenção", "Escolha o tipo de custo"),
        ("classificacao", "TALVEZ", "CAPEX ou OPEX"),
        ("centro_custo", "C" * 21, "até 20 caracteres"),
        ("responsavel", "999999999", "Escolha o responsável"),
        ("responsavel", "", "Escolha o responsável"),
        ("justificativa", "j" * 301, "até 300 caracteres"),
    ],
)
def test_cada_campo_recusa_o_que_nao_serve_com_a_mensagem_do_campo(
    cenario: EacScenario, campo: str, valor: str, mensagem: str
) -> None:
    with pytest.raises(InvalidDataError) as refusal:
        _edit(cenario, "1.1.1", _form(**{campo: valor}))

    detail = refusal.value.detail
    assert isinstance(detail, dict)
    assert mensagem in detail[campo]


def test_edicao_da_versao_antiga_e_recusada_com_409_que_nomeia_quem_gravou(
    cenario: EacScenario,
) -> None:
    _edit(cenario, "1.1.1", _form(descricao="Primeira mudança"))

    with pytest.raises(VersionConflictError) as conflict:
        _edit(cenario, "1.1.1", _form(descricao="Segunda mudança", versao="1"))

    assert "Este registro foi alterado por Maria Membro às" in str(conflict.value)


def test_edicao_no_portfolio_e_recusada_porque_a_eac_da_carteira_e_so_leitura(
    cenario: EacScenario,
) -> None:
    with pytest.raises(AccessDeniedError, match="somente leitura"):
        service.edit_item_registry(
            cenario.session,
            user=user_of(cenario.member, cenario.session, GeneralProfile.MEMBER),
            scope=PORTFOLIO,
            item_id=cenario.items["TN-EAC-001:1.1.1"],
            form=_form(responsavel=str(cenario.responsible.id), versao="1"),
        )
    with pytest.raises(AccessDeniedError, match="somente leitura"):
        service.item_form(
            cenario.session,
            user=user_of(cenario.member, cenario.session, GeneralProfile.MEMBER),
            scope=PORTFOLIO,
            item_id=cenario.items["TN-EAC-001:1.1.1"],
        )


def test_visualizador_nao_edita(cenario: EacScenario) -> None:
    with pytest.raises(AccessDeniedError):
        service.edit_item_registry(
            cenario.session,
            user=user_of(cenario.viewer, cenario.session, GeneralProfile.VIEWER),
            scope=_project_scope(cenario.first),
            item_id=cenario.items["TN-EAC-001:1.1.1"],
            form=_form(responsavel=str(cenario.responsible.id), versao="1"),
        )


def test_item_de_outro_projeto_nao_se_edita_no_escopo_deste(cenario: EacScenario) -> None:
    with pytest.raises(AccessDeniedError, match="outro projeto"):
        service.item_form(
            cenario.session,
            user=user_of(cenario.member, cenario.session, GeneralProfile.MEMBER),
            scope=_project_scope(cenario.second),
            item_id=cenario.items["TN-EAC-001:1.1.1"],
        )


def test_so_o_item_de_custo_tem_cadastro_editavel(cenario: EacScenario) -> None:
    with pytest.raises(InvalidDataError, match="nível 3"):
        service.item_form(
            cenario.session,
            user=user_of(cenario.member, cenario.session, GeneralProfile.MEMBER),
            scope=_project_scope(cenario.first),
            item_id=cenario.items["TN-EAC-001:1.1"],
        )


def test_item_inexistente_e_recusado_com_mensagem(cenario: EacScenario) -> None:
    with pytest.raises(InvalidDataError, match="não encontrado"):
        service.item_form(
            cenario.session,
            user=user_of(cenario.member, cenario.session, GeneralProfile.MEMBER),
            scope=_project_scope(cenario.first),
            item_id=987654321,
        )


def test_formulario_traz_o_item_as_pessoas_e_o_historico(cenario: EacScenario) -> None:
    _edit(cenario, "1.1.1", _form(descricao="Engenharia civil e estrutural"))

    form = service.item_form(
        cenario.session,
        user=user_of(cenario.member, cenario.session, GeneralProfile.MEMBER),
        scope=_project_scope(cenario.first),
        item_id=cenario.items["TN-EAC-001:1.1.1"],
    )

    assert form.row.code == "1.1.1"
    assert form.row.budget_cents == 1_000_000
    assert form.description == "Engenharia civil e estrutural"
    assert form.version == 2
    assert form.responsible_id == cenario.responsible.id
    assert len(form.history) == 1
    assert cenario.responsible.id in {person.id for person in form.people}


def test_carga_criar_item_passa_pela_trilha(cenario: EacScenario) -> None:
    item_id = cenario.items["TN-EAC-001:1.1.1"]

    created = cenario.session.scalars(
        select(AuditEntry).where(
            AuditEntry.entity == "eac_item",
            AuditEntry.record_id == item_id,
            AuditEntry.action == audit.CREATED,
        )
    ).all()

    assert len(created) == 1
