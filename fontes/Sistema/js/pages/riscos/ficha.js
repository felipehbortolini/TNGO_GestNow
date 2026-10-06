/* ==========================================================================
   Gestão de Riscos > Ficha do risco (mockup 03)
   Abas: Identificação, Avaliação (somente leitura), Resposta e ações,
   Monitoramento (linha do tempo das revisões) e Histórico (auditoria).
   Botões do cabeçalho abrem os modais 10 a 15. ?codigo=RSK-TN-2026-0001
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt, S = GI.rsk, API = GI.api.riscos;
  var codigo = U.param("codigo"), r = null, raiz = document.getElementById("ficha");
  var abaAtual = U.param("aba") || "identificacao";
  var tAcoes = null, tHist = null;
  var ABAS = [
    { id: "identificacao", nome: "Identificação", icone: "fileText" },
    { id: "avaliacao", nome: "Avaliação", icone: "gauge" },
    { id: "resposta", nome: "Resposta e ações", icone: "target" },
    { id: "monitoramento", nome: "Monitoramento", icone: "calendarClock" },
    { id: "historico", nome: "Histórico", icone: "history" }
  ];

  function recarregar() { return API.risco(codigo).then(function (x) { r = x; if (r) render(); }); }
  function btn(id, icone, texto, primario) {
    return '<button type="button" class="btn btn--' + (primario ? "primary" : "secondary") + '" data-btn="' + id + '">' + U.icone(icone) + U.esc(texto) + "</button>";
  }
  function alerta(tipo, html) { return '<div class="alert alert--' + tipo + ' mb-4">' + U.icone(tipo === "info" ? "info" : "alertTriangle") + '<div class="alert__body">' + html + "</div></div>"; }
  function dl(linhas) {
    return '<dl class="dl">' + linhas.filter(Boolean).map(function (l) { return "<dt>" + U.esc(l[0]) + "</dt><dd>" + (l[2] ? l[1] : U.esc(l[1] == null || l[1] === "" ? "·" : l[1])) + "</dd>"; }).join("") + "</dl>";
  }
  function linkOrigem() {
    if (r.ata) return '<a href="' + U.tela("central-acoes", "ata", { id: r.ata.id }) + '">Ata ' + U.esc(r.ata.numero) + "</a>";
    var o = r.origem || "";
    var ped = o.match(/PED-\d{4}-\d{4}/), clm = o.match(/CLM-[A-Z0-9-]+/);
    if (ped) return U.esc(o.replace(ped[0], "")) + '<a href="' + U.tela("suprimentos", "diligenciamento", { pedido: ped[0] }) + '">' + ped[0] + "</a>";
    if (clm) return U.esc(o.replace(clm[0], "")) + '<a href="' + U.tela("financeiro", "contratos", { busca: clm[0] }) + '">' + clm[0] + "</a>";
    return U.esc(o);
  }
  function pi(av) { return av ? "P" + av.p + " " + S.nomeProb(av.p) + " x I" + av.i + " " + S.nomeImp(av.i) : ""; }

  /* ---------------- Cabeçalho ---------------- */
  function cabecalho() {
    var p = U.projeto(r.projetoId) || {};
    var gestor = API.pode("Gestor"), membro = API.pode("Membro");
    var al = "";
    function sp(t) { return "<span>" + U.esc(t) + "</span>"; }
    if (r.oculto) al += alerta("danger", "<b>Risco excluído</b> " + [sp("Excluído em " + F.data(r.exclusao.data) + " por " + U.pessoa(r.exclusao.porId) + "."), sp("Motivo: " + r.exclusao.motivo + "."),
      r.exclusao.observacao ? sp(r.exclusao.observacao) : ""].join(" "));
    if (!r.ativo && r.encerramento) {
      var e = r.encerramento;
      al += alerta("info", "<b>Risco encerrado</b> " + [
        sp("Encerrado em " + F.data(e.data) + " por " + U.pessoa(e.porId) + "."),
        sp("Motivo: " + (e.motivo === "Materializado" && r.natureza === "Oportunidade" ? "Capturada" : e.motivo) + "."),
        e.duplicadoDe ? sp("Duplicado de") + " " + S.linkFicha(e.duplicadoDe) : "",
        e.impactoRealPrazoDias != null ? sp("Impacto real: " + U.plural(e.impactoRealPrazoDias, "dia") + " e " + F.moeda(e.impactoRealCustoCentavos) + ".") : "",
        r.licao ? sp("Lição") + ' <a href="' + U.tela("governanca", "licoes", { busca: r.licao.codigo }) + '">' + U.esc(r.licao.codigo) + "</a> " + sp("(" + r.licao.situacao + ")") : "",
        r.smEncerramento ? sp("Mudança") + ' <a href="' + U.tela("governanca", "mudanca", { codigo: r.smEncerramento.codigo }) + '">' + U.esc(r.smEncerramento.codigo) + "</a> " + sp("(" + r.smEncerramento.situacao + ")") : ""
      ].filter(Boolean).join(" "));
    }
    if (r.ativo) {
      if (r.situacao === "Identificado") al += alerta("warning", "<b>Risco sem avaliação.</b> Avalie probabilidade e impacto para definir a severidade e a cadência de revisão.");
      if (r.planoPendente) al += alerta("warning", "<b>Plano de resposta aguardando aprovação</b> da gerência do projeto desde " + F.data(r.aprovacao.solicitadaEm) + ".");
      if (r.aprovacao && r.aprovacao.situacao === "Devolvido") al += alerta("warning", "<b>Plano devolvido pelo gestor</b> " + [sp("Devolvido em " + F.data(r.aprovacao.data) + "."), sp(r.aprovacao.comentario || ""), sp("Revise e salve o plano novamente.")].join(" "));
      if (r.gatilhoOcorridoEm) al += alerta("warning", "<b>Gatilho ocorreu</b> em " + F.data(r.gatilhoOcorridoEm) + ": reavaliação obrigatória.");
      if (r.revisaoVencida) al += alerta("warning", "<b>Revisão vencida</b> desde " + F.data(r.proximaRevisao) + " (cadência " + U.esc(S.cadencia(r.cadenciaDias)) + ").");
      if (r.exigeAcao && !r.acoes) al += alerta("warning", "<b>Risco " + U.esc(r.sevInerente.nome) + " sem ação vinculada.</b> O plano exige pelo menos uma ação.");
      if (r.temPlano && r.situacao === "Em tratamento" && r.acoes && !r.acoesAbertas) al += alerta("info", "Todas as ações foram concluídas. Reavalie o residual: concluir as ações não fecha o risco (encerramento é explícito).");
      if (r.pauta.length && !r.oculto) al += alerta("info", "<b>Na pauta de escalonamento:</b> " + U.esc(r.pauta.join(" · ")));
    }
    var faixa = '<section class="faixa" aria-label="Identificação do risco"><div>' +
      '<div class="faixa__codigo">' + U.esc(r.codigo) + " · " + U.esc(r.natureza) + "</div>" +
      '<div class="faixa__meta"><span>' + U.esc(r.categoriaCompleta) + "</span><span>Dono: " + U.esc(U.pessoa(r.donoId)) + "</span><span>Identificado em " + F.data(r.identificadoEm) + "</span></div></div>" +
      '<div class="faixa__acoes faixa__sev"><span>Inerente</span>' + S.sev(r.sevInerente, r.scoreInerente, r.natureza) + "<span>›</span><span>Residual</span>" + S.sev(r.sevResidual, r.scoreResidual, r.natureza) +
      S.situacao(r.situacao) + "</div></section>";
    var titulo = '<div class="mb-4"><h2 class="section-title">' + U.esc(r.titulo) + '</h2><p class="text-small text-muted">Projeto ' + U.esc(p.codigo + " · " + p.nome) + "</p></div>";
    var b = "";
    if (r.ativo && !r.oculto) {
      var prox = !r.avaliado ? "avaliar" : !r.temPlano ? "plano" : r.planoPendente && gestor ? "aprovar" : r.gatilhoOcorridoEm ? "avaliar" : r.revisaoVencida ? "revisar" : "";
      if (membro) {
        b += btn("editar", "edit", "Editar") + btn("avaliar", "gauge", "Avaliar", prox === "avaliar") + btn("plano", "target", "Plano de resposta", prox === "plano") +
          btn("acao", "plus", "Nova ação") + btn("revisar", "calendarClock", "Registrar revisão", prox === "revisar");
      }
      if (gestor && r.planoPendente) b += btn("aprovar", "checkCircle", "Aprovar plano", prox === "aprovar");
      if (gestor) b += btn("encerrar", "lock", "Encerrar");
    } else if (!r.ativo && !r.oculto && gestor) b += btn("reabrir", "refresh", "Reabrir");
    return al + faixa + titulo + (b ? '<div class="toolbar" role="group" aria-label="Ações do risco">' + b + "</div>" : "");
  }

  /* ---------------- Abas ---------------- */
  function abaIdentificacao() {
    var dono = U.mapas.pessoas[r.donoId] || {};
    return '<section class="card">' + dl([
      ["Número", r.codigo], ["Natureza", r.natureza], ["Categoria (RBS)", r.categoriaCompleta], ["Causa", r.causa], ["Evento (título)", r.titulo],
      ["Consequência", r.consequencia], ["Descrição", r.descricao], ["Dono do risco", dono.nome ? dono.nome + " (" + dono.funcao + ")" : ""],
      ["Identificado por", U.pessoa(r.identificadoPorId)], ["Identificado em", F.data(r.identificadoEm)], ["Origem", linkOrigem(), true],
      ["Gatilho (sinal de alerta)", r.gatilho], ["Projeto", r.projetoCodigo]
    ]) + "</section>";
  }
  function cardAval(rotulo, av, sv, score, vazio) {
    return '<div class="aval-card"><span class="aval-card__rotulo">' + U.esc(rotulo) + "</span>" + (av
      ? '<div class="aval-card__score"><b>' + score + "</b>" + S.sev(sv, null, r.natureza) + '</div><span class="aval-card__pi">' + U.esc(pi(av)) + "</span>"
      : '<span class="text-small text-muted">' + U.esc(vazio) + "</span>") + "</div>";
  }
  function abaAvaliacao() {
    var op = r.natureza === "Oportunidade";
    var dims = API.DIMENSOES.map(function (d) {
      var a = r.inerente && r.inerente.dimensoes ? r.inerente.dimensoes[d.id] : null, b = r.residual && r.residual.dimensoes ? r.residual.dimensoes[d.id] : null;
      return "<tr><td data-label=\"Dimensão\">" + U.esc(d.nome) + '</td><td data-label="Inerente" class="num">' + (a ? a + " " + U.esc(S.nomeImp(a)) : "·") +
        '</td><td data-label="Residual" class="num">' + (b ? b + " " + U.esc(S.nomeImp(b)) : "·") + "</td></tr>";
    }).join("");
    var faixaAlvo = API.legenda().filter(function (f) { return f.id === r.severidadeAlvo; })[0];
    return '<section class="card"><div class="card__header"><div><h3 class="card__title">Avaliação vigente</h3><p class="card__subtitle">Somente leitura; alterar exige o modal Avaliação, que grava justificativa e histórico.</p></div>' +
      (r.ativo && API.pode("Membro") ? '<button type="button" class="btn btn--secondary btn--sm" data-btn="avaliar">' + U.icone("gauge") + "Reavaliar</button>" : "") + "</div>" +
      '<div class="aval-grid">' + cardAval("Inerente (sem tratamento)", r.inerente, r.sevInerente, r.scoreInerente, "Ainda não avaliado.") +
      cardAval("Residual (com o plano)", r.residual, r.sevResidual, r.scoreResidual, r.temPlano ? "Plano registrado: avalie o residual." : "Habilitada depois do plano de resposta.") + "</div>" +
      '<div class="grid grid--2 mt-4"><div>' + dl([
        ["Dimensão de maior impacto", r.dimensao], [op ? "Benefício em prazo" : "Impacto em prazo", r.impactoPrazoDias ? U.plural(r.impactoPrazoDias, "dia") + (op ? " de antecipação" : " no caminho crítico") : "sem impacto"],
        [op ? "Benefício em custo" : "Impacto em custo", F.moeda(r.impactoCustoCentavos)],
        ["VME inerente", F.moeda(r.vmeInerenteCentavos)], ["VME atual", F.moeda(r.vmeCentavos) + (r.probabilidadePct != null ? " (" + r.probabilidadePct + "% x impacto em custo)" : "")],
        ["Severidade-alvo", faixaAlvo ? faixaAlvo.nome + " (até " + faixaAlvo.maximo + ")" : "sem plano"], ["Prazo para atingir o alvo", r.prazoAlvo ? F.data(r.prazoAlvo) + (r.diasAlvo != null ? " (" + (r.diasAlvo >= 0 ? "faltam " + U.plural(r.diasAlvo, "dia") : "vencido há " + U.plural(-r.diasAlvo, "dia")) + ")" : "") : ""],
        ["Risco à vida", r.riscoVida ? "Sim" : "Não"]
      ]) + '<p class="text-small text-muted mt-2">VME = probabilidade média da faixa x impacto em custo, calculado em centavos.' + (op ? " Oportunidade: o VME é benefício esperado e não soma na exposição." : "") + "</p></div>" +
      '<div><div class="table-wrap table-wrap--stack"><table class="table table--stack table--compact"><caption class="sr-only">Impacto por dimensão</caption><thead><tr><th>Dimensão</th><th class="num">Inerente</th><th class="num">Residual</th></tr></thead><tbody>' + dims +
      '</tbody></table></div><p class="text-small text-muted mt-2">Impacto do risco = maior valor entre as dimensões (pior caso).</p></div></div></section>';
  }
  function abaResposta() {
    var op = r.natureza === "Oportunidade";
    var aprov = !r.aprovacao || !r.aprovacao.exigida ? "Não exigida" : r.aprovacao.situacao === "Aprovado" ? "Aprovado por " + U.pessoa(r.aprovacao.porId) + " em " + F.data(r.aprovacao.data)
      : r.aprovacao.situacao === "Devolvido" ? "Devolvido em " + F.data(r.aprovacao.data) : "Pendente desde " + F.data(r.aprovacao.solicitadaEm);
    var reducao = r.vmeInerenteCentavos - r.vmeCentavos;
    var plano = r.temPlano ? '<p class="mb-4">' + U.esc(r.plano) + "</p>" + dl([
      ["Estratégia", r.estrategia], r.instrumento ? ["Instrumento", r.instrumento] : null,
      r.estrategia === "Evitar" ? ["Solicitação de mudança", r.sm ? '<a href="' + U.tela("governanca", "mudanca", { codigo: r.sm.codigo }) + '">' + U.esc(r.sm.codigo) + "</a> · " + U.esc(r.sm.titulo) + " (" + U.esc(r.sm.situacao) + ")" : "a registrar (ação na Central)", true] : null,
      ["Severidade-alvo", r.nomeAlvo + " até " + F.data(r.prazoAlvo) + (r.acimaAlvo ? (op ? " (abaixo do alvo)" : " (acima do alvo)") : " (alvo atingido)")],
      ["Custo da resposta", r.custoRespostaCentavos != null ? F.moeda(r.custoRespostaCentavos) : "não informado"],
      [op ? "Ganho esperado (VME)" : "Redução da exposição (VME)", r.scoreResidual != null ? F.moeda(Math.abs(reducao)) + " (" + F.moeda(r.vmeInerenteCentavos) + " para " + F.moeda(r.vmeCentavos) + ")" : "avaliar residual"],
      ["Responsável pelo plano", U.pessoa(r.responsavelPlanoId)], ["Aprovação da gerência do projeto", aprov]
    ]) : (r.respostaProposta ? '<p class="text-small">Resposta proposta na origem: <i>' + U.esc(r.respostaProposta) + "</i></p>" : "") + U.vazio("Plano de resposta ainda não definido.", "target");
    return '<section class="card"><div class="card__header"><div><h3 class="card__title">Plano de resposta</h3><p class="card__subtitle">' + (r.estrategia ? U.esc(r.estrategia) : "sem estratégia") + "</p></div>" +
      (r.ativo && API.pode("Membro") ? '<button type="button" class="btn btn--secondary btn--sm" data-btn="plano">' + U.icone("target") + "Plano de resposta</button>" : "") + "</div>" + plano + "</section>" +
      '<section class="card card--flush mt-4"><div class="card__header"><div><h3 class="card__title">Ações vinculadas</h3><p class="card__subtitle">Registros da Central de Ações com origem Risco; navegam de volta para esta ficha.</p></div>' +
      (r.ativo && API.pode("Membro") ? '<button type="button" class="btn btn--primary btn--sm" data-btn="acao">' + U.icone("plus") + "Nova ação</button>" : "") + '</div><div id="t-acoes"></div></section>';
  }
  var ICONE_AP = { "Risco reduzido": "arrowDown", "Risco agravado": "arrowUp", "Risco materializado": "alertTriangle", "Risco superado": "check", "Avaliação inicial": "gauge", "Sem mudança": "clock" };
  function abaMonitoramento() {
    var revs = r.revisoes || [];
    var itens = revs.map(function (v) {
      var sv = v.para != null ? API.legenda().filter(function (f) { return v.para >= f.minimo && v.para <= f.maximo; })[0] : null;
      var tipo = v.situacaoApurada === "Risco agravado" && r.natureza === "Ameaça" || v.gatilho ? "warning" : v.situacaoApurada === "Risco materializado" ? "danger" : v.situacaoApurada === "Risco reduzido" ? "info" : "";
      var tit = v.tipo === "inerente" ? "Avaliação inicial" : v.tipo === "residual" ? (v.de == null ? "Avaliação residual" : v.de === v.para ? "Avaliação residual sem mudança" : "Avaliação residual: de " + v.de + " para " + v.para) :
        v.situacaoApurada === "Sem mudança" ? "Sem mudança de severidade" : S.apurada(v.situacaoApurada, r.natureza) + (v.de !== v.para ? ": de " + v.de + " para " + v.para : "");
      return '<li class="feed__item' + (tipo ? " feed__item--" + tipo : "") + '"><span class="feed__icon">' + U.icone(v.gatilho ? "flag" : ICONE_AP[v.tipo === "inerente" ? "Avaliação inicial" : v.situacaoApurada] || "clock") + "</span>" +
        '<span class="feed__body"><b>' + F.data(v.data) + " · " + U.esc(tit) + '</b><span class="text-small">P' + v.p + " x I" + v.i + " = " + v.para + (sv ? " (" + U.esc(sv.nome) + ")" : "") + ". " + U.esc(v.texto) +
        (v.gatilho ? " <b>Gatilho ocorreu.</b>" : "") + '</span></span><span class="text-small text-muted">' + U.esc(U.pessoa(v.porId)) + "</span></li>";
    }).join("");
    var maxCad = r.cadenciaMaxDias;
    return '<section class="card"><div class="card__header"><div><h3 class="card__title">Revisões</h3><p class="card__subtitle">' +
      (r.cadenciaDias ? "Cadência: " + U.esc(S.cadencia(r.cadenciaDias)) + (r.sevAtual ? " (" + U.esc(r.sevAtual.nome.toLowerCase()) + ": máximo de " + maxCad + " dias)" : "") : "Sem cadência definida (risco não avaliado)") + "</p></div>" +
      (r.ativo && API.pode("Membro") ? '<button type="button" class="btn btn--secondary btn--sm" data-btn="revisar">' + U.icone("calendarClock") + "Registrar revisão</button>" : "") + "</div>" +
      (itens ? '<ul class="feed">' + itens + "</ul>" : U.vazio("Nenhuma revisão registrada.", "calendarClock")) +
      '<p class="text-small text-muted mt-4">' + (r.ativo ? (r.proximaRevisao ? "Próxima revisão: <b>" + F.data(r.proximaRevisao) + "</b>. " : "") + "O sistema alerta na Home e no painel quando a data vence. Cadência sugerida pela severidade; o gestor pode antecipar, nunca postergar."
        : "Risco fora da carteira ativa: sem revisões programadas.") + "</p></section>";
  }
  function abaHistorico() { return '<section class="card card--flush"><div id="t-hist"></div></section>'; }

  function render() {
    document.title = r.codigo + " · Riscos | Gestão Integrada AMT";
    document.getElementById("titulo").textContent = "Risco " + r.codigo;
    if (GI.layout) GI.layout.detalhe(r.codigo);
    var contagem = { resposta: r.acoes, monitoramento: (r.revisoes || []).length, historico: r.historico.length };
    raiz.innerHTML = cabecalho() +
      '<div class="tabs mt-2" data-tabs role="tablist" aria-label="Seções do risco">' + ABAS.map(function (a) {
        return '<button type="button" class="tab" role="tab" id="aba-' + a.id + '" aria-controls="p-' + a.id + '" aria-selected="' + (a.id === abaAtual) + '">' + U.icone(a.icone) + U.esc(a.nome) +
          (contagem[a.id] != null ? '<span class="tab__count">' + contagem[a.id] + "</span>" : "") + "</button>";
      }).join("") + "</div>" +
      '<section class="tab-panel" role="tabpanel" id="p-identificacao" aria-labelledby="aba-identificacao">' + abaIdentificacao() + "</section>" +
      '<section class="tab-panel" role="tabpanel" id="p-avaliacao" aria-labelledby="aba-avaliacao">' + abaAvaliacao() + "</section>" +
      '<section class="tab-panel" role="tabpanel" id="p-resposta" aria-labelledby="aba-resposta">' + abaResposta() + "</section>" +
      '<section class="tab-panel" role="tabpanel" id="p-monitoramento" aria-labelledby="aba-monitoramento">' + abaMonitoramento() + "</section>" +
      '<section class="tab-panel" role="tabpanel" id="p-historico" aria-labelledby="aba-historico">' + abaHistorico() + "</section>";
    tAcoes = GI.tabela.criar("t-acoes", {
      porPagina: 0, legenda: "Ações do risco", vazio: "Nenhuma ação vinculada.",
      colunas: [
        { id: "item", titulo: "Item", classe: "num", valor: function (a) { return Number(a.item) || 0; } },
        { id: "assunto", titulo: "Ação", valor: function (a) { return a.assunto; },
          html: function (a) { return '<div class="cell-title"><b>' + U.esc(a.assunto) + "</b><small>" + U.esc((a.grupo === "Problema" ? "Problema (risco materializado) · " : "") + "Origem: Risco " + r.codigo) + "</small></div>"; } },
        { id: "responsavel", titulo: "Responsável", valor: function (a) { return U.pessoa(a.responsavelId); } },
        { id: "prevista", titulo: "Prevista", tipo: "data", valor: function (a) { return a.replanejada || a.prevista; },
          html: function (a) { return F.data(a.replanejada || a.prevista) + (a.replanejada ? '<br><small class="text-muted">original ' + F.data(a.prevista) + "</small>" : ""); } },
        { id: "contribuicao", titulo: "Contribuição", valor: function (a) {
            var c = a.contribuicao || {}, op = r.natureza === "Oportunidade";
            return [c.probabilidade ? (op ? "aumenta P" : "reduz P") : "", c.impacto ? (op ? "aumenta I" : "reduz I") : ""].filter(Boolean).join(", ");
          } },
        { id: "status", titulo: "Situação", valor: function (a) { return a.statusRotulo; },
          html: function (a) { return U.badge(a.statusRotulo, U.statusAcao(a.status), true) + (a.status === "atrasada" ? '<br><small class="text-muted">há ' + U.plural(a.diasAtraso, "dia") + "</small>" : ""); } }
      ],
      classeLinha: function (a) { return a.status === "atrasada" ? "is-alert" : ""; },
      acoes: function (a) { return '<a class="btn btn--ghost btn--icon btn--sm" href="' + U.tela("central-acoes", "acoes", { busca: r.codigo, status: "todos" }) + '" aria-label="Abrir na Central de Ações" title="Abrir na Central de Ações">' + U.icone("arrowRight") + "</a>"; }
    });
    tAcoes.atualizar(r.listaAcoes.filter(function (a) { return a.ehAcao; }));
    tHist = GI.tabela.criar("t-hist", {
      porPagina: 20, legenda: "Histórico do risco", compacta: true, ordem: { coluna: "quando", direcao: "desc" },
      colunas: [
        { id: "quando", titulo: "Quando", classe: "nowrap", valor: function (h) { return h.quando; },
          html: function (h) { return F.data(h.quando.slice(0, 10)) + " " + h.quando.slice(11, 16); }, exportar: function (h) { return F.data(h.quando.slice(0, 10)) + " " + h.quando.slice(11, 16); } },
        { id: "quem", titulo: "Quem", valor: function (h) { return U.pessoa(h.porId); } },
        { id: "texto", titulo: "O que mudou" }
      ]
    });
    tHist.atualizar(r.historico);
    GI.ui.init(raiz);
  }

  /* ---------------- Eventos ---------------- */
  raiz.addEventListener("tabs:change", function (ev) { abaAtual = ev.detail.id.slice(2); });
  raiz.addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-btn]");
    if (!b) return;
    var a = b.getAttribute("data-btn");
    if (a === "editar") S.editar(codigo, recarregar);
    else if (a === "avaliar") S.avaliar(codigo, null, recarregar);
    else if (a === "plano") S.plano(codigo, recarregar);
    else if (a === "acao") S.novaAcao(codigo, recarregar);
    else if (a === "revisar") S.revisar(codigo, recarregar);
    else if (a === "aprovar") S.aprovarPlano(codigo, recarregar);
    else if (a === "encerrar") S.encerrar(codigo, null, recarregar);
    else if (a === "reabrir") S.reabrir(codigo, recarregar);
  });

  GI.exportar.registrar(function () {
    var revs = r.revisoes || [];
    return {
      titulo: "Ficha do risco " + r.codigo, subtitulo: r.titulo, arquivo: "ficha-" + r.codigo,
      blocos: [
        { tipo: "kpis", titulo: "Situação", itens: [
          { rotulo: "Inerente", valor: r.scoreInerente != null ? r.scoreInerente + " " + r.sevInerente.nome : "não avaliado" },
          { rotulo: "Residual", valor: r.scoreResidual != null ? r.scoreResidual + " " + r.sevResidual.nome : "não avaliado" },
          { rotulo: "VME atual", valor: F.moeda(r.vmeCentavos) }, { rotulo: "Situação", valor: r.situacao },
          { rotulo: "Próxima revisão", valor: r.proximaRevisao ? F.data(r.proximaRevisao) : "·" }] },
        { tipo: "texto", titulo: "Identificação", texto: "Categoria: " + r.categoriaCompleta + ". Causa: " + r.causa + ". Evento: " + r.titulo + ". Consequência: " + r.consequencia +
          ". Dono: " + U.pessoa(r.donoId) + ". Origem: " + r.origem + ". Gatilho: " + (r.gatilho || "·") + "." },
        { tipo: "texto", titulo: "Plano de resposta", texto: r.temPlano ? r.estrategia + ": " + r.plano + " Alvo " + r.nomeAlvo + " até " + F.data(r.prazoAlvo) + "." : "Não definido." },
        { tipo: "tabela", titulo: "Ações vinculadas", dados: tAcoes.exportacao() },
        { tipo: "tabela", titulo: "Revisões", dados: {
          colunas: [{ titulo: "Data", tipo: "data" }, { titulo: "Situação apurada", tipo: "texto" }, { titulo: "De", tipo: "num" }, { titulo: "Para", tipo: "num" }, { titulo: "Comentário", tipo: "texto" }, { titulo: "Por", tipo: "texto" }],
          bruto: revs.map(function (v) { return [v.data, S.apurada(v.situacaoApurada, r.natureza), v.de, v.para, v.texto, U.pessoa(v.porId)]; }),
          texto: revs.map(function (v) { return [F.data(v.data), S.apurada(v.situacaoApurada, r.natureza), v.de == null ? "" : String(v.de), String(v.para), v.texto, U.pessoa(v.porId)]; }) } },
        { tipo: "tabela", titulo: "Histórico", dados: tHist.exportacao() }
      ]
    };
  });

  S.pronto().then(recarregar).then(function () {
    if (!r) raiz.innerHTML = U.vazio("Risco não encontrado ou sem acesso.", "search", "Risco não encontrado");
  });
})(window.GI = window.GI || {});
