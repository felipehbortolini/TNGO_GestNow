/* ============================================================
   ata.js — Comportamento da tela Ata (central_acoes/ata)

   Ficha da ata: faixa de identificação, Dados da Reunião e Lista de Presença
   (Anotações e Ações chegam na ISSUE-022).

   Registra um único objeto em TN.paginas["central_acoes/ata"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela (carregando, erro,
   sem-permissao ou pronto) mora no x-data da view; a ficha e os modais são fragmentos do
   servidor, e este arquivo só liga as pontas:

     ficha     a resposta traz o fragmento da ficha; o servidor responde 404 com o aviso de ata
               não encontrada (também "pronto": o aviso é o conteúdo), e 403 vira sem-permissao
     modais    os botões da ficha (data-ata-modal-url) abrem o modal cujo corpo o servidor entrega
               por GET em #ata-modal-corpo: empresas executoras, buscar convidado e retirar
               participante; o 422 volta no próprio modal e o sucesso troca a ficha

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const RAIZ = "main.pagina--central_acoes-ata";
  const ALVO_DO_MODAL = "ata-modal-corpo";
  const LARGURA_PADRAO = 600;
  let modalAberto = null;
  let ouvindo = false;

  function raizDaTela() {
    return document.querySelector(RAIZ);
  }

  function estadoDaTela(estado) {
    const raiz = raizDaTela();
    if (raiz) window.Alpine.$data(raiz).estado = estado;
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

  function abrirModal(botao) {
    if (modalAberto) modalAberto.close();
    modalAberto = window.TN.modal({
      title: botao.dataset.ataModalTitulo,
      subtitle: botao.dataset.ataModalSubtitulo || "",
      width: LARGURA_PADRAO,
      onClose: function () { modalAberto = null; },
      body: corpoCarregando(botao.dataset.ataModalUrl)
    });
  }

  function aoChegarAFicha(detalhe) {
    const status = detalhe ? detalhe.status : 0;
    if (detalhe && (detalhe.ok || status === 404)) estadoDaTela("pronto");
    else if (status === 403) estadoDaTela("sem-permissao");
    else if (!status || status >= 500) estadoDaTela("erro");
  }

  function aoClicar(evento) {
    if (!raizDaTela() || !evento.target.closest) return;
    const botao = evento.target.closest("[data-ata-modal-url]");
    if (!botao) return;
    evento.preventDefault();
    abrirModal(botao);
  }

  function aoEnviar(evento) {
    if (!raizDaTela() || !(evento.target instanceof Element)) return;
    if (evento.target.closest("#ata-ficha")) aoChegarAFicha(evento.detail);
  }

  function ouvir() {
    if (ouvindo) return;
    ouvindo = true;
    document.addEventListener("click", aoClicar);
    document.addEventListener("ajax:sent", aoEnviar);
  }

  window.TN.paginas["central_acoes/ata"] = {
    iniciar: function (raiz) {
      window.Alpine.$data(raiz).estado = "carregando";
      ouvir();
    }
  };
})();
