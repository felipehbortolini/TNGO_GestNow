/* ==========================================================================
   Planejamento > Programação Semanal
   Grade diária de segunda a sábado (Previsto, Dia, Noite); situação da
   programação (Em elaboração, Validada, Publicada) e aprovação do realizado
   (Pendente, Aprovado); Total, PPC e Aderência automáticos; importação
   Excel em 5 passos; PPC por área e aderência por contratada.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt;
  var DIAS = [["seg", "Seg"], ["ter", "Ter"], ["qua", "Qua"], ["qui", "Qui"], ["sex", "Sex"], ["sab", "Sáb"]];
  var projetoId = GI.api.projetoAtualId();
  var programacoes = [], atual = null, lookahead = [], tabela;

  function podePrevisto() { return atual && atual.situacao === "Em elaboração"; }
  function podeRealizado() { return atual && atual.situacao === "Publicada" && atual.aprovacaoRealizado === "Pendente"; }

  /* No Portfólio, o seletor lista as programações de todos os projetos (código do projeto na frente) */
  function rotuloSemana(p) { return (projetoId == null ? U.codigoProjeto(p.projetoId) + " · " : "") + p.semana.replace("2026-", "") + " · " + F.data(p.inicio).slice(0, 5) + " a " + F.data(p.fim).slice(0, 5); }

  function render() {
    var sel = document.getElementById("f-semana");
    sel.innerHTML = U.opcoes(programacoes.map(function (p) { return { valor: p.id, texto: rotuloSemana(p) + " · " + p.situacao }; }), atual.id);
    var fluxo = [];
    if (atual.situacao === "Em elaboração") fluxo.push('<button type="button" class="btn btn--primary" data-fluxo="validar">' + U.icone("check") + "Validar programação</button>");
    if (atual.situacao === "Validada") {
      fluxo.push('<button type="button" class="btn btn--secondary" data-fluxo="voltar">' + U.icone("chevronLeft") + "Voltar para elaboração</button>");
      fluxo.push('<button type="button" class="btn btn--primary" data-fluxo="publicar">' + U.icone("send") + "Publicar</button>");
    }
    if (podeRealizado()) fluxo.push('<button type="button" class="btn btn--primary" data-fluxo="aprovar">' + U.icone("checkCircle") + "Aprovar realizado</button>");
    document.getElementById("fluxo").innerHTML = fluxo.join("");

    var tipoSit = { "Em elaboração": "warning", "Validada": "info", "Publicada": "success" };
    /* Esperado de atividades: atividades do 6WLA na semana (horizonte de 6 semanas); fora dele, a programação anterior do projeto */
    var idx6 = Math.round((new Date(atual.inicio + "T00:00:00") - new Date("2026-09-28T00:00:00")) / 604800000);
    var anterior = programacoes.filter(function (p) { return p.projetoId === atual.projetoId && p.semana < atual.semana; })
      .sort(function (a, b) { return a.semana < b.semana ? 1 : -1; })[0];
    var espAtv = idx6 >= 0 && idx6 <= 5
      ? { rotulo: "Previsto", valor: F.num(lookahead.filter(function (l) { return l.projetoId === atual.projetoId && l.semanas[idx6]; }).length) }
      : { rotulo: "Referência", valor: anterior && anterior.atividades ? F.num(anterior.atividades.length) : "·" };
    document.getElementById("kpis").innerHTML = [
      U.kpi({ rotulo: "Situação da programação", valor: '<span class="text-small">' + U.badge(atual.situacao, tipoSit[atual.situacao], true) + "</span>", icone: "calendarDays", cor: "primary",
        esperado: { rotulo: "Esperado", valor: "Publicada" }, rodape: "elaborada por " + U.esc(U.pessoa(atual.elaboradaPorId)) }),
      U.kpi({ rotulo: "Atividades programadas", valor: F.num(atual.atividades.length), icone: "list", cor: "info", esperado: espAtv }),
      U.kpi({ rotulo: "PPC", valor: atual.ppc == null ? "·" : F.num(atual.ppc, 0), unidade: atual.ppc == null ? "" : "%", icone: "target",
        cor: atual.ppc == null ? "info" : atual.ppc >= 80 ? "success" : atual.ppc >= 60 ? "warning" : "danger", esperado: { rotulo: "Meta", valor: "≥ " + F.pct(80, 0) }, rodape: atual.ppc == null ? "semana ainda não apurada" : "atividades 100% cumpridas" }),
      U.kpi({ rotulo: "Aderência", valor: atual.aderencia == null ? "·" : F.num(atual.aderencia, 0), unidade: atual.aderencia == null ? "" : "%", icone: "gauge",
        cor: atual.aderencia == null ? "info" : atual.aderencia >= 90 ? "success" : atual.aderencia >= 75 ? "warning" : "danger", esperado: { rotulo: "Meta", valor: "≥ " + F.pct(90, 0) }, rodape: "realizado ÷ previsto" }),
      U.kpi({ rotulo: "Aprovação do realizado", valor: '<span class="text-small">' + U.badge(atual.aprovacaoRealizado, atual.aprovacaoRealizado === "Aprovado" ? "success" : "warning", true) + "</span>",
        icone: "checkCircle", cor: atual.aprovacaoRealizado === "Aprovado" ? "success" : "warning", esperado: { rotulo: "Esperado", valor: "Aprovado" }, rodape: atual.aprovadaPorId ? "por " + U.esc(U.pessoa(atual.aprovadaPorId)) : "" })
    ].join("");
    document.getElementById("sub-prog").textContent = rotuloSemana(atual) + (podePrevisto() ? " · edite o previsto" : podeRealizado() ? " · aponte o realizado" : " · somente leitura");
    document.getElementById("btn-nova-atv").disabled = !podePrevisto();
    document.getElementById("btn-importar").disabled = !podePrevisto();
    tabela.atualizar(atual.atividades);

    var ind = document.getElementById("indicadores");
    if (!atual.apurada) {
      ind.hidden = true;
    } else {
      ind.hidden = false;
      GI.charts.bar("g-ppc", { labels: atual.porArea.map(function (a) { return a.chave; }), horizontal: true, percent: true, max: 100, ariaLabel: "PPC por área",
        series: [{ label: "PPC", color: "chart-1", data: atual.porArea.map(function (a) { return a.ppc; }) }] });
      GI.charts.bar("g-ader", { labels: atual.porEmpresa.map(function (a) { return U.empresa(a.chave); }), horizontal: true, percent: true, max: 100, ariaLabel: "Aderência por contratada",
        series: [{ label: "Aderência", color: "chart-4", data: atual.porEmpresa.map(function (a) { return a.aderencia; }) }] });
    }
  }

  function carregar(idSel) {
    return Promise.all([GI.api.planejamento.programacoes(projetoId), GI.api.planejamento.lookahead(projetoId)]).then(function (r) {
      programacoes = r[0]; lookahead = r[1].atividades;
      if (projetoId == null) programacoes.sort(function (a, b) { return a.semana < b.semana ? 1 : a.semana > b.semana ? -1 : a.projetoId - b.projetoId; });
      var alvo = idSel || (atual && atual.id) || (programacoes.filter(function (p) { return p.semana === "2026-S39"; })[0] || programacoes[0]).id;
      atual = programacoes.filter(function (p) { return p.id === Number(alvo); })[0] || programacoes[0];
      render();
    });
  }

  function salvarProgramacao(mudar, msg) {
    return GI.api.obter("programacoes", atual.id).then(function (o) { mudar(o); return GI.api.salvar("programacoes", o); })
      .then(function () { if (msg) GI.ui.toast(msg, "success"); return carregar(atual.id); });
  }

  function fluxo(acao) {
    if (acao === "validar") {
      if (!atual.atividades.length) { GI.ui.toast("Inclua ao menos uma atividade antes de validar.", "warning"); return; }
      salvarProgramacao(function (o) { o.situacao = "Validada"; }, "Programação validada.");
    } else if (acao === "voltar") salvarProgramacao(function (o) { o.situacao = "Em elaboração"; }, "Programação voltou para elaboração.");
    else if (acao === "publicar") {
      GI.modal.confirm({ title: "Publicar programação", message: "Depois de publicada, o previsto não pode mais ser alterado e as frentes passam a apontar o realizado.", okText: "Publicar" })
        .then(function (ok) { if (ok) salvarProgramacao(function (o) { o.situacao = "Publicada"; }, "Programação publicada."); });
    } else if (acao === "aprovar") {
      GI.modal.confirm({ title: "Aprovar realizado", message: "PPC " + (atual.ppc == null ? "não apurado" : F.pct(atual.ppc, 0)) + " e aderência " + (atual.aderencia == null ? "não apurada" : F.pct(atual.aderencia, 0)) + ". Após aprovar, o realizado fica bloqueado.", okText: "Aprovar" })
        .then(function (ok) { if (ok) salvarProgramacao(function (o) { o.aprovacaoRealizado = "Aprovado"; o.aprovadaPorId = GI.api.sessaoAtual().pessoaId; }, "Realizado aprovado."); });
    }
  }

  /* Modal Atividade com a grade diária */
  function gradeHtml(a, editPrev, editReal) {
    function inp(dia, campo, valor, ed) {
      return '<input class="input input--grade" type="number" min="0" step="any" data-dia="' + dia + '" data-campo="' + campo + '" value="' + (valor || 0) + '"' +
        (ed ? "" : " disabled") + ' aria-label="' + campo + " " + dia + '">';
    }
    var linhas = [["prev", "Previsto", editPrev], ["dia", "Realizado dia", editReal], ["noite", "Realizado noite", editReal]];
    return '<div class="table-wrap"><table class="table table--compact grade-diaria"><thead><tr><th scope="col"></th>' +
      DIAS.map(function (d) { return '<th scope="col" class="num">' + d[1] + "</th>"; }).join("") + '<th scope="col" class="num">Total</th></tr></thead><tbody>' +
      linhas.map(function (l) {
        return '<tr><th scope="row">' + l[1] + "</th>" + DIAS.map(function (d) { return "<td>" + inp(d[0], l[0], a ? a.dias[d[0]][l[0]] : 0, l[2]) + "</td>"; }).join("") +
          '<td class="num"><b data-total="' + l[0] + '">0</b></td></tr>';
      }).join("") + "</tbody></table></div>" +
      '<div class="cluster mt-2 text-small" data-resumo></div>';
  }
  function atualizarResumo(el, unidade) {
    var t = { prev: 0, dia: 0, noite: 0 };
    el.querySelectorAll("input[data-dia]").forEach(function (i) { t[i.getAttribute("data-campo")] += Number(i.value) || 0; });
    Object.keys(t).forEach(function (k) { el.querySelector('[data-total="' + k + '"]').textContent = F.num(t[k], 1).replace(/,0$/, ""); });
    var real = t.dia + t.noite, ader = t.prev ? Math.min(100, real / t.prev * 100) : null;
    el.querySelector("[data-resumo]").innerHTML = "<span>Produção prevista: <b>" + F.num(t.prev, 1).replace(/,0$/, "") + " " + U.esc(unidade || "") + "</b></span>" +
      "<span>Realizado: <b>" + F.num(real, 1).replace(/,0$/, "") + "</b></span><span>Aderência: <b>" + (ader == null ? "·" : F.pct(ader, 0)) + "</b></span>" +
      "<span>PPC: " + (t.prev > 0 && real >= t.prev ? U.badge("Cumprida", "success") : U.badge("Não cumprida", "neutral")) + "</span>";
  }

  function formAtividade(a) {
    var editPrev = podePrevisto(), editReal = podeRealizado();
    var semanaIdx = Math.round((new Date(atual.inicio + "T00:00:00") - new Date("2026-09-28T00:00:00")) / 604800000);
    var ops6 = lookahead.filter(function (l) { return l.projetoId === atual.projetoId; }).filter(function (l) { return semanaIdx < 0 || semanaIdx > 5 || l.semanas[semanaIdx]; })
      .map(function (l) { return { valor: l.codigo, texto: l.codigo + " · " + l.atividade + (l.abertas ? " (restrição aberta)" : "") }; });
    var empresas = Object.keys(U.mapas.empresas).map(function (k) { return { valor: k, texto: U.mapas.empresas[k].nome }; });
    var pessoas = Object.keys(U.mapas.pessoas).map(function (k) { return { valor: k, texto: U.mapas.pessoas[k].nome }; });
    var somenteLeitura = !editPrev && !editReal;
    var m = GI.form.abrir({
      titulo: a ? "Atividade " + a.item : "Nova atividade", subtitulo: "Semana " + rotuloSemana(atual) + " · " + atual.situacao, tamanho: "xl", colunas: 3,
      textoSalvar: somenteLeitura ? "Fechar" : "Salvar",
      campos: [
        { id: "idExclusiva", rotulo: "ID Exclusiva (6WLA)", tipo: "select", opcoes: ops6, vazio: "Sem vínculo", valor: a ? a.idExclusiva : "", desabilitado: !editPrev },
        { id: "atividade", rotulo: "Atividade", tipo: "texto", obrigatorio: true, max: 120, valor: a ? a.atividade : "", desabilitado: !editPrev },
        { id: "local", rotulo: "Local", tipo: "texto", obrigatorio: true, valor: a ? a.local : "", desabilitado: !editPrev,
          sugestoes: ["Moagem 210", "Flotação 310", "Subestação 420", "Utilidades 510", "Terraplenagem"] },
        { id: "empresaId", rotulo: "Empresa", tipo: "select", obrigatorio: true, opcoes: empresas, valor: a ? a.empresaId : "", desabilitado: !editPrev },
        { id: "fiscalId", rotulo: "Fiscal", tipo: "select", obrigatorio: true, opcoes: pessoas, valor: a ? a.fiscalId : 12, desabilitado: !editPrev },
        { id: "encarregado", rotulo: "Encarregado", tipo: "texto", obrigatorio: true, valor: a ? a.encarregado : "", desabilitado: !editPrev },
        { id: "unidade", rotulo: "Unidade", tipo: "texto", obrigatorio: true, valor: a ? a.unidade : "", desabilitado: !editPrev, sugestoes: ["m", "m²", "m³", "t", "un", "%", "juntas"] },
        { id: "grade", rotulo: "Grade diária", tipo: "info", html: gradeHtml(a, editPrev, editReal) },
        { id: "observacoes", rotulo: "Observações", tipo: "textarea", max: 300, linhas: 2, valor: a ? a.observacoes : "", desabilitado: somenteLeitura },
        { id: "comentarios", rotulo: "Comentários (causa do não cumprimento)", tipo: "textarea", max: 300, linhas: 2, valor: a ? a.comentarios : "", desabilitado: somenteLeitura }
      ],
      validar: function (v) {
        var l = lookahead.filter(function (x) { return x.codigo === v.idExclusiva; })[0];
        return l && l.abertas && editPrev && (!a || a.idExclusiva !== v.idExclusiva) ? [{ campo: "idExclusiva", msg: "A atividade " + l.codigo + " tem restrição aberta no 6WLA. Remova a restrição antes de programar." }] : [];
      },
      aoSalvar: function (v, api) {
        if (somenteLeitura) return;
        var dias = {};
        DIAS.forEach(function (d) { dias[d[0]] = { prev: 0, dia: 0, noite: 0 }; });
        api.el.querySelectorAll("input[data-dia]").forEach(function (i) { dias[i.getAttribute("data-dia")][i.getAttribute("data-campo")] = Number(i.value) || 0; });
        return salvarProgramacao(function (o) {
          var alvo = a ? o.atividades.filter(function (x) { return x.item === a.item; })[0] : null;
          if (!alvo) { alvo = { item: o.atividades.reduce(function (mx, x) { return Math.max(mx, x.item); }, 0) + 1 }; o.atividades.push(alvo); }
          if (editPrev) {
            alvo.idExclusiva = v.idExclusiva || ""; alvo.atividade = v.atividade; alvo.local = v.local; alvo.empresaId = Number(v.empresaId);
            alvo.fiscalId = Number(v.fiscalId); alvo.encarregado = v.encarregado; alvo.unidade = v.unidade;
          }
          alvo.dias = dias; alvo.observacoes = v.observacoes; alvo.comentarios = v.comentarios;
        }, a ? "Atividade " + a.item + " atualizada." : "Atividade incluída.");
      }
    });
    var unidade = a ? a.unidade : "";
    atualizarResumo(m.el, unidade);
    m.el.addEventListener("input", function (ev) {
      if (ev.target.hasAttribute("data-dia")) atualizarResumo(m.el, unidade);
      if (ev.target.id && /-unidade$/.test(ev.target.id)) { unidade = ev.target.value; atualizarResumo(m.el, unidade); }
    });
  }

  function importar() {
    var nomes = Object.keys(U.mapas.empresas).map(function (k) { return U.mapas.empresas[k].nome; });
    GI.importar.abrir({
      titulo: "Importar programação (Excel)", subtitulo: "Semana " + rotuloSemana(atual) + " · o previsto é adicionado às atividades da semana", arquivoModelo: "modelo-programacao-semanal",
      colunas: [
        { campo: "idExclusiva", titulo: "ID Exclusiva", tipo: "texto", exemplo: "LA-05" },
        { campo: "atividade", titulo: "Atividade", tipo: "texto", obrigatorio: true, exemplo: "Tubulação de reagentes da flotação" },
        { campo: "local", titulo: "Local", tipo: "texto", obrigatorio: true, exemplo: "Flotação 310" },
        { campo: "empresa", titulo: "Empresa", tipo: "lista", obrigatorio: true, opcoes: nomes, exemplo: "Alfa Montagens" },
        { campo: "encarregado", titulo: "Encarregado", tipo: "texto", obrigatorio: true, exemplo: "Sérgio Pinto" },
        { campo: "unidade", titulo: "Unidade", tipo: "texto", obrigatorio: true, exemplo: "m" }
      ].concat(DIAS.map(function (d) { return { campo: d[0], titulo: d[1], tipo: "num", exemplo: d[0] === "sab" ? 0 : 40 }; })),
      validarLinha: function (o) {
        var total = DIAS.reduce(function (s, d) { return s + (o[d[0]] || 0); }, 0);
        return total > 0 ? [] : ["sem produção prevista na semana"];
      },
      aoImportar: function (linhas) {
        return salvarProgramacao(function (o) {
          var prox = o.atividades.reduce(function (mx, x) { return Math.max(mx, x.item); }, 0);
          linhas.forEach(function (l) {
            var dias = {};
            DIAS.forEach(function (d) { dias[d[0]] = { prev: l[d[0]] || 0, dia: 0, noite: 0 }; });
            var emp = Object.keys(U.mapas.empresas).filter(function (k) { return U.mapas.empresas[k].nome === l.empresa; })[0];
            o.atividades.push({ item: ++prox, idExclusiva: l.idExclusiva || "", atividade: l.atividade, local: l.local, empresaId: Number(emp), fiscalId: 12,
              encarregado: l.encarregado, unidade: l.unidade, dias: dias, observacoes: "Importada do Excel", comentarios: "" });
          });
        }).then(function () { return U.plural(linhas.length, "atividade incluída", "atividades incluídas") + " na semana " + rotuloSemana(atual) + "."; });
      }
    });
  }

  document.getElementById("f-semana").addEventListener("change", function (ev) { carregar(Number(ev.target.value)); });
  document.getElementById("fluxo").addEventListener("click", function (ev) { var b = ev.target.closest("[data-fluxo]"); if (b) fluxo(b.getAttribute("data-fluxo")); });
  document.getElementById("btn-nova-atv").addEventListener("click", function () { formAtividade(null); });
  document.getElementById("btn-importar").addEventListener("click", importar);
  document.getElementById("tabela").addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-atividade]");
    if (b) formAtividade(atual.atividades.filter(function (a) { return String(a.item) === b.getAttribute("data-atividade"); })[0]);
  });

  GI.exportar.registrar(function () {
    return {
      titulo: "Programação Semanal " + rotuloSemana(atual), subtitulo: atual.situacao + " · realizado " + atual.aprovacaoRealizado.toLowerCase(), arquivo: "programacao-" + atual.semana,
      blocos: [
        { tipo: "kpis", titulo: "Indicadores", itens: [
          { rotulo: "Situação", valor: atual.situacao }, { rotulo: "Atividades", valor: String(atual.atividades.length) },
          { rotulo: "PPC", valor: atual.ppc == null ? "não apurado" : F.pct(atual.ppc, 0) }, { rotulo: "Aderência", valor: atual.aderencia == null ? "não apurada" : F.pct(atual.aderencia, 0) }] },
        { tipo: "tabela", titulo: "Atividades", dados: tabela.exportacao() },
        { tipo: "tabela", titulo: "Grade diária", dados: (function () {
            var cab = [{ titulo: "Item" }, { titulo: "Atividade" }].concat(DIAS.map(function (d) { return { titulo: d[1] + " prev", tipo: "num" }; }))
              .concat(DIAS.map(function (d) { return { titulo: d[1] + " real", tipo: "num" }; }));
            var bruto = atual.atividades.map(function (a) {
              return [a.item, a.atividade].concat(DIAS.map(function (d) { return a.dias[d[0]].prev; })).concat(DIAS.map(function (d) { return a.dias[d[0]].dia + a.dias[d[0]].noite; }));
            });
            return { colunas: cab, bruto: bruto, texto: bruto.map(function (l) { return l.map(String); }) };
          })() }
      ].concat(atual.apurada ? [{ tipo: "grafico", titulo: "PPC por área", canvas: document.getElementById("g-ppc") },
        { tipo: "grafico", titulo: "Aderência por contratada", canvas: document.getElementById("g-ader") }] : [])
    };
  });

  GI.util.pronto().then(function () {
    tabela = GI.tabela.criar("tabela", {
      porPagina: 0, ordem: { coluna: "item", direcao: "asc" }, vazio: "Nenhuma atividade programada nesta semana.", legenda: "Atividades da semana",
      colunas: [
        { id: "item", titulo: "Item", tipo: "num" },
        { id: "idExclusiva", titulo: "ID 6WLA", classe: "nowrap" },
        { id: "atividade", titulo: "Atividade", html: function (a) { return '<div class="cell-title"><b>' + U.esc(a.atividade) + "</b><small>" + U.esc(a.local) + "</small></div>"; },
          exportar: function (a) { return a.atividade + " · " + a.local; } },
        { id: "empresa", titulo: "Empresa", valor: function (a) { return U.empresa(a.empresaId); } },
        { id: "encarregado", titulo: "Encarregado" },
        { id: "previsto", titulo: "Previsto", tipo: "num", casas: 0, html: function (a) { return F.num(a.previsto) + " " + U.esc(a.unidade); } },
        { id: "realizado", titulo: "Realizado", tipo: "num", casas: 0, html: function (a) { return F.num(a.realizado) + " " + U.esc(a.unidade); } },
        { id: "aderencia", titulo: "Aderência", tipo: "pct", casas: 0 },
        { id: "cumprida", titulo: "PPC", valor: function (a) { return atual.apurada ? (a.cumprida ? "Cumprida" : "Não cumprida") : "Não apurada"; },
          html: function (a) { return !atual.apurada ? U.badge("Não apurada", "neutral") : a.cumprida ? U.badge("Cumprida", "success", true) : U.badge("Não cumprida", "danger", true); } }
      ],
      classeLinha: function (a) { return atual.apurada && !a.cumprida ? "is-alert" : ""; },
      acoes: function (a) {
        var rot = podePrevisto() ? "Editar" : podeRealizado() ? "Apontar" : "Ver";
        return '<button type="button" class="btn btn--ghost btn--sm" data-atividade="' + a.item + '">' + U.icone(podePrevisto() || podeRealizado() ? "edit" : "eye") + rot + "</button>";
      }
    });
    return carregar(U.param("semana"));
  });
})(window.GI = window.GI || {});
