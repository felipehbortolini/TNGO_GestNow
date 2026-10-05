---
id: ISSUE-015
title: "Biblioteca de gráficos 2: cards, faixa de KPI, matrizes, heatmap, mapa de 52 semanas, quantitativos e etapas"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 2
onda: 4
blocked_by:
  - ISSUE-014
blocks:
  - ISSUE-016
labels:
  - ready-for-agent
source_requirements:
  - HU-032
  - HU-089
  - HU-102
  - HU-111
spec_decisions:
  - D11
---

# Biblioteca de gráficos 2: cards, faixa de KPI, matrizes, heatmap, mapa de 52 semanas, quantitativos e etapas

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D11.
> Entrega 2 (Plataforma no ar), onda 4 (Serviços transversais).
> Histórias: 32, 89, 102, 111. Bloqueada por: ISSUE-014.

## O que construir

Porta para a biblioteca, sobre o motor comum da ISSUE-014, os visuais **Card
Indicador Único**, **Card Indicador Único com detalhes** (com a referência de
gestão abaixo do valor), **HTML KPI Status**, **Matriz Formatada**, **Separação
Severidade Riscos**, **Tabela Heatmap**, **Mapa 52 semanas**, **Tabela
Quantitativos por entregável** e **Etapas**.

As faixas de cor do mapa de calor e da matriz P x I são refeitas nas famílias
do Design System (`ok`, `warn`, `erro`, `azul`, `frio`, `roxo`), mantendo o
sinal e o ícone além da cor (D1). Cada visual entra no styleguide de gráficos
com dados de exemplo.

## Critérios de aceite

- [ ] Os nove visuais renderizam no styleguide com a aparência dos originais.
- [ ] As faixas do heatmap e da matriz usam as famílias do Design System e mostram sinal e ícone além da cor.
- [ ] Os cards mostram a referência de gestão (previsto, meta, linha de base) abaixo do valor.
- [ ] Nenhuma cor fixa e nenhum erro no console.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Abrir o styleguide e comparar cada visual com o original. `npm run verificar`
passa.

## Decisões em aberto

Nenhuma.

## Notas

Mapeamento de uso da D11: cards no Início e nos painéis; heatmap no mapa de
controle, no dia x frente e no aging; Mapa 52 semanas no MAS e no plano de
quantidades; Etapas no processo de compra, na SM e na RNC.
