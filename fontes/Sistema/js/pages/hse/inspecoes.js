/* ==========================================================================
   HSE > Inspeções, observações e DDS (07)
   Indicadores proativos consolidados por mês: DDS, inspeções de checklist
   (itens conformes) e observações comportamentais; desvios (nível 5 da
   pirâmide) também entram aqui, sem registro individual.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt, H = GI.hse, API = GI.api.hse;
  var projetoId, tabela, lista = [], hht = [];

  function kpis() {
    var progSoma = lista.reduce(function (s, r) { return s + r.ddsProgramados; }, 0);
    var realSoma = lista.reduce(function (s, r) { return s + r.ddsRealizados; }, 0);
    var inspSoma = lista.reduce(function (s, r) { return s + r.itensInspecionados; }, 0);
    var confSoma = lista.reduce(function (s, r) { return s + r.itensConformes; }, 0);
    var obsSoma = lista.reduce(function (s, r) { return s + r.observacoes; }, 0);
    var desvSoma = lista.reduce(function (s, r) { return s + r.desvios; }, 0);
    /* Metas proativas por 10 mil HHT (parâmetros hse.metas) aplicadas ao HHT dos meses registrados */
    var metas = API.metas(), mesesReg = {}; lista.forEach(function (r) { mesesReg[r.projetoId + "|" + r.mes] = true; });
    var hhtReg = hht.filter(function (h) { return mesesReg[h.projetoId + "|" + h.mes]; }).reduce(function (s, h) { return s + h.hht; }, 0);
    var metaObs = Math.round(metas.observacoesPor10MilHht * hhtReg / 10000), metaDesv = Math.round(metas.desviosPor10MilHht * hhtReg / 10000);
    document.getElementById("kpis").innerHTML = [
      U.kpi({ rotulo: "DDS realizados", valor: progSoma ? F.pct(realSoma / progSoma * 100, 1) : "·", icone: "calendarDays", cor: "info", esperado: { rotulo: "Meta", valor: F.pct(100, 0) },
        rodape: F.num(realSoma) + " de " + F.num(progSoma) + " programados" }),
      U.kpi({ rotulo: "Conformidade em inspeções", valor: inspSoma ? F.pct(confSoma / inspSoma * 100, 1) : "·", icone: "clipboardCheck", cor: "info", esperado: { rotulo: "Esperado", valor: F.pct(100, 0) },
        rodape: F.num(confSoma) + " de " + F.num(inspSoma) + " itens" }),
      U.kpi({ rotulo: "Observações comportamentais", valor: F.num(obsSoma), icone: "eye", cor: hhtReg && obsSoma < metaObs ? "warning" : "primary",
        esperado: { rotulo: "Meta", valor: hhtReg ? "≥ " + F.num(metaObs) : "·" }, rodape: F.num(metas.observacoesPor10MilHht) + " por 10 mil HHT" }),
      U.kpi({ rotulo: "Desvios (nível 5)", valor: F.num(desvSoma), icone: "listChecks", cor: hhtReg && desvSoma < metaDesv ? "warning" : "primary",
        esperado: { rotulo: "Meta de relato", valor: hhtReg ? "≥ " + F.num(metaDesv) : "·" }, rodape: "atos e condições inseguras · " + F.num(metas.desviosPor10MilHht) + " por 10 mil HHT" })
    ].join("");
  }

  function montarTabela() {
    tabela = GI.tabela.criar("tabela", {
      porPagina: 20, legenda: "Registros mensais", vazio: "Nenhum mês registrado.", ordem: { coluna: "mes", direcao: "desc" },
      colunas: (projetoId == null ? [U.colunaProjeto()] : []).concat([
        { id: "mes", titulo: "Mês", classe: "nowrap", valor: function (r) { return r.mes; }, html: function (r) { return U.mesCurto(r.mes) + "/" + r.mes.slice(0, 4); } },
        { id: "dds", titulo: "DDS", ordenavel: false, valor: function (r) { return r.ddsProgramados ? r.ddsRealizados / r.ddsProgramados : 0; },
          html: function (r) { return F.num(r.ddsRealizados) + " / " + F.num(r.ddsProgramados) + (r.ddsProgramados ? " <small class=\"text-muted\">(" + F.pct(r.ddsRealizados / r.ddsProgramados * 100, 0) + ")</small>" : ""); },
          exportar: function (r) { return r.ddsRealizados + " / " + r.ddsProgramados; } },
        { id: "insp", titulo: "Inspeções", ordenavel: false, valor: function (r) { return r.itensInspecionados ? r.itensConformes / r.itensInspecionados : 0; },
          html: function (r) { return F.num(r.itensConformes) + " / " + F.num(r.itensInspecionados) + (r.itensInspecionados ? " <small class=\"text-muted\">(" + F.pct(r.itensConformes / r.itensInspecionados * 100, 0) + ")</small>" : ""); },
          exportar: function (r) { return r.itensConformes + " / " + r.itensInspecionados; } },
        { id: "observacoes", titulo: "Observações", tipo: "num", valor: function (r) { return r.observacoes; } },
        { id: "desvios", titulo: "Desvios", tipo: "num", valor: function (r) { return r.desvios; } }
      ]),
      acoes: function (r) { return '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-editar="' + r.mes + "|" + r.projetoId + '" aria-label="Editar mês" title="Editar">' + U.icone("edit") + "</button>"; }
    });
  }

  function carregar() {
    return Promise.all([API.hseMensal({ projetoId: projetoId }), API.hht({ projetoId: projetoId })]).then(function (res) {
      var r = res[0]; hht = res[1] || [];
      lista = r;
      kpis();
      tabela.atualizar(lista, true);
      document.getElementById("contagem").textContent = U.plural(lista.length, "mês registrado", "meses registrados");
    });
  }

  document.getElementById("btn-novo").addEventListener("click", function () { H.registrarMes(projetoId, null, function () { carregar(); }); });
  document.getElementById("tabela").addEventListener("click", function (ev) {
    var el = ev.target.closest("[data-editar]");
    if (!el) return;
    var partes = el.getAttribute("data-editar").split("|");
    var registro = lista.filter(function (r) { return r.mes === partes[0] && String(r.projetoId) === partes[1]; })[0];
    if (registro) H.registrarMes(registro.projetoId, registro, function () { carregar(); });
  });

  GI.exportar.registrar(function () {
    return {
      titulo: "Inspeções, observações e DDS", subtitulo: U.projeto(projetoId) ? U.projeto(projetoId).codigo + " " + U.projeto(projetoId).nome : "Portfólio de projetos", arquivo: "inspecoes-hse",
      blocos: [
        { tipo: "kpis", titulo: "Indicadores", itens: Array.prototype.map.call(document.querySelectorAll("#kpis .kpi"), function (k) {
          return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" }; }) },
        { tipo: "tabela", titulo: "Registros mensais", dados: tabela.exportacao() }
      ]
    };
  });

  GI.hse.pronto().then(function () {
    projetoId = GI.hse.projeto(function (id) { projetoId = id; carregar(); });
    montarTabela();
    return carregar().then(function () { if (projetoId != null && U.acaoPendente() === "novo") H.registrarMes(projetoId, null, function () { carregar(); }); });
  });
})(window.GI = window.GI || {});
