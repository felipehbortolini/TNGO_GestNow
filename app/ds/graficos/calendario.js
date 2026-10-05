/* ============================================================
   graficos/calendario.js — HTML Calendário

   Porte de "HTML Calendario.html" (docs/referencia/graficos/): o calendário
   de um mês numa grade fixa de 6 semanas por 7 dias (42 células, sem rolagem
   em nenhum mês), com o mês e as setas no alto, o botão Hoje, o selo de cada
   dia com a contagem de itens e uma barrinha embaixo que divide o dia pelas
   situações. Fim de semana em cinza, o dia de hoje com contorno verde, o
   dia passado com pendência vencida em rosa e os dias dos meses vizinhos
   só com o número. Serve o cronograma de marcos e de auditorias.

   Contrato dos dados (data-dados):
     {
       "titulo": "Calendário de ações",
       "hoje": "2026-02-26",
       "mes": { "ano": 2026, "mes": 2 },
       "situacoes": [{ "id": "no_prazo", "rotulo": "No prazo", "papel": "ok" }],
       "dias": [{ "data": "2026-02-03", "valores": { "no_prazo": 2 } }]
     }
   O servidor manda a quantidade de itens de cada dia por situação; a soma
   (o selo), a divisão da barrinha e a cor do selo saem aqui. O selo pega a
   cor da situação mais grave do dia (erro, atenção, alerta, informação,
   neutro, ok); `papel` no dia troca essa escolha. Um dia antes de `hoje`
   com situação de papel `erro` fica rosa. `mes` é o mês aberto (sem ele, o
   de `hoje`, ou o do primeiro dia com dado); as setas andam de mês em mês e
   Hoje volta ao mês de `hoje`. A data de hoje vem do servidor: a biblioteca
   não lê o relógio.

     <div data-grafico="calendario" data-dados='{{ grafico | tojson }}'></div>

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;
  const A = G.apoio;
  const D = A.datas;

  const ROTULOS = { hoje: "Hoje", anterior: "Mês anterior", proximo: "Próximo mês", total: "Total" };
  const DIAS_DA_SEMANA = 7;
  const CELULAS = 6 * DIAS_DA_SEMANA;
  const MESES_DO_ANO = 12;
  /* Quanto mais alto, mais grave: o selo do dia pega a situação mais grave. */
  const GRAVIDADE_DO_PAPEL = { erro: 5, atencao: 4, alerta: 3, info: 2, neutro: 1, ok: 0 };
  const DOMINGO = 0;
  const SABADO = 6;

  /* ---------- Contas ---------- */

  /* As 42 células do mês: da semana (de domingo) em que ele começa, seis
     semanas seguidas. Cada uma é um dia inteiro (ver apoio.js). */
  function celulasDoMes(ano, mes) {
    const primeiro = D.inicioDoMes(ano, mes);
    const comeco = primeiro - D.partes(primeiro).semana;
    return Array.from({ length: CELULAS }, function (_vazio, i) {
      return comeco + i;
    });
  }

  /* O mês `passo` meses depois (ou antes, se negativo). */
  function mesVizinho(atual, passo) {
    const indice = atual.ano * MESES_DO_ANO + (atual.mes - 1) + passo;
    return { ano: Math.floor(indice / MESES_DO_ANO), mes: (indice % MESES_DO_ANO) + 1 };
  }

  function gravidade(papel) {
    return Object.hasOwn(GRAVIDADE_DO_PAPEL, papel) ? GRAVIDADE_DO_PAPEL[papel] : 0;
  }

  /* O que um dia mostra: o total, as partes com o que há de cada situação e o
     papel do selo (o do dado, ou o da situação mais grave). */
  function resumoDoDia(entrada, situacoes) {
    const partes = situacoes
      .map(function (situacao) {
        const valor = entrada.valores ? entrada.valores[situacao.id] : 0;
        return { situacao: situacao, valor: Number.isFinite(valor) && valor > 0 ? valor : 0 };
      })
      .filter(function (parte) {
        return parte.valor > 0;
      });
    const total = partes.reduce(function (soma, parte) {
      return soma + parte.valor;
    }, 0);
    const maisGrave = partes.reduce(function (pior, parte) {
      return pior === null || gravidade(parte.situacao.papel) > gravidade(pior.situacao.papel) ? parte : pior;
    }, null);
    const papel = entrada.papel || (maisGrave ? maisGrave.situacao.papel : "ok");
    return { total: total, partes: partes, papel: papel };
  }

  function temVencido(resumo) {
    return resumo.partes.some(function (parte) {
      return parte.situacao.papel === "erro";
    });
  }

  /* ---------- Dados ---------- */

  function prepararSituacoes(dados) {
    return (dados.situacoes || []).map(function (situacao, indice) {
      const nome = situacao.cor || situacao.papel;
      return { id: situacao.id, rotulo: situacao.rotulo, papel: situacao.papel, cor: nome ? G.cor(nome) : G.corDaSequencia(indice) };
    });
  }

  function indexarDias(dados) {
    const porDia = new Map();
    (dados.dias || []).forEach(function (entrada) {
      const dia = D.dia(entrada.data);
      if (dia !== null) porDia.set(dia, entrada);
    });
    return porDia;
  }

  /* O mês de abertura: o pedido, senão o de hoje, senão o do primeiro dia
     com dado. */
  function mesDeAbertura(dados, hoje, porDia) {
    if (dados.mes && Number.isInteger(dados.mes.ano) && Number.isInteger(dados.mes.mes)) {
      return { ano: dados.mes.ano, mes: dados.mes.mes };
    }
    const referencia = hoje !== null ? hoje : Math.min(...porDia.keys());
    if (!Number.isFinite(referencia)) return null;
    const partes = D.partes(referencia);
    return { ano: partes.ano, mes: partes.mes };
  }

  /* ---------- Desenho ---------- */

  function conteudoDaDica(ctx, dia, resumo) {
    const linhas = [G.dicaTitulo(D.completa(dia)), G.dicaDivisor()];
    resumo.partes.forEach(function (parte) {
      linhas.push(G.dicaLinha(parte.situacao.cor, parte.situacao.rotulo, [G.fmt.numero(parte.valor, 0)]));
    });
    linhas.push(G.dicaLinha(G.cor("texto-suave"), ctx.rotulo("total"), [G.fmt.numero(resumo.total, 0)]));
    return linhas;
  }

  function barraDoDia(resumo) {
    const segmentos = resumo.partes.map(function (parte) {
      const trecho = G.el("i");
      trecho.style.flex = parte.valor + " 1 0";
      trecho.style.background = parte.situacao.cor;
      return trecho;
    });
    return G.el("div", { class: "graf-calendario__barra" }, segmentos);
  }

  function ehFimDeSemana(dia) {
    const semana = D.partes(dia).semana;
    return semana === DOMINGO || semana === SABADO;
  }

  /* Dia anterior a hoje com alguma situação de erro. */
  function ehVencido(ctx, dia, resumo) {
    return resumo !== null && ctx.hoje !== null && dia < ctx.hoje && temVencido(resumo);
  }

  function classesDoDia(ctx, dia, fora, resumo) {
    const classes = ["graf-calendario__dia"];
    if (fora) classes.push("is-fora");
    else if (ehFimDeSemana(dia)) classes.push("is-fim-de-semana");
    if (dia === ctx.hoje) classes.push("is-hoje");
    if (ehVencido(ctx, dia, resumo)) classes.push("is-vencido");
    return classes.join(" ");
  }

  function textoDoDia(dia, resumo) {
    const partes = resumo.partes.map(function (parte) {
      return parte.situacao.rotulo + " " + G.fmt.numero(parte.valor, 0);
    });
    return D.completa(dia) + ": " + G.fmt.numero(resumo.total, 0) + " (" + partes.join(", ") + ")";
  }

  /* Dia dos meses vizinhos mostra só o número; o do mês, o selo e a barra. */
  function celula(ctx, dia, mesAberto) {
    const partes = D.partes(dia);
    const fora = partes.ano !== mesAberto.ano || partes.mes !== mesAberto.mes;
    const entrada = fora ? null : ctx.porDia.get(dia);
    const resumo = entrada ? resumoDoDia(entrada, ctx.situacoes) : null;
    const comDado = resumo !== null && resumo.total > 0;
    const filhos = [G.el("span", { class: "graf-calendario__numero", texto: String(partes.dia) })];
    if (comDado) {
      filhos.push(G.el("span", { class: "graf-calendario__selo " + A.tom(resumo.papel), texto: G.fmt.numero(resumo.total, 0) }));
      filhos.push(barraDoDia(resumo));
    }
    const no = G.el("div", { class: classesDoDia(ctx, dia, fora, resumo), title: comDado ? textoDoDia(dia, resumo) : null }, filhos);
    if (comDado) {
      no.addEventListener("pointerenter", function (evento) {
        ctx.dica.mostrar(evento, conteudoDaDica(ctx, dia, resumo));
      });
      no.addEventListener("pointermove", ctx.dica.mover);
      no.addEventListener("pointerleave", ctx.dica.esconder);
    }
    return no;
  }

  function cabecalhoDaSemana() {
    return G.el(
      "div",
      { class: "graf-calendario__semana", "aria-hidden": "true" },
      Array.from({ length: DIAS_DA_SEMANA }, function (_vazio, i) {
        return G.el("span", { texto: D.nomeDoDiaDaSemana(i) });
      }),
    );
  }

  function botao(classe, rotulo, texto) {
    return G.el("button", { type: "button", class: classe, "aria-label": rotulo, texto: texto });
  }

  /* A legenda mostra só a amostra de barra, como a barrinha dos dias. */
  function legenda(situacoes) {
    const itens = situacoes.map(function (situacao) {
      return { rotulo: situacao.rotulo, cor: situacao.cor, barra: true };
    });
    const pronta = G.criarLegenda(itens);
    pronta.classList.add("graf-calendario__legenda");
    pronta.querySelectorAll(".graf__leg-linha").forEach(function (amostra) {
      amostra.remove();
    });
    return pronta;
  }

  /* ---------- Montagem ---------- */

  G.registrar("calendario", function (host, dados) {
    const porDia = indexarDias(dados);
    const hoje = D.dia(dados.hoje);
    const abertura = mesDeAbertura(dados, hoje, porDia);
    if (!abertura) {
      G.mostrarMensagem(host, G.rotulo(dados, "vazio"));
      return null;
    }
    const raiz = G.el("div", { class: "graf-calendario", role: "group", "aria-label": dados.titulo });
    const ctx = {
      rotulo: A.rotulador(dados, ROTULOS),
      situacoes: prepararSituacoes(dados),
      porDia: porDia,
      hoje: hoje,
      dica: G.criarDica(raiz),
    };
    const estado = { mes: abertura };
    const nomeDoMes = G.el("span", { class: "graf-calendario__mes", "aria-live": "polite" });
    const grade = G.el("div", { class: "graf-calendario__grade" });
    const anterior = botao("graf-calendario__seta", ctx.rotulo("anterior"), "‹");
    const proximo = botao("graf-calendario__seta", ctx.rotulo("proximo"), "›");
    const botaoHoje = hoje === null ? null : botao("graf-calendario__hoje", ctx.rotulo("hoje"), ctx.rotulo("hoje"));

    function desenhar() {
      const mes = estado.mes;
      nomeDoMes.textContent = D.nomeDoMes(mes.mes) + " " + mes.ano;
      ctx.dica.esconder();
      grade.replaceChildren(
        ...celulasDoMes(mes.ano, mes.mes).map(function (dia) {
          return celula(ctx, dia, mes);
        }),
      );
    }

    function ir(mes) {
      estado.mes = mes;
      desenhar();
    }

    anterior.addEventListener("click", function () {
      ir(mesVizinho(estado.mes, -1));
    });
    proximo.addEventListener("click", function () {
      ir(mesVizinho(estado.mes, 1));
    });
    if (botaoHoje) {
      botaoHoje.addEventListener("click", function () {
        const partes = D.partes(hoje);
        ir({ ano: partes.ano, mes: partes.mes });
      });
    }
    const navegacao = G.el("div", { class: "graf-calendario__nav" }, [anterior, nomeDoMes, proximo, botaoHoje].filter(Boolean));
    [navegacao, cabecalhoDaSemana(), grade].concat(ctx.situacoes.length ? [legenda(ctx.situacoes)] : []).forEach(function (no) {
      raiz.appendChild(no);
    });
    host.replaceChildren(raiz);
    desenhar();
    return {
      destruir: function () {
        ctx.dica.esconder();
      },
    };
  });

  G.calendario = { celulasDoMes: celulasDoMes, mesVizinho: mesVizinho, resumoDoDia: resumoDoDia };
})();
