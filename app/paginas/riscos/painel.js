/* ============================================================
   painel.js — Comportamento da tela Painel de riscos (riscos/painel)

   Exposição, evolução do score residual e pauta de escalonamento (ISSUE-066).

   Registra um único objeto em TN.paginas["riscos/painel"]. A view o aciona por x-init com
   iniciar(raiz), e raiz é o <main> da tela. O estado da tela (carregando, conteudo,
   vazio-origem, erro ou sem-permissao) mora no x-data da view; o vazio de origem vem do
   servidor, dentro do fragmento (o marcador data-situacao), e erro/sem permissão saem do
   ajax:error. O servidor desenha tudo (api/src/templates/riscos/painel.html): KPIs, gráficos
   (data-grafico + data-dados), as categorias, a pauta e as exportações. Aqui moram a carga
   inicial, a nova tentativa e o modal do envio da pauta, cujo corpo o servidor entrega por GET
   no alvo do modal.

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const RAIZ = "main.pagina--riscos-painel";
  const ROTA_PAUTA = "/api/riscos/painel/pauta";
  const ALVO_DO_MODAL = "riscos-pauta-modal";

  let modalPauta = null;
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

  /* O corpo do modal pede o formulário ao servidor assim que o Alpine o inicializa; o endereço
     vai por data-url para nunca ser interpolado dentro de uma expressão. */
  function corpoDoEnvio() {
    return (
      '<div id="' + ALVO_DO_MODAL + '" data-url="' + window.TN.esc(ROTA_PAUTA) + '"' +
      " x-init=\"$ajax($el.dataset.url, { target: '" + ALVO_DO_MODAL + "' })\">" +
      '<div class="spinner" role="status" aria-label="' + window.TN.t("riscos", "Carregando o envio") + '"></div></div>'
    );
  }

  function abrirEnvio() {
    if (modalPauta) modalPauta.close();
    modalPauta = window.TN.modal({
      title: window.TN.t("riscos", "Enviar pauta por e-mail"),
      subtitle: window.TN.t("riscos", "O envio fica registrado na trilha de auditoria"),
      width: 720,
      onClose: function () {
        modalPauta = null;
      },
      body: corpoDoEnvio()
    });
  }

  function fecharModalDe(elemento) {
    const fundo = elemento.closest(".modal-backdrop");
    const fechar = fundo ? fundo.querySelector(".modal__close") : null;
    if (fechar) fechar.click();
  }

  function aoClicar(evento) {
    const alvo = evento.target.closest ? evento.target : null;
    if (!alvo) return;
    if (alvo.closest("[data-riscos-pauta-enviar]")) {
      abrirEnvio();
      return;
    }
    const fechar = alvo.closest("[data-riscos-pauta-fechar-modal]");
    if (fechar) fecharModalDe(fechar);
  }

  function ouvir() {
    if (ouvindo) return;
    ouvindo = true;
    document.addEventListener("ajax:success", aoSucesso);
    document.addEventListener("ajax:error", aoErro);
    document.addEventListener("click", aoClicar);
    document.addEventListener("click", function (evento) {
      const alvo = evento.target.closest ? evento.target.closest("[data-painel-recarregar]") : null;
      if (!alvo) return;
      const raiz = raizDaTela();
      if (!raiz) return;
      definirEstado(raiz, "carregando");
      window.Alpine.$data(raiz).carregar();
    });
  }

  window.TN.paginas["riscos/painel"] = {
    iniciar: function (raiz) {
      definirEstado(raiz, "carregando");
      ouvir();
      if (window.TN.analise) window.TN.analise.abrirDoEndereco("riscos");
      window.Alpine.$data(raiz).carregar();
    }
  };
})();
