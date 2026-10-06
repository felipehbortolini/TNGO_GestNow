"""Validação da Central de Ações (ISSUE-019): filtros da lista, justificativa, datas e a ação nova.

Tudo puro: as mensagens que a fachada e a rota entregam à tela, e as fronteiras de cada campo.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.modulos.central_acoes import validation
from src.modulos.central_acoes.calculations import ACTION, INFORMATION, StatusFilter
from src.modulos.central_acoes.validation import (
    ActionFilters,
    NewAction,
    ReplanEntry,
    ReplanRequest,
)

REFERENCIA = date(2026, 9, 25)


def _nova(**campos: object) -> NewAction:
    base = NewAction(
        project_id=1,
        origin="Risco",
        origin_ref="RSK-1",
        subject="Assunto",
        requester_id=1,
        responsible_id=2,
        planned_date=REFERENCIA,
    )
    return NewAction(**{**base.__dict__, **campos})  # type: ignore[arg-type]


# ── Os filtros da lista ──────────────────────────────────────────────────────


def test_sem_consulta_o_filtro_e_em_andamento_na_primeira_pagina() -> None:
    assert validation.parse_filters({}) == ActionFilters()
    assert ActionFilters().status is StatusFilter.OPEN
    assert ActionFilters().page == 1


def test_os_filtros_saem_da_consulta() -> None:
    filtros = validation.parse_filters(
        {
            "busca": "  rigging  ",
            "origem": "Ata",
            "status": "atrasada",
            "responsavel": "12",
            "pagina": "3",
        }
    )

    assert filtros == ActionFilters(
        search="rigging",
        origin="Ata",
        status=StatusFilter.OVERDUE,
        responsible_id=12,
        page=3,
    )


@pytest.mark.parametrize(
    "consulta",
    [
        {"status": "inventado"},
        {"origem": "Origem que não existe"},
        {"responsavel": "abc"},
        {"responsavel": "-1"},
        {"responsavel": "9" * 30},
        {"pagina": "0"},
        {"pagina": "-2"},
        {"pagina": "x"},
    ],
)
def test_valor_sem_sentido_na_consulta_e_ignorado(consulta: dict[str, str]) -> None:
    assert validation.parse_filters(consulta) == ActionFilters()


def test_a_busca_e_cortada_no_limite() -> None:
    filtros = validation.parse_filters({"busca": "a" * 500})

    assert len(filtros.search) == validation.MAX_SEARCH_LENGTH


@pytest.mark.parametrize(
    ("consulta", "esperada"),
    [
        ({}, "lista"),
        ({"visao": "kanban"}, "kanban"),
        ({"visao": "lista"}, "lista"),
        ({"visao": "x"}, "lista"),
    ],
)
def test_a_visao_e_lista_ou_kanban(consulta: dict[str, str], esperada: str) -> None:
    assert validation.parse_view(consulta) == esperada


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("12", 12),
        (" 7 ", 7),
        ("", None),
        (None, None),
        ("1.5", None),
        ("٣", None),
        ("9" * 19, None),
    ],
)
def test_id_so_com_digitos_e_de_tamanho_razoavel(texto: str | None, esperado: int | None) -> None:
    assert validation.parse_id(texto) == esperado


@pytest.mark.parametrize(
    ("texto", "esperada"),
    [
        ("2026-09-25", date(2026, 9, 25)),
        ("", None),
        (None, None),
        ("25/09/2026", None),
        ("2026-02-30", None),
    ],
)
def test_data_do_campo_de_data(texto: str | None, esperada: date | None) -> None:
    assert validation.parse_date(texto) == esperada


# ── A justificativa do replanejamento (HU-053) ───────────────────────────────


@pytest.mark.parametrize(
    ("justificativa", "mensagem"),
    [
        ("", validation.JUSTIFICATION_REQUIRED),
        ("          ", validation.JUSTIFICATION_REQUIRED),
        ("123456789", validation.JUSTIFICATION_TOO_SHORT),
        ("  123456789  ", validation.JUSTIFICATION_TOO_SHORT),
        ("1234567890", None),
        ("a" * 300, None),
        ("a" * 301, validation.JUSTIFICATION_TOO_LONG),
    ],
)
def test_justificativa_exige_de_10_a_300_caracteres(
    justificativa: str, mensagem: str | None
) -> None:
    assert validation.justification_problem(justificativa) == mensagem


# ── A nova data e a data de conclusão ────────────────────────────────────────


def test_a_nova_data_e_obrigatoria() -> None:
    assert validation.new_date_problem(None, REFERENCIA) == validation.NEW_DATE_REQUIRED


def test_a_nova_data_igual_a_referencia_vale_e_um_dia_antes_nao() -> None:
    assert validation.new_date_problem(REFERENCIA, REFERENCIA) is None
    assert (
        validation.new_date_problem(date(2026, 9, 24), REFERENCIA)
        == validation.NEW_DATE_IN_THE_PAST
    )


def test_replanejar_para_o_mesmo_prazo_vigente_e_recusado() -> None:
    pedido = ReplanRequest(
        action_id=1, new_date=date(2026, 10, 1), justification="Motivo válido aqui", version=1
    )

    problemas = validation.replan_problems(
        pedido, current_due=date(2026, 10, 1), reference_date=REFERENCIA
    )

    assert problemas == {"data": validation.NEW_DATE_UNCHANGED}


def test_replanejar_reune_as_mensagens_por_campo() -> None:
    pedido = ReplanRequest(action_id=1, new_date=None, justification="", version=1)

    problemas = validation.replan_problems(
        pedido, current_due=REFERENCIA, reference_date=REFERENCIA
    )

    assert problemas == {
        "data": validation.NEW_DATE_REQUIRED,
        "justificativa": validation.JUSTIFICATION_REQUIRED,
    }


def test_replanejamento_valido_nao_tem_mensagem() -> None:
    pedido = ReplanRequest(
        action_id=1,
        new_date=date(2026, 10, 20),
        justification="Fornecedor atrasou a entrega",
        version=1,
    )

    assert (
        validation.replan_problems(pedido, current_due=REFERENCIA, reference_date=REFERENCIA) == {}
    )


def test_a_conclusao_e_obrigatoria_e_nao_pode_ser_futura() -> None:
    assert validation.completion_problem(None, REFERENCIA) == validation.COMPLETION_DATE_REQUIRED
    assert validation.completion_problem(REFERENCIA, REFERENCIA) is None
    assert (
        validation.completion_problem(date(2026, 9, 26), REFERENCIA)
        == validation.COMPLETION_IN_THE_FUTURE
    )


# ── A ação nova da costura única ─────────────────────────────────────────────


def test_acao_completa_nao_tem_mensagem() -> None:
    assert validation.new_action_problems(_nova()) == {}


@pytest.mark.parametrize("origem", sorted(validation.ORIGINS))
def test_as_dez_origens_valem(origem: str) -> None:
    assert validation.new_action_problems(_nova(origin=origem)) == {}


def test_as_origens_sao_as_dez_da_spec() -> None:
    assert validation.ORIGINS == (
        "Ata",
        "Punch list",
        "Contrato",
        "Suprimentos",
        "Risco",
        "RNC",
        "HSE",
        "Mudança",
        "Lição",
        "Produtividade",
    )


def test_origem_desconhecida_e_referencia_vazia_sao_recusadas() -> None:
    problemas = validation.new_action_problems(_nova(origin="Pendências", origin_ref="   "))

    assert set(problemas) == {"origem", "origem_ref"}


def test_assunto_vazio_e_tipo_desconhecido_sao_recusados() -> None:
    problemas = validation.new_action_problems(_nova(subject=" ", kind="Tarefa"))

    assert set(problemas) == {"assunto", "tipo"}


def test_so_a_acao_exige_data_prevista() -> None:
    assert set(validation.new_action_problems(_nova(planned_date=None))) == {"data_prevista"}
    assert validation.new_action_problems(_nova(planned_date=None, kind=INFORMATION)) == {}


def test_informacao_nao_tem_data_de_conclusao() -> None:
    problemas = validation.new_action_problems(
        _nova(kind=INFORMATION, planned_date=None, completed_on=REFERENCIA)
    )

    assert set(problemas) == {"data_conclusao"}
    assert validation.new_action_problems(_nova(kind=ACTION, completed_on=REFERENCIA)) == {}


def test_todo_replanejamento_do_historico_traz_justificativa() -> None:
    sem = ReplanEntry(
        author_id=1,
        registered_on=REFERENCIA,
        from_date=REFERENCIA,
        to_date=date(2026, 10, 1),
        justification="curta",
    )

    assert set(validation.new_action_problems(_nova(replans=(sem,)))) == {"replanejamentos"}


def test_a_pagina_da_consulta_comeca_em_um() -> None:
    assert validation.parse_page({}) == 1
    assert validation.parse_page({"pagina": "4"}) == 4
    assert validation.parse_page({"pagina": "0"}) == 1
