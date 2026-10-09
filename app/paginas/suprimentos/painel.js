/* ============================================================
   painel.js — Comportamento da tela Painel de suprimentos (suprimentos/painel)

   Indicadores, curva de contratação, avanço do MAS e pedidos críticos (ISSUE-063).

   Registra um único objeto em TN.paginas["suprimentos/painel"]. A view o aciona por x-init com
   iniciar(raiz), e raiz é o <main> da tela. O estado da tela (carregando, conteudo, erro ou
   sem-permissao) mora no x-data da view; o vazio de origem vem do servidor, dentro do fragmento.
   O servidor desenha tudo (api/src/templates/suprimentos/painel.html): KPIs, gráficos
   (data-grafico + data-dados), a tabela e as exportações são links e botões genéricos. Aqui
   mora só a carga inicial e a nova tentativa.

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  function raizDaTela() {
    return document.querySelector("main.pagina--suprimentos-painel");
  }

  function estadoDaTela(estado) {
    const raiz = raizDaTela();
    if (raiz) window.Alpine.$data(raiz).estado = estado;
  }

  function aoFalhar(evento) {
    if (!raizDaTela()) return;
    if (evento.detail && evento.detail.status === 403) estadoDaTela("sem-permissao");
    else estadoDaTela("erro");
  }

  window.TN.paginas["suprimentos/painel"] = {
    iniciar: function (raiz) {
      const dados = window.Alpine.$data(raiz);

      /* Só a primeira carga decide entre erro e sem permissão; depois de aberta, a tela se
         mantém e a falha de uma ação vira toast (ds/ui.js). */
      function aoErro(evento) {
        if (!raiz.isConnected) {
          document.removeEventListener("ajax:error", aoErro);
          return;
        }
        if (dados.estado !== "carregando") return;
        aoFalhar(evento);
      }

      function carregar() {
        dados.estado = "carregando";
        dados
          .carregar()
          .then(function () {
            if (dados.estado === "carregando") dados.estado = "conteudo";
          })
          .catch(function () {
            /* aoErro já escolheu o estado a partir do ajax:error */
          });
      }

      document.addEventListener("ajax:error", aoErro);
      raiz.addEventListener("click", function (evento) {
        if (evento.target.closest("[data-painel-recarregar]")) carregar();
      });
      carregar();
    }
  };
})();
