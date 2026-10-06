/* ==========================================================================
   Suprimentos > Painel
   Indicadores do README (aderência ao plano, ciclo, saving, competitividade,
   OTD, pedidos críticos, emergenciais e comprometido x orçado), curva de
   contratação, avanço físico de suprimentos (do MAS), saving acumulado,
   pacotes por etapa e pedidos por folga em relação ao ROS.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt, S = GI.sup;
  var projetoId, ind = null, mapa = null, tabela, alerta = 7, propMin = 3, cicloLb = null;

  function render() {
    var i = ind, r = mapa.resumo;
    document.getElementById("kpis").innerHTML = [
      U.kpi({ rotulo: "Aderência ao plano de compras", valor: F.num(i.aderenciaPct, 1), unidade: "%", icone: "target", cor: i.aderenciaPct >= 90 ? "success" : "warning",
        esperado: { rotulo: "Meta", valor: "≥ " + F.pct(90, 0) }, rodape: F.num(i.adjudicadosAteRef) + " de " + F.num(i.planejadosAteRef) + " pacotes planejados até hoje", href: U.tela("suprimentos", "plano-compras", { projeto: projetoId }) }),
      U.kpi({ rotulo: "Ciclo de compra", valor: F.num(i.cicloMedioDias), unidade: "dias", icone: "clock", cor: "info",
        esperado: { rotulo: "Linha de base", valor: cicloLb == null ? "·" : F.num(cicloLb) + " dias" }, rodape: "média entre requisição e pedido emitido" }),
      U.kpi({ rotulo: "Saving sobre estimativa", moeda: i.savingCentavos, icone: "coins", cor: i.savingCentavos >= 0 ? "success" : "danger",
        esperado: { rotulo: "Meta", valor: "≥ " + F.moedaCompacta(0) }, rodape: F.pct(i.savingPct) + " da estimativa dos pacotes adjudicados" }),
      U.kpi({ rotulo: "Saving de negociação", moeda: i.savingNegociacaoCentavos, icone: "swap", cor: "success",
        esperado: { rotulo: "Meta", valor: "≥ " + F.moedaCompacta(0) }, rodape: F.pct(i.savingNegociacaoPct) + " sobre a primeira proposta vencedora" }),
      U.kpi({ rotulo: "Competitividade", valor: F.num(i.mediaPropostas, 1), unidade: "propostas", icone: "users", cor: i.mediaPropostas >= 3 ? "success" : "warning",
        esperado: { rotulo: "Meta", valor: "≥ " + F.num(propMin) }, rodape: "válidas por processo · fornecedor único " + F.pct(i.fornecedorUnicoPct), href: U.tela("suprimentos", "processos", { projeto: projetoId }) }),
      U.kpi({ rotulo: "Entrega no prazo (OTD)", valor: i.otdPct == null ? "" : F.num(i.otdPct, 1), unidade: i.otdPct == null ? "" : "%", icone: "truck", cor: i.otdPct >= 90 ? "success" : "warning",
        esperado: { rotulo: "Meta", valor: "≥ " + F.pct(90, 0) }, rodape: F.num(i.entregasNoPrazo) + " de " + F.num(i.entregas) + " entregas até a data contratual" }),
      U.kpi({ rotulo: "Pedidos críticos", valor: F.num(i.pedidosCriticos), icone: "alertTriangle", cor: i.pedidosCriticos ? "danger" : "success",
        esperado: { rotulo: "Esperado", valor: F.num(0) }, rodape: "folga negativa em relação ao ROS · " + F.num(i.lliCriticos) + " de longo prazo", href: U.tela("suprimentos", "diligenciamento", { projeto: projetoId }) }),
      U.kpi({ rotulo: "Compras emergenciais", valor: F.num(i.emergenciaisPct, 1), unidade: "%", icone: "octagonAlert", cor: i.emergenciaisPct ? "warning" : "success",
        esperado: { rotulo: "Esperado", valor: F.pct(0, 0) }, rodape: F.moedaCompacta(i.emergenciaisCentavos) + " do valor contratado" }),
      U.kpi({ rotulo: "Comprometido x orçado", valor: F.num(i.comprometidoOrcadoPct, 1), unidade: "%", icone: "money", cor: i.comprometidoOrcadoPct > 100 ? "danger" : "primary",
        esperado: [{ rotulo: "Limite", valor: F.pct(100, 0) }, { rotulo: "Orçado", valor: F.moedaCompacta(i.orcadoLigadoCentavos) }],
        rodape: F.moedaCompacta(i.adjudicadoCentavos) + " adjudicado nos itens da EAC" })
    ].join("");

    var cc = i.curvaContratacao;
    GI.charts.line("g-contratacao", {
      labels: cc.meses.map(U.mesCurto), ariaLabel: "Pacotes adjudicados acumulados por mês: plano x realizado",
      series: [
        { label: "Plano de compras", data: cc.planejado, color: "chart-baseline", dashed: true, points: false },
        { label: "Realizado", data: cc.realizado, color: "chart-real", fill: true }
      ]
    });
    var cv = mapa.curva;
    document.getElementById("sub-avanco").textContent = cv ? "Real " + F.pct(r.avancoReal) + " x previsto " + F.pct(r.avancoPrevisto) + " na LB · critério de medição do MAS, ponderado pelo valor" : "";
    if (cv) GI.charts.sCurve("g-avanco", { labels: cv.meses.map(U.mesCurto), baseline: cv.planejado, real: cv.real, forecast: cv.tendencia,
      ariaLabel: "Curva S de suprimentos: percentual acumulado previsto na linha de base, real e tendência" });
    var sm = i.savingMensal;
    GI.charts.line("g-saving", {
      labels: sm.meses.map(U.mesCurto), money: true, ariaLabel: "Saving acumulado por mês de adjudicação",
      series: [
        { label: "Sobre a estimativa", data: sm.acumulado, color: "chart-1" },
        { label: "Na negociação", data: sm.negociacao, color: "chart-3" }
      ]
    });
    var et = i.porEtapa.filter(function (e) { return e.total; });
    GI.charts.bar("g-etapas", { labels: et.map(function (e) { return e.etapa; }), horizontal: true, ariaLabel: "Quantidade de pacotes por etapa do processo de compra",
      series: [{ label: "Pacotes", data: et.map(function (e) { return e.total; }), color: "chart-4" }] });

    var linhas = mapa.linhas.filter(function (l) { return !l.servico && l.folgaDias != null; });
    document.getElementById("sub-folga").textContent = "Folga = ROS menos a previsão de entrega · alerta com " + F.num(alerta) + " dias ou menos · " +
      U.plural(i.pedidosCriticos, "pedido crítico", "pedidos críticos") + ", " + U.plural(i.pedidosAtencao, "em atenção", "em atenção");
    tabela.atualizar(linhas);
  }

  function carregar() {
    return Promise.all([GI.api.suprimentos.indicadores(projetoId), GI.api.suprimentos.mas(projetoId), GI.api.parametros(), GI.api.suprimentos.pacotes(projetoId)]).then(function (r) {
      ind = r[0]; mapa = r[1]; alerta = r[2].suprimentos.folgaAlertaDias; propMin = r[2].suprimentos.propostasMinimas;
      /* Ciclo planejado (LB) dos mesmos pacotes do ciclo realizado: requisição até o pedido */
      var lb = r[3].filter(function (p) { return p.adjudicadoCentavos != null && p.real && p.real.pedido && p.plano && p.plano.requisicao && p.plano.pedido; })
        .map(function (p) { return GI.regras.diasEntre(p.plano.requisicao, p.plano.pedido); });
      cicloLb = lb.length ? Math.round(lb.reduce(function (s, v) { return s + v; }, 0) / lb.length) : null;
      render();
    });
  }

  GI.exportar.registrar(function () {
    var p = U.projeto(projetoId);
    return {
      titulo: "Painel de suprimentos", subtitulo: p ? p.codigo + " " + p.nome : "Portfólio de projetos", arquivo: "painel-suprimentos-" + (p ? p.codigo : "portfolio"), orientacao: "l",
      blocos: [
        { tipo: "kpis", titulo: "Indicadores", itens: S.kpisExport() },
        { tipo: "grafico", titulo: "Curva de contratação", canvas: document.getElementById("g-contratacao") },
        { tipo: "grafico", titulo: "Avanço físico de suprimentos", canvas: document.getElementById("g-avanco") },
        { tipo: "grafico", titulo: "Saving acumulado", canvas: document.getElementById("g-saving") },
        { tipo: "grafico", titulo: "Pacotes por etapa", canvas: document.getElementById("g-etapas") },
        { tipo: "tabela", titulo: "Pedidos por folga", dados: tabela.exportacao() }
      ]
    };
  });

  GI.util.pronto().then(function () {
    projetoId = S.projeto(function (id) { projetoId = id; carregar(); });
    tabela = GI.tabela.criar("tabela", {
      porPagina: 10, legenda: "Pedidos por folga em relação ao ROS", vazio: "Nenhum pedido com data de entrega.", ordem: { coluna: "folgaDias", direcao: "asc" },
      colunas: (projetoId == null ? [U.colunaProjeto()] : []).concat([
        { id: "codigo", titulo: "Pacote", html: function (l) { return "<b>" + S.linkMas(l.codigo) + '</b><br><span class="text-small">' + (l.pedido ? S.linkPedido(l.pedido) : U.esc(l.etapa)) + "</span>"; } },
        { id: "escopo", titulo: "Escopo", html: function (l) { return '<div class="cell-title"><b>' + U.esc(l.escopo) + "</b><small>" + U.esc(l.fornecedor || "em contratação") + (l.lli ? " · LLI" : "") + "</small></div>"; } },
        { id: "proximo", titulo: "Próximo marco", valor: function (l) { return l.proximoMarco ? l.proximoMarco.nome : ""; },
          html: function (l) { return l.proximoMarco ? U.esc(l.proximoMarco.nome) + '<br><span class="text-small text-muted">' + U.esc(F.data(l.proximoMarco.data)) + "</span>" : U.esc(l.situacao); } },
        { id: "dataFolga", titulo: "Previsão de entrega", tipo: "data" },
        { id: "ros", titulo: "ROS", tipo: "data" },
        { id: "folgaDias", titulo: "Folga", tipo: "num", html: function (l) { return S.folga(l.folgaDias, l.faixaFolga); }, exportar: function (l) { return l.folgaDias; } },
        { id: "situacao", titulo: "Situação", html: function (l) { return S.situacao(l.situacao); } }
      ]),
      classeLinha: function (l) { return l.faixaFolga === "critico" ? "is-alert" : ""; }
    });
    return carregar();
  });
})(window.GI = window.GI || {});
