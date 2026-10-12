#!/usr/bin/env node
/* global document, getComputedStyle */
/**
 * varredura-telas.mjs — a varredura de telas nas três larguras e nos três perfis (ISSUE-090).
 *
 * Precedente: o `_dev/crawl.py` do protótipo (docs/referencia/prototipo/). Abre
 * cada tela da lista de navegação (api/src/core/navegacao.json) em 1280, 1100 e
 * 760 px, com os perfis Admin, Visualizador e Fornecedor, e reprova:
 *
 *   (a) console com erro            — console.error ou exceção da página;
 *   (b) rolagem horizontal          — a largura do documento passa da janela;
 *   (c) barra lateral ausente       — em 1280 é a barra cheia; em 1100 e 760 é o
 *                                     trilho de 64px; ela nunca some;
 *   (d) tela sem estilo próprio     — a classe raiz `.pagina--<modulo>-<tela>`
 *                                     aplicada e o CSS da página carregado;
 *   (e) link quebrado               — `a[href]` de mesma origem responde < 400 e
 *                                     `data-tn-tela` aponta para tela conhecida.
 *
 * O fornecedor só alcança a Programação Semanal e o Visualizador não alcança
 * Configurações, como o servidor decide (api/src/core/rbac.py): para eles,
 * essas telas precisam mostrar o acesso negado (navegar por elas não é falha;
 * mostrar a tela proibida é). O Início nunca entrega o fornecedor na negativa:
 * o servidor o leva à primeira tela que ele alcança (navigation_view._position).
 *
 *   node scripts/varredura-telas.mjs [--base http://localhost:4280]
 *                                    [--perfis admin,visualizador,fornecedor]
 *                                    [--larguras 1280,1100,760]
 *
 * A base também vem da variável GESTNOW_BASE. O app precisa estar no ar com a
 * API (host do Functions + proxy, ou o `run.bat`). Sai com código 1 se houver
 * qualquer reprovação e imprime a tabela-resumo no fim.
 */

import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const RAIZ_DO_PRODUTO = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const NAVEGACAO = join(RAIZ_DO_PRODUTO, "api", "src", "core", "navegacao.json");

const BASE_PADRAO = "http://localhost:4280";
const LARGURAS_PADRAO = [1280, 1100, 760];
const ALTURA = 900;
const LARGURA_TRILHO = 1100;

// O rodapé do seletor de perfil da demonstração separa nome, perfil e vínculo
// com "·": "Leonardo Gomes · Admin · Timenow".
const SEPARADOR_DO_SELETOR = "·";

const PERFIS_PADRAO = [
  { chave: "admin", titulo: "Admin", casa: (opcao) => opcao.perfil === "Admin" },
  {
    chave: "visualizador",
    titulo: "Visualizador",
    casa: (opcao) => opcao.perfil === "Visualizador",
  },
  { chave: "fornecedor", titulo: "Fornecedor", casa: (opcao) => opcao.vinculo === "Fornecedor" },
];

// ── Opções e lista de telas ────────────────────────────────────────────

function lerOpcoes(argumentos) {
  const opcoes = {
    base: (process.env.GESTNOW_BASE || BASE_PADRAO).replace(/\/+$/, ""),
    perfis: PERFIS_PADRAO,
    larguras: LARGURAS_PADRAO,
  };
  for (let i = 0; i < argumentos.length; i += 1) {
    const chave = argumentos[i];
    const valor = argumentos[i + 1];
    if (chave === "--base" && valor) {
      opcoes.base = valor.replace(/\/+$/, "");
      i += 1;
    } else if (chave === "--perfis" && valor) {
      const pedidas = valor.split(",").map((item) => item.trim());
      opcoes.perfis = PERFIS_PADRAO.filter((perfil) => pedidas.includes(perfil.chave));
      i += 1;
    } else if (chave === "--larguras" && valor) {
      opcoes.larguras = valor.split(",").map((item) => Number.parseInt(item, 10));
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
        classe: `pagina--${pasta}-${tela.id}`,
        detalhe: Boolean(tela.detalhe_de),
      });
    }
  }
  return telas;
}

// A tela que o endereço abre, como o screen_for_path do servidor: "/" é o
// Início; as demais trocam "-" por "_" e procuram a chave na lista.
function telaDoCaminho(telas, caminho) {
  const limpo = (caminho.split("?")[0].split("#")[0] || "").toLowerCase().replace(/\/$/, "");
  if (["", "/", "/index.html", "/inicio"].includes(limpo)) {
    return telas.find((tela) => tela.chave === "inicio/home") ?? null;
  }
  const partes = limpo.split("/").filter(Boolean);
  if (partes.length !== 2) return null;
  const chave = partes.map((parte) => parte.replaceAll("-", "_")).join("/");
  return telas.find((tela) => tela.chave === chave) ?? null;
}

// O que cada perfil alcança, como o servidor decide (api/src/core/rbac.py): o
// fornecedor só a Programação Semanal (D7) e o Visualizador não alcança
// Configurações, que exige "configurar" (Gestor ou Admin, HU-007).
function perfilAlcanca(perfil, tela) {
  if (perfil.chave === "fornecedor") return tela.pasta === "programacao_semanal";
  if (perfil.chave === "visualizador") return tela.pasta !== "configuracoes";
  return true;
}

const esperaAcessoNegado = (perfil, tela) => !perfilAlcanca(perfil, tela);

// A primeira tela que o fornecedor alcança: onde o servidor entrega o Início
// dele (navigation_view._position). Preenchida em principal(), com a lista.
let entradaDoFornecedor = null;

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

// O que a página conta de si mesma, já resolvido (sem depender do Node).
async function lerFatos(pagina, tela) {
  return pagina.evaluate((dados) => {
    function classesDe(elemento) {
      return elemento ? elemento.className.split(/\s+/).filter(Boolean) : [];
    }

    function medirFolhaDaPagina() {
      const url = `/paginas/${dados.pasta}/${dados.id}.css`;
      const folha = [...document.styleSheets].find((item) => (item.href || "").endsWith(url));
      return { presente: Boolean(folha) };
    }

    function medirRolagem() {
      const raiz = document.documentElement;
      const excesso = raiz.scrollWidth - raiz.clientWidth;
      let pior = null;
      if (excesso <= 1) return { excesso, pior };
      for (const elemento of document.querySelectorAll("body *")) {
        const caixa = elemento.getBoundingClientRect();
        const estouro = Math.round(caixa.right - raiz.clientWidth);
        if (caixa.width > 0 && estouro > 2 && (pior === null || estouro > pior.estouro)) {
          const id = elemento.id ? `#${elemento.id}` : "";
          const classe = elemento.classList[0] ? `.${elemento.classList[0]}` : "";
          pior = { estouro, seletor: `${elemento.tagName.toLowerCase()}${id}${classe}` };
        }
      }
      return { excesso, pior };
    }

    function medirBarra() {
      const barra = document.getElementById("main-nav");
      if (!barra) return { visivel: false, largura: 0 };
      const estilo = getComputedStyle(barra);
      const caixa = barra.getBoundingClientRect();
      const visivel =
        estilo.display !== "none" &&
        estilo.visibility !== "hidden" &&
        caixa.width > 0 &&
        caixa.height > 0;
      return { visivel, largura: Math.round(caixa.width) };
    }

    const shell = document.getElementById("app-shell");
    const folha = medirFolhaDaPagina();
    const rolagem = medirRolagem();
    const barra = medirBarra();
    const guardaTitulo = shell?.querySelector(".guard h1")?.textContent?.trim() ?? "";
    return {
      classeRaiz: classesDe(shell),
      guarda: guardaTitulo !== "",
      guardaTitulo,
      dsCarregado: getComputedStyle(document.documentElement)
        .getPropertyValue("--ds-carregado")
        .trim(),
      folhaDaPagina: folha.presente,
      trilho: document.documentElement.classList.contains("sidebar-trilho"),
      barraVisivel: barra.visivel,
      barraLargura: barra.largura,
      excesso: rolagem.excesso,
      pior: rolagem.pior,
      links: [...document.querySelectorAll("a[href]")].map((link) => ({
        href: link.getAttribute("href"),
        tela: link.hasAttribute("data-tn-tela"),
      })),
    };
  }, { pasta: tela.pasta, id: tela.id });
}

// ── Conferências ───────────────────────────────────────────────────────

const falhaDe = ({ perfil, largura, tela, categoria, detalhe }) => ({
  perfil: perfil.chave,
  largura,
  tela: tela.chave,
  categoria,
  detalhe,
});

/* O servidor nunca deixa o fornecedor numa negativa no Início: o endereço o
   entrega na primeira tela que ele alcança (navigation_view._position). */
function entregouNaEntrada(fatos, perfil, tela) {
  if (perfil.chave !== "fornecedor" || tela.chave !== "inicio/home") return false;
  return entradaDoFornecedor !== null && fatos.classeRaiz.includes(entradaDoFornecedor.classe);
}

function conferirConteudo(fatos, perfil, largura, tela) {
  if (esperaAcessoNegado(perfil, tela)) {
    if (fatos.guarda && fatos.guardaTitulo.startsWith("Acesso negado")) return [];
    if (entregouNaEntrada(fatos, perfil, tela)) return [];
    const visto = fatos.guardaTitulo || fatos.classeRaiz.join(" ");
    return [
      falhaDe({
        perfil,
        largura,
        tela,
        categoria: "permissao",
        detalhe: `o perfil ${perfil.chave} alcançou o que não pode (mostrou: ${visto})`,
      }),
    ];
  }
  const falhas = [];
  const base = { perfil, largura, tela, categoria: "estilo" };
  if (fatos.guarda) {
    const guarda = fatos.guardaTitulo || "sem título";
    falhas.push(
      falhaDe({ ...base, categoria: "conteudo", detalhe: `a tela não abriu; mostrou a guarda «${guarda}»` })
    );
  }
  if (!fatos.classeRaiz.includes(tela.classe)) {
    falhas.push(falhaDe({ ...base, detalhe: `raiz sem a classe ${tela.classe}` }));
  }
  if (!fatos.folhaDaPagina) {
    falhas.push(falhaDe({ ...base, detalhe: `CSS da página não carregado (/paginas/${tela.chave}.css)` }));
  }
  if (!fatos.dsCarregado) {
    falhas.push(falhaDe({ ...base, detalhe: "Design System não carregou (sentinela --ds-carregado)" }));
  }
  return falhas;
}

function conferirBarra(fatos, perfil, largura, tela) {
  const base = { perfil, largura, tela, categoria: "barra" };
  if (!fatos.barraVisivel) {
    return [falhaDe({ ...base, detalhe: "barra lateral ausente ou oculta" })];
  }
  const vista = fatos.trilho ? `trilho de ${fatos.barraLargura}px` : `barra de ${fatos.barraLargura}px`;
  if (largura <= LARGURA_TRILHO && (!fatos.trilho || fatos.barraLargura > 100)) {
    return [falhaDe({ ...base, detalhe: `em ${largura}px esperava o trilho; veio ${vista}` })];
  }
  if (largura > LARGURA_TRILHO && (fatos.trilho || fatos.barraLargura < 200)) {
    return [falhaDe({ ...base, detalhe: `em ${largura}px esperava a barra cheia; veio ${vista}` })];
  }
  return [];
}

function conferirRolagem(fatos, perfil, largura, tela) {
  if (fatos.excesso <= 1) return [];
  const culpado = fatos.pior ? `; maior estouro: ${fatos.pior.seletor} (+${fatos.pior.estouro}px)` : "";
  return [
    falhaDe({
      perfil,
      largura,
      tela,
      categoria: "rolagem",
      detalhe: `rolagem horizontal de ${fatos.excesso}px${culpado}`,
    }),
  ];
}

// Um link já visto na mesma varredura não é buscado de novo (cache por perfil).
async function conferirLink(link, contexto, cache) {
  const { perfil, largura, tela, requisicoes } = contexto;
  const base = { perfil, largura, tela, categoria: "link" };
  if (link.tela) {
    const alvo = telaDoCaminho(requisicoes.telas, new URL(link.url).pathname);
    if (alvo === null) {
      return [
        falhaDe({ ...base, detalhe: `data-tn-tela aponta para tela desconhecida: ${link.url}` }),
      ];
    }
  }
  if (!cache.has(link.url)) {
    cache.set(link.url, await medirResposta(link.url, requisicoes.fetch));
  }
  const status = cache.get(link.url);
  if (status === 0) return [falhaDe({ ...base, detalhe: `link não respondeu: ${link.url}` })];
  if (status >= 400) return [falhaDe({ ...base, detalhe: `link quebrado: ${link.url} (HTTP ${status})` })];
  return [];
}

async function medirResposta(url, buscar) {
  try {
    const resposta = await buscar(url, {
      method: "GET",
      maxRedirects: 0,
      failOnStatusCode: false,
      timeout: 20000,
    });
    const status = resposta.status();
    await resposta.dispose();
    return status;
  } catch {
    return 0;
  }
}

function linksDaTela(fatos, origem) {
  const urls = new Map();
  for (const link of fatos.links) {
    const bruto = link.href ?? "";
    if (bruto === "" || bruto.startsWith("#") || bruto.startsWith("javascript:")) continue;
    let url;
    try {
      url = new URL(bruto, `${origem}/`);
    } catch {
      continue;
    }
    if (url.origin !== new URL(origem).origin) continue;
    if (!urls.has(url.href)) urls.set(url.href, { url: url.href, tela: link.tela });
  }
  return [...urls.values()];
}

async function conferirLinks(contexto, fatos) {
  const falhas = [];
  for (const link of linksDaTela(fatos, contexto.requisicoes.base)) {
    const problemas = await conferirLink(link, contexto, contexto.cache);
    falhas.push(...problemas);
  }
  return falhas;
}

// ── A varredura ────────────────────────────────────────────────────────

async function visitarTela(contexto, tela) {
  const { pagina, caixa, opcoes, perfil, largura } = contexto;
  caixa.erros.length = 0;
  try {
    await pagina.goto(`${opcoes.base}${tela.caminho}?projeto=portfolio`, {
      waitUntil: "domcontentloaded",
      timeout: 30000,
    });
    await esperarShell(pagina);
    await pagina.waitForLoadState("networkidle", { timeout: 5000 }).catch(() => {});
    await pagina.waitForTimeout(150);
  } catch (erro) {
    return [
      falhaDe({
        perfil,
        largura,
        tela,
        categoria: "abertura",
        detalhe: `a tela não abriu: ${erro.message.split("\n")[0]}`,
      }),
    ];
  }
  const fatos = await lerFatos(pagina, tela);
  const erros = esperaAcessoNegado(perfil, tela)
    ? caixa.erros.filter((texto) => !/403/.test(texto))
    : [...caixa.erros];
  const falhas = [
    ...conferirConteudo(fatos, perfil, largura, tela),
    ...conferirBarra(fatos, perfil, largura, tela),
    ...conferirRolagem(fatos, perfil, largura, tela),
    ...erros.map((texto) => falhaDe({ perfil, largura, tela, categoria: "console", detalhe: texto })),
  ];
  const links = await conferirLinks({ ...contexto, tela }, fatos);
  return [...falhas, ...links];
}

async function varrerCombinacao(navegador, programa, perfil, largura) {
  const janela = await navegador.newContext({ viewport: { width: largura, height: ALTURA } });
  const pagina = await janela.newPage();
  const caixa = { erros: [] };
  pagina.on("console", (mensagem) => {
    if (mensagem.type() === "error") caixa.erros.push(`console: ${mensagem.text()}`);
  });
  pagina.on("pageerror", (erro) => caixa.erros.push(`pageerror: ${erro.message}`));
  const resultado = { perfil: perfil.chave, largura, total: 0, ok: 0, falhas: [] };
  try {
    await iniciarSessao(janela, pagina, programa, perfil);
    const contexto = {
      pagina,
      caixa,
      opcoes: programa,
      perfil,
      largura,
      cache: programa.cacheDeLinks.get(perfil.chave) ?? new Map(),
      requisicoes: {
        base: programa.base,
        fetch: janela.request.fetch.bind(janela.request),
        telas: programa.telas,
      },
    };
    programa.cacheDeLinks.set(perfil.chave, contexto.cache);
    for (const tela of programa.telas) {
      const problemas = await visitarTela(contexto, tela);
      resultado.total += 1;
      if (problemas.length === 0) {
        resultado.ok += 1;
      } else {
        resultado.falhas.push(...problemas);
      }
    }
  } catch (erro) {
    resultado.falhas.push({
      perfil: perfil.chave,
      largura,
      tela: "(sessão)",
      categoria: "sessao",
      detalhe: erro.message,
    });
  } finally {
    await janela.close();
  }
  return resultado;
}

// ── Relatório ──────────────────────────────────────────────────────────

const CATEGORIAS = ["console", "rolagem", "barra", "estilo", "conteudo", "link", "permissao", "abertura", "sessao"];

function imprimirRelatorio(resultados, telas, opcoes, segundos) {
  console.log("");
  console.log(`Varredura de telas — ${opcoes.base}`);
  console.log(
    `Telas: ${telas.length} · Larguras: ${opcoes.larguras.join(", ")} px · Perfis: ` +
      opcoes.perfis.map((perfil) => perfil.chave).join(", ")
  );
  console.log("─".repeat(72));
  const geral = { total: 0, ok: 0 };
  const porCategoria = new Map(CATEGORIAS.map((categoria) => [categoria, 0]));
  const falhas = [];
  for (const resultado of resultados) {
    geral.total += resultado.total;
    geral.ok += resultado.ok;
    for (const falha of resultado.falhas) {
      porCategoria.set(falha.categoria, (porCategoria.get(falha.categoria) ?? 0) + 1);
      falhas.push(falha);
    }
    const marca = resultado.falhas.length === 0 ? "ok" : `${resultado.falhas.length} falha(s)`;
    console.log(
      `${resultado.perfil.padEnd(14)} ${String(resultado.largura).padStart(5)}px  ` +
        `${String(resultado.total).padStart(3)} telas · ${marca}`
    );
  }
  console.log("─".repeat(72));
  const categorias = [...porCategoria.entries()].filter(([, quantidade]) => quantidade > 0);
  if (categorias.length === 0) {
    console.log(`Tudo certo: ${geral.ok}/${geral.total} navegações aprovadas.`);
  } else {
    for (const [categoria, quantidade] of categorias) {
      console.log(`${categoria}: ${quantidade}`);
    }
    console.log("─".repeat(72));
    for (const falha of falhas) {
      console.log(`FALHA [${falha.categoria}] ${falha.perfil} ${falha.largura}px ${falha.tela}: ${falha.detalhe}`);
    }
    console.log("─".repeat(72));
    console.log(`${geral.total - geral.ok} de ${geral.total} navegações reprovadas.`);
  }
  console.log(`Duração: ${segundos.toFixed(1)}s`);
  return falhas.length;
}

// ── Rodando ────────────────────────────────────────────────────────────

async function principal() {
  const opcoes = lerOpcoes(process.argv.slice(2));
  opcoes.telas = lerTelas();
  opcoes.cacheDeLinks = new Map();
  entradaDoFornecedor =
    opcoes.telas.find((tela) => tela.pasta === "programacao_semanal" && !tela.detalhe) ?? null;
  if (opcoes.perfis.length === 0) {
    console.error("varredura-telas: nenhum perfil conhecido em --perfis.");
    process.exit(2);
  }
  console.log(
    `Varredura de telas: ${opcoes.telas.length} telas × ${opcoes.larguras.length} larguras × ` +
      `${opcoes.perfis.length} perfis`
  );
  const navegador = await chromium.launch();
  const inicio = Date.now();
  const resultados = [];
  try {
    for (const perfil of opcoes.perfis) {
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
  const reprovadas = imprimirRelatorio(resultados, opcoes.telas, opcoes, (Date.now() - inicio) / 1000);
  process.exit(reprovadas === 0 ? 0 : 1);
}

await principal();
