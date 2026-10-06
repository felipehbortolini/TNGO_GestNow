/* ============================================================
   graficos/mapa-52-semanas.js — Mapa 52 semanas

   Porte de "Mapa 52 semanas.html" (docs/referencia/graficos/): uma coluna por
   semana do ano, de seis em seis na tela, e em cada coluna os cartões dos
   itens que caem naquela semana, com a faixa colorida do estado, a etiqueta, os
   chips e a data. Em cima, o título, os totais por estado e os botões de ano;
   abaixo, a busca, os filtros, as setas, o botão Hoje e a contagem; no pé, a
   legenda. O clique no cartão abre o detalhe. Serve o MAS (os marcos de cada
   pacote) e o plano de quantidades por semana.

   Contrato dos dados (data-dados):
     {
       "titulo": "Marcos do MAS", "subtitulo": "Pacote x Marco",
       "ano": 2026, "hoje": { "ano": 2026, "semana": 41 }, "por_pagina": 6,
       "anos": [{ "ano": 2026, "semanas": [
         { "semana": 1, "mes": 1, "inicio": "2025-12-29", "fim": "2026-01-04" }
       ] }],
       "legenda": [{ "id": "concluido", "rotulo": "Concluído", "rotulo_total": "Concluídas", "tom": "ok" }],
       "filtros": [{ "id": "fase", "rotulo": "Fase",
                     "opcoes": [{ "id": "FEL2", "rotulo": "FEL2" }] }],
       "kpis_extras": [{ "rotulo": "Sem plano", "valor": 3, "tom": "info" }],
       "itens": [{
         "id": "m-12", "ano": 2026, "semana": 38, "titulo": "Pacote Alfa",
         "subtitulo": "Marco 5", "etiqueta": { "texto": "FEL2", "tom": "info" },
         "estado": "concluido", "chips": [{ "texto": "Replano", "tom": "alerta" }],
         "data": "2026-09-14", "quantidade": 7,
         "atributos": { "fase": "FEL2" }, "busca": "texto a mais",
         "detalhe": { "titulo": "...", "blocos": [] }
       }]
     }
   - As semanas e o mês de cada uma são do calendário da plataforma e vêm do
     servidor (um ano por entrada de `anos`, com 52 ou 53 semanas); `hoje` é a
     semana de hoje, também do servidor. O item aponta a semana por `ano` e
     `semana`; sem isso, ou numa semana fora do calendário, ele conta em "Sem
     data" e não ganha coluna.
   - `estado` é o id de uma entrada de `legenda`, e o tom dela pinta a faixa do
     cartão (`rotulo_total` é o nome dela nos totais do topo, no plural; sem
     ele vale `rotulo`). O nome do estado fica na dica e para o leitor de
     tela, e a legenda do pé o mostra ao lado do ponto colorido, como no
     original. Os totais do topo contam os itens por estado.
   - `chips` do cartão ficam antes da data; o chip com `depois_da_data: true`
     fica depois dela (no original, a severidade vem antes e o plano depois).
   - `filtros` viram listas de escolha; o item responde por `atributos[id]`. A
     busca olha o título, o subtítulo, a etiqueta, os chips, os atributos e
     `busca`, sem acento nem caixa.
   - Datas em ISO (AAAA-MM-DD); o formato na tela é o da língua do documento.
   - `detalhe` é o painel do clique (ver detalhe.js). Sem ele, o cartão só é
     clicável se tiver `href` ou `selecionavel: true`, e então dispara
     grafico:selecionar com { id, item }.

     <div data-grafico="mapa-52-semanas" data-dados='{{ grafico | tojson }}'></div>

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;
  const P = G.pecas;
  const TIPO = "mapa-52-semanas";
  /* O mesmo espaço entre colunas do graficos.css (--mapa-espaco). */
  const ESPACO = 6;
  const POR_PAGINA = 6;

  const cacheDeBusca = new WeakMap();

  /* ---------- Dados ---------- */

  function semanasDoAno(dados, ano) {
    const entrada = (dados.anos || []).find(function (item) {
      return item.ano === ano;
    });
    return entrada && Array.isArray(entrada.semanas) ? entrada.semanas : [];
  }

  function anoInicial(dados) {
    const anos = (dados.anos || []).map(function (item) {
      return item.ano;
    });
    if (anos.includes(dados.ano)) return dados.ano;
    if (dados.hoje && anos.includes(dados.hoje.ano)) return dados.hoje.ano;
    return anos.length ? anos[anos.length - 1] : null;
  }

  function textoDeBusca(item) {
    if (!cacheDeBusca.has(item)) {
      const partes = [item.titulo, item.subtitulo, item.busca, item.etiqueta ? item.etiqueta.texto : ""];
      (item.chips || []).forEach(function (chip) {
        partes.push(chip.texto);
      });
      Object.values(item.atributos || {}).forEach(function (valor) {
        partes.push(valor);
      });
      cacheDeBusca.set(item, P.normalizar(partes.join(" ")));
    }
    return cacheDeBusca.get(item);
  }

  function passaNosFiltros(item, contexto) {
    const estado = contexto.estado;
    const atributos = item.atributos || {};
    const dentro = (contexto.dados.filtros || []).every(function (filtro) {
      const escolhido = estado.filtros[filtro.id];
      return !escolhido || String(atributos[filtro.id]) === escolhido;
    });
    return dentro && (!estado.busca || textoDeBusca(item).includes(estado.busca));
  }

  function temSemana(item) {
    return Number.isInteger(item.semana) && Number.isInteger(item.ano);
  }

  function itensDoAno(contexto, ano, comFiltros) {
    return (contexto.dados.itens || []).filter(function (item) {
      return temSemana(item) && item.ano === ano && (!comFiltros || passaNosFiltros(item, contexto));
    });
  }

  /* Sem semana, ou numa semana que o calendário não tem. */
  function itensSemData(contexto) {
    const noCalendario = new Set();
    (contexto.dados.anos || []).forEach(function (entrada) {
      semanasDoAno(contexto.dados, entrada.ano).forEach(function (semana) {
        noCalendario.add(entrada.ano + "|" + semana.semana);
      });
    });
    return (contexto.dados.itens || []).filter(function (item) {
      const colocado = temSemana(item) && noCalendario.has(item.ano + "|" + item.semana);
      return !colocado && passaNosFiltros(item, contexto);
    });
  }

  function ordenar(a, b) {
    const dataA = a.data || "9999";
    const dataB = b.data || "9999";
    if (dataA !== dataB) return dataA < dataB ? -1 : 1;
    return String(a.titulo).localeCompare(String(b.titulo), document.documentElement.lang || "pt-BR");
  }

  function agruparPorSemana(itens) {
    const porSemana = new Map();
    itens.forEach(function (item) {
      if (!porSemana.has(item.semana)) porSemana.set(item.semana, []);
      porSemana.get(item.semana).push(item);
    });
    porSemana.forEach(function (lista) {
      lista.sort(ordenar);
    });
    return porSemana;
  }

  function estadoDoItem(item, dados) {
    return (dados.legenda || []).find(function (entrada) {
      return entrada.id === item.estado;
    });
  }

  /* ---------- Cartão ---------- */

  function linhaDaEtiqueta(item) {
    const filhos = [];
    if (item.etiqueta && item.etiqueta.texto) filhos.push(P.chip(item.etiqueta.texto, item.etiqueta.tom, { classe: "graf-mapa__etiqueta" }));
    if (item.subtitulo) filhos.push(G.el("span", { class: "graf-mapa__sub", title: item.subtitulo, texto: item.subtitulo }));
    return filhos.length ? G.el("span", { class: "graf-mapa__linha2" }, filhos) : null;
  }

  function chipDoItem(chip) {
    return P.chip(chip.texto, chip.tom, { icone: chip.icone, classe: "graf-mapa__chip" });
  }

  /* A terceira linha do cartão, na ordem do original: os chips que vêm antes
     da data, a data e os chips marcados com `depois_da_data`. */
  function linhaDoEstado(item) {
    const chips = item.chips || [];
    const antes = chips
      .filter(function (chip) {
        return chip.depois_da_data !== true;
      })
      .map(chipDoItem);
    const depois = chips
      .filter(function (chip) {
        return chip.depois_da_data === true;
      })
      .map(chipDoItem);
    const data = item.data ? [G.el("span", { class: "graf-mapa__data", texto: P.data(item.data, "curta") })] : [];
    const filhos = antes.concat(data, depois);
    return filhos.length ? G.el("span", { class: "graf-mapa__linha3" }, filhos) : null;
  }

  function tagDoCartao(item, interativo) {
    if (item.href) return "a";
    return interativo ? "button" : "div";
  }

  function cartao(item, contexto) {
    const dados = contexto.dados;
    const estado = estadoDoItem(item, dados);
    const filhos = [];
    if (Number.isFinite(item.quantidade)) filhos.push(G.el("span", { class: "graf-mapa__qtd", texto: String(item.quantidade) }));
    filhos.push(G.el("span", { class: "graf-mapa__nome", title: item.titulo, texto: item.titulo }));
    [linhaDaEtiqueta(item), linhaDoEstado(item)].forEach(function (linha) {
      if (linha) filhos.push(linha);
    });
    if (estado) filhos.push(G.el("span", { class: "graf-sr", texto: ", " + estado.rotulo }));
    const interativo = Boolean(item.detalhe) || P.ehSelecionavel(item, dados);
    const atributos = {
      class: "graf-mapa__cartao " + P.classeDoTom(estado ? estado.tom : "cinza"),
      href: item.href,
      type: interativo && !item.href ? "button" : null,
      title: estado ? estado.rotulo : null,
    };
    const raiz = G.el(tagDoCartao(item, interativo), atributos, filhos);
    if (interativo) {
      P.tornarInterativo(raiz, {
        host: contexto.host,
        tipo: TIPO,
        detalhe: { id: item.id, item: item },
        aoAtivar: function () {
          if (item.detalhe) G.detalhe.abrir(item.detalhe);
        },
      });
    }
    return raiz;
  }

  /* ---------- Colunas de semana ---------- */

  function classeDaSemana(ehHoje, indice, porPagina) {
    if (ehHoje) return " is-hoje";
    return Math.floor(indice / porPagina) % 2 ? " is-alt" : "";
  }

  function periodoDaSemana(semana) {
    if (!semana.inicio || !semana.fim) return "";
    return P.data(semana.inicio, "dia") + " – " + P.data(semana.fim, "dia");
  }

  function cabecalhoDaSemana(semana, quantidade) {
    const nome = [G.el("span", { texto: semana.rotulo || "S" + semana.semana })];
    if (Number.isInteger(semana.mes)) nome.push(G.el("em", { class: "graf-mapa__mes", texto: G.nomeMes(semana.mes) }));
    if (quantidade) nome.push(G.el("b", { class: "graf-mapa__contagem", texto: String(quantidade) }));
    return G.el("div", { class: "graf-mapa__cab-semana" }, [
      G.el("div", { class: "graf-mapa__semana-nome" }, nome),
      G.el("div", { class: "graf-mapa__periodo", texto: periodoDaSemana(semana) }),
    ]);
  }

  function colunaDaSemana(semana, itens, indice, contexto) {
    const hoje = contexto.dados.hoje;
    const ehHoje = Boolean(hoje) && hoje.ano === contexto.estado.ano && hoje.semana === semana.semana;
    const cartoes = itens.length
      ? itens.map(function (item) {
          return cartao(item, contexto);
        })
      : [G.el("div", { class: "graf-mapa__vazio", texto: P.VAZIO })];
    return G.el("div", { class: "graf-mapa__semana" + classeDaSemana(ehHoje, indice, contexto.porPagina) }, [
      cabecalhoDaSemana(semana, itens.length),
      G.el("div", { class: "graf-mapa__lista" }, cartoes),
    ]);
  }

  /* ---------- Rolagem ---------- */

  function medidas(contexto) {
    const corpo = contexto.ui.corpo;
    const primeira = corpo.querySelector(".graf-mapa__semana");
    if (!primeira) return null;
    const coluna = primeira.getBoundingClientRect().width + ESPACO;
    return { coluna: coluna, pagina: Math.max(1, Math.round((corpo.clientWidth + ESPACO) / coluna)) * coluna };
  }

  function rolarPara(contexto, esquerda, instantaneo) {
    const reduzido = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    contexto.ui.corpo.scrollTo({ left: Math.max(0, esquerda), behavior: instantaneo || reduzido ? "auto" : "smooth" });
  }

  function rolarPagina(contexto, sentido) {
    const medida = medidas(contexto);
    if (medida) rolarPara(contexto, contexto.ui.corpo.scrollLeft + sentido * medida.pagina, false);
  }

  /* A semana de hoje fica na segunda coluna, com a anterior à esquerda. */
  function irParaHoje(contexto, instantaneo) {
    const hoje = contexto.dados.hoje;
    const medida = medidas(contexto);
    if (!medida) return;
    if (!hoje || hoje.ano !== contexto.estado.ano) {
      rolarPara(contexto, 0, instantaneo);
      return;
    }
    const indice = semanasDoAno(contexto.dados, hoje.ano).findIndex(function (semana) {
      return semana.semana === hoje.semana;
    });
    if (indice >= 0) rolarPara(contexto, medida.coluna * Math.max(0, indice - 1), instantaneo);
  }

  /* ---------- Topo e rodapé ---------- */

  function kpisDoMapa(contexto, visiveis, semData) {
    const dados = contexto.dados;
    const kpis = [{ rotulo: P.rotulo(dados, "itens"), valor: visiveis.length, tom: "cinza" }];
    (dados.legenda || []).forEach(function (entrada) {
      const quantos = visiveis.filter(function (item) {
        return item.estado === entrada.id;
      }).length;
      kpis.push({ rotulo: entrada.rotulo_total || entrada.rotulo, valor: quantos, tom: entrada.tom });
    });
    (dados.kpis_extras || []).forEach(function (extra) {
      kpis.push(extra);
    });
    if (semData.length) kpis.push({ rotulo: P.rotulo(dados, "semData"), valor: semData.length, tom: "info" });
    return kpis;
  }

  function elementoDeKpi(kpi) {
    return G.el("div", { class: "graf-mapa__kpi " + P.classeDoTom(kpi.tom) }, [
      G.el("b", { texto: String(kpi.valor) }),
      G.el("span", { texto: kpi.rotulo }),
    ]);
  }

  function textoDoRodape(contexto, semData) {
    const dados = contexto.dados;
    const semanas = semanasDoAno(dados, contexto.estado.ano).length;
    const partes = [contexto.estado.ano + " — " + semanas + " " + P.rotulo(dados, "semanas")];
    if (semData.length) partes.push(P.rotulo(dados, "semData") + ": " + semData.length + " (" + P.rotulo(dados, "semColuna") + ")");
    return partes.join("  •  ");
  }

  function desenharBotoesDeAno(contexto) {
    contexto.ui.botoesDeAno.forEach(function (item) {
      const ativo = item.ano === contexto.estado.ano;
      item.botao.classList.toggle("is-ativo", ativo);
      item.botao.setAttribute("aria-pressed", ativo ? "true" : "false");
      item.contador.textContent = "(" + itensDoAno(contexto, item.ano, true).length + ")";
    });
  }

  /* Refaz o que muda com o ano, o filtro e a busca; os controles ficam. */
  function renderizar(contexto, irAoAtual) {
    const dados = contexto.dados;
    const ano = contexto.estado.ano;
    const visiveis = itensDoAno(contexto, ano, true);
    const semData = itensSemData(contexto);
    const porSemana = agruparPorSemana(visiveis);
    const semanas = semanasDoAno(dados, ano);
    contexto.ui.kpis.replaceChildren(...kpisDoMapa(contexto, visiveis, semData).map(elementoDeKpi));
    desenharBotoesDeAno(contexto);
    if (!visiveis.length) {
      contexto.ui.corpo.replaceChildren(G.el("div", { class: "graf-mapa__nada", texto: P.rotulo(dados, "nenhumResultado") }));
    } else {
      contexto.ui.corpo.replaceChildren(
        ...semanas.map(function (semana, indice) {
          return colunaDaSemana(semana, porSemana.get(semana.semana) || [], indice, contexto);
        }),
      );
    }
    contexto.ui.contagem.replaceChildren(G.el("b", { texto: String(visiveis.length) }), "/" + itensDoAno(contexto, ano, false).length);
    contexto.ui.rodape.textContent = textoDoRodape(contexto, semData);
    if (irAoAtual) irParaHoje(contexto, true);
  }

  /* ---------- Montagem ---------- */

  function montarAnos(contexto) {
    contexto.ui.botoesDeAno = (contexto.dados.anos || []).map(function (entrada) {
      const contador = G.el("i", { texto: "" });
      const botao = G.el("button", { type: "button", class: "graf-mapa__ano" }, [String(entrada.ano), contador]);
      botao.addEventListener("click", function () {
        contexto.estado.ano = entrada.ano;
        renderizar(contexto, true);
      });
      return { ano: entrada.ano, botao: botao, contador: contador };
    });
    return G.el(
      "div",
      { class: "graf-mapa__anos", role: "group", "aria-label": P.rotulo(contexto.dados, "ano") },
      contexto.ui.botoesDeAno.map(function (item) {
        return item.botao;
      }),
    );
  }

  function montarCabecalho(contexto) {
    const dados = contexto.dados;
    const titulos = [];
    if (dados.titulo) titulos.push(G.el("div", { class: "graf-mapa__titulo", texto: dados.titulo }));
    if (dados.subtitulo) titulos.push(G.el("div", { class: "graf-mapa__subtitulo", texto: dados.subtitulo }));
    contexto.ui.kpis = G.el("div", { class: "graf-mapa__kpis" });
    return G.el("div", { class: "graf-mapa__cab" }, [G.el("div", { class: "graf-mapa__titulos" }, titulos), contexto.ui.kpis, montarAnos(contexto)]);
  }

  function seletorDeFiltro(filtro, contexto) {
    const opcoes = [G.el("option", { value: "", texto: filtro.rotulo + ": " + P.rotulo(contexto.dados, "todos") })];
    (filtro.opcoes || []).forEach(function (opcao) {
      opcoes.push(G.el("option", { value: String(opcao.id), texto: opcao.rotulo }));
    });
    const seletor = G.el("select", { class: "graf-mapa__filtro", "aria-label": filtro.rotulo }, opcoes);
    seletor.addEventListener("change", function () {
      contexto.estado.filtros[filtro.id] = seletor.value;
      seletor.classList.toggle("is-ativo", seletor.value !== "");
      renderizar(contexto, false);
    });
    return seletor;
  }

  function campoDeBusca(contexto) {
    const campo = G.el("input", { type: "search", class: "graf-mapa__busca", placeholder: P.rotulo(contexto.dados, "buscar"), "aria-label": P.rotulo(contexto.dados, "buscar") });
    campo.addEventListener("input", function () {
      contexto.estado.busca = P.normalizar(campo.value.trim());
      renderizar(contexto, false);
    });
    return campo;
  }

  function botaoDeNavegacao(texto, rotulo, aoClicar) {
    const botao = G.el("button", { type: "button", class: "graf-mapa__nav", "aria-label": rotulo, title: rotulo, texto: texto });
    botao.addEventListener("click", aoClicar);
    return botao;
  }

  function montarBarra(contexto) {
    const dados = contexto.dados;
    contexto.ui.contagem = G.el("div", { class: "graf-mapa__contagem-total", "aria-live": "polite" });
    const navegacao = G.el("div", { class: "graf-mapa__navegacao" }, [
      botaoDeNavegacao("‹", P.rotulo(dados, "semanasAnteriores"), function () {
        rolarPagina(contexto, -1);
      }),
      botaoDeNavegacao(P.rotulo(dados, "hoje"), P.rotulo(dados, "hoje"), function () {
        irParaHoje(contexto, false);
      }),
      botaoDeNavegacao("›", P.rotulo(dados, "proximasSemanas"), function () {
        rolarPagina(contexto, 1);
      }),
    ]);
    const filtros = (dados.filtros || []).map(function (filtro) {
      return seletorDeFiltro(filtro, contexto);
    });
    return G.el("div", { class: "graf-mapa__barra" }, [campoDeBusca(contexto)].concat(filtros, [navegacao, contexto.ui.contagem]));
  }

  function montarRodape(contexto) {
    const itens = P.itensDeLegenda(contexto.dados.legenda || []);
    contexto.ui.rodape = G.el("div", { class: "graf-mapa__situacao" });
    return G.el("div", { class: "graf-mapa__pe" }, [itens.length ? P.legenda(itens, P.rotulo(contexto.dados, "legenda"), { pontos: true }) : null, contexto.ui.rodape].filter(Boolean));
  }

  G.registrar(TIPO, function (host, dados) {
    const ano = anoInicial(dados);
    if (ano === null) {
      G.mostrarMensagem(host, G.rotulo(dados, "vazio"));
      return null;
    }
    const filtros = {};
    const contexto = {
      dados: dados,
      host: host,
      estado: { ano: ano, busca: "", filtros: filtros },
      porPagina: Number.isInteger(dados.por_pagina) && dados.por_pagina > 0 ? dados.por_pagina : POR_PAGINA,
      ui: {},
    };
    contexto.ui.corpo = G.el("div", { class: "graf-mapa__corpo", role: "region", tabindex: "0", "aria-label": dados.titulo || P.rotulo(dados, "semana") });
    const raiz = G.el("div", { class: "graf-mapa" }, [montarCabecalho(contexto), montarBarra(contexto), contexto.ui.corpo, montarRodape(contexto)]);
    raiz.style.setProperty("--mapa-por-pagina", String(contexto.porPagina));
    host.replaceChildren(raiz);
    renderizar(contexto, false);
    window.requestAnimationFrame(function () {
      irParaHoje(contexto, true);
    });
    return null;
  });
})();
