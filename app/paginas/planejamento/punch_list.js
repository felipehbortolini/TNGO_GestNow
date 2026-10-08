/* ============================================================
   punch_list.js — Comportamento da tela Punch list (planejamento/punch_list)

   Itens de completação com verificação, evidência obrigatória e bloqueio de sistema.

   Registra um único objeto em TN.paginas["planejamento/punch_list"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela (carregando,
   vazio-origem, vazio-filtro, conteudo, erro ou sem-permissao) mora no x-data da view; a
   barra de filtros, a lista e os modais são fragmentos do servidor, e este arquivo só liga
   as pontas:

     filtros    a barra pede a lista; o modal de filtros aplica pela rota da tela e a resposta
                esvazia o modal (o JS o fecha); os KPIs clicáveis reescrevem a barra e a submetem
     modais     Novo item, editar, fechamento com verificação, cancelamento, filtros e a
                importação genérica abrem um modal cujo corpo busca o fragmento no servidor
     fluxo      Tratar e Enviar para verificação são formulários escondidos por linha; a
                resposta multi-alvo atualiza a lista
     gravação   o servidor responde o modal com a marca data-punch-salvo: o modal fecha
     abas       Lista e Painel; o Painel chega junto com a tela e é refeito quando a aba abre
                depois de uma gravação (a lista mudou)
     endereço   ?acao=novo|importar vem do mecanismo de inclusão do Portfólio (TN.escopo);
                ?busca=PL-... vem do link da ação na Central e preenche a busca;
                ?aba=painel abre a aba do painel de completação

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const RAIZ = "main.pagina--planejamento-punch_list";
  const ABA_PAINEL = "painel";
  const LARGURA_FORM = 880;
  const LARGURA_FILTROS = 760;

  let modalAberto = null;
  let ouvindo = false;
  let acaoPendente = null;
  let buscaPendente = "";
  let importando = false;
  let painelSujo = false;

  function raizDaTela() {
    return document.querySelector(RAIZ);
  }

  function estadoDaTela(estado) {
    const raiz = raizDaTela();
    if (raiz) window.Alpine.$data(raiz).estado = estado;
  }

  /* ---------- Abas ---------- */

  function trocarAba(aba) {
    const raiz = raizDaTela();
    if (!raiz) return;
    window.Alpine.$data(raiz).aba = aba;
    if (aba === ABA_PAINEL && painelSujo) carregarPainel();
  }

  function carregarPainel() {
    const host = document.getElementById("punch-painel");
    const marco = raizDaTela() && raizDaTela().querySelector("[data-punch-painel-url]");
    if (!host || !marco) return;
    painelSujo = false;
    host.insertAdjacentHTML(
      "afterbegin",
      '<div class="empty" role="status"><div class="spinner" aria-hidden="true"></div><p>Carregando...</p></div>'
    );
    host.insertAdjacentHTML(
      "beforeend",
      '<span hidden x-init="$ajax(\'' + marco.dataset.punchPainelUrl + '\', { target: \'punch-painel\' })"></span>'
    );
  }

  /* ---------- Filtros e lista ---------- */

  function refazerConteudo() {
    const formulario = document.getElementById("punch-filtro");
    if (formulario) formulario.requestSubmit();
  }

  function aoChegarOConteudo(detalhe) {
    if (detalhe && detalhe.ok) {
      const marca = document.querySelector("#punch-conteudo[data-punch-resultado]");
      estadoDaTela(marca ? marca.dataset.punchResultado : "conteudo");
      if (buscaPendente) {
        const campo = document.getElementById("punch-busca");
        const termo = buscaPendente;
        buscaPendente = "";
        if (campo) {
          campo.value = termo;
          refazerConteudo();
        }
      }
      return;
    }
    const status = detalhe ? detalhe.status : 0;
    if (status === 403) estadoDaTela("sem-permissao");
    else if (!status || status >= 500) estadoDaTela("erro");
  }

  /* ---------- Modais ---------- */

  function fecharModal() {
    if (modalAberto) modalAberto.close();
    modalAberto = null;
  }

  function abrirModal(opcoes) {
    fecharModal();
    modalAberto = window.TN.modal({
      title: opcoes.titulo,
      subtitle: opcoes.subtitulo,
      width: opcoes.largura,
      onClose: function () {
        modalAberto = null;
        if (importando) {
          importando = false;
          refazerConteudo();
        }
      },
      body: '<div id="punch-modal" data-endereco="' + window.TN.esc(opcoes.endereco) + '"' +
        " x-init=\"$ajax($el.dataset.endereco, { target: 'punch-modal' })\">" +
        '<div class="spinner" role="status" aria-label="Carregando"></div></div>'
    });
  }

  function modal(botao, titulo, subtitulo, largura) {
    abrirModal({
      titulo: titulo,
      subtitulo: subtitulo,
      largura: largura,
      endereco: botao.dataset.punchUrl
    });
  }

  function novo(botao) {
    modal(botao, "Novo item da Punch list", "A numeração segue o padrão do projeto e a ação entra na Central", LARGURA_FORM);
  }

  function editar(botao) {
    modal(botao, "Editar " + botao.dataset.punchCodigo, botao.dataset.punchTitulo, LARGURA_FORM);
  }

  function verificar(botao) {
    modal(botao, "Fechamento com verificação", botao.dataset.punchCodigo + " · " + botao.dataset.punchTitulo, LARGURA_FORM);
  }

  function cancelar(botao) {
    modal(botao, "Cancelar " + botao.dataset.punchCodigo, botao.dataset.punchTitulo || "O cancelamento exige justificativa", LARGURA_FORM);
  }

  function filtros(botao) {
    modal(botao, "Filtros da Punch list", "Situação, categoria, sistema, disciplina e empresa", LARGURA_FILTROS);
  }

  function importar(botao) {
    importando = true;
    modal(botao, "Importar itens da Punch list", "Walkdowns e listas de comissionamento; nada é gravado antes da confirmação", LARGURA_FORM);
  }

  function submeterFormulario(botao) {
    const formulario = document.getElementById(botao.dataset.punchForm);
    if (formulario) formulario.requestSubmit();
  }

  /* ---------- KPIs clicáveis ---------- */

  function filtrarPeloKpi(botao) {
    const formulario = document.getElementById("punch-filtro");
    if (!formulario) return;
    const escolha = botao.dataset.punchKpi;
    const situacao = formulario.elements.situacao;
    const categoria = formulario.elements.categoria;
    const vencidos = formulario.elements.vencidos;
    if (!situacao || !categoria || !vencidos) return;
    if (escolha === "abertos") {
      situacao.value = "abertos";
      categoria.value = "";
      vencidos.value = "";
    } else if (escolha === "A") {
      situacao.value = "abertos";
      categoria.value = "A";
      vencidos.value = "";
    } else if (escolha === "verificacao") {
      situacao.value = "Aguardando verificação";
      categoria.value = "";
      vencidos.value = "";
    } else if (escolha === "vencidos") {
      vencidos.value = vencidos.value === "1" ? "" : "1";
    } else if (escolha === "fechados") {
      situacao.value = "Fechado";
      categoria.value = "";
      vencidos.value = "";
    }
    formulario.requestSubmit();
  }

  /* ---------- Eventos ---------- */

  const ACOES = {
    novo: novo,
    editar: editar,
    verificar: verificar,
    cancelar: cancelar,
    filtros: filtros,
    importar: importar,
    tratar: submeterFormulario,
    enviar: submeterFormulario,
    fechar: fecharModal
  };

  function aoClicar(evento) {
    if (!raizDaTela()) return;
    const aba = evento.target.closest("[data-punch-aba]");
    if (aba) {
      evento.preventDefault();
      trocarAba(aba.dataset.punchAba);
      return;
    }
    const kpi = evento.target.closest("[data-punch-kpi]");
    if (kpi) {
      evento.preventDefault();
      filtrarPeloKpi(kpi);
      return;
    }
    const botao = evento.target.closest("[data-punch-acao]");
    if (!botao) return;
    const acao = ACOES[botao.dataset.punchAcao];
    if (!acao) return;
    evento.preventDefault();
    acao(botao);
  }

  function daCarga(evento) {
    return Boolean(evento.target.hasAttribute && evento.target.hasAttribute("data-punch-carga"));
  }

  function doConteudo(evento) {
    return Boolean(evento.target.closest && evento.target.closest("#punch-filtro, #punch-conteudo"));
  }

  function doModal(evento) {
    return Boolean(evento.target.closest && evento.target.closest("#punch-modal"));
  }

  function aoResponder(evento) {
    if (!raizDaTela()) return;
    if (daCarga(evento) || doConteudo(evento)) aoChegarOConteudo(evento.detail);
    if (doModal(evento) || doConteudo(evento)) painelSujo = true;
    aoGravar();
    abrirAcaoPendente();
  }

  function aoGravar() {
    const salvo = document.querySelector("#punch-modal [data-punch-salvo]");
    if (salvo) {
      fecharModal();
      return;
    }
    const corpo = document.querySelector("#punch-modal");
    if (modalAberto && corpo && corpo.childElementCount === 0) fecharModal();
  }

  function abrirAcaoPendente() {
    if (!acaoPendente) return;
    const botao = document.querySelector('[data-tn-incluir="' + acaoPendente + '"]');
    if (!botao) return;
    acaoPendente = null;
    botao.click();
  }

  function ouvir() {
    if (ouvindo) return;
    ouvindo = true;
    document.addEventListener("click", aoClicar);
    document.addEventListener("ajax:sent", aoResponder);
  }

  window.TN.paginas["planejamento/punch_list"] = {
    iniciar: function (raiz) {
      const dados = window.Alpine.$data(raiz);
      const consulta = new URLSearchParams(window.location.search);
      dados.estado = "carregando";
      buscaPendente = consulta.get("busca") || "";
      acaoPendente = window.TN.escopo.acaoPendente();
      ouvir();
      if (consulta.get("aba") === ABA_PAINEL) dados.aba = ABA_PAINEL;
    }
  };
})();
