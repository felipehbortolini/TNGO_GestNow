/* ==========================================================================
   Gestão Financeira > Curva S financeira
   CAPEX planejado (linha de base de custo), comprometido e realizado
   acumulados por mês, com a projeção a partir do corte; tabela período a período.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt;
  var projetoId, curva = null, total = null, tabela;

  function linhas(c) {
    return c.meses.map(function (m, i) {
      var ant = function (s) { return i > 0 && s[i - 1] != null ? s[i - 1] : 0; };
      return {
        mes: m, corte: m === c.corte,
        planejadoMes: c.planejado[i] == null ? null : c.planejado[i] - ant(c.planejado), planejado: c.planejado[i],
        comprometido: c.comprometido[i],
        realizadoMes: c.realizado[i] == null ? null : c.realizado[i] - ant(c.realizado), realizado: c.realizado[i],
        projecao: c.projecao[i],
        desvio: c.realizado[i] == null ? null : c.realizado[i] - c.planejado[i]
      };
    });
  }

  function render() {
    var el = document.getElementById("kpis");
    if (!curva) {
      el.innerHTML = "";
      document.getElementById("sub-curva").textContent = projetoId == null ? "Nenhum projeto da carteira tem curva financeira cadastrada." : "Este projeto ainda não tem curva financeira cadastrada.";
      GI.charts.sCurveFinanceira("g-curva", { labels: [], planejado: [], comprometido: [], realizado: [] });
      tabela.atualizar([]);
      return;
    }
    var k = curva.meses.indexOf(curva.corte);
    var plan = curva.planejado[k], real = curva.realizado[k], comp = curva.comprometido[k];
    var fim = curva.projecao[curva.projecao.length - 1];
    var dif = real - plan;
    el.innerHTML = [
      U.kpi({ rotulo: "Planejado acumulado", moeda: plan, icone: "curve", cor: "info", rodape: "linha de base de custo em " + U.mesCurto(curva.corte),
        esperado: { rotulo: "Orçado", valor: F.moedaCompacta(total.atual) } }),
      U.kpi({ rotulo: "Realizado acumulado", moeda: real, icone: "coins", cor: "primary",
        esperado: { rotulo: "Previsto", valor: F.moedaCompacta(plan) },
        rodape: (dif > 0 ? "+" : "") + F.moedaCompacta(dif) + " em relação ao planejado" }),
      U.kpi({ rotulo: "Comprometido acumulado", moeda: comp, icone: "fileContract", cor: "info",
        esperado: { rotulo: "Orçado", valor: F.moedaCompacta(total.atual) },
        rodape: F.pct(comp / total.atual * 100) + " do orçamento" }),
      U.kpi({ rotulo: "Projeção no término", moeda: fim, icone: "target", cor: fim > total.atual ? "warning" : "success",
        esperado: { rotulo: "Orçado", valor: F.moedaCompacta(total.atual) },
        rodape: GI.fin.calor(total) })
    ].join("");
    document.getElementById("sub-curva").textContent = "Corte em " + U.mesCurto(curva.corte) + " · acumulado por mês" + (projetoId == null ? " · carteira: soma dos valores em R$ dos projetos (sem ponderação)" : "");
    GI.charts.sCurveFinanceira("g-curva", {
      labels: curva.meses.map(U.mesCurto), planejado: curva.planejado, comprometido: curva.comprometido, realizado: curva.realizado, projecao: curva.projecao,
      ariaLabel: (projetoId == null ? "Curva S financeira da carteira" : "Curva S financeira") + ": planejado, comprometido, realizado e projeção acumulados por mês"
    });
    tabela.atualizar(linhas(curva));
  }

  function carregar() {
    return Promise.all([GI.api.financeiro.curvaFinanceira(projetoId), GI.api.financeiro.mapaControle(projetoId)]).then(function (r) {
      curva = r[0]; total = r[1].total; render();
    });
  }

  GI.exportar.registrar(function () {
    var p = U.projeto(projetoId);
    return {
      titulo: projetoId == null ? "Curva S financeira da carteira" : "Curva S financeira", subtitulo: p ? p.codigo + " " + p.nome : "Portfólio de projetos", arquivo: "curva-s-financeira-" + (p ? p.codigo : "portfolio"), orientacao: "l",
      blocos: [
        { tipo: "kpis", titulo: "Indicadores", itens: Array.prototype.map.call(document.querySelectorAll("#kpis .kpi"), function (k) {
            return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" };
          }) },
        { tipo: "grafico", titulo: "Curva S financeira", canvas: document.getElementById("g-curva") },
        { tipo: "tabela", titulo: "Período a período", dados: tabela.exportacao() }
      ]
    };
  });

  function colMil(id, titulo, extra) {
    return Object.assign({ id: id, titulo: titulo, tipo: "moeda", ordenavel: false, html: function (l) { return l[id] == null ? "" : U.esc(GI.fin.mil(l[id])); } }, extra || {});
  }

  GI.util.pronto().then(function () {
    projetoId = GI.fin.projeto(function (id) { projetoId = id; carregar(); });
    tabela = GI.tabela.criar("tabela", {
      porPagina: 0, legenda: "Curva S financeira período a período",
      colunas: [
        { id: "mes", titulo: "Mês", ordenavel: false, html: function (l) { return U.esc(U.mesCurto(l.mes)) + (l.corte ? " " + U.badge("corte", "primary") : ""); },
          exportar: function (l) { return U.mesCurto(l.mes); } },
        colMil("planejadoMes", "Planejado no mês"),
        colMil("planejado", "Planejado acumulado"),
        colMil("comprometido", "Comprometido acumulado"),
        colMil("realizadoMes", "Realizado no mês"),
        colMil("realizado", "Realizado acumulado", { html: function (l) { return l.realizado == null ? "" : "<b>" + U.esc(GI.fin.mil(l.realizado)) + "</b>"; } }),
        colMil("projecao", "Projeção acumulada"),
        colMil("desvio", "Realizado menos planejado", { html: function (l) { return l.desvio == null ? "" : (l.desvio > 0 ? "+" : "") + U.esc(GI.fin.mil(l.desvio)); } })
      ],
      classeLinha: function (l) { return l.corte ? "is-selected" : ""; }
    });
    return carregar();
  });
})(window.GI = window.GI || {});
