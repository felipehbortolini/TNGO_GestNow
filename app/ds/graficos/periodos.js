/* ============================================================
   graficos/periodos.js — Agregação por período e drill ano, mês e semana

   É o motor que as curvas compartilham (curva-s-linha.js e
   curva-s-barra-linha.js). Veio do app de Programação Semanal, onde os
   gráficos agrupam por mês, abrem em semanas ao clique e têm botões de ano.

   A lição que ele carrega: resumir um mês NÃO é sempre somar.
     - quantidade de um período (avanço da semana)  -> soma
     - valor acumulado (curva S)                    -> o último do mês
     - taxa (aderência, PPC)                        -> soma do numerador
                                                       dividida pela soma do
                                                       denominador, nunca a
                                                       média das taxas
   Por isso o servidor manda QUANTIDADE por semana, nunca o percentual pronto,
   e o gráfico resume (D11 da spec).

   Contrato dos dados das curvas (data-dados):
     {
       "titulo": "Curva S física",              // nome acessível do gráfico
       "modo": "periodo" | "acumulado",         // o que `valores` significa
       "formato": "pct" | "numero",             // eixo de 0 a 100% ou escala livre
       "unidade": "%",  "casas": 1,  "casas_dica": 1,
       "series": [{ "id", "rotulo", "papel" | "cor", "traco", "largura",
                    "raio", "destaque", "tipo": "valor" | "razao" }],
       "periodos": [{ "ano": 2026, "mes": 3, "semana": 12,
                      "valores": { "<id da série>": 0.8 } }]
     }
   `valores` é a quantidade da semana (modo "periodo", padrão) ou o acumulado
   até a semana (modo "acumulado"); nulo marca o que ainda não aconteceu. Uma
   série "razao" traz { "num", "den" } por semana. A que mês cada semana
   pertence é decisão do servidor (calendário da plataforma): o gráfico só
   agrupa por (ano, mes) na ordem em que as semanas chegam.

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;

  /* Margens do desenho, em px. A de baixo guarda os três níveis do eixo do
     tempo: semana, mês e ano. */
  const MARGEM = { esq: 58, dir: 20, topo: 30, base: 88 };
  const LARGURA_MINIMA = 300;
  const ALTURA_MINIMA = 200;
  /* Espaço que a legenda ocupa além do próprio texto: a margem da direita e o
     respiro até os botões de ano. */
  const FOLGA_DA_LEGENDA = 24;
  const ESPACO_ENTRE_ETIQUETAS = 56;
  const DURACAO_DO_TRACO_MS = 1500;
  const FOLGA_DO_PONTO_FLUTUANTE = 1e-9;

  /* ---------- Resumos (o "adaptador" de cada série) ---------- */

  function somenteNumeros(valores) {
    return valores.filter(function (valor) {
      return Number.isFinite(valor);
    });
  }

  function ehPar(par) {
    return Boolean(par) && Number.isFinite(par.num) && Number.isFinite(par.den);
  }

  const RESUMOS = {
    soma: function (valores) {
      const itens = somenteNumeros(valores);
      if (!itens.length) return null;
      return itens.reduce(function (total, valor) {
        return total + valor;
      }, 0);
    },
    ultimo: function (valores) {
      const itens = somenteNumeros(valores);
      return itens.length ? itens[itens.length - 1] : null;
    },
    maximo: function (valores) {
      const itens = somenteNumeros(valores);
      return itens.length ? Math.max(...itens) : null;
    },
    /* Recebe pares { num, den } e devolve em %. Soma antes de dividir: a
       média das taxas de cada semana dá o mesmo peso a uma semana de 5 e a
       uma de 500. */
    razao: function (pares) {
      const completos = pares.filter(ehPar);
      const den = completos.reduce(function (total, par) {
        return total + par.den;
      }, 0);
      if (den <= 0) return null;
      const num = completos.reduce(function (total, par) {
        return total + par.num;
      }, 0);
      return (num / den) * 100;
    },
  };

  function resumir(nome, valores) {
    if (!Object.hasOwn(RESUMOS, nome)) {
      console.warn("[graficos] resumo desconhecido: " + nome);
      return null;
    }
    return RESUMOS[nome](valores);
  }

  /* ---------- Séries e semanas ---------- */

  const PADRAO_DA_SERIE = { largura: 2.5, raio: 3.5, traco: null, destaque: false, tipo: "valor" };

  /* Aparência por papel: a linha de base é fina e tracejada, o realizado é a
     linha de destaque (a que se desenha na entrada e leva as etiquetas). */
  const ESTILO_DO_PAPEL = {
    "linha-base": { largura: 1.5, raio: 2.5, traco: "6,4", texto: "texto-suave" },
    realizado: { largura: 3.5, raio: 4.5, destaque: true, texto: "titulo" },
    tendencia: { traco: "6,4" },
  };

  function normalizarSeries(dados) {
    return (dados.series || []).map(function (bruta, indice) {
      const serie = Object.assign({}, PADRAO_DA_SERIE, ESTILO_DO_PAPEL[bruta.papel], bruta);
      const nomeDaCor = serie.cor || serie.papel;
      serie.rotulo = serie.rotulo || serie.id;
      serie.corCss = nomeDaCor ? G.cor(nomeDaCor) : G.corDaSequencia(indice);
      serie.corTexto = serie.texto ? G.cor(serie.texto) : serie.corCss;
      return serie;
    });
  }

  function semanaValida(periodo) {
    return Boolean(periodo) && Number.isInteger(periodo.ano) && Number.isInteger(periodo.mes) && periodo.mes >= 1 && periodo.mes <= 12;
  }

  function normalizarSemanas(dados) {
    return (dados.periodos || []).filter(semanaValida).map(function (periodo) {
      return {
        ano: periodo.ano,
        mes: periodo.mes,
        semana: periodo.semana,
        rotulo: periodo.rotulo,
        valores: periodo.valores || {},
        periodo: {},
        acum: {},
      };
    });
  }

  /* Cada semana ganha o valor do período e o acumulado de cada série, seja
     qual for o modo em que o servidor mandou: quem pede barra usa o primeiro,
     quem pede linha usa o segundo. */
  function derivarAcumulado(semanas, serie, modo) {
    let acumulado = 0;
    semanas.forEach(function (semana) {
      const valor = semana.valores[serie.id];
      if (!Number.isFinite(valor)) {
        semana.periodo[serie.id] = null;
        semana.acum[serie.id] = null;
        return;
      }
      semana.periodo[serie.id] = modo === "acumulado" ? valor - acumulado : valor;
      acumulado = modo === "acumulado" ? valor : acumulado + valor;
      semana.acum[serie.id] = acumulado;
    });
  }

  function derivarRazao(semanas, serie) {
    semanas.forEach(function (semana) {
      const valor = RESUMOS.razao([semana.valores[serie.id]]);
      semana.periodo[serie.id] = valor;
      semana.acum[serie.id] = valor;
    });
  }

  function prepararModelo(dados) {
    const series = normalizarSeries(dados);
    const semanas = normalizarSemanas(dados);
    const modo = dados.modo === "acumulado" ? "acumulado" : "periodo";
    series.forEach(function (serie) {
      if (serie.tipo === "razao") derivarRazao(semanas, serie);
      else derivarAcumulado(semanas, serie, modo);
    });
    const anos = Array.from(new Set(semanas.map(function (semana) {
      return semana.ano;
    }))).sort(function (a, b) {
      return a - b;
    });
    return { series: series, semanas: semanas, anos: anos };
  }

  /* ---------- Drill: meses, semanas e posições ---------- */

  function agruparMeses(semanas) {
    const mapa = new Map();
    semanas.forEach(function (semana) {
      const chave = semana.ano + "_" + semana.mes;
      if (!mapa.has(chave)) mapa.set(chave, { chave: chave, ano: semana.ano, mes: semana.mes, semanas: [] });
      mapa.get(chave).semanas.push(semana);
    });
    return Array.from(mapa.values()).sort(function (a, b) {
      return a.ano - b.ano || a.mes - b.mes;
    });
  }

  /* Mês aberto ocupa uma coluna por semana; fechado, uma só. */
  function posicionar(meses, abertos, area) {
    const colunas = meses.reduce(function (total, mes) {
      return total + (abertos[mes.chave] ? mes.semanas.length : 1);
    }, 0);
    const larguraDaColuna = area.largura / colunas;
    let x = area.esq;
    meses.forEach(function (mes) {
      mes.aberto = Boolean(abertos[mes.chave]);
      mes.x0 = x;
      mes.larg = (mes.aberto ? mes.semanas.length : 1) * larguraDaColuna;
      mes.xc = mes.x0 + mes.larg / 2;
      x += mes.larg;
    });
    return larguraDaColuna;
  }

  function rotuloDaSemana(semana) {
    if (semana.rotulo) return semana.rotulo;
    return semana.semana === undefined || semana.semana === null ? "" : "S" + semana.semana;
  }

  /* O mês fechado resume as suas semanas: a quantidade soma, o acumulado fica
     com o último valor e a taxa divide a soma pela soma. */
  function resumirMes(mes, series) {
    const periodo = {};
    const acum = {};
    series.forEach(function (serie) {
      if (serie.tipo === "razao") {
        const pares = mes.semanas.map(function (semana) {
          return semana.valores[serie.id];
        });
        periodo[serie.id] = RESUMOS.razao(pares);
        acum[serie.id] = periodo[serie.id];
        return;
      }
      periodo[serie.id] = RESUMOS.soma(
        mes.semanas.map(function (semana) {
          return semana.periodo[serie.id];
        }),
      );
      acum[serie.id] = RESUMOS.ultimo(
        mes.semanas.map(function (semana) {
          return semana.acum[serie.id];
        }),
      );
    });
    return { periodo: periodo, acum: acum };
  }

  function pontosDoMes(mes, series, larguraDaColuna) {
    const nomeDoMes = G.nomeMes(mes.mes) + " " + mes.ano;
    if (!mes.aberto) {
      const resumo = resumirMes(mes, series);
      return [{ x: mes.xc, rotulo: nomeDoMes, periodo: resumo.periodo, acum: resumo.acum }];
    }
    return mes.semanas.map(function (semana, i) {
      const rotulo = rotuloDaSemana(semana);
      return {
        x: mes.x0 + i * larguraDaColuna + larguraDaColuna / 2,
        rotulo: rotulo ? rotulo + " · " + nomeDoMes : nomeDoMes,
        periodo: semana.periodo,
        acum: semana.acum,
      };
    });
  }

  function montarPontos(meses, series, larguraDaColuna) {
    return meses.reduce(function (pontos, mes) {
      return pontos.concat(pontosDoMes(mes, series, larguraDaColuna));
    }, []);
  }

  /* ---------- Linha suave ---------- */

  function arredondar(valor) {
    return Math.round(valor * 100) / 100;
  }

  /* Curva de Catmull-Rom convertida em Bézier: passa por todos os pontos
     sem quina. */
  function caminhoSuave(pontos) {
    if (pontos.length < 2) return "";
    const inicio = "M" + arredondar(pontos[0][0]) + "," + arredondar(pontos[0][1]);
    if (pontos.length === 2) return inicio + " L" + arredondar(pontos[1][0]) + "," + arredondar(pontos[1][1]);
    let caminho = inicio;
    for (let i = 0; i < pontos.length - 1; i++) {
      const p0 = pontos[i - 1] || pontos[i];
      const p1 = pontos[i];
      const p2 = pontos[i + 1];
      const p3 = pontos[i + 2] || p2;
      const c1x = p1[0] + (p2[0] - p0[0]) / 6;
      const c1y = p1[1] + (p2[1] - p0[1]) / 6;
      const c2x = p2[0] - (p3[0] - p1[0]) / 6;
      const c2y = p2[1] - (p3[1] - p1[1]) / 6;
      caminho += " C" + [c1x, c1y, c2x, c2y, p2[0], p2[1]].map(arredondar).join(" ");
    }
    return caminho;
  }

  /* ---------- Eixo e formatação ---------- */

  function unidadeDe(dados) {
    if (typeof dados.unidade === "string") return dados.unidade;
    return dados.formato === "numero" ? "" : "%";
  }

  function maiorValor(pontos, series) {
    let maior = 0;
    pontos.forEach(function (ponto) {
      series.forEach(function (serie) {
        const valor = ponto.acum[serie.id];
        if (valor !== null && valor > maior) maior = valor;
      });
    });
    return maior;
  }

  /* Em % o eixo é de 0 a 100, a menos que o dado passe disso (e a soma de
     centésimos que dá 100,00000000000001 não conta como passar). `eixo_max`
     no dado manda: o topo é exatamente ele. */
  function escalaDoEixo(dados, pontos, series) {
    if (Number.isFinite(dados.eixo_max) && dados.eixo_max > 0) {
      return {
        max: dados.eixo_max,
        passos: [0, 1, 2, 3, 4].map(function (i) {
          return (i * dados.eixo_max) / 4;
        }),
      };
    }
    const maior = maiorValor(pontos, series);
    const cabeEmCem = dados.formato !== "numero" && maior <= 100 * (1 + FOLGA_DO_PONTO_FLUTUANTE);
    return G.escalaLivre(cabeEmCem ? 100 : maior);
  }

  function paleta() {
    return {
      grade: G.cor("--neutro-100"),
      eixo: G.cor("--neutro-200"),
      eixoTexto: G.cor("--neutro-300"),
      separador: G.cor("--neutro-200"),
      mesAberto: G.cor("--brand-title"),
      mesFechado: G.cor("--neutro-600"),
      semana: G.cor("--verde-500"),
      fundoAberto: G.cor("--neutro-50"),
      contorno: G.cor("--branco"),
      etiqueta: G.cor("--branco"),
    };
  }

  function formatar(ctx, valor, casas) {
    return valor === null ? "–" : G.fmt.numero(valor, casas) + ctx.unidade;
  }

  /* ---------- Desenho compartilhado ---------- */

  function desenharBase(ctx) {
    const raiz = ctx.svg;
    ctx.escalaY.passos.forEach(function (valor) {
      const y = ctx.y(valor);
      const texto = G.fmt.numero(valor, Number.isInteger(valor) ? 0 : 2) + ctx.unidade;
      /* 18 px cabe em "100%"; rótulo mais longo encolhe para não vazar da margem. */
      const tamanho = Math.min(18, Math.floor(46 / (texto.length * 0.58)));
      raiz.appendChild(G.svg("line", { x1: ctx.area.esq, y1: y, x2: ctx.area.dir, y2: y, stroke: ctx.paleta.grade, "stroke-width": 1 }));
      raiz.appendChild(
        G.svg("text", { x: ctx.area.esq - 8, y: y + 5, "font-size": tamanho, fill: ctx.paleta.eixoTexto, "text-anchor": "end" }, [texto]),
      );
    });
    ctx.meses.forEach(function (mes) {
      if (!mes.aberto) return;
      raiz.appendChild(
        G.svg("rect", { x: mes.x0, y: ctx.area.topo, width: mes.larg, height: ctx.area.altura + 4, fill: ctx.paleta.fundoAberto }),
      );
    });
  }

  function pontosDaSerie(ctx, serie) {
    return ctx.pontos
      .filter(function (ponto) {
        return ponto.acum[serie.id] !== null;
      })
      .map(function (ponto) {
        return [ponto.x, ctx.y(ponto.acum[serie.id])];
      });
  }

  /* Etiqueta de valor sobre a linha de destaque, uma a cada 56 px: mais
     junto que isso elas se sobrepõem. Perto do topo ela vira para baixo. */
  function desenharEtiquetas(ctx, serie) {
    let ultimoX = -Infinity;
    ctx.pontos.forEach(function (ponto) {
      const valor = ponto.acum[serie.id];
      if (valor === null || ponto.x - ultimoX < ESPACO_ENTRE_ETIQUETAS) return;
      ultimoX = ponto.x;
      const y = ctx.y(valor);
      const baixo = y - ctx.area.topo < 44;
      const ancora = baixo ? y + 36 : y - 12;
      ctx.svg.appendChild(
        G.svg("rect", { x: ponto.x - 26, y: ancora - 20, width: 52, height: 22, rx: 4, fill: serie.corCss, opacity: 0.93 }),
      );
      ctx.svg.appendChild(
        G.svg(
          "text",
          { x: ponto.x, y: ancora - 5, "font-size": 11, "font-weight": 700, fill: ctx.paleta.etiqueta, "text-anchor": "middle" },
          [formatar(ctx, valor, ctx.casas)],
        ),
      );
    });
  }

  /* As linhas acumuladas de todas as séries, os pontos e as etiquetas da
     série em destaque. */
  function desenharLinhas(ctx) {
    ctx.modelo.series.forEach(function (serie) {
      const caminho = G.svg("path", {
        d: caminhoSuave(pontosDaSerie(ctx, serie)),
        fill: "none",
        stroke: serie.corCss,
        "stroke-width": serie.largura,
        "stroke-linecap": "round",
        "stroke-linejoin": "round",
        "stroke-dasharray": serie.traco,
      });
      ctx.svg.appendChild(caminho);
      if (serie.destaque) ctx.animaveis.push(caminho);
    });
    ctx.modelo.series.forEach(function (serie) {
      pontosDaSerie(ctx, serie).forEach(function (ponto) {
        ctx.svg.appendChild(
          G.svg("circle", {
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
    ctx.modelo.series
      .filter(function (serie) {
        return serie.destaque;
      })
      .forEach(function (serie) {
        desenharEtiquetas(ctx, serie);
      });
  }

  /* ---------- Eixo do tempo ---------- */

  function desenharSemanas(ctx, mes) {
    const tamanho = Math.max(9, Math.min(13, ctx.slotW * 0.26));
    mes.semanas.forEach(function (semana, i) {
      ctx.svg.appendChild(
        G.svg(
          "text",
          {
            x: mes.x0 + i * ctx.slotW + ctx.slotW / 2,
            y: ctx.area.base + 16,
            "font-size": tamanho,
            "font-weight": 600,
            fill: ctx.paleta.semana,
            "text-anchor": "middle",
          },
          [rotuloDaSemana(semana)],
        ),
      );
    });
  }

  /* O nome do mês é o botão do drill: clique ou Enter/Espaço abre as semanas;
     de novo, fecha. */
  function desenharRotuloDoMes(ctx, mes) {
    const nome = G.nomeMes(mes.mes);
    const texto = G.svg(
      "text",
      {
        x: mes.xc,
        y: ctx.area.base + 36,
        "font-size": Math.max(9, Math.min(14, ctx.slotW * 0.22)),
        "font-weight": 600,
        fill: mes.aberto ? ctx.paleta.mesAberto : ctx.paleta.mesFechado,
        "text-anchor": "middle",
        class: "graf__mes",
        role: "button",
        tabindex: 0,
        "aria-expanded": mes.aberto ? "true" : "false",
        "aria-label": nome + " " + mes.ano,
        "data-mes": mes.chave,
      },
      [nome],
    );
    texto.addEventListener("click", function () {
      ctx.alternar(mes.chave);
    });
    texto.addEventListener("keydown", function (evento) {
      if (evento.key !== "Enter" && evento.key !== " ") return;
      evento.preventDefault();
      ctx.alternar(mes.chave);
    });
    ctx.svg.appendChild(texto);
    if (mes.aberto) {
      ctx.svg.appendChild(
        G.svg("line", {
          x1: mes.x0 + 4,
          y1: ctx.area.base + 39,
          x2: mes.x0 + mes.larg - 4,
          y2: ctx.area.base + 39,
          stroke: ctx.paleta.semana,
          "stroke-width": 1.5,
        }),
      );
    }
  }

  function intervalosDeAno(meses) {
    const mapa = new Map();
    meses.forEach(function (mes) {
      const atual = mapa.get(mes.ano);
      if (atual) atual.x1 = mes.x0 + mes.larg;
      else mapa.set(mes.ano, { ano: mes.ano, x0: mes.x0, x1: mes.x0 + mes.larg });
    });
    return Array.from(mapa.values());
  }

  function desenharAnos(ctx) {
    intervalosDeAno(ctx.meses).forEach(function (intervalo, i) {
      ctx.svg.appendChild(
        G.svg(
          "text",
          {
            x: (intervalo.x0 + intervalo.x1) / 2,
            y: ctx.area.base + 66,
            "font-size": 16,
            "font-weight": 700,
            fill: ctx.paleta.mesAberto,
            "text-anchor": "middle",
          },
          [String(intervalo.ano)],
        ),
      );
      if (i === 0) return;
      ctx.svg.appendChild(
        G.svg("line", {
          x1: intervalo.x0,
          y1: ctx.area.base + 46,
          x2: intervalo.x0,
          y2: ctx.area.base + 74,
          stroke: ctx.paleta.mesAberto,
          "stroke-width": 1.5,
        }),
      );
    });
  }

  function desenharEixoDoTempo(ctx) {
    ctx.svg.appendChild(
      G.svg("line", {
        x1: ctx.area.esq,
        y1: ctx.area.base,
        x2: ctx.area.dir,
        y2: ctx.area.base,
        stroke: ctx.paleta.eixo,
        "stroke-width": 1,
      }),
    );
    ctx.meses.forEach(function (mes, i) {
      if (i > 0) {
        ctx.svg.appendChild(
          G.svg("line", {
            x1: mes.x0,
            y1: ctx.area.base + 2,
            x2: mes.x0,
            y2: ctx.area.base + 84,
            stroke: ctx.paleta.separador,
            "stroke-width": 1,
            "stroke-dasharray": "2,3",
          }),
        );
      }
      if (mes.aberto) desenharSemanas(ctx, mes);
      desenharRotuloDoMes(ctx, mes);
    });
    desenharAnos(ctx);
  }

  /* Uma faixa transparente por ponto: é nela que o ponteiro faz a dica
     aparecer, sem exigir mira no marcador. */
  function desenharAreasDeToque(ctx, desenhista) {
    ctx.pontos.forEach(function (ponto) {
      const faixa = G.svg("rect", {
        x: ponto.x - ctx.slotW / 2,
        y: ctx.area.topo,
        width: ctx.slotW,
        height: ctx.area.altura,
        fill: "transparent",
      });
      faixa.addEventListener("pointerenter", function (evento) {
        ctx.dica.mostrar(evento, desenhista.conteudoDica(ponto, ctx));
      });
      faixa.addEventListener("pointermove", ctx.dica.mover);
      faixa.addEventListener("pointerleave", ctx.dica.esconder);
      ctx.svg.appendChild(faixa);
    });
  }

  /* ---------- A curva completa ---------- */

  function substituirSvg(tela, novo) {
    const anterior = tela.querySelector(":scope > svg");
    if (anterior) anterior.remove();
    tela.insertBefore(novo, tela.firstChild);
  }

  function inteiroOu(valor, padrao) {
    return Number.isInteger(valor) ? valor : padrao;
  }

  /* Ano null é "Todos". */
  function semanasDoAno(modelo, ano) {
    if (ano === null) return modelo.semanas;
    return modelo.semanas.filter(function (semana) {
      return semana.ano === ano;
    });
  }

  function montarContexto(base) {
    const largura = Math.max(base.tela.clientWidth, LARGURA_MINIMA);
    const altura = Math.max(base.tela.clientHeight, ALTURA_MINIMA);
    const area = { esq: MARGEM.esq, dir: largura - MARGEM.dir, topo: MARGEM.topo, base: altura - MARGEM.base };
    area.largura = area.dir - area.esq;
    area.altura = area.base - area.topo;
    const meses = agruparMeses(semanasDoAno(base.modelo, base.estado.ano));
    const slotW = posicionar(meses, base.estado.abertos, area);
    const pontos = montarPontos(meses, base.modelo.series, slotW);
    const escalaY = escalaDoEixo(base.dados, pontos, base.modelo.series);
    const casas = inteiroOu(base.dados.casas, 1);
    return {
      /* role="group" e não "img": dentro de uma imagem os botões dos meses
         ficariam fora do alcance do leitor de tela. */
      svg: G.svg("svg", {
        class: "graf__svg",
        viewBox: "0 0 " + largura + " " + altura,
        role: "group",
        "aria-label": base.dados.titulo,
      }),
      modelo: base.modelo,
      dados: base.dados,
      area: area,
      meses: meses,
      pontos: pontos,
      slotW: slotW,
      escalaY: escalaY,
      y: function (valor) {
        return area.base - (valor / escalaY.max) * area.altura;
      },
      unidade: unidadeDe(base.dados),
      casas: casas,
      casasDica: inteiroOu(base.dados.casas_dica, inteiroOu(base.desenhista.casasDica, casas)),
      paleta: paleta(),
      animaveis: [],
    };
  }

  /* Monta a moldura (botões de ano, legenda, tela com a dica) e devolve a
     instância. `desenhista` diz o que se desenha em cada curva:
       classeDica, casasDica
       itensLegenda(modelo)        -> itens de G.criarLegenda
       desenhar(ctx)               -> marcas no ctx.svg (linhas, barras...)
       conteudoDica(ponto, ctx)    -> nós da dica */
  function criarCurva(host, dados, desenhista) {
    const modelo = prepararModelo(dados);
    if (!modelo.semanas.length) {
      G.mostrarMensagem(host, G.rotulo(dados, "vazio"));
      return null;
    }
    const estado = { ano: null, abertos: {}, foco: null };
    const anos = modelo.anos.length > 1 ? G.criarAnos(modelo.anos, dados, escolherAno) : null;
    const legenda = G.criarLegenda(desenhista.itensLegenda(modelo));
    const topo = G.el(
      "div",
      { class: "graf__topo" + (anos ? "" : " graf__topo--sem-anos") },
      anos ? [anos.elemento, legenda] : [legenda],
    );
    const tela = G.el("div", { class: "graf__tela" });
    host.replaceChildren(topo, tela);
    const dica = G.criarDica(tela, desenhista.classeDica);

    function escolherAno(ano) {
      estado.ano = ano;
      estado.abertos = {};
      anos.marcar(ano);
      desenhar(true);
    }

    function alternarMes(chave) {
      estado.abertos[chave] = !estado.abertos[chave];
      estado.foco = chave;
      desenhar(true);
    }

    function devolverFoco() {
      if (estado.foco === null) return;
      const alvo = tela.querySelector('[data-mes="' + estado.foco + '"]');
      if (alvo) alvo.focus();
      estado.foco = null;
    }

    /* A legenda fica à direita, e os botões de ano no centro, enquanto os dois
       lados cabem; senão a legenda desce para baixo dos botões. Mede-se a
       legenda solta (sem is-estreito), que é quando ela tem o tamanho do texto. */
    function ajustarTopo() {
      topo.classList.remove("is-estreito");
      if (!anos) return;
      const necessario = anos.elemento.offsetWidth + 2 * (legenda.offsetWidth + FOLGA_DA_LEGENDA);
      topo.classList.toggle("is-estreito", tela.clientWidth < necessario);
    }

    function desenhar(animar) {
      if (tela.clientWidth === 0) return;
      ajustarTopo();
      dica.esconder();
      const ctx = montarContexto({ tela: tela, modelo: modelo, estado: estado, dados: dados, desenhista: desenhista });
      ctx.dica = dica;
      ctx.alternar = alternarMes;
      if (!animar) ctx.svg.classList.add("graf__svg--parado");
      desenharBase(ctx);
      desenhista.desenhar(ctx);
      desenharEixoDoTempo(ctx);
      desenharAreasDeToque(ctx, desenhista);
      substituirSvg(tela, ctx.svg);
      if (animar) {
        ctx.animaveis.forEach(function (caminho) {
          G.animarTraco(caminho, DURACAO_DO_TRACO_MS);
        });
      }
      devolverFoco();
    }

    desenhar(true);
    const parar = G.observarTamanho(tela, function () {
      desenhar(false);
    });
    return {
      destruir: function () {
        parar();
        dica.esconder();
      },
    };
  }

  G.periodos = {
    resumos: RESUMOS,
    resumir: resumir,
    criarCurva: criarCurva,
    desenharLinhas: desenharLinhas,
    formatar: formatar,
    caminhoSuave: caminhoSuave,
  };
})();
