/* ============================================================
   registro.js — Comportamento da tela Registro de riscos (riscos/registro)

   Ameaças e oportunidades com avaliação, filtros e próximas revisões (ISSUE-064, HU-107).

   Registra um único objeto em TN.paginas["riscos/registro"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela
   (carregando, conteudo, erro ou sem-permissao) mora no x-data da view; os estados vazio de
   origem e vazio por filtro vêm do servidor, dentro do fragmento.

   O servidor desenha tudo (api/src/templates/riscos/registro.html): contexto, KPIs, chips,
   alternador Inerente/Residual, tabela, páginas e busca são links ou formulários GET com
   x-target. Aqui só moram os modais que o Design System abre por JavaScript: os filtros (o
   formulário vem num <template> do fragmento), o cadastro rápido de categoria e os formulários
   da linha (novo, editar, avaliar, excluir), cujo corpo o servidor entrega por GET no alvo do
   modal. Depois de "Salvar e avaliar" o fragmento traz um marcador oculto que reabre a avaliação.

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const ALVO_DO_MODAL = "registro-modal-corpo";
  const ALVO_DA_CATEGORIA = "risco-categoria-modal";
  const LARGURA_PADRAO = 760;
  const LARGURA_DA_AVALIACAO = 880;
  const LARGURA_DA_EXCLUSAO = 560;
  const LARGURA_DA_CATEGORIA = 520;
  const LARGURA_DOS_FILTROS = 720;

  /* O corpo do modal pede o fragmento ao servidor assim que o Alpine o inicializa; o endereço
     vai por data-url para nunca ser interpolado dentro de uma expressão. */
  function corpoCarregando(alvo, endereco) {
    return (
      '<div id="' + alvo + '" data-url="' + window.TN.esc(endereco) + '"' +
      " x-init=\"$ajax($el.dataset.url, { target: '" + alvo + "' })\">" +
      '<div class="spinner" role="status" aria-label="Carregando"></div></div>'
    );
  }

  function larguraDe(endereco) {
    if (endereco.indexOf("/avaliar") >= 0) return LARGURA_DA_AVALIACAO;
    if (endereco.indexOf("/excluir") >= 0) return LARGURA_DA_EXCLUSAO;
    return LARGURA_PADRAO;
  }

  function abrirFormulario(botao) {
    window.TN.modal({
      title: botao.dataset.registroModalTitulo,
      subtitle: botao.dataset.registroModalSubtitulo,
      width: larguraDe(botao.dataset.registroModalUrl),
      body: corpoCarregando(ALVO_DO_MODAL, botao.dataset.registroModalUrl)
    });
  }

  function abrirFiltros() {
    const modelo = document.querySelector("template[data-registro-filtros-modelo]");
    if (!modelo) return;
    window.TN.modal({
      title: "Filtros do registro",
      subtitle: "Busca, natureza, severidade e revisão",
      width: LARGURA_DOS_FILTROS,
      body: modelo.innerHTML
    });
  }

  function abrirCategoria() {
    window.TN.modal({
      title: "Nova categoria (RBS)",
      subtitle: "Cadastro rápido do catálogo mantido em Configurações",
      width: LARGURA_DA_CATEGORIA,
      body: corpoCarregando(ALVO_DA_CATEGORIA, "/api/riscos/categorias/nova")
    });
  }

  function fecharModalDe(elemento) {
    const fundo = elemento.closest(".modal-backdrop");
    const fechar = fundo ? fundo.querySelector(".modal__close") : null;
    if (fechar) fechar.click();
  }

  /* Um só ouvinte no documento, registrado quando o script carrega: o modal mora fora da raiz da
     tela (o Design System o anexa ao fim do <body>) e a tela pode ser aberta várias vezes. */
  document.addEventListener("click", function (evento) {
    const alvo = evento.target.closest ? evento.target : null;
    if (!alvo) return;
    const filtros = alvo.closest("[data-registro-filtros]");
    const categoria = alvo.closest("[data-registro-categoria]");
    const formulario = alvo.closest("[data-registro-modal-url]");
    const cancelar = alvo.closest("[data-registro-fechar-modal]");
    if (filtros) abrirFiltros();
    else if (categoria) abrirCategoria();
    else if (formulario) abrirFormulario(formulario);
    else if (cancelar) fecharModalDe(cancelar);
  });

  window.TN.paginas["riscos/registro"] = {
    iniciar: function (raiz) {
      const dados = window.Alpine.$data(raiz);

      /* Só a primeira carga decide entre erro e sem permissão; depois de aberta, a tela se
         mantém e a falha de uma ação vira toast (ds/ui.js) ou a mensagem no modal. */
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
        dados
          .carregar()
          .then(function () {
            if (dados.estado === "carregando") dados.estado = "conteudo";
          })
          .catch(function () {
            /* aoFalhar já escolheu o estado a partir do ajax:error */
          });
      }

      document.addEventListener("ajax:error", aoFalhar);
      raiz.addEventListener("click", function (evento) {
        if (evento.target.closest("[data-registro-recarregar]")) carregar();
      });
      carregar();
    },

    /* "Salvar e avaliar" atualiza a tela com um marcador oculto; este abre a avaliação do risco
       que acabou de ser salvo, no lugar do modal do formulário. */
    abrirAvaliacao: function (marcador) {
      window.setTimeout(function () {
        window.TN.modal({
          title: marcador.dataset.registroAvaliarTitulo,
          subtitle: marcador.dataset.registroAvaliarSubtitulo || "",
          width: LARGURA_DA_AVALIACAO,
          body: corpoCarregando(ALVO_DO_MODAL, marcador.dataset.registroAvaliar)
        });
      }, 50);
    }
  };
})();
