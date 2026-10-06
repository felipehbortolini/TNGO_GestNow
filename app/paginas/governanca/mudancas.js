/* ============================================================
   mudancas.js — Comportamento da tela Gestão de mudanças (governanca/mudancas)

   Solicitações de mudança com etapa, próxima decisão e indicadores.

   Registra um único objeto em TN.paginas["governanca/mudancas"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela (carregando,
   vazio-origem, vazio-filtro, erro, sem-permissao ou pronto) mora no x-data da view; o
   conteúdo e os modais são fragmentos do servidor, e este arquivo só liga as pontas:

     painel     a resposta traz a marca data-estado (vazio-origem ou vazio-filtro) na tabela;
                sem marca a tela está pronta; 403 vira sem-permissao e falha vira erro
     KPIs       os três primeiros filtram a lista pela situação (o formulário de filtros refaz KPIs e tabela)
     nova       "Nova solicitação" abre o modal com o formulário do servidor; o 422 volta
                no próprio modal e o sucesso leva à ficha da SM (redirecionamento)
     endereço   ?acao=nova vem do mecanismo de inclusão do Portfólio (TN.escopo)

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const CHAVE = "governanca/mudancas";
  const RAIZ = "main.pagina--governanca-mudancas";
  let modalAberto = null;
  let ouvindo = false;

  function raizDaTela() {
    return document.querySelector(RAIZ);
  }

  function estadoDaTela(estado) {
    const raiz = raizDaTela();
    if (raiz) window.Alpine.$data(raiz).estado = estado;
  }

  function fecharModal() {
    if (modalAberto) modalAberto.close();
    modalAberto = null;
  }

  function abrirModal(opcoes) {
    fecharModal();
    modalAberto = window.TN.modal({
      title: opcoes.titulo,
      subtitle: opcoes.subtitulo || "",
      width: 760,
      onClose: function () { modalAberto = null; },
      body: '<div id="mudanca-modal" data-endereco="' + window.TN.esc(opcoes.endereco) + '"' +
        " x-init=\"$ajax($el.dataset.endereco, { target: 'mudanca-modal' })\">" +
        '<div class="spinner" role="status" aria-label="Carregando"></div></div>'
    });
  }

  function aoChegarOPainel(detalhe) {
    if (detalhe && detalhe.ok) {
      const marca = document.querySelector("#mudancas-tabela [data-estado]");
      estadoDaTela(marca ? marca.dataset.estado : "pronto");
      return;
    }
    const status = detalhe ? detalhe.status : 0;
    if (status === 403) estadoDaTela("sem-permissao");
    else if (!status || status >= 500) estadoDaTela("erro");
  }

  function nova() {
    abrirModal({
      titulo: "Nova solicitação de mudança",
      subtitulo: "O número nasce na gravação e a SM nasce Registrada",
      endereco: "/api/governanca/mudancas/nova" + window.location.search
    });
  }

  /* Os três primeiros KPIs filtram pela situação; clicar de novo no ativo limpa o filtro. */
  function filtrarPorSituacao(botao) {
    const seletor = document.getElementById("mudancas-situacao");
    if (!seletor) return;
    const valor = botao.dataset.filtroSituacao;
    seletor.value = seletor.value === valor ? "" : valor;
    seletor.form.requestSubmit();
  }

  function aoClicar(evento) {
    if (!raizDaTela()) return;
    const kpi = evento.target.closest("[data-filtro-situacao]");
    if (kpi) {
      evento.preventDefault();
      filtrarPorSituacao(kpi);
      return;
    }
    const botao = evento.target.closest("[data-mudanca-nova]");
    if (!botao) return;
    evento.preventDefault();
    nova();
  }

  function aoEnviar(evento) {
    if (!raizDaTela() || !(evento.target instanceof Element)) return;
    if (evento.target.closest("#mudancas-painel, #mudancas-kpis, #mudancas-tabela")) {
      aoChegarOPainel(evento.detail);
    }
  }

  function ouvir() {
    if (ouvindo) return;
    ouvindo = true;
    document.addEventListener("click", aoClicar);
    document.addEventListener("ajax:sent", aoEnviar);
  }

  window.TN.paginas[CHAVE] = {
    iniciar: function (raiz) {
      window.Alpine.$data(raiz).estado = "carregando";
      ouvir();
      if (window.TN.escopo.acaoPendente() === "nova") nova();
    }
  };
})();
