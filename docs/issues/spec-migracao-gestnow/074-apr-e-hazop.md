---
id: ISSUE-074
title: "Análises de risco APR e HAZOP"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 7
onda: 15
blocked_by:
  - ISSUE-019
blocks:
  - ISSUE-075
labels:
  - ready-for-agent
source_requirements:
  - HU-123
spec_decisions:
  - D9
---

# Análises de risco APR e HAZOP

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D9.
> Entrega 7 (Qualidade, HSE e Configurações), onda 15 (07 HSE).
> Histórias: 123. Bloqueada por: ISSUE-019.

## O que construir

A tela **Análises de risco** registra os estudos (tipo APR/JSA ou HAZOP, área,
data, participantes) e as recomendações (responsável, prazo, situação). Cada
recomendação vira ação na Central pela costura (origem HSE), com o link de
volta para o estudo, e a situação fica sincronizada. O indicador de
recomendações fechadas ÷ emitidas fica disponível para o painel.

## Critérios de aceite

- [ ] A recomendação cria a ação na Central com link de volta ao estudo.
- [ ] Recomendação e ação ficam sincronizadas.
- [ ] Recomendações fechadas ÷ emitidas tem teste da fórmula.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (recomendação e sincronização) e de cálculo.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `analises-risco.html` e `js/pages/hse/analises-risco.js`.
