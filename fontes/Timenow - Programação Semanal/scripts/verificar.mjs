#!/usr/bin/env node
/**
 * verificar.mjs — porta de qualidade única do modelo.
 *
 * Roda, em ordem, tudo que precisa passar antes de um commit:
 *
 *   1. ruff check     Python — lint
 *   2. ruff format    Python — formatação
 *   3. ty check       Python — tipos
 *   4. pytest         Python — regras de domínio
 *   5. eslint         JS, CSS e HTML
 *   6. padrão Timenow contrato visual, paridade, Design System
 *
 * Por que um script só: enforcement de verdade não vem de documentação,
 * vem de um comando que falha. Quatro ferramentas separadas viram quatro
 * comandos que alguém esquece de rodar.
 *
 *   node scripts/verificar.mjs            tudo
 *   node scripts/verificar.mjs --corrigir aplica o que é automático antes
 *   node scripts/verificar.mjs --py       só Python
 *   node scripts/verificar.mjs --front    só JS/CSS/HTML
 *
 * Sai com código 1 se qualquer etapa falhar — serve para CI e hook.
 */

import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const RAIZ = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const API = join(RAIZ, "api");

const args = new Set(process.argv.slice(2));
const corrigir = args.has("--corrigir") || args.has("--fix");
const soPython = args.has("--py");
const soFront = args.has("--front");

const AZUL = "\x1b[36m";
const VERDE = "\x1b[32m";
const VERMELHO = "\x1b[31m";
const CINZA = "\x1b[90m";
const FIM = "\x1b[0m";

// No Windows os executáveis do venv ficam em Scripts/, no resto em bin/.
const venvBin = join(API, ".venv", process.platform === "win32" ? "Scripts" : "bin");
const exe = (nome) => join(venvBin, process.platform === "win32" ? `${nome}.exe` : nome);

const etapas = [];

function registrar(nome, comando, argumentos, opcoes = {}) {
  etapas.push({ nome, comando, argumentos, ...opcoes });
}

// ── Python ────────────────────────────────────────────────────────────
if (!soFront) {
  const ruff = exe("ruff");
  const ty = exe("ty");

  if (!existsSync(ruff)) {
    console.error(
      `${VERMELHO}O ambiente Python não está preparado.${FIM}\n` +
        `  Esperava encontrar ${ruff}\n` +
        `  Rode:  cd api && uv sync\n` +
        `  Ou:    .\\scripts\\instalar.ps1\n`,
    );
    process.exit(1);
  }

  registrar("ruff check   (Python · lint)", ruff, corrigir ? ["check", ".", "--fix"] : ["check", "."], { cwd: API });
  registrar("ruff format  (Python · formatação)", ruff, corrigir ? ["format", "."] : ["format", "--check", "."], { cwd: API });
  registrar("ty check     (Python · tipos)", ty, ["check"], { cwd: API });

  // Os linters pegam a forma do código; o pytest pega a conta errada.
  // Cobre o que quebraria em silêncio mostrando um número plausível:
  // aritmética de semana ISO, janela de programação e a curva S.
  registrar("pytest       (Python · domínio)", exe("python"), ["-m", "pytest"], { cwd: API });
}

// ── Front ─────────────────────────────────────────────────────────────
if (!soPython) {
  if (!existsSync(join(RAIZ, "node_modules", "eslint"))) {
    console.error(
      `${VERMELHO}O ESLint não está instalado.${FIM}\n` +
        `  Rode:  npm install\n` +
        `  Ou:    .\\scripts\\instalar.ps1\n`,
    );
    process.exit(1);
  }

  // Chamado pelo próprio entrypoint em JS, não por `npx`. No Windows o npx
  // é um .cmd, e desde a correção de CVE-2024-27980 o Node exige shell para
  // executá-lo — o que reparte qualquer caminho com espaço, e "Padrao
  // Desenvolvimento" tem um. Rodar pelo node evita o shell por completo.
  registrar(
    "eslint       (JS, CSS, HTML)",
    process.execPath,
    [
      join(RAIZ, "node_modules", "eslint", "bin", "eslint.js"),
      ".",
      ...(corrigir ? ["--fix"] : []),
    ],
    { cwd: RAIZ },
  );
}

// ── Padrão Timenow ────────────────────────────────────────────────────
// Sempre roda: cobre contrato visual, Design System e paridade — coisas
// que nenhum linter de mercado conhece.
registrar("padrão Timenow (contrato visual, DS)", process.execPath, [join(RAIZ, "scripts", "verificar-padrao.mjs")], {
  cwd: RAIZ,
  silenciarSucesso: false,
});

// ── Execução ──────────────────────────────────────────────────────────
console.log(`\n${AZUL}Porta de qualidade — Programação Semanal${FIM}`);
if (corrigir) console.log(`${CINZA}modo --corrigir: aplica o que for automático${FIM}`);
console.log("─".repeat(58));

const falhas = [];

for (const etapa of etapas) {
  process.stdout.write(`  ${etapa.nome.padEnd(38)}`);

  // shell: false sempre. Todo comando aqui é um caminho absoluto para um
  // executável real (.exe do venv ou o próprio node), então não há nada a
  // resolver via PATH — e passar pelo shell no Windows quebraria em
  // qualquer diretório com espaço no nome.
  const r = spawnSync(etapa.comando, etapa.argumentos, {
    cwd: etapa.cwd,
    encoding: "utf8",
    shell: false,
  });

  const saida = `${r.stdout || ""}${r.stderr || ""}`.trim();

  if (r.status === 0) {
    console.log(`${VERDE}ok${FIM}`);
  } else {
    console.log(`${VERMELHO}FALHOU${FIM}`);
    falhas.push({ nome: etapa.nome, saida });
  }
}

console.log("─".repeat(58));

if (falhas.length === 0) {
  console.log(`${VERDE}Tudo passou.${FIM}\n`);
  process.exit(0);
}

for (const f of falhas) {
  console.log(`\n${VERMELHO}▼ ${f.nome}${FIM}`);
  console.log(f.saida || "(sem saída)");
}

console.log(
  `\n${VERMELHO}${falhas.length} etapa(s) falharam.${FIM}\n` +
    `${CINZA}Boa parte costuma ser automática:  node scripts/verificar.mjs --corrigir${FIM}\n`,
);
process.exit(1);
