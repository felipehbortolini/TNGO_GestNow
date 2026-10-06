/* ============================================================
   graficos/rosca.js — Rosca de distribuição

   Visual novo (a coletânea não tem equivalente), no padrão dela: tipografia,
   dica escura, legenda e animação de entrada. Mostra como um total se divide
   em categorias (ocorrências por empresa, por área, composição de um valor):
   o anel, o total no centro e, ao lado, a legenda com o valor e a parte de
   cada fatia. O anel se desenha no sentido horário, uma fatia depois da
   outra; ao passar o ponteiro numa fatia ou na linha da legenda, a fatia se
   destaca e as outras esmaecem.

   Contrato dos dados (data-dados):
     {
       "titulo": "Ocorrências por empresa",
       "rotulo_total": "Ocorrências",
       "formato": { "divisor": 1, "moeda": "BRL", "casas": 0, "compacto": false },
       "maximo_fatias": 5,
       "fatias": [{ "id": "a", "rotulo": "Empresa A", "valor": 42, "papel": "marca" }]
     }
   As fatias saem em ordem decrescente. Passando de `maximo_fatias` (padrão
   5), as menores se juntam numa fatia "Outros" (cinza), regra do protótipo
   para gráfico categórico: as quatro maiores têm cor, o resto é Outros;
   `maximo_fatias: 0` desliga o agrupamento. Sem `papel` (ou `cor`), a cor
   vem da sequência da biblioteca (marca, laranja, roxo, azul). O servidor
   manda os valores; o percentual sai aqui. `formato` é o mesmo da cascata.

     <div data-grafico="rosca" data-dados='{{ grafico | tojson }}'></div>

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;
  const A = G.apoio;

  const ROTULOS = { outros: "Outros", total: "Total" };
  const MAXIMO_PADRAO = 5;
  /* O anel mede 240 por 240 no desenho e se ajusta ao espaço pelo CSS. */
  const LADO = 240;
  const CENTRO = LADO / 2;
  const RAIO = 86;
  const ESPESSURA = 38;
  const AFASTAMENTO_DA_FATIA = 2;
  const DURACAO_DO_ANEL_MS = 1100;
  const CIRCUNFERENCIA = 2 * Math.PI * RAIO;

  /* ---------- Contas ---------- */

  /* As fatias com valor, em ordem decrescente; passando do máximo, as menores
     viram uma só ("Outros"). */
  function agrupar(fatias, maximo, rotuloDeOutros) {
    const validas = fatias
      .filter(function (fatia) {
        return Number.isFinite(fatia.valor) && fatia.valor > 0;
      })
      .sort(function (a, b) {
        return b.valor - a.valor;
      });
    if (!(maximo > 0) || validas.length <= maximo) return validas;
    const mantidas = validas.slice(0, maximo - 1);
    const resto = validas.slice(maximo - 1);
    const soma = resto.reduce(function (total, fatia) {
      return total + fatia.valor;
    }, 0);
    return mantidas.concat([{ id: "outros", rotulo: rotuloDeOutros, valor: soma, papel: "outros", agrupadas: resto.length }]);
  }

  function corDaFatia(fatia, indice) {
    const nome = fatia.cor || fatia.papel;
    return nome ? G.cor(nome) : G.corDaSequencia(indice);
  }

  /* Cada fatia ganha a parte do total, o ponto onde o anel começa e o
     comprimento do arco, em unidades do traço (circunferência). */
  function preparar(fatias, total) {
    let inicio = 0;
    return fatias.map(function (fatia, indice) {
      const parte = fatia.valor / total;
      const pronta = {
        id: fatia.id,
        rotulo: fatia.rotulo,
        valor: fatia.valor,
        parte: parte,
        cor: corDaFatia(fatia, indice),
        inicio: inicio * CIRCUNFERENCIA,
        comprimento: parte * CIRCUNFERENCIA,
      };
      inicio += parte;
      return pronta;
    });
  }

  /* ---------- Desenho ---------- */

  /* O arco de uma fatia é um círculo só com traço: `stroke-dasharray` diz o
     que se vê e `stroke-dashoffset` onde começa. O afastamento abre uma
     fresta entre fatias vizinhas. */
  function circuloDaFatia(fatia, varias) {
    const fresta = varias ? AFASTAMENTO_DA_FATIA : 0;
    const visivel = Math.max(fatia.comprimento - fresta, 0.1);
    const circulo = G.svg("circle", {
      class: "graf-rosca__fatia",
      cx: CENTRO,
      cy: CENTRO,
      r: RAIO,
      fill: "none",
      stroke: fatia.cor,
      "stroke-width": ESPESSURA,
      "stroke-dashoffset": String(-(fatia.inicio + fresta / 2)),
      transform: "rotate(-90 " + CENTRO + " " + CENTRO + ")",
    });
    circulo.dataset.final = visivel.toFixed(2) + " " + (CIRCUNFERENCIA - visivel).toFixed(2);
    circulo.setAttribute("stroke-dasharray", circulo.dataset.final);
    return circulo;
  }

  /* O anel se desenha no sentido horário: cada fatia começa quando a anterior
     termina, no tempo proporcional ao tamanho dela. O traço vai pelo `style`
     porque é ele que o navegador anima. */
  function animarAnel(circulos, fatias) {
    if (!G.podeAnimar(circulos[0])) return;
    circulos.forEach(function (circulo) {
      circulo.style.strokeDasharray = "0 " + CIRCUNFERENCIA;
    });
    /* Força o cálculo de layout: sem isto o navegador junta os dois valores e
       a transição não acontece. */
    circulos[0].getBoundingClientRect();
    circulos.forEach(function (circulo, i) {
      const duracao = fatias[i].parte * DURACAO_DO_ANEL_MS;
      const atraso = (fatias[i].inicio / CIRCUNFERENCIA) * DURACAO_DO_ANEL_MS;
      circulo.style.transition = "stroke-dasharray " + duracao.toFixed(0) + "ms linear " + atraso.toFixed(0) + "ms";
      circulo.style.strokeDasharray = circulo.dataset.final;
    });
  }

  function centro(ctx) {
    const total = G.svg("text", { class: "graf-rosca__total", x: CENTRO, y: CENTRO - 2, "text-anchor": "middle" }, [
      ctx.escrever(ctx.total),
    ]);
    const nome = G.svg("text", { class: "graf-rosca__total-rotulo", x: CENTRO, y: CENTRO + 20, "text-anchor": "middle" }, [
      ctx.dados.rotulo_total || ctx.rotulo("total"),
    ]);
    return [total, nome];
  }

  function conteudoDaDica(ctx, fatia) {
    const linhas = [G.dicaTitulo(fatia.rotulo), G.dicaDivisor()];
    linhas.push(G.dicaLinha(fatia.cor, G.fmt.numero(fatia.parte * 100, 1) + "%", [ctx.formato.completo(fatia.valor)]));
    if (fatia.agrupadas) linhas.push(G.dicaLinha(G.cor("neutro"), ctx.rotulo("outros"), [String(fatia.agrupadas)]));
    return linhas;
  }

  /* ---------- Legenda ---------- */

  function linhaDaLegenda(ctx, fatia) {
    const cor = G.el("i", { class: "graf-rosca__cor" });
    cor.style.background = fatia.cor;
    return G.el("li", { class: "graf-rosca__item", tabindex: 0 }, [
      cor,
      G.el("span", { class: "graf-rosca__nome", texto: fatia.rotulo }),
      G.el("span", { class: "graf-rosca__valor", texto: ctx.escrever(fatia.valor) }),
      G.el("span", { class: "graf-rosca__parte", texto: G.fmt.numero(fatia.parte * 100, 1) + "%" }),
    ]);
  }

  /* ---------- Realce ---------- */

  /* Passar o ponteiro (ou o foco) numa fatia ou na linha dela realça as duas
     e esmaece o resto. */
  function ligarRealce(raiz, circulos, itens) {
    function realcar(indice) {
      raiz.classList.add("tem-realce");
      circulos.forEach(function (circulo, i) {
        circulo.classList.toggle("is-realce", i === indice);
      });
      itens.forEach(function (item, i) {
        item.classList.toggle("is-realce", i === indice);
      });
    }
    function limpar() {
      raiz.classList.remove("tem-realce");
      circulos.concat(itens).forEach(function (no) {
        no.classList.remove("is-realce");
      });
    }
    return { realcar: realcar, limpar: limpar };
  }

  function ligarEventos(ctx, circulos, itens) {
    const realce = ligarRealce(ctx.raiz, circulos, itens);
    circulos.forEach(function (circulo, i) {
      circulo.addEventListener("pointerenter", function (evento) {
        realce.realcar(i);
        ctx.dica.mostrar(evento, conteudoDaDica(ctx, ctx.fatias[i]));
      });
      circulo.addEventListener("pointermove", ctx.dica.mover);
      circulo.addEventListener("pointerleave", function () {
        realce.limpar();
        ctx.dica.esconder();
      });
    });
    itens.forEach(function (item, i) {
      item.addEventListener("pointerenter", function () {
        realce.realcar(i);
      });
      item.addEventListener("focus", function () {
        realce.realcar(i);
      });
      item.addEventListener("pointerleave", realce.limpar);
      item.addEventListener("blur", realce.limpar);
    });
  }

  /* ---------- Montagem ---------- */

  G.registrar("rosca", function (host, dados) {
    const rotulo = A.rotulador(dados, ROTULOS);
    const maximo = Number.isFinite(dados.maximo_fatias) ? dados.maximo_fatias : MAXIMO_PADRAO;
    const agrupadas = agrupar(Array.isArray(dados.fatias) ? dados.fatias : [], maximo, rotulo("outros"));
    if (!agrupadas.length) {
      G.mostrarMensagem(host, G.rotulo(dados, "vazio"));
      return null;
    }
    const total = agrupadas.reduce(function (soma, fatia) {
      return soma + fatia.valor;
    }, 0);
    const formato = A.formatador(dados.formato);
    const raiz = G.el("div", { class: "graf-rosca", role: "group", "aria-label": dados.titulo });
    const ctx = {
      raiz: raiz,
      dados: dados,
      rotulo: rotulo,
      formato: formato,
      total: total,
      fatias: preparar(agrupadas, total),
      dica: G.criarDica(raiz),
      escrever: dados.formato && dados.formato.compacto ? formato.compacto : formato.completo,
    };
    const circulos = ctx.fatias.map(function (fatia) {
      return circuloDaFatia(fatia, ctx.fatias.length > 1);
    });
    const svg = G.svg("svg", { class: "graf-rosca__anel", viewBox: "0 0 " + LADO + " " + LADO, "aria-hidden": "true" }, circulos.concat(centro(ctx)));
    const itens = ctx.fatias.map(function (fatia) {
      return linhaDaLegenda(ctx, fatia);
    });
    [G.el("div", { class: "graf-rosca__quadro" }, [svg]), G.el("ul", { class: "graf-rosca__legenda" }, itens)].forEach(function (no) {
      raiz.appendChild(no);
    });
    host.replaceChildren(raiz);
    ligarEventos(ctx, circulos, itens);
    animarAnel(circulos, ctx.fatias);
    return {
      destruir: function () {
        ctx.dica.esconder();
      },
    };
  });

  G.rosca = { agrupar: agrupar };
})();
