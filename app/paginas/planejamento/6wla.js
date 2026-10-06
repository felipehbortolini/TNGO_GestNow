/* ============================================================
   6wla.js — Comportamento da tela 6WLA (planejamento/6wla)

   Atividades por semana (seis semanas), restrições e responsáveis.

   Registra um único objeto em TN.paginas["planejamento/6wla"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela
   (carregando, vazio-origem, vazio-filtro, conteudo, erro ou sem-permissao) mora no
   x-data da view. O servidor desenha tudo (filtros, indicadores, Gantt, grade,
   restrições e formulários); este arquivo só:

   - lê o `data-resultado` do conteúdo que chegou e escolhe o estado;
   - leva os filtros da tela para os botões Excel e PDF, que exportam o que se vê;
   - leva a pessoa ao formulário que acabou de abrir;
   - abre o formulário pedido pelo mecanismo de inclusão do Portfólio (?acao=).

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const ID_CONTEUDO = "lookahead-conteudo";
  const ID_FORMULARIO = "lookahead-formulario";
  const ID_FILTROS = "lookahead-filtros";
  const STATUS_SEM_PERMISSAO = 403;
  const STATUS_ERRO_DE_SERVIDOR = 500;
  const ESTADOS_DO_CONTEUDO = ["vazio-origem", "vazio-filtro", "conteudo"];
  const EXPORTACOES = [
    ["data-tn-excel", "tnExcelBase"],
    ["data-tn-pdf", "tnPdfBase"]
  ];

  /* O estado que a resposta da carga pede: 403 e falha de servidor ou de rede
     têm tela própria; do resto, o conteúdo diz. */
  function estadoDaCarga(raiz, status) {
    if (status === STATUS_SEM_PERMISSAO) return "sem-permissao";
    if (!status || status >= STATUS_ERRO_DE_SERVIDOR) return "erro";
    return estadoDoConteudo(raiz);
  }

  function estadoDoConteudo(raiz) {
    const conteudo = raiz.querySelector("#" + ID_CONTEUDO);
    const resultado = conteudo ? conteudo.dataset.resultado : null;
    return ESTADOS_DO_CONTEUDO.includes(resultado) ? resultado : null;
  }

  function aoTerminarPedido(raiz, evento) {
    const status = evento.detail ? evento.detail.status : 0;
    const dados = window.Alpine.$data(raiz);
    const daCarga = evento.target.hasAttribute && evento.target.hasAttribute("data-lookahead-carga");
    const estado = daCarga ? estadoDaCarga(raiz, status) : estadoDoConteudo(raiz);
    if (estado) dados.estado = estado;
    sincronizarExportacao(raiz);
    levarAoFormulario(raiz, evento);
  }

  /* Excel e PDF exportam o que a pessoa filtrou: os mesmos campos, na consulta. */
  function sincronizarExportacao(raiz) {
    const formulario = raiz.querySelector("#" + ID_FILTROS + " form");
    const consulta = formulario ? new URLSearchParams(new FormData(formulario)).toString() : "";
    EXPORTACOES.forEach(function (par) {
      const botao = raiz.querySelector("[" + par[0] + "]");
      if (!botao) return;
      if (!botao.dataset[par[1]]) botao.dataset[par[1]] = botao.getAttribute(par[0]);
      const base = botao.dataset[par[1]];
      botao.setAttribute(par[0], consulta ? base + "?" + consulta : base);
    });
  }

  /* Formulário que acabou de abrir: rola até ele e põe o foco no primeiro campo. */
  function levarAoFormulario(raiz, evento) {
    const formulario = raiz.querySelector("#" + ID_FORMULARIO);
    const abriu = evento.target.closest && evento.target.closest("[data-tn-incluir], .iconbtn, .btn");
    if (!formulario || !formulario.firstElementChild || !abriu) return;
    formulario.scrollIntoView({ behavior: "smooth", block: "start" });
    const campo = formulario.querySelector("input:not([type=hidden]), select, textarea");
    if (campo) campo.focus();
  }

  /* Ação pedida pelo mecanismo de inclusão do Portfólio: reabre a tela no projeto
     com ?acao=atividade ou ?acao=restricao; clica o botão quando os filtros chegarem. */
  function abrirAcaoPendente(raiz, acao) {
    const botao = raiz.querySelector('[data-tn-incluir="' + acao + '"]');
    if (botao) botao.click();
    return Boolean(botao);
  }

  window.TN.paginas["planejamento/6wla"] = {
    iniciar: function (raiz) {
      let acao = window.TN.escopo.acaoPendente();
      raiz.addEventListener("ajax:sent", function (evento) {
        aoTerminarPedido(raiz, evento);
        if (acao && abrirAcaoPendente(raiz, acao)) acao = null;
      });
      raiz.addEventListener("input", function () {
        sincronizarExportacao(raiz);
      });
    }
  };
})();
