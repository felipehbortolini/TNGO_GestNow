#!/usr/bin/env node
/**
 * verificar-trio-da-tela.mjs — a verificação `trio-da-tela` (D3).
 *
 * Toda tela da lista de navegação (api/src/core/navegacao.json) tem um trio
 * com o mesmo nome, e o shell vincula o CSS e o JS de todos:
 *
 *   app/_views/<modulo>/<tela>.html   a view (fragmento)
 *   app/paginas/<modulo>/<tela>.css   o estilo da página
 *   app/paginas/<modulo>/<tela>.js    o comportamento da página
 *   app/index.html                    o <link> do CSS e o <script> do JS
 *
 * A tela é identificada por "<modulo>/<tela>", como no navegacao.json: <modulo>
 * é a pasta da tela, que nem sempre é o módulo da navegação (a Programação
 * Semanal tem pasta própria e aparece entre as abas do Planejamento).
 *
 * Reprova, nomeando a tela:
 *   - view sem CSS ou view sem JS
 *   - trio fora do shell: o index.html não vincula o CSS ou o JS
 *   - view sem item de navegação, e item de navegação sem view
 *   - trio incoerente: a raiz da view sem a classe da página, a view que não
 *     aciona o iniciar() do JS por x-init, o JS que não registra a página
 *   - view com <script> (nenhum fragmento carrega script)
 *
 *   node scripts/verificar-trio-da-tela.mjs [--raiz <pasta>]
 *
 * --raiz aponta outra árvore com a mesma estrutura (o teste monta uma mínima).
 * A porta de qualidade chama a verificação por scripts/verificar-padrao.mjs
 * (regra `trio-da-tela`); rodando sozinho, sai com código 1 se houver falha.
 */

import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { basename, dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const ESTE_ARQUIVO = fileURLToPath(import.meta.url);
const RAIZ_DO_PRODUTO = resolve(dirname(ESTE_ARQUIVO), "..");

// O que sobra de uma view ou de um JS depois de tirar os comentários: um
// comentário de propósito cita TN.paginas["..."] sem registrar nada.
const COMENTARIO_HTML = /<!--[\s\S]*?-->/g;
const COMENTARIO_JS = /\/\*[\s\S]*?\*\/|^\s*\/\/.*$/gm;

// A tag <main> aceita ">" dentro de um atributo entre aspas (x-init com seta).
const TAG_MAIN = /<main\b(?:[^>"']|"[^"]*"|'[^']*')*>/i;

const escapar = (texto) => texto.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const chamaIniciar = (chave) =>
  new RegExp(`TN\\.paginas\\[\\s*["']${escapar(chave)}["']\\s*\\]\\s*\\.iniciar\\s*\\(`);

const registraPagina = (chave) =>
  new RegExp(`TN\\.paginas\\[\\s*["']${escapar(chave)}["']\\s*\\]\\s*=(?!=)`);

// ── Leitura ──────────────────────────────────────────────────────────

function caminhosDe(raiz) {
  return {
    raiz,
    navegacao: join(raiz, "api", "src", "core", "navegacao.json"),
    shell: join(raiz, "app", "index.html"),
    views: join(raiz, "app", "_views"),
    paginas: join(raiz, "app", "paginas"),
  };
}

function listarArquivos(pasta, extensao) {
  if (!existsSync(pasta)) return [];
  const encontrados = [];
  for (const nome of readdirSync(pasta)) {
    const caminho = join(pasta, nome);
    if (statSync(caminho).isDirectory()) encontrados.push(...listarArquivos(caminho, extensao));
    else if (nome.endsWith(extensao)) encontrados.push(caminho);
  }
  return encontrados;
}

// Valor de um atributo de uma tag; o nome vem depois de um espaço, para
// "src" não casar com "data-src".
function atributo(tag, nome) {
  const achado = tag.match(new RegExp(`\\s${nome}\\s*=\\s*["']([^"']*)["']`, "i"));
  return achado ? achado[1] : null;
}

function classesDaRaiz(html) {
  const raiz = html.match(TAG_MAIN);
  const classes = raiz ? atributo(raiz[0], "class") : null;
  return classes ? classes.split(/\s+/) : [];
}

// As chaves "<modulo>/<tela>" da lista de navegação.
function lerNavegacao(contexto) {
  const chaves = new Set();
  const { navegacao } = contexto.caminhos;
  let lista;
  try {
    lista = JSON.parse(readFileSync(navegacao, "utf8"));
  } catch (erro) {
    contexto.falha(navegacao, null, `lista de navegação ilegível (${erro.message})`);
    return chaves;
  }
  for (const modulo of lista.modulos ?? []) {
    for (const tela of modulo.telas ?? []) {
      chaves.add(`${tela.modulo ?? modulo.id}/${tela.id}`);
    }
  }
  return chaves;
}

// O que o shell vincula: os href dos <link rel="stylesheet"> e os src dos
// <script>. Comentário não vincula nada.
function lerVinculosDoShell(contexto) {
  const vinculos = { estilos: new Set(), scripts: new Set() };
  const { shell } = contexto.caminhos;
  if (!existsSync(shell)) {
    contexto.falha(shell, null, "shell ausente (app/index.html)");
    return vinculos;
  }
  const html = readFileSync(shell, "utf8").replace(COMENTARIO_HTML, "");
  for (const [tag] of html.matchAll(/<link\b[^>]*>/gi)) {
    const href = atributo(tag, "href");
    if (href && /stylesheet/i.test(atributo(tag, "rel") ?? "")) vinculos.estilos.add(href);
  }
  for (const [tag] of html.matchAll(/<script\b[^>]*>/gi)) {
    const src = atributo(tag, "src");
    if (src) vinculos.scripts.add(src);
  }
  return vinculos;
}

// As views do disco, por chave "<modulo>/<tela>".
function lerViews(contexto) {
  const { views: pasta } = contexto.caminhos;
  const encontradas = new Map();
  for (const arquivo of listarArquivos(pasta, ".html")) {
    const partes = relative(pasta, arquivo).split(sep);
    if (partes.length === 2) {
      encontradas.set(`${partes[0]}/${partes[1].slice(0, -".html".length)}`, arquivo);
    } else {
      contexto.falha(arquivo, null, "view fora do padrão app/_views/<modulo>/<tela>.html");
    }
  }
  return encontradas;
}

// ── Conferência ──────────────────────────────────────────────────────

function conferirNavegacao(contexto, chave, arquivoDaView) {
  if (!contexto.navegacao.has(chave)) {
    contexto.falha(
      arquivoDaView,
      chave,
      "view sem item de navegação (acrescente a tela em api/src/core/navegacao.json)",
    );
  }
}

// Cada arquivo da página existe e está vinculado no shell.
function conferirArquivosDaPagina(contexto, chave, arquivoDaView) {
  const { caminhos, vinculos, falha } = contexto;
  for (const extensao of ["css", "js"]) {
    const url = `/paginas/${chave}.${extensao}`;
    if (!existsSync(join(caminhos.paginas, `${chave}.${extensao}`))) {
      falha(arquivoDaView, chave, `view sem ${extensao.toUpperCase()} (esperado app${url})`);
    }
    const vinculados = extensao === "css" ? vinculos.estilos : vinculos.scripts;
    if (!vinculados.has(url)) {
      falha(caminhos.shell, chave, `trio fora do shell: index.html não vincula ${url}`);
    }
  }
}

// A view e o JS combinam: a classe da página, a chamada do iniciar() e o
// registro em TN.paginas, todos com a chave da tela.
function conferirConteudoDaView(contexto, chave, arquivo) {
  const [modulo, tela] = chave.split("/");
  const html = readFileSync(arquivo, "utf8").replace(COMENTARIO_HTML, "");
  const classe = `pagina--${modulo}-${tela}`;
  if (!classesDaRaiz(html).includes(classe)) {
    contexto.falha(arquivo, chave, `trio incoerente: a raiz da view não tem a classe ${classe}`);
  }
  if (!chamaIniciar(chave).test(html)) {
    const chamada = `TN.paginas["${chave}"].iniciar()`;
    contexto.falha(arquivo, chave, `trio incoerente: a view não aciona ${chamada} por x-init`);
  }
  if (/<script\b/i.test(html)) {
    contexto.falha(arquivo, chave, "view com <script>: nenhum fragmento carrega script");
  }
}

function conferirRegistroDoScript(contexto, chave) {
  const arquivo = join(contexto.caminhos.paginas, `${chave}.js`);
  if (!existsSync(arquivo)) return;
  const codigo = readFileSync(arquivo, "utf8").replace(COMENTARIO_JS, "");
  if (!registraPagina(chave).test(codigo)) {
    contexto.falha(arquivo, chave, `trio incoerente: o JS não registra TN.paginas["${chave}"]`);
  }
}

const porTela = (a, b) =>
  (a.tela ?? "").localeCompare(b.tela ?? "") || a.detalhe.localeCompare(b.detalhe);

/**
 * Confere o trio de toda tela sob `raiz` e devolve as falhas: { arquivo, tela,
 * detalhe }, ordenadas por tela. `arquivo` é o caminho onde está o defeito e
 * `tela` é "<modulo>/<tela>" (ou null, quando o defeito não é de uma tela).
 */
export function verificarTrioDaTela(raiz = RAIZ_DO_PRODUTO) {
  const falhas = [];
  const contexto = {
    caminhos: caminhosDe(raiz),
    falha: (arquivo, tela, detalhe) => falhas.push({ arquivo, tela, detalhe }),
  };
  contexto.navegacao = lerNavegacao(contexto);
  contexto.vinculos = lerVinculosDoShell(contexto);

  const views = lerViews(contexto);
  for (const chave of [...views.keys()].sort()) {
    const arquivo = views.get(chave);
    conferirNavegacao(contexto, chave, arquivo);
    conferirArquivosDaPagina(contexto, chave, arquivo);
    conferirConteudoDaView(contexto, chave, arquivo);
    conferirRegistroDoScript(contexto, chave);
  }
  for (const chave of [...contexto.navegacao].sort()) {
    if (!views.has(chave)) {
      const detalhe = `item de navegação sem view (esperado app/_views/${chave}.html)`;
      contexto.falha(contexto.caminhos.navegacao, chave, detalhe);
    }
  }
  return falhas.sort(porTela);
}

/** A falha como a porta de qualidade a mostra: a tela primeiro, depois o defeito. */
export const descreverFalha = (falha) =>
  falha.tela ? `${falha.tela}: ${falha.detalhe}` : falha.detalhe;

// ── Rodando sozinho ──────────────────────────────────────────────────

function lerRaiz(argumentos) {
  const indice = argumentos.indexOf("--raiz");
  if (indice === -1) return RAIZ_DO_PRODUTO;
  const pasta = argumentos[indice + 1];
  if (!pasta) {
    console.error("verificar-trio-da-tela: --raiz pede uma pasta.");
    process.exit(2);
  }
  return resolve(pasta);
}

function executar() {
  const falhas = verificarTrioDaTela(lerRaiz(process.argv.slice(2)));
  console.log("\nVerificação trio-da-tela\n" + "─".repeat(52));
  for (const falha of falhas) console.log(`FALHA  ${descreverFalha(falha)}`);
  console.log("─".repeat(52));
  if (falhas.length > 0) {
    console.log(`${falhas.length} falha(s).\n`);
    process.exit(1);
  }
  console.log("Toda tela tem view, CSS e JS vinculados no shell.\n");
}

// Importado pelo verificar-padrao.mjs, este arquivo só exporta; rodado pelo
// node, confere o repositório (ou a árvore de --raiz).
if (process.argv[1] && basename(process.argv[1]) === basename(ESTE_ARQUIVO)) executar();
