/* ==========================================================================
   Qualidade > Inspeções e ITP (06)
   Planos de inspeção e testes (pontos H, W e R, revisão e aprovação do cliente) e
   registros de inspeção por ponto. Reprovação abre RNC; inspeção só em ITP aprovado.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt, Q = GI.qld, API = GI.api.qualidade;
  var projetoId, tItps, tabela, itps = [], filtro = {}, meta = 95;

  function kpis(insp) {
    var aprov = insp.filter(function (n) { return n.resultado !== "Reprovado"; }).length;
    var pct = insp.length ? aprov / insp.length * 100 : null;
    var reprov = insp.filter(function (n) { return n.resultado === "Reprovado"; });
    var rncAbertas = reprov.filter(function (n) { return n.rncSituacao && n.rncSituacao !== "Encerrada" && n.rncSituacao !== "Cancelada"; }).length;
    var semAprov = itps.filter(function (i) { return !i.aprovadoCliente; }).length;
    var pontos = itps.reduce(function (s, i) { return s + i.totalPontos; }, 0), cobertos = itps.reduce(function (s, i) { return s + i.pontosInspecionados; }, 0);
    document.getElementById("kpis").innerHTML = [
      U.kpi({ rotulo: "Inspeções registradas", valor: F.num(insp.length), icone: "clipboardCheck", cor: "primary", esperado: { rotulo: "Previsto", valor: F.num(pontos) + " pontos" },
        rodape: U.plural(insp.filter(function (n) { return n.resultado === "Aprovado com ressalva"; }).length, "com ressalva", "com ressalva") }),
      U.kpi({ rotulo: "Aprovação nas inspeções", valor: pct == null ? "·" : F.num(pct, 1), unidade: pct == null ? "" : "%", icone: "checkCircle",
        cor: pct == null ? "info" : pct >= meta ? "success" : "warning", esperado: { rotulo: "Meta", valor: F.pct(meta, 0) }, rodape: "ressalva conta como aprovada" }),
      U.kpi({ rotulo: "Reprovadas", valor: F.num(reprov.length), icone: "octagonAlert", cor: reprov.length ? "danger" : "success", esperado: { rotulo: "Esperado", valor: "0" }, rodape: U.plural(rncAbertas, "RNC em aberto", "RNCs em aberto") }),
      U.kpi({ rotulo: "ITPs aprovados pelo cliente", valor: F.num(itps.length - semAprov), unidade: "de " + F.num(itps.length), icone: "shieldCheck", cor: semAprov ? "warning" : "success",
        esperado: { rotulo: "Meta", valor: F.pct(100, 0) }, rodape: semAprov ? U.plural(semAprov, "aguardando aprovação", "aguardando aprovação") : "todos aprovados" }),
      U.kpi({ rotulo: "Pontos já inspecionados", valor: F.num(cobertos), unidade: "de " + F.num(pontos), icone: "listChecks", cor: "info", esperado: { rotulo: "Meta", valor: F.pct(100, 0) }, rodape: "ao menos um registro no ponto" })
    ].join("");
  }

  function montarTabelas() {
    tItps = GI.tabela.criar("tabela-itps", {
      porPagina: 0, legenda: "Planos de inspeção e testes", vazio: "Nenhum ITP cadastrado.", ordem: { coluna: "codigo", direcao: "asc" },
      colunas: (projetoId == null ? [U.colunaProjeto()] : []).concat([
        { id: "codigo", titulo: "ITP", classe: "nowrap", html: function (i) { return '<a href="#" data-ver-itp="' + U.esc(i.codigo) + '"><b>' + U.esc(i.codigo) + "</b></a><br><small class=\"text-muted\">Rev " + i.revisao + "</small>"; },
          exportar: function (i) { return i.codigo + " rev " + i.revisao; } },
        { id: "titulo", titulo: "Título", html: function (i) { return '<div class="cell-title"><b>' + U.esc(i.titulo) + "</b><small>" + U.esc(i.disciplina + " · " + U.empresa(i.empresaId)) + "</small></div>"; } },
        { id: "pontos", titulo: "Pontos", valor: function (i) { return i.totalPontos; },
          html: function (i) { return F.num(i.totalPontos) + '<br><small class="text-muted nowrap">H ' + i.porTipo.H + " · W " + i.porTipo.W + " · R " + i.porTipo.R + "</small>"; },
          exportar: function (i) { return i.totalPontos + " (H " + i.porTipo.H + ", W " + i.porTipo.W + ", R " + i.porTipo.R + ")"; } },
        { id: "inspecoes", titulo: "Inspeções", tipo: "num", oculta: true },
        { id: "aprovacaoPct", titulo: "Inspeções e aprovação", tipo: "num", html: function (i) { return F.num(i.inspecoes) + (i.aprovacaoPct == null ? "" : '<br><small class="' + (i.aprovacaoPct < meta ? "valor--negativo" : "text-muted") + '">' + U.esc(F.pct(i.aprovacaoPct)) + " aprovadas</small>"); },
          exportar: function (i) { return i.aprovacaoPct == null ? "" : F.pct(i.aprovacaoPct); } },
        { id: "aprovadoCliente", titulo: "Cliente", valor: function (i) { return i.aprovadoCliente ? "Aprovado" : "Pendente"; },
          html: function (i) { return i.aprovadoCliente ? U.badge("Aprovado", "success", true) : U.badge("Pendente", "warning", true); } }
      ]),
      acoes: function (i) {
        var b = '<a class="btn btn--ghost btn--icon btn--sm" href="#" data-ver-itp="' + U.esc(i.codigo) + '" title="Ver pontos" aria-label="Ver pontos do ' + U.esc(i.codigo) + '">' + U.icone("eye") + "</a>";
        if (!i.aprovadoCliente) b += '<button type="button" class="btn btn--ghost btn--sm" data-aprovar-itp="' + U.esc(i.codigo) + '" title="Registrar a aprovação do cliente">' + U.icone("checkCircle") + "Aprovar</button>";
        b += '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-revisar-itp="' + U.esc(i.codigo) + '" title="Nova revisão" aria-label="Nova revisão do ' + U.esc(i.codigo) + '">' + U.icone("history") + "</button>";
        if (i.aprovadoCliente) b += '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-inspecionar="' + i.id + '" title="Registrar inspeção" aria-label="Registrar inspeção no ' + U.esc(i.codigo) + '">' + U.icone("clipboardCheck") + "</button>";
        return b;
      }
    });
    tabela = GI.tabela.criar("tabela", {
      porPagina: 20, legenda: "Registros de inspeção", vazio: "Nenhum registro encontrado.", ordem: { coluna: "data", direcao: "desc" },
      colunas: (projetoId == null ? [U.colunaProjeto()] : []).concat([
        { id: "codigo", titulo: "Nº", classe: "nowrap" },
        { id: "data", titulo: "Data", tipo: "data" },
        { id: "ponto", titulo: "Ponto", html: function (n) { return '<div class="cell-title"><b>' + U.esc(n.ponto) + "</b><small>" + U.esc((n.itpCodigo || n.itpTitulo) + " · " + U.empresa(n.empresaId)) + "</small></div>"; },
          exportar: function (n) { return n.ponto + " (" + (n.itpCodigo || n.itpTitulo) + ")"; } },
        { id: "tipoPonto", titulo: "Tipo", html: function (n) { return Q.tipoPonto(n.tipoPonto); } },
        { id: "inspetor", titulo: "Inspetor", valor: function (n) { return U.pessoa(n.inspetorId); } },
        { id: "resultado", titulo: "Resultado", html: function (n) { return Q.resultado(n.resultado) + (n.observacao ? '<br><small class="text-muted">' + U.esc(n.observacao) + "</small>" : ""); },
          exportar: function (n) { return n.resultado + (n.observacao ? " · " + n.observacao : ""); } },
        { id: "rncRef", titulo: "RNC", classe: "nowrap", html: function (n) { return n.rncRef ? '<a href="' + U.tela("qualidade", "rnc", { busca: n.rncRef }) + '">' + U.esc(n.rncRef) + "</a><br><small class=\"text-muted\">" + U.esc(n.rncSituacao || "") + "</small>" : ""; } }
      ]),
      classeLinha: function (n) { return n.resultado === "Reprovado" ? "is-alert" : ""; }
    });
  }

  function carregar() {
    return Promise.all([API.itps({ projetoId: projetoId }), API.inspecoes(Object.assign({ projetoId: projetoId }, filtro)), API.inspecoes({ projetoId: projetoId })]).then(function (r) {
      itps = r[0];
      tItps.atualizar(itps, true);
      document.getElementById("sub-itps").textContent = U.plural(itps.length, "plano", "planos") + " · H = espera obrigatória; W = testemunho do cliente; R = revisão de registros";
      var fi = document.getElementById("f-itp"), sel = fi.value;
      fi.innerHTML = U.opcoes(itps.map(function (i) { return { valor: String(i.id), texto: i.codigo + " " + i.titulo }; }), sel, "ITP: todos");
      kpis(r[2]);
      tabela.atualizar(r[1], true);
      document.getElementById("contagem").textContent = U.plural(r[1].length, "registro encontrado", "registros encontrados") + " · reprovação abre RNC automaticamente";
    });
  }
  function recarregar() { return carregar(); }

  function montarFiltros() {
    var busca = document.getElementById("busca");
    busca.addEventListener("input", U.debounce(function () { filtro.busca = busca.value.trim() || null; carregar(); }, 250));
    var fi = document.getElementById("f-itp");
    fi.addEventListener("change", function () { filtro.itpId = fi.value || null; carregar(); });
    var fr = document.getElementById("f-resultado");
    fr.innerHTML = U.opcoes(API.RESULTADOS, "", "Resultado: todos");
    fr.addEventListener("change", function () { filtro.resultado = fr.value || null; carregar(); });
    var ft = document.getElementById("f-tipo");
    ft.innerHTML = U.opcoes(API.TIPOS_PONTO.map(function (t) { return { valor: t, texto: Q.NOME_PONTO[t] }; }), "", "Tipo de ponto: todos");
    ft.addEventListener("change", function () { filtro.tipoPonto = ft.value || null; carregar(); });
  }

  function itpPorCodigo(c) { return itps.filter(function (i) { return i.codigo === c; })[0]; }
  document.getElementById("btn-inspecao").addEventListener("click", function () { Q.registrarInspecao(projetoId, itps, recarregar); });
  document.getElementById("btn-itp").addEventListener("click", function () { Q.editarItp(projetoId, null, recarregar); });
  document.getElementById("tabela-itps").addEventListener("click", function (ev) {
    var el;
    if ((el = ev.target.closest("[data-ver-itp]"))) { ev.preventDefault(); Q.verItp(itpPorCodigo(el.getAttribute("data-ver-itp"))); }
    else if ((el = ev.target.closest("[data-aprovar-itp]"))) Q.aprovarItp(itpPorCodigo(el.getAttribute("data-aprovar-itp")), recarregar);
    else if ((el = ev.target.closest("[data-revisar-itp]"))) Q.editarItp(projetoId, itpPorCodigo(el.getAttribute("data-revisar-itp")), recarregar);
    else if ((el = ev.target.closest("[data-inspecionar]"))) {
      var i = itps.filter(function (x) { return String(x.id) === el.getAttribute("data-inspecionar"); })[0];
      if (projetoId == null) { window.location.href = U.tela("qualidade", "inspecoes", { projeto: i.projetoId, acao: "inspecao", itp: i.id }); return; }
      Q.registrarInspecao(projetoId, itps, recarregar, { itpId: i.id });
    }
  });

  GI.exportar.registrar(function () {
    var p = U.projeto(projetoId);
    return {
      titulo: "Inspeções e ITP", subtitulo: p ? p.codigo + " " + p.nome : "Portfólio de projetos", arquivo: "inspecoes-qualidade-" + (p ? p.codigo : "portfolio"), orientacao: "l",
      blocos: [
        { tipo: "kpis", titulo: "Indicadores", itens: Array.prototype.map.call(document.querySelectorAll("#kpis .kpi"), function (k) {
          return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" }; }) },
        { tipo: "tabela", titulo: "Planos de inspeção e testes", dados: tItps.exportacao() },
        { tipo: "tabela", titulo: "Registros de inspeção", dados: tabela.exportacao() }
      ]
    };
  });

  Q.pronto().then(function (par) {
    meta = par && par.metaAprovacaoInspecaoPct || 95;
    projetoId = Q.projeto();
    montarFiltros();
    montarTabelas();
    return carregar().then(function () {
      if (projetoId == null) return;
      var a = U.acaoPendente();
      if (a === "novo-itp") Q.editarItp(projetoId, null, recarregar);
      else if (a === "inspecao") Q.registrarInspecao(projetoId, itps, recarregar, { itpId: U.param("itp") ? Number(U.param("itp")) : null });
    });
  });
})(window.GI = window.GI || {});
