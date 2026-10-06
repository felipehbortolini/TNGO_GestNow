/* ==========================================================================
   Suprimentos > Plano de compras
   Pacote = estratégia de contratação: escopo, tipo, modalidade, LLI, item da
   EAC, estimativa, comprador, datas planejadas (LB) e data necessária na obra
   (ROS). Regras: todo pacote nasce ligado a um item da EAC; a LB fica
   congelada a partir da requisição (depois só ajustes justificados); o plano
   não pode nascer com folga negativa; LLI antes do gate de investimento exige
   aprovação específica (gate LLI). Entrada: modal Novo pacote e planilha.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt, S = GI.sup;
  var projetoId, pacotes = [], folhasEac = [], tabela, alerta = 7;
  var filtro = { busca: U.param("busca") || "", tipo: "", lli: false };

  function passa(p) {
    if (filtro.tipo && p.tipo !== filtro.tipo) return false;
    if (filtro.lli && !p.lli) return false;
    return U.contem([p.codigo, p.escopo, p.eacCodigo, p.eacDescricao, p.fornecedor, p.disciplina].join(" "), filtro.busca);
  }

  function render() {
    var adj = pacotes.filter(function (p) { return p.adjudicado; });
    var ref = GI.api.referencia();
    var ateHoje = pacotes.filter(function (p) { return p.plano.adjudicacao <= ref; });
    var est = pacotes.reduce(function (s, p) { return s + p.estimativaCentavos; }, 0);
    var saving = adj.reduce(function (s, p) { return s + p.savingCentavos; }, 0);
    var lli = pacotes.filter(function (p) { return p.lli; });
    var atrasados = pacotes.filter(function (p) { return !p.adjudicado && p.desvioAdjudicacaoDias > 0; });
    document.getElementById("kpis").innerHTML = [
      U.kpi({ rotulo: "Pacotes no plano", valor: F.num(pacotes.length), icone: "listChecks", cor: "primary",
        esperado: { rotulo: "Linha de base", valor: F.num(pacotes.filter(function (p) { return p.plano && p.plano.adjudicacao; }).length) }, rodape: F.moedaCompacta(est) + " estimados" }),
      U.kpi({ rotulo: "Adjudicados", valor: F.num(adj.length), icone: "checkCircle", cor: "success",
        esperado: { rotulo: "Previsto", valor: F.num(ateHoje.length) }, rodape: F.num(ateHoje.filter(function (p) { return p.adjudicado; }).length) + " dos previstos até hoje" }),
      U.kpi({ rotulo: "Adjudicação atrasada", valor: F.num(atrasados.length), icone: "clock", cor: atrasados.length ? "warning" : "success", esperado: { rotulo: "Esperado", valor: F.num(0) }, rodape: "LB da adjudicação vencida ou previsão após a LB" }),
      U.kpi({ rotulo: "Itens de longo prazo (LLI)", valor: F.num(lli.length), icone: "calendarClock", cor: "info",
        esperado: { rotulo: "Referência", valor: "de " + F.num(pacotes.length) + " pacotes" }, rodape: F.num(lli.filter(function (p) { return p.linha && p.linha.situacao === "Crítico"; }).length) + " com folga negativa" }),
      U.kpi({ rotulo: "Saving sobre estimativa", moeda: saving, icone: "coins", cor: saving >= 0 ? "success" : "danger",
        esperado: { rotulo: "Meta", valor: "≥ " + F.moedaCompacta(0) }, rodape: "pacotes adjudicados" })
    ].join("");
    var lista = pacotes.filter(passa);
    document.getElementById("sub-plano").textContent = U.plural(lista.length, "pacote") + " · LB = linha de base do plano; a LB fica congelada a partir da requisição";
    tabela.atualizar(lista);
  }

  function carregar() {
    return Promise.all([GI.api.suprimentos.pacotes(projetoId), GI.api.financeiro.mapaControle(projetoId), GI.api.parametros()]).then(function (r) {
      pacotes = r[0]; alerta = r[2].suprimentos.folgaAlertaDias;
      folhasEac = r[1].itens.filter(function (x) { return x.nivel === 3; });
      render();
    });
  }

  function opcoesPessoas() {
    return Object.keys(U.mapas.pessoas).map(function (k) { var p = U.mapas.pessoas[k]; return { valor: p.id, texto: p.nome + " · " + p.funcao }; });
  }
  function opcoesEac() { return folhasEac.map(function (x) { return { valor: x.codigo, texto: x.codigo + " " + x.descricao }; }); }
  function servico(t) { return t === "Serviço" || t === "EPC"; }

  /* Novo pacote ou edição. Depois da requisição, só escopo, comprador, estimativa e ROS, com justificativa. */
  function abrirPacote(p) {
    if (projetoId == null) {
      /* Portfólio: o cadastro e a edição acontecem no projeto do pacote */
      if (!p) U.noProjeto("novo", "Novo pacote de compra");
      else window.location.href = U.tela("suprimentos", "plano-compras", { projeto: p.projetoId, editar: p.id });
      return;
    }
    var proj = U.projeto(projetoId);
    if (!p && !folhasEac.length) { GI.ui.toast("Cadastre a EAC do projeto antes de incluir pacotes.", "warning"); return; }
    var congelado = p && !p.editavelLb;
    var campos;
    if (congelado) {
      campos = [
        { id: "info", tipo: "info", html: '<div class="alert">' + U.icone("lock") + '<div class="alert__body">A linha de base deste pacote está congelada desde a requisição (' +
          U.esc(F.data(p.real.requisicao)) + "). Datas do plano não mudam; ajuste escopo, comprador, estimativa ou ROS com justificativa.</div></div>" },
        { id: "escopo", rotulo: "Escopo de fornecimento", tipo: "texto", obrigatorio: true, max: 120, valor: p.escopo, largura: "full" },
        { id: "comprador", rotulo: "Comprador", tipo: "select", obrigatorio: true, opcoes: opcoesPessoas(), valor: p.compradorId },
        { id: "estimativa", rotulo: "Estimativa", tipo: "moeda", obrigatorio: true, valor: p.estimativaCentavos },
        { id: "ros", rotulo: "Data necessária na obra (ROS)", tipo: "data", obrigatorio: true, valor: p.ros, ajuda: "Vem do cronograma do projeto (02)" },
        { id: "justificativa", rotulo: "Justificativa da alteração", tipo: "textarea", obrigatorio: true, max: 300 }
      ];
    } else {
      campos = [
        { id: "escopo", rotulo: "Escopo de fornecimento", tipo: "texto", obrigatorio: true, max: 120, valor: p ? p.escopo : "", largura: "full" },
        { id: "tipo", rotulo: "Tipo", tipo: "select", obrigatorio: true, opcoes: S.TIPOS, valor: p ? p.tipo : "" },
        { id: "modalidade", rotulo: "Modalidade contratual", tipo: "select", obrigatorio: true, opcoes: S.MODALIDADES, valor: p ? p.modalidade : "" },
        { id: "disciplina", rotulo: "Disciplina", tipo: "select", obrigatorio: true, opcoes: S.DISCIPLINAS, valor: p ? p.disciplina : "" },
        { id: "comprador", rotulo: "Comprador", tipo: "select", obrigatorio: true, opcoes: opcoesPessoas(), valor: p ? p.compradorId : 7 },
        { id: "eac", rotulo: "Item da EAC", tipo: "select", obrigatorio: true, opcoes: opcoesEac(), valor: p ? p.eacCodigo : "", largura: "full" },
        { id: "estimativa", rotulo: "Estimativa", tipo: "moeda", obrigatorio: true, valor: p ? p.estimativaCentavos : null },
        { id: "saldo", rotulo: "Saldo a comprometer do item", tipo: "info", html: "" },
        { id: "requisicao", rotulo: "Requisição (LB)", tipo: "data", obrigatorio: true, valor: p ? p.plano.requisicao : "" },
        { id: "rfx", rotulo: "Emissão da RFx (LB)", tipo: "data", obrigatorio: true, valor: p ? p.plano.rfx : "" },
        { id: "adjudicacao", rotulo: "Adjudicação (LB)", tipo: "data", obrigatorio: true, valor: p ? p.plano.adjudicacao : "" },
        { id: "pedido", rotulo: "Pedido ou contrato (LB)", tipo: "data", obrigatorio: true, valor: p ? p.plano.pedido : "" },
        { id: "prazo", rotulo: "Prazo de entrega após o pedido (dias)", tipo: "numero", min: 1, maxNumero: 900, valor: p ? p.prazoEntregaDias : null,
          mostrarSe: function (v) { return !servico(v.tipo); } },
        { id: "ros", rotulo: "Data necessária na obra (ROS)", tipo: "data", obrigatorio: true, valor: p ? p.ros : "", ajuda: "Vem do cronograma do projeto (02)" },
        { id: "folga", rotulo: "Folga planejada", tipo: "info", html: "" },
        { id: "lli", rotulo: "Item de longo prazo de entrega (LLI)", tipo: "check", valor: p ? p.lli : false, largura: "full" },
        { id: "antecipado", rotulo: "Contratação antes do gate de investimento (FID)", tipo: "check", valor: !!(p && p.gateLli), largura: "full",
          mostrarSe: function (v) { return v.lli; } },
        { id: "gate", rotulo: "Aprovação específica do gate LLI", tipo: "texto", max: 160, largura: "full", valor: p && p.gateLli ? p.gateLli.referencia : "",
          placeholder: "Ex.: ata do comitê de investimentos e análise de risco do pacote", mostrarSe: function (v) { return v.lli && v.antecipado; } },
        { id: "emergencial", rotulo: "Compra emergencial (fora do plano original)", tipo: "check", valor: p ? p.emergencial : false, largura: "full" },
        { id: "justEmergencial", rotulo: "Justificativa da compra emergencial", tipo: "textarea", max: 300, valor: p ? p.justificativaEmergencial : "",
          mostrarSe: function (v) { return v.emergencial; } }
      ];
    }
    GI.form.abrir({
      titulo: p ? "Editar pacote " + p.codigo : "Novo pacote de compra", subtitulo: p ? p.escopo : (proj ? proj.codigo + " · " + GI.api.suprimentos.proximoCodigoPacote(projetoId) : ""),
      tamanho: "lg", campos: campos,
      aoMudar: congelado ? null : function (v, ctx) {
        var item = folhasEac.filter(function (x) { return x.codigo === v.eac; })[0];
        if (item) {
          var acima = v.estimativa > item.saldoAComprometer;
          ctx.info("saldo", '<span class="num' + (acima ? " valor--sobrecusto" : "") + '">' + U.esc(F.moeda(item.saldoAComprometer)) + "</span>" +
            (acima ? '<br><span class="text-small valor--sobrecusto">Estimativa acima do saldo: avalie remanejamento ou SM antes da adjudicação.</span>' : ""));
        } else ctx.info("saldo", '<span class="text-muted">Escolha o item da EAC.</span>');
        var fim = servico(v.tipo) ? v.pedido : v.pedido && v.prazo > 0 ? somar(v.pedido, v.prazo) : null;
        if (fim && v.ros) {
          var f = GI.regras.folga(v.ros, fim);
          ctx.info("folga", S.folga(f, GI.regras.faixaFolga(f, alerta, false)) + ' <span class="text-small text-muted">' +
            U.esc((servico(v.tipo) ? "contrato " : "entrega ") + F.data(fim) + " x ROS " + F.data(v.ros)) + "</span>");
        } else ctx.info("folga", '<span class="text-muted">Informe as datas.</span>');
      },
      aoSalvar: function (v) {
        var d = congelado ? { escopo: v.escopo, compradorId: v.comprador, estimativaCentavos: v.estimativa, ros: v.ros, justificativa: v.justificativa } : {
          escopo: v.escopo, tipo: v.tipo, modalidade: v.modalidade, disciplina: v.disciplina, compradorId: v.comprador, eacCodigo: v.eac, estimativaCentavos: v.estimativa,
          requisicao: v.requisicao, rfx: v.rfx, adjudicacao: v.adjudicacao, pedido: v.pedido, prazoEntregaDias: v.prazo, ros: v.ros,
          lli: v.lli, antecipadoFid: v.antecipado, gateLli: v.gate, emergencial: v.emergencial, justificativaEmergencial: v.justEmergencial };
        return GI.api.suprimentos.salvarPacote(projetoId, d, p ? p.id : null).then(function (r) {
          GI.ui.toast(p ? "Pacote " + r.codigo + " atualizado." : "Pacote " + r.codigo + " incluído no plano de compras.", "success");
          return carregar();
        });
      }
    });
  }
  function somar(iso, n) {
    var d = new Date(iso + "T00:00:00"); d.setDate(d.getDate() + Number(n));
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  }

  function importar() {
    if (projetoId == null) { U.noProjeto("importar", "Importar pacotes"); return; }
    if (!folhasEac.length) { GI.ui.toast("Cadastre a EAC do projeto antes de importar pacotes.", "warning"); return; }
    var pessoas = Object.keys(U.mapas.pessoas).map(function (k) { return U.mapas.pessoas[k].nome; });
    GI.importar.abrir({
      titulo: "Importar plano de compras", subtitulo: "Um pacote por linha; o código é gerado na importação", arquivoModelo: "modelo-plano-de-compras",
      colunas: [
        { campo: "escopo", titulo: "Escopo", tipo: "texto", obrigatorio: true, exemplo: "Compressores de ar" },
        { campo: "tipo", titulo: "Tipo", tipo: "lista", obrigatorio: true, opcoes: S.TIPOS, exemplo: "Equipamento" },
        { campo: "modalidade", titulo: "Modalidade", tipo: "lista", obrigatorio: true, opcoes: S.MODALIDADES, exemplo: "Preço global" },
        { campo: "disciplina", titulo: "Disciplina", tipo: "lista", obrigatorio: true, opcoes: S.DISCIPLINAS, exemplo: "Mecânica" },
        { campo: "eacCodigo", titulo: "Item da EAC", tipo: "lista", obrigatorio: true, opcoes: folhasEac.map(function (x) { return x.codigo; }), exemplo: "2.1.4" },
        { campo: "estimativaCentavos", titulo: "Estimativa (R$)", tipo: "moeda", obrigatorio: true, exemplo: "250.000,00" },
        { campo: "comprador", titulo: "Comprador", tipo: "lista", obrigatorio: true, opcoes: pessoas, exemplo: "Diego Matos" },
        { campo: "requisicao", titulo: "Requisição", tipo: "data", obrigatorio: true, exemplo: "05/10/2026" },
        { campo: "rfx", titulo: "RFx", tipo: "data", obrigatorio: true, exemplo: "15/10/2026" },
        { campo: "adjudicacao", titulo: "Adjudicação", tipo: "data", obrigatorio: true, exemplo: "20/11/2026" },
        { campo: "pedido", titulo: "Pedido", tipo: "data", obrigatorio: true, exemplo: "25/11/2026" },
        { campo: "prazoEntregaDias", titulo: "Prazo de entrega (dias)", tipo: "num", exemplo: "90" },
        { campo: "ros", titulo: "ROS", tipo: "data", obrigatorio: true, exemplo: "15/03/2027" },
        { campo: "lli", titulo: "LLI", tipo: "lista", opcoes: ["Sim", "Não"], exemplo: "Não" }
      ],
      validarLinha: function (l) {
        var e = [];
        if (!servico(l.tipo) && !(l.prazoEntregaDias > 0)) e.push("Prazo de entrega obrigatório para equipamento e material.");
        if (l.requisicao && l.rfx && l.adjudicacao && l.pedido && !(l.requisicao <= l.rfx && l.rfx <= l.adjudicacao && l.adjudicacao <= l.pedido)) e.push("Datas do plano fora de ordem.");
        return e;
      },
      aoImportar: function (linhas) {
        var ids = {};
        Object.keys(U.mapas.pessoas).forEach(function (k) { ids[U.mapas.pessoas[k].nome] = Number(k); });
        return GI.api.suprimentos.importarPacotes(projetoId, linhas.map(function (l) {
          var x = Object.assign({}, l); x.compradorId = ids[l.comprador]; x.lli = l.lli === "Sim"; return x;
        })).then(function (r) {
          carregar();
          return U.plural(r.importados, "pacote incluído", "pacotes incluídos") + " no plano." + (r.falhas.length ? " " + r.falhas.join(" ") : "");
        });
      }
    });
  }

  GI.exportar.registrar(function () {
    var p = U.projeto(projetoId);
    return {
      titulo: "Plano de compras", subtitulo: p ? p.codigo + " " + p.nome : "Portfólio de projetos", arquivo: "plano-de-compras-" + (p ? p.codigo : "portfolio"), orientacao: "l",
      blocos: [{ tipo: "kpis", titulo: "Resumo", itens: S.kpisExport() }, { tipo: "tabela", titulo: "Pacotes de compra", dados: tabela.exportacao() }]
    };
  });

  function colData(id, titulo, extra) {
    return Object.assign({ id: id, titulo: titulo, tipo: "data", valor: function (p) { return p.plano[id]; } }, extra || {});
  }

  GI.util.pronto().then(function () {
    projetoId = S.projeto(function (id) { projetoId = id; carregar(); });
    var busca = document.getElementById("busca");
    busca.value = filtro.busca;
    busca.addEventListener("input", U.debounce(function () { filtro.busca = busca.value.trim(); render(); }, 200));
    var ft = document.getElementById("f-tipo");
    ft.innerHTML = U.opcoes(S.TIPOS, "", "Todos os tipos");
    ft.addEventListener("change", function () { filtro.tipo = ft.value; render(); });
    document.getElementById("f-lli").addEventListener("change", function (ev) { filtro.lli = ev.target.checked; render(); });
    document.getElementById("btn-novo").addEventListener("click", function () { abrirPacote(null); });
    document.getElementById("btn-importar").addEventListener("click", importar);
    document.getElementById("btn-colunas").addEventListener("click", function () { GI.tabela.escolherColunas(tabela); });

    tabela = GI.tabela.criar("tabela", {
      porPagina: 20, legenda: "Pacotes do plano de compras", vazio: "Nenhum pacote encontrado.", ordem: { coluna: "codigo", direcao: "asc" },
      colunas: (projetoId == null ? [U.colunaProjeto()] : []).concat([
        { id: "codigo", titulo: "Pacote", fixa: true, html: function (p) { return "<b>" + S.linkMas(p.codigo) + "</b>" + (p.lli ? '<br><span class="badge badge--purple">LLI</span>' : "") +
          (p.emergencial ? '<br><span class="badge badge--warning">Emergencial</span>' : ""); } },
        { id: "escopo", titulo: "Escopo", fixa: true, html: function (p) { return '<div class="cell-title"><b>' + U.esc(p.escopo) + "</b><small>" + U.esc(p.tipo + " · " + p.modalidade + " · " + p.disciplina) + "</small></div>"; } },
        { id: "tipo", titulo: "Tipo", oculta: true }, { id: "modalidade", titulo: "Modalidade", oculta: true }, { id: "disciplina", titulo: "Disciplina", oculta: true },
        { id: "eacCodigo", titulo: "Item da EAC", html: function (p) { return p.eacCodigo ? S.linkEac(p.eacCodigo, p.projetoId) + '<br><span class="text-small text-muted">' + U.esc(p.eacDescricao) + "</span>" : '<span class="text-muted">sem EAC</span>'; },
          exportar: function (p) { return p.eacCodigo ? p.eacCodigo + " " + p.eacDescricao : ""; } },
        { id: "estimativaCentavos", titulo: "Estimativa", tipo: "moeda",
          html: function (p) { return U.esc(F.moeda(p.estimativaCentavos)) + (p.adjudicado ? '<br><span class="text-small text-muted">adjudicado ' + U.esc(F.moedaCompacta(p.adjudicadoCentavos)) + "</span>" : ""); } },
        { id: "comprador", titulo: "Comprador", oculta: true, valor: function (p) { return U.pessoa(p.compradorId); } },
        colData("requisicao", "Requisição (LB)", { oculta: true }), colData("rfx", "RFx (LB)", { oculta: true }),
        { id: "adjudicacao", titulo: "Adjudicação", tipo: "data", valor: function (p) { return p.plano.adjudicacao; },
          html: function (p) {
            var r = p.real.adjudicacao || p.previsao.adjudicacao;
            return '<span class="text-small text-muted">LB</span> ' + U.esc(F.data(p.plano.adjudicacao)) + (r ? '<br><span class="text-small ' + (p.desvioAdjudicacaoDias > 0 ? "valor--negativo" : "valor--positivo") + '">' +
              (p.real.adjudicacao ? "real " : "prev. ") + U.esc(F.data(r)) + (p.desvioAdjudicacaoDias ? " · " + U.esc(S.dias(p.desvioAdjudicacaoDias, true)) : "") + "</span>" :
              p.desvioAdjudicacaoDias > 0 ? '<br><span class="text-small valor--negativo">vencida há ' + U.esc(S.dias(p.desvioAdjudicacaoDias)) + "</span>" : "");
          },
          exportar: function (p) { return F.data(p.plano.adjudicacao) + (p.real.adjudicacao ? " / real " + F.data(p.real.adjudicacao) : ""); } },
        colData("pedido", "Pedido (LB)", { oculta: true }),
        { id: "ros", titulo: "ROS", tipo: "data" },
        { id: "etapa", titulo: "Etapa", html: function (p) { return S.etapa(p.etapa); } },
        { id: "folga", titulo: "Folga", tipo: "num", valor: function (p) { return p.linha ? p.linha.folgaDias : null; },
          html: function (p) { return p.linha ? S.folga(p.linha.folgaDias, p.linha.faixaFolga) : ""; } },
        { id: "adjudicadoCentavos", titulo: "Adjudicado", tipo: "moeda", oculta: true,
          html: function (p) { return p.adjudicado ? U.esc(F.moeda(p.adjudicadoCentavos)) + '<br><span class="text-small text-muted">' + U.esc(p.fornecedor) + "</span>" : ""; } },
        { id: "savingCentavos", titulo: "Saving", tipo: "moeda", oculta: true }
      ]),
      classeLinha: function (p) { return p.linha && p.linha.situacao === "Crítico" ? "is-alert" : p.codigo === filtro.busca ? "is-selected" : ""; },
      acoes: function (p) {
        return p.etapa === "Pedido/contrato emitido" ? "" : '<button type="button" class="btn btn--ghost btn--icon btn--sm" data-editar="' + p.id + '" aria-label="Editar pacote ' + U.esc(p.codigo) + '" title="Editar pacote">' + U.icone("edit") + "</button>";
      }
    });
    document.getElementById("tabela").addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-editar]");
      if (b) abrirPacote(pacotes.filter(function (p) { return String(p.id) === b.getAttribute("data-editar"); })[0]);
    });
    return carregar().then(function () {
      if (projetoId == null) return;
      var a = U.acaoPendente(), ed = U.param("editar");
      if (a === "novo") abrirPacote(null); else if (a === "importar") importar();
      else if (ed) { var pc = pacotes.filter(function (x) { return String(x.id) === ed; })[0]; if (pc && pc.etapa !== "Pedido/contrato emitido") abrirPacote(pc); }
    });
  });
})(window.GI = window.GI || {});
