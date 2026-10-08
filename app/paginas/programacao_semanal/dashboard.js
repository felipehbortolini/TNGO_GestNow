/* ============================================================
   dashboard.js — Comportamento da tela Dashboard da programação (programacao_semanal/dashboard)

   Aderência, ranking, mapa de calor, turnos e gargalos da programação semanal.

   Registra um único objeto em TN.paginas["programacao_semanal/dashboard"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela (carregando,
   pronto, erro ou sem-permissao) mora no x-data da view; a barra de filtros (#dash-filtros)
   carrega sozinha pelo x-init da view e o painel (#dash-painel) é buscado aqui com a query
   da página (o projeto do escopo). Trocar um filtro é hipermídia: o formulário do fragmento
   tem x-target="dash-painel", então só o painel redesenha.

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const BASE = "/api/programacao-semanal";
  const HTTP_PROIBIDO = 403;

  /* $ajax é magic: só devolve promessa quando chamado no escopo do Alpine. Por
     Alpine.evaluate o evaluator aguarda a promessa e devolve undefined antes. */
  function pedir(raiz, endereco, alvo) {
    return window.Alpine.$data(raiz).$ajax(endereco, { target: alvo });
  }

  function vigiarRecusa(raiz, dados) {
    raiz.addEventListener("ajax:error", function (e) {
      if (dados.estado === "carregando" && e.detail && e.detail.status === HTTP_PROIBIDO) {
        dados.recusado = true;
      }
    });
  }

  window.TN.paginas["programacao_semanal/dashboard"] = {
    iniciar: function (raiz) {
      const dados = window.Alpine.$data(raiz);
      dados.estado = "carregando";
      dados.recusado = false;
      if (!raiz.dataset.vigiando) {
        raiz.dataset.vigiando = "1";
        vigiarRecusa(raiz, dados);
      }
      pedir(raiz, BASE + "/dashboard" + window.location.search, "dash-painel")
        .then(function () {
          dados.estado = dados.recusado ? "sem-permissao" : "pronto";
        })
        .catch(function () {
          dados.estado = dados.recusado ? "sem-permissao" : "erro";
        });
    }
  };
})();
