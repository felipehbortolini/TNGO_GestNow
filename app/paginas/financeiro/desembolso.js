(function () {
  "use strict";

  const ESTADOS_DE_RESULTADO = ["conteudo", "vazio-origem"];
  const RAIZ = "main.pagina--financeiro-desembolso";
  const ROTA_ENVIO = "/api/financeiro/desembolso/enviar";
  const ALVO_DO_MODAL = "desembolso-modal";
  const EXPORTACOES = [
    ["data-tn-excel", "tnExcelBase"],
    ["data-tn-pdf", "tnPdfBase"]
  ];

  let modalEnvio = null;
  let ouvindo = false;

  function raizDaTela() {
    return document.querySelector(RAIZ);
  }

  function definirEstado(raiz, estado) {
    window.Alpine.$data(raiz).estado = estado;
  }

  function nivelCorrente(raiz) {
    const seletor = raiz.querySelector("#desembolso-nivel");
    return seletor ? seletor.value : "2";
  }

  function sincronizarExportacao(raiz) {
    const consulta = "?nivel=" + encodeURIComponent(nivelCorrente(raiz));
    EXPORTACOES.forEach(function (par) {
      const botao = raiz.querySelector("[" + par[0] + "]");
      if (!botao) return;
      if (!botao.dataset[par[1]]) botao.dataset[par[1]] = botao.getAttribute(par[0]);
      botao.setAttribute(par[0], botao.dataset[par[1]] + consulta);
    });
  }

  function aoResponder(raiz) {
    const marcador = raiz.querySelector("[data-situacao]");
    if (!marcador) return;
    const situacao = marcador.getAttribute("data-situacao");
    definirEstado(raiz, ESTADOS_DE_RESULTADO.indexOf(situacao) >= 0 ? situacao : "erro");
    sincronizarExportacao(raiz);
  }

  function aoSucesso() {
    const raiz = raizDaTela();
    if (!raiz) return;
    window.setTimeout(function () {
      aoResponder(raiz);
    }, 0);
  }

  function aoErro(evento) {
    const raiz = raizDaTela();
    if (!raiz || window.Alpine.$data(raiz).estado !== "carregando") return;
    const status = evento.detail && evento.detail.status;
    definirEstado(raiz, status === 403 ? "sem-permissao" : "erro");
  }

  function corpoDoEnvio() {
    return (
      '<div id="' + ALVO_DO_MODAL + '" data-url="' + window.TN.esc(ROTA_ENVIO) + '"' +
      " x-init=\"$ajax($el.dataset.url, { target: '" + ALVO_DO_MODAL + "' })\">" +
      '<div class="spinner" role="status" aria-label="Carregando o envio"></div></div>'
    );
  }

  function abrirEnvio() {
    if (modalEnvio) modalEnvio.close();
    modalEnvio = window.TN.modal({
      title: "Enviar à tesouraria",
      width: 640,
      onClose: function () {
        modalEnvio = null;
      },
      body: corpoDoEnvio()
    });
  }

  function fecharModalDe(elemento) {
    const fundo = elemento.closest(".modal-backdrop");
    const fechar = fundo ? fundo.querySelector(".modal__close") : null;
    if (fechar) fechar.click();
  }

  function aoClicar(evento) {
    const alvo = evento.target.closest ? evento.target : null;
    if (!alvo) return;
    if (alvo.closest("[data-desembolso-enviar]")) {
      abrirEnvio();
      return;
    }
    const fechar = alvo.closest("[data-desembolso-fechar-modal]");
    if (fechar) fecharModalDe(fechar);
  }

  function ouvir() {
    if (ouvindo) return;
    ouvindo = true;
    document.addEventListener("ajax:success", aoSucesso);
    document.addEventListener("ajax:error", aoErro);
    document.addEventListener("click", aoClicar);
  }

  window.TN.paginas["financeiro/desembolso"] = {
    iniciar: function (raiz) {
      definirEstado(raiz, "carregando");
      sincronizarExportacao(raiz);
      ouvir();
    }
  };
})();
