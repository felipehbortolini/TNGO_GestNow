/* ============================================================
   analise.js — Comportamento do modal Análise do período (relatorio/analise)

   O botão "Análise do período" abre o modal em cinco telas: 02 KPIs e Relato do período,
   03 KPIs de custo e Curva S financeira e 04 Painel de suprimentos. O comportamento é
   compartilhado — não é o trio de uma tela —, então o par analise.js/analise.css é carregado
   pelo shell e o servidor desenha o fragmento inteiro do modal (passo 1 e passo 2).

   Registra window.TN.analise = { abrir(modulo, opcoes), abrirDoEndereco(modulo) }:

     botões     qualquer elemento com data-analise="<modulo>" abre o modal (ligação delegada)
     abrir      com tipo e período vai direto ao formulário; sem eles, abre o passo 1
     endereço   ?analise=1&tipo=&periodo= abre o modal ao carregar a tela (vindo do relatório
                gerencial); as telas chamam abrirDoEndereco no iniciar()
     gravação   o servidor responde um corpo com data-analise-salvo ou data-analise-excluida:
                o modal fecha

   Carrega pelo shell (app/index.html), nunca pela view. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const BASE = "/api/relatorio/analise";
  const LARGURA_FORMULARIO = 760;
  const TIPOS = ["Semanal", "Mensal"];

  let modalAberto = null;
  let ouvindo = false;

  function fecharModal() {
    if (modalAberto) modalAberto.close();
    modalAberto = null;
  }

  function enderecoDe(modulo, tipo, periodo) {
    const parametros = new URLSearchParams({ modulo: modulo });
    if (tipo) parametros.set("tipo", tipo);
    if (tipo && periodo) {
      parametros.set("periodo", periodo);
      return BASE + "/formulario?" + parametros.toString();
    }
    return BASE + "/periodo?" + parametros.toString();
  }

  function abrirModal(modulo, tipo, periodo) {
    fecharModal();
    const endereco = enderecoDe(modulo, tipo, periodo);
    modalAberto = window.TN.modal({
      title: window.TN.t("relatorio", "Análise do período"),
      width: LARGURA_FORMULARIO,
      onClose: function () {
        modalAberto = null;
      },
      body:
        '<div id="analise-modal" data-endereco="' + window.TN.esc(endereco) + '"' +
        " x-init=\"$ajax($el.dataset.endereco, { target: 'analise-modal' })\">" +
        '<div class="spinner" role="status" aria-label="' + window.TN.t("relatorio", "Carregando") + '"></div></div>'
    });
  }

  function abrir(modulo, opcoes) {
    const o = opcoes || {};
    const tipo = TIPOS.indexOf(o.tipo) >= 0 ? o.tipo : "";
    abrirModal(modulo, tipo, o.periodo || "");
  }

  function abrirDoEndereco(modulo) {
    const parametros = new URLSearchParams(window.location.search);
    if (parametros.get("analise") !== "1") return;
    abrir(modulo, {
      tipo: parametros.get("tipo") || "",
      periodo: parametros.get("periodo") || ""
    });
  }

  function aoClicar(evento) {
    const botao = evento.target.closest && evento.target.closest("[data-analise]");
    if (!botao) return;
    evento.preventDefault();
    abrir(botao.getAttribute("data-analise"));
  }

  /* A resposta da gravação e da exclusão traz a marca dentro do modal: a tela fecha. */
  function aoEnviar() {
    const marca = document.querySelector(
      "#analise-modal [data-analise-salvo], #analise-modal [data-analise-excluida]"
    );
    if (marca) fecharModal();
  }

  function ouvir() {
    if (ouvindo) return;
    ouvindo = true;
    document.addEventListener("click", aoClicar);
    document.addEventListener("ajax:sent", aoEnviar);
  }

  window.TN.analise = { abrir: abrir, abrirDoEndereco: abrirDoEndereco };

  ouvir();
})();
