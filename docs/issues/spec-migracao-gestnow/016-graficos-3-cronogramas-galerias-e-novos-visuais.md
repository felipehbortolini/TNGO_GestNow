---
id: ISSUE-016
title: "Biblioteca de gráficos 3: Gantt, calendário, galeria, cards de formulário, áreas, tabelas formatadas e os visuais novos"
status: in-progress
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 2
onda: 4
blocked_by:
  - ISSUE-015
blocks:
  - ISSUE-019
  - ISSUE-023
  - ISSUE-029
  - ISSUE-044
  - ISSUE-045
  - ISSUE-051
  - ISSUE-064
  - ISSUE-072
labels:
  - ready-for-agent
source_requirements:
  - HU-064
  - HU-095
  - HU-122
spec_decisions:
  - D11
---

# Biblioteca de gráficos 3: Gantt, calendário, galeria, cards de formulário, áreas, tabelas formatadas e os visuais novos

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D11.
> Entrega 2 (Plataforma no ar), onda 4 (Serviços transversais).
> Histórias: 64, 95, 122. Bloqueada por: ISSUE-015.

## O que construir

Completa a coletânea na biblioteca: **Gráfico Gantt**, **HTML Calendário**,
**Galeria**, **Formulário de Cards**, **Gráfico de Áreas de Avaliação**,
**Tabela formatada**, **Tabela Formata 2** e **Tabela Etapa por etapa**.

E constrói, no mesmo padrão visual (tipografia, tooltip escuro, legenda, botões
de ano, animação de entrada), os quatro visuais que a coletânea não tem:
**pirâmide de segurança dupla** (mês x acumulado, com a proporção de
referência Bird ou Heinrich), **cascata de valor do contrato**, **rosca de
distribuição** e **linhas múltiplas** (TF e TRIF, CPI e SPI mês a mês).

O styleguide de gráficos fica completo, com a tabela de mapeamento da D11
("necessidade no GestNow" para "visual") e o exemplo de cada um.

## Critérios de aceite

- [ ] Os oito visuais da coletânea renderizam no styleguide com a aparência dos originais.
- [ ] Os quatro visuais novos seguem tipografia, tooltip, legenda e animação da coletânea.
- [ ] O styleguide traz os 22 visuais da coletânea e os 4 novos, com a tabela de mapeamento da D11.
- [ ] Nenhuma cor fixa e nenhum erro no console.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Abrir o styleguide completo e comparar com os originais. `npm run verificar`
passa.

## Decisões em aberto

Nenhuma.

## Notas

Fonte da pirâmide dupla: `GI.charts.pyramidPair` do protótipo (faixas de
altura fixa, rótulos na coluna central, proporção real abaixo de cada pirâmide,
referência no rodapé), redesenhada no padrão da coletânea.
