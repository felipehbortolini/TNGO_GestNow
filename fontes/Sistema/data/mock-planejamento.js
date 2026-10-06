/* ==========================================================================
   mock-planejamento.js | 02 Planejamento (dados fictícios).
   curvaFisica: % acumulado por mês (linha de base, real até o corte e
   tendência a partir do corte). avancoAreas: pesos e % por área na data de
   corte (a média ponderada fecha com a curva). punch: itens da Punch list.
   ========================================================================== */
window.MOCK = window.MOCK || {};

window.MOCK.curvaFisica = [
  { id: 1, projetoId: 1, corte: "2026-09",
    meses:    ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10", "2026-11", "2026-12", "2027-01", "2027-02", "2027-03", "2027-04"],
    baseline: [2.1, 5.4, 10.2, 16.8, 24.5, 33.0, 42.1, 54.0, 65.7, 75.8, 84.2, 90.6, 95.1, 98.4, 100, 100],
    real:     [1.8, 4.9, 9.1, 15.2, 22.6, 30.4, 39.0, 50.3, 61.8, null, null, null, null, null, null, null],
    tendencia:[null, null, null, null, null, null, null, null, 61.8, 71.2, 80.1, 87.0, 92.6, 96.4, 99.0, 100] }
];

window.MOCK.avancoAreas = [
  { id: 1, projetoId: 1, area: "Engenharia", peso: 15, previsto: 98, real: 96 },
  { id: 2, projetoId: 1, area: "Suprimentos", peso: 30, previsto: 80, real: 78 },
  { id: 3, projetoId: 1, area: "Obras civis", peso: 25, previsto: 70, real: 66 },
  { id: 4, projetoId: 1, area: "Montagem eletromecânica", peso: 25, previsto: 38, real: 30 },
  { id: 5, projetoId: 1, area: "Comissionamento", peso: 5, previsto: 0, real: 0 }
];

/* Sistemas para a completação mecânica e o comissionamento */
window.MOCK.sistemas = [
  { id: 1, projetoId: 1, codigo: "210", nome: "Moagem", area: "Beneficiamento" },
  { id: 2, projetoId: 1, codigo: "310", nome: "Flotação", area: "Beneficiamento" },
  { id: 3, projetoId: 1, codigo: "420", nome: "Subestação unitária", area: "Elétrica" },
  { id: 4, projetoId: 1, codigo: "510", nome: "Utilidades", area: "Utilidades" }
];

/* Punch list. Situação: Aberto, Em tratamento, Aguardando verificação, Fechado, Cancelado */
window.MOCK.punch = [
  { id: 1, projetoId: 1, codigo: "PL-TN-2026-0001", sistemaId: 3, subsistema: "Painéis", tag: "PN-420-01", disciplina: "Elétrica", categoria: "A",
    marco: "Completação mecânica", origem: "Walkdown", descricao: "Falta identificação dos cabos no painel PN-420-01.",
    empresaId: 1, responsavelId: 5, identificadoPorId: 8, abertura: "2026-08-05", prazo: "2026-08-25",
    situacao: "Fechado", verificadoPorId: 9, fechamento: "2026-08-20", evidencia: "foto-fechamento-0001.jpg" },
  { id: 2, projetoId: 1, codigo: "PL-TN-2026-0002", sistemaId: 1, subsistema: "Transportadores", tag: "TC-210-03", disciplina: "Mecânica", categoria: "B",
    marco: "Aceite provisório", origem: "Walkdown", descricao: "Proteção do acoplamento do transportador TC-210-03 ausente.",
    empresaId: 1, responsavelId: 5, identificadoPorId: 8, abertura: "2026-08-12", prazo: "2026-10-10", situacao: "Em tratamento" },
  { id: 3, projetoId: 1, codigo: "PL-TN-2026-0003", sistemaId: 3, subsistema: "Painéis", tag: "PN-420-01", disciplina: "Elétrica", categoria: "A",
    marco: "Completação mecânica", origem: "Inspeção", descricao: "Aterramento do painel PN-420-01 incompleto.",
    empresaId: 1, responsavelId: 5, identificadoPorId: 9, abertura: "2026-08-28", prazo: "2026-09-18", situacao: "Em tratamento" },
  { id: 4, projetoId: 1, codigo: "PL-TN-2026-0004", sistemaId: 1, subsistema: "Instrumentação", tag: "PT-210-07", disciplina: "Instrumentação", categoria: "A",
    marco: "Comissionamento", origem: "Comissionamento", descricao: "Transmissor de pressão PT-210-07 sem certificado de calibração.",
    empresaId: 1, responsavelId: 5, identificadoPorId: 8, abertura: "2026-09-02", prazo: "2026-09-26", situacao: "Aguardando verificação",
    evidencia: "certificado-pt-210-07.pdf" },
  { id: 5, projetoId: 1, codigo: "PL-TN-2026-0005", sistemaId: 4, subsistema: "Casa de bombas", tag: "CB-510", disciplina: "Civil", categoria: "C",
    marco: "Aceite definitivo", origem: "Cliente", descricao: "Acabamento do piso da casa de bombas.",
    empresaId: 6, responsavelId: 11, identificadoPorId: 2, abertura: "2026-09-15", prazo: "2026-11-30", situacao: "Aberto" },
  { id: 6, projetoId: 1, codigo: "PL-TN-2026-0006", sistemaId: 2, subsistema: "Tubulação", tag: "310-P-022", disciplina: "Tubulação", categoria: "B",
    marco: "Pré-comissionamento", origem: "Inspeção", descricao: "Teste hidrostático da linha 310-P-022 sem registro.",
    empresaId: 1, responsavelId: 5, identificadoPorId: 9, abertura: "2026-09-08", prazo: "2026-10-05", situacao: "Aberto" },
  { id: 7, projetoId: 1, codigo: "PL-TN-2026-0007", sistemaId: 1, subsistema: "Tubulação", tag: "210-P-005", disciplina: "Tubulação", categoria: "B",
    marco: "Aceite provisório", origem: "Walkdown", descricao: "Suportes de tubulação sem pintura de acabamento.",
    empresaId: 1, responsavelId: 5, identificadoPorId: 8, abertura: "2026-09-01", prazo: "2026-10-15", situacao: "Em tratamento" },
  { id: 8, projetoId: 1, codigo: "PL-TN-2026-0008", sistemaId: 1, subsistema: "Moinho", tag: "MO-210-01", disciplina: "Mecânica", categoria: "A",
    marco: "Comissionamento", origem: "Comissionamento", descricao: "Alinhamento a laser do motor do moinho pendente.",
    empresaId: 1, responsavelId: 5, identificadoPorId: 8, abertura: "2026-09-18", prazo: "2026-10-02", situacao: "Aberto" },
  { id: 9, projetoId: 1, codigo: "PL-TN-2026-0009", sistemaId: 4, subsistema: "Área de utilidades", tag: "AU-510", disciplina: "Arquitetura", categoria: "C",
    marco: "Aceite definitivo", origem: "Cliente", descricao: "Pintura de sinalização de piso da área de utilidades.",
    empresaId: 6, responsavelId: 11, identificadoPorId: 2, abertura: "2026-09-20", prazo: "2026-12-15", situacao: "Aberto" },
  { id: 10, projetoId: 1, codigo: "PL-TN-2026-0010", sistemaId: 2, subsistema: "Automação", tag: "BP-310-02", disciplina: "Automação", categoria: "B",
    marco: "Comissionamento", origem: "Comissionamento", descricao: "Tela do supervisório sem intertravamento da bomba BP-310-02.",
    empresaId: 1, responsavelId: 5, identificadoPorId: 8, abertura: "2026-08-25", prazo: "2026-09-30", situacao: "Em tratamento" },
  { id: 11, projetoId: 1, codigo: "PL-TN-2026-0011", sistemaId: 3, subsistema: "Cubículos", tag: "C-03", disciplina: "Elétrica", categoria: "A",
    marco: "Comissionamento", origem: "Comissionamento", descricao: "Relé de proteção do cubículo C-03 sem parametrização final.",
    empresaId: 1, responsavelId: 5, identificadoPorId: 8, abertura: "2026-08-10", prazo: "2026-09-10",
    situacao: "Fechado", verificadoPorId: 8, fechamento: "2026-09-05", evidencia: "relatorio-parametrizacao-c03.pdf" },
  { id: 12, projetoId: 1, codigo: "PL-TN-2026-0012", sistemaId: 1, subsistema: "Canaletas", tag: "CN-210", disciplina: "Civil", categoria: "C",
    marco: "Aceite definitivo", origem: "Walkdown", descricao: "Rejunte da canaleta da área do moinho.",
    empresaId: 6, responsavelId: 11, identificadoPorId: 9, abertura: "2026-07-28", prazo: "2026-08-30",
    situacao: "Fechado", verificadoPorId: 9, fechamento: "2026-08-18", evidencia: "foto-fechamento-0012.jpg" },
  { id: 13, projetoId: 1, codigo: "PL-TN-2026-0013", sistemaId: 2, subsistema: "Agitadores", tag: "AG-310-01", disciplina: "Mecânica", categoria: "B",
    marco: "Aceite provisório", origem: "Inspeção", descricao: "Vazamento de óleo no redutor do agitador AG-310-01.",
    empresaId: 1, responsavelId: 5, identificadoPorId: 9, abertura: "2026-09-22", prazo: "2026-10-20", situacao: "Aberto" },
  { id: 14, projetoId: 1, codigo: "PL-TN-2026-0014", sistemaId: 2, subsistema: "Tubulação", tag: "PSV-310-04", disciplina: "Tubulação", categoria: "A",
    marco: "Comissionamento", origem: "Comissionamento", descricao: "Válvula de segurança PSV-310-04 sem teste de bancada.",
    empresaId: 1, responsavelId: 5, identificadoPorId: 8, abertura: "2026-09-10", prazo: "2026-09-24", situacao: "Aberto" },
  { id: 15, projetoId: 1, codigo: "PL-TN-2026-0015", sistemaId: 4, subsistema: "Instrumentação", tag: "LIC-510-02", disciplina: "Instrumentação", categoria: "B",
    marco: "Comissionamento", origem: "Comissionamento", descricao: "Malha de nível LIC-510-02 sem teste de malha.",
    empresaId: 1, responsavelId: 5, identificadoPorId: 8, abertura: "2026-09-11", prazo: "2026-10-09", situacao: "Aguardando verificação",
    evidencia: "folha-teste-malha-lic-510-02.pdf" },
  { id: 16, projetoId: 1, codigo: "PL-TN-2026-0016", sistemaId: 4, subsistema: "Casa de bombas", tag: "CB-510", disciplina: "Civil", categoria: "C",
    marco: "Aceite definitivo", origem: "Cliente", descricao: "Acabamento do piso da casa de bombas (registro duplicado).",
    empresaId: 6, responsavelId: 11, identificadoPorId: 2, abertura: "2026-09-15", prazo: "2026-11-30",
    situacao: "Cancelado", justificativaCancelamento: "Registrado em duplicidade com o PL-TN-2026-0005." }
];

/* ---------------- 6WLA: planejamento de 6 semanas (lookahead) ----------------
   semanas: 6 posições a partir da semana 40 (28/09/2026); 1 = atividade programada.
   restricoes: tipo, descrição, responsável, data necessária, data de remoção. */
window.MOCK.lookaheadInicio = "2026-09-28";
window.MOCK.lookahead = [
  { id: 1, projetoId: 1, codigo: "LA-01", atividade: "Montagem da carcaça do moinho MO-210-01", area: "Moagem 210", disciplina: "Mecânica", empresaId: 1, responsavelId: 5,
    semanas: [1, 1, 1, 0, 0, 0], restricoes: [
      { id: 1, tipo: "Equipamento", descricao: "Guindaste de 250 t mobilizado", responsavelId: 5, necessaria: "2026-09-25", remocao: "2026-09-20" },
      { id: 2, tipo: "Material", descricao: "Chegada do moinho (PED-2026-0001)", responsavelId: 7, necessaria: "2026-09-28", remocao: null } ] },
  { id: 2, projetoId: 1, codigo: "LA-02", atividade: "Alinhamento a laser do motor do moinho", area: "Moagem 210", disciplina: "Mecânica", empresaId: 1, responsavelId: 5,
    semanas: [0, 0, 0, 1, 0, 0], restricoes: [
      { id: 3, tipo: "Predecessora", descricao: "Carcaça do moinho montada (LA-01)", responsavelId: 5, necessaria: "2026-10-19", remocao: null } ] },
  { id: 3, projetoId: 1, codigo: "LA-03", atividade: "Montagem do britador cônico", area: "Moagem 210", disciplina: "Mecânica", empresaId: 1, responsavelId: 5,
    semanas: [0, 0, 1, 1, 0, 0], restricoes: [
      { id: 4, tipo: "Material", descricao: "Entrega do britador (PED-2026-0002)", responsavelId: 7, necessaria: "2026-10-05", remocao: null } ] },
  { id: 4, projetoId: 1, codigo: "LA-04", atividade: "Pipe rack PR-03: estruturas do nível 1", area: "Utilidades 510", disciplina: "Estruturas", empresaId: 1, responsavelId: 5,
    semanas: [1, 1, 0, 0, 0, 0], restricoes: [
      { id: 5, tipo: "Documentação", descricao: "Desenhos de montagem do PR-03 em revisão 0", responsavelId: 6, necessaria: "2026-09-21", remocao: "2026-09-18" },
      { id: 6, tipo: "Segurança", descricao: "Linha de vida definitiva no PR-02 concluída", responsavelId: 5, necessaria: "2026-10-06", remocao: null } ] },
  { id: 5, projetoId: 1, codigo: "LA-05", atividade: "Tubulação de reagentes da flotação", area: "Flotação 310", disciplina: "Tubulação", empresaId: 1, responsavelId: 5,
    semanas: [1, 1, 1, 1, 0, 0], restricoes: [] },
  { id: 6, projetoId: 1, codigo: "LA-06", atividade: "Teste hidrostático das linhas 310-P-018 a 022", area: "Flotação 310", disciplina: "Tubulação", empresaId: 1, responsavelId: 5,
    semanas: [0, 1, 0, 0, 0, 0], restricoes: [
      { id: 7, tipo: "Documentação", descricao: "Procedimento de teste hidrostático aprovado", responsavelId: 9, necessaria: "2026-10-02", remocao: null } ] },
  { id: 7, projetoId: 1, codigo: "LA-07", atividade: "Lançamento de cabos de média tensão", area: "Subestação 420", disciplina: "Elétrica", empresaId: 1, responsavelId: 5,
    semanas: [0, 0, 1, 1, 1, 0], restricoes: [
      { id: 8, tipo: "Material", descricao: "Cabos de média tensão (PED-2026-0009)", responsavelId: 7, necessaria: "2026-10-08", remocao: null } ] },
  { id: 8, projetoId: 1, codigo: "LA-08", atividade: "Energização da subestação unitária", area: "Subestação 420", disciplina: "Elétrica", empresaId: 1, responsavelId: 8,
    semanas: [0, 0, 0, 0, 1, 1], restricoes: [
      { id: 9, tipo: "Material", descricao: "Transformadores entregues (PED-2026-0007)", responsavelId: 7, necessaria: "2026-10-20", remocao: null },
      { id: 10, tipo: "Liberação de área", descricao: "Liberação da concessionária para energização", responsavelId: 2, necessaria: "2026-10-30", remocao: null } ] },
  { id: 9, projetoId: 1, codigo: "LA-09", atividade: "Fundações F-20 a F-28 da casa de bombas", area: "Utilidades 510", disciplina: "Civil", empresaId: 6, responsavelId: 11,
    semanas: [1, 1, 1, 0, 0, 0], restricoes: [
      { id: 11, tipo: "Projeto", descricao: "Resultado da sondagem complementar (RSK-TN-2026-0003)", responsavelId: 6, necessaria: "2026-09-22", remocao: null } ] },
  { id: 10, projetoId: 1, codigo: "LA-10", atividade: "Concretagem da laje da casa de bombas", area: "Utilidades 510", disciplina: "Civil", empresaId: 6, responsavelId: 11,
    semanas: [0, 0, 0, 1, 1, 0], restricoes: [
      { id: 12, tipo: "Predecessora", descricao: "Fundações F-20 a F-28 concluídas (LA-09)", responsavelId: 11, necessaria: "2026-10-19", remocao: null } ] },
  { id: 11, projetoId: 1, codigo: "LA-11", atividade: "Terraplenagem da fase 2 com drenagem", area: "Terraplenagem", disciplina: "Civil", empresaId: 6, responsavelId: 11,
    semanas: [1, 1, 0, 0, 0, 0], restricoes: [] },
  { id: 12, projetoId: 1, codigo: "LA-12", atividade: "Instalação de instrumentos da moagem", area: "Moagem 210", disciplina: "Instrumentação", empresaId: 1, responsavelId: 5,
    semanas: [0, 0, 0, 1, 1, 1], restricoes: [
      { id: 13, tipo: "Material", descricao: "Instrumentos de campo (PED-2026-0010)", responsavelId: 7, necessaria: "2026-10-19", remocao: null } ] },
  { id: 13, projetoId: 1, codigo: "LA-13", atividade: "Montagem das bombas de polpa BP-310", area: "Flotação 310", disciplina: "Mecânica", empresaId: 1, responsavelId: 5,
    semanas: [0, 0, 0, 0, 1, 1], restricoes: [
      { id: 14, tipo: "Material", descricao: "Bombas de polpa (PED-2026-0004)", responsavelId: 7, necessaria: "2026-10-26", remocao: null } ] },
  { id: 14, projetoId: 1, codigo: "LA-14", atividade: "Pintura de acabamento das estruturas da moagem", area: "Moagem 210", disciplina: "Pintura", empresaId: 1, responsavelId: 5,
    semanas: [0, 1, 1, 0, 0, 0], restricoes: [
      { id: 15, tipo: "Mão de obra", descricao: "Equipe de pintura mobilizada", responsavelId: 5, necessaria: "2026-10-02", remocao: null } ] }
];

/* ---------------- Programação Semanal ----------------
   Cada atividade tem a grade diária de segunda a sábado: [previsto, realizado dia, realizado noite].
   Total, PPC e Aderência são calculados (nunca gravados). */
(function (M) {
  function dias(prev, dia, noite) {
    var nomes = ["seg", "ter", "qua", "qui", "sex", "sab"], d = {};
    nomes.forEach(function (n, i) { d[n] = { prev: prev[i] || 0, dia: (dia || [])[i] || 0, noite: (noite || [])[i] || 0 }; });
    return d;
  }
  M.programacoes = [
    { id: 1, projetoId: 1, semana: "2026-S38", inicio: "2026-09-14", fim: "2026-09-19", situacao: "Publicada", aprovacaoRealizado: "Aprovado", elaboradaPorId: 3, aprovadaPorId: 2,
      atividades: [
        { item: 1, idExclusiva: "LA-05", atividade: "Tubulação de reagentes da flotação", local: "Flotação 310", empresaId: 1, fiscalId: 12, encarregado: "Sérgio Pinto", unidade: "m",
          dias: dias([40, 40, 40, 40, 40, 0], [40, 42, 40, 38, 40, 0]), observacoes: "", comentarios: "" },
        { item: 2, idExclusiva: "LA-11", atividade: "Terraplenagem da fase 2 com drenagem", local: "Terraplenagem", empresaId: 6, fiscalId: 12, encarregado: "Wagner Luz", unidade: "m³",
          dias: dias([900, 900, 900, 900, 900, 600], [850, 920, 700, 880, 900, 600]), observacoes: "Chuva na quarta-feira.", comentarios: "" },
        { item: 3, idExclusiva: "LA-04", atividade: "Pipe rack PR-02: estruturas do nível 2", local: "Utilidades 510", empresaId: 1, fiscalId: 12, encarregado: "Mário Castro", unidade: "t",
          dias: dias([6, 6, 6, 6, 6, 0], [6, 6, 6, 6, 6, 0]), observacoes: "", comentarios: "" },
        { item: 4, idExclusiva: "", atividade: "Formas e armação das fundações F-15 a F-19", local: "Utilidades 510", empresaId: 6, fiscalId: 9, encarregado: "Wagner Luz", unidade: "m³",
          dias: dias([20, 20, 20, 20, 20, 10], [20, 18, 20, 20, 22, 10]), observacoes: "", comentarios: "" },
        { item: 5, idExclusiva: "", atividade: "Montagem dos transportadores TC-210-04 e 05", local: "Moagem 210", empresaId: 1, fiscalId: 12, encarregado: "Mário Castro", unidade: "t",
          dias: dias([4, 4, 4, 4, 4, 0], [4, 4, 2, 2, 3, 0]), observacoes: "Falta de chumbadores.", comentarios: "Restrição não identificada no 6WLA." },
        { item: 6, idExclusiva: "", atividade: "Lançamento de bandejamento da subestação", local: "Subestação 420", empresaId: 1, fiscalId: 12, encarregado: "Ronaldo Dias", unidade: "m",
          dias: dias([60, 60, 60, 60, 60, 0], [60, 62, 60, 58, 60, 0]), observacoes: "", comentarios: "" },
        { item: 7, idExclusiva: "", atividade: "Concretagem das bases dos agitadores", local: "Flotação 310", empresaId: 6, fiscalId: 9, encarregado: "Wagner Luz", unidade: "m³",
          dias: dias([0, 12, 0, 12, 0, 0], [0, 12, 0, 12, 0, 0]), observacoes: "", comentarios: "" }
      ] },
    { id: 2, projetoId: 1, semana: "2026-S39", inicio: "2026-09-21", fim: "2026-09-26", situacao: "Publicada", aprovacaoRealizado: "Pendente", elaboradaPorId: 3, aprovadaPorId: null,
      atividades: [
        { item: 1, idExclusiva: "LA-05", atividade: "Tubulação de reagentes da flotação", local: "Flotação 310", empresaId: 1, fiscalId: 12, encarregado: "Sérgio Pinto", unidade: "m",
          dias: dias([40, 40, 40, 40, 40, 0], [40, 40, 40, 42, 38, 0]), observacoes: "", comentarios: "" },
        { item: 2, idExclusiva: "LA-11", atividade: "Terraplenagem da fase 2 com drenagem", local: "Terraplenagem", empresaId: 6, fiscalId: 12, encarregado: "Wagner Luz", unidade: "m³",
          dias: dias([900, 900, 900, 900, 900, 600], [900, 910, 880, 900, 920, 0]), observacoes: "Sábado ainda não apurado.", comentarios: "" },
        { item: 3, idExclusiva: "LA-04", atividade: "Pipe rack PR-03: estruturas do nível 1", local: "Utilidades 510", empresaId: 1, fiscalId: 12, encarregado: "Mário Castro", unidade: "t",
          dias: dias([6, 6, 6, 6, 6, 0], [6, 5, 6, 4, 5, 0]), observacoes: "Aguardando linha de vida do PR-02.", comentarios: "" },
        { item: 4, idExclusiva: "LA-09", atividade: "Fundações F-20 a F-28 da casa de bombas", local: "Utilidades 510", empresaId: 6, fiscalId: 9, encarregado: "Wagner Luz", unidade: "m³",
          dias: dias([25, 25, 25, 25, 25, 0], [0, 0, 10, 8, 12, 0]), observacoes: "Sondagem complementar não concluída.", comentarios: "Restrição de projeto em aberto." },
        { item: 5, idExclusiva: "LA-14", atividade: "Pintura de acabamento das estruturas da moagem", local: "Moagem 210", empresaId: 1, fiscalId: 12, encarregado: "Ronaldo Dias", unidade: "m²",
          dias: dias([80, 80, 80, 80, 80, 0], [0, 0, 0, 0, 0, 0]), observacoes: "Equipe de pintura não mobilizada.", comentarios: "" },
        { item: 6, idExclusiva: "", atividade: "Lançamento de bandejamento da subestação", local: "Subestação 420", empresaId: 1, fiscalId: 12, encarregado: "Ronaldo Dias", unidade: "m",
          dias: dias([60, 60, 60, 60, 60, 0], [60, 60, 64, 60, 60, 0]), observacoes: "", comentarios: "" },
        { item: 7, idExclusiva: "", atividade: "Soldagem da linha 310-P-014 (reparo)", local: "Flotação 310", empresaId: 1, fiscalId: 9, encarregado: "Sérgio Pinto", unidade: "juntas",
          dias: dias([2, 2, 2, 0, 0, 0], [2, 2, 2, 0, 0, 0], [0, 0, 0, 0, 0, 0]), observacoes: "RNC-TN-2026-0004", comentarios: "" }
      ] },
    { id: 3, projetoId: 1, semana: "2026-S40", inicio: "2026-09-28", fim: "2026-10-03", situacao: "Em elaboração", aprovacaoRealizado: "Pendente", elaboradaPorId: 3, aprovadaPorId: null,
      atividades: [
        { item: 1, idExclusiva: "LA-01", atividade: "Montagem da carcaça do moinho MO-210-01", local: "Moagem 210", empresaId: 1, fiscalId: 12, encarregado: "Mário Castro", unidade: "%",
          dias: dias([5, 5, 5, 5, 5, 0]), observacoes: "Depende da chegada do moinho.", comentarios: "" },
        { item: 2, idExclusiva: "LA-04", atividade: "Pipe rack PR-03: estruturas do nível 1", local: "Utilidades 510", empresaId: 1, fiscalId: 12, encarregado: "Mário Castro", unidade: "t",
          dias: dias([6, 6, 6, 6, 6, 0]), observacoes: "", comentarios: "" },
        { item: 3, idExclusiva: "LA-05", atividade: "Tubulação de reagentes da flotação", local: "Flotação 310", empresaId: 1, fiscalId: 12, encarregado: "Sérgio Pinto", unidade: "m",
          dias: dias([40, 40, 40, 40, 40, 0]), observacoes: "", comentarios: "" },
        { item: 4, idExclusiva: "LA-09", atividade: "Fundações F-20 a F-28 da casa de bombas", local: "Utilidades 510", empresaId: 6, fiscalId: 9, encarregado: "Wagner Luz", unidade: "m³",
          dias: dias([25, 25, 25, 25, 25, 10]), observacoes: "", comentarios: "" },
        { item: 5, idExclusiva: "LA-11", atividade: "Terraplenagem da fase 2 com drenagem", local: "Terraplenagem", empresaId: 6, fiscalId: 12, encarregado: "Wagner Luz", unidade: "m³",
          dias: dias([900, 900, 900, 900, 900, 600]), observacoes: "", comentarios: "" }
      ] }
  ];
})(window.MOCK);

/* ---------------- Produtividade ----------------
   produtividadeItens: plano de quantidades da linha de base (LB) por empresa. O total de cada
     item (cabo por tipo, concreto, aço, tubulação, painéis) é distribuído por semana ISO
     ("2026-S39") conforme o cronograma da LB; a contratada aponta o realizado e as HH
     apropriadas por semana. Índice HH (HH por unidade) = produtividade orçada.
   jornadasCampo: registro da fiscalização por frente e dia (chegada, início e término nos dois
     turnos, efetivo). Capacidade produtiva (CP) = horas de execução na frente.
   amostragens: amostragem do trabalho (work sampling) por rodada: pessoas trabalhando, em
     trânsito e paradas, com os motivos.
   paralisacoes: efetivo (Hhora = pessoas x horas) e máquinas ou equipamentos (Mhora) parados.
   Dados gerados com semente fixa (mesmos números a cada abertura). */
(function (M) {
  var semente = 20260925;
  function aleatorio() { semente = (semente * 1103515245 + 12345) % 2147483648; return semente / 2147483648; }
  function variar(base, amplitude) { return base * (1 + (aleatorio() * 2 - 1) * amplitude); }

  /* Semanas ISO (mesma regra de GI.regras, que ainda não está carregado aqui) */
  var DIA = 86400000;
  function inicioSemana(r) {
    var m = /^(\d{4})-S(\d{2})$/.exec(r), ano = Number(m[1]), n = Number(m[2]);
    var jan4 = new Date(Date.UTC(ano, 0, 4));
    return new Date(jan4.getTime() - ((jan4.getUTCDay() || 7) - 1) * DIA + (n - 1) * 7 * DIA);
  }
  function rotulo(d) {
    var t = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
    t.setUTCDate(t.getUTCDate() + 4 - (t.getUTCDay() || 7));
    var ano = t.getUTCFullYear(), n = Math.ceil(((t - Date.UTC(ano, 0, 1)) / DIA + 1) / 7);
    return ano + "-S" + (n < 10 ? "0" : "") + n;
  }
  function semanas(ini, fim) {
    var l = [], d = inicioSemana(ini), f = inicioSemana(fim);
    while (d <= f) { l.push(rotulo(d)); d = new Date(d.getTime() + 7 * DIA); }
    return l;
  }
  function distribuir(total, n, casas) {   /* perfil curva S (rampa 20%, pico 60%, desmobilização 20%) */
    var f = Math.pow(10, casas), u = Math.round(total * f), w = [];
    for (var k = 0; k < n; k++) { var x = (k + 0.5) / n; w.push(x < 0.2 ? 0.2 + 4 * x : x > 0.8 ? 0.2 + 4 * (1 - x) : 1); }
    var sw = w.reduce(function (s, x) { return s + x; }, 0), ex = w.map(function (x) { return u * x / sw; }), b = ex.map(Math.floor);
    var falta = u - b.reduce(function (s, x) { return s + x; }, 0);
    ex.map(function (x, k) { return { k: k, r: x - b[k] }; }).sort(function (a, c) { return c.r - a.r || a.k - c.k; }).slice(0, falta).forEach(function (o) { b[o.k] += 1; });
    return b.map(function (x) { return x / f; });
  }

  var CORTE = "2026-S39";
  /* fatorReal: ritmo realizado em relação ao previsto da LB; pf: HH apropriadas ÷ HH ganhas;
     semApontar: item ainda sem apontamento da semana de corte */
  var ITENS = [
    { codigo: "QTD-01", empresaId: 1, grupo: "Aço", tipo: "Estrutura metálica", disciplina: "Estruturas", unidade: "t", casas: 1, total: 1850, indiceHH: 38,
      ini: "2026-S24", fim: "2026-S48", fatorReal: 0.86, pf: 1.14 },
    { codigo: "QTD-02", empresaId: 1, grupo: "Tubulação", tipo: "Tubulação de processo (montagem)", disciplina: "Tubulação", unidade: "t", casas: 1, total: 420, indiceHH: 95,
      ini: "2026-S30", fim: "2026-S52", fatorReal: 0.8, pf: 1.18 },
    { codigo: "QTD-03", empresaId: 1, grupo: "Cabo elétrico", tipo: "Cabo de potência BT 0,6/1 kV", disciplina: "Elétrica", unidade: "m", casas: 0, total: 68000, indiceHH: 0.12,
      ini: "2026-S33", fim: "2026-S51", fatorReal: 0.72, pf: 1.08 },
    { codigo: "QTD-04", empresaId: 1, grupo: "Cabo elétrico", tipo: "Cabo de controle", disciplina: "Elétrica", unidade: "m", casas: 0, total: 42000, indiceHH: 0.1,
      ini: "2026-S36", fim: "2027-S03", fatorReal: 0.9, pf: 1.02, semApontar: true },
    { codigo: "QTD-05", empresaId: 1, grupo: "Cabo elétrico", tipo: "Cabo de instrumentação", disciplina: "Instrumentação", unidade: "m", casas: 0, total: 36000, indiceHH: 0.11,
      ini: "2026-S38", fim: "2027-S05", fatorReal: 0.65, pf: 1.1 },
    { codigo: "QTD-06", empresaId: 1, grupo: "Cabo elétrico", tipo: "Cabo de média tensão 8,7/15 kV", disciplina: "Elétrica", unidade: "m", casas: 0, total: 9500, indiceHH: 0.35,
      ini: "2026-S42", fim: "2026-S50", emElaboracao: true },
    { codigo: "QTD-07", empresaId: 1, grupo: "Painel elétrico", tipo: "Painéis elétricos montados", disciplina: "Elétrica", unidade: "un", casas: 0, total: 64, indiceHH: 60,
      ini: "2026-S36", fim: "2026-S47", fatorReal: 0.75, pf: 1.06 },
    { codigo: "QTD-08", empresaId: 6, grupo: "Concreto", tipo: "Concreto estrutural (lançamento)", disciplina: "Civil", unidade: "m³", casas: 0, total: 14200, indiceHH: 3.2,
      ini: "2026-S08", fim: "2026-S46", fatorReal: 0.95, pf: 1.03,
      revisao: { rev: 1, data: "2026-07-20", porId: 3, smRef: "SM-TN-2026-0002", totalAnterior: 13350, desde: "2026-S30",
        justificativa: "Reforço das fundações por interferência no subsolo: +850 m³ distribuídos de S30 a S46." } },
    { codigo: "QTD-09", empresaId: 6, grupo: "Aço", tipo: "Aço de armação CA-50", disciplina: "Civil", unidade: "t", casas: 1, total: 1180, indiceHH: 42,
      ini: "2026-S08", fim: "2026-S46", fatorReal: 0.93, pf: 1.05, semApontar: true }
  ];

  M.produtividadeItens = ITENS.map(function (b, i) {
    var sem = semanas(b.ini, b.fim), prev = distribuir(b.total, sem.length, b.casas);
    var f = Math.pow(10, b.casas), acumPrev = 0, acumReal = 0, apont = [];
    if (!b.emElaboracao) {
      sem.forEach(function (s, k) {
        acumPrev += prev[k];
        if (s > CORTE || (s === CORTE && b.semApontar)) return;
        var real = Math.max(0, Math.round(prev[k] * b.fatorReal * variar(1, 0.12) * f) / f);
        real = Math.min(real, Math.round((b.total - acumReal) * f) / f);
        acumReal += real;
        var hh = Math.round(real * b.indiceHH * variar(b.pf, 0.08));
        apont.push({ semana: s, realizado: real, hh: hh, informadoEm: s === CORTE ? "2026-09-25" : null });
      });
    }
    var rev = b.revisao;
    return {
      id: i + 1, projetoId: 1, codigo: b.codigo, empresaId: b.empresaId, grupo: b.grupo, tipo: b.tipo, disciplina: b.disciplina, unidade: b.unidade, casas: b.casas,
      total: b.total, indiceHH: b.indiceHH, inicio: b.ini, fim: b.fim, perfil: "curvaS",
      situacao: b.emElaboracao ? "Em elaboração" : "Aprovada", revisao: rev ? rev.rev : 0,
      aprovadoPorId: b.emElaboracao ? null : 2, aprovadoEm: b.emElaboracao ? null : (b.ini < "2026-S20" ? "2026-02-06" : "2026-06-01"),
      observacoes: b.emElaboracao ? "Aguardando a decisão da SM-TN-2026-0006 (troca da especificação dos cabos de média tensão)." : "",
      distribuicao: sem.map(function (s, k) { return { semana: s, previsto: prev[k] }; }),
      apontamentos: apont,
      revisoes: [{ rev: 0, data: b.ini < "2026-S20" ? "2026-02-06" : "2026-06-01", porId: 3, total: rev ? rev.totalAnterior : b.total, smRef: null, justificativa: "Linha de base original do cronograma." }]
        .concat(rev ? [{ rev: rev.rev, data: rev.data, porId: rev.porId, total: b.total, smRef: rev.smRef, desde: rev.desde, justificativa: rev.justificativa }] : [])
    };
  });

  /* ---- Horas efetivas: frentes acompanhadas pela fiscalização (S36 a S39) ---- */
  var FRENTES = [
    { empresaId: 1, area: "Flotação 310", encarregado: "Sérgio Pinto", efetivo: 28, atraso: 38, fimManha: 690, fimTarde: 995, trab: 0.52 },
    { empresaId: 1, area: "Utilidades 510", encarregado: "Mário Castro", efetivo: 34, atraso: 42, fimManha: 685, fimTarde: 990, trab: 0.49 },
    { empresaId: 1, area: "Subestação 420", encarregado: "Ronaldo Dias", efetivo: 22, atraso: 30, fimManha: 700, fimTarde: 1000, trab: 0.55 },
    { empresaId: 1, area: "Moagem 210", encarregado: "Everaldo Sousa", efetivo: 26, atraso: 45, fimManha: 680, fimTarde: 985, trab: 0.47 },
    { empresaId: 6, area: "Utilidades 510", encarregado: "Wagner Luz", efetivo: 40, atraso: 22, fimManha: 705, fimTarde: 1005, trab: 0.61 },
    { empresaId: 6, area: "Terraplenagem", encarregado: "Gilmar Freitas", efetivo: 18, atraso: 18, fimManha: 710, fimTarde: 1010, trab: 0.64 }
  ];
  function hhmm(min) { min = Math.round(min); return (min < 600 ? "0" : "") + Math.floor(min / 60) + ":" + ("0" + (min % 60)).slice(-2); }
  var DIAS = [];
  (function () {
    var d = new Date(Date.UTC(2026, 7, 31)), fim = new Date(Date.UTC(2026, 8, 25));
    while (d <= fim) { var w = d.getUTCDay(); if (w >= 1 && w <= 5) DIAS.push(d.toISOString().slice(0, 10)); d = new Date(d.getTime() + DIA); }
  })();

  var MOTIVOS_PARADO = [
    ["Direcionamento da liderança para execução", 34], ["Descanso entre atividades", 9], ["Término da atividade antecessora", 8],
    ["Raio de ação de içamento (munck, guindaste)", 6], ["Pit stop", 5], ["Raio de ação de máquina", 4], ["Dúvida de execução / interferência", 5],
    ["Mais pessoas que a frente de serviço comporta", 7], ["Material / insumo / acessório", 9], ["Sobreposição de atividades na própria frente", 5],
    ["Direito de recusa (trabalho seguro)", 2], ["Máquina ou equipamento indisponível", 6]
  ];
  var MOTIVOS_TRANSITO = [["Material / insumo / acessório", 55], ["Água / banheiro", 18], ["Entre frentes de serviço", 11], ["Ferramenta", 9], ["Máquina / equipamento", 7]];
  function repartir(qtd, pesos) {
    var sw = pesos.reduce(function (s, p) { return s + p[1]; }, 0), r = {};
    for (var k = 0; k < qtd; k++) {
      var x = aleatorio() * sw, acc = 0;
      for (var j = 0; j < pesos.length; j++) { acc += pesos[j][1]; if (x <= acc) { r[pesos[j][0]] = (r[pesos[j][0]] || 0) + 1; break; } }
    }
    return Object.keys(r).map(function (m) { return { motivo: m, qtd: r[m] }; });
  }

  M.jornadasCampo = []; M.amostragens = [];
  DIAS.forEach(function (dia) {
    var sexta = new Date(dia + "T12:00:00Z").getUTCDay() === 5;
    FRENTES.forEach(function (f) {
      var chegada = variar(450, 0.012), inicio = chegada + variar(f.atraso, 0.35), fimManha = variar(f.fimManha, 0.012);
      var chegadaT = fimManha + variar(88, 0.12), inicioT = chegadaT + variar(8, 0.8), fimTarde = variar(f.fimTarde - (sexta ? 55 : 0), 0.012);
      var efetivo = Math.round(variar(f.efetivo, 0.1));
      M.jornadasCampo.push({ id: M.jornadasCampo.length + 1, projetoId: 1, data: dia, empresaId: f.empresaId, area: f.area, encarregado: f.encarregado, efetivo: efetivo,
        manha: { chegada: hhmm(chegada), inicio: hhmm(inicio), termino: hhmm(fimManha) }, tarde: { chegada: hhmm(chegadaT), inicio: hhmm(inicioT), termino: hhmm(fimTarde) },
        registradoPorId: 12, observacoes: "" });
      [570, 870].forEach(function (hora) {
        var obs = Math.max(6, Math.round(efetivo * variar(0.85, 0.1)));
        var trab = Math.round(obs * Math.min(0.9, variar(f.trab, 0.14))), tran = Math.round(obs * variar(0.1, 0.4));
        if (trab + tran > obs) tran = obs - trab;
        var par = obs - trab - tran;
        M.amostragens.push({ id: M.amostragens.length + 1, projetoId: 1, data: dia, hora: hhmm(hora), empresaId: f.empresaId, area: f.area, encarregado: f.encarregado,
          trabalhando: trab, transito: tran, parado: par, motivosParado: repartir(par, MOTIVOS_PARADO), motivosTransito: repartir(tran, MOTIVOS_TRANSITO), observadorId: 12 });
      });
    });
  });

  /* Paralisações (tipo: Efetivo = pessoas; Máquina/Equipamento = unidades) */
  function par(data, empresaId, area, tipo, recurso, qtd, ini, fim, motivo, resp, descricao) {
    return { projetoId: 1, data: data, empresaId: empresaId, area: area, tipo: tipo, recurso: recurso, quantidade: qtd, inicio: ini, termino: fim,
      motivo: motivo, responsabilidade: resp, descricao: descricao, registradoPorId: 12 };
  }
  M.paralisacoes = [
    par("2026-08-12", 6, "Terraplenagem", "Efetivo", "Equipe de terraplenagem", 16, "13:20", "16:40", "Chuva / condição climática", "Clima", "Chuva forte; frente paralisada até o fim do turno."),
    par("2026-08-12", 6, "Terraplenagem", "Máquina/Equipamento", "Escavadeira e rolo compactador", 3, "13:20", "16:40", "Chuva / condição climática", "Clima", "Equipamentos parados pela chuva."),
    par("2026-08-19", 1, "Moagem 210", "Efetivo", "Montadores de estrutura", 12, "08:10", "10:40", "Aguardando equipamento de içamento", "Contratada", "Guindaste de 250 t em manutenção corretiva."),
    par("2026-08-19", 1, "Moagem 210", "Máquina/Equipamento", "Guindaste 250 t", 1, "07:30", "16:30", "Quebra de máquina / equipamento", "Contratada", "Vazamento hidráulico no guindaste."),
    par("2026-08-26", 1, "Subestação 420", "Efetivo", "Eletricistas", 14, "07:40", "09:40", "Falta de liberação de área / permissão de trabalho", "Cliente", "Permissão de trabalho liberada às 09:40 pela operação."),
    par("2026-09-01", 1, "Flotação 310", "Efetivo", "Encanadores e soldadores", 10, "13:30", "16:30", "Falta de material", "Contratada", "Falta de eletrodos no almoxarifado da contratada."),
    par("2026-09-02", 6, "Utilidades 510", "Efetivo", "Armadores e carpinteiros", 20, "07:30", "11:30", "Falta de projeto / dúvida técnica", "Cliente", "Aguardando resultado da sondagem complementar (RSK-TN-2026-0003)."),
    par("2026-09-02", 6, "Utilidades 510", "Máquina/Equipamento", "Retroescavadeira", 1, "07:30", "11:30", "Falta de projeto / dúvida técnica", "Cliente", "Frente sem liberação de projeto."),
    par("2026-09-04", 1, "Utilidades 510", "Efetivo", "Montadores de estrutura", 18, "14:00", "16:40", "Interferência com a operação da planta", "Cliente", "Bloqueio de via para passagem de caminhões da operação."),
    par("2026-09-08", 6, "Terraplenagem", "Efetivo", "Equipe de terraplenagem", 18, "07:30", "10:30", "Chuva / condição climática", "Clima", "Chuva na primeira parte da manhã."),
    par("2026-09-08", 6, "Terraplenagem", "Máquina/Equipamento", "Escavadeira, rolo e caminhões basculantes", 5, "07:30", "10:30", "Chuva / condição climática", "Clima", "Equipamentos parados pela chuva."),
    par("2026-09-09", 1, "Moagem 210", "Efetivo", "Montadores mecânicos", 8, "09:00", "11:30", "Aguardando frente (atividade predecessora)", "Contratada", "Base do transportador sem cura concluída."),
    par("2026-09-10", 1, "Subestação 420", "Máquina/Equipamento", "Caminhão munck", 1, "13:10", "16:40", "Quebra de máquina / equipamento", "Contratada", "Pane elétrica no munck."),
    par("2026-09-11", 1, "Flotação 310", "Efetivo", "Encanadores e soldadores", 12, "07:30", "09:00", "Parada de segurança", "Contratada", "DDS extraordinário após quase acidente."),
    par("2026-09-15", 1, "Utilidades 510", "Efetivo", "Montadores de estrutura", 16, "07:40", "11:40", "Falta de material", "Cliente", "Chumbadores fornecidos pelo cliente não entregues."),
    par("2026-09-15", 1, "Utilidades 510", "Máquina/Equipamento", "Guindaste 90 t", 1, "07:40", "11:40", "Falta de material", "Cliente", "Guindaste mobilizado sem frente."),
    par("2026-09-16", 1, "Moagem 210", "Efetivo", "Montadores de estrutura", 10, "13:20", "16:30", "Aguardando equipamento de içamento", "Contratada", "Guindaste compartilhado com a frente do PR-03."),
    par("2026-09-17", 6, "Utilidades 510", "Efetivo", "Armadores e carpinteiros", 22, "13:15", "16:45", "Falta de projeto / dúvida técnica", "Cliente", "Revisão das armaduras das fundações F-20 a F-28."),
    par("2026-09-18", 1, "Subestação 420", "Efetivo", "Eletricistas", 12, "07:40", "10:10", "Falta de liberação de área / permissão de trabalho", "Cliente", "Área energizada da subestação existente sem bloqueio."),
    par("2026-09-21", 1, "Flotação 310", "Efetivo", "Encanadores e soldadores", 14, "07:30", "11:00", "Falta de material", "Contratada", "Spools com não conformidade (RNC-TN-2026-0004)."),
    par("2026-09-22", 6, "Terraplenagem", "Máquina/Equipamento", "Rolo compactador", 1, "07:30", "16:30", "Quebra de máquina / equipamento", "Contratada", "Rolo sem reposição no canteiro."),
    par("2026-09-23", 1, "Moagem 210", "Efetivo", "Pintores", 8, "07:30", "16:30", "Falta de liberação de área / permissão de trabalho", "Gerenciadora", "Plano de pintura sem aprovação da fiscalização."),
    par("2026-09-24", 1, "Utilidades 510", "Efetivo", "Montadores de estrutura", 18, "13:10", "15:40", "Interferência com a operação da planta", "Cliente", "Parada para manobra de carretas da operação."),
    par("2026-09-24", 6, "Utilidades 510", "Máquina/Equipamento", "Bomba de concreto", 1, "08:00", "12:00", "Terceiros (concreteira, concessionária)", "Terceiros", "Atraso do caminhão-betoneira da concreteira."),
    par("2026-09-25", 1, "Subestação 420", "Efetivo", "Eletricistas", 10, "13:10", "15:10", "Chuva / condição climática", "Clima", "Descarga atmosférica; trabalho externo suspenso.")
  ].map(function (p, k) { p.id = k + 1; return p; });

  /* Plano de recuperação já aberto na Central para a semana anterior (origem Produtividade) */
  if (M.acoes) {
    M.acoes.push({ id: M.acoes.reduce(function (m, a) { return Math.max(m, a.id); }, 0) + 1, projetoId: 1, origem: "Produtividade", origemRef: "PRD-2026-S38-01", item: "1",
      grupo: "Produtividade", tipo: "Ação", assunto: "Recuperar o ritmo da montagem de tubulação da flotação",
      descricao: "Fator de produtividade acima de 1,10 e aderência abaixo de 80% nas últimas 4 semanas: reforçar a frente de soldagem e liberar spools com antecedência.",
      solicitanteId: 3, responsavelId: 5, prevista: "2026-10-09", replanejada: null, conclusao: null });
  }
})(window.MOCK);

/* ---------------- EAP (estrutura analítica do projeto, avanço físico) ----------------
   Área (nível 1) > subárea (nível 2) > pacote (nível 3). Só os pacotes têm peso, datas
   da linha de base, critério de medição e avanço; áreas e subáreas são somadas pela api.
     peso       % do projeto (os pacotes somam 100; as áreas fecham com avancoAreas)
     previsto   % previsto na data de corte, vindo do cronograma da linha de base (P6/MSP)
     tipo       "Trabalho" (pacote de trabalho, mede avanço) ou "Planejamento" (pacote de
                planejamento: peso reservado, sem medição, desdobrado em ondas sucessivas)
     criterio   Etapas (etapas com peso e % concluído), Unidades (executado ÷ quantidade),
                Marco 0/100, Marco 50/50 (estado) ou Percentual estimado (estimadoPct)
   O real de cada pacote é sempre calculado (GI.regras.avancoPacoteEap), nunca gravado.
   Cenário: previsto 65,7% e real 61,8% (fecha com a Curva S e com o avanço por área). */
(function (M) {
  var MODELOS = {};
  ((M.parametros && M.parametros.eap && M.parametros.eap.modelosEtapas) || []).forEach(function (m) { MODELOS[m.id] = m; });
  function etapas(modelo, pcts) {
    return MODELOS[modelo].etapas.map(function (e, i) { return { nome: e.nome, peso: e.peso, pct: pcts[i] || 0 }; });
  }
  var id = 0, lista = [];
  function no(codigo, descricao) { lista.push({ id: ++id, projetoId: 1, codigo: codigo, descricao: descricao, nivel: codigo.split(".").length }); }
  function pacote(codigo, descricao, o) {
    var x = { id: ++id, projetoId: 1, codigo: codigo, descricao: descricao, nivel: 3, tipo: o.tipo || "Trabalho", criterio: o.criterio || null,
      modelo: o.modelo || null, etapas: o.modelo ? etapas(o.modelo, o.pcts || []) : null,
      unidade: o.unidade || null, quantidade: o.quantidade == null ? null : o.quantidade, executado: o.executado == null ? null : o.executado,
      estado: o.estado || null, estimadoPct: o.estimadoPct == null ? null : o.estimadoPct,
      peso: o.peso, previsto: o.previsto, inicio: o.inicio, termino: o.termino, empresaId: o.empresaId || null, responsavelId: o.responsavelId,
      eacCodigo: o.eac || null, entregavel: o.entregavel || "", aceitacao: o.aceitacao || "", medicoes: o.medicoes || [] };
    if (o.criterio === "Unidades") x.modelo = null;
    lista.push(x);
  }

  no("1", "Engenharia");
  no("1.1", "Projeto básico");
  pacote("1.1.1", "Projeto básico de processo", { criterio: "Etapas", modelo: "engenharia", pcts: [100, 100, 100], peso: 2, previsto: 100,
    inicio: "2026-01-05", termino: "2026-03-13", empresaId: 5, responsavelId: 6, eac: "1.1.1",
    entregavel: "Fluxogramas de processo, balanços de massa e folhas de dados aprovados", aceitacao: "Documentos em Rev 0 aprovados pelo cliente" });
  pacote("1.1.2", "Estudos de interferências e topografia", { criterio: "Marco 0/100", estado: "Concluído", peso: 1, previsto: 100,
    inicio: "2026-01-05", termino: "2026-02-13", empresaId: 5, responsavelId: 6, eac: "1.1.2",
    entregavel: "Levantamento planialtimétrico e cadastro de interferências", aceitacao: "Relatório aceito pela engenharia do cliente" });
  no("1.2", "Projeto detalhado");
  pacote("1.2.1", "Engenharia civil e estrutural", { criterio: "Etapas", modelo: "engenharia", pcts: [100, 100, 100], peso: 4, previsto: 100,
    inicio: "2026-02-02", termino: "2026-08-28", empresaId: 5, responsavelId: 6, eac: "1.2.1",
    entregavel: "Desenhos de fôrma, armação e estruturas metálicas para construção", aceitacao: "Lista de documentos 100% em Rev 0" });
  pacote("1.2.2", "Engenharia mecânica e de tubulação", { criterio: "Etapas", modelo: "engenharia", pcts: [100, 100, 80], peso: 4, previsto: 98,
    inicio: "2026-02-02", termino: "2026-10-02", empresaId: 5, responsavelId: 6, eac: "1.2.2",
    entregavel: "Arranjos, isométricos e listas de materiais de tubulação", aceitacao: "Lista de documentos 100% em Rev 0" });
  pacote("1.2.3", "Engenharia elétrica e de automação", { criterio: "Etapas", modelo: "engenharia", pcts: [100, 100, 70], peso: 3.5, previsto: 96,
    inicio: "2026-02-16", termino: "2026-10-16", empresaId: 5, responsavelId: 6, eac: "1.2.3",
    entregavel: "Diagramas unifilares, listas de cabos e arquitetura de automação", aceitacao: "Lista de documentos 100% em Rev 0" });
  pacote("1.2.4", "Engenharia da estação de tratamento de efluentes", { criterio: "Etapas", modelo: "engenharia", pcts: [100, 100, 70], peso: 0.5, previsto: 84,
    inicio: "2026-05-25", termino: "2026-10-30", empresaId: 5, responsavelId: 6, eac: "1.1.1",
    entregavel: "Projeto da ETE para a licença de operação", aceitacao: "Projeto aprovado pelo órgão ambiental" });

  no("2", "Suprimentos");
  no("2.1", "Equipamentos mecânicos");
  var SUP = { criterio: "Etapas", modelo: "suprimentos", responsavelId: 7 };
  function sup(o) { return Object.assign({}, SUP, o); }
  pacote("2.1.1", "Moinho de bolas", sup({ pcts: [100, 100, 100, 100, 0], peso: 6, previsto: 100, inicio: "2026-01-19", termino: "2026-09-15", empresaId: 7, eac: "2.1.1",
    entregavel: "Moinho entregue na obra com data book", aceitacao: "Recebimento sem avarias e FAT aprovado",
    medicoes: [{ data: "2026-08-28", de: 70, para: 80, porId: 7, obs: "FAT concluído no fornecedor." }] }));
  pacote("2.1.2", "Britador cônico", sup({ pcts: [100, 100, 100, 100, 0], peso: 3, previsto: 80, inicio: "2026-02-02", termino: "2026-10-30", empresaId: 7, eac: "2.1.2",
    entregavel: "Britador entregue na obra", aceitacao: "Recebimento sem avarias" }));
  pacote("2.1.3", "Transportadores de correia", sup({ pcts: [100, 100, 100, 100, 100], peso: 3, previsto: 100, inicio: "2026-01-26", termino: "2026-08-14", empresaId: 4, eac: "2.1.3",
    entregavel: "Cinco transportadores entregues", aceitacao: "Recebimento sem avarias" }));
  pacote("2.1.4", "Bombas de polpa", sup({ pcts: [100, 100, 100, 0, 0], peso: 2, previsto: 80, inicio: "2026-03-02", termino: "2026-11-13", empresaId: 8, eac: "2.1.4",
    entregavel: "Oito bombas entregues", aceitacao: "Teste de desempenho no fornecedor aprovado" }));
  pacote("2.1.5", "Células de flotação", sup({ pcts: [100, 100, 100, 0, 0], peso: 3, previsto: 80, inicio: "2026-03-02", termino: "2026-11-27", empresaId: 12, eac: "2.1.5",
    entregavel: "Quatro células entregues", aceitacao: "Recebimento sem avarias" }));
  pacote("2.1.6", "Válvulas de processo", sup({ pcts: [100, 100, 100, 100, 100], peso: 1, previsto: 100, inicio: "2026-02-16", termino: "2026-07-31", empresaId: 3, eac: "2.1.6",
    entregavel: "Válvulas entregues com certificados", aceitacao: "Recebimento sem avarias" }));
  no("2.2", "Materiais elétricos e automação");
  pacote("2.2.1", "Transformadores de força", sup({ pcts: [100, 100, 100, 100, 0], peso: 3, previsto: 80, inicio: "2026-02-09", termino: "2026-10-23", empresaId: 2, eac: "2.2.1",
    entregavel: "Dois transformadores entregues", aceitacao: "Ensaios de rotina aprovados" }));
  pacote("2.2.2", "Painéis e CCMs", sup({ pcts: [100, 100, 100, 100, 50], peso: 3, previsto: 70, inicio: "2026-02-09", termino: "2026-11-06", empresaId: 9, eac: "2.2.2",
    entregavel: "Onze painéis e CCMs entregues", aceitacao: "TAF aprovado" }));
  pacote("2.2.3", "Cabos e bandejamento", sup({ pcts: [100, 100, 100, 0, 0], peso: 3, previsto: 70, inicio: "2026-03-02", termino: "2026-11-20", empresaId: 10, eac: "2.2.3",
    entregavel: "Cabos e bandejamento entregues", aceitacao: "Certificados de ensaio aprovados" }));
  pacote("2.2.4", "Instrumentação de campo", sup({ pcts: [100, 100, 100, 50, 0], peso: 2, previsto: 40, inicio: "2026-04-06", termino: "2026-12-18", empresaId: 11, eac: "2.2.4",
    entregavel: "Instrumentos entregues com certificados de calibração", aceitacao: "Certificados de calibração válidos" }));
  pacote("2.2.5", "Sistema digital de controle (SDCD)", sup({ pcts: [0, 0, 0, 0, 0], peso: 1, previsto: 20, inicio: "2026-06-01", termino: "2027-01-29", eac: "2.2.5",
    entregavel: "SDCD entregue e configurado", aceitacao: "TAF do SDCD aprovado" }));

  no("3", "Obras civis");
  no("3.1", "Movimento de terra");
  var CIV = { criterio: "Unidades", empresaId: 6, responsavelId: 11 };
  function civ(o) { return Object.assign({}, CIV, o); }
  pacote("3.1.1", "Terraplenagem", civ({ unidade: "m³", quantidade: 120000, executado: 120000, peso: 3, previsto: 100, inicio: "2026-02-02", termino: "2026-05-29", eac: "3.1.1",
    entregavel: "Plataformas na cota de projeto", aceitacao: "Ensaios de compactação aprovados" }));
  pacote("3.1.2", "Drenagem", civ({ unidade: "m", quantidade: 2400, executado: 2400, peso: 1, previsto: 100, inicio: "2026-03-02", termino: "2026-06-26", eac: "3.1.1",
    entregavel: "Rede de drenagem pluvial", aceitacao: "Teste de escoamento aprovado" }));
  no("3.2", "Fundações");
  pacote("3.2.1", "Fundações da moagem", civ({ unidade: "m³", quantidade: 1400, executado: 1260, peso: 3.5, previsto: 100, inicio: "2026-03-16", termino: "2026-09-11", eac: "3.1.2",
    entregavel: "Fundações da moagem, incluindo o reforço da F-12", aceitacao: "Relatórios de concretagem e ensaios de corpos de prova aprovados",
    medicoes: [{ data: "2026-09-18", de: 85, para: 90, porId: 11, obs: "Concretagem da F-12 reforçada; faltam as bases dos transportadores." }] }));
  pacote("3.2.2", "Fundações da flotação", civ({ unidade: "m³", quantidade: 1000, executado: 1000, peso: 2.5, previsto: 100, inicio: "2026-04-06", termino: "2026-08-28", eac: "3.1.2",
    entregavel: "Fundações da flotação", aceitacao: "Relatórios de concretagem aprovados" }));
  pacote("3.2.3", "Fundações da subestação e utilidades", civ({ unidade: "m³", quantidade: 800, executado: 680, peso: 2, previsto: 90, inicio: "2026-05-04", termino: "2026-10-09", eac: "3.1.2",
    entregavel: "Fundações da subestação 420 e da área de utilidades", aceitacao: "Relatórios de concretagem aprovados" }));
  no("3.3", "Estruturas e edificações");
  pacote("3.3.1", "Estruturas de concreto", civ({ unidade: "m³", quantidade: 6000, executado: 3300, peso: 7, previsto: 60, inicio: "2026-05-04", termino: "2027-01-15", eac: "3.1.3",
    entregavel: "Estruturas de concreto das áreas de processo", aceitacao: "Liberação da fiscalização por trecho" }));
  pacote("3.3.2", "Edificações e acabamentos", civ({ unidade: "m²", quantidade: 3500, executado: 875, peso: 4, previsto: 30, inicio: "2026-07-06", termino: "2027-02-26", eac: "3.1.4",
    entregavel: "Casas de painéis, salas de controle e casa de bombas", aceitacao: "Vistoria de acabamento aprovada" }));
  pacote("3.3.3", "Obras civis da estação de tratamento de efluentes", civ({ unidade: "m³", quantidade: 400, executado: 60, peso: 2, previsto: 15, inicio: "2026-08-03", termino: "2027-01-29", eac: "3.1.3",
    entregavel: "Tanques e bases da ETE", aceitacao: "Teste de estanqueidade dos tanques aprovado" }));

  no("4", "Montagem eletromecânica");
  no("4.1", "Estruturas metálicas");
  var MON = { empresaId: 1, responsavelId: 5 };
  function mon(o) { return Object.assign({}, MON, o); }
  pacote("4.1.1", "Estruturas metálicas das áreas de processo", mon({ criterio: "Unidades", unidade: "t", quantidade: 250, executado: 150, peso: 3, previsto: 70,
    inicio: "2026-05-04", termino: "2026-11-27", eac: "3.2.4", entregavel: "Estruturas montadas, torqueadas e pintadas", aceitacao: "Liberação topográfica e de torque" }));
  pacote("4.1.2", "Pipe racks PR-01 e PR-02", mon({ criterio: "Unidades", unidade: "t", quantidade: 100, executado: 50, peso: 2, previsto: 60,
    inicio: "2026-06-01", termino: "2026-12-11", eac: "3.2.4", entregavel: "Pipe racks montados", aceitacao: "Liberação topográfica e de torque" }));
  no("4.2", "Montagem mecânica de equipamentos");
  pacote("4.2.1", "Montagem mecânica da moagem", mon({ criterio: "Etapas", modelo: "montagem", pcts: [100, 25, 0, 0], peso: 4, previsto: 50,
    inicio: "2026-06-15", termino: "2026-12-18", eac: "3.2.1", entregavel: "Moinho, britador e transportadores montados", aceitacao: "Checklist de completação mecânica assinado" }));
  pacote("4.2.2", "Montagem mecânica da flotação", mon({ criterio: "Unidades", unidade: "t", quantidade: 600, executado: 120, peso: 3, previsto: 30,
    inicio: "2026-07-13", termino: "2027-01-29", eac: "3.2.1", entregavel: "Células, bombas e agitadores montados", aceitacao: "Checklist de completação mecânica assinado" }));
  no("4.3", "Tubulação");
  pacote("4.3.1", "Tubulação de processo", mon({ criterio: "Unidades", unidade: "m", quantidade: 8000, executado: 1600, peso: 4, previsto: 30,
    inicio: "2026-07-06", termino: "2027-02-12", eac: "3.2.2", entregavel: "Linhas de processo montadas e testadas", aceitacao: "Teste hidrostático aprovado por linha" }));
  pacote("4.3.2", "Tubulação de utilidades", mon({ criterio: "Unidades", unidade: "m", quantidade: 3000, executado: 300, peso: 2, previsto: 20,
    inicio: "2026-08-03", termino: "2027-02-12", eac: "3.2.2", entregavel: "Linhas de água, ar e reagentes", aceitacao: "Teste hidrostático aprovado por linha" }));
  no("4.4", "Elétrica e instrumentação");
  pacote("4.4.1", "Lançamento de cabos", mon({ criterio: "Unidades", unidade: "m", quantidade: 60000, executado: 15000, peso: 3, previsto: 30,
    inicio: "2026-07-06", termino: "2027-01-29", eac: "3.2.3", entregavel: "Cabos lançados, identificados e testados", aceitacao: "Teste de isolação aprovado" }));
  pacote("4.4.2", "Montagem de painéis e CCMs", mon({ criterio: "Etapas", modelo: "paineis", pcts: [100, 0, 0, 0], peso: 2, previsto: 30,
    inicio: "2026-07-20", termino: "2026-12-18", eac: "3.2.3", entregavel: "Painéis montados e energizáveis", aceitacao: "Checklist de liberação assinado" }));
  pacote("4.4.3", "Instrumentação", mon({ criterio: "Unidades", unidade: "un", quantidade: 160, executado: 12, peso: 2, previsto: 10,
    inicio: "2026-08-17", termino: "2027-02-26", eac: "3.2.3", entregavel: "Instrumentos montados e interligados", aceitacao: "Loop test aprovado",
    medicoes: [{ data: "2026-09-18", de: 5, para: 7.5, porId: 5, obs: "Instrumentos da moagem instalados." }] }));

  no("5", "Comissionamento");
  no("5.1", "Pré-comissionamento e comissionamento a frio");
  var COM = { criterio: "Etapas", modelo: "comissionamento", pcts: [0, 0], empresaId: 1, responsavelId: 8, previsto: 0 };
  function com(o) { return Object.assign({}, COM, o); }
  pacote("5.1.1", "Pré-comissionamento por sistema", com({ peso: 1.5, inicio: "2026-11-02", termino: "2027-02-12",
    entregavel: "Certificados de completação mecânica dos sistemas 210, 310, 420 e 510", aceitacao: "Sem punch list categoria A aberto" }));
  pacote("5.1.2", "Comissionamento a frio", com({ peso: 1.5, inicio: "2026-12-07", termino: "2027-03-12",
    entregavel: "Testes funcionais e de malha concluídos", aceitacao: "Certificados de prontidão para partida" }));
  no("5.2", "Comissionamento a quente e partida");
  pacote("5.2.1", "Partida e operação assistida", { tipo: "Planejamento", peso: 1.2, previsto: 0, inicio: "2027-02-15", termino: "2027-04-16", empresaId: 1, responsavelId: 8,
    entregavel: "Planta em operação assistida", aceitacao: "Aceite provisório do cliente" });
  pacote("5.2.2", "Comissionamento a quente da moagem", com({ peso: 0.8, inicio: "2027-01-18", termino: "2027-03-05",
    entregavel: "Moagem operando com carga", aceitacao: "Teste de desempenho da moagem aprovado" }));

  M.eap = lista;

  /* Revisões da EAP (Rev 0 = linha de base). Estrutura e pesos só mudam por revisão, a partir de SM aprovada com impacto em escopo. */
  M.eapRevisoes = [
    { id: 1, projetoId: 1, revisao: 0, data: "2026-01-05", pacotes: 35, smRef: null, aprovadoPorId: 2, alteracao: "Linha de base",
      justificativa: "Linha de base aprovada no gate de investimento, com pesos por HH orçadas." },
    { id: 2, projetoId: 1, revisao: 1, data: "2026-05-18", pacotes: 37, smRef: "SM-TN-2026-0001", aprovadoPorId: 2, alteracao: "Pacotes 1.2.4 e 3.3.3 incluídos; demais pesos reescalados",
      justificativa: "Inclusão do sistema de tratamento de efluentes." },
    { id: 3, projetoId: 1, revisao: 2, data: "2026-07-10", pacotes: 37, smRef: "SM-TN-2026-0002", aprovadoPorId: 2, alteracao: "Peso de 3.2.1 ajustado; demais pesos reescalados",
      justificativa: "Reforço das fundações por interferência no subsolo (F-12)." }
  ];

  /* Desdobramentos da revisão vigente (planejamento em ondas sucessivas): o peso sai do pacote de
     planejamento para o pacote de trabalho novo; o total do projeto não muda. */
  M.eapDesdobramentos = [
    { id: 1, projetoId: 1, revisao: 2, data: "2026-09-10", origem: "5.2.1", destino: "5.2.2", peso: 0.8, porId: 3,
      justificativa: "Plano de comissionamento da moagem detalhado; a partida e a operação assistida seguem como pacote de planejamento." }
  ];
})(window.MOCK);

/* Relato do período (02): um registro por tipo (Semanal ou Mensal) e período; semanal e mensal são
   registros distintos. pontos: ponto de atenção com o risco atrelado (natureza Ameaça ou Oportunidade),
   sem vínculo com o registro de riscos do 05. Alimenta a página 2 do Planejamento no relatório gerencial.
   Semana 39 e setembro ainda sem relato (períodos em andamento na data de referência). */
window.MOCK.relatos = [
  { id: 1, projetoId: 1, tipo: "Mensal", periodo: "2026-07", criadoPorId: 3, criadoEm: "2026-08-03T10:15", atualizadoPorId: 3, atualizadoEm: "2026-08-04T16:40",
    atividadesPeriodo: [
      "Concluída a fundação dos moinhos e liberada a base do britador para montagem.",
      "Recebida a matéria-prima das células de flotação e iniciada a fabricação.",
      "Terraplenagem da área da flotação concluída com 94% do volume previsto.",
      "Emitida a revisão 2 da EAP com a incorporação da SM-TN-2026-0002 (reforço das fundações)."
    ],
    atividadesProximo: [
      "Iniciar a montagem das estruturas metálicas do prédio da moagem.",
      "Concluir as bases de concreto da casa de bombas.",
      "Fechar a equalização técnica do SDCD (PC-14).",
      "Receber os painéis e CCMs da subestação unitária."
    ],
    pontos: [
      { descricao: "Fabricação do moinho de bolas com previsão de entrega após a data necessária na obra.",
        natureza: "Ameaça", risco: "Atraso na montagem mecânica da moagem e deslocamento do comissionamento a frio do sistema 210." },
      { descricao: "Chuvas de julho abaixo da média permitiram adiantar a drenagem da área da flotação.",
        natureza: "Oportunidade", risco: "Antecipar as fundações da flotação em até duas semanas, reduzindo a exposição ao período chuvoso." }
    ] },
  { id: 2, projetoId: 1, tipo: "Mensal", periodo: "2026-08", criadoPorId: 3, criadoEm: "2026-09-02T09:30", atualizadoPorId: 3, atualizadoEm: "2026-09-03T11:05",
    atividadesPeriodo: [
      "Montagem das estruturas metálicas do prédio da moagem com 45% de avanço.",
      "Entregues os transportadores de correia TC-210-01 a TC-210-05 dentro do prazo contratual.",
      "Recebidos os painéis e CCMs da subestação unitária; montagem elétrica iniciada.",
      "Equalização técnica do SDCD concluída com 3 propostas aprovadas."
    ],
    atividadesProximo: [
      "Concluir as estruturas do prédio da moagem e iniciar a montagem do pipe rack PR-03.",
      "Montar os transportadores no sistema 210 e iniciar o alinhamento.",
      "Concluir a equalização comercial e adjudicar o SDCD (PC-14).",
      "Energizar a subestação unitária para testes."
    ],
    pontos: [
      { descricao: "Moinho de bolas com FAT previsto para setembro e entrega ainda depois da data necessária na obra.",
        natureza: "Ameaça", risco: "Atraso de até 20 dias na montagem da moagem, com impacto no caminho crítico do comissionamento." },
      { descricao: "SM-TN-2026-0004 (pipe rack PR-03) aprovada e ainda fora do orçamento vigente.",
        natureza: "Ameaça", risco: "Execução sem cobertura orçamentária e divergência entre a EAC e o custo real do pacote de estruturas." },
      { descricao: "Fornecedor dos transformadores sinalizou possibilidade de antecipar o embarque.",
        natureza: "Oportunidade", risco: "Antecipar a energização da subestação e liberar mais cedo os testes a frio dos motores." }
    ] },
  { id: 3, projetoId: 1, tipo: "Semanal", periodo: "2026-S36", criadoPorId: 3, criadoEm: "2026-09-07T08:40", atualizadoPorId: 3, atualizadoEm: "2026-09-07T08:40",
    atividadesPeriodo: [
      "Içamento das tesouras da cobertura do prédio da moagem.",
      "Chegada das válvulas de processo (lote 1) com certificados em análise pela qualidade.",
      "Concretagem da base da bomba BP-210-01."
    ],
    atividadesProximo: [
      "Concluir o fechamento lateral do prédio da moagem.",
      "Iniciar a montagem dos transportadores TC-210-01 e TC-210-02.",
      "Receber a proposta final negociada do SDCD."
    ],
    pontos: [
      { descricao: "Guindaste de 250 t reservado só a partir de 21/09 para o içamento do moinho.",
        natureza: "Ameaça", risco: "Sobreposição com a janela de entrega do moinho e ociosidade da equipe de montagem mecânica." }
    ] },
  { id: 4, projetoId: 1, tipo: "Semanal", periodo: "2026-S37", criadoPorId: 3, criadoEm: "2026-09-14T08:25", atualizadoPorId: 3, atualizadoEm: "2026-09-14T17:10",
    atividadesPeriodo: [
      "Fechamento lateral do prédio da moagem concluído.",
      "Montagem dos transportadores TC-210-01 e TC-210-02 iniciada.",
      "Fabricação dos cabos de potência (lote 2) concluída na fábrica.",
      "Ocorrência de alto potencial em 12/09 no içamento de estruturas; frente paralisada por 1 dia para análise."
    ],
    atividadesProximo: [
      "Retomar o içamento com o plano de rigging revisado e a APR específica.",
      "Concluir o alinhamento dos transportadores TC-210-01 e TC-210-02.",
      "Iniciar a montagem do pipe rack PR-03.",
      "Acompanhar o FAT do britador cônico na fábrica."
    ],
    pontos: [
      { descricao: "Revisão do plano de rigging após a ocorrência de alto potencial de 12/09.",
        natureza: "Ameaça", risco: "Nova paralisação da frente de estruturas se o plano não for aprovado até 16/09, com perda de 3 a 5 dias." },
      { descricao: "Certificados de 6 válvulas divergentes no recebimento do lote 1.",
        natureza: "Ameaça", risco: "Bloqueio da montagem da tubulação da flotação até a substituição dos certificados pelo fornecedor." }
    ] },
  { id: 5, projetoId: 1, tipo: "Semanal", periodo: "2026-S38", criadoPorId: 3, criadoEm: "2026-09-21T08:30", atualizadoPorId: 3, atualizadoEm: "2026-09-21T16:20",
    atividadesPeriodo: [
      "Içamento das estruturas retomado com o plano de rigging revisado e aprovado.",
      "Alinhamento dos transportadores TC-210-01 e TC-210-02 concluído.",
      "Fabricação do britador cônico concluída; FAT agendado para 30/09.",
      "Montagem do pipe rack PR-03 iniciada (SM-TN-2026-0004).",
      "Equalização comercial do SDCD com 3 propostas; negociação em curso."
    ],
    atividadesProximo: [
      "Concluir a montagem das estruturas do pipe rack PR-03 (trechos 1 e 2).",
      "Montar os transportadores TC-210-03 a TC-210-05.",
      "Adjudicar o SDCD (PC-14) até 02/10.",
      "Iniciar os testes a frio dos painéis da subestação unitária.",
      "Mobilizar o guindaste de 250 t para o içamento do moinho."
    ],
    pontos: [
      { descricao: "Moinho de bolas (PED-2026-0001) com entrega prevista em 05/10, 20 dias depois da data necessária na obra.",
        natureza: "Ameaça", risco: "Deslocamento do comissionamento a frio da moagem (sistema 210) e da partida da planta." },
      { descricao: "Três SMs aguardando decisão do comitê, entre elas a troca da especificação dos cabos de média tensão.",
        natureza: "Ameaça", risco: "Compra dos cabos de média tensão sem especificação definida, com retrabalho e atraso na montagem elétrica." },
      { descricao: "Transformadores de força com previsão de entrega em 01/10, 9 dias antes da data contratual.",
        natureza: "Oportunidade", risco: "Antecipar a energização da subestação e os testes a frio dos motores da moagem." }
    ] }
];

/* Análise do período (02): comentário executivo e analítico por tipo (Semanal ou Mensal) e período,
   inserido e editado em modal no módulo. desvios: comentário por desvio negativo detectado (chave
   calculada pela api com os dados do período). Semana 39 e setembro sem análise (em andamento). */
window.MOCK.analisesPeriodo = (window.MOCK.analisesPeriodo || []).concat([
  { id: 1, projetoId: 1, modulo: "planejamento", tipo: "Semanal", periodo: "2026-S37", criadoPorId: 3, criadoEm: "2026-09-14T09:10", atualizadoPorId: 3, atualizadoEm: "2026-09-14T11:25",
    analise: "O projeto fecha a semana com 56,3% de avanço contra 59,1% previstos (SPI 0,95). O desvio vem estável há quatro semanas, concentrado na montagem eletromecânica e nas obras civis da flotação. A tendência aponta término em abril de 2027, um mês após a linha de base, e depende da recuperação da produtividade da montagem nas próximas três semanas.",
    desvios: [
      { chave: "avanco", indicador: "Avanço físico acumulado", comentario: "Atraso de 2,8 p.p. causado pela liberação tardia das frentes de montagem da moagem. Plano de recuperação com segundo turno a partir da S38." },
      { chave: "termino", indicador: "Término pela tendência", comentario: "Tendência de término em abr/27 por efeito do caminho crítico da montagem. Ação: resequenciar comissionamento a frio em paralelo." },
      { chave: "areas", indicador: "Avanço por área", comentario: "Montagem eletromecânica (-8 p.p.) e obras civis (-4 p.p.) concentram o desvio; engenharia e suprimentos em recuperação." },
      { chave: "produtividade", indicador: "Produtividade", comentario: "Fator de produtividade acima de 1,00 na Alfa Montagens por espera de material e retrabalho de solda. Ação de supervisão aberta." }
    ] },
  { id: 2, projetoId: 1, modulo: "planejamento", tipo: "Semanal", periodo: "2026-S38", criadoPorId: 3, criadoEm: "2026-09-21T09:05", atualizadoPorId: 3, atualizadoEm: "2026-09-21T15:30",
    analise: "Panorama: o projeto atinge 59,5% de avanço físico contra 61,8% previstos (SPI 0,96), com leve melhora sobre a semana anterior (SPI 0,95). A semana produziu 3,2 p.p. contra 2,7 p.p. planejados, primeiro resultado acima do plano em cinco semanas, efeito do segundo turno na montagem da moagem. Desempenho anterior: o desvio acumulado cresceu de forma contínua entre julho e agosto e estabilizou a partir da S36. Tendência: mantido o ritmo atual, o desvio cai para cerca de 1,5 p.p. até o fim de outubro, mas o término projetado segue em abril de 2027 enquanto a produtividade da montagem (FP 1,10 e aderência de 83,9%) não voltar à faixa de meta.",
    desvios: [
      { chave: "avanco", indicador: "Avanço físico acumulado", comentario: "Desvio de 2,3 p.p. (SPI 0,96), em redução pela primeira vez no mês. Causa: frentes de montagem liberadas com atraso. Ação: segundo turno mantido até a S42." },
      { chave: "termino", indicador: "Término pela tendência", comentario: "Término tendencial em abr/27 (LB mar/27). Recuperação depende de antecipar o comissionamento a frio da moagem; proposta em análise na SM-TN-2026-0005." },
      { chave: "areas", indicador: "Avanço por área", comentario: "Montagem eletromecânica segue com -8 p.p. e obras civis com -4 p.p.; demais áreas dentro de 2 p.p. Reforço de equipe de solda aprovado para a S39." },
      { chave: "produtividade", indicador: "Produtividade", comentario: "SPI de quantidades 0,89, FP 1,10 e 55,2% de pessoas trabalhando (meta 60%). Principal causa: espera de material no campo. Ação: kit de materiais por frente liberado no dia anterior." }
    ] },
  { id: 3, projetoId: 1, modulo: "planejamento", tipo: "Mensal", periodo: "2026-08", criadoPorId: 3, criadoEm: "2026-09-02T10:00", atualizadoPorId: 2, atualizadoEm: "2026-09-03T17:20",
    analise: "Agosto fecha com 50,3% de avanço físico contra 54,0% previstos (SPI 0,93). O mês produziu 11,3 p.p. contra 11,9 p.p. planejados, terceiro mês seguido abaixo do plano, porém com a menor diferença do trimestre. O desvio acumulado se origina da liberação tardia das frentes de montagem e da interferência no subsolo das fundações da flotação. Tendência: com o segundo turno e o reforço de soldadores, a projeção indica recuperação gradual a partir de outubro, com término em abril de 2027 caso a produtividade não atinja a meta até novembro.",
    desvios: [
      { chave: "avanco", indicador: "Avanço físico acumulado", comentario: "Desvio de 3,7 p.p. concentrado na montagem. Plano de recuperação aprovado em reunião de 28/08 com segundo turno a partir de setembro." },
      { chave: "avanco_periodo", indicador: "Avanço no período", comentario: "Mês com 0,6 p.p. abaixo do plano por chuvas atípicas na segunda quinzena e parada de 3 dias para interferência no subsolo." },
      { chave: "termino", indicador: "Término pela tendência", comentario: "Término tendencial em abr/27. Recuperação exige produtividade da montagem de volta a FP 1,00 até novembro." },
      { chave: "areas", indicador: "Avanço por área", comentario: "Montagem (-8 p.p.) e obras civis (-4 p.p.) respondem por mais de 80% do desvio ponderado do projeto." },
      { chave: "produtividade", indicador: "Produtividade", comentario: "FP 1,11 e aderência semanal de 84,7%. Retrabalho de solda e espera de material são as causas principais; auditoria de campo programada." }
    ] }
]);
