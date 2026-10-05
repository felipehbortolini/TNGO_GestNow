/* ============================================================
   graficos/pareto.js — Pareto

   Porte de "Pareto.html" (docs/referencia/graficos/): barras empilhadas por
   categoria em ordem decrescente, a curva do percentual acumulado, a zona
   vital (as categorias que reúnem os primeiros 80%) com a linha de corte, a
   legenda por status e, opcionalmente, o cabeçalho com cartões e a frase de
   leitura. Serve o Pareto de RNC, de origem de mudanças e de motivos de
   parada.

   Contrato dos dados (data-dados):
     {
       "eyebrow": "ANÁLISE DE PARETO", "titulo": "...", "subtitulo": "...",
       "eixo_esquerdo": "Nº de ações", "eixo_direito": "% acumulado",
       "corte": 80,
       "status": [{ "id": "concluido", "rotulo": "Concluído", "papel": "ok" }],
       "categorias": [{ "rotulo": "Mitigação de riscos",
                        "valores": { "concluido": 14 } }],
       "kpis": [{ "rotulo": "Total", "valor": 299, "sub": "12 tipos",
                  "papel": "titulo" }],
       "insight": ["texto", ["trecho em destaque", "atencao"], "texto"]
     }
   O servidor manda a quantidade de cada categoria por status (a ordem de
   `status` é a da pilha, de baixo para cima). Total, percentual, ordem, zona
   vital e acumulado saem aqui. `kpis` e `insight` são opcionais: texto e
   números dessas faixas vêm prontos do servidor.

     <div data-grafico="pareto" data-dados='{{ grafico | tojson }}'></div>

   O tamanho de tudo acompanha a unidade `--graf-u`, calculada pelo tamanho
   do gráfico, como o original fazia com a janela do visual.

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;

  /* A maior barra ocupa 65% da altura: o resto é do valor, da pílula e do
     ponto da curva acima dela. */
  const FRACAO_DA_MAIOR_BARRA = 0.65;
  const CORTE_PADRAO = 80;
  const POSICOES_DO_EIXO = [0, 25, 50, 75, 100];
  const MISTURA_DO_TOPO = 0.3;
  /* Larguras e alturas em que o original esconde partes (media queries do
     visual). Como o gráfico mora num cartão e não na janela, o teste é feito
     contra o tamanho dele e vai para os atributos data-faixa-*. */
  const FAIXAS_DE_LARGURA = [900, 680, 622, 480, 434, 280];
  const FAIXAS_DE_ALTURA = [520, 400, 300];

  let sequenciaDeGradiente = 0;

  /* ---------- Contas ---------- */

  function quantidadeDe(categoria, status) {
    const valor = categoria.valores ? categoria.valores[status.id] : 0;
    return Number.isFinite(valor) ? valor : 0;
  }

  function soma(valores) {
    return valores.reduce(function (total, valor) {
      return total + valor;
    }, 0);
  }

  function cobrirPercentuais(categorias, geral) {
    let acumulado = 0;
    categorias.forEach(function (categoria) {
      acumulado += categoria.total;
      categoria.pct = (categoria.total / geral) * 100;
      categoria.acumPct = (acumulado / geral) * 100;
    });
  }

  function corDoStatus(status, indice) {
    const nome = status.cor || status.papel;
    const base = nome ? G.cor(nome) : G.corDaSequencia(indice);
    return { base: base, topo: G.clarear(base, MISTURA_DO_TOPO) };
  }

  /* Tudo o que o desenho precisa, calculado uma vez. Devolve null sem dado. */
  function preparar(dados) {
    const status = dados.status || [];
    const categorias = (dados.categorias || [])
      .map(function (categoria) {
        const partes = status.map(function (item) {
          return quantidadeDe(categoria, item);
        });
        return { rotulo: categoria.rotulo, partes: partes, total: soma(partes) };
      })
      .filter(function (categoria) {
        return categoria.total > 0;
      })
      .sort(function (a, b) {
        return b.total - a.total;
      });
    if (!categorias.length) return null;
    const geral = soma(
      categorias.map(function (categoria) {
        return categoria.total;
      }),
    );
    cobrirPercentuais(categorias, geral);
    const corte = Math.min(Math.max(Number.isFinite(dados.corte) ? dados.corte : CORTE_PADRAO, 1), 100);
    return {
      dados: dados,
      status: status,
      categorias: categorias,
      geral: geral,
      corte: corte,
      indiceDoCorte: categorias.findIndex(function (categoria) {
        return categoria.acumPct >= corte;
      }),
      escala: G.escala(categorias[0].total / FRACAO_DA_MAIOR_BARRA),
      cores: status.map(corDoStatus),
      porStatus: status.map(function (item, k) {
        return soma(
          categorias.map(function (categoria) {
            return categoria.partes[k];
          }),
        );
      }),
    };
  }

  /* ---------- Cabeçalho ---------- */

  function cartaoDeKpi(kpi, indice) {
    const nome = G.cor(kpi.papel || "titulo");
    const valor = G.el("div", { class: "graf-pareto__kpi-val", texto: String(kpi.valor) });
    valor.style.color = nome;
    const cartao = G.el("div", { class: "graf-pareto__kpi graf-pareto__kpi--" + (indice + 1) }, [
      G.el("div", { class: "graf-pareto__kpi-rot", texto: kpi.rotulo }),
      valor,
      kpi.sub ? G.el("div", { class: "graf-pareto__kpi-sub", texto: kpi.sub }) : null,
    ].filter(Boolean));
    cartao.style.borderTopColor = nome;
    return cartao;
  }

  function cabecalho(dados) {
    const kpis = dados.kpis || [];
    if (!dados.eyebrow && !dados.titulo && !dados.subtitulo && !kpis.length) return null;
    const titulos = G.el("div", { class: "graf-pareto__tit" }, [
      dados.eyebrow ? G.el("div", { class: "graf-pareto__eb", texto: dados.eyebrow }) : null,
      dados.titulo ? G.el("div", { class: "graf-pareto__h1", texto: dados.titulo }) : null,
      dados.subtitulo ? G.el("div", { class: "graf-pareto__sb", texto: dados.subtitulo }) : null,
      G.el("div", { class: "graf-pareto__fio" }),
    ].filter(Boolean));
    const filhos = [titulos];
    if (kpis.length) filhos.push(G.el("div", { class: "graf-pareto__kpis" }, kpis.map(cartaoDeKpi)));
    return G.el("div", { class: "graf-pareto__cab" }, filhos);
  }

  function trechoDaFrase(trecho) {
    if (typeof trecho === "string") return trecho;
    const destaque = G.el("b", { texto: trecho[0] });
    if (trecho[1]) destaque.style.color = G.cor(trecho[1]);
    return destaque;
  }

  function frase(dados) {
    if (!Array.isArray(dados.insight) || !dados.insight.length) return null;
    return G.el("div", { class: "graf-pareto__frase" }, [
      G.el("span", { class: "graf-pareto__frase-ponto" }),
      G.el("span", {}, dados.insight.map(trechoDaFrase)),
    ]);
  }

  /* ---------- Área do gráfico ---------- */

  function posicionado(classe, base, texto) {
    const no = G.el("div", { class: classe, texto: texto });
    no.style.bottom = base + "%";
    return no;
  }

  function grade(ctx) {
    const nos = [];
    POSICOES_DO_EIXO.forEach(function (posicao, i) {
      const passo = ctx.escala.passos[i];
      nos.push(posicionado("graf-pareto__grade" + (i === 0 ? " is-base" : ""), posicao, ""));
      nos.push(posicionado("graf-pareto__eixo-esq", posicao, G.fmt.numero(passo, Number.isInteger(passo) ? 0 : 1)));
      nos.push(posicionado("graf-pareto__eixo-dir", posicao, posicao + "%"));
    });
    return nos;
  }

  /* Zona vital: do primeiro ao último dos que reúnem o corte, com a linha
     vertical na divisa e a horizontal na altura do corte. */
  function zonaVital(ctx) {
    const largura = ((ctx.indiceDoCorte + 1) / ctx.categorias.length) * 100;
    const zona = G.el("div", { class: "graf-pareto__zona" }, [
      G.el("div", {
        class: "graf-pareto__zona-rotulo",
        texto: G.rotulo(ctx.dados, "zonaVital") + " · " + G.fmt.numero(ctx.corte, 0) + "%",
      }),
    ]);
    zona.style.width = largura + "%";
    const divisa = G.el("div", { class: "graf-pareto__divisa" });
    divisa.style.left = largura + "%";
    return [
      zona,
      divisa,
      posicionado("graf-pareto__corte", ctx.corte, ""),
      posicionado("graf-pareto__corte-selo", ctx.corte, G.fmt.numero(ctx.corte, 0) + "%"),
    ];
  }

  function pilhaDaBarra(categoria, indice, ctx) {
    const pilha = G.el("div", { class: "graf-pareto__pilha" });
    pilha.style.height = (categoria.total / ctx.escala.max) * 100 + "%";
    pilha.style.setProperty("--graf-atraso", 170 + indice * 70 + "ms");
    /* A pilha vai de baixo para cima na ordem de `status`; no DOM, de cima
       para baixo. */
    for (let k = ctx.status.length - 1; k >= 0; k--) {
      if (categoria.partes[k] > 0) {
        const trecho = G.el("i", { class: "graf-pareto__trecho", texto: G.fmt.numero(categoria.partes[k], 0) });
        trecho.style.flex = categoria.partes[k] + " 1 0";
        trecho.style.background = "linear-gradient(" + ctx.cores[k].topo + ", " + ctx.cores[k].base + ")";
        pilha.appendChild(trecho);
      }
    }
    return pilha;
  }

  /* Ponto da curva acumulada, pílula com o percentual e total da barra. O
     ponto que cai dentro da própria barra não tem espaço para a pílula: ela
     sobe para o topo, acima do total, e uma guia tracejada liga o ponto a
     ela. Fora da barra, a pílula fica logo acima do ponto. */
  function marcadores(categoria, indice, ctx) {
    const estado = indice <= ctx.indiceDoCorte ? "is-dentro" : "is-fora";
    const alturaDaBarra = (categoria.total / ctx.escala.max) * 100;
    const sobreABarra = categoria.acumPct < alturaDaBarra;
    const baseDaPilula = sobreABarra ? alturaDaBarra : categoria.acumPct;
    const atraso = 800 + indice * 80 + "ms";
    const nos = [];
    if (sobreABarra) {
      const guia = posicionado("graf-pareto__guia", categoria.acumPct, "");
      guia.style.height = alturaDaBarra - categoria.acumPct + "%";
      nos.push(guia);
    }
    if (indice === ctx.indiceDoCorte) nos.push(posicionado("graf-pareto__halo", categoria.acumPct, ""));
    nos.push(
      posicionado(
        "graf-pareto__ponto " + estado + (indice === ctx.indiceDoCorte ? " is-corte" : ""),
        categoria.acumPct,
        "",
      ),
      posicionado(
        "graf-pareto__pilula " + estado + (sobreABarra ? " is-alta" : ""),
        baseDaPilula,
        Math.round(categoria.acumPct) + "%",
      ),
      posicionado("graf-pareto__valor " + estado, alturaDaBarra, G.fmt.numero(categoria.total, 0)),
    );
    nos.forEach(function (no) {
      no.style.setProperty("--graf-atraso", atraso);
    });
    return nos;
  }

  function colunas(ctx) {
    const todas = ctx.categorias.map(function (categoria, i) {
      const coluna = G.el(
        "div",
        {
          class: "graf-pareto__coluna",
          title:
            categoria.rotulo +
            ": " +
            G.fmt.numero(categoria.total, 0) +
            " · " +
            G.fmt.numero(categoria.acumPct, 1) +
            "% " +
            G.rotulo(ctx.dados, "acumulado"),
        },
        [pilhaDaBarra(categoria, i, ctx)].concat(marcadores(categoria, i, ctx)),
      );
      return coluna;
    });
    return G.el("div", { class: "graf-pareto__colunas" }, todas);
  }

  /* A curva acumulada é um SVG esticado sobre a área (viewBox de 1000 por
     coluna e 10000 de altura), com traço de largura fixa na tela. */
  function curva(ctx) {
    sequenciaDeGradiente += 1;
    const id = "graf-pareto-grad-" + sequenciaDeGradiente;
    const verde = G.cor("--verde-500");
    const laranja = G.cor("--laranja-500");
    const pontos = ctx.categorias
      .map(function (categoria, i) {
        return (i + 0.5) * 1000 + "," + Math.round(10000 - categoria.acumPct * 100);
      })
      .join(" ");
    const tracado = { points: pontos, fill: "none", "stroke-linejoin": "round", "stroke-linecap": "round", "vector-effect": "non-scaling-stroke" };
    return G.svg(
      "svg",
      {
        class: "graf-pareto__curva",
        viewBox: "0 0 " + ctx.categorias.length * 1000 + " 10000",
        preserveAspectRatio: "none",
        "aria-hidden": "true",
      },
      [
        G.svg("defs", {}, [
          G.svg("linearGradient", { id: id, x1: 0, y1: 0, x2: 1, y2: 0 }, [
            G.svg("stop", { offset: 0, "stop-color": verde }),
            G.svg("stop", { offset: 0.5, "stop-color": G.misturar(verde, laranja, 0.5) }),
            G.svg("stop", { offset: 1, "stop-color": laranja }),
          ]),
        ]),
        G.svg("polyline", Object.assign({ class: "graf-pareto__curva-fundo" }, tracado)),
        G.svg("polyline", Object.assign({ class: "graf-pareto__curva-linha", stroke: "url(#" + id + ")" }, tracado)),
      ],
    );
  }

  function area(ctx) {
    const filhos = grade(ctx).concat(zonaVital(ctx), [colunas(ctx), curva(ctx)]);
    return G.el("div", { class: "graf-pareto__area" }, filhos);
  }

  function plot(ctx) {
    return G.el("div", { class: "graf-pareto__plot" }, [
      G.el("div", {
        class: "graf-pareto__titulo-eixo is-esq",
        texto: ctx.dados.eixo_esquerdo || G.rotulo(ctx.dados, "quantidade"),
      }),
      G.el("div", {
        class: "graf-pareto__titulo-eixo is-dir",
        texto: ctx.dados.eixo_direito || G.rotulo(ctx.dados, "percAcumulado"),
      }),
      area(ctx),
    ]);
  }

  /* ---------- Rodapé: nomes das categorias e legenda dos status ---------- */

  function nomesDasCategorias(ctx) {
    return G.el(
      "div",
      { class: "graf-pareto__x" },
      ctx.categorias.map(function (categoria, i) {
        const estado = i <= ctx.indiceDoCorte ? "is-dentro" : "is-fora";
        const coluna = G.el("div", { class: "graf-pareto__xc " + estado }, [
          G.el("div", { class: "graf-pareto__xu" }),
          G.el("div", { class: "graf-pareto__xn", texto: categoria.rotulo }),
          G.el("div", {
            class: "graf-pareto__xs",
            texto: G.fmt.numero(categoria.pct, 0) + "% " + G.rotulo(ctx.dados, "doTotal"),
          }),
        ]);
        coluna.style.setProperty("--graf-atraso", 170 + i * 70 + "ms");
        return coluna;
      }),
    );
  }

  function legenda(ctx) {
    return G.el(
      "div",
      { class: "graf-pareto__leg" },
      ctx.status.map(function (item, k) {
        const amostra = G.el("i", { class: "graf-pareto__leg-cor" });
        amostra.style.background = ctx.cores[k].base;
        const parte = (ctx.porStatus[k] / ctx.geral) * 100;
        return G.el("div", { class: "graf-pareto__leg-item" }, [
          amostra,
          G.el("div", { class: "graf-pareto__leg-txt" }, [
            G.el("div", { class: "graf-pareto__leg-nome", texto: item.rotulo }),
            G.el("div", {
              class: "graf-pareto__leg-val",
              texto: G.fmt.numero(ctx.porStatus[k], 0) + " · " + G.fmt.numero(parte, 0) + "%",
            }),
          ]),
        ]);
      }),
    );
  }

  /* ---------- Escala ---------- */

  /* A unidade `--graf-u` faz o papel do vh e do vw do original: fonte, espaço e
     espessura são múltiplos dela. Os fatores (1,55% da altura, 0,98% da
     largura, de 3,5 a 13 px) são os do preview do original, 1,1 vh e 0,7 vw
     numa janela de uns 1400 x 800 em que o palco ocupava cerca de 70%, só que
     aplicados ao tamanho do próprio gráfico. */
  function aplicarEscala(raiz) {
    const largura = raiz.clientWidth;
    const altura = raiz.clientHeight;
    const unidade = Math.max(3.5, Math.min(13, altura * 0.0155, largura * 0.0098));
    raiz.style.setProperty("--graf-u", unidade.toFixed(2) + "px");
    raiz.dataset.faixaLarg = FAIXAS_DE_LARGURA.filter(function (limite) {
      return largura <= limite;
    }).join(" ");
    raiz.dataset.faixaAlt = FAIXAS_DE_ALTURA.filter(function (limite) {
      return altura <= limite;
    }).join(" ");
  }

  G.registrar("pareto", function (host, dados) {
    const ctx = preparar(dados);
    if (!ctx) {
      G.mostrarMensagem(host, G.rotulo(dados, "vazio"));
      return null;
    }
    const raiz = G.el(
      "div",
      { class: "graf-pareto", role: "group", "aria-label": dados.titulo },
      [cabecalho(dados), frase(dados), plot(ctx), nomesDasCategorias(ctx), legenda(ctx)].filter(Boolean),
    );
    host.replaceChildren(raiz);
    aplicarEscala(raiz);
    const parar = G.observarTamanho(raiz, function () {
      aplicarEscala(raiz);
    });
    return { destruir: parar };
  });
})();
