/* ==========================================================================
   HSE > Horas trabalhadas (HHT) (07)
   Base de todas as taxas reativas (TF, TRIF, TG); registro mensal por
   empresa (efetivo médio e HHT), com upsert por mês e empresa.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt, H = GI.hse, API = GI.api.hse;
  var projetoId, tabela, lista = [], contratos = [];

  /* Meses esperados com registro: do início de cada projeto até o mês de referência
     (ou o término, se anterior), sem repetir meses na visão de portfólio. */
  function mesesEsperados() {
    var ref = GI.api.referencia().slice(0, 7), set = {};
    GI.api.portfolio.projetos().filter(function (p) { return projetoId == null || p.id === projetoId; }).forEach(function (p) {
      if (!p.inicio) return;
      var fim = p.terminoPrevisto && p.terminoPrevisto.slice(0, 7) < ref ? p.terminoPrevisto.slice(0, 7) : ref;
      var a = +p.inicio.slice(0, 4), m = +p.inicio.slice(5, 7);
      for (var mes = p.inicio.slice(0, 7); mes <= fim; mes = a + "-" + (m < 10 ? "0" : "") + m) {
        set[mes] = true;
        m += 1; if (m > 12) { m = 1; a += 1; }
      }
    });
    return Object.keys(set).length;
  }

  function kpis() {
    var hht12 = lista.reduce(function (s, r) { return s + r.hht; }, 0);
    var mesesSet = {}; lista.forEach(function (r) { mesesSet[r.mes] = true; });
    var meses = Object.keys(mesesSet);
    var ultimoMes = meses.sort()[meses.length - 1];
    var efetivoUltimoMes = lista.filter(function (r) { return r.mes === ultimoMes; }).reduce(function (s, r) { return s + r.efetivoMedio; }, 0);
    var empresasSet = {}; lista.forEach(function (r) { empresasSet[r.empresaId] = true; });
    /* Empresas com contrato no escopo mais a gerenciadora: referência de quem deveria reportar HHT */
    var contratadas = {}; contratos.forEach(function (c) { if (c.empresaId != null) contratadas[c.empresaId] = true; });
    Object.keys(U.mapas.empresas).forEach(function (id) { if (U.mapas.empresas[id].tipo === "Gerenciadora") contratadas[id] = true; });
    var nContratadas = Object.keys(contratadas).length;
    /* Histograma de mão de obra previsto (linha de base de recursos) até o último mês registrado */
    var prevAcum = ultimoMes ? API.hhtPrevisto(projetoId, ultimoMes) : null, prevMes = ultimoMes ? API.hhtPrevisto(projetoId, ultimoMes, true) : null;
    document.getElementById("kpis").innerHTML = [
      U.kpi({ rotulo: "HHT total registrado", valor: F.num(hht12), icone: "clock", cor: "primary",
        esperado: { rotulo: "Previsto", valor: prevAcum ? F.num(prevAcum.hht) : "·" }, rodape: "histograma de mão de obra até " + (ultimoMes ? U.mesCurto(ultimoMes) : "·") }),
      U.kpi({ rotulo: "Meses com registro", valor: F.num(meses.length), icone: "calendarDays", cor: "info",
        esperado: { rotulo: "Esperado", valor: F.num(mesesEsperados()) } }),
      U.kpi({ rotulo: "Efetivo médio (último mês)", valor: ultimoMes ? F.num(efetivoUltimoMes) : "·", icone: "users", cor: "info",
        esperado: { rotulo: "Previsto", valor: prevMes ? F.num(prevMes.efetivo) : "·" },
        rodape: ultimoMes ? U.mesCurto(ultimoMes) : "" }),
      U.kpi({ rotulo: "Empresas com registro", valor: F.num(Object.keys(empresasSet).length), icone: "building", cor: "info",
        esperado: { rotulo: "Referência", valor: "de " + F.num(nContratadas) + " previstas" } })
    ].join("");
  }

  function montarTabela() {
    tabela = GI.tabela.criar("tabela", {
      porPagina: 20, legenda: "HHT por mês e empresa", vazio: "Nenhum registro de HHT.", ordem: { coluna: "mes", direcao: "desc" },
      colunas: (projetoId == null ? [U.colunaProjeto()] : []).concat([
        { id: "mes", titulo: "Mês", classe: "nowrap", valor: function (r) { return r.mes; }, html: function (r) { return U.mesCurto(r.mes) + "/" + r.mes.slice(0, 4); } },
        { id: "empresa", titulo: "Empresa", valor: function (r) { return U.empresa(r.empresaId); } },
        { id: "efetivoMedio", titulo: "Efetivo médio", tipo: "num", valor: function (r) { return r.efetivoMedio; } },
        { id: "hht", titulo: "HHT", tipo: "num", valor: function (r) { return r.hht; } },
        { id: "mediaHoras", titulo: "Média horas / pessoa", tipo: "num", ordenavel: false,
          valor: function (r) { return r.efetivoMedio ? Math.round(r.hht / r.efetivoMedio) : 0; },
          html: function (r) { return r.efetivoMedio ? F.num(Math.round(r.hht / r.efetivoMedio)) : "·"; } }
      ]),
      acoes: function (r) { return '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-editar="' + r.mes + "|" + r.empresaId + "|" + r.projetoId + '" aria-label="Editar registro" title="Editar">' + U.icone("edit") + "</button>"; }
    });
  }

  function carregar() {
    return Promise.all([API.hht({ projetoId: projetoId }), GI.api.financeiro.contratos(projetoId)]).then(function (res) {
      var r = res[0];
      lista = r; contratos = res[1] || [];
      kpis();
      tabela.atualizar(lista, true);
      document.getElementById("contagem").textContent = U.plural(lista.length, "registro encontrado", "registros encontrados");
    });
  }

  document.getElementById("btn-novo").addEventListener("click", function () { H.registrarHht(projetoId, function () { carregar(); }); });
  document.getElementById("tabela").addEventListener("click", function (ev) {
    var el = ev.target.closest("[data-editar]");
    if (!el) return;
    var partes = el.getAttribute("data-editar").split("|"), mes = partes[0], empresaId = Number(partes[1]);
    var pid = Number(partes[2]);
    var registro = lista.filter(function (r) { return r.mes === mes && r.empresaId === empresaId && r.projetoId === pid; })[0];
    if (registro) H.registrarHht(registro.projetoId, registro, function () { carregar(); });
  });

  GI.exportar.registrar(function () {
    return {
      titulo: "Horas trabalhadas (HHT)", subtitulo: U.projeto(projetoId) ? U.projeto(projetoId).codigo + " " + U.projeto(projetoId).nome : "Portfólio de projetos", arquivo: "hht-hse",
      blocos: [
        { tipo: "kpis", titulo: "Indicadores", itens: Array.prototype.map.call(document.querySelectorAll("#kpis .kpi"), function (k) {
          return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" }; }) },
        { tipo: "tabela", titulo: "HHT por mês e empresa", dados: tabela.exportacao() }
      ]
    };
  });

  GI.hse.pronto().then(function () {
    projetoId = GI.hse.projeto(function (id) { projetoId = id; carregar(); });
    montarTabela();
    return carregar().then(function () { if (projetoId != null && U.acaoPendente() === "novo") H.registrarHht(projetoId, function () { carregar(); }); });
  });
})(window.GI = window.GI || {});
