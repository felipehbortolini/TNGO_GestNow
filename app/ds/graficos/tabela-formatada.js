/* ============================================================
   graficos/tabela-formatada.js — Tabela formatada

   Porte de "Tabela formatada.html" (docs/referencia/graficos/): uma tabela
   larga com a busca no alto (com a contagem), o cabeçalho em dois níveis
   (grupos de colunas e colunas), pílulas de categoria que mudam de cor por
   valor, horas em H:MM coloridas por faixa, percentuais com fundo de mapa de
   calor, a coluna de total que avisa quando não fecha, a linha achada pela
   busca em destaque e o rodapé "Exibindo X de Y registros". As linhas
   entram em sequência. Serve as tabelas detalhadas (mapa de controle, EAP).

   Contrato dos dados (data-dados):
     {
       "titulo": "Rateio de colaboradores",
       "rodape": "Rateio de colaboradores · Med Parc",
       "grupos": [{ "rotulo": "Dados de medição", "colunas": 6 },
                  { "rotulo": "Total", "colunas": 1, "total": true }],
       "colunas": [
         { "id": "nome", "rotulo": "Colaborador" },
         { "id": "portfolio", "rotulo": "Portfólio", "tipo": "categoria" },
         { "id": "horas", "rotulo": "Horas em projeto", "tipo": "hhmm",
           "faixas": [{ "ate": 6000, "papel": "atencao" }, { "papel": "neutro" }] },
         { "id": "refinaria", "rotulo": "Refinaria", "tipo": "percentual" },
         { "id": "total", "rotulo": "Total", "tipo": "percentual", "esperado": 100 }
       ],
       "linhas": [{ "nome": "Ana Souza", "portfolio": "Refinaria",
                    "horas": 8520, "refinaria": 60, "total": 100 }]
     }
   `grupos` é opcional e cada um cobre as `colunas` seguintes; a divisa entre
   grupos sai daí. Tipos de coluna: `texto` (padrão), `categoria` (pílula; a
   cor vem da ordem do primeiro aparecimento, ou de `tons`: { "valor":
   "papel" }), `hhmm` (o valor em minutos, escrito H:MM; `faixas` dá o papel
   de cor pelo primeiro `ate` maior que o valor, sem faixa vale `papel`),
   `percentual` (de 0 a 100; zero e vazio viram "—"; o fundo é um mapa de
   calor) e `numero` (`casas`, `unidade`). Uma coluna com `esperado` é a de
   total: igual ao esperado fica no verde escuro; abaixo, em aviso; acima,
   em vermelho. A linha é um objeto com um valor por `id` de coluna. Os
   limites das faixas vêm dos parâmetros do projeto, não daqui.

     <div data-grafico="tabela-formatada" data-dados='{{ grafico | tojson }}'></div>

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;
  const A = G.apoio;

  const ROTULOS = {
    buscar: "Pesquisar...",
    exibindo: "Exibindo {visiveis} de {total} registros",
    semResultados: "Nenhum registro encontrado.",
  };
  const TONS_DAS_CATEGORIAS = ["marca", "info", "atencao", "ok", "comprometido", "alerta", "neutro"];
  const MINUTOS_POR_HORA = 60;
  const ATRASO_ENTRE_LINHAS_MS = 18;
  const LINHAS_COM_ATRASO = 30;
  /* O fundo do mapa de calor vai de 12% (valor pequeno) a 80% (valor cheio). */
  const CALOR_MINIMO = 0.12;
  const CALOR_MAXIMO = 0.8;
  const PESO_DO_CALOR = 0.68;
  const CALOR_DO_EXCESSO = 0.25;
  const PESO_DO_EXCESSO = 1.5;
  /* A partir desta fração o fundo escurece o bastante para o texto virar branco. */
  const FRACAO_DO_TEXTO_CLARO = 0.55;

  /* ---------- Contas ---------- */

  /* 8520 minutos viram "142:00". */
  function horasEMinutos(minutos) {
    const total = Math.round(minutos);
    const resto = total % MINUTOS_POR_HORA;
    return Math.floor(total / MINUTOS_POR_HORA) + ":" + String(resto).padStart(2, "0");
  }

  /* O papel de cor de um valor pelas faixas: a primeira cujo `ate` é maior
     que o valor; a última (sem `ate`) pega o resto. */
  function papelDaFaixa(faixas, valor, padrao) {
    if (!Array.isArray(faixas) || !faixas.length) return padrao;
    const achada = faixas.find(function (faixa) {
      return !Number.isFinite(faixa.ate) || valor < faixa.ate;
    });
    return achada ? achada.papel : padrao;
  }

  /* A força do fundo de um percentual, de 0 a 0,8: de 12% a 80% até o valor
     cheio e, passando de 100%, uma subida mais íngreme (o excesso). */
  function intensidadeDoCalor(fracao) {
    if (fracao > 1) return Math.min(CALOR_DO_EXCESSO + (fracao - 1) * PESO_DO_EXCESSO, CALOR_MAXIMO);
    return Math.min(CALOR_MINIMO + fracao * PESO_DO_CALOR, CALOR_MAXIMO);
  }

  function ehNumero(valor) {
    return Number.isFinite(valor);
  }

  /* ---------- Colunas ---------- */

  /* A ordem do primeiro aparecimento de cada valor dá a cor da categoria,
     salvo a que a coluna fixa em `tons`. */
  function tonsDaCategoria(coluna, linhas) {
    const tons = new Map();
    linhas.forEach(function (linha) {
      const valor = linha[coluna.id];
      if (valor === undefined || valor === null || tons.has(valor)) return;
      const fixo = coluna.tons ? coluna.tons[valor] : null;
      tons.set(valor, fixo || TONS_DAS_CATEGORIAS[tons.size % TONS_DAS_CATEGORIAS.length]);
    });
    return tons;
  }

  function prepararColunas(dados) {
    const linhas = dados.linhas || [];
    return (dados.colunas || []).map(function (coluna) {
      const pronta = Object.assign({ tipo: "texto" }, coluna);
      if (pronta.tipo === "categoria") pronta.tonsPorValor = tonsDaCategoria(coluna, linhas);
      return pronta;
    });
  }

  /* Quais colunas abrem um grupo (ganham a divisa à esquerda), com a do
     primeiro grupo de fora. */
  function inicioDosGrupos(dados) {
    const inicios = new Set();
    let posicao = 0;
    (dados.grupos || []).forEach(function (grupo, i) {
      if (i > 0) inicios.add(posicao);
      posicao += Number.isInteger(grupo.colunas) ? grupo.colunas : 1;
    });
    return inicios;
  }

  /* ---------- Células ---------- */

  function pilula(texto, papel, classe) {
    return G.el("span", { class: classe + " " + A.tom(papel), texto: texto });
  }

  function semValor(valor) {
    return valor === undefined || valor === null || valor === "";
  }

  function casasDe(coluna, padrao) {
    return Number.isInteger(coluna.casas) ? coluna.casas : padrao;
  }

  const TEXTO_POR_TIPO = {
    hhmm: function (_coluna, valor) {
      if (semValor(valor)) return "";
      return ehNumero(valor) ? horasEMinutos(valor) : String(valor);
    },
    numero: function (coluna, valor) {
      if (semValor(valor)) return "";
      return ehNumero(valor) ? G.fmt.numero(valor, casasDe(coluna, 0)) + (coluna.unidade || "") : String(valor);
    },
    percentual: function (coluna, valor) {
      if (!ehNumero(valor) || valor <= 0) return "—";
      return G.fmt.numero(valor, casasDe(coluna, 1)) + "%";
    },
  };

  function textoDaCelula(coluna, valor) {
    if (Object.hasOwn(TEXTO_POR_TIPO, coluna.tipo)) return TEXTO_POR_TIPO[coluna.tipo](coluna, valor);
    return semValor(valor) ? "" : String(valor);
  }

  /* Como o total está em relação ao esperado: abaixo avisa, acima passa,
     igual fecha. Sem `esperado` a coluna não é de total. */
  function estadoDoTotal(valor, esperado) {
    if (!ehNumero(esperado)) return null;
    if (valor < esperado) return "aviso";
    return valor > esperado ? "excesso" : "total";
  }

  /* O percentual vira uma pílula com o fundo do mapa de calor. A coluna com
     `esperado` é a de total: o que não fecha avisa, o que passa fica vermelho. */
  function celulaDePercentual(coluna, valor) {
    const no = G.el("span", { class: "graf-tabela__perc", texto: textoDaCelula(coluna, valor) });
    if (!ehNumero(valor) || valor <= 0) {
      no.classList.add("is-vazio");
      return no;
    }
    const estado = estadoDoTotal(valor, coluna.esperado);
    if (estado) no.classList.add("is-" + estado);
    if (estado === "aviso") return no;
    const fracao = valor / 100;
    no.style.setProperty("--intensidade", String(Math.round(intensidadeDoCalor(fracao) * 100)));
    if (fracao > FRACAO_DO_TEXTO_CLARO) no.classList.add("is-forte");
    return no;
  }

  function celulaDaHora(coluna, valor) {
    const texto = textoDaCelula(coluna, valor);
    if (!texto) return texto;
    const papel = ehNumero(valor) ? papelDaFaixa(coluna.faixas, valor, coluna.papel || "neutro") : "neutro";
    return pilula(texto, papel, "graf-tabela__hora");
  }

  function conteudoDaCelula(coluna, valor) {
    if (coluna.tipo === "categoria") {
      const texto = textoDaCelula(coluna, valor);
      return texto ? pilula(texto, coluna.tonsPorValor.get(valor), "graf-tabela__categoria") : "";
    }
    if (coluna.tipo === "hhmm") return celulaDaHora(coluna, valor);
    if (coluna.tipo === "percentual") return celulaDePercentual(coluna, valor);
    return textoDaCelula(coluna, valor);
  }

  /* ---------- Linhas ---------- */

  /* Cada célula leva o tipo da coluna (graf-tabela__td-texto, -percentual...):
     é por ele que o CSS deixa o texto quebrar a linha e dá ao percentual o
     recuo menor do original. */
  function celulasDaLinha(linha, ctx) {
    return ctx.colunas.map(function (coluna, i) {
      const classe = "graf-tabela__td-" + coluna.tipo + (ctx.inicios.has(i) ? " is-inicio-de-grupo" : "");
      const td = G.el("td", { class: classe });
      td.append(conteudoDaCelula(coluna, linha[coluna.id]));
      return td;
    });
  }

  function linhaDaTabela(linha, indice, ctx) {
    const tr = G.el("tr", { class: "graf-tabela__linha" }, celulasDaLinha(linha, ctx));
    tr.style.setProperty("--graf-atraso", Math.min(indice, LINHAS_COM_ATRASO) * ATRASO_ENTRE_LINHAS_MS + "ms");
    const texto = A.semAcento(
      ctx.colunas
        .map(function (coluna) {
          return textoDaCelula(coluna, linha[coluna.id]);
        })
        .join(" "),
    );
    return { tr: tr, texto: texto };
  }

  /* ---------- Cabeçalho e rodapé ---------- */

  function cabecalhoDosGrupos(dados) {
    const grupos = dados.grupos || [];
    if (!grupos.length) return null;
    return G.el(
      "tr",
      { class: "graf-tabela__grupos" },
      grupos.map(function (grupo, i) {
        return G.el("th", {
          class: "graf-tabela__grupo" + (grupo.total ? " is-total" : "") + (i > 0 ? " is-inicio-de-grupo" : ""),
          colspan: Number.isInteger(grupo.colunas) ? grupo.colunas : 1,
          texto: grupo.rotulo,
        });
      }),
    );
  }

  function cabecalhoDasColunas(ctx) {
    return G.el(
      "tr",
      { class: "graf-tabela__colunas" },
      ctx.colunas.map(function (coluna, i) {
        return G.el("th", { class: ctx.inicios.has(i) ? "is-inicio-de-grupo" : null, texto: coluna.rotulo });
      }),
    );
  }

  /* "Exibindo 9 de 9 registros": os dois números saem em destaque (negrito
     e verde), como no original. */
  function partesDoRodape(ctx, visiveis) {
    const numeros = { "{visiveis}": visiveis, "{total}": ctx.total };
    return ctx
      .rotulo("exibindo")
      .split(/(\{visiveis\}|\{total\})/)
      .map(function (parte) {
        return Object.hasOwn(numeros, parte) ? G.el("span", { texto: String(numeros[parte]) }) : parte;
      });
  }

  /* ---------- Montagem ---------- */

  G.registrar("tabela-formatada", function (host, dados) {
    const colunas = prepararColunas(dados);
    const linhas = Array.isArray(dados.linhas) ? dados.linhas : [];
    if (!colunas.length || !linhas.length) {
      G.mostrarMensagem(host, G.rotulo(dados, "vazio"));
      return null;
    }
    const ctx = { colunas: colunas, inicios: inicioDosGrupos(dados), rotulo: A.rotulador(dados, ROTULOS), total: linhas.length };
    const prontas = linhas.map(function (linha, i) {
      return linhaDaTabela(linha, i, ctx);
    });
    const cabecalho = G.el("thead", {}, [cabecalhoDosGrupos(dados), cabecalhoDasColunas(ctx)].filter(Boolean));
    const corpo = G.el(
      "tbody",
      {},
      prontas.map(function (pronta) {
        return pronta.tr;
      }),
    );
    const vazio = G.el("p", { class: "graf__vazio", hidden: true, texto: ctx.rotulo("semResultados") });
    const contagem = G.el("span", { class: "graf-tabela__contagem" });
    const busca = A.barraDeBusca(ctx.rotulo("buscar"), filtrar, "/");
    const tabela = G.el("table", { class: "graf-tabela__tabela" }, [cabecalho, corpo]);
    const rodape = G.el("div", { class: "graf-tabela__rodape" }, [
      contagem,
      dados.rodape ? G.el("span", { class: "graf-tabela__rodape-texto", texto: dados.rodape }) : null,
    ].filter(Boolean));
    const raiz = G.el("div", { class: "graf-tabela", role: "group", "aria-label": dados.titulo }, [
      busca.elemento,
      G.el("div", { class: "graf-tabela__rolagem" }, [tabela, vazio]),
      rodape,
    ]);

    function filtrar(consulta) {
      let visiveis = 0;
      prontas.forEach(function (pronta) {
        const acha = consulta === "" || pronta.texto.includes(consulta);
        pronta.tr.hidden = !acha;
        pronta.tr.classList.toggle("is-destaque", consulta !== "" && acha);
        if (acha) visiveis += 1;
      });
      vazio.hidden = visiveis > 0;
      busca.contar(visiveis, ctx.total);
      contagem.replaceChildren(...partesDoRodape(ctx, visiveis));
    }

    host.replaceChildren(raiz);
    filtrar("");
    return null;
  });

  G.tabelaFormatada = { horasEMinutos: horasEMinutos, papelDaFaixa: papelDaFaixa, intensidadeDoCalor: intensidadeDoCalor };
})();
