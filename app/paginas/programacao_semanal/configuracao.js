/* ============================================================
   configuracao.js — Comportamento da tela Configuração da programação (programacao_semanal/configuracao)

   Parâmetros e janelas da programação semanal, uma configuração por projeto.

   Registra um único objeto em TN.paginas["programacao_semanal/configuracao"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela (carregando,
   pronto, erro ou sem-permissao) mora no x-data da view; o painel vem do servidor,
   dentro de #config-painel. Todo o resto (salvar, recusar) é hipermídia: os fragmentos
   já trazem os formulários e o x-target.

   marcar(botao) é o atalho do seletor de semanas do app: o botão carrega o ano, o
   trimestre e o valor em data-*, e o formulário do cartão é quem tem as pastilhas.

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

  window.TN.paginas["programacao_semanal/configuracao"] = {
    iniciar: function (raiz) {
      const dados = window.Alpine.$data(raiz);
      dados.estado = "carregando";
      dados.recusado = false;
      if (!raiz.dataset.vigiando) {
        raiz.dataset.vigiando = "1";
        vigiarRecusa(raiz, dados);
      }
      pedir(raiz, BASE + "/configuracao", "config-painel")
        .then(function () {
          dados.estado = dados.recusado ? "sem-permissao" : "pronto";
        })
        .catch(function () {
          dados.estado = dados.recusado ? "sem-permissao" : "erro";
        });
    },

    marcar: function (botao) {
      const form = botao.closest("form");
      if (!form) {
        return;
      }
      const ano = botao.dataset.marcarAno;
      const tri = botao.dataset.marcarTri;
      const valor = botao.dataset.marcarValor === "sim";
      let seletor = '[data-ano="' + ano + '"]';
      if (tri) {
        seletor += '[data-tri="' + tri + '"]';
      }
      form.querySelectorAll(seletor).forEach(function (campo) {
        campo.checked = valor;
      });
    }
  };
})();
