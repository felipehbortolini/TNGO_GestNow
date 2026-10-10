/* ============================================================
   analises_risco.js — Comportamento da tela Análises de risco (APR/HAZOP)
   (hse/analises_risco)

   Estudos APR/JSA e HAZOP, com as recomendações que viram ações na Central.

   Registra um único objeto em TN.paginas["hse/analises_risco"]. A view o aciona
   por x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela
   (carregando, conteudo, erro ou sem-permissao) mora no x-data da view; o
   vazio de origem vem do servidor, dentro do fragmento.

   O servidor desenha tudo (api/src/templates/hse/): indicadores, filtros,
   tabela e páginas são links ou um formulário GET com x-target. Aqui moram os
   modais que o Design System abre por JavaScript (a ficha, o novo estudo e o
   fechamento da recomendação), cujo corpo o servidor entrega por GET em
   #analises-risco-modal-corpo, e as linhas repetíveis de recomendação do
   formulário (acrescentar e remover, renumerando os campos). Depois de uma
   gravação o fragmento traz o marcador oculto que reabre a ficha. No Portfólio
   o botão de inclusão pede o projeto antes (data-tn-incluir, ds/shell.js) e a
   tela reabre no projeto com a ação pedida (TN.escopo.acaoPendente).

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const ALVO_DO_MODAL = "analises-risco-modal-corpo";
  const LARGURA_PADRAO = 640;
  const LARGURA_DA_FICHA = 960;
  const CAMPOS_DA_LINHA = ["descricao", "responsavel", "prazo"];

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
      body: corpoCarregando(opcoes.url),
      onClose: opcoes.aoFechar
    });
  }

  function abrirDoBotao(botao, aoFechar) {
    abrirModal({
      titulo: botao.dataset.analisesRiscoModalTitulo,
      subtitulo: botao.dataset.analisesRiscoModalSubtitulo,
      url: botao.dataset.analisesRiscoModalUrl,
      largura: botao.dataset.analisesRiscoModalLargura,
      aoFechar: aoFechar
    });
  }

  function abrirFicha(codigo) {
    abrirModal({
      titulo: "Estudo " + codigo,
      subtitulo: "Recomendações e ações na Central",
      url: "/api/hse/analises-risco/" + encodeURIComponent(codigo) + "/ficha",
      largura: LARGURA_DA_FICHA
    });
  }

  function fecharModalDe(elemento) {
    const fundo = elemento.closest(".modal-backdrop");
    const fechar = fundo ? fundo.querySelector(".modal__close") : null;
    if (fechar) fechar.click();
  }

  /* As linhas de recomendação do formulário: o nome e o id de cada campo seguem o índice da
     linha (rec_descricao_1, rec_responsavel_1, rec_prazo_1), como o servidor os lê. */
  function linhasDe(formulario) {
    return formulario.querySelectorAll("[data-analises-risco-linha]");
  }

  function renumerarLinhas(formulario) {
    linhasDe(formulario).forEach(function (linha, indice) {
      const numero = indice + 1;
      const ids = {};
      linha.querySelectorAll("[data-analises-risco-campo]").forEach(function (campo) {
        const nome = campo.dataset.analisesRiscoCampo;
        if (CAMPOS_DA_LINHA.indexOf(nome) < 0) return;
        campo.name = "rec_" + nome + "_" + numero;
        campo.id = "ar-rec-" + nome + "-" + numero;
        ids[nome] = campo.id;
      });
      const rotulos = {
        descricao: linha.querySelector("[data-analises-risco-rotulo]"),
        responsavel: linha.querySelector("[data-analises-risco-rotulo-responsavel]"),
        prazo: linha.querySelector("[data-analises-risco-rotulo-prazo]")
      };
      if (rotulos.descricao) {
        rotulos.descricao.textContent = "Recomendação " + numero;
        rotulos.descricao.setAttribute("for", ids.descricao || "");
      }
      if (rotulos.responsavel) rotulos.responsavel.setAttribute("for", ids.responsavel || "");
      if (rotulos.prazo) rotulos.prazo.setAttribute("for", ids.prazo || "");
      const remover = linha.querySelector("[data-analises-risco-remover]");
      if (remover) remover.setAttribute("aria-label", "Remover a recomendação " + numero);
    });
  }

  function adicionarLinha(botao) {
    const formulario = botao.closest("form");
    if (!formulario) return;
    const modelo = formulario.querySelector("template[data-analises-risco-modelo]");
    const destino = formulario.querySelector("[data-analises-risco-linhas]");
    if (!modelo || !destino) return;
    destino.appendChild(modelo.content.cloneNode(true));
    renumerarLinhas(formulario);
  }

  function removerLinha(botao) {
    const formulario = botao.closest("form");
    const linha = botao.closest("[data-analises-risco-linha]");
    if (!formulario || !linha) return;
    if (linhasDe(formulario).length > 1) {
      linha.remove();
      renumerarLinhas(formulario);
    }
  }

  window.TN.paginas["hse/analises_risco"] = {
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

      /* A ação pedida pelo mecanismo de inclusão do Portfólio: abre o formulário já na tela. */
      function atenderAcaoPendente(acao) {
        if (acao !== "nova") return;
        carregar(null).then(function () {
          abrirModal({
            titulo: "Nova análise de risco",
            subtitulo: "Estudo APR/JSA ou HAZOP com participantes e recomendações",
            url: "/api/hse/analises-risco/nova",
            largura: 920,
            aoFechar: function () { carregar(urlAtual); }
          });
        });
      }

      /* Um só ouvinte por tela, preso à raiz, para o que vive no fragmento da lista. */
      raiz.addEventListener("click", function (evento) {
        const abrir = evento.target.closest("[data-analises-risco-modal-url]");
        if (abrir) abrirDoBotao(abrir, function () { carregar(urlAtual); });
        else if (evento.target.closest("[data-analises-risco-recarregar]")) carregar(urlAtual);
      });

      /* O modal mora fora da raiz (o Design System o anexa ao fim do <body>): os cliques de
         dentro dele (acrescentar/remover linhas e cancelar) são ouvidos no documento. */
      document.addEventListener("click", function aoClicarNoModal(evento) {
        if (!raiz.isConnected) {
          document.removeEventListener("click", aoClicarNoModal);
          return;
        }
        const alvo = evento.target.closest
          ? evento.target.closest("[data-analises-risco-adicionar], [data-analises-risco-remover], [data-analises-risco-fechar-modal]")
          : null;
        if (!alvo) return;
        if (alvo.hasAttribute("data-analises-risco-adicionar")) adicionarLinha(alvo);
        else if (alvo.hasAttribute("data-analises-risco-remover")) removerLinha(alvo);
        else fecharModalDe(alvo);
      });
      document.addEventListener("ajax:error", aoFalhar);

      const acao = window.TN.escopo ? window.TN.escopo.acaoPendente() : null;
      carregar(null).then(function () { atenderAcaoPendente(acao); });
    },

    /* Depois de uma gravação o fragmento da lista traz o marcador oculto com o número do
       estudo: este abre a ficha atualizada no lugar do modal que se fechou. */
    abrirFicha: function (marcador) {
      const codigo = marcador.getAttribute("data-analises-risco-abrir-ficha");
      window.setTimeout(function () { abrirFicha(codigo); }, 50);
    }
  };
})();
