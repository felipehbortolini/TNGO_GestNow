#!/usr/bin/env node
/* global document, getComputedStyle, window */
/**
 * acessibilidade.mjs — a auditoria de acessibilidade das telas (ISSUE-091).
 *
 * Segue docs/ACESSIBILIDADE.md: axe-core na versão fixada do Padrão (4.13.0),
 * com as regras wcag2a, wcag2aa, wcag21a, wcag21aa e best-practice, em cada
 * tela da lista de navegação (api/src/core/navegacao.json), mais a passada de
 * teclado com Tab real medindo o estilo computado de cada parada.
 *
 * Os perfis são os mesmos da varredura de telas (ISSUE-090): Admin em todas as
 * telas e Fornecedor nas da Programação Semanal, que é tudo o que o vínculo
 * dele alcança (api/src/core/rbac.py); nas demais ele só veria o acesso negado.
 *
 * Larguras: 1280px em todas as telas e 760px (trilho) numa segunda passada. O
 * teclado roda em 1280px, como a medição registrada no Padrão:
 *
 *   (a) violação do axe        — qualquer nó reprovado nas regras do Padrão;
 *   (b) teclado                — o skip link tem que ser a primeira parada do
 *                                Tab, cada parada precisa de nome acessível e
 *                                de anel de foco computado casando
 *                                `:focus-visible`.
 *
 *   node scripts/acessibilidade.mjs [--base http://localhost:4280]
 *                                   [--telas inicio/home,riscos/registro]
 *                                   [--perfil admin]
 *
 * A base também vem da variável GESTNOW_BASE, no mesmo padrão da varredura.
 * O app precisa estar no ar. Sai com código 1 se houver qualquer violação ou
 * falha de teclado e imprime a tabela-resumo no fim.
 */

import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const RAIZ_DO_PRODUTO = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const NAVEGACAO = join(RAIZ_DO_PRODUTO, "api", "src", "core", "navegacao.json");
const AXE = join(RAIZ_DO_PRODUTO, "node_modules", "axe-core");
const VERSAO_DO_AXE = JSON.parse(readFileSync(join(AXE, "package.json"), "utf8")).version;
const AXE_MIN = readFileSync(join(AXE, "axe.min.js"), "utf8");

const BASE_PADRAO = "http://localhost:4280";
const LARGURAS_PADRAO = [1280, 760];
const LARGURA_DO_TECLADO = 1280;
const ALTURA = 900;
const REGRAS_AXE = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"];

// Teto de segurança da passada de teclado: a página termina o Tab quando o
// foco sai dela (activeElement volta ao body); o teto só evita laço infinito.
const LIMITE_DE_PARADAS = 500;

// O rodapé do seletor de perfil da demonstração separa nome, perfil e vínculo
// com "·": "Leonardo Gomes · Admin · Timenow".
const SEPARADOR_DO_SELETOR = "·";

const PERFIS_PADRAO = [
  { chave: "admin", casa: (opcao) => opcao.perfil === "Admin" },
  { chave: "fornecedor", casa: (opcao) => opcao.vinculo === "Fornecedor" },
];

// ── Opções e lista de telas ────────────────────────────────────────────

function lerOpcoes(argumentos) {
  const opcoes = {
    base: (process.env.GESTNOW_BASE || BASE_PADRAO).replace(/\/+$/, ""),
    telas: null,
    perfis: PERFIS_PADRAO.map((perfil) => perfil.chave),
  };
  for (let i = 0; i < argumentos.length; i += 1) {
    const chave = argumentos[i];
    const valor = argumentos[i + 1];
    if (chave === "--base" && valor) {
      opcoes.base = valor.replace(/\/+$/, "");
      i += 1;
    } else if (chave === "--telas" && valor) {
      opcoes.telas = valor.split(",").map((item) => item.trim()).filter(Boolean);
      i += 1;
    } else if (chave === "--perfil" && valor) {
      opcoes.perfis = [valor.trim()];
      i += 1;
    }
  }
  return opcoes;
}

const slug = (identificador) => identificador.replaceAll("_", "-");

function caminhoPublico(modulo, id) {
  if (modulo === "inicio" && id === "home") return "/";
  return `/${slug(modulo)}/${slug(id)}`;
}

function lerTelas() {
  const lista = JSON.parse(readFileSync(NAVEGACAO, "utf8"));
  const telas = [];
  for (const modulo of lista.modulos ?? []) {
    for (const tela of modulo.telas ?? []) {
      const pasta = tela.modulo ?? modulo.id;
      telas.push({
        chave: `${pasta}/${tela.id}`,
        pasta,
        id: tela.id,
        titulo: tela.titulo,
        caminho: caminhoPublico(pasta, tela.id),
      });
    }
  }
  return telas;
}

// `--telas` aceita a chave (modulo/tela) ou o módulo inteiro (ex.: riscos).
function filtrarTelas(telas, pedidas) {
  if (pedidas === null) return telas;
  return telas.filter((tela) => pedidas.includes(tela.chave) || pedidas.includes(tela.pasta));
}

// O fornecedor só alcança a Programação Semanal (rbac.py): as outras telas ele
// só veria o acesso negado, que não é o assunto desta auditoria.
function alcancaveisPeloPerfil(tela, chave) {
  if (chave === "fornecedor") return tela.pasta === "programacao_semanal";
  return true;
}

// ── Navegador ──────────────────────────────────────────────────────────

async function esperarShell(pagina) {
  await pagina.waitForFunction(
    () => {
      const shell = document.getElementById("app-shell");
      const barra = document.getElementById("main-nav");
      const pronta = shell && !shell.querySelector(".page-loading");
      const visivel = barra && barra.style.display !== "none";
      return Boolean(pronta && visivel);
    },
    null,
    { timeout: 30000 }
  );
}

async function descobrirColaborador(pagina, perfil) {
  const opcoes = await pagina.$$eval(
    "#perfil-seletor option",
    (itens, separador) =>
      itens.map((item) => {
        const partes = item.textContent.split(separador).map((parte) => parte.trim());
        return { valor: item.value, perfil: partes[1] ?? "", vinculo: partes[2] ?? "" };
      }),
    SEPARADOR_DO_SELETOR
  );
  const escolhida = opcoes.find(perfil.casa);
  return escolhida ? escolhida.valor : null;
}

async function iniciarSessao(janela, pagina, opcoes, perfil) {
  await pagina.goto(`${opcoes.base}/?projeto=portfolio`, { waitUntil: "domcontentloaded" });
  await esperarShell(pagina);
  const colaborador = await descobrirColaborador(pagina, perfil);
  if (colaborador === null) {
    throw new Error(`o seletor da barra lateral não tem o perfil ${perfil.chave}`);
  }
  const resposta = await janela.request.post(`${opcoes.base}/api/demonstracao/perfil`, {
    form: { colaborador },
    headers: { "X-Alpine-Request": "true" },
  });
  if (!resposta.ok()) {
    throw new Error(`o servidor recusou a troca para ${perfil.chave} (HTTP ${resposta.status()})`);
  }
  await resposta.dispose();
}

// ── axe-core ───────────────────────────────────────────────────────────

async function rodarAxe(pagina) {
  await pagina.addScriptTag({ content: AXE_MIN });
  return pagina.evaluate(async (regras) => {
    const resultado = await window.axe.run(document, {
      runOnly: { type: "tag", values: regras },
      resultTypes: ["violations"],
    });
    return resultado.violations.map((violacao) => ({
      regra: violacao.id,
      impacto: violacao.impact ?? "sem impacto declarado",
      ajuda: violacao.help,
      nos: violacao.nodes.map((no) => ({
        alvo: no.target.join(" "),
        resumo: (no.failureSummary ?? "").replace(/\s+/g, " ").trim(),
      })),
    }));
  }, REGRAS_AXE);
}

// ── Teclado ────────────────────────────────────────────────────────────
//
// Tab de verdade (evento de teclado, não .focus() programático). Antes de
// começar, o foco volta ao body: o shell foca a área de conteúdo após a
// navegação e, sem esse reset, o primeiro Tab cairia no meio da página.
// As transições e animações são neutralizadas porque, congeladas, o estilo
// computado fica no estado de repouso (o aviso está em docs/ACESSIBILIDADE.md).

async function medirParada(pagina) {
  return pagina.evaluate(() => {
    const ativo = document.activeElement;
    if (!ativo || ativo === document.body || ativo === document.documentElement) {
      return { fim: true };
    }

    /* Sombra que desenha algo: nem transparente nem de tamanho zero. Uma
       `rgba(0, 0, 0, 0) 0px 0px 0px 0px` passa no teste ingênuo e não pinta. */
    function desenhaParteDaSombra(parte) {
      const trecho = parte.trim();
      if (/rgba\([^)]*,\s*0\)/.test(trecho)) return false;
      return !/^(rgb\([^)]+\)|#[0-9a-f]{3,8})\s+0(px)?\s+0(px)?\s+0(px)?\s+0(px)?$/i.test(trecho);
    }

    function sombraDesenha(sombra) {
      if (!sombra || sombra === "none") return false;
      return sombra.split(/,(?![^(]*\))/).some(desenhaParteDaSombra);
    }

    function texto(elemento) {
      return (elemento ? elemento.textContent : "").trim().replace(/\s+/g, " ");
    }

    function rotuloExterno(elemento) {
      if (!elemento.id) return "";
      return texto(document.querySelector(`label[for="${elemento.id}"]`));
    }

    function rotuloPorLabelledBy(elemento) {
      const ids = (elemento.getAttribute("aria-labelledby") ?? "").split(/\s+/).filter(Boolean);
      return ids.map((id) => texto(document.getElementById(id))).join(" ").trim();
    }

    /* O nome sai da mesma ordem que o leitor de tela resolve: rótulo direto,
       aria-labelledby, <label for>, label envolvente, título, alt, valor e
       conteúdo. Sem isto o campo com <label class="sr-only" for> seria acusado
       sem razão. */
    function nomeAcessivel(elemento) {
      const candidatos = [
        elemento.getAttribute("aria-label") ?? "",
        rotuloPorLabelledBy(elemento),
        rotuloExterno(elemento),
        texto(elemento.closest("label")),
        elemento.getAttribute("title") ?? "",
        elemento.getAttribute("alt") ?? "",
        typeof elemento.value === "string" ? elemento.value : "",
        texto(elemento).slice(0, 80),
      ];
      const achado = candidatos.map((item) => String(item ?? "").trim()).find((item) => item !== "");
      return achado ?? "";
    }

    function contornoDesenha(estilo) {
      if (estilo.outlineStyle === "none") return false;
      if (Number.parseFloat(estilo.outlineWidth) <= 0) return false;
      return estilo.outlineColor !== "rgba(0, 0, 0, 0)" && estilo.outlineColor !== "transparent";
    }

    const estilo = getComputedStyle(ativo);
    const caixa = ativo.getBoundingClientRect();
    const id = ativo.id ? `#${ativo.id}` : "";
    const classe = ativo.classList.length > 0 ? `.${ativo.classList[0]}` : "";
    const visivelNaTela =
      caixa.width > 0 && caixa.height > 0 && caixa.top >= 0 && caixa.left >= 0;
    return {
      fim: false,
      descricao: `${ativo.tagName.toLowerCase()}${id}${classe}`,
      nome: nomeAcessivel(ativo),
      casouFocusVisible: ativo.matches(":focus-visible"),
      anel: contornoDesenha(estilo) || sombraDesenha(estilo.boxShadow),
      skip: ativo.classList.contains("skip-link"),
      visivel: visivelNaTela,
    };
  });
}

async function medirTeclado(contexto, tela) {
  const { pagina, perfil, largura } = contexto;
  const base = { perfil, largura, tela, categoria: "teclado" };
  await pagina.addStyleTag({
    content: "* { transition: none !important; animation: none !important; }",
  });
  await pagina.evaluate(() => {
    /* Focar o body (com tabindex -1, que não vira parada) devolve o ponto de
       partida do Tab ao início do documento. Só blur() não basta: o Chromium
       continua a navegação sequencial a partir do elemento que perdeu o foco,
       e a primeira parada cairia no meio do conteúdo. */
    document.body.setAttribute("tabindex", "-1");
    document.body.focus();
    window.scrollTo(0, 0);
  });
  const falhas = [];
  let paradas = 0;
  for (let indice = 1; indice <= LIMITE_DE_PARADAS; indice += 1) {
    await pagina.keyboard.press("Tab");
    const parada = await medirParada(pagina);
    if (parada.fim) break;
    paradas += 1;
    if (indice === 1 && !parada.skip) {
      falhas.push(
        falhaDe({ ...base, detalhe: `a primeira parada do Tab não é o skip link (foi ${parada.descricao})` })
      );
    }
    if (parada.skip && !parada.visivel) {
      falhas.push(falhaDe({ ...base, detalhe: "o skip link recebeu foco mas não está visível na tela" }));
    }
    if (parada.nome === "") {
      falhas.push(falhaDe({ ...base, detalhe: `parada ${indice}: ${parada.descricao} sem nome acessível` }));
    }
    if (!parada.casouFocusVisible) {
      falhas.push(
        falhaDe({ ...base, detalhe: `parada ${indice}: ${parada.descricao} não casa :focus-visible` })
      );
    }
    if (!parada.anel) {
      falhas.push(
        falhaDe({ ...base, detalhe: `parada ${indice}: ${parada.descricao} sem anel de foco computado` })
      );
    }
  }
  return { falhas, paradas };
}

// ── Conferências ───────────────────────────────────────────────────────

const falhaDe = ({ perfil, largura, tela, categoria, detalhe, regra, impacto }) => ({
  perfil: perfil.chave,
  largura,
  tela: tela.chave,
  categoria,
  detalhe,
  regra: regra ?? null,
  impacto: impacto ?? null,
});

function falhasDaViolacao(violacao, perfil, largura, tela) {
  return violacao.nos.map((no) =>
    falhaDe({
      perfil,
      largura,
      tela,
      categoria: "violacao",
      regra: violacao.regra,
      impacto: violacao.impacto,
      detalhe: `${violacao.regra} (${violacao.impacto}) — ${violacao.ajuda}; alvo: ${no.alvo}; ${no.resumo}`,
    })
  );
}

// ── A auditoria ────────────────────────────────────────────────────────

async function visitarTela(contexto, tela) {
  const { pagina, opcoes, perfil, largura, caixa } = contexto;
  caixa.erros.length = 0;
  try {
    await pagina.goto(`${opcoes.base}${tela.caminho}?projeto=portfolio`, {
      waitUntil: "domcontentloaded",
      timeout: 30000,
    });
    await esperarShell(pagina);
    await pagina.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
    await pagina.waitForTimeout(300);
  } catch (erro) {
    return {
      falhas: [
        falhaDe({
          perfil,
          largura,
          tela,
          categoria: "abertura",
          detalhe: `a tela não abriu: ${erro.message.split("\n")[0]}`,
        }),
      ],
      violacoes: 0,
      paradas: 0,
    };
  }
  const violacoes = await rodarAxe(pagina);
  const falhas = violacoes.flatMap((violacao) => falhasDaViolacao(violacao, perfil, largura, tela));
  let resultadoTeclado = { falhas: [], paradas: 0 };
  if (largura === LARGURA_DO_TECLADO) {
    resultadoTeclado = await medirTeclado(contexto, tela);
  }
  const erros = [...caixa.erros].map((texto) =>
    falhaDe({ perfil, largura, tela, categoria: "console", detalhe: texto })
  );
  return {
    falhas: [...falhas, ...resultadoTeclado.falhas, ...erros],
    violacoes: violacoes.length,
    paradas: resultadoTeclado.paradas,
  };
}

async function varrerCombinacao(navegador, programa, perfil, largura) {
  const janela = await navegador.newContext({ viewport: { width: largura, height: ALTURA } });
  const pagina = await janela.newPage();
  const caixa = { erros: [] };
  pagina.on("console", (mensagem) => {
    if (mensagem.type() === "error") caixa.erros.push(`console: ${mensagem.text()}`);
  });
  pagina.on("pageerror", (erro) => caixa.erros.push(`pageerror: ${erro.message}`));
  const telas = programa.telasPorPerfil.get(perfil.chave) ?? [];
  const resultado = { perfil: perfil.chave, largura, total: 0, violacoes: 0, paradas: 0, falhas: [] };
  try {
    await iniciarSessao(janela, pagina, programa, perfil);
    const contexto = { pagina, caixa, opcoes: programa, perfil, largura };
    for (const tela of telas) {
      const visita = await visitarTela(contexto, tela);
      resultado.total += 1;
      resultado.violacoes += visita.violacoes;
      resultado.paradas += visita.paradas;
      resultado.falhas.push(...visita.falhas);
    }
  } catch (erro) {
    resultado.falhas.push({
      perfil: perfil.chave,
      largura,
      tela: "(sessão)",
      categoria: "sessao",
      detalhe: erro.message,
      regra: null,
      impacto: null,
    });
  } finally {
    await janela.close();
  }
  return resultado;
}

// ── Relatório ──────────────────────────────────────────────────────────

const CATEGORIAS = ["violacao", "teclado", "abertura", "console", "sessao"];

function resumirRegras(falhas) {
  const porRegra = new Map();
  for (const falha of falhas) {
    if (falha.regra === null) continue;
    const atual = porRegra.get(falha.regra) ?? { impacto: falha.impacto, quantidade: 0, telas: new Set() };
    atual.quantidade += 1;
    atual.telas.add(`${falha.perfil} ${falha.largura}px ${falha.tela}`);
    porRegra.set(falha.regra, atual);
  }
  return [...porRegra.entries()].sort((a, b) => b[1].quantidade - a[1].quantidade);
}

function imprimirRelatorio(resultados, opcoes, segundos) {
  console.log("");
  console.log(`Auditoria de acessibilidade — ${opcoes.base}`);
  console.log(`axe-core ${VERSAO_DO_AXE} · regras: ${REGRAS_AXE.join(", ")}`);
  console.log(
    `Larguras: ${opcoes.larguras.join(", ")} px · Teclado: ${LARGURA_DO_TECLADO}px · ` +
      `Perfis: ${opcoes.perfis.join(", ")}`
  );
  console.log("─".repeat(72));
  const geral = { total: 0, violacoes: 0, paradas: 0 };
  const porCategoria = new Map(CATEGORIAS.map((categoria) => [categoria, 0]));
  const falhas = [];
  for (const resultado of resultados) {
    geral.total += resultado.total;
    geral.violacoes += resultado.violacoes;
    geral.paradas += resultado.paradas;
    for (const falha of resultado.falhas) {
      porCategoria.set(falha.categoria, (porCategoria.get(falha.categoria) ?? 0) + 1);
      falhas.push(falha);
    }
    const marca =
      resultado.falhas.length === 0 ? "ok" : `${resultado.falhas.length} falha(s)`;
    console.log(
      `${resultado.perfil.padEnd(14)} ${String(resultado.largura).padStart(5)}px  ` +
        `${String(resultado.total).padStart(3)} telas · ${String(resultado.violacoes).padStart(3)} regras do axe ` +
        `· ${String(resultado.paradas).padStart(4)} paradas de Tab · ${marca}`
    );
  }
  console.log("─".repeat(72));
  const categorias = [...porCategoria.entries()].filter(([, quantidade]) => quantidade > 0);
  if (categorias.length === 0) {
    console.log(
      `Tudo certo: ${geral.total} telas auditadas, ${geral.violacoes} regras do axe violadas, ` +
        `${geral.paradas} paradas de Tab aprovadas.`
    );
  } else {
    for (const [categoria, quantidade] of categorias) {
      console.log(`${categoria}: ${quantidade}`);
    }
    const regras = resumirRegras(falhas);
    if (regras.length > 0) {
      console.log("─".repeat(72));
      console.log("violações por regra:");
      for (const [regra, dados] of regras) {
        console.log(
          `  ${regra} (${dados.impacto}): ${dados.quantidade} nó(s) em ${dados.telas.size} tela(s)/combinação(ões)`
        );
      }
    }
    console.log("─".repeat(72));
    for (const falha of falhas) {
      console.log(`FALHA [${falha.categoria}] ${falha.perfil} ${falha.largura}px ${falha.tela}: ${falha.detalhe}`);
    }
  }
  console.log(`Duração: ${segundos.toFixed(1)}s`);
  return falhas.length;
}

// ── Rodando ────────────────────────────────────────────────────────────

async function principal() {
  const opcoes = lerOpcoes(process.argv.slice(2));
  opcoes.larguras = LARGURAS_PADRAO;
  const perfis = PERFIS_PADRAO.filter((perfil) => opcoes.perfis.includes(perfil.chave));
  if (perfis.length === 0) {
    console.error("acessibilidade: nenhum perfil conhecido em --perfil (admin, fornecedor).");
    process.exit(2);
  }
  const telas = filtrarTelas(lerTelas(), opcoes.telas);
  opcoes.telasPorPerfil = new Map();
  for (const perfil of perfis) {
    opcoes.telasPorPerfil.set(
      perfil.chave,
      telas.filter((tela) => alcancaveisPeloPerfil(tela, perfil.chave))
    );
  }
  const totalDeTelas = [...opcoes.telasPorPerfil.values()].reduce((soma, lista) => soma + lista.length, 0);
  if (totalDeTelas === 0) {
    console.error("acessibilidade: nenhuma tela da lista de navegação casa com --telas/--perfil.");
    process.exit(2);
  }
  console.log(
    `Auditoria de acessibilidade: axe-core ${VERSAO_DO_AXE} · ${totalDeTelas} telas × ` +
      `${opcoes.larguras.length} larguras · perfis ${perfis.map((perfil) => perfil.chave).join(", ")}`
  );
  const navegador = await chromium.launch();
  const inicio = Date.now();
  const resultados = [];
  try {
    for (const perfil of perfis) {
      for (const largura of opcoes.larguras) {
        process.stdout.write(`${perfil.chave} ${largura}px… `);
        const resultado = await varrerCombinacao(navegador, opcoes, perfil, largura);
        resultados.push(resultado);
        console.log(resultado.falhas.length === 0 ? "ok" : `reprovou (${resultado.falhas.length})`);
      }
    }
  } finally {
    await navegador.close();
  }
  const reprovadas = imprimirRelatorio(resultados, opcoes, (Date.now() - inicio) / 1000);
  process.exit(reprovadas === 0 ? 0 : 1);
}

await principal();
