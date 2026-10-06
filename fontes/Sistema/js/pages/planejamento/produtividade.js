/* ==========================================================================
   Planejamento > Produtividade (02)
   Abas:
   * Quantidades: plano da linha de base (LB) por empresa (cabo por tipo, concreto,
     aço, tubulação, painéis) distribuído por semana; apontamento semanal do
     realizado e das HH apropriadas; aprovação e revisão da LB (só com SM do 08).
   * Horas efetivas: registros da fiscalização (capacidade produtiva por turno,
     amostragem do trabalho e paralisações de efetivo e de máquinas).
   * KPIs de performance: geral e por empresa, na janela de N semanas até a
     semana de corte; plano de recuperação vira ação na Central (origem Produtividade).
   Cálculos na api (GI.api.planejamento.produtividade); a tela só exibe.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt, R = GI.regras, API = GI.api.planejamento.produtividade;
  var projetoId = GI.api.projetoAtualId();
  var PAR = API.parametros();
  var ATUAL = API.semanaAtual();
  var ABAS = { qtd: "p-qtd", horas: "p-horas", kpis: "p-kpis" };
  var estado = {
    aba: ABAS[U.param("aba")] ? U.param("aba") : "qtd", empresaId: U.param("empresa") || "", corte: U.param("corte") || ATUAL, grupo: "",
    visao: "cp", area: "", encarregado: "", periodo: "janela"
  };
  var qtd = null, horas = null, kpis = null, empresasComDados = [];
  /* Aba inicial pela URL (?aba=kpis), marcada antes da inicialização das abas */
  Object.keys(ABAS).forEach(function (k) {
    var t = document.getElementById("aba-" + k), painel = document.getElementById(ABAS[k]);
    if (t) t.setAttribute("aria-selected", String(k === estado.aba));
    if (painel) painel.hidden = k !== estado.aba;
  });
  var tb = {};
  var CORES = ["chart-1", "chart-2", "chart-3", "chart-4"];

  /* ---------------- Formatação ---------------- */
  var EN = !!(GI.i18n && GI.i18n.idioma === "en");
  function dataCurta(iso) { return new Date(String(iso).slice(0, 10) + "T12:00:00").toLocaleDateString(GI.i18n ? GI.i18n.locale : "pt-BR", { day: "2-digit", month: "2-digit" }); }
  /* Semana curta: S39 (W39 em inglês); outro ano leva o sufixo /27 */
  function semCurta(s) {
    if (!s) return "";
    var p = s.split("-S");
    return (EN ? "W" : "S") + p[1] + (p[0] !== ATUAL.slice(0, 4) ? "/" + p[0].slice(2) : "");
  }
  function fimSemana(s) { var d = new Date(R.inicioSemana(s) + "T12:00:00Z"); d.setUTCDate(d.getUTCDate() + 6); return d.toISOString().slice(0, 10); }
  function rotuloSemana(s) { return semCurta(s) + " · " + dataCurta(R.inicioSemana(s)) + " a " + dataCurta(fimSemana(s)); }
  function qt(v, casas) { return v == null ? "·" : F.num(v, casas || 0); }
  function qtu(v, casas, un) { return v == null ? "·" : F.num(v, casas || 0) + " " + un; }
  function horasDec(h) { return h == null ? "·" : F.num(h, 2); }
  function duracao(min) {
    if (min == null || isNaN(min)) return "·";
    var m = Math.round(Math.abs(min));
    return (min < 0 ? "-" : "") + ("0" + Math.floor(m / 60)).slice(-2) + ":" + ("0" + (m % 60)).slice(-2);
  }
  function pctTxt(v, casas) { return v == null ? "·" : F.pct(v, casas == null ? 1 : casas); }
  function indice(v) { return v == null ? "·" : F.num(v, 2); }
  function corFaixa(f) { return f === "success" ? "success" : f === "warning" ? "warning" : f === "danger" ? "danger" : "info"; }
  function selo(texto, faixa) { return faixa ? U.badge(texto, faixa, true) : U.esc(texto); }
  function faixaAder(v) { return R.faixaIndicador(v, PAR.aderenciaFaixas, true); }
  function faixaPf(v) { return R.faixaIndicador(v, PAR.pfFaixas, false); }
  function faixaTrab(v) { return v == null ? null : v >= PAR.metaTrabalhandoPct ? "success" : v >= PAR.metaTrabalhandoPct - 10 ? "warning" : "danger"; }
  function faixaUtil(v) { return v == null ? null : v >= PAR.metaUtilizacaoPct ? "success" : v >= PAR.metaUtilizacaoPct - 10 ? "warning" : "danger"; }
  /* CP de referência: jornada x meta de utilização (h/dia) */
  function metaCp() { return Math.round(PAR.jornadaDiariaHoras * PAR.metaUtilizacaoPct) / 100; }
  function spiFx() { return PAR.spiFaixas || [0.85, 0.95]; }
  function atrasoFx() { return PAR.atrasoInicioFaixasMin || [15, 30]; }
  function faixaSpi(v) { return v == null ? null : v >= spiFx()[1] ? "success" : v >= spiFx()[0] ? "warning" : "danger"; }
  function nomeEmpresa() { return estado.empresaId ? U.empresa(Number(estado.empresaId)) : ""; }
  function opcoesSemanas(de, ate, sel) {
    return R.listaSemanas(de, ate).map(function (s) { return { valor: s, texto: s + " · " + dataCurta(R.inicioSemana(s)) }; });
  }
  function contratadas() {
    return Object.keys(U.mapas.empresas).map(Number).filter(function (id) { return U.mapas.empresas[id].tipo === "Contratada"; })
      .map(function (id) { return { valor: id, texto: U.empresa(id) }; });
  }
  function listaMov(elId, itens, unidade, casas, vazio) {
    var max = itens.reduce(function (m, x) { return Math.max(m, x.total); }, 0) || 1;
    var tot = itens.reduce(function (s, x) { return s + x.total; }, 0) || 1;
    document.getElementById(elId).innerHTML = itens.length ? '<ul class="mov mov--largo">' + itens.slice(0, 12).map(function (x) {
      return '<li><div class="mov__row"><span class="mov__id">' + U.esc(x.chave) + "</span>" +
        '<span class="mov__trilho" aria-hidden="true"><span class="mov__barra" style="width:' + (x.total / max * 100).toFixed(1) + '%"></span></span>' +
        '<span class="mov__val">' + F.num(x.total, casas || 0) + (unidade ? " " + unidade : "") + " <small>" + F.pct(x.total / tot * 100, 0) + "</small></span></div></li>";
    }).join("") + "</ul>" : U.vazio(vazio || "Nenhum registro no período.", "pieChart");
  }

  /* ======================================================================
     Filtros globais
     ====================================================================== */
  function montarFiltrosGlobais() {
    document.getElementById("f-empresa").innerHTML = U.opcoes(empresasComDados.map(function (id) { return { valor: id, texto: U.empresa(id) }; }), estado.empresaId, "Todas as empresas");
    var semanas = (qtd ? qtd.semanasCorte : [ATUAL]).slice().reverse();
    document.getElementById("f-corte").innerHTML = U.opcoes(semanas.map(function (s) { return { valor: s, texto: "Corte " + rotuloSemana(s) + (s === ATUAL ? " (atual)" : "") }; }), estado.corte);
    document.getElementById("contexto").textContent = "Semana atual " + semCurta(ATUAL) + " · janela de " + PAR.semanasMedia + " semanas para médias e tendência";
  }

  /* ======================================================================
     Aba Quantidades
     ====================================================================== */
  function carregarQtd() {
    return API.quantidades(projetoId, { corte: estado.corte, empresaId: estado.empresaId || null, grupo: estado.grupo || null }).then(function (d) { qtd = d; renderQtd(); });
  }
  function renderQtd() {
    var ind = qtd.indicadores;
    document.getElementById("f-grupo").innerHTML = U.opcoes(API.GRUPOS.filter(function (g) { return g !== "Outros"; }), estado.grupo, "Todos os grupos");
    var alerta = document.getElementById("alerta-qtd");
    alerta.hidden = !qtd.emElaboracao;
    alerta.innerHTML = U.icone("alertTriangle") + '<div class="alert__body">' + U.esc(U.plural(qtd.emElaboracao, "item com linha de base em elaboração", "itens com linha de base em elaboração")) +
      ": não entram nos indicadores até a aprovação.</div>";
    document.getElementById("kpis-qtd").innerHTML = [
      U.kpi({ rotulo: "Avanço por quantidades", valor: ind.pctReal == null ? "·" : F.num(ind.pctReal, 1), unidade: ind.pctReal == null ? "" : "%", icone: "trendingUp",
        cor: corFaixa(faixaSpi(ind.spi)), esperado: { rotulo: "Previsto", valor: pctTxt(ind.pctPrev) }, rodape: "SPI " + indice(ind.spi) }),
      U.kpi({ rotulo: "Aderência da semana", valor: ind.aderenciaSem == null ? "·" : F.num(ind.aderenciaSem, 0), unidade: ind.aderenciaSem == null ? "" : "%", icone: "target",
        cor: corFaixa(faixaAder(ind.aderenciaSem)), esperado: { rotulo: "Meta", valor: "≥ " + F.pct(PAR.aderenciaFaixas[1], 0) }, rodape: "média de " + PAR.semanasMedia + " semanas: " + pctTxt(ind.aderenciaJan, 0) }),
      U.kpi({ rotulo: "Fator de produtividade", valor: indice(ind.pfJan), icone: "gauge", cor: corFaixa(faixaPf(ind.pfJan)), esperado: { rotulo: "Meta", valor: "≤ " + indice(PAR.pfFaixas[0]) },
        rodape: "últimas " + PAR.semanasMedia + " semanas · acumulado " + indice(ind.pf) }),
      U.kpi({ rotulo: "Apontamentos pendentes", valor: F.num(ind.pendentes), icone: "clock", cor: ind.pendentes ? "warning" : "success", esperado: { rotulo: "Esperado", valor: F.num(0) },
        rodape: "itens ativos sem apontamento em " + semCurta(qtd.corte) }),
      U.kpi({ rotulo: "Tendência de atraso", valor: F.num(ind.tendenciaAtraso), icone: "alertTriangle", cor: ind.tendenciaAtraso ? "danger" : "success", esperado: { rotulo: "Esperado", valor: F.num(0) },
        rodape: "itens com término previsto depois da LB" })
    ].join("");
    document.getElementById("grupos").innerHTML = qtd.grupos.length ? qtd.grupos.map(function (g) {
      return U.kpi({ rotulo: g.grupo + " (" + g.unidade + ")", valor: qt(g.realAcum, g.casas), unidade: g.unidade, icone: g.grupo === "Cabo elétrico" ? "swap" : g.grupo === "Painel elétrico" ? "columns" : g.grupo === "Concreto" ? "building" : g.grupo === "Tubulação" ? "listTree" : "package",
        cor: corFaixa(faixaSpi(g.pctPrev ? g.pctReal / g.pctPrev : null)), esperado: { rotulo: "Previsto", valor: qtu(g.prevAcum, g.casas, g.unidade) },
        rodape: "de " + qtu(g.total, g.casas, g.unidade) + " · real " + pctTxt(g.pctReal) + " x previsto " + pctTxt(g.pctPrev) +
          "<br>" + U.esc(semCurta(qtd.corte)) + ": previsto " + qt(g.prevSem, g.casas) + " · realizado " + qt(g.realSem, g.casas) });
    }).join("") : U.vazio("Nenhum item com linha de base aprovada no filtro.", "barChart");

    /* Gráficos: janela de 17 semanas até o corte e 8 à frente */
    var s = qtd.serie, iCorte = s.semanas.indexOf(qtd.corte);
    if (iCorte < 0) iCorte = s.semanas.filter(function (x) { return x <= qtd.corte; }).length - 1;
    var ini = Math.max(0, iCorte - 16), fim = Math.min(s.semanas.length, iCorte + 9);
    var unid = qtd.unidadeSerie;
    var realCortado = s.realizado.map(function (v, k) { return s.semanas[k] > qtd.corte ? null : v; });
    var acumCortado = s.realAcumPct.map(function (v, k) { return s.semanas[k] > qtd.corte ? null : v; });
    if (!s.semanas.length) {
      document.getElementById("sub-semanal").textContent = "Sem linha de base aprovada no filtro.";
      document.getElementById("sub-acum").textContent = "Sem linha de base aprovada no filtro.";
    } else document.getElementById("sub-semanal").textContent = (s.emHH ? "Horas ganhas (HH): quantidade x índice orçado, para somar unidades diferentes" : "Quantidade em " + unid) +
      " · " + semCurta(s.semanas[ini]) + " a " + semCurta(s.semanas[fim - 1]);
    GI.charts.bar("g-semanal", { labels: s.semanas.slice(ini, fim).map(semCurta), ariaLabel: "Produção semanal prevista e realizada",
      series: [{ label: "Previsto (LB)", color: "chart-baseline", data: s.previsto.slice(ini, fim) }, { label: "Realizado", color: "chart-real", data: realCortado.slice(ini, fim) }] });
    if (s.semanas.length) document.getElementById("sub-acum").textContent = "% acumulado " + (s.emHH ? "em horas ganhas" : "em " + unid) + " · LB x realizado";
    GI.charts.line("g-acum", { labels: s.semanas.map(semCurta), percent: true, max: 100, ariaLabel: "Avanço acumulado previsto e realizado",
      series: [{ label: "Previsto (LB)", color: "chart-baseline", dashed: true, points: false, data: s.prevAcumPct },
        { label: "Realizado", color: "chart-real", fill: true, points: false, data: acumCortado }] });

    document.getElementById("sub-itens").textContent = U.plural(qtd.itens.length, "item", "itens") + " · corte " + rotuloSemana(qtd.corte) + " · FP = fator de produtividade acumulado";
    tb.itens.atualizar(qtd.itens);
  }
  function criarTabelaItens() {
    tb.itens = GI.tabela.criar("tb-itens", {
      porPagina: 0, ordem: { coluna: "codigo", direcao: "asc" }, vazio: "Nenhum item no filtro.", legenda: "Plano x realizado por item",
      colunas: [
        { id: "codigo", titulo: "Item", fixa: true, html: function (i) { return '<div class="cell-title"><b>' + U.esc(i.codigo) + (i.situacao !== "Aprovada" ? " " + U.badge("LB em elaboração", "warning") : "") + "</b><small>" + U.esc(i.tipo) + "</small></div>"; },
          exportar: function (i) { return i.codigo + " " + i.tipo; } },
        { id: "empresa", titulo: "Empresa", valor: function (i) { return U.empresa(i.empresaId); } },
        { id: "grupo", titulo: "Grupo", oculta: true },
        { id: "realAcum", titulo: "Realizado / LB", tipo: "num", valor: function (i) { return i.calc.realAcum; },
          html: function (i) { return '<div class="cell-duo"><b>' + qtu(i.calc.realAcum, i.casas, i.unidade) + "</b><small>de " + qtu(i.total, i.casas, i.unidade) + "</small></div>"; },
          exportar: function (i) { return qtu(i.calc.realAcum, i.casas, i.unidade) + " de " + qtu(i.total, i.casas, i.unidade); } },
        { id: "prevAcum", titulo: "Previsto acum.", tipo: "num", oculta: true, valor: function (i) { return i.calc.prevAcum; }, html: function (i) { return qt(i.calc.prevAcum, i.casas); } },
        { id: "pct", titulo: "% real (prev.)", tipo: "pct", valor: function (i) { return i.calc.pctReal; },
          html: function (i) {
            var d = i.calc.desvioPp;
            return '<div class="cell-duo"><b>' + pctTxt(i.calc.pctReal) + "</b><small>" + pctTxt(i.calc.pctPrev) + (d ? ' · <span class="' + (d < 0 ? "valor--negativo" : "") + '">' + F.num(d, 1) + " p.p.</span>" : "") + "</small></div>";
          },
          exportar: function (i) { return pctTxt(i.calc.pctReal) + " (prev. " + pctTxt(i.calc.pctPrev) + "; " + F.num(i.calc.desvioPp || 0, 1) + " p.p.)"; } },
        { id: "semana", titulo: "Semana prev. / real.", ordenavel: false, valor: function (i) { return i.calc.realSem; },
          html: function (i) {
            if (!i.calc.aprovado) return "·";
            return qt(i.calc.prevSem, i.casas) + " / " + (i.calc.pendente ? U.badge("Pendente", "warning") : qt(i.calc.realSem, i.casas));
          }, exportar: function (i) { return qt(i.calc.prevSem, i.casas) + " / " + (i.calc.pendente ? "pendente" : qt(i.calc.realSem, i.casas)); } },
        { id: "aderencia", titulo: "Aderência", tipo: "pct", casas: 0, valor: function (i) { return i.calc.aderenciaSem; },
          html: function (i) { return i.calc.aderenciaSem == null ? "·" : selo(F.pct(i.calc.aderenciaSem, 0), faixaAder(i.calc.aderenciaSem)); } },
        { id: "pf", titulo: "FP", tipo: "num", casas: 2, valor: function (i) { return i.calc.pf; },
          html: function (i) { return i.calc.pf == null ? "·" : selo(indice(i.calc.pf), faixaPf(i.calc.pf)); } },
        { id: "tendencia", titulo: "Término LB / tendência", valor: function (i) { return i.calc.desvioSemanas; },
          html: function (i) {
            var t = i.calc.tendencia ? semCurta(i.calc.tendencia) : "·";
            var d = i.calc.desvioSemanas;
            return '<div class="cell-duo"><b>' + semCurta(i.fim) + " → " + t + "</b><small" + (d > 0 ? ' class="valor--negativo"' : "") + ">" +
              (d == null ? (i.calc.aprovado ? "sem realizado" : "LB não aprovada") : d > 0 ? "+" + U.plural(d, "semana") : d < 0 ? U.plural(-d, "semana") + " antes" : "no prazo") + "</small></div>";
          }, exportar: function (i) { return semCurta(i.fim) + " → " + (i.calc.tendencia ? semCurta(i.calc.tendencia) : "sem tendência") + (i.calc.desvioSemanas ? " (" + i.calc.desvioSemanas + " sem.)" : ""); } },
        { id: "situacao", titulo: "LB", oculta: true, valor: function (i) { return i.situacao + " rev " + i.revisao; },
          html: function (i) { return i.situacao === "Aprovada" ? U.badge("Aprovada rev " + i.revisao, "success") : U.badge("Em elaboração", "warning", true); } }
      ],
      classeLinha: function (i) { return i.calc.pendente ? "is-alert" : ""; },
      acoes: function (i) { return '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-item="' + i.id + '" aria-label="Ver semanas e linha de base de ' + U.esc(i.codigo) + '" title="Semanas e linha de base">' + U.icone("eye") + "</button>"; }
    });
  }

  /* ---- Ficha do item: semanas, revisões e fluxo da LB ---- */
  function abrirItem(id) {
    API.item(Number(id), estado.corte).then(function (it) {
      if (!it) return;
      var semanas = {}, dist = {}, apont = {};
      it.distribuicao.forEach(function (d) { semanas[d.semana] = true; dist[d.semana] = d.previsto; });
      it.apontamentos.forEach(function (a) { semanas[a.semana] = true; apont[a.semana] = a; });
      var pa = 0, ra = 0;
      var linhas = Object.keys(semanas).sort().map(function (s) {
        var a = apont[s], p = dist[s] || 0;
        pa += p; if (a) ra += a.realizado;
        var ader = p > 0 && a ? Math.min(a.realizado, p) / p * 100 : null;
        var pf = a && a.realizado > 0 ? a.hh / (a.realizado * it.indiceHH) : null;
        return '<tr' + (s === estado.corte ? ' class="is-selected"' : "") + '><th scope="row" class="nowrap">' + U.esc(rotuloSemana(s)) + '</th><td class="num">' + qt(p, it.casas) + '</td><td class="num">' +
          (a ? qt(a.realizado, it.casas) : s <= ATUAL && it.situacao === "Aprovada" && s >= it.inicio ? U.badge("Pendente", "warning") : "·") + '</td><td class="num">' + (a ? F.num(a.hh) : "·") + '</td><td class="num">' +
          (ader == null ? "·" : selo(F.pct(ader, 0), faixaAder(ader))) + '</td><td class="num">' + (pf == null ? "·" : selo(indice(pf), faixaPf(pf))) + '</td><td class="num">' +
          F.pct(pa / it.total * 100, 1) + '</td><td class="num">' + (s <= ATUAL && it.situacao === "Aprovada" ? F.pct(ra / it.total * 100, 1) : "·") + "</td></tr>";
      }).join("");
      var sit = it.situacao === "Aprovada" ? U.badge("LB aprovada · rev " + it.revisao, "success") : U.badge("Em elaboração", "warning", true);
      var perfil = (API.PERFIS.filter(function (p) { return p.id === it.perfil; })[0] || {}).nome || it.perfil;
      var revs = (it.revisoes || []).slice().reverse().map(function (r) {
        return "<li><b>Rev " + r.rev + "</b> · " + F.data(r.data) + " · " + U.esc(U.pessoa(r.porId)) + " · total " + qtu(r.total, it.casas, it.unidade) +
          (r.smRef ? " · " + '<a href="' + U.tela("governanca", "mudanca", { codigo: r.smRef }) + '">' + U.esc(r.smRef) + "</a>" : "") + "<br><span class=\"text-muted\">" + U.esc(r.justificativa || "") + "</span></li>";
      }).join("");
      var corpo = document.createElement("div");
      corpo.innerHTML =
        '<dl class="dl">' +
        "<dt>Empresa</dt><dd>" + U.esc(U.empresa(it.empresaId)) + "</dd>" +
        "<dt>Grupo e disciplina</dt><dd>" + U.esc(it.grupo + " · " + (it.disciplina || "sem disciplina")) + "</dd>" +
        "<dt>Total da LB</dt><dd>" + qtu(it.total, it.casas, it.unidade) + " · índice orçado " + F.num(it.indiceHH, 2) + " HH/" + U.esc(it.unidade) + "</dd>" +
        "<dt>Distribuição</dt><dd><span>" + U.esc(rotuloSemana(it.inicio)) + "</span> → <span>" + U.esc(rotuloSemana(it.fim)) + "</span><br><span>" + U.esc(perfil) + "</span></dd>" +
        "<dt>Situação</dt><dd>" + sit + (it.aprovadoPorId ? " · aprovada por " + U.esc(U.pessoa(it.aprovadoPorId)) + " em " + F.data(it.aprovadoEm) : "") + "</dd>" +
        (it.observacoes ? "<dt>Observações</dt><dd>" + U.esc(it.observacoes) + "</dd>" : "") +
        "<dt>No corte " + U.esc(semCurta(estado.corte)) + "</dt><dd>realizado " + qtu(it.calc.realAcum, it.casas, it.unidade) + " (" + pctTxt(it.calc.pctReal) + ") x previsto " + pctTxt(it.calc.pctPrev) +
          " · FP " + indice(it.calc.pf) + " · tendência " + (it.calc.tendencia ? U.esc(semCurta(it.calc.tendencia)) : "·") + "</dd>" +
        "</dl>" +
        '<div class="btn-group mt-4" data-fluxo-item></div>' +
        '<h3 class="section-title mt-6">Semanas</h3>' +
        '<div class="table-wrap table-wrap--tall"><table class="table table--compact"><caption class="sr-only">Distribuição semanal do item</caption><thead><tr><th scope="col">Semana</th><th scope="col" class="num">Previsto</th><th scope="col" class="num">Realizado</th>' +
        '<th scope="col" class="num">HH apropriadas</th><th scope="col" class="num">Aderência</th><th scope="col" class="num">FP</th><th scope="col" class="num">Prev. acum.</th><th scope="col" class="num">Real. acum.</th></tr></thead><tbody>' +
        linhas + "</tbody></table></div>" +
        (revs ? '<h3 class="section-title mt-6">Revisões da linha de base</h3><ul class="lista-revisoes">' + revs + "</ul>" : "");
      var m = GI.modal.create({ title: it.codigo + " · " + it.tipo, subtitle: U.empresa(it.empresaId) + " · " + it.unidade, size: "xl", body: corpo, buttons: [{ label: "Fechar", variant: "secondary" }] });
      var fluxo = [];
      if (it.situacao === "Em elaboração") {
        fluxo.push('<button type="button" class="btn btn--secondary" data-acao="editar">' + U.icone("edit") + "Editar distribuição</button>");
        if (API.pode("Gestor")) fluxo.push('<button type="button" class="btn btn--primary" data-acao="aprovar">' + U.icone("checkCircle") + "Aprovar LB</button>");
        if (!it.apontamentos.length) fluxo.push('<button type="button" class="btn btn--ghost" data-acao="excluir">' + U.icone("trash") + "Excluir</button>");
      } else {
        fluxo.push('<button type="button" class="btn btn--secondary" data-acao="revisar">' + U.icone("history") + "Revisar LB (com SM)</button>");
        fluxo.push('<button type="button" class="btn btn--ghost" data-acao="obs">' + U.icone("edit") + "Observações</button>");
      }
      var box = corpo.querySelector("[data-fluxo-item]");
      box.innerHTML = fluxo.join("");
      if (GI.icons) GI.icons.hydrate(box);
      box.addEventListener("click", function (ev) {
        var b = ev.target.closest("[data-acao]");
        if (!b) return;
        var acao = b.getAttribute("data-acao");
        if (acao === "editar") { m.close(); formItem(it); }
        else if (acao === "revisar") { m.close(); formRevisao(it); }
        else if (acao === "obs") { m.close(); formObservacoes(it); }
        else if (acao === "aprovar") {
          GI.modal.confirm({ title: "Aprovar linha de base", message: "A distribuição semanal de " + it.codigo + " fica congelada. Mudanças depois disso só por revisão com SM aprovada (08).", okText: "Aprovar" })
            .then(function (ok) {
              if (!ok) return;
              API.aprovarItem(it.id).then(function () { m.close(); GI.ui.toast("Linha de base de " + it.codigo + " aprovada.", "success"); recarregar(); })
                .catch(function (e) { GI.ui.toast((e.erros || [e]).join(" "), "warning"); });
            });
        } else if (acao === "excluir") {
          GI.modal.confirm({ title: "Excluir item", message: "Excluir " + it.codigo + " (em elaboração, sem apontamento)?", okText: "Excluir", danger: true }).then(function (ok) {
            if (ok) API.excluirItem(it.id).then(function () { m.close(); GI.ui.toast("Item excluído.", "success"); recarregar(); })
              .catch(function (e) { GI.ui.toast((e.erros || [e]).join(" "), "warning"); });
          });
        }
      });
    });
  }

  /* ---- Grade de distribuição semanal (editável) ---- */
  function gradeDistribuicao(semanas, valores, casas, unidade, congeladas) {
    return '<div class="grade-semanas">' + semanas.map(function (s, k) {
      return '<label class="grade-semanas__cel"><span>' + U.esc(semCurta(s)) + '</span><input class="input input--grade" type="number" min="0" step="' + (casas ? "0.1" : "1") +
        '" data-semana="' + s + '" value="' + (valores[k] == null ? 0 : valores[k]) + '" aria-label="Previsto ' + U.esc(s) + '"></label>';
    }).join("") + "</div>" +
      '<p class="text-small mt-2" data-soma-dist data-congeladas="' + (congeladas || 0) + '" data-casas="' + (casas || 0) + '" data-unidade="' + U.esc(unidade || "") + '"></p>';
  }
  function atualizarSoma(el, total) {
    var p = el.querySelector("[data-soma-dist]");
    if (!p) return;
    var casas = Number(p.getAttribute("data-casas")), cong = Number(p.getAttribute("data-congeladas")) || 0;
    var s = cong;
    el.querySelectorAll("input[data-semana]").forEach(function (i) { s += Number(i.value) || 0; });
    var ok = total != null && Math.abs(s - total) <= Math.pow(10, -casas) / 2;
    if (total == null) { p.innerHTML = "Informe a quantidade total da LB."; return; }
    p.innerHTML = "Soma das semanas" + (cong ? " (com " + F.num(cong, casas) + " congeladas)" : "") + ": <b>" + F.num(s, casas) + " " + U.esc(p.getAttribute("data-unidade")) + "</b> de " +
      (total == null ? "·" : F.num(total, casas)) + " " + (ok ? U.badge("Fecha com o total", "success") : U.badge("Diferença de " + F.num((total || 0) - s, casas), "warning"));
  }
  /* O primeiro aoMudar roda antes de GI.form.abrir devolver o modal: atualiza a soma no ciclo seguinte */
  function somaDepois(obterModal, total) {
    var md = obterModal();
    if (md) atualizarSoma(md.el, total);
    else setTimeout(function () { var x = obterModal(); if (x) atualizarSoma(x.el, total); }, 0);
  }
  function lerDistribuicao(el) {
    return Array.prototype.map.call(el.querySelectorAll("input[data-semana]"), function (i) { return i.value === "" ? null : Number(i.value); });
  }

  /* ---- Novo item / edição em elaboração ---- */
  function formItem(it) {
    var de = R.somarSemanas(ATUAL, -52), ate = R.somarSemanas(ATUAL, 78);
    var ops = opcoesSemanas(de, ate);
    var chave = "";
    var m = GI.form.abrir({
      titulo: it ? "Editar " + it.codigo : "Novo item da linha de base", subtitulo: "Quantidade total da LB distribuída por semana conforme o cronograma", tamanho: "xl", colunas: 3,
      campos: [
        { id: "empresaId", rotulo: "Empresa", tipo: "select", obrigatorio: true, opcoes: contratadas(), valor: it ? it.empresaId : estado.empresaId },
        { id: "grupo", rotulo: "Grupo", tipo: "select", obrigatorio: true, opcoes: API.GRUPOS, valor: it ? it.grupo : estado.grupo },
        { id: "tipo", rotulo: "Tipo", tipo: "texto", obrigatorio: true, max: 80, valor: it ? it.tipo : "", placeholder: "Ex.: Cabo de controle",
          sugestoes: ["Cabo de potência BT 0,6/1 kV", "Cabo de controle", "Cabo de instrumentação", "Cabo de média tensão 8,7/15 kV", "Concreto estrutural (lançamento)",
            "Estrutura metálica", "Aço de armação CA-50", "Tubulação de processo (montagem)", "Painéis elétricos montados"] },
        { id: "disciplina", rotulo: "Disciplina", tipo: "texto", valor: it ? it.disciplina : "", sugestoes: ["Civil", "Estruturas", "Tubulação", "Mecânica", "Elétrica", "Instrumentação"] },
        { id: "unidade", rotulo: "Unidade", tipo: "select", obrigatorio: true, opcoes: API.UNIDADES, valor: it ? it.unidade : "m" },
        { id: "total", rotulo: "Quantidade total da LB", tipo: "numero", obrigatorio: true, min: 0, passo: "any", valor: it ? it.total : null },
        { id: "indiceHH", rotulo: "Índice orçado (HH por unidade)", tipo: "numero", obrigatorio: true, min: 0, passo: "any", valor: it ? it.indiceHH : null,
          ajuda: "Produtividade da proposta; base das horas ganhas e do fator de produtividade" },
        { id: "inicio", rotulo: "Semana inicial", tipo: "select", obrigatorio: true, opcoes: ops, valor: it ? it.inicio : R.somarSemanas(ATUAL, 1) },
        { id: "fim", rotulo: "Semana final", tipo: "select", obrigatorio: true, opcoes: ops, valor: it ? it.fim : R.somarSemanas(ATUAL, 12) },
        { id: "perfil", rotulo: "Perfil de distribuição", tipo: "select", obrigatorio: true, opcoes: API.PERFIS.map(function (p) { return { valor: p.id, texto: p.nome }; }), valor: it ? it.perfil : "curvaS",
          ajuda: "Gera a distribuição; os valores podem ser ajustados semana a semana" },
        { id: "distribuicao", rotulo: "Previsto por semana (LB)", tipo: "info", html: "" },
        { id: "observacoes", rotulo: "Observações", tipo: "textarea", max: 300, linhas: 2, valor: it ? it.observacoes : "" }
      ],
      aoMudar: function (v, ctx) {
        var k = [v.unidade, v.total, v.inicio, v.fim, v.perfil].join("|");
        if (k === chave) { if (m) atualizarSoma(m.el, v.total); return; }
        var primeira = !chave;
        chave = k;
        var sem = v.inicio && v.fim ? R.listaSemanas(v.inicio, v.fim) : [];
        var casas = v.unidade === "t" ? 1 : 0;
        var valores = primeira && it && it.inicio === v.inicio && it.fim === v.fim ? it.distribuicao.map(function (d) { return d.previsto; })
          : R.distribuirQuantidade(v.total || 0, sem.length, v.perfil, casas);
        ctx.info("distribuicao", sem.length ? gradeDistribuicao(sem, valores, casas, v.unidade) : '<p class="text-small text-muted">Escolha semanas inicial e final válidas.</p>');
        somaDepois(function () { return m; }, v.total);
      },
      aoSalvar: function (v, modal) {
        var d = Object.assign({}, v, { id: it ? it.id : null, projetoId: it ? it.projetoId : projetoId, valores: lerDistribuicao(modal.el) });
        return API.salvarItem(d).then(function (x) {
          GI.ui.toast(it ? x.codigo + " atualizado." : x.codigo + " criado em elaboração: aprove a LB para entrar nos indicadores.", "success");
          recarregar();
        });
      }
    });
    m.el.addEventListener("input", function (ev) { if (ev.target.hasAttribute("data-semana")) atualizarSoma(m.el, m.ler().total); });
  }

  function formObservacoes(it) {
    GI.form.abrir({
      titulo: "Observações de " + it.codigo, tamanho: "sm",
      campos: [{ id: "observacoes", rotulo: "Observações", tipo: "textarea", max: 300, linhas: 3, valor: it.observacoes }],
      aoSalvar: function (v) { return API.salvarItem({ id: it.id, observacoes: v.observacoes }).then(function () { GI.ui.toast("Observações gravadas.", "success"); recarregar(); }); }
    });
  }

  /* ---- Revisão da LB (item aprovado) ---- */
  function formRevisao(it) {
    API.smsRevisao(projetoId).then(function (sms) {
      var livre = R.somarSemanas(ATUAL, 1);
      var congeladas = it.distribuicao.filter(function (d) { return d.semana <= ATUAL; }).reduce(function (s, d) { return s + d.previsto; }, 0);
      congeladas = Math.round(congeladas * Math.pow(10, it.casas)) / Math.pow(10, it.casas);
      var fimMin = it.fim > livre ? it.fim : livre;
      var ops = opcoesSemanas(livre, R.somarSemanas(ATUAL, 104));
      var chave = "";
      var m = GI.form.abrir({
        titulo: "Revisar linha de base de " + it.codigo, subtitulo: "Semanas até " + semCurta(ATUAL) + " ficam congeladas; a revisão redistribui o saldo a partir de " + semCurta(livre), tamanho: "xl", colunas: 3,
        intro: sms.length ? "" : '<div class="alert alert--warning">' + U.icone("alertTriangle") + '<div class="alert__body">Nenhuma SM aprovada disponível. Registre a mudança em Governança (08) antes de revisar a linha de base.</div></div>',
        campos: [
          { id: "smRef", rotulo: "SM que autoriza", tipo: "select", obrigatorio: true, opcoes: sms.map(function (s) { return { valor: s.codigo, texto: s.codigo + " · " + s.titulo }; }), largura: "full" },
          { id: "total", rotulo: "Novo total da LB (" + it.unidade + ")", tipo: "numero", obrigatorio: true, min: 0, passo: "any", valor: it.total,
            ajuda: "Realizado acumulado: " + qtu(it.calc.realAcum, it.casas, it.unidade) },
          { id: "fim", rotulo: "Nova semana final", tipo: "select", obrigatorio: true, opcoes: ops, valor: fimMin },
          { id: "perfil", rotulo: "Perfil do saldo", tipo: "select", obrigatorio: true, opcoes: API.PERFIS.map(function (p) { return { valor: p.id, texto: p.nome }; }), valor: "linear" },
          { id: "distribuicao", rotulo: "Previsto por semana a partir de " + semCurta(livre), tipo: "info", html: "" },
          { id: "justificativa", rotulo: "Justificativa", tipo: "textarea", obrigatorio: true, max: 400, linhas: 2 }
        ],
        aoMudar: function (v, ctx) {
          var k = [v.total, v.fim, v.perfil].join("|");
          if (k === chave) { if (m) atualizarSoma(m.el, v.total); return; }
          chave = k;
          var sem = v.fim ? R.listaSemanas(it.inicio > livre ? it.inicio : livre, v.fim) : [];
          var saldo = Math.max(0, (v.total || 0) - congeladas);
          ctx.info("distribuicao", sem.length ? gradeDistribuicao(sem, R.distribuirQuantidade(saldo, sem.length, v.perfil, it.casas), it.casas, it.unidade, congeladas) : "");
          somaDepois(function () { return m; }, v.total);
        },
        aoSalvar: function (v, modal) {
          return API.revisarItem(it.id, { smRef: v.smRef, justificativa: v.justificativa, total: v.total, fim: v.fim, perfil: v.perfil, valores: lerDistribuicao(modal.el) }).then(function (x) {
            GI.ui.toast("Linha de base de " + x.codigo + " revisada (rev " + x.revisao + ").", "success"); recarregar();
          });
        }
      });
      m.el.addEventListener("input", function (ev) { if (ev.target.hasAttribute("data-semana")) atualizarSoma(m.el, m.ler().total); });
    });
  }

  /* ---- Apontamento semanal ---- */
  function formApontar() {
    var empresas = empresasComDados.filter(function (id) { return U.mapas.empresas[id] && U.mapas.empresas[id].tipo === "Contratada"; })
      .map(function (id) { return { valor: id, texto: U.empresa(id) }; });
    var semanas = opcoesSemanas(R.somarSemanas(ATUAL, -12), ATUAL).reverse();
    var chave = "", linhasAtuais = [];
    GI.form.abrir({
      titulo: "Apontar semana", subtitulo: "Realizado e HH apropriadas informados pela contratada, por item da LB", tamanho: "xl",
      campos: [
        { id: "empresaId", rotulo: "Empresa", tipo: "select", obrigatorio: true, opcoes: empresas, valor: estado.empresaId || (empresas[0] || {}).valor },
        { id: "semana", rotulo: "Semana", tipo: "select", obrigatorio: true, opcoes: semanas, valor: estado.corte <= ATUAL ? estado.corte : ATUAL },
        { id: "grade", rotulo: "Itens da empresa", tipo: "info", html: "" }
      ],
      aoMudar: function (v, ctx) {
        var k = v.empresaId + "|" + v.semana;
        if (k === chave || !v.empresaId || !v.semana) return;
        chave = k;
        API.quantidades(projetoId, { corte: v.semana, empresaId: Number(v.empresaId) }).then(function (d) {
          linhasAtuais = d.itens.filter(function (i) { return i.situacao === "Aprovada" && i.inicio <= v.semana && (i.calc.saldo > 0 || i.calc.realSem != null); });
          ctx.info("grade", linhasAtuais.length ? '<div class="table-wrap"><table class="table table--compact"><caption class="sr-only">Apontamento da semana</caption><thead><tr><th scope="col">Item</th>' +
            '<th scope="col" class="num">Previsto na semana</th><th scope="col" class="num">Realizado</th><th scope="col" class="num">HH apropriadas</th><th scope="col" class="num">Acumulado / LB</th></tr></thead><tbody>' +
            linhasAtuais.map(function (i) {
              var a = i.apontamentos.filter(function (x) { return x.semana === v.semana; })[0];
              return '<tr><th scope="row"><div class="cell-title"><b>' + U.esc(i.codigo) + "</b><small>" + U.esc(i.tipo) + " (" + U.esc(i.unidade) + ")</small></div></th>" +
                '<td class="num">' + qt(i.calc.prevSem, i.casas) + "</td>" +
                '<td><input class="input input--grade" type="number" min="0" step="' + (i.casas ? "0.1" : "1") + '" data-real="' + i.id + '" value="' + (a ? a.realizado : "") + '" aria-label="Realizado ' + U.esc(i.codigo) + '"></td>' +
                '<td><input class="input input--grade" type="number" min="0" step="1" data-hh="' + i.id + '" value="' + (a ? a.hh : "") + '" aria-label="HH apropriadas ' + U.esc(i.codigo) + '"></td>' +
                '<td class="num">' + qt(i.calc.realAcum, i.casas) + " / " + qt(i.total, i.casas) + "</td></tr>";
            }).join("") + "</tbody></table></div>" +
            '<p class="text-small text-muted mt-2">Deixe em branco o item sem apontamento. Acumulado acima do total da LB exige SM (08) e revisão da linha de base.</p>'
            : U.vazio("Nenhum item com linha de base aprovada e saldo nesta semana.", "barChart"));
        });
      },
      aoSalvar: function (v, modal) {
        var linhas = linhasAtuais.map(function (i) {
          var r = modal.el.querySelector('[data-real="' + i.id + '"]'), h = modal.el.querySelector('[data-hh="' + i.id + '"]');
          return { itemId: i.id, realizado: r && r.value !== "" ? Number(r.value) : null, hh: h && h.value !== "" ? Number(h.value) : null };
        });
        if (!linhas.some(function (l) { return l.realizado != null || l.hh != null; })) return Promise.reject({ erros: ["Informe o realizado de ao menos um item."] });
        return API.apontar(projetoId, Number(v.empresaId), v.semana, linhas).then(function (n) {
          GI.ui.toast(U.plural(n, "item apontado", "itens apontados") + " em " + semCurta(v.semana) + ".", "success"); recarregar();
        });
      }
    });
  }

  function importar() {
    var nomes = contratadas().map(function (e) { return e.texto; });
    GI.importar.abrir({
      titulo: "Importar plano de quantidades (Excel)", subtitulo: "Itens entram em elaboração, distribuídos pelo perfil; aprove a LB depois de conferir", arquivoModelo: "modelo-plano-quantidades",
      colunas: [
        { campo: "empresa", titulo: "Empresa", tipo: "lista", obrigatorio: true, opcoes: nomes, exemplo: "Alfa Montagens" },
        { campo: "grupo", titulo: "Grupo", tipo: "lista", obrigatorio: true, opcoes: API.GRUPOS, exemplo: "Cabo elétrico" },
        { campo: "tipo", titulo: "Tipo", tipo: "texto", obrigatorio: true, exemplo: "Cabo de iluminação" },
        { campo: "disciplina", titulo: "Disciplina", tipo: "texto", exemplo: "Elétrica" },
        { campo: "unidade", titulo: "Unidade", tipo: "lista", obrigatorio: true, opcoes: API.UNIDADES, exemplo: "m" },
        { campo: "total", titulo: "Quantidade total", tipo: "num", obrigatorio: true, exemplo: 12000 },
        { campo: "indiceHH", titulo: "Índice HH por unidade", tipo: "num", obrigatorio: true, exemplo: 0.08 },
        { campo: "inicio", titulo: "Semana inicial", tipo: "texto", obrigatorio: true, exemplo: R.somarSemanas(ATUAL, 2) },
        { campo: "fim", titulo: "Semana final", tipo: "texto", obrigatorio: true, exemplo: R.somarSemanas(ATUAL, 14) },
        { campo: "perfil", titulo: "Perfil", tipo: "lista", opcoes: ["Curva S", "Linear", "Concentrado no início", "Concentrado no fim"], exemplo: "Curva S" }
      ],
      validarLinha: function (o) {
        var e = [];
        if (!R.inicioSemana(o.inicio) || !R.inicioSemana(o.fim)) e.push("semanas no formato 2026-S40");
        else if (o.fim < o.inicio) e.push("semana final antes da inicial");
        if (!(o.total > 0)) e.push("quantidade total deve ser maior que zero");
        if (!(o.indiceHH > 0)) e.push("índice HH deve ser maior que zero");
        return e;
      },
      aoImportar: function (linhas) {
        return API.importarItens(projetoId, linhas).then(function (cods) { recarregar(); return U.plural(cods.length, "item incluído", "itens incluídos") + " em elaboração."; });
      }
    });
  }

  /* ======================================================================
     Aba Horas efetivas
     ====================================================================== */
  function periodoHoras() {
    var ate = fimSemana(estado.corte);
    if (ate > GI.api.referencia()) ate = GI.api.referencia();
    if (estado.periodo === "semana") return { de: R.inicioSemana(estado.corte), ate: ate };
    if (estado.periodo === "janela") return { de: R.inicioSemana(R.somarSemanas(estado.corte, -(PAR.semanasMedia - 1))), ate: ate };
    return { de: null, ate: ate };
  }
  function carregarHoras() {
    var p = periodoHoras();
    return API.horasEfetivas({ projetoId: projetoId, empresaId: estado.empresaId || null, area: estado.area || null, encarregado: estado.encarregado || null, de: p.de, ate: p.ate })
      .then(function (d) { horas = d; renderHoras(); });
  }
  function renderHoras() {
    var p = periodoHoras();
    document.getElementById("f-area").innerHTML = U.opcoes(horas.areas, estado.area, "Todas as áreas (CWA)");
    document.getElementById("f-encarregado").innerHTML = U.opcoes(horas.encarregados, estado.encarregado, "Todos os encarregados");
    document.getElementById("f-periodo").innerHTML = U.opcoes([
      { valor: "semana", texto: "Semana de corte" }, { valor: "janela", texto: "Últimas " + PAR.semanasMedia + " semanas" }, { valor: "tudo", texto: "Desde o início" }], estado.periodo);
    document.getElementById("periodo-horas").textContent = "Período: " + (p.de ? F.data(p.de) + " a " : "até ") + F.data(p.ate) + " · " +
      U.plural(horas.capacidade.registros, "registro de jornada", "registros de jornada") + " · " + U.plural(horas.amostragem.observacoes, "rodada de observação", "rodadas de observação") +
      " · " + U.plural(horas.resumoParalisacoes.eventos, "paralisação", "paralisações");
    ["cp", "amostragem", "paralisacoes"].forEach(function (v) { document.getElementById("v-" + v).hidden = v !== estado.visao; });
    document.querySelectorAll("#f-visao .segmented__opt").forEach(function (o) { o.setAttribute("aria-pressed", String(o.getAttribute("data-value") === estado.visao)); });
    if (estado.visao === "cp") renderCp();
    else if (estado.visao === "amostragem") renderAmostragem();
    else renderParalisacoes();
  }

  function renderCp() {
    var c = horas.capacidade;
    document.getElementById("kpis-cp").innerHTML = [
      U.kpi({ rotulo: "Capacidade produtiva (CP)", valor: horasDec(c.cp), unidade: c.cp == null ? "" : "h/dia", icone: "clock", cor: "primary", esperado: { rotulo: "Meta", valor: "≥ " + F.num(metaCp(), 2) + " h" },
        rodape: "manhã " + horasDec(c.cpManha) + " h · tarde " + horasDec(c.cpTarde) + " h" }),
      U.kpi({ rotulo: "Utilização da jornada", valor: c.utilizacao == null ? "·" : F.num(c.utilizacao, 1), unidade: c.utilizacao == null ? "" : "%", icone: "gauge", cor: corFaixa(faixaUtil(c.utilizacao)), esperado: { rotulo: "Meta", valor: "≥ " + F.pct(PAR.metaUtilizacaoPct, 0) },
        rodape: "CP ÷ jornada de " + F.num(PAR.jornadaDiariaHoras, 1) + " h" }),
      U.kpi({ rotulo: "Atraso médio de início", valor: c.atrasoManhaMin == null ? "·" : F.num(c.atrasoManhaMin), unidade: c.atrasoManhaMin == null ? "" : "min", icone: "calendarClock",
        cor: c.atrasoManhaMin > atrasoFx()[1] ? "danger" : c.atrasoManhaMin > atrasoFx()[0] ? "warning" : "success", esperado: { rotulo: "Limite", valor: "≤ " + F.num(atrasoFx()[0]) + " min" }, rodape: "manhã, da chegada ao início · tarde " + (c.atrasoTardeMin == null ? "·" : F.num(c.atrasoTardeMin) + " min") }),
      U.kpi({ rotulo: "HH efetivas", valor: F.num(c.hhEfetivas || 0), icone: "users", cor: "info",
        esperado: { rotulo: "Meta", valor: "≥ " + F.num(((c.hhEfetivas || 0) + (c.hhImprodutivas || 0)) * PAR.metaUtilizacaoPct / 100) }, rodape: "CP x efetivo nas frentes registradas" }),
      U.kpi({ rotulo: "HH improdutivas na frente", valor: F.num(c.hhImprodutivas || 0), icone: "alertTriangle", cor: c.hhImprodutivas ? "warning" : "success",
        esperado: { rotulo: "Esperado", valor: F.num(0) }, rodape: "(jornada − CP) x efetivo" })
    ].join("");
    var el = document.getElementById("linha-tempo");
    if (!c.registros) { el.innerHTML = U.vazio("Nenhum registro de jornada no filtro.", "clock"); }
    else {
      var mn = R.minutos;
      function marco(rot, h) { return '<div class="jornada__marco"><span>' + U.esc(rot) + "</span><b>" + U.esc(h || "·") + "</b></div>"; }
      function trecho(rot, min, tipo) {
        return '<div class="jornada__trecho jornada__trecho--' + tipo + '"><span class="jornada__seta" aria-hidden="true"></span><b>' + duracao(min) + "</b><span>" + U.esc(rot) + "</span></div>";
      }
      el.innerHTML = '<div class="jornada">' +
        '<div class="jornada__turno"><h3 class="jornada__titulo">Turno da manhã</h3><div class="jornada__linha">' +
          marco("Chegada na frente", c.manha.chegada) + trecho("Atraso de início", mn(c.manha.inicio) - mn(c.manha.chegada), "atraso") +
          marco("Início das atividades", c.manha.inicio) + trecho("Execução", mn(c.manha.termino) - mn(c.manha.inicio), "execucao") + marco("Término das atividades", c.manha.termino) + "</div></div>" +
        '<div class="jornada__turno jornada__turno--almoco"><h3 class="jornada__titulo">Almoço</h3><div class="jornada__linha jornada__linha--3">' +
          marco("Saída para almoço", c.manha.termino) + trecho("Duração do almoço", mn(c.tarde.chegada) - mn(c.manha.termino), "pausa") + marco("Retorno do almoço", c.tarde.chegada) + "</div></div>" +
        '<div class="jornada__turno"><h3 class="jornada__titulo">Turno da tarde</h3><div class="jornada__linha">' +
          marco("Chegada na frente", c.tarde.chegada) + trecho("Atraso de início", mn(c.tarde.inicio) - mn(c.tarde.chegada), "atraso") +
          marco("Início das atividades", c.tarde.inicio) + trecho("Execução", mn(c.tarde.termino) - mn(c.tarde.inicio), "execucao") + marco("Término das atividades", c.tarde.termino) + "</div></div>" +
        "</div>";
    }
    GI.charts.bar("g-cp-area", { labels: horas.porArea.map(function (a) { return a.area; }), horizontal: true, casas: 2, ariaLabel: "Capacidade produtiva por área",
      series: [{ label: "CP (h/dia)", color: "chart-1", data: horas.porArea.map(function (a) { return a.cp; }) }] });
    var dias = horas.porDia.filter(function (d) { return d.cp != null; });
    var metaH = Math.round(PAR.jornadaDiariaHoras * PAR.metaUtilizacaoPct) / 100;
    document.getElementById("sub-cp-dia").textContent = "Média das frentes por dia; meta de " + F.num(metaH, 2) + " h (" + F.pct(PAR.metaUtilizacaoPct, 0) + " da jornada)";
    GI.charts.line("g-cp-dia", { labels: dias.map(function (d) { return dataCurta(d.data); }), casas: 2, ariaLabel: "Capacidade produtiva por dia",
      series: [{ label: "CP (h/dia)", color: "chart-1", data: dias.map(function (d) { return d.cp; }) },
        { label: "Meta", color: "chart-baseline", dashed: true, points: false, data: dias.map(function () { return metaH; }) }] });
    document.getElementById("sub-jornadas").textContent = U.plural(horas.jornadas.length, "registro", "registros") + " · registrado pela fiscalização da gerenciadora";
    tb.jornadas.atualizar(horas.jornadas);
  }
  function criarTabelasHoras() {
    tb.jornadas = GI.tabela.criar("tb-jornadas", {
      porPagina: 15, ordem: { coluna: "data", direcao: "desc" }, vazio: "Nenhum registro de jornada no filtro.", legenda: "Registros de jornada",
      colunas: [
        { id: "data", titulo: "Data", tipo: "data" },
        { id: "empresa", titulo: "Empresa", valor: function (j) { return U.empresa(j.empresaId); } },
        { id: "frente", titulo: "Área / encarregado", valor: function (j) { return j.area + " · " + j.encarregado; },
          html: function (j) { return '<div class="cell-title"><b>' + U.esc(j.area) + "</b><small>" + U.esc(j.encarregado) + "</small></div>"; } },
        { id: "efetivo", titulo: "Efetivo", tipo: "num" },
        { id: "manha", titulo: "Manhã", ordenavel: false, valor: function (j) { return j.manha.chegada + " · " + j.manha.inicio + " · " + j.manha.termino; }, classe: "nowrap" },
        { id: "tarde", titulo: "Tarde", ordenavel: false, valor: function (j) { return j.tarde.chegada + " · " + j.tarde.inicio + " · " + j.tarde.termino; }, classe: "nowrap" },
        { id: "atraso", titulo: "Atraso (min)", tipo: "num", valor: function (j) { return j.calc.atrasoManhaMin + j.calc.atrasoTardeMin; } },
        { id: "cp", titulo: "CP (h)", tipo: "num", casas: 2, valor: function (j) { return j.calc.cp; } },
        { id: "utilizacao", titulo: "Utilização", tipo: "pct", casas: 0, valor: function (j) { return j.calc.utilizacao; },
          html: function (j) { return selo(F.pct(j.calc.utilizacao, 0), faixaUtil(j.calc.utilizacao)); } }
      ],
      acoes: function (j) { return '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-jornada="' + j.id + '" aria-label="Editar registro" title="Editar">' + U.icone("edit") + "</button>"; }
    });
    tb.amostraEmp = GI.tabela.criar("tb-amostra-emp", {
      porPagina: 0, vazio: "Nenhuma rodada de observação no filtro.", legenda: "Amostragem por empresa e encarregado",
      colunas: [
        { id: "nome", titulo: "Empresa / encarregado", ordenavel: false, fixa: true, html: function (r) { return r.nivel === 1 ? "<b>" + U.esc(r.nome) + "</b>" : U.esc(r.nome); } },
        { id: "observacoes", titulo: "Rodadas", tipo: "num", ordenavel: false },
        { id: "pessoas", titulo: "Pessoas observadas", tipo: "num", ordenavel: false },
        { id: "pctTrabalhando", titulo: "% trabalhando", tipo: "pct", casas: 1, ordenavel: false, html: function (r) { return selo(pctTxt(r.pctTrabalhando), faixaTrab(r.pctTrabalhando)); } },
        { id: "pctTransito", titulo: "% em trânsito", tipo: "pct", casas: 1, ordenavel: false },
        { id: "pctParado", titulo: "% parado", tipo: "pct", casas: 1, ordenavel: false }
      ],
      classeLinha: function (r) { return r.nivel === 1 ? "row--nivel-1" : "row--nivel-2"; }
    });
    tb.amostras = GI.tabela.criar("tb-amostras", {
      porPagina: 15, ordem: { coluna: "data", direcao: "desc" }, vazio: "Nenhuma rodada de observação no filtro.", legenda: "Rodadas de observação",
      colunas: [
        { id: "data", titulo: "Data", tipo: "data" }, { id: "hora", titulo: "Hora" },
        { id: "empresa", titulo: "Empresa", valor: function (a) { return U.empresa(a.empresaId); } },
        { id: "frente", titulo: "Área / encarregado", valor: function (a) { return a.area + " · " + a.encarregado; },
          html: function (a) { return '<div class="cell-title"><b>' + U.esc(a.area) + "</b><small>" + U.esc(a.encarregado) + "</small></div>"; } },
        { id: "trabalhando", titulo: "Trabalhando", tipo: "num" }, { id: "transito", titulo: "Em trânsito", tipo: "num" }, { id: "parado", titulo: "Parado", tipo: "num" },
        { id: "pct", titulo: "% trabalhando", tipo: "pct", casas: 0, valor: function (a) { var n = a.trabalhando + a.transito + a.parado; return n ? a.trabalhando / n * 100 : null; },
          html: function (a) { var n = a.trabalhando + a.transito + a.parado, v = n ? a.trabalhando / n * 100 : null; return v == null ? "·" : selo(F.pct(v, 0), faixaTrab(v)); } }
      ],
      acoes: function (a) { return '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-amostra="' + a.id + '" aria-label="Editar rodada" title="Editar">' + U.icone("edit") + "</button>"; }
    });
    tb.paral = GI.tabela.criar("tb-paral", {
      porPagina: 15, ordem: { coluna: "data", direcao: "desc" }, vazio: "Nenhuma paralisação no filtro.", legenda: "Registros de paralisação",
      colunas: [
        { id: "data", titulo: "Data", tipo: "data" },
        { id: "empresa", titulo: "Empresa", valor: function (p) { return U.empresa(p.empresaId); } },
        { id: "area", titulo: "Área" },
        { id: "recurso", titulo: "Recurso parado", valor: function (p) { return p.tipo + " · " + p.recurso; },
          html: function (p) { return '<div class="cell-title"><b>' + U.esc(p.recurso) + "</b><small>" + U.esc(p.tipo) + " · " + F.num(p.quantidade) + " · " + U.esc(p.inicio) + " a " + U.esc(p.termino) + "</small></div>"; } },
        { id: "total", titulo: "Hhora / Mhora", tipo: "num", casas: 1, valor: function (p) { return p.calc.total; },
          html: function (p) { return F.num(p.calc.total, 1) + " " + (p.tipo === "Efetivo" ? "Hhora" : "Mhora"); } },
        { id: "motivo", titulo: "Motivo" },
        { id: "responsabilidade", titulo: "Responsabilidade", html: function (p) {
          return p.calc.externa ? U.badge(p.responsabilidade, "warning", true) + (p.responsabilidade === "Cliente" ? '<br><small class="text-muted">pleito potencial</small>' : "")
            : U.badge(p.responsabilidade, p.responsabilidade === "Clima" ? "info" : "neutral"); } }
      ],
      acoes: function (p) { return '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-paral="' + p.id + '" aria-label="Editar paralisação" title="Editar">' + U.icone("edit") + "</button>"; }
    });
  }

  function renderAmostragem() {
    var a = horas.amostragem;
    document.getElementById("kpis-amostra").innerHTML = [
      U.kpi({ rotulo: "Trabalhando", valor: a.pctTrabalhando == null ? "·" : F.num(a.pctTrabalhando, 1), unidade: a.pctTrabalhando == null ? "" : "%", icone: "hardHat",
        cor: corFaixa(faixaTrab(a.pctTrabalhando)), esperado: { rotulo: "Meta", valor: "≥ " + F.pct(PAR.metaTrabalhandoPct, 0) }, rodape: F.num(a.trabalhando) + " pessoas" }),
      U.kpi({ rotulo: "Em trânsito", valor: a.pctTransito == null ? "·" : F.num(a.pctTransito, 1), unidade: a.pctTransito == null ? "" : "%", icone: "truck", cor: "warning", esperado: { rotulo: "Limite", valor: "≤ " + F.pct(100 - PAR.metaTrabalhandoPct, 0) }, rodape: F.num(a.transito) + " pessoas" }),
      U.kpi({ rotulo: "Parado", valor: a.pctParado == null ? "·" : F.num(a.pctParado, 1), unidade: a.pctParado == null ? "" : "%", icone: "octagonAlert", cor: "danger", esperado: { rotulo: "Esperado", valor: F.pct(0, 0) }, rodape: F.num(a.parado) + " pessoas" }),
      U.kpi({ rotulo: "Rodadas de observação", valor: F.num(a.observacoes), icone: "clipboardCheck", cor: "info", esperado: { rotulo: "Referência", valor: U.plural(horas.capacidade.registros, "jornada", "jornadas") }, rodape: F.num(a.pessoas) + " pessoas observadas" })
    ].join("");
    var dias = horas.porDia.filter(function (d) { return d.pctTrabalhando != null; });
    GI.charts.bar("g-amostra-dia", { labels: dias.map(function (d) { return dataCurta(d.data); }), stacked: true, percent: true, max: 100, ariaLabel: "Distribuição por dia",
      series: [{ label: "Trabalhando", color: "status-success-solid", data: dias.map(function (d) { return d.pctTrabalhando; }) },
        { label: "Em trânsito", color: "status-warning-solid", data: dias.map(function (d) { return d.pctTransito; }) },
        { label: "Parado", color: "status-danger-solid", data: dias.map(function (d) { return d.pctParado; }) }] });
    listaMov("motivos-parado", horas.motivosParado, "", 0, "Nenhuma pessoa parada nas rodadas do filtro.");
    listaMov("motivos-transito", horas.motivosTransito, "", 0, "Nenhuma pessoa em trânsito nas rodadas do filtro.");
    var linhas = [];
    horas.amostragemPorEmpresa.forEach(function (e) {
      linhas.push(Object.assign({ nivel: 1, nome: U.empresa(e.empresaId) }, e));
      e.encarregados.forEach(function (x) { linhas.push(Object.assign({ nivel: 2, nome: x.encarregado }, x)); });
    });
    tb.amostraEmp.atualizar(linhas);
    document.getElementById("sub-amostras").textContent = U.plural(horas.amostras.length, "rodada", "rodadas") + " no período";
    tb.amostras.atualizar(horas.amostras);
  }

  function renderParalisacoes() {
    var r = horas.resumoParalisacoes;
    document.getElementById("kpis-par").innerHTML = [
      U.kpi({ rotulo: "Efetivo paralisado", valor: F.num(r.hhora, 1), unidade: "Hhora", icone: "users", cor: r.hhora ? "danger" : "success", esperado: { rotulo: "Esperado", valor: F.num(0) }, rodape: "pessoas x horas paradas" }),
      U.kpi({ rotulo: "Máquinas e equipamentos parados", valor: F.num(r.mhora, 1), unidade: "Mhora", icone: "truck", cor: r.mhora ? "warning" : "success", esperado: { rotulo: "Esperado", valor: F.num(0) }, rodape: "unidades x horas paradas" }),
      U.kpi({ rotulo: "Responsabilidade do cliente", valor: F.num(r.hhoraCliente, 1), unidade: "Hhora", icone: "gavel", cor: r.hhoraCliente ? "warning" : "success", esperado: { rotulo: "Esperado", valor: F.num(0) },
        rodape: "pleito potencial · gerenciadora e terceiros " + F.num(r.hhoraExterna - r.hhoraCliente, 1) }),
      U.kpi({ rotulo: "Clima", valor: F.num(r.hhoraClima, 1), unidade: "Hhora", icone: "calendarClock", cor: "info", esperado: { rotulo: "Esperado", valor: F.num(0) }, rodape: "tempo excusável sem compensação" }),
      U.kpi({ rotulo: "Eventos", valor: F.num(r.eventos), icone: "list", cor: "info", esperado: { rotulo: "Esperado", valor: F.num(0) }, rodape: "registros de paralisação" })
    ].join("");
    tb.parArea.atualizar(horas.porArea);
    listaMov("par-motivo", r.porMotivoEfetivo, "Hhora", 1, "Nenhuma paralisação de efetivo no filtro.");
    listaMov("par-resp", r.porResponsabilidade, "Hhora", 1, "Nenhuma paralisação de efetivo no filtro.");
    document.getElementById("sub-paral").textContent = U.plural(horas.paralisacoes.length, "registro", "registros") + " · Hhora = pessoas x horas; Mhora = unidades x horas";
    tb.paral.atualizar(horas.paralisacoes);
  }
  function criarTabelaParArea() {
    tb.parArea = GI.tabela.criar("tb-par-area", {
      porPagina: 0, ordem: { coluna: "area", direcao: "asc" }, vazio: "Nenhum registro no filtro.", legenda: "Resumo por área",
      colunas: [
        { id: "area", titulo: "Área (CWA)", fixa: true },
        { id: "cp", titulo: "CP (h/dia)", tipo: "num", casas: 2 },
        { id: "utilizacao", titulo: "Utilização", tipo: "pct", casas: 0, html: function (a) { return a.utilizacao == null ? "·" : selo(F.pct(a.utilizacao, 0), faixaUtil(a.utilizacao)); } },
        { id: "hhora", titulo: "Efetivo paralisado (Hhora)", tipo: "num", casas: 1 },
        { id: "mhora", titulo: "Máq./equip. parados (Mhora)", tipo: "num", casas: 1 }
      ]
    });
  }

  /* ---- Formulários de campo ---- */
  function opcoesFrentes(campo) {
    return (horas ? (campo === "area" ? horas.areas : horas.encarregados) : []).slice();
  }
  function formJornada(j) {
    var m = GI.form.abrir({
      titulo: j ? "Editar jornada" : "Registrar jornada", subtitulo: "Fiscalização da frente de serviço: horários dos dois turnos e efetivo", tamanho: "lg", colunas: 3,
      campos: [
        { id: "data", rotulo: "Data", tipo: "data", obrigatorio: true, valor: j ? j.data : GI.api.referencia(), maxData: GI.api.referencia() },
        { id: "empresaId", rotulo: "Empresa", tipo: "select", obrigatorio: true, opcoes: contratadas(), valor: j ? j.empresaId : estado.empresaId },
        { id: "efetivo", rotulo: "Efetivo na frente", tipo: "numero", obrigatorio: true, min: 1, passo: 1, valor: j ? j.efetivo : null },
        { id: "area", rotulo: "Área (CWA)", tipo: "texto", obrigatorio: true, valor: j ? j.area : estado.area, sugestoes: opcoesFrentes("area") },
        { id: "encarregado", rotulo: "Encarregado", tipo: "texto", obrigatorio: true, valor: j ? j.encarregado : estado.encarregado, sugestoes: opcoesFrentes("encarregado") },
        { id: "sep", rotulo: "", tipo: "info", html: '<h3 class="section-title">Turno da manhã</h3>' },
        { id: "mChegada", rotulo: "Chegada na frente", tipo: "hora", obrigatorio: true, valor: j ? j.manha.chegada : "07:30" },
        { id: "mInicio", rotulo: "Início das atividades", tipo: "hora", obrigatorio: true, valor: j ? j.manha.inicio : "" },
        { id: "mTermino", rotulo: "Término das atividades", tipo: "hora", obrigatorio: true, valor: j ? j.manha.termino : "" },
        { id: "sep2", rotulo: "", tipo: "info", html: '<h3 class="section-title">Turno da tarde</h3>' },
        { id: "tChegada", rotulo: "Chegada na frente", tipo: "hora", obrigatorio: true, valor: j ? j.tarde.chegada : "" },
        { id: "tInicio", rotulo: "Início das atividades", tipo: "hora", obrigatorio: true, valor: j ? j.tarde.inicio : "" },
        { id: "tTermino", rotulo: "Término das atividades", tipo: "hora", obrigatorio: true, valor: j ? j.tarde.termino : "" },
        { id: "previa", rotulo: "Resultado", tipo: "info", html: "" },
        { id: "observacoes", rotulo: "Observações", tipo: "textarea", max: 300, linhas: 2, valor: j ? j.observacoes : "" }
      ],
      aoMudar: function (v, ctx) {
        var em = R.duracaoHoras(v.mInicio, v.mTermino), et = R.duracaoHoras(v.tInicio, v.tTermino);
        if (em == null || et == null) { ctx.info("previa", '<p class="text-small text-muted">Preencha os horários para ver a capacidade produtiva.</p>'); return; }
        var cp = em + et, ut = cp / PAR.jornadaDiariaHoras * 100;
        ctx.info("previa", '<div class="cluster text-small"><span>Atraso manhã: <b>' + duracao(R.minutos(v.mInicio) - R.minutos(v.mChegada)) + "</b></span><span>Execução manhã: <b>" + duracao(em * 60) +
          "</b></span><span>Almoço: <b>" + duracao(R.minutos(v.tChegada) - R.minutos(v.mTermino)) + "</b></span><span>Execução tarde: <b>" + duracao(et * 60) + "</b></span><span>CP: <b>" + F.num(cp, 2) + " h</b></span>" +
          "<span>Utilização: " + selo(F.pct(ut, 0), faixaUtil(ut)) + "</span>" + (v.efetivo ? "<span>HH efetivas: <b>" + F.num(cp * v.efetivo, 1) + "</b></span>" : "") + "</div>");
      },
      aoSalvar: function (v) {
        return API.salvarJornada(Object.assign({}, v, { id: j ? j.id : null, projetoId: j ? j.projetoId : projetoId })).then(function () { GI.ui.toast(j ? "Jornada atualizada." : "Jornada registrada.", "success"); recarregar(); });
      }
    });
    return m;
  }
  function gradeMotivos(titulo, cat, valores, attr) {
    var mapa = {}; (valores || []).forEach(function (x) { mapa[x.motivo] = x.qtd; });
    return '<fieldset class="grade-motivos"><legend>' + U.esc(titulo) + '</legend>' + cat.map(function (m) {
      return '<label class="grade-motivos__cel"><span>' + U.esc(m) + '</span><input class="input input--grade" type="number" min="0" step="1" ' + attr + '="' + U.esc(m) + '" value="' + (mapa[m] || "") + '"></label>';
    }).join("") + "</fieldset>";
  }
  function lerMotivos(el, attr) {
    var o = {};
    el.querySelectorAll("[" + attr + "]").forEach(function (i) { if (i.value !== "") o[i.getAttribute(attr)] = Number(i.value); });
    return o;
  }
  function formAmostragem(a) {
    var m = GI.form.abrir({
      titulo: a ? "Editar rodada de observação" : "Registrar observação", subtitulo: "Amostragem do trabalho: pessoas trabalhando, em trânsito e paradas no instante da rodada", tamanho: "xl", colunas: 3,
      campos: [
        { id: "data", rotulo: "Data", tipo: "data", obrigatorio: true, valor: a ? a.data : GI.api.referencia(), maxData: GI.api.referencia() },
        { id: "hora", rotulo: "Hora da rodada", tipo: "hora", obrigatorio: true, valor: a ? a.hora : "09:30" },
        { id: "empresaId", rotulo: "Empresa", tipo: "select", obrigatorio: true, opcoes: contratadas(), valor: a ? a.empresaId : estado.empresaId },
        { id: "area", rotulo: "Área (CWA)", tipo: "texto", obrigatorio: true, valor: a ? a.area : estado.area, sugestoes: opcoesFrentes("area") },
        { id: "encarregado", rotulo: "Encarregado", tipo: "texto", obrigatorio: true, valor: a ? a.encarregado : estado.encarregado, sugestoes: opcoesFrentes("encarregado") },
        { id: "trabalhando", rotulo: "Pessoas trabalhando", tipo: "numero", obrigatorio: true, min: 0, passo: 1, valor: a ? a.trabalhando : null },
        { id: "motivos", rotulo: "", tipo: "info", html: gradeMotivos("Paradas, por motivo", API.MOTIVOS_PARADO, a && a.motivosParado, "data-mparado") +
          gradeMotivos("Em trânsito, por motivo", API.MOTIVOS_TRANSITO, a && a.motivosTransito, "data-mtransito") },
        { id: "previa", rotulo: "Resultado da rodada", tipo: "info", html: "" }
      ],
      aoMudar: function (v, ctx) { if (m) previaAmostra(m.el, v, ctx); },
      aoSalvar: function (v, modal) {
        return API.salvarAmostragem(Object.assign({}, v, { id: a ? a.id : null, projetoId: a ? a.projetoId : projetoId, motivosParado: lerMotivos(modal.el, "data-mparado"), motivosTransito: lerMotivos(modal.el, "data-mtransito") }))
          .then(function () { GI.ui.toast(a ? "Rodada atualizada." : "Rodada registrada.", "success"); recarregar(); });
      }
    });
    function previaAmostra(el, v, ctx) {
      var par = 0, tra = 0;
      el.querySelectorAll("[data-mparado]").forEach(function (i) { par += Number(i.value) || 0; });
      el.querySelectorAll("[data-mtransito]").forEach(function (i) { tra += Number(i.value) || 0; });
      var t = Number(v.trabalhando) || 0, n = t + par + tra;
      ctx.info("previa", '<div class="cluster text-small"><span>Observadas: <b>' + F.num(n) + "</b></span><span>Trabalhando: " + (n ? selo(F.pct(t / n * 100, 0), faixaTrab(t / n * 100)) : "·") +
        "</span><span>Em trânsito: <b>" + F.num(tra) + (n ? " (" + F.pct(tra / n * 100, 0) + ")" : "") + "</b></span><span>Paradas: <b>" + F.num(par) + (n ? " (" + F.pct(par / n * 100, 0) + ")" : "") + "</b></span></div>");
    }
    previaAmostra(m.el, m.ler(), { info: function (id, html) { var b = m.el.querySelector('[data-campo="' + id + '"] [data-info]'); if (b) b.innerHTML = html; } });
    m.el.addEventListener("input", function (ev) {
      if (ev.target.hasAttribute("data-mparado") || ev.target.hasAttribute("data-mtransito")) previaAmostra(m.el, m.ler(), { info: function (id, html) { var b = m.el.querySelector('[data-campo="' + id + '"] [data-info]'); if (b) b.innerHTML = html; } });
    });
  }
  function formParalisacao(p) {
    GI.form.abrir({
      titulo: p ? "Editar paralisação" : "Registrar paralisação", subtitulo: "Efetivo (Hhora) ou máquina e equipamento (Mhora) parados na frente", tamanho: "lg", colunas: 3,
      campos: [
        { id: "data", rotulo: "Data", tipo: "data", obrigatorio: true, valor: p ? p.data : GI.api.referencia(), maxData: GI.api.referencia() },
        { id: "empresaId", rotulo: "Empresa", tipo: "select", obrigatorio: true, opcoes: contratadas(), valor: p ? p.empresaId : estado.empresaId },
        { id: "area", rotulo: "Área (CWA)", tipo: "texto", obrigatorio: true, valor: p ? p.area : estado.area, sugestoes: opcoesFrentes("area") },
        { id: "tipo", rotulo: "Tipo", tipo: "escolha", obrigatorio: true, largura: "full", valor: p ? p.tipo : "Efetivo",
          opcoes: [{ valor: "Efetivo", texto: "Efetivo", sub: "pessoas (Hhora)" }, { valor: "Máquina/Equipamento", texto: "Máquina ou equipamento", sub: "unidades (Mhora)" }] },
        { id: "recurso", rotulo: "Recurso parado", tipo: "texto", obrigatorio: true, max: 80, valor: p ? p.recurso : "", placeholder: "Ex.: Montadores de estrutura; Guindaste 90 t" },
        { id: "quantidade", rotulo: "Quantidade", tipo: "numero", obrigatorio: true, min: 1, passo: 1, valor: p ? p.quantidade : null },
        { id: "inicio", rotulo: "Hora de início", tipo: "hora", obrigatorio: true, valor: p ? p.inicio : "" },
        { id: "termino", rotulo: "Hora de término", tipo: "hora", obrigatorio: true, valor: p ? p.termino : "" },
        { id: "motivo", rotulo: "Motivo", tipo: "select", obrigatorio: true, opcoes: API.MOTIVOS_PARALISACAO, valor: p ? p.motivo : "" },
        { id: "responsabilidade", rotulo: "Responsabilidade", tipo: "select", obrigatorio: true, opcoes: API.RESPONSABILIDADES, valor: p ? p.responsabilidade : "" },
        { id: "previa", rotulo: "", tipo: "info", html: "" },
        { id: "descricao", rotulo: "Descrição", tipo: "textarea", max: 300, linhas: 2, valor: p ? p.descricao : "" }
      ],
      aoMudar: function (v, ctx) {
        var h = R.duracaoHoras(v.inicio, v.termino);
        var txt = h == null || !v.quantidade ? "" : "<span>Total: <b>" + F.num(h * v.quantidade, 1) + " " + (v.tipo === "Efetivo" ? "Hhora" : "Mhora") + "</b> (" + F.num(h, 2) + " h x " + F.num(v.quantidade) + ")</span>";
        var ext = API.RESP_EXTERNA.indexOf(v.responsabilidade) >= 0;
        ctx.info("previa", (txt ? '<div class="cluster text-small">' + txt + "</div>" : "") +
          (ext ? '<div class="alert alert--warning mt-2">' + U.icone("alertTriangle") + '<div class="alert__body">Tempo potencialmente excusável' + (v.responsabilidade === "Cliente" ? " e compensável" : "") +
            ": notifique formalmente dentro do prazo contratual e avalie o pleito em Contratos (03).</div></div>" : ""));
      },
      aoSalvar: function (v) {
        return API.salvarParalisacao(Object.assign({}, v, { id: p ? p.id : null, projetoId: p ? p.projetoId : projetoId })).then(function () { GI.ui.toast(p ? "Paralisação atualizada." : "Paralisação registrada.", "success"); recarregar(); });
      }
    });
  }

  /* ======================================================================
     Aba KPIs de performance
     ====================================================================== */
  function carregarKpis() {
    return API.kpis(projetoId, estado.corte).then(function (d) { kpis = d; renderKpis(); });
  }
  function blocoSelecionado() {
    if (!estado.empresaId) return kpis.geral;
    return kpis.porEmpresa.filter(function (b) { return b.empresaId === Number(estado.empresaId); })[0] || kpis.geral;
  }
  function renderKpis() {
    var j = kpis.janela, b = blocoSelecionado(), q = b.quantidades, c = b.capacidade, a = b.amostragem, p = b.paralisacoes;
    document.getElementById("janela").textContent = "Janela de avaliação: " + semCurta(j.semanas[0]) + " a " + semCurta(j.semanas[j.semanas.length - 1]) + " (" + F.data(j.de) + " a " + F.data(j.ate) + ") · " +
      "quantidades acumuladas até o corte " + semCurta(kpis.corte);
    document.getElementById("t-perf").textContent = estado.empresaId ? "Performance: " + nomeEmpresa() : "Performance geral";
    document.getElementById("kpis-perf").innerHTML = [
      U.kpi({ rotulo: "Avanço por quantidades", valor: q.pctReal == null ? "·" : F.num(q.pctReal, 1), unidade: q.pctReal == null ? "" : "%", icone: "trendingUp", cor: corFaixa(b.faixas.spi),
        esperado: { rotulo: "Previsto", valor: pctTxt(q.pctPrev) }, rodape: "em horas ganhas" }),
      U.kpi({ rotulo: "SPI de quantidades", valor: indice(q.spi), icone: "curve", cor: corFaixa(b.faixas.spi), esperado: { rotulo: "Meta", valor: "≥ " + indice(spiFx()[1]) }, rodape: "horas ganhas ÷ previstas na LB" }),
      U.kpi({ rotulo: "Aderência (" + PAR.semanasMedia + " semanas)", valor: q.aderenciaJan == null ? "·" : F.num(q.aderenciaJan, 1), unidade: q.aderenciaJan == null ? "" : "%", icone: "target", cor: corFaixa(b.faixas.aderencia), esperado: { rotulo: "Meta", valor: "≥ " + F.pct(PAR.aderenciaFaixas[1], 0) },
        rodape: "semana de corte: " + pctTxt(q.aderenciaSem, 0) }),
      U.kpi({ rotulo: "Fator de produtividade", valor: indice(q.pfJan), icone: "gauge", cor: corFaixa(b.faixas.pf), esperado: { rotulo: "Meta", valor: "≤ " + indice(PAR.pfFaixas[0]) }, rodape: "acumulado " + indice(q.pf) + " · " + F.num(1, 2) + " = orçado" }),
      U.kpi({ rotulo: "Tendência de atraso", valor: F.num(q.tendenciaAtraso), icone: "alertTriangle", cor: q.tendenciaAtraso ? "danger" : "success", esperado: { rotulo: "Esperado", valor: F.num(0) },
        rodape: U.plural(q.pendentes, "apontamento pendente", "apontamentos pendentes") + (b.itensSemLb ? " · " + U.plural(b.itensSemLb, "item sem LB aprovada", "itens sem LB aprovada") : "") })
    ].join("");
    document.getElementById("kpis-perf-campo").innerHTML = [
      U.kpi({ rotulo: "Capacidade produtiva", valor: horasDec(c.cp), unidade: c.cp == null ? "" : "h/dia", icone: "clock", cor: corFaixa(b.faixas.utilizacao),
        esperado: { rotulo: "Meta", valor: "≥ " + F.num(metaCp(), 2) + " h" }, rodape: "utilização " + pctTxt(c.utilizacao) + " · meta " + F.pct(PAR.metaUtilizacaoPct, 0) }),
      U.kpi({ rotulo: "Pessoas trabalhando", valor: a.pctTrabalhando == null ? "·" : F.num(a.pctTrabalhando, 1), unidade: a.pctTrabalhando == null ? "" : "%", icone: "hardHat", cor: corFaixa(b.faixas.trabalhando),
        esperado: { rotulo: "Meta", valor: "≥ " + F.pct(PAR.metaTrabalhandoPct, 0) }, rodape: "parado " + pctTxt(a.pctParado) }),
      U.kpi({ rotulo: "Efetivo paralisado", valor: F.num(p.hhora, 1), unidade: "Hhora", icone: "users", cor: p.hhora ? "warning" : "success", esperado: { rotulo: "Esperado", valor: F.num(0) },
        rodape: pctTxt(b.pctHhoraParalisada, 2) + " das HH disponíveis · cliente " + F.num(p.hhoraCliente, 1) }),
      U.kpi({ rotulo: "Máquinas e equipamentos parados", valor: F.num(p.mhora, 1), unidade: "Mhora", icone: "truck", cor: p.mhora ? "warning" : "success", esperado: { rotulo: "Esperado", valor: F.num(0) }, rodape: U.plural(p.eventos, "evento", "eventos") + " de paralisação" }),
      U.kpi({ rotulo: "HH improdutivas na frente", valor: F.num(c.hhImprodutivas || 0), icone: "alertTriangle", cor: c.hhImprodutivas ? "warning" : "success",
        esperado: { rotulo: "Esperado", valor: F.num(0) }, rodape: "(jornada − CP) x efetivo" })
    ].join("");
    tb.empresas.atualizar(kpis.porEmpresa);

    var labels = kpis.porEmpresa[0] ? kpis.porEmpresa[0].tendencia.map(function (t) { return semCurta(t.semana); }) : [];
    function series(campo) {
      return kpis.porEmpresa.map(function (e, k) { return { label: U.empresa(e.empresaId), color: CORES[k % CORES.length], data: e.tendencia.map(function (t) { return t[campo]; }) }; });
    }
    function ref(valor, rot) { return { label: rot, color: "chart-baseline", dashed: true, points: false, data: labels.map(function () { return valor; }) }; }
    GI.charts.line("g-pf", { labels: labels, casas: 2, ariaLabel: "Fator de produtividade por semana e empresa", series: series("pf").concat([ref(1, "Orçado (" + F.num(1, 2) + ")")]) });
    GI.charts.line("g-ader", { labels: labels, percent: true, max: 100, ariaLabel: "Aderência semanal por empresa", series: series("aderencia").concat([ref(PAR.aderenciaFaixas[1], "Meta")]) });
    GI.charts.line("g-trab", { labels: labels, percent: true, max: 100, ariaLabel: "Pessoas trabalhando por semana e empresa", series: series("pctTrabalhando").concat([ref(PAR.metaTrabalhandoPct, "Meta")]) });
    GI.charts.line("g-cp", { labels: labels, casas: 2, ariaLabel: "Capacidade produtiva por semana e empresa",
      series: series("cp").concat([ref(Math.round(PAR.jornadaDiariaHoras * PAR.metaUtilizacaoPct) / 100, "Meta")]) });

    document.getElementById("definicoes").innerHTML = [
      ["Horas ganhas (HG)", "Quantidade realizada x índice orçado (HH por unidade). Permite somar cabos, concreto, aço, tubulação e painéis na mesma base."],
      ["Avanço por quantidades", "HG acumuladas ÷ HH orçadas do total da LB. Previsto: quantidade prevista acumulada na LB x índice ÷ HH orçadas."],
      ["SPI de quantidades", "Horas ganhas ÷ horas previstas na LB até a semana de corte (" + F.num(1, 2) + " = no plano; abaixo = atrasado)."],
      ["Aderência semanal", "Realizado ÷ previsto da LB na semana, limitado a 100% por item e ponderado pelas HH orçadas; faixas " + F.num(PAR.aderenciaFaixas[0]) + "% e " + F.num(PAR.aderenciaFaixas[1]) + "%."],
      ["Fator de produtividade (FP)", "HH apropriadas pela contratada ÷ horas ganhas. " + F.num(1, 2) + " = índice da proposta; acima de " + F.num(PAR.pfFaixas[0], 2) + " consome mais HH que o orçado; alerta acima de " + F.num(PAR.pfFaixas[1], 2) + "."],
      ["Tendência de término", "Prazo agregado (earned schedule): semanas da LB equivalentes ao realizado ÷ semanas decorridas = SPI(t); duração prevista = duração da LB ÷ SPI(t)."],
      ["Capacidade produtiva (CP)", "Horas de execução por dia na frente: (término − início) da manhã + (término − início) da tarde. Utilização = CP ÷ jornada de " + F.num(PAR.jornadaDiariaHoras, 1) + " h."],
      ["Amostragem do trabalho", "Rodadas de observação instantânea: % de pessoas trabalhando, em trânsito e paradas (com motivo). Meta de " + F.num(PAR.metaTrabalhandoPct) + "% trabalhando."],
      ["Hhora e Mhora", "Efetivo paralisado (pessoas x horas) e máquinas ou equipamentos parados (unidades x horas). Responsabilidade do cliente, da gerenciadora ou de terceiros é tempo potencialmente excusável (pleito no 03)."]
    ].map(function (d) { return "<dt>" + U.esc(d[0]) + "</dt><dd>" + U.esc(d[1]) + "</dd>"; }).join("");
  }
  function criarTabelaEmpresas() {
    tb.empresas = GI.tabela.criar("tb-empresas", {
      porPagina: 0, ordem: { coluna: "empresa", direcao: "asc" }, vazio: "Nenhuma empresa com dados de produtividade.", legenda: "Performance por empresa",
      colunas: [
        { id: "empresa", titulo: "Empresa", fixa: true, valor: function (b) { return U.empresa(b.empresaId); } },
        { id: "avanco", titulo: "Avanço real x prev.", tipo: "pct", valor: function (b) { return b.quantidades.pctReal; },
          html: function (b) { return '<div class="cell-duo"><b>' + pctTxt(b.quantidades.pctReal) + "</b><small>" + pctTxt(b.quantidades.pctPrev) + "</small></div>"; },
          exportar: function (b) { return pctTxt(b.quantidades.pctReal) + " / " + pctTxt(b.quantidades.pctPrev); } },
        { id: "spi", titulo: "SPI", tipo: "num", casas: 2, valor: function (b) { return b.quantidades.spi; }, html: function (b) { return b.quantidades.spi == null ? "·" : selo(indice(b.quantidades.spi), b.faixas.spi); } },
        { id: "aderencia", titulo: "Aderência", tipo: "pct", casas: 0, valor: function (b) { return b.quantidades.aderenciaJan; },
          html: function (b) { return b.quantidades.aderenciaJan == null ? "·" : selo(F.pct(b.quantidades.aderenciaJan, 0), b.faixas.aderencia); } },
        { id: "pf", titulo: "FP", tipo: "num", casas: 2, valor: function (b) { return b.quantidades.pfJan; }, html: function (b) { return b.quantidades.pfJan == null ? "·" : selo(indice(b.quantidades.pfJan), b.faixas.pf); } },
        { id: "cp", titulo: "CP (h/dia)", tipo: "num", casas: 2, valor: function (b) { return b.capacidade.cp; },
          html: function (b) { return b.capacidade.cp == null ? "·" : selo(F.num(b.capacidade.cp, 2), b.faixas.utilizacao); } },
        { id: "trab", titulo: "% trabalhando", tipo: "pct", casas: 1, valor: function (b) { return b.amostragem.pctTrabalhando; },
          html: function (b) { return b.amostragem.pctTrabalhando == null ? "·" : selo(pctTxt(b.amostragem.pctTrabalhando), b.faixas.trabalhando); } },
        { id: "hhora", titulo: "Hhora parada", tipo: "num", casas: 1, valor: function (b) { return b.paralisacoes.hhora; } },
        { id: "mhora", titulo: "Mhora parada", tipo: "num", casas: 1, valor: function (b) { return b.paralisacoes.mhora; }, oculta: true },
        { id: "situacao", titulo: "Situação", valor: function (b) { return b.alertas.length ? "Alerta" : b.atencao.length ? "Atenção" : "No plano"; },
          html: function (b) {
            return b.alertas.length ? U.badge(U.plural(b.alertas.length, "alerta"), "danger", true) : b.atencao.length ? U.badge(U.plural(b.atencao.length, "ponto de atenção", "pontos de atenção"), "warning", true) : U.badge("No plano", "success", true);
          } }
      ],
      classeLinha: function (b) { return String(b.empresaId) === String(estado.empresaId) ? "is-selected" : ""; },
      acoes: function (b) {
        if (b.acaoAberta) return '<a class="btn btn--ghost btn--icon btn--sm" href="' + U.tela("central-acoes", "acoes", { busca: b.acaoAberta.ref }) + '" aria-label="Ver ação na Central" title="Ver ação na Central">' + U.icone("actions") + "</a>";
        if (!b.alertas.length && !b.atencao.length) return "";
        return '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-plano="' + b.empresaId + '" aria-label="Criar plano de ação" title="Criar plano de ação">' + U.icone("plus") + "</button>";
      }
    });
  }
  function formPlano(empresaId) {
    var b = kpis.porEmpresa.filter(function (x) { return x.empresaId === empresaId; })[0];
    if (!b) return;
    /* Texto sugerido já no idioma da tela (vira dado do usuário ao salvar) */
    var T = function (x) { return GI.t ? GI.t(x) : x; };
    var nomes = { aderencia: T("aderência") + " " + pctTxt(b.quantidades.aderenciaJan, 0), pf: T("fator de produtividade") + " " + indice(b.quantidades.pfJan), spi: "SPI " + indice(b.quantidades.spi),
      trabalhando: T("pessoas trabalhando") + " " + pctTxt(b.amostragem.pctTrabalhando), utilizacao: T("utilização da jornada") + " " + pctTxt(b.capacidade.utilizacao) };
    var pontos = b.alertas.concat(b.atencao).map(function (k) { return nomes[k]; });
    var pessoas = Object.keys(U.mapas.pessoas).map(function (k) { return { valor: k, texto: U.mapas.pessoas[k].nome }; });
    var resp = Object.keys(U.mapas.pessoas).filter(function (k) { return U.mapas.pessoas[k].empresaId === empresaId; })[0] || "";
    var prev = new Date(GI.api.referencia() + "T12:00:00Z"); prev.setUTCDate(prev.getUTCDate() + 14);
    GI.form.abrir({
      titulo: "Plano de ação de produtividade", subtitulo: U.empresa(empresaId) + " · corte " + semCurta(kpis.corte) + " · vai para a Central de Ações (origem Produtividade)", tamanho: "lg",
      campos: [
        { id: "assunto", rotulo: "Ação", tipo: "texto", obrigatorio: true, max: 150, largura: "full", valor: T("Recuperar a produtividade") + ": " + U.empresa(empresaId) + " (" + semCurta(kpis.corte) + ")" },
        { id: "descricao", rotulo: "Descrição", tipo: "textarea", max: 600, linhas: 3,
          valor: T("Indicadores fora da faixa na janela de avaliação") + " (" + PAR.semanasMedia + "): " + pontos.join("; ") + ". " + T("Causas principais e contramedidas a definir com a contratada.") },
        { id: "responsavelId", rotulo: "Responsável", tipo: "select", obrigatorio: true, opcoes: pessoas, valor: resp },
        { id: "prevista", rotulo: "Data prevista", tipo: "data", obrigatorio: true, valor: prev.toISOString().slice(0, 10), min: GI.api.referencia() }
      ],
      aoSalvar: function (v) {
        return API.gerarAcao(projetoId, empresaId, kpis.corte, v).then(function (a) {
          GI.ui.toast("Ação criada na Central (" + a.origemRef + ").", "success"); carregarKpis();
        });
      }
    });
  }

  /* ======================================================================
     Carga, eventos e exportação
     ====================================================================== */
  function recarregar() {
    var ps = [carregarQtd()];
    if (estado.aba === "horas" || horas) ps.push(carregarHoras());
    if (estado.aba === "kpis" || kpis) ps.push(carregarKpis());
    return Promise.all(ps);
  }
  function renderAba() {
    if (estado.aba === "horas" && !horas) carregarHoras();
    else if (estado.aba === "horas") renderHoras();
    if (estado.aba === "kpis" && !kpis) carregarKpis();
    else if (estado.aba === "kpis") renderKpis();
    if (estado.aba === "qtd" && qtd) renderQtd();
  }

  document.getElementById("f-empresa").addEventListener("change", function (ev) {
    estado.empresaId = ev.target.value; estado.encarregado = "";
    horas = null; carregarQtd().then(function () { renderAba(); });
  });
  document.getElementById("f-corte").addEventListener("change", function (ev) {
    estado.corte = ev.target.value; horas = null; kpis = null;
    carregarQtd().then(function () { renderAba(); });
  });
  document.getElementById("f-grupo").addEventListener("change", function (ev) { estado.grupo = ev.target.value; carregarQtd(); });
  document.getElementById("f-area").addEventListener("change", function (ev) { estado.area = ev.target.value; carregarHoras(); });
  document.getElementById("f-encarregado").addEventListener("change", function (ev) { estado.encarregado = ev.target.value; carregarHoras(); });
  document.getElementById("f-periodo").addEventListener("change", function (ev) { estado.periodo = ev.target.value; carregarHoras(); });
  document.getElementById("f-visao").addEventListener("segmented:change", function (ev) { estado.visao = ev.detail.value; renderHoras(); });
  document.addEventListener("tabs:change", function (ev) {
    var aba = Object.keys(ABAS).filter(function (k) { return ABAS[k] === ev.detail.id; })[0];
    if (!aba) return;
    estado.aba = aba;
    if (qtd) renderAba();
  });
  /* Portfólio: consulta consolidada; cadastros, apontamentos e planos de ação pedem o projeto */
  var ACOES_PRD = { apontar: formApontar, item: function () { formItem(null); }, importar: importar, jornada: function () { formJornada(null); },
    amostra: function () { formAmostragem(null); }, paralisacao: function () { formParalisacao(null); } };
  function acaoPrd(nome, titulo) { return function () { if (projetoId == null) U.noProjeto(nome, titulo, { aba: estado.aba }); else ACOES_PRD[nome](); }; }
  document.getElementById("btn-apontar").addEventListener("click", acaoPrd("apontar", "Apontar semana"));
  document.getElementById("btn-novo-item").addEventListener("click", acaoPrd("item", "Novo item de quantidade"));
  document.getElementById("btn-importar").addEventListener("click", acaoPrd("importar", "Importar itens de quantidade"));
  document.getElementById("btn-jornada").addEventListener("click", acaoPrd("jornada", "Registrar jornada"));
  document.getElementById("btn-amostra").addEventListener("click", acaoPrd("amostra", "Registrar amostragem"));
  document.getElementById("btn-paralisacao").addEventListener("click", acaoPrd("paralisacao", "Registrar paralisação"));
  document.getElementById("tb-itens").addEventListener("click", function (ev) { var b = ev.target.closest("[data-item]"); if (b) abrirItem(b.getAttribute("data-item")); });
  document.getElementById("tb-jornadas").addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-jornada]"); if (!b) return;
    var j = horas.jornadas.filter(function (x) { return String(x.id) === b.getAttribute("data-jornada"); })[0]; if (j) formJornada(j);
  });
  document.getElementById("tb-amostras").addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-amostra]"); if (!b) return;
    var a = horas.amostras.filter(function (x) { return String(x.id) === b.getAttribute("data-amostra"); })[0]; if (a) formAmostragem(a);
  });
  document.getElementById("tb-paral").addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-paral]"); if (!b) return;
    var p = horas.paralisacoes.filter(function (x) { return String(x.id) === b.getAttribute("data-paral"); })[0]; if (p) formParalisacao(p);
  });
  document.getElementById("tb-empresas").addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-plano]");
    if (!b) return;
    if (projetoId == null) { U.noProjeto(null, "Plano de ação de produtividade", { aba: "kpis" }); return; }
    formPlano(Number(b.getAttribute("data-plano")));
  });

  function kpisDe(id) {
    return Array.prototype.map.call(document.querySelectorAll("#" + id + " .kpi"), function (k) {
      return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" };
    });
  }
  GI.exportar.registrar(function () {
    var filtro = (estado.empresaId ? nomeEmpresa() : "Todas as empresas") + " · corte " + rotuloSemana(estado.corte);
    if (estado.aba === "horas") {
      var nomesV = { cp: "Capacidade produtiva", amostragem: "Amostragem do trabalho", paralisacoes: "Paralisações" };
      var blocos = estado.visao === "cp" ? [{ tipo: "kpis", titulo: "Indicadores", itens: kpisDe("kpis-cp") }, { tipo: "grafico", titulo: "Capacidade produtiva por área", canvas: document.getElementById("g-cp-area") },
        { tipo: "grafico", titulo: "Capacidade produtiva por dia", canvas: document.getElementById("g-cp-dia") }, { tipo: "tabela", titulo: "Registros de jornada", dados: tb.jornadas.exportacao() }]
        : estado.visao === "amostragem" ? [{ tipo: "kpis", titulo: "Indicadores", itens: kpisDe("kpis-amostra") }, { tipo: "grafico", titulo: "Distribuição por dia", canvas: document.getElementById("g-amostra-dia") },
          { tipo: "tabela", titulo: "Por empresa e encarregado", dados: tb.amostraEmp.exportacao() }, { tipo: "tabela", titulo: "Rodadas de observação", dados: tb.amostras.exportacao() }]
        : [{ tipo: "kpis", titulo: "Indicadores", itens: kpisDe("kpis-par") }, { tipo: "tabela", titulo: "Por área", dados: tb.parArea.exportacao() }, { tipo: "tabela", titulo: "Registros de paralisação", dados: tb.paral.exportacao() }];
      return { titulo: "Produtividade: horas efetivas (" + nomesV[estado.visao] + ")", subtitulo: filtro + " · " + document.getElementById("periodo-horas").textContent, arquivo: "produtividade-horas-" + estado.visao, blocos: blocos };
    }
    if (estado.aba === "kpis") {
      return { titulo: "Produtividade: KPIs de performance", subtitulo: filtro + " · " + document.getElementById("janela").textContent, arquivo: "produtividade-kpis-" + estado.corte, orientacao: "paisagem",
        blocos: [{ tipo: "kpis", titulo: document.getElementById("t-perf").textContent, itens: kpisDe("kpis-perf").concat(kpisDe("kpis-perf-campo")) },
          { tipo: "tabela", titulo: "Performance por empresa", dados: tb.empresas.exportacao() },
          { tipo: "grafico", titulo: "Fator de produtividade por semana", canvas: document.getElementById("g-pf") },
          { tipo: "grafico", titulo: "Aderência semanal", canvas: document.getElementById("g-ader") },
          { tipo: "grafico", titulo: "Pessoas trabalhando por semana", canvas: document.getElementById("g-trab") },
          { tipo: "grafico", titulo: "Capacidade produtiva por semana", canvas: document.getElementById("g-cp") }] };
    }
    return { titulo: "Produtividade: quantidades da linha de base", subtitulo: filtro + (estado.grupo ? " · " + estado.grupo : ""), arquivo: "produtividade-quantidades-" + estado.corte, orientacao: "paisagem",
      blocos: [{ tipo: "kpis", titulo: "Indicadores", itens: kpisDe("kpis-qtd") }, { tipo: "kpis", titulo: "Quantidades por grupo", itens: kpisDe("grupos") },
        { tipo: "tabela", titulo: "Plano x realizado por item", dados: tb.itens.exportacao() },
        { tipo: "grafico", titulo: "Produção semanal", canvas: document.getElementById("g-semanal") }, { tipo: "grafico", titulo: "Avanço acumulado", canvas: document.getElementById("g-acum") }] };
  });

  GI.util.pronto().then(function () {
    criarTabelaItens(); criarTabelasHoras(); criarTabelaParArea(); criarTabelaEmpresas();
    return API.kpis(projetoId, estado.corte).then(function (k) {
      kpis = k;
      empresasComDados = k.porEmpresa.map(function (b) { return b.empresaId; });
      if (estado.empresaId && empresasComDados.indexOf(Number(estado.empresaId)) < 0) estado.empresaId = "";
      return carregarQtd();
    }).then(function () {
      if (qtd.semanasCorte.indexOf(estado.corte) < 0) { estado.corte = ATUAL; return carregarQtd(); }
    }).then(function () {
      montarFiltrosGlobais();
      if (estado.aba !== "qtd") GI.ui.selecionarAba(document.getElementById("aba-" + estado.aba));
      renderAba();
      var ac = U.acaoPendente();
      if (ac && projetoId != null && ACOES_PRD[ac]) ACOES_PRD[ac]();
    });
  });
})(window.GI = window.GI || {});
