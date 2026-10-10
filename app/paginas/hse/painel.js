/* ============================================================
   painel.js — Comportamento da tela Painel HSE (hse/painel)

   Taxas reativas e proativas, pirâmides, dias sem afastamento e evolução
   (ISSUE-075).

   Registra um único objeto em TN.paginas["hse/painel"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela
   (carregando, conteudo, vazio-origem, erro ou sem-permissao) mora no x-data
   da view; o vazio de origem vem do servidor, dentro do fragmento (o marcador
   data-situacao), e erro/sem permissão saem do ajax:error. O servidor desenha
   tudo (api/src/templates/hse/painel.html): a barra de filtros (ano, mês e a
   referência da pirâmide), os três blocos de KPIs, os gráficos
   (data-grafico + data-dados) e as duas listas. Aqui moram a carga inicial, a
   nova tentativa e a lembrança do último endereço, para o "Tentar de novo"
   repetir os filtros que estavam na tela.

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const RAIZ = "main.pagina--hse-painel";

  let ouvindo = false;
  let ultimoEndereco = null;

  function raizDaTela() {
    return document.querySelector(RAIZ);
  }

  function definirEstado(raiz, estado) {
    window.Alpine.$data(raiz).estado = estado;
  }

  /* O vazio de origem vem do servidor, dentro do fragmento: o marcador é lido depois que o
     Alpine AJAX troca o conteúdo. */
  function aoResponder() {
    const raiz = raizDaTela();
    if (!raiz) return;
    const marcador = raiz.querySelector("[data-situacao]");
    if (marcador) {
      definirEstado(raiz, marcador.getAttribute("data-situacao"));
      return;
    }
    if (window.Alpine.$data(raiz).estado === "carregando") definirEstado(raiz, "conteudo");
  }

  function aoSucesso() {
    window.setTimeout(aoResponder, 0);
  }

  /* Toda requisição do Alpine AJAX (a carga, um filtro) passa por aqui: o endereço fica
     guardado para a nova tentativa repetir o que estava na tela. */
  function aoEnviar(evento) {
    if (evento.detail && evento.detail.url) ultimoEndereco = evento.detail.url;
  }

  function aoErro(evento) {
    const raiz = raizDaTela();
    if (!raiz || window.Alpine.$data(raiz).estado !== "carregando") return;
    const semPermissao = evento.detail && evento.detail.status === 403;
    definirEstado(raiz, semPermissao ? "sem-permissao" : "erro");
  }

  function aoClicar(evento) {
    const alvo = evento.target.closest ? evento.target.closest("[data-painel-recarregar]") : null;
    if (!alvo) return;
    const raiz = raizDaTela();
    if (!raiz) return;
    definirEstado(raiz, "carregando");
    window.Alpine.$data(raiz).carregar(ultimoEndereco);
  }

  function ouvir() {
    if (ouvindo) return;
    ouvindo = true;
    document.addEventListener("ajax:success", aoSucesso);
    document.addEventListener("ajax:sent", aoEnviar);
    document.addEventListener("ajax:error", aoErro);
    document.addEventListener("click", aoClicar);
  }

  window.TN.paginas["hse/painel"] = {
    iniciar: function (raiz) {
      definirEstado(raiz, "carregando");
      ouvir();
      window.Alpine.$data(raiz).carregar();
    }
  };
})();
