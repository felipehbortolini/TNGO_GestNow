/* ==========================================================================
   Planejamento > KPIs
   SPI, previsto x real e desvio por período e por área; atualização do
   avanço por área (média ponderada fecha com a Curva S). No Portfólio, as
   linhas são os projetos (peso na carteira) e o SPI é o ponderado da carteira.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt;
  var projetoId = GI.api.projetoAtualId();
  var PF = projetoId == null;
  var curva = null, ind = null, areas = [], tabela, faixasPP = null;

  function ponderado(campo) {
    var peso = areas.reduce(function (s, a) { return s + a.peso; }, 0);
    return peso ? Math.round(areas.reduce(function (s, a) { return s + a.peso * a[campo]; }, 0) / peso * 10) / 10 : null;
  }

  function render() {
    if (!curva) {
      document.getElementById("kpis").innerHTML = '<div class="card">' + U.vazio(PF ? "Sem Curva S cadastrada nos projetos da carteira." : "Sem Curva S cadastrada para este projeto.", "curve") + "</div>";
      tabela.atualizar([]);
      return;
    }
    var iCorte = curva.meses.indexOf(curva.corte);
    var spiMes = curva.meses.slice(0, iCorte + 1).map(function (m, i) { return curva.real[i] != null && curva.baseline[i] ? Math.round(curva.real[i] / curva.baseline[i] * 100) / 100 : null; });
    var piorArea = areas.filter(function (a) { return a.previsto > 0; }).sort(function (a, b) { return (a.real - a.previsto) - (b.real - b.previsto); })[0];
    document.getElementById("kpis").innerHTML = [
      U.kpi({ rotulo: PF ? "SPI ponderado da carteira" : "SPI do projeto", valor: F.indice(ind.spi), icone: "gauge", cor: ind.spi >= 1 ? "success" : ind.spi >= 0.95 ? "warning" : "danger",
        esperado: { rotulo: "Meta", valor: "≥ " + F.indice(1) }, rodape: ind.anterior ? '<span class="kpi__delta kpi__delta--' + (ind.spi >= ind.anterior.spi ? "up" : "down") + '">' + U.icone(ind.spi >= ind.anterior.spi ? "arrowUp" : "arrowDown") +
          F.indice(Math.abs(ind.spi - ind.anterior.spi)) + "</span> vs. mês anterior" : "" }),
      U.kpi({ rotulo: "Previsto x real", valor: F.num(ind.real, 1), unidade: "%", icone: "curve", cor: "primary", esperado: { rotulo: "Previsto", valor: F.pct(ind.previsto, 1) }, rodape: "acumulado em " + U.mesCurto(ind.corte) }),
      U.kpi({ rotulo: "Desvio acumulado", valor: F.num(ind.desvioPP, 1), unidade: "p.p.", icone: "alertTriangle", cor: ind.desvioPP < 0 ? "danger" : "success", esperado: { rotulo: "Meta", valor: "≥ " + F.num(0) } }),
      U.kpi({ rotulo: PF ? "Maior desvio por projeto" : "Maior desvio por área", valor: piorArea ? F.num(piorArea.real - piorArea.previsto, 1) : "·", unidade: piorArea ? "p.p." : "", icone: "flag", cor: "warning",
        esperado: { rotulo: "Limite", valor: faixasPP ? "≥ −" + F.num(faixasPP[0]) : "≥ " + F.num(0) },
        rodape: piorArea ? U.esc(PF ? piorArea.codigo : piorArea.area) + ": real " + F.pct(piorArea.real, 0) + " x previsto " + F.pct(piorArea.previsto, 0) : "" })
    ].join("");

    GI.charts.line("g-spi", {
      labels: curva.meses.slice(0, iCorte + 1).map(U.mesCurto), min: 0.8, max: 1.1, casas: 2, ariaLabel: "SPI mensal",
      series: [{ label: "SPI", data: spiMes, color: "chart-real" }, { label: "Meta (1,00)", data: spiMes.map(function () { return 1; }), color: "chart-baseline", dashed: true, points: false }]
    });
    GI.charts.bar("g-areas", {
      labels: areas.map(function (a) { return PF ? a.codigo : a.area; }), percent: true, max: 100, ariaLabel: PF ? "Avanço previsto e real por projeto" : "Avanço previsto e real por área",
      series: [
        { label: "Previsto", color: "chart-baseline", data: areas.map(function (a) { return a.previsto; }) },
        { label: "Real", color: "chart-real", data: areas.map(function (a) { return a.real; }) }
      ]
    });
    tabela.atualizar(areas);
  }

  function carregar() {
    return Promise.all([GI.api.planejamento.curvaFisica(projetoId), GI.api.planejamento.avancoAreas(projetoId), GI.api.parametros()]).then(function (r) {
      curva = r[0].curva; ind = r[0].indices; areas = r[1]; faixasPP = r[2].eap ? r[2].eap.faixasDesvioPP : null; render();
    });
  }

  function atualizarAreas() {
    if (PF) { U.noProjeto("areas", "Atualizar avanço por área"); return; }
    if (!areas.length) { GI.ui.toast("Este projeto não tem áreas cadastradas.", "info"); return; }
    GI.form.abrir({
      titulo: "Atualizar avanço por área", subtitulo: "Real acumulado (%) na data de corte", tamanho: "lg",
      intro: '<p class="text-small text-muted">A média ponderada pelos pesos deve bater com o real acumulado da Curva S (' + F.pct(ind ? ind.real : null) + ").</p>",
      campos: areas.map(function (a) { return { id: "a" + a.id, rotulo: a.area + " (peso " + a.peso + "%)", tipo: "numero", obrigatorio: true, min: 0, maxNumero: 100, passo: 0.1, valor: a.real }; }),
      validar: function (v) {
        var peso = areas.reduce(function (s, a) { return s + a.peso; }, 0);
        var media = Math.round(areas.reduce(function (s, a) { return s + a.peso * v["a" + a.id]; }, 0) / peso * 10) / 10;
        return ind && Math.abs(media - ind.real) > 0.5 ? [{ msg: "A média ponderada (" + F.pct(media) + ") diverge do real da Curva S (" + F.pct(ind.real) + "). Ajuste as áreas ou registre o avanço na Curva S." }] : [];
      },
      aoSalvar: function (v) {
        return areas.reduce(function (p, a) {
          return p.then(function () { return GI.api.obter("avancoAreas", a.id); }).then(function (o) { o.real = v["a" + a.id]; return GI.api.salvar("avancoAreas", o); });
        }, Promise.resolve()).then(function () { GI.ui.toast("Avanço por área atualizado.", "success"); return carregar(); });
      }
    });
  }

  GI.exportar.registrar(function () {
    var p = U.projeto(projetoId);
    return {
      titulo: "KPIs de prazo", subtitulo: p ? p.codigo + " " + p.nome : "Portfólio de projetos", arquivo: "kpis-prazo",
      blocos: [
        { tipo: "kpis", titulo: "Indicadores", itens: Array.prototype.map.call(document.querySelectorAll("#kpis .kpi"), function (k) {
            return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" };
          }) },
        { tipo: "grafico", titulo: "SPI por mês", canvas: document.getElementById("g-spi") },
        { tipo: "grafico", titulo: PF ? "Previsto x real por projeto" : "Previsto x real por área", canvas: document.getElementById("g-areas") },
        { tipo: "tabela", titulo: PF ? "Avanço por projeto" : "Avanço por área", dados: tabela.exportacao() }
      ]
    };
  });

  GI.util.pronto().then(function () {
    document.getElementById("btn-areas").addEventListener("click", atualizarAreas);
    if (PF) {
      document.getElementById("t-areas").textContent = "Avanço por projeto";
      document.getElementById("t-areas").nextElementSibling.textContent = "Pesos da ponderação da carteira (somam 100%); a média ponderada fecha com a Curva S da carteira";
      document.getElementById("t-desvio").textContent = "Previsto x real por projeto";
    }
    tabela = GI.tabela.criar("tabela", {
      porPagina: 0, legenda: PF ? "Avanço por projeto" : "Avanço por área",
      colunas: [
        { id: "area", titulo: PF ? "Projeto" : "Área", html: function (a) { return PF ? '<b data-sem-traducao>' + U.esc(a.codigo) + '</b><span class="linha-sub" data-sem-traducao>' + U.esc(a.nome) + "</span>" : "<b>" + U.esc(a.area) + "</b>"; } },
        { id: "peso", titulo: PF ? "Peso na carteira" : "Peso", tipo: "pct", casas: PF ? 1 : 0 },
        { id: "previsto", titulo: "Previsto", tipo: "pct" },
        { id: "real", titulo: "Real", tipo: "pct" },
        { id: "desvio", titulo: "Desvio (p.p.)", tipo: "num", casas: 1, valor: function (a) { return Math.round((a.real - a.previsto) * 10) / 10; },
          html: function (a) { var d = Math.round((a.real - a.previsto) * 10) / 10; return '<span class="' + (d < 0 ? "valor--negativo" : "") + '">' + (d > 0 ? "+" : "") + F.num(d, 1) + "</span>"; } },
        { id: "spi", titulo: PF ? "SPI do projeto" : "SPI da área", tipo: "indice", valor: function (a) { return a.previsto ? Math.round(a.real / a.previsto * 100) / 100 : null; } },
        { id: "contrib", titulo: "Contribuição (p.p.)", tipo: "num", casas: 1, valor: function (a) { return Math.round(a.peso * a.real / 10) / 10; } }
      ],
      rodape: function () {
        return { area: PF ? "<b>Carteira (ponderado)</b>" : "<b>Projeto (ponderado)</b>", peso: F.pct(areas.reduce(function (s, a) { return s + a.peso; }, 0), 0),
          previsto: F.pct(ponderado("previsto")), real: F.pct(ponderado("real")),
          desvio: F.num(Math.round((ponderado("real") - ponderado("previsto")) * 10) / 10, 1) };
      }
    });
    return carregar().then(function () { if (U.acaoPendente() === "areas") atualizarAreas(); });
  });
})(window.GI = window.GI || {});
