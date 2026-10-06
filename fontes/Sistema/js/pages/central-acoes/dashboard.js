/* ==========================================================================
   Central de Ações > Dashboards e KPIs
   Indicadores do motor de status único por origem, responsável e mês.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt;
  var ORIGENS = ["Ata", "Punch list", "Contrato", "Suprimentos", "Risco", "RNC", "HSE", "Mudança", "Lição", "Produtividade"];
  var todas = [];
  var tabela;
  var filtro = { origem: "" };
  var projetoId = GI.api.projetoAtualId();   /* null = Portfólio */

  function dados() {
    return todas.filter(function (a) {
      return a.ehAcao && (!filtro.origem || a.origem === filtro.origem);
    });
  }

  function render() {
    var l = dados();
    var n = function (st, lista) { return (lista || l).filter(function (a) { return a.status === st; }).length; };
    var concluidas = l.filter(function (a) { return a.status === "concluida"; });
    var noPrazo = concluidas.filter(function (a) { return a.conclusao <= a.prevista; }).length;
    var abertas = n("andamento") + n("atrasada");
    var ref = GI.api.referencia();
    var previstas = l.filter(function (a) { return a.prevista && a.prevista <= ref; }).length;   /* prazo original até a data de referência */
    var universo = todas.filter(function (a) { return a.ehAcao; }).length;
    document.getElementById("kpis").innerHTML = [
      U.kpi({ rotulo: "Total de ações", valor: F.num(l.length), icone: "list", cor: "primary", esperado: { rotulo: "Referência", valor: F.num(universo) }, rodape: F.num(abertas) + " em andamento" }),
      U.kpi({ rotulo: "Em dia", valor: F.num(n("andamento")), icone: "clock", cor: "info", esperado: { rotulo: "Esperado", valor: F.num(abertas) }, href: U.tela("central-acoes", "acoes", { status: "andamento" }) }),
      U.kpi({ rotulo: "Atrasadas", valor: F.num(n("atrasada")), icone: "alertTriangle", cor: "danger", esperado: { rotulo: "Meta", valor: "0" },
        rodape: abertas ? F.pct(n("atrasada") / abertas * 100, 0) + " das abertas" : "", href: U.tela("central-acoes", "acoes", { status: "atrasada" }) }),
      U.kpi({ rotulo: "Concluídas", valor: F.num(concluidas.length), icone: "checkCircle", cor: "success", esperado: { rotulo: "Previsto", valor: F.num(previstas) }, href: U.tela("central-acoes", "acoes", { status: "concluida" }) }),
      U.kpi({ rotulo: "Concluídas no prazo original", valor: concluidas.length ? F.pct(noPrazo / concluidas.length * 100, 0) : "·", icone: "target",
        cor: "highlight", esperado: { rotulo: "Esperado", valor: F.pct(100, 0) }, rodape: F.num(noPrazo) + " de " + F.num(concluidas.length) + " sem replanejar" })
    ].join("");

    /* Status por origem (barras horizontais empilhadas) */
    var origens = ORIGENS.filter(function (o) { return l.some(function (a) { return a.origem === o; }); });
    GI.charts.bar("g-origem", {
      labels: origens, horizontal: true, stacked: true, ariaLabel: "Ações por origem e status",
      series: [
        { label: "Em dia", color: "chart-4", data: origens.map(function (o) { return n("andamento", l.filter(function (a) { return a.origem === o; })); }) },
        { label: "Atrasadas", color: "chart-2", data: origens.map(function (o) { return n("atrasada", l.filter(function (a) { return a.origem === o; })); }) },
        { label: "Concluídas", color: "chart-1", data: origens.map(function (o) { return n("concluida", l.filter(function (a) { return a.origem === o; })); }) }
      ]
    });

    /* Portfólio: status por projeto */
    var secP = document.getElementById("sec-projeto");
    if (secP) {
      secP.hidden = projetoId != null;
      if (projetoId == null) {
        var projs = U.listaProjetos();
        GI.charts.bar("g-projeto", {
          labels: projs.map(function (p) { return p.codigo; }), horizontal: true, stacked: true, ariaLabel: "Ações por projeto e status",
          series: [
            { label: "Em dia", color: "chart-4", data: projs.map(function (p) { return n("andamento", l.filter(function (a) { return a.projetoId === p.id; })); }) },
            { label: "Atrasadas", color: "chart-2", data: projs.map(function (p) { return n("atrasada", l.filter(function (a) { return a.projetoId === p.id; })); }) },
            { label: "Concluídas", color: "chart-1", data: projs.map(function (p) { return n("concluida", l.filter(function (a) { return a.projetoId === p.id; })); }) }
          ]
        });
      }
    }

    /* Abertas por responsável (10 com mais ações abertas) */
    var porResp = {};
    l.forEach(function (a) {
      var r = porResp[a.responsavelId] = porResp[a.responsavelId] || { id: a.responsavelId, andamento: 0, atrasada: 0, concluida: 0, maiorAtraso: 0, total: 0 };
      r[a.status]++; r.total++;
      if (a.status === "atrasada") r.maiorAtraso = Math.max(r.maiorAtraso, a.diasAtraso);
    });
    var resp = Object.keys(porResp).map(function (k) { return porResp[k]; });
    var top = resp.filter(function (r) { return r.andamento + r.atrasada > 0; })
      .sort(function (a, b) { return (b.andamento + b.atrasada) - (a.andamento + a.atrasada) || b.atrasada - a.atrasada; }).slice(0, 10);
    GI.charts.bar("g-resp", {
      labels: top.map(function (r) { return U.pessoa(r.id); }), horizontal: true, stacked: true, ariaLabel: "Ações abertas por responsável",
      series: [
        { label: "Em dia", color: "chart-4", data: top.map(function (r) { return r.andamento; }) },
        { label: "Atrasadas", color: "chart-2", data: top.map(function (r) { return r.atrasada; }) }
      ]
    });

    /* Previstas x concluídas por mês */
    var meses = {};
    l.forEach(function (a) {
      var mp = String(a.replanejada || a.prevista || "").slice(0, 7);
      if (mp) (meses[mp] = meses[mp] || { previstas: 0, concluidas: 0 }).previstas++;
      if (a.conclusao) { var mc = a.conclusao.slice(0, 7); (meses[mc] = meses[mc] || { previstas: 0, concluidas: 0 }).concluidas++; }
    });
    var chaves = Object.keys(meses).sort();
    GI.charts.bar("g-mes", {
      labels: chaves.map(U.mesCurto), ariaLabel: "Ações previstas e concluídas por mês",
      series: [
        { label: "Previstas", color: "chart-4", data: chaves.map(function (k) { return meses[k].previstas; }) },
        { label: "Concluídas", color: "chart-1", data: chaves.map(function (k) { return meses[k].concluidas; }) }
      ]
    });

    tabela.atualizar(resp);
  }

  function preencherFiltros() {
    document.getElementById("f-origem").innerHTML = U.opcoes(ORIGENS, filtro.origem, "Todas as origens");
    document.getElementById("f-origem").addEventListener("change", function (ev) { filtro.origem = ev.target.value; render(); });
  }

  GI.exportar.registrar(function () {
    var p = U.projeto(projetoId);
    var blocoP = projetoId == null ? [{ tipo: "grafico", titulo: "Status por projeto", canvas: document.getElementById("g-projeto") }] : [];
    return {
      titulo: "Central de Ações: dashboards e KPIs", arquivo: "central-dashboard",
      subtitulo: (p ? p.codigo : "Portfólio de projetos") + (filtro.origem ? " · origem " + filtro.origem : ""),
      blocos: [
        { tipo: "kpis", titulo: "Indicadores", itens: Array.prototype.map.call(document.querySelectorAll("#kpis .kpi"), function (k) {
            return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" };
          }) },
        { tipo: "grafico", titulo: "Status por origem", canvas: document.getElementById("g-origem") },
        { tipo: "grafico", titulo: "Ações abertas por responsável", canvas: document.getElementById("g-resp") },
      ].concat(blocoP).concat([
        { tipo: "grafico", titulo: "Previstas x concluídas por mês", canvas: document.getElementById("g-mes") },
        { tipo: "tabela", titulo: "Desempenho por responsável", dados: tabela.exportacao() }
      ])
    };
  });

  GI.util.pronto().then(function () {
    preencherFiltros();
    tabela = GI.tabela.criar("tabela", {
      porPagina: 0, ordem: { coluna: "atrasada", direcao: "desc" }, legenda: "Desempenho por responsável",
      colunas: [
        { id: "nome", titulo: "Responsável", valor: function (r) { return U.pessoa(r.id); },
          html: function (r) { return '<a href="' + U.tela("central-acoes", "acoes", { responsavel: r.id }) + '">' + U.esc(U.pessoa(r.id)) + "</a>"; } },
        { id: "abertas", titulo: "Abertas", tipo: "num", valor: function (r) { return r.andamento + r.atrasada; } },
        { id: "atrasada", titulo: "Atrasadas", tipo: "num" },
        { id: "pctAtraso", titulo: "% atrasadas", tipo: "pct", casas: 0, valor: function (r) { var ab = r.andamento + r.atrasada; return ab ? r.atrasada / ab * 100 : null; } },
        { id: "concluida", titulo: "Concluídas", tipo: "num" },
        { id: "maiorAtraso", titulo: "Maior atraso (dias)", tipo: "num", valor: function (r) { return r.maiorAtraso || null; } }
      ],
      classeLinha: function (r) { return r.atrasada ? "is-alert" : ""; }
    });
    return GI.api.central.acoes(projetoId == null ? null : { projetoId: projetoId });
  }).then(function (l) { todas = l; render(); });
})(window.GI = window.GI || {});
