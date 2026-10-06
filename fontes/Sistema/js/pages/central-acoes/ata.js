/* ==========================================================================
   Central de Ações > Ata (visualização)
   Faixa da ata; abas Dados da Reunião, Lista de Presença, Anotações e Ações;
   nova revisão, empresas executoras, convidados, anotação/ação,
   replanejamento com justificativa, colunas e histórico.
   Regra 11.5: não retira participante nem empresa com ação em aberto.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt, R = GI.regras;
  var REF = GI.api.referencia();
  var ata = null, revisoes = [], itens = [], vigente = null;
  var colunasVisiveis = null;
  var tabelas = [];
  var raizEl = document.getElementById("ata");

  function statusDe(a) { var s = R.statusAcao(a, REF); return s; }
  function comStatus(lista) {
    return lista.map(function (a) {
      var s = statusDe(a);
      a.status = s.chave; a.statusRotulo = s.rotulo; a.ehAcao = s.ehAcao;
      a.diasAtraso = s.chave === "atrasada" ? R.diasEntre(a.replanejada || a.prevista, REF) : 0;
      return a;
    });
  }
  function ordemItem(a, b) {
    var pa = String(a.item || "0").split(".").map(Number), pb = String(b.item || "0").split(".").map(Number);
    return (pa[0] - pb[0]) || ((pa[1] || 0) - (pb[1] || 0));
  }
  function grupos() {
    var ordem = [], mapa = {};
    itens.slice().sort(ordemItem).forEach(function (a) {
      var g = a.grupo || "Geral";
      if (!mapa[g]) { mapa[g] = { nome: g, num: String(a.item || "").split(".")[0] || String(ordem.length + 1), itens: [] }; ordem.push(mapa[g]); }
      mapa[g].itens.push(a);
    });
    return ordem;
  }
  function editavel() { return vigente && ata.id === vigente.id; }

  /* ---------------- Carga ---------------- */
  function carregar() {
    var id = U.param("id");
    return GI.api.listar("atas").then(function (todas) {
      ata = todas.filter(function (a) { return String(a.id) === String(id); })[0] || null;
      if (!ata) return null;
      revisoes = todas.filter(function (a) { return a.numero === ata.numero; }).sort(function (a, b) { return a.revisao - b.revisao; });
      vigente = revisoes[revisoes.length - 1];
      return GI.api.listar("acoes", { ataId: ata.id });
    }).then(function (lista) {
      if (!ata) {
        raizEl.innerHTML = '<section class="card">' + U.vazio("A ata pedida não existe ou foi removida.", "fileSearch", "Ata não encontrada") +
          '<div class="text-center"><a class="btn btn--primary" href="' + U.tela("central-acoes", "atas") + '">Ir para Atas</a></div></section>';
        return;
      }
      itens = comStatus(lista || []);
      render();
    });
  }

  /* ---------------- Render ---------------- */
  function render() {
    var proj = U.projeto(ata.projetoId);
    document.title = ata.numero + " Rev " + ata.revisao + " · Atas | Gestão Integrada AMT";
    document.getElementById("titulo").textContent = "Ata " + ata.numero + " Rev " + ata.revisao;
    if (GI.layout) GI.layout.detalhe("Ata " + ata.numero + " Rev " + ata.revisao);
    var acoesFaixa = editavel()
      ? '<button type="button" class="btn btn--on-dark" id="btn-revisao">' + U.icone("filePlus") + "Gerar nova revisão</button>"
      : "";
    raizEl.innerHTML =
      (editavel() ? "" : '<div class="alert alert--warning mb-4">' + U.icone("alertCircle") + '<div class="alert__body"><b>Revisão anterior, somente leitura.</b> A revisão vigente é a Rev ' +
        vigente.revisao + '. <a href="' + U.tela("central-acoes", "ata", { id: vigente.id }) + '">Abrir a revisão vigente</a></div></div>') +
      '<section class="faixa" aria-label="Identificação da ata"><div>' +
        '<div class="faixa__codigo">' + U.esc(ata.numero) + " · Rev " + ata.revisao + "</div>" +
        '<div class="faixa__meta"><span>' + U.icone("calendar", 14) + " " + F.data(ata.data) + "</span><span>" + U.esc(ata.tipoReuniao) + "</span>" +
          "<span>" + (proj ? "Projeto " + U.esc(proj.codigo) : "") + "</span><span>Elaborada por " + U.esc(U.pessoa(ata.elaboradoPorId)) + "</span></div>" +
      "</div>" +
      '<div class="faixa__acoes">' + acoesFaixa +
        '<button type="button" class="btn btn--on-dark" id="btn-historico">' + U.icone("history") + "Histórico da ata</button>" +
        '<button type="button" class="btn btn--on-dark" data-exportar="pdf">' + U.icone("filePdf") + "Gerar PDF</button>" +
        '<button type="button" class="btn btn--on-dark" data-exportar="excel">' + U.icone("fileSheet") + "Excel</button>" +
      "</div></section>" +
      '<div class="tabs" data-tabs role="tablist" aria-label="Seções da ata">' +
        '<button type="button" class="tab" role="tab" id="aba-dados" aria-controls="p-dados" aria-selected="false">' + U.icone("fileText") + "Dados da Reunião</button>" +
        '<button type="button" class="tab" role="tab" id="aba-presenca" aria-controls="p-presenca" aria-selected="false">' + U.icone("users") + 'Lista de Presença<span class="tab__count">' + ata.participantesIds.length + "</span></button>" +
        '<button type="button" class="tab" role="tab" id="aba-itens" aria-controls="p-itens" aria-selected="true">' + U.icone("listChecks") + 'Anotações e Ações<span class="tab__count">' + itens.length + "</span></button>" +
      "</div>" +
      '<section class="tab-panel card" role="tabpanel" id="p-dados" aria-labelledby="aba-dados" hidden></section>' +
      '<section class="tab-panel" role="tabpanel" id="p-presenca" aria-labelledby="aba-presenca" hidden></section>' +
      '<section class="tab-panel" role="tabpanel" id="p-itens" aria-labelledby="aba-itens"></section>';
    renderDados(); renderPresenca(); renderItens();
    GI.ui.init(raizEl);
    var aba = U.param("aba");
    if (aba) { var t = document.getElementById("aba-" + aba); if (t) GI.ui.selecionarAba(t); }
  }

  function renderDados() {
    var linhas = [
      ["Número", ata.numero], ["Revisão", "Rev " + ata.revisao], ["Data", F.data(ata.data)], ["Tipo de reunião", ata.tipoReuniao],
      ["Diretoria", ata.diretoria], ["Unidade", ata.unidade], ["Elaborado por", U.pessoa(ata.elaboradoPorId)],
      ["Projeto", ata.projetoId ? (U.projeto(ata.projetoId).codigo + " " + U.projeto(ata.projetoId).nome) : "·"],
      ["Assunto", ata.assunto],
      ["Empresa principal", ata.empresaPrincipalId ? U.empresa(ata.empresaPrincipalId) : "·"],
      ["Empresas executoras", (ata.empresasIds || []).map(U.empresa).join(", ") || "·"]
    ];
    document.getElementById("p-dados").innerHTML =
      '<div class="card__header"><div><h2 class="card__title">Dados da Reunião</h2></div>' +
      (editavel() ? '<div class="btn-group"><button type="button" class="btn btn--secondary btn--sm" id="btn-editar-dados">' + U.icone("edit") + "Editar dados</button>" +
        '<button type="button" class="btn btn--secondary btn--sm" id="btn-empresas">' + U.icone("building") + "Empresas executoras</button></div>" : "") + "</div>" +
      '<dl class="dl">' + linhas.map(function (l) { return "<dt>" + U.esc(l[0]) + "</dt><dd>" + U.esc(l[1]) + "</dd>"; }).join("") + "</dl>";
  }

  function abertasDe(pessoaId) {
    return itens.filter(function (a) { return a.ehAcao && a.status !== "concluida" && a.responsavelId === pessoaId; }).length;
  }
  function renderPresenca() {
    var el = document.getElementById("p-presenca");
    el.innerHTML = '<div class="card card--flush"><div class="card__header"><div><h2 class="card__title">Lista de Presença</h2>' +
      '<p class="card__subtitle">' + U.plural(ata.participantesIds.length, "participante") + "</p></div>" +
      (editavel() ? '<button type="button" class="btn btn--secondary btn--sm" id="btn-convidado">' + U.icone("search") + "Buscar convidado</button>" : "") +
      '</div><div id="tb-presenca"></div></div>';
    var pessoas = ata.participantesIds.map(function (pid) { return U.mapas.pessoas[pid]; }).filter(Boolean);
    GI.tabela.criar("tb-presenca", {
      linhas: pessoas, porPagina: 0, ordem: { coluna: "nome", direcao: "asc" }, legenda: "Participantes",
      colunas: [
        { id: "nome", titulo: "Nome", html: function (p) { return "<b>" + U.esc(p.nome) + "</b>"; } },
        { id: "funcao", titulo: "Função" },
        { id: "empresa", titulo: "Empresa", valor: function (p) { return p.empresaId ? U.empresa(p.empresaId) : "Timenow / cliente"; } },
        { id: "email", titulo: "E-mail" },
        { id: "abertas", titulo: "Ações abertas nesta ata", tipo: "num", valor: function (p) { return abertasDe(p.id); } }
      ],
      acoes: editavel() ? function (p) {
        return '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-retirar="' + p.id + '" aria-label="Retirar ' + U.esc(p.nome) + ' da lista">' + U.icone("trash") + "</button>";
      } : null
    });
  }

  function colunasItens() {
    return [
      { id: "item", titulo: "Item", classe: "num", fixa: true, valor: function (a) { return a.item; } },
      { id: "tipo", titulo: "Tipo", html: function (a) { return U.badge(a.tipo, a.tipo === "Informação" ? "purple" : "primary"); } },
      { id: "assunto", titulo: "Assunto / Descrição", fixa: true, valor: function (a) { return a.assunto; },
        html: function (a) { return '<div class="cell-title"><b>' + U.esc(a.assunto) + "</b><small>" + U.esc(a.descricao || "") + "</small></div>"; },
        exportar: function (a) { return a.assunto + (a.descricao ? " · " + a.descricao : ""); } },
      { id: "solicitante", titulo: "Solicitante", valor: function (a) { return U.pessoa(a.solicitanteId); }, oculta: true },
      { id: "responsavel", titulo: "Responsável", valor: function (a) { return U.pessoa(a.responsavelId); } },
      { id: "prevista", titulo: "Prevista", tipo: "data" },
      { id: "replanejada", titulo: "Replanejada", tipo: "data" },
      { id: "conclusao", titulo: "Conclusão", tipo: "data", oculta: true },
      { id: "status", titulo: "Status", fixa: true, valor: function (a) { return a.statusRotulo; },
        html: function (a) { return U.badge(a.statusRotulo, U.statusAcao(a.status), true) + (a.status === "atrasada" ? '<br><small class="text-muted">há ' + U.plural(a.diasAtraso, "dia") + "</small>" : ""); } }
    ];
  }
  function acoesItem(a) {
    if (!editavel()) return a.replanejamentos && a.replanejamentos.length ? '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-just="' + a.id + '" aria-label="Justificativas">' + U.icone("history") + "</button>" : "";
    var h = '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-editar="' + a.id + '" aria-label="Editar item ' + U.esc(a.item) + '" title="Editar">' + U.icone("edit") + "</button>";
    if (a.ehAcao && a.status !== "concluida") h += '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-replanejar="' + a.id + '" aria-label="Registrar replanejamento do item ' + U.esc(a.item) + '" title="Registrar replanejamento">' + U.icone("calendarClock") + "</button>";
    if (a.replanejamentos && a.replanejamentos.length) h += '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-just="' + a.id + '" aria-label="Justificativas do item ' + U.esc(a.item) + '" title="Justificativas">' + U.icone("history") + "</button>";
    return h;
  }
  function renderItens() {
    var el = document.getElementById("p-itens");
    var n = function (st) { return itens.filter(function (a) { return a.status === st; }).length; };
    var gs = grupos();
    var abertas = n("andamento") + n("atrasada");
    var previstas = itens.filter(function (a) { return a.ehAcao && a.prevista && a.prevista <= REF; }).length;   /* prazo original até a data de referência */
    el.innerHTML =
      '<div class="toolbar">' +
        (editavel() ? '<button type="button" class="btn btn--primary" id="btn-novo-item">' + U.icone("plus") + "Nova anotação/ação</button>" : "") +
        '<button type="button" class="btn btn--secondary" id="btn-colunas">' + U.icone("columns") + "Colunas da tabela</button>" +
      "</div>" +
      (gs.length ? gs.map(function (g, k) {
        return '<section class="card card--flush mb-4" aria-labelledby="g-' + k + '"><div class="card__header"><h2 class="grupo-titulo" id="g-' + k + '"><span class="grupo-titulo__num">' + U.esc(g.num) + "</span>" +
          U.esc(g.nome) + "</h2></div><div id=\"tb-g-" + k + "\"></div></section>";
      }).join("") : '<section class="card">' + U.vazio("Esta ata ainda não tem anotações nem ações.", "listChecks", "Sem itens") + "</section>") +
      '<div class="kpi-grid mt-6" aria-label="Resumo da ata">' +
        U.kpi({ rotulo: "Itens", valor: F.num(itens.length), icone: "list", cor: "primary", esperado: { rotulo: "Referência", valor: F.num(itens.length) } }) +
        U.kpi({ rotulo: "Em dia", valor: F.num(n("andamento")), icone: "clock", cor: "info", esperado: { rotulo: "Esperado", valor: F.num(abertas) } }) +
        U.kpi({ rotulo: "Atrasadas", valor: F.num(n("atrasada")), icone: "alertTriangle", cor: "danger", esperado: { rotulo: "Meta", valor: "0" } }) +
        U.kpi({ rotulo: "Concluídas", valor: F.num(n("concluida")), icone: "checkCircle", cor: "success", esperado: { rotulo: "Previsto", valor: F.num(previstas) } }) +
        U.kpi({ rotulo: "Informações", valor: F.num(n("info")), icone: "info", cor: "highlight", esperado: { rotulo: "Referência", valor: F.num(itens.length) } }) +
      "</div>";
    tabelas = gs.map(function (g, k) {
      var t = GI.tabela.criar("tb-g-" + k, {
        linhas: g.itens, porPagina: 0, colunas: colunasItens(), acoes: acoesItem, compacta: false, legenda: "Itens do grupo " + g.nome,
        classeLinha: function (a) { return a.status === "atrasada" ? "is-alert" : ""; }
      });
      if (colunasVisiveis) t.colunasVisiveis(colunasVisiveis);
      return t;
    });
  }

  /* ---------------- Ações da tela ---------------- */
  function salvarAta(mudar) {
    return GI.api.obter("atas", ata.id).then(function (orig) { mudar(orig); return GI.api.salvar("atas", orig); })
      .then(function () { return carregar(); });
  }

  function editarDados() {
    GI.form.abrir({
      titulo: "Editar dados da reunião", subtitulo: ata.numero + " Rev " + ata.revisao, tamanho: "lg",
      campos: [
        { id: "tipoReuniao", rotulo: "Tipo de reunião", tipo: "texto", obrigatorio: true, valor: ata.tipoReuniao },
        { id: "diretoria", rotulo: "Diretoria", tipo: "texto", obrigatorio: true, valor: ata.diretoria },
        { id: "unidade", rotulo: "Unidade", tipo: "texto", obrigatorio: true, valor: ata.unidade },
        { id: "elaboradoPorId", rotulo: "Elaborado por", tipo: "select", obrigatorio: true, valor: ata.elaboradoPorId,
          opcoes: Object.keys(U.mapas.pessoas).map(function (k) { return { valor: k, texto: U.mapas.pessoas[k].nome }; }) },
        { id: "assunto", rotulo: "Assunto", tipo: "textarea", obrigatorio: true, max: 150, linhas: 2, valor: ata.assunto }
      ],
      aoSalvar: function (v) {
        return salvarAta(function (o) { o.tipoReuniao = v.tipoReuniao; o.diretoria = v.diretoria; o.unidade = v.unidade; o.elaboradoPorId = Number(v.elaboradoPorId); o.assunto = v.assunto; })
          .then(function () { GI.ui.toast("Dados atualizados.", "success"); });
      }
    });
  }

  function empresas() {
    var ops = Object.keys(U.mapas.empresas).map(function (k) { return { valor: k, texto: U.mapas.empresas[k].nome }; });
    GI.form.abrir({
      titulo: "Empresas executoras", subtitulo: ata.numero, tamanho: "lg",
      campos: [
        { id: "principal", rotulo: "Empresa principal", tipo: "select", opcoes: ops, vazio: "Nenhuma", valor: ata.empresaPrincipalId, largura: "full" },
        { id: "empresas", rotulo: "Empresas executoras", tipo: "multi", opcoes: ops, valor: (ata.empresasIds || []).map(String) }
      ],
      validar: function (v) {
        var retiradas = (ata.empresasIds || []).filter(function (e) { return v.empresas.indexOf(String(e)) < 0; });
        var bloqueadas = retiradas.filter(function (e) {
          return itens.some(function (a) { var p = U.mapas.pessoas[a.responsavelId]; return a.ehAcao && a.status !== "concluida" && p && p.empresaId === e; });
        });
        return bloqueadas.length ? [{ campo: "empresas", msg: "Não é possível retirar " + bloqueadas.map(U.empresa).join(", ") + ": há ação em aberto com responsável da empresa." }] : [];
      },
      aoSalvar: function (v) {
        return salvarAta(function (o) {
          o.empresasIds = v.empresas.map(Number);
          o.empresaPrincipalId = v.principal ? Number(v.principal) : null;
          if (o.empresaPrincipalId && o.empresasIds.indexOf(o.empresaPrincipalId) < 0) o.empresasIds.unshift(o.empresaPrincipalId);
        }).then(function () { GI.ui.toast("Empresas atualizadas.", "success"); });
      }
    });
  }

  function convidado() {
    var fora = Object.keys(U.mapas.pessoas).filter(function (k) { return ata.participantesIds.indexOf(Number(k)) < 0; });
    if (!fora.length) { GI.ui.toast("Todas as pessoas cadastradas já estão na lista.", "info"); return; }
    GI.form.abrir({
      titulo: "Buscar convidado", subtitulo: ata.numero, textoSalvar: "Adicionar",
      campos: [{ id: "pessoas", rotulo: "Pessoas cadastradas", tipo: "multi", obrigatorio: true,
        opcoes: fora.map(function (k) { var p = U.mapas.pessoas[k]; return { valor: k, texto: p.nome + " · " + p.funcao }; }) }],
      aoSalvar: function (v) {
        return salvarAta(function (o) { o.participantesIds = o.participantesIds.concat(v.pessoas.map(Number)); })
          .then(function () { GI.ui.toast(U.plural(v.pessoas.length, "convidado adicionado", "convidados adicionados") + ".", "success"); GI.ui.selecionarAba(document.getElementById("aba-presenca")); });
      }
    });
  }

  function retirar(pid) {
    pid = Number(pid);
    var n = abertasDe(pid);
    if (n) { GI.ui.toast("Não é possível retirar " + U.pessoa(pid) + ": " + U.plural(n, "ação aberta", "ações abertas") + " sob sua responsabilidade nesta ata.", "warning", 6000); return; }
    GI.modal.confirm({ title: "Retirar participante", message: "Retirar " + U.pessoa(pid) + " da lista de presença?", okText: "Retirar", danger: true }).then(function (ok) {
      if (!ok) return;
      salvarAta(function (o) { o.participantesIds = o.participantesIds.filter(function (x) { return x !== pid; }); })
        .then(function () { GI.ui.toast("Participante retirado.", "success"); GI.ui.selecionarAba(document.getElementById("aba-presenca")); });
    });
  }

  function formItem(item) {
    var pessoas = ata.participantesIds.map(function (pid) { return { valor: pid, texto: U.pessoa(pid) }; });
    var nomesGrupos = grupos().map(function (g) { return g.nome; });
    GI.form.abrir({
      titulo: item ? "Editar item " + item.item : "Nova anotação/ação", subtitulo: ata.numero + " Rev " + ata.revisao, tamanho: "lg",
      intro: '<p class="text-small text-muted">Responsável e solicitante vêm da lista de presença. Para mudar o prazo de uma ação existente use "Registrar replanejamento".</p>',
      campos: [
        { id: "tipo", rotulo: "Tipo", tipo: "select", obrigatorio: true, valor: item ? item.tipo : "Ação", opcoes: [{ valor: "Ação", texto: "Ação" }, { valor: "Informação", texto: "Informação" }] },
        { id: "grupo", rotulo: "Grupo / Área", tipo: "texto", obrigatorio: true, valor: item ? item.grupo : "", sugestoes: nomesGrupos, ajuda: "Escolha um grupo existente ou digite um novo." },
        { id: "assunto", rotulo: "Assunto", tipo: "texto", obrigatorio: true, max: 150, valor: item ? item.assunto : "", largura: "full" },
        { id: "descricao", rotulo: "Descrição", tipo: "textarea", obrigatorio: true, max: 500, valor: item ? item.descricao : "" },
        { id: "solicitanteId", rotulo: "Solicitante", tipo: "select", obrigatorio: true, opcoes: pessoas, valor: item ? item.solicitanteId : GI.api.sessaoAtual().pessoaId },
        { id: "responsavelId", rotulo: "Responsável", tipo: "select", obrigatorio: true, opcoes: pessoas, valor: item ? item.responsavelId : "" },
        { id: "prevista", rotulo: "Data prevista", tipo: "data", valor: item ? item.prevista : "", desabilitado: !!(item && item.replanejada), ajuda: "Obrigatória para ações." },
        { id: "conclusao", rotulo: "Data de conclusão", tipo: "data", valor: item ? item.conclusao : "", ajuda: "Preenchida define Concluída." }
      ],
      validar: function (v) {
        var e = [];
        if (v.tipo === "Ação" && !v.prevista && !(item && item.replanejada)) e.push({ campo: "prevista", msg: "Informe a data prevista da ação." });
        return e;
      },
      aoSalvar: function (v) {
        var base = item ? GI.api.obter("acoes", item.id) : Promise.resolve({ projetoId: ata.projetoId, origem: "Ata", ataId: ata.id, replanejada: null });
        return base.then(function (o) {
          var grupoMudou = !item || item.grupo !== v.grupo;
          o.tipo = v.tipo; o.grupo = v.grupo; o.assunto = v.assunto; o.descricao = v.descricao;
          o.solicitanteId = Number(v.solicitanteId); o.responsavelId = Number(v.responsavelId);
          if (!(item && item.replanejada)) o.prevista = v.tipo === "Ação" ? v.prevista : (v.prevista || null);
          o.conclusao = v.conclusao || null;
          if (grupoMudou) o.item = proximoItem(v.grupo);
          return GI.api.salvar("acoes", o);
        }).then(function (s) { GI.ui.toast((item ? "Item " : "Item " + s.item + " ") + "salvo.", "success"); return carregar(); });
      }
    });
  }
  function proximoItem(grupo) {
    var gs = grupos();
    var g = gs.filter(function (x) { return x.nome === grupo; })[0];
    if (!g) {
      var maior = gs.reduce(function (m, x) { return Math.max(m, Number(x.num) || 0); }, 0);
      return (maior + 1) + ".1";
    }
    var k = g.itens.reduce(function (m, a) { return Math.max(m, Number(String(a.item).split(".")[1]) || 0); }, 0);
    return g.num + "." + (k + 1);
  }

  function itemPorId(id) { return itens.filter(function (a) { return String(a.id) === String(id); })[0]; }
  function replanejar(id) {
    var a = itemPorId(id);
    GI.form.abrir({
      titulo: "Registrar replanejamento", subtitulo: "Item " + a.item + " · " + a.assunto,
      intro: '<p class="text-small text-muted">Prazo vigente: <b>' + F.data(a.replanejada || a.prevista) + "</b>.</p>",
      campos: [
        { id: "data", rotulo: "Nova data", tipo: "data", obrigatorio: true, min: REF },
        { id: "justificativa", rotulo: "Justificativa", tipo: "textarea", obrigatorio: true, max: 300, ajuda: "Obrigatória (mínimo de 10 caracteres)." }
      ],
      validar: function (v) {
        var e = [];
        if (v.data && v.data < REF) e.push({ campo: "data", msg: "A nova data não pode ser anterior à data de referência." });
        if (v.justificativa && v.justificativa.length < 10) e.push({ campo: "justificativa", msg: "Detalhe a justificativa (mínimo de 10 caracteres)." });
        return e;
      },
      aoSalvar: function (v) {
        return GI.api.obter("acoes", a.id).then(function (o) {
          o.replanejamentos = (o.replanejamentos || []).concat([{ data: REF, de: o.replanejada || o.prevista, para: v.data, porId: GI.api.sessaoAtual().pessoaId, justificativa: v.justificativa }]);
          o.replanejada = v.data;
          return GI.api.salvar("acoes", o);
        }).then(function () { GI.ui.toast("Replanejamento registrado.", "success"); return carregar(); });
      }
    });
  }
  function justificativas(id) {
    var a = itemPorId(id);
    GI.modal.create({
      title: "Justificativas", subtitle: "Item " + a.item + " · " + a.assunto, size: "lg",
      body: '<p class="text-small text-muted mb-4">Prevista original: <b>' + F.data(a.prevista) + "</b></p>" +
        '<div class="table-wrap table-wrap--stack"><table class="table table--stack table--compact"><thead><tr><th>Registrado em</th><th>De</th><th>Para</th><th>Por</th><th>Justificativa</th></tr></thead><tbody>' +
        (a.replanejamentos || []).slice().reverse().map(function (r) {
          return '<tr><td data-label="Registrado em">' + F.data(r.data) + '</td><td data-label="De">' + F.data(r.de) + '</td><td data-label="Para">' + F.data(r.para) +
            '</td><td data-label="Por">' + U.esc(U.pessoa(r.porId)) + '</td><td data-label="Justificativa">' + U.esc(r.justificativa) + "</td></tr>";
        }).join("") + "</tbody></table></div>",
      buttons: [{ label: "Fechar", variant: "secondary" }]
    });
  }

  function colunas() {
    var cols = colunasItens();
    var atuais = colunasVisiveis || cols.filter(function (c) { return !c.oculta; }).map(function (c) { return c.id; });
    GI.form.abrir({
      titulo: "Colunas da tabela", tamanho: "sm", textoSalvar: "Aplicar",
      campos: [{ id: "cols", rotulo: "Colunas visíveis", tipo: "multi", opcoes: cols.filter(function (c) { return !c.fixa; }).map(function (c) { return { valor: c.id, texto: c.titulo }; }),
        valor: atuais.filter(function (id) { return cols.some(function (c) { return c.id === id && !c.fixa; }); }) }],
      aoSalvar: function (v) {
        colunasVisiveis = cols.filter(function (c) { return c.fixa || v.cols.indexOf(c.id) >= 0; }).map(function (c) { return c.id; });
        tabelas.forEach(function (t) { t.colunasVisiveis(colunasVisiveis); });
      }
    });
  }

  function novaRevisao() {
    GI.form.abrir({
      titulo: "Gerar nova revisão", subtitulo: ata.numero + " · próxima: Rev " + (ata.revisao + 1), textoSalvar: "Gerar revisão",
      intro: '<p class="text-small text-muted">A revisão atual fica guardada como histórico (somente leitura). Os itens são copiados para a nova revisão, que passa a alimentar a Central de Ações.</p>',
      campos: [{ id: "data", rotulo: "Data da nova revisão", tipo: "data", obrigatorio: true, valor: REF, min: ata.data }],
      validar: function (v) { return v.data < ata.data ? [{ campo: "data", msg: "A data não pode ser anterior à revisão atual (" + F.data(ata.data) + ")." }] : []; },
      aoSalvar: function (v) {
        var nova = JSON.parse(JSON.stringify(ata));
        delete nova.id; nova.revisao = ata.revisao + 1; nova.data = v.data;
        return GI.api.salvar("atas", nova).then(function (salva) {
          return GI.api.listar("acoes", { ataId: ata.id }).then(function (origens) {
            return origens.reduce(function (p, a) {
              return p.then(function () { var c = JSON.parse(JSON.stringify(a)); delete c.id; c.ataId = salva.id; return GI.api.salvar("acoes", c); });
            }, Promise.resolve());
          }).then(function () { window.location.href = U.tela("central-acoes", "ata", { id: salva.id }); });
        });
      }
    });
  }

  function historico() {
    GI.modal.create({
      title: "Histórico da ata", subtitle: ata.numero, size: "lg",
      body: '<div class="table-wrap table-wrap--stack"><table class="table table--stack"><thead><tr><th>Revisão</th><th>Data</th><th>Assunto</th><th>Situação</th><th class="cell-actions"><span class="sr-only">Abrir</span></th></tr></thead><tbody>' +
        revisoes.slice().reverse().map(function (r) {
          var atual = r.id === ata.id;
          return '<tr><td data-label="Revisão"><b>Rev ' + r.revisao + '</b></td><td data-label="Data">' + F.data(r.data) + '</td><td data-label="Assunto">' + U.esc(r.assunto) +
            '</td><td data-label="Situação">' + (r.id === vigente.id ? U.badge("Vigente", "success", true) : U.badge("Histórico", "neutral")) + (atual ? " " + U.badge("Aberta agora", "info") : "") +
            '</td><td class="cell-actions" data-label="Abrir">' + (atual ? "" : '<a class="btn btn--ghost btn--sm" href="' + U.tela("central-acoes", "ata", { id: r.id }) + '">Abrir</a>') + "</td></tr>";
        }).join("") + "</tbody></table></div>",
      buttons: [{ label: "Fechar", variant: "secondary" }]
    });
  }

  /* ---------------- Eventos (delegados) ---------------- */
  raizEl.addEventListener("click", function (ev) {
    var b = ev.target.closest("button, a");
    if (!b) return;
    if (b.id === "btn-revisao") novaRevisao();
    else if (b.id === "btn-historico") historico();
    else if (b.id === "btn-editar-dados") editarDados();
    else if (b.id === "btn-empresas") empresas();
    else if (b.id === "btn-convidado") convidado();
    else if (b.id === "btn-novo-item") formItem(null);
    else if (b.id === "btn-colunas") colunas();
    else if (b.hasAttribute("data-retirar")) retirar(b.getAttribute("data-retirar"));
    else if (b.hasAttribute("data-editar")) formItem(itemPorId(b.getAttribute("data-editar")));
    else if (b.hasAttribute("data-replanejar")) replanejar(b.getAttribute("data-replanejar"));
    else if (b.hasAttribute("data-just")) justificativas(b.getAttribute("data-just"));
  });

  GI.exportar.registrar(function () {
    var linhasDados = [["Data", F.data(ata.data)], ["Tipo de reunião", ata.tipoReuniao], ["Diretoria", ata.diretoria], ["Unidade", ata.unidade],
      ["Elaborado por", U.pessoa(ata.elaboradoPorId)], ["Assunto", ata.assunto], ["Empresas executoras", (ata.empresasIds || []).map(U.empresa).join(", ")]];
    var participantes = ata.participantesIds.map(function (pid) { var p = U.mapas.pessoas[pid] || {}; return [p.nome, p.funcao, p.empresaId ? U.empresa(p.empresaId) : "Timenow / cliente"]; });
    var todos = itens.slice().sort(ordemItem);
    return {
      titulo: "Ata " + ata.numero + " Rev " + ata.revisao, subtitulo: ata.assunto, arquivo: "ata-" + ata.numero + "-rev" + ata.revisao, orientacao: "p",
      blocos: [
        { tipo: "tabela", titulo: "Dados da Reunião", dados: { colunas: [{ titulo: "Campo" }, { titulo: "Valor" }], bruto: linhasDados, texto: linhasDados } },
        { tipo: "tabela", titulo: "Lista de Presença", dados: { colunas: [{ titulo: "Nome" }, { titulo: "Função" }, { titulo: "Empresa" }], bruto: participantes, texto: participantes } },
        { tipo: "tabela", titulo: "Anotações e Ações", dados: {
            colunas: [{ titulo: "Item" }, { titulo: "Grupo" }, { titulo: "Tipo" }, { titulo: "Assunto / Descrição" }, { titulo: "Responsável" }, { titulo: "Prevista", tipo: "data" }, { titulo: "Replanejada", tipo: "data" }, { titulo: "Status" }],
            bruto: todos.map(function (a) { return [a.item, a.grupo, a.tipo, a.assunto + " · " + (a.descricao || ""), U.pessoa(a.responsavelId), a.prevista, a.replanejada, a.statusRotulo]; }),
            texto: todos.map(function (a) { return [a.item, a.grupo, a.tipo, a.assunto + " · " + (a.descricao || ""), U.pessoa(a.responsavelId), F.data(a.prevista), F.data(a.replanejada), a.statusRotulo]; })
          } }
      ]
    };
  });

  GI.util.pronto().then(carregar);
})(window.GI = window.GI || {});
