/* ============================================================
   graficos/tabela-quantitativos.js — Tabela Quantitativos por entregável

   Porte de "Tabela Quantitativos por entregavel.html"
   (docs/referencia/graficos/), a tabela de contagens por categoria com
   mergulho: uma linha por entregável, as colunas reunidas em grupos com o
   nome em cima, o valor de cada célula numa pílula pintada pela faixa, o
   total da linha, as colunas de medida, o total geral fixo embaixo e, ao clicar
   numa linha, a descida para os itens dela, com o caminho, o botão Voltar e a
   busca. Serve o plano de quantidades por semana e o quadro do MAS por pacote.

   Contrato dos dados (data-dados):
     {
       "titulo": "Plano de quantidades", "rotulo_linhas": "Entregável",
       "casas": 0, "unidade": "",
       "grupos": [{ "id": "set", "rotulo": "Setembro",
                    "colunas": [{ "id": "s36", "rotulo": "S36", "dica": "31/08 a 06/09" }] }],
       "coluna_total": { "rotulo": "Total" },
       "metricas": [{ "id": "itens", "rotulo": "Itens", "somar": true }],
       "linhas": [{ "id": "fund", "rotulo": "Fundações", "subtitulo": "Pacote A",
                    "valores": { "s36": 12, "s37": { "valor": 4, "id": "fund|s37" } },
                    "metricas": { "itens": 3 }, "busca": "texto a mais",
                    "filhos": [{ "id": "fund-1", "rotulo": "Bloco 1", "detalhe": {} }] }],
       "total": { "rotulo": "Total geral", "rotulo_raiz": "Entregáveis",
                  "valores": { "total": 120 }, "metricas": { "itens": 9 } },
       "faixas": { "padrao": [], "total": [] }, "legenda": [], "selecionavel": true
     }
   - O valor da célula é número, `null` ou { valor, texto, faixa, id, href }; o
     que falta soma sozinho (o pai soma os filhos, a linha soma as colunas, o
     total geral soma as linhas). A taxa e outras medidas que não são soma vêm
     prontas: em `valores`, em `linha.total` e em `total.valores` (por id de
     coluna; o total da linha é a chave `total`).
   - Faixa (ver pecas.js): tom, nível, ícone e nome por valor, vindos do servidor
     (`faixas`, uma lista ou um objeto com `padrao` e `total`). Sem faixa, a
     célula é uma pílula cinza. A cor nunca é o único sinal: a faixa leva ícone
     e nome.
   - Linha com `filhos` desce ao clicar; sem filhos, abre o `detalhe` (ver
     detalhe.js), se houver. O clique dispara grafico:selecionar com { id,
     linha, item }; quem cancela o evento assume o clique. A linha só é
     clicável com `filhos`, `detalhe` ou `selecionavel: true`.
   - Célula com `id`/`href` (ou `selecionavel: true` no topo) também dispara o
     evento, com { id, linha, coluna, valor, item }, assim como o nome do grupo
     com `selecionavel: true` ou `href`, com { id, grupo, item }.
   - `metricas` são colunas de números prontos, sem faixa; `somar: true` as soma
     no total geral.

     <div data-grafico="tabela-quantitativos" data-dados='{{ grafico | tojson }}'></div>

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;
  const P = G.pecas;
  const TIPO = "tabela-quantitativos";
  const PONTO_VAZIO = "·";

  function temFilhos(linha) {
    return Array.isArray(linha.filhos) && linha.filhos.length > 0;
  }

  function itemDe(bruto) {
    return bruto !== null && typeof bruto === "object" ? bruto : { valor: bruto };
  }

  /* ---------- Níveis e busca ---------- */

  function nivelAtual(contexto) {
    const pilha = contexto.estado.pilha;
    return pilha.length ? pilha[pilha.length - 1].filhos : contexto.dados.linhas;
  }

  function linhasFiltradas(contexto) {
    const busca = contexto.estado.busca;
    const linhas = nivelAtual(contexto);
    if (!busca) return linhas;
    return linhas.filter(function (linha) {
      return P.normalizar([linha.rotulo, linha.subtitulo, linha.busca].join(" ")).includes(busca);
    });
  }

  /* ---------- Valores ---------- */

  function valorDaColuna(linha, coluna) {
    return P.valorDaArvore(linha, function (no) {
      return no.valores ? no.valores[coluna.id] : undefined;
    });
  }

  function totalDaLinha(linha, contexto) {
    if (Number.isFinite(linha.total)) return linha.total;
    return P.somar(
      contexto.folhas
        .filter(function (coluna) {
          return coluna.somar !== false;
        })
        .map(function (coluna) {
          return P.valorDaCelula(valorDaColuna(linha, coluna));
        }),
    );
  }

  function metricaDaLinha(linha, metrica) {
    return linha.metricas ? linha.metricas[metrica.id] : undefined;
  }

  /* ---------- Células ---------- */

  function espaco(tag) {
    return G.el(tag, { class: "graf-quant__espaco", "aria-hidden": "true" });
  }

  function celulaDeValor(linha, coluna, contexto) {
    const dados = contexto.dados;
    const bruto = valorDaColuna(linha, coluna);
    const item = itemDe(bruto);
    const semValor = !Number.isFinite(item.valor) && typeof item.texto !== "string";
    if (semValor) return G.el("td", { class: "graf-quant__td is-vazio", texto: PONTO_VAZIO });
    const faixa = P.faixaDaCelula(bruto, P.conjuntoDeFaixas(dados.faixas, coluna.faixas), dados.faixas);
    const pilula = P.celula(P.textoDoValor(item, P.padroesDaColuna(coluna, dados)), faixa, { classe: "graf-quant__celula", href: item.href });
    if (P.ehSelecionavel(item, dados)) {
      const detalhe = { id: item.id, linha: linha.id, coluna: coluna.id, valor: item.valor, item: item };
      P.tornarInterativo(pilula, { host: contexto.host, tipo: TIPO, detalhe: detalhe });
    }
    return G.el("td", { class: "graf-quant__td" }, [pilula]);
  }

  /* O total usa o conjunto "total" das faixas e a formatação da coluna. */
  function celulaDeTotal(valor, padroes, dados) {
    const faixa = P.faixaDe(valor, P.conjuntoDeFaixas(dados.faixas, "total"));
    const texto = Number.isFinite(valor) ? P.textoDoValor({ valor: valor }, padroes) : PONTO_VAZIO;
    return G.el("td", { class: "graf-quant__td is-total" }, [P.celula(texto, faixa, { classe: "graf-quant__celula is-total" })]);
  }

  function celulaDeMedida(valor, metrica, dados) {
    const vazio = !Number.isFinite(valor);
    const texto = vazio ? PONTO_VAZIO : P.textoDoValor({ valor: valor }, P.padroesDaColuna(metrica, dados));
    return G.el("td", { class: "graf-quant__td is-medida" }, [G.el("span", { class: "graf-quant__medida" + (vazio ? " is-vazio" : ""), texto: texto })]);
  }

  /* ---------- Linha ---------- */

  function descer(linha, contexto) {
    contexto.estado.pilha.push(linha);
    contexto.estado.busca = "";
    contexto.ui.busca.value = "";
    contexto.redesenhar();
  }

  function acaoDaLinha(linha, contexto) {
    if (temFilhos(linha)) {
      descer(linha, contexto);
      return;
    }
    if (linha.detalhe) G.detalhe.abrir(linha.detalhe);
  }

  function nomeDaLinha(linha, contexto) {
    const filhos = [G.el("span", { class: "graf-quant__texto", texto: linha.rotulo })];
    if (linha.subtitulo) filhos.push(G.el("span", { class: "graf-quant__sub", texto: linha.subtitulo }));
    const desce = temFilhos(linha);
    if (desce) filhos.push(G.el("span", { class: "graf-quant__seta", "aria-hidden": "true" }));
    const acionavel = desce || Boolean(linha.detalhe) || linha.selecionavel === true;
    if (!acionavel) return G.el("span", { class: "graf-quant__nome" }, filhos);
    const botao = G.el("button", { type: "button", class: "graf-quant__nome is-acionavel" }, filhos);
    P.tornarInterativo(botao, {
      host: contexto.host,
      tipo: TIPO,
      detalhe: { id: linha.id, linha: linha.id, item: linha },
      aoAtivar: function () {
        acaoDaLinha(linha, contexto);
      },
    });
    return botao;
  }

  function linhaDaTabela(linha, indice, contexto) {
    const dados = contexto.dados;
    const nome = nomeDaLinha(linha, contexto);
    const acionavel = nome.tagName === "BUTTON";
    const celulas = [G.el("th", { class: "graf-quant__rotulo", scope: "row", title: linha.rotulo }, [nome])];
    (dados.grupos || []).forEach(function (grupo) {
      (grupo.colunas || []).forEach(function (coluna) {
        celulas.push(celulaDeValor(linha, coluna, contexto));
      });
      celulas.push(espaco("td"));
    });
    if (dados.coluna_total) celulas.push(celulaDeTotal(totalDaLinha(linha, contexto), dados, dados));
    (dados.metricas || []).forEach(function (metrica) {
      celulas.push(celulaDeMedida(metricaDaLinha(linha, metrica), metrica, dados));
    });
    const tr = G.el("tr", { class: "graf-quant__linha" + (acionavel ? " is-acionavel" : "") }, celulas);
    tr.style.setProperty("--atraso", Math.min(indice, 12) * 30 + "ms");
    /* O clique em qualquer ponto da linha vale o clique no nome, menos o que
       já é botão, link ou célula clicável. */
    if (acionavel) {
      tr.addEventListener("click", function (clique) {
        if (!clique.target.closest("button, a, .is-interativo")) nome.click();
      });
    }
    return tr;
  }

  /* ---------- Total geral ---------- */

  function somaDasLinhas(linhas, ler) {
    return P.somar(
      linhas.map(function (linha) {
        return P.valorDaCelula(ler(linha));
      }),
    );
  }

  /* O que o servidor mandou para o total (só na raiz) ou a soma calculada. */
  function valorDoTotal(explicitos, chave, soma) {
    const explicito = explicitos ? explicitos[chave] : undefined;
    return explicito === undefined ? soma : P.valorDaCelula(explicito);
  }

  function celulaDeMedidaDoTotal(metrica, contexto, linhas) {
    const total = contexto.dados.total;
    const naRaiz = contexto.estado.pilha.length === 0;
    const somada = metrica.somar === true ? somaDasLinhas(linhas, function (linha) {
      return metricaDaLinha(linha, metrica);
    }) : null;
    const explicitas = naRaiz && total ? total.metricas : undefined;
    return celulaDeMedida(valorDoTotal(explicitas, metrica.id, somada), metrica, contexto.dados);
  }

  function linhaDoTotal(contexto) {
    const dados = contexto.dados;
    const linhas = nivelAtual(contexto);
    const total = dados.total;
    const explicitos = contexto.estado.pilha.length === 0 && total ? total.valores : undefined;
    const rotulo = total && total.rotulo ? total.rotulo : P.rotulo(dados, "total");
    const celulas = [G.el("th", { class: "graf-quant__rotulo is-total", scope: "row", texto: rotulo })];
    (dados.grupos || []).forEach(function (grupo) {
      (grupo.colunas || []).forEach(function (coluna) {
        const soma = somaDasLinhas(linhas, function (linha) {
          return valorDaColuna(linha, coluna);
        });
        celulas.push(celulaDeTotal(valorDoTotal(explicitos, coluna.id, soma), P.padroesDaColuna(coluna, dados), dados));
      });
      celulas.push(espaco("td"));
    });
    if (dados.coluna_total) {
      const geral = somaDasLinhas(linhas, function (linha) {
        return totalDaLinha(linha, contexto);
      });
      celulas.push(celulaDeTotal(valorDoTotal(explicitos, "total", geral), dados, dados));
    }
    (dados.metricas || []).forEach(function (metrica) {
      celulas.push(celulaDeMedidaDoTotal(metrica, contexto, linhas));
    });
    return G.el("tr", { class: "graf-quant__linha is-total-linha" }, celulas);
  }

  /* ---------- Cabeçalho ---------- */

  function cabecalhoDoGrupo(grupo, contexto) {
    const texto = G.el("span", { class: "graf-quant__grupo-texto", texto: grupo.rotulo });
    const acionavel = Boolean(grupo.href) || grupo.selecionavel === true;
    const conteudo = acionavel ? G.el("button", { type: "button", class: "graf-quant__grupo-botao" }, [texto]) : texto;
    if (acionavel) {
      P.tornarInterativo(conteudo, { host: contexto.host, tipo: TIPO, detalhe: { id: grupo.id, grupo: grupo.id, item: grupo } });
    }
    return G.el("th", { class: "graf-quant__th is-grupo", scope: "colgroup", colspan: (grupo.colunas || []).length }, [conteudo]);
  }

  function cabecalhoDaTabela(contexto) {
    const dados = contexto.dados;
    const primeira = [G.el("th", { class: "graf-quant__th is-canto", scope: "col", rowspan: 2, texto: dados.rotulo_linhas || "" })];
    const segunda = [];
    (dados.grupos || []).forEach(function (grupo) {
      primeira.push(cabecalhoDoGrupo(grupo, contexto));
      primeira.push(G.el("th", { class: "graf-quant__espaco", scope: "col", rowspan: 2, "aria-hidden": "true" }));
      (grupo.colunas || []).forEach(function (coluna) {
        segunda.push(G.el("th", { class: "graf-quant__th is-sub", scope: "col", title: coluna.dica || coluna.rotulo, texto: coluna.rotulo }));
      });
    });
    if (dados.coluna_total) {
      primeira.push(G.el("th", { class: "graf-quant__th is-medida", scope: "col", rowspan: 2, texto: dados.coluna_total.rotulo || P.rotulo(dados, "total") }));
    }
    (dados.metricas || []).forEach(function (metrica) {
      primeira.push(G.el("th", { class: "graf-quant__th is-medida", scope: "col", rowspan: 2, texto: metrica.rotulo }));
    });
    return G.el("thead", {}, [G.el("tr", { class: "graf-quant__h1" }, primeira), G.el("tr", { class: "graf-quant__h2" }, segunda)]);
  }

  /* ---------- Caminho e busca ---------- */

  function botaoDoCaminho(texto, aoClicar) {
    const botao = G.el("button", { type: "button", class: "graf-quant__caminho-botao", texto: texto });
    botao.addEventListener("click", aoClicar);
    return botao;
  }

  /* Volta ao nível de `tamanho` linhas no caminho (0 é a raiz). */
  function voltarAte(contexto, tamanho) {
    contexto.estado.pilha.length = tamanho;
    contexto.estado.busca = "";
    contexto.ui.busca.value = "";
    contexto.redesenhar();
  }

  function trilhaDoCaminho(contexto) {
    const dados = contexto.dados;
    const pilha = contexto.estado.pilha;
    const raiz = (dados.total && dados.total.rotulo_raiz) || dados.rotulo_linhas || P.rotulo(dados, "itens");
    const partes = [
      botaoDoCaminho(raiz, function () {
        voltarAte(contexto, 0);
      }),
    ];
    pilha.forEach(function (linha, indice) {
      partes.push(G.el("span", { class: "graf-quant__separador", "aria-hidden": "true", texto: "/" }));
      if (indice === pilha.length - 1) {
        partes.push(G.el("span", { class: "graf-quant__atual", "aria-current": "page", texto: linha.rotulo }));
        return;
      }
      partes.push(
        botaoDoCaminho(linha.rotulo, function () {
          voltarAte(contexto, indice + 1);
        }),
      );
    });
    return G.el("nav", { class: "graf-quant__caminho", "aria-label": P.rotulo(dados, "caminho") }, partes);
  }

  function atualizarContagem(contexto) {
    const dados = contexto.dados;
    contexto.ui.contagem.textContent = linhasFiltradas(contexto).length + " " + P.rotulo(dados, "de") + " " + nivelAtual(contexto).length;
  }

  /* A barra só existe dentro de uma linha; a busca e a contagem são os mesmos
     elementos de sempre, para o foco não se perder enquanto se digita. */
  function desenharBarra(contexto) {
    const pilha = contexto.estado.pilha;
    contexto.ui.barra.hidden = pilha.length === 0;
    if (!pilha.length) {
      contexto.ui.barra.replaceChildren();
      return;
    }
    const voltar = botaoDoCaminho("← " + P.rotulo(contexto.dados, "voltar"), function () {
      voltarAte(contexto, pilha.length - 1);
    });
    voltar.classList.add("is-voltar");
    atualizarContagem(contexto);
    contexto.ui.barra.replaceChildren(voltar, trilhaDoCaminho(contexto), contexto.ui.contagem, contexto.ui.busca);
  }

  /* ---------- Montagem ---------- */

  function colunasDaTabela(contexto) {
    const dados = contexto.dados;
    const grupos = (dados.grupos || []).length;
    return 1 + contexto.folhas.length + grupos + (dados.coluna_total ? 1 : 0) + (dados.metricas || []).length;
  }

  function desenharTabela(contexto) {
    const linhas = linhasFiltradas(contexto);
    const corpo = G.el(
      "tbody",
      {},
      linhas.map(function (linha, indice) {
        return linhaDaTabela(linha, indice, contexto);
      }),
    );
    if (!linhas.length) {
      const vazio = G.el("td", { class: "graf-quant__nada", colspan: colunasDaTabela(contexto), texto: P.rotulo(contexto.dados, "nenhumResultado") });
      corpo.appendChild(G.el("tr", {}, [vazio]));
    }
    corpo.appendChild(linhaDoTotal(contexto));
    const tabela = G.el("table", { class: "graf-quant__tabela", "aria-label": contexto.dados.titulo }, [cabecalhoDaTabela(contexto), corpo]);
    contexto.ui.rolagem.replaceChildren(tabela);
  }

  function desenhar(contexto) {
    desenharBarra(contexto);
    desenharTabela(contexto);
  }

  function criarContexto(host, dados, grupos) {
    const contexto = {
      dados: dados,
      host: host,
      estado: { pilha: [], busca: "" },
      folhas: grupos.flatMap(function (grupo) {
        return grupo.colunas || [];
      }),
      ui: {
        barra: G.el("div", { class: "graf-quant__barra", hidden: true }),
        rolagem: G.el("div", { class: "graf-quant__rolagem" }),
        contagem: G.el("span", { class: "graf-quant__contagem", "aria-live": "polite" }),
        busca: G.el("input", { type: "search", class: "graf-quant__busca", placeholder: P.rotulo(dados, "buscar"), "aria-label": P.rotulo(dados, "buscar") }),
      },
      redesenhar: function () {
        desenhar(contexto);
      },
    };
    contexto.ui.busca.addEventListener("input", function () {
      contexto.estado.busca = P.normalizar(contexto.ui.busca.value.trim());
      desenharTabela(contexto);
      atualizarContagem(contexto);
    });
    return contexto;
  }

  G.registrar(TIPO, function (host, dados) {
    const grupos = Array.isArray(dados.grupos) ? dados.grupos : [];
    if (!grupos.length || !Array.isArray(dados.linhas) || !dados.linhas.length) {
      G.mostrarMensagem(host, G.rotulo(dados, "vazio"));
      return null;
    }
    const contexto = criarContexto(host, dados, grupos);
    const itensDaLegenda = P.itensDeLegenda(dados.legenda || dados.faixas);
    const filhos = [
      dados.titulo ? G.el("div", { class: "graf-quant__titulo", texto: dados.titulo }) : null,
      contexto.ui.barra,
      contexto.ui.rolagem,
      itensDaLegenda.length ? P.legenda(itensDaLegenda, P.rotulo(dados, "legenda")) : null,
    ].filter(Boolean);
    host.replaceChildren(G.el("div", { class: "graf-quant" }, filhos));
    desenhar(contexto);
    return null;
  });
})();
