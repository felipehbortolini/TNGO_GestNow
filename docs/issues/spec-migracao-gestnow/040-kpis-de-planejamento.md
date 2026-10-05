---
id: ISSUE-040
title: "KPIs de planejamento por período e por área"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 4
onda: 8
blocked_by:
  - ISSUE-039
blocks:
  - ISSUE-079
  - ISSUE-081
labels:
  - ready-for-agent
source_requirements:
  - HU-063
spec_decisions:
  - D6
  - D11
---

# KPIs de planejamento por período e por área

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D6, D11.
> Entrega 4 (Custo e avanço físico), onda 8 (02 Planejamento, avanço físico).
> Histórias: 63. Bloqueada por: ISSUE-039.

## O que construir

A tela **KPIs** do Planejamento mostra SPI físico, avanço previsto x real e
desvio (p.p.) por período e por área, com a referência de gestão abaixo de cada
valor. O avanço por área é calculado da EAP, sem lançamento próprio. Entram
também os indicadores da EAP que a tela do protótipo mostrava (término vencido
e SMs a incorporar).

## Critérios de aceite

- [ ] SPI físico = real ÷ previsto acumulados, com teste de fronteira.
- [ ] O avanço por área vem da EAP e bate com a árvore.
- [ ] O oráculo afirma SPI de 0,94 em 25/09/2026.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo e o oráculo do SPI.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `kpis.html` do Planejamento; README, "02 Planejamento". O botão Análise do período desta tela chega na ISSUE-081.
