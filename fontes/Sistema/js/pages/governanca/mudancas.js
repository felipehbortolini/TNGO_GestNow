/* ==========================================================================
   Governança > Gestão de mudanças (08): abas Registro e Painel.
   Controle integrado de mudanças: Registrada -> Em análise de impacto ->
   Aguardando comitê -> Aprovada / Aprovada com condições / Rejeitada / Adiada ->
   Em implementação -> Encerrada (ou Cancelada). ?situacao=&busca=&projeto=
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt, G = GI.gov, API = GI.api.governanca;
  var projetoId, tabela, filtro = {}, aba = "registro", painel = null, lista = [], carteira = null;   /* carteira: resumo de todos os projetos (referência dos cards) */
  var ROTULOS = {
    tipo: { nome: "Tipo" }, origem: { nome: "Origem" }, prioridade: { nome: "Prioridade" }, alcada: { nome: "Alçada" }
  };
  var SIT_GRUPOS = [{ valor: "abertas", texto: "Situação: em aberto" }, { valor: "em-analise", texto: "Situação: em análise" }, { valor: "aprovadas", texto: "Situação: aprovadas" }];

  function kpis(r) {
    var c = carteira || r, proj = GI.api.portfolio.projeto(projetoId);
    function k(o, valor) { o.filtro = { valor: valor, ativo: filtro.situacao === valor }; return U.kpi(o); }
    document.getElementById("kpis").innerHTML = [
      k({ rotulo: "Em análise", valor: F.num(r.emAnalise), icone: "fileSearch", cor: r.analiseVencida ? "danger" : "info", esperado: { rotulo: "Referência", valor: F.num(r.total) },
        rodape: r.analiseVencida ? U.plural(r.analiseVencida, "análise vencida", "análises vencidas") : "registradas e em análise de impacto" }, "em-analise"),
      k({ rotulo: "Aguardando comitê", valor: F.num(r.aguardandoComite), icone: "gavel", cor: r.aguardandoComite ? "warning" : "success", esperado: { rotulo: "Referência", valor: F.num(r.total) },
        rodape: r.adiadas ? U.plural(r.adiadas, "adiada", "adiadas") : "decisão pendente" }, "Aguardando comitê"),
      k({ rotulo: "Aprovadas em " + r.ano, valor: F.num(r.aprovadasAno), icone: "checkCircle", cor: "success", esperado: { rotulo: "Referência", valor: F.num(r.aprovadas) },
        rodape: r.emImplementacao ? U.plural(r.emImplementacao, "em implementação", "em implementação") : "nenhuma em implementação" }, "aprovadas"),
      U.kpi({ rotulo: "Valor aprovado acumulado", moeda: r.valorAprovadoCentavos, icone: "money", cor: "primary", esperado: { rotulo: "Orçado", valor: proj && proj.orcamentoCentavos ? F.moedaCompacta(proj.orcamentoCentavos) : "·" },
        rodape: F.pct(r.valorAprovadoPct) + " do orçamento" + (r.smsNaoIncorporadas ? " · " + U.plural(r.smsNaoIncorporadas, "SM não incorporada", "SMs não incorporadas") + " à EAC" : "") }),
      U.kpi({ rotulo: "Impacto de prazo acumulado", valor: (r.prazoAprovadoDias > 0 ? "+" : "") + F.num(r.prazoAprovadoDias), unidade: "dias", icone: "calendarClock", cor: r.prazoAprovadoDias > 0 ? "warning" : "success", esperado: { rotulo: "Esperado", valor: "0" },
        rodape: "no caminho crítico, mudanças aprovadas" }),
      U.kpi({ rotulo: "Tempo médio de decisão", valor: r.tempoMedioDecisaoDias == null ? "·" : F.num(r.tempoMedioDecisaoDias), unidade: r.tempoMedioDecisaoDias == null ? "" : "dias", icone: "clock", cor: "info",
        esperado: { rotulo: "Referência", valor: c.tempoMedioDecisaoDias == null ? "·" : F.num(c.tempoMedioDecisaoDias) },
        rodape: "da solicitação à decisão" + (r.emergenciaisPendentes ? " · " + U.plural(r.emergenciaisPendentes, "emergencial sem ratificação", "emergenciais sem ratificação") : "") })
    ].join("");
  }

  function montarTabela() {
    tabela = GI.tabela.criar("tabela", {
      porPagina: 20, compacta: true, legenda: "Solicitações de mudança", vazio: "Nenhuma solicitação encontrada.", ordem: { coluna: "codigo", direcao: "desc" },
      colunas: (projetoId == null ? [U.colunaProjeto()] : []).concat([
        { id: "codigo", titulo: "Nº", classe: "nowrap", valor: function (s) { return s.codigo; },
          html: function (s) { return '<a href="' + U.tela("governanca", "mudanca", { codigo: s.codigo }) + '">' + U.esc(s.codigo) + "</a>"; } },
        { id: "titulo", titulo: "Título", valor: function (s) { return s.titulo; },
          html: function (s) {
            return '<div class="cell-title"><b>' + U.esc(s.titulo) + "</b><small>" + U.esc(F.data(s.dataSolicitacao)) + "</small>" +
              (s.prioridade !== "Normal" ? "<span>" + G.prioridade(s.prioridade) + (s.emergenciaPendente ? " " + U.badge("Ratificação pendente", s.ratificacaoVencida ? "danger" : "warning") : "") + "</span>" : "") + "</div>";
          } },
        { id: "tipo", titulo: "Tipo · origem", valor: function (s) { return s.tipo; }, exportar: function (s) { return s.tipo + " · " + s.origem; },
          html: function (s) { return '<div class="cell-title"><span>' + U.esc(s.tipo) + "</span><small>" + U.esc(s.origem) + "</small></div>"; } },
        { id: "custo", titulo: "Custo", tipo: "moeda", classe: "num", valor: function (s) { return s.custoCentavos; }, html: function (s) { return G.custo(s.custoCentavos); } },
        { id: "prazo", titulo: "Prazo", tipo: "num", classe: "num", valor: function (s) { return s.prazoDias; }, html: function (s) { return G.prazo(s.prazoDias); } },
        { id: "situacao", titulo: "Situação", valor: function (s) { return s.situacao; },
          html: function (s) { return G.situacaoSm(s.situacao); } },
        { id: "proxima", titulo: "Próxima etapa", valor: function (s) { return s.proximaEtapa; },
          html: function (s) {
            if (!s.proximaEtapa) return '<span class="text-small text-muted">' + (s.encerramento ? "encerrada em " + F.data(s.encerramento) : "·") + "</span>";
            return '<span class="text-small' + (s.analiseVencida || s.acoesAtrasadas ? " valor--negativo" : "") + '">' + U.esc(s.proximaEtapa) + "</span>";
          } }
      ]),
      classeLinha: function (s) { return s.analiseVencida || s.ratificacaoVencida || s.acoesAtrasadas ? "is-alert" : ""; },
      acoes: function (s) {
        return '<a class="btn btn--ghost btn--icon btn--sm" href="' + U.tela("governanca", "mudanca", { codigo: s.codigo }) + '" title="Abrir ficha" aria-label="Abrir ficha">' + U.icone("arrowRight") + "</a>";
      }
    });
  }

  function situacoes() {
    var sel = document.getElementById("f-situacao");
    sel.innerHTML = '<option value="">Situação: todas</option>' + U.opcoes(SIT_GRUPOS) + U.opcoes(API.SITUACOES.map(function (s) { return { valor: s, texto: s }; }));
    sel.value = filtro.situacao || "";
  }
  function carregar() {
    var q = Object.assign({ projetoId: projetoId }, filtro);
    return Promise.all([API.mudancas(q), API.resumoMudancas(projetoId), API.painelMudancas(projetoId), projetoId == null ? null : API.resumoMudancas(null)]).then(function (r) {
      lista = r[0]; painel = r[2]; carteira = r[3] || r[1];
      kpis(r[1]);
      tabela.atualizar(lista, true);
      document.getElementById("contagem").textContent = U.plural(lista.length, "solicitação encontrada", "solicitações encontradas");
      document.getElementById("n-registro").textContent = lista.length;
      document.getElementById("f-situacao").value = filtro.situacao || "";
      G.chips(document.getElementById("chips"), filtro, ROTULOS, carregar);
      if (aba === "painel") renderPainel();
    });
  }

  /* ---------------- Painel ---------------- */
  function renderPainel() {
    var p = painel, r = p.resumo, c = carteira || r;
    document.getElementById("kpis-painel").innerHTML = [
      U.kpi({ rotulo: "Solicitações", valor: F.num(r.total), icone: "swap", cor: "primary", esperado: { rotulo: "Referência", valor: F.num(c.total) }, rodape: U.plural(r.aprovadas, "aprovada", "aprovadas") + " · " + U.plural(r.aguardandoComite, "aguardando comitê", "aguardando comitê") }),
      U.kpi({ rotulo: "Taxa de aprovação", valor: r.taxaAprovacaoPct == null ? "·" : F.num(r.taxaAprovacaoPct, 1), unidade: r.taxaAprovacaoPct == null ? "" : "%", icone: "checkCircle", cor: "success",
        esperado: { rotulo: "Referência", valor: c.taxaAprovacaoPct == null ? "·" : F.pct(c.taxaAprovacaoPct, 1) },
        rodape: "aprovadas sobre decididas (sem as adiadas)" }),
      U.kpi({ rotulo: "Tempo médio de decisão", valor: r.tempoMedioDecisaoDias == null ? "·" : F.num(r.tempoMedioDecisaoDias), unidade: r.tempoMedioDecisaoDias == null ? "" : "dias", icone: "clock", cor: "info",
        esperado: { rotulo: "Referência", valor: c.tempoMedioDecisaoDias == null ? "·" : F.num(c.tempoMedioDecisaoDias) } }),
      p.contingencia ? U.kpi({ rotulo: "Reserva de contingência consumida", moeda: p.contingencia.consumido, icone: "coins", cor: p.contingencia.saldo < 0 ? "danger" : "info",
        esperado: { rotulo: "Orçado", valor: F.moedaCompacta(p.contingencia.total) },
        rodape: "saldo " + F.moeda(p.contingencia.saldo) }) : ""
    ].join("");
    var sit = p.porSituacao;
    GI.charts.bar("g-situacao", { labels: sit.map(function (x) { return x.chave; }), horizontal: true, ariaLabel: "Mudanças por situação",
      series: [{ label: "Solicitações", data: sit.map(function (x) { return x.total; }), color: "chart-1" }] });
    var max = p.porOrigem.reduce(function (m, o) { return Math.max(m, o.total); }, 0) || 1;
    document.getElementById("pareto").innerHTML = p.porOrigem.length ? '<div class="table-wrap"><table class="table table--compact"><caption class="sr-only">Pareto das mudanças por origem</caption>' +
      '<thead><tr><th>Origem</th><th class="num">Qtd.</th><th>Participação</th><th class="num">%</th><th class="num">% acumulado</th></tr></thead><tbody>' +
      p.porOrigem.map(function (o) {
        return '<tr><td>' + U.esc(o.chave) + '</td><td class="num">' + F.num(o.total) + '</td><td><span class="pareto-barra" style="width:' + Math.max(4, Math.round(o.total / max * 120)) + 'px" aria-hidden="true"></span></td>' +
          '<td class="num">' + F.pct(o.pct) + '</td><td class="num"><b>' + F.pct(o.acumPct) + "</b></td></tr>";
      }).join("") + "</tbody></table></div>" : U.vazio("Sem solicitações no projeto.", "swap");
    var meses = p.mensal.map(function (m) { return U.mesCurto(m.mes); });
    GI.charts.line("g-valor", { labels: meses, money: true, ariaLabel: "Valor aprovado acumulado por mês",
      series: [{ label: "Valor aprovado acumulado", data: p.mensal.map(function (m) { return m.valorAcumulado; }), color: "chart-1", fill: true, tension: 0 }] });
    GI.charts.line("g-prazo", { labels: meses, ariaLabel: "Impacto de prazo acumulado por mês",
      series: [{ label: "Dias acumulados", data: p.mensal.map(function (m) { return m.prazoAcumulado; }), color: "chart-2", tension: 0 }] });
    GI.charts.bar("g-tipo", { labels: p.porTipo.map(function (x) { return x.chave; }), ariaLabel: "Mudanças por tipo",
      series: [{ label: "Solicitações", data: p.porTipo.map(function (x) { return x.total; }), color: "chart-3" }] });
  }

  /* ---------------- Eventos ---------------- */
  function montarFiltros() {
    filtro.situacao = U.param("situacao") || null;
    var busca = document.getElementById("busca");
    busca.value = U.param("busca") || "";
    filtro.busca = busca.value || null;
    busca.addEventListener("input", U.debounce(function () { filtro.busca = busca.value.trim() || null; carregar(); }, 250));
    situacoes();
    document.getElementById("f-situacao").addEventListener("change", function (ev) { filtro.situacao = ev.target.value || null; carregar(); });
    document.getElementById("btn-filtros").addEventListener("click", function () {
      G.filtros({ titulo: "Filtros de mudanças", filtro: filtro, aoAplicar: carregar, campos: [
        { id: "tipo", rotulo: "Tipo", opcoes: API.TIPOS.map(function (t) { return { valor: t, texto: t }; }) },
        { id: "origem", rotulo: "Origem", opcoes: API.ORIGENS.map(function (t) { return { valor: t, texto: t }; }) },
        { id: "prioridade", rotulo: "Prioridade", vazio: "Todas", opcoes: API.PRIORIDADES.map(function (t) { return { valor: t, texto: t }; }) },
        { id: "alcada", rotulo: "Alçada", vazio: "Todas", opcoes: API.ALCADAS.map(function (t) { return { valor: t, texto: t }; }) }
      ] });
    });
    document.getElementById("kpis").addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-filtro]");
      if (!b) return;
      var v = b.getAttribute("data-filtro");
      filtro.situacao = filtro.situacao === v ? null : v;
      carregar();
    });
  }
  document.getElementById("btn-nova").addEventListener("click", function () {
    G.novaMudanca(projetoId, function (codigo) { window.location.href = U.tela("governanca", "mudanca", { codigo: codigo }); });
  });
  document.getElementById("tabela").addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-sm-acao]");
    if (b) G.acaoSm(b.getAttribute("data-sm-acao"), b.getAttribute("data-codigo"), function () { carregar(); });
  });
  document.addEventListener("tabs:change", function (ev) {
    aba = ev.detail.id === "p-painel" ? "painel" : "registro";
    if (aba === "painel" && painel) renderPainel();
  });

  GI.exportar.registrar(function () {
    var proj = U.projeto(projetoId) || {};
    var sub = proj.codigo ? proj.codigo + " " + proj.nome : "Portfólio de projetos";
    if (aba === "painel") {
      return {
        titulo: "Painel de mudanças", subtitulo: sub, arquivo: "painel-de-mudancas",
        blocos: [
          { tipo: "kpis", titulo: "Indicadores", itens: Array.prototype.map.call(document.querySelectorAll("#kpis-painel .kpi"), function (k) {
            return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" }; }) },
          { tipo: "grafico", titulo: "Mudanças por situação", canvas: document.getElementById("g-situacao") },
          { tipo: "tabela", titulo: "Pareto por origem", dados: {
            colunas: [{ titulo: "Origem", tipo: "texto" }, { titulo: "Quantidade", tipo: "num" }, { titulo: "%", tipo: "pct" }, { titulo: "% acumulado", tipo: "pct" }],
            bruto: painel.porOrigem.map(function (o) { return [o.chave, o.total, o.pct, o.acumPct]; }),
            texto: painel.porOrigem.map(function (o) { return [o.chave, String(o.total), F.pct(o.pct), F.pct(o.acumPct)]; }) } },
          { tipo: "grafico", titulo: "Valor aprovado acumulado", canvas: document.getElementById("g-valor") },
          { tipo: "grafico", titulo: "Impacto de prazo acumulado", canvas: document.getElementById("g-prazo") },
          { tipo: "tabela", titulo: "Evolução mensal", dados: {
            colunas: [{ titulo: "Mês", tipo: "texto" }, { titulo: "Solicitadas", tipo: "num" }, { titulo: "Aprovadas", tipo: "num" }, { titulo: "Valor aprovado acumulado", tipo: "moeda" }, { titulo: "Prazo acumulado (dias)", tipo: "num" }],
            bruto: painel.mensal.map(function (m) { return [m.mes, m.solicitadas, m.aprovadas, m.valorAcumulado, m.prazoAcumulado]; }),
            texto: painel.mensal.map(function (m) { return [U.mesCurto(m.mes), String(m.solicitadas), String(m.aprovadas), F.moeda(m.valorAcumulado), String(m.prazoAcumulado)]; }) } }
        ]
      };
    }
    return {
      titulo: "Registro de mudanças", subtitulo: sub, arquivo: "registro-de-mudancas", orientacao: "l",
      blocos: [
        { tipo: "kpis", titulo: "Indicadores", itens: Array.prototype.map.call(document.querySelectorAll("#kpis .kpi"), function (k) {
          return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" }; }) },
        { tipo: "tabela", titulo: "Solicitações de mudança", dados: tabela.exportacao() }
      ]
    };
  });

  G.pronto().then(function () {
    projetoId = G.projeto(function (id) { projetoId = id; carregar(); });
    montarFiltros();
    montarTabela();
    return carregar().then(function () {
      if (projetoId != null && U.acaoPendente() === "nova") G.novaMudanca(projetoId, function (codigo) { window.location.href = U.tela("governanca", "mudanca", { codigo: codigo }); });
    });
  });
})(window.GI = window.GI || {});
