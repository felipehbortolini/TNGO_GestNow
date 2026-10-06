/* ==========================================================================
   upload.js | Componente único de upload: arrastar e soltar ou botão.
   Aceita .xlsx, .xls, .csv, .pdf, .png, .jpg (configurável); valida tipo e
   tamanho; prévia de imagem (miniatura), PDF (iframe) e planilha (primeiras
   linhas via SheetJS). Arquivos ficam só em memória.
   TODO: API enviar para POST /arquivos (multipart) e guardar o id devolvido.

   var up = GI.upload.criar(elemento, { aceitar: ["pdf","png","jpg"], maxMB: 10, multiplo: true,
                                        compacto: false, aoMudar: fn(arquivos) });
   up.arquivos() -> [{ file, nome, tamanho, tipo: "imagem"|"pdf"|"planilha", valido, erro, linhas }]
   up.limpar()
   ========================================================================== */
(function (GI) {
  "use strict";

  var PADRAO = ["xlsx", "xls", "csv", "pdf", "png", "jpg", "jpeg"];
  var TIPO = { xlsx: "planilha", xls: "planilha", csv: "planilha", pdf: "pdf", png: "imagem", jpg: "imagem", jpeg: "imagem" };
  var ROTULO = { planilha: "Planilha", pdf: "PDF", imagem: "Imagem" };
  var seq = 0;

  function ext(nome) { var m = /\.([a-z0-9]+)$/i.exec(nome || ""); return m ? m[1].toLowerCase() : ""; }
  function tamanho(b) {
    if (b < 1024) return b + " B";
    if (b < 1048576) return GI.fmt.num(b / 1024, 0) + " KB";
    return GI.fmt.num(b / 1048576, 1) + " MB";
  }
  function esc(t) { return GI.util.esc(t); }

  function criar(alvo, cfg) {
    cfg = cfg || {};
    var el = typeof alvo === "string" ? document.getElementById(alvo) : alvo;
    var aceitar = (cfg.aceitar || PADRAO).map(function (x) { return x.toLowerCase(); });
    if (aceitar.indexOf("jpg") >= 0 && aceitar.indexOf("jpeg") < 0) aceitar.push("jpeg");
    var maxMB = cfg.maxMB || 10;
    var lista = [];
    var id = "up" + (++seq);
    var urls = [];
    var extsTexto = aceitar.filter(function (x) { return x !== "jpeg"; }).map(function (x) { return "." + x; }).join(", ");

    el.classList.add("upload");
    el.innerHTML =
      '<div class="upload__drop' + (cfg.compacto ? " upload__drop--compacto" : "") + '" data-drop>' +
        '<span class="upload__icon">' + GI.util.icone("uploadCloud") + "</span>" +
        '<span class="upload__title" data-titulo>' + esc(cfg.titulo || "Arraste arquivos aqui") + "</span>" +
        '<span class="upload__hint" data-dica>' + esc(extsTexto + " · até " + maxMB + " MB" + (cfg.multiplo === false ? " · 1 arquivo" : "")) + "</span>" +
        '<input class="upload__input" type="file" id="' + id + '"' + (cfg.multiplo === false ? "" : " multiple") +
          ' accept="' + aceitar.map(function (x) { return "." + x; }).join(",") + '">' +
        '<label class="btn btn--secondary btn--sm mt-2" for="' + id + '">' + GI.util.icone("upload") + "Selecionar arquivo" + (cfg.multiplo === false ? "" : "s") + "</label>" +
      "</div>" +
      '<ul class="upload__list" data-lista></ul>' +
      '<div class="upload-preview" data-previa hidden></div>';

    var drop = el.querySelector("[data-drop]");
    var input = el.querySelector("input[type=file]");
    var ul = el.querySelector("[data-lista]");
    var previa = el.querySelector("[data-previa]");

    function estadoDrop(tipo, titulo, dica) {
      drop.classList.toggle("is-dragover", tipo === "arrastando");
      drop.classList.toggle("has-error", tipo === "erro");
      el.querySelector("[data-titulo]").textContent = titulo || cfg.titulo || "Arraste arquivos aqui";
      el.querySelector("[data-dica]").textContent = dica || (extsTexto + " · até " + maxMB + " MB");
    }

    function adicionar(files) {
      var novos = Array.prototype.slice.call(files || []);
      if (!novos.length) return;
      if (cfg.multiplo === false) { lista = []; novos = novos.slice(0, 1); }
      var erros = [];
      novos.forEach(function (f) {
        var e = ext(f.name);
        var item = { file: f, nome: f.name, tamanho: f.size, tipo: TIPO[e] || "outro", valido: true, erro: "" };
        if (aceitar.indexOf(e) < 0) { item.valido = false; item.erro = "Tipo não permitido"; }
        else if (f.size > maxMB * 1048576) { item.valido = false; item.erro = "Acima de " + maxMB + " MB"; }
        if (!item.valido) erros.push(f.name + ": " + item.erro);
        lista.push(item);
        if (item.valido && item.tipo === "planilha") lerPlanilha(item);
      });
      if (erros.length) estadoDrop("erro", erros.length === 1 ? "Arquivo recusado" : erros.length + " arquivos recusados", erros.join(" · "));
      else estadoDrop();
      render();
      if (cfg.aoMudar) cfg.aoMudar(lista);
    }

    function lerPlanilha(item) {
      item.lendo = true;
      GI.exportar.libsExcel().then(function () {
        return item.file.arrayBuffer();
      }).then(function (buf) {
        var wb = window.XLSX.read(buf, { type: "array", cellDates: true });
        var ws = wb.Sheets[wb.SheetNames[0]];
        item.linhas = window.XLSX.utils.sheet_to_json(ws, { header: 1, raw: false, defval: "" });
        item.objetos = window.XLSX.utils.sheet_to_json(ws, { raw: true, defval: null });
        item.aba = wb.SheetNames[0];
      }).catch(function () {
        item.valido = false; item.erro = "Não foi possível ler a planilha";
      }).then(function () { item.lendo = false; render(); if (cfg.aoMudar) cfg.aoMudar(lista); });
    }

    function thumb(item, i) {
      if (item.tipo === "imagem" && item.valido) {
        if (!item.url) { item.url = URL.createObjectURL(item.file); urls.push(item.url); }
        return '<span class="upload-item__thumb"><img src="' + item.url + '" alt=""></span>';
      }
      if (item.tipo === "pdf") return '<span class="upload-item__thumb upload-item__thumb--pdf">' + GI.util.icone("filePdf") + "</span>";
      if (item.tipo === "planilha") return '<span class="upload-item__thumb upload-item__thumb--sheet">' + GI.util.icone("fileSheet") + "</span>";
      return '<span class="upload-item__thumb">' + GI.util.icone("fileText") + "</span>";
    }

    function render() {
      ul.innerHTML = lista.map(function (item, i) {
        var meta = (ROTULO[item.tipo] || "Arquivo") + " · " + tamanho(item.tamanho) +
          (item.linhas ? " · " + GI.util.plural(Math.max(0, item.linhas.length - 1), "linha") : "") +
          " " + (item.lendo ? GI.util.badge("Lendo...", "info") : item.valido ? GI.util.badge("Válido", "success") : GI.util.badge(item.erro, "danger"));
        return '<li class="upload-item' + (item.valido ? "" : " has-error") + (item.aberto ? " is-selected" : "") + '">' + thumb(item, i) +
          '<div><span class="upload-item__name">' + esc(item.nome) + '</span><span class="upload-item__meta">' + meta + "</span></div>" +
          '<div class="upload-item__actions">' +
            (item.valido && !item.lendo ? '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-ver="' + i + '" aria-label="Pré-visualizar ' + esc(item.nome) + '">' + GI.util.icone("eye") + "</button>" : "") +
            '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-remover="' + i + '" aria-label="Remover ' + esc(item.nome) + '">' + GI.util.icone("x") + "</button>" +
          "</div></li>";
      }).join("");
    }

    function mostrarPrevia(i) {
      var item = lista[i];
      lista.forEach(function (x, k) { x.aberto = k === i ? !x.aberto : false; });
      render();
      if (!item.aberto) { previa.hidden = true; previa.innerHTML = ""; return; }
      var corpo = "";
      if (item.tipo === "imagem") corpo = '<img src="' + item.url + '" alt="Prévia de ' + esc(item.nome) + '">';
      else if (item.tipo === "pdf") {
        if (!item.url) { item.url = URL.createObjectURL(item.file); urls.push(item.url); }
        corpo = '<iframe src="' + item.url + '" title="Prévia de ' + esc(item.nome) + '"></iframe>';
      } else if (item.tipo === "planilha" && item.linhas) {
        var linhas = item.linhas.slice(0, 11);
        corpo = '<table class="table table--compact"><thead><tr>' + (linhas[0] || []).map(function (c) { return "<th>" + esc(c) + "</th>"; }).join("") + "</tr></thead><tbody>" +
          linhas.slice(1).map(function (l) { return "<tr>" + l.map(function (c) { return "<td>" + esc(c) + "</td>"; }).join("") + "</tr>"; }).join("") + "</tbody></table>";
      }
      previa.innerHTML = '<div class="upload-preview__head"><b>' + esc(item.nome) + "</b>" +
        (item.tipo === "planilha" ? '<span class="text-small text-muted">Aba "' + esc(item.aba || "") + '" · primeiras 10 linhas</span>' : "") + "</div>" +
        '<div class="upload-preview__body">' + corpo + "</div>";
      previa.hidden = false;
    }

    input.addEventListener("change", function () { adicionar(input.files); input.value = ""; });
    ["dragenter", "dragover"].forEach(function (t) {
      drop.addEventListener(t, function (ev) { ev.preventDefault(); estadoDrop("arrastando", "Solte para adicionar", ""); });
    });
    drop.addEventListener("dragleave", function (ev) { if (!drop.contains(ev.relatedTarget)) estadoDrop(); });
    drop.addEventListener("drop", function (ev) { ev.preventDefault(); adicionar(ev.dataTransfer.files); });
    el.addEventListener("click", function (ev) {
      var r = ev.target.closest("[data-remover]");
      if (r) {
        var i = Number(r.getAttribute("data-remover"));
        if (lista[i].aberto) { previa.hidden = true; previa.innerHTML = ""; }
        lista.splice(i, 1); render(); estadoDrop();
        if (cfg.aoMudar) cfg.aoMudar(lista);
        return;
      }
      var v = ev.target.closest("[data-ver]");
      if (v) mostrarPrevia(Number(v.getAttribute("data-ver")));
    });

    return {
      arquivos: function () { return lista.slice(); },
      limpar: function () { lista = []; urls.forEach(function (u) { URL.revokeObjectURL(u); }); urls = []; previa.hidden = true; render(); estadoDrop(); }
    };
  }

  GI.upload = { criar: criar };
})(window.GI = window.GI || {});
