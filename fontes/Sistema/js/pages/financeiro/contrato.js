/* ==========================================================================
   Gestão Financeira > Contrato (ficha)
   Resumo (cascata do valor e datas), Medições, Aditivos, Marcos de pagamento,
   Claims, Extensões de prazo e Avaliação de desempenho, com os fluxos de
   situação de cada registro. ?numero=CT-2026-012
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt;
  var numero = U.param("numero"), ct = null, param = null, t = {}, abaAtual = U.param("aba") || "resumo";
  var REF = GI.api.referencia();

  var ABAS = [
    { id: "resumo", nome: "Resumo", icone: "dashboard" },
    { id: "medicoes", nome: "Medições", icone: "coins", botao: "Nova medição" },
    { id: "aditivos", nome: "Aditivos", icone: "filePlus", botao: "Novo aditivo" },
    { id: "marcos", nome: "Marcos", icone: "flag", botao: "Novo marco" },
    { id: "claims", nome: "Claims", icone: "gavel", botao: "Novo claim" },
    { id: "eot", nome: "Extensões de prazo", icone: "calendarClock", botao: "Nova extensão de prazo" },
    { id: "avaliacao", nome: "Avaliações", icone: "star", botao: "Nova avaliação" }
  ];
  var CAUSAS = ["Liberação de área", "Mudança de escopo", "Informação de projeto tardia", "Interferência", "Suspensão", "Condição climática", "Força maior", "Outros"];
  var METODOS = ["Análise de impacto no tempo", "Análise por janelas", "Planejado x executado"];
  var CLASSIFICACOES = ["Justificável e compensável", "Justificável não compensável", "Não justificável"];
  var PROXIMA_MEDICAO = { "Em análise": [["Aprovada", "Aprovar"], ["Devolvida", "Devolver"]], "Aprovada": [["Faturada", "Faturar"]], "Faturada": [["Paga", "Registrar pagamento"]] };
  var PROXIMO_MARCO = { "Previsto": ["Evidência enviada", "Enviar evidência"], "Evidência enviada": ["Aprovado", "Aprovar"], "Aprovado": ["Faturado", "Faturar"], "Faturado": ["Pago", "Registrar pagamento"] };
  var PROXIMO_CLAIM = { "Notificado": ["Em análise"], "Em análise": ["Em negociação", "Rejeitado"], "Em negociação": ["Acordado", "Rejeitado", "Em disputa"],
    "Acordado": ["Encerrado"], "Rejeitado": ["Em disputa", "Encerrado"], "Em disputa": ["Acordado", "Encerrado"] };

  function sessao() { return GI.api.sessaoAtual().pessoaId; }
  function mesesContrato() {
    var l = [], d = new Date(ct.inicio.slice(0, 7) + "-01T00:00:00"), fim = REF.slice(0, 7);
    for (var k = 0; k < 60; k++) {
      var m = d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0");
      l.push(m); if (m >= fim) break;
      d.setMonth(d.getMonth() + 1);
    }
    return l.reverse();
  }
  function diaMes(iso) { return new Date(iso + "T00:00:00").toLocaleDateString(GI.i18n ? GI.i18n.locale : "pt-BR", { day: "2-digit", month: "2-digit" }); }
  function somaDias(iso, n) { var d = new Date(iso + "T00:00:00"); d.setDate(d.getDate() + n); return d.toISOString().slice(0, 10); }
  function botao(texto, attrs, variante) {
    return '<button type="button" class="btn btn--' + (variante || "secondary") + ' btn--sm" ' + attrs + ">" + U.esc(texto) + "</button>";
  }

  /* ---------------- Estrutura ---------------- */
  function montarEstrutura() {
    document.getElementById("abas").innerHTML = ABAS.map(function (a) {
      return '<button type="button" class="tab" role="tab" id="aba-' + a.id + '" aria-controls="p-' + a.id + '" aria-selected="' + (a.id === abaAtual) + '">' +
        U.icone(a.icone) + U.esc(a.nome) + (a.id === "resumo" ? "" : ' <span class="tab__count" id="n-' + a.id + '"></span>') + "</button>";
    }).join("");
    document.getElementById("paineis").innerHTML = ABAS.map(function (a) {
      if (a.id === "resumo") {
        return '<section class="tab-panel" role="tabpanel" id="p-resumo" aria-labelledby="aba-resumo"' + (abaAtual === "resumo" ? "" : " hidden") + '><div class="grid grid--2">' +
          '<section class="card" aria-labelledby="t-cascata"><div class="card__header"><div><h2 class="card__title" id="t-cascata">Composição do valor</h2>' +
          '<p class="card__subtitle">Valor original, aditivos, medido e saldo a faturar</p></div></div><div class="chart"><canvas id="g-cascata"></canvas></div></section>' +
          '<section class="card" aria-labelledby="t-dados"><div class="card__header"><div><h2 class="card__title" id="t-dados">Dados do contrato</h2></div></div><div id="dados"></div></section>' +
          "</div></section>";
      }
      return '<section class="tab-panel" role="tabpanel" id="p-' + a.id + '" aria-labelledby="aba-' + a.id + '"' + (abaAtual === a.id ? "" : " hidden") + ">" +
        '<div class="toolbar"><button type="button" class="btn btn--primary" data-novo="' + a.id + '">' + U.icone("plus") + U.esc(a.botao) + "</button>" +
        '<span class="text-small text-muted" id="sub-' + a.id + '"></span></div>' +
        (a.id === "avaliacao" ? '<section class="card mb-4" aria-labelledby="t-notas"><div class="card__header"><div><h2 class="card__title" id="t-notas">Nota por período</h2>' +
          '<p class="card__subtitle">Nota ponderada de 0 a 100; faixas das classes A a D nos parâmetros</p></div></div><div class="chart chart--sm"><canvas id="g-notas"></canvas></div></section>' : "") +
        '<section class="card card--flush"><div id="t-' + a.id + '"></div></section></section>';
    }).join("");
    GI.ui.init(document.getElementById("paineis"));
    document.getElementById("abas").addEventListener("tabs:change", function (ev) {
      abaAtual = ev.detail.id.slice(2);
      if (abaAtual === "resumo" || abaAtual === "avaliacao") desenharGraficos();
    });
    criarTabelas();
  }

  /* ---------------- Render ---------------- */
  function render() {
    document.title = ct.numero + " · Contratos | Gestão Integrada AMT";
    document.getElementById("titulo").textContent = "Contrato " + ct.numero;
    if (GI.layout) GI.layout.detalhe(ct.numero);
    var dias = ct.diasAditados;
    document.getElementById("faixa").innerHTML =
      '<section class="faixa" aria-label="Identificação do contrato"><div>' +
        '<div class="faixa__codigo">' + U.esc(ct.numero) + " · " + U.esc(ct.empresa) + "</div>" +
        '<div class="faixa__meta"><span>' + U.esc(ct.objeto) + "</span><span>" + U.esc(ct.modalidade) + "</span>" +
          "<span>" + U.icone("calendar", 14) + " " + F.data(ct.inicio) + " a " + F.data(ct.terminoVigente) + "</span>" +
          "<span>Gestor " + U.esc(U.pessoa(ct.gestorId)) + "</span><span>Fiscal " + U.esc(U.pessoa(ct.fiscalId)) + "</span></div>" +
      "</div>" + '<div class="faixa__acoes">' + U.badge(ct.situacao, "primary", true) + "</div></section>";
    /* Previsto até a data de referência: marcos de pagamento com data prevista vencida; sem marcos
       (preço unitário), a referência é o prazo decorrido do contrato */
    var comMarcos = ct.marcos.length > 0, prevPct;
    if (comMarcos) prevPct = ct.valorAtualCentavos ? ct.marcos.filter(function (m) { return m.prevista <= REF; }).reduce(function (s, m) { return s + (m.valorCentavos || 0); }, 0) / ct.valorAtualCentavos * 100 : null;
    else {
      var ini = Date.parse(ct.inicio), fim = Date.parse(ct.terminoVigente), ref = Date.parse(REF);
      prevPct = fim > ini ? Math.max(0, Math.min(100, (ref - ini) / (fim - ini) * 100)) : null;
    }
    if (prevPct != null) prevPct = Math.min(100, prevPct);
    var rotPrev = comMarcos ? "Previsto" : "Referência";
    document.getElementById("kpis").innerHTML = [
      U.kpi({ rotulo: "Valor atual", moeda: ct.valorAtualCentavos, icone: "fileContract", cor: "primary",
        esperado: { rotulo: "Linha de base", valor: F.moedaCompacta(ct.valorOriginalCentavos) },
        rodape: "aditivos " + F.moedaCompacta(ct.aditivosCentavos) }),
      U.kpi({ rotulo: "Medido aprovado", valor: F.num(ct.medidoPct, 1), unidade: "%", icone: "coins", cor: "info", rodape: F.moedaCompacta(ct.medidoCentavos) + " · pago " + F.moedaCompacta(ct.pagoCentavos),
        esperado: { rotulo: rotPrev, valor: prevPct == null ? "·" : F.pct(prevPct, 1) } }),
      U.kpi({ rotulo: "Saldo a faturar", moeda: ct.saldoCentavos, icone: "money", cor: "info", rodape: "retido " + F.moedaCompacta(ct.retidoCentavos) + " (" + F.num(ct.retencaoPct) + "%)",
        esperado: { rotulo: rotPrev, valor: prevPct == null ? "·" : F.moedaCompacta(Math.round(ct.valorAtualCentavos * (100 - prevPct) / 100)) } }),
      U.kpi({ rotulo: "Término vigente", valor: diaMes(ct.terminoVigente), unidade: "/" + ct.terminoVigente.slice(0, 4), icone: "calendarClock", cor: dias > 0 ? "warning" : "success",
        esperado: { rotulo: "Linha de base", valor: F.data(ct.terminoOriginal) },
        rodape: dias > 0 ? "+" + U.plural(dias, "dia") + " sobre o original" : "no prazo original" })
    ].join("");

    var linhas = [
      ["Contratada", ct.empresa], ["Objeto", ct.objeto], ["Modalidade", ct.modalidade], ["Pacote de compra", ct.pacoteCompra],
      ["Item da EAC", ct.eacCodigo], ["Data de início", F.data(ct.inicio)], ["Término original", F.data(ct.terminoOriginal)], ["Término vigente", F.data(ct.terminoVigente)],
      ["Retenção contratual", F.num(ct.retencaoPct) + "%"], ["Prazo de notificação de claims", U.plural(ct.prazoNotificacaoClaimDias, "dia")],
      ["Faturado", F.moeda(ct.faturadoCentavos)], ["Pago", F.moeda(ct.pagoCentavos)], ["Gestor do contrato", U.pessoa(ct.gestorId)], ["Fiscal", U.pessoa(ct.fiscalId)]
    ];
    document.getElementById("dados").innerHTML = '<dl class="dl">' + linhas.map(function (l) { return "<dt>" + U.esc(l[0]) + "</dt><dd>" + U.esc(l[1] || "·") + "</dd>"; }).join("") + "</dl>";

    t.medicoes.atualizar(ct.medicoes.slice().reverse());
    t.aditivos.atualizar(ct.aditivos.slice().reverse());
    t.marcos.atualizar(ct.marcos);
    t.claims.atualizar(ct.claims.slice().reverse());
    t.eot.atualizar(ct.extensoes.slice().reverse());
    t.avaliacao.atualizar(ct.avaliacoes.slice().reverse());
    ["medicoes", "aditivos", "marcos", "claims", "eot", "avaliacao"].forEach(function (k) {
      var lista = { medicoes: ct.medicoes, aditivos: ct.aditivos, marcos: ct.marcos, claims: ct.claims, eot: ct.extensoes, avaliacao: ct.avaliacoes }[k];
      document.getElementById("n-" + k).textContent = lista.length;
    });
    var somaPct = ct.marcos.reduce(function (s, m) { return s + m.pct; }, 0);
    document.getElementById("sub-medicoes").textContent = "Em análise > Aprovada > Faturada > Paga (ou Devolvida) · retenção de " + F.num(ct.retencaoPct) + "%";
    document.getElementById("sub-aditivos").textContent = "Aditivos somam ao valor; dias prorrogam o término vigente";
    document.getElementById("sub-marcos").textContent = "Soma dos marcos: " + F.num(somaPct) + "% · marco só é aprovado com evidência anexada";
    document.getElementById("sub-claims").textContent = "Prazo contratual de notificação: " + U.plural(ct.prazoNotificacaoClaimDias, "dia") + " após o evento";
    document.getElementById("sub-eot").textContent = "Concedida prorroga o término vigente e pede SM para a linha de base do cronograma";
    document.getElementById("sub-avaliacao").textContent = "Mensal durante a execução e final no encerramento";
    desenharGraficos();
  }

  function desenharGraficos() {
    if (!ct) return;
    if (abaAtual === "resumo") {
      GI.charts.waterfall("g-cascata", {
        ariaLabel: "Composição do valor do contrato",
        steps: [
          { label: "Valor original", value: ct.valorOriginalCentavos, type: "total" },
          { label: "Aditivos", value: Math.abs(ct.aditivosCentavos), type: ct.aditivosCentavos >= 0 ? "aumento" : "reducao" },
          { label: "Valor atual", type: "total" },
          { label: "Medido", value: ct.medidoCentavos, type: "reducao" },
          { label: "Saldo a faturar", type: "total" }
        ]
      });
    }
    if (abaAtual === "avaliacao") {
      GI.charts.line("g-notas", {
        labels: ct.avaliacoes.map(function (a) { return U.mesCurto(a.periodo) + (a.tipo === "Final" ? " (final)" : ""); }), min: 0, max: 100,
        ariaLabel: "Nota da contratada por período",
        series: [
          { label: "Nota", data: ct.avaliacoes.map(function (a) { return a.nota; }), color: "chart-1" },
          { label: "Classe B (mínimo)", data: ct.avaliacoes.map(function () { return classeMinimo("B"); }), color: "chart-outros", dashed: true, points: false }
        ]
      });
    }
  }
  function classeMinimo(c) { var x = param.avaliacaoContratada.classes.filter(function (k) { return k.classe === c; })[0]; return x ? x.minimo : null; }

  /* ---------------- Tabelas ---------------- */
  function criarTabelas() {
    t.medicoes = GI.tabela.criar("t-medicoes", {
      porPagina: 20, legenda: "Medições", vazio: "Nenhuma medição registrada.",
      colunas: [
        { id: "numero", titulo: "Nº", html: function (m) { return "<b>" + U.esc(m.numero) + "</b>"; } },
        { id: "periodo", titulo: "Período", html: function (m) { return U.esc(U.mesCurto(m.periodo)); }, exportar: function (m) { return U.mesCurto(m.periodo); } },
        { id: "brutoCentavos", titulo: "Valor bruto", tipo: "moeda" },
        { id: "retencaoCentavos", titulo: "Retenção", tipo: "moeda" },
        { id: "liquidoCentavos", titulo: "Valor líquido", tipo: "moeda" },
        { id: "marco", titulo: "Marco", valor: function (m) { var k = ct.marcos.filter(function (x) { return x.id === m.marcoId; })[0]; return k ? k.numero : ""; } },
        { id: "situacao", titulo: "Situação", html: function (m) { return GI.fin.situacao(m.situacao) + (m.motivo ? '<br><small class="text-muted">' + U.esc(m.motivo) + "</small>" : ""); } }
      ],
      acoes: function (m) { return (PROXIMA_MEDICAO[m.situacao] || []).map(function (p) { return botao(p[1], 'data-medicao="' + m.id + '" data-para="' + p[0] + '"', p[0] === "Devolvida" ? "ghost" : "secondary"); }).join(""); }
    });
    t.aditivos = GI.tabela.criar("t-aditivos", {
      porPagina: 20, legenda: "Aditivos", vazio: "Nenhum aditivo registrado.",
      colunas: [
        { id: "numero", titulo: "Nº", html: function (a) { return "<b>" + U.esc(a.numero) + "</b>"; } },
        { id: "data", titulo: "Data", tipo: "data" },
        { id: "valorCentavos", titulo: "Valor", tipo: "moeda" },
        { id: "dias", titulo: "Dias", tipo: "num" },
        { id: "motivo", titulo: "Motivo" },
        { id: "smRef", titulo: "SM", html: function (a) { return a.smRef ? '<a href="' + U.tela("governanca", "mudanca", { codigo: a.smRef }) + '">' + U.esc(a.smRef) + "</a>" : ""; } },
        { id: "claimRef", titulo: "Claim" }
      ]
    });
    t.marcos = GI.tabela.criar("t-marcos", {
      porPagina: 20, legenda: "Marcos de pagamento", vazio: "Nenhum marco cadastrado.",
      colunas: [
        { id: "numero", titulo: "Marco", valor: function (m) { return m.numero + " " + m.descricao; },
          html: function (m) { return '<div class="cell-title"><b>' + U.esc(m.numero + " " + m.descricao) + "</b><small>" + U.esc("Aceite: " + m.criterio) + "</small></div>"; } },
        { id: "pct", titulo: "%", tipo: "pct", casas: 0 },
        { id: "valorCentavos", titulo: "Valor", tipo: "moeda" },
        { id: "prevista", titulo: "Prevista", tipo: "data",
          html: function (m) { return U.esc(F.data(m.prevista)) + (m.atrasado ? '<br><span class="text-small valor--negativo">' + U.plural(m.diasAtraso, "dia") + " de atraso</span>" : ""); } },
        { id: "conclusao", titulo: "Conclusão", tipo: "data" },
        { id: "situacao", titulo: "Situação", html: function (m) { return GI.fin.situacao(m.situacao) + (m.evidencias && m.evidencias.length ? '<br><small class="text-muted">' + U.plural(m.evidencias.length, "evidência") + "</small>" : ""); } }
      ],
      classeLinha: function (m) { return m.atrasado ? "is-alert" : ""; },
      acoes: function (m) { var p = PROXIMO_MARCO[m.situacao]; return p ? botao(p[1], 'data-marco="' + m.id + '" data-para="' + p[0] + '"') : ""; },
      rodape: function (l) { return { numero: "<b>Total</b>", pct: "<b>" + F.num(l.reduce(function (s, m) { return s + m.pct; }, 0)) + "%</b>", valorCentavos: "<b>" + U.esc(F.moeda(l.reduce(function (s, m) { return s + m.valorCentavos; }, 0))) + "</b>" }; }
    });
    t.claims = GI.tabela.criar("t-claims", {
      porPagina: 20, compacta: true, legenda: "Claims", vazio: "Nenhum claim registrado.",
      colunas: [
        { id: "codigo", titulo: "Código", html: function (c) { return "<b>" + U.esc(c.codigo) + "</b>"; } },
        { id: "direcao", titulo: "Direção / tipo", valor: function (c) { return c.direcao + " · " + c.tipo; },
          html: function (c) { return '<div class="cell-title"><b>' + U.esc(c.direcao) + "</b><small>" + U.esc(c.tipo + " · " + c.causa) + "</small></div>"; } },
        { id: "descricao", titulo: "Descrição", html: function (c) { return U.esc(c.descricao) + (c.clausula ? '<br><small class="text-muted">' + U.esc("Cláusula " + c.clausula) + "</small>" : ""); } },
        { id: "notificacao", titulo: "Notificação", tipo: "data",
          html: function (c) { return U.esc(F.data(c.notificacao)) + '<br><span class="text-small ' + (c.foraDoPrazo ? "valor--negativo" : "text-muted") + '">' + U.plural(c.diasParaNotificar, "dia") + " após o evento" + (c.foraDoPrazo ? " · fora do prazo" : "") + "</span>"; } },
        { id: "pleiteadoCentavos", titulo: "Pleiteado", tipo: "moeda",
          html: function (c) { return U.esc(F.moeda(c.pleiteadoCentavos)) + (c.diasPleiteados ? '<br><small class="text-muted">' + U.plural(c.diasPleiteados, "dia") + "</small>" : ""); } },
        { id: "reconhecidoCentavos", titulo: "Reconhecido", tipo: "moeda",
          html: function (c) { return c.reconhecidoCentavos == null ? "" : U.esc(F.moeda(c.reconhecidoCentavos)) + (c.diasReconhecidos ? '<br><small class="text-muted">' + U.plural(c.diasReconhecidos, "dia") + "</small>" : ""); } },
        { id: "situacao", titulo: "Situação", html: function (c) { return GI.fin.situacao(c.situacao); } }
      ],
      acoes: function (c) { return PROXIMO_CLAIM[c.situacao] ? botao("Atualizar", 'data-claim="' + c.id + '"') : ""; }
    });
    t.eot = GI.tabela.criar("t-eot", {
      porPagina: 20, legenda: "Extensões de prazo", vazio: "Nenhuma extensão de prazo registrada.",
      colunas: [
        { id: "codigo", titulo: "Código", html: function (e) { return "<b>" + U.esc(e.codigo) + "</b>" + (e.claimRef ? '<br><small class="text-muted">' + U.esc(e.claimRef) + "</small>" : ""); } },
        { id: "evento", titulo: "Evento causador" },
        { id: "diasSolicitados", titulo: "Solicitados", tipo: "num" },
        { id: "diasConcedidos", titulo: "Concedidos", tipo: "num" },
        { id: "classificacao", titulo: "Classificação" },
        { id: "metodo", titulo: "Análise de atraso", html: function (e) { return U.esc(e.metodo || "") + (e.marcoAfetado ? '<br><small class="text-muted">' + U.esc(e.marcoAfetado) + "</small>" : ""); } },
        { id: "situacao", titulo: "Situação", html: function (e) { return GI.fin.situacao(e.situacao); } }
      ],
      acoes: function (e) { return e.aberta ? botao("Decidir", 'data-eot="' + e.id + '"') : ""; }
    });
    var crit = param.avaliacaoContratada.criterios;
    t.avaliacao = GI.tabela.criar("t-avaliacao", {
      porPagina: 20, compacta: true, legenda: "Avaliações de desempenho", vazio: "Nenhuma avaliação registrada.",
      colunas: [
        { id: "periodo", titulo: "Período", html: function (a) { return "<b>" + U.esc(U.mesCurto(a.periodo)) + "</b>"; }, exportar: function (a) { return U.mesCurto(a.periodo); } },
        { id: "tipo", titulo: "Tipo" },
        { id: "nota", titulo: "Nota", tipo: "num", html: function (a) { return "<b>" + F.num(a.nota) + "</b>"; } },
        { id: "classe", titulo: "Classe", html: function (a) { return GI.fin.classe(a.classe); } }
      ].concat(crit.map(function (c) {
        return { id: "n-" + c.id, titulo: c.nome, tipo: "num", valor: function (a) { return a.notas[c.id]; },
          html: function (a) { var n = a.notas[c.id]; return '<span class="' + (n <= param.avaliacaoContratada.notaExigePlano ? "valor--negativo" : "") + '">' + (n == null ? "" : n) + "</span>"; } };
      })).concat([
        { id: "exigePlano", titulo: "Plano de melhoria", valor: function (a) { return a.exigePlano ? "Exigido" : ""; }, html: function (a) { return a.exigePlano ? U.badge("Exigido", "warning") : ""; } },
        { id: "comentario", titulo: "Comentário", oculta: true },
        { id: "avaliador", titulo: "Avaliador", valor: function (a) { return U.pessoa(a.avaliadorId); }, oculta: true }
      ])
    });
    document.getElementById("paineis").addEventListener("click", clique);
  }

  function clique(ev) {
    var b = ev.target.closest("button");
    if (!b) return;
    if (b.hasAttribute("data-novo")) { NOVO[b.getAttribute("data-novo")](); return; }
    if (b.hasAttribute("data-medicao")) { avancarMedicao(Number(b.getAttribute("data-medicao")), b.getAttribute("data-para")); return; }
    if (b.hasAttribute("data-marco")) { avancarMarco(Number(b.getAttribute("data-marco")), b.getAttribute("data-para")); return; }
    if (b.hasAttribute("data-claim")) { atualizarClaim(Number(b.getAttribute("data-claim"))); return; }
    if (b.hasAttribute("data-eot")) { decidirEot(Number(b.getAttribute("data-eot"))); }
  }

  function recarregar(msg) {
    if (msg) GI.ui.toast(msg, "success");
    return GI.api.financeiro.contrato(ct.numero).then(function (r) { ct = r; render(); });
  }
  function gravar(colecao, id, alterar) {
    return GI.api.obter(colecao, id).then(function (o) { alterar(o); return GI.api.salvar(colecao, o); });
  }

  /* ---------------- Medições ---------------- */
  function novaMedicao() {
    var livres = ct.marcos.filter(function (m) { return ["Aprovado"].indexOf(m.situacao) >= 0 && !ct.medicoes.some(function (x) { return x.marcoId === m.id; }); });
    var emAnalise = ct.medicoes.filter(function (m) { return m.situacao === "Em análise"; }).reduce(function (s, m) { return s + m.brutoCentavos; }, 0);
    var disponivel = ct.saldoCentavos - emAnalise;
    GI.form.abrir({
      titulo: "Nova medição", subtitulo: ct.numero + " · BM-" + ("0" + (ct.medicoes.length + 1)).slice(-2),
      campos: [
        { id: "periodo", rotulo: "Período", tipo: "select", obrigatorio: true, opcoes: mesesContrato().map(function (m) { return { valor: m, texto: U.mesCurto(m) }; }), valor: REF.slice(0, 7) },
        { id: "marco", rotulo: "Marco de pagamento", tipo: "select", opcoes: livres.map(function (m) { return { valor: m.id, texto: m.numero + " " + m.descricao + " · " + F.moeda(m.valorCentavos) }; }),
          vazio: livres.length ? "Sem marco (medição por quantidade)" : "Nenhum marco aprovado sem medição" },
        { id: "bruto", rotulo: "Valor bruto", tipo: "moeda", obrigatorio: true, ajuda: "Disponível no contrato: " + F.moeda(disponivel) },
        { id: "liquido", rotulo: "Retenção e líquido", tipo: "info", html: "" },
        { id: "observacao", rotulo: "Observação", tipo: "textarea", max: 300 }
      ],
      aoMudar: function (v, ctx) {
        if (v.marco) {
          var m = livres.filter(function (x) { return String(x.id) === String(v.marco); })[0];
          var campo = document.querySelector(".modal [data-campo='bruto'] input");
          if (m && campo && !campo.value) campo.value = GI.form.deCentavos(m.valorCentavos);
          v.bruto = GI.form.paraCentavos(campo ? campo.value : "");
        }
        var b = v.bruto > 0 ? v.bruto : 0, r = Math.round(b * ct.retencaoPct / 100);
        ctx.info("liquido", '<span class="num">Retenção ' + U.esc(F.moeda(r)) + " · líquido <b>" + U.esc(F.moeda(b - r)) + "</b></span>");
      },
      validar: function (v) {
        if (!(v.bruto > 0)) return [{ campo: "bruto", msg: "Informe um valor maior que zero." }];
        if (v.bruto > disponivel) return [{ campo: "bruto", msg: "Supera o saldo do contrato (" + F.moeda(disponivel) + "). Registre um aditivo antes." }];
        return [];
      },
      aoSalvar: function (v) {
        return GI.api.salvar("medicoes", { contratoId: ct.id, numero: "BM-" + ("0" + (ct.medicoes.length + 1)).slice(-2), periodo: v.periodo, brutoCentavos: v.bruto,
          situacao: "Em análise", marcoId: v.marco ? Number(v.marco) : null, observacao: v.observacao || "" })
          .then(function () { return recarregar("Medição registrada para análise do fiscal."); });
      }
    });
  }
  function avancarMedicao(id, para) {
    var m = ct.medicoes.filter(function (x) { return x.id === id; })[0];
    if (para === "Devolvida") {
      GI.form.abrir({
        titulo: "Devolver medição " + m.numero, subtitulo: F.moeda(m.brutoCentavos), textoSalvar: "Devolver", perigo: true,
        campos: [{ id: "motivo", rotulo: "Motivo da devolução", tipo: "textarea", obrigatorio: true, max: 300 }],
        aoSalvar: function (v) { return gravar("medicoes", id, function (o) { o.situacao = "Devolvida"; o.motivo = v.motivo; }).then(function () { return recarregar("Medição " + m.numero + " devolvida à contratada."); }); }
      });
      return;
    }
    var textos = { Aprovada: "Aprovar a medição " + m.numero + "? O valor passa a contar como medido e alimenta o realizado da EAC.",
      Faturada: "Registrar o faturamento da medição " + m.numero + "?", Paga: "Registrar o pagamento da medição " + m.numero + "?" };
    GI.modal.confirm({ title: "Medição " + m.numero, message: textos[para], okText: "Confirmar" }).then(function (ok) {
      if (!ok) return;
      gravar("medicoes", id, function (o) { o.situacao = para; }).then(function () {
        /* Medição de marco: faturamento e pagamento acompanham o marco */
        if (m.marcoId && (para === "Faturada" || para === "Paga")) return gravar("marcosPagamento", m.marcoId, function (o) { o.situacao = para === "Faturada" ? "Faturado" : "Pago"; });
      }).then(function () { recarregar("Medição " + m.numero + ": " + para.toLowerCase() + "."); });
    });
  }

  /* ---------------- Aditivos ---------------- */
  function novoAditivo() {
    GI.api.listar("mudancas", function (s) { return s.projetoId === ct.projetoId && ["Aprovada", "Aprovada com condições", "Em implementação", "Encerrada"].indexOf(s.situacao) >= 0; }).then(function (sms) {
      GI.form.abrir({
        titulo: "Novo aditivo", subtitulo: ct.numero,
        campos: [
          { id: "data", rotulo: "Data de assinatura", tipo: "data", obrigatorio: true, valor: REF },
          { id: "valor", rotulo: "Valor", tipo: "moeda", ajuda: "Use valor negativo para supressão." },
          { id: "dias", rotulo: "Prorrogação (dias)", tipo: "numero", min: 0, passo: 1, valor: 0 },
          { id: "sm", rotulo: "SM de origem", tipo: "select", opcoes: sms.map(function (s) { return { valor: s.codigo, texto: s.codigo + " " + s.titulo }; }), vazio: "Nenhuma" },
          { id: "claim", rotulo: "Claim de origem", tipo: "select", opcoes: ct.claims.filter(function (c) { return ["Acordado", "Encerrado"].indexOf(c.situacao) >= 0; }).map(function (c) { return c.codigo; }), vazio: "Nenhum" },
          { id: "motivo", rotulo: "Motivo", tipo: "textarea", obrigatorio: true, max: 300 }
        ],
        validar: function (v) { return !v.valor && !v.dias ? [{ campo: "valor", msg: "Informe valor, prorrogação ou ambos." }] : []; },
        aoSalvar: function (v) {
          return GI.api.financeiro.salvarAditivo(ct.id, { data: v.data, valorCentavos: v.valor || 0, dias: v.dias || 0, motivo: v.motivo, smRef: v.sm, claimRef: v.claim })
            .then(function (a) { return recarregar("Aditivo " + a.numero + " registrado" + (a.dias ? "; término vigente prorrogado em " + U.plural(a.dias, "dia") : "") + "."); });
        }
      });
    });
  }

  /* ---------------- Marcos de pagamento ---------------- */
  function novoMarco() {
    var usado = ct.marcos.reduce(function (s, m) { return s + m.pct; }, 0);
    GI.form.abrir({
      titulo: "Novo marco de pagamento", subtitulo: ct.numero + " · M" + (ct.marcos.length + 1) + " · " + F.num(100 - usado) + "% disponíveis",
      campos: [
        { id: "descricao", rotulo: "Descrição", tipo: "texto", obrigatorio: true, max: 120, largura: "full" },
        { id: "criterio", rotulo: "Critério de aceite (evidência exigida)", tipo: "texto", obrigatorio: true, max: 160, largura: "full" },
        { id: "pct", rotulo: "% do valor do contrato", tipo: "numero", obrigatorio: true, min: 0.1, maxNumero: 100, passo: 0.1 },
        { id: "valor", rotulo: "Valor do marco", tipo: "info", html: "" },
        { id: "prevista", rotulo: "Data prevista", tipo: "data", obrigatorio: true }
      ],
      aoMudar: function (v, ctx) { ctx.info("valor", '<b class="num">' + U.esc(F.moeda(v.pct > 0 ? Math.round(ct.valorAtualCentavos * v.pct / 100) : 0)) + "</b>"); },
      validar: function (v) { return usado + v.pct > 100.0001 ? [{ campo: "pct", msg: "A soma dos marcos passaria de 100% (restam " + F.num(100 - usado, 1) + "%)." }] : []; },
      aoSalvar: function (v) {
        return GI.api.salvar("marcosPagamento", { contratoId: ct.id, numero: "M" + (ct.marcos.length + 1), descricao: v.descricao, criterio: v.criterio, pct: v.pct,
          valorCentavos: Math.round(ct.valorAtualCentavos * v.pct / 100), prevista: v.prevista, conclusao: null, situacao: "Previsto" })
          .then(function () { return recarregar("Marco M" + (ct.marcos.length + 1) + " cadastrado."); });
      }
    });
  }
  function avancarMarco(id, para) {
    var m = ct.marcos.filter(function (x) { return x.id === id; })[0];
    if (para === "Evidência enviada") {
      GI.form.abrir({
        titulo: "Enviar evidência do marco " + m.numero, subtitulo: m.descricao,
        intro: '<p class="text-small text-muted">Critério de aceite: ' + U.esc(m.criterio) + "</p>",
        campos: [
          { id: "conclusao", rotulo: "Data de conclusão", tipo: "data", obrigatorio: true, valor: REF },
          { id: "evidencias", rotulo: "Evidências", tipo: "arquivo", obrigatorio: true },
          { id: "comentario", rotulo: "Comentário", tipo: "textarea", max: 300 }
        ],
        aoSalvar: function (v) {
          return gravar("marcosPagamento", id, function (o) { o.situacao = para; o.conclusao = v.conclusao; o.evidencias = v.evidencias; o.comentario = v.comentario; })
            .then(function () { return recarregar("Evidência do marco " + m.numero + " enviada para aprovação."); });
        }
      });
      return;
    }
    var textos = { "Aprovado": "Aprovar o marco " + m.numero + "? A aprovação registra o aceite do fiscal e do gestor do contrato.",
      "Faturado": "Registrar o faturamento do marco " + m.numero + "?", "Pago": "Registrar o pagamento do marco " + m.numero + "?" };
    GI.modal.confirm({ title: "Marco " + m.numero, message: textos[para], okText: "Confirmar" }).then(function (ok) {
      if (!ok) return;
      gravar("marcosPagamento", id, function (o) { o.situacao = para; if (para === "Aprovado") o.aprovadoPorId = sessao(); })
        .then(function () { recarregar("Marco " + m.numero + ": " + para.toLowerCase() + "."); });
    });
  }

  /* ---------------- Claims ---------------- */
  function novoClaim() {
    var prazo = ct.prazoNotificacaoClaimDias;
    var proj = U.projeto(ct.projetoId);
    var prefixo = "CLM-" + (proj ? proj.padraoAta : "TN-2026") + "-";
    GI.form.abrir({
      titulo: "Novo claim", subtitulo: ct.numero + " · " + GI.api.proximoCodigo("claims", prefixo), tamanho: "lg",
      campos: [
        { id: "direcao", rotulo: "Direção", tipo: "select", obrigatorio: true, valor: "Da contratada",
          opcoes: [{ valor: "Da contratada", texto: "Da contratada (pleito contra o contratante)" }, { valor: "Do contratante", texto: "Do contratante (back-charge)" }] },
        { id: "tipo", rotulo: "Tipo", tipo: "select", obrigatorio: true, opcoes: ["Prazo", "Custo", "Prazo e custo"] },
        { id: "causa", rotulo: "Causa", tipo: "select", obrigatorio: true, opcoes: CAUSAS },
        { id: "clausula", rotulo: "Cláusula contratual", tipo: "texto", max: 20, placeholder: "12.3" },
        { id: "descricao", rotulo: "Descrição", tipo: "textarea", obrigatorio: true, max: 300 },
        { id: "evento", rotulo: "Data do evento", tipo: "data", obrigatorio: true },
        { id: "notificacao", rotulo: "Data da notificação", tipo: "data", obrigatorio: true, valor: REF },
        { id: "prazo", rotulo: "", tipo: "info", html: "" },
        { id: "valor", rotulo: "Valor pleiteado", tipo: "moeda" },
        { id: "dias", rotulo: "Dias pleiteados", tipo: "numero", min: 0, passo: 1 },
        { id: "documentos", rotulo: "Documentos", tipo: "arquivo" }
      ],
      aoMudar: function (v, ctx) {
        if (!v.evento || !v.notificacao) { ctx.info("prazo", ""); return; }
        var d = Math.round((new Date(v.notificacao + "T00:00:00") - new Date(v.evento + "T00:00:00")) / 86400000);
        var fora = d > prazo;
        ctx.info("prazo", '<div class="alert' + (fora ? " alert--warning" : " alert--success") + '">' + U.icone(fora ? "alertTriangle" : "checkCircle") +
          '<div class="alert__body">Notificação ' + U.plural(d, "dia") + " após o evento: " + (fora ? "fora do prazo contratual de " : "dentro do prazo contratual de ") + U.plural(prazo, "dia") + ".</div></div>");
      },
      validar: function (v) {
        var e = [];
        if (v.evento && v.notificacao && v.notificacao < v.evento) e.push({ campo: "notificacao", msg: "A notificação não pode ser anterior ao evento." });
        if (v.tipo !== "Prazo" && !(v.valor > 0)) e.push({ campo: "valor", msg: "Informe o valor pleiteado." });
        if (v.tipo !== "Custo" && !(v.dias > 0)) e.push({ campo: "dias", msg: "Informe os dias pleiteados." });
        return e;
      },
      aoSalvar: function (v) {
        var codigo = GI.api.proximoCodigo("claims", prefixo);
        return GI.api.salvar("claims", { contratoId: ct.id, codigo: codigo, direcao: v.direcao, tipo: v.tipo, causa: v.causa, descricao: v.descricao, clausula: v.clausula,
          evento: v.evento, notificacao: v.notificacao, pleiteadoCentavos: v.valor || 0, diasPleiteados: v.dias || 0, reconhecidoCentavos: null, diasReconhecidos: null,
          situacao: "Notificado", encerramento: null, riscoRef: null, smRef: null, documentos: v.documentos, historico: [] })
          .then(function () { return recarregar("Claim " + codigo + " registrado."); });
      }
    });
  }
  function atualizarClaim(id) {
    var c = ct.claims.filter(function (x) { return x.id === id; })[0];
    var opcoes = PROXIMO_CLAIM[c.situacao] || [];
    GI.form.abrir({
      titulo: "Atualizar claim " + c.codigo, subtitulo: c.situacao + " · pleiteado " + F.moeda(c.pleiteadoCentavos) + (c.diasPleiteados ? " e " + U.plural(c.diasPleiteados, "dia") : ""),
      campos: [
        { id: "situacao", rotulo: "Nova situação", tipo: "select", obrigatorio: true, opcoes: opcoes, valor: opcoes[0] },
        { id: "reconhecido", rotulo: "Valor reconhecido", tipo: "moeda", obrigatorio: true, valor: c.reconhecidoCentavos,
          mostrarSe: function (v) { return v.situacao === "Acordado"; } },
        { id: "dias", rotulo: "Dias reconhecidos", tipo: "numero", min: 0, passo: 1, valor: c.diasReconhecidos,
          mostrarSe: function (v) { return v.situacao === "Acordado"; } },
        { id: "parecer", rotulo: "Parecer", tipo: "textarea", obrigatorio: true, max: 400 }
      ],
      validar: function (v) {
        if (v.situacao === "Acordado" && v.reconhecido > c.pleiteadoCentavos) return [{ campo: "reconhecido", msg: "O reconhecido não pode superar o pleiteado." }];
        return [];
      },
      aoSalvar: function (v) {
        return gravar("claims", id, function (o) {
          o.historico = (o.historico || []).concat([{ data: REF, de: o.situacao, para: v.situacao, parecer: v.parecer, porId: sessao() }]);
          o.situacao = v.situacao;
          if (v.situacao === "Acordado") { o.reconhecidoCentavos = v.reconhecido; o.diasReconhecidos = v.dias || 0; }
          if (v.situacao === "Rejeitado") { o.reconhecidoCentavos = 0; o.diasReconhecidos = 0; }
          if (v.situacao === "Encerrado") o.encerramento = REF;
        }).then(function () {
          return recarregar(v.situacao === "Acordado" && c.direcao === "Da contratada"
            ? "Claim " + c.codigo + " acordado. Registre a SM em 08 Governança para o aditivo e a linha de base."
            : "Claim " + c.codigo + ": " + v.situacao.toLowerCase() + ".");
        });
      }
    });
  }

  /* ---------------- Extensões de prazo ---------------- */
  function novaEot() {
    var proj = U.projeto(ct.projetoId);
    var prefixo = "EOT-" + (proj ? proj.padraoAta : "TN-2026") + "-";
    GI.form.abrir({
      titulo: "Nova extensão de prazo", subtitulo: ct.numero + " · " + GI.api.proximoCodigo("extensoesPrazo", prefixo),
      campos: [
        { id: "claim", rotulo: "Claim relacionado", tipo: "select", opcoes: ct.claims.filter(function (c) { return c.tipo !== "Custo"; }).map(function (c) { return { valor: c.codigo, texto: c.codigo + " " + c.causa }; }), vazio: "Nenhum" },
        { id: "evento", rotulo: "Evento causador", tipo: "textarea", obrigatorio: true, max: 300 },
        { id: "dias", rotulo: "Dias solicitados", tipo: "numero", obrigatorio: true, min: 1, passo: 1 },
        { id: "marco", rotulo: "Marco contratual afetado", tipo: "texto", obrigatorio: true, max: 120 },
        { id: "metodo", rotulo: "Método de análise de atraso", tipo: "select", obrigatorio: true, opcoes: METODOS }
      ],
      aoSalvar: function (v) {
        var codigo = GI.api.proximoCodigo("extensoesPrazo", prefixo);
        return GI.api.salvar("extensoesPrazo", { contratoId: ct.id, codigo: codigo, claimRef: v.claim || null, evento: v.evento, diasSolicitados: v.dias, diasConcedidos: null,
          classificacao: null, metodo: v.metodo, marcoAfetado: v.marco, data: REF, decisao: null, situacao: "Solicitada" })
          .then(function () { return recarregar("Extensão de prazo " + codigo + " registrada."); });
      }
    });
  }
  function decidirEot(id) {
    var e = ct.extensoes.filter(function (x) { return x.id === id; })[0];
    GI.form.abrir({
      titulo: "Decidir extensão " + e.codigo, subtitulo: U.plural(e.diasSolicitados, "dia") + " solicitados · " + e.marcoAfetado,
      campos: [
        { id: "situacao", rotulo: "Decisão", tipo: "select", obrigatorio: true, opcoes: ["Concedida", "Concedida parcialmente", "Negada"] },
        { id: "dias", rotulo: "Dias concedidos", tipo: "numero", obrigatorio: true, min: 1, maxNumero: e.diasSolicitados, passo: 1,
          mostrarSe: function (v) { return v.situacao && v.situacao !== "Negada"; } },
        { id: "classificacao", rotulo: "Classificação", tipo: "select", obrigatorio: true, opcoes: CLASSIFICACOES,
          mostrarSe: function (v) { return v.situacao && v.situacao !== "Negada"; } },
        { id: "parecer", rotulo: "Parecer da análise de atraso", tipo: "textarea", obrigatorio: true, max: 400 }
      ],
      validar: function (v) {
        if (v.situacao === "Concedida" && v.dias !== e.diasSolicitados) return [{ campo: "dias", msg: "Concedida integralmente: " + U.plural(e.diasSolicitados, "dia") + ". Use Concedida parcialmente para menos dias." }];
        if (v.situacao === "Concedida parcialmente" && v.dias >= e.diasSolicitados) return [{ campo: "dias", msg: "Parcial precisa ser menor que o solicitado." }];
        return [];
      },
      aoSalvar: function (v) {
        return GI.api.financeiro.decidirEot(id, { situacao: v.situacao, diasConcedidos: v.dias, classificacao: v.classificacao }).then(function () {
          return gravar("extensoesPrazo", id, function (o) { o.parecer = v.parecer; o.decididoPorId = sessao(); });
        }).then(function () {
          return recarregar(v.situacao === "Negada" ? "Extensão " + e.codigo + " negada." :
            "Término vigente prorrogado em " + U.plural(v.dias, "dia") + ". Abra a SM em 08 Governança para a linha de base do cronograma.");
        });
      }
    });
  }

  /* ---------------- Avaliação de desempenho ---------------- */
  function novaAvaliacao() {
    var pa = param.avaliacaoContratada;
    var NOTAS = [{ valor: 5, texto: "5 · Excelente" }, { valor: 4, texto: "4 · Bom" }, { valor: 3, texto: "3 · Regular" }, { valor: 2, texto: "2 · Fraco" }, { valor: 1, texto: "1 · Insatisfatório" }];
    GI.form.abrir({
      titulo: "Nova avaliação de desempenho", subtitulo: ct.numero + " · " + ct.empresa, tamanho: "lg", colunas: 3,
      campos: [
        { id: "periodo", rotulo: "Período", tipo: "select", obrigatorio: true, opcoes: mesesContrato().map(function (m) { return { valor: m, texto: U.mesCurto(m) }; }), valor: REF.slice(0, 7) },
        { id: "tipo", rotulo: "Tipo", tipo: "select", obrigatorio: true, opcoes: ["Mensal", "Final"], valor: "Mensal" }
      ].concat(pa.criterios.map(function (c) {
        return { id: c.id, rotulo: c.nome + " (peso " + c.peso + "%)", tipo: "select", obrigatorio: true, opcoes: NOTAS };
      })).concat([
        { id: "resultado", rotulo: "Resultado", tipo: "info", html: '<span class="text-muted">Preencha as notas</span>' },
        { id: "comentario", rotulo: "Comentário e evidências", tipo: "textarea", max: 400 }
      ]),
      aoMudar: function (v, ctx) {
        var notas = {}; pa.criterios.forEach(function (c) { notas[c.id] = Number(v[c.id]) || null; });
        if (pa.criterios.some(function (c) { return !notas[c.id]; })) { ctx.info("resultado", '<span class="text-muted">Preencha as notas</span>'); return; }
        var r = GI.regras.avaliarContratada(notas, pa);
        ctx.info("resultado", '<span class="cluster"><b class="num">Nota ' + r.nota + "</b> " + GI.fin.classe(r.classe.classe, r.classe.descricao) +
          (r.exigePlano ? " " + U.badge("Exige plano de melhoria", "warning") : "") + "</span>");
      },
      validar: function (v) {
        return ct.avaliacoes.some(function (a) { return a.periodo === v.periodo && a.tipo === v.tipo; }) ? [{ campo: "periodo", msg: "Já existe avaliação " + v.tipo.toLowerCase() + " neste período." }] : [];
      },
      aoSalvar: function (v) {
        var notas = {}, pesos = {};
        pa.criterios.forEach(function (c) { notas[c.id] = Number(v[c.id]); pesos[c.id] = c.peso; });
        var r = GI.regras.avaliarContratada(notas, pa);
        var fracos = pa.criterios.filter(function (c) { return notas[c.id] <= pa.notaExigePlano; });
        if (r.exigePlano && !v.comentario) return Promise.reject({ erros: [{ campo: "comentario", msg: "Nota " + pa.notaExigePlano + " ou menor exige evidência no comentário." }] });
        return GI.api.salvar("avaliacoes", { contratoId: ct.id, periodo: v.periodo, tipo: v.tipo, avaliadorId: sessao(), parametrosVersao: param.versao,
          pesos: pesos, notas: notas, comentario: v.comentario || "" }).then(function () {
          if (!r.exigePlano) return null;
          return GI.api.salvar("acoes", { projetoId: ct.projetoId, origem: "Contrato", origemRef: ct.numero, grupo: "Avaliação da contratada", tipo: "Ação",
            assunto: "Plano de melhoria da " + ct.empresa, descricao: "Notas baixas em " + fracos.map(function (c) { return c.nome; }).join(", ") + " na avaliação de " + U.mesCurto(v.periodo) + ".",
            solicitanteId: sessao(), responsavelId: ct.gestorId, prevista: somaDias(REF, 15), replanejada: null, conclusao: null });
        }).then(function (acao) {
          return recarregar("Avaliação registrada: nota " + r.nota + " (classe " + r.classe.classe + ")." + (acao ? " Ação de plano de melhoria criada na Central." : ""));
        });
      }
    });
  }

  var NOVO = { medicoes: novaMedicao, aditivos: novoAditivo, marcos: novoMarco, claims: novoClaim, eot: novaEot, avaliacao: novaAvaliacao };

  /* ---------------- Exportação ---------------- */
  GI.exportar.registrar(function () {
    if (!ct) return null;
    return {
      titulo: "Contrato " + ct.numero, subtitulo: ct.empresa + " · " + ct.objeto, arquivo: "contrato-" + ct.numero, orientacao: "l",
      blocos: [
        { tipo: "kpis", titulo: "Resumo", itens: Array.prototype.map.call(document.querySelectorAll("#kpis .kpi"), function (k) {
            return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" };
          }) },
        { tipo: "tabela", titulo: "Medições", dados: t.medicoes.exportacao() },
        { tipo: "tabela", titulo: "Aditivos", dados: t.aditivos.exportacao() },
        { tipo: "tabela", titulo: "Marcos de pagamento", dados: t.marcos.exportacao() },
        { tipo: "tabela", titulo: "Claims", dados: t.claims.exportacao() },
        { tipo: "tabela", titulo: "Extensões de prazo", dados: t.eot.exportacao() },
        { tipo: "tabela", titulo: "Avaliações de desempenho", dados: t.avaliacao.exportacao() }
      ]
    };
  });

  /* ---------------- Início ---------------- */
  GI.util.pronto().then(function () {
    return GI.api.parametros();
  }).then(function (p) {
    param = p;
    if (numero) return numero;
    return GI.api.financeiro.contratos(GI.api.projetoAtualId()).then(function (l) { return l.length ? l[0].numero : null; });
  }).then(function (n) {
    if (!n) { document.getElementById("faixa").innerHTML = '<section class="card">' + U.vazio("Nenhum contrato cadastrado.", "fileContract", "Sem contratos") + "</section>"; return; }
    return GI.api.financeiro.contrato(n).then(function (r) {
      if (!r) { document.getElementById("faixa").innerHTML = '<section class="card">' + U.vazio("Contrato " + n + " não encontrado.", "fileContract", "Contrato não encontrado") + "</section>"; return; }
      ct = r;
      montarEstrutura();
      render();
    });
  });
})(window.GI = window.GI || {});
