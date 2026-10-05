/* ============================================================
   graficos/pecas.js — Peças comuns dos cards, matrizes e tabelas

   O que os visuais da ISSUE-015 (cards, faixa de KPI, severidade, matriz,
   mapa de calor, mapa de 52 semanas, quantitativos e etapas) têm em comum,
   para cada um não refazer a sua:

     - tom: o servidor fala em tom (ok, alerta, atencao, erro, info, neutro,
       roxo, cinza), que é uma família do Design System. O tom não leva cor:
       a classe .graf-tom.is-<tom> do graficos.css lê os tokens.
     - ícone de estado, desenhado em SVG: o sinal além da cor (D1). Cada tom
       tem um ícone de silhueta própria (círculo com visto, triângulo,
       losango, círculo com exclamação...), então daltônico e leitor de tela
       não dependem da cor.
     - faixa: valor -> { tom, nivel (intensidade 1 a 3), icone, rotulo }.
       Quem define os limites é o servidor (parâmetros do projeto); aqui só
       se escolhe a faixa de um valor.
     - formatação de valor, de diferença e de data; busca sem acento.
     - chip, legenda e célula de valor.
     - o evento grafico:selecionar, para o item clicável avisar a tela.

   Faixa. Uma faixa tem de zero a quatro limites e vale quando todos eles
   valem; a primeira que vale ganha, então a lista vai da mais específica
   para a mais geral:

     { "de": 5, "ate": 10, "tom": "erro", "nivel": 2,
       "icone": "sobe", "rotulo": "Sobrecusto de 5% a 10%" }

   `de` é maior ou igual, `maior_que` é maior, `ate` é menor ou igual e
   `menor_que` é menor. Sem limite nenhum a faixa vale para tudo (a última).
   `vazia: true` desenha a célula esmaecida, sem pílula (o zero do mapa de
   calor). `id` deixa a célula escolher a faixa pelo nome, quando a faixa
   não depende do valor (a matriz P x I depende da posição, não da contagem).

   Evento. O item com `href` vira link; o item com `selecionavel: true` (ou
   dentro de um visual com `selecionavel: true` no topo) vira botão. O clique
   dispara no elemento do gráfico o evento grafico:selecionar, que sobe pela
   página e pode ser cancelado, com detail = { tipo, id, ... }. A tela o ouve
   por Alpine, sem script no fragmento:

     <div data-grafico="matriz-formatada" data-dados='{{ grafico | tojson }}'
          @grafico:selecionar.prevent="$ajax('/riscos/registro?celula=' + $event.detail.id)"></div>

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;

  const VAZIO = "–";

  /* ---------- Rótulos de interface ----------
     Padrão em português; o servidor troca em `rotulos` (D13). */

  const ROTULOS = {
    total: "Total",
    geral: "Geral",
    expandirTudo: "Expandir tudo",
    recolherTudo: "Recolher tudo",
    expandir: "Expandir",
    recolher: "Recolher",
    limparFiltros: "Limpar filtros",
    buscar: "Buscar...",
    voltar: "Voltar",
    caminho: "Caminho",
    hoje: "Hoje",
    semanasAnteriores: "Semanas anteriores",
    proximasSemanas: "Próximas semanas",
    semana: "Semana",
    semData: "Sem data",
    semColuna: "não têm coluna",
    semanas: "semanas",
    itens: "Itens",
    fechar: "Fechar",
    nenhumResultado: "Nenhum item atende aos filtros.",
    nenhumRegistro: "Nenhum registro.",
    previsto: "Prev.",
    de: "de",
    status: "Status",
    filtros: "Filtros",
    legenda: "Legenda",
    mostrando: "Mostrando",
    atividades: "atividades",
  };

  function rotulo(dados, chave) {
    const doServidor = dados && dados.rotulos ? dados.rotulos[chave] : undefined;
    if (doServidor !== undefined) return doServidor;
    return Object.hasOwn(ROTULOS, chave) ? ROTULOS[chave] : G.rotulo(dados, chave);
  }

  /* ---------- Tons ---------- */

  const TONS = ["ok", "alerta", "atencao", "erro", "info", "neutro", "roxo", "cinza"];

  /* O nome da família do Design System e o do estado de negócio também valem. */
  const APELIDOS = {
    warn: "alerta",
    azul: "info",
    frio: "neutro",
    sucesso: "ok",
    critico: "erro",
    atraso: "erro",
    comprometido: "roxo",
    vazio: "cinza",
  };

  function tom(nome) {
    const chave = Object.hasOwn(APELIDOS, nome) ? APELIDOS[nome] : nome;
    return TONS.includes(chave) ? chave : "cinza";
  }

  /* `nivel` (1 a 3) é a intensidade da célula de mapa de calor. */
  function classeDoTom(nome, nivel) {
    return "graf-tom is-" + tom(nome) + (nivel ? " is-nivel-" + nivel : "");
  }

  /* ---------- Ícones ----------
     Formas de 20 x 20 no traço do Design System (icons.js); as quatro de
     estado repetem as de lá (checkCircle, warning, errorCircle, info) e o
     losango é do tom "atencao", para ele não se confundir com o triângulo. */

  const PONTO = { cx: 10, fill: "currentColor", stroke: "none", r: 0.7 };

  const ICONES = {
    ok: [["circle", { cx: 10, cy: 10, r: 6.8 }], ["path", { d: "m6.9 10.3 2.1 2.1 4.1-4.6" }]],
    alerta: [
      ["path", { d: "M10 3.4 17.4 16a.7.7 0 0 1-.6 1H3.2a.7.7 0 0 1-.6-1L10 3.4ZM10 8v3.6" }],
      ["circle", Object.assign({ cy: 14.2 }, PONTO)],
    ],
    atencao: [
      ["path", { d: "M10 2.8 17.2 10 10 17.2 2.8 10 10 2.8ZM10 6.8v3.4" }],
      ["circle", Object.assign({ cy: 12.9 }, PONTO)],
    ],
    erro: [
      ["circle", { cx: 10, cy: 10, r: 6.8 }],
      ["path", { d: "M10 6.4v4.2" }],
      ["circle", Object.assign({ cy: 13.4 }, PONTO)],
    ],
    info: [
      ["circle", { cx: 10, cy: 10, r: 6.8 }],
      ["path", { d: "M10 9.4v4" }],
      ["circle", Object.assign({ cy: 6.6 }, PONTO)],
    ],
    ponto: [["circle", { cx: 10, cy: 10, r: 2.6, fill: "currentColor", stroke: "none" }]],
    sobe: [["path", { d: "M10 5.2 16 14.6H4L10 5.2Z", fill: "currentColor" }]],
    desce: [["path", { d: "M10 14.8 4 5.4h12L10 14.8Z", fill: "currentColor" }]],
    igual: [["path", { d: "M5 8h10M5 12h10" }]],
  };

  /* O ícone que cada tom leva quando a faixa não manda outro. */
  const ICONE_DO_TOM = {
    ok: "ok",
    alerta: "alerta",
    atencao: "atencao",
    erro: "erro",
    info: "info",
    neutro: "ponto",
    roxo: "info",
    cinza: "ponto",
  };

  /* `preferido` é o nome que veio do dado; false ou "nenhum" tira o ícone. */
  function nomeDoIcone(preferido, tomDoItem) {
    if (preferido === false || preferido === "nenhum") return null;
    if (typeof preferido === "string" && Object.hasOwn(ICONES, preferido)) return preferido;
    return ICONE_DO_TOM[tom(tomDoItem)];
  }

  function icone(nome, tamanho) {
    const formas = ICONES[nome];
    if (!formas) return null;
    return G.svg(
      "svg",
      {
        class: "graf-icone",
        width: tamanho || 14,
        height: tamanho || 14,
        viewBox: "0 0 20 20",
        fill: "none",
        stroke: "currentColor",
        "stroke-width": 1.6,
        "stroke-linecap": "round",
        "stroke-linejoin": "round",
        "aria-hidden": "true",
      },
      formas.map(function (forma) {
        return G.svg(forma[0], forma[1]);
      }),
    );
  }

  /* ---------- Faixas ---------- */

  function atende(valor, faixa) {
    if (Number.isFinite(faixa.de) && valor < faixa.de) return false;
    if (Number.isFinite(faixa.maior_que) && valor <= faixa.maior_que) return false;
    if (Number.isFinite(faixa.ate) && valor > faixa.ate) return false;
    if (Number.isFinite(faixa.menor_que) && valor >= faixa.menor_que) return false;
    return true;
  }

  function nivelDe(faixa) {
    const valido = Number.isInteger(faixa.nivel) && faixa.nivel >= 1 && faixa.nivel <= 3;
    return valido ? faixa.nivel : 1;
  }

  function normalizarFaixa(faixa) {
    return {
      id: faixa.id,
      rotulo: faixa.rotulo,
      tom: tom(faixa.tom),
      nivel: nivelDe(faixa),
      icone: faixa.icone,
      vazia: faixa.vazia === true,
    };
  }

  /* Uma lista, ou um objeto de listas com nome (semana, mes, total...). */
  function todasAsFaixas(faixas) {
    if (Array.isArray(faixas)) return faixas;
    if (faixas && typeof faixas === "object") {
      return Object.values(faixas).filter(Array.isArray).flat();
    }
    return [];
  }

  function conjuntoDeFaixas(faixas, nome) {
    if (Array.isArray(faixas)) return faixas;
    if (faixas && typeof faixas === "object") {
      if (Array.isArray(faixas[nome])) return faixas[nome];
      return Array.isArray(faixas.padrao) ? faixas.padrao : [];
    }
    return [];
  }

  function faixaDe(valor, faixas) {
    if (!Number.isFinite(valor) || !Array.isArray(faixas)) return null;
    const achada = faixas.find(function (faixa) {
      return atende(valor, faixa);
    });
    return achada ? normalizarFaixa(achada) : null;
  }

  function faixaPorId(faixas, id) {
    const achada = todasAsFaixas(faixas).find(function (faixa) {
      return faixa.id === id;
    });
    return achada ? normalizarFaixa(achada) : null;
  }

  /* A faixa que a célula manda (`faixa`: id), ou a do valor no conjunto. */
  function faixaDaCelula(bruto, conjunto, todas) {
    const ehObjeto = bruto !== null && typeof bruto === "object";
    if (ehObjeto && bruto.faixa !== undefined) return faixaPorId(todas, bruto.faixa);
    return faixaDe(ehObjeto ? bruto.valor : bruto, conjunto);
  }

  /* Estado pelos limites e pela meta: a partir de `ok` é ok; a partir de
     `alerta`, alerta; abaixo, erro. Sem limites vale a meta e, sem meta ou
     sem valor, é cinza. É a regra dos Relógios (relogios.js). */
  function estadoPorLimites(valor, meta, limites) {
    if (!Number.isFinite(valor)) return "cinza";
    const lim = limites || {};
    const minimoDoOk = Number.isFinite(lim.ok) ? lim.ok : meta;
    if (!Number.isFinite(minimoDoOk)) return "cinza";
    if (valor >= minimoDoOk) return "ok";
    return Number.isFinite(lim.alerta) && valor >= lim.alerta ? "alerta" : "erro";
  }

  /* As faixas com nome, uma vez cada, para a legenda. */
  function itensDeLegenda(faixas) {
    const vistos = new Set();
    const itens = [];
    todasAsFaixas(faixas).forEach(function (faixa) {
      const normal = normalizarFaixa(faixa);
      const chave = normal.tom + "|" + normal.nivel + "|" + normal.rotulo;
      if (!normal.rotulo || vistos.has(chave)) return;
      vistos.add(chave);
      itens.push(normal);
    });
    return itens;
  }

  /* ---------- Valor, diferença, data e busca ---------- */

  function casasDe(item, padroes) {
    if (Number.isInteger(item.casas)) return item.casas;
    return padroes && Number.isInteger(padroes.casas) ? padroes.casas : 0;
  }

  function unidadeDe(item, padroes) {
    if (typeof item.unidade === "string") return item.unidade;
    return padroes && typeof padroes.unidade === "string" ? padroes.unidade : "";
  }

  function comSinalDe(item, padroes) {
    if (item.sinal !== undefined) return item.sinal === true;
    return Boolean(padroes && padroes.sinal === true);
  }

  /* `texto` pronto do servidor vence; senão, número com casas, sinal opcional
     e unidade; sem valor, o traço. */
  function textoDoValor(item, padroes) {
    if (typeof item.texto === "string") return item.texto;
    if (!Number.isFinite(item.valor)) return VAZIO;
    const casas = casasDe(item, padroes);
    const numero = comSinalDe(item, padroes) ? G.fmt.comSinal(item.valor, casas) : G.fmt.numero(item.valor, casas);
    return numero + unidadeDe(item, padroes);
  }

  /* A célula é um número ou um objeto { valor, texto, faixa, id, href... }. */
  function valorDaCelula(bruto) {
    if (bruto !== null && typeof bruto === "object") return bruto.valor;
    return bruto;
  }

  /* Soma os que são número; sem nenhum, nulo (sem dado não é zero). */
  function somar(valores) {
    let total = null;
    valores.forEach(function (valor) {
      if (Number.isFinite(valor)) total = (total === null ? 0 : total) + valor;
    });
    return total;
  }

  /* O valor próprio da linha (o que `ler` devolve) ou, sendo pai sem valor
     próprio, a soma dos filhos; folha sem valor, nulo. */
  function valorDaArvore(linha, ler) {
    const proprio = ler(linha);
    if (proprio !== undefined) return proprio;
    if (!Array.isArray(linha.filhos) || !linha.filhos.length) return null;
    return somar(
      linha.filhos.map(function (filho) {
        return valorDaCelula(valorDaArvore(filho, ler));
      }),
    );
  }

  /* Formato da coluna: o dela e, onde ela não diz, o do topo. */
  function padroesDaColuna(coluna, dados) {
    return {
      casas: Number.isInteger(coluna.casas) ? coluna.casas : dados.casas,
      unidade: typeof coluna.unidade === "string" ? coluna.unidade : dados.unidade,
      sinal: coluna.sinal !== undefined ? coluna.sinal : dados.sinal,
    };
  }

  /* O total de uma lista de itens com `valor`: o `total` que o servidor mandou
     ou, sem ele, a soma. */
  function totalDosItens(dados, itens) {
    if (Number.isFinite(dados.total)) return dados.total;
    return (
      somar(
        itens.map(function (item) {
          return item.valor;
        }),
      ) || 0
    );
  }

  function percentualDe(valor, total) {
    return total > 0 && Number.isFinite(valor) ? (valor / total) * 100 : 0;
  }

  function sentidoDe(diferenca) {
    if (diferenca > 0) return "sobe";
    return diferenca < 0 ? "desce" : "igual";
  }

  /* Subir é bom ("sobe") ou cair é bom ("desce"); sem isso, neutro. */
  function julgar(diferenca, favoravel) {
    if (diferenca === 0 || !favoravel) return "neutro";
    const subiu = diferenca > 0;
    const subirEhBom = favoravel === "sobe";
    return subiu === subirEhBom ? "ok" : "erro";
  }

  /* O arredondamento vem antes do juízo: 0,04 com uma casa é zero, não sobe. */
  function delta(diferenca, favoravel, casas) {
    const arredondada = Number(diferenca.toFixed(casas));
    return { diferenca: arredondada, sentido: sentidoDe(arredondada), tom: julgar(arredondada, favoravel) };
  }

  function chipDelta(diferenca, opcoes) {
    const o = opcoes || {};
    const casas = Number.isInteger(o.casas) ? o.casas : 1;
    const d = delta(diferenca, o.favoravel, casas);
    const texto = G.fmt.comSinal(d.diferenca, casas) + (o.unidade || "");
    return G.el("span", { class: "graf-delta " + classeDoTom(d.tom) }, [icone(d.sentido, 9), texto]);
  }

  const formatadoresDeData = new Map();

  function formatadorDeData(estilo) {
    const lingua = document.documentElement.lang || "pt-BR";
    const chave = lingua + estilo;
    if (!formatadoresDeData.has(chave)) {
      const opcoes = { day: "2-digit", month: "2-digit", timeZone: "UTC" };
      if (estilo === "curta") opcoes.year = "2-digit";
      formatadoresDeData.set(chave, new Intl.DateTimeFormat(lingua, opcoes));
    }
    return formatadoresDeData.get(chave);
  }

  /* Data ISO (AAAA-MM-DD) na língua do documento: "curta" é 04/09/26 e "dia"
     é 04/09. Sem data válida, o traço. */
  function data(iso, estilo) {
    const partes = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso));
    if (!partes) return VAZIO;
    const instante = Date.UTC(Number(partes[1]), Number(partes[2]) - 1, Number(partes[3]));
    return formatadorDeData(estilo || "curta").format(instante);
  }

  /* Minúsculas e sem acento, para a busca achar "Medição" digitando "medicao". */
  function normalizar(texto) {
    return String(texto === null || texto === undefined ? "" : texto)
      .toLowerCase()
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "");
  }

  /* ---------- Peças de tela ---------- */

  function chip(texto, tomDoChip, opcoes) {
    const o = opcoes || {};
    const nome = o.icone ? nomeDoIcone(o.icone === true ? undefined : o.icone, tomDoChip) : null;
    const ico = nome ? icone(nome, o.tamanho || 12) : null;
    const classe = "graf-chip " + classeDoTom(tomDoChip) + (o.classe ? " " + o.classe : "");
    return G.el("span", { class: classe }, [ico, texto].filter(Boolean));
  }

  /* O quadradinho da legenda: o mesmo tom, nível e ícone da célula. */
  function amostra(faixa) {
    const nome = faixa.vazia ? null : nomeDoIcone(faixa.icone, faixa.tom);
    const ico = nome ? icone(nome, 10) : null;
    const classe = "graf-legenda__amostra " + classeDoTom(faixa.tom, faixa.nivel) + (faixa.vazia ? " is-vazia" : "");
    return G.el("span", { class: classe, "aria-hidden": "true" }, ico ? [ico] : []);
  }

  /* `itens` são faixas normalizadas ({ rotulo, tom, nivel, icone, vazia }). */
  function legenda(itens, nomeAcessivel) {
    return G.el(
      "ul",
      { class: "graf-legenda", "aria-label": nomeAcessivel },
      itens.map(function (item) {
        return G.el("li", { class: "graf-legenda__item" }, [amostra(item), item.rotulo]);
      }),
    );
  }

  /* Célula de valor: pílula do tom da faixa, com o ícone e o número. O nome
     da faixa vai escondido para o leitor de tela e na dica do ponteiro. Com
     `href` vira link. */
  function celula(texto, faixa, opcoes) {
    const f = faixa || {};
    const o = opcoes || {};
    const nome = faixa && !f.vazia ? nomeDoIcone(f.icone, f.tom) : null;
    const ico = nome ? icone(nome, 11) : null;
    const filhos = [ico, G.el("span", { class: "graf-celula__texto", texto: texto })];
    if (f.rotulo) filhos.push(G.el("span", { class: "graf-sr", texto: ", " + f.rotulo }));
    const classe = "graf-celula " + classeDoTom(f.tom, f.nivel) + (f.vazia ? " is-vazia" : "") + (o.classe ? " " + o.classe : "");
    return G.el(o.href ? "a" : "span", { class: classe, href: o.href, title: f.rotulo ? f.rotulo + ": " + texto : null }, filhos.filter(Boolean));
  }

  /* ---------- Seleção ---------- */

  function ehSelecionavel(item, dados) {
    if (item.href) return true;
    if (item.selecionavel !== undefined) return item.selecionavel === true;
    return Boolean(dados && dados.selecionavel === true);
  }

  /* Avisa a tela. Devolve false se alguém cancelou (aí o link não navega). */
  function notificar(host, tipo, detalhe, clique) {
    const evento = new CustomEvent("grafico:selecionar", {
      bubbles: true,
      cancelable: true,
      detail: Object.assign({ tipo: tipo }, detalhe),
    });
    const seguir = host.dispatchEvent(evento);
    if (!seguir && clique) clique.preventDefault();
    return seguir;
  }

  /* Torna o elemento clicável e acessível pelo teclado. `contexto` é
     { host, tipo, detalhe, aoAtivar }: `detalhe` vai no evento e `aoAtivar`
     roda depois dele, se ninguém cancelou. */
  function tornarInterativo(elemento, contexto) {
    /* Link e botão de verdade já respondem ao teclado: Enter vira clique. */
    const nativo = elemento.tagName === "A" || elemento.tagName === "BUTTON";
    elemento.classList.add("is-interativo");
    if (!nativo) {
      elemento.setAttribute("role", "button");
      elemento.setAttribute("tabindex", "0");
    }
    function acionar(clique) {
      const seguir = notificar(contexto.host, contexto.tipo, contexto.detalhe, clique);
      if (seguir && typeof contexto.aoAtivar === "function") contexto.aoAtivar(clique);
    }
    elemento.addEventListener("click", acionar);
    if (nativo) return elemento;
    elemento.addEventListener("keydown", function (tecla) {
      if (tecla.target !== elemento || (tecla.key !== "Enter" && tecla.key !== " ")) return;
      tecla.preventDefault();
      acionar(tecla);
    });
    return elemento;
  }

  G.pecas = {
    VAZIO: VAZIO,
    rotulo: rotulo,
    tom: tom,
    classeDoTom: classeDoTom,
    icone: icone,
    nomeDoIcone: nomeDoIcone,
    faixaDe: faixaDe,
    faixaPorId: faixaPorId,
    faixaDaCelula: faixaDaCelula,
    conjuntoDeFaixas: conjuntoDeFaixas,
    itensDeLegenda: itensDeLegenda,
    estadoPorLimites: estadoPorLimites,
    casasDe: casasDe,
    unidadeDe: unidadeDe,
    textoDoValor: textoDoValor,
    valorDaCelula: valorDaCelula,
    somar: somar,
    valorDaArvore: valorDaArvore,
    padroesDaColuna: padroesDaColuna,
    totalDosItens: totalDosItens,
    percentualDe: percentualDe,
    delta: delta,
    chipDelta: chipDelta,
    data: data,
    normalizar: normalizar,
    chip: chip,
    legenda: legenda,
    celula: celula,
    ehSelecionavel: ehSelecionavel,
    notificar: notificar,
    tornarInterativo: tornarInterativo,
  };
})();
