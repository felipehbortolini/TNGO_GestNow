/* ============================================================
   diligenciamento.js — Comportamento da tela Diligenciamento e recebimento (suprimentos/diligenciamento)

   Marcos dos pedidos, folga sobre o ROS, ação na Central e recebimento na obra (ISSUE-061).

   Registra um único objeto em TN.paginas["suprimentos/diligenciamento"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela (carregando, conteudo,
   erro ou sem-permissao) mora no x-data da view; os estados vazio de origem e vazio por filtro
   vêm do servidor, dentro do fragmento. O servidor desenha tudo
   (api/src/templates/suprimentos/diligenciamento.html): KPIs, busca, filtros, bloco de
   pendências, tabela, ficha e páginas são links ou um formulário GET com x-target. Aqui moram os
   modais que o Design System abre por JavaScript — Atualizar marco, Registrar recebimento e a
   importação genérica do ERP —, cujo corpo o servidor entrega por GET no alvo do modal, e a ação
   pendente do mecanismo de inclusão do Portfólio (?acao=importar, TN.escopo).

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const ALVO_DO_MODAL = "diligenciamento-modal-corpo";
  const LARGURA_DO_FORM = 880;
  const LARGURA_DA_IMPORTACAO = 880;

  let modalAberto = null;
  let importando = false;
  let acaoPendente = null;
  let ouvindo = false;

  function raizDaTela() {
    return document.querySelector("main.pagina--suprimentos-diligenciamento");
  }

  function estadoDaTela(estado) {
    const raiz = raizDaTela();
    if (raiz) window.Alpine.$data(raiz).estado = estado;
  }

  function recarregarConteudo() {
    const raiz = raizDaTela();
    if (!raiz) return;
    const filtro = raiz.querySelector("#diligenciamento-conteudo form.busca");
    if (filtro) filtro.requestSubmit();
    else window.Alpine.$data(raiz).carregar();
  }

  /* ---------- Modais ---------- */

  function fecharModal() {
    if (modalAberto) modalAberto.close();
    modalAberto = null;
  }

  /* O corpo do modal pede o fragmento ao servidor assim que o Alpine o inicializa; o endereço
     vai por data-url para nunca ser interpolado dentro de uma expressão. */
  function corpoCarregando(endereco) {
    return (
      '<div id="' + ALVO_DO_MODAL + '" data-url="' + window.TN.esc(endereco) + '"' +
      " x-init=\"$ajax($el.dataset.url, { target: '" + ALVO_DO_MODAL + "' })\">" +
      '<div class="spinner" role="status" aria-label="' + window.TN.t("suprimentos", "Carregando") + '"></div></div>'
    );
  }

  function abrirModal(opcoes) {
    fecharModal();
    modalAberto = window.TN.modal({
      title: opcoes.titulo,
      subtitle: opcoes.subtitulo,
      width: opcoes.largura,
      onClose: function () {
        modalAberto = null;
        if (importando) {
          importando = false;
          recarregarConteudo();
        }
      },
      body: corpoCarregando(opcoes.endereco)
    });
  }

  function abrirFormulario(botao) {
    abrirModal({
      titulo: botao.dataset.diligenciaModalTitulo,
      subtitulo: botao.dataset.diligenciaModalSubtitulo,
      largura: LARGURA_DO_FORM,
      endereco: botao.dataset.diligenciaModalUrl
    });
  }

  function abrirImportacao(botao) {
    importando = true;
    abrirModal({
      titulo: window.TN.t("suprimentos", "Importar pedidos do ERP"),
      subtitulo: window.TN.t("suprimentos", "Uma linha por marco: previsão atualizada ou data realizada; nada grava antes da confirmação"),
      largura: LARGURA_DA_IMPORTACAO,
      endereco: botao.dataset.diligenciaUrl
    });
  }

  function abrirAcaoPendente() {
    if (!acaoPendente) return;
    const raiz = raizDaTela();
    const botao = raiz && raiz.querySelector('[data-tn-incluir="' + acaoPendente + '"]');
    if (!botao) return;
    acaoPendente = null;
    botao.click();
  }

  /* ---------- Eventos ---------- */

  function aoClicar(evento) {
    if (!raizDaTela()) return;
    const editar = evento.target.closest ? evento.target.closest("[data-diligencia-modal-url]") : null;
    if (editar) {
      evento.preventDefault();
      abrirFormulario(editar);
      return;
    }
    const fechar = evento.target.closest ? evento.target.closest("[data-diligencia-fechar-modal]") : null;
    if (fechar) {
      evento.preventDefault();
      fecharModal();
      return;
    }
    const acao = evento.target.closest ? evento.target.closest("[data-diligencia-acao]") : null;
    if (!acao) return;
    if (acao.dataset.diligenciaAcao === "importar") {
      evento.preventDefault();
      abrirImportacao(acao);
    }
  }

  function aoFalhar(evento) {
    const raiz = raizDaTela();
    if (!raiz) return;
    if (evento.detail && evento.detail.status === 403) estadoDaTela("sem-permissao");
    else estadoDaTela("erro");
  }

  function ouvir() {
    if (ouvindo) return;
    ouvindo = true;
    document.addEventListener("click", aoClicar);
  }

  window.TN.paginas["suprimentos/diligenciamento"] = {
    iniciar: function (raiz) {
      const dados = window.Alpine.$data(raiz);
      acaoPendente = window.TN.escopo.acaoPendente();
      ouvir();

      /* Só a primeira carga decide entre erro e sem permissão; depois de aberta, a tela se
         mantém e a falha de uma ação vira toast (ds/ui.js) ou a mensagem no modal. */
      function aoErro(evento) {
        if (!raiz.isConnected) {
          document.removeEventListener("ajax:error", aoErro);
          return;
        }
        if (dados.estado !== "carregando") return;
        aoFalhar(evento);
      }

      function carregar() {
        dados.estado = "carregando";
        dados
          .carregar()
          .then(function () {
            if (dados.estado === "carregando") dados.estado = "conteudo";
            abrirAcaoPendente();
          })
          .catch(function () {
            /* aoErro já escolheu o estado a partir do ajax:error */
          });
      }

      document.addEventListener("ajax:error", aoErro);
      raiz.addEventListener("click", function (evento) {
        if (evento.target.closest("[data-diligencia-recarregar]")) carregar();
      });
      carregar();
    }
  };
})();
