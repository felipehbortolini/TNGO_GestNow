"""A fachada das atas (ISSUE-021, HU-051, HU-054): numeração, revisão mais recente e retirada bloqueada.

Tudo na transação do teste, com a data de referência injetada em 25/09/2026.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import origin_links
from src.core.errors import AccessDeniedError, InvalidDataError, VersionConflictError
from src.core.models import AuditEntry
from src.core.scope import Scope
from src.modulos.central_acoes import minutes_service, service
from src.modulos.central_acoes.calculations import INFORMATION
from src.modulos.central_acoes.validation import (
    AttendanceRequest,
    CompaniesRequest,
    MinutesFilters,
)
from src.modulos.configuracoes import service as configuracoes
from tests.apoio_acoes import REFERENCIA, Cenario, nova_acao
from tests.apoio_atas import criar_ata, criar_unidade, nova_ata
from tests.identidades import criar_empresa

PORTFOLIO = Scope(project_id=None, source="padrao")


def _acao_da_ata(
    session: Session, cenario: Cenario, ata: minutes_service.MinutesRecord, **campos: object
) -> service.ActionRecord:
    base = {"origin": "Ata", "origin_ref": ata.number, "ata_id": ata.id}
    return service.create_action(
        session,
        user=cenario.gil,
        new=nova_acao(cenario, **{**base, **campos}),
        reference_date=REFERENCIA,
    )


def _ficha(session: Session, cenario: Cenario, ata_id: int) -> minutes_service.MinutesSheet:
    ficha = minutes_service.find_minutes(
        session, user=cenario.gil, minutes_id=ata_id, reference_date=REFERENCIA
    )
    assert ficha is not None
    return ficha


def _retirar(
    session: Session, cenario: Cenario, ata: minutes_service.MinutesRecord, person_id: int
) -> minutes_service.MinutesRecord:
    return minutes_service.remove_attendee(
        session,
        user=cenario.gil,
        minutes_id=ata.id,
        person_id=person_id,
        version=_ficha(session, cenario, ata.id).record.version,
    )


# ── Numeração e criação ──────────────────────────────────────────────────────


def test_nova_ata_recebe_o_numero_do_projeto_na_revisao_zero(
    sessao: Session, cenario: Cenario
) -> None:
    unidade = criar_unidade(sessao)

    primeira = criar_ata(sessao, cenario, unidade)
    segunda = criar_ata(sessao, cenario, unidade)

    assert (primeira.number, primeira.revision) == ("TN-2026-0001", 0)
    assert segunda.number == "TN-2026-0002"


def test_a_numeracao_e_uma_sequencia_por_projeto(sessao: Session, cenario: Cenario) -> None:
    unidade = criar_unidade(sessao)
    criar_ata(sessao, cenario, unidade)

    do_outro_projeto = criar_ata(sessao, cenario, unidade, project_id=cenario.projeto_b.id)

    assert do_outro_projeto.number == "TN-2026-0001"


def test_o_autor_entra_na_lista_de_presenca_e_as_empresas_ficam_com_a_principal(
    sessao: Session, cenario: Cenario
) -> None:
    unidade = criar_unidade(sessao)
    principal = criar_empresa(sessao, "Principal")
    outra = criar_empresa(sessao, "Outra")

    ata = criar_ata(sessao, cenario, unidade, main_company_id=principal.id, company_ids=(outra.id,))

    ficha = _ficha(sessao, cenario, ata.id)
    assert [item.person.id for item in ficha.attendees] == [cenario.mario.person_id]
    assert {(item.name, item.is_main) for item in ficha.companies} == {
        ("Principal", True),
        ("Outra", False),
    }
    assert ficha.unit_name == unidade.name


def test_nova_ata_sem_os_campos_obrigatorios_da_422_por_campo(
    sessao: Session, cenario: Cenario
) -> None:
    unidade = criar_unidade(sessao)
    vazia = nova_ata(
        cenario, unidade, meeting_date=None, meeting_type="", board="", unit_id=None, subject=""
    )

    with pytest.raises(InvalidDataError) as erro:
        minutes_service.create_minutes(
            sessao, user=cenario.gil, new=vazia, reference_date=REFERENCIA
        )

    assert set(erro.value.detail) == {"data", "tipo_reuniao", "diretoria", "unidade", "assunto"}


def test_unidade_ou_pessoa_fora_do_cadastro_e_recusada(sessao: Session, cenario: Cenario) -> None:
    unidade = criar_unidade(sessao)

    with pytest.raises(InvalidDataError) as erro:
        criar_ata(sessao, cenario, unidade, unit_id=999_999, prepared_by_id=999_999)

    assert set(erro.value.detail) == {"unidade", "elaborado_por"}


def test_visualizador_nao_gera_ata(sessao: Session, cenario: Cenario) -> None:
    unidade = criar_unidade(sessao)

    with pytest.raises(AccessDeniedError):
        minutes_service.create_minutes(
            sessao,
            user=cenario.vera,
            new=nova_ata(cenario, unidade),
            reference_date=REFERENCIA,
        )


# ── A lista ──────────────────────────────────────────────────────────────────


def test_a_lista_mostra_so_a_revisao_mais_recente_de_cada_ata(
    sessao: Session, cenario: Cenario
) -> None:
    unidade = criar_unidade(sessao)
    criar_ata(sessao, cenario, unidade, number="TN-2026-0100", revision=0)
    vigente = criar_ata(sessao, cenario, unidade, number="TN-2026-0100", revision=1)
    outra = criar_ata(sessao, cenario, unidade, number="TN-2026-0101")

    listagem = minutes_service.list_minutes(
        sessao,
        user=cenario.gil,
        scope=PORTFOLIO,
        filters=MinutesFilters(),
        reference_date=REFERENCIA,
    )

    assert {linha.record.id for linha in listagem.rows} == {vigente.id, outra.id}
    assert listagem.universe == 2


def test_a_lista_respeita_o_projeto_e_a_busca(sessao: Session, cenario: Cenario) -> None:
    unidade = criar_unidade(sessao)
    criar_ata(sessao, cenario, unidade, subject="Licenciamento ambiental")
    criar_ata(sessao, cenario, unidade, subject="Montagem da caldeira")
    criar_ata(sessao, cenario, unidade, project_id=cenario.projeto_b.id, subject="Outro projeto")

    do_projeto = minutes_service.list_minutes(
        sessao,
        user=cenario.gil,
        scope=Scope(project_id=cenario.projeto_a.id, source="padrao"),
        filters=MinutesFilters(search="LICENCIAMENTO"),
        reference_date=REFERENCIA,
    )

    assert [linha.record.subject for linha in do_projeto.rows] == ["Licenciamento ambiental"]


def test_a_lista_conta_acoes_abertas_e_atrasadas_da_ata(sessao: Session, cenario: Cenario) -> None:
    unidade = criar_unidade(sessao)
    ata = criar_ata(sessao, cenario, unidade)
    _acao_da_ata(sessao, cenario, ata)
    _acao_da_ata(sessao, cenario, ata, planned_date=REFERENCIA - timedelta(days=1))
    _acao_da_ata(sessao, cenario, ata, kind=INFORMATION, planned_date=None)

    linha = minutes_service.list_minutes(
        sessao,
        user=cenario.gil,
        scope=PORTFOLIO,
        filters=MinutesFilters(),
        reference_date=REFERENCIA,
    ).rows[0]

    assert (linha.open_count, linha.overdue_count) == (2, 1)


# ── Retirada bloqueada (HU-054) ──────────────────────────────────────────────


def test_retirar_participante_com_acao_aberta_e_recusado_com_a_mensagem(
    sessao: Session, cenario: Cenario
) -> None:
    unidade = criar_unidade(sessao)
    ata = criar_ata(sessao, cenario, unidade, participant_ids=(cenario.gil.person_id,))
    _acao_da_ata(sessao, cenario, ata, responsible_id=cenario.gil.person_id)

    with pytest.raises(InvalidDataError) as erro:
        _retirar(sessao, cenario, ata, cenario.gil.person_id)

    assert str(erro.value.detail) == (
        "Não é possível retirar Gil Gestor: 1 ação aberta sob sua responsabilidade nesta ata."
    )
    assert len(_ficha(sessao, cenario, ata.id).attendees) == 2


def test_a_mensagem_da_retirada_conta_no_plural() -> None:
    assert minutes_service.blocked_attendee_message("Gil", 3) == (
        "Não é possível retirar Gil: 3 ações abertas sob sua responsabilidade nesta ata."
    )


def test_retirar_sem_acao_aberta_retira_e_registra_na_trilha(
    sessao: Session, cenario: Cenario
) -> None:
    unidade = criar_unidade(sessao)
    ata = criar_ata(sessao, cenario, unidade, participant_ids=(cenario.gil.person_id,))

    depois = _retirar(sessao, cenario, ata, cenario.gil.person_id)

    ficha = _ficha(sessao, cenario, ata.id)
    assert [item.person.id for item in ficha.attendees] == [cenario.mario.person_id]
    assert depois.version == ata.version + 1
    trilha = sessao.scalars(
        select(AuditEntry).where(
            AuditEntry.entity == "ata_participante", AuditEntry.action == "excluido"
        )
    ).all()
    assert len(trilha) == 1


def test_acao_concluida_ou_informacao_nao_bloqueiam_a_retirada(
    sessao: Session, cenario: Cenario
) -> None:
    unidade = criar_unidade(sessao)
    ata = criar_ata(sessao, cenario, unidade, participant_ids=(cenario.gil.person_id,))
    _acao_da_ata(
        sessao,
        cenario,
        ata,
        responsible_id=cenario.gil.person_id,
        planned_date=REFERENCIA - timedelta(days=5),
        completed_on=REFERENCIA - timedelta(days=1),
    )
    _acao_da_ata(
        sessao,
        cenario,
        ata,
        responsible_id=cenario.gil.person_id,
        kind=INFORMATION,
        planned_date=None,
    )

    _retirar(sessao, cenario, ata, cenario.gil.person_id)

    assert len(_ficha(sessao, cenario, ata.id).attendees) == 1


def test_a_acao_aberta_de_outra_ata_nao_bloqueia(sessao: Session, cenario: Cenario) -> None:
    unidade = criar_unidade(sessao)
    ata = criar_ata(sessao, cenario, unidade, participant_ids=(cenario.gil.person_id,))
    outra = criar_ata(sessao, cenario, unidade)
    _acao_da_ata(sessao, cenario, outra, responsible_id=cenario.gil.person_id)

    _retirar(sessao, cenario, ata, cenario.gil.person_id)

    assert len(_ficha(sessao, cenario, ata.id).attendees) == 1


def test_retirar_quem_nao_esta_na_lista_da_422(sessao: Session, cenario: Cenario) -> None:
    unidade = criar_unidade(sessao)
    ata = criar_ata(sessao, cenario, unidade)

    with pytest.raises(InvalidDataError):
        _retirar(sessao, cenario, ata, cenario.ada.person_id)


def test_retirar_empresa_com_acao_aberta_de_gente_dela_e_recusado(
    sessao: Session, cenario: Cenario
) -> None:
    unidade = criar_unidade(sessao)
    empresa_id = configuracoes.find_person_details(sessao, [cenario.fabio.person_id])[
        cenario.fabio.person_id
    ].company_id
    assert empresa_id is not None
    ata = criar_ata(sessao, cenario, unidade, company_ids=(empresa_id,))
    _acao_da_ata(sessao, cenario, ata, responsible_id=cenario.fabio.person_id)

    with pytest.raises(InvalidDataError) as erro:
        minutes_service.set_companies(
            sessao,
            user=cenario.gil,
            request=CompaniesRequest(ata.id, None, (), ata.version),
        )

    assert "há ação em aberto com responsável da empresa" in erro.value.detail["empresas"]
    assert [item.id for item in _ficha(sessao, cenario, ata.id).companies] == [empresa_id]


def test_retirar_empresa_sem_acao_aberta_e_trocar_a_principal(
    sessao: Session, cenario: Cenario
) -> None:
    unidade = criar_unidade(sessao)
    velha = criar_empresa(sessao, "Velha")
    nova = criar_empresa(sessao, "Nova")
    ata = criar_ata(sessao, cenario, unidade, main_company_id=velha.id)

    minutes_service.set_companies(
        sessao,
        user=cenario.gil,
        request=CompaniesRequest(ata.id, nova.id, (), ata.version),
    )

    ficha = _ficha(sessao, cenario, ata.id)
    assert [(item.name, item.is_main) for item in ficha.companies] == [("Nova", True)]
    assert ficha.main_company_name == "Nova"


# ── Convidados, revisão e versão ─────────────────────────────────────────────


def test_buscar_convidado_oferece_so_quem_nao_esta_na_lista_e_adiciona(
    sessao: Session, cenario: Cenario
) -> None:
    unidade = criar_unidade(sessao)
    ata = criar_ata(sessao, cenario, unidade)

    candidatos = minutes_service.guest_candidates(
        sessao, user=cenario.gil, minutes_id=ata.id, search="vera"
    )
    assert [pessoa.id for pessoa in candidatos] == [cenario.vera.person_id]
    assert cenario.mario.person_id not in {
        pessoa.id
        for pessoa in minutes_service.guest_candidates(
            sessao, user=cenario.gil, minutes_id=ata.id, search=""
        )
    }

    minutes_service.add_guests(
        sessao,
        user=cenario.gil,
        request=AttendanceRequest(ata.id, (cenario.vera.person_id,), ata.version),
    )

    assert cenario.vera.person_id in {
        item.person.id for item in _ficha(sessao, cenario, ata.id).attendees
    }


def test_convidado_exige_escolha_e_nao_repete(sessao: Session, cenario: Cenario) -> None:
    unidade = criar_unidade(sessao)
    ata = criar_ata(sessao, cenario, unidade)

    with pytest.raises(InvalidDataError):
        minutes_service.add_guests(
            sessao, user=cenario.gil, request=AttendanceRequest(ata.id, (), ata.version)
        )
    with pytest.raises(InvalidDataError):
        minutes_service.add_guests(
            sessao,
            user=cenario.gil,
            request=AttendanceRequest(ata.id, (cenario.mario.person_id,), ata.version),
        )


def test_revisao_anterior_e_somente_leitura(sessao: Session, cenario: Cenario) -> None:
    unidade = criar_unidade(sessao)
    antiga = criar_ata(sessao, cenario, unidade, number="TN-2026-0200", revision=0)
    vigente = criar_ata(sessao, cenario, unidade, number="TN-2026-0200", revision=1)

    ficha = _ficha(sessao, cenario, antiga.id)
    assert (ficha.is_latest, ficha.latest_id) == (False, vigente.id)
    with pytest.raises(InvalidDataError) as erro:
        _retirar(sessao, cenario, antiga, cenario.mario.person_id)
    assert str(erro.value.detail) == minutes_service.READ_ONLY_MESSAGE


def test_versao_antiga_da_409(sessao: Session, cenario: Cenario) -> None:
    unidade = criar_unidade(sessao)
    ata = criar_ata(sessao, cenario, unidade, participant_ids=(cenario.gil.person_id,))
    _retirar(sessao, cenario, ata, cenario.gil.person_id)

    with pytest.raises(VersionConflictError):
        minutes_service.add_guests(
            sessao,
            user=cenario.gil,
            request=AttendanceRequest(ata.id, (cenario.vera.person_id,), ata.version),
        )


def test_ata_inexistente_nao_tem_ficha(sessao: Session, cenario: Cenario) -> None:
    assert (
        minutes_service.find_minutes(
            sessao, user=cenario.gil, minutes_id=999_999, reference_date=REFERENCIA
        )
        is None
    )


def test_a_acao_da_ata_abre_a_ficha_da_ata() -> None:
    link = origin_links.resolve("Ata", "TN-2026-0001", record_id=42)

    assert link.url == "/central-acoes/ata?id=42"
    assert origin_links.resolve("Ata", "TN-2026-0001").url is None
