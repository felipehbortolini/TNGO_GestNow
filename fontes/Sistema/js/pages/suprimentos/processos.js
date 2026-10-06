/* ==========================================================================
   Suprimentos > Processos de compra (RFx)
   Fluxo: Requisição > RFx emitida > Propostas recebidas > Equalização técnica
   > Equalização comercial > Negociação > Recomendação de adjudicação >
   Aprovada > Pedido/contrato emitido. Regras (validadas na api): mínimo de
   propostas (fornecedor único só com justificativa), técnica antes da
   comercial, proposta reprovada fica fora do mapa comercial, recomendação só
   para fornecedor cadastrado, aprovação por alçada com segregação de funções
   e limite do saldo da EAC. A emissão cria o pedido (04) ou o contrato (03) e
   compromete o valor na EAC. Cada ação grava o marco realizado no MAS.
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt, S = GI.sup;
  var ETAPAS = GI.api.suprimentos.ETAPAS;
  var projetoId, processos = [], tabela, tEq, selecionado = U.param("pacote") || null, filtro = { busca: U.param("pacote") || "", situacao: "andamento" };
  var fornecedores = [], par = { propostasMinimas: 3, folgaAlertaDias: 7 };

  function emAndamento(x) { return x.etapaIndice >= 0 && x.etapaIndice < 9; }
  function passa(x) {
    if (filtro.situacao === "andamento" && !emAndamento(x) && x.pacote.codigo !== selecionado) return false;
    return U.contem([x.pacote.codigo, x.pacote.escopo, x.processo ? x.processo.numero : "", x.melhor ? x.melhor.fornecedor : "", x.pacote.fornecedor].join(" "), filtro.busca);
  }
  function atual() { return processos.filter(function (x) { return x.pacote.codigo === selecionado; })[0] || null; }

  function renderKpis() {
    var and = processos.filter(emAndamento);
    var comp = processos.filter(function (x) { return x.pacote.propostasValidas; });
    var unicos = comp.filter(function (x) { return x.pacote.fornecedorUnico; }).length;
    var ciclos = processos.filter(function (x) { return x.etapa === "Pedido/contrato emitido" && x.cicloDias != null; });
    var aguard = processos.filter(function (x) { return x.etapa === "Recomendação de adjudicação"; }).length;
    var hoje = GI.api.referencia();
    var previstosAnd = processos.filter(function (x) { var pl = x.pacote.plano || {}; return pl.requisicao && pl.requisicao <= hoje && (!pl.pedido || pl.pedido > hoje); }).length;
    var cicloLb = ciclos.filter(function (x) { var pl = x.pacote.plano || {}; return pl.requisicao && pl.pedido; })
      .map(function (x) { return GI.regras.diasEntre(x.pacote.plano.requisicao, x.pacote.plano.pedido); });
    cicloLb = cicloLb.length ? Math.round(cicloLb.reduce(function (s, v) { return s + v; }, 0) / cicloLb.length) : null;
    var media = comp.length ? comp.reduce(function (s, x) { return s + x.pacote.propostasValidas; }, 0) / comp.length : null;
    document.getElementById("kpis").innerHTML = [
      U.kpi({ rotulo: "Em andamento", valor: F.num(and.length), icone: "fileSearch", cor: "primary", esperado: { rotulo: "Previsto", valor: F.num(previstosAnd) }, rodape: F.num(processos.length) + " pacotes no plano" }),
      U.kpi({ rotulo: "Aguardando aprovação", valor: F.num(aguard), icone: "gavel", cor: aguard ? "warning" : "success", esperado: { rotulo: "Esperado", valor: F.num(0) }, rodape: "recomendação na alçada" }),
      U.kpi({ rotulo: "Propostas válidas por processo", valor: F.num(media, 1), icone: "users", cor: media >= 3 ? "success" : "warning", esperado: { rotulo: "Meta", valor: "≥ " + F.num(par.propostasMinimas) } }),
      U.kpi({ rotulo: "Fornecedor único", valor: F.num(comp.length ? unicos / comp.length * 100 : 0, 1), unidade: "%", icone: "user", cor: unicos ? "warning" : "success", esperado: { rotulo: "Esperado", valor: F.pct(0, 0) }, rodape: F.num(unicos) + " processos com justificativa" }),
      U.kpi({ rotulo: "Ciclo de compra", valor: ciclos.length ? F.num(Math.round(ciclos.reduce(function (s, x) { return s + x.cicloDias; }, 0) / ciclos.length)) : "", unidade: "dias", icone: "clock", cor: "info",
        esperado: { rotulo: "Linha de base", valor: cicloLb == null ? "·" : F.num(cicloLb) + " dias" }, rodape: "requisição até o pedido emitido" })
    ].join("");
  }

  function render() {
    renderKpis();
    var lista = processos.filter(passa);
    document.getElementById("sub-proc").textContent = U.plural(lista.length, "processo") + " · abra o processo para ver o mapa de equalização e avançar o fluxo";
    tabela.atualizar(lista, true);
    renderDetalhe();
  }

  function carregar() {
    return Promise.all([GI.api.suprimentos.processos(projetoId), GI.api.suprimentos.fornecedores(), GI.api.parametros()]).then(function (r) {
      processos = r[0]; fornecedores = r[1]; par = r[2].suprimentos;
      if (!selecionado) { var p = processos.filter(function (x) { return emAndamento(x) && x.etapaIndice > 0; })[0] || processos.filter(emAndamento)[0]; selecionado = p ? p.pacote.codigo : null; }
      render();
    });
  }

  /* ---------------- Detalhe do processo ---------------- */
  var BOTOES = {
    "Planejado": [["requisicao", "Registrar requisição", "filePlus", "primary"]],
    "Requisição": [["rfx", "Emitir RFx", "send", "primary"]],
    "RFx emitida": [["proposta", "Registrar proposta", "upload", "primary"]],
    "Propostas recebidas": [["proposta", "Registrar proposta", "upload", "secondary"], ["encerrar", "Encerrar recebimento", "check", "primary"]],
    "Equalização técnica": [["eqTecnica", "Equalização técnica", "clipboardCheck", "primary"]],
    "Equalização comercial": [["eqComercial", "Concluir equalização comercial", "coins", "primary"]],
    "Negociação": [["negociacao", "Registrar negociação", "swap", "secondary"], ["recomendacao", "Recomendar adjudicação", "star", "primary"]],
    "Recomendação de adjudicação": [["devolver", "Devolver", "chevronLeft", "secondary"], ["aprovar", "Aprovar adjudicação", "checkCircle", "primary"]],
    "Aprovada": [["emitir", "Emitir pedido ou contrato", "fileContract", "primary"]]
  };

  function renderDetalhe() {
    var x = atual(), sec = document.getElementById("detalhe");
    if (!x) { sec.hidden = true; return; }
    sec.hidden = false;
    var p = x.pacote, pr = x.processo;
    document.getElementById("t-det").textContent = p.codigo + " " + p.escopo;
    document.getElementById("sub-det").textContent = [pr ? pr.numero : "RFx ainda não emitida", p.tipo, p.modalidade, "comprador " + U.pessoa(p.compradorId)].join(" · ");
    var bts = (BOTOES[x.etapa] || []).map(function (b) {
      var rot = b[0] === "emitir" ? (x.servico ? "Emitir contrato" : "Emitir pedido") : b[1];
      return '<button type="button" class="btn btn--' + b[3] + ' btn--sm" data-acao="' + b[0] + '">' + U.icone(b[2]) + U.esc(rot) + "</button>";
    }).join("");
    if (x.etapa === "Pedido/contrato emitido") bts = p.pedidoRef ? '<a class="btn btn--secondary btn--sm" href="' + U.tela("suprimentos", "diligenciamento", { pedido: p.pedidoRef }) + '">' + U.icone("truck") + "Diligenciamento " + U.esc(p.pedidoRef) + "</a>" :
      p.contratoRef ? '<a class="btn btn--secondary btn--sm" href="' + U.tela("financeiro", "contrato", { numero: p.contratoRef }) + '">' + U.icone("fileContract") + "Contrato " + U.esc(p.contratoRef) + "</a>" : "";
    bts += '<a class="btn btn--ghost btn--sm" href="' + U.tela("suprimentos", "mas", { busca: p.codigo }) + '">' + U.icone("matrix") + "Ver no MAS</a>";
    document.getElementById("fluxo").innerHTML = bts;

    document.getElementById("etapas").innerHTML = ETAPAS.slice(1).map(function (e, k) {
      var i = k + 1, cls = i < x.etapaIndice || x.etapaIndice === 9 ? "is-done" : i === x.etapaIndice ? "is-current" : "";
      return '<li class="step ' + cls + '"' + (cls === "is-current" ? ' aria-current="step"' : "") + '><span class="step__dot" aria-hidden="true"></span><span class="step__label">' + U.esc(e) + "</span></li>";
    }).join("");

    var linhas = [
      ["Item da EAC", x.eac ? U.esc(x.eac.codigo + " " + x.eac.descricao) + (x.eac.saldo != null ? ' <span class="text-muted">· saldo a comprometer ' + U.esc(F.moeda(x.eac.saldo)) + "</span>" : "") : '<span class="text-muted">sem EAC</span>'],
      ["Estimativa", U.esc(F.moeda(p.estimativaCentavos))],
      ["Pesos técnico e comercial", pr ? U.esc(pr.pesoTecnico + " / " + pr.pesoComercial) : "·"],
      ["Prazo das propostas", pr ? U.esc(F.data(pr.dataLimitePropostas)) : U.esc(F.data(p.plano.propostas)) + ' <span class="text-muted">(LB)</span>'],
      ["Convidados", pr ? U.esc(pr.convidados.join(", ")) : "·"],
      ["Propostas", U.esc(F.num(x.propostasRecebidas) + " recebidas · " + F.num(x.propostasAprovadas) + " aprovadas tecnicamente · mínimo " + F.num(x.minimo)) +
        (pr && pr.fornecedorUnico ? '<br><span class="badge badge--warning">Fornecedor único</span> <span class="text-small">' + U.esc(pr.fornecedorUnico.justificativa) + "</span>" : "") +
        (pr && pr.excecaoMinimo ? '<br><span class="badge badge--warning">Exceção ao mínimo</span> <span class="text-small">' + U.esc(pr.excecaoMinimo.justificativa) + "</span>" : "")],
      ["Alçada exigida", U.esc(x.alcada.papel) + ' <span class="text-muted">· valor de referência ' + U.esc(F.moeda(x.valorReferencia)) + "</span>"]
    ];
    if (pr && pr.recomendacao) linhas.push(["Recomendação", U.esc(pr.recomendacao.fornecedor + " · " + F.moeda(pr.recomendacao.valorCentavos) + " · " + F.data(pr.recomendacao.data)) +
      (pr.recomendacao.justificativa ? '<br><span class="text-small text-muted">' + U.esc(pr.recomendacao.justificativa) + "</span>" : "")]);
    if (pr && pr.aprovacao) linhas.push(["Aprovação", U.esc(U.pessoa(pr.aprovacao.porId) + " · " + pr.aprovacao.alcada + " · " + F.data(pr.aprovacao.data))]);
    if (p.adjudicadoCentavos != null) linhas.push(["Adjudicado", U.esc(F.moeda(p.adjudicadoCentavos) + " · " + p.fornecedor) +
      (p.primeiraPropostaCentavos ? ' <span class="text-muted">· saving de negociação ' + U.esc(F.moeda(p.primeiraPropostaCentavos - p.adjudicadoCentavos)) + "</span>" : "")]);
    document.getElementById("resumo-det").innerHTML = '<dl class="dl">' + linhas.map(function (l) { return "<dt>" + U.esc(l[0]) + "</dt><dd>" + l[1] + "</dd>"; }).join("") + "</dl>";

    document.getElementById("sub-eq").textContent = !pr ? "O mapa aparece quando a RFx é emitida." :
      !x.tecnicaConcluida ? "Equalização técnica pendente: notas e aprovação técnica antes da comercial." :
      "Nota comercial = menor preço tecnicamente aprovado ÷ preço x 100 · nota final = técnica x " + pr.pesoTecnico + "% + comercial x " + pr.pesoComercial + "% · proposta reprovada fica fora do ranking";
    tEq.atualizar(pr ? pr.propostas : []);
    var hist = pr ? pr.historico.slice().reverse() : [];
    document.getElementById("historico").innerHTML = hist.length ? '<ul class="feed">' + hist.map(function (h) {
      return '<li class="feed__item"><span class="feed__icon">' + U.icone("history") + '</span><div class="feed__body"><span class="feed__title">' + U.esc(h.etapa) + "</span>" +
        '<span class="feed__detail">' + U.esc(F.data(h.data) + " · " + U.pessoa(h.porId) + " · " + h.texto) + "</span></div></li>";
    }).join("") + "</ul>" : U.vazio("Sem registros no histórico.", "history");
  }

  /* ---------------- Ações do fluxo ---------------- */
  function executar(acao, dados, msg) {
    var x = atual();
    return GI.api.suprimentos.acaoProcesso(x.pacote.id, acao, dados).then(function (r) {
      GI.ui.toast(typeof msg === "function" ? msg(r) : msg, "success");
      return carregar();
    });
  }
  function opcoesPessoas() { return Object.keys(U.mapas.pessoas).map(function (k) { var p = U.mapas.pessoas[k]; return { valor: p.id, texto: p.nome + " · " + p.funcao }; }); }
  function aprovadasOpcoes(x) {
    return x.processo.propostas.filter(function (q) { return q.tecnicamenteAprovada; }).sort(function (a, b) { return (a.ranking || 99) - (b.ranking || 99); })
      .map(function (q) { return { valor: q.fornecedor, texto: (q.ranking ? q.ranking + "º " : "") + q.fornecedor + " · " + F.moeda(q.negociadoCentavos || q.valorCentavos) }; });
  }
  var ref = function () { return GI.api.referencia(); };

  var ACOES = {
    requisicao: function (x) {
      GI.form.abrir({ titulo: "Registrar requisição", subtitulo: x.pacote.codigo + " " + x.pacote.escopo, campos: [
        { id: "data", rotulo: "Data da requisição", tipo: "data", obrigatorio: true, valor: ref() },
        { id: "documento", rotulo: "Documento da requisição", tipo: "texto", max: 40, placeholder: "Ex.: RM-MEC-0042 rev. 0" },
        { id: "espec", rotulo: "Especificação técnica e folha de dados", tipo: "arquivo", aceitar: ["pdf", "xlsx", "docx"] },
        { id: "observacao", rotulo: "Observação", tipo: "textarea", max: 300 }
      ], aoSalvar: function (v) { return executar("requisicao", v, "Requisição registrada; marco realizado no MAS."); } });
    },
    rfx: function (x) {
      var opc = fornecedores.filter(function (f) { return f.cadastrado && f.situacao !== "Bloqueado"; }).map(function (f) { return { valor: f.nome, texto: f.nome + " · " + f.situacao + (f.categorias.length ? " · " + f.categorias.join(", ") : "") }; });
      GI.form.abrir({ titulo: "Emitir RFx", subtitulo: x.pacote.codigo + " " + x.pacote.escopo, tamanho: "lg", campos: [
        { id: "data", rotulo: "Emissão", tipo: "data", obrigatorio: true, valor: ref() },
        { id: "dataLimite", rotulo: "Prazo para as propostas", tipo: "data", obrigatorio: true, valor: x.pacote.plano.propostas },
        { id: "pesoTecnico", rotulo: "Peso técnico (%)", tipo: "numero", obrigatorio: true, min: 0, maxNumero: 100, valor: 40 },
        { id: "pesoComercial", rotulo: "Peso comercial (%)", tipo: "numero", obrigatorio: true, min: 0, maxNumero: 100, valor: 60 },
        { id: "convidados", rotulo: "Fornecedores cadastrados convidados", tipo: "multi", opcoes: opc, valor: [] },
        { id: "outros", rotulo: "Outros convidados (separados por vírgula)", tipo: "texto", max: 200, largura: "full", ajuda: "Sem cadastro: para ser adjudicado, o fornecedor precisa ser cadastrado e qualificado" },
        { id: "unico", rotulo: "Fornecedor único (sem concorrência)", tipo: "check", largura: "full" },
        { id: "justUnico", rotulo: "Justificativa do fornecedor único", tipo: "textarea", max: 300, mostrarSe: function (v) { return v.unico; } }
      ], aoSalvar: function (v) {
        var conv = v.convidados.concat((v.outros || "").split(",").map(function (s) { return s.trim(); }).filter(Boolean));
        return executar("rfx", { data: v.data, dataLimite: v.dataLimite, pesoTecnico: v.pesoTecnico, pesoComercial: v.pesoComercial, convidados: conv,
          fornecedorUnico: v.unico, justificativaUnico: v.justUnico }, function (r) { return r.processo.numero + " emitida para " + U.plural(conv.length, "fornecedor", "fornecedores") + "."; });
      } });
    },
    proposta: function (x) {
      GI.form.abrir({ titulo: "Registrar proposta", subtitulo: x.processo.numero + " · " + x.pacote.escopo, campos: [
        { id: "fornecedor", rotulo: "Fornecedor", tipo: "texto", obrigatorio: true, max: 80, sugestoes: x.processo.convidados, largura: "full" },
        { id: "data", rotulo: "Recebida em", tipo: "data", obrigatorio: true, valor: ref() },
        { id: "validade", rotulo: "Validade da proposta", tipo: "data" },
        { id: "valor", rotulo: "Valor total", tipo: "moeda", obrigatorio: true },
        { id: "prazo", rotulo: "Prazo de entrega (dias após o pedido)", tipo: "numero", obrigatorio: true, min: 1, maxNumero: 900 },
        { id: "anexos", rotulo: "Proposta técnica e comercial (PDF)", tipo: "arquivo", aceitar: ["pdf"], obrigatorio: true }
      ], aoSalvar: function (v) {
        return executar("proposta", { fornecedor: v.fornecedor, data: v.data, validade: v.validade, valorCentavos: v.valor, prazoDias: v.prazo, anexos: v.anexos },
          "Proposta de " + v.fornecedor + " registrada.");
      } });
    },
    encerrar: function (x) {
      var falta = x.propostasRecebidas < x.minimo && !(x.processo && x.processo.fornecedorUnico);
      GI.form.abrir({ titulo: "Encerrar recebimento de propostas", subtitulo: x.processo.numero, tamanho: "sm",
        intro: '<p class="text-small">' + U.esc(U.plural(x.propostasRecebidas, "proposta recebida", "propostas recebidas") + "; mínimo de " + x.minimo + " propostas por processo.") + "</p>",
        campos: [
          { id: "data", rotulo: "Encerramento", tipo: "data", obrigatorio: true, valor: ref() },
          { id: "justificativa", rotulo: "Justificativa para seguir abaixo do mínimo", tipo: "textarea", max: 300, obrigatorio: falta, mostrarSe: function () { return falta; } }
        ], aoSalvar: function (v) { return executar("encerrarRecebimento", v, "Recebimento encerrado; equalização técnica liberada."); } });
    },
    eqTecnica: function (x) {
      var campos = [];
      x.processo.propostas.forEach(function (q) {
        campos.push({ id: "i" + q.id, tipo: "info", html: "<b>" + U.esc(q.fornecedor) + '</b> <span class="text-small text-muted">' + U.esc(F.moeda(q.valorCentavos) + " · " + q.prazoDias + " dias") + "</span>" });
        campos.push({ id: "n" + q.id, rotulo: "Nota técnica (0 a 100)", tipo: "numero", obrigatorio: true, min: 0, maxNumero: 100, valor: q.notaTecnica });
        campos.push({ id: "a" + q.id, rotulo: "Aprovada tecnicamente", tipo: "check", valor: q.tecnicamenteAprovada !== false });
        campos.push({ id: "d" + q.id, rotulo: "Desvios e esclarecimentos", tipo: "texto", max: 160, largura: "full", valor: q.desvios });
      });
      campos.push({ id: "responsavel", rotulo: "Responsável pelo parecer técnico", tipo: "select", obrigatorio: true, opcoes: opcoesPessoas(), valor: 6 });
      campos.push({ id: "data", rotulo: "Data do parecer", tipo: "data", obrigatorio: true, valor: ref() });
      campos.push({ id: "parecer", rotulo: "Parecer técnico", tipo: "textarea", max: 400 });
      campos.push({ id: "justificativa", rotulo: "Justificativa (menos aprovadas que o mínimo)", tipo: "textarea", max: 300,
        mostrarSe: function (v) { return x.processo.propostas.filter(function (q) { return v["a" + q.id]; }).length < x.minimo && !x.processo.fornecedorUnico && !x.processo.excecaoMinimo; } });
      GI.form.abrir({ titulo: "Equalização técnica", subtitulo: x.processo.numero + " · a técnica é concluída antes da comercial", tamanho: "lg", campos: campos,
        aoSalvar: function (v) {
          return executar("eqTecnica", { data: v.data, responsavelId: Number(v.responsavel), parecer: v.parecer, justificativa: v.justificativa,
            avaliacoes: x.processo.propostas.map(function (q) { return { id: q.id, notaTecnica: v["n" + q.id], aprovada: v["a" + q.id], desvios: v["d" + q.id] }; }) },
            "Equalização técnica concluída; mapa comercial liberado.");
        } });
    },
    eqComercial: function (x) {
      function previa(pt, pc) {
        var val = x.processo.propostas.filter(function (q) { return q.tecnicamenteAprovada; });
        var menor = Math.min.apply(null, val.map(function (q) { return q.valorCentavos; }));
        var r = val.map(function (q) { var nc = GI.regras.notaComercial(q.valorCentavos, menor); return { f: q.fornecedor, v: q.valorCentavos, nt: q.notaTecnica, nc: nc, nf: GI.regras.notaFinal(q.notaTecnica, nc, pt, pc) }; })
          .sort(function (a, b) { return b.nf - a.nf; });
        return '<div class="table-wrap"><table class="table table--compact"><thead><tr><th>#</th><th>Fornecedor</th><th class="num">Valor</th><th class="num">Técnica</th><th class="num">Comercial</th><th class="num">Final</th></tr></thead><tbody>' +
          r.map(function (q, i) { return "<tr><td>" + (i + 1) + "</td><td>" + U.esc(q.f) + '</td><td class="num">' + U.esc(F.moeda(q.v)) + '</td><td class="num">' + F.num(q.nt, 1) + '</td><td class="num">' + F.num(q.nc, 1) + '</td><td class="num"><b>' + F.num(q.nf, 1) + "</b></td></tr>"; }).join("") +
          "</tbody></table></div>";
      }
      GI.form.abrir({ titulo: "Concluir equalização comercial", subtitulo: x.processo.numero, tamanho: "lg", campos: [
        { id: "pesoTecnico", rotulo: "Peso técnico (%)", tipo: "numero", obrigatorio: true, min: 0, maxNumero: 100, valor: x.processo.pesoTecnico },
        { id: "pesoComercial", rotulo: "Peso comercial (%)", tipo: "numero", obrigatorio: true, min: 0, maxNumero: 100, valor: x.processo.pesoComercial },
        { id: "previa", rotulo: "Ranking", tipo: "info", html: "" },
        { id: "data", rotulo: "Data do mapa comercial", tipo: "data", obrigatorio: true, valor: ref() }
      ], aoMudar: function (v, ctx) { ctx.info("previa", v.pesoTecnico + v.pesoComercial === 100 ? previa(v.pesoTecnico, v.pesoComercial) : '<span class="valor--negativo">Os pesos devem somar 100.</span>'); },
        aoSalvar: function (v) { return executar("eqComercial", v, "Mapa comercial concluído; processo em negociação."); } });
    },
    negociacao: function (x) {
      GI.form.abrir({ titulo: "Registrar negociação", subtitulo: x.processo.numero, campos: [
        { id: "fornecedor", rotulo: "Fornecedor", tipo: "select", obrigatorio: true, opcoes: aprovadasOpcoes(x), valor: x.melhor ? x.melhor.fornecedor : "", largura: "full" },
        { id: "valor", rotulo: "Valor negociado", tipo: "moeda", obrigatorio: true },
        { id: "data", rotulo: "Data", tipo: "data", obrigatorio: true, valor: ref() },
        { id: "observacao", rotulo: "Condições negociadas", tipo: "textarea", max: 300 }
      ], aoSalvar: function (v) { return executar("negociacao", { fornecedor: v.fornecedor, valorCentavos: v.valor, data: v.data, observacao: v.observacao }, "Negociação registrada."); } });
    },
    recomendacao: function (x) {
      var m = x.melhor;
      GI.form.abrir({ titulo: "Recomendar adjudicação", subtitulo: x.processo.numero, tamanho: "lg",
        intro: '<div class="alert">' + U.icone("info") + '<div class="alert__body">Melhor nota final: <b>' + U.esc(m ? m.fornecedor + " (" + F.num(m.notaFinal, 1) + ")" : "·") +
          "</b>. Recomendar outro fornecedor, ou fornecedor não qualificado, exige justificativa.</div></div>",
        campos: [
          { id: "fornecedor", rotulo: "Fornecedor recomendado", tipo: "select", obrigatorio: true, opcoes: aprovadasOpcoes(x), valor: m ? m.fornecedor : "", largura: "full" },
          { id: "valor", rotulo: "Valor recomendado", tipo: "moeda", obrigatorio: true, valor: m ? (m.negociadoCentavos || m.valorCentavos) : null },
          { id: "data", rotulo: "Data", tipo: "data", obrigatorio: true, valor: ref() },
          { id: "alcada", rotulo: "Alçada de aprovação", tipo: "info", html: "" },
          { id: "justificativa", rotulo: "Justificativa da recomendação", tipo: "textarea", max: 400 }
        ],
        aoMudar: function (v, ctx) {
          (function () {
            var a = GI.regras.alcada(v.valor || 0, par.alcadas);
            var saldo = x.eac && x.eac.saldo != null && v.valor > x.eac.saldo ? '<br><span class="text-small valor--sobrecusto">Acima do saldo a comprometer do item ' + U.esc(x.eac.codigo) + " (" + U.esc(F.moeda(x.eac.saldo)) + "): a aprovação será recusada sem remanejamento ou SM.</span>" : "";
            ctx.info("alcada", U.esc(a.papel) + saldo);
          })();
        },
        aoSalvar: function (v) { return executar("recomendacao", { fornecedor: v.fornecedor, valorCentavos: v.valor, data: v.data, justificativa: v.justificativa }, "Recomendação enviada para aprovação na alçada."); } });
    },
    devolver: function (x) {
      GI.form.abrir({ titulo: "Devolver recomendação", subtitulo: x.processo.numero, tamanho: "sm", campos: [
        { id: "motivo", rotulo: "Motivo", tipo: "textarea", obrigatorio: true, max: 300 }
      ], aoSalvar: function (v) { return executar("devolver", v, "Recomendação devolvida para negociação."); } });
    },
    aprovar: function (x) {
      var rc = x.processo.recomendacao;
      GI.form.abrir({ titulo: "Aprovar adjudicação", subtitulo: x.processo.numero,
        intro: '<dl class="dl"><dt>Recomendado</dt><dd>' + U.esc(rc.fornecedor) + '</dd><dt>Valor</dt><dd class="num">' + U.esc(F.moeda(rc.valorCentavos)) +
          "</dd><dt>Alçada exigida</dt><dd><b>" + U.esc(x.alcada.papel) + "</b></dd>" + (x.eac && x.eac.saldo != null ? "<dt>Saldo a comprometer (EAC " + U.esc(x.eac.codigo) + ')</dt><dd class="num">' + U.esc(F.moeda(x.eac.saldo)) + "</dd>" : "") +
          '</dl><p class="text-small text-muted mt-4">Segregação de funções: o aprovador não pode ser o comprador nem quem recomendou.</p>',
        campos: [
          { id: "aprovador", rotulo: "Aprovador", tipo: "select", obrigatorio: true, opcoes: opcoesPessoas(), valor: 2 },
          { id: "data", rotulo: "Data da aprovação", tipo: "data", obrigatorio: true, valor: ref() },
          { id: "parecer", rotulo: "Parecer", tipo: "textarea", max: 300 }
        ], aoSalvar: function (v) { return executar("aprovar", { aprovadorId: v.aprovador, data: v.data, parecer: v.parecer }, "Adjudicação aprovada; marco realizado no MAS."); } });
    },
    emitir: function (x) {
      var rc = x.processo.recomendacao, orig = x.processo.propostas.filter(function (q) { return q.fornecedor === rc.fornecedor; })[0];
      var campos = x.servico ? [
        { id: "data", rotulo: "Emissão do contrato", tipo: "data", obrigatorio: true, valor: ref() },
        { id: "inicio", rotulo: "Início (mobilização)", tipo: "data", obrigatorio: true, valor: x.pacote.ros },
        { id: "termino", rotulo: "Término contratual", tipo: "data", obrigatorio: true },
        { id: "fiscal", rotulo: "Fiscal do contrato", tipo: "select", obrigatorio: true, opcoes: opcoesPessoas(), valor: 12 },
        { id: "retencao", rotulo: "Retenção contratual (%)", tipo: "numero", min: 0, maxNumero: 20, valor: 5 }
      ] : [
        { id: "data", rotulo: "Emissão do pedido", tipo: "data", obrigatorio: true, valor: ref() },
        { id: "prazo", rotulo: "Prazo de entrega (dias)", tipo: "numero", obrigatorio: true, min: 1, maxNumero: 900, valor: orig ? orig.prazoDias : null },
        { id: "contratual", rotulo: "Data contratual de entrega", tipo: "info", html: "" }
      ];
      GI.form.abrir({ titulo: x.servico ? "Emitir contrato" : "Emitir pedido", subtitulo: x.processo.numero + " · " + rc.fornecedor + " · " + F.moeda(rc.valorCentavos),
        intro: '<p class="text-small">' + (x.servico ? "O contrato nasce no módulo 03 (administração contratual)" : "O pedido entra no diligenciamento com o cronograma de fabricação padrão") +
          " e o valor fica comprometido no item " + U.esc(x.pacote.eacCodigo || "") + " da EAC.</p>",
        campos: campos,
        aoMudar: x.servico ? null : function (v, ctx) {
          if (!v.data || !(v.prazo > 0)) { ctx.info("contratual", ""); return; }
          var d = new Date(v.data + "T00:00:00"); d.setDate(d.getDate() + v.prazo);
          var iso = d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
          var f = GI.regras.folga(x.pacote.ros, iso);
          ctx.info("contratual", U.esc(F.data(iso)) + " · ROS " + U.esc(F.data(x.pacote.ros)) + " " + S.folga(f, GI.regras.faixaFolga(f, par.folgaAlertaDias, false)));
        },
        aoSalvar: function (v) {
          var d = x.servico ? { data: v.data, inicio: v.inicio, termino: v.termino, fiscalId: v.fiscal, retencaoPct: v.retencao } : { data: v.data, prazoDias: v.prazo };
          return executar("emitir", d, function (r) {
            return (x.servico ? "Contrato " + r.pacote.contratoRef : "Pedido " + r.pacote.pedidoRef) + " emitido; " + F.moeda(rc.valorCentavos) + " comprometidos na EAC.";
          });
        } });
    }
  };

  function novaRequisicao() {
    if (projetoId == null) { U.noProjeto("requisicao", "Nova requisição"); return; }
    var plan = processos.filter(function (x) { return x.etapa === "Planejado"; });
    if (!plan.length) { GI.ui.toast("Não há pacotes planejados aguardando requisição. Inclua o pacote no Plano de compras.", "info"); return; }
    GI.form.abrir({ titulo: "Nova requisição", subtitulo: "Pacotes do plano de compras ainda sem requisição", campos: [
      { id: "pacote", rotulo: "Pacote", tipo: "select", obrigatorio: true, largura: "full", opcoes: plan.map(function (x) { return { valor: x.pacote.codigo, texto: x.pacote.codigo + " " + x.pacote.escopo + " · LB " + F.data(x.pacote.plano.requisicao) }; }) },
      { id: "data", rotulo: "Data da requisição", tipo: "data", obrigatorio: true, valor: ref() },
      { id: "documento", rotulo: "Documento da requisição", tipo: "texto", max: 40, placeholder: "Ex.: RM-MEC-0042 rev. 0" },
      { id: "espec", rotulo: "Especificação técnica e folha de dados", tipo: "arquivo", aceitar: ["pdf", "xlsx", "docx"] }
    ], aoSalvar: function (v) { selecionado = v.pacote; return executar("requisicao", { data: v.data, documento: v.documento }, "Requisição de " + v.pacote + " registrada."); } });
  }

  GI.exportar.registrar(function () {
    var p = U.projeto(projetoId), x = atual();
    var blocos = [{ tipo: "kpis", titulo: "Indicadores", itens: S.kpisExport() }, { tipo: "tabela", titulo: "Processos de compra", dados: tabela.exportacao() }];
    if (x && x.processo) blocos.push({ tipo: "tabela", titulo: "Mapa de equalização " + x.processo.numero, dados: tEq.exportacao() });
    return { titulo: "Processos de compra (RFx)", subtitulo: p ? p.codigo + " " + p.nome : "Portfólio de projetos", arquivo: "processos-de-compra-" + (p ? p.codigo : "portfolio"), orientacao: "l", blocos: blocos };
  });

  GI.util.pronto().then(function () {
    projetoId = S.projeto(function (id) { projetoId = id; selecionado = null; carregar(); });
    var busca = document.getElementById("busca");
    busca.value = filtro.busca;
    busca.addEventListener("input", U.debounce(function () { filtro.busca = busca.value.trim(); render(); }, 200));
    document.getElementById("f-situacao").addEventListener("segmented:change", function (ev) { filtro.situacao = ev.detail.value; render(); });
    document.getElementById("btn-requisicao").addEventListener("click", novaRequisicao);
    document.getElementById("fluxo").addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-acao]"); if (b && ACOES[b.getAttribute("data-acao")]) ACOES[b.getAttribute("data-acao")](atual());
    });

    tabela = GI.tabela.criar("tabela", {
      porPagina: 20, legenda: "Processos de compra", vazio: "Nenhum processo encontrado.", ordem: { coluna: "codigo", direcao: "asc" },
      colunas: (projetoId == null ? [U.colunaProjeto("_p", { valor: function (x) { return U.codigoProjeto(x.pacote.projetoId); },
        html: function (x) { return U.esc(U.codigoProjeto(x.pacote.projetoId)); } })] : []).concat([
        { id: "codigo", titulo: "Pacote", valor: function (x) { return x.pacote.codigo; },
          html: function (x) { return '<div class="cell-title"><b>' + U.esc(x.pacote.codigo + " " + x.pacote.escopo) + "</b><small>" + U.esc((x.processo ? x.processo.numero + " · " : "") + x.pacote.tipo + (x.pacote.lli ? " · LLI" : "")) + "</small></div>"; } },
        { id: "etapa", titulo: "Etapa", valor: function (x) { return x.etapaIndice; }, html: function (x) { return S.etapa(x.etapa) + "<br>" + S.etapasMini(x.etapaIndice); },
          exportar: function (x) { return x.etapa; } },
        { id: "propostas", titulo: "Propostas", valor: function (x) { return x.processo ? x.propostasRecebidas : x.pacote.propostasValidas; },
          html: function (x) { return x.processo ? U.esc(F.num(x.propostasRecebidas) + " recebidas") + '<br><span class="text-small text-muted">' + U.esc(F.num(x.propostasAprovadas) + " aprovadas") + "</span>" :
            x.pacote.propostasValidas ? U.esc(F.num(x.pacote.propostasValidas) + " válidas") : ""; } },
        { id: "melhor", titulo: "Melhor proposta / adjudicado", valor: function (x) { return x.pacote.adjudicadoCentavos || (x.melhor ? x.melhor.valorCentavos : null); },
          html: function (x) {
            if (x.pacote.adjudicadoCentavos != null) return U.esc(F.moeda(x.pacote.adjudicadoCentavos)) + '<br><span class="text-small text-muted">' + U.esc(x.pacote.fornecedor) + "</span>";
            return x.melhor ? U.esc(F.moeda(x.melhor.negociadoCentavos || x.melhor.valorCentavos)) + '<br><span class="text-small text-muted">' + U.esc(x.melhor.fornecedor + " · nota " + F.num(x.melhor.notaFinal, 1)) + "</span>" :
              '<span class="text-small text-muted">' + U.esc("estimativa " + F.moeda(x.pacote.estimativaCentavos)) + "</span>";
          },
          exportar: function (x) { return x.pacote.adjudicadoCentavos != null ? F.moeda(x.pacote.adjudicadoCentavos) + " " + x.pacote.fornecedor : x.melhor ? F.moeda(x.melhor.valorCentavos) + " " + x.melhor.fornecedor : ""; } },
        { id: "alcada", titulo: "Alçada", valor: function (x) { return x.alcada.papel; } },
        { id: "adjLb", titulo: "Adjudicação (LB)", tipo: "data", valor: function (x) { return x.pacote.plano.adjudicacao; },
          html: function (x) {
            var r = x.pacote.real.adjudicacao, pv = x.pacote.previsao.adjudicacao, d = GI.regras.diasEntre(x.pacote.plano.adjudicacao, r || pv || GI.api.referencia());
            return U.esc(F.data(x.pacote.plano.adjudicacao)) + (r ? '<br><span class="text-small ' + (d > 0 ? "valor--negativo" : "valor--positivo") + '">real ' + U.esc(F.data(r)) + "</span>" :
              pv ? '<br><span class="text-small ' + (d > 0 ? "valor--negativo" : "text-muted") + '">prev. ' + U.esc(F.data(pv)) + "</span>" : "");
          } }
      ]),
      classeLinha: function (x) { return x.pacote.codigo === selecionado ? "is-selected" : ""; },
      acoes: function (x) { return '<button type="button" class="btn btn--secondary btn--icon btn--sm" data-abrir="' + U.esc(x.pacote.codigo) + '" aria-label="Abrir processo ' + U.esc(x.pacote.codigo) + '" title="Abrir processo">' + U.icone("eye") + "</button>"; }
    });
    document.getElementById("tabela").addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-abrir]");
      if (!b) return;
      selecionado = b.getAttribute("data-abrir");
      render();
      document.getElementById("detalhe").scrollIntoView({ behavior: "smooth", block: "start" });
    });

    tEq = GI.tabela.criar("t-equalizacao", {
      porPagina: 0, compacta: true, legenda: "Mapa de equalização", vazio: "Nenhuma proposta registrada.", ordem: { coluna: "ranking", direcao: "asc" },
      colunas: [
        { id: "ranking", titulo: "#", tipo: "num", html: function (q) { return q.ranking ? '<span class="ranking' + (q.ranking === 1 ? " ranking--1" : "") + '">' + q.ranking + "</span>" : ""; } },
        { id: "fornecedor", titulo: "Fornecedor", html: function (q) { return "<b>" + U.esc(q.fornecedor) + "</b><br>" + S.fornecedor(q.qualificacao) +
          (q.anexos || []).map(function (a) { return '<br><span class="text-small text-muted" title="' + U.esc(a.nome) + '">' + U.icone("filePdf") + " " + U.esc(a.nome) + "</span>"; }).join(""); } },
        { id: "valorCentavos", titulo: "Valor", tipo: "moeda" },
        { id: "negociadoCentavos", titulo: "Negociado", tipo: "moeda" },
        { id: "prazoDias", titulo: "Prazo (dias)", tipo: "num" },
        { id: "notaTecnica", titulo: "Nota técnica", tipo: "num", casas: 0 },
        { id: "tecnica", titulo: "Técnica", valor: function (q) { return q.tecnicamenteAprovada == null ? "Pendente" : q.tecnicamenteAprovada ? "Aprovada" : "Reprovada"; },
          html: function (q) { return q.tecnicamenteAprovada == null ? U.badge("Pendente", "neutral") : q.tecnicamenteAprovada ? U.badge("Aprovada", "success") : U.badge("Reprovada", "danger"); } },
        { id: "notaComercial", titulo: "Nota comercial", tipo: "num", casas: 1 },
        { id: "notaFinal", titulo: "Nota final", tipo: "num", casas: 1, html: function (q) { return q.notaFinal == null ? "" : "<b>" + F.num(q.notaFinal, 1) + "</b>"; } },
        { id: "desvios", titulo: "Desvios", classe: "cell-desvios" },
        { id: "anexos", titulo: "Anexos", oculta: true, valor: function (q) { return (q.anexos || []).map(function (a) { return a.nome; }).join(", "); } }
      ],
      classeLinha: function (q) { return q.tecnicamenteAprovada === false ? "is-muted" : q.ranking === 1 ? "is-selected" : ""; }
    });
    return carregar().then(function () {
      if (projetoId != null && U.acaoPendente() === "requisicao") novaRequisicao();
    });
  });
})(window.GI = window.GI || {});
