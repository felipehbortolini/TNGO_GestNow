/* ============================================================
   ficha.js — Comportamento da tela Ficha do risco (riscos/ficha)

   Identificação, avaliação, resposta, monitoramento e histórico do risco (ISSUE-065).

   Registra um único objeto em TN.paginas["riscos/ficha"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela
   (carregando, pronto, vazio-origem, vazio-filtro, erro ou sem-permissao) mora no
   x-data da view; o conteúdo e os modais são fragmentos do servidor, e este arquivo
   só liga as pontas:

     ficha     o servidor desenha tudo (api/src/templates/riscos/ficha.html): alertas,
               faixa, botões e abas. O conteúdo carrega pelo $ajax da view.
     modais    os botões da ficha trazem data-ficha-modal-url; o corpo do modal pede o
               formulário ao servidor (alvo ficha-modal-corpo) e o sucesso atualiza a
               ficha atrás dele. Um marcador oculto do fragmento reabre o próximo modal
               (avaliação, encerramento ou "Salvar e nova") por abrirModal.

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const ALVO_DO_MODAL = "ficha-modal-corpo";
  const LARGURA_PADRAO = 760;
  const LARGURA_DA_AVALIACAO = 880;
  const LARGURA_DA_REVISAO = 720;
  const LARGURA_DO_ENCERRAMENTO = 820;

  let modalAberto = null;
  let ouvindo = false;

  function corpoCarregando(endereco) {
    return (
      '<div id="' + ALVO_DO_MODAL + '" data-url="' + window.TN.esc(endereco) + '"' +
      " x-init=\"$ajax($el.dataset.url, { target: '" + ALVO_DO_MODAL + "' })\">" +
      '<div class="spinner" role="status" aria-label="Carregando"></div></div>'
    );
  }

  function larguraDe(endereco) {
    if (endereco.indexOf("/ficha/avaliar") >= 0) return LARGURA_DA_AVALIACAO;
    if (endereco.indexOf("/revisoes") >= 0) return LARGURA_DA_REVISAO;
    if (endereco.indexOf("/encerramento") >= 0) return LARGURA_DO_ENCERRAMENTO;
    return LARGURA_PADRAO;
  }

  function fecharModal() {
    if (modalAberto) modalAberto.close();
    modalAberto = null;
  }

  function abrirModalPor(endereco, titulo, subtitulo) {
    fecharModal();
    modalAberto = window.TN.modal({
      title: titulo,
      subtitle: subtitulo || "",
      width: larguraDe(endereco),
      onClose: function () { modalAberto = null; },
      body: corpoCarregando(endereco)
    });
  }

  function aoClicar(evento) {
    const alvo = evento.target.closest ? evento.target : null;
    if (!alvo) return;
    const botao = alvo.closest("[data-ficha-modal-url]");
    if (botao) {
      evento.preventDefault();
      abrirModalPor(
        botao.dataset.fichaModalUrl,
        botao.dataset.fichaModalTitulo,
        botao.dataset.fichaModalSubtitulo
      );
      return;
    }
    const fechar = alvo.closest("[data-ficha-fechar-modal]");
    if (fechar) {
      evento.preventDefault();
      fecharModal();
      return;
    }
    const recarregar = alvo.closest("[data-ficha-recarregar]");
    if (recarregar) carregarFicha();
  }

  function ouvir() {
    if (ouvindo) return;
    ouvindo = true;
    document.addEventListener("click", aoClicar);
  }

  function carregarFicha() {
    const raiz = document.querySelector("main.pagina--riscos-ficha");
    if (!raiz) return;
    const dados = window.Alpine.$data(raiz);
    dados.estado = "carregando";
    dados
      .carregar()
      .then(function () {
        if (dados.estado === "carregando") dados.estado = "pronto";
      })
      .catch(function () {
        /* aoFalhar já escolheu o estado a partir do ajax:error */
      });
  }

  window.TN.paginas["riscos/ficha"] = {
    iniciar: function (raiz) {
      const dados = window.Alpine.$data(raiz);

      /* Só a primeira carga decide entre erro, sem permissão e risco não encontrado; depois de
         aberta, a tela se mantém e a falha de uma ação vira toast ou a mensagem no modal. */
      function aoFalhar(evento) {
        if (!raiz.isConnected) {
          document.removeEventListener("ajax:error", aoFalhar);
          return;
        }
        if (dados.estado !== "carregando") return;
        const status = evento.detail ? evento.detail.status : 0;
        if (status === 403) dados.estado = "sem-permissao";
        else if (status === 404) dados.estado = "vazio-origem";
        else dados.estado = "erro";
      }

      document.addEventListener("ajax:error", aoFalhar);
      ouvir();
      carregarFicha();
    },

    /* Um marcador oculto do fragmento reabre o próximo modal depois de uma gravação:
       a avaliação de um gatilho, o encerramento de um risco materializado ou o "Salvar e nova". */
    abrirModal: function (marcador) {
      window.setTimeout(function () {
        abrirModalPor(
          marcador.dataset.fichaAbrirUrl,
          marcador.dataset.fichaAbrirTitulo,
          marcador.dataset.fichaAbrirSubtitulo
        );
      }, 50);
    }
  };
})();
