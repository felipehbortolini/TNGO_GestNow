/* ============================================================
   analises_risco.js — Comportamento da tela Análises de risco (APR/HAZOP) (hse/analises_risco)

   Estudos APR/JSA e HAZOP, com as recomendações que viram ações.

   Registra um único objeto em TN.paginas["hse/analises_risco"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela
   (carregando, conteudo, erro ou sem-permissao) mora no x-data da view; o vazio de origem e o
   vazio por filtro vêm do servidor, dentro do fragmento.

   O servidor desenha tudo (api/src/templates/hse/): indicadores, filtro, tabela e página são
   formulários e links com x-target. Aqui só moram os modais que o Design System abre por
   JavaScript: o formulário do novo estudo e o estudo com as recomendações, cujo corpo o servidor
   entrega por GET em #hse-modal-corpo. Quem abre o estudo (botão com data-hse-atualiza) vê a tela
   se recarregar ao fechar o modal, porque fechar uma recomendação ou criar a ação muda a tabela.
   No Portfólio o botão de inclusão pede o projeto antes (data-tn-incluir, ds/shell.js) e a tela
   reabre no projeto com a ação pedida (TN.escopo.acaoPendente). Vinda do link de uma ação da
   Central (?busca=código), a tela abre o estudo sozinha (botão data-hse-auto, desenhado pelo
   servidor quando o código é exato).

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const CHAVE = "hse/analises_risco";
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

  function abrirModal(botao, aoFechar) {
    window.TN.modal({
      title: botao.dataset.hseModalTitulo,
      subtitle: botao.dataset.hseModalSubtitulo,
      width: Number(botao.dataset.hseModalLargura) || LARGURA_PADRAO,
      body: corpoCarregando(botao.dataset.hseModalUrl),
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
      let abriuSozinho = false;

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

      function atenderAutoAbertura() {
        const botao = raiz.querySelector("[data-hse-auto]");
        if (!botao || abriuSozinho) return;
        abriuSozinho = true;
        abrirModal(botao, recarregar);
      }

      function carregar() {
        dados.estado = "carregando";
        return dados
          .carregar()
          .then(function () {
            if (dados.estado === "carregando") dados.estado = "conteudo";
            atenderAutoAbertura();
          })
          .catch(function () {
            /* aoFalhar já escolheu o estado a partir do ajax:error */
          });
      }

      /* Ao fechar o estudo, a tela se recarrega com os filtros que a pessoa deixou no formulário;
         o estudo não reabre sozinho, só a primeira carga atende data-hse-auto. */
      function recarregar() {
        const formulario = raiz.querySelector('form[action="/api/hse/analises-de-risco"]');
        const consulta = formulario ? new URLSearchParams(new FormData(formulario)).toString() : "";
        dados.estado = "carregando";
        dados.carregar("/api/hse/analises-de-risco" + (consulta ? "?" + consulta : "")).then(function () {
          if (dados.estado === "carregando") dados.estado = "conteudo";
        });
      }

      /* A ação pedida pelo mecanismo de inclusão do Portfólio: abre o formulário já na tela. */
      function atenderAcaoPendente(acao) {
        if (acao !== "novo") return;
        const botao = raiz.querySelector('[data-tn-incluir="novo"]');
        if (botao) botao.click();
      }

      /* Um só ouvinte por tela, preso à raiz; o modal mora fora dela (o Design System o anexa
         ao fim do <body>), por isso o do botão Cancelar é do documento e só um o atende. */
      raiz.addEventListener("click", function (evento) {
        const abrir = evento.target.closest("[data-hse-modal-url]");
        if (abrir) {
          evento.preventDefault();
          abrirModal(abrir, recarregar);
        } else if (evento.target.closest("[data-hse-recarregar]")) {
          carregar();
        }
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
      carregar().then(function () { atenderAcaoPendente(acao); });
    }
  };
})();
