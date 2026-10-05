/* ============================================================
   dica.js — Dica (tooltip) do Timenow Design System e hover das siglas

   O Padrão não tinha componente de dica: só o atributo title, que demora,
   não tem estilo e não aparece no foco do teclado. Este arquivo cria o
   componente e o usa em dois lugares:

     [data-dica="texto"]         dica de qualquer elemento (aba de nome curto)
     [data-dica-trilho="texto"]  dica só enquanto a barra lateral é trilho de
                                 ícones, quando o rótulo do item não aparece
     sigla no texto da tela      mostra o significado vindo do glossário

   As siglas são achadas sem mexer no DOM: a palavra sob o ponteiro é
   localizada pela posição (caretPositionFromPoint), então tabelas e textos
   montados por Alpine não são tocados. O glossário chega do servidor em
   /api/glossario (CONTEXT.md, a fonte única) e fica no #glossario do shell.
   Limitação: texto dentro de gráfico (SVG/canvas) e de lista de seleção não
   tem a dica de sigla.

   Carrega pelo shell, nunca por fragmento. Ver docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const ATRASO_MS = 150;
  const MARGEM = 8;
  const CLASSE_TRILHO = "sidebar-trilho";
  /* Onde uma sigla nunca recebe dica: campos e blocos de código. */
  const IGNORAR = "input, textarea, select, option, script, style, [data-sem-dica]";

  let balao = null;
  let temporizador = null;
  let atual = null;
  let quadro = null;

  const glossario = { siglas: new Map(), notacoes: new Map(), regex: null };

  /* ---------- O balão ---------- */

  function garantirBalao() {
    if (!balao) {
      balao = document.createElement("div");
      balao.className = "dica";
      balao.setAttribute("role", "tooltip");
      balao.hidden = true;
      document.body.appendChild(balao);
    }
    return balao;
  }

  function bloco(linha) {
    const item = document.createElement("div");
    item.className = "dica__item";
    [["dica__titulo", linha.titulo], ["dica__texto", linha.texto]].forEach(function (par) {
      if (!par[1]) return;
      const campo = document.createElement("div");
      campo.className = par[0];
      campo.textContent = par[1];
      item.appendChild(campo);
    });
    return item;
  }

  function posicionar(el, ancora, lado) {
    const largura = el.offsetWidth;
    const altura = el.offsetHeight;
    let esquerda = ancora.left;
    let topo = ancora.bottom + MARGEM;
    if (lado === "direita") {
      esquerda = ancora.right + MARGEM;
      topo = ancora.top + (ancora.height - altura) / 2;
    } else if (topo + altura > window.innerHeight - MARGEM) {
      topo = ancora.top - altura - MARGEM;
    }
    el.style.left = Math.min(Math.max(MARGEM, esquerda), window.innerWidth - largura - MARGEM) + "px";
    el.style.top = Math.min(Math.max(MARGEM, topo), window.innerHeight - altura - MARGEM) + "px";
  }

  function mostrar(linhas, ancora, lado) {
    const el = garantirBalao();
    el.replaceChildren.apply(el, linhas.map(bloco));
    /* Volta ao canto antes de medir: perto da borda direita o balão encolheria
       e a medida sairia errada. */
    el.style.left = "0px";
    el.style.top = "0px";
    el.hidden = false;
    posicionar(el, ancora, lado);
  }

  function esconder() {
    clearTimeout(temporizador);
    atual = null;
    if (balao) balao.hidden = true;
  }

  /* ---------- Dica de elemento ---------- */

  function emTrilho() {
    return document.documentElement.classList.contains(CLASSE_TRILHO);
  }

  function textoDoElemento(el) {
    if (el.dataset.dica) return el.dataset.dica;
    return emTrilho() ? el.dataset.dicaTrilho || "" : "";
  }

  function elementoComDica(origem) {
    const el = origem && origem.closest ? origem.closest("[data-dica], [data-dica-trilho]") : null;
    return el && textoDoElemento(el) ? el : null;
  }

  function agendar(el, imediato) {
    if (atual && atual.elemento === el) return;
    esconder();
    atual = { elemento: el };
    const lado = el.closest(".sidebar") ? "direita" : "baixo";
    const exibir = function () {
      mostrar([{ texto: textoDoElemento(el) }], el.getBoundingClientRect(), lado);
    };
    if (imediato) exibir();
    else temporizador = setTimeout(exibir, ATRASO_MS);
  }

  document.addEventListener("mouseover", function (e) {
    const el = elementoComDica(e.target);
    if (el) agendar(el, false);
  });

  document.addEventListener("mouseout", function (e) {
    const el = atual && atual.elemento;
    if (el && !(e.relatedTarget && el.contains(e.relatedTarget))) esconder();
  });

  document.addEventListener("focusin", function (e) {
    const el = elementoComDica(e.target);
    if (el) agendar(el, true);
  });

  document.addEventListener("focusout", esconder);
  document.addEventListener("click", esconder);
  window.addEventListener("scroll", esconder, true);
  window.addEventListener("resize", esconder);
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") esconder();
  });

  /* ---------- Dica de sigla ---------- */

  function escaparRegex(texto) {
    return texto.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function lerGlossario() {
    const raiz = document.getElementById("glossario");
    const termos = raiz ? raiz.querySelectorAll("dt") : [];
    if (!termos.length) return false;
    glossario.siglas.clear();
    glossario.notacoes.clear();
    termos.forEach(function (dt) {
      const descricao = dt.nextElementSibling;
      const item = { titulo: dt.textContent.trim(), texto: descricao ? descricao.textContent.trim() : "" };
      if (dt.dataset.sigla) {
        glossario.siglas.set(dt.dataset.sigla, (glossario.siglas.get(dt.dataset.sigla) || []).concat(item));
      } else if (dt.dataset.padrao) {
        glossario.notacoes.set(dt.dataset.padrao, item);
      }
    });
    glossario.regex = montarRegex();
    return true;
  }

  /* A sigla inteira, sem letra ou dígito colado: "SPI" casa, "SPIN" e "ASPI" não.
     S39 (ou S.39) é a semana ISO, explicada pelo termo "Semana ISO". */
  function montarRegex() {
    const siglas = Array.from(glossario.siglas.keys())
      .sort(function (a, b) { return b.length - a.length; })
      .map(escaparRegex);
    const alternativas = [];
    if (siglas.length) alternativas.push("(?<sigla>" + siglas.join("|") + ")");
    if (glossario.notacoes.has("semana")) alternativas.push("S\\.?(?<numero>\\d{1,2})");
    if (!alternativas.length) return null;
    return new RegExp("(?<![\\p{L}\\p{N}_])(?:" + alternativas.join("|") + ")(?![\\p{L}\\p{N}_])", "gu");
  }

  function posicaoDoTexto(x, y) {
    if (typeof document.caretPositionFromPoint === "function") {
      const posicao = document.caretPositionFromPoint(x, y);
      return posicao ? { no: posicao.offsetNode, indice: posicao.offset } : null;
    }
    if (typeof document.caretRangeFromPoint === "function") {
      const faixa = document.caretRangeFromPoint(x, y);
      return faixa ? { no: faixa.startContainer, indice: faixa.startOffset } : null;
    }
    return null;
  }

  function contemPonto(faixa, x, y) {
    return Array.from(faixa.getClientRects()).some(function (r) {
      return x >= r.left - 1 && x <= r.right + 1 && y >= r.top - 1 && y <= r.bottom + 1;
    });
  }

  function siglaSob(x, y) {
    const posicao = posicaoDoTexto(x, y);
    if (!posicao || posicao.no.nodeType !== Node.TEXT_NODE) return null;
    const pai = posicao.no.parentElement;
    if (!pai || pai.closest(IGNORAR)) return null;
    for (const achado of posicao.no.data.matchAll(glossario.regex)) {
      const inicio = achado.index;
      const fim = inicio + achado[0].length;
      if (posicao.indice < inicio || posicao.indice > fim) continue;
      const faixa = document.createRange();
      faixa.setStart(posicao.no, inicio);
      faixa.setEnd(posicao.no, fim);
      if (contemPonto(faixa, x, y)) return { achado, faixa, chave: posicao.no, inicio };
    }
    return null;
  }

  function linhasDaSigla(achado) {
    if (achado.groups.sigla) return glossario.siglas.get(achado.groups.sigla) || [];
    const semana = glossario.notacoes.get("semana");
    if (!semana) return [];
    return [{ titulo: semana.titulo + " " + achado.groups.numero, texto: semana.texto }];
  }

  function mesmaSigla(sigla) {
    return atual !== null && atual.chave === sigla.chave && atual.inicio === sigla.inicio;
  }

  function exibirSigla(sigla) {
    if (mesmaSigla(sigla)) return;
    const linhas = linhasDaSigla(sigla.achado);
    if (!linhas.length) return;
    esconder();
    atual = { chave: sigla.chave, inicio: sigla.inicio };
    mostrar(linhas, sigla.faixa.getBoundingClientRect(), "baixo");
  }

  function sobreTexto(x, y, origem) {
    if (elementoComDica(origem)) return;
    if (!glossario.regex && !lerGlossario()) return;
    const sigla = glossario.regex ? siglaSob(x, y) : null;
    if (sigla) {
      exibirSigla(sigla);
    } else if (atual && atual.chave) {
      esconder();
    }
  }

  document.addEventListener("mousemove", function (e) {
    if (quadro !== null || e.buttons !== 0) return;
    const x = e.clientX;
    const y = e.clientY;
    const origem = e.target;
    quadro = requestAnimationFrame(function () {
      quadro = null;
      sobreTexto(x, y, origem);
    });
  });

  window.TN.dica = { mostrar: mostrar, esconder: esconder };
})();
