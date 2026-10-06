/* ==========================================================================
   Central de Ações > Atas
   Localizador das atas do projeto ou do portfólio (coluna Projeto); só a revisão
   mais recente de cada ata; "Gerar nova ata" com a numeração do projeto (no
   Portfólio, pede o projeto antes).
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt;
  var TIPOS = ["Coordenação de obra", "Licenciamento", "Status com o cliente", "Segurança", "Planejamento", "Kickoff", "Reunião de acompanhamento"];
  var projetoId = GI.api.projetoAtualId();
  var busca = "";
  var atas = [], acoes = [], tabela;

  function vigentes() {
    var maior = {};
    atas.forEach(function (a) { if (!maior[a.numero] || a.revisao > maior[a.numero].revisao) maior[a.numero] = a; });
    return Object.keys(maior).map(function (k) { return maior[k]; });
  }
  function doProjeto(a) { return projetoId == null || a.projetoId === projetoId; }

  function render() {
    var lista = vigentes().filter(doProjeto).filter(function (a) { return U.contem(a.numero + " " + a.assunto + " " + a.tipoReuniao + " " + U.codigoProjeto(a.projetoId), busca); });
    var p = U.projeto(projetoId) || {};
    document.getElementById("contagem").textContent = U.plural(lista.length, "ata") + " · " + (projetoId == null ? "Portfólio" : p.codigo || "");
    tabela.atualizar(lista);
  }

  function carregar() {
    return Promise.all([GI.api.listar("atas"), GI.api.central.acoes()]).then(function (r) {
      atas = r[0]; acoes = r[1]; render();
    });
  }

  function contagem(ata, st) {
    return acoes.filter(function (a) { return a.ataId === ata.id && a.ehAcao && (st ? a.status === st : a.status !== "concluida"); }).length;
  }

  /* Numeração pelo padrão do projeto (ex.: TN-2026-0039) */
  function prefixo() { var p = U.projeto(projetoId); return (p ? p.padraoAta : "ATA") + "-"; }

  function novaAta() {
    if (projetoId == null) { U.noProjeto("nova", "Gerar nova ata"); return; }
    var numero = GI.api.proximoCodigo("atas", prefixo());
    var pessoas = Object.keys(U.mapas.pessoas).map(function (k) { return { valor: k, texto: U.mapas.pessoas[k].nome }; });
    var empresas = Object.keys(U.mapas.empresas).map(function (k) { return { valor: k, texto: U.mapas.empresas[k].nome }; });
    GI.form.abrir({
      titulo: "Gerar nova ata", subtitulo: "Número " + numero, tamanho: "lg", textoSalvar: "Gerar ata",
      campos: [
        { id: "data", rotulo: "Data", tipo: "data", obrigatorio: true, valor: GI.api.referencia() },
        { id: "tipoReuniao", rotulo: "Tipo de reunião", tipo: "select", obrigatorio: true, opcoes: TIPOS.map(function (t) { return { valor: t, texto: t }; }) },
        { id: "diretoria", rotulo: "Diretoria", tipo: "texto", obrigatorio: true, valor: "Diretoria de Projetos" },
        { id: "unidade", rotulo: "Unidade", tipo: "texto", obrigatorio: true, valor: "Unidade Horizonte" },
        { id: "elaboradoPorId", rotulo: "Elaborado por", tipo: "select", obrigatorio: true, opcoes: pessoas, valor: String(GI.api.sessaoAtual().pessoaId) },
        { id: "empresaPrincipalId", rotulo: "Empresa principal", tipo: "select", opcoes: empresas, vazio: "Nenhuma" },
        { id: "assunto", rotulo: "Assunto", tipo: "textarea", obrigatorio: true, max: 150, linhas: 2, ajuda: "Máximo de 150 caracteres." },
        { id: "empresasIds", rotulo: "Empresas executoras (opcional)", tipo: "multi", opcoes: empresas }
      ],
      aoSalvar: function (v) {
        var reg = {
          escopo: "Projeto", projetoId: projetoId,
          numero: numero, revisao: 0, data: v.data, tipoReuniao: v.tipoReuniao, diretoria: v.diretoria, unidade: v.unidade,
          elaboradoPorId: Number(v.elaboradoPorId), assunto: v.assunto, empresaPrincipalId: v.empresaPrincipalId ? Number(v.empresaPrincipalId) : null,
          empresasIds: v.empresasIds.map(Number), participantesIds: [Number(v.elaboradoPorId)]
        };
        if (reg.empresaPrincipalId && reg.empresasIds.indexOf(reg.empresaPrincipalId) < 0) reg.empresasIds.unshift(reg.empresaPrincipalId);
        return GI.api.salvar("atas", reg).then(function (salva) {
          GI.ui.toast("Ata " + numero + " gerada.", "success");
          window.location.href = U.tela("central-acoes", "ata", { id: salva.id });
        });
      }
    });
  }

  document.getElementById("busca").addEventListener("input", U.debounce(function (ev) { busca = ev.target.value.trim(); render(); }, 200));
  document.getElementById("btn-nova").addEventListener("click", novaAta);

  GI.exportar.registrar(function () {
    return { titulo: "Atas", subtitulo: document.getElementById("contagem").textContent, arquivo: "atas",
      blocos: [{ tipo: "tabela", titulo: "Atas", dados: tabela.exportacao() }] };
  });

  GI.util.pronto().then(function () {
    tabela = GI.tabela.criar("tabela", {
      porPagina: 15, ordem: { coluna: "data", direcao: "desc" }, vazio: "Nenhuma ata encontrada.", legenda: "Atas",
      colunas: (projetoId == null ? [U.colunaProjeto()] : []).concat([
        { id: "numero", titulo: "Número", classe: "nowrap", html: function (a) { return '<a href="' + U.tela("central-acoes", "ata", { id: a.id }) + '"><b>' + U.esc(a.numero) + "</b></a>"; } },
        { id: "revisao", titulo: "Rev", tipo: "num" },
        { id: "data", titulo: "Data", tipo: "data" },
        { id: "assunto", titulo: "Assunto", html: function (a) { return '<div class="cell-title"><b>' + U.esc(a.assunto) + "</b></div>"; } },
        { id: "empresa", titulo: "Empresa principal", valor: function (a) { return U.empresa(a.empresaPrincipalId); } },
        { id: "tipoReuniao", titulo: "Tipo de reunião" },
        { id: "abertas", titulo: "Ações abertas", tipo: "num", valor: function (a) { return contagem(a); } },
        { id: "atrasadas", titulo: "Atrasadas", tipo: "num", valor: function (a) { return contagem(a, "atrasada"); },
          html: function (a) { var n = contagem(a, "atrasada"); return n ? U.badge(String(n), "danger", true) : "0"; } }
      ]),
      acoes: function (a) { return '<a class="btn btn--ghost btn--icon btn--sm" href="' + U.tela("central-acoes", "ata", { id: a.id }) + '" aria-label="Abrir ata ' + U.esc(a.numero) + '">' + U.icone("arrowRight") + "</a>"; }
    });
    return carregar().then(function () { if (U.acaoPendente() === "nova") novaAta(); });
  });
})(window.GI = window.GI || {});
