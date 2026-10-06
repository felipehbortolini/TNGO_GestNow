/* ==========================================================================
   Gestão Financeira > EAC (Estrutura Analítica de Custos)
   Árvore pacote > subpacote > item; revisões do orçamento (Rev 0 = linha de
   base) e remanejamentos da revisão vigente (soma zero). Toda alteração de valor
   passa pela gestão de mudanças (08): remanejamento e item novo com recurso de
   outro item viram SM "Remanejamento de orçamento" (aplicada na aprovação);
   acréscimo ao total só por nova revisão a partir de SM aprovada com custo.
   Portfólio: linha 0 = portfólio, nível 1 = projeto e nível 2 = pacotes principais
   (nível 1 da EAC de cada projeto); só leitura, os cadastros pedem o projeto.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt;
  var TIPOS = ["Material", "Mão de obra", "Equipamento", "Serviço", "Indireto", "Contingência"];
  var UNIDADES = ["vb", "un", "m", "m²", "m³", "t", "kg", "Hh", "mês"];
  var projetoId, dados = null, tabela, tRev, tRem, contPrevista = null, contSaldo = null;
  var filtro = { busca: "", nivel: 3, tipo: "" };
  var rec, arvoreCompleta = []; /* rec: recolher/expandir (GI.fin.recolhimento) */

  function folhas() { return dados.mapa.itens.filter(function (x) { return x.nivel === 3; }); }
  function porCodigo(c, pid) {
    return dados.mapa.itens.filter(function (x) { return (x.codigoProjeto || x.codigo) === c && (pid == null || x.projetoId == null || x.projetoId === pid); })[0];
  }
  function saldo(x) { return x.atual - x.comprometido; }
  /* Saldo livre = a comprometer menos o reservado em SMs de remanejamento abertas */
  function saldoLivre(x) { return GI.api.financeiro.saldoLivre(projetoId, x.codigo); }
  function linhasRemanejamento() {
    return dados.remanejamentos.slice().reverse().concat((dados.remanejamentosPendentes || []).map(function (r) { return Object.assign({}, r); }));
  }
  function opcoesPessoas() {
    return Object.keys(U.mapas.pessoas).map(function (k) { return { valor: k, texto: U.mapas.pessoas[k].nome }; });
  }
  function rotuloItem(x) { return x.codigo + " " + x.descricao; }

  /* ---------------- Render ---------------- */
  function renderPortfolio() {
    var m = dados.mapa, ind = dados.indices || {};
    var projetos = m.itens.filter(function (x) { return x.nivel === 1; });
    var reman = dados.remanejamentos.reduce(function (s, r) { return s + r.valorCentavos; }, 0);
    var base = dados.revisoes.reduce(function (s, r) { return s + (r.linhaBase || 0); }, 0);
    var variacao = base ? (m.total.atual - base) / base * 100 : null;
    var disponivel = contSaldo;
    document.getElementById("kpis").innerHTML = [
      U.kpi({ rotulo: "Orçamento vigente da carteira", moeda: m.total.atual, icone: "money", cor: "primary",
        esperado: { rotulo: "Linha de base", valor: base ? F.moedaCompacta(base) : "·" },
        rodape: variacao ? "variação " + (variacao > 0 ? "+" : "") + F.num(variacao, 1) + "%" : "" }),
      U.kpi({ rotulo: "Projetos", valor: F.num(projetos.length), icone: "listTree", cor: "info",
        esperado: { rotulo: "Referência", valor: F.num(U.listaProjetos().length) },
        rodape: U.plural(m.itens.filter(function (x) { return x.nivel === 2; }).length, "pacote principal", "pacotes principais") }),
      U.kpi({ rotulo: "Remanejado nas revisões vigentes", moeda: reman, icone: "swap", cor: "info",
        esperado: { rotulo: "Referência", valor: F.moedaCompacta(m.total.base) }, rodape: U.plural(dados.remanejamentos.length, "remanejamento") + " · soma zero" + pendentesTxt() }),
      U.kpi({ rotulo: "Contingência disponível", valor: disponivel == null ? "·" : null, moeda: disponivel == null ? null : disponivel, icone: "shieldCheck",
        cor: ind.contingenciaPct > 50 ? "warning" : "success", rodape: ind.contingenciaPct == null ? "" : F.pct(ind.contingenciaPct) + " consumida por SMs aprovadas",
        esperado: { rotulo: "Previsto", valor: contPrevista == null ? "·" : F.moedaCompacta(contPrevista) } }),
      U.kpi({ rotulo: "SMs a incorporar", valor: F.num(dados.smsPendentes.length), icone: "fileText", cor: dados.smsPendentes.length ? "warning" : "success",
        esperado: { rotulo: "Esperado", valor: "0" },
        rodape: dados.smsPendentes.length ? dados.smsPendentes.map(function (s) { return s.projetoCodigo; }).filter(function (x, k, l) { return l.indexOf(x) === k; }).join(", ") : "orçamentos em dia com as SMs" })
    ].join("");
    document.getElementById("sub-eac").textContent = "Portfólio: projeto e pacotes principais · orçado atual = orçado na revisão vigente + remanejamentos";
    document.getElementById("sub-rem").textContent = "Remanejamentos das revisões vigentes de cada projeto e os propostos em SMs abertas";
    renderTabela();
    tRev.atualizar(dados.revisoes.map(function (r) { return Object.assign({}, r, { vigente: true, variacao: r.linhaBase != null ? r.totalCentavos - r.linhaBase : null,
      variacaoPct: r.linhaBase ? (r.totalCentavos - r.linhaBase) / r.linhaBase * 100 : null }); }));
    tRem.atualizar(linhasRemanejamento());
  }

  function render() {
    if (dados.portfolio) { renderPortfolio(); return; }
    var m = dados.mapa;
    var vig = dados.vigente, rev0 = dados.revisoes[0];
    if (!m.itens.length) {
      document.getElementById("kpis").innerHTML = "";
      document.getElementById("sub-eac").textContent = "Este projeto ainda não tem EAC cadastrada.";
      document.getElementById("sub-rem").textContent = "";
      tabela.atualizar([]); tRev.atualizar([]); tRem.atualizar([]);
      return;
    }
    var reman = dados.remanejamentos.reduce(function (s, r) { return s + r.valorCentavos; }, 0);
    var ind = dados.indices || {};
    var variacao = rev0 && rev0.totalCentavos ? (m.total.atual - rev0.totalCentavos) / rev0.totalCentavos * 100 : null;
    var disponivel = contSaldo;
    var pacotes = m.itens.filter(function (x) { return x.nivel === 1; }).length, subs = m.itens.filter(function (x) { return x.nivel === 2; }).length;
    document.getElementById("kpis").innerHTML = [
      U.kpi({ rotulo: "Orçamento vigente", moeda: m.total.atual, icone: "money", cor: "primary",
        esperado: { rotulo: "Linha de base", valor: rev0 ? F.moedaCompacta(rev0.totalCentavos) : "·" },
        rodape: [vig ? "Rev " + vig.revisao : "", variacao ? "variação " + (variacao > 0 ? "+" : "") + F.num(variacao, 1) + "%" : ""].filter(Boolean).join(" · ") }),
      U.kpi({ rotulo: "Itens de custo", valor: F.num(folhas().length), icone: "listTree", cor: "info",
        esperado: { rotulo: "Referência", valor: U.plural(pacotes, "pacote") },
        rodape: U.plural(subs, "subpacote") }),
      U.kpi({ rotulo: "Remanejado na revisão", moeda: reman, icone: "swap", cor: "info",
        esperado: { rotulo: "Referência", valor: F.moedaCompacta(m.total.base) },
        rodape: U.plural(dados.remanejamentos.length, "remanejamento") + " · soma zero" + pendentesTxt() }),
      U.kpi({ rotulo: "Contingência disponível", valor: disponivel == null ? "·" : null, moeda: disponivel == null ? null : disponivel, icone: "shieldCheck",
        cor: ind.contingenciaPct > 50 ? "warning" : "success", rodape: ind.contingenciaPct == null ? "" : F.pct(ind.contingenciaPct) + " consumida por SMs aprovadas",
        esperado: { rotulo: "Previsto", valor: contPrevista == null ? "·" : F.moedaCompacta(contPrevista) } }),
      U.kpi({ rotulo: "SMs a incorporar", valor: F.num(dados.smsPendentes.length), icone: "fileText", cor: dados.smsPendentes.length ? "warning" : "success",
        esperado: { rotulo: "Esperado", valor: "0" },
        rodape: dados.smsPendentes.length ? "aprovadas, ainda fora do orçamento" : "orçamento em dia com as SMs" })
    ].join("");
    document.getElementById("sub-eac").textContent = (vig ? "Rev " + vig.revisao + " de " + F.data(vig.data) : "") +
      " · orçado atual = orçado na revisão + remanejamentos";
    document.getElementById("sub-rem").textContent = vig ? "Rev " + vig.revisao + " · só por SM aprovada (08); só sai saldo ainda não comprometido nem reservado em outra SM" : "";
    renderTabela();
    var anterior = null;
    tRev.atualizar(dados.revisoes.map(function (r) {
      var x = Object.assign({}, r);
      x.variacao = anterior ? r.totalCentavos - anterior.totalCentavos : null;
      x.variacaoPct = anterior && anterior.totalCentavos ? x.variacao / anterior.totalCentavos * 100 : null;
      x.vigente = vig && r.revisao === vig.revisao;
      anterior = r;
      return x;
    }).reverse());
    tRem.atualizar(linhasRemanejamento());
  }

  function pendentesTxt() {
    var p = (dados.remanejamentosPendentes || []).length;
    return p ? " · " + U.plural(p, "em SM aberta", "em SMs abertas") : "";
  }
  function renderTabela() {
    var so = filtro.tipo ? function (x) { return x.nivel === 3 && x.tipoCusto === filtro.tipo; } : null;
    var p = U.projeto(projetoId) || {};
    /* Primeira linha: atividade resumo do projeto (ou do portfólio) com o total da EAC */
    var raiz = Object.assign({}, dados.mapa.total, { descricao: projetoId == null ? "Portfólio de projetos" : p.nome || "Projeto", responsavelId: p.gerenteId });
    arvoreCompleta = GI.fin.arvore(dados.mapa.itens, { busca: filtro.busca, nivel: filtro.nivel, so: so, raiz: raiz });
    tabela.atualizar(rec.aplicar(arvoreCompleta));
  }

  function carregar() {
    return Promise.all([GI.api.financeiro.eac(projetoId), GI.api.financeiro.contingencia(projetoId)]).then(function (r) {
      dados = r[0];
      /* Saldo previsto da contingência pelo avanço físico no corte (mesma referência da tela Contingência) */
      var corte = r[1] && r[1].burn ? r[1].burn.filter(function (b) { return b.real != null; }).slice(-1)[0] : null;
      contPrevista = corte ? corte.esperado : null; contSaldo = r[1] ? r[1].contingencia.saldo : null;
      render();
    });
  }

  /* ---------------- Modais ---------------- */
  function opcoesFolhasComSaldo() {
    return folhas().filter(function (x) { return saldoLivre(x) > 0; }).map(function (x) {
      return { valor: x.codigo, texto: rotuloItem(x) + " · livre " + F.moeda(saldoLivre(x)) };
    });
  }
  function avisoSm(r, texto) {
    GI.ui.toast(texto + " " + r.codigo + " registrada em 08 Governança: o valor muda na EAC só depois da aprovação.", "success", 8000);
    (r.avisos || []).forEach(function (a) { GI.ui.toast(a, "warning", 8000); });
  }
  function opcoesSms() {
    return dados.smsPendentes.map(function (s) { return { valor: s.codigo, texto: s.codigo + " " + s.titulo + " · " + F.moeda(s.impacto.custoCentavos) }; });
  }
  function sm(codigo) { return dados.smsPendentes.filter(function (s) { return s.codigo === codigo; })[0]; }

  function novoItem() {
    if (!dados.mapa.itens.length) { GI.ui.toast("Cadastre a EAC do projeto antes de incluir itens.", "warning"); return; }
    var subpacotes = dados.mapa.itens.filter(function (x) { return x.nivel === 2; });
    GI.form.abrir({
      titulo: "Novo item de custo", subtitulo: "Toda inclusão passa pela gestão de mudanças: SM de remanejamento (o total não muda) ou nova revisão a partir de SM aprovada",
      tamanho: "lg",
      campos: [
        { id: "pai", rotulo: "Subpacote", tipo: "select", obrigatorio: true, opcoes: subpacotes.map(function (x) { return { valor: x.codigo, texto: rotuloItem(x) }; }) },
        { id: "codigo", rotulo: "Código", tipo: "info", html: '<span class="text-muted">Escolha o subpacote</span>' },
        { id: "descricao", rotulo: "Descrição", tipo: "texto", obrigatorio: true, max: 120, largura: "full" },
        { id: "tipoCusto", rotulo: "Tipo de custo", tipo: "select", obrigatorio: true, opcoes: TIPOS },
        { id: "unidade", rotulo: "Unidade", tipo: "select", obrigatorio: true, opcoes: UNIDADES },
        { id: "quantidade", rotulo: "Quantidade", tipo: "numero", obrigatorio: true, min: 0, passo: 0.01 },
        { id: "preco", rotulo: "Preço unitário", tipo: "moeda", obrigatorio: true },
        { id: "valor", rotulo: "Valor orçado", tipo: "info", html: '<b class="num">' + F.moeda(0) + "</b>" },
        { id: "capex", rotulo: "Classificação", tipo: "select", obrigatorio: true, valor: "CAPEX", opcoes: ["CAPEX", "OPEX"] },
        { id: "centroCusto", rotulo: "Centro de custo", tipo: "texto", max: 20, sugestoes: unicos(folhas().map(function (x) { return x.centroCusto; })) },
        { id: "responsavel", rotulo: "Responsável", tipo: "select", obrigatorio: true, opcoes: opcoesPessoas() },
        { id: "recurso", rotulo: "Origem do recurso", tipo: "select", obrigatorio: true, valor: "remanejamento", largura: "full",
          opcoes: [{ valor: "remanejamento", texto: "Remanejamento de outro item por SM (o total não muda; o item nasce na aprovação)" }, { valor: "revisao", texto: "Nova revisão do orçamento (SM aprovada com custo)" }] },
        { id: "origem", rotulo: "Item de origem", tipo: "select", obrigatorio: true, largura: "full", opcoes: opcoesFolhasComSaldo(),
          mostrarSe: function (v) { return v.recurso === "remanejamento"; } },
        { id: "sm", rotulo: "SM aprovada", tipo: "select", obrigatorio: true, largura: "full", opcoes: opcoesSms(),
          ajuda: dados.smsPendentes.length ? "" : "Não há SM aprovada pendente de incorporação.", mostrarSe: function (v) { return v.recurso === "revisao"; } },
        { id: "justificativa", rotulo: "Justificativa", tipo: "textarea", obrigatorio: true, max: 300 }
      ],
      aoMudar: function (v, ctx) {
        ctx.info("codigo", v.pai ? '<b class="num">' + U.esc(GI.api.financeiro.proximoCodigoEac(projetoId, v.pai)) + "</b>" : '<span class="text-muted">Escolha o subpacote</span>');
        ctx.info("valor", '<b class="num">' + F.moeda(valorItem(v)) + "</b>");
      },
      validar: function (v) {
        var e = [], valor = valorItem(v);
        if (!(valor > 0)) e.push({ campo: "preco", msg: "O valor orçado precisa ser maior que zero." });
        if (v.recurso === "remanejamento" && v.origem) {
          var o = porCodigo(v.origem);
          if (o && valor > saldoLivre(o)) e.push({ campo: "origem", msg: "O item de origem só tem " + F.moeda(saldoLivre(o)) + " livres para remanejar." });
        }
        if (v.recurso === "revisao" && v.sm && valor > sm(v.sm).impacto.custoCentavos) {
          e.push({ campo: "sm", msg: "O valor do item supera o custo aprovado na SM (" + F.moeda(sm(v.sm).impacto.custoCentavos) + ")." });
        }
        return e;
      },
      aoSalvar: function (v) {
        var item = { codigo: GI.api.financeiro.proximoCodigoEac(projetoId, v.pai), descricao: v.descricao, tipoCusto: v.tipoCusto, unidade: v.unidade,
          quantidade: v.quantidade, precoUnitario: v.preco, capex: v.capex === "CAPEX", centroCusto: v.centroCusto, responsavelId: Number(v.responsavel), base: valorItem(v) };
        return GI.api.financeiro.novoItemEac(projetoId, item, { tipo: v.recurso, origem: v.origem, smRef: v.sm, justificativa: v.justificativa }).then(function (r) {
          if (v.recurso === "revisao") GI.ui.toast("Item " + item.codigo + " incluído na Rev " + r.revisao + ".", "success");
          else avisoSm(r, "Item " + item.codigo + " proposto na SM");
          return carregar();
        });
      }
    });
  }
  function valorItem(v) { return v.quantidade > 0 && v.preco > 0 ? Math.round(v.quantidade * v.preco) : 0; }
  function unicos(l) { return l.filter(function (x, i) { return x && l.indexOf(x) === i; }); }

  function editarItem(codigo) {
    var x = porCodigo(codigo);
    GI.form.abrir({
      titulo: "Editar item " + x.codigo, subtitulo: x.descricao, tamanho: "lg",
      intro: '<div class="alert">' + U.icone("info") + '<div class="alert__body">Orçado atual ' + F.moeda(x.atual) +
        " (" + F.num(x.quantidade, 2) + " " + U.esc(x.unidade) + " x " + F.moeda(x.precoUnitario) + "). O valor só muda por SM (08): Remanejar ou Nova revisão.</div></div>" +
        '<p class="text-small text-muted">Dados cadastrais não mudam valor: dispensam SM, mas exigem justificativa e ficam no histórico do item.</p>' +
        (x.historicoCadastro && x.historicoCadastro.length ? '<ul class="text-small text-muted">' + x.historicoCadastro.slice(-3).reverse().map(function (h) {
          return "<li>" + U.esc(F.data(h.data) + " · " + U.pessoa(h.porId) + " · " + h.campos.join(", ") + ": " + h.justificativa) + "</li>"; }).join("") + "</ul>" : ""),
      campos: [
        { id: "descricao", rotulo: "Descrição", tipo: "texto", obrigatorio: true, max: 120, largura: "full", valor: x.descricao },
        { id: "tipoCusto", rotulo: "Tipo de custo", tipo: "select", obrigatorio: true, opcoes: TIPOS, valor: x.tipoCusto },
        { id: "capex", rotulo: "Classificação", tipo: "select", obrigatorio: true, opcoes: ["CAPEX", "OPEX"], valor: x.capex ? "CAPEX" : "OPEX" },
        { id: "centroCusto", rotulo: "Centro de custo", tipo: "texto", max: 20, valor: x.centroCusto },
        { id: "responsavel", rotulo: "Responsável", tipo: "select", obrigatorio: true, opcoes: opcoesPessoas(), valor: x.responsavelId },
        { id: "justificativa", rotulo: "Justificativa da alteração", tipo: "textarea", obrigatorio: true, max: 300, largura: "full" }
      ],
      aoSalvar: function (v) {
        return GI.api.financeiro.editarItem(projetoId, x.codigo, { descricao: v.descricao, tipoCusto: v.tipoCusto, capex: v.capex === "CAPEX", centroCusto: v.centroCusto,
          responsavelId: Number(v.responsavel), justificativa: v.justificativa }).then(function (r) {
          GI.ui.toast(r.alterados ? "Item " + x.codigo + " atualizado; alteração registrada no histórico." : "Nenhum dado alterado.", r.alterados ? "success" : "info"); return carregar(); });
      }
    });
  }

  function remanejar() {
    if (!folhas().length) return;
    GI.form.abrir({
      titulo: "Solicitar remanejamento entre itens", subtitulo: (dados.vigente ? "Rev " + dados.vigente.revisao + " · " : "") + "gera SM em 08 Governança; o total do orçamento não muda",
      textoSalvar: "Registrar SM",
      intro: '<div class="alert alert--info">' + U.icone("info") + '<div class="alert__body">Remanejamento é mudança na linha de base de custo: segue o fluxo da SM (análise de impacto e decisão na alçada). ' +
        "A transferência é aplicada na EAC só quando a SM for aprovada; até lá, o valor fica reservado na origem.</div></div>",
      campos: [
        { id: "origem", rotulo: "Origem", tipo: "select", obrigatorio: true, largura: "full", opcoes: opcoesFolhasComSaldo() },
        { id: "destino", rotulo: "Destino", tipo: "select", obrigatorio: true, largura: "full", opcoes: folhas().map(function (x) { return { valor: x.codigo, texto: rotuloItem(x) }; }) },
        { id: "valor", rotulo: "Valor", tipo: "moeda", obrigatorio: true },
        { id: "saldo", rotulo: "Saldo livre na origem", tipo: "info", html: '<span class="text-muted">Escolha a origem</span>' },
        { id: "prioridade", rotulo: "Prioridade", tipo: "select", obrigatorio: true, valor: "Normal", opcoes: ["Normal", "Urgente"] },
        { id: "justificativa", rotulo: "Justificativa", tipo: "textarea", obrigatorio: true, max: 1000,
          ajuda: "Por que a origem não precisa do valor e por que o destino precisa (mínimo de 20 caracteres)." }
      ],
      aoMudar: function (v, ctx) {
        var o = v.origem && porCodigo(v.origem);
        ctx.info("saldo", o ? '<b class="num">' + F.moeda(saldoLivre(o)) + '</b> <span class="text-small text-muted">a comprometer ' + F.moeda(saldo(o)) + "</span>" : '<span class="text-muted">Escolha a origem</span>');
      },
      aoSalvar: function (v) {
        return GI.api.financeiro.remanejar(projetoId, { origem: v.origem, destino: v.destino, valorCentavos: v.valor, justificativa: v.justificativa, prioridade: v.prioridade }).then(function (r) {
          avisoSm(r, "Remanejamento de " + F.moeda(v.valor) + " proposto na SM");
          return carregar();
        });
      }
    });
  }

  function semSmPendente() {
    GI.modal.create({
      title: "Nova revisão do orçamento", size: "sm",
      body: '<p>Não há SM aprovada pendente de incorporação ao orçamento.</p><p class="text-small text-muted">O total do orçamento só muda por revisão, a partir de uma Solicitação de Mudança aprovada em 08 Governança.</p>',
      buttons: [{ label: "Fechar", variant: "secondary" },
        { label: "Abrir Gestão de mudanças", variant: "primary", onClick: function () { window.location.href = U.tela("governanca", "mudancas"); } }]
    });
  }

  function novaRevisao() {
    if (!dados.smsPendentes.length) { semSmPendente(); return; }
    var vig = dados.vigente;
    GI.form.abrir({
      titulo: "Nova revisão do orçamento", subtitulo: "Rev " + (vig ? vig.revisao + 1 : 0) + " · a partir de SM aprovada", tamanho: "lg",
      intro: '<p class="text-small text-muted">A revisão consolida os remanejamentos da Rev ' + (vig ? vig.revisao : 0) +
        " na base, incorpora o custo aprovado na SM e reescala a linha de base da Curva S financeira.</p>",
      campos: [
        { id: "sm", rotulo: "SM aprovada", tipo: "select", obrigatorio: true, largura: "full", opcoes: opcoesSms() },
        { id: "item", rotulo: "Item que recebe o valor", tipo: "select", obrigatorio: true, largura: "full", opcoes: folhas().map(function (x) { return { valor: x.codigo, texto: rotuloItem(x) }; }) },
        { id: "valor", rotulo: "Valor incorporado", tipo: "moeda", obrigatorio: true, ajuda: "Até o custo aprovado na SM." },
        { id: "total", rotulo: "Total do orçamento", tipo: "info", html: "" },
        { id: "justificativa", rotulo: "Justificativa", tipo: "textarea", obrigatorio: true, max: 300 }
      ],
      aoMudar: function (v, ctx) {
        var novo = dados.mapa.total.atual + (v.valor > 0 ? v.valor : 0);
        ctx.info("total", '<span class="num">' + F.moeda(dados.mapa.total.atual) + " > <b>" + F.moeda(novo) + "</b></span>");
      },
      validar: function (v) {
        var s = sm(v.sm);
        if (s && v.valor > s.impacto.custoCentavos) return [{ campo: "valor", msg: "O valor supera o custo aprovado na SM (" + F.moeda(s.impacto.custoCentavos) + ")." }];
        if (!(v.valor > 0)) return [{ campo: "valor", msg: "Informe um valor maior que zero." }];
        return [];
      },
      aoSalvar: function (v) {
        return GI.api.financeiro.novaRevisao(projetoId, { smRef: v.sm, justificativa: v.justificativa, ajustes: [{ codigo: v.item, deltaCentavos: v.valor }] }).then(function (r) {
          GI.ui.toast("Rev " + r.revisao + " criada: orçamento de " + F.moeda(r.totalCentavos) + ".", "success");
          return carregar();
        });
      }
    });
    /* Sugestão: SM e item mais prováveis */
    var campoSm = document.querySelector(".modal [data-campo='sm'] select");
    if (campoSm && dados.smsPendentes.length === 1) {
      campoSm.value = dados.smsPendentes[0].codigo;
      var s = dados.smsPendentes[0];
      var just = document.querySelector(".modal [data-campo='justificativa'] textarea");
      var val = document.querySelector(".modal [data-campo='valor'] input");
      if (just) just.value = s.titulo + " (" + s.codigo + ").";
      if (val) val.value = GI.form.deCentavos(s.impacto.custoCentavos);
      campoSm.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }

  function importar() {
    if (!dados.mapa.itens.length) { GI.ui.toast("Cadastre a EAC do projeto antes de importar itens.", "warning"); return; }
    if (!dados.smsPendentes.length) { semSmPendente(); return; }
    GI.form.abrir({
      titulo: "Importar itens para nova revisão", subtitulo: "Rev " + (dados.vigente ? dados.vigente.revisao + 1 : 0), textoSalvar: "Continuar",
      intro: '<p class="text-small text-muted">Itens novos mudam o total do orçamento; por isso a importação gera uma nova revisão. Informe a SM que aprovou o acréscimo.</p>',
      campos: [
        { id: "sm", rotulo: "SM aprovada", tipo: "select", obrigatorio: true, largura: "full", opcoes: opcoesSms() },
        { id: "justificativa", rotulo: "Justificativa da revisão", tipo: "textarea", obrigatorio: true, max: 300 }
      ],
      aoSalvar: function (v) { setTimeout(function () { abrirImportacao(v); }, 0); }
    });
  }
  function abrirImportacao(rev) {
    var existentes = dados.mapa.itens.map(function (x) { return x.codigo; });
    var nomesPes = Object.keys(U.mapas.pessoas).map(function (k) { return U.mapas.pessoas[k].nome; });
    GI.importar.abrir({
      titulo: "Importar itens da EAC", subtitulo: "Itens de custo (nível 3) em subpacotes existentes", arquivoModelo: "modelo-eac",
      colunas: [
        { campo: "codigo", titulo: "Código", tipo: "texto", obrigatorio: true, exemplo: "3.2.5" },
        { campo: "descricao", titulo: "Descrição", tipo: "texto", obrigatorio: true, exemplo: "Isolamento térmico" },
        { campo: "tipoCusto", titulo: "Tipo de custo", tipo: "lista", obrigatorio: true, opcoes: TIPOS, exemplo: "Serviço" },
        { campo: "unidade", titulo: "Unidade", tipo: "lista", obrigatorio: true, opcoes: UNIDADES, exemplo: "m²" },
        { campo: "quantidade", titulo: "Quantidade", tipo: "num", obrigatorio: true, exemplo: "1200" },
        { campo: "preco", titulo: "Preço unitário (R$)", tipo: "moeda", obrigatorio: true, exemplo: "85,00" },
        { campo: "classificacao", titulo: "CAPEX/OPEX", tipo: "lista", obrigatorio: true, opcoes: ["CAPEX", "OPEX"], exemplo: "CAPEX" },
        { campo: "centroCusto", titulo: "Centro de custo", tipo: "texto", exemplo: "CC-4501-05" },
        { campo: "responsavel", titulo: "Responsável", tipo: "lista", obrigatorio: true, opcoes: nomesPes, exemplo: "Carlos Nunes" }
      ],
      validarLinha: function (l) {
        var e = [];
        if (l.codigo && !/^\d+\.\d+\.\d+$/.test(l.codigo)) e.push("Código deve ter 3 níveis (ex.: 3.2.5).");
        else if (l.codigo && existentes.indexOf(l.codigo.split(".").slice(0, 2).join(".")) < 0) e.push("Subpacote " + l.codigo.split(".").slice(0, 2).join(".") + " não existe.");
        else if (l.codigo && existentes.indexOf(l.codigo) >= 0) e.push("Código " + l.codigo + " já existe.");
        if (l.quantidade != null && !(l.quantidade > 0)) e.push("Quantidade deve ser maior que zero.");
        return e;
      },
      aoImportar: function (linhas) {
        var novos = linhas.map(function (l) {
          var pes = Object.keys(U.mapas.pessoas).filter(function (k) { return U.mapas.pessoas[k].nome === l.responsavel; })[0];
          return { codigo: l.codigo, descricao: l.descricao, tipoCusto: l.tipoCusto, unidade: l.unidade, quantidade: l.quantidade, precoUnitario: l.preco,
            capex: l.classificacao === "CAPEX", centroCusto: l.centroCusto || "", responsavelId: Number(pes), base: Math.round(l.quantidade * l.preco) };
        });
        var acrescimo = novos.reduce(function (s, n) { return s + n.base; }, 0);
        return GI.api.financeiro.novaRevisao(projetoId, { smRef: rev.sm || null, justificativa: rev.justificativa, novos: novos }).then(function (r) {
          carregar();
          return "Rev " + r.revisao + " criada com " + U.plural(novos.length, "item novo", "itens novos") + " (+" + F.moeda(acrescimo) + ").";
        });
      }
    });
  }

  /* ---------------- Exportação ---------------- */
  GI.exportar.registrar(function () {
    var p = U.projeto(projetoId);
    /* exporta a estrutura inteira, mesmo com linhas recolhidas na tela */
    tabela.atualizar(arvoreCompleta);
    var dadosEac = tabela.exportacao();
    renderTabela();
    return {
      titulo: projetoId == null ? "EAC da carteira: projetos e pacotes principais" : "EAC: estrutura analítica de custos", subtitulo: p ? p.codigo + " " + p.nome : "Portfólio de projetos",
      arquivo: "eac-" + (p ? p.codigo : "portfolio"), orientacao: "l",
      blocos: [
        { tipo: "kpis", titulo: "Resumo", itens: Array.prototype.map.call(document.querySelectorAll("#kpis .kpi"), function (k) {
            return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" };
          }) },
        { tipo: "tabela", titulo: "Estrutura analítica de custos", dados: dadosEac },
        { tipo: "tabela", titulo: "Revisões do orçamento", dados: tRev.exportacao() },
        { tipo: "tabela", titulo: "Remanejamentos da revisão vigente", dados: tRem.exportacao() }
      ]
    };
  });

  /* ---------------- Início ---------------- */
  GI.util.pronto().then(function () {
    rec = GI.fin.recolhimento("tabela", renderTabela);
    projetoId = GI.fin.projeto(function (id) { projetoId = id; rec.limpar(); carregar(); });
    var PF = projetoId == null;
    if (PF) {
      filtro.nivel = 2;
      document.getElementById("f-nivel").innerHTML = '<option value="1">Mostrar projetos</option><option value="2" selected>Mostrar pacotes principais</option>';
      document.getElementById("f-tipo").hidden = true;
      document.getElementById("t-eac").textContent = "Estrutura analítica de custos da carteira";
      document.getElementById("t-rev").textContent = "Revisão vigente do orçamento por projeto";
      document.getElementById("t-rem").textContent = "Remanejamentos das revisões vigentes";
    }
    function noProjeto(acao, titulo, fn) { return function () { if (PF) U.noProjeto(acao, titulo); else fn(); }; }
    var ACOES = { novo: novoItem, importar: importar, remanejar: remanejar, revisao: novaRevisao };
    document.getElementById("f-tipo").innerHTML = U.opcoes(TIPOS, "", "Todos os tipos de custo");
    document.getElementById("busca").addEventListener("input", U.debounce(function (ev) { filtro.busca = ev.target.value.trim(); rec.limpar(); renderTabela(); }, 200));
    document.getElementById("f-nivel").addEventListener("change", function (ev) { filtro.nivel = Number(ev.target.value); rec.limpar(); renderTabela(); });
    document.getElementById("f-tipo").addEventListener("change", function (ev) { filtro.tipo = ev.target.value; rec.limpar(); renderTabela(); });
    document.getElementById("btn-novo").addEventListener("click", noProjeto("novo", "Novo item de custo", novoItem));
    document.getElementById("btn-importar").addEventListener("click", noProjeto("importar", "Importar itens da EAC", importar));
    document.getElementById("btn-remanejar").addEventListener("click", noProjeto("remanejar", "Remanejar entre itens", remanejar));
    document.getElementById("btn-revisao").addEventListener("click", noProjeto("revisao", "Nova revisão do orçamento", novaRevisao));
    document.getElementById("btn-colunas").addEventListener("click", function () { GI.tabela.escolherColunas(tabela); });

    tabela = GI.tabela.criar("tabela", {
      porPagina: 0, pilha: false, legenda: "Estrutura analítica de custos", vazio: "Nenhum item encontrado.", celulaVazia: "",
      colunas: [
        { id: "codigo", titulo: "Código", ordenavel: false, fixa: true, classe: "nowrap",
          html: function (x) { return rec.botao(x) + U.esc(x.codigo); } },
        { id: "descricao", titulo: "Descrição", ordenavel: false, fixa: true,
          html: function (x) { return x.nivel < 3 ? "<b>" + U.esc(x.descricao) + "</b>" : U.esc(x.descricao); } },
        { id: "tipoCusto", titulo: "Tipo de custo", ordenavel: false },
        { id: "unidade", titulo: "Un.", ordenavel: false },
        { id: "quantidade", titulo: "Qtd.", tipo: "num", ordenavel: false },
        { id: "precoUnitario", titulo: "Preço unitário", tipo: "moeda", ordenavel: false },
        { id: "base", titulo: "Orçado na revisão", tipo: "moeda", ordenavel: false, oculta: true },
        { id: "remanejamento", titulo: "Remanejado", tipo: "moeda", ordenavel: false, oculta: true,
          html: function (x) { return x.remanejamento ? (x.remanejamento > 0 ? "+" : "") + U.esc(F.moeda(x.remanejamento)) : ""; } },
        { id: "atual", titulo: "Orçado atual", tipo: "moeda", ordenavel: false, html: function (x) { return "<b>" + U.esc(F.moeda(x.atual)) + "</b>"; } },
        { id: "capex", titulo: "CAPEX/OPEX", ordenavel: false, oculta: true, valor: function (x) { return x.nivel === 3 ? (x.capex ? "CAPEX" : "OPEX") : ""; } },
        { id: "centroCusto", titulo: "Centro de custo", ordenavel: false, oculta: true },
        { id: "responsavel", titulo: "Responsável", ordenavel: false, valor: function (x) { return x.responsavelId ? U.pessoa(x.responsavelId) : ""; } }
      ].concat(PF ? [{ id: "peso", titulo: "Peso na carteira", tipo: "pct", casas: 1, ordenavel: false, valor: function (x) { return x.nivel === 1 ? x.peso : null; } }] : []),
      classeLinha: GI.fin.classeNivel,
      acoes: function (x) {
        if (PF && x.nivel === 1 && x.projetoId) return '<a class="btn btn--ghost btn--sm" href="' + U.tela("financeiro", "eac", { projeto: x.projetoId }) + '">' + U.icone("chevronRight") + "Abrir</a>";
        return x.nivel === 3 ? '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-editar="' + U.esc(x.codigo) + '" aria-label="Editar item ' + U.esc(x.codigo) + '" title="Editar">' + U.icone("edit") + "</button>" : "";
      },
      rodape: function (visiveis) {
        /* Sem filtro, o total do projeto já está na linha resumo (código 0) */
        var filtrado = filtro.busca || filtro.tipo;
        if (!filtrado) return null;
        var linhas = (arvoreCompleta.length ? arvoreCompleta : visiveis).filter(function (x) { return !x.raiz; }); /* total não muda ao recolher */
        var f = linhas.filter(function (x) { return x.nivel === 3; });
        var base = f.length ? f : linhas.filter(function (x) { return x.nivel === Math.min.apply(null, linhas.map(function (y) { return y.nivel; })); });
        var total = base.reduce(function (s, x) { return s + x.atual; }, 0);
        return { codigo: "Total filtrado", atual: "<b>" + U.esc(F.moeda(total)) + "</b>" };
      }
    });
    document.getElementById("tabela").addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-editar]");
      if (b) editarItem(b.getAttribute("data-editar"));
    });

    tRev = GI.tabela.criar("revisoes", {
      porPagina: 0, legenda: "Revisões do orçamento", ordem: null,
      colunas: (PF ? [U.colunaProjeto()] : []).concat([
        { id: "revisao", titulo: "Revisão", valor: function (r) { return "Rev " + r.revisao; },
          html: function (r) { return "<b>Rev " + r.revisao + "</b>" + (r.revisao === 0 ? " " + U.badge("Linha de base", "info") : "") + (r.vigente ? " " + U.badge("Vigente", "success") : ""); } },
        { id: "data", titulo: "Data", tipo: "data" },
        { id: "totalCentavos", titulo: "Total", tipo: "moeda" },
        { id: "variacao", titulo: "Variação", tipo: "moeda",
          html: function (r) { return r.variacao == null ? "" : (r.variacao > 0 ? "+" : "") + U.esc(F.moeda(r.variacao)) + ' <span class="text-muted">(' + (r.variacaoPct > 0 ? "+" : "") + F.num(r.variacaoPct, 1) + "%)</span>"; } },
        { id: "smRef", titulo: "SM", html: function (r) { return r.smRef ? '<a href="' + U.tela("governanca", "mudanca", { codigo: r.smRef }) + '">' + U.esc(r.smRef) + "</a>" : ""; } },
        { id: "justificativa", titulo: "Justificativa" },
        { id: "aprovado", titulo: "Aprovado por", valor: function (r) { return U.pessoa(r.aprovadoPorId); } }
      ]),
      classeLinha: function (r) { return r.vigente && !PF ? "is-selected" : ""; }
    });
    tRem = GI.tabela.criar("remanejamentos", {
      porPagina: 0, legenda: "Remanejamentos da revisão vigente", vazio: "Nenhum remanejamento nesta revisão nem em SM aberta.",
      colunas: (PF ? [U.colunaProjeto()] : []).concat([
        { id: "data", titulo: "Data", tipo: "data" },
        { id: "origem", titulo: "Origem", valor: function (r) { var x = PF ? null : porCodigo(r.origem); return x ? rotuloItem(x) : r.origem; } },
        { id: "destino", titulo: "Destino", valor: function (r) { var x = PF ? null : porCodigo(r.destino); return x ? rotuloItem(x) : r.destino; } },
        { id: "valorCentavos", titulo: "Valor", tipo: "moeda" },
        { id: "smRef", titulo: "SM", classe: "nowrap", valor: function (r) { return r.smRef || ""; },
          html: function (r) { return r.smRef ? '<a href="' + U.tela("governanca", "mudanca", { codigo: r.smRef }) + '">' + U.esc(r.smRef) + "</a>" : '<span class="text-muted">sem SM</span>'; } },
        { id: "situacao", titulo: "Situação", valor: function (r) { return r.pendente ? r.situacaoSm : "Aplicado"; },
          html: function (r) { return r.pendente ? U.badge(r.situacaoSm, "warning", true) + '<br><small class="text-muted">aplica na aprovação</small>' : U.badge("Aplicado", "success", true); } },
        { id: "justificativa", titulo: "Justificativa", oculta: true },
        { id: "por", titulo: "Registrado por", valor: function (r) { return U.pessoa(r.porId); } }
      ]),
      classeLinha: function (r) { return r.pendente ? "is-alert" : ""; }
    });
    return carregar().then(function () { var a = U.acaoPendente(); if (a && !PF && ACOES[a]) ACOES[a](); });
  });
})(window.GI = window.GI || {});
