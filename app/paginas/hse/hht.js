/* ============================================================
   hht.js — Comportamento da tela Horas trabalhadas (HHT) (hse/hht)

   Horas-homem trabalhadas e efetivo médio por mês e por empresa, com importação e histograma.

   Registra um único objeto em TN.paginas["hse/hht"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela
   (carregando, conteudo, erro ou sem-permissao) mora no x-data da view; o vazio de origem vem
   do servidor, dentro do fragmento.

   O servidor desenha tudo (api/src/templates/hse/): indicadores, tabela, abas e página são links
   com x-target. Aqui só moram os modais que o Design System abre por JavaScript: o formulário
   do registro e a importação de planilha, cujo corpo o servidor entrega por GET em
   #hse-modal-corpo. Depois de uma importação a tela se recarrega ao fechar o modal. No
   Portfólio o botão de inclusão pede o projeto antes (data-tn-incluir, ds/shell.js) e a tela
   reabre no projeto com a ação pedida (TN.escopo.acaoPendente).

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const CHAVE = "hse/hht";
  const ALVO_DO_MODAL = "hse-modal-corpo";
  const LARGURA_PADRAO = 640;

  /* O corpo do modal pede o fragmento ao servidor assim que o Alpine o inicializa; o endereço
     vai por data-url para nunca ser interpolado dentro de uma expressão. */
  function corpoCarregando(endereco) {
    return (
      '<div id="' + ALVO_DO_MODAL + '" data-url="' + window.TN.esc(endereco) + '"' +
      " x-init=\"$ajax($el.dataset.url, { target: '" + ALVO_DO_MODAL + "' })\">" +
      '<div class="spinner" role="status" aria-label="Carregando"></div></div>'
    );
  }

  function abrirFormulario(botao, aoFechar) {
    window.TN.modal({
      title: botao.dataset.hseModalTitulo,
      subtitle: botao.dataset.hseModalSubtitulo,
      width: Number(botao.dataset.hseModalLargura) || LARGURA_PADRAO,
      body: corpoCarregando(botao.dataset.hseModalUrl),
      /* Depois de uma importação o que foi gravado precisa aparecer na tabela. */
      onClose: botao.hasAttribute("data-hse-atualiza") ? aoFechar : undefined
    });
  }

  function fecharModalDe(elemento) {
    const fundo = elemento.closest(".modal-backdrop");
    const fechar = fundo ? fundo.querySelector(".modal__close") : null;
    if (fechar) fechar.click();
  }

  window.TN.paginas[CHAVE] = {
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
        if (!acao) return;
        const botao = raiz.querySelector('[data-tn-incluir="' + acao + '"]');
        if (botao) botao.click();
      }

      /* Um só ouvinte por tela, preso à raiz; o modal mora fora dela (o Design System o anexa
         ao fim do <body>), por isso o do botão Cancelar é do documento e só um o atende. */
      raiz.addEventListener("click", function (evento) {
        const abrir = evento.target.closest("[data-hse-modal-url]");
        if (abrir) abrirFormulario(abrir, function () { carregar(urlAtual); });
        else if (evento.target.closest("[data-hse-recarregar]")) carregar(urlAtual);
      });
      document.addEventListener("click", function aoCancelar(evento) {
        if (!raiz.isConnected) {
          document.removeEventListener("click", aoCancelar);
          return;
        }
        const cancelar = evento.target.closest ? evento.target.closest("[data-hse-fechar-modal]") : null;
        if (cancelar) fecharModalDe(cancelar);
      });
      document.addEventListener("ajax:error", aoFalhar);

      const acao = window.TN.escopo ? window.TN.escopo.acaoPendente() : null;
      carregar(null).then(function () { atenderAcaoPendente(acao); });
    }
  };
})();
