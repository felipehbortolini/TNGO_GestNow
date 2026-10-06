/* ============================================================
   graficos/detalhe.js — Painel de detalhe dos visuais

   O que abre quando se clica no cartão do Mapa de 52 semanas, na linha das
   Etapas ou no item dos Quantitativos: o modal do Design System (TN.modal)
   com o conteúdo que o servidor mandou em `detalhe`. Os originais montavam
   um modal diferente por visual; aqui há um só, feito de blocos.

   Contrato (`detalhe`):
     {
       "titulo": "Projeto Ômega", "subtitulo": "Submissão em 04/09/26",
       "chips": [{ "texto": "FEL2", "tom": "info", "icone": true }],
       "blocos": [
         { "tipo": "campos", "titulo": "Resumo",
           "itens": [{ "rotulo": "Fase", "valor": "FEL2", "tom": "info" }] },
         { "tipo": "textos", "itens": [{ "rotulo": "Justificativa", "valor": "..." }] },
         { "tipo": "tabela", "titulo": "Atividades",
           "colunas": ["Atividade", { "rotulo": "Prazo", "alinhar": "centro" }],
           "linhas": [{ "tom": "ok", "celulas": ["Emitir RFA", { "texto": "Concluída", "tom": "ok" }] }],
           "vazio": "Nenhuma atividade." },
         { "tipo": "cartoes", "titulo": "Etapas",
           "itens": [{ "titulo": "Ata", "tom": "alerta", "selo": { "texto": "Em andamento", "tom": "alerta" },
                       "campos": [{ "rotulo": "Previsto", "valor": "04/09/26" }], "texto": "...",
                       "filhos": [{ "titulo": "Atividade", "tom": "ok" }] }] }
       ]
     }
   Todo texto entra por textContent: o que vem do banco não vira HTML. O
   `tom` é o das peças (pecas.js) e vira a faixa colorida do item.

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;
  const P = G.pecas;

  function textoOuTraco(valor) {
    return valor === null || valor === undefined || valor === "" ? P.VAZIO : String(valor);
  }

  function titulo(texto) {
    return texto ? G.el("h3", { class: "graf-det__titulo", texto: texto }) : null;
  }

  function valorDoCampo(campo) {
    const texto = textoOuTraco(campo.valor);
    if (campo.tom) return P.chip(texto, campo.tom, { icone: campo.icone });
    return G.el("div", { class: "graf-det__val", texto: texto });
  }

  function campo(item) {
    return G.el("div", { class: "graf-det__campo" }, [G.el("div", { class: "graf-det__rot", texto: item.rotulo }), valorDoCampo(item)]);
  }

  function blocoCampos(bloco) {
    return G.el("div", { class: "graf-det__campos" }, (bloco.itens || []).map(campo));
  }

  function blocoTextos(bloco) {
    return G.el(
      "div",
      { class: "graf-det__textos" },
      (bloco.itens || []).map(function (item) {
        return G.el("div", { class: "graf-det__texto" }, [
          G.el("div", { class: "graf-det__rot", texto: item.rotulo }),
          G.el("div", { class: "graf-det__val", texto: textoOuTraco(item.valor) }),
        ]);
      }),
    );
  }

  /* ---------- Tabela ---------- */

  function alinhamento(alinhar) {
    return alinhar ? " is-" + alinhar : "";
  }

  function cabecalhoDaTabela(coluna) {
    const ehTexto = typeof coluna === "string";
    const rotulo = ehTexto ? coluna : coluna.rotulo;
    return G.el("th", { class: "graf-det__th" + alinhamento(ehTexto ? null : coluna.alinhar), scope: "col", texto: rotulo });
  }

  function celulaDaTabela(bruto, indice, colunas) {
    const coluna = colunas[indice];
    const alinhar = coluna && typeof coluna === "object" ? coluna.alinhar : null;
    const ehObjeto = bruto !== null && typeof bruto === "object";
    const texto = textoOuTraco(ehObjeto ? bruto.texto : bruto);
    const vazio = texto === P.VAZIO ? " is-vazio" : "";
    if (ehObjeto && bruto.tom) {
      return G.el("td", { class: "graf-det__td" + alinhamento(alinhar) }, [P.chip(texto, bruto.tom, { icone: bruto.icone })]);
    }
    return G.el("td", { class: "graf-det__td" + alinhamento(alinhar) + vazio, texto: texto });
  }

  function linhaDaTabela(linha, colunas) {
    const celulas = (linha.celulas || []).map(function (bruto, indice) {
      return celulaDaTabela(bruto, indice, colunas);
    });
    return G.el("tr", { class: "graf-det__linha " + P.classeDoTom(linha.tom) }, celulas);
  }

  function linhaVazia(bloco, colunas) {
    const celula = G.el("td", { class: "graf-det__td is-vazio is-centro", colspan: Math.max(colunas.length, 1), texto: bloco.vazio || P.rotulo(null, "nenhumRegistro") });
    return G.el("tr", {}, [celula]);
  }

  function blocoTabela(bloco) {
    const colunas = bloco.colunas || [];
    const linhas = bloco.linhas || [];
    const corpo = linhas.length
      ? linhas.map(function (linha) {
          return linhaDaTabela(linha, colunas);
        })
      : [linhaVazia(bloco, colunas)];
    const tabela = G.el("table", { class: "graf-det__tabela" }, [
      G.el("thead", {}, [G.el("tr", {}, colunas.map(cabecalhoDaTabela))]),
      G.el("tbody", {}, corpo),
    ]);
    return G.el("div", { class: "graf-det__rolagem" }, [tabela]);
  }

  /* ---------- Cartões ---------- */

  function cabecaDoCartao(item) {
    const filhos = [G.el("div", { class: "graf-det__cartao-tit", texto: item.titulo })];
    if (item.selo && item.selo.texto) filhos.push(P.chip(item.selo.texto, item.selo.tom || item.tom, { icone: item.selo.icone }));
    return G.el("div", { class: "graf-det__cartao-cab" }, filhos);
  }

  function cartao(item) {
    const filhos = [cabecaDoCartao(item)];
    if (item.subtitulo) filhos.push(G.el("div", { class: "graf-det__cartao-sub", texto: item.subtitulo }));
    if (Array.isArray(item.campos) && item.campos.length) filhos.push(blocoCampos({ itens: item.campos }));
    if (item.texto) filhos.push(G.el("div", { class: "graf-det__cartao-texto", texto: item.texto }));
    if (Array.isArray(item.filhos) && item.filhos.length) {
      filhos.push(G.el("div", { class: "graf-det__cartoes is-aninhados" }, item.filhos.map(cartao)));
    }
    return G.el("div", { class: "graf-det__cartao " + P.classeDoTom(item.tom) }, filhos);
  }

  function blocoCartoes(bloco) {
    return G.el("div", { class: "graf-det__cartoes" }, (bloco.itens || []).map(cartao));
  }

  const BLOCOS = {
    campos: blocoCampos,
    textos: blocoTextos,
    tabela: blocoTabela,
    cartoes: blocoCartoes,
  };

  function montarBloco(dadosDoBloco) {
    const montar = Object.hasOwn(BLOCOS, dadosDoBloco.tipo) ? BLOCOS[dadosDoBloco.tipo] : null;
    if (!montar) {
      console.warn("[graficos] bloco de detalhe desconhecido: " + dadosDoBloco.tipo);
      return null;
    }
    return G.el("section", { class: "graf-det__bloco" }, [titulo(dadosDoBloco.titulo), montar(dadosDoBloco)].filter(Boolean));
  }

  function conteudo(detalhe) {
    const chips = (detalhe.chips || []).map(function (item) {
      return P.chip(item.texto, item.tom, { icone: item.icone });
    });
    const filhos = [];
    if (chips.length) filhos.push(G.el("div", { class: "graf-det__chips" }, chips));
    (detalhe.blocos || []).forEach(function (dadosDoBloco) {
      const no = montarBloco(dadosDoBloco);
      if (no) filhos.push(no);
    });
    return G.el("div", { class: "graf-det" }, filhos);
  }

  /* Abre o modal do Design System. TN.modal usa `this`: chamar sempre como
     método de TN. O foco vai para o botão de fechar, porque o modal nasce
     vazio e, sem isso, o teclado continuaria atrás dele. */
  function abrir(detalhe) {
    if (!window.TN || typeof window.TN.modal !== "function") {
      console.warn("[graficos] TN.modal indisponível: o detalhe não abre");
      return null;
    }
    const aberto = window.TN.modal({
      title: detalhe.titulo || "",
      subtitle: detalhe.subtitulo || "",
      width: Number.isFinite(detalhe.largura) ? detalhe.largura : 1040,
      body: "",
    });
    aberto.body.appendChild(conteudo(detalhe));
    const fechar = aberto.el.querySelector(".modal__close");
    if (fechar) fechar.focus();
    return aberto;
  }

  G.detalhe = { abrir: abrir, conteudo: conteudo };
})();
