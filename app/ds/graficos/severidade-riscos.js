/* ============================================================
   graficos/severidade-riscos.js — Separação Severidade Riscos

   Porte de "Separação Severidade Riscos.html" (docs/referencia/graficos/): um
   cartão por faixa de severidade, lado a lado, cada um com o nome da faixa, a
   quantidade e o percentual do total (6 | 13%). O último cartão, em cinza, é o
   que ainda não foi avaliado. Serve a separação dos riscos por severidade.

   Contrato dos dados (data-dados):
     {
       "titulo": "Severidade dos riscos",
       "itens": [
         { "id": "critico", "rotulo": "Crítico", "valor": 6, "tom": "erro" },
         { "id": "alto", "rotulo": "Alto", "valor": 11, "tom": "atencao" },
         { "id": "moderado", "rotulo": "Moderado", "valor": 18, "tom": "alerta" },
         { "id": "baixo", "rotulo": "Baixo", "valor": 9, "tom": "ok" },
         { "id": "sem_avaliacao", "rotulo": "Sem avaliação", "valor": 3, "tom": "cinza" }
       ],
       "total": 47, "casas_pct": 0
     }
   As faixas e os tons vêm da escala de riscos ativa dos parâmetros (Timenow de
   quatro faixas ou a de três), nunca daqui; o percentual sai do valor dividido
   pelo total, que é a soma quando `total` não vem. O nome da faixa, em letras
   maiúsculas, é o sinal além da cor, como no original; `icone` no item (um
   nome de ícone das peças) acrescenta um ícone ao lado do nome. O original
   pintava o cartão cheio, com texto branco; aqui o fundo é suave, com a faixa
   forte em cima e o texto escuro, porque só o vermelho e o roxo do Design
   System passam de 4,5:1 com texto branco (DECISÃO da ISSUE-015).
   Item com `href`, ou `selecionavel: true` (no item ou no topo), filtra o
   registro: dispara grafico:selecionar com { id, item }.

     <div data-grafico="severidade-riscos" data-dados='{{ grafico | tojson }}'></div>

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;
  const P = G.pecas;

  function rotuloDoCartao(item) {
    const nome = typeof item.icone === "string" ? P.nomeDoIcone(item.icone, item.tom) : null;
    const icone = nome ? P.icone(nome, 14) : null;
    return G.el("span", { class: "graf-sev__rotulo" }, [icone, item.rotulo].filter(Boolean));
  }

  function numerosDoCartao(item, percentual, dados) {
    const casas = Number.isInteger(dados.casas_pct) ? dados.casas_pct : 0;
    return G.el("span", { class: "graf-sev__numeros" }, [
      G.el("span", { class: "graf-sev__valor", texto: P.textoDoValor(item, dados) }),
      G.el("span", { class: "graf-sev__sep", "aria-hidden": "true", texto: "|" }),
      G.el("span", { class: "graf-sev__pct", title: P.rotulo(dados, "doTotal"), texto: G.fmt.percentual(percentual, casas) }),
    ]);
  }

  function cartao(item, contexto) {
    const dados = contexto.dados;
    const raiz = G.el(
      item.href ? "a" : "div",
      {
        class: "graf-sev__card " + P.classeDoTom(item.tom),
        href: item.href,
        role: item.href ? null : "group",
        "aria-label": item.rotulo,
      },
      [rotuloDoCartao(item), numerosDoCartao(item, P.percentualDe(item.valor, contexto.total), dados), G.el("span", { class: "graf-sev__brilho", "aria-hidden": "true" })],
    );
    if (P.ehSelecionavel(item, dados)) {
      P.tornarInterativo(raiz, { host: contexto.host, tipo: "severidade-riscos", detalhe: { id: item.id, item: item } });
    }
    return raiz;
  }

  G.registrar("severidade-riscos", function (host, dados) {
    const itens = Array.isArray(dados.itens) ? dados.itens : [];
    if (!itens.length) {
      G.mostrarMensagem(host, G.rotulo(dados, "vazio"));
      return null;
    }
    const contexto = { dados: dados, host: host, total: P.totalDosItens(dados, itens) };
    host.replaceChildren(
      G.el(
        "div",
        { class: "graf-sev", role: "group", "aria-label": dados.titulo },
        itens.map(function (item) {
          return cartao(item, contexto);
        }),
      ),
    );
    return null;
  });
})();
