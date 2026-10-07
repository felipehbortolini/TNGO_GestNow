/* ============================================================
   mapa_controle.js — Comportamento da tela Mapa de controle (financeiro/mapa_controle)

   Orçado, comprometido, realizado, saldo, projeção no término e desvio por item, com o
   mapa de calor do desvio no visual Tabela Heatmap (o desenho vem do data-grafico do
   servidor; aqui não se monta grade).

   Registra um único objeto em TN.paginas["financeiro/mapa_controle"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela (carregando,
   conteudo, vazio-origem, vazio-filtro, erro ou sem-permissao) mora no x-data da view e
   vem do marcador data-resultado que o servidor põe no conteúdo; 403 vira sem-permissao e
   qualquer outra falha da primeira carga vira erro.

   Também cuida do modal da importação dos custos do ERP (o corpo é o formulário genérico
   que o servidor entrega por GET), da ação importar pendente do Portfólio (o mecanismo de
   inclusão pede o projeto e reabre a tela com ?acao=importar) e dos botões de projeção da
   tabela servidora, abrindo o formulário no alvo mapa-projecao-formulario. No visual, a
   célula clicável do desvio abre o mesmo formulário pelo @grafico:selecionar do fragmento.

   Carrega pelo shell (app/index.html), nunca pela view. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const ROTA = "/api/financeiro/mapa-de-controle";
  const ROTA_IMPORTACAO = "/api/financeiro/custos/importar/formulario";
  const ALVO_FORMULARIO = "mapa-projecao-formulario";
  const ALVO_MODAL = "custos-importar-modal";
  const LARGURA_DO_MODAL = 720;
  const ESTADOS_DE_RESULTADO = ["conteudo", "vazio-origem"];

  let modalImportacao = null;

  function dadosDaTela(raiz) {
    return window.Alpine.$data(raiz);
  }

  function definirEstado(raiz, estado) {
    dadosDaTela(raiz).estado = estado;
  }

  function resultadoDoConteudo(raiz) {
    const marcador = raiz.querySelector("[data-resultado]");
    return marcador ? marcador.getAttribute("data-resultado") : "";
  }

  function noPortfolio() {
    return window.TN.escopo ? window.TN.escopo.noPortfolio() : false;
  }

  function fecharModal() {
    if (modalImportacao) modalImportacao.close();
    modalImportacao = null;
  }

  function corpoDoModal() {
    return (
      '<div id="' + ALVO_MODAL + '"' +
      ' x-init="$ajax(\'' + ROTA_IMPORTACAO + '\', { target: \'' + ALVO_MODAL + '\' })">' +
      '<div class="spinner" role="status" aria-label="Carregando a importação"></div></div>'
    );
  }

  function abrirImportacao() {
    fecharModal();
    modalImportacao = window.TN.modal({
      title: "Importar custos do ERP",
      subtitle: "Fechamento do mês: comprometido, realizado e projeção no término por item",
      width: LARGURA_DO_MODAL,
      onClose: function () { modalImportacao = null; },
      body: corpoDoModal()
    });
  }

  function abrirProjecao(raiz, itemId) {
    window.Alpine.evaluate(raiz, "$ajax(endereco, { target: alvo })", {
      scope: { endereco: ROTA + "/projecao/" + itemId + "/formulario", alvo: ALVO_FORMULARIO }
    });
  }

  function aoResponder(raiz) {
    const resultado = resultadoDoConteudo(raiz);
    definirEstado(raiz, ESTADOS_DE_RESULTADO.indexOf(resultado) >= 0 ? resultado : "erro");
  }

  function aoFalhar(raiz, evento) {
    if (dadosDaTela(raiz).estado !== "carregando") return;
    const status = evento.detail && evento.detail.status;
    definirEstado(raiz, status === 403 ? "sem-permissao" : "erro");
  }

  function aoClicar(raiz, evento) {
    if (evento.target.closest("[data-mapa-importar]")) {
      if (!noPortfolio()) abrirImportacao();
      return;
    }
    const projetar = evento.target.closest("[data-projecao]");
    if (projetar) abrirProjecao(raiz, projetar.getAttribute("data-projecao"));
  }

  window.TN.paginas["financeiro/mapa_controle"] = {
    iniciar: function (raiz) {
      const dados = dadosDaTela(raiz);
      const acao = window.TN.escopo ? window.TN.escopo.acaoPendente() : null;

      raiz.addEventListener("ajax:success", function () {
        window.setTimeout(function () { aoResponder(raiz); }, 0);
      });

      raiz.addEventListener("ajax:error", function (evento) {
        aoFalhar(raiz, evento);
      });

      raiz.addEventListener("click", function (evento) {
        aoClicar(raiz, evento);
      });

      dados.carregar().then(function () {
        aoResponder(raiz);
        if (acao === "importar" && !noPortfolio()) abrirImportacao();
      });
    }
  };
})();
