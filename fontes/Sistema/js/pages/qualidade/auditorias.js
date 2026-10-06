/* ==========================================================================
   Qualidade > Auditorias (06)
   Programa de auditorias (contratadas, fornecedores e interna), reprogramação justificada,
   resultado com conformidade e constatações; Não conformidade abre RNC (origem Auditoria).
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt, Q = GI.qld, API = GI.api.qualidade;
  var projetoId, tabela, lista = [], filtro = {}, meta = 90;

  function kpis(todas) {
    var ref = GI.api.referencia();
    var previstas = todas.filter(function (a) { return a.data <= ref; });
    var feitas = previstas.filter(function (a) { return a.situacao === "Realizada"; });
    var real = todas.filter(function (a) { return a.situacao === "Realizada"; });
    var ver = real.reduce(function (s, a) { return s + a.itensVerificados; }, 0), conf = real.reduce(function (s, a) { return s + a.itensConformes; }, 0);
    var pct = ver ? conf / ver * 100 : null;
    var atrasadas = todas.filter(function (a) { return a.atrasada; }).length;
    var nc = todas.reduce(function (s, a) { return s + (a.porTipo ? a.porTipo["Não conformidade"] || 0 : 0); }, 0);
    var ncAbertas = todas.reduce(function (s, a) { return s + (a.ncAbertas || 0); }, 0);
    var proxima = todas.filter(function (a) { return a.situacao === "Planejada" && a.data >= ref; })[0];
    document.getElementById("kpis").innerHTML = [
      U.kpi({ rotulo: "Aderência ao programa", valor: previstas.length ? F.num(feitas.length / previstas.length * 100, 1) : "·", unidade: previstas.length ? "%" : "", icone: "calendarClock",
        cor: atrasadas ? "warning" : "success", esperado: { rotulo: "Meta", valor: F.pct(100, 0) }, rodape: F.num(feitas.length) + " de " + F.num(previstas.length) + " previstas até hoje" }),
      U.kpi({ rotulo: "Auditorias atrasadas", valor: F.num(atrasadas), icone: "clock", cor: atrasadas ? "danger" : "success", esperado: { rotulo: "Esperado", valor: "0" }, rodape: "data planejada vencida sem resultado" }),
      U.kpi({ rotulo: "Conformidade nas auditorias", valor: pct == null ? "·" : F.num(pct, 1), unidade: pct == null ? "" : "%", icone: "shieldCheck",
        cor: pct == null ? "info" : pct >= meta ? "success" : "warning", esperado: { rotulo: "Meta", valor: F.pct(meta, 0) }, rodape: F.num(conf) + " de " + F.num(ver) + " itens" }),
      U.kpi({ rotulo: "Não conformidades de auditoria", valor: F.num(nc), icone: "octagonAlert", cor: ncAbertas ? "warning" : "success", esperado: { rotulo: "Esperado", valor: "0" }, rodape: U.plural(ncAbertas, "RNC em aberto", "RNCs em aberto") }),
      U.kpi({ rotulo: "Próxima auditoria", valor: proxima ? U.esc(F.data(proxima.data).replace(/[\/.-]?\d{4}$/, "").replace(/^\d{4}[\/.-]/, "")) : "·", unidade: proxima ? proxima.data.slice(0, 4) : "", icone: "calendar", cor: "info",
        /* Linha de base: data original do programa (antes de reprogramações justificadas) */
        esperado: { rotulo: "Linha de base", valor: proxima ? F.data(proxima.reprogramacoes && proxima.reprogramacoes.length ? proxima.reprogramacoes[0].de : proxima.data) : "·" }, rodape: proxima ? U.esc(proxima.codigo + " · " + U.empresa(proxima.auditadoId)) : "nenhuma planejada" })
    ].join("");
  }

  function montarTabela() {
    tabela = GI.tabela.criar("tabela", {
      porPagina: 20, legenda: "Programa de auditorias", vazio: "Nenhuma auditoria encontrada.", ordem: { coluna: "data", direcao: "asc" },
      colunas: (projetoId == null ? [U.colunaProjeto()] : []).concat([
        { id: "codigo", titulo: "Nº", classe: "nowrap", html: function (a) { return '<a href="#" data-ver="' + U.esc(a.codigo) + '"><b>' + U.esc(a.codigo) + "</b></a>"; } },
        { id: "data", titulo: "Data", tipo: "data", valor: function (a) { return a.realizadaEm || a.data; },
          html: function (a) { return U.esc(F.data(a.realizadaEm || a.data)) + (a.atrasada ? '<br><span class="text-small valor--negativo">planejada há ' + U.esc(U.plural(a.diasAtraso, "dia")) + "</span>" : ""); } },
        { id: "escopo", titulo: "Escopo", html: function (a) { return '<div class="cell-title"><b>' + U.esc(a.escopo) + "</b><small>" + U.esc(a.tipo + " · " + U.empresa(a.auditadoId) + " · auditor " + U.pessoa(a.auditorId)) + "</small></div>"; },
          exportar: function (a) { return a.escopo + " (" + a.tipo + ", " + U.empresa(a.auditadoId) + ")"; } },
        { id: "auditor", titulo: "Auditor líder", oculta: true, valor: function (a) { return U.pessoa(a.auditorId); } },
        { id: "situacao", titulo: "Situação", valor: function (a) { return a.atrasada ? "Atrasada" : a.situacao; }, html: function (a) { return Q.situacaoAuditoria(a); } },
        { id: "conformidadePct", titulo: "Conformidade", tipo: "num", oculta: true,
          html: function (a) { return a.conformidadePct == null ? '<span class="text-muted">·</span>' : '<span class="' + (a.conformidadePct < meta ? "valor--negativo" : "") + '">' + U.esc(F.pct(a.conformidadePct)) + "</span>"; },
          exportar: function (a) { return a.conformidadePct == null ? "" : F.pct(a.conformidadePct); } },
        { id: "constatacoes", titulo: "Resultado", valor: function (a) { return a.conformidadePct == null ? -1 : a.conformidadePct; },
          html: function (a) {
            if (a.situacao !== "Realizada") return '<span class="text-muted">·</span>';
            return '<b class="' + (a.conformidadePct < meta ? "valor--negativo" : "") + '">' + U.esc(F.pct(a.conformidadePct)) + '</b> <span class="text-small text-muted">conforme</span><br><span class="text-small nowrap">NC ' + (a.porTipo["Não conformidade"] || 0) + " · Obs. " + (a.porTipo["Observação"] || 0) + " · OM " + (a.porTipo["Oportunidade de melhoria"] || 0) + "</span>" +
              (a.ncAbertas ? '<br><small class="valor--negativo">' + U.esc(U.plural(a.ncAbertas, "RNC em aberto", "RNCs em aberto")) + "</small>" : "");
          },
          exportar: function (a) { return a.situacao === "Realizada" ? "NC " + (a.porTipo["Não conformidade"] || 0) + ", Obs. " + (a.porTipo["Observação"] || 0) + ", OM " + (a.porTipo["Oportunidade de melhoria"] || 0) : ""; } }
      ]),
      classeLinha: function (a) { return a.atrasada ? "is-alert" : ""; },
      acoes: function (a) {
        var b = '<a class="btn btn--ghost btn--icon btn--sm" href="#" data-ver="' + U.esc(a.codigo) + '" title="Ver auditoria" aria-label="Ver auditoria ' + U.esc(a.codigo) + '">' + U.icone("eye") + "</a>";
        if (a.situacao === "Planejada") {
          b += '<button type="button" class="btn btn--ghost btn--sm" data-resultado="' + U.esc(a.codigo) + '">' + U.icone("clipboardCheck") + "Resultado</button>";
          b += '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-reprogramar="' + U.esc(a.codigo) + '" title="Reprogramar" aria-label="Reprogramar ' + U.esc(a.codigo) + '">' + U.icone("calendarClock") + "</button>";
        }
        return b;
      }
    });
  }

  function carregar() {
    return Promise.all([API.auditorias(Object.assign({ projetoId: projetoId }, filtro)), API.auditorias({ projetoId: projetoId })]).then(function (r) {
      lista = r[0];
      kpis(r[1]);
      tabela.atualizar(lista, true);
      document.getElementById("contagem").textContent = U.plural(lista.length, "auditoria", "auditorias") + " · ISO 19011; Não conformidade abre RNC";
    });
  }
  function recarregar() { return carregar(); }

  function montarFiltros() {
    var busca = document.getElementById("busca");
    busca.addEventListener("input", U.debounce(function () { filtro.busca = busca.value.trim() || null; carregar(); }, 250));
    var fs = document.getElementById("f-situacao");
    fs.innerHTML = U.opcoes(["Planejada", "Realizada", "Atrasada"], "", "Situação: todas");
    fs.addEventListener("change", function () { filtro.situacao = fs.value || null; carregar(); });
    var ft = document.getElementById("f-tipo");
    ft.innerHTML = U.opcoes(API.TIPOS_AUDITORIA, "", "Tipo: todos");
    ft.addEventListener("change", function () { filtro.tipo = ft.value || null; carregar(); });
  }

  function porCodigo(c) { return lista.filter(function (a) { return a.codigo === c; })[0]; }
  document.getElementById("btn-nova").addEventListener("click", function () { Q.planejarAuditoria(projetoId, null, recarregar); });
  document.getElementById("tabela").addEventListener("click", function (ev) {
    var el;
    if ((el = ev.target.closest("[data-ver]"))) { ev.preventDefault(); Q.verAuditoria(porCodigo(el.getAttribute("data-ver"))); }
    else if ((el = ev.target.closest("[data-resultado]"))) Q.registrarResultado(porCodigo(el.getAttribute("data-resultado")), recarregar);
    else if ((el = ev.target.closest("[data-reprogramar]"))) Q.planejarAuditoria(projetoId, porCodigo(el.getAttribute("data-reprogramar")), recarregar);
  });

  GI.exportar.registrar(function () {
    var p = U.projeto(projetoId);
    return {
      titulo: "Programa de auditorias", subtitulo: p ? p.codigo + " " + p.nome : "Portfólio de projetos", arquivo: "auditorias-" + (p ? p.codigo : "portfolio"), orientacao: "l",
      blocos: [
        { tipo: "kpis", titulo: "Indicadores", itens: Array.prototype.map.call(document.querySelectorAll("#kpis .kpi"), function (k) {
          return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" }; }) },
        { tipo: "tabela", titulo: "Programa de auditorias", dados: tabela.exportacao() }
      ]
    };
  });

  Q.pronto().then(function (par) {
    meta = par && par.metaConformidadeAuditoriaPct || 90;
    projetoId = Q.projeto();
    montarFiltros();
    montarTabela();
    return carregar().then(function () { if (projetoId != null && U.acaoPendente() === "nova") Q.planejarAuditoria(projetoId, null, recarregar); });
  });
})(window.GI = window.GI || {});
