---
id: ISSUE-026
title: "Painel de mudanças"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 3
onda: 6
blocked_by:
  - ISSUE-025
blocks:
  - ISSUE-079
labels:
  - ready-for-agent
source_requirements:
  - HU-130
spec_decisions:
  - D11
---

# Painel de mudanças

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D11.
> Entrega 3 (Central de Ações e Governança), onda 6 (08 Governança).
> Histórias: 130. Bloqueada por: ISSUE-025.

## O que construir

A aba **Painel** do registro de mudanças mostra mudanças por situação, Pareto
por origem (com a tabela e o percentual acumulado), valor e prazo aprovados
acumulados por mês (linhas sem suavização), mudanças por tipo, taxa de
aprovação (sem as adiadas) e tempo médio de decisão, com os visuais da
biblioteca. O consumo da reserva de contingência entra no painel na ISSUE-041.

## Critérios de aceite

- [ ] Taxa de aprovação (sem as adiadas) e tempo médio de decisão têm teste da fórmula.
- [ ] O Pareto sai em ordem decrescente, com o acumulado chegando a 100%.
- [ ] Os acumulados por mês batem com as SMs aprovadas.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo dos indicadores e conferência do Pareto com o mock.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `GI.api.governanca.painelMudancas`.

## Registro de execução

- Data: 2026-10-06.
- Feito: a aba **Painel** no registro de mudanças (KPIs, gráficos e a tabela do Pareto), os cálculos (`count_lines`, `pareto_lines`, `approval_rate`, `approved_monthly`), a fachada (`service.change_panel`), os gráficos (`panel.py`: `charts_of`, `month_label`), a exportação com as tabelas do painel no Excel e no PDF (`export.register_document`), os testes (`api/tests/governanca/test_painel_mudancas.py`) e o oráculo (`api/tests/governanca/test_oraculo_mudancas_painel.py`).
- Decisão de execução: o painel é calculado no escopo inteiro da requisição (sem os filtros da tabela), como no protótipo; o pedido de partes do filtro não carrega o painel. Os visuais são os da biblioteca do Design System, sem `<script>` nos fragmentos.
- Pendência registrada: o consumo da reserva de contingência entra no painel na ISSUE-041, como a issue aponta.
- Porta de qualidade (`npm run verificar`) e a suíte completa de pytest passaram em 06/10/2026.
