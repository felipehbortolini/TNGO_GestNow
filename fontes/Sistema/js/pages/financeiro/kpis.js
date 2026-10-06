/* ==========================================================================
   Gestão Financeira > KPIs de custo
   Valor agregado (EV = % físico real x orçamento): CPI, SPI, CV, VAC,
   contingência e comprometido, com variação em relação ao mês anterior.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt;
  var projetoId, ind = null, hist = [], tabela, tResumo, tProj = null, limiteCont = null;

  function delta(atual, anterior, casas, inverter) {
    if (anterior == null || atual == null) return "";
    var d = Math.round((atual - anterior) * Math.pow(10, casas)) / Math.pow(10, casas);
    var cls = d === 0 ? "flat" : (d > 0) !== !!inverter ? "up" : "down";
    var ic = d === 0 ? "" : U.icone(d > 0 ? "arrowUp" : "arrowDown");
    return '<span class="kpi__delta kpi__delta--' + cls + '">' + ic + F.num(Math.abs(d), casas) + "</span> ";
  }
  function corIndice(v) { return v >= 1 ? "success" : v >= 0.95 ? "warning" : "danger"; }
  function sinal(c) { return (c > 0 ? "+" : "") + F.moedaCompacta(c); }

  function render() {
    var el = document.getElementById("kpis");
    if (!ind || !ind.atual) {
      el.innerHTML = "";
      document.getElementById("sub-corte").textContent = projetoId == null ? "Nenhum projeto da carteira tem curva física e financeira para o valor agregado." : "Este projeto ainda não tem curva física e financeira para o valor agregado.";
      GI.charts.line("g-indices", { labels: [], series: [] }); GI.charts.line("g-va", { labels: [], series: [] });
      tabela.atualizar([]); tResumo.atualizar([]);
      return;
    }
    var a = ind.atual, b = ind.anterior || {};
    el.innerHTML = [
      U.kpi({ rotulo: "CPI (desempenho de custo)", valor: F.indice(a.cpi), icone: "gauge", cor: corIndice(a.cpi), rodape: delta(a.cpi, b.cpi, 2) + "vs. mês anterior",
        esperado: { rotulo: "Meta", valor: "≥ " + F.indice(1) } }),
      U.kpi({ rotulo: "SPI (desempenho de prazo)", valor: F.indice(a.spi), icone: "curve", cor: corIndice(a.spi), rodape: delta(a.spi, b.spi, 2) + "vs. mês anterior",
        esperado: { rotulo: "Meta", valor: "≥ " + F.indice(1) },
        href: U.tela("planejamento", "kpis", { projeto: projetoId }) }),
      U.kpi({ rotulo: "CV (variação de custo)", moeda: a.cv, sinal: true, icone: "coins", cor: a.cv < 0 ? "danger" : "success", rodape: "EV menos AC · mês anterior " + sinal(b.cv),
        esperado: { rotulo: "Meta", valor: "≥ 0" } }),
      U.kpi({ rotulo: "VAC (variação no término)", moeda: ind.vac, sinal: true, icone: "target", cor: ind.vac < 0 ? "danger" : "success",
        esperado: { rotulo: "Meta", valor: "≥ 0" },
        rodape: "orçamento menos projeção no término", href: U.tela("financeiro", "mapa-controle", { projeto: projetoId }) }),
      U.kpi({ rotulo: "Contingência consumida", valor: F.num(ind.contingenciaPct, 1), unidade: "%", icone: "shieldCheck", cor: ind.contingenciaPct > 50 ? "warning" : "success",
        esperado: { rotulo: "Limite", valor: limiteCont == null ? "·" : F.pct(limiteCont, 1) },
        rodape: F.moedaCompacta(ind.contingenciaConsumida) + " de " + F.moedaCompacta(ind.contingencia) }),
      U.kpi({ rotulo: "Comprometido", valor: F.num(ind.comprometidoPct, 1), unidade: "%", icone: "fileContract", cor: "info",
        esperado: { rotulo: "Orçado", valor: F.moedaCompacta(ind.bac) },
        rodape: F.moedaCompacta(ind.comprometido) + " do orçamento" })
    ].join("");
    document.getElementById("sub-corte").textContent = "Corte em " + U.mesCurto(ind.corte) + (projetoId == null ? " · carteira: soma do EV, PV e AC dos projetos (EV de cada projeto = avanço físico real x BAC)" : " · EV = avanço físico real x orçamento (BAC)");
    renderProjetos();

    var labels = hist.map(function (h) { return U.mesCurto(h.mes); });
    GI.charts.line("g-indices", {
      labels: labels, min: 0.8, max: 1.1, casas: 2, ariaLabel: "CPI e SPI por mês",
      series: [
        { label: "CPI", data: hist.map(function (h) { return h.cpi; }), color: "chart-1" },
        { label: "SPI", data: hist.map(function (h) { return h.spi; }), color: "chart-2" },
        { label: "Meta", data: hist.map(function () { return 1; }), color: "chart-outros", dashed: true, points: false }
      ]
    });
    GI.charts.line("g-va", {
      labels: labels, money: true, ariaLabel: "Valor agregado acumulado: PV, EV e AC por mês",
      series: [
        { label: "PV (planejado)", data: hist.map(function (h) { return h.pv; }), color: "chart-baseline", dashed: true, points: false },
        { label: "EV (agregado)", data: hist.map(function (h) { return h.ev; }), color: "chart-1" },
        { label: "AC (custo real)", data: hist.map(function (h) { return h.ac; }), color: "chart-2" }
      ]
    });
    tResumo.atualizar([
      { sigla: "BAC", nome: "Orçamento no término", valor: ind.bac, leitura: "Orçado atual da EAC" },
      { sigla: "PV", nome: "Valor planejado", valor: a.pv, leitura: "Avanço físico previsto x BAC" },
      { sigla: "EV", nome: "Valor agregado", valor: a.ev, leitura: "Avanço físico real x BAC" },
      { sigla: "AC", nome: "Custo real", valor: a.ac, leitura: "Realizado acumulado" },
      { sigla: "CV", nome: "Variação de custo", valor: a.cv, leitura: a.cv < 0 ? "Gastou mais do que agregou" : "Agregou mais do que gastou" },
      { sigla: "SV", nome: "Variação de prazo", valor: a.sv, leitura: a.sv < 0 ? "Agregou menos do que o planejado" : "Agregou mais do que o planejado" },
      { sigla: "EAC (CPI)", nome: "Estimativa no término pelo CPI", valor: ind.eacPorCpi, leitura: "BAC ÷ CPI: se o desempenho de custo se mantiver" },
      { sigla: "Projeção", nome: "Projeção no término (bottom-up)", valor: ind.projecaoTermino, leitura: "Soma das projeções dos responsáveis por item" },
      { sigla: "VAC", nome: "Variação no término", valor: ind.vac, leitura: "BAC menos projeção no término" },
      { sigla: "TCPI", nome: "Índice de desempenho a completar", indice: ind.tcpi, leitura: ind.tcpi > 1 ? "Precisa render mais do que até agora para fechar no BAC" : "Fecha no BAC mantendo o ritmo" }
    ]);
    tabela.atualizar(hist.slice().reverse());
  }

  /* Portfólio: índices de cada projeto na data de corte */
  function renderProjetos() {
    var sec = document.getElementById("sec-projetos");
    if (!sec) return;
    sec.hidden = projetoId != null || !ind || !ind.porProjeto;
    if (sec.hidden) return;
    if (!tProj) {
      tProj = GI.tabela.criar("tabela-projetos", {
        porPagina: 0, legenda: "Desempenho de custo por projeto",
        colunas: [
          U.colunaProjeto("projetoId", { html: function (x) { return '<b data-sem-traducao>' + U.esc(x.codigo) + '</b><span class="linha-sub" data-sem-traducao>' + U.esc(x.nome) + "</span>"; } }),
          { id: "bac", titulo: "BAC", tipo: "moeda" },
          { id: "ev", titulo: "EV", tipo: "moeda", valor: function (x) { return x.atual ? x.atual.ev : null; } },
          { id: "ac", titulo: "AC", tipo: "moeda", valor: function (x) { return x.atual ? x.atual.ac : null; } },
          { id: "cpi", titulo: "CPI", tipo: "indice", valor: function (x) { return x.atual ? x.atual.cpi : null; },
            html: function (x) { var v = x.atual && x.atual.cpi; return v == null ? "" : '<span class="' + (v < 1 ? "valor--sobrecusto" : "valor--positivo") + '">' + F.indice(v) + "</span>"; } },
          { id: "spi", titulo: "SPI", tipo: "indice", valor: function (x) { return x.atual ? x.atual.spi : null; } },
          { id: "projecaoTermino", titulo: "Projeção no término", tipo: "moeda" },
          { id: "vac", titulo: "VAC", tipo: "moeda", html: function (x) { return '<span class="' + (x.vac < 0 ? "valor--sobrecusto" : "") + '">' + U.esc(F.moeda(x.vac)) + "</span>"; } },
          { id: "contingenciaPct", titulo: "Contingência consumida", tipo: "pct" }
        ],
        acoes: function (x) { return '<a class="btn btn--ghost btn--sm" href="' + U.tela("financeiro", "kpis", { projeto: x.projetoId }) + '">' + U.icone("chevronRight") + "Abrir</a>"; }
      });
    }
    tProj.atualizar(ind.porProjeto);
  }

  function carregar() {
    return Promise.all([GI.api.financeiro.indicadores(projetoId), GI.api.financeiro.historicoIndices(projetoId), GI.api.financeiro.contingencia(projetoId)]).then(function (r) {
      ind = r[0]; hist = r[1]; limiteCont = r[2] ? r[2].limiteConsumoPct : null; render();
    });
  }

  GI.exportar.registrar(function () {
    var p = U.projeto(projetoId);
    return {
      titulo: projetoId == null ? "KPIs de custo da carteira" : "KPIs de custo", subtitulo: p ? p.codigo + " " + p.nome : "Portfólio de projetos", arquivo: "kpis-custo-" + (p ? p.codigo : "portfolio"),
      blocos: (tProj && projetoId == null ? [{ tipo: "tabela", titulo: "Desempenho de custo por projeto", dados: tProj.exportacao() }] : []).concat([
        { tipo: "kpis", titulo: "Indicadores", itens: Array.prototype.map.call(document.querySelectorAll("#kpis .kpi"), function (k) {
            return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" };
          }) },
        { tipo: "grafico", titulo: "CPI e SPI por mês", canvas: document.getElementById("g-indices") },
        { tipo: "grafico", titulo: "Valor agregado acumulado", canvas: document.getElementById("g-va") },
        { tipo: "tabela", titulo: "Valor agregado na data de corte", dados: tResumo.exportacao() },
        { tipo: "tabela", titulo: "Período a período", dados: tabela.exportacao() }
      ])
    };
  });

  GI.util.pronto().then(function () {
    projetoId = GI.fin.projeto(function (id) { projetoId = id; carregar(); });
    tResumo = GI.tabela.criar("resumo", {
      porPagina: 0, legenda: "Valor agregado na data de corte",
      colunas: [
        { id: "sigla", titulo: "Indicador", ordenavel: false, html: function (x) { return "<b>" + U.esc(x.sigla) + "</b>"; } },
        { id: "nome", titulo: "Descrição", ordenavel: false },
        { id: "valor", titulo: "Valor", tipo: "moeda", ordenavel: false, valor: function (x) { return x.valor; },
          html: function (x) { return x.indice != null ? F.indice(x.indice) : '<span class="' + (x.valor < 0 ? (x.sigla === "SV" ? "valor--negativo" : "valor--sobrecusto") : "") + '">' + U.esc(F.moeda(x.valor)) + "</span>"; },
          exportar: function (x) { return x.indice != null ? x.indice : x.valor; } },
        { id: "leitura", titulo: "Leitura", ordenavel: false }
      ]
    });
    tabela = GI.tabela.criar("tabela", {
      porPagina: 0, legenda: "Valor agregado período a período",
      colunas: [
        { id: "mes", titulo: "Mês", ordenavel: false, html: function (h) { return U.esc(U.mesCurto(h.mes)); }, exportar: function (h) { return U.mesCurto(h.mes); } },
        { id: "pv", titulo: "PV", tipo: "moeda", ordenavel: false },
        { id: "ev", titulo: "EV", tipo: "moeda", ordenavel: false },
        { id: "ac", titulo: "AC", tipo: "moeda", ordenavel: false },
        { id: "cv", titulo: "CV", tipo: "moeda", ordenavel: false, html: function (h) { return '<span class="' + (h.cv < 0 ? "valor--sobrecusto" : "") + '">' + U.esc(F.moeda(h.cv)) + "</span>"; } },
        { id: "sv", titulo: "SV", tipo: "moeda", ordenavel: false, html: function (h) { return '<span class="' + (h.sv < 0 ? "valor--negativo" : "") + '">' + U.esc(F.moeda(h.sv)) + "</span>"; } },
        { id: "cpi", titulo: "CPI", tipo: "indice", ordenavel: false },
        { id: "spi", titulo: "SPI", tipo: "indice", ordenavel: false }
      ]
    });
    return carregar();
  });
})(window.GI = window.GI || {});
