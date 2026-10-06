/* ==========================================================================
   suprimentos.js | Apoio comum às telas do módulo 04 Suprimentos (GI.sup)

   GI.sup.projeto(aoTrocar)        -> id do projeto (URL ?projeto= ou atual); preenche #f-projeto
   GI.sup.etapa(texto)             -> selo da etapa do processo de compra
   GI.sup.etapasMini(indice)       -> barra de 9 segmentos (Requisição a Pedido/contrato)
   GI.sup.folga(dias, faixa)       -> selo da folga em relação ao ROS (sinal, ícone e cor)
   GI.sup.situacao(texto)          -> selo da situação da linha do MAS / pedido
   GI.sup.fornecedor(texto)        -> selo da situação de qualificação do fornecedor
   GI.sup.marco(m, modo, attrs)    -> célula do MAS (datas ou desvio em dias)
   GI.sup.legenda()                -> legenda das cores das células do MAS
   GI.sup.dataCurta(iso)           -> 25/09/26 (pt) ou 09/25/26 (en)
   GI.sup.dias(n, sinal)           -> "+12 d" / "-5 d"
   GI.sup.link*(...)               -> links para outras telas do módulo e do 03
   GI.sup.TIPOS, MODALIDADES, DISCIPLINAS, SITUACOES_LINHA
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt;

  function projeto(aoTrocar) {
    var id = GI.api.projetoAtualId();   /* null = Portfólio */
    var sel = document.getElementById("f-projeto");
    if (sel) {
      sel.innerHTML = U.opcoes(Object.keys(U.mapas.projetos).map(function (k) {
        var p = U.mapas.projetos[k]; return { valor: k, texto: p.codigo + " " + p.nome };
      }), id);
      sel.addEventListener("change", function () { aoTrocar(Number(sel.value)); });
    }
    return id;
  }

  var TIPO_ETAPA = { "Planejado": "neutral", "Requisição": "info", "RFx emitida": "info", "Propostas recebidas": "info", "Equalização técnica": "purple",
    "Equalização comercial": "purple", "Negociação": "warning", "Recomendação de adjudicação": "warning", "Aprovada": "primary", "Pedido/contrato emitido": "success" };
  function etapa(t) { return t ? U.badge(t, TIPO_ETAPA[t] || "neutral", true) : ""; }
  function etapasMini(i) {
    var h = '<span class="etapas-mini" role="img" aria-label="Etapa ' + Math.max(0, i) + ' de 9">';
    for (var k = 1; k <= 9; k++) h += '<span class="' + (k < i || i === 9 ? "is-done" : k === i ? "is-current" : "") + '"></span>';
    return h + "</span>";
  }

  var TIPO_FOLGA = { critico: "danger", atencao: "warning", ok: "success", concluido: "neutral", "sem-data": "neutral" };
  function dias(n, sinal) {
    if (n == null) return "";
    return (sinal && n > 0 ? "+" : "") + F.num(n) + " d";
  }
  function folga(n, faixa) {
    if (n == null) return '<span class="text-muted">·</span>';
    var ic = faixa === "critico" ? "alertTriangle" : faixa === "atencao" ? "clock" : faixa === "concluido" ? "checkCircle" : "check";
    return '<span class="badge badge--' + (TIPO_FOLGA[faixa] || "neutral") + '"><span class="folga">' + U.icone(ic) + U.esc(dias(n, true)) + "</span></span>";
  }
  var TIPO_SITUACAO = { "Crítico": "danger", "Atenção": "warning", "No prazo": "info", "Entregue": "success", "Contratado": "success",
    "Em aberto": "info" };
  function situacao(t) { return t ? U.badge(t, TIPO_SITUACAO[t] || "neutral", true) : ""; }
  var TIPO_FORN = { "Qualificado": "success", "Em qualificação": "info", "Restrito": "warning", "Bloqueado": "danger", "Sem qualificação": "neutral", "Não cadastrado": "neutral" };
  function fornecedor(t) { return t ? U.badge(t, TIPO_FORN[t] || "neutral", true) : ""; }

  function dataCurta(iso) {
    if (!iso) return "";
    var d = new Date(String(iso).slice(0, 10) + "T00:00:00");
    return isNaN(d) ? iso : d.toLocaleDateString(GI.i18n ? GI.i18n.locale : "pt-BR", { day: "2-digit", month: "2-digit", year: "2-digit" });
  }

  /* Célula do MAS. modo "datas": data principal (real, previsão ou LB) e LB abaixo; "desvio": dias em relação à LB */
  var ROTULO_SIT = { prazo: "Realizado no prazo", atraso: "Realizado com atraso", vencido: "Vencido sem realização", "previsto-atraso": "Previsão após a LB",
    "a-vencer": "A vencer", "sem-data": "Sem data", na: "Não se aplica" };
  var ICONE_SIT = { prazo: "check", atraso: "check", vencido: "alertTriangle", "previsto-atraso": "clock" };
  function marco(m, modo, attrs) {
    var cls = "marco marco--" + m.situacao + (m.estimada ? " marco--estimada" : "");
    var tag = attrs ? "button" : "span";
    var a = attrs ? ' type="button" ' + attrs : "";
    var titulo = ROTULO_SIT[m.situacao] + (m.lb ? " · LB " + F.data(m.lb) : "") + (m.real ? " · realizado " + F.data(m.real) : m.previsao ? " · previsão " + F.data(m.previsao) : "") +
      (m.desvio ? " · " + dias(m.desvio, true) : "") + (m.estimada ? " · LB estimada" : "");
    var ic = ICONE_SIT[m.situacao] ? U.icone(ICONE_SIT[m.situacao]) : "";
    var principal, sub;
    if (m.situacao === "na") { principal = "N/A"; sub = ""; }
    else if (m.situacao === "sem-data") { principal = "·"; sub = ""; }
    else if (modo === "desvio") {
      principal = m.situacao === "vencido" ? dias(m.diasVencido) : m.desvio ? dias(m.desvio, true) : "0 d";
      sub = m.situacao === "vencido" ? "vencido" : m.real ? "real" : "prev.";
    } else {
      principal = dataCurta(m.real || m.previsao || m.lb);
      sub = m.lb && (m.real || m.previsao) && (m.real || m.previsao) !== m.lb ? "LB " + dataCurta(m.lb).slice(0, 5) : m.real ? "real" : "LB";
    }
    return "<" + tag + ' class="' + cls + '"' + a + ' title="' + U.esc(titulo) + '" aria-label="' + U.esc(m.nome + ": " + titulo) + '"><b>' + ic + U.esc(principal) + "</b>" +
      (sub ? "<small>" + U.esc(sub) + "</small>" : "") + "</" + tag + ">";
  }
  function legenda() {
    function item(sit, texto) { return '<span class="legend__item"><span class="marco marco--' + sit + '" aria-hidden="true"><b>' + (ICONE_SIT[sit] ? U.icone(ICONE_SIT[sit]) : "&nbsp;") + "</b></span>" + U.esc(texto) + "</span>"; }
    return '<div class="legend legend--mas" aria-label="Legenda do MAS">' +
      item("prazo", "Realizado no prazo") + item("atraso", "Realizado com atraso") + item("vencido", "Vencido sem realização") +
      item("previsto-atraso", "Previsão após a LB") + item("a-vencer", "A vencer") + item("na", "Não se aplica") + "</div>";
  }

  function linkPedido(n) { return n ? '<a href="' + U.tela("suprimentos", "diligenciamento", { pedido: n }) + '">' + U.esc(n) + "</a>" : ""; }
  function linkProcesso(codigo) { return '<a href="' + U.tela("suprimentos", "processos", { pacote: codigo }) + '">' + U.esc(codigo) + "</a>"; }
  function linkMas(codigo) { return '<a href="' + U.tela("suprimentos", "mas", { busca: codigo }) + '">' + U.esc(codigo) + "</a>"; }
  function linkEac(codigo, projetoId) { return codigo ? '<a href="' + U.tela("financeiro", "mapa-controle", { projeto: projetoId }) + '">' + U.esc(codigo) + "</a>" : ""; }
  function linkContrato(n) { return n ? '<a href="' + U.tela("financeiro", "contrato", { numero: n }) + '">' + U.esc(n) + "</a>" : ""; }

  /* KPIs da tela para exportação */
  function kpisExport(sel) {
    return Array.prototype.map.call(document.querySelectorAll((sel || "#kpis") + " .kpi"), function (k) {
      return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" };
    });
  }

  GI.sup = {
    projeto: projeto, etapa: etapa, etapasMini: etapasMini, folga: folga, situacao: situacao, fornecedor: fornecedor,
    marco: marco, legenda: legenda, dataCurta: dataCurta, dias: dias, rotuloSituacao: ROTULO_SIT,
    linkPedido: linkPedido, linkProcesso: linkProcesso, linkMas: linkMas, linkEac: linkEac, linkContrato: linkContrato, kpisExport: kpisExport,
    TIPOS: ["Equipamento", "Material", "Serviço", "EPC"],
    MODALIDADES: ["Preço global", "Preço unitário", "Administração", "EPC"],
    DISCIPLINAS: ["Engenharia", "Civil", "Mecânica", "Tubulação", "Elétrica", "Instrumentação", "Automação", "Montagem"],
    SITUACOES_LINHA: ["Crítico", "Atenção", "No prazo", "Entregue", "Contratado"]
  };
})(window.GI = window.GI || {});
