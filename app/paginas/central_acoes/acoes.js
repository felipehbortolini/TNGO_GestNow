/* ============================================================
   acoes.js — Comportamento da tela Ações (central_acoes/acoes)

   Ações de todas as origens em lista e kanban, com filtros, replanejamento justificado e link para a origem.

   Registra um único objeto em TN.paginas["central_acoes/acoes"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela
   (carregando, conteudo, erro ou sem-permissao) mora no x-data da view; os estados vazio de
   origem e vazio por filtro vêm do servidor, dentro do fragmento.

   O servidor desenha tudo (api/src/templates/central_acoes/acoes.html): KPIs, chips, visão e
   página são links com x-target. Aqui só moram os dois modais que o Design System abre por
   JavaScript: o dos filtros (o formulário vem num <template> do fragmento) e o dos formulários
   da linha (replanejar, concluir, histórico e anexos), cujo corpo o servidor entrega por
   GET em #acoes-modal-corpo.

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const CHAVE = "central_acoes/acoes";
  const ALVO_DO_MODAL = "acoes-modal-corpo";
  const LARGURA_DOS_FILTROS = 640;
  const LARGURA_PADRAO = 560;
  const LARGURA_DO_HISTORICO = 820;

  /* O corpo do modal pede o fragmento ao servidor assim que o Alpine o inicializa; o endereço
     vai por data-url para nunca ser interpolado dentro de uma expressão. */
  function corpoCarregando(endereco) {
    return (
      '<div id="' + ALVO_DO_MODAL + '" data-url="' + window.TN.esc(endereco) + '"' +
      " x-init=\"$ajax($el.dataset.url, { target: '" + ALVO_DO_MODAL + "' })\">" +
      '<div class="spinner" role="status" aria-label="Carregando"></div></div>'
    );
  }

  function abrirFiltros() {
    const modelo = document.querySelector("template[data-acoes-filtros-modelo]");
    if (!modelo) return;
    window.TN.modal({
      title: "Filtros da Central",
      subtitle: "Busca, origem, status e responsável",
      width: LARGURA_DOS_FILTROS,
      body: modelo.innerHTML
    });
  }

  function abrirFormulario(botao) {
    const historico = botao.dataset.acoesModalUrl.indexOf("/historico") >= 0;
    window.TN.modal({
      title: botao.dataset.acoesModalTitulo,
      subtitle: botao.dataset.acoesModalSubtitulo,
      width: historico ? LARGURA_DO_HISTORICO : LARGURA_PADRAO,
      body: corpoCarregando(botao.dataset.acoesModalUrl)
    });
  }

  function fecharModalDe(elemento) {
    const fundo = elemento.closest(".modal-backdrop");
    const fechar = fundo ? fundo.querySelector(".modal__close") : null;
    if (fechar) fechar.click();
  }

  /* Um só ouvinte no documento, registrado quando o script carrega: o modal mora fora da raiz da
     tela (o Design System o anexa ao fim do <body>), e a tela pode ser aberta várias vezes. */
  document.addEventListener("click", function (evento) {
    const alvo = evento.target.closest ? evento.target : null;
    if (!alvo) return;
    const filtros = alvo.closest("[data-acoes-filtros]");
    const formulario = alvo.closest("[data-acoes-modal-url]");
    const cancelar = alvo.closest("[data-acoes-fechar-modal]");
    if (filtros) abrirFiltros();
    else if (formulario) abrirFormulario(formulario);
    else if (cancelar) fecharModalDe(cancelar);
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
        if (evento.target.closest("[data-acoes-recarregar]")) carregar();
      });
      carregar();
    }
  };
})();
