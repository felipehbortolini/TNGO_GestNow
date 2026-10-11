(function () {
  "use strict";

  const ESTADOS_DE_RESULTADO = ["conteudo", "vazio-origem"];
  const RAIZ = "main.pagina--financeiro-kpis";

  let ouvindo = false;

  function raizDaTela() {
    return document.querySelector(RAIZ);
  }

  function definirEstado(raiz, estado) {
    window.Alpine.$data(raiz).estado = estado;
  }

  function aoResponder(raiz) {
    const marcador = raiz.querySelector("[data-situacao]");
    if (!marcador) return;
    const situacao = marcador.getAttribute("data-situacao");
    definirEstado(raiz, ESTADOS_DE_RESULTADO.indexOf(situacao) >= 0 ? situacao : "erro");
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

  function ouvir() {
    if (ouvindo) return;
    ouvindo = true;
    document.addEventListener("ajax:success", aoSucesso);
    document.addEventListener("ajax:error", aoErro);
  }

  window.TN.paginas["financeiro/kpis"] = {
    iniciar: function (raiz) {
      definirEstado(raiz, "carregando");
      ouvir();
      if (window.TN.analise) window.TN.analise.abrirDoEndereco("financeiro");
    }
  };
})();
