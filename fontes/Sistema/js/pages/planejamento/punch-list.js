/* ==========================================================================
   Planejamento > Punch list
   Lista e painel; fluxo Aberto > Em tratamento > Aguardando verificação >
   Fechado (volta para Em tratamento se reprovar); Cancelado com justificativa.
   Fechamento exige evidência e verificação por pessoa diferente do
   responsável pela execução. Sistema com item A aberto fica bloqueado.
   Cada item é também uma ação na Central (origem Punch list).
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt;
  var projetoId = GI.api.projetoAtualId();
  var DISCIPLINAS = ["Civil", "Mecânica", "Tubulação", "Elétrica", "Instrumentação", "Automação", "Arquitetura"];
  var MARCOS = ["Completação mecânica", "Pré-comissionamento", "Comissionamento", "Partida", "Aceite provisório", "Aceite definitivo"];
  var ORIGENS = ["Walkdown", "Inspeção", "Comissionamento", "Cliente", "Auditoria"];
  var SITUACOES = ["Aberto", "Em tratamento", "Aguardando verificação", "Fechado", "Cancelado"];
  var TIPO_CAT = { A: "danger", B: "purple", C: "info" };
  var TIPO_SIT = { "Aberto": "warning", "Em tratamento": "info", "Aguardando verificação": "purple", "Fechado": "success", "Cancelado": "neutral" };
  var itens = [], sistemas = [], tabela, tbSis;
  var filtro = { busca: U.param("item") || U.param("busca") || "", categoria: "", situacao: U.param("item") ? "" : "abertos", sistemaId: "", disciplina: "", empresaId: "" };

  function passa(p) {
    if (filtro.categoria && p.categoria !== filtro.categoria) return false;
    if (filtro.situacao === "abertos" && !p.aberto) return false;
    if (filtro.situacao && filtro.situacao !== "abertos" && p.situacao !== filtro.situacao) return false;
    if (filtro.sistemaId && String(p.sistemaId) !== String(filtro.sistemaId)) return false;
    if (filtro.disciplina && p.disciplina !== filtro.disciplina) return false;
    if (filtro.empresaId && String(p.empresaId) !== String(filtro.empresaId)) return false;
    return U.contem([p.codigo, p.descricao, p.tag, p.subsistema, p.sistema ? p.sistema.nome : ""].join(" "), filtro.busca);
  }

  /* ---------------- Lista ---------------- */
  function renderLista() {
    var abertos = itens.filter(function (p) { return p.aberto; });
    var fechados = itens.filter(function (p) { return p.situacao === "Fechado"; }).length;
    var validos = itens.filter(function (p) { return p.situacao !== "Cancelado"; }).length;
    var n = function (f) { return itens.filter(f).length; };
    document.getElementById("kpis").innerHTML = [
      U.kpi({ rotulo: "Abertos", valor: F.num(abertos.length), icone: "listChecks", cor: "primary", esperado: { rotulo: "Esperado", valor: F.num(0) }, filtro: { valor: "abertos", ativo: filtro.situacao === "abertos" && !filtro.categoria } }),
      U.kpi({ rotulo: "Categoria A abertos", valor: F.num(abertos.filter(function (p) { return p.categoria === "A"; }).length), icone: "alertTriangle", cor: "danger", esperado: { rotulo: "Esperado", valor: F.num(0) },
        filtro: { valor: "A", ativo: filtro.categoria === "A" }, rodape: "impedem o marco seguinte" }),
      U.kpi({ rotulo: "Aguardando verificação", valor: F.num(n(function (p) { return p.situacao === "Aguardando verificação"; })), icone: "eye", cor: "info", esperado: { rotulo: "Esperado", valor: F.num(0) },
        filtro: { valor: "Aguardando verificação", ativo: filtro.situacao === "Aguardando verificação" } }),
      U.kpi({ rotulo: "Vencidos", valor: F.num(n(function (p) { return p.vencido; })), icone: "clock", cor: "warning", esperado: { rotulo: "Esperado", valor: F.num(0) }, rodape: "prazo passou e o item segue aberto" }),
      U.kpi({ rotulo: "Fechados", valor: F.num(fechados), icone: "checkCircle", cor: "success", esperado: { rotulo: "Meta", valor: F.num(validos) }, filtro: { valor: "Fechado", ativo: filtro.situacao === "Fechado" },
        rodape: validos ? F.pct(fechados / validos * 100, 0) + " dos itens válidos" : "" })
    ].join("");
    var chips = [];
    if (filtro.situacao) chips.push({ c: "situacao", t: "Situação: " + (filtro.situacao === "abertos" ? "abertos" : filtro.situacao) });
    if (filtro.categoria) chips.push({ c: "categoria", t: "Categoria " + filtro.categoria });
    if (filtro.sistemaId) { var s = U.sistema(filtro.sistemaId); chips.push({ c: "sistemaId", t: "Sistema " + (s ? s.codigo + " " + s.nome : "") }); }
    if (filtro.disciplina) chips.push({ c: "disciplina", t: "Disciplina: " + filtro.disciplina });
    if (filtro.empresaId) chips.push({ c: "empresaId", t: "Empresa: " + U.empresa(filtro.empresaId) });
    if (filtro.busca) chips.push({ c: "busca", t: "Busca: " + filtro.busca });
    document.getElementById("chips").innerHTML = chips.length ? '<span class="filter-bar__label">Filtros ativos:</span>' + chips.map(function (x) {
      return '<span class="chip"><span class="chip__label">' + U.esc(x.t) + '</span><button type="button" class="chip__remove" data-limpar="' + x.c + '" aria-label="Remover filtro ' + U.esc(x.t) + '">' + U.icone("x") + "</button></span>";
    }).join("") : "";
    var lista = itens.filter(passa);
    document.getElementById("contagem").textContent = U.plural(lista.length, "item", "itens") + " no filtro atual";
    tabela.atualizar(lista);
  }

  /* ---------------- Painel ---------------- */
  function bloqueio(sistemaId, marco) {
    var idx = MARCOS.indexOf(marco);
    return itens.filter(function (p) {
      if (!p.aberto || p.sistemaId !== sistemaId) return false;
      if (marco === "Aceite definitivo") return true;
      return p.categoria === "A" && MARCOS.indexOf(p.marco) <= idx;
    }).length;
  }
  function renderPainel() {
    var abertos = itens.filter(function (p) { return p.aberto; });
    var bloqueados = sistemas.filter(function (s) { return bloqueio(s.id, "Comissionamento") || bloqueio(s.id, "Completação mecânica"); });
    var al = document.getElementById("alerta-bloqueio");
    al.hidden = !bloqueados.length;
    al.innerHTML = U.icone("alertCircle") + '<div class="alert__body"><b>' + U.plural(bloqueados.length, "sistema bloqueado", "sistemas bloqueados") + " por item A aberto:</b> " +
      bloqueados.map(function (s) { return U.esc(s.codigo + " " + s.nome); }).join(", ") + ".</div>";

    /* Burndown semanal */
    var datas = itens.filter(function (p) { return p.situacao !== "Cancelado"; });
    var ini = datas.reduce(function (m, p) { return p.abertura < m ? p.abertura : m; }, GI.api.referencia());
    var semanas = [], d = new Date(ini + "T00:00:00");
    d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
    var fim = new Date(GI.api.referencia() + "T00:00:00");
    while (d <= fim) { semanas.push(new Date(d)); d.setDate(d.getDate() + 7); }
    semanas.push(new Date(d));
    function iso(x) { return x.getFullYear() + "-" + String(x.getMonth() + 1).padStart(2, "0") + "-" + String(x.getDate()).padStart(2, "0"); }
    var ab = [], fe = [], sd = [];
    semanas.forEach(function (s) {
      var lim = iso(s);
      var a = datas.filter(function (p) { return p.abertura < lim; }).length;
      var f = datas.filter(function (p) { return p.situacao === "Fechado" && p.fechamento && p.fechamento < lim; }).length;
      ab.push(a); fe.push(f); sd.push(a - f);
    });
    GI.charts.line("g-burn", {
      labels: semanas.map(function (s) { return s.toLocaleDateString((GI.i18n ? GI.i18n.locale : "pt-BR"), { day: "2-digit", month: "2-digit" }); }), ariaLabel: "Itens abertos e fechados acumulados por semana",
      series: [{ label: "Abertos (acumulado)", data: ab, color: "chart-4" }, { label: "Fechados (acumulado)", data: fe, color: "chart-1" },
        { label: "Saldo em aberto", data: sd, color: "chart-2", dashed: true }]
    });
    var faixas = [["Até 7 dias", function (p) { return p.idadeDias <= 7; }], ["8 a 30 dias", function (p) { return p.idadeDias > 7 && p.idadeDias <= 30; }], ["Mais de 30 dias", function (p) { return p.idadeDias > 30; }]];
    function porCat(lista) {
      return ["A", "B", "C"].map(function (c, k) {
        return { label: "Categoria " + c, color: ["chart-2", "chart-3", "chart-4"][k], data: lista.map(function (f) { return abertos.filter(function (p) { return p.categoria === c && f(p); }).length; }) };
      });
    }
    GI.charts.bar("g-aging", { labels: faixas.map(function (f) { return f[0]; }), stacked: true, ariaLabel: "Itens abertos por tempo em aberto e categoria", series: porCat(faixas.map(function (f) { return f[1]; })) });
    var disc = DISCIPLINAS.filter(function (x) { return abertos.some(function (p) { return p.disciplina === x; }); });
    GI.charts.bar("g-disc", { labels: disc, stacked: true, horizontal: true, ariaLabel: "Itens abertos por disciplina e categoria",
      series: porCat(disc.map(function (x) { return function (p) { return p.disciplina === x; }; })) });
    var emps = Object.keys(abertos.reduce(function (m, p) { m[p.empresaId] = 1; return m; }, {}));
    GI.charts.bar("g-emp", { labels: emps.map(U.empresa), stacked: true, horizontal: true, ariaLabel: "Itens abertos por empresa e categoria",
      series: porCat(emps.map(function (e) { return function (p) { return String(p.empresaId) === e; }; })) });
    tbSis.atualizar(sistemas);
  }

  function render() { renderLista(); if (!document.getElementById("p-painel").hidden) renderPainel(); }
  function carregar() {
    return GI.api.planejamento.punch(projetoId).then(function (l) {
      itens = l;
      sistemas = Object.keys(U.mapas.sistemas).map(function (k) { return U.mapas.sistemas[k]; }).filter(function (s) { return projetoId == null || s.projetoId === projetoId; });
      render();
    });
  }

  /* ---------------- Fluxo do item ---------------- */
  function item(id) { return itens.filter(function (p) { return String(p.id) === String(id); })[0]; }
  function gravar(id, mudar, msg) {
    return GI.api.obter("punch", id).then(function (o) { mudar(o); o.historico = (o.historico || []).concat([{ data: GI.api.referencia(), situacao: o.situacao, porId: GI.api.sessaoAtual().pessoaId }]); return GI.api.salvar("punch", o); })
      .then(function () { GI.ui.toast(msg, "success"); return carregar(); });
  }
  function acoesItem(p) {
    var b = function (acao, icone, rotulo) {
      return '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-acao="' + acao + '" data-id="' + p.id + '" aria-label="' + rotulo + " " + p.codigo + '" title="' + rotulo + '">' + U.icone(icone) + "</button>";
    };
    var h = "";
    if (p.situacao === "Aberto") h += b("tratar", "refresh", "Tratar");
    if (p.situacao === "Em tratamento") h += b("enviar", "send", "Enviar p/ verificação");
    if (p.situacao === "Aguardando verificação") h += b("verificar", "eye", "Verificar");
    if (p.aberto) h += '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-acao="editar" data-id="' + p.id + '" aria-label="Editar ' + p.codigo + '">' + U.icone("edit") + "</button>" +
      '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-acao="cancelar" data-id="' + p.id + '" aria-label="Cancelar ' + p.codigo + '">' + U.icone("x") + "</button>";
    return h;
  }
  function executar(acao, id) {
    var p = item(id);
    if (acao === "tratar") return gravar(id, function (o) { o.situacao = "Em tratamento"; }, p.codigo + " em tratamento.");
    if (acao === "editar") return formItem(p);
    if (acao === "enviar") {
      return GI.form.abrir({
        titulo: "Enviar para verificação", subtitulo: p.codigo + " · " + p.descricao, textoSalvar: "Enviar",
        intro: '<p class="text-small text-muted">A evidência (foto ou documento) é obrigatória para fechar o item.</p>',
        campos: [{ id: "evidencia", rotulo: "Evidência do tratamento", tipo: "arquivo", obrigatorio: true, aceitar: ["png", "jpg", "pdf"] },
          { id: "comentario", rotulo: "O que foi feito", tipo: "textarea", obrigatorio: true, max: 300, linhas: 2 }],
        aoSalvar: function (v) {
          /* TODO: API enviar os arquivos (POST /arquivos) e gravar os ids */
          return gravar(id, function (o) { o.situacao = "Aguardando verificação"; o.evidencia = v.evidencia.map(function (a) { return a.nome; }).join(", "); o.comentarioTratamento = v.comentario; },
            p.codigo + " enviado para verificação.");
        }
      });
    }
    if (acao === "verificar") {
      var pessoas = Object.keys(U.mapas.pessoas).filter(function (k) { return Number(k) !== p.responsavelId; }).map(function (k) { return { valor: k, texto: U.mapas.pessoas[k].nome }; });
      return GI.form.abrir({
        titulo: "Verificar fechamento", subtitulo: p.codigo + " · " + p.descricao, textoSalvar: "Registrar verificação",
        intro: '<dl class="dl mb-4"><dt>Evidência</dt><dd>' + U.esc(p.evidencia || "·") + "</dd><dt>Tratamento</dt><dd>" + U.esc(p.comentarioTratamento || "·") +
          "</dd><dt>Executante</dt><dd>" + U.esc(U.pessoa(p.responsavelId)) + "</dd></dl>",
        campos: [
          { id: "resultado", rotulo: "Resultado", tipo: "select", obrigatorio: true, opcoes: [{ valor: "aprovado", texto: "Aprovado: fechar o item" }, { valor: "reprovado", texto: "Reprovado: volta para tratamento" }] },
          { id: "verificadorId", rotulo: "Verificado por", tipo: "select", obrigatorio: true, opcoes: pessoas, valor: String(GI.api.sessaoAtual().pessoaId),
            ajuda: "Precisa ser diferente do executante (segregação de funções)." },
          { id: "comentario", rotulo: "Comentário", tipo: "textarea", max: 300, linhas: 2 }
        ],
        validar: function (v) {
          var e = [];
          if (Number(v.verificadorId) === p.responsavelId) e.push({ campo: "verificadorId", msg: "O verificador não pode ser o executante." });
          if (v.resultado === "reprovado" && !v.comentario) e.push({ campo: "comentario", msg: "Explique o motivo da reprovação." });
          return e;
        },
        aoSalvar: function (v) {
          return gravar(id, function (o) {
            if (v.resultado === "aprovado") { o.situacao = "Fechado"; o.fechamento = GI.api.referencia(); o.verificadoPorId = Number(v.verificadorId); }
            else { o.situacao = "Em tratamento"; o.reprovacoes = (o.reprovacoes || 0) + 1; }
            o.comentarioVerificacao = v.comentario;
          }, v.resultado === "aprovado" ? p.codigo + " fechado." : p.codigo + " reprovado e devolvido para tratamento.");
        }
      });
    }
    if (acao === "cancelar") {
      return GI.form.abrir({
        titulo: "Cancelar item", subtitulo: p.codigo, textoSalvar: "Cancelar item", perigo: true,
        campos: [{ id: "justificativa", rotulo: "Justificativa", tipo: "textarea", obrigatorio: true, max: 300 }],
        validar: function (v) { return v.justificativa.length < 10 ? [{ campo: "justificativa", msg: "Detalhe a justificativa (mínimo de 10 caracteres)." }] : []; },
        aoSalvar: function (v) { return gravar(id, function (o) { o.situacao = "Cancelado"; o.justificativaCancelamento = v.justificativa; }, p.codigo + " cancelado."); }
      });
    }
  }

  function formItem(p) {
    if (!p && projetoId == null) { U.noProjeto("novo", "Novo item da Punch list"); return; }
    var pessoas = Object.keys(U.mapas.pessoas).map(function (k) { return { valor: k, texto: U.mapas.pessoas[k].nome }; });
    var proj = U.projeto(p ? p.projetoId : projetoId);
    var codigo = p ? p.codigo : GI.api.proximoCodigo("punch", proj.padraoPunch + "-");
    GI.form.abrir({
      titulo: p ? "Editar " + p.codigo : "Novo item da Punch list", subtitulo: codigo, tamanho: "lg",
      campos: [
        { id: "sistemaId", rotulo: "Sistema", tipo: "select", obrigatorio: true, valor: p ? p.sistemaId : "", opcoes: sistemas.map(function (s) { return { valor: s.id, texto: s.codigo + " " + s.nome }; }) },
        { id: "subsistema", rotulo: "Subsistema", tipo: "texto", obrigatorio: true, valor: p ? p.subsistema : "" },
        { id: "tag", rotulo: "TAG", tipo: "texto", obrigatorio: true, valor: p ? p.tag : "" },
        { id: "disciplina", rotulo: "Disciplina", tipo: "select", obrigatorio: true, valor: p ? p.disciplina : "", opcoes: DISCIPLINAS.map(function (d) { return { valor: d, texto: d }; }) },
        { id: "categoria", rotulo: "Categoria", tipo: "select", obrigatorio: true, valor: p ? p.categoria : "",
          opcoes: [{ valor: "A", texto: "A: impede o marco seguinte" }, { valor: "B", texto: "B: não impede a operação" }, { valor: "C", texto: "C: melhoria ou acabamento" }] },
        { id: "marco", rotulo: "Marco vinculado", tipo: "select", obrigatorio: true, valor: p ? p.marco : "", opcoes: MARCOS.map(function (m) { return { valor: m, texto: m }; }) },
        { id: "origem", rotulo: "Origem", tipo: "select", obrigatorio: true, valor: p ? p.origem : "Walkdown", opcoes: ORIGENS.map(function (o) { return { valor: o, texto: o }; }) },
        { id: "prazo", rotulo: "Prazo", tipo: "data", obrigatorio: true, valor: p ? p.prazo : "" },
        { id: "descricao", rotulo: "Descrição", tipo: "textarea", obrigatorio: true, max: 300, linhas: 2, valor: p ? p.descricao : "" },
        { id: "empresaId", rotulo: "Empresa executante", tipo: "select", obrigatorio: true, valor: p ? p.empresaId : "", opcoes: Object.keys(U.mapas.empresas).map(function (k) { return { valor: k, texto: U.mapas.empresas[k].nome }; }) },
        { id: "responsavelId", rotulo: "Responsável", tipo: "select", obrigatorio: true, valor: p ? p.responsavelId : "", opcoes: pessoas },
        { id: "identificadoPorId", rotulo: "Identificado por", tipo: "select", obrigatorio: true, valor: p ? p.identificadoPorId : String(GI.api.sessaoAtual().pessoaId), opcoes: pessoas },
        { id: "foto", rotulo: "Foto de abertura (opcional)", tipo: "arquivo", aceitar: ["png", "jpg", "pdf"] }
      ],
      aoSalvar: function (v) {
        var base = p ? GI.api.obter("punch", p.id) : Promise.resolve({ projetoId: projetoId, codigo: codigo, abertura: GI.api.referencia(), situacao: "Aberto" });
        return base.then(function (o) {
          ["subsistema", "tag", "disciplina", "categoria", "marco", "origem", "prazo", "descricao"].forEach(function (k) { o[k] = v[k]; });
          o.sistemaId = Number(v.sistemaId); o.empresaId = Number(v.empresaId); o.responsavelId = Number(v.responsavelId); o.identificadoPorId = Number(v.identificadoPorId);
          if (v.foto.length) o.fotoAbertura = v.foto[0].nome;
          return GI.api.salvar("punch", o);
        }).then(function () { GI.ui.toast(codigo + (p ? " atualizado." : " aberto; ação criada na Central."), "success"); return carregar(); });
      }
    });
  }

  function importar() {
    var nomesEmp = Object.keys(U.mapas.empresas).map(function (k) { return U.mapas.empresas[k].nome; });
    var nomesPes = Object.keys(U.mapas.pessoas).map(function (k) { return U.mapas.pessoas[k].nome; });
    var cods = sistemas.map(function (s) { return s.codigo; });
    GI.importar.abrir({
      titulo: "Importar itens da Punch list", subtitulo: "Walkdowns e listas de comissionamento", arquivoModelo: "modelo-punch-list",
      colunas: [
        { campo: "sistema", titulo: "Sistema", tipo: "lista", obrigatorio: true, opcoes: cods, exemplo: "310" },
        { campo: "subsistema", titulo: "Subsistema", tipo: "texto", obrigatorio: true, exemplo: "Tubulação" },
        { campo: "tag", titulo: "TAG", tipo: "texto", obrigatorio: true, exemplo: "310-P-030" },
        { campo: "disciplina", titulo: "Disciplina", tipo: "lista", obrigatorio: true, opcoes: DISCIPLINAS, exemplo: "Tubulação" },
        { campo: "categoria", titulo: "Categoria", tipo: "lista", obrigatorio: true, opcoes: ["A", "B", "C"], exemplo: "B" },
        { campo: "marco", titulo: "Marco", tipo: "lista", obrigatorio: true, opcoes: MARCOS, exemplo: "Aceite provisório" },
        { campo: "origem", titulo: "Origem", tipo: "lista", obrigatorio: true, opcoes: ORIGENS, exemplo: "Walkdown" },
        { campo: "descricao", titulo: "Descrição", tipo: "texto", obrigatorio: true, exemplo: "Isolamento térmico incompleto" },
        { campo: "empresa", titulo: "Empresa", tipo: "lista", obrigatorio: true, opcoes: nomesEmp, exemplo: "Alfa Montagens" },
        { campo: "responsavel", titulo: "Responsável", tipo: "lista", obrigatorio: true, opcoes: nomesPes, exemplo: "Carlos Nunes" },
        { campo: "prazo", titulo: "Prazo", tipo: "data", obrigatorio: true, exemplo: "15/10/2026" }
      ],
      aoImportar: function (linhas) {
        var proj = U.projeto(projetoId);
        return linhas.reduce(function (pr, l) {
          return pr.then(function () {
            var sis = sistemas.filter(function (s) { return s.codigo === l.sistema; })[0];
            var emp = Object.keys(U.mapas.empresas).filter(function (k) { return U.mapas.empresas[k].nome === l.empresa; })[0];
            var pes = Object.keys(U.mapas.pessoas).filter(function (k) { return U.mapas.pessoas[k].nome === l.responsavel; })[0];
            return GI.api.salvar("punch", { projetoId: projetoId, codigo: GI.api.proximoCodigo("punch", proj.padraoPunch + "-"), sistemaId: sis.id, subsistema: l.subsistema, tag: l.tag,
              disciplina: l.disciplina, categoria: l.categoria, marco: l.marco, origem: l.origem, descricao: l.descricao, empresaId: Number(emp), responsavelId: Number(pes),
              identificadoPorId: GI.api.sessaoAtual().pessoaId, abertura: GI.api.referencia(), prazo: l.prazo, situacao: "Aberto" });
          });
        }, Promise.resolve()).then(function () { carregar(); return U.plural(linhas.length, "item aberto", "itens abertos") + " e " + U.plural(linhas.length, "ação criada", "ações criadas") + " na Central."; });
      }
    });
  }

  function filtros() {
    GI.form.abrir({
      titulo: "Filtros da Punch list", tamanho: "lg", textoSalvar: "Aplicar",
      campos: [
        { id: "situacao", rotulo: "Situação", tipo: "select", vazio: "Todas", valor: filtro.situacao, opcoes: [{ valor: "abertos", texto: "Abertos (não fechados)" }].concat(SITUACOES.map(function (s) { return { valor: s, texto: s }; })) },
        { id: "categoria", rotulo: "Categoria", tipo: "select", vazio: "Todas", valor: filtro.categoria, opcoes: ["A", "B", "C"].map(function (c) { return { valor: c, texto: "Categoria " + c }; }) },
        { id: "sistemaId", rotulo: "Sistema", tipo: "select", vazio: "Todos", valor: filtro.sistemaId, opcoes: sistemas.map(function (s) { return { valor: s.id, texto: s.codigo + " " + s.nome }; }) },
        { id: "disciplina", rotulo: "Disciplina", tipo: "select", vazio: "Todas", valor: filtro.disciplina, opcoes: DISCIPLINAS.map(function (d) { return { valor: d, texto: d }; }) },
        { id: "empresaId", rotulo: "Empresa", tipo: "select", vazio: "Todas", valor: filtro.empresaId, largura: "full",
          opcoes: Object.keys(U.mapas.empresas).map(function (k) { return { valor: k, texto: U.mapas.empresas[k].nome }; }) }
      ],
      aoSalvar: function (v) { Object.keys(v).forEach(function (k) { filtro[k] = v[k]; }); renderLista(); }
    });
  }

  /* ---------------- Eventos ---------------- */
  document.getElementById("kpis").addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-filtro]"); if (!b) return;
    var v = b.getAttribute("data-filtro");
    if (v === "A") { filtro.categoria = filtro.categoria === "A" ? "" : "A"; filtro.situacao = "abertos"; }
    else { filtro.categoria = ""; filtro.situacao = filtro.situacao === v && v !== "abertos" ? "abertos" : v; }
    renderLista();
  });
  document.getElementById("chips").addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-limpar]"); if (!b) return;
    filtro[b.getAttribute("data-limpar")] = ""; if (b.getAttribute("data-limpar") === "busca") document.getElementById("busca").value = "";
    renderLista();
  });
  document.getElementById("busca").value = filtro.busca;
  document.getElementById("busca").addEventListener("input", U.debounce(function (ev) { filtro.busca = ev.target.value.trim(); renderLista(); }, 200));
  document.getElementById("btn-filtros").addEventListener("click", filtros);
  document.getElementById("btn-novo").addEventListener("click", function () { formItem(null); });
  document.getElementById("btn-importar").addEventListener("click", function () { if (projetoId == null) U.noProjeto("importar", "Importar itens da Punch list"); else importar(); });
  document.getElementById("tabela").addEventListener("click", function (ev) { var b = ev.target.closest("[data-acao]"); if (b) executar(b.getAttribute("data-acao"), b.getAttribute("data-id")); });
  document.addEventListener("tabs:change", function (ev) { if (ev.detail.id === "p-painel") renderPainel(); });

  GI.exportar.registrar(function () {
    var painel = !document.getElementById("p-painel").hidden;
    var blocos = [{ tipo: "kpis", titulo: "Indicadores", itens: Array.prototype.map.call(document.querySelectorAll("#kpis .kpi"), function (k) {
      return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" };
    }) }, { tipo: "tabela", titulo: "Itens da Punch list", dados: tabela.exportacao() }];
    if (painel) {
      blocos.push({ tipo: "grafico", titulo: "Abertura e fechamento acumulados", canvas: document.getElementById("g-burn") });
      blocos.push({ tipo: "grafico", titulo: "Tempo em aberto", canvas: document.getElementById("g-aging") });
    }
    blocos.push({ tipo: "tabela", titulo: "Sistemas e liberação por marco", dados: tbSis.exportacao() });
    return { titulo: "Punch list", subtitulo: document.getElementById("contagem").textContent, arquivo: "punch-list", blocos: blocos };
  });

  GI.util.pronto().then(function () {
    tabela = GI.tabela.criar("tabela", {
      porPagina: 15, ordem: { coluna: "codigo", direcao: "asc" }, vazio: "Nenhum item no filtro atual.", legenda: "Itens da Punch list", compacta: true,
      colunas: (projetoId == null ? [U.colunaProjeto()] : []).concat([
        { id: "codigo", titulo: "Nº / Cat.", classe: "nowrap", html: function (p) { return "<b>" + U.esc(p.codigo) + "</b><br>" + U.badge("Categoria " + p.categoria, TIPO_CAT[p.categoria]); } },
        { id: "categoria", titulo: "Categoria", oculta: true },
        { id: "sistema", titulo: "Sistema / TAG", valor: function (p) { return p.sistema ? p.sistema.codigo + " " + p.tag : p.tag; },
          html: function (p) { return '<div class="cell-title"><b>' + U.esc(p.sistema ? p.sistema.codigo + " " + p.sistema.nome : "") + "</b><small>" + U.esc(p.tag + " · " + p.disciplina) + "</small></div>"; },
          exportar: function (p) { return (p.sistema ? p.sistema.codigo + " " + p.sistema.nome + " · " : "") + p.subsistema + " · " + p.tag; } },
        { id: "disciplina", titulo: "Disciplina", oculta: true },
        { id: "descricao", titulo: "Descrição", html: function (p) { return '<div class="cell-title"><span>' + U.esc(p.descricao) + "</span><small>Marco: " + U.esc(p.marco) + " · origem " + U.esc(p.origem.toLowerCase()) + "</small></div>"; },
          exportar: function (p) { return p.descricao + " (marco " + p.marco + ", origem " + p.origem + ")"; } },
        { id: "responsavel", titulo: "Responsável", valor: function (p) { return U.pessoa(p.responsavelId); },
          html: function (p) { return U.esc(U.pessoa(p.responsavelId)) + '<br><small class="text-muted">' + U.esc(U.empresa(p.empresaId)) + "</small>"; } },
        { id: "prazo", titulo: "Prazo", tipo: "data", html: function (p) { return F.data(p.prazo) + '<br><small class="text-muted">' + (p.aberto ? "aberto há " : "tratado em ") + U.plural(p.idadeDias, "dia") + "</small>"; } },
        { id: "idadeDias", titulo: "Idade (dias)", tipo: "num", oculta: true },
        { id: "situacao", titulo: "Situação", html: function (p) { return U.badge(p.situacao, TIPO_SIT[p.situacao], true) + (p.vencido ? '<br><small class="text-muted">vencido</small>' : ""); } }
      ]),
      classeLinha: function (p) { return (p.vencido && p.categoria === "A") || (filtro.busca && p.codigo === filtro.busca) ? "is-alert" : ""; },
      acoes: acoesItem
    });
    tbSis = GI.tabela.criar("tb-sistemas", {
      porPagina: 0, legenda: "Sistemas e liberação por marco",
      colunas: (projetoId == null ? [U.colunaProjeto()] : []).concat([
        { id: "codigo", titulo: "Sistema", html: function (s) { return "<b>" + U.esc(s.codigo + " " + s.nome) + "</b>"; }, valor: function (s) { return s.codigo + " " + s.nome; } },
        { id: "area", titulo: "Área" },
        { id: "a", titulo: "A abertos", tipo: "num", valor: function (s) { return itens.filter(function (p) { return p.sistemaId === s.id && p.aberto && p.categoria === "A"; }).length; } },
        { id: "b", titulo: "B abertos", tipo: "num", valor: function (s) { return itens.filter(function (p) { return p.sistemaId === s.id && p.aberto && p.categoria === "B"; }).length; } },
        { id: "c", titulo: "C abertos", tipo: "num", valor: function (s) { return itens.filter(function (p) { return p.sistemaId === s.id && p.aberto && p.categoria === "C"; }).length; } }
      ]).concat(["Completação mecânica", "Comissionamento", "Aceite definitivo"].map(function (m) {
        return { id: "m-" + m, titulo: m, valor: function (s) { return bloqueio(s.id, m) ? "Bloqueado" : "Liberado"; },
          html: function (s) { var n = bloqueio(s.id, m); return n ? U.badge("Bloqueado (" + n + ")", "danger", true) : U.badge("Liberado", "success", true); } };
      }))
    });
    return carregar().then(function () {
      var a = U.acaoPendente();
      if (projetoId != null && a === "novo") formItem(null); else if (projetoId != null && a === "importar") importar();
    });
  });
})(window.GI = window.GI || {});
