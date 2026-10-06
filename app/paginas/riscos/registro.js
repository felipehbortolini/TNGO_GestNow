/* ============================================================
   registro.js — Comportamento da tela Registro de riscos (riscos/registro)

   Ameaças e oportunidades com avaliação, filtros e próximas revisões.

   Registra um único objeto em TN.paginas["riscos/registro"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela
   (carregando, vazio-origem, vazio-filtro, erro, sem-permissao ou pronto) mora no
   x-data da view; o conteúdo e os formulários são fragmentos do servidor, e este
   arquivo só liga as pontas:

     conteúdo   a resposta traz a marca data-estado (vazio-origem ou vazio-filtro);
                sem marca a tela está pronta; 403 vira sem-permissao e falha vira erro
     modal      [data-registro-modal-url] abre o formulário do servidor no modal; o 422
                volta no próprio corpo do modal e o sucesso fecha o modal
     avaliação  "Salvar e avaliar" devolve a tela com [data-registro-avaliar], que abre
                a avaliação do risco salvo
     categoria  "Nova categoria" abre o cadastro rápido sobre o formulário do risco
     filtros    o filtro completo mora no <template> do fragmento e abre no modal
     endereço   ?acao=nova vem do mecanismo de inclusão do Portfólio (TN.escopo)

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const CHAVE = "riscos/registro";
  const RAIZ = "main.pagina--riscos-registro";
  const CORPO = "registro-modal-corpo";
  let modalAberto = null;
  let modalCategoria = null;
  let ouvindo = false;

  function raizDaTela() {
    return document.querySelector(RAIZ);
  }

  function estadoDaTela(estado) {
    const raiz = raizDaTela();
    if (raiz) window.Alpine.$data(raiz).estado = estado;
  }

  function fecharModal() {
    if (modalCategoria) modalCategoria.close();
    modalCategoria = null;
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
      body: '<div id="' + CORPO + '" data-endereco="' + window.TN.esc(opcoes.endereco) + '"' +
        " x-init=\"$ajax($el.dataset.endereco, { target: '" + CORPO + "' })\">" +
        '<div class="spinner" role="status" aria-label="Carregando"></div></div>'
    });
  }

  function abrirFiltros() {
    const modelo = document.querySelector("[data-registro-filtros-modelo]");
    if (!modelo) return;
    fecharModal();
    modalAberto = window.TN.modal({
      title: "Filtros do registro",
      subtitle: "Combine natureza, categoria, situação, estratégia, dono, revisão e severidade",
      width: 760,
      onClose: function () { modalAberto = null; },
      body: '<div id="' + CORPO + '">' + modelo.innerHTML + "</div>"
    });
  }

  function abrirCategoria() {
    if (modalCategoria) modalCategoria.close();
    modalCategoria = window.TN.modal({
      title: "Nova categoria",
      subtitle: "Cadastro rápido na RBS",
      width: 480,
      onClose: function () { modalCategoria = null; },
      body: '<div id="risco-categoria-modal" data-endereco="/api/riscos/categorias/nova"' +
        " x-init=\"$ajax($el.dataset.endereco, { target: 'risco-categoria-modal' })\">" +
        '<div class="spinner" role="status" aria-label="Carregando"></div></div>'
    });
  }

  function aoChegarOConteudo(detalhe) {
    if (detalhe && detalhe.ok) {
      const marca = document.querySelector("#registro-conteudo [data-estado]");
      estadoDaTela(marca ? marca.dataset.estado : "pronto");
      return;
    }
    const status = detalhe ? detalhe.status : 0;
    if (status === 403) estadoDaTela("sem-permissao");
    else if (!status || status >= 500) estadoDaTela("erro");
  }

  function aoClicar(evento) {
    if (!raizDaTela() && !modalAberto) return;
    const alvo = evento.target.closest("[data-registro-modal-url], [data-registro-filtros], [data-registro-categoria-nova], [data-registro-fechar-modal]");
    if (!alvo) return;
    evento.preventDefault();
    if (alvo.hasAttribute("data-registro-filtros")) abrirFiltros();
    else if (alvo.hasAttribute("data-registro-categoria-nova")) abrirCategoria();
    else if (alvo.hasAttribute("data-registro-fechar-modal")) fecharModal();
    else {
      abrirModal({
        titulo: alvo.dataset.registroModalTitulo,
        subtitulo: alvo.dataset.registroModalSubtitulo,
        endereco: alvo.dataset.registroModalUrl
      });
    }
  }

  function aoEnviar(evento) {
    if (!raizDaTela() || !(evento.target instanceof Element)) return;
    if (evento.target.closest("#registro-conteudo")) aoChegarOConteudo(evento.detail);
  }

  function ouvir() {
    if (ouvindo) return;
    ouvindo = true;
    document.addEventListener("click", aoClicar);
    document.addEventListener("ajax:sent", aoEnviar);
  }

  /* Fecha o modal do formulário que acabou de ser enviado, se ele ainda estiver na página
     (a avaliação aberta depois do salvamento já trocou o modal). */
  function fecharDoFormulario(formulario) {
    if (!formulario || !formulario.isConnected) return;
    if (formulario.closest("#risco-categoria-modal")) {
      if (modalCategoria) modalCategoria.close();
      modalCategoria = null;
      return;
    }
    fecharModal();
  }

  window.TN.paginas[CHAVE] = {
    fecharDoFormulario: fecharDoFormulario,
    abrirAvaliacao: function (marca) {
      abrirModal({
        titulo: marca.dataset.registroAvaliarTitulo,
        subtitulo: "Probabilidade, impacto e a prévia do score",
        endereco: marca.dataset.registroAvaliar,
        largura: 820
      });
    },
    iniciar: function (raiz) {
      window.Alpine.$data(raiz).estado = "carregando";
      ouvir();
      if (window.TN.escopo.acaoPendente() === "nova") {
        abrirModal({
          titulo: "Novo risco",
          subtitulo: "Causa, evento e consequência",
          endereco: "/api/riscos/novo" + window.location.search
        });
      }
    }
  };
})();
