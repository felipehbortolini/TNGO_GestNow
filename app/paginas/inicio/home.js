/* ============================================================
   home.js — Comportamento da tela Início (inicio/home)

   Indicadores-chave por módulo, carteira de projetos e pontos de atenção
   (ISSUE-079 e ISSUE-080). O modal da Ponderação abre pelo botão do card da
   carteira (data-ponderacao): o corpo #ponderacao-modal carrega o formulário
   do servidor; a Prévia manda o form para a prévia e a gravação responde com a
   marca data-ponderacao-salva, que fecha o modal — e a carteira atualizada, que
   o próprio Alpine AJAX troca pelo alvo declarado.

   Registra um único objeto em TN.paginas["inicio/home"]. A view o aciona por x-init com
   iniciar(raiz), e raiz é o <main> da tela. O estado da tela (carregando, conteudo, erro ou
   sem-permissao) mora no x-data da view; o vazio de origem vem do servidor, dentro do
   fragmento (api/src/templates/inicio/home.html). O servidor desenha tudo — barra de
   contexto, indicadores, carteira, pontos de atenção, cards e as exportações — e aqui mora
   só a carga inicial, o modal da ponderação e a nova tentativa. Os links de indicador,
   atenção e card são âncoras normais com data-tn-tela: a navegação é a do shell.

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const PONDERATION_URL = "/api/inicio/ponderacao";
  const PONDERATION_MODAL = "ponderacao-modal";
  const PONDERATION_WIDTH = 760;

  let modalAberto = null;
  let ouvindo = false;

  function raizDaTela() {
    return document.querySelector("main.pagina--inicio-home");
  }

  function estadoDaTela(estado) {
    const raiz = raizDaTela();
    if (raiz) window.Alpine.$data(raiz).estado = estado;
  }

  function aoFalhar(evento) {
    if (!raizDaTela()) return;
    if (evento.detail && evento.detail.status === 403) estadoDaTela("sem-permissao");
    else estadoDaTela("erro");
  }

  function fecharModal() {
    if (modalAberto) modalAberto.close();
    modalAberto = null;
  }

  function abrirPonderacao() {
    fecharModal();
    modalAberto = window.TN.modal({
      title: "Ponderação da carteira",
      subtitle:
        "Define a relevância de cada projeto na Curva S física e nos índices ponderados do portfólio",
      width: PONDERATION_WIDTH,
      onClose: function () {
        modalAberto = null;
      },
      body:
        '<div id="' +
        PONDERATION_MODAL +
        '" data-endereco="' +
        PONDERATION_URL +
        '" x-init="$ajax($el.dataset.endereco, { target: \'' +
        PONDERATION_MODAL +
        "' })\">" +
        '<div class="spinner" role="status" aria-label="Carregando"></div></div>'
    });
  }

  /* A soma dos pesos é a soma dos campos: acompanha o que se digita, sem gravar. */
  function atualizarSoma(formulario) {
    const alvo = document.getElementById("ponderacao-soma");
    if (!alvo) return;
    let total = 0;
    formulario.querySelectorAll('input[name^="peso_"]').forEach(function (campo) {
      const valor = parseFloat(String(campo.value).replace(",", "."));
      if (!isNaN(valor)) total += valor;
    });
    alvo.textContent = total.toFixed(1).replace(".", ",") + "%";
  }

  function aoClicar(evento) {
    const botao = evento.target.closest && evento.target.closest("[data-ponderacao]");
    if (!botao) return;
    evento.preventDefault();
    abrirPonderacao();
  }

  function aoDigitar(evento) {
    const campo = evento.target;
    const formulario =
      campo.closest && campo.name && campo.name.indexOf("peso_") === 0
        ? campo.closest("form.ponderacao")
        : null;
    if (formulario) atualizarSoma(formulario);
  }

  /* A resposta da gravação traz a marca dentro do modal: a tela fecha. */
  function aoEnviar() {
    if (document.querySelector("#" + PONDERATION_MODAL + " [data-ponderacao-salva]")) {
      fecharModal();
    }
  }

  /* Os ouvintes de documento são de uma vez só: a tela é recarregada a cada navegação. */
  function ouvir() {
    if (ouvindo) return;
    ouvindo = true;
    document.addEventListener("click", aoClicar);
    document.addEventListener("input", aoDigitar);
    document.addEventListener("ajax:sent", aoEnviar);
  }

  window.TN.paginas["inicio/home"] = {
    iniciar: function (raiz) {
      const dados = window.Alpine.$data(raiz);

      /* Só a primeira carga decide entre erro e sem permissão; depois de aberta, a tela se
         mantém e a falha de uma ação vira toast (ds/ui.js). */
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
          })
          .catch(function () {
            /* aoErro já escolheu o estado a partir do ajax:error */
          });
      }

      document.addEventListener("ajax:error", aoErro);
      ouvir();
      raiz.addEventListener("click", function (evento) {
        if (evento.target.closest("[data-home-recarregar]")) carregar();
      });
      carregar();
    }
  };
})();
