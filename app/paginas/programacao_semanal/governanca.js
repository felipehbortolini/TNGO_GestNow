/* ============================================================
   governanca.js — Comportamento da tela Governança da programação (programacao_semanal/governanca)

   Painel por contratada e semana, pedidos de alteração e trilha de auditoria.

   Registra um único objeto em TN.paginas["programacao_semanal/governanca"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela (carregando,
   pronto, erro ou sem-permissao) mora no x-data da view; o painel vem do servidor,
   dentro de #gov-painel, e traz a fila (#gov-pedidos) e a trilha (#gov-trilha) por
   $ajax nos próprios fragmentos. Todo o resto (decidir um pedido) é hipermídia: os
   fragmentos já trazem o formulário e o x-target.

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const BASE = "/api/programacao-semanal";
  const HTTP_PROIBIDO = 403;

  function pedir(raiz, endereco, alvo) {
    return window.Alpine.evaluate(raiz, "$ajax(endereco, { target: alvo })", {
      scope: { endereco: endereco, alvo: alvo }
    });
  }

  function vigiarRecusa(raiz, dados) {
    raiz.addEventListener("ajax:error", function (e) {
      if (dados.estado === "carregando" && e.detail && e.detail.status === HTTP_PROIBIDO) {
        dados.recusado = true;
      }
    });
  }

  window.TN.paginas["programacao_semanal/governanca"] = {
    iniciar: function (raiz) {
      const dados = window.Alpine.$data(raiz);
      dados.estado = "carregando";
      dados.recusado = false;
      if (!raiz.dataset.vigiando) {
        raiz.dataset.vigiando = "1";
        vigiarRecusa(raiz, dados);
      }
      pedir(raiz, BASE + "/governanca", "gov-painel")
        .then(function () {
          dados.estado = dados.recusado ? "sem-permissao" : "pronto";
        })
        .catch(function () {
          dados.estado = dados.recusado ? "sem-permissao" : "erro";
        });
    }
  };
})();
