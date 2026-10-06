/* ==========================================================================
   mock-config.js | Parâmetros configuráveis do sistema e data de referência.
   Na fase com backend, vira a tabela de parâmetros com vigência (versões):
   uma alteração vale dali em diante; registros já calculados guardam os
   parâmetros usados na época (não são recalculados).
   Valores financeiros em centavos.
   ========================================================================== */
window.MOCK = window.MOCK || {};

/* Data de referência do protótipo: fixa para que status e prazos
   (atrasada, vencida, dias sem acidente) não mudem conforme o dia de abertura. */
window.MOCK.referencia = "2026-09-25";

window.MOCK.parametros = {
  versao: 1,
  vigenciaInicio: "2026-09-25",
  alteradoPor: "Leonardo Gomes",

  /* 03 Contratos: avaliação de desempenho da contratada */
  avaliacaoContratada: {
    criterios: [
      { id: "hse", nome: "HSE", peso: 25 },
      { id: "qualidade", nome: "Qualidade", peso: 20 },
      { id: "prazo", nome: "Prazo", peso: 20 },
      { id: "gestao", nome: "Gestão contratual e comercial", peso: 15 },
      { id: "recursos", nome: "Recursos e mobilização", peso: 10 },
      { id: "documentacao", nome: "Documentação e comunicação", peso: 10 }
    ],
    classes: [
      { classe: "A", minimo: 85, descricao: "Preferencial" },
      { classe: "B", minimo: 70, descricao: "Aprovada" },
      { classe: "C", minimo: 50, descricao: "Aprovada com plano de melhoria" },
      { classe: "D", minimo: 0, descricao: "Não recomendada" }
    ],
    notaExigePlano: 2            /* nota igual ou abaixo exige evidência e plano de melhoria */
  },

  /* 03 Contratos: claims */
  claims: { prazoNotificacaoPadraoDias: 30 },

  /* 07 HSE */
  hse: {
    baseTaxa: 1000000,           /* NBR 14280; 200000 = OSHA */
    prazos: { comunicacaoHoras: 24, investigacaoPreliminarHoras: 48, relatorioFinalDias: 30 },
    referenciaPiramide: "bird",  /* bird | heinrich */
    /* Metas proativas por 10 mil HHT: observações comportamentais e relato de desvios (nível 5) */
    metas: { observacoesPor10MilHht: 40, desviosPor10MilHht: 12 }
  },

  /* 05 Riscos: faixas de severidade do score P x I (1 a 25) */
  riscos: {
    escalaAtiva: "timenow",
    escalas: {
      timenow: { nome: "Timenow (4 faixas)", faixas: [
        { id: "baixo", nome: "Baixo", minimo: 1 }, { id: "moderado", nome: "Moderado", minimo: 5 },
        { id: "alto", nome: "Alto", minimo: 10 }, { id: "critico", nome: "Crítico", minimo: 15 }
      ], riscoVidaEhAlto: false },
      cipm: { nome: "CIPM ArcelorMittal (3 faixas)", faixas: [
        { id: "baixo", nome: "Baixo", minimo: 1 }, { id: "moderado", nome: "Moderado", minimo: 8 },
        { id: "alto", nome: "Alto", minimo: 16 }
      ], riscoVidaEhAlto: true }
    },
    /* Cadência máxima de revisão por faixa (dias). O gestor pode antecipar, nunca postergar. */
    cadenciaDias: { critico: 15, alto: 30, moderado: 60, baixo: 90 },
    /* Faixas de probabilidade (escala 1 a 5). VME = probabilidade média da faixa x impacto em custo. */
    probabilidades: [
      { nivel: 1, nome: "Muito baixa", faixa: "até 10%", mediaPct: 5 },
      { nivel: 2, nome: "Baixa", faixa: "10 a 30%", mediaPct: 20 },
      { nivel: 3, nome: "Média", faixa: "30 a 50%", mediaPct: 40 },
      { nivel: 4, nome: "Alta", faixa: "50 a 70%", mediaPct: 60 },
      { nivel: 5, nome: "Muito alta", faixa: "acima de 70%", mediaPct: 85 }
    ],
    impactos: ["Muito baixo", "Baixo", "Moderado", "Alto", "Muito alto"],
    /* Pauta de escalonamento: severidade acima do alvo a N dias (ou menos) do prazo do alvo */
    pautaDiasAntesDoPrazo: 30,
    /* Filtro "Vencem em N dias" do registro */
    revisaoAlertaDias: 15
  },

  /* 03 Financeiro: faixas do mapa de calor de desvio (%) e controle da contingência
     (tolerância do consumo acima do avanço físico, em pontos percentuais; cobertura mínima
     do saldo sobre a exposição das ameaças ativas, em %) */
  financeiro: { faixasDesvio: [1, 5, 10], contingencia: { toleranciaConsumoPP: 10, coberturaMinimaPct: 100 } },

  /* 04 Suprimentos
     alcadas: aprovação da adjudicação por valor (centavos; ate null = sem teto).
     pesosMarcos: critério de medição do avanço de suprimentos no MAS (soma 100).
     Pacote de serviço só tem marcos de aquisição: os pesos são renormalizados. */
  suprimentos: {
    propostasMinimas: 3, folgaAlertaDias: 7,
    alcadas: [
      { ate: 50000000, papel: "Gerente de suprimentos" },
      { ate: 500000000, papel: "Gerente do projeto" },
      { ate: null, papel: "Comitê de investimentos" }
    ],
    pesosMarcos: { requisicao: 5, rfx: 5, propostas: 5, eqTecnica: 5, eqComercial: 5, adjudicacao: 5, pedido: 10,
      documentos: 10, fabricacao: 30, inspecao: 10, embarque: 5, entrega: 5 }
  },

  /* 02 Punch list: faixas de tempo em aberto (dias) */
  punch: { agingFaixas: [7, 30] },

  /* 08 Mudanças
     alcadaGerentePctOrcamento: até este % do orçamento, e sem impacto em marco contratual, decide o
       Gerente do projeto; acima, o Comitê de Controle de Mudanças (o analista pode elevar, nunca rebaixar).
     prazoAnaliseDias: prazo padrão da análise de impacto. quorumComite: participantes mínimos da decisão do Comitê.
     prazoAcoesDias: prazo padrão das ações de implementação criadas na aprovação.
     ratificacaoDias: prazo para o Comitê ratificar mudança emergencial executada antes da decisão. */
  mudancas: { alcadaGerentePctOrcamento: 1, prazoAnaliseDias: 10, quorumComite: 3, prazoAcoesDias: 15, ratificacaoDias: 7 },

  /* 08 Lições aprendidas: alerta de projeto sem registro de lição há N dias */
  licoes: { alertaSemRegistroDias: 90 },

  /* 02 Produtividade
     jornadaDiariaHoras: jornada de referência por dia útil (44 h semanais em 5 dias = 8,8 h),
       base da utilização da jornada (capacidade produtiva ÷ jornada) e das horas improdutivas.
     metaTrabalhandoPct: meta de pessoas trabalhando na amostragem do trabalho (work sampling).
     metaUtilizacaoPct: meta de utilização da jornada na frente de serviço.
     aderenciaFaixas: aderência semanal (realizado ÷ previsto da LB) abaixo de [0] = alerta forte;
       entre [0] e [1] = atenção; a partir de [1] = no plano.
     pfFaixas: fator de produtividade (HH apropriadas ÷ HH ganhas; 1,00 = índice orçado)
       até [0] = no orçado; até [1] = atenção; acima = alerta.
     semanasMedia: janela da média móvel (aderência, fator de produtividade e tendência de término). */
  produtividade: { jornadaDiariaHoras: 8.8, metaTrabalhandoPct: 60, metaUtilizacaoPct: 75,
    aderenciaFaixas: [75, 90], pfFaixas: [1.0, 1.1], semanasMedia: 4,
    spiFaixas: [0.85, 0.95],           /* SPI de quantidades: abaixo de [0] alerta; a partir de [1] no plano */
    atrasoInicioFaixasMin: [15, 30] }, /* atraso médio de início: até [0] no plano; acima de [1] alerta */

  /* 02 EAP (estrutura analítica do projeto, avanço físico)
     faixasDesvioPP: desvio real menos previsto (p.p.) até -[0] = atenção; abaixo de -[1] = alerta.
     pesoMaximoPacotePct: peso máximo de um pacote de trabalho no projeto (pacote grande demais perde controle).
     estimadoMaximoPct: peso máximo de pacote medido por percentual estimado (critério subjetivo).
     modelosEtapas: critérios de medição por etapas (degraus); pesos de cada modelo somam 100.
     Pacote criado guarda uma cópia das etapas: mudar o modelo não altera pacotes existentes. */
  eap: {
    faixasDesvioPP: [2, 5], pesoMaximoPacotePct: 10, estimadoMaximoPct: 5,
    modelosEtapas: [
      { id: "engenharia", nome: "Engenharia (documentos)", etapas: [
        { nome: "Elaboração", peso: 40 }, { nome: "Emissão para comentários", peso: 30 }, { nome: "Emissão para construção", peso: 30 }] },
      { id: "suprimentos", nome: "Suprimentos (equipamentos e materiais)", etapas: [
        { nome: "Pedido emitido", peso: 10 }, { nome: "Documentos do fornecedor aprovados", peso: 15 }, { nome: "Fabricação", peso: 45 },
        { nome: "Inspeção e FAT", peso: 10 }, { nome: "Entrega na obra", peso: 20 }] },
      { id: "montagem", nome: "Montagem de equipamentos", etapas: [
        { nome: "Posicionamento", peso: 30 }, { nome: "Nivelamento e alinhamento", peso: 40 }, { nome: "Grauteamento", peso: 15 }, { nome: "Checklist de liberação", peso: 15 }] },
      { id: "paineis", nome: "Montagem de painéis", etapas: [
        { nome: "Posicionamento", peso: 30 }, { nome: "Fixação e aterramento", peso: 30 }, { nome: "Conexões", peso: 25 }, { nome: "Checklist de liberação", peso: 15 }] },
      { id: "comissionamento", nome: "Comissionamento", etapas: [
        { nome: "Inspeções e testes", peso: 70 }, { nome: "Certificado emitido", peso: 30 }] }
    ]
  },

  /* 06 Qualidade
     prazoTratamentoDias: prazo da RNC (abertura até a ação corretiva concluída) por severidade.
     verificacaoEficaciaDias: espera entre a conclusão das ações e a verificação de eficácia.
     metaAprovacaoInspecaoPct: meta de aprovação na primeira inspeção (ponto do ITP).
     metaConformidadeAuditoriaPct: meta de itens conformes nas auditorias realizadas.
     notificacaoClienteHoras: antecedência mínima da notificação ao cliente nos pontos H e W. */
  qualidade: { prazoTratamentoDias: { critica: 15, maior: 30, menor: 45 }, verificacaoEficaciaDias: 30,
    metaAprovacaoInspecaoPct: 95, metaConformidadeAuditoriaPct: 90, notificacaoClienteHoras: 48 },

  /* Portfólio: ponderação dos projetos na carteira (define a relevância de cada projeto na
     Curva S física, no avanço e nos índices ponderados do portfólio). Pesos dos critérios somam 100.
     fonte "orcamento": participação do orçamento vigente (EAC) do projeto no total da carteira;
     fonte "nota": participação da nota do projeto (1 a 5, em projetos[].ponderacao) na soma das notas.
     Peso do projeto = soma de (peso do critério x participação do projeto no critério).
     A Curva S financeira do portfólio soma os valores em R$ (não usa ponderação). */
  portfolio: {
    criterios: [
      { id: "valor", nome: "Valor financeiro (orçamento vigente)", peso: 60, fonte: "orcamento" },
      { id: "estrategico", nome: "Criticidade estratégica", peso: 25, fonte: "nota" },
      { id: "complexidade", nome: "Complexidade e exposição a risco", peso: 15, fonte: "nota" }
    ],
    notaMinima: 1, notaMaxima: 5
  }
};
