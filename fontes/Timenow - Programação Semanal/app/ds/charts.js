/* ============================================================
   charts.js — gráficos SVG do Timenow Design System

   Sem biblioteca externa: o contrato visual proíbe CDN, e um pacote de
   gráficos vendorizado pesaria mais que o app inteiro.

   ## O motor de drill

   Três dos quatro gráficos compartilham o mesmo eixo: **mês por padrão,
   clique no nome do mês abre as semanas dele, botões filtram por ano**.
   É o desenho dos visuais de Power BI que originaram estes gráficos, e
   está escrito uma vez só — `montarColunas`, `geometria`, `eixoDrill`,
   `botoesDeAno`. Cada gráfico entra com um **adaptador**: como resumir
   um mês, como ler uma semana, o que desenhar e o que mostrar na dica.

   Consolidar o mês NÃO é somar percentuais em todo caso. Barras de
   avanço somam (cada semana é uma fatia do escopo); aderência divide
   (soma do realizado sobre soma do previsto do período). Cada adaptador
   sabe a sua conta — por isso o servidor manda quantidade e não
   percentual pronto.

   ## Como uma página usa

   Fragmento nunca traz <script src> (Regra 2 do contrato visual). A
   página declara o container e os dados:

       <div class="grafico__tela" data-grafico="curva-s">
         <script type="application/json">{ ... }</script>
       </div>

   Este arquivo, carregado uma vez pelo shell, encontra os containers
   sozinho — no boot, a cada troca de fragmento e a cada mudança de
   tamanho. **Nenhum número é fixo aqui:** tudo vem do payload, que o
   servidor recalcula a cada requisição.

   ## As cores

   Saem dos tokens, lidos do :root em tempo de execução. Nenhum
   hexadecimal escrito aqui: trocar a rampa da marca em tokens.css troca
   o gráfico junto.
   ============================================================ */
(function () {
  "use strict";

  const MESES = ["jan", "fev", "mar", "abr", "mai", "jun",
    "jul", "ago", "set", "out", "nov", "dez"];

  const MARGEM = { esquerda: 48, direita: 18, topo: 26, base: 80 };

  const estados = new WeakMap();
  let observador = null;

  /* ---------- utilidades ---------- */

  function token(nome, alternativa) {
    const valor = getComputedStyle(document.documentElement)
      .getPropertyValue("--" + nome).trim();
    return valor || alternativa;
  }

  function cores() {
    return {
      base: token("neutro-300", "#B9B9BC"),
      /* Previsto em laranja Timenow, não no azul acinzentado que veio do
         visual de origem: a paleta da aplicação é verde e laranja, e o
         par previsto/realizado é justamente onde dois matizes opostos
         trabalham melhor. `--laranja-700` e não o 500 porque o 500 não
         aprova contraste como cor de texto, e este token também rotula
         número sobre branco. */
      previsto: token("laranja-700", "#B34A00"),
      realizado: token("verde-500", "#00A793"),
      marca: token("brand-title", "#006357"),
      grade: token("neutro-100", "#F1F1F1"),
      eixo: token("neutro-200", "#DCDCDC"),
      texto: token("text-secondary", "#767676"),
      apagado: token("text-hint", "#767676"),
      realce: token("neutro-50", "#F5FAFB"),
      alerta: token("warn-500", "#E8B43B"),
      laranja: token("laranja-500", "#EB6100"),
      laranjaEscuro: token("laranja-700", "#B34A00"),
      verdeMedio: token("verde-600", "#008A7D"),
      verdeClaro: token("verde-200", "#91D9D1"),
      erro: token("erro-500", "#D03636"),
    };
  }

  /* Paleta de séries — só o que o Design System tem: os tons de verde
     Timenow, depois os tons de laranja Timenow. Nada de roxo, azul ou
     amarelo: não são cores da marca, e um gráfico é o lugar onde uma cor
     de fora aparece mais.

     A ordem não é a da rampa, é a da separação: o mais escuro, depois o
     mais claro, depois o do meio. Percorrer a rampa em ordem colocaria
     dois degraus vizinhos lado a lado no gráfico, que é onde eles se
     confundem.

     Verde e laranja são o mesmo par de matizes em toda a rampa. Com três
     ou mais contratadas, séries do mesmo matiz ficam próximas — por isso
     `tracoDaSerie` dá a cada uma um traço diferente, e a leitura deixa de
     depender só de distinguir dois verdes. */
  function paleta() {
    const c = cores();
    return [
      c.marca,          // #006457 — verde escuro da marca
      c.realizado,      // #00A793 — verde vivo
      c.verdeMedio,     // #008A7D — verde médio
      c.laranja,        // #EB6100 — laranja vivo
      c.laranjaEscuro,  // #B34A00 — laranja escuro
      c.verdeClaro,     // #91D9D1 — verde claro
    ];
  }

  /* Traço por série. Sólido para a primeira, e padrões cada vez mais
     abertos depois — o que separa as séries quando a cor não basta, e o
     que faz o gráfico continuar legível impresso em preto e branco ou
     para quem não distingue os dois matizes. */
  const TRACOS = ["", "7,4", "2,3", "10,4,2,4", "5,3,1,3", "14,5"];

  function tracoDaSerie(ordem) {
    const t = TRACOS[ordem % TRACOS.length];
    return t ? " stroke-dasharray='" + t + "'" : "";
  }

  /* O mesmo padrão do traço, em CSS, para a amostra da legenda.

     A legenda tem de mostrar o que distingue as séries. Com três verdes
     próximos, o traço faz metade do trabalho de separação — uma legenda
     de três riscos sólidos idênticos mandaria procurar no gráfico uma
     diferença que ela não mostrou.

     O padrão é reduzido a 0,7 para caber nos 16px da amostra sem perder
     o ritmo que identifica a linha. */
  function amostraDoTraco(ordem, cor) {
    const traco = TRACOS[ordem % TRACOS.length];
    if (!traco) return "background:" + cor;
    const passos = traco.split(",").map(function (n) { return Number(n) * 0.7; });
    let posicao = 0;
    const paradas = [];
    passos.forEach(function (passo, i) {
      const tinta = i % 2 === 0 ? cor : "transparent";
      paradas.push(tinta + " " + posicao.toFixed(1) + "px " + (posicao + passo).toFixed(1) + "px");
      posicao += passo;
    });
    return "background:repeating-linear-gradient(to right," + paradas.join(",") + ")";
  }

  function esc(texto) {
    return String(texto === null || texto === undefined ? "" : texto)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function fmt(valor, casas) {
    const numero = Number(valor);
    if (!isFinite(numero)) return "—";
    return numero.toLocaleString("pt-BR", {
      minimumFractionDigits: casas === undefined ? 0 : casas,
      maximumFractionDigits: casas === undefined ? 1 : casas,
    });
  }

  function pct(valor, casas) {
    return fmt(valor, casas === undefined ? 1 : casas) + "%";
  }

  /* Escala "redonda" para o topo do eixo: 47 vira 50, 1.180 vira 1.500.
     Sem isso o rótulo do topo fica em 47,3 e ninguém lê o eixo. */
  function tetoRedondo(valor) {
    if (valor <= 0) return 1;
    const grandeza = Math.pow(10, Math.floor(Math.log10(valor)));
    return Math.ceil((valor * 1.12) / grandeza) * grandeza;
  }

  /* Catmull-Rom convertido em Bézier: passa por todos os pontos, sem a
     ondulação exagerada que uma spline solta produz nas bordas. */
  function suavizar(pontos) {
    if (pontos.length < 2) return "";
    if (pontos.length === 2) {
      return "M" + pontos[0][0] + "," + pontos[0][1] +
        " L" + pontos[1][0] + "," + pontos[1][1];
    }
    let d = "M" + pontos[0][0] + "," + pontos[0][1];
    for (let i = 0; i < pontos.length - 1; i++) {
      const p0 = pontos[i - 1] || pontos[i];
      const p1 = pontos[i];
      const p2 = pontos[i + 1];
      const p3 = pontos[i + 2] || p2;
      d += " C" + (p1[0] + (p2[0] - p0[0]) / 6) + "," + (p1[1] + (p2[1] - p0[1]) / 6) +
        " " + (p2[0] - (p3[0] - p1[0]) / 6) + "," + (p2[1] - (p3[1] - p1[1]) / 6) +
        " " + p2[0] + "," + p2[1];
    }
    return d;
  }

  function svgAbre(geo, rotulo) {
    return "<svg width='" + geo.largura + "' height='" + geo.altura + "' viewBox='0 0 " +
      geo.largura + " " + geo.altura + "' xmlns='http://www.w3.org/2000/svg' role='img' " +
      "aria-label='" + esc(rotulo || "Gráfico") + "'>";
  }

  function textoSvg(x, y, conteudo, atributos) {
    return "<text x='" + x + "' y='" + y + "' " + (atributos || "") + ">" +
      esc(conteudo) + "</text>";
  }

  /* ---------- Rótulos de valor ----------

     A regra é rotular tudo, e a única forma de garantir que nada se
     sobreponha é **colocar e conferir**, não estimar. A primeira versão
     estimava — decidia por fórmula se os rótulos caberiam — e errou duas
     vezes, nas duas direções:

       * esqueceu que o halo (`stroke-width: 3`, centrado na borda da
         letra) cresce 1,5px para cada lado e conta como espaço ocupado.
         Trinta e quatro rótulos se encostaram numa matriz de seis
         contratadas por vinte semanas;
       * e girava o rótulo quando ele não cabia deitado, o que para
         número curto é pior: em pé o texto passa a ocupar a caixa em da
         fonte, ~1,3 do corpo, contra ~0,73 por caractere deitado. Para
         dois dígitos, girar SEMPRE ocupa mais espaço que não girar. A
         rotação saiu.

     O que ficou: `colocarRotulos` desenha um candidato de cada vez,
     testa a caixa dele contra tudo que já foi colocado e, se bater,
     tenta um degrau acima antes de desistir. O que não couber em lugar
     nenhum é omitido — e a dica do mouse, que continua ligada, entrega
     o número exato de qualquer ponto.

     As duas constantes de medida foram calibradas com `getBBox` na
     própria fonte da aplicação, não estimadas: 0,73 é a largura máxima
     por caractere observada entre "45", "100", "62%" e "100%" de 7 a
     10px; 1,3 é a altura da caixa em. */

  const HALO = 3;        /* stroke-width do contorno branco */
  const CHAR_EM = 0.73;  /* largura máxima por caractere, medida */
  const ALTURA_EM = 1.3; /* altura da caixa em, medida */

  /* `estilo`: { tamanho, cor, ancora } */
  function textoComHalo(x, y, conteudo, estilo) {
    return "<text x='" + x + "' y='" + y + "' font-size='" + estilo.tamanho +
      "' font-weight='700' fill='" + estilo.cor +
      "' text-anchor='" + (estilo.ancora || "middle") +
      "' stroke='#fff' stroke-width='" + HALO +
      "' paint-order='stroke' stroke-linejoin='round'>" + esc(conteudo) + "</text>";
  }

  function caixaDoRotulo(x, y, texto, tamanho) {
    const largura = String(texto).length * CHAR_EM * tamanho + HALO;
    const altura = ALTURA_EM * tamanho + HALO;
    /* `y` é a linha de base: a letra sobe a maior parte da caixa acima
       dela e desce pouco. */
    return {
      esq: x - largura / 2, dir: x + largura / 2,
      topo: y - altura * 0.8, base: y + altura * 0.2,
    };
  }

  function seCruzam(a, b) {
    return a.esq < b.dir && b.esq < a.dir && a.topo < b.base && b.topo < a.base;
  }

  /* Coloca o que couber, na ordem recebida — quem vem primeiro tem
     preferência. Cada candidato tenta a posição natural e até três
     degraus acima antes de ser descartado.

     `candidatos`: [{ x, y, texto, cor, tamanho }] */
  function colocarRotulos(candidatos, limiteTopo) {
    const postos = [];
    let saida = "";
    candidatos.forEach(function (c) {
      const degrau = ALTURA_EM * c.tamanho + 2;
      for (let tentativa = 0; tentativa < 4; tentativa++) {
        const y = c.y - tentativa * degrau;
        const caixa = caixaDoRotulo(c.x, y, c.texto, c.tamanho);
        if (caixa.topo < limiteTopo) break;
        const bate = postos.some(function (p) { return seCruzam(p, caixa); });
        if (!bate) {
          postos.push(caixa);
          saida += textoComHalo(c.x, y, c.texto, { tamanho: c.tamanho, cor: c.cor });
          return;
        }
      }
    });
    return saida;
  }

  /* ---------- dica flutuante ---------- */

  function dicaDe(container) {
    let dica = container.querySelector(".grafico-dica");
    if (!dica) {
      dica = document.createElement("div");
      dica.className = "grafico-dica";
      container.appendChild(dica);
    }
    return dica;
  }

  function mostrarDica(container, html, evento) {
    const dica = dicaDe(container);
    dica.innerHTML = html;
    dica.classList.add("is-visivel");
    const caixa = container.getBoundingClientRect();
    let x = evento.clientX - caixa.left + 14;
    let y = evento.clientY - caixa.top + 14;
    if (x + dica.offsetWidth > container.clientWidth - 8) {
      x = Math.max(4, evento.clientX - caixa.left - dica.offsetWidth - 14);
    }
    if (y + dica.offsetHeight > container.clientHeight - 8) {
      y = Math.max(4, container.clientHeight - dica.offsetHeight - 8);
    }
    dica.style.left = x + "px";
    dica.style.top = y + "px";
  }

  function ligarDica(container, montarHtml) {
    container.querySelectorAll("[data-alvo]").forEach(function (alvo) {
      alvo.addEventListener("mousemove", function (evento) {
        mostrarDica(container, montarHtml(Number(this.dataset.alvo)), evento);
      });
      alvo.addEventListener("mouseleave", function () {
        const dica = container.querySelector(".grafico-dica");
        if (dica) dica.classList.remove("is-visivel");
      });
    });
  }

  function linhaDica(rotulo, valor, cor) {
    const marcador = cor
      ? "<i style='display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:6px;background:" + cor + "'></i>"
      : "";
    return "<div><span>" + marcador + esc(rotulo) + "</span><strong>" + esc(valor) + "</strong></div>";
  }

  /* ============================================================
     Motor de drill — mês por padrão, semana ao clique
     ============================================================ */

  function agruparPorMes(pontos) {
    const mapa = {};
    const meses = [];
    pontos.forEach(function (p) {
      const chave = p.ano + "-" + p.mes;
      if (!mapa[chave]) {
        mapa[chave] = {
          chave: chave, ano: p.ano, mes: p.mes,
          nome: p.mesNome || MESES[p.mes - 1] || "",
          semanas: [],
        };
        meses.push(mapa[chave]);
      }
      mapa[chave].semanas.push(p);
    });
    meses.sort(function (a, b) { return a.ano - b.ano || a.mes - b.mes; });
    meses.forEach(function (mes) {
      mes.semanas.sort(function (a, b) { return a.numero - b.numero; });
    });
    return meses;
  }

  function montarColunas(meses, expandidos, adaptador) {
    const colunas = [];
    const faixas = [];
    meses.forEach(function (mes) {
      const inicio = colunas.length;
      const aberto = Boolean(expandidos[mes.chave]);
      if (aberto) {
        mes.semanas.forEach(function (s) { colunas.push(adaptador.daSemana(s)); });
      } else {
        colunas.push(adaptador.doMes(mes));
      }
      faixas.push({
        chave: mes.chave, nome: mes.nome, ano: mes.ano,
        aberto: aberto, inicio: inicio, fim: colunas.length - 1,
      });
    });
    return { colunas: colunas, faixas: faixas };
  }

  function geometria(container, total, alturaMinima) {
    const largura = Math.max(container.clientWidth || 760, 320);
    const altura = Math.max(container.clientHeight || 0, alturaMinima || 300);
    const desenho = altura - MARGEM.topo - MARGEM.base;
    const util = largura - MARGEM.esquerda - MARGEM.direita;
    const slot = util / Math.max(total, 1);
    return {
      largura: largura,
      altura: altura,
      desenho: desenho,
      slot: slot,
      topo: MARGEM.topo,
      base: MARGEM.topo + desenho,
      esquerda: MARGEM.esquerda,
      direita: largura - MARGEM.direita,
      x: function (i) { return MARGEM.esquerda + i * slot + slot / 2; },
      borda: function (i) { return MARGEM.esquerda + i * slot; },
    };
  }

  function gradeY(geo, teto, sufixo) {
    const cor = cores();
    let saida = "";
    for (let t = 0; t <= 4; t++) {
      const valor = (teto * t) / 4;
      const y = geo.base - (valor / teto) * geo.desenho;
      saida += "<line x1='" + geo.esquerda + "' y1='" + y + "' x2='" + geo.direita +
        "' y2='" + y + "' stroke='" + cor.grade + "' stroke-width='1'/>";
      saida += textoSvg(geo.esquerda - 8, y + 4, fmt(valor, 0) + (sufixo || ""),
        "font-size='10' fill='" + cor.apagado + "' text-anchor='end'");
    }
    return saida;
  }

  function fundoDosMeses(faixas, geo) {
    const cor = cores();
    let saida = "";
    faixas.forEach(function (faixa) {
      if (!faixa.aberto) return;
      saida += "<rect x='" + geo.borda(faixa.inicio) + "' y='" + geo.topo + "' width='" +
        (geo.borda(faixa.fim + 1) - geo.borda(faixa.inicio)) + "' height='" +
        (geo.desenho + 4) + "' fill='" + cor.realce + "'/>";
    });
    return saida;
  }

  function eixoDeAnos(faixas, geo) {
    const cor = cores();
    const anos = {};
    const ordem = [];
    faixas.forEach(function (faixa) {
      if (!anos[faixa.ano]) {
        anos[faixa.ano] = { inicio: faixa.inicio, fim: faixa.fim };
        ordem.push(faixa.ano);
      }
      anos[faixa.ano].fim = faixa.fim;
    });
    let saida = "";
    ordem.forEach(function (ano, i) {
      const intervalo = anos[ano];
      const centro = (geo.borda(intervalo.inicio) + geo.borda(intervalo.fim + 1)) / 2;
      saida += textoSvg(centro, geo.base + 64, ano,
        "font-size='14' font-weight='700' fill='" + cor.marca + "' text-anchor='middle'");
      if (i > 0) {
        saida += "<line x1='" + geo.borda(intervalo.inicio) + "' y1='" + (geo.base + 46) +
          "' x2='" + geo.borda(intervalo.inicio) + "' y2='" + (geo.base + 72) +
          "' stroke='" + cor.marca + "' stroke-width='1.5'/>";
      }
    });
    return saida;
  }

  /* Três linhas sob o eixo: semanas (só nos meses abertos), meses
     (sempre, clicáveis) e anos. É o que deixa a leitura passar de
     "como foi o ano" para "o que houve na semana 32" sem trocar de
     gráfico. */
  function eixoDrill(colunas, faixas, geo) {
    const cor = cores();
    let saida = "<line x1='" + geo.esquerda + "' y1='" + geo.base + "' x2='" + geo.direita +
      "' y2='" + geo.base + "' stroke='" + cor.eixo + "' stroke-width='1'/>";

    faixas.forEach(function (faixa, i) {
      if (i === 0) return;
      const x = geo.borda(faixa.inicio);
      saida += "<line x1='" + x + "' y1='" + (geo.base + 2) + "' x2='" + x + "' y2='" +
        (geo.base + 74) + "' stroke='" + cor.grade + "' stroke-width='1' stroke-dasharray='2,3'/>";
    });

    const tamanhoSemana = Math.max(9, Math.min(13, geo.slot * 0.28));
    colunas.forEach(function (coluna, i) {
      if (!coluna.semanal) return;
      saida += textoSvg(geo.x(i), geo.base + 16, coluna.rotulo,
        "font-size='" + tamanhoSemana + "' font-weight='600' fill='" + cor.realizado +
        "' text-anchor='middle'");
    });

    const tamanhoMes = Math.max(9, Math.min(14, geo.slot * 0.24));
    faixas.forEach(function (faixa) {
      const centro = (geo.borda(faixa.inicio) + geo.borda(faixa.fim + 1)) / 2;
      saida += "<text x='" + centro + "' y='" + (geo.base + 36) + "' font-size='" + tamanhoMes +
        "' font-weight='600' fill='" + (faixa.aberto ? cor.marca : cor.texto) +
        "' text-anchor='middle' data-mes='" + esc(faixa.chave) +
        "' style='cursor:pointer'>" + esc(faixa.nome) + "</text>";
      if (faixa.aberto) {
        saida += "<line x1='" + (geo.borda(faixa.inicio) + 4) + "' y1='" + (geo.base + 40) +
          "' x2='" + (geo.borda(faixa.fim + 1) - 4) + "' y2='" + (geo.base + 40) +
          "' stroke='" + cor.realizado + "' stroke-width='1.5'/>";
      }
    });

    return saida + eixoDeAnos(faixas, geo);
  }

  function areasDeDica(colunas, geo) {
    let saida = "";
    colunas.forEach(function (coluna, i) {
      saida += "<rect data-alvo='" + i + "' x='" + geo.borda(i) + "' y='" + geo.topo +
        "' width='" + geo.slot + "' height='" + geo.desenho + "' fill='transparent'/>";
    });
    return saida;
  }

  function ligarDrill(container, estado) {
    container.querySelectorAll("[data-mes]").forEach(function (rotulo) {
      rotulo.addEventListener("click", function () {
        const chave = this.dataset.mes;
        estado.expandidos[chave] = !estado.expandidos[chave];
        redesenhar(container);
      });
    });
  }

  function botoesDeAno(container, estado, anos) {
    const painel = container.parentElement
      ? container.parentElement.querySelector("[data-grafico-anos]")
      : null;
    if (!painel) return;
    if (anos.length < 2) { painel.innerHTML = ""; return; }

    let html = "<button type='button' class='periodo-botao" +
      (estado.ano ? "" : " is-active") + "' data-ano=''>Todos</button>";
    anos.forEach(function (ano) {
      html += "<button type='button' class='periodo-botao" +
        (estado.ano === ano ? " is-active" : "") + "' data-ano='" + ano + "'>" + ano + "</button>";
    });
    painel.innerHTML = html;

    painel.querySelectorAll(".periodo-botao").forEach(function (botao) {
      botao.addEventListener("click", function () {
        estado.ano = this.dataset.ano ? Number(this.dataset.ano) : null;
        estado.expandidos = {};
        redesenhar(container);
      });
    });
  }

  function vazio(container, mensagem) {
    container.innerHTML = "<p class='hint' style='padding:24px'>" + esc(mensagem) + "</p>";
  }

  /* O desenho comum: filtra o ano, agrupa, monta a geometria e delega
     as barras e as linhas ao adaptador. */
  function desenharComDrill(container, estado, adaptador) {
    const todos = adaptador.pontos(estado.dados);
    const filtrados = estado.ano
      ? todos.filter(function (p) { return p.ano === estado.ano; })
      : todos;

    const anos = [];
    todos.forEach(function (p) { if (anos.indexOf(p.ano) < 0) anos.push(p.ano); });
    anos.sort();

    if (!filtrados.length) {
      vazio(container, "Sem dados no período.");
      botoesDeAno(container, estado, anos);
      return;
    }

    const montado = montarColunas(agruparPorMes(filtrados), estado.expandidos, adaptador);
    const geo = geometria(container, montado.colunas.length, adaptador.alturaMinima);

    let svg = svgAbre(geo, adaptador.rotulo);
    svg += fundoDosMeses(montado.faixas, geo);
    svg += adaptador.desenhar(montado.colunas, geo);
    svg += eixoDrill(montado.colunas, montado.faixas, geo);
    svg += areasDeDica(montado.colunas, geo);
    svg += "</svg>";

    container.innerHTML = svg;
    dicaDe(container);
    ligarDrill(container, estado);
    ligarDica(container, function (indice) { return adaptador.dica(montado.colunas[indice]); });
    botoesDeAno(container, estado, anos);
    if (adaptador.aoDesenhar) adaptador.aoDesenhar(container);
  }

  /* ============================================================
     Curva S — avanço físico por semana, mês e ano
     ============================================================ */

  function somarCampos(semanas, campos) {
    const total = {};
    campos.forEach(function (campo) { total[campo] = 0; });
    semanas.forEach(function (s) {
      campos.forEach(function (campo) { total[campo] += s[campo] || 0; });
    });
    return total;
  }

  function colunaDaCurva(rotulo, detalhe, semanal, dados) {
    return {
      rotulo: rotulo, detalhe: detalhe, semanal: semanal,
      base: dados.base, previsto: dados.previsto, realizado: dados.realizado,
      baseAcumulado: dados.baseAcumulado,
      previstoAcumulado: dados.previstoAcumulado,
      realizadoAcumulado: dados.realizadoAcumulado,
      atividades: dados.atividades,
    };
  }

  function barrasDaCurva(colunas, geo) {
    const cor = cores();
    const maior = colunas.reduce(function (m, c) {
      return Math.max(m, c.base || 0, c.previsto || 0, c.realizado || 0);
    }, 0);
    const escala = maior > 0 ? (geo.desenho * 0.34) / maior : 1;
    const largura = Math.max(3, Math.min(11, geo.slot * 0.2));
    const vao = Math.max(1, largura * 0.18);
    const grupo = 3 * largura + 2 * vao;
    const series = [
      { chave: "base", cor: cor.base },
      { chave: "previsto", cor: cor.previsto },
      { chave: "realizado", cor: cor.realizado },
    ];

    let saida = "";
    colunas.forEach(function (coluna, i) {
      const centro = geo.x(i);
      series.forEach(function (serie, ordem) {
        const valor = coluna[serie.chave] || 0;
        if (valor <= 0) return;
        const alturaBarra = valor * escala;
        const x = centro - grupo / 2 + ordem * (largura + vao);
        saida += "<rect x='" + x + "' y='" + (geo.base - alturaBarra) + "' width='" +
          largura + "' height='" + alturaBarra + "' rx='1' fill='" + serie.cor +
          "' opacity='0.85'/>";
      });
    });
    return saida;
  }

  function linhasAcumuladas(colunas, geo) {
    const cor = cores();
    const escalaY = function (valor) {
      return geo.base - (Math.min(valor, 100) / 100) * geo.desenho;
    };
    const series = [
      { chave: "baseAcumulado", cor: cor.base, largura: 1.5, traco: "6,4", ponto: 2.5 },
      { chave: "previstoAcumulado", cor: cor.previsto, largura: 2.5, traco: "", ponto: 3.5 },
      { chave: "realizadoAcumulado", cor: cor.realizado, largura: 3.5, traco: "", ponto: 4.5 },
    ];
    let saida = "";
    series.forEach(function (serie, ordem) {
      const pontos = [];
      colunas.forEach(function (coluna, i) {
        const valor = coluna[serie.chave];
        if (valor === null || valor === undefined) return;
        pontos.push([geo.x(i), escalaY(valor)]);
      });
      if (!pontos.length) return;
      const traco = serie.traco ? " stroke-dasharray='" + serie.traco + "'" : "";
      const id = ordem === 2 ? " id='linha-realizado'" : "";
      saida += "<path" + id + " d='" + suavizar(pontos) + "' fill='none' stroke='" +
        serie.cor + "' stroke-width='" + serie.largura +
        "' stroke-linecap='round' stroke-linejoin='round'" + traco + "/>";
      pontos.forEach(function (p) {
        saida += "<circle cx='" + p[0] + "' cy='" + p[1] + "' r='" + serie.ponto +
          "' fill='" + serie.cor + "' stroke='#fff' stroke-width='1.5'/>";
      });
    });
    return saida;
  }

  function rotulosDoRealizado(colunas, geo) {
    const cor = cores();
    let ultimoX = -999;
    let saida = "";
    colunas.forEach(function (coluna, i) {
      const valor = coluna.realizadoAcumulado;
      if (valor === null || valor === undefined) return;
      const x = geo.x(i);
      if (x - ultimoX < 58) return;
      ultimoX = x;
      const y = geo.base - (Math.min(valor, 100) / 100) * geo.desenho;
      const alvo = y - geo.topo > 40 ? y - 12 : y + 30;
      saida += "<rect x='" + (x - 26) + "' y='" + (alvo - 20) + "' width='52' height='21' rx='4' fill='" +
        cor.realizado + "' opacity='0.94'/>";
      saida += textoSvg(x, alvo - 5, fmt(valor, 1) + "%",
        "font-size='11' font-weight='700' fill='#fff' text-anchor='middle'");
    });
    return saida;
  }

  function animarLinha(container) {
    const linha = container.querySelector("#linha-realizado");
    if (!linha || !linha.getTotalLength) return;
    const comprimento = linha.getTotalLength();
    linha.style.strokeDasharray = comprimento;
    linha.style.setProperty("--traco", comprimento);
    linha.style.animation = "tracarLinha 1.2s cubic-bezier(.4,0,.2,1) both";
  }

  const CAMPOS_CURVA = ["base", "previsto", "realizado"];

  const ADAPTADOR_CURVA = {
    rotulo: "Curva S do avanço físico",
    alturaMinima: 360,
    pontos: function (dados) { return dados; },
    daSemana: function (p) {
      return colunaDaCurva("S" + String(p.numero).padStart(2, "0"),
        p.semana + " · " + p.periodo, true, p);
    },
    doMes: function (mes) {
      const soma = somarCampos(mes.semanas, CAMPOS_CURVA);
      const ultimo = mes.semanas[mes.semanas.length - 1];
      soma.baseAcumulado = ultimo.baseAcumulado;
      soma.previstoAcumulado = ultimo.previstoAcumulado;
      soma.realizadoAcumulado = ultimo.realizadoAcumulado;
      soma.atividades = mes.semanas.reduce(function (t, s) { return t + (s.atividades || 0); }, 0);
      return colunaDaCurva(mes.nome, mes.nome + " de " + mes.ano, false, soma);
    },
    desenhar: function (colunas, geo) {
      return gradeY(geo, 100, "%") + barrasDaCurva(colunas, geo) +
        linhasAcumuladas(colunas, geo) + rotulosDoRealizado(colunas, geo);
    },
    dica: function (coluna) {
      const cor = cores();
      return "<b>" + esc(coluna.detalhe) + "</b>" +
        linhaDica("Previsto no período", pct(coluna.previsto), cor.previsto) +
        linhaDica("Realizado no período", pct(coluna.realizado), cor.realizado) +
        linhaDica("Previsto acumulado", pct(coluna.previstoAcumulado), cor.previsto) +
        linhaDica("Realizado acumulado", pct(coluna.realizadoAcumulado), cor.realizado) +
        linhaDica("Referência", pct(coluna.baseAcumulado), cor.base);
    },
    aoDesenhar: animarLinha,
  };

  /* ============================================================
     Barras — previsto contra realizado, com o mesmo drill
     ============================================================ */

  function colunaDeBarras(rotulo, detalhe, semanal, dados) {
    return {
      rotulo: rotulo, detalhe: detalhe, semanal: semanal,
      previsto: dados.previsto, realizado: dados.realizado,
      atividades: dados.atividades,
    };
  }

  function barrasComparadas(colunas, geo) {
    const cor = cores();
    const maior = colunas.reduce(function (m, c) {
      return Math.max(m, c.previsto || 0, c.realizado || 0);
    }, 0);
    const teto = tetoRedondo(maior);
    const escalaY = function (valor) { return (valor / teto) * geo.desenho; };
    const largura = Math.max(6, Math.min(26, geo.slot * 0.3));
    const tamanho = Math.max(7, Math.min(11, (largura + 4) * 0.7));

    let saida = gradeY(geo, teto, "%");
    const rotulos = [];
    colunas.forEach(function (coluna, i) {
      const centro = geo.x(i);
      const alturaPrev = escalaY(coluna.previsto || 0);
      const alturaReal = escalaY(coluna.realizado || 0);
      const xPrev = centro - largura - 2;
      const xReal = centro + 2;

      saida += "<rect x='" + xPrev + "' y='" + (geo.base - alturaPrev) + "' width='" +
        largura + "' height='" + alturaPrev + "' rx='2' fill='" + cor.previsto + "'/>";
      saida += "<rect x='" + xReal + "' y='" + (geo.base - alturaReal) + "' width='" +
        largura + "' height='" + alturaReal + "' rx='2' fill='" + cor.realizado + "'/>";

      rotulos.push({ x: xPrev + largura / 2, y: geo.base - alturaPrev - 4,
        texto: fmt(coluna.previsto, 1), cor: cor.previsto, tamanho: tamanho });
      rotulos.push({ x: xReal + largura / 2, y: geo.base - alturaReal - 4,
        texto: fmt(coluna.realizado, 1), cor: cor.marca, tamanho: tamanho });
    });
    /* Toda barra é rotulada, e não só quando o slot passa de 34px como
       antes: `colocarRotulos` confere par a par e decide pelo espaço
       real, em vez de por um limiar único para o gráfico inteiro. */
    return saida + colocarRotulos(rotulos, geo.topo);
  }

  const ADAPTADOR_BARRAS = {
    rotulo: "Previsto contra realizado",
    alturaMinima: 300,
    pontos: function (dados) { return dados.itens || []; },
    daSemana: function (p) {
      return colunaDeBarras("S" + String(p.numero).padStart(2, "0"),
        p.semana + " · " + p.periodo, true, p);
    },
    doMes: function (mes) {
      const soma = somarCampos(mes.semanas, ["previsto", "realizado"]);
      soma.atividades = mes.semanas.reduce(function (t, s) { return t + (s.atividades || 0); }, 0);
      return colunaDeBarras(mes.nome, mes.nome + " de " + mes.ano +
        " · " + mes.semanas.length + " semana(s)", false, soma);
    },
    desenhar: barrasComparadas,
    dica: function (coluna) {
      const cor = cores();
      const saldo = (coluna.realizado || 0) - (coluna.previsto || 0);
      return "<b>" + esc(coluna.detalhe) + "</b>" +
        linhaDica("Previsto", pct(coluna.previsto), cor.previsto) +
        linhaDica("Realizado", pct(coluna.realizado), cor.realizado) +
        linhaDica("Saldo", (saldo > 0 ? "+" : "") + pct(saldo));
    },
  };

  /* ============================================================
     Curva de aderência por contratada

     Mesma gramática visual da curva S: **barra do período + linha do
     acumulado**, por contratada. A barra responde "como foi este mês";
     a linha, "como está o ano". As duas juntas evitam a leitura errada
     mais comum de uma série de aderência — um mês ruim isolado parece
     queda de patamar quando na verdade o acumulado nem se moveu.

     A linha tracejada é a **meta do projeto**, que vem no payload. Uma
     linha de aderência sem a meta desenhada obriga quem lê a manter o
     número na cabeça para saber quem está acima.

     Consolidar o mês NÃO é a média das aderências semanais: é a soma do
     realizado do mês sobre a soma do previsto do mês. O mesmo vale para
     o acumulado, que soma quantidade período a período e divide uma vez
     no fim. Por isso o servidor manda quantidade, e a divisão acontece
     aqui, no nível que está sendo exibido — trocar de mês para semana
     refaz a conta em vez de reaproveitar um percentual pronto.
     ============================================================ */

  function aderenciaDe(acumulado) {
    if (!acumulado || !acumulado.previsto) return null;
    return Math.round((acumulado.realizado / acumulado.previsto) * 1000) / 10;
  }

  function colunaDeAderencia(identificacao, series, quantidades) {
    const valores = {};
    series.forEach(function (nome) { valores[nome] = aderenciaDe(quantidades[nome]); });
    return {
      rotulo: identificacao.rotulo,
      detalhe: identificacao.detalhe,
      semanal: identificacao.semanal,
      /* `valores` é a aderência DO PERÍODO desta coluna — vira barra.
         `acumulados` é preenchido depois, no desenho, porque depende da
         sequência inteira de colunas e não só desta. */
      valores: valores,
      acumulados: {},
      quantidades: quantidades,
    };
  }

  /* Soma corrida sobre as colunas já montadas, na ordem em que aparecem.
     Funciona igual com mês fechado ou aberto: as colunas exibidas
     particionam a linha do tempo de um jeito ou de outro, e a soma das
     partes é a mesma. */
  function acumularAderencia(colunas, series) {
    const corrido = {};
    series.forEach(function (nome) { corrido[nome] = { previsto: 0, realizado: 0 }; });
    colunas.forEach(function (coluna) {
      series.forEach(function (nome) {
        const q = (coluna.quantidades || {})[nome];
        if (q) {
          corrido[nome].previsto += q.previsto || 0;
          corrido[nome].realizado += q.realizado || 0;
        }
        coluna.acumulados[nome] = aderenciaDe(corrido[nome]);
      });
    });
  }

  function somarPorEmpresa(semanas, series) {
    const total = {};
    series.forEach(function (nome) { total[nome] = { previsto: 0, realizado: 0 }; });
    semanas.forEach(function (s) {
      series.forEach(function (nome) {
        const v = (s.valores || {})[nome];
        if (!v) return;
        total[nome].previsto += v.previsto || 0;
        total[nome].realizado += v.realizado || 0;
      });
    });
    return total;
  }

  /* Barras da aderência do período, agrupadas por coluna.

     Ficam presas a 34% da altura do desenho, como na curva S: elas são
     contexto para as linhas, não o assunto. Deixá-las usarem a escala
     de 0 a 100 do eixo faria um mês de 90% cobrir a própria linha. */
  function barrasDeAderencia(colunas, geo, series) {
    const tons = paleta();
    const maior = colunas.reduce(function (m, coluna) {
      return series.reduce(function (n, nome) {
        return Math.max(n, coluna.valores[nome] || 0);
      }, m);
    }, 0);
    if (maior <= 0) return { svg: "", rotulos: [] };

    const escala = (geo.desenho * 0.34) / maior;
    const quantas = Math.max(series.length, 1);
    const largura = Math.max(2.5, Math.min(12, (geo.slot * 0.62) / quantas));
    const vao = Math.max(1, largura * 0.15);
    const grupo = quantas * largura + (quantas - 1) * vao;

    let saida = "";
    const rotulos = [];
    colunas.forEach(function (coluna, i) {
      const inicio = geo.x(i) - grupo / 2;
      series.forEach(function (nome, ordem) {
        const valor = coluna.valores[nome];
        if (valor === null || valor === undefined || valor <= 0) return;
        const alturaBarra = valor * escala;
        const x = inicio + ordem * (largura + vao);
        saida += "<rect x='" + x + "' y='" + (geo.base - alturaBarra) + "' width='" +
          largura + "' height='" + alturaBarra + "' rx='1' fill='" +
          tons[ordem % tons.length] + "' opacity='0.85'/>";
        rotulos.push({
          x: x + largura / 2,
          y: geo.base - alturaBarra - 4,
          texto: fmt(valor, 0),
          cor: tons[ordem % tons.length],
          /* O corpo acompanha o passo entre barras, com piso de 7px:
             abaixo disso o número deixa de ser lido e vira sujeira. */
          tamanho: Math.max(7, Math.min(10, (largura + vao) * 0.8)),
        });
      });
    });
    /* Devolve o desenho e os CANDIDATOS a rótulo, sem colocá-los. Quem
       chama junta estes candidatos aos dos pontos de linha e faz uma
       colocação só — duas passadas independentes não se enxergam, e foi
       assim que um rótulo de barra encostou num de ponto a 768px. */
    return { svg: saida, rotulos: rotulos };
  }

  /* A meta do projeto, atravessando o gráfico. Tracejada e cinza para
     não competir com as contratadas: é referência, não série. */
  function linhaDaMeta(meta, geo, escalaY) {
    if (!meta || meta <= 0) return "";
    const cor = cores();
    const y = escalaY(meta);
    if (y < geo.topo || y > geo.base) return "";
    return "<line x1='" + geo.esquerda + "' y1='" + y + "' x2='" + geo.direita + "' y2='" + y +
      "' stroke='" + cor.base + "' stroke-width='1.5' stroke-dasharray='6,4'/>" +
      "<rect x='" + (geo.direita - 74) + "' y='" + (y - 17) + "' width='72' height='15' rx='3' fill='" +
      cor.realce + "'/>" +
      textoSvg(geo.direita - 38, y - 6, "Meta " + fmt(meta, 0) + "%",
        "font-size='10' font-weight='700' fill='" + cor.texto + "' text-anchor='middle'");
  }

  /* Teto do eixo de percentual.

     `tetoRedondo` é feito para quantidade e arredonda pela potência de
     dez: 118 vira 200, e metade do gráfico fica vazia. Aqui 100 é o
     patamar natural, e acima dele o passo de 20 mantém os rótulos dos
     quartos inteiros — 120 dá 0/30/60/90/120, 140 dá 0/35/70/105/140. */
  function tetoDePercentual(maior) {
    if (maior <= 100) return 100;
    return Math.ceil(maior / 20) * 20;
  }

  function linhasPorEmpresa(colunas, geo, series, meta) {
    const tons = paleta();
    acumularAderencia(colunas, series);

    /* O teto olha para os dois desenhos. O acumulado costuma ficar sob
       100%, mas uma contratada que entrega acima do previsto passa disso
       — e um ponto acima do topo do eixo é um ponto fora do gráfico. */
    const maior = colunas.reduce(function (m, coluna) {
      return series.reduce(function (n, nome) {
        return Math.max(n, coluna.valores[nome] || 0, coluna.acumulados[nome] || 0);
      }, m);
    }, meta || 0);
    const teto = tetoDePercentual(maior);
    const escalaY = function (valor) { return geo.base - (valor / teto) * geo.desenho; };

    const barras = barrasDeAderencia(colunas, geo, series);
    let saida = gradeY(geo, teto, "%");
    saida += barras.svg;
    saida += linhaDaMeta(meta, geo, escalaY);

    const porColuna = {};
    series.forEach(function (nome, ordem) {
      const cor = tons[ordem % tons.length];
      const pontos = [];
      colunas.forEach(function (coluna, i) {
        const valor = coluna.acumulados[nome];
        if (valor === null || valor === undefined) return;
        const x = geo.x(i);
        const y = escalaY(valor);
        pontos.push([x, y]);
        if (!porColuna[i]) porColuna[i] = [];
        porColuna[i].push({ x: x, y: y, valor: valor, cor: cor });
      });
      if (!pontos.length) return;
      saida += "<path data-anima='" + ordem + "' d='" + suavizar(pontos) + "' fill='none' stroke='" +
        cor + "' stroke-width='2.75' stroke-linecap='round' stroke-linejoin='round'" +
        tracoDaSerie(ordem) + "/>";
      pontos.forEach(function (p) {
        saida += "<circle cx='" + p[0] + "' cy='" + p[1] + "' r='3.6' fill='#fff' stroke='" +
          cor + "' stroke-width='2'/>";
      });
    });

    /* Ponto antes de barra na fila: o acumulado é o número que responde
       à pergunta da tela. Se um dos dois tiver de sair por falta de
       espaço, que saia o da barra, cujo valor a dica entrega igual. */
    return saida + colocarRotulos(
      candidatosDosPontos(porColuna).concat(barras.rotulos), geo.topo);
  }

  /* Um rótulo por ponto de linha.

     A ordem importa: coluna a coluna, e dentro da coluna de cima para
     baixo. Assim, quando duas contratadas se cruzam num mês, quem está
     por cima no gráfico fica com a posição natural e quem está por baixo
     é empurrada — que é a leitura que a pessoa espera. Fosse a ordem por
     série, o rótulo deslocado seria o de uma contratada arbitrária. */
  function candidatosDosPontos(porColuna) {
    const candidatos = [];
    Object.keys(porColuna).forEach(function (k) {
      porColuna[k]
        .slice()
        .sort(function (a, b) { return a.y - b.y; })
        .forEach(function (p) {
          candidatos.push({
            x: p.x, y: p.y - 9, texto: fmt(p.valor, 0) + "%", cor: p.cor, tamanho: 10,
          });
        });
    });
    return candidatos;
  }

  /* Cada contratada aparece duas vezes no desenho — barra e linha — e a
     legenda mostra as duas formas, como no visual do Power BI que
     originou o gráfico. Sem isso a barra fica sem nome. */
  function legendaDeSeries(container, series) {
    const painel = container.parentElement
      ? container.parentElement.querySelector("[data-grafico-legenda]")
      : null;
    if (!painel) return;
    const tons = paleta();
    painel.innerHTML = series.map(function (nome, i) {
      const cor = tons[i % tons.length];
      return "<span><i style='background:" + cor + "'></i>" +
        "<i class='is-linha' style='" + amostraDoTraco(i, cor) + "'></i>" +
        esc(nome) + "</span>";
    }).join("") +
      "<span><i class='is-tracejada'></i>Meta</span>";
  }

  /* Todas as linhas se traçam, com um atraso por série para que a
     leitura acompanhe uma de cada vez em vez de ver três aparecerem
     sobrepostas. */
  function animarLinhas(container) {
    container.querySelectorAll("[data-anima]").forEach(function (linha) {
      if (!linha.getTotalLength) return;
      const comprimento = linha.getTotalLength();
      linha.style.strokeDasharray = comprimento;
      linha.style.setProperty("--traco", comprimento);
      linha.style.animation = "tracarLinha 1.1s cubic-bezier(.4,0,.2,1) " +
        (Number(linha.dataset.anima) * 0.12) + "s both";
    });
  }

  function adaptadorDeAderencia(series, meta) {
    return {
      rotulo: "Evolução da aderência por contratada",
      alturaMinima: 320,
      pontos: function (dados) { return dados.pontos || []; },
      daSemana: function (p) {
        return colunaDeAderencia(
          {
            rotulo: "S" + String(p.numero).padStart(2, "0"),
            detalhe: p.semana + " · " + p.periodo,
            semanal: true,
          },
          series,
          p.valores || {},
        );
      },
      doMes: function (mes) {
        return colunaDeAderencia(
          {
            rotulo: mes.nome,
            detalhe: mes.nome + " de " + mes.ano + " · " + mes.semanas.length + " semana(s)",
            semanal: false,
          },
          series,
          somarPorEmpresa(mes.semanas, series),
        );
      },
      desenhar: function (colunas, geo) {
        return linhasPorEmpresa(colunas, geo, series, meta);
      },
      dica: function (coluna) {
        const tons = paleta();
        let html = "<b>" + esc(coluna.detalhe) + "</b>";
        series.forEach(function (nome, i) {
          const periodo = coluna.valores[nome];
          const acumulado = coluna.acumulados[nome];
          if ((periodo === null || periodo === undefined) &&
              (acumulado === null || acumulado === undefined)) return;
          html += linhaDica(nome,
            (periodo === null || periodo === undefined ? "—" : pct(periodo, 0)) +
            "  ·  " + (acumulado === null || acumulado === undefined ? "—" : pct(acumulado, 0)),
            tons[i % tons.length]);
        });
        return html + "<div style='margin-top:4px;opacity:.7'><span>no período · acumulado</span></div>";
      },
      aoDesenhar: animarLinhas,
    };
  }

  /* ============================================================
     Barras simples — sem drill

     Para séries que não são calendário: os sete dias de uma semana, por
     exemplo. Forçá-las no motor de drill exigiria inventar mês e ano
     para um eixo que não tem nenhum dos dois.
     ============================================================ */

  function desenharBarrasSimples(container, estado) {
    const itens = estado.dados.itens || [];
    if (!itens.length) { vazio(container, "Sem dados no período."); return; }

    const cor = cores();
    const largura = Math.max(container.clientWidth || 520, 300);
    const altura = Math.max(container.clientHeight || 0, 240);
    const margem = { esquerda: 46, direita: 14, topo: 18, base: 44 };
    const desenho = altura - margem.topo - margem.base;
    const slot = (largura - margem.esquerda - margem.direita) / itens.length;
    const base = margem.topo + desenho;
    const teto = tetoRedondo(itens.reduce(function (m, i) {
      return Math.max(m, i.previsto || 0, i.realizado || 0);
    }, 0));
    const larguraBarra = Math.max(6, Math.min(24, slot * 0.32));

    let svg = "<svg width='" + largura + "' height='" + altura + "' viewBox='0 0 " + largura +
      " " + altura + "' xmlns='http://www.w3.org/2000/svg' role='img' aria-label='" +
      esc(estado.dados.rotulo || "Previsto e realizado") + "'>";

    for (let t = 0; t <= 2; t++) {
      const valor = (teto * t) / 2;
      const y = base - (valor / teto) * desenho;
      svg += "<line x1='" + margem.esquerda + "' y1='" + y + "' x2='" + (largura - margem.direita) +
        "' y2='" + y + "' stroke='" + cor.grade + "' stroke-width='1'/>";
      svg += textoSvg(margem.esquerda - 8, y + 4, fmt(valor, 0),
        "font-size='10' fill='" + cor.apagado + "' text-anchor='end'");
    }

    itens.forEach(function (item, i) {
      const centro = margem.esquerda + i * slot + slot / 2;
      const alturaPrev = ((item.previsto || 0) / teto) * desenho;
      const alturaReal = ((item.realizado || 0) / teto) * desenho;
      svg += "<rect x='" + (centro - larguraBarra - 2) + "' y='" + (base - alturaPrev) +
        "' width='" + larguraBarra + "' height='" + alturaPrev + "' rx='2' fill='" +
        cor.previsto + "'/>";
      svg += "<rect x='" + (centro + 2) + "' y='" + (base - alturaReal) + "' width='" +
        larguraBarra + "' height='" + alturaReal + "' rx='2' fill='" + cor.realizado + "'/>";
      svg += textoSvg(centro, base + 18, item.rotulo,
        "font-size='10' font-weight='600' fill='" + cor.texto + "' text-anchor='middle'");
      svg += "<rect data-alvo='" + i + "' x='" + (margem.esquerda + i * slot) + "' y='" +
        margem.topo + "' width='" + slot + "' height='" + desenho + "' fill='transparent'/>";
    });
    svg += "<line x1='" + margem.esquerda + "' y1='" + base + "' x2='" + (largura - margem.direita) +
      "' y2='" + base + "' stroke='" + cor.eixo + "' stroke-width='1'/>";

    container.innerHTML = svg + "</svg>";
    dicaDe(container);
    ligarDica(container, function (indice) {
      const item = itens[indice];
      const unidade = estado.dados.unidade ? " " + estado.dados.unidade : "";
      return "<b>" + esc(item.detalhe || item.rotulo) + "</b>" +
        linhaDica("Previsto", fmt(item.previsto, 1) + unidade, cor.previsto) +
        linhaDica("Realizado", fmt(item.realizado, 1) + unidade, cor.realizado);
    });
  }

  /* ============================================================
     Rosca — um indicador contra a sua meta
     ============================================================ */

  function corDaFaixa(valor, meta) {
    const cor = cores();
    if (valor >= meta) return cor.realizado;
    if (valor >= meta * 0.75) return cor.alerta;
    return cor.erro;
  }

  function desenharRosca(container, estado) {
    const dados = estado.dados;
    const valor = Math.max(0, Math.min(Number(dados.valor) || 0, 100));
    const meta = Number(dados.meta) || 0;
    const cor = cores();
    const preenchimento = corDaFaixa(valor, meta);
    const lado = 200;
    const raio = 76;
    const perimetro = 2 * Math.PI * raio;
    const traco = (valor / 100) * perimetro;

    let svg = "<svg width='" + lado + "' height='" + lado + "' viewBox='0 0 " + lado + " " +
      lado + "' xmlns='http://www.w3.org/2000/svg' role='img' aria-label='" +
      esc((dados.rotulo || "Indicador") + ": " + pct(valor)) + "'>";
    svg += "<g transform='rotate(-90 100 100)'>";
    svg += "<circle cx='100' cy='100' r='" + raio + "' fill='none' stroke='" + cor.grade +
      "' stroke-width='18'/>";
    svg += "<circle cx='100' cy='100' r='" + raio + "' fill='none' stroke='" + preenchimento +
      "' stroke-width='18' stroke-linecap='round' stroke-dasharray='" + traco + " " +
      (perimetro - traco) + "'/>";
    if (meta > 0) {
      const angulo = (meta / 100) * 2 * Math.PI;
      svg += "<circle cx='" + (100 + Math.cos(angulo) * raio) + "' cy='" +
        (100 + Math.sin(angulo) * raio) + "' r='4' fill='" + cor.marca +
        "' stroke='#fff' stroke-width='2'/>";
    }
    svg += "</g>";
    svg += textoSvg(100, 96, fmt(valor, 1) + "%",
      "font-size='30' font-weight='700' fill='" + cor.marca + "' text-anchor='middle'");
    svg += textoSvg(100, 118, dados.rotulo || "",
      "font-size='11' font-weight='600' fill='" + cor.texto + "' text-anchor='middle'");
    if (meta > 0) {
      svg += textoSvg(100, 136, "meta " + fmt(meta, 0) + "%",
        "font-size='10' fill='" + cor.apagado + "' text-anchor='middle'");
    }
    container.innerHTML = svg + "</svg>";
  }

  /* ============================================================
     Montagem
     ============================================================ */

  const DESENHOS = {
    "curva-s": function (container, estado) {
      desenharComDrill(container, estado, ADAPTADOR_CURVA);
    },
    barras: function (container, estado) {
      desenharComDrill(container, estado, ADAPTADOR_BARRAS);
    },
    "barras-simples": desenharBarrasSimples,
    aderencia: function (container, estado) {
      const series = estado.dados.series || [];
      if (!series.length) { vazio(container, "Sem contratadas no período."); return; }
      legendaDeSeries(container, series);
      desenharComDrill(container, estado, adaptadorDeAderencia(series, estado.dados.meta));
    },
    rosca: desenharRosca,
  };

  function lerDados(container) {
    const bloco = container.querySelector("script[type='application/json']");
    if (!bloco) return null;
    try {
      return JSON.parse(bloco.textContent);
    } catch (erro) {
      console.error("Gráfico com payload inválido", erro);
      return null;
    }
  }

  function redesenhar(container) {
    const estado = estados.get(container);
    if (!estado) return;
    DESENHOS[estado.tipo](container, estado);
  }

  function observar(container) {
    if (typeof ResizeObserver !== "function") return;
    if (!observador) {
      observador = new ResizeObserver(function (entradas) {
        entradas.forEach(function (entrada) { redesenhar(entrada.target); });
      });
    }
    observador.observe(container);
  }

  function montarUm(container) {
    const tipo = container.dataset.grafico;
    if (!DESENHOS[tipo]) return;

    const bloco = container.querySelector("script[type='application/json']");
    const bruto = bloco ? bloco.textContent : "";
    const anterior = estados.get(container);

    /* Remontar um gráfico cujo payload não mudou apagaria o mês que a
       pessoa abriu e o ano que ela filtrou — e `montar()` varre o
       documento inteiro a cada troca de fragmento. */
    if (anterior && anterior.bruto === bruto) return;

    const dados = lerDados(container);
    if (dados === null) return;

    estados.set(container, {
      tipo: tipo,
      dados: dados,
      bruto: bruto,
      ano: anterior ? anterior.ano : null,
      expandidos: anterior ? anterior.expandidos : {},
    });
    redesenhar(container);
    observar(container);
  }

  function montar(raiz) {
    const alvo = raiz && raiz.querySelectorAll ? raiz : document;
    alvo.querySelectorAll("[data-grafico]").forEach(montarUm);
  }

  window.TNChart = { montar: montar, redesenhar: redesenhar };

  document.addEventListener("DOMContentLoaded", function () { montar(document); });
  /* Cada troca de fragmento pode trazer um gráfico novo — e um payload
     novo para um gráfico que já existia. Remontar é o que garante que o
     desenho acompanhe o dado depois de salvar, filtrar ou trocar de
     semana. */
  document.addEventListener("ajax:success", function () {
    window.setTimeout(function () { montar(document); }, 0);
  });
})();
