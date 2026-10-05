---
id: ISSUE-091
title: "Exportações tela a tela, acessibilidade e roteiro manual"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 9
onda: 19
blocked_by:
  - ISSUE-090
blocks:
  - ISSUE-092
labels:
  - ready-for-agent
source_requirements:
  - HU-136
  - HU-137
  - HU-138
spec_decisions:
  - D12
  - D1
---

# Exportações tela a tela, acessibilidade e roteiro manual

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D12, D1.
> Entrega 9 (Produto final), onda 19 (Validação final e Azure).
> Histórias: 136, 137, 138. Bloqueada por: ISSUE-090.

## O que construir

O **inventário de exportações** da D12 é conferido tela a tela e registrado em
`docs/` (cada tela, cada botão Excel e PDF, o teste que o cobre), e um teste
automatizado por tela confere que o Excel abre, tem as colunas da tabela e os
KPIs com referência, e que a versão imprimível renderiza sem navegação.

A passada de **acessibilidade** segue o `ACESSIBILIDADE.md` do Padrão
(teclado, foco, contraste, rótulos, ARIA), com as correções feitas aqui.

O **roteiro manual de aceite** para o dono do produto fica em `docs/`: passo a
passo por módulo, com o que fazer e o que deve aparecer, incluindo a revisão
do modelo de dados (Q30) e das divergências (Q31).

## Critérios de aceite

- [ ] O inventário lista todas as telas, e cada botão Excel e PDF tem teste.
- [ ] Os critérios de acessibilidade do Padrão passam.
- [ ] O roteiro manual cobre todos os módulos e as revisões pendentes do dono.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Rodar os testes de exportação por tela e a porta de qualidade; conferir o roteiro contra a lista de navegação.

## Decisões em aberto

Nenhuma.

## Notas

Testing Decisions da spec: "Exportações".
