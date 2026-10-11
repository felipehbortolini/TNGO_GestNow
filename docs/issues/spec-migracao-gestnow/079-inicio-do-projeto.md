---
id: ISSUE-079
title: "Início do projeto: indicador-chave por módulo e pontos de atenção"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 8
onda: 17
blocked_by:
  - ISSUE-020
  - ISSUE-026
  - ISSUE-035
  - ISSUE-040
  - ISSUE-042
  - ISSUE-050
  - ISSUE-063
  - ISSUE-066
  - ISSUE-071
  - ISSUE-075
blocks:
  - ISSUE-080
labels:
  - ready-for-agent
source_requirements:
  - HU-032
  - HU-033
spec_decisions:
  - D6
  - D11
  - D9
---

# Início do projeto: indicador-chave por módulo e pontos de atenção

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D6, D11, D9.
> Entrega 8 (Visão executiva), onda 17 (Início, análise do período e relatório gerencial).
> Histórias: 32, 33. Bloqueada por: ISSUE-020, ISSUE-026, ISSUE-035, ISSUE-040, ISSUE-042, ISSUE-050, ISSUE-063, ISSUE-066, ISSUE-071, ISSUE-075.

## O que construir

O **Início** mostra o contexto do projeto em etiquetas na barra da página
(projeto, data de referência, que é hoje, orçamento e término) com a
exportação à direita; um **indicador-chave por módulo**, clicável, com a
referência de gestão abaixo do valor (ações atrasadas, SPI, CPI, pedidos
críticos, riscos críticos, RNC abertas, dias sem afastamento, mudanças
aguardando comitê); os **pontos de atenção** calculados (ações mais atrasadas,
pedidos com folga negativa, sistemas bloqueados por item A, revisão de risco
vencida, claim fora do prazo, HiPo no mês e os demais alertas que o protótipo
mostra); e os cards dos 8 módulos.

Cada número vem da fachada do módulo dono, nunca de tabela de outro módulo, e
é calculado na hora.

## Critérios de aceite

- [ ] Cada card mostra o mesmo número da tela do módulo e leva a ela com o filtro certo.
- [ ] Os pontos de atenção saem calculados com a data injetada (teste).
- [ ] O oráculo afirma, no Início do projeto 1: 8 ações atrasadas, SPI 0,94, CPI 0,96, 3 pedidos críticos, 2 riscos críticos, 4 RNC abertas e 263 dias sem afastamento.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada do resumo (pelas fachadas dos módulos) e o oráculo do Início.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `index.html` e `js/pages/home.js`, `GI.api.resumoHome`; README, "Home".

## Registro de execução

Fatia entregue em 11/10/2026: o **Início do projeto** (a tela padrão do app — a rota `/` resolve
para `inicio/home`). A fachada `home_overview(session, *, user, scope, reference_date)` lê as
fachadas donas na hora (D9) e monta o contexto, os **8 indicadores-chave** e os **pontos de
atenção**; `calculations.py` tem as funções puras (formatação compacta, delta, tom do índice,
plural). Rotas (`routes.py`, nomes `home_*`): `GET /api/inicio/resumo` (fragmento no alvo
`inicio-conteudo`, `Access(module="inicio")` — READ) e `GET resumo/excel` e `GET
resumo/imprimivel` pelos mecanismos genéricos (`export.py` monta um `Document` único com os
KPIs, a tabela dos pontos de atenção e a dos módulos). Os indicadores: **ações atrasadas**
(`central_acoes.count_by_status().overdue`, "de N em aberto", link `?status=atrasada`), **SPI**
(`planning_kpis_overview().indicators`, meta ≥ 1,00, "±X vs. mês anterior" e real x previsto),
**CPI** (`cost_kpis_overview().actual.cpi`, meta, variação e a projeção), **pedidos críticos**
(`list_panel().summary.orders`, "N de longo prazo", link `?faixa=critico`), **riscos críticos**
(`risk_panel().summary.top`, segunda faixa e exposição), **RNC abertas**
(`quality_indicators().open_rncs`, "N vencidas · inspeções aprovadas X%"), **dias sem
afastamento** (`panel().accumulated_indicators.days_without_leave` — o 263 do mock —, TF e o
selo de HiPo do mês) e **mudanças aguardando comitê**
(`register_overview().summary.awaiting_committee`, "R$ … aprovados (X%)"). Os **pontos de
atenção** são os 9 do protótipo, cada um com nível, título, detalhe e o link filtrado da tela
dona: ações mais atrasadas (top 3/4 por dias), pedidos com folga negativa, sistemas bloqueados
por item A (um alerta por sistema, com o link `?sistema=<id>`), revisão de risco vencida, claim
fora do prazo (link `?busca=<código>`), emergencial sem ratificação e análise de impacto vencida
(link para a ficha da mudança), RNC vencida/crítica e HiPo no mês. Os **cards dos 8 módulos**
saem do `navegacao.json` (título, primeira tela e ícone) com a descrição do protótipo, o acento
por token e os selos calculados (N atrasadas, N itens A, N claims, aderência, N revisões, N RNC,
TRIF, N em análise). O **contexto** usa o cadastro (orçamento e término do `ProjectSummary`; no
Portfólio, a soma dos orçamentos e o término mais distante) e a data de referência injetada. O
**Portfólio** sai consolidado, com o código do projeto nos pontos de atenção; a tabela Carteira
de projetos e a edição da ponderação ficam para a ISSUE-080. **Correção da carga** achada no
fechamento: o `PARTS` de `tests/plataforma/test_carga_demonstracao.py` não listava as partes
`relatorio-analises` e `relatorio-analises-050607` (ISSUE-081/082) e duas asserções falhavam —
corrigido. **Divergência registrada**: os alertas que dependem de dado de prazo não exposto
pelas fachadas saem sem o número (HiPo sem "em até 30 dias"; emergencial sem a data-limite) e o
bloqueio da punch list vira um alerta por sistema, sem o código do projeto no Portfólio (o
`PunchSystemBlock` não carrega o projeto); os números dos oito indicadores não divergem. O
oráculo (`test_inicio_oraculo.py`) afirma no projeto 1 em 25/09/2026: 8 ações atrasadas, SPI
0,94, CPI 0,96, 3 pedidos críticos, 2 riscos críticos, 4 RNC abertas, 263 dias sem afastamento e
3 mudanças aguardando comitê, com os pontos de atenção sustentados (folgas, sistemas, revisão,
claim de 56 dias, RNC vencida, HiPo) e o Portfólio consolidado. `ruff check`, `ruff format
--check` e `ty check` limpos; as rodadas do fechamento (Início, relatório, Central, planejamento,
financeiro, suprimentos, riscos, qualidade, HSE, governança e plataforma — 3.553 testes, uma vez
no fechamento; o subagente rodou 2.618 ×2 sem a plataforma) passam; a porta de qualidade, 5/5.

- DECISAO: Início serve os dois escopos | projeto e Portfólio consolidado com o código do projeto nos pontos de atenção; a tabela Carteira de projetos e a ponderação ficam para a 080 | ISSUE-079, ISSUE-080
- DECISAO: cada indicador pela fachada dona | os 8 KPIs lidos na hora, com a referência de gestão no rodapé (meta, variação, exposição, prazos) e o link filtrado da tela | D9, ISSUE-079
- DECISAO: pontos de atenção calculados | os 9 do protótipo com o link da tela dona; o bloqueio da punch list vira um alerta por sistema e os prazos não expostos saem sem o número — divergência registrada | D6, ISSUE-079
- DECISAO: contexto do cadastro | orçamento e término do `ProjectSummary` (Portfólio: a soma e o término mais distante) e a data de referência injetada pela rota | D6, ISSUE-079
- DECISAO: export genérico | um `Document` único alimenta o Excel e o imprimível com os KPIs, os pontos de atenção e os módulos | D12, ISSUE-079
- DECISAO: correção da carga | o `PARTS` da plataforma ganhou as partes `relatorio-analises` e `relatorio-analises-050607` das 081/082, que faltavam e quebravam duas asserções | ISSUE-081, ISSUE-082, ISSUE-079
