---
id: ISSUE-014
title: "Biblioteca de gráficos 1: motor comum com drill e curvas, barras, Pareto e relógios"
status: in-progress
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 2
onda: 4
blocked_by:
  - ISSUE-010
blocks:
  - ISSUE-015
  - ISSUE-017
labels:
  - ready-for-agent
source_requirements:
  - HU-062
  - HU-084
  - HU-093
spec_decisions:
  - D11
---

# Biblioteca de gráficos 1: motor comum com drill e curvas, barras, Pareto e relógios

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D11.
> Entrega 2 (Plataforma no ar), onda 4 (Serviços transversais).
> Histórias: 62, 84, 93. Bloqueada por: ISSUE-010.

## O que construir

Nasce a biblioteca de gráficos do Design System, um arquivo por tipo de
visual, em SVG e JavaScript puro, sem dependência externa.

Primeiro sai o **motor comum**: tooltip escuro, legenda, botões de ano,
animação de entrada, leitura das cores dos tokens em tempo de execução e o
drill ano, mês e semana do app de Programação Semanal. Sobre ele são portados
os visuais desta issue: **Curva S Linha**, **Curva S Barra e Linha**,
**Comparativo de Barras Entre períodos**, **Pareto** e **Relógios de
Indicadores**. Os dados fictícios dos originais saem.

Contrato de dados: o gráfico lê os dados de atributo `data-*` (JSON escapado
pelo Jinja), nunca de `<script>` no fragmento; o servidor manda quantidades, e
o gráfico agrega por período quando o resumo não é soma.

O styleguide de gráficos, em `docs/`, é uma página HTML que carrega a
biblioteca do próprio `app/ds/` e mostra cada visual com dados de exemplo,
explicando o contrato de dados e o uso. As issues 015 e 016 acrescentam os
seus visuais nela.

## Critérios de aceite

- [ ] Os cinco visuais renderizam no styleguide com a mesma aparência dos originais preservados em `docs/referencia/graficos/`.
- [ ] Nenhuma cor fixa no código dos gráficos: todas vêm dos tokens.
- [ ] O drill ano, mês e semana funciona nas curvas.
- [ ] Os dados chegam por `data-*`; nenhum fragmento tem `<script>`.
- [ ] Abrir o styleguide não gera erro no console.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Abrir o styleguide e comparar cada visual com o original; lint de JS verde.
`npm run verificar` passa.

## Decisões em aberto

Nenhuma.

## Notas

Fontes: `Graficos HTML` (cópia em `docs/referencia/graficos/`) e `ds/charts.js`
do app de Programação Semanal (motor de drill e a lição de agregação). Fato
verificado: a paleta da coletânea já é a do Design System (D11). Histórias
listadas são as que dependem destes visuais.
