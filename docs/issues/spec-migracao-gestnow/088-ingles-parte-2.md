---
id: ISSUE-088
title: "Inglês, parte 2: Planejamento, Programação Semanal, Suprimentos, Riscos, Qualidade, HSE, Configurações e relatório"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 9
onda: 18
blocked_by:
  - ISSUE-087
blocks:
  - ISSUE-089
labels:
  - ready-for-agent
source_requirements:
  - HU-017
spec_decisions:
  - D13
---

# Inglês, parte 2: Planejamento, Programação Semanal, Suprimentos, Riscos, Qualidade, HSE, Configurações e relatório

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D13.
> Entrega 9 (Produto final), onda 18 (Idioma).
> Histórias: 17. Bloqueada por: ISSUE-087.

## O que construir

Completa a tradução com o catálogo da parte 1: Planejamento, Programação
Semanal, Suprimentos, Riscos, Qualidade, HSE, Configurações e o relatório
gerencial, inclusive gráficos, Excel e PDF. Um teste de completude garante que
toda chave usada tem tradução em EN.

## Critérios de aceite

- [ ] Toda chave do catálogo tem tradução em EN (teste de completude).
- [ ] Em EN, nenhuma tela mostra texto de interface em português (dados à parte).
- [ ] O relatório gerencial sai em EN, inclusive Excel e impressão.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Teste de completude do catálogo e revisão de tela em EN.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: dicionário `en.js` do protótipo; a Programação Semanal, que no app era só em português, ganha as chaves novas.
