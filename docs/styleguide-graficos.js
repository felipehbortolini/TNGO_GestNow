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

  /* ============================================================
     Exemplos da ISSUE-015: cards, faixa de KPI, severidade, mapas de calor,
     matrizes, Mapa 52 semanas, quantitativos e etapas. Tudo fictício e gerado
     aqui; no app, as faixas, os limites e os estados chegam do servidor.
     ============================================================ */

  /* ---------- Datas e calendário ---------- */

  function msDeIso(iso) {
    const partes = iso.split("-").map(Number);
    return Date.UTC(partes[0], partes[1] - 1, partes[2]);
  }

  function isoDeMs(ms) {
    return new Date(ms).toISOString().slice(0, 10);
  }

  function somarDias(iso, dias) {
    return isoDeMs(msDeIso(iso) + dias * DIA_MS);
  }

  function dataBr(iso) {
    const partes = iso.split("-");
    return partes[2] + "/" + partes[1] + "/" + partes[0];
  }

  function diaMes(iso) {
    return iso.slice(8, 10) + "/" + iso.slice(5, 7);
  }

  /* A semana ISO de uma data: a do ano da quinta-feira dela. */
  function semanaIsoDe(iso) {
    const instante = msDeIso(iso);
    const diaDaSemana = (new Date(instante).getUTCDay() + 6) % 7;
    const quinta = instante + (3 - diaDaSemana) * DIA_MS;
    const ano = new Date(quinta).getUTCFullYear();
    const diaDoAno = Math.floor((quinta - Date.UTC(ano, 0, 1)) / DIA_MS) + 1;
    return { ano: ano, semana: Math.ceil(diaDoAno / 7) };
  }

  /* As semanas de um ano, de segunda a domingo, cada uma no mês da sua
     quinta-feira: o calendário que, no app, o servidor entrega. */
  function calendarioDoAno(ano) {
    const semanas = [];
    for (let segunda = primeiraSegunda(ano); ; segunda += 7 * DIA_MS) {
      const quinta = new Date(segunda + 3 * DIA_MS);
      if (quinta.getUTCFullYear() !== ano) return semanas;
      semanas.push({
        semana: semanas.length + 1,
        mes: quinta.getUTCMonth() + 1,
        inicio: isoDeMs(segunda),
        fim: isoDeMs(segunda + 6 * DIA_MS),
      });
    }
  }

  /* Hoje, fixo, para o exemplo sair igual em toda abertura. */
  const HOJE = { ano: 2026, semana: 41, inicio: "2026-10-05" };

  /* ---------- Cards, faixa de KPI e severidade ---------- */

  const CARDS = {
    ok: {
      id: "avanco",
      rotulo: "Avanço físico acumulado",
      valor: 62.8,
      casas: 1,
      unidade: "%",
      meta: 60,
      limites: { ok: 60, alerta: 50 },
      referencias: [
        { rotulo: "Previsto", valor: 61.5 },
        { rotulo: "Meta", valor: 60 },
        { rotulo: "Linha de base", valor: 58 },
      ],
      unidade_delta: " pp",
      detalhe: "Média de 1,6 pp por semana no último mês",
      base: "Corte na semana 41",
      progresso: 62.8,
      selecionavel: true,
    },
    alerta: {
      id: "aderencia",
      rotulo: "Aderência da programação",
      valor: 71.4,
      casas: 1,
      unidade: "%",
      meta: 80,
      limites: { ok: 80, alerta: 60 },
      referencias: [
        { rotulo: "Previsto", valor: 78 },
        { rotulo: "Meta", valor: 80 },
        { rotulo: "Linha de base", valor: 75 },
      ],
      unidade_delta: " pp",
      detalhe: "12 pacotes abaixo do plano da semana",
      base: "30 de 42 pacotes",
      progresso: 71.4,
      selecionavel: true,
    },
    erro: {
      id: "conformidade",
      rotulo: "Conformidade das medições",
      valor: 54,
      casas: 1,
      unidade: "%",
      meta: 80,
      limites: { ok: 80, alerta: 60 },
      referencias: [
        { rotulo: "Previsto", valor: 72 },
        { rotulo: "Meta", valor: 80 },
        { rotulo: "Linha de base", valor: 70 },
      ],
      unidade_delta: " pp",
      detalhe: "23 medições com pendência",
      base: "27 de 50 medições",
      progresso: 54,
      selecionavel: true,
    },
    prazo: {
      id: "prazo-resposta",
      rotulo: "Prazo médio de resposta",
      valor: 6.2,
      casas: 1,
      unidade: " dias",
      tom: "alerta",
      favoravel: "desce",
      referencias: [
        { rotulo: "Previsto", valor: 5 },
        { rotulo: "Meta", valor: 5 },
        { rotulo: "Linha de base", valor: 7 },
      ],
      unidade_delta: " dias",
      detalhe: "Maior prazo: 14 dias",
      base: "18 solicitações",
      selecionavel: true,
    },
  };

  function exemploKpiStatus() {
    return {
      titulo: "Status dos pacotes",
      itens: [
        { id: "estavel", rotulo: "Estável", valor: 18, tom: "ok" },
        { id: "alerta", rotulo: "Alerta", valor: 7, tom: "alerta" },
        { id: "critico", rotulo: "Crítico", valor: 3, tom: "erro" },
      ],
      total: 28,
      casas_pct: 1,
      selecionavel: true,
    };
  }

  function exemploSeveridade() {
    return {
      titulo: "Severidade dos riscos",
      itens: [
        { id: "critico", rotulo: "Crítico", valor: 6, tom: "erro" },
        { id: "alto", rotulo: "Alto", valor: 11, tom: "atencao" },
        { id: "moderado", rotulo: "Moderado", valor: 18, tom: "alerta" },
        { id: "baixo", rotulo: "Baixo", valor: 9, tom: "ok" },
        { id: "sem_avaliacao", rotulo: "Sem avaliação", valor: 3, tom: "cinza" },
      ],
      total: 47,
      casas_pct: 0,
      selecionavel: true,
    };
  }

  /* ---------- Tabela Heatmap ---------- */

  /* Os números são os do original (Tabela Heatmap.html), para a conferência
     lado a lado. As faixas são do servidor: cada uma leva tom (família do
     Design System), nível de intensidade, ícone e nome, de modo que a cor não
     é o único sinal. */
  const COLUNAS_DO_HEATMAP = [
    "Escopo Pendente",
    "Aprovação Técnica",
    "Sem Restrição",
    "HOLD",
    "Aguard. Proposta",
    "Sem SSE",
    "Em Desenvolvimento",
    "Rec. Propostas",
    "Entend. Técnico",
  ];

  const LINHAS_DO_HEATMAP = [
    ["Alfa", [3, 7, 12, 0, 2, 15, 0, 5, 1]],
    ["Beta", [14, 0, 6, 20, 0, 3, 30, 0, 4]],
    ["Gama", [0, 2, 9, 1, 5, 0, 11, 24, 0]],
  ];

  function exemploHeatmap() {
    return {
      titulo: "Distribuição por área e restrição",
      rotulo_linhas: "Área",
      casas: 0,
      colunas: COLUNAS_DO_HEATMAP.map(function (rotulo, i) {
        return { id: "c" + (i + 1), rotulo: rotulo };
      }),
      linhas: LINHAS_DO_HEATMAP.map(function (linha) {
        const valores = {};
        linha[1].forEach(function (valor, i) {
          valores["c" + (i + 1)] = valor;
        });
        return { id: linha[0].toLowerCase(), rotulo: linha[0], valores: valores };
      }),
      total: { linha: "Total geral", coluna: "Total" },
      faixas: {
        padrao: [
          { ate: 0, tom: "cinza", vazia: true, rotulo: "Nenhuma" },
          { ate: 3, tom: "neutro", nivel: 1, icone: "ponto", rotulo: "1 a 3" },
          { ate: 9, tom: "ok", nivel: 2, icone: "ok", rotulo: "4 a 9" },
          { ate: 19, tom: "alerta", nivel: 2, icone: "alerta", rotulo: "10 a 19" },
          { ate: 29, tom: "atencao", nivel: 2, icone: "atencao", rotulo: "20 a 29" },
          { tom: "erro", nivel: 3, icone: "erro", rotulo: "30 ou mais" },
        ],
        total: [
          { ate: 49, tom: "ok", nivel: 2, icone: "ok" },
          { ate: 99, tom: "alerta", nivel: 2, icone: "alerta" },
          { tom: "erro", nivel: 3, icone: "erro" },
        ],
      },
      selecionavel: true,
    };
  }

  /* O mapa de controle: valores em R$ mil sem pintar e o desvio da projeção
     sobre o orçado, pintado pelas faixas do prototipo (limites 1, 5 e 10). O
     total do desvio não é soma: é a conta sobre os totais. */
  const PACOTES_DO_MAPA = [
    ["Terraplenagem", 1250, 1342],
    ["Fundações", 3480, 3706],
    ["Estrutura metálica", 5210, 5221],
    ["Montagem eletromecânica", 4120, 3897],
    ["Elétrica e instrumentação", 2760, 2698],
    ["Comissionamento", 980, 1109],
  ];

  function desvioPct(orcado, projecao) {
    return arredondar(((projecao - orcado) / orcado) * 100, 1);
  }

  function exemploHeatmapDesvio() {
    const orcado = soma(PACOTES_DO_MAPA.map(function (p) { return p[1]; }));
    const projecao = soma(PACOTES_DO_MAPA.map(function (p) { return p[2]; }));
    return {
      titulo: "Desvio da projeção sobre o orçado atual",
      rotulo_linhas: "Pacote",
      cabecalho: "horizontal",
      casas: 1,
      unidade: "%",
      sinal: true,
      colunas: [
        { id: "orcado", rotulo: "Orçado atual (R$ mil)", calor: false, casas: 0, unidade: "", sinal: false },
        { id: "projecao", rotulo: "Projeção (R$ mil)", calor: false, casas: 0, unidade: "", sinal: false },
        { id: "desvio", rotulo: "Desvio", somar: false, total: desvioPct(orcado, projecao) },
      ],
      linhas: PACOTES_DO_MAPA.map(function (p) {
        return {
          id: p[0],
          rotulo: p[0],
          valores: { orcado: p[1], projecao: p[2], desvio: desvioPct(p[1], p[2]) },
        };
      }),
      total: { linha: "Total geral", coluna: false },
      faixas: [
        { maior_que: 10, tom: "erro", nivel: 3, icone: "sobe", rotulo: "Sobrecusto acima de 10%" },
        { maior_que: 5, tom: "erro", nivel: 2, icone: "sobe", rotulo: "Sobrecusto de 5% a 10%" },
        { de: 1, tom: "erro", nivel: 1, icone: "sobe", rotulo: "Sobrecusto de 1% a 5%" },
        { maior_que: -1, menor_que: 1, tom: "neutro", nivel: 1, icone: "igual", rotulo: "Desvio abaixo de 1%" },
        { menor_que: -10, tom: "ok", nivel: 3, icone: "desce", rotulo: "Economia acima de 10%" },
        { menor_que: -5, tom: "ok", nivel: 2, icone: "desce", rotulo: "Economia de 5% a 10%" },
        { ate: -1, tom: "ok", nivel: 1, icone: "desce", rotulo: "Economia de 1% a 5%" },
      ],
      selecionavel: true,
    };
  }

  /* ---------- Matriz Formatada ---------- */

  /* As semanas de um mês como o original as conta: de segunda a sexta, da
     semana do dia 1 à do último dia. */
  function semanasDoMes(ano, mes) {
    const primeira = Date.UTC(ano, mes - 1, 1);
    const ultima = Date.UTC(ano, mes, 0);
    const segundaDe = function (ms) {
      return ms - ((new Date(ms).getUTCDay() + 6) % 7) * DIA_MS;
    };
    const semanas = [];
    for (let segunda = segundaDe(primeira); segunda <= segundaDe(ultima); segunda += 7 * DIA_MS) {
      semanas.push({ inicio: isoDeMs(segunda), fim: isoDeMs(segunda + 4 * DIA_MS) });
    }
    return semanas;
  }

  const MESES_DA_MATRIZ = [
    { ano: 2026, mes: 9, rotulo: "SET/26", de: "01/09", ate: "30/09" },
    { ano: 2026, mes: 10, rotulo: "OUT/26", de: "01/10", ate: "31/10" },
  ];

  /* Horas por semana de cada projeto: uma base e uma variação fixa. */
  const COLABORADORES = [
    ["Ana Beatriz Rocha", [["PJ-0001 · Ampliação da talha de içamento", 1900], ["PJ-0002 · Retrofit do forno de calcinação", 1700]], 1200],
    ["Carlos Andrade", [["PJ-0003 · Automação da esteira portuária", 2300], ["PJ-0004 · Novo silo de armazenagem", 2150]], 900],
    ["Fernanda Lima", [["PJ-0005 · Reposição de bombas de recalque", 1500], ["PJ-0006 · Modernização do alimentador", 1650]], 1500],
  ];

  function horasDaSemana(base, indicePessoa, indiceProjeto, indiceMes, indiceSemana) {
    const variacao = ((indiceMes * 13 + indiceSemana * 7 + indicePessoa * 5 + indiceProjeto * 3) % 9) - 4;
    return base + variacao * 100;
  }

  function exemploMatrizHoras() {
    const colunas = MESES_DA_MATRIZ.map(function (m) {
      return {
        id: "m" + m.mes,
        rotulo: m.rotulo,
        faixas: "mes",
        resumo: { rotulo: "Mês", sub: m.de + " a " + m.ate },
        filhas: semanasDoMes(m.ano, m.mes).map(function (semana, i) {
          return {
            id: "m" + m.mes + "s" + (i + 1),
            rotulo: "S" + (i + 1),
            sub: diaMes(semana.inicio) + " a " + diaMes(semana.fim),
            faixas: "semana",
          };
        }),
      };
    });
    const linhas = COLABORADORES.map(function (pessoa, p) {
      return {
        id: "col-" + p,
        rotulo: pessoa[0],
        selo: pessoa[1].length + " proj",
        fixas: { indiretas: pessoa[2] },
        filhos: pessoa[1].map(function (projeto, j) {
          const valores = {};
          let total = 0;
          colunas.forEach(function (coluna, m) {
            coluna.filhas.forEach(function (filha, s) {
              const horas = horasDaSemana(projeto[1], p, j, m, s);
              valores[filha.id] = horas;
              total += horas;
            });
          });
          return { id: "proj-" + p + "-" + j, rotulo: projeto[0], sem_faixa: true, valores: valores, fixas: { horas: total } };
        }),
      };
    });
    return {
      titulo: "Horas por semana",
      subtitulo: "Colaborador e projeto",
      variante: "pilulas",
      rotulo_linhas: "Colaborador / Projeto",
      casas: 0,
      unidade: "",
      zero_como_vazio: true,
      colunas_fixas: [
        { id: "horas", rotulo: "Horas em projeto", tom: "ok" },
        { id: "indiretas", rotulo: "Horas indiretas", tom: "neutro" },
      ],
      colunas: colunas,
      coluna_total: { titulo: "Total", rotulo: "Geral", sub: "período", faixas: "total" },
      linhas: linhas,
      rodape: { rotulo: "Total geral" },
      faixas: {
        semana: [
          { menor_que: 3200, tom: "atencao", nivel: 1, icone: "desce", rotulo: "Semana abaixo do esperado" },
          { maior_que: 4800, tom: "roxo", nivel: 1, icone: "sobe", rotulo: "Semana acima do esperado" },
          { tom: "cinza", nivel: 1, icone: false, rotulo: "Semana dentro do esperado" },
        ],
        mes: [
          { menor_que: 17000, tom: "erro", nivel: 1, icone: "desce", rotulo: "Mês abaixo da referência" },
          { maior_que: 21000, tom: "ok", nivel: 1, icone: "sobe", rotulo: "Mês acima da referência" },
          { tom: "cinza", nivel: 1, icone: false, rotulo: "Mês na referência" },
        ],
        total: [{ tom: "ok", nivel: 1, icone: false }],
      },
      expandir: 1,
      altura: 520,
    };
  }

  /* A matriz P x I 5 x 5: a cor é da posição (probabilidade x impacto), então
     a célula manda o id da faixa. Escala de 4 faixas do prototipo: baixo a
     partir de 1, moderado de 5, alto de 10 e crítico de 15. */
  const NIVEIS_DA_MATRIZ = ["Muito baixo", "Baixo", "Médio", "Alto", "Muito alto"];
  const PROBABILIDADES = ["Muito baixa", "Baixa", "Média", "Alta", "Muito alta"];

  function faixaDoScore(score) {
    if (score >= 15) return "critico";
    if (score >= 10) return "alto";
    if (score >= 5) return "moderado";
    return "baixo";
  }

  /* `contagem[p - 1][i - 1]` é a quantidade de riscos na probabilidade p e no
     impacto i. */
  function matrizPxI(subtitulo, contagem, faixas) {
    const linhas = [];
    for (let p = 5; p >= 1; p -= 1) {
      const valores = {};
      for (let i = 1; i <= 5; i += 1) {
        valores["i" + i] = {
          valor: contagem[p - 1][i - 1],
          faixa: faixaDoScore(p * i),
          apoio: p + " x " + i + " = " + p * i,
          id: "p" + p + "|i" + i,
        };
      }
      linhas.push({ id: "p" + p, rotulo: p + " · " + PROBABILIDADES[p - 1], valores: valores });
    }
    return {
      titulo: "Matriz P x I residual",
      subtitulo: subtitulo,
      variante: "grade",
      rotulo_linhas: "Probabilidade x Impacto",
      casas: 0,
      colunas: NIVEIS_DA_MATRIZ.map(function (nome, i) {
        return { id: "i" + (i + 1), rotulo: String(i + 1), sub: nome };
      }),
      linhas: linhas,
      faixas: faixas,
      selecionavel: true,
    };
  }

  function exemploMatrizAmeacas() {
    return matrizPxI(
      "Ameaças",
      [[0, 1, 0, 0, 0], [1, 0, 1, 0, 0], [0, 1, 2, 1, 0], [0, 1, 0, 2, 0], [0, 0, 1, 0, 1]],
      [
        { id: "baixo", tom: "ok", nivel: 2, icone: "ok", rotulo: "Baixo" },
        { id: "moderado", tom: "alerta", nivel: 2, icone: "alerta", rotulo: "Moderado" },
        { id: "alto", tom: "atencao", nivel: 2, icone: "atencao", rotulo: "Alto" },
        { id: "critico", tom: "erro", nivel: 3, icone: "erro", rotulo: "Crítico" },
      ],
    );
  }

  /* Nas oportunidades a escala se inverte: quanto maior, melhor, e as
     famílias são as frias e o verde. */
  function exemploMatrizOportunidades() {
    return matrizPxI(
      "Oportunidades",
      [[0, 0, 1, 0, 0], [1, 0, 0, 0, 1], [0, 1, 0, 1, 0], [0, 0, 1, 0, 0], [0, 0, 0, 0, 0]],
      [
        { id: "baixo", tom: "neutro", nivel: 2, icone: "ponto", rotulo: "Baixo" },
        { id: "moderado", tom: "info", nivel: 2, icone: "info", rotulo: "Moderado" },
        { id: "alto", tom: "roxo", nivel: 2, icone: "sobe", rotulo: "Alto" },
        { id: "critico", tom: "ok", nivel: 3, icone: "ok", rotulo: "Crítico" },
      ],
    );
  }

  /* ---------- Mapa 52 semanas ---------- */

  const PACOTES_DO_MAS = [
    { id: "A", nome: "Estrutura metálica", inicio: "2026-06-01" },
    { id: "B", nome: "Subestação principal", inicio: "2026-07-13" },
    { id: "C", nome: "Sistema de ventilação", inicio: "2026-08-17" },
  ];

  const MARCOS_DO_MAS = [
    "Requisição",
    "RFx",
    "Propostas",
    "Equalização técnica",
    "Equalização comercial",
    "Adjudicação",
    "Pedido",
    "Documentos",
    "Fabricação",
    "Inspeção",
    "Embarque",
    "Entrega",
  ];

  const SITUACOES_DO_MAS = [
    { id: "concluido", rotulo: "Concluído", rotulo_total: "Concluídos", tom: "ok" },
    { id: "em_dia", rotulo: "Em dia", rotulo_total: "Em dia", tom: "info" },
    { id: "atencao", rotulo: "Em atenção", rotulo_total: "Em atenção", tom: "alerta" },
    { id: "atrasado", rotulo: "Atrasado", rotulo_total: "Atrasados", tom: "erro" },
  ];

  /* A situação de um marco: o que já passou concluiu, salvo alguns atrasados;
     o da semana de hoje pede atenção. No app, é regra do servidor. */
  function situacaoDoMarco(data, indicePacote, indiceMarco) {
    if (data < HOJE.inicio) return (indiceMarco * 3 + indicePacote) % 7 === 5 ? "atrasado" : "concluido";
    return data < somarDias(HOJE.inicio, 7) ? "atencao" : "em_dia";
  }

  function itensDoMas() {
    const itens = [];
    PACOTES_DO_MAS.forEach(function (pacote, p) {
      MARCOS_DO_MAS.forEach(function (marco, m) {
        const data = somarDias(pacote.inicio, m * 16);
        const semana = semanaIsoDe(data);
        const situacao = SITUACOES_DO_MAS.find(function (s) { return s.id === situacaoDoMarco(data, p, m); });
        const chips = (m + p) % 5 === 0 ? [{ texto: "Replano", tom: "alerta", depois_da_data: true }] : [];
        itens.push({
          id: "mas-" + pacote.id + "-" + (m + 1),
          ano: semana.ano,
          semana: semana.semana,
          titulo: pacote.nome,
          subtitulo: "Marco " + (m + 1) + " · " + marco,
          etiqueta: { texto: "Pacote " + pacote.id, tom: "info" },
          estado: situacao.id,
          chips: chips,
          data: data,
          atributos: { pacote: pacote.id, marco: marco },
          detalhe: {
            titulo: pacote.nome,
            subtitulo: "Marco " + (m + 1) + " · " + marco,
            chips: [{ texto: situacao.rotulo, tom: situacao.tom, icone: true }],
            blocos: [
              {
                tipo: "campos",
                titulo: "Resumo",
                itens: [
                  { rotulo: "Pacote", valor: "Pacote " + pacote.id },
                  { rotulo: "Marco", valor: marco },
                  { rotulo: "Data prevista", valor: dataBr(data) },
                  { rotulo: "Semana", valor: "S" + semana.semana + " de " + semana.ano },
                  { rotulo: "Situação", valor: situacao.rotulo, tom: situacao.tom },
                ],
              },
            ],
          },
        });
      });
    });
    /* Itens sem semana contam em "Sem data" e não ganham coluna. */
    itens.push({ id: "mas-D-1", titulo: "Painéis de comando", subtitulo: "Marco 1 · Requisição", etiqueta: { texto: "Pacote D", tom: "info" }, estado: "em_dia", atributos: { pacote: "D", marco: "Requisição" } });
    return itens;
  }

  function exemploMapa52() {
    return {
      titulo: "Marcos do MAS",
      subtitulo: "Pacote x Marco",
      ano: HOJE.ano,
      hoje: { ano: HOJE.ano, semana: HOJE.semana },
      por_pagina: 6,
      anos: [2026, 2027].map(function (ano) {
        return { ano: ano, semanas: calendarioDoAno(ano) };
      }),
      legenda: SITUACOES_DO_MAS,
      filtros: [
        {
          id: "pacote",
          rotulo: "Pacote",
          opcoes: ["A", "B", "C", "D"].map(function (id) { return { id: id, rotulo: "Pacote " + id }; }),
        },
        {
          id: "marco",
          rotulo: "Marco",
          opcoes: MARCOS_DO_MAS.map(function (nome) { return { id: nome, rotulo: nome }; }),
        },
      ],
      itens: itensDoMas(),
    };
  }

  /* ---------- Tabela Quantitativos por entregável ---------- */

  const MESES_DO_PLANO = [
    { mes: 9, rotulo: "Setembro" },
    { mes: 10, rotulo: "Outubro" },
  ];

  const ENTREGAVEIS = [
    ["Fundações", "Pacote A", ["Bloco 1", "Bloco 2", "Bloco 3"]],
    ["Estrutura metálica", "Pacote B", ["Colunas", "Vigas", "Contraventos", "Cobertura"]],
    ["Tubulação", "Pacote C", ["Linha de processo", "Linha de utilidades"]],
    ["Elétrica e instrumentação", "Pacote D", ["Painéis", "Cabos", "Instrumentos"]],
    ["Comissionamento", "Pacote E", ["Pré-operação", "Partida"]],
  ];

  /* Itens planejados por semana: de 0 a 11, fixo por posição. */
  function itensDaSemana(entregavel, filho, semana) {
    return Math.max(0, ((entregavel * 5 + filho * 3 + semana * 7) % 14) - 2);
  }

  function exemploQuantitativos() {
    const calendario = calendarioDoAno(2026);
    const grupos = MESES_DO_PLANO.map(function (m) {
      return {
        id: "mes-" + m.mes,
        rotulo: m.rotulo,
        colunas: calendario
          .filter(function (semana) {
            return semana.mes === m.mes && semana.semana >= 36 && semana.semana <= 44;
          })
          .map(function (semana) {
            return { id: "s" + semana.semana, rotulo: "S" + semana.semana, dica: diaMes(semana.inicio) + " a " + diaMes(semana.fim) };
          }),
      };
    });
    const colunas = grupos.flatMap(function (grupo) { return grupo.colunas; });
    const linhas = ENTREGAVEIS.map(function (entregavel, e) {
      const filhos = entregavel[2].map(function (nome, f) {
        const valores = {};
        colunas.forEach(function (coluna) {
          valores[coluna.id] = itensDaSemana(e, f, Number(coluna.id.slice(1)));
        });
        const planejado = soma(Object.values(valores));
        return {
          id: "ent-" + e + "-" + f,
          rotulo: nome,
          valores: valores,
          metricas: { pendentes: (e + f) % 4 },
          detalhe: {
            titulo: nome,
            subtitulo: entregavel[0] + " · " + entregavel[1],
            blocos: [
              {
                tipo: "campos",
                titulo: "Resumo",
                itens: [
                  { rotulo: "Entregável", valor: entregavel[0] },
                  { rotulo: "Itens planejados", valor: String(planejado) },
                ],
              },
              {
                tipo: "tabela",
                titulo: "Itens por semana",
                colunas: ["Semana", { rotulo: "Itens", alinhar: "centro" }],
                linhas: colunas.map(function (coluna) {
                  return { celulas: [coluna.rotulo, String(valores[coluna.id])] };
                }),
              },
            ],
          },
        };
      });
      return {
        id: "ent-" + e,
        rotulo: entregavel[0],
        subtitulo: entregavel[1],
        metricas: { pendentes: soma(filhos.map(function (filho) { return filho.metricas.pendentes; })) },
        filhos: filhos,
      };
    });
    return {
      titulo: "Plano de quantidades por semana",
      rotulo_linhas: "Entregável",
      casas: 0,
      unidade: "",
      grupos: grupos,
      coluna_total: { rotulo: "Total" },
      metricas: [{ id: "pendentes", rotulo: "Pendentes", somar: true }],
      linhas: linhas,
      total: { rotulo: "Total geral", rotulo_raiz: "Entregáveis" },
      faixas: {
        padrao: [
          { ate: 0, tom: "cinza", vazia: true, rotulo: "Sem itens" },
          { ate: 4, tom: "neutro", nivel: 1, icone: "ponto", rotulo: "1 a 4 itens" },
          { ate: 9, tom: "info", nivel: 2, icone: "info", rotulo: "5 a 9 itens" },
          { tom: "roxo", nivel: 3, icone: "sobe", rotulo: "10 itens ou mais" },
        ],
        total: [{ tom: "neutro", nivel: 1, icone: false }],
      },
      selecionavel: true,
      altura: 420,
    };
  }

  /* ---------- Etapas ---------- */

  const ETAPAS_DA_COMPRA = [
    { id: "req", rotulo: "Requisição" },
    { id: "rfx", rotulo: "RFx emitida" },
    { id: "prop", rotulo: "Propostas" },
    { id: "eqt", rotulo: "Equalização técnica" },
    { id: "eqc", rotulo: "Equalização comercial" },
    { id: "neg", rotulo: "Negociação" },
    { id: "adj", rotulo: "Adjudicação" },
  ];

  const ESTADOS_DAS_ETAPAS = [
    { id: "concluido", rotulo: "Concluído", tom: "ok" },
    { id: "andamento", rotulo: "Em andamento", tom: "alerta" },
    { id: "nao_iniciado", rotulo: "Não iniciado", tom: "atencao" },
    { id: "na", rotulo: "N/A", tom: "cinza", padrao: true },
  ];

  /* Cada processo, com a quantidade de etapas já concluídas. */
  const PROCESSOS_DE_COMPRA = [
    ["PC-0012", "Painéis elétricos de média tensão", "Equipamento", 7],
    ["PC-0013", "Transformador de potência", "Equipamento", 5],
    ["PC-0014", "Montagem de tubulação", "Serviço", 4],
    ["PC-0015", "Cabos de controle", "Material", 3],
    ["PC-0016", "Válvulas de controle", "Equipamento", 2],
    ["PC-0017", "Sistema de ventilação", "Equipamento", 1],
    ["PC-0018", "Andaimes e acesso", "Serviço", 0],
    ["PC-0019", "Eletrodutos e conexões", "Material", 6],
  ];

  function processoDeCompra(processo, indice) {
    const concluidas = processo[3];
    const inicio = somarDias("2026-06-01", indice * 9);
    const etapas = {};
    ETAPAS_DA_COMPRA.forEach(function (etapa, s) {
      if (indice === 3 && etapa.id === "neg") return;
      const data = somarDias(inicio, s * 12);
      if (s < concluidas) {
        etapas[etapa.id] = { estado: "concluido", data: data, quantidade: etapa.id === "prop" ? 3 : undefined };
      } else if (s === concluidas && concluidas > 0) {
        etapas[etapa.id] = { estado: "andamento", data: data, previsto: true };
      } else {
        etapas[etapa.id] = { estado: "nao_iniciado", data: data, previsto: true };
      }
    });
    const prevista = somarDias(inicio, ETAPAS_DA_COMPRA.length * 12);
    const estadoGeral = concluidas === ETAPAS_DA_COMPRA.length ? "concluido" : concluidas === 0 ? "nao_iniciado" : "andamento";
    const nomeDoEstado = ESTADOS_DAS_ETAPAS.find(function (estado) { return estado.id === estadoGeral; });
    return {
      id: processo[0],
      titulo: processo[0] + " · " + processo[1],
      tags: [processo[2]],
      estado: estadoGeral,
      etapas: etapas,
      datas: [prevista, somarDias(prevista, -5)],
      detalhe: {
        titulo: processo[0],
        subtitulo: processo[1],
        chips: [{ texto: nomeDoEstado.rotulo, tom: nomeDoEstado.tom, icone: true }],
        blocos: [
          {
            tipo: "campos",
            titulo: "Resumo",
            itens: [
              { rotulo: "Tipo", valor: processo[2] },
              { rotulo: "Etapas concluídas", valor: concluidas + " de " + ETAPAS_DA_COMPRA.length },
              { rotulo: "Conclusão prevista", valor: dataBr(prevista) },
            ],
          },
          {
            tipo: "tabela",
            titulo: "Etapas",
            colunas: ["Etapa", "Estado", { rotulo: "Data", alinhar: "centro" }],
            linhas: ETAPAS_DA_COMPRA.filter(function (etapa) { return etapas[etapa.id]; }).map(function (etapa) {
              const atual = etapas[etapa.id];
              const estado = ESTADOS_DAS_ETAPAS.find(function (e) { return e.id === atual.estado; });
              return { celulas: [etapa.rotulo, { texto: estado.rotulo, tom: estado.tom }, dataBr(atual.data)] };
            }),
          },
        ],
      },
    };
  }

  function exemploEtapas() {
    return {
      titulo: "Processo de compra",
      rotulo_linhas: "Processo",
      etapas: ETAPAS_DA_COMPRA,
      estados: ESTADOS_DAS_ETAPAS,
      colunas_datas: ["Prevista", "Linha de base"],
      linhas: PROCESSOS_DE_COMPRA.map(processoDeCompra),
    };
  }

  const EXEMPLOS = {
    "curva-s-linha": exemploCurvaLinha,
    "curva-s-barra-linha": exemploCurvaBarraLinha,
    "comparativo-barras": exemploComparativo,
    pareto: exemploPareto,
    relogios: exemploRelogios,
    "card-indicador-ok": function () { return CARDS.ok; },
    "card-indicador-alerta": function () { return CARDS.alerta; },
    "card-indicador-erro": function () { return CARDS.erro; },
    "card-detalhes-ok": function () { return CARDS.ok; },
    "card-detalhes-alerta": function () { return CARDS.alerta; },
    "card-detalhes-erro": function () { return CARDS.erro; },
    "card-detalhes-prazo": function () { return CARDS.prazo; },
    "kpi-status": exemploKpiStatus,
    "severidade-riscos": exemploSeveridade,
    "tabela-heatmap": exemploHeatmap,
    "tabela-heatmap-desvio": exemploHeatmapDesvio,
    "matriz-formatada": exemploMatrizHoras,
    "matriz-ameacas": exemploMatrizAmeacas,
    "matriz-oportunidades": exemploMatrizOportunidades,
    "mapa-52-semanas": exemploMapa52,
    "tabela-quantitativos": exemploQuantitativos,
    etapas: exemploEtapas,
  };

  /* ---------- Exemplos da ISSUE-016 ---------- */

  /* Soma `dias` a uma data ISO (AAAA-MM-DD): o servidor é quem manda as datas
     assim. */
  function somarDias(iso, dias) {
    const partes = iso.split("-").map(Number);
    return new Date(Date.UTC(partes[0], partes[1] - 1, partes[2] + dias)).toISOString().slice(0, 10);
  }

  /* Uma lista de linhas em colunas nomeadas: o exemplo fica em tabela e o JSON
     que o gráfico recebe, em objetos. */
  function emObjetos(nomes, linhas) {
    return linhas.map(function (linha) {
      const objeto = {};
      nomes.forEach(function (nome, i) {
        objeto[nome] = linha[i];
      });
      return objeto;
    });
  }

  /* As 14 atividades do original (cronograma 2026 e 2027): WBS, nome, início,
     término, término da linha de base, concluída, crítica, fora do prazo,
     avanço (%) e situação. */
  const ATIVIDADES_DO_GANTT = [
    ["1.1", "Mobilização de canteiro", "2026-02-02", "2026-02-27", "2026-03-06", true, false, false, 100, ["No prazo", "ok"]],
    ["1.2", "Levantamento topográfico e geotécnico", "2026-02-16", "2026-03-27", null, true, false, false, 100, ["No prazo", "ok"]],
    ["1.3", "Licenciamento ambiental", "2026-02-23", "2026-05-08", "2026-04-24", false, false, false, 78, ["Alerta", "alerta"]],
    ["1.4", "Estudos de viabilidade técnica", "2026-03-02", "2026-04-17", "2026-04-17", true, false, false, 100, ["No prazo", "ok"]],
    ["2.1", "Fundação e estruturas de concreto", "2026-03-09", "2026-07-30", "2026-06-30", false, true, true, 82, ["Atrasado", "erro"]],
    ["2.2", "Estruturas metálicas da planta", "2026-04-20", "2026-09-21", "2026-08-31", false, true, true, 46, ["Atrasado", "erro"]],
    ["2.3", "Coberturas e fechamentos", "2026-05-25", "2026-10-14", "2026-09-30", false, false, false, 18, ["Alerta", "alerta"]],
    ["3.1", "Montagem eletromecânica", "2026-06-01", "2026-11-30", "2026-11-15", false, true, false, 12, ["Alerta", "alerta"]],
    ["3.2", "Tubulações industriais", "2026-06-15", "2026-12-15", "2026-12-22", false, false, false, 6, ["No prazo", "ok"]],
    ["4.1", "Sala de controle e automação", "2026-08-03", "2026-12-18", null, false, false, false, 5, ["No prazo", "ok"]],
    ["4.2", "Comissionamento da unidade", "2026-10-05", "2027-01-08", "2026-12-22", false, true, false, 0, ["Alerta", "alerta"]],
    ["5.1", "Testes e partida operacional", "2026-11-09", "2026-12-30", null, false, false, false, 0, ["Em dia", "ok"]],
    ["5.2", "Treinamento e documentação as-built", "2026-11-30", "2027-01-29", "2027-01-29", false, false, false, 0, ["No prazo", "ok"]],
    ["6.1", "Suporte pós-entrega", "2027-01-04", "2027-01-29", null, false, false, false, 0, ["No prazo", "ok"]],
  ];

  function exemploGantt() {
    const atividades = emObjetos(
      ["wbs", "nome", "inicio", "fim", "base_fim", "concluida", "critica", "atrasada", "avanco", "situacao"],
      ATIVIDADES_DO_GANTT,
    ).map(function (atividade) {
      return Object.assign({ id: atividade.wbs }, atividade, { situacao: { rotulo: atividade.situacao[0], papel: atividade.situacao[1] } });
    });
    return { titulo: "Cronograma de atividades, exemplo", hoje: "2026-08-05", atividades: atividades };
  }

  function exemploCalendario() {
    return {
      titulo: "Calendário de ações, exemplo",
      hoje: "2026-02-26",
      mes: { ano: 2026, mes: 2 },
      situacoes: [
        { id: "no_prazo", rotulo: "No prazo", papel: "ok" },
        { id: "atencao", rotulo: "Atenção", papel: "alerta" },
        { id: "atrasada", rotulo: "Atrasada", papel: "erro" },
      ],
      dias: [
        { data: "2026-02-03", valores: { no_prazo: 2 } },
        { data: "2026-02-05", valores: { atencao: 1 } },
        { data: "2026-02-09", valores: { no_prazo: 2, atencao: 1 } },
        { data: "2026-02-11", valores: { atrasada: 1 } },
        { data: "2026-02-17", valores: { atencao: 2 } },
        { data: "2026-02-20", valores: { no_prazo: 1 } },
        { data: "2026-02-25", valores: { atrasada: 1 } },
        { data: "2026-02-26", valores: { no_prazo: 1 } },
        { data: "2026-02-27", valores: { no_prazo: 2 } },
      ],
    };
  }

  function exemploGaleria() {
    const restricoes = [
      ["Projeto Alfa - Liberação de área civil", "Mariana Costa", "Status: Atrasado (12/03/2026). Área civil pendente de laudo geotécnico. Avanço 45%. Valor em risco R$ 1.240.000,00. Aguardando ART do responsável técnico."],
      ["Projeto Beta - Fornecimento de válvulas", "Ricardo Alves", "Status: Em alerta (28/02/2026). Fornecedor com atraso de 15 dias na entrega. Avanço 70%. Impacto estimado R$ 380.500,00 no cronograma de montagem."],
      ["Projeto Gama - Ensaio hidrostático", "Fernanda Lima", "Status: Em dia (05/04/2026). Ensaio agendado após conclusão da soldagem. Avanço 88%. Sem restrições financeiras. Valor do pacote R$ 520.000,00."],
      ["Projeto Delta - Comissionamento elétrico", "Carlos Menezes", "Status: Backlog (prev. 20/05/2026). Aguardando energização da subestação. Avanço 10%. Depende de liberação da concessionária. Valor R$ 2.100.000,00."],
      ["Projeto Alfa - Montagem de tubulação", "", "Status: Concluído (18/01/2026). Pacote finalizado dentro do prazo. Avanço 100%. Valor realizado R$ 640.000,00. Sem restrições remanescentes."],
    ];
    return {
      titulo: "Restrições do 6WLA, exemplo",
      contador: "Restrições",
      rotulos: { semValor: "Não atribuído" },
      itens: restricoes.map(function (restricao) {
        return { titulo: restricao[0], meta: [{ rotulo: "Responsável", valor: restricao[1] }], texto: restricao[2] };
      }),
    };
  }

  function exemploFormularioCards() {
    const categorias = { A: "alerta", B: "atencao", C: "ok", D: "erro" };
    const situacoes = {
      andamento: { rotulo: "Em andamento", papel: "alerta" },
      atrasado: { rotulo: "Atrasado", papel: "atencao" },
      nao_iniciado: { rotulo: "Não iniciado", papel: "info" },
    };
    const sim = { rotulo: "Sim", papel: "ok" };
    const nao = { rotulo: "Não", papel: "erro" };
    const registros = [
      ["PRJ-001", "B", "andamento", "Carlos Lima", "2026-09-12", nao, "Inspeção de integridade dos dutos da unidade de ácido, com emissão de relatório dos reparos identificados."],
      ["PRJ-002", "A", "atrasado", "Ana Souza", "2026-07-30", sim, "Revisão do laudo GCMS dos tanques T-301 e T-302 para liberação da operação."],
      ["PRJ-003", "C", "andamento", "Mariana Costa", "2026-10-18", nao, "Manutenção preventiva das bombas P-204 A/B, incluindo troca de selos mecânicos e alinhamento."],
      ["PRJ-004", "D", "nao_iniciado", "Roberto Neves", "2026-11-15", nao, "Comissionamento da subestação SE-2 e testes de energização do painel elétrico principal."],
    ];
    return {
      titulo: "Registros de formulários, exemplo",
      itens: registros.map(function (r) {
        return {
          id: r[0],
          titulo: r[0],
          subtitulo: "Categoria " + r[1],
          situacao: situacoes[r[2]],
          faixa: { rotulo: "Subcategoria", valor: "Categoria " + r[1], papel: categorias[r[1]] },
          campos: [
            { rotulo: "Responsável", valor: r[3] },
            { rotulo: "Status", situacao: situacoes[r[2]] },
            { rotulo: "Data de término", data: r[4] },
            { rotulo: "Área", situacao: r[5] },
          ],
          secoes: [{ rotulo: "Descrição", texto: r[6] }],
        };
      }),
    };
  }

  /* Seis meses de 2025 e os doze de 2026 do original (jan/26 68,4 a dez/26
     94,6): com dois anos, os botões de ano aparecem. */
  const NOTAS_DAS_AREAS = {
    2025: [61.5, 63.8, 62.4, 65.9, 66.7, 67.2],
    2026: [68.4, 71.2, 69.8, 73.5, 76.1, 79.9, 82.4, 85.7, 88.2, 90.3, 92.8, 94.6],
  };

  function exemploAreas() {
    const pontos = [];
    Object.keys(NOTAS_DAS_AREAS).forEach(function (ano) {
      const notas = NOTAS_DAS_AREAS[ano];
      notas.forEach(function (valor, i) {
        pontos.push({ ano: Number(ano), mes: 12 - notas.length + i + 1, valor: valor });
      });
    });
    return {
      titulo: "Desempenho da contratada, exemplo",
      unidade: "%",
      casas: 1,
      meta: 90,
      zonas: [
        { de: 0, rotulo: "Não aceitável", papel: "erro" },
        { de: 70, rotulo: "Insuficiente", papel: "alerta" },
        { de: 81, rotulo: "Bom", papel: "marca" },
        { de: 90, rotulo: "Muito bom", papel: "ok" },
      ],
      pontos: pontos,
    };
  }

  /* As nove linhas do original: colaborador, cargo, portfólio, tipo de rateio,
     horas em projeto e horas indiretas (em minutos), os dez percentuais por
     portfólio e o total. */
  const COLABORADORES_DO_RATEIO = [
    ["Ana Souza", "Engenheira de Planejamento", "Refinaria", "Específico", 8520, 720, [0, 0, 0, 20, 60, 0, 10, 10, 0, 0], 100],
    ["Carlos Lima", "Técnico de Manutenção", "Impoundment", "Geral", 9930, 270, [40, 35, 15, 0, 0, 0, 0, 0, 5, 5], 100],
    ["Mariana Costa", "Inspetora de Qualidade", "Smelter", "Timesheet", 10200, 0, [0, 0, 0, 0, 0, 100, 0, 0, 0, 0], 100],
    ["Roberto Neves", "Coordenador de Projetos", "Porto", "Específico", 5280, 1920, [0, 0, 0, 0, 0, 20, 25, 55, 0, 0], 100],
    ["Fernanda Alves", "Analista de Contratos", "Pae", "Baseload", 9480, 600, [0, 10, 0, 0, 10, 0, 80, 0, 0, 0], 100],
    ["Paulo Mendes", "Engenheiro de Processos", "Refinaria", "Específico", 7830, 960, [0, 0, 0, 35, 45, 0, 0, 0, 0, 20], 100],
    ["Juliana Rocha", "Assistente Administrativa", "Engenharia", "Geral", 5700, 2700, [0, 50, 50, 0, 0, 0, 0, 0, 0, 0], 100],
    ["Thiago Nunes", "Supervisor de Operações", "Smelter", "Timesheet", 10470, 120, [0, 0, 0, 0, 0, 70, 10, 20, 0, 0], 100],
    ["Beatriz Ramos", "Arquiteta Corporativa", "Pae", "Baseload", 8880, 720, [0, 0, 0, 0, 0, 0, 90, 0, 0, 0], 90],
  ];
  const PORTFOLIOS_DO_RATEIO = [
    "Impoundment Eng Phase", "Impoundments Plant", "Impoundments Arbs", "Refinaria Especial", "Refinaria", "Smelter", "Pae", "Porto", "Arb 10", "Arb 11",
  ];

  function exemploTabelaFormatada() {
    const percentuais = PORTFOLIOS_DO_RATEIO.map(function (rotulo, i) {
      return { id: "p" + i, rotulo: rotulo, tipo: "percentual" };
    });
    const colunas = [
      { id: "nome", rotulo: "Colaborador" },
      { id: "cargo", rotulo: "Cargo" },
      { id: "portfolio", rotulo: "Portfólio", tipo: "categoria" },
      { id: "tipo", rotulo: "Tipo de rateio", tipo: "categoria" },
      {
        id: "horas",
        rotulo: "Horas em projeto",
        tipo: "hhmm",
        faixas: [{ ate: 6000, papel: "atencao" }, { ate: 9000, papel: "alerta" }, { ate: 10081, papel: "vazio" }, { papel: "comprometido" }],
      },
      { id: "indiretas", rotulo: "Horas indiretas", tipo: "hhmm", papel: "neutro" },
    ]
      .concat(percentuais)
      .concat([{ id: "total", rotulo: "Total", tipo: "percentual", esperado: 100 }]);
    const linhas = COLABORADORES_DO_RATEIO.map(function (c) {
      const linha = { nome: c[0], cargo: c[1], portfolio: c[2], tipo: c[3], horas: c[4], indiretas: c[5], total: c[7] };
      c[6].forEach(function (valor, i) {
        linha["p" + i] = valor;
      });
      return linha;
    });
    return {
      titulo: "Rateio de colaboradores, exemplo",
      rodape: "Rateio de colaboradores · Med Parc",
      rotulos: { buscar: "Pesquisar colaborador, cargo, portfólio..." },
      grupos: [
        { rotulo: "Dados de medição", colunas: 6 },
        { rotulo: "Rateio por portfólio", colunas: 10 },
        { rotulo: "Total", colunas: 1, total: true },
      ],
      colunas: colunas,
      linhas: linhas,
    };
  }

  /* As linhas do mapa de funções do original: previsto, realizado e contratado
     por função (PC, Pl, Ld, Co) e nas vagas diversas. */
  const FUNCOES_DO_MAPA = [
    { id: "pc", rotulo: "Project Control" },
    { id: "pl", rotulo: "Planejador" },
    { id: "ld", rotulo: "Líder de projetos" },
    { id: "co", rotulo: "Coord. Portfólio" },
    { id: "vd", rotulo: "Vagas diversas" },
  ];
  /* Por linha: nome, subtítulo, e [previsto, realizado, contratado] de cada função. */
  const LINHAS_DO_MAPA = [
    ["Refinaria", null, [[6, 6, 0], [5, 4, 2], [3, 3, 0], [2, 1, 1], [0, 0, 0]]],
    ["Smelter", null, [[4, 4, 0], [4, 2, 3], [2, 1, 2], [2, 0, 2], [3, 1, 2]]],
    ["Impoundment", null, [[3, 3, 0], [3, 1, 1], [2, 2, 0], [1, 1, 0], [2, 2, 0]]],
    ["PAE", null, [[4, 2, 4], [3, 3, 0], [1, 0, 1], [1, 1, 0], [3, 2, 1]]],
    ["Porto", null, [[2, 1, 1], [2, 2, 0], [1, 0, 0], [1, 1, 0], [2, 1, 1]]],
    ["Outros", "Suporte e construção", [[1, 1, 0], [1, 0, 1], [0, 0, 0], [0, 0, 0], [8, 5, 4]]],
  ];

  function exemploTabelaFormatada2() {
    return {
      titulo: "Mapa de funções, exemplo",
      primeira_coluna: "Portfólio",
      grupos: FUNCOES_DO_MAPA,
      medidas: [
        { id: "previsto", rotulo: "Prev", tipo: "previsto" },
        { id: "realizado", rotulo: "Real", tipo: "realizado" },
        { id: "saldo", rotulo: "Rem", tipo: "saldo" },
        { id: "contratado", rotulo: "Contr." },
      ],
      total: { grupo: "Total", linha: "Total geral" },
      faixas_progresso: [{ de: 100, papel: "ok" }, { de: 80, papel: "marca" }, { de: 50, papel: "alerta" }, { de: 0, papel: "atencao" }],
      faixas_saude: [{ de: 0, papel: "ok" }, { de: 1, papel: "alerta" }, { de: 3, papel: "atencao" }],
      linhas: LINHAS_DO_MAPA.map(function (linha) {
        const valores = {};
        FUNCOES_DO_MAPA.forEach(function (funcao, i) {
          valores[funcao.id] = { previsto: linha[2][i][0], realizado: linha[2][i][1], contratado: linha[2][i][2] };
        });
        return { id: linha[0].toLowerCase(), rotulo: linha[0], subtitulo: linha[1], valores: valores };
      }),
    };
  }

  /* A matriz de ações do original (hoje, 07/08/2026): quatro fases com quatro
     etapas cada e sete projetos. As datas dos projetos são dias antes (-) ou
     depois de hoje; a ação é [etapa na fase, previsto, concluído, estado,
     responsável, justificativa]. */
  const HOJE_DA_MATRIZ = "2026-08-07";
  const ETAPAS_DA_MATRIZ = [
    ["EXEC", ["Mobilização da frente", "Construção civil e fundações", "Montagem de passarela com juntas térmicas", "Comissionamento das unidades A/B"]],
    ["FEL1", ["Estudo de conceito", "Definição de escopo", "Lógica de viabilidade", "Aprovação da especificação funcional"]],
    ["FEL2", ["Engenharia básica", "Linha de base de investimento", "Contratação do EPC", "Aprovação de orçamento de capital"]],
    ["FEL3", ["Engenharia de detalhamento", "Licenciamento e contratação", "Construção e montagem", "Comissionamento final e startup"]],
  ];
  const ATRASOS_DA_MATRIZ = [
    { valor: "No prazo", papel: "ok" },
    { valor: "< 6 meses", papel: "alerta" },
    { valor: "< 1 ano", papel: "atencao" },
    { valor: "> 1 ano", papel: "erro" },
  ];
  const NIVEIS_DO_ORM = ["Extremo - 25", "Muito alto - 20", "Alto - 16", "Alto - 15", "Alto - 12", "Médio - 10", "Baixo - 9", "Baixo - 8"];
  const PORTFOLIOS_DA_MATRIZ = ["Alumar", "Impoundment", "Juruti", "PAE", "Poços de Caldas", "Porto", "Refinaria", "Smelter"];
  const RESPONSAVEIS_DA_MATRIZ = ["Alexandre Pontes", "Carla Fonseca", "Daniel Lima", "Eduarda Melo", "Felipe Ramos", "Gabriel Silva"];
  const ESTADOS_DA_MATRIZ = { C: "concluida", A: "em_andamento", N: "nao_iniciada" };
  /* Por projeto: nome, fase, atraso da entrega, atraso do RFA, nível do ORM,
     portfólio e as ações. */
  const PROJETOS_DA_MATRIZ = [
    ["Expansão de armazenagem - Bloco 5", 0, 3, 2, 4, "Refinaria", [
      [0, -25, -5, "C", 0, "Frente mobilizada e área de armazenagem liberada pelo contratado."],
      [1, 37, null, "N", 1, "Fundações condicionadas ao release da engenharia de fundo de caixa."],
      [2, 51, null, "A", 2, "Passagem pré-fabricada; mobilização do guindaste para a 3T26."],
      [3, 49, null, "N", 3, "Comissionamento agendado após o startup da linha de filmagem."],
    ]],
    ["Reforma do descarregador de navios", 0, 1, 0, 6, "Porto", [
      [1, 3, 20, "C", 0, "Fundos e obra civil concluídos com restrição parcial de área."],
      [2, 34, null, "A", 4, "Montagem em fase de preparação do shell externo."],
    ]],
    ["Ampliação do terminal de carga", 0, 1, 1, 2, "Juruti", [
      [2, 26, null, "N", 1, "Aguardando a licença ambiental da secretaria estadual."],
      [3, 40, null, "A", 3, "Interface elétrica em execução pela equipe de automação."],
    ]],
    ["Remodelagem do sistema de turbo sopradores", 1, 1, 0, 1, "Smelter", [
      [0, 28, 31, "C", 0, "Conceito final aprovado no comitê técnico de engenharia."],
      [1, 32, null, "A", 2, "Levantamento de mercado dos equipamentos de alta tensão."],
      [3, 46, null, "N", 5, "Especificação funcional em revisão pela gestão de ativos."],
    ]],
    ["Retomada do silo 2 de armazenagem", 1, 2, 1, 5, "Alumar", [
      [0, -6, -13, "C", 3, "Estudos atualizados; escopo emendado para vazão máx. de 480 t/h."],
      [1, 13, null, "N", 1, "Aprovação de investimento pendente junto ao conselho."],
      [2, 37, null, "A", 0, "Viabilidade econômica em consolidação na planilha de custos."],
    ]],
    ["Modernização da estação de bombeamento", 2, 0, 0, 2, "Porto", [
      [2, 33, null, "A", 4, "Pacote EPC em negociação com os três proponentes qualificados."],
      [0, 55, null, "N", 2, "Engenharia básica aguardando a definição da sala de comando."],
    ]],
    ["Backup da linha de transferência 2", 3, 0, 2, 4, "PAE", [
      [0, 35, 37, "C", 1, "Detalhamento concluído com uma redução corretiva de intertravamento."],
      [2, 36, null, "A", 0, "Construção e montagem da tubulação em adiantamento."],
      [3, 43, null, "N", 3, "Startup previsto após a retirada recursa do sistema antigo."],
    ]],
  ];

  /* A cor da borda do cartão pelo ranking do ORM (1 é o mais alto): no app é
     regra do servidor. */
  function faixaDoOrm(ranking) {
    if (ranking <= 1) return "erro";
    if (ranking === 2) return "atencao";
    if (ranking <= 5) return "alerta";
    return ranking <= 7 ? "info" : "vazio";
  }

  function exemploTabelaEtapas() {
    const fases = ETAPAS_DA_MATRIZ.map(function (fase) {
      const id = fase[0].toLowerCase();
      return {
        id: id,
        rotulo: fase[0],
        etapas: fase[1].map(function (rotulo, i) {
          return { id: id + "-" + (i + 1), rotulo: rotulo };
        }),
      };
    });
    const dia = function (dias) {
      return dias === null ? null : somarDias(HOJE_DA_MATRIZ, dias);
    };
    return {
      titulo: "Gerenciamento de pendências",
      subtitulo: "Ações por etapa · FEL e Execução",
      hoje: HOJE_DA_MATRIZ,
      rotulos: { buscar: "Buscar projeto, ação ou portfólio..." },
      fases: fases,
      marcadores: [
        { id: "late_ho", rotulo: "Late HO", valores: ATRASOS_DA_MATRIZ.map(function (a) { return a.valor; }) },
        { id: "rfa", rotulo: "RFA x Fcst", valores: ATRASOS_DA_MATRIZ.map(function (a) { return a.valor; }) },
        { id: "orm", rotulo: "ORM", valores: NIVEIS_DO_ORM },
        { id: "portfolio", rotulo: "Portfólio", valores: PORTFOLIOS_DA_MATRIZ },
      ],
      itens: PROJETOS_DA_MATRIZ.map(function (p, i) {
        const fase = fases[p[1]];
        return {
          id: "projeto-" + (i + 1),
          rotulo: p[0],
          fase: fase.id,
          faixa: faixaDoOrm(p[4] + 1),
          marcas: {
            late_ho: ATRASOS_DA_MATRIZ[p[2]],
            rfa: ATRASOS_DA_MATRIZ[p[3]],
            orm: { valor: NIVEIS_DO_ORM[p[4]], papel: "vazio", ponto: true },
            portfolio: { valor: p[5], papel: "marca" },
          },
          acoes: p[6].map(function (a) {
            return {
              etapa: fase.etapas[a[0]].id,
              estado: ESTADOS_DA_MATRIZ[a[3]],
              previsto: dia(a[1]),
              concluido: dia(a[2]),
              responsavel: RESPONSAVEIS_DA_MATRIZ[a[4]],
              justificativa: a[5],
            };
          }),
        };
      }),
    };
  }

  /* Os cinco níveis da pirâmide de segurança, do vértice para a base. */
  const NIVEIS_DA_PIRAMIDE = [
    { id: "grave", rotulo: "Lesões graves", papel: "erro" },
    { id: "leve", rotulo: "Lesões leves", papel: "atencao" },
    { id: "dano", rotulo: "Danos materiais", papel: "alerta" },
    { id: "quase", rotulo: "Quase acidentes", papel: "info" },
    { id: "desvio", rotulo: "Desvios", papel: "marca" },
  ];

  function exemploPiramide(referencia) {
    return {
      titulo: "Pirâmide de segurança, exemplo",
      niveis: NIVEIS_DA_PIRAMIDE,
      piramides: [
        { titulo: "No mês", valores: { grave: 2, leve: 5, dano: 9, quase: 41, desvio: 118 } },
        { titulo: "Acumulado", valores: { grave: 0, leve: 14, dano: 33, quase: 205, desvio: 1130 } },
      ],
      referencia: referencia,
    };
  }

  function exemploPiramideBird() {
    return exemploPiramide({
      nome: "Bird",
      termos: [
        { niveis: ["grave"], valor: 1 },
        { niveis: ["leve"], valor: 10 },
        { niveis: ["dano"], valor: 30 },
        { niveis: ["quase"], valor: 600 },
      ],
    });
  }

  function exemploPiramideHeinrich() {
    return exemploPiramide({
      nome: "Heinrich",
      termos: [
        { niveis: ["grave"], valor: 1 },
        { niveis: ["leve"], valor: 29 },
        { niveis: ["dano", "quase"], valor: 300 },
      ],
      nota: "níveis 3 e 4 somados",
    });
  }

  function exemploCascata() {
    return {
      titulo: "Cascata de valor do contrato, exemplo",
      formato: { divisor: 100, moeda: "BRL", casas: 0 },
      etapas: [
        { id: "original", rotulo: "Valor original", tipo: "total", valor: 3800000000 },
        { id: "aditivos", rotulo: "Aditivos aprovados", valor: 460000000 },
        { id: "reajustes", rotulo: "Reajustes", valor: 120000000 },
        { id: "atual", rotulo: "Valor atual", tipo: "total" },
        { id: "medido", rotulo: "Medido", valor: -2730000000 },
        { id: "saldo", rotulo: "Saldo a faturar", tipo: "total" },
      ],
    };
  }

  function exemploRosca() {
    const empresas = [
      ["Empresa A", 42],
      ["Empresa B", 31],
      ["Empresa C", 24],
      ["Empresa D", 17],
      ["Empresa E", 9],
      ["Empresa F", 6],
      ["Empresa G", 3],
    ];
    return {
      titulo: "Ocorrências por empresa, exemplo",
      rotulo_total: "Ocorrências",
      formato: { casas: 0 },
      fatias: empresas.map(function (empresa, i) {
        return { id: "e" + i, rotulo: empresa[0], valor: empresa[1] };
      }),
    };
  }

  /* TF e TRIF, mês a mês: de out/25 a set/26, com um mês sem leitura. */
  function exemploLinhasTaxas() {
    const tf = [0.82, 0.74, 0.61, 0.55, 0.69, 0.5, 0.44, 0.38, 0.41, 0.33, 0.29, 0.31];
    const trif = [1.9, 1.75, 1.52, 1.4, 1.66, 1.31, null, 1.08, 1.12, 0.95, 0.9, 0.86];
    return {
      titulo: "TF e TRIF mês a mês, exemplo",
      casas: 2,
      series: [
        { id: "tf", rotulo: "TF", papel: "realizado" },
        { id: "trif", rotulo: "TRIF", papel: "comprometido" },
      ],
      periodos: tf.map(function (valor, i) {
        const indice = i + 9;
        return { ano: 2025 + Math.floor(indice / 12), mes: (indice % 12) + 1, valores: { tf: valor, trif: trif[i] } };
      }),
    };
  }

  /* CPI e SPI de jan a set/26, em torno de 1,00. */
  function exemploLinhasIndices() {
    const cpi = [0.97, 0.96, 0.98, 0.95, 0.93, 0.94, 0.96, 0.97, 0.96];
    const spi = [1.02, 1.0, 0.98, 0.97, 0.95, 0.93, 0.94, 0.95, 0.94];
    return {
      titulo: "CPI e SPI mês a mês, exemplo",
      base_zero: false,
      casas: 2,
      series: [
        { id: "cpi", rotulo: "CPI", papel: "realizado" },
        { id: "spi", rotulo: "SPI", papel: "previsto" },
      ],
      referencias: [{ valor: 1, rotulo: "Meta 1,00", papel: "ok" }],
      periodos: cpi.map(function (valor, i) {
        return { ano: 2026, mes: i + 1, valores: { cpi: valor, spi: spi[i] } };
      }),
    };
  }

  Object.assign(EXEMPLOS, {
    gantt: exemploGantt,
    calendario: exemploCalendario,
    galeria: exemploGaleria,
    "formulario-cards": exemploFormularioCards,
    "areas-avaliacao": exemploAreas,
    "tabela-formatada": exemploTabelaFormatada,
    "tabela-formatada-2": exemploTabelaFormatada2,
    "tabela-etapa-por-etapa": exemploTabelaEtapas,
    "piramide-seguranca": exemploPiramideBird,
    "piramide-seguranca-heinrich": exemploPiramideHeinrich,
    "cascata-contrato": exemploCascata,
    rosca: exemploRosca,
    "linhas-multiplas": exemploLinhasTaxas,
    "linhas-multiplas-indices": exemploLinhasIndices,
  });

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

  /* ---------- Seleção ---------- */

  /* Os visuais clicáveis avisam a tela com grafico:selecionar. No app a tela o
     ouve por Alpine, sem script no fragmento; aqui o último evento aparece na
     linha de cima, para ver o que o servidor receberia. */
  const saidaDaSelecao = document.getElementById("sg-selecao");
  if (saidaDaSelecao) {
    document.addEventListener("grafico:selecionar", function (evento) {
      const d = evento.detail || {};
      const partes = [d.tipo];
      ["id", "linha", "coluna", "grupo", "valor"].forEach(function (chave) {
        if (d[chave] !== undefined && d[chave] !== null) partes.push(chave + " " + d[chave]);
      });
      saidaDaSelecao.textContent = "Último clique: " + partes.join(", ");
    });
  }

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
    /* Peças da ISSUE-015 (pecas.js): faixa, estado, percentual, diferença, soma. */
    ["faixa: maior_que é exclusivo (5 cai na faixa de baixo, 5,01 na de cima)", "alerta / erro", function () {
      const faixas = [{ maior_que: 5, tom: "erro" }, { de: 1, tom: "alerta" }];
      return G.pecas.faixaDe(5, faixas).tom + " / " + G.pecas.faixaDe(5.01, faixas).tom;
    }],
    ["faixa: ate é inclusivo e menor_que é exclusivo (10)", "ok / cinza", function () {
      return G.pecas.faixaDe(10, [{ ate: 10, tom: "ok" }]).tom + " / " + G.pecas.faixaDe(10, [{ menor_que: 10, tom: "ok" }, { tom: "cinza" }]).tom;
    }],
    ["faixa: sem valor, ou fora de todas as faixas, é sem faixa", "null / null", function () {
      return G.pecas.faixaDe(null, [{ tom: "ok" }]) + " / " + G.pecas.faixaDe(5, [{ de: 10, tom: "ok" }]);
    }],
    ["estado pelos limites: 80 é ok, 79,99 é alerta, 59,99 é erro", "ok / alerta / erro", function () {
      const limites = { ok: 80, alerta: 60 };
      return [80, 79.99, 59.99].map(function (valor) { return G.pecas.estadoPorLimites(valor, 80, limites); }).join(" / ");
    }],
    ["estado: sem limites vale a meta e, sem valor, é cinza", "erro / cinza", function () {
      return G.pecas.estadoPorLimites(50, 60, undefined) + " / " + G.pecas.estadoPorLimites(null, 60, undefined);
    }],
    ["percentual do total: total zero dá 0, e 6 de 47 dá 12,8", "0 / 12.8", function () {
      return G.pecas.percentualDe(1, 0) + " / " + G.pecas.percentualDe(6, 47).toFixed(1);
    }],
    ["diferença: 0,04 com uma casa é zero e fica neutra (não sobe)", "igual / neutro", function () {
      const d = G.pecas.delta(0.04, "sobe", 1);
      return d.sentido + " / " + d.tom;
    }],
    ["diferença: cair é bom quando o favorável é desce", "ok / erro", function () {
      return G.pecas.delta(-0.5, "desce", 1).tom + " / " + G.pecas.delta(0.5, "desce", 1).tom;
    }],
    ["soma ignora o nulo, e só nulos dão nulo (sem dado não é zero)", "3 / null", function () {
      return G.pecas.somar([1, null, 2]) + " / " + G.pecas.somar([null, null]);
    }],
    ["árvore: o pai sem valor soma os filhos; a folha sem valor é nula", "7 / null", function () {
      const ler = function (no) { return no.v; };
      const pai = { filhos: [{ v: 3 }, { v: 4 }] };
      return G.pecas.valorDaArvore(pai, ler) + " / " + G.pecas.valorDaArvore({}, ler);
    }],
  ];

  /* Casos de fronteira dos visuais da ISSUE-016. Os de cada fórmula com nome
     (situacaoDaAcao, proporcaoReal, agrupar...) conferem o limite onde o
     resultado vira: o dia do vencimento, o termo zerado, o máximo de fatias. */
  function casosDaIssue016() {
    const DATAS = G.apoio.datas;
    const hoje = DATAS.dia("2026-08-07");
    const acao = function (previsto, concluido, estado) {
      return { previsto: previsto === null ? null : DATAS.dia(previsto), concluido: concluido === null ? null : DATAS.dia(concluido), estado: estado };
    };
    const situacao = function (a, referencia) {
      const resultado = G.tabelaEtapaPorEtapa.situacaoDaAcao(a, referencia === undefined ? hoje : referencia);
      return resultado.tipo + "/" + resultado.desvio;
    };
    const urgente = function (previsto, tipo) {
      return { previsto: previsto === null ? null : DATAS.dia(previsto), situacao: { tipo: tipo } };
    };
    const classe = function (...tipos) {
      const resultado = G.tabelaEtapaPorEtapa.classeDoItem(
        tipos.map(function (tipo) {
          return { situacao: { tipo: tipo } };
        }),
      );
      return resultado.papel + "/" + resultado.progresso;
    };
    const datasDaGrade = function (ano, mes) {
      const celulas = G.calendario.celulasDoMes(ano, mes);
      const primeira = DATAS.partes(celulas[0]);
      const ultima = DATAS.partes(celulas[celulas.length - 1]);
      return celulas.length + ": " + primeira.dia + "/" + primeira.mes + " a " + ultima.dia + "/" + ultima.mes;
    };
    const fatias = function (...valores) {
      return valores.map(function (valor, i) {
        return { id: "f" + i, rotulo: "F" + i, valor: valor };
      });
    };
    const agrupadas = function (lista, maximo) {
      return G.rosca
        .agrupar(lista, maximo, "Outros")
        .map(function (fatia) {
          return fatia.valor;
        })
        .join(" ");
    };
    const etapasDaCascata = function (etapas) {
      return G.cascata
        .montar(etapas)
        .map(function (nivel) {
          return nivel.de + ">" + nivel.ate + " " + nivel.tipo;
        })
        .join(", ");
    };
    const termos = [{ niveis: ["grave"] }, { niveis: ["leve"] }];
    const ordenadas = function (resultado) {
      return resultado.termos.join(",") + (resultado.normalizada ? " (dividida)" : " (contagem)");
    };
    const faixaDeHoras = [{ ate: 6000, papel: "atencao" }, { ate: 9000, papel: "alerta" }, { papel: "neutro" }];
    const zonas = [{ de: 0, rotulo: "D" }, { de: 70, rotulo: "C" }, { de: 81, rotulo: "B" }, { de: 90, rotulo: "A" }];
    const blocos = [{ id: "p", tipo: "previsto" }, { id: "r", tipo: "realizado" }, { id: "s", tipo: "saldo" }];
    const faixasDeSaude = [{ de: 3, papel: "atencao" }, { de: 1, papel: "alerta" }, { de: 0, papel: "ok" }];
    const mes = function (lugar) {
      return lugar.ano + "-" + lugar.mes;
    };
    const eixoDaFaixa = function (menor, maior) {
      const eixo = G.linhasMultiplas.escalaDaFaixa(menor, maior);
      return eixo.min.toFixed(2) + " a " + eixo.max.toFixed(2) + ", " + (eixo.passos.length - 1) + " intervalos";
    };
    return [
      ["Gantt: o desvio é o término menos o da linha de base (10/03 contra 03/03)", "7", function () {
        return G.gantt.prepararAtividade({ inicio: "2026-03-01", fim: "2026-03-10", base_fim: "2026-03-03" }).desvio;
      }],
      ["Gantt: a janela vai do dia 1 do mês da data mais antiga até a mais tardia mais 15 dias", "01/02/2026 a 20/03/2026, 48 dias", function () {
        const janela = G.gantt.janelaDe({}, [G.gantt.prepararAtividade({ inicio: "2026-02-10", fim: "2026-03-05" })]);
        return DATAS.completa(janela.inicio) + " a " + DATAS.completa(janela.fim) + ", " + janela.dias + " dias";
      }],
      ["Gantt: hoje no 5º de 10 dias da barra, a sombra do que falta começa em 40%", "0.4", function () {
        return G.gantt.fracaoDoFuturo({ inicio: DATAS.dia("2026-08-01"), fim: DATAS.dia("2026-08-10"), concluida: false }, DATAS.dia("2026-08-05"));
      }],
      ["Gantt: hoje no primeiro dia da barra, ela toda é futuro; no último dia, não há sombra", "0 / null", function () {
        const atividade = { inicio: DATAS.dia("2026-08-01"), fim: DATAS.dia("2026-08-10"), concluida: false };
        return G.gantt.fracaoDoFuturo(atividade, DATAS.dia("2026-08-01")) + " / " + G.gantt.fracaoDoFuturo(atividade, DATAS.dia("2026-08-10"));
      }],
      ["Gantt: atividade concluída ou ainda não começada não leva sombra", "null / null", function () {
        const feita = { inicio: DATAS.dia("2026-08-01"), fim: DATAS.dia("2026-08-10"), concluida: true };
        const futura = { inicio: DATAS.dia("2026-08-01"), fim: DATAS.dia("2026-08-10"), concluida: false };
        return G.gantt.fracaoDoFuturo(feita, DATAS.dia("2026-08-05")) + " / " + G.gantt.fracaoDoFuturo(futura, DATAS.dia("2026-07-31"));
      }],
      ["Calendário: maio de 2026 começa numa sexta, e a grade de 42 células vai de 26/04 a 06/06", "42: 26/4 a 6/6", function () { return datasDaGrade(2026, 5); }],
      ["Calendário: fevereiro de 2026 começa num domingo, e a grade vai de 01/02 a 14/03", "42: 1/2 a 14/3", function () { return datasDaGrade(2026, 2); }],
      ["Calendário: dezembro mais um mês é janeiro do ano seguinte; janeiro menos um é dezembro", "2027-1 / 2025-12", function () {
        return mes(G.calendario.mesVizinho({ ano: 2026, mes: 12 }, 1)) + " / " + mes(G.calendario.mesVizinho({ ano: 2026, mes: 1 }, -1));
      }],
      ["Calendário: o selo soma as quantidades do dia e pega a situação mais grave", "3 erro", function () {
        const situacoes = [{ id: "ok", papel: "ok" }, { id: "atraso", papel: "erro" }, { id: "alerta", papel: "alerta" }];
        const resumo = G.calendario.resumoDoDia({ valores: { ok: 2, atraso: 1, alerta: 0 } }, situacoes);
        return resumo.total + " " + resumo.papel;
      }],
      ["Calendário: o papel mandado no dia troca a escolha pela situação mais grave", "info", function () {
        return G.calendario.resumoDoDia({ valores: { ok: 2 }, papel: "info" }, [{ id: "ok", papel: "ok" }]).papel;
      }],
      ["Galeria: do primeiro cartão voltar vai ao último; do último avançar vai ao primeiro; com um só, fica nele", "4 / 0 / 0", function () {
        return [G.galeria.cartaoVizinho(0, -1, 5), G.galeria.cartaoVizinho(4, 1, 5), G.galeria.cartaoVizinho(0, 1, 1)].join(" / ");
      }],
      ["Áreas: a nota 70 é da faixa que começa em 70, 89,99 é da de 81 e 90 é da de 90", "C / B / A", function () {
        return [70, 89.99, 90].map(function (nota) { return G.areasAvaliacao.zonaDoValor(zonas, nota).rotulo; }).join(" / ");
      }],
      ["Áreas: nota abaixo de todas as faixas fica na mais baixa; sem faixas, não há faixa", "D / null", function () {
        return G.areasAvaliacao.zonaDoValor(zonas, -5).rotulo + " / " + G.areasAvaliacao.zonaDoValor([], 50);
      }],
      ["Áreas: o piso do eixo é o menor entre 60 e a dezena quatro pontos abaixo da menor nota (68,4: 60; 42: 30)", "60 / 30", function () {
        return G.areasAvaliacao.limitesDoEixo({}, [68.4, 71]).min + " / " + G.areasAvaliacao.limitesDoEixo({}, [42]).min;
      }],
      ["Áreas: eixo_min e eixo_max fixam as pontas, e sem nota o eixo vai de 0 a 100", "50-95 / 0-100", function () {
        const fixo = G.areasAvaliacao.limitesDoEixo({ eixo_min: 50, eixo_max: 95 }, [42]);
        const vazio = G.areasAvaliacao.limitesDoEixo({}, []);
        return fixo.min + "-" + fixo.max + " / " + vazio.min + "-" + vazio.max;
      }],
      ["Tabela formatada: 8520 minutos são 142:00, 270 são 4:30 e 0 é 0:00; 59,6 arredonda para 1:00 e não 0:60", "142:00 / 4:30 / 0:00 / 1:00", function () {
        return [8520, 270, 0, 59.6].map(G.tabelaFormatada.horasEMinutos).join(" / ");
      }],
      ["Tabela formatada: o valor igual ao limite da faixa cai na faixa seguinte (5999, 6000 e acima de tudo)", "atencao / alerta / neutro", function () {
        return [5999, 6000, 99999].map(function (valor) { return G.tabelaFormatada.papelDaFaixa(faixaDeHoras, valor, "x"); }).join(" / ");
      }],
      ["Tabela formatada: sem faixas vale o papel padrão", "padrao", function () { return G.tabelaFormatada.papelDaFaixa([], 10, "padrao"); }],
      ["Tabela formatada: o fundo do mapa de calor em 0%, 50%, 100% e 110% (passando de 100% recomeça mais claro, em vermelho)", "0.12 / 0.46 / 0.80 / 0.40", function () {
        return [0, 0.5, 1, 1.1].map(function (fracao) { return G.tabelaFormatada.intensidadeDoCalor(fracao).toFixed(2); }).join(" / ");
      }],
      ["Tabela Formata 2: o saldo é previsto menos realizado e fica negativo quando o realizado passa", "2 / -2", function () {
        return G.tabelaFormatada2.comSaldo({ p: 6, r: 4 }, blocos).s + " / " + G.tabelaFormatada2.comSaldo({ p: 4, r: 6 }, blocos).s;
      }],
      ["Tabela Formata 2: a faixa vale pelo maior limite que o valor alcança (3, 2, 0 e -1)", "atencao / alerta / ok / null", function () {
        return [3, 2, 0, -1].map(function (saldo) { return String(G.tabelaFormatada2.papelPeloLimite(faixasDeSaude, saldo)); }).join(" / ");
      }],
      ["Tabela Formata 2: o avanço sem previsto é 0, passando do previsto fica em 100, e 1 de 3 é 33", "0 / 100 / 33", function () {
        return [[0, 0], [6, 7], [3, 1]].map(function (par) { return G.tabelaFormatada2.avancoEmPercentual(par[0], par[1]); }).join(" / ");
      }],
      ["Tabela Formata 2: o remanescente é laranja se falta, verde se fecha e vermelho se passou", "atencao / ok / erro", function () {
        return [2, 0, -1].map(G.tabelaFormatada2.papelDoSaldo).join(" / ");
      }],
      ["Etapa por etapa: ação não iniciada com previsto hoje vence hoje, e com previsto ontem está atrasada em 1 dia", "naoIniciada/0 / naoIniciadaAtrasada/1", function () {
        return situacao(acao("2026-08-07", null, "nao_iniciada")) + " / " + situacao(acao("2026-08-06", null, "nao_iniciada"));
      }],
      ["Etapa por etapa: ação em andamento com previsto ontem está atrasada em 1 dia", "andamentoAtrasado/1", function () {
        return situacao(acao("2026-08-06", null, "em_andamento"));
      }],
      ["Etapa por etapa: concluída no previsto não tem atraso; um dia depois é concluída com atraso de 1 dia", "concluida/0 / concluidaAtraso/1", function () {
        return situacao(acao("2026-08-01", "2026-08-01", "concluida")) + " / " + situacao(acao("2026-08-01", "2026-08-02", "concluida"));
      }],
      ["Etapa por etapa: sem as duas datas o estado decide (concluída sem data, em andamento, sem ação)", "concluidaSemData/null / emAndamento/null / semAcao/null", function () {
        return [acao(null, null, "concluida"), acao(null, null, "em_andamento"), acao(null, null, "nao_iniciada")].map(function (a) { return situacao(a); }).join(" / ");
      }],
      ["Etapa por etapa: sem a data de hoje, a ação em andamento não fica atrasada", "emAndamento/null", function () {
        return situacao(acao("2026-08-01", null, "em_andamento"), null);
      }],
      ["Etapa por etapa: na célula vale a ação mais urgente, e no empate a de previsto mais antigo", "urgente / mais antiga", function () {
        const andamento = urgente("2026-08-10", "emAndamento");
        const antiga = urgente("2026-08-05", "emAndamento");
        const atrasada = urgente("2026-08-20", "andamentoAtrasado");
        const porUrgencia = G.tabelaEtapaPorEtapa.acaoMaisUrgente([andamento, atrasada]) === atrasada;
        const porData = G.tabelaEtapaPorEtapa.acaoMaisUrgente([andamento, antiga]) === antiga;
        return (porUrgencia ? "urgente" : "errado") + " / " + (porData ? "mais antiga" : "errado");
      }],
      ["Etapa por etapa: projeto todo concluído é ok (100%); com concluída e atrasada, erro (50%)", "ok/100 / erro/50", function () {
        return classe("concluida", "concluidaAtraso") + " / " + classe("concluida", "andamentoAtrasado");
      }],
      ["Etapa por etapa: concluída com pendente em dia é alerta (50%); só não iniciadas ou sem ação, neutro (0%)", "alerta/50 / neutro/0 / neutro/0", function () {
        return classe("concluida", "naoIniciada") + " / " + classe("naoIniciada", "naoIniciada") + " / " + classe("semAcao");
      }],
      ["Pirâmide: a proporção real divide pelo primeiro termo (2 e 5 dão 1 : 2,5)", "1,2.5 (dividida)", function () {
        return ordenadas(G.piramide.proporcaoReal({ grave: 2, leve: 5 }, termos));
      }],
      ["Pirâmide: com o primeiro termo zerado não há como dividir, e mostra a contagem", "0,5 (contagem)", function () {
        return ordenadas(G.piramide.proporcaoReal({ grave: 0, leve: 5 }, termos));
      }],
      ["Pirâmide: o último termo de Heinrich soma dois níveis (1 : 29 : 300)", "1,29,300 (dividida)", function () {
        const heinrich = [{ niveis: ["grave"] }, { niveis: ["leve"] }, { niveis: ["dano", "quase"] }];
        return ordenadas(G.piramide.proporcaoReal({ grave: 1, leve: 29, dano: 100, quase: 200 }, heinrich));
      }],
      ["Pirâmide: a faixa do vértice é um triângulo e a da base ocupa a largura toda", "polygon(50% 0, 50% 0, 60% 100%, 40% 100%) / polygon(10% 0, 90% 0, 100% 100%, 0% 100%)", function () {
        return G.piramide.poligonoDaFaixa(0, 5) + " / " + G.piramide.poligonoDaFaixa(4, 5);
      }],
      ["Cascata: o total sem valor assume a soma corrida (100 + 20), e a redução parte dali", "0>100 total, 100>120 acrescimo, 0>120 total, 120>70 reducao, 0>70 total", function () {
        return etapasDaCascata([
          { id: "a", tipo: "total", valor: 100 },
          { id: "b", valor: 20 },
          { id: "c", tipo: "total" },
          { id: "d", valor: -50 },
          { id: "e", tipo: "total" },
        ]);
      }],
      ["Cascata: a redução maior que o acumulado atravessa o zero, e o eixo cobre o menor nível", "100>-30 reducao / -50 a 100", function () {
        const etapas = [{ id: "a", tipo: "total", valor: 100 }, { id: "b", valor: -130 }];
        const niveis = G.cascata.montar(etapas);
        const eixo = G.cascata.escalaDoEixo(niveis);
        return niveis[1].de + ">" + niveis[1].ate + " " + niveis[1].tipo + " / " + eixo.min + " a " + eixo.max;
      }],
      ["Rosca: passando do máximo de 5 fatias, as quatro maiores ficam e as outras três juntam em Outros (9 + 6 + 3)", "42 31 24 17 18", function () {
        return agrupadas(fatias(3, 42, 31, 24, 17, 9, 6), 5);
      }],
      ["Rosca: com exatamente o máximo de fatias não agrupa (ordem decrescente)", "5 4 3 2 1", function () { return agrupadas(fatias(1, 2, 3, 4, 5), 5); }],
      ["Rosca: fatia zerada, negativa ou sem número não entra", "5 2", function () { return agrupadas(fatias(0, -3, 5, Number.NaN, 2), 5); }],
      ["Rosca: máximo de fatias 0 desliga o agrupamento", "7 6 5 4 3 2 1", function () { return agrupadas(fatias(1, 2, 3, 4, 5, 6, 7), 0); }],
      ["Linhas: a escala do zero ao 5 tem passos de 1", "0.00 a 5.00, 5 intervalos", function () { return eixoDaFaixa(0, 5); }],
      ["Linhas: sem base no zero, o eixo se ajusta ao dado (de 0,85 a 1,10)", "0.85 a 1.10, 5 intervalos", function () { return eixoDaFaixa(0.85, 1.1); }],
      ["Linhas: a curva suave não passa abaixo da menor leitura nem acima da maior", "0 a 50", function () {
        const numeros = G.linhasMultiplas.caminhoSuave([[0, 50], [10, 0], [20, 50], [30, 50]]).match(/-?\d+(\.\d+)?/g).map(Number);
        const alturas = numeros.filter(function (_numero, i) { return i % 2 === 1; });
        return Math.min(...alturas) + " a " + Math.max(...alturas);
      }],
    ];
  }

  CASOS.push(...casosDaIssue016());

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

  /* ---------- Mapeamento da D11 e cobertura da biblioteca ---------- */

  /* A tabela da D11 da spec: [necessidade no GestNow, [[nome do visual, tipo]]].
     O tipo é o data-grafico do visual e o id da seção dele nesta página. */
  const MAPEAMENTO = [
    ["Curva S física e financeira, avanço da programação, Curva S do MAS", [["Curva S Linha", "curva-s-linha"]]],
    [
      "Desembolso previsto x realizado, contratação acumulada, avanço por período com acumulado",
      [["Curva S Barra e Linha", "curva-s-barra-linha"]],
    ],
    ["Avanço por período, real x previsto, comparação entre meses", [["Comparativo de Barras Entre períodos", "comparativo-barras"]]],
    ["Pareto de RNC, de origem de mudanças, de motivos de parada", [["Pareto", "pareto"]]],
    ["Cards de KPI com referência de gestão", [["Card Indicador Único", "card-indicador"], ["Card com detalhes", "card-indicador-detalhes"]]],
    ["Faixa de KPIs com estado", [["HTML KPI Status", "kpi-status"]]],
    ["SPI, CPI, aderência, conformidade, índice do MAS", [["Relógios de Indicadores", "relogios"]]],
    ["Matriz P x I e severidade de riscos", [["Matriz Formatada", "matriz-formatada"], ["Separação Severidade Riscos", "severidade-riscos"]]],
    ["Mapa de calor do desvio da EAC, dia x frente, aging", [["Tabela Heatmap", "tabela-heatmap"]]],
    [
      "MAS (12 marcos por pacote), plano de quantidades por semana",
      [["Mapa 52 semanas", "mapa-52-semanas"], ["Tabela Quantitativos por entregável", "tabela-quantitativos"]],
    ],
    ["Etapas do processo de compra, fluxo da SM, ciclo da RNC", [["Etapas", "etapas"]]],
    ["6WLA, cronograma de marcos e auditorias", [["Gráfico Gantt", "gantt"], ["HTML Calendário", "calendario"]]],
    ["Restrições do 6WLA, acervo de lições", [["Galeria", "galeria"], ["Formulário de Cards", "formulario-cards"]]],
    ["Desempenho da contratada ao longo do tempo", [["Gráfico de Áreas de Avaliação", "areas-avaliacao"]]],
    [
      "Tabelas detalhadas (mapa de controle, EAP, punch)",
      [["Tabela formatada", "tabela-formatada"], ["Tabela Formata 2", "tabela-formatada-2"], ["Tabela Etapa por etapa", "tabela-etapa-por-etapa"]],
    ],
  ];

  /* Os quatro visuais sem equivalente na coletânea, construídos no mesmo padrão. */
  const MAPEAMENTO_NOVOS = [
    ["Painel HSE: pirâmides do mês e do acumulado, com a proporção de referência", [["Pirâmide de segurança dupla", "piramide-seguranca"]]],
    ["Ficha do contrato: do valor original ao saldo a faturar", [["Cascata de valor do contrato", "cascata-contrato"]]],
    ["Distribuição de um total em partes (ocorrências por empresa e por área)", [["Rosca de distribuição", "rosca"]]],
    ["TF e TRIF, CPI e SPI mês a mês", [["Linhas múltiplas", "linhas-multiplas"]]],
  ];

  function preencherMapeamento(corpo, linhas) {
    linhas.forEach(function (linha) {
      const partes = [];
      linha[1].forEach(function (visual, i) {
        if (i > 0) partes.push(", ");
        partes.push(document.getElementById(visual[1]) ? G.el("a", { href: "#" + visual[1], texto: visual[0] }) : visual[0]);
      });
      corpo.appendChild(G.el("tr", {}, [G.el("td", { texto: linha[0] }), G.el("td", {}, partes)]));
    });
  }

  /* Quantos tipos da lista têm um gráfico desenhado nesta página. */
  function comExemplo(linhas) {
    const tipos = new Set();
    linhas.forEach(function (linha) {
      linha[1].forEach(function (visual) {
        tipos.add(visual[1]);
      });
    });
    const presentes = Array.from(tipos).filter(function (tipo) {
      return document.querySelector('[data-grafico="' + tipo + '"]') !== null;
    });
    return { total: tipos.size, presentes: presentes.length };
  }

  const tabelaDoMapeamento = document.getElementById("sg-mapeamento");
  if (tabelaDoMapeamento) {
    preencherMapeamento(tabelaDoMapeamento, MAPEAMENTO);
    preencherMapeamento(document.getElementById("sg-mapeamento-novos"), MAPEAMENTO_NOVOS);
    const coletanea = comExemplo(MAPEAMENTO);
    const novos = comExemplo(MAPEAMENTO_NOVOS);
    document.getElementById("sg-cobertura").textContent =
      coletanea.presentes + " de " + coletanea.total + " visuais da coletânea e " + novos.presentes + " de " + novos.total +
      " visuais novos têm exemplo nesta página.";
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

  /* ---------- Tons dos cards, matrizes e tabelas ---------- */

  const tabelaDeTons = document.getElementById("sg-tons");
  if (tabelaDeTons) {
    [
      ["ok", "ok"],
      ["alerta", "warn"],
      ["atencao", "laranja"],
      ["erro", "erro"],
      ["info", "azul"],
      ["neutro", "frio"],
      ["roxo", "roxo"],
      ["cinza", "neutro"],
    ].forEach(function (par) {
      tabelaDeTons.appendChild(
        G.el("tr", {}, [
          G.el("td", {}, [G.pecas.chip(par[0], par[0], { icone: true })]),
          G.el("td", {}, [G.el("code", { texto: par[0] })]),
          G.el("td", {}, [G.el("code", { texto: par[1] })]),
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
