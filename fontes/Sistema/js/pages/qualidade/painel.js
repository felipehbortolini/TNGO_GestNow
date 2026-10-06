/* ==========================================================================
   Qualidade > Painel (06)
   Indicadores (RNC, tratamento, aprovação em inspeções, auditorias, custo da não
   qualidade), série de 6 meses, Pareto por disciplina, origens, pauta de tratamento
   e desempenho por empresa. Cálculos só em GI.api.qualidade.painel.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt, Q = GI.qld, API = GI.api.qualidade;
  var projetoId, dados = null, tPauta, tEmp, prazos = null;

  function render() {
    var i = dados.indicadores;
    var tela = function (t, p) { return U.tela("qualidade", t, Object.assign({ projeto: projetoId }, p || {})); };
    /* Limite de tratamento: faixa dos prazos por severidade (parâmetros da qualidade) */
    var faixaPrazo = prazos ? Object.keys(prazos).map(function (k) { return prazos[k]; }) : [];
    var limiteTratamento = faixaPrazo.length ? F.num(Math.min.apply(null, faixaPrazo)) + " a " + F.num(Math.max.apply(null, faixaPrazo)) + " dias" : "·";
    document.getElementById("kpis").innerHTML = [
      U.kpi({ rotulo: "RNC em aberto", valor: F.num(i.rncAbertas), icone: "octagonAlert", cor: i.rncVencidas || i.rncCriticasAbertas ? "danger" : i.rncAbertas ? "warning" : "success",
        esperado: { rotulo: "Esperado", valor: "0" },
        rodape: U.plural(i.rncVencidas, "vencida", "vencidas") + " · " + U.plural(i.rncCriticasAbertas, "crítica", "críticas"), href: tela("rnc") }),
      U.kpi({ rotulo: "Tempo médio de tratamento", valor: i.tempoMedioTratamentoDias == null ? "·" : F.num(i.tempoMedioTratamentoDias), unidade: i.tempoMedioTratamentoDias == null ? "" : "dias",
        icone: "clock", cor: "info", esperado: { rotulo: "Limite", valor: limiteTratamento }, rodape: U.plural(i.rncEncerradas, "RNC encerrada", "RNCs encerradas") + (i.eficaciaPrimeiraPct != null ? " · " + F.pct(i.eficaciaPrimeiraPct, 0) + " eficazes na 1ª verificação" : "") }),
      U.kpi({ rotulo: "Aprovação em inspeções", valor: i.aprovacaoInspecoesPct == null ? "·" : F.num(i.aprovacaoInspecoesPct, 1), unidade: i.aprovacaoInspecoesPct == null ? "" : "%", icone: "clipboardCheck",
        cor: i.aprovacaoInspecoesPct == null ? "info" : i.aprovacaoInspecoesPct >= i.metaAprovacaoInspecaoPct ? "success" : "warning",
        esperado: { rotulo: "Meta", valor: F.pct(i.metaAprovacaoInspecaoPct, 0) },
        rodape: U.plural(i.inspecoesReprovadas, "reprovada", "reprovadas") + " em " + F.num(i.inspecoes), href: tela("inspecoes") }),
      U.kpi({ rotulo: "Conformidade em auditorias", valor: i.conformidadeAuditoriasPct == null ? "·" : F.num(i.conformidadeAuditoriasPct, 1), unidade: i.conformidadeAuditoriasPct == null ? "" : "%",
        icone: "shieldCheck", cor: i.conformidadeAuditoriasPct == null ? "info" : i.conformidadeAuditoriasPct >= i.metaConformidadeAuditoriaPct ? "success" : "warning",
        esperado: { rotulo: "Meta", valor: F.pct(i.metaConformidadeAuditoriaPct, 0) },
        rodape: "programa " + (i.aderenciaProgramaPct == null ? "·" : F.pct(i.aderenciaProgramaPct, 0)) + " cumprido · " + U.plural(i.auditoriasAtrasadas, "atrasada", "atrasadas"), href: tela("auditorias") }),
      U.kpi({ rotulo: "Custo da não qualidade", moeda: i.custoNaoQualidadeCentavos, icone: "coins", cor: i.custoNaoQualidadeCentavos ? "danger" : "success",
        esperado: { rotulo: "Esperado", valor: F.moedaCompacta(0) }, rodape: "soma das RNC (retrabalho, reparo, ensaios e perdas)" })
    ].join("");

    var al = document.getElementById("alerta-auditorias");
    al.hidden = !dados.auditoriasAtrasadas.length;
    al.innerHTML = dados.auditoriasAtrasadas.length ? U.icone("calendarClock") + '<div class="alert__body"><b>' + U.esc(U.plural(dados.auditoriasAtrasadas.length, "auditoria atrasada", "auditorias atrasadas")) + "</b>: " +
      dados.auditoriasAtrasadas.map(function (a) { return U.esc(a.codigo + " " + a.escopo + " (planejada para " + F.data(a.data) + ")"); }).join("; ") + "." : "";

    var s = dados.serie;
    GI.charts.bar("g-rnc-mes", { labels: s.map(function (x) { return U.mesCurto(x.mes); }), ariaLabel: "RNC abertas e encerradas por mês",
      series: [{ label: "Abertas", data: s.map(function (x) { return x.abertas; }), color: "chart-2" }, { label: "Encerradas", data: s.map(function (x) { return x.encerradas; }), color: "chart-1" }] });
    document.getElementById("sub-aprov").textContent = "% de inspeções aprovadas por mês (ressalva conta como aprovada) · meta " + F.pct(i.metaAprovacaoInspecaoPct, 0);
    GI.charts.line("g-aprov", { labels: s.map(function (x) { return U.mesCurto(x.mes); }), percent: true, min: 0, max: 100, ariaLabel: "Aprovação em inspeções por mês",
      series: [{ label: "Aprovação", data: s.map(function (x) { return x.aprovacaoPct; }), color: "chart-1" },
        { label: "Meta", data: s.map(function () { return i.metaAprovacaoInspecaoPct; }), color: "chart-baseline", dashed: true }] });
    var pd = dados.porDisciplina;
    GI.charts.bar("g-pareto", { labels: pd.map(function (x) { return x.nome; }), horizontal: true, ariaLabel: "Pareto de RNC por disciplina",
      series: [{ label: "RNC", data: pd.map(function (x) { return x.total; }), color: "chart-1" }] });
    var po = dados.porOrigem;
    GI.charts.bar("g-origem", { labels: po.map(function (x) { return x.nome; }), horizontal: true, ariaLabel: "RNC por origem",
      series: [{ label: "RNC", data: po.map(function (x) { return x.total; }), color: "chart-3" }] });

    document.getElementById("sub-pauta").textContent = dados.pauta.length
      ? U.plural(dados.pauta.length, "RNC pede decisão", "RNCs pedem decisão") + ": prazo vencido, verificação vencida, severidade crítica ou concessão pendente"
      : "Nenhuma RNC fora do prazo, crítica ou com concessão pendente";
    tPauta.atualizar(dados.pauta, true);
    tEmp.atualizar(dados.porEmpresa, true);
  }

  function montar() {
    tPauta = GI.tabela.criar("pauta", {
      porPagina: 10, legenda: "Pauta de tratamento", vazio: "Nenhuma RNC na pauta.", ordem: { coluna: "diasAtraso", direcao: "desc" },
      colunas: (projetoId == null ? [U.colunaProjeto()] : []).concat([
        { id: "codigo", titulo: "RNC", classe: "nowrap", html: function (r) { return '<a href="' + U.tela("qualidade", "rnc", { busca: r.codigo }) + '"><b>' + U.esc(r.codigo) + "</b></a>"; } },
        { id: "descricao", titulo: "Não conformidade", html: function (r) { return '<div class="cell-title"><b>' + U.esc(r.descricao) + "</b><small>" + U.esc(r.disciplina + " · " + U.empresa(r.empresaId)) + "</small></div>"; },
          exportar: function (r) { return r.descricao; } },
        { id: "severidade", titulo: "Severidade", html: function (r) { return Q.severidade(r.severidade); }, exportar: function (r) { return r.severidade; } },
        { id: "situacao", titulo: "Situação", html: function (r) { return Q.situacaoRnc(r.situacao); }, exportar: function (r) { return r.situacao; } },
        { id: "diasAtraso", titulo: "Atraso", tipo: "num", html: function (r) { return r.diasAtraso ? '<span class="valor--negativo">' + U.esc(U.plural(r.diasAtraso, "dia")) + "</span>" : "·"; } },
        { id: "motivos", titulo: "Motivo", valor: function (r) { return r.motivos.join("; "); } }
      ])
    });
    tEmp = GI.tabela.criar("empresas", {
      porPagina: 10, legenda: "Desempenho por empresa", vazio: "Sem registros.", ordem: { coluna: "rncs", direcao: "desc" },
      colunas: [
        { id: "nome", titulo: "Empresa" },
        { id: "inspecoes", titulo: "Inspeções", tipo: "num" },
        { id: "reprovadas", titulo: "Reprovadas", tipo: "num" },
        { id: "aprovacaoPct", titulo: "Aprovação", tipo: "num", html: function (e) { return e.aprovacaoPct == null ? "·" : U.esc(F.pct(e.aprovacaoPct)); }, exportar: function (e) { return e.aprovacaoPct == null ? "" : F.pct(e.aprovacaoPct); } },
        { id: "rncs", titulo: "RNC", tipo: "num" },
        { id: "custoCentavos", titulo: "Custo da não qualidade", tipo: "moeda" }
      ]
    });
  }

  function carregar() {
    return Promise.all([API.painel(projetoId), GI.api.parametros()]).then(function (r) {
      dados = r[0]; prazos = ((r[1] || {}).qualidade || {}).prazoTratamentoDias || null; render();
    });
  }

  GI.exportar.registrar(function () {
    var p = U.projeto(projetoId);
    return {
      titulo: "Painel da qualidade", subtitulo: p ? p.codigo + " " + p.nome : "Portfólio de projetos", arquivo: "painel-qualidade-" + (p ? p.codigo : "portfolio"), orientacao: "l",
      blocos: [
        { tipo: "kpis", titulo: "Indicadores", itens: Array.prototype.map.call(document.querySelectorAll("#kpis .kpi"), function (k) {
          return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" }; }) },
        { tipo: "grafico", titulo: "RNC por mês", canvas: document.getElementById("g-rnc-mes") },
        { tipo: "grafico", titulo: "Aprovação em inspeções", canvas: document.getElementById("g-aprov") },
        { tipo: "grafico", titulo: "Pareto de RNC por disciplina", canvas: document.getElementById("g-pareto") },
        { tipo: "grafico", titulo: "RNC por origem", canvas: document.getElementById("g-origem") },
        { tipo: "tabela", titulo: "Pauta de tratamento", dados: tPauta.exportacao() },
        { tipo: "tabela", titulo: "Desempenho por empresa", dados: tEmp.exportacao() }
      ]
    };
  });

  Q.pronto().then(function () {
    projetoId = Q.projeto();
    document.getElementById("lnk-rnc").href = U.tela("qualidade", "rnc", { projeto: projetoId });
    montar();
    return carregar();
  });
})(window.GI = window.GI || {});
