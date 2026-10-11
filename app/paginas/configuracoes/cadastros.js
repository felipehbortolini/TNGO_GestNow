/* ============================================================
   cadastros.js — Comportamento da tela Cadastros de apoio (configuracoes/cadastros)

   Empresas, pessoas, projetos, sistemas, unidades, locais e disciplinas que alimentam os
   formulários.

   Registra um único objeto em TN.paginas["configuracoes/cadastros"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela (carregando, conteudo,
   erro ou sem-permissao) mora no x-data da view; o vazio de origem sai por cartão, dentro do
   fragmento.

   O servidor desenha tudo (api/src/templates/configuracoes/): os sete cartões com a contagem, o
   Incluir, a tabela e Editar/Excluir por linha. Aqui moram o modal de novo/editar cadastro —
   cujo corpo o servidor entrega por GET em #cadastros-modal-corpo, conforme o tipo — e o
   recarregar. O sucesso da gravação atualiza a lista atrás do modal e o modal fecha pelo
   @ajax:success do formulário; a exclusão confirma por TN.confirmarExclusao (no próprio
   fragmento) e o servidor devolve a lista com o toast.

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const ALVO_DO_MODAL = "cadastros-modal-corpo";
  const LARGURA_PADRAO = 820;

  /* O corpo do modal pede o fragmento ao servidor assim que o Alpine o inicializa; o endereço
     vai por data-url para nunca ser interpolado dentro de uma expressão. */
  function corpoCarregando(endereco) {
    return (
      '<div id="' + ALVO_DO_MODAL + '" data-url="' + window.TN.esc(endereco) + '"' +
      " x-init=\"$ajax($el.dataset.url, { target: '" + ALVO_DO_MODAL + "' })\">" +
      '<div class="spinner" role="status" aria-label="Carregando"></div></div>'
    );
  }

  function abrirModal(opcoes) {
    window.TN.modal({
      title: opcoes.titulo,
      subtitle: opcoes.subtitulo,
      width: Number(opcoes.largura) || LARGURA_PADRAO,
      body: corpoCarregando(opcoes.url)
    });
  }

  function abrirDoBotao(botao) {
    abrirModal({
      titulo: botao.dataset.cadastrosModalTitulo,
      subtitulo: botao.dataset.cadastrosModalSubtitulo,
      url: botao.dataset.cadastrosModalUrl,
      largura: botao.dataset.cadastrosModalLargura
    });
  }

  function fecharModalDe(elemento) {
    const fundo = elemento.closest(".modal-backdrop");
    const fechar = fundo ? fundo.querySelector(".modal__close") : null;
    if (fechar) fechar.click();
  }

  window.TN.paginas["configuracoes/cadastros"] = {
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

      /* Um só ouvinte por tela, preso à raiz, para o que vive no fragmento. */
      raiz.addEventListener("click", function (evento) {
        const abrir = evento.target.closest("[data-cadastros-modal-url]");
        if (abrir) abrirDoBotao(abrir);
        else if (evento.target.closest("[data-cadastros-recarregar]")) carregar(urlAtual);
      });

      /* O modal mora fora da raiz (o Design System o anexa ao fim do <body>): o clique do
         Cancelar é ouvido no documento. */
      document.addEventListener("click", function aoClicarNoModal(evento) {
        if (!raiz.isConnected) {
          document.removeEventListener("click", aoClicarNoModal);
          return;
        }
        const alvo = evento.target.closest
          ? evento.target.closest("[data-cadastros-fechar-modal]")
          : null;
        if (alvo) fecharModalDe(alvo);
      });
      document.addEventListener("ajax:error", aoFalhar);

      carregar(null);
    }
  };
})();
