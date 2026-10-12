/* ============================================================
   produtividade.js — Comportamento da tela Produtividade (planejamento/produtividade)

   Plano de quantidades da linha de base, horas efetivas do campo e indicadores por empresa.

   Registra um único objeto em TN.paginas["planejamento/produtividade"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela (carregando,
   vazio-origem, vazio-filtro, conteudo, erro ou sem-permissao) mora no x-data da view; a aba
   ativa também (Quantidades, Horas efetivas ou KPIs de performance). Os filtros, as abas de
   conteúdo e os modais são fragmentos do servidor, e este arquivo só liga as pontas:

     filtros    o formulário da aba Quantidades pede só o conteúdo; o da aba Horas pede só a
                própria aba; o `data-resultado` que chega decide o estado da tela
     modais     Novo item, ficha, revisão e apontamento (Quantidades), jornada, amostragem e
                paralisação (Horas) e o plano de ação (KPIs) abrem um modal cujo corpo busca o
                fragmento no servidor
     gravação   o servidor responde o modal com a marca data-produtividade-salvo: o modal fecha
                e, quando o conteúdo não veio na mesma resposta, os filtros são refeitos
     exclusão   confirmação do Design System; depois o formulário escondido pede ao servidor
     exportação os botões Excel e PDF moram em cada aba e levam o filtro de agora
     endereço   ?acao=item|apontar|importar|jornada|amostragem|paralisacao|plano vem do
                mecanismo de inclusão do Portfólio (TN.escopo); ?aba=kpis (e empresa e corte)
                vem do link da ação na Central e abre a aba certa

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const RAIZ = "main.pagina--planejamento-produtividade";
  const BASE = "/api/planejamento/produtividade";
  const IMPORTACAO = "/api/importacao/produtividade-itens";
  const LARGURA_FORMULARIO = 860;
  const LARGURA_FICHA = 900;
  const LARGURA_APONTAMENTO = 960;
  const LARGURA_CAMPO = 860;
  const ABAS = ["quantidades", "horas", "kpis"];

  let modalAberto = null;
  let ouvindo = false;
  let acaoPendente = null;

  function raizDaTela() {
    return document.querySelector(RAIZ);
  }

  function estadoDaTela(estado) {
    const raiz = raizDaTela();
    if (raiz) window.Alpine.$data(raiz).estado = estado;
  }

  /* ---------- Filtros e conteúdo ---------- */

  function filtroDeAgora() {
    const formulario = document.getElementById("produtividade-filtro");
    if (!formulario) return new URLSearchParams();
    const consulta = new URLSearchParams();
    ["empresa", "corte", "grupo"].forEach(function (nome) {
      const campo = formulario.elements[nome];
      if (campo && campo.value) consulta.set(nome, campo.value);
    });
    return consulta;
  }

  function sufixoDeFiltro(extra) {
    const consulta = filtroDeAgora();
    if (extra) Object.keys(extra).forEach(function (chave) { consulta.set(chave, extra[chave]); });
    const texto = consulta.toString();
    return texto ? "?" + texto : "";
  }

  function refazerConteudo() {
    const formulario = document.getElementById("produtividade-filtro");
    if (formulario) formulario.requestSubmit();
  }

  function aoChegarOConteudo(detalhe) {
    if (detalhe && detalhe.ok) {
      const marca = document.querySelector("#produtividade-conteudo[data-resultado]");
      estadoDaTela(marca ? marca.dataset.resultado : "conteudo");
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
      onClose: function () { modalAberto = null; },
      body: '<div id="produtividade-modal" data-endereco="' + window.TN.esc(opcoes.endereco) + '"' +
        " x-init=\"$ajax($el.dataset.endereco, { target: 'produtividade-modal' })\">" +
        '<div class="spinner" role="status" aria-label="' + window.TN.t("planejamento", "Carregando") + '"></div></div>'
    });
  }

  function ver(dados) {
    abrirModal({
      titulo: dados.titulo || "Item da linha de base",
      subtitulo: dados.subtitulo,
      largura: LARGURA_FICHA,
      endereco: BASE + "/itens/" + encodeURIComponent(dados.id) + sufixoDeFiltro()
    });
  }

  function editar(dados) {
    fecharModal();
    abrirModal({
      titulo: dados.titulo || "Item da linha de base",
      subtitulo: dados.subtitulo,
      largura: LARGURA_FORMULARIO,
      endereco: BASE + "/itens/" + encodeURIComponent(dados.id) + "/editar" + sufixoDeFiltro()
    });
  }

  function revisar(dados) {
    fecharModal();
    abrirModal({
      titulo: window.TN.t("planejamento", "Revisar linha de base"),
      subtitulo: dados.titulo,
      largura: LARGURA_FORMULARIO,
      endereco: BASE + "/itens/" + encodeURIComponent(dados.id) + "/revisao" + sufixoDeFiltro()
    });
  }

  function novo() {
    fecharModal();
    abrirModal({
      titulo: window.TN.t("planejamento", "Novo item da linha de base"),
      subtitulo: window.TN.t("planejamento", "Quantidade total da LB distribuída por semana conforme o cronograma"),
      largura: LARGURA_FORMULARIO,
      endereco: BASE + "/itens/novo" + sufixoDeFiltro()
    });
  }

  function apontar() {
    fecharModal();
    const consulta = filtroDeAgora();
    abrirModal({
      titulo: window.TN.t("planejamento", "Apontar semana"),
      subtitulo: window.TN.t("planejamento", "Realizado e HH apropriadas informados pela contratada, por item da LB"),
      largura: LARGURA_APONTAMENTO,
      endereco: BASE + "/apontamento" + sufixoDeFiltro({ semana: consulta.get("corte") || "" })
    });
  }

  function importar() {
    fecharModal();
    abrirModal({
      titulo: window.TN.t("planejamento", "Importar plano de quantidades"),
      subtitulo: window.TN.t("planejamento", "Itens entram em elaboração, distribuídos pelo perfil; aprove a LB depois de conferir"),
      largura: LARGURA_FORMULARIO,
      endereco: IMPORTACAO + sufixoDeFiltro()
    });
  }

  function plano(dados) {
    fecharModal();
    const parametros = new URLSearchParams();
    if (dados.empresa) parametros.set("empresa", dados.empresa);
    if (dados.corte) parametros.set("corte", dados.corte);
    const texto = parametros.toString();
    abrirModal({
      titulo: window.TN.t("planejamento", "Plano de ação de produtividade"),
      subtitulo: window.TN.t("planejamento", "Empresa com indicador fora da faixa: a ação vai para a Central (origem Produtividade)"),
      largura: LARGURA_FORMULARIO,
      endereco: BASE + "/kpis/acoes/nova" + (texto ? "?" + texto : "")
    });
  }

  const TITULOS_CAMPO = {
    jornada: ["Registrar jornada", "Fiscalização da frente de serviço: horários dos dois turnos e efetivo"],
    amostragem: ["Registrar observação", "Pessoas trabalhando, em trânsito e paradas no instante da rodada"],
    paralisacao: ["Registrar paralisação", "Efetivo (Hhora) ou máquina e equipamento (Mhora) parados na frente"]
  };

  function campo(dados) {
    fecharModal();
    const textos = TITULOS_CAMPO[dados.acao] || ["Registro de campo", ""];
    abrirModal({
      titulo: textos[0],
      subtitulo: textos[1],
      largura: LARGURA_CAMPO,
      endereco: dados.endereco
    });
  }

  /* ---------- Aprovação, exclusão e resposta ---------- */

  function aprovar(dados) {
    window.TN.confirmarExclusao({
      title: window.TN.t("planejamento", "Aprovar linha de base"),
      mensagem: "A distribuição semanal de " + dados.titulo + " fica congelada. Mudanças depois disso só por revisão com SM aprovada (08).",
      labelConfirmar: "Aprovar"
    }).then(function (confirmado) {
      if (!confirmado) return;
      const formulario = document.getElementById("prod-aprovacao");
      if (formulario) formulario.requestSubmit();
    });
  }

  function excluir(dados) {
    window.TN.confirmarExclusao({
      title: window.TN.t("planejamento", "Excluir item"),
      mensagem: "Excluir " + dados.titulo + " (em elaboração, sem apontamento)?",
      labelConfirmar: "Excluir"
    }).then(function (confirmado) {
      if (!confirmado) return;
      const formulario = document.getElementById("prod-exclusao");
      if (formulario) formulario.requestSubmit();
    });
  }

  function aoGravar() {
    const salvo = document.querySelector("#produtividade-modal [data-produtividade-salvo]");
    if (!salvo) return;
    fecharModal();
    if (!salvo.hasAttribute("data-prod-conteudo")) refazerConteudo();
  }

  /* ---------- Eventos ---------- */

  const ACOES = {
    ver: ver,
    editar: editar,
    revisar: revisar,
    novo: novo,
    apontar: apontar,
    importar: importar,
    aprovar: aprovar,
    excluir: excluir,
    plano: plano,
    fechar: fecharModal
  };

  function aoClicar(evento) {
    if (!raizDaTela()) return;
    const campoBotao = evento.target.closest("[data-horas-acao]");
    if (campoBotao) {
      evento.preventDefault();
      if (campoBotao.dataset.horasAcao === "fechar") { fecharModal(); return; }
      campo({ acao: campoBotao.dataset.horasAcao, endereco: campoBotao.dataset.horasEndereco });
      return;
    }
    const botao = evento.target.closest("[data-prod-acao]");
    if (!botao) return;
    const acao = ACOES[botao.dataset.prodAcao];
    if (!acao) return;
    evento.preventDefault();
    acao({
      id: botao.dataset.prodId,
      versao: botao.dataset.prodVersao,
      titulo: botao.dataset.prodTitulo,
      subtitulo: botao.dataset.prodSubtitulo,
      empresa: botao.dataset.prodEmpresa,
      corte: botao.dataset.prodCorte
    });
  }

  function daCarga(evento) {
    return Boolean(evento.target.hasAttribute && evento.target.hasAttribute("data-produtividade-carga"));
  }

  function doConteudo(evento) {
    return Boolean(evento.target.closest && evento.target.closest("#produtividade-filtro, #produtividade-conteudo"));
  }

  function aoResponder(evento) {
    if (!raizDaTela()) return;
    if (daCarga(evento) || doConteudo(evento)) aoChegarOConteudo(evento.detail);
    aoGravar();
    abrirAcaoPendente();
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

  window.TN.paginas["planejamento/produtividade"] = {
    iniciar: function (raiz) {
      const dados = window.Alpine.$data(raiz);
      dados.estado = "carregando";
      const escolhida = new URLSearchParams(window.location.search).get("aba");
      if (ABAS.indexOf(escolhida) >= 0) dados.aba = escolhida;
      acaoPendente = window.TN.escopo.acaoPendente();
      ouvir();
    }
  };
})();
