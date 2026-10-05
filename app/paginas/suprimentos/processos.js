/* ============================================================
   processos.js — Comportamento da tela Processos de compra (suprimentos/processos)

   Da requisição ao pedido ou contrato: RFx, equalização, ranking e aprovação por alçada.

   Registra um único objeto em TN.paginas["suprimentos/processos"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela
   (carregando, vazio-origem, vazio-filtro, erro ou sem-permissao) mora no
   x-data da view, que já abre no vazio de origem.

   Sem comportamento próprio ainda: iniciar() só confirma o vazio de origem,
   que vale até a carga dos dados chegar com as ISSUE-059 e ISSUE-060.

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  window.TN.paginas["suprimentos/processos"] = {
    iniciar: function (raiz) {
      window.Alpine.$data(raiz).estado = "vazio-origem";
    }
  };
})();
