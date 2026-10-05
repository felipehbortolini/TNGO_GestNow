---
id: ISSUE-079
title: "Início do projeto: indicador-chave por módulo e pontos de atenção"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 8
onda: 17
blocked_by:
  - ISSUE-020
  - ISSUE-026
  - ISSUE-035
  - ISSUE-040
  - ISSUE-042
  - ISSUE-050
  - ISSUE-063
  - ISSUE-066
  - ISSUE-071
  - ISSUE-075
blocks:
  - ISSUE-080
labels:
  - ready-for-agent
source_requirements:
  - HU-032
  - HU-033
spec_decisions:
  - D6
  - D11
  - D9
---

# Início do projeto: indicador-chave por módulo e pontos de atenção

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D6, D11, D9.
> Entrega 8 (Visão executiva), onda 17 (Início, análise do período e relatório gerencial).
> Histórias: 32, 33. Bloqueada por: ISSUE-020, ISSUE-026, ISSUE-035, ISSUE-040, ISSUE-042, ISSUE-050, ISSUE-063, ISSUE-066, ISSUE-071, ISSUE-075.

## O que construir

O **Início** mostra o contexto do projeto em etiquetas na barra da página
(projeto, data de referência, que é hoje, orçamento e término) com a
exportação à direita; um **indicador-chave por módulo**, clicável, com a
referência de gestão abaixo do valor (ações atrasadas, SPI, CPI, pedidos
críticos, riscos críticos, RNC abertas, dias sem afastamento, mudanças
aguardando comitê); os **pontos de atenção** calculados (ações mais atrasadas,
pedidos com folga negativa, sistemas bloqueados por item A, revisão de risco
vencida, claim fora do prazo, HiPo no mês e os demais alertas que o protótipo
mostra); e os cards dos 8 módulos.

Cada número vem da fachada do módulo dono, nunca de tabela de outro módulo, e
é calculado na hora.

## Critérios de aceite

- [ ] Cada card mostra o mesmo número da tela do módulo e leva a ela com o filtro certo.
- [ ] Os pontos de atenção saem calculados com a data injetada (teste).
- [ ] O oráculo afirma, no Início do projeto 1: 8 ações atrasadas, SPI 0,94, CPI 0,96, 3 pedidos críticos, 2 riscos críticos, 4 RNC abertas e 263 dias sem afastamento.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada do resumo (pelas fachadas dos módulos) e o oráculo do Início.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `index.html` e `js/pages/home.js`, `GI.api.resumoHome`; README, "Home".
