---
id: ISSUE-052
title: "Fluxo de cinco passos: validar com fiscal, realizado por turno, aprovação do fiscal e publicação"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 5
onda: 11
blocked_by:
  - ISSUE-051
blocks:
  - ISSUE-053
  - ISSUE-055
  - ISSUE-056
labels:
  - ready-for-agent
source_requirements:
  - HU-073
  - HU-074
  - HU-075
  - HU-076
  - HU-077
spec_decisions:
  - D10
  - D7
---

# Fluxo de cinco passos: validar com fiscal, realizado por turno, aprovação do fiscal e publicação

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D10, D7.
> Entrega 5 (Planejamento de campo e Programação Semanal), onda 11 (02 Programação Semanal (o app existente, adaptado)).
> Histórias: 73, 74, 75, 76, 77. Bloqueada por: ISSUE-051.

## O que construir

Porta o fluxo de cinco passos do app. O Planejador valida a programação e
define o fiscal. Encarregado ou Fornecedor lançam o realizado por turno (dia e
noite), com "= previsto" e "copiar a semana", e justificativa quando o desvio
passa do limite do parâmetro. O Fiscal aprova o realizado das atividades sob a
sua responsabilidade, ou reabre com motivo. O Planejador publica as atividades
validadas, encerrando a edição da semana.

A matriz mostra, em cada atividade, o botão com a próxima ação de quem está
olhando e um menu só com o que o perfil pode fazer. Situação por atividade, PPC
por atividade e aderência ponderada do conjunto, com as faixas alta, média e
baixa, exatamente como no app.

## Critérios de aceite

- [ ] Os testes do fluxo do app estão portados e verdes.
- [ ] Cada transição só é aceita do papel certo no projeto; os demais recebem 403.
- [ ] Desvio acima do limite sem justificativa é recusado.
- [ ] O botão da próxima ação e o menu mudam com o perfil.
- [ ] PPC e aderência dão os mesmos números do app para os mesmos dados.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A demonstração da programação vem da carga de demonstração do app, convertida para as tabelas, num projeto do portfólio, com as datas deslocadas para hoje.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes portados do app e testes de rota das permissões por papel.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: blueprints e templates de atividade (validar, realizado, aprovar) do app e os cálculos de PPC e aderência.
