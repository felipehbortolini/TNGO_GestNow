/* ==========================================================================
   Planejamento > Curva S
   Linha de base (tracejada), Real e Tendência (tracejada); tabela período a
   período; registro do avanço do mês (entrada de dados). No Portfólio: Curva S
   ponderada pelos pesos da carteira e composição por projeto (peso, avanço e
   contribuição para o desvio); o registro do avanço pede o projeto.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt;
  var projetoId = GI.api.projetoAtualId();
  var dados = null, tabela, tCarteira = null, carteira = null;

  function linhas(c) {
    return c.meses.map(function (m, i) {
      return {
        mes: m, previsto: c.baseline[i], real: c.real[i], tendencia: c.tendencia[i],
        prevMes: i ? c.baseline[i] - c.baseline[i - 1] : c.baseline[i],
        realMes: c.real[i] == null ? null : (i ? c.real[i] - (c.real[i - 1] || 0) : c.real[i]),
        desvio: c.real[i] == null ? null : Math.round((c.real[i] - c.baseline[i]) * 10) / 10,
        corte: m === c.corte
      };
    });
  }

  function render() {
    var c = dados.curva, ind = dados.indices;
    if (!c) {
      document.getElementById("kpis").innerHTML = "";
      document.getElementById("g-curva").parentNode.innerHTML = U.vazio(projetoId == null ? "Nenhum projeto da carteira tem Curva S cadastrada." : "Este projeto ainda não tem Curva S cadastrada.", "curve");
      tabela.atualizar([]);
      return;
    }
    var atraso = ind.terminoTendencia && ind.terminoBaseline && ind.terminoTendencia > ind.terminoBaseline;
    document.getElementById("kpis").innerHTML = [
      U.kpi({ rotulo: "Previsto acumulado", valor: F.num(ind.previsto, 1), unidade: "%", icone: "curve", cor: "info",
        esperado: { rotulo: "Linha de base", valor: ind.terminoBaseline ? "100% em " + U.mesCurto(ind.terminoBaseline) : F.pct(100, 0) },
        rodape: "linha de base em " + U.mesCurto(ind.corte) }),
      U.kpi({ rotulo: "Real acumulado", valor: F.num(ind.real, 1), unidade: "%", icone: "trendingUp", cor: "primary",
        esperado: { rotulo: "Previsto", valor: F.pct(ind.previsto, 1) },
        rodape: ind.anterior ? "+" + F.num(ind.real - ind.anterior.real, 1) + " p.p. no mês" : "" }),
      U.kpi({ rotulo: "Desvio", valor: (ind.desvioPP > 0 ? "+" : "") + F.num(ind.desvioPP, 1), unidade: "p.p.", icone: "alertTriangle", cor: ind.desvioPP < 0 ? "danger" : "success",
        esperado: { rotulo: "Meta", valor: "≥ " + F.num(0) }, rodape: "real menos previsto" }),
      U.kpi({ rotulo: "SPI", valor: F.indice(ind.spi), icone: "gauge", cor: ind.spi >= 1 ? "success" : ind.spi >= 0.95 ? "warning" : "danger",
        esperado: { rotulo: "Meta", valor: "≥ " + F.indice(1) }, rodape: ind.anterior ? "mês anterior " + F.indice(ind.anterior.spi) : "", href: U.tela("planejamento", "kpis", { projeto: projetoId }) }),
      U.kpi({ rotulo: "Término pela tendência", valor: U.mesCurto(ind.terminoTendencia), icone: "flag", cor: atraso ? "danger" : "success",
        esperado: { rotulo: "Linha de base", valor: U.mesCurto(ind.terminoBaseline) } })
    ].join("");
    document.getElementById("sub-curva").textContent = "Corte em " + U.mesCurto(c.corte) + " · % acumulado por mês" +
      (projetoId == null ? " · média ponderada pelos pesos dos projetos na carteira" : "");
    GI.charts.sCurve("g-curva", {
      labels: c.meses.map(U.mesCurto), baseline: c.baseline, real: c.real, forecast: c.tendencia,
      ariaLabel: projetoId == null ? "Curva S física da carteira (ponderada): previsto, real e tendência acumulados por mês" : "Curva S física do projeto: previsto, real e tendência acumulados por mês"
    });
    renderCarteira();
    tabela.atualizar(linhas(c));
  }

  function carregar() {
    return Promise.all([GI.api.planejamento.curvaFisica(projetoId), projetoId == null ? GI.api.portfolio.resumo() : Promise.resolve(null)])
      .then(function (r) { dados = r[0]; carteira = r[1]; render(); });
  }

  /* Portfólio: composição da carteira (peso, avanço e contribuição para o desvio ponderado) */
  function renderCarteira() {
    var sec = document.getElementById("sec-carteira");
    if (!sec) return;
    sec.hidden = projetoId != null || !carteira;
    if (sec.hidden) return;
    if (!tCarteira) {
      tCarteira = GI.tabela.criar("tabela-carteira", {
        porPagina: 0, legenda: "Composição da carteira", ordem: { coluna: "peso", direcao: "desc" },
        colunas: [
          U.colunaProjeto("projetoId", { titulo: "Projeto", html: function (x) { return '<b data-sem-traducao>' + U.esc(x.codigo) + '</b><span class="linha-sub" data-sem-traducao>' + U.esc(x.nome) + "</span>"; } }),
          { id: "peso", titulo: "Peso na carteira", tipo: "pct" },
          { id: "previsto", titulo: "Previsto acumulado", tipo: "pct" },
          { id: "real", titulo: "Real acumulado", tipo: "pct" },
          { id: "desvioPP", titulo: "Desvio (p.p.)", tipo: "num", casas: 1,
            html: function (x) { return x.desvioPP == null ? "" : '<span class="' + (x.desvioPP < 0 ? "valor--negativo" : "valor--positivo") + '">' + (x.desvioPP > 0 ? "+" : "") + F.num(x.desvioPP, 1) + "</span>"; } },
          { id: "spi", titulo: "SPI", tipo: "indice" },
          { id: "contribuicao", titulo: "Contribuição para o desvio (p.p.)", tipo: "num", casas: 2,
            valor: function (x) { return x.desvioPP == null ? null : Math.round(x.peso * x.desvioPP) / 100; },
            html: function (x) { if (x.desvioPP == null) return ""; var v = Math.round(x.peso * x.desvioPP) / 100; return '<span class="' + (v < 0 ? "valor--negativo" : "") + '">' + (v > 0 ? "+" : "") + F.num(v, 2) + "</span>"; } },
          { id: "terminoTendencia", titulo: "Término pela tendência", valor: function (x) { return x.terminoTendencia || ""; },
            html: function (x) { return x.terminoTendencia ? U.esc(U.mesCurto(x.terminoTendencia)) + ' <span class="text-small text-muted">LB ' + U.esc(U.mesCurto(x.terminoBaseline)) + "</span>" : ""; } }
        ],
        acoes: function (x) { return '<a class="btn btn--ghost btn--sm" href="' + U.tela("planejamento", "curva-s", { projeto: x.projetoId }) + '">' + U.icone("chevronRight") + "Abrir</a>"; }
      });
    }
    tCarteira.atualizar(carteira.projetos);
  }

  function proximoMes(m) {
    var a = Number(m.slice(0, 4)), n = Number(m.slice(5, 7)) + 1;
    if (n > 12) { n = 1; a++; }
    return a + "-" + String(n).padStart(2, "0");
  }

  function registrarAvanco() {
    if (projetoId == null) { U.noProjeto("avanco", "Registrar avanço do mês"); return; }
    var c = dados.curva;
    if (!c) return;
    var mes = proximoMes(c.corte);
    var i = c.meses.indexOf(mes);
    if (i < 0) { GI.ui.toast("A curva não tem o mês " + U.mesCurto(mes) + ". Revise a linha de base.", "warning"); return; }
    var anterior = c.real[c.meses.indexOf(c.corte)];
    GI.form.abrir({
      titulo: "Registrar avanço do mês", subtitulo: "Mês " + U.mesCurto(mes) + " · previsto " + F.pct(c.baseline[i]),
      intro: '<p class="text-small text-muted">O real acumulado anterior é ' + F.pct(anterior) + ". A tendência passa a partir deste ponto; o que já foi registrado não muda.</p>",
      campos: [
        { id: "real", rotulo: "Real acumulado (%)", tipo: "numero", obrigatorio: true, min: anterior, maxNumero: 100, passo: 0.1 },
        { id: "tendencia", rotulo: "Tendência de término", tipo: "select", obrigatorio: true, valor: "manter",
          opcoes: [{ valor: "manter", texto: "Manter a tendência atual" }, { valor: "baseline", texto: "Seguir o ritmo da linha de base" }] },
        { id: "comentario", rotulo: "Comentário do mês", tipo: "textarea", max: 300 }
      ],
      aoSalvar: function (v) {
        return GI.api.obter("curvaFisica", c.id).then(function (o) {
          o.real[i] = v.real;
          o.corte = mes;
          /* Tendência: começa no ponto real e segue até 100 */
          for (var k = 0; k < o.meses.length; k++) {
            if (k < i) o.tendencia[k] = null;
            else if (k === i) o.tendencia[k] = v.real;
            else if (v.tendencia === "baseline") o.tendencia[k] = Math.min(100, Math.round((v.real + (o.baseline[k] - o.baseline[i])) * 10) / 10);
            else o.tendencia[k] = Math.max(v.real, o.tendencia[k] == null ? v.real : o.tendencia[k]);
          }
          o.comentarios = (o.comentarios || []).concat(v.comentario ? [{ mes: mes, texto: v.comentario, porId: GI.api.sessaoAtual().pessoaId }] : []);
          return GI.api.salvar("curvaFisica", o);
        }).then(function () { GI.ui.toast("Avanço de " + U.mesCurto(mes) + " registrado.", "success"); return carregar(); });
      }
    });
  }

  GI.exportar.registrar(function () {
    var p = U.projeto(projetoId);
    return {
      titulo: projetoId == null ? "Curva S física da carteira" : "Curva S física", subtitulo: p ? p.codigo + " " + p.nome : "Portfólio de projetos", arquivo: "curva-s-" + (p ? p.codigo : "portfolio"),
      blocos: (projetoId == null && tCarteira ? [{ tipo: "tabela", titulo: "Composição da carteira", dados: tCarteira.exportacao() }] : []).concat([
        { tipo: "kpis", titulo: "Indicadores", itens: Array.prototype.map.call(document.querySelectorAll("#kpis .kpi"), function (k) {
            return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" };
          }) },
        { tipo: "grafico", titulo: "Curva S", canvas: document.getElementById("g-curva") },
        { tipo: "tabela", titulo: "Período a período", dados: tabela.exportacao() }
      ])
    };
  });

  GI.util.pronto().then(function () {
    document.getElementById("btn-avanco").addEventListener("click", registrarAvanco);
    tabela = GI.tabela.criar("tabela", {
      porPagina: 0, legenda: "Curva S período a período",
      colunas: [
        { id: "mes", titulo: "Mês", valor: function (l) { return l.mes; }, html: function (l) { return U.esc(U.mesCurto(l.mes)) + (l.corte ? " " + U.badge("corte", "primary") : ""); },
          exportar: function (l) { return U.mesCurto(l.mes); } },
        { id: "prevMes", titulo: "Previsto no mês (p.p.)", tipo: "num", casas: 1 },
        { id: "previsto", titulo: "Previsto acumulado", tipo: "pct" },
        { id: "realMes", titulo: "Real no mês (p.p.)", tipo: "num", casas: 1 },
        { id: "real", titulo: "Real acumulado", tipo: "pct" },
        { id: "tendencia", titulo: "Tendência", tipo: "pct" },
        { id: "desvio", titulo: "Desvio (p.p.)", tipo: "num", casas: 1,
          html: function (l) { return l.desvio == null ? "" : '<span class="' + (l.desvio < 0 ? "valor--negativo" : "") + '">' + (l.desvio > 0 ? "+" : "") + F.num(l.desvio, 1) + "</span>"; } }
      ],
      classeLinha: function (l) { return l.corte ? "is-selected" : ""; }
    });
    return carregar().then(function () { if (U.acaoPendente() === "avanco") registrarAvanco(); });
  });
})(window.GI = window.GI || {});
