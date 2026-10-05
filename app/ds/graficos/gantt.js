/* ============================================================
   graficos/gantt.js — Gráfico Gantt

   Porte de "Gráfico Gantt.html" (docs/referencia/graficos/): a faixa de
   indicadores no alto, a lista de atividades fixa à esquerda (WBS, nome e
   situação), o calendário por ano e mês à direita com as barras, a linha de
   Hoje, o término da linha de base (losango), o desvio em dias (vermelho se
   atrasa, verde se antecipa), a sombra do que ainda vai acontecer, a borda
   das atividades críticas e a legenda. Ao abrir, o calendário rola até o
   Hoje. Serve o 6WLA e o cronograma de marcos e auditorias.

   Contrato dos dados (data-dados):
     {
       "titulo": "Cronograma de atividades",
       "hoje": "2026-08-05",
       "inicio": "2026-02-01", "fim": "2027-02-13",
       "atividades": [{
         "id": "1.1", "wbs": "1.1", "nome": "Mobilização de canteiro",
         "inicio": "2026-02-02", "fim": "2026-02-27", "base_fim": "2026-03-06",
         "concluida": true, "critica": false, "atrasada": false, "avanco": 100,
         "situacao": { "rotulo": "No prazo", "papel": "ok" }
       }]
     }
   As datas são texto ISO e `hoje` vem do servidor (a biblioteca não lê o
   relógio). Sem `inicio` e `fim`, a janela vai do primeiro dia do mês da
   data mais antiga até a mais tardia mais 15 dias, como no original (um
   Hoje fora dessa janela não aparece). O
   desvio é o término menos o término da linha de base. `atrasada` (a regra
   é do servidor) é o que a faixa de cima conta como "Fora do prazo";
   `situacao` é a pílula da lista. Atividade sem data aparece na lista, sem
   barra. Os rótulos de interface (Hoje, Concluída, Crítica...) vêm em
   `rotulos`.

     <div data-grafico="gantt" data-dados='{{ grafico | tojson }}'></div>

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;
  const A = G.apoio;
  const D = A.datas;

  const ROTULOS = {
    colunaEsquerda: "WBS · Atividade",
    atividades: "Atividades",
    concluidas: "Concluídas",
    criticas: "Críticas",
    foraDoPrazo: "Fora do prazo",
    hoje: "Hoje",
    concluida: "Concluída",
    emExecucao: "Em execução",
    baseline: "Baseline (término)",
    desvioAtraso: "Desvio (atraso)",
    desvioAntecipacao: "Desvio (antecipação)",
    critica: "Crítica",
    inicio: "Início",
    termino: "Término",
    linhaDeBase: "Linha de base",
    desvio: "Desvio",
    avanco: "Avanço",
    situacao: "Situação",
    dia: "d",
  };
  /* Folga depois do último término, como no original. */
  const DIAS_DE_FOLGA = 15;
  const CASAS_DO_PERCENTUAL = 1;
  const ATRASO_ENTRE_BARRAS_MS = 35;
  const ESPERA_ANTES_DE_ROLAR_MS = 350;
  const LARGURA_ESTREITA = 640;

  /* ---------- Dados ---------- */

  function numeroOuNulo(valor) {
    return Number.isFinite(valor) ? valor : null;
  }

  function prepararAtividade(bruta) {
    const inicio = D.dia(bruta.inicio);
    const fim = D.dia(bruta.fim);
    const base = D.dia(bruta.base_fim);
    return {
      wbs: bruta.wbs,
      nome: bruta.nome,
      inicio: inicio,
      fim: fim,
      base: base,
      desvio: fim !== null && base !== null ? fim - base : null,
      concluida: Boolean(bruta.concluida),
      critica: Boolean(bruta.critica),
      atrasada: Boolean(bruta.atrasada),
      avanco: numeroOuNulo(bruta.avanco),
      situacao: bruta.situacao || null,
    };
  }

  function datasDasAtividades(atividades) {
    const datas = [];
    atividades.forEach(function (atividade) {
      [atividade.inicio, atividade.fim, atividade.base].forEach(function (data) {
        if (data !== null) datas.push(data);
      });
    });
    return datas;
  }

  /* O calendário: do primeiro dia do mês da data mais antiga até a mais
     tardia mais 15 dias, com `dias` contando os dois extremos. */
  function janelaDe(dados, atividades) {
    const datas = datasDasAtividades(atividades);
    if (!datas.length) return null;
    const menor = Math.min(...datas);
    const primeiro = D.partes(menor);
    const comeco = D.dia(dados.inicio);
    const termino = D.dia(dados.fim);
    const inicio = comeco === null ? D.inicioDoMes(primeiro.ano, primeiro.mes) : comeco;
    const fim = termino === null ? Math.max(...datas) + DIAS_DE_FOLGA : termino;
    return { inicio: inicio, fim: fim, dias: fim - inicio + 1 };
  }

  /* Cada mês da janela, com a fração dela que ocupa. */
  function mesesDaJanela(janela) {
    const meses = [];
    const primeiro = D.partes(janela.inicio);
    let ano = primeiro.ano;
    let mes = primeiro.mes;
    for (let comeco = D.inicioDoMes(ano, mes); comeco <= janela.fim; comeco = D.inicioDoMes(ano, mes)) {
      const de = Math.max(comeco, janela.inicio);
      const ate = Math.min(comeco + D.diasNoMes(ano, mes) - 1, janela.fim);
      meses.push({ ano: ano, mes: mes, de: de, dias: ate - de + 1 });
      ano = mes === 12 ? ano + 1 : ano;
      mes = mes === 12 ? 1 : mes + 1;
    }
    return meses;
  }

  function anosDosMeses(meses) {
    const anos = [];
    meses.forEach(function (mes) {
      const ultimo = anos[anos.length - 1];
      if (ultimo && ultimo.ano === mes.ano) ultimo.dias += mes.dias;
      else anos.push({ ano: mes.ano, dias: mes.dias });
    });
    return anos;
  }

  /* ---------- Posições ---------- */

  function percentual(valor, dias) {
    return ((valor / dias) * 100).toFixed(3) + "%";
  }

  /* A parte da barra que ainda vai acontecer: só se a barra cruza o Hoje e a
     atividade não terminou. */
  function fracaoDoFuturo(atividade, hoje) {
    if (hoje === null || atividade.concluida || atividade.inicio === null || atividade.fim === null) return null;
    if (hoje < atividade.inicio || hoje >= atividade.fim) return null;
    return (hoje - atividade.inicio) / (atividade.fim - atividade.inicio + 1);
  }

  /* ---------- Faixa de indicadores ---------- */

  function indicador(tom, rotulo, valor, extras) {
    const filhos = [
      G.el("span", { class: "graf-gantt__kpi-rotulo", texto: rotulo }),
      G.el("span", { class: "graf-gantt__kpi-valor" }, [String(valor)].concat(extras.sub ? [G.el("small", { texto: extras.sub })] : [])),
    ];
    if (extras.barra !== undefined) {
      const preenchimento = G.el("i");
      preenchimento.style.width = extras.barra + "%";
      filhos.push(G.el("span", { class: "graf-gantt__kpi-barra" }, [preenchimento]));
    }
    return G.el("div", { class: "graf-gantt__kpi " + A.tom(tom) }, filhos);
  }

  function faixaDeIndicadores(ctx) {
    const todas = ctx.atividades;
    const concluidas = todas.filter(function (atividade) {
      return atividade.concluida;
    }).length;
    const parte = todas.length ? (concluidas / todas.length) * 100 : 0;
    const contar = function (campo) {
      return todas.filter(function (atividade) {
        return atividade[campo];
      }).length;
    };
    return G.el("div", { class: "graf-gantt__kpis" }, [
      indicador("marca", ctx.rotulo("atividades"), todas.length, {}),
      indicador("marca", ctx.rotulo("concluidas"), concluidas, { sub: G.fmt.percentual(parte, CASAS_DO_PERCENTUAL), barra: parte }),
      indicador("erro", ctx.rotulo("criticas"), contar("critica"), {}),
      indicador("alerta", ctx.rotulo("foraDoPrazo"), contar("atrasada"), {}),
    ]);
  }

  /* ---------- Lista da esquerda ---------- */

  function linhaDaLista(atividade, indice) {
    const filhos = [];
    if (atividade.critica) filhos.push(G.el("i", { class: "graf-gantt__marca-critica" }));
    filhos.push(G.el("span", { class: "graf-gantt__wbs", texto: atividade.wbs }));
    filhos.push(G.el("span", { class: "graf-gantt__nome", title: atividade.nome, texto: atividade.nome }));
    if (atividade.situacao) {
      filhos.push(G.el("span", { class: "graf-gantt__situacao " + A.tom(atividade.situacao.papel), texto: atividade.situacao.rotulo }));
    }
    return G.el("div", { class: "graf-gantt__item" + (indice % 2 === 1 ? " is-zebra" : "") }, filhos);
  }

  function colunaEsquerda(ctx) {
    const cabecalho = G.el("div", { class: "graf-gantt__esq-cab", texto: ctx.rotulo("colunaEsquerda") });
    return G.el("div", { class: "graf-gantt__esq" }, [cabecalho].concat(ctx.atividades.map(linhaDaLista)));
  }

  /* ---------- Calendário da direita ---------- */

  function cabecalhoDoCalendario(ctx) {
    const faixa = function (classe, itens, texto) {
      return G.el(
        "div",
        { class: "graf-gantt__faixa" },
        itens.map(function (item) {
          const celula = G.el("div", { class: classe, texto: texto(item) });
          celula.style.width = percentual(item.dias, ctx.janela.dias);
          return celula;
        }),
      );
    };
    return G.el("div", { class: "graf-gantt__dir-cab" }, [
      faixa("graf-gantt__ano", anosDosMeses(ctx.meses), function (item) {
        return String(item.ano);
      }),
      faixa("graf-gantt__mes", ctx.meses, function (item) {
        return String(item.mes);
      }),
    ]);
  }

  function divisasDoCalendario(ctx) {
    const linhas = ctx.meses.map(function (mes) {
      const divisa = G.el("i");
      divisa.style.left = percentual(mes.de - ctx.janela.inicio, ctx.janela.dias);
      return divisa;
    });
    return G.el("div", { class: "graf-gantt__grade" }, linhas);
  }

  function linhaDeHoje(ctx) {
    if (ctx.hoje === null || ctx.hoje < ctx.janela.inicio || ctx.hoje > ctx.janela.fim) return [];
    const esquerda = percentual(ctx.hoje - ctx.janela.inicio, ctx.janela.dias);
    const linha = G.el("div", { class: "graf-gantt__hoje" });
    const selo = G.el("div", { class: "graf-gantt__hoje-selo", texto: ctx.rotulo("hoje") });
    linha.style.left = esquerda;
    selo.style.left = esquerda;
    return [linha, selo];
  }

  function textoDoDesvio(ctx, desvio) {
    return (desvio > 0 ? "+" : "") + desvio + ctx.rotulo("dia");
  }

  function datasDaBarra(ctx, atividade) {
    const fim = G.el("span", { class: "graf-gantt__data-fim", texto: D.curta(atividade.fim) });
    if (atividade.desvio) {
      fim.appendChild(
        G.el("em", { class: "graf-gantt__delta " + (atividade.desvio > 0 ? "is-atraso" : "is-antecipa"), texto: textoDoDesvio(ctx, atividade.desvio) }),
      );
    }
    return [G.el("span", { class: "graf-gantt__data-ini", texto: D.curta(atividade.inicio) }), fim];
  }

  function classesDaBarra(atividade) {
    return "graf-gantt__barra" + (atividade.concluida ? " is-concluida" : "") + (atividade.critica ? " is-critica" : "");
  }

  function barra(ctx, atividade, indice) {
    const filhos = [];
    const futuro = fracaoDoFuturo(atividade, ctx.hoje);
    if (futuro !== null) {
      const sombra = G.el("i", { class: "graf-gantt__futuro" });
      sombra.style.left = (futuro * 100).toFixed(3) + "%";
      filhos.push(sombra);
    }
    const no = G.el("b", { class: classesDaBarra(atividade), role: "img", "aria-label": atividade.nome }, filhos.concat(datasDaBarra(ctx, atividade)));
    no.style.left = percentual(atividade.inicio - ctx.janela.inicio, ctx.janela.dias);
    no.style.width = percentual(atividade.fim - atividade.inicio + 1, ctx.janela.dias);
    no.style.setProperty("--graf-atraso", indice * ATRASO_ENTRE_BARRAS_MS + "ms");
    no.addEventListener("pointerenter", function (evento) {
      ctx.dica.mostrar(evento, conteudoDaDica(ctx, atividade));
    });
    no.addEventListener("pointermove", ctx.dica.mover);
    no.addEventListener("pointerleave", ctx.dica.esconder);
    return no;
  }

  /* Do término da atividade ao da linha de base: o tamanho do desvio. */
  function linhaDeDesvio(ctx, atividade) {
    const de = Math.min(atividade.fim, atividade.base);
    const linha = G.el("i", { class: "graf-gantt__desvio " + (atividade.desvio > 0 ? "is-atraso" : "is-antecipa") });
    linha.style.left = percentual(de - ctx.janela.inicio, ctx.janela.dias);
    linha.style.width = percentual(Math.abs(atividade.desvio), ctx.janela.dias);
    return linha;
  }

  function losangoDaBase(ctx, atividade) {
    const losango = G.el("i", { class: "graf-gantt__base" });
    losango.style.left = percentual(atividade.base - ctx.janela.inicio, ctx.janela.dias);
    return losango;
  }

  function linhaDaBarra(ctx, atividade, indice) {
    const filhos = [];
    if (atividade.base !== null && atividade.fim !== null && atividade.desvio) filhos.push(linhaDeDesvio(ctx, atividade));
    if (atividade.base !== null) filhos.push(losangoDaBase(ctx, atividade));
    if (atividade.inicio !== null && atividade.fim !== null) filhos.push(barra(ctx, atividade, indice));
    return G.el("div", { class: "graf-gantt__linha" + (indice % 2 === 1 ? " is-zebra" : "") }, filhos);
  }

  function colunaDireita(ctx) {
    const filhos = [cabecalhoDoCalendario(ctx), divisasDoCalendario(ctx)]
      .concat(linhaDeHoje(ctx))
      .concat(
        ctx.atividades.map(function (atividade, indice) {
          return linhaDaBarra(ctx, atividade, indice);
        }),
      );
    return G.el("div", { class: "graf-gantt__dir" }, filhos);
  }

  /* ---------- Dica ---------- */

  function par(rotulo, valor) {
    return G.el("div", { class: "graf__tip-linha" }, [
      G.el("span", { class: "graf__tip-rot", texto: rotulo }),
      G.el("strong", { class: "graf__tip-val", texto: valor }),
    ]);
  }

  function conteudoDaDica(ctx, atividade) {
    const titulo = (atividade.wbs ? atividade.wbs + " · " : "") + atividade.nome;
    const linhas = [G.dicaTitulo(titulo), G.dicaDivisor()];
    linhas.push(par(ctx.rotulo("inicio"), D.completa(atividade.inicio)));
    linhas.push(par(ctx.rotulo("termino"), D.completa(atividade.fim)));
    if (atividade.base !== null) linhas.push(par(ctx.rotulo("linhaDeBase"), D.completa(atividade.base)));
    if (atividade.desvio) linhas.push(par(ctx.rotulo("desvio"), textoDoDesvio(ctx, atividade.desvio)));
    if (atividade.avanco !== null) linhas.push(par(ctx.rotulo("avanco"), G.fmt.percentual(atividade.avanco, CASAS_DO_PERCENTUAL)));
    if (atividade.situacao) linhas.push(par(ctx.rotulo("situacao"), atividade.situacao.rotulo));
    return linhas;
  }

  /* ---------- Legenda ---------- */

  const ITENS_DA_LEGENDA = [
    ["is-concluida", "concluida"],
    ["is-execucao", "emExecucao"],
    ["is-base", "baseline"],
    ["is-atraso", "desvioAtraso"],
    ["is-antecipa", "desvioAntecipacao"],
    ["is-hoje", "hoje"],
    ["is-critica", "critica"],
  ];

  function legenda(ctx) {
    return G.el(
      "div",
      { class: "graf-gantt__legenda" },
      ITENS_DA_LEGENDA.map(function (item) {
        return G.el("span", { class: "graf-gantt__leg-item" }, [G.el("i", { class: "graf-gantt__amostra " + item[0] }), ctx.rotulo(item[1])]);
      }),
    );
  }

  /* ---------- Rolagem até o Hoje ---------- */

  function rolarAteHoje(rolagem) {
    const linhaDeHoje = rolagem.querySelector(".graf-gantt__hoje");
    if (!linhaDeHoje) return;
    const area = rolagem.getBoundingClientRect();
    const linha = linhaDeHoje.getBoundingClientRect();
    const esquerda = rolagem.querySelector(".graf-gantt__esq").offsetWidth;
    rolagem.scrollTo({
      left: rolagem.scrollLeft + (linha.left - area.left) - (area.width + esquerda) / 2,
      behavior: G.podeAnimar(rolagem) ? "smooth" : "auto",
    });
  }

  function aplicarLargura(raiz) {
    raiz.dataset.faixaLarg = raiz.clientWidth <= LARGURA_ESTREITA ? String(LARGURA_ESTREITA) : "";
  }

  /* ---------- Montagem ---------- */

  G.registrar("gantt", function (host, dados) {
    const atividades = (Array.isArray(dados.atividades) ? dados.atividades : []).map(prepararAtividade);
    const hoje = D.dia(dados.hoje);
    const janela = janelaDe(dados, atividades);
    if (!janela) {
      G.mostrarMensagem(host, G.rotulo(dados, "vazio"));
      return null;
    }
    const raiz = G.el("div", { class: "graf-gantt", role: "group", "aria-label": dados.titulo });
    const quadro = G.el("div", { class: "graf-gantt__quadro" });
    const ctx = {
      rotulo: A.rotulador(dados, ROTULOS),
      atividades: atividades,
      hoje: hoje,
      janela: janela,
      meses: mesesDaJanela(janela),
      dica: G.criarDica(quadro),
    };
    const corpo = G.el("div", { class: "graf-gantt__corpo" }, [colunaEsquerda(ctx), colunaDireita(ctx)]);
    const rolagem = G.el("div", { class: "graf-gantt__rolagem" }, [corpo]);
    quadro.insertBefore(rolagem, quadro.firstChild);
    [faixaDeIndicadores(ctx), quadro, legenda(ctx)].forEach(function (no) {
      raiz.appendChild(no);
    });
    host.replaceChildren(raiz);
    aplicarLargura(raiz);
    const parar = G.observarTamanho(raiz, function () {
      aplicarLargura(raiz);
    });
    const espera = window.setTimeout(function () {
      rolarAteHoje(rolagem);
    }, ESPERA_ANTES_DE_ROLAR_MS);
    return {
      destruir: function () {
        window.clearTimeout(espera);
        parar();
        ctx.dica.esconder();
      },
    };
  });

  G.gantt = { janelaDe: janelaDe, mesesDaJanela: mesesDaJanela, fracaoDoFuturo: fracaoDoFuturo, prepararAtividade: prepararAtividade };
})();
