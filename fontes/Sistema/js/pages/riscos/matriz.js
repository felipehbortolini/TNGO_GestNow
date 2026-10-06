/* ==========================================================================
   Gestão de Riscos > Matriz de riscos 5x5 (mockup 02)
   Alternador Inerente/Residual (residual padrão; sem residual entra a
   inerente); natureza; célula abre o registro filtrado; legenda pelas
   faixas da escala ativa; movimentação inerente para residual.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, S = GI.rsk, API = GI.api.riscos;
  var projetoId = null, dados = null;
  var aval = U.param("aval") === "inerente" ? "inerente" : "residual";
  var natureza = U.param("natureza") || "";

  function celula(c) {
    var n = c.riscos.length;
    var nome = S.nomeProb(c.p) + " x " + S.nomeImp(c.i);
    var rot = "P" + c.p + " x I" + c.i + " = " + c.score + " (" + c.sev.nome + "): " + U.plural(n, "risco", "riscos");
    var q = { projeto: projetoId, p: c.p, i: c.i, aval: aval };
    if (natureza) q.natureza = natureza;
    var tag = n ? "a" : "span";
    /* Células são links (abrem o registro filtrado); vazia fica esmaecida e não é clicável */
    return "<" + tag + ' class="matrix__cell matrix__cell--' + c.sev.id + (n ? "" : " is-empty") + '"' + (n ? ' href="' + U.tela("riscos", "registro", q) + '"' : "") +
      ' aria-label="' + U.esc(rot) + '" title="' + U.esc(nome + " · " + rot) + '"><b>' + n + '</b><span class="matrix__formula">P' + c.p + " x I" + c.i + " = " + c.score + "</span>" +
      (n ? '<span class="matrix__chips">' + c.riscos.map(function (r) { return '<span' + (r.natureza === "Oportunidade" ? ' class="is-op" title="Oportunidade"' : "") + ">" + U.esc(r.curto) + "</span>"; }).join("") + "</span>" : "") + "</" + tag + ">";
  }
  function render() {
    var d = dados;
    var h = '<div class="matriz-wrap"><span class="matriz-wrap__y">Probabilidade →</span><div class="matrix matrix--riscos' + (natureza === "Oportunidade" ? " matrix--op" : "") + '" role="group" aria-label="Matriz probabilidade x impacto">';
    for (var p = 5; p >= 1; p--) {
      h += '<span class="matrix__axis matrix__axis--y"><span><b>P' + p + "</b><small>" + U.esc(S.nomeProb(p)) + "</small></span></span>";
      d.celulas.filter(function (c) { return c.p === p; }).forEach(function (c) { h += celula(c); });
    }
    h += "<span></span>";
    for (var i = 1; i <= 5; i++) h += '<span class="matrix__axis"><span><b>I' + i + "</b><small>" + U.esc(S.nomeImp(i)) + "</small></span></span>";
    h += '</div><span class="matriz-wrap__x">Impacto →</span></div>';
    document.getElementById("matriz").innerHTML = h;
    document.getElementById("sub-mat").textContent = U.plural(d.total, "risco ativo", "riscos ativos") + " · avaliação " + aval +
      (natureza ? " · " + (natureza === "Ameaça" ? "somente ameaças" : "somente oportunidades") : "") + " · escala " + d.escala;
    document.getElementById("legenda").innerHTML = '<div class="legend" aria-label="Faixas de severidade">' + d.faixas.map(function (f) {
      return '<span class="legend__item"><span class="sev sev--' + f.id + (natureza === "Oportunidade" ? " sev--op" : "") + '">' + U.esc(f.nome) + "</span>" + f.minimo + " a " + f.maximo + "</span>";
    }).join("") + "</div>";
    var notas = [];
    if (d.semAvaliacao) notas.push(U.plural(d.semAvaliacao, "risco identificado sem avaliação fica fora da matriz", "riscos identificados sem avaliação ficam fora da matriz") + ".");
    if (natureza === "Oportunidade") notas.push("Para oportunidades, score alto indica prioridade de captura.");
    if (d.riscoVidaEhAlto && d.riscoVida) notas.push("Na escala ativa, risco à vida é sempre da faixa mais alta: " + U.plural(d.riscoVida, "risco", "riscos") + " com classificação acima da cor da célula.");
    if (aval === "residual") notas.push("Riscos sem avaliação residual entram com a inerente.");
    document.getElementById("nota-mat").textContent = notas.join(" ");

    var mov = d.movimentacao;
    document.getElementById("mov").innerHTML = mov.length ? '<ul class="mov">' + mov.map(function (m) {
      var op = m.natureza === "Oportunidade";
      return '<li><a class="mov__row' + (m.semReducao ? " is-alert" : "") + '" href="' + U.tela("riscos", "ficha", { codigo: m.codigo }) + '" title="' + U.esc(m.codigo + " · " + m.titulo) + '">' +
        '<span class="mov__id">' + U.esc(m.curto) + '</span><span class="mov__trilho" aria-hidden="true">' +
        '<span class="mov__ine mov--' + m.sevDe.id + (op ? " mov--op" : "") + '" style="width:' + (m.de / 25 * 100) + '%"></span>' +
        '<span class="mov__res mov--' + m.sevPara.id + (op ? " mov--op" : "") + '" style="width:' + (m.para / 25 * 100) + '%"></span></span>' +
        '<span class="mov__val">' + m.de + " → " + m.para + '</span><span class="sr-only">' + U.esc(m.titulo) + ": inerente " + m.de + ", residual " + m.para +
        (m.semReducao ? ", sem redução" : "") + (op ? " (oportunidade)" : "") + "</span></a></li>";
    }).join("") + "</ul>" : U.vazio("Nenhum risco com plano de resposta e avaliação residual.", "target");
    var sem = mov.filter(function (m) { return m.semReducao; });
    document.getElementById("nota-mov").textContent = (sem.length ? "Sem redução após o plano, o risco entra na pauta de escalonamento (" + sem.map(function (m) { return m.curto; }).join(", ") + "). " : "") +
      "Barra clara: inerente; barra cheia: residual. Oportunidades crescem quando a resposta funciona.";
    document.getElementById("contexto").innerHTML = S.contexto(projetoId);
    document.getElementById("lnk-registro").href = U.tela("riscos", "registro", { projeto: projetoId, aval: aval });
  }
  function carregar() {
    return API.matriz({ projetoId: projetoId, avaliacao: aval, natureza: natureza }).then(function (d) { dados = d; render(); });
  }

  document.getElementById("f-aval").addEventListener("segmented:change", function (ev) { aval = ev.detail.value === "inerente" ? "inerente" : "residual"; carregar(); });
  document.getElementById("f-natureza").addEventListener("change", function (ev) { natureza = ev.target.value; carregar(); });

  GI.exportar.registrar(function () {
    var p = U.projeto(projetoId) || { codigo: "Portfólio" };
    var linhas = [];
    for (var pp = 5; pp >= 1; pp--) {
      var l = ["P" + pp + " " + S.nomeProb(pp)];
      dados.celulas.filter(function (c) { return c.p === pp; }).forEach(function (c) { l.push(c.riscos.length ? c.riscos.length + " (" + c.riscos.map(function (r) { return r.curto; }).join(", ") + ")" : "0"); });
      linhas.push(l);
    }
    var cols = [{ titulo: "Probabilidade \\ Impacto", tipo: "texto" }].concat([1, 2, 3, 4, 5].map(function (i) { return { titulo: "I" + i + " " + S.nomeImp(i), tipo: "texto" }; }));
    var cores = {};
    dados.celulas.forEach(function (c) { cores[(5 - c.p) + "-" + c.i] = c.sev.id; });
    return {
      titulo: "Matriz de riscos 5x5 · " + p.codigo, subtitulo: document.getElementById("sub-mat").textContent, arquivo: "matriz-de-riscos-" + (projetoId == null ? "portfolio" : p.codigo), orientacao: "l",
      blocos: [
        { tipo: "tabela", titulo: "Distribuição por probabilidade e impacto", dados: { colunas: cols, bruto: linhas, texto: linhas },
          corCelula: function (li, co) { var s = co > 0 ? cores[li + "-" + co] : null; return s ? { fundo: (natureza === "Oportunidade" ? "oport-" : "sev-") + s + "-bg", texto: (natureza === "Oportunidade" ? "oport-" : "sev-") + s + "-fg" } : null; } },
        { tipo: "texto", titulo: "Faixas", texto: dados.faixas.map(function (f) { return f.nome + " " + f.minimo + " a " + f.maximo; }).join(" · ") },
        { tipo: "tabela", titulo: "Movimentação inerente para residual", dados: {
          colunas: [{ titulo: "Risco", tipo: "texto" }, { titulo: "Título", tipo: "texto" }, { titulo: "Inerente", tipo: "num" }, { titulo: "Residual", tipo: "num" }, { titulo: "Observação", tipo: "texto" }],
          bruto: dados.movimentacao.map(function (m) { return [m.codigo, m.titulo, m.de, m.para, m.semReducao ? "Sem redução: pauta de escalonamento" : m.natureza === "Oportunidade" ? "Oportunidade" : ""]; }),
          texto: dados.movimentacao.map(function (m) { return [m.codigo, m.titulo, String(m.de), String(m.para), m.semReducao ? "Sem redução: pauta de escalonamento" : m.natureza === "Oportunidade" ? "Oportunidade" : ""]; }) } }
      ]
    };
  });

  S.pronto().then(function () {
    projetoId = S.projeto(function (id) { projetoId = id; carregar(); });
    Array.prototype.forEach.call(document.querySelectorAll("#f-aval .segmented__opt"), function (o) { o.setAttribute("aria-pressed", String(o.getAttribute("data-value") === aval)); });
    document.getElementById("f-natureza").value = natureza;
    return carregar();
  });
})(window.GI = window.GI || {});
