---
id: ISSUE-082
title: "Análise do período de 05, 06, 07 e do Portfólio"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 8
onda: 17
blocked_by:
  - ISSUE-081
  - ISSUE-066
  - ISSUE-071
  - ISSUE-075
blocks:
  - ISSUE-083
labels:
  - ready-for-agent
source_requirements:
  - HU-042
  - HU-044
spec_decisions:
  - D6
  - D8
---

# Análise do período de 05, 06, 07 e do Portfólio

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D6, D8.
> Entrega 8 (Visão executiva), onda 17 (Início, análise do período e relatório gerencial).
> Histórias: 42, 44. Bloqueada por: ISSUE-081, ISSUE-066, ISSUE-071, ISSUE-075.

## O que construir

O mesmo modal entra em 05 Painel de riscos, 06 Painel da qualidade e 07 Painel
HSE. Em 05 e 07, só o texto é obrigatório. No 06, os desvios são listados sem
comentário obrigatório: RNC com prazo de tratamento vencido, aprovação em
inspeções e conformidade em auditorias abaixo da meta e auditorias atrasadas.

A análise do **Portfólio** existe para cada módulo, com projeto nulo, escrita
pelo PMO sobre os números consolidados.

## Critérios de aceite

- [ ] Em 05 e 07 só o texto é exigido; no 06, os desvios aparecem sem exigir comentário.
- [ ] A análise do Portfólio grava com projeto nulo e não se mistura com a dos projetos.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada das regras por módulo e do Portfólio.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: README, "Análise do período por módulo: regras" e "Gestão de portfólio".
