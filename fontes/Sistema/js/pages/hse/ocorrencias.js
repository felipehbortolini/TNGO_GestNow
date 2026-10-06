/* ==========================================================================
   HSE > Ocorrências (07)
   Registro, investigação, ações corretivas, tratamento e encerramento.
   Fluxo: Registrada -> Em investigação -> Ações definidas -> Em tratamento -> Encerrada.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt, H = GI.hse, API = GI.api.hse;
  var projetoId, tabela, filtro = {}, abriuBusca = false;
  var ZERO = { rotulo: "Esperado", valor: "0" }, paramHse = null;

  function kpis(lista, total) {
    var prazos = (paramHse && paramHse.prazos) || {};
    var abertas = lista.filter(function (o) { return o.situacao !== "Encerrada"; });
    var hipoAbertas = abertas.filter(function (o) { return o.hipo; }).length;
    var foraPrazo = lista.filter(function (o) {
      return (o.prazoComunicacao && o.prazoComunicacao.foraDoPrazo) || (o.prazoInvestigacao && o.prazoInvestigacao.foraDoPrazo) ||
        (o.prazoInvestigacao && o.prazoInvestigacao.vencido) || (o.prazoRelatorio && (o.prazoRelatorio.foraDoPrazo || o.prazoRelatorio.vencido));
    }).length;
    document.getElementById("kpis").innerHTML = [
      U.kpi({ rotulo: "Ocorrências no projeto", valor: F.num(lista.length), icone: "octagonAlert", cor: "primary",
        esperado: { rotulo: "Referência", valor: "de " + F.num(total) + " registradas" } }),
      U.kpi({ rotulo: "Em aberto", valor: F.num(abertas.length), icone: "clock", cor: abertas.length ? "warning" : "success", esperado: ZERO }),
      U.kpi({ rotulo: "Alto potencial (HiPo) em aberto", valor: F.num(hipoAbertas), icone: "star", cor: hipoAbertas ? "danger" : "success", esperado: ZERO }),
      U.kpi({ rotulo: "Fora do prazo (comunicação, investigação ou relatório)", valor: F.num(foraPrazo), icone: "alertTriangle", cor: foraPrazo ? "danger" : "success", esperado: ZERO,
        rodape: prazos.comunicacaoHoras != null ? "limites: " + F.num(prazos.comunicacaoHoras) + " h, " + F.num(prazos.investigacaoPreliminarHoras) + " h e " + F.num(prazos.relatorioFinalDias) + " dias" : "" })
    ].join("");
  }

  function acoesLinha(o) {
    var b = [];
    b.push('<a class="btn btn--ghost btn--icon btn--sm" href="#" data-ver="' + o.codigo + '" title="Ver ficha" aria-label="Ver ficha">' + U.icone("eye") + "</a>");
    if (o.situacao === "Registrada") b.push('<button type="button" class="btn btn--ghost btn--sm" data-investigar="' + o.codigo + '">' + U.icone("fileSearch") + "Investigar</button>");
    if (o.situacao === "Em investigação" || o.situacao === "Ações definidas") b.push('<button type="button" class="btn btn--ghost btn--sm" data-nova-acao="' + o.codigo + '">' + U.icone("plus") + "Ação</button>");
    if (o.situacao === "Ações definidas") b.push('<button type="button" class="btn btn--ghost btn--sm" data-iniciar="' + o.codigo + '">' + U.icone("refresh") + "Iniciar tratamento</button>");
    if (o.situacao === "Em tratamento") b.push('<button type="button" class="btn btn--ghost btn--sm" data-encerrar="' + o.codigo + '">' + U.icone("checkCircle") + "Encerrar</button>");
    return b.join("");
  }

  function montarTabela() {
    tabela = GI.tabela.criar("tabela", {
      porPagina: 20, legenda: "Ocorrências", vazio: "Nenhuma ocorrência encontrada.", ordem: { coluna: "dataHora", direcao: "desc" },
      colunas: (projetoId == null ? [U.colunaProjeto()] : []).concat([
        { id: "codigo", titulo: "Nº", classe: "nowrap", valor: function (o) { return o.codigo; },
          html: function (o) { return '<a href="#" data-ver="' + o.codigo + '">' + U.esc(o.codigo) + "</a>"; } },
        { id: "dataHora", titulo: "Data / hora", tipo: "data", valor: function (o) { return o.dataHora; },
          html: function (o) { return F.data(o.dataHora) + '<br><small class="text-muted">' + o.dataHora.slice(11, 16) + "</small>"; }, exportar: function (o) { return F.data(o.dataHora) + " " + o.dataHora.slice(11, 16); } },
        { id: "area", titulo: "Área", valor: function (o) { return o.area; } },
        { id: "empresa", titulo: "Empresa", valor: function (o) { return U.empresa(o.empresaId); } },
        { id: "tipo", titulo: "Tipo / nível", valor: function (o) { return o.tipo; },
          html: function (o) { return '<div class="cell-title"><b>' + U.esc(o.tipo) + "</b>" + H.nivelBadge(o) + "</div>"; }, exportar: function (o) { return o.tipo + (o.nivelNome ? " (" + o.nivelNome + ")" : ""); } },
        { id: "potencial", titulo: "Potencial", ordenavel: false, valor: function (o) { return o.potencialFaixa ? o.potencialFaixa.score : -1; },
          html: function (o) { return o.ambiental ? U.badge(o.severidadeAmbiental, "neutral") : H.potencial(o.potencialFaixa, o.potencial.p, o.potencial.i); },
          exportar: function (o) { return o.ambiental ? o.severidadeAmbiental : (o.potencialFaixa ? o.potencialFaixa.nome + " (P" + o.potencial.p + " x I" + o.potencial.i + ")" : ""); } },
        { id: "situacao", titulo: "Situação", valor: function (o) { return o.situacao; }, html: function (o) { return H.situacaoOcorrencia(o.situacao); } },
        { id: "prazo", titulo: "Prazos", ordenavel: false, valor: function () { return 0; },
          html: function (o) {
            var b = [];
            if (o.prazoComunicacao && o.prazoComunicacao.foraDoPrazo) b.push(U.badge("Comunicação fora do prazo", "danger"));
            if (o.prazoInvestigacao && (o.prazoInvestigacao.foraDoPrazo || o.prazoInvestigacao.vencido)) b.push(U.badge(o.prazoInvestigacao.vencido ? "Investigação vencida" : "Investigação fora do prazo", "danger"));
            if (o.prazoRelatorio && o.prazoRelatorio.exige && (o.prazoRelatorio.foraDoPrazo || o.prazoRelatorio.vencido)) b.push(U.badge(o.prazoRelatorio.vencido ? "Relatório final vencido" : "Relatório fora do prazo", "danger"));
            return b.join(" ") || '<span class="text-small text-muted">no prazo</span>';
          } }
      ]),
      acoes: acoesLinha
    });
  }

  function carregar() {
    var filtrado = Object.keys(filtro).some(function (k) { return filtro[k]; });
    return Promise.all([
      API.ocorrencias(Object.assign({ projetoId: projetoId }, filtro)),
      /* Universo sem filtros: referência do card de contagem */
      filtrado ? API.ocorrencias({ projetoId: projetoId }) : null
    ]).then(function (r) {
      var lista = r[0];
      kpis(lista, (r[1] || lista).length);
      tabela.atualizar(lista, true);
      document.getElementById("contagem").textContent = U.plural(lista.length, "ocorrência encontrada", "ocorrências encontradas");
      if (!abriuBusca && filtro.busca) {
        abriuBusca = true;
        var exata = lista.filter(function (o) { return o.codigo === filtro.busca; })[0];
        if (exata) H.verOcorrencia(exata.codigo);
      }
    });
  }

  function montarFiltros() {
    var busca = document.getElementById("busca");
    busca.value = U.param("busca") || "";
    filtro.busca = busca.value || null;
    busca.addEventListener("input", U.debounce(function () { filtro.busca = busca.value.trim() || null; carregar(); }, 250));

    var fSit = document.getElementById("f-situacao");
    fSit.innerHTML = '<option value="">Situação: todas</option>' + U.opcoes(API.SITUACOES.map(function (s) { return { valor: s, texto: s }; }));
    fSit.addEventListener("change", function () { filtro.situacao = fSit.value || null; carregar(); });

    var fTipo = document.getElementById("f-tipo");
    var tipos = [].concat(API.TIPOS_PIRAMIDE[1], API.TIPOS_PIRAMIDE[2], API.TIPOS_PIRAMIDE[3], API.TIPOS_PIRAMIDE[4], ["Ambiental"]);
    fTipo.innerHTML = '<option value="">Tipo: todos</option>' + U.opcoes(tipos.map(function (t) { return { valor: t, texto: t }; }));
    fTipo.addEventListener("change", function () { filtro.tipo = fTipo.value || null; carregar(); });

    var fHipo = document.getElementById("f-hipo");
    fHipo.addEventListener("change", function () { filtro.hipo = fHipo.checked || null; carregar(); });
  }

  document.getElementById("btn-nova").addEventListener("click", function () { H.novaOcorrencia(projetoId, function () { carregar(); }); });

  document.getElementById("tabela").addEventListener("click", function (ev) {
    var el;
    if ((el = ev.target.closest("[data-ver]"))) { ev.preventDefault(); H.verOcorrencia(el.getAttribute("data-ver")); }
    else if ((el = ev.target.closest("[data-investigar]"))) { H.investigar(el.getAttribute("data-investigar"), function () { carregar(); }); }
    else if ((el = ev.target.closest("[data-nova-acao]"))) { H.novaAcaoCorretiva(el.getAttribute("data-nova-acao"), function () { carregar(); }); }
    else if ((el = ev.target.closest("[data-iniciar]"))) { H.iniciarTratamento(el.getAttribute("data-iniciar"), function () { carregar(); }); }
    else if ((el = ev.target.closest("[data-encerrar]"))) { H.encerrarOcorrencia(el.getAttribute("data-encerrar"), function () { carregar(); }); }
  });

  GI.exportar.registrar(function () {
    return {
      titulo: "Ocorrências HSE", subtitulo: U.projeto(projetoId) ? U.projeto(projetoId).codigo + " " + U.projeto(projetoId).nome : "Portfólio de projetos", arquivo: "ocorrencias-hse",
      blocos: [
        { tipo: "kpis", titulo: "Indicadores", itens: Array.prototype.map.call(document.querySelectorAll("#kpis .kpi"), function (k) {
          return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" }; }) },
        { tipo: "tabela", titulo: "Ocorrências", dados: tabela.exportacao() }
      ]
    };
  });

  GI.hse.pronto().then(function (param) {
    paramHse = param;
    projetoId = GI.hse.projeto(function (id) { projetoId = id; carregar(); });
    montarFiltros();
    montarTabela();
    return carregar().then(function () { if (projetoId != null && U.acaoPendente() === "nova") H.novaOcorrencia(projetoId, function () { carregar(); }); });
  });
})(window.GI = window.GI || {});
