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

  var ESTADOS_DE_RESULTADO = ["conteudo", "vazio-origem", "vazio-filtro"];

  function definirEstado(raiz, estado) {
    window.Alpine.$data(raiz).estado = estado;
  }

  function filhas(tabela, codigo) {
    var linhas = Array.prototype.slice.call(tabela.querySelectorAll("tr[data-codigo]"));
    return linhas.filter(function (linha) {
      var c = linha.getAttribute("data-codigo");
      if (c === codigo) return false;
      return codigo === "0" || c.indexOf(codigo + ".") === 0;
    });
  }

  function alternar(botao) {
    var tabela = botao.closest("table");
    var codigo = botao.getAttribute("data-alternar");
    var recolher = botao.getAttribute("aria-expanded") === "true";
    botao.setAttribute("aria-expanded", recolher ? "false" : "true");
    var rotulo = (recolher ? "Expandir " : "Recolher ") + codigo;
    botao.setAttribute("aria-label", rotulo);
    botao.setAttribute("title", rotulo);
    filhas(tabela, codigo).forEach(function (linha) {
      linha.hidden = recolher;
      var proprio = linha.querySelector("[data-alternar]");
      if (proprio) {
        // Ao expandir um pai, os descendentes voltam abertos.
        proprio.setAttribute("aria-expanded", "true");
      }
    });
  }

  function atualizarExportacao(raiz) {
    var form = raiz.querySelector("[data-filtros]");
    if (!form) return;
    var consulta = new URLSearchParams(new FormData(form)).toString();
    raiz.querySelectorAll("[data-exportar]").forEach(function (link) {
      var base = link.getAttribute("href").split("?")[0];
      link.setAttribute("href", consulta ? base + "?" + consulta : base);
    });
  }

  function aoResponder(raiz) {
    var marcador = raiz.querySelector("[data-resultado]");
    var resultado = marcador && marcador.getAttribute("data-resultado");
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
        var status = e.detail && e.detail.status;
        if (status === 403) definirEstado(raiz, "sem-permissao");
        else if (status !== 422 && status !== 409) definirEstado(raiz, "erro");
      });

      raiz.addEventListener("click", function (e) {
        var botao = e.target.closest("[data-alternar]");
        if (botao && raiz.contains(botao)) alternar(botao);
      });

      raiz.addEventListener("change", function () { atualizarExportacao(raiz); });
    }
  };
})();
