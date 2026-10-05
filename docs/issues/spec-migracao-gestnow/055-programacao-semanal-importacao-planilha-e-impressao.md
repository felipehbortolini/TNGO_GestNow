---
id: ISSUE-055
title: "Importação da semana, planilha e relatório de impressão"
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
  - HU-082
  - HU-083
spec_decisions:
  - D10
  - D12
---

# Importação da semana, planilha e relatório de impressão

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D10, D12.
> Entrega 5 (Planejamento de campo e Programação Semanal), onda 11 (02 Programação Semanal (o app existente, adaptado)).
> Histórias: 82, 83. Bloqueada por: ISSUE-052.

## O que construir

Importar a semana pela planilha modelo do app, com conferência linha a linha
antes de gravar (fluxo genérico da plataforma com as regras do importador do
app). Baixar a semana em Excel com o mesmo conteúdo da planilha do app, e gerar
o relatório para imprimir (a folha do app) pela folha de impressão do Design
System.

## Critérios de aceite

- [ ] A importação confere linha a linha e só grava na confirmação, com as regras do app.
- [ ] O Excel da semana tem as mesmas colunas e abas da planilha do app.
- [ ] O relatório de impressão sai sem navegação e com o conteúdo da folha do app.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes portados da importação e da planilha; teste do relatório imprimível.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: importação, planilha e relatório (folha) do app.
