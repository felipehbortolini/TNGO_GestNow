/* ============================================================
   graficos/relogios.js — Relógios de indicadores

   Porte de "Relogios de Indicadores.html" (docs/referencia/graficos/): um
   relógio por indicador, com o arco do valor que se enche e o número que
   sobe na entrada, o marcador da meta, a pílula do estado, a legenda
   Atual e Meta e a diferença para a meta. Serve SPI, CPI, aderência,
   conformidade e o índice do MAS.

   Contrato dos dados (data-dados): um relógio ou uma lista deles.
     {
       "relogios": [{
         "titulo": "Aderência da programação", "subtitulo": "Semana 39",
         "valor": 78.5, "meta": 60, "max": 100, "casas": 1, "unidade": "",
         "limites": { "ok": 70, "alerta": 60 }
       }],
       "rotulos": { "atual": "Atual", "meta": "Meta", "vsMeta": "vs meta",
                    "ok": "Dentro da meta", "alerta": "Atenção",
                    "erro": "Abaixo da meta" }
     }
   O estado vem dos limites: valor a partir de `ok` é ok; a partir de `alerta`,
   alerta; abaixo, erro. Sem `limites`, vale a meta (a partir dela é ok, abaixo
   é erro) e, sem meta, o relógio fica neutro. O servidor pode também mandar
   `estado` pronto ("ok", "alerta", "erro"). O arco enche até valor / max; os
   limites e a meta vêm dos parâmetros do projeto, nunca daqui.

   Decisão do porte: o original desenhava o marcador da meta com o ângulo
   igual ao número da meta, em graus (meta 60 caía a 30 graus do topo, e não
   aos 60% do círculo). Aqui o marcador fica em meta / max do círculo, que é
   o que o rótulo "Meta" diz.

     <div data-grafico="relogios" data-dados='{{ grafico | tojson }}'></div>

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;

  const CENTRO = 70;
  const RAIO = 54;
  const CIRCUNFERENCIA = 2 * Math.PI * RAIO;
  const DURACAO_MS = 900;
  const ATRASO_MS = 150;
  const ESTADOS = ["ok", "alerta", "erro", "neutro"];

  let sequenciaDeSombra = 0;

  /* ---------- Contas ---------- */

  function entreZeroEUm(fracao) {
    return Math.min(Math.max(fracao, 0), 1);
  }

  function estadoDe(relogio) {
    if (ESTADOS.includes(relogio.estado)) return relogio.estado;
    if (!Number.isFinite(relogio.valor)) return "neutro";
    const limites = relogio.limites || {};
    const minimoDoOk = Number.isFinite(limites.ok) ? limites.ok : relogio.meta;
    if (!Number.isFinite(minimoDoOk)) return "neutro";
    if (relogio.valor >= minimoDoOk) return "ok";
    return Number.isFinite(limites.alerta) && relogio.valor >= limites.alerta ? "alerta" : "erro";
  }

  function casasDe(relogio, dados) {
    if (Number.isInteger(relogio.casas)) return relogio.casas;
    return Number.isInteger(dados.casas) ? dados.casas : 1;
  }

  function arredondar(valor) {
    return Math.round(valor * 10) / 10;
  }

  /* O marcador atravessa o anel, de dentro para um pouco além da borda. */
  function marcadorDaMeta(fracaoDaMeta) {
    const angulo = fracaoDaMeta * 2 * Math.PI;
    const ponto = function (raio) {
      return { x: arredondar(CENTRO + raio * Math.sin(angulo)), y: arredondar(CENTRO - raio * Math.cos(angulo)) };
    };
    const dentro = ponto(RAIO);
    const fora = ponto(RAIO + 14);
    return { x1: dentro.x, y1: dentro.y, x2: fora.x, y2: fora.y };
  }

  /* ---------- Animação do arco e do número ---------- */

  function suavizar(progresso) {
    return progresso < 0.5 ? 2 * progresso * progresso : 1 - Math.pow(-2 * progresso + 2, 2) / 2;
  }

  function preencher(partes, progresso) {
    const andamento = suavizar(progresso);
    const cheio = partes.fracao * andamento * CIRCUNFERENCIA;
    partes.arco.setAttribute("stroke-dasharray", cheio.toFixed(2) + " " + (CIRCUNFERENCIA - cheio).toFixed(2));
    if (partes.numero !== null) partes.texto.textContent = partes.formatar(partes.numero * andamento);
  }

  /* Devolve a função que cancela. Sem animação, o relógio já nasce cheio. */
  function animarPreenchimento(partes) {
    if (!G.podeAnimar(partes.arco)) {
      preencher(partes, 1);
      return function () {};
    }
    preencher(partes, 0);
    let inicio = null;
    let quadro = 0;
    function passo(agora) {
      if (inicio === null) inicio = agora;
      const progresso = Math.min((agora - inicio) / DURACAO_MS, 1);
      preencher(partes, progresso);
      if (progresso < 1) quadro = window.requestAnimationFrame(passo);
    }
    const adiado = window.setTimeout(function () {
      quadro = window.requestAnimationFrame(passo);
    }, ATRASO_MS);
    return function () {
      window.clearTimeout(adiado);
      window.cancelAnimationFrame(quadro);
    };
  }

  /* ---------- Desenho ---------- */

  /* As partes que a animação mexe (o arco e o número do centro) e o que se
     precisa para escrever um valor. */
  function prepararPartes(relogio, dados) {
    const casas = casasDe(relogio, dados);
    const unidade = typeof relogio.unidade === "string" ? relogio.unidade : "";
    const maximo = Number.isFinite(relogio.max) && relogio.max > 0 ? relogio.max : 100;
    const temValor = Number.isFinite(relogio.valor);
    const partes = {
      casas: casas,
      unidade: unidade,
      maximo: maximo,
      numero: temValor ? relogio.valor : null,
      fracao: temValor ? entreZeroEUm(relogio.valor / maximo) : 0,
      formatar: function (numero) {
        return G.fmt.numero(numero, casas) + unidade;
      },
      /* A meta é um número redondo na maioria dos casos (60, não 60,0). */
      formatarMeta: function (numero) {
        return G.fmt.numero(numero, Number.isInteger(numero) ? 0 : casas) + unidade;
      },
    };
    partes.arco = G.svg("circle", {
      class: "graf-relogio__arco",
      cx: CENTRO,
      cy: CENTRO,
      r: RAIO,
      fill: "none",
      "stroke-width": 16,
      "stroke-linecap": "round",
      "stroke-dasharray": "0 " + CIRCUNFERENCIA,
      transform: "rotate(-90 " + CENTRO + " " + CENTRO + ")",
    });
    partes.texto = G.svg(
      "text",
      { class: "graf-relogio__valor", x: CENTRO, y: 64, "text-anchor": "middle", "dominant-baseline": "middle" },
      [temValor ? partes.formatar(relogio.valor) : "–"],
    );
    return partes;
  }

  function mostrador(relogio, partes, dados) {
    sequenciaDeSombra += 1;
    const idDaSombra = "graf-relogio-sombra-" + sequenciaDeSombra;
    const filhos = [
      G.svg("defs", {}, [
        G.svg("filter", { id: idDaSombra }, [
          G.svg("feDropShadow", { dx: 0, dy: 1, stdDeviation: 3, "flood-color": G.cor("--neutro-800"), "flood-opacity": 0.1 }),
        ]),
      ]),
      G.svg("circle", { class: "graf-relogio__miolo", cx: CENTRO, cy: CENTRO, r: 46, filter: "url(#" + idDaSombra + ")" }),
      G.svg("circle", { class: "graf-relogio__trilho", cx: CENTRO, cy: CENTRO, r: RAIO, fill: "none", "stroke-width": 16 }),
      partes.arco,
    ];
    if (Number.isFinite(relogio.meta)) {
      const marca = marcadorDaMeta(entreZeroEUm(relogio.meta / partes.maximo));
      filhos.push(
        G.svg("line", Object.assign({ class: "graf-relogio__marca-meta", "stroke-width": 2.5, "stroke-linecap": "round" }, marca)),
      );
    }
    filhos.push(partes.texto);
    if (Number.isFinite(relogio.meta)) {
      filhos.push(
        G.svg(
          "text",
          { class: "graf-relogio__meta-texto", x: CENTRO, y: 83, "text-anchor": "middle", "dominant-baseline": "middle" },
          [G.rotulo(dados, "meta") + ": " + partes.formatarMeta(relogio.meta)],
        ),
      );
    }
    return G.svg("svg", { width: 140, height: 140, viewBox: "0 0 140 140", "aria-hidden": "true" }, filhos);
  }

  function pilula(estado, dados) {
    if (estado === "neutro") return null;
    return G.el("div", { class: "graf-relogio__pilula-linha" }, [
      G.el("span", { class: "graf-relogio__pilula" }, [G.el("span", { class: "graf-relogio__pilula-ponto" }), G.rotulo(dados, estado)]),
    ]);
  }

  function linhaDaLegenda(modificador, nome, valor) {
    return G.el("div", { class: "graf-relogio__leg-linha" }, [
      G.el("span", { class: "graf-relogio__leg-ponto " + modificador }),
      G.el("span", { class: "graf-relogio__leg-rotulo", texto: nome }),
      G.el("span", { class: "graf-relogio__leg-valor " + modificador, texto: valor }),
    ]);
  }

  /* A diferença para a meta é verde quando a alcança, mesmo que o estado
     seja de atenção: ela mede só a distância, o estado é dos limites. */
  function selo(relogio, partes, dados) {
    const diferenca = relogio.valor - relogio.meta;
    const alcancou = diferenca >= 0;
    return G.el("div", { class: "graf-relogio__delta " + (alcancou ? "is-bom" : "is-ruim") }, [
      G.el("span", { class: "graf-relogio__delta-icone", "aria-hidden": "true", texto: alcancou ? "▲" : "▼" }),
      G.el("span", { class: "graf-relogio__delta-rotulo", texto: G.rotulo(dados, "vsMeta") }),
      G.el("span", { class: "graf-relogio__delta-numero", texto: G.fmt.comSinal(diferenca, partes.casas) + partes.unidade }),
    ]);
  }

  function base(relogio, partes, dados) {
    const linhas = [linhaDaLegenda("is-estado", G.rotulo(dados, "atual"), Number.isFinite(relogio.valor) ? partes.formatar(relogio.valor) : "–")];
    const temMeta = Number.isFinite(relogio.meta);
    if (temMeta) linhas.push(linhaDaLegenda("is-meta", G.rotulo(dados, "meta"), partes.formatarMeta(relogio.meta)));
    const filhos = [G.el("div", { class: "graf-relogio__leg" }, linhas)];
    if (temMeta && Number.isFinite(relogio.valor)) filhos.push(selo(relogio, partes, dados));
    return G.el("div", { class: "graf-relogio__base" }, filhos);
  }

  function cartao(relogio, dados) {
    const estado = estadoDe(relogio);
    const partes = prepararPartes(relogio, dados);
    const corpo = [
      G.el("div", { class: "graf-relogio__mostrador" }, [mostrador(relogio, partes, dados)]),
      pilula(estado, dados),
      base(relogio, partes, dados),
    ].filter(Boolean);
    const filhos = [
      relogio.titulo ? G.el("div", { class: "graf-relogio__titulo", texto: relogio.titulo }) : null,
      relogio.subtitulo ? G.el("div", { class: "graf-relogio__sub", texto: relogio.subtitulo }) : null,
      G.el("div", { class: "graf-relogio__corpo" }, corpo),
    ].filter(Boolean);
    return {
      elemento: G.el("div", { class: "graf-relogio is-" + estado, role: "group", "aria-label": relogio.titulo }, filhos),
      partes: partes,
    };
  }

  G.registrar("relogios", function (host, dados) {
    const lista = Array.isArray(dados.relogios) ? dados.relogios : [dados];
    if (!lista.length) {
      G.mostrarMensagem(host, G.rotulo(dados, "vazio"));
      return null;
    }
    const cartoes = lista.map(function (relogio) {
      return cartao(relogio, dados);
    });
    host.replaceChildren(
      G.el(
        "div",
        { class: "graf-relogios" },
        cartoes.map(function (pronto) {
          return pronto.elemento;
        }),
      ),
    );
    const cancelamentos = cartoes.map(function (pronto) {
      return animarPreenchimento(pronto.partes);
    });
    return {
      destruir: function () {
        cancelamentos.forEach(function (cancelar) {
          cancelar();
        });
      },
    };
  });
})();
