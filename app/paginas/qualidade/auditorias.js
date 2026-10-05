/* ============================================================
   auditorias.js — Comportamento da tela Auditorias (qualidade/auditorias)

   Programa de auditorias, resultado, constatações e reprogramação.

   Registra um único objeto em TN.paginas["qualidade/auditorias"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela
   (carregando, vazio-origem, vazio-filtro, erro ou sem-permissao) mora no
   x-data da view, que já abre no vazio de origem.

   Sem comportamento próprio ainda: iniciar() só confirma o vazio de origem,
   que vale até a carga dos dados chegar com a ISSUE-070.

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  window.TN.paginas["qualidade/auditorias"] = {
    iniciar: function (raiz) {
      window.Alpine.$data(raiz).estado = "vazio-origem";
    }
  };
})();
