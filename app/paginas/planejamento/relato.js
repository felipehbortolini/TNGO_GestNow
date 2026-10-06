/* ============================================================
   relato.js — Comportamento da tela Relato do período (planejamento/relato)

   Atividades do período e do próximo período, com os pontos de atenção.

   Registra um único objeto em TN.paginas["planejamento/relato"]. A view o aciona por
   x-init com iniciar(raiz), e raiz é o <main> da tela. O estado da tela (carregando,
   vazio-origem, vazio-filtro, erro, sem-permissao ou pronto) mora no x-data da view; o painel
   (indicadores e tabela) e os modais são fragmentos do servidor, e este arquivo só liga as
   pontas:

     painel     a resposta do painel traz a marca data-situacao; é ela que decide o estado
     modais     Novo, Editar e Ver abrem um modal cujo corpo busca o fragmento no servidor
     gravação   o servidor responde um corpo com a marca data-relato-salvo: o modal fecha e o
                painel é refeito com o filtro de agora
     exclusão   confirmação do Design System; depois o formulário escondido pede ao servidor
     exportação os botões Excel e PDF levam o filtro de agora (o que a lista mostra vai)
     endereço   ?tipo= filtra; ?tipo=&periodo=&abrir=1 abre o relato do período, ou o cadastro
                dele, como o modal do relatório gerencial pede; ?acao=nova vem do mecanismo
                de inclusão do Portfólio (TN.escopo)

   Carrega pelo shell (app/index.html), nunca pela view. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const RAIZ = "main.pagina--planejamento-relato";
  const BASE = "/api/planejamento/relatos";
  const TIPOS = ["Semanal", "Mensal"];
  const LARGURA_FORMULARIO = 760;
  const LARGURA_RELATO = 820;

  let modalAberto = null;
  let ouvindo = false;

  function raizDaTela() {
    return document.querySelector(RAIZ);
  }

  function estadoDaTela(estado) {
    const raiz = raizDaTela();
    if (raiz) window.Alpine.$data(raiz).estado = estado;
  }

  function parametro(nome) {
    return new URLSearchParams(window.location.search).get(nome) || "";
  }

  /* ---------- Painel ---------- */

  function filtroDeAgora() {
    const formulario = document.getElementById("relato-filtro");
    if (!formulario) return new URLSearchParams();
    const consulta = new URLSearchParams();
    const tipo = formulario.elements.tipo.value;
    const busca = formulario.elements.busca.value.trim();
    if (tipo) consulta.set("tipo", tipo);
    if (busca) consulta.set("busca", busca);
    return consulta;
  }

  function atualizarExportacao() {
    const texto = filtroDeAgora().toString();
    const sufixo = texto ? "?" + texto : "";
    const excel = document.getElementById("relato-excel");
    const pdf = document.getElementById("relato-pdf");
    if (excel) excel.dataset.tnExcel = BASE + "/excel" + sufixo;
    if (pdf) pdf.dataset.tnPdf = BASE + "/imprimivel" + sufixo;
  }

  function refazerPainel() {
    const formulario = document.getElementById("relato-filtro");
    if (formulario) formulario.requestSubmit();
  }

  /* A resposta do painel diz em que estado a tela fica; falha vira erro ou acesso negado. */
  function aoChegarOPainel(detalhe) {
    if (detalhe && detalhe.ok) {
      const marca = document.querySelector("#relato-painel [data-situacao]");
      estadoDaTela(marca ? marca.dataset.situacao : "pronto");
      atualizarExportacao();
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
      subtitle: opcoes.subtitulo || "",
      width: opcoes.largura,
      onClose: function () { modalAberto = null; },
      body: '<div id="relato-modal" data-endereco="' + window.TN.esc(opcoes.endereco) + '"' +
        " x-init=\"$ajax($el.dataset.endereco, { target: 'relato-modal' })\">" +
        '<div class="spinner" role="status" aria-label="Carregando"></div></div>'
    });
  }

  function consulta(valores) {
    return new URLSearchParams(valores).toString();
  }

  function ver(dados) {
    abrirModal({
      titulo: dados.titulo || "Relato do período",
      subtitulo: dados.subtitulo,
      largura: LARGURA_RELATO,
      endereco: BASE + "/ver?" + consulta({ id: dados.id })
    });
  }

  function editar(dados) {
    abrirModal({
      titulo: dados.titulo || "Editar relato",
      subtitulo: dados.subtitulo,
      largura: LARGURA_FORMULARIO,
      endereco: BASE + "/formulario?" + consulta({ id: dados.id })
    });
  }

  function novo(padrao) {
    const valores = {};
    const tipo = padrao && padrao.tipo ? padrao.tipo : filtroDeAgora().get("tipo");
    if (TIPOS.indexOf(tipo) >= 0) valores.tipo = tipo;
    if (padrao && padrao.periodo) valores.periodo = padrao.periodo;
    abrirModal({
      titulo: "Novo relato do período",
      subtitulo: "Um registro por tipo e período: o semanal e o mensal são distintos",
      largura: LARGURA_FORMULARIO,
      endereco: BASE + "/formulario?" + consulta(valores)
    });
  }

  function abrirDoEndereco(tipo, periodo) {
    abrirModal({
      titulo: "Relato do período",
      largura: LARGURA_RELATO,
      endereco: BASE + "/abrir?" + consulta({ tipo: tipo, periodo: periodo })
    });
  }

  /* ---------- Gravação e exclusão ---------- */

  function aoGravar() {
    if (!document.querySelector("#relato-modal [data-relato-salvo]")) return;
    fecharModal();
    refazerPainel();
  }

  function excluir(dados) {
    window.TN.confirmarExclusao({
      mensagem: "Excluir o relato? O período volta a ficar pendente e sai da página 2 do Planejamento no relatório gerencial.",
      rows: [
        { label: "Relato", valor: dados.titulo },
        { label: "Projeto", valor: dados.subtitulo }
      ]
    }).then(function (confirmado) {
      if (!confirmado) return;
      const formulario = document.getElementById("relato-excluir");
      const filtro = filtroDeAgora();
      formulario.elements.id.value = dados.id;
      formulario.elements.versao.value = dados.versao;
      formulario.elements.tipo.value = filtro.get("tipo") || "";
      formulario.elements.busca.value = filtro.get("busca") || "";
      formulario.requestSubmit();
    });
  }

  /* ---------- Eventos ---------- */

  const ACOES = {
    ver: ver,
    editar: function (dados) { fecharModal(); editar(dados); },
    excluir: excluir,
    novo: function () { novo(); },
    fechar: fecharModal
  };

  function aoClicar(evento) {
    const botao = evento.target.closest("[data-relato-acao]");
    if (!botao || !raizDaTela()) return;
    const acao = ACOES[botao.dataset.relatoAcao];
    if (!acao) return;
    evento.preventDefault();
    acao({
      id: botao.dataset.relatoId,
      versao: botao.dataset.relatoVersao,
      titulo: botao.dataset.relatoTitulo,
      subtitulo: botao.dataset.relatoSubtitulo
    });
  }

  function aoEnviar(evento) {
    if (!raizDaTela() || !(evento.target instanceof Element)) return;
    if (evento.target.closest("#relato-filtro, #relato-painel, #relato-excluir")) {
      aoChegarOPainel(evento.detail);
    }
    aoGravar();
  }

  function ouvir() {
    if (ouvindo) return;
    ouvindo = true;
    document.addEventListener("click", aoClicar);
    document.addEventListener("ajax:sent", aoEnviar);
  }

  window.TN.paginas["planejamento/relato"] = {
    /* O tipo do filtro quando o endereço pede (?tipo=Mensal); vazio é "Todos". */
    tipoInicial: function () {
      const tipo = parametro("tipo");
      return TIPOS.indexOf(tipo) >= 0 ? tipo : "";
    },

    iniciar: function (raiz) {
      window.Alpine.$data(raiz).estado = "carregando";
      ouvir();
      atualizarExportacao();
      const acao = window.TN.escopo.acaoPendente();
      const tipo = parametro("tipo");
      const periodo = parametro("periodo");
      if (parametro("abrir") === "1" && tipo && periodo) abrirDoEndereco(tipo, periodo);
      else if (acao === "nova") novo();
    }
  };
})();
