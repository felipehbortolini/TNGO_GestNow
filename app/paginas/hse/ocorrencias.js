/* ============================================================
   ocorrencias.js — Comportamento da tela Ocorrências (hse/ocorrencias)

   Registro, investigação, ações corretivas, tratamento e encerramento das
   ocorrências, com prazos legais e dado restrito (LGPD).

   Registra um único objeto em TN.paginas["hse/ocorrencias"]. A view o aciona
   por x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela
   (carregando, conteudo, erro ou sem-permissao) mora no x-data da view; o
   vazio de origem vem do servidor, dentro do fragmento.

   O servidor desenha tudo (api/src/templates/hse/): indicadores, filtros,
   tabela e páginas são links ou um formulário GET com x-target. Aqui só moram
   os modais que o Design System abre por JavaScript: a ficha e os formulários
   do fluxo (nova, investigar, ação, tratamento e encerrar), cujo corpo o
   servidor entrega por GET em #ocorrencias-modal-corpo. Depois de uma
   gravação o fragmento traz um marcador oculto que reabre a ficha. No
   Portfólio o botão de inclusão pede o projeto antes (data-tn-incluir,
   ds/shell.js) e a tela reabre no projeto com a ação pedida
   (TN.escopo.acaoPendente).

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const ALVO_DO_MODAL = "ocorrencias-modal-corpo";
  const LARGURA_PADRAO = 640;
  const LARGURA_DA_FICHA = 960;

  /* O corpo do modal pede o fragmento ao servidor assim que o Alpine o inicializa; o endereço
     vai por data-url para nunca ser interpolado dentro de uma expressão. */
  function corpoCarregando(endereco) {
    return (
      '<div id="' + ALVO_DO_MODAL + '" data-url="' + window.TN.esc(endereco) + '"' +
      " x-init=\"$ajax($el.dataset.url, { target: '" + ALVO_DO_MODAL + "' })\">" +
      '<div class="spinner" role="status" aria-label="Carregando"></div></div>'
    );
  }

  /* Uma opção por modal: o título, o subtítulo, o endereço do fragmento, a largura e o que
     fazer ao fechar (para a lista se atualizar depois de uma gravação). */
  function abrirModal(opcoes) {
    window.TN.modal({
      title: opcoes.titulo,
      subtitle: opcoes.subtitulo,
      width: Number(opcoes.largura) || LARGURA_PADRAO,
      body: corpoCarregando(opcoes.url),
      onClose: opcoes.aoFechar
    });
  }

  function abrirDoBotao(botao, aoFechar) {
    abrirModal({
      titulo: botao.dataset.ocorrenciasModalTitulo,
      subtitulo: botao.dataset.ocorrenciasModalSubtitulo,
      url: botao.dataset.ocorrenciasModalUrl,
      largura: botao.dataset.ocorrenciasModalLargura,
      aoFechar: aoFechar
    });
  }

  function abrirFicha(codigo) {
    abrirModal({
      titulo: "Ocorrência " + codigo,
      subtitulo: "Registro, investigação, ações e histórico",
      url: "/api/hse/ocorrencias/" + encodeURIComponent(codigo) + "/ficha",
      largura: LARGURA_DA_FICHA
    });
  }

  function fecharModalDe(elemento) {
    const fundo = elemento.closest(".modal-backdrop");
    const fechar = fundo ? fundo.querySelector(".modal__close") : null;
    if (fechar) fechar.click();
  }

  window.TN.paginas["hse/ocorrencias"] = {
    iniciar: function (raiz) {
      const dados = window.Alpine.$data(raiz);
      let urlAtual = null;

      /* Só a primeira carga decide entre erro e sem permissão; depois de aberta, a tela se
         mantém e a falha de uma ação vira toast (ds/ui.js) ou a mensagem no modal. */
      function aoFalhar(evento) {
        if (!raiz.isConnected) {
          document.removeEventListener("ajax:error", aoFalhar);
          return;
        }
        if (dados.estado !== "carregando") return;
        dados.estado = evento.detail && evento.detail.status === 403 ? "sem-permissao" : "erro";
      }

      function carregar(url) {
        dados.estado = "carregando";
        urlAtual = url || null;
        return dados
          .carregar(url)
          .then(function () {
            if (dados.estado === "carregando") dados.estado = "conteudo";
          })
          .catch(function () {
            /* aoFalhar já escolheu o estado a partir do ajax:error */
          });
      }

      /* A ação pedida pelo mecanismo de inclusão do Portfólio: abre o formulário já na tela. */
      function atenderAcaoPendente(acao) {
        if (acao !== "nova") return;
        carregar(null).then(function () {
          abrirModal({
            titulo: "Nova ocorrência",
            subtitulo: "Fluxo: Registrada, Em investigação, Ações definidas, Em tratamento, Encerrada",
            url: "/api/hse/ocorrencias/nova",
            largura: 920,
            aoFechar: function () { carregar(urlAtual); }
          });
        });
      }

      /* Um só ouvinte por tela, preso à raiz; o modal mora fora dela (o Design System o anexa
         ao fim do <body>), por isso o do botão Cancelar é do documento e só um o atende. */
      raiz.addEventListener("click", function (evento) {
        const abrir = evento.target.closest("[data-ocorrencias-modal-url]");
        if (abrir) abrirDoBotao(abrir, function () { carregar(urlAtual); });
        else if (evento.target.closest("[data-ocorrencias-recarregar]")) carregar(urlAtual);
      });
      document.addEventListener("click", function aoCancelar(evento) {
        if (!raiz.isConnected) {
          document.removeEventListener("click", aoCancelar);
          return;
        }
        const cancelar = evento.target.closest ? evento.target.closest("[data-ocorrencias-fechar-modal]") : null;
        if (cancelar) fecharModalDe(cancelar);
      });
      document.addEventListener("ajax:error", aoFalhar);

      const acao = window.TN.escopo ? window.TN.escopo.acaoPendente() : null;
      carregar(null).then(function () { atenderAcaoPendente(acao); });
    },

    /* Depois de uma gravação o fragmento da lista traz o marcador oculto com o número da
       ocorrência: este abre a ficha atualizada no lugar do modal que se fechou. */
    abrirFicha: function (marcador) {
      const codigo = marcador.getAttribute("data-ocorrencias-abrir-ficha");
      window.setTimeout(function () { abrirFicha(codigo); }, 50);
    }
  };
})();
