---
id: ISSUE-086
title: "Relatório: Excel, Imprimir / PDF e Alterar período"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 8
onda: 17
blocked_by:
  - ISSUE-085
blocks:
  - ISSUE-087
labels:
  - ready-for-agent
source_requirements:
  - HU-039
spec_decisions:
  - D12
---

# Relatório: Excel, Imprimir / PDF e Alterar período

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D12.
> Entrega 8 (Visão executiva), onda 17 (Início, análise do período e relatório gerencial).
> Histórias: 39. Bloqueada por: ISSUE-085.

## O que construir

A view do relatório ganha os botões **Imprimir / PDF** (impressão do navegador
com as folhas A4), **Excel** (indicadores e tabelas de todas as folhas, mais as
abas "Análises do período" e "Desvios negativos e comentários") e **Alterar
período** (volta ao modal com as escolhas atuais).

## Critérios de aceite

- [ ] O Excel tem uma aba por folha e as abas de análises e de desvios com comentários.
- [ ] Imprimir sai uma folha por página, sem navegação, com os fundos preservados.
- [ ] Alterar período reabre o modal com as escolhas atuais.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Teste que abre o Excel do relatório com openpyxl e confere as abas; teste da versão imprimível.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: README, "Relatório gerencial" (Impressão e Excel).
