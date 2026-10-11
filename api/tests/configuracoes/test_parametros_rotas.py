"""As rotas da tela Parâmetros do sistema (ISSUE-076): tela, modal, gravação, histórico e exports.

O handler é chamado com a requisição de Alpine, o cookie da demonstração identificando a pessoa
e a unidade de trabalho do teste (fixture ``sessao``). A gravação cria uma versão por grupo de
origem que mudou; a troca da escala de riscos pede confirmação e muda a severidade na consulta
seguinte pela fachada da Riscos.
"""

from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import unquote, urlencode

import azure.functions as func
import pytest
from sqlalchemy.orm import Session

from src.core.auth import DEMO_COOKIE
from src.core.rbac import User
from src.modulos.configuracoes import forms, routes, service
from src.modulos.configuracoes.models import PortfolioWeight
from src.modulos.riscos import ficha_service
from src.modulos.riscos import service as riscos_service
from tests.apoio_riscos import REFERENCIA, Cenario, nova_avaliacao, novo_risco

TELA = "/api/configuracoes/parametros"
JUSTIFICATIVA = "Ajuste dos parâmetros para o teste da tela."


def _requisicao(
    usuario: User,
    *,
    metodo: str = "GET",
    caminho: str = TELA,
    params: Mapping[str, str] | None = None,
    rota: Mapping[str, str] | None = None,
    corpo: Mapping[str, str] | None = None,
    alvo: str = "parametros-conteudo",
    cabecalho: bool = True,
) -> func.HttpRequest:
    headers = {"X-Alpine-Target": alvo, "Cookie": f"{DEMO_COOKIE}={usuario.id}"}
    if cabecalho:
        headers["X-Alpine-Request"] = "true"
    if corpo is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    return func.HttpRequest(
        method=metodo,
        url=caminho,
        headers=headers,
        params=dict(params or {}),
        route_params=dict(rota or {}),
        body=urlencode(corpo, doseq=True).encode() if corpo is not None else b"",
    )


def _corpo_do_grupo(
    sessao: Session,
    grupo: str,
    *,
    justificativa: str = JUSTIFICATIVA,
    **mudancas: str,
) -> dict[str, str]:
    """O formulário de um grupo como o navegador o envia: os campos vigentes, sem os somente leitura."""
    atual = service.current_parameters(sessao, reference_date=REFERENCIA)
    group = forms.find_group(forms.group_forms(atual), grupo)
    assert group is not None
    corpo: dict[str, str] = {}
    for campo in group.campos:
        if campo.somente:
            continue
        corpo[campo.field_id] = forms.input_text(campo, forms.value_at(atual, campo.caminho))
    corpo.update(mudancas)
    corpo["justificativa"] = justificativa
    return corpo


def _gravar(
    cenario: Cenario, grupo: str, corpo: Mapping[str, str], usuario: User | None = None
) -> func.HttpResponse:
    return routes.parameters_save(
        _requisicao(
            usuario or cenario.gil,
            metodo="POST",
            caminho=f"{TELA}/{grupo}",
            rota={"grupo": grupo},
            corpo=corpo,
            alvo="parametros-modal-corpo",
        )
    )


# ── A tela ───────────────────────────────────────────────────────────────────────────────────


def test_a_tela_lista_os_grupos_e_os_valores_vigentes(cenario: Cenario) -> None:
    resposta = routes.parameters_screen(
        _requisicao(cenario.gil, params={"projeto": str(cenario.projeto.id)})
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    for nome in (
        "Avaliação de contratadas",
        "Financeiro",
        "Suprimentos",
        "Riscos",
        "Qualidade",
        "HSE",
        "Planejamento",
        "Governança",
        "Portfólio",
        "Anexos",
    ):
        assert nome in corpo
    assert "Versão vigente" in corpo
    assert "R$ 500.000,00" in corpo  # alçada em centavos, lida em reais
    assert "Timenow (4 faixas)" in corpo  # select pelo texto da opção
    assert "8,80 h" in corpo  # jornada 8.8 com duas casas e unidade
    assert "v1" in corpo
    assert 'data-situacao="conteudo"' in corpo
    assert "Editar" in corpo
    assert 'data-tn-excel="/api/configuracoes/parametros/excel"' in corpo
    assert 'data-tn-pdf="/api/configuracoes/parametros/imprimivel"' in corpo


def test_o_admin_tambem_chega_a_tela(cenario: Cenario) -> None:
    resposta = routes.parameters_screen(_requisicao(cenario.ada))

    assert resposta.status_code == 200


@pytest.mark.parametrize("perfil", ["mario", "vera"])
def test_quem_nao_e_gestor_nem_admin_recebe_403(
    sessao: Session, cenario: Cenario, perfil: str
) -> None:
    usuario: User = getattr(cenario, perfil)

    tela = routes.parameters_screen(_requisicao(usuario))
    corpo = _corpo_do_grupo(sessao, "governanca", licoes__alertaSemRegistroDias="60")
    gravacao = _gravar(cenario, "governanca", corpo, usuario=usuario)

    assert tela.status_code == 403
    assert gravacao.status_code == 403


def test_a_busca_filtra_no_servidor(cenario: Cenario) -> None:
    resposta = routes.parameters_screen(_requisicao(cenario.gil, params={"busca": "alçada"}))

    corpo = resposta.get_body().decode()
    assert "Alçada: Gerente de suprimentos até" in corpo
    assert "Suprimentos" in corpo
    assert "Nota mínima da classe A" not in corpo


def test_o_filtro_de_modulo_filtra_no_servidor(cenario: Cenario) -> None:
    resposta = routes.parameters_screen(_requisicao(cenario.gil, params={"modulo": "05"}))

    corpo = resposta.get_body().decode()
    assert "Escala de severidade ativa" in corpo
    assert "Prazo de tratamento da RNC" not in corpo
    assert 'value="05" selected' in corpo


def test_busca_sem_resultado_mostra_o_vazio_por_filtro(cenario: Cenario) -> None:
    resposta = routes.parameters_screen(_requisicao(cenario.gil, params={"busca": "zzz"}))

    corpo = resposta.get_body().decode()
    assert 'data-situacao="vazio-filtro"' in corpo
    assert "Nenhum parâmetro encontrado" in corpo


def test_sem_o_cabecalho_do_alpine_a_tela_manda_para_o_shell(cenario: Cenario) -> None:
    resposta = routes.parameters_screen(_requisicao(cenario.gil, cabecalho=False))

    assert resposta.status_code == 302


# ── O modal de edição ────────────────────────────────────────────────────────────────────────


def test_o_modal_de_edicao_traz_os_campos_vigentes(cenario: Cenario) -> None:
    resposta = routes.parameters_edit_form(
        _requisicao(
            cenario.gil,
            caminho=f"{TELA}/riscos/editar",
            rota={"grupo": "riscos"},
            alvo="parametros-modal-corpo",
        )
    )

    corpo = resposta.get_body().decode()
    assert resposta.status_code == 200
    assert "Escala de severidade ativa" in corpo
    assert "Timenow (4 faixas)" in corpo
    assert "CIPM ArcelorMittal (3 faixas)" in corpo
    assert "Cadência máxima de revisão: Crítico" in corpo
    assert "Probabilidade média: Muito baixa (até 10%)" in corpo
    assert "Justificativa da alteração" in corpo
    assert "Confirmo a troca da escala de severidade" in corpo


def test_o_modal_mostra_a_alcada_em_reais(cenario: Cenario) -> None:
    resposta = routes.parameters_edit_form(
        _requisicao(
            cenario.gil,
            caminho=f"{TELA}/suprimentos/editar",
            rota={"grupo": "suprimentos"},
            alvo="parametros-modal-corpo",
        )
    )

    corpo = resposta.get_body().decode()
    assert "Alçada: Gerente de suprimentos até" in corpo
    assert 'value="R$ 500.000,00"' in corpo
    assert "Peso do marco: Fabricação" in corpo


# ── A gravação ───────────────────────────────────────────────────────────────────────────────


def test_gravar_sem_justificativa_e_recusado(sessao: Session, cenario: Cenario) -> None:
    corpo = _corpo_do_grupo(
        sessao, "governanca", justificativa="curta", licoes__alertaSemRegistroDias="60"
    )

    resposta = _gravar(cenario, "governanca", corpo)

    assert resposta.status_code == 422
    assert "Informe a justificativa da alteração (mínimo de 10 caracteres)." in (
        resposta.get_body().decode()
    )
    versao = service.current_version(sessao, group="licoes", reference_date=REFERENCIA)
    assert versao is not None and versao.version == 1


def test_gravar_sem_alteracao_e_recusado(sessao: Session, cenario: Cenario) -> None:
    corpo = _corpo_do_grupo(sessao, "governanca")

    resposta = _gravar(cenario, "governanca", corpo)

    assert resposta.status_code == 422
    assert "Nenhum valor foi alterado." in resposta.get_body().decode()


def test_valor_invalido_do_bloco_volta_no_formulario(sessao: Session, cenario: Cenario) -> None:
    corpo = _corpo_do_grupo(sessao, "suprimentos", suprimentos__pesosMarcos__propostas="99")

    resposta = _gravar(cenario, "suprimentos", corpo)

    assert resposta.status_code == 422
    assert "A soma dos pesos dos marcos do MAS deve ser 100% (atual: 194%)." in (
        resposta.get_body().decode()
    )


def test_valor_nao_numerico_volta_no_campo(sessao: Session, cenario: Cenario) -> None:
    corpo = _corpo_do_grupo(sessao, "governanca", licoes__alertaSemRegistroDias="abc")

    resposta = _gravar(cenario, "governanca", corpo)

    corpo_da_recusa = resposta.get_body().decode()
    assert resposta.status_code == 422
    assert "Informe um número." in corpo_da_recusa
    assert 'id="erro-licoes__alertaSemRegistroDias"' in corpo_da_recusa


def test_gravar_cria_nova_versao_com_vigencia_e_autor(sessao: Session, cenario: Cenario) -> None:
    corpo = _corpo_do_grupo(sessao, "governanca", licoes__alertaSemRegistroDias="60")

    resposta = _gravar(cenario, "governanca", corpo)

    assert resposta.status_code == 200
    assert "60 dias" in resposta.get_body().decode()
    assert unquote(resposta.headers["X-TN-Toast"]) == "Versão 2 gravada: 1 parâmetro alterado."
    versao = service.current_version(sessao, group="licoes", reference_date=REFERENCIA)
    assert versao is not None and versao.version == 2
    assert versao.effective_from == REFERENCIA
    assert versao.author_id == cenario.gil.id
    assert versao.justification == JUSTIFICATIVA
    vigente = service.current_group(sessao, group="licoes", reference_date=REFERENCIA)
    assert vigente["alertaSemRegistroDias"] == 60


def test_gravar_grupo_misto_cria_versao_so_do_grupo_que_mudou(
    sessao: Session, cenario: Cenario
) -> None:
    corpo = _corpo_do_grupo(sessao, "planejamento", produtividade__semanasMedia="6")

    resposta = _gravar(cenario, "planejamento", corpo)

    assert resposta.status_code == 200
    assert unquote(resposta.headers["X-TN-Toast"]) == "Versão 2 gravada: 1 parâmetro alterado."
    produtividade = service.current_version(
        sessao, group="produtividade", reference_date=REFERENCIA
    )
    assert produtividade is not None and produtividade.version == 2
    for intocado in ("punch", "eap"):
        versao = service.current_version(sessao, group=intocado, reference_date=REFERENCIA)
        assert versao is not None and versao.version == 1


# ── A escala de riscos ───────────────────────────────────────────────────────────────────────


def test_a_troca_de_escala_pede_confirmacao_e_muda_a_severidade(
    sessao: Session, cenario: Cenario
) -> None:
    risco = riscos_service.save_risk(
        sessao, user=cenario.mario, data=novo_risco(cenario), reference_date=REFERENCIA
    )
    avaliacao = riscos_service.assess_risk(
        sessao,
        user=cenario.mario,
        code=risco.code,
        data=nova_avaliacao(probability=5, impact=4),
        reference_date=REFERENCIA,
    )
    assert avaliacao.severity.id == "critico"

    corpo = _corpo_do_grupo(sessao, "riscos", riscos__escalaAtiva="cipm")
    sem_confirmar = _gravar(cenario, "riscos", corpo)

    assert sem_confirmar.status_code == 422
    assert "muda as faixas e a contagem de riscos críticos" in sem_confirmar.get_body().decode()
    versao = service.current_version(sessao, group="riscos", reference_date=REFERENCIA)
    assert versao is not None and versao.version == 1

    corpo["confirmar_escala"] = "sim"
    com_confirmacao = _gravar(cenario, "riscos", corpo)

    assert com_confirmacao.status_code == 200
    assert "CIPM ArcelorMittal (3 faixas)" in com_confirmacao.get_body().decode()
    versao = service.current_version(sessao, group="riscos", reference_date=REFERENCIA)
    assert versao is not None and versao.version == 2
    folha = ficha_service.find_risk_sheet(
        sessao, user=cenario.mario, code=risco.code, reference_date=REFERENCIA
    )
    assert folha is not None and folha.line.inherent is not None
    assert folha.line.inherent.severity.id == "alto"


# ── O histórico ──────────────────────────────────────────────────────────────────────────────


def test_o_historico_mostra_antes_e_depois(sessao: Session, cenario: Cenario) -> None:
    corpo = _corpo_do_grupo(sessao, "governanca", licoes__alertaSemRegistroDias="60")
    _gravar(cenario, "governanca", corpo)

    lista = routes.parameters_history(
        _requisicao(cenario.gil, caminho=f"{TELA}/historico", alvo="parametros-modal-corpo")
    )
    texto = lista.get_body().decode()
    assert lista.status_code == 200
    assert "<b>v2</b>" in texto and "Vigente" in texto
    assert JUSTIFICATIVA in texto
    assert "Alterações da v2" not in texto

    detalhe = routes.parameters_history(
        _requisicao(
            cenario.gil,
            caminho=f"{TELA}/historico",
            params={"grupo": "licoes", "versao": "2"},
            alvo="parametros-modal-corpo",
        )
    )
    texto_do_detalhe = detalhe.get_body().decode()
    assert "Alterações da v2 · Governança" in texto_do_detalhe
    assert "Alerta de projeto sem lição registrada" in texto_do_detalhe
    assert "90 dias" in texto_do_detalhe and "60 dias" in texto_do_detalhe

    inicial = routes.parameters_history(
        _requisicao(
            cenario.gil,
            caminho=f"{TELA}/historico",
            params={"grupo": "licoes", "versao": "1"},
            alvo="parametros-modal-corpo",
        )
    )
    assert "Alterações da v1" not in inicial.get_body().decode()


def test_o_historico_marca_a_vigente_de_cada_grupo(sessao: Session, cenario: Cenario) -> None:
    corpo = _corpo_do_grupo(sessao, "governanca", licoes__alertaSemRegistroDias="60")
    _gravar(cenario, "governanca", corpo)

    resposta = routes.parameters_history(
        _requisicao(cenario.gil, caminho=f"{TELA}/historico", alvo="parametros-modal-corpo")
    )

    texto = resposta.get_body().decode()
    assert "Versão inicial" in texto
    assert texto.count("Vigente") == len(service.PARAMETER_GROUPS)


def test_a_nova_versao_do_portfolio_leva_as_notas_dos_projetos(
    sessao: Session, cenario: Cenario
) -> None:
    versao = service.current_version(sessao, group="portfolio", reference_date=REFERENCIA)
    assert versao is not None
    sessao.add(
        PortfolioWeight(
            version_id=versao.id,
            project_id=cenario.projeto.id,
            criterion="estrategico",
            grade=5,
        )
    )
    sessao.flush()

    corpo = _corpo_do_grupo(
        sessao,
        "portfolio",
        portfolio__criterios__1__peso="30",
        portfolio__criterios__2__peso="10",
    )
    resposta = _gravar(cenario, "portfolio", corpo)

    assert resposta.status_code == 200
    nova = service.current_version(sessao, group="portfolio", reference_date=REFERENCIA)
    assert nova is not None and nova.version == 2
    assert service.portfolio_grades(sessao, reference_date=REFERENCIA)[cenario.projeto.id] == {
        "estrategico": 5
    }


# ── As exportações ───────────────────────────────────────────────────────────────────────────


def test_excel_e_imprimivel_saem_com_as_duas_tabelas(cenario: Cenario) -> None:
    excel = routes.parameters_excel(
        _requisicao(cenario.gil, caminho=f"{TELA}/excel", alvo="parametros-conteudo")
    )
    imprimivel = routes.parameters_printable(
        _requisicao(cenario.gil, caminho=f"{TELA}/imprimivel", alvo="parametros-conteudo")
    )

    assert excel.status_code == 200
    assert excel.get_body().startswith(b"PK")
    texto = imprimivel.get_body().decode()
    assert imprimivel.status_code == 200
    assert "Parâmetros vigentes" in texto
    assert "Histórico de versões" in texto
    assert "R$ 500.000,00" in texto
    assert "v1" in texto
    assert "<script" not in texto
