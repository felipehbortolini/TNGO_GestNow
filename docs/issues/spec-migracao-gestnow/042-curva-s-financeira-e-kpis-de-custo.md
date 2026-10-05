---
id: ISSUE-042
title: "Curva S financeira e KPIs de custo"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 4
onda: 9
blocked_by:
  - ISSUE-041
blocks:
  - ISSUE-079
  - ISSUE-081
labels:
  - ready-for-agent
source_requirements:
  - HU-092
  - HU-093
spec_decisions:
  - D6
  - D11
---

# Curva S financeira e KPIs de custo

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D6, D11.
> Entrega 4 (Custo e avanço físico), onda 9 (03 Financeiro, desempenho).
> Histórias: 92, 93. Bloqueada por: ISSUE-041.

## O que construir

A **Curva S financeira** mostra CAPEX planejado (linha de base congelada por
revisão), comprometido e realizado acumulados por mês, mais a tendência, com a
tabela período a período; no Portfólio, a soma em reais dos projetos. A
tendência é uma função única do servidor, reutilizada pelo relatório gerencial
(ISSUE-084): parte do realizado e chega à EAC por desempenho (BAC ÷ CPI, isto
é, AC + (BAC − EV) ÷ CPI), distribuindo o custo restante pelo perfil do
planejado.

Os **KPIs de custo** mostram CPI, SPI de custo, CV, VAC, % de consumo da
contingência e % comprometido, com a variação em relação ao período anterior;
CPI e SPI mês a mês (linhas múltiplas); e a tabela de valor agregado com a EAC
pelo CPI e o TCPI. EV vem do avanço físico real da EAP sobre o BAC, PV da linha
de base e AC do realizado. No Portfólio, PV, EV e AC são somados.

## Critérios de aceite

- [ ] CPI, SPI, CV, VAC, EAC pelo CPI e TCPI têm teste com fronteira (por exemplo, AC zero).
- [ ] A tendência não usa dado posterior ao mês consultado (teste).
- [ ] O oráculo afirma CPI de 0,96 em 25/09/2026.
- [ ] No Portfólio, PV, EV e AC somam os projetos.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo e o oráculo do CPI.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `curva-s.html` e `kpis.html` do Financeiro, `GI.api.financeiro.curvaFinanceira`,
`indicadores` e `historicoIndices`. O botão Análise do período destas telas
chega na ISSUE-081.
