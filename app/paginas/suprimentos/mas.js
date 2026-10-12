/* ============================================================
   mas.js — Comportamento da tela Mapa de Suprimentos (MAS) (suprimentos/mas)

   Os doze marcos de aquisição, fabricação e entrega de cada pacote (ISSUE-062).

   Registra um único objeto em TN.paginas["suprimentos/mas"]. A view o aciona por x-init com
   iniciar(raiz), e raiz é o <main> da tela. O estado da tela (carregando, conteudo, erro ou
   sem-permissao) mora no x-data da view; os estados vazio de origem e vazio por filtro vêm do
   servidor, dentro do fragmento. O servidor desenha tudo
   (api/src/templates/suprimentos/mas.html): KPIs, segmentos, filtros e a tabela são links ou um
   formulário GET com x-target. Aqui mora o detalhe do pacote: a célula é um botão com o endereço
   da ficha, e o corpo do modal o servidor entrega por GET no alvo do modal (TN.modal).

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const ALVO_DO_MODAL = "mas-modal-corpo";
  const LARGURA_DO_DETALHE = 1080;

  let modalAberto = null;
  let ouvindo = false;

  function raizDaTela() {
    return document.querySelector("main.pagina--suprimentos-mas");
  }

  function estadoDaTela(estado) {
    const raiz = raizDaTela();
    if (raiz) window.Alpine.$data(raiz).estado = estado;
  }

  function fecharModal() {
    if (modalAberto) modalAberto.close();
    modalAberto = null;
  }

  /* O corpo do modal pede o fragmento ao servidor assim que o Alpine o inicializa; o endereço
     vai por data-url para nunca ser interpolado dentro de uma expressão. */
  function corpoCarregando(endereco) {
    return (
      '<div id="' + ALVO_DO_MODAL + '" data-url="' + window.TN.esc(endereco) + '"' +
      " x-init=\"$ajax($el.dataset.url, { target: '" + ALVO_DO_MODAL + "' })\">" +
      '<div class="spinner" role="status" aria-label="' + window.TN.t("suprimentos", "Carregando") + '"></div></div>'
    );
  }

  function abrirDetalhe(botao) {
    fecharModal();
    modalAberto = window.TN.modal({
      title: botao.dataset.masPacoteTitulo,
      subtitle: botao.dataset.masPacoteSubtitulo,
      width: LARGURA_DO_DETALHE,
      onClose: function () {
        modalAberto = null;
      },
      body: corpoCarregando(botao.dataset.masPacoteUrl)
    });
  }

  function aoClicar(evento) {
    if (!raizDaTela()) return;
    const celula = evento.target.closest ? evento.target.closest("[data-mas-pacote-url]") : null;
    if (!celula) return;
    evento.preventDefault();
    abrirDetalhe(celula);
  }

  function aoFalhar(evento) {
    if (!raizDaTela()) return;
    if (evento.detail && evento.detail.status === 403) estadoDaTela("sem-permissao");
    else estadoDaTela("erro");
  }

  function ouvir() {
    if (ouvindo) return;
    ouvindo = true;
    document.addEventListener("click", aoClicar);
  }

  window.TN.paginas["suprimentos/mas"] = {
    iniciar: function (raiz) {
      const dados = window.Alpine.$data(raiz);
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
          })
          .catch(function () {
            /* aoErro já escolheu o estado a partir do ajax:error */
          });
      }

      document.addEventListener("ajax:error", aoErro);
      raiz.addEventListener("click", function (evento) {
        if (evento.target.closest("[data-mas-recarregar]")) carregar();
      });
      carregar();
    }
  };
})();
