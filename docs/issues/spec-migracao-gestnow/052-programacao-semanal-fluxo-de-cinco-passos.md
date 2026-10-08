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
- [x] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio — **sem migração**: a `m051` já cria `situacao`, `aprovacao_realizado`, `aprovado_por_id`, `aprovado_em` e `publicado_em`, e a seção 8 do diagrama não mudou.
- [x] A demonstração da programação vem da carga de demonstração do app, convertida para as tabelas, num projeto do portfólio, com as datas deslocadas para hoje — a carga da 051 já cobre o fluxo; o oráculo dos estados e da próxima ação foi acrescentado.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes portados do app e testes de rota das permissões por papel.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: blueprints e templates de atividade (validar, realizado, aprovar) do app e os cálculos de PPC e aderência.

## Registro de execução

Data: 2026-10-08.
Feito: `permissions.py` (`can_validate`, `can_report`, `can_approve`, `next_action` — a fila validar → lançar → aprovar → publicar → ver), `calculations.deviation_percent`, `validation.py` (formulários da validação, do realizado e da aprovação/reabertura), `service.py` (as transições, a regra do desvio, `publish_week`, o histórico da atividade), `views.py`/`screen.py` (botão da próxima ação e menu na linha; contextos dos painéis de validar, realizado, aprovar/reabrir e detalhe), `routes.py` (`validacoes`, `realizados`, `aprovacoes`, `reaberturas`, `publicacoes` e `publicacoes/semana`, `atividades/detalhe`), fragmentos (`_validar.html`, `_realizado.html`, `_aprovacao.html`, `_grade.html`, `_detalhe.html`, `validacao.html`, `realizado.html`, `aprovacao.html`, `detalhe.html`), `_tabela.html` (ações da linha) e `filtros.html` ("Publicar as validadas"); CSS do menu, do lançamento por turno e da trilha; `ancorarMenu` no JS da tela; testes `test_programacao_fluxo.py`, `test_programacao_fluxo_rotas.py`, o oráculo de PPC/aderência em `test_programacao_dominio.py` e o oráculo do fluxo em `test_carga_demonstracao.py`; LEIA-ME do módulo; CONTEXT.md ("Fluxo da programação", "Próxima ação") e `glossario.json` regerado (sem sigla nova).
Verificação: pytest de `programacao_semanal`, `plataforma`, `configuracoes` e `planejamento` — 1662 passaram; `ruff check`, `ruff format --check` e `ty check` verdes; `node scripts/verificar.mjs` com as cinco etapas verdes; sem migração (conferência da `m051` e da seção 8 do MODELO-DE-DADOS).
Oráculo: 92 atividades no projeto `TN-2026-014` (48 publicadas/aprovado, 8 validadas/aprovado, 11 validadas/pendente, 25 em elaboração); semana S.34/2026 — aderência 66,19%, PPC médio 65,86%, 4 aguardando o fiscal, 2 na faixa baixa; PS2-EST-003 com PPC 74,11% (média).
DECISÃO: confirmação de publicar | o modal do Design System (`TN.confirmarExclusao`), como no app; o fragmento da publicação é o `salvo.html`, não há painel de confirmação | D10, ISSUE-052
DECISÃO: regra de publicar | exige só a situação validada, como no app; a próxima ação só oferece "Publicar" com o realizado aprovado, mas `publicacoes` e `publicacoes/semana` publicam validadas com realizado pendente, como o app fazia | D10, ISSUE-052
DECISÃO: publicar a semana | sem os filtros de tela (o endereço do shell não os carrega) e tudo ou nada, na transação única, com a versão de cada atividade lida na hora; o app publicava o que conseguia e ignorava o resto linha a linha | D5, D10, ISSUE-052
DECISÃO: dono da aprovação | o papel Fiscal no projeto (qualquer pessoa com ele), sem restringir à pessoa designada em `responsavel_id` — o app não restringia e a D10 pede só as adaptações listadas; a HU-075 fala "sob minha responsabilidade" e o filtro por fiscal já ajuda a achar as suas | D7, HU-075, ISSUE-052
DECISÃO: reabrir | mantém `aprovado_por_id`/`aprovado_em` preenchidos, como o app; a aprovação seguinte os sobrescreve e a trilha guarda as duas | D10, ISSUE-052
DECISÃO: painel de leitura ("ver") | o destino da próxima ação `ver` é um painel de detalhe novo (ficha, grade dos dias e histórico da própria atividade); as linhas de dia ficam fora da trilha para um lançamento de sete dias não virar sete entradas | D10, ISSUE-052
DECISÃO: mensagem do fiscal | "Escolha um fiscal — a lista vem dos colaboradores com o papel de Fiscal neste projeto", adaptada dos cadastros do GestNow | D10, ISSUE-052
DECISÃO: nome da rota do painel do realizado | `done_form` (e não `report_form`, que já existe em Planejamento): o Azure Functions exige nome de função único no app | D1, ISSUE-052
DECISÃO: sem migração | a `m051` já tem `situacao`, `aprovacao_realizado`, `aprovado_por_id`, `aprovado_em` e `publicado_em`; a seção 8 de `docs/MODELO-DE-DADOS.md` não mudou | D5, ISSUE-052
DECISÃO: glossário | CONTEXT.md ganhou "Fluxo da programação" e "Próxima ação"; `glossario.json` regerado sem sigla nova | D10, ISSUE-052
