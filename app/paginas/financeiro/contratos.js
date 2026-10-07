(function () {
  "use strict";

  const ROTA = "/api/financeiro/contratos/consolidado";
  const ALVO_CONTEUDO = "contratos-conteudo";
  const EXPORTACOES = [
    ["data-tn-excel", "tnExcelBase"],
    ["data-tn-pdf", "tnPdfBase"]
  ];

  function dadosDaTela(raiz) {
    return window.Alpine.$data(raiz);
  }

  function definirEstado(raiz, estado) {
    dadosDaTela(raiz).estado = estado;
  }

  function resultadoDoConteudo(raiz) {
    const conteudo = raiz.querySelector("#" + ALVO_CONTEUDO);
    if (!conteudo || !conteudo.firstElementChild) return "";
    return conteudo.querySelector("[data-estado='vazio-origem']") ? "vazio-origem" : "conteudo";
  }

  function formularioDeFiltros(raiz) {
    return raiz.querySelector("#" + ALVO_CONTEUDO + " form[action='" + ROTA + "']");
  }

  function consultaDosFiltros(raiz) {
    const formulario = formularioDeFiltros(raiz);
    if (!formulario) return "";
    return new URLSearchParams(new FormData(formulario)).toString();
  }

  function sincronizarExportacao(raiz) {
    const consulta = consultaDosFiltros(raiz);
    EXPORTACOES.forEach(function (par) {
      const botao = raiz.querySelector("[" + par[0] + "]");
      if (!botao) return;
      if (!botao.dataset[par[1]]) botao.dataset[par[1]] = botao.getAttribute(par[0]);
      const base = botao.dataset[par[1]];
      botao.setAttribute(par[0], consulta ? base + "?" + consulta : base);
    });
  }

  function aoResponder(raiz) {
    const resultado = resultadoDoConteudo(raiz);
    if (resultado) definirEstado(raiz, resultado);
    sincronizarExportacao(raiz);
  }

  function aoFalhar(raiz, evento) {
    const status = evento.detail && evento.detail.status;
    if (status === 403) {
      definirEstado(raiz, "sem-permissao");
      return;
    }
    if (dadosDaTela(raiz).estado !== "carregando") return;
    definirEstado(raiz, status === 422 ? "vazio-origem" : "erro");
  }

  window.TN.paginas["financeiro/contratos"] = {
    iniciar: function (raiz) {
      raiz.addEventListener("ajax:success", function () {
        window.setTimeout(function () {
          aoResponder(raiz);
        }, 0);
      });

      raiz.addEventListener("ajax:error", function (evento) {
        aoFalhar(raiz, evento);
      });

      dadosDaTela(raiz).carregar().then(function () {
        aoResponder(raiz);
      });
    }
  };
})();
