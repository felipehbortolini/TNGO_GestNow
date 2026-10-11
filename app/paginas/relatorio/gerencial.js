/* ============================================================
   gerencial.js — Comportamento da tela Relatório gerencial (relatorio/gerencial)

   Folhas A4 na horizontal, uma por seção, montadas pelo servidor no corte do período
   (service.report_view). Registra um único objeto em TN.paginas["relatorio/gerencial"], e a
   view o aciona por x-init com iniciar(raiz):

     endereço   ?tipo=&periodo=&secoes= carrega as folhas no alvo gerencial-conteudo (o
                x-init do contêiner chama endereco() daqui); sem tipo/periodo — ou com
                ?relatorio=1 — a tela abre o modal de emissão
     modal      o corpo do modal busca o fragmento em /api/relatorio/gerencial/emissao; trocar
                o escopo, o tipo ou o período redesenha o modal pelo servidor
     emitir     o botão Emitir lê o formulário de agora e navega para a tela com
                ?projeto=&tipo=&periodo=&secoes=; a navegação fecha o modal (ajax:sent)
     encaixe    depois de renderizar, a fonte da folha que passar da altura útil é reduzida
                até caber, mínimo de 6,4 pt (o ajustar do protótipo)
     impressão  o botão Imprimir / PDF aciona a impressão do navegador

   Carrega pelo shell (app/index.html), nunca pela view. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const RAIZ = "main.pagina--relatorio-gerencial";
  const BASE = "/api/relatorio/gerencial";
  const TAMANHO_PADRAO = 8.6;
  const TAMANHO_MINIMO = 6.4;
  const PASSO = 0.3;
  const GUARDA = 12;
  const LARGURA_MODAL = 720;

  let modalAberto = null;
  let ouvindo = false;

  function raizDaTela() {
    return document.querySelector(RAIZ);
  }

  function estadoDaTela(estado) {
    const raiz = raizDaTela();
    if (raiz) window.Alpine.$data(raiz).estado = estado;
  }

  /* O que o endereço pede: o tipo, o período, as seções e o endereço das folhas. */
  function endereco() {
    const parametros = new URLSearchParams(window.location.search);
    const tipo = parametros.get("tipo") || "";
    const periodo = parametros.get("periodo") || "";
    const secoes = parametros.get("secoes") || "";
    const consulta = new URLSearchParams();
    if (tipo) consulta.set("tipo", tipo);
    if (periodo) consulta.set("periodo", periodo);
    if (secoes) consulta.set("secoes", secoes);
    return {
      tipo: tipo,
      periodo: periodo,
      secoes: secoes,
      folhas: tipo && periodo ? BASE + "?" + consulta.toString() : ""
    };
  }

  function pedeModal() {
    return new URLSearchParams(window.location.search).get("relatorio") === "1";
  }

  /* ---------- Modal ---------- */

  function fecharModal() {
    if (modalAberto) modalAberto.close();
    modalAberto = null;
  }

  function abrirModal() {
    fecharModal();
    const rel = endereco();
    const consulta = new URLSearchParams();
    if (rel.tipo) consulta.set("tipo", rel.tipo);
    if (rel.periodo) consulta.set("periodo", rel.periodo);
    if (rel.secoes) consulta.set("secoes", rel.secoes);
    const texto = consulta.toString();
    const destino = BASE + "/emissao" + (texto ? "?" + texto : "");
    modalAberto = window.TN.modal({
      title: "Emitir relatório gerencial",
      subtitle: "O relatório sai em folhas A4 na horizontal, uma por seção.",
      width: LARGURA_MODAL,
      onClose: function () { modalAberto = null; },
      body: '<div id="relatorio-modal" data-endereco="' + window.TN.esc(destino) + '"' +
        " x-init=\"$ajax($el.dataset.endereco, { target: 'relatorio-modal' })\">" +
        '<div class="spinner" role="status" aria-label="Carregando"></div></div>'
    });
  }

  /* Emitir: leva o formulário de agora para a tela do relatório e fecha o modal. */
  function emitir() {
    const formulario = document.querySelector("#relatorio-modal form");
    if (!formulario) return;
    const dados = new FormData(formulario);
    const consulta = new URLSearchParams();
    consulta.set("projeto", dados.get("escopo") || "portfolio");
    consulta.set("tipo", dados.get("tipo") || "Semanal");
    consulta.set("periodo", dados.get("periodo") || "");
    consulta.set("secoes", dados.getAll("secoes").join(","));
    fecharModal();
    window.TN.shell.navegar("/relatorio/gerencial?" + consulta.toString(), {
      historico: "empurrar"
    });
  }

  /* ---------- Folhas ---------- */

  /* O encaixe: se o corpo passar da altura útil, reduz a fonte da folha até caber. */
  function ajustar() {
    document.querySelectorAll(".pagina--relatorio-gerencial .rel-folha").forEach(function (folha) {
      const corpo = folha.querySelector(".rel-folha__corpo");
      if (!corpo) return;
      let tamanho = TAMANHO_PADRAO;
      let guarda = 0;
      while (
        corpo.scrollHeight > corpo.clientHeight + 1 &&
        tamanho > TAMANHO_MINIMO &&
        guarda < GUARDA
      ) {
        tamanho = Math.round((tamanho - PASSO) * 10) / 10;
        folha.style.setProperty("--rel-fs", tamanho + "pt");
        guarda += 1;
      }
    });
  }

  function paginar() {
    const paginas = document.querySelectorAll(".pagina--relatorio-gerencial [data-pagina]");
    paginas.forEach(function (elemento, indice) {
      elemento.textContent = "Página " + (indice + 1) + " de " + paginas.length;
    });
  }

  /* ---------- Eventos ---------- */

  function aoClicar(evento) {
    if (!raizDaTela() || !evento.target.closest) return;
    const botao = evento.target.closest(
      "[data-relatorio-abrir], [data-relatorio-emitir], [data-relatorio-fechar], [data-relatorio-imprimir]"
    );
    if (!botao) return;
    evento.preventDefault();
    if (botao.hasAttribute("data-relatorio-abrir")) abrirModal();
    else if (botao.hasAttribute("data-relatorio-emitir")) emitir();
    else if (botao.hasAttribute("data-relatorio-fechar")) fecharModal();
    else window.print();
  }

  /* A resposta das folhas diz em que estado a tela fica; a navegação fecha o modal. */
  function aoEnviar(evento) {
    if (!raizDaTela()) return;
    const detalhe = evento.detail || {};
    const url = detalhe.url || "";
    if (modalAberto && url.indexOf("/api/nav") >= 0) {
      fecharModal();
      return;
    }
    if (url.indexOf(BASE + "?") < 0) return;
    if (detalhe.ok) {
      estadoDaTela("pronto");
      setTimeout(function () {
        ajustar();
        paginar();
      }, 0);
      return;
    }
    estadoDaTela(detalhe.status === 403 ? "sem-permissao" : "erro");
  }

  function ouvir() {
    if (ouvindo) return;
    ouvindo = true;
    document.addEventListener("click", aoClicar);
    document.addEventListener("ajax:sent", aoEnviar);
  }

  window.TN.paginas["relatorio/gerencial"] = {
    endereco: endereco,

    iniciar: function (raiz) {
      window.Alpine.$data(raiz).estado = "carregando";
      ouvir();
      const rel = endereco();
      if (!rel.folhas) estadoDaTela("vazio-origem");
      if (pedeModal() || !rel.folhas) abrirModal();
    }
  };
})();
