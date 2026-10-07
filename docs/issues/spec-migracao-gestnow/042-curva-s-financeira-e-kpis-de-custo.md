---
id: ISSUE-042
title: "Curva S financeira e KPIs de custo"
status: done
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

- [x] CPI, SPI, CV, VAC, EAC pelo CPI e TCPI têm teste com fronteira (por exemplo, AC zero).
- [x] A tendência não usa dado posterior ao mês consultado (teste).
- [x] O oráculo afirma CPI de 0,96 em 25/09/2026.
- [x] No Portfólio, PV, EV e AC somam os projetos.
- [x] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [x] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo e o oráculo do CPI.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `curva-s.html` e `kpis.html` do Financeiro, `GI.api.financeiro.curvaFinanceira`,
`indicadores` e `historicoIndices`. O botão Análise do período destas telas
chega na ISSUE-081.

## Registro de execução

- Data: 2026-10-07.
- Feito: as etapas 1 a 3 (commits `6ebb37f`, `0417082` e `f7e2fcd`) entregaram as tabelas `curva_financeira_revisao` e `curva_financeira_mes` (migração `m039_curva_s_financeira`), os cálculos da curva e dos KPIs de custo (`curva_financeira_planejado`, `curva_financeira_erp`, `curva_financeira_trend`, `cost_performance_index`, `cost_schedule_index`, `cost_variance`, `schedule_variance`, `estimate_at_completion_by_cpi`, `to_complete_performance_index`, `estimate_variance`, `committed_percent`, `value_aggregated_month` e `cost_indicators`) com testes de fronteira (AC zero, BAC igual ao AC, EV zero e a tendência sem dado posterior ao mês consultado), o serviço (`freeze_financial_curve` como gancho do `create_revision` da EAC; `financial_curve_overview` e `cost_kpis_overview`, projeto e Portfólio, com PV, EV e AC somados na carteira), as rotas `GET /api/financeiro/curva-s` (alvo `curva-s-conteudo`) e `GET /api/financeiro/kpis` (alvo `kpis-conteudo`), cada uma com `/excel` e `/imprimivel`, os fragmentos `curva_financeira.html` e `custos_kpis.html`, o documento de exportação (`export.curva_financeira_document` e `export.custos_kpis_document`) e a carga `financeiro-curva` (`seed.py::load_financial_curve`). Oráculos: no corte de 25/09/2026 do projeto 1, o CPI é 0,96 (EV do avanço físico real de 65,7% sobre o BAC contra AC de R$ 28,7 mi), o SPI de custo é 0,94, a EAC pelo CPI é R$ 46.440.129,45 e o TCPI é 1,07; na carteira, PV, EV e AC somam os projetos e o CPI da soma sai 0,97. A carga congela o planejado do mock `curvaFinanceira` na revisão vigente da EAC (o número do protótipo, não a distribuição pelo perfil da curva física) e grava o comprometido e o realizado item a item, substituindo o fechamento da parte `financeiro-custos`; a divergência do planejado dos projetos 2 e 3 (32.760.000 e 25.900.000 do mock contra 27.300.000 e 22.200.000 da distribuição pelo perfil) ficou registrada em `docs/DIVERGENCIAS-DO-PROTOTIPO.md` (Q31). Nesta etapa de fechamento, as telas `financeiro/curva_s` e `financeiro/kpis` trocaram o esqueleto pela visão real (views com os alvos `curva-s-conteudo` e `kpis-conteudo` e os botões Excel/PDF pelos mecanismos genéricos; comportamento que carrega o fragmento no boot, mapeia os estados pelo marcador `data-situacao` e trata 403 como sem-permissão) e o `LEIA-ME.md` do módulo recebeu a seção "O que a ISSUE-042 trouxe", com as fórmulas e os nomes no código.
- Fora desta fatia: o botão Análise do período destas telas chega na ISSUE-081, como a nota da issue registra; as duas telas são só de leitura — a curva muda pelas revisões da EAC e pelos fechamentos do ERP.
- Porta de qualidade (`node scripts/verificar.mjs`, cinco etapas) verde e a suíte completa de pytest (2.617 testes, 0 falhas, 0 erros) passou em 07/10/2026.
