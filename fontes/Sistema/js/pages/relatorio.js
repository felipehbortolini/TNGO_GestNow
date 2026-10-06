/* ==========================================================================
   relatorio.js | Início > Relatório gerencial (semanal ou mensal)
   URL: relatorio.html?escopo=portfolio|<id>&tipo=Semanal|Mensal&periodo=2026-S38|2026-08&secoes=planejamento,financeiro,suprimentos,riscos,hse
   escopo: portfolio (carteira consolidada, com folha própria da carteira) ou id do projeto (mesmo formato
   do relatório por projeto). Usa escopo= e não projeto= para não trocar o escopo global das telas.
   Folhas A4 na horizontal: Planejamento em duas (Curva S, KPIs e produtividade; análise e relato
   do período), Financeiro, Suprimentos, Riscos, Qualidade e HSE em uma cada. Cada folha traz a análise do
   período do módulo (texto executivo e tabela de desvios negativos com o comentário de cada um).
   Dados só via GI.api.relatorioGerencial (regras de corte na api). Imprimir usa a impressão do
   navegador (Salvar como PDF).
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt;
  var esc = function (t) { return U.esc(t); };
  var dados = null;
  /* Referências dos cards (valor esperado) que não vêm no relatório: parâmetros, mapa de controle (orçado),
     contingência (limite de consumo e saldo) e registro de riscos (total cadastrado). Carregadas junto. */
  var ref = {};
  var LETRA_AMEACA = GI.i18n && GI.i18n.idioma === "en" ? "T" : "A";   /* matriz: A = ameaça (T = threat), O = oportunidade */

  /* ---------------- Formatação ---------------- */
  function pct(v, casas) { return v == null ? "·" : F.pct(v, casas == null ? 1 : casas); }
  function pp(v) { return v == null ? "·" : (v > 0 ? "+" : v < 0 ? "−" : "") + F.num(Math.abs(v), 1); }
  function indice(v) { return v == null ? "·" : F.indice(v); }
  function corIndice(v) { return v == null ? "info" : v >= 1 ? "success" : v >= 0.95 ? "warning" : "danger"; }
  function dataCurta(iso) { return iso ? F.data(iso) : "·"; }
  function mes(m) { return U.mesCurto(m); }
  /* Valores esperados (texto simples: esperadoRel escapa) */
  var META_INDICE = "≥ " + F.indice(1);
  function zero() { return F.num(0); }
  function deCadastrados(n) { return n == null ? "·" : "de " + F.num(n) + " cadastrados"; }
  function deRegistrados(n) { return n == null ? "·" : "de " + F.num(n) + " registrados"; }
  function minimo(v, casas) { return v == null ? "·" : "≥ " + F.pct(v, casas == null ? 0 : casas); }
  var ESP_ZERO = { rotulo: "Esperado", valor: "0" };
  /* Meta por faixa de severidade (mesma regra do registro de riscos): severidade-alvo do plano ou, sem plano, a atual */
  function metaSeveridade(id) {
    if (!ref.riscos) return "·";
    return F.num(ref.riscos.filter(function (r) { var a = r.temPlano && r.severidadeAlvo ? r.severidadeAlvo : r.sevAtual ? r.sevAtual.id : null; return r.ativo && a === id; }).length);
  }
  function diasEntre(a, b) {
    if (!a || !b) return null;
    var d = function (iso) { var x = iso.slice(0, 10).split("-"); return Date.UTC(+x[0], +x[1] - 1, +x[2]); };
    return Math.max(0, Math.round((d(b) - d(a)) / 86400000));
  }
  function moedaRef(c) { return c == null ? "·" : F.moedaCompacta(c); }
  function faixasDesvioPP() { var e = ref.par && ref.par.eap; return e && e.faixasDesvioPP ? e.faixasDesvioPP : [2, 5]; }
  function mesesEntre(a, b) { if (!a || !b) return null; return (Number(b.slice(0, 4)) - Number(a.slice(0, 4))) * 12 + Number(b.slice(5, 7)) - Number(a.slice(5, 7)) + 1; }
  function nomeTipo() { return dados.periodo.tipo === "Semanal" ? "semanal" : "mensal"; }

  function kpi(o) {
    return '<div class="rel-kpi rel-kpi--' + (o.cor || "info") + '"' + (o.id ? ' id="' + esc(o.id) + '"' : "") + '><span class="rel-kpi__rotulo">' + esc(o.rotulo) + '</span><span class="rel-kpi__valor">' + o.valor +
      (o.unidade ? "<small>" + esc(o.unidade) + "</small>" : "") + "</span>" + esperadoRel(o.esperado) + '<span class="rel-kpi__rodape">' + (o.rodape || "&nbsp;") + "</span></div>";
  }
  /* Referência do valor (previsto, meta, linha de base, limite), mesma regra dos cards das telas */
  function esperadoRel(e) {
    if (!e) return "";
    var l = Array.isArray(e) ? e : [e];
    return '<span class="rel-kpi__esperado">' + l.filter(Boolean).map(function (x) { return "<span>" + esc(x.rotulo) + " <b>" + esc(x.valor == null || x.valor === "" ? "·" : x.valor) + "</b></span>"; }).join(" ") + "</span>";
  }
  function kpiMoeda(o) {
    var mp = F.moedaPartes(o.centavos, o.sinal);
    o.valor = "<small>" + esc(mp.moeda) + "</small>" + esc(mp.numero);
    o.unidade = mp.escala;
    return kpi(o);
  }
  function tabela(colunas, linhas, opcoes) {
    var o = opcoes || {};
    if (!linhas.length) return '<p class="rel-vazio">' + esc(o.vazio || "Sem registros.") + "</p>";
    var vis = o.limite ? linhas.slice(0, o.limite) : linhas;
    return '<table class="rel-tabela' + (o.classe ? " " + o.classe : "") + '"><caption class="sr-only">' + esc(o.legenda || "") + "</caption><thead><tr>" + colunas.map(function (c) {
      return '<th scope="col"' + (c.num ? ' class="num"' : "") + ">" + esc(c.titulo) + "</th>";
    }).join("") + "</tr></thead><tbody>" + vis.map(function (l) {
      return "<tr" + (l._classe ? ' class="' + l._classe + '"' : "") + ">" + colunas.map(function (c) {
        return "<td" + (c.num ? ' class="num"' : c.nowrap ? ' class="nowrap"' : "") + ">" + c.html(l) + "</td>";
      }).join("") + "</tr>";
    }).join("") + "</tbody></table>" + (vis.length < linhas.length ? '<span class="rel-mais">+ ' + (linhas.length - vis.length) + " no módulo</span>" : "");
  }
  function sev(s, score, natureza) {
    if (!s) return '<span class="rel-nota">não avaliado</span>';
    return '<span class="sev sev--' + esc(s.id) + (natureza === "Oportunidade" ? " sev--op" : "") + '"><b>' + score + "</b> " + esc(s.nome) + "</span>";
  }
  function natureza(n) { return U.badge(n, n === "Oportunidade" ? "success" : "warning", true); }
  function calor(desvioPct, faixa) {
    if (desvioPct == null) return "·";
    return '<span class="heat heat--' + esc(faixa || "neutro") + '">' + (desvioPct > 0 ? "+" : "") + F.num(desvioPct, 1) + "%</span>";
  }
  function mil(c) { return c == null ? "·" : F.num(c / 100000, 0); }
  function portfolio() { return !!(dados && dados.portfolio); }
  /* Links para registrar análise ou relato: abrem a tela no mesmo escopo do relatório */
  function qEscopo() { return "&projeto=" + (portfolio() ? "portfolio" : encodeURIComponent(dados.projeto.id)); }

  /* ---------------- Análise do período (bloco comum às folhas) ---------------- */
  var ONDE_ANALISE = {
    planejamento: ["modulos/planejamento/relato.html", "02 Planejamento > Relato do período"],
    financeiro: ["modulos/financeiro/kpis.html", "03 Gestão Financeira > KPIs de custo"],
    suprimentos: ["modulos/suprimentos/painel.html", "04 Suprimentos > Painel de suprimentos"],
    riscos: ["modulos/riscos/painel.html", "05 Gestão de Riscos > Painel de riscos"],
    qualidade: ["modulos/qualidade/painel.html", "06 Gestão da Qualidade > Painel"],
    hse: ["modulos/hse/painel.html", "07 HSE > Painel HSE"]
  };
  function paragrafos(t) {
    return String(t || "").split(/\r?\n+/).map(function (x) { return x.trim(); }).filter(Boolean).map(function (x) { return "<p>" + esc(x) + "</p>"; }).join("");
  }
  function blocoAnalise(modulo, o) {
    o = o || {};
    var a = dados.analises ? dados.analises[modulo] : null;
    if (!a) return "";
    var reg = a.registro, onde = ONDE_ANALISE[modulo];
    var url = onde[0] + "?analise=1&tipo=" + encodeURIComponent(dados.periodo.tipo) + "&periodo=" + encodeURIComponent(dados.periodo.periodo) + qEscopo();
    var pend = a.obrigatorio && a.pendentes ? ' · <span class="valor--negativo">' + esc(U.plural(a.pendentes, "desvio sem comentário", "desvios sem comentário")) + "</span>" : "";
    var html = '<h3 class="rel-bloco__titulo">Análise do período <small>' + (reg ? "desvio e tendência · " + esc(F.data(reg.atualizadoEm.slice(0, 10)) + " por " + U.pessoa(reg.atualizadoPorId)) : "desvio e tendência") + pend + "</small></h3>";
    html += reg ? '<div class="rel-analise">' + paragrafos(reg.analise) + "</div>"
      : '<div class="rel-alerta"><b>Análise ' + nomeTipo() + " do período não registrada.</b> Registre em " + esc(onde[1]) + " (botão Análise do período)" +
        ' <a class="no-print" href="' + esc(url) + '">(registrar agora)</a> e emita o relatório de novo.</div>';
    if (a.desvios.length) {
      html += tabela([
        { titulo: "Desvio negativo", html: function (d) { return "<b>" + esc(d.indicador) + '</b><br><span class="valor--negativo">' + esc(GI.analise.textoDesvio(d)) + "</span>"; } },
        { titulo: "Comentário", html: function (d) { return d.comentario ? esc(d.comentario) : '<span class="valor--negativo">' + (a.obrigatorio ? "Comentário pendente" : "Sem comentário") + "</span>"; } }
      ], a.desvios, { legenda: "Desvios negativos do período e comentários", classe: "rel-tabela--desvios" });
    } else if (a.obrigatorio) html += '<p class="rel-vazio">Nenhum desvio negativo no período.</p>';
    return '<div class="rel-bloco rel-bloco--analise">' + html + "</div>";
  }

  /* ---------------- Folha ---------------- */
  function cabecalho() {
    var p = dados.projeto || {}, per = dados.periodo;
    return '<header class="folha__cabecalho">' +
      '<img class="folha__logo" src="assets/logos/timenow-horizontal.png" alt="Timenow">' +
      '<div class="folha__titulo"><b>Relatório gerencial ' + nomeTipo() + "</b><span>" + esc(per.rotulo) +
        (per.emAndamento ? " · parcial, dados até " + esc(F.data(dados.referencia)) : "") + "</span></div>" +
      '<div class="folha__projeto"><b>' + esc(portfolio() ? p.nome + " · " + U.plural(p.projetos, "projeto") : p.codigo + " · " + p.nome) + "</b>Emitido em " + esc(F.data(dados.referencia)) + " (data de referência) por " + esc(dados.emitidoPor) + "</div></header>";
  }
  function folha(o) {
    return '<section class="folha" style="--acento: var(' + o.acento + ')" aria-label="' + esc(o.secao) + '">' + cabecalho() +
      '<h2 class="folha__secao">' + esc(o.secao) + (o.sub ? " <small>" + esc(o.sub) + "</small>" : "") + "</h2>" +
      '<div class="folha__corpo">' + o.corpo + "</div>" +
      '<footer class="folha__rodape"><span>Gestão Integrada AMT · protótipo com dados fictícios</span><span>' + esc(o.nota || "") + '</span><span data-pagina></span></footer></section>';
  }

  /* ---------------- Portfólio: carteira de projetos ---------------- */
  var SAUDE = { success: ["Em dia", "success"], warning: ["Atenção", "warning"], danger: ["Crítico", "danger"] };
  function folhaCarteira() {
    var c = dados.carteira, t = c.total, sobre = t.vac < 0;
    var kpis = '<div class="rel-kpis">' + [
      kpi({ rotulo: "Projetos na carteira", valor: F.num(t.projetos), cor: "info", esperado: { rotulo: "Referência", valor: deCadastrados(c.projetos.length) }, rodape: "ponderação composta configurável" }),
      kpiMoeda({ rotulo: "Orçamento da carteira (BAC)", centavos: t.bac, cor: "previsto", esperado: { rotulo: "Linha de base", valor: moedaRef(ref.mapa ? ref.mapa.total.base : null) }, rodape: "soma das EAC vigentes" }),
      kpi({ rotulo: "Avanço ponderado", valor: pct(t.real), cor: "real", esperado: { rotulo: "Previsto", valor: pct(t.previsto) }, rodape: "desvio " + (t.desvioPP < 0 ? '<span class="valor--negativo">' + pp(t.desvioPP) + " p.p.</span>" : pp(t.desvioPP) + " p.p.") }),
      kpi({ rotulo: "SPI físico ponderado", valor: indice(t.spi), cor: corIndice(t.spi), esperado: { rotulo: "Meta", valor: META_INDICE }, rodape: "término " + esc(t.terminoTendencia ? mes(t.terminoTendencia) : "·") + " x LB " + esc(t.terminoBaseline ? mes(t.terminoBaseline) : "·") }),
      kpi({ rotulo: "CPI da carteira", valor: indice(t.cpi), cor: corIndice(t.cpi), esperado: { rotulo: "Meta", valor: META_INDICE }, rodape: "EV ÷ AC somados dos projetos" }),
      kpiMoeda({ rotulo: "Projeção no término", centavos: t.projecaoTermino, cor: sobre ? "danger" : "success", esperado: { rotulo: "Orçado", valor: moedaRef(t.bac) },
        rodape: '<span class="' + (sobre ? "valor--sobrecusto" : "valor--economia") + '">' + (sobre ? "+" : "−") + esc(F.moedaCompacta(Math.abs(t.vac))) + "</span> x orçamento" })
    ].join("") + "</div>";
    var linhas = c.projetos.concat([Object.assign({ _classe: "rel-total", _total: true, codigo: "Carteira", nome: "", peso: 100 }, t)]);
    var tab = tabela([
      { titulo: "Projeto", html: function (x) { return x._total ? "<b>Total da carteira</b>" : "<b>" + esc(x.codigo) + "</b><br>" + esc(x.nome); } },
      { titulo: "Peso", num: true, html: function (x) { return pct(x.peso, 1); } },
      { titulo: "BAC (R$ mil)", num: true, html: function (x) { return mil(x.bac); } },
      { titulo: "Previsto", num: true, html: function (x) { return pct(x.previsto); } },
      { titulo: "Real", num: true, html: function (x) { return pct(x.real); } },
      { titulo: "SPI", num: true, html: function (x) { return '<span class="' + (x.spi < 1 ? "valor--negativo" : "") + '">' + indice(x.spi) + "</span>"; } },
      { titulo: "CPI", num: true, html: function (x) { return '<span class="' + (x.cpi < 1 ? "valor--negativo" : "") + '">' + indice(x.cpi) + "</span>"; } },
      { titulo: "Projeção (R$ mil)", num: true, html: function (x) { return mil(x.projecaoTermino) + '<br><span class="' + (x.vac < 0 ? "valor--sobrecusto" : "valor--economia") + '">' + (x.vac < 0 ? "+" : "−") + mil(Math.abs(x.vac)) + "</span>"; } },
      { titulo: "Término LB / tendência", nowrap: true, html: function (x) { return esc((x.terminoBaseline ? mes(x.terminoBaseline) : "·") + " / ") +
          '<span class="' + (x.terminoTendencia && x.terminoBaseline && x.terminoTendencia > x.terminoBaseline ? "valor--negativo" : "") + '">' + esc(x.terminoTendencia ? mes(x.terminoTendencia) : "·") + "</span>"; } },
      { titulo: "Riscos críticos", num: true, html: function (x) { return F.num(x.riscosTopo); } },
      { titulo: "Pedidos críticos", num: true, html: function (x) { return F.num(x.pedidosCriticos); } },
      { titulo: "Ações atrasadas", num: true, html: function (x) { return F.num(x.acoesAtrasadas); } },
      { titulo: "Situação", nowrap: true, html: function (x) { var sd = SAUDE[x.saude]; return x._total ? "" : sd ? U.badge(sd[0], sd[1], true) : "·"; } }
    ], linhas, { legenda: "Carteira de projetos" });
    var crit = tabela([
      { titulo: "Critério", html: function (k) { return esc(k.nome); } },
      { titulo: "Peso", num: true, html: function (k) { return pct(k.peso, 0); } },
      { titulo: "Fonte", html: function (k) { return esc(k.fonte === "orcamento" ? "orçamento vigente (EAC)" : "nota de 1 a 5 por projeto"); } }
    ], c.criterios, { legenda: "Critérios de ponderação" });
    var corpo = kpis + '<div class="rel-bloco"><h3 class="rel-bloco__titulo">Projetos da carteira <small>R$ mil · posição na data de referência · peso = relevância na carteira</small></h3>' + tab + "</div>" +
      '<div class="rel-grade rel-grade--60-40">' +
        '<div class="rel-bloco"><h3 class="rel-bloco__titulo">Curva S física da carteira <small>média ponderada pelos pesos dos projetos</small></h3><div class="chart rel-grafico rel-grafico--p"><canvas id="g-carteira"></canvas></div></div>' +
        '<div class="rel-bloco"><h3 class="rel-bloco__titulo">Critérios de ponderação <small>peso do projeto = soma ponderada dos critérios, normalizada a 100%</small></h3>' + crit + "</div>" +
      "</div>";
    return folha({ secao: "Carteira de projetos", sub: "posição em " + F.data(c.referencia), acento: "--brand-verde", corpo: corpo,
      nota: "Posição na data de referência (a folha de Planejamento mostra o corte do período); SPI físico ponderado pelos pesos; custo somado em R$" });
  }
  function graficosCarteira() {
    var p = dados.planejamento;
    if (!p) return;
    GI.charts.sCurve("g-carteira", { labels: p.curva.meses.map(mes), baseline: p.curva.baseline, real: p.curva.real, forecast: p.curva.tendencia });
  }

  /* ---------------- 02 Planejamento: Curva S e KPIs ---------------- */
  function folhaPlanejamentoKpis() {
    var p = dados.planejamento, sem = dados.periodo.tipo === "Semanal";
    if (!p) return folha({ secao: "Planejamento · Curva S, KPIs e produtividade", acento: "--module-planejamento", corpo: '<div class="rel-alerta">Projeto sem Curva S cadastrada.</div>' });
    /* Cards: previsto em azul e realizado em verde (mesmas cores dos gráficos); desvio negativo e data atrasada em vermelho */
    var desvioCor = p.desvioPP == null ? "info" : p.desvioPP < 0 ? "danger" : "success";
    var atrasoTermino = p.terminoTendencia && p.terminoBaseline && p.terminoTendencia > p.terminoBaseline;
    var kpis = '<div class="rel-kpis">' + [
      kpi({ rotulo: "Avanço previsto (acumulado)", valor: pct(p.previsto), cor: "previsto", esperado: { rotulo: "Linha de base", valor: F.data(dados.periodo.corte) } }),
      kpi({ rotulo: "Avanço real (acumulado)", valor: pct(p.real), cor: "real", esperado: { rotulo: "Previsto", valor: pct(p.previsto) }, rodape: "desvio " + (p.desvioPP < 0 ? '<span class="valor--negativo">' + pp(p.desvioPP) + " p.p.</span>" : pp(p.desvioPP) + " p.p.") }),
      kpi({ rotulo: "SPI físico", valor: indice(p.spi), cor: corIndice(p.spi), esperado: { rotulo: "Meta", valor: META_INDICE }, rodape: p.spiAnterior != null ? "período anterior " + indice(p.spiAnterior) : "real ÷ previsto" }),
      kpi({ rotulo: sem ? "Avanço na semana" : "Avanço no mês", valor: p.realPeriodo == null ? "·" : F.num(p.realPeriodo, 1), unidade: "p.p.",
        cor: p.realPeriodo != null && p.realPeriodo >= p.previstoPeriodo ? "success" : "danger", esperado: { rotulo: "Previsto", valor: p.previstoPeriodo == null ? "·" : F.num(p.previstoPeriodo, 1) + " p.p." },
        rodape: p.realPeriodo == null || p.previstoPeriodo == null ? "" : "desvio " + pp(Math.round((p.realPeriodo - p.previstoPeriodo) * 10) / 10) + " p.p." }),
      kpi({ rotulo: "Término pela tendência", valor: p.terminoTendencia ? esc(mes(p.terminoTendencia)) : "·", cor: atrasoTermino ? "danger" : "success",
        esperado: { rotulo: "Linha de base", valor: p.terminoBaseline ? mes(p.terminoBaseline) : "·" } }),
      kpi({ rotulo: "Desvio acumulado", valor: pp(p.desvioPP), unidade: "p.p.", cor: desvioCor, esperado: { rotulo: "Meta", valor: "≥ " + F.num(0) }, rodape: "faixas −" + F.num(faixasDesvioPP()[0]) + " e −" + F.num(faixasDesvioPP()[1]) + " p.p." })
    ].join("") + "</div>";
    var areas = tabela([
      { titulo: portfolio() ? "Projeto" : "Área", html: function (a) { return esc(a.area); } },
      { titulo: "Peso", num: true, html: function (a) { return pct(a.peso, 0); } },
      { titulo: "Previsto", num: true, html: function (a) { return pct(a.previsto, 0); } },
      { titulo: "Real", num: true, html: function (a) { return pct(a.real, 0); } },
      { titulo: "Desvio (p.p.)", num: true, html: function (a) { return '<span class="' + (a.desvio < 0 ? "valor--negativo" : "") + '">' + pp(a.desvio) + "</span>"; } }
    ], p.areas, { legenda: portfolio() ? "Avanço por projeto" : "Avanço por área", vazio: "Sem avanço por área." });
    var corpo = kpis + kpisProdutividade(p.produtividade) +
      '<div class="rel-grade rel-grade--60-40">' +
        '<div class="rel-bloco"><h3 class="rel-bloco__titulo">Curva S física <small>% acumulado por mês</small></h3><div class="chart rel-grafico rel-grafico--c"><canvas id="g-curva"></canvas></div></div>' +
        '<div class="rel-bloco"><h3 class="rel-bloco__titulo">' + (sem ? "Avanço por semana" : "Avanço por mês") + " <small>p.p. no período</small></h3>" +
          '<div class="chart rel-grafico rel-grafico--p"><canvas id="g-periodos"></canvas></div>' +
          '<h3 class="rel-bloco__titulo">' + (portfolio() ? "Avanço por projeto <small>peso = relevância na carteira</small>" : "Avanço por área") + (p.areasNaReferencia ? " <small>posição na data de referência</small>" : "") + "</h3>" + areas + "</div>" +
      "</div>";
    var nota = (sem ? "Semanal: avanço interpolado dentro do mês (Curva S mensal)" : "Mensal: ponto do mês da Curva S") + (portfolio() ? "; carteira: média ponderada dos projetos" : "");
    return folha({ secao: "Planejamento · Curva S, KPIs e produtividade", sub: "corte " + F.data(dados.periodo.corte), acento: "--module-planejamento", corpo: corpo, nota: nota });
  }
  /* Produtividade (02 Produtividade): janela de N semanas terminando na semana do corte, metas dos parâmetros */
  function kpisProdutividade(q) {
    if (!q) return "";
    var m = q.metas, f = q.faixas || {};
    var jan = q.janela || {};
    return '<h3 class="rel-bloco__titulo">Produtividade <small>' + esc("últimas " + (jan.n || "") + " semanas até " + (jan.semanas ? jan.semanas[jan.semanas.length - 1].replace(/^\d{4}-/, "") : "")) +
      (q.empresasEmAlerta && q.empresasEmAlerta.length ? " · empresas em alerta: " + esc(q.empresasEmAlerta.join(", ")) : "") + "</small></h3>" +
      '<div class="rel-kpis">' + [
        kpi({ rotulo: "SPI de quantidades", valor: indice(q.spi), cor: f.spi || corIndice(q.spi), esperado: { rotulo: "Meta", valor: META_INDICE }, rodape: "real " + pct(q.pctReal) + " x previsto " + pct(q.pctPrev) }),
        kpi({ rotulo: "Fator de produtividade (FP)", valor: indice(q.pf), cor: f.pf || "info", esperado: { rotulo: "Meta", valor: "≤ " + indice(m.pf) }, rodape: "HH aprop. ÷ ganhas" }),
        kpi({ rotulo: "Aderência semanal", valor: pct(q.aderencia), cor: f.aderencia || "info", esperado: { rotulo: "Meta", valor: minimo(m.aderencia) }, rodape: "real ÷ LB" }),
        kpi({ rotulo: "Pessoas trabalhando", valor: pct(q.pctTrabalhando), cor: f.trabalhando || "info", esperado: { rotulo: "Meta", valor: minimo(m.trabalhando) }, rodape: "amostragem" }),
        kpi({ rotulo: "Utilização da jornada", valor: pct(q.utilizacao), cor: f.utilizacao || "info", esperado: { rotulo: "Meta", valor: minimo(m.utilizacao) }, rodape: "horas efetivas" }),
        kpi({ rotulo: "HH paralisadas", valor: pct(q.pctHhoraParalisada), cor: q.pctHhoraParalisada > 5 ? "warning" : "success", esperado: { rotulo: "Limite", valor: "≤ " + F.pct(5, 0) }, rodape: F.num(q.hhoraParalisada, 0) + " HH na janela" })
      ].join("") + "</div>";
  }
  function graficosPlanejamento() {
    var p = dados.planejamento;
    if (!p) return;
    GI.charts.sCurve("g-curva", { labels: p.curva.meses.map(mes), baseline: p.curva.baseline, real: p.curva.real, forecast: p.curva.tendencia });
    GI.charts.bar("g-periodos", { labels: p.serie.rotulos, ariaLabel: "Avanço previsto e real por período, em pontos percentuais",
      series: [{ label: "Previsto", data: p.serie.previsto, color: "chart-baseline" }, { label: "Real", data: p.serie.real, color: "chart-real" }] });
  }

  /* ---------------- 02 Planejamento: relato do período ---------------- */
  function folhaPlanejamentoRelatoCarteira() {
    var rp = (dados.planejamento && dados.planejamento.relatosProjetos) || [];
    var pontos = [], n = 0;
    rp.forEach(function (x) { (x.relato ? x.relato.pontos : []).forEach(function (pt) { pontos.push(Object.assign({ _n: ++n, _proj: x.projetoCodigo }, pt)); }); });
    var situacao = tabela([
      { titulo: "Projeto", nowrap: true, html: function (x) { return esc(x.projetoCodigo); } },
      { titulo: "Relato " + nomeTipo(), html: function (x) {
          if (x.relato) return esc("registrado em " + F.data(x.relato.atualizadoEm.slice(0, 10)) + " por " + U.pessoa(x.relato.atualizadoPorId));
          var u = "modulos/planejamento/relato.html?projeto=" + x.projetoId + "&tipo=" + encodeURIComponent(dados.periodo.tipo) + "&periodo=" + encodeURIComponent(dados.periodo.periodo) + "&abrir=1";
          return '<span class="valor--negativo">pendente</span> <a class="no-print" href="' + esc(u) + '">(registrar)</a>'; } },
      { titulo: "Pontos", num: true, html: function (x) { return x.relato ? F.num(x.relato.pontos.length) : "·"; } }
    ], rp, { legenda: "Relatos dos projetos" });
    var corpo = '<div class="rel-grade rel-grade--55-45">' + blocoAnalise("planejamento") +
      '<div class="rel-bloco"><h3 class="rel-bloco__titulo">Relatos dos projetos <small>' + esc(dados.periodo.rotulo) + " · atividades no relatório de cada projeto</small></h3>" + situacao + "</div></div>" +
      '<div class="rel-bloco"><h3 class="rel-bloco__titulo">Pontos de atenção e riscos dos projetos (ameaça e oportunidade)</h3>' +
      tabela([
        { titulo: "Nº", nowrap: true, html: function (x) { return String(x._n); } },
        { titulo: "Projeto", nowrap: true, html: function (x) { return esc(x._proj); } },
        { titulo: "Ponto de atenção", html: function (x) { return esc(x.descricao); } },
        { titulo: "Risco", nowrap: true, html: function (x) { return natureza(x.natureza); } },
        { titulo: "Descrição do risco", html: function (x) { return esc(x.risco); } }
      ], pontos, { legenda: "Pontos de atenção e riscos dos projetos", vazio: "Nenhum ponto de atenção registrado nos relatos do período.", limite: 8 }) + "</div>";
    var pend = rp.filter(function (x) { return !x.relato; }).length;
    return folha({ secao: "Planejamento · Análise da carteira e relatos", sub: U.plural(pontos.length, "ponto de atenção", "pontos de atenção"), acento: "--module-planejamento", corpo: corpo,
      nota: pend ? U.plural(pend, "relato pendente", "relatos pendentes") : "Relatos de todos os projetos registrados" });
  }
  function folhaPlanejamentoRelato() {
    if (portfolio()) return folhaPlanejamentoRelatoCarteira();
    var r = dados.planejamento ? dados.planejamento.relato : null, prox = dados.proximo;
    var urlRelato = "modulos/planejamento/relato.html?tipo=" + encodeURIComponent(dados.periodo.tipo) + "&periodo=" + encodeURIComponent(dados.periodo.periodo) + "&abrir=1" + qEscopo();
    function lista(itens) { return itens.length ? '<ul class="rel-lista">' + itens.map(function (t) { return "<li>" + esc(t) + "</li>"; }).join("") + "</ul>" : '<p class="rel-vazio">Sem registro.</p>'; }
    var corpo, analise = blocoAnalise("planejamento");
    if (!r) {
      corpo = '<div class="rel-grade rel-grade--55-45">' + analise +
        '<div class="rel-bloco"><div class="rel-alerta"><b>Relato ' + nomeTipo() + " do período não registrado.</b> Registre as atividades do período, as do próximo período e os pontos de atenção em 02 Planejamento > Relato do período" +
        ' <a class="no-print" href="' + esc(urlRelato) + '">(registrar agora)</a> e emita o relatório de novo.</div></div></div>';
    } else {
      corpo = '<div class="rel-grade rel-grade--55-45">' + analise +
        '<div class="rel-bloco"><h3 class="rel-bloco__titulo">Atividades do período <small>' + esc(dados.periodo.rotulo) + "</small></h3>" + lista(r.atividadesPeriodo) +
        '<h3 class="rel-bloco__titulo">Atividades do próximo período <small>' + esc(prox ? prox.rotulo : "") + "</small></h3>" + lista(r.atividadesProximo) + "</div></div>" +
        '<div class="rel-bloco"><h3 class="rel-bloco__titulo">Pontos de atenção e riscos (ameaça e oportunidade)</h3>' +
        tabela([
          { titulo: "Nº", nowrap: true, html: function (x) { return String(x._n); } },
          { titulo: "Ponto de atenção", html: function (x) { return esc(x.descricao); } },
          { titulo: "Risco", nowrap: true, html: function (x) { return natureza(x.natureza); } },
          { titulo: "Descrição do risco", html: function (x) { return esc(x.risco); } }
        ], r.pontos.map(function (x, k) { return Object.assign({ _n: k + 1 }, x); }), { legenda: "Pontos de atenção e riscos", vazio: "Nenhum ponto de atenção registrado no período." }) + "</div>";
    }
    var nota = r ? "Relato atualizado em " + F.data(r.atualizadoEm.slice(0, 10)) + " por " + U.pessoa(r.atualizadoPorId) + "; riscos sem vínculo com o 05" : "Relato pendente";
    return folha({ secao: "Planejamento · Análise e relato do período", sub: r ? U.plural(r.pontos.length, "ponto de atenção", "pontos de atenção") : "", acento: "--module-planejamento", corpo: corpo, nota: nota });
  }

  /* ---------------- 03 Financeiro ---------------- */
  function folhaFinanceiro() {
    var f = dados.financeiro;
    if (!f || f.semFechamento) {
      return folha({ secao: "Financeiro", acento: "--module-financeiro", nota: "Custos apurados por mês",
        corpo: '<div class="rel-alerta">Sem fechamento mensal de custos até o fim do período. O primeiro fechamento disponível é posterior ao período escolhido.</div>' + blocoAnalise("financeiro") });
    }
    var va = f.valorAgregado || {}, ant = f.anterior || {};
    var sobrecusto = f.vac < 0;
    var kpis = '<div class="rel-kpis">' + [
      kpiMoeda({ rotulo: "Orçamento vigente (BAC)", centavos: f.bac, cor: "previsto", esperado: { rotulo: "Linha de base", valor: moedaRef(ref.mapa ? ref.mapa.total.base : null) }, rodape: "EAC revisão vigente" }),
      kpiMoeda({ rotulo: "Realizado acumulado", centavos: f.realizado, cor: "real", esperado: { rotulo: "Previsto", valor: moedaRef(f.planejado) }, rodape: F.moedaCompacta(f.realizadoMes) + " no mês · plan. " + F.moedaCompacta(f.planejadoMes) }),
      kpiMoeda({ rotulo: "Valor agregado (EV)", centavos: va.ev, cor: "real", esperado: { rotulo: "Previsto", valor: moedaRef(va.pv) }, rodape: "planejado (PV)" }),
      kpi({ rotulo: "CPI", valor: indice(va.cpi), cor: corIndice(va.cpi), esperado: { rotulo: "Meta", valor: META_INDICE }, rodape: "mês anterior " + indice(ant.cpi) + " · SPI " + indice(va.spi) }),
      kpiMoeda({ rotulo: "Projeção no término", centavos: f.projecaoTermino, cor: sobrecusto ? "danger" : "success", esperado: { rotulo: "Orçado", valor: moedaRef(f.bac) },
        rodape: '<span class="' + (sobrecusto ? "valor--sobrecusto" : "valor--economia") + '">' + (sobrecusto ? "+" : "−") + esc(F.moedaCompacta(Math.abs(f.vac))) + "</span> x orçamento" }),
      kpi({ rotulo: "Contingência consumida", valor: pct(f.contingenciaPct), cor: f.contingenciaPct > 50 ? "danger" : "success", esperado: { rotulo: "Limite", valor: ref.cont && ref.cont.limiteConsumoPct != null ? "≤ " + F.pct(ref.cont.limiteConsumoPct, 1) : "·" },
        rodape: F.moedaCompacta(f.contingenciaConsumida) + " de " + F.moedaCompacta(f.contingencia) })
    ].join("") + "</div>";
    var linhas = f.pacotes.concat([Object.assign({ _classe: "rel-total", codigo: "", descricao: portfolio() ? "Total da carteira" : "Total do projeto" }, f.total)]);
    var tab = tabela([
      { titulo: portfolio() ? "Projeto" : "Pacote", html: function (x) { return portfolio() ? esc(x.descricao) : (x.codigo ? esc(x.codigo) + " " : "") + esc(x.descricao); } },
      { titulo: "Orçado", num: true, html: function (x) { return mil(x.atual); } },
      { titulo: "Comprometido", num: true, html: function (x) { return mil(x.comprometido); } },
      { titulo: "Realizado", num: true, html: function (x) { return mil(x.realizado); } },
      { titulo: "Projeção", num: true, html: function (x) { return mil(x.projecao); } },
      { titulo: "Desvio", num: true, html: function (x) { return calor(x.desvioPct, x.faixa); } }
    ], linhas, { legenda: portfolio() ? "EAC por projeto" : "EAC por pacote" });
    var ev = tabela([
      { titulo: "Mês", nowrap: true, html: function (x) { return esc(mes(x.mes)); } },
      { titulo: "Planejado (PV)", num: true, html: function (x) { return mil(x.pv); } },
      { titulo: "Agregado (EV)", num: true, html: function (x) { return mil(x.ev); } },
      { titulo: "Real (AC)", num: true, html: function (x) { return mil(x.ac); } },
      { titulo: "CPI", num: true, html: function (x) { return '<span class="' + (x.cpi < 1 ? "valor--negativo" : "") + '">' + indice(x.cpi) + "</span>"; } },
      { titulo: "SPI", num: true, html: function (x) { return '<span class="' + (x.spi < 1 ? "valor--negativo" : "") + '">' + indice(x.spi) + "</span>"; } }
    ], f.historico || [], { legenda: "Valor agregado mês a mês", vazio: "Sem histórico de valor agregado." });
    var corpo = kpis + '<div class="rel-grade rel-grade--45-55">' +
      '<div class="rel-bloco"><h3 class="rel-bloco__titulo">Curva S financeira <small>acumulado até ' + esc(mes(f.mes)) + (f.curva.eacTendencia ? " · tendência pelo CPI: EAC " + esc(F.moedaCompacta(f.curva.eacTendencia)) : "") + "</small></h3>" +
        '<div class="chart rel-grafico rel-grafico--m"><canvas id="g-financeira"></canvas></div>' +
        '<h3 class="rel-bloco__titulo">Valor agregado mês a mês <small>R$ mil</small></h3>' + ev + "</div>" +
      '<div class="rel-bloco">' + blocoAnalise("financeiro") +
        '<h3 class="rel-bloco__titulo">' + (portfolio() ? "EAC por projeto" : "EAC por pacote") + ' <small>R$ mil · desvio = projeção x orçado (posição atual)</small></h3>' + tab + "</div></div>";
    var nota = "Fechamento de " + f.mesRotulo + (f.fechadoNoSemanal ? " (no semanal, último mês fechado)" : "") + (f.mesCorrente ? " · mês em andamento" : "") +
      " · tendência: EAC = BAC ÷ CPI, pelo perfil do planejado";
    return folha({ secao: "Financeiro", sub: "competência " + f.mesRotulo, acento: "--module-financeiro", corpo: corpo, nota: nota });
  }
  function graficosFinanceiro() {
    var f = dados.financeiro;
    if (!f || f.semFechamento) return;
    GI.charts.sCurveFinanceira("g-financeira", { labels: f.curva.meses.map(mes), planejado: f.curva.planejado, comprometido: f.curva.comprometido,
      realizado: f.curva.realizado, projecao: f.curva.tendencia, rotuloProjecao: "Tendência (CPI)",
      ariaLabel: "Curva S financeira: planejado, comprometido e realizado acumulados por mês, com a linha de tendência pelo CPI" });
  }

  /* ---------------- 04 Suprimentos ---------------- */
  function folhaSuprimentos() {
    var s = dados.suprimentos, sem = dados.periodo.tipo === "Semanal", corte = dados.periodo.corte;
    /* Pedidos com emissão planejada (LB do pacote) até o corte */
    var pedidosPrevistos = ref.pacotes ? ref.pacotes.filter(function (x) { return x.plano && x.plano.pedido && x.plano.pedido <= corte; }).length : null;
    var kpis = '<div class="rel-kpis">' + [
      kpi({ rotulo: "Aderência ao plano de compras", valor: pct(s.aderenciaPct), cor: s.aderenciaPct == null ? "info" : s.aderenciaPct >= 90 ? "success" : "warning", esperado: { rotulo: "Meta", valor: minimo(90) },
        rodape: F.num(s.adjudicadosAteCorte) + " de " + F.num(s.planejadosAteCorte) + " planejados até o corte" }),
      kpi({ rotulo: "Pacotes adjudicados", valor: F.num(s.adjudicadosAteCorte), unidade: "de " + F.num(s.pacotes), cor: "real", esperado: { rotulo: "Previsto", valor: F.num(s.planejadosAteCorte) }, rodape: F.moedaCompacta(s.adjudicadoCentavos) + " adjudicados" }),
      kpi({ rotulo: "Saving", valor: pct(s.savingPct), cor: "success", esperado: { rotulo: "Meta", valor: "≥ " + F.pct(0, 0) }, rodape: F.moedaCompacta(s.savingCentavos) + " sobre a estimativa" }),
      kpi({ rotulo: "Entregas no prazo (OTD)", valor: pct(s.otdPct), cor: s.otdPct == null ? "info" : s.otdPct >= 90 ? "success" : "warning", esperado: { rotulo: "Meta", valor: minimo(90) }, rodape: F.num(s.entregasNoPrazo) + " de " + F.num(s.entregas) + " entregas até o corte" }),
      kpi({ rotulo: "Pedidos críticos", valor: F.num(s.criticos.length), cor: s.criticos.length ? "danger" : "success", esperado: ESP_ZERO, rodape: "folga negativa · " + F.num(s.emAtencao) + " em atenção" }),
      kpi({ rotulo: "Pedidos emitidos", valor: F.num(s.pedidos), cor: "real", esperado: { rotulo: "Linha de base", valor: pedidosPrevistos == null ? "·" : F.num(pedidosPrevistos) }, rodape: "até o corte" })
    ].join("") + "</div>";
    var criticos = tabela([
      { titulo: "Pedido", nowrap: true, html: function (x) { return esc(x.numero) + (x.lli ? " " + U.badge("LLI", "outline") : ""); } },
      { titulo: "Item", html: function (x) { return (portfolio() ? "<b>" + esc(x.projetoCodigo) + "</b> · " : "") + esc(x.descricao); } },
      { titulo: "ROS", nowrap: true, html: function (x) { return dataCurta(x.ros); } },
      { titulo: "Previsão", nowrap: true, html: function (x) { return dataCurta(x.previsao); } },
      { titulo: "Folga", num: true, html: function (x) { return '<span class="valor--negativo">' + F.num(x.folgaDias) + " d</span>"; } }
    ], s.criticos, { legenda: "Pedidos críticos", vazio: "Nenhum pedido com folga negativa.", limite: 4 });
    var colEv = [
      { titulo: "Data", nowrap: true, html: function (x) { return dataCurta(x.data); } },
      { titulo: "Marco", nowrap: true, html: function (x) { return esc(x.tipo); } },
      { titulo: "Pedido / pacote", nowrap: true, html: function (x) { return esc(x.codigo); } },
      { titulo: "Item", html: function (x) { return (portfolio() && x.projetoCodigo ? "<b>" + esc(x.projetoCodigo) + "</b> · " : "") + esc(x.descricao); } },
      { titulo: "Desvio", num: true, html: function (x) { return x.desvioDias == null ? "·" : '<span class="' + (x.desvioDias > 0 ? "valor--negativo" : "") + '">' + (x.desvioDias > 0 ? "+" : "") + F.num(x.desvioDias) + " d</span>"; } }
    ];
    var h = s.horizonte;
    var corpo = kpis + '<div class="rel-grade rel-grade--45-55">' +
      '<div class="rel-bloco"><h3 class="rel-bloco__titulo">Curva de contratação <small>pacotes adjudicados, acumulado</small></h3><div class="chart rel-grafico rel-grafico--p"><canvas id="g-contratacao"></canvas></div>' +
        '<h3 class="rel-bloco__titulo">Pedidos críticos <small>posição na data de referência</small></h3>' + criticos + "</div>" +
      blocoAnalise("suprimentos") + "</div>" +
      '<div class="rel-grade rel-grade--50-50">' +
      '<div class="rel-bloco"><h3 class="rel-bloco__titulo">Realizado no período <small>desvio x linha de base</small></h3>' +
        tabela(colEv, s.eventos, { legenda: "Marcos realizados no período", vazio: "Nenhum marco de suprimentos realizado no período.", limite: 5 }) + "</div>" +
      '<div class="rel-bloco"><h3 class="rel-bloco__titulo">' + (sem ? "Previsto nas próximas 4 semanas" : "Previsto no próximo mês") + " <small>" + esc(F.data(h.inicio) + " a " + F.data(h.fim)) + " · desvio x plano ou contrato</small></h3>" +
        tabela(colEv, s.previstos, { legenda: "Adjudicações e entregas previstas", vazio: "Nenhuma adjudicação ou entrega prevista no horizonte.", limite: 5 }) + "</div></div>";
    return folha({ secao: "Suprimentos", sub: "corte " + F.data(dados.periodo.corte), acento: "--module-suprimentos", corpo: corpo, nota: "Eventos por data até o corte; pedidos críticos na data de referência" });
  }
  function graficosSuprimentos() {
    var c = dados.suprimentos.curva;
    GI.charts.line("g-contratacao", { labels: c.meses.map(mes), ariaLabel: "Pacotes adjudicados acumulados: planejado e realizado",
      series: [{ label: "Planejado", data: c.planejado, color: "chart-baseline", dashed: true, points: false }, { label: "Realizado", data: c.realizado, color: "chart-real" }] });
  }

  /* ---------------- 05 Riscos ---------------- */
  function folhaRiscos() {
    var k = dados.riscos, s = k.resumo;
    var kpis = '<div class="rel-kpis">' + [
      kpi({ rotulo: "Riscos ativos", valor: F.num(s.ativos), cor: "info", esperado: { rotulo: "Referência", valor: deRegistrados(ref.riscos ? ref.riscos.length : null) }, rodape: U.plural(k.ameacas, "ameaça") + " · " + U.plural(k.oportunidades, "oportunidade") }),
      kpi({ rotulo: s.topo.nome + "s", valor: F.num(s.topo.total), cor: s.topo.total ? "danger" : "success", esperado: { rotulo: "Meta", valor: metaSeveridade(s.topo.id) }, rodape: U.plural(s.topo.ameacas, "ameaça") + " · " + U.plural(s.topo.oportunidades, "oportunidade") }),
      s.segunda ? kpi({ rotulo: s.segunda.nome + "s", valor: F.num(s.segunda.total), cor: s.segunda.total ? "warning" : "success", esperado: { rotulo: "Meta", valor: metaSeveridade(s.segunda.id) }, rodape: U.plural(s.segunda.ameacas, "ameaça") + " · " + U.plural(s.segunda.oportunidades, "oportunidade") }) : "",
      kpiMoeda({ rotulo: "Exposição (VME)", centavos: s.exposicaoCentavos, cor: "info", esperado: { rotulo: "Limite", valor: ref.cont ? "≤ " + F.moedaCompacta(ref.cont.contingencia.saldo) : "·" }, rodape: "ameaças ativas" }),
      kpi({ rotulo: "Revisão vencida", valor: F.num(s.revisaoVencida), cor: s.revisaoVencida ? "danger" : "success", esperado: ESP_ZERO, rodape: F.num(s.pauta) + " na pauta de escalonamento" }),
      kpi({ rotulo: "Identificados no período", valor: F.num(k.identificadosNoPeriodo), cor: "info", esperado: { rotulo: "Referência", valor: deRegistrados(ref.riscos ? ref.riscos.length : null) }, rodape: F.num(k.encerradosNoPeriodo) + " encerrados no período" })
    ].join("") + "</div>";
    var cel = {};
    k.matriz.forEach(function (c) { cel[c.p + "-" + c.i] = c; });
    var mat = '<div class="rel-matriz" role="img" aria-label="Matriz de probabilidade por impacto, avaliação residual">';
    for (var p = 5; p >= 1; p--) {
      mat += '<span class="rel-matriz__eixo">' + p + "</span>";
      for (var i = 1; i <= 5; i++) {
        var c = cel[p + "-" + i];
        var txt = (c.ameacas ? c.ameacas + LETRA_AMEACA : "") + (c.ameacas && c.oportunidades ? " · " : "") + (c.oportunidades ? c.oportunidades + "O" : "");
        mat += '<span class="rel-matriz__cel sev--' + esc(c.sev ? c.sev.id : "baixo") + '" title="P' + p + " x I" + i + '">' + esc(txt) + "</span>";
      }
    }
    mat += '<span></span>' + [1, 2, 3, 4, 5].map(function (n) { return '<span class="rel-matriz__eixo">' + n + "</span>"; }).join("") +
      '<span class="rel-matriz__rotulo-x">Impacto (eixo vertical: probabilidade) · A = ameaças, O = oportunidades</span></div>';
    var principais = tabela([
      { titulo: "Nº", nowrap: true, html: function (r) { return esc(portfolio() ? r.codigo : r.codigo.replace(/^RSK-[A-Z]+-\d{4}-/, "RSK-")); } },
      { titulo: "Risco", html: function (r) { return esc(r.titulo) + "<br>" + natureza(r.natureza); } },
      { titulo: "Residual", nowrap: true, html: function (r) { return sev(r.sevAtual, r.scoreAtual, r.natureza); } },
      { titulo: "Estratégia", nowrap: true, html: function (r) { return esc(r.estrategia || "·"); } },
      { titulo: "Dono", html: function (r) { return esc(U.pessoa(r.donoId)); } },
      { titulo: "Próx. revisão", nowrap: true, html: function (r) { return '<span class="' + (r.revisaoVencida ? "valor--negativo" : "") + '">' + dataCurta(r.proximaRevisao) + "</span>"; } }
    ], k.principais, { legenda: "Principais riscos", vazio: "Nenhum risco ativo avaliado.", limite: 5 });
    var corpo = kpis + '<div class="rel-grade rel-grade--40-60">' +
      '<div class="rel-bloco"><h3 class="rel-bloco__titulo">Matriz P x I <small>residual, riscos ativos</small></h3>' + mat +
        '<h3 class="rel-bloco__titulo">Exposição das ameaças <small>score residual somado por mês</small></h3><div class="chart rel-grafico rel-grafico--p"><canvas id="g-exposicao"></canvas></div></div>' +
      '<div class="rel-bloco">' + blocoAnalise("riscos") + '<h3 class="rel-bloco__titulo">Principais riscos <small>maior score residual</small></h3>' + principais + "</div></div>";
    return folha({ secao: "Riscos", sub: "registro do 05 Gestão de Riscos", acento: "--module-riscos", corpo: corpo, nota: "KPIs, matriz e riscos na data de referência; identificados e encerrados no período" });
  }
  function graficosRiscos() {
    var e = dados.riscos.evolucao;
    GI.charts.bar("g-exposicao", { labels: e.map(function (x) { return mes(x.mes); }), ariaLabel: "Score residual somado das ameaças por mês",
      series: [{ label: "Score residual somado", data: e.map(function (x) { return x.score; }), color: "chart-1" }] });
  }

  /* ---------------- 06 Qualidade ---------------- */
  function folhaQualidade() {
    var q = dados.qualidade;
    var kpis = '<div class="rel-kpis">' + [
      kpi({ rotulo: "RNC em aberto no corte", valor: F.num(q.emAbertoCorte), cor: q.criticasCorte || q.vencidas.length ? "danger" : q.emAbertoCorte ? "warning" : "success", esperado: ESP_ZERO,
        rodape: U.plural(q.criticasCorte, "crítica", "críticas") + " · " + U.plural(q.vencidas.length, "vencida", "vencidas") }),
      kpi({ rotulo: "RNC abertas no período", valor: F.num(q.abertasPeriodo), cor: q.abertasPeriodo ? "warning" : "success", esperado: ESP_ZERO, rodape: F.num(q.encerradasPeriodo) + " encerradas no período" }),
      kpi({ rotulo: "Aprovação em inspeções", valor: pct(q.aprovacaoPct), cor: q.aprovacaoPct == null ? "info" : q.aprovacaoPct >= q.metaAprovacaoPct ? "success" : "warning",
        esperado: { rotulo: "Meta", valor: minimo(q.metaAprovacaoPct) }, rodape: U.plural(q.reprovadas.length, "reprovada", "reprovadas") + " em " + F.num(q.inspecoes) }),
      kpi({ rotulo: "Conformidade em auditorias", valor: pct(q.conformidadePct), cor: q.conformidadePct == null ? "info" : q.conformidadePct >= q.metaConformidadePct ? "success" : "warning", esperado: { rotulo: "Meta", valor: minimo(q.metaConformidadePct) },
        rodape: U.plural(q.auditoriasPeriodo, "auditoria no período", "auditorias no período") + " · " + U.plural(q.auditoriasAtrasadas.length, "atrasada", "atrasadas") }),
      kpiMoeda({ rotulo: "Custo da não qualidade", centavos: q.custoAcumuladoCentavos, cor: q.custoAcumuladoCentavos ? "danger" : "success", esperado: { rotulo: "Esperado", valor: F.moedaCompacta(0) }, rodape: F.moedaCompacta(q.custoPeriodoCentavos) + " em RNC do período" }),
      kpi({ rotulo: "Disciplina com mais RNC", valor: q.porDisciplina.length ? esc(q.porDisciplina[0].nome) : "·", cor: "info",
        esperado: { rotulo: "Referência", valor: U.plural(q.porDisciplina.reduce(function (t, d) { return t + d.total; }, 0), "RNC", "RNCs") },
        rodape: q.porDisciplina.length ? U.plural(q.porDisciplina[0].total, "RNC", "RNCs") + " · " + pct(q.porDisciplina[0].pct, 0) + " do total" : "" })
    ].join("") + "</div>";
    var pauta = tabela([
      { titulo: "RNC", nowrap: true, html: function (r) { return esc(r.codigo); } },
      { titulo: "Não conformidade", html: function (r) { return esc(r.descricao); } },
      { titulo: "Severidade", nowrap: true, html: function (r) { return esc(r.severidade); } },
      { titulo: "Situação", nowrap: true, html: function (r) { return esc(r.situacao); } },
      { titulo: "Motivo", html: function (r) { return '<span class="valor--negativo">' + esc(r.motivos.join("; ")) + "</span>"; } }
    ], q.pauta, { legenda: "Pauta de tratamento", vazio: "Nenhuma RNC fora do prazo, crítica ou com concessão pendente.", limite: 5 });
    var repr = tabela([
      { titulo: "Data", nowrap: true, html: function (n) { return dataCurta(n.data); } },
      { titulo: "Ponto", html: function (n) { return esc(n.ponto) + (n.itpCodigo ? " (" + esc(n.itpCodigo) + ")" : ""); } },
      { titulo: "Empresa", html: function (n) { return esc(U.empresa(n.empresaId)); } },
      { titulo: "RNC", nowrap: true, html: function (n) { return esc(n.rncRef || "·"); } }
    ], q.reprovadas, { legenda: "Inspeções reprovadas no período", vazio: "Nenhuma inspeção reprovada no período.", limite: 5 });
    var corpo = kpis + '<div class="rel-grade rel-grade--40-60">' +
      '<div class="rel-bloco"><h3 class="rel-bloco__titulo">RNC por mês <small>abertas e encerradas</small></h3><div class="chart rel-grafico rel-grafico--p"><canvas id="g-qualidade"></canvas></div>' +
        '<h3 class="rel-bloco__titulo">Inspeções reprovadas no período</h3>' + repr + "</div>" +
      '<div class="rel-bloco">' + blocoAnalise("qualidade") + '<h3 class="rel-bloco__titulo">Pauta de tratamento <small>posição na data de referência</small></h3>' + pauta + "</div></div>";
    return folha({ secao: "Qualidade", sub: "corte " + F.data(dados.periodo.corte), acento: "--module-qualidade", corpo: corpo,
      nota: "RNC e inspeções por data até o corte; pauta e auditorias atrasadas na data de referência" });
  }
  function graficosQualidade() {
    var s = dados.qualidade.serie;
    GI.charts.bar("g-qualidade", { labels: s.map(function (x) { return mes(x.mes); }), ariaLabel: "RNC abertas e encerradas por mês",
      series: [{ label: "Abertas", data: s.map(function (x) { return x.abertas; }), color: "chart-2" }, { label: "Encerradas", data: s.map(function (x) { return x.encerradas; }), color: "chart-1" }] });
  }

  /* ---------------- 07 HSE ---------------- */
  var ROTULOS_PIRAMIDE = ["Lesões graves", "Lesões leves", "Danos materiais", "Quase acidentes", "Desvios"];
  function folhaHse() {
    var h = dados.hse, m = h.mes_, a = h.acumulado, sem = dados.periodo.tipo === "Semanal";
    function taxa(v, casas) { return v == null ? "·" : F.num(v, casas == null ? 2 : casas); }
    /* Esperados: dias desde o início (zero afastamento), ocorrências do mês e HHT médio mensal do acumulado */
    var diasEsp = diasEntre(dados.projeto && dados.projeto.inicio, dados.periodo.corte);
    var ocorrenciasMes = (m.piramide || []).slice(0, 4).reduce(function (t, v) { return t + (v || 0); }, 0);
    var hhtPrev = GI.api.hse.hhtPrevisto(dados.portfolio ? null : (dados.projeto && dados.projeto.id), h.mes, true);
    var nMeses = mesesEntre(h.primeiroMes, h.mes), mediaHht = nMeses && a.hht != null ? Math.round(a.hht / nMeses) : null;
    var ant = ref.hseAnterior;
    var kpis = '<div class="rel-kpis">' + [
      kpi({ rotulo: "Taxa de frequência (TF)", valor: taxa(m.tf), cor: m.lti ? "danger" : "success", esperado: { rotulo: "Esperado", valor: taxa(0) }, rodape: "no mês · acumulado " + taxa(a.tf) }),
      kpi({ rotulo: "Lesões registráveis (TRIF)", valor: taxa(m.trif), cor: m.registraveis ? "warning" : "success", esperado: { rotulo: "Esperado", valor: taxa(0) }, rodape: "no mês · acumulado " + taxa(a.trif) }),
      kpi({ rotulo: "Taxa de gravidade (TG)", valor: taxa(m.tg, 1), cor: "info", esperado: { rotulo: "Esperado", valor: taxa(0, 1) }, rodape: "no mês · acumulado " + taxa(a.tg, 1) }),
      kpi({ rotulo: "Alto potencial (HiPo)", valor: F.num(m.hipo), cor: m.hipo ? "danger" : "success", esperado: ESP_ZERO, rodape: "no mês · " + F.num(a.hipo) + " no acumulado" }),
      kpi({ rotulo: "Dias sem afastamento", valor: h.diasSemAfastamento == null ? "·" : F.num(h.diasSemAfastamento), cor: "info", esperado: { rotulo: "Esperado", valor: diasEsp == null ? "·" : F.num(diasEsp) }, rodape: "no corte · desde " + dataCurta(h.semAfastamentoDesde) }),
      sem ? kpi({ rotulo: "Ocorrências na semana", valor: F.num(h.ocorrenciasPeriodo), cor: h.hipoPeriodo ? "danger" : "info", esperado: { rotulo: "Referência", valor: "de " + F.num(ocorrenciasMes) + " no mês" },
          rodape: U.plural(h.niveisPeriodo[3], "quase acidente", "quase acidentes") })
        : kpi({ rotulo: "HHT no mês", valor: F.num(m.hht), cor: "info", esperado: { rotulo: "Previsto", valor: hhtPrev ? F.num(hhtPrev.hht) : (mediaHht == null ? "·" : F.num(mediaHht)) }, rodape: F.num(a.hht) + " HHT no acumulado" })
    ].join("") + "</div>";
    var proativos = '<h3 class="rel-bloco__titulo">Indicadores proativos <small>acumulado de ' + esc(mes(h.primeiroMes)) + " a " + esc(mes(h.mes)) + "</small></h3>" +
      '<div class="rel-kpis">' + [
        kpi({ rotulo: "DDS realizados", valor: pct(a.ddsPct), cor: "info", esperado: { rotulo: "Meta", valor: F.pct(100, 0) }, rodape: "no mês " + pct(m.ddsPct) }),
        kpi({ rotulo: "Conformidade em inspeções", valor: pct(a.conformidadeInspecoesPct), cor: "info", esperado: { rotulo: "Esperado", valor: F.pct(100, 0) }, rodape: "no mês " + pct(m.conformidadeInspecoesPct) }),
        kpi({ rotulo: "Observações / 10 mil HHT", valor: a.observacoesPor10k == null ? "·" : F.num(a.observacoesPor10k, 1), cor: "info",
          esperado: { rotulo: "Meta", valor: "≥ " + F.num(((ref.par && ref.par.hse && ref.par.hse.metas) || { observacoesPor10MilHht: 40 }).observacoesPor10MilHht) }, rodape: "abordagens comportamentais" }),
        kpi({ rotulo: "Relato de quase acidentes", valor: a.relatoQuaseAcidente == null ? "·" : F.num(a.relatoQuaseAcidente, 1), cor: "info", id: "kpi-quase-acidente",
          esperado: { rotulo: "Referência", valor: "·" }, rodape: "por lesão registrável" }),
        kpi({ rotulo: "Recomendações fechadas", valor: pct(a.recomendacoesFechadasPct), cor: "info", esperado: { rotulo: "Esperado", valor: F.pct(100, 0) }, rodape: "APR e HAZOP" }),
        kpi({ rotulo: "Incidentes ambientais", valor: F.num(a.ambientais), cor: a.ambientais ? "warning" : "success", esperado: ESP_ZERO, rodape: F.num(m.ambientais) + " no mês" })
      ].join("") + "</div>";
    var corpo = kpis + '<div class="rel-grade rel-grade--40-60">' +
      '<div class="rel-bloco"><h3 class="rel-bloco__titulo">Pirâmide de segurança <small>mês x acumulado</small></h3><div class="pyramid-pair rel-piramide" id="g-piramide"></div>' +
        '<p class="rel-nota" id="nota-piramide"></p></div>' +
      '<div class="rel-bloco">' + blocoAnalise("hse") +
        '<h3 class="rel-bloco__titulo">Evolução mensal <small>TF e TRIF</small></h3><div class="chart rel-grafico rel-grafico--m"><canvas id="g-hse"></canvas></div></div></div>' + proativos;
    var nota = "Taxas por " + F.num(m.base) + " HHT (" + (m.base === 1000000 ? "NBR 14280" : "OSHA") + ") · base mensal (HHT por mês)" +
      (sem ? "; semanal: mês de " + mes(h.mes) + (h.mesParcial ? " até a data de referência" : "") + " e ocorrências da semana" : "");
    return folha({ secao: "HSE", sub: "mês de " + mes(h.mes) + (h.mesParcial ? " (parcial)" : ""), acento: "--module-hse", corpo: corpo, nota: nota });
  }
  function graficosHse() {
    var h = dados.hse;
    function niveis(p) { return p.map(function (v, i) { return { label: ROTULOS_PIRAMIDE[i], value: v }; }); }
    var r = GI.charts.pyramidPair("g-piramide", { reference: h.referencia,
      esquerda: { titulo: "Mês: " + mes(h.mes), levels: niveis(h.mes_.piramide) },
      direita: { titulo: "Acumulado: " + mes(h.primeiroMes) + " a " + mes(h.mes), levels: niveis(h.acumulado.piramide) } });
    /* Referência do relato de quase acidentes por lesão: proporção da pirâmide de referência (Bird ou Heinrich) */
    var rq = document.querySelector("#kpi-quase-acidente .rel-kpi__esperado b");
    if (r && rq && r.referenciaQuaseAcidente != null) rq.textContent = F.num(r.referenciaQuaseAcidente, 1);
    var nota = document.getElementById("nota-piramide");
    if (r && nota) nota.innerHTML = "Referência " + esc(r.referencia) + " <b>" + esc(r.proporcaoReferencia) + "</b>" + (r.nota ? " · " + esc(r.nota) : "");
    GI.charts.line("g-hse", { labels: h.evolucao.map(function (e) { return mes(e.mes); }), ariaLabel: "Evolução mensal da TF e da TRIF",
      series: [{ label: "TF (com afastamento)", data: h.evolucao.map(function (e) { return e.tf; }), color: "chart-1" },
        { label: "TRIF (registráveis)", data: h.evolucao.map(function (e) { return e.trif; }), color: "chart-2" }] });
  }

  /* ---------------- Montagem ---------------- */
  /* Encaixe na folha: se o corpo passar da altura útil, reduz a fonte até caber (mínimo 6,4 pt) */
  function ajustar() {
    Array.prototype.forEach.call(document.querySelectorAll(".folha"), function (f) {
      var corpo = f.querySelector(".folha__corpo"), fs = 8.6, guarda = 0;
      while (corpo.scrollHeight > corpo.clientHeight + 1 && fs > 6.4 && guarda++ < 12) {
        fs = Math.round((fs - 0.3) * 10) / 10;
        f.style.setProperty("--rel-fs", fs + "pt");
      }
    });
  }
  function paginar() {
    var ps = document.querySelectorAll("[data-pagina]");
    Array.prototype.forEach.call(ps, function (el, k) { el.textContent = "Página " + (k + 1) + " de " + ps.length; });
  }
  function render() {
    var sec = dados.secoes, html = "", graficos = [];
    if (portfolio() && dados.carteira) { html += folhaCarteira(); graficos.push(graficosCarteira); }
    if (sec.indexOf("planejamento") >= 0) { html += folhaPlanejamentoKpis() + folhaPlanejamentoRelato(); graficos.push(graficosPlanejamento); }
    if (sec.indexOf("financeiro") >= 0) { html += folhaFinanceiro(); graficos.push(graficosFinanceiro); }
    if (sec.indexOf("suprimentos") >= 0) { html += folhaSuprimentos(); graficos.push(graficosSuprimentos); }
    if (sec.indexOf("riscos") >= 0) { html += folhaRiscos(); graficos.push(graficosRiscos); }
    if (sec.indexOf("qualidade") >= 0 && dados.qualidade) { html += folhaQualidade(); graficos.push(graficosQualidade); }
    if (sec.indexOf("hse") >= 0 && dados.hse) { html += folhaHse(); graficos.push(graficosHse); }
    document.getElementById("folhas").innerHTML = html;
    graficos.forEach(function (g) { g(); });
    paginar();
    ajustar();
    var per = dados.periodo;
    document.getElementById("rel-titulo").textContent = "Relatório gerencial " + nomeTipo() + (portfolio() ? " do portfólio" : " · " + dados.projeto.codigo);
    document.getElementById("rel-sub").textContent = per.rotulo + " · " + U.plural(document.querySelectorAll(".folha").length, "página", "páginas") + " A4 na horizontal";
    document.title = "Relatório gerencial " + nomeTipo() + " | Gestão Integrada AMT";
    if (per.emAndamento) {
      document.getElementById("aviso").innerHTML = '<div class="alert alert--info">' + U.icone("info") + '<div class="alert__body">Período em andamento: os dados vão até a data de referência (' +
        esc(F.data(dados.referencia)) + ").</div></div>";
    }
  }

  function erro(msg) {
    document.getElementById("folhas").innerHTML = "";
    document.getElementById("aviso").innerHTML = '<div class="alert alert--danger">' + U.icone("alertTriangle") + '<div class="alert__body">' + esc(msg) +
      ' <a href="index.html?relatorio=1&escopo=' + encodeURIComponent(escopoParam()) + '">Escolher o período de novo</a>.</div></div>';
  }

  /* Exportação Excel: indicadores e tabelas de cada seção */
  GI.exportar.registrar(function () {
    if (!dados) return null;
    var blocos = [];
    Array.prototype.forEach.call(document.querySelectorAll(".folha"), function (f) {
      var secao = f.querySelector(".folha__secao").childNodes[0].textContent.trim();
      var itens = Array.prototype.map.call(f.querySelectorAll(".rel-kpi"), function (k) {
        return { rotulo: secao + " · " + k.querySelector(".rel-kpi__rotulo").textContent, valor: k.querySelector(".rel-kpi__valor").textContent };
      });
      if (itens.length) blocos.push({ tipo: "kpis", titulo: secao + " (indicadores)", itens: itens });
      Array.prototype.forEach.call(f.querySelectorAll(".rel-tabela:not(.rel-tabela--desvios)"), function (t) {
        var titulo = t.querySelector("caption").textContent;
        var colunas = Array.prototype.map.call(t.querySelectorAll("thead th"), function (th) { return { titulo: th.textContent, tipo: "texto" }; });
        var linhas = Array.prototype.map.call(t.querySelectorAll("tbody tr"), function (tr) { return Array.prototype.map.call(tr.children, function (td) { return td.textContent.replace(/\s+/g, " ").trim(); }); });
        blocos.push({ tipo: "tabela", titulo: titulo, dados: { colunas: colunas, bruto: linhas, texto: linhas } });
      });
    });
    var an = [], dv = [];
    Object.keys(dados.analises || {}).forEach(function (k) {
      var a = dados.analises[k];
      an.push([a.nomeModulo, dados.periodo.tipo, dados.periodo.rotulo, a.registro ? a.registro.analise : "Não registrada",
        a.registro ? F.data(a.registro.atualizadoEm.slice(0, 10)) + " · " + U.pessoa(a.registro.atualizadoPorId) : ""]);
      a.desvios.forEach(function (d) { dv.push([a.nomeModulo, d.indicador, GI.analise.textoDesvio(d), d.comentario || (a.obrigatorio ? "Comentário pendente" : "")]); });
    });
    if (an.length) blocos.push({ tipo: "tabela", titulo: "Análises do período", dados: { colunas: [{ titulo: "Módulo" }, { titulo: "Tipo" }, { titulo: "Período" }, { titulo: "Análise" }, { titulo: "Atualizada" }], bruto: an, texto: an } });
    if (dv.length) blocos.push({ tipo: "tabela", titulo: "Desvios negativos e comentários", dados: { colunas: [{ titulo: "Módulo" }, { titulo: "Indicador" }, { titulo: "Desvio" }, { titulo: "Comentário" }], bruto: dv, texto: dv } });
    return { titulo: "Relatório gerencial " + nomeTipo() + (portfolio() ? " do portfólio" : ""), subtitulo: (portfolio() ? "Portfólio de projetos" : dados.projeto.codigo + " " + dados.projeto.nome) + " · " + dados.periodo.rotulo,
      arquivo: "relatorio-gerencial-" + (portfolio() ? "portfolio" : dados.projeto.codigo) + "-" + dados.periodo.periodo, orientacao: "l", blocos: blocos };
  });

  document.getElementById("btn-imprimir").addEventListener("click", function () { window.print(); });

  /* Escopo do relatório: ?escopo=portfolio|<id>; sem o parâmetro, vale o escopo atual das telas */
  function escopoParam() {
    var e = U.param("escopo");
    if (e) return e;
    var id = GI.api.projetoAtualId();
    return id == null ? "portfolio" : String(id);
  }
  function escopoId() { var e = escopoParam(); return e === "portfolio" ? null : Number(e); }

  if (window.Chart) { Chart.defaults.animation = false; Chart.defaults.devicePixelRatio = 2; }
  GI.util.pronto().then(function () {
    GI.ui.init(document);
    var tipo = U.param("tipo") || "Semanal";
    var periodo = U.param("periodo") || GI.api.periodoPadraoRelatorio(tipo);
    var secoes = (U.param("secoes") || "").split(",").filter(Boolean);
    document.getElementById("btn-alterar").href = "index.html?relatorio=1&escopo=" + encodeURIComponent(escopoParam()) + "&tipo=" + encodeURIComponent(tipo) + "&periodo=" + encodeURIComponent(periodo);
    var id = escopoId(), nada = function () { return null; };
    return Promise.all([
      GI.api.relatorioGerencial(id, { tipo: tipo, periodo: periodo, secoes: secoes }),
      GI.api.parametros().catch(nada), GI.api.financeiro.mapaControle(id).catch(nada), GI.api.financeiro.contingencia(id).catch(nada),
      GI.api.riscos.lista(id).catch(nada), GI.api.suprimentos.pacotes(id).catch(nada)
    ]).then(function (r) {
      ref = { par: r[1], mapa: r[2], cont: r[3], riscos: r[4], pacotes: r[5], hseAnterior: null };
      dados = r[0];
      /* HSE: acumulado até o mês anterior (referência das observações comportamentais, como no painel HSE) */
      var h = dados.hse;
      if (!h || !h.mes) return;
      var y = Number(h.mes.slice(0, 4)), mm = Number(h.mes.slice(5, 7)) - 1;
      if (mm < 1) { y--; mm = 12; }
      var mesAnt = y + "-" + (mm < 10 ? "0" : "") + mm;
      if (mesAnt < h.primeiroMes) return;
      return GI.api.hse.indicadores(id, { inicio: h.primeiroMes, fim: mesAnt }).then(function (x) { ref.hseAnterior = x; }, nada);
    }).then(function () { render(); });
  }).catch(function (e) {
    erro(e && e.erros ? e.erros.map(function (x) { return x.msg || x; }).join(" ") : "Não foi possível montar o relatório.");
    if (window.console && !(e && e.erros)) console.error(e);
  });
})(window.GI = window.GI || {});
