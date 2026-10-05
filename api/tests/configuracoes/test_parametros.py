"""Fachada dos parâmetros versionados: versão 1, vigência por data e validação."""

from __future__ import annotations

from copy import deepcopy
from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core.errors import InvalidDataError
from src.core.models import AuditEntry
from src.modulos.configuracoes import service, validation
from src.modulos.configuracoes.models import Collaborator, ParameterVersion, Person


def _autor(session: Session, nome: str = "Ana Souza") -> Collaborator:
    pessoa = Person(name=nome, email="parametros@example.invalid")
    session.add(pessoa)
    session.flush()
    colaborador = Collaborator(person_id=pessoa.id, general_profile="Gestor", bond="Timenow")
    session.add(colaborador)
    session.flush()
    return colaborador


def _versao_um(session: Session) -> Collaborator:
    autor = _autor(session)
    service.seed_initial_parameters(session, author_id=autor.id, effective_from=date(2026, 9, 25))
    return autor


def test_versao_1_tem_todos_os_grupos_da_tabela_e_o_grupo_anexos(db_session: Session) -> None:
    autor = _autor(db_session)
    criadas = service.seed_initial_parameters(
        db_session, author_id=autor.id, effective_from=date(2026, 9, 25)
    )

    assert len(criadas) == len(service.PARAMETER_GROUPS)
    assert all(versao.version == 1 for versao in criadas)

    parametros = service.current_parameters(db_session, reference_date=date(2026, 9, 25))
    assert set(parametros) == set(service.PARAMETER_GROUPS)
    # Valores iniciais da tabela 7.4 do README do protótipo.
    pesos = [criterio["peso"] for criterio in parametros["avaliacaoContratada"]["criterios"]]
    assert pesos == [25, 20, 20, 15, 10, 10]
    assert parametros["mudancas"]["quorumComite"] == 3
    assert parametros["produtividade"]["jornadaDiariaHoras"] == 8.8
    assert parametros["eap"]["modelosEtapas"][1]["etapas"][2]["peso"] == 45
    assert parametros["suprimentos"]["alcadas"][2]["ate"] is None
    assert parametros["riscos"]["impactos"][0] == "Muito baixo"
    # Grupo Anexos (D5a).
    assert parametros["anexos"]["tamanhoMaximoMb"] == 25
    assert parametros["anexos"]["tiposAceitos"] == [
        "PDF",
        "JPG",
        "PNG",
        "DOCX",
        "XLSX",
        "PPTX",
        "DWG",
        "ZIP",
    ]


def test_semear_de_novo_nao_duplica_a_versao_1(db_session: Session) -> None:
    autor = _versao_um(db_session)

    assert (
        service.seed_initial_parameters(
            db_session, author_id=autor.id, effective_from=date(2026, 9, 25)
        )
        == []
    )
    total = db_session.scalar(select(func.count()).select_from(ParameterVersion))
    assert total == len(service.PARAMETER_GROUPS)


def test_versao_vigente_e_lida_por_data(db_session: Session) -> None:
    autor = _versao_um(db_session)
    valores = deepcopy(service.INITIAL_PARAMETERS["riscos"])
    valores["cadenciaDias"]["critico"] = 10
    nova = service.save_parameter_group(
        db_session,
        author_id=autor.id,
        group="riscos",
        values=valores,
        effective_from=date(2026, 10, 10),
        justification="Antecipar a revisão dos riscos críticos.",
    )
    assert nova.version == 2

    antes = service.current_version(db_session, group="riscos", reference_date=date(2026, 10, 9))
    assert antes is not None and antes.version == 1
    lidos = service.current_group(db_session, group="riscos", reference_date=date(2026, 10, 9))
    assert lidos["cadenciaDias"]["critico"] == 15

    vigente = service.current_version(db_session, group="riscos", reference_date=date(2026, 10, 10))
    assert vigente is not None and vigente.version == 2
    lidos = service.current_group(db_session, group="riscos", reference_date=date(2026, 10, 10))
    assert lidos["cadenciaDias"]["critico"] == 10

    # A gravação de um grupo não mexe nos demais.
    qualidade = service.current_group(
        db_session, group="qualidade", reference_date=date(2026, 10, 10)
    )
    assert qualidade["notificacaoClienteHoras"] == 48


def test_gravar_sem_justificativa_e_recusado(db_session: Session) -> None:
    autor = _versao_um(db_session)

    with pytest.raises(InvalidDataError) as recusa:
        service.save_parameter_group(
            db_session,
            author_id=autor.id,
            group="licoes",
            values=deepcopy(service.INITIAL_PARAMETERS["licoes"]),
            effective_from=date(2026, 10, 5),
            justification="curta",
        )

    assert "justificativa" in recusa.value.detail


def test_gravar_com_valor_invalido_e_recusado_com_o_campo(db_session: Session) -> None:
    autor = _versao_um(db_session)
    valores = deepcopy(service.INITIAL_PARAMETERS["hse"])
    valores["prazos"]["investigacaoPreliminarHoras"] = 12

    with pytest.raises(InvalidDataError) as recusa:
        service.save_parameter_group(
            db_session,
            author_id=autor.id,
            group="hse",
            values=valores,
            effective_from=date(2026, 10, 5),
            justification="Alteração inválida dos prazos de HSE.",
        )

    assert "hse.prazos" in recusa.value.detail


def test_gravacao_de_nova_versao_deixa_trilha(db_session: Session) -> None:
    autor = _versao_um(db_session)
    nova = service.save_parameter_group(
        db_session,
        author_id=autor.id,
        group="licoes",
        values=deepcopy(service.INITIAL_PARAMETERS["licoes"]),
        effective_from=date(2026, 10, 5),
        justification="Revisar o alerta de lições.",
    )

    linhas = db_session.scalars(
        select(AuditEntry).where(
            AuditEntry.entity == "parametro_versao", AuditEntry.record_id == nova.id
        )
    ).all()
    assert len(linhas) == 1
    assert linhas[0].action == "criado"
    assert linhas[0].user_id == autor.id


def test_valores_iniciais_de_todos_os_grupos_passam_na_validacao() -> None:
    for grupo, valores in service.INITIAL_PARAMETERS.items():
        assert validation.validate_parameter_group(grupo, valores) == {}
