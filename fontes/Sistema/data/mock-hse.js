/* ==========================================================================
   mock-hse.js | 07 HSE (dados fictícios).
   hht: horas-homem trabalhadas por mês e empresa (base de todas as taxas).
   ocorrencias: níveis 1 a 4 da pirâmide e ambientais. Os eventos
   relevantes são fixos; os demais são gerados de forma determinística
   (semente fixa), distribuídos pelo HHT de cada mês e empresa.
   observacoes: desvios (nível 5) vêm das observações comportamentais e
   inspeções, por isso são consolidados por mês, não registro a registro.
   LGPD: nenhum nome de pessoa lesionada; só função e empresa.
   Cenário sem lesão grave (nível 1 da pirâmide = 0 em todos os meses, 28/09/2026):
   nenhuma fatalidade nem acidente com afastamento; TF e TG zerados e "dias sem
   afastamento" contados desde o início do projeto.
   ========================================================================== */
window.MOCK = window.MOCK || {};

(function (M) {
  "use strict";

  var MESES = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"];
  var HORAS_MES = 218;
  var EFETIVO = {            /* empresaId: efetivo médio por mês */
    6: [60, 140, 220, 280, 300, 300, 280, 250, 220],   /* Zeta Civil */
    1: [0, 0, 0, 0, 60, 150, 260, 360, 420],           /* Alfa Montagens */
    5: [10, 10, 10, 10, 10, 10, 10, 10, 10],           /* Épsilon Engenharia (campo) */
    13: [25, 25, 25, 25, 25, 25, 25, 25, 25]           /* Timenow Gerenciadora */
  };

  M.hht = [];
  Object.keys(EFETIVO).forEach(function (emp) {
    EFETIVO[emp].forEach(function (ef, i) {
      if (ef > 0) M.hht.push({ projetoId: 1, mes: MESES[i], empresaId: Number(emp), efetivoMedio: ef, hht: ef * HORAS_MES });
    });
  });

  /* Gerador pseudoaleatório com semente fixa (mulberry32): mesmos dados a cada abertura */
  var semente = 2026;
  function aleatorio() {
    semente |= 0; semente = (semente + 0x6D2B79F5) | 0;
    var t = Math.imul(semente ^ (semente >>> 15), 1 | semente);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }
  function escolher(lista) { return lista[Math.floor(aleatorio() * lista.length)]; }
  function dois(n) { return (n < 10 ? "0" : "") + n; }

  /* Sorteio de mês e empresa ponderado pelo HHT */
  var totalHHT = M.hht.reduce(function (s, r) { return s + r.hht; }, 0);
  function sortearMesEmpresa() {
    var alvo = aleatorio() * totalHHT, acc = 0;
    for (var i = 0; i < M.hht.length; i++) { acc += M.hht[i].hht; if (alvo <= acc) return M.hht[i]; }
    return M.hht[M.hht.length - 1];
  }
  var AREAS = ["Terraplenagem", "Fundações", "Moagem 210", "Flotação 310", "Subestação 420", "Pipe rack PR-02", "Utilidades 510", "Canteiro"];
  var FUNCOES = ["Montador", "Soldador", "Armador", "Carpinteiro", "Operador de equipamento", "Eletricista", "Ajudante", "Encarregado", "Motorista"];
  var TEXTOS = {
    "Primeiros socorros": ["Corte superficial na mão ao manusear chapa.", "Partícula no olho durante esmerilhamento.",
      "Escoriação no antebraço em contato com estrutura.", "Picada de inseto na frente de trabalho.", "Torção leve do punho ao carregar material."],
    "Dano material": ["Caminhão colidiu com defensa metálica na via interna.", "Retroescavadeira atingiu eletroduto provisório.",
      "Queda de material da caçamba em via interna.", "Dano ao talude por tráfego de equipamento.",
      "Empilhadeira derrubou cavalete de sinalização.", "Rompimento de mangueira hidráulica do guindaste."],
    "Quase acidente": ["Material solto em altura sem amarração.", "Pessoa sob carga suspensa durante içamento.",
      "Escada apoiada em superfície instável.", "Veículo acima do limite de velocidade na via interna.",
      "Abertura de piso sem proteção.", "Trabalho a quente sem vigia de incêndio.",
      "Ferramenta elétrica com cabo danificado em uso.", "Andaime em uso sem liberação diária."]
  };
  var CAUSAS = ["Procedimento não seguido", "Condição insegura do local", "Falha de planejamento da tarefa",
    "EPI inadequado", "Falta de sinalização", "Equipamento sem inspeção"];

  function gerar(tipo) {
    var base = sortearMesEmpresa();
    var ano = Number(base.mes.slice(0, 4)), mes = Number(base.mes.slice(5, 7));
    var ultimoDia = base.mes === "2026-09" ? 24 : new Date(ano, mes, 0).getDate();
    var dia = 1 + Math.floor(aleatorio() * ultimoDia);
    var hora = 7 + Math.floor(aleatorio() * 10), minuto = Math.floor(aleatorio() * 60);
    return {
      projetoId: 1, dataHora: base.mes + "-" + dois(dia) + "T" + dois(hora) + ":" + dois(minuto),
      area: escolher(AREAS), empresaId: base.empresaId, tipo: tipo, descricao: escolher(TEXTOS[tipo]),
      funcao: tipo === "Primeiros socorros" ? escolher(FUNCOES) : null, pessoasEnvolvidas: tipo === "Primeiros socorros" ? 1 : 0,
      gravidadeReal: tipo === "Dano material" ? 2 : 1,
      potencial: { p: 1 + Math.floor(aleatorio() * 3), i: 1 + Math.floor(aleatorio() * 3) },
      hipo: false, diasPerdidos: 0, diasDebitados: 0, cat: false,
      causaImediata: escolher(CAUSAS), comunicacaoHoras: 1 + Math.floor(aleatorio() * 6), ambiental: false
    };
  }

  var lista = [
    { projetoId: 1, dataHora: "2026-02-03T10:40", area: "Terraplenagem", empresaId: 6, tipo: "Trabalho restrito",
      descricao: "Entorse leve de tornozelo ao descer da escavadeira sem os três pontos de apoio; retorno com restrição de atividade, sem afastamento.", funcao: "Operador de equipamento", pessoasEnvolvidas: 1,
      gravidadeReal: 2, potencial: { p: 3, i: 3 }, hipo: false, diasPerdidos: 0, diasDebitados: 0, cat: true,
      causaImediata: "Procedimento não seguido", comunicacaoHoras: 2, metodo: "5 porquês", ambiental: false },
    { projetoId: 1, dataHora: "2026-02-25T15:10", area: "Fundações", empresaId: 6, tipo: "Tratamento médico",
      descricao: "Prensamento da mão durante o posicionamento de forma metálica; sutura no ambulatório, sem afastamento.", funcao: "Carpinteiro", pessoasEnvolvidas: 1,
      gravidadeReal: 2, potencial: { p: 3, i: 4 }, hipo: true, diasPerdidos: 0, diasDebitados: 0, cat: true,
      causaImediata: "Falha de planejamento da tarefa", comunicacaoHoras: 1, metodo: "Árvore de causas", ambiental: false },
    { projetoId: 1, dataHora: "2026-06-18T14:05", area: "Fundações", empresaId: 6, tipo: "Trabalho restrito",
      descricao: "Lombalgia ao movimentar vergalhões sem auxílio mecânico.", funcao: "Armador", pessoasEnvolvidas: 1,
      gravidadeReal: 2, potencial: { p: 3, i: 2 }, hipo: false, diasPerdidos: 0, diasDebitados: 0, cat: true,
      causaImediata: "Falha de planejamento da tarefa", comunicacaoHoras: 3, ambiental: false },
    { projetoId: 1, dataHora: "2026-08-27T09:50", area: "Moagem 210", empresaId: 1, tipo: "Trabalho restrito",
      descricao: "Contusão no ombro durante o alinhamento de peça com talha.", funcao: "Montador", pessoasEnvolvidas: 1,
      gravidadeReal: 2, potencial: { p: 2, i: 3 }, hipo: false, diasPerdidos: 0, diasDebitados: 0, cat: true,
      causaImediata: "Procedimento não seguido", comunicacaoHoras: 2, ambiental: false },
    { projetoId: 1, dataHora: "2026-04-09T11:30", area: "Terraplenagem", empresaId: 6, tipo: "Tratamento médico",
      descricao: "Corte no joelho com sutura ao tropeçar em vergalhão sem proteção.", funcao: "Ajudante", pessoasEnvolvidas: 1,
      gravidadeReal: 2, potencial: { p: 3, i: 3 }, hipo: false, diasPerdidos: 0, diasDebitados: 0, cat: false,
      causaImediata: "Condição insegura do local", comunicacaoHoras: 2, ambiental: false },
    { projetoId: 1, dataHora: "2026-07-15T16:20", area: "Flotação 310", empresaId: 1, tipo: "Tratamento médico",
      descricao: "Queimadura de segundo grau no antebraço durante corte a quente.", funcao: "Soldador", pessoasEnvolvidas: 1,
      gravidadeReal: 2, potencial: { p: 2, i: 3 }, hipo: false, diasPerdidos: 0, diasDebitados: 0, cat: false,
      causaImediata: "EPI inadequado", comunicacaoHoras: 30, ambiental: false },
    { projetoId: 1, dataHora: "2026-09-03T08:15", area: "Subestação 420", empresaId: 1, tipo: "Tratamento médico",
      descricao: "Corte na mão com sutura ao decapar cabo com estilete.", funcao: "Eletricista", pessoasEnvolvidas: 1,
      gravidadeReal: 2, potencial: { p: 2, i: 2 }, hipo: false, diasPerdidos: 0, diasDebitados: 0, cat: false,
      causaImediata: "Ferramenta inadequada", comunicacaoHoras: 4, ambiental: false },
    { projetoId: 1, dataHora: "2026-09-12T09:25", area: "Pipe rack PR-02", empresaId: 1, tipo: "Quase acidente",
      descricao: "Queda de chave de 1,2 kg de 14 m de altura em área de circulação parcialmente isolada.", funcao: null, pessoasEnvolvidas: 0,
      gravidadeReal: 1, potencial: { p: 3, i: 5 }, hipo: true, diasPerdidos: 0, diasDebitados: 0, cat: false,
      causaImediata: "Ferramenta sem amarração em trabalho em altura", comunicacaoHoras: 1, metodo: "Árvore de causas", ambiental: false,
      situacaoFixa: "Em investigação" },
    /* Ambientais (fora da pirâmide) */
    { projetoId: 1, dataHora: "2026-05-14T13:40", area: "Canteiro", empresaId: 6, tipo: "Ambiental", subtipo: "Vazamento",
      descricao: "Vazamento de 20 L de óleo hidráulico de escavadeira no solo.", funcao: null, pessoasEnvolvidas: 0,
      gravidadeReal: 2, potencial: { p: 2, i: 3 }, hipo: false, diasPerdidos: 0, diasDebitados: 0, cat: false,
      causaImediata: "Equipamento sem inspeção", comunicacaoHoras: 2, ambiental: true, severidadeAmbiental: "Moderada" },
    { projetoId: 1, dataHora: "2026-07-22T10:05", area: "Canteiro", empresaId: 1, tipo: "Ambiental", subtipo: "Resíduo",
      descricao: "Resíduo contaminado descartado em caçamba de resíduo comum.", funcao: null, pessoasEnvolvidas: 0,
      gravidadeReal: 1, potencial: { p: 2, i: 2 }, hipo: false, diasPerdidos: 0, diasDebitados: 0, cat: false,
      causaImediata: "Procedimento não seguido", comunicacaoHoras: 5, ambiental: true, severidadeAmbiental: "Baixa" },
    { projetoId: 1, dataHora: "2026-09-03T15:30", area: "Terraplenagem", empresaId: 6, tipo: "Ambiental", subtipo: "Emissão",
      descricao: "Emissão de poeira acima do limite na divisa norte em dia de vento forte.", funcao: null, pessoasEnvolvidas: 0,
      gravidadeReal: 1, potencial: { p: 3, i: 2 }, hipo: false, diasPerdidos: 0, diasDebitados: 0, cat: false,
      causaImediata: "Falta de umectação das vias", comunicacaoHoras: 3, ambiental: true, severidadeAmbiental: "Baixa" }
  ];

  var quantidades = { "Primeiros socorros": 9, "Dano material": 31, "Quase acidente": 189 };
  Object.keys(quantidades).forEach(function (tipo) {
    for (var n = 0; n < quantidades[tipo]; n++) lista.push(gerar(tipo));
  });
  /* Duas comunicações fora do prazo entre os gerados */
  lista[20].comunicacaoHoras = 28;
  lista[140].comunicacaoHoras = 36;

  /* Redistribuição de 2 "Primeiros socorros" gerados (janeiro e fevereiro não tinham nenhum
     registro de nível 2, lesão leve) para o painel por mês não abrir zerado. Não muda o total
     do ano (14, mantido coerente com README e HANDOVER). */
  function moverData(tipo, dataOriginal, dataNova) {
    var alvo = lista.filter(function (o) { return o.tipo === tipo && o.dataHora === dataOriginal; })[0];
    if (alvo) alvo.dataHora = dataNova;
  }
  moverData("Primeiros socorros", "2026-07-01T16:56", "2026-01-14T09:10");
  moverData("Primeiros socorros", "2026-07-19T11:30", "2026-02-11T14:05");

  lista.sort(function (a, b) { return a.dataHora < b.dataHora ? -1 : a.dataHora > b.dataHora ? 1 : 0; });

  var ref = new Date((M.referencia || "2026-09-25") + "T00:00:00");
  lista.forEach(function (o, i) {
    o.id = i + 1;
    o.codigo = "OCR-TN-2026-" + ("000" + (i + 1)).slice(-4);
    var idade = Math.round((ref - new Date(o.dataHora)) / 86400000);
    o.situacao = o.situacaoFixa || (idade > 40 ? "Encerrada" : idade > 15 ? "Em tratamento" : idade > 3 ? "Ações definidas" : "Registrada");
    delete o.situacaoFixa;
  });
  M.ocorrencias = lista;

  /* Nível 5 (desvios) e indicadores proativos consolidados por mês */
  var DESVIOS = [40, 72, 108, 138, 150, 165, 182, 196, 189];            /* soma 1240 */
  var DDS_PROG = [44, 88, 110, 130, 150, 170, 180, 185, 170];
  var DDS_REAL = [40, 82, 104, 122, 142, 160, 170, 175, 160];
  var INSP_ITENS = [120, 260, 380, 460, 520, 560, 600, 640, 580];
  var INSP_CONF = [100, 222, 330, 402, 455, 490, 523, 556, 505];
  M.hseMensal = MESES.map(function (mes, i) {
    var hhtMes = M.hht.filter(function (r) { return r.mes === mes; }).reduce(function (s, r) { return s + r.hht; }, 0);
    return {
      projetoId: 1, mes: mes, desvios: DESVIOS[i],
      observacoes: Math.round(hhtMes * 41 / 10000),
      ddsProgramados: DDS_PROG[i], ddsRealizados: DDS_REAL[i],
      itensInspecionados: INSP_ITENS[i], itensConformes: INSP_CONF[i]
    };
  });

  /* Análises de risco (APR/JSA e HAZOP) e recomendações */
  M.analisesRisco = [
    { id: 1, projetoId: 1, codigo: "APR-TN-2026-018", tipo: "APR", area: "Moagem 210", titulo: "Içamento da carcaça do moinho", data: "2026-09-15",
      participantesIds: [5, 10, 12], recomendacoes: [
        { descricao: "Plano de rigging assinado por engenheiro habilitado.", responsavelId: 5, prazo: "2026-09-30", situacao: "Aberta" },
        { descricao: "Isolamento de área com raio de 1,5 vez a altura de içamento.", responsavelId: 5, prazo: "2026-10-03", situacao: "Aberta" },
        { descricao: "Teste de carga do guindaste antes da operação.", responsavelId: 5, prazo: "2026-10-04", situacao: "Aberta" } ] },
    { id: 2, projetoId: 1, codigo: "APR-TN-2026-015", tipo: "APR", area: "Pipe rack PR-02", titulo: "Montagem de estruturas em altura", data: "2026-08-05",
      participantesIds: [5, 10], recomendacoes: [
        { descricao: "Linha de vida contínua no nível superior.", responsavelId: 5, prazo: "2026-08-20", situacao: "Fechada" },
        { descricao: "Amarração de ferramentas manuais.", responsavelId: 5, prazo: "2026-08-20", situacao: "Aberta" },
        { descricao: "Plataforma elevatória no lugar de escadas.", responsavelId: 5, prazo: "2026-08-30", situacao: "Fechada" } ] },
    { id: 3, projetoId: 1, codigo: "APR-TN-2026-009", tipo: "APR", area: "Fundações", titulo: "Escavação próxima a interferências", data: "2026-04-16",
      participantesIds: [11, 10], recomendacoes: [
        { descricao: "Detecção de interferências antes de escavar.", responsavelId: 11, prazo: "2026-04-30", situacao: "Fechada" },
        { descricao: "Escoramento de valas acima de 1,25 m.", responsavelId: 11, prazo: "2026-04-30", situacao: "Fechada" } ] },
    { id: 4, projetoId: 1, codigo: "HAZOP-TN-2026-01", tipo: "HAZOP", area: "Flotação 310", titulo: "Circuito de reagentes da flotação", data: "2026-06-22",
      participantesIds: [6, 8, 10, 1], recomendacoes: [
        { descricao: "Alarme de nível alto no tanque de reagente TQ-310-05.", responsavelId: 6, prazo: "2026-08-15", situacao: "Fechada" },
        { descricao: "Válvula de retenção na linha de dosagem.", responsavelId: 6, prazo: "2026-08-15", situacao: "Fechada" },
        { descricao: "Chuveiro e lava-olhos na área de reagentes.", responsavelId: 6, prazo: "2026-09-10", situacao: "Aberta" },
        { descricao: "Intertravamento da bomba dosadora com o agitador.", responsavelId: 6, prazo: "2026-09-30", situacao: "Aberta" },
        { descricao: "Bacia de contenção dimensionada para 110% do maior tanque.", responsavelId: 6, prazo: "2026-07-31", situacao: "Fechada" },
        { descricao: "Procedimento de descarregamento de reagentes.", responsavelId: 8, prazo: "2026-10-15", situacao: "Aberta" } ] },
    { id: 5, projetoId: 1, codigo: "HAZOP-TN-2026-02", tipo: "HAZOP", area: "Utilidades 510", titulo: "Sistema de água de processo", data: "2026-07-28",
      participantesIds: [6, 8, 10], recomendacoes: [
        { descricao: "Proteção contra sobrepressão na descarga das bombas.", responsavelId: 6, prazo: "2026-08-30", situacao: "Fechada" },
        { descricao: "Indicação local de pressão na sucção.", responsavelId: 6, prazo: "2026-08-30", situacao: "Fechada" },
        { descricao: "Revisar a lógica de partida das bombas reserva.", responsavelId: 6, prazo: "2026-09-20", situacao: "Aberta" } ] }
  ];
})(window.MOCK);

/* Análise do período (07): comentário executivo e analítico por tipo (Semanal ou Mensal) e período,
   inserido e editado em modal no módulo. desvios: comentário por desvio negativo detectado (chave
   calculada pela api com os dados do período). Semana 39 e setembro sem análise (em andamento). */
window.MOCK.analisesPeriodo = (window.MOCK.analisesPeriodo || []).concat([
  { id: 41, projetoId: 1, modulo: "hse", tipo: "Semanal", periodo: "2026-S38", criadoPorId: 6, criadoEm: "2026-09-21T08:30", atualizadoPorId: 6, atualizadoEm: "2026-09-21T08:30",
    analise: "Semana sem acidente com afastamento: o projeto soma mais de 250 dias sem afastamento desde a mobilização. Foram registradas 10 ocorrências (2 danos materiais e 8 quase acidentes), com boa cultura de relato. A TRIF do mês em curso (6,80) segue abaixo da acumulada do ano (8,88), mantendo a tendência de queda desde abril. Ponto de atenção: aumento de atividades em altura com o segundo turno na montagem; reforço de DDS e inspeção de linhas de vida programados." },
  { id: 42, projetoId: 1, modulo: "hse", tipo: "Mensal", periodo: "2026-08", criadoPorId: 6, criadoEm: "2026-09-02T08:45", atualizadoPorId: 6, atualizadoEm: "2026-09-02T08:45",
    analise: "Agosto fecha com TF zero e TRIF de 7,11, a menor desde junho, para 140,6 mil HHT. Foram 56 ocorrências registradas, das quais 44 quase acidentes, o que indica relato ativo na base da pirâmide. DDS com 94,6% de realização e conformidade de inspeções de 86,9%. Tendência: manutenção da TRIF abaixo de 8 com o aumento de efetivo, desde que as ações das análises de risco de içamento sejam fechadas no prazo." }
]);
