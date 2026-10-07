/* ============================================================
   eap.js — Comportamento da tela EAP (planejamento/eap)

   Árvore de áreas, subáreas e pacotes, com dicionário, avanço, revisões,
   desdobramento e as duas importações.

   Registra um único objeto em TN.paginas["planejamento/eap"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela
   (carregando, conteudo, vazio-origem, vazio-filtro, erro ou sem-permissao) mora no
   x-data da view e vem do marcador data-situacao que o servidor põe no conteúdo;
   403 vira sem-permissao e qualquer outra falha da primeira carga vira erro. O 422
   por campo, o 403 do estorno e o 409 da gravação não trocam o estado: a resposta
   multi-alvo já devolve o conteúdo atualizado e o formulário com as mensagens.

   Também cuida de recolher e expandir a árvore (os totais já vêm somados do
   servidor, aqui só se esconde linha), de mostrar as ações pelo papel que o
   marcador declara (data-pode-editar e data-pode-gerir) e dos modais: o dicionário
   e o avanço abrem pelo próprio link no alvo eap-formulario; o pacote novo e a
   revisão guardam esse alvo fora da página e o devolvem ao fechar; a importação do
   avanço e a de pacotes abrem no alvo próprio e a conferência e a confirmação
   atualizam o conteúdo no lugar.

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const ESTADOS_DE_RESULTADO = ["conteudo", "vazio-origem"];
  const ROTA_IMPORTACAO_AVANCO = "/api/planejamento/eap/importar/formulario";
  const ROTA_IMPORTACAO_PACOTES = "/api/planejamento/eap/pacotes/importar/formulario";
  const ROTA_PACOTE = "/api/planejamento/eap/pacotes/novo";
  const ROTA_REVISAO = "/api/planejamento/eap/revisoes/nova";
  const ROTAS_DE_GRAVACAO = ["/api/planejamento/eap/pacotes", "/api/planejamento/eap/revisoes"];
  const ALVO_FORMULARIO = "eap-formulario";
  const ALVO_IMPORTACAO_AVANCO = "eap-importacao-modal";
  const ALVO_IMPORTACAO_PACOTES = "eap-pacotes-importacao-modal";
  const LARGURA_DO_MODAL = 820;
  const RAIZ = "main.pagina--planejamento-eap";

  let modalAberto = null;
  let formularioDaPagina = null;
  let ouvindo = false;

  function raizDaTela() {
    return document.querySelector(RAIZ);
  }

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

  function mostrarBotao(raiz, seletor, visivel) {
    const botao = raiz.querySelector(seletor);
    if (botao) botao.hidden = !visivel;
  }

  function mostrarAcoes(raiz, marcador) {
    const conteudo = marcador.getAttribute("data-situacao") === "conteudo";
    const editavel = marcador.getAttribute("data-pode-editar") === "sim";
    const gere = marcador.getAttribute("data-pode-gerir") === "sim";
    mostrarBotao(raiz, "[data-eap-pacote]", conteudo && editavel);
    mostrarBotao(raiz, "[data-eap-importar]", conteudo && editavel);
    mostrarBotao(raiz, "[data-eap-revisao]", conteudo && gere);
    mostrarBotao(raiz, "[data-eap-importar-pacotes]", conteudo && gere);
  }

  function fecharModal() {
    if (modalAberto) modalAberto.close();
    modalAberto = null;
  }

  function devolverFormulario() {
    if (!formularioDaPagina) return;
    const guardado = formularioDaPagina;
    formularioDaPagina = null;
    guardado.pai.insertBefore(guardado.no, guardado.proximo);
  }

  function tirarFormularioDaPagina(raiz) {
    const pagina = raiz.querySelector("#" + ALVO_FORMULARIO);
    if (!pagina) return;
    formularioDaPagina = { no: pagina, pai: pagina.parentNode, proximo: pagina.nextSibling };
    pagina.remove();
  }

  function corpoDoModal(alvo, endereco, rotulo) {
    return (
      '<div id="' + alvo + '" data-endereco="' + window.TN.esc(endereco) + '"' +
      " x-init=\"$ajax($el.dataset.endereco, { target: '" + alvo + "' })\">" +
      '<div class="spinner" role="status" aria-label="' + rotulo + '"></div></div>'
    );
  }

  function abrirFormulario(raiz, titulo, subtitulo, endereco) {
    fecharModal();
    tirarFormularioDaPagina(raiz);
    modalAberto = window.TN.modal({
      title: titulo,
      subtitle: subtitulo,
      width: LARGURA_DO_MODAL,
      onClose: function () {
        modalAberto = null;
        devolverFormulario();
      },
      body: corpoDoModal(ALVO_FORMULARIO, endereco, "Carregando o formulário")
    });
  }

  function abrirImportacao(titulo, subtitulo, endereco, alvo) {
    fecharModal();
    modalAberto = window.TN.modal({
      title: titulo,
      subtitle: subtitulo,
      width: LARGURA_DO_MODAL,
      onClose: function () {
        modalAberto = null;
      },
      body: corpoDoModal(alvo, endereco, "Carregando a importação")
    });
  }

  function aoResponder(raiz) {
    const marcador = raiz.querySelector("[data-situacao]");
    if (!marcador) return;
    const situacao = marcador.getAttribute("data-situacao");
    definirEstado(raiz, ESTADOS_DE_RESULTADO.indexOf(situacao) >= 0 ? situacao : "erro");
    mostrarAcoes(raiz, marcador);
  }

  function fechouAGravacao(evento) {
    const alvo = evento.target;
    if (!(alvo instanceof Element) || !alvo.closest(".modal-backdrop")) return false;
    return ROTAS_DE_GRAVACAO.indexOf(alvo.getAttribute("action") || "") >= 0;
  }

  function aoConcluir(raiz, evento) {
    const gravou = fechouAGravacao(evento);
    window.setTimeout(function () {
      aoResponder(raiz);
      if (gravou) fecharModal();
    }, 0);
  }

  function aoFalhar(raiz, evento) {
    if (dadosDaTela(raiz).estado !== "carregando") return;
    const status = evento.detail && evento.detail.status;
    definirEstado(raiz, status === 403 ? "sem-permissao" : "erro");
  }

  function abrirPelaAcao(raiz, evento) {
    if (evento.target.closest("[data-eap-pacote]")) {
      abrirFormulario(
        raiz,
        "Novo pacote",
        "Desdobramento de pacote de planejamento (o total não muda) ou nova revisão a partir de SM aprovada com impacto em escopo",
        ROTA_PACOTE
      );
      return true;
    }
    if (evento.target.closest("[data-eap-revisao]")) {
      abrirFormulario(
        raiz,
        "Nova revisão da EAP",
        "A partir de SM aprovada com impacto em escopo; os demais pesos são reescalados para fechar 100%",
        ROTA_REVISAO
      );
      return true;
    }
    if (evento.target.closest("[data-eap-importar]")) {
      abrirImportacao(
        "Importar avanço",
        "Boletim de medição física: avanço acumulado por pacote de trabalho",
        ROTA_IMPORTACAO_AVANCO,
        ALVO_IMPORTACAO_AVANCO
      );
      return true;
    }
    if (evento.target.closest("[data-eap-importar-pacotes]")) {
      abrirImportacao(
        "Importar pacotes da EAP",
        "Pacotes novos em subáreas existentes; a importação cria a revisão vinculada à SM aprovada",
        ROTA_IMPORTACAO_PACOTES,
        ALVO_IMPORTACAO_PACOTES
      );
      return true;
    }
    return false;
  }

  function aoClicar(raiz, evento) {
    const botao = evento.target.closest("[data-alternar]");
    if (botao && raiz.contains(botao)) {
      alternar(botao);
      return;
    }
    abrirPelaAcao(raiz, evento);
  }

  function aoSucesso(evento) {
    const raiz = raizDaTela();
    if (raiz) aoConcluir(raiz, evento);
  }

  function aoErro(evento) {
    const raiz = raizDaTela();
    if (raiz) aoFalhar(raiz, evento);
  }

  function aoCliqueNaTela(evento) {
    const raiz = raizDaTela();
    if (raiz && raiz.contains(evento.target)) aoClicar(raiz, evento);
  }

  function ouvir() {
    if (ouvindo) return;
    ouvindo = true;
    document.addEventListener("ajax:success", aoSucesso);
    document.addEventListener("ajax:error", aoErro);
    document.addEventListener("click", aoCliqueNaTela);
  }

  window.TN.paginas["planejamento/eap"] = {
    iniciar: function (raiz) {
      definirEstado(raiz, "carregando");
      ouvir();
    }
  };
})();
