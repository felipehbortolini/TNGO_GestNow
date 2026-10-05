# Pendências de fonte

> Documento do orquestrador. Lista, por issue, os critérios de aceite que
> **não puderam ser cumpridos** porque dependem de pastas de origem que não
> estão no repositório do GitHub. A issue correspondente fecha como `done` com
> estes critérios ainda `[ ]` (decisão da execução, pendente de revisão do
> dono, no Histórico de decisões da spec).

## Fontes que faltam no repositório

| Fonte | O que ela destrava |
|---|---|
| `Sistema/data` (os 11 `mock-*.js`) e `Sistema/js` (`api.js`, `regras.js`) | Carga de demonstração de cada módulo (`scripts/converter_mocks.mjs` lê `../Sistema/data`), números do oráculo e conferência exata das fórmulas |
| `Sistema/js/i18n/en.js` | Catálogo em inglês (ISSUE-087 e 088) |
| `Timenow - Programação Semanal` (código e testes do app) | Portar o módulo Programação Semanal (ISSUE-051 a 056, 077 e 078) |

## Como conciliar quando as fontes chegarem

1. Colocar `Sistema/` e `Timenow - Programação Semanal/` ao lado da raiz do
   repositório (a estrutura original: `Timenow - Gestao de Projetos/{Sistema, Timenow - GestNow, ...}`).
2. Para cada issue da tabela abaixo: acrescentar as coleções da sua parte ao
   `scripts/converter_mocks.mjs`, gerar o JSON de carga, escrever o `seed.py` do
   módulo e as afirmações do oráculo, marcar os critérios e remover a linha.
3. Rodar a porta de qualidade e a suíte completa.

## Pendências por issue

| Issue | Critérios pendentes | Fonte necessária |
|---|---|---|
