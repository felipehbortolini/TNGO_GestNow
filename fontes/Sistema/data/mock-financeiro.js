/* ==========================================================================
   mock-financeiro.js | 03 Gestão Financeira (dados fictícios).
   TODOS os valores em centavos (inteiros). Nada é formatado aqui.

   eac: árvore da Estrutura Analítica de Custos. Só os itens folha (nível 3)
   têm valores; pacotes e subpacotes são somados pela api.
     base          orçado na revisão vigente (linha de base)
     remanejamento soma dos remanejamentos da revisão (total da revisão = 0)
     comprometido  pedidos e contratos emitidos
     realizado     medições aprovadas e pagamentos
     projecao      projeção no término (estimativa do responsável)
   ========================================================================== */
window.MOCK = window.MOCK || {};

window.MOCK.eac = [
  { id: 1, projetoId: 1, codigo: "1", descricao: "Engenharia", nivel: 1 },
  { id: 2, projetoId: 1, codigo: "1.1", descricao: "Projeto básico", nivel: 2 },
  { id: 3, projetoId: 1, codigo: "1.1.1", descricao: "Projeto básico de processo", nivel: 3, tipoCusto: "Serviço", unidade: "vb", quantidade: 1, precoUnitario: 70000000,
    capex: true, centroCusto: "CC-4501-01", responsavelId: 6, base: 70000000, remanejamento: 0, comprometido: 69000000, realizado: 67200000, projecao: 69500000 },
  { id: 4, projetoId: 1, codigo: "1.1.2", descricao: "Estudos de interferências e topografia", nivel: 3, tipoCusto: "Serviço", unidade: "vb", quantidade: 1, precoUnitario: 50000000,
    capex: true, centroCusto: "CC-4501-01", responsavelId: 6, base: 50000000, remanejamento: 0, comprometido: 49000000, realizado: 48000000, projecao: 49000000 },
  { id: 5, projetoId: 1, codigo: "1.2", descricao: "Projeto detalhado", nivel: 2 },
  { id: 6, projetoId: 1, codigo: "1.2.1", descricao: "Engenharia civil e estrutural", nivel: 3, tipoCusto: "Serviço", unidade: "Hh", quantidade: 5500, precoUnitario: 20000,
    capex: true, centroCusto: "CC-4501-01", responsavelId: 6, base: 110000000, remanejamento: 0, comprometido: 117300000, realizado: 108000000, projecao: 121000000 },
  { id: 7, projetoId: 1, codigo: "1.2.2", descricao: "Engenharia mecânica e de tubulação", nivel: 3, tipoCusto: "Serviço", unidade: "Hh", quantidade: 6000, precoUnitario: 20000,
    capex: true, centroCusto: "CC-4501-01", responsavelId: 6, base: 120000000, remanejamento: 15000000, comprometido: 124200000, realizado: 102000000, projecao: 138000000 },
  { id: 8, projetoId: 1, codigo: "1.2.3", descricao: "Engenharia elétrica e de automação", nivel: 3, tipoCusto: "Serviço", unidade: "Hh", quantidade: 5000, precoUnitario: 20000,
    capex: true, centroCusto: "CC-4501-01", responsavelId: 6, base: 100000000, remanejamento: 0, comprometido: 103500000, realizado: 79800000, projecao: 113000000 },

  { id: 9, projetoId: 1, codigo: "2", descricao: "Suprimentos", nivel: 1 },
  { id: 10, projetoId: 1, codigo: "2.1", descricao: "Equipamentos mecânicos", nivel: 2 },
  { id: 11, projetoId: 1, codigo: "2.1.1", descricao: "Moinho de bolas", nivel: 3, tipoCusto: "Equipamento", unidade: "un", quantidade: 1, precoUnitario: 900000000,
    capex: true, centroCusto: "CC-4501-02", responsavelId: 7, base: 900000000, remanejamento: 0, comprometido: 900000000, realizado: 720000000, projecao: 900000000 },
  { id: 12, projetoId: 1, codigo: "2.1.2", descricao: "Britador cônico", nivel: 3, tipoCusto: "Equipamento", unidade: "un", quantidade: 1, precoUnitario: 300000000,
    capex: true, centroCusto: "CC-4501-02", responsavelId: 7, base: 300000000, remanejamento: 0, comprometido: 290000000, realizado: 145000000, projecao: 290000000 },
  { id: 13, projetoId: 1, codigo: "2.1.3", descricao: "Transportadores de correia", nivel: 3, tipoCusto: "Equipamento", unidade: "un", quantidade: 5, precoUnitario: 50000000,
    capex: true, centroCusto: "CC-4501-02", responsavelId: 7, base: 250000000, remanejamento: -15000000, comprometido: 225000000, realizado: 225000000, projecao: 225000000 },
  { id: 14, projetoId: 1, codigo: "2.1.4", descricao: "Bombas de polpa", nivel: 3, tipoCusto: "Equipamento", unidade: "un", quantidade: 8, precoUnitario: 20000000,
    capex: true, centroCusto: "CC-4501-02", responsavelId: 7, base: 160000000, remanejamento: 0, comprometido: 150000000, realizado: 45000000, projecao: 150000000 },
  { id: 15, projetoId: 1, codigo: "2.1.5", descricao: "Células de flotação", nivel: 3, tipoCusto: "Equipamento", unidade: "un", quantidade: 4, precoUnitario: 47500000,
    capex: true, centroCusto: "CC-4501-02", responsavelId: 7, base: 190000000, remanejamento: 0, comprometido: 180000000, realizado: 72000000, projecao: 180000000 },
  { id: 16, projetoId: 1, codigo: "2.1.6", descricao: "Válvulas de processo", nivel: 3, tipoCusto: "Material", unidade: "un", quantidade: 100, precoUnitario: 500000,
    capex: true, centroCusto: "CC-4501-02", responsavelId: 7, base: 50000000, remanejamento: 0, comprometido: 45000000, realizado: 33000000, projecao: 45000000 },
  { id: 17, projetoId: 1, codigo: "2.2", descricao: "Materiais elétricos e automação", nivel: 2 },
  { id: 18, projetoId: 1, codigo: "2.2.1", descricao: "Transformadores de força", nivel: 3, tipoCusto: "Equipamento", unidade: "un", quantidade: 2, precoUnitario: 70000000,
    capex: true, centroCusto: "CC-4501-03", responsavelId: 7, base: 140000000, remanejamento: 0, comprometido: 140000000, realizado: 70000000, projecao: 140000000 },
  { id: 19, projetoId: 1, codigo: "2.2.2", descricao: "Painéis e CCMs", nivel: 3, tipoCusto: "Equipamento", unidade: "un", quantidade: 11, precoUnitario: 10000000,
    capex: true, centroCusto: "CC-4501-03", responsavelId: 7, base: 110000000, remanejamento: 0, comprometido: 112000000, realizado: 112000000, projecao: 112000000 },
  { id: 20, projetoId: 1, codigo: "2.2.3", descricao: "Cabos e bandejamento", nivel: 3, tipoCusto: "Material", unidade: "m", quantidade: 40000, precoUnitario: 2500,
    capex: true, centroCusto: "CC-4501-03", responsavelId: 7, base: 100000000, remanejamento: 0, comprometido: 98000000, realizado: 40000000, projecao: 146000000 },
  { id: 21, projetoId: 1, codigo: "2.2.4", descricao: "Instrumentação de campo", nivel: 3, tipoCusto: "Material", unidade: "un", quantidade: 150, precoUnitario: 200000,
    capex: true, centroCusto: "CC-4501-03", responsavelId: 7, base: 30000000, remanejamento: 0, comprometido: 30000000, realizado: 8000000, projecao: 30000000 },
  { id: 22, projetoId: 1, codigo: "2.2.5", descricao: "Sistema digital de controle (SDCD)", nivel: 3, tipoCusto: "Equipamento", unidade: "vb", quantidade: 1, precoUnitario: 60000000,
    capex: true, centroCusto: "CC-4501-03", responsavelId: 7, base: 60000000, remanejamento: -20000000, comprometido: 0, realizado: 0, projecao: 40000000 },

  { id: 23, projetoId: 1, codigo: "3", descricao: "Construção e montagem", nivel: 1 },
  { id: 24, projetoId: 1, codigo: "3.1", descricao: "Obras civis", nivel: 2 },
  { id: 25, projetoId: 1, codigo: "3.1.1", descricao: "Terraplenagem e drenagem", nivel: 3, tipoCusto: "Serviço", unidade: "m³", quantidade: 120000, precoUnitario: 1500,
    capex: true, centroCusto: "CC-4501-04", responsavelId: 11, base: 180000000, remanejamento: 0, comprometido: 185000000, realizado: 185000000, projecao: 190000000 },
  { id: 26, projetoId: 1, codigo: "3.1.2", descricao: "Fundações", nivel: 3, tipoCusto: "Serviço", unidade: "m³", quantidade: 3200, precoUnitario: 100000,
    capex: true, centroCusto: "CC-4501-04", responsavelId: 11, base: 320000000, remanejamento: 20000000, comprometido: 355000000, realizado: 300000000, projecao: 370000000 },
  { id: 27, projetoId: 1, codigo: "3.1.3", descricao: "Estruturas de concreto", nivel: 3, tipoCusto: "Serviço", unidade: "m³", quantidade: 6000, precoUnitario: 50000,
    capex: true, centroCusto: "CC-4501-04", responsavelId: 11, base: 300000000, remanejamento: 0, comprometido: 290000000, realizado: 200000000, projecao: 290000000 },
  { id: 28, projetoId: 1, codigo: "3.1.4", descricao: "Edificações e acabamentos", nivel: 3, tipoCusto: "Serviço", unidade: "m²", quantidade: 3500, precoUnitario: 40000,
    capex: true, centroCusto: "CC-4501-04", responsavelId: 11, base: 140000000, remanejamento: 0, comprometido: 130000000, realizado: 60000000, projecao: 145000000 },
  { id: 29, projetoId: 1, codigo: "3.2", descricao: "Montagem eletromecânica", nivel: 2 },
  { id: 30, projetoId: 1, codigo: "3.2.1", descricao: "Montagem mecânica de equipamentos", nivel: 3, tipoCusto: "Serviço", unidade: "t", quantidade: 1500, precoUnitario: 200000,
    capex: true, centroCusto: "CC-4501-05", responsavelId: 5, base: 300000000, remanejamento: 0, comprometido: 200000000, realizado: 110000000, projecao: 290000000 },
  { id: 31, projetoId: 1, codigo: "3.2.2", descricao: "Tubulação", nivel: 3, tipoCusto: "Serviço", unidade: "m", quantidade: 11000, precoUnitario: 20000,
    capex: true, centroCusto: "CC-4501-05", responsavelId: 5, base: 220000000, remanejamento: 0, comprometido: 150000000, realizado: 60000000, projecao: 235000000 },
  { id: 32, projetoId: 1, codigo: "3.2.3", descricao: "Montagem elétrica e de instrumentação", nivel: 3, tipoCusto: "Serviço", unidade: "vb", quantidade: 1, precoUnitario: 190000000,
    capex: true, centroCusto: "CC-4501-05", responsavelId: 5, base: 190000000, remanejamento: 0, comprometido: 130000000, realizado: 50000000, projecao: 192000000 },
  { id: 33, projetoId: 1, codigo: "3.2.4", descricao: "Estruturas metálicas e pipe racks", nivel: 3, tipoCusto: "Serviço", unidade: "t", quantidade: 350, precoUnitario: 200000,
    capex: true, centroCusto: "CC-4501-05", responsavelId: 5, base: 70000000, remanejamento: 0, comprometido: 40000000, realizado: 30000000, projecao: 65000000 }
];

/* Revisões do orçamento (Rev 0 = linha de base aprovada). O total só muda por revisão. */
window.MOCK.eacRevisoes = [
  { id: 1, projetoId: 1, revisao: 0, data: "2026-01-05", totalCentavos: 4380000000, justificativa: "Linha de base aprovada no gate de investimento.", smRef: null, aprovadoPorId: 2 },
  { id: 2, projetoId: 1, revisao: 1, data: "2026-05-18", totalCentavos: 4420000000, justificativa: "Inclusão do sistema de tratamento de efluentes.", smRef: "SM-TN-2026-0001", aprovadoPorId: 2 },
  { id: 3, projetoId: 1, revisao: 2, data: "2026-07-10", totalCentavos: 4460000000, justificativa: "Reforço das fundações por interferência no subsolo.", smRef: "SM-TN-2026-0002", aprovadoPorId: 2 }
];

/* Remanejamentos da revisão vigente (soma zero) */
window.MOCK.eacRemanejamentos = [
  { id: 1, projetoId: 1, revisao: 2, data: "2026-08-12", origem: "2.1.3", destino: "1.2.2", valorCentavos: 15000000, porId: 2, smRef: "SM-TN-2026-0009",
    justificativa: "Economia na compra dos transportadores cobre a engenharia mecânica adicional." },
  { id: 2, projetoId: 1, revisao: 2, data: "2026-09-02", origem: "2.2.5", destino: "3.1.2", valorCentavos: 20000000, porId: 2, smRef: "SM-TN-2026-0010",
    justificativa: "Estimativa do SDCD reduzida após as propostas; saldo cobre fundações adicionais." }
];

/* Reservas do projeto (fora do orçado da EAC). contingenciaCentavos: riscos identificados (05), integra a
   linha de base de custo; gerencialCentavos: imprevistos, fora da linha de base (libera só o Comitê).
   O consumo vem das SMs aprovadas com a fonte da reserva (08). */
window.MOCK.reservas = [
  { id: 1, projetoId: 1, contingenciaCentavos: 200000000, gerencialCentavos: 90000000, constituidaEm: "2026-01-05",
    base: "Análise quantitativa dos riscos no gate de investimento (VME das ameaças, P80)" }
];

/* Curva S financeira (acumulado por mês, centavos). planejado = linha de base de custo;
   comprometido e realizado até o corte; projecao a partir do corte (fecha na projeção no término). */
window.MOCK.curvaFinanceira = [
  { id: 1, projetoId: 1, corte: "2026-09",
    meses: ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10", "2026-11", "2026-12", "2027-01", "2027-02", "2027-03", "2027-04"],
    planejado: [93660000, 240840000, 454920000, 749280000, 1092700000, 1471800000, 1877660000, 2408400000, 2930220000, 3380680000, 3755320000, 4040760000, 4241460000, 4388640000, 4460000000, 4460000000],
    comprometido: [448000000, 1368000000, 1368000000, 2020000000, 2500000000, 3300000000, 3700000000, 3960000000, 4113000000, null, null, null, null, null, null, null],
    realizado: [90000000, 245000000, 440000000, 700000000, 1010000000, 1360000000, 1760000000, 2280000000, 2870000000, null, null, null, null, null, null, null],
    projecao: [null, null, null, null, null, null, null, null, 2870000000, 3277400000, 3663100000, 3962100000, 4204800000, 4369500000, 4482200000, 4525500000] }
];

/* ---------------- Contratos e administração contratual ---------------- */
window.MOCK.contratos = [
  { id: 1, projetoId: 1, numero: "CT-2026-011", empresaId: 5, objeto: "Engenharia detalhada", modalidade: "Preço global", eacCodigo: "1.2",
    pacoteCompra: "PC-01", valorOriginalCentavos: 330000000, inicio: "2026-01-12", terminoOriginal: "2026-10-30", terminoVigente: "2026-11-20",
    gestorId: 2, fiscalId: 12, retencaoPct: 5, prazoNotificacaoClaimDias: 30, situacao: "Em execução" },
  { id: 2, projetoId: 1, numero: "CT-2026-012", empresaId: 6, objeto: "Obras civis e fundações", modalidade: "Preço unitário", eacCodigo: "3.1",
    pacoteCompra: "PC-02", valorOriginalCentavos: 920000000, inicio: "2026-02-02", terminoOriginal: "2026-11-30", terminoVigente: "2026-12-21",
    gestorId: 2, fiscalId: 12, retencaoPct: 5, prazoNotificacaoClaimDias: 30, situacao: "Em execução" },
  { id: 3, projetoId: 1, numero: "CT-2026-014", empresaId: 1, objeto: "Montagem eletromecânica", modalidade: "Preço unitário", eacCodigo: "3.2",
    pacoteCompra: "PC-13", valorOriginalCentavos: 480000000, inicio: "2026-05-04", terminoOriginal: "2027-01-29", terminoVigente: "2027-01-29",
    gestorId: 2, fiscalId: 12, retencaoPct: 5, prazoNotificacaoClaimDias: 30, situacao: "Em execução" }
];

window.MOCK.aditivos = [
  { id: 1, contratoId: 1, numero: "AD-01", data: "2026-05-18", valorCentavos: 15000000, dias: 21,
    motivo: "Engenharia do sistema de tratamento de efluentes.", smRef: "SM-TN-2026-0001", claimRef: "CLM-TN-2026-0005" },
  { id: 2, contratoId: 2, numero: "AD-01", data: "2026-07-10", valorCentavos: 40000000, dias: 21,
    motivo: "Reforço das fundações por interferência no subsolo.", smRef: "SM-TN-2026-0002", claimRef: "CLM-TN-2026-0004" },
  { id: 3, contratoId: 3, numero: "AD-01", data: "2026-08-20", valorCentavos: 40000000, dias: 0,
    motivo: "Montagem das estruturas do pipe rack PR-03.", smRef: "SM-TN-2026-0004", claimRef: null }
];

/* Medições. Situação: Em análise, Aprovada, Faturada, Paga, Devolvida. valor bruto em centavos. */
window.MOCK.medicoes = [
  { id: 1, contratoId: 1, numero: "BM-01", periodo: "2026-01", brutoCentavos: 34500000, situacao: "Paga", marcoId: 1 },
  { id: 2, contratoId: 1, numero: "BM-02", periodo: "2026-04", brutoCentavos: 69000000, situacao: "Paga", marcoId: 2 },
  { id: 3, contratoId: 1, numero: "BM-03", periodo: "2026-06", brutoCentavos: 86250000, situacao: "Paga", marcoId: 3 },
  { id: 4, contratoId: 1, numero: "BM-04", periodo: "2026-08", brutoCentavos: 100050000, situacao: "Faturada", marcoId: 4 },
  { id: 5, contratoId: 2, numero: "BM-01", periodo: "2026-02", brutoCentavos: 22350000, situacao: "Paga" },
  { id: 6, contratoId: 2, numero: "BM-02", periodo: "2026-03", brutoCentavos: 44700000, situacao: "Paga" },
  { id: 7, contratoId: 2, numero: "BM-03", periodo: "2026-04", brutoCentavos: 67050000, situacao: "Paga" },
  { id: 8, contratoId: 2, numero: "BM-04", periodo: "2026-05", brutoCentavos: 89400000, situacao: "Paga" },
  { id: 9, contratoId: 2, numero: "BM-05", periodo: "2026-06", brutoCentavos: 104300000, situacao: "Paga" },
  { id: 10, contratoId: 2, numero: "BM-06", periodo: "2026-07", brutoCentavos: 119200000, situacao: "Paga" },
  { id: 11, contratoId: 2, numero: "BM-07", periodo: "2026-08", brutoCentavos: 141550000, situacao: "Faturada" },
  { id: 12, contratoId: 2, numero: "BM-08", periodo: "2026-09", brutoCentavos: 156450000, situacao: "Aprovada" },
  { id: 13, contratoId: 3, numero: "BM-01", periodo: "2026-05", brutoCentavos: 18000000, situacao: "Paga" },
  { id: 14, contratoId: 3, numero: "BM-02", periodo: "2026-06", brutoCentavos: 42000000, situacao: "Paga" },
  { id: 15, contratoId: 3, numero: "BM-03", periodo: "2026-07", brutoCentavos: 61000000, situacao: "Paga" },
  { id: 16, contratoId: 3, numero: "BM-04", periodo: "2026-08", brutoCentavos: 64000000, situacao: "Faturada" },
  { id: 17, contratoId: 3, numero: "BM-05", periodo: "2026-09", brutoCentavos: 65000000, situacao: "Aprovada" }
];

/* Marcos de pagamento (soma dos % do contrato = 100).
   Situação: Previsto, Evidência enviada, Aprovado, Faturado, Pago. */
window.MOCK.marcosPagamento = [
  { id: 1, contratoId: 1, numero: "M1", descricao: "Mobilização e plano de projeto", criterio: "Plano de projeto aprovado", pct: 10, valorCentavos: 34500000,
    prevista: "2026-01-30", conclusao: "2026-01-28", situacao: "Pago" },
  { id: 2, contratoId: 1, numero: "M2", descricao: "Projeto básico consolidado", criterio: "Documentos aprovados pelo cliente", pct: 20, valorCentavos: 69000000,
    prevista: "2026-04-10", conclusao: "2026-04-15", situacao: "Pago" },
  { id: 3, contratoId: 1, numero: "M3", descricao: "Civil e estrutural emitida para construção", criterio: "Lista de documentos em revisão 0", pct: 25, valorCentavos: 86250000,
    prevista: "2026-06-15", conclusao: "2026-06-18", situacao: "Pago" },
  { id: 4, contratoId: 1, numero: "M4", descricao: "Mecânica e tubulação emitida para construção", criterio: "Lista de documentos em revisão 0", pct: 29, valorCentavos: 100050000,
    prevista: "2026-08-15", conclusao: "2026-08-20", situacao: "Faturado" },
  { id: 5, contratoId: 1, numero: "M5", descricao: "Elétrica e automação emitida para construção", criterio: "Lista de documentos em revisão 0", pct: 12, valorCentavos: 41400000,
    prevista: "2026-09-20", conclusao: null, situacao: "Evidência enviada" },
  { id: 6, contratoId: 1, numero: "M6", descricao: "Data book e documentação como construído", criterio: "Data book aceito pelo cliente", pct: 4, valorCentavos: 13800000,
    prevista: "2026-11-20", conclusao: null, situacao: "Previsto" }
];

/* Claims. Direção: Da contratada | Do contratante (back-charge).
   Situação: Notificado, Em análise, Em negociação, Acordado, Rejeitado, Em disputa, Encerrado. */
window.MOCK.claims = [
  { id: 1, contratoId: 3, codigo: "CLM-TN-2026-0001", direcao: "Da contratada", tipo: "Custo", causa: "Liberação de área",
    descricao: "Improdutividade da equipe por liberação tardia da frente do pipe rack PR-02.", clausula: "12.3",
    evento: "2026-07-08", notificacao: "2026-07-22", pleiteadoCentavos: 18500000, diasPleiteados: 0,
    reconhecidoCentavos: null, diasReconhecidos: null, situacao: "Em negociação", encerramento: null, riscoRef: null, smRef: null },
  { id: 2, contratoId: 3, codigo: "CLM-TN-2026-0002", direcao: "Do contratante", tipo: "Custo", causa: "Outros",
    descricao: "Back-charge do retrabalho de solda da linha 310-P-014 executado por terceiro.", clausula: "18.1",
    evento: "2026-08-19", notificacao: "2026-08-26", pleiteadoCentavos: 3400000, diasPleiteados: 0,
    reconhecidoCentavos: 3400000, diasReconhecidos: 0, situacao: "Acordado", encerramento: "2026-09-09", riscoRef: null, smRef: null },
  { id: 3, contratoId: 3, codigo: "CLM-TN-2026-0003", direcao: "Da contratada", tipo: "Prazo e custo", causa: "Informação de projeto tardia",
    descricao: "Revisão tardia dos desenhos de montagem do moinho paralisou a frente por 6 semanas.", clausula: "12.5",
    evento: "2026-06-10", notificacao: "2026-08-05", pleiteadoCentavos: 42000000, diasPleiteados: 45,
    reconhecidoCentavos: null, diasReconhecidos: null, situacao: "Em análise", encerramento: null, riscoRef: null, smRef: null },
  { id: 4, contratoId: 2, codigo: "CLM-TN-2026-0004", direcao: "Da contratada", tipo: "Prazo e custo", causa: "Interferência",
    descricao: "Interferência não mapeada no subsolo da fundação F-12.", clausula: "9.2",
    evento: "2026-04-14", notificacao: "2026-04-20", pleiteadoCentavos: 52000000, diasPleiteados: 30,
    reconhecidoCentavos: 40000000, diasReconhecidos: 21, situacao: "Encerrado", encerramento: "2026-07-10", riscoRef: "RSK-TN-2026-0003", smRef: "SM-TN-2026-0002" },
  { id: 5, contratoId: 1, codigo: "CLM-TN-2026-0005", direcao: "Da contratada", tipo: "Prazo e custo", causa: "Mudança de escopo",
    descricao: "Engenharia adicional do sistema de tratamento de efluentes.", clausula: "7.4",
    evento: "2026-03-20", notificacao: "2026-03-27", pleiteadoCentavos: 18000000, diasPleiteados: 21,
    reconhecidoCentavos: 15000000, diasReconhecidos: 21, situacao: "Encerrado", encerramento: "2026-05-18", riscoRef: null, smRef: "SM-TN-2026-0001" }
];

/* Extensões de prazo. Situação: Solicitada, Em análise, Concedida, Concedida parcialmente, Negada. */
window.MOCK.extensoesPrazo = [
  { id: 1, contratoId: 2, codigo: "EOT-TN-2026-0001", claimRef: "CLM-TN-2026-0004", evento: "Interferência não mapeada no subsolo da fundação F-12.",
    diasSolicitados: 30, diasConcedidos: 21, classificacao: "Justificável e compensável", metodo: "Análise de impacto no tempo",
    marcoAfetado: "Término das fundações", data: "2026-04-20", decisao: "2026-07-10", situacao: "Concedida parcialmente" },
  { id: 2, contratoId: 3, codigo: "EOT-TN-2026-0002", claimRef: "CLM-TN-2026-0003", evento: "Revisão tardia dos desenhos de montagem do moinho.",
    diasSolicitados: 45, diasConcedidos: null, classificacao: null, metodo: "Análise por janelas",
    marcoAfetado: "Montagem mecânica do moinho", data: "2026-08-05", decisao: null, situacao: "Em análise" },
  { id: 3, contratoId: 1, codigo: "EOT-TN-2026-0003", claimRef: "CLM-TN-2026-0005", evento: "Engenharia adicional do tratamento de efluentes.",
    diasSolicitados: 21, diasConcedidos: 21, classificacao: "Justificável e compensável", metodo: "Análise de impacto no tempo",
    marcoAfetado: "Emissão da engenharia elétrica", data: "2026-03-27", decisao: "2026-05-18", situacao: "Concedida" }
];

/* Avaliações de desempenho. Notas 1 a 5 por critério; guardam a versão dos parâmetros
   e os pesos usados (não são recalculadas se os pesos mudarem). */
window.MOCK.avaliacoes = [
  { id: 1, contratoId: 3, periodo: "2026-07", tipo: "Mensal", avaliadorId: 12, parametrosVersao: 1,
    pesos: { hse: 25, qualidade: 20, prazo: 20, gestao: 15, recursos: 10, documentacao: 10 },
    notas: { hse: 4, qualidade: 4, prazo: 3, gestao: 3, recursos: 4, documentacao: 3 }, comentario: "Mobilização dentro do plano." },
  { id: 2, contratoId: 3, periodo: "2026-08", tipo: "Mensal", avaliadorId: 12, parametrosVersao: 1,
    pesos: { hse: 25, qualidade: 20, prazo: 20, gestao: 15, recursos: 10, documentacao: 10 },
    notas: { hse: 4, qualidade: 3, prazo: 3, gestao: 3, recursos: 4, documentacao: 3 }, comentario: "Soldas reprovadas na linha 310-P-014 (RNC-TN-2026-0004)." },
  { id: 3, contratoId: 3, periodo: "2026-09", tipo: "Mensal", avaliadorId: 12, parametrosVersao: 1,
    pesos: { hse: 25, qualidade: 20, prazo: 20, gestao: 15, recursos: 10, documentacao: 10 },
    notas: { hse: 4, qualidade: 3, prazo: 2, gestao: 3, recursos: 4, documentacao: 3 }, comentario: "Atraso de 8% na montagem mecânica; plano de melhoria exigido." },
  { id: 4, contratoId: 2, periodo: "2026-08", tipo: "Mensal", avaliadorId: 12, parametrosVersao: 1,
    pesos: { hse: 25, qualidade: 20, prazo: 20, gestao: 15, recursos: 10, documentacao: 10 },
    notas: { hse: 5, qualidade: 4, prazo: 4, gestao: 4, recursos: 4, documentacao: 4 }, comentario: "" },
  { id: 5, contratoId: 2, periodo: "2026-09", tipo: "Mensal", avaliadorId: 12, parametrosVersao: 1,
    pesos: { hse: 25, qualidade: 20, prazo: 20, gestao: 15, recursos: 10, documentacao: 10 },
    notas: { hse: 4, qualidade: 4, prazo: 4, gestao: 4, recursos: 4, documentacao: 4 }, comentario: "RNC de concretagem em verificação de eficácia." },
  { id: 6, contratoId: 1, periodo: "2026-09", tipo: "Mensal", avaliadorId: 12, parametrosVersao: 1,
    pesos: { hse: 25, qualidade: 20, prazo: 20, gestao: 15, recursos: 10, documentacao: 10 },
    notas: { hse: 5, qualidade: 4, prazo: 3, gestao: 4, recursos: 4, documentacao: 5 }, comentario: "Marco M5 com evidência enviada após a data prevista." }
];

/* Análise do período (03): comentário executivo e analítico por tipo (Semanal ou Mensal) e período,
   inserido e editado em modal no módulo. desvios: comentário por desvio negativo detectado (chave
   calculada pela api com os dados do período). Semana 39 e setembro sem análise (em andamento). */
window.MOCK.analisesPeriodo = (window.MOCK.analisesPeriodo || []).concat([
  { id: 11, projetoId: 1, modulo: "financeiro", tipo: "Semanal", periodo: "2026-S38", criadoPorId: 4, criadoEm: "2026-09-21T10:30", atualizadoPorId: 4, atualizadoEm: "2026-09-21T10:30",
    analise: "Na semana, a posição de custo segue o fechamento de agosto (último mês fechado): CPI 0,98 e SPI de custo 0,93. O realizado acumulado de R$ 22,8 milhões supera o valor agregado em R$ 366 mil. Nas últimas três medições o CPI oscilou entre 0,97 e 0,99, sem tendência de piora. A projeção no término de R$ 45,26 milhões excede o orçamento vigente em 1,5% (R$ 655 mil), dentro da contingência disponível. Tendência: estabilidade do CPI até o fechamento de setembro; o principal risco é a mobilização do segundo turno na montagem.",
    desvios: [
      { chave: "cpi", indicador: "CPI (desempenho de custo)", comentario: "CPI 0,98 por horas extras de engenharia e retrabalho de solda. Sem novos gatilhos na semana; acompanhamento até o fechamento de setembro." },
      { chave: "spi_custo", indicador: "SPI de custo (valor agregado)", comentario: "SPI de custo 0,93 reflete o atraso físico da montagem, não gasto adicional. Deve convergir com o plano de recuperação físico." },
      { chave: "vac", indicador: "Projeção no término", comentario: "Sobrecusto projetado de R$ 655 mil (1,5%) coberto pela contingência. Sem necessidade de revisão de orçamento neste momento." },
      { chave: "pacotes", indicador: "Pacotes com sobrecusto projetado", comentario: "Engenharia (+5,5%) por revisão de fundações; construção e montagem (+2,1%) por segundo turno. Suprimentos com variação desprezível (+0,1%)." }
    ] },
  { id: 12, projetoId: 1, modulo: "financeiro", tipo: "Mensal", periodo: "2026-08", criadoPorId: 4, criadoEm: "2026-09-05T14:00", atualizadoPorId: 2, atualizadoEm: "2026-09-06T09:40",
    analise: "Agosto fecha com CPI 0,98 e SPI de custo 0,93. O realizado acumulado atinge R$ 22,8 milhões para R$ 22,43 milhões de valor agregado. Nos últimos seis meses o CPI permaneceu entre 0,97 e 1,01, com piora gradual desde junho por horas extras de engenharia e custos do reforço das fundações (SM-TN-2026-0002). A projeção no término de R$ 45,26 milhões supera o orçamento vigente em 1,5%. Tendência: manutenção do CPI próximo de 0,98 até dezembro; a contingência cobre o sobrecusto projetado, mas a margem se reduz caso o segundo turno se estenda além de outubro.",
    desvios: [
      { chave: "cpi", indicador: "CPI (desempenho de custo)", comentario: "CPI 0,98: horas extras de engenharia e custo do reforço das fundações. Ação: renegociação das horas extras com a projetista." },
      { chave: "spi_custo", indicador: "SPI de custo (valor agregado)", comentario: "Atraso físico da montagem reduz o valor agregado; o efeito é de prazo, sem desembolso adicional no mês." },
      { chave: "vac", indicador: "Projeção no término", comentario: "VAC de R$ 655 mil negativo (1,5%). Coberto pela contingência; revisão da EAC programada para o fechamento de setembro." },
      { chave: "pacotes", indicador: "Pacotes com sobrecusto projetado", comentario: "Engenharia (+R$ 255 mil) e construção e montagem (+R$ 370 mil) concentram o desvio. Suprimentos (+R$ 30 mil) sob controle." }
    ] }
]);
