---
id: ISSUE-056
title: "Dashboard da programação"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 5
onda: 11
blocked_by:
  - ISSUE-052
blocks: []
labels:
  - ready-for-agent
source_requirements:
  - HU-084
spec_decisions:
  - D10
  - D11
---

# Dashboard da programação

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D10, D11.
> Entrega 5 (Planejamento de campo e Programação Semanal), onda 11 (02 Programação Semanal (o app existente, adaptado)).
> Histórias: 84. Bloqueada por: ISSUE-052.

## O que construir

O **dashboard** do app, com os gráficos da biblioteca: curva S do avanço,
previsto x realizado, aderência por contratada com drill, rankings, mapa de
calor dia x frente, turnos e gargalos, com os filtros do app. O servidor manda
quantidades, e o gráfico agrega por período quando o resumo não é soma.

## Critérios de aceite

- [ ] Os números do dashboard são os do app para os mesmos dados (testes de indicadores portados).
- [ ] O drill da aderência por contratada funciona.
- [ ] O fornecedor vê o dashboard só da própria empresa.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes portados dos indicadores e revisão de tela comparando com o app.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: blueprint e templates do dashboard do app, `indicadores` e `ds/charts.js` do app.
