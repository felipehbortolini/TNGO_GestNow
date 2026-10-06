"""Fachada da análise de impacto (ISSUE-024): início, conclusão, elevação da alçada e tipos especiais."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.errors import AccessDeniedError, InvalidDataError
from src.modulos.configuracoes import service as configuracoes
from src.modulos.financeiro import service as financeiro
from src.modulos.financeiro.service import NewItem
from src.modulos.governanca import models, service
from tests.governanca import apoio
from tests.governanca.apoio import HOJE


def _cenario(session: Session):
    projeto = apoio.projeto_com_orcamento(session)
    membro = apoio.colaborador(session, apoio.MEMBRO)
    usuario = apoio.usuario_de(membro)
    for codigo in ("1", "2", "3"):
        financeiro.create_item(
            session,
            user_id=membro.id,
            new=NewItem(
                project_id=projeto.id, code=codigo, description=f"Pacote {codigo}", level=1
            ),
        )
    return projeto, membro, usuario


def _registrar(session: Session, usuario, projeto, **campos: str) -> models.ChangeRequest:
    criada = apoio.registrar(session, usuario, projeto, **campos)
    return session.get(models.ChangeRequest, criada.id)


def _iniciar(session: Session, usuario, mudanca, *, prazo: str = "2026-10-16") -> None:
    service.start_analysis(
        session,
        user=usuario,
        code=mudanca.code,
        form={
            "responsavel_id": str(usuario.person_id),
            "prazo": prazo,
            "versao": str(mudanca.version),
        },
        reference_date=HOJE,
    )


def analise_valida(mudanca: models.ChangeRequest, **campos: str) -> dict[str, str]:
    """O formulário de uma análise que passa; ``campos`` troca os valores."""
    base = {
        "custo": "1.000,00",
        "prazo_dias": "5",
        "marco_contratual": "nao",
        "escopo": "Inclui o novo pacote de tratamento.",
        "qualidade": "Sem impacto",
        "riscos": "Sem impacto",
        "sms": "Sem impacto",
        "contrato": "Sem impacto",
        "alcada": "Gerente do projeto",
        "fonte_recurso": "Aditivo de orçamento",
        "itens_eac": "1, 2",
        "versao": str(mudanca.version),
    }
    base.update(campos)
    return base


def _concluir(session: Session, usuario, mudanca, **campos: str) -> models.ChangeRequest:
    return service.conclude_analysis(
        session,
        user=usuario,
        code=mudanca.code,
        form=analise_valida(mudanca, **campos),
        reference_date=HOJE,
    )


def _ficha(session: Session, usuario, mudanca) -> service.ChangeSheet:
    ficha = service.find_change_sheet(session, user=usuario, code=mudanca.code, reference_date=HOJE)
    assert ficha is not None
    return ficha


def test_iniciar_leva_a_em_analise_com_responsavel_e_prazo(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    mudanca = _registrar(sessao, usuario, projeto)
    _iniciar(sessao, usuario, mudanca)
    ficha = _ficha(sessao, usuario, mudanca)
    assert ficha.change.situation == models.SITUATION_ANALYSIS
    assert ficha.analysis is not None
    assert ficha.analysis.deadline.isoformat() == "2026-10-16"
    assert ficha.analysis.start_date == HOJE
    assert ficha.row.next_step == "Concluir a análise de impacto até 16/10/2026"
    assert ficha.analysis_action == service.ACTION_CONCLUDE


def test_o_formulario_de_inicio_sugere_o_prazo_do_parametro(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    mudanca = _registrar(sessao, usuario, projeto)
    formulario = service.analysis_start_form(
        sessao, user=usuario, code=mudanca.code, reference_date=HOJE
    )
    assert formulario.analysis_days == 10
    assert formulario.suggested_deadline.isoformat() == "2026-10-16"
    assert any(pessoa.id == usuario.person_id for pessoa in formulario.people)


def test_iniciar_so_vale_em_registrada(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    mudanca = _registrar(sessao, usuario, projeto)
    _iniciar(sessao, usuario, mudanca)
    with pytest.raises(InvalidDataError, match="Registrada"):
        _iniciar(sessao, usuario, mudanca)


def test_iniciar_pede_responsavel_e_prazo(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    mudanca = _registrar(sessao, usuario, projeto)
    with pytest.raises(InvalidDataError) as erro:
        service.start_analysis(
            sessao,
            user=usuario,
            code=mudanca.code,
            form={"versao": str(mudanca.version)},
            reference_date=HOJE,
        )
    assert set(erro.value.detail) == {"responsavel_id", "prazo"}


def test_visualizador_nao_inicia_nem_conclui(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    mudanca = _registrar(sessao, usuario, projeto)
    visualizador = apoio.usuario_de(
        apoio.colaborador(sessao, apoio.VISUALIZADOR, perfil="Visualizador")
    )
    with pytest.raises(AccessDeniedError):
        _iniciar(sessao, visualizador, mudanca)
    ficha = _ficha(sessao, visualizador, mudanca)
    assert ficha.analysis_action is None


def test_concluir_leva_a_aguardando_comite_e_a_ficha_mostra_a_analise(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    mudanca = _registrar(sessao, usuario, projeto)
    _iniciar(sessao, usuario, mudanca)
    _concluir(sessao, usuario, mudanca)
    ficha = _ficha(sessao, usuario, mudanca)
    assert ficha.change.situation == models.SITUATION_AWAITING
    assert ficha.change.authority == models.AUTHORITY_MANAGER
    assert ficha.change.resource_source == "Aditivo de orçamento"
    assert ficha.impact is not None
    assert ficha.impact.cost_cents == 100_000
    assert ficha.impact.term_days == 5
    assert ficha.impact.analysis_date == HOJE
    assert ficha.eac_item_codes == ("1", "2")
    assert ficha.required_authority == models.AUTHORITY_MANAGER
    assert ficha.analysis is not None
    assert ficha.analysis.concluded_on == HOJE
    assert ficha.row.next_step == "Decisão do gerente do projeto"


def test_custo_alto_exige_o_comite_e_a_proxima_etapa_diz_quem_decide(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    mudanca = _registrar(sessao, usuario, projeto)
    _iniciar(sessao, usuario, mudanca)
    _concluir(sessao, usuario, mudanca, custo="500.000,00", alcada="Comitê")
    ficha = _ficha(sessao, usuario, mudanca)
    assert ficha.required_authority == models.AUTHORITY_COMMITTEE
    assert ficha.row.next_step == "Decisão do Comitê"


def test_fronteira_do_percentual_do_orcamento(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    limite = "446.000,00"
    no_limite = _registrar(sessao, usuario, projeto, titulo="Mudança exatamente no limite")
    _iniciar(sessao, usuario, no_limite)
    _concluir(sessao, usuario, no_limite, custo=limite)
    assert _ficha(sessao, usuario, no_limite).required_authority == models.AUTHORITY_MANAGER
    acima = _registrar(sessao, usuario, projeto, titulo="Mudança um centavo acima do limite")
    _iniciar(sessao, usuario, acima)
    with pytest.raises(InvalidDataError) as erro:
        _concluir(sessao, usuario, acima, custo="446.000,01")
    assert "nunca rebaixada" in erro.value.detail["alcada"]


def test_fronteira_do_marco_contratual(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    mudanca = _registrar(sessao, usuario, projeto)
    _iniciar(sessao, usuario, mudanca)
    with pytest.raises(InvalidDataError) as erro:
        _concluir(sessao, usuario, mudanca, custo="0", marco_contratual="sim", fonte_recurso="")
    assert "alcada" in erro.value.detail
    _concluir(
        sessao,
        usuario,
        mudanca,
        custo="0",
        marco_contratual="sim",
        alcada="Comitê",
        fonte_recurso="",
    )
    assert _ficha(sessao, usuario, mudanca).required_authority == models.AUTHORITY_COMMITTEE


def test_elevar_e_aceito_e_a_ficha_guarda_a_alcada_elevada(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    mudanca = _registrar(sessao, usuario, projeto)
    _iniciar(sessao, usuario, mudanca)
    _concluir(sessao, usuario, mudanca, alcada="Comitê")
    ficha = _ficha(sessao, usuario, mudanca)
    assert ficha.change.authority == models.AUTHORITY_COMMITTEE
    assert ficha.required_authority == models.AUTHORITY_MANAGER
    assert ficha.row.next_step == "Decisão do Comitê"


def test_analise_sem_campos_obrigatorios_e_422_por_campo(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    mudanca = _registrar(sessao, usuario, projeto)
    _iniciar(sessao, usuario, mudanca)
    with pytest.raises(InvalidDataError) as erro:
        service.conclude_analysis(
            sessao,
            user=usuario,
            code=mudanca.code,
            form={"versao": str(mudanca.version)},
            reference_date=HOJE,
        )
    assert {"custo", "prazo_dias", "marco_contratual", "escopo", "contrato", "alcada"} <= set(
        erro.value.detail
    )
    assert _ficha(sessao, usuario, mudanca).change.situation == models.SITUATION_ANALYSIS


def test_concluir_exige_a_situacao_em_analise_ou_a_revisao_antes_da_decisao(
    sessao: Session,
) -> None:
    projeto, _, usuario = _cenario(sessao)
    mudanca = _registrar(sessao, usuario, projeto)
    with pytest.raises(InvalidDataError, match="em análise"):
        _concluir(sessao, usuario, mudanca)


def test_item_da_eac_que_nao_existe_e_recusado_no_campo(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    mudanca = _registrar(sessao, usuario, projeto)
    _iniciar(sessao, usuario, mudanca)
    with pytest.raises(InvalidDataError) as erro:
        _concluir(sessao, usuario, mudanca, itens_eac="1, 9.9.9")
    assert "9.9.9" in erro.value.detail["itens_eac"]


def test_revisao_antes_da_decisao_mantem_a_situacao_e_atualiza_o_mesmo_impacto(
    sessao: Session,
) -> None:
    projeto, _, usuario = _cenario(sessao)
    mudanca = _registrar(sessao, usuario, projeto)
    _iniciar(sessao, usuario, mudanca)
    _concluir(sessao, usuario, mudanca)
    ficha = _ficha(sessao, usuario, mudanca)
    assert ficha.analysis_action == service.ACTION_REVIEW
    formulario = service.impact_form(sessao, user=usuario, code=mudanca.code, reference_date=HOJE)
    assert formulario.is_review
    assert formulario.values["custo"] == "1.000,00"
    assert formulario.values["itens_eac"] == "1, 2"
    revisao = analise_valida(
        ficha.change,
        custo="2.000,00",
        itens_eac="3",
        versao_impacto=str(ficha.impact.version),
    )
    service.conclude_analysis(
        sessao, user=usuario, code=mudanca.code, form=revisao, reference_date=HOJE
    )
    depois = _ficha(sessao, usuario, mudanca)
    assert depois.change.situation == models.SITUATION_AWAITING
    assert depois.impact.cost_cents == 200_000
    assert depois.eac_item_codes == ("3",)
    quantidade = len(
        sessao.scalars(
            select(models.ChangeImpact).where(models.ChangeImpact.change_id == mudanca.id)
        ).all()
    )
    assert quantidade == 1


def test_remanejamento_tem_custo_zero_transferencias_e_alcada_pelo_total(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    mudanca = _registrar(sessao, usuario, projeto, tipo=models.TYPE_REALLOCATION)
    _iniciar(sessao, usuario, mudanca)
    with pytest.raises(InvalidDataError) as erro:
        _concluir(sessao, usuario, mudanca, custo="10,00", fonte_recurso="")
    assert "custo zero" in erro.value.detail["custo"]
    transferencia = {
        "custo": "0",
        "fonte_recurso": "",
        "itens_eac": "",
        "remanejamento_origem_1": "1",
        "remanejamento_destino_1": "2",
        "remanejamento_valor_1": "150.000,00",
    }
    _concluir(sessao, usuario, mudanca, **transferencia)
    ficha = _ficha(sessao, usuario, mudanca)
    assert ficha.change.authority == models.AUTHORITY_MANAGER
    assert [(t.source_code, t.target_code, t.value_cents) for t in ficha.transfers] == [
        ("1", "2", 15_000_000)
    ]
    assert ficha.total_transferred_cents == 15_000_000
    assert ficha.eac_item_codes == ("1", "2")
    assert ficha.impact.cost_cents == 0


def test_remanejamento_acima_do_limite_vai_ao_comite_e_recusa_o_gerente(sessao: Session) -> None:
    projeto, _, usuario = _cenario(sessao)
    mudanca = _registrar(sessao, usuario, projeto, tipo=models.TYPE_REALLOCATION)
    _iniciar(sessao, usuario, mudanca)
    grande = {
        "custo": "0",
        "fonte_recurso": "",
        "itens_eac": "",
        "remanejamento_origem_1": "1",
        "remanejamento_destino_1": "2",
        "remanejamento_valor_1": "446.000,01",
    }
    with pytest.raises(InvalidDataError) as erro:
        _concluir(sessao, usuario, mudanca, **grande)
    assert "nunca rebaixada" in erro.value.detail["alcada"]
    _concluir(sessao, usuario, mudanca, alcada="Comitê", **grande)
    assert _ficha(sessao, usuario, mudanca).required_authority == models.AUTHORITY_COMMITTEE


def test_liberacao_de_reserva_tem_custo_zero_a_reserva_o_valor_e_vai_ao_comite(
    sessao: Session,
) -> None:
    projeto, _, usuario = _cenario(sessao)
    mudanca = _registrar(sessao, usuario, projeto, tipo=models.TYPE_RESERVE_RELEASE)
    _iniciar(sessao, usuario, mudanca)
    base = {"custo": "0", "fonte_recurso": "", "itens_eac": ""}
    with pytest.raises(InvalidDataError) as erro:
        _concluir(sessao, usuario, mudanca, **base)
    assert {"liberacao_reserva", "liberacao_valor", "alcada"} <= set(erro.value.detail)
    _concluir(
        sessao,
        usuario,
        mudanca,
        alcada="Comitê",
        liberacao_reserva="Contingência",
        liberacao_valor="25.000,00",
        **base,
    )
    ficha = _ficha(sessao, usuario, mudanca)
    assert ficha.impact.release_reserve == "Contingência"
    assert ficha.impact.release_value_cents == 2_500_000
    assert ficha.impact.cost_cents == 0
    assert ficha.required_authority == models.AUTHORITY_COMMITTEE


def test_o_projeto_do_item_e_o_da_mudanca(sessao: Session) -> None:
    projeto, membro, usuario = _cenario(sessao)
    outro = apoio.projeto_com_orcamento(sessao, codigo="TN-2026-015", padrao="TN-2026-B")
    financeiro.create_item(
        sessao,
        user_id=membro.id,
        new=NewItem(project_id=outro.id, code="7", description="Pacote 7", level=1),
    )
    mudanca = _registrar(sessao, usuario, projeto)
    _iniciar(sessao, usuario, mudanca)
    with pytest.raises(InvalidDataError) as erro:
        _concluir(sessao, usuario, mudanca, itens_eac="7")
    assert "7" in erro.value.detail["itens_eac"]
    assert configuracoes.find_project(sessao, outro.id) is not None
