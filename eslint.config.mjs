// ═══════════════════════════════════════════════════════════════════════════
// ESLint 10 — configuração plana (flat config)
//
// Cobre as três linguagens do front: JavaScript, CSS e HTML. O back-end
// Python fica com ruff + ty (ver api/pyproject.toml).
//
//   npx eslint .          conferir
//   npx eslint . --fix    corrigir o que é automático
//
// Nota sobre a promessa "sem build": o ESLint é ferramenta de
// DESENVOLVIMENTO, não de execução. Nada em app/ é compilado, empacotado ou
// transformado — continua sendo servido exatamente como está no disco. O
// node_modules/ existe só na máquina de quem desenvolve e está no
// .gitignore; o pacote implantado não o contém.
// ═══════════════════════════════════════════════════════════════════════════

import js from "@eslint/js";
import css from "@eslint/css";
import html from "@html-eslint/eslint-plugin";
import htmlParser from "@html-eslint/parser";
import globals from "globals";

export default [
  // ─────────────────────────────────────────────────────────────────────
  // Ignorados
  // ─────────────────────────────────────────────────────────────────────
  {
    ignores: [
      "node_modules/**",
      "api/**", // Python — coberto por ruff/ty
      "app/lib/**", // Alpine.js e Alpine AJAX vendorizados, minificados
      "docs/referencia/**", // DaisyUI arquivado, referência inativa
      "docs/architecture-reviews/**", // documento gerado, não código do app
      "app/ds/assets/**",
    ],
  },

  // ─────────────────────────────────────────────────────────────────────
  // JavaScript do Design System — roda no navegador
  // ─────────────────────────────────────────────────────────────────────
  {
    // O JS de cada página (app/paginas/, o trio da tela) roda no mesmo
    // navegador e segue as mesmas regras do Design System.
    files: ["app/ds/**/*.js", "app/paginas/**/*.js"],
    ...js.configs.recommended,
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "script", // <script> clássico, não módulo
      globals: {
        ...globals.browser,
        // Alpine vem das libs vendorizadas em app/lib/.
        //
        // `icon`, `LOGO_FULL`, `logoAtom` e `TN` NÃO entram aqui de
        // propósito: quem os define são os próprios arquivos do DS, e
        // declará-los como global faria o ESLint acusar o arquivo que os
        // cria de estar redeclarando um global. Quem consome sempre passa
        // por `window.icon(...)` / `window.TN`, que é acesso a propriedade
        // e dispensa declaração.
        Alpine: "readonly",
      },
    },
    rules: {
      ...js.configs.recommended.rules,

      // Qualidade
      eqeqeq: ["error", "smart"],
      "no-var": "error",
      "prefer-const": "error",
      "no-unused-vars": ["error", { argsIgnorePattern: "^_" }],

      // Armadilhas
      "no-implied-eval": "error",
      "no-new-func": "error",
      "no-return-assign": "error",
      "no-throw-literal": "error",

      // ── Clean code, na parte que é mecânica ──────────────────────
      // Princípios de docs/CLEAN-CODE.md que dá para verificar sem
      // julgamento. O que exige leitura humana ficou fora daqui e está
      // na checklist de revisão.
      complexity: ["error", 12], // "funções devem fazer uma coisa"
      "max-params": ["error", 4], // "2 argumentos, idealmente"
      "max-depth": ["error", 4], // aninhamento que vira escada
      "no-param-reassign": "error", // use parâmetro com valor padrão
      "no-nested-ternary": "error", // obriga a ler de trás para frente
      "no-unneeded-ternary": "error",
      "no-else-return": "error",
      "no-lonely-if": "error",
      "no-useless-return": "error",
      "no-implicit-coercion": "error", // !!x, +x — diga o que quer dizer
      "default-case-last": "error",

      // O DS manipula innerHTML de propósito (é como os componentes
      // imperativos montam markup). O que protege contra injeção é o
      // TN.esc() aplicado a todo dado — não a proibição do innerHTML.
      // Ver docs/CONVENCOES.md.
      "no-console": ["warn", { allow: ["warn", "error"] }],
    },
  },

  // ─────────────────────────────────────────────────────────────────────
  // Scripts de ferramentaria — rodam no Node
  // ─────────────────────────────────────────────────────────────────────
  {
    files: ["scripts/**/*.mjs", "*.mjs"],
    ...js.configs.recommended,
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: globals.node,
    },
    rules: {
      ...js.configs.recommended.rules,
      eqeqeq: ["error", "smart"],
      "no-var": "error",
      "prefer-const": "error",
      "no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
      // Script de linha de comando existe para escrever no terminal.
      "no-console": "off",

      // Mesmas regras de clean code do Design System
      complexity: ["error", 12],
      "max-params": ["error", 4],
      "max-depth": ["error", 4],
      "no-param-reassign": "error",
      "no-nested-ternary": "error",
      "no-unneeded-ternary": "error",
      "no-else-return": "error",
      "no-lonely-if": "error",
      "no-useless-return": "error",
      "no-implicit-coercion": "error",
      "default-case-last": "error",
    },
  },

  // ─────────────────────────────────────────────────────────────────────
  // CSS do Design System
  // ─────────────────────────────────────────────────────────────────────
  {
    // O CSS de cada página (app/paginas/, o trio da tela) segue as mesmas
    // regras: só tokens, e escopado pela classe raiz da view.
    files: ["app/ds/**/*.css", "app/paginas/**/*.css"],
    plugins: { css },
    language: "css/css",
    languageOptions: {
      tolerant: true, // aceita sintaxe moderna que o parser ainda não conhece
    },
    rules: {
      "css/no-duplicate-imports": "error",
      "css/no-empty-blocks": "error",
      "css/no-invalid-at-rules": "error",
      // allowUnknownVariables porque a arquitetura do DS é justamente essa:
      // os tokens moram em tokens.css e são consumidos por shell.css e
      // patterns.css. A regra valida arquivo por arquivo e não enxerga
      // variável declarada em outro — sem esta opção acusa 99 falsos
      // positivos. Continua pegando o que interessa: nome de propriedade
      // inexistente e valor incompatível quando não há var() no meio.
      "css/no-invalid-properties": ["error", { allowUnknownVariables: true }],
      "css/no-invalid-at-rule-placement": "error",
      "css/no-duplicate-keyframe-selectors": "error",
      "css/no-unmatchable-selectors": "error",
      // A elevação no padrão Timenow vem da borda, e a hierarquia vem da
      // ordem do CSS. !important é sinal de que a especificidade saiu do
      // controle — vira aviso para aparecer em revisão, não erro cego.
      "css/no-important": "warn",
      // Fonte declarada sem pilha de fallback: se o arquivo não carregar,
      // o texto cai num serif genérico. Já aconteceu aqui com a Montserrat.
      "css/font-family-fallbacks": "warn",
    },
  },

  // ─────────────────────────────────────────────────────────────────────
  // Falsos positivos estruturais do @eslint/css
  //
  // Os dois casos abaixo são CSS válido que o parser da regra ainda não
  // entende. Ficam desligados por arquivo, com o motivo escrito; nenhuma
  // outra regra do CSS sai de cena. Mesmo caminho de ARG001 nos blueprints
  // e de allowUnknownVariables logo acima (docs/CLEAN-CODE.md).
  // ─────────────────────────────────────────────────────────────────────
  {
    // `color-mix(in srgb, var(--cor) calc(var(--intensidade) * 1%), transparent)`
    // é CSS Color 5: a porcentagem calculada dentro do color-mix é válida e é
    // como as tabelas de calor dos gráficos pintam a intensidade. O parser
    // lê o `calc()` como valor de `background` e reprova.
    files: ["app/ds/graficos/graficos-3.css"],
    rules: { "css/no-invalid-properties": "off" },
  },
  {
    // `margin` é descritor válido de `@page` (margem do papel); a regra
    // `no-invalid-at-rules` ainda não conhece os descritores de @page.
    files: ["app/ds/print.css"],
    rules: { "css/no-invalid-at-rules": "off" },
  },

  // ─────────────────────────────────────────────────────────────────────
  // HTML
  //
  // O preset `flat/recommended` mistura correção com formatação — traz
  // `indent`, `quotes`, `attrs-newline`, `require-closing-tags` e afins.
  // Ligá-lo inteiro rendeu 458 reprovações neste código, quase todas por
  // indentação de 2 espaços em vez de 4 e por `<img />`, que é válido em
  // HTML5. Mesmo princípio adotado no ruff: FORMATAÇÃO NÃO É LINTER.
  //
  // Por isso as regras são listadas uma a uma, só as de correção,
  // acessibilidade e compatibilidade. Se um dia entrar um formatador de
  // HTML no projeto, ele cuida do resto — e as duas coisas não brigam.
  // ─────────────────────────────────────────────────────────────────────

  // Shell e portão de login — documentos completos
  {
    files: ["app/index.html"],
    plugins: { "@html-eslint": html },
    languageOptions: { parser: htmlParser },
    rules: {
      // Estrutura de documento
      "@html-eslint/require-doctype": "error",
      "@html-eslint/require-lang": "error",
      "@html-eslint/require-title": "error",
      "@html-eslint/no-duplicate-in-head": "error",

      // Correção
      "@html-eslint/no-duplicate-attrs": "error",
      "@html-eslint/no-duplicate-id": "error",
      "@html-eslint/no-obsolete-attrs": "error",
      "@html-eslint/no-obsolete-tags": "error",
      "@html-eslint/no-ineffective-attrs": "error",
      "@html-eslint/require-li-container": "error",

      // Acessibilidade — reforça o que a auditoria do axe cobrou
      "@html-eslint/require-img-alt": "error",
      "@html-eslint/require-button-type": "error",
      "@html-eslint/no-multiple-h1": "error",
      "@html-eslint/no-accesskey-attrs": "error",
      "@html-eslint/no-heading-inside-button": "error",
      "@html-eslint/require-frame-title": "error",

      // Segurança — target="_blank" sem rel deixa a página aberta ao
      // window.opener da aba de destino
      "@html-eslint/no-target-blank": "error",

      "@html-eslint/use-baseline": "warn",
    },
  },

  // Fragmentos — views, componentes e o portão de login
  //
  // NÃO são documentos: por contrato não têm <html>, <head>, <body> nem
  // doctype (Regra 2 do contrato visual). As três regras de estrutura de
  // documento ficam de fora, senão reprovariam todo fragmento válido.
  //
  // api/src/templates/ fica de fora por inteiro: são templates Jinja2, e
  // {% if %} / {{ var }} não são HTML — o parser não tem como analisar.
  // Aquele conteúdo é coberto pelo teste de renderização, que confere o
  // HTML depois de produzido.
  {
    files: ["app/_views/**/*.html", "app/_components/**/*.html", "app/login.html"],
    plugins: { "@html-eslint": html },
    languageOptions: { parser: htmlParser },
    rules: {
      "@html-eslint/no-duplicate-attrs": "error",
      "@html-eslint/no-duplicate-id": "error",
      "@html-eslint/no-obsolete-attrs": "error",
      "@html-eslint/no-obsolete-tags": "error",
      "@html-eslint/no-ineffective-attrs": "error",
      "@html-eslint/require-li-container": "error",

      "@html-eslint/require-img-alt": "error",
      "@html-eslint/require-button-type": "error",
      "@html-eslint/no-multiple-h1": "error",
      "@html-eslint/no-accesskey-attrs": "error",
      "@html-eslint/no-heading-inside-button": "error",

      "@html-eslint/no-target-blank": "error",

      "@html-eslint/use-baseline": "warn",
    },
  },
];
