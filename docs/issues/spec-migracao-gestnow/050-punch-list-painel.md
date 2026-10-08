---
id: ISSUE-050
title: "Punch list: painel de completação"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 5
onda: 10
blocked_by:
  - ISSUE-049
blocks:
  - ISSUE-079
labels:
  - ready-for-agent
source_requirements:
  - HU-070
spec_decisions:
  - D11
---

# Punch list: painel de completação

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D11.
> Entrega 5 (Planejamento de campo e Programação Semanal), onda 10 (02 Planejamento, campo).
> Histórias: 70. Bloqueada por: ISSUE-049.

## O que construir

A aba **Painel** da Punch list mostra os itens abertos por categoria, a curva
de abertura e fechamento acumulados (burndown), o tempo em aberto nas faixas
dos parâmetros (até 7, de 8 a 30 e mais de 30 dias), os itens por disciplina,
sistema e empresa, o % de sistemas liberados por marco e o alerta dos sistemas
bloqueados.

## Critérios de aceite

- [x] As faixas de aging têm teste de fronteira com a data injetada.
- [x] O % de sistemas liberados por marco tem teste da fórmula.
- [x] O burndown bate com as datas de abertura e fechamento dos itens.
- [x] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [x] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo do painel.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `GI.api.planejamento.resumoPunch`.

## Registro de execução

- Data: 2026-10-08.
- Feito: os cálculos em `calculations.py` (bloco "Painel da punch list (ISSUE-050)": `PunchPanelState`, `PunchCategoryCount`, `PunchCountRow`, `PunchBurndownPoint`, `punch_aging_labels`, `punch_aging_band`, `punch_aging_counts`, `punch_category_count`, `punch_discipline_counts`, `punch_company_counts`, `punch_burndown_week_start`, `punch_burndown_weeks`, `punch_burndown` e `punch_released_pct`); a fachada em `service.py` (bloco "Painel da Punch list": `PunchParameters`, `punch_parameters`, `PunchDashboardSystem`, `PunchMilestoneRelease`, `PunchDashboard`, `punch_dashboard` e os internos `_punch_aging_bands`, `_punch_panel_state`, `_punch_dashboard_system`, `_punch_burndown_chart` e `_punch_stacked_chart`); a exportação em `export.py` (`punch_dashboard_document`, `punch_dashboard_kpis`, `_punch_burndown_table`, `_punch_aging_table`, `_punch_group_table`, `_punch_systems_table`, `_punch_block_cell`, `_punch_week_text`); as rotas em `routes.py` (bloco `PUNCH_DASHBOARD_BASE = "planejamento/punch/painel"`: fragmento da aba, Excel e imprimível; a tela passou a devolver o fragmento do painel e o contexto ganhou `_punch_dashboard_context`); o fragmento `punch_painel.html`; o trio: a view ganhou as abas Lista e Painel (`?aba=painel`), o JS troca a aba e refaz o painel pela rota própria quando a lista mudou (marca `painelSujo` em gravações e carga), e o CSS ganhou a barra, o alerta e a grade dos gráficos; os testes `test_punch_painel_calculos.py` (novo), as extensões de `test_punch_servico.py` e `test_punch_rotas.py` e o oráculo `test_oraculo_do_painel_da_punch_list`; a seção do `LEIA-ME.md`; e os termos Aging e Burndown no `CONTEXT.md`.
- Oráculos: no projeto 1, na âncora, o aging fecha em 3 itens abertos na faixa "Até 7 dias" (A/B/C = 1/1/1), 7 em "8 a 30 dias" (3/3/1) e 2 em "Mais de 30 dias" (0/2/0); por disciplina, 7 disciplinas com abertos (Arquitetura 1, Automação 1, Civil 1, Elétrica 1, Instrumentação 2, Mecânica 3, Tubulação 3); por empresa, Alfa Montagens 10 (4/6/0) e Zeta Civil 2 (0/0/2); os sistemas 210 (2/2/0), 310 (1/3/0), 420 (1/0/0) e 510 (0/1/2); a liberação por marco em 75,0% na Completação mecânica (1 bloqueado de 4), 25,0% no Comissionamento (3 de 4) e 0,0% no Aceite definitivo (4 de 4), com o alerta dos sistemas 210, 310 e 420; o burndown de 10 semanas termina com 15 abertos, 3 fechados e saldo de 12 (aberturas: 0, 1, 2, 4, 4, 6, 8, 11, 14 e 15; fechamentos: 0, 0, 0, 0, 2, 2, 3, 3, 3 e 3).
- Decisão: os gráficos usam os visuais existentes da biblioteca (D11) sem tipo novo — o burndown no Curva S Linha (`modo: "acumulado"`, três séries: abertos, fechados e saldo em tracejado) e o aging, a disciplina e a empresa no Comparativo de Barras (barras horizontais empilhadas por categoria A/B/C, um painel por grupo, com a legenda repetida por painel como no exemplo do próprio visual). O protótipo desenhava o aging em barras verticais, e a biblioteca não tem barra vertical empilhada sem a curva acumulada do Pareto; a escolha do visual mais próximo fica registrada.
- Decisão: a aba é endereçável (`?aba=painel`); a tela carrega o painel junto com a lista (alvo `punch-painel`) e o JS o refaz pela rota `GET /api/planejamento/punch/painel` quando a aba abre depois de uma gravação, para o painel nunca sair de sincronia com a lista.
- Decisão: o aging lê o grupo `punch` dos parâmetros vigentes (`agingFaixas`) pelo mesmo caminho das outras fatias (`configuracoes.current_group`, com `INITIAL_PARAMETERS` de reserva); a leitura inválida cai nas faixas iniciais (7 e 30). O alerta segue o protótipo: os sistemas bloqueados para a Completação mecânica ou o Comissionamento; o % liberado sai sobre os sistemas com item no escopo (nenhum sistema, sem percentual), e a tabela do painel mostra os três marcos do protótipo.
- Decisão: "Aging" e "Burndown" entraram no `CONTEXT.md` (o aging é vocabulário dos parâmetros e o burndown é a curva do painel); o `glossario.json` foi regerado e não mudou porque o gerador só carrega siglas e notações. O `% de sistemas liberados` ficou como fórmula da fatia no `LEIA-ME.md`, sem termo novo.
- Decisão: sem migração — nenhuma tabela nova; o painel é cálculo a cada leitura (nada materializado), e a carga de demonstração da ISSUE-049 serve sem mudança.
- Verificação: suíte escopada (`api/tests/planejamento api/tests/plataforma api/tests/central_acoes api/tests/configuracoes`) verde com 1752 testes (16 novos); `ruff check`, `ruff format --check` e `ty check` verdes (o `PLR0913` do apoio `_estado` justificado em `api/pyproject.toml`, no formato das issues anteriores); porta de qualidade completa (`node scripts/verificar.mjs`) verde nas cinco etapas. Sem pendência.
