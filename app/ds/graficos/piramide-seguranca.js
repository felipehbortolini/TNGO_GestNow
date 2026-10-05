/* ============================================================
   graficos/piramide-seguranca.js — Pirâmide de segurança dupla

   Visual novo (a coletânea não tem equivalente), no padrão dela: tipografia,
   dica escura e animação de entrada. Vem de GI.charts.pyramidPair do
   protótipo, redesenhada: duas pirâmides lado a lado (por exemplo o mês e o
   acumulado), faixas de altura fixa, o nome de cada nível uma vez só na
   coluna do meio, a proporção real escrita embaixo de cada pirâmide e a
   proporção de referência (Bird ou Heinrich) numa linha no rodapé. Serve o
   Painel HSE.

   Contrato dos dados (data-dados):
     {
       "titulo": "Pirâmide de segurança",
       "niveis": [{ "id": "grave", "rotulo": "Lesões graves", "papel": "erro" }],
       "piramides": [
         { "titulo": "No mês", "valores": { "grave": 0, "leve": 2 } },
         { "titulo": "Acumulado", "valores": { "grave": 0, "leve": 16 } }
       ],
       "referencia": {
         "nome": "Bird",
         "termos": [{ "niveis": ["grave"], "valor": 1 },
                    { "niveis": ["leve"], "valor": 10 }],
         "nota": "níveis 3 e 4 somados"
       }
     }
   `niveis` vem do vértice para a base. O servidor manda a contagem de cada
   nível; a proporção real sai aqui. Cada termo da referência diz que níveis
   cobre (Heinrich, 1 : 29 : 300, soma dois níveis no último termo), e a
   proporção real usa os mesmos grupos. Com o primeiro termo maior que zero,
   a proporção real é dividida por ele ("Real 1 : 12,5 : 31"); com zero, não
   há como dividir e a linha mostra a contagem ("Real 0 : 16 : 31 : 190"). A
   referência vem dos parâmetros do projeto: a biblioteca não traz a dela.

     <div data-grafico="piramide-seguranca" data-dados='{{ grafico | tojson }}'></div>

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;
  const A = G.apoio;

  const ROTULOS = { real: "Real", referencia: "Referência" };
  /* Até esta largura a faixa baixa de 44 para 40 px (o atributo vai para o
     CSS, como no Pareto). */
  const LARGURA_ESTREITA = 480;
  const ATRASO_ENTRE_FAIXAS_MS = 90;
  /* A faixa sem ocorrência não some (a forma da pirâmide é fixa), mas fica
     clara para não gritar. */
  const MISTURA_DA_FAIXA_ZERADA = 0.55;
  const CASAS_DA_PROPORCAO = 1;

  /* ---------- Contas ---------- */

  function quantidade(valor) {
    return Number.isFinite(valor) && valor > 0 ? valor : 0;
  }

  function somaDosNiveis(valores, ids) {
    return ids.reduce(function (total, id) {
      return total + quantidade(valores[id]);
    }, 0);
  }

  /* Proporção real de uma pirâmide nos termos da referência. Dividida pelo
     primeiro termo; sem ele (zero), a contagem de cada termo. */
  function proporcaoReal(valores, termos) {
    const somas = termos.map(function (termo) {
      return somaDosNiveis(valores, termo.niveis);
    });
    if (!(somas[0] > 0)) return { termos: somas, normalizada: false };
    return {
      termos: somas.map(function (soma) {
        return soma / somas[0];
      }),
      normalizada: true,
    };
  }

  /* Sem referência, um termo por nível. */
  function termosDe(dados) {
    const referencia = dados.referencia;
    if (referencia && Array.isArray(referencia.termos) && referencia.termos.length) return referencia.termos;
    return dados.niveis.map(function (nivel) {
      return { niveis: [nivel.id], valor: null };
    });
  }

  function textoDosTermos(valores, decimais) {
    return valores
      .map(function (valor) {
        return G.fmt.numero(valor, decimais && !Number.isInteger(valor) ? CASAS_DA_PROPORCAO : 0);
      })
      .join(" : ");
  }

  /* Faixa i de n (0 é o vértice): um trapézio de um triângulo que ocupa a
     largura toda; no vértice, o trapézio é um triângulo. */
  function poligonoDaFaixa(indice, total) {
    const ponto = function (fracao) {
      return Number((fracao * 50).toFixed(2));
    };
    const topo = ponto(indice / total);
    const base = ponto((indice + 1) / total);
    return (
      "polygon(" + (50 - topo) + "% 0, " + (50 + topo) + "% 0, " + (50 + base) + "% 100%, " + (50 - base) + "% 100%)"
    );
  }

  /* ---------- Montagem dos dados ---------- */

  function prepararNiveis(dados) {
    return dados.niveis.map(function (nivel, indice) {
      const nome = nivel.cor || nivel.papel;
      return { id: nivel.id, rotulo: nivel.rotulo, cor: nome ? G.cor(nome) : G.corDaSequencia(indice) };
    });
  }

  function prepararPiramides(dados, niveis, termos) {
    return dados.piramides.slice(0, 2).map(function (piramide) {
      const valores = piramide.valores || {};
      const total = somaDosNiveis(
        valores,
        niveis.map(function (nivel) {
          return nivel.id;
        }),
      );
      return { titulo: piramide.titulo, valores: valores, total: total, real: proporcaoReal(valores, termos) };
    });
  }

  /* ---------- Dica ---------- */

  function conteudoDaDica(ctx, indiceDoNivel) {
    const nivel = ctx.niveis[indiceDoNivel];
    const linhas = [G.dicaTitulo(nivel.rotulo), G.dicaDivisor()];
    ctx.piramides.forEach(function (piramide) {
      const valor = quantidade(piramide.valores[nivel.id]);
      const parte = piramide.total > 0 ? (valor / piramide.total) * 100 : 0;
      linhas.push(
        G.dicaLinha(nivel.cor, piramide.titulo, [
          G.fmt.numero(valor, 0) + " · " + G.fmt.numero(parte, 1) + "% " + G.rotulo(ctx.dados, "doTotal"),
        ]),
      );
    });
    return linhas;
  }

  /* ---------- Desenho ---------- */

  function faixa(ctx, indiceDaPiramide, indiceDoNivel) {
    const nivel = ctx.niveis[indiceDoNivel];
    const valor = quantidade(ctx.piramides[indiceDaPiramide].valores[nivel.id]);
    const no = G.el(
      "div",
      {
        class: "graf-piramide__faixa" + (valor > 0 ? "" : " is-zerada"),
        role: "img",
        "aria-label": nivel.rotulo + ": " + G.fmt.numero(valor, 0),
      },
      [G.el("span", { class: "graf-piramide__numero", texto: G.fmt.numero(valor, 0) })],
    );
    no.style.setProperty("--cor", valor > 0 ? nivel.cor : G.clarear(nivel.cor, MISTURA_DA_FAIXA_ZERADA));
    no.style.setProperty("--graf-atraso", (ctx.niveis.length - 1 - indiceDoNivel) * ATRASO_ENTRE_FAIXAS_MS + "ms");
    no.style.clipPath = poligonoDaFaixa(indiceDoNivel, ctx.niveis.length);
    no.addEventListener("pointerenter", function (evento) {
      ctx.dica.mostrar(evento, conteudoDaDica(ctx, indiceDoNivel));
    });
    no.addEventListener("pointermove", ctx.dica.mover);
    no.addEventListener("pointerleave", ctx.dica.esconder);
    return no;
  }

  function nomeDoNivel(nivel) {
    const ponto = G.el("i", { class: "graf-piramide__ponto" });
    ponto.style.background = nivel.cor;
    return G.el("div", { class: "graf-piramide__nivel" }, [ponto, G.el("span", { texto: nivel.rotulo })]);
  }

  /* Uma linha da grade: o conteúdo de cada pirâmide, com a coluna do meio
     (vazia ou com o nome do nível) entre a primeira e a segunda. */
  function linhaDaGrade(ctx, daPiramide, doMeio) {
    const nos = [];
    ctx.piramides.forEach(function (_piramide, indice) {
      nos.push(daPiramide(indice));
      if (indice === 0) nos.push(doMeio());
    });
    return nos;
  }

  function celulaVazia() {
    return G.el("div", { class: "graf-piramide__vazio" });
  }

  function titulos(ctx) {
    return linhaDaGrade(
      ctx,
      function (indice) {
        return G.el("div", { class: "graf-piramide__titulo", texto: ctx.piramides[indice].titulo });
      },
      celulaVazia,
    );
  }

  function faixasDosNiveis(ctx) {
    return ctx.niveis.reduce(function (nos, nivel, indiceDoNivel) {
      return nos.concat(
        linhaDaGrade(
          ctx,
          function (indice) {
            return faixa(ctx, indice, indiceDoNivel);
          },
          function () {
            return nomeDoNivel(nivel);
          },
        ),
      );
    }, []);
  }

  function proporcoesReais(ctx) {
    return linhaDaGrade(
      ctx,
      function (indice) {
        const real = ctx.piramides[indice].real;
        return G.el("div", { class: "graf-piramide__real" }, [
          G.el("span", { class: "graf-piramide__real-rotulo", texto: ctx.rotulo("real") }),
          " ",
          G.el("b", { texto: textoDosTermos(real.termos, real.normalizada) }),
        ]);
      },
      celulaVazia,
    );
  }

  function rodape(ctx) {
    const referencia = ctx.dados.referencia;
    if (!referencia || !Array.isArray(referencia.termos) || !referencia.termos.length) return null;
    const valores = referencia.termos.map(function (termo) {
      return termo.valor;
    });
    const partes = [ctx.rotulo("referencia"), referencia.nome, textoDosTermos(valores, true)].filter(Boolean);
    return G.el("div", { class: "graf-piramide__referencia" }, [
      G.el("b", { texto: partes.join(" ") }),
      referencia.nota ? " (" + referencia.nota + ")" : "",
    ]);
  }

  function aplicarLargura(raiz) {
    raiz.dataset.faixaLarg = raiz.clientWidth <= LARGURA_ESTREITA ? String(LARGURA_ESTREITA) : "";
  }

  function dadosValidos(dados) {
    return Array.isArray(dados.niveis) && dados.niveis.length > 0 && Array.isArray(dados.piramides) && dados.piramides.length > 0;
  }

  G.registrar("piramide-seguranca", function (host, dados) {
    if (!dadosValidos(dados)) {
      G.mostrarMensagem(host, G.rotulo(dados, "vazio"));
      return null;
    }
    const raiz = G.el("div", { class: "graf-piramide", role: "group", "aria-label": dados.titulo });
    const niveis = prepararNiveis(dados);
    const ctx = {
      dados: dados,
      rotulo: A.rotulador(dados, ROTULOS),
      niveis: niveis,
      piramides: prepararPiramides(dados, niveis, termosDe(dados)),
      dica: G.criarDica(raiz),
    };
    const grade = G.el("div", { class: "graf-piramide__grade" }, titulos(ctx).concat(faixasDosNiveis(ctx), proporcoesReais(ctx)));
    grade.style.gridTemplateColumns = "minmax(0, 1fr) auto" + (ctx.piramides.length > 1 ? " minmax(0, 1fr)" : "");
    [grade, rodape(ctx)].filter(Boolean).forEach(function (no) {
      raiz.appendChild(no);
    });
    host.replaceChildren(raiz);
    aplicarLargura(raiz);
    const parar = G.observarTamanho(raiz, function () {
      aplicarLargura(raiz);
    });
    return {
      destruir: function () {
        parar();
        ctx.dica.esconder();
      },
    };
  });

  G.piramide = { proporcaoReal: proporcaoReal, poligonoDaFaixa: poligonoDaFaixa };
})();
