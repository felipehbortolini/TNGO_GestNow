---
id: ISSUE-028
title: "Painel de lições"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 3
onda: 6
blocked_by:
  - ISSUE-027
blocks: []
labels:
  - ready-for-agent
source_requirements:
  - HU-130
spec_decisions:
  - D11
---

# Painel de lições

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D11.
> Entrega 3 (Central de Ações e Governança), onda 6 (08 Governança).
> Histórias: 130. Bloqueada por: ISSUE-027.

## O que construir

A aba **Painel** das lições mostra lições por fase e por área (a repetir e a
evitar), as publicadas nos últimos dias do parâmetro, "Dias desde a última
lição" com alerta pelo parâmetro (90 dias), lições por situação, taxa de
reuso, projetos sem registro no período e as lições mais reusadas.

## Critérios de aceite

- [ ] "Dias desde a última lição" e o alerta têm teste de fronteira no parâmetro.
- [ ] Taxa de reuso e projetos sem registro têm teste da fórmula.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo dos indicadores com a data injetada.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `GI.api.governanca.painelLicoes`.

## Registro de execução

- Data: 2026-10-06.
- Feito: a aba **Painel** no acervo de lições (cinco KPIs, os dois gráficos de barras por fase e por área e as tabelas de situação, mais reusadas e projetos sem registro), os cálculos (`days_since_last`, `is_registration_alert`, `reuse_rate`, `lines_by_phase`, `lines_by_area`, `projects_without_record`), a fachada (`service.lesson_panel`), os gráficos (`lessons_panel.py`: `charts_of`), a exportação com as tabelas e os gráficos do painel (`export.acervo_document`), os testes (`api/tests/governanca/test_painel_licoes.py`) e o oráculo (`api/tests/oraculo/test_oraculo_licoes_painel.py`).
- Decisão de execução: a janela do alerta é o parâmetro `licoes.alertaSemRegistroDias` (padrão 90), lido pela versão em vigor na data; as contagens do painel saem das lições visíveis no escopo (como o acervo), e "projetos sem registro" olha as lições do próprio projeto, em qualquer situação. O app de projeto único tinha tirado "Projetos sem registro"; o produto é multi-projeto e a issue pede a fórmula.
- Porta de qualidade (`npm run verificar`) e a suíte completa de pytest passaram em 06/10/2026.
