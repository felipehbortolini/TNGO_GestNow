/* ==========================================================================
   Gestão Financeira > Mapa de controle da EAC
   Item a item e subtotal por pacote: orçado, comprometido, realizado, saldo a
   comprometer, projeção no término e desvio com mapa de calor (faixas nos
   parâmetros). Entrada de dados: custos do ERP (planilha) e projeção por item.
   Portfólio: projeto > pacotes principais; maiores sobrecustos entre os itens
   de todos os projetos; importação pede o projeto.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt, M = function (c) { return GI.fin.mil(c); };
  var projetoId, dados = null, limites = [1, 5, 10], tabela, tTop, reservas = null, linhaBase = null, previstoCorte = null;
  var filtro = { busca: "", nivel: 3, desvio: false };
  var rec, arvoreCompleta = [], folhasCarteira = []; /* rec: recolher/expandir (GI.fin.recolhimento) */

  function porCodigo(c) { return dados.itens.filter(function (x) { return x.codigo === c; })[0]; }
  function pct(v, base) { return base ? v / base * 100 : null; }

  function render() {
    var t = dados.total;
    if (!dados.itens.length) {
      document.getElementById("kpis").innerHTML = "";
      document.getElementById("sub-mapa").textContent = "Este projeto ainda não tem EAC cadastrada.";
      tabela.atualizar([]); tTop.atualizar([]);
      return;
    }
    document.getElementById("kpis").innerHTML = [
      U.kpi({ rotulo: "Orçado atual", moeda: t.atual, icone: "money", cor: "primary", rodape: "linha de base mais remanejamentos",
        esperado: { rotulo: "Linha de base", valor: linhaBase == null ? "·" : F.moedaCompacta(linhaBase) },
        href: U.tela("financeiro", "eac", { projeto: projetoId }) }),
      U.kpi({ rotulo: "Comprometido", moeda: t.comprometido, icone: "fileContract", cor: "info", rodape: F.pct(pct(t.comprometido, t.atual)) + " do orçado atual",
        esperado: { rotulo: "Orçado", valor: F.moedaCompacta(t.atual) } }),
      U.kpi({ rotulo: "Realizado", moeda: t.realizado, icone: "coins", cor: "info", rodape: F.pct(pct(t.realizado, t.atual)) + " do orçado atual",
        esperado: { rotulo: "Previsto", valor: previstoCorte == null ? "·" : F.moedaCompacta(previstoCorte) } }),
      U.kpi({ rotulo: "Projeção no término", moeda: t.projecao, icone: "target", cor: t.desvio > 0 ? "warning" : "success",
        esperado: { rotulo: "Orçado", valor: F.moedaCompacta(t.atual) },
        rodape: "saldo a comprometer " + F.moedaCompacta(t.saldoAComprometer) }),
      U.kpi({ rotulo: "Desvio no término", moeda: t.desvio, sinal: true, icone: "alertTriangle", cor: t.desvio > 0 ? "danger" : "success",
        esperado: [{ rotulo: "Esperado", valor: "0" }, { rotulo: "Limite", valor: "≤ " + F.moedaCompacta(Math.round(t.atual * limites[0] / 100)) }],
        rodape: GI.fin.calor(t) + " projeção menos orçado" })
    ].join("");
    renderReservas();
    document.getElementById("sub-mapa").textContent = "Valores em R$ mil · desvio = projeção no término menos orçado atual (positivo = sobrecusto)";
    document.getElementById("legenda").innerHTML = GI.fin.legendaCalor(limites);
    renderTabela();
    tTop.atualizar((projetoId == null ? folhasCarteira : dados.itens).filter(function (x) { return x.nivel === 3 && x.desvio > 0; })
      .sort(function (a, b) { return b.desvio - a.desvio; }).slice(0, 5));
  }

  /* Reservas: o saldo da contingência cobre o desvio projetado? (detalhe em 03 Contingência) */
  function renderReservas() {
    var el = document.getElementById("reservas"), r = reservas, t = dados.total;
    el.hidden = !r;
    if (!r) return;
    var c = r.contingencia, cobre = t.desvio <= 0 || c.saldo >= t.desvio;
    el.className = "alert mt-4 alert--" + (cobre ? "info" : "warning");
    el.innerHTML = U.icone("shieldCheck") + '<div class="alert__body"><b>Reservas</b>: contingência com saldo de ' + U.esc(F.moeda(c.saldo)) + " (" + U.esc(F.pct(c.consumoPct, 1)) + " consumida; " +
      U.esc(F.moeda(c.emAnalise)) + " pedidos em SMs em análise) e reserva gerencial de " + U.esc(F.moeda(r.gerencial.saldo)) + ". " +
      (t.desvio > 0 ? (cobre ? "O saldo da contingência cobre o desvio projetado no término (" + U.esc(F.moeda(t.desvio)) + "), só por SM aprovada." :
        "O desvio projetado no término (" + U.esc(F.moeda(t.desvio)) + ") supera o saldo da contingência.") : "Sem desvio projetado a cobrir.") +
      ' <a href="' + U.tela("financeiro", "contingencia", { projeto: projetoId }) + '">Abrir Contingência</a></div>';
  }
  function renderTabela() {
    var folha = projetoId == null ? 2 : 3;
    var so = filtro.desvio ? function (x) { return x.nivel === folha && x.faixa !== "neutro"; } : null;
    var p = U.projeto(projetoId) || {};
    /* Primeira linha: atividade resumo do projeto (ou do portfólio) com os totais do mapa */
    var raiz = Object.assign({}, dados.total, { descricao: projetoId == null ? "Portfólio de projetos" : p.nome || "Projeto", responsavelId: p.gerenteId });
    arvoreCompleta = GI.fin.arvore(dados.itens, { busca: filtro.busca, nivel: filtro.nivel, so: so, raiz: raiz });
    tabela.atualizar(rec.aplicar(arvoreCompleta));
  }

  /* Referências dos cards: linha de base Rev 0 (EAC) e planejado acumulado no corte (curva financeira) */
  function linhaBaseDe(e) {
    if (!e) return null;
    if (e.portfolio) { var l = (e.revisoes || []).filter(function (v) { return v.linhaBase != null; }); return l.length ? l.reduce(function (s, v) { return s + v.linhaBase; }, 0) : null; }
    return e.revisoes && e.revisoes.length ? e.revisoes[0].totalCentavos : null;
  }
  function planejadoNoCorte(c) {
    if (!c) return null;
    var k = c.meses.indexOf(c.corte);
    return k < 0 ? null : c.planejado[k];
  }

  function carregar() {
    var extras = projetoId == null ? U.listaProjetos().map(function (pj) { return GI.api.financeiro.mapaControle(pj.id).then(function (m) { return m.itens.map(function (x) { x.projetoId = pj.id; return x; }); }); }) : [];
    return Promise.all([GI.api.financeiro.mapaControle(projetoId), GI.api.parametros(), GI.api.financeiro.contingencia(projetoId),
      GI.api.financeiro.eac(projetoId), GI.api.financeiro.curvaFinanceira(projetoId)].concat(extras)).then(function (r) {
      dados = r[0]; limites = r[1].financeiro.faixasDesvio; reservas = r[2];
      linhaBase = linhaBaseDe(r[3]); previstoCorte = planejadoNoCorte(r[4]);
      folhasCarteira = [].concat.apply([], r.slice(5));
      render();
    });
  }

  /* Projeção no término de um item (estimativa do responsável) */
  function atualizarProjecao(codigo) {
    var x = porCodigo(codigo);
    var hist = (x.historicoProjecao || []).slice().reverse();
    GI.form.abrir({
      titulo: "Atualizar projeção no término", subtitulo: x.codigo + " " + x.descricao,
      intro: '<dl class="dl"><dt>Orçado atual</dt><dd class="num">' + F.moeda(x.atual) + "</dd><dt>Comprometido</dt><dd class=\"num\">" + F.moeda(x.comprometido) +
        '</dd><dt>Realizado</dt><dd class="num">' + F.moeda(x.realizado) + "</dd><dt>Projeção vigente</dt><dd class=\"num\">" + F.moeda(x.projecao) + "</dd></dl>" +
        (hist.length ? '<p class="text-small text-muted mt-4">Última alteração em ' + F.data(hist[0].data) + " por " + U.esc(U.pessoa(hist[0].porId)) + ": " + U.esc(hist[0].justificativa) + "</p>" : ""),
      campos: [
        { id: "projecao", rotulo: "Nova projeção no término", tipo: "moeda", obrigatorio: true, valor: x.projecao },
        { id: "desvio", rotulo: "Desvio resultante", tipo: "info", html: "" },
        { id: "justificativa", rotulo: "Justificativa", tipo: "textarea", obrigatorio: true, max: 300, placeholder: "Premissas: quantidades, preços, produtividade, pleitos" }
      ],
      aoMudar: function (v, ctx) {
        var d = (v.projecao > 0 ? v.projecao : x.projecao) - x.atual;
        var p = x.atual ? d / x.atual * 100 : null;
        ctx.info("desvio", '<span class="num">' + (d > 0 ? "+" : "") + U.esc(F.moeda(d)) + (p == null ? "" : " (" + (p > 0 ? "+" : "") + F.num(p, 1) + "%)") + "</span>");
      },
      aoSalvar: function (v) {
        return GI.api.financeiro.atualizarProjecao(projetoId, x.codigo, v.projecao, v.justificativa).then(function () {
          GI.ui.toast("Projeção de " + x.codigo + " atualizada.", "success");
          return carregar();
        });
      }
    });
  }

  /* Fechamento do mês: custos exportados do ERP */
  function importar() {
    if (projetoId == null) { U.noProjeto("importar", "Importar custos do ERP"); return; }
    if (!dados.itens.length) { GI.ui.toast("Cadastre a EAC do projeto antes de importar custos.", "warning"); return; }
    var folhas = dados.itens.filter(function (x) { return x.nivel === 3; });
    var codigos = folhas.map(function (x) { return x.codigo; });
    GI.importar.abrir({
      titulo: "Importar custos do ERP", subtitulo: "Fechamento do mês: comprometido, realizado e projeção por item", arquivoModelo: "modelo-custos-eac",
      colunas: [
        { campo: "codigo", titulo: "Código do item", tipo: "lista", obrigatorio: true, opcoes: codigos, exemplo: "3.1.2" },
        { campo: "comprometido", titulo: "Comprometido (R$)", tipo: "moeda", obrigatorio: true, exemplo: "3.550.000,00" },
        { campo: "realizado", titulo: "Realizado (R$)", tipo: "moeda", obrigatorio: true, exemplo: "3.100.000,00" },
        { campo: "projecao", titulo: "Projeção no término (R$)", tipo: "moeda", exemplo: "3.700.000,00" }
      ],
      validarLinha: function (l) {
        var e = [];
        if (l.comprometido < 0 || l.realizado < 0) e.push("Valores não podem ser negativos.");
        var x = folhas.filter(function (f) { return f.codigo === l.codigo; })[0];
        var proj = l.projecao != null ? l.projecao : (x ? x.projecao : null);
        if (proj != null && l.realizado != null && proj < l.realizado) e.push("Projeção no término menor que o realizado.");
        return e;
      },
      aoImportar: function (linhas) {
        return GI.api.financeiro.importarCustos(projetoId, linhas).then(function (n) {
          carregar();
          return U.plural(n, "item atualizado", "itens atualizados") + " no mapa de controle.";
        });
      }
    });
  }

  GI.exportar.registrar(function () {
    var p = U.projeto(projetoId);
    /* exporta a estrutura inteira, mesmo com linhas recolhidas na tela */
    tabela.atualizar(arvoreCompleta);
    var dadosMapa = tabela.exportacao();
    renderTabela();
    return {
      titulo: projetoId == null ? "Mapa de controle da carteira" : "Mapa de controle da EAC", subtitulo: p ? p.codigo + " " + p.nome : "Portfólio de projetos", arquivo: "mapa-controle-" + (p ? p.codigo : "portfolio"), orientacao: "l",
      blocos: [
        { tipo: "kpis", titulo: "Resumo", itens: Array.prototype.map.call(document.querySelectorAll("#kpis .kpi"), function (k) {
            return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" };
          }) },
        { tipo: "tabela", titulo: "Mapa de controle", dados: dadosMapa },
        { tipo: "tabela", titulo: "Maiores sobrecustos", dados: tTop.exportacao() }
      ]
    };
  });

  function colMoeda(id, titulo, extra) {
    return Object.assign({ id: id, titulo: titulo, tipo: "moeda", ordenavel: false, html: function (x) { return U.esc(M(x[id])); } }, extra || {});
  }

  GI.util.pronto().then(function () {
    rec = GI.fin.recolhimento("tabela", renderTabela);
    projetoId = GI.fin.projeto(function (id) { projetoId = id; rec.limpar(); carregar(); });
    if (projetoId == null) {
      filtro.nivel = 2;
      document.getElementById("f-nivel").innerHTML = '<option value="1">Mostrar projetos</option><option value="2" selected>Mostrar pacotes principais</option>';
      document.getElementById("t-mapa").textContent = "Mapa de controle da carteira";
    }
    document.getElementById("busca").addEventListener("input", U.debounce(function (ev) { filtro.busca = ev.target.value.trim(); rec.limpar(); renderTabela(); }, 200));
    document.getElementById("f-nivel").addEventListener("change", function (ev) { filtro.nivel = Number(ev.target.value); rec.limpar(); renderTabela(); });
    document.getElementById("f-desvio").addEventListener("change", function (ev) { filtro.desvio = ev.target.checked; rec.limpar(); renderTabela(); });
    document.getElementById("btn-importar").addEventListener("click", importar);
    document.getElementById("btn-colunas").addEventListener("click", function () { GI.tabela.escolherColunas(tabela); });

    tabela = GI.tabela.criar("tabela", {
      porPagina: 0, pilha: false, compacta: true, legenda: "Mapa de controle da EAC", vazio: "Nenhum item encontrado.",
      colunas: [
        { id: "codigo", titulo: "Código", ordenavel: false, fixa: true, classe: "nowrap",
          html: function (x) { return rec.botao(x) + U.esc(x.codigo); } },
        { id: "descricao", titulo: "Descrição", ordenavel: false, fixa: true,
          html: function (x) { return x.nivel < 3 ? "<b>" + U.esc(x.descricao) + "</b>" : U.esc(x.descricao); } },
        colMoeda("base", "Orçado na revisão", { oculta: true }),
        colMoeda("remanejamento", "Remanejado", { oculta: true, html: function (x) { return x.remanejamento ? (x.remanejamento > 0 ? "+" : "") + U.esc(M(x.remanejamento)) : ""; } }),
        colMoeda("atual", "Orçado atual"),
        colMoeda("comprometido", "Comprometido"),
        colMoeda("realizado", "Realizado"),
        colMoeda("saldoAComprometer", "Saldo a comprometer", { html: function (x) { return '<span class="' + (x.saldoAComprometer < 0 ? "valor--sobrecusto" : "") + '">' + U.esc(M(x.saldoAComprometer)) + "</span>"; } }),
        colMoeda("projecao", "Projeção no término", { html: function (x) { return "<b>" + U.esc(M(x.projecao)) + "</b>"; } }),
        colMoeda("desvio", "Desvio", { html: function (x) { return '<span class="' + (x.desvio > 0 ? "valor--sobrecusto" : x.desvio < 0 ? "valor--economia" : "") + '">' + (x.desvio > 0 ? "+" : "") + U.esc(M(x.desvio)) + "</span>"; } }),
        { id: "desvioPct", titulo: "Desvio %", tipo: "pct", ordenavel: false, html: GI.fin.calor }
      ],
      classeLinha: GI.fin.classeNivel,
      acoes: function (x) {
        return x.nivel === 3 ? '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-projecao="' + U.esc(x.codigo) + '" aria-label="Atualizar projeção de ' + U.esc(x.codigo) + '" title="Atualizar projeção">' + U.icone("target") + "</button>" : "";
      }
    });
    document.getElementById("tabela").addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-projecao]");
      if (b) atualizarProjecao(b.getAttribute("data-projecao"));
    });

    tTop = GI.tabela.criar("top", {
      porPagina: 0, legenda: "Maiores sobrecustos", vazio: "Nenhum item com sobrecusto projetado.",
      colunas: (projetoId == null ? [U.colunaProjeto()] : []).concat([
        { id: "codigo", titulo: "Código", ordenavel: false },
        { id: "descricao", titulo: "Descrição", ordenavel: false },
        { id: "atual", titulo: "Orçado atual", tipo: "moeda", ordenavel: false },
        { id: "projecao", titulo: "Projeção no término", tipo: "moeda", ordenavel: false },
        { id: "desvio", titulo: "Desvio", tipo: "moeda", ordenavel: false, html: function (x) { return '<span class="valor--sobrecusto">+' + U.esc(F.moeda(x.desvio)) + "</span>"; } },
        { id: "desvioPct", titulo: "Desvio %", tipo: "pct", ordenavel: false, html: GI.fin.calor },
        { id: "responsavel", titulo: "Responsável", ordenavel: false, valor: function (x) { return U.pessoa(x.responsavelId); } }
      ])
    });
    return carregar().then(function () { if (U.acaoPendente() === "importar" && projetoId != null) importar(); });
  });
})(window.GI = window.GI || {});
