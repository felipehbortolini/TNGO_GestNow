/* ============================================================
   graficos/comparativo-barras.js — Comparativo de barras entre períodos

   Porte de "Comparativo de Barras Entre periodos.html"
   (docs/referencia/graficos/): para cada painel, duas barras empilhadas (a
   referência e a posição atual, por exemplo linha de base e atual, ou um
   mês e o seguinte) com o mesmo conjunto de categorias, e abaixo delas a
   variação percentual de cada categoria, colorida pelo que é favorável.

   Serve o avanço por período, o real x previsto e a comparação entre meses.

   Contrato dos dados (data-dados):
     {
       "titulo": "Linha de base x Atual",
       "paineis": [{
         "titulo": "Status das atividades",
         "categorias": [{ "id": "no_prazo", "rotulo": "No prazo",
                          "papel": "ok", "favoravel": "sobe" }],
         "linhas": [
           { "rotulo": "Linha de base", "valores": { "no_prazo": 51 } },
           { "rotulo": "Atual",         "valores": { "no_prazo": 48 } }
         ]
       }]
     }
   `favoravel` diz se subir ("sobe") ou cair ("desce") é bom; sem ele a
   variação aparece neutra, sem julgamento. A variação é (atual - referência)
   dividida pela referência: categoria zerada na referência não tem variação.
   O servidor manda as quantidades; totais e percentuais saem aqui.

     <div data-grafico="comparativo-barras" data-dados='{{ grafico | tojson }}'></div>

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;

  function quantidade(linha, categoria) {
    const valor = linha && linha.valores ? linha.valores[categoria.id] : null;
    return Number.isFinite(valor) ? valor : 0;
  }

  function totalDa(linha, categorias) {
    return categorias.reduce(function (total, categoria) {
      return total + quantidade(linha, categoria);
    }, 0);
  }

  function variacao(referencia, atual) {
    return referencia > 0 ? ((atual - referencia) / referencia) * 100 : null;
  }

  function julgamento(percentual, favoravel) {
    if (percentual === null || percentual === 0 || !favoravel) return "neutro";
    const subiu = percentual > 0;
    const subirEhBom = favoravel === "sobe";
    return subiu === subirEhBom ? "bom" : "ruim";
  }

  function simboloDa(percentual) {
    if (percentual === null) return "•";
    if (percentual > 0) return "▲";
    return percentual < 0 ? "▼" : "=";
  }

  function corDaCategoria(categoria, indice) {
    const nome = categoria.cor || categoria.papel;
    return nome ? G.cor(nome) : G.corDaSequencia(indice);
  }

  function legenda(categorias) {
    return G.el(
      "div",
      { class: "graf-comp__legenda" },
      categorias.map(function (categoria, i) {
        const ponto = G.el("span", { class: "graf-comp__ponto" });
        ponto.style.background = corDaCategoria(categoria, i);
        return G.el("div", { class: "graf-comp__leg" }, [ponto, G.el("span", { class: "graf-comp__leg-texto", texto: categoria.rotulo })]);
      }),
    );
  }

  function segmento(valor, categoria, indice) {
    const caixa = G.el("div", { class: "graf-comp__seg", title: categoria.rotulo + ": " + G.fmt.numero(valor, 0) }, [
      G.el("span", { class: "graf-comp__seg-num", texto: G.fmt.numero(valor, 0) }),
    ]);
    caixa.style.flex = valor + " 1 0";
    caixa.style.background = corDaCategoria(categoria, indice);
    return caixa;
  }

  function linhaDeBarra(linha, categorias) {
    const segmentos = categorias
      .map(function (categoria, i) {
        return { valor: quantidade(linha, categoria), categoria: categoria, indice: i };
      })
      .filter(function (parte) {
        return parte.valor > 0;
      })
      .map(function (parte) {
        return segmento(parte.valor, parte.categoria, parte.indice);
      });
    return G.el("div", { class: "graf-comp__linha" }, [
      G.el("div", { class: "graf-comp__rotulo", texto: linha.rotulo }),
      G.el("div", { class: "graf-comp__fundo" }, [G.el("div", { class: "graf-comp__trilho" }, segmentos)]),
      G.el("div", { class: "graf-comp__total", texto: G.fmt.numero(totalDa(linha, categorias), 0) }),
    ]);
  }

  function chipDeVariacao(categoria, referencia, atual) {
    const percentual = variacao(quantidade(referencia, categoria), quantidade(atual, categoria));
    const texto = percentual === null ? "–" : G.fmt.comSinal(percentual, 1) + "%";
    return G.el(
      "div",
      { class: "graf-comp__delta is-" + julgamento(percentual, categoria.favoravel), title: categoria.rotulo + ": " + texto },
      [
        G.el("span", { class: "graf-comp__delta-rotulo", texto: categoria.rotulo }),
        G.el("div", { class: "graf-comp__delta-base" }, [
          G.el("span", { class: "graf-comp__delta-icone", "aria-hidden": "true", texto: simboloDa(percentual) }),
          G.el("span", { class: "graf-comp__delta-valor", texto: texto }),
        ]),
      ],
    );
  }

  function faixaDeVariacoes(categorias, referencia, atual) {
    const faixa = G.el(
      "div",
      { class: "graf-comp__deltas" },
      categorias.map(function (categoria) {
        return chipDeVariacao(categoria, referencia, atual);
      }),
    );
    faixa.style.gridTemplateColumns = "repeat(" + categorias.length + ", minmax(0, 1fr))";
    return faixa;
  }

  function painel(dadosDoPainel) {
    const categorias = dadosDoPainel.categorias || [];
    const linhas = dadosDoPainel.linhas || [];
    const corpo = [linhaDeBarra(linhas[0], categorias)];
    if (linhas.length > 1) {
      corpo.push(faixaDeVariacoes(categorias, linhas[0], linhas[1]));
      corpo.push(linhaDeBarra(linhas[1], categorias));
    }
    return G.el("section", { class: "graf-comp__painel" }, [
      G.el("div", { class: "graf-comp__cab" }, [
        G.el("div", { class: "graf-comp__titulo", texto: dadosDoPainel.titulo }),
        legenda(categorias),
      ]),
      G.el("div", { class: "graf-comp__linhas" }, corpo),
    ]);
  }

  function painelCompleto(dadosDoPainel) {
    return Array.isArray(dadosDoPainel.linhas) && dadosDoPainel.linhas.length > 0;
  }

  G.registrar("comparativo-barras", function (host, dados) {
    const paineis = (dados.paineis || []).filter(painelCompleto);
    if (!paineis.length) {
      G.mostrarMensagem(host, G.rotulo(dados, "vazio"));
      return null;
    }
    const raiz = G.el("div", { class: "graf-comp" }, [
      dados.titulo ? G.el("div", { class: "graf-comp__titulo-geral", texto: dados.titulo }) : null,
      G.el("div", { class: "graf-comp__pilha" }, paineis.map(painel)),
    ].filter(Boolean));
    host.replaceChildren(raiz);
    return null;
  });
})();
