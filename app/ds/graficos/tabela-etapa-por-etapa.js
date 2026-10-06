/* ============================================================
   graficos/tabela-etapa-por-etapa.js — Tabela Etapa por etapa

   Porte de "Tabela Etapa por etapa super detalhada.html"
   (docs/referencia/graficos/): a matriz de ações por etapa. Uma linha
   (cartão) por projeto e uma coluna por etapa da fase que está à vista; cada
   célula mostra a ação mais urgente da etapa (o previsto, o concluído, a
   situação, o desvio em dias e a justificativa), com um selo de quantidade
   quando há mais de uma. No alto: o título, os contadores de projetos por
   situação, as abas das fases, a busca e os filtros; embaixo, a legenda e o
   resumo da fase. Tocar numa célula com ação abre, sobre o próprio visual, o
   detalhe de todas as ações dela (responsável, prazos e justificativa); Esc
   ou a sombra fecham. Serve as tabelas detalhadas (mapa de controle, EAP,
   punch).

   Contrato dos dados (data-dados):
     {
       "titulo": "Gerenciamento de pendências",
       "subtitulo": "Ações por etapa · FEL e Execução",
       "hoje": "2026-08-07",
       "fases": [{ "id": "exec", "rotulo": "EXEC", "etapas": [
                    { "id": "mobilizacao", "rotulo": "Mobilização da frente" }] }],
       "marcadores": [{ "id": "orm", "rotulo": "ORM", "valores": ["Alto", "Médio"] }],
       "itens": [{
         "id": "03246", "rotulo": "Expansão de armazenagem - Bloco 5",
         "fase": "exec", "faixa": "erro",
         "marcas": { "orm": { "valor": "Alto", "papel": "atencao", "ponto": true } },
         "acoes": [{ "etapa": "mobilizacao", "estado": "em_andamento",
                     "previsto": "2026-08-01", "concluido": null,
                     "responsavel": "Alexandre Pontes",
                     "justificativa": "Frente mobilizada." }]
       }]
     }
   As datas são texto ISO e `hoje` vem do servidor (a biblioteca não lê o
   relógio). `estado` é o que o servidor registra da ação: `concluida`,
   `em_andamento` ou `nao_iniciada`. A situação sai daqui, das datas e do
   estado (situacaoDaAcao): com data de conclusão, "Concluído" (ou "com
   atraso" se passou do previsto); sem ela, o desvio é hoje menos o previsto e
   a ação em andamento ou não iniciada fica atrasada quando é positivo; sem as
   duas datas, `concluida` é "Concluído sem data", `em_andamento` é "Em
   andamento" e `nao_iniciada` é "Sem ação". Numa célula com várias ações vale
   a mais urgente (acaoMaisUrgente). O projeto é "Concluído" se todas as ações
   com situação estão concluídas; senão "Atrasado" se alguma tem atraso;
   senão "Em andamento" se alguma está em andamento ou já há concluída;
   senão "Não iniciado" (classeDoItem). `fase` omitida vale a primeira; ação
   de etapa que a fase não tem e projeto de fase que não existe são
   ignorados. `faixa` é o papel de cor da borda do cartão (a regra é do
   servidor, como o ORM do original). `marcadores` são os rótulos do
   cabeçalho do cartão e, ao mesmo tempo, os filtros do alto: `valores` fixa
   a ordem das opções (senão, a da primeira aparição). `marcas` traz, por
   marcador, o `valor`, o `papel` de cor e `ponto` (o pontinho na cor da
   borda). Os textos de interface vêm em `rotulos`.

     <div data-grafico="tabela-etapa-por-etapa" data-dados='{{ grafico | tojson }}'></div>

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;
  const A = G.apoio;
  const D = A.datas;

  /* A chave de cada situação (semAcao, concluida...) é também a do rótulo
     curto (a célula); o longo é a chave mais "Longa" (a dica e o detalhe). */
  const ROTULOS = {
    buscar: "Buscar projeto, ação ou portfólio...",
    projetos: "Projetos",
    concluidos: "Concluídos",
    andamento: "Em andamento",
    atrasados: "Atrasados",
    naoIniciados: "Não iniciados",
    status: "Status",
    responsavel: "Responsável",
    filtroTodos: "{filtro}: todos",
    previsto: "Prev",
    concluido: "Concl",
    acao: "Ação",
    acoesNoDetalhe: "{n} ação(ões)",
    semJustificativa: "Sem justificativa registrada para esta ação.",
    prazoPrevisto: "Prazo previsto",
    conclusao: "Conclusão",
    fechar: "Fechar",
    semProjetos: "Nenhum projeto atende aos filtros selecionados.",
    progresso: "Ações concluídas",
    resumo: "{fase} — {com} etapas com ação, {sem} sem  •  {etapas} etapas na fase",
    atrasoDaConcluida: "+{n}d atraso",
    atraso: "{n}d atraso",
    antes: "{n}d antes",
    faltam: "faltam {n}d",
    noPrazo: "no prazo",
    venceHoje: "vence hoje",
    semPrevisto: "sem previsto",
    semAcao: "Sem ação",
    semAcaoLonga: "Sem ação registrada",
    concluida: "Concluído",
    concluidaLonga: "Concluído sem atraso",
    concluidaAtraso: "Concl. c/ atraso",
    concluidaAtrasoLonga: "Concluído com atraso",
    concluidaSemData: "Concl. s/ data",
    concluidaSemDataLonga: "Concluído sem data de conclusão",
    emAndamento: "Em andamento",
    emAndamentoLonga: "Em andamento - No prazo",
    andamentoAtrasado: "Andam. atrasado",
    andamentoAtrasadoLonga: "Em andamento - Atrasado",
    naoIniciada: "No prazo",
    naoIniciadaLonga: "Não iniciado - No prazo",
    naoIniciadaAtrasada: "Não inic. atrasado",
    naoIniciadaAtrasadaLonga: "Não iniciado - Atrasado",
    legendaConcluido: "Concluído",
    legendaAndamento: "Em andamento",
    legendaAtrasado: "Atrasado",
    legendaNaoIniciado: "Não iniciado",
    legendaSemAcao: "Sem ação",
  };

  /* Por situação: o papel da pílula, o do pontinho (a concluída com atraso é
     verde com o ponto vermelho) e a urgência, de 0 a 7. */
  const SITUACOES = {
    semAcao: { pilula: "vazio", ponto: "vazio", urgencia: 0 },
    concluida: { pilula: "ok", ponto: "ok", urgencia: 1 },
    concluidaSemData: { pilula: "alerta", ponto: "alerta", urgencia: 2 },
    concluidaAtraso: { pilula: "ok", ponto: "erro", urgencia: 3 },
    naoIniciada: { pilula: "neutro", ponto: "neutro", urgencia: 4 },
    emAndamento: { pilula: "alerta", ponto: "alerta", urgencia: 5 },
    naoIniciadaAtrasada: { pilula: "erro", ponto: "erro", urgencia: 6 },
    andamentoAtrasado: { pilula: "erro", ponto: "erro", urgencia: 7 },
  };
  const TIPOS_CONCLUIDOS = ["concluida", "concluidaAtraso", "concluidaSemData"];
  const TIPOS_ATRASADOS = ["concluidaAtraso", "andamentoAtrasado", "naoIniciadaAtrasada"];
  const TIPOS_EM_ANDAMENTO = ["emAndamento", "andamentoAtrasado"];
  /* As quatro classes do projeto, na ordem dos contadores e do filtro. */
  const CLASSES = [
    { papel: "ok", rotulo: "concluidos" },
    { papel: "alerta", rotulo: "andamento" },
    { papel: "erro", rotulo: "atrasados" },
    { papel: "neutro", rotulo: "naoIniciados" },
  ];
  const LEGENDA = [
    ["ok", "legendaConcluido"],
    ["alerta", "legendaAndamento"],
    ["erro", "legendaAtrasado"],
    ["neutro", "legendaNaoIniciado"],
    ["vazio", "legendaSemAcao"],
  ];
  const SEM_DADO = "—";

  /* ---------- Contas ---------- */

  function preencher(texto, valores) {
    return Object.keys(valores).reduce(function (resultado, chave) {
      return resultado.replace("{" + chave + "}", String(valores[chave]));
    }, texto);
  }

  /* Ação com conclusão: concluída, com atraso se passou do previsto. */
  function situacaoConcluida(acao) {
    if (acao.previsto === null) return { tipo: "concluida", desvio: null };
    const desvio = acao.concluido - acao.previsto;
    return { tipo: desvio > 0 ? "concluidaAtraso" : "concluida", desvio: desvio };
  }

  /* Ação sem nenhuma das duas datas: só o estado diz o que há para mostrar. */
  function situacaoSemDatas(estado) {
    if (estado === "concluida") return { tipo: "concluidaSemData", desvio: null };
    return { tipo: estado === "em_andamento" ? "emAndamento" : "semAcao", desvio: null };
  }

  /* Ação com previsto e sem conclusão: o desvio é o atraso de hoje sobre o
     previsto (positivo passou, negativo ainda falta); sem `hoje`, não há
     como dizer. */
  function situacaoEmAberto(estado, atraso) {
    const atrasada = atraso !== null && atraso > 0;
    if (estado === "concluida") return { tipo: "concluidaSemData", desvio: atraso };
    if (estado === "em_andamento") return { tipo: atrasada ? "andamentoAtrasado" : "emAndamento", desvio: atraso };
    return { tipo: atrasada ? "naoIniciadaAtrasada" : "naoIniciada", desvio: atraso };
  }

  /* acao: { previsto, concluido (dias inteiros ou nulo), estado }; hoje:
     dia inteiro ou nulo. Devolve { tipo, desvio }. */
  function situacaoDaAcao(acao, hoje) {
    if (acao.concluido !== null) return situacaoConcluida(acao);
    if (acao.previsto === null) return situacaoSemDatas(acao.estado);
    return situacaoEmAberto(acao.estado, hoje === null ? null : hoje - acao.previsto);
  }

  /* A mais urgente vence; no empate, a de previsto mais antigo. */
  function maisUrgente(atual, candidata) {
    const urgenciaAtual = SITUACOES[atual.situacao.tipo].urgencia;
    const urgenciaCandidata = SITUACOES[candidata.situacao.tipo].urgencia;
    if (urgenciaCandidata !== urgenciaAtual) return urgenciaCandidata > urgenciaAtual ? candidata : atual;
    const maisAntiga = candidata.previsto !== null && atual.previsto !== null && candidata.previsto < atual.previsto;
    return maisAntiga ? candidata : atual;
  }

  function acaoMaisUrgente(acoes) {
    return acoes.reduce(maisUrgente);
  }

  function contarTipos(acoes, tipos) {
    return acoes.filter(function (acao) {
      return tipos.includes(acao.situacao.tipo);
    }).length;
  }

  /* A classe e o avanço do projeto pelas ações que têm situação. */
  function classeDoItem(acoes) {
    const contadas = acoes.filter(function (acao) {
      return acao.situacao.tipo !== "semAcao";
    });
    if (!contadas.length) return { papel: "neutro", progresso: 0 };
    const concluidas = contarTipos(contadas, TIPOS_CONCLUIDOS);
    const progresso = Math.round((concluidas * 100) / contadas.length);
    if (concluidas === contadas.length) return { papel: "ok", progresso: progresso };
    if (contarTipos(contadas, TIPOS_ATRASADOS) > 0) return { papel: "erro", progresso: progresso };
    const andando = contarTipos(contadas, TIPOS_EM_ANDAMENTO) > 0 || concluidas > 0;
    return { papel: andando ? "alerta" : "neutro", progresso: progresso };
  }

  /* O texto e o papel de cor do desvio de uma ação. */
  function desvioDaConcluida(ctx, desvio) {
    if (desvio > 0) return { texto: preencher(ctx.rotulo("atrasoDaConcluida"), { n: desvio }), papel: "erro" };
    if (desvio < 0) return { texto: preencher(ctx.rotulo("antes"), { n: -desvio }), papel: "ok" };
    return { texto: ctx.rotulo("noPrazo"), papel: "ok" };
  }

  function desvioEmAberto(ctx, desvio) {
    if (desvio > 0) return { texto: preencher(ctx.rotulo("atraso"), { n: desvio }), papel: "erro" };
    if (desvio < 0) return { texto: preencher(ctx.rotulo("faltam"), { n: -desvio }), papel: "neutro" };
    return { texto: ctx.rotulo("venceHoje"), papel: "alerta" };
  }

  function descreverDesvio(ctx, acao) {
    const desvio = acao.situacao.desvio;
    if (acao.situacao.tipo === "semAcao") return { texto: SEM_DADO, papel: "vazio" };
    if (desvio === null) return { texto: acao.previsto === null ? ctx.rotulo("semPrevisto") : "", papel: "neutro" };
    return acao.concluido === null ? desvioEmAberto(ctx, desvio) : desvioDaConcluida(ctx, desvio);
  }

  /* ---------- Dados ---------- */

  function temTexto(valor) {
    return valor !== undefined && valor !== null && valor !== "";
  }

  function prepararAcao(bruta, hoje) {
    const acao = {
      etapa: bruta.etapa,
      estado: bruta.estado,
      previsto: D.dia(bruta.previsto),
      concluido: D.dia(bruta.concluido),
      responsavel: bruta.responsavel || "",
      justificativa: bruta.justificativa || "",
    };
    acao.situacao = situacaoDaAcao(acao, hoje);
    return acao;
  }

  function prepararFases(dados) {
    return (Array.isArray(dados.fases) ? dados.fases : []).map(function (fase) {
      const etapas = Array.isArray(fase.etapas) ? fase.etapas : [];
      return {
        id: fase.id,
        rotulo: fase.rotulo,
        etapas: etapas,
        ids: new Set(
          etapas.map(function (etapa) {
            return etapa.id;
          }),
        ),
      };
    });
  }

  /* As marcas do cartão, na ordem dos marcadores; o que o marcador não tem
     valor não aparece. */
  function marcasDoItem(bruto, marcadores) {
    const doDado = bruto.marcas || {};
    return marcadores.reduce(function (marcas, marcador) {
      const marca = doDado[marcador.id];
      if (marca && temTexto(marca.valor)) {
        marcas.push({ marcador: marcador, valor: String(marca.valor), papel: marca.papel || "vazio", ponto: Boolean(marca.ponto) });
      }
      return marcas;
    }, []);
  }

  /* Por etapa: as ações dela e a mais urgente. */
  function celulasDoItem(acoes) {
    const porEtapa = new Map();
    acoes.forEach(function (acao) {
      if (!porEtapa.has(acao.etapa)) porEtapa.set(acao.etapa, []);
      porEtapa.get(acao.etapa).push(acao);
    });
    const celulas = new Map();
    porEtapa.forEach(function (lista, etapa) {
      celulas.set(etapa, { acoes: lista, melhor: acaoMaisUrgente(lista) });
    });
    return celulas;
  }

  function textoDeBusca(bruto, fase, marcas, acoes) {
    const partes = [bruto.rotulo, fase.rotulo];
    marcas.forEach(function (marca) {
      partes.push(marca.valor);
    });
    acoes.forEach(function (acao) {
      partes.push(acao.justificativa, acao.responsavel);
    });
    return A.semAcento(partes.filter(temTexto).join(" "));
  }

  function prepararItem(bruto, fase, ctx) {
    const acoes = (Array.isArray(bruto.acoes) ? bruto.acoes : [])
      .map(function (acao) {
        return prepararAcao(acao, ctx.hoje);
      })
      .filter(function (acao) {
        return fase.ids.has(acao.etapa);
      });
    const classe = classeDoItem(acoes);
    const marcas = marcasDoItem(bruto, ctx.marcadores);
    const valores = {};
    marcas.forEach(function (marca) {
      valores[marca.marcador.id] = marca.valor;
    });
    return {
      rotulo: bruto.rotulo,
      fase: fase,
      faixa: bruto.faixa || "vazio",
      marcas: marcas,
      valores: valores,
      acoes: acoes,
      celulas: celulasDoItem(acoes),
      papel: classe.papel,
      progresso: classe.progresso,
      responsaveis: new Set(
        acoes
          .map(function (acao) {
            return acao.responsavel;
          })
          .filter(temTexto),
      ),
      texto: textoDeBusca(bruto, fase, marcas, acoes),
    };
  }

  function prepararItens(dados, fases, ctx) {
    const porId = new Map(
      fases.map(function (fase) {
        return [fase.id, fase];
      }),
    );
    return (Array.isArray(dados.itens) ? dados.itens : []).reduce(function (itens, bruto) {
      const fase = bruto.fase === undefined ? fases[0] : porId.get(bruto.fase);
      if (fase) itens.push(prepararItem(bruto, fase, ctx));
      else console.warn("[graficos] tabela-etapa-por-etapa: fase desconhecida: " + bruto.fase);
      return itens;
    }, []);
  }

  /* ---------- Filtros ---------- */

  function unicos(lista) {
    return Array.from(new Set(lista));
  }

  /* Cada filtro: o rótulo, as opções { valor, texto }, o teste de um projeto
     e o valor escolhido (nulo é "todos"). */
  function filtroDoStatus(ctx) {
    return {
      rotulo: ctx.rotulo("status"),
      opcoes: CLASSES.map(function (classe) {
        return { valor: classe.papel, texto: ctx.rotulo(classe.rotulo) };
      }),
      aceita: function (item, valor) {
        return item.papel === valor;
      },
      valor: null,
    };
  }

  function filtroDoMarcador(marcador, itens) {
    const valores = Array.isArray(marcador.valores)
      ? marcador.valores.map(String)
      : unicos(
          itens
            .map(function (item) {
              return item.valores[marcador.id];
            })
            .filter(temTexto),
        );
    return {
      rotulo: marcador.rotulo,
      opcoes: valores.map(function (valor) {
        return { valor: valor, texto: valor };
      }),
      aceita: function (item, valor) {
        return item.valores[marcador.id] === valor;
      },
      valor: null,
    };
  }

  function filtroDoResponsavel(ctx, itens) {
    const nomes = new Set();
    itens.forEach(function (item) {
      item.responsaveis.forEach(function (nome) {
        nomes.add(nome);
      });
    });
    return {
      rotulo: ctx.rotulo("responsavel"),
      opcoes: Array.from(nomes)
        .sort(function (a, b) {
          return a.localeCompare(b, document.documentElement.lang || "pt-BR");
        })
        .map(function (nome) {
          return { valor: nome, texto: nome };
        }),
      aceita: function (item, valor) {
        return item.responsaveis.has(valor);
      },
      valor: null,
    };
  }

  function montarFiltros(ctx, itens) {
    return [filtroDoStatus(ctx)]
      .concat(
        ctx.marcadores.map(function (marcador) {
          return filtroDoMarcador(marcador, itens);
        }),
      )
      .concat([filtroDoResponsavel(ctx, itens)]);
  }

  function seletor(ctx, filtro, aoMudar) {
    const todos = G.el("option", { value: "", texto: preencher(ctx.rotulo("filtroTodos"), { filtro: filtro.rotulo }) });
    const opcoes = filtro.opcoes.map(function (opcao) {
      return G.el("option", { value: opcao.valor, texto: opcao.texto });
    });
    const no = G.el("select", { class: "graf-acoes__filtro", "aria-label": filtro.rotulo }, [todos].concat(opcoes));
    no.addEventListener("change", function () {
      filtro.valor = no.value === "" ? null : no.value;
      no.classList.toggle("is-ativo", filtro.valor !== null);
      aoMudar();
    });
    return no;
  }

  /* ---------- Peças ---------- */

  function dataOuTraco(dia) {
    return dia === null ? SEM_DADO : D.curta(dia);
  }

  function pilula(ctx, tipo, longa) {
    const situacao = SITUACOES[tipo];
    return G.el("span", { class: "graf-acoes__pilula " + A.tom(situacao.pilula) }, [
      G.el("i", { class: "graf-acoes__ponto " + A.tom(situacao.ponto) }),
      G.el("span", { texto: ctx.rotulo(longa ? tipo + "Longa" : tipo) }),
    ]);
  }

  function linhaDeData(rotulo, dia, concluida) {
    return G.el("span", { class: "graf-acoes__linha" + (concluida ? " is-concluida" : "") }, [
      G.el("i", { texto: rotulo }),
      G.el("b", { texto: dataOuTraco(dia) }),
    ]);
  }

  function spanDoDesvio(descricao) {
    return G.el("span", { class: "graf-acoes__desvio " + A.tom(descricao.papel), texto: descricao.texto });
  }

  /* O que a célula mostra da ação (nula é a célula sem ação). */
  function conteudoDaCelula(ctx, acao) {
    const tipo = acao ? acao.situacao.tipo : "semAcao";
    const descricao = acao ? descreverDesvio(ctx, acao) : { texto: SEM_DADO, papel: "vazio" };
    const filhos = [
      linhaDeData(ctx.rotulo("previsto"), acao ? acao.previsto : null, false),
      linhaDeData(ctx.rotulo("concluido"), acao ? acao.concluido : null, true),
      pilula(ctx, tipo, false),
      spanDoDesvio(descricao),
    ];
    if (acao && acao.justificativa) filhos.push(G.el("span", { class: "graf-acoes__comentario", texto: acao.justificativa }));
    return filhos;
  }

  function celula(ctx, item, etapa) {
    const dados = item.celulas.get(etapa.id);
    if (!dados) return G.el("div", { class: "graf-acoes__celula is-vazia" }, conteudoDaCelula(ctx, null));
    const botao = G.el(
      "button",
      {
        type: "button",
        class: "graf-acoes__botao",
        title: ctx.rotulo(dados.melhor.situacao.tipo + "Longa"),
        "aria-haspopup": "dialog",
      },
      [G.el("span", { class: "sr-only", texto: etapa.rotulo + ": " })].concat(conteudoDaCelula(ctx, dados.melhor)),
    );
    botao.addEventListener("click", function () {
      ctx.abrirDetalhe(item, etapa, dados, botao);
    });
    const filhos = [botao];
    if (dados.acoes.length > 1) filhos.push(G.el("b", { class: "graf-acoes__qtd", texto: String(dados.acoes.length) }));
    return G.el("div", { class: "graf-acoes__celula" }, filhos);
  }

  function chipDaMarca(marca, faixa) {
    const filhos = [];
    if (marca.ponto) filhos.push(G.el("i", { class: "graf-acoes__ponto " + A.tom(faixa) }));
    filhos.push(G.el("i", { class: "graf-acoes__chip-rotulo", texto: marca.marcador.rotulo }));
    filhos.push(marca.valor);
    return G.el("em", { class: "graf-acoes__chip " + A.tom(marca.papel) }, filhos);
  }

  function cabecalhoDoCartao(ctx, item) {
    const filhos = [
      G.el("b", { class: "graf-acoes__nome", texto: item.rotulo }),
      G.el("em", { class: "graf-acoes__chip " + A.tom("marca"), texto: item.fase.rotulo }),
    ];
    item.marcas.forEach(function (marca) {
      filhos.push(chipDaMarca(marca, item.faixa));
    });
    const preenchimento = G.el("i");
    preenchimento.style.width = item.progresso + "%";
    filhos.push(G.el("span", { class: "graf-acoes__progresso", title: ctx.rotulo("progresso") }, [preenchimento]));
    filhos.push(G.el("span", { class: "graf-acoes__perc", texto: item.progresso + "%" }));
    return G.el("div", { class: "graf-acoes__cartao-cab" }, filhos);
  }

  function cartao(ctx, item) {
    const grade = G.el(
      "div",
      { class: "graf-acoes__grade" },
      item.fase.etapas.map(function (etapa) {
        return celula(ctx, item, etapa);
      }),
    );
    return G.el("div", { class: "graf-acoes__cartao " + A.tom(item.faixa) }, [cabecalhoDoCartao(ctx, item), grade]);
  }

  function cabecalhoDasEtapas(fase) {
    return G.el(
      "div",
      { class: "graf-acoes__colunas" },
      fase.etapas.map(function (etapa) {
        return G.el("div", { class: "graf-acoes__coluna", texto: etapa.rotulo });
      }),
    );
  }

  function contador(papel, valor, rotulo) {
    return G.el("div", { class: "graf-acoes__kpi " + A.tom(papel) }, [G.el("b", { texto: String(valor) }), G.el("span", { texto: rotulo })]);
  }

  function legenda(ctx) {
    return G.el(
      "div",
      { class: "graf-acoes__legenda" },
      LEGENDA.map(function (item) {
        return G.el("span", { class: "graf-acoes__leg" }, [G.el("i", { class: "graf-acoes__ponto " + A.tom(item[0]) }), ctx.rotulo(item[1])]);
      }),
    );
  }

  /* ---------- Detalhe ---------- */

  function dado(rotulo, valor) {
    return G.el("span", {}, [rotulo + " ", G.el("b", { texto: valor })]);
  }

  function blocoDaAcao(ctx, acao, indice) {
    const justificativa = acao.justificativa
      ? G.el("div", { class: "graf-acoes__justificativa", texto: acao.justificativa })
      : G.el("div", { class: "graf-acoes__justificativa is-vazia", texto: ctx.rotulo("semJustificativa") });
    return G.el("div", { class: "graf-acoes__acao" }, [
      G.el("div", { class: "graf-acoes__acao-cab" }, [
        G.el("b", { texto: ctx.rotulo("acao") + " " + (indice + 1) }),
        pilula(ctx, acao.situacao.tipo, true),
        spanDoDesvio(descreverDesvio(ctx, acao)),
      ]),
      justificativa,
      G.el("div", { class: "graf-acoes__dados" }, [
        dado(ctx.rotulo("responsavel"), acao.responsavel || SEM_DADO),
        dado(ctx.rotulo("prazoPrevisto"), dataOuTraco(acao.previsto)),
        dado(ctx.rotulo("conclusao"), dataOuTraco(acao.concluido)),
      ]),
    ]);
  }

  /* A linha de baixo do título: a fase, as marcas e a quantidade de ações. */
  function subtituloDoDetalhe(ctx, item, quantas) {
    const partes = [item.fase.rotulo].concat(
      item.marcas.map(function (marca) {
        return marca.marcador.rotulo + " " + marca.valor;
      }),
    );
    partes.push(preencher(ctx.rotulo("acoesNoDetalhe"), { n: quantas }));
    return partes.join(" · ");
  }

  function montarDetalhe(ctx, item, etapa, dados) {
    const fechar = G.el("button", { type: "button", class: "graf-acoes__fechar", "aria-label": ctx.rotulo("fechar"), texto: "×" });
    fechar.addEventListener("click", ctx.fecharDetalhe);
    const titulo = G.el("div", { class: "graf-acoes__m-titulo", id: ctx.idDoTitulo }, [item.rotulo + " · " + etapa.rotulo, fechar]);
    const sub = G.el("div", { class: "graf-acoes__m-sub", texto: subtituloDoDetalhe(ctx, item, dados.acoes.length) });
    const acoes = dados.acoes.map(function (acao, indice) {
      return blocoDaAcao(ctx, acao, indice);
    });
    return { fechar: fechar, filhos: [titulo, sub].concat(acoes) };
  }

  /* ---------- Montagem ---------- */

  function dadosValidos(fases) {
    return fases.length > 0 && fases.every(function (fase) {
      return fase.etapas.length > 0;
    });
  }

  function prepararContexto(dados) {
    const fases = prepararFases(dados);
    const contexto = {
      rotulo: A.rotulador(dados, ROTULOS),
      hoje: D.dia(dados.hoje),
      marcadores: Array.isArray(dados.marcadores) ? dados.marcadores : [],
      fases: fases,
      idDoTitulo: "graf-acoes-detalhe-" + String(Math.random()).slice(2, 9),
    };
    contexto.itens = prepararItens(dados, fases, contexto);
    contexto.filtros = montarFiltros(contexto, contexto.itens);
    return contexto;
  }

  G.registrar("tabela-etapa-por-etapa", function (host, dados) {
    const ctx = prepararContexto(dados);
    if (!dadosValidos(ctx.fases) || !ctx.itens.length) {
      G.mostrarMensagem(host, G.rotulo(dados, "vazio"));
      return null;
    }
    const estado = { fase: 0, busca: "" };
    let aberto = null;

    const titulo = G.el("div", { class: "graf-acoes__titulos" }, [
      G.el("div", { class: "graf-acoes__titulo", texto: dados.titulo || "" }),
      dados.subtitulo ? G.el("div", { class: "graf-acoes__subtitulo", texto: dados.subtitulo }) : null,
    ].filter(Boolean));
    const contadores = G.el("div", { class: "graf-acoes__kpis" });
    const abas = ctx.fases.map(function (fase, indice) {
      const quantos = G.el("i");
      const botao = G.el("button", { type: "button", class: "graf-acoes__aba", "aria-pressed": "false" }, [fase.rotulo, quantos]);
      botao.addEventListener("click", function () {
        estado.fase = indice;
        desenhar();
      });
      return { botao: botao, quantos: quantos };
    });
    const grupoDeAbas = G.el(
      "div",
      { class: "graf-acoes__abas", role: "group", "aria-label": dados.titulo || null, hidden: ctx.fases.length < 2 },
      abas.map(function (aba) {
        return aba.botao;
      }),
    );
    const cabecalho = G.el("div", { class: "graf-acoes__cab" }, [titulo, contadores, grupoDeAbas]);

    const busca = G.el("input", {
      type: "search",
      class: "graf-acoes__busca",
      placeholder: ctx.rotulo("buscar"),
      "aria-label": ctx.rotulo("buscar"),
      autocomplete: "off",
    });
    busca.addEventListener("input", function () {
      estado.busca = A.semAcento(busca.value.trim());
      desenhar();
    });
    const contagem = G.el("div", { class: "graf-acoes__contagem" });
    const barra = G.el(
      "div",
      { class: "graf-acoes__filtros" },
      [busca]
        .concat(
          ctx.filtros.map(function (filtro) {
            return seletor(ctx, filtro, desenhar);
          }),
        )
        .concat([contagem]),
    );

    const corpo = G.el("div", { class: "graf-acoes__corpo" });
    const resumo = G.el("div", { class: "graf-acoes__resumo" });
    const rodape = G.el("div", { class: "graf-acoes__rodape" }, [legenda(ctx), resumo]);
    const sombra = G.el("div", { class: "graf-acoes__sombra", hidden: true });
    const raiz = G.el("div", { class: "graf-acoes", role: "group", "aria-label": dados.titulo || null }, [cabecalho, barra, corpo, rodape, sombra]);
    const camadas = [cabecalho, barra, corpo, rodape];

    function aceita(item) {
      const passaNosFiltros = ctx.filtros.every(function (filtro) {
        return filtro.valor === null || filtro.aceita(item, filtro.valor);
      });
      return passaNosFiltros && (estado.busca === "" || item.texto.includes(estado.busca));
    }

    function daFase(indice) {
      return ctx.itens.filter(function (item) {
        return item.fase === ctx.fases[indice] && aceita(item);
      });
    }

    function contarCelulas(selecionados) {
      let com = 0;
      let sem = 0;
      selecionados.forEach(function (item) {
        item.fase.etapas.forEach(function (etapa) {
          const dadosDaCelula = item.celulas.get(etapa.id);
          if (dadosDaCelula && dadosDaCelula.melhor.situacao.tipo !== "semAcao") com += 1;
          else sem += 1;
        });
      });
      return { com: com, sem: sem };
    }

    function atualizarCabecalhos(selecionados) {
      const total = ctx.itens.filter(function (item) {
        return item.fase === ctx.fases[estado.fase];
      }).length;
      const porClasse = CLASSES.map(function (classe) {
        return selecionados.filter(function (item) {
          return item.papel === classe.papel;
        }).length;
      });
      contadores.replaceChildren(
        contador("vazio", selecionados.length, ctx.rotulo("projetos")),
        ...CLASSES.map(function (classe, i) {
          return contador(classe.papel, porClasse[i], ctx.rotulo(classe.rotulo));
        }),
      );
      contagem.replaceChildren(G.el("b", { texto: String(selecionados.length) }), "/" + total);
      abas.forEach(function (aba, i) {
        aba.botao.classList.toggle("is-ativa", i === estado.fase);
        aba.botao.setAttribute("aria-pressed", i === estado.fase ? "true" : "false");
        aba.quantos.textContent = String(daFase(i).length);
      });
    }

    function atualizarResumo(selecionados) {
      const fase = ctx.fases[estado.fase];
      const celulas = contarCelulas(selecionados);
      resumo.textContent = preencher(ctx.rotulo("resumo"), { fase: fase.rotulo, com: celulas.com, sem: celulas.sem, etapas: fase.etapas.length });
    }

    function desenhar() {
      const fase = ctx.fases[estado.fase];
      const selecionados = daFase(estado.fase);
      corpo.style.setProperty("--n", String(fase.etapas.length));
      const lista = selecionados.length
        ? G.el(
            "div",
            { class: "graf-acoes__lista" },
            selecionados.map(function (item) {
              return cartao(ctx, item);
            }),
          )
        : G.el("div", { class: "graf-acoes__vazio" }, [G.el("i"), G.el("span", { texto: ctx.rotulo("semProjetos") })]);
      corpo.replaceChildren(cabecalhoDasEtapas(fase), lista);
      corpo.scrollTop = 0;
      atualizarCabecalhos(selecionados);
      atualizarResumo(selecionados);
    }

    function trancar(travar) {
      camadas.forEach(function (no) {
        no.toggleAttribute("inert", travar);
      });
    }

    ctx.fecharDetalhe = function () {
      if (!aberto) return;
      const origem = aberto.origem;
      aberto = null;
      sombra.hidden = true;
      sombra.replaceChildren();
      trancar(false);
      if (origem.isConnected) origem.focus();
    };

    ctx.abrirDetalhe = function (item, etapa, dadosDaCelula, origem) {
      const detalhe = montarDetalhe(ctx, item, etapa, dadosDaCelula);
      const dialogo = G.el(
        "div",
        { class: "graf-acoes__dialogo", role: "dialog", "aria-modal": "true", "aria-labelledby": ctx.idDoTitulo },
        detalhe.filhos,
      );
      sombra.replaceChildren(dialogo);
      sombra.hidden = false;
      trancar(true);
      aberto = { origem: origem };
      detalhe.fechar.focus();
    };

    sombra.addEventListener("click", function (evento) {
      if (evento.target === sombra) ctx.fecharDetalhe();
    });
    raiz.addEventListener("keydown", function (evento) {
      if (evento.key === "Escape" && aberto) {
        evento.stopPropagation();
        ctx.fecharDetalhe();
      }
    });
    host.replaceChildren(raiz);
    desenhar();
    return {
      destruir: function () {
        aberto = null;
      },
    };
  });

  G.tabelaEtapaPorEtapa = { situacaoDaAcao: situacaoDaAcao, acaoMaisUrgente: acaoMaisUrgente, classeDoItem: classeDoItem };
})();
