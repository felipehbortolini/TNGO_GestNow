/* ==========================================================================
   Planejamento > EAP (Estrutura Analítica do Projeto, avanço físico)
   Árvore área > subárea > pacote, com peso (% do projeto), datas da linha de
   base, critério de medição e avanço previsto x real. Espelha a EAC (03):
   Rev 0 = linha de base; estrutura e pesos só mudam por nova revisão, a partir
   de SM aprovada com impacto em escopo. Pacote de planejamento é desdobrado em
   pacotes de trabalho sem mudar o total (planejamento em ondas sucessivas).
   Árvore e recolhimento reaproveitam GI.fin (js/pages/financeiro/financeiro.js).
   Portfólio: linha 0 = portfólio, nível 1 = projeto (peso na carteira) e nível 2 =
   pacotes principais de cada projeto (áreas); só leitura, os cadastros pedem o
   projeto e abrem a EAP dele.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt, R = GI.regras, API = GI.api.planejamento;
  var UNIDADES = ["m", "m²", "m³", "t", "kg", "un", "vb"];
  var projetoId, dados = null, tabela, tRev, tDes, eacFolhas = [];
  var filtro = { busca: "", nivel: 3, criterio: "", situacao: "" };
  var rec, arvoreCompleta = [];

  function folhas() { return dados.arvore.itens.filter(function (x) { return x.nivel === 3; }); }
  function porCodigo(c) { return dados.arvore.itens.filter(function (x) { return x.codigo === c; })[0]; }
  function rotulo(x) { return x.codigo + " " + x.descricao; }
  function modelos() { return (dados && dados.parametros.modelosEtapas) || []; }
  function modelo(id) { return modelos().filter(function (m) { return m.id === id; })[0]; }
  function par() { return dados.parametros; }
  function opcoesPessoas() { return Object.keys(U.mapas.pessoas).map(function (k) { return { valor: k, texto: U.mapas.pessoas[k].nome }; }); }
  function opcoesEmpresas() { return Object.keys(U.mapas.empresas).map(function (k) { return { valor: k, texto: U.mapas.empresas[k].nome }; }); }
  function opcoesEac() { return eacFolhas.map(function (x) { return { valor: x.codigo, texto: x.codigo + " " + x.descricao }; }); }
  function peso(v) { return v == null ? "" : F.num(v, 2) + "%"; }
  function pp(v) { return v == null ? "" : (v > 0 ? "+" : "") + F.num(v, 1); }
  function classeDesvio(faixa) { return faixa === "danger" ? "valor--negativo" : faixa === "warning" ? "valor--atencao" : ""; }
  function planejamentos() { return folhas().filter(function (x) { return !x.trabalho && x.peso > 0; }); }

  /* Descrição curta do critério (tabela e ficha) */
  function textoCriterio(x) {
    if (x.nivel !== 3) return "";
    if (!x.trabalho) return "Sem medição";
    if (x.criterio === "Etapas") return "Etapas";
    if (x.criterio === "Unidades") return "Unidades (" + x.unidade + ")";
    return x.criterio || "";
  }
  function barra(v) {
    var n = Math.max(0, Math.min(100, v || 0));
    return '<div class="progress-row"><div class="progress progress--sm" role="progressbar" aria-valuenow="' + n + '" aria-valuemin="0" aria-valuemax="100" aria-label="Real">' +
      '<span class="progress__bar" style="--value: ' + n + '%"></span></div><span class="num">' + F.pct(v, 1) + "</span></div>";
  }

  /* ---------------- Render ---------------- */
  function render() {
    var a = dados.arvore, ind = dados.indicadores, vig = dados.vigente;
    if (dados.portfolio) { renderPortfolio(); return; }
    if (!a.itens.length) {
      document.getElementById("kpis").innerHTML = "";
      document.getElementById("sub-eap").textContent = "Este projeto ainda não tem EAP cadastrada.";
      document.getElementById("sub-des").textContent = "";
      tabela.atualizar([]); tRev.atualizar([]); tDes.atualizar([]);
      return;
    }
    var c = dados.curva, fx = par().faixasDesvioPP;
    var concilia = c && Math.abs(c.diferencaPP) < 0.05;
    document.getElementById("kpis").innerHTML = [
      U.kpi({ rotulo: "Avanço físico real", valor: F.num(ind.real, 1), unidade: "%", icone: "trendingUp", cor: a.total.faixa || "primary",
        esperado: { rotulo: "Previsto", valor: F.pct(ind.previsto, 1) }, rodape: "desvio " + pp(ind.desvioPP) + " p.p." }),
      U.kpi({ rotulo: "Curva S no corte", valor: c ? F.num(c.real, 1) : "·", unidade: c ? "%" : "", icone: "curve", cor: !c ? "info" : concilia ? "success" : "warning",
        esperado: { rotulo: "Linha de base", valor: c ? F.pct(c.previsto, 1) : "·" }, rodape: !c ? "projeto sem Curva S" : concilia ? "fecha com a EAP em " + U.mesCurto(c.corte) : "diferença de " + pp(c.diferencaPP) + " p.p. em " + U.mesCurto(c.corte),
        href: U.tela("planejamento", "curva-s", { projeto: projetoId }) }),
      U.kpi({ rotulo: "Pacotes de trabalho", valor: F.num(ind.pacotes), icone: "listTree", cor: "info",
        esperado: { rotulo: "Linha de base", valor: vig && vig.pacotes != null ? F.num(vig.pacotes) : "·" },
        rodape: U.plural(ind.areas, "área") + " · " + U.plural(ind.subareas, "subárea") + (ind.planejamento ? " · " + U.plural(ind.planejamento, "de planejamento", "de planejamento") + " (" + peso(ind.pesoPlanejamento) + ")" : "") }),
      U.kpi({ rotulo: "Término vencido", valor: F.num(ind.vencidos), icone: "flag", cor: ind.vencidos ? "danger" : "success", esperado: { rotulo: "Esperado", valor: F.num(0) },
        rodape: U.plural(ind.atrasados, "pacote", "pacotes") + " com desvio abaixo de −" + F.num(fx[1]) + " p.p." }),
      U.kpi({ rotulo: "SMs a incorporar", valor: F.num(dados.smsPendentes.length), icone: "fileText", cor: dados.smsPendentes.length ? "warning" : "success", esperado: { rotulo: "Esperado", valor: F.num(0) },
        rodape: dados.smsPendentes.length ? "aprovadas com impacto em escopo, fora da EAP" : "EAP em dia com as SMs" })
    ].join("");
    document.getElementById("sub-eap").textContent = (vig ? "Rev " + vig.revisao + " de " + F.data(vig.data) + " · " : "") +
      "avanço na data de referência " + F.data(dados.referencia) + "; pesos em % do projeto; faixas de desvio −" + F.num(fx[0]) + " e −" + F.num(fx[1]) + " p.p.";
    document.getElementById("sub-des").textContent = vig ? "Rev " + vig.revisao + " · o peso sai do pacote de planejamento para o pacote de trabalho; o total não muda" : "";
    renderTabela();
    tRev.atualizar(dados.revisoes.map(function (r) { var x = Object.assign({}, r); x.vigente = vig && r.revisao === vig.revisao; return x; }).reverse());
    tDes.atualizar(dados.desdobramentos.slice().reverse());
  }

  /* Portfólio: KPIs da carteira, revisão vigente de cada projeto, sem desdobramentos */
  function renderPortfolio() {
    var a = dados.arvore, ind = dados.indicadores, c = dados.curva, fx = par().faixasDesvioPP;
    var concilia = c && Math.abs(c.diferencaPP) < 0.05;
    document.getElementById("kpis").innerHTML = [
      U.kpi({ rotulo: "Avanço físico ponderado", valor: F.num(ind.real, 1), unidade: "%", icone: "trendingUp", cor: a.total.faixa || "primary",
        esperado: { rotulo: "Previsto", valor: F.pct(ind.previsto, 1) }, rodape: "desvio " + pp(ind.desvioPP) + " p.p." }),
      U.kpi({ rotulo: "Curva S da carteira no corte", valor: c ? F.num(c.real, 1) : "·", unidade: c ? "%" : "", icone: "curve", cor: !c ? "info" : concilia ? "success" : "warning",
        esperado: { rotulo: "Linha de base", valor: c ? F.pct(c.previsto, 1) : "·" }, rodape: !c ? "carteira sem Curva S" : concilia ? "fecha com a EAP em " + U.mesCurto(c.corte) : "diferença de " + pp(c.diferencaPP) + " p.p. em " + U.mesCurto(c.corte),
        href: U.tela("planejamento", "curva-s") }),
      U.kpi({ rotulo: "Pacotes de trabalho", valor: F.num(ind.pacotes), icone: "listTree", cor: "info",
        esperado: { rotulo: "Linha de base", valor: F.num(dados.revisoes.reduce(function (t, r) { return t + (r.pacotes || 0); }, 0)) },
        rodape: U.plural(ind.projetos, "projeto") + " · " + U.plural(ind.areas, "pacote principal", "pacotes principais") }),
      U.kpi({ rotulo: "Término vencido", valor: F.num(ind.vencidos), icone: "flag", cor: ind.vencidos ? "danger" : "success", esperado: { rotulo: "Esperado", valor: F.num(0) },
        rodape: U.plural(ind.atrasados, "pacote", "pacotes") + " com desvio abaixo de −" + F.num(fx[1]) + " p.p." }),
      U.kpi({ rotulo: "SMs a incorporar", valor: F.num(dados.smsPendentes.length), icone: "fileText", cor: dados.smsPendentes.length ? "warning" : "success", esperado: { rotulo: "Esperado", valor: F.num(0) },
        rodape: dados.smsPendentes.length ? dados.smsPendentes.map(function (sm) { return sm.projetoCodigo; }).filter(function (x, k, l) { return l.indexOf(x) === k; }).join(", ") : "EAP em dia com as SMs" })
    ].join("");
    document.getElementById("sub-eap").textContent = "Portfólio: projeto (peso na carteira) e pacotes principais (peso na carteira e no projeto); avanço na data de referência " + F.data(dados.referencia) + "; faixas de desvio −" + F.num(fx[0]) + " e −" + F.num(fx[1]) + " p.p.";
    renderTabela();
    tRev.atualizar(dados.revisoes.map(function (r) { return Object.assign({}, r, { vigente: true }); }));
    tDes.atualizar([]);
  }

  function passaFiltro(x) {
    if (x.nivel !== 3) return false;
    if (filtro.criterio && (filtro.criterio === "Planejamento" ? x.trabalho : x.criterio !== filtro.criterio)) return false;
    if (filtro.situacao === "atrasado" && !(x.trabalho && x.faixa === "danger")) return false;
    if (filtro.situacao === "vencido" && !x.vencido) return false;
    if (filtro.situacao === "planejamento" && x.trabalho) return false;
    return true;
  }
  /* Primeira linha: atividade resumo do projeto (peso 100%, avanço consolidado, datas extremas) */
  function raizEap() {
    if (dados.portfolio) {
      var ps = dados.arvore.itens.filter(function (x) { return x.nivel === 1; });
      return Object.assign({}, dados.arvore.total, { descricao: "Portfólio de projetos", inicio: ps.map(function (x) { return x.inicio; }).filter(Boolean).sort()[0],
        termino: ps.map(function (x) { return x.termino; }).filter(Boolean).sort().pop(), responsavelId: null });
    }
    var p = U.projeto(projetoId) || {}, t = dados.arvore.total, areas = dados.arvore.itens.filter(function (x) { return x.nivel === 1; });
    var ini = areas.map(function (x) { return x.inicio; }).filter(Boolean).sort()[0] || p.inicio;
    var fim = areas.map(function (x) { return x.termino; }).filter(Boolean).sort().pop() || p.terminoPrevisto;
    return Object.assign({}, t, { descricao: p.nome || "Projeto", inicio: ini, termino: fim, responsavelId: p.gerenteId });
  }
  function renderTabela() {
    var so = filtro.criterio || filtro.situacao ? passaFiltro : null;
    arvoreCompleta = GI.fin.arvore(dados.arvore.itens, { busca: filtro.busca, nivel: filtro.nivel, so: so, raiz: raizEap() });
    tabela.atualizar(rec.aplicar(arvoreCompleta));
  }

  function carregar() {
    return Promise.all([API.eap(projetoId), projetoId == null ? Promise.resolve({ itens: [] }) : GI.api.financeiro.mapaControle(projetoId)]).then(function (r) {
      dados = r[0];
      eacFolhas = r[1].itens.filter(function (x) { return x.nivel === 3; });
      render();
    });
  }

  /* ---------------- Registrar avanço ---------------- */
  function camposCriterio(x) {
    switch (x.criterio) {
      case "Etapas":
        return x.etapas.map(function (e, k) {
          return { id: "etapa" + k, rotulo: e.nome + " (peso " + F.num(e.peso) + ")", tipo: "numero", obrigatorio: true, min: 0, maxNumero: 100, passo: 1, valor: e.pct, ajuda: "% concluído da etapa" };
        });
      case "Unidades":
        return [{ id: "executado", rotulo: "Executado acumulado (" + x.unidade + ")", tipo: "numero", obrigatorio: true, min: 0, maxNumero: x.quantidade, passo: 0.01, valor: x.executado,
          ajuda: "Quantidade da linha de base: " + F.num(x.quantidade, 2).replace(/,00$/, "") + " " + x.unidade }];
      case "Marco 0/100":
        return [{ id: "estado", rotulo: "Situação do marco", tipo: "escolha", obrigatorio: true, valor: x.estado, largura: "full",
          opcoes: [{ valor: "Não iniciado", texto: "Não iniciado", sub: "0%" }, { valor: "Concluído", texto: "Concluído", sub: "100%" }] }];
      case "Marco 50/50":
        return [{ id: "estado", rotulo: "Situação do marco", tipo: "escolha", obrigatorio: true, valor: x.estado, largura: "full",
          opcoes: [{ valor: "Não iniciado", texto: "Não iniciado", sub: "0%" }, { valor: "Iniciado", texto: "Iniciado", sub: "50%" }, { valor: "Concluído", texto: "Concluído", sub: "100%" }] }];
      case "Percentual estimado":
        return [{ id: "estimadoPct", rotulo: "Avanço estimado acumulado (%)", tipo: "numero", obrigatorio: true, min: 0, maxNumero: 100, passo: 0.1, valor: x.estimadoPct }];
      default: return [];
    }
  }
  function entradas(x, v) {
    if (x.criterio === "Etapas") return { etapas: x.etapas.map(function (e, k) { return v["etapa" + k]; }) };
    if (x.criterio === "Unidades") return { executado: v.executado };
    if (/^Marco/.test(x.criterio)) return { estado: v.estado };
    return { estimadoPct: v.estimadoPct };
  }
  function simular(x, v) {
    var ent = entradas(x, v), clone = Object.assign({}, x);
    if (ent.etapas) clone.etapas = x.etapas.map(function (e, k) { return { nome: e.nome, peso: e.peso, pct: ent.etapas[k] == null ? 0 : ent.etapas[k] }; });
    else Object.keys(ent).forEach(function (k) { clone[k] = ent[k]; });
    return R.avancoPacoteEap(clone);
  }
  function registrarAvanco(codigo) {
    var x = porCodigo(codigo);
    if (!x) return;
    if (!x.trabalho) { GI.ui.toast("Pacote de planejamento não recebe medição: desdobre-o em pacotes de trabalho antes.", "warning"); return; }
    GI.form.abrir({
      titulo: "Registrar avanço · " + x.codigo, subtitulo: x.descricao, tamanho: "lg",
      intro: '<div class="alert">' + U.icone("info") + '<div class="alert__body">Critério: ' + U.esc(textoCriterio(x)) + ". Previsto na linha de base " + F.pct(x.previsto, 1) +
        "; real atual " + F.pct(x.real, 1) + ". O acumulado não regride: estorno só com justificativa e papel Gestor.</div></div>",
      campos: [{ id: "data", rotulo: "Data da medição", tipo: "data", obrigatorio: true, valor: dados.referencia, maxData: dados.referencia }]
        .concat(camposCriterio(x))
        .concat([
          { id: "novo", rotulo: "Avanço acumulado", tipo: "info", html: "" },
          { id: "obs", rotulo: "Observação ou evidência", tipo: "textarea", max: 300, placeholder: "Boletim de medição, relatório de campo, certificado..." },
          { id: "justificativa", rotulo: "Justificativa do estorno", tipo: "textarea", obrigatorio: true, max: 300,
            mostrarSe: function (v) { return simular(x, v) < x.real; } }
        ]),
      aoMudar: function (v, ctx) {
        var n = simular(x, v);
        ctx.info("novo", '<span class="num">' + F.pct(x.real, 1) + " > <b>" + F.pct(n, 1) + "</b></span>" +
          (n < x.real ? ' <span class="valor--negativo">estorno</span>' : ""));
      },
      aoSalvar: function (v) {
        var d = entradas(x, v);
        d.data = v.data; d.obs = v.obs; d.justificativa = v.justificativa;
        return API.eapRegistrarAvanco(projetoId, x.codigo, d).then(function (r) {
          GI.ui.toast("Avanço de " + r.codigo + " registrado: " + F.pct(r.de, 1) + " para " + F.pct(r.para, 1) + ".", "success");
          return carregar();
        });
      }
    });
  }

  /* ---------------- Dicionário da EAP (ficha do pacote) ---------------- */
  function fichaHtml(x) {
    var linhas = [
      ["Tipo", x.trabalho ? "Pacote de trabalho" : "Pacote de planejamento (peso reservado, sem medição)"],
      ["Critério de medição", textoCriterio(x) + (x.criterio === "Etapas" && modelo(x.modelo) ? " · " + modelo(x.modelo).nome : "")],
      ["Peso no projeto", peso(x.peso) + (x.pesoNoPai != null ? " · " + F.pct(x.pesoNoPai, 1) + " da subárea" : "")],
      ["Linha de base", F.data(x.inicio) + " a " + F.data(x.termino)],
      ["Avanço", "previsto " + F.pct(x.previsto, 1) + " · real " + F.pct(x.real, 1) + " · desvio " + pp(x.desvioPP) + " p.p."]
    ];
    if (x.criterio === "Unidades") linhas.push(["Quantidade", F.num(x.executado, 2).replace(/,00$/, "") + " de " + F.num(x.quantidade, 2).replace(/,00$/, "") + " " + x.unidade]);
    var dl = '<dl class="dl">' + linhas.map(function (l) { return "<dt>" + U.esc(l[0]) + "</dt><dd>" + U.esc(l[1]) + "</dd>"; }).join("") + "</dl>";
    var et = x.criterio === "Etapas" ? '<h3 class="section-title mt-6">Etapas</h3><div class="table-wrap"><table class="table table--compact"><thead><tr><th>Etapa</th><th class="num">Peso</th><th class="num">Concluído</th></tr></thead><tbody>' +
      x.etapas.map(function (e) { return "<tr><td>" + U.esc(e.nome) + '</td><td class="num">' + F.num(e.peso) + '</td><td class="num">' + F.pct(e.pct, 0) + "</td></tr>"; }).join("") + "</tbody></table></div>" : "";
    var med = (x.medicoes || []).slice().reverse();
    var hist = '<h3 class="section-title mt-6">Medições</h3>' + (med.length ? '<ul class="feed">' + med.map(function (m) {
      return '<li class="feed__item' + (m.estorno ? " feed__item--warning" : "") + '"><span class="feed__icon">' + U.icone(m.estorno ? "alertTriangle" : "trendingUp") + '</span><span class="feed__body"><b>' +
        F.data(m.data) + " · " + F.pct(m.de, 1) + " > " + F.pct(m.para, 1) + '</b><span class="text-small">' + U.esc(U.pessoa(m.porId)) + (m.obs ? " · " + U.esc(m.obs) : "") + "</span></span></li>";
    }).join("") + "</ul>" : '<p class="text-small text-muted">Nenhuma medição registrada nesta sessão ou na carga inicial.</p>');
    return dl + et + hist + '<h3 class="section-title mt-6">Dicionário</h3>';
  }
  function dicionario(codigo) {
    var x = porCodigo(codigo);
    if (!x) return;
    GI.form.abrir({
      titulo: "Dicionário da EAP · " + x.codigo, subtitulo: x.descricao, tamanho: "lg",
      intro: fichaHtml(x) + '<p class="text-small text-muted">Peso, datas e critério fazem parte da linha de base: mudam só por Nova revisão.</p>',
      campos: [
        { id: "descricao", rotulo: "Descrição", tipo: "texto", obrigatorio: true, max: 120, largura: "full", valor: x.descricao },
        { id: "entregavel", rotulo: "Entregável", tipo: "textarea", max: 300, valor: x.entregavel },
        { id: "aceitacao", rotulo: "Critério de aceitação", tipo: "textarea", max: 300, valor: x.aceitacao },
        { id: "empresa", rotulo: "Empresa executante", tipo: "select", opcoes: opcoesEmpresas(), valor: x.empresaId },
        { id: "responsavel", rotulo: "Responsável", tipo: "select", obrigatorio: true, opcoes: opcoesPessoas(), valor: x.responsavelId },
        { id: "eac", rotulo: "Item da EAC (custo)", tipo: "select", largura: "full", opcoes: opcoesEac(), valor: x.eacCodigo, vazio: "Sem vínculo com a EAC" }
      ],
      aoSalvar: function (v) {
        return API.eapEditarPacote(projetoId, x.codigo, { descricao: v.descricao, entregavel: v.entregavel, aceitacao: v.aceitacao,
          empresaId: v.empresa, responsavelId: v.responsavel, eacCodigo: v.eac }).then(function () {
          GI.ui.toast("Pacote " + x.codigo + " atualizado.", "success");
          return carregar();
        });
      }
    });
  }

  /* ---------------- Novo pacote (desdobramento ou nova revisão) ---------------- */
  function opcoesSms() {
    return dados.smsPendentes.map(function (s) { return { valor: s.codigo, texto: s.codigo + " " + s.titulo + (s.impacto && s.impacto.escopo ? " · " + s.impacto.escopo : "") }; });
  }
  function novoPacote(recursoInicial) {
    if (!dados.arvore.itens.length) { GI.ui.toast("Cadastre a EAP do projeto antes de incluir pacotes.", "warning"); return; }
    var plan = planejamentos();
    if (recursoInicial === "desdobramento" && !plan.length) { GI.ui.toast("Não há pacote de planejamento com peso a desdobrar.", "warning"); return; }
    var subareas = dados.arvore.itens.filter(function (x) { return x.nivel === 2; });
    var p = par();
    GI.form.abrir({
      titulo: recursoInicial === "desdobramento" ? "Desdobrar pacote de planejamento" : "Novo pacote",
      subtitulo: "Desdobramento de pacote de planejamento (o total não muda) ou nova revisão a partir de SM aprovada", tamanho: "lg",
      campos: [
        { id: "recurso", rotulo: "Origem do peso", tipo: "select", obrigatorio: true, largura: "full", valor: recursoInicial || (plan.length ? "desdobramento" : "revisao"),
          opcoes: [{ valor: "desdobramento", texto: "Desdobramento de pacote de planejamento (o total não muda)" }, { valor: "revisao", texto: "Nova revisão da EAP (SM aprovada com impacto em escopo)" }] },
        { id: "origem", rotulo: "Pacote de planejamento", tipo: "select", obrigatorio: true, largura: "full",
          opcoes: plan.map(function (x) { return { valor: x.codigo, texto: rotulo(x) + " · " + peso(x.peso) + " a desdobrar" }; }),
          ajuda: plan.length ? "" : "Não há pacote de planejamento com peso a desdobrar.", mostrarSe: function (v) { return v.recurso === "desdobramento"; } },
        { id: "sm", rotulo: "SM aprovada", tipo: "select", obrigatorio: true, largura: "full", opcoes: opcoesSms(),
          ajuda: dados.smsPendentes.length ? "" : "Não há SM aprovada com impacto em escopo pendente de incorporação.", mostrarSe: function (v) { return v.recurso === "revisao"; } },
        { id: "tipo", rotulo: "Tipo de pacote", tipo: "select", obrigatorio: true, valor: "Trabalho",
          opcoes: [{ valor: "Trabalho", texto: "Pacote de trabalho" }, { valor: "Planejamento", texto: "Pacote de planejamento" }], mostrarSe: function (v) { return v.recurso === "revisao"; } },
        { id: "pai", rotulo: "Subárea", tipo: "select", obrigatorio: true, opcoes: subareas.map(function (x) { return { valor: x.codigo, texto: rotulo(x) }; }) },
        { id: "codigo", rotulo: "Código", tipo: "info", html: '<span class="text-muted">Escolha a subárea</span>' },
        { id: "descricao", rotulo: "Descrição", tipo: "texto", obrigatorio: true, max: 120, largura: "full" },
        { id: "criterio", rotulo: "Critério de medição", tipo: "select", obrigatorio: true, opcoes: R.CRITERIOS_EAP,
          mostrarSe: function (v) { return !(v.recurso === "revisao" && v.tipo === "Planejamento"); } },
        { id: "modelo", rotulo: "Modelo de etapas", tipo: "select", obrigatorio: true, opcoes: modelos().map(function (m) { return { valor: m.id, texto: m.nome }; }),
          mostrarSe: function (v) { return v.criterio === "Etapas" && !(v.recurso === "revisao" && v.tipo === "Planejamento"); } },
        { id: "etapas", rotulo: "Etapas do modelo", tipo: "info", html: "", mostrarSe: function (v) { return v.criterio === "Etapas" && !!v.modelo && !(v.recurso === "revisao" && v.tipo === "Planejamento"); } },
        { id: "unidade", rotulo: "Unidade", tipo: "select", obrigatorio: true, opcoes: UNIDADES, mostrarSe: function (v) { return v.criterio === "Unidades" && !(v.recurso === "revisao" && v.tipo === "Planejamento"); } },
        { id: "quantidade", rotulo: "Quantidade da linha de base", tipo: "numero", obrigatorio: true, min: 0, passo: 0.01,
          mostrarSe: function (v) { return v.criterio === "Unidades" && !(v.recurso === "revisao" && v.tipo === "Planejamento"); } },
        { id: "peso", rotulo: "Peso (% do projeto)", tipo: "numero", obrigatorio: true, min: 0, maxNumero: p.pesoMaximoPacotePct, passo: 0.01,
          ajuda: "Máximo de " + F.num(p.pesoMaximoPacotePct) + "% por pacote; percentual estimado até " + F.num(p.estimadoMaximoPct) + "%." },
        { id: "efeito", rotulo: "Efeito no peso", tipo: "info", html: "" },
        { id: "inicio", rotulo: "Início da linha de base", tipo: "data", obrigatorio: true },
        { id: "termino", rotulo: "Término da linha de base", tipo: "data", obrigatorio: true },
        { id: "empresa", rotulo: "Empresa executante", tipo: "select", opcoes: opcoesEmpresas() },
        { id: "responsavel", rotulo: "Responsável", tipo: "select", obrigatorio: true, opcoes: opcoesPessoas() },
        { id: "eac", rotulo: "Item da EAC (custo)", tipo: "select", largura: "full", opcoes: opcoesEac(), vazio: "Sem vínculo com a EAC" },
        { id: "entregavel", rotulo: "Entregável", tipo: "textarea", max: 300 },
        { id: "aceitacao", rotulo: "Critério de aceitação", tipo: "textarea", max: 300 },
        { id: "justificativa", rotulo: "Justificativa", tipo: "textarea", obrigatorio: true, max: 300 }
      ],
      aoMudar: function (v, ctx) {
        ctx.info("codigo", v.pai ? '<b class="num">' + U.esc(API.proximoCodigoEap(projetoId, v.pai)) + "</b>" : '<span class="text-muted">Escolha a subárea</span>');
        var m = v.modelo && modelo(v.modelo);
        ctx.info("etapas", m ? U.esc(m.etapas.map(function (e) { return (GI.t ? GI.t(e.nome) : e.nome) + " " + F.num(e.peso); }).join(" · ")) : "");
        var efeito = "";
        if (v.recurso === "desdobramento") {
          var o = v.origem && porCodigo(v.origem);
          efeito = o ? '<span class="num">' + U.esc(o.codigo) + ": " + peso(o.peso) + " > <b>" + peso(Math.max(0, Math.round((o.peso - (v.peso || 0)) * 100) / 100)) + "</b></span>" +
            (v.peso > o.peso ? ' <span class="valor--negativo">acima do peso a desdobrar</span>' : v.peso && Math.abs(v.peso - o.peso) < 0.005 ? ' <span class="text-muted">(pacote de planejamento encerrado)</span>' : "")
            : '<span class="text-muted">Escolha o pacote de planejamento</span>';
        } else {
          efeito = v.peso > 0 && v.peso < 100 ? '<span class="text-small">Os demais pacotes são reescalados para ' + F.num(100 - v.peso, 2) + "% (x " + F.num((100 - v.peso) / 100, 4) + ").</span>" : "";
        }
        ctx.info("efeito", efeito);
      },
      validar: function (v) {
        var e = [];
        if (v.inicio && v.termino && v.termino < v.inicio) e.push({ campo: "termino", msg: "O término não pode ser anterior ao início." });
        if (v.criterio === "Percentual estimado" && v.peso > p.estimadoMaximoPct) e.push({ campo: "criterio", msg: "Percentual estimado só vale para pacotes de até " + F.num(p.estimadoMaximoPct) + "% de peso." });
        return e;
      },
      aoSalvar: function (v) {
        var plano = v.recurso === "revisao" && v.tipo === "Planejamento";
        var m = !plano && v.criterio === "Etapas" ? modelo(v.modelo) : null;
        var n = { pai: v.pai, descricao: v.descricao, tipo: plano ? "Planejamento" : "Trabalho", criterio: plano ? null : v.criterio,
          modelo: m ? m.id : null, etapas: m ? m.etapas : null, unidade: v.unidade, quantidade: v.quantidade, peso: v.peso,
          inicio: v.inicio, termino: v.termino, empresaId: v.empresa, responsavelId: v.responsavel, eacCodigo: v.eac, entregavel: v.entregavel, aceitacao: v.aceitacao };
        return API.eapNovoPacote(projetoId, n, { tipo: v.recurso, origem: v.origem, smRef: v.sm, justificativa: v.justificativa }).then(function (r) {
          GI.ui.toast(v.recurso === "revisao" ? "Pacote " + r.codigo + " incluído na Rev " + r.revisao + "; demais pesos reescalados."
            : "Pacote " + r.codigo + " criado com peso desdobrado de " + v.origem + (r.origemEncerrada ? " (pacote de planejamento encerrado)." : "."), "success");
          return carregar();
        });
      }
    });
  }

  /* ---------------- Nova revisão (ajuste de pacote existente) ---------------- */
  function semSmPendente() {
    GI.modal.create({
      title: "Nova revisão da EAP", size: "sm",
      body: '<p>Não há SM aprovada com impacto em escopo pendente de incorporação à EAP.</p><p class="text-small text-muted">Estrutura e pesos da EAP só mudam por revisão, a partir de uma Solicitação de Mudança aprovada em 08 Governança.</p>',
      buttons: [{ label: "Fechar", variant: "secondary" },
        { label: "Abrir Gestão de mudanças", variant: "primary", onClick: function () { window.location.href = U.tela("governanca", "mudancas"); } }]
    });
  }
  function novaRevisao() {
    if (!dados.smsPendentes.length) { semSmPendente(); return; }
    var vig = dados.vigente;
    var pac = folhas();
    GI.form.abrir({
      titulo: "Nova revisão da EAP", subtitulo: "Rev " + (vig ? vig.revisao + 1 : 0) + " · a partir de SM aprovada com impacto em escopo", tamanho: "lg",
      intro: '<p class="text-small text-muted">Ajusta peso, quantidade ou término de um pacote e reescala os demais pesos para fechar 100%. Para incluir um pacote novo, use Novo pacote com origem Nova revisão. A linha de base da Curva S física é reemitida pelo cronograma com os novos pesos.</p>',
      campos: [
        { id: "sm", rotulo: "SM aprovada", tipo: "select", obrigatorio: true, largura: "full", opcoes: opcoesSms() },
        { id: "pacote", rotulo: "Pacote afetado", tipo: "select", obrigatorio: true, largura: "full", opcoes: pac.map(function (x) { return { valor: x.codigo, texto: rotulo(x) + " · " + peso(x.peso) }; }) },
        { id: "peso", rotulo: "Novo peso (% do projeto)", tipo: "numero", obrigatorio: true, min: 0, maxNumero: par().pesoMaximoPacotePct, passo: 0.01 },
        { id: "quantidade", rotulo: "Nova quantidade da linha de base", tipo: "numero", min: 0, passo: 0.01,
          mostrarSe: function (v) { var x = v.pacote && porCodigo(v.pacote); return !!(x && x.criterio === "Unidades"); } },
        { id: "termino", rotulo: "Novo término da linha de base", tipo: "data", ajuda: "Deixe em branco para manter." },
        { id: "efeito", rotulo: "Efeito", tipo: "info", html: "" },
        { id: "justificativa", rotulo: "Justificativa", tipo: "textarea", obrigatorio: true, max: 300 }
      ],
      aoMudar: function (v, ctx) {
        var x = v.pacote && porCodigo(v.pacote);
        if (!x) { ctx.info("efeito", '<span class="text-muted">Escolha o pacote</span>'); return; }
        var t = '<span class="num">' + U.esc(x.codigo) + ": " + peso(x.peso) + " > <b>" + (v.peso > 0 ? peso(v.peso) : "·") + "</b></span>";
        if (x.criterio === "Unidades" && v.quantidade > 0) t += '<br><span class="text-small">Real passa de ' + F.pct(x.real, 1) + " para " + F.pct(Math.min(100, x.executado / v.quantidade * 100), 1) + " (" + F.num(x.executado, 2).replace(/,00$/, "") + " " + U.esc(x.unidade) + " executados).</span>";
        if (v.peso > 0) t += '<br><span class="text-small">Demais pacotes: ' + F.num(100 - x.peso, 2) + "% > " + F.num(100 - v.peso, 2) + "%.</span>";
        ctx.info("efeito", t);
      },
      validar: function (v) {
        var x = v.pacote && porCodigo(v.pacote), e = [];
        if (x && v.quantidade != null && x.criterio === "Unidades" && v.quantidade < x.executado) e.push({ campo: "quantidade", msg: "A nova quantidade não pode ser menor que o executado." });
        if (x && v.termino && v.termino < x.inicio) e.push({ campo: "termino", msg: "O término não pode ser anterior ao início (" + F.data(x.inicio) + ")." });
        return e;
      },
      aoSalvar: function (v) {
        return API.eapNovaRevisao(projetoId, { smRef: v.sm, justificativa: v.justificativa,
          ajustes: [{ codigo: v.pacote, peso: v.peso, quantidade: v.quantidade, termino: v.termino }] }).then(function (r) {
          GI.ui.toast("Rev " + r.revisao + " da EAP criada.", "success");
          return carregar();
        });
      }
    });
    /* Sugestão: SM única pendente preenche a justificativa */
    var campoSm = document.querySelector(".modal [data-campo='sm'] select");
    if (campoSm && dados.smsPendentes.length === 1) {
      var s = dados.smsPendentes[0];
      campoSm.value = s.codigo;
      var just = document.querySelector(".modal [data-campo='justificativa'] textarea");
      if (just) { just.value = s.titulo + " (" + s.codigo + ")."; just.dispatchEvent(new Event("input", { bubbles: true })); }
      campoSm.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }

  /* ---------------- Importações ---------------- */
  function importarPacotes() {
    if (!dados.arvore.itens.length) { GI.ui.toast("Cadastre a EAP do projeto antes de importar pacotes.", "warning"); return; }
    if (!dados.smsPendentes.length) { semSmPendente(); return; }
    GI.form.abrir({
      titulo: "Importar pacotes para nova revisão", subtitulo: "Rev " + (dados.vigente ? dados.vigente.revisao + 1 : 0), textoSalvar: "Continuar",
      intro: '<p class="text-small text-muted">Pacotes novos mudam os pesos da EAP; por isso a importação gera uma nova revisão. Informe a SM que aprovou o acréscimo de escopo.</p>',
      campos: [
        { id: "sm", rotulo: "SM aprovada", tipo: "select", obrigatorio: true, largura: "full", opcoes: opcoesSms() },
        { id: "justificativa", rotulo: "Justificativa da revisão", tipo: "textarea", obrigatorio: true, max: 300 }
      ],
      aoSalvar: function (v) { setTimeout(function () { abrirImportacaoPacotes(v); }, 0); }
    });
  }
  function abrirImportacaoPacotes(rev) {
    var existentes = dados.arvore.itens.map(function (x) { return x.codigo; });
    var nomesPes = Object.keys(U.mapas.pessoas).map(function (k) { return U.mapas.pessoas[k].nome; });
    var nomesEmp = Object.keys(U.mapas.empresas).map(function (k) { return U.mapas.empresas[k].nome; });
    var nomesMod = modelos().map(function (m) { return m.nome; });
    var p = par();
    function idPorNome(mapa, nome) { return Object.keys(mapa).filter(function (k) { return mapa[k].nome === nome; })[0] || null; }
    GI.importar.abrir({
      titulo: "Importar pacotes da EAP", subtitulo: "Pacotes (nível 3) em subáreas existentes", arquivoModelo: "modelo-eap",
      colunas: [
        { campo: "codigo", titulo: "Código", tipo: "texto", obrigatorio: true, exemplo: "4.1.3" },
        { campo: "descricao", titulo: "Descrição", tipo: "texto", obrigatorio: true, exemplo: "Pipe rack PR-03" },
        { campo: "tipo", titulo: "Tipo", tipo: "lista", obrigatorio: true, opcoes: ["Trabalho", "Planejamento"], exemplo: "Trabalho" },
        { campo: "criterio", titulo: "Critério de medição", tipo: "lista", opcoes: R.CRITERIOS_EAP, exemplo: "Unidades" },
        { campo: "modelo", titulo: "Modelo de etapas", tipo: "lista", opcoes: nomesMod, exemplo: "" },
        { campo: "unidade", titulo: "Unidade", tipo: "lista", opcoes: UNIDADES, exemplo: "t" },
        { campo: "quantidade", titulo: "Quantidade", tipo: "num", exemplo: "120" },
        { campo: "peso", titulo: "Peso (% do projeto)", tipo: "num", obrigatorio: true, exemplo: "1,5" },
        { campo: "inicio", titulo: "Início LB", tipo: "data", obrigatorio: true, exemplo: "05/10/2026" },
        { campo: "termino", titulo: "Término LB", tipo: "data", obrigatorio: true, exemplo: "29/01/2027" },
        { campo: "responsavel", titulo: "Responsável", tipo: "lista", obrigatorio: true, opcoes: nomesPes, exemplo: "Carlos Nunes" },
        { campo: "empresa", titulo: "Empresa executante", tipo: "lista", opcoes: nomesEmp, exemplo: "Alfa Montagens" },
        { campo: "eac", titulo: "Item da EAC", tipo: "texto", exemplo: "3.2.4" }
      ],
      validarLinha: function (l) {
        var e = [];
        if (l.codigo && !/^\d+\.\d+\.\d+$/.test(l.codigo)) e.push("Código deve ter 3 níveis (ex.: 4.1.3).");
        else if (l.codigo && existentes.indexOf(l.codigo.split(".").slice(0, 2).join(".")) < 0) e.push("Subárea " + l.codigo.split(".").slice(0, 2).join(".") + " não existe.");
        else if (l.codigo && existentes.indexOf(l.codigo) >= 0) e.push("Código " + l.codigo + " já existe.");
        if (l.tipo === "Trabalho" && !l.criterio) e.push("Pacote de trabalho precisa de critério de medição.");
        if (l.criterio === "Etapas" && !l.modelo) e.push("Critério Etapas precisa do modelo de etapas.");
        if (l.criterio === "Unidades" && (!l.unidade || !(l.quantidade > 0))) e.push("Critério Unidades precisa de unidade e quantidade maior que zero.");
        if (l.peso != null && !(l.peso > 0 && l.peso <= p.pesoMaximoPacotePct)) e.push("Peso deve ficar entre 0 e " + F.num(p.pesoMaximoPacotePct) + "%.");
        if (l.inicio && l.termino && l.termino < l.inicio) e.push("Término anterior ao início.");
        if (l.eac && !eacFolhas.some(function (x) { return x.codigo === l.eac; })) e.push("Item " + l.eac + " não é item de custo (nível 3) da EAC.");
        return e;
      },
      aoImportar: function (linhas) {
        var novos = linhas.map(function (l) {
          var m = l.criterio === "Etapas" ? modelos().filter(function (x) { return x.nome === l.modelo; })[0] : null;
          return { codigo: l.codigo, pai: l.codigo.split(".").slice(0, 2).join("."), descricao: l.descricao, tipo: l.tipo, criterio: l.tipo === "Planejamento" ? null : l.criterio,
            modelo: m ? m.id : null, etapas: m ? m.etapas : null, unidade: l.unidade, quantidade: l.quantidade, peso: l.peso, inicio: l.inicio, termino: l.termino,
            responsavelId: idPorNome(U.mapas.pessoas, l.responsavel), empresaId: idPorNome(U.mapas.empresas, l.empresa), eacCodigo: l.eac || null };
        });
        var soma = novos.reduce(function (s, n) { return s + n.peso; }, 0);
        return API.eapNovaRevisao(projetoId, { smRef: rev.sm, justificativa: rev.justificativa, novos: novos }).then(function (r) {
          carregar();
          return "Rev " + r.revisao + " criada com " + U.plural(novos.length, "pacote novo", "pacotes novos") + " (" + F.num(soma, 2) + "% do projeto).";
        }).catch(function (e) {
          throw new Error(e && e.erros ? e.erros.map(function (x) { return x.msg || x; }).join(" ") : String(e));
        });
      }
    });
  }
  function importarAvanco() {
    if (!folhas().length) { GI.ui.toast("Cadastre a EAP do projeto antes de importar o avanço.", "warning"); return; }
    GI.importar.abrir({
      titulo: "Importar avanço", subtitulo: "Boletim de medição física ou cronograma: avanço acumulado por pacote em " + F.data(dados.referencia), arquivoModelo: "modelo-avanco-eap",
      colunas: [
        { campo: "codigo", titulo: "Código", tipo: "texto", obrigatorio: true, exemplo: "4.4.3" },
        { campo: "pct", titulo: "Avanço acumulado (%)", tipo: "num", exemplo: "12,5" },
        { campo: "executado", titulo: "Quantidade executada", tipo: "num", exemplo: "" }
      ],
      validarLinha: function (l) {
        var x = porCodigo(l.codigo), e = [];
        if (!x || x.nivel !== 3) e.push("Pacote " + l.codigo + " não existe.");
        else if (!x.trabalho) e.push("Pacote de planejamento não recebe medição.");
        else if (x.criterio === "Unidades" ? l.pct == null && l.executado == null : l.pct == null) e.push(x.criterio === "Unidades" ? "Informe o avanço (%) ou a quantidade executada." : "Informe o avanço acumulado (%).");
        return e;
      },
      aoImportar: function (linhas) {
        return API.eapImportarAvanco(projetoId, linhas, dados.referencia).then(function (r) {
          carregar();
          return U.plural(r.aplicados, "pacote atualizado", "pacotes atualizados") + (r.erros.length ? "; " + U.plural(r.erros.length, "linha recusada", "linhas recusadas") + ": " + r.erros.join(" ") : ".");
        });
      }
    });
  }

  /* ---------------- Exportação ---------------- */
  GI.exportar.registrar(function () {
    var p = U.projeto(projetoId);
    tabela.atualizar(arvoreCompleta);
    var dadosEap = tabela.exportacao();
    renderTabela();
    return {
      titulo: projetoId == null ? "EAP da carteira: projetos e pacotes principais" : "EAP: estrutura analítica do projeto", subtitulo: p ? p.codigo + " " + p.nome : "Portfólio de projetos",
      arquivo: "eap-" + (p ? p.codigo : "portfolio"), orientacao: "l",
      blocos: [
        { tipo: "kpis", titulo: "Resumo", itens: Array.prototype.map.call(document.querySelectorAll("#kpis .kpi"), function (k) {
            return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" };
          }) },
        { tipo: "tabela", titulo: "Estrutura analítica do projeto", dados: dadosEap },
        { tipo: "tabela", titulo: "Revisões da EAP", dados: tRev.exportacao() },
        { tipo: "tabela", titulo: "Desdobramentos da revisão vigente", dados: tDes.exportacao() }
      ]
    };
  });

  /* ---------------- Início ---------------- */
  GI.util.pronto().then(function () {
    rec = GI.fin.recolhimento("tabela", renderTabela);
    projetoId = GI.api.projetoAtualId();
    var PF = projetoId == null;
    /* Portfólio: níveis projeto e pacote principal; filtros de pacote não se aplicam */
    if (PF) {
      filtro.nivel = 2;
      document.getElementById("f-nivel").innerHTML = '<option value="1">Mostrar projetos</option><option value="2" selected>Mostrar pacotes principais</option>';
      ["f-criterio", "f-situacao"].forEach(function (id) { var el = document.getElementById(id); el.hidden = true; });
      document.getElementById("t-eap").textContent = "Estrutura analítica da carteira";
      document.getElementById("t-rev").textContent = "Revisão vigente da EAP por projeto";
      document.getElementById("t-des").closest("section").hidden = true;
    }
    function noProjeto(acao, titulo, fn) { return function () { if (PF) U.noProjeto(acao, titulo); else fn(); }; }
    document.getElementById("f-criterio").innerHTML = U.opcoes(R.CRITERIOS_EAP.concat([{ valor: "Planejamento", texto: "Sem medição (planejamento)" }]), "", "Todos os critérios");
    document.getElementById("busca").addEventListener("input", U.debounce(function (ev) { filtro.busca = ev.target.value.trim(); rec.limpar(); renderTabela(); }, 200));
    document.getElementById("f-nivel").addEventListener("change", function (ev) { filtro.nivel = Number(ev.target.value); rec.limpar(); renderTabela(); });
    document.getElementById("f-criterio").addEventListener("change", function (ev) { filtro.criterio = ev.target.value; rec.limpar(); renderTabela(); });
    document.getElementById("f-situacao").addEventListener("change", function (ev) { filtro.situacao = ev.target.value; rec.limpar(); renderTabela(); });
    var ACOES = { novo: function () { novoPacote(); }, importar: importarPacotes, avanco: importarAvanco, revisao: novaRevisao, desdobrar: function () { novoPacote("desdobramento"); } };
    document.getElementById("btn-novo").addEventListener("click", noProjeto("novo", "Novo pacote", ACOES.novo));
    document.getElementById("btn-importar").addEventListener("click", noProjeto("importar", "Importar pacotes", ACOES.importar));
    document.getElementById("btn-importar-avanco").addEventListener("click", noProjeto("avanco", "Importar avanço", ACOES.avanco));
    document.getElementById("btn-revisao").addEventListener("click", noProjeto("revisao", "Nova revisão da EAP", ACOES.revisao));
    document.getElementById("btn-desdobrar").addEventListener("click", noProjeto("desdobrar", "Desdobrar pacote", ACOES.desdobrar));
    document.getElementById("btn-colunas").addEventListener("click", function () { GI.tabela.escolherColunas(tabela); });

    tabela = GI.tabela.criar("tabela", {
      porPagina: 0, pilha: false, legenda: "Estrutura analítica do projeto", vazio: "Nenhum pacote encontrado.", celulaVazia: "",
      colunas: [
        { id: "codigo", titulo: "Código", ordenavel: false, fixa: true, classe: "nowrap",
          html: function (x) { return rec.botao(x) + U.esc(x.codigo); } },
        { id: "descricao", titulo: "Descrição", ordenavel: false, fixa: true,
          valor: function (x) { return x.descricao + (x.nivel === 3 && !x.trabalho ? " (pacote de planejamento)" : ""); },
          html: function (x) { return x.nivel < 3 ? "<b>" + U.esc(x.descricao) + "</b>" : U.esc(x.descricao) + (x.trabalho ? "" : " " + U.badge("Planejamento", "info")); } },
        { id: "criterio", titulo: "Critério de medição", ordenavel: false, oculta: PF, valor: textoCriterio },
        { id: "unidade", titulo: "Un.", ordenavel: false, oculta: true, valor: function (x) { return x.criterio === "Unidades" ? x.unidade : ""; } },
        { id: "quantidade", titulo: "Qtd.", tipo: "num", ordenavel: false, oculta: true, valor: function (x) { return x.criterio === "Unidades" ? x.quantidade : null; } },
        { id: "executado", titulo: "Executado", tipo: "num", ordenavel: false, oculta: true, valor: function (x) { return x.criterio === "Unidades" ? x.executado : null; } },
        { id: "peso", titulo: PF ? "Peso na carteira" : "Peso", tipo: "pct", casas: 2, ordenavel: false,
          html: function (x) { return x.nivel < 3 ? "<b>" + U.esc(peso(x.peso)) + "</b>" : U.esc(peso(x.peso)); } },
        { id: "pesoNoPai", titulo: PF ? "Peso no projeto" : "Peso no nível acima", tipo: "pct", casas: 1, ordenavel: false, oculta: !PF,
          valor: function (x) { return PF && x.nivel === 1 ? null : x.pesoNoPai; } },
        { id: "inicio", titulo: "Início LB", tipo: "data", ordenavel: false, oculta: true },
        { id: "termino", titulo: "Término LB", tipo: "data", ordenavel: false,
          html: function (x) { return U.esc(F.data(x.termino)) + (x.nivel === 3 && x.vencido ? " " + U.badge("vencido", "danger") : ""); },
          exportar: function (x) { return F.data(x.termino) + (x.nivel === 3 && x.vencido ? " (vencido)" : ""); } },
        { id: "previsto", titulo: "Previsto", tipo: "pct", casas: 1, ordenavel: false },
        { id: "real", titulo: "Real", tipo: "pct", casas: 1, ordenavel: false,
          html: function (x) { return x.nivel === 3 && !x.trabalho ? '<span class="text-muted">sem medição</span>' : barra(x.real); } },
        { id: "desvioPP", titulo: "Desvio (p.p.)", tipo: "num", casas: 1, ordenavel: false,
          html: function (x) { return x.nivel === 3 && !x.trabalho ? "" : '<span class="' + classeDesvio(x.faixa) + '">' + pp(x.desvioPP) + "</span>"; } },
        { id: "eacCodigo", titulo: "Item da EAC", ordenavel: false, oculta: true },
        { id: "empresa", titulo: "Empresa", ordenavel: false, oculta: true, valor: function (x) { return x.empresaId ? U.empresa(x.empresaId) : ""; } },
        { id: "responsavel", titulo: "Responsável", ordenavel: false, valor: function (x) { return x.responsavelId ? U.pessoa(x.responsavelId) : ""; } }
      ],
      classeLinha: GI.fin.classeNivel,
      acoes: function (x) {
        if (PF && x.nivel === 1 && x.projetoId) return '<a class="btn btn--ghost btn--sm" href="' + U.tela("planejamento", "eap", { projeto: x.projetoId }) + '" title="Abrir a EAP do projeto">' + U.icone("chevronRight") + "Abrir</a>";
        if (x.nivel !== 3) return "";
        var c = U.esc(x.codigo);
        return '<div class="btn-group">' +
          (x.trabalho ? '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-avanco="' + c + '" aria-label="Registrar avanço de ' + c + '" title="Registrar avanço">' + U.icone("trendingUp") + "</button>" : "") +
          '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-dicionario="' + c + '" aria-label="Dicionário do pacote ' + c + '" title="Dicionário">' + U.icone("fileText") + "</button></div>";
      }
    });
    document.getElementById("tabela").addEventListener("click", function (ev) {
      var a = ev.target.closest("[data-avanco]"), d = ev.target.closest("[data-dicionario]");
      if (a) registrarAvanco(a.getAttribute("data-avanco"));
      else if (d) dicionario(d.getAttribute("data-dicionario"));
    });

    tRev = GI.tabela.criar("revisoes", {
      porPagina: 0, legenda: "Revisões da EAP", ordem: null,
      colunas: (PF ? [U.colunaProjeto()] : []).concat([
        { id: "revisao", titulo: "Revisão", valor: function (r) { return "Rev " + r.revisao; },
          html: function (r) { return "<b>Rev " + r.revisao + "</b>" + (r.revisao === 0 ? " " + U.badge("Linha de base", "info") : "") + (r.vigente ? " " + U.badge("Vigente", "success") : ""); } },
        { id: "data", titulo: "Data", tipo: "data" },
        { id: "pacotes", titulo: "Pacotes", tipo: "num", casas: 0 },
        { id: "alteracao", titulo: "Alteração" },
        { id: "smRef", titulo: "SM", html: function (r) { return r.smRef ? '<a href="' + U.tela("governanca", "mudanca", { codigo: r.smRef }) + '">' + U.esc(r.smRef) + "</a>" : ""; } },
        { id: "justificativa", titulo: "Justificativa" },
        { id: "aprovado", titulo: "Aprovado por", valor: function (r) { return U.pessoa(r.aprovadoPorId); } }
      ]),
      classeLinha: function (r) { return r.vigente && !PF ? "is-selected" : ""; }
    });
    tDes = GI.tabela.criar("desdobramentos", {
      porPagina: 0, legenda: "Desdobramentos da revisão vigente", vazio: "Nenhum desdobramento nesta revisão.",
      colunas: [
        { id: "data", titulo: "Data", tipo: "data" },
        { id: "origem", titulo: "Pacote de planejamento", valor: function (r) { var x = porCodigo(r.origem); return x ? rotulo(x) : r.origem + (r.origemDescricao ? " " + r.origemDescricao : "") + " (encerrado)"; } },
        { id: "destino", titulo: "Pacote de trabalho", valor: function (r) { var x = porCodigo(r.destino); return x ? rotulo(x) : r.destino; } },
        { id: "peso", titulo: "Peso", tipo: "pct", casas: 2 },
        { id: "justificativa", titulo: "Justificativa" },
        { id: "por", titulo: "Registrado por", valor: function (r) { return U.pessoa(r.porId); } }
      ]
    });
    return carregar().then(function () { var a = U.acaoPendente(); if (a && ACOES[a] && !PF) ACOES[a](); });
  });
})(window.GI = window.GI || {});
