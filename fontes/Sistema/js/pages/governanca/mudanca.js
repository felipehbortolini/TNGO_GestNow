/* ==========================================================================
   Governança > Ficha da mudança (08). ?codigo=SM-TN-2026-0004
   Abas: Solicitação, Análise de impacto, Decisão, Implementação e Histórico.
   Os botões do cabeçalho seguem o fluxo e o papel (GI.gov.botoesSm).
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt, G = GI.gov, API = GI.api.governanca;
  var codigo = U.param("codigo"), s = null, raiz = document.getElementById("ficha");
  var abaAtual = U.param("aba") || "solicitacao";
  var tAcoes = null, tHist = null;
  var ABAS = [
    { id: "solicitacao", nome: "Solicitação", icone: "fileText" },
    { id: "analise", nome: "Análise de impacto", icone: "gauge" },
    { id: "decisao", nome: "Decisão", icone: "gavel" },
    { id: "implementacao", nome: "Implementação", icone: "listChecks" },
    { id: "historico", nome: "Histórico", icone: "history" }
  ];

  function recarregar() { return API.mudanca(codigo).then(function (x) { s = x; if (s) render(); }); }
  function dl(linhas) {
    return '<dl class="dl">' + linhas.filter(Boolean).map(function (l) {
      return "<dt>" + U.esc(l[0]) + "</dt><dd>" + (l[2] ? (l[1] || "·") : U.esc(l[1] == null || l[1] === "" ? "·" : l[1])) + "</dd>";
    }).join("") + "</dl>";
  }
  function link(tela, modulo, params, texto) { return '<a href="' + U.tela(modulo, tela, params) + '">' + U.esc(texto) + "</a>"; }
  function sp(t) { return "<span>" + U.esc(t) + "</span>"; }
  function btnAba(acao, icone, texto) { return '<button type="button" class="btn btn--secondary btn--sm" data-sm-acao="' + acao + '" data-codigo="' + U.esc(s.codigo) + '">' + U.icone(icone) + U.esc(texto) + "</button>"; }

  /* ---------------- Cabeçalho ---------------- */
  function cabecalho() {
    var p = U.projeto(s.projetoId) || {};
    var al = "";
    if (s.emergenciaPendente) al += G.alerta(s.ratificacaoVencida ? "danger" : "warning", "<b>Mudança emergencial em execução desde " + F.data(s.emergencia.inicio) + ".</b> " +
      sp("Ratificação pelo Comitê obrigatória até " + F.data(s.ratificacaoAte) + (s.ratificacaoVencida ? " (vencida)." : ".")));
    if (s.analiseVencida) al += G.alerta("warning", "<b>Análise de impacto vencida</b> " + sp("desde " + F.data(s.analise.prazo) + ". Responsável: " + U.pessoa(s.analise.responsavelId) + "."));
    if (s.situacao === "Adiada" && s.decisao) al += G.alerta("warning", "<b>Decisão adiada</b> " + sp("em " + F.data(s.decisao.data) + (s.decisao.reapresentarEm ? "; volta à pauta em " + F.data(s.decisao.reapresentarEm) : "") + "."));
    if (s.situacao === "Aprovada com condições" || (s.decisao && s.decisao.condicoes && s.aberta)) al += G.alerta("info", "<b>Condições da aprovação:</b> " + U.esc(s.decisao.condicoes));
    if (s.aprovada && s.exigeEac && s.eacRevisao == null) al += G.alerta("warning", "<b>Custo aprovado ainda não incorporado à EAC.</b> " +
      sp("Gere a nova revisão do orçamento em") + " " + link("eac", "financeiro", { projeto: s.projetoId }, "03 Gestão Financeira > EAC") + ".");
    if (s.aprovada && s.exigeEap && s.eapRevisao == null) al += G.alerta("warning", "<b>Impacto em escopo ainda não incorporado à EAP.</b> " +
      sp("Gere a nova revisão da estrutura em") + " " + link("eap", "planejamento", { projeto: s.projetoId }, "02 Planejamento > EAP") + ".");
    if (s.situacao === "Cancelada" && s.cancelamento) al += G.alerta("info", "<b>Solicitação cancelada</b> " + sp("em " + F.data(s.cancelamento.data) + " por " + U.pessoa(s.cancelamento.porId) + ": " + s.cancelamento.justificativa));
    var faixa = '<section class="faixa" aria-label="Identificação da mudança"><div>' +
      '<div class="faixa__codigo">' + U.esc(s.codigo) + " · " + U.esc(s.tipo) + "</div>" +
      '<div class="faixa__meta"><span>Origem: ' + U.esc(s.origem) + "</span><span>Solicitada em " + F.data(s.dataSolicitacao) + " por " + U.esc(U.pessoa(s.solicitanteId)) + "</span>" +
      (s.alcada ? "<span>Alçada: " + U.esc(s.alcada) + "</span>" : "") + "</div></div>" +
      '<div class="faixa__acoes faixa__sev">' + U.badge("Prioridade " + s.prioridade.toLowerCase(), s.prioridade === "Normal" ? "neutral" : s.prioridade === "Emergencial" ? "danger" : "warning") + G.situacaoSm(s.situacao) + "</div></section>";
    var titulo = '<div class="mb-4"><h2 class="section-title">' + U.esc(s.titulo) + '</h2><p class="text-small text-muted">Projeto ' + U.esc(p.codigo + " · " + p.nome) +
      (s.proximaEtapa ? " · Próxima etapa: <b>" + U.esc(s.proximaEtapa) + "</b>" : "") + "</p></div>";
    var b = G.botoesSm(s);
    return al + faixa + titulo + G.etapas(s) + (b ? '<div class="toolbar" role="group" aria-label="Ações da mudança">' + b + "</div>" : "");
  }

  /* ---------------- Abas ---------------- */
  function abaSolicitacao() {
    var linhas = [
      ["Número", s.codigo], ["Título", s.titulo], ["Tipo", s.tipo], ["Origem", s.origem], ["Prioridade", s.prioridade],
      ["Solicitante", U.pessoa(s.solicitanteId)], ["Data da solicitação", F.data(s.dataSolicitacao)], ["Descrição e justificativa", s.descricao],
      s.emergencia ? ["Execução emergencial", "Iniciada em " + F.data(s.emergencia.inicio) + ". " + s.emergencia.justificativa] : null,
      s.analise ? ["Análise de impacto", "Responsável " + U.pessoa(s.analise.responsavelId) + "; prazo " + F.data(s.analise.prazo)] : null,
      s.risco ? ["Risco de origem (05)", link("ficha", "riscos", { codigo: s.risco.codigo }, s.risco.codigo) + " " + U.esc(s.risco.titulo) + " (" + U.esc(s.risco.situacao) + ")", true] : null,
      s.riscosVinculados.length ? ["Riscos vinculados (05)", s.riscosVinculados.map(function (r) { return link("ficha", "riscos", { codigo: r.codigo }, r.codigo) + " " + U.esc(r.titulo); }).join("<br>"), true] : null,
      s.anexos && s.anexos.length ? ["Anexos", s.anexos.map(function (a) { return a.nome; }).join(", ")] : null,
      s.liberacao ? ["Liberação de reserva", U.esc(F.moeda(s.liberacao.valorCentavos) + " da reserva " + (s.liberacao.reserva === "Gerencial" ? "gerencial" : "de contingência") +
        (s.aprovada ? " (liberada na aprovação)" : " (liberada na aprovação do Comitê)")) + ' · <a href="' + U.tela("financeiro", "contingencia", { projeto: s.projetoId }) + '">Abrir Contingência</a>', true] : null
    ];
    return '<section class="card">' + dl(linhas) + "</section>" + secaoRemanejamento();
  }
  /* Transferências propostas entre itens da EAC (03): aplicadas só na aprovação */
  function secaoRemanejamento() {
    var l = s.remanejamentosDetalhe || [];
    if (!l.length) return "";
    var ap = s.remanejamentoAplicado;
    var linhas = l.map(function (t) {
      return "<tr><td>" + U.esc(t.origem) + "<br><small class=\"text-muted\">" + U.esc(t.origemDescricao) + "</small></td><td>" + U.esc(t.destino) + (t.novoItem ? " " + U.badge("Item novo", "info") : "") +
        "<br><small class=\"text-muted\">" + U.esc(t.destinoDescricao) + '</small></td><td class="num">' + U.esc(F.moeda(t.valorCentavos)) + '</td><td class="num">' +
        (t.saldoLivre == null ? "·" : '<span class="' + (t.saldoLivre < t.valorCentavos ? "valor--negativo" : "") + '">' + U.esc(F.moeda(t.saldoLivre)) + "</span>") + "</td></tr>";
    }).join("");
    return '<section class="card mt-4"><div class="card__header"><div><h3 class="card__title">Remanejamento na EAC (03)</h3><p class="card__subtitle">' +
      (ap ? "Aplicado na EAC em " + F.data(ap.data) + " (Rev " + ap.revisao + "), pela aprovação desta SM" : "Proposto: a aprovação desta SM aplica as transferências; o total do orçamento não muda") +
      '</p></div><a class="btn btn--ghost btn--sm" href="' + U.tela("financeiro", "eac", { projeto: s.projetoId }) + '">' + U.icone("arrowRight") + "Abrir EAC</a></div>" +
      '<div class="table-wrap"><table class="table"><thead><tr><th>Origem</th><th>Destino</th><th class="num">Valor</th><th class="num">Saldo livre na origem</th></tr></thead><tbody>' + linhas +
      '</tbody><tfoot><tr><td colspan="2"><b>Total remanejado</b></td><td class="num"><b>' + U.esc(F.moeda(s.remanejamentoTotal)) + "</b></td><td></td></tr></tfoot></table></div></section>";
  }
  function abaAnalise() {
    var im = s.impacto;
    var botao = s.situacao === "Em análise de impacto" && API.pode("Membro") ? btnAba("analise", "gauge", im ? "Continuar análise" : "Registrar análise")
      : (s.situacao === "Aguardando comitê" || s.situacao === "Adiada") && API.pode("Membro") ? btnAba("analise", "gauge", "Revisar análise") : "";
    var cab = '<div class="card__header"><div><h3 class="card__title">Análise de impacto</h3><p class="card__subtitle">' +
      (im && im.dataAnalise ? "Concluída em " + F.data(im.dataAnalise) + (im.analistaId ? " por " + U.esc(U.pessoa(im.analistaId)) : "") : im ? "Rascunho (não enviada para decisão)" : "Obrigatória antes da decisão") + "</p></div>" + botao + "</div>";
    if (!im) return '<section class="card">' + cab + U.vazio(s.situacao === "Registrada" ? "Inicie a análise de impacto para avaliar escopo, prazo, custo, qualidade, riscos, SMS e contrato." : "Análise ainda não registrada.", "gauge") + "</section>";
    var alc = s.alcada + (s.alcadaExigida && s.alcadaExigida !== s.alcada ? " (mínima exigida: " + s.alcadaExigida + "; elevada pelo analista)" : " (mínima exigida)");
    return '<section class="card">' + cab + '<div class="grid grid--2"><div>' + dl([
      ["Impacto em custo", G.custo(im.custoCentavos), true], ["Impacto em prazo", G.prazo(im.prazoDias) + " no caminho crítico", true],
      ["Marco contratual", im.afetaMarcoContratual ? "Afeta marco contratual" : "Sem impacto em marco contratual"],
      ["Alçada de decisão", alc], ["Limite do gerente do projeto", s.limiteGerenteCentavos != null ? F.moeda(s.limiteGerenteCentavos) : ""],
      ["Fonte do recurso", s.fonteRecurso || (im.custoCentavos > 0 ? "a definir" : "sem custo adicional")],
      s.fonteRecurso === "Reserva de contingência" && s.contingencia ? ["Reserva de contingência", "saldo de " + F.moeda(s.contingencia.saldo) + " sem esta SM (total " + F.moeda(s.contingencia.total) + ")"] : null
    ]) + "</div><div>" + dl([
      ["Escopo", im.escopo], ["Qualidade e especificação", im.qualidade], ["Riscos novos ou alterados", im.riscos], ["SMS", im.sms], ["Contrato", im.contrato],
      ["Itens da EAC", s.eacItensDetalhe.length ? s.eacItensDetalhe.map(function (x) { return U.esc(x.codigo + " " + x.descricao); }).join("<br>") : "", true],
      ["Atividades do cronograma", im.atividades]
    ]) + "</div></div></section>";
  }
  function abaDecisao() {
    var d = s.decisao;
    var botao = s.situacao === "Aguardando comitê" && API.pode("Gestor") ? btnAba("decidir", "gavel", "Registrar decisão") : s.situacao === "Adiada" && API.pode("Membro") ? btnAba("reapresentar", "refresh", "Reapresentar") : "";
    var cab = '<div class="card__header"><div><h3 class="card__title">' + (s.alcada === "Gerente do projeto" ? "Decisão do gerente do projeto" : "Decisão do Comitê de Controle de Mudanças") + '</h3><p class="card__subtitle">' +
      (d ? "Registrada em " + F.data(d.data) : s.situacao === "Aguardando comitê" ? "Aguardando decisão" : "Sem decisão") + "</p></div>" + botao + "</div>";
    var corpo = d ? dl([
      ["Decisão", G.situacaoSm(d.resultado), true], ["Data", F.data(d.data)], ["Alçada", s.alcada],
      ["Participantes", (d.participantesIds || []).map(function (id) { return U.pessoa(id); }).join(", ")],
      ["Justificativa", d.justificativa], d.condicoes ? ["Condições", d.condicoes] : null,
      d.reapresentarEm ? ["Reapresentar em", F.data(d.reapresentarEm)] : null,
      ["Ata da reunião", s.ata ? link("ata", "central-acoes", { id: s.ata.id }, "Ata " + s.ata.numero + " Rev " + s.ata.revisao) : "sem ata vinculada", true],
      d.ratificacao ? ["Ratificação", "Decisão ratificou mudança emergencial"] : null
    ]) : U.vazio(s.etapa < 2 ? "A decisão acontece depois da análise de impacto." : "Nenhuma decisão registrada.", "gavel");
    var ant = (s.decisoesAnteriores || []).map(function (x) {
      return '<li class="feed__item feed__item--warning"><span class="feed__icon">' + U.icone("clock") + '</span><span class="feed__body"><b>' + F.data(x.data) + " · " + U.esc(x.resultado) + '</b><span class="text-small">' + U.esc(x.justificativa || "") + "</span></span></li>";
    }).join("");
    return '<section class="card">' + cab + corpo + (ant ? '<h4 class="section-title mt-4">Decisões anteriores</h4><ul class="feed">' + ant + "</ul>" : "") + "</section>";
  }
  function abaImplementacao() {
    var e = s.encerramentoDetalhe;
    var resumo = dl([
      ["Início da implementação", s.implementacao && s.implementacao.inicio ? F.data(s.implementacao.inicio) : "não iniciada"],
      s.remanejamentoTotal ? ["Remanejamento na EAC (03)", s.remanejamentoAplicado ? link("eac", "financeiro", { projeto: s.projetoId }, "Aplicado em " + F.data(s.remanejamentoAplicado.data)) + " (" + U.esc(F.moeda(s.remanejamentoTotal)) + ")" : "aplicado na aprovação", true] : null,
      ["Nova revisão da EAC (03)", s.exigeEac ? (s.eacRevisao != null ? link("eac", "financeiro", { projeto: s.projetoId }, "Rev " + s.eacRevisao) + " (custo incorporado)" : (s.aprovada ? "pendente: " + link("eac", "financeiro", { projeto: s.projetoId }, "gerar revisão") : "após a aprovação")) : "sem impacto em custo", true],
      ["Nova revisão da EAP (02)", s.exigeEap ? (s.eapRevisao != null ? link("eap", "planejamento", { projeto: s.projetoId }, "Rev " + s.eapRevisao) + " (escopo incorporado)" : (s.aprovada ? "pendente: " + link("eap", "planejamento", { projeto: s.projetoId }, "gerar revisão") : "após a aprovação")) : "sem impacto em escopo", true],
      ["Aditivos de contrato (03)", s.aditivos.length ? s.aditivos.map(function (a) { return link("contrato", "financeiro", { numero: a.contrato }, a.contrato) + " " + U.esc(a.numero + " · " + F.moeda(a.valorCentavos) + (a.dias ? " · " + U.plural(a.dias, "dia") : "")); }).join("<br>") : "nenhum vinculado", true],
      ["Ações de implementação", s.acoesTotal ? U.plural(s.acoesTotal, "ação", "ações") + (s.acoesAbertas ? " · " + U.plural(s.acoesAbertas, "em aberto", "em aberto") : " · todas concluídas") : "nenhuma"],
      e ? ["Encerramento", F.data(e.data) + " por " + U.pessoa(e.porId) + (e.observacao ? ". " + e.observacao : "")] : null,
      e ? ["Linhas de base conferidas", [e.eacRevisao != null ? "EAC Rev " + e.eacRevisao : "", e.eapRevisao != null ? "EAP Rev " + e.eapRevisao : "", e.cronograma ? "cronograma e Curva S" : "", e.contrato ? "aditivo contratual" : "", e.riscos ? "riscos revisados" : ""].filter(Boolean).join(", ") || "sem linha de base afetada"] : null,
      e && e.licaoRef ? ["Lição aprendida (08)", link("licoes", "governanca", { busca: e.licaoRef }, e.licaoRef) + (s.licao ? " " + U.esc(s.licao.titulo) + " (" + U.esc(s.licao.situacao) + ")" : ""), true] : null
    ]);
    var botao = s.situacao === "Em implementação" && API.pode("Gestor") ? btnAba("encerrar", "lock", "Encerrar") : (s.situacao === "Aprovada" || s.situacao === "Aprovada com condições") && API.pode("Membro") ? btnAba("iniciarImplementacao", "arrowRight", "Iniciar implementação") : "";
    return '<section class="card"><div class="card__header"><div><h3 class="card__title">Implementação e linhas de base</h3><p class="card__subtitle">Nada altera linha de base sem SM aprovada; o encerramento confere as atualizações.</p></div>' + botao + "</div>" + resumo + "</section>" +
      '<section class="card card--flush mt-4"><div class="card__header"><div><h3 class="card__title">Ações vinculadas</h3><p class="card__subtitle">Registros da Central de Ações com origem Mudança; navegam de volta para esta ficha.</p></div></div><div id="t-acoes"></div></section>';
  }
  function abaHistorico() { return '<section class="card card--flush"><div id="t-hist"></div></section>'; }

  function render() {
    document.title = s.codigo + " · Governança | Gestão Integrada AMT";
    document.getElementById("titulo").textContent = "Mudança " + s.codigo;
    if (GI.layout) GI.layout.detalhe(s.codigo);
    var contagem = { implementacao: s.acoesTotal, historico: s.historicoExibicao.length };
    raiz.innerHTML = cabecalho() +
      '<div class="tabs mt-2" data-tabs role="tablist" aria-label="Seções da mudança">' + ABAS.map(function (a) {
        return '<button type="button" class="tab" role="tab" id="aba-' + a.id + '" aria-controls="p-' + a.id + '" aria-selected="' + (a.id === abaAtual) + '">' + U.icone(a.icone) + U.esc(a.nome) +
          (contagem[a.id] ? '<span class="tab__count">' + contagem[a.id] + "</span>" : "") + "</button>";
      }).join("") + "</div>" +
      '<section class="tab-panel" role="tabpanel" id="p-solicitacao" aria-labelledby="aba-solicitacao">' + abaSolicitacao() + "</section>" +
      '<section class="tab-panel" role="tabpanel" id="p-analise" aria-labelledby="aba-analise">' + abaAnalise() + "</section>" +
      '<section class="tab-panel" role="tabpanel" id="p-decisao" aria-labelledby="aba-decisao">' + abaDecisao() + "</section>" +
      '<section class="tab-panel" role="tabpanel" id="p-implementacao" aria-labelledby="aba-implementacao">' + abaImplementacao() + "</section>" +
      '<section class="tab-panel" role="tabpanel" id="p-historico" aria-labelledby="aba-historico">' + abaHistorico() + "</section>";
    tAcoes = GI.tabela.criar("t-acoes", {
      porPagina: 0, legenda: "Ações da mudança", vazio: s.aprovada ? "Nenhuma ação vinculada." : "As ações de implementação são criadas na aprovação.",
      colunas: [
        { id: "item", titulo: "Item", classe: "num", valor: function (a) { return Number(a.item) || 0; }, html: function (a) { return a.item ? U.esc(a.item) : "·"; }, exportar: function (a) { return a.item || ""; } },
        { id: "assunto", titulo: "Ação", valor: function (a) { return a.assunto; },
          html: function (a) { return '<div class="cell-title"><b>' + U.esc(a.assunto) + "</b><small>" + U.esc(a.descricao || "") + "</small></div>"; } },
        { id: "responsavel", titulo: "Responsável", valor: function (a) { return U.pessoa(a.responsavelId); } },
        { id: "prevista", titulo: "Prevista", tipo: "data", valor: function (a) { return a.replanejada || a.prevista; } },
        { id: "status", titulo: "Situação", valor: function (a) { return a.statusRotulo; },
          html: function (a) { return U.badge(a.statusRotulo, U.statusAcao(a.status), true) + (a.status === "atrasada" ? '<br><small class="text-muted">há ' + U.plural(a.diasAtraso, "dia") + "</small>" : ""); } }
      ],
      classeLinha: function (a) { return a.status === "atrasada" ? "is-alert" : ""; },
      acoes: function () { return '<a class="btn btn--ghost btn--icon btn--sm" href="' + U.tela("central-acoes", "acoes", { busca: s.codigo, status: "todos" }) + '" aria-label="Abrir na Central de Ações" title="Abrir na Central de Ações">' + U.icone("arrowRight") + "</a>"; }
    });
    tAcoes.atualizar(s.acoesLista.filter(function (a) { return a.ehAcao; }));
    tHist = GI.tabela.criar("t-hist", {
      porPagina: 20, legenda: "Histórico da mudança", compacta: true, ordem: { coluna: "quando", direcao: "desc" },
      colunas: [
        { id: "quando", titulo: "Quando", classe: "nowrap", valor: function (h) { return h.quando; },
          html: function (h) { return F.data(h.quando.slice(0, 10)) + " " + h.quando.slice(11, 16); }, exportar: function (h) { return F.data(h.quando.slice(0, 10)) + " " + h.quando.slice(11, 16); } },
        { id: "quem", titulo: "Quem", valor: function (h) { return h.porId ? U.pessoa(h.porId) : ""; } },
        { id: "texto", titulo: "O que aconteceu" }
      ]
    });
    tHist.atualizar(s.historicoExibicao);
    GI.ui.init(raiz);
  }

  raiz.addEventListener("tabs:change", function (ev) { abaAtual = ev.detail.id.slice(2); });
  raiz.addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-sm-acao]");
    if (b) G.acaoSm(b.getAttribute("data-sm-acao"), codigo, recarregar);
  });

  GI.exportar.registrar(function () {
    var im = s.impacto || {}, d = s.decisao;
    return {
      titulo: "Solicitação de mudança " + s.codigo, subtitulo: s.titulo, arquivo: "mudanca-" + s.codigo, orientacao: "p",
      blocos: [
        { tipo: "kpis", titulo: "Situação", itens: [
          { rotulo: "Situação", valor: s.situacao }, { rotulo: "Impacto em custo", valor: im.custoCentavos != null ? F.moeda(im.custoCentavos) : "a analisar" },
          { rotulo: "Impacto em prazo", valor: im.prazoDias != null ? U.plural(im.prazoDias, "dia") : "a analisar" }, { rotulo: "Alçada", valor: s.alcada || "·" },
          { rotulo: "Próxima etapa", valor: s.proximaEtapa || "·" }] },
        { tipo: "texto", titulo: "Solicitação", texto: "Tipo: " + s.tipo + ". Origem: " + s.origem + ". Prioridade: " + s.prioridade + ". Solicitante: " + U.pessoa(s.solicitanteId) +
          " em " + F.data(s.dataSolicitacao) + ". " + s.descricao },
        { tipo: "texto", titulo: "Análise de impacto", texto: s.impacto ? "Escopo: " + im.escopo + ". Qualidade: " + im.qualidade + ". Riscos: " + im.riscos + ". SMS: " + im.sms + ". Contrato: " + im.contrato +
          ". Marco contratual: " + (im.afetaMarcoContratual ? "afetado" : "sem impacto") + ". Fonte do recurso: " + (s.fonteRecurso || "sem custo adicional") + "." : "Não registrada." },
        { tipo: "texto", titulo: "Decisão", texto: d ? d.resultado + " em " + F.data(d.data) + " (" + s.alcada + "). Participantes: " + (d.participantesIds || []).map(function (id) { return U.pessoa(id); }).join(", ") +
          ". Justificativa: " + d.justificativa + (d.condicoes ? " Condições: " + d.condicoes : "") : "Sem decisão." },
        { tipo: "tabela", titulo: "Ações vinculadas", dados: tAcoes.exportacao() },
        { tipo: "tabela", titulo: "Histórico", dados: tHist.exportacao() }
      ]
    };
  });

  G.pronto().then(recarregar).then(function () {
    if (!s) raiz.innerHTML = U.vazio("Solicitação de mudança não encontrada.", "search", "Mudança não encontrada");
  });
})(window.GI = window.GI || {});
