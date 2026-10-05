---
id: ISSUE-048
title: "Produtividade: KPIs de performance e plano de ação na Central"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 5
onda: 10
blocked_by:
  - ISSUE-046
  - ISSUE-047
  - ISSUE-019
blocks:
  - ISSUE-081
labels:
  - ready-for-agent
source_requirements:
  - HU-067
spec_decisions:
  - D6
  - D9
---

# Produtividade: KPIs de performance e plano de ação na Central

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D6, D9.
> Entrega 5 (Planejamento de campo e Programação Semanal), onda 10 (02 Planejamento, campo).
> Histórias: 67. Bloqueada por: ISSUE-046, ISSUE-047, ISSUE-019.

## O que construir

A aba **KPIs de performance** mostra, geral e por empresa, na janela de N
semanas do parâmetro até a semana de corte: avanço, SPI de quantidades,
aderência, fator de produtividade (FP), tendência de atraso, CP e utilização,
% trabalhando, Hhora e Mhora (com % das HH disponíveis), e a tendência semanal
por empresa (FP, aderência, % trabalhando, CP), com as cores pelas faixas dos
parâmetros.

Fórmulas: horas ganhas (HG) = realizado x índice orçado; avanço = HG ÷ HH
orçadas; SPI de quantidades = HG ÷ horas previstas na linha de base; aderência
semanal = realizado ÷ previsto, limitada a 100% por item e ponderada pelas HH
orçadas; FP = HH apropriadas ÷ HG; tendência pelo prazo agregado (SPI(t) =
semanas da linha de base equivalentes ao realizado ÷ semanas decorridas);
apontamento pendente = item ativo sem apontamento na semana de corte.

Empresa com indicador fora da faixa pode gerar **plano de ação na Central**
(origem Produtividade, referência semana e empresa, como `PRD-2026-S39-01`):
uma ação aberta por empresa e semana, com o link da Central voltando para esta
aba com a empresa e a semana.

## Critérios de aceite

- [ ] HG, avanço, SPI de quantidades, aderência, FP e SPI(t) têm teste com fronteira.
- [ ] Gerar o plano duas vezes para a mesma empresa e semana não duplica a ação.
- [ ] O link da ação na Central volta para a aba KPIs com a empresa e a semana.
- [ ] O oráculo afirma avanço de 59,2% x 67,5% (SPI 0,88), FP de 1,12 nas últimas 4 semanas, CP de 6,81 h/dia e 55,3% trabalhando.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo, de fachada (plano de ação sem duplicar) e o oráculo da produtividade.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `GI.api.planejamento.produtividade.kpis` e `gerarAcao`; números do cenário no README, "Produtividade: regras".
