"""Fachada do 6WLA (ISSUE-045): gravação, janela, indicadores, escopo e perfis.

O cenário mínimo vem de ``apoio_6wla``; a data de hoje é injetada (25/09/2026).
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from src.core.errors import AccessDeniedError, InvalidDataError, VersionConflictError
from src.core.scope import Scope
from src.modulos.planejamento import service
from tests.apoio_6wla import (
    HOJE,
    Cadastro,
    campos_da_atividade,
    campos_da_restricao,
    incluir_atividade,
)


def _escopo(cadastro: Cadastro) -> Scope:
    return Scope(project_id=cadastro.projeto.id, source="url")


def _quadro(
    sessao: Session,
    cadastro: Cadastro,
    *,
    hoje: date = HOJE,
    filtros: service.LookaheadFilter | None = None,
    escopo: Scope | None = None,
) -> service.LookaheadBoard:
    return service.lookahead_board(
        sessao,
        user=cadastro.usuario_membro,
        scope=escopo or _escopo(cadastro),
        reference_date=hoje,
        filters=filtros or service.LookaheadFilter(),
    )


def _restringir(
    sessao: Session, cadastro: Cadastro, atividade_id: int, *, necessaria: str = "2026-10-02"
) -> int:
    registro = service.create_constraint(
        sessao,
        user=cadastro.usuario_membro,
        scope=_escopo(cadastro),
        raw=campos_da_restricao(cadastro, atividade_id, necessaria=necessaria),
    )
    return registro.id


def test_a_atividade_nasce_com_o_proximo_codigo_do_projeto(
    sessao: Session, cadastro: Cadastro
) -> None:
    primeira = incluir_atividade(sessao, cadastro)
    segunda = incluir_atividade(sessao, cadastro, atividade="Alinhamento")

    assert (primeira.code, segunda.code) == ("LA-01", "LA-02")
    assert primeira.planned == (True, True, False, False, False, False)


def test_o_codigo_e_contado_por_projeto(sessao: Session, cadastro: Cadastro) -> None:
    incluir_atividade(sessao, cadastro)
    do_outro = incluir_atividade(sessao, cadastro, projeto=cadastro.outro_projeto)

    assert do_outro.code == "LA-01"


def test_no_portfolio_a_inclusao_pede_o_projeto(sessao: Session, cadastro: Cadastro) -> None:
    with pytest.raises(InvalidDataError):
        service.create_activity(
            sessao,
            user=cadastro.usuario_membro,
            scope=Scope(project_id=None, source="padrao"),
            form=campos_da_atividade(cadastro),
        )


def test_a_janela_do_quadro_anda_com_a_data_injetada(sessao: Session, cadastro: Cadastro) -> None:
    hoje = _quadro(sessao, cadastro, hoje=HOJE)
    semana_depois = _quadro(sessao, cadastro, hoje=date(2026, 10, 2))

    assert len(hoje.weeks) == 6
    assert hoje.weeks[0].start == date(2026, 9, 28)
    assert semana_depois.weeks[0].start == date(2026, 10, 5)


def test_restricao_aberta_sinaliza_a_atividade_do_curto_prazo(
    sessao: Session, cadastro: Cadastro
) -> None:
    atividade = incluir_atividade(sessao, cadastro)
    _restringir(sessao, cadastro, atividade.id)

    quadro = _quadro(sessao, cadastro)
    lida = quadro.activities[0]

    assert lida.open_constraints == 1
    assert lida.has_short_term_risk
    assert lida.week_at_risk(0)
    assert quadro.figures.short_term_ready == 0
    assert quadro.figures.open_constraints == 1


def test_restricao_vence_quando_a_data_de_referencia_passa_da_necessaria(
    sessao: Session, cadastro: Cadastro
) -> None:
    atividade = incluir_atividade(sessao, cadastro)
    _restringir(sessao, cadastro, atividade.id, necessaria="2026-09-25")

    no_dia = _quadro(sessao, cadastro, hoje=date(2026, 9, 25))
    no_dia_seguinte = _quadro(sessao, cadastro, hoje=date(2026, 9, 26))

    assert no_dia.figures.overdue_constraints == 0
    assert no_dia_seguinte.figures.overdue_constraints == 1
    assert no_dia_seguinte.activities[0].situation == "vencida"


def test_remover_a_restricao_registra_data_e_libera_a_atividade(
    sessao: Session, cadastro: Cadastro
) -> None:
    atividade = incluir_atividade(sessao, cadastro)
    restricao_id = _restringir(sessao, cadastro, atividade.id)

    service.remove_constraint(
        sessao,
        user=cadastro.usuario_membro,
        scope=_escopo(cadastro),
        constraint_id=restricao_id,
        raw={"remocao": "2026-09-24", "comentario": "Guindaste mobilizado"},
    )

    quadro = _quadro(sessao, cadastro)
    restricao = quadro.activities[0].constraints[0]
    assert restricao.removal_date == date(2026, 9, 24)
    assert restricao.status == "Removida"
    assert quadro.activities[0].is_ready
    assert quadro.figures.removal_index is not None
    assert str(quadro.figures.removal_index) == "100.00"


def test_remover_duas_vezes_e_recusado(sessao: Session, cadastro: Cadastro) -> None:
    atividade = incluir_atividade(sessao, cadastro)
    restricao_id = _restringir(sessao, cadastro, atividade.id)
    campos = {"remocao": "2026-09-24"}
    service.remove_constraint(
        sessao,
        user=cadastro.usuario_membro,
        scope=_escopo(cadastro),
        constraint_id=restricao_id,
        raw=campos,
    )

    with pytest.raises(InvalidDataError):
        service.remove_constraint(
            sessao,
            user=cadastro.usuario_membro,
            scope=_escopo(cadastro),
            constraint_id=restricao_id,
            raw=campos,
        )


def test_o_filtro_so_com_restricao_aberta_nao_mexe_nos_indicadores(
    sessao: Session, cadastro: Cadastro
) -> None:
    com = incluir_atividade(sessao, cadastro, atividade="Com restrição")
    incluir_atividade(sessao, cadastro, atividade="Sem restrição")
    _restringir(sessao, cadastro, com.id)

    quadro = _quadro(
        sessao, cadastro, filtros=service.LookaheadFilter(only_with_open_constraint=True)
    )

    assert [item.name for item in quadro.activities] == ["Com restrição"]
    assert quadro.figures.activities == 2
    assert quadro.total_activities == 2


def test_a_busca_filtra_por_texto_da_atividade(sessao: Session, cadastro: Cadastro) -> None:
    incluir_atividade(sessao, cadastro, atividade="Montagem da carcaça")
    incluir_atividade(sessao, cadastro, atividade="Alinhamento do eixo")

    quadro = _quadro(sessao, cadastro, filtros=service.LookaheadFilter(search="alinhamento"))

    assert [item.name for item in quadro.activities] == ["Alinhamento do eixo"]


def test_o_portfolio_junta_os_projetos_e_o_projeto_isola(
    sessao: Session, cadastro: Cadastro
) -> None:
    incluir_atividade(sessao, cadastro)
    incluir_atividade(sessao, cadastro, projeto=cadastro.outro_projeto)

    portfolio = _quadro(sessao, cadastro, escopo=Scope(project_id=None, source="padrao"))

    assert portfolio.portfolio
    assert len(portfolio.activities) == 2
    assert len(_quadro(sessao, cadastro).activities) == 1


def test_registro_de_outro_projeto_nao_e_alcancado_pelo_escopo(
    sessao: Session, cadastro: Cadastro
) -> None:
    do_outro = incluir_atividade(sessao, cadastro, projeto=cadastro.outro_projeto)

    with pytest.raises(InvalidDataError):
        service.find_activity(
            sessao, scope=_escopo(cadastro), activity_id=do_outro.id, reference_date=HOJE
        )


def test_edicao_com_versao_vencida_e_conflito(sessao: Session, cadastro: Cadastro) -> None:
    atividade = incluir_atividade(sessao, cadastro)
    formulario = campos_da_atividade(cadastro, atividade="Nova descrição")
    formulario.fields["versao"] = str(atividade.version)
    service.update_activity(
        sessao,
        user=cadastro.usuario_membro,
        scope=_escopo(cadastro),
        activity_id=atividade.id,
        form=formulario,
    )

    with pytest.raises(VersionConflictError):
        service.update_activity(
            sessao,
            user=cadastro.usuario_membro,
            scope=_escopo(cadastro),
            activity_id=atividade.id,
            form=formulario,
        )


def test_visualizador_nao_grava(sessao: Session, cadastro: Cadastro) -> None:
    with pytest.raises(AccessDeniedError):
        service.create_activity(
            sessao,
            user=cadastro.usuario_visualizador,
            scope=_escopo(cadastro),
            form=campos_da_atividade(cadastro),
        )
    assert not service.can_write(cadastro.usuario_visualizador)
    assert service.can_write(cadastro.usuario_membro)


def test_empresa_inexistente_e_recusada_no_servidor(sessao: Session, cadastro: Cadastro) -> None:
    formulario = campos_da_atividade(cadastro)
    formulario.fields["empresa"] = "999999"

    with pytest.raises(InvalidDataError) as erro:
        service.create_activity(
            sessao,
            user=cadastro.usuario_membro,
            scope=_escopo(cadastro),
            form=formulario,
        )
    assert isinstance(erro.value.detail, dict)
    assert "empresa" in erro.value.detail
