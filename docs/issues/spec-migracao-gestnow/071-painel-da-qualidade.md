---
id: ISSUE-071
title: "Painel da qualidade"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 7
onda: 14
blocked_by:
  - ISSUE-069
  - ISSUE-070
blocks:
  - ISSUE-079
  - ISSUE-082
labels:
  - ready-for-agent
source_requirements:
  - HU-119
spec_decisions:
  - D11
---

# Painel da qualidade

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D11.
> Entrega 7 (Qualidade, HSE e Configurações), onda 14 (06 Qualidade).
> Histórias: 119. Bloqueada por: ISSUE-069, ISSUE-070.

## O que construir

O **Painel** da Qualidade mostra os KPIs (RNC em aberto com vencidas e
críticas, tempo médio de tratamento, eficácia na 1ª verificação, aprovação em
inspeções x meta, conformidade em auditorias x meta, aderência ao programa e
custo da não qualidade), o aviso de auditorias atrasadas, RNC por mês (abertas
e encerradas), aprovação em inspeções por mês com a meta, Pareto de RNC por
disciplina, RNC por origem, a pauta de tratamento e o desempenho por empresa.

Fórmulas: aprovação = (aprovadas + com ressalva) ÷ inspeções; conformidade =
conformes ÷ verificados; aderência = realizadas ÷ previstas até a data de
referência; tempo médio = abertura até encerramento; eficácia = encerradas
sem reincidência ÷ encerradas.

## Critérios de aceite

- [ ] Cada fórmula tem teste com fronteira.
- [ ] As metas vêm dos parâmetros vigentes.
- [ ] O Pareto por disciplina sai em ordem decrescente com o acumulado.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo do painel.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `painel.html` da Qualidade, `GI.api.qualidade.indicadores`. O botão Análise do período chega na ISSUE-082.
