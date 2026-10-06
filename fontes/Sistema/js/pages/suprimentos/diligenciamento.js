/* ==========================================================================
   Suprimentos > Diligenciamento e recebimento
   Por pedido: marcos de fabricação (LB contratual, previsão e realizado),
   data contratual, previsão de entrega, ROS e folga (ROS menos a previsão).
   Folga negativa gera alerta, ação de diligenciamento na Central (origem
   Suprimentos) e risco sugerido (05). FAT realizado gera inspeção no 06.
   Recebimento na obra com conferência, avarias e pendências. Importação dos
   pedidos exportados do ERP (uma linha por marco).
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt, S = GI.sup;
  var MARCOS = GI.api.suprimentos.MARCOS_PEDIDO;
  var projetoId, pedidos = [], tabela, tMarcos, par = null, paramRiscos = null;
  var inicial = U.param("pedido") || U.param("busca") || "";
  var selecionado = inicial || null, filtro = { busca: inicial, situacao: "abertos", faixa: "" };
  var TIPO_BADGE = { prazo: "success", atraso: "danger", vencido: "danger", "previsto-atraso": "warning", "a-vencer": "neutral", "sem-data": "neutral" };

  function sit(p) { return p.entregue ? "Entregue" : p.faixaFolga === "critico" ? "Crítico" : (p.faixaFolga === "atencao" || p.marcosVencidos) ? "Atenção" : "No prazo"; }
  function passa(p) {
    if (filtro.situacao === "abertos" && p.entregue && p.numero !== selecionado) return false;
    if (filtro.faixa === "critico" && !p.critico) return false;
    if (filtro.faixa === "atencao" && sit(p) !== "Atenção") return false;
    if (filtro.faixa === "vencidos" && !p.marcosVencidos) return false;
    return U.contem([p.numero, p.descricao, p.fornecedor, p.pacote].join(" "), filtro.busca);
  }
  function atual() { return pedidos.filter(function (p) { return p.numero === selecionado; })[0] || null; }

  function renderKpis() {
    var abertos = pedidos.filter(function (p) { return !p.entregue; });
    var ent = pedidos.filter(function (p) { return p.entregue; });
    var noPrazo = ent.filter(function (p) { return p.atrasoContratualDias <= 0; }).length;
    var crit = pedidos.filter(function (p) { return p.critico; });
    var venc = pedidos.reduce(function (s, p) { return s + p.marcosVencidos; }, 0);
    var hoje = GI.api.referencia();
    var previstosAbertos = pedidos.filter(function (p) { return p.dataContratual && p.dataContratual > hoje; }).length;
    var aten = pedidos.filter(function (p) { return sit(p) === "Atenção"; }).length;
    document.getElementById("kpis").innerHTML = [
      U.kpi({ rotulo: "Pedidos em aberto", valor: F.num(abertos.length), icone: "truck", cor: "primary", esperado: { rotulo: "Previsto", valor: F.num(previstosAbertos) }, rodape: F.moedaCompacta(abertos.reduce(function (s, p) { return s + p.valorCentavos; }, 0)) + " a receber",
        filtro: { valor: "", ativo: !filtro.faixa } }),
      U.kpi({ rotulo: "Críticos", valor: F.num(crit.length), icone: "alertTriangle", cor: crit.length ? "danger" : "success",
        esperado: { rotulo: "Esperado", valor: F.num(0) }, rodape: F.num(crit.filter(function (p) { return p.lli; }).length) + " de longo prazo (LLI) · previsão depois do ROS", filtro: { valor: "critico", ativo: filtro.faixa === "critico" } }),
      U.kpi({ rotulo: "Em atenção", valor: F.num(aten), icone: "clock", cor: aten ? "warning" : "success", esperado: { rotulo: "Esperado", valor: F.num(0) }, rodape: "folga de até " + F.num(par.folgaAlertaDias) + " dias ou marco vencido",
        filtro: { valor: "atencao", ativo: filtro.faixa === "atencao" } }),
      U.kpi({ rotulo: "Marcos vencidos", valor: F.num(venc), icone: "calendarClock", cor: venc ? "danger" : "success", esperado: { rotulo: "Esperado", valor: F.num(0) }, rodape: "previsão passou sem realização: atualize",
        filtro: { valor: "vencidos", ativo: filtro.faixa === "vencidos" } }),
      U.kpi({ rotulo: "Entrega no prazo (OTD)", valor: ent.length ? F.num(noPrazo / ent.length * 100, 1) : "", unidade: ent.length ? "%" : "", icone: "checkCircle", cor: ent.length && noPrazo === ent.length ? "success" : "warning",
        esperado: { rotulo: "Meta", valor: "≥ " + F.pct(90, 0) }, rodape: F.num(noPrazo) + " de " + F.num(ent.length) + " entregas até a data contratual" })
    ].join("");
  }

  function renderPendencias() {
    var crit = pedidos.filter(function (p) { return p.critico && (!p.acaoAberta || !p.risco); });
    var el = document.getElementById("pendencias");
    if (!crit.length) { el.innerHTML = ""; return; }
    el.innerHTML = '<div class="alert alert--danger">' + U.icone("alertTriangle") + '<div class="alert__body"><p class="alert__title">' +
      U.esc(U.plural(crit.length, "pedido crítico com tratamento pendente", "pedidos críticos com tratamento pendente")) + "</p>" +
      "<p>Folga negativa exige ação de diligenciamento na Central e avaliação do risco no registro (05).</p>" +
      '<ul class="planejado mt-2">' + crit.map(function (p) {
        return "<li>" + U.icone("truck") + "<span><b>" + U.esc(p.numero) + "</b> " + U.esc(p.descricao + " · folga " + S.dias(p.folgaDias, true)) + " " +
          (p.acaoAberta ? U.badge("Ação na Central", "success") : '<button type="button" class="btn btn--secondary btn--sm" data-gerar-acao="' + p.id + '">' + U.icone("actions") + "Gerar ação</button>") + " " +
          (p.risco ? U.badge(p.risco.codigo, "success") : '<button type="button" class="btn btn--secondary btn--sm" data-risco="' + p.id + '">' + U.icone("alertTriangle") + "Registrar risco sugerido</button>") +
          "</span></li>";
      }).join("") + "</ul></div></div>";
  }

  function render() {
    renderKpis(); renderPendencias();
    var lista = pedidos.filter(passa);
    document.getElementById("sub-ped").textContent = U.plural(lista.length, "pedido") + " · folga = ROS menos a previsão de entrega · alerta com " + F.num(par.folgaAlertaDias) + " dias ou menos";
    tabela.atualizar(lista, true);
    renderDetalhe();
  }

  function carregar() {
    return Promise.all([GI.api.suprimentos.pedidos(projetoId), GI.api.parametros()]).then(function (r) {
      pedidos = r[0]; par = r[1].suprimentos; paramRiscos = r[1].riscos;
      if (!selecionado || !atual()) { var c = pedidos.filter(function (p) { return p.critico; })[0] || pedidos[0]; selecionado = c ? c.numero : null; }
      render();
    });
  }

  function renderDetalhe() {
    var p = atual(), sec = document.getElementById("detalhe");
    if (!p) { sec.hidden = true; return; }
    sec.hidden = false;
    document.getElementById("t-det").textContent = p.numero + " " + p.descricao;
    document.getElementById("sub-det").textContent = [p.fornecedor, "emissão " + F.data(p.emissao), F.moeda(p.valorCentavos), "pacote " + p.pacote, sit(p)].join(" · ");
    var b = [];
    if (!p.entregue) b.push('<button type="button" class="btn btn--primary btn--sm" data-det="marco">' + U.icone("edit") + "Atualizar marco</button>");
    if (!p.entregue && p.marcos[4].realizada) b.push('<button type="button" class="btn btn--primary btn--sm" data-det="recebimento">' + U.icone("package") + "Registrar recebimento</button>");
    if (p.critico && !p.acaoAberta) b.push('<button type="button" class="btn btn--secondary btn--sm" data-gerar-acao="' + p.id + '">' + U.icone("actions") + "Gerar ação</button>");
    if (p.critico && !p.risco) b.push('<button type="button" class="btn btn--secondary btn--sm" data-risco="' + p.id + '">' + U.icone("alertTriangle") + "Registrar risco</button>");
    b.push('<a class="btn btn--ghost btn--sm" href="' + U.tela("suprimentos", "mas", { busca: p.pacote }) + '">' + U.icone("matrix") + "Ver no MAS</a>");
    document.getElementById("acoes-det").innerHTML = b.join("");
    tMarcos.atualizar(p.marcos);
    var rod = [];
    rod.push("<dt>Data contratual</dt><dd>" + U.esc(F.data(p.dataContratual)) + (p.atrasoContratualDias > 0 ? ' <span class="valor--negativo">' + U.esc(S.dias(p.atrasoContratualDias, true)) + "</span>" : "") + "</dd>");
    rod.push("<dt>ROS e folga</dt><dd>" + U.esc(F.data(p.ros)) + " " + S.folga(p.folgaDias, p.faixaFolga) + "</dd>");
    rod.push("<dt>Ação na Central</dt><dd>" + (p.acaoAberta ? '<a href="' + U.tela("central-acoes", "acoes", { busca: p.numero }) + '">' + U.esc(p.acaoAberta.assunto) + "</a> · " + U.esc(F.data(p.acaoAberta.prevista)) : '<span class="text-muted">nenhuma aberta</span>') + "</dd>");
    rod.push("<dt>Risco</dt><dd>" + (p.risco ? '<a href="' + U.tela("riscos", "ficha", { codigo: p.risco.codigo }) + '">' + U.esc(p.risco.codigo + " " + p.risco.titulo) + "</a>" : '<span class="text-muted">sem risco registrado</span>') + "</dd>");
    if (p.recebimento) rod.push("<dt>Recebimento</dt><dd>" + U.esc(F.data(p.recebimento.data) + " · " + (p.recebimento.conferido ? "conferido" : "conferência pendente") + (p.recebimento.avarias ? " · com avarias: " + (p.recebimento.descricaoAvarias || "") : " · sem avarias")) +
      (p.recebimento.pendencias ? '<br><span class="text-small valor--negativo">' + U.esc(p.recebimento.pendencias) + "</span>" : "") + "</dd>");
    var hist = (p.historico || []).slice().reverse().slice(0, 5);
    if (hist.length) rod.push("<dt>Últimas atualizações</dt><dd>" + hist.map(function (h) { return U.esc(F.data(h.data) + " · " + U.pessoa(h.porId) + " · " + h.texto); }).join("<br>") + "</dd>");
    document.getElementById("rodape-det").innerHTML = '<dl class="dl">' + rod.join("") + "</dl>";
  }

  /* ---------------- Modais ---------------- */
  function opcoesPessoas() { return Object.keys(U.mapas.pessoas).map(function (k) { var x = U.mapas.pessoas[k]; return { valor: x.id, texto: x.nome + " · " + x.funcao }; }); }
  function atualizarMarco(p) {
    var pend = p.marcos.map(function (m, i) { return { m: m, i: i }; }).filter(function (x) { return !x.m.realizada && x.i < 5; });
    var prox = pend[0] ? pend[0].i : 5;
    GI.form.abrir({
      titulo: "Atualizar marco", subtitulo: p.numero + " · " + p.fornecedor, tamanho: "lg",
      campos: [
        { id: "marco", rotulo: "Marco", tipo: "select", obrigatorio: true, largura: "full", valor: String(prox),
          opcoes: p.marcos.map(function (m, i) { return { m: m, i: i }; }).filter(function (x) { return !x.m.realizada; }).map(function (x) {
            return { valor: String(x.i), texto: x.m.nome + " · LB " + F.data(x.m.lb) + " · previsão " + F.data(x.m.previsao) }; }) },
        { id: "tipo", rotulo: "O que registrar", tipo: "select", obrigatorio: true, valor: "previsao",
          opcoes: [{ valor: "realizado", texto: "Marco realizado" }, { valor: "previsao", texto: "Nova previsão (reprogramação)" }] },
        { id: "realizada", rotulo: "Data realizada", tipo: "data", valor: GI.api.referencia(), mostrarSe: function (v) { return v.tipo === "realizado"; } },
        { id: "resultado", rotulo: "Resultado da inspeção em fábrica", tipo: "select", opcoes: ["Aprovado", "Reprovado"],
          mostrarSe: function (v) { return v.tipo === "realizado" && v.marco === "3"; }, ajuda: "Gera o registro de inspeção no 06 Qualidade" },
        { id: "inspetor", rotulo: "Inspetor", tipo: "select", opcoes: opcoesPessoas(), valor: 9, mostrarSe: function (v) { return v.tipo === "realizado" && v.marco === "3"; } },
        { id: "previsao", rotulo: "Nova previsão", tipo: "data", mostrarSe: function (v) { return v.tipo === "previsao" || (v.marco === "3" && v.resultado === "Reprovado"); } },
        { id: "cascata", rotulo: "Reprogramar os marcos seguintes na mesma quantidade de dias", tipo: "check", valor: true, largura: "full",
          mostrarSe: function (v) { return v.tipo === "previsao" || (v.marco === "3" && v.resultado === "Reprovado"); } },
        { id: "efeito", rotulo: "Efeito na folga", tipo: "info", html: "" },
        { id: "comentario", rotulo: "Comentário do diligenciamento", tipo: "textarea", max: 300, placeholder: "Fonte da informação, visita à fábrica, relatório do inspetor" },
        { id: "anexos", rotulo: "Evidências (relatório de fabricação, fotos, certificado)", tipo: "arquivo", aceitar: ["pdf", "jpg", "png"] }
      ],
      aoMudar: function (v, ctx) {
        var i = Number(v.marco);
        if (!v.previsao || !p.marcos[i]) { ctx.info("efeito", '<span class="text-muted">Folga atual ' + U.esc(S.dias(p.folgaDias, true)) + "</span>"); return; }
        var delta = GI.regras.diasEntre(p.marcos[i].previsao, v.previsao);
        var ent = i === 5 ? v.previsao : v.cascata !== false ? somar(p.marcos[5].previsao, delta) : p.marcos[5].previsao;
        if (ent < v.previsao) ent = v.previsao;
        var f = GI.regras.folga(p.ros, ent);
        ctx.info("efeito", "Entrega prevista " + U.esc(F.data(ent)) + " " + S.folga(f, GI.regras.faixaFolga(f, par.folgaAlertaDias, false)) +
          (f < 0 && p.folgaDias >= 0 ? '<br><span class="text-small valor--negativo">A folga fica negativa: a ação de diligenciamento será criada na Central.</span>' : ""));
      },
      validar: function (v) {
        if (v.tipo === "realizado" && !v.realizada) return [{ campo: "realizada", msg: "Preencha este campo." }];
        if (v.tipo === "previsao" && !v.previsao) return [{ campo: "previsao", msg: "Preencha este campo." }];
        return [];
      },
      aoSalvar: function (v) {
        var d = { indice: Number(v.marco), comentario: v.comentario, anexos: v.anexos, cascata: v.cascata };
        if (v.tipo === "realizado") { d.realizada = v.realizada; d.resultado = v.resultado; d.inspetorId = v.inspetor; if (v.resultado === "Reprovado") d.previsao = v.previsao; }
        else d.previsao = v.previsao;
        return GI.api.suprimentos.atualizarMarco(p.id, d).then(function (r) {
          GI.ui.toast(r.acaoCriada ? "Marco atualizado. Folga negativa: ação criada na Central." : "Marco de " + p.numero + " atualizado.", r.acaoCriada ? "warning" : "success");
          return carregar().then(function () { if (r.riscoSugerido && r.passouACritico) registrarRisco(atual()); });
        });
      }
    });
  }
  function somar(iso, n) {
    var d = new Date(iso + "T00:00:00"); d.setDate(d.getDate() + Number(n || 0));
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  }

  function registrarRecebimento(p) {
    GI.form.abrir({
      titulo: "Registrar recebimento na obra", subtitulo: p.numero + " · " + p.descricao,
      campos: [
        { id: "data", rotulo: "Data do recebimento", tipo: "data", obrigatorio: true, valor: GI.api.referencia() },
        { id: "conferido", rotulo: "Conferência de quantidade e documentos concluída", tipo: "check", valor: true, largura: "full" },
        { id: "avarias", rotulo: "Recebido com avarias", tipo: "check", largura: "full" },
        { id: "descricaoAvarias", rotulo: "Descrição das avarias", tipo: "textarea", max: 300, mostrarSe: function (v) { return v.avarias; } },
        { id: "pendencias", rotulo: "Pendências do recebimento", tipo: "textarea", max: 300, placeholder: "Certificados, data book, sobressalentes, itens faltantes" },
        { id: "anexos", rotulo: "Romaneio, nota fiscal e fotos", tipo: "arquivo", aceitar: ["pdf", "jpg", "png"] }
      ],
      aoSalvar: function (v) {
        return GI.api.suprimentos.registrarRecebimento(p.id, v).then(function () {
          GI.ui.toast("Recebimento de " + p.numero + " registrado; entrega realizada no MAS.", "success");
          return carregar();
        });
      }
    });
  }

  function registrarRisco(p) {
    if (!p) return;
    var impacto = p.lli || p.folgaDias < -14 ? 4 : 3;
    GI.form.abrir({
      titulo: "Registrar risco sugerido", subtitulo: p.numero + " · folga " + S.dias(p.folgaDias, true) + " em relação ao ROS", tamanho: "lg",
      intro: '<p class="text-small">O risco entra no registro (05) em análise, com origem no diligenciamento. O dono define o plano de resposta na ficha do risco; o VME usa a probabilidade média da faixa.</p>',
      campos: [
        { id: "titulo", rotulo: "Risco", tipo: "texto", obrigatorio: true, max: 140, largura: "full", valor: "Atraso na entrega de " + p.descricao.toLowerCase() + " compromete a montagem" },
        { id: "p", rotulo: "Probabilidade (1 a 5)", tipo: "numero", obrigatorio: true, min: 1, maxNumero: 5, valor: 4 },
        { id: "i", rotulo: "Impacto (1 a 5)", tipo: "numero", obrigatorio: true, min: 1, maxNumero: 5, valor: impacto },
        { id: "severidade", rotulo: "Severidade", tipo: "info", html: "" },
        { id: "custo", rotulo: "Impacto em custo se ocorrer", tipo: "moeda" },
        { id: "dono", rotulo: "Dono do risco", tipo: "select", obrigatorio: true, opcoes: opcoesPessoas(), valor: p.compradorId },
        { id: "causa", rotulo: "Causa", tipo: "texto", max: 160, largura: "full", valor: "Fabricação atrasada no fornecedor " + p.fornecedor + "." },
        { id: "consequencia", rotulo: "Consequência", tipo: "texto", max: 160, largura: "full", valor: "Frente de montagem parada aguardando o equipamento; impacto no caminho crítico." },
        { id: "plano", rotulo: "Resposta proposta", tipo: "textarea", max: 300, placeholder: "Ex.: diligenciamento semanal na fábrica, embarque parcial, frete expresso" }
      ],
      aoMudar: function (v, ctx) {
        var s = v.p && v.i && paramRiscos ? GI.regras.severidade(v.p * v.i, paramRiscos, false) : null;
        ctx.info("severidade", s ? '<span class="sev sev--' + s.id + '">' + U.esc(s.nome) + "</span> " + U.esc("score " + v.p * v.i) : "");
      },
      aoSalvar: function (v) {
        return GI.api.suprimentos.registrarRisco(p.id, { titulo: v.titulo, p: v.p, i: v.i, impactoCustoCentavos: v.custo || 0,
          donoId: v.dono, causa: v.causa, consequencia: v.consequencia, plano: v.plano }).then(function (codigo) {
          GI.ui.toast("Risco " + codigo + " registrado em 05 Gestão de Riscos.", "success");
          return carregar();
        });
      }
    });
  }

  function gerarAcao(id) {
    GI.api.suprimentos.gerarAcao(Number(id)).then(function (a) {
      GI.ui.toast("Ação criada na Central: " + a.assunto + ".", "success");
      return carregar();
    }).catch(function (e) { GI.ui.toast((e && e.erros ? e.erros.join(" ") : String(e)), "warning"); });
  }

  function importar() {
    if (projetoId == null) { U.noProjeto("importar", "Importar pedidos do ERP"); return; }
    GI.importar.abrir({
      titulo: "Importar pedidos do ERP", subtitulo: "Uma linha por marco: previsão atualizada ou data realizada", arquivoModelo: "modelo-diligenciamento-erp",
      colunas: [
        { campo: "numero", titulo: "Nº do pedido", tipo: "lista", obrigatorio: true, opcoes: pedidos.map(function (p) { return p.numero; }), exemplo: pedidos[0] ? pedidos[0].numero : "" },
        { campo: "marco", titulo: "Marco", tipo: "lista", obrigatorio: true, opcoes: MARCOS, exemplo: "Embarque" },
        { campo: "previsao", titulo: "Previsão", tipo: "data", exemplo: "30/09/2026" },
        { campo: "realizada", titulo: "Realizada", tipo: "data", exemplo: "" }
      ],
      validarLinha: function (l) { return !l.previsao && !l.realizada ? ["Informe a previsão ou a data realizada."] : []; },
      aoImportar: function (linhas) {
        return GI.api.suprimentos.importarPedidos(projetoId, linhas).then(function (r) {
          carregar();
          return U.plural(r.atualizados, "marco atualizado", "marcos atualizados") + "." + (r.acoesCriadas ? " " + U.plural(r.acoesCriadas, "ação criada", "ações criadas") + " na Central por folga negativa." : "") +
            (r.falhas.length ? " " + r.falhas.join(" ") : "");
        });
      }
    });
  }

  GI.exportar.registrar(function () {
    var pj = U.projeto(projetoId), p = atual();
    var blocos = [{ tipo: "kpis", titulo: "Indicadores", itens: S.kpisExport() }, { tipo: "tabela", titulo: "Pedidos em diligenciamento", dados: tabela.exportacao() }];
    if (p) blocos.push({ tipo: "tabela", titulo: "Marcos do pedido " + p.numero, dados: tMarcos.exportacao() });
    return { titulo: "Diligenciamento e recebimento", subtitulo: pj ? pj.codigo + " " + pj.nome : "Portfólio de projetos", arquivo: "diligenciamento-" + (pj ? pj.codigo : "portfolio"), orientacao: "l", blocos: blocos };
  });

  GI.util.pronto().then(function () {
    projetoId = S.projeto(function (id) { projetoId = id; selecionado = null; carregar(); });
    var busca = document.getElementById("busca");
    busca.value = filtro.busca;
    busca.addEventListener("input", U.debounce(function () { filtro.busca = busca.value.trim(); render(); }, 200));
    document.getElementById("f-situacao").addEventListener("segmented:change", function (ev) { filtro.situacao = ev.detail.value; render(); });
    document.getElementById("btn-importar").addEventListener("click", importar);
    document.getElementById("kpis").addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-filtro]"); if (!b) return;
      var v = b.getAttribute("data-filtro"); filtro.faixa = filtro.faixa === v ? "" : v; render();
    });
    document.querySelector(".container").addEventListener("click", function (ev) {
      var g = ev.target.closest("[data-gerar-acao]"); if (g) { gerarAcao(g.getAttribute("data-gerar-acao")); return; }
      var r = ev.target.closest("[data-risco]"); if (r) { registrarRisco(pedidos.filter(function (p) { return String(p.id) === r.getAttribute("data-risco"); })[0]); return; }
      var d = ev.target.closest("[data-det]"); if (d) { if (d.getAttribute("data-det") === "marco") atualizarMarco(atual()); else registrarRecebimento(atual()); return; }
      var a = ev.target.closest("[data-abrir]");
      if (a) { selecionado = a.getAttribute("data-abrir"); render(); document.getElementById("detalhe").scrollIntoView({ behavior: "smooth", block: "start" }); }
    });

    tabela = GI.tabela.criar("tabela", {
      porPagina: 20, legenda: "Pedidos em diligenciamento", vazio: "Nenhum pedido encontrado.", ordem: { coluna: "folgaDias", direcao: "asc" },
      colunas: (projetoId == null ? [U.colunaProjeto()] : []).concat([
        { id: "numero", titulo: "Pedido", classe: "nowrap", html: function (p) { return "<b>" + U.esc(p.numero) + '</b><br><span class="text-small">' + S.linkMas(p.pacote) + "</span>"; } },
        { id: "descricao", titulo: "Descrição", html: function (p) { return '<div class="cell-title"><b>' + U.esc(p.descricao) + "</b><small>" + U.esc(p.fornecedor) + (p.lli ? " · LLI" : "") + "</small></div>"; } },
        { id: "valorCentavos", titulo: "Valor", tipo: "moeda", oculta: true },
        { id: "proximo", titulo: "Próximo marco", valor: function (p) { return p.proximoMarco ? p.proximoMarco.nome : ""; },
          html: function (p) {
            if (!p.proximoMarco) return U.badge("Entregue", "success", true);
            var m = p.proximoMarco;
            return U.esc(m.nome) + '<br><span class="text-small text-muted">' + U.esc(F.data(m.previsao)) + "</span> " + (m.situacao !== "a-vencer" ? U.badge(S.rotuloSituacao[m.situacao], TIPO_BADGE[m.situacao]) : "");
          } },
        { id: "dataContratual", titulo: "Data contratual", tipo: "data" },
        { id: "previsao", titulo: "Previsão de entrega", tipo: "data", valor: function (p) { return p.entrega || p.previsao; },
          html: function (p) { return U.esc(F.data(p.entrega || p.previsao)) + (p.atrasoContratualDias > 0 ? '<br><span class="text-small valor--negativo">' + U.esc(S.dias(p.atrasoContratualDias, true)) + " x contrato</span>" : ""); } },
        { id: "ros", titulo: "ROS", tipo: "data" },
        { id: "folgaDias", titulo: "Folga", tipo: "num", html: function (p) { return S.folga(p.folgaDias, p.faixaFolga); }, exportar: function (p) { return p.folgaDias; } },
        { id: "situacao", titulo: "Situação", valor: sit, html: function (p) { return S.situacao(sit(p)) + (p.critico ? '<br><span class="text-small ' + (p.acaoAberta ? "text-muted" : "valor--negativo") + '">' + (p.acaoAberta ? "ação na Central" : "sem ação") + "</span>" : ""); } }
      ]),
      classeLinha: function (p) { return p.numero === selecionado ? "is-selected" : p.critico ? "is-alert" : ""; },
      acoes: function (p) { return '<button type="button" class="btn btn--secondary btn--icon btn--sm" data-abrir="' + U.esc(p.numero) + '" aria-label="Abrir pedido ' + U.esc(p.numero) + '" title="Abrir pedido">' + U.icone("eye") + "</button>"; }
    });
    tMarcos = GI.tabela.criar("t-marcos", {
      porPagina: 0, compacta: true, legenda: "Marcos de fabricação do pedido", vazio: "Sem marcos.",
      colunas: [
        { id: "nome", titulo: "Marco", ordenavel: false },
        { id: "lb", titulo: "LB (contratual)", tipo: "data", ordenavel: false },
        { id: "previsao", titulo: "Previsão", tipo: "data", ordenavel: false, valor: function (m) { return m.realizada ? null : m.previsao; } },
        { id: "realizada", titulo: "Realizado", tipo: "data", ordenavel: false },
        { id: "desvio", titulo: "Desvio", tipo: "num", ordenavel: false, html: function (m) { return m.desvio ? '<span class="' + (m.desvio > 0 ? "valor--negativo" : "valor--positivo") + '">' + U.esc(S.dias(m.desvio, true)) + "</span>" : "0 d"; } },
        { id: "situacao", titulo: "Situação", ordenavel: false, valor: function (m) { return S.rotuloSituacao[m.situacao]; },
          html: function (m) { return U.badge(S.rotuloSituacao[m.situacao], TIPO_BADGE[m.situacao] || "neutral", true) + (m.situacao === "vencido" ? ' <span class="text-small valor--negativo">há ' + U.esc(S.dias(m.diasVencido)) + "</span>" : ""); } }
      ],
      classeLinha: function (m) { return m.situacao === "vencido" ? "is-alert" : ""; }
    });
    return carregar().then(function () {
      if (projetoId != null && U.acaoPendente() === "importar") importar();
    });
  });
})(window.GI = window.GI || {});
