/* ==========================================================================
   mock-suprimentos.js | 04 Suprimentos (dados fictícios). Valores em centavos.
   pacotes: plano de compras (estratégia por pacote). Datas por marco de
     aquisição em três camadas: plano (linha de base, LB), previsao
     (reprogramação dos marcos pendentes) e real (realizado).
   pedidos: diligenciamento e recebimento. Cada marco de fabricação tem LB
     (cronograma contratual do pedido), previsão atual e data realizada.
     Folga = ROS - previsão de entrega (calculada pela api, nunca gravada).
   processos: RFx com convidados, propostas, equalização, negociação,
     recomendação e aprovação por alçada.
   fornecedores: qualificação e documentos (a nota de desempenho vem das
     avaliações de contrato do módulo 03).
   O MAS (Mapa de Suprimentos) não tem coleção própria: a api monta o mapa a
   partir de pacotes, processos e pedidos (uma fonte de verdade por dado).
   ========================================================================== */
window.MOCK = window.MOCK || {};

/* Etapas: Planejado, Requisição, RFx emitida, Propostas recebidas, Equalização técnica,
   Equalização comercial, Negociação, Recomendação de adjudicação, Aprovada, Pedido/contrato emitido.
   Chaves de marco: requisicao, rfx, propostas, eqTecnica, eqComercial, adjudicacao, pedido (+ entrega na LB
   dos pacotes que ainda não têm pedido). */
window.MOCK.pacotes = [
  { id: 1, projetoId: 1, codigo: "PC-01", escopo: "Engenharia detalhada", tipo: "Serviço", disciplina: "Engenharia", modalidade: "Preço global", lli: false, eacCodigo: "1.2",
    estimativaCentavos: 340000000, compradorId: 7, ros: "2026-01-12",
    plano: { requisicao: "2025-11-10", rfx: "2025-11-20", propostas: "2025-12-11", eqTecnica: "2025-12-20", eqComercial: "2025-12-29", adjudicacao: "2026-01-05", pedido: "2026-01-08" },
    real: { requisicao: "2025-11-10", rfx: "2025-11-24", propostas: "2025-12-16", eqTecnica: "2025-12-25", eqComercial: "2026-01-03", adjudicacao: "2026-01-08", pedido: "2026-01-10" },
    previsao: {}, etapa: "Pedido/contrato emitido", fornecedorId: 5, adjudicadoCentavos: 330000000, primeiraPropostaCentavos: 345000000,
    propostasValidas: 4, fornecedorUnico: false, emergencial: false, contratoRef: "CT-2026-011" },
  { id: 2, projetoId: 1, codigo: "PC-02", escopo: "Obras civis e fundações", tipo: "Serviço", disciplina: "Civil", modalidade: "Preço unitário", lli: false, eacCodigo: "3.1",
    estimativaCentavos: 950000000, compradorId: 7, ros: "2026-02-02",
    plano: { requisicao: "2025-11-17", rfx: "2025-12-01", propostas: "2025-12-22", eqTecnica: "2026-01-02", eqComercial: "2026-01-13", adjudicacao: "2026-01-20", pedido: "2026-01-23" },
    real: { requisicao: "2025-11-17", rfx: "2025-12-03", propostas: "2025-12-27", eqTecnica: "2026-01-09", eqComercial: "2026-01-23", adjudicacao: "2026-01-28", pedido: "2026-01-30" },
    previsao: {}, etapa: "Pedido/contrato emitido", fornecedorId: 6, adjudicadoCentavos: 920000000, primeiraPropostaCentavos: 968000000,
    propostasValidas: 5, fornecedorUnico: false, emergencial: false, contratoRef: "CT-2026-012" },
  { id: 3, projetoId: 1, codigo: "PC-03", escopo: "Moinho de bolas com supervisão de montagem", tipo: "Equipamento", disciplina: "Mecânica", modalidade: "Preço global", lli: true, eacCodigo: "2.1.1",
    gateLli: { data: "2025-11-26", referencia: "Aprovação específica de LLI pelo comitê de investimentos, com análise de risco do pacote" },
    estimativaCentavos: 960000000, compradorId: 7, ros: "2026-09-15",
    plano: { requisicao: "2025-12-01", rfx: "2025-12-15", propostas: "2026-01-05", eqTecnica: "2026-01-22", eqComercial: "2026-02-08", adjudicacao: "2026-02-15", pedido: "2026-02-18" },
    real: { requisicao: "2025-12-01", rfx: "2025-12-18", propostas: "2026-01-10", eqTecnica: "2026-01-28", eqComercial: "2026-02-15", adjudicacao: "2026-02-20", pedido: "2026-02-25" },
    previsao: {}, etapa: "Pedido/contrato emitido", fornecedorId: 7, adjudicadoCentavos: 900000000, primeiraPropostaCentavos: 948000000,
    propostasValidas: 3, fornecedorUnico: false, emergencial: false, pedidoRef: "PED-2026-0001" },
  { id: 4, projetoId: 1, codigo: "PC-04", escopo: "Britador cônico", tipo: "Equipamento", disciplina: "Mecânica", modalidade: "Preço global", lli: true, eacCodigo: "2.1.2",
    estimativaCentavos: 310000000, compradorId: 7, ros: "2026-10-01",
    plano: { requisicao: "2026-01-05", rfx: "2026-01-19", propostas: "2026-02-09", eqTecnica: "2026-02-20", eqComercial: "2026-03-03", adjudicacao: "2026-03-10", pedido: "2026-03-13" },
    real: { requisicao: "2026-01-05", rfx: "2026-01-20", propostas: "2026-02-14", eqTecnica: "2026-02-27", eqComercial: "2026-03-13", adjudicacao: "2026-03-18", pedido: "2026-03-20" },
    previsao: {}, etapa: "Pedido/contrato emitido", fornecedorId: 7, adjudicadoCentavos: 290000000, primeiraPropostaCentavos: 301000000,
    propostasValidas: 3, fornecedorUnico: false, emergencial: false, pedidoRef: "PED-2026-0002" },
  { id: 5, projetoId: 1, codigo: "PC-05", escopo: "Transportadores de correia", tipo: "Equipamento", disciplina: "Mecânica", modalidade: "Preço global", lli: false, eacCodigo: "2.1.3",
    estimativaCentavos: 240000000, compradorId: 7, ros: "2026-09-01",
    plano: { requisicao: "2026-01-12", rfx: "2026-01-26", propostas: "2026-02-16", eqTecnica: "2026-02-28", eqComercial: "2026-03-13", adjudicacao: "2026-03-20", pedido: "2026-03-23" },
    real: { requisicao: "2026-01-12", rfx: "2026-01-26", propostas: "2026-02-16", eqTecnica: "2026-02-27", eqComercial: "2026-03-11", adjudicacao: "2026-03-16", pedido: "2026-03-18" },
    previsao: {}, etapa: "Pedido/contrato emitido", fornecedorId: 4, adjudicadoCentavos: 225000000, primeiraPropostaCentavos: 236000000,
    propostasValidas: 4, fornecedorUnico: false, emergencial: false, pedidoRef: "PED-2026-0003" },
  { id: 6, projetoId: 1, codigo: "PC-06", escopo: "Bombas de polpa", tipo: "Equipamento", disciplina: "Mecânica", modalidade: "Preço global", lli: false, eacCodigo: "2.1.4",
    estimativaCentavos: 160000000, compradorId: 7, ros: "2026-10-15",
    plano: { requisicao: "2026-02-02", rfx: "2026-02-16", propostas: "2026-03-09", eqTecnica: "2026-03-21", eqComercial: "2026-04-03", adjudicacao: "2026-04-10", pedido: "2026-04-13" },
    real: { requisicao: "2026-02-02", rfx: "2026-02-20", propostas: "2026-03-16", eqTecnica: "2026-04-01", eqComercial: "2026-04-17", adjudicacao: "2026-04-22", pedido: "2026-04-24" },
    previsao: {}, etapa: "Pedido/contrato emitido", fornecedorId: 8, adjudicadoCentavos: 150000000, primeiraPropostaCentavos: 155500000,
    propostasValidas: 3, fornecedorUnico: false, emergencial: false, pedidoRef: "PED-2026-0004" },
  { id: 7, projetoId: 1, codigo: "PC-07", escopo: "Células de flotação", tipo: "Equipamento", disciplina: "Mecânica", modalidade: "Preço global", lli: true, eacCodigo: "2.1.5",
    estimativaCentavos: 195000000, compradorId: 7, ros: "2026-11-10",
    plano: { requisicao: "2026-02-09", rfx: "2026-02-23", propostas: "2026-03-16", eqTecnica: "2026-03-30", eqComercial: "2026-04-13", adjudicacao: "2026-04-20", pedido: "2026-04-23" },
    real: { requisicao: "2026-02-09", rfx: "2026-02-23", propostas: "2026-03-16", eqTecnica: "2026-03-29", eqComercial: "2026-04-12", adjudicacao: "2026-04-17", pedido: "2026-04-20" },
    previsao: {}, etapa: "Pedido/contrato emitido", fornecedorId: 12, adjudicadoCentavos: 180000000, primeiraPropostaCentavos: 186000000,
    propostasValidas: 3, fornecedorUnico: false, emergencial: false, pedidoRef: "PED-2026-0005" },
  { id: 8, projetoId: 1, codigo: "PC-08", escopo: "Válvulas de processo", tipo: "Material", disciplina: "Tubulação", modalidade: "Preço unitário", lli: false, eacCodigo: "2.1.6",
    estimativaCentavos: 48000000, compradorId: 7, ros: "2026-09-30",
    plano: { requisicao: "2026-03-02", rfx: "2026-03-16", propostas: "2026-04-06", eqTecnica: "2026-04-14", eqComercial: "2026-04-23", adjudicacao: "2026-04-30", pedido: "2026-05-03" },
    real: { requisicao: "2026-03-02", rfx: "2026-03-16", propostas: "2026-04-08", eqTecnica: "2026-04-19", eqComercial: "2026-05-01", adjudicacao: "2026-05-06", pedido: "2026-05-08" },
    previsao: {}, etapa: "Pedido/contrato emitido", fornecedorId: 3, adjudicadoCentavos: 45000000, primeiraPropostaCentavos: 47200000,
    propostasValidas: 5, fornecedorUnico: false, emergencial: false, pedidoRef: "PED-2026-0006" },
  { id: 9, projetoId: 1, codigo: "PC-09", escopo: "Transformadores de força", tipo: "Equipamento", disciplina: "Elétrica", modalidade: "Preço global", lli: true, eacCodigo: "2.2.1",
    estimativaCentavos: 150000000, compradorId: 7, ros: "2026-10-20",
    plano: { requisicao: "2026-01-19", rfx: "2026-02-02", propostas: "2026-02-23", eqTecnica: "2026-03-06", eqComercial: "2026-03-18", adjudicacao: "2026-03-25", pedido: "2026-03-28" },
    real: { requisicao: "2026-01-19", rfx: "2026-02-02", propostas: "2026-02-24", eqTecnica: "2026-03-09", eqComercial: "2026-03-22", adjudicacao: "2026-03-27", pedido: "2026-03-30" },
    previsao: {}, etapa: "Pedido/contrato emitido", fornecedorId: 2, adjudicadoCentavos: 140000000, primeiraPropostaCentavos: 148500000,
    propostasValidas: 3, fornecedorUnico: false, emergencial: false, pedidoRef: "PED-2026-0007" },
  { id: 10, projetoId: 1, codigo: "PC-10", escopo: "Painéis e CCMs", tipo: "Equipamento", disciplina: "Elétrica", modalidade: "Preço global", lli: false, eacCodigo: "2.2.2",
    estimativaCentavos: 115000000, compradorId: 7, ros: "2026-09-10",
    plano: { requisicao: "2026-02-16", rfx: "2026-03-02", propostas: "2026-03-23", eqTecnica: "2026-03-31", eqComercial: "2026-04-08", adjudicacao: "2026-04-15", pedido: "2026-04-18" },
    real: { requisicao: "2026-02-16", rfx: "2026-03-02", propostas: "2026-03-23", eqTecnica: "2026-03-31", eqComercial: "2026-04-09", adjudicacao: "2026-04-14", pedido: "2026-04-16" },
    previsao: {}, etapa: "Pedido/contrato emitido", fornecedorId: 9, adjudicadoCentavos: 112000000, primeiraPropostaCentavos: 115000000,
    propostasValidas: 4, fornecedorUnico: false, emergencial: false, pedidoRef: "PED-2026-0008" },
  { id: 11, projetoId: 1, codigo: "PC-11", escopo: "Cabos e bandejamento", tipo: "Material", disciplina: "Elétrica", modalidade: "Preço unitário", lli: false, eacCodigo: "2.2.3",
    estimativaCentavos: 105000000, compradorId: 7, ros: "2026-10-08",
    plano: { requisicao: "2026-03-16", rfx: "2026-03-30", propostas: "2026-04-20", eqTecnica: "2026-04-29", eqComercial: "2026-05-08", adjudicacao: "2026-05-15", pedido: "2026-05-18" },
    real: { requisicao: "2026-03-16", rfx: "2026-04-01", propostas: "2026-04-24", eqTecnica: "2026-05-04", eqComercial: "2026-05-15", adjudicacao: "2026-05-20", pedido: "2026-05-22" },
    previsao: {}, etapa: "Pedido/contrato emitido", fornecedorId: 10, adjudicadoCentavos: 98000000, primeiraPropostaCentavos: 104000000,
    propostasValidas: 4, fornecedorUnico: false, emergencial: false, pedidoRef: "PED-2026-0009" },
  { id: 12, projetoId: 1, codigo: "PC-12", escopo: "Instrumentação de campo", tipo: "Material", disciplina: "Instrumentação", modalidade: "Preço unitário", lli: false, eacCodigo: "2.2.4",
    estimativaCentavos: 32000000, compradorId: 7, ros: "2026-11-20",
    plano: { requisicao: "2026-04-06", rfx: "2026-04-20", propostas: "2026-05-11", eqTecnica: "2026-05-20", eqComercial: "2026-05-29", adjudicacao: "2026-06-05", pedido: "2026-06-08" },
    real: { requisicao: "2026-04-06", rfx: "2026-04-22", propostas: "2026-05-14", eqTecnica: "2026-05-25", eqComercial: "2026-06-05", adjudicacao: "2026-06-10", pedido: "2026-06-12" },
    previsao: {}, etapa: "Pedido/contrato emitido", fornecedorId: 11, adjudicadoCentavos: 30000000, primeiraPropostaCentavos: 32000000,
    propostasValidas: 3, fornecedorUnico: false, emergencial: false, pedidoRef: "PED-2026-0010" },
  { id: 13, projetoId: 1, codigo: "PC-13", escopo: "Montagem eletromecânica", tipo: "Serviço", disciplina: "Montagem", modalidade: "Preço unitário", lli: false, eacCodigo: "3.2",
    estimativaCentavos: 510000000, compradorId: 7, ros: "2026-05-04",
    plano: { requisicao: "2026-02-02", rfx: "2026-02-16", propostas: "2026-03-09", eqTecnica: "2026-03-24", eqComercial: "2026-04-08", adjudicacao: "2026-04-15", pedido: "2026-04-18" },
    real: { requisicao: "2026-02-02", rfx: "2026-02-18", propostas: "2026-03-13", eqTecnica: "2026-03-29", eqComercial: "2026-04-15", adjudicacao: "2026-04-20", pedido: "2026-04-24" },
    previsao: {}, etapa: "Pedido/contrato emitido", fornecedorId: 1, adjudicadoCentavos: 480000000, primeiraPropostaCentavos: 505000000,
    propostasValidas: 4, fornecedorUnico: false, emergencial: false, contratoRef: "CT-2026-014" },
  { id: 14, projetoId: 1, codigo: "PC-14", escopo: "Sistema digital de controle (SDCD)", tipo: "Equipamento", disciplina: "Automação", modalidade: "Preço global", lli: false, eacCodigo: "2.2.5",
    estimativaCentavos: 60000000, compradorId: 7, ros: "2027-01-10",
    plano: { requisicao: "2026-06-15", rfx: "2026-07-01", propostas: "2026-07-22", eqTecnica: "2026-08-15", eqComercial: "2026-09-08", adjudicacao: "2026-09-15", pedido: "2026-09-18", entrega: "2026-12-28" },
    real: { requisicao: "2026-06-15", rfx: "2026-07-06", propostas: "2026-07-27", eqTecnica: "2026-08-25" },
    previsao: { eqComercial: "2026-09-28", adjudicacao: "2026-10-02", pedido: "2026-10-05", entrega: "2027-01-08" },
    etapa: "Equalização comercial", fornecedorId: null, adjudicadoCentavos: null, primeiraPropostaCentavos: null,
    propostasValidas: 4, fornecedorUnico: false, emergencial: false }
];

/* Pedidos em diligenciamento. marcos: lb = cronograma contratual do pedido; previsao = data
   reprogramada pelo diligenciamento; realizada = data de conclusão. A previsão de entrega do pedido
   (previsao) é a previsão do marco Entrega. */
(function () {
var NOMES = ["Aprovação de documentos", "Matéria-prima", "Fabricação", "Inspeção / FAT", "Embarque", "Entrega"];
function _marcos(lb, previsao, realizada) {
  return NOMES.map(function (n, i) {
    var r = realizada[i] || null;
    return { nome: n, lb: lb[i], previsao: r || previsao[i] || lb[i], realizada: r };
  });
}
window.MOCK.pedidos = [
  { id: 1, projetoId: 1, numero: "PED-2026-0001", pacoteId: 3, fornecedorId: 7, descricao: "Moinho de bolas 5,0 x 7,5 m", valorCentavos: 900000000, lli: true,
    emissao: "2026-02-25", dataContratual: "2026-08-01", previsao: "2026-10-05", ros: "2026-09-15", entrega: null,
    marcos: _marcos(["2026-03-30", "2026-04-30", "2026-06-30", "2026-07-10", "2026-07-15", "2026-08-01"],
      [null, null, null, null, "2026-09-28", "2026-10-05"],
      ["2026-04-08", "2026-05-12", "2026-08-28", "2026-09-10"]) },
  { id: 2, projetoId: 1, numero: "PED-2026-0002", pacoteId: 4, fornecedorId: 7, descricao: "Britador cônico 300 t/h", valorCentavos: 290000000, lli: true,
    emissao: "2026-03-20", dataContratual: "2026-09-20", previsao: "2026-10-10", ros: "2026-10-01", entrega: null,
    marcos: _marcos(["2026-04-20", "2026-05-25", "2026-08-20", "2026-09-05", "2026-09-10", "2026-09-20"],
      [null, null, null, "2026-09-30", "2026-10-03", "2026-10-10"],
      ["2026-04-24", "2026-06-10", "2026-09-15"]) },
  { id: 3, projetoId: 1, numero: "PED-2026-0003", pacoteId: 5, fornecedorId: 4, descricao: "Transportadores de correia TC-210-01 a TC-210-05", valorCentavos: 225000000, lli: false,
    emissao: "2026-03-18", dataContratual: "2026-08-30", previsao: "2026-08-28", ros: "2026-09-01", entrega: "2026-08-28",
    marcos: _marcos(["2026-04-15", "2026-05-15", "2026-07-31", "2026-08-10", "2026-08-20", "2026-08-30"], [],
      ["2026-04-14", "2026-05-15", "2026-07-30", "2026-08-10", "2026-08-21", "2026-08-28"]),
    recebimento: { data: "2026-08-28", conferido: true, avarias: false, pendencias: "" } },
  { id: 4, projetoId: 1, numero: "PED-2026-0004", pacoteId: 6, fornecedorId: 8, descricao: "Bombas de polpa BP-210 e BP-310 (8 un.)", valorCentavos: 150000000, lli: false,
    emissao: "2026-04-24", dataContratual: "2026-09-05", previsao: "2026-10-20", ros: "2026-10-15", entrega: null,
    marcos: _marcos(["2026-05-20", "2026-06-15", "2026-08-10", "2026-08-20", "2026-08-30", "2026-09-05"],
      [null, null, "2026-09-22", "2026-10-05", "2026-10-12", "2026-10-20"],
      ["2026-06-02", "2026-07-08"]) },
  { id: 5, projetoId: 1, numero: "PED-2026-0005", pacoteId: 7, fornecedorId: 12, descricao: "Células de flotação 50 m³ (4 un.)", valorCentavos: 180000000, lli: true,
    emissao: "2026-04-20", dataContratual: "2026-10-15", previsao: "2026-10-15", ros: "2026-11-10", entrega: null,
    marcos: _marcos(["2026-05-20", "2026-06-20", "2026-09-10", "2026-09-25", "2026-10-05", "2026-10-15"], [],
      ["2026-05-18", "2026-06-19", "2026-09-08"]) },
  { id: 6, projetoId: 1, numero: "PED-2026-0006", pacoteId: 8, fornecedorId: 3, descricao: "Válvulas de processo (lote 1)", valorCentavos: 45000000, lli: false,
    emissao: "2026-05-08", dataContratual: "2026-09-05", previsao: "2026-09-10", ros: "2026-09-30", entrega: "2026-09-10",
    marcos: _marcos(["2026-06-01", "2026-06-20", "2026-08-10", "2026-08-20", "2026-08-30", "2026-09-05"], [],
      ["2026-06-03", "2026-06-25", "2026-08-18", "2026-08-27", "2026-09-04", "2026-09-10"]),
    recebimento: { data: "2026-09-10", conferido: true, avarias: false, pendencias: "Certificados de 6 válvulas divergentes (RNC-TN-2026-0003)." } },
  { id: 7, projetoId: 1, numero: "PED-2026-0007", pacoteId: 9, fornecedorId: 2, descricao: "Transformadores de força 13,8 kV (2 un.)", valorCentavos: 140000000, lli: true,
    emissao: "2026-03-30", dataContratual: "2026-10-10", previsao: "2026-10-01", ros: "2026-10-20", entrega: null,
    marcos: _marcos(["2026-04-30", "2026-05-30", "2026-08-30", "2026-09-26", "2026-10-03", "2026-10-10"],
      [null, null, null, "2026-09-26", "2026-09-28", "2026-10-01"],
      ["2026-04-28", "2026-05-26", "2026-08-21"]) },
  { id: 8, projetoId: 1, numero: "PED-2026-0008", pacoteId: 10, fornecedorId: 9, descricao: "Painéis e CCMs da subestação unitária", valorCentavos: 112000000, lli: false,
    emissao: "2026-04-16", dataContratual: "2026-09-01", previsao: "2026-09-01", ros: "2026-09-10", entrega: "2026-09-01",
    marcos: _marcos(["2026-05-15", "2026-06-10", "2026-08-05", "2026-08-15", "2026-08-25", "2026-09-01"], [],
      ["2026-05-14", "2026-06-10", "2026-08-04", "2026-08-14", "2026-08-25", "2026-09-01"]),
    recebimento: { data: "2026-09-01", conferido: true, avarias: false, pendencias: "" } },
  { id: 9, projetoId: 1, numero: "PED-2026-0009", pacoteId: 11, fornecedorId: 10, descricao: "Cabos de potência e bandejas (lote 2)", valorCentavos: 98000000, lli: false,
    emissao: "2026-05-22", dataContratual: "2026-10-05", previsao: "2026-10-03", ros: "2026-10-08", entrega: null,
    marcos: _marcos(["2026-06-15", "2026-07-10", "2026-09-10", "2026-09-20", "2026-09-28", "2026-10-05"],
      [null, null, null, null, "2026-09-28", "2026-10-03"],
      ["2026-06-12", "2026-07-10", "2026-09-12", "2026-09-22"]) },
  { id: 10, projetoId: 1, numero: "PED-2026-0010", pacoteId: 12, fornecedorId: 11, descricao: "Instrumentação de campo (transmissores e válvulas de controle)", valorCentavos: 30000000, lli: false,
    emissao: "2026-06-12", dataContratual: "2026-11-05", previsao: "2026-11-05", ros: "2026-11-20", entrega: null,
    marcos: _marcos(["2026-07-10", "2026-08-10", "2026-10-10", "2026-10-20", "2026-10-28", "2026-11-05"], [],
      ["2026-07-09", "2026-08-12"]) }
];
})();

/* Processos de compra (RFx): convidados, propostas e equalização (nota técnica 0 a 100; pesos técnico
   e comercial). A etapa do processo é a do pacote (fonte única). Nota comercial e ranking: calculados. */
window.MOCK.processos = [
  { id: 1, pacoteId: 14, numero: "RFQ-2026-014", pesoTecnico: 40, pesoComercial: 60, dataLimitePropostas: "2026-07-27",
    convidados: ["Teta Automação", "Kappa Elétrica", "Sistemas Nu", "Xi Controles", "Ômicron Automação"],
    propostas: [
      { id: 1, fornecedor: "Teta Automação", fornecedorId: 11, recebida: "2026-07-24", valorCentavos: 38500000, prazoDias: 95, validade: "2026-10-31",
        notaTecnica: 88, tecnicamenteAprovada: true, desvios: "Sem desvios.", anexos: [{ nome: "Proposta Teta RFQ-2026-014.pdf" }] },
      { id: 2, fornecedor: "Kappa Elétrica", fornecedorId: 9, recebida: "2026-07-25", valorCentavos: 41200000, prazoDias: 110, validade: "2026-10-25",
        notaTecnica: 82, tecnicamenteAprovada: true, desvios: "Licenças de engenharia cobradas à parte.", anexos: [{ nome: "Proposta Kappa RFQ-2026-014.pdf" }] },
      { id: 3, fornecedor: "Sistemas Nu", fornecedorId: null, recebida: "2026-07-27", valorCentavos: 36900000, prazoDias: 150, validade: "2026-10-27",
        notaTecnica: 64, tecnicamenteAprovada: false, desvios: "Redundância de CPU não atende à especificação.", anexos: [{ nome: "Proposta Sistemas Nu.pdf" }] },
      { id: 4, fornecedor: "Xi Controles", fornecedorId: null, recebida: "2026-07-27", valorCentavos: 44800000, prazoDias: 100, validade: "2026-11-15",
        notaTecnica: 90, tecnicamenteAprovada: true, desvios: "Treinamento reduzido a 40 h.", anexos: [{ nome: "Proposta Xi Controles.pdf" }] }
    ],
    negociacoes: [], recomendacao: null, aprovacao: null, historico: [
      { data: "2026-07-06", etapa: "RFx emitida", porId: 7, texto: "RFQ enviada a 5 fornecedores." },
      { data: "2026-07-27", etapa: "Equalização técnica", porId: 7, texto: "Recebimento encerrado com 4 propostas." },
      { data: "2026-08-25", etapa: "Equalização comercial", porId: 6, texto: "Parecer técnico emitido: Sistemas Nu reprovada (redundância de CPU)." }
    ] },
  { id: 3, pacoteId: 12, numero: "RFQ-2026-012", pesoTecnico: 40, pesoComercial: 60, dataLimitePropostas: "2026-05-13",
    convidados: ["Teta Automação", "Kappa Elétrica", "Ípsilon Instrumentos", "Sigma Bombas"],
    propostas: [
      { id: 1, fornecedor: "Teta Automação", fornecedorId: 11, recebida: "2026-05-12", valorCentavos: 32000000, prazoDias: 145, validade: "2026-07-31",
        notaTecnica: 84, tecnicamenteAprovada: true, desvios: "Sem desvios.", anexos: [{ nome: "Proposta Teta RFQ-2026-012.pdf" }] },
      { id: 2, fornecedor: "Kappa Elétrica", fornecedorId: 9, recebida: "2026-05-13", valorCentavos: 34500000, prazoDias: 150, validade: "2026-07-31",
        notaTecnica: 80, tecnicamenteAprovada: true, desvios: "Certificados de calibração em até 30 dias após a entrega.", anexos: [{ nome: "Proposta Kappa RFQ-2026-012.pdf" }] },
      { id: 3, fornecedor: "Ípsilon Instrumentos", fornecedorId: null, recebida: "2026-05-14", valorCentavos: 33800000, prazoDias: 140, validade: "2026-08-14",
        notaTecnica: 76, tecnicamenteAprovada: true, desvios: "Transmissores de outro fabricante, equivalentes à especificação.", anexos: [{ nome: "Proposta Ípsilon.pdf" }] }
    ],
    negociacoes: [{ data: "2026-06-05", fornecedor: "Teta Automação", valorCentavos: 30000000, observacao: "Desconto por pagamento em marcos e frete incluso." }],
    recomendacao: { data: "2026-06-08", fornecedor: "Teta Automação", fornecedorId: 11, valorCentavos: 30000000, porId: 7,
      justificativa: "Melhor nota final; fornecedor qualificado em instrumentação, com qualificação em automação em andamento, sem impacto neste escopo." },
    aprovacao: { data: "2026-06-10", porId: 2, alcada: "Gerente de suprimentos", parecer: "Aprovado." },
    historico: [
      { data: "2026-04-22", etapa: "RFx emitida", porId: 7, texto: "RFQ enviada a 4 fornecedores." },
      { data: "2026-05-14", etapa: "Equalização técnica", porId: 7, texto: "Recebimento encerrado com 3 propostas." },
      { data: "2026-05-25", etapa: "Equalização comercial", porId: 9, texto: "Três propostas tecnicamente aprovadas." },
      { data: "2026-06-05", etapa: "Negociação", porId: 7, texto: "Mapa comercial concluído." },
      { data: "2026-06-08", etapa: "Recomendação de adjudicação", porId: 7, texto: "Recomendada a Teta Automação por R$ 300.000,00." },
      { data: "2026-06-10", etapa: "Aprovada", porId: 2, texto: "Aprovada na alçada do gerente de suprimentos." },
      { data: "2026-06-12", etapa: "Pedido/contrato emitido", porId: 7, texto: "Pedido PED-2026-0010 emitido." }
    ] }
];

/* Qualificação de fornecedores e contratadas. documentosEmDia é calculado pela api a partir das validades. */
(function () {
function _docs(fiscal, trabalhista, fgts, iso) {
  var d = [{ nome: "Certidão negativa de débitos federais", validade: fiscal }, { nome: "Certidão negativa de débitos trabalhistas", validade: trabalhista },
    { nome: "Certificado de regularidade do FGTS", validade: fgts }];
  if (iso) d.push({ nome: "Certificado ISO 9001", validade: iso });
  return d;
}
window.MOCK.fornecedores = [
  { empresaId: 1, situacao: "Qualificado", categorias: ["Montagem eletromecânica"], validadeQualificacao: "2027-03-31",
    documentos: _docs("2027-01-20", "2027-02-10", "2026-11-05", "2027-08-30"), historico: [] },
  { empresaId: 2, situacao: "Qualificado", categorias: ["Transformadores", "Equipamentos elétricos"], validadeQualificacao: "2027-06-30",
    documentos: _docs("2027-02-15", "2027-01-30", "2026-12-12", "2028-03-01"), historico: [] },
  { empresaId: 3, situacao: "Restrito", categorias: ["Válvulas"], validadeQualificacao: "2026-12-31",
    documentos: _docs("2027-01-10", "2027-03-02", "2026-10-30", "2027-05-18"),
    observacao: "Restrição por certificados divergentes (RNC-TN-2026-0003) até a auditoria de fornecedor.",
    historico: [{ data: "2026-09-12", de: "Qualificado", para: "Restrito", porId: 9, justificativa: "Certificados de 6 válvulas divergentes no recebimento (RNC-TN-2026-0003)." }] },
  { empresaId: 4, situacao: "Qualificado", categorias: ["Estruturas metálicas", "Transportadores"], validadeQualificacao: "2027-02-28",
    documentos: _docs("2026-12-20", "2027-01-15", "2026-11-20"), historico: [] },
  { empresaId: 5, situacao: "Qualificado", categorias: ["Engenharia"], validadeQualificacao: "2027-01-31",
    documentos: _docs("2027-02-01", "2027-02-01", "2026-12-01", "2027-10-10"), historico: [] },
  { empresaId: 6, situacao: "Qualificado", categorias: ["Obras civis", "Terraplenagem"], validadeQualificacao: "2026-11-30",
    documentos: _docs("2026-12-18", "2026-09-15", "2026-10-28"),
    observacao: "Certidão trabalhista vencida em 15/09/2026.", historico: [] },
  { empresaId: 7, situacao: "Qualificado", categorias: ["Moagem", "Britagem"], validadeQualificacao: "2027-05-31",
    documentos: _docs("2027-03-10", "2027-02-20", "2026-12-30", "2028-01-15"), historico: [] },
  { empresaId: 8, situacao: "Qualificado", categorias: ["Bombas"], validadeQualificacao: "2027-04-30",
    documentos: _docs("2027-01-25", "2027-01-25", "2026-11-25"), historico: [] },
  { empresaId: 9, situacao: "Qualificado", categorias: ["Painéis elétricos"], validadeQualificacao: "2027-03-31",
    documentos: _docs("2027-02-28", "2027-02-28", "2026-12-15", "2027-09-01"), historico: [] },
  { empresaId: 10, situacao: "Qualificado", categorias: ["Cabos"], validadeQualificacao: "2027-01-31",
    documentos: _docs("2026-12-05", "2027-01-05", "2026-11-12"), historico: [] },
  { empresaId: 11, situacao: "Em qualificação", categorias: ["Automação", "Instrumentação"], validadeQualificacao: null,
    documentos: _docs("2027-01-31", "2027-01-31", "2026-12-20"),
    observacao: "Qualificada em instrumentação; auditoria de automação agendada para outubro.", historico: [] },
  { empresaId: 12, situacao: "Qualificado", categorias: ["Flotação"], validadeQualificacao: "2027-02-28",
    documentos: _docs("2027-02-10", "2027-02-10", "2026-12-08"), historico: [] }
];
})();

/* Análise do período (04): comentário executivo e analítico por tipo (Semanal ou Mensal) e período,
   inserido e editado em modal no módulo. desvios: comentário por desvio negativo detectado (chave
   calculada pela api com os dados do período). Semana 39 e setembro sem análise (em andamento). */
window.MOCK.analisesPeriodo = (window.MOCK.analisesPeriodo || []).concat([
  { id: 21, projetoId: 1, modulo: "suprimentos", tipo: "Semanal", periodo: "2026-S38", criadoPorId: 5, criadoEm: "2026-09-21T11:00", atualizadoPorId: 5, atualizadoEm: "2026-09-21T11:00",
    analise: "Suprimentos mantém 13 de 14 pacotes adjudicados até o corte (92,9%) e saving acumulado positivo. O ponto crítico são os equipamentos de longo prazo: moinho de bolas, britador cônico e bombas de polpa estão com folga negativa em relação à necessidade da obra. Nas últimas quatro semanas não houve piora das folgas, mas também não houve recuperação. Tendência: sem aceleração da fabricação do moinho, o atraso de 20 dias passa a impactar o início da montagem mecânica em novembro.",
    desvios: [
      { chave: "aderencia", indicador: "Aderência ao plano de compras", comentario: "Pacote do SDCD pendente de equalização técnica. Adjudicação prevista para a S40, sem impacto no caminho crítico." },
      { chave: "otd", indicador: "Entregas no prazo (OTD)", comentario: "Uma entrega fora do prazo no período (bombas reserva), por falha de transporte do fornecedor. Multa contratual em avaliação." },
      { chave: "criticos", indicador: "Pedidos críticos", comentario: "Moinho (-20 dias), britador (-9) e bombas (-5). Diligenciamento semanal na fábrica e proposta de embarque aéreo parcial das bombas." },
      { chave: "marcos_atrasados", indicador: "Marcos realizados com atraso no período", comentario: "Fabricação do britador concluída com 26 dias de atraso por falta de forjados. Fornecedor apresentou plano de recuperação na inspeção." }
    ] },
  { id: 22, projetoId: 1, modulo: "suprimentos", tipo: "Mensal", periodo: "2026-08", criadoPorId: 5, criadoEm: "2026-09-04T09:30", atualizadoPorId: 5, atualizadoEm: "2026-09-04T09:30",
    analise: "Agosto encerra com todos os pacotes planejados até o corte adjudicados e cinco marcos de fabricação e logística realizados com atraso. O desempenho dos fornecedores de equipamentos de longo prazo piorou no bimestre, com destaque para o moinho de bolas, que acumula 59 dias de atraso na fabricação. Tendência: o risco de atraso da montagem mecânica cresce em outubro; a estratégia é concentrar o diligenciamento em três pedidos críticos e avaliar o transporte expresso.",
    desvios: [
      { chave: "criticos", indicador: "Pedidos críticos", comentario: "Três pedidos com folga negativa (moinho, britador e bombas). Diligenciamento em fábrica e reunião executiva com o fornecedor do moinho." },
      { chave: "marcos_atrasados", indicador: "Marcos realizados com atraso no período", comentario: "Cinco marcos atrasados, o mais relevante é a fabricação do moinho (59 dias). Demais atrasos até 8 dias, absorvidos pela folga." }
    ] }
]);
