/* ============================================================
   graficos/matriz-formatada.js — Matriz Formatada

   Porte de "Matriz Formatada.html" (docs/referencia/graficos/), a matriz de
   horas por semana: linhas em árvore que abrem e fecham, colunas em grupo (o
   mês abre nas semanas e ganha a coluna de total), valores em pílulas pintadas
   por faixa, coluna de total, linha de total fixa embaixo, cabeçalho e coluna
   de rótulos que acompanham a rolagem, legenda e os botões Expandir tudo e
   Recolher tudo.

   Serve a matriz P x I, inerente e residual (variante "grade": o miolo é a
   própria célula, com o número e o apoio, e a célula filtra o registro), e
   qualquer matriz de valores por linha e coluna.

   Contrato dos dados (data-dados):
     {
       "titulo": "Matriz P x I residual", "subtitulo": "Ameaças",
       "variante": "pilulas",
       "rotulo_linhas": "Portfólio / Projeto",
       "casas": 0, "unidade": "", "zero_como_vazio": true,
       "colunas_fixas": [{ "id": "total_h", "rotulo": "Horas", "tom": "ok" }],
       "colunas": [
         { "id": "m5", "rotulo": "MAI/26", "faixas": "mes",
           "resumo": { "rotulo": "Mês", "sub": "01/05 a 31/05" },
           "filhas": [{ "id": "m5s1", "rotulo": "S1", "sub": "04/05 a 08/05", "faixas": "semana" }] },
         { "id": "i1", "rotulo": "1", "sub": "Muito baixo" }
       ],
       "coluna_total": { "titulo": "Total", "rotulo": "Geral", "sub": "período", "faixas": "total" },
       "linhas": [{ "id": "a", "rotulo": "Alfa", "selo": "2 proj",
                    "valores": { "m5s1": 4500, "i1": { "valor": 2, "faixa": "alto", "apoio": "5 x 4 = 20", "id": "p5|i4" } },
                    "fixas": { "total_h": 12 }, "filhos": [] }],
       "rodape": { "rotulo": "Total geral" },
       "faixas": { "semana": [{ "menor_que": 3200, "tom": "atencao", "icone": "desce", "rotulo": "Abaixo do esperado" }] },
       "legenda": [], "selecionavel": true, "expandir": 0, "altura": 560
     }
   - `valores` é por id de coluna: número, `null` (sem dado) ou { valor, texto,
     faixa, apoio, id, href }. O que o servidor não manda soma sozinho: o pai
     soma os filhos, o mês soma as semanas, o total soma tudo, o rodapé soma as
     linhas de cima. Quem tem resumo que não é soma (taxa) manda o valor.
   - Faixa: ver pecas.js. `faixas` é uma lista, ou um objeto de listas com
     nome; a coluna escolhe o conjunto em `faixas` (a semana e o mês têm
     limites diferentes) e, sem nome, vale `padrao`. A célula pode mandar
     `faixa` (o id de uma faixa), porque na matriz P x I a cor é da posição.
     `sem_faixa: true` na linha deixa o valor dela neutro. A faixa traz tom e
     ícone: a severidade aparece pela cor, pelo ícone e pelo nome.
   - `variante: "grade"`: células cheias, para a matriz P x I. `zero_como_vazio`
     (padrão true nas pílulas, false na grade) mostra o zero como traço.
   - Linha com `id`, `filhos` e `aberta: true`, ou `expandir` (as linhas de
     nível menor que ele abrem), começa aberta; coluna com `filhas` e
     `aberta: true` também.
   Célula com `id`/`href` (ou `selecionavel: true`) é clicável e dispara
   grafico:selecionar com { id, linha, coluna, valor, item }.

     <div data-grafico="matriz-formatada" data-dados='{{ grafico | tojson }}'></div>

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;
  const P = G.pecas;
  const TIPO = "matriz-formatada";

  /* ---------- Árvore de linhas ---------- */

  function temFilhos(linha) {
    return Array.isArray(linha.filhos) && linha.filhos.length > 0;
  }

  function temFilhas(coluna) {
    return Array.isArray(coluna.filhas) && coluna.filhas.length > 0;
  }

  function chaveDe(linha, prefixo, indice) {
    return linha.id !== undefined ? String(linha.id) : prefixo + indice;
  }

  /* Abre as linhas em que `deveAbrir(linha, profundidade)` diz que sim. */
  function abrirLinhas(dados, estado, deveAbrir) {
    function percorrer(linhas, prof, prefixo) {
      linhas.forEach(function (linha, indice) {
        if (!temFilhos(linha)) return;
        const chave = chaveDe(linha, prefixo, indice);
        if (deveAbrir(linha, prof)) estado.linhas.add(chave);
        percorrer(linha.filhos, prof + 1, chave + ".");
      });
    }
    percorrer(dados.linhas || [], 0, "");
  }

  function abrirColunas(dados, estado, deveAbrir) {
    (dados.colunas || []).forEach(function (coluna) {
      if (temFilhas(coluna) && deveAbrir(coluna)) estado.colunas.add(coluna.id);
    });
  }

  function abrirIniciais(dados, estado) {
    const limite = Number.isInteger(dados.expandir) ? dados.expandir : 0;
    abrirLinhas(dados, estado, function (linha, prof) {
      return linha.aberta === true || prof < limite;
    });
    abrirColunas(dados, estado, function (coluna) {
      return coluna.aberta === true;
    });
  }

  function abrirTudo(dados, estado) {
    abrirLinhas(dados, estado, function () {
      return true;
    });
    abrirColunas(dados, estado, function () {
      return true;
    });
  }

  /* As linhas na ordem em que aparecem, com a profundidade e a chave. */
  function linhasVisiveis(dados, estado) {
    const saida = [];
    function percorrer(linhas, prof, prefixo) {
      linhas.forEach(function (linha, indice) {
        const chave = chaveDe(linha, prefixo, indice);
        saida.push({ linha: linha, prof: prof, chave: chave });
        if (temFilhos(linha) && estado.linhas.has(chave)) percorrer(linha.filhos, prof + 1, chave + ".");
      });
    }
    percorrer(dados.linhas || [], 0, "");
    return saida;
  }

  /* ---------- Colunas ---------- */

  function colunaFolha(coluna, grupo) {
    return {
      tipo: "folha",
      id: coluna.id,
      rotulo: coluna.rotulo,
      sub: coluna.sub,
      folhas: [coluna.id],
      faixas: coluna.faixas || (grupo === coluna ? undefined : grupo.faixas_filhas),
      grupo: grupo,
    };
  }

  function todasAsFolhas(dados) {
    const ids = [];
    (dados.colunas || []).forEach(function (coluna) {
      if (!temFilhas(coluna)) {
        ids.push(coluna.id);
        return;
      }
      coluna.filhas.forEach(function (filha) {
        ids.push(filha.id);
      });
    });
    return ids;
  }

  /* O grupo fechado é uma coluna de resumo; aberto, são as semanas e mais a
     coluna de total do grupo. */
  function colunasDoGrupo(coluna, dados, estado) {
    const ids = coluna.filhas.map(function (filha) {
      return filha.id;
    });
    if (!estado.colunas.has(coluna.id)) {
      const resumo = coluna.resumo || {};
      return [{ tipo: "resumo", id: coluna.id, rotulo: resumo.rotulo || coluna.rotulo, sub: resumo.sub, folhas: ids, faixas: coluna.faixas, grupo: coluna }];
    }
    const colunas = coluna.filhas.map(function (filha) {
      return colunaFolha(filha, coluna);
    });
    colunas.push({ tipo: "subtotal", id: coluna.id, rotulo: P.rotulo(dados, "total"), sub: coluna.rotulo, folhas: ids, faixas: coluna.faixas, grupo: coluna });
    return colunas;
  }

  function colunaDeTotal(dados) {
    const total = dados.coluna_total;
    return {
      tipo: "total",
      id: total.id || "__total",
      titulo: total.titulo || P.rotulo(dados, "total"),
      rotulo: total.rotulo,
      sub: total.sub,
      folhas: todasAsFolhas(dados),
      faixas: total.faixas,
      grupo: total,
    };
  }

  function colunasVisiveis(dados, estado) {
    const visiveis = [];
    (dados.colunas || []).forEach(function (coluna) {
      const colunas = temFilhas(coluna) ? colunasDoGrupo(coluna, dados, estado) : [colunaFolha(coluna, coluna)];
      colunas.forEach(function (visivel) {
        visiveis.push(visivel);
      });
    });
    if (dados.coluna_total) visiveis.push(colunaDeTotal(dados));
    return visiveis;
  }

  /* ---------- Valores ---------- */

  /* O valor da linha numa coluna de folha: o que ela manda ou, sendo pai, a
     soma dos filhos. */
  function valorDaFolha(linha, folhaId) {
    return P.valorDaArvore(linha, function (no) {
      return no.valores ? no.valores[folhaId] : undefined;
    });
  }

  function valorDaColuna(linha, coluna) {
    if (coluna.tipo === "folha") return valorDaFolha(linha, coluna.id);
    const proprio = linha.valores ? linha.valores[coluna.id] : undefined;
    if (proprio !== undefined) return proprio;
    return P.somar(
      coluna.folhas.map(function (folhaId) {
        return P.valorDaCelula(valorDaFolha(linha, folhaId));
      }),
    );
  }

  function valorFixo(linha, fixa) {
    return P.valorDaArvore(linha, function (no) {
      return no.fixas ? no.fixas[fixa.id] : undefined;
    });
  }

  function itemDe(bruto) {
    return bruto !== null && typeof bruto === "object" ? bruto : { valor: bruto };
  }

  function zeroComoVazio(dados) {
    if (typeof dados.zero_como_vazio === "boolean") return dados.zero_como_vazio;
    return dados.variante !== "grade";
  }

  function faixaDaMatriz(bruto, linha, coluna, dados) {
    const propria = bruto !== null && typeof bruto === "object" && bruto.faixa !== undefined;
    if (linha.sem_faixa === true && !propria) return null;
    return P.faixaDaCelula(bruto, P.conjuntoDeFaixas(dados.faixas, coluna.faixas), dados.faixas);
  }

  /* ---------- Células ---------- */

  function celulaDeValor(bruto, faixa, dados) {
    const item = itemDe(bruto);
    const semValor = !Number.isFinite(item.valor) && typeof item.texto !== "string";
    const zerado = item.valor === 0 && zeroComoVazio(dados);
    if (semValor || zerado) {
      return P.celula(P.VAZIO, { tom: "cinza", vazia: true }, { classe: "graf-matriz__valor", href: item.href });
    }
    const classe = "graf-matriz__valor" + (item.valor === 0 ? " is-zero" : "");
    return P.celula(P.textoDoValor(item, dados), faixa, { classe: classe, href: item.href });
  }

  function celulaDaMatriz(linha, coluna, contexto) {
    const dados = contexto.dados;
    const bruto = valorDaColuna(linha, coluna);
    const item = itemDe(bruto);
    const pilula = celulaDeValor(bruto, faixaDaMatriz(bruto, linha, coluna, dados), dados);
    const filhos = [pilula];
    if (item.apoio) filhos.push(G.el("span", { class: "graf-matriz__apoio", texto: item.apoio }));
    if (P.ehSelecionavel(item, dados)) {
      const detalhe = { id: item.id, linha: linha.id, coluna: coluna.id, valor: item.valor, item: item };
      P.tornarInterativo(pilula, { host: contexto.host, tipo: TIPO, detalhe: detalhe });
    }
    return G.el("td", { class: "graf-matriz__td" + (coluna.tipo === "folha" ? "" : " is-total") }, filhos);
  }

  /* A coluna fixa leva só o tom da coluna, sem ícone: é uma medida, não um estado. */
  function celulaFixa(linha, fixa, dados) {
    const item = itemDe(valorFixo(linha, fixa));
    const semValor = !Number.isFinite(item.valor);
    const texto = semValor ? P.VAZIO : P.textoDoValor(item, dados);
    const faixa = semValor ? { tom: "cinza", vazia: true } : { tom: fixa.tom || "neutro", icone: false };
    return G.el("td", { class: "graf-matriz__td is-fixa" }, [P.celula(texto, faixa, { classe: "graf-matriz__valor" })]);
  }

  /* ---------- Rótulo da linha ---------- */

  function alternarEm(conjunto, chave) {
    if (conjunto.has(chave)) {
      conjunto.delete(chave);
    } else {
      conjunto.add(chave);
    }
  }

  function caret(aberto) {
    return G.el("span", { class: "graf-matriz__caret" + (aberto ? " is-aberto" : ""), "aria-hidden": "true" });
  }

  /* O nome da linha é o próprio botão: o alvo do clique é grande e o leitor de
     tela ouve o nome e o estado (aria-expanded). */
  function botaoDeAbrir(no, aberta, contexto) {
    const botao = G.el(
      "button",
      {
        type: "button",
        class: "graf-matriz__alternar",
        "aria-expanded": aberta ? "true" : "false",
        title: P.rotulo(contexto.dados, aberta ? "recolher" : "expandir"),
        "data-foco": "l:" + no.chave,
      },
      [caret(aberta), G.el("span", { class: "graf-matriz__texto", texto: no.linha.rotulo })],
    );
    botao.addEventListener("click", function () {
      alternarEm(contexto.estado.linhas, no.chave);
      contexto.redesenhar("l:" + no.chave);
    });
    return botao;
  }

  function nomeDaLinha(no, contexto) {
    if (temFilhos(no.linha)) return botaoDeAbrir(no, contexto.estado.linhas.has(no.chave), contexto);
    return G.el("span", { class: "graf-matriz__folha" }, [
      G.el("span", { class: "graf-matriz__ponto", "aria-hidden": "true" }),
      G.el("span", { class: "graf-matriz__texto", texto: no.linha.rotulo }),
    ]);
  }

  function celulaDoRotulo(no, contexto) {
    const filhos = [nomeDaLinha(no, contexto)];
    if (no.linha.selo) filhos.push(G.el("span", { class: "graf-matriz__selo", texto: no.linha.selo }));
    const celula = G.el("th", { class: "graf-matriz__rotulo", scope: "row", title: no.linha.rotulo }, filhos);
    celula.style.paddingLeft = 12 + no.prof * 14 + "px";
    return celula;
  }

  function linhaDaTabela(no, contexto) {
    const celulas = [celulaDoRotulo(no, contexto)];
    (contexto.dados.colunas_fixas || []).forEach(function (fixa) {
      celulas.push(celulaFixa(no.linha, fixa, contexto.dados));
    });
    contexto.visiveis.forEach(function (coluna) {
      celulas.push(celulaDaMatriz(no.linha, coluna, contexto));
    });
    return G.el("tr", { class: "graf-matriz__linha is-prof-" + Math.min(no.prof, 3) }, celulas);
  }

  /* ---------- Rodapé ---------- */

  function celulaDoRodape(texto) {
    return G.el("td", { class: "graf-matriz__td" }, [P.celula(texto, null, { classe: "graf-matriz__valor is-rodape" })]);
  }

  /* O que o servidor mandou para o rodapé, ou a soma das linhas de cima. */
  function textoDoRodape(explicito, soma, dados) {
    if (explicito !== undefined) return P.textoDoValor(itemDe(explicito), dados);
    return soma === null ? P.VAZIO : P.textoDoValor({ valor: soma }, dados);
  }

  function somaDasLinhas(linhas, calcular) {
    return P.somar(
      linhas.map(function (linha) {
        return P.valorDaCelula(calcular(linha));
      }),
    );
  }

  function linhaDoRodape(contexto) {
    const dados = contexto.dados;
    const rodape = dados.rodape;
    if (!rodape) return null;
    const topo = dados.linhas || [];
    const celulas = [G.el("th", { class: "graf-matriz__rotulo is-rodape", scope: "row", texto: rodape.rotulo || P.rotulo(dados, "total") })];
    (dados.colunas_fixas || []).forEach(function (fixa) {
      const soma = somaDasLinhas(topo, function (linha) {
        return valorFixo(linha, fixa);
      });
      celulas.push(celulaDoRodape(textoDoRodape(rodape.fixas ? rodape.fixas[fixa.id] : undefined, soma, dados)));
    });
    contexto.visiveis.forEach(function (coluna) {
      const soma = somaDasLinhas(topo, function (linha) {
        return valorDaColuna(linha, coluna);
      });
      celulas.push(celulaDoRodape(textoDoRodape(rodape.valores ? rodape.valores[coluna.id] : undefined, soma, dados)));
    });
    return G.el("tr", { class: "graf-matriz__linha is-rodape-linha" }, celulas);
  }

  /* ---------- Cabeçalho ---------- */

  function nomeEApoio(coluna) {
    const filhos = [G.el("span", { class: "graf-matriz__th-nome", texto: coluna.rotulo })];
    if (coluna.sub) filhos.push(G.el("span", { class: "graf-matriz__th-sub", texto: coluna.sub }));
    return filhos;
  }

  function cabecalhoDeCanto(texto, classe, linhasDeCabecalho) {
    return G.el("th", { class: "graf-matriz__th " + classe, scope: "col", rowspan: linhasDeCabecalho }, [G.el("span", { class: "graf-matriz__th-nome", texto: texto })]);
  }

  function cabecalhoDoGrupo(grupo, quantidade, contexto) {
    const aberto = contexto.estado.colunas.has(grupo.id);
    const botao = G.el(
      "button",
      {
        type: "button",
        class: "graf-matriz__alternar",
        "aria-expanded": aberto ? "true" : "false",
        title: P.rotulo(contexto.dados, aberto ? "recolher" : "expandir"),
        "data-foco": "c:" + grupo.id,
      },
      [caret(aberto), G.el("span", { class: "graf-matriz__texto", texto: grupo.rotulo })],
    );
    botao.addEventListener("click", function () {
      alternarEm(contexto.estado.colunas, grupo.id);
      contexto.redesenhar("c:" + grupo.id);
    });
    return G.el("th", { class: "graf-matriz__th is-grupo" + (aberto ? " is-aberto" : ""), scope: "colgroup", colspan: quantidade }, [botao]);
  }

  /* As colunas visíveis reunidas por grupo, na ordem. */
  function agruparColunas(visiveis) {
    const grupos = [];
    visiveis.forEach(function (coluna) {
      const ultimo = grupos[grupos.length - 1];
      if (ultimo && ultimo.grupo === coluna.grupo) {
        ultimo.colunas.push(coluna);
        return;
      }
      grupos.push({ grupo: coluna.grupo, colunas: [coluna] });
    });
    return grupos;
  }

  /* Com colunas em grupo (ou de total) o cabeçalho tem duas linhas: o nome do
     grupo em cima e as colunas embaixo; a coluna solta ocupa as duas. */
  function celulasDoGrupo(reuniao, contexto) {
    const primeira = reuniao.colunas[0];
    if (primeira.tipo === "total") {
      return {
        em_cima: [G.el("th", { class: "graf-matriz__th is-total-cab", scope: "col", texto: primeira.titulo })],
        embaixo: [G.el("th", { class: "graf-matriz__th is-sub is-total-cab", scope: "col" }, nomeEApoio(primeira))],
      };
    }
    if (temFilhas(reuniao.grupo)) {
      return {
        em_cima: [cabecalhoDoGrupo(reuniao.grupo, reuniao.colunas.length, contexto)],
        embaixo: reuniao.colunas.map(function (coluna) {
          const classe = "graf-matriz__th is-sub" + (coluna.tipo === "subtotal" ? " is-subtotal" : "");
          return G.el("th", { class: classe, scope: "col" }, nomeEApoio(coluna));
        }),
      };
    }
    const linhasDeCabecalho = contexto.temGrupos ? 2 : 1;
    return { em_cima: [G.el("th", { class: "graf-matriz__th", scope: "col", rowspan: linhasDeCabecalho }, nomeEApoio(primeira))], embaixo: [] };
  }

  function cabecalhoDaMatriz(contexto) {
    const dados = contexto.dados;
    const linhasDeCabecalho = contexto.temGrupos ? 2 : 1;
    const primeira = [cabecalhoDeCanto(dados.rotulo_linhas || "", "is-canto", linhasDeCabecalho)];
    (dados.colunas_fixas || []).forEach(function (fixa) {
      primeira.push(cabecalhoDeCanto(fixa.rotulo, "is-fixa", linhasDeCabecalho));
    });
    const segunda = [];
    agruparColunas(contexto.visiveis).forEach(function (reuniao) {
      const celulas = celulasDoGrupo(reuniao, contexto);
      celulas.em_cima.forEach(function (celula) {
        primeira.push(celula);
      });
      celulas.embaixo.forEach(function (celula) {
        segunda.push(celula);
      });
    });
    const linhas = [G.el("tr", { class: "graf-matriz__h1" }, primeira)];
    if (contexto.temGrupos) linhas.push(G.el("tr", { class: "graf-matriz__h2" }, segunda));
    return G.el("thead", {}, linhas);
  }

  /* ---------- Montagem ---------- */

  function desenhar(contexto, foco) {
    contexto.visiveis = colunasVisiveis(contexto.dados, contexto.estado);
    const corpo = G.el(
      "tbody",
      {},
      linhasVisiveis(contexto.dados, contexto.estado).map(function (no) {
        return linhaDaTabela(no, contexto);
      }),
    );
    const rodape = linhaDoRodape(contexto);
    if (rodape) corpo.appendChild(rodape);
    const tabela = G.el("table", { class: "graf-matriz__tabela", "aria-label": contexto.dados.titulo }, [cabecalhoDaMatriz(contexto), corpo]);
    contexto.corpo.replaceChildren(tabela);
    if (!foco) return;
    /* O botão que a pessoa acabou de usar foi refeito: o foco volta para ele. */
    const alvo = Array.from(contexto.corpo.querySelectorAll("[data-foco]")).find(function (no) {
      return no.getAttribute("data-foco") === foco;
    });
    if (alvo) alvo.focus();
  }

  function botoesDeExpansao(contexto) {
    const dados = contexto.dados;
    if (!contexto.expansivel) return [];
    const expandir = G.el("button", { type: "button", class: "graf-matriz__botao", texto: P.rotulo(dados, "expandirTudo") });
    expandir.addEventListener("click", function () {
      abrirTudo(dados, contexto.estado);
      desenhar(contexto, null);
    });
    const recolher = G.el("button", { type: "button", class: "graf-matriz__botao", texto: P.rotulo(dados, "recolherTudo") });
    recolher.addEventListener("click", function () {
      contexto.estado.linhas.clear();
      contexto.estado.colunas.clear();
      desenhar(contexto, null);
    });
    return [expandir, recolher];
  }

  function blocoDeTitulo(dados) {
    const titulos = [];
    if (dados.titulo) titulos.push(G.el("div", { class: "graf-matriz__titulo", texto: dados.titulo }));
    if (dados.subtitulo) titulos.push(G.el("div", { class: "graf-matriz__subtitulo", texto: dados.subtitulo }));
    if (!titulos.length) return G.el("div", { class: "graf-matriz__tit" });
    return G.el("div", { class: "graf-matriz__tit" }, [G.el("span", { class: "graf-matriz__barra", "aria-hidden": "true" }), G.el("div", {}, titulos)]);
  }

  function cabecalhoDaVisao(contexto) {
    const dados = contexto.dados;
    const itensDaLegenda = P.itensDeLegenda(dados.legenda || dados.faixas);
    const botoes = botoesDeExpansao(contexto);
    if (!dados.titulo && !dados.subtitulo && !itensDaLegenda.length && !botoes.length) return null;
    const direita = [];
    if (itensDaLegenda.length) direita.push(P.legenda(itensDaLegenda, P.rotulo(dados, "legenda")));
    if (botoes.length) direita.push(G.el("div", { class: "graf-matriz__botoes" }, botoes));
    return G.el("header", { class: "graf-matriz__cab" }, [blocoDeTitulo(dados), G.el("div", { class: "graf-matriz__acoes" }, direita)]);
  }

  function haFilhosNasLinhas(dados) {
    return (dados.linhas || []).some(temFilhos);
  }

  G.registrar(TIPO, function (host, dados) {
    if (!Array.isArray(dados.linhas) || !dados.linhas.length) {
      G.mostrarMensagem(host, G.rotulo(dados, "vazio"));
      return null;
    }
    const grupos = (dados.colunas || []).some(temFilhas);
    const contexto = {
      dados: dados,
      host: host,
      estado: { linhas: new Set(), colunas: new Set() },
      temGrupos: grupos || Boolean(dados.coluna_total),
      expansivel: grupos || haFilhosNasLinhas(dados),
      corpo: G.el("div", { class: "graf-matriz__corpo" }),
      visiveis: [],
      redesenhar: function (foco) {
        desenhar(contexto, foco);
      },
    };
    abrirIniciais(dados, contexto.estado);
    const variante = dados.variante === "grade" ? "grade" : "pilulas";
    const raiz = G.el("div", { class: "graf-matriz graf-matriz--" + variante }, [cabecalhoDaVisao(contexto), contexto.corpo].filter(Boolean));
    host.replaceChildren(raiz);
    desenhar(contexto, null);
    return null;
  });
})();
