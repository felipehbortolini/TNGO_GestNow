/* ==========================================================================
   Qualidade > Não conformidades (06)
   Lista de RNC com filtros, KPIs e fluxo por etapa: Aberta > Em análise de causa >
   Ação corretiva > Verificação de eficácia > Encerrada. ?busca=RNC-... abre a ficha.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt, Q = GI.qld, API = GI.api.qualidade;
  var projetoId, tabela, lista = [], filtro = { situacao: "ativas" }, abriuBusca = false, parQ = {};

  function kpis() {
    var ativas = lista.filter(function (r) { return r.ativa; });
    var vencidas = lista.filter(function (r) { return r.vencida; });
    var verif = lista.filter(function (r) { return r.situacao === "Verificação de eficácia"; });
    var enc = lista.filter(function (r) { return r.situacao === "Encerrada"; });
    var tempo = enc.length ? Math.round(enc.reduce(function (s, r) { return s + r.diasAberta; }, 0) / enc.length) : null;
    var custo = lista.reduce(function (s, r) { return s + (r.custoNaoQualidadeCentavos || 0); }, 0);
    var registradas = lista.filter(function (r) { return r.situacao !== "Cancelada"; }).length;
    document.getElementById("kpis").innerHTML = [
      U.kpi({ rotulo: "RNC em aberto", valor: F.num(ativas.length), icone: "octagonAlert", cor: ativas.length ? "warning" : "success", esperado: { rotulo: "Esperado", valor: "0" },
        rodape: U.plural(ativas.filter(function (r) { return r.severidade === "Crítica"; }).length, "crítica", "críticas") }),
      U.kpi({ rotulo: "Prazo de tratamento vencido", valor: F.num(vencidas.length), icone: "clock", cor: vencidas.length ? "danger" : "success", esperado: { rotulo: "Esperado", valor: "0" }, rodape: "antes da verificação de eficácia" }),
      U.kpi({ rotulo: "Em verificação de eficácia", valor: F.num(verif.length), icone: "checkCircle", cor: "info",
        esperado: { rotulo: "Limite", valor: parQ.verificacaoEficaciaDias == null ? "·" : F.num(parQ.verificacaoEficaciaDias) + " dias" },
        rodape: U.plural(verif.filter(function (r) { return r.verificacaoVencida; }).length, "vencida", "vencidas") }),
      U.kpi({ rotulo: "Encerradas", valor: F.num(enc.length), icone: "shieldCheck", cor: "success", esperado: { rotulo: "Referência", valor: "de " + F.num(registradas) + " registradas" }, rodape: tempo == null ? "sem encerramento" : "tempo médio de " + tempo + " dias" }),
      U.kpi({ rotulo: "Custo da não qualidade", moeda: custo, icone: "coins", cor: custo ? "danger" : "success", esperado: { rotulo: "Esperado", valor: F.moedaCompacta(0) }, rodape: "retrabalho, reparo, ensaios e perdas" })
    ].join("");
  }

  function montarTabela() {
    tabela = GI.tabela.criar("tabela", {
      porPagina: 20, legenda: "Relatórios de não conformidade", vazio: "Nenhuma RNC encontrada.", ordem: { coluna: "data", direcao: "desc" },
      colunas: (projetoId == null ? [U.colunaProjeto()] : []).concat([
        { id: "codigo", titulo: "Nº", classe: "nowrap", fixa: true, html: function (r) { return '<a href="#" data-ver="' + U.esc(r.codigo) + '"><b>' + U.esc(r.codigo) + '</b></a><br><small class="text-muted">' + U.esc(F.data(r.data)) + "</small>"; } },
        { id: "data", titulo: "Data", tipo: "data", oculta: true },
        { id: "descricao", titulo: "Não conformidade", fixa: true,
          html: function (r) { return '<div class="cell-title"><b>' + U.esc(r.descricao) + "</b><small>" + U.esc(r.origem + (r.origemRef ? " " + r.origemRef : "") + " · " + r.disciplina + " · " + U.empresa(r.empresaId)) + "</small></div>"; },
          exportar: function (r) { return r.descricao; } },
        { id: "origem", titulo: "Origem", oculta: true, valor: function (r) { return r.origem + (r.origemRef ? " " + r.origemRef : ""); } },
        { id: "disciplina", titulo: "Disciplina", oculta: true },
        { id: "empresa", titulo: "Empresa", oculta: true, valor: function (r) { return U.empresa(r.empresaId); } },
        { id: "severidade", titulo: "Severidade", valor: function (r) { return { "Crítica": 3, "Maior": 2, "Menor": 1 }[r.severidade] || 0; },
          html: function (r) { return Q.severidade(r.severidade); }, exportar: function (r) { return r.severidade; } },
        { id: "situacao", titulo: "Situação", valor: function (r) { return r.situacao; },
          html: function (r) { return Q.situacaoRnc(r.situacao) + (r.proximaEtapa ? '<br><small class="text-muted">' + U.esc(r.proximaEtapa) + "</small>" : "") +
            (r.acoesTotal ? '<br><small class="' + (r.acoesAtrasadas ? "valor--negativo" : "text-muted") + '">' + U.esc(r.acoesAbertas + " de " + U.plural(r.acoesTotal, "ação aberta", "ações abertas") + (r.acoesAtrasadas ? " · " + U.plural(r.acoesAtrasadas, "atrasada", "atrasadas") : "")) + "</small>" : ""); },
          exportar: function (r) { return r.situacao; } },
        { id: "prazo", titulo: "Prazo", tipo: "data",
          html: function (r) { return U.esc(F.data(r.prazo)) + (r.vencida ? '<br><span class="text-small valor--negativo">vencido há ' + U.esc(U.plural(r.diasAtraso, "dia")) + "</span>" :
            r.verificacaoVencida ? '<br><span class="text-small valor--negativo">verificação vencida</span>' : ""); } },
        { id: "acoesCentral", titulo: "Ações na Central", tipo: "num", oculta: true, valor: function (r) { return r.acoesAbertas; },
          html: function (r) { return r.acoesTotal ? F.num(r.acoesAbertas) + " / " + F.num(r.acoesTotal) + '<br><small class="text-muted">abertas</small>' + (r.acoesAtrasadas ? '<br><small class="valor--negativo">' + U.esc(U.plural(r.acoesAtrasadas, "atrasada", "atrasadas")) + "</small>" : "") : '<span class="text-muted">·</span>'; },
          exportar: function (r) { return r.acoesAbertas + " de " + r.acoesTotal; } },
        { id: "disposicao", titulo: "Disposição", oculta: true, valor: function (r) { return r.disposicao || ""; } },
        { id: "custoNaoQualidadeCentavos", titulo: "Custo", tipo: "moeda", oculta: true }
      ]),
      classeLinha: function (r) { return r.vencida || r.severidade === "Crítica" && r.ativa ? "is-alert" : ""; },
      acoes: function (r) {
        return '<a class="btn btn--ghost btn--icon btn--sm" href="#" data-ver="' + U.esc(r.codigo) + '" title="Ver RNC" aria-label="Ver RNC ' + U.esc(r.codigo) + '">' + U.icone("eye") + "</a>" + Q.acoesRnc(r, true);
      }
    });
  }

  function carregar() {
    return Promise.all([API.rncs(Object.assign({ projetoId: projetoId }, filtro)), API.rncs({ projetoId: projetoId }), GI.api.parametros()]).then(function (res) {
      var vis = res[0];
      parQ = (res[2] || {}).qualidade || {};
      lista = res[1]; kpis();
      tabela.atualizar(vis, true);
      document.getElementById("contagem").textContent = U.plural(vis.length, "RNC encontrada", "RNCs encontradas") + " · prazo de tratamento pela severidade; ações corretivas na Central (origem RNC)";
      if (!abriuBusca && filtro.busca) {
        abriuBusca = true;
        var exata = vis.filter(function (r) { return r.codigo === filtro.busca; })[0];
        if (exata) Q.verRnc(exata.codigo, recarregar);
      }
    });
  }
  function recarregar() { return carregar(); }

  function montarFiltros() {
    var busca = document.getElementById("busca");
    busca.value = U.param("busca") || "";
    filtro.busca = busca.value || null;
    if (filtro.busca) filtro.situacao = null;
    busca.addEventListener("input", U.debounce(function () { filtro.busca = busca.value.trim() || null; carregar(); }, 250));
    var fs = document.getElementById("f-situacao");
    fs.innerHTML = U.opcoes([{ valor: "ativas", texto: "Situação: em aberto" }, { valor: "vencidas", texto: "Situação: vencidas" }]
      .concat(API.SITUACOES.map(function (s) { return { valor: s, texto: s }; })), filtro.situacao || "", "Situação: todas");
    fs.addEventListener("change", function () { filtro.situacao = fs.value || null; carregar(); });
    var fv = document.getElementById("f-severidade");
    fv.innerHTML = U.opcoes(API.SEVERIDADES, "", "Severidade: todas");
    fv.addEventListener("change", function () { filtro.severidade = fv.value || null; carregar(); });
    var fd = document.getElementById("f-disciplina");
    fd.innerHTML = U.opcoes(API.DISCIPLINAS, "", "Disciplina: todas");
    fd.addEventListener("change", function () { filtro.disciplina = fd.value || null; carregar(); });
  }

  document.getElementById("btn-nova").addEventListener("click", function () { Q.novaRnc(projetoId, recarregar); });
  document.getElementById("btn-colunas").addEventListener("click", function () { GI.tabela.escolherColunas(tabela); });
  document.getElementById("tabela").addEventListener("click", function (ev) {
    var el;
    if ((el = ev.target.closest("[data-ver]"))) { ev.preventDefault(); Q.verRnc(el.getAttribute("data-ver"), recarregar); }
    else if ((el = ev.target.closest("[data-rnc-acao]"))) Q.executarAcaoRnc(el.getAttribute("data-rnc-acao"), el.getAttribute("data-codigo"), recarregar);
  });

  GI.exportar.registrar(function () {
    var p = U.projeto(projetoId);
    return {
      titulo: "Não conformidades (RNC)", subtitulo: p ? p.codigo + " " + p.nome : "Portfólio de projetos", arquivo: "rnc-" + (p ? p.codigo : "portfolio"), orientacao: "l",
      blocos: [
        { tipo: "kpis", titulo: "Indicadores", itens: Array.prototype.map.call(document.querySelectorAll("#kpis .kpi"), function (k) {
          return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" }; }) },
        { tipo: "tabela", titulo: "Relatórios de não conformidade", dados: tabela.exportacao() }
      ]
    };
  });

  Q.pronto().then(function () {
    projetoId = Q.projeto();
    montarFiltros();
    montarTabela();
    return carregar().then(function () { if (projetoId != null && U.acaoPendente() === "nova") Q.novaRnc(projetoId, recarregar); });
  });
})(window.GI = window.GI || {});
