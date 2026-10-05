/* ============================================================
   graficos/curva-s-barra-linha.js — Curva S Barra e Linha

   Porte de "Curva S Barra e Linha.html" (docs/referencia/graficos/): barras
   do período (a semana, ou a soma no mês) agrupadas por série, mais as linhas
   acumuladas (no mês fechado, o último acumulado), com o mesmo drill ano,
   mês e semana da Curva S Linha. A dica mostra duas colunas: Período e
   Acum.

   Serve o desembolso previsto x realizado, a contratação acumulada e o
   avanço por período com acumulado. O contrato dos dados é o de periodos.js;
   com `modo: "periodo"` o servidor manda só a quantidade da semana e o
   acumulado sai da soma corrida.

     <div data-grafico="curva-s-barra-linha" data-dados='{{ grafico | tojson }}'></div>

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;
  const P = G.periodos;

  /* As barras ocupam até 38% da altura útil: o resto é das linhas. */
  const FRACAO_DA_ALTURA = 0.38;

  /* Série de taxa não tem barra: a taxa de um período não se soma. */
  function comBarra(modelo) {
    return modelo.series.filter(function (serie) {
      return serie.tipo !== "razao";
    });
  }

  function maiorPeriodo(ctx, series) {
    let maior = 0;
    ctx.pontos.forEach(function (ponto) {
      series.forEach(function (serie) {
        const valor = ponto.periodo[serie.id];
        if (valor !== null && valor > maior) maior = valor;
      });
    });
    return maior;
  }

  function desenharBarras(ctx) {
    const series = comBarra(ctx.modelo);
    if (!series.length) return;
    const maior = maiorPeriodo(ctx, series);
    const escala = maior > 0 ? (ctx.area.altura * FRACAO_DA_ALTURA) / maior : 1;
    const largura = Math.max(3, Math.min(12, ctx.slotW * 0.22));
    const folga = Math.max(1, largura * 0.15);
    const grupo = series.length * largura + (series.length - 1) * folga;
    ctx.pontos.forEach(function (ponto) {
      series.forEach(function (serie, i) {
        const valor = ponto.periodo[serie.id];
        if (valor === null || valor <= 0) return;
        const altura = valor * escala;
        const x = ponto.x - grupo / 2 + i * (largura + folga);
        ctx.svg.appendChild(
          G.svg("rect", {
            x: x,
            y: ctx.area.base - altura,
            width: largura,
            height: altura,
            rx: 1,
            fill: serie.corCss,
            opacity: 0.85,
          }),
        );
        /* O valor só cabe sobre a barra larga e alta o bastante. */
        if (largura <= 7 || altura <= 18) return;
        ctx.svg.appendChild(
          G.svg(
            "text",
            { x: x + largura / 2, y: ctx.area.base - altura - 4, "font-size": 9, fill: serie.corTexto, "text-anchor": "middle" },
            [P.formatar(ctx, valor, ctx.casas)],
          ),
        );
      });
    });
  }

  const desenhista = {
    classeDica: "graf__tip--larga",
    casasDica: 2,

    itensLegenda: function (modelo) {
      return modelo.series.map(function (serie) {
        return { rotulo: serie.rotulo, cor: serie.corCss, traco: Boolean(serie.traco), barra: serie.tipo !== "razao" };
      });
    },

    desenhar: function (ctx) {
      desenharBarras(ctx);
      P.desenharLinhas(ctx);
    },

    conteudoDica: function (ponto, ctx) {
      const colunas = [G.rotulo(ctx.dados, "periodo"), G.rotulo(ctx.dados, "acumulado")];
      const linhas = [G.dicaTitulo(ponto.rotulo), G.dicaCabecalho(colunas)];
      ctx.modelo.series.forEach(function (serie) {
        linhas.push(
          G.dicaLinha(serie.corCss, serie.rotulo, [
            P.formatar(ctx, ponto.periodo[serie.id], ctx.casasDica),
            P.formatar(ctx, ponto.acum[serie.id], ctx.casasDica),
          ]),
        );
      });
      return linhas;
    },
  };

  G.registrar("curva-s-barra-linha", function (host, dados) {
    return P.criarCurva(host, dados, desenhista);
  });
})();
