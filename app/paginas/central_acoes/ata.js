/* ============================================================
   ata.js — Comportamento da tela Ata (central_acoes/ata)

   Ficha da ata: faixa de identificação, Dados da Reunião, Lista de Presença e
   Anotações e Ações (itens por grupo, com as colunas configuráveis).

   Registra um único objeto em TN.paginas["central_acoes/ata"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela (carregando, erro,
   sem-permissao ou pronto) mora no x-data da view; a ficha e os modais são fragmentos do
   servidor, e este arquivo só liga as pontas:

     ficha     a resposta traz o fragmento da ficha; o servidor responde 404 com o aviso de ata
               não encontrada (também "pronto": o aviso é o conteúdo), e 403 vira sem-permissao
     modais    os botões da ficha (data-ata-modal-url) abrem o modal cujo corpo o servidor entrega
               por GET em #ata-modal-corpo: empresas executoras, buscar convidado, retirar
               participante, item, replanejamento, justificativas, histórico e nova revisão; o 422
               volta no próprio modal e o sucesso troca a ficha
     colunas   o modal "Colunas da tabela" nasce do <template data-ata-colunas-modelo> da ficha e
               alterna as células [data-coluna] das tabelas de itens, sem ir ao servidor

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const RAIZ = "main.pagina--central_acoes-ata";
  const ALVO_DO_MODAL = "ata-modal-corpo";
  const LARGURA_PADRAO = 600;
  const LARGURA_DAS_COLUNAS = 520;
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

  function abrirColunas() {
    const modelo = document.querySelector("template[data-ata-colunas-modelo]");
    if (!modelo) return;
    if (modalAberto) modalAberto.close();
    modalAberto = window.TN.modal({
      title: "Colunas da tabela",
      subtitle: "Colunas visíveis nas tabelas de itens",
      width: LARGURA_DAS_COLUNAS,
      onClose: function () { modalAberto = null; },
      body: modelo.innerHTML
    });
  }

  function aplicarColunas(formulario) {
    const visiveis = Array.prototype.slice
      .call(formulario.querySelectorAll("input[name='colunas']:checked"))
      .map(function (campo) { return campo.value; });
    document.querySelectorAll("#painel-itens [data-coluna]").forEach(function (celula) {
      celula.hidden = visiveis.indexOf(celula.getAttribute("data-coluna")) < 0;
    });
    if (modalAberto) modalAberto.close();
  }

  function aoChegarAFicha(detalhe) {
    const status = detalhe ? detalhe.status : 0;
    if (detalhe && (detalhe.ok || status === 404)) estadoDaTela("pronto");
    else if (status === 403) estadoDaTela("sem-permissao");
    else if (!status || status >= 500) estadoDaTela("erro");
  }

  function aoClicar(evento) {
    if (!raizDaTela() || !evento.target.closest) return;
    if (evento.target.closest("[data-ata-colunas]")) {
      evento.preventDefault();
      abrirColunas();
      return;
    }
    const cancelar = evento.target.closest("[data-ata-colunas-cancelar]");
    if (cancelar) {
      const fundo = cancelar.closest(".modal-backdrop");
      const fechar = fundo ? fundo.querySelector(".modal__close") : null;
      if (fechar) fechar.click();
      return;
    }
    const botao = evento.target.closest("[data-ata-modal-url]");
    if (!botao) return;
    evento.preventDefault();
    abrirModal(botao);
  }

  function aoSubmeter(evento) {
    if (!(evento.target instanceof Element)) return;
    const formulario = evento.target.closest("form[data-ata-colunas-form]");
    if (!formulario) return;
    evento.preventDefault();
    aplicarColunas(formulario);
  }

  function aoEnviar(evento) {
    if (!raizDaTela() || !(evento.target instanceof Element)) return;
    if (evento.target.closest("#ata-ficha")) aoChegarAFicha(evento.detail);
  }

  function ouvir() {
    if (ouvindo) return;
    ouvindo = true;
    document.addEventListener("click", aoClicar);
    document.addEventListener("submit", aoSubmeter);
    document.addEventListener("ajax:sent", aoEnviar);
  }

  window.TN.paginas["central_acoes/ata"] = {
    iniciar: function (raiz) {
      window.Alpine.$data(raiz).estado = "carregando";
      ouvir();
    }
  };
})();
