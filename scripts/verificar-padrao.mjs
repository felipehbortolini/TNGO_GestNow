#!/usr/bin/env node
/**
 * verificar-padrao.mjs — porta de qualidade do modelo.
 *
 * Roda as verificações da Regra 5 do contrato visual. É o que impede
 * uma página nova de nascer sem estilo ou fora do padrão.
 *
 *   node scripts/verificar-padrao.mjs
 *
 * Sai com código 1 se qualquer verificação falhar — dá para plugar no CI.
 */

import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, dirname, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const RAIZ = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const APP = join(RAIZ, "app");
const API = join(RAIZ, "api");
const TEMPLATES = join(API, "src", "templates");

const MODULOS = [
  "inicio",
  "central_acoes",
  "planejamento",
  "programacao_semanal",
  "financeiro",
  "suprimentos",
  "riscos",
  "qualidade",
  "hse",
  "governanca",
  "configuracoes",
  "relatorio",
];

const CAMADAS_MODULOS = [
  ["views", join(APP, "_views")],
  ["paginas", join(APP, "paginas")],
  ["backend", join(API, "src", "modulos")],
  ["templates", TEMPLATES],
  ["testes", join(API, "tests")],
];

const ARQUIVOS_MODULO = [
  "routes.py",
  "service.py",
  "calculations.py",
  "validation.py",
  "export.py",
  "models.py",
];

const falhas = [];
const avisos = [];

function reportar(regra, arquivo, detalhe) {
  falhas.push({ regra, arquivo: relative(RAIZ, arquivo), detalhe });
}

function arquivos(dir, ext) {
  if (!existsSync(dir)) return [];
  const saida = [];
  for (const nome of readdirSync(dir)) {
    const caminho = join(dir, nome);
    if (statSync(caminho).isDirectory()) {
      if (nome === "_nao-utilizados" || nome === "lib") continue;
      saida.push(...arquivos(caminho, ext));
    } else if (ext.some((e) => nome.endsWith(e))) {
      saida.push(caminho);
    }
  }
  return saida;
}

const ler = (f) => readFileSync(f, "utf8");

// ── 1. Sem CDN em app/ ──────────────────────────────────────────────
// docs/ é isento: architecture-reviews/ usa Tailwind e mermaid via CDN
// e é documento, não aplicação.
for (const f of arquivos(APP, [".html", ".css", ".js"])) {
  const m = ler(f).match(/(?:href|src)\s*=\s*["'](https?:)?\/\/[^"']+/gi);
  if (m) reportar("sem-cdn", f, m[0].slice(0, 70));
}

// ── 2. Sem Tailwind/DaisyUI ─────────────────────────────────────────
const CLASSES_PROIBIDAS =
  /\bclass\s*=\s*["'][^"']*\b(bg-base-\d|text-base-content|btn-primary|btn-ghost|card-body|card-title|navbar(-\w+)?|badge-\w+|hero-content|fieldset-legend|loading-spinner)\b/;
for (const f of [...arquivos(APP, [".html"]), ...arquivos(TEMPLATES, [".html"])]) {
  const m = ler(f).match(CLASSES_PROIBIDAS);
  if (m) reportar("sem-tailwind-daisyui", f, m[1]);
}

// ── 3. Fragmento limpo: sem <link>, <style> ou <script src> ─────────
const PASTAS_FRAGMENTO = [
  join(APP, "_views"),
  join(APP, "_components"),
  TEMPLATES,
];
for (const dir of PASTAS_FRAGMENTO) {
  for (const f of arquivos(dir, [".html"])) {
    const txt = ler(f).replace(/<!--[\s\S]*?-->/g, "").replace(/\{#[\s\S]*?#\}/g, "");
    if (/<link\b/i.test(txt)) reportar("fragmento-limpo", f, "<link>");
    if (/<style\b/i.test(txt)) reportar("fragmento-limpo", f, "<style>");
    if (/<script[^>]+\bsrc\b/i.test(txt)) reportar("fragmento-limpo", f, "<script src>");
    if (/<(html|head|body)\b/i.test(txt)) reportar("fragmento-limpo", f, "<html/head/body>");
  }
}

// ── 4. Todo recurso local existe no disco ───────────────────────────
// É a verificação que teria pego o /kyno-theme.css do template original.
for (const f of arquivos(APP, [".html"])) {
  const txt = ler(f).replace(/<!--[\s\S]*?-->/g, "");
  for (const m of txt.matchAll(/(?:href|src)\s*=\s*["'](\/[^"'#?]+)/g)) {
    const url = m[1];
    if (url.startsWith("/.auth") || url.startsWith("/api/") || url.startsWith("/_")) continue;
    if (!existsSync(join(APP, url))) reportar("recurso-existe", f, url);
  }
}

// ── 4b. url() do CSS resolve no disco ───────────────────────────────
// Pega @font-face apontando para arquivo que não foi versionado, e
// background-image de asset renomeado.
for (const f of arquivos(join(APP, "ds"), [".css"])) {
  for (const m of ler(f).matchAll(/url\(\s*["']?([^"')]+)["']?\s*\)/g)) {
    const ref = m[1].trim();
    if (ref.startsWith("data:") || /^https?:/.test(ref)) continue;
    const alvo = ref.startsWith("/") ? join(APP, ref) : join(dirname(f), ref);
    if (!existsSync(alvo)) reportar("recurso-existe", f, `url(${ref})`);
  }
}

// ── 5. Sem nome de asset em formato UUID ────────────────────────────
const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
for (const f of [...arquivos(APP, [".html", ".css", ".js"]), ...arquivos(TEMPLATES, [".html"])]) {
  const m = ler(f).match(UUID);
  if (m) reportar("sem-uuid", f, m[0]);
}

// ── 6. Sem prefixo de app específico ────────────────────────────────
for (const f of arquivos(APP, [".js", ".css", ".html"])) {
  const m = ler(f).match(/\bCAA_[A-Za-z]+/);
  if (m) reportar("sem-prefixo-de-app", f, m[0]);
}

// ── 7. Raiz do fragmento de view ────────────────────────────────────
for (const f of arquivos(join(APP, "_views"), [".html"])) {
  const txt = ler(f).replace(/<!--[\s\S]*?-->/g, "").trim();
  if (!/^<main\s+id=["']app-shell["']/.test(txt)) {
    reportar("raiz-do-fragmento", f, 'a raiz precisa ser <main id="app-shell" ...>');
  }
  if (!/class=["'][^"']*\bcontent\b/.test(txt.slice(0, 200))) {
    avisos.push(`${relative(RAIZ, f)}: <main> sem class="content"`);
  }
}

// ── 8. Design System carregado no shell ─────────────────────────────
const shell = ler(join(APP, "index.html"));
for (const recurso of ["/ds/tokens.css", "/ds/shell.css", "/ds/patterns.css", "/ds/icons.js", "/ds/ui.js"]) {
  if (!shell.includes(recurso)) {
    reportar("contrato-visual", join(APP, "index.html"), `não carrega ${recurso}`);
  }
}
if (!ler(join(APP, "ds", "tokens.css")).includes("--ds-carregado")) {
  reportar("contrato-visual", join(APP, "ds", "tokens.css"), "sentinela --ds-carregado ausente");
}
if (!shell.includes("--ds-carregado")) {
  reportar("contrato-visual", join(APP, "index.html"), "shell não verifica o sentinela (Regra 4)");
}

// ── 9. Sem colisão de seletor entre os CSS do DS ────────────────────
function seletores(arquivo) {
  const css = ler(arquivo).replace(/\/\*[\s\S]*?\*\//g, "");
  const out = new Set();
  for (const m of css.matchAll(/([^{}]+)\{/g)) {
    const bloco = m[1];
    if (bloco.includes("@")) continue;
    for (const s of bloco.split(",")) {
      const t = s.trim();
      if (t) out.add(t);
    }
  }
  return out;
}
const arquivosCss = ["tokens.css", "shell.css", "patterns.css"].map((n) => join(APP, "ds", n));
for (let i = 0; i < arquivosCss.length; i++) {
  for (let j = i + 1; j < arquivosCss.length; j++) {
    for (const s of seletores(arquivosCss[i])) {
      if (seletores(arquivosCss[j]).has(s)) {
        reportar("colisao-css", arquivosCss[j], `"${s}" também em ${relative(APP, arquivosCss[i])}`);
      }
    }
  }
}

// ── 10. Estrutura dos módulos ────────────────────────────────────────
const functionApp = ler(join(API, "function_app.py"));
for (const modulo of MODULOS) {
  for (const [camada, raizCamada] of CAMADAS_MODULOS) {
    const pasta = join(raizCamada, modulo);
    if (!existsSync(pasta) || readdirSync(pasta).length === 0) {
      reportar("estrutura-dos-modulos", pasta, `módulo ${modulo}: pasta da camada ${camada} ausente ou vazia`);
    }
  }

  const pastaBackend = join(API, "src", "modulos", modulo);
  for (const arquivo of ARQUIVOS_MODULO) {
    if (!existsSync(join(pastaBackend, arquivo))) {
      reportar("estrutura-dos-modulos", join(pastaBackend, arquivo), `módulo ${modulo}: arquivo ${arquivo} ausente`);
    }
  }

  const leiaMe = join(pastaBackend, "LEIA-ME.md");
  if (!existsSync(leiaMe)) {
    reportar("estrutura-dos-modulos", leiaMe, `módulo ${modulo}: LEIA-ME.md ausente`);
  }

  const blueprint = `${modulo}_bp`;
  if (
    !functionApp.includes(`from src.modulos.${modulo}.routes import bp as ${blueprint}`) ||
    !functionApp.includes(`app.register_functions(${blueprint})`)
  ) {
    reportar("estrutura-dos-modulos", join(API, "function_app.py"), `módulo ${modulo}: blueprint não importado e registrado`);
  }
}

// ── Relatório ───────────────────────────────────────────────────────
const REGRAS = [
  "sem-cdn", "sem-tailwind-daisyui", "fragmento-limpo", "recurso-existe",
  "sem-uuid", "sem-prefixo-de-app", "raiz-do-fragmento", "contrato-visual",
  "colisao-css", "estrutura-dos-modulos",
];

console.log("\nVerificação do padrão Timenow\n" + "─".repeat(52));
for (const regra of REGRAS) {
  const doGrupo = falhas.filter((f) => f.regra === regra);
  console.log(`${doGrupo.length ? "FALHA" : "  ok "}  ${regra}${doGrupo.length ? ` (${doGrupo.length})` : ""}`);
  for (const f of doGrupo) console.log(`        ${f.arquivo}: ${f.detalhe}`);
}

if (avisos.length) {
  console.log("\nAvisos:");
  for (const a of avisos) console.log(`   ~ ${a}`);
}

console.log("─".repeat(52));
if (falhas.length) {
  console.log(`${falhas.length} falha(s).\n`);
  process.exit(1);
}
console.log("Tudo conforme o padrão.\n");
