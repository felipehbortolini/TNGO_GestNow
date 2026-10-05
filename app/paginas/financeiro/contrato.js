/* ============================================================
   contrato.js — Comportamento da tela Contrato (financeiro/contrato)

   Ficha do contrato: valores, medições, aditivos, marcos, claims, extensões de prazo e avaliação.

   Registra um único objeto em TN.paginas["financeiro/contrato"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela
   (carregando, vazio-origem, vazio-filtro, erro ou sem-permissao) mora no
   x-data da view, que já abre no vazio de origem.

   Sem comportamento próprio ainda: iniciar() só confirma o vazio de origem,
   que vale até a carga dos dados chegar com as ISSUE-032 a ISSUE-034.

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  window.TN.paginas["financeiro/contrato"] = {
    iniciar: function (raiz) {
      window.Alpine.$data(raiz).estado = "vazio-origem";
    }
  };
})();
