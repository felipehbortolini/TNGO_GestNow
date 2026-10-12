/* ============================================================
   inspecoes.js — Comportamento da tela Inspeções e ITP (qualidade/inspecoes)

   A lista é um fragmento do servidor (api/src/templates/qualidade/inspecoes.html) no alvo
   inspecoes-conteudo: KPIs, tabela dos ITPs, filtros, tabela das inspeções e páginas são
   links ou formulários GET com x-target. Aqui moram só os modais que o Design System abre
   por JavaScript: a ficha do ITP e os formulários (novo ITP, nova revisão, aprovação do
   cliente e registro de inspeção), cujo corpo o servidor entrega por GET no alvo
   inspecoes-modal-corpo.

   Registra um único objeto em TN.paginas["qualidade/inspecoes"]; a view o aciona por
   x-init com iniciar(raiz). Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const ALVO_DO_MODAL = "inspecoes-modal-corpo";
  const LARGURA_DA_FICHA = 1000;
  const LARGURA_DO_FORMULARIO = 760;
  const LARGURA_DO_ITP = 980;

  function corpoCarregando(alvo, endereco) {
    return (
      '<div id="' + alvo + '" data-url="' + window.TN.esc(endereco) + '"' +
      " x-init=\"$ajax($el.dataset.url, { target: '" + alvo + "' })\">" +
      '<div class="spinner" role="status" aria-label="' + window.TN.t("qualidade", "Carregando") + '"></div></div>'
    );
  }

  function consultaAtual() {
    return window.location.search ? window.location.search.slice(1) : "";
  }

  function enderecoDaFicha(codigo) {
    const consulta = consultaAtual();
    const sufixo = consulta ? "?" + consulta : "";
    return "/api/qualidade/inspecoes/" + encodeURIComponent(codigo) + "/ficha" + sufixo;
  }

  function abrirFicha(codigo) {
    window.TN.modal({
      title: codigo,
      subtitle: window.TN.t("qualidade", "Plano de inspeção e testes"),
      width: LARGURA_DA_FICHA,
      body: corpoCarregando(ALVO_DO_MODAL, enderecoDaFicha(codigo))
    });
  }

  function abrirFormulario(botao) {
    const url = botao.dataset.inspecoesUrl;
    const largura = url && url.indexOf("/itp/") >= 0 ? LARGURA_DO_ITP : LARGURA_DO_FORMULARIO;
    window.TN.modal({
      title: botao.dataset.inspecoesTitulo,
      width: largura,
      body: corpoCarregando(ALVO_DO_MODAL, url)
    });
  }

  function fecharModalDe(elemento) {
    const fundo = elemento.closest(".modal-backdrop");
    const fechar = fundo ? fundo.querySelector(".modal__close") : null;
    if (fechar) fechar.click();
  }

  /* Um só ouvinte no documento, registrado quando o script carrega: o modal mora fora da raiz
     da tela (o Design System o anexa ao fim do <body>) e a tela pode ser aberta várias vezes. */
  document.addEventListener("click", function (evento) {
    const alvo = evento.target.closest ? evento.target : null;
    if (!alvo) return;
    const fechar = alvo.closest("[data-inspecoes-fechar-modal]");
    const formulario = alvo.closest("[data-inspecoes-formulario]");
    const ficha = alvo.closest("[data-itp-ficha]");
    if (fechar) {
      fecharModalDe(fechar);
    } else if (formulario) {
      if (formulario.dataset.inspecoesFechar) fecharModalDe(formulario);
      abrirFormulario(formulario);
    } else if (ficha) {
      evento.preventDefault();
      abrirFicha(ficha.getAttribute("data-itp-ficha"));
    }
  });

  window.TN.paginas["qualidade/inspecoes"] = {
    iniciar: function (raiz) {
      const dados = window.Alpine.$data(raiz);

      function aoFalhar(evento) {
        if (!raiz.isConnected) {
          document.removeEventListener("ajax:error", aoFalhar);
          return;
        }
        if (dados.estado !== "carregando") return;
        dados.estado = evento.detail && evento.detail.status === 403 ? "sem-permissao" : "erro";
      }

      function carregar() {
        dados.estado = "carregando";
        dados.carregar().then(function () {
          if (dados.estado === "carregando") dados.estado = "conteudo";
        });
      }

      document.addEventListener("ajax:error", aoFalhar);
      raiz.addEventListener("click", function (evento) {
        if (evento.target.closest("[data-inspecoes-recarregar]")) carregar();
      });
      carregar();
    },

    /* Os formulários que abrem de dentro da ficha fecham a ficha antes de abrir o modal. */
    abrirFicha: abrirFicha
  };
})();
