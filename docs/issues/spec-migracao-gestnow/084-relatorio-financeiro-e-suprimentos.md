---
id: ISSUE-084
title: "Relatório: folhas Financeiro (com a linha de tendência) e Suprimentos"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 8
onda: 17
blocked_by:
  - ISSUE-083
blocks:
  - ISSUE-085
labels:
  - ready-for-agent
source_requirements:
  - HU-041
spec_decisions:
  - D12
  - D6
---

# Relatório: folhas Financeiro (com a linha de tendência) e Suprimentos

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D12, D6.
> Entrega 8 (Visão executiva), onda 17 (Início, análise do período e relatório gerencial).
> Histórias: 41. Bloqueada por: ISSUE-083.

## O que construir

Folha **Financeiro**: BAC, realizado acumulado e do mês, valor agregado (EV e
PV), CPI e SPI de custo, projeção no término e VAC (sobrecusto na família
`erro`), contingência consumida; Curva S financeira com a **linha de
tendência** (a função da ISSUE-042, calculada no próprio mês, sem dado
posterior ao período) e o valor agregado de 6 meses; análise do período; EAC
por pacote (nível 1, R$ mil, mapa de calor).

Folha **Suprimentos**: aderência ao plano, pacotes adjudicados, saving, OTD,
pedidos críticos e emitidos até o corte; curva de contratação e pedidos
críticos (até 4) ao lado da análise; marcos realizados no período e
adjudicações e entregas previstas no horizonte (até 5 cada; semanal: 4 semanas
seguintes; mensal: mês seguinte).

## Critérios de aceite

- [ ] A linha de tendência não usa dado posterior ao período (teste).
- [ ] O horizonte de previstos segue o tipo do relatório (teste).
- [ ] As folhas mostram os mesmos números das telas no mesmo corte.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo das folhas.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: README, "Relatório gerencial: regras" (folhas 3 e 4).
