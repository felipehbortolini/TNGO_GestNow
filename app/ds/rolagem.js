/* ============================================================
   rolagem.js — Rolagem horizontal acessível do .tbl-wrap (ISSUE-091)

   Uma tabela mais larga que a coluna rola dentro do .tbl-wrap, e quem usa
   teclado não alcançava a parte cortada: o contêiner de rolagem precisa ser
   focável (WCAG 2.1.1; é o `scrollable-region-focusable` do axe). Só a
   rolagem real vira parada de Tab — tabela que cabe não ganha foco — e o
   nome acessível sai do <caption>, do aria-label da tabela, do título do
   card ou de um rótulo genérico, para o leitor de tela dizer o que rola.

   Roda na carga, a cada mutação do DOM (os fragmentos do Alpine AJAX) e no
   redimensionamento, como o motor dos gráficos. O anel de foco do .tbl-wrap
   está na regra única de :focus-visible em tokens.css.

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const SELETOR = ".tbl-wrap";
  const MARCA = "data-tn-rolagem";
  const ROTULO_PADRAO = "Tabela com rolagem";

  function rola(quadro) {
    return (
      quadro.scrollWidth > quadro.clientWidth + 1 ||
      quadro.scrollHeight > quadro.clientHeight + 1
    );
  }

  function texto(elemento) {
    return elemento ? elemento.textContent.trim().replace(/\s+/g, " ") : "";
  }

  function nomeDoQuadro(quadro) {
    const legenda = texto(quadro.querySelector("caption"));
    if (legenda) return legenda;
    const tabela = quadro.querySelector("table[aria-label]");
    if (tabela) return tabela.getAttribute("aria-label").trim();
    const card = quadro.closest("section, .card");
    const titulo = texto(card && card.querySelector(".card__head"));
    if (titulo) return titulo;
    if (window.TN && window.TN.t) return window.TN.t("comum", ROTULO_PADRAO);
    return ROTULO_PADRAO;
  }

  function marcar(quadro) {
    if (rola(quadro)) {
      if (quadro.hasAttribute("tabindex")) return;
      quadro.setAttribute("tabindex", "0");
      quadro.setAttribute("role", "group");
      quadro.setAttribute("aria-label", nomeDoQuadro(quadro));
      quadro.setAttribute(MARCA, "1");
      return;
    }
    if (!quadro.hasAttribute(MARCA)) return;
    quadro.removeAttribute("tabindex");
    quadro.removeAttribute("role");
    quadro.removeAttribute("aria-label");
    quadro.removeAttribute(MARCA);
  }

  function marcarTudo() {
    document.querySelectorAll(SELETOR).forEach(marcar);
  }

  let quadro = null;

  function agendar() {
    if (quadro !== null) return;
    quadro = window.requestAnimationFrame(function () {
      quadro = null;
      marcarTudo();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", agendar);
  } else {
    window.setTimeout(agendar, 0);
  }
  /* childList pega o fragmento que chega; attributes, o x-show que revela a
     tabela depois (display: none zera a medida). As escritas daqui também
     disparam o observador, mas a varredura é idempotente e para sozinha. */
  new MutationObserver(agendar).observe(document.body, {
    childList: true,
    subtree: true,
    attributes: true,
  });
  window.addEventListener("load", agendar);
  window.addEventListener("resize", agendar);
})();
