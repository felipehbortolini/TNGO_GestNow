/* ==========================================================================
   Gestão Financeira > Cronograma de desembolso
   Gerado a partir do mapa de controle: histograma mensal (previsto na linha de
   base, realizado até o corte e projetado depois) e grade item x mês com o
   saldo a pagar, para alinhamento com a tesouraria.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt;
  var projetoId, dados = null, tabela, nivel = 2, chaveGrade = null;

  function colunasGrade(futuros) {
    return [
      { id: "codigo", titulo: "Código", ordenavel: false, classe: "nowrap" },
      { id: "descricao", titulo: "Descrição", ordenavel: false, html: function (x) { return x.nivel < 3 ? "<b>" + U.esc(x.descricao) + "</b>" : U.esc(x.descricao); } },
      { id: "saldo", titulo: "Saldo a pagar", tipo: "moeda", ordenavel: false, html: function (x) { return "<b>" + U.esc(GI.fin.mil(x.saldo)) + "</b>"; } }
    ].concat(futuros.map(function (m) {
      return { id: "m" + m, titulo: U.mesCurto(m), tipo: "moeda", ordenavel: false, valor: function (x) { return x.meses[m]; },
        html: function (x) { return x.meses[m] ? U.esc(GI.fin.mil(x.meses[m])) : '<span class="text-muted">·</span>'; } };
    }));
  }

  function criarTabela(futuros) {
    if (tabela && chaveGrade === futuros.join()) return;
    chaveGrade = futuros.join();
    tabela = GI.tabela.criar("tabela", {
      porPagina: 0, pilha: false, compacta: true, legenda: "Saldo a pagar por mês", vazio: "Sem saldo a desembolsar.",
      colunas: colunasGrade(futuros),
      classeLinha: GI.fin.classeNivel,
      rodape: function () {
        var r = { codigo: "", descricao: "<b>Total</b>", saldo: "<b>" + U.esc(GI.fin.mil(dados.saldo)) + "</b>" };
        futuros.forEach(function (m) { r["m" + m] = "<b>" + U.esc(GI.fin.mil(dados.totalMeses[m])) + "</b>"; });
        return r;
      }
    });
  }

  function render() {
    var el = document.getElementById("kpis");
    if (!dados) {
      el.innerHTML = "";
      document.getElementById("sub-hist").textContent = projetoId == null ? "Nenhum projeto da carteira tem curva financeira cadastrada." : "Este projeto ainda não tem curva financeira cadastrada.";
      GI.charts.bar("g-mensal", { labels: [], series: [] });
      criarTabela([]); tabela.atualizar([]);
      return;
    }
    var fut = dados.futuros;
    var prox3 = fut.slice(0, 3).reduce(function (s, m) { return s + (dados.totalMeses[m] || 0); }, 0);
    var pico = fut.reduce(function (a, m) { return !a || dados.totalMeses[m] > dados.totalMeses[a] ? m : a; }, null);
    var k = dados.meses.indexOf(dados.corte);
    var prevMes = dados.planejado[k], realMes = dados.realizado[k];
    /* Previsto na linha de base (curva financeira mensal) para cada card */
    function previsto(meses) { return meses.reduce(function (s, m) { var i = dados.meses.indexOf(m); return s + (i < 0 ? 0 : dados.planejado[i] || 0); }, 0); }
    var prevAteCorte = previsto(dados.meses.slice(0, k + 1)), prevSaldo = previsto(dados.meses.slice(k + 1)), prev3 = previsto(fut.slice(0, 3));
    el.innerHTML = [
      U.kpi({ rotulo: "Realizado até o corte", moeda: dados.realizadoAcumulado, icone: "coins", cor: "primary",
        esperado: { rotulo: "Previsto", valor: F.moedaCompacta(prevAteCorte) },
        rodape: F.pct(dados.realizadoAcumulado / dados.projecaoTermino * 100) + " da projeção no término" }),
      U.kpi({ rotulo: "Saldo a desembolsar", moeda: dados.saldo, icone: "calendarRange", cor: "info",
        esperado: { rotulo: "Previsto", valor: F.moedaCompacta(prevSaldo) },
        rodape: fut.length ? "de " + U.mesCurto(fut[0]) + " a " + U.mesCurto(fut[fut.length - 1]) : "" }),
      U.kpi({ rotulo: "Próximos 3 meses", moeda: prox3, icone: "calendarClock", cor: "warning",
        esperado: { rotulo: "Previsto", valor: F.moedaCompacta(prev3) },
        rodape: fut.slice(0, 3).map(U.mesCurto).join(", ") }),
      U.kpi({ rotulo: "Mês de corte", moeda: realMes, icone: "barChart", cor: realMes > prevMes ? "warning" : "success",
        esperado: { rotulo: "Previsto", valor: prevMes == null ? "·" : F.moedaCompacta(prevMes) },
        rodape: U.mesCurto(dados.corte) + (pico ? " · pico " + U.mesCurto(pico) : "") })
    ].join("");
    document.getElementById("sub-hist").textContent = "Corte em " + U.mesCurto(dados.corte) + " · previsto na linha de base, realizado até o corte e projetado depois" + (projetoId == null ? " · soma dos projetos da carteira" : "");
    GI.charts.bar("g-mensal", {
      labels: dados.meses.map(U.mesCurto), money: true,
      ariaLabel: "Desembolso mensal: previsto, realizado e projetado por mês",
      series: [
        { label: "Previsto", data: dados.planejado, color: "chart-desembolso-previsto" },
        { label: "Realizado", data: dados.realizado, color: "chart-desembolso-realizado" },
        { label: "Projetado", data: dados.projetado, color: "chart-forecast" }
      ]
    });
    criarTabela(fut);
    tabela.atualizar(dados.itens.filter(function (x) { return x.nivel <= nivel && x.saldo > 0; }));
  }

  function carregar() {
    return GI.api.financeiro.desembolso(projetoId).then(function (r) { dados = r; render(); });
  }

  function enviar() {
    if (!dados) return;
    GI.form.abrir({
      titulo: "Enviar à tesouraria", subtitulo: "Cronograma de desembolso de " + U.mesCurto(dados.futuros[0]) + " em diante", textoSalvar: "Enviar",
      intro: '<p class="text-small text-muted">Segue a planilha do cronograma (Excel) com o saldo a pagar por mês. Envio simulado no protótipo.</p>',
      campos: [
        { id: "para", rotulo: "Para", tipo: "texto", obrigatorio: true, valor: "tesouraria@exemplo.com", largura: "full" },
        { id: "mensagem", rotulo: "Mensagem", tipo: "textarea", max: 400,
          valor: GI.t("Cronograma de desembolso atualizado com o fechamento de " + U.mesCurto(dados.corte) + ". Saldo a desembolsar: " + F.moeda(dados.saldo) + ".") }
      ],
      validar: function (v) { return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v.para) ? [] : [{ campo: "para", msg: "Informe um e-mail válido." }]; },
      aoSalvar: function (v) { GI.ui.toast("Cronograma enviado para " + v.para + " (envio simulado).", "success"); }
    });
  }

  GI.exportar.registrar(function () {
    var p = U.projeto(projetoId);
    return {
      titulo: "Cronograma de desembolso", subtitulo: p ? p.codigo + " " + p.nome : "Portfólio de projetos", arquivo: "desembolso-" + (p ? p.codigo : "portfolio"), orientacao: "l",
      blocos: [
        { tipo: "kpis", titulo: "Resumo", itens: Array.prototype.map.call(document.querySelectorAll("#kpis .kpi"), function (k) {
            return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" };
          }) },
        { tipo: "grafico", titulo: "Desembolso mensal", canvas: document.getElementById("g-mensal") },
        { tipo: "tabela", titulo: "Saldo a pagar por mês", dados: tabela.exportacao() }
      ]
    };
  });

  GI.util.pronto().then(function () {
    projetoId = GI.fin.projeto(function (id) { projetoId = id; carregar(); });
    if (projetoId == null) {
      nivel = 1;
      document.getElementById("f-nivel").innerHTML = '<option value="1" selected>Mostrar projetos</option><option value="2">Mostrar pacotes principais</option>';
    }
    document.getElementById("f-nivel").addEventListener("change", function (ev) { nivel = Number(ev.target.value); render(); });
    document.getElementById("btn-enviar").addEventListener("click", enviar);
    return carregar();
  });
})(window.GI = window.GI || {});
