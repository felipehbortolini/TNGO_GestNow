/* ============================================================
   i18n.js — O idioma da interface no navegador (D13, ISSUE-087)

   A tradução vive no servidor: os fragmentos e as telas chegam prontos no
   idioma do cookie (`gestnow_idioma`), e o texto que o JavaScript escreve
   passa por TN.t. Este arquivo cuida do que é estático no cliente:

     TN.i18n.aplicar(idioma, textos)  guarda a escolha e o mapa do fragmento
                                      da barra lateral (data-textos) e
                                      ajusta o lang do documento
     TN.i18n.traduzirView()           traduz a view recém-carregada pelos
                                      atributos data-i18n* (texto, title,
                                      aria-label e placeholder)
     TN.t(namespace, texto)           o texto do namespace do módulo da tela,
                                      com o comum de reserva; sem tradução,
                                      devolve o próprio texto em português

   A ordem de busca do atributo é namespace do módulo da tela → comum. O
   namespace do módulo sai do `data-tela` da barra lateral
   (`/_views/central_acoes/atas.html` → `central_acoes`), que o servidor
   acabou de gravar na navegação.

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const TN = (window.TN = window.TN || {});

  const VAZIO = Object.freeze({});
  const CADEIA_DE_ATRIBUTOS = [
    ["data-i18n", "textContent"],
    ["data-i18n-title", "title"],
    ["data-i18n-aria-label", "aria-label"],
    ["data-i18n-placeholder", "placeholder"]
  ];

  const i18n = {
    idioma: "pt",
    textos: VAZIO,

    /* Chamado pelo shell quando /api/nav devolve a barra lateral: o servidor
       já decidiu o idioma (cookie) e mandou o mapa das chaves estáticas. */
    aplicar: function (idioma, textos) {
      i18n.idioma = idioma === "en" ? "en" : "pt";
      i18n.textos = textos || VAZIO;
      document.documentElement.lang = i18n.idioma === "en" ? "en" : "pt-BR";
      traduzir(document.body);
    },

    /* Depois de cada troca de view: os data-i18n* que o servidor não traduz. */
    traduzirView: function () {
      traduzir(document.getElementById("app-shell"));
    }
  };

  TN.i18n = i18n;

  /* O texto da interface em português na chave: procura no namespace do
     módulo, depois no comum, e sem achar devolve o próprio texto. */
  TN.t = function (namespace, texto) {
    if (!texto || i18n.idioma !== "en") return texto;
    const chave = String(texto).replace(/\s+/g, " ").trim();
    const doModulo = i18n.textos[namespace];
    if (doModulo && Object.prototype.hasOwnProperty.call(doModulo, chave)) {
      return doModulo[chave];
    }
    const comum = i18n.textos.comum;
    if (comum && Object.prototype.hasOwnProperty.call(comum, chave)) return comum[chave];
    return texto;
  };

  /* O namespace do módulo da tela aberta, lido do data-tela da barra lateral. */
  function namespaceDaTela() {
    const barra = document.getElementById("main-nav");
    const caminho = barra && barra.dataset ? barra.dataset.tela || "" : "";
    const partes = caminho.split("/").filter(function (parte) {
      return parte && parte !== "_views";
    });
    const modulo = (partes[0] || "").replace(/\.html$/, "");
    return modulo || "comum";
  }

  function traduzirElemento(elemento, namespace) {
    CADEIA_DE_ATRIBUTOS.forEach(function (par) {
      const marca = elemento.getAttribute(par[0]);
      if (marca === null) return;
      const traduzido = TN.t(namespace, marca);
      if (par[1] === "textContent") elemento.textContent = traduzido;
      else elemento.setAttribute(par[1], traduzido);
    });
  }

  function traduzir(raiz) {
    if (!raiz || i18n.idioma !== "en") return;
    const namespace = namespaceDaTela();
    const marcados = raiz.querySelectorAll("[data-i18n], [data-i18n-title], [data-i18n-aria-label], [data-i18n-placeholder]");
    Array.prototype.forEach.call(marcados, function (elemento) {
      traduzirElemento(elemento, namespace);
    });
  }
})();
