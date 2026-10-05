/* ============================================================
   graficos/apoio.js — Apoio dos visuais de calendário, lista e linha

   O que mais de um visual usa e o motor (motor.js) não traz. Nasceu na
   ISSUE-016, que não mexe no motor: tudo aqui é acréscimo.

     - datas: o servidor manda a data em texto ISO (AAAA-MM-DD, como o
       Python a serializa) e "hoje" como dado; nada aqui lê o relógio. O dia é
       um inteiro contado em UTC, para a conta de prazo não sofrer com fuso
       nem com horário de verão. Nomes de mês e de dia da semana saem do Intl,
       na língua do documento (nenhuma tradução no JavaScript).
     - rotulador: texto de interface com padrão em português por visual,
       trocado pelo servidor em `rotulos` (a mesma regra do motor).
     - tom: a classe CSS que dá a uma peça (selo, pílula, chip) a cor de um
       papel (ok, alerta, erro...), com fundo suave e texto escuro.
     - semAcento: texto para busca que ignora maiúscula e acento.
     - formatador: valor em reais (ou número) com a forma completa e a
       compacta ("R$ 44,6 mi"), a partir do `formato` do dado.
     - icone e barraDeBusca: o ícone do Design System e a barra de busca
       (ícone, campo e contagem "visíveis / total") dos visuais de lista.
     - moldura: barra de cima (botões de ano e legenda), tela do SVG e dica,
       a mesma das curvas de periodos.js, para as linhas e as áreas.

   Carrega pelo shell, nunca por fragmento, depois do motor. Ver
   docs/CONTRATO-VISUAL.md.
   ============================================================ */
(function () {
  "use strict";

  const G = window.TN.graficos;

  const DIA_MS = 24 * 60 * 60 * 1000;
  const FORMATO_ISO = /^(\d{4})-(\d{2})-(\d{2})/;
  /* Espaço que a legenda ocupa além do próprio texto: a margem da direita e o
     respiro até os botões de ano (o mesmo de periodos.js). */
  const FOLGA_DA_LEGENDA = 24;
  /* O primeiro de janeiro de 2023 foi um domingo: base para os nomes dos dias
     da semana, sem escrevê-los à mão. */
  const DOMINGO_DE_REFERENCIA = Date.UTC(2023, 0, 1);

  /* ---------- Datas ---------- */

  function lingua() {
    return document.documentElement.lang || "pt-BR";
  }

  const formatadoresDeData = new Map();

  function formatadorDeData(opcoes) {
    const chave = lingua() + JSON.stringify(opcoes);
    if (!formatadoresDeData.has(chave)) {
      formatadoresDeData.set(chave, new Intl.DateTimeFormat(lingua(), Object.assign({ timeZone: "UTC" }, opcoes)));
    }
    return formatadoresDeData.get(chave);
  }

  function maiuscula(texto) {
    return texto.charAt(0).toUpperCase() + texto.slice(1);
  }

  /* Dia inteiro (UTC) de um texto ISO; nulo se não for uma data que existe
     (31/02 volta nulo, não 3 de março). */
  function dia(iso) {
    const partes = typeof iso === "string" ? FORMATO_ISO.exec(iso) : null;
    if (!partes) return null;
    const ano = Number(partes[1]);
    const mes = Number(partes[2]);
    const dd = Number(partes[3]);
    const instante = Date.UTC(ano, mes - 1, dd);
    const conferido = new Date(instante);
    const existe = conferido.getUTCFullYear() === ano && conferido.getUTCMonth() === mes - 1 && conferido.getUTCDate() === dd;
    return existe ? instante / DIA_MS : null;
  }

  /* { ano, mes (1 a 12), dia, semana (0 é domingo) } de um dia inteiro. */
  function partes(dias) {
    const data = new Date(dias * DIA_MS);
    return { ano: data.getUTCFullYear(), mes: data.getUTCMonth() + 1, dia: data.getUTCDate(), semana: data.getUTCDay() };
  }

  function inicioDoMes(ano, mes) {
    return Date.UTC(ano, mes - 1, 1) / DIA_MS;
  }

  function diasNoMes(ano, mes) {
    return new Date(Date.UTC(ano, mes, 0)).getUTCDate();
  }

  /* 02/02/26 */
  function curta(dias) {
    return formatadorDeData({ day: "2-digit", month: "2-digit", year: "2-digit" }).format(dias * DIA_MS);
  }

  /* 02/02/2026 */
  function completa(dias) {
    return formatadorDeData({ day: "2-digit", month: "2-digit", year: "numeric" }).format(dias * DIA_MS);
  }

  /* "Fevereiro" */
  function nomeDoMes(mes) {
    return maiuscula(formatadorDeData({ month: "long" }).format(Date.UTC(2000, mes - 1, 1)));
  }

  /* "Dom", "Seg"... (0 é domingo) */
  function nomeDoDiaDaSemana(indice) {
    const curto = formatadorDeData({ weekday: "short" }).format(DOMINGO_DE_REFERENCIA + indice * DIA_MS);
    return maiuscula(curto.replace(".", ""));
  }

  /* ---------- Rótulos ---------- */

  /* Devolve rotulo(chave): o texto do servidor (`rotulos` no JSON), senão o
     padrão do visual, senão o do motor. */
  function rotulador(dados, padroes) {
    return function (chave) {
      const doServidor = dados && dados.rotulos ? dados.rotulos[chave] : undefined;
      if (doServidor !== undefined) return doServidor;
      return Object.hasOwn(padroes, chave) ? padroes[chave] : G.rotulo(dados, chave);
    };
  }

  /* ---------- Tom ---------- */

  const TONS = ["ok", "alerta", "atencao", "erro", "neutro", "info", "marca", "comprometido", "bege", "vazio"];
  /* Papéis de série do motor que, numa peça de estado, valem um destes tons. */
  const APELIDOS_DE_TOM = {
    previsto: "neutro",
    realizado: "marca",
    tendencia: "atencao",
    "linha-base": "vazio",
    outros: "vazio",
  };

  /* A classe .is-tom-<papel> define --tom, --tom-fundo e --tom-texto no
     graficos.css. Papel desconhecido vira neutro. */
  function tom(papel) {
    const nome = Object.hasOwn(APELIDOS_DE_TOM, papel) ? APELIDOS_DE_TOM[papel] : papel;
    return "is-tom-" + (TONS.includes(nome) ? nome : "neutro");
  }

  /* ---------- Texto ---------- */

  function semAcento(texto) {
    return String(texto)
      .toLowerCase()
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "");
  }

  /* ---------- Valor ---------- */

  /* formato: { divisor (padrão 1: o servidor manda centavos, divisor 100),
     casas (padrão 0), moeda ("BRL"), unidade (sufixo) }. */
  function formatador(formato) {
    const f = formato || {};
    const divisor = Number.isFinite(f.divisor) && f.divisor > 0 ? f.divisor : 1;
    const casas = Number.isInteger(f.casas) ? f.casas : 0;
    const unidade = typeof f.unidade === "string" ? f.unidade : "";
    const base = f.moeda ? { style: "currency", currency: f.moeda } : {};
    const completo = new Intl.NumberFormat(lingua(), Object.assign({ minimumFractionDigits: casas, maximumFractionDigits: casas }, base));
    const compacto = new Intl.NumberFormat(lingua(), Object.assign({ notation: "compact", compactDisplay: "short", maximumFractionDigits: 1 }, base));
    return {
      completo: function (valor) {
        return completo.format(valor / divisor) + unidade;
      },
      compacto: function (valor) {
        return compacto.format(valor / divisor) + unidade;
      },
    };
  }

  /* ---------- Ícone e busca ---------- */

  /* O ícone do Design System (icons.js) num <span>. O texto do SVG é do
     próprio Design System, nunca dado do servidor. */
  function icone(nome, tamanho) {
    const no = G.el("span", { class: "graf-icone", "aria-hidden": "true" });
    if (typeof window.icon === "function") no.innerHTML = window.icon(nome, tamanho);
    return no;
  }

  /* Barra de busca: ícone, campo e a contagem. `aoDigitar` recebe o texto
     sem acento nem maiúscula, o mesmo formato de semAcento. */
  function barraDeBusca(dica, aoDigitar) {
    const campo = G.el("input", {
      type: "search",
      class: "graf-busca__campo",
      placeholder: dica,
      "aria-label": dica,
      autocomplete: "off",
    });
    const contagem = G.el("span", { class: "graf-busca__contagem" });
    campo.addEventListener("input", function () {
      aoDigitar(semAcento(campo.value.trim()));
    });
    return {
      elemento: G.el("div", { class: "graf-busca" }, [icone("search", 14), campo, contagem]),
      campo: campo,
      contar: function (visiveis, total) {
        contagem.textContent = visiveis + " / " + total;
      },
    };
  }

  /* ---------- Moldura dos gráficos de SVG ---------- */

  /* A legenda fica à direita, e os botões de ano no centro, enquanto os dois
     lados cabem; senão a legenda desce para baixo dos botões. Mede-se a
     legenda solta (sem is-estreito), que é quando ela tem o tamanho do texto. */
  function ajustarTopo(quadro) {
    quadro.topo.classList.remove("is-estreito");
    if (!quadro.anos) return;
    const necessario = quadro.anos.elemento.offsetWidth + 2 * (quadro.legenda.offsetWidth + FOLGA_DA_LEGENDA);
    quadro.topo.classList.toggle("is-estreito", quadro.tela.clientWidth < necessario);
  }

  /* Monta a barra de cima (botões de ano, quando há mais de um ano, e a
     legenda), a tela onde o SVG entra e a dica escura. opcoes:
       dados, anos (lista), aoEscolherAno(ano), itensLegenda, classeDica,
       soBarras (a legenda mostra só a amostra de barra, sem a de linha) */
  function moldura(host, opcoes) {
    const anos = opcoes.anos.length > 1 ? G.criarAnos(opcoes.anos, opcoes.dados, opcoes.aoEscolherAno) : null;
    const legenda = G.criarLegenda(opcoes.itensLegenda);
    if (opcoes.soBarras) {
      legenda.querySelectorAll(".graf__leg-linha").forEach(function (amostra) {
        amostra.remove();
      });
    }
    const topo = G.el(
      "div",
      { class: "graf__topo" + (anos ? "" : " graf__topo--sem-anos") },
      anos ? [anos.elemento, legenda] : [legenda],
    );
    const tela = G.el("div", { class: "graf__tela" });
    host.replaceChildren(topo, tela);
    const pronta = { topo: topo, legenda: legenda, tela: tela, anos: anos, dica: G.criarDica(tela, opcoes.classeDica) };
    pronta.ajustar = function () {
      ajustarTopo(pronta);
    };
    return pronta;
  }

  /* Troca o SVG da tela pelo novo, sempre como primeiro filho (a dica fica
     por cima). */
  function substituirSvg(tela, novo) {
    const anterior = tela.querySelector(":scope > svg");
    if (anterior) anterior.remove();
    tela.insertBefore(novo, tela.firstChild);
  }

  G.apoio = {
    datas: {
      DIA_MS: DIA_MS,
      dia: dia,
      partes: partes,
      inicioDoMes: inicioDoMes,
      diasNoMes: diasNoMes,
      curta: curta,
      completa: completa,
      nomeDoMes: nomeDoMes,
      nomeDoDiaDaSemana: nomeDoDiaDaSemana,
    },
    rotulador: rotulador,
    tom: tom,
    semAcento: semAcento,
    formatador: formatador,
    icone: icone,
    barraDeBusca: barraDeBusca,
    moldura: moldura,
    substituirSvg: substituirSvg,
  };
})();
