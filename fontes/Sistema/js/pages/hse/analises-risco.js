/* ==========================================================================
   HSE > Análises de risco: APR/JSA e HAZOP (07)
   Registro dos estudos e das recomendações; recomendação vira ação na
   Central quando o responsável solicita.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt, H = GI.hse, API = GI.api.hse;
  var projetoId, tabela, filtro = {}, abriuBusca = false;
  var ZERO = { rotulo: "Esperado", valor: "0" };

  function kpis(lista, totalEstudos) {
    var abertas = 0, atrasadas = 0, fechadas = 0, total = 0;
    lista.forEach(function (a) { abertas += a.abertas; atrasadas += a.atrasadas; fechadas += a.fechadas; total += a.recomendacoes.length; });
    document.getElementById("kpis").innerHTML = [
      U.kpi({ rotulo: "Estudos registrados", valor: F.num(lista.length), icone: "fileSearch", cor: "primary",
        esperado: { rotulo: "Referência", valor: "de " + F.num(totalEstudos) + " registrados" } }),
      U.kpi({ rotulo: "Recomendações abertas", valor: F.num(abertas), icone: "clock", cor: abertas ? "warning" : "success", esperado: ZERO }),
      U.kpi({ rotulo: "Recomendações atrasadas", valor: F.num(atrasadas), icone: "alertTriangle", cor: atrasadas ? "danger" : "success", esperado: ZERO }),
      U.kpi({ rotulo: "Recomendações fechadas", valor: total ? F.pct(fechadas / total * 100, 1) : "·", icone: "checkCircle", cor: "info", esperado: { rotulo: "Esperado", valor: F.pct(100, 0) } })
    ].join("");
  }

  function montarTabela() {
    tabela = GI.tabela.criar("tabela", {
      porPagina: 20, legenda: "Análises de risco", vazio: "Nenhum estudo encontrado.", ordem: { coluna: "data", direcao: "desc" },
      colunas: (projetoId == null ? [U.colunaProjeto()] : []).concat([
        { id: "codigo", titulo: "Nº", classe: "nowrap", valor: function (a) { return a.codigo; }, html: function (a) { return '<a href="#" data-ver="' + a.codigo + '">' + U.esc(a.codigo) + "</a>"; } },
        { id: "tipo", titulo: "Tipo", valor: function (a) { return a.tipo; }, html: function (a) { return U.badge(a.tipo === "HAZOP" ? "HAZOP" : "APR / JSA", a.tipo === "HAZOP" ? "purple" : "info"); } },
        { id: "area", titulo: "Área", valor: function (a) { return a.area; } },
        { id: "titulo", titulo: "Título", valor: function (a) { return a.titulo; } },
        { id: "data", titulo: "Data", tipo: "data", valor: function (a) { return a.data; } },
        { id: "participantes", titulo: "Participantes", tipo: "num", valor: function (a) { return a.participantesIds.length; } },
        { id: "recs", titulo: "Recomendações", ordenavel: false, valor: function (a) { return a.abertas; },
          html: function (a) { return U.badge(a.abertas + " aberta" + (a.abertas === 1 ? "" : "s"), a.atrasadas ? "danger" : (a.abertas ? "warning" : "success")) + " " + U.badge(a.fechadas + " fechada" + (a.fechadas === 1 ? "" : "s"), "neutral"); },
          exportar: function (a) { return a.abertas + " abertas (" + a.atrasadas + " atrasadas), " + a.fechadas + " fechadas"; } }
      ]),
      acoes: function (a) { return '<a class="btn btn--ghost btn--icon btn--sm" href="#" data-ver="' + a.codigo + '" title="Ver estudo" aria-label="Ver estudo">' + U.icone("eye") + "</a>"; }
    });
  }

  function carregar() {
    var filtrado = Object.keys(filtro).some(function (k) { return filtro[k]; });
    return Promise.all([
      API.analisesRisco(Object.assign({ projetoId: projetoId }, filtro)),
      /* Universo sem filtros: referência do card de contagem */
      filtrado ? API.analisesRisco({ projetoId: projetoId }) : null
    ]).then(function (r) {
      var lista = r[0];
      kpis(lista, (r[1] || lista).length);
      tabela.atualizar(lista, true);
      document.getElementById("contagem").textContent = U.plural(lista.length, "estudo encontrado", "estudos encontrados");
      if (!abriuBusca && filtro.busca) {
        abriuBusca = true;
        var exata = lista.filter(function (a) { return a.codigo === filtro.busca; })[0];
        if (exata) H.verEstudo(exata.codigo, function () { carregar(); });
      }
    });
  }

  function montarFiltros() {
    var busca = document.getElementById("busca");
    busca.value = U.param("busca") || "";
    filtro.busca = busca.value || null;
    busca.addEventListener("input", U.debounce(function () { filtro.busca = busca.value.trim() || null; carregar(); }, 250));

    var fTipo = document.getElementById("f-tipo");
    fTipo.innerHTML = '<option value="">Tipo: todos</option><option value="APR">APR / JSA</option><option value="HAZOP">HAZOP</option>';
    fTipo.addEventListener("change", function () { filtro.tipo = fTipo.value || null; carregar(); });

    var fAbertas = document.getElementById("f-abertas");
    fAbertas.addEventListener("change", function () { filtro.situacao = fAbertas.checked ? "abertas" : null; carregar(); });
  }

  document.getElementById("btn-novo").addEventListener("click", function () { H.novoEstudo(projetoId, function () { carregar(); }); });
  document.getElementById("tabela").addEventListener("click", function (ev) {
    var el = ev.target.closest("[data-ver]");
    if (el) { ev.preventDefault(); H.verEstudo(el.getAttribute("data-ver"), function () { carregar(); }); }
  });

  GI.exportar.registrar(function () {
    return {
      titulo: "Análises de risco (APR/HAZOP)", subtitulo: U.projeto(projetoId) ? U.projeto(projetoId).codigo + " " + U.projeto(projetoId).nome : "Portfólio de projetos", arquivo: "analises-risco-hse",
      blocos: [
        { tipo: "kpis", titulo: "Indicadores", itens: Array.prototype.map.call(document.querySelectorAll("#kpis .kpi"), function (k) {
          return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" }; }) },
        { tipo: "tabela", titulo: "Estudos", dados: tabela.exportacao() }
      ]
    };
  });

  GI.hse.pronto().then(function () {
    projetoId = GI.hse.projeto(function (id) { projetoId = id; carregar(); });
    montarFiltros();
    montarTabela();
    return carregar().then(function () { if (projetoId != null && U.acaoPendente() === "novo") H.novoEstudo(projetoId, function () { carregar(); }); });
  });
})(window.GI = window.GI || {});
