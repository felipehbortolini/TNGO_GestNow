/* ==========================================================================
   Planejamento > Relato do período (02)
   Registro semanal e registro mensal (distintos) por período, com atividades do
   período, atividades do próximo período e pontos de atenção, cada ponto com o
   risco atrelado (ameaça ou oportunidade), sem vínculo com o 05 Gestão de Riscos.
   Alimenta a página 2 do Planejamento no relatório gerencial (Início).
   Tudo em modais: novo, editar, ver e excluir. URL: ?tipo=&periodo=&abrir=1
   (abre o relato do período ou o cadastro dele, vindo do relatório gerencial).
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt, API = GI.api.planejamento;
  var projetoId = GI.api.projetoAtualId();
  var PF = projetoId == null;   /* Portfólio: relatos de todos os projetos (registro sempre num projeto) */
  var filtro = { tipo: U.param("tipo") || "", busca: "" };
  var lista = [], tabela = null, periodos = { Semanal: [], Mensal: [] }, resumo = null;
  var relatosPrevistos = null;   /* períodos já encerrados desde o início de cada projeto (semanais + mensais) */

  function erroApi(e) { GI.ui.toast((e && e.erros ? e.erros.map(function (x) { return x.msg || x; }).join(" ") : String(e)), "warning", 7000); }
  function seloTipo(t) { return U.badge(t, t === "Mensal" ? "purple" : "info"); }
  function seloNatureza(n) { return U.badge(n, n === "Oportunidade" ? "success" : "warning", true); }
  function porId(id) { return lista.filter(function (r) { return String(r.id) === String(id); })[0] || null; }
  function linhas(texto) { return String(texto || "").split(/\r?\n/).map(function (t) { return t.trim(); }).filter(Boolean); }
  function quando(r) { return r.atualizadoEm ? F.data(r.atualizadoEm.slice(0, 10)) + " " + r.atualizadoEm.slice(11, 16) : ""; }

  /* ---------------- KPIs ---------------- */
  function renderKpis() {
    var s = resumo, u = s.ultimoSemanal;
    function kPeriodo(rotulo, x, icone) {
      if (PF) {
        var n = U.listaProjetos().length, reg = U.listaProjetos().filter(function (p) { return lista.some(function (r) { return r.projetoId === p.id && r.tipo === x.info.tipo && r.periodo === x.info.periodo; }); }).length;
        return U.kpi({ rotulo: rotulo, valor: F.num(reg), icone: icone, cor: reg === n ? "success" : "warning", esperado: { rotulo: "Esperado", valor: F.num(n) }, rodape: U.esc(x.info.rotulo) + " · projetos com relato" });
      }
      return U.kpi({ rotulo: rotulo, valor: x.registrado ? "Registrado" : "Pendente", icone: icone, cor: x.registrado ? "success" : "warning", esperado: { rotulo: "Esperado", valor: "Registrado" }, rodape: U.esc(x.info.rotulo) });
    }
    /* Referência dos pontos de atenção: relato semanal anterior do mesmo projeto */
    var uAnt = u ? lista.filter(function (r) { return r.tipo === "Semanal" && r.projetoId === u.projetoId && r.periodo < u.periodo; })
      .sort(function (a, b) { return a.periodo < b.periodo ? 1 : -1; })[0] : null;
    document.getElementById("kpis").innerHTML = [
      kPeriodo("Semana anterior", s.semanaAnterior, "calendarDays"),
      kPeriodo("Mês anterior", s.mesAnterior, "calendar"),
      U.kpi({ rotulo: "Pontos de atenção (último semanal)", valor: u ? F.num(u.pontos.length) : "·", icone: "flag", cor: u && u.ameacas ? "warning" : "info",
        esperado: { rotulo: "Referência", valor: uAnt && uAnt.pontos ? F.num(uAnt.pontos.length) : "·" },
        rodape: u ? U.plural(u.ameacas, "ameaça") + " · " + U.plural(u.oportunidades, "oportunidade") + " · " + U.esc(u.info.rotuloCurto) : "nenhum relato semanal" }),
      U.kpi({ rotulo: "Relatos registrados", valor: F.num(s.total), icone: "fileText", cor: "primary",
        esperado: { rotulo: "Previsto", valor: relatosPrevistos == null ? "·" : F.num(relatosPrevistos) }, rodape: U.plural(s.semanais, "semanal", "semanais") + " · " + U.plural(s.mensais, "mensal", "mensais") })
    ].join("");
  }

  /* ---------------- Tabela ---------------- */
  function passa(r) {
    if (filtro.tipo && r.tipo !== filtro.tipo) return false;
    if (!filtro.busca) return true;
    var alvo = [r.info.rotulo, U.codigoProjeto(r.projetoId)].concat(r.atividadesPeriodo, r.atividadesProximo, r.pontos.map(function (p) { return p.descricao + " " + p.natureza + " " + p.risco; })).join(" ");
    return U.contem(alvo, filtro.busca);
  }
  function render() { tabela.atualizar(lista.filter(passa)); }
  function montarTabela() {
    tabela = GI.tabela.criar("tabela", {
      porPagina: 15, legenda: "Relatos do período", vazio: "Nenhum relato encontrado.", ordem: { coluna: "periodo", direcao: "desc" },
      colunas: (PF ? [U.colunaProjeto()] : []).concat([
        { id: "periodo", titulo: "Período", valor: function (r) { return r.info.inicio + (r.tipo === "Mensal" ? "0" : "1"); },
          html: function (r) { return '<div class="cell-title"><a href="#" data-ver="' + r.id + '"><b>' + U.esc(r.info.rotulo) + "</b></a><small>" + seloTipo(r.tipo) + "</small></div>"; },
          exportar: function (r) { return r.tipo + " · " + r.info.rotulo; } },
        { id: "atividades", titulo: "Atividades do período", tipo: "num", valor: function (r) { return r.atividadesPeriodo.length; } },
        { id: "proximo", titulo: "Próximo período", tipo: "num", valor: function (r) { return r.atividadesProximo.length; } },
        { id: "pontos", titulo: "Pontos de atenção", tipo: "num", valor: function (r) { return r.pontos.length; },
          html: function (r) {
            return F.num(r.pontos.length) + (r.pontos.length ? ' <span class="text-small text-muted">(' + U.esc(U.plural(r.ameacas, "ameaça") + " · " + U.plural(r.oportunidades, "oportunidade")) + ")</span>" : "");
          },
          exportar: function (r) { return r.pontos.length + " (" + r.ameacas + " ameaças, " + r.oportunidades + " oportunidades)"; } },
        { id: "atualizado", titulo: "Atualizado", valor: function (r) { return r.atualizadoEm || ""; },
          html: function (r) { return '<div class="cell-title"><span>' + U.esc(quando(r)) + "</span><small>" + U.esc(U.pessoa(r.atualizadoPorId)) + "</small></div>"; },
          exportar: function (r) { return quando(r) + " · " + U.pessoa(r.atualizadoPorId); } }
      ]),
      acoes: function (r) {
        return '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-ver="' + r.id + '" aria-label="Ver relato ' + U.esc(r.info.rotulo) + '" title="Ver">' + U.icone("eye") + "</button>" +
          '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-editar="' + r.id + '" aria-label="Editar relato ' + U.esc(r.info.rotulo) + '" title="Editar">' + U.icone("edit") + "</button>" +
          (API.pode("Gestor") ? '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-excluir="' + r.id + '" aria-label="Excluir relato ' + U.esc(r.info.rotulo) + '" title="Excluir">' + U.icone("trash") + "</button>" : "");
      }
    });
  }

  function carregar() {
    return Promise.all([API.relatos(projetoId), API.periodosRelato(projetoId, "Semanal"), API.periodosRelato(projetoId, "Mensal"), API.resumoRelatos(projetoId)]).then(function (r) {
      lista = r[0]; periodos.Semanal = r[1]; periodos.Mensal = r[2]; resumo = r[3];
      return contarPrevistos();
    }).then(function () { renderKpis(); render(); });
  }

  /* Relatos previstos: períodos encerrados (exclui o período corrente) de cada tipo, por projeto */
  function contarPrevistos() {
    var ids = PF ? U.listaProjetos().map(function (p) { return p.id; }) : [projetoId];
    var pedidos = [];
    ids.forEach(function (id) { ["Semanal", "Mensal"].forEach(function (t) { pedidos.push(API.periodosRelato(id, t)); }); });
    return Promise.all(pedidos).then(function (r) {
      relatosPrevistos = r.reduce(function (t, l) { return t + Math.max(0, (l || []).length - 1); }, 0);
    });
  }

  /* ---------------- Modal: ver ---------------- */
  function htmlRelato(r) {
    function listaHtml(itens) { return itens.length ? '<ul class="relato-lista">' + itens.map(function (t) { return "<li>" + U.esc(t) + "</li>"; }).join("") + "</ul>" : '<p class="text-muted">Sem registro.</p>'; }
    var pontos = r.pontos.length ? '<div class="table-wrap"><table class="table table--compact"><caption class="sr-only">Pontos de atenção e riscos atrelados</caption><thead><tr><th scope="col">Ponto de atenção</th><th scope="col">Risco atrelado</th></tr></thead><tbody>' +
      r.pontos.map(function (p) { return "<tr><td>" + U.esc(p.descricao) + "</td><td>" + seloNatureza(p.natureza) + "<br>" + U.esc(p.risco) + "</td></tr>"; }).join("") + "</tbody></table></div>"
      : '<p class="text-muted">Nenhum ponto de atenção no período.</p>';
    return '<div class="relato-bloco"><h3 class="relato-bloco__titulo">Atividades do período</h3>' + listaHtml(r.atividadesPeriodo) + "</div>" +
      '<div class="relato-bloco"><h3 class="relato-bloco__titulo">Atividades do próximo período</h3><p class="text-small text-muted mb-2">' + U.esc(r.proximo ? r.proximo.rotulo : "") + "</p>" + listaHtml(r.atividadesProximo) + "</div>" +
      '<div class="relato-bloco"><h3 class="relato-bloco__titulo">Pontos de atenção e riscos (ameaça e oportunidade)</h3>' + pontos + "</div>" +
      '<p class="text-small text-muted mt-4">Atualizado em ' + U.esc(quando(r)) + " por " + U.esc(U.pessoa(r.atualizadoPorId)) + ". O risco atrelado é a leitura do planejamento e não entra no registro do 05 Gestão de Riscos.</p>";
  }
  function ver(id) {
    var r = porId(id);
    if (!r) return;
    GI.modal.create({
      title: "Relato " + r.tipo.toLowerCase() + " · " + r.info.rotulo, subtitle: (function (pj) { return pj.codigo ? pj.codigo + " · " + pj.nome : ""; })(U.projeto(r.projetoId) || {}), size: "lg", body: htmlRelato(r),
      buttons: [{ label: "Fechar", variant: "secondary" }, { label: "Editar", variant: "primary", onClick: function (api) { api.close(); editar(r); } }]
    });
  }

  /* ---------------- Modal: novo e editar ---------------- */
  function opcoesPeriodo(tipo, atual) {
    return (periodos[tipo] || []).map(function (p) {
      var ocupado = p.relatoId && p.periodo !== atual;
      return '<option value="' + U.esc(p.periodo) + '"' + (p.periodo === atual ? " selected" : "") + (ocupado ? " disabled" : "") + ">" +
        U.esc(p.rotulo + (p.emAndamento ? " (em andamento)" : "") + (ocupado ? " (já registrado)" : "")) + "</option>";
    }).join("");
  }
  /* Sugestão: o período mais recente ainda sem relato (o corrente, se estiver livre) */
  function primeiroLivre(tipo) {
    var l = (periodos[tipo] || []).filter(function (p) { return !p.relatoId; });
    return l[0] ? l[0].periodo : "";
  }
  function relatoAnterior(tipo, periodo, pid) {
    var todos = lista.filter(function (r) { return r.tipo === tipo && r.periodo < periodo && (pid == null || r.projetoId === pid); }).sort(function (a, b) { return a.periodo < b.periodo ? 1 : -1; });
    return todos[0] || null;
  }
  function editar(r, padrao) {
    if (!r && PF) { U.noProjeto("novo", "Novo relato do período"); return; }
    var novo = !r, p = padrao || {};
    var pidRelato = r ? r.projetoId : projetoId;
    if (novo && !API.pode("Membro")) { GI.ui.toast("Seu papel não permite registrar o relato do período.", "warning"); return; }
    var tipoIni = novo ? (p.tipo || filtro.tipo || "Semanal") : r.tipo;
    var periodoIni = novo ? (p.periodo && !(periodos[tipoIni] || []).some(function (x) { return x.periodo === p.periodo && x.relatoId; }) ? p.periodo : primeiroLivre(tipoIni)) : r.periodo;
    var ultimoTipo = tipoIni;
    var campos = [];
    if (novo) {
      campos.push({ id: "tipo", rotulo: "Tipo", tipo: "escolha", obrigatorio: true, valor: tipoIni, opcoes: API.TIPOS_RELATO.map(function (t) { return { valor: t, texto: t, sub: t === "Semanal" ? "semana ISO, segunda a domingo" : "mês civil" }; }) });
      campos.push({ id: "periodo", rotulo: "Período", tipo: "select", obrigatorio: true, opcoes: [], valor: periodoIni });
    } else {
      campos.push({ id: "ident", rotulo: "Período", tipo: "info", html: seloTipo(r.tipo) + " <b>" + U.esc(r.info.rotulo) + "</b>" });
    }
    campos.push(
      { id: "atividadesPeriodo", rotulo: "Atividades do período", tipo: "textarea", obrigatorio: true, linhas: 5, valor: novo ? "" : r.atividadesPeriodo.join("\n"),
        ajuda: "Uma atividade por linha (até " + API.LIMITES_RELATO.itens + " linhas de " + API.LIMITES_RELATO.textoItem + " caracteres)." },
      { id: "atividadesProximo", rotulo: "Atividades do próximo período", tipo: "textarea", obrigatorio: true, linhas: 5, valor: novo ? "" : r.atividadesProximo.join("\n"),
        ajuda: "Uma atividade por linha." },
      { id: "pontos", rotulo: "Pontos de atenção e riscos (ameaça e oportunidade)", tipo: "repetir", rotuloItem: "Ponto de atenção", textoAdicionar: "Adicionar ponto de atenção",
        maximo: API.LIMITES_RELATO.pontos, vazio: "Nenhum ponto de atenção no período. Use o botão abaixo para incluir.",
        valor: novo ? [{}] : r.pontos.map(function (x) { return { descricao: x.descricao, natureza: x.natureza, risco: x.risco }; }),
        itens: [
          { id: "descricao", rotulo: "Ponto de atenção", tipo: "textarea", obrigatorio: true, linhas: 2, max: API.LIMITES_RELATO.textoPonto },
          { id: "natureza", rotulo: "Risco atrelado", tipo: "escolha", obrigatorio: true, largura: "full",
            opcoes: API.NATUREZAS_RELATO.map(function (n) { return { valor: n, texto: n }; }) },
          { id: "risco", rotulo: "Descrição do risco", tipo: "textarea", obrigatorio: true, linhas: 2, max: API.LIMITES_RELATO.textoPonto,
            placeholder: "Causa, evento e efeito no projeto (prazo, custo, escopo ou qualidade)" }
        ] }
    );
    var m = GI.form.abrir({
      titulo: novo ? "Novo relato do período" : "Editar relato " + r.tipo.toLowerCase(),
      subtitulo: novo ? "Um registro por tipo e período: o semanal e o mensal são distintos" : r.info.rotulo,
      tamanho: "lg", textoSalvar: novo ? "Registrar relato" : "Salvar alterações",
      intro: '<p class="text-small text-muted">O risco de cada ponto de atenção é a leitura do planejamento e não tem vínculo com o registro do 05 Gestão de Riscos. Para tratá-lo formalmente, registre-o também no 05.</p>',
      campos: campos,
      extras: [{ texto: "Copiar do período anterior", variante: "ghost", acao: function (ctx) {
        var v = ctx.ler(), tipo = novo ? v.tipo : r.tipo, periodo = novo ? v.periodo : r.periodo;
        var ant = tipo && periodo ? relatoAnterior(tipo, periodo, pidRelato) : null;
        if (!ant) { GI.ui.toast("Não há relato " + (tipo || "").toLowerCase() + " anterior para copiar.", "info"); return; }
        ctx.definir({ atividadesPeriodo: ant.atividadesProximo.join("\n"), pontos: ant.pontos.map(function (x) { return { descricao: x.descricao, natureza: x.natureza, risco: x.risco }; }) });
        GI.ui.toast("Copiado de " + ant.info.rotulo + ": próximo período virou atividades do período e os pontos de atenção foram trazidos para revisão.", "info", 6000);
      } }],
      aoMudar: function (v) {
        if (!novo || !m) return;
        var sel = m.el.querySelector('[data-campo="periodo"] select');
        if (!sel) return;
        if (!sel.options.length || v.tipo !== ultimoTipo) {
          var alvo = sel.options.length ? primeiroLivre(v.tipo) : periodoIni;
          ultimoTipo = v.tipo;
          sel.innerHTML = opcoesPeriodo(v.tipo || "Semanal", alvo);
        }
      },
      validar: function (v) {
        var e = [];
        if (linhas(v.atividadesPeriodo).length > API.LIMITES_RELATO.itens) e.push({ campo: "atividadesPeriodo", msg: "No máximo " + API.LIMITES_RELATO.itens + " linhas." });
        if (linhas(v.atividadesProximo).length > API.LIMITES_RELATO.itens) e.push({ campo: "atividadesProximo", msg: "No máximo " + API.LIMITES_RELATO.itens + " linhas." });
        return e;
      },
      aoSalvar: function (v) {
        var d = { id: novo ? null : r.id, tipo: novo ? v.tipo : r.tipo, periodo: novo ? v.periodo : r.periodo,
          atividadesPeriodo: linhas(v.atividadesPeriodo), atividadesProximo: linhas(v.atividadesProximo), pontos: v.pontos || [] };
        return API.salvarRelato(pidRelato, d).then(function (x) {
          GI.ui.toast("Relato " + x.tipo.toLowerCase() + " de " + x.info.rotulo + (novo ? " registrado." : " atualizado."), "success");
          return carregar();
        });
      }
    });
    /* primeira carga das opções de período (o aoMudar inicial roda antes de m existir) */
    var sel = m.el.querySelector('[data-campo="periodo"] select');
    if (sel) sel.innerHTML = opcoesPeriodo(tipoIni, periodoIni);
  }

  /* ---------------- Excluir ---------------- */
  function excluir(id) {
    var r = porId(id);
    if (!r) return;
    GI.modal.confirm({ title: "Excluir relato", message: "Excluir o relato " + r.tipo.toLowerCase() + " de " + r.info.rotulo + "? O período volta a ficar pendente e sai da página 2 do Planejamento no relatório gerencial.",
      okText: "Excluir", danger: true }).then(function (ok) {
      if (!ok) return;
      API.excluirRelato(r.id).then(function () { GI.ui.toast("Relato excluído.", "success"); carregar(); }).catch(erroApi);
    });
  }

  /* ---------------- Eventos ---------------- */
  document.getElementById("btn-novo").addEventListener("click", function () { editar(null); });
  document.getElementById("tabela").addEventListener("click", function (ev) {
    var v = ev.target.closest("[data-ver]"), e = ev.target.closest("[data-editar]"), x = ev.target.closest("[data-excluir]");
    if (v) { ev.preventDefault(); ver(v.getAttribute("data-ver")); }
    else if (e) editar(porId(e.getAttribute("data-editar")));
    else if (x) excluir(x.getAttribute("data-excluir"));
  });
  document.getElementById("f-tipo").addEventListener("segmented:change", function (ev) { filtro.tipo = ev.detail.value; render(); });
  document.getElementById("busca").addEventListener("input", U.debounce(function (ev) { filtro.busca = ev.target.value.trim(); render(); }, 200));

  GI.exportar.registrar(function () {
    var vis = lista.filter(passa), p = U.projeto(projetoId) || { codigo: "Portfólio", nome: "de projetos" };
    var cp = function (r) { return PF ? [U.codigoProjeto(r.projetoId)] : []; };
    var linhasPontos = [];
    vis.forEach(function (r) { r.pontos.forEach(function (x) { linhasPontos.push(cp(r).concat([r.tipo, r.info.rotulo, x.descricao, x.natureza, x.risco])); }); });
    var linhasAtv = [];
    vis.forEach(function (r) {
      r.atividadesPeriodo.forEach(function (t) { linhasAtv.push(cp(r).concat([r.tipo, r.info.rotulo, "Atividades do período", t])); });
      r.atividadesProximo.forEach(function (t) { linhasAtv.push(cp(r).concat([r.tipo, r.info.rotulo, "Atividades do próximo período", t])); });
    });
    var colP = PF ? [{ titulo: "Projeto" }] : [];
    return {
      titulo: "Relato do período", subtitulo: (p.codigo || "") + " " + (p.nome || ""), arquivo: "relato-do-periodo", orientacao: "l",
      blocos: [
        { tipo: "kpis", titulo: "Situação", itens: Array.prototype.map.call(document.querySelectorAll("#kpis .kpi"), function (k) {
            return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" };
          }) },
        { tipo: "tabela", titulo: "Relatos registrados", dados: tabela.exportacao() },
        { tipo: "tabela", titulo: "Atividades", dados: { colunas: colP.concat([{ titulo: "Tipo" }, { titulo: "Período" }, { titulo: "Campo" }, { titulo: "Atividade" }]), bruto: linhasAtv, texto: linhasAtv } },
        { tipo: "tabela", titulo: "Pontos de atenção e riscos", dados: { colunas: colP.concat([{ titulo: "Tipo" }, { titulo: "Período" }, { titulo: "Ponto de atenção" }, { titulo: "Natureza do risco" }, { titulo: "Risco atrelado" }]), bruto: linhasPontos, texto: linhasPontos } }
      ]
    };
  });

  GI.util.pronto().then(function () {
    if (filtro.tipo) {
      Array.prototype.forEach.call(document.querySelectorAll("#f-tipo .segmented__opt"), function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-value") === filtro.tipo)); });
    }
    montarTabela();
    return carregar().then(function () {
      if (U.param("abrir") !== "1") return;
      var tipo = U.param("tipo"), periodo = U.param("periodo");
      var r = lista.filter(function (x) { return x.tipo === tipo && x.periodo === periodo; })[0];
      if (r) ver(r.id); else editar(null, { tipo: tipo, periodo: periodo });
    }).then(function () { if (U.acaoPendente() === "novo" && !PF) editar(null); });
  }).catch(function (e) { GI.ui.toast("Não foi possível carregar os relatos.", "danger"); if (window.console) console.error(e); });
})(window.GI = window.GI || {});
