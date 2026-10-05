"""Regras de validação da seção 7.4, uma função por regra, com o caso de fronteira.

Cada teste altera um valor no grupo inicial e confere a fronteira: o valor
inválido acusa o campo e o valor no limite (quando existe) passa. O grupo
inicial inteiro passa em
``test_parametros.test_valores_iniciais_de_todos_os_grupos_passam_na_validacao``.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.modulos.configuracoes import validation
from src.modulos.configuracoes.service import INITIAL_PARAMETERS


def _erros(grupo: str, caminho: str, valor: Any) -> dict[str, str]:
    valores = deepcopy(INITIAL_PARAMETERS[grupo])
    _definir(valores, caminho, valor)
    return validation.validate_parameter_group(grupo, valores)


def _definir(valores: dict[str, Any], caminho: str, valor: Any) -> None:
    partes = caminho.split(".")
    alvo: Any = valores
    for parte in partes[:-1]:
        alvo = alvo[int(parte)] if parte.isdigit() else alvo[parte]
    ultima = partes[-1]
    if ultima.isdigit():
        alvo[int(ultima)] = valor
    else:
        alvo[ultima] = valor


def _vale(grupo: str) -> None:
    assert validation.validate_parameter_group(grupo, INITIAL_PARAMETERS[grupo]) == {}


def test_pesos_da_avaliacao_somam_100() -> None:
    assert "avaliacaoContratada.criterios" in _erros("avaliacaoContratada", "criterios.5.peso", 9)
    assert "avaliacaoContratada.criterios" not in _erros(
        "avaliacaoContratada", "criterios.5.peso", 10
    )
    _vale("avaliacaoContratada")


def test_notas_minimas_das_classes_sao_decrescentes() -> None:
    assert "avaliacaoContratada.classes" in _erros("avaliacaoContratada", "classes.1.minimo", 85)
    assert "avaliacaoContratada.classes" not in _erros(
        "avaliacaoContratada", "classes.1.minimo", 84
    )
    _vale("avaliacaoContratada")


def test_prazos_de_hse_nao_invertem_comunicacao_e_investigacao() -> None:
    assert "hse.prazos" in _erros("hse", "prazos.investigacaoPreliminarHoras", 23)
    # Fronteira: iguais passam.
    assert "hse.prazos" not in _erros("hse", "prazos.investigacaoPreliminarHoras", 24)
    assert "hse.prazos" in _erros("hse", "prazos.relatorioFinalDias", 0)


def test_base_das_taxas_de_hse_tem_duas_opcoes() -> None:
    assert "hse.baseTaxa" in _erros("hse", "baseTaxa", 500000)
    assert "hse.baseTaxa" not in _erros("hse", "baseTaxa", 1000000)
    assert "hse.baseTaxa" not in _erros("hse", "baseTaxa", 200000)


def test_metas_proativas_de_hse_ficam_entre_0_e_1000() -> None:
    assert "hse.metas" in _erros("hse", "metas.observacoesPor10MilHht", -1)
    assert "hse.metas" in _erros("hse", "metas.desviosPor10MilHht", 1001)
    assert "hse.metas" not in _erros("hse", "metas.observacoesPor10MilHht", 0)
    assert "hse.metas" not in _erros("hse", "metas.desviosPor10MilHht", 1000)


def test_pesos_dos_marcos_do_mas_somam_100() -> None:
    assert "suprimentos.pesosMarcos" in _erros("suprimentos", "pesosMarcos.fabricacao", 29)
    assert "suprimentos.pesosMarcos" not in _erros("suprimentos", "pesosMarcos.fabricacao", 30)
    _vale("suprimentos")


def test_alcadas_de_suprimentos_crescem_e_a_ultima_e_sem_teto() -> None:
    assert "suprimentos.alcadas" in _erros("suprimentos", "alcadas.1.ate", 50000000)
    assert "suprimentos.alcadas" in _erros("suprimentos", "alcadas.2.ate", 600000000)
    assert "suprimentos.alcadas" in _erros("suprimentos", "alcadas.0.ate", 0)
    assert "suprimentos.alcadas" not in _erros("suprimentos", "alcadas.1.ate", 50000001)
    _vale("suprimentos")


def test_minimo_de_propostas_e_pelo_menos_1() -> None:
    assert "suprimentos.propostasMinimas" in _erros("suprimentos", "propostasMinimas", 0)
    assert "suprimentos.propostasMinimas" not in _erros("suprimentos", "propostasMinimas", 1)


def test_cadencia_de_revisao_cresce_do_mais_grave_ao_mais_leve() -> None:
    assert "riscos.cadenciaDias" in _erros("riscos", "cadenciaDias.alto", 14)
    # Fronteira: empate passa (a regra é crescente, não estritamente).
    assert "riscos.cadenciaDias" not in _erros("riscos", "cadenciaDias.alto", 15)
    assert "riscos.cadenciaDias" in _erros("riscos", "cadenciaDias.critico", 0)
    _vale("riscos")


def test_probabilidades_medias_crescem_entre_0_e_100() -> None:
    assert "riscos.probabilidades" in _erros("riscos", "probabilidades.1.mediaPct", 5)
    assert "riscos.probabilidades" in _erros("riscos", "probabilidades.0.mediaPct", 0)
    assert "riscos.probabilidades" in _erros("riscos", "probabilidades.4.mediaPct", 100)
    assert "riscos.probabilidades" in _erros("riscos", "probabilidades.1.mediaPct", 4)
    assert "riscos.probabilidades" not in _erros("riscos", "probabilidades.1.mediaPct", 6)
    _vale("riscos")


def test_alcada_do_gerente_fica_entre_0_e_10_pct() -> None:
    assert "mudancas.alcadaGerentePctOrcamento" in _erros(
        "mudancas", "alcadaGerentePctOrcamento", 0
    )
    assert "mudancas.alcadaGerentePctOrcamento" in _erros(
        "mudancas", "alcadaGerentePctOrcamento", 10.1
    )
    assert "mudancas.alcadaGerentePctOrcamento" not in _erros(
        "mudancas", "alcadaGerentePctOrcamento", 10
    )


def test_quorum_do_comite_e_de_2_ou_mais() -> None:
    assert "mudancas.quorumComite" in _erros("mudancas", "quorumComite", 1)
    assert "mudancas.quorumComite" not in _erros("mudancas", "quorumComite", 2)


def test_prazos_de_mudancas_ficam_entre_1_e_90_dias() -> None:
    assert "mudancas.prazos" in _erros("mudancas", "prazoAnaliseDias", 0)
    assert "mudancas.prazos" in _erros("mudancas", "prazoAcoesDias", 91)
    assert "mudancas.prazos" not in _erros("mudancas", "ratificacaoDias", 1)
    assert "mudancas.prazos" not in _erros("mudancas", "ratificacaoDias", 90)


def test_alerta_de_licoes_fica_entre_30_e_365_dias() -> None:
    assert "licoes.alertaSemRegistroDias" in _erros("licoes", "alertaSemRegistroDias", 29)
    assert "licoes.alertaSemRegistroDias" in _erros("licoes", "alertaSemRegistroDias", 366)
    assert "licoes.alertaSemRegistroDias" not in _erros("licoes", "alertaSemRegistroDias", 30)
    assert "licoes.alertaSemRegistroDias" not in _erros("licoes", "alertaSemRegistroDias", 365)


def test_jornada_diaria_fica_entre_4_e_12_horas() -> None:
    assert "produtividade.jornadaDiariaHoras" in _erros("produtividade", "jornadaDiariaHoras", 3.9)
    assert "produtividade.jornadaDiariaHoras" in _erros("produtividade", "jornadaDiariaHoras", 12.1)
    assert "produtividade.jornadaDiariaHoras" not in _erros(
        "produtividade", "jornadaDiariaHoras", 4
    )
    assert "produtividade.jornadaDiariaHoras" not in _erros(
        "produtividade", "jornadaDiariaHoras", 12
    )


def test_metas_de_produtividade_ficam_entre_0_e_100() -> None:
    assert "produtividade.metas" in _erros("produtividade", "metaTrabalhandoPct", 0)
    assert "produtividade.metas" in _erros("produtividade", "metaUtilizacaoPct", 101)
    assert "produtividade.metas" not in _erros("produtividade", "metaTrabalhandoPct", 1)
    assert "produtividade.metas" not in _erros("produtividade", "metaUtilizacaoPct", 100)


def test_faixas_de_aderencia_crescem_ate_100() -> None:
    assert "produtividade.aderenciaFaixas" in _erros("produtividade", "aderenciaFaixas.0", 0)
    assert "produtividade.aderenciaFaixas" in _erros("produtividade", "aderenciaFaixas.1", 75)
    assert "produtividade.aderenciaFaixas" in _erros("produtividade", "aderenciaFaixas.1", 101)
    _vale("produtividade")


def test_faixas_do_fator_de_produtividade_crescem_e_sao_positivas() -> None:
    assert "produtividade.pfFaixas" in _erros("produtividade", "pfFaixas.0", 0)
    assert "produtividade.pfFaixas" in _erros("produtividade", "pfFaixas.1", 1.0)
    _vale("produtividade")


def test_faixas_do_spi_crescem_ate_1_5() -> None:
    assert "produtividade.spiFaixas" in _erros("produtividade", "spiFaixas.1", 0.85)
    assert "produtividade.spiFaixas" in _erros("produtividade", "spiFaixas.1", 1.6)
    _vale("produtividade")


def test_faixas_do_atraso_de_inicio_vao_de_0_a_240_minutos() -> None:
    assert "produtividade.atrasoInicioFaixasMin" in _erros(
        "produtividade", "atrasoInicioFaixasMin.0", -1
    )
    assert "produtividade.atrasoInicioFaixasMin" in _erros(
        "produtividade", "atrasoInicioFaixasMin.1", 241
    )
    assert "produtividade.atrasoInicioFaixasMin" in _erros(
        "produtividade", "atrasoInicioFaixasMin.1", 15
    )
    _vale("produtividade")


def test_janela_da_media_movel_fica_entre_1_e_12_semanas() -> None:
    assert "produtividade.semanasMedia" in _erros("produtividade", "semanasMedia", 0)
    assert "produtividade.semanasMedia" in _erros("produtividade", "semanasMedia", 13)
    assert "produtividade.semanasMedia" not in _erros("produtividade", "semanasMedia", 1)
    assert "produtividade.semanasMedia" not in _erros("produtividade", "semanasMedia", 12)


def test_tolerancia_do_consumo_da_contingencia_fica_entre_0_e_50() -> None:
    assert "financeiro.contingencia.toleranciaConsumoPP" in _erros(
        "financeiro", "contingencia.toleranciaConsumoPP", -1
    )
    assert "financeiro.contingencia.toleranciaConsumoPP" in _erros(
        "financeiro", "contingencia.toleranciaConsumoPP", 51
    )
    assert "financeiro.contingencia.toleranciaConsumoPP" not in _erros(
        "financeiro", "contingencia.toleranciaConsumoPP", 0
    )
    assert "financeiro.contingencia.toleranciaConsumoPP" not in _erros(
        "financeiro", "contingencia.toleranciaConsumoPP", 50
    )


def test_cobertura_minima_da_contingencia_fica_entre_0_e_300() -> None:
    assert "financeiro.contingencia.coberturaMinimaPct" in _erros(
        "financeiro", "contingencia.coberturaMinimaPct", -1
    )
    assert "financeiro.contingencia.coberturaMinimaPct" in _erros(
        "financeiro", "contingencia.coberturaMinimaPct", 301
    )
    assert "financeiro.contingencia.coberturaMinimaPct" not in _erros(
        "financeiro", "contingencia.coberturaMinimaPct", 0
    )
    assert "financeiro.contingencia.coberturaMinimaPct" not in _erros(
        "financeiro", "contingencia.coberturaMinimaPct", 300
    )


def test_faixas_de_desvio_fisico_da_eap_crescem_e_sao_positivas() -> None:
    assert "eap.faixasDesvioPP" in _erros("eap", "faixasDesvioPP.0", 0)
    assert "eap.faixasDesvioPP" in _erros("eap", "faixasDesvioPP.1", 2)
    _vale("eap")


def test_peso_maximo_de_pacote_da_eap_fica_entre_0_e_100() -> None:
    assert "eap.pesoMaximoPacotePct" in _erros("eap", "pesoMaximoPacotePct", 0)
    assert "eap.pesoMaximoPacotePct" in _erros("eap", "pesoMaximoPacotePct", 101)
    assert "eap.pesoMaximoPacotePct" not in _erros("eap", "pesoMaximoPacotePct", 100)


def test_peso_estimado_da_eap_nao_passa_do_peso_maximo_do_pacote() -> None:
    assert "eap.estimadoMaximoPct" in _erros("eap", "estimadoMaximoPct", 0)
    assert "eap.estimadoMaximoPct" in _erros("eap", "estimadoMaximoPct", 11)
    assert "eap.estimadoMaximoPct" not in _erros("eap", "estimadoMaximoPct", 10)


def test_etapas_de_cada_modelo_da_eap_somam_100() -> None:
    assert "eap.modelosEtapas" in _erros("eap", "modelosEtapas.0.etapas.0.peso", 39)
    # Fronteira: 40 + 31 + 29 fecha os 100 do modelo.
    valores = deepcopy(INITIAL_PARAMETERS["eap"])
    valores["modelosEtapas"][0]["etapas"][1]["peso"] = 31
    valores["modelosEtapas"][0]["etapas"][2]["peso"] = 29
    assert validation.validate_parameter_group("eap", valores) == {}


def test_prazos_de_tratamento_da_rnc_crescem_de_critica_a_menor() -> None:
    assert "qualidade.prazoTratamentoDias" in _erros("qualidade", "prazoTratamentoDias.critica", 0)
    assert "qualidade.prazoTratamentoDias" in _erros("qualidade", "prazoTratamentoDias.menor", 181)
    assert "qualidade.prazoTratamentoDias" in _erros("qualidade", "prazoTratamentoDias.maior", 14)
    assert "qualidade.prazoTratamentoDias" not in _erros(
        "qualidade", "prazoTratamentoDias.critica", 1
    )
    _vale("qualidade")


def test_espera_da_verificacao_de_eficacia_fica_entre_0_e_180() -> None:
    assert "qualidade.verificacaoEficaciaDias" in _erros("qualidade", "verificacaoEficaciaDias", -1)
    assert "qualidade.verificacaoEficaciaDias" in _erros(
        "qualidade", "verificacaoEficaciaDias", 181
    )
    assert "qualidade.verificacaoEficaciaDias" not in _erros(
        "qualidade", "verificacaoEficaciaDias", 0
    )
    assert "qualidade.verificacaoEficaciaDias" not in _erros(
        "qualidade", "verificacaoEficaciaDias", 180
    )


def test_metas_da_qualidade_ficam_entre_0_e_100() -> None:
    assert "qualidade.metas" in _erros("qualidade", "metaAprovacaoInspecaoPct", 0)
    assert "qualidade.metas" in _erros("qualidade", "metaConformidadeAuditoriaPct", 101)
    assert "qualidade.metas" not in _erros("qualidade", "metaAprovacaoInspecaoPct", 1)
    assert "qualidade.metas" not in _erros("qualidade", "metaConformidadeAuditoriaPct", 100)


def test_notificacao_ao_cliente_fica_entre_0_e_240_horas() -> None:
    assert "qualidade.notificacaoClienteHoras" in _erros("qualidade", "notificacaoClienteHoras", -1)
    assert "qualidade.notificacaoClienteHoras" in _erros(
        "qualidade", "notificacaoClienteHoras", 241
    )
    assert "qualidade.notificacaoClienteHoras" not in _erros(
        "qualidade", "notificacaoClienteHoras", 0
    )
    assert "qualidade.notificacaoClienteHoras" not in _erros(
        "qualidade", "notificacaoClienteHoras", 240
    )


def test_pesos_do_portfolio_somam_100() -> None:
    assert "portfolio.criterios" in _erros("portfolio", "criterios.0.peso", 59)
    assert "portfolio.criterios" not in _erros("portfolio", "criterios.0.peso", 60)


def test_pesos_do_portfolio_nao_podem_ser_negativos() -> None:
    # A soma continua 100, mas um peso é negativo.
    valores = deepcopy(INITIAL_PARAMETERS["portfolio"])
    valores["criterios"][0]["peso"] = -5
    valores["criterios"][1]["peso"] = 90
    erros = validation.validate_parameter_group("portfolio", valores)
    assert "não podem ser negativos" in erros["portfolio.criterios"]
