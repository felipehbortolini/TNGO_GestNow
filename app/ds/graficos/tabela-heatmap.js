/* ============================================================
   graficos/tabela-heatmap.js — Tabela Heatmap

   Porte de "Tabela Heatmap.html" (docs/referencia/graficos/): a tabela de
   linhas e colunas em que cada célula é pintada pela faixa do seu valor, com
   o cabeçalho escuro de nomes na vertical, a coluna de total, a linha de
   total geral e a legenda. Serve o mapa de calor do desvio da EAC (R$ mil, com
   o desvio pintado), o dia x frente e o aging.

   Contrato dos dados (data-dados):
     {
       "titulo": "Desvio da projeção sobre o orçado atual",
       "rotulo_linhas": "Pacote",
       "casas": 1, "unidade": "%", "sinal": true,
       "colunas": [
         { "id": "orcado", "rotulo": "Orçado atual", "calor": false, "casas": 0, "unidade": "", "sinal": false },
         { "id": "desvio", "rotulo": "Desvio" }
       ],
       "linhas": [{ "id": "p1", "rotulo": "Terraplenagem",
                    "valores": { "orcado": 1250, "desvio": 7.4 } }],
       "total": { "linha": "Total geral", "coluna": "Total" },
       "faixas": [
         { "maior_que": 10, "tom": "erro", "nivel": 3, "icone": "sobe", "rotulo": "Sobrecusto acima de 10%" },
         { "ate": 0, "tom": "cinza", "vazia": true, "rotulo": "Sem desvio" }
       ],
       "legenda": [], "selecionavel": true
     }
   - O valor da célula é um número, `null` ou { valor, texto, faixa, id, href }.
   - A faixa de cada célula vem de `faixas` (ver pecas.js): tom (família do
     Design System), nível de intensidade, ícone e nome. A célula mostra o
     ícone e o número (e o sinal, com `sinal: true`), e o nome da faixa fica na
     dica e para o leitor de tela: a cor nunca é o único sinal. Os limites são
     parâmetros do projeto e chegam do servidor, nunca daqui.
   - `calor: false` na coluna mostra o número sem pintar (as colunas de valor
     do mapa de controle). `casas`, `unidade` e `sinal` valem por coluna e, sem
     eles, os do topo.
   - `total` põe a coluna e a linha de total, que somam as colunas e as linhas
     (menos as de `somar: false`); a linha pode mandar `total` e a coluna
     também, quando o total não é soma. Os totais usam o conjunto `total` de
     `faixas` (um objeto de listas) ou, sem ele, a lista `padrao`.
   Célula com `id`/`href` (ou `selecionavel: true`) é clicável e dispara
   grafico:selecionar com { id, linha, coluna, valor, item }.

     <div data-grafico="tabela-heatmap" data-dados='{{ grafico | tojson }}'></div>

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;
  const P = G.pecas;
  const TIPO = "tabela-heatmap";
  const PONTO_VAZIO = "·";

  function itemDe(bruto) {
    return bruto !== null && typeof bruto === "object" ? bruto : { valor: bruto };
  }

  function totalDaLinha(linha, colunas) {
    if (Number.isFinite(linha.total)) return linha.total;
    return P.somar(
      colunas
        .filter(function (coluna) {
          return coluna.somar !== false;
        })
        .map(function (coluna) {
          return P.valorDaCelula(linha.valores ? linha.valores[coluna.id] : null);
        }),
    );
  }

  function totalDaColuna(coluna, linhas) {
    if (Number.isFinite(coluna.total)) return coluna.total;
    if (coluna.somar === false) return null;
    return P.somar(
      linhas.map(function (linha) {
        return P.valorDaCelula(linha.valores ? linha.valores[coluna.id] : null);
      }),
    );
  }

  /* ---------- Células ---------- */

  /* A célula pintada: o ícone e o número da faixa; sem valor ou na faixa vazia,
     um ponto esmaecido. */
  function celulaPintada(item, faixa, padroes) {
    const semValor = !Number.isFinite(item.valor) && typeof item.texto !== "string";
    if (semValor || (faixa && faixa.vazia)) {
      return P.celula(PONTO_VAZIO, { tom: "cinza", vazia: true, rotulo: faixa ? faixa.rotulo : undefined }, { classe: "graf-heat__celula", href: item.href });
    }
    return P.celula(P.textoDoValor(item, padroes), faixa, { classe: "graf-heat__celula", href: item.href });
  }

  function celulaSimples(item, padroes) {
    const semValor = !Number.isFinite(item.valor) && typeof item.texto !== "string";
    return G.el("span", { class: "graf-heat__numero" + (semValor ? " is-vazio" : ""), texto: semValor ? PONTO_VAZIO : P.textoDoValor(item, padroes) });
  }

  function celulaDeCorpo(linha, coluna, contexto) {
    const dados = contexto.dados;
    const bruto = linha.valores ? linha.valores[coluna.id] : null;
    const item = itemDe(bruto);
    const padroes = P.padroesDaColuna(coluna, dados);
    if (coluna.calor === false) return G.el("td", { class: "graf-heat__td is-simples" }, [celulaSimples(item, padroes)]);
    const faixa = P.faixaDaCelula(bruto, P.conjuntoDeFaixas(dados.faixas, coluna.faixas), dados.faixas);
    const pilula = celulaPintada(item, faixa, padroes);
    if (P.ehSelecionavel(item, dados)) {
      const detalhe = { id: item.id, linha: linha.id, coluna: coluna.id, valor: item.valor, item: item };
      P.tornarInterativo(pilula, { host: contexto.host, tipo: TIPO, detalhe: detalhe });
    }
    return G.el("td", { class: "graf-heat__td" }, [pilula]);
  }

  /* O total usa o conjunto "total" das faixas, e fica em destaque. */
  function celulaDeTotal(valor, dados, padroes) {
    const faixa = P.faixaDe(valor, P.conjuntoDeFaixas(dados.faixas, "total"));
    const texto = Number.isFinite(valor) ? P.textoDoValor({ valor: valor }, padroes) : PONTO_VAZIO;
    return G.el("td", { class: "graf-heat__td is-total" }, [P.celula(texto, faixa, { classe: "graf-heat__celula is-total" })]);
  }

  /* ---------- Tabela ---------- */

  function cabecalho(contexto) {
    const dados = contexto.dados;
    const celulas = [G.el("th", { class: "graf-heat__th is-area", scope: "col", texto: dados.rotulo_linhas || "" })];
    contexto.colunas.forEach(function (coluna) {
      celulas.push(G.el("th", { class: "graf-heat__th is-coluna", scope: "col", title: coluna.rotulo }, [G.el("span", { class: "graf-heat__th-texto", texto: coluna.rotulo })]));
    });
    if (contexto.comTotal) {
      celulas.push(G.el("th", { class: "graf-heat__th is-coluna is-total", scope: "col" }, [G.el("span", { class: "graf-heat__th-texto", texto: contexto.rotuloDaColunaTotal })]));
    }
    return G.el("thead", {}, [G.el("tr", {}, celulas)]);
  }

  function linhaDoCorpo(linha, indice, contexto) {
    const celulas = [G.el("th", { class: "graf-heat__rotulo", scope: "row", title: linha.rotulo, texto: linha.rotulo })];
    contexto.colunas.forEach(function (coluna) {
      celulas.push(celulaDeCorpo(linha, coluna, contexto));
    });
    if (contexto.comTotal) celulas.push(celulaDeTotal(totalDaLinha(linha, contexto.colunas), contexto.dados, contexto.dados));
    const tr = G.el("tr", { class: "graf-heat__linha" }, celulas);
    tr.style.setProperty("--atraso", indice * 40 + "ms");
    return tr;
  }

  function linhaDeTotal(contexto) {
    const dados = contexto.dados;
    const celulas = [G.el("th", { class: "graf-heat__rotulo is-total", scope: "row", texto: contexto.rotuloDaLinhaTotal })];
    contexto.colunas.forEach(function (coluna) {
      celulas.push(celulaDeTotal(totalDaColuna(coluna, dados.linhas), dados, P.padroesDaColuna(coluna, dados)));
    });
    if (contexto.comTotal) {
      const geral = Number.isFinite(dados.total && dados.total.valor) ? dados.total.valor : totalGeral(contexto);
      celulas.push(celulaDeTotal(geral, dados, dados));
    }
    return G.el("tr", { class: "graf-heat__linha is-total" }, celulas);
  }

  function totalGeral(contexto) {
    return P.somar(
      contexto.dados.linhas.map(function (linha) {
        return totalDaLinha(linha, contexto.colunas);
      }),
    );
  }

  function rotuloDoTotal(dados, chave) {
    const total = dados.total;
    if (total && typeof total === "object" && typeof total[chave] === "string") return total[chave];
    return P.rotulo(dados, "total");
  }

  G.registrar(TIPO, function (host, dados) {
    const colunas = Array.isArray(dados.colunas) ? dados.colunas : [];
    const linhas = Array.isArray(dados.linhas) ? dados.linhas : [];
    if (!colunas.length || !linhas.length) {
      G.mostrarMensagem(host, G.rotulo(dados, "vazio"));
      return null;
    }
    const contexto = {
      dados: dados,
      host: host,
      colunas: colunas,
      comTotal: Boolean(dados.total),
      rotuloDaColunaTotal: rotuloDoTotal(dados, "coluna"),
      rotuloDaLinhaTotal: rotuloDoTotal(dados, "linha"),
    };
    const corpo = G.el(
      "tbody",
      {},
      linhas.map(function (linha, indice) {
        return linhaDoCorpo(linha, indice, contexto);
      }),
    );
    if (contexto.comTotal) corpo.appendChild(linhaDeTotal(contexto));
    const tabela = G.el("table", { class: "graf-heat__tabela", "aria-label": dados.titulo }, [cabecalho(contexto), corpo]);
    const itensDaLegenda = P.itensDeLegenda(dados.legenda || dados.faixas);
    const filhos = [
      dados.titulo ? G.el("div", { class: "graf-heat__titulo", texto: dados.titulo }) : null,
      G.el("div", { class: "graf-heat__rolagem" }, [tabela]),
      itensDaLegenda.length ? P.legenda(itensDaLegenda, P.rotulo(dados, "legenda")) : null,
    ].filter(Boolean);
    host.replaceChildren(G.el("div", { class: "graf-heat" }, filhos));
    return null;
  });
})();
