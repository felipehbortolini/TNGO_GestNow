/* ============================================================
   graficos/areas-avaliacao.js — Gráfico de Áreas de Avaliação

   Porte de "Grafico de Areas de Avaliação.html" (docs/referencia/graficos/):
   a evolução mensal de uma nota (de 0 a 100) sobre faixas de classificação
   coloridas, a linha suave que se desenha na entrada com a área embaixo, os
   pontos na cor da faixa em que cada nota caiu, o valor sobre cada ponto, o
   último com um anel que pulsa, e no alto os quatro resumos (média do
   período, melhor mês, variação para o mês anterior e a leitura atual, na cor
   da faixa). Serve o desempenho da contratada ao longo do tempo.

   Contrato dos dados (data-dados):
     {
       "titulo": "Desempenho da contratada",
       "unidade": "%", "casas": 1, "meta": 85,
       "eixo_min": 60, "eixo_max": 100,
       "zonas": [{ "de": 0, "rotulo": "Classe D", "papel": "erro" },
                 { "de": 85, "rotulo": "Classe A", "papel": "ok" }],
       "pontos": [{ "ano": 2026, "mes": 1, "valor": 68.4 }]
     }
   `zonas` são as faixas de classificação, vindas dos parâmetros do projeto
   (a biblioteca não traz faixa própria: os 90, 81 e 70 do original eram só
   dele). Cada faixa começa em `de`, que vale a partir dele (a nota 85 é da
   faixa que começa em 85), e vai até o `de` da seguinte, ou até o topo do
   eixo. O eixo vai de 0 a 100 para baixo até onde a menor nota pede, em
   passos de 10 (o piso é o menor entre 60 e o múltiplo de 10 quatro pontos
   abaixo da menor nota, a conta do original); `eixo_min` e `eixo_max` fixam
   as pontas. `meta`, se vier, é a linha tracejada. Com mais de um ano, os
   botões de ano aparecem e os resumos seguem o que está à vista.

     <div data-grafico="areas-avaliacao" data-dados='{{ grafico | tojson }}'></div>

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;
  const A = G.apoio;

  const ROTULOS = {
    media: "Média do período",
    melhorMes: "Melhor mês",
    vsAnterior: "vs mês anterior",
    atual: "Atual",
    pontosPercentuais: "p.p.",
    meta: "Meta",
  };
  const MARGEM = { esq: 46, dir: 26, topo: 22, base: 32 };
  const LARGURA_MINIMA = 300;
  const ALTURA_MINIMA = 160;
  const PASSO_DO_EIXO = 10;
  /* A conta do piso do original: o menor entre 60 e a menor nota menos 4,
     arredondada para baixo na dezena. */
  const PISO_MAXIMO = 60;
  const FOLGA_DO_PISO = 4;
  const TETO_PADRAO = 100;
  const CASAS_PADRAO = 1;
  const OPACIDADE_DA_ZONA = 0.05;
  const DURACAO_DO_TRACO_MS = 1600;
  const ATRASO_DO_PRIMEIRO_PONTO_MS = 300;
  const ATRASO_ENTRE_PONTOS_MS = 110;
  const LARGURA_DO_VALOR = 42;
  const LARGURA_DO_MES = 50;

  let sequenciaDeGradiente = 0;

  /* ---------- Contas ---------- */

  function pontoValido(ponto) {
    return Boolean(ponto) && Number.isInteger(ponto.ano) && Number.isInteger(ponto.mes) && ponto.mes >= 1 && ponto.mes <= 12 && Number.isFinite(ponto.valor);
  }

  function prepararPontos(dados) {
    return (dados.pontos || [])
      .filter(pontoValido)
      .map(function (ponto) {
        return { ano: ponto.ano, mes: ponto.mes, valor: ponto.valor };
      })
      .sort(function (a, b) {
        return a.ano - b.ano || a.mes - b.mes;
      });
  }

  function prepararZonas(dados) {
    return (dados.zonas || [])
      .filter(function (zona) {
        return Number.isFinite(zona.de);
      })
      .map(function (zona, indice) {
        const nome = zona.cor || zona.papel;
        return { de: zona.de, rotulo: zona.rotulo, cor: nome ? G.cor(nome) : G.corDaSequencia(indice) };
      })
      .sort(function (a, b) {
        return a.de - b.de;
      });
  }

  /* A faixa da nota: a mais alta que começa em ou antes dela; abaixo de todas,
     a mais baixa. Sem faixas, nulo. */
  function zonaDoValor(zonas, valor) {
    if (!zonas.length) return null;
    let escolhida = zonas[0];
    zonas.forEach(function (zona) {
      if (valor >= zona.de) escolhida = zona;
    });
    return escolhida;
  }

  /* O piso e o teto do eixo. */
  function limitesDoEixo(dados, valores) {
    const teto = Number.isFinite(dados.eixo_max) ? dados.eixo_max : TETO_PADRAO;
    if (Number.isFinite(dados.eixo_min)) return { min: dados.eixo_min, max: teto };
    if (!valores.length) return { min: 0, max: teto };
    const menor = Math.min(...valores);
    const piso = Math.min(PISO_MAXIMO, Math.floor((menor - FOLGA_DO_PISO) / PASSO_DO_EIXO) * PASSO_DO_EIXO);
    return { min: piso, max: teto };
  }

  function resumoDos(pontos) {
    const valores = pontos.map(function (ponto) {
      return ponto.valor;
    });
    const ultimo = pontos[pontos.length - 1];
    return {
      media: valores.reduce(function (soma, valor) {
        return soma + valor;
      }, 0) / valores.length,
      melhor: Math.max(...valores),
      ultimo: ultimo,
      variacao: pontos.length > 1 ? ultimo.valor - pontos[pontos.length - 2].valor : null,
    };
  }

  function nomeDoPonto(ponto) {
    return G.nomeMes(ponto.mes).toUpperCase() + "/" + String(ponto.ano % 100).padStart(2, "0");
  }

  function arredondar(valor) {
    return Math.round(valor * 100) / 100;
  }

  /* A linha do original: segmentos quadráticos que passam pelos pontos
     médios, com os pontos de dados como alças. */
  function caminhoDaLinha(xs, ys) {
    let caminho = "M" + arredondar(xs[0]) + " " + arredondar(ys[0]);
    for (let i = 1; i < xs.length; i++) {
      const mx = (xs[i - 1] + xs[i]) / 2;
      const my = (ys[i - 1] + ys[i]) / 2;
      caminho += " Q" + arredondar(xs[i - 1]) + " " + arredondar(ys[i - 1]) + " " + arredondar(mx) + " " + arredondar(my);
    }
    return caminho + " T" + arredondar(xs[xs.length - 1]) + " " + arredondar(ys[ys.length - 1]);
  }

  /* ---------- Cabeçalho ---------- */

  function chip(rotulo, valor, estilo) {
    const no = G.el("div", { class: "graf-areas__chip" + (estilo ? " " + estilo.classe : "") }, [
      G.el("span", { class: "graf-areas__chip-rotulo", texto: rotulo }),
      G.el("span", { class: "graf-areas__chip-valor", texto: valor }),
    ]);
    if (estilo && estilo.fundo) no.style.background = estilo.fundo;
    return no;
  }

  function chipDaVariacao(ctx, variacao) {
    const texto = (variacao >= 0 ? "▲ " : "▼ ") + G.fmt.comSinal(variacao, ctx.casas) + " " + ctx.rotulo("pontosPercentuais");
    const no = chip(ctx.rotulo("vsAnterior"), texto, null);
    no.classList.add(variacao >= 0 ? "is-subiu" : "is-caiu");
    return no;
  }

  function chipsDoResumo(ctx, pontos) {
    const resumo = resumoDos(pontos);
    const zona = zonaDoValor(ctx.zonas, resumo.ultimo.valor);
    const leitura = ctx.escrever(resumo.ultimo.valor) + (zona && zona.rotulo ? " · " + zona.rotulo : "");
    const chips = [chip(ctx.rotulo("media"), ctx.escrever(resumo.media), null), chip(ctx.rotulo("melhorMes"), ctx.escrever(resumo.melhor), null)];
    if (resumo.variacao !== null) chips.push(chipDaVariacao(ctx, resumo.variacao));
    chips.push(chip(nomeDoPonto(resumo.ultimo) + " · " + ctx.rotulo("atual"), leitura, { classe: "is-destaque", fundo: zona ? zona.cor : null }));
    return chips;
  }

  /* ---------- Desenho ---------- */

  function paleta() {
    return {
      grade: G.cor("--neutro-100"),
      gradeTexto: G.cor("--neutro-300"),
      mes: G.cor("--neutro-400"),
      valor: G.cor("--text-secondary"),
      contorno: G.cor("--branco"),
      linha: G.cor("--verde-500"),
    };
  }

  function montarContexto(base) {
    const largura = Math.max(base.tela.clientWidth, LARGURA_MINIMA);
    const altura = Math.max(base.tela.clientHeight, ALTURA_MINIMA);
    const area = { esq: MARGEM.esq, dir: largura - MARGEM.dir, topo: MARGEM.topo, base: altura - MARGEM.base };
    area.largura = area.dir - area.esq;
    area.altura = area.base - area.topo;
    const pontos = base.pontos;
    const passo = pontos.length > 1 ? area.largura / (pontos.length - 1) : area.largura;
    const eixo = base.eixo;
    return {
      svg: G.svg("svg", { class: "graf__svg", viewBox: "0 0 " + largura + " " + altura, role: "img", "aria-label": base.dados.titulo }),
      dados: base.dados,
      zonas: base.zonas,
      pontos: pontos,
      area: area,
      altura: altura,
      passo: passo,
      eixo: eixo,
      x: function (i) {
        return pontos.length > 1 ? area.esq + i * passo : (area.esq + area.dir) / 2;
      },
      y: function (valor) {
        return area.topo + ((eixo.max - valor) / (eixo.max - eixo.min)) * area.altura;
      },
      casas: base.casas,
      escrever: base.escrever,
      rotulo: base.rotulo,
      dica: base.dica,
      paleta: paleta(),
      animaveis: [],
    };
  }

  function desenharZonas(ctx) {
    ctx.zonas.forEach(function (zona, i) {
      const topo = Math.min(i + 1 < ctx.zonas.length ? ctx.zonas[i + 1].de : ctx.eixo.max, ctx.eixo.max);
      const fundo = Math.max(zona.de, ctx.eixo.min);
      if (topo <= fundo) return;
      const y0 = ctx.y(topo);
      const y1 = ctx.y(fundo);
      ctx.svg.appendChild(
        G.svg("rect", { x: ctx.area.esq, y: y0, width: ctx.area.largura, height: y1 - y0, fill: zona.cor, opacity: OPACIDADE_DA_ZONA }),
      );
      if (zona.rotulo && y1 - y0 >= 14) {
        ctx.svg.appendChild(
          G.svg(
            "text",
            { class: "graf-areas__zona", x: ctx.area.dir - 8, y: (y0 + y1) / 2 + 3, fill: zona.cor, "text-anchor": "end" },
            [zona.rotulo],
          ),
        );
      }
    });
  }

  function desenharGrade(ctx) {
    for (let valor = ctx.eixo.min; valor <= ctx.eixo.max; valor += PASSO_DO_EIXO) {
      const y = ctx.y(valor);
      ctx.svg.appendChild(
        G.svg("line", { x1: ctx.area.esq, y1: y, x2: ctx.area.dir, y2: y, stroke: ctx.paleta.grade, "stroke-width": 1 }),
      );
      ctx.svg.appendChild(
        G.svg("text", { x: ctx.area.esq - 8, y: y + 3.5, "font-size": 10, "font-weight": 600, fill: ctx.paleta.gradeTexto, "text-anchor": "end" }, [
          G.fmt.numero(valor, 0),
        ]),
      );
    }
    if (!Number.isFinite(ctx.dados.meta)) return;
    const y = ctx.y(ctx.dados.meta);
    ctx.svg.appendChild(
      G.svg("line", {
        x1: ctx.area.esq,
        y1: y,
        x2: ctx.area.dir,
        y2: y,
        stroke: G.cor("ok"),
        "stroke-width": 1.2,
        "stroke-dasharray": "5 4",
        opacity: 0.55,
      }),
    );
  }

  function desenharAreaELinha(ctx) {
    sequenciaDeGradiente += 1;
    const id = "graf-areas-grad-" + sequenciaDeGradiente;
    const xs = ctx.pontos.map(function (_ponto, i) {
      return ctx.x(i);
    });
    const ys = ctx.pontos.map(function (ponto) {
      return ctx.y(ponto.valor);
    });
    const linha = caminhoDaLinha(xs, ys);
    const piso = ctx.y(ctx.eixo.min);
    ctx.svg.appendChild(
      G.svg("defs", {}, [
        G.svg("linearGradient", { id: id, x1: 0, y1: 0, x2: 0, y2: 1 }, [
          G.svg("stop", { offset: "0%", "stop-color": ctx.paleta.linha, "stop-opacity": 0.16 }),
          G.svg("stop", { offset: "100%", "stop-color": ctx.paleta.linha, "stop-opacity": 0 }),
        ]),
      ]),
    );
    if (ctx.pontos.length < 2) return;
    ctx.svg.appendChild(
      G.svg("path", {
        class: "graf-areas__area",
        d: linha + " L" + arredondar(xs[xs.length - 1]) + " " + arredondar(piso) + " L" + arredondar(xs[0]) + " " + arredondar(piso) + " Z",
        fill: "url(#" + id + ")",
      }),
    );
    const caminho = G.svg("path", {
      d: linha,
      fill: "none",
      stroke: ctx.paleta.linha,
      "stroke-width": 2.4,
      "stroke-linecap": "round",
      "stroke-linejoin": "round",
    });
    ctx.svg.appendChild(caminho);
    ctx.animaveis.push(caminho);
  }

  function desenharPonto(ctx, ponto, i) {
    const ultimo = i === ctx.pontos.length - 1;
    const zona = zonaDoValor(ctx.zonas, ponto.valor);
    const cor = zona ? zona.cor : ctx.paleta.linha;
    const x = ctx.x(i);
    const y = ctx.y(ponto.valor);
    if (ultimo) {
      ctx.svg.appendChild(
        G.svg("circle", { class: "graf-areas__anel", cx: x, cy: y, r: 6.5, fill: "none", stroke: cor, "stroke-width": 2 }),
      );
    }
    const bolinha = G.svg("circle", {
      class: "graf-areas__ponto",
      cx: x,
      cy: y,
      r: ultimo ? 5.5 : 4,
      fill: cor,
      stroke: ctx.paleta.contorno,
      "stroke-width": 1.8,
    });
    bolinha.style.animationDelay = ATRASO_DO_PRIMEIRO_PONTO_MS + i * ATRASO_ENTRE_PONTOS_MS + "ms";
    ctx.svg.appendChild(bolinha);
  }

  /* O valor sobre o ponto e o nome do mês embaixo; com muitos pontos, só
     uma parte deles, para os textos não se atropelarem. */
  function desenharRotulos(ctx, ponto, i) {
    const ultimo = i === ctx.pontos.length - 1;
    const x = ctx.x(i);
    const aCada = Math.max(1, Math.ceil(LARGURA_DO_VALOR / Math.max(ctx.passo, 1)));
    if (ultimo || i % aCada === 0) {
      const zona = zonaDoValor(ctx.zonas, ponto.valor);
      const rotulo = G.svg(
        "text",
        {
          class: "graf-areas__valor",
          x: x,
          y: ctx.y(ponto.valor) - 10,
          fill: ultimo && zona ? zona.cor : ctx.paleta.valor,
          "text-anchor": "middle",
        },
        [G.fmt.numero(ponto.valor, ctx.casas)],
      );
      rotulo.style.animationDelay = 400 + i * ATRASO_ENTRE_PONTOS_MS + "ms";
      ctx.svg.appendChild(rotulo);
    }
    const doMes = Math.max(1, Math.ceil(LARGURA_DO_MES / Math.max(ctx.passo, 1)));
    if (i % doMes === 0 || ultimo) {
      ctx.svg.appendChild(
        G.svg("text", { class: "graf-areas__mes", x: x, y: ctx.altura - 8, fill: ctx.paleta.mes, "text-anchor": "middle" }, [nomeDoPonto(ponto)]),
      );
    }
  }

  function conteudoDaDica(ctx, ponto) {
    const zona = zonaDoValor(ctx.zonas, ponto.valor);
    const cor = zona ? zona.cor : ctx.paleta.linha;
    const linhas = [G.dicaTitulo(nomeDoPonto(ponto)), G.dicaDivisor()];
    linhas.push(G.dicaLinha(cor, zona && zona.rotulo ? zona.rotulo : ctx.rotulo("atual"), [ctx.escrever(ponto.valor)]));
    return linhas;
  }

  /* Uma faixa transparente por ponto: é nela que o ponteiro faz a dica
     aparecer, sem exigir mira no marcador. */
  function desenharAreasDeToque(ctx) {
    const largura = Math.max(ctx.passo, 24);
    ctx.pontos.forEach(function (ponto, i) {
      const faixa = G.svg("rect", { x: ctx.x(i) - largura / 2, y: ctx.area.topo, width: largura, height: ctx.area.altura, fill: "transparent" });
      faixa.addEventListener("pointerenter", function (evento) {
        ctx.dica.mostrar(evento, conteudoDaDica(ctx, ponto));
      });
      faixa.addEventListener("pointermove", ctx.dica.mover);
      faixa.addEventListener("pointerleave", ctx.dica.esconder);
      ctx.svg.appendChild(faixa);
    });
  }

  /* ---------- Montagem ---------- */

  function anosDe(pontos) {
    return Array.from(
      new Set(
        pontos.map(function (ponto) {
          return ponto.ano;
        }),
      ),
    ).sort(function (a, b) {
      return a - b;
    });
  }

  function pontosDoAno(pontos, ano) {
    return ano === null
      ? pontos
      : pontos.filter(function (ponto) {
          return ponto.ano === ano;
        });
  }

  G.registrar("areas-avaliacao", function (host, dados) {
    const todos = prepararPontos(dados);
    if (!todos.length) {
      G.mostrarMensagem(host, G.rotulo(dados, "vazio"));
      return null;
    }
    const casas = Number.isInteger(dados.casas) ? dados.casas : CASAS_PADRAO;
    const unidade = typeof dados.unidade === "string" ? dados.unidade : "%";
    const base = {
      dados: dados,
      zonas: prepararZonas(dados),
      casas: casas,
      rotulo: A.rotulador(dados, ROTULOS),
      escrever: function (valor) {
        return G.fmt.numero(valor, casas) + unidade;
      },
    };
    const estado = { ano: null };
    const anos = anosDe(todos);
    const botoes = anos.length > 1 ? G.criarAnos(anos, dados, escolherAno) : null;
    const chips = G.el("div", { class: "graf-areas__chips" });
    const cabecalho = G.el("div", { class: "graf-areas__cab" }, botoes ? [chips, botoes.elemento] : [chips]);
    const tela = G.el("div", { class: "graf__tela" });
    host.replaceChildren(cabecalho, tela);
    base.dica = G.criarDica(tela);

    function escolherAno(ano) {
      estado.ano = ano;
      botoes.marcar(ano);
      desenhar(true);
    }

    function desenhar(animar) {
      if (tela.clientWidth === 0) return;
      base.dica.esconder();
      const pontos = pontosDoAno(todos, estado.ano);
      chips.replaceChildren(...chipsDoResumo(base, pontos));
      const ctx = montarContexto({
        tela: tela,
        dados: dados,
        zonas: base.zonas,
        pontos: pontos,
        eixo: limitesDoEixo(
          dados,
          pontos.map(function (ponto) {
            return ponto.valor;
          }),
        ),
        casas: casas,
        escrever: base.escrever,
        rotulo: base.rotulo,
        dica: base.dica,
      });
      if (!animar) ctx.svg.classList.add("graf__svg--parado");
      desenharZonas(ctx);
      desenharGrade(ctx);
      desenharAreaELinha(ctx);
      pontos.forEach(function (ponto, i) {
        desenharPonto(ctx, ponto, i);
        desenharRotulos(ctx, ponto, i);
      });
      desenharAreasDeToque(ctx);
      A.substituirSvg(tela, ctx.svg);
      if (animar) {
        ctx.animaveis.forEach(function (caminho) {
          G.animarTraco(caminho, DURACAO_DO_TRACO_MS);
        });
      }
    }

    desenhar(true);
    const parar = G.observarTamanho(tela, function () {
      desenhar(false);
    });
    return {
      destruir: function () {
        parar();
        base.dica.esconder();
      },
    };
  });

  G.areasAvaliacao = { zonaDoValor: zonaDoValor, limitesDoEixo: limitesDoEixo };
})();
