/* ==========================================================================
   mock-portfolio.js | Dados fictícios dos projetos 2 e 3 do portfólio, em todos
   os módulos (carregado depois dos mocks de cada módulo; acrescenta registros às
   mesmas coleções, com ids e códigos próprios).

   Projeto 2  TN-2026-021  Construção de uma nova caldeira de biomassa (R$ 18,2 mi)
              Fase: suprimentos da caldeira (LLI) em fabricação e fundações em curso.
              Cenário: avanço 32,2% x 36,0% (SPI 0,89), CPI 1,02, caldeira com folga
              negativa (pedido crítico) e término pela tendência um mês após a LB.
   Projeto 3  TN-2026-027  Construção de uma nova torre de resfriamento (R$ 7,4 mi)
              Fase: torre (EPC) em fabricação e bacia de água fria em escavação.
              Cenário: avanço 34,1% x 33,2% (SPI 1,03), CPI 0,93 com sobrecusto
              projetado na bacia (escavação em rocha, SM aguardando comitê).
   Também grava as análises do período do portfólio (projetoId null).
   Numeração própria de cada projeto (padrões CB-2026 e TR-2026) para as listas
   consolidadas do portfólio não terem códigos repetidos.
   ========================================================================== */
window.MOCK = window.MOCK || {};

(function (M) {
  "use strict";

  function proximo(nome) { return (M[nome] || []).reduce(function (m, x) { return Math.max(m, Number(x.id) || 0); }, 0) + 1; }
  function incluir(nome, reg) { M[nome] = M[nome] || []; if (reg.id == null) reg.id = proximo(nome); M[nome].push(reg); return reg; }
  function mi(v) { return Math.round(v * 100000000); }   /* R$ milhões -> centavos */

  /* ======================================================================
     02 Planejamento: Curva S física, avanço por área e sistemas
     ====================================================================== */
  incluir("curvaFisica", { projetoId: 2, corte: "2026-09",
    meses:    ["2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10", "2026-11", "2026-12", "2027-01", "2027-02", "2027-03", "2027-04", "2027-05", "2027-06", "2027-07"],
    baseline: [1.5, 4.0, 8.0, 13.5, 20.0, 27.5, 36.0, 45.0, 54.5, 64.0, 73.0, 81.0, 88.0, 94.0, 98.0, 100, 100],
    real:     [1.2, 3.4, 6.8, 11.6, 17.5, 24.3, 32.2, null, null, null, null, null, null, null, null, null, null],
    tendencia:[null, null, null, null, null, null, 32.2, 40.0, 48.5, 57.5, 66.5, 75.0, 82.5, 89.0, 94.0, 97.8, 100] });
  incluir("curvaFisica", { projetoId: 3, corte: "2026-09",
    meses:    ["2026-06", "2026-07", "2026-08", "2026-09", "2026-10", "2026-11", "2026-12", "2027-01", "2027-02", "2027-03"],
    baseline: [3.0, 9.0, 18.0, 33.2, 47.0, 62.0, 77.0, 90.0, 100, 100],
    real:     [3.1, 9.4, 18.6, 34.1, null, null, null, null, null, null],
    tendencia:[null, null, null, 34.1, 48.5, 63.5, 78.5, 91.5, 100, 100] });

  /* Avanço por área na data de corte (fecha com a EAP e com a curva) */
  [[2, "Engenharia", 12, 97.9, 96.3], [2, "Suprimentos", 40, 42.8, 35.7], [2, "Obras civis", 18, 36.1, 32.3], [2, "Montagem eletromecânica", 25, 2.4, 2.4], [2, "Comissionamento", 5, 0, 0],
   [3, "Engenharia", 10, 95.5, 96.4], [3, "Fornecimento da torre e equipamentos", 45, 36.9, 37.7], [3, "Obras civis", 25, 28, 30.1], [3, "Montagem", 15, 0, 0], [3, "Comissionamento", 5, 0, 0]]
    .forEach(function (a) { incluir("avancoAreas", { projetoId: a[0], area: a[1], peso: a[2], previsto: a[3], real: a[4] }); });

  var SIS = {};
  [[2, "610", "Caldeira e queimador", "Geração de vapor"], [2, "620", "Alimentação de biomassa", "Geração de vapor"], [2, "630", "Tratamento de gases", "Meio ambiente"],
   [3, "710", "Torre de resfriamento", "Utilidades"], [3, "720", "Bombeamento de água de resfriamento", "Utilidades"]]
    .forEach(function (s) { SIS[s[1]] = incluir("sistemas", { projetoId: s[0], codigo: s[1], nome: s[2], area: s[3] }).id; });

  /* Punch list: a caldeira já tem pendências da liberação das fundações para a montagem */
  [
    { codigo: "PL-CB-2026-0001", sis: "610", subsistema: "Fundações", tag: "BS-610-01", disciplina: "Civil", categoria: "B", marco: "Completação mecânica", origem: "Walkdown",
      descricao: "Chumbadores da base BS-610-01 com rosca danificada em dois pontos.", empresaId: 17, responsavelId: 18, identificadoPorId: 17,
      abertura: "2026-08-24", prazo: "2026-09-11", situacao: "Fechado", verificadoPorId: 9, fechamento: "2026-09-09", evidencia: "foto-fechamento-cb-0001.jpg" },
    { codigo: "PL-CB-2026-0002", sis: "610", subsistema: "Fundações", tag: "BS-610-02", disciplina: "Civil", categoria: "A", marco: "Completação mecânica", origem: "Walkdown",
      descricao: "Cota de topo da base BS-610-02 8 mm abaixo do projeto; exige graute de correção antes do posicionamento do tubulão.", empresaId: 17, responsavelId: 18, identificadoPorId: 17,
      abertura: "2026-09-02", prazo: "2026-09-18", situacao: "Em tratamento", verificadoPorId: null, fechamento: null, evidencia: null },
    { codigo: "PL-CB-2026-0003", sis: "620", subsistema: "Silo", tag: "SL-620-01", disciplina: "Civil", categoria: "C", marco: "Aceite provisório", origem: "Inspeção da fiscalização",
      descricao: "Acabamento da face externa do anel do silo com falhas de concretagem superficiais.", empresaId: 17, responsavelId: 18, identificadoPorId: 9,
      abertura: "2026-09-10", prazo: "2026-10-09", situacao: "Aberto", verificadoPorId: null, fechamento: null, evidencia: null },
    { codigo: "PL-CB-2026-0004", sis: "610", subsistema: "Estruturas", tag: "EM-610-03", disciplina: "Estruturas", categoria: "B", marco: "Completação mecânica", origem: "Walkdown",
      descricao: "Torque dos parafusos da coluna C-03 da estrutura da caldeira sem registro.", empresaId: 15, responsavelId: 17, identificadoPorId: 9,
      abertura: "2026-09-16", prazo: "2026-09-30", situacao: "Aguardando verificação", verificadoPorId: null, fechamento: null, evidencia: "registro-torque-c03.pdf" }
  ].forEach(function (p) {
    var x = Object.assign({ projetoId: 2 }, p); x.sistemaId = SIS[p.sis]; delete x.sis; incluir("punch", x);
  });

  /* 6WLA (mesma janela de 6 semanas do projeto 1) */
  function rest(id, tipo, descricao, responsavelId, necessaria, remocao) { return { id: id, tipo: tipo, descricao: descricao, responsavelId: responsavelId, necessaria: necessaria, remocao: remocao || null }; }
  [
    { projetoId: 2, codigo: "CB-LA-01", atividade: "Posicionamento do tubulão superior da caldeira", area: "Caldeira 610", disciplina: "Mecânica", empresaId: 15, responsavelId: 17, semanas: [0, 0, 0, 1, 1, 0],
      restricoes: [rest(1, "Material", "Chegada do tubulão superior (PED-2026-0011)", 7, "2026-10-16"), rest(2, "Equipamento", "Guindaste de 300 t mobilizado", 17, "2026-10-19")] },
    { projetoId: 2, codigo: "CB-LA-02", atividade: "Montagem das colunas e vigas da estrutura da caldeira", area: "Caldeira 610", disciplina: "Estruturas", empresaId: 15, responsavelId: 17, semanas: [1, 1, 1, 1, 0, 0],
      restricoes: [rest(1, "Frente", "Correção da cota da base BS-610-02 (PL-CB-2026-0002)", 18, "2026-09-25"), rest(2, "Projeto", "Revisão 2 dos desenhos de ligação", 6, "2026-09-22", "2026-09-21")] },
    { projetoId: 2, codigo: "CB-LA-03", atividade: "Concretagem do anel e das paredes do silo de biomassa", area: "Alimentação 620", disciplina: "Civil", empresaId: 17, responsavelId: 18, semanas: [1, 1, 0, 0, 0, 0],
      restricoes: [rest(1, "Material", "Fôrma deslizante liberada pela locadora", 18, "2026-09-26", "2026-09-24")] },
    { projetoId: 2, codigo: "CB-LA-04", atividade: "Bases do precipitador eletrostático", area: "Tratamento de gases 630", disciplina: "Civil", empresaId: 17, responsavelId: 18, semanas: [0, 1, 1, 1, 0, 0],
      restricoes: [rest(1, "Projeto", "Cargas do precipitador certificadas pelo fornecedor (PED-2026-0013)", 7, "2026-09-30"), rest(2, "Licença", "Autorização de supressão da faixa leste", 4, "2026-10-02")] },
    { projetoId: 2, codigo: "CB-LA-05", atividade: "Edificação da sala elétrica da caldeira", area: "Caldeira 610", disciplina: "Civil", empresaId: 17, responsavelId: 18, semanas: [0, 0, 0, 0, 1, 1],
      restricoes: [rest(1, "Projeto", "Projeto executivo da sala elétrica em Rev 0", 6, "2026-10-23")] },
    { projetoId: 3, codigo: "TR-LA-01", atividade: "Escavação da bacia de água fria com desmonte de rocha", area: "Bacia 710", disciplina: "Civil", empresaId: 17, responsavelId: 18, semanas: [1, 1, 1, 0, 0, 0],
      restricoes: [rest(1, "Licença", "Plano de fogo aprovado e licença do Exército para explosivos", 18, "2026-09-25"), rest(2, "Contrato", "Decisão da SM-TR-2026-0001 (escavação em rocha)", 15, "2026-10-02")] },
    { projetoId: 3, codigo: "TR-LA-02", atividade: "Concretagem do fundo da bacia (células 1 e 2)", area: "Bacia 710", disciplina: "Civil", empresaId: 17, responsavelId: 18, semanas: [0, 0, 1, 1, 1, 0],
      restricoes: [rest(1, "Frente", "Escavação liberada até a cota de fundo", 18, "2026-10-09")] },
    { projetoId: 3, codigo: "TR-LA-03", atividade: "Bases das bombas de água de resfriamento", area: "Casa de bombas 720", disciplina: "Civil", empresaId: 17, responsavelId: 18, semanas: [0, 0, 0, 1, 1, 0],
      restricoes: [rest(1, "Projeto", "Desenhos certificados das bombas (PED-2026-0014)", 7, "2026-10-09", "2026-09-18")] },
    { projetoId: 3, codigo: "TR-LA-04", atividade: "Recebimento e inspeção dos perfis de PRFV da torre", area: "Torre 710", disciplina: "Mecânica", empresaId: 16, responsavelId: 7, semanas: [0, 0, 0, 0, 1, 1],
      restricoes: [rest(1, "Logística", "Área de armazenagem coberta preparada", 18, "2026-10-26")] }
  ].forEach(function (a) { incluir("lookahead", a); });

  /* Programação semanal (S38) */
  function dias(prev, dia) {
    var d = {};
    ["seg", "ter", "qua", "qui", "sex", "sab"].forEach(function (n, i) { d[n] = { prev: prev[i] || 0, dia: (dia || [])[i] || 0, noite: 0 }; });
    return d;
  }
  incluir("programacoes", { projetoId: 2, semana: "2026-S38", inicio: "2026-09-14", fim: "2026-09-19", situacao: "Publicada", aprovacaoRealizado: "Aprovado", elaboradaPorId: 16, aprovadaPorId: 14,
    atividades: [
      { item: 1, idExclusiva: "CB-LA-03", atividade: "Armação e fôrma do anel do silo", local: "Alimentação 620", empresaId: 17, fiscalId: 12, encarregado: "Nilton Prado", unidade: "t",
        dias: dias([2, 2, 2, 2, 2, 0], [2, 1.5, 2, 2, 1.5, 0]), observacoes: "", comentarios: "" },
      { item: 2, idExclusiva: "", atividade: "Concretagem dos blocos de estacas B-21 a B-26", local: "Caldeira 610", empresaId: 17, fiscalId: 9, encarregado: "Nilton Prado", unidade: "m³",
        dias: dias([30, 30, 30, 30, 30, 15], [30, 30, 0, 30, 30, 15]), observacoes: "Chuva na quarta-feira.", comentarios: "" },
      { item: 3, idExclusiva: "CB-LA-02", atividade: "Montagem das colunas C-01 a C-06", local: "Caldeira 610", empresaId: 15, fiscalId: 12, encarregado: "Hélio Barros", unidade: "t",
        dias: dias([5, 5, 5, 5, 5, 0], [4, 5, 3, 0, 4, 0]), observacoes: "Base BS-610-02 sem liberação.", comentarios: "Restrição da cota identificada tarde no 6WLA." },
      { item: 4, idExclusiva: "", atividade: "Drenagem da área do pátio de biomassa", local: "Alimentação 620", empresaId: 17, fiscalId: 9, encarregado: "Nilton Prado", unidade: "m",
        dias: dias([40, 40, 40, 40, 40, 0], [40, 42, 20, 40, 40, 0]), observacoes: "", comentarios: "" }
    ] });
  incluir("programacoes", { projetoId: 3, semana: "2026-S38", inicio: "2026-09-14", fim: "2026-09-19", situacao: "Publicada", aprovacaoRealizado: "Aprovado", elaboradaPorId: 16, aprovadaPorId: 15,
    atividades: [
      { item: 1, idExclusiva: "TR-LA-01", atividade: "Escavação da célula 1 da bacia", local: "Bacia 710", empresaId: 17, fiscalId: 12, encarregado: "Joel Ramos", unidade: "m³",
        dias: dias([60, 60, 60, 60, 60, 30], [60, 55, 40, 60, 62, 30]), observacoes: "Rocha a partir da cota 2,1 m.", comentarios: "" },
      { item: 2, idExclusiva: "", atividade: "Acesso e plataforma da casa de bombas", local: "Casa de bombas 720", empresaId: 17, fiscalId: 12, encarregado: "Joel Ramos", unidade: "m²",
        dias: dias([120, 120, 120, 0, 0, 0], [120, 120, 130, 0, 0, 0]), observacoes: "", comentarios: "" },
      { item: 3, idExclusiva: "", atividade: "Lastro de concreto magro da célula 1", local: "Bacia 710", empresaId: 17, fiscalId: 9, encarregado: "Joel Ramos", unidade: "m³",
        dias: dias([0, 0, 0, 12, 12, 0], [0, 0, 0, 0, 12, 0]), observacoes: "Frente liberada só na sexta.", comentarios: "" }
    ] });

  /* ======================================================================
     02 Planejamento: Produtividade (quantidades, horas efetivas e paralisações)
     Mesmas regras do projeto 1 (semente fixa própria)
     ====================================================================== */
  var semente = 20260930;
  function aleatorio() { semente = (semente * 1103515245 + 12345) % 2147483648; return semente / 2147483648; }
  function variar(base, amplitude) { return base * (1 + (aleatorio() * 2 - 1) * amplitude); }
  var DIA = 86400000;
  function inicioSemana(r) {
    var m = /^(\d{4})-S(\d{2})$/.exec(r), ano = Number(m[1]), n = Number(m[2]);
    var jan4 = new Date(Date.UTC(ano, 0, 4));
    return new Date(jan4.getTime() - ((jan4.getUTCDay() || 7) - 1) * DIA + (n - 1) * 7 * DIA);
  }
  function rotuloSemana(d) {
    var t = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
    t.setUTCDate(t.getUTCDate() + 4 - (t.getUTCDay() || 7));
    var ano = t.getUTCFullYear(), n = Math.ceil(((t - Date.UTC(ano, 0, 1)) / DIA + 1) / 7);
    return ano + "-S" + (n < 10 ? "0" : "") + n;
  }
  function semanas(ini, fim) {
    var l = [], d = inicioSemana(ini), f = inicioSemana(fim);
    while (d <= f) { l.push(rotuloSemana(d)); d = new Date(d.getTime() + 7 * DIA); }
    return l;
  }
  function distribuir(total, n, casas) {
    var f = Math.pow(10, casas), u = Math.round(total * f), w = [];
    for (var k = 0; k < n; k++) { var x = (k + 0.5) / n; w.push(x < 0.2 ? 0.2 + 4 * x : x > 0.8 ? 0.2 + 4 * (1 - x) : 1); }
    var sw = w.reduce(function (s, x) { return s + x; }, 0), ex = w.map(function (x) { return u * x / sw; }), b = ex.map(Math.floor);
    var falta = u - b.reduce(function (s, x) { return s + x; }, 0);
    ex.map(function (x, k) { return { k: k, r: x - b[k] }; }).sort(function (a, c) { return c.r - a.r || a.k - c.k; }).slice(0, falta).forEach(function (o) { b[o.k] += 1; });
    return b.map(function (x) { return x / f; });
  }
  var CORTE = "2026-S39";
  [
    { projetoId: 2, codigo: "CB-QTD-01", empresaId: 17, grupo: "Concreto", tipo: "Concreto estrutural (lançamento)", disciplina: "Civil", unidade: "m³", casas: 0, total: 1450, indiceHH: 3.4,
      ini: "2026-S16", fim: "2026-S46", fatorReal: 0.9, pf: 1.06, aprov: "2026-04-10", aprovPor: 14 },
    { projetoId: 2, codigo: "CB-QTD-02", empresaId: 17, grupo: "Aço", tipo: "Aço de armação CA-50", disciplina: "Civil", unidade: "t", casas: 1, total: 132, indiceHH: 44,
      ini: "2026-S16", fim: "2026-S46", fatorReal: 0.88, pf: 1.08, aprov: "2026-04-10", aprovPor: 14 },
    { projetoId: 2, codigo: "CB-QTD-03", empresaId: 15, grupo: "Aço", tipo: "Estrutura metálica da caldeira", disciplina: "Estruturas", unidade: "t", casas: 1, total: 420, indiceHH: 40,
      ini: "2026-S35", fim: "2027-S04", fatorReal: 0.62, pf: 1.16, aprov: "2026-08-14", aprovPor: 14 },
    { projetoId: 3, codigo: "TR-QTD-01", empresaId: 17, grupo: "Concreto", tipo: "Concreto da bacia e da casa de bombas", disciplina: "Civil", unidade: "m³", casas: 0, total: 1030, indiceHH: 3.1,
      ini: "2026-S33", fim: "2026-S50", fatorReal: 1.04, pf: 0.97, aprov: "2026-07-24", aprovPor: 15 },
    { projetoId: 3, codigo: "TR-QTD-02", empresaId: 17, grupo: "Aço", tipo: "Aço de armação CA-50", disciplina: "Civil", unidade: "t", casas: 1, total: 78, indiceHH: 42,
      ini: "2026-S34", fim: "2026-S50", fatorReal: 1.02, pf: 0.99, aprov: "2026-07-24", aprovPor: 15, semApontar: true }
  ].forEach(function (b) {
    var sem = semanas(b.ini, b.fim), prev = distribuir(b.total, sem.length, b.casas);
    var f = Math.pow(10, b.casas), acumReal = 0, apont = [];
    sem.forEach(function (s, k) {
      if (s > CORTE || (s === CORTE && b.semApontar)) return;
      var real = Math.max(0, Math.round(prev[k] * b.fatorReal * variar(1, 0.12) * f) / f);
      real = Math.min(real, Math.round((b.total - acumReal) * f) / f);
      acumReal += real;
      apont.push({ semana: s, realizado: real, hh: Math.round(real * b.indiceHH * variar(b.pf, 0.08)), informadoEm: s === CORTE ? "2026-09-25" : null });
    });
    incluir("produtividadeItens", { projetoId: b.projetoId, codigo: b.codigo, empresaId: b.empresaId, grupo: b.grupo, tipo: b.tipo, disciplina: b.disciplina, unidade: b.unidade, casas: b.casas,
      total: b.total, indiceHH: b.indiceHH, inicio: b.ini, fim: b.fim, perfil: "curvaS", situacao: "Aprovada", revisao: 0, aprovadoPorId: b.aprovPor, aprovadoEm: b.aprov, observacoes: "",
      distribuicao: sem.map(function (s, k) { return { semana: s, previsto: prev[k] }; }), apontamentos: apont,
      revisoes: [{ rev: 0, data: b.aprov, porId: 16, total: b.total, smRef: null, justificativa: "Linha de base original do cronograma." }] });
  });

  /* Horas efetivas: frentes da caldeira e da torre acompanhadas pela fiscalização (S36 a S39) */
  var FRENTES = [
    { projetoId: 2, empresaId: 17, area: "Caldeira 610", encarregado: "Nilton Prado", efetivo: 30, atraso: 28, fimManha: 700, fimTarde: 1000, trab: 0.58 },
    { projetoId: 2, empresaId: 15, area: "Caldeira 610", encarregado: "Hélio Barros", efetivo: 18, atraso: 46, fimManha: 685, fimTarde: 985, trab: 0.46 },
    { projetoId: 3, empresaId: 17, area: "Bacia 710", encarregado: "Joel Ramos", efetivo: 24, atraso: 20, fimManha: 710, fimTarde: 1010, trab: 0.63 }
  ];
  function hhmm(min) { min = Math.round(min); return (min < 600 ? "0" : "") + Math.floor(min / 60) + ":" + ("0" + (min % 60)).slice(-2); }
  var DIAS_CAMPO = [];
  (function () {
    var d = new Date(Date.UTC(2026, 7, 31)), fim = new Date(Date.UTC(2026, 8, 25));
    while (d <= fim) { var w = d.getUTCDay(); if (w >= 1 && w <= 5) DIAS_CAMPO.push(d.toISOString().slice(0, 10)); d = new Date(d.getTime() + DIA); }
  })();
  var MOTIVOS_PARADO = [["Direcionamento da liderança para execução", 30], ["Descanso entre atividades", 9], ["Término da atividade antecessora", 10],
    ["Raio de ação de içamento (munck, guindaste)", 8], ["Pit stop", 5], ["Raio de ação de máquina", 5], ["Dúvida de execução / interferência", 6],
    ["Mais pessoas que a frente de serviço comporta", 6], ["Material / insumo / acessório", 11], ["Sobreposição de atividades na própria frente", 4],
    ["Direito de recusa (trabalho seguro)", 1], ["Máquina ou equipamento indisponível", 5]];
  var MOTIVOS_TRANSITO = [["Material / insumo / acessório", 50], ["Água / banheiro", 20], ["Entre frentes de serviço", 12], ["Ferramenta", 10], ["Máquina / equipamento", 8]];
  function repartir(qtd, pesos) {
    var sw = pesos.reduce(function (s, p) { return s + p[1]; }, 0), r = {};
    for (var k = 0; k < qtd; k++) {
      var x = aleatorio() * sw, acc = 0;
      for (var j = 0; j < pesos.length; j++) { acc += pesos[j][1]; if (x <= acc) { r[pesos[j][0]] = (r[pesos[j][0]] || 0) + 1; break; } }
    }
    return Object.keys(r).map(function (m) { return { motivo: m, qtd: r[m] }; });
  }
  DIAS_CAMPO.forEach(function (dia) {
    var sexta = new Date(dia + "T12:00:00Z").getUTCDay() === 5;
    FRENTES.forEach(function (f) {
      var chegada = variar(450, 0.012), inicio = chegada + variar(f.atraso, 0.35), fimManha = variar(f.fimManha, 0.012);
      var chegadaT = fimManha + variar(88, 0.12), inicioT = chegadaT + variar(8, 0.8), fimTarde = variar(f.fimTarde - (sexta ? 55 : 0), 0.012);
      var efetivo = Math.round(variar(f.efetivo, 0.1));
      incluir("jornadasCampo", { projetoId: f.projetoId, data: dia, empresaId: f.empresaId, area: f.area, encarregado: f.encarregado, efetivo: efetivo,
        manha: { chegada: hhmm(chegada), inicio: hhmm(inicio), termino: hhmm(fimManha) }, tarde: { chegada: hhmm(chegadaT), inicio: hhmm(inicioT), termino: hhmm(fimTarde) },
        registradoPorId: 12, observacoes: "" });
      [570, 870].forEach(function (hora) {
        var obs = Math.max(6, Math.round(efetivo * variar(0.85, 0.1)));
        var trab = Math.round(obs * Math.min(0.9, variar(f.trab, 0.14))), tran = Math.round(obs * variar(0.1, 0.4));
        if (trab + tran > obs) tran = obs - trab;
        var par = obs - trab - tran;
        incluir("amostragens", { projetoId: f.projetoId, data: dia, hora: hhmm(hora), empresaId: f.empresaId, area: f.area, encarregado: f.encarregado,
          trabalhando: trab, transito: tran, parado: par, motivosParado: repartir(par, MOTIVOS_PARADO), motivosTransito: repartir(tran, MOTIVOS_TRANSITO), observadorId: 12 });
      });
    });
  });
  [
    [2, "2026-09-02", 15, "Caldeira 610", "Efetivo", "Montadores de estrutura", 12, "07:40", "11:30", "Aguardando frente (atividade predecessora)", "Contratada", "Base BS-610-02 sem liberação (PL-CB-2026-0002)."],
    [2, "2026-09-09", 17, "Caldeira 610", "Efetivo", "Armadores e carpinteiros", 14, "13:10", "16:40", "Chuva / condição climática", "Clima", "Chuva forte à tarde."],
    [2, "2026-09-16", 15, "Caldeira 610", "Máquina/Equipamento", "Guindaste 90 t", 1, "07:30", "16:30", "Quebra de máquina / equipamento", "Contratada", "Falha no sistema de giro."],
    [2, "2026-09-17", 15, "Caldeira 610", "Efetivo", "Montadores de estrutura", 12, "07:30", "16:30", "Falta de projeto / dúvida técnica", "Cliente", "Aguardando a revisão 2 dos desenhos de ligação."],
    [3, "2026-09-08", 17, "Bacia 710", "Máquina/Equipamento", "Escavadeira 30 t", 2, "08:00", "16:30", "Falta de projeto / dúvida técnica", "Cliente", "Rocha na cota de escavação; aguardando definição do método de desmonte."],
    [3, "2026-09-15", 17, "Bacia 710", "Efetivo", "Equipe de escavação", 10, "13:00", "16:40", "Falta de liberação de área / permissão de trabalho", "Cliente", "Permissão para uso de rompedor hidráulico liberada no dia seguinte."]
  ].forEach(function (p) {
    incluir("paralisacoes", { projetoId: p[0], data: p[1], empresaId: p[2], area: p[3], tipo: p[4], recurso: p[5], quantidade: p[6], inicio: p[7], termino: p[8],
      motivo: p[9], responsabilidade: p[10], descricao: p[11], registradoPorId: 12 });
  });

  /* ======================================================================
     02 Planejamento: EAP (área > subárea > pacote), pesos em % do projeto
     ====================================================================== */
  var MODELOS = {};
  ((M.parametros && M.parametros.eap && M.parametros.eap.modelosEtapas) || []).forEach(function (m) { MODELOS[m.id] = m; });
  function etapas(modelo, pcts) { return MODELOS[modelo].etapas.map(function (e, i) { return { nome: e.nome, peso: e.peso, pct: pcts[i] || 0 }; }); }
  function eap(projetoId) {
    return {
      no: function (codigo, descricao) { incluir("eap", { projetoId: projetoId, codigo: codigo, descricao: descricao, nivel: codigo.split(".").length }); },
      pacote: function (codigo, descricao, o) {
        incluir("eap", { projetoId: projetoId, codigo: codigo, descricao: descricao, nivel: 3, tipo: o.tipo || "Trabalho", criterio: o.criterio || null,
          modelo: o.criterio === "Etapas" ? o.modelo : null, etapas: o.criterio === "Etapas" ? etapas(o.modelo, o.pcts || []) : null,
          unidade: o.unidade || null, quantidade: o.quantidade == null ? null : o.quantidade, executado: o.executado == null ? null : o.executado,
          estado: o.estado || null, estimadoPct: null, peso: o.peso, previsto: o.previsto, inicio: o.inicio, termino: o.termino,
          empresaId: o.empresaId || null, responsavelId: o.responsavelId, eacCodigo: o.eac || null, entregavel: o.entregavel || "", aceitacao: o.aceitacao || "", medicoes: [] });
      }
    };
  }
  var E2 = eap(2);
  E2.no("1", "Engenharia"); E2.no("1.1", "Engenharia básica e detalhada");
  E2.pacote("1.1.1", "Engenharia básica e de integração", { criterio: "Etapas", modelo: "engenharia", pcts: [100, 100, 100], peso: 3, previsto: 100, inicio: "2026-03-02", termino: "2026-05-29", empresaId: 5, responsavelId: 6, eac: "1.1.1",
    entregavel: "Fluxogramas, balanço térmico e folhas de dados da caldeira", aceitacao: "Documentos em Rev 0 aprovados pelo cliente" });
  E2.pacote("1.1.2", "Engenharia civil e estrutural", { criterio: "Etapas", modelo: "engenharia", pcts: [100, 100, 100], peso: 4, previsto: 100, inicio: "2026-03-16", termino: "2026-08-28", empresaId: 5, responsavelId: 6, eac: "1.1.2",
    entregavel: "Projetos de fundações, estruturas e edificações", aceitacao: "Lista de documentos 100% em Rev 0" });
  E2.pacote("1.1.3", "Engenharia eletromecânica e de automação", { criterio: "Etapas", modelo: "engenharia", pcts: [100, 100, 70], peso: 5, previsto: 95, inicio: "2026-03-30", termino: "2026-10-30", empresaId: 5, responsavelId: 6, eac: "1.1.3",
    entregavel: "Arranjos, isométricos, unifilares e arquitetura de automação", aceitacao: "Lista de documentos 100% em Rev 0" });
  E2.no("2", "Suprimentos"); E2.no("2.1", "Caldeira e periféricos");
  E2.pacote("2.1.1", "Caldeira aquatubular de biomassa 45 t/h", { criterio: "Etapas", modelo: "suprimentos", pcts: [100, 100, 50, 0, 0], peso: 22, previsto: 58, inicio: "2026-05-04", termino: "2027-01-15", empresaId: 14, responsavelId: 7, eac: "2.1.1",
    entregavel: "Caldeira entregue na obra com data book", aceitacao: "FAT dos componentes de pressão aprovado e recebimento sem avarias" });
  E2.pacote("2.1.2", "Sistema de alimentação e estocagem de biomassa", { criterio: "Etapas", modelo: "suprimentos", pcts: [100, 100, 30, 0, 0], peso: 6, previsto: 45, inicio: "2026-05-18", termino: "2027-01-22", empresaId: 4, responsavelId: 7, eac: "2.1.2",
    entregavel: "Transportadores, rosca dosadora e silo metálico entregues", aceitacao: "Recebimento sem avarias" });
  E2.pacote("2.1.3", "Precipitador eletrostático", { criterio: "Etapas", modelo: "suprimentos", pcts: [100, 100, 0, 0, 0], peso: 6, previsto: 25, inicio: "2026-06-15", termino: "2027-02-15", empresaId: 18, responsavelId: 7, eac: "2.1.3",
    entregavel: "Precipitador entregue com certificados de desempenho", aceitacao: "Recebimento sem avarias" });
  E2.no("2.2", "Balanço de planta");
  E2.pacote("2.2.1", "Bombas, ventiladores e válvulas", { criterio: "Etapas", modelo: "suprimentos", pcts: [0, 0, 0, 0, 0], peso: 3, previsto: 5, inicio: "2026-08-17", termino: "2027-02-26", responsavelId: 7, eac: "2.2.1",
    entregavel: "Bombas de alimentação, ventiladores e válvulas entregues", aceitacao: "Testes de desempenho no fornecedor aprovados" });
  E2.pacote("2.2.2", "Materiais elétricos e de automação", { criterio: "Etapas", modelo: "suprimentos", pcts: [0, 0, 0, 0, 0], peso: 3, previsto: 0, inicio: "2026-09-14", termino: "2027-03-12", responsavelId: 7, eac: "2.2.2",
    entregavel: "Painéis, cabos e instrumentos entregues", aceitacao: "Certificados de ensaio aprovados" });
  E2.no("3", "Obras civis"); E2.no("3.1", "Fundações e bases");
  E2.pacote("3.1.1", "Estaqueamento e fundações da caldeira", { criterio: "Unidades", unidade: "m³", quantidade: 900, executado: 565, peso: 8, previsto: 65, inicio: "2026-04-20", termino: "2026-11-13", empresaId: 17, responsavelId: 18, eac: "3.1.1",
    entregavel: "Estacas, blocos e bases da caldeira e do silo", aceitacao: "Relatórios de concretagem e prova de carga aprovados" });
  E2.pacote("3.1.2", "Bases de equipamentos e do silo", { criterio: "Unidades", unidade: "m³", quantidade: 300, executado: 60, peso: 4, previsto: 25, inicio: "2026-07-20", termino: "2026-12-18", empresaId: 17, responsavelId: 18, eac: "3.1.1",
    entregavel: "Bases do precipitador, ventiladores e silo", aceitacao: "Liberação topográfica" });
  E2.no("3.2", "Edificações");
  E2.pacote("3.2.1", "Casa de caldeira e sala elétrica", { criterio: "Unidades", unidade: "m²", quantidade: 1200, executado: 0, peso: 6, previsto: 5, inicio: "2026-09-07", termino: "2027-03-19", empresaId: 17, responsavelId: 18, eac: "3.1.2",
    entregavel: "Edificação da casa de caldeira e sala elétrica", aceitacao: "Vistoria de acabamento aprovada" });
  E2.no("4", "Montagem eletromecânica"); E2.no("4.1", "Montagem da caldeira");
  E2.pacote("4.1.1", "Estruturas e pré-montagem da caldeira", { criterio: "Unidades", unidade: "t", quantidade: 420, executado: 25, peso: 10, previsto: 6, inicio: "2026-08-31", termino: "2027-01-29", empresaId: 15, responsavelId: 17, eac: "3.2.1",
    entregavel: "Estrutura da caldeira montada e torqueada", aceitacao: "Liberação topográfica e de torque" });
  E2.pacote("4.1.2", "Montagem das partes de pressão e refratário", { criterio: "Etapas", modelo: "montagem", pcts: [0, 0, 0, 0], peso: 8, previsto: 0, inicio: "2026-11-16", termino: "2027-04-30", empresaId: 15, responsavelId: 17, eac: "3.2.1",
    entregavel: "Tubulões, paredes d'água e refratário montados", aceitacao: "Teste hidrostático da caldeira aprovado" });
  E2.no("4.2", "Tubulação, elétrica e instrumentação");
  E2.pacote("4.2.1", "Tubulação e isolamento térmico", { criterio: "Unidades", unidade: "m", quantidade: 2600, executado: 0, peso: 4, previsto: 0, inicio: "2026-12-07", termino: "2027-05-14", empresaId: 15, responsavelId: 17, eac: "3.2.2",
    entregavel: "Linhas de vapor, água de alimentação e drenos montadas", aceitacao: "Teste hidrostático por linha aprovado" });
  E2.pacote("4.2.2", "Elétrica e instrumentação", { criterio: "Unidades", unidade: "m", quantidade: 18000, executado: 0, peso: 3, previsto: 0, inicio: "2027-01-11", termino: "2027-05-28", empresaId: 15, responsavelId: 17, eac: "3.2.3",
    entregavel: "Cabos lançados e instrumentos interligados", aceitacao: "Loop test aprovado" });
  E2.no("5", "Comissionamento"); E2.no("5.1", "Comissionamento e partida");
  E2.pacote("5.1.1", "Comissionamento a frio e fervura química", { criterio: "Etapas", modelo: "comissionamento", pcts: [0, 0], peso: 2, previsto: 0, inicio: "2027-04-19", termino: "2027-06-04", empresaId: 15, responsavelId: 8, eac: "4.1.1",
    entregavel: "Testes funcionais, limpeza química e sopragem concluídos", aceitacao: "Certificado de prontidão para partida" });
  E2.pacote("5.1.2", "Partida e teste de desempenho", { tipo: "Planejamento", peso: 3, previsto: 0, inicio: "2027-06-07", termino: "2027-06-30", empresaId: 15, responsavelId: 8,
    entregavel: "Caldeira operando na carga nominal", aceitacao: "Teste de desempenho aprovado pelo cliente" });

  var E3 = eap(3);
  E3.no("1", "Engenharia"); E3.no("1.1", "Engenharia");
  E3.pacote("1.1.1", "Estudo térmico e engenharia básica", { criterio: "Etapas", modelo: "engenharia", pcts: [100, 100, 100], peso: 3, previsto: 100, inicio: "2026-06-01", termino: "2026-07-10", empresaId: 5, responsavelId: 6, eac: "1.1.1",
    entregavel: "Balanço térmico, dimensionamento das células e folhas de dados", aceitacao: "Documentos em Rev 0 aprovados pelo cliente" });
  E3.pacote("1.1.2", "Engenharia civil da bacia e das fundações", { criterio: "Etapas", modelo: "engenharia", pcts: [100, 100, 100], peso: 4, previsto: 100, inicio: "2026-06-08", termino: "2026-08-14", empresaId: 5, responsavelId: 6, eac: "1.1.2",
    entregavel: "Projetos da bacia de água fria, casa de bombas e bases", aceitacao: "Lista de documentos 100% em Rev 0" });
  E3.pacote("1.1.3", "Engenharia de tubulação, elétrica e automação", { criterio: "Etapas", modelo: "engenharia", pcts: [100, 100, 60], peso: 3, previsto: 85, inicio: "2026-06-22", termino: "2026-10-09", empresaId: 5, responsavelId: 6, eac: "1.1.3",
    entregavel: "Isométricos, unifilares e arquitetura de automação", aceitacao: "Lista de documentos 100% em Rev 0" });
  E3.no("2", "Fornecimento da torre e equipamentos"); E3.no("2.1", "Torre de resfriamento");
  E3.pacote("2.1.1", "Projeto e fabricação da torre em PRFV (3 células)", { criterio: "Etapas", modelo: "suprimentos", pcts: [100, 100, 50, 0, 0], peso: 30, previsto: 45, inicio: "2026-07-01", termino: "2026-12-11", empresaId: 16, responsavelId: 7, eac: "2.1.1",
    entregavel: "Estrutura, enchimento, eliminadores de gotas e ventiladores entregues", aceitacao: "Inspeção dos perfis e dos ventiladores aprovada" });
  E3.no("2.2", "Equipamentos");
  E3.pacote("2.2.1", "Bombas de água de resfriamento", { criterio: "Etapas", modelo: "suprimentos", pcts: [100, 100, 20, 0, 0], peso: 8, previsto: 30, inicio: "2026-08-10", termino: "2026-12-15", empresaId: 8, responsavelId: 7, eac: "2.1.2",
    entregavel: "Três bombas entregues", aceitacao: "Teste de desempenho no fornecedor aprovado" });
  E3.pacote("2.2.2", "Painéis e inversores dos ventiladores", { criterio: "Etapas", modelo: "suprimentos", pcts: [0, 0, 0, 0, 0], peso: 7, previsto: 10, inicio: "2026-09-01", termino: "2027-01-15", responsavelId: 7, eac: "2.1.3",
    entregavel: "Painéis e inversores entregues", aceitacao: "TAF aprovado" });
  E3.no("3", "Obras civis"); E3.no("3.1", "Bacia e fundações");
  E3.pacote("3.1.1", "Escavação e bacia de água fria", { criterio: "Unidades", unidade: "m³", quantidade: 850, executado: 200, peso: 15, previsto: 20, inicio: "2026-08-17", termino: "2026-12-04", empresaId: 17, responsavelId: 18, eac: "3.1.1",
    entregavel: "Bacia de água fria em concreto com as quatro células", aceitacao: "Teste de estanqueidade aprovado" });
  E3.pacote("3.1.2", "Casa de bombas e bases", { criterio: "Unidades", unidade: "m³", quantidade: 180, executado: 0, peso: 6, previsto: 0, inicio: "2026-10-05", termino: "2026-12-18", empresaId: 17, responsavelId: 18, eac: "3.1.2",
    entregavel: "Casa de bombas e bases dos equipamentos", aceitacao: "Liberação topográfica" });
  E3.pacote("3.1.3", "Terraplenagem e acessos", { criterio: "Marco 0/100", estado: "Concluído", peso: 4, previsto: 100, inicio: "2026-07-20", termino: "2026-08-14", empresaId: 17, responsavelId: 18, eac: "3.1.1",
    entregavel: "Plataforma e acessos da torre", aceitacao: "Ensaios de compactação aprovados" });
  E3.no("4", "Montagem"); E3.no("4.1", "Montagem da torre e interligações");
  E3.pacote("4.1.1", "Montagem da torre (estrutura, enchimento e ventiladores)", { criterio: "Etapas", modelo: "montagem", pcts: [0, 0, 0, 0], peso: 8, previsto: 0, inicio: "2026-11-02", termino: "2027-01-29", empresaId: 16, responsavelId: 7, eac: "2.1.1",
    entregavel: "Torre montada com ventiladores alinhados", aceitacao: "Checklist de completação mecânica assinado" });
  E3.pacote("4.1.2", "Tubulação de água de circulação", { criterio: "Unidades", unidade: "m", quantidade: 900, executado: 0, peso: 5, previsto: 0, inicio: "2026-11-16", termino: "2027-02-05", empresaId: 17, responsavelId: 18, eac: "3.2.1",
    entregavel: "Linhas de água fria e quente interligadas", aceitacao: "Teste hidrostático aprovado" });
  E3.pacote("4.1.3", "Elétrica e automação", { criterio: "Unidades", unidade: "m", quantidade: 6000, executado: 0, peso: 2, previsto: 0, inicio: "2026-12-07", termino: "2027-02-12", empresaId: 17, responsavelId: 18, eac: "3.2.2",
    entregavel: "Cabos lançados, painéis e inversores interligados", aceitacao: "Teste de isolação e loop test aprovados" });
  E3.no("5", "Comissionamento"); E3.no("5.1", "Comissionamento");
  E3.pacote("5.1.1", "Comissionamento e teste de desempenho térmico", { criterio: "Etapas", modelo: "comissionamento", pcts: [0, 0], peso: 5, previsto: 0, inicio: "2027-02-01", termino: "2027-02-26", empresaId: 16, responsavelId: 8, eac: "4.1.1",
    entregavel: "Torre operando com a aproximação de projeto", aceitacao: "Teste de desempenho térmico (CTI) aprovado" });

  incluir("eapRevisoes", { projetoId: 2, revisao: 0, data: "2026-03-02", pacotes: 17, smRef: null, aprovadoPorId: 14, alteracao: "Linha de base",
    justificativa: "Linha de base aprovada no gate de investimento, com pesos por valor agregado planejado." });
  incluir("eapRevisoes", { projetoId: 3, revisao: 0, data: "2026-06-01", pacotes: 13, smRef: null, aprovadoPorId: 15, alteracao: "Linha de base",
    justificativa: "Linha de base aprovada no gate de investimento, com pesos por HH e valor dos pacotes." });

  /* ======================================================================
     03 Gestão Financeira: EAC, curva financeira, reserva, revisões
     ====================================================================== */
  function eacNo(projetoId, codigo, descricao) { incluir("eac", { projetoId: projetoId, codigo: codigo, descricao: descricao, nivel: codigo.split(".").length }); }
  function eacItem(projetoId, codigo, descricao, o) {
    incluir("eac", { projetoId: projetoId, codigo: codigo, descricao: descricao, nivel: 3, tipoCusto: o.tipo, unidade: o.un || "vb", quantidade: o.qtd || 1,
      precoUnitario: Math.round(mi(o.base) / (o.qtd || 1)), capex: true, centroCusto: o.cc, responsavelId: o.resp,
      base: mi(o.base), remanejamento: 0, comprometido: mi(o.comp || 0), realizado: mi(o.real || 0), projecao: mi(o.proj == null ? o.base : o.proj) });
  }
  eacNo(2, "1", "Engenharia"); eacNo(2, "1.1", "Engenharia básica e detalhada");
  eacItem(2, "1.1.1", "Engenharia básica e de integração", { tipo: "Serviço", base: 0.45, comp: 0.44, real: 0.44, proj: 0.45, cc: "CC-4502-01", resp: 6 });
  eacItem(2, "1.1.2", "Engenharia detalhada civil e estrutural", { tipo: "Serviço", base: 0.40, comp: 0.40, real: 0.37, cc: "CC-4502-01", resp: 6 });
  eacItem(2, "1.1.3", "Engenharia detalhada eletromecânica e de automação", { tipo: "Serviço", base: 0.50, comp: 0.46, real: 0.42, cc: "CC-4502-01", resp: 6 });
  eacNo(2, "2", "Suprimentos"); eacNo(2, "2.1", "Caldeira e periféricos");
  eacItem(2, "2.1.1", "Caldeira aquatubular de biomassa 45 t/h", { tipo: "Equipamento", un: "un", base: 6.80, comp: 6.70, real: 2.72, proj: 6.70, cc: "CC-4502-02", resp: 7 });
  eacItem(2, "2.1.2", "Sistema de alimentação e estocagem de biomassa", { tipo: "Equipamento", base: 1.10, comp: 1.08, real: 0.33, proj: 1.10, cc: "CC-4502-02", resp: 7 });
  eacItem(2, "2.1.3", "Precipitador eletrostático", { tipo: "Equipamento", un: "un", base: 1.20, comp: 1.15, real: 0.24, proj: 1.20, cc: "CC-4502-02", resp: 7 });
  eacNo(2, "2.2", "Balanço de planta");
  eacItem(2, "2.2.1", "Bombas, ventiladores e válvulas", { tipo: "Equipamento", base: 0.55, cc: "CC-4502-02", resp: 7 });
  eacItem(2, "2.2.2", "Materiais elétricos e de automação", { tipo: "Material", base: 0.55, cc: "CC-4502-02", resp: 7 });
  eacNo(2, "3", "Construção e montagem"); eacNo(2, "3.1", "Obras civis");
  eacItem(2, "3.1.1", "Fundações e bases", { tipo: "Serviço", un: "m³", qtd: 1200, base: 1.30, comp: 1.25, real: 0.52, proj: 1.38, cc: "CC-4502-03", resp: 18 });
  eacItem(2, "3.1.2", "Edificação da casa de caldeira e sala elétrica", { tipo: "Serviço", un: "m²", qtd: 1200, base: 0.90, cc: "CC-4502-03", resp: 18 });
  eacNo(2, "3.2", "Montagem eletromecânica");
  eacItem(2, "3.2.1", "Montagem eletromecânica da caldeira", { tipo: "Serviço", un: "t", qtd: 520, base: 2.60, comp: 2.55, real: 0.26, proj: 2.60, cc: "CC-4502-04", resp: 17 });
  eacItem(2, "3.2.2", "Tubulação e isolamento térmico", { tipo: "Serviço", un: "m", qtd: 2600, base: 0.60, cc: "CC-4502-04", resp: 17 });
  eacItem(2, "3.2.3", "Elétrica e instrumentação", { tipo: "Serviço", un: "m", qtd: 18000, base: 0.45, cc: "CC-4502-04", resp: 17 });
  eacNo(2, "4", "Comissionamento e indiretos"); eacNo(2, "4.1", "Comissionamento e gerenciamento");
  eacItem(2, "4.1.1", "Comissionamento e partida", { tipo: "Serviço", base: 0.35, cc: "CC-4502-05", resp: 8 });
  eacItem(2, "4.1.2", "Gerenciamento e canteiro", { tipo: "Indireto", un: "mês", qtd: 16, base: 0.45, comp: 0.45, real: 0.45, cc: "CC-4502-05", resp: 14 });

  eacNo(3, "1", "Engenharia"); eacNo(3, "1.1", "Engenharia básica e detalhada");
  eacItem(3, "1.1.1", "Estudo térmico e engenharia básica", { tipo: "Serviço", base: 0.20, comp: 0.20, real: 0.21, proj: 0.22, cc: "CC-4503-01", resp: 6 });
  eacItem(3, "1.1.2", "Engenharia civil da bacia e das fundações", { tipo: "Serviço", base: 0.15, comp: 0.17, real: 0.16, proj: 0.15, cc: "CC-4503-01", resp: 6 });
  eacItem(3, "1.1.3", "Engenharia de tubulação, elétrica e automação", { tipo: "Serviço", base: 0.20, comp: 0.20, real: 0.19, cc: "CC-4503-01", resp: 6 });
  eacNo(3, "2", "Fornecimento da torre e equipamentos"); eacNo(3, "2.1", "Torre e equipamentos");
  eacItem(3, "2.1.1", "Torre de resfriamento em PRFV com 3 células (fornecimento e montagem)", { tipo: "Serviço", un: "un", base: 3.40, comp: 3.40, real: 1.70, cc: "CC-4503-02", resp: 7 });
  eacItem(3, "2.1.2", "Bombas de água de resfriamento", { tipo: "Equipamento", un: "un", qtd: 3, base: 0.55, comp: 0.52, real: 0, proj: 0.55, cc: "CC-4503-02", resp: 7 });
  eacItem(3, "2.1.3", "Painéis e inversores dos ventiladores", { tipo: "Equipamento", base: 0.35, cc: "CC-4503-02", resp: 7 });
  eacNo(3, "3", "Obras e montagem"); eacNo(3, "3.1", "Obras civis");
  eacItem(3, "3.1.1", "Escavação e bacia de água fria", { tipo: "Serviço", un: "m³", qtd: 850, base: 1.10, comp: 1.10, real: 0.30, proj: 1.38, cc: "CC-4503-03", resp: 18 });
  eacItem(3, "3.1.2", "Casa de bombas e bases", { tipo: "Serviço", un: "m³", qtd: 180, base: 0.40, comp: 0.40, cc: "CC-4503-03", resp: 18 });
  eacNo(3, "3.2", "Montagem e interligações");
  eacItem(3, "3.2.1", "Tubulação de água de circulação", { tipo: "Serviço", un: "m", qtd: 900, base: 0.50, cc: "CC-4503-04", resp: 18 });
  eacItem(3, "3.2.2", "Elétrica e automação", { tipo: "Serviço", un: "m", qtd: 6000, base: 0.25, cc: "CC-4503-04", resp: 18 });
  eacNo(3, "4", "Comissionamento e indiretos"); eacNo(3, "4.1", "Comissionamento e gerenciamento");
  eacItem(3, "4.1.1", "Comissionamento e teste de desempenho", { tipo: "Serviço", base: 0.10, cc: "CC-4503-05", resp: 8 });
  eacItem(3, "4.1.2", "Gerenciamento e canteiro", { tipo: "Indireto", un: "mês", qtd: 9, base: 0.20, comp: 0.20, real: 0.16, proj: 0.23, cc: "CC-4503-05", resp: 15 });

  incluir("eacRevisoes", { projetoId: 2, revisao: 0, data: "2026-03-02", totalCentavos: mi(18.2), justificativa: "Linha de base aprovada no gate de investimento.", smRef: null, aprovadoPorId: 14 });
  incluir("eacRevisoes", { projetoId: 3, revisao: 0, data: "2026-06-01", totalCentavos: mi(7.4), justificativa: "Linha de base aprovada no gate de investimento.", smRef: null, aprovadoPorId: 15 });
  incluir("reservas", { projetoId: 2, contingenciaCentavos: mi(0.9), gerencialCentavos: mi(0.36), constituidaEm: "2026-03-02", base: "Análise quantitativa dos riscos no gate de investimento (VME das ameaças, P80)" });
  incluir("reservas", { projetoId: 3, contingenciaCentavos: mi(0.37), gerencialCentavos: mi(0.15), constituidaEm: "2026-06-01", base: "Análise quantitativa dos riscos no gate de investimento (VME das ameaças, P80)" });

  function serie(lista) { return lista.map(function (v) { return v == null ? null : mi(v); }); }
  var PF2 = [1.8, 5.0, 9.5, 15.5, 22.5, 29.5, 36.5, 45.0, 54.0, 63.0, 71.5, 79.5, 86.5, 92.5, 97.0, 100, 100];
  incluir("curvaFinanceira", { projetoId: 2, corte: "2026-09",
    meses: ["2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10", "2026-11", "2026-12", "2027-01", "2027-02", "2027-03", "2027-04", "2027-05", "2027-06", "2027-07"],
    planejado: PF2.map(function (p) { return Math.round(mi(18.2) * p / 100); }),
    comprometido: serie([0.45, 1.30, 8.00, 9.10, 12.35, 13.95, 14.48, null, null, null, null, null, null, null, null, null, null]),
    realizado: serie([0.21, 0.61, 1.22, 2.07, 3.12, 4.34, 5.75, null, null, null, null, null, null, null, null, null, null]),
    projecao: serie([null, null, null, null, null, null, 5.75, 7.00, 8.80, 10.50, 12.10, 13.60, 14.95, 16.15, 17.05, 17.70, 18.18]) });
  var PF3 = [3.5, 10.0, 19.0, 33.0, 48.0, 63.0, 78.0, 91.0, 100, 100];
  incluir("curvaFinanceira", { projetoId: 3, corte: "2026-09",
    meses: ["2026-06", "2026-07", "2026-08", "2026-09", "2026-10", "2026-11", "2026-12", "2027-01", "2027-02", "2027-03"],
    planejado: PF3.map(function (p) { return Math.round(mi(7.4) * p / 100); }),
    comprometido: serie([0.57, 4.49, 5.99, 6.19, null, null, null, null, null, null]),
    realizado: serie([0.24, 0.72, 1.48, 2.72, null, null, null, null, null, null]),
    projecao: serie([null, null, null, 2.72, 3.85, 4.95, 6.05, 7.00, 7.62, 7.73]) });

  /* ======================================================================
     03 Contratos: contratos, medições, marcos, claims, EOT e avaliações
     ====================================================================== */
  var CT = {};
  [
    [2, "CT-2026-020", 5, "Engenharia básica e detalhada da caldeira", "Preço global", "1.1", "CB-PC-01", 1.30, "2026-03-09", "2026-10-30", "2026-10-30", 14],
    [2, "CT-2026-021", 15, "Montagem eletromecânica da caldeira", "Preço unitário", "3.2", "CB-PC-08", 2.55, "2026-08-24", "2027-05-28", "2027-05-28", 14],
    [2, "CT-2026-022", 17, "Obras civis e fundações da caldeira", "Preço unitário", "3.1", "CB-PC-07", 1.25, "2026-04-20", "2027-03-19", "2027-03-19", 14],
    [3, "CT-2026-026", 5, "Engenharia básica e detalhada da torre", "Preço global", "1.1", "TR-PC-01", 0.57, "2026-06-01", "2026-10-09", "2026-10-09", 15],
    [3, "CT-2026-027", 17, "Obras civis da bacia e da casa de bombas", "Preço unitário", "3.1", "TR-PC-05", 1.50, "2026-07-20", "2026-12-18", "2026-12-18", 15],
    [3, "CT-2026-028", 16, "Fornecimento e montagem da torre de resfriamento (EPC)", "Preço global", "2.1", "TR-PC-02", 3.40, "2026-07-01", "2027-02-26", "2027-02-26", 15]
  ].forEach(function (c) {
    CT[c[1]] = incluir("contratos", { projetoId: c[0], numero: c[1], empresaId: c[2], objeto: c[3], modalidade: c[4], eacCodigo: c[5], pacoteCompra: c[6],
      valorOriginalCentavos: mi(c[7]), inicio: c[8], terminoOriginal: c[9], terminoVigente: c[10], gestorId: c[11], fiscalId: 12, retencaoPct: 5,
      prazoNotificacaoClaimDias: 30, situacao: "Em execução" }).id;
  });
  function marco(ct, numero, descricao, criterio, pct, valor, prevista, conclusao, situacao) {
    return incluir("marcosPagamento", { contratoId: CT[ct], numero: numero, descricao: descricao, criterio: criterio, pct: pct, valorCentavos: mi(valor), prevista: prevista, conclusao: conclusao || null, situacao: situacao });
  }
  var mk20a = marco("CT-2026-020", "M1", "Engenharia básica aprovada", "Documentos da engenharia básica em Rev 0", 35, 0.455, "2026-05-29", "2026-05-27", "Pago");
  var mk20b = marco("CT-2026-020", "M2", "Engenharia civil emitida para construção", "Lista civil 100% em Rev 0", 30, 0.39, "2026-08-28", "2026-08-31", "Aprovado");
  marco("CT-2026-020", "M3", "Engenharia eletromecânica emitida para construção", "Lista eletromecânica 100% em Rev 0", 35, 0.455, "2026-10-30", null, "Previsto");
  var mk21 = marco("CT-2026-021", "M1", "Mobilização do canteiro de montagem", "Canteiro e equipe mobilizados", 10, 0.255, "2026-09-11", "2026-09-10", "Faturado");
  var mk28a = marco("CT-2026-028", "M1", "Sinal e aprovação do projeto da torre", "Pedido assinado e projeto em Rev 0", 30, 1.02, "2026-07-15", "2026-07-14", "Pago");
  var mk28b = marco("CT-2026-028", "M2", "Fabricação dos perfis e enchimento (50%)", "Relatório de inspeção de fabricação", 20, 0.68, "2026-09-15", "2026-09-18", "Aprovado");
  marco("CT-2026-028", "M3", "Entrega da torre na obra", "Recebimento sem avarias", 30, 1.02, "2026-11-20", null, "Previsto");
  marco("CT-2026-028", "M4", "Teste de desempenho térmico", "Teste CTI aprovado", 20, 0.68, "2027-02-26", null, "Previsto");
  function med(ct, numero, periodo, valor, situacao, marcoId) { incluir("medicoes", { contratoId: CT[ct], numero: numero, periodo: periodo, brutoCentavos: mi(valor), situacao: situacao, marcoId: marcoId || null }); }
  med("CT-2026-020", "BM-01", "2026-05", 0.455, "Paga", mk20a.id);
  med("CT-2026-020", "BM-02", "2026-06", 0.21, "Paga");
  med("CT-2026-020", "BM-03", "2026-07", 0.18, "Paga");
  med("CT-2026-020", "BM-04", "2026-08", 0.39, "Faturada", mk20b.id);
  med("CT-2026-021", "BM-01", "2026-09", 0.255, "Faturada", mk21.id);
  med("CT-2026-022", "BM-01", "2026-06", 0.12, "Paga");
  med("CT-2026-022", "BM-02", "2026-07", 0.16, "Paga");
  med("CT-2026-022", "BM-03", "2026-08", 0.18, "Aprovada");
  med("CT-2026-022", "BM-04", "2026-09", 0.14, "Em análise");
  med("CT-2026-026", "BM-01", "2026-07", 0.21, "Paga");
  med("CT-2026-026", "BM-02", "2026-08", 0.19, "Paga");
  med("CT-2026-026", "BM-03", "2026-09", 0.16, "Aprovada");
  med("CT-2026-027", "BM-01", "2026-08", 0.14, "Paga");
  med("CT-2026-027", "BM-02", "2026-09", 0.16, "Aprovada");
  med("CT-2026-028", "BM-01", "2026-07", 1.02, "Paga", mk28a.id);
  med("CT-2026-028", "BM-02", "2026-09", 0.68, "Aprovada", mk28b.id);
  incluir("claims", { contratoId: CT["CT-2026-022"], codigo: "CLM-CB-2026-0001", direcao: "Da contratada", tipo: "Custo", causa: "Liberação de área",
    descricao: "Improdutividade da equipe de fundações por liberação tardia da área do silo (faixa leste).", clausula: "11.2", evento: "2026-08-10", notificacao: "2026-08-21",
    pleiteadoCentavos: mi(0.18), diasPleiteados: 0, reconhecidoCentavos: null, diasReconhecidos: null, situacao: "Em análise", encerramento: null, riscoRef: null, smRef: null });
  incluir("claims", { contratoId: CT["CT-2026-027"], codigo: "CLM-TR-2026-0001", direcao: "Da contratada", tipo: "Custo e prazo", causa: "Condição de subsolo",
    descricao: "Escavação em rocha sã a partir da cota 2,1 m na bacia de água fria, não indicada nas sondagens do edital.", clausula: "9.4", evento: "2026-08-24", notificacao: "2026-08-28",
    pleiteadoCentavos: mi(0.28), diasPleiteados: 15, reconhecidoCentavos: null, diasReconhecidos: null, situacao: "Em negociação", encerramento: null, riscoRef: "RSK-TR-2026-0001", smRef: "SM-TR-2026-0001" });
  incluir("extensoesPrazo", { contratoId: CT["CT-2026-027"], codigo: "EOT-TR-2026-0001", claimRef: "CLM-TR-2026-0001", evento: "Escavação em rocha na bacia de água fria.",
    diasSolicitados: 15, diasConcedidos: null, classificacao: "Justificável e compensável", metodo: "Análise de impacto no tempo", marcoAfetado: "Término da bacia de água fria",
    data: "2026-09-04", decisao: null, situacao: "Em análise" });
  function aval(ct, periodo, notas, comentario) {
    incluir("avaliacoes", { contratoId: CT[ct], periodo: periodo, tipo: "Mensal", avaliadorId: 12, parametrosVersao: 1,
      pesos: { hse: 25, qualidade: 20, prazo: 20, gestao: 15, recursos: 10, documentacao: 10 }, notas: notas, comentario: comentario });
  }
  aval("CT-2026-020", "2026-08", { hse: 4, qualidade: 4, prazo: 3, gestao: 4, recursos: 4, documentacao: 4 }, "Emissões no prazo, com atraso pontual na eletromecânica.");
  aval("CT-2026-022", "2026-08", { hse: 3, qualidade: 3, prazo: 3, gestao: 3, recursos: 3, documentacao: 3 }, "Produtividade abaixo do plano nas fundações; recobrimento de armadura com não conformidade.");
  aval("CT-2026-027", "2026-08", { hse: 4, qualidade: 3, prazo: 3, gestao: 2, recursos: 3, documentacao: 3 }, "Notificação do pleito de rocha dentro do prazo, porém sem histograma de equipamentos.");
  aval("CT-2026-028", "2026-08", { hse: 4, qualidade: 4, prazo: 4, gestao: 4, recursos: 4, documentacao: 3 }, "Fabricação dentro do plano; data book parcial.");

  /* ======================================================================
     04 Suprimentos: pacotes, processos (RFx), pedidos e qualificação
     ====================================================================== */
  var PAC = {};
  function pac(o) { PAC[o.codigo] = incluir("pacotes", Object.assign({ previsao: {}, primeiraPropostaCentavos: null, propostasValidas: 0, fornecedorUnico: false, emergencial: false,
    fornecedorId: null, adjudicadoCentavos: null, compradorId: 7 }, o)); return PAC[o.codigo]; }
  pac({ projetoId: 2, codigo: "CB-PC-01", escopo: "Engenharia básica e detalhada", tipo: "Serviço", disciplina: "Engenharia", modalidade: "Preço global", lli: false, eacCodigo: "1.1",
    estimativaCentavos: mi(1.35), ros: "2026-03-09",
    plano: { requisicao: "2026-01-19", rfx: "2026-01-26", propostas: "2026-02-13", eqTecnica: "2026-02-20", eqComercial: "2026-02-27", adjudicacao: "2026-03-04", pedido: "2026-03-06" },
    real: { requisicao: "2026-01-19", rfx: "2026-01-27", propostas: "2026-02-13", eqTecnica: "2026-02-20", eqComercial: "2026-02-27", adjudicacao: "2026-03-04", pedido: "2026-03-06" },
    etapa: "Pedido/contrato emitido", fornecedorId: 5, adjudicadoCentavos: mi(1.30), primeiraPropostaCentavos: mi(1.38), propostasValidas: 3, contratoRef: "CT-2026-020" });
  pac({ projetoId: 2, codigo: "CB-PC-02", escopo: "Caldeira aquatubular de biomassa 45 t/h", tipo: "Equipamento", disciplina: "Mecânica", modalidade: "Preço global", lli: true, eacCodigo: "2.1.1",
    gateLli: { data: "2026-03-02", referencia: "Aprovação específica de LLI no gate de investimento, com análise de risco do pacote" },
    estimativaCentavos: mi(6.90), ros: "2027-01-10",
    plano: { requisicao: "2026-03-09", rfx: "2026-03-16", propostas: "2026-04-06", eqTecnica: "2026-04-17", eqComercial: "2026-04-28", adjudicacao: "2026-05-08", pedido: "2026-05-12" },
    real: { requisicao: "2026-03-09", rfx: "2026-03-18", propostas: "2026-04-10", eqTecnica: "2026-04-24", eqComercial: "2026-05-06", adjudicacao: "2026-05-15", pedido: "2026-05-20" },
    etapa: "Pedido/contrato emitido", fornecedorId: 14, adjudicadoCentavos: mi(6.70), primeiraPropostaCentavos: mi(7.05), propostasValidas: 3, pedidoRef: "PED-2026-0011" });
  pac({ projetoId: 2, codigo: "CB-PC-03", escopo: "Sistema de alimentação e estocagem de biomassa", tipo: "Equipamento", disciplina: "Mecânica", modalidade: "Preço global", lli: false, eacCodigo: "2.1.2",
    estimativaCentavos: mi(1.12), ros: "2027-02-01",
    plano: { requisicao: "2026-03-23", rfx: "2026-04-01", propostas: "2026-04-22", eqTecnica: "2026-05-04", eqComercial: "2026-05-15", adjudicacao: "2026-05-25", pedido: "2026-05-28" },
    real: { requisicao: "2026-03-23", rfx: "2026-04-03", propostas: "2026-04-24", eqTecnica: "2026-05-08", eqComercial: "2026-05-22", adjudicacao: "2026-06-01", pedido: "2026-06-05" },
    etapa: "Pedido/contrato emitido", fornecedorId: 4, adjudicadoCentavos: mi(1.08), primeiraPropostaCentavos: mi(1.14), propostasValidas: 3, pedidoRef: "PED-2026-0012" });
  pac({ projetoId: 2, codigo: "CB-PC-04", escopo: "Precipitador eletrostático", tipo: "Equipamento", disciplina: "Meio ambiente", modalidade: "Preço global", lli: true, eacCodigo: "2.1.3",
    gateLli: { data: "2026-03-02", referencia: "Aprovação específica de LLI no gate de investimento" },
    estimativaCentavos: mi(1.20), ros: "2027-03-01",
    plano: { requisicao: "2026-04-06", rfx: "2026-04-15", propostas: "2026-05-11", eqTecnica: "2026-05-25", eqComercial: "2026-06-05", adjudicacao: "2026-06-15", pedido: "2026-06-18" },
    real: { requisicao: "2026-04-06", rfx: "2026-04-17", propostas: "2026-05-15", eqTecnica: "2026-06-01", eqComercial: "2026-06-17", adjudicacao: "2026-06-26", pedido: "2026-07-01" },
    etapa: "Pedido/contrato emitido", fornecedorId: 18, adjudicadoCentavos: mi(1.15), primeiraPropostaCentavos: mi(1.22), propostasValidas: 3, pedidoRef: "PED-2026-0013" });
  pac({ projetoId: 2, codigo: "CB-PC-05", escopo: "Bombas de alimentação, ventiladores e válvulas", tipo: "Equipamento", disciplina: "Mecânica", modalidade: "Preço global", lli: false, eacCodigo: "2.2.1",
    estimativaCentavos: mi(0.55), ros: "2027-02-26",
    plano: { requisicao: "2026-07-06", rfx: "2026-07-20", propostas: "2026-08-10", eqTecnica: "2026-08-24", eqComercial: "2026-09-04", adjudicacao: "2026-09-11", pedido: "2026-09-15", entrega: "2027-01-29" },
    real: { requisicao: "2026-07-06", rfx: "2026-07-27", propostas: "2026-08-31" },
    previsao: { eqTecnica: "2026-09-30", eqComercial: "2026-10-09", adjudicacao: "2026-10-16", pedido: "2026-10-20", entrega: "2027-02-19" },
    etapa: "Propostas recebidas", propostasValidas: 3 });
  pac({ projetoId: 2, codigo: "CB-PC-06", escopo: "Materiais elétricos e de automação", tipo: "Material", disciplina: "Elétrica", modalidade: "Preço unitário", lli: false, eacCodigo: "2.2.2",
    estimativaCentavos: mi(0.55), ros: "2027-01-11",
    plano: { requisicao: "2026-08-17", rfx: "2026-09-01", propostas: "2026-09-22", eqTecnica: "2026-10-02", eqComercial: "2026-10-13", adjudicacao: "2026-10-20", pedido: "2026-10-23", entrega: "2026-12-18" },
    real: { requisicao: "2026-09-08" },
    previsao: { rfx: "2026-09-29", propostas: "2026-10-20", eqTecnica: "2026-10-30", eqComercial: "2026-11-10", adjudicacao: "2026-11-17", pedido: "2026-11-20", entrega: "2027-01-15" },
    etapa: "Requisição" });
  pac({ projetoId: 2, codigo: "CB-PC-07", escopo: "Obras civis e fundações", tipo: "Serviço", disciplina: "Civil", modalidade: "Preço unitário", lli: false, eacCodigo: "3.1",
    estimativaCentavos: mi(1.30), ros: "2026-04-20",
    plano: { requisicao: "2026-02-16", rfx: "2026-02-23", propostas: "2026-03-16", eqTecnica: "2026-03-27", eqComercial: "2026-04-06", adjudicacao: "2026-04-13", pedido: "2026-04-16" },
    real: { requisicao: "2026-02-16", rfx: "2026-02-24", propostas: "2026-03-18", eqTecnica: "2026-03-30", eqComercial: "2026-04-08", adjudicacao: "2026-04-14", pedido: "2026-04-17" },
    etapa: "Pedido/contrato emitido", fornecedorId: 17, adjudicadoCentavos: mi(1.25), primeiraPropostaCentavos: mi(1.33), propostasValidas: 4, contratoRef: "CT-2026-022" });
  pac({ projetoId: 2, codigo: "CB-PC-08", escopo: "Montagem eletromecânica da caldeira", tipo: "Serviço", disciplina: "Montagem", modalidade: "Preço unitário", lli: false, eacCodigo: "3.2",
    estimativaCentavos: mi(2.65), ros: "2026-08-31",
    plano: { requisicao: "2026-05-11", rfx: "2026-05-25", propostas: "2026-06-19", eqTecnica: "2026-07-03", eqComercial: "2026-07-17", adjudicacao: "2026-07-27", pedido: "2026-07-31" },
    real: { requisicao: "2026-05-11", rfx: "2026-05-27", propostas: "2026-06-24", eqTecnica: "2026-07-10", eqComercial: "2026-07-29", adjudicacao: "2026-08-12", pedido: "2026-08-19" },
    etapa: "Pedido/contrato emitido", fornecedorId: 15, adjudicadoCentavos: mi(2.55), primeiraPropostaCentavos: mi(2.71), propostasValidas: 3, contratoRef: "CT-2026-021" });

  pac({ projetoId: 3, codigo: "TR-PC-01", escopo: "Engenharia básica e detalhada da torre", tipo: "Serviço", disciplina: "Engenharia", modalidade: "Preço global", lli: false, eacCodigo: "1.1",
    estimativaCentavos: mi(0.60), ros: "2026-06-01",
    plano: { requisicao: "2026-04-20", rfx: "2026-04-27", propostas: "2026-05-15", eqTecnica: "2026-05-20", eqComercial: "2026-05-25", adjudicacao: "2026-05-27", pedido: "2026-05-29" },
    real: { requisicao: "2026-04-20", rfx: "2026-04-27", propostas: "2026-05-15", eqTecnica: "2026-05-20", eqComercial: "2026-05-25", adjudicacao: "2026-05-27", pedido: "2026-05-29" },
    etapa: "Pedido/contrato emitido", fornecedorId: 5, adjudicadoCentavos: mi(0.57), primeiraPropostaCentavos: mi(0.61), propostasValidas: 3, contratoRef: "CT-2026-026" });
  pac({ projetoId: 3, codigo: "TR-PC-02", escopo: "Torre de resfriamento em PRFV com 3 células (fornecimento e montagem)", tipo: "EPC", disciplina: "Mecânica", modalidade: "Preço global", lli: true, eacCodigo: "2.1.1",
    gateLli: { data: "2026-06-01", referencia: "Aprovação específica de LLI no gate de investimento" },
    estimativaCentavos: mi(3.55), ros: "2026-07-01",
    plano: { requisicao: "2026-05-04", rfx: "2026-05-11", propostas: "2026-06-01", eqTecnica: "2026-06-10", eqComercial: "2026-06-19", adjudicacao: "2026-06-24", pedido: "2026-06-26" },
    real: { requisicao: "2026-05-04", rfx: "2026-05-12", propostas: "2026-06-02", eqTecnica: "2026-06-12", eqComercial: "2026-06-22", adjudicacao: "2026-06-26", pedido: "2026-06-30" },
    etapa: "Pedido/contrato emitido", fornecedorId: 16, adjudicadoCentavos: mi(3.40), primeiraPropostaCentavos: mi(3.62), propostasValidas: 3, contratoRef: "CT-2026-028" });
  pac({ projetoId: 3, codigo: "TR-PC-03", escopo: "Bombas de água de resfriamento", tipo: "Equipamento", disciplina: "Mecânica", modalidade: "Preço global", lli: false, eacCodigo: "2.1.2",
    estimativaCentavos: mi(0.55), ros: "2026-12-20",
    plano: { requisicao: "2026-06-15", rfx: "2026-06-22", propostas: "2026-07-13", eqTecnica: "2026-07-22", eqComercial: "2026-07-29", adjudicacao: "2026-08-03", pedido: "2026-08-06" },
    real: { requisicao: "2026-06-15", rfx: "2026-06-24", propostas: "2026-07-15", eqTecnica: "2026-07-24", eqComercial: "2026-07-31", adjudicacao: "2026-08-05", pedido: "2026-08-10" },
    etapa: "Pedido/contrato emitido", fornecedorId: 8, adjudicadoCentavos: mi(0.52), primeiraPropostaCentavos: mi(0.55), propostasValidas: 3, pedidoRef: "PED-2026-0014" });
  pac({ projetoId: 3, codigo: "TR-PC-04", escopo: "Painéis e inversores dos ventiladores", tipo: "Equipamento", disciplina: "Elétrica", modalidade: "Preço global", lli: false, eacCodigo: "2.1.3",
    estimativaCentavos: mi(0.35), ros: "2027-01-08",
    plano: { requisicao: "2026-07-13", rfx: "2026-07-20", propostas: "2026-08-10", eqTecnica: "2026-08-21", eqComercial: "2026-08-31", adjudicacao: "2026-09-04", pedido: "2026-09-08", entrega: "2026-12-11" },
    real: { requisicao: "2026-07-13", rfx: "2026-07-24", propostas: "2026-08-19" },
    previsao: { eqTecnica: "2026-09-29", eqComercial: "2026-10-06", adjudicacao: "2026-10-09", pedido: "2026-10-13", entrega: "2027-01-15" },
    etapa: "Equalização técnica", propostasValidas: 3 });
  pac({ projetoId: 3, codigo: "TR-PC-05", escopo: "Obras civis da bacia e da casa de bombas", tipo: "Serviço", disciplina: "Civil", modalidade: "Preço unitário", lli: false, eacCodigo: "3.1",
    estimativaCentavos: mi(1.55), ros: "2026-07-20",
    plano: { requisicao: "2026-05-18", rfx: "2026-05-25", propostas: "2026-06-15", eqTecnica: "2026-06-26", eqComercial: "2026-07-06", adjudicacao: "2026-07-10", pedido: "2026-07-14" },
    real: { requisicao: "2026-05-18", rfx: "2026-05-26", propostas: "2026-06-17", eqTecnica: "2026-06-29", eqComercial: "2026-07-08", adjudicacao: "2026-07-13", pedido: "2026-07-16" },
    etapa: "Pedido/contrato emitido", fornecedorId: 17, adjudicadoCentavos: mi(1.50), primeiraPropostaCentavos: mi(1.58), propostasValidas: 4, contratoRef: "CT-2026-027" });
  pac({ projetoId: 3, codigo: "TR-PC-06", escopo: "Tubulação de água de circulação", tipo: "Serviço", disciplina: "Tubulação", modalidade: "Preço unitário", lli: false, eacCodigo: "3.2.1",
    estimativaCentavos: mi(0.50), ros: "2026-11-16",
    plano: { requisicao: "2026-09-14", rfx: "2026-09-21", propostas: "2026-10-09", eqTecnica: "2026-10-16", eqComercial: "2026-10-23", adjudicacao: "2026-10-28", pedido: "2026-10-30" },
    real: {}, etapa: "Planejado" });

  function pedido(o) {
    var nomes = ["Aprovação de documentos", "Matéria-prima", "Fabricação", "Inspeção / FAT", "Embarque", "Entrega"];
    var x = incluir("pedidos", Object.assign({}, o, { pacoteId: PAC[o.pacote].id, marcos: o.marcos.map(function (m, k) { return { nome: nomes[k], lb: m[0], previsao: m[1], realizada: m[2] || null }; }) }));
    delete x.pacote;
    return x;
  }
  pedido({ projetoId: 2, numero: "PED-2026-0011", pacote: "CB-PC-02", fornecedorId: 14, descricao: "Caldeira aquatubular de biomassa 45 t/h, 42 bar", valorCentavos: mi(6.70), lli: true,
    emissao: "2026-05-20", dataContratual: "2027-01-05", previsao: "2027-02-05", ros: "2027-01-10", entrega: null,
    marcos: [["2026-06-30", "2026-07-20", "2026-07-20"], ["2026-08-15", "2026-09-05", "2026-09-05"], ["2026-11-30", "2026-12-28"], ["2026-12-10", "2027-01-12"], ["2026-12-20", "2027-01-22"], ["2027-01-05", "2027-02-05"]] });
  pedido({ projetoId: 2, numero: "PED-2026-0012", pacote: "CB-PC-03", fornecedorId: 4, descricao: "Transportadores, rosca dosadora e silo metálico de biomassa", valorCentavos: mi(1.08), lli: false,
    emissao: "2026-06-05", dataContratual: "2027-01-20", previsao: "2027-01-25", ros: "2027-02-01", entrega: null,
    marcos: [["2026-07-10", "2026-07-10", "2026-07-10"], ["2026-08-20", "2026-08-20", "2026-08-20"], ["2026-11-30", "2026-12-10"], ["2026-12-15", "2026-12-22"], ["2027-01-08", "2027-01-14"], ["2027-01-20", "2027-01-25"]] });
  pedido({ projetoId: 2, numero: "PED-2026-0013", pacote: "CB-PC-04", fornecedorId: 18, descricao: "Precipitador eletrostático de 2 campos", valorCentavos: mi(1.15), lli: true,
    emissao: "2026-07-01", dataContratual: "2027-02-15", previsao: "2027-02-20", ros: "2027-03-01", entrega: null,
    marcos: [["2026-08-15", "2026-09-30"], ["2026-10-01", "2026-10-20"], ["2026-12-20", "2027-01-15"], ["2027-01-15", "2027-01-29"], ["2027-02-01", "2027-02-08"], ["2027-02-15", "2027-02-20"]] });
  pedido({ projetoId: 3, numero: "PED-2026-0014", pacote: "TR-PC-03", fornecedorId: 8, descricao: "Bombas centrífugas de água de resfriamento (3 x 850 m³/h)", valorCentavos: mi(0.52), lli: false,
    emissao: "2026-08-10", dataContratual: "2026-12-10", previsao: "2026-12-15", ros: "2026-12-20", entrega: null,
    marcos: [["2026-09-10", "2026-09-18", "2026-09-18"], ["2026-10-05", "2026-10-09"], ["2026-11-13", "2026-11-20"], ["2026-11-24", "2026-11-30"], ["2026-12-01", "2026-12-07"], ["2026-12-10", "2026-12-15"]] });

  function proposta(id, fornecedor, fornecedorId, recebida, valor, prazoDias, validade, nota, aprovada, desvios) {
    return { id: id, fornecedor: fornecedor, fornecedorId: fornecedorId, recebida: recebida, valorCentavos: mi(valor), prazoDias: prazoDias, validade: validade,
      notaTecnica: nota, tecnicamenteAprovada: aprovada, desvios: desvios, anexos: [{ nome: "Proposta " + fornecedor + ".pdf" }] };
  }
  incluir("processos", { pacoteId: PAC["CB-PC-05"].id, numero: "RFQ-2026-021", pesoTecnico: 40, pesoComercial: 60, dataLimitePropostas: "2026-08-28",
    convidados: ["Sigma Bombas", "Gama Válvulas", "Chi Ventiladores", "Psi Fluidos"],
    propostas: [proposta(1, "Sigma Bombas", 8, "2026-08-27", 0.53, 150, "2026-11-30", null, null, "A confirmar na equalização técnica."),
      proposta(2, "Gama Válvulas", 3, "2026-08-28", 0.57, 140, "2026-11-28", null, null, "Ventiladores de terceiro fabricante."),
      proposta(3, "Chi Ventiladores", null, "2026-08-31", 0.51, 170, "2026-12-15", null, null, "Proposta recebida após o prazo; aceita por decisão do comprador.")],
    negociacoes: [], recomendacao: null, aprovacao: null,
    historico: [{ data: "2026-07-27", etapa: "RFx emitida", porId: 7, texto: "RFQ enviada a 4 fornecedores." },
      { data: "2026-08-31", etapa: "Propostas recebidas", porId: 7, texto: "Recebimento encerrado com 3 propostas; equalização técnica pendente da engenharia." }] });
  incluir("processos", { pacoteId: PAC["TR-PC-04"].id, numero: "RFQ-2026-027", pesoTecnico: 40, pesoComercial: 60, dataLimitePropostas: "2026-08-17",
    convidados: ["Kappa Elétrica", "Teta Automação", "Ômega Drives"],
    propostas: [proposta(1, "Kappa Elétrica", 9, "2026-08-14", 0.34, 110, "2026-11-14", 84, true, "Sem desvios."),
      proposta(2, "Teta Automação", 11, "2026-08-17", 0.36, 95, "2026-11-17", null, null, "Inversores com filtro de harmônicas opcional."),
      proposta(3, "Ômega Drives", null, "2026-08-19", 0.31, 130, "2026-11-19", null, null, "Fornecedor sem qualificação; documentação em análise.")],
    negociacoes: [], recomendacao: null, aprovacao: null,
    historico: [{ data: "2026-07-24", etapa: "RFx emitida", porId: 7, texto: "RFQ enviada a 3 fornecedores." },
      { data: "2026-08-19", etapa: "Equalização técnica", porId: 7, texto: "Recebimento encerrado com 3 propostas." }] });

  function docs(validades) {
    var nomes = ["Certidão negativa de débitos federais", "Certidão negativa de débitos trabalhistas", "Certificado de regularidade do FGTS", "Certificado ISO 9001"];
    return validades.map(function (v, k) { return { nome: nomes[k], validade: v }; });
  }
  [
    { empresaId: 14, situacao: "Qualificado", categorias: ["Caldeiras e vasos de pressão"], validadeQualificacao: "2027-04-30", documentos: docs(["2027-02-10", "2027-01-15", "2026-12-01", "2027-06-30"]), historico: [] },
    { empresaId: 15, situacao: "Qualificado", categorias: ["Montagem eletromecânica"], validadeQualificacao: "2027-06-30", documentos: docs(["2027-03-05", "2027-02-20", "2026-11-20", "2027-09-15"]), historico: [] },
    { empresaId: 16, situacao: "Qualificado", categorias: ["Torres de resfriamento"], validadeQualificacao: "2027-05-31", documentos: docs(["2027-01-30", "2027-01-10", "2026-10-15", "2027-04-20"]), historico: [] },
    { empresaId: 17, situacao: "Qualificado com restrição", categorias: ["Obras civis"], validadeQualificacao: "2026-12-31", documentos: docs(["2026-12-20", "2026-11-30", "2026-10-05", "2026-10-02"]), historico: [] },
    { empresaId: 18, situacao: "Qualificado", categorias: ["Equipamentos de controle ambiental"], validadeQualificacao: "2027-03-31", documentos: docs(["2027-02-28", "2027-02-01", "2026-12-15", "2027-05-10"]), historico: [] }
  ].forEach(function (f) { M.fornecedores = M.fornecedores || []; M.fornecedores.push(f); });

  /* ======================================================================
     01 Central de Ações: atas e ações
     ====================================================================== */
  var ATA = {};
  [
    { projetoId: 2, numero: "CB-2026-0001", data: "2026-08-20", tipoReuniao: "Coordenação de obra", assunto: "Coordenação mensal: fundações, suprimentos da caldeira e mobilização da montagem",
      elaboradoPorId: 16, empresaPrincipalId: 17, empresasIds: [17, 15], participantesIds: [1, 14, 16, 7, 9, 18, 17] },
    { projetoId: 2, numero: "CB-2026-0002", data: "2026-09-17", tipoReuniao: "Coordenação de obra", assunto: "Coordenação quinzenal: estrutura da caldeira e diligenciamento do fornecedor",
      elaboradoPorId: 16, empresaPrincipalId: 15, empresasIds: [15, 17, 14], participantesIds: [1, 14, 16, 7, 17, 18] },
    { projetoId: 3, numero: "TR-2026-0001", data: "2026-09-10", tipoReuniao: "Coordenação de obra", assunto: "Coordenação da obra da torre: escavação em rocha e interfaces com a operação",
      elaboradoPorId: 16, empresaPrincipalId: 17, empresasIds: [17, 16], participantesIds: [1, 15, 16, 7, 18, 10] }
  ].forEach(function (a) {
    ATA[a.numero] = incluir("atas", Object.assign({ escopo: "Projeto", revisao: 0, diretoria: "Diretoria de Projetos", unidade: "Unidade Horizonte" }, a)).id;
  });
  function acao(o) {
    return incluir("acoes", Object.assign({ tipo: "Ação", replanejada: null, conclusao: null }, o, o.ata ? { ataId: ATA[o.ata], origem: "Ata" } : {}));
  }
  [
    { projetoId: 2, ata: "CB-2026-0001", item: "1.1", grupo: "Obras civis", assunto: "Liberar as bases BS-610-01 a 04 para a montagem", descricao: "Concluir as bases da estrutura da caldeira e emitir o termo de liberação.", solicitanteId: 14, responsavelId: 18, prevista: "2026-09-04", conclusao: "2026-09-09" },
    { projetoId: 2, ata: "CB-2026-0001", item: "1.2", grupo: "Suprimentos", assunto: "Plano de recuperação do fornecedor da caldeira", descricao: "Obter do fornecedor o plano de recuperação da fabricação das paredes d'água com datas por marco.", solicitanteId: 14, responsavelId: 7, prevista: "2026-09-04", conclusao: null },
    { projetoId: 2, ata: "CB-2026-0001", item: "1.3", grupo: "Engenharia", assunto: "Emitir a revisão 2 dos desenhos de ligação da estrutura", descricao: "Incorporar os comentários do fornecedor da caldeira às ligações das colunas.", solicitanteId: 16, responsavelId: 6, prevista: "2026-09-11", conclusao: "2026-09-21" },
    { projetoId: 2, ata: "CB-2026-0001", item: "1.4", grupo: "HSE", assunto: "Aprovar o plano de rigging dos içamentos da estrutura", descricao: "Plano de rigging assinado por engenheiro habilitado antes do primeiro içamento.", solicitanteId: 10, responsavelId: 17, prevista: "2026-08-28", conclusao: "2026-08-27" },
    { projetoId: 2, ata: "CB-2026-0002", item: "1.1", grupo: "Obras civis", assunto: "Corrigir a cota da base BS-610-02 com graute", descricao: "Executar a correção e liberar a base para o posicionamento da coluna C-02.", solicitanteId: 17, responsavelId: 18, prevista: "2026-09-22", conclusao: null },
    { projetoId: 2, ata: "CB-2026-0002", item: "1.2", grupo: "Suprimentos", assunto: "Inspeção residente no fornecedor da caldeira", descricao: "Mobilizar inspetor residente na fábrica até a expedição do tubulão superior.", solicitanteId: 14, responsavelId: 7, prevista: "2026-10-02", conclusao: null },
    { projetoId: 2, ata: "CB-2026-0002", item: "1.3", grupo: "Planejamento", assunto: "Estudar a pré-montagem em solo dos módulos da caldeira", descricao: "Avaliar ganho de prazo e necessidade de guindaste para a pré-montagem (oportunidade RSK-CB-2026-0004).", solicitanteId: 14, responsavelId: 16, prevista: "2026-10-09", conclusao: null },
    { projetoId: 2, ata: "CB-2026-0002", item: "1.4", grupo: "Licenciamento", assunto: "Protocolar o plano de monitoramento de emissões", descricao: "Protocolar no órgão ambiental o plano de monitoramento do precipitador.", solicitanteId: 4, responsavelId: 4, prevista: "2026-09-18", conclusao: null },
    { projetoId: 2, ata: "CB-2026-0002", item: "1.5", grupo: "Obras civis", assunto: "Reforçar a equipe de fôrmas do silo", descricao: "Mobilizar segunda equipe de carpinteiros para recuperar o atraso do anel do silo.", solicitanteId: 16, responsavelId: 18, prevista: "2026-09-24", conclusao: "2026-09-23" },
    { projetoId: 3, ata: "TR-2026-0001", item: "1.1", grupo: "Obras civis", assunto: "Plano de fogo para o desmonte de rocha da bacia", descricao: "Aprovar o plano de fogo e obter a licença de uso de explosivos.", solicitanteId: 15, responsavelId: 18, prevista: "2026-09-18", conclusao: null },
    { projetoId: 3, ata: "TR-2026-0001", item: "1.2", grupo: "Operação", assunto: "Janela de parada da torre existente para as interligações", descricao: "Acordar com a operação a janela de parada para as interligações de água de circulação.", solicitanteId: 15, responsavelId: 15, prevista: "2026-10-16", conclusao: null },
    { projetoId: 3, ata: "TR-2026-0001", item: "1.3", grupo: "Suprimentos", assunto: "Concluir a equalização técnica dos inversores", descricao: "Parecer técnico das três propostas da RFQ-2026-027.", solicitanteId: 7, responsavelId: 6, prevista: "2026-09-29", conclusao: null },
    { projetoId: 3, ata: "TR-2026-0001", item: "1.4", grupo: "HSE", assunto: "APR do desmonte de rocha com isolamento de área", descricao: "Elaborar a APR do desmonte com raio de isolamento e horários combinados com a operação.", solicitanteId: 10, responsavelId: 10, prevista: "2026-09-15", conclusao: "2026-09-14" }
  ].forEach(acao);
  acao({ projetoId: 2, origem: "Suprimentos", origemRef: "PED-2026-0011", grupo: "Diligenciamento", assunto: "Recuperar a folga negativa da caldeira (PED-2026-0011)",
    descricao: "Previsão de entrega 26 dias após a data necessária na obra: negociar turno extra na fabricação das paredes d'água.", solicitanteId: 7, responsavelId: 7, prevista: "2026-10-05" });
  acao({ projetoId: 2, origem: "Risco", origemRef: "RSK-CB-2026-0001", item: "1", grupo: "Plano de resposta", assunto: "Diligenciamento semanal na fábrica da caldeira",
    descricao: "Reunião semanal com o fornecedor e relatório fotográfico da fabricação dos componentes de pressão.", solicitanteId: 14, responsavelId: 7, prevista: "2026-09-18", contribuicao: { probabilidade: true, impacto: false } });
  acao({ projetoId: 2, origem: "Risco", origemRef: "RSK-CB-2026-0002", item: "1", grupo: "Plano de resposta", assunto: "Especificar a umidade máxima da biomassa no contrato de fornecimento",
    descricao: "Incluir a faixa de umidade de projeto e a penalidade no contrato do fornecedor de biomassa.", solicitanteId: 14, responsavelId: 14, prevista: "2026-10-30", contribuicao: { probabilidade: true, impacto: false } });
  acao({ projetoId: 3, origem: "Risco", origemRef: "RSK-TR-2026-0005", item: "1", grupo: "Plano de resposta", assunto: "Linha de vida e plataforma na montagem da torre",
    descricao: "Exigir linha de vida contínua e plataforma elevatória no plano de montagem da Rho Torres.", solicitanteId: 10, responsavelId: 10, prevista: "2026-10-23", contribuicao: { probabilidade: false, impacto: true } });
  acao({ projetoId: 2, origem: "Mudança", origemRef: "SM-CB-2026-0001", item: "1", grupo: "Mudança", assunto: "Revisar o projeto do silo de biomassa para 3 dias de estoque",
    descricao: "Implementação da SM-CB-2026-0001: revisão do projeto civil e do pedido do silo metálico.", solicitanteId: 14, responsavelId: 6, prevista: "2026-10-09" });

  /* ======================================================================
     05 Gestão de Riscos
     ====================================================================== */
  function risco(o) {
    var base = { natureza: "Ameaça", identificadoPorId: 1, origemTipo: "Workshop de riscos", origem: "Workshop de riscos", riscoVida: false, aprovacao: { exigida: false },
      custoRespostaCentavos: 0, revisoes: [] };
    return incluir("riscos", Object.assign(base, o));
  }
  function dim(prazo, custo, escopo, sms, imagem, legal) { return { prazo: prazo, custo: custo, escopo: escopo, sms: sms, imagem: imagem, legal: legal }; }
  function rev(data, porId, tipo, apurada, de, para, p, i, texto) { return { data: data, porId: porId, tipo: tipo, situacaoApurada: apurada, de: de, para: para, p: p, i: i, gatilho: false, texto: texto }; }
  risco({ projetoId: 2, codigo: "RSK-CB-2026-0001", titulo: "Atraso na fabricação das partes de pressão da caldeira", categoria: "Suprimentos", subcategoria: "Fornecedores",
    donoId: 7, identificadoEm: "2026-05-25", origemTipo: "Plano de compras", origem: "Plano de compras",
    causa: "Carteira do fornecedor cheia e atraso na chegada das chapas e tubos de aço-liga", consequencia: "Entrega da caldeira após a data necessária na obra e deslocamento da montagem de pressão",
    descricao: "O fornecedor já registrou 20 dias de atraso na matéria-prima; a fabricação das paredes d'água concentra o caminho crítico do projeto.",
    gatilho: "Folga negativa no diligenciamento por duas semanas seguidas",
    inerente: { p: 4, i: 4, dimensoes: dim(4, 3, 1, 1, 2, 1) }, residual: { p: 4, i: 4, dimensoes: dim(4, 3, 1, 1, 2, 1) },
    dimensao: "Prazo", impactoPrazoDias: 30, impactoCustoCentavos: mi(1.5), estrategia: "Mitigar",
    plano: "Diligenciamento semanal com inspetor residente, turno extra na fabricação das paredes d'água custeado pelo fornecedor e resequenciamento da montagem com pré-montagem em solo.",
    severidadeAlvo: "alto", prazoAlvo: "2026-11-15", custoRespostaCentavos: mi(0.12), responsavelPlanoId: 7,
    aprovacao: { exigida: true, situacao: "Aprovado", porId: 1, data: "2026-06-05" }, cadenciaDias: 15, ultimaRevisao: "2026-09-18", proximaRevisao: "2026-10-02", situacao: "Em tratamento",
    revisoes: [rev("2026-09-18", 7, "revisao", "Sem mudança", 16, 16, 4, 4, "Matéria-prima chegou em 05/09; previsão de entrega ainda 26 dias após a data necessária."),
      rev("2026-09-03", 7, "revisao", "Sem mudança", 16, 16, 4, 4, "Fornecedor confirmou atraso das chapas de aço-liga."),
      rev("2026-05-25", 1, "inerente", "Avaliação inicial", null, 16, 4, 4, "Risco identificado na emissão do pedido.")] });
  risco({ projetoId: 2, codigo: "RSK-CB-2026-0002", titulo: "Umidade da biomassa acima da faixa de projeto da caldeira", categoria: "Técnico", subcategoria: "Interfaces",
    donoId: 14, identificadoEm: "2026-06-15", causa: "Fornecimento de cavaco sem pátio coberto nem secagem prévia", consequencia: "Perda de rendimento e instabilidade da combustão na operação",
    descricao: "O projeto da caldeira admite até 45% de umidade; a biomassa regional chega com 50 a 55% no período chuvoso.", gatilho: "Laudo da biomassa com umidade acima de 45%",
    inerente: { p: 3, i: 4, dimensoes: dim(2, 3, 2, 1, 2, 1) }, residual: { p: 2, i: 4, dimensoes: dim(2, 3, 2, 1, 2, 1) },
    dimensao: "Escopo", impactoPrazoDias: 0, impactoCustoCentavos: mi(0.6), estrategia: "Mitigar",
    plano: "Especificar a umidade máxima no contrato de fornecimento de biomassa e prever pátio coberto com 3 dias de estoque (SM-CB-2026-0001).",
    severidadeAlvo: "moderado", prazoAlvo: "2026-12-15", custoRespostaCentavos: mi(0.18), responsavelPlanoId: 14, cadenciaDias: 30, ultimaRevisao: "2026-09-10", proximaRevisao: "2026-10-10", situacao: "Em tratamento",
    revisoes: [rev("2026-09-10", 14, "revisao", "Sem mudança", 8, 8, 2, 4, "SM do silo aprovada; contrato de biomassa em negociação."),
      rev("2026-08-12", 14, "residual", "Risco reduzido", 12, 8, 2, 4, "Silo ampliado aprovado (SM-CB-2026-0001)."),
      rev("2026-06-15", 1, "inerente", "Avaliação inicial", null, 12, 3, 4, "Identificado na revisão do projeto básico.")] });
  risco({ projetoId: 2, codigo: "RSK-CB-2026-0003", titulo: "Exigência adicional do órgão ambiental para emissões de material particulado", categoria: "Regulatório", subcategoria: "Licenciamento",
    donoId: 4, identificadoEm: "2026-09-08", origemTipo: "Ata de reunião", ataId: ATA["CB-2026-0002"], origem: "Ata CB-2026-0002",
    causa: "Revisão da norma estadual de emissões em consulta pública", consequencia: "Troca do precipitador por filtro de mangas ou campo adicional",
    descricao: "A consulta pública propõe limite de 30 mg/Nm³, abaixo dos 50 mg/Nm³ garantidos pelo precipitador contratado.", gatilho: "Publicação da norma com o novo limite",
    inerente: { p: 3, i: 3, dimensoes: dim(2, 3, 2, 1, 2, 3) }, residual: null, dimensao: "Custo", impactoPrazoDias: 20, impactoCustoCentavos: mi(0.8),
    estrategia: null, plano: null, severidadeAlvo: null, prazoAlvo: null, responsavelPlanoId: null, cadenciaDias: 60, ultimaRevisao: "2026-09-08", proximaRevisao: "2026-10-15", situacao: "Em análise",
    revisoes: [rev("2026-09-08", 4, "inerente", "Avaliação inicial", null, 9, 3, 3, "Consulta pública da norma de emissões.")] });
  risco({ projetoId: 2, codigo: "RSK-CB-2026-0004", titulo: "Pré-montagem em solo dos módulos da caldeira", natureza: "Oportunidade", categoria: "Recursos", subcategoria: "Equipamentos",
    donoId: 16, identificadoEm: "2026-08-20", origemTipo: "Ata de reunião", ataId: ATA["CB-2026-0001"], origem: "Ata CB-2026-0001",
    causa: "Área livre ao lado da casa de caldeira e guindaste de 300 t já contratado", consequencia: "Recuperação de até 25 dias na montagem de pressão",
    descricao: "Pré-montar em solo os módulos das paredes d'água e içar por conjunto reduz o trabalho em altura e o prazo.", gatilho: "Chegada dos primeiros painéis de parede d'água",
    inerente: { p: 3, i: 4, dimensoes: dim(4, 2, 1, 2, 1, 1) }, residual: { p: 4, i: 4, dimensoes: dim(4, 2, 1, 2, 1, 1) },
    dimensao: "Prazo", impactoPrazoDias: 25, impactoCustoCentavos: mi(0.25), estrategia: "Explorar",
    plano: "Detalhar a sequência de pré-montagem com a Pi Montagens e registrar a SM de resequenciamento (SM-CB-2026-0003).",
    severidadeAlvo: "alto", prazoAlvo: "2026-11-30", custoRespostaCentavos: mi(0.04), responsavelPlanoId: 16, cadenciaDias: 15, ultimaRevisao: "2026-09-17", proximaRevisao: "2026-10-02", situacao: "Monitorado",
    revisoes: [rev("2026-09-17", 16, "residual", "Oportunidade ampliada", 12, 16, 4, 4, "Guindaste de 300 t confirmado na janela da pré-montagem."),
      rev("2026-08-20", 1, "inerente", "Avaliação inicial", null, 12, 3, 4, "Identificada na coordenação mensal.")] });
  risco({ projetoId: 2, codigo: "RSK-CB-2026-0005", titulo: "Chuvas intensas durante as fundações", categoria: "Ambiental", subcategoria: "Clima",
    donoId: 18, identificadoEm: "2026-04-10", causa: "Fundações programadas para o início do período chuvoso", consequencia: "Paralisação das escavações e da concretagem",
    descricao: "Blocos de estacas em área sem drenagem definitiva.", gatilho: "Previsão de mais de 50 mm em 24 h",
    inerente: { p: 3, i: 2, dimensoes: dim(2, 2, 1, 1, 1, 1) }, residual: { p: 2, i: 2, dimensoes: dim(2, 2, 1, 1, 1, 1) },
    dimensao: "Prazo", impactoPrazoDias: 8, impactoCustoCentavos: mi(0.08), estrategia: "Mitigar", plano: "Drenagem provisória e cobertura das frentes de concretagem.",
    severidadeAlvo: "baixo", prazoAlvo: "2026-11-30", custoRespostaCentavos: mi(0.02), responsavelPlanoId: 18, cadenciaDias: 90, ultimaRevisao: "2026-06-22", proximaRevisao: "2026-09-20", situacao: "Monitorado",
    revisoes: [rev("2026-06-22", 18, "residual", "Risco reduzido", 6, 4, 2, 2, "Drenagem provisória concluída."), rev("2026-04-10", 1, "inerente", "Avaliação inicial", null, 6, 3, 2, "Workshop de riscos da obra.")] });

  risco({ projetoId: 3, codigo: "RSK-TR-2026-0001", titulo: "Rocha não indicada nas sondagens na escavação da bacia", categoria: "Técnico", subcategoria: "Fundações",
    donoId: 18, identificadoEm: "2026-06-10", causa: "Sondagens a percussão do edital sem investigação rotativa", consequencia: "Desmonte de rocha, aditivo ao contrato civil e atraso da bacia",
    descricao: "Área próxima a afloramentos rochosos; as sondagens pararam no impenetrável sem caracterizar o material.", gatilho: "Escavação atingir material impenetrável acima da cota de fundo",
    inerente: { p: 3, i: 4, dimensoes: dim(3, 4, 1, 2, 1, 1) }, residual: { p: 3, i: 4, dimensoes: dim(3, 4, 1, 2, 1, 1) },
    dimensao: "Custo", impactoPrazoDias: 15, impactoCustoCentavos: mi(0.28), estrategia: "Aceitar",
    plano: "Aceito com reserva de contingência; sondagem rotativa não realizada por prazo da licitação.", severidadeAlvo: "alto", prazoAlvo: "2026-08-31", responsavelPlanoId: 18,
    cadenciaDias: 30, ultimaRevisao: "2026-08-24", proximaRevisao: null, situacao: "Materializado",
    encerramento: { motivo: "Materializado", data: "2026-08-24", porId: 15, impactoRealPrazoDias: 15, impactoRealCustoCentavos: mi(0.28), smRef: "SM-TR-2026-0001",
      licao: "Sondagem rotativa na área da bacia antes da licitação civil.", licaoRef: "LA-TR-2026-0001" },
    revisoes: [rev("2026-08-24", 18, "revisao", "Materializado", 12, 12, 3, 4, "Rocha sã a partir da cota 2,1 m; claim da contratada notificado."),
      rev("2026-06-10", 1, "inerente", "Avaliação inicial", null, 12, 3, 4, "Identificado na análise das sondagens.")] });
  risco({ projetoId: 3, codigo: "RSK-TR-2026-0002", titulo: "Interferência com a operação da torre existente nas interligações", categoria: "Técnico", subcategoria: "Interfaces",
    donoId: 15, identificadoEm: "2026-09-10", origemTipo: "Ata de reunião", ataId: ATA["TR-2026-0001"], origem: "Ata TR-2026-0001",
    causa: "Interligações exigem parada da torre existente, sem janela definida pela operação", consequencia: "Atraso do comissionamento e perda de produção na parada",
    descricao: "A operação só admite parada de 36 h; as interligações foram planejadas para 60 h.", gatilho: "Janela de parada não acordada até 30 dias antes das interligações",
    inerente: { p: 3, i: 4, dimensoes: dim(4, 2, 1, 1, 3, 1) }, residual: { p: 2, i: 4, dimensoes: dim(4, 2, 1, 1, 3, 1) },
    dimensao: "Prazo", impactoPrazoDias: 20, impactoCustoCentavos: mi(0.35), estrategia: "Mitigar",
    plano: "Pré-fabricar os spools das interligações e executar em duas paradas curtas acordadas com a operação.",
    severidadeAlvo: "moderado", prazoAlvo: "2026-12-15", custoRespostaCentavos: mi(0.05), responsavelPlanoId: 15, cadenciaDias: 60, ultimaRevisao: "2026-09-17", proximaRevisao: "2026-11-16", situacao: "Em tratamento",
    revisoes: [rev("2026-09-17", 15, "residual", "Risco reduzido", 12, 8, 2, 4, "Plano de duas paradas aceito pela operação em princípio."),
      rev("2026-09-10", 1, "inerente", "Avaliação inicial", null, 12, 3, 4, "Identificado na coordenação da obra.")] });
  risco({ projetoId: 3, codigo: "RSK-TR-2026-0003", titulo: "Atraso na entrega dos inversores dos ventiladores", categoria: "Suprimentos", subcategoria: "Fornecedores",
    donoId: 7, identificadoEm: "2026-08-24", origemTipo: "Plano de compras", origem: "Plano de compras",
    causa: "Equalização técnica atrasada e prazo de fabricação de 95 a 130 dias", consequencia: "Ventiladores sem acionamento no comissionamento",
    descricao: "A adjudicação prevista para outubro deixa folga de uma semana para o comissionamento.", gatilho: "Adjudicação após 15/10/2026",
    inerente: { p: 3, i: 3, dimensoes: dim(3, 1, 1, 1, 1, 1) }, residual: { p: 3, i: 3, dimensoes: dim(3, 1, 1, 1, 1, 1) },
    dimensao: "Prazo", impactoPrazoDias: 15, impactoCustoCentavos: mi(0.06), estrategia: "Mitigar",
    plano: "Antecipar a equalização técnica e aceitar partida provisória com inversor de aluguel se necessário.",
    severidadeAlvo: "baixo", prazoAlvo: "2026-11-30", custoRespostaCentavos: mi(0.02), responsavelPlanoId: 7, cadenciaDias: 60, ultimaRevisao: "2026-08-24", proximaRevisao: "2026-09-15", situacao: "Em tratamento",
    revisoes: [rev("2026-08-24", 7, "inerente", "Avaliação inicial", null, 9, 3, 3, "Identificado no plano de compras.")] });
  risco({ projetoId: 3, codigo: "RSK-TR-2026-0004", titulo: "Enchimento de alta eficiência reduz a potência dos ventiladores", natureza: "Oportunidade", categoria: "Custo", subcategoria: "Estimativa",
    donoId: 6, identificadoEm: "2026-09-02", causa: "Proposta técnica do fornecedor com enchimento de filme de nova geração", consequencia: "Redução do consumo de energia na operação e do custo dos inversores",
    descricao: "O enchimento proposto permite motores de 75 kW no lugar de 90 kW.", gatilho: "Aprovação do enchimento pela engenharia do cliente",
    inerente: { p: 2, i: 3, dimensoes: dim(1, 3, 1, 1, 1, 1) }, residual: null, dimensao: "Custo", impactoPrazoDias: 0, impactoCustoCentavos: mi(0.05),
    estrategia: null, plano: null, severidadeAlvo: null, prazoAlvo: null, responsavelPlanoId: null, cadenciaDias: 60, ultimaRevisao: "2026-09-02", proximaRevisao: "2026-10-30", situacao: "Em análise",
    revisoes: [rev("2026-09-02", 6, "inerente", "Avaliação inicial", null, 6, 2, 3, "Identificada na revisão da proposta técnica.")] });
  risco({ projetoId: 3, codigo: "RSK-TR-2026-0005", titulo: "Queda de altura na montagem da estrutura da torre", categoria: "SMS", subcategoria: "Segurança do trabalho", riscoVida: true,
    donoId: 10, identificadoEm: "2026-09-10", origemTipo: "Ata de reunião", ataId: ATA["TR-2026-0001"], origem: "Ata TR-2026-0001",
    causa: "Montagem de perfis de PRFV a 14 m de altura sem pontos de ancoragem na estrutura", consequencia: "Acidente grave ou fatal",
    descricao: "A estrutura em PRFV não admite solda de pontos de ancoragem; a linha de vida depende de estrutura provisória.", gatilho: "Plano de montagem sem linha de vida aprovado",
    inerente: { p: 3, i: 5, dimensoes: dim(2, 2, 1, 5, 4, 3) }, residual: { p: 2, i: 5, dimensoes: dim(2, 2, 1, 5, 4, 3) },
    dimensao: "SMS", impactoPrazoDias: 10, impactoCustoCentavos: mi(0.1), estrategia: "Mitigar",
    plano: "Linha de vida em estrutura provisória metálica, plataforma elevatória e pré-montagem das seções em solo.",
    severidadeAlvo: "moderado", prazoAlvo: "2026-10-30", custoRespostaCentavos: mi(0.06), responsavelPlanoId: 10,
    aprovacao: { exigida: true, situacao: "Aprovado", porId: 1, data: "2026-09-12" }, cadenciaDias: 30, ultimaRevisao: "2026-09-12", proximaRevisao: "2026-10-12", situacao: "Em tratamento",
    revisoes: [rev("2026-09-12", 10, "residual", "Risco reduzido", 15, 10, 2, 5, "Plano de montagem com linha de vida aprovado."),
      rev("2026-09-10", 1, "inerente", "Avaliação inicial", null, 15, 3, 5, "Identificado na coordenação da obra.")] });
  [[2, "2026-04", 6], [2, "2026-05", 22], [2, "2026-06", 34], [2, "2026-07", 34], [2, "2026-08", 44],
   [3, "2026-06", 12], [3, "2026-07", 12], [3, "2026-08", 21]].forEach(function (e) { M.riscosEvolucao.push({ projetoId: e[0], mes: e[1], scoreResidual: e[2] }); });

  /* ======================================================================
     06 Gestão da Qualidade
     ====================================================================== */
  [
    { projetoId: 2, codigo: "RNC-CB-2026-0001", data: "2026-07-14", origem: "Inspeção", origemRef: null, disciplina: "Civil", empresaId: 17, descricao: "Recobrimento de armadura abaixo do mínimo no bloco B-14.",
      severidade: "Maior", contencao: "Concretagem do bloco B-14 suspensa.", responsavelId: 18, disposicao: "Reparo", concessao: { referencia: "Carta MHS-CB-ENG-021 (reparo com argamassa polimérica)", data: "2026-07-22" },
      metodo: "5 porquês", causaRaiz: "Espaçadores de altura errada no lote entregue.", prazo: "2026-08-13", encerramento: "2026-08-10", situacao: "Encerrada", custoNaoQualidadeCentavos: 950000, abertaPorId: 9,
      eficacia: { data: "2026-08-10", eficaz: true, texto: "Espaçadores conferidos no recebimento; quatro blocos seguintes aprovados na liberação de armadura.", porId: 9 }, licaoRef: null },
    { projetoId: 2, codigo: "RNC-CB-2026-0002", data: "2026-09-11", origem: "Inspeção de fabricação", origemRef: "INS-2026-0304", disciplina: "Mecânica", empresaId: 14,
      descricao: "Certificado de material das chapas do tubulão com composição divergente da especificação.", severidade: "Crítica",
      contencao: "Chapas segregadas no fornecedor; soldagem do tubulão suspensa.", responsavelId: 7, disposicao: null, concessao: null,
      metodo: null, causaRaiz: null, prazo: "2026-09-26", encerramento: null, situacao: "Em análise de causa", custoNaoQualidadeCentavos: 0, abertaPorId: 9, licaoRef: null },
    { projetoId: 2, codigo: "RNC-CB-2026-0003", data: "2026-09-02", origem: "Inspeção", origemRef: "INS-2026-0303", disciplina: "Civil", empresaId: 17,
      descricao: "Cota de topo da base BS-610-02 8 mm abaixo do projeto.", severidade: "Menor",
      contencao: "Posicionamento da coluna C-02 bloqueado (punch PL-CB-2026-0002).", responsavelId: 18, disposicao: "Reparo", concessao: { referencia: "Carta MHS-CB-ENG-034 (correção com graute)", data: "2026-09-09" },
      metodo: "5 porquês", causaRaiz: "Nível de referência da topografia tomado de marco deslocado.", prazo: "2026-10-17", encerramento: null, situacao: "Ação corretiva", custoNaoQualidadeCentavos: 180000, abertaPorId: 9, licaoRef: null },
    { projetoId: 3, codigo: "RNC-TR-2026-0001", data: "2026-09-04", origem: "Inspeção", origemRef: "INS-2026-0306", disciplina: "Civil", empresaId: 17, descricao: "Junta de concretagem do lastro da célula 1 fora da posição de projeto.",
      severidade: "Menor", contencao: "Concretagem da célula 2 condicionada ao plano de juntas.", responsavelId: 18, disposicao: "Usar como está", concessao: { referencia: "Parecer estrutural MHS-TR-EST-007", data: "2026-09-12" },
      metodo: "5 porquês", causaRaiz: "Plano de concretagem sem a posição das juntas.", prazo: "2026-10-19", encerramento: null, situacao: "Ação corretiva", custoNaoQualidadeCentavos: 120000, abertaPorId: 9, licaoRef: null }
  ].forEach(function (r) { incluir("rncs", r); });
  [
    { projetoId: 2, origem: "RNC", origemRef: "RNC-CB-2026-0003", item: "1", grupo: "Ação corretiva", tipo: "Ação", assunto: "Corrigir a cota da base BS-610-02 com graute",
      descricao: "Graute de correção e nova topografia antes do posicionamento da coluna.", solicitanteId: 9, responsavelId: 18, prevista: "2026-10-03", replanejada: null, conclusao: null },
    { projetoId: 3, origem: "RNC", origemRef: "RNC-TR-2026-0001", item: "1", grupo: "Ação corretiva", tipo: "Ação", assunto: "Incluir a posição das juntas no plano de concretagem da bacia",
      descricao: "Plano de concretagem revisado com as juntas das células 2 e 3.", solicitanteId: 9, responsavelId: 18, prevista: "2026-09-18", replanejada: null, conclusao: "2026-09-17" }
  ].forEach(function (a) { incluir("acoes", a); });
  function pts(lista) { return lista.map(function (p, k) { return { id: k + 1, atividade: p[0], tipo: p[1], criterio: p[2], referencia: p[3], responsavel: p[4] || "Contratada" }; }); }
  var ITP = {};
  [
    [2, "ITP-CB-CIV-01", "Civil", "Concreto das fundações da caldeira", 17, 1, "2026-03-10", true, [
      ["Topografia das bases", "W", "Cota de topo com tolerância de ±3 mm", "ET-CB-CIV-002"],
      ["Liberação de armadura", "H", "Bitolas, espaçamentos e recobrimento de projeto", "NBR 14931"],
      ["Posição dos chumbadores", "H", "Gabarito conferido com o desenho do fabricante", "ET-CB-CIV-002"],
      ["Liberação de concretagem", "H", "Fôrmas, armadura e embutidos liberados", "NBR 14931"],
      ["Ensaios de corpo de prova", "R", "fck aos 28 dias igual ou acima do projeto", "NBR 5739", "Laboratório"]]],
    [2, "ITP-CB-MEC-01", "Mecânica", "Montagem das partes de pressão", 14, 0, "2026-05-20", true, [
      ["Inspeção de fabricação das paredes d'água", "W", "Dimensional e soldas conforme projeto aprovado", "ASME I", "Fabricante"],
      ["Certificados de material", "R", "Composição e propriedades conforme especificação", "ASME II", "Fabricante"],
      ["Montagem do tubulão superior", "H", "Nivelamento e posição conforme projeto", "Manual do fabricante"],
      ["Radiografia das soldas de pressão", "H", "Sem descontinuidade acima do critério", "ASME I", "Laboratório"],
      ["Teste hidrostático da caldeira", "H", "1,5 vez a PMTA sem vazamento", "NR-13 e ASME I", "Fiscalização"],
      ["Liberação pelo profissional habilitado (NR-13)", "H", "Prontuário e relatório de inspeção inicial", "NR-13", "Cliente"]]],
    [3, "ITP-TR-CIV-01", "Civil", "Bacia de água fria", 17, 0, "2026-07-01", true, [
      ["Liberação da escavação", "H", "Cota de fundo e solo conferidos", "ET-TR-CIV-001", "Fiscalização"],
      ["Liberação de concretagem do lastro", "H", "Juntas na posição do plano", "ET-TR-CIV-001"],
      ["Juntas de dilatação e veda-juntas", "W", "Veda-junta contínuo e fixado", "ET-TR-CIV-003"],
      ["Estanqueidade da bacia", "H", "Perda até 0,5% do volume em 24 h", "NBR 6118", "Fiscalização"]]]
  ].forEach(function (i) { ITP[i[1]] = incluir("itps", { projetoId: i[0], codigo: i[1], disciplina: i[2], titulo: i[3], empresaId: i[4], revisao: i[5], data: i[6], aprovadoCliente: i[7], aprovacao: i[7] ? { referencia: "Carta MHS-" + i[1].split("-")[1] + "-QUA-00" + (i[5] + 1), data: i[6], porId: 9 } : null, pontos: pts(i[8]) }).id; });
  [
    [2, "INS-2026-0301", "ITP-CB-CIV-01", 2, "Liberação de armadura", "H", "2026-09-03", 17, "Aprovado"],
    [2, "INS-2026-0302", "ITP-CB-CIV-01", 4, "Liberação de concretagem", "H", "2026-09-10", 17, "Aprovado com ressalva", null, "Limpeza de fôrma refeita antes do lançamento."],
    [2, "INS-2026-0303", "ITP-CB-CIV-01", 1, "Topografia das bases", "W", "2026-09-02", 17, "Reprovado", "RNC-CB-2026-0003", "Base BS-610-02 com cota 8 mm abaixo."],
    [2, "INS-2026-0304", "ITP-CB-MEC-01", 1, "Inspeção de fabricação das paredes d'água", "W", "2026-09-11", 14, "Reprovado", "RNC-CB-2026-0002", "Certificado das chapas divergente da especificação."],
    [2, "INS-2026-0291", "ITP-CB-CIV-01", 2, "Liberação de armadura", "H", "2026-07-13", 17, "Reprovado", "RNC-CB-2026-0001", "Recobrimento abaixo do mínimo no B-14."],
    [2, "INS-2026-0295", "ITP-CB-CIV-01", 5, "Ensaios de corpo de prova", "R", "2026-08-20", 17, "Aprovado"],
    [3, "INS-2026-0305", "ITP-TR-CIV-01", 1, "Liberação da escavação", "H", "2026-09-01", 17, "Aprovado"],
    [3, "INS-2026-0306", "ITP-TR-CIV-01", 2, "Liberação de concretagem do lastro", "H", "2026-09-04", 17, "Reprovado", "RNC-TR-2026-0001", "Junta fora da posição do projeto."]
  ].forEach(function (i) {
    incluir("inspecoesQualidade", { projetoId: i[0], codigo: i[1], itpId: ITP[i[2]], pontoId: i[3], ponto: i[4], tipoPonto: i[5], data: i[6], empresaId: i[7], inspetorId: 9, resultado: i[8],
      rncRef: i[9] || null, observacao: i[10] || "" });
  });
  incluir("auditorias", { projetoId: 2, codigo: "AUD-CB-2026-01", tipo: "Contratada", auditadoId: 17, escopo: "Controle tecnológico do concreto das fundações", data: "2026-08-05",
    situacao: "Realizada", realizadaEm: "2026-08-05", itensVerificados: 30, itensConformes: 26, auditorId: 9, criterio: "ET-CB-CIV-002 e NBR 12655",
    constatacoes: [
      { tipo: "Observação", descricao: "Espaçadores sem conferência de altura no recebimento.", requisito: "NBR 14931" },
      { tipo: "Observação", descricao: "Registro de cura sem assinatura do encarregado.", requisito: "ET-CB-CIV-002" },
      { tipo: "Observação", descricao: "Corpos de prova sem identificação do caminhão.", requisito: "NBR 5738" },
      { tipo: "Oportunidade de melhoria", descricao: "Checklist de liberação de armadura em tablet.", requisito: "" }] });
  incluir("auditorias", { projetoId: 2, codigo: "AUD-CB-2026-02", tipo: "Fornecedor", auditadoId: 14, escopo: "Qualificação de soldagem das partes de pressão", data: "2026-10-20",
    situacao: "Planejada", auditorId: 9, criterio: "ASME I e ASME IX" });
  incluir("auditorias", { projetoId: 3, codigo: "AUD-TR-2026-01", tipo: "Fornecedor", auditadoId: 16, escopo: "Fabricação dos perfis de PRFV", data: "2026-09-09",
    situacao: "Realizada", realizadaEm: "2026-09-09", itensVerificados: 24, itensConformes: 23, auditorId: 9, criterio: "ET-TR-MEC-001",
    constatacoes: [{ tipo: "Observação", descricao: "Registro de cura da resina sem temperatura ambiente.", requisito: "ET-TR-MEC-001" }] });

  /* ======================================================================
     07 HSE: HHT, ocorrências (fixas + geradas com semente própria), consolidado mensal e APR
     ====================================================================== */
  var HORAS_MES = 218;
  var HHT_PROJ = {
    2: { meses: ["2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"],
         efetivo: { 17: [20, 45, 70, 90, 110, 120, 110], 15: [0, 0, 0, 0, 0, 25, 60], 5: [4, 4, 4, 4, 4, 4, 4], 13: [6, 6, 8, 8, 8, 10, 10] } },
    3: { meses: ["2026-06", "2026-07", "2026-08", "2026-09"],
         efetivo: { 17: [0, 15, 45, 60], 16: [0, 0, 0, 10], 5: [3, 3, 3, 3], 13: [4, 4, 5, 5] } }
  };
  Object.keys(HHT_PROJ).forEach(function (pid) {
    var h = HHT_PROJ[pid];
    Object.keys(h.efetivo).forEach(function (emp) {
      h.efetivo[emp].forEach(function (ef, i) { if (ef > 0) M.hht.push({ projetoId: Number(pid), mes: h.meses[i], empresaId: Number(emp), efetivoMedio: ef, hht: ef * HORAS_MES }); });
    });
  });
  var sem2 = 3030;
  function rnd() {
    sem2 |= 0; sem2 = (sem2 + 0x6D2B79F5) | 0;
    var t = Math.imul(sem2 ^ (sem2 >>> 15), 1 | sem2);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }
  function escolher(l) { return l[Math.floor(rnd() * l.length)]; }
  function dois(n) { return (n < 10 ? "0" : "") + n; }
  var AREAS_HSE = { 2: ["Caldeira 610", "Alimentação 620", "Tratamento de gases 630", "Canteiro"], 3: ["Bacia 710", "Casa de bombas 720", "Canteiro"] };
  var TEXTOS = {
    "Primeiros socorros": ["Corte superficial na mão ao manusear fôrma.", "Partícula no olho durante corte de vergalhão.", "Escoriação no antebraço em contato com armadura."],
    "Dano material": ["Caminhão-betoneira danificou a cerca provisória.", "Retroescavadeira atingiu tubulação provisória de água.", "Queda de painel de fôrma durante o içamento."],
    "Quase acidente": ["Material solto em altura sem amarração.", "Pessoa sob carga suspensa durante içamento.", "Escada apoiada em superfície instável.",
      "Abertura de vala sem sinalização.", "Veículo acima do limite de velocidade na via interna.", "Trabalho a quente sem vigia de incêndio."]
  };
  var CAUSAS = ["Procedimento não seguido", "Condição insegura do local", "Falha de planejamento da tarefa", "EPI inadequado", "Falta de sinalização"];
  var FUNCOES = ["Armador", "Carpinteiro", "Montador", "Ajudante", "Operador de equipamento"];
  function gerarOcorrencia(pid, tipo) {
    var regs = M.hht.filter(function (r) { return r.projetoId === pid; });
    var total = regs.reduce(function (s, r) { return s + r.hht; }, 0), alvo = rnd() * total, acc = 0, base = regs[regs.length - 1];
    for (var i = 0; i < regs.length; i++) { acc += regs[i].hht; if (alvo <= acc) { base = regs[i]; break; } }
    var ano = Number(base.mes.slice(0, 4)), mes = Number(base.mes.slice(5, 7));
    var ultimo = base.mes === "2026-09" ? 24 : new Date(ano, mes, 0).getDate();
    return { projetoId: pid, dataHora: base.mes + "-" + dois(1 + Math.floor(rnd() * ultimo)) + "T" + dois(7 + Math.floor(rnd() * 10)) + ":" + dois(Math.floor(rnd() * 60)),
      area: escolher(AREAS_HSE[pid]), empresaId: base.empresaId, tipo: tipo, descricao: escolher(TEXTOS[tipo]),
      funcao: tipo === "Primeiros socorros" ? escolher(FUNCOES) : null, pessoasEnvolvidas: tipo === "Primeiros socorros" ? 1 : 0,
      gravidadeReal: tipo === "Dano material" ? 2 : 1, potencial: { p: 1 + Math.floor(rnd() * 3), i: 1 + Math.floor(rnd() * 3) },
      hipo: false, diasPerdidos: 0, diasDebitados: 0, cat: false, causaImediata: escolher(CAUSAS), comunicacaoHoras: 1 + Math.floor(rnd() * 6), ambiental: false };
  }
  var OCOR = {
    2: { fixas: [
      { projetoId: 2, dataHora: "2026-07-08T10:20", area: "Caldeira 610", empresaId: 17, tipo: "Tratamento médico", descricao: "Corte na mão com sutura ao desmontar fôrma metálica.", funcao: "Carpinteiro",
        pessoasEnvolvidas: 1, gravidadeReal: 2, potencial: { p: 2, i: 3 }, hipo: false, diasPerdidos: 0, diasDebitados: 0, cat: false, causaImediata: "EPI inadequado", comunicacaoHoras: 3, ambiental: false },
      { projetoId: 2, dataHora: "2026-09-09T14:35", area: "Caldeira 610", empresaId: 15, tipo: "Quase acidente", descricao: "Queda de chapa de ligação de 8 m de altura durante o içamento de coluna, em área isolada.",
        funcao: null, pessoasEnvolvidas: 0, gravidadeReal: 1, potencial: { p: 3, i: 5 }, hipo: true, diasPerdidos: 0, diasDebitados: 0, cat: false, causaImediata: "Falha de planejamento da tarefa",
        comunicacaoHoras: 1, metodo: "Árvore de causas", ambiental: false, situacaoFixa: "Em investigação" },
      { projetoId: 2, dataHora: "2026-06-11T09:40", area: "Canteiro", empresaId: 17, tipo: "Ambiental", subtipo: "Vazamento", descricao: "Vazamento de 10 L de diesel no abastecimento da escavadeira.",
        funcao: null, pessoasEnvolvidas: 0, gravidadeReal: 1, potencial: { p: 2, i: 2 }, hipo: false, diasPerdidos: 0, diasDebitados: 0, cat: false, causaImediata: "Procedimento não seguido",
        comunicacaoHoras: 2, ambiental: true, severidadeAmbiental: "Baixa" } ],
      gerar: { "Primeiros socorros": 3, "Dano material": 6, "Quase acidente": 34 } },
    3: { fixas: [
      { projetoId: 3, dataHora: "2026-09-16T15:10", area: "Bacia 710", empresaId: 17, tipo: "Trabalho restrito", descricao: "Torção de joelho ao descer do talude da escavação sem escada; retorno com restrição, sem afastamento.",
        funcao: "Ajudante", pessoasEnvolvidas: 1, gravidadeReal: 2, potencial: { p: 2, i: 3 }, hipo: false, diasPerdidos: 0, diasDebitados: 0, cat: true, causaImediata: "Condição insegura do local",
        comunicacaoHoras: 2, ambiental: false } ],
      gerar: { "Primeiros socorros": 1, "Dano material": 2, "Quase acidente": 11 } }
  };
  var refData = new Date((M.referencia || "2026-09-25") + "T00:00:00");
  var idOc = proximo("ocorrencias");
  [2, 3].forEach(function (pid) {
    var cfg = OCOR[pid], lista = cfg.fixas.slice();
    Object.keys(cfg.gerar).forEach(function (tipo) { for (var n = 0; n < cfg.gerar[tipo]; n++) lista.push(gerarOcorrencia(pid, tipo)); });
    lista.sort(function (a, b) { return a.dataHora < b.dataHora ? -1 : a.dataHora > b.dataHora ? 1 : 0; });
    var pad = pid === 2 ? "CB-2026" : "TR-2026";
    lista.forEach(function (o, i) {
      o.id = idOc++;
      o.codigo = "OCR-" + pad + "-" + ("000" + (i + 1)).slice(-4);
      var idade = Math.round((refData - new Date(o.dataHora)) / 86400000);
      o.situacao = o.situacaoFixa || (idade > 40 ? "Encerrada" : idade > 15 ? "Em tratamento" : idade > 3 ? "Ações definidas" : "Registrada");
      delete o.situacaoFixa;
      M.ocorrencias.push(o);
    });
  });
  var MENSAL = {
    2: { desvios: [8, 14, 20, 26, 30, 36, 40], dds: [[10, 9], [18, 17], [24, 22], [28, 27], [30, 28], [34, 32], [36, 33]], insp: [[30, 26], [50, 44], [70, 62], [90, 80], [100, 88], [120, 104], [130, 112]] },
    3: { desvios: [2, 6, 12, 16], dds: [[4, 4], [10, 9], [16, 15], [20, 19]], insp: [[10, 10], [24, 22], [40, 37], [52, 48]] }
  };
  [2, 3].forEach(function (pid) {
    HHT_PROJ[pid].meses.forEach(function (mes, i) {
      var hhtMes = M.hht.filter(function (r) { return r.projetoId === pid && r.mes === mes; }).reduce(function (s, r) { return s + r.hht; }, 0), m = MENSAL[pid];
      M.hseMensal.push({ projetoId: pid, mes: mes, desvios: m.desvios[i], observacoes: Math.round(hhtMes * 38 / 10000), ddsProgramados: m.dds[i][0], ddsRealizados: m.dds[i][1],
        itensInspecionados: m.insp[i][0], itensConformes: m.insp[i][1] });
    });
  });
  incluir("analisesRisco", { projetoId: 2, codigo: "APR-CB-2026-004", tipo: "APR", area: "Caldeira 610", titulo: "Içamento das colunas e vigas da estrutura da caldeira", data: "2026-08-26",
    participantesIds: [17, 10, 12], recomendacoes: [
      { descricao: "Plano de rigging assinado por engenheiro habilitado.", responsavelId: 17, prazo: "2026-08-28", situacao: "Fechada" },
      { descricao: "Amarração das chapas de ligação antes do içamento.", responsavelId: 17, prazo: "2026-09-18", situacao: "Aberta" },
      { descricao: "Isolamento de área com raio de 1,5 vez a altura de içamento.", responsavelId: 17, prazo: "2026-09-04", situacao: "Fechada" } ] });
  incluir("analisesRisco", { projetoId: 2, codigo: "HAZOP-CB-2026-01", tipo: "HAZOP", area: "Caldeira 610", titulo: "Sistema de combustão e alimentação de biomassa", data: "2026-07-22",
    participantesIds: [6, 8, 10, 14], recomendacoes: [
      { descricao: "Intertravamento de baixa pressão de ar de combustão com corte da alimentação.", responsavelId: 6, prazo: "2026-10-30", situacao: "Aberta" },
      { descricao: "Detector de chama redundante no queimador de partida.", responsavelId: 6, prazo: "2026-10-30", situacao: "Aberta" },
      { descricao: "Válvula rotativa corta-chamas na descarga da rosca dosadora.", responsavelId: 6, prazo: "2026-09-15", situacao: "Fechada" } ] });
  incluir("analisesRisco", { projetoId: 3, codigo: "APR-TR-2026-002", tipo: "APR", area: "Bacia 710", titulo: "Escavação e desmonte de rocha da bacia", data: "2026-09-14",
    participantesIds: [18, 10, 12], recomendacoes: [
      { descricao: "Plano de fogo com raio de isolamento e horários combinados com a operação.", responsavelId: 18, prazo: "2026-09-25", situacao: "Aberta" },
      { descricao: "Escoramento dos taludes acima de 1,25 m e escadas de acesso a cada 15 m.", responsavelId: 18, prazo: "2026-09-18", situacao: "Aberta" } ] });

  /* ======================================================================
     08 Governança: mudanças e lições
     ====================================================================== */
  [
    { projetoId: 2, codigo: "SM-CB-2026-0001", titulo: "Silo de biomassa com capacidade ampliada para 3 dias de estoque", tipo: "Escopo", origem: "Cliente", prioridade: "Normal", solicitanteId: 14, dataSolicitacao: "2026-07-20",
      descricao: "Mitigação do risco de umidade da biomassa (RSK-CB-2026-0002): estoque coberto para 3 dias de operação.",
      impacto: { custoCentavos: 18000000, prazoDias: 0, escopo: "Silo de 900 m³ no lugar de 600 m³", qualidade: "Sem impacto", riscos: "Reduz RSK-CB-2026-0002", sms: "Sem impacto", contrato: "Aditivo do pedido PED-2026-0012",
        afetaMarcoContratual: false, eacItens: ["2.1.2"], atividades: "Fundações e montagem do silo", dataAnalise: "2026-08-03", analistaId: 13 },
      fonteRecurso: "Reserva de contingência", alcada: "Gerente do projeto", decisao: { data: "2026-08-12", resultado: "Aprovada", participantesIds: [14], condicoes: "", justificativa: "Custo dentro da alçada do gerente e coberto pela reserva de contingência." },
      implementacao: { inicio: "2026-08-17" }, situacao: "Em implementação", encerramento: null },
    { projetoId: 2, codigo: "SM-CB-2026-0002", titulo: "Refratário da fornalha em concreto de baixo cimento", tipo: "Qualidade/Especificação", origem: "Engenharia", prioridade: "Normal", solicitanteId: 6, dataSolicitacao: "2026-08-25",
      descricao: "Troca do tijolo refratário por concreto refratário de baixo cimento, com menor prazo de secagem.",
      impacto: { custoCentavos: 32000000, prazoDias: -10, escopo: "Sem impacto", qualidade: "Nova especificação do refratário", riscos: "Reduz RSK-CB-2026-0001", sms: "Sem impacto", contrato: "Aditivo do pedido PED-2026-0011",
        afetaMarcoContratual: true, eacItens: ["2.1.1"], atividades: "Montagem do refratário e secagem", dataAnalise: "2026-09-08", analistaId: 13 },
      fonteRecurso: "Aditivo de orçamento", alcada: "Comitê", decisao: null, situacao: "Aguardando comitê", encerramento: null },
    { projetoId: 2, codigo: "SM-CB-2026-0003", titulo: "Resequenciamento da montagem com pré-montagem em solo", tipo: "Prazo", origem: "Interna", prioridade: "Normal", solicitanteId: 16, dataSolicitacao: "2026-09-18",
      descricao: "Explorar a oportunidade RSK-CB-2026-0004 para recuperar o atraso do fornecedor da caldeira.",
      impacto: null, fonteRecurso: null, alcada: null, decisao: null, analise: { responsavelId: 16, prazo: "2026-10-02" }, situacao: "Em análise de impacto", encerramento: null },
    { projetoId: 3, codigo: "SM-TR-2026-0001", titulo: "Escavação e desmonte de rocha na bacia de água fria", tipo: "Custo", origem: "Contratada", prioridade: "Urgente", solicitanteId: 18, dataSolicitacao: "2026-08-28",
      descricao: "Decorrente do claim CLM-TR-2026-0001 (rocha não indicada nas sondagens do edital).",
      impacto: { custoCentavos: 28000000, prazoDias: 15, escopo: "Desmonte de 380 m³ de rocha", qualidade: "Sem impacto", riscos: "RSK-TR-2026-0001 materializado", sms: "APR de desmonte de rocha", contrato: "Aditivo CT-2026-027",
        afetaMarcoContratual: true, eacItens: ["3.1.1"], atividades: "Escavação e concretagem da bacia", dataAnalise: "2026-09-11", analistaId: 13 },
      fonteRecurso: "Aditivo de orçamento", alcada: "Comitê", decisao: null, situacao: "Aguardando comitê", encerramento: null },
    { projetoId: 3, codigo: "SM-TR-2026-0002", titulo: "Monitoramento online de vibração dos ventiladores", tipo: "Escopo", origem: "Cliente", prioridade: "Normal", solicitanteId: 15, dataSolicitacao: "2026-09-21",
      descricao: "Cliente pediu sensores de vibração ligados ao sistema de manutenção preditiva.",
      impacto: null, fonteRecurso: null, alcada: null, decisao: null, situacao: "Registrada", encerramento: null }
  ].forEach(function (s) { incluir("mudancas", s); });
  [
    { projetoId: 2, codigo: "LA-CB-2026-0001", titulo: "Inspeção residente no fornecedor de equipamento de longo prazo", tipo: "A repetir", fase: "Suprimentos", area: "Aquisições", disciplina: "Mecânica",
      origem: "Risco RSK-CB-2026-0001", aconteceu: "O atraso da matéria-prima da caldeira só foi percebido na terceira semana, pelo relatório mensal do fornecedor.",
      causa: "Diligenciamento documental, sem presença na fábrica nas fases iniciais.", impactoPrazoDias: 20, impactoCustoCentavos: 0,
      recomendacao: "Mobilizar inspetor residente em fornecedores LLI desde a compra da matéria-prima, com relatório semanal fotográfico.",
      palavrasChave: ["LLI", "diligenciamento", "inspeção"], autorId: 7, aplicabilidade: "Corporativa", situacao: "Em validação", data: "2026-09-19", reusos: 0 },
    { projetoId: 3, codigo: "LA-TR-2026-0001", titulo: "Sondagem rotativa na área de bacias antes da licitação civil", tipo: "A evitar", fase: "Engenharia", area: "Riscos", disciplina: "Civil",
      origem: "Risco RSK-TR-2026-0001", aconteceu: "Rocha sã na escavação da bacia gerou claim de R$ 280 mil e 15 dias de atraso.",
      causa: "Sondagens do edital só a percussão, sem investigação rotativa.", impactoPrazoDias: 15, impactoCustoCentavos: 28000000,
      recomendacao: "Exigir sondagem rotativa em escavações acima de 2 m em áreas com afloramento rochoso antes de licitar a obra civil.",
      palavrasChave: ["sondagem", "rocha", "escavação"], autorId: 18, aplicabilidade: "Corporativa", situacao: "Rascunho", data: "2026-09-02", reusos: 0 }
  ].forEach(function (l) { incluir("licoes", l); });

  /* ======================================================================
     02 Relato do período e análises do período (projetos 2 e 3)
     ====================================================================== */
  function relato(o) { return incluir("relatos", Object.assign({ criadoPorId: 16, atualizadoPorId: 16 }, o)); }
  relato({ projetoId: 2, tipo: "Mensal", periodo: "2026-08", criadoEm: "2026-09-02T09:30", atualizadoEm: "2026-09-02T15:10",
    atividadesPeriodo: ["Concluída a engenharia civil e estrutural em Rev 0.", "Mobilizada a Pi Montagens e iniciada a montagem das colunas da caldeira.", "Estacas e blocos da caldeira com 60% do volume concretado.", "Aprovada a SM-CB-2026-0001 (silo de 3 dias de estoque)."],
    atividadesProximo: ["Concluir as bases da estrutura e liberar a BS-610-02.", "Montar as colunas C-01 a C-06.", "Concluir a equalização técnica das bombas e ventiladores (RFQ-2026-021).", "Iniciar a concretagem do anel do silo."],
    pontos: [{ descricao: "Fabricação das paredes d'água da caldeira com 20 dias de atraso na matéria-prima.", natureza: "Ameaça", risco: "Entrega da caldeira após a data necessária e deslocamento da montagem de pressão." },
      { descricao: "Área livre ao lado da casa de caldeira permite pré-montagem em solo.", natureza: "Oportunidade", risco: "Recuperar até 25 dias da montagem de pressão com içamento de módulos." }] });
  relato({ projetoId: 2, tipo: "Semanal", periodo: "2026-S38", criadoEm: "2026-09-21T08:40", atualizadoEm: "2026-09-21T11:05",
    atividadesPeriodo: ["Concretados os blocos B-21 a B-26 (150 m³).", "Montadas 4 das 6 colunas previstas da estrutura da caldeira.", "Drenagem do pátio de biomassa com 182 m executados."],
    atividadesProximo: ["Corrigir a cota da base BS-610-02.", "Concluir as colunas C-05 e C-06.", "Iniciar a armação do anel do silo."],
    pontos: [{ descricao: "Base BS-610-02 com cota abaixo do projeto bloqueia a coluna C-02.", natureza: "Ameaça", risco: "Atraso de uma semana na estrutura da caldeira." }] });
  relato({ projetoId: 3, tipo: "Mensal", periodo: "2026-08", criadoEm: "2026-09-03T10:00", atualizadoEm: "2026-09-03T10:00",
    atividadesPeriodo: ["Terraplenagem e acessos da torre concluídos.", "Iniciada a escavação da bacia de água fria.", "Aprovado o projeto da torre (marco M1 da Rho Torres)."],
    atividadesProximo: ["Definir o método de desmonte da rocha e decidir a SM-TR-2026-0001.", "Concretar o lastro da célula 1.", "Adjudicar os painéis e inversores."],
    pontos: [{ descricao: "Rocha sã encontrada na escavação da bacia a partir da cota 2,1 m.", natureza: "Ameaça", risco: "Sobrecusto de R$ 280 mil e 15 dias de atraso na bacia." }] });
  relato({ projetoId: 3, tipo: "Semanal", periodo: "2026-S38", criadoEm: "2026-09-21T09:15", atualizadoEm: "2026-09-21T09:15",
    atividadesPeriodo: ["Escavação da célula 1 com 307 m³ executados.", "Plataforma da casa de bombas concluída.", "Lastro da célula 1 iniciado na sexta-feira."],
    atividadesProximo: ["Aprovar o plano de fogo.", "Concluir o lastro da célula 1.", "Parecer técnico da RFQ-2026-027."],
    pontos: [{ descricao: "Decisão da SM de rocha pendente no comitê.", natureza: "Ameaça", risco: "Paralisação da escavação da célula 2 a partir de 02/10." }] });

  function analise(projetoId, modulo, tipo, periodo, texto, desvios, porId) {
    return incluir("analisesPeriodo", { projetoId: projetoId, modulo: modulo, tipo: tipo, periodo: periodo, criadoPorId: porId || 16, criadoEm: periodo.indexOf("S") > 0 ? "2026-09-21T10:00" : "2026-09-03T10:00",
      atualizadoPorId: porId || 16, atualizadoEm: periodo.indexOf("S") > 0 ? "2026-09-21T14:30" : "2026-09-03T16:00", analise: texto,
      desvios: (desvios || []).map(function (d) { return { chave: d[0], indicador: d[1], comentario: d[2] }; }) });
  }
  var D_PLAN = [["avanco", "Avanço físico acumulado", "Desvio concentrado em suprimentos: fabricação da caldeira atrasada no fornecedor. Diligenciamento com inspetor residente e turno extra negociado."],
    ["avanco_periodo", "Avanço no período", "Período abaixo do previsto pela base BS-610-02 bloqueada e pela chuva de quarta-feira; correção da base programada para a S39."],
    ["termino", "Término pela tendência", "Tendência de término um mês após a LB pelo caminho crítico da caldeira; pré-montagem em solo em análise (SM-CB-2026-0003) para recuperar o prazo."],
    ["areas", "Avanço por área", "Suprimentos (-6 p.p.) e engenharia eletromecânica abaixo do previsto; obras civis em linha com o plano."],
    ["produtividade", "Produtividade", "Montagem da estrutura com fator de produtividade acima de 1,10 por falta de frente; plano de ação com a Pi Montagens."]];
  analise(2, "planejamento", "Semanal", "2026-S38", "A caldeira fecha a semana com 30,6% de avanço contra 33,2% previstos (SPI 0,92). O desvio vem do suprimento da caldeira, que concentra 22% do peso do projeto e tem a fabricação atrasada no fornecedor. As obras civis seguem em linha com o plano; a montagem da estrutura começou com restrição de frente. A tendência aponta término em julho de 2027, um mês após a linha de base, e depende da recuperação da fabricação e da pré-montagem em solo.", D_PLAN);
  analise(2, "planejamento", "Mensal", "2026-08", "Agosto fecha com 24,3% de avanço contra 27,5% previstos (SPI 0,88). A engenharia civil foi concluída e a montagem da caldeira foi mobilizada; o desvio vem do atraso da matéria-prima da caldeira no fornecedor, identificado como risco crítico. A tendência de término passou para julho de 2027 e a recuperação depende do plano do fornecedor e da pré-montagem em solo em estudo.", D_PLAN);
  var D_FIN = [["spi_custo", "SPI de custo (valor agregado)", "Valor agregado abaixo do planejado pelo atraso físico da caldeira; custo por unidade de avanço segue abaixo do orçado (CPI acima de 1)."],
    ["pacotes", "Pacotes com sobrecusto projetado", "Fundações com sobrecusto projetado de R$ 80 mil por aprofundamento de estacas, compensado pela economia na compra da caldeira."],
    ["cpi", "CPI (desempenho de custo)", "CPI abaixo de 1 no mês pelo pagamento antecipado do marco de mobilização; tendência de retorno acima de 1 com a medição de setembro."],
    ["vac", "Projeção no término", "Projeção no término dentro do orçamento; sem necessidade de revisão."]];
  analise(2, "financeiro", "Semanal", "2026-S38", "O projeto mantém desempenho de custo favorável (CPI 1,02 em agosto) com 14,5 milhões comprometidos, 80% do orçamento. A projeção no término de R$ 18,18 milhões fica R$ 20 mil abaixo do orçamento: a economia na compra da caldeira compensa o sobrecusto das fundações. O ponto de atenção é o SPI de custo, reflexo do atraso físico da caldeira, e a contingência já comprometida com a SM do silo.", D_FIN, 13);
  analise(2, "financeiro", "Mensal", "2026-08", "Agosto fecha com CPI 1,02 e SPI de custo 0,88. O comprometido chega a 76,6% do orçamento com a contratação da montagem eletromecânica. A projeção no término fica dentro do orçamento, com economia na caldeira e sobrecusto nas fundações. A contingência foi acionada pela SM do silo de biomassa (R$ 180 mil).", D_FIN, 13);
  var D_SUP = [["aderencia", "Aderência ao plano de compras", "Contratação das bombas e ventiladores atrasada pela equalização técnica; materiais elétricos com requisição emitida com três semanas de atraso."],
    ["criticos", "Pedidos críticos", "Caldeira com folga negativa de 26 dias: inspetor residente mobilizado e turno extra negociado com o fornecedor."],
    ["otd", "Entregas no prazo (OTD)", "Sem entregas no período."], ["marcos_atrasados", "Marcos realizados com atraso no período", "Matéria-prima da caldeira realizada 21 dias após a LB; recuperação na fabricação acordada com o fornecedor."]];
  analise(2, "suprimentos", "Semanal", "2026-S38", "Suprimentos concentra o desvio do projeto. A caldeira (PED-2026-0011) segue com previsão de entrega 26 dias após a data necessária na obra, apesar da matéria-prima recebida em 05/09. O alimentador de biomassa e o precipitador seguem sem folga negativa. A contratação das bombas e ventiladores atrasou três semanas na equalização técnica e a requisição dos materiais elétricos saiu com atraso, sem efeito no caminho crítico por enquanto.", D_SUP, 7);
  analise(2, "suprimentos", "Mensal", "2026-08", "Agosto registrou a contratação da montagem eletromecânica e o recebimento da matéria-prima do alimentador de biomassa. A caldeira entrou em folga negativa com o atraso das chapas de aço-liga; o risco foi elevado a crítico e o diligenciamento passou a semanal. A aderência ao plano de compras caiu pela RFQ das bombas e ventiladores.", D_SUP, 7);
  analise(2, "riscos", "Semanal", "2026-S38", "O projeto tem 5 riscos ativos, 2 críticos: o atraso da fabricação da caldeira (ameaça, sem redução após o plano) e a pré-montagem em solo (oportunidade). A exposição de ameaças soma R$ 1,4 milhão. A nova exigência de emissões está em análise e pode demandar campo adicional no precipitador. A revisão do risco de chuvas está vencida e entra na pauta.", [], 14);
  analise(2, "riscos", "Mensal", "2026-08", "Agosto elevou o risco do fornecedor da caldeira a crítico e registrou a oportunidade de pré-montagem em solo. O risco de umidade da biomassa foi reduzido a moderado com a aprovação do silo ampliado. A exposição das ameaças subiu com a folga negativa da caldeira.", [], 14);
  analise(2, "hse", "Semanal", "2026-S38", "Semana sem acidente com afastamento. Foram registrados quase acidentes na montagem da estrutura, entre eles o HiPo de 09/09 (queda de chapa de ligação), ainda em investigação. A TRIF do mês segue influenciada pelo aumento de efetivo da montagem. Ação principal: amarração de chapas antes do içamento e reforço do DDS de trabalho em altura.", [], 10);
  analise(2, "hse", "Mensal", "2026-08", "Agosto fecha sem acidente registrável e com boa cultura de relato na base da pirâmide. DDS com 94% de realização e conformidade de inspeções de 87%. Ponto de atenção: início da montagem da estrutura com trabalho em altura e içamentos, coberto pela APR-CB-2026-004.", [], 10);

  var D_PLAN3 = [["areas", "Avanço por área", "Obras civis levemente abaixo do previsto na escavação da bacia (rocha); fornecimento da torre acima do plano compensa."]];
  analise(3, "planejamento", "Semanal", "2026-S38", "A torre fecha a semana com 31,0% de avanço contra 28,1% previstos (SPI 1,10). O fornecimento da torre (EPC) segue adiantado e compensa a escavação da bacia, afetada pela rocha. A tendência mantém o término em fevereiro de 2027, desde que a decisão da SM de rocha saia até a primeira semana de outubro.", D_PLAN3, 16);
  analise(3, "financeiro", "Semanal", "2026-S38", "O projeto tem CPI 0,93 em agosto e projeção no término de R$ 7,73 milhões, 4,5% acima do orçamento, pelo desmonte de rocha da bacia (R$ 280 mil) e pelo prolongamento do gerenciamento. A SM-TR-2026-0001 aguarda o comitê; aprovada, o valor sai de aditivo de orçamento. Sem ação, a contingência não cobre o sobrecusto.",
    [["cpi", "CPI (desempenho de custo)", "Escavação em rocha com produtividade de 40% do previsto e equipamento adicional mobilizado; custo absorvido até a decisão da SM."],
     ["vac", "Projeção no término", "Sobrecusto projetado de R$ 330 mil: rocha (R$ 280 mil), engenharia básica e gerenciamento. SM-TR-2026-0001 aguardando comitê."],
     ["pacotes", "Pacotes com sobrecusto projetado", "Bacia de água fria (+25%), engenharia básica e gerenciamento; a bacia depende da decisão da SM."],
     ["spi_custo", "SPI de custo (valor agregado)", "Sem desvio de prazo relevante."]], 13);
  analise(3, "suprimentos", "Semanal", "2026-S38", "A torre em PRFV segue com a fabricação no plano (marco M2 aprovado). As bombas estão sem folga negativa, com cinco dias de folga para a data necessária. Os painéis e inversores estão em equalização técnica com três semanas de atraso, o que motivou o risco RSK-TR-2026-0003.",
    [["aderencia", "Aderência ao plano de compras", "Painéis e inversores com adjudicação prevista para outubro, contra setembro na LB, pela equalização técnica."],
     ["marcos_atrasados", "Marcos realizados com atraso no período", "Documentos das bombas aprovados oito dias após a LB, sem efeito na entrega."]], 7);
  analise(3, "riscos", "Semanal", "2026-S38", "A torre tem 4 riscos ativos. O risco de rocha materializou em agosto e virou claim e SM. O risco de queda de altura na montagem da torre é o mais grave (risco de vida), reduzido a alto com o plano de linha de vida aprovado. A revisão do risco dos inversores está vencida.", [], 15);
  analise(3, "hse", "Semanal", "2026-S38", "Semana com um trabalho restrito na bacia (torção de joelho ao descer o talude sem escada), que eleva a TRIF do mês. Ação imediata: escadas a cada 15 m e escoramento dos taludes, já registrados na APR do desmonte de rocha.", [], 10);

  /* ======================================================================
     Análises do período do PORTFÓLIO (projetoId null): texto do PMO por módulo
     ====================================================================== */
  var DP = [["avanco", "Avanço físico acumulado", "Carteira abaixo do previsto pela fábrica (montagem eletromecânica) e pela caldeira (fabricação no fornecedor); a torre segue adiantada."],
    ["avanco_periodo", "Avanço no período", "Período abaixo do previsto nos dois projetos de maior peso; planos de recuperação em andamento em ambos."],
    ["termino", "Término pela tendência", "Término da carteira pela tendência da caldeira (julho de 2027), um mês após a linha de base; fábrica também com um mês de atraso na tendência."],
    ["areas", "Avanço por projeto", "Fábrica (-3,9 p.p.) e caldeira (-3,8 p.p.) abaixo do previsto; torre acima (+0,9 p.p.)."],
    ["produtividade", "Produtividade", "Fator de produtividade acima de 1,10 na montagem da fábrica e da caldeira; ações abertas com as duas contratadas."]];
  analise(null, "planejamento", "Semanal", "2026-S38", "A carteira fecha a semana com 46,7% de avanço ponderado contra 48,2% previstos (SPI ponderado 0,97). A fábrica, com 55% do peso, responde pela maior parte do desvio pela montagem eletromecânica; a caldeira, com 29%, pela fabricação atrasada no fornecedor. A torre segue adiantada, mas tem pouco peso na carteira. A tendência de término da carteira é julho de 2027, puxada pela caldeira. Prioridades do PMO: recuperação da montagem da fábrica e diligenciamento da caldeira.", DP, 1);
  analise(null, "planejamento", "Mensal", "2026-08", "Agosto fecha a carteira com 37,8% de avanço ponderado contra 40,7% previstos (SPI ponderado 0,93). O desvio está concentrado nos dois projetos de maior peso: a fábrica pela montagem eletromecânica e a caldeira pelo atraso da matéria-prima no fornecedor. A torre começou a obra adiantada. A tendência de término da carteira passou para julho de 2027.", DP, 1);
  var DF = [["cpi", "CPI (desempenho de custo)", "CPI da carteira abaixo de 1 pela fábrica e pela torre (0,93); a caldeira compensa parcialmente (1,02)."],
    ["spi_custo", "SPI de custo (valor agregado)", "Valor agregado da carteira abaixo do planejado, reflexo do atraso físico da fábrica e da caldeira."],
    ["vac", "Projeção no término", "Projeção da carteira R$ 1 milhão acima do orçamento: fábrica (+R$ 660 mil) e torre (+R$ 330 mil); caldeira dentro do orçamento."],
    ["pacotes", "Projetos com sobrecusto projetado", "Fábrica e torre com sobrecusto projetado; SMs de rocha e da casa de bombas aguardam comitê."]];
  analise(null, "financeiro", "Semanal", "2026-S38", "A carteira de R$ 70,2 milhões tem projeção no término de R$ 71,2 milhões (+1,4%). O sobrecusto vem da fábrica (montagem e fundações) e da torre (rocha na bacia); a caldeira segue dentro do orçamento com CPI 1,02. O CPI consolidado de agosto é 0,99. Três SMs com impacto de custo aguardam comitê e devem ser decididas antes do fechamento de setembro para a carteira não consumir a contingência sem aprovação.", DF, 1);
  analise(null, "financeiro", "Mensal", "2026-08", "Agosto fecha a carteira com CPI 0,99 e 85% do orçamento comprometido. A fábrica mantém leve sobrecusto e a torre iniciou o desvio com a escavação em rocha. A caldeira tem economia na compra do equipamento principal. A projeção no término fica 1,4% acima do orçamento consolidado.", DF, 1);
  var DS = [["aderencia", "Aderência ao plano de compras", "Atrasos em RFQs da caldeira (bombas e ventiladores) e da torre (inversores); SDCD da fábrica em equalização comercial."],
    ["otd", "Entregas no prazo (OTD)", "Entregas da fábrica com atraso em transportadores e válvulas; caldeira e torre sem entregas no período."],
    ["criticos", "Pedidos críticos", "Quatro pedidos com folga negativa: três da fábrica (moinho, britador e bombas) e a caldeira."],
    ["marcos_atrasados", "Marcos realizados com atraso no período", "Marcos de fabricação realizados com atraso na fábrica e na caldeira; torre no plano."]];
  analise(null, "suprimentos", "Semanal", "2026-S38", "A carteira tem quatro pedidos críticos (folga negativa): moinho, britador e bombas da fábrica e a caldeira. Os equipamentos de longo prazo concentram o risco de prazo da carteira. A aderência ao plano de compras caiu com as RFQs da caldeira e da torre. Ação do PMO: reunião mensal de diligenciamento consolidada com os fornecedores de LLI dos três projetos.", DS, 1);
  analise(null, "suprimentos", "Mensal", "2026-08", "Agosto registrou a contratação da montagem da caldeira e o marco de projeto da torre. A folga negativa se estendeu à caldeira. A carteira mantém saving positivo nas adjudicações.", DS, 1);
  analise(null, "riscos", "Semanal", "2026-S38", "A carteira tem 16 riscos ativos, 4 críticos (duas ameaças e duas oportunidades). As ameaças críticas são o licenciamento da fábrica e o fornecedor da caldeira; o risco de vida na montagem da torre foi reduzido a alto com o plano de linha de vida. A exposição das ameaças soma R$ 4,9 milhões, 70% na fábrica. O risco de rocha da torre materializou e virou SM. Revisões vencidas nos três projetos entram na pauta do comitê de portfólio.", [], 1);
  analise(null, "riscos", "Mensal", "2026-08", "Agosto elevou a exposição da carteira com o risco crítico do fornecedor da caldeira e a materialização da rocha na torre. A fábrica manteve os dois riscos críticos. A pauta do comitê de portfólio concentra planos pendentes e revisões vencidas.", [], 1);
  analise(null, "hse", "Semanal", "2026-S38", "A carteira segue sem acidente com afastamento. A TRIF consolidada do mês é influenciada pelo trabalho restrito da torre e pelos tratamentos médicos da fábrica. Dois HiPo em investigação (fábrica e caldeira) envolvem queda de objetos em altura: o PMO padronizou a amarração de ferramentas e chapas nos três projetos.", [], 10);
  analise(null, "hse", "Mensal", "2026-08", "Agosto fecha a carteira sem acidente com afastamento e com TRIF abaixo da acumulada. O relato de quase acidentes está ativo nos três projetos. Ponto de atenção: início de trabalhos em altura na caldeira e na torre.", [], 10);
  analise(null, "qualidade", "Semanal", "2026-S38", "A carteira fecha a semana com 7 RNC em aberto, uma crítica: o certificado das chapas do tubulão da caldeira (RNC-CB-2026-0002), que suspendeu a soldagem no fornecedor. A fábrica responde pela única RNC com prazo vencido (soldas da linha 310-P-014) e pela reprovação da semana (torque do PR-02), confirmada na auditoria AUD-TN-2026-02 com 82,9% de conformidade. Aprovação em inspeções de 66,7% na semana, abaixo da meta de 95%. Prioridades do PMO: rastreabilidade de materiais nos fornecedores LLI e controle de torque na montagem.", [], 9);
  analise(null, "qualidade", "Mensal", "2026-08", "Agosto encerra a RNC de recobrimento da caldeira (eficaz na primeira verificação) e abre a das soldas da fábrica, que concentra o custo da não qualidade do mês (R$ 34 mil). A carteira fecha com 2 RNC em aberto e 80% de aprovação nas 5 inspeções do mês; a auditoria de concreto da caldeira teve 86,7% de conformidade, abaixo da meta de 90%. Tendência: auditorias de fornecedores de partes de pressão e de PRFV programadas para reduzir as não conformidades de origem externa.", [], 9);

  /* Histograma de mão de obra previsto (linha de base de recursos, PMBOK) por projeto e mês: HHT e
     efetivo previstos. Derivado uma única vez do realizado ajustado pela razão entre o avanço
     previsto e o real do mês (fator limitado a 0,85 a 1,20), arredondado; é dado de plano e não
     acompanha lançamentos posteriores de HHT. */
  M.histogramaMaoDeObra = (function () {
    var out = [], porChave = {};
    (M.hht || []).forEach(function (r) {
      var k = r.projetoId + "|" + r.mes;
      var x = porChave[k] = porChave[k] || { projetoId: r.projetoId, mes: r.mes, hht: 0, efetivo: 0 };
      x.hht += r.hht; x.efetivo += r.efetivoMedio;
    });
    Object.keys(porChave).sort().forEach(function (k) {
      var x = porChave[k];
      var c = (M.curvaFisica || []).filter(function (cf) { return cf.projetoId === x.projetoId; })[0];
      var f = 1;
      if (c) {
        var i = c.meses.indexOf(x.mes);
        if (i >= 0 && c.real[i] != null) {
          var dp = c.baseline[i] - (i > 0 ? c.baseline[i - 1] : 0), dr = c.real[i] - (i > 0 && c.real[i - 1] != null ? c.real[i - 1] : 0);
          if (dr > 0 && dp > 0) f = Math.max(0.85, Math.min(1.2, dp / dr));
        }
      }
      out.push({ id: out.length + 1, projetoId: x.projetoId, mes: x.mes, hhtPrevisto: Math.round(x.hht * f / 100) * 100, efetivoPrevisto: Math.round(x.efetivo * f) });
    });
    return out;
  })();
})(window.MOCK);
