/* ==========================================================================
   Suprimentos > MAS (Mapa de Suprimentos)
   Uma linha por pacote do plano de compras e 12 marcos do ciclo completo:
   aquisição (requisição, RFx, propostas, equalização técnica e comercial,
   aprovação, pedido/contrato) e fabricação e entrega (documentos aprovados,
   fabricação, inspeção/FAT, embarque, entrega). Cada marco mostra LB e
   previsão ou realizado, com a situação por cor, ícone e texto. Folga = ROS
   menos a previsão de entrega (serviços: ROS menos o contrato). Avanço pelo
   critério de medição dos parâmetros (pesos por marco), ponderado pelo valor.
   O MAS é só leitura: os dados vêm do plano, dos processos e do
   diligenciamento (uma fonte de verdade por dado).
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt, S = GI.sup;
  var projetoId, dados = null, visiveis = [];
  var modo = "datas", fase = "todos";
  var filtro = { busca: U.param("busca") || "", disciplina: "", tipo: "", lli: "", compradorId: "", fornecedorId: "", situacao: U.param("situacao") || "", vencidos: false, ordem: "codigo" };

  function passa(l) {
    if (filtro.disciplina && l.disciplina !== filtro.disciplina) return false;
    if (filtro.tipo && l.tipo !== filtro.tipo) return false;
    if (filtro.lli === "sim" && !l.lli) return false;
    if (filtro.lli === "nao" && l.lli) return false;
    if (filtro.compradorId && String(l.compradorId) !== String(filtro.compradorId)) return false;
    if (filtro.fornecedorId && String(l.fornecedorId) !== String(filtro.fornecedorId)) return false;
    if (filtro.situacao && l.situacao !== filtro.situacao) return false;
    if (filtro.vencidos && !l.marcosVencidos) return false;
    return U.contem([l.codigo, l.projetoCodigo, l.escopo, l.fornecedor, l.pedido, l.contrato, l.processo, l.eacCodigo].join(" "), filtro.busca);
  }
  function ordenar(a, b) {
    if (filtro.ordem === "folga") return (a.concluido - b.concluido) || ((a.folgaDias == null ? 9999 : a.folgaDias) - (b.folgaDias == null ? 9999 : b.folgaDias));
    if (filtro.ordem === "valor") return b.valorCentavos - a.valorCentavos;
    if (filtro.ordem === "avanco") return a.avancoReal - b.avancoReal;
    return a.codigo.localeCompare(b.codigo, "pt-BR", { numeric: true });
  }
  function marcosVisiveis() { return dados.marcos.filter(function (m) { return fase === "todos" || m.fase === fase; }); }

  function renderKpis() {
    var r = dados.resumo;
    var realizados = dados.linhas.reduce(function (s, l) { return s + l.marcos.filter(function (m) { return m.real; }).length; }, 0);
    document.getElementById("kpis").innerHTML = [
      U.kpi({ rotulo: "Itens no MAS", valor: F.num(r.itens), icone: "matrix", cor: "primary",
        esperado: { rotulo: "Linha de base", valor: F.num(dados.linhas.filter(function (l) { return l.marcos.some(function (m) { return m.lb; }); }).length) }, rodape: F.num(r.concluidos) + " concluídos (entregues ou contratados)",
        filtro: { valor: "", ativo: !filtro.situacao && !filtro.vencidos } }),
      U.kpi({ rotulo: "Críticos", valor: F.num(r.criticos), icone: "alertTriangle", cor: r.criticos ? "danger" : "success", esperado: { rotulo: "Esperado", valor: F.num(0) }, rodape: "folga negativa em relação ao ROS",
        filtro: { valor: "Crítico", ativo: filtro.situacao === "Crítico" } }),
      U.kpi({ rotulo: "Em atenção", valor: F.num(r.atencao), icone: "clock", cor: r.atencao ? "warning" : "success", esperado: { rotulo: "Esperado", valor: F.num(0) }, rodape: "folga pequena ou marco vencido",
        filtro: { valor: "Atenção", ativo: filtro.situacao === "Atenção" } }),
      U.kpi({ rotulo: "Marcos vencidos", valor: F.num(r.marcosVencidos), icone: "calendarClock", cor: r.marcosVencidos ? "danger" : "success", esperado: { rotulo: "Esperado", valor: F.num(0) }, rodape: "previsão passou sem realização",
        filtro: { valor: "vencidos", ativo: filtro.vencidos } }),
      U.kpi({ rotulo: "Realizados com atraso", valor: realizados ? F.num(r.marcosComAtraso / realizados * 100, 0) : "", unidade: "%", icone: "history", cor: "warning",
        esperado: { rotulo: "Esperado", valor: F.pct(0, 0) }, rodape: F.num(r.marcosComAtraso) + " de " + F.num(realizados) + " marcos realizados depois da LB" }),
      U.kpi({ rotulo: "Avanço de suprimentos", valor: F.num(r.avancoReal, 1), unidade: "%", icone: "trendingUp", cor: r.indice >= 1 ? "success" : r.indice >= 0.95 ? "warning" : "danger",
        esperado: { rotulo: "Linha de base", valor: F.pct(r.avancoPrevisto) }, rodape: "índice " + F.indice(r.indice), href: U.tela("suprimentos", "painel", { projeto: projetoId }) })
    ].join("");
  }

  function renderChips() {
    var c = [];
    if (filtro.situacao) c.push({ c: "situacao", t: "Situação: " + filtro.situacao });
    if (filtro.vencidos) c.push({ c: "vencidos", t: "Com marco vencido" });
    if (filtro.disciplina) c.push({ c: "disciplina", t: "Disciplina: " + filtro.disciplina });
    if (filtro.tipo) c.push({ c: "tipo", t: "Tipo: " + filtro.tipo });
    if (filtro.lli) c.push({ c: "lli", t: filtro.lli === "sim" ? "Só LLI" : "Sem LLI" });
    if (filtro.compradorId) c.push({ c: "compradorId", t: "Comprador: " + U.pessoa(filtro.compradorId) });
    if (filtro.fornecedorId) c.push({ c: "fornecedorId", t: "Fornecedor: " + U.empresa(filtro.fornecedorId) });
    if (filtro.busca) c.push({ c: "busca", t: "Busca: " + filtro.busca });
    var el = document.getElementById("chips");
    el.hidden = !c.length;
    el.innerHTML = c.length ? '<span class="filter-bar__label">Filtros ativos:</span>' + c.map(function (x) {
      return '<span class="chip"><span class="chip__label">' + U.esc(x.t) + '</span><button type="button" class="chip__remove" data-limpar="' + x.c + '" aria-label="Remover filtro ' + U.esc(x.t) + '">' + U.icone("x") + "</button></span>";
    }).join("") : "";
  }

  function celulaPacote(l) {
    var refs = [l.processo ? '<a href="' + U.tela("suprimentos", "processos", { pacote: l.codigo }) + '">' + U.esc(l.processo) + "</a>" : "",
      l.pedido ? S.linkPedido(l.pedido) : "", l.contrato ? S.linkContrato(l.contrato) : ""].filter(Boolean).join(" · ");
    return '<div class="mas__pacote"><b>' + U.esc(l.codigo) + "</b>" + (projetoId == null ? " " + U.selosProjeto([l.projetoId]) : "") + '<small>' + U.esc(l.escopo) + "</small>" +
      '<span class="mas__selos">' + U.badge(l.tipo, "neutral") + (l.lli ? U.badge("LLI", "purple") : "") + "</span>" +
      (refs ? '<small>' + refs + "</small>" : "") + "</div>";
  }

  function render() {
    renderKpis(); renderChips();
    var ms = marcosVisiveis();
    visiveis = dados.linhas.filter(passa).sort(ordenar);
    var nAq = ms.filter(function (m) { return m.fase === "aquisicao"; }).length, nFab = ms.length - nAq;
    document.getElementById("sub-mas").textContent = U.plural(visiveis.length, "pacote") + " · data de referência " + F.data(dados.referencia) +
      " · célula: " + (modo === "datas" ? "data realizada ou prevista e LB abaixo" : "desvio em dias em relação à LB") + " · clique na célula para o detalhe do item";
    var cab1 = '<tr><th scope="col" rowspan="2" class="mas__fixa">Pacote</th><th scope="col" rowspan="2">Fornecedor e valor</th>' +
      (nAq ? '<th scope="colgroup" colspan="' + nAq + '" class="mas__grupo mas__grupo--aq">Aquisição</th>' : "") +
      (nFab ? '<th scope="colgroup" colspan="' + nFab + '" class="mas__grupo">Fabricação e entrega</th>' : "") +
      '<th scope="col" rowspan="2">ROS</th><th scope="col" rowspan="2">Previsão de entrega</th><th scope="col" rowspan="2">Folga</th><th scope="col" rowspan="2">Avanço</th><th scope="col" rowspan="2">Situação</th></tr>';
    var cab2 = "<tr>" + ms.map(function (m, k) {
      var inicio = k === 0 || m.fase !== ms[k - 1].fase;
      return '<th scope="col" class="mas__marco-th' + (inicio ? " mas__inicio-fase" : "") + '">' + U.esc(m.nome) + '<br><span class="text-muted">' + F.num(m.peso) + "%</span></th>";
    }).join("") + "</tr>";
    var corpo = visiveis.length ? visiveis.map(function (l) {
      var cels = ms.map(function (mm, k) {
        var m = l.marcos.filter(function (x) { return x.id === mm.id; })[0];
        var inicio = k === 0 || mm.fase !== ms[k - 1].fase;
        return '<td class="' + (inicio ? "mas__inicio-fase" : "") + '">' + S.marco(m, modo, m.situacao === "na" ? null : 'data-linha="' + l.id + '" data-marco="' + m.id + '"') + "</td>";
      }).join("");
      return '<tr class="' + (l.situacao === "Crítico" ? "is-alert" : "") + '"><th scope="row" class="mas__fixa">' + celulaPacote(l) + "</th>" +
        "<td>" + (l.fornecedor ? "<b>" + U.esc(l.fornecedor) + "</b><br>" : '<span class="text-muted">em contratação</span><br>') +
        '<span class="text-small num">' + U.esc(F.moedaCompacta(l.valorCentavos)) + "</span>" + (l.adjudicadoCentavos == null ? ' <span class="text-small text-muted">estimado</span>' : "") + "</td>" +
        cels + '<td class="nowrap">' + U.esc(F.data(l.ros)) + '</td><td class="nowrap">' + U.esc(F.data(l.dataFolga)) + "</td><td>" + S.folga(l.folgaDias, l.faixaFolga) + "</td>" +
        '<td><div class="progress-row"><div class="progress progress--sm" role="progressbar" aria-valuenow="' + l.avancoReal + '" aria-valuemin="0" aria-valuemax="100" aria-label="Avanço real">' +
        '<span class="progress__bar" style="--value: ' + l.avancoReal + '%"></span></div><span class="num text-small">' + F.pct(l.avancoReal, 0) + "</span></div>" +
        '<span class="text-small text-muted">LB ' + F.pct(l.avancoPrevisto, 0) + "</span></td>" +
        "<td>" + S.situacao(l.situacao) + '<br><span class="text-small text-muted">' + U.esc(l.etapaAtual) + "</span></td></tr>";
    }).join("") : '<tr class="table__empty"><td colspan="' + (ms.length + 7) + '">' + U.vazio("Nenhum pacote no filtro atual.", "search") + "</td></tr>";
    /* Rodapé: realizados x previstos na LB até a data de referência, por marco */
    var ref = dados.referencia;
    var rodape = visiveis.length ? '<tfoot><tr class="row--total"><th scope="row" class="mas__fixa">Realizados / previstos na LB até hoje</th><td></td>' + ms.map(function (mm, k) {
      var ap = visiveis.map(function (l) { return l.marcos.filter(function (x) { return x.id === mm.id; })[0]; }).filter(function (m) { return m.situacao !== "na"; });
      var prev = ap.filter(function (m) { return m.lb && m.lb <= ref; }).length, real = ap.filter(function (m) { return m.real; }).length;
      return '<td class="num' + (k === 0 || mm.fase !== ms[k - 1].fase ? " mas__inicio-fase" : "") + '"><b class="' + (real < prev ? "valor--negativo" : "") + '">' + F.num(real) + "</b> / " + F.num(prev) + "</td>";
    }).join("") + "<td></td><td></td><td></td><td></td><td></td></tr></tfoot>" : "";
    document.getElementById("grade").innerHTML = '<div class="table-wrap"><table class="table table--compact mas" aria-describedby="sub-mas">' +
      '<caption class="sr-only">Mapa de Suprimentos: marcos de aquisição, fabricação e entrega por pacote</caption><thead>' + cab1 + cab2 + "</thead><tbody>" + corpo + "</tbody>" + rodape + "</table></div>";
  }

  function carregar() {
    return GI.api.suprimentos.mas(projetoId).then(function (r) {
      dados = r;
      document.getElementById("legenda").innerHTML = S.legenda();
      render();
    });
  }

  var TIPO_BADGE = { prazo: "success", atraso: "danger", vencido: "danger", "previsto-atraso": "warning", "a-vencer": "neutral", "sem-data": "neutral", na: "neutral" };
  /* Detalhe do item: todos os marcos com LB, previsão, realizado e desvio */
  function detalhe(id, marcoId) {
    var l = dados.linhas.filter(function (x) { return String(x.id) === String(id); })[0];
    if (!l) return;
    var linhas = l.marcos.map(function (m) {
      return '<tr' + (m.id === marcoId ? ' class="is-selected"' : "") + "><td>" + U.esc(m.nome) + (m.estimada ? ' <span class="text-small text-muted">(LB estimada)</span>' : "") + '</td><td class="num">' + F.num(m.pesoPct, 1) + "%</td>" +
        '<td class="nowrap">' + U.esc(F.data(m.lb)) + '</td><td class="nowrap">' + U.esc(m.real ? "" : F.data(m.previsao)) + '</td><td class="nowrap">' + U.esc(F.data(m.real)) + "</td>" +
        '<td class="num">' + U.esc(m.situacao === "na" ? "" : m.desvio ? S.dias(m.desvio, true) : "0 d") + "</td><td>" + U.badge(S.rotuloSituacao[m.situacao], TIPO_BADGE[m.situacao] || "neutral", true) + "</td></tr>";
    }).join("");
    var links = [
      l.processo ? '<a class="btn btn--secondary btn--sm" href="' + U.tela("suprimentos", "processos", { pacote: l.codigo }) + '">' + U.icone("fileSearch") + "Processo " + U.esc(l.processo) + "</a>" : "",
      l.pedido ? '<a class="btn btn--secondary btn--sm" href="' + U.tela("suprimentos", "diligenciamento", { pedido: l.pedido }) + '">' + U.icone("truck") + "Diligenciamento " + U.esc(l.pedido) + "</a>" : "",
      l.contrato ? '<a class="btn btn--secondary btn--sm" href="' + U.tela("financeiro", "contrato", { numero: l.contrato }) + '">' + U.icone("fileContract") + "Contrato " + U.esc(l.contrato) + "</a>" : "",
      '<a class="btn btn--ghost btn--sm" href="' + U.tela("suprimentos", "plano-compras", { busca: l.codigo }) + '">' + U.icone("listChecks") + "Plano de compras</a>"
    ].join("");
    var corpo = document.createElement("div");
    corpo.innerHTML = '<dl class="dl"><dt>Item da EAC</dt><dd>' + U.esc(l.eacCodigo ? l.eacCodigo + " " + l.eacDescricao : "sem EAC") + "</dd><dt>Fornecedor</dt><dd>" + U.esc(l.fornecedor || "em contratação") +
      "</dd><dt>Valor</dt><dd>" + U.esc(F.moeda(l.valorCentavos)) + (l.adjudicadoCentavos == null ? " (estimado)" : "") + "</dd><dt>Comprador</dt><dd>" + U.esc(U.pessoa(l.compradorId)) +
      "</dd><dt>ROS e folga</dt><dd>" + U.esc(F.data(l.ros)) + " " + S.folga(l.folgaDias, l.faixaFolga) + "</dd><dt>Avanço</dt><dd>" + U.esc("real " + F.pct(l.avancoReal) + " · previsto na LB " + F.pct(l.avancoPrevisto)) + "</dd></dl>" +
      '<div class="table-wrap mt-4"><table class="table table--compact"><caption class="sr-only">Marcos do pacote</caption><thead><tr><th scope="col">Marco</th><th scope="col" class="num">Peso</th><th scope="col">LB</th><th scope="col">Previsão</th><th scope="col">Realizado</th><th scope="col" class="num">Desvio</th><th scope="col">Situação</th></tr></thead><tbody>' +
      linhas + '</tbody></table></div><div class="btn-group mt-4">' + links + "</div>";
    GI.modal.create({ title: l.codigo + " " + l.escopo, subtitle: l.tipo + " · " + l.disciplina + " · " + l.situacao, size: "xl", body: corpo, buttons: [{ label: "Fechar", variant: "secondary" }] });
  }

  function abrirFiltros() {
    var pessoas = {}, fornecedores = {};
    dados.linhas.forEach(function (l) { pessoas[l.compradorId] = true; if (l.fornecedorId) fornecedores[l.fornecedorId] = true; });
    GI.form.abrir({
      titulo: "Filtros do MAS", textoSalvar: "Aplicar",
      campos: [
        { id: "disciplina", rotulo: "Disciplina", tipo: "select", opcoes: S.DISCIPLINAS, valor: filtro.disciplina, vazio: "Todas" },
        { id: "tipo", rotulo: "Tipo", tipo: "select", opcoes: S.TIPOS, valor: filtro.tipo, vazio: "Todos" },
        { id: "lli", rotulo: "Longo prazo de entrega (LLI)", tipo: "select", opcoes: [{ valor: "sim", texto: "Só LLI" }, { valor: "nao", texto: "Sem LLI" }], valor: filtro.lli, vazio: "Todos" },
        { id: "situacao", rotulo: "Situação", tipo: "select", opcoes: S.SITUACOES_LINHA, valor: filtro.situacao, vazio: "Todas" },
        { id: "comprador", rotulo: "Comprador", tipo: "select", opcoes: Object.keys(pessoas).map(function (k) { return { valor: k, texto: U.pessoa(k) }; }), valor: filtro.compradorId, vazio: "Todos" },
        { id: "fornecedor", rotulo: "Fornecedor", tipo: "select", opcoes: Object.keys(fornecedores).map(function (k) { return { valor: k, texto: U.empresa(k) }; }), valor: filtro.fornecedorId, vazio: "Todos" },
        { id: "ordem", rotulo: "Ordenar por", tipo: "select", opcoes: [{ valor: "codigo", texto: "Código do pacote" }, { valor: "folga", texto: "Folga (menor primeiro)" },
          { valor: "valor", texto: "Valor (maior primeiro)" }, { valor: "avanco", texto: "Avanço (menor primeiro)" }], valor: filtro.ordem, vazio: "Código do pacote" },
        { id: "vencidos", rotulo: "Só pacotes com marco vencido", tipo: "check", valor: filtro.vencidos }
      ],
      aoSalvar: function (v) {
        filtro.disciplina = v.disciplina; filtro.tipo = v.tipo; filtro.lli = v.lli; filtro.situacao = v.situacao;
        filtro.compradorId = v.comprador; filtro.fornecedorId = v.fornecedor; filtro.ordem = v.ordem || "codigo"; filtro.vencidos = v.vencidos;
        render();
      }
    });
  }

  /* Exportação: Excel com LB, previsão/realizado e situação de cada marco; PDF A3 paisagem com as células coloridas */
  var COR = { prazo: { fundo: "status-success-bg", texto: "status-success-fg" }, atraso: { fundo: "status-danger-bg", texto: "status-danger-fg" },
    vencido: { fundo: "status-danger-solid", texto: "text-inverse" }, "previsto-atraso": { fundo: "status-warning-bg", texto: "status-warning-fg" },
    na: { fundo: "status-neutral-bg", texto: "status-neutral-fg" } };
  var ABREV = { prazo: "no prazo", atraso: "com atraso", vencido: "vencido", "previsto-atraso": "previsão após LB", "a-vencer": "a vencer", "sem-data": "sem data", na: "N/A" };
  function marcoDe(l, id) { return l.marcos.filter(function (x) { return x.id === id; })[0]; }
  GI.exportar.registrar(function (tipo) {
    var p = U.projeto(projetoId), ms = marcosVisiveis();
    var base = (projetoId == null ? [{ titulo: "Projeto", tipo: "texto", v: function (l) { return U.codigoProjeto(l.projetoId); } }] : []).concat([
      { titulo: "Pacote", tipo: "texto", v: function (l) { return l.codigo; } }, { titulo: "Escopo", tipo: "texto", v: function (l) { return l.escopo; } }
    ]);
    var fim = [
      { titulo: "ROS", tipo: "data", v: function (l) { return l.ros; } }, { titulo: "Previsão de entrega", tipo: "data", v: function (l) { return l.dataFolga; } },
      { titulo: "Folga (dias)", tipo: "num", v: function (l) { return l.folgaDias; } }, { titulo: "Avanço real (%)", tipo: "pct", v: function (l) { return l.avancoReal; } },
      { titulo: "Avanço LB (%)", tipo: "pct", v: function (l) { return l.avancoPrevisto; } }, { titulo: "Situação", tipo: "texto", v: function (l) { return l.situacao; } }
    ];
    var cols, corCelula = null, idxMarco = {};
    if (tipo === "pdf") {
      cols = base.concat([{ titulo: "Fornecedor", tipo: "texto", v: function (l) { return l.fornecedor || "em contratação"; } }]);
      ms.forEach(function (mm) {
        idxMarco[cols.length] = mm.id;
        cols.push({ titulo: mm.nome, tipo: "texto", v: function (l) {
          var m = marcoDe(l, mm.id);
          if (m.situacao === "na") return "N/A";
          if (m.situacao === "sem-data") return "";
          return S.dataCurta(m.real || m.previsao || m.lb) + (m.desvio ? " (" + S.dias(m.desvio, true) + ")" : "") + (m.situacao === "vencido" ? " vencido" : "");
        } });
      });
      cols = cols.concat(fim.filter(function (c) { return c.titulo !== "Avanço LB (%)"; }));
      corCelula = function (i, j) { var id = idxMarco[j]; if (!id) return null; var m = marcoDe(visiveis[i], id); return COR[m.situacao] || null; };
    } else {
      cols = base.concat([
        { titulo: "Tipo", tipo: "texto", v: function (l) { return l.tipo; } }, { titulo: "Disciplina", tipo: "texto", v: function (l) { return l.disciplina; } },
        { titulo: "LLI", tipo: "texto", v: function (l) { return l.lli ? "Sim" : "Não"; } }, { titulo: "Item da EAC", tipo: "texto", v: function (l) { return l.eacCodigo || ""; } },
        { titulo: "Fornecedor", tipo: "texto", v: function (l) { return l.fornecedor; } }, { titulo: "Comprador", tipo: "texto", v: function (l) { return U.pessoa(l.compradorId); } },
        { titulo: "Estimativa", tipo: "moeda", v: function (l) { return l.estimativaCentavos; } }, { titulo: "Adjudicado", tipo: "moeda", v: function (l) { return l.adjudicadoCentavos; } }
      ]);
      ms.forEach(function (mm) {
        cols.push({ titulo: mm.nome + " LB", tipo: "data", v: function (l) { return marcoDe(l, mm.id).lb; } });
        cols.push({ titulo: mm.nome + " previsão ou real", tipo: "data", v: function (l) { var m = marcoDe(l, mm.id); return m.real || m.previsao; } });
        cols.push({ titulo: mm.nome + " situação", tipo: "texto", v: function (l) { var m = marcoDe(l, mm.id); return ABREV[m.situacao] + (m.desvio ? " " + S.dias(m.desvio, true) : ""); } });
      });
      cols = cols.concat([{ titulo: "Processo", tipo: "texto", v: function (l) { return l.processo || ""; } }, { titulo: "Pedido ou contrato", tipo: "texto", v: function (l) { return l.pedido || l.contrato || ""; } }], fim);
    }
    var dadosTab = {
      colunas: cols.map(function (c) { return { titulo: c.titulo, tipo: c.tipo }; }),
      bruto: visiveis.map(function (l) { return cols.map(function (c) { return c.v(l); }); }),
      texto: visiveis.map(function (l) { return cols.map(function (c) { var v = c.v(l); return v == null ? "" : GI.tabela.formatar({ tipo: c.tipo, casas: c.tipo === "pct" ? 1 : 0 }, v); }); })
    };
    var legenda = "Situação dos marcos: no prazo = realizado até a LB; com atraso = realizado depois da LB; vencido = previsão passou sem realização; previsão após LB = previsão futura depois da linha de base; N/A = não se aplica ao tipo do pacote. Desvio em dias em relação à LB. Folga = ROS menos a previsão de entrega.";
    return {
      titulo: "Mapa de Suprimentos (MAS)", subtitulo: p ? p.codigo + " " + p.nome : "Portfólio de projetos", arquivo: "mas-" + (p ? p.codigo : "portfolio"), orientacao: "l", formato: tipo === "pdf" ? "a3" : "a4",
      blocos: [
        { tipo: "kpis", titulo: "Resumo", itens: S.kpisExport() },
        { tipo: "tabela", titulo: "Mapa de Suprimentos", dados: dadosTab, corCelula: corCelula, fonte: tipo === "pdf" ? 6.5 : null },
        { tipo: "texto", titulo: "Legenda", texto: legenda }
      ]
    };
  });

  GI.util.pronto().then(function () {
    projetoId = S.projeto(function (id) { projetoId = id; carregar(); });
    var busca = document.getElementById("busca");
    busca.value = filtro.busca;
    busca.addEventListener("input", U.debounce(function () { filtro.busca = busca.value.trim(); render(); }, 200));
    document.getElementById("btn-filtros").addEventListener("click", abrirFiltros);
    document.getElementById("f-modo").addEventListener("segmented:change", function (ev) { modo = ev.detail.value; render(); });
    document.getElementById("f-fase").addEventListener("segmented:change", function (ev) { fase = ev.detail.value; render(); });
    document.getElementById("kpis").addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-filtro]");
      if (!b) return;
      var v = b.getAttribute("data-filtro");
      if (v === "vencidos") { filtro.vencidos = !filtro.vencidos; filtro.situacao = ""; }
      else if (!v) { filtro.situacao = ""; filtro.vencidos = false; }
      else { filtro.situacao = filtro.situacao === v ? "" : v; filtro.vencidos = false; }
      render();
    });
    document.getElementById("chips").addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-limpar]");
      if (!b) return;
      var c = b.getAttribute("data-limpar");
      filtro[c] = c === "vencidos" ? false : "";
      if (c === "busca") busca.value = "";
      render();
    });
    document.getElementById("grade").addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-linha]");
      if (b) detalhe(b.getAttribute("data-linha"), b.getAttribute("data-marco"));
    });
    return carregar();
  });
})(window.GI = window.GI || {});
