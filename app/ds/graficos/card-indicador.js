/* ============================================================
   graficos/card-indicador.js — Card Indicador Único

   Porte de "Card Indicador Unico.html" (docs/referencia/graficos/): o valor
   grande na cor do estado, o selo ao lado, a linha de apoio e o trilho fino
   de progresso, sobre a faixa colorida do estado. Serve o indicador-chave de
   cada módulo no Início e nos painéis, clicável, com a referência de gestão
   (previsto, meta, linha de base) logo abaixo do valor.

   O desenho e o contrato dos dados são do motor dos cards (cards.js): este
   visual mostra a referência, a linha de apoio e o trilho de progresso.

     <div data-grafico="card-indicador" data-dados='{{ card | tojson }}'></div>

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;

  G.registrar("card-indicador", function (host, dados) {
    host.replaceChildren(G.cards.montar(host, "card-indicador", dados, { trilho: true, detalhe: false, iconeNoSelo: false }));
    return null;
  });
})();
