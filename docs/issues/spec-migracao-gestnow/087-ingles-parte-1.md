---
id: ISSUE-087
title: "Inglês, parte 1: catálogo no servidor, seletor PT | EN, shell, Início, Central, Governança e Financeiro"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 9
onda: 18
blocked_by:
  - ISSUE-086
  - ISSUE-078
blocks:
  - ISSUE-088
labels:
  - ready-for-agent
source_requirements:
  - HU-017
spec_decisions:
  - D13
---

# Inglês, parte 1: catálogo no servidor, seletor PT | EN, shell, Início, Central, Governança e Financeiro

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D13.
> Entrega 9 (Produto final), onda 18 (Idioma).
> Histórias: 17. Bloqueada por: ISSUE-086, ISSUE-078.

## O que construir

O alternador PT | EN do protótipo volta, com tradução **no servidor** por um
catálogo de mensagens alimentado pelo dicionário `en.js` do protótipo. O
catálogo tem namespace por módulo, o que resolve as colisões do dicionário
plano do protótipo (Prazo, Desvio, Emissão). O seletor de idioma fica na barra
lateral, e a escolha é lembrada.

Terminologia em inglês do protótipo: EAP vira WBS, SM vira CR, EAC vira CBS,
FP vira PF, CP vira PC, S39 vira W39, e as datas curtas seguem o idioma.
Gráficos, Excel e PDF usam o mesmo catálogo. Dados cadastrados não são
traduzidos.

Esta parte cobre o shell, a navegação, os estados de tela, o Início e os
módulos Central de Ações, Governança e Financeiro.

## Critérios de aceite

- [ ] Trocar o idioma muda tela, gráfico, Excel e PDF das áreas desta parte.
- [ ] Dado cadastrado continua no idioma em que foi gravado.
- [ ] As colisões do dicionário antigo não aparecem (cada módulo com o seu termo).
- [ ] A escolha do idioma é lembrada entre as telas.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Teste que confere que toda chave usada nas áreas desta parte tem tradução, e revisão de tela em EN.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `js/i18n.js` e `js/i18n/en.js` do protótipo; README, seção 6.2 e as notas de tradução de cada módulo.
