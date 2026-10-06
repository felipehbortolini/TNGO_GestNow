/* ==========================================================================
   formulario.js | Formulário em modal com validação (GI.form.abrir).

   GI.form.abrir({
     titulo, subtitulo, tamanho: "sm"|"lg"|"xl", textoSalvar, colunas: 2|3,
     intro: "HTML opcional acima dos campos",
     campos: [{ id, rotulo, tipo: "texto"|"textarea"|"select"|"data"|"hora"|"numero"|"moeda"|"multi"|"check"|"arquivo"|"info"|"escolha"|"radio",
                opcoes: [{ valor, texto, sub, numero, desabilitado }], obrigatorio, valor, ajuda, max (caracteres), min, maxNumero, passo,
                maxData (data), largura: "full", placeholder, desabilitado, aceitar (arquivo), html (info), sugestoes (texto),
                antes (HTML entre o rótulo e o controle, ligado por aria-describedby; ex.: o desvio a comentar) }],
     escolha: opções em pílula (uma selecionada; numero opcional em destaque; sub = legenda curta);
     radio: lista vertical de rádios (textos longos).
     repetir: grupo de itens repetíveis (ex.: pontos de atenção). { id, tipo: "repetir", rotulo, itens: [subcampos
       texto|textarea|select|escolha], valor: [{...}], textoAdicionar, rotuloItem: "Ponto", minimo, maximo }.
       Devolve array de objetos; erro de subcampo usa o id "campo.indice.subcampo" (ex.: "pontos.0.risco").
     extras: [{ texto, variante, acao }] botões entre Cancelar e Salvar. acao string: valida e chama
       aoSalvar(valores, modal, acao); acao função: recebe { ler(), definir(valores), fechar() } sem validar.
     mostrarSe: fn(valores) -> bool (no campo: aparece só quando verdadeiro; oculto não valida e volta null),
     validar: fn(valores) -> [{ campo, msg }],
     aoMudar: fn(valores, { info(idCampo, html) }) (a cada alteração; atualiza campos "info" calculados),
     aoSalvar: fn(valores, modal, acao) -> Promise | valor. Promise rejeitada com { erros } mostra os erros no modal.
   })
   Tipos devolvidos: numero -> Number; moeda -> centavos (inteiro); data -> "AAAA-MM-DD"; hora -> "hh:mm";
   multi -> array de valores; check -> boolean; arquivo -> [{ nome, tamanho, tipo }]; escolha e radio -> valor ("" sem seleção);
   repetir -> [{ subcampo: valor }].
   ========================================================================== */
(function (GI) {
  "use strict";

  var seq = 0;
  function esc(t) { return GI.util.esc(t); }

  /* "1.234,56" -> 123456 centavos; aceita também "1234.56" */
  function paraCentavos(txt) {
    if (txt == null || String(txt).trim() === "") return null;
    var s = String(txt).replace(/[R$\s]/g, "");
    if (GI.i18n && GI.i18n.idioma === "en") s = s.replace(/,/g, "");          /* 1,234.56 */
    else if (s.indexOf(",") >= 0) s = s.replace(/\./g, "").replace(",", "."); /* 1.234,56 */
    var n = Number(s);
    return isNaN(n) ? NaN : Math.round(n * 100);
  }
  function deCentavos(c) {
    if (c == null || c === "") return "";
    return (Number(c) / 100).toLocaleString((GI.i18n ? GI.i18n.locale : "pt-BR"), { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function campoHtml(f, pref) {
    var id = pref + "-" + f.id;
    var req = f.obrigatorio ? '<span class="field__required" aria-hidden="true">*</span>' : "";
    var cls = "field" + (f.largura === "full" || f.tipo === "textarea" || f.tipo === "multi" || f.tipo === "arquivo" || f.tipo === "info" || f.tipo === "repetir" ? " field--full" : "");
    var dis = f.desabilitado ? " disabled" : "";
    var aria = ' aria-describedby="' + id + "-e" + (f.antes ? " " + id + "-a" : "") + '"' + (f.obrigatorio ? ' aria-required="true"' : "");
    var ctrl = "";
    var rotulo = '<label class="field__label" for="' + id + '">' + esc(f.rotulo) + req + "</label>";
    switch (f.tipo) {
      case "textarea":
        rotulo = '<div class="field__row">' + rotulo + (f.max ? '<span class="field__counter" data-counter-for="' + id + '"></span>' : "") + "</div>";
        ctrl = '<textarea class="textarea" id="' + id + '" rows="' + (f.linhas || 3) + '"' + (f.max ? ' maxlength="' + f.max + '" data-counter' : "") +
          (f.placeholder ? ' placeholder="' + esc(f.placeholder) + '"' : "") + aria + dis + ">" + esc(f.valor || "") + "</textarea>";
        break;
      case "select":
        ctrl = '<select class="select" id="' + id + '"' + aria + dis + ">" + GI.util.opcoes(f.opcoes, f.valor, f.obrigatorio ? "Selecione..." : (f.vazio || "Nenhum")) + "</select>";
        break;
      case "multi":
        rotulo = '<span class="field__label" id="' + id + '-l">' + esc(f.rotulo) + req + "</span>";
        ctrl = '<div class="check-list" id="' + id + '" role="group" aria-labelledby="' + id + '-l">' + (f.opcoes || []).map(function (o, k) {
          var marcado = (f.valor || []).map(String).indexOf(String(o.valor)) >= 0;
          return '<label class="check"><input type="checkbox" value="' + esc(o.valor) + '"' + (marcado ? " checked" : "") + dis + "> " + esc(o.texto) + "</label>";
        }).join("") + "</div>";
        break;
      case "check":
        rotulo = "";
        ctrl = '<label class="check"><input type="checkbox" id="' + id + '"' + (f.valor ? " checked" : "") + dis + "> " + esc(f.rotulo) + "</label>";
        break;
      case "arquivo":
        rotulo = '<span class="field__label">' + esc(f.rotulo) + req + "</span>";
        ctrl = '<div class="upload" id="' + id + '"></div>';
        break;
      case "escolha":
        rotulo = '<span class="field__label" id="' + id + '-l">' + esc(f.rotulo) + req + "</span>";
        ctrl = '<div class="escolha" id="' + id + '" role="radiogroup" aria-labelledby="' + id + '-l" aria-describedby="' + id + '-e">' + (f.opcoes || []).map(function (o) {
          var sel = f.valor != null && String(f.valor) === String(o.valor);
          return '<button type="button" class="escolha__opt" role="radio" aria-checked="' + sel + '" data-value="' + esc(o.valor) + '"' + (f.desabilitado || o.desabilitado ? " disabled" : "") + ">" +
            (o.numero != null ? "<b>" + esc(o.numero) + "</b>" : "") + "<span>" + esc(o.texto) + (o.sub ? "<small>" + esc(o.sub) + "</small>" : "") + "</span></button>";
        }).join("") + "</div>";
        break;
      case "radio":
        rotulo = '<span class="field__label" id="' + id + '-l">' + esc(f.rotulo) + req + "</span>";
        ctrl = '<div class="radio-list" id="' + id + '" role="radiogroup" aria-labelledby="' + id + '-l" aria-describedby="' + id + '-e">' + (f.opcoes || []).map(function (o) {
          return '<label class="check"><input type="radio" name="' + id + '" value="' + esc(o.valor) + '"' + (f.valor != null && String(f.valor) === String(o.valor) ? " checked" : "") +
            (f.desabilitado || o.desabilitado ? " disabled" : "") + "> " + esc(o.texto) + "</label>";
        }).join("") + "</div>";
        break;
      case "repetir":
        rotulo = '<span class="field__label" id="' + id + '-l">' + esc(f.rotulo) + req + "</span>";
        ctrl = '<div class="repetir" id="' + id + '" role="group" aria-labelledby="' + id + '-l"><div class="repetir__itens" data-repetir-itens></div>' +
          '<button type="button" class="btn btn--secondary btn--sm" data-repetir-add="' + esc(f.id) + '">' + GI.util.icone("plus") + esc(f.textoAdicionar || "Adicionar item") + "</button></div>";
        break;
      case "info":
        return '<div class="' + cls + '" data-campo="' + f.id + '">' + (f.rotulo ? '<span class="field__label">' + esc(f.rotulo) + "</span>" : "") + '<div data-info>' + (f.html || "") + "</div></div>";
      case "moeda":
        ctrl = '<div class="input-affix"><span class="input-affix__text" aria-hidden="true">R$</span><input class="input" id="' + id + '" inputmode="decimal" autocomplete="off" value="' +
          esc(deCentavos(f.valor)) + '" placeholder="0,00"' + aria + dis + "></div>";
        break;
      case "numero":
        ctrl = '<input class="input" type="number" id="' + id + '" value="' + (f.valor == null ? "" : esc(f.valor)) + '"' +
          (f.min != null ? ' min="' + f.min + '"' : "") + (f.maxNumero != null ? ' max="' + f.maxNumero + '"' : "") + (f.passo ? ' step="' + f.passo + '"' : "") + aria + dis + ">";
        break;
      case "hora":
        ctrl = '<input class="input" type="time" id="' + id + '" value="' + esc(f.valor || "") + '"' + aria + dis + ">";
        break;
      case "data":
        ctrl = '<input class="input" type="date" id="' + id + '" value="' + esc(f.valor || "") + '"' + (f.min ? ' min="' + f.min + '"' : "") + (f.maxData ? ' max="' + f.maxData + '"' : "") + aria + dis + ">";
        break;
      default:
        ctrl = '<input class="input" type="text" id="' + id + '" value="' + esc(f.valor || "") + '"' + (f.max ? ' maxlength="' + f.max + '"' : "") +
          (f.placeholder ? ' placeholder="' + esc(f.placeholder) + '"' : "") + (f.sugestoes ? ' list="' + id + '-l" autocomplete="off"' : "") + aria + dis + ">" +
          (f.sugestoes ? '<datalist id="' + id + '-l">' + f.sugestoes.map(function (x) { return '<option value="' + esc(x) + '">'; }).join("") + "</datalist>" : "");
    }
    return '<div class="' + cls + '" data-campo="' + f.id + '">' + rotulo + (f.antes ? '<div class="field__antes" id="' + id + '-a">' + f.antes + "</div>" : "") + ctrl +
      (f.ajuda ? '<span class="field__hint">' + esc(f.ajuda) + "</span>" : "") +
      '<span class="field__error" id="' + id + '-e">' + GI.util.icone("alertCircle") + '<span></span></span></div>';
  }

  function abrir(cfg) {
    var pref = "gf" + (++seq);
    var uploads = {};
    var corpo = document.createElement("div");
    corpo.innerHTML = (cfg.intro ? '<div class="mb-4">' + cfg.intro + "</div>" : "") +
      '<div class="alert alert--danger mb-4" data-erros hidden>' + GI.util.icone("alertTriangle") + '<div class="alert__body"></div></div>' +
      '<div class="form-grid' + (cfg.colunas === 3 ? " form-grid--3" : "") + '">' + cfg.campos.map(function (f) { return campoHtml(f, pref); }).join("") + "</div>";

    var botoes = [{ label: "Cancelar", variant: "secondary" }];
    (cfg.extras || []).forEach(function (x, k) {
      botoes.push({ label: x.texto, variant: x.variante || "secondary", onClick: function (api) {
        if (typeof x.acao === "function") x.acao({ ler: ler, definir: definir, fechar: api.close, erros: mostrarErros });
        else salvar(api, x.acao, m.el.querySelectorAll(".modal__footer .btn")[k + 1]);
      } });
    });
    botoes.push({ label: cfg.textoSalvar || "Salvar", variant: cfg.perigo ? "danger" : "primary", onClick: function (api) { salvar(api, null); } });
    var m = GI.modal.create({ title: cfg.titulo, subtitle: cfg.subtitulo, size: cfg.tamanho, body: corpo, buttons: botoes });
    cfg.campos.forEach(function (f) {
      if (f.tipo === "arquivo" && GI.upload) {
        uploads[f.id] = GI.upload.criar(document.getElementById(pref + "-" + f.id), { aceitar: f.aceitar, multiplo: f.multiplo !== false, maxMB: f.maxMB, compacto: true });
      }
    });
    if (GI.ui) GI.ui.init(m.el);

    /* ---------- Grupos repetíveis ---------- */
    var repetiveis = cfg.campos.filter(function (f) { return f.tipo === "repetir"; });
    function subId(f, k, sub) { return f.id + "." + k + "." + sub.id; }
    function renderRepetir(f, lista) {
      var caixa = document.getElementById(pref + "-" + f.id).querySelector("[data-repetir-itens]");
      var rot = f.rotuloItem || "Item";
      caixa.innerHTML = (lista || []).map(function (item, k) {
        return '<div class="repetir__item" data-indice="' + k + '"><div class="repetir__topo"><span class="repetir__num">' + esc(rot) + " " + (k + 1) + "</span>" +
          '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-repetir-remover="' + esc(f.id) + '" data-indice="' + k + '" aria-label="Remover ' + esc(rot.toLowerCase()) + " " + (k + 1) + '" title="Remover">' +
          GI.util.icone("trash") + '</button></div><div class="form-grid">' + f.itens.map(function (sub) {
            return campoHtml(Object.assign({}, sub, { id: subId(f, k, sub), valor: item ? item[sub.id] : null }), pref);
          }).join("") + "</div></div>";
      }).join("") || '<p class="text-small text-muted repetir__vazio">' + esc(f.vazio || "Nenhum item.") + "</p>";
      var add = m.el.querySelector('[data-repetir-add="' + f.id + '"]');
      if (add) add.disabled = !!(f.maximo && (lista || []).length >= f.maximo);
      if (GI.ui) GI.ui.init(caixa);
    }
    function lerRepetir(f) {
      var caixa = document.getElementById(pref + "-" + f.id).querySelector("[data-repetir-itens]");
      return Array.prototype.map.call(caixa.querySelectorAll(".repetir__item"), function (w) {
        var k = w.getAttribute("data-indice"), o = {};
        f.itens.forEach(function (sub) { o[sub.id] = lerCampo(sub, document.getElementById(pref + "-" + f.id + "." + k + "." + sub.id)); });
        return o;
      });
    }
    repetiveis.forEach(function (f) { renderRepetir(f, f.valor || []); });
    m.el.addEventListener("click", function (ev) {
      var add = ev.target.closest("[data-repetir-add]"), rem = ev.target.closest("[data-repetir-remover]");
      if (!add && !rem) return;
      var f = repetiveis.filter(function (x) { return x.id === (add || rem).getAttribute(add ? "data-repetir-add" : "data-repetir-remover"); })[0];
      if (!f) return;
      var lista = lerRepetir(f);
      if (add) lista.push({}); else lista.splice(Number(rem.getAttribute("data-indice")), 1);
      renderRepetir(f, lista);
      if (add) { var novos = m.el.querySelectorAll("#" + CSS.escape(pref + "-" + f.id) + " .repetir__item"); var ult = novos[novos.length - 1]; var foco = ult && ult.querySelector("input, textarea, select, .escolha__opt"); if (foco) foco.focus(); }
      else { var botaoAdd = m.el.querySelector('[data-repetir-add="' + f.id + '"]'); if (botaoAdd) botaoAdd.focus(); }
      atualizar();
    });

    function oculto(f, v) { return !!(f.mostrarSe && !f.mostrarSe(v)); }
    function atualizar() {
      var v = ler();
      cfg.campos.forEach(function (f) {
        if (!f.mostrarSe) return;
        var w = m.el.querySelector('[data-campo="' + f.id + '"]');
        if (w) w.hidden = oculto(f, v);
      });
      if (cfg.aoMudar) cfg.aoMudar(v, { info: function (id, html) { var w = m.el.querySelector('[data-campo="' + id + '"] [data-info]'); if (w) w.innerHTML = html; } });
    }
    /* Opções em pílula: uma marcada por grupo */
    m.el.addEventListener("click", function (ev) {
      var opt = ev.target.closest(".escolha__opt");
      if (!opt || opt.disabled) return;
      Array.prototype.forEach.call(opt.parentNode.querySelectorAll(".escolha__opt"), function (o) { o.setAttribute("aria-checked", o === opt ? "true" : "false"); });
      atualizar();
    });
    if (cfg.aoMudar || cfg.campos.some(function (f) { return f.mostrarSe; })) {
      m.el.addEventListener("input", atualizar);
      m.el.addEventListener("change", atualizar);
      atualizar();
    }
    /* Grava valores nos controles (botões extras, ex.: Limpar) */
    function definir(valores) {
      cfg.campos.forEach(function (f) {
        if (!(f.id in valores)) return;
        var el = document.getElementById(pref + "-" + f.id), v = valores[f.id];
        if (!el) return;
        if (f.tipo === "multi") Array.prototype.forEach.call(el.querySelectorAll("input"), function (i) { i.checked = (v || []).map(String).indexOf(i.value) >= 0; });
        else if (f.tipo === "check") el.checked = !!v;
        else if (f.tipo === "escolha") Array.prototype.forEach.call(el.querySelectorAll(".escolha__opt"), function (o) { o.setAttribute("aria-checked", String(v != null && o.getAttribute("data-value") === String(v))); });
        else if (f.tipo === "radio") Array.prototype.forEach.call(el.querySelectorAll("input"), function (i) { i.checked = v != null && i.value === String(v); });
        else if (f.tipo === "moeda") el.value = deCentavos(v);
        else if (f.tipo === "repetir") renderRepetir(f, v || []);
        else el.value = v == null ? "" : v;
      });
      atualizar();
    }

    function lerCampo(f, el) {
      if (!el) return null;
      if (f.tipo === "multi") return Array.prototype.map.call(el.querySelectorAll("input:checked"), function (i) { return i.value; });
      if (f.tipo === "check") return el.checked;
      if (f.tipo === "escolha") { var o = el.querySelector('.escolha__opt[aria-checked="true"]'); return o ? o.getAttribute("data-value") : ""; }
      if (f.tipo === "radio") { var r = el.querySelector("input:checked"); return r ? r.value : ""; }
      if (f.tipo === "arquivo") return uploads[f.id] ? uploads[f.id].arquivos().filter(function (a) { return a.valido; }).map(function (a) { return { nome: a.nome, tamanho: a.tamanho, tipo: a.tipo }; }) : [];
      if (f.tipo === "repetir") return lerRepetir(f);
      var t = el.value;
      if (f.tipo === "numero") return t === "" ? null : Number(t);
      if (f.tipo === "moeda") return paraCentavos(t);
      return typeof t === "string" ? t.trim() : t;
    }
    function ler() {
      var v = {};
      cfg.campos.forEach(function (f) {
        if (f.tipo === "info") return;
        v[f.id] = lerCampo(f, document.getElementById(pref + "-" + f.id));
      });
      return v;
    }
    function mostrarErros(lista) {
      m.el.querySelectorAll(".field.has-error").forEach(function (c) { c.classList.remove("has-error"); });
      m.el.querySelectorAll("[aria-invalid]").forEach(function (c) { c.removeAttribute("aria-invalid"); });
      var geral = [];
      lista.forEach(function (e) {
        var campo = e.campo && m.el.querySelector('[data-campo="' + e.campo + '"]');
        if (campo) {
          campo.classList.add("has-error");
          campo.querySelector(".field__error span").textContent = e.msg;
          var ctrl = document.getElementById(pref + "-" + e.campo);
          if (ctrl) ctrl.setAttribute("aria-invalid", "true");
        } else geral.push(e.msg || e);
      });
      var caixa = m.el.querySelector("[data-erros]");
      caixa.hidden = !geral.length;
      caixa.querySelector(".alert__body").innerHTML = geral.map(esc).join("<br>");
      var primeiro = m.el.querySelector(".field.has-error input, .field.has-error select, .field.has-error textarea, .field.has-error .escolha__opt");
      if (primeiro) primeiro.focus(); else if (geral.length) caixa.scrollIntoView({ block: "nearest" });
    }
    function salvar(api, acao, botao) {
      var v = ler(), erros = [];
      var ocultos = cfg.campos.filter(function (f) { return oculto(f, v); });
      ocultos.forEach(function (f) { v[f.id] = null; });
      cfg.campos.forEach(function (f) {
        if (ocultos.indexOf(f) >= 0) return;
        var x = v[f.id];
        if (f.obrigatorio && (x == null || x === "" || (Array.isArray(x) && !x.length) || (typeof x === "number" && isNaN(x)))) {
          erros.push({ campo: f.id, msg: f.tipo === "arquivo" ? "Anexe ao menos um arquivo válido." : "Preencha este campo." });
        } else if (f.tipo === "moeda" && typeof x === "number" && isNaN(x)) erros.push({ campo: f.id, msg: "Valor inválido. Use o formato 1.234,56." });
        else if (f.tipo === "repetir") {
          if (f.minimo && x.length < f.minimo) erros.push({ campo: f.id, msg: "Inclua ao menos " + f.minimo + (f.minimo === 1 ? " item." : " itens.") });
          x.forEach(function (item, k) {
            f.itens.forEach(function (sub) { if (sub.obrigatorio && (item[sub.id] == null || item[sub.id] === "")) erros.push({ campo: subId(f, k, sub), msg: "Preencha este campo." }); });
          });
        }
        else if (f.tipo === "numero" && x != null && ((f.min != null && x < f.min) || (f.maxNumero != null && x > f.maxNumero))) {
          erros.push({ campo: f.id, msg: "Informe um valor entre " + f.min + " e " + f.maxNumero + "." });
        }
      });
      if (!erros.length && cfg.validar) erros = erros.concat(cfg.validar(v) || []);
      if (erros.length) { mostrarErros(erros); return; }
      botao = botao || m.el.querySelector(".modal__footer .btn:last-child");
      botao.classList.add("is-loading"); botao.disabled = true;
      Promise.resolve().then(function () { return cfg.aoSalvar ? cfg.aoSalvar(v, api, acao || null) : v; }).then(function (r) {
        if (r !== false) api.close();
      }).catch(function (e) {
        mostrarErros((e && e.erros ? e.erros : [String(e && e.message || e)]).map(function (x) { return typeof x === "string" ? { msg: x } : x; }));
      }).then(function () { botao.classList.remove("is-loading"); botao.disabled = false; });
    }
    m.ler = ler; m.definir = definir; m.erros = mostrarErros;
    return m;
  }

  GI.form = { abrir: abrir, paraCentavos: paraCentavos, deCentavos: deCentavos };
})(window.GI = window.GI || {});
