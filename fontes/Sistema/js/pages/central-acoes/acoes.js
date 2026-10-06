/* ==========================================================================
   Central de Ações > Ações
   Lista e kanban de todas as origens; KPIs que filtram; filtros em modal com
   chips; replanejamento com justificativa; conclusão; follow-up simulado.
   Só itens do tipo Ação (Informações ficam na ata). Status sempre calculado.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt;
  var ORIGENS = ["Ata", "Punch list", "Contrato", "Suprimentos", "Risco", "RNC", "HSE", "Mudança", "Lição", "Produtividade"];
  var STATUS = [
    { valor: "aberto", texto: "Em andamento (inclui atrasadas)" },
    { valor: "andamento", texto: "Em dia" },
    { valor: "atrasada", texto: "Somente atrasadas" },
    { valor: "concluida", texto: "Concluídas" },
    { valor: "todos", texto: "Todos" }
  ];
  var filtro = {
    busca: U.param("busca") || "",
    origem: U.param("origem") || "",
    status: U.param("status") || "aberto",
    responsavelId: U.param("responsavel") || ""
  };
  var todas = [];
  var projetoId = GI.api.projetoAtualId();   /* null = Portfólio (todas as ações da carteira) */
  var tabela;
  var visao = "lista";

  /* ---------------- Filtros ---------------- */
  function passaContexto(a) {
    if (!a.ehAcao) return false;
    if (filtro.origem && a.origem !== filtro.origem) return false;
    if (filtro.responsavelId && String(a.responsavelId) !== String(filtro.responsavelId)) return false;
    if (filtro.busca && !U.contem([a.assunto, a.descricao, a.origemRef, a.origem, U.pessoa(a.responsavelId), a.grupo, U.codigoProjeto(a.projetoId)].join(" "), filtro.busca)) return false;
    return true;
  }
  function passaStatus(a) {
    switch (filtro.status) {
      case "aberto": return a.status === "andamento" || a.status === "atrasada";
      case "todos": return true;
      default: return a.status === filtro.status;
    }
  }

  /* ---------------- KPIs ---------------- */
  function renderKpis(base) {
    var n = function (st) { return base.filter(function (a) { return a.status === st; }).length; };
    var abertas = n("andamento") + n("atrasada");
    var ref = GI.api.referencia();
    var previstas = base.filter(function (a) { return a.prevista && a.prevista <= ref; }).length;   /* prazo original até a data de referência */
    var universo = todas.filter(function (a) { return a.ehAcao; }).length;
    document.getElementById("kpis").innerHTML = [
      U.kpi({ rotulo: "Em dia", valor: F.num(n("andamento")), icone: "clock", cor: "info", filtro: { valor: "andamento", ativo: filtro.status === "andamento" },
        esperado: { rotulo: "Esperado", valor: F.num(abertas) },
        rodape: "prazo vigente ainda não venceu" }),
      U.kpi({ rotulo: "Atrasadas", valor: F.num(n("atrasada")), icone: "alertTriangle", cor: "danger", filtro: { valor: "atrasada", ativo: filtro.status === "atrasada" },
        esperado: { rotulo: "Meta", valor: "0" },
        rodape: abertas ? F.pct(n("atrasada") / abertas * 100, 0) + " das abertas" : "" }),
      U.kpi({ rotulo: "Concluídas", valor: F.num(n("concluida")), icone: "checkCircle", cor: "success", filtro: { valor: "concluida", ativo: filtro.status === "concluida" },
        esperado: { rotulo: "Previsto", valor: F.num(previstas) },
        rodape: "com data de conclusão" }),
      U.kpi({ rotulo: "Total de ações", valor: F.num(base.length), icone: "list", cor: "primary", filtro: { valor: "todos", ativo: filtro.status === "todos" },
        esperado: { rotulo: "Referência", valor: F.num(universo) },
        rodape: F.num(abertas) + " em andamento" })
    ].join("");
  }

  /* ---------------- Chips ---------------- */
  function chips() {
    var itens = [];
    var st = STATUS.filter(function (s) { return s.valor === filtro.status; })[0];
    itens.push({ campo: "status", texto: "Status: " + (st ? st.texto : filtro.status), fixo: filtro.status === "aberto" });
    if (filtro.origem) itens.push({ campo: "origem", texto: "Origem: " + filtro.origem });
    if (filtro.responsavelId) itens.push({ campo: "responsavelId", texto: "Responsável: " + U.pessoa(filtro.responsavelId) });
    if (filtro.busca) itens.push({ campo: "busca", texto: "Busca: " + filtro.busca });
    var el = document.getElementById("chips");
    el.innerHTML = '<span class="filter-bar__label">Filtros ativos:</span>' + itens.map(function (c) {
      return '<span class="chip"><span class="chip__label">' + U.esc(c.texto) + "</span>" +
        (c.fixo ? "" : '<button type="button" class="chip__remove" data-limpar="' + c.campo + '" aria-label="Remover filtro ' + U.esc(c.texto) + '">' + U.icone("x") + "</button>") + "</span>";
    }).join("") + (itens.length > 1 || filtro.status !== "aberto" ? '<button type="button" class="btn btn--ghost btn--sm" data-limpar="tudo">Limpar filtros</button>' : "");
  }

  /* ---------------- Lista ---------------- */
  function colunas() {
    return (projetoId == null ? [U.colunaProjeto()] : []).concat([
      { id: "origemRef", titulo: "Origem / Referência", classe: "nowrap", valor: function (a) { return a.origem + " " + (a.origemRef || ""); },
        html: function (a) {
          var l = U.linkOrigem(a);
          var txt = (a.origemRef || "") + (a.ataRevisao ? " Rev " + a.ataRevisao : "");
          return U.badge(a.origem, a.origem === "Ata" ? "primary" : "outline") + "<br>" +
            (l ? '<a href="' + l + '">' + U.esc(txt) + "</a>" : U.esc(txt)) + (a.item ? ' <small class="text-muted">item ' + U.esc(a.item) + "</small>" : "");
        },
        exportar: function (a) { return a.origem + " " + (a.origemRef || "") + (a.item ? " item " + a.item : ""); } },
      { id: "assunto", titulo: "Assunto / Descrição", fixa: true, valor: function (a) { return a.assunto; },
        html: function (a) { return '<div class="cell-title"><b>' + U.esc(a.assunto) + "</b><small>" + U.esc(a.descricao || "") + "</small></div>"; },
        exportar: function (a) { return a.assunto + (a.descricao ? " · " + a.descricao : ""); } },
      { id: "grupo", titulo: "Grupo / Área", oculta: true },
      { id: "solicitante", titulo: "Solicitante", oculta: true, valor: function (a) { return U.pessoa(a.solicitanteId); } },
      { id: "responsavel", titulo: "Responsável", valor: function (a) { return U.pessoa(a.responsavelId); } },
      { id: "prazo", titulo: "Prazo vigente", tipo: "data", valor: function (a) { return a.replanejada || a.prevista; },
        html: function (a) {
          return F.data(a.replanejada || a.prevista) + (a.replanejada ? '<br><small class="text-muted">prevista ' + F.data(a.prevista) + "</small>" : "");
        } },
      { id: "prevista", titulo: "Prevista", tipo: "data", oculta: true },
      { id: "replanejada", titulo: "Replanejada", tipo: "data", oculta: true },
      { id: "conclusao", titulo: "Conclusão", tipo: "data", oculta: true },
      { id: "status", titulo: "Status", fixa: true, valor: function (a) { return a.statusRotulo; },
        html: function (a) {
          return U.badge(a.statusRotulo, U.statusAcao(a.status), true) +
            (a.status === "atrasada" ? '<br><small class="text-muted nowrap">há ' + U.plural(a.diasAtraso, "dia") + "</small>" : "");
        },
        exportar: function (a) { return a.statusRotulo + (a.status === "atrasada" ? " (" + a.diasAtraso + " dias)" : ""); } }
    ]);
  }
  function acoesLinha(a) {
    var h = "";
    if (a.origem === "Punch list") {
      return '<a class="btn btn--ghost btn--icon btn--sm" href="' + U.linkOrigem(a) + '" aria-label="Abrir item ' + U.esc(a.origemRef) + ' na Punch list" title="Tratada na Punch list">' + U.icone("arrowRight") + "</a>";
    }
    if (a.status !== "concluida") {
      h += '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-replanejar="' + a.id + '" aria-label="Registrar replanejamento" title="Registrar replanejamento">' + U.icone("calendarClock") + "</button>";
      h += '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-concluir="' + a.id + '" aria-label="Concluir ação" title="Concluir">' + U.icone("check") + "</button>";
    }
    if (a.replanejamentos && a.replanejamentos.length) {
      h += '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-historico="' + a.id + '" aria-label="Justificativas de replanejamento" title="Justificativas">' + U.icone("history") + "</button>";
    }
    return h;
  }

  /* ---------------- Kanban ---------------- */
  function renderKanban(lista) {
    var colunasK = [
      { st: "andamento", titulo: "Em dia", cls: "" },
      { st: "atrasada", titulo: "Atrasadas", cls: "kanban-card--danger" },
      { st: "concluida", titulo: "Concluídas", cls: "kanban-card--success" }
    ];
    document.getElementById("kanban").innerHTML = colunasK.map(function (c) {
      var itens = lista.filter(function (a) { return a.status === c.st; })
        .sort(function (a, b) { return String(a.replanejada || a.prevista).localeCompare(String(b.replanejada || b.prevista)); });
      return '<section class="kanban__col" aria-label="' + c.titulo + '"><div class="kanban__head"><span>' + c.titulo + "</span>" + U.badge(String(itens.length), "neutral") + "</div>" +
        (itens.length ? itens.map(function (a) {
          var l = U.linkOrigem(a);
          return '<article class="kanban-card ' + c.cls + '"><span class="kanban-card__title">' + U.esc(a.assunto) + "</span>" +
            '<span class="kanban-card__meta">' + (projetoId == null ? U.selosProjeto([a.projetoId]) : "") + U.badge(a.origem, "outline") + (l ? '<a href="' + l + '">' + U.esc(a.origemRef || "") + "</a>" : U.esc(a.origemRef || "")) + "</span>" +
            '<span class="kanban-card__meta"><span>' + U.icone("user", 14) + " " + U.esc(U.pessoa(a.responsavelId)) + "</span><span>" +
            (c.st === "concluida" ? "Concluída " + F.data(a.conclusao) : F.data(a.replanejada || a.prevista) + (a.status === "atrasada" ? " · " + a.diasAtraso + " d" : "")) + "</span></span></article>";
        }).join("") : '<p class="text-small text-muted">Nenhuma ação.</p>') + "</section>";
    }).join("");
  }

  /* ---------------- Render geral ---------------- */
  function aplicar() {
    var base = todas.filter(passaContexto);
    var lista = base.filter(passaStatus);
    renderKpis(base);
    chips();
    document.getElementById("contagem").textContent = U.plural(lista.length, "ação", "ações") + " no filtro atual";
    tabela.atualizar(lista);
    if (visao === "kanban") renderKanban(filtro.status === "aberto" || filtro.status === "todos" ? base : lista);
  }

  function carregar() {
    return GI.api.central.acoes(projetoId == null ? null : { projetoId: projetoId }).then(function (lista) { todas = lista; aplicar(); });
  }

  /* ---------------- Modais ---------------- */
  function abrirFiltros() {
    var pessoasComAcao = {};
    todas.forEach(function (a) { if (a.ehAcao) pessoasComAcao[a.responsavelId] = true; });
    GI.form.abrir({
      titulo: "Filtros da Central", tamanho: "lg", textoSalvar: "Consultar",
      campos: [
        { id: "busca", rotulo: "Busca livre", tipo: "texto", valor: filtro.busca, largura: "full", placeholder: "Assunto, descrição, referência, responsável..." },
        { id: "origem", rotulo: "Origem", tipo: "select", vazio: "Todas as origens", valor: filtro.origem, opcoes: ORIGENS.map(function (o) { return { valor: o, texto: o }; }) },
        { id: "status", rotulo: "Status", tipo: "select", vazio: "Em andamento (inclui atrasadas)", valor: filtro.status === "aberto" ? "" : filtro.status, opcoes: STATUS.slice(1) },
        { id: "responsavelId", rotulo: "Responsável", tipo: "select", vazio: "Todos", valor: filtro.responsavelId, largura: "full",
          opcoes: Object.keys(pessoasComAcao).map(function (k) { return { valor: k, texto: U.pessoa(k) }; }).sort(function (a, b) { return a.texto.localeCompare(b.texto); }) }
      ],
      aoSalvar: function (v) {
        filtro.busca = v.busca; filtro.origem = v.origem; filtro.status = v.status || "aberto";
        filtro.responsavelId = v.responsavelId;
        document.getElementById("busca").value = filtro.busca;
        aplicar();
      }
    });
  }

  function acaoPorId(id) { return todas.filter(function (a) { return String(a.id) === String(id); })[0]; }

  function replanejar(id) {
    var a = acaoPorId(id);
    GI.form.abrir({
      titulo: "Registrar replanejamento", subtitulo: (a.origemRef || "") + " · " + a.assunto,
      intro: '<p class="text-small text-muted">Prazo vigente: <b>' + F.data(a.replanejada || a.prevista) + "</b>. A data prevista original é mantida; a justificativa fica no histórico da ação.</p>",
      campos: [
        { id: "data", rotulo: "Nova data", tipo: "data", obrigatorio: true, min: GI.api.referencia() },
        { id: "justificativa", rotulo: "Justificativa", tipo: "textarea", obrigatorio: true, max: 300, ajuda: "Obrigatória (mínimo de 10 caracteres)." }
      ],
      validar: function (v) {
        var e = [];
        if (v.data && v.data < GI.api.referencia()) e.push({ campo: "data", msg: "A nova data não pode ser anterior à data de referência." });
        if (v.justificativa && v.justificativa.length < 10) e.push({ campo: "justificativa", msg: "Detalhe a justificativa (mínimo de 10 caracteres)." });
        return e;
      },
      aoSalvar: function (v) {
        return GI.api.obter("acoes", a.id).then(function (orig) {
          orig.replanejamentos = (orig.replanejamentos || []).concat([{ data: GI.api.referencia(), de: orig.replanejada || orig.prevista, para: v.data,
            porId: GI.api.sessaoAtual().pessoaId, justificativa: v.justificativa }]);
          orig.replanejada = v.data;
          return GI.api.salvar("acoes", orig);
        }).then(function () { GI.ui.toast("Replanejamento registrado.", "success"); return carregar(); });
      }
    });
  }

  function concluir(id) {
    var a = acaoPorId(id);
    GI.form.abrir({
      titulo: "Concluir ação", subtitulo: (a.origemRef || "") + " · " + a.assunto, textoSalvar: "Concluir",
      campos: [
        { id: "conclusao", rotulo: "Data de conclusão", tipo: "data", obrigatorio: true, valor: GI.api.referencia() },
        { id: "evidencia", rotulo: "Evidência (opcional)", tipo: "arquivo", aceitar: ["pdf", "png", "jpg", "xlsx"] }
      ],
      aoSalvar: function (v) {
        return GI.api.obter("acoes", a.id).then(function (orig) {
          orig.conclusao = v.conclusao;
          if (v.evidencia.length) orig.evidencias = (orig.evidencias || []).concat(v.evidencia); /* TODO: API enviar arquivos */
          return GI.api.salvar("acoes", orig);
        }).then(function () { GI.ui.toast("Ação concluída.", "success"); return carregar(); });
      }
    });
  }

  function historico(id) {
    var a = acaoPorId(id);
    var linhas = (a.replanejamentos || []).slice().reverse().map(function (r) {
      return "<tr><td data-label=\"Registrado em\" class=\"nowrap\">" + F.data(r.data) + "</td><td data-label=\"De\" class=\"nowrap\">" + F.data(r.de) +
        "</td><td data-label=\"Para\" class=\"nowrap\">" + F.data(r.para) + "</td><td data-label=\"Por\">" + U.esc(U.pessoa(r.porId)) +
        "</td><td data-label=\"Justificativa\">" + U.esc(r.justificativa) + "</td></tr>";
    }).join("");
    GI.modal.create({
      title: "Justificativas de replanejamento", subtitle: a.assunto, size: "lg",
      body: '<p class="text-small text-muted mb-4">Prevista original: <b>' + F.data(a.prevista) + "</b></p>" +
        '<div class="table-wrap table-wrap--stack"><table class="table table--stack table--compact"><thead><tr><th>Registrado em</th><th>De</th><th>Para</th><th>Por</th><th>Justificativa</th></tr></thead><tbody>' +
        linhas + "</tbody></table></div>",
      buttons: [{ label: "Fechar", variant: "secondary" }]
    });
  }

  function escolherColunas() {
    var cols = tabela.colunas();
    GI.form.abrir({
      titulo: "Colunas da tabela", tamanho: "sm", textoSalvar: "Aplicar",
      campos: [{ id: "cols", rotulo: "Colunas visíveis", tipo: "multi", obrigatorio: true,
        opcoes: cols.filter(function (c) { return !c.fixa; }).map(function (c) { return { valor: c.id, texto: c.titulo }; }),
        valor: cols.filter(function (c) { return c.visivel && !c.fixa; }).map(function (c) { return c.id; }) }],
      aoSalvar: function (v) {
        var fixas = cols.filter(function (c) { return c.fixa; }).map(function (c) { return c.id; });
        tabela.colunasVisiveis(cols.filter(function (c) { return fixas.indexOf(c.id) >= 0 || v.cols.indexOf(c.id) >= 0; }).map(function (c) { return c.id; }));
      }
    });
  }

  /* Follow-up: agrupa as ações abertas do filtro atual por responsável (envio simulado) */
  function followup() {
    var abertas = todas.filter(passaContexto).filter(function (a) { return a.status === "andamento" || a.status === "atrasada"; });
    var grupos = {};
    abertas.forEach(function (a) { (grupos[a.responsavelId] = grupos[a.responsavelId] || []).push(a); });
    var ids = Object.keys(grupos).sort(function (x, y) {
      var ax = grupos[x].filter(function (a) { return a.status === "atrasada"; }).length, ay = grupos[y].filter(function (a) { return a.status === "atrasada"; }).length;
      return ay - ax || U.pessoa(x).localeCompare(U.pessoa(y));
    });
    if (!ids.length) { GI.ui.toast("Nenhuma ação em aberto no filtro atual.", "info"); return; }
    function texto(pid) {
      var l = grupos[pid].slice().sort(function (a, b) { return b.diasAtraso - a.diasAtraso; });
      return "Olá, " + U.pessoa(pid).split(" ")[0] + ".\n\nSeguem suas ações em aberto na Central de Ações (referência " + F.data(GI.api.referencia()) + "):\n\n" +
        l.map(function (a) {
          return "* " + (a.origemRef || a.origem) + ": " + a.assunto + " · prazo " + F.data(a.replanejada || a.prevista) + (a.status === "atrasada" ? " (ATRASADA há " + a.diasAtraso + " dias)" : "");
        }).join("\n") + "\n\nPor favor, atualize o andamento ou registre o replanejamento com justificativa.\n\nPMO · Gestão Integrada AMT";
    }
    var corpo = '<p class="text-small text-muted mb-4">' + U.plural(ids.length, "responsável", "responsáveis") + " com " + U.plural(abertas.length, "ação", "ações") +
      " em aberto no filtro atual. No protótipo nenhum e-mail é enviado.</p>" +
      '<div class="form-grid"><div class="field"><label class="field__label" for="fu-resp">Responsável</label><select class="select" id="fu-resp">' +
      ids.map(function (pid) {
        var at = grupos[pid].filter(function (a) { return a.status === "atrasada"; }).length;
        return '<option value="' + pid + '">' + U.esc(U.pessoa(pid)) + " · " + grupos[pid].length + " abertas" + (at ? ", " + at + " atrasadas" : "") + "</option>";
      }).join("") + "</select></div>" +
      '<div class="field"><span class="field__label">E-mail</span><span class="text-small" id="fu-email"></span></div>' +
      '<div class="field field--full"><label class="field__label" for="fu-texto">Mensagem (prévia)</label><textarea class="textarea" id="fu-texto" rows="10"></textarea></div></div>';
    var m = GI.modal.create({
      title: "Enviar follow-up", size: "lg", body: corpo,
      buttons: [
        { label: "Cancelar", variant: "secondary" },
        { label: "Copiar texto", variant: "secondary", onClick: function () {
            var t = document.getElementById("fu-texto").value;
            if (navigator.clipboard) navigator.clipboard.writeText(t).then(function () { GI.ui.toast("Texto copiado.", "success"); }, function () { GI.ui.toast("Não foi possível copiar.", "warning"); });
          } },
        { label: "Enviar a todos", variant: "primary", onClick: function (api) {
            /* TODO: API POST /acoes/followup (mesmo motor de e-mail da Central) */
            api.close();
            GI.ui.toast("Simulação: " + U.plural(ids.length, "e-mail", "e-mails") + " de follow-up preparados. Nada foi enviado no protótipo.", "info", 6000);
          } }
      ]
    });
    var sel = m.el.querySelector("#fu-resp");
    function atualizar() {
      var p = U.mapas.pessoas[sel.value];
      m.el.querySelector("#fu-email").textContent = p && p.email ? p.email : "sem e-mail cadastrado";
      m.el.querySelector("#fu-texto").value = texto(sel.value);
    }
    sel.addEventListener("change", atualizar);
    atualizar();
  }

  /* ---------------- Eventos ---------------- */
  document.getElementById("kpis").addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-filtro]");
    if (!b) return;
    var v = b.getAttribute("data-filtro");
    filtro.status = filtro.status === v ? "aberto" : v;
    aplicar();
    var novo = document.querySelector('#kpis [data-filtro="' + v + '"]');
    if (novo) novo.focus();
  });
  document.getElementById("chips").addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-limpar]");
    if (!b) return;
    var c = b.getAttribute("data-limpar");
    if (c === "tudo") { filtro = { busca: "", origem: "", status: "aberto", responsavelId: "" }; }
    else if (c === "status") filtro.status = "aberto";
    else filtro[c] = "";
    document.getElementById("busca").value = filtro.busca;
    aplicar();
  });
  document.getElementById("busca").value = filtro.busca;
  document.getElementById("busca").addEventListener("input", U.debounce(function (ev) { filtro.busca = ev.target.value.trim(); aplicar(); }, 200));
  document.getElementById("btn-filtros").addEventListener("click", abrirFiltros);
  document.getElementById("btn-colunas").addEventListener("click", escolherColunas);
  document.getElementById("btn-followup").addEventListener("click", followup);
  document.getElementById("visao").addEventListener("segmented:change", function (ev) {
    visao = ev.detail && ev.detail.value ? ev.detail.value : "lista";
    document.getElementById("painel-lista").hidden = visao !== "lista";
    document.getElementById("painel-kanban").hidden = visao !== "kanban";
    aplicar();
  });
  document.getElementById("tabela").addEventListener("click", function (ev) {
    var b;
    if ((b = ev.target.closest("[data-replanejar]"))) replanejar(b.getAttribute("data-replanejar"));
    else if ((b = ev.target.closest("[data-concluir]"))) concluir(b.getAttribute("data-concluir"));
    else if ((b = ev.target.closest("[data-historico]"))) historico(b.getAttribute("data-historico"));
  });

  GI.exportar.registrar(function () {
    return {
      titulo: "Central de Ações", subtitulo: (projetoId == null ? "Portfólio de projetos · " : "") + document.getElementById("contagem").textContent, arquivo: "central-de-acoes",
      blocos: [
        { tipo: "kpis", titulo: "Resumo", itens: Array.prototype.map.call(document.querySelectorAll("#kpis .kpi"), function (k) {
            return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" };
          }) },
        { tipo: "texto", titulo: "Filtros aplicados", texto: Array.prototype.map.call(document.querySelectorAll("#chips .chip__label"), function (c) { return c.textContent; }).join(" · ") },
        { tipo: "tabela", titulo: "Ações", dados: tabela.exportacao() }
      ]
    };
  });

  GI.util.pronto().then(function () {
    tabela = GI.tabela.criar("tabela", {
      colunas: colunas(), porPagina: 15, ordem: { coluna: "prazo", direcao: "asc" },
      vazio: "Nenhuma ação encontrada com os filtros atuais.",
      classeLinha: function (a) { return a.status === "atrasada" ? "is-alert" : ""; },
      acoes: acoesLinha, legenda: "Ações da Central"
    });
    return carregar();
  });
})(window.GI = window.GI || {});
