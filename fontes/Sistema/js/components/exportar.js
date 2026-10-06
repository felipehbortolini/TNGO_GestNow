/* ==========================================================================
   exportar.js | Exportação Excel (.xlsx, SheetJS) e PDF (jsPDF + AutoTable).
   As bibliotecas são carregadas só no primeiro clique (páginas mais leves).

   Na página:
     <button type="button" class="btn btn--secondary" data-exportar="excel">...</button>
     <button type="button" class="btn btn--secondary" data-exportar="pdf">...</button>
     GI.exportar.registrar(function () {
       return { titulo, subtitulo, arquivo, orientacao: "l"|"p", formato: "a4"|"a3",
                blocos: [ { tipo: "kpis", titulo, itens: [{ rotulo, valor, esperado }] },
                          { tipo: "tabela", titulo, dados: tabela.exportacao(),
                            corCelula: fn(linha, coluna) -> { fundo: "token", texto: "token" } (PDF, opcional),
                            fonte: tamanho da fonte no PDF (opcional) },
                          { tipo: "grafico", titulo, canvas: elementoCanvas },
                          { tipo: "texto", titulo, texto } ] };
     });
   Excel: uma aba por tabela + aba "Indicadores" (KPIs) + aba "Sobre".
   PDF: cabeçalho com logo, blocos na ordem, rodapé com página.
   Cores do PDF lidas das variáveis CSS (nenhum hexadecimal aqui).
   ========================================================================== */
(function (GI) {
  "use strict";

  var cache = {};
  var provedor = null;
  function T(x) { return GI.t && x != null ? GI.t(String(x)) : x; }

  function raiz() { return document.body.getAttribute("data-root") || ""; }
  function carregarScript(src) {
    if (!cache[src]) {
      cache[src] = new Promise(function (ok, erro) {
        var s = document.createElement("script");
        s.src = src;
        s.onload = function () { ok(); };
        s.onerror = function () { erro(new Error("Falha ao carregar " + src)); };
        document.head.appendChild(s);
      });
    }
    return cache[src];
  }
  function carregar(lista) {
    return lista.reduce(function (p, src) { return p.then(function () { return carregarScript(src); }); }, Promise.resolve());
  }
  function libsExcel() { return window.XLSX ? Promise.resolve() : carregar([raiz() + "assets/vendor/xlsx.full.min.js"]); }
  function libsPdf() {
    return carregar([raiz() + "assets/vendor/jspdf.umd.min.js", raiz() + "assets/vendor/jspdf.plugin.autotable.min.js", raiz() + "js/components/logo-pdf.js"]);
  }

  function nomeArquivo(base, ext) {
    var ref = GI.api ? GI.api.referencia() : "";
    var limpo = GI.util.normalizar(base || "exportacao").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    return limpo + (ref ? "-" + ref : "") + "." + ext;
  }
  function contexto() {
    /* Escopo: ?escopo= (relatório gerencial) ou o escopo global; null = Portfólio */
    var e = GI.util && GI.util.param ? GI.util.param("escopo") : null;
    var id = e ? (e === "portfolio" ? null : Number(e)) : GI.api ? GI.api.projetoAtualId() : null;
    var proj = GI.util && GI.api && id != null ? GI.util.projeto(id) : null;
    var agora = new Date();
    return {
      projeto: proj ? proj.codigo + " " + proj.nome : GI.api ? "Portfólio de projetos" : "",
      referencia: GI.api ? GI.fmt.data(GI.api.referencia()) : "",
      gerado: agora.toLocaleDateString((GI.i18n ? GI.i18n.locale : "pt-BR")) + " " + agora.toLocaleTimeString((GI.i18n ? GI.i18n.locale : "pt-BR"), { hour: "2-digit", minute: "2-digit" }),
      usuario: GI.api ? GI.api.sessaoAtual().nome : ""
    };
  }

  /* ---------------- Excel ---------------- */
  var FORMATO = { moeda: '"R$" #,##0.00', num: "#,##0", pct: '0.0"%"', indice: "0.00", data: "dd/mm/yyyy" };
  function celulaExcel(tipo, v) {
    if (v == null || v === "") return { t: "s", v: "" };
    if (tipo === "moeda" && typeof v === "number") return { t: "n", v: v / 100, z: FORMATO.moeda };
    if ((tipo === "num" || tipo === "pct" || tipo === "indice") && typeof v === "number") return { t: "n", v: v, z: FORMATO[tipo] };
    if (tipo === "data" && /^\d{4}-\d{2}-\d{2}/.test(String(v))) {
      /* número de série do Excel (dias desde 30/12/1899), sem efeito de fuso horário */
      var p = String(v).slice(0, 10).split("-").map(Number);
      var serie = (Date.UTC(p[0], p[1] - 1, p[2]) - Date.UTC(1899, 11, 30)) / 86400000;
      return { t: "n", v: serie, z: FORMATO.data };
    }
    return { t: "s", v: T(String(v)) };
  }
  function abaTabela(titulo, dados) {
    var X = window.XLSX;
    var ws = {};
    var cols = dados.colunas;
    cols.forEach(function (c, j) { ws[X.utils.encode_cell({ r: 0, c: j })] = { t: "s", v: T(c.titulo) }; });
    dados.bruto.forEach(function (linha, i) {
      linha.forEach(function (v, j) { ws[X.utils.encode_cell({ r: i + 1, c: j })] = celulaExcel(cols[j].tipo, v); });
    });
    ws["!ref"] = X.utils.encode_range({ s: { r: 0, c: 0 }, e: { r: Math.max(dados.bruto.length, 1), c: Math.max(cols.length - 1, 0) } });
    ws["!cols"] = cols.map(function (c, j) {
      var max = String(c.titulo).length;
      dados.texto.forEach(function (l) { max = Math.max(max, String(l[j] || "").length); });
      return { wch: Math.min(60, Math.max(10, max + 2)) };
    });
    ws["!autofilter"] = { ref: ws["!ref"] };
    return ws;
  }
  function nomeAba(t, usados) {
    var n = String(t || "Dados").replace(/[\\\/\?\*\[\]:]/g, " ").slice(0, 31).trim() || "Dados";
    var base = n, k = 2;
    while (usados[n]) { n = base.slice(0, 28) + " " + k++; }
    usados[n] = true;
    return n;
  }
  function excel(def) {
    return libsExcel().then(function () {
      var X = window.XLSX, wb = X.utils.book_new(), usados = {}, ctx = contexto();
      var sobre = [[T("Gestão Integrada AMT (protótipo com dados fictícios)")], [T(def.titulo || "")], [T(def.subtitulo || "")],
        [T("Projeto"), ctx.projeto], [T("Data de referência"), ctx.referencia], [T("Gerado em"), ctx.gerado], [T("Usuário"), ctx.usuario]];
      (def.blocos || []).forEach(function (b) {
        if (b.tipo === "tabela" && b.dados) X.utils.book_append_sheet(wb, abaTabela(b.titulo, b.dados), nomeAba(T(b.titulo), usados));
        if (b.tipo === "kpis") {
          var comRef = b.itens.some(function (k) { return k.esperado; });
          var ws = X.utils.aoa_to_sheet([[T("Indicador"), T("Valor")].concat(comRef ? [T("Referência")] : [])].concat(b.itens.map(function (k) { return [T(k.rotulo), T(k.valor)].concat(comRef ? [T(k.esperado || "")] : []); })));
          ws["!cols"] = [{ wch: 44 }, { wch: 28 }, { wch: 40 }];
          X.utils.book_append_sheet(wb, ws, nomeAba(T(b.titulo || "Indicadores"), usados));
        }
      });
      var wsSobre = X.utils.aoa_to_sheet(sobre);
      wsSobre["!cols"] = [{ wch: 22 }, { wch: 60 }];
      X.utils.book_append_sheet(wb, wsSobre, nomeAba(T("Sobre"), usados));
      if (!wb.SheetNames.length) throw new Error(T("Nada para exportar."));
      X.writeFile(wb, nomeArquivo(def.arquivo || def.titulo, "xlsx"));
      /* TODO: API gerar o arquivo no servidor quando o volume for grande */
    });
  }

  /* ---------------- PDF ---------------- */
  function rgb(nomeToken) {
    var v = getComputedStyle(document.documentElement).getPropertyValue("--" + nomeToken).trim();
    var m = /^#([0-9a-f]{6})$/i.exec(v);
    if (m) return [parseInt(m[1].slice(0, 2), 16), parseInt(m[1].slice(2, 4), 16), parseInt(m[1].slice(4, 6), 16)];
    var r = /rgba?\((\d+)[, ]+(\d+)[, ]+(\d+)/.exec(v);
    return r ? [Number(r[1]), Number(r[2]), Number(r[3])] : [0, 0, 0];
  }
  /* Fontes padrão do PDF usam WinAnsi: troca símbolos fora da tabela */
  function limpar(t) {
    return String(t == null ? "" : t).replace(/−/g, "-").replace(/≥/g, ">=").replace(/≤/g, "<=")
      .replace(/→/g, "->").replace(/[\u2013\u2014]/g, "-").replace(/ | /g, " ").replace(/[^\x00-\xff€…•]/g, "");
  }
  function pdf(def) {
    return libsPdf().then(function () {
      var jsPDF = window.jspdf.jsPDF;
      var orient = def.orientacao || "l";
      var doc = new jsPDF({ orientation: orient, unit: "mm", format: def.formato || "a4" });
      var W = doc.internal.pageSize.getWidth(), H = doc.internal.pageSize.getHeight(), M = 12;
      var cor = { primaria: rgb("color-primary"), texto: rgb("text-default"), muted: rgb("text-muted"), borda: rgb("border-default"),
        suave: rgb("surface-sunken"), destaque: rgb("color-highlight"), branco: rgb("brand-branco") };
      var ctx = contexto();
      var autoTable = function (opts) { return doc.autoTable ? doc.autoTable(opts) : window.autoTable(doc, opts); };

      function cabecalho() {
        var logo = GI.logoPdf;
        if (logo) doc.addImage(logo.dataUrl, "PNG", M, 8, 36, 36 * logo.altura / logo.largura);
        doc.setFont("helvetica", "bold"); doc.setFontSize(14); doc.setTextColor.apply(doc, cor.primaria);
        doc.text(limpar(T(def.titulo || "")), M + 42, 12);
        doc.setFont("helvetica", "normal"); doc.setFontSize(8.5); doc.setTextColor.apply(doc, cor.muted);
        var linha2 = [T(def.subtitulo), ctx.projeto].filter(function (v, i, a) { return v && a.indexOf(v) === i; }).join(" · ");
        doc.text(limpar(linha2), M + 42, 17);
        doc.text(limpar(T("Data de referência " + ctx.referencia + " · Gerado em " + ctx.gerado + " por " + ctx.usuario)), M + 42, 21.5);
        doc.setFillColor.apply(doc, cor.destaque); doc.rect(M, 26, 18, 1.2, "F");
        doc.setDrawColor.apply(doc, cor.borda); doc.setLineWidth(0.2); doc.line(M + 19, 26.6, W - M, 26.6);
      }
      function rodapes() {
        var n = doc.getNumberOfPages();
        for (var i = 1; i <= n; i++) {
          doc.setPage(i);
          doc.setFont("helvetica", "normal"); doc.setFontSize(7.5); doc.setTextColor.apply(doc, cor.muted);
          doc.text(limpar(T("Gestão Integrada AMT · protótipo com dados fictícios")), M, H - 6);
          doc.text(limpar(T("Página " + i + " de " + n)), W - M, H - 6, { align: "right" });
        }
      }
      function tituloBloco(t, y) {
        if (!t) return y;
        if (y > H - 30) { doc.addPage(); cabecalho(); y = 34; }
        doc.setFont("helvetica", "bold"); doc.setFontSize(10.5); doc.setTextColor.apply(doc, cor.primaria);
        doc.text(limpar(T(t)), M, y + 4);
        return y + 7;
      }

      cabecalho();
      var y = 32;
      (def.blocos || []).forEach(function (b) {
        if (b.tipo === "kpis") {
          y = tituloBloco(b.titulo, y);
          var comRef = b.itens.some(function (k) { return k.esperado; });
          var porLinha = orient === "l" ? 4 : 3, gap = 3, w = (W - 2 * M - gap * (porLinha - 1)) / porLinha, h = comRef ? 19 : 15;
          b.itens.forEach(function (k, i) {
            var col = i % porLinha;
            if (col === 0 && i > 0) y += h + gap;
            if (y + h > H - 14) { doc.addPage(); cabecalho(); y = 34; }
            var x = M + col * (w + gap);
            doc.setDrawColor.apply(doc, cor.borda); doc.setFillColor.apply(doc, cor.branco); doc.roundedRect(x, y, w, h, 1.5, 1.5, "FD");
            doc.setFillColor.apply(doc, cor.primaria); doc.rect(x, y, 1, h, "F");
            doc.setFont("helvetica", "normal"); doc.setFontSize(7.5); doc.setTextColor.apply(doc, cor.muted);
            doc.text(limpar(T(k.rotulo)), x + 3.5, y + 5, { maxWidth: w - 5 });
            doc.setFont("helvetica", "bold"); doc.setFontSize(12); doc.setTextColor.apply(doc, cor.texto);
            doc.text(limpar(k.valor), x + 3.5, y + 12);
            if (k.esperado) { doc.setFont("helvetica", "normal"); doc.setFontSize(7); doc.setTextColor.apply(doc, cor.muted); doc.text(limpar(T(k.esperado)), x + 3.5, y + 16.5, { maxWidth: w - 5 }); }
          });
          y += h + 6;
        } else if (b.tipo === "tabela" && b.dados) {
          y = tituloBloco(b.titulo, y);
          var numericas = {};
          b.dados.colunas.forEach(function (c, j) { if (["moeda", "num", "pct", "indice"].indexOf(c.tipo) >= 0) numericas[j] = { halign: "right" }; });
          autoTable({
            startY: y, margin: { left: M, right: M, top: 34, bottom: 14 },
            head: [b.dados.colunas.map(function (c) { return limpar(T(c.titulo)); })],
            body: b.dados.texto.map(function (l) { return l.map(function (v) { return limpar(T(v)); }); }),
            styles: { font: "helvetica", fontSize: b.fonte || 7.5, cellPadding: b.fonte ? 1.2 : 1.8, textColor: cor.texto, lineColor: cor.borda, lineWidth: 0.1, overflow: "linebreak" },
            headStyles: { fillColor: cor.primaria, textColor: cor.branco, fontStyle: "bold" },
            alternateRowStyles: { fillColor: cor.suave },
            columnStyles: numericas,
            didParseCell: b.corCelula ? function (d) {
              if (d.section !== "body") return;
              var c = b.corCelula(d.row.index, d.column.index);
              if (c) { if (c.fundo) d.cell.styles.fillColor = rgb(c.fundo); if (c.texto) d.cell.styles.textColor = rgb(c.texto); }
            } : undefined,
            didDrawPage: function (d) { if (d.pageNumber > 1) cabecalho(); }
          });
          y = doc.lastAutoTable.finalY + 8;
        } else if (b.tipo === "grafico" && b.canvas) {
          y = tituloBloco(b.titulo, y);
          var img = b.canvas.toDataURL("image/png", 1);
          var larg = W - 2 * M, alt = larg * b.canvas.height / b.canvas.width;
          var maxAlt = orient === "l" ? 95 : 110;
          if (alt > maxAlt) { larg = larg * maxAlt / alt; alt = maxAlt; }
          if (y + alt > H - 14) { doc.addPage(); cabecalho(); y = tituloBloco(b.titulo, 34); }
          doc.addImage(img, "PNG", M, y, larg, alt);
          y += alt + 8;
        } else if (b.tipo === "texto") {
          y = tituloBloco(b.titulo, y);
          doc.setFont("helvetica", "normal"); doc.setFontSize(9); doc.setTextColor.apply(doc, cor.texto);
          var linhas = doc.splitTextToSize(limpar(T(b.texto)), W - 2 * M);
          linhas.forEach(function (ln) {
            if (y > H - 16) { doc.addPage(); cabecalho(); y = 34; }
            doc.text(ln, M, y + 3); y += 4.6;
          });
          y += 4;
        }
      });
      rodapes();
      doc.save(nomeArquivo(def.arquivo || def.titulo, "pdf"));
    });
  }

  function executar(tipo, botao) {
    if (!provedor) { GI.ui.toast("Esta tela ainda não tem dados para exportar.", "warning"); return; }
    var def;
    try { def = provedor(tipo); } catch (e) { GI.ui.toast("Não foi possível montar a exportação.", "danger"); if (window.console) console.error(e); return; }
    if (!def) { GI.ui.toast("Nada para exportar.", "warning"); return; }
    if (botao) { botao.classList.add("is-loading"); botao.disabled = true; }
    var tarefa = tipo === "pdf" ? pdf(def) : excel(def);
    tarefa.then(function () {
      GI.ui.toast(tipo === "pdf" ? "PDF gerado." : "Planilha Excel gerada.", "success");
    }).catch(function (e) {
      GI.ui.toast("Falha ao exportar: " + (e && e.message ? e.message : "erro desconhecido"), "danger");
      if (window.console) console.error(e);
    }).then(function () { if (botao) { botao.classList.remove("is-loading"); botao.disabled = false; } });
  }

  document.addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-exportar]");
    if (!b) return;
    ev.preventDefault();
    executar(b.getAttribute("data-exportar"), b);
  });

  GI.exportar = {
    registrar: function (fn) { provedor = fn; },
    excel: excel, pdf: pdf, executar: executar, carregar: carregar, libsExcel: libsExcel,
    /* Botões padrão para cabeçalhos de página e de card */
    botoes: function (pequeno) {
      var sm = pequeno ? " btn--sm" : "";
      return '<button type="button" class="btn btn--secondary' + sm + '" data-exportar="excel" title="Exportar Excel">' + GI.util.icone("fileSheet") + '<span><span class="btn__prefixo">Exportar </span>Excel</span></button>' +
        '<button type="button" class="btn btn--secondary' + sm + '" data-exportar="pdf" title="Exportar PDF">' + GI.util.icone("filePdf") + '<span><span class="btn__prefixo">Exportar </span>PDF</span></button>';
    }
  };
})(window.GI = window.GI || {});
