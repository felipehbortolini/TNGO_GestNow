/* ============================================================
   dashboard.js — Comportamento da tela Dashboards e KPIs (central_acoes/dashboard)

   Indicadores das ações por origem, responsável e projeto, calculados pelo status único.

   Registra um único objeto em TN.paginas["central_acoes/dashboard"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela
   (carregando, vazio-origem, vazio-filtro, erro ou sem-permissao) mora no
   x-data da view, que já abre no vazio de origem.

   Sem comportamento próprio ainda: iniciar() só confirma o vazio de origem,
   que vale até a carga dos dados chegar com a ISSUE-020.

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  window.TN.paginas["central_acoes/dashboard"] = {
    iniciar: function (raiz) {
      window.Alpine.$data(raiz).estado = "vazio-origem";
    }
  };
})();
