---
id: ISSUE-056
title: "Dashboard da programação"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 5
onda: 11
blocked_by:
  - ISSUE-052
blocks: []
labels:
  - ready-for-agent
source_requirements:
  - HU-084
spec_decisions:
  - D10
  - D11
---

# Dashboard da programação

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D10, D11.
> Entrega 5 (Planejamento de campo e Programação Semanal), onda 11 (02 Programação Semanal (o app existente, adaptado)).
> Histórias: 84. Bloqueada por: ISSUE-052.

## O que construir

O **dashboard** do app, com os gráficos da biblioteca: curva S do avanço,
previsto x realizado, aderência por contratada com drill, rankings, mapa de
calor dia x frente, turnos e gargalos, com os filtros do app. O servidor manda
quantidades, e o gráfico agrega por período quando o resumo não é soma.

## Critérios de aceite

- [x] Os números do dashboard são os do app para os mesmos dados (testes de indicadores portados).
- [x] O drill da aderência por contratada funciona.
- [x] O fornecedor vê o dashboard só da própria empresa.
- [x] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes portados dos indicadores e revisão de tela comparando com o app.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: blueprint e templates do dashboard do app, `indicadores` e `ds/charts.js` do app.

## Registro de execução

Data: 2026-10-08.
Feito: `calculations.py` (novo bloco do dashboard: `IndicatorActivity`, `RankingLine`, `StatusSegment`/`StatusBlock`, `HeatmapCell`/`HeatmapRow`/`Heatmap`, `ShiftDay`, `Bottleneck`, `CompanyWeek`/`EvolutionPoint`/`Evolution` e as funções `ranking`, `situation_distribution`, `heatmap_day_front`, `heat_band`/`heat_faixas`, `shifts_by_day`, `bottlenecks` e `evolution_by_company` — porte de `indicadores.py` do app), `service.py` (`horizon_activities`, que a curva da ISSUE-055 e o dashboard compartilham, `DashboardData` e `dashboard_data`), `export.py` (`curve_chart`, `weekly_chart`, `adherence_chart` com a série `razao`, `status_chart`, `heatmap_chart`, `daily_chart`, `dashboard_charts` e `dashboard_document` com KPIs, gráficos e as tabelas dos números), `screen.py` (`dashboard_context` e `dashboard_filters_context`, as URLs do dashboard e os vazios), `routes.py` (`dashboard`, `dashboard_filters`, `dashboard_excel` e `dashboard_printable`, no prefixo do módulo, com o `Access` de sempre), fragmentos (`dashboard.html`, `_dashboard_painel.html`, `_dashboard_ranking.html`, `_dashboard_turnos.html`, `_dashboard_gargalos.html` e `dashboard_filtros.html`); a tela `app/_views/programacao_semanal/dashboard.html` e o trio CSS/JS (a barra fora do painel, com `x-target="dash-painel"`); testes `test_programacao_indicadores.py`, `test_programacao_dashboard.py` e `test_programacao_dashboard_rotas.py`; `test_programacao_rotas.py` (o `Access` das quatro rotas novas) e `test_carga_demonstracao.py` (o oráculo do dashboard com a carga); `pyproject.toml` (per-file-ignore de `PLR0913` nos três testes novos, com comentário); LEIA-ME do módulo.
Verificação: pytest de `programacao_semanal`, `plataforma` e `configuracoes` — 1252 testes, todos verdes; `ruff check`, `ruff format --check` e `ty check` verdes; `node scripts/verificar.mjs` com as cinco etapas verdes, sem regra desligada; sem migração (o dashboard só lê as tabelas da `m051` — nenhuma tabela nova, seção 8 do MODELO-DE-DADOS inalterada).
DECISÃO: indicadores portados | porte de `indicadores.py` para `calculations.py` com nomes em inglês (D1): `ranking`, `situation_distribution`, `heatmap_day_front`, `heat_band`/`heat_faixas`, `shifts_by_day`, `bottlenecks` e `evolution_by_company`; a fachada monta o material (`service.dashboard_data`) e as funções puras devolvem quantidade, nunca percentual pronto — a evolução manda o par (realizado, previsto) de cada semana | D10, D11, ISSUE-056
DECISÃO: escala do mapa de calor | o app tinha uma rampa contínua de cinco níveis (25/50/75/100); no GestNow o mapa usa a escala única do módulo (60 e 80) no contrato da Tabela Heatmap (tom, nível de 1 a 3 e ícone), como o glossário manda ("uma escala só") e o D11 exige (os visuais são da biblioteca); o dia sem previsão é faixa vazia, não 0% | D11, ISSUE-056
DECISÃO: drill da aderência | a evolução manda o par (realizado, previsto) de cada semana como série `razao` e a biblioteca fecha o mês somando o numerador e o denominador; a meta viaja como par tracejado. O app desenhava barra + linha acumulada; a biblioteca desenha a taxa do período e o drill agrega pela soma — o número do mês é o mesmo (soma do realizado pela soma do previsto) | D11, ISSUE-056
DECISÃO: curva S do dashboard | a curva do avanço é a mesma de `curve_points` (ISSUE-055) sobre o horizonte de treze semanas, agora com os filtros do dashboard via `horizon_activities`; o app tinha removido a curva da tela, mas a issue pede "curva S do avanço" e ela volta como leitura acumulada, ao lado do previsto x realizado por semana | D10, D11, ISSUE-056
DECISÃO: turnos | o app desenhava `barras-simples`, fora da biblioteca; no GestNow o previsto x realizado por dia é o Comparativo de Barras e a separação dia/noite fica na tabela abaixo dele | D11, ISSUE-056
DECISÃO: filtros e barra | a barra fica fora do painel (o formulário tem `x-target="dash-painel"`), como no app: mudar um corte não perde o seletor; "Limpar" recarrega a barra e o painel com a semana; o fornecedor não vê o seletor de contratada (o corte é dele) | D10, D7, ISSUE-056
DECISÃO: exportações | um `Document` para os dois mecanismos: o imprimível desenha os mesmos gráficos (`data-grafico`) e o Excel leva os números atrás de cada um (rankings, gargalos, mapa de calor, turnos, previsto x realizado e evolução); a lista de gargalos é por projeto no Portfólio (HU-016) | D12, HU-016, ISSUE-056
DECISÃO: sem migração | nenhuma tabela nova; o dashboard só lê `programacao_atividade`/`programacao_dia` e os cadastros — seção 8 do `docs/MODELO-DE-DADOS.md` inalterada | D5, ISSUE-056
DECISÃO: glossário | nenhum termo novo de domínio (drill, curva, aderência, turnos e faixas já estão no vocabulário; "gargalo" é o nome da lista de ação da tela, não um conceito novo); `CONTEXT.md` e `glossario.json` não mudaram | D10, ISSUE-056
DECISÃO: oráculo da carga | o oráculo do dashboard entra em `test_carga_demonstracao.py` com os números da S.34/2026 (aderência 66,19%, ranking por contratada, 2 gargalos, turnos, evolução e o fornecedor só com a própria empresa); a carga não mudou | D10, ISSUE-056
