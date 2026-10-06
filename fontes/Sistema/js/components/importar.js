/* ==========================================================================
   importar.js | Importação de planilha em 5 passos:
   1 Upload (com modelo para baixar) · 2 Validação · 3 Pré-visualização ·
   4 Confirmação · 5 Inserção. Usa GI.upload e SheetJS (carregado sob demanda).

   GI.importar.abrir({
     titulo, subtitulo,
     colunas: [{ campo, titulo, tipo: "texto"|"num"|"data"|"moeda"|"lista", obrigatorio, opcoes: [..], exemplo }],
     arquivoModelo: "modelo-punch-list",
     validarLinha: fn(obj) -> ["mensagem", ...] (regras extras),
     aoImportar: fn(linhasValidas) -> Promise (grava via GI.api)
   })
   Tipos convertidos: num -> Number; moeda (em reais) -> centavos; data -> "AAAA-MM-DD".
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = function () { return GI.util; };
  var PASSOS = ["Upload", "Validação", "Pré-visualização", "Confirmação", "Inserção"];

  function numero(v) {
    if (typeof v === "number") return v;
    if (v == null || String(v).trim() === "") return null;
    var s = String(v).trim().replace(/[R$\s%]/g, "");
    if (s.indexOf(",") >= 0) s = s.replace(/\./g, "").replace(",", ".");
    var n = Number(s);
    return isNaN(n) ? NaN : n;
  }
  function dataIso(v) {
    if (v == null || v === "") return null;
    if (v instanceof Date && !isNaN(v)) {
      return v.getFullYear() + "-" + String(v.getMonth() + 1).padStart(2, "0") + "-" + String(v.getDate()).padStart(2, "0");
    }
    if (typeof v === "number") { /* número de série do Excel */
      var d = new Date(Date.UTC(1899, 11, 30) + Math.round(v) * 86400000);
      return d.toISOString().slice(0, 10);
    }
    var s = String(v).trim(), m;
    if ((m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s))) return m[1] + "-" + m[2] + "-" + m[3];
    if ((m = /^(\d{1,2})\/(\d{1,2})\/(\d{2,4})$/.exec(s))) {
      var ano = m[3].length === 2 ? "20" + m[3] : m[3];
      return ano + "-" + m[2].padStart(2, "0") + "-" + m[1].padStart(2, "0");
    }
    return "invalida";
  }

  function converter(col, v) {
    var vazio = v == null || String(v).trim() === "";
    if (vazio) return { valor: null, erro: col.obrigatorio ? "obrigatório" : null };
    switch (col.tipo) {
      case "num": var n = numero(v); return isNaN(n) ? { erro: "número inválido" } : { valor: n };
      case "moeda": var r = numero(v); return isNaN(r) ? { erro: "valor inválido" } : { valor: Math.round(r * 100) };
      case "data": var d = dataIso(v); return d === "invalida" ? { erro: "data inválida (use dd/mm/aaaa)" } : { valor: d };
      case "lista":
        var txt = String(v).trim();
        var achou = (col.opcoes || []).filter(function (o) { return U().normalizar(o) === U().normalizar(txt); })[0];
        return achou ? { valor: achou } : { erro: "valor fora da lista (" + col.opcoes.join(", ") + ")" };
      default: return { valor: String(v).trim() };
    }
  }

  function abrir(cfg) {
    var passo = 0, upload = null, arquivo = null, resultado = null, ignorarErros = false;
    var corpo = document.createElement("div");
    corpo.innerHTML = '<ol class="stepper" aria-label="Etapas da importação">' + PASSOS.map(function (p, i) {
      return '<li class="step" data-passo="' + i + '"><span class="step__dot" aria-hidden="true"></span><span class="step__label">' + p + "</span></li>";
    }).join("") + '</ol><div data-conteudo aria-live="polite"></div>';

    var m = GI.modal.create({
      title: cfg.titulo || "Importar planilha", subtitle: cfg.subtitulo, size: "xl", body: corpo,
      buttons: [
        { label: "Voltar", variant: "secondary", onClick: function () { if (passo > 0 && passo < 4) { passo--; render(); } else m.close(); } },
        { label: "Avançar", variant: "primary", onClick: avancar }
      ]
    });
    m.el.setAttribute("data-static", "");
    var btVoltar = m.el.querySelectorAll(".modal__footer .btn")[0];
    var btAvancar = m.el.querySelectorAll(".modal__footer .btn")[1];
    var conteudo = corpo.querySelector("[data-conteudo]");

    function baixarModelo() {
      GI.exportar.libsExcel().then(function () {
        var X = window.XLSX;
        var linhas = [cfg.colunas.map(function (c) { return c.titulo; })];
        var ex = cfg.colunas.map(function (c) { return c.exemplo == null ? "" : c.exemplo; });
        linhas.push(ex);
        var ws = X.utils.aoa_to_sheet(linhas);
        ws["!cols"] = cfg.colunas.map(function (c) { return { wch: Math.max(14, c.titulo.length + 4) }; });
        var instr = X.utils.aoa_to_sheet([["Coluna", "Obrigatória", "Formato"]].concat(cfg.colunas.map(function (c) {
          return [c.titulo, c.obrigatorio ? "Sim" : "Não",
            c.tipo === "data" ? "dd/mm/aaaa" : c.tipo === "moeda" ? "valor em reais (ex.: 1234,56)" : c.tipo === "num" ? "número" :
            c.tipo === "lista" ? "um de: " + c.opcoes.join(", ") : "texto"];
        })));
        instr["!cols"] = [{ wch: 28 }, { wch: 12 }, { wch: 70 }];
        var wb = X.utils.book_new();
        X.utils.book_append_sheet(wb, ws, "Dados");
        X.utils.book_append_sheet(wb, instr, "Instruções");
        X.writeFile(wb, (cfg.arquivoModelo || "modelo-importacao") + ".xlsx");
      });
    }

    function validar() {
      var cols = cfg.colunas;
      var objetos = arquivo.objetos || [];
      var cabecalhos = objetos.length ? Object.keys(objetos[0]) : (arquivo.linhas && arquivo.linhas[0]) || [];
      var mapa = {};
      cols.forEach(function (c) {
        var h = cabecalhos.filter(function (x) { return U().normalizar(x).replace(/\s+/g, " ").trim() === U().normalizar(c.titulo); })[0];
        if (h) mapa[c.campo] = h;
      });
      var faltando = cols.filter(function (c) { return c.obrigatorio && !mapa[c.campo]; });
      var validas = [], erros = [];
      if (!faltando.length) {
        objetos.forEach(function (o, i) {
          var reg = {}, msgs = [];
          var vazia = cols.every(function (c) { return !mapa[c.campo] || o[mapa[c.campo]] == null || String(o[mapa[c.campo]]).trim() === ""; });
          if (vazia) return;
          cols.forEach(function (c) {
            if (!mapa[c.campo]) return;
            var r = converter(c, o[mapa[c.campo]]);
            if (r.erro) msgs.push(c.titulo + ": " + r.erro); else reg[c.campo] = r.valor;
          });
          if (!msgs.length && cfg.validarLinha) msgs = msgs.concat(cfg.validarLinha(reg) || []);
          if (msgs.length) erros.push({ linha: i + 2, msgs: msgs }); else validas.push(reg);
        });
      }
      resultado = { mapa: mapa, faltando: faltando, validas: validas, erros: erros, total: validas.length + erros.length, ignoradas: cabecalhos.filter(function (h) {
        return !Object.keys(mapa).some(function (k) { return mapa[k] === h; });
      }) };
    }

    function tabelaHtml(cab, linhas) {
      return '<div class="table-wrap"><table class="table table--compact"><thead><tr>' + cab.map(function (c) { return "<th>" + U().esc(c) + "</th>"; }).join("") +
        "</tr></thead><tbody>" + linhas.map(function (l) { return "<tr>" + l.map(function (c) { return "<td>" + U().esc(c) + "</td>"; }).join("") + "</tr>"; }).join("") + "</tbody></table></div>";
    }
    function fmt(c, v) {
      if (v == null) return "";
      if (c.tipo === "moeda") return GI.fmt.moeda(v);
      if (c.tipo === "data") return GI.fmt.data(v);
      if (c.tipo === "num") return GI.fmt.num(v, 2).replace(/,00$/, "");
      return String(v);
    }

    function render() {
      Array.prototype.forEach.call(corpo.querySelectorAll(".step"), function (s, i) {
        s.classList.toggle("is-done", i < passo);
        s.classList.toggle("is-current", i === passo);
        if (i === passo) s.setAttribute("aria-current", "step"); else s.removeAttribute("aria-current");
      });
      btVoltar.textContent = passo === 0 || passo === 4 ? (passo === 4 ? "Fechar" : "Cancelar") : "Voltar";
      btAvancar.hidden = passo === 4;
      btAvancar.textContent = passo === 3 ? "Importar" : "Avançar";
      btAvancar.disabled = false;

      if (passo === 0) {
        conteudo.innerHTML = '<div class="split mb-4"><p class="text-small text-muted">Use o modelo para garantir os nomes das colunas. Aceita .xlsx, .xls ou .csv; a primeira aba é lida.</p>' +
          '<button type="button" class="btn btn--secondary btn--sm" data-modelo>' + U().icone("download") + "Baixar modelo</button></div><div data-upload></div>";
        conteudo.querySelector("[data-modelo]").addEventListener("click", baixarModelo);
        upload = GI.upload.criar(conteudo.querySelector("[data-upload]"), { aceitar: ["xlsx", "xls", "csv"], multiplo: false, maxMB: 5,
          titulo: "Arraste a planilha aqui", aoMudar: function (l) { arquivo = l.filter(function (a) { return a.valido && !a.lendo && a.objetos; })[0] || null; } });
      } else if (passo === 1) {
        validar();
        var r = resultado;
        conteudo.innerHTML =
          (r.faltando.length ? '<div class="alert alert--danger mb-4">' + U().icone("alertTriangle") + '<div class="alert__body"><b>Colunas obrigatórias ausentes:</b> ' +
            r.faltando.map(function (c) { return U().esc(c.titulo); }).join(", ") + ". Baixe o modelo e ajuste a planilha.</div></div>" : "") +
          '<div class="kpi-grid mb-4">' +
            U().kpi({ rotulo: "Linhas lidas", valor: GI.fmt.num(r.total), icone: "fileSheet", cor: "primary", esperado: { rotulo: "Referência", valor: GI.fmt.num(r.total) } }) +
            U().kpi({ rotulo: "Válidas", valor: GI.fmt.num(r.validas.length), icone: "checkCircle", cor: "success", esperado: { rotulo: "Esperado", valor: GI.fmt.num(r.total) } }) +
            U().kpi({ rotulo: "Com erro", valor: GI.fmt.num(r.erros.length), icone: "alertTriangle", cor: r.erros.length ? "danger" : "success", esperado: { rotulo: "Esperado", valor: "0" } }) +
          "</div>" +
          (r.ignoradas.length ? '<p class="text-small text-muted mb-4">Colunas ignoradas (não fazem parte do modelo): ' + r.ignoradas.map(U().esc).join(", ") + ".</p>" : "") +
          (r.erros.length ? '<h3 class="section-title">Erros encontrados</h3>' + tabelaHtml(["Linha", "Problemas"], r.erros.slice(0, 50).map(function (e) { return [e.linha, e.msgs.join("; ")]; })) : "");
        btAvancar.disabled = !!r.faltando.length || !r.validas.length;
      } else if (passo === 2) {
        var cols = cfg.colunas.filter(function (c) { return resultado.mapa[c.campo]; });
        conteudo.innerHTML = '<p class="text-small text-muted mb-4">Primeiras ' + Math.min(20, resultado.validas.length) + " de " + resultado.validas.length + " linhas válidas, já convertidas.</p>" +
          tabelaHtml(cols.map(function (c) { return c.titulo; }), resultado.validas.slice(0, 20).map(function (o) { return cols.map(function (c) { return fmt(c, o[c.campo]); }); }));
      } else if (passo === 3) {
        conteudo.innerHTML = '<div class="alert mb-4">' + U().icone("info") + '<div class="alert__body"><b>' + U().plural(resultado.validas.length, "linha será inserida", "linhas serão inseridas") + ".</b>" +
          (resultado.erros.length ? " " + U().plural(resultado.erros.length, "linha com erro será ignorada", "linhas com erro serão ignoradas") + "." : "") + "</div></div>" +
          (resultado.erros.length ? '<label class="check"><input type="checkbox" data-ignorar> Estou ciente de que as linhas com erro não serão importadas</label>' : "");
        var chk = conteudo.querySelector("[data-ignorar]");
        if (chk) { btAvancar.disabled = !ignorarErros; chk.checked = ignorarErros; chk.addEventListener("change", function () { ignorarErros = chk.checked; btAvancar.disabled = !chk.checked; }); }
      } else if (passo === 4) {
        conteudo.innerHTML = U().vazio("Gravando...", "refresh");
        Promise.resolve(cfg.aoImportar(resultado.validas)).then(function (msg) {
          conteudo.innerHTML = '<div class="empty"><span class="empty__icon">' + U().icone("checkCircle") + '</span><span class="empty__title">Importação concluída</span><p>' +
            U().esc(msg || U().plural(resultado.validas.length, "registro importado", "registros importados") + ".") + "</p></div>";
        }).catch(function (e) {
          conteudo.innerHTML = '<div class="alert alert--danger">' + U().icone("alertTriangle") + '<div class="alert__body">Falha na importação: ' + U().esc(e && e.message ? e.message : String(e)) + "</div></div>";
        });
      }
    }

    function avancar() {
      if (passo === 0) {
        if (!arquivo) { GI.ui.toast("Selecione uma planilha válida (aguarde a leitura terminar).", "warning"); return; }
      }
      passo++;
      render();
    }
    render();
    return m;
  }

  GI.importar = { abrir: abrir, converter: converter };
})(window.GI = window.GI || {});
