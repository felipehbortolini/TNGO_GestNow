/* ============================================================
   configuracao.js — Comportamento da tela Configuração da programação (programacao_semanal/configuracao)

   Parâmetros, janelas por empresa, semanas liberadas e liberações extraordinárias, uma configuração por projeto.

   Registra um único objeto em TN.paginas["programacao_semanal/configuracao"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela
   (carregando, pronto, erro ou sem-permissao) mora no x-data da view; os
   vazios (sem projeto escolhido, sem empresa) vêm do servidor, dentro de
   #config-area.

   iniciar() pede ao servidor a configuração do escopo (o resumo somente
   leitura no Portfólio, a do projeto nos demais casos). Gravar parâmetros e
   janelas é hipermídia: os formulários já trazem o x-target e o servidor
   devolve a tela inteira com o aviso de sucesso.

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const ENDERECO = "/api/programacao-semanal/configuracoes";
  const HTTP_PROIBIDO = 403;

  function pedir(raiz, endereco, alvos) {
    return window.Alpine.evaluate(raiz, "$ajax(endereco, { targets: alvos })", {
      scope: { endereco: endereco, alvos: alvos }
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
      pedir(raiz, ENDERECO, ["config-area"]).then(function () {
        dados.estado = dados.recusado ? "sem-permissao" : "pronto";
      }).catch(function () {
        dados.estado = dados.recusado ? "sem-permissao" : "erro";
      });
    }
  };
})();
