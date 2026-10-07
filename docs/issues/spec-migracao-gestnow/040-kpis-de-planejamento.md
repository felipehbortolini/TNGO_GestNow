---
id: ISSUE-040
title: "KPIs de planejamento por período e por área"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 4
onda: 8
blocked_by:
  - ISSUE-039
blocks:
  - ISSUE-079
  - ISSUE-081
labels:
  - ready-for-agent
source_requirements:
  - HU-063
spec_decisions:
  - D6
  - D11
---

# KPIs de planejamento por período e por área

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D6, D11.
> Entrega 4 (Custo e avanço físico), onda 8 (02 Planejamento, avanço físico).
> Histórias: 63. Bloqueada por: ISSUE-039.

## O que construir

A tela **KPIs** do Planejamento mostra SPI físico, avanço previsto x real e
desvio (p.p.) por período e por área, com a referência de gestão abaixo de cada
valor. O avanço por área é calculado da EAP, sem lançamento próprio. Entram
também os indicadores da EAP que a tela do protótipo mostrava (término vencido
e SMs a incorporar).

## Critérios de aceite

- [x] SPI físico = real ÷ previsto acumulados, com teste de fronteira.
- [x] O avanço por área vem da EAP e bate com a árvore.
- [x] O oráculo afirma SPI de 0,94 em 25/09/2026.
- [x] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [x] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo e o oráculo do SPI.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `kpis.html` do Planejamento; README, "02 Planejamento". O botão Análise do período desta tela chega na ISSUE-081.

## Registro de execução

- Data: 2026-10-07.
- Feito: as etapas 1 a 3 (commits `88895a3`, `a4a388a` e este fechamento) entregaram os cálculos `calculations.spi_index`, `spi_series` e `area_contribution` (com testes de fronteira: sem previsto não há índice e a série para no último mês com real); a leitura `service.planning_kpis_overview` (a curva da ISSUE-039, o SPI por mês, as linhas de avanço por área — os projetos da carteira no Portfólio —, o pior desvio, os indicadores da EAP e os dois gráficos, com os testes `test_kpis_servico.py`); as rotas `GET /api/planejamento/kpis` (alvo `kpis-conteudo`), `/excel` e `/imprimivel`, o fragmento `kpis.html` e o documento de exportação `export.planning_kpis_document` (com os testes `test_kpis_rotas.py`); e o trio `app/_views/planejamento/kpis.html` + `app/paginas/planejamento/kpis.css`/`js` no padrão da Curva S (`$ajax` no alvo, `data-situacao` decidindo o estado, 403 → sem-permissão, Excel e PDF no cabeçalho). Nesta etapa de fechamento, o `LEIA-ME.md` do módulo recebeu a seção "KPIs de planejamento (ISSUE-040)" e este registro, e o oráculo entrou em `test_carga_demonstracao.py`.
- O avanço por área é calculado da EAP (D6): as áreas de nível 1 da árvore, cuja média ponderada pelos pesos fecha com a Curva S. O botão "Atualizar avanço por área" do protótipo saiu por D6 — ele lançava o real por área à mão, e o real vem só das medições dos pacotes. O botão "Análise do período" não entrou: chega na ISSUE-081, como a spec registra.
- Oráculo: com a mesma data deslocada da Curva S (a âncora mais cinco dias, corte em set/26), o projeto 1 tem SPI de 0,94, previsto de 65,7% e real de 61,8%; as áreas da EAP batem com o mock de `avancoAreas` (Engenharia 98/96, Suprimentos 80/78, Obras civis 70/66, Montagem eletromecânica 38/30 e Comissionamento 0/0) e a soma ponderada fecha com a curva; a carteira devolve uma linha por projeto, com peso.
- Fora desta fatia: a tela é só de leitura (sem botão de inclusão e, por isso, nada a pedir o projeto no Portfólio); a exportação traz a coluna Projeto no Portfólio pelo mecanismo genérico.
- Porta de qualidade (`node scripts/verificar.mjs`, cinco etapas) verde e a suíte completa de pytest (2.511 testes, 0 falhas, 0 erros) passou em 07/10/2026.
