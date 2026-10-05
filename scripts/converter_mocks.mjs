#!/usr/bin/env node
/**
 * converter_mocks.mjs — converte os mocks do protótipo em dados de carga.
 *
 * A carga de demonstração não reimplementa gerador nenhum: executa os mocks
 * do protótipo na mesma ordem em que o `index.html` os carrega, num
 * `window` isolado, e grava o resultado já gerado em
 * `api/src/carga/dados/<destino>.json` (ISSUE-008, D6/Q15).
 *
 *   node scripts/converter_mocks.mjs
 *
 * Cada issue de módulo acrescenta as coleções da sua parte à seleção e
 * roda este script de novo; o LEIA-ME da carga explica o passo a passo
 * (`api/src/carga/LEIA-ME.md`). O protótipo fica apenas como fonte de
 * leitura — este script nunca escreve na pasta de origem.
 */

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const RAIZ = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const ORIGEM = join(RAIZ, "..", "Sistema", "data");
const DESTINO = join(RAIZ, "api", "src", "carga", "dados", "plataforma.json");

// Ordem de carga do protótipo; conferida no MODELO-DE-DADOS.md ("Verificação
// das coleções"). O mock-portfolio acrescenta registros às coleções dos
// mocks anteriores, então precisa vir por último.
const ARQUIVOS = [
  "mock-config",
  "mock-base",
  "mock-central",
  "mock-planejamento",
  "mock-financeiro",
  "mock-suprimentos",
  "mock-riscos",
  "mock-qualidade",
  "mock-hse",
  "mock-governanca",
  "mock-portfolio",
];

// Nome de negócio das unidades de medida usadas nos mocks; o que não estiver
// aqui é unidade organizacional (ex.: "Unidade Horizonte").
const NOMES_MEDIDA = {
  "%": "Percentual",
  Hh: "Homem-hora",
  juntas: "Juntas",
  m: "Metro",
  "m²": "Metro quadrado",
  "m³": "Metro cúbico",
  "mês": "Mês",
  t: "Tonelada",
  un: "Unidade",
  vb: "Verba",
};

function carregarMocks() {
  const sandbox = { console, window: {} };
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  for (const nome of ARQUIVOS) {
    const codigo = readFileSync(join(ORIGEM, `${nome}.js`), "utf8");
    vm.runInContext(codigo, sandbox, { filename: `${nome}.js` });
  }
  return sandbox.window.MOCK;
}

function semAcento(texto) {
  return texto.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

function codigoDoLocal(nome) {
  const numero = /(\d{2,4})\s*$/.exec(nome);
  if (numero) return numero[1];
  return semAcento(nome).toUpperCase().replace(/[^A-Z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

// Código e nome por projeto, na ordem em que o protótipo os usa.
function locaisDe(programacoes) {
  const vistos = new Map();
  for (const lote of programacoes ?? []) {
    for (const atividade of lote.atividades ?? []) {
      if (!atividade.local) continue;
      const chave = `${lote.projetoId}:${atividade.local}`;
      if (vistos.has(chave)) continue;
      vistos.set(chave, {
        projetoId: lote.projetoId,
        codigo: codigoDoLocal(atividade.local),
        nome: atividade.local,
      });
    }
  }
  return [...vistos.values()];
}

// Percorre a árvore de mocks e junta os valores de um campo de texto; é como
// o protótipo guarda disciplina e unidade (campos soltos dentro dos registros).
function valoresDoCampo(valor, campo, achados) {
  if (Array.isArray(valor)) {
    for (const item of valor) valoresDoCampo(item, campo, achados);
    return;
  }
  if (valor === null || typeof valor !== "object") return;
  for (const [chave, filho] of Object.entries(valor)) {
    if (chave === campo && typeof filho === "string" && filho.trim()) {
      achados.add(filho.trim());
    } else {
      valoresDoCampo(filho, campo, achados);
    }
  }
}

function unidadesDe(mocks) {
  const achados = new Set();
  valoresDoCampo(mocks, "unidade", achados);
  return [...achados].sort().map((codigo) => {
    const nome = NOMES_MEDIDA[codigo];
    if (nome) return { tipo: "medida", codigo, nome };
    return { tipo: "organizacional", codigo, nome: codigo };
  });
}

function disciplinasDe(mocks) {
  const achados = new Set();
  valoresDoCampo(mocks, "disciplina", achados);
  return [...achados].sort();
}

function montarPayload(mocks) {
  return {
    origem: "Sistema/data do protótipo, na ordem de carga do MODELO-DE-DADOS.md",
    ancora: mocks.referencia,
    geradoPor: "scripts/converter_mocks.mjs",
    clientes: mocks.clientes ?? [],
    projetos: mocks.projetos ?? [],
    empresas: mocks.empresas ?? [],
    pessoas: mocks.pessoas ?? [],
    sistemas: mocks.sistemas ?? [],
    locais: locaisDe(mocks.programacoes),
    disciplinas: disciplinasDe(mocks),
    unidades: unidadesDe(mocks),
  };
}

function main() {
  const mocks = carregarMocks();
  const payload = montarPayload(mocks);
  mkdirSync(dirname(DESTINO), { recursive: true });
  writeFileSync(DESTINO, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  const contagens = [
    `clientes ${payload.clientes.length}`,
    `projetos ${payload.projetos.length}`,
    `empresas ${payload.empresas.length}`,
    `pessoas ${payload.pessoas.length}`,
    `sistemas ${payload.sistemas.length}`,
    `locais ${payload.locais.length}`,
    `disciplinas ${payload.disciplinas.length}`,
    `unidades ${payload.unidades.length}`,
  ];
  console.log(`Conversão concluída: ${contagens.join(", ")}`);
  console.log(`  destino: ${DESTINO}`);
  return 0;
}

process.exit(main());
