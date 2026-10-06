/* ============================================================
   punch_list.js — Comportamento da tela Punch list (planejamento/punch_list)

   Itens de completação com verificação, bloqueio de sistema e painel.

   Registra um único objeto em TN.paginas["planejamento/punch_list"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela
   (carregando, conteudo, erro ou sem-permissao) mora no x-data da view; o vazio de origem
   e o vazio por filtro vêm do servidor, dentro do fragmento.

   O servidor desenha tudo (api/src/templates/planejamento/): indicadores, alerta, tabelas e
   formulários. Aqui só moram os modais que o Design System abre por JavaScript: Novo item,
   Fechamento com verificação, Filtros e a importação de planilha, cujo corpo o servidor
   entrega por GET em #punch-modal-corpo. Depois de uma importação a tela se recarrega ao
   fechar o modal. No Portfólio o botão de inclusão pede o projeto antes (data-tn-incluir,
   ds/shell.js) e a tela reabre no projeto com a ação pedida (TN.escopo.acaoPendente).
   Um endereço com ?item=PL-... abre a lista já filtrada nesse item (link de volta da Central).

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const CHAVE = "planejamento/punch_list";
  const ALVO_DO_MODAL = "punch-modal-corpo";
  const LARGURA_PADRAO = 640;
  const STATUS_SEM_PERMISSAO = 403;

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
      title: botao.dataset.punchModalTitulo,
      subtitle: botao.dataset.punchModalSubtitulo,
      width: Number(botao.dataset.punchModalLargura) || LARGURA_PADRAO,
      body: corpoCarregando(botao.dataset.punchModalUrl),
      /* Depois de uma importação o que foi gravado precisa aparecer na lista. */
      onClose: botao.hasAttribute("data-punch-atualiza") ? aoFechar : undefined
    });
  }

  function fecharModalDe(elemento) {
    const fundo = elemento.closest(".modal-backdrop");
    const fechar = fundo ? fundo.querySelector(".modal__close") : null;
    if (fechar) fechar.click();
  }

  /* O filtro por código que o link de volta da Central leva na consulta da tela. */
  function consultaDaTela() {
    const item = new URLSearchParams(window.location.search).get("item");
    return item ? "?item=" + encodeURIComponent(item) : "";
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
        const status = evento.detail ? evento.detail.status : 0;
        dados.estado = status === STATUS_SEM_PERMISSAO ? "sem-permissao" : "erro";
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
         ao fim do <body>), por isso o do botão Fechar é do documento e só um o atende. */
      raiz.addEventListener("click", function (evento) {
        const abrir = evento.target.closest("[data-punch-modal-url]");
        if (abrir) abrirModal(abrir, function () { carregar(urlAtual); });
        else if (evento.target.closest("[data-punch-recarregar]")) carregar(urlAtual);
      });
      document.addEventListener("click", function aoFechar(evento) {
        if (!raiz.isConnected) {
          document.removeEventListener("click", aoFechar);
          return;
        }
        const fechar = evento.target.closest ? evento.target.closest("[data-punch-fechar-modal]") : null;
        if (fechar) fecharModalDe(fechar);
      });
      document.addEventListener("ajax:error", aoFalhar);

      const acao = window.TN.escopo ? window.TN.escopo.acaoPendente() : null;
      const consulta = consultaDaTela();
      carregar(consulta ? "/api/planejamento/punch-list" + consulta : null).then(function () {
        atenderAcaoPendente(acao);
      });
    }
  };
})();
