/* ============================================================
   processos.js — Comportamento da tela Processos de compra (suprimentos/processos)

   Da requisição ao pedido ou contrato: RFx, equalização, ranking, recomendação, aprovação por
   alçada e emissão (ISSUE-059/060).

   Registra um único objeto em TN.paginas["suprimentos/processos"]. A view o aciona por x-init
   com iniciar(raiz), e raiz é o <main> da tela. O estado da tela (carregando, conteudo, erro ou
   sem-permissao) mora no x-data da view; os estados vazio de origem e vazio por filtro vêm do
   servidor, dentro do fragmento. O servidor desenha tudo
   (api/src/templates/suprimentos/processos.html): KPIs, busca, filtro, a régua de etapas
   (biblioteca de gráficos, visual Etapas) e a ficha do processo selecionado. O clique numa linha
   da régua é um $ajax do próprio fragmento, que carrega a ficha no alvo processo-ficha.

   Aqui moram os modais que o Design System abre por JavaScript — Nova requisição e as ações do
   fluxo (RFx, proposta, encerramento, equalizações, negociação, recomendação, devolução,
   aprovação e emissão) —, cujo corpo o servidor entrega por GET no alvo do modal, a conta de
   prévia do ranking comercial (o servidor revalida) e a ação pendente do mecanismo de inclusão do
   Portfólio (?acao=requisicao, TN.escopo).

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const ALVO_DO_MODAL = "processo-modal-corpo";
  const LARGURA_DO_FORM = 880;

  let modalAberto = null;
  let acaoPendente = null;
  let ouvindo = false;

  function raizDaTela() {
    return document.querySelector("main.pagina--suprimentos-processos");
  }

  function estadoDaTela(estado) {
    const raiz = raizDaTela();
    if (raiz) window.Alpine.$data(raiz).estado = estado;
  }

  /* O corpo do modal pede o fragmento ao servidor assim que o Alpine o inicializa; o endereço
     vai por data-url para nunca ser interpolado dentro de uma expressão. */
  function corpoCarregando(endereco) {
    return (
      '<div id="' + ALVO_DO_MODAL + '" data-url="' + window.TN.esc(endereco) + '"' +
      " x-init=\"$ajax($el.dataset.url, { target: '" + ALVO_DO_MODAL + "' })\">" +
      '<div class="spinner" role="status" aria-label="Carregando"></div></div>'
    );
  }

  function fecharModal() {
    if (modalAberto) modalAberto.close();
    modalAberto = null;
  }

  function abrirModal(titulo, subtitulo, endereco) {
    fecharModal();
    modalAberto = window.TN.modal({
      title: titulo,
      subtitle: subtitulo,
      width: LARGURA_DO_FORM,
      onClose: function () {
        modalAberto = null;
      },
      body: corpoCarregando(endereco)
    });
  }

  function abrirAcaoDoProcesso(botao) {
    abrirModal(
      botao.dataset.processoModalTitulo || "Ação do processo",
      botao.dataset.processoModalSubtitulo || "",
      botao.dataset.processoModalUrl
    );
  }

  function abrirRequisicao(botao) {
    abrirModal("Nova requisição", "Pacotes do plano de compras ainda sem requisição", botao.dataset.processoUrl);
  }

  function abrirAcaoPendente() {
    if (!acaoPendente) return;
    const raiz = raizDaTela();
    const botao = raiz && raiz.querySelector('[data-tn-incluir="' + acaoPendente + '"]');
    if (!botao) return;
    acaoPendente = null;
    botao.click();
  }

  /* ---------- A prévia do ranking comercial (o servidor revalida) ---------- */

  function moeda(centavos) {
    return (Number(centavos || 0) / 100).toLocaleString("pt-BR", {
      style: "currency",
      currency: "BRL"
    });
  }

  function numero(valor, casas) {
    if (valor === null || valor === undefined) return "·";
    return Number(valor).toLocaleString("pt-BR", {
      minimumFractionDigits: casas,
      maximumFractionDigits: casas
    });
  }

  /* O objeto do x-data do formulário comercial: lê os pesos e as propostas aprovadas dos
     data-* e calcula a mesma nota do servidor (menor preço aprovado ÷ preço x 100; final
     ponderada pelos pesos). */
  function previaComercial() {
    return {
      pt: 0,
      pc: 0,
      propostas: [],
      carregar: function (elemento) {
        this.pt = Number(elemento.dataset.pesoTecnico || 0);
        this.pc = Number(elemento.dataset.pesoComercial || 0);
        this.propostas = JSON.parse(elemento.dataset.propostas || "[]");
      },
      linhas: function () {
        const pt = Number(this.pt);
        const pc = Number(this.pc);
        if (pt + pc !== 100) return [];
        const validas = this.propostas.filter(function (proposta) {
          return proposta.notaTecnica !== null && proposta.notaTecnica !== undefined;
        });
        if (!validas.length) return [];
        const menor = Math.min.apply(
          null,
          validas.map(function (proposta) {
            return proposta.valor;
          })
        );
        return validas
          .map(function (proposta) {
            const comercial =
              menor > 0 && proposta.valor > 0
                ? Math.round((menor / proposta.valor) * 1000) / 10
                : null;
            const final =
              comercial === null
                ? null
                : Math.round(
                    ((proposta.notaTecnica * pt + comercial * pc) / (pt + pc)) * 10
                  ) / 10;
            return {
              fornecedor: proposta.fornecedor,
              valor: proposta.valor,
              tecnica: proposta.notaTecnica,
              comercial: comercial,
              final: final
            };
          })
          .sort(function (a, b) {
            return (b.final || 0) - (a.final || 0) || a.valor - b.valor;
          });
      },
      moeda: moeda,
      numero: numero
    };
  }

  /* ---------- Eventos ---------- */

  function aoClicar(evento) {
    if (!raizDaTela()) return;
    const abrir = evento.target.closest ? evento.target.closest("[data-processo-modal-url]") : null;
    if (abrir) {
      evento.preventDefault();
      abrirAcaoDoProcesso(abrir);
      return;
    }
    const fechar = evento.target.closest ? evento.target.closest("[data-processo-fechar-modal]") : null;
    if (fechar) {
      evento.preventDefault();
      fecharModal();
      return;
    }
    const acao = evento.target.closest ? evento.target.closest("[data-processo-url]") : null;
    if (acao) {
      evento.preventDefault();
      abrirRequisicao(acao);
    }
  }

  function aoFalhar(evento) {
    const raiz = raizDaTela();
    if (!raiz) return;
    if (evento.detail && evento.detail.status === 403) estadoDaTela("sem-permissao");
    else estadoDaTela("erro");
  }

  function ouvir() {
    if (ouvindo) return;
    ouvindo = true;
    document.addEventListener("click", aoClicar);
  }

  window.TN.paginas["suprimentos/processos"] = {
    previaComercial: previaComercial,
    iniciar: function (raiz) {
      const dados = window.Alpine.$data(raiz);
      acaoPendente = window.TN.escopo.acaoPendente();
      ouvir();

      /* Só a primeira carga decide entre erro e sem permissão; depois de aberta, a tela se
         mantém e a falha de uma ação vira toast (ds/ui.js) ou a mensagem no modal. */
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
            abrirAcaoPendente();
          })
          .catch(function () {
            /* aoErro já escolheu o estado a partir do ajax:error */
          });
      }

      document.addEventListener("ajax:error", aoErro);
      raiz.addEventListener("click", function (evento) {
        if (evento.target.closest("[data-processos-recarregar]")) carregar();
      });
      carregar();
    }
  };
})();
