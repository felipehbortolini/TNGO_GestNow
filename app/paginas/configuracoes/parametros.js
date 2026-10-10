/* ============================================================
   parametros.js — Comportamento da tela Parâmetros do sistema (configuracoes/parametros)

   Grupos de parâmetros versionados, com edição justificada e histórico do antes e depois.

   Registra um único objeto em TN.paginas["configuracoes/parametros"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela (carregando, conteudo,
   erro ou sem-permissao) mora no x-data da view; o vazio por filtro vem do servidor, dentro do
   fragmento.

   O servidor desenha tudo (api/src/templates/configuracoes/): o card da versão, a barra de
   filtros (um formulário GET com x-target, filtrado no servidor) e os grupos. Aqui moram os
   modais que o Design System abre por JavaScript (a edição de um grupo e o histórico), cujo
   corpo o servidor entrega por GET em #parametros-modal-corpo: o botão Editar carrega o
   formulário e o botão Histórico de versões carrega a lista; o Ver do histórico recarrega o
   próprio corpo do modal pela query. O sucesso da gravação atualiza a tela atrás do modal e o
   modal fecha pelo @ajax:success do formulário.

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const ALVO_DO_MODAL = "parametros-modal-corpo";
  const LARGURA_PADRAO = 760;

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
      titulo: botao.dataset.parametrosModalTitulo,
      subtitulo: botao.dataset.parametrosModalSubtitulo,
      url: botao.dataset.parametrosModalUrl,
      largura: botao.dataset.parametrosModalLargura
    });
  }

  function fecharModalDe(elemento) {
    const fundo = elemento.closest(".modal-backdrop");
    const fechar = fundo ? fundo.querySelector(".modal__close") : null;
    if (fechar) fechar.click();
  }

  window.TN.paginas["configuracoes/parametros"] = {
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
        const abrir = evento.target.closest("[data-parametros-modal-url]");
        if (abrir) abrirDoBotao(abrir);
        else if (evento.target.closest("[data-parametros-recarregar]")) carregar(urlAtual);
      });

      /* O modal mora fora da raiz (o Design System o anexa ao fim do <body>): o clique do
         Cancelar é ouvido no documento. */
      document.addEventListener("click", function aoClicarNoModal(evento) {
        if (!raiz.isConnected) {
          document.removeEventListener("click", aoClicarNoModal);
          return;
        }
        const alvo = evento.target.closest
          ? evento.target.closest("[data-parametros-fechar-modal]")
          : null;
        if (alvo) fecharModalDe(alvo);
      });
      document.addEventListener("ajax:error", aoFalhar);

      carregar(null);
    }
  };
})();
