---
id: ISSUE-090
title: "Varredura de todas as telas nas três larguras"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 9
onda: 19
blocked_by:
  - ISSUE-089
blocks:
  - ISSUE-091
labels:
  - ready-for-agent
source_requirements:
  - HU-005
  - HU-006
  - HU-020
spec_decisions:
  - D2
  - D3
---

# Varredura de todas as telas nas três larguras

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D2, D3.
> Entrega 9 (Produto final), onda 19 (Validação final e Azure).
> Histórias: 5, 6, 20. Bloqueada por: ISSUE-089.

## O que construir

A varredura de telas vira teste automatizado com Playwright (precedente: o
`_dev/crawl.py` do protótipo, preservado em `docs/referencia/prototipo/`): abre
cada tela da lista de navegação em 1280, 1100 e 760 px, com os perfis Admin,
Visualizador e Fornecedor, e reprova console com erro, rolagem horizontal,
barra lateral ausente ou oculta, tela sem estilo próprio (classe raiz e CSS da
página aplicados) e link quebrado. Playwright e o navegador dele entram como
dependência de desenvolvimento.

O que a varredura encontrar é corrigido nesta issue.

## Critérios de aceite

- [ ] A varredura cobre todas as telas da lista de navegação nas três larguras e nos três perfis.
- [ ] Nenhuma tela reprova em console, rolagem, barra lateral, estilo ou link.
- [ ] O fornecedor só alcança as telas da Programação Semanal.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Rodar a varredura (comando documentado no README) e a porta de qualidade.

## Decisões em aberto

Nenhuma.

## Notas

Testing Decisions da spec: "Varredura de telas".
