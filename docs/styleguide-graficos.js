/* ============================================================
   styleguide-graficos.js — Dados de exemplo e demonstrações da página
   docs/styleguide-graficos.html

   A página carrega a biblioteca do próprio app (app/ds/graficos/) e este
   arquivo só faz o que, no app, é papel do servidor: montar o JSON de cada
   gráfico e entregá-lo no atributo data-dados. Os números são fictícios,
   gerados aqui só para mostrar o visual; nada deste arquivo vai para o app.

   Cada elemento [data-exemplo="<nome>"] da página recebe os dados da função
   de mesmo nome em EXEMPLOS; o <pre data-previa="<nome>"> mostra um trecho do
   JSON enviado. Visual novo (ISSUE-015 e 016): uma função em EXEMPLOS e a
   seção na página.

   ?animar=nao na URL desliga a animação de entrada de todos os gráficos.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;
  const DIA_MS = 24 * 60 * 60 * 1000;
  const SEMANA_DO_CORTE = { ano: 2026, semana: 39 };

  if (new URLSearchParams(window.location.search).get("animar") === "nao") G.configurar({ animar: false });

  /* ---------- Semanas de exemplo ---------- */

  /* A segunda-feira da semana 1: a que cai em ou antes de 4 de janeiro. */
  function primeiraSegunda(ano) {
    const quatroDeJaneiro = Date.UTC(ano, 0, 4);
    const diaDaSemana = (new Date(quatroDeJaneiro).getUTCDay() + 6) % 7;
    return quatroDeJaneiro - diaDaSemana * DIA_MS;
  }

  /* Semanas ISO de segunda a domingo, cada uma no mês e no ano da sua
     quinta-feira, que é a regra do calendário da plataforma. No app, quem
     diz a que mês a semana pertence é o servidor. */
  function semanasIso(anoInicial, anoFinal) {
    const semanas = [];
    for (let segunda = primeiraSegunda(anoInicial); ; segunda += 7 * DIA_MS) {
      const quinta = new Date(segunda + 3 * DIA_MS);
      const ano = quinta.getUTCFullYear();
      if (ano > anoFinal) return semanas;
      const diaDoAno = Math.floor((quinta.getTime() - Date.UTC(ano, 0, 1)) / DIA_MS) + 1;
      semanas.push({ ano: ano, mes: quinta.getUTCMonth() + 1, semana: Math.ceil(diaDoAno / 7) });
    }
  }

  function arredondar(valor, casas) {
    const fator = Math.pow(10, casas);
    return Math.round(valor * fator) / fator;
  }

  /* Curva S: logística normalizada para ir de 0 a 100. */
  function logistica(t, forma) {
    return 1 / (1 + Math.exp(-forma.inclinacao * (t - forma.centro)));
  }

  function normalizada(t, forma) {
    const zero = logistica(0, forma);
    return (logistica(t, forma) - zero) / (logistica(1, forma) - zero);
  }

  /* Acumulado em % até a semana `ultimo`; depois dela, nulo (ainda não houve). */
  function acumulado(semanas, forma, ultimo) {
    return semanas.map(function (_semana, i) {
      if (i > ultimo) return null;
      return arredondar(100 * normalizada((i + 1) / semanas.length, forma), 2);
    });
  }

  function incrementos(acumulados) {
    return acumulados.map(function (valor, i) {
      if (valor === null) return null;
      return arredondar(valor - (i === 0 ? 0 : acumulados[i - 1]), 3);
    });
  }

  /* A tendência sai do último realizado e vai até 97%. */
  function tendencia(realizado, corte) {
    const ultimo = realizado.length - 1;
    return realizado.map(function (_valor, i) {
      if (i < corte) return null;
      if (i === corte) return realizado[corte];
      const u = (i - corte) / (ultimo - corte);
      return arredondar(realizado[corte] + (97 - realizado[corte]) * u * u * (3 - 2 * u), 2);
    });
  }

  function curvasDeExemplo() {
    const semanas = semanasIso(2025, 2026);
    const corte = semanas.findIndex(function (semana) {
      return semana.ano === SEMANA_DO_CORTE.ano && semana.semana === SEMANA_DO_CORTE.semana;
    });
    const ultima = semanas.length - 1;
    return {
      semanas: semanas,
      corte: corte,
      linhaBase: acumulado(semanas, { centro: 0.5, inclinacao: 9 }, ultima),
      previsto: acumulado(semanas, { centro: 0.56, inclinacao: 8.5 }, ultima),
      realizado: acumulado(semanas, { centro: 0.62, inclinacao: 8 }, corte),
    };
  }

  /* ---------- Os exemplos de cada visual ---------- */

  function exemploCurvaLinha() {
    const c = curvasDeExemplo();
    const tendenciaDoRealizado = tendencia(c.realizado, c.corte);
    return {
      titulo: "Curva S física, exemplo",
      modo: "acumulado",
      formato: "pct",
      casas: 1,
      series: [
        { id: "linha_base", rotulo: "Linha de Base", papel: "linha-base" },
        { id: "previsto", rotulo: "Previsto", papel: "previsto" },
        { id: "realizado", rotulo: "Realizado", papel: "realizado" },
        { id: "tendencia", rotulo: "Tendência", papel: "tendencia" },
      ],
      periodos: c.semanas.map(function (semana, i) {
        return {
          ano: semana.ano,
          mes: semana.mes,
          semana: semana.semana,
          valores: {
            linha_base: c.linhaBase[i],
            previsto: c.previsto[i],
            realizado: c.realizado[i],
            tendencia: tendenciaDoRealizado[i],
          },
        };
      }),
    };
  }

  function exemploCurvaBarraLinha() {
    const c = curvasDeExemplo();
    const base = incrementos(c.linhaBase);
    const previsto = incrementos(c.previsto);
    const realizado = incrementos(c.realizado);
    return {
      titulo: "Avanço por período e acumulado, exemplo",
      modo: "periodo",
      formato: "pct",
      casas: 1,
      casas_dica: 2,
      series: [
        { id: "linha_base", rotulo: "Linha de Base", papel: "linha-base" },
        { id: "previsto", rotulo: "Previsto", papel: "previsto" },
        { id: "realizado", rotulo: "Realizado", papel: "realizado" },
      ],
      periodos: c.semanas.map(function (semana, i) {
        return {
          ano: semana.ano,
          mes: semana.mes,
          semana: semana.semana,
          valores: { linha_base: base[i], previsto: previsto[i], realizado: realizado[i] },
        };
      }),
    };
  }

  function exemploComparativo() {
    const prazo = [
      { id: "no_prazo", rotulo: "No prazo", papel: "marca", favoravel: "sobe" },
      { id: "ate_6_meses", rotulo: "Atraso até 6 meses", papel: "alerta", favoravel: "desce" },
      { id: "ate_1_ano", rotulo: "Atraso até 1 ano", papel: "atencao", favoravel: "desce" },
      { id: "mais_de_1_ano", rotulo: "Atraso acima de 1 ano", papel: "erro", favoravel: "desce" },
    ];
    const validade = [
      { id: "valido", rotulo: "Válido", papel: "marca", favoravel: "sobe" },
      { id: "invalido", rotulo: "Inválido", papel: "erro", favoravel: "desce" },
    ];
    return {
      titulo: "Linha de base x Atual",
      paineis: [
        {
          titulo: "Status das atividades",
          categorias: prazo,
          linhas: [
            { rotulo: "Linha de base", valores: { no_prazo: 51, ate_6_meses: 37, ate_1_ano: 11, mais_de_1_ano: 21 } },
            { rotulo: "Atual", valores: { no_prazo: 48, ate_6_meses: 40, ate_1_ano: 14, mais_de_1_ano: 18 } },
          ],
        },
        {
          titulo: "Diferença entre o previsto e a projeção",
          categorias: prazo,
          linhas: [
            { rotulo: "Linha de base", valores: { no_prazo: 16, ate_6_meses: 59, ate_1_ano: 20, mais_de_1_ano: 25 } },
            { rotulo: "Atual", valores: { no_prazo: 22, ate_6_meses: 52, ate_1_ano: 17, mais_de_1_ano: 29 } },
          ],
        },
        {
          titulo: "Marcos com data inválida",
          categorias: validade,
          linhas: [
            { rotulo: "Linha de base", valores: { valido: 119, invalido: 1 } },
            { rotulo: "Atual", valores: { valido: 118, invalido: 2 } },
          ],
        },
      ],
    };
  }

  const STATUS_DO_PARETO = [
    { id: "concluido", rotulo: "Concluído", papel: "ok" },
    { id: "andamento", rotulo: "Em andamento", papel: "alerta" },
    { id: "nao_iniciado", rotulo: "Não iniciado", papel: "neutro" },
    { id: "nao_aplicavel", rotulo: "Não aplicável", papel: "bege" },
    { id: "atrasado", rotulo: "Atrasado", papel: "erro" },
    { id: "outros", rotulo: "Outros", papel: "outros" },
  ];

  /* Quantidade por status, na ordem de STATUS_DO_PARETO. */
  const TIPOS_DE_ACAO = [
    ["Mitigação de riscos", [14, 12, 18, 3, 5, 0]],
    ["Inspeção de segurança", [18, 6, 10, 2, 5, 0]],
    ["Ação corretiva", [11, 12, 8, 0, 6, 0]],
    ["Fechamento de não conformidade", [19, 7, 0, 3, 5, 0]],
    ["Monitoramento de riscos", [7, 10, 7, 0, 5, 0]],
    ["Adequação à norma", [9, 8, 5, 0, 5, 0]],
    ["Execução de serviço", [6, 7, 0, 2, 5, 0]],
    ["Tratamento de desvios", [4, 5, 3, 0, 3, 0]],
    ["Validação de engenharia", [5, 3, 2, 0, 1, 1]],
    ["Liberação de pacote de trabalho", [4, 4, 2, 0, 2, 0]],
    ["Atualização de cronograma", [6, 2, 1, 0, 2, 0]],
    ["Comissionamento de equipamento", [3, 2, 2, 0, 2, 0]],
  ];

  function soma(valores) {
    return valores.reduce(function (total, valor) {
      return total + valor;
    }, 0);
  }

  /* As contas das faixas de cima do Pareto. No app é o servidor quem as faz e
     manda o texto pronto em `kpis` e `insight`. */
  function faixasDoPareto(categorias, corte) {
    const totais = categorias.map(function (c) {
      return soma(Object.values(c.valores));
    });
    const geral = soma(totais);
    let acumulado = 0;
    let vitais = 0;
    while (vitais < categorias.length && (acumulado / geral) * 100 < corte) {
      acumulado += totais[vitais];
      vitais += 1;
    }
    const foco = categorias.slice(0, vitais);
    const emAberto = soma(foco.map(function (c) { return c.valores.andamento + c.valores.nao_iniciado; }));
    const atrasadas = soma(foco.map(function (c) { return c.valores.atrasado; }));
    const totalDoFoco = soma(totais.slice(0, vitais));
    const n = categorias.length;
    return {
      kpis: [
        { rotulo: "Total de ações", valor: geral, sub: n + " tipos de ação", papel: "titulo" },
        { rotulo: "Zona vital (" + corte + "%)", valor: vitais + "/" + n, sub: corte + "% das ações", papel: "atencao" },
        { rotulo: "Em aberto", valor: emAberto, sub: Math.round((emAberto / totalDoFoco) * 100) + "% da zona vital", papel: "alerta" },
        { rotulo: "Atrasadas", valor: atrasadas, sub: "na zona vital", papel: "erro" },
      ],
      insight: [
        [vitais + " de " + n + " tipos", "titulo"],
        " (" + Math.round((vitais / n) * 100) + "% das categorias) concentram ",
        [corte + "%", "atencao"],
        " das ações; nesse foco há ",
        [emAberto + " em aberto", "alerta"],
        " e ",
        [atrasadas + " atrasadas", "erro"],
        ".",
      ],
    };
  }

  function exemploPareto() {
    const categorias = TIPOS_DE_ACAO.map(function (tipo) {
      const valores = {};
      STATUS_DO_PARETO.forEach(function (status, i) {
        valores[status.id] = tipo[1][i];
      });
      return { rotulo: tipo[0], valores: valores };
    });
    const faixas = faixasDoPareto(categorias, 80);
    return {
      altura: 560,
      eyebrow: "Análise de Pareto · 80/20",
      titulo: "Tipo de ação × status",
      subtitulo: "Concentração das ações e desdobramento da execução",
      eixo_esquerdo: "Nº de ações",
      eixo_direito: "% acumulado",
      corte: 80,
      status: STATUS_DO_PARETO,
      categorias: categorias,
      kpis: faixas.kpis,
      insight: faixas.insight,
    };
  }

  function exemploRelogios() {
    const limites = { ok: 70, alerta: 60 };
    return {
      relogios: [
        { titulo: "Indicador A", subtitulo: "Exemplo acima do limite de 70", valor: 78.5, meta: 60, limites: limites },
        { titulo: "Indicador B", subtitulo: "Exemplo entre 60 e 70", valor: 64.2, meta: 60, limites: limites },
        { titulo: "Indicador C", subtitulo: "Exemplo abaixo de 60", valor: 41.8, meta: 60, limites: limites },
      ],
    };
  }

  const EXEMPLOS = {
    "curva-s-linha": exemploCurvaLinha,
    "curva-s-barra-linha": exemploCurvaBarraLinha,
    "comparativo-barras": exemploComparativo,
    pareto: exemploPareto,
    relogios: exemploRelogios,
  };

  /* ---------- Entrega dos dados e prévia do JSON ---------- */

  /* Só o começo de cada lista, para o trecho caber na tela. */
  function encurtar(valor) {
    if (Array.isArray(valor)) {
      const inicio = valor.slice(0, 2).map(encurtar);
      return valor.length > 2 ? inicio.concat(["… mais " + (valor.length - 2)]) : inicio;
    }
    if (valor !== null && typeof valor === "object") {
      return Object.fromEntries(
        Object.entries(valor).map(function (par) {
          return [par[0], encurtar(par[1])];
        }),
      );
    }
    return valor;
  }

  document.querySelectorAll("[data-exemplo]").forEach(function (host) {
    const nome = host.dataset.exemplo;
    const dados = EXEMPLOS[nome]();
    host.dataset.dados = JSON.stringify(dados);
    document.querySelectorAll('[data-previa="' + nome + '"]').forEach(function (previa) {
      previa.textContent = JSON.stringify(encurtar(dados), null, 2);
    });
  });

  /* ---------- Conferências das contas ---------- */

  /* Os casos de fronteira das contas da biblioteca. O repositório não tem
     executor de teste de JavaScript, então a página os roda ao abrir: a linha
     que falha fica vermelha e vai para o console. Cada caso é
     [o que se confere, o esperado, a conta]. */
  const CASOS = [
    ["escala(80): passos redondos de 20", "0,20,40,60,80", function () { return G.escala(80).passos.join(","); }],
    ["escala(100,00000000000001): o ruído da soma não empurra o topo para 200", "100", function () { return G.escala(100.00000000000001).max; }],
    ["escalaLivre(100): quatro intervalos de 25", "100: 0,25,50,75,100", function () {
      const eixo = G.escalaLivre(100);
      return eixo.max + ": " + eixo.passos.join(",");
    }],
    ["escalaLivre(100,00000000000001): idem", "100", function () { return G.escalaLivre(100.00000000000001).max; }],
    ["escalaLivre(103): passou de 100, o topo vai a 120 e não a 200", "120", function () { return G.escalaLivre(103).max; }],
    ["escalaLivre(0): sem dado, o eixo vai de 0 a 1", "1", function () { return G.escalaLivre(0).max; }],
    ["soma de [1, nulo, 2] ignora o nulo", "3", function () { return G.periodos.resumir("soma", [1, null, 2]); }],
    ["soma de [nulo, nulo]: sem dado não é zero", "null", function () { return G.periodos.resumir("soma", [null, null]); }],
    ["último de [1, 2, nulo] é o último que existe", "2", function () { return G.periodos.resumir("ultimo", [1, 2, null]); }],
    ["último de uma lista vazia", "null", function () { return G.periodos.resumir("ultimo", []); }],
    ["razão: soma ÷ soma (73,08), e não a média das taxas (82,5)", "73.08", function () {
      const semanas = [{ num: 80, den: 100 }, { num: 20, den: 20 }, { num: 50, den: 100 }, { num: 40, den: 40 }];
      return G.periodos.resumir("razao", semanas).toFixed(2);
    }],
    ["razão com denominador zero", "null", function () { return G.periodos.resumir("razao", [{ num: 0, den: 0 }]); }],
    ["número: -0,04 com uma casa não vira -0,0", "0,0", function () { return G.fmt.numero(-0.04, 1); }],
    ["sinal: zero fica sem sinal e o positivo ganha +", "0,0 / +8,1 / -5,9", function () {
      return [G.fmt.comSinal(0, 1), G.fmt.comSinal(8.14, 1), G.fmt.comSinal(-5.86, 1)].join(" / ");
    }],
    ["mistura de preto e branco a 50%", "rgb(128, 128, 128)", function () { return G.misturar("#000000", "#FFFFFF", 0.5); }],
    ["nome do mês na língua do documento: setembro", "Set", function () { return G.nomeMes(9); }],
  ];

  function conferir(caso) {
    let obtido;
    try {
      obtido = String(caso[2]());
    } catch (erro) {
      obtido = "erro: " + erro.message;
    }
    return { caso: caso[0], esperado: caso[1], obtido: obtido, passou: obtido === caso[1] };
  }

  const tabelaDeConferencias = document.getElementById("sg-conferencias");
  if (tabelaDeConferencias) {
    const resultados = CASOS.map(conferir);
    resultados.forEach(function (resultado) {
      if (!resultado.passou) console.error("[styleguide] conferência falhou: " + resultado.caso + " (esperado " + resultado.esperado + ", obtido " + resultado.obtido + ")");
      tabelaDeConferencias.appendChild(
        G.el("tr", { class: resultado.passou ? "" : "sg-errado" }, [
          G.el("td", { texto: resultado.caso }),
          G.el("td", {}, [G.el("code", { texto: resultado.esperado })]),
          G.el("td", {}, [G.el("code", { texto: resultado.obtido })]),
          G.el("td", { texto: resultado.passou ? "passou" : "FALHOU" }),
        ]),
      );
    });
    const passaram = resultados.filter(function (resultado) {
      return resultado.passou;
    }).length;
    document.getElementById("sg-conferencias-resumo").textContent =
      passaram + " de " + resultados.length + " conferências passaram.";
  }

  /* ---------- Papéis de cor ---------- */

  const tabelaDePapeis = document.getElementById("sg-papeis");
  if (tabelaDePapeis) {
    Object.keys(G.papeis).forEach(function (papel) {
      const amostra = G.el("span", { class: "sg-amostra" });
      amostra.style.background = G.cor(papel);
      tabelaDePapeis.appendChild(
        G.el("tr", {}, [
          G.el("td", {}, [amostra]),
          G.el("td", {}, [G.el("code", { texto: papel })]),
          G.el("td", {}, [G.el("code", { texto: G.papeis[papel] })]),
        ]),
      );
    });
  }

  /* ---------- Agregação por período: soma, último e razão ---------- */

  const demonstracao = document.getElementById("sg-agregacao");
  if (demonstracao) {
    const previsto = [100, 20, 100, 40];
    const realizado = [80, 20, 50, 40];
    const pares = previsto.map(function (valor, i) {
      return { num: realizado[i], den: valor };
    });
    const taxas = pares.map(function (par) {
      return (par.num / par.den) * 100;
    });
    const percentual = function (valor) {
      return G.fmt.percentual(valor, 1);
    };
    const linha = function (celulas, classe, tag) {
      return G.el(
        "tr",
        { class: classe },
        celulas.map(function (celula) {
          return G.el(tag || "td", { texto: celula });
        }),
      );
    };
    const corpo = G.el("tbody", {});
    previsto.forEach(function (valor, i) {
      corpo.appendChild(linha(["Semana " + (i + 1), String(valor), String(realizado[i]), percentual(taxas[i])]));
    });
    const media = soma(taxas) / taxas.length;
    corpo.appendChild(
      linha(
        ["Mês: soma das semanas", String(G.periodos.resumir("soma", previsto)), String(G.periodos.resumir("soma", realizado)), "–"],
        "sg-total",
      ),
    );
    corpo.appendChild(linha(["Mês: média das taxas (errado)", "", "", percentual(media)], "sg-errado"));
    corpo.appendChild(linha(["Mês: soma ÷ soma (certo)", "", "", percentual(G.periodos.resumir("razao", pares))], "sg-certo"));
    const cabecalho = G.el("thead", {}, [linha(["", "Previsto", "Realizado", "Aderência"], "", "th")]);
    demonstracao.appendChild(G.el("table", { class: "sg-tabela sg-tabela--num" }, [cabecalho, corpo]));
  }
})();
