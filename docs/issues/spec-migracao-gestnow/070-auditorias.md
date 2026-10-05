---
id: ISSUE-070
title: "Auditorias"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 7
onda: 14
blocked_by:
  - ISSUE-068
blocks:
  - ISSUE-071
labels:
  - ready-for-agent
source_requirements:
  - HU-118
spec_decisions:
  - D9
---

# Auditorias

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D9.
> Entrega 7 (Qualidade, HSE e Configurações), onda 14 (06 Qualidade).
> Histórias: 118. Bloqueada por: ISSUE-068.

## O que construir

A tela **Auditorias** mostra o programa (contratada, fornecedor, interna) com
escopo, critérios, auditado, auditor líder e data. Data vencida sem resultado
é **atrasada**; **reprogramação** exige justificativa e fica registrada. O
resultado registra itens verificados e conformes e as constatações (Não
conformidade, Observação, Oportunidade de melhoria); **cada não conformidade
abre RNC** (origem Auditoria), e não pode haver mais NC que itens não
conformes.

## Critérios de aceite

- [ ] Auditoria vencida sem resultado aparece atrasada pela data de hoje.
- [ ] Reprogramação sem justificativa é recusada.
- [ ] Cada NC abre uma RNC na mesma transação, e NC acima dos itens não conformes é recusada.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (atraso, reprogramação e RNC por NC).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `auditorias.html` da Qualidade; README, regras de auditorias.
