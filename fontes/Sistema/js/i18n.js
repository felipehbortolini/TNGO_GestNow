/* ==========================================================================
   i18n.js | Idiomas do sistema: português (padrão) e inglês.

   Como funciona (protótipo):
   * O idioma escolhido fica salvo no navegador (chave "gi.idioma") e a
     página recarrega ao trocar. Carregar este arquivo ANTES de todos.
   * Textos da interface são escritos em português no código. Em inglês,
     GI.t("texto") devolve a tradução do dicionário (js/i18n/en.js) e um
     tradutor de DOM troca textos e atributos (aria-label, title,
     placeholder, data-label) que aparecem na tela, inclusive os gerados
     depois (MutationObserver).
   * Dados digitados pelos usuários (assuntos, descrições, nomes) NÃO são
     traduzidos; listas controladas (status, categorias, tipos) são.
   * Textos com números usam padrões (ex.: "Mostrando 1 a 15 de 32").
   TODO: API na fase com backend, os dicionários viram arquivos de recurso
   por idioma e o idioma passa a ser preferência do usuário no servidor.
   ========================================================================== */
(function (GI) {
  "use strict";

  var CHAVE = "gi.idioma";
  var idioma = "pt";
  try { if (window.localStorage.getItem(CHAVE) === "en") idioma = "en"; } catch (e) { /* sem armazenamento: português */ }

  var DIC = {};
  var PADROES = [];
  var NUMERO = /^([\d.,]+)\s+(.+)$/;

  function t(texto) {
    if (idioma === "pt" || texto == null) return texto;
    var s = String(texto);
    var k = s.replace(/\s+/g, " ").trim();
    if (!k) return s;
    var tr = traduzir(k);
    return tr == null ? s : s.replace(s.trim(), tr);
  }
  function traduzir(k) {
    if (Object.prototype.hasOwnProperty.call(DIC, k)) return DIC[k];
    for (var i = 0; i < PADROES.length; i++) {
      var p = PADROES[i], m = p[0].exec(k);
      if (m) return typeof p[1] === "function" ? p[1].apply(null, m) : k.replace(p[0], p[1]);
    }
    var n = NUMERO.exec(k);                              /* "32 registros" -> "32 records" */
    if (n && Object.prototype.hasOwnProperty.call(DIC, n[2])) return n[1] + " " + DIC[n[2]];
    if (k.indexOf(" · ") > 0) {                          /* partes separadas por " · " */
      var mudou = false;
      var partes = k.split(" · ").map(function (p) { var tr = traduzir(p); if (tr != null) { mudou = true; return tr; } return p; });
      if (mudou) return partes.join(" · ");
    }
    return null;
  }

  /* antes: true coloca os padrões na frente (específicos de um módulo antes dos genéricos) */
  function registrar(dicionario, padroes, antes) {
    Object.keys(dicionario || {}).forEach(function (k) { DIC[k] = dicionario[k]; });
    if (antes) PADROES = (padroes || []).concat(PADROES);
    else (padroes || []).forEach(function (p) { PADROES.push(p); });
  }

  /* ---------------- Tradutor de DOM (só em inglês) ---------------- */
  var ATRIBUTOS = ["aria-label", "title", "placeholder", "data-label", "alt"];
  var IGNORAR = { SCRIPT: 1, STYLE: 1, TEXTAREA: 1, CODE: 1, PRE: 1, NOSCRIPT: 1 };
  function ignorado(el) {
    while (el && el.nodeType === 1) {
      if (IGNORAR[el.tagName] || el.hasAttribute("data-sem-traducao") || el.getAttribute("translate") === "no") return true;
      el = el.parentElement;
    }
    return false;
  }
  function traduzirTexto(no) {
    var v = no.nodeValue;
    if (!v || !/[A-Za-zÀ-ú]/.test(v)) return;
    var novo = t(v);
    if (novo !== v) no.nodeValue = novo;
  }
  function traduzirElemento(el) {
    ATRIBUTOS.forEach(function (a) {
      if (el.hasAttribute && el.hasAttribute(a)) {
        var v = el.getAttribute(a), novo = t(v);
        if (novo !== v) el.setAttribute(a, novo);
      }
    });
    if (el.tagName === "INPUT" && (el.type === "button" || el.type === "submit") && el.value) el.value = t(el.value);
  }
  function traduzirArvore(raiz) {
    if (!raiz) return;
    if (raiz.nodeType === 3) { if (!ignorado(raiz.parentElement)) traduzirTexto(raiz); return; }
    if (raiz.nodeType === 1 && raiz.tagName === "TEXTAREA" && !ignorado(raiz.parentElement)) { traduzirElemento(raiz); return; }   /* só o placeholder; o conteúdo é do usuário */
    if (raiz.nodeType !== 1 || ignorado(raiz)) return;
    traduzirElemento(raiz);
    var w = document.createTreeWalker(raiz, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        if (n.nodeType === 1) {
          if (n.tagName === "TEXTAREA" && !n.hasAttribute("data-sem-traducao")) { traduzirElemento(n); return NodeFilter.FILTER_REJECT; }
          return IGNORAR[n.tagName] || n.hasAttribute("data-sem-traducao") ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
        }
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    var n;
    while ((n = w.nextNode())) { if (n.nodeType === 3) traduzirTexto(n); else traduzirElemento(n); }
  }

  function iniciar() {
    document.documentElement.lang = idioma === "en" ? "en" : "pt-BR";
    if (idioma === "pt") return;
    document.title = t(document.title);
    traduzirArvore(document.body);
    new MutationObserver(function (lista) {
      lista.forEach(function (m) {
        if (m.type === "childList") Array.prototype.forEach.call(m.addedNodes, traduzirArvore);
        else if (m.type === "characterData") { if (!ignorado(m.target.parentElement)) traduzirTexto(m.target); }
        else if (m.type === "attributes") traduzirElemento(m.target);
      });
    }).observe(document.documentElement, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATRIBUTOS });
  }

  function definir(novo) {
    try { window.localStorage.setItem(CHAVE, novo === "en" ? "en" : "pt"); } catch (e) { /* segue no idioma atual */ }
    window.location.reload();
  }

  GI.i18n = {
    idioma: idioma,
    locale: idioma === "en" ? "en-US" : "pt-BR",
    t: t, registrar: registrar, definir: definir, traduzirArvore: traduzirArvore
  };
  GI.t = t;

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar);
  else iniciar();
})(window.GI = window.GI || {});
