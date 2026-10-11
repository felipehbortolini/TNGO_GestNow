/* ============================================================
   home.js — Comportamento da tela Início (inicio/home)

   Indicadores-chave por módulo, pontos de atenção e cards dos módulos (ISSUE-079).

   Registra um único objeto em TN.paginas["inicio/home"]. A view o aciona por x-init com
   iniciar(raiz), e raiz é o <main> da tela. O estado da tela (carregando, conteudo, erro ou
   sem-permissao) mora no x-data da view; o vazio de origem vem do servidor, dentro do
   fragmento (api/src/templates/inicio/home.html). O servidor desenha tudo — barra de
   contexto, indicadores, pontos de atenção, cards e as exportações — e aqui mora só a
   carga inicial e a nova tentativa. Os links de indicador, atenção e card são âncoras
   normais com data-tn-tela: a navegação é a do shell.

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  function raizDaTela() {
    return document.querySelector("main.pagina--inicio-home");
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

  window.TN.paginas["inicio/home"] = {
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
        if (evento.target.closest("[data-home-recarregar]")) carregar();
      });
      carregar();
    }
  };
})();
