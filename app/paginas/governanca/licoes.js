/* ============================================================
   licoes.js — Comportamento da tela Lições aprendidas (governanca/licoes)

   Acervo de lições aprendidas, com busca, filtros, fluxo de validação e aplicação em projeto.

   Registra um único objeto em TN.paginas["governanca/licoes"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela (carregando,
   vazio-origem, vazio-filtro, erro, sem-permissao ou pronto) mora no x-data da view; o
   conteúdo e os modais são fragmentos do servidor, e este arquivo só liga as pontas:

     painel     a resposta traz a marca data-estado (vazio-origem ou vazio-filtro) nos cartões;
                sem marca a tela está pronta; 403 vira sem-permissao e falha vira erro
     kickoff    cada botão de fase preenche fase e situação (Publicada) do formulário de filtros
                e o reenvia; clicar de novo no ativo limpa os dois
     ações      data-licao-acao abre o formulário do servidor no modal: ver, editar, validar e
                aplicar; o 422 volta no próprio modal e o sucesso reabre o acervo com a lição
     nova       "Nova lição" abre o formulário; ?acao=nova vem do mecanismo de inclusão do
                Portfólio (TN.escopo)
     endereço   ?codigo=LA-... abre a ficha da lição (vindo de outro módulo ou de uma gravação)

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const RAIZ = "main.pagina--governanca-licoes";
  const ROTAS = {
    ver: "/api/governanca/licoes/ver",
    editar: "/api/governanca/licoes/editar",
    validar: "/api/governanca/licoes/validar",
    aplicar: "/api/governanca/licoes/aplicar"
  };
  const TITULOS = {
    ver: "Lição",
    editar: "Editar lição",
    validar: "Validar lição",
    aplicar: "Aplicar em projeto"
  };
  let modalAberto = null;
  let ouvindo = false;

  function raizDaTela() {
    return document.querySelector(RAIZ);
  }

  function estadoDaTela(estado) {
    const raiz = raizDaTela();
    if (raiz) window.Alpine.$data(raiz).estado = estado;
  }

  function fecharModal() {
    if (modalAberto) modalAberto.close();
    modalAberto = null;
  }

  function abrirModal(opcoes) {
    fecharModal();
    modalAberto = window.TN.modal({
      title: opcoes.titulo,
      subtitle: opcoes.subtitulo || "",
      width: opcoes.largura || 760,
      onClose: function () { modalAberto = null; },
      body: '<div id="licao-modal" data-endereco="' + window.TN.esc(opcoes.endereco) + '"' +
        " x-init=\"$ajax($el.dataset.endereco, { target: 'licao-modal' })\">" +
        '<div class="spinner" role="status" aria-label="Carregando"></div></div>'
    });
  }

  function aoChegarOPainel(detalhe) {
    if (detalhe && detalhe.ok) {
      const marca = document.querySelector("#licoes-cartoes [data-estado]");
      estadoDaTela(marca ? marca.dataset.estado : "pronto");
      return;
    }
    const status = detalhe ? detalhe.status : 0;
    if (status === 403) estadoDaTela("sem-permissao");
    else if (!status || status >= 500) estadoDaTela("erro");
  }

  function nova() {
    abrirModal({
      titulo: "Nova lição aprendida",
      subtitulo: "O número nasce na gravação e a lição nasce em Rascunho",
      endereco: "/api/governanca/licoes/nova" + window.location.search
    });
  }

  function agir(acao, codigo) {
    const rota = ROTAS[acao] || ROTAS.ver;
    const tipo = ROTAS[acao] ? acao : "ver";
    abrirModal({
      titulo: TITULOS[tipo] + (tipo === "ver" ? " " + codigo : ""),
      largura: tipo === "ver" ? 880 : 760,
      endereco: rota + "?codigo=" + encodeURIComponent(codigo)
    });
  }

  /* Os botões de fase do kickoff filtram pelas lições publicadas da fase; de novo no ativo, limpa. */
  function filtrarPorFase(botao) {
    const fase = document.getElementById("licoes-fase");
    const situacao = document.getElementById("licoes-situacao");
    if (!fase || !situacao) return;
    const ativo = botao.getAttribute("aria-pressed") === "true";
    fase.value = ativo ? "" : botao.dataset.licoesFase;
    situacao.value = ativo ? "" : "Publicada";
    fase.form.requestSubmit();
  }

  function aoClicar(evento) {
    if (!raizDaTela() && !evento.target.closest(".modal-backdrop")) return;
    const fase = evento.target.closest("[data-licoes-fase]");
    if (fase) {
      evento.preventDefault();
      filtrarPorFase(fase);
      return;
    }
    const acao = evento.target.closest("[data-licao-acao]");
    if (acao) {
      evento.preventDefault();
      agir(acao.dataset.licaoAcao, acao.dataset.codigo);
      return;
    }
    if (evento.target.closest("[data-licao-nova]")) {
      evento.preventDefault();
      nova();
    }
  }

  function aoEnviar(evento) {
    if (!raizDaTela() || !(evento.target instanceof Element)) return;
    if (evento.target.closest("#licoes-painel, #licoes-resumo, #licoes-cartoes")) {
      aoChegarOPainel(evento.detail);
    }
  }

  function ouvir() {
    if (ouvindo) return;
    ouvindo = true;
    document.addEventListener("click", aoClicar);
    document.addEventListener("ajax:sent", aoEnviar);
  }

  window.TN.paginas["governanca/licoes"] = {
    iniciar: function (raiz) {
      window.Alpine.$data(raiz).estado = "carregando";
      ouvir();
      const codigo = new URLSearchParams(window.location.search).get("codigo");
      if (codigo) agir("ver", codigo);
      else if (window.TN.escopo.acaoPendente() === "nova") nova();
    }
  };
})();
