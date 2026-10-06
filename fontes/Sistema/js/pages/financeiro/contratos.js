/* ==========================================================================
   Gestão Financeira > Contratos (visão consolidada)
   Abas Contratos, Claims, Extensões de prazo, Marcos de pagamento e
   Avaliações, com os indicadores da administração contratual. Registros novos
   nascem na ficha do contrato; o contrato nasce da adjudicação (04 Suprimentos).
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt;
  var projetoId, dados = null, t = {}, previstos = null; /* previstos: pacotes de serviço (04 Suprimentos) = contratos previstos */
  var filtro = { busca: U.param("busca") || "", contrato: "" };

  function passa(x, campos) {
    if (filtro.contrato && x.contrato !== filtro.contrato && x.numero !== filtro.contrato) return false;
    return !filtro.busca || U.contem(campos.map(function (c) { return x[c] || ""; }).join(" "), filtro.busca);
  }

  function renderKpis() {
    var r = dados.resumo, i = dados.indicadores;
    var valor = dados.contratos.reduce(function (s, c) { return s + c.valorAtualCentavos; }, 0);
    document.getElementById("kpis").innerHTML = [
      U.kpi({ rotulo: "Contratos", valor: F.num(r.contratos), icone: "fileContract", cor: "primary", rodape: F.moedaCompacta(valor) + " em valor atual",
        esperado: { rotulo: "Previsto", valor: previstos == null ? "·" : F.num(previstos) } }),
      U.kpi({ rotulo: "Exposição de claims", moeda: i.exposicaoDaContratada, icone: "gavel", cor: i.exposicaoDaContratada ? "warning" : "success",
        esperado: { rotulo: "Esperado", valor: "0" },
        rodape: U.plural(r.claimsAbertos, "claim aberto", "claims abertos") }),
      U.kpi({ rotulo: "Notificados fora do prazo", valor: F.num(r.notificacoesForaDoPrazo), icone: "clock", cor: r.notificacoesForaDoPrazo ? "danger" : "success",
        esperado: { rotulo: "Esperado", valor: "0" },
        rodape: "risco de preclusão do pleito" }),
      U.kpi({ rotulo: "Marcos atrasados", valor: F.num(r.marcosAtrasados), icone: "flag", cor: r.marcosAtrasados ? "warning" : "success",
        esperado: { rotulo: "Esperado", valor: "0" },
        rodape: i.pagoPrevistoPct == null ? "" : "pago " + F.pct(i.pagoPrevistoPct) + " do previsto até hoje" }),
      U.kpi({ rotulo: "Extensão de prazo", valor: F.num(i.extensaoPct, 1), unidade: "%", icone: "calendarClock", cor: i.extensaoPct > 10 ? "warning" : "info",
        esperado: { rotulo: "Limite", valor: "≤ " + F.pct(10, 0) },
        rodape: F.num(i.diasConcedidos) + " de " + F.num(i.diasSolicitados) + " dias solicitados concedidos" }),
      U.kpi({ rotulo: "Contratadas C ou D", valor: F.num(r.contratadasCouD), icone: "star", cor: r.contratadasCouD ? "warning" : "success",
        esperado: { rotulo: "Esperado", valor: "0" },
        rodape: i.notaMedia == null ? "" : "nota média " + F.num(i.notaMedia, 1) })
    ].join("");
  }

  function render() {
    if (!dados.contratos.length) {
      document.getElementById("kpis").innerHTML = "";
      Object.keys(t).forEach(function (k) { t[k].atualizar([]); });
      ["contratos", "claims", "eot", "marcos", "aval"].forEach(function (k) { document.getElementById("n-" + k).textContent = "0"; document.getElementById("sub-" + k).textContent = ""; });
      return;
    }
    renderKpis();
    var i = dados.indicadores;
    var cts = dados.contratos.filter(function (c) { return passa(c, ["numero", "empresa", "objeto", "modalidade"]); });
    var cls = dados.claims.filter(function (c) { return passa(c, ["codigo", "contrato", "descricao", "causa", "tipo", "direcao"]); });
    var eot = dados.extensoes.filter(function (e) { return passa(e, ["codigo", "contrato", "evento", "claimRef", "marcoAfetado"]); });
    var mar = dados.marcos.filter(function (m) { return passa(m, ["numero", "contrato", "descricao", "criterio"]); });
    var ava = dados.avaliacoes.filter(function (a) { return passa(a, ["contrato", "empresa", "periodo", "comentario"]); });
    t.contratos.atualizar(cts); t.claims.atualizar(cls); t.eot.atualizar(eot); t.marcos.atualizar(mar); t.aval.atualizar(ava);
    document.getElementById("n-contratos").textContent = cts.length;
    document.getElementById("n-claims").textContent = cls.length;
    document.getElementById("n-eot").textContent = eot.length;
    document.getElementById("n-marcos").textContent = mar.length;
    document.getElementById("n-aval").textContent = ava.length;
    document.getElementById("sub-contratos").textContent = "Valor atual = original + aditivos; saldo = valor atual menos medido aprovado";
    document.getElementById("sub-claims").textContent = "Taxa de reconhecimento " + (i.taxaReconhecimento == null ? "·" : F.pct(i.taxaReconhecimento)) +
      " · tempo médio de resolução " + (i.tempoMedioResolucao == null ? "·" : U.plural(i.tempoMedioResolucao, "dia")) +
      " · back-charges em aberto " + F.moedaCompacta(i.exposicaoDoContratante);
    document.getElementById("sub-eot").textContent = F.num(i.diasSolicitados) + " dias solicitados x " + F.num(i.diasConcedidos) + " concedidos · " +
      F.pct(i.extensaoPct) + " da duração original dos contratos";
    document.getElementById("sub-marcos").textContent = "Aprovado não faturado " + F.moedaCompacta(i.aprovadoNaoFaturado) + " · pago x previsto até hoje " +
      (i.pagoPrevistoPct == null ? "·" : F.pct(i.pagoPrevistoPct)) + " · marco só é aprovado com evidência";
    document.getElementById("sub-aval").textContent = "Nota ponderada de 0 a 100 com os pesos gravados em cada avaliação · nota 1 ou 2 em algum critério exige plano de melhoria";
  }

  function carregar() {
    return Promise.all([GI.api.financeiro.consolidadoContratos(projetoId), GI.api.suprimentos.pacotes(projetoId)]).then(function (rr) {
      var r = rr[0];
      dados = r; previstos = (rr[1] || []).filter(function (p) { return p.tipo === "Serviço"; }).length;
      var sel = document.getElementById("f-contrato");
      sel.innerHTML = U.opcoes(r.contratos.map(function (c) { return { valor: c.numero, texto: c.numero + " " + c.empresa }; }), filtro.contrato, "Todos os contratos");
      render();
    });
  }

  /* Portfólio: coluna Projeto (pelo contrato do registro) */
  function projDoContrato(numero) {
    var c = dados ? dados.contratos.filter(function (x) { return x.numero === numero; })[0] : null;
    return c ? c.projetoId : null;
  }
  function colProj(campoContrato) {
    if (projetoId != null) return [];
    return [U.colunaProjeto("_p", { valor: function (x) { return U.codigoProjeto(campoContrato ? projDoContrato(x[campoContrato]) : x.projetoId); },
      html: function (x) { return U.esc(U.codigoProjeto(campoContrato ? projDoContrato(x[campoContrato]) : x.projetoId)); } })];
  }
  function criarTabelas() {
    t.contratos = GI.tabela.criar("t-contratos", {
      porPagina: 20, legenda: "Contratos", vazio: "Nenhum contrato encontrado.", ordem: { coluna: "numero", direcao: "asc" },
      colunas: colProj(null).concat([
        { id: "numero", titulo: "Nº", classe: "nowrap", html: function (c) { return "<b>" + GI.fin.linkContrato(c.numero) + "</b>"; } },
        { id: "empresa", titulo: "Contratada", html: function (c) { return '<div class="cell-title"><b>' + U.esc(c.empresa) + "</b><small>" + U.esc(c.objeto + " · " + c.modalidade) + "</small></div>"; } },
        { id: "modalidade", titulo: "Modalidade", oculta: true },
        { id: "valorAtualCentavos", titulo: "Valor atual", tipo: "moeda" },
        { id: "medidoPct", titulo: "Medido", tipo: "pct",
          html: function (c) { return '<div class="progress-row"><div class="progress progress--sm" role="progressbar" aria-valuenow="' + c.medidoPct + '" aria-valuemin="0" aria-valuemax="100" aria-label="Medido"><span class="progress__bar" style="--value: ' + Math.min(100, c.medidoPct) + '%"></span></div><span class="num">' + F.pct(c.medidoPct) + "</span></div>"; } },
        { id: "saldoCentavos", titulo: "Saldo a faturar", tipo: "moeda" },
        { id: "terminoVigente", titulo: "Término vigente", tipo: "data",
          html: function (c) { return U.esc(F.data(c.terminoVigente)) + (c.diasAditados ? '<br><span class="text-small valor--negativo">+' + U.plural(c.diasAditados, "dia") + "</span>" : ""); } },
        { id: "claimsAbertos", titulo: "Claims abertos", tipo: "num", html: function (c) { return c.claimsAbertos ? U.badge(F.num(c.claimsAbertos), "warning") : "0"; } },
        { id: "avaliacao", titulo: "Última avaliação", valor: function (c) { return c.ultimaAvaliacao ? c.ultimaAvaliacao.nota : null; },
          html: function (c) { return c.ultimaAvaliacao ? GI.fin.classe(c.ultimaAvaliacao.classe) + ' <span class="num">' + F.num(c.ultimaAvaliacao.nota) + "</span>" : ""; },
          exportar: function (c) { return c.ultimaAvaliacao ? c.ultimaAvaliacao.classe + " (" + c.ultimaAvaliacao.nota + ")" : ""; } }
      ])
    });
    t.claims = GI.tabela.criar("t-claims", {
      porPagina: 20, compacta: true, legenda: "Claims", vazio: "Nenhum claim encontrado.", ordem: { coluna: "codigo", direcao: "desc" },
      colunas: colProj("contrato").concat([
        { id: "codigo", titulo: "Código", html: function (c) { return "<b>" + U.esc(c.codigo) + '</b><br><span class="text-small">' + GI.fin.linkContrato(c.contrato) + "</span>"; } },
        { id: "direcao", titulo: "Direção / tipo", valor: function (c) { return c.direcao + " · " + c.tipo; },
          html: function (c) { return '<div class="cell-title"><b>' + U.esc(c.direcao) + "</b><small>" + U.esc(c.tipo + " · " + c.causa) + "</small></div>"; } },
        { id: "descricao", titulo: "Descrição" },
        { id: "notificacao", titulo: "Notificação", tipo: "data",
          html: function (c) { return U.esc(F.data(c.notificacao)) + '<br><span class="text-small ' + (c.foraDoPrazo ? "valor--negativo" : "text-muted") + '">' + U.plural(c.diasParaNotificar, "dia") + " após o evento" + (c.foraDoPrazo ? " · fora do prazo" : "") + "</span>"; } },
        { id: "pleiteadoCentavos", titulo: "Pleiteado", tipo: "moeda",
          html: function (c) { return U.esc(F.moeda(c.pleiteadoCentavos)) + (c.diasPleiteados ? '<br><span class="text-small text-muted">' + U.plural(c.diasPleiteados, "dia") + "</span>" : ""); } },
        { id: "reconhecidoCentavos", titulo: "Reconhecido", tipo: "moeda",
          html: function (c) { return c.reconhecidoCentavos == null ? "" : U.esc(F.moeda(c.reconhecidoCentavos)) + (c.diasReconhecidos ? '<br><span class="text-small text-muted">' + U.plural(c.diasReconhecidos, "dia") + "</span>" : ""); } },
        { id: "situacao", titulo: "Situação", html: function (c) { return GI.fin.situacao(c.situacao); } }
      ]),
      classeLinha: function (c) { return c.codigo === filtro.busca ? "is-selected" : ""; }
    });
    t.eot = GI.tabela.criar("t-eot", {
      porPagina: 20, legenda: "Extensões de prazo", vazio: "Nenhuma extensão de prazo encontrada.", ordem: { coluna: "codigo", direcao: "desc" },
      colunas: colProj("contrato").concat([
        { id: "codigo", titulo: "Código", html: function (e) { return "<b>" + U.esc(e.codigo) + '</b><br><span class="text-small">' + GI.fin.linkContrato(e.contrato) + "</span>"; } },
        { id: "evento", titulo: "Evento causador", html: function (e) { return U.esc(e.evento) + (e.claimRef ? '<br><span class="text-small text-muted">' + U.esc(e.claimRef) + "</span>" : ""); } },
        { id: "diasSolicitados", titulo: "Dias solicitados", tipo: "num" },
        { id: "diasConcedidos", titulo: "Dias concedidos", tipo: "num" },
        { id: "classificacao", titulo: "Classificação" },
        { id: "marcoAfetado", titulo: "Marco afetado" },
        { id: "situacao", titulo: "Situação", html: function (e) { return GI.fin.situacao(e.situacao); } }
      ])
    });
    t.marcos = GI.tabela.criar("t-marcos", {
      porPagina: 20, legenda: "Marcos de pagamento", vazio: "Nenhum marco encontrado.", ordem: { coluna: "prevista", direcao: "asc" },
      colunas: colProj("contrato").concat([
        { id: "contrato", titulo: "Contrato", html: function (m) { return GI.fin.linkContrato(m.contrato); } },
        { id: "numero", titulo: "Marco", html: function (m) { return '<div class="cell-title"><b>' + U.esc(m.numero + " " + m.descricao) + "</b><small>" + U.esc("Aceite: " + m.criterio) + "</small></div>"; },
          valor: function (m) { return m.numero + " " + m.descricao; } },
        { id: "pct", titulo: "%", tipo: "pct", casas: 0 },
        { id: "valorCentavos", titulo: "Valor", tipo: "moeda" },
        { id: "prevista", titulo: "Prevista", tipo: "data",
          html: function (m) { return U.esc(F.data(m.prevista)) + (m.atrasado ? '<br><span class="text-small valor--negativo">' + U.plural(m.diasAtraso, "dia") + " de atraso</span>" : ""); } },
        { id: "conclusao", titulo: "Conclusão", tipo: "data" },
        { id: "situacao", titulo: "Situação", html: function (m) { return GI.fin.situacao(m.situacao); } }
      ]),
      classeLinha: function (m) { return m.atrasado ? "is-alert" : ""; }
    });
    t.aval = GI.tabela.criar("t-aval", {
      porPagina: 20, legenda: "Avaliações de desempenho", vazio: "Nenhuma avaliação encontrada.", ordem: { coluna: "periodo", direcao: "desc" },
      colunas: colProj("contrato").concat([
        { id: "contrato", titulo: "Contrato", html: function (a) { return GI.fin.linkContrato(a.contrato) + '<br><span class="text-small text-muted">' + U.esc(a.empresa) + "</span>"; } },
        { id: "periodo", titulo: "Período", html: function (a) { return U.esc(U.mesCurto(a.periodo)); }, exportar: function (a) { return U.mesCurto(a.periodo); } },
        { id: "tipo", titulo: "Tipo" },
        { id: "nota", titulo: "Nota", tipo: "num", html: function (a) { return "<b>" + F.num(a.nota) + "</b>"; } },
        { id: "classe", titulo: "Classe", html: function (a) { return GI.fin.classe(a.classe, a.classeDescricao); } },
        { id: "exigePlano", titulo: "Plano de melhoria", valor: function (a) { return a.exigePlano ? "Exigido" : ""; },
          html: function (a) { return a.exigePlano ? U.badge("Exigido", "warning") : ""; } },
        { id: "comentario", titulo: "Comentário" },
        { id: "avaliador", titulo: "Avaliador", valor: function (a) { return U.pessoa(a.avaliadorId); } }
      ])
    });
  }

  GI.exportar.registrar(function () {
    var p = U.projeto(projetoId);
    return {
      titulo: "Contratos: administração contratual", subtitulo: p ? p.codigo + " " + p.nome : "Portfólio de projetos", arquivo: "contratos-" + (p ? p.codigo : "portfolio"), orientacao: "l",
      blocos: [
        { tipo: "kpis", titulo: "Indicadores", itens: Array.prototype.map.call(document.querySelectorAll("#kpis .kpi"), function (k) {
            return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" };
          }) },
        { tipo: "tabela", titulo: "Contratos", dados: t.contratos.exportacao() },
        { tipo: "tabela", titulo: "Claims", dados: t.claims.exportacao() },
        { tipo: "tabela", titulo: "Extensões de prazo", dados: t.eot.exportacao() },
        { tipo: "tabela", titulo: "Marcos de pagamento", dados: t.marcos.exportacao() },
        { tipo: "tabela", titulo: "Avaliações de desempenho", dados: t.aval.exportacao() }
      ]
    };
  });

  GI.util.pronto().then(function () {
    projetoId = GI.api.projetoAtualId();   /* null = Portfólio */
    criarTabelas();
    var busca = document.getElementById("busca");
    busca.value = filtro.busca;
    busca.addEventListener("input", U.debounce(function () { filtro.busca = busca.value.trim(); render(); }, 200));
    document.getElementById("f-contrato").addEventListener("change", function (ev) { filtro.contrato = ev.target.value; render(); });
    /* Link vindo de outra tela: abre a aba do registro */
    var aba = U.param("aba") || (/^CLM-/.test(filtro.busca) ? "claims" : /^EOT-/.test(filtro.busca) ? "eot" : null);
    if (aba && document.getElementById("a-" + aba)) GI.ui.selecionarAba(document.getElementById("a-" + aba));
    return carregar();
  });
})(window.GI = window.GI || {});
