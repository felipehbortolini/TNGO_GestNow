/* ==========================================================================
   Suprimentos > Fornecedores
   Cadastro e qualificação: situação (Qualificado, Em qualificação, Restrito,
   Bloqueado), categorias, validade da qualificação e documentos. Histórico
   de notas vindo das avaliações de contrato (03) e entrega no prazo dos
   pedidos (04). Bloqueado não é convidado nem adjudicado; Restrito ou Em
   qualificação exige justificativa na recomendação (Processos de compra).
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt, S = GI.sup;
  var SITUACOES = GI.api.suprimentos.SITUACOES_FORNECEDOR;
  var lista = [], tabela, filtro = { busca: U.param("busca") || "", situacao: "", categoria: "" };

  function passa(f) {
    if (filtro.situacao && f.situacao !== filtro.situacao) return false;
    if (filtro.categoria && f.categorias.indexOf(filtro.categoria) < 0) return false;
    return U.contem([f.nome, f.tipo, f.categorias.join(" "), f.observacao].join(" "), filtro.busca);
  }

  function render() {
    var cad = lista.filter(function (f) { return f.cadastrado; });
    var n = function (s) { return cad.filter(function (f) { return f.situacao === s; }).length; };
    var docs = cad.filter(function (f) { return !f.documentosEmDia; }).length;
    var aVencer = cad.filter(function (f) { return f.qualificacaoAVencer || f.qualificacaoVencida; }).length;
    document.getElementById("kpis").innerHTML = [
      U.kpi({ rotulo: "Cadastrados", valor: F.num(cad.length), icone: "package", cor: "primary", esperado: { rotulo: "Referência", valor: "de " + F.num(lista.length) + " empresas" }, rodape: F.num(lista.length - cad.length) + " empresas sem qualificação", filtro: { valor: "", ativo: !filtro.situacao } }),
      U.kpi({ rotulo: "Qualificados", valor: F.num(n("Qualificado")), icone: "checkCircle", cor: "success", esperado: { rotulo: "Referência", valor: "de " + F.num(cad.length) + " cadastrados" }, filtro: { valor: "Qualificado", ativo: filtro.situacao === "Qualificado" } }),
      U.kpi({ rotulo: "Em qualificação", valor: F.num(n("Em qualificação")), icone: "clock", cor: "info", esperado: { rotulo: "Referência", valor: "de " + F.num(cad.length) + " cadastrados" }, filtro: { valor: "Em qualificação", ativo: filtro.situacao === "Em qualificação" } }),
      U.kpi({ rotulo: "Restritos ou bloqueados", valor: F.num(n("Restrito") + n("Bloqueado")), icone: "lock", cor: n("Restrito") + n("Bloqueado") ? "warning" : "success",
        esperado: { rotulo: "Esperado", valor: F.num(0) }, rodape: F.num(n("Bloqueado")) + " bloqueados", filtro: { valor: "Restrito", ativo: filtro.situacao === "Restrito" } }),
      U.kpi({ rotulo: "Documentos vencidos", valor: F.num(docs), icone: "fileText", cor: docs ? "danger" : "success", esperado: { rotulo: "Esperado", valor: F.num(0) }, rodape: "certidões e certificados fora da validade" }),
      U.kpi({ rotulo: "Qualificação a vencer", valor: F.num(aVencer), icone: "calendarClock", cor: aVencer ? "warning" : "success", esperado: { rotulo: "Esperado", valor: F.num(0) }, rodape: "vencida ou vence em até 90 dias" })
    ].join("");
    tabela.atualizar(lista.filter(passa));
  }

  function carregar() {
    return GI.api.suprimentos.fornecedores().then(function (r) {
      lista = r;
      var cats = {};
      r.forEach(function (f) { f.categorias.forEach(function (c) { cats[c] = true; }); });
      var fc = document.getElementById("f-categoria");
      fc.innerHTML = U.opcoes(Object.keys(cats).sort(), filtro.categoria, "Todas as categorias");
      render();
    });
  }

  function camposDocs(docs) {
    return (docs || []).map(function (d, i) {
      return { id: "doc" + i, rotulo: d.nome, tipo: "data", valor: d.validade, ajuda: d.vencido ? "Vencido" : d.aVencer ? "Vence em até 30 dias" : "" };
    });
  }
  function lerDocs(docs, v) { return (docs || []).map(function (d, i) { return { nome: d.nome, validade: v["doc" + i] || null }; }); }

  function qualificar(f) {
    var docs = f.documentos && f.documentos.length ? f.documentos : [{ nome: "Certidão negativa de débitos federais" }, { nome: "Certidão negativa de débitos trabalhistas" }, { nome: "Certificado de regularidade do FGTS" }];
    GI.form.abrir({
      titulo: "Atualizar qualificação", subtitulo: f.nome + " · " + f.tipo, tamanho: "lg",
      campos: [
        { id: "situacao", rotulo: "Situação", tipo: "select", obrigatorio: true, opcoes: SITUACOES, valor: f.cadastrado ? f.situacao : "Em qualificação" },
        { id: "validade", rotulo: "Validade da qualificação", tipo: "data", valor: f.validadeQualificacao },
        { id: "categorias", rotulo: "Categorias atendidas (separadas por vírgula)", tipo: "texto", obrigatorio: true, max: 160, largura: "full", valor: f.categorias.join(", ") },
        { id: "info", rotulo: "Documentos (validade)", tipo: "info", html: '<span class="text-small text-muted">Documento vencido deixa o fornecedor com pendência no cadastro.</span>' }
      ].concat(camposDocs(docs)).concat([
        { id: "observacao", rotulo: "Observação", tipo: "textarea", max: 300, valor: f.observacao },
        { id: "justificativa", rotulo: "Justificativa da mudança de situação", tipo: "textarea", max: 300, mostrarSe: function (v) { return f.cadastrado && v.situacao !== f.situacao; } }
      ]),
      aoSalvar: function (v) {
        return GI.api.suprimentos.salvarQualificacao(f.empresaId, { situacao: v.situacao, validade: v.validade, observacao: v.observacao, justificativa: v.justificativa,
          categorias: v.categorias.split(",").map(function (c) { return c.trim(); }).filter(Boolean), documentos: lerDocs(docs, v) }).then(function () {
          GI.ui.toast("Qualificação de " + f.nome + " atualizada.", "success");
          return carregar();
        });
      }
    });
  }

  function novo() {
    var docs = [{ nome: "Certidão negativa de débitos federais" }, { nome: "Certidão negativa de débitos trabalhistas" }, { nome: "Certificado de regularidade do FGTS" }];
    GI.form.abrir({
      titulo: "Novo fornecedor", subtitulo: "Entra como Em qualificação até a análise de documentos e capacidade técnica",
      campos: [
        { id: "nome", rotulo: "Razão social ou nome fantasia", tipo: "texto", obrigatorio: true, max: 80, largura: "full" },
        { id: "tipo", rotulo: "Tipo", tipo: "select", obrigatorio: true, opcoes: ["Fornecedor", "Contratada"], valor: "Fornecedor" },
        { id: "categorias", rotulo: "Categorias atendidas (separadas por vírgula)", tipo: "texto", obrigatorio: true, max: 160, largura: "full" }
      ].concat(camposDocs(docs)).concat([{ id: "observacao", rotulo: "Observação", tipo: "textarea", max: 300 }]),
      aoSalvar: function (v) {
        return GI.api.suprimentos.novoFornecedor({ nome: v.nome, tipo: v.tipo, observacao: v.observacao, documentos: lerDocs(docs, v),
          categorias: v.categorias.split(",").map(function (c) { return c.trim(); }).filter(Boolean) }).then(function () {
          GI.ui.toast(v.nome + " cadastrado em qualificação.", "success");
          return GI.util.pronto().then(carregar);
        });
      }
    });
  }

  function historico(f) {
    var aval = f.avaliacoes.slice().reverse();
    var corpo = document.createElement("div");
    function tab(cab, linhas, vazio) {
      return linhas.length ? '<div class="table-wrap"><table class="table table--compact"><thead><tr>' + cab.map(function (c) { return '<th scope="col">' + U.esc(c) + "</th>"; }).join("") +
        "</tr></thead><tbody>" + linhas.map(function (l) { return "<tr>" + l.map(function (c) { return "<td>" + c + "</td>"; }).join("") + "</tr>"; }).join("") + "</tbody></table></div>" : U.vazio(vazio, "search");
    }
    corpo.innerHTML = '<dl class="dl"><dt>Situação</dt><dd>' + S.fornecedor(f.situacao) + "</dd><dt>Nota média</dt><dd>" + (f.notaMedia == null ? "·" : U.esc(F.num(f.notaMedia, 1))) +
      "</dd><dt>Entrega no prazo</dt><dd>" + (f.otdPct == null ? "·" : U.esc(F.pct(f.otdPct) + " de " + f.entregas + " entregas")) + "</dd><dt>Valor contratado</dt><dd>" + U.esc(F.moeda(f.valorContratadoCentavos)) + "</dd></dl>" +
      '<div class="mt-6"><h3 class="section-title">Avaliações de desempenho (03 Contratos)</h3></div>' +
      tab(["Período", "Contrato", "Tipo", "Nota", "Classe"], aval.map(function (a) {
        return [U.esc(U.mesCurto(a.periodo)), S.linkContrato(a.contrato), U.esc(a.tipo), "<b>" + F.num(a.nota) + "</b>", GI.util.badge("Classe " + a.classe, { A: "success", B: "primary", C: "warning", D: "danger" }[a.classe] || "neutral")];
      }), "Sem avaliações de contrato para esta empresa.") +
      '<div class="mt-6"><h3 class="section-title">Pedidos e contratos</h3></div>' +
      tab(["Número", "Objeto", "Valor", "Data contratual", "Entrega"], f.pedidos.map(function (p) {
        var atraso = p.entrega && p.entrega > p.dataContratual;
        return [S.linkPedido(p.numero), U.esc(p.descricao), U.esc(F.moeda(p.valorCentavos)), U.esc(F.data(p.dataContratual)),
          p.entrega ? '<span class="' + (atraso ? "valor--negativo" : "valor--positivo") + '">' + U.esc(F.data(p.entrega)) + "</span>" : '<span class="text-muted">em aberto</span>'];
      }).concat(f.contratos.map(function (c) { return [S.linkContrato(c.numero), U.esc(c.objeto), U.esc(F.moeda(c.valorCentavos)), "", '<span class="text-muted">contrato</span>']; })), "Sem pedidos nem contratos.") +
      '<div class="mt-6"><h3 class="section-title">Histórico da qualificação</h3></div>' +
      tab(["Data", "De", "Para", "Por", "Justificativa"], (f.historico || []).slice().reverse().map(function (h) {
        return [U.esc(F.data(h.data)), U.esc(h.de || "·"), U.esc(h.para), U.esc(U.pessoa(h.porId)), U.esc(h.justificativa)];
      }), "Sem mudanças de situação registradas.");
    GI.modal.create({ title: f.nome, subtitle: "Desempenho e histórico", size: "xl", body: corpo, buttons: [{ label: "Fechar", variant: "secondary" }] });
  }

  GI.exportar.registrar(function () {
    return { titulo: "Fornecedores", subtitulo: "Qualificação e desempenho", arquivo: "fornecedores", orientacao: "l",
      blocos: [{ tipo: "kpis", titulo: "Indicadores", itens: S.kpisExport() }, { tipo: "tabela", titulo: "Fornecedores e contratadas", dados: tabela.exportacao() }] };
  });

  GI.util.pronto().then(function () {
    var busca = document.getElementById("busca");
    busca.value = filtro.busca;
    busca.addEventListener("input", U.debounce(function () { filtro.busca = busca.value.trim(); render(); }, 200));
    var fs = document.getElementById("f-situacao");
    fs.innerHTML = U.opcoes(SITUACOES.concat(["Sem qualificação"]), "", "Todas as situações");
    fs.addEventListener("change", function () { filtro.situacao = fs.value; render(); });
    document.getElementById("f-categoria").addEventListener("change", function (ev) { filtro.categoria = ev.target.value; render(); });
    document.getElementById("btn-novo").addEventListener("click", novo);
    document.getElementById("btn-colunas").addEventListener("click", function () { GI.tabela.escolherColunas(tabela); });
    document.getElementById("kpis").addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-filtro]"); if (!b) return;
      filtro.situacao = filtro.situacao === b.getAttribute("data-filtro") ? "" : b.getAttribute("data-filtro"); fs.value = filtro.situacao; render();
    });

    tabela = GI.tabela.criar("tabela", {
      porPagina: 20, legenda: "Fornecedores e contratadas", vazio: "Nenhum fornecedor encontrado.", ordem: { coluna: "nome", direcao: "asc" },
      colunas: [
        { id: "nome", titulo: "Empresa", fixa: true, html: function (f) { return '<div class="cell-title"><b>' + U.esc(f.nome) + "</b><small>" + U.esc(f.tipo) + "</small></div>"; } },
        { id: "categorias", titulo: "Categorias", valor: function (f) { return f.categorias.join(", "); } },
        { id: "situacao", titulo: "Situação", html: function (f) { return S.fornecedor(f.situacao) + (f.observacao ? '<br><span class="text-small text-muted">' + U.esc(f.observacao) + "</span>" : ""); },
          exportar: function (f) { return f.situacao + (f.observacao ? " · " + f.observacao : ""); } },
        { id: "validadeQualificacao", titulo: "Validade", tipo: "data",
          html: function (f) { return f.validadeQualificacao ? U.esc(F.data(f.validadeQualificacao)) + (f.qualificacaoVencida ? '<br><span class="text-small valor--negativo">vencida</span>' : f.qualificacaoAVencer ? '<br><span class="text-small valor--negativo">vence em até 90 dias</span>' : "") : ""; } },
        { id: "documentos", titulo: "Documentos", valor: function (f) { return f.documentosEmDia ? "Válidos" : "Documentos vencidos"; },
          html: function (f) {
            if (!f.cadastrado) return "";
            var venc = f.documentos.filter(function (d) { return d.vencido; });
            return venc.length ? U.badge(U.plural(venc.length, "vencido", "vencidos"), "danger", true) + '<br><span class="text-small text-muted">' + U.esc(venc.map(function (d) { return d.nome; }).join(", ")) + "</span>" : U.badge("Válidos", "success", true);
          } },
        { id: "nota", titulo: "Desempenho", valor: function (f) { return f.ultimaAvaliacao ? f.ultimaAvaliacao.nota : f.otdPct; },
          html: function (f) {
            var h = [];
            if (f.ultimaAvaliacao) h.push(GI.util.badge("Classe " + f.ultimaAvaliacao.classe, { A: "success", B: "primary", C: "warning", D: "danger" }[f.ultimaAvaliacao.classe] || "neutral") + ' <span class="num">' + F.num(f.ultimaAvaliacao.nota) + "</span>");
            if (f.otdPct != null) h.push('<span class="text-small">OTD ' + U.esc(F.pct(f.otdPct)) + "</span>");
            return h.join("<br>");
          },
          exportar: function (f) { return [f.ultimaAvaliacao ? "Classe " + f.ultimaAvaliacao.classe + " (" + f.ultimaAvaliacao.nota + ")" : "", f.otdPct != null ? "OTD " + F.pct(f.otdPct) : ""].filter(Boolean).join(" · "); } },
        { id: "valorContratadoCentavos", titulo: "Valor contratado", tipo: "moeda" },
        { id: "participacoes", titulo: "Propostas em RFx", tipo: "num", oculta: true }
      ],
      classeLinha: function (f) { return f.situacao === "Bloqueado" || !f.documentosEmDia && f.cadastrado ? "is-alert" : ""; },
      acoes: function (f) {
        return '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-qualificar="' + f.empresaId + '" aria-label="Atualizar qualificação de ' + U.esc(f.nome) + '" title="Atualizar qualificação">' + U.icone("edit") + "</button>" +
          '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-historico="' + f.empresaId + '" aria-label="Desempenho e histórico de ' + U.esc(f.nome) + '" title="Desempenho e histórico">' + U.icone("history") + "</button>";
      }
    });
    document.getElementById("tabela").addEventListener("click", function (ev) {
      var q = ev.target.closest("[data-qualificar]"), h = ev.target.closest("[data-historico]");
      var id = q ? q.getAttribute("data-qualificar") : h ? h.getAttribute("data-historico") : null;
      if (!id) return;
      var f = lista.filter(function (x) { return String(x.empresaId) === id; })[0];
      if (q) qualificar(f); else historico(f);
    });
    return carregar();
  });
})(window.GI = window.GI || {});
