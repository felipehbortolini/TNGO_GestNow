---
id: ISSUE-028
title: "Painel de lições"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 3
onda: 6
blocked_by:
  - ISSUE-027
blocks: []
labels:
  - ready-for-agent
source_requirements:
  - HU-130
spec_decisions:
  - D11
---

# Painel de lições

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D11.
> Entrega 3 (Central de Ações e Governança), onda 6 (08 Governança).
> Histórias: 130. Bloqueada por: ISSUE-027.

## O que construir

A aba **Painel** das lições mostra lições por fase e por área (a repetir e a
evitar), as publicadas nos últimos dias do parâmetro, "Dias desde a última
lição" com alerta pelo parâmetro (90 dias), lições por situação, taxa de
reuso, projetos sem registro no período e as lições mais reusadas.

## Critérios de aceite

- [ ] "Dias desde a última lição" e o alerta têm teste de fronteira no parâmetro.
- [ ] Taxa de reuso e projetos sem registro têm teste da fórmula.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo dos indicadores com a data injetada.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `GI.api.governanca.painelLicoes`.
