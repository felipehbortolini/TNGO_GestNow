---
id: ISSUE-063
title: "Painel de suprimentos"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 6
onda: 12
blocked_by:
  - ISSUE-062
blocks:
  - ISSUE-079
  - ISSUE-081
labels:
  - ready-for-agent
source_requirements:
  - HU-106
spec_decisions:
  - D11
---

# Painel de suprimentos

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D11.
> Entrega 6 (Suprimentos e Riscos), onda 12 (04 Suprimentos).
> Histórias: 106. Bloqueada por: ISSUE-062.

## O que construir

O **Painel de suprimentos** mostra os 9 KPIs do protótipo (entre eles aderência
ao plano de compras, saving sobre a estimativa e de negociação, OTD, pedidos
críticos e avanço do MAS), a curva de contratação (pacotes adjudicados
acumulados, plano x realizado), o avanço físico de suprimentos (Curva S do MAS:
linha de base, real e tendência), o saving acumulado, os pacotes por etapa e os
pedidos por folga em relação ao ROS. As fórmulas seguem a tabela de
indicadores do README.

## Critérios de aceite

- [ ] Cada indicador do painel tem teste da fórmula.
- [ ] O oráculo afirma aderência de 92,9%, saving de 5,2% sobre a estimativa e 4,7% na negociação, e avanço de 90,9% x 97,3% (índice 0,93).
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo e o oráculo de suprimentos.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `painel.html` de Suprimentos, `GI.api.suprimentos.indicadores`; README, indicadores de Suprimentos. O botão Análise do período chega na ISSUE-081.
