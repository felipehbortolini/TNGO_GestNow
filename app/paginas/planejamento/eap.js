/* ============================================================
   eap.js — Comportamento da tela EAP (planejamento/eap)

   Árvore de áreas, subáreas e pacotes, com dicionário, avanço pelo critério de
   medição e importação do avanço.

   Registra um único objeto em TN.paginas["planejamento/eap"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela
   (carregando, conteudo, vazio-origem, vazio-filtro, erro ou sem-permissao) mora no
   x-data da view e vem do marcador data-situacao que o servidor põe no conteúdo;
   403 vira sem-permissao e qualquer outra falha da primeira carga vira erro. O 422
   por campo, o 403 do estorno e o 409 da gravação não trocam o estado: a resposta
   multi-alvo já devolve o conteúdo atualizado e o formulário com as mensagens.

   Também cuida de recolher e expandir a árvore (os totais já vêm somados do
   servidor, aqui só se esconde linha). O dicionário e o avanço abrem pelo próprio
   link do fragmento (x-target eap-formulario). O botão Importar avanço só aparece
   no projeto editável, pelo marcador data-pode-editar, e abre o formulário no modal
   do Design System; a conferência e a confirmação atualizam o conteúdo no lugar.

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const ESTADOS_DE_RESULTADO = ["conteudo", "vazio-origem"];
  const ROTA_IMPORTACAO = "/api/planejamento/eap/importar/formulario";
  const ALVO_DO_MODAL = "eap-importacao-modal";
  const LARGURA_DO_MODAL = 820;

  let modalImportacao = null;

  function dadosDaTela(raiz) {
    return window.Alpine.$data(raiz);
  }

  function definirEstado(raiz, estado) {
    dadosDaTela(raiz).estado = estado;
  }

  function filhas(tabela, codigo) {
    const linhas = Array.prototype.slice.call(tabela.querySelectorAll("tr[data-codigo]"));
    return linhas.filter(function (linha) {
      const c = linha.getAttribute("data-codigo");
      if (c === codigo) return false;
      return codigo === "0" || c.indexOf(codigo + ".") === 0;
    });
  }

  function alternar(botao) {
    const tabela = botao.closest("table");
    const codigo = botao.getAttribute("data-alternar");
    const recolher = botao.getAttribute("aria-expanded") === "true";
    botao.setAttribute("aria-expanded", recolher ? "false" : "true");
    const rotulo = (recolher ? "Expandir " : "Recolher ") + codigo;
    botao.setAttribute("aria-label", rotulo);
    botao.setAttribute("title", rotulo);
    filhas(tabela, codigo).forEach(function (linha) {
      linha.hidden = recolher;
      const proprio = linha.querySelector("[data-alternar]");
      if (proprio) {
        proprio.setAttribute("aria-expanded", "true");
      }
    });
  }

  function mostrarImportacao(raiz, marcador) {
    const botao = raiz.querySelector("[data-eap-importar]");
    if (!botao) return;
    const editavel = marcador.getAttribute("data-pode-editar") === "sim";
    botao.hidden = !(editavel && marcador.getAttribute("data-situacao") === "conteudo");
  }

  function fecharModal() {
    if (modalImportacao) modalImportacao.close();
    modalImportacao = null;
  }

  function abrirImportacao() {
    fecharModal();
    modalImportacao = window.TN.modal({
      title: "Importar avanço",
      subtitle: "Boletim de medição física: avanço acumulado por pacote de trabalho",
      width: LARGURA_DO_MODAL,
      onClose: function () {
        modalImportacao = null;
      },
      body:
        '<div id="' + ALVO_DO_MODAL + '" x-init="$ajax(\'' + ROTA_IMPORTACAO +
        "', { target: '" + ALVO_DO_MODAL + "' })\">" +
        '<div class="spinner" role="status" aria-label="Carregando a importação"></div></div>'
    });
  }

  function aoResponder(raiz) {
    const marcador = raiz.querySelector("[data-situacao]");
    if (!marcador) return;
    const situacao = marcador.getAttribute("data-situacao");
    definirEstado(raiz, ESTADOS_DE_RESULTADO.indexOf(situacao) >= 0 ? situacao : "erro");
    mostrarImportacao(raiz, marcador);
  }

  function aoFalhar(raiz, evento) {
    if (dadosDaTela(raiz).estado !== "carregando") return;
    const status = evento.detail && evento.detail.status;
    definirEstado(raiz, status === 403 ? "sem-permissao" : "erro");
  }

  function aoClicar(raiz, evento) {
    const botao = evento.target.closest("[data-alternar]");
    if (botao && raiz.contains(botao)) {
      alternar(botao);
      return;
    }
    if (evento.target.closest("[data-eap-importar]")) abrirImportacao();
  }

  window.TN.paginas["planejamento/eap"] = {
    iniciar: function (raiz) {
      definirEstado(raiz, "carregando");

      raiz.addEventListener("ajax:success", function () {
        window.setTimeout(function () {
          aoResponder(raiz);
        }, 0);
      });

      raiz.addEventListener("ajax:error", function (evento) {
        aoFalhar(raiz, evento);
      });

      raiz.addEventListener("click", function (evento) {
        aoClicar(raiz, evento);
      });
    }
  };
})();
