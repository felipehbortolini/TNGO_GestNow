/* ============================================================
   painel.js — Comportamento da tela Painel da qualidade (qualidade/painel)

   RNC, inspeções, auditorias, Pareto, custo da não qualidade e pauta de tratamento
   (ISSUE-071).

   Registra um único objeto em TN.paginas["qualidade/painel"]. A view o aciona por x-init com
   iniciar(raiz), e raiz é o <main> da tela. O estado da tela (carregando, conteudo,
   vazio-origem, erro ou sem-permissao) mora no x-data da view; o vazio de origem vem do
   servidor, dentro do fragmento (o marcador data-situacao), e erro/sem permissão saem do
   ajax:error. O servidor desenha tudo (api/src/templates/qualidade/painel.html): KPIs,
   gráficos (data-grafico + data-dados), o alerta de auditorias atrasadas e as duas tabelas.
   Aqui moram a carga inicial e a nova tentativa.

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const RAIZ = "main.pagina--qualidade-painel";

  let ouvindo = false;

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
    window.Alpine.$data(raiz).carregar();
  }

  function ouvir() {
    if (ouvindo) return;
    ouvindo = true;
    document.addEventListener("ajax:success", aoSucesso);
    document.addEventListener("ajax:error", aoErro);
    document.addEventListener("click", aoClicar);
  }

  window.TN.paginas["qualidade/painel"] = {
    iniciar: function (raiz) {
      definirEstado(raiz, "carregando");
      ouvir();
      if (window.TN.analise) window.TN.analise.abrirDoEndereco("qualidade");
      window.Alpine.$data(raiz).carregar();
    }
  };
})();
