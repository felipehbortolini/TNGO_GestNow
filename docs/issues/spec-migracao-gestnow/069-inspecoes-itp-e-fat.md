---
id: ISSUE-069
title: "Inspeções e ITP, com o FAT do diligenciamento"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 7
onda: 14
blocked_by:
  - ISSUE-068
  - ISSUE-061
blocks:
  - ISSUE-071
labels:
  - ready-for-agent
source_requirements:
  - HU-104
  - HU-117
spec_decisions:
  - D9
---

# Inspeções e ITP, com o FAT do diligenciamento

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D9.
> Entrega 7 (Qualidade, HSE e Configurações), onda 14 (06 Qualidade).
> Histórias: 104, 117. Bloqueada por: ISSUE-068, ISSUE-061.

## O que construir

A tela **Inspeções e ITP** mostra os planos de inspeção e testes (pontos H, W e
R com critério, referência e responsável; revisão e aprovação do cliente) e os
registros de inspeção por ponto (filtros por ITP, resultado e tipo).

Regras: ponto H (espera) só libera a atividade seguinte com o registro
aprovado; ponto W (testemunho) exige o cliente notificado com a antecedência
mínima do parâmetro, e notificação ausente ou menor gera aviso; ponto R
(revisão de registros). Inspeção só em ITP aprovado pelo cliente; nova revisão
do ITP volta a pedir aprovação e não pode retirar ponto que já tem inspeção.
Ressalva conta como aprovada; **reprovação abre RNC** automaticamente, com a
severidade e a contenção do próprio registro, na mesma transação.

Ligação com Suprimentos: o **FAT realizado** no diligenciamento registra a
inspeção (origem Suprimentos); FAT reprovado não conclui o marco e exige nova
previsão do reteste.

## Critérios de aceite

- [ ] Inspeção em ITP não aprovado é recusada, e a revisão do ITP não retira ponto com inspeção.
- [ ] A antecedência da notificação gera aviso pela fronteira do parâmetro.
- [ ] Reprovação abre a RNC na mesma transação.
- [ ] FAT realizado grava a inspeção; FAT reprovado não conclui o marco.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (ITP, pontos, reprovação e FAT).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `inspecoes.html` da Qualidade e o FAT do diligenciamento (`inspecoesQualidade`, origem Suprimentos); README, regras do ITP.
