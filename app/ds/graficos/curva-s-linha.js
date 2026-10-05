/* ============================================================
   graficos/curva-s-linha.js — Curva S Linha

   Porte de "Curva S Linha.html" (docs/referencia/graficos/): as linhas
   acumuladas, uma por série (linha de base tracejada, previsto, realizado),
   com botões de ano, drill de mês em semanas e dica ao passar o ponteiro.

   Serve a curva S física e financeira, o avanço da programação e a Curva S
   do MAS. O drill, o contrato dos dados e as regras de agregação são do
   motor de períodos (periodos.js); aqui só se escolhe o que desenhar.

     <div data-grafico="curva-s-linha" data-dados='{{ grafico | tojson }}'></div>

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;
  const P = G.periodos;

  const desenhista = {
    classeDica: "",
    casasDica: 1,

    itensLegenda: function (modelo) {
      return modelo.series.map(function (serie) {
        return { rotulo: serie.rotulo, cor: serie.corCss, traco: Boolean(serie.traco) };
      });
    },

    desenhar: function (ctx) {
      P.desenharLinhas(ctx);
    },

    conteudoDica: function (ponto, ctx) {
      const linhas = [G.dicaTitulo(ponto.rotulo), G.dicaDivisor()];
      ctx.modelo.series.forEach(function (serie) {
        const valor = ponto.acum[serie.id];
        if (valor === null) return;
        linhas.push(G.dicaLinha(serie.corCss, serie.rotulo, [P.formatar(ctx, valor, ctx.casasDica)]));
      });
      return linhas;
    },
  };

  G.registrar("curva-s-linha", function (host, dados) {
    return P.criarCurva(host, dados, desenhista);
  });
})();
