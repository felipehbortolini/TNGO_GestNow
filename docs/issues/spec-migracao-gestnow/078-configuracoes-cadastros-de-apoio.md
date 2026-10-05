---
id: ISSUE-078
title: "Cadastros de apoio: empresas, pessoas, projetos, sistemas, unidades e locais"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 7
onda: 16
blocked_by:
  - ISSUE-054
blocks:
  - ISSUE-087
labels:
  - ready-for-agent
source_requirements:
  - HU-135
  - HU-080
spec_decisions:
  - D8
  - D10
---

# Cadastros de apoio: empresas, pessoas, projetos, sistemas, unidades e locais

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D8, D10.
> Entrega 7 (Qualidade, HSE e Configurações), onda 16 (Configurações).
> Histórias: 135, 80. Bloqueada por: ISSUE-054.

## O que construir

A tela **Configurações > Cadastros** mantém os cadastros que alimentam os
formulários: empresas, pessoas, projetos (código, nome, cliente, orçamento,
datas, padrões de numeração e as notas de ponderação), sistemas (hierarquia da
punch list), unidades, locais e disciplinas. Exclusão de cadastro em uso é
recusada com a mensagem de onde ele é usado. Um **projeto novo** nasce com a
configuração padrão da Programação Semanal (função da ISSUE-054).

## Critérios de aceite

- [ ] Cada cadastro tem inclusão, edição e exclusão com validação no servidor.
- [ ] Excluir cadastro em uso é recusado com a mensagem.
- [ ] O projeto novo já tem a configuração padrão da programação.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (validação, exclusão em uso e projeto novo).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `GI.api.cadastros` e `mock-base` do protótipo; cadastros de apoio do app de Programação Semanal.
