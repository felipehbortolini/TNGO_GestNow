"""Fachada das Ocorrências do HSE (ISSUE-073, D5, D5b, D7, D9): o fluxo, os prazos e o restrito.

O fluxo vai de Registrada a Encerrada com a investigação como fato, as ações corretivas na
Central na mesma transação (origem HSE, com o código da ocorrência), o HiPo encerrado abrindo a
lição em Rascunho na Governança e a verificação de eficácia. O prazo vigente fica gravado na
ocorrência: mudar o parâmetro depois não muda o registro. O nome e os dados médicos entram em
``ocorrencia_restrito`` na mesma transação e só Gestor e Admin leem de volta (Q35).
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import func, select

from src.core import recording
from src.core.errors import AccessDeniedError, InvalidDataError
from src.core.scope import Scope
from src.modulos.central_acoes import service as actions
from src.modulos.central_acoes.validation import CompletionRequest
from src.modulos.configuracoes import service as configuracoes
from src.modulos.governanca import lessons_models as lessons
from src.modulos.hse import models, service, validation
from src.modulos.hse.models import Occurrence, OccurrenceInvestigation, OccurrenceRestricted
from tests.apoio_hse import (
    REFERENCIA,
    Cenario,
    acao_de,
    encerramento_de,
    investigacao_de,
    ocorrencia_de,
    usuario_de,
)
from tests.identidades import criar_colaborador

ONTEM = REFERENCIA - timedelta(days=1)


def _escopo(cenario: Cenario, *, projeto: bool = True) -> Scope:
    return Scope(project_id=cenario.projeto.id if projeto else None, source="url")


def _registrar(cenario: Cenario, sessao, **campos: object) -> service.OccurrenceSave:
    return service.save_occurrence(
        sessao, user=cenario.maria, data=ocorrencia_de(cenario, **campos), reference_date=REFERENCIA
    )


def _linha(sessao, cenario: Cenario, codigo: str) -> service.OccurrenceRow:
    screen = service.occurrences_screen(
        sessao,
        scope=_escopo(cenario),
        filters=validation.OccurrenceFilters(),
        reference_date=REFERENCIA,
    )
    return next(row for row in screen.rows if row.code == codigo)


def _investigar(sessao, cenario: Cenario, codigo: str, **campos: object) -> None:
    service.record_investigation(
        sessao,
        user=cenario.maria,
        code=codigo,
        data=investigacao_de(**campos),
        reference_date=REFERENCIA,
    )


def _acao(sessao, cenario: Cenario, codigo: str) -> actions.ActionRecord:
    service.define_corrective_actions(
        sessao,
        user=cenario.maria,
        code=codigo,
        actions_input=(acao_de(cenario),),
        reference_date=REFERENCIA,
    )
    sheet = service.occurrence_sheet(
        sessao, user=cenario.gil, code=codigo, reference_date=REFERENCIA
    )
    assert sheet is not None
    return sheet.actions[0]


def _concluir(sessao, cenario: Cenario, record: actions.ActionRecord) -> None:
    actions.complete_action(
        sessao,
        user=cenario.gil,
        request=CompletionRequest(
            action_id=record.id, completed_on=REFERENCIA, version=record.version
        ),
        reference_date=REFERENCIA,
    )


# ── O prazo vigente gravado (D5b) ────────────────────────────────────────────────────────────


def test_o_prazo_vigente_fica_gravado_e_mudar_o_parametro_nao_muda_a_ocorrencia(
    sessao, cenario: Cenario
) -> None:
    primeira = _registrar(cenario, sessao, communication_hours=30)

    atual = configuracoes.current_group(sessao, group="hse", reference_date=REFERENCIA)
    prazos = {
        **atual.get("prazos", {}),
        "comunicacaoHoras": 48,
        "investigacaoPreliminarHoras": 72,
        "relatorioFinalDias": 45,
    }
    configuracoes.save_parameter_group(
        sessao,
        author_id=cenario.ada.id,
        group="hse",
        values={**atual, "prazos": prazos},
        effective_from=REFERENCIA,
        justification="Prazo de comunicação maior para o teste da D5b.",
    )
    segunda = _registrar(cenario, sessao, communication_hours=30)

    primeira_linha = _linha(sessao, cenario, primeira.code)
    segunda_linha = _linha(sessao, cenario, segunda.code)

    assert primeira.avisos == ("Comunicação registrada fora do prazo de 24 horas.",)
    assert segunda.avisos == (), "o prazo novo vale para o próximo registro"
    assert primeira_linha.communication_overdue is True, "o prazo gravado da primeira não mudou"
    assert primeira_linha.investigation_deadline_hours == 48
    assert primeira_linha.report_deadline_days == 30
    assert segunda_linha.communication_overdue is False
    assert segunda_linha.investigation_deadline_hours == 72
    assert segunda_linha.report_deadline_days == 45


def test_o_codigo_nasce_da_serie_do_projeto(sessao, cenario: Cenario) -> None:
    primeira = _registrar(cenario, sessao)
    segunda = _registrar(cenario, sessao, happened_time="11:00")
    outro = service.save_occurrence(
        sessao,
        user=cenario.maria,
        data=ocorrencia_de(cenario, project_id=cenario.outro.id),
        reference_date=REFERENCIA,
    )

    assert primeira.code == "OCR-TN-2026-0001"
    assert segunda.code == "OCR-TN-2026-0002"
    assert outro.code == "OCR-TN-2026-0001", "a série é de cada projeto"


# ── O fluxo completo ─────────────────────────────────────────────────────────────────────────


def test_o_fluxo_completo_ate_o_encerramento_com_a_acao_na_central(
    sessao, cenario: Cenario
) -> None:
    salva = _registrar(cenario, sessao)
    ocorrencia = service.occurrence_by_code(sessao, salva.code)
    assert ocorrencia is not None
    assert ocorrencia.situation == models.SITUATION_REGISTERED

    with pytest.raises(InvalidDataError, match="Investigue"):
        service.define_corrective_actions(
            sessao,
            user=cenario.maria,
            code=salva.code,
            actions_input=(acao_de(cenario),),
            reference_date=REFERENCIA,
        )
    with pytest.raises(InvalidDataError, match="ações corretivas"):
        service.start_treatment(sessao, user=cenario.maria, code=salva.code)

    _investigar(sessao, cenario, salva.code)
    assert ocorrencia.situation == models.SITUATION_INVESTIGATING

    record = _acao(sessao, cenario, salva.code)
    assert ocorrencia.situation == models.SITUATION_ACTIONS
    assert (record.origin, record.origin_ref, record.group) == (
        "HSE",
        salva.code,
        "Ação corretiva",
    )
    assert record.item == "1"

    service.start_treatment(sessao, user=cenario.maria, code=salva.code)
    assert ocorrencia.situation == models.SITUATION_TREATING

    with pytest.raises(InvalidDataError, match="aberto"):
        service.close_occurrence(
            sessao,
            user=cenario.gil,
            code=salva.code,
            data=encerramento_de(),
            reference_date=REFERENCIA,
        )
    _concluir(sessao, cenario, record)
    fechamento = service.close_occurrence(
        sessao,
        user=cenario.gil,
        code=salva.code,
        data=encerramento_de(),
        reference_date=REFERENCIA,
    )

    assert not fechamento.report_late
    assert fechamento.lesson_code is None, "sem HiPo não há lição"
    assert ocorrencia.situation == models.SITUATION_CLOSED
    sheet = service.occurrence_sheet(
        sessao, user=cenario.gil, code=salva.code, reference_date=REFERENCIA
    )
    assert sheet is not None
    assert sheet.line.effectiveness == encerramento_de().effectiveness
    assert sheet.line.closed_on == REFERENCIA
    assert [line.text for line in sheet.history][::-1] == [
        "Ocorrência registrada.",
        "Investigação registrada (5 porquês). Causa raiz: Ferramenta sem amarração durante o trabalho em altura.",
        "1 ação(ões) corretiva(s) criada(s) na Central.",
        "Tratamento iniciado.",
        "Ocorrência encerrada. Eficácia: Inspeções diárias seguidas sem reincidência do desvio.",
    ]


def test_a_investigacao_repetida_e_um_segundo_encerramento_sao_recusados(
    sessao, cenario: Cenario
) -> None:
    salva = _registrar(cenario, sessao)
    _investigar(sessao, cenario, salva.code)

    with pytest.raises(InvalidDataError, match="já foi investigada"):
        _investigar(sessao, cenario, salva.code)

    record = _acao(sessao, cenario, salva.code)
    _concluir(sessao, cenario, record)
    service.start_treatment(sessao, user=cenario.maria, code=salva.code)
    service.close_occurrence(
        sessao,
        user=cenario.gil,
        code=salva.code,
        data=encerramento_de(),
        reference_date=REFERENCIA,
    )

    with pytest.raises(InvalidDataError, match="já encerrada"):
        service.close_occurrence(
            sessao,
            user=cenario.gil,
            code=salva.code,
            data=encerramento_de(),
            reference_date=REFERENCIA,
        )
    with pytest.raises(InvalidDataError, match="já encerrada"):
        service.define_corrective_actions(
            sessao,
            user=cenario.maria,
            code=salva.code,
            actions_input=(acao_de(cenario),),
            reference_date=REFERENCIA,
        )


def test_encerrar_exige_gestor(sessao, cenario: Cenario) -> None:
    salva = _registrar(cenario, sessao)
    _investigar(sessao, cenario, salva.code)
    record = _acao(sessao, cenario, salva.code)
    _concluir(sessao, cenario, record)
    service.start_treatment(sessao, user=cenario.maria, code=salva.code)

    with pytest.raises(AccessDeniedError):
        service.close_occurrence(
            sessao,
            user=cenario.maria,
            code=salva.code,
            data=encerramento_de(),
            reference_date=REFERENCIA,
        )


# ── Prazos vencidos pela data de hoje ────────────────────────────────────────────────────────


def test_os_prazos_vencidos_saem_pela_data_de_hoje(sessao, cenario: Cenario) -> None:
    salva = _registrar(
        cenario,
        sessao,
        kind="Fatalidade",
        role="Operador de equipamento",
        happened_on=REFERENCIA - timedelta(days=40),
        communication_hours=30,
    )
    linha = _linha(sessao, cenario, salva.code)

    assert linha.communication_overdue is True, "30 h acima das 24 h gravadas"
    assert linha.investigation_late == "vencido", "Registrada há 40 dias com prazo de 2"
    assert linha.report_required is True, "nível 1 (LTI) exige o relatório final"
    assert linha.report_late == "vencido", "o limite de 30 dias passou"
    assert linha.overdue is True

    screen = service.occurrences_screen(
        sessao,
        scope=_escopo(cenario),
        filters=validation.OccurrenceFilters(),
        reference_date=REFERENCIA,
    )
    assert (screen.summary.total, screen.summary.overdue) == (1, 1)


def test_hipo_aberto_com_relatorio_no_prazo_e_a_investigacao_registrada_no_prazo(
    sessao, cenario: Cenario
) -> None:
    salva = _registrar(cenario, sessao, hipo=True, happened_on=ONTEM)
    _investigar(sessao, cenario, salva.code, investigated_on=REFERENCIA)
    linha = _linha(sessao, cenario, salva.code)

    assert linha.report_required is True
    assert linha.report_late is None, "o limite do HiPo ainda não venceu"
    assert linha.investigation_late is None, "investigada dentro do prazo preliminar"
    assert linha.overdue is False


# ── O HiPo encerrado e a lição (D9) ──────────────────────────────────────────────────────────


def test_hipo_encerrado_sem_licao_e_recusado_e_com_licao_abre_o_rascunho(
    sessao, cenario: Cenario
) -> None:
    salva = _registrar(cenario, sessao, hipo=True, happened_on=ONTEM)
    _investigar(sessao, cenario, salva.code)
    record = _acao(sessao, cenario, salva.code)
    _concluir(sessao, cenario, record)
    service.start_treatment(sessao, user=cenario.maria, code=salva.code)

    with pytest.raises(InvalidDataError, match="lição"):
        service.close_occurrence(
            sessao,
            user=cenario.gil,
            code=salva.code,
            data=encerramento_de(),
            reference_date=REFERENCIA,
        )
    ocorrencia = service.occurrence_by_code(sessao, salva.code)
    assert ocorrencia is not None and ocorrencia.situation == models.SITUATION_TREATING, (
        "a recusa não deixa nada gravado"
    )
    assert sessao.scalar(select(func.count()).select_from(lessons.Lesson)) == 0

    fechamento = service.close_occurrence(
        sessao,
        user=cenario.gil,
        code=salva.code,
        data=encerramento_de(
            lesson_title="Amarração de ferramentas em trabalho em altura",
            lesson_recommendation="Padronizar talabartes de ferramenta em todas as frentes de altura.",
        ),
        reference_date=REFERENCIA,
    )

    assert fechamento.lesson_code is not None
    licao = sessao.scalars(
        select(lessons.Lesson).where(lessons.Lesson.code == fechamento.lesson_code)
    ).one()
    assert (licao.origin, licao.origin_ref) == (lessons.ORIGIN_HSE, salva.code)
    assert licao.situation == lessons.SITUATION_DRAFT
    assert licao.project_id == cenario.projeto.id
    sheet = service.occurrence_sheet(
        sessao, user=cenario.gil, code=salva.code, reference_date=REFERENCIA
    )
    assert sheet is not None and sheet.lesson_code == fechamento.lesson_code


# ── O dado restrito (Q35) ───────────────────────────────────────────────────────────────────


def test_o_restrito_e_gravado_junto_e_so_gestor_e_admin_leem_de_volta(
    sessao, cenario: Cenario
) -> None:
    salva = _registrar(
        cenario,
        sessao,
        kind="Acidente com afastamento",
        role="Operador de equipamento",
        name="João da Silva",
        real_gravity=4,
        days_lost=5,
        days_charged=2,
        cat=True,
        medical_notes="Lesão com afastamento; CAT emitida.",
    )
    ocorrencia = service.occurrence_by_code(sessao, salva.code)
    assert ocorrencia is not None

    do_gestor = service.restricted_view(sessao, user=cenario.gil, code=salva.code)
    do_admin = service.restricted_view(sessao, user=cenario.ada, code=salva.code)

    assert do_gestor is not None
    assert do_gestor.name == "João da Silva"
    assert (do_gestor.real_gravity, do_gestor.days_lost, do_gestor.days_charged) == (4, 5, 2)
    assert do_gestor.cat is True
    assert do_gestor.medical_notes == "Lesão com afastamento; CAT emitida."
    assert do_admin is not None and do_admin.name == "João da Silva"

    with pytest.raises(AccessDeniedError):
        service.restricted_view(sessao, user=cenario.maria, code=salva.code)


def test_falha_ao_gravar_o_restrito_desfaz_a_ocorrencia(
    sessao, cenario: Cenario, monkeypatch
) -> None:
    chamadas: list[str] = []
    original = recording.create

    def falha_na_segunda(session, *, user_id, record):
        chamadas.append(type(record).__name__)
        if len(chamadas) > 1:
            raise RuntimeError
        return original(session, user_id=user_id, record=record)

    monkeypatch.setattr(recording, "create", falha_na_segunda)

    with pytest.raises(RuntimeError), sessao.begin_nested():
        _registrar(cenario, sessao)

    assert chamadas == ["Occurrence", "OccurrenceRestricted"]
    assert sessao.scalar(select(func.count()).select_from(Occurrence)) == 0
    assert sessao.scalar(select(func.count()).select_from(OccurrenceRestricted)) == 0


def test_ambiental_fica_fora_da_piramide_e_nao_tem_potencial_nem_hipo(
    sessao, cenario: Cenario
) -> None:
    salva = _registrar(
        cenario,
        sessao,
        kind="Ambiental",
        subtype="Vazamento",
        environmental_severity="Moderada",
        description="",
        potential_p=5,
        potential_i=5,
        hipo=True,
        real_gravity=4,
    )
    ocorrencia = service.occurrence_by_code(sessao, salva.code)
    assert ocorrencia is not None
    linha = _linha(sessao, cenario, salva.code)

    assert ocorrencia.environmental is True
    assert (ocorrencia.potential_p, ocorrencia.potential_i, ocorrencia.hipo) == (None, None, False)
    assert (ocorrencia.subtype, ocorrencia.environmental_severity) == ("Vazamento", "Moderada")
    assert linha.level is None and linha.level_name == "Ambiental"
    assert linha.band is None
    restrito = service.restricted_view(sessao, user=cenario.gil, code=salva.code)
    assert restrito is not None and restrito.real_gravity is None


def test_ambiental_exige_subtipo_e_severidade(sessao, cenario: Cenario) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        _registrar(cenario, sessao, kind="Ambiental", subtype="", environmental_severity="")

    mensagens = str(recusa.value)
    assert "subtipo" in mensagens and "severidade" in mensagens


# ── As mensagens da validação (o protótipo) ─────────────────────────────────────────────────


def test_a_descricao_curta_e_recusada_com_a_mensagem_do_prototipo(sessao, cenario: Cenario) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        _registrar(cenario, sessao, description="curta")

    assert "Descreva o ocorrido" in str(recusa.value)


def test_a_hora_fora_do_formato_e_recusada(sessao, cenario: Cenario) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        _registrar(cenario, sessao, happened_time="25:99")

    assert "HH:MM" in str(recusa.value)


def test_a_funcao_e_exigida_dos_tipos_com_pessoa_envolvida(sessao, cenario: Cenario) -> None:
    with pytest.raises(InvalidDataError) as recusa:
        _registrar(cenario, sessao, kind="Primeiros socorros", role="")

    assert "função" in str(recusa.value)


def test_a_investigacao_anterior_ao_evento_e_recusada(sessao, cenario: Cenario) -> None:
    salva = _registrar(cenario, sessao, happened_on=REFERENCIA)

    with pytest.raises(InvalidDataError, match="anterior"):
        _investigar(sessao, cenario, salva.code, investigated_on=ONTEM)

    # A recusa não deixa a ocorrência meio investigada.
    ocorrencia = service.occurrence_by_code(sessao, salva.code)
    assert ocorrencia is not None and ocorrencia.situation == models.SITUATION_REGISTERED
    assert sessao.scalar(select(func.count()).select_from(OccurrenceInvestigation)) == 0


def test_a_ocorrencia_sem_projeto_no_portfolio_nao_e_criada(sessao, cenario: Cenario) -> None:
    with pytest.raises(InvalidDataError):
        service.save_occurrence(
            sessao,
            user=cenario.maria,
            data=ocorrencia_de(cenario, project_id=0),
            reference_date=REFERENCIA,
        )


def test_a_acao_sem_responsavel_e_recusada(sessao, cenario: Cenario) -> None:
    salva = _registrar(cenario, sessao)
    _investigar(sessao, cenario, salva.code)

    with pytest.raises(InvalidDataError) as recusa:
        service.define_corrective_actions(
            sessao,
            user=cenario.maria,
            code=salva.code,
            actions_input=(acao_de(cenario, responsible_id=None),),
            reference_date=REFERENCIA,
        )

    assert "responsável" in str(recusa.value).lower()


def test_o_visualizador_nao_grava(sessao, cenario: Cenario) -> None:
    vendo = usuario_de(
        sessao,
        criar_colaborador(
            sessao,
            email="vera.hse@example.invalid",
            nome="Vera Visualizadora",
            perfil="Visualizador",
        ),
    )

    with pytest.raises(AccessDeniedError):
        service.save_occurrence(
            sessao, user=vendo, data=ocorrencia_de(cenario), reference_date=REFERENCIA
        )


def test_a_comunicacao_negativa_e_recusada(sessao, cenario: Cenario) -> None:
    with pytest.raises(InvalidDataError):
        _registrar(cenario, sessao, communication_hours=-1)
