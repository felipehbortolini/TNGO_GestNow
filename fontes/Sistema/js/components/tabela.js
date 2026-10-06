/* ==========================================================================
   tabela.js | Tabela padrão: ordenação, paginação, linhas destacadas,
   empilhamento no mobile (data-label), colunas visíveis e dados para exportar.

   var t = GI.tabela.criar(elemento, {
     colunas: [{ id, titulo, tipo: "texto"|"moeda"|"data"|"num"|"pct"|"indice",
                 valor: fn(linha) -> valor bruto (ordena e exporta),
                 html: fn(linha) -> HTML exibido (opcional),
                 exportar: fn(linha) -> texto (opcional), casas, classe, ordenavel (padrão true),
                 oculta (começa escondida), fixa (não pode ser escondida) }],
     linhas: [], porPagina: 20 (0 = tudo), ordem: { coluna, direcao: "asc"|"desc" },
     vazio: "texto", classeLinha: fn(linha), acoes: fn(linha) -> HTML,
     pilha: true (empilha no mobile) | false (rolagem contida), compacta: bool,
     rodape: fn(linhasVisiveis) -> { idColuna: HTML } (linha de total; null = sem rodapé), legenda: "descrição",
     celulaVazia: HTML da célula sem valor (padrão: ponto discreto; "" em árvores)
   });
   t.atualizar(novasLinhas) | t.colunasVisiveis([ids]) | t.exportacao() | t.ordenadas()
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = function () { return GI.util; };
  var F = function () { return GI.fmt; };
  var seq = 0;

  function bruto(col, linha) {
    if (col.valor) return col.valor(linha);
    return linha[col.id];
  }
  function formatar(col, v) {
    if (v == null || v === "") return "";
    switch (col.tipo) {
      case "moeda": return F().moeda(v);
      case "data": return F().data(v);
      case "num": return F().num(v, col.casas || 0);
      case "pct": return F().pct(v, col.casas == null ? 1 : col.casas);
      case "indice": return F().indice(v);
      default: return String(v);
    }
  }
  function textoExport(col, linha) {
    if (col.exportar) return col.exportar(linha);
    return formatar(col, bruto(col, linha));
  }
  function comparar(a, b) {
    if (a == null || a === "") return (b == null || b === "") ? 0 : 1;
    if (b == null || b === "") return -1;
    if (typeof a === "number" && typeof b === "number") return a - b;
    return String(a).localeCompare(String(b), "pt-BR", { numeric: true, sensitivity: "base" });
  }
  function numerico(col) { return ["moeda", "num", "pct", "indice", "data"].indexOf(col.tipo) >= 0; }

  function criar(alvo, cfg) {
    var el = typeof alvo === "string" ? document.getElementById(alvo) : alvo;
    var id = "tb" + (++seq);
    var estado = {
      linhas: cfg.linhas || [],
      pagina: 1,
      ordem: cfg.ordem || null,
      visiveis: cfg.colunas.filter(function (c) { return !c.oculta; }).map(function (c) { return c.id; })
    };
    var porPagina = cfg.porPagina == null ? 20 : cfg.porPagina;

    function colunas() { return cfg.colunas.filter(function (c) { return estado.visiveis.indexOf(c.id) >= 0; }); }

    function ordenadas() {
      var l = estado.linhas.slice();
      if (estado.ordem && estado.ordem.coluna) {
        var col = cfg.colunas.filter(function (c) { return c.id === estado.ordem.coluna; })[0];
        if (col) {
          var dir = estado.ordem.direcao === "desc" ? -1 : 1;
          l.sort(function (a, b) {
            var va = bruto(col, a), vb = bruto(col, b);
            var r = comparar(va, vb);
            if ((va == null || va === "") || (vb == null || vb === "")) return r; /* vazios sempre no fim */
            return r * dir;
          });
        }
      }
      return l;
    }

    function cabecalho(cols) {
      return "<thead><tr>" + cols.map(function (c) {
        var cls = (numerico(c) && c.tipo !== "data") || c.classe === "num" ? ' class="num"' : "";
        if (c.ordenavel === false) return "<th" + cls + ' scope="col">' + U().esc(c.titulo) + "</th>";
        var ativo = estado.ordem && estado.ordem.coluna === c.id;
        var dir = ativo ? estado.ordem.direcao : null;
        var aria = ativo ? ' aria-sort="' + (dir === "desc" ? "descending" : "ascending") + '"' : "";
        var ic = ativo ? (dir === "desc" ? "chevronDown" : "chevronUp") : "sort";
        return "<th" + cls + aria + ' scope="col"><button type="button" class="th-sort" data-ordenar="' + c.id + '">' +
          U().esc(c.titulo) + U().icone(ic) + "</button></th>";
      }).join("") + (cfg.acoes ? '<th class="cell-actions" scope="col"><span class="sr-only">Ações da linha</span></th>' : "") + "</tr></thead>";
    }

    function celula(c, linha) {
      var v = bruto(c, linha);
      var conteudo = c.html ? c.html(linha) : U().esc(formatar(c, v));
      var classes = [];
      if ((numerico(c) && c.tipo !== "data") || c.classe === "num") classes.push("num");
      if (c.tipo === "data") classes.push("nowrap");
      if (c.classe && c.classe !== "num") classes.push(c.classe);
      return "<td" + (classes.length ? ' class="' + classes.join(" ") + '"' : "") + ' data-label="' + U().esc(c.titulo) + '">' +
        '<div class="cell-v">' + (conteudo === "" ? (cfg.celulaVazia != null ? cfg.celulaVazia : '<span class="text-muted">·</span>') : conteudo) + "</div></td>";
    }

    function paginacao(total) {
      if (!porPagina || total <= porPagina) {
        return total ? '<div class="table-foot"><span>' + U().plural(total, "registro") + "</span></div>" : "";
      }
      var paginas = Math.ceil(total / porPagina);
      var p = estado.pagina;
      var ini = (p - 1) * porPagina + 1, fim = Math.min(total, p * porPagina);
      var nums = [];
      var de = Math.max(1, Math.min(p - 2, paginas - 4)), ate = Math.min(paginas, de + 4);
      for (var i = de; i <= ate; i++) nums.push(i);
      return '<div class="table-foot"><span>Mostrando ' + ini + " a " + fim + " de " + GI.fmt.num(total) + "</span>" +
        '<nav class="pagination" aria-label="Paginação">' +
        '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-pagina="' + (p - 1) + '" aria-label="Página anterior"' + (p === 1 ? " disabled" : "") + ">" + U().icone("chevronLeft") + "</button>" +
        nums.map(function (n) {
          return '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-pagina="' + n + '"' + (n === p ? ' aria-current="page"' : "") + ' aria-label="Página ' + n + '">' + n + "</button>";
        }).join("") +
        '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-pagina="' + (p + 1) + '" aria-label="Próxima página"' + (p === paginas ? " disabled" : "") + ">" + U().icone("chevronRight") + "</button>" +
        "</nav></div>";
    }

    function render() {
      var cols = colunas();
      var todas = ordenadas();
      var total = todas.length;
      var paginas = porPagina ? Math.max(1, Math.ceil(total / porPagina)) : 1;
      if (estado.pagina > paginas) estado.pagina = paginas;
      var vis = porPagina ? todas.slice((estado.pagina - 1) * porPagina, estado.pagina * porPagina) : todas;
      var pilha = cfg.pilha !== false;
      var corpo;
      if (!total) {
        corpo = '<tbody><tr class="table__empty"><td colspan="' + (cols.length + (cfg.acoes ? 1 : 0)) + '">' +
          U().vazio(cfg.vazio || "Nenhum registro encontrado.", "search") + "</td></tr></tbody>";
      } else {
        corpo = "<tbody>" + vis.map(function (linha, i) {
          var cls = cfg.classeLinha ? cfg.classeLinha(linha) : "";
          return "<tr" + (cls ? ' class="' + cls + '"' : "") + ' data-indice="' + i + '">' + cols.map(function (c) { return celula(c, linha); }).join("") +
            (cfg.acoes ? '<td class="cell-actions" data-label="Ações"><div class="btn-group">' + cfg.acoes(linha) + "</div></td>" : "") + "</tr>";
        }).join("") + "</tbody>";
      }
      var rodape = "";
      var tot = cfg.rodape && total ? cfg.rodape(todas) : null;
      if (tot) {
        rodape = '<tfoot><tr class="row--total">' + cols.map(function (c, k) {
          var conteudo = tot[c.id] != null ? tot[c.id] : (k === 0 ? "Total" : "");
          var num = (numerico(c) && c.tipo !== "data") || c.classe === "num";
          return "<td" + (num ? ' class="num"' : "") + ' data-label="' + U().esc(c.titulo) + '">' + conteudo + "</td>";
        }).join("") + (cfg.acoes ? "<td></td>" : "") + "</tr></tfoot>";
      }
      el.innerHTML =
        '<div class="table-wrap' + (pilha ? " table-wrap--stack" : "") + '">' +
        '<table class="table' + (pilha ? " table--stack" : "") + (cfg.compacta ? " table--compact" : "") + '" id="' + id + '">' +
        (cfg.legenda ? '<caption class="sr-only">' + U().esc(cfg.legenda) + "</caption>" : "") +
        cabecalho(cols) + corpo + rodape + "</table></div>" + paginacao(total);
      estado.visiveisLinhas = vis;
    }

    el.addEventListener("click", function (ev) {
      var ord = ev.target.closest("[data-ordenar]");
      if (ord) {
        var c = ord.getAttribute("data-ordenar");
        if (estado.ordem && estado.ordem.coluna === c) estado.ordem.direcao = estado.ordem.direcao === "asc" ? "desc" : "asc";
        else estado.ordem = { coluna: c, direcao: "asc" };
        estado.pagina = 1;
        render();
        var novo = el.querySelector('[data-ordenar="' + c + '"]');
        if (novo) novo.focus();
        return;
      }
      var pg = ev.target.closest("[data-pagina]");
      if (pg && !pg.disabled) {
        estado.pagina = Number(pg.getAttribute("data-pagina"));
        render();
        var tabela = el.querySelector("table");
        if (tabela && tabela.getBoundingClientRect().top < 0) tabela.scrollIntoView({ block: "start" });
      }
    });

    render();

    return {
      el: el,
      atualizar: function (linhas, manterPagina) { estado.linhas = linhas || []; if (!manterPagina) estado.pagina = 1; render(); },
      linha: function (tr) { var i = Number(tr.getAttribute("data-indice")); return estado.visiveisLinhas[i]; },
      ordenadas: ordenadas,
      colunas: function () { return cfg.colunas.map(function (c) { return { id: c.id, titulo: c.titulo, visivel: estado.visiveis.indexOf(c.id) >= 0, fixa: !!c.fixa }; }); },
      colunasVisiveis: function (ids) { estado.visiveis = ids; render(); },
      /* Dados para exportar: respeita ordenação, filtros aplicados e colunas visíveis */
      exportacao: function () {
        var cols = colunas();
        var linhas = ordenadas();
        return {
          colunas: cols.map(function (c) { return { titulo: c.titulo, tipo: c.tipo || "texto" }; }),
          bruto: linhas.map(function (l) { return cols.map(function (c) { return c.exportar ? c.exportar(l) : bruto(c, l); }); }),
          texto: linhas.map(function (l) { return cols.map(function (c) { return textoExport(c, l); }); })
        };
      }
    };
  }

  /* Modal padrão para escolher as colunas visíveis de uma tabela */
  function escolherColunas(t, aoAplicar) {
    var cols = t.colunas();
    GI.form.abrir({
      titulo: "Colunas da tabela", tamanho: "sm", textoSalvar: "Aplicar",
      campos: [{ id: "cols", rotulo: "Colunas visíveis", tipo: "multi", obrigatorio: true,
        opcoes: cols.filter(function (c) { return !c.fixa; }).map(function (c) { return { valor: c.id, texto: c.titulo }; }),
        valor: cols.filter(function (c) { return c.visivel && !c.fixa; }).map(function (c) { return c.id; }) }],
      aoSalvar: function (v) {
        var ids = cols.filter(function (c) { return c.fixa || v.cols.indexOf(c.id) >= 0; }).map(function (c) { return c.id; });
        t.colunasVisiveis(ids);
        if (aoAplicar) aoAplicar(ids);
      }
    });
  }

  GI.tabela = { criar: criar, formatar: formatar, escolherColunas: escolherColunas };
})(window.GI = window.GI || {});
