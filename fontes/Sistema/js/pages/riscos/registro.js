/* ==========================================================================
   Gestão de Riscos > Registro (mockup 01, com filtros 16 e exclusão 17)
   KPIs clicáveis pela avaliação exibida (residual quando existe, senão a
   inerente); aviso de revisão vencida; chips; tabela com ações por linha.
   Parâmetros de URL: projeto, busca, categoria, situacao, revisao,
   severidade, natureza, p, i, aval (vindos da matriz, do painel e da Home).
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt, S = GI.rsk, API = GI.api.riscos;
  var projetoId = null, todos = [], tabela = null;
  var aval = U.param("aval") === "inerente" ? "inerente" : "residual";
  function padrao() {
    return { busca: "", natureza: "", categoria: "", severidades: [], situacao: "ativos", estrategia: "", donoId: "", revisao: "",
      de: "", ate: "", incluirEncerrados: false, incluirExcluidos: false, p: null, i: null };
  }
  var filtro = padrao();
  filtro.busca = U.param("busca") || "";
  filtro.categoria = U.param("categoria") || "";
  filtro.natureza = U.param("natureza") || "";
  filtro.situacao = U.param("situacao") || "ativos";
  filtro.revisao = U.param("revisao") || "";
  if (U.param("severidade")) filtro.severidades = U.param("severidade").split(",");
  if (U.param("p") && U.param("i")) { filtro.p = Number(U.param("p")); filtro.i = Number(U.param("i")); }

  var REVISOES = [{ valor: "vencidas", texto: "Vencidas" }, { valor: "proximas", texto: "Vencem em 15 dias" }, { valor: "sem", texto: "Sem revisão registrada" }];

  /* ---------------- Avaliação exibida ---------------- */
  function exibida(r) {
    if (aval === "inerente") return { av: r.inerente, sev: r.sevInerente, score: r.scoreInerente };
    return { av: r.residual || r.inerente, sev: r.sevAtual, score: r.scoreAtual };
  }

  /* ---------------- Filtros ---------------- */
  function passaSituacao(r) {
    var ok = filtro.situacao === "todas" ? true : filtro.situacao === "ativos" ? r.ativo : r.situacao === filtro.situacao;
    if (!ok && filtro.incluirEncerrados && !r.ativo) ok = true;
    return ok;
  }
  function passaResto(r) {
    if (r.oculto && !filtro.incluirExcluidos) return false;
    if (filtro.natureza && r.natureza !== filtro.natureza) return false;
    if (filtro.categoria && r.categoria !== filtro.categoria && r.categoriaCompleta !== filtro.categoria) return false;
    if (filtro.estrategia && r.estrategia !== filtro.estrategia) return false;
    if (filtro.donoId && String(r.donoId) !== String(filtro.donoId)) return false;
    var e = exibida(r);
    if (filtro.severidades.length && !(e.sev && filtro.severidades.indexOf(e.sev.id) >= 0)) return false;
    if (filtro.p && filtro.i && !(e.av && e.av.p === filtro.p && e.av.i === filtro.i)) return false;
    if (filtro.revisao === "vencidas" && !r.revisaoVencida) return false;
    if (filtro.revisao === "proximas" && !(r.ativo && r.diasRevisao != null && r.diasRevisao >= 0 && r.diasRevisao <= S.param().revisaoAlertaDias)) return false;
    if (filtro.revisao === "sem" && !r.semRevisao) return false;
    if (filtro.de && r.identificadoEm < filtro.de) return false;
    if (filtro.ate && r.identificadoEm > filtro.ate) return false;
    if (filtro.busca && !U.contem([r.codigo, r.titulo, r.causa, r.consequencia, U.pessoa(r.donoId)].join(" "), filtro.busca)) return false;
    return true;
  }
  function filtroPadrao() {
    var p = padrao();
    return Object.keys(p).every(function (k) { return k === "busca" || JSON.stringify(p[k]) === JSON.stringify(filtro[k]); });
  }

  /* ---------------- KPIs e aviso ---------------- */
  function renderKpis() {
    var ativos = todos.filter(function (r) { return r.ativo && !r.oculto; });
    var leg = API.legenda().slice().reverse();
    var rot = aval === "inerente" ? "inerente" : "residual";
    function porSev(id) { return ativos.filter(function (r) { var e = exibida(r); return e.sev && e.sev.id === id; }); }
    /* Meta por faixa: severidade-alvo do plano de resposta (sem plano, a severidade atual) */
    function metaSev(id) { return ativos.filter(function (r) { var a = r.temPlano && r.severidadeAlvo ? r.severidadeAlvo : r.sevAtual ? r.sevAtual.id : null; return a === id; }).length; }
    function kSev(f, cor, icone) {
      var l = porSev(f.id), op = l.filter(function (r) { return r.natureza === "Oportunidade"; }).length;
      var ativo = filtro.severidades.length === 1 && filtro.severidades[0] === f.id;
      return U.kpi({ rotulo: f.nome + "s (" + rot + ")", valor: F.num(l.length), icone: icone, cor: l.length ? cor : "success",
        filtro: { valor: "sev:" + f.id, ativo: ativo }, esperado: { rotulo: "Meta", valor: F.num(metaSev(f.id)) },
        rodape: l.length ? U.plural(l.length - op, "ameaça") + (op ? " · " + U.plural(op, "oportunidade") : "") : "nenhum na faixa" });
    }
    var venc = ativos.filter(function (r) { return r.revisaoVencida; });
    var trat = ativos.filter(function (r) { return r.situacao === "Em tratamento"; });
    document.getElementById("kpis").innerHTML = [
      kSev(leg[0], "danger", "alertTriangle"),
      leg[1] ? kSev(leg[1], "warning", "alertCircle") : "",
      U.kpi({ rotulo: "Em tratamento", valor: F.num(trat.length), icone: "target", cor: "info", filtro: { valor: "sit:Em tratamento", ativo: filtro.situacao === "Em tratamento" },
        esperado: { rotulo: "Esperado", valor: F.num(ativos.filter(function (r) { return r.temPlano && r.estrategia !== "Aceitar"; }).length) },
        rodape: "plano aprovado e ações em curso" }),
      U.kpi({ rotulo: "Revisão vencida", valor: F.num(venc.length), icone: "calendarClock", cor: venc.length ? "danger" : "success",
        filtro: { valor: "rev:vencidas", ativo: filtro.revisao === "vencidas" }, esperado: { rotulo: "Esperado", valor: F.num(0) }, rodape: "próxima revisão anterior a hoje" }),
      U.kpi({ rotulo: "Ativos", valor: F.num(ativos.length), icone: "list", cor: "primary", filtro: { valor: "ativos", ativo: filtroPadrao() },
        esperado: { rotulo: "Referência", valor: "de " + F.num(todos.filter(function (r) { return !r.oculto; }).length) + " registrados" },
        rodape: U.plural(ativos.filter(function (r) { return !r.avaliado; }).length, "sem avaliação", "sem avaliação") })
    ].join("");
    var par = S.param(), topo = leg[0];
    document.getElementById("aviso").innerHTML = venc.length ? '<div class="alert alert--warning">' + U.icone("alertTriangle") + '<div class="alert__body"><b>' +
      U.plural(venc.length, "risco com revisão vencida", "riscos com revisão vencida") + ":</b> " + venc.map(function (r) { return S.linkFicha(r.codigo); }).join(", ") +
      ". Riscos " + U.esc(topo.nome.toLowerCase()) + "s exigem revisão " + U.esc(S.cadencia(par.cadenciaDias[topo.id])) + ". " +
      '<button type="button" class="btn btn--secondary btn--sm" data-filtro-aviso>' + U.icone("filter") + "Filtrar vencidas</button></div></div>" : "";
  }

  /* ---------------- Chips ---------------- */
  var SIT_TEXTO = { ativos: "Ativos", todas: "Todas" };
  function chips() {
    var it = [];
    it.push({ campo: "situacao", texto: "Situação: " + (SIT_TEXTO[filtro.situacao] || filtro.situacao), fixo: filtro.situacao === "ativos" });
    it.push({ campo: "natureza", texto: "Natureza: " + (filtro.natureza || "Todas"), fixo: !filtro.natureza });
    var nomes = API.legenda().filter(function (f) { return filtro.severidades.indexOf(f.id) >= 0; }).map(function (f) { return f.nome; });
    it.push({ campo: "severidades", texto: "Severidade: " + (nomes.length ? nomes.join(", ") : "Todas"), fixo: !nomes.length });
    if (filtro.p && filtro.i) it.push({ campo: "pi", texto: "Célula: P" + filtro.p + " x I" + filtro.i + " (" + aval + ")" });
    if (filtro.categoria) it.push({ campo: "categoria", texto: "Categoria: " + filtro.categoria });
    if (filtro.estrategia) it.push({ campo: "estrategia", texto: "Estratégia: " + filtro.estrategia });
    if (filtro.donoId) it.push({ campo: "donoId", texto: "Dono: " + U.pessoa(filtro.donoId) });
    if (filtro.revisao) it.push({ campo: "revisao", texto: "Revisão: " + REVISOES.filter(function (x) { return x.valor === filtro.revisao; })[0].texto });
    if (filtro.de || filtro.ate) it.push({ campo: "periodo", texto: "Identificado: " + (filtro.de ? F.data(filtro.de) : "início") + " a " + (filtro.ate ? F.data(filtro.ate) : "hoje") });
    if (filtro.incluirEncerrados) it.push({ campo: "incluirEncerrados", texto: "Inclui encerrados" });
    if (filtro.busca) it.push({ campo: "busca", texto: "Busca: " + filtro.busca });
    document.getElementById("chips").innerHTML = '<span class="filter-bar__label">Filtros ativos:</span>' + it.map(function (c) {
      return '<span class="chip"><span class="chip__label">' + U.esc(c.texto) + "</span>" +
        (c.fixo ? "" : '<button type="button" class="chip__remove" data-limpar="' + c.campo + '" aria-label="Remover filtro ' + U.esc(c.texto) + '">' + U.icone("x") + "</button>") + "</span>";
    }).join("") + (!filtroPadrao() ? '<button type="button" class="btn btn--ghost btn--sm" data-limpar="tudo">Limpar filtros</button>' : "");
  }

  /* ---------------- Tabela ---------------- */
  function colunas() {
    return [
      { id: "codigo", titulo: "Nº", fixa: true, classe: "nowrap", valor: function (r) { return r.codigo; },
        html: function (r) { return '<a href="' + U.tela("riscos", "ficha", { codigo: r.codigo }) + '" title="Abrir ficha"><b>' + U.esc(r.codigo) + "</b></a>" + (r.oculto ? '<br><small class="text-muted">excluído</small>' : ""); } },
      { id: "titulo", titulo: "Risco", fixa: true, valor: function (r) { return r.titulo; },
        html: function (r) { return '<div class="cell-title"><b>' + U.esc(r.titulo) + "</b><small>" + U.esc(r.categoriaCompleta) + (r.natureza === "Oportunidade" ? " · " + U.esc(r.natureza) : "") + "</small></div>"; },
        exportar: function (r) { return r.titulo + " · " + r.categoriaCompleta; } },
      { id: "natureza", titulo: "Natureza", oculta: true, valor: function (r) { return r.natureza; }, html: function (r) { return S.natureza(r.natureza); } },
      { id: "projeto", titulo: "Projeto", oculta: projetoId != null, classe: "nowrap", valor: function (r) { return r.projetoCodigo; } },
      { id: "dono", titulo: "Dono", valor: function (r) { return U.pessoa(r.donoId); } },
      { id: "inerente", titulo: "Inerente", tipo: "num", classe: aval === "inerente" ? "col-destaque" : "", valor: function (r) { return r.scoreInerente; },
        html: function (r) { return S.scoreCel(r.inerente, r.sevInerente, r.natureza, true); },
        exportar: function (r) { return r.inerente ? r.scoreInerente + " (P" + r.inerente.p + " x I" + r.inerente.i + ", " + r.sevInerente.nome + ")" : "não avaliado"; } },
      { id: "residual", titulo: "Residual", tipo: "num", classe: aval === "residual" ? "col-destaque" : "", valor: function (r) { return r.scoreResidual; },
        html: function (r) { return S.scoreCel(r.residual, r.sevResidual, r.natureza, true); },
        exportar: function (r) { return r.residual ? r.scoreResidual + " (P" + r.residual.p + " x I" + r.residual.i + ", " + r.sevResidual.nome + ")" : "não avaliado"; } },
      { id: "estrategia", titulo: "Estratégia", valor: function (r) { return r.estrategia || ""; },
        html: function (r) { return S.estrategia(r.estrategia) + (r.planoPendente ? '<br><small class="text-muted">aguarda aprovação</small>' : ""); } },
      { id: "acoes", titulo: "Ações", tipo: "num", valor: function (r) { return r.acoes; },
        html: function (r) {
          return r.acoes ? "<b>" + r.acoesAbertas + "</b>/" + r.acoes + '<br><small class="text-muted">abertas</small>' + (r.acoesAtrasadas ? '<br><small class="valor--negativo">' + U.plural(r.acoesAtrasadas, "atrasada") + "</small>" : "") : "0";
        },
        exportar: function (r) { return r.acoesAbertas + " abertas de " + r.acoes + (r.acoesAtrasadas ? " (" + r.acoesAtrasadas + " atrasadas)" : ""); } },
      { id: "proximaRevisao", titulo: "Próx. revisão", tipo: "data", classe: "nowrap", valor: function (r) { return r.proximaRevisao; },
        html: function (r) {
          if (!r.proximaRevisao) return '<span class="text-small text-muted">' + (r.ativo ? "sem data" : "encerrado") + "</span>";
          return F.data(r.proximaRevisao) + (r.revisaoVencida ? '<br><span class="badge badge--danger badge--dot">vencida</span>' : '<br><small class="text-muted">' + U.esc(S.cadencia(r.cadenciaDias)) + "</small>");
        },
        exportar: function (r) { return r.proximaRevisao ? F.data(r.proximaRevisao) + (r.revisaoVencida ? " (vencida)" : "") : ""; } },
      { id: "situacao", titulo: "Situação", fixa: true, valor: function (r) { return r.situacao; }, html: function (r) { return S.situacao(r.situacao, true); } }
    ];
  }
  function acoesLinha(r) {
    /* Abrir ficha: o número do risco é o link (mantém a tabela sem rolagem em 1440px) */
    var h = "";
    if (!r.ativo || r.oculto) return '<a class="btn btn--ghost btn--icon btn--sm" href="' + U.tela("riscos", "ficha", { codigo: r.codigo }) + '" aria-label="Abrir ficha de ' + U.esc(r.codigo) + '" title="Abrir ficha">' + U.icone("fileText") + "</a>";
    if (API.pode("Membro")) {
      h += '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-avaliar="' + U.esc(r.codigo) + '" aria-label="Avaliar ' + U.esc(r.codigo) + '" title="Avaliar">' + U.icone("gauge") + "</button>";
      h += '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-acao="' + U.esc(r.codigo) + '" aria-label="Nova ação em ' + U.esc(r.codigo) + '" title="Nova ação">' + U.icone("plus") + "</button>";
    }
    if (API.pode("Gestor")) h += '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-excluir="' + U.esc(r.codigo) + '" aria-label="Excluir ' + U.esc(r.codigo) + '" title="Excluir">' + U.icone("trash") + "</button>";
    return h;
  }
  function criarTabela() {
    var visiveis = tabela ? tabela.colunas().filter(function (c) { return c.visivel; }).map(function (c) { return c.id; }) : null;
    tabela = GI.tabela.criar("tabela", {
      colunas: colunas(), porPagina: 15, compacta: true, ordem: { coluna: aval, direcao: "desc" }, legenda: "Registro de riscos",
      vazio: "Nenhum risco encontrado com os filtros atuais.",
      classeLinha: function (r) { return r.revisaoVencida ? "is-alert" : !r.ativo || r.oculto ? "is-muted" : ""; },
      acoes: acoesLinha
    });
    if (visiveis) tabela.colunasVisiveis(visiveis);
  }

  function aplicar() {
    var base = todos.filter(passaResto);
    var lista = base.filter(passaSituacao);
    renderKpis(); chips();
    var fechadosFora = todos.filter(function (r) { return !r.ativo && !r.oculto && lista.indexOf(r) < 0; }).length;
    document.getElementById("contagem").textContent = (filtro.situacao === "ativos" && !filtro.incluirEncerrados ? U.plural(lista.length, "risco ativo", "riscos ativos") : U.plural(lista.length, "risco", "riscos") + " no filtro atual") +
      (fechadosFora ? " (" + U.plural(fechadosFora, "encerrado oculto", "encerrados ocultos") + " pelo filtro)" : "");
    tabela.atualizar(lista);
    document.getElementById("lnk-matriz").href = U.tela("riscos", "matriz", { projeto: projetoId, aval: aval });
  }
  function carregar() {
    return API.lista({ projetoId: projetoId, incluirOcultos: filtro.incluirExcluidos }).then(function (l) {
      todos = l;
      document.getElementById("contexto").innerHTML = S.contexto(projetoId);
      aplicar();
    });
  }

  /* ---------------- Modal 7: Filtros ---------------- */
  function abrirFiltros() {
    var par = S.param();
    var grupos = [];
    S.categorias().forEach(function (c) { if (grupos.indexOf(c.grupo) < 0) grupos.push(c.grupo); });
    var cats = [];
    grupos.sort().forEach(function (g) {
      cats.push({ valor: g, texto: g + " (todas)" });
      S.categorias().filter(function (c) { return c.grupo === g; }).forEach(function (c) { cats.push({ valor: g + " > " + c.nome, texto: g + " > " + c.nome }); });
    });
    var estr = [];
    Object.keys(API.ESTRATEGIAS).forEach(function (n) { API.ESTRATEGIAS[n].forEach(function (e) { if (estr.indexOf(e) < 0) estr.push(e); }); });
    var admin = API.pode("Admin");
    var m = GI.form.abrir({
      titulo: "Filtros do registro de riscos", tamanho: "lg", textoSalvar: "Aplicar",
      campos: [
        { id: "natureza", rotulo: "Natureza", tipo: "select", vazio: "Todas", valor: filtro.natureza, opcoes: [{ valor: "Ameaça", texto: "Ameaça" }, { valor: "Oportunidade", texto: "Oportunidade" }] },
        { id: "categoria", rotulo: "Categoria (RBS)", tipo: "select", vazio: "Todas", valor: filtro.categoria, opcoes: cats },
        { id: "severidades", rotulo: "Severidade (" + aval + ")", tipo: "multi", valor: filtro.severidades,
          opcoes: API.legenda().map(function (f) { return { valor: f.id, texto: f.nome + " (" + f.minimo + " a " + f.maximo + ")" }; }), ajuda: "Seleção múltipla. Sem seleção equivale a todas." },
        { id: "situacao", rotulo: "Situação", tipo: "select", obrigatorio: true, valor: filtro.situacao,
          opcoes: [{ valor: "ativos", texto: "Ativos" }].concat(API.SITUACOES.map(function (s) { return { valor: s, texto: s }; })).concat([{ valor: "todas", texto: "Todas" }]) },
        { id: "estrategia", rotulo: "Estratégia", tipo: "select", vazio: "Todas", valor: filtro.estrategia, opcoes: estr.map(function (e) { return { valor: e, texto: e }; }) },
        { id: "donoId", rotulo: "Dono do risco", tipo: "select", vazio: "Todos", valor: filtro.donoId, opcoes: S.pessoas() },
        { id: "revisao", rotulo: "Revisão", tipo: "select", vazio: "Todas", valor: filtro.revisao,
          opcoes: REVISOES.map(function (x) { return x.valor === "proximas" ? { valor: x.valor, texto: "Vencem em " + par.revisaoAlertaDias + " dias" } : x; }) },
        { id: "de", rotulo: "Identificado de", tipo: "data", valor: filtro.de },
        { id: "ate", rotulo: "até", tipo: "data", valor: filtro.ate },
        { id: "busca", rotulo: "Busca livre", tipo: "texto", valor: filtro.busca, largura: "full", placeholder: "Número, título, causa, consequência ou dono" },
        { id: "incluirEncerrados", rotulo: "Incluir encerrados", tipo: "check", valor: filtro.incluirEncerrados },
        { id: "incluirExcluidos", rotulo: "Incluir excluídos (só Admin)", tipo: "check", valor: filtro.incluirExcluidos, desabilitado: !admin,
          ajuda: admin ? "Mostra registros excluídos (exclusão lógica) para restauração." : "Disponível somente para o papel Admin." }
      ],
      extras: [{ texto: "Limpar", variante: "ghost", acao: function (ctx) {
        ctx.definir({ natureza: "", categoria: "", severidades: [], situacao: "ativos", estrategia: "", donoId: "", revisao: "", de: "", ate: "", busca: "", incluirEncerrados: false, incluirExcluidos: false });
      } }],
      aoMudar: function (v) {
        if (!m) return;
        Array.prototype.forEach.call(m.el.querySelectorAll('[data-campo="estrategia"] option'), function (o) {
          o.hidden = !!(o.value && v.natureza && API.ESTRATEGIAS[v.natureza].indexOf(o.value) < 0);
        });
      },
      validar: function (v) {
        var e = [];
        if (v.de && v.ate && v.de > v.ate) e.push({ campo: "ate", msg: "A data final deve ser posterior à inicial." });
        if (v.natureza && v.estrategia && API.ESTRATEGIAS[v.natureza].indexOf(v.estrategia) < 0) e.push({ campo: "estrategia", msg: "Estratégia não se aplica à natureza escolhida." });
        return e;
      },
      aoSalvar: function (v) {
        var trocou = !!v.incluirExcluidos !== filtro.incluirExcluidos;
        Object.keys(padrao()).forEach(function (k) { if (k in v) filtro[k] = v[k]; });
        filtro.severidades = v.severidades || [];
        document.getElementById("busca").value = filtro.busca;
        if (trocou) return carregar();
        aplicar();
      }
    });
  }

  /* ---------------- Eventos ---------------- */
  function recarregar() { return carregar(); }
  document.getElementById("kpis").addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-filtro]");
    if (!b) return;
    var v = b.getAttribute("data-filtro");
    if (v === "ativos") { var busca = filtro.busca; filtro = padrao(); filtro.busca = busca; }
    else if (v.indexOf("sev:") === 0) { var id = v.slice(4); filtro.severidades = filtro.severidades.length === 1 && filtro.severidades[0] === id ? [] : [id]; }
    else if (v.indexOf("sit:") === 0) filtro.situacao = filtro.situacao === v.slice(4) ? "ativos" : v.slice(4);
    else if (v === "rev:vencidas") filtro.revisao = filtro.revisao === "vencidas" ? "" : "vencidas";
    aplicar();
    var novo = document.querySelector('#kpis [data-filtro="' + v + '"]');
    if (novo) novo.focus();
  });
  document.getElementById("aviso").addEventListener("click", function (ev) {
    if (ev.target.closest("[data-filtro-aviso]")) { filtro.revisao = "vencidas"; aplicar(); }
  });
  document.getElementById("chips").addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-limpar]");
    if (!b) return;
    var c = b.getAttribute("data-limpar");
    if (c === "tudo") { var inc = filtro.incluirExcluidos; filtro = padrao(); document.getElementById("busca").value = ""; if (inc) return carregar(); }
    else if (c === "situacao") filtro.situacao = "ativos";
    else if (c === "severidades") filtro.severidades = [];
    else if (c === "pi") { filtro.p = null; filtro.i = null; }
    else if (c === "periodo") { filtro.de = ""; filtro.ate = ""; }
    else if (c === "incluirEncerrados") filtro.incluirEncerrados = false;
    else { filtro[c] = ""; if (c === "busca") document.getElementById("busca").value = ""; }
    aplicar();
  });
  document.getElementById("busca").addEventListener("input", U.debounce(function (ev) { filtro.busca = ev.target.value.trim(); aplicar(); }, 200));
  document.getElementById("btn-filtros").addEventListener("click", abrirFiltros);
  document.getElementById("btn-atualizar").addEventListener("click", function () { carregar().then(function () { GI.ui.toast("Consulta atualizada.", "success"); }); });
  document.getElementById("btn-colunas").addEventListener("click", function () {
    var cols = tabela.colunas();
    GI.form.abrir({
      titulo: "Colunas da tabela", tamanho: "sm", textoSalvar: "Aplicar",
      campos: [{ id: "cols", rotulo: "Colunas visíveis", tipo: "multi", obrigatorio: true,
        opcoes: cols.filter(function (c) { return !c.fixa; }).map(function (c) { return { valor: c.id, texto: c.titulo }; }),
        valor: cols.filter(function (c) { return c.visivel && !c.fixa; }).map(function (c) { return c.id; }) }],
      aoSalvar: function (v) { tabela.colunasVisiveis(cols.filter(function (c) { return c.fixa || v.cols.indexOf(c.id) >= 0; }).map(function (c) { return c.id; })); }
    });
  });
  document.getElementById("f-aval").addEventListener("segmented:change", function (ev) {
    aval = ev.detail.value === "inerente" ? "inerente" : "residual";
    criarTabela(); aplicar();
  });
  document.getElementById("btn-novo").addEventListener("click", function () { S.novo(projetoId, recarregar); });
  document.getElementById("tabela").addEventListener("click", function (ev) {
    var b;
    if ((b = ev.target.closest("[data-avaliar]"))) S.avaliar(b.getAttribute("data-avaliar"), null, recarregar);
    else if ((b = ev.target.closest("[data-acao]"))) S.novaAcao(b.getAttribute("data-acao"), recarregar);
    else if ((b = ev.target.closest("[data-excluir]"))) S.excluir(b.getAttribute("data-excluir"), recarregar);
  });

  GI.exportar.registrar(function (tipo) {
    var d = tabela.exportacao();
    if (tipo === "excel") {
      var linhas = tabela.ordenadas();
      [["Causa", function (r) { return r.causa; }], ["Consequência", function (r) { return r.consequencia; }], ["Plano de resposta", function (r) { return r.plano || ""; }]].forEach(function (x) {
        d.colunas.push({ titulo: x[0], tipo: "texto" });
        d.bruto.forEach(function (l, k) { l.push(x[1](linhas[k])); });
        d.texto.forEach(function (l, k) { l.push(x[1](linhas[k])); });
      });
    }
    var p = U.projeto(projetoId) || { codigo: "Portfólio", nome: "Portfólio de projetos" };
    return {
      titulo: "Registro de riscos · " + p.codigo, subtitulo: p.nome + " · " + document.getElementById("contagem").textContent, arquivo: "registro-de-riscos-" + (projetoId == null ? "portfolio" : p.codigo), orientacao: "l",
      blocos: [
        { tipo: "kpis", titulo: "Resumo (" + aval + ")", itens: Array.prototype.map.call(document.querySelectorAll("#kpis .kpi"), function (k) {
            return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" };
          }) },
        { tipo: "texto", titulo: "Filtros aplicados", texto: Array.prototype.map.call(document.querySelectorAll("#chips .chip__label"), function (c) { return c.textContent; }).join(" · ") },
        { tipo: "tabela", titulo: "Riscos", dados: d, fonte: 7 }
      ]
    };
  });

  S.pronto().then(function () {
    projetoId = S.projeto(function (id) { projetoId = id; filtro.p = null; filtro.i = null; carregar(); });
    document.getElementById("busca").value = filtro.busca;
    Array.prototype.forEach.call(document.querySelectorAll("#f-aval .segmented__opt"), function (o) { o.setAttribute("aria-pressed", String(o.getAttribute("data-value") === aval)); });
    criarTabela();
    return carregar().then(function () { if (projetoId != null && U.acaoPendente() === "novo") S.novo(projetoId, recarregar); });
  });
})(window.GI = window.GI || {});
