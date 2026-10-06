/* ============================================================
   eac.js — Comportamento da tela EAC (financeiro/eac)

   Árvore da Estrutura Analítica de Custos.

   Registra um único objeto em TN.paginas["financeiro/eac"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela
   (carregando, conteudo, vazio-origem, vazio-filtro, erro ou sem-permissao) mora
   no x-data da view e vem do marcador data-resultado que o servidor põe no
   conteúdo; 403 vira sem-permissao e qualquer outra falha vira erro.

   Também cuida de recolher e expandir a árvore (os totais já vêm somados do
   servidor, aqui só se esconde linha) e de manter os links de Excel e PDF com
   os mesmos filtros que a tela mostra.

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const ESTADOS_DE_RESULTADO = ["conteudo", "vazio-origem", "vazio-filtro"];

  function definirEstado(raiz, estado) {
    window.Alpine.$data(raiz).estado = estado;
  }

  function filhas(tabela, codigo) {
    const linhas = Array.prototype.slice.call(tabela.querySelectorAll("tr[data-codigo]"));
    return linhas.filter(function (linha) {
      const c = linha.getAttribute("data-codigo");
      if (c === codigo) return false;
      return codigo === "0" || c.indexOf(codigo + ".") === 0;
    });
  }

  function alternar(botao) {
    const tabela = botao.closest("table");
    const codigo = botao.getAttribute("data-alternar");
    const recolher = botao.getAttribute("aria-expanded") === "true";
    botao.setAttribute("aria-expanded", recolher ? "false" : "true");
    const rotulo = (recolher ? "Expandir " : "Recolher ") + codigo;
    botao.setAttribute("aria-label", rotulo);
    botao.setAttribute("title", rotulo);
    filhas(tabela, codigo).forEach(function (linha) {
      linha.hidden = recolher;
      const proprio = linha.querySelector("[data-alternar]");
      if (proprio) {
        // Ao expandir um pai, os descendentes voltam abertos.
        proprio.setAttribute("aria-expanded", "true");
      }
    });
  }

  function atualizarExportacao(raiz) {
    const form = raiz.querySelector("[data-filtros]");
    if (!form) return;
    const consulta = new URLSearchParams(new FormData(form)).toString();
    raiz.querySelectorAll("[data-exportar]").forEach(function (link) {
      const base = link.getAttribute("href").split("?")[0];
      link.setAttribute("href", consulta ? base + "?" + consulta : base);
    });
  }

  function aoResponder(raiz) {
    const marcador = raiz.querySelector("[data-resultado]");
    const resultado = marcador && marcador.getAttribute("data-resultado");
    definirEstado(raiz, ESTADOS_DE_RESULTADO.indexOf(resultado) >= 0 ? resultado : "erro");
    atualizarExportacao(raiz);
  }

  window.TN.paginas["financeiro/eac"] = {
    iniciar: function (raiz) {
      definirEstado(raiz, "carregando");

      raiz.addEventListener("ajax:success", function (e) {
        if (!e.target.closest("[data-filtros]") && !e.target.closest("#eac-conteudo")) return;
        window.setTimeout(function () { aoResponder(raiz); }, 0);
      });

      raiz.addEventListener("ajax:error", function (e) {
        const status = e.detail && e.detail.status;
        if (status === 403) definirEstado(raiz, "sem-permissao");
        else if (status !== 422 && status !== 409) definirEstado(raiz, "erro");
      });

      raiz.addEventListener("click", function (e) {
        const botao = e.target.closest("[data-alternar]");
        if (botao && raiz.contains(botao)) alternar(botao);
      });

      raiz.addEventListener("change", function () { atualizarExportacao(raiz); });
    }
  };
})();
