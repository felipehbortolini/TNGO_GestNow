---
id: ISSUE-053
title: "Pedidos de alteração e governança da programação"
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
  - HU-078
  - HU-085
spec_decisions:
  - D10
  - D5b
---

# Pedidos de alteração e governança da programação

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D10, D5b.
> Entrega 5 (Planejamento de campo e Programação Semanal), onda 11 (02 Programação Semanal (o app existente, adaptado)).
> Histórias: 78, 85. Bloqueada por: ISSUE-052.

## O que construir

O fornecedor pede alteração de atividade já validada, e o planejador aplica ou
recusa, com rastreabilidade, como no app. A tela de **governança** mostra o
painel por contratada e semana, os pedidos e a trilha de auditoria (agora a
auditoria única do GestNow, filtrada pela programação).

## Critérios de aceite

- [ ] Pedido aplicado ou recusado fica na trilha com antes e depois.
- [ ] Os indicadores da governança dão os mesmos números do app para os mesmos dados.
- [ ] O fornecedor só vê os próprios pedidos.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A demonstração da programação vem da carga de demonstração do app, convertida para as tabelas, num projeto do portfólio, com as datas deslocadas para hoje.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.

## Verificação

Testes portados do app para pedidos e governança.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: blueprint e templates de governança do app (painel, pedidos, trilha).
