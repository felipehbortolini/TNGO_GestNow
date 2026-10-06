/* ==========================================================================
   charts.js | Chart.js com cores lidas de css/tokens.css (nenhuma cor aqui)

   Regras de desenho (skill de visualização adotada no projeto):
     * categórica em ordem fixa: --chart-1..4; excedente vira "Outros" (--chart-outros)
     * linhas de 2px, marcadores de 8px com anel da cor da superfície
     * barras com no máximo 24px, ponta arredondada de 4px e base reta
     * grade de 1px, contínua e discreta; um único eixo Y
     * legenda HTML sempre presente com 2 ou mais séries; texto nunca na cor da série
     * dica (tooltip) ao passar o mouse em todos os gráficos

   API:
     GI.charts.line(canvas, { labels, series:[{label, data, color:"chart-1", dashed, fill}], percent, max })
     GI.charts.bar(canvas,  { labels, series:[...], horizontal, stacked, percent, max })
     GI.charts.sCurve(canvas, { labels, baseline, real, forecast })
     GI.charts.sCurveFinanceira(canvas, { labels, planejado, comprometido, realizado, projecao, rotuloProjecao })  (centavos)
     GI.charts.waterfall(canvas, { steps:[{label, value, type}] })                      (centavos)
     GI.charts.pyramid(div, { levels:[{label, sub, value}], reference:"bird"|"heinrich" })
     GI.charts.pyramidPair(div, { reference, esquerda:{titulo, levels}, direita:{titulo, levels} })
     Opção money:true em line/bar: valores em centavos, formatados em R$ só na exibição.
   Opções min e max fixam o eixo de valores (ex.: SPI de 0,8 a 1,1).
     GI.charts.token("chart-1")  -> valor calculado da variável CSS
   "color" recebe o NOME do token (sem "--"); nunca um hexadecimal.
   ========================================================================== */
(function (GI) {
  "use strict";

  var registro = {};

  function token(nome) {
    return getComputedStyle(document.documentElement).getPropertyValue("--" + nome).trim();
  }

  function paleta() {
    return {
      cat: ["chart-1", "chart-2", "chart-3", "chart-4"],
      outros: "chart-outros",
      grid: token("chart-grid"),
      axis: token("chart-axis"),
      surface: token("chart-surface"),
      tooltipBg: token("chart-tooltip-bg"),
      tooltipFg: token("chart-tooltip-fg"),
      text: token("text-default"),
      fontText: token("font-text") || "Roboto, sans-serif"
    };
  }

  function aplicarPadroes() {
    if (!window.Chart) return false;
    var p = paleta();
    Chart.defaults.font.family = p.fontText;
    Chart.defaults.font.size = 12;
    Chart.defaults.color = p.axis;
    Chart.defaults.borderColor = p.grid;
    Chart.defaults.locale = (GI.i18n ? GI.i18n.locale : "pt-BR");
    Chart.defaults.maintainAspectRatio = false;
    Chart.defaults.responsive = true;
    Chart.defaults.plugins.legend.display = false;   // usamos legenda HTML
    var tt = Chart.defaults.plugins.tooltip;
    tt.backgroundColor = p.tooltipBg;
    tt.titleColor = p.tooltipFg;
    tt.bodyColor = p.tooltipFg;
    tt.padding = 10;
    tt.cornerRadius = 8;
    tt.boxPadding = 4;
    tt.usePointStyle = true;
    return true;
  }

  function fmtNum(v, pct, casas) {
    var s = Number(v).toLocaleString((GI.i18n ? GI.i18n.locale : "pt-BR"), { minimumFractionDigits: casas || 0, maximumFractionDigits: casas == null ? 1 : casas });
    return pct ? s + "%" : s;
  }

  /* Valores financeiros chegam em CENTAVOS (inteiros) e só são formatados aqui */
  var moedaCheia = new Intl.NumberFormat((GI.i18n ? GI.i18n.locale : "pt-BR"), { style: "currency", currency: "BRL" });
  var moedaCompacta = new Intl.NumberFormat((GI.i18n ? GI.i18n.locale : "pt-BR"), { style: "currency", currency: "BRL", notation: "compact", maximumFractionDigits: 1 });
  function fmtValor(v, cfg, compacto) {
    if (v == null) return "";
    if (cfg.money) return (compacto ? moedaCompacta : moedaCheia).format(Number(v) / 100);
    return fmtNum(v, cfg.percent, cfg.casas);
  }

  function eixos(cfg, p) {
    var valor = {
      beginAtZero: cfg.min == null,
      min: cfg.min,
      max: cfg.max,
      stacked: !!cfg.stacked,
      grid: { color: p.grid, lineWidth: 1, drawTicks: false },
      border: { display: false },
      ticks: { color: p.axis, padding: 8, precision: cfg.money || cfg.percent || cfg.casas != null ? undefined : 0,
        callback: function (v) { return fmtValor(v, cfg, true); } }
    };
    var categoria = {
      stacked: !!cfg.stacked,
      grid: { display: false },
      border: { color: p.grid },
      ticks: { color: p.axis, padding: 6, autoSkip: true, maxRotation: 0 }
    };
    return cfg.horizontal ? { x: valor, y: categoria } : { x: categoria, y: valor };
  }

  /* Legenda HTML antes do contêiner .chart (identidade nunca só pela cor) */
  function legenda(canvas, itens) {
    var box = canvas.closest(".chart") || canvas.parentNode;
    var anterior = box.previousElementSibling;
    if (anterior && anterior.classList.contains("legend") && anterior.hasAttribute("data-auto")) anterior.remove();
    if (itens.length < 2) return;
    var ul = document.createElement("ul");
    ul.className = "legend";
    ul.setAttribute("data-auto", "");
    itens.forEach(function (it) {
      var li = document.createElement("li");
      li.className = "legend__item";
      var key = document.createElement("span");
      key.className = "legend__key" + (it.dashed ? " legend__key--dashed" : "") + (it.box ? " legend__key--box" : "");
      key.style.setProperty("--key", "var(--" + it.color + ")");
      li.appendChild(key);
      li.appendChild(document.createTextNode(it.label));
      ul.appendChild(li);
    });
    box.parentNode.insertBefore(ul, box);
  }

  function montar(canvas, config, itensLegenda, rotulo) {
    if (!aplicarPadroes()) {
      console.warn("[charts] Chart.js não carregado.");
      return null;
    }
    var el = typeof canvas === "string" ? document.getElementById(canvas) : canvas;
    if (!el) return null;
    var chave = el.id || (el.id = "chart-" + Math.random().toString(36).slice(2, 8));
    if (registro[chave]) registro[chave].destroy();
    el.setAttribute("role", "img");
    if (rotulo) el.setAttribute("aria-label", rotulo);
    legenda(el, itensLegenda);
    registro[chave] = new Chart(el, config);
    return registro[chave];
  }

  function corSerie(s, i, p) {
    return s.color || (i < p.cat.length ? p.cat[i] : p.outros);
  }

  /* Idioma: rótulos de categorias, séries e descrição passam pelo dicionário */
  function tr(x) { return GI.t && typeof x === "string" ? GI.t(x) : x; }
  function traduzirCfg(cfg) {
    var c = {};
    Object.keys(cfg).forEach(function (k) { c[k] = cfg[k]; });
    if (c.labels) c.labels = c.labels.map(tr);
    if (c.series) c.series = c.series.map(function (s) { var x = {}; Object.keys(s).forEach(function (k) { x[k] = s[k]; }); x.label = tr(s.label); return x; });
    if (c.steps) c.steps = c.steps.map(function (s) { var x = {}; Object.keys(s).forEach(function (k) { x[k] = s[k]; }); x.label = tr(s.label); return x; });
    if (c.ariaLabel) c.ariaLabel = tr(c.ariaLabel);
    return c;
  }

  function line(canvas, cfg) {
    cfg = traduzirCfg(cfg);
    var p = paleta();
    var itens = [];
    var datasets = cfg.series.map(function (s, i) {
      var nome = corSerie(s, i, p);
      var cor = token(nome);
      itens.push({ label: s.label, color: nome, dashed: s.dashed });
      return {
        label: s.label,
        data: s.data,
        borderColor: cor,
        backgroundColor: s.fill ? token(s.fillToken || "chart-area-real") : cor,
        fill: !!s.fill,
        borderWidth: 2,
        borderDash: s.dashed ? [6, 4] : [],
        pointRadius: s.points === false ? 0 : 4,
        pointHoverRadius: 6,
        pointBackgroundColor: cor,
        pointBorderColor: p.surface,
        pointBorderWidth: 2,
        pointHitRadius: 12,
        tension: s.tension == null ? 0.25 : s.tension,
        spanGaps: false
      };
    });
    return montar(canvas, {
      type: "line",
      data: { labels: cfg.labels, datasets: datasets },
      options: {
        interaction: { mode: "index", intersect: false },
        scales: eixos(cfg, p),
        plugins: {
          tooltip: {
            callbacks: {
              label: function (c) { return " " + c.dataset.label + ": " + fmtValor(c.parsed.y, cfg); }
            },
            filter: function (c) { return c.parsed.y != null; }
          }
        }
      }
    }, itens, cfg.ariaLabel);
  }

  function bar(canvas, cfg) {
    cfg = traduzirCfg(cfg);
    var p = paleta();
    var itens = [];
    var datasets = cfg.series.map(function (s, i) {
      var nome = corSerie(s, i, p);
      itens.push({ label: s.label, color: nome, box: true });
      return {
        label: s.label,
        data: s.data,
        backgroundColor: token(nome),
        hoverBackgroundColor: token(nome),
        borderColor: p.surface,
        borderWidth: cfg.stacked ? (cfg.horizontal ? { right: 2 } : { top: 2 }) : 0,
        borderRadius: cfg.stacked ? 0 : 4,
        borderSkipped: "start",
        maxBarThickness: 24,
        categoryPercentage: 0.7,
        barPercentage: 0.9
      };
    });
    return montar(canvas, {
      type: "bar",
      data: { labels: cfg.labels, datasets: datasets },
      options: {
        indexAxis: cfg.horizontal ? "y" : "x",
        interaction: { mode: "nearest", intersect: true },
        scales: eixos(cfg, p),
        plugins: {
          tooltip: {
            callbacks: {
              label: function (c) {
                var v = cfg.horizontal ? c.parsed.x : c.parsed.y;
                return " " + c.dataset.label + ": " + fmtValor(v, cfg);
              }
            }
          }
        }
      }
    }, itens, cfg.ariaLabel);
  }

  /* Curva S: Baseline (tracejada), Real (contínua com área), Tendência (tracejada,
     começa no último ponto real). Eixo Y em % acumulado, 0 a 100. */
  function sCurve(canvas, cfg) {
    return line(canvas, {
      labels: cfg.labels,
      percent: true,
      max: 100,
      ariaLabel: cfg.ariaLabel || "Curva S: percentual acumulado previsto, real e tendência por período",
      series: [
        { label: "Baseline", data: cfg.baseline, color: "chart-baseline", dashed: true, points: false },
        { label: "Real", data: cfg.real, color: "chart-real", fill: true },
        { label: "Tendência (forecast)", data: cfg.forecast, color: "chart-forecast", dashed: true }
      ]
    });
  }

  /* Curva S financeira: CAPEX acumulado em centavos (Planejado, Comprometido, Realizado) */
  function sCurveFinanceira(canvas, cfg) {
    return line(canvas, {
      labels: cfg.labels,
      money: true,
      ariaLabel: cfg.ariaLabel || "Curva S financeira: CAPEX planejado, comprometido e realizado acumulados por mês",
      series: [
        { label: "Planejado", data: cfg.planejado, color: "chart-capex-planejado", dashed: true, points: false },
        { label: "Comprometido", data: cfg.comprometido, color: "chart-capex-comprometido" },
        { label: "Realizado", data: cfg.realizado, color: "chart-capex-realizado", fill: true }
      ].concat(cfg.projecao ? [{ label: cfg.rotuloProjecao || "Projeção", data: cfg.projecao, color: "chart-forecast", dashed: true }] : [])
    });
  }

  /* Cascata (waterfall): passos { label, value (centavos), type: "total" | "aumento" | "reducao" }.
     "total" sem value usa o acumulado até ali. Barras flutuantes [início, fim]. */
  function waterfall(canvas, cfg) {
    cfg = traduzirCfg(cfg);
    var p = paleta();
    var cores = { total: "chart-cascata-total", aumento: "chart-cascata-aumento", reducao: "chart-cascata-reducao" };
    var acumulado = 0, faixas = [], tipos = [], valores = [];
    cfg.steps.forEach(function (st) {
      var v = Math.round(Number(st.value || 0));
      if (st.type === "total") {
        if (st.value != null) acumulado = v;
        faixas.push([0, acumulado]); valores.push(acumulado);
      } else if (st.type === "aumento") {
        faixas.push([acumulado, acumulado + v]); acumulado += v; valores.push(v);
      } else {
        faixas.push([acumulado - v, acumulado]); acumulado -= v; valores.push(-v);
      }
      tipos.push(st.type);
    });
    var itens = [
      { label: cfg.labelTotal || "Total", color: cores.total, box: true },
      { label: cfg.labelAumento || "Acréscimo", color: cores.aumento, box: true },
      { label: cfg.labelReducao || "Redução", color: cores.reducao, box: true }
    ];
    return montar(canvas, {
      type: "bar",
      data: {
        labels: cfg.steps.map(function (st) { return st.label; }),
        datasets: [{
          label: cfg.title || "Cascata",
          data: faixas,
          backgroundColor: tipos.map(function (t) { return token(cores[t]); }),
          borderRadius: 4,
          borderSkipped: false,
          maxBarThickness: 48,
          categoryPercentage: 0.7
        }]
      },
      options: {
        interaction: { mode: "nearest", intersect: true },
        scales: (function () {
          var e = eixos({ money: true }, p);
          e.x.ticks.autoSkip = false;   /* todas as etapas rotuladas; inclina em telas estreitas */
          e.x.ticks.maxRotation = 45;
          return e;
        })(),
        plugins: {
          tooltip: {
            callbacks: {
              label: function (c) {
                var v = valores[c.dataIndex], t = tipos[c.dataIndex];
                var sinal = t === "aumento" ? "+ " : t === "reducao" ? "- " : "";
                return " " + sinal + fmtValor(Math.abs(v), { money: true });
              }
            }
          }
        }
      }
    }, itens, cfg.ariaLabel || "Gráfico em cascata do contrato");
  }

  /* Pirâmide de Heinrich/Bird (HSE). HTML/CSS, sem Chart.js.
     cfg.levels: [{ label, sub, value }] do topo (mais grave) para a base; sub vira dica (title).
     cfg.reference: "bird" (1:10:30:600) ou "heinrich" (1:29:300, sem lesão agrupado).
     Visual padronizado: faixas de altura fixa (a pirâmide tem sempre o mesmo tamanho,
     qualquer que seja o valor ou o idioma), rótulo curto numa linha e a proporção real
     numa linha única abaixo ("Real 0 : 16 : 31 : 190"), no mesmo formato da referência.
     Devolve { nota, referencia, proporcaoReal, razaoQuaseAcidente, referenciaQuaseAcidente }. */
  var REFERENCIAS = {
    bird: {
      nome: "Bird (1969)", curto: "Bird", proporcao: "1 : 10 : 30 : 600",
      nota: ""
    },
    heinrich: {
      nome: "Heinrich (1931)", curto: "Heinrich", proporcao: "1 : 29 : 300", somaNiveis: [2, 3],
      nota: "(dano material e quase acidente somados)"
    }
  };

  function escPir(t) { return String(t).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  /* Faixa trapezoidal do nível i (0 = topo) de n níveis */
  function faixaPir(valor, i, n) {
    var largura = function (k) { return 0.12 + 0.88 * k / n; }; /* largura relativa na borda k */
    var wt = largura(i), wb = largura(i + 1);
    var poly = "polygon(" + ((1 - wt) / 2 * 100).toFixed(2) + "% 0, " + ((1 + wt) / 2 * 100).toFixed(2) + "% 0, " +
               ((1 + wb) / 2 * 100).toFixed(2) + "% 100%, " + ((1 - wb) / 2 * 100).toFixed(2) + "% 100%)";
    return '<div class="pyramid__band pyramid__band--' + (i + 1) + '" style="clip-path: ' + poly + '" aria-hidden="true">' + fmtNum(valor) + "</div>";
  }
  /* Proporção real nos níveis da referência (Bird: 1 a 4; Heinrich: 1, 2 e 3+4) */
  function proporcaoPir(niveis, ref) {
    var valores = niveis.slice(0, 4).map(function (nv) { return nv.value || 0; });
    if (ref.somaNiveis) valores = [valores[0], valores[1], valores[2] + valores[3]];
    return valores.map(function (v) { return fmtNum(v); }).join(" : ");
  }
  function leituraPir(niveis, ref, proporcaoReal) {
    /* Leitura: quase acidentes por lesão (níveis 1 e 2) x referência.
       Bird compara quase acidentes; Heinrich compara eventos sem lesão (dano + quase acidente) */
    var lesoes = niveis[0].value + (niveis[1] ? niveis[1].value : 0);
    var ehBird = !ref.somaNiveis;
    var quase = (niveis[3] ? niveis[3].value : 0) + (!ehBird && niveis[2] ? niveis[2].value : 0);
    return {
      nota: ref.nota, referencia: ref.curto, proporcaoReferencia: ref.proporcao, proporcaoReal: proporcaoReal,
      razaoQuaseAcidente: lesoes ? quase / lesoes : null,
      referenciaQuaseAcidente: ehBird ? 600 / 11 : 300 / 30
    };
  }
  function ariaPir(ref, niveis) {
    return "Pirâmide de segurança com referência " + ref.nome + ": " +
      niveis.map(function (nv, i) { return (i + 1) + ". " + nv.label + " " + nv.value; }).join(", ");
  }

  function pyramid(container, cfg) {
    var el = typeof container === "string" ? document.getElementById(container) : container;
    if (!el) return null;
    var ref = REFERENCIAS[cfg.reference || "bird"] || REFERENCIAS.bird;
    var niveis = cfg.levels, n = niveis.length;
    var html = niveis.map(function (nv, i) {
      return '<div class="pyramid__row">' + faixaPir(nv.value, i, n) +
        '<span class="pyramid__label"' + (nv.sub ? ' title="' + escPir(nv.sub) + '"' : "") + ">" + escPir(nv.label) + "</span></div>";
    }).join("");
    var proporcaoReal = proporcaoPir(niveis, ref);
    html += '<p class="pyramid__ratio"><span>Real</span> <b>' + proporcaoReal + "</b></p>";
    el.innerHTML = html;
    el.setAttribute("role", "figure");
    el.setAttribute("aria-label", ariaPir(ref, niveis));
    return leituraPir(niveis, ref, proporcaoReal);
  }

  /* Par de pirâmides lado a lado (ex.: mês x acumulado) com os rótulos dos níveis
     uma única vez, na coluna central. As duas pirâmides têm sempre o mesmo tamanho.
     cfg: { reference, esquerda: { titulo, levels }, direita: { titulo, levels } }.
     Devolve a leitura da pirâmide da direita (a de maior base, em geral o acumulado). */
  function pyramidPair(container, cfg) {
    var el = typeof container === "string" ? document.getElementById(container) : container;
    if (!el) return null;
    var ref = REFERENCIAS[cfg.reference || "bird"] || REFERENCIAS.bird;
    var e = cfg.esquerda, d = cfg.direita, n = e.levels.length;
    var html = '<p class="pyramid-pair__titulo">' + escPir(e.titulo) + '</p><span aria-hidden="true"></span>' +
               '<p class="pyramid-pair__titulo">' + escPir(d.titulo) + "</p>";
    for (var i = 0; i < n; i++) {
      var nv = e.levels[i];
      html += faixaPir(nv.value, i, n) +
        '<span class="pyramid-pair__label"' + (nv.sub ? ' title="' + escPir(nv.sub) + '"' : "") + ">" + escPir(nv.label) + "</span>" +
        faixaPir(d.levels[i].value, i, n);
    }
    var propE = proporcaoPir(e.levels, ref), propD = proporcaoPir(d.levels, ref);
    html += '<p class="pyramid-pair__ratio"><span>Real</span> <b>' + propE + '</b></p><span aria-hidden="true"></span>' +
            '<p class="pyramid-pair__ratio"><span>Real</span> <b>' + propD + "</b></p>";
    el.innerHTML = html;
    el.setAttribute("role", "figure");
    el.setAttribute("aria-label", e.titulo + ". " + ariaPir(ref, e.levels) + ". " + d.titulo + ". " + ariaPir(ref, d.levels));
    return leituraPir(d.levels, ref, propD);
  }

  /* Recalcula cores se os tokens mudarem (ex.: impressão) */
  function atualizarTodos() {
    Object.keys(registro).forEach(function (k) { registro[k].update(); });
  }

  GI.charts = { token: token, line: line, bar: bar, sCurve: sCurve, sCurveFinanceira: sCurveFinanceira,
                waterfall: waterfall, pyramid: pyramid, pyramidPair: pyramidPair, atualizarTodos: atualizarTodos };
})(window.GI = window.GI || {});
