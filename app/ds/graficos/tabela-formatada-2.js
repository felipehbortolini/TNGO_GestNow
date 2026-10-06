/* ============================================================
   graficos/tabela-formatada-2.js — Tabela Formata 2

   Porte de "Tabela Formata 2.html" (docs/referencia/graficos/), o mapa de
   funções: uma linha por item (portfólio), um bloco de medidas para cada
   grupo (função), com o previsto, o realizado, o remanescente (o selo que
   avisa o que falta) e o contratado. À esquerda de cada linha, o ponto de
   saúde e uma barrinha com o avanço (realizado sobre previsto); no alto,
   a linha de Total geral dentro do cabeçalho; à direita, o bloco Total de
   cada linha. Passar o ponteiro realça a linha. Serve as tabelas detalhadas
   (mapa de controle, EAP).

   Contrato dos dados (data-dados):
     {
       "titulo": "Mapa de funções",
       "primeira_coluna": "Portfólio",
       "grupos": [{ "id": "pc", "rotulo": "Project Control" }],
       "medidas": [
         { "id": "previsto", "rotulo": "Prev", "tipo": "previsto" },
         { "id": "realizado", "rotulo": "Real", "tipo": "realizado" },
         { "id": "saldo", "rotulo": "Rem", "tipo": "saldo" },
         { "id": "contratado", "rotulo": "Contr." }
       ],
       "total": { "grupo": "Total", "linha": "Total geral" },
       "faixas_progresso": [{ "de": 100, "papel": "ok" }, { "de": 0, "papel": "atencao" }],
       "faixas_saude": [{ "de": 3, "papel": "atencao" }, { "de": 0, "papel": "ok" }],
       "linhas": [{ "id": "refinaria", "rotulo": "Refinaria", "subtitulo": null,
                    "valores": { "pc": { "previsto": 6, "realizado": 6, "contratado": 0 } } }]
     }
   O servidor manda previsto, realizado e as demais medidas por grupo; o
   saldo (`tipo: "saldo"`, previsto menos realizado), os totais por linha e
   por coluna e o avanço saem aqui. O selo do saldo fica laranja se falta
   (positivo), verde se fecha (zero) e vermelho se passou (negativo).
   `total` acrescenta o grupo Total e a linha Total geral. As faixas, que são
   regra do projeto, vêm do servidor: `faixas_progresso` pinta a barrinha
   pelo avanço em % e `faixas_saude` o ponto pelo saldo total, ambas pelo
   maior `de` que o valor alcança. Sem elas, a barrinha é da cor da marca e
   não há ponto.

     <div data-grafico="tabela-formatada-2" data-dados='{{ grafico | tojson }}'></div>

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;
  const A = G.apoio;

  const ROTULOS = { total: "Total", totalGeral: "Total geral", primeiraColuna: "" };
  const ATRASO_ENTRE_LINHAS_MS = 45;
  const LARGURA_DA_PRIMEIRA_COLUNA = 12;

  /* ---------- Contas ---------- */

  function quantidade(valor) {
    return Number.isFinite(valor) ? valor : 0;
  }

  /* Soma de cada medida (que não é saldo) sobre uma lista de blocos
     { medida: valor }. */
  function somarBlocos(blocos, medidas) {
    const soma = {};
    medidas.forEach(function (medida) {
      soma[medida.id] = blocos.reduce(function (total, bloco) {
        return total + quantidade(bloco[medida.id]);
      }, 0);
    });
    return soma;
  }

  /* O saldo de um bloco: previsto menos realizado. Sem as duas medidas no
     contrato, o saldo é o que o servidor mandou. */
  function comSaldo(bloco, medidas) {
    const previsto = medidas.find(function (medida) {
      return medida.tipo === "previsto";
    });
    const realizado = medidas.find(function (medida) {
      return medida.tipo === "realizado";
    });
    const saldo = medidas.find(function (medida) {
      return medida.tipo === "saldo";
    });
    const pronto = Object.assign({}, bloco);
    if (saldo && previsto && realizado) pronto[saldo.id] = quantidade(bloco[previsto.id]) - quantidade(bloco[realizado.id]);
    return pronto;
  }

  /* O papel da faixa de maior `de` que o valor alcança; nulo se nenhuma. */
  function papelPeloLimite(faixas, valor) {
    if (!Array.isArray(faixas)) return null;
    let escolhida = null;
    faixas.forEach(function (faixa) {
      if (valor >= faixa.de && (escolhida === null || faixa.de > escolhida.de)) escolhida = faixa;
    });
    return escolhida ? escolhida.papel : null;
  }

  /* Avanço da linha: realizado sobre previsto, de 0 a 100, inteiro. */
  function avancoEmPercentual(previsto, realizado) {
    return previsto > 0 ? Math.min(100, Math.round((100 * realizado) / previsto)) : 0;
  }

  function papelDoSaldo(saldo) {
    if (saldo > 0) return "atencao";
    return saldo === 0 ? "ok" : "erro";
  }

  /* ---------- Modelo ---------- */

  function tipoDa(medidas, tipo) {
    return medidas.find(function (medida) {
      return medida.tipo === tipo;
    });
  }

  /* Cada linha ganha o saldo por grupo, o bloco Total, o avanço e os totais
     de previsto, realizado e saldo que as faixas usam. */
  function prepararLinha(linha, ctx) {
    const blocos = {};
    ctx.grupos.forEach(function (grupo) {
      blocos[grupo.id] = comSaldo((linha.valores || {})[grupo.id] || {}, ctx.medidas);
    });
    const lista = ctx.grupos.map(function (grupo) {
      return blocos[grupo.id];
    });
    const total = comSaldo(somarBlocos(lista, ctx.medidas), ctx.medidas);
    const previsto = ctx.previsto ? total[ctx.previsto.id] : 0;
    const realizado = ctx.realizado ? total[ctx.realizado.id] : 0;
    const saldo = ctx.saldo ? total[ctx.saldo.id] : 0;
    return {
      rotulo: linha.rotulo,
      subtitulo: linha.subtitulo,
      blocos: blocos,
      total: total,
      avanco: avancoEmPercentual(previsto, realizado),
      saldo: saldo,
    };
  }

  /* A linha Total geral: a soma das linhas, grupo a grupo. */
  function totalGeral(linhas, ctx) {
    const geral = {};
    ctx.grupos.forEach(function (grupo) {
      const blocos = linhas.map(function (linha) {
        return linha.blocos[grupo.id];
      });
      geral[grupo.id] = comSaldo(somarBlocos(blocos, ctx.medidas), ctx.medidas);
    });
    geral.total = comSaldo(
      somarBlocos(
        linhas.map(function (linha) {
          return linha.total;
        }),
        ctx.medidas,
      ),
      ctx.medidas,
    );
    return geral;
  }

  /* ---------- Células ---------- */

  function valorDaMedida(ctx, medida, bloco, inicioDeGrupo) {
    const numero = quantidade(bloco[medida.id]);
    const classe = "graf-tabela2__valor" + (medida.tipo ? " is-" + medida.tipo : "") + (inicioDeGrupo ? " is-inicio-de-grupo" : "");
    const texto = G.fmt.numero(numero, 0);
    if (medida.tipo === "saldo") {
      return G.el("td", { class: classe }, [G.el("span", { class: "graf-tabela2__selo " + A.tom(papelDoSaldo(numero)), texto: texto })]);
    }
    return G.el("td", { class: classe, texto: texto });
  }

  function celulasDoBloco(ctx, bloco) {
    return ctx.medidas.map(function (medida, i) {
      return valorDaMedida(ctx, medida, bloco, i === 0);
    });
  }

  function celulaDaPrimeiraColuna(ctx, linha) {
    const papelDaSaude = papelPeloLimite(ctx.dados.faixas_saude, linha.saldo);
    const papelDaBarra = papelPeloLimite(ctx.dados.faixas_progresso, linha.avanco) || "marca";
    const nomes = [G.el("span", { class: "graf-tabela2__nome", texto: linha.rotulo })];
    if (linha.subtitulo) nomes.push(G.el("span", { class: "graf-tabela2__subtitulo", texto: linha.subtitulo }));
    const identificacao = [];
    if (papelDaSaude) identificacao.push(G.el("span", { class: "graf-tabela2__ponto " + A.tom(papelDaSaude) }));
    identificacao.push(G.el("span", { class: "graf-tabela2__nomes" }, nomes));
    const preenchimento = G.el("i", { class: A.tom(papelDaBarra) });
    preenchimento.style.width = linha.avanco + "%";
    return G.el("td", { class: "graf-tabela2__primeira" }, [
      G.el("div", { class: "graf-tabela2__identificacao" }, identificacao),
      G.el("div", { class: "graf-tabela2__avanco", title: linha.avanco + "%" }, [preenchimento]),
    ]);
  }

  function linhaDaTabela(ctx, linha, indice) {
    const celulas = [celulaDaPrimeiraColuna(ctx, linha)];
    ctx.grupos.forEach(function (grupo) {
      celulas.push(...celulasDoBloco(ctx, linha.blocos[grupo.id]));
    });
    if (ctx.dados.total) celulas.push(...celulasDoBloco(ctx, linha.total));
    const tr = G.el("tr", { class: "graf-tabela2__linha" }, celulas);
    tr.style.setProperty("--graf-atraso", indice * ATRASO_ENTRE_LINHAS_MS + "ms");
    return tr;
  }

  /* ---------- Cabeçalho ---------- */

  function gruposDoCabecalho(ctx) {
    const lista = ctx.grupos.map(function (grupo) {
      return grupo.rotulo;
    });
    if (ctx.dados.total) lista.push(ctx.dados.total.grupo || ctx.rotulo("total"));
    return lista;
  }

  function cabecalho(ctx, geral) {
    const nomes = gruposDoCabecalho(ctx);
    const primeira = G.el("tr", { class: "graf-tabela2__grupos" }, [
      G.el("th", { class: "graf-tabela2__primeira-coluna", texto: ctx.dados.primeira_coluna || ctx.rotulo("primeiraColuna") }),
    ].concat(
      nomes.map(function (nome) {
        return G.el("th", { class: "is-inicio-de-grupo", colspan: ctx.medidas.length, texto: nome });
      }),
    ));
    const segunda = G.el("tr", { class: "graf-tabela2__medidas" }, [G.el("th")].concat(
      nomes.reduce(function (celulas) {
        return celulas.concat(
          ctx.medidas.map(function (medida, i) {
            return G.el("th", { class: i === 0 ? "is-inicio-de-grupo" : null, texto: medida.rotulo });
          }),
        );
      }, []),
    ));
    const linhas = [primeira, segunda];
    if (geral) linhas.push(linhaDoTotalGeral(ctx, geral));
    return G.el("thead", {}, linhas);
  }

  function linhaDoTotalGeral(ctx, geral) {
    const celulas = [G.el("td", { texto: ctx.dados.total.linha || ctx.rotulo("totalGeral") })];
    ctx.grupos.forEach(function (grupo) {
      celulas.push(...totaisDoBloco(ctx, geral[grupo.id]));
    });
    celulas.push(...totaisDoBloco(ctx, geral.total));
    return G.el("tr", { class: "graf-tabela2__total" }, celulas);
  }

  function totaisDoBloco(ctx, bloco) {
    return ctx.medidas.map(function (medida, i) {
      return G.el("td", { class: i === 0 ? "is-inicio-de-grupo" : null, texto: G.fmt.numero(quantidade(bloco[medida.id]), 0) });
    });
  }

  /* As colunas dividem o resto da largura por igual. */
  function colunas(ctx) {
    const blocos = ctx.grupos.length + (ctx.dados.total ? 1 : 0);
    const quantas = blocos * ctx.medidas.length;
    const cada = (100 - LARGURA_DA_PRIMEIRA_COLUNA) / quantas;
    const lista = [G.el("col")];
    lista[0].style.width = LARGURA_DA_PRIMEIRA_COLUNA + "%";
    for (let i = 0; i < quantas; i++) {
      const coluna = G.el("col");
      coluna.style.width = cada.toFixed(3) + "%";
      lista.push(coluna);
    }
    return G.el("colgroup", {}, lista);
  }

  /* ---------- Montagem ---------- */

  G.registrar("tabela-formatada-2", function (host, dados) {
    const grupos = Array.isArray(dados.grupos) ? dados.grupos : [];
    const medidas = Array.isArray(dados.medidas) ? dados.medidas : [];
    const brutas = Array.isArray(dados.linhas) ? dados.linhas : [];
    if (!grupos.length || !medidas.length || !brutas.length) {
      G.mostrarMensagem(host, G.rotulo(dados, "vazio"));
      return null;
    }
    const ctx = {
      dados: dados,
      grupos: grupos,
      medidas: medidas,
      rotulo: A.rotulador(dados, ROTULOS),
      previsto: tipoDa(medidas, "previsto"),
      realizado: tipoDa(medidas, "realizado"),
      saldo: tipoDa(medidas, "saldo"),
    };
    const linhas = brutas.map(function (linha) {
      return prepararLinha(linha, ctx);
    });
    const corpo = G.el(
      "tbody",
      {},
      linhas.map(function (linha, i) {
        return linhaDaTabela(ctx, linha, i);
      }),
    );
    const tabela = G.el("table", { class: "graf-tabela2__tabela" }, [colunas(ctx), cabecalho(ctx, dados.total ? totalGeral(linhas, ctx) : null), corpo]);
    host.replaceChildren(G.el("div", { class: "graf-tabela2", role: "group", "aria-label": dados.titulo }, [G.el("div", { class: "graf-tabela2__rolagem" }, [tabela])]));
    return null;
  });

  G.tabelaFormatada2 = { comSaldo: comSaldo, papelPeloLimite: papelPeloLimite, avancoEmPercentual: avancoEmPercentual, papelDoSaldo: papelDoSaldo };
})();
