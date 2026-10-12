/* ============================================================
   fornecedores.js — Comportamento da tela Fornecedores (suprimentos/fornecedores)

   Qualificação, documentos com validade e desempenho dos fornecedores (ISSUE-057, HU-105).

   Registra um único objeto em TN.paginas["suprimentos/fornecedores"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela (carregando, conteudo,
   erro ou sem-permissao) mora no x-data da view; os estados vazio de origem e vazio por filtro
   vêm do servidor, dentro do fragmento.

   O servidor desenha tudo (api/src/templates/suprimentos/fornecedores.html): KPIs, busca,
   filtros, tabela e páginas são links ou um formulário GET com x-target. Aqui só moram os
   modais que o Design System abre por JavaScript: Novo fornecedor, Atualizar qualificação e
   Desempenho e histórico, cujo corpo o servidor entrega por GET no alvo do modal.

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const ALVO_DO_MODAL = "fornecedor-modal-corpo";
  const LARGURA_PADRAO = 760;
  const LARGURA_DO_DESEMPENHO = 980;

  /* O corpo do modal pede o fragmento ao servidor assim que o Alpine o inicializa; o endereço
     vai por data-url para nunca ser interpolado dentro de uma expressão. */
  function corpoCarregando(alvo, endereco) {
    return (
      '<div id="' + alvo + '" data-url="' + window.TN.esc(endereco) + '"' +
      " x-init=\"$ajax($el.dataset.url, { target: '" + alvo + "' })\">" +
      '<div class="spinner" role="status" aria-label="' + window.TN.t("suprimentos", "Carregando") + '"></div></div>'
    );
  }

  function larguraDe(endereco) {
    return endereco.indexOf("/desempenho") >= 0 ? LARGURA_DO_DESEMPENHO : LARGURA_PADRAO;
  }

  function abrirModal(botao) {
    window.TN.modal({
      title: botao.dataset.fornecedorModalTitulo,
      subtitle: botao.dataset.fornecedorModalSubtitulo,
      width: larguraDe(botao.dataset.fornecedorModalUrl),
      body: corpoCarregando(ALVO_DO_MODAL, botao.dataset.fornecedorModalUrl)
    });
  }

  function fecharModalDe(elemento) {
    const fundo = elemento.closest(".modal-backdrop");
    const fechar = fundo ? fundo.querySelector(".modal__close") : null;
    if (fechar) fechar.click();
  }

  /* Um só ouvinte no documento, registrado quando o script carrega: o modal mora fora da raiz
     da tela (o Design System o anexa ao fim do <body>) e a tela pode ser aberta várias vezes. */
  document.addEventListener("click", function (evento) {
    const alvo = evento.target.closest ? evento.target : null;
    if (!alvo) return;
    const formulario = alvo.closest("[data-fornecedor-modal-url]");
    const cancelar = alvo.closest("[data-fornecedor-fechar-modal]");
    if (formulario) abrirModal(formulario);
    else if (cancelar) fecharModalDe(cancelar);
  });

  window.TN.paginas["suprimentos/fornecedores"] = {
    iniciar: function (raiz) {
      const dados = window.Alpine.$data(raiz);

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

      function carregar() {
        dados.estado = "carregando";
        dados
          .carregar()
          .then(function () {
            if (dados.estado === "carregando") dados.estado = "conteudo";
          })
          .catch(function () {
            /* aoFalhar já escolheu o estado a partir do ajax:error */
          });
      }

      document.addEventListener("ajax:error", aoFalhar);
      raiz.addEventListener("click", function (evento) {
        if (evento.target.closest("[data-fornecedores-recarregar]")) carregar();
      });
      carregar();
    }
  };
})();
