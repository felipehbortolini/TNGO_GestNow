/* ============================================================
   programacao.js — Comportamento da tela Programação (programacao_semanal/programacao)

   Matriz de atividades de segunda a domingo, com previsto e realizado por turno.

   Registra um único objeto em TN.paginas["programacao_semanal/programacao"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela
   (carregando, pronto, erro ou sem-permissao) mora no x-data da view; os
   vazios de origem e de filtro vêm do servidor, dentro da matriz.

   iniciar() pede ao servidor, em paralelo, o aviso da janela, a barra de
   ferramentas e a matriz com a faixa de indicadores. Todo o resto (ordenar,
   filtrar, abrir o painel, gravar, excluir) é hipermídia: os fragmentos já
   trazem o $ajax e o x-target. O ?acao=nova, que o escopo deixa ao escolher
   um projeto no Portfólio, abre o painel de nova atividade.

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const BASE = "/api/programacao-semanal";
  const HTTP_PROIBIDO = 403;

  /* $ajax é magic: só devolve promessa quando chamado no escopo do Alpine. Por
     Alpine.evaluate o evaluator aguarda a promessa e devolve undefined antes. */
  function pedir(raiz, endereco, alvos) {
    return window.Alpine.$data(raiz).$ajax(endereco, { targets: alvos });
  }

  function consultaDaSemana() {
    const semana = new URLSearchParams(window.location.search).get("semana");
    return semana ? "?semana=" + encodeURIComponent(semana) : "";
  }

  function vigiarRecusa(raiz, dados) {
    raiz.addEventListener("ajax:error", function (e) {
      if (dados.estado === "carregando" && e.detail && e.detail.status === HTTP_PROIBIDO) {
        dados.recusado = true;
      }
    });
  }

  window.TN.paginas["programacao_semanal/programacao"] = {
    /* Prende o menu de ações da linha ao botão que o abriu. O painel é fixed
       porque a matriz rola: um menu absoluto seria cortado pela rolagem da
       tabela. Vira para cima quando não cabe embaixo. */
    ancorarMenu: function (menu, botao) {
      if (!menu || !botao) return;
      const alvo = botao.getBoundingClientRect();
      const altura = menu.offsetHeight;
      const acima = window.innerHeight - alvo.bottom < altura + 12 && alvo.top > altura + 12;
      menu.style.left = "auto";
      menu.style.right = Math.max(8, window.innerWidth - alvo.right) + "px";
      menu.style.top = (acima ? alvo.top - altura - 6 : alvo.bottom + 6) + "px";
    },

    iniciar: function (raiz) {
      const dados = window.Alpine.$data(raiz);
      const consulta = consultaDaSemana();
      const acao = window.TN.escopo ? window.TN.escopo.acaoPendente() : null;
      dados.estado = "carregando";
      dados.recusado = false;
      if (!raiz.dataset.vigiando) {
        raiz.dataset.vigiando = "1";
        vigiarRecusa(raiz, dados);
      }
      Promise.all([
        pedir(raiz, BASE + "/programacoes/janela" + consulta, ["prog-janela"]),
        pedir(raiz, BASE + "/programacoes/filtros" + consulta, ["prog-filtros"]),
        pedir(raiz, BASE + "/programacoes" + consulta, ["prog-resumo", "prog-tabela"])
      ]).then(function () {
        dados.estado = dados.recusado ? "sem-permissao" : "pronto";
        if (acao === "nova" && dados.estado === "pronto") {
          pedir(raiz, BASE + "/atividades/formulario" + consulta, ["drawer"]);
        }
      }).catch(function () {
        dados.estado = dados.recusado ? "sem-permissao" : "erro";
      });
    }
  };
})();
