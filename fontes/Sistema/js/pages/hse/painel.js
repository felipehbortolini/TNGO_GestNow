/* ==========================================================================
   HSE > Painel HSE (07)
   Pirâmide de Heinrich/Bird, taxas reativas (NBR 14280) e indicadores
   proativos, evolução mensal (TF/TRIF), distribuição por área e por empresa.
   Filtro de mês e ano: "No mês selecionado" mostra só o mês escolhido;
   "Acumulado" soma desde o primeiro mês com HHT até o mês escolhido
   (mesmo critério de "acumulado" usado em Financeiro e Planejamento).
   ========================================================================== */
(function (GI) {
  "use strict";

  var U = GI.util, F = GI.fmt, API = GI.api.hse;
  var projetoId, referencia = "bird";
  var meses = [], mesSelecionado = null, anoSelecionado = null;
  var dadosMes = null, dadosAcum = null, indAnterior = null;
  var META_ACOES_PRAZO = 90; /* mesmo limiar da cor do card "Ações HSE no prazo" */
  var ZERO = { rotulo: "Esperado", valor: "0" };
  /* Rótulos curtos da pirâmide (plural: a faixa mostra a contagem do nível) */
  var ROTULOS_PIRAMIDE = ["Lesões graves", "Lesões leves", "Danos materiais", "Quase acidentes", "Desvios"];

  function popularFiltros() {
    var anos = [];
    meses.forEach(function (m) { var a = m.slice(0, 4); if (anos.indexOf(a) < 0) anos.push(a); });
    document.getElementById("f-ano").innerHTML = anos.map(function (a) {
      return '<option value="' + a + '"' + (a === anoSelecionado ? " selected" : "") + ">" + a + "</option>";
    }).join("");
    var mesesDoAno = meses.filter(function (m) { return m.slice(0, 4) === anoSelecionado; });
    document.getElementById("f-mes").innerHTML = mesesDoAno.map(function (m) {
      return '<option value="' + m + '"' + (m === mesSelecionado ? " selected" : "") + ">" + U.mesCurto(m).split("/")[0] + "</option>";
    }).join("");
  }

  /* Dias desde o início do projeto (ou da carteira) até a data de referência: com zero
     acidentes com afastamento, todos os dias seriam sem afastamento. */
  function diasEsperadosSemAfastamento() {
    var ps = GI.api.portfolio.projetos().filter(function (p) { return projetoId == null || p.id === projetoId; });
    var ini = ps.reduce(function (m, p) { return p.inicio && (!m || p.inicio < m) ? p.inicio : m; }, null);
    if (!ini) return null;
    var dia = function (iso) { var x = iso.slice(0, 10).split("-"); return Date.UTC(+x[0], +x[1] - 1, +x[2]); };
    return Math.max(0, Math.round((dia(GI.api.referencia()) - dia(ini)) / 86400000));
  }

  function kpisReativos(ind, rodapeAcidente, rodapeHipo) {
    return [
      U.kpi({ rotulo: "Taxa de frequência (TF)", valor: ind.tf == null ? "·" : F.indice(ind.tf), icone: "alertTriangle", cor: ind.lti ? "danger" : "success", esperado: { rotulo: "Esperado", valor: F.indice(0) },
        rodape: U.plural(ind.lti, "acidente com afastamento", "acidentes com afastamento") + " " + rodapeAcidente }),
      U.kpi({ rotulo: "Lesões registráveis (TRIF)", valor: ind.trif == null ? "·" : F.indice(ind.trif), icone: "octagonAlert", cor: ind.registraveis ? "warning" : "success", esperado: { rotulo: "Esperado", valor: F.indice(0) },
        rodape: U.plural(ind.registraveis, "lesão registrável", "lesões registráveis") }),
      U.kpi({ rotulo: "Taxa de gravidade (TG)", valor: ind.tg == null ? "·" : F.num(ind.tg, 1), icone: "gauge", cor: "info", esperado: { rotulo: "Esperado", valor: F.num(0, 1) }, rodape: "dias perdidos e debitados x base / HHT" }),
      U.kpi({ rotulo: "Alto potencial (HiPo)", valor: F.num(ind.hipo), icone: "star", cor: ind.hipo ? "danger" : "success", esperado: ZERO, rodape: U.plural(ind.hipo, "ocorrência") + " " + rodapeHipo })
    ].join("");
  }

  function render() {
    var indMes = dadosMes.indicadores, indAcum = dadosAcum.indicadores;
    var diasEsperados = diasEsperadosSemAfastamento();

    document.getElementById("periodo").textContent = "Mês: " + U.mesCurto(mesSelecionado) + " · Acumulado: " + U.mesCurto(indAcum.periodo.inicio) +
      " a " + U.mesCurto(indAcum.periodo.fim) + " · base " + F.num(indAcum.base) + " HHT (" + (indAcum.base === 1000000 ? "NBR 14280" : "OSHA") + ")";

    document.getElementById("kpis-mes").innerHTML = kpisReativos(indMes, "no mês", "no mês");

    document.getElementById("kpis").innerHTML = kpisReativos(indAcum, "no acumulado", "no acumulado") + [
      U.kpi({ rotulo: "Dias sem afastamento", valor: F.num(indAcum.diasSemAfastamento || 0), icone: "calendarClock", cor: "primary",
        esperado: { rotulo: "Esperado", valor: diasEsperados == null ? "·" : F.num(diasEsperados) },
        rodape: indAcum.ultimaLTI ? "última LTI em " + F.data(indAcum.ultimaLTI) :
          indAcum.inicioContagem ? (projetoId == null ? "desde o início da carteira (" : "desde o início do projeto (") + F.data(indAcum.inicioContagem) + ")" : "nenhum acidente com afastamento registrado" }),
      U.kpi({ rotulo: "Ações HSE no prazo", valor: indAcum.acoesNoPrazoPct == null ? "·" : F.pct(indAcum.acoesNoPrazoPct), icone: "checkCircle", cor: indAcum.acoesNoPrazoPct >= META_ACOES_PRAZO ? "success" : "warning",
        esperado: { rotulo: "Meta", valor: "≥ " + F.pct(META_ACOES_PRAZO, 0) } })
    ].join("");

    var niveis = function (piramide) { return piramide.map(function (v, i) { return { label: ROTULOS_PIRAMIDE[i], value: v }; }); };
    var resAcum = GI.charts.pyramidPair("piramides", { reference: referencia,
      esquerda: { titulo: "Mês: " + U.mesCurto(mesSelecionado), levels: niveis(indMes.piramide) },
      direita: { titulo: "Acumulado: " + U.mesCurto(indAcum.periodo.inicio) + " a " + U.mesCurto(indAcum.periodo.fim), levels: niveis(indAcum.piramide) } });
    /* Referência numa linha só, no mesmo formato da proporção real de cada pirâmide */
    document.getElementById("nota-piramide").innerHTML = resAcum ? "<span>Referência " + U.esc(resAcum.referencia) + "</span> <b>" +
      U.esc(resAcum.proporcaoReferencia) + "</b>" + (resAcum.nota ? " <span>" + U.esc(resAcum.nota) + "</span>" : "") : "";

    /* Proativos depois da pirâmide: o relato de quase acidentes usa a razão de referência (Bird ou Heinrich) */
    document.getElementById("proativos").innerHTML = [
      U.kpi({ rotulo: "DDS realizados", valor: indAcum.ddsPct == null ? "·" : F.pct(indAcum.ddsPct), icone: "calendarDays", cor: "info", esperado: { rotulo: "Meta", valor: F.pct(100, 0) } }),
      U.kpi({ rotulo: "Conformidade em inspeções", valor: indAcum.conformidadeInspecoesPct == null ? "·" : F.pct(indAcum.conformidadeInspecoesPct), icone: "clipboardCheck", cor: "info", esperado: { rotulo: "Esperado", valor: F.pct(100, 0) } }),
      U.kpi({ rotulo: "Observações / 10 mil HHT", valor: indAcum.observacoesPor10k == null ? "·" : F.num(indAcum.observacoesPor10k, 1), icone: "eye", cor: "info",
        esperado: { rotulo: "Meta", valor: "≥ " + F.num(API.metas().observacoesPor10MilHht) } }),
      U.kpi({ rotulo: "Relato de quase acidentes", valor: indAcum.relatoQuaseAcidente == null ? "·" : F.num(indAcum.relatoQuaseAcidente, 1), icone: "search", cor: "info",
        esperado: { rotulo: "Referência", valor: resAcum && resAcum.referenciaQuaseAcidente != null ? F.num(resAcum.referenciaQuaseAcidente, 1) : "·" },
        rodape: "quase acidentes por lesão registrável" }),
      U.kpi({ rotulo: "Recomendações fechadas (APR/HAZOP)", valor: indAcum.recomendacoesFechadasPct == null ? "·" : F.pct(indAcum.recomendacoesFechadasPct), icone: "fileSearch", cor: "info", esperado: { rotulo: "Esperado", valor: F.pct(100, 0) } }),
      U.kpi({ rotulo: "Incidentes ambientais", valor: F.num(indAcum.ambientais), icone: "octagonAlert", cor: indAcum.ambientais ? "warning" : "success", esperado: ZERO })
    ].join("");

    GI.charts.line("g-evolucao", {
      labels: dadosAcum.evolucao.map(function (e) { return U.mesCurto(e.mes); }),
      series: [
        { label: "TF (com afastamento)", data: dadosAcum.evolucao.map(function (e) { return e.tf; }), color: "chart-1" },
        { label: "TRIF (registráveis)", data: dadosAcum.evolucao.map(function (e) { return e.trif; }), color: "chart-2" }
      ]
    });

    function lista(elId, itens, rotular) {
      var max = itens.reduce(function (m, x) { return Math.max(m, x.total); }, 0) || 1;
      document.getElementById(elId).innerHTML = itens.length ? '<ul class="mov">' + itens.slice(0, 8).map(function (x) {
        return '<li><div class="mov__row"><span class="mov__id">' + U.esc(rotular(x.chave)) + '</span>' +
          '<span class="mov__trilho" aria-hidden="true"><span class="mov__barra" style="width:' + (x.total / max * 100) + '%"></span></span>' +
          '<span class="mov__val">' + x.total + "</span></div></li>";
      }).join("") + "</ul>" : U.vazio("Nenhuma ocorrência no período.", "pieChart");
    }
    lista("por-area", dadosAcum.porArea, function (a) { return a; });
    lista("por-empresa", dadosAcum.porEmpresa, function (id) { return U.empresa(id); });
  }

  function atualizarDados() {
    if (!mesSelecionado) return Promise.resolve();
    var primeiroMes = meses.length ? meses[0] : mesSelecionado;
    var mesAnterior = meses[meses.indexOf(mesSelecionado) - 1] || null;
    return Promise.all([
      API.painel(projetoId, { inicio: mesSelecionado, fim: mesSelecionado }),
      API.painel(projetoId, { inicio: primeiroMes, fim: mesSelecionado }),
      /* Acumulado até o mês anterior: referência dos proativos sem meta parametrizada */
      mesAnterior ? API.indicadores(projetoId, { inicio: primeiroMes, fim: mesAnterior }) : Promise.resolve(null)
    ]).then(function (r) { dadosMes = r[0]; dadosAcum = r[1]; indAnterior = r[2]; render(); });
  }

  function carregar() {
    return API.painel(projetoId, null).then(function (geral) {
      meses = geral.evolucao.map(function (e) { return e.mes; });
      if (!mesSelecionado || meses.indexOf(mesSelecionado) < 0) mesSelecionado = meses.length ? meses[meses.length - 1] : null;
      anoSelecionado = mesSelecionado ? mesSelecionado.slice(0, 4) : "";
      popularFiltros();
      return atualizarDados();
    });
  }

  GI.exportar.registrar(function () {
    var indMes = dadosMes.indicadores, indAcum = dadosAcum.indicadores;
    return {
      titulo: "Painel HSE", subtitulo: U.projeto(projetoId) ? U.projeto(projetoId).codigo + " " + U.projeto(projetoId).nome : "Portfólio de projetos", arquivo: "painel-hse",
      blocos: [
        { tipo: "kpis", titulo: "Indicadores reativos · mês", itens: Array.prototype.map.call(document.querySelectorAll("#kpis-mes .kpi"), function (k) {
          return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" }; }) },
        { tipo: "kpis", titulo: "Indicadores reativos · acumulado", itens: Array.prototype.map.call(document.querySelectorAll("#kpis .kpi"), function (k) {
          return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" }; }) },
        { tipo: "kpis", titulo: "Indicadores proativos", itens: Array.prototype.map.call(document.querySelectorAll("#proativos .kpi"), function (k) {
          return { rotulo: k.querySelector(".kpi__label").textContent, valor: k.querySelector(".kpi__value").textContent, esperado: k.querySelector(".kpi__esperado") ? k.querySelector(".kpi__esperado").textContent.replace(/\s+/g, " ").trim() : "" }; }) },
        { tipo: "tabela", titulo: "Pirâmide de segurança · mês", dados: {
          colunas: [{ titulo: "Nível", tipo: "texto" }, { titulo: "Ocorrências", tipo: "num" }],
          bruto: indMes.piramide.map(function (v, i) { return [(i + 1) + ". " + API.NIVEIS_NOMES[i], v]; }),
          texto: indMes.piramide.map(function (v, i) { return [(i + 1) + ". " + API.NIVEIS_NOMES[i], String(v)]; }) } },
        { tipo: "tabela", titulo: "Pirâmide de segurança · acumulado", dados: {
          colunas: [{ titulo: "Nível", tipo: "texto" }, { titulo: "Ocorrências", tipo: "num" }],
          bruto: indAcum.piramide.map(function (v, i) { return [(i + 1) + ". " + API.NIVEIS_NOMES[i], v]; }),
          texto: indAcum.piramide.map(function (v, i) { return [(i + 1) + ". " + API.NIVEIS_NOMES[i], String(v)]; }) } },
        { tipo: "grafico", titulo: "Evolução mensal (TF e TRIF)", canvas: document.getElementById("g-evolucao") },
        { tipo: "tabela", titulo: "Ocorrências por área", dados: {
          colunas: [{ titulo: "Área", tipo: "texto" }, { titulo: "Ocorrências", tipo: "num" }],
          bruto: dadosAcum.porArea.map(function (a) { return [a.chave, a.total]; }), texto: dadosAcum.porArea.map(function (a) { return [a.chave, String(a.total)]; }) } },
        { tipo: "tabela", titulo: "Ocorrências por empresa", dados: {
          colunas: [{ titulo: "Empresa", tipo: "texto" }, { titulo: "Ocorrências", tipo: "num" }],
          bruto: dadosAcum.porEmpresa.map(function (a) { return [U.empresa(a.chave), a.total]; }), texto: dadosAcum.porEmpresa.map(function (a) { return [U.empresa(a.chave), String(a.total)]; }) } }
      ]
    };
  });

  document.addEventListener("segmented:change", function (ev) {
    if (!ev.target.closest("#f-referencia")) return;
    referencia = ev.detail.value;
    if (dadosMes && dadosAcum) render();
  });

  document.addEventListener("change", function (ev) {
    if (ev.target.id === "f-ano") {
      anoSelecionado = ev.target.value;
      var mesesDoAno = meses.filter(function (m) { return m.slice(0, 4) === anoSelecionado; });
      mesSelecionado = mesesDoAno.length ? mesesDoAno[mesesDoAno.length - 1] : mesSelecionado;
      popularFiltros();
      atualizarDados();
    } else if (ev.target.id === "f-mes") {
      mesSelecionado = ev.target.value;
      atualizarDados();
    }
  });

  GI.hse.pronto().then(function (param) {
    referencia = param.referenciaPiramide || "bird";
    document.querySelectorAll("#f-referencia .segmented__opt").forEach(function (o) { o.setAttribute("aria-pressed", String(o.getAttribute("data-value") === referencia)); });
    projetoId = GI.hse.projeto(function (id) { projetoId = id; carregar(); });
    return carregar();
  });
})(window.GI = window.GI || {});
