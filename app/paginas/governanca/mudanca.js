/* ============================================================
   mudanca.js — Comportamento da tela Solicitação de mudança (governanca/mudanca)

   Ficha da SM: barra de etapas e as cinco abas em leitura, com o cancelamento.

   Registra um único objeto em TN.paginas["governanca/mudanca"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela (carregando,
   vazio-origem, vazio-filtro, erro, sem-permissao ou pronto) mora no x-data da view; o
   conteúdo e os modais são fragmentos do servidor, e este arquivo só liga as pontas:

     ficha      a resposta traz o fragmento da ficha; o servidor responde 404 com o aviso de
                solicitação não encontrada, e 403 vira sem-permissao
     cancelar   o botão da ficha abre o modal com o formulário de justificativa

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const CHAVE = "governanca/mudanca";
  const RAIZ = "main.pagina--governanca-mudanca";
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

  function aoChegarAFicha(detalhe) {
    if (detalhe && detalhe.ok) {
      estadoDaTela("pronto");
      return;
    }
    const status = detalhe ? detalhe.status : 0;
    if (status === 403) estadoDaTela("sem-permissao");
    else if (status === 404) estadoDaTela("vazio-origem");
    else if (!status || status >= 500) estadoDaTela("erro");
  }

  function cancelar(endereco, codigo) {
    abrirModal({
      titulo: "Cancelar solicitação",
      subtitulo: codigo,
      endereco: endereco
    });
  }

  function aoClicar(evento) {
    const botao = evento.target.closest("[data-mudanca-cancelar]");
    if (!botao || !raizDaTela()) return;
    evento.preventDefault();
    cancelar(botao.dataset.mudancaCancelar, botao.dataset.codigo);
  }

  function aoEnviar(evento) {
    if (!raizDaTela() || !(evento.target instanceof Element)) return;
    if (evento.target.closest("#mudanca-ficha")) aoChegarAFicha(evento.detail);
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
    }
  };
})();
