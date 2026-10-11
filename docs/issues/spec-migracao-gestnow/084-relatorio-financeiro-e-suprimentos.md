---
id: ISSUE-084
title: "Relatório: folhas Financeiro (com a linha de tendência) e Suprimentos"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 8
onda: 17
blocked_by:
  - ISSUE-083
blocks:
  - ISSUE-085
labels:
  - ready-for-agent
source_requirements:
  - HU-041
spec_decisions:
  - D12
  - D6
---

# Relatório: folhas Financeiro (com a linha de tendência) e Suprimentos

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D12, D6.
> Entrega 8 (Visão executiva), onda 17 (Início, análise do período e relatório gerencial).
> Histórias: 41. Bloqueada por: ISSUE-083.

## O que construir

Folha **Financeiro**: BAC, realizado acumulado e do mês, valor agregado (EV e
PV), CPI e SPI de custo, projeção no término e VAC (sobrecusto na família
`erro`), contingência consumida; Curva S financeira com a **linha de
tendência** (a função da ISSUE-042, calculada no próprio mês, sem dado
posterior ao período) e o valor agregado de 6 meses; análise do período; EAC
por pacote (nível 1, R$ mil, mapa de calor).

Folha **Suprimentos**: aderência ao plano, pacotes adjudicados, saving, OTD,
pedidos críticos e emitidos até o corte; curva de contratação e pedidos
críticos (até 4) ao lado da análise; marcos realizados no período e
adjudicações e entregas previstas no horizonte (até 5 cada; semanal: 4 semanas
seguintes; mensal: mês seguinte).

## Critérios de aceite

- [ ] A linha de tendência não usa dado posterior ao período (teste).
- [ ] O horizonte de previstos segue o tipo do relatório (teste).
- [ ] As folhas mostram os mesmos números das telas no mesmo corte.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo das folhas.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: README, "Relatório gerencial: regras" (folhas 3 e 4).

## Registro de execução

Fatia entregue em 11/10/2026: as folhas **Financeiro** e **Suprimentos** do relatório gerencial.
`REPORT_SECTIONS` tem as quatro seções e o Conteúdo do modal cresce sozinho; `report_view` monta
as folhas 3-4 quando escolhidas, cada uma com o bloco comum da análise do período (texto e
desvios com comentário; pendente em laranja; sem análise, aviso e link `?analise=1`). A **folha
3** usa os KPIs do dono no **mês de competência** (`_collect_cost` da 081: BAC, realizado
acumulado e do mês, EV/PV, CPI, SPI de custo, projeção e VAC na família `erro`, contingência), a
**Curva S financeira** de `financial_curve_overview(reference_date=competence_month)` — a
tendência do dono (`curva_financeira_trend`) parte do realizado do próprio mês e **não usa dado
posterior** (teste prova `realizado=None` depois do mês) —, o valor agregado dos últimos 6 meses
(`history[-6:]` do dono) e a **EAC por pacote** (nível 1 do `mapa_controle` no mês, R$ mil, com a
`DeviationBand` vigente de cada linha, por projeto no Portfólio). A **folha 4** usa o painel de
suprimentos no corte (aderência, adjudicados, saving, OTD, críticos com LLI e emitidos), a curva
de contratação pelo gráfico do dono (`panel_contracting_chart`), os pedidos críticos (até 4), os
**marcos de pedido realizados no período** com o desvio contra a linha de base e os **previstos
no horizonte** (até 5 cada: adjudicações de pacote ainda não adjudicados e entregas de pedido
ainda não entregues, com o desvio contra o plano/data contratual). O **horizonte** é função pura
(`report_horizon`): semanal = o dia seguinte ao fim do período mais 28 dias (as 4 semanas
seguintes, como o protótipo — S39–S42 em `2026-S38`); mensal = o mês seguinte. **Divergências
registradas** (em `docs/DIVERGENCIAS-DO-PROTOTIPO.md`): o "Realizado no período" da folha
Suprimentos lista só marcos de pedido (o protótipo listava adjudicações, pedidos emitidos e
marcos; a issue e o README falam em marcos, e adjudicação/emissão vivem nos próprios registros),
e o KPI "Contingência consumida" não traz o "Esperado ≤ limite" do protótipo (o
`cost_kpis_overview` não expõe o limite — ele vive na tela de Contingência — e a folha não
refaz a conta do dono). O oráculo estendido afirma no projeto 1 em `2026-S38`: a folha Financeiro
na competência 2026-08 (BAC 4.460.000.000; realizado 2.280.000.000, 520.000.000 no mês; EV
2.243.380.000 x PV 2.408.400.000; CPI 0,98; SPI 0,93; projeção 4.525.500.000 com VAC −65.500.000
na faixa `erro`; contingência 20,0%; tendência de agosto = realizado) e a folha Suprimentos no
corte (aderência 92,9%, adjudicado 3.900.000.000 com saving 5,2%, OTD 66,7%, 3 críticos, o marco
`PED-2026-0002`/Fabricação em 15/09 com +26 d e os previstos de S39–S42). `ruff check`, `ruff
format --check` e `ty check` limpos; as rodadas do fechamento (relatório, planejamento,
financeiro, suprimentos, riscos, qualidade e HSE — 2.195 testes, duas vezes no subagente e uma no
fechamento) passam; a porta de qualidade, 5/5. As folhas Riscos, Qualidade, HSE e a Carteira
ficam para a ISSUE-085; Excel, "Alterar período" e o restante da impressão, para a 086.

- DECISAO: tendência no mês de competência | a Curva S financeira da folha usa a visão do dono no mês de competência — a tendência parte do realizado do mês e não usa dado posterior (o teste prova o realizado nulo depois do mês) | D12, ISSUE-084
- DECISAO: horizonte por tipo | semanal = o dia seguinte ao fim do período + 28 dias (as 4 semanas seguintes, como o protótipo); mensal = o mês seguinte; `report_horizon` puro e testado | D12, ISSUE-084
- DECISAO: EAC por pacote e mapa de calor | nível 1 do mapa do dono no mês de competência, em R$ mil, com a faixa de desvio vigente de cada linha — nada recalculado | D12, ISSUE-084
- DECISAO: realizado no período só marcos | a folha lista os marcos de pedido com o desvio; adjudicações e emissões vivem nos próprios registros e entram nos previstos enquanto não realizadas — divergência registrada | ISSUE-084
- DECISAO: contingência sem o limite | o KPI mostra o consumido do dono e o total da reserva; o limite de consumo vive na tela de Contingência e não entra nesta fatia — divergência registrada | ISSUE-084
