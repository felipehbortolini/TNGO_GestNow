/* ============================================================
   atas.js — Comportamento da tela Atas (central_acoes/atas)

   Atas de reunião do projeto: aparece a revisão mais recente de cada ata.

   Registra um único objeto em TN.paginas["central_acoes/atas"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela
   (carregando, conteudo, erro ou sem-permissao) mora no x-data da view; os estados vazio de
   origem e vazio por filtro vêm do servidor, dentro do fragmento.

   O servidor desenha tudo (api/src/templates/central_acoes/atas.html): busca, tabela e
   páginas são um formulário GET e links com x-target. Aqui mora só o modal do formulário
   "Gerar nova ata", que o Design System abre por JavaScript e cujo corpo o servidor entrega
   por GET em #atas-modal-corpo; o 422 volta no próprio modal e o sucesso leva à ficha da ata
   (redirecionamento). No Portfólio o mecanismo de inclusão (data-tn-incluir) pede o projeto antes
   e reabre a tela com ?acao=nova, que abre o formulário aqui (TN.escopo.acaoPendente).

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const CHAVE = "central_acoes/atas";
  const RAIZ = "main.pagina--central_acoes-atas";
  const ALVO_DO_MODAL = "atas-modal-corpo";
  const LARGURA_DO_FORMULARIO = 640;
  let modalAberto = null;

  function raizDaTela() {
    return document.querySelector(RAIZ);
  }

  /* O corpo do modal pede o fragmento ao servidor assim que o Alpine o inicializa; o endereço
     vai por data-url para nunca ser interpolado dentro de uma expressão. */
  function corpoCarregando(endereco) {
    return (
      '<div id="' + ALVO_DO_MODAL + '" data-url="' + window.TN.esc(endereco) + '"' +
      " x-init=\"$ajax($el.dataset.url, { target: '" + ALVO_DO_MODAL + "' })\">" +
      '<div class="spinner" role="status" aria-label="Carregando"></div></div>'
    );
  }

  function abrirNova(endereco) {
    if (modalAberto) modalAberto.close();
    modalAberto = window.TN.modal({
      title: "Gerar nova ata",
      subtitle: "O número nasce na gravação, pelo padrão do projeto",
      width: LARGURA_DO_FORMULARIO,
      onClose: function () { modalAberto = null; },
      body: corpoCarregando(endereco)
    });
  }

  /* Um só ouvinte no documento, registrado quando o script carrega: o modal mora fora da raiz da
     tela (o Design System o anexa ao fim do <body>), e a tela pode ser aberta várias vezes. */
  document.addEventListener("click", function (evento) {
    if (!raizDaTela() || !evento.target.closest) return;
    const nova = evento.target.closest("[data-atas-nova]");
    if (!nova) return;
    evento.preventDefault();
    abrirNova(nova.dataset.atasNova);
  });

  window.TN.paginas[CHAVE] = {
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
        if (evento.target.closest("[data-atas-recarregar]")) carregar();
      });
      carregar();
      if (window.TN.escopo.acaoPendente() === "nova") {
        abrirNova("/api/central-acoes/atas/nova");
      }
    }
  };
})();
