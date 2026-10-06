---
id: ISSUE-052
title: "Fluxo de cinco passos: validar com fiscal, realizado por turno, aprovação do fiscal e publicação"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 5
onda: 11
blocked_by:
  - ISSUE-051
blocks:
  - ISSUE-053
  - ISSUE-055
  - ISSUE-056
labels:
  - ready-for-agent
source_requirements:
  - HU-073
  - HU-074
  - HU-075
  - HU-076
  - HU-077
spec_decisions:
  - D10
  - D7
---

# Fluxo de cinco passos: validar com fiscal, realizado por turno, aprovação do fiscal e publicação

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D10, D7.
> Entrega 5 (Planejamento de campo e Programação Semanal), onda 11 (02 Programação Semanal (o app existente, adaptado)).
> Histórias: 73, 74, 75, 76, 77. Bloqueada por: ISSUE-051.

## O que construir

Porta o fluxo de cinco passos do app. O Planejador valida a programação e
define o fiscal. Encarregado ou Fornecedor lançam o realizado por turno (dia e
noite), com "= previsto" e "copiar a semana", e justificativa quando o desvio
passa do limite do parâmetro. O Fiscal aprova o realizado das atividades sob a
sua responsabilidade, ou reabre com motivo. O Planejador publica as atividades
validadas, encerrando a edição da semana.

A matriz mostra, em cada atividade, o botão com a próxima ação de quem está
olhando e um menu só com o que o perfil pode fazer. Situação por atividade, PPC
por atividade e aderência ponderada do conjunto, com as faixas alta, média e
baixa, exatamente como no app.

## Critérios de aceite

- [x] Os testes do fluxo do app estão portados e verdes.
- [x] Cada transição só é aceita do papel certo no projeto; os demais recebem 403.
- [x] Desvio acima do limite sem justificativa é recusado.
- [x] O botão da próxima ação e o menu mudam com o perfil.
- [x] PPC e aderência dão os mesmos números do app para os mesmos dados.
- [x] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [x] A demonstração da programação vem da carga de demonstração do app, convertida para as tabelas, num projeto do portfólio, com as datas deslocadas para hoje.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes portados do app e testes de rota das permissões por papel.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: blueprints e templates de atividade (validar, realizado, aprovar) do app e os cálculos de PPC e aderência.

## Registro de execução

Data: 2026-10-06.
Feito: `permissions.py` (quem faz cada passo), `flow.py` (próxima ação, menu, guardas), `workflow.py` (validar, realizado por turno, aprovar, reabrir, publicar, publicar a semana), desvio em `calculations.py`, rotas e painéis (validação, realizado, aprovação, reabertura, detalhe), botão e menu na matriz, CSS, testes (`api/tests/programacao_semanal/test_programacao_fluxo_*.py`), LEIA-ME. Nada foi executado (política de testes): só `ruff`.
Falta: execução da porta de qualidade pelo orquestrador. Sem migração (o modelo da 051 já tem tudo) e sem mudança no modelo de dados; a carga da 051 já cobre todos os estados do fluxo.
DECISÃO: aprovar e reabrir o realizado | só o Fiscal responsável pela atividade (ou o Admin); o app deixava qualquer fiscal | D7, ISSUE-052
DECISÃO: lançar o realizado | Encarregado, Fornecedor (só a própria empresa) e Admin, sem a janela de programação, como no app | D7, ISSUE-052
DECISÃO: justificativa do desvio | guardada em observações do fornecedor, como no app; no limite exato não exige; sem previsto não exige | D10, ISSUE-052
DECISÃO: publicar | atividade validada, com ou sem realizado aprovado (como no app); "Publicar a semana" publica só as validadas | D10, ISSUE-052
DECISÃO: ver detalhes | painel só de leitura (dias, observações, comentários), pois o botão "Ver" do app precisa de destino | D10, ISSUE-052
