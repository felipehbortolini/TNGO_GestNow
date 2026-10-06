/* ============================================================
   graficos/card-indicador-detalhes.js — Card Indicador Único com detalhes

   Porte de "Card Indicador Unico com detalhes.html"
   (docs/referencia/graficos/): o valor grande, o selo com ícone, a
   referência de gestão (previsto, meta, linha de base) abaixo do valor, a
   linha de detalhe e a linha de base do indicador. Entra com uma subida
   suave e, num card estreito, perde o detalhe (abaixo de 260 px) e a linha de
   base (abaixo de 200 px), como o original (consulta @container no estilo).

   O desenho e o contrato dos dados são do motor dos cards (cards.js): este
   visual mostra o detalhe e o ícone no selo, e não leva o trilho.

     <div data-grafico="card-indicador-detalhes" data-dados='{{ card | tojson }}'></div>

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;

  G.registrar("card-indicador-detalhes", function (host, dados) {
    host.replaceChildren(
      G.cards.montar(host, "card-indicador-detalhes", dados, { trilho: false, detalhe: true, iconeNoSelo: true, iconePorTom: { erro: "alerta" } }),
    );
    return null;
  });
})();
