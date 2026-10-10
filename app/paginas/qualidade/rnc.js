/* ============================================================
   rnc.js — Comportamento da tela Não conformidades (RNC) (qualidade/rnc)

   A lista é um fragmento do servidor (api/src/templates/qualidade/rnc.html) no alvo
   rnc-conteudo: KPIs, filtros, tabela, páginas e busca são links ou formulários GET com
   x-target. Aqui moram só os modais que o Design System abre por JavaScript: a ficha da RNC
   e os formulários do fluxo (abrir, atribuir, analisar, ação, verificação, eficácia, custo e
   cancelamento), cujo corpo o servidor entrega por GET no alvo rnc-modal-corpo. Depois de
   gravar, o fragmento da lista traz um marcador oculto que reabre a ficha.

   Registra um único objeto em TN.paginas["qualidade/rnc"]; a view o aciona por x-init com
   iniciar(raiz). Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const ALVO_DO_MODAL = "rnc-modal-corpo";
  const LARGURA_DA_FICHA = 1000;
  const LARGURA_DO_FORMULARIO = 760;

  function corpoCarregando(alvo, endereco) {
    return (
      '<div id="' + alvo + '" data-url="' + window.TN.esc(endereco) + '"' +
      " x-init=\"$ajax($el.dataset.url, { target: '" + alvo + "' })\">" +
      '<div class="spinner" role="status" aria-label="Carregando"></div></div>'
    );
  }

  function consultaAtual() {
    return window.location.search ? window.location.search.slice(1) : "";
  }

  function enderecoDaFicha(codigo) {
    const consulta = consultaAtual();
    const sufixo = consulta ? "?" + consulta : "";
    return "/api/qualidade/rnc/" + encodeURIComponent(codigo) + "/ficha" + sufixo;
  }

  function abrirFicha(codigo) {
    window.TN.modal({
      title: codigo,
      subtitle: "Não conformidade registrada",
      width: LARGURA_DA_FICHA,
      body: corpoCarregando(ALVO_DO_MODAL, enderecoDaFicha(codigo))
    });
  }

  function abrirFormulario(botao) {
    window.TN.modal({
      title: botao.dataset.rncTitulo,
      width: LARGURA_DO_FORMULARIO,
      body: corpoCarregando(ALVO_DO_MODAL, botao.dataset.rncUrl)
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
    const fechar = alvo.closest("[data-rnc-fechar-modal]");
    const formulario = alvo.closest("[data-rnc-formulario]");
    const ficha = alvo.closest("[data-rnc-ficha]");
    if (fechar) {
      fecharModalDe(fechar);
    } else if (formulario) {
      if (formulario.dataset.rncFechar) fecharModalDe(formulario);
      abrirFormulario(formulario);
    } else if (ficha) {
      evento.preventDefault();
      abrirFicha(ficha.getAttribute("data-rnc-ficha"));
    }
  });

  window.TN.paginas["qualidade/rnc"] = {
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
        if (evento.target.closest("[data-rnc-recarregar]")) carregar();
      });
      carregar();
    },

    /* Depois de uma gravação o fragmento da lista traz o marcador oculto com o número da RNC:
       este abre a ficha atualizada no lugar do modal que se fechou. */
    abrirFicha: function (marcador) {
      window.setTimeout(function () {
        abrirFicha(marcador.getAttribute("data-rnc-abrir-ficha"));
      }, 50);
    }
  };
})();
