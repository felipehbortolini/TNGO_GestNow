/* ============================================================
   colaboradores.js — Comportamento da tela Colaboradores (configuracoes/colaboradores)

   Quem entra no GestNow: perfil geral, vínculo, empresa e os papéis da Programação Semanal por
   projeto.

   Registra um único objeto em TN.paginas["configuracoes/colaboradores"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela (carregando, conteudo,
   erro ou sem-permissao) mora no x-data da view; o vazio de origem e o vazio por filtro vêm do
   servidor, dentro do fragmento.

   O servidor desenha tudo (api/src/templates/configuracoes/): os avisos, os KPIs por perfil, a
   barra de filtros (um formulário GET com x-target, filtrado no servidor) e a lista. Aqui moram
   o modal de novo/editar acesso — cujo corpo o servidor entrega por GET em
   #colaboradores-modal-corpo — e o editor dos papéis por projeto do formulário, que lê os
   projetos, os papéis atuais e os rótulos de data-* e posta um campo repetido "papeis" por
   linha, com valor "projeto_id:papel". O sucesso da gravação atualiza a lista atrás do modal e
   o modal fecha pelo @ajax:success do formulário; a revogação confirma por TN.confirmarExclusao
   e o servidor devolve a lista com o toast.

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const ALVO_DO_MODAL = "colaboradores-modal-corpo";
  const LARGURA_PADRAO = 820;

  /* O corpo do modal pede o fragmento ao servidor assim que o Alpine o inicializa; o endereço
     vai por data-url para nunca ser interpolado dentro de uma expressão. */
  function corpoCarregando(endereco) {
    return (
      '<div id="' + ALVO_DO_MODAL + '" data-url="' + window.TN.esc(endereco) + '"' +
      " x-init=\"$ajax($el.dataset.url, { target: '" + ALVO_DO_MODAL + "' })\">" +
      '<div class="spinner" role="status" aria-label="Carregando"></div></div>'
    );
  }

  function abrirModal(opcoes) {
    window.TN.modal({
      title: opcoes.titulo,
      subtitle: opcoes.subtitulo,
      width: Number(opcoes.largura) || LARGURA_PADRAO,
      body: corpoCarregando(opcoes.url)
    });
  }

  function abrirDoBotao(botao) {
    abrirModal({
      titulo: botao.dataset.colaboradoresModalTitulo,
      subtitulo: botao.dataset.colaboradoresModalSubtitulo,
      url: botao.dataset.colaboradoresModalUrl,
      largura: botao.dataset.colaboradoresModalLargura
    });
  }

  function fecharModalDe(elemento) {
    const fundo = elemento.closest(".modal-backdrop");
    const fechar = fundo ? fundo.querySelector(".modal__close") : null;
    if (fechar) fechar.click();
  }

  /* O editor do modal: o vínculo (para a empresa aparecer só no Fornecedor) e a lista de papéis
     por projeto. Tudo chega de data-*; os ids viram texto para o x-model do select e para o
     campo repetido que o servidor lê. */
  function editorDeAcesso() {
    return {
      vinculo: "",
      papeis: [],
      projetos: [],
      rotulos: [],
      carregar: function (elemento) {
        this.vinculo = elemento.dataset.vinculo || "";
        this.projetos = JSON.parse(elemento.dataset.projetos || "[]");
        this.rotulos = JSON.parse(elemento.dataset.rotulos || "[]");
        this.papeis = JSON.parse(elemento.dataset.papeis || "[]").map(function (linha) {
          return { projeto_id: String(linha.projeto_id), papel: linha.papel };
        });
      },
      adicionarPapel: function () {
        const primeiro = this.projetos.length ? String(this.projetos[0].id) : "";
        this.papeis.push({ projeto_id: primeiro, papel: "" });
      },
      removerPapel: function (indice) {
        this.papeis.splice(indice, 1);
      }
    };
  }

  window.TN.paginas["configuracoes/colaboradores"] = {
    editorDeAcesso: editorDeAcesso,
    iniciar: function (raiz) {
      const dados = window.Alpine.$data(raiz);
      let urlAtual = null;

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

      function carregar(url) {
        dados.estado = "carregando";
        urlAtual = url || null;
        return dados
          .carregar(url)
          .then(function () {
            if (dados.estado === "carregando") dados.estado = "conteudo";
          })
          .catch(function () {
            /* aoFalhar já escolheu o estado a partir do ajax:error */
          });
      }

      /* Um só ouvinte por tela, preso à raiz, para o que vive no fragmento. */
      raiz.addEventListener("click", function (evento) {
        const abrir = evento.target.closest("[data-colaboradores-modal-url]");
        if (abrir) abrirDoBotao(abrir);
        else if (evento.target.closest("[data-colaboradores-recarregar]")) carregar(urlAtual);
      });

      /* O modal mora fora da raiz (o Design System o anexa ao fim do <body>): o clique do
         Cancelar é ouvido no documento. */
      document.addEventListener("click", function aoClicarNoModal(evento) {
        if (!raiz.isConnected) {
          document.removeEventListener("click", aoClicarNoModal);
          return;
        }
        const alvo = evento.target.closest
          ? evento.target.closest("[data-colaboradores-fechar-modal]")
          : null;
        if (alvo) fecharModalDe(alvo);
      });
      document.addEventListener("ajax:error", aoFalhar);

      carregar(null);
    }
  };
})();
