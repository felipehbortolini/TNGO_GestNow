/* ============================================================
   kpis.js — Comportamento da tela KPIs (planejamento/kpis)

   Avanço previsto e real, SPI e desvios por período e por área.

   Registra um único objeto em TN.paginas["planejamento/kpis"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela
   (carregando, conteudo, vazio-origem, vazio-filtro, erro ou sem-permissao) mora
   no x-data da view e vem do marcador data-situacao que o servidor põe no
   fragmento; 403 vira sem-permissao e qualquer outra falha da primeira carga
   vira erro. Os gráficos nascem do data-grafico/data-dados do fragmento pela
   biblioteca do Design System — esta página não desenha SVG nem busca dados.
   O Portfólio é resolvido pelo servidor, no mesmo endpoint do projeto.

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const ESTADOS_DE_RESULTADO = ["conteudo", "vazio-origem"];
  const RAIZ = "main.pagina--planejamento-kpis";

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

  window.TN.paginas["planejamento/kpis"] = {
    iniciar: function (raiz) {
      definirEstado(raiz, "carregando");
      ouvir();
    }
  };
})();
