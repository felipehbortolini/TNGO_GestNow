/* ============================================================
   programacao.js — Comportamento da tela Programação (programacao_semanal/programacao)

   Matriz de atividades de segunda a domingo, com previsto e realizado por turno.

   Registra um único objeto em TN.paginas["programacao_semanal/programacao"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela
   (carregando, vazio-origem, vazio-filtro, erro ou sem-permissao) mora no
   x-data da view, que já abre no vazio de origem.

   Sem comportamento próprio ainda: iniciar() só confirma o vazio de origem,
   que vale até a carga dos dados chegar com as ISSUE-051 e ISSUE-052.

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  window.TN.paginas["programacao_semanal/programacao"] = {
    iniciar: function (raiz) {
      window.Alpine.$data(raiz).estado = "vazio-origem";
    }
  };
})();
