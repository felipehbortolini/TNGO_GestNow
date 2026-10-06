/* ==========================================================================
   Gestão Financeira > Contingência
   Reserva de contingência (riscos identificados, integra a linha de base de
   custo) e reserva gerencial (imprevistos, fora da linha de base, libera só o
   Comitê). Constituição na linha de base; consumo só por SM aprovada (08).
   Controles: consumo x avanço físico real (com tolerância), cobertura do saldo
   sobre a exposição das ameaças ativas (VME do 05), valor pedido em SMs ainda
   em análise e saldo previsto pelo avanço planejado. Cálculos só em
   GI.api.financeiro.contingencia.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt;
  var projetoId, dados = null, tProj, tMov, tRsk;

  function pct(v, c) { return v == null ? "·" : F.pct(v, c == null ? 1 : c); }

  function render() {
    var el = document.getElementById("kpis");
    if (!dados) {
      el.innerHTML = "";
      document.getElementById("composicao").innerHTML = U.vazio("Este projeto ainda não tem reservas constituídas.", "shieldCheck");
      tMov.atualizar([]); tRsk.atualizar([]); if (tProj) tProj.atualizar([]);
      return;
    }
    var c = dados.contingencia, g = dados.gerencial;
    var corte = dados.burn.filter(function (b) { return b.real != null; }).slice(-1)[0];
    var saldoPrevisto = corte ? corte.esperado : null;
    var consumoAlto = c.consumoPct != null && dados.limiteConsumoPct != null && c.consumoPct > dados.limiteConsumoPct;
    var coberturaBaixa = dados.coberturaPct != null && dados.coberturaPct < dados.coberturaMinimaPct;
    el.innerHTML = [
      U.kpi({ rotulo: "Saldo da contingência", moeda: c.saldo, icone: "shieldCheck", cor: c.saldo < 0 ? "danger" : consumoAlto ? "warning" : "success",
        esperado: { rotulo: "Previsto", valor: saldoPrevisto == null ? "·" : F.moedaCompacta(saldoPrevisto) },
        rodape: "constituída " + F.moedaCompacta(c.total) + " · consumida " + F.moedaCompacta(c.consumido) + (c.liberado ? " · liberada " + F.moedaCompacta(c.liberado) : "") }),
      U.kpi({ rotulo: "Consumo da contingência", valor: c.consumoPct == null ? "·" : F.num(c.consumoPct, 1), unidade: c.consumoPct == null ? "" : "%", icone: "gauge",
        cor: consumoAlto ? "warning" : "success",
        esperado: { rotulo: "Limite", valor: dados.limiteConsumoPct == null ? "·" : F.pct(dados.limiteConsumoPct, 1) },
        rodape: "avanço físico real " + pct(dados.avancoReal) + " + tolerância de " + F.num(dados.toleranciaConsumoPP) + " p.p." }),
      U.kpi({ rotulo: "Pedido em SMs em análise", moeda: c.emAnalise, icone: "fileText", cor: c.emAnalise > c.saldo ? "danger" : c.emAnalise ? "warning" : "success",
        esperado: { rotulo: "Saldo se aprovadas", valor: F.moedaCompacta(c.saldoAposAnalise) },
        rodape: U.plural(dados.smsEmAnalise, "SM aguardando decisão", "SMs aguardando decisão"), href: U.tela("governanca", "mudancas", { projeto: projetoId }) }),
      U.kpi({ rotulo: "Cobertura da exposição a riscos", valor: dados.coberturaPct == null ? "·" : F.num(dados.coberturaPct, 0), unidade: dados.coberturaPct == null ? "" : "%", icone: "target",
        cor: coberturaBaixa ? "warning" : "success",
        esperado: { rotulo: "Meta", valor: "≥ " + F.pct(dados.coberturaMinimaPct, 0) },
        rodape: "saldo sobre a exposição de " + F.moedaCompacta(dados.exposicaoCentavos) + " (VME das ameaças ativas)", href: U.tela("riscos", "painel", { projeto: projetoId }) }),
      U.kpi({ rotulo: "Reserva gerencial", moeda: g.saldo, icone: "landmark", cor: g.saldo < g.total ? "warning" : "info",
        esperado: { rotulo: "Constituída", valor: F.moedaCompacta(g.total) },
        rodape: "fora da linha de base · só o Comitê libera" + (g.emAnalise ? " · " + F.moedaCompacta(g.emAnalise) + " em análise" : "") })
    ].join("");

    var al = document.getElementById("alertas");
    al.hidden = !dados.alertas.length;
    al.innerHTML = dados.alertas.length ? U.icone("alertTriangle") + '<div class="alert__body"><b>' + U.esc(U.plural(dados.alertas.length, "ponto de atenção", "pontos de atenção")) + "</b><br>" +
      dados.alertas.map(function (a) { return U.esc(a.texto); }).join("<br>") + "</div>" : "";

    document.getElementById("sub-burn").textContent = "Saldo real e saldo previsto pelo avanço físico planejado (consumo proporcional à linha de base)" +
      (projetoId == null ? " · carteira: soma dos projetos" : "");
    GI.charts.line("g-burn", {
      labels: dados.burn.map(function (b) { return U.mesCurto(b.mes); }), money: true, ariaLabel: "Saldo da contingência real e previsto por mês",
      series: [{ label: "Saldo real", data: dados.burn.map(function (b) { return b.real; }), color: "chart-1" },
        { label: "Saldo previsto pelo avanço", data: dados.burn.map(function (b) { return b.esperado; }), color: "chart-baseline", dashed: true, points: false }]
    });

    document.getElementById("composicao").innerHTML = '<div class="table-wrap"><table class="table"><caption class="sr-only">Composição do orçamento</caption><tbody>' +
      linhaComp("Orçado atual da EAC (linha de base de medição)", dados.pmbCentavos) +
      linhaComp("Saldo da reserva de contingência", c.saldo, "+") +
      linhaComp("Linha de base de custo", dados.linhaBaseCustoCentavos, null, true) +
      linhaComp("Saldo da reserva gerencial", g.saldo, "+") +
      linhaComp("Orçamento do projeto", dados.orcamentoProjetoCentavos, null, true) +
      "</tbody></table></div>" +
      '<p class="text-small text-muted mt-2">Contingência consumida por SM aprovada sai da reserva e entra no orçado da EAC pela nova revisão; o total da linha de base de custo não muda.</p>';

    if (tProj) tProj.atualizar(dados.projetos || []);
    tMov.atualizar(dados.movimentos.slice());
    document.getElementById("sub-rsk").textContent = "Exposição (VME) de " + F.moeda(dados.exposicaoCentavos) + " contra saldo de " + F.moeda(c.saldo) + " · SMs que citam o risco na análise de impacto";
    tRsk.atualizar(dados.riscos);
  }
  function linhaComp(rotulo, valor, sinal, total) {
    return "<tr" + (total ? ' class="row--total"' : "") + "><td>" + (total ? "<b>" + U.esc(rotulo) + "</b>" : U.esc(rotulo)) + '</td><td class="num">' +
      (sinal ? '<span class="text-muted">' + sinal + "</span> " : "") + (total ? "<b>" + U.esc(F.moeda(valor)) + "</b>" : U.esc(F.moeda(valor))) + "</td></tr>";
  }

  function montar() {
    var PF = projetoId == null;
    var linkSm = function (cod) { return '<a href="' + U.tela("governanca", "mudanca", { codigo: cod }) + '">' + U.esc(cod) + "</a>"; };
    if (PF) {
      document.getElementById("sec-proj").hidden = false;
      tProj = GI.tabela.criar("projetos", {
        porPagina: 0, legenda: "Reservas por projeto", vazio: "Nenhum projeto com reservas.", ordem: { coluna: "total", direcao: "desc" },
        colunas: [
          { id: "projetoCodigo", titulo: "Projeto", html: function (x) { return '<a href="' + U.tela("financeiro", "contingencia", { projeto: x.projetoId }) + '"><b>' + U.esc(x.projetoCodigo) + "</b></a><br><small class=\"text-muted\">" + U.esc(x.projetoNome) + "</small>"; },
            exportar: function (x) { return x.projetoCodigo + " " + x.projetoNome; } },
          { id: "total", titulo: "Constituída", tipo: "moeda" },
          { id: "consumido", titulo: "Consumida", tipo: "moeda" },
          { id: "saldo", titulo: "Saldo", tipo: "moeda" },
          { id: "consumoPct", titulo: "Consumo", tipo: "num", html: function (x) {
            var alto = x.consumoPct != null && x.limiteConsumoPct != null && x.consumoPct > x.limiteConsumoPct;
            return '<span class="' + (alto ? "valor--negativo" : "") + '">' + U.esc(pct(x.consumoPct)) + '</span><br><small class="text-muted">limite ' + U.esc(pct(x.limiteConsumoPct)) + "</small>"; },
            exportar: function (x) { return pct(x.consumoPct); } },
          { id: "emAnalise", titulo: "Em análise", tipo: "moeda" },
          { id: "coberturaPct", titulo: "Cobertura", tipo: "num", html: function (x) { return x.coberturaPct == null ? "·" : '<span class="' + (dados && x.coberturaPct < dados.coberturaMinimaPct ? "valor--negativo" : "") + '">' + U.esc(F.pct(x.coberturaPct, 0)) + "</span>"; },
            exportar: function (x) { return x.coberturaPct == null ? "" : F.pct(x.coberturaPct, 0); } },
          { id: "gerencial", titulo: "Reserva gerencial", tipo: "moeda" }
        ]
      });
    }
    tMov = GI.tabela.criar("movimentos", {
      porPagina: 20, legenda: "Extrato de movimentos das reservas", vazio: "Nenhum movimento.", ordem: { coluna: "data", direcao: "asc" },
      colunas: (PF ? [U.colunaProjeto()] : []).concat([
        { id: "data", titulo: "Data", tipo: "data" },
        { id: "reserva", titulo: "Reserva" },
        { id: "tipo", titulo: "Movimento", html: function (m) { return U.badge(m.tipo, m.tipo === "Consumo" ? "warning" : m.tipo === "Em análise" ? "neutral" : m.tipo === "Liberação" ? "success" : "info", true); }, exportar: function (m) { return m.tipo; } },
        { id: "descricao", titulo: "Descrição", html: function (m) { return '<div class="cell-title"><b>' + U.esc(m.descricao) + "</b>" + (m.smRef ? "<small>" + linkSm(m.smRef) + (m.tipo === "Em análise" ? " · " + U.esc(m.situacao) : "") + "</small>" : "") + "</div>"; },
          exportar: function (m) { return (m.smRef ? m.smRef + " " : "") + m.descricao; } },
        { id: "valorCentavos", titulo: "Valor", tipo: "moeda", html: function (m) { return '<span class="' + (m.tipo === "Em análise" ? "text-muted" : "") + '">' + (m.valorCentavos > 0 ? "+" : "") + U.esc(F.moeda(m.valorCentavos)) + "</span>"; } },
        { id: "saldoCentavos", titulo: "Saldo", tipo: "moeda" }
      ])
    });
    tRsk = GI.tabela.criar("riscos", {
      porPagina: 10, legenda: "Ameaças ativas e cobertura", vazio: "Nenhuma ameaça ativa.", ordem: { coluna: "vmeCentavos", direcao: "desc" },
      colunas: (PF ? [U.colunaProjeto()] : []).concat([
        { id: "codigo", titulo: "Risco", classe: "nowrap", html: function (r) { return '<a href="' + U.tela("riscos", "ficha", { codigo: r.codigo }) + '"><b>' + U.esc(r.codigo) + "</b></a>"; } },
        { id: "titulo", titulo: "Ameaça" },
        { id: "severidade", titulo: "Severidade" },
        { id: "situacao", titulo: "Situação" },
        { id: "vmeCentavos", titulo: "VME", tipo: "moeda" },
        { id: "sms", titulo: "SMs vinculadas", valor: function (r) { return r.sms.join(", "); }, html: function (r) { return r.sms.length ? r.sms.map(linkSm).join("<br>") : '<span class="text-muted">·</span>'; } }
      ])
    });
  }

  function carregar() { return GI.api.financeiro.contingencia(projetoId).then(function (d) { dados = d; render(); }); }

  GI.exportar.registrar(function () {
    var p = U.projeto(projetoId);
    var blocos = [{ tipo: "kpis", titulo: "Indicadores", itens: Array.prototype.map.call(document.querySelectorAll("#kpis .kpi"), function (k) {
      return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" }; }) },
      { tipo: "grafico", titulo: "Saldo da contingência", canvas: document.getElementById("g-burn") }];
    if (tProj) blocos.push({ tipo: "tabela", titulo: "Reservas por projeto", dados: tProj.exportacao() });
    blocos.push({ tipo: "tabela", titulo: "Extrato de movimentos", dados: tMov.exportacao() }, { tipo: "tabela", titulo: "Ameaças ativas e cobertura", dados: tRsk.exportacao() });
    return { titulo: "Contingência e reservas", subtitulo: p ? p.codigo + " " + p.nome : "Portfólio de projetos", arquivo: "contingencia-" + (p ? p.codigo : "portfolio"), orientacao: "l", blocos: blocos };
  });

  GI.util.pronto().then(function () {
    projetoId = GI.fin.projeto(function (id) { projetoId = id; carregar(); });
    var sm = document.getElementById("btn-sm");
    sm.href = projetoId == null ? U.tela("governanca", "mudancas") : U.tela("governanca", "mudancas", { projeto: projetoId, acao: "nova" });
    montar();
    return carregar();
  });
})(window.GI = window.GI || {});
