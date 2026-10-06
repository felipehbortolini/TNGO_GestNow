/* ============================================================
   dashboard.js — Comportamento da tela Dashboards e KPIs (central_acoes/dashboard)

   Indicadores do motor de status único por origem, responsável e projeto (ISSUE-020, HU-050).

   Registra um único objeto em TN.paginas["central_acoes/dashboard"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela (carregando, conteudo,
   erro ou sem-permissao) mora no x-data da view; os estados vazio de origem e vazio por filtro
   vêm do servidor, dentro do fragmento.

   O servidor desenha tudo (api/src/templates/central_acoes/painel.html): KPIs, os gráficos da
   biblioteca (que o motor de app/ds/graficos monta sozinho, observando o DOM trocado), a tabela
   por projeto no Portfólio, o desempenho por responsável e as exportações. O filtro de origem
   é um formulário GET com x-target no próprio fragmento; aqui só moram os cinco estados.

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  window.TN.paginas["central_acoes/dashboard"] = {
    iniciar: function (raiz) {
      const dados = window.Alpine.$data(raiz);

      /* Só a primeira carga decide entre erro e sem permissão; depois de aberta, a tela se
         mantém e a falha de uma ação vira toast (ds/ui.js). */
      function aoFalhar(evento) {
        if (!raiz.isConnected) {
          document.removeEventListener("ajax:error", aoFalhar);
          return;
        }
        if (dados.estado !== "carregando") return;
        dados.estado = evento.detail && evento.detail.status === 403 ? "sem-permissao" : "erro";
      }

      function carregar() {
        dados.estado = "carregando";
        dados
          .carregar()
          .then(function () {
            if (dados.estado === "carregando") dados.estado = "conteudo";
          })
          .catch(function () {
            /* aoFalhar já escolheu o estado a partir do ajax:error */
          });
      }

      document.addEventListener("ajax:error", aoFalhar);
      raiz.addEventListener("click", function (evento) {
        if (evento.target.closest("[data-painel-recarregar]")) carregar();
      });
      carregar();
    }
  };
})();
