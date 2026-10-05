---
id: ISSUE-049
title: "Punch list: itens, fluxo com verificação e bloqueio de sistema"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 5
onda: 10
blocked_by:
  - ISSUE-019
blocks:
  - ISSUE-050
labels:
  - ready-for-agent
source_requirements:
  - HU-068
  - HU-069
spec_decisions:
  - D7
  - D9
  - D5a
---

# Punch list: itens, fluxo com verificação e bloqueio de sistema

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D7, D9, D5a.
> Entrega 5 (Planejamento de campo e Programação Semanal), onda 10 (02 Planejamento, campo).
> Histórias: 68, 69. Bloqueada por: ISSUE-019.

## O que construir

A tela **Punch list**, aba Lista, registra itens com numeração
`PL-TN-2026-0001`, hierarquia Área, Sistema, Subsistema e TAG, disciplina,
categoria (A impede o marco seguinte; B fecha até o aceite definitivo; C
conforme acordo), marco vinculado, origem, descrição, empresa executante,
responsável, prazo, identificado por, data de abertura e fotos.

Fluxo: Aberto, Em tratamento, Aguardando verificação, Fechado, voltando para
Em tratamento quando a verificação reprova; Cancelado exige justificativa. O
fechamento exige evidência (anexo) e verificação por pessoa diferente do
executante (segregação). **Sistema com item A aberto fica bloqueado** para o
marco vinculado.

Cada item gera uma ação na Central (origem Punch list) pela costura, e o
status do item e o da ação ficam sincronizados nos dois sentidos. Modais Novo
item, Fechamento com verificação, Filtros e Importação Excel.

## Critérios de aceite

- [ ] Fechamento sem anexo é recusado, e o verificador igual ao executante recebe 403.
- [ ] Item A aberto bloqueia o sistema para o marco vinculado.
- [ ] Item e ação ficam sincronizados nos dois sentidos.
- [ ] A importação recusa linhas inválidas e grava as válidas só na confirmação.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (fluxo, segregação, bloqueio, sincronização e importação) e de rota (403).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `punch-list.html`, `GI.api.planejamento.punch`; README, "Punch list: regras".
