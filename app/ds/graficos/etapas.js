/* ============================================================
   graficos/etapas.js — Etapas

   Porte de "Etapas.html" (docs/referencia/graficos/), a régua de etapas: uma
   linha por item (projeto, solicitação, RNC), com a faixa colorida do estado
   geral, o nome e as etiquetas, a régua das etapas (cada uma com a barra, o
   estado, a data e, quando há mais de uma atividade, a quantidade) e as datas
   de referência à direita. No cabeçalho, cada etapa traz os filtros por estado
   com a contagem; a legenda, a quantidade de itens e o botão Limpar filtros
   ficam em cima. O clique na linha abre o detalhe. Serve as etapas do processo
   de compra, o fluxo da SM e o ciclo da RNC.

   Contrato dos dados (data-dados):
     {
       "titulo": "Processo de compra", "rotulo_linhas": "Solicitação",
       "etapas": [{ "id": "req", "rotulo": "Requisição" }],
       "estados": [
         { "id": "concluido", "rotulo": "Concluído", "tom": "ok" },
         { "id": "andamento", "rotulo": "Em andamento", "tom": "alerta" },
         { "id": "nao_iniciado", "rotulo": "Não iniciado", "tom": "atencao" },
         { "id": "na", "rotulo": "N/A", "tom": "cinza", "padrao": true }
       ],
       "colunas_datas": ["Prevista", "Linha de base"],
       "linhas": [{
         "id": "SM-0012", "titulo": "SM-0012", "tags": ["Elétrica"],
         "estado": "andamento",
         "etapas": { "req": { "estado": "concluido", "data": "2026-08-29",
                              "previsto": false, "quantidade": 2, "texto": "Concluído" } },
         "datas": ["2027-01-16", null],
         "detalhe": { "titulo": "SM-0012", "blocos": [] }
       }],
       "selecionavel": true
     }
   - `estados` é o vocabulário: o nome e o tom (ver pecas.js) de cada estado,
     que pintam a barra, o texto e o ícone da etapa, a faixa da linha, a legenda
     e os filtros; o estado nunca é só cor, porque leva o ícone do tom e o nome.
     O de `padrao: true` (ou o último) vale para a etapa que a linha não traz.
   - O estado geral da linha (`estado`) é regra de negócio e vem do servidor;
     sem ele, a faixa fica cinza. `texto` troca o nome do estado na etapa; `data`
     é a conclusão, ou a previsão quando `previsto: true` (aparece "Prev.").
   - Os filtros se somam por etapa (mais de um estado na mesma etapa vale como
     "ou") e entre etapas (valem como "e"); a contagem de cada botão ignora o
     filtro da própria etapa, como no original.
   - Datas em ISO; o formato é o da língua do documento. `datas` acompanha
     `colunas_datas`.
   - `detalhe` é o painel do clique (ver detalhe.js). Sem ele, a linha só é
     clicável com `href` ou `selecionavel: true`, e dispara grafico:selecionar
     com { id, item }.

     <div data-grafico="etapas" data-dados='{{ grafico | tojson }}'></div>

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;
  const P = G.pecas;
  const TIPO = "etapas";

  /* ---------- Estados ---------- */

  function estadoPadrao(dados) {
    const estados = dados.estados || [];
    return (
      estados.find(function (estado) {
        return estado.padrao === true;
      }) || estados[estados.length - 1]
    );
  }

  function estadoPorId(dados, id) {
    return (dados.estados || []).find(function (estado) {
      return estado.id === id;
    });
  }

  /* O estado da linha numa etapa; a etapa que ela não traz é o estado padrão. */
  function estadoDaEtapa(linha, etapa, dados) {
    const dadosDaEtapa = linha.etapas ? linha.etapas[etapa.id] : undefined;
    return (dadosDaEtapa && estadoPorId(dados, dadosDaEtapa.estado)) || estadoPadrao(dados);
  }

  /* ---------- Filtros ---------- */

  function passaNosFiltros(linha, contexto, exceto) {
    return contexto.dados.etapas.every(function (etapa) {
      const escolhidos = contexto.filtros[etapa.id];
      if (etapa.id === exceto || !escolhidos.size) return true;
      return escolhidos.has(estadoDaEtapa(linha, etapa, contexto.dados).id);
    });
  }

  function haFiltro(contexto) {
    return Object.values(contexto.filtros).some(function (escolhidos) {
      return escolhidos.size > 0;
    });
  }

  /* ---------- Linha ---------- */

  function textoDaData(dadosDaEtapa) {
    if (!dadosDaEtapa || !dadosDaEtapa.data) return P.VAZIO;
    const data = P.data(dadosDaEtapa.data, "curta");
    return dadosDaEtapa.previsto === true ? "Prev. " + data : data;
  }

  function elementoDaEtapa(linha, etapa, contexto) {
    const dados = contexto.dados;
    const estado = estadoDaEtapa(linha, etapa, dados);
    const dadosDaEtapa = linha.etapas ? linha.etapas[etapa.id] : undefined;
    const nome = dadosDaEtapa && dadosDaEtapa.texto ? dadosDaEtapa.texto : estado.rotulo;
    const icone = P.icone(P.nomeDoIcone(estado.icone, estado.tom), 12);
    const rotulo = [icone, G.el("span", { class: "graf-etapas__nome-estado", texto: nome })];
    if (dadosDaEtapa && dadosDaEtapa.quantidade > 1) rotulo.push(G.el("span", { class: "graf-etapas__qtd", texto: String(dadosDaEtapa.quantidade) }));
    return G.el("div", { class: "graf-etapas__etapa " + P.classeDoTom(estado.tom), title: etapa.rotulo + ": " + nome }, [
      G.el("div", { class: "graf-etapas__barra" }),
      G.el("div", { class: "graf-etapas__estado" }, rotulo.filter(Boolean)),
      G.el("div", { class: "graf-etapas__data" + (dadosDaEtapa && dadosDaEtapa.previsto === true ? " is-previsto" : ""), texto: textoDaData(dadosDaEtapa) }),
    ]);
  }

  function blocoDeIdentificacao(linha) {
    const tags = (linha.tags || []).map(function (tag) {
      return G.el("span", { class: "graf-etapas__tag", title: tag, texto: tag });
    });
    return G.el("div", { class: "graf-etapas__id" }, [G.el("div", { class: "graf-etapas__projeto", title: linha.titulo, texto: linha.titulo }), G.el("div", { class: "graf-etapas__tags" }, tags)]);
  }

  function blocoDeDatas(linha, dados) {
    const rotulos = dados.colunas_datas || [];
    const caixas = rotulos.map(function (rotulo, indice) {
      const valor = linha.datas ? linha.datas[indice] : null;
      return G.el("div", { class: "graf-etapas__data-caixa" }, [
        G.el("span", { class: "graf-etapas__data-rot", texto: rotulo }),
        G.el("b", { class: "graf-etapas__data-val", texto: valor ? P.data(valor, "curta") : P.VAZIO }),
      ]);
    });
    return G.el("div", { class: "graf-etapas__datas" }, caixas);
  }

  function tomDaLinha(linha, dados) {
    const estado = estadoPorId(dados, linha.estado);
    return estado ? estado.tom : "cinza";
  }

  function elementoDaLinha(linha, contexto) {
    const dados = contexto.dados;
    const estadoGeral = estadoPorId(dados, linha.estado);
    const regua = G.el(
      "div",
      { class: "graf-etapas__regua" },
      dados.etapas.map(function (etapa) {
        return elementoDaEtapa(linha, etapa, contexto);
      }),
    );
    const filhos = [blocoDeIdentificacao(linha), regua, blocoDeDatas(linha, dados)];
    if (estadoGeral) filhos.push(G.el("span", { class: "graf-sr", texto: ", " + estadoGeral.rotulo }));
    const raiz = G.el(linha.href ? "a" : "div", { class: "graf-etapas__linha " + P.classeDoTom(tomDaLinha(linha, dados)), href: linha.href }, filhos);
    if (Boolean(linha.detalhe) || P.ehSelecionavel(linha, dados)) {
      P.tornarInterativo(raiz, {
        host: contexto.host,
        tipo: TIPO,
        detalhe: { id: linha.id, item: linha },
        aoAtivar: function () {
          if (linha.detalhe) G.detalhe.abrir(linha.detalhe);
        },
      });
    }
    return raiz;
  }

  /* ---------- Cabeçalho e filtros ---------- */

  function botaoDeFiltro(etapa, estado, contexto) {
    const contador = G.el("span", { class: "graf-etapas__contagem", texto: "0" });
    const icone = P.icone(P.nomeDoIcone(estado.icone, estado.tom), 10);
    const botao = G.el(
      "button",
      { type: "button", class: "graf-etapas__filtro " + P.classeDoTom(estado.tom), "aria-pressed": "false" },
      [icone, contador].filter(Boolean),
    );
    botao.addEventListener("click", function () {
      const escolhidos = contexto.filtros[etapa.id];
      if (escolhidos.has(estado.id)) {
        escolhidos.delete(estado.id);
      } else {
        escolhidos.add(estado.id);
      }
      atualizar(contexto);
    });
    contexto.botoes.push({ etapaId: etapa.id, estadoId: estado.id, botao: botao, contador: contador, rotulo: etapa.rotulo + " · " + estado.rotulo });
    return botao;
  }

  function cabecalhoDaEtapa(etapa, indice, contexto) {
    const filtros = (contexto.dados.estados || []).map(function (estado) {
      return botaoDeFiltro(etapa, estado, contexto);
    });
    return G.el("div", { class: "graf-etapas__cab-etapa" }, [
      G.el("span", { class: "graf-etapas__indice", "aria-hidden": "true", texto: String(indice + 1).padStart(2, "0") }),
      G.el("span", { class: "graf-etapas__cab-nome", texto: etapa.rotulo }),
      G.el("div", { class: "graf-etapas__filtros", role: "group", "aria-label": etapa.rotulo + " · " + P.rotulo(contexto.dados, "filtros") }, filtros),
    ]);
  }

  function cabecalhoDoQuadro(contexto) {
    const dados = contexto.dados;
    return G.el("div", { class: "graf-etapas__cab" }, [
      G.el("div", { class: "graf-etapas__cab-id", texto: dados.rotulo_linhas || "" }),
      G.el(
        "div",
        { class: "graf-etapas__regua" },
        dados.etapas.map(function (etapa, indice) {
          return cabecalhoDaEtapa(etapa, indice, contexto);
        }),
      ),
      G.el(
        "div",
        { class: "graf-etapas__datas" },
        (dados.colunas_datas || []).map(function (rotulo) {
          return G.el("div", { class: "graf-etapas__cab-data", texto: rotulo });
        }),
      ),
    ]);
  }

  /* ---------- Atualização ---------- */

  function contarNaEtapa(contexto, item) {
    const base = contexto.dados.linhas.filter(function (linha) {
      return passaNosFiltros(linha, contexto, item.etapaId);
    });
    const etapa = contexto.dados.etapas.find(function (candidata) {
      return candidata.id === item.etapaId;
    });
    return base.filter(function (linha) {
      return estadoDaEtapa(linha, etapa, contexto.dados).id === item.estadoId;
    }).length;
  }

  function atualizarFiltros(contexto) {
    contexto.botoes.forEach(function (item) {
      const quantos = contarNaEtapa(contexto, item);
      const ativo = contexto.filtros[item.etapaId].has(item.estadoId);
      item.contador.textContent = String(quantos);
      item.botao.classList.toggle("is-ativo", ativo);
      item.botao.classList.toggle("is-zero", quantos === 0);
      item.botao.setAttribute("aria-pressed", ativo ? "true" : "false");
      item.botao.setAttribute("aria-label", item.rotulo + ": " + quantos);
      item.botao.title = item.rotulo + ": " + quantos;
    });
  }

  function atualizar(contexto) {
    const dados = contexto.dados;
    const visiveis = dados.linhas.filter(function (linha) {
      return passaNosFiltros(linha, contexto, null);
    });
    const total = dados.linhas.length;
    contexto.ui.lista.replaceChildren(
      ...(visiveis.length
        ? visiveis.map(function (linha) {
            return elementoDaLinha(linha, contexto);
          })
        : [G.el("div", { class: "graf-etapas__nada", texto: P.rotulo(dados, "nenhumResultado") })]),
    );
    const nome = P.rotulo(dados, "itens");
    contexto.ui.kpi.replaceChildren(G.el("b", { texto: String(visiveis.length) }), G.el("span", { texto: visiveis.length === total ? nome : P.rotulo(dados, "de") + " " + total + " " + nome }));
    contexto.ui.limpar.hidden = !haFiltro(contexto);
    atualizarFiltros(contexto);
  }

  /* ---------- Montagem ---------- */

  function montarTopo(contexto) {
    const dados = contexto.dados;
    contexto.ui.kpi = G.el("div", { class: "graf-etapas__kpi", "aria-live": "polite" });
    contexto.ui.limpar = G.el("button", { type: "button", class: "graf-etapas__limpar", hidden: true, texto: P.rotulo(dados, "limparFiltros") });
    contexto.ui.limpar.addEventListener("click", function () {
      Object.values(contexto.filtros).forEach(function (escolhidos) {
        escolhidos.clear();
      });
      atualizar(contexto);
    });
    const itensDaLegenda = (dados.estados || []).map(function (estado) {
      return { rotulo: estado.rotulo, tom: estado.tom, icone: estado.icone };
    });
    return G.el("div", { class: "graf-etapas__topo" }, [
      dados.titulo ? G.el("div", { class: "graf-etapas__titulo", texto: dados.titulo }) : G.el("div"),
      contexto.ui.kpi,
      P.legenda(itensDaLegenda, P.rotulo(dados, "legenda")),
      contexto.ui.limpar,
    ]);
  }

  G.registrar(TIPO, function (host, dados) {
    const etapas = Array.isArray(dados.etapas) ? dados.etapas : [];
    const linhas = Array.isArray(dados.linhas) ? dados.linhas : [];
    if (!etapas.length || !(dados.estados || []).length || !linhas.length) {
      G.mostrarMensagem(host, G.rotulo(dados, "vazio"));
      return null;
    }
    const filtros = {};
    etapas.forEach(function (etapa) {
      filtros[etapa.id] = new Set();
    });
    const contexto = { dados: dados, host: host, filtros: filtros, botoes: [], ui: { lista: G.el("div", { class: "graf-etapas__lista" }) } };
    const topo = montarTopo(contexto);
    const quadro = G.el("div", { class: "graf-etapas__quadro" }, [cabecalhoDoQuadro(contexto), contexto.ui.lista]);
    const raiz = G.el("div", { class: "graf-etapas" }, [topo, quadro]);
    raiz.style.setProperty("--etapas-n", String(etapas.length));
    raiz.style.setProperty("--etapas-datas", String((dados.colunas_datas || []).length));
    host.replaceChildren(raiz);
    atualizar(contexto);
    return null;
  });
})();
