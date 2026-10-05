/* ============================================================
   graficos/cards.js — Motor dos cards de indicador

   O que o Card Indicador Único (card-indicador.js) e o Card Indicador Único
   com detalhes (card-indicador-detalhes.js) têm em comum: o valor grande, o
   selo do estado, a referência de gestão (previsto, meta, linha de base)
   logo abaixo do valor, as linhas de apoio e a faixa colorida do estado. Cada
   visual escolhe o que mostrar; o desenho é o mesmo.

   Contrato dos dados (data-dados), um card por elemento:
     {
       "rotulo": "Aderência da programação",
       "valor": 71.4, "casas": 1, "unidade": "%",
       "tom": "alerta",
       "selo": "Atenção",
       "referencias": [
         { "rotulo": "Previsto", "valor": 78 },
         { "rotulo": "Meta", "valor": 80 },
         { "rotulo": "Linha de base", "valor": 75 }
       ],
       "detalhe": "Média de 52,7 dias em aberto",
       "base": "30 de 42 pacotes",
       "progresso": 71.4,
       "href": "/financeiro/mapa-de-controle"
     }
   - `texto` no lugar de `valor` é o valor já formatado pelo servidor.
   - O estado: `tom` (ok, alerta, atencao, erro, info, neutro, roxo, cinza) ou
     `estado` ("ok", "alerta", "erro"); sem nenhum, sai de `valor`, `meta` e
     `limites` ({ "ok": 80, "alerta": 60 }), a regra dos Relógios.
   - `selo` é um texto, ou { texto, tom, icone }; `false` tira o selo; sem ele
     vale o nome do estado (Dentro da meta, Atenção, Abaixo da meta).
   - Cada referência mostra o próprio valor e a diferença do card para ela,
     com seta e sinal além da cor: `favoravel` é "sobe" (padrão: subir é bom)
     ou "desce". `unidade_delta` (" pp") é a unidade da diferença.
   - `progresso` (0 a 100), ou `max` com o valor, desenha o trilho de baixo.
   - `href` faz do card um link; `selecionavel: true` o faz um botão que dispara
     grafico:selecionar com { id, item } (ver pecas.js).

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;
  const P = G.pecas;

  /* Os estados que têm nome pronto (rotulos.ok, .alerta, .erro). */
  const ESTADOS_COM_NOME = { ok: "ok", alerta: "alerta", erro: "erro" };

  function tomDoCard(dados) {
    if (dados.tom) return P.tom(dados.tom);
    if (dados.estado) return P.tom(dados.estado);
    return P.tom(P.estadoPorLimites(dados.valor, dados.meta, dados.limites));
  }

  /* ---------- Selo ---------- */

  function dadosDoSelo(dados, tomAtual) {
    const selo = dados.selo;
    if (selo === false || selo === null) return null;
    if (selo && typeof selo === "object") return selo;
    if (typeof selo === "string") return { texto: selo };
    const chave = ESTADOS_COM_NOME[tomAtual];
    return chave ? { texto: P.rotulo(dados, chave) } : null;
  }

  function elementoDoSelo(dados, tomAtual, opcoes) {
    const selo = dadosDoSelo(dados, tomAtual);
    if (!selo || !selo.texto) return null;
    const icone = selo.icone === undefined ? opcoes.iconeNoSelo : selo.icone;
    return P.chip(selo.texto, selo.tom || tomAtual, { icone: icone, classe: "graf-card__selo" });
  }

  /* ---------- Referência de gestão ---------- */

  function unidadeDoDelta(ref, dados) {
    if (typeof ref.unidade_delta === "string") return ref.unidade_delta;
    return typeof dados.unidade_delta === "string" ? dados.unidade_delta : "";
  }

  function referencia(ref, dados) {
    const filhos = [
      G.el("span", { class: "graf-ref__rot", texto: ref.rotulo }),
      G.el("b", { class: "graf-ref__val", texto: P.textoDoValor(ref, dados) }),
    ];
    if (Number.isFinite(dados.valor) && Number.isFinite(ref.valor)) {
      filhos.push(
        P.chipDelta(dados.valor - ref.valor, {
          casas: P.casasDe(ref, dados),
          unidade: unidadeDoDelta(ref, dados),
          favoravel: ref.favoravel || dados.favoravel || "sobe",
        }),
      );
    }
    return G.el("span", { class: "graf-ref" }, filhos);
  }

  function referencias(dados) {
    const lista = Array.isArray(dados.referencias) ? dados.referencias : [];
    if (!lista.length) return null;
    return G.el(
      "div",
      { class: "graf-card__refs" },
      lista.map(function (ref) {
        return referencia(ref, dados);
      }),
    );
  }

  /* ---------- Trilho de progresso ---------- */

  function progressoDe(dados) {
    if (Number.isFinite(dados.progresso)) return dados.progresso;
    if (Number.isFinite(dados.max) && dados.max > 0 && Number.isFinite(dados.valor)) return (dados.valor / dados.max) * 100;
    return null;
  }

  function trilho(dados) {
    const percentual = progressoDe(dados);
    if (percentual === null) return null;
    const preenchimento = G.el("div", { class: "graf-card__preenchimento" });
    preenchimento.style.width = Math.min(Math.max(percentual, 0), 100) + "%";
    return G.el("div", { class: "graf-card__trilho" }, [preenchimento]);
  }

  /* ---------- Card ---------- */

  function linhaDeTexto(classe, texto) {
    return texto ? G.el("span", { class: classe, texto: texto }) : null;
  }

  /* `opcoes`: { iconeNoSelo, detalhe, trilho } dizem o que o visual mostra. */
  function montar(host, tipo, dados, opcoes) {
    const tomAtual = tomDoCard(dados);
    const topo = G.el(
      "div",
      { class: "graf-card__topo" },
      [G.el("span", { class: "graf-card__valor", texto: P.textoDoValor(dados) }), elementoDoSelo(dados, tomAtual, opcoes)].filter(Boolean),
    );
    const filhos = [
      linhaDeTexto("graf-card__rotulo", dados.rotulo),
      topo,
      referencias(dados),
      opcoes.detalhe ? linhaDeTexto("graf-card__detalhe", dados.detalhe) : null,
      linhaDeTexto("graf-card__base", dados.base),
      opcoes.trilho ? trilho(dados) : null,
    ].filter(Boolean);
    const raiz = G.el(
      dados.href ? "a" : "div",
      {
        class: "graf-card graf-card--" + tipo + " " + P.classeDoTom(tomAtual),
        href: dados.href,
        role: dados.href ? null : "group",
        "aria-label": dados.rotulo || dados.titulo,
      },
      filhos,
    );
    if (P.ehSelecionavel(dados, dados)) {
      P.tornarInterativo(raiz, { host: host, tipo: tipo, detalhe: { id: dados.id, item: dados } });
    }
    return raiz;
  }

  G.cards = { montar: montar };
})();
