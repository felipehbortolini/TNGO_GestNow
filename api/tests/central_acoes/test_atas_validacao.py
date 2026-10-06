"""Validação das atas (ISSUE-021): um recado por campo e o assunto de 150 caracteres."""

from __future__ import annotations

from datetime import date

from src.modulos.central_acoes import validation
from src.modulos.central_acoes.validation import NewMinutes


def _minutes(**fields: object) -> NewMinutes:
    base = NewMinutes(
        project_id=1,
        meeting_date=date(2026, 9, 25),
        meeting_type="Segurança",
        board="Diretoria de Projetos",
        unit_id=3,
        prepared_by_id=4,
        subject="Reunião de segurança",
    )
    return NewMinutes(**{**base.__dict__, **fields})


def test_ata_completa_nao_tem_problema() -> None:
    assert validation.minutes_problems(_minutes()) == {}


def test_todos_os_campos_obrigatorios_vazios_dao_um_recado_por_campo() -> None:
    problems = validation.minutes_problems(
        _minutes(
            meeting_date=None,
            meeting_type="",
            board=" ",
            unit_id=None,
            prepared_by_id=None,
            subject="",
        )
    )

    assert set(problems) == {
        "data",
        "tipo_reuniao",
        "diretoria",
        "unidade",
        "elaborado_por",
        "assunto",
    }


def test_tipo_de_reuniao_fora_da_lista_e_recusado() -> None:
    assert "tipo_reuniao" in validation.minutes_problems(_minutes(meeting_type="Churrasco"))


def test_assunto_aceita_150_caracteres_e_recusa_151() -> None:
    assert validation.minutes_problems(_minutes(subject="a" * 150)) == {}
    assert validation.minutes_problems(_minutes(subject="a" * 151)) == {
        "assunto": validation.MINUTES_SUBJECT_TOO_LONG
    }


def test_assunto_so_de_espacos_conta_como_vazio() -> None:
    assert validation.minutes_problems(_minutes(subject="   ")) == {
        "assunto": validation.MINUTES_SUBJECT_REQUIRED
    }


def test_diretoria_aceita_100_caracteres_e_recusa_101() -> None:
    assert validation.minutes_problems(_minutes(board="d" * 100)) == {}
    assert "diretoria" in validation.minutes_problems(_minutes(board="d" * 101))


def test_parse_ids_tira_repetidos_e_o_que_nao_e_numero() -> None:
    assert validation.parse_ids(["3", "x", "3", "", "7", "-1"]) == (3, 7)


def test_filtros_da_lista_de_atas() -> None:
    filters = validation.parse_minutes_filters({"busca": "  coordenação ", "pagina": "3"})

    assert (filters.search, filters.page) == ("coordenação", 3)
    assert validation.parse_minutes_filters({"pagina": "0"}).page == 1
