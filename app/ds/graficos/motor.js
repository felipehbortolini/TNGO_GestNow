/* ============================================================
   graficos/motor.js — Motor comum da biblioteca de gráficos

   Os gráficos do GestNow são SVG e JavaScript puro, sem biblioteca de
   terceiros. Este arquivo é o que todos têm em comum; cada tipo de visual
   mora no seu próprio arquivo (curva-s-linha.js, pareto.js...) e se
   registra aqui com TN.graficos.registrar().

   O que o motor oferece:
     - cores lidas dos tokens do :root em tempo de execução (nenhum
       hexadecimal neste diretório): cor(), clarear(), misturar()
     - dica escura que segue o ponteiro, legenda e botões de ano
     - animação de entrada que respeita prefers-reduced-motion
     - leitura do contrato de dados e montagem automática
     - escala de eixo, formatação de número e nome do mês

   Contrato de montagem. O fragmento do servidor traz só o elemento, nunca
   <script>:

     <div data-grafico="curva-s-linha" data-dados='{{ grafico | tojson }}'></div>

   `tojson` do Jinja devolve texto seguro para HTML, mas as aspas duplas
   fecham um atributo entre aspas duplas: use aspas simples no atributo (ou
   `| tojson | forceescape`). O motor observa o documento, então o gráfico
   nasce quando o Alpine AJAX troca o fragmento e é refeito quando o
   atributo `data-dados` muda. Opcional: `data-animar="nao"` desliga a
   animação de entrada.

   Rótulos de interface ("Todos", "Atual"...) têm padrão em português aqui e
   podem ser trocados pelo servidor em `rotulos` no JSON; nenhuma tradução
   vive no JavaScript (ver docs/MAPA-DE-MODULOS.md).

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  window.TN = window.TN || {};
  const TN = window.TN;

  const NS_SVG = "http://www.w3.org/2000/svg";

  /* ---------- Cores ----------

     O servidor fala em papel ("realizado"), não em cor: se o Design System
     trocar o token, nenhum dado muda. Quem preferir pode passar o nome do
     token direto ("--roxo-500"). */
  const PAPEIS = {
    "linha-base": "--neutro-300",
    previsto: "--frio-500",
    realizado: "--verde-500",
    comprometido: "--roxo-500",
    tendencia: "--laranja-500",
    ok: "--ok-500",
    alerta: "--warn-500",
    atencao: "--laranja-500",
    erro: "--erro-500",
    neutro: "--frio-500",
    info: "--azul-500",
    bege: "--bege-500",
    outros: "--neutro-400",
    marca: "--verde-500",
    titulo: "--brand-title",
    texto: "--text-primary",
    "texto-suave": "--text-secondary",
  };

  /* Ordem das séries quando o dado não diz o papel nem a cor. */
  const SEQUENCIA = ["marca", "atencao", "comprometido", "info", "bege", "neutro"];

  const tokensLidos = new Map();

  function lerToken(token) {
    if (!tokensLidos.has(token)) {
      const valor = window.getComputedStyle(document.documentElement).getPropertyValue(token).trim();
      if (!valor) {
        console.warn("[graficos] token sem valor: " + token);
        return "currentColor";
      }
      tokensLidos.set(token, valor);
    }
    return tokensLidos.get(token);
  }

  function cor(nome) {
    const texto = String(nome);
    const token = texto.startsWith("--") ? texto : PAPEIS[texto];
    if (!token) console.warn("[graficos] papel de cor desconhecido: " + texto);
    return lerToken(token || PAPEIS.texto);
  }

  function corDaSequencia(indice) {
    return cor(SEQUENCIA[indice % SEQUENCIA.length]);
  }

  function paraRgb(css) {
    const hex = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(css.trim());
    if (hex) {
      const cheio = hex[1].length === 3 ? hex[1].replace(/./g, "$&$&") : hex[1];
      return [0, 2, 4].map(function (i) {
        return parseInt(cheio.slice(i, i + 2), 16);
      });
    }
    const partes = css.match(/[\d.]+/g);
    return partes && partes.length >= 3 ? partes.slice(0, 3).map(Number) : null;
  }

  /* Mistura duas cores; `peso` é a fração de corB (0 a 1). Se alguma não for
     uma cor que dê para decompor (currentColor), devolve a primeira. */
  function misturar(corA, corB, peso) {
    const a = paraRgb(corA);
    const b = paraRgb(corB);
    if (!a || !b) return corA;
    const mistura = a.map(function (valor, i) {
      return Math.round(valor + (b[i] - valor) * peso);
    });
    return "rgb(" + mistura.join(", ") + ")";
  }

  function clarear(corCss, peso) {
    return misturar(corCss, lerToken("--branco"), peso);
  }

  /* ---------- Formatação ---------- */

  const formatadores = new Map();

  function formatador(casas) {
    const lingua = document.documentElement.lang || "pt-BR";
    const chave = lingua + casas;
    if (!formatadores.has(chave)) {
      formatadores.set(
        chave,
        new Intl.NumberFormat(lingua, { minimumFractionDigits: casas, maximumFractionDigits: casas }),
      );
    }
    return formatadores.get(chave);
  }

  function numero(valor, casas) {
    const arredondado = Number(Number(valor).toFixed(casas));
    /* -0,04 com uma casa vira zero: sem isto sairia "-0,0". */
    return formatador(casas).format(arredondado === 0 ? 0 : arredondado);
  }

  function percentual(valor, casas) {
    return numero(valor, casas) + "%";
  }

  function comSinal(valor, casas) {
    const texto = numero(valor, casas);
    return valor > 0 ? "+" + texto : texto;
  }

  const nomesDeMes = new Map();

  /* "Jan", "Fev"...: vem do Intl na língua do documento, para o mês não ser
     texto de interface escrito à mão aqui. */
  function nomeMes(mes) {
    const lingua = document.documentElement.lang || "pt-BR";
    if (!nomesDeMes.has(lingua)) {
      nomesDeMes.set(lingua, new Intl.DateTimeFormat(lingua, { month: "short", timeZone: "UTC" }));
    }
    const curto = nomesDeMes.get(lingua).format(Date.UTC(2000, mes - 1, 1));
    const semPonto = curto.replace(".", "");
    return semPonto.charAt(0).toUpperCase() + semPonto.slice(1);
  }

  /* Folga para o erro de ponto flutuante: 100,00000000000001 (uma soma de
     centésimos) não pode empurrar o eixo de 100 para 125 ou 200. */
  const TOLERANCIA = 1e-9;
  const MULTIPLOS_REDONDOS = [1, 2, 2.5, 5, 10];

  /* Eixo em quatro intervalos com passo "redondo" (1, 2, 2,5, 5 vezes uma
     potência de dez): escala(80) dá 0, 20, 40, 60, 80. É o que o Pareto usa,
     porque a grade dele tem sempre quatro intervalos. */
  function escala(maximo) {
    const alvo = maximo > 0 ? maximo : 1;
    const potencia = Math.pow(10, Math.floor(Math.log10(alvo / 4)));
    const multiplo = MULTIPLOS_REDONDOS.find(function (m) {
      return m * potencia * 4 >= alvo * (1 - TOLERANCIA);
    });
    const passo = multiplo * potencia;
    return {
      max: passo * 4,
      passos: [0, 1, 2, 3, 4].map(function (i) {
        return i * passo;
      }),
    };
  }

  /* Eixo livre, para as curvas: passo redondo com 4 a 6 intervalos. Entre os
     que servem fica o de menor topo (que passa pouco do maior valor) e, se
     empatam, o de menos intervalos: escalaLivre(100) dá 0, 25, 50, 75, 100 e
     escalaLivre(103) dá 0, 20, ... 120, não 0, 50, ... 200. */
  function escalaLivre(maximo) {
    const alvo = maximo > 0 ? maximo : 1;
    const base = Math.pow(10, Math.floor(Math.log10(alvo / 5)));
    const candidatos = MULTIPLOS_REDONDOS.map(function (multiplo) {
      const passo = multiplo * base;
      return { passo: passo, intervalos: Math.ceil(alvo / passo - TOLERANCIA) };
    }).filter(function (candidato) {
      return candidato.intervalos >= 4 && candidato.intervalos <= 6;
    });
    if (!candidatos.length) return escala(alvo);
    candidatos.sort(function (a, b) {
      const diferenca = a.passo * a.intervalos - b.passo * b.intervalos;
      return Math.abs(diferenca) > alvo * TOLERANCIA ? diferenca : a.intervalos - b.intervalos;
    });
    const melhor = candidatos[0];
    return {
      max: melhor.passo * melhor.intervalos,
      passos: Array.from({ length: melhor.intervalos + 1 }, function (_vazio, i) {
        return i * melhor.passo;
      }),
    };
  }

  /* ---------- Rótulos de interface ---------- */

  const ROTULOS = {
    todos: "Todos",
    ano: "Ano",
    periodo: "Período",
    acumulado: "Acum.",
    doTotal: "do total",
    zonaVital: "Zona vital",
    quantidade: "Quantidade",
    percAcumulado: "% acumulado",
    atual: "Atual",
    meta: "Meta",
    vsMeta: "vs meta",
    ok: "Dentro da meta",
    alerta: "Atenção",
    erro: "Abaixo da meta",
    vazio: "Sem dados para exibir.",
    falha: "Não foi possível exibir o gráfico.",
  };

  function rotulo(dados, chave) {
    const doServidor = dados && dados.rotulos ? dados.rotulos[chave] : undefined;
    return doServidor === undefined ? ROTULOS[chave] : doServidor;
  }

  /* ---------- Elementos ---------- */

  function montarNo(no, atributos, filhos) {
    Object.keys(atributos || {}).forEach(function (chave) {
      const valor = atributos[chave];
      if (valor === null || valor === undefined || valor === false) return;
      if (chave === "texto") {
        no.textContent = valor;
      } else {
        no.setAttribute(chave, valor === true ? "" : valor);
      }
    });
    (filhos || []).forEach(function (filho) {
      no.appendChild(typeof filho === "string" ? document.createTextNode(filho) : filho);
    });
    return no;
  }

  /* Texto sempre entra por textContent: rótulo vindo do banco não vira HTML. */
  function el(nome, atributos, filhos) {
    return montarNo(document.createElement(nome), atributos, filhos);
  }

  function svg(nome, atributos, filhos) {
    return montarNo(document.createElementNS(NS_SVG, nome), atributos, filhos);
  }

  function mostrarMensagem(host, texto) {
    host.replaceChildren(el("p", { class: "graf__vazio", texto: texto }));
  }

  /* ---------- Animação ---------- */

  const configuracao = { animar: true };

  function configurar(opcoes) {
    Object.assign(configuracao, opcoes);
  }

  function podeAnimar(no) {
    if (!configuracao.animar) return false;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return false;
    return no.closest('[data-animar="nao"]') === null;
  }

  function comprimentoDe(caminho) {
    try {
      return caminho.getTotalLength();
    } catch {
      return 0;
    }
  }

  /* A linha se desenha da esquerda para a direita. */
  function animarTraco(caminho, duracaoMs) {
    if (!podeAnimar(caminho)) return;
    const comprimento = comprimentoDe(caminho);
    if (!Number.isFinite(comprimento) || comprimento <= 0) return;
    caminho.style.strokeDasharray = String(comprimento);
    caminho.style.strokeDashoffset = String(comprimento);
    /* Força o cálculo de layout: sem isto o navegador junta os dois valores
       e a transição não acontece. */
    caminho.getBoundingClientRect();
    caminho.style.transition = "stroke-dashoffset " + duracaoMs + "ms cubic-bezier(0.4, 0, 0.2, 1)";
    caminho.style.strokeDashoffset = "0";
  }

  /* Refaz o desenho quando o tamanho muda. Devolve a função que desliga. O
     redesenho espera o próximo quadro: mexer no DOM de dentro do callback
     do ResizeObserver faz o navegador acusar "loop" no console. */
  function observarTamanho(no, aoMudar) {
    if (typeof window.ResizeObserver !== "function") return function () {};
    let ultimo = no.clientWidth + "x" + no.clientHeight;
    let quadro = 0;
    const observador = new window.ResizeObserver(function () {
      const atual = no.clientWidth + "x" + no.clientHeight;
      if (atual === ultimo) return;
      ultimo = atual;
      window.cancelAnimationFrame(quadro);
      quadro = window.requestAnimationFrame(function () {
        aoMudar();
      });
    });
    observador.observe(no);
    return function () {
      observador.disconnect();
      window.cancelAnimationFrame(quadro);
    };
  }

  /* ---------- Dica escura ---------- */

  function posicionarDica(caixa, tela, evento) {
    const area = tela.getBoundingClientRect();
    let x = evento.clientX - area.left + 12;
    let y = evento.clientY - area.top + 12;
    if (x + caixa.offsetWidth > tela.clientWidth - 8) x = evento.clientX - area.left - caixa.offsetWidth - 12;
    if (y + caixa.offsetHeight > tela.clientHeight - 8) y = tela.clientHeight - caixa.offsetHeight - 8;
    caixa.style.left = Math.max(4, x) + "px";
    caixa.style.top = Math.max(4, y) + "px";
  }

  /* `tela` é o contêiner posicionado (position: relative) onde a dica flutua. */
  function criarDica(tela, classe) {
    const caixa = el("div", { class: "graf__tip " + (classe || ""), role: "tooltip", hidden: true });
    tela.appendChild(caixa);
    return {
      mostrar: function (evento, conteudo) {
        caixa.replaceChildren(...conteudo);
        caixa.hidden = false;
        posicionarDica(caixa, tela, evento);
      },
      mover: function (evento) {
        if (!caixa.hidden) posicionarDica(caixa, tela, evento);
      },
      esconder: function () {
        caixa.hidden = true;
      },
    };
  }

  function dicaTitulo(texto) {
    return el("b", { class: "graf__tip-tit", texto: texto });
  }

  function dicaDivisor() {
    return el("div", { class: "graf__tip-div" });
  }

  /* Uma linha da dica: marca colorida, rótulo e um ou mais valores. */
  function dicaLinha(corDaMarca, texto, valores) {
    const ponto = el("i", { class: "graf__tip-ponto" });
    ponto.style.background = corDaMarca;
    const celulas = valores.map(function (valor) {
      return el("strong", { class: "graf__tip-val", texto: valor });
    });
    return el("div", { class: "graf__tip-linha" }, [el("span", { class: "graf__tip-rot" }, [ponto, texto])].concat(celulas));
  }

  /* Cabeçalho de colunas da dica (Período | Acum.). */
  function dicaCabecalho(colunas) {
    const celulas = colunas.map(function (coluna) {
      return el("span", { class: "graf__tip-val", texto: coluna });
    });
    return el("div", { class: "graf__tip-linha graf__tip-cab" }, [el("span", { class: "graf__tip-rot" })].concat(celulas));
  }

  /* ---------- Legenda ---------- */

  /* Item: { rotulo, cor, traco (linha tracejada), barra (amostra de barra) }. */
  function amostrasDoItem(item) {
    const amostras = [];
    if (item.barra) {
      const barra = el("b", { class: "graf__leg-barra" });
      barra.style.background = item.cor;
      amostras.push(barra);
    }
    const linha = el("i", { class: "graf__leg-linha" + (item.traco ? " is-tracejada" : "") });
    linha.style[item.traco ? "borderTopColor" : "background"] = item.cor;
    amostras.push(linha);
    return amostras;
  }

  function criarLegenda(itens) {
    return el(
      "div",
      { class: "graf__leg" },
      itens.map(function (item) {
        return el("span", { class: "graf__leg-item" }, amostrasDoItem(item).concat([item.rotulo]));
      }),
    );
  }

  /* ---------- Botões de ano ---------- */

  /* Devolve { elemento, marcar(ano) }; ano null é "Todos". */
  function criarAnos(anos, dados, aoEscolher) {
    const opcoes = [{ ano: null, texto: rotulo(dados, "todos") }].concat(
      anos.map(function (ano) {
        return { ano: ano, texto: String(ano) };
      }),
    );
    const botoes = opcoes.map(function (opcao) {
      const botao = el("button", { type: "button", class: "graf__ano", texto: opcao.texto });
      botao.addEventListener("click", function () {
        aoEscolher(opcao.ano);
      });
      return botao;
    });
    const grupo = el("div", { class: "graf__anos", role: "group", "aria-label": rotulo(dados, "ano") }, botoes);
    function marcar(ano) {
      botoes.forEach(function (botao, i) {
        const ativo = opcoes[i].ano === ano;
        botao.classList.toggle("is-ativo", ativo);
        botao.setAttribute("aria-pressed", ativo ? "true" : "false");
      });
    }
    marcar(null);
    return { elemento: grupo, marcar: marcar };
  }

  /* ---------- Registro e montagem ---------- */

  const fabricas = new Map();
  const montados = new WeakMap();
  let iniciado = false;

  function analisar(bruto) {
    try {
      return JSON.parse(bruto);
    } catch (erro) {
      console.error("[graficos] data-dados com JSON inválido", erro);
      return null;
    }
  }

  function desmontar(host) {
    const atual = montados.get(host);
    if (!atual) return;
    if (atual.instancia && typeof atual.instancia.destruir === "function") atual.instancia.destruir();
    montados.delete(host);
    host.replaceChildren();
  }

  function criarInstancia(fabrica, host, dados) {
    try {
      return fabrica(host, dados);
    } catch (erro) {
      console.error("[graficos] falha ao desenhar " + host.dataset.grafico, erro);
      mostrarMensagem(host, ROTULOS.falha);
      return null;
    }
  }

  /* Monta (ou refaz) o gráfico de um elemento [data-grafico]. Sem
     data-dados ainda, espera: o observador chama de novo quando o atributo
     aparecer. */
  function montar(host) {
    const tipo = host.dataset.grafico;
    const bruto = host.dataset.dados;
    const anterior = montados.get(host);
    if (!bruto || (anterior && anterior.bruto === bruto)) return;
    const fabrica = fabricas.get(tipo);
    if (!fabrica) {
      console.warn("[graficos] tipo de gráfico desconhecido: " + tipo);
      return;
    }
    desmontar(host);
    host.classList.add("graf", "graf--" + tipo);
    host.classList.toggle("graf--parado", !podeAnimar(host));
    const dados = analisar(bruto);
    if (dados === null) {
      mostrarMensagem(host, ROTULOS.falha);
      montados.set(host, { bruto: bruto, instancia: null });
      return;
    }
    if (dados.altura) host.style.setProperty("--graf-altura", dados.altura + "px");
    montados.set(host, { bruto: bruto, instancia: criarInstancia(fabrica, host, dados) });
  }

  function montarTudo(raiz) {
    const base = raiz || document;
    if (base.matches && base.matches("[data-grafico]")) montar(base);
    base.querySelectorAll("[data-grafico]").forEach(montar);
  }

  function registrar(tipo, fabrica) {
    fabricas.set(tipo, fabrica);
    if (iniciado) montarTudo(document);
  }

  /* Criação sem passar pelo atributo, para quem monta o gráfico do JavaScript
     da página: TN.graficos.criar("pareto", elemento, dados). */
  function criar(tipo, host, dados) {
    host.dataset.grafico = tipo;
    host.dataset.dados = JSON.stringify(dados);
    montar(host);
  }

  function noDeElemento(no) {
    return no.nodeType === 1 ? no : null;
  }

  function reagir(mutacoes) {
    mutacoes.forEach(function (mutacao) {
      if (mutacao.type === "attributes") {
        if (mutacao.target.matches("[data-grafico]")) montar(mutacao.target);
        return;
      }
      Array.from(mutacao.addedNodes).map(noDeElemento).filter(Boolean).forEach(function (no) {
        if (!no.closest(".graf")) montarTudo(no);
      });
      Array.from(mutacao.removedNodes).map(noDeElemento).filter(Boolean).forEach(function (no) {
        const hosts = Array.from(no.querySelectorAll("[data-grafico]"));
        if (no.matches("[data-grafico]")) hosts.push(no);
        hosts.forEach(desmontar);
      });
    });
  }

  function iniciar() {
    iniciado = true;
    montarTudo(document);
    new MutationObserver(reagir).observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["data-dados"],
    });
  }

  /* Com `defer` o documento já está lido, mas os outros scripts do shell ainda
     não rodaram: esperar um ciclo garante que todo tipo de gráfico já se
     registrou antes da primeira varredura. */
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciar);
  } else {
    window.setTimeout(iniciar, 0);
  }

  TN.graficos = {
    registrar: registrar,
    montar: montar,
    montarTudo: montarTudo,
    criar: criar,
    configurar: configurar,
    papeis: Object.assign({}, PAPEIS),
    cor: cor,
    corDaSequencia: corDaSequencia,
    clarear: clarear,
    misturar: misturar,
    fmt: { numero: numero, percentual: percentual, comSinal: comSinal },
    nomeMes: nomeMes,
    escala: escala,
    escalaLivre: escalaLivre,
    rotulo: rotulo,
    el: el,
    svg: svg,
    mostrarMensagem: mostrarMensagem,
    podeAnimar: podeAnimar,
    animarTraco: animarTraco,
    observarTamanho: observarTamanho,
    criarDica: criarDica,
    dicaTitulo: dicaTitulo,
    dicaDivisor: dicaDivisor,
    dicaLinha: dicaLinha,
    dicaCabecalho: dicaCabecalho,
    criarLegenda: criarLegenda,
    criarAnos: criarAnos,
  };
})();
