/* ============================================================
   diligenciamento.js — Comportamento da tela Diligenciamento e recebimento (suprimentos/diligenciamento)

   Marcos dos pedidos, folga sobre o ROS, riscos sugeridos e recebimento.

   Registra um único objeto em TN.paginas["suprimentos/diligenciamento"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela
   (carregando, vazio-origem, vazio-filtro, erro ou sem-permissao) mora no
   x-data da view, que já abre no vazio de origem.

   Sem comportamento próprio ainda: iniciar() só confirma o vazio de origem,
   que vale até a carga dos dados chegar com a ISSUE-061.

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  window.TN.paginas["suprimentos/diligenciamento"] = {
    iniciar: function (raiz) {
      window.Alpine.$data(raiz).estado = "vazio-origem";
    }
  };
})();
