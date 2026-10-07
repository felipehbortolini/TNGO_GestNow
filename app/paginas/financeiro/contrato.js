(function () {
  "use strict";

  const ALVOS_DE_CONTEUDO = [
    "contrato-resumo",
    "contrato-medicoes",
    "contrato-aditivos",
    "contrato-marcos",
    "contrato-claims",
    "contrato-extensoes"
  ];
  const ALVO_FORMULARIO = "contrato-formulario";

  function dadosDaTela(raiz) {
    return window.Alpine.$data(raiz);
  }

  function definirEstado(raiz, estado) {
    dadosDaTela(raiz).estado = estado;
  }

  function concluirCarga(raiz, evento) {
    if (dadosDaTela(raiz).estado !== "carregando") return;
    const alvo = evento.target;
    if (alvo instanceof Element && ALVOS_DE_CONTEUDO.indexOf(alvo.id) >= 0) {
      definirEstado(raiz, "conteudo");
    }
  }

  function falharCarga(raiz, evento) {
    if (dadosDaTela(raiz).estado !== "carregando") return;
    const status = evento.detail && evento.detail.status;
    if (status === 403) definirEstado(raiz, "sem-permissao");
    else if (status === 422) definirEstado(raiz, "vazio-origem");
    else definirEstado(raiz, "erro");
  }

  function focarFormulario(evento) {
    const alvo = evento.target;
    if (!(alvo instanceof Element)) return;
    if ((alvo.getAttribute("x-target") || "").indexOf(ALVO_FORMULARIO) < 0) return;
    window.setTimeout(function () {
      const formulario = document.getElementById(ALVO_FORMULARIO);
      if (!formulario) return;
      const campo = formulario.querySelector("input, select, textarea");
      if (!campo) return;
      campo.focus();
      formulario.scrollIntoView({ block: "nearest" });
    }, 0);
  }

  window.TN.paginas["financeiro/contrato"] = {
    iniciar: function (raiz) {
      definirEstado(raiz, "carregando");

      raiz.addEventListener("ajax:success", function (evento) {
        concluirCarga(raiz, evento);
        focarFormulario(evento);
      });

      raiz.addEventListener("ajax:error", function (evento) {
        falharCarga(raiz, evento);
      });
    }
  };
})();
