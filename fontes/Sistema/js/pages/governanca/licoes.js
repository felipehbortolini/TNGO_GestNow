/* ==========================================================================
   Governança > Lições aprendidas (08): abas Acervo e Painel.
   Acervo das lições do projeto (sistema de controle de um projeto); a
   aplicabilidade diz se a lição fica restrita ao projeto ou vai para a organização.
   Fluxo: Rascunho -> Em validação -> Validada -> Publicada. ?busca=&projeto=
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt, G = GI.gov, API = GI.api.governanca;
  var projetoId, filtro = {}, aba = "acervo", lista = [], painel = null, carteira = null, limite = 24;   /* carteira: painel do acervo de todos os projetos (referência dos cards) */
  var tSem = null, tReuso = null;
  var ROTULOS = {
    fase: { nome: "Fase" }, area: { nome: "Área" }, disciplina: { nome: "Disciplina" }, origemTipo: { nome: "Origem" },
    aplicabilidade: { nome: "Aplicabilidade" },
    projetoId: { nome: "Projeto", texto: function (v) { var p = U.projeto(v); return p ? p.codigo : v; } }
  };

  function cartao(l) {
    var h = G.linkOrigemLicao(l);
    return '<article class="licao-card licao-card--' + (l.tipo === "A repetir" ? "repetir" : "evitar") + '" aria-labelledby="lc-' + U.esc(l.codigo) + '">' +
      '<div class="licao-card__topo"><span class="licao-card__codigo">' + U.esc(l.codigo) + " · " + U.esc(l.projetoCodigo) + '</span><span class="licao-card__selos">' + G.tipoLicao(l.tipo) + G.situacaoLicao(l.situacao) + "</span></div>" +
      '<h3 class="licao-card__titulo" id="lc-' + U.esc(l.codigo) + '"><a href="#" data-lic-acao="ver" data-codigo="' + U.esc(l.codigo) + '">' + U.esc(l.titulo) + "</a></h3>" +
      '<p class="licao-card__rec">' + U.esc(l.recomendacao) + "</p>" +
      '<div class="licao-card__meta"><span>' + U.esc(l.fase) + "</span><span>" + U.esc(l.area) + "</span><span>" + U.esc(l.disciplina || "") + "</span>" +
      "<span>Aplicabilidade: " + U.esc(l.aplicabilidade) + "</span>" + (l.reusos ? "<span>" + U.esc(U.plural(l.reusos, "reuso")) + "</span>" : "") + "</div>" +
      '<div class="licao-card__meta"><span>Origem: ' + (h ? '<a href="' + h + '">' + U.esc(l.origemRef || l.origemTipo) + "</a>" : U.esc(l.origemTipo)) + "</span>" +
      (l.impactoPrazoDias || l.impactoCustoCentavos ? "<span>Impacto: " + U.esc(U.plural(l.impactoPrazoDias || 0, "dia") + " · " + F.moeda(l.impactoCustoCentavos || 0)) + "</span>" : "") + "</div>" +
      '<div class="licao-card__acoes">' + G.botoesLicao(l, true) +
      '<button type="button" class="btn btn--ghost btn--sm" data-lic-acao="ver" data-codigo="' + U.esc(l.codigo) + '">' + U.icone("eye") + "Ver</button></div></article>";
  }
  function renderAcervo() {
    var p = U.projeto(projetoId) || {};
    var proprias = lista.filter(function (l) { return l.projetoId === projetoId; }).length;
    var corp = lista.filter(function (l) { return l.aplicabilidade === "Corporativa"; }).length;
    if (projetoId == null) proprias = lista.filter(function (l) { return l.projetoId != null; }).length;
    document.getElementById("escopo").textContent = (projetoId == null ? "Acervo do portfólio: " : "Acervo do projeto " + (p.codigo || "") + ": ") + U.plural(proprias, "lição", "lições") + " (" +
      U.plural(corp, "corporativa", "corporativas") + ", compartilhadas com a organização).";
    var vis = lista.slice(0, limite);
    document.getElementById("cards").innerHTML = vis.length ? vis.map(cartao).join("") : U.vazio("Nenhuma lição encontrada com os filtros atuais.", "lightbulb");
    document.getElementById("mais").innerHTML = lista.length > limite ? '<button type="button" class="btn btn--secondary" id="btn-mais">' + U.icone("chevronDown") + "Mostrar mais (" + (lista.length - limite) + ")</button>" : "";
    document.getElementById("n-acervo").textContent = lista.length;
  }
  /* Checklist de kickoff: consulta ao acervo no início do projeto e de cada fase */
  function renderKickoff(pn) {
    var el = document.getElementById("kickoff");
    if (!pn) { el.innerHTML = ""; return; }
    el.innerHTML = '<section class="card mb-4" aria-labelledby="t-kick"><div class="card__header"><div><h2 class="card__title" id="t-kick">Consulta ao acervo no kickoff</h2>' +
      '<p class="card__subtitle">Recomendada no início do projeto e de cada fase: escolha a fase que começa para ver as lições publicadas.</p></div></div>' +
      '<div class="toolbar mb-0" role="group" aria-label="Filtrar lições publicadas por fase">' + pn.porFase.map(function (f) {
        var ativo = filtro.fase === f.chave && filtro.situacao === "Publicada";
        return '<button type="button" class="btn btn--sm ' + (ativo ? "btn--primary" : "btn--secondary") + '" data-fase="' + U.esc(f.chave) + '" aria-pressed="' + ativo + '">' + U.esc(f.chave) +
          ' <span class="tab__count">' + f.publicadas + "</span></button>";
      }).join("") + "</div></section>";
  }

  function carregar() {
    var q = Object.assign({ contextoProjetoId: projetoId }, filtro);
    return Promise.all([API.licoes(q), API.painelLicoes({ contextoProjetoId: projetoId }), projetoId == null ? null : API.painelLicoes({ contextoProjetoId: null })]).then(function (r) {
      lista = r[0]; painel = r[1]; carteira = r[2] || r[1];
      renderAcervo();
      renderKickoff(painel);
      document.getElementById("f-tipo").value = filtro.tipo || "";
      document.getElementById("f-situacao").value = filtro.situacao || "";
      G.chips(document.getElementById("chips"), filtro, ROTULOS, carregar);
      if (aba === "painel") renderPainel();
    });
  }

  /* ---------------- Painel ---------------- */
  function renderPainel() {
    var p = painel, c = carteira || painel;
    document.getElementById("kpis-painel").innerHTML = [
      U.kpi({ rotulo: "Lições no acervo", valor: F.num(p.total), icone: "lightbulb", cor: "primary", esperado: { rotulo: "Referência", valor: F.num(c.total) }, rodape: U.plural(p.aRepetir, "a repetir", "a repetir") + " · " + U.plural(p.aEvitar, "a evitar", "a evitar") }),
      U.kpi({ rotulo: "Publicadas nos últimos " + p.diasAlerta + " dias", valor: F.num(p.publicadasPeriodo), icone: "upload", cor: "success", esperado: { rotulo: "Meta", valor: "≥ " + F.num(1) }, rodape: U.plural(p.publicadas, "publicada no total", "publicadas no total") }),
      U.kpi({ rotulo: "Em validação", valor: F.num(p.emValidacao), icone: "clock", cor: p.emValidacao ? "warning" : "success", esperado: { rotulo: "Esperado", valor: "0" }, rodape: U.plural(p.emFluxo, "lição ainda não publicada", "lições ainda não publicadas") }),
      U.kpi({ rotulo: "Taxa de reuso", valor: p.taxaReusoPct == null ? "·" : F.num(p.taxaReusoPct, 1), unidade: p.taxaReusoPct == null ? "" : "%", icone: "refresh", cor: "info",
        esperado: { rotulo: "Referência", valor: c.taxaReusoPct == null ? "·" : F.pct(c.taxaReusoPct, 1) },
        rodape: "publicadas com aplicação registrada · " + U.plural(p.reusos, "reuso") }),
      U.kpi({ rotulo: "Dias desde a última lição", valor: p.diasSemRegistro == null ? "·" : F.num(p.diasSemRegistro), icone: "calendarClock", cor: p.semRegistroAlerta ? "warning" : "success",
        esperado: { rotulo: "Limite", valor: "≤ " + F.num(p.diasAlerta) } })
    ].join("");
    GI.charts.bar("g-fase", { labels: p.porFase.map(function (f) { return f.chave; }), horizontal: true, stacked: true, ariaLabel: "Lições por fase",
      series: [{ label: "A repetir", data: p.porFase.map(function (f) { return f.aRepetir; }), color: "chart-1" }, { label: "A evitar", data: p.porFase.map(function (f) { return f.aEvitar; }), color: "chart-2" }] });
    GI.charts.bar("g-area", { labels: p.porArea.map(function (a) { return a.chave; }), horizontal: true, stacked: true, ariaLabel: "Lições por área de conhecimento",
      series: [{ label: "A repetir", data: p.porArea.map(function (f) { return f.aRepetir; }), color: "chart-1" }, { label: "A evitar", data: p.porArea.map(function (f) { return f.aEvitar; }), color: "chart-2" }] });
    tSem.atualizar(p.porSituacao);
    tReuso.atualizar(p.maisReusadas);
  }
  function montarTabelasPainel() {
    tSem = GI.tabela.criar("t-situacao", {
      porPagina: 0, compacta: true, legenda: "Lições por situação", vazio: "Nenhuma lição registrada.", ordem: null,
      colunas: [
        { id: "chave", titulo: "Situação", valor: function (x) { return x.chave; }, html: function (x) { return G.situacaoLicao(x.chave); } },
        { id: "total", titulo: "Lições", tipo: "num", classe: "num", valor: function (x) { return x.total; } }
      ]
    });
    tReuso = GI.tabela.criar("t-reusadas", {
      porPagina: 0, compacta: true, legenda: "Lições mais reusadas", vazio: "Nenhuma aplicação registrada.",
      colunas: [
        { id: "codigo", titulo: "Lição", valor: function (l) { return l.codigo; },
          html: function (l) { return '<div class="cell-title"><a href="#" data-lic-acao="ver" data-codigo="' + U.esc(l.codigo) + '"><b>' + U.esc(l.codigo) + "</b></a><small>" + U.esc(l.titulo) + "</small></div>"; } },
        { id: "tipo", titulo: "Tipo", valor: function (l) { return l.tipo; }, html: function (l) { return G.tipoLicao(l.tipo); } },
        { id: "reusos", titulo: "Reusos", tipo: "num", classe: "num", valor: function (l) { return l.reusos; } }
      ]
    });
  }

  /* ---------------- Filtros e eventos ---------------- */
  function montarFiltros() {
    var busca = document.getElementById("busca");
    busca.value = U.param("busca") || "";
    filtro.busca = busca.value || null;
    busca.addEventListener("input", U.debounce(function () { filtro.busca = busca.value.trim() || null; limite = 24; carregar(); }, 250));
    var fTipo = document.getElementById("f-tipo");
    fTipo.innerHTML = '<option value="">Tipo: todos</option>' + U.opcoes(API.TIPOS_LICAO.map(function (t) { return { valor: t, texto: t }; }));
    fTipo.addEventListener("change", function () { filtro.tipo = fTipo.value || null; carregar(); });
    var fSit = document.getElementById("f-situacao");
    fSit.innerHTML = '<option value="">Situação: todas</option>' + U.opcoes(API.SITUACOES_LICAO.map(function (t) { return { valor: t, texto: t }; }));
    fSit.addEventListener("change", function () { filtro.situacao = fSit.value || null; carregar(); });
    document.getElementById("btn-filtros").addEventListener("click", function () {
      G.filtros({ titulo: "Filtros do acervo", filtro: filtro, aoAplicar: function () { limite = 24; carregar(); }, campos: [
        { id: "fase", rotulo: "Fase", vazio: "Todas", opcoes: API.FASES.map(function (t) { return { valor: t, texto: t }; }) },
        { id: "area", rotulo: "Área de conhecimento", vazio: "Todas", opcoes: API.AREAS.map(function (t) { return { valor: t, texto: t }; }) },
        { id: "disciplina", rotulo: "Disciplina", vazio: "Todas", opcoes: API.disciplinas().map(function (t) { return { valor: t, texto: t }; }) },
        { id: "origemTipo", rotulo: "Origem", vazio: "Todas", opcoes: API.ORIGENS_LICAO.map(function (t) { return { valor: t, texto: t }; }) },
        { id: "aplicabilidade", rotulo: "Aplicabilidade", vazio: "Todas", opcoes: API.APLICABILIDADES.map(function (t) { return { valor: t, texto: t }; }) }
      ] });
    });
  }
  function aoAgir() { carregar(); }
  document.getElementById("btn-nova").addEventListener("click", function () { G.novaLicao(projetoId, aoAgir); });
  document.addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-lic-acao]");
    if (b && !b.closest(".modal")) { ev.preventDefault(); G.acaoLicao(b.getAttribute("data-lic-acao"), b.getAttribute("data-codigo"), projetoId, aoAgir); return; }
    var f = ev.target.closest("[data-fase]");
    if (f) {
      var fase = f.getAttribute("data-fase");
      var ativo = filtro.fase === fase && filtro.situacao === "Publicada";
      filtro.fase = ativo ? null : fase; filtro.situacao = ativo ? null : "Publicada";
      carregar();
      return;
    }
    if (ev.target.closest("#btn-mais")) { limite += 24; renderAcervo(); }
  });
  document.addEventListener("tabs:change", function (ev) {
    aba = ev.detail.id === "p-painel" ? "painel" : "acervo";
    if (aba === "painel" && painel) renderPainel();
  });

  GI.exportar.registrar(function () {
    var p = U.projeto(projetoId) || {};
    var sub = (projetoId == null ? "Acervo visível ao portfólio" : "Acervo visível ao projeto " + (p.codigo || "")) + (Array.prototype.map.call(document.querySelectorAll("#chips .chip__label"), function (c) { return c.textContent; }).join(" · ") ? " · " +
      Array.prototype.map.call(document.querySelectorAll("#chips .chip__label"), function (c) { return c.textContent; }).join(" · ") : "");
    if (aba === "painel") {
      return {
        titulo: "Painel de lições aprendidas", subtitulo: sub, arquivo: "painel-de-licoes",
        blocos: [
          { tipo: "kpis", titulo: "Indicadores", itens: Array.prototype.map.call(document.querySelectorAll("#kpis-painel .kpi"), function (k) {
            return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" }; }) },
          { tipo: "grafico", titulo: "Lições por fase", canvas: document.getElementById("g-fase") },
          { tipo: "grafico", titulo: "Lições por área de conhecimento", canvas: document.getElementById("g-area") },
          { tipo: "tabela", titulo: "Lições por situação", dados: tSem.exportacao() },
          { tipo: "tabela", titulo: "Lições mais reusadas", dados: tReuso.exportacao() }
        ]
      };
    }
    var cols = [["Código", "texto"], ["Título", "texto"], ["Tipo", "texto"], ["Situação", "texto"], ["Fase", "texto"], ["Área", "texto"], ["Disciplina", "texto"], ["Aplicabilidade", "texto"],
      ["Origem", "texto"], ["Recomendação", "texto"], ["Prazo (dias)", "num"], ["Custo", "moeda"], ["Reusos", "num"], ["Projeto", "texto"], ["Data", "data"]];
    return {
      titulo: "Acervo de lições aprendidas", subtitulo: sub, arquivo: "acervo-de-licoes", orientacao: "l", formato: "a3",
      blocos: [{ tipo: "tabela", titulo: "Lições", dados: {
        colunas: cols.map(function (c) { return { titulo: c[0], tipo: c[1] }; }),
        bruto: lista.map(function (l) { return [l.codigo, l.titulo, l.tipo, l.situacao, l.fase, l.area, l.disciplina, l.aplicabilidade, l.origem, l.recomendacao, l.impactoPrazoDias, l.impactoCustoCentavos, l.reusos, l.projetoCodigo, l.data]; }),
        texto: lista.map(function (l) { return [l.codigo, l.titulo, l.tipo, l.situacao, l.fase, l.area, l.disciplina, l.aplicabilidade, l.origem, l.recomendacao, String(l.impactoPrazoDias || 0), F.moeda(l.impactoCustoCentavos || 0), String(l.reusos), l.projetoCodigo, F.data(l.data)]; })
      } }]
    };
  });

  G.pronto().then(function () {
    projetoId = G.projeto(function (id) { projetoId = id; limite = 24; carregar(); });
    montarFiltros();
    montarTabelasPainel();
    return carregar().then(function () {
      /* ?busca=LA-... abre a lição direto (vínculo vindo de outros módulos) */
      if (projetoId != null && U.acaoPendente() === "nova") { G.novaLicao(projetoId, aoAgir); return; }
      var b = filtro.busca;
      if (b && lista.length === 1 && lista[0].codigo === b.toUpperCase()) G.verLicao(lista[0].codigo, projetoId, aoAgir);
    });
  });
})(window.GI = window.GI || {});
