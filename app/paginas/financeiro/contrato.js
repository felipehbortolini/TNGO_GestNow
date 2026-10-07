(function () {
  "use strict";

  const ALVOS_DE_CONTEUDO = [
    "contrato-resumo",
    "contrato-medicoes",
    "contrato-aditivos",
    "contrato-marcos",
    "contrato-claims",
    "contrato-extensoes",
    "contrato-avaliacoes"
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

  function formularioDaAvaliacao(alvo) {
    if (!(alvo instanceof Element)) return null;
    return alvo.closest("form[data-avaliacao]");
  }

  function temNotaBaixa(formulario) {
    const limite = Number(formulario.getAttribute("data-limite-plano"));
    const notas = Array.from(formulario.querySelectorAll("input[data-nota]"));
    return notas.some(function (campo) {
      const nota = Number(campo.value);
      return campo.value !== "" && nota >= 1 && nota <= limite;
    });
  }

  function sincronizarAvisoDePlano(formulario) {
    const aviso = formulario.querySelector("[data-aviso-plano]");
    if (!aviso) return;
    aviso.hidden = !temNotaBaixa(formulario);
  }

  function atualizarAvisoDePlano(evento) {
    const formulario = formularioDaAvaliacao(evento.target);
    if (formulario) sincronizarAvisoDePlano(formulario);
  }

  function sincronizarAvisosDePlano(raiz) {
    window.setTimeout(function () {
      raiz.querySelectorAll("form[data-avaliacao]").forEach(sincronizarAvisoDePlano);
    }, 0);
  }

  window.TN.paginas["financeiro/contrato"] = {
    iniciar: function (raiz) {
      definirEstado(raiz, "carregando");

      raiz.addEventListener("input", atualizarAvisoDePlano);

      raiz.addEventListener("ajax:success", function (evento) {
        concluirCarga(raiz, evento);
        focarFormulario(evento);
        sincronizarAvisosDePlano(raiz);
      });

      raiz.addEventListener("ajax:error", function (evento) {
        falharCarga(raiz, evento);
        sincronizarAvisosDePlano(raiz);
      });
    }
  };
})();
