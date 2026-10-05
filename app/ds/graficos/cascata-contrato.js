/* ============================================================
   graficos/cascata-contrato.js — Cascata de valor do contrato

   Visual novo (a coletânea não tem equivalente), no padrão dela: tipografia,
   dica escura, legenda e animação de entrada. É a cascata (waterfall) da
   ficha do contrato: o valor original, os aditivos aprovados que o
   aumentam, o medido que o reduz, e os totais no meio e no fim (valor
   atual, saldo a faturar). As cores seguem o protótipo: totais no verde da
   marca, acréscimos no laranja, reduções no roxo.

   Contrato dos dados (data-dados):
     {
       "titulo": "Cascata de valor do contrato",
       "formato": { "divisor": 100, "moeda": "BRL", "casas": 0 },
       "etapas": [
         { "id": "original", "rotulo": "Valor original", "tipo": "total", "valor": 120000000 },
         { "id": "aditivos", "rotulo": "Aditivos aprovados", "valor": 18000000 },
         { "id": "atual", "rotulo": "Valor atual", "tipo": "total" },
         { "id": "medido", "rotulo": "Medido", "valor": -64000000 },
         { "id": "saldo", "rotulo": "Saldo a faturar", "tipo": "total" }
       ]
     }
   `tipo: "total"` desenha a barra do zero até o valor; sem `tipo` a etapa é
   uma variação, com sinal, que sai de onde a anterior parou. Total sem `valor`
   assume a soma corrida até ali; com `valor`, ele manda (a fórmula do
   negócio, como valor atual = original + aditivos, é do servidor, que também
   escolhe o papel de cor de uma etapa em `papel`). `formato` serve a quem
   manda centavos (`divisor: 100`) e pede reais (`moeda: "BRL"`); os rótulos
   sobre as barras saem na forma compacta ("R$ 1,2 mi") e a dica na completa.

     <div data-grafico="cascata-contrato" data-dados='{{ grafico | tojson }}'></div>

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;
  const A = G.apoio;

  const ROTULOS = { total: "Total", acrescimo: "Acréscimo", reducao: "Redução", valor: "Valor", acumulado: "Acumulado" };
  /* A de cima guarda o rótulo de valor sobre a barra mais alta; a de baixo, as
     três linhas do nome da etapa. */
  const MARGEM = { esq: 66, dir: 16, topo: 36, base: 62 };
  const LARGURA_MINIMA = 280;
  const ALTURA_MINIMA = 220;
  const PAPEL_DO_TIPO = { total: "marca", acrescimo: "atencao", reducao: "comprometido" };
  const FRACAO_DA_COLUNA = 0.58;
  const LARGURA_MAXIMA_DA_BARRA = 96;
  const ALTURA_MINIMA_DA_BARRA = 2;
  const PIXELS_POR_CARACTERE = 6.2;
  const LINHAS_DO_NOME = 3;
  const ATRASO_ENTRE_BARRAS_MS = 120;
  /* Folga para o ruído de ponto flutuante na escala. */
  const TOLERANCIA = 1e-9;

  /* ---------- Contas ---------- */

  /* Aonde a barra chega: o total vale o seu valor (ou, sem ele, o acumulado
     até ali); a variação soma ao acumulado. */
  function nivelFinal(etapa, acumulado) {
    const valor = Number.isFinite(etapa.valor) ? etapa.valor : null;
    if (etapa.tipo === "total") return valor === null ? acumulado : valor;
    return acumulado + (valor === null ? 0 : valor);
  }

  function tipoDaEtapa(etapa, de, ate) {
    if (etapa.tipo === "total") return "total";
    return ate >= de ? "acrescimo" : "reducao";
  }

  /* A soma corrida da cascata: cada etapa ganha de onde a barra sai (`de`) e
     aonde chega (`ate`). Um total sem valor assume o acumulado até ali. */
  function montarCascata(etapas) {
    let acumulado = 0;
    return etapas.map(function (etapa) {
      const de = etapa.tipo === "total" ? 0 : acumulado;
      const ate = nivelFinal(etapa, acumulado);
      acumulado = ate;
      return {
        id: etapa.id,
        rotulo: etapa.rotulo,
        papel: etapa.cor || etapa.papel,
        de: de,
        ate: ate,
        variacao: ate - de,
        tipo: tipoDaEtapa(etapa, de, ate),
      };
    });
  }

  /* Eixo com passo redondo que cobre do menor ao maior nível, zero incluído. */
  function escalaDoEixo(niveis) {
    const maior = Math.max(
      0,
      ...niveis.map(function (nivel) {
        return Math.max(nivel.de, nivel.ate);
      }),
    );
    const menor = Math.min(
      0,
      ...niveis.map(function (nivel) {
        return Math.min(nivel.de, nivel.ate);
      }),
    );
    const base = G.escalaLivre(Math.max(maior, -menor)).passos;
    const passo = base[1] - base[0];
    const topo = Math.ceil(maior / passo - TOLERANCIA) * passo;
    const fundo = Math.floor(menor / passo + TOLERANCIA) * passo;
    const intervalos = Math.max(1, Math.round((topo - fundo) / passo));
    return {
      min: fundo,
      max: fundo + intervalos * passo,
      passos: Array.from({ length: intervalos + 1 }, function (_vazio, i) {
        return fundo + i * passo;
      }),
    };
  }

  /* O nome da etapa em até três linhas, com reticências se não couber. */
  function quebrarEmLinhas(texto, maximoDeCaracteres) {
    const palavras = String(texto || "").split(/\s+/).filter(Boolean);
    const linhas = [];
    palavras.forEach(function (palavra) {
      const ultima = linhas.length - 1;
      if (ultima >= 0 && linhas[ultima].length + 1 + palavra.length <= maximoDeCaracteres) {
        linhas[ultima] += " " + palavra;
      } else {
        linhas.push(palavra);
      }
    });
    if (linhas.length <= LINHAS_DO_NOME) return linhas;
    const cabem = linhas.slice(0, LINHAS_DO_NOME);
    cabem[LINHAS_DO_NOME - 1] = cabem[LINHAS_DO_NOME - 1].replace(/.$/, "…");
    return cabem;
  }

  /* ---------- Cores ---------- */

  function corDaEtapa(etapa) {
    return G.cor(etapa.papel || PAPEL_DO_TIPO[etapa.tipo]);
  }

  function paleta() {
    return {
      grade: G.cor("--neutro-100"),
      eixo: G.cor("--neutro-200"),
      eixoTexto: G.cor("--neutro-300"),
      ligacao: G.cor("--neutro-400"),
      nome: G.cor("--text-secondary"),
      valor: G.cor("--text-primary"),
    };
  }

  /* ---------- Desenho ---------- */

  function montarContexto(base) {
    const largura = Math.max(base.tela.clientWidth, LARGURA_MINIMA);
    const altura = Math.max(base.tela.clientHeight, ALTURA_MINIMA);
    const area = { esq: MARGEM.esq, dir: largura - MARGEM.dir, topo: MARGEM.topo, base: altura - MARGEM.base };
    area.largura = area.dir - area.esq;
    area.altura = area.base - area.topo;
    const eixo = escalaDoEixo(base.niveis);
    const coluna = area.largura / base.niveis.length;
    return {
      svg: G.svg("svg", { class: "graf__svg", viewBox: "0 0 " + largura + " " + altura, role: "img", "aria-label": base.dados.titulo }),
      niveis: base.niveis,
      dica: base.dica,
      formato: base.formato,
      rotulo: base.rotulo,
      area: area,
      eixo: eixo,
      coluna: coluna,
      barra: Math.min(coluna * FRACAO_DA_COLUNA, LARGURA_MAXIMA_DA_BARRA),
      paleta: paleta(),
      y: function (valor) {
        return area.base - ((valor - eixo.min) / (eixo.max - eixo.min)) * area.altura;
      },
    };
  }

  function desenharGrade(ctx) {
    ctx.eixo.passos.forEach(function (valor) {
      const y = ctx.y(valor);
      const zero = Math.abs(valor) < TOLERANCIA;
      ctx.svg.appendChild(
        G.svg("line", {
          x1: ctx.area.esq,
          y1: y,
          x2: ctx.area.dir,
          y2: y,
          stroke: zero ? ctx.paleta.eixo : ctx.paleta.grade,
          "stroke-width": zero ? 1.5 : 1,
        }),
      );
      ctx.svg.appendChild(
        G.svg("text", { x: ctx.area.esq - 8, y: y + 4, "font-size": 11, fill: ctx.paleta.eixoTexto, "text-anchor": "end" }, [
          ctx.formato.compacto(valor),
        ]),
      );
    });
  }

  function centroDaColuna(ctx, indice) {
    return ctx.area.esq + (indice + 0.5) * ctx.coluna;
  }

  /* A linha fina que liga o fim de uma barra ao começo da próxima. */
  function desenharLigacao(ctx, indice) {
    if (indice >= ctx.niveis.length - 1) return;
    const nivel = ctx.niveis[indice];
    const y = ctx.y(nivel.ate);
    ctx.svg.appendChild(
      G.svg("line", {
        x1: centroDaColuna(ctx, indice) + ctx.barra / 2,
        y1: y,
        x2: centroDaColuna(ctx, indice + 1) - ctx.barra / 2,
        y2: y,
        stroke: ctx.paleta.ligacao,
        "stroke-width": 1,
        "stroke-dasharray": "3,3",
      }),
    );
  }

  function desenharBarra(ctx, indice) {
    const nivel = ctx.niveis[indice];
    const topo = ctx.y(Math.max(nivel.de, nivel.ate));
    const altura = Math.max(ctx.y(Math.min(nivel.de, nivel.ate)) - topo, ALTURA_MINIMA_DA_BARRA);
    const barra = G.svg("rect", {
      class: "graf-cascata__barra",
      x: centroDaColuna(ctx, indice) - ctx.barra / 2,
      y: topo,
      width: ctx.barra,
      height: altura,
      rx: 2,
      fill: corDaEtapa(nivel),
    });
    barra.style.setProperty("--graf-atraso", indice * ATRASO_ENTRE_BARRAS_MS + "ms");
    ctx.svg.appendChild(barra);
  }

  function textoDoValor(ctx, nivel) {
    if (nivel.tipo === "total") return ctx.formato.compacto(nivel.ate);
    return (nivel.variacao > 0 ? "+" : "") + ctx.formato.compacto(nivel.variacao);
  }

  function desenharRotulos(ctx, indice) {
    const nivel = ctx.niveis[indice];
    const x = centroDaColuna(ctx, indice);
    const valor = G.svg(
      "text",
      {
        class: "graf-cascata__valor",
        x: x,
        y: ctx.y(Math.max(nivel.de, nivel.ate)) - 7,
        "font-size": 12,
        "font-weight": 700,
        fill: ctx.paleta.valor,
        "text-anchor": "middle",
      },
      [textoDoValor(ctx, nivel)],
    );
    valor.style.setProperty("--graf-atraso", indice * ATRASO_ENTRE_BARRAS_MS + 300 + "ms");
    ctx.svg.appendChild(valor);
    const linhas = quebrarEmLinhas(nivel.rotulo, Math.max(6, Math.floor((ctx.coluna - 6) / PIXELS_POR_CARACTERE)));
    linhas.forEach(function (linha, i) {
      ctx.svg.appendChild(
        G.svg(
          "text",
          { x: x, y: ctx.area.base + 18 + i * 14, "font-size": 11, "font-weight": 600, fill: ctx.paleta.nome, "text-anchor": "middle" },
          [linha],
        ),
      );
    });
  }

  function conteudoDaDica(ctx, nivel) {
    const cor = corDaEtapa(nivel);
    const linhas = [G.dicaTitulo(nivel.rotulo), G.dicaDivisor()];
    if (nivel.tipo === "total") {
      linhas.push(G.dicaLinha(cor, ctx.rotulo("valor"), [ctx.formato.completo(nivel.ate)]));
      return linhas;
    }
    const sinal = nivel.variacao > 0 ? "+" : "";
    linhas.push(G.dicaLinha(cor, ctx.rotulo(nivel.tipo), [sinal + ctx.formato.completo(nivel.variacao)]));
    linhas.push(G.dicaLinha(G.cor("neutro"), ctx.rotulo("acumulado"), [ctx.formato.completo(nivel.ate)]));
    return linhas;
  }

  /* Uma faixa transparente por coluna: é nela que o ponteiro faz a dica
     aparecer, sem exigir mira na barra. */
  function desenharAreasDeToque(ctx) {
    ctx.niveis.forEach(function (nivel, indice) {
      const faixa = G.svg("rect", {
        x: centroDaColuna(ctx, indice) - ctx.coluna / 2,
        y: ctx.area.topo - MARGEM.topo / 2,
        width: ctx.coluna,
        height: ctx.area.altura + MARGEM.topo / 2,
        fill: "transparent",
      });
      faixa.addEventListener("pointerenter", function (evento) {
        ctx.dica.mostrar(evento, conteudoDaDica(ctx, nivel));
      });
      faixa.addEventListener("pointermove", ctx.dica.mover);
      faixa.addEventListener("pointerleave", ctx.dica.esconder);
      ctx.svg.appendChild(faixa);
    });
  }

  /* ---------- Montagem ---------- */

  /* A legenda mostra só os tipos que a cascata usa. */
  function itensDaLegenda(niveis, rotulo) {
    const usados = [];
    niveis.forEach(function (nivel) {
      if (!usados.some(function (item) { return item.tipo === nivel.tipo; })) {
        usados.push({ tipo: nivel.tipo, rotulo: rotulo(nivel.tipo), cor: corDaEtapa(nivel), barra: true });
      }
    });
    return usados;
  }

  G.registrar("cascata-contrato", function (host, dados) {
    const etapas = Array.isArray(dados.etapas) ? dados.etapas : [];
    if (!etapas.length) {
      G.mostrarMensagem(host, G.rotulo(dados, "vazio"));
      return null;
    }
    const rotulo = A.rotulador(dados, ROTULOS);
    const niveis = montarCascata(etapas);
    const quadro = A.moldura(host, {
      dados: dados,
      anos: [],
      itensLegenda: itensDaLegenda(niveis, rotulo),
      classeDica: "graf__tip--larga",
      soBarras: true,
    });
    const formato = A.formatador(dados.formato);

    function desenhar(animar) {
      if (quadro.tela.clientWidth === 0) return;
      quadro.dica.esconder();
      const ctx = montarContexto({ tela: quadro.tela, niveis: niveis, dados: dados, dica: quadro.dica, formato: formato, rotulo: rotulo });
      if (!animar) ctx.svg.classList.add("graf__svg--parado");
      desenharGrade(ctx);
      niveis.forEach(function (_nivel, indice) {
        desenharLigacao(ctx, indice);
        desenharBarra(ctx, indice);
        desenharRotulos(ctx, indice);
      });
      desenharAreasDeToque(ctx);
      A.substituirSvg(quadro.tela, ctx.svg);
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

  G.cascata = { montar: montarCascata, escalaDoEixo: escalaDoEixo };
})();
