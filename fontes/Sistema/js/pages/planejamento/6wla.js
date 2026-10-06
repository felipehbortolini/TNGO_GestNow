/* ==========================================================================
   Planejamento > 6WLA (lookahead de 6 semanas)
   Grade de atividades por semana, restrições (tipo, situação, data de
   remoção) e responsáveis. Atividade das 2 primeiras semanas com restrição
   aberta não deve entrar na programação semanal.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt;
  var projetoId = GI.api.projetoAtualId();
  var TIPOS = ["Projeto", "Material", "Mão de obra", "Equipamento", "Liberação de área", "Segurança", "Documentação", "Predecessora"];
  var DISCIPLINAS = ["Civil", "Estruturas", "Mecânica", "Tubulação", "Elétrica", "Instrumentação", "Pintura", "Comissionamento"];
  var inicio = null, atividades = [], grade, tbRestr;
  var filtro = { busca: U.param("busca") || "", disciplina: "", soRestricao: false, sitRestr: "abertas" };

  function semanaInfo(k) {
    var d = new Date(inicio + "T00:00:00"); d.setDate(d.getDate() + 7 * k);
    var t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
    var dia = t.getUTCDay() || 7; t.setUTCDate(t.getUTCDate() + 4 - dia);
    var inicioAno = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
    var num = Math.ceil(((t - inicioAno) / 86400000 + 1) / 7);
    return { num: num, rotulo: "S" + num, data: d.toLocaleDateString((GI.i18n ? GI.i18n.locale : "pt-BR"), { day: "2-digit", month: "2-digit" }) };
  }

  function visiveis() {
    return atividades.filter(function (a) {
      if (filtro.disciplina && a.disciplina !== filtro.disciplina) return false;
      if (filtro.soRestricao && !a.abertas) return false;
      return U.contem([a.codigo, a.atividade, a.area, a.disciplina, U.empresa(a.empresaId), U.codigoProjeto(a.projetoId)].join(" "), filtro.busca);
    });
  }

  function render() {
    var curto = atividades.filter(function (a) { return a.semanas[0] || a.semanas[1]; });
    var prontasCurto = curto.filter(function (a) { return a.pronta; }).length;
    var restr = [];
    atividades.forEach(function (a) { a.restricoes.forEach(function (r) { restr.push(r); }); });
    var abertas = restr.filter(function (r) { return r.aberta; }).length, vencidas = restr.filter(function (r) { return r.vencida; }).length;
    document.getElementById("kpis").innerHTML = [
      U.kpi({ rotulo: "Atividades no horizonte", valor: F.num(atividades.length), icone: "calendarRange", cor: "primary",
        esperado: { rotulo: "Referência", valor: semanaInfo(0).rotulo + " a " + semanaInfo(5).rotulo } }),
      U.kpi({ rotulo: "Prontas nas 2 próximas semanas", valor: F.num(prontasCurto), icone: "checkCircle", esperado: { rotulo: "Meta", valor: F.num(curto.length) },
        cor: prontasCurto === curto.length ? "success" : "warning", rodape: "sem restrição aberta; podem ir para a programação" }),
      U.kpi({ rotulo: "Restrições abertas", valor: F.num(abertas), icone: "flag", cor: abertas ? "warning" : "success", esperado: { rotulo: "Esperado", valor: F.num(0) }, rodape: "de " + F.num(restr.length) + " identificadas" }),
      U.kpi({ rotulo: "Restrições vencidas", valor: F.num(vencidas), icone: "alertTriangle", cor: vencidas ? "danger" : "success", esperado: { rotulo: "Esperado", valor: F.num(0) }, rodape: "data necessária já passou" }),
      U.kpi({ rotulo: "Índice de remoção", valor: restr.length ? F.num((restr.length - abertas) / restr.length * 100, 0) : "·", unidade: "%", icone: "trendingUp", cor: "info",
        esperado: { rotulo: "Meta", valor: F.pct(100, 0) }, rodape: "restrições removidas ÷ identificadas" })
    ].join("");
    document.getElementById("sub-grade").textContent = "Semanas " + semanaInfo(0).rotulo + " (" + semanaInfo(0).data + ") a " + semanaInfo(5).rotulo + " · faixa laranja = semana programada com restrição aberta";
    grade.atualizar(visiveis());
    var lista = [];
    visiveis().forEach(function (a) { a.restricoes.forEach(function (r) { var x = Object.assign({}, r); x.atv = a; lista.push(x); }); });
    tbRestr.atualizar(filtro.sitRestr === "abertas" ? lista.filter(function (r) { return r.aberta; }) : lista);
  }

  function carregar() {
    return GI.api.planejamento.lookahead(projetoId).then(function (r) { inicio = r.inicio; atividades = r.atividades; montarGrade(); render(); });
  }

  var montada = false;
  function montarGrade() {
    if (montada) return;
    montada = true;
    var cols = (projetoId == null ? [U.colunaProjeto()] : []).concat([
      { id: "codigo", titulo: "ID", classe: "nowrap", html: function (a) { return "<b>" + U.esc(a.codigo) + "</b>"; } },
      { id: "atividade", titulo: "Atividade", html: function (a) {
          return '<div class="cell-title"><b>' + U.esc(a.atividade) + "</b><small>" + U.esc(a.area + " · " + a.disciplina + " · " + U.empresa(a.empresaId)) + "</small></div>";
        }, exportar: function (a) { return a.atividade + " · " + a.area + " · " + a.disciplina; } },
      { id: "responsavel", titulo: "Responsável", valor: function (a) { return U.pessoa(a.responsavelId); } }
    ]);
    for (var k = 0; k < 6; k++) (function (k) {
      var s = semanaInfo(k);
      cols.push({ id: "s" + k, titulo: s.rotulo + " " + s.data, ordenavel: false, classe: "text-center", valor: function (a) { return a.semanas[k] ? "X" : ""; },
        html: function (a) {
          if (!a.semanas[k]) return '<span class="semana semana--vazia" aria-label="Não programada"></span>';
          var risco = a.abertas && k < 2;
          return '<span class="semana' + (risco ? " semana--risco" : "") + '" role="img" aria-label="Programada' + (risco ? " com restrição aberta" : "") + '"></span>';
        } });
    })(k);
    cols.push({ id: "restricoes", titulo: "Restrições", valor: function (a) { return a.abertas; },
      html: function (a) {
        if (!a.restricoes.length) return U.badge("Nenhuma", "success");
        return (a.vencidas ? U.badge(a.vencidas + " vencida" + (a.vencidas > 1 ? "s" : ""), "danger", true) + " " : "") +
          (a.abertas ? U.badge(a.abertas + " aberta" + (a.abertas > 1 ? "s" : ""), "warning") : U.badge("Removidas", "success"));
      }, exportar: function (a) { return a.abertas + " abertas, " + a.vencidas + " vencidas"; } });
    grade = GI.tabela.criar("grade", {
      colunas: cols, porPagina: 0, pilha: false, compacta: true, legenda: "Grade de 6 semanas",
      classeLinha: function (a) { return a.vencidas ? "is-alert" : ""; },
      acoes: function (a) { return '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-nova-restricao="' + a.id + '" aria-label="Nova restrição para ' + U.esc(a.codigo) + '" title="Nova restrição">' + U.icone("flag") + "</button>"; }
    });
    tbRestr = GI.tabela.criar("restricoes", {
      porPagina: 10, ordem: { coluna: "necessaria", direcao: "asc" }, vazio: "Nenhuma restrição neste filtro.", legenda: "Restrições",
      colunas: [
        { id: "atv", titulo: "Atividade", valor: function (r) { return r.atv.codigo; },
          html: function (r) { return '<div class="cell-title"><b>' + U.esc(r.atv.codigo) + "</b><small>" + U.esc(r.atv.atividade) + "</small></div>"; },
          exportar: function (r) { return r.atv.codigo + " " + r.atv.atividade; } },
        { id: "tipo", titulo: "Tipo", html: function (r) { return U.badge(r.tipo, "outline"); }, valor: function (r) { return r.tipo; } },
        { id: "descricao", titulo: "Restrição" },
        { id: "responsavel", titulo: "Responsável", valor: function (r) { return U.pessoa(r.responsavelId); } },
        { id: "necessaria", titulo: "Necessária até", tipo: "data" },
        { id: "remocao", titulo: "Removida em", tipo: "data" },
        { id: "situacao", titulo: "Situação", valor: function (r) { return r.vencida ? "Vencida" : r.aberta ? "Aberta" : "Removida"; },
          html: function (r) { return r.vencida ? U.badge("Vencida", "danger", true) : r.aberta ? U.badge("Aberta", "warning", true) : U.badge("Removida", "success", true); } }
      ],
      classeLinha: function (r) { return r.vencida ? "is-alert" : ""; },
      acoes: function (r) {
        return r.aberta ? '<button type="button" class="btn btn--ghost btn--sm" data-remover="' + r.atv.id + ":" + r.id + '">' + U.icone("check") + "Remover</button>" : "";
      }
    });
  }

  /* ---------------- Entradas de dados ---------------- */
  function opcoesSemanas() { var o = []; for (var k = 0; k < 6; k++) { var s = semanaInfo(k); o.push({ valor: String(k), texto: s.rotulo + " (" + s.data + ")" }); } return o; }
  function novaAtividade() {
    if (projetoId == null) { U.noProjeto("atividade", "Nova atividade no 6WLA"); return; }
    var areas = {}; atividades.forEach(function (a) { areas[a.area] = true; });
    var pref = atividades.length ? atividades[0].codigo.replace(/\d+$/, "") : "LA-";
    var codigo = pref + String(atividades.reduce(function (m, a) { var n = Number((/(\d+)$/.exec(a.codigo) || [0, 0])[1]); return Math.max(m, n); }, 0) + 1).padStart(2, "0");
    GI.form.abrir({
      titulo: "Nova atividade", subtitulo: codigo + " · horizonte de 6 semanas", tamanho: "lg",
      campos: [
        { id: "atividade", rotulo: "Atividade", tipo: "texto", obrigatorio: true, max: 120, largura: "full" },
        { id: "area", rotulo: "Área / local", tipo: "texto", obrigatorio: true, sugestoes: Object.keys(areas) },
        { id: "disciplina", rotulo: "Disciplina", tipo: "select", obrigatorio: true, opcoes: DISCIPLINAS.map(function (d) { return { valor: d, texto: d }; }) },
        { id: "empresaId", rotulo: "Empresa", tipo: "select", obrigatorio: true, opcoes: Object.keys(U.mapas.empresas).map(function (k) { return { valor: k, texto: U.mapas.empresas[k].nome }; }) },
        { id: "responsavelId", rotulo: "Responsável", tipo: "select", obrigatorio: true, opcoes: Object.keys(U.mapas.pessoas).map(function (k) { return { valor: k, texto: U.mapas.pessoas[k].nome }; }) },
        { id: "semanas", rotulo: "Semanas programadas", tipo: "multi", obrigatorio: true, opcoes: opcoesSemanas() }
      ],
      aoSalvar: function (v) {
        var sem = [0, 0, 0, 0, 0, 0]; v.semanas.forEach(function (k) { sem[Number(k)] = 1; });
        return GI.api.salvar("lookahead", { projetoId: projetoId, codigo: codigo, atividade: v.atividade, area: v.area, disciplina: v.disciplina,
          empresaId: Number(v.empresaId), responsavelId: Number(v.responsavelId), semanas: sem, restricoes: [] })
          .then(function () { GI.ui.toast("Atividade " + codigo + " incluída.", "success"); return carregar(); });
      }
    });
  }
  function novaRestricao(atividadeId) {
    GI.form.abrir({
      titulo: "Nova restrição", tamanho: "lg",
      campos: [
        { id: "atividadeId", rotulo: "Atividade", tipo: "select", obrigatorio: true, largura: "full", valor: atividadeId,
          opcoes: atividades.map(function (a) { return { valor: a.id, texto: a.codigo + " · " + a.atividade }; }) },
        { id: "tipo", rotulo: "Tipo", tipo: "select", obrigatorio: true, opcoes: TIPOS.map(function (t) { return { valor: t, texto: t }; }) },
        { id: "responsavelId", rotulo: "Responsável pela remoção", tipo: "select", obrigatorio: true, opcoes: Object.keys(U.mapas.pessoas).map(function (k) { return { valor: k, texto: U.mapas.pessoas[k].nome }; }) },
        { id: "descricao", rotulo: "Descrição", tipo: "textarea", obrigatorio: true, max: 200, linhas: 2 },
        { id: "necessaria", rotulo: "Necessária até", tipo: "data", obrigatorio: true }
      ],
      aoSalvar: function (v) {
        return GI.api.obter("lookahead", v.atividadeId).then(function (o) {
          var id = atividades.reduce(function (m, a) { return Math.max(m, a.restricoes.reduce(function (n, r) { return Math.max(n, r.id); }, 0)); }, 0) + 1;
          o.restricoes.push({ id: id, tipo: v.tipo, descricao: v.descricao, responsavelId: Number(v.responsavelId), necessaria: v.necessaria, remocao: null });
          return GI.api.salvar("lookahead", o);
        }).then(function () { GI.ui.toast("Restrição registrada.", "success"); return carregar(); });
      }
    });
  }
  function remover(chave) {
    var p = chave.split(":"), atv = atividades.filter(function (a) { return String(a.id) === p[0]; })[0];
    var r = atv.restricoes.filter(function (x) { return String(x.id) === p[1]; })[0];
    GI.form.abrir({
      titulo: "Remover restrição", subtitulo: atv.codigo + " · " + r.descricao, textoSalvar: "Registrar remoção",
      campos: [{ id: "remocao", rotulo: "Data de remoção", tipo: "data", obrigatorio: true, valor: GI.api.referencia() },
        { id: "comentario", rotulo: "Como foi removida", tipo: "textarea", max: 200, linhas: 2 }],
      aoSalvar: function (v) {
        return GI.api.obter("lookahead", atv.id).then(function (o) {
          o.restricoes.forEach(function (x) { if (x.id === r.id) { x.remocao = v.remocao; x.comentario = v.comentario; } });
          return GI.api.salvar("lookahead", o);
        }).then(function () { GI.ui.toast("Restrição removida.", "success"); return carregar(); });
      }
    });
  }

  document.getElementById("btn-atividade").addEventListener("click", novaAtividade);
  document.getElementById("btn-restricao").addEventListener("click", function () { novaRestricao(""); });
  document.getElementById("busca").value = filtro.busca;
  document.getElementById("busca").addEventListener("input", U.debounce(function (ev) { filtro.busca = ev.target.value.trim(); render(); }, 200));
  document.getElementById("f-disciplina").innerHTML = U.opcoes(DISCIPLINAS, "", "Todas as disciplinas");
  document.getElementById("f-disciplina").addEventListener("change", function (ev) { filtro.disciplina = ev.target.value; render(); });
  document.getElementById("f-restricao").addEventListener("change", function (ev) { filtro.soRestricao = ev.target.checked; render(); });
  document.getElementById("f-sit-restr").addEventListener("segmented:change", function (ev) { filtro.sitRestr = ev.detail.value; render(); });
  document.getElementById("grade").addEventListener("click", function (ev) { var b = ev.target.closest("[data-nova-restricao]"); if (b) novaRestricao(b.getAttribute("data-nova-restricao")); });
  document.getElementById("restricoes").addEventListener("click", function (ev) { var b = ev.target.closest("[data-remover]"); if (b) remover(b.getAttribute("data-remover")); });

  GI.exportar.registrar(function () {
    return {
      titulo: "6WLA: planejamento de 6 semanas", subtitulo: document.getElementById("sub-grade").textContent.split(" · ")[0], arquivo: "6wla",
      blocos: [
        { tipo: "kpis", titulo: "Indicadores", itens: Array.prototype.map.call(document.querySelectorAll("#kpis .kpi"), function (k) {
            return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" };
          }) },
        { tipo: "tabela", titulo: "Grade de 6 semanas", dados: grade.exportacao() },
        { tipo: "tabela", titulo: "Restrições", dados: tbRestr.exportacao() }
      ]
    };
  });

  GI.util.pronto().then(carregar).then(function () { if (U.acaoPendente() === "atividade" && projetoId != null) novaAtividade(); });
})(window.GI = window.GI || {});
