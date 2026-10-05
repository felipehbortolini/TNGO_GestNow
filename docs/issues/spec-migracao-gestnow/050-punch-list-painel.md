---
id: ISSUE-050
title: "Punch list: painel de completação"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 5
onda: 10
blocked_by:
  - ISSUE-049
blocks:
  - ISSUE-079
labels:
  - ready-for-agent
source_requirements:
  - HU-070
spec_decisions:
  - D11
---

# Punch list: painel de completação

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D11.
> Entrega 5 (Planejamento de campo e Programação Semanal), onda 10 (02 Planejamento, campo).
> Histórias: 70. Bloqueada por: ISSUE-049.

## O que construir

A aba **Painel** da Punch list mostra os itens abertos por categoria, a curva
de abertura e fechamento acumulados (burndown), o tempo em aberto nas faixas
dos parâmetros (até 7, de 8 a 30 e mais de 30 dias), os itens por disciplina,
sistema e empresa, o % de sistemas liberados por marco e o alerta dos sistemas
bloqueados.

## Critérios de aceite

- [ ] As faixas de aging têm teste de fronteira com a data injetada.
- [ ] O % de sistemas liberados por marco tem teste da fórmula.
- [ ] O burndown bate com as datas de abertura e fechamento dos itens.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo do painel.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `GI.api.planejamento.resumoPunch`.
