/* ============================================================
   graficos/kpi-status.js — HTML KPI Status

   Porte de "HTML KPI Status.html" (docs/referencia/graficos/): uma faixa de
   cartões, um por estado (Estável, Alerta, Crítico), cada um com a faixa
   colorida do estado, o ícone, a contagem e o percentual do total com a
   barra. Serve a faixa de KPIs com estado dos painéis.

   Contrato dos dados (data-dados):
     {
       "titulo": "Status dos pacotes",
       "itens": [
         { "id": "estavel", "rotulo": "Estável", "valor": 18, "tom": "ok" },
         { "id": "alerta", "rotulo": "Alerta", "valor": 7, "tom": "alerta" },
         { "id": "critico", "rotulo": "Crítico", "valor": 3, "tom": "erro", "icone": "erro" }
       ],
       "total": 28, "casas_pct": 1
     }
   O servidor manda a contagem; o percentual sai aqui (valor dividido pelo
   total, que é a soma quando `total` não vem). `tom` é o das peças
   (pecas.js) e o ícone vem do tom, ou de `icone` ("ok", "alerta", "atencao",
   "erro", "info"): o estado aparece pelo ícone e pelo nome, não só pela cor.
   Item com `href`, ou com `selecionavel: true` (no item ou no topo), é
   clicável e dispara grafico:selecionar com { id, item }.

     <div data-grafico="kpi-status" data-dados='{{ grafico | tojson }}'></div>

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;
  const P = G.pecas;

  /* Os três estados do original têm o desenho dele (grade de 18 x 18, ver
     pecas.js); os outros tons levam o ícone do Design System. */
  const ICONE_DO_ORIGINAL = { ok: "kpiOk", alerta: "kpiAlerta", erro: "kpiErro" };

  function nomeDoIcone(item) {
    if (item.icone !== undefined) return P.nomeDoIcone(item.icone, item.tom);
    return ICONE_DO_ORIGINAL[P.tom(item.tom)] || P.nomeDoIcone(undefined, item.tom);
  }

  function barra(percentual, dados) {
    const preenchimento = G.el("div", { class: "graf-kstatus__preenchimento" });
    preenchimento.style.width = Math.min(percentual, 100) + "%";
    const casas = Number.isInteger(dados.casas_pct) ? dados.casas_pct : 1;
    return G.el("div", { class: "graf-kstatus__linha" }, [
      G.el("div", { class: "graf-kstatus__trilho" }, [preenchimento]),
      G.el("span", { class: "graf-kstatus__pct", title: P.rotulo(dados, "doTotal"), texto: G.fmt.percentual(percentual, casas) }),
    ]);
  }

  function topo(item, dados) {
    const nome = nomeDoIcone(item);
    const icone = nome ? P.icone(nome, 18) : null;
    return G.el("div", { class: "graf-kstatus__topo" }, [
      G.el("span", { class: "graf-kstatus__icone" }, icone ? [icone] : []),
      G.el("div", { class: "graf-kstatus__textos" }, [
        G.el("span", { class: "graf-kstatus__rotulo", texto: item.rotulo }),
        G.el("span", { class: "graf-kstatus__valor", texto: P.textoDoValor(item, dados) }),
      ]),
    ]);
  }

  function cartao(item, contexto) {
    const dados = contexto.dados;
    const raiz = G.el(
      item.href ? "a" : "div",
      {
        class: "graf-kstatus__card " + P.classeDoTom(item.tom),
        href: item.href,
        role: item.href ? null : "group",
        "aria-label": item.rotulo,
      },
      [topo(item, dados), barra(P.percentualDe(item.valor, contexto.total), dados)],
    );
    if (P.ehSelecionavel(item, dados)) {
      P.tornarInterativo(raiz, { host: contexto.host, tipo: "kpi-status", detalhe: { id: item.id, item: item } });
    }
    return raiz;
  }

  G.registrar("kpi-status", function (host, dados) {
    const itens = Array.isArray(dados.itens) ? dados.itens : [];
    if (!itens.length) {
      G.mostrarMensagem(host, G.rotulo(dados, "vazio"));
      return null;
    }
    const contexto = { dados: dados, host: host, total: P.totalDosItens(dados, itens) };
    host.replaceChildren(
      G.el(
        "div",
        { class: "graf-kstatus", role: "group", "aria-label": dados.titulo },
        itens.map(function (item) {
          return cartao(item, contexto);
        }),
      ),
    );
    return null;
  });
})();
