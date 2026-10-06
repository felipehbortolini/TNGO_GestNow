/* ============================================================
   graficos/linhas-multiplas.js — Linhas múltiplas

   Visual novo (a coletânea não tem equivalente), no padrão dela: tipografia,
   dica escura, legenda, botões de ano e animação de entrada. Duas ou mais
   séries mês a mês no mesmo eixo: TF e TRIF do HSE, CPI e SPI do custo e do
   prazo. A linha se desenha da esquerda para a direita, a última leitura de
   cada série leva o valor, e linhas de referência (a meta, o 1,00 dos
   índices) cortam o gráfico em tracejado.

   Contrato dos dados (data-dados):
     {
       "titulo": "TF e TRIF mês a mês",
       "casas": 2, "unidade": "",
       "base_zero": true, "eixo": { "min": 0, "max": 5 }, "suavizar": true,
       "series": [{ "id": "tf", "rotulo": "TF", "papel": "realizado",
                    "traco": "6,4", "largura": 2.5, "raio": 3.5 }],
       "referencias": [{ "valor": 1, "rotulo": "Meta", "papel": "ok" }],
       "periodos": [{ "ano": 2026, "mes": 3, "valores": { "tf": 0.4 } }]
     }
   `periodos` traz um item por mês; valor nulo é o mês sem leitura e quebra
   a linha. `base_zero` (padrão sim) faz o eixo começar no zero, o certo para
   taxas como TF e TRIF; os índices que giram em torno de 1 (CPI e SPI)
   mandam `base_zero: false` e o eixo se ajusta ao dado. `eixo.min` e
   `eixo.max` fixam as pontas. `suavizar` (padrão sim) usa a mesma curva das
   curvas S, sem passar abaixo nem acima de dois pontos vizinhos. Com mais de
   um ano, os botões de ano aparecem.

     <div data-grafico="linhas-multiplas" data-dados='{{ grafico | tojson }}'></div>

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;
  const A = G.apoio;

  /* A de baixo guarda os dois níveis do eixo do tempo: o mês e o ano. */
  const MARGEM = { esq: 58, dir: 24, topo: 26, base: 62 };
  const LARGURA_MINIMA = 300;
  const ALTURA_MINIMA = 200;
  const DURACAO_DO_TRACO_MS = 1400;
  const ESPACO_ENTRE_MESES = 30;
  const CASAS_PADRAO = 2;
  const FOLGA_ENTRE_ETIQUETAS = 26;
  const TOLERANCIA = 1e-9;
  const PADRAO_DA_SERIE = { largura: 2.5, raio: 3.5, traco: null };
  const ESTILO_DO_PAPEL = {
    "linha-base": { largura: 1.5, raio: 2.5, traco: "6,4" },
    realizado: { largura: 3, raio: 4 },
    tendencia: { traco: "6,4" },
  };

  /* ---------- Dados ---------- */

  function normalizarSeries(dados) {
    return (dados.series || []).map(function (bruta, indice) {
      const serie = Object.assign({}, PADRAO_DA_SERIE, ESTILO_DO_PAPEL[bruta.papel], bruta);
      const nome = serie.cor || serie.papel;
      serie.rotulo = serie.rotulo || serie.id;
      serie.corCss = nome ? G.cor(nome) : G.corDaSequencia(indice);
      return serie;
    });
  }

  function mesValido(periodo) {
    return Boolean(periodo) && Number.isInteger(periodo.ano) && Number.isInteger(periodo.mes) && periodo.mes >= 1 && periodo.mes <= 12;
  }

  function normalizarPeriodos(dados) {
    return (dados.periodos || [])
      .filter(mesValido)
      .map(function (periodo) {
        return { ano: periodo.ano, mes: periodo.mes, valores: periodo.valores || {} };
      })
      .sort(function (a, b) {
        return a.ano - b.ano || a.mes - b.mes;
      });
  }

  function referenciasDe(dados) {
    return (dados.referencias || [])
      .filter(function (referencia) {
        return Number.isFinite(referencia.valor);
      })
      .map(function (referencia) {
        const nome = referencia.cor || referencia.papel || "texto-suave";
        return { valor: referencia.valor, rotulo: referencia.rotulo, corCss: G.cor(nome), traco: referencia.traco || "6,4" };
      });
  }

  function anosDe(periodos) {
    return Array.from(
      new Set(
        periodos.map(function (periodo) {
          return periodo.ano;
        }),
      ),
    ).sort(function (a, b) {
      return a - b;
    });
  }

  /* ---------- Eixo ---------- */

  function limite(explicito, calculado) {
    return Number.isFinite(explicito) ? explicito : calculado;
  }

  function limitesDoEixo(dados, numeros) {
    const eixo = dados.eixo || {};
    const dosDados = numeros.length ? { menor: Math.min(...numeros), maior: Math.max(...numeros) } : { menor: 0, maior: 1 };
    const comZero = dados.base_zero !== false;
    return {
      menor: limite(eixo.min, comZero ? Math.min(0, dosDados.menor) : dosDados.menor),
      maior: limite(eixo.max, comZero ? Math.max(0, dosDados.maior) : dosDados.maior),
    };
  }

  /* Do zero, o eixo é o das outras curvas; fora dele, o passo redondo que
     cabe o intervalo, com as pontas em múltiplos dele. */
  function escalaDaFaixa(menor, maior) {
    if (menor === 0) return Object.assign({ min: 0 }, G.escalaLivre(maior));
    const base = G.escalaLivre(maior - menor).passos;
    const passo = base[1] - base[0];
    const fundo = Math.floor(menor / passo + TOLERANCIA) * passo;
    const alto = Math.ceil(maior / passo - TOLERANCIA) * passo;
    const topo = alto > fundo ? alto : fundo + passo;
    const intervalos = Math.round((topo - fundo) / passo);
    return {
      min: fundo,
      max: topo,
      passos: Array.from({ length: intervalos + 1 }, function (_vazio, i) {
        return fundo + i * passo;
      }),
    };
  }

  /* Casas decimais que o passo do eixo pede (0,25 pede duas). */
  function casasDoPasso(passo) {
    for (let casas = 0; casas < 4; casas += 1) {
      const fator = Math.pow(10, casas);
      if (Math.abs(passo * fator - Math.round(passo * fator)) < TOLERANCIA * fator) return casas;
    }
    return 3;
  }

  /* ---------- Linha ---------- */

  function arredondar(valor) {
    return Math.round(valor * 100) / 100;
  }

  function entre(valor, a, b) {
    return Math.min(Math.max(valor, Math.min(a, b)), Math.max(a, b));
  }

  /* Curva de Catmull-Rom em Bézier, com as alças presas à altura dos dois
     pontos da ponta: a linha não passa abaixo de zero nem acima de uma
     leitura entre duas leituras vizinhas. */
  function caminhoSuave(pontos) {
    let caminho = "M" + arredondar(pontos[0][0]) + "," + arredondar(pontos[0][1]);
    for (let i = 0; i < pontos.length - 1; i++) {
      const p0 = pontos[i - 1] || pontos[i];
      const p1 = pontos[i];
      const p2 = pontos[i + 1];
      const p3 = pontos[i + 2] || p2;
      const c1y = entre(p1[1] + (p2[1] - p0[1]) / 6, p1[1], p2[1]);
      const c2y = entre(p2[1] - (p3[1] - p1[1]) / 6, p1[1], p2[1]);
      const curva = [p1[0] + (p2[0] - p0[0]) / 6, c1y, p2[0] - (p3[0] - p1[0]) / 6, c2y, p2[0], p2[1]];
      caminho += " C" + curva.map(arredondar).join(" ");
    }
    return caminho;
  }

  function caminhoReto(pontos) {
    return pontos
      .map(function (ponto, i) {
        return (i === 0 ? "M" : "L") + arredondar(ponto[0]) + "," + arredondar(ponto[1]);
      })
      .join(" ");
  }

  /* As leituras seguidas de uma série; um mês sem leitura quebra a linha. */
  function trechosDa(ctx, serie) {
    const trechos = [];
    let atual = [];
    ctx.pontos.forEach(function (ponto) {
      const valor = ponto.valores[serie.id];
      if (Number.isFinite(valor)) {
        atual.push([ponto.x, ctx.y(valor)]);
        return;
      }
      if (atual.length) trechos.push(atual);
      atual = [];
    });
    if (atual.length) trechos.push(atual);
    return trechos;
  }

  /* ---------- Desenho ---------- */

  function paleta() {
    return {
      grade: G.cor("--neutro-100"),
      eixo: G.cor("--neutro-200"),
      eixoTexto: G.cor("--neutro-300"),
      mes: G.cor("--neutro-600"),
      ano: G.cor("--brand-title"),
      contorno: G.cor("--branco"),
      etiqueta: G.cor("--branco"),
    };
  }

  function montarContexto(base) {
    const largura = Math.max(base.tela.clientWidth, LARGURA_MINIMA);
    const altura = Math.max(base.tela.clientHeight, ALTURA_MINIMA);
    const area = { esq: MARGEM.esq, dir: largura - MARGEM.dir, topo: MARGEM.topo, base: altura - MARGEM.base };
    area.largura = area.dir - area.esq;
    area.altura = area.base - area.topo;
    const escalaY = base.escalaY;
    const folga = area.largura / Math.max(base.periodos.length, 1);
    const pontos = base.periodos.map(function (periodo, i) {
      return Object.assign({}, periodo, { x: area.esq + (i + 0.5) * folga });
    });
    return {
      svg: G.svg("svg", { class: "graf__svg", viewBox: "0 0 " + largura + " " + altura, role: "group", "aria-label": base.dados.titulo }),
      dados: base.dados,
      series: base.series,
      referencias: base.referencias,
      pontos: pontos,
      area: area,
      folga: folga,
      escalaY: escalaY,
      y: function (valor) {
        return area.base - ((valor - escalaY.min) / (escalaY.max - escalaY.min)) * area.altura;
      },
      escrever: base.escrever,
      dica: base.dica,
      paleta: paleta(),
      animaveis: [],
    };
  }

  function desenharGrade(ctx) {
    const casas = casasDoPasso(ctx.escalaY.passos[1] - ctx.escalaY.passos[0]);
    ctx.escalaY.passos.forEach(function (valor) {
      const y = ctx.y(valor);
      ctx.svg.appendChild(
        G.svg("line", { x1: ctx.area.esq, y1: y, x2: ctx.area.dir, y2: y, stroke: ctx.paleta.grade, "stroke-width": 1 }),
      );
      ctx.svg.appendChild(
        G.svg("text", { x: ctx.area.esq - 8, y: y + 4, "font-size": 11, fill: ctx.paleta.eixoTexto, "text-anchor": "end" }, [
          G.fmt.numero(valor, casas),
        ]),
      );
    });
  }

  function desenharReferencias(ctx) {
    ctx.referencias.forEach(function (referencia) {
      if (referencia.valor < ctx.escalaY.min || referencia.valor > ctx.escalaY.max) return;
      const y = ctx.y(referencia.valor);
      ctx.svg.appendChild(
        G.svg("line", {
          x1: ctx.area.esq,
          y1: y,
          x2: ctx.area.dir,
          y2: y,
          stroke: referencia.corCss,
          "stroke-width": 1.5,
          "stroke-dasharray": referencia.traco,
        }),
      );
    });
  }

  function desenharSerie(ctx, serie) {
    const suave = ctx.dados.suavizar !== false;
    const trechos = trechosDa(ctx, serie);
    trechos.forEach(function (trecho) {
      if (trecho.length < 2) return;
      const linha = G.svg("path", {
        d: suave ? caminhoSuave(trecho) : caminhoReto(trecho),
        fill: "none",
        stroke: serie.corCss,
        "stroke-width": serie.largura,
        "stroke-linecap": "round",
        "stroke-linejoin": "round",
        "stroke-dasharray": serie.traco,
      });
      ctx.svg.appendChild(linha);
      if (!serie.traco) ctx.animaveis.push(linha);
    });
    trechos.forEach(function (trecho) {
      trecho.forEach(function (ponto) {
        ctx.svg.appendChild(
          G.svg("circle", {
            class: "graf-linhas__ponto",
            cx: ponto[0],
            cy: ponto[1],
            r: serie.raio,
            fill: serie.corCss,
            stroke: ctx.paleta.contorno,
            "stroke-width": (serie.raio - 0.5) / 2,
          }),
        );
      });
    });
  }

  /* A última leitura de cada série leva o valor. Etiquetas de séries que
     terminam juntas (a diferença de altura menor que a da caixa) vão uma
     para cima do ponto e a outra para baixo. */
  function desenharEtiquetas(ctx) {
    const finais = ctx.series
      .map(function (serie) {
        const lidos = ctx.pontos.filter(function (ponto) {
          return Number.isFinite(ponto.valores[serie.id]);
        });
        const ultimo = lidos[lidos.length - 1];
        return ultimo ? { serie: serie, x: ultimo.x, valor: ultimo.valores[serie.id], y: ctx.y(ultimo.valores[serie.id]) } : null;
      })
      .filter(Boolean)
      .sort(function (a, b) {
        return a.y - b.y;
      });
    finais.forEach(function (final, i) {
      const colada = i > 0 && final.y - finais[i - 1].y < FOLGA_ENTRE_ETIQUETAS;
      const ancora = colada ? final.y + 30 : final.y - 12;
      ctx.svg.appendChild(
        G.svg("rect", { x: final.x - 25, y: ancora - 17, width: 50, height: 22, rx: 4, fill: final.serie.corCss, opacity: 0.93 }),
      );
      ctx.svg.appendChild(
        G.svg(
          "text",
          { x: final.x, y: ancora - 2, "font-size": 11, "font-weight": 700, fill: ctx.paleta.etiqueta, "text-anchor": "middle" },
          [ctx.escrever(final.valor)],
        ),
      );
    });
  }

  /* ---------- Eixo do tempo ---------- */

  function desenharMeses(ctx) {
    const passo = Math.max(1, Math.ceil(ESPACO_ENTRE_MESES / ctx.folga));
    ctx.pontos.forEach(function (ponto, i) {
      if (i % passo !== 0) return;
      ctx.svg.appendChild(
        G.svg(
          "text",
          { x: ponto.x, y: ctx.area.base + 20, "font-size": 12, "font-weight": 600, fill: ctx.paleta.mes, "text-anchor": "middle" },
          [G.nomeMes(ponto.mes)],
        ),
      );
    });
  }

  /* O ano fica centrado sob os meses dele; entre dois anos, uma divisa. */
  function desenharAnos(ctx) {
    const intervalos = new Map();
    ctx.pontos.forEach(function (ponto) {
      const atual = intervalos.get(ponto.ano);
      if (atual) atual.x1 = ponto.x + ctx.folga / 2;
      else intervalos.set(ponto.ano, { ano: ponto.ano, x0: ponto.x - ctx.folga / 2, x1: ponto.x + ctx.folga / 2 });
    });
    Array.from(intervalos.values()).forEach(function (intervalo, i) {
      ctx.svg.appendChild(
        G.svg(
          "text",
          { x: (intervalo.x0 + intervalo.x1) / 2, y: ctx.area.base + 46, "font-size": 15, "font-weight": 700, fill: ctx.paleta.ano, "text-anchor": "middle" },
          [String(intervalo.ano)],
        ),
      );
      if (i === 0) return;
      ctx.svg.appendChild(
        G.svg("line", {
          x1: intervalo.x0,
          y1: ctx.area.base + 2,
          x2: intervalo.x0,
          y2: ctx.area.base + 54,
          stroke: ctx.paleta.ano,
          "stroke-width": 1.5,
        }),
      );
    });
  }

  function desenharEixoDoTempo(ctx) {
    ctx.svg.appendChild(
      G.svg("line", { x1: ctx.area.esq, y1: ctx.area.base, x2: ctx.area.dir, y2: ctx.area.base, stroke: ctx.paleta.eixo, "stroke-width": 1 }),
    );
    desenharMeses(ctx);
    desenharAnos(ctx);
  }

  /* ---------- Dica ---------- */

  function conteudoDaDica(ctx, ponto) {
    const linhas = [G.dicaTitulo(G.nomeMes(ponto.mes) + " " + ponto.ano), G.dicaDivisor()];
    ctx.series.forEach(function (serie) {
      const valor = ponto.valores[serie.id];
      linhas.push(G.dicaLinha(serie.corCss, serie.rotulo, [Number.isFinite(valor) ? ctx.escrever(valor) : "–"]));
    });
    return linhas;
  }

  /* Uma faixa transparente por mês: é nela que o ponteiro faz a dica
     aparecer, sem exigir mira no ponto. */
  function desenharAreasDeToque(ctx) {
    ctx.pontos.forEach(function (ponto) {
      const faixa = G.svg("rect", {
        x: ponto.x - ctx.folga / 2,
        y: ctx.area.topo,
        width: ctx.folga,
        height: ctx.area.altura,
        fill: "transparent",
      });
      faixa.addEventListener("pointerenter", function (evento) {
        ctx.dica.mostrar(evento, conteudoDaDica(ctx, ponto));
      });
      faixa.addEventListener("pointermove", ctx.dica.mover);
      faixa.addEventListener("pointerleave", ctx.dica.esconder);
      ctx.svg.appendChild(faixa);
    });
  }

  /* ---------- Montagem ---------- */

  function itensDaLegenda(series, referencias) {
    return series
      .map(function (serie) {
        return { rotulo: serie.rotulo, cor: serie.corCss, traco: Boolean(serie.traco) };
      })
      .concat(
        referencias
          .filter(function (referencia) {
            return referencia.rotulo;
          })
          .map(function (referencia) {
            return { rotulo: referencia.rotulo, cor: referencia.corCss, traco: true };
          }),
      );
  }

  function periodosDoAno(periodos, ano) {
    return ano === null
      ? periodos
      : periodos.filter(function (periodo) {
          return periodo.ano === ano;
        });
  }

  function numerosDoEixo(periodos, series, referencias) {
    const lidos = [];
    periodos.forEach(function (periodo) {
      series.forEach(function (serie) {
        const valor = periodo.valores[serie.id];
        if (Number.isFinite(valor)) lidos.push(valor);
      });
    });
    return lidos.concat(
      referencias.map(function (referencia) {
        return referencia.valor;
      }),
    );
  }

  G.registrar("linhas-multiplas", function (host, dados) {
    const series = normalizarSeries(dados);
    const todos = normalizarPeriodos(dados);
    if (!series.length || !todos.length) {
      G.mostrarMensagem(host, G.rotulo(dados, "vazio"));
      return null;
    }
    const referencias = referenciasDe(dados);
    const casas = Number.isInteger(dados.casas) ? dados.casas : CASAS_PADRAO;
    const unidade = typeof dados.unidade === "string" ? dados.unidade : "";
    const estado = { ano: null };
    const quadro = A.moldura(host, {
      dados: dados,
      anos: anosDe(todos),
      aoEscolherAno: escolherAno,
      itensLegenda: itensDaLegenda(series, referencias),
    });

    function escolherAno(ano) {
      estado.ano = ano;
      quadro.anos.marcar(ano);
      desenhar(true);
    }

    function desenhar(animar) {
      if (quadro.tela.clientWidth === 0) return;
      quadro.ajustar();
      quadro.dica.esconder();
      const periodos = periodosDoAno(todos, estado.ano);
      const limites = limitesDoEixo(dados, numerosDoEixo(periodos, series, referencias));
      const escalaY = escalaDaFaixa(limites.menor, limites.maior);
      const ctx = montarContexto({
        tela: quadro.tela,
        dados: dados,
        series: series,
        referencias: referencias,
        periodos: periodos,
        escalaY: escalaY,
        dica: quadro.dica,
        escrever: function (valor) {
          return G.fmt.numero(valor, casas) + unidade;
        },
      });
      if (!animar) ctx.svg.classList.add("graf__svg--parado");
      desenharGrade(ctx);
      desenharReferencias(ctx);
      series.forEach(function (serie) {
        desenharSerie(ctx, serie);
      });
      desenharEtiquetas(ctx);
      desenharEixoDoTempo(ctx);
      desenharAreasDeToque(ctx);
      A.substituirSvg(quadro.tela, ctx.svg);
      if (animar) {
        ctx.animaveis.forEach(function (linha) {
          G.animarTraco(linha, DURACAO_DO_TRACO_MS);
        });
      }
    }

    desenhar(true);
    const parar = G.observarTamanho(quadro.tela, function () {
      desenhar(false);
    });
    return {
      destruir: function () {
        parar();
        quadro.dica.esconder();
      },
    };
  });

  G.linhasMultiplas = { escalaDaFaixa: escalaDaFaixa, caminhoSuave: caminhoSuave };
})();
