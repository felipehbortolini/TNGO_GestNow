/* ============================================================
   graficos/galeria.js — Galeria

   Porte de "Galeria.html" (docs/referencia/graficos/): um carrossel de
   cartões, um por vez, com o contador no alto, o título e os campos do
   registro no cabeçalho do cartão, o texto que rola quando é longo, as
   setas e os pontos embaixo. A navegação dá a volta: passar do último vai
   ao primeiro. Com um cartão só, a navegação some. Serve as restrições do
   6WLA e o acervo de lições.

   Contrato dos dados (data-dados):
     {
       "titulo": "Restrições do 6WLA",
       "contador": "Restrições",
       "itens": [{
         "titulo": "Projeto Alfa - Liberação de área civil",
         "meta": [{ "rotulo": "Responsável", "valor": "Mariana Costa" }],
         "texto": "Status: Atrasado (12/03/2026). Área civil pendente de laudo."
       }],
       "rotulos": { "semTitulo": "Sem título", "semTexto": "Sem observação",
                    "semValor": "Não informado", "anterior": "Anterior",
                    "proximo": "Próximo", "carrossel": "carrossel",
                    "cartao": "cartão" }
     }
   `meta` é a lista de campos do cabeçalho ("Rótulo: valor", o valor em
   destaque); campo sem valor mostra o texto de `semValor`. `contador` é o
   nome do que se conta ("Restrições: 5"); sem ele, o contador não aparece.
   As setas e as teclas de seta (com o foco na galeria) andam um cartão.

     <div data-grafico="galeria" data-dados='{{ grafico | tojson }}'></div>

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;
  const A = G.apoio;

  const ROTULOS = {
    semTitulo: "Sem título",
    semTexto: "Sem observação",
    semValor: "Não informado",
    anterior: "Anterior",
    proximo: "Próximo",
    carrossel: "carrossel",
    cartao: "cartão",
  };

  /* ---------- Contas ---------- */

  /* O cartão `indice` + `passo`, dando a volta nas pontas. */
  function cartaoVizinho(indice, passo, total) {
    return (indice + passo + total) % total;
  }

  function textoOuPadrao(valor, padrao) {
    const texto = typeof valor === "string" ? valor.trim() : "";
    return texto || padrao;
  }

  /* ---------- Desenho ---------- */

  function campoDoCabecalho(campo, rotulo) {
    return G.el("div", { class: "graf-galeria__campo" }, [
      campo.rotulo + ": ",
      G.el("b", { texto: textoOuPadrao(campo.valor, rotulo("semValor")) }),
    ]);
  }

  function cartao(item, posicao, ctx) {
    const meta = Array.isArray(item.meta) ? item.meta : [];
    const texto = textoOuPadrao(item.texto, "");
    const cabecalho = G.el(
      "div",
      { class: "graf-galeria__cab" },
      [G.el("div", { class: "graf-galeria__titulo", texto: textoOuPadrao(item.titulo, ctx.rotulo("semTitulo")) })].concat(
        meta.map(function (campo) {
          return campoDoCabecalho(campo, ctx.rotulo);
        }),
      ),
    );
    return G.el(
      "div",
      {
        class: "graf-galeria__cartao",
        role: "group",
        "aria-roledescription": ctx.rotulo("cartao"),
        "aria-label": posicao + " / " + ctx.total,
      },
      [
        cabecalho,
        G.el("div", { class: "graf-galeria__corpo" + (texto ? "" : " is-vazio"), texto: texto || ctx.rotulo("semTexto") }),
      ],
    );
  }

  function seta(direcao, rotulo) {
    const pontos = direcao < 0 ? "15 18 9 12 15 6" : "9 6 15 12 9 18";
    return G.el("button", { type: "button", class: "graf-galeria__seta", "aria-label": rotulo }, [
      G.svg("svg", { viewBox: "0 0 24 24", "aria-hidden": "true", focusable: "false" }, [G.svg("polyline", { points: pontos })]),
    ]);
  }

  function navegacao(ctx) {
    const anterior = seta(-1, ctx.rotulo("anterior"));
    const proximo = seta(1, ctx.rotulo("proximo"));
    const pontos = Array.from({ length: ctx.total }, function () {
      return G.el("span", { class: "graf-galeria__ponto" });
    });
    const barra = G.el("div", { class: "graf-galeria__nav" }, [anterior, G.el("div", { class: "graf-galeria__pontos", "aria-hidden": "true" }, pontos), proximo]);
    return { barra: barra, anterior: anterior, proximo: proximo, pontos: pontos };
  }

  /* ---------- Montagem ---------- */

  G.registrar("galeria", function (host, dados) {
    const itens = Array.isArray(dados.itens) ? dados.itens : [];
    if (!itens.length) {
      G.mostrarMensagem(host, G.rotulo(dados, "vazio"));
      return null;
    }
    const ctx = { rotulo: A.rotulador(dados, ROTULOS), total: itens.length };
    const cartoes = itens.map(function (item, i) {
      return cartao(item, i + 1, ctx);
    });
    const trilho = G.el("div", { class: "graf-galeria__trilho" }, cartoes);
    const filhos = [];
    if (dados.contador) filhos.push(G.el("div", { class: "graf-galeria__contador", texto: dados.contador + ": " + ctx.total }));
    filhos.push(G.el("div", { class: "graf-galeria__area" }, [trilho]));
    const nav = ctx.total > 1 ? navegacao(ctx) : null;
    if (nav) filhos.push(nav.barra);
    const raiz = G.el(
      "div",
      { class: "graf-galeria", role: "region", "aria-roledescription": ctx.rotulo("carrossel"), "aria-label": dados.titulo },
      filhos,
    );
    let atual = 0;

    /* Só o cartão à vista entra na ordem do teclado e na leitura. */
    function ir(indice) {
      atual = indice;
      trilho.style.transform = "translateX(-" + atual * 100 + "%)";
      cartoes.forEach(function (no, i) {
        no.toggleAttribute("inert", i !== atual);
        no.setAttribute("aria-hidden", i === atual ? "false" : "true");
      });
      if (nav) {
        nav.pontos.forEach(function (ponto, i) {
          ponto.classList.toggle("is-ativo", i === atual);
        });
      }
    }

    if (nav) {
      nav.anterior.addEventListener("click", function () {
        ir(cartaoVizinho(atual, -1, ctx.total));
      });
      nav.proximo.addEventListener("click", function () {
        ir(cartaoVizinho(atual, 1, ctx.total));
      });
      raiz.addEventListener("keydown", function (evento) {
        if (evento.key !== "ArrowLeft" && evento.key !== "ArrowRight") return;
        evento.preventDefault();
        ir(cartaoVizinho(atual, evento.key === "ArrowLeft" ? -1 : 1, ctx.total));
      });
    }
    host.replaceChildren(raiz);
    ir(0);
    return null;
  });

  G.galeria = { cartaoVizinho: cartaoVizinho };
})();
