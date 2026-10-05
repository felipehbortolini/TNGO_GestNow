---
id: ISSUE-081
title: "Análise do período de 02, 03 e 04, com desvios negativos e comentários obrigatórios"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 8
onda: 17
blocked_by:
  - ISSUE-040
  - ISSUE-042
  - ISSUE-044
  - ISSUE-048
  - ISSUE-063
blocks:
  - ISSUE-082
labels:
  - ready-for-agent
source_requirements:
  - HU-042
  - HU-043
  - HU-044
  - HU-045
spec_decisions:
  - D6
---

# Análise do período de 02, 03 e 04, com desvios negativos e comentários obrigatórios

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D6.
> Entrega 8 (Visão executiva), onda 17 (Início, análise do período e relatório gerencial).
> Histórias: 42, 43, 44, 45. Bloqueada por: ISSUE-040, ISSUE-042, ISSUE-044, ISSUE-048, ISSUE-063.

## O que construir

O botão **Análise do período** abre o modal em 02 Relato do período e KPIs, 03
KPIs de custo e Curva S financeira e 04 Painel de suprimentos. Passo 1: tipo e
período (lista com a situação: registrada, pendente ou em andamento; padrão:
período anterior). Passo 2: resumo dos indicadores do período, texto da
análise (150 a 2.500 caracteres) e um campo por desvio negativo. O endereço com
`analise`, tipo e período abre direto no passo 2.

Um registro por módulo, tipo e período; Trocar período, Copiar do período
anterior e Excluir (Gestor). Os **desvios negativos são detectados no
servidor**, com os mesmos dados do relatório: no 02, avanço acumulado e do
período abaixo do previsto, término pela tendência depois da linha de base,
áreas com desvio negativo e produtividade fora da meta; no 03, CPI e SPI de
custo abaixo de 1, VAC negativo e pacotes com sobrecusto projetado; no 04,
aderência e OTD abaixo de 100%, pedidos críticos e marcos realizados com
atraso no período. Em 02, 03 e 04, cada desvio exige comentário de ao menos 20
caracteres, gravado pela chave do desvio; um desvio novo, surgido porque os
dados mudaram, aparece como pendente.

## Critérios de aceite

- [ ] A detecção de cada desvio dos três módulos tem teste.
- [ ] Texto fora de 150 a 2.500 caracteres e comentário com menos de 20 são recusados.
- [ ] Mudar um dado que cria um desvio novo faz ele aparecer pendente (teste).
- [ ] Copiar do anterior traz o texto para revisão, e Excluir exige Gestor.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo (detecção) e de fachada (gravação, pendência e cópia).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `js/components/analise.js` e `GI.api.analises.*`; README, "Análise do período por módulo: regras".
