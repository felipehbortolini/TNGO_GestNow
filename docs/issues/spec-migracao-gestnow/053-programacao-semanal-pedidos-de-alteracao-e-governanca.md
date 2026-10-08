---
id: ISSUE-053
title: "Pedidos de alteração e governança da programação"
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
  - HU-078
  - HU-085
spec_decisions:
  - D10
  - D5b
---

# Pedidos de alteração e governança da programação

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D10, D5b.
> Entrega 5 (Planejamento de campo e Programação Semanal), onda 11 (02 Programação Semanal (o app existente, adaptado)).
> Histórias: 78, 85. Bloqueada por: ISSUE-052.

## O que construir

O fornecedor pede alteração de atividade já validada, e o planejador aplica ou
recusa, com rastreabilidade, como no app. A tela de **governança** mostra o
painel por contratada e semana, os pedidos e a trilha de auditoria (agora a
auditoria única do GestNow, filtrada pela programação).

## Critérios de aceite

- [x] Pedido aplicado ou recusado fica na trilha com antes e depois.
- [x] Os indicadores da governança dão os mesmos números do app para os mesmos dados.
- [x] O fornecedor só vê os próprios pedidos.
- [x] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio — **sem migração**: a `m051` já cria `programacao_pedido_alteracao` como o diagrama mostra, e a seção 8 de `docs/MODELO-DE-DADOS.md` não mudou.
- [x] A demonstração da programação vem da carga de demonstração do app, convertida para as tabelas, num projeto do portfólio, com as datas deslocadas para hoje — o mock do app não tem pedidos (`solicitacoes: []`); a cópia convertida ganhou três, escritos pela própria fachada com as datas deslocadas.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.
- [x] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava — lista de controle e fila no mesmo documento; a trilha fica só na tela, como no app.

## Verificação

Testes portados do app para pedidos e governança.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: blueprint e templates de governança do app (painel, pedidos, trilha).

## Registro de execução

Data: 2026-10-08.
Feito: `service.py` (o painel `governance_panel` com a regra de `dados.governanca`, `request_queue`, `open_request`, `request_change`, `decide_request` com a reabertura, `governance_trail` filtrada por `TRAIL_ENTITIES`, `_closed_for_editing`, `_trail_label` para os comentários do pedido), `permissions.py` (`can_decide_requests`, `can_view_trail`), `validation.py` (`DecisionForm`), `views.py` (linhas do painel, contagens, janelas, fila e trilha), `screen.py` (contextos do painel, da fila, da trilha e do pedido; `pode_pedir` no detalhe), `export.py` (documento único do painel e da fila), `repository.py` (pedidos, janelas, trilha do módulo, atividade por semana e ID), `routes.py` (`governanca`, `governanca/trilha`, `governanca/excel`, `governanca/imprimivel`, `pedidos` GET/POST, `pedidos/formulario`, `pedidos/{id}/decisao`), fragmentos (`painel.html`, `_painel.html`, `fila.html`, `_fila.html`, `trilha.html`, `_trilha.html`, `pedido.html`, `_pedido.html`, `pedido_salvo.html`, `fila_resposta.html`), `_tabela.html` (ação "Pedir alteração" no menu) e `_detalhe.html` (formulário embutido, como no app); tela `app/_views/programacao_semanal/governanca.html` e o trio CSS/JS; `seed.py` + `demonstracao.json` (pedidos da demonstração, datas deslocadas); testes `test_programacao_governanca.py`, `test_programacao_governanca_rotas.py` e o oráculo da governança em `test_carga_demonstracao.py`; `test_programacao_rotas.py` (o `Access` das rotas novas); LEIA-ME do módulo; CONTEXT.md ("Pedido de alteração"; `glossario.json` regerado sem sigla nova).
Verificação: pytest de `programacao_semanal`, `plataforma` e `configuracoes` — 1137 passaram; `ruff check`, `ruff format --check` e `ty check` verdes; `node scripts/verificar.mjs` com as cinco etapas verdes (o `ARG001` de `governance_excel` ficou no per-file-ignore do `routes.py` com comentário, como o dos blueprints — contrato V2 do Azure Functions); sem migração (conferência da `m051` e da seção 8 do MODELO-DE-DADOS).
Oráculo: o pedido aplicado da carga reabre `CAL-TUB-012` (S.31/2026), que passa a publicada/pendente — o projeto `TN-2026-014` fica com 47 publicadas/aprovado, 1 publicada/pendente, 8 validadas/aprovado, 11 validadas/pendente e 25 em elaboração (o oráculo da ISSUE-052 mudou de 48 para 47 e ganhou o par novo). Numa sexta da S.35/2026 (28/08/2026, 10:00 de São Paulo), o painel tem 26 linhas de controle (92 atividades, 3 contratadas), 1 janela aberta (M. Roscoe), 17 pendências de aprovação com realizado e aderência de 72,79% na S.34 de M. Roscoe; a fila tem 3 pedidos (PS2-PIN-011 pendente, CAL-TUB-012 aplicado, SUB-TRF-010 recusado) e a trilha do módulo soma 103 linhas (92 atividades criadas, 1 reabertura, 3 janelas, 1 configuração e 5 do pedido).
DECISÃO: condição do pedido | só em item fechado para edição (publicada ou com o realizado aprovado), exatamente onde o app oferece o botão; a fachada recusa com 422 o pedido em item editável | D10, HU-078, ISSUE-053
DECISÃO: quem decide | Planejador no projeto ou Admin (`can_decide_requests`), como o `APLICAR` do app | D7, D10, ISSUE-053
DECISÃO: aplicar | o efeito concreto do app: grava a decisão, anexa o comentário na atividade e, se o realizado estava aprovado, volta a pendente; a atividade é gravada com a versão lida na hora (o pedido não carrega a versão dela) e o pedido tem o 409 da própria versão | D5, D10, ISSUE-053
DECISÃO: abrir o pedido | qualquer perfil que enxerga o item (como no app), sempre com o recorte de empresa do fornecedor; o painel do pedido é um drawer com motivo mínimo de 10 caracteres, e o detalhe ganha o formulário embutido onde o app tinha | D7, D10, ISSUE-053
DECISÃO: forma da decisão | formulário embutido na fila (resposta + Liberar/Recusar), como no app, em vez de um segundo modal; o 422/409 devolvem a fila e a trilha com a mensagem no item (`fila_resposta.html`) | D10, ISSUE-053
DECISÃO: recusar | exige resposta (mínimo de 5 caracteres, como no app); a resposta fica no pedido e no comentário da atividade | D10, ISSUE-053
DECISÃO: trilha da governança | a auditoria única filtrada pelas entidades do módulo (atividade, pedido, janela e configuração); as linhas de dia ficam fora, como no histórico da atividade (um lançamento de sete dias viraria sete entradas) | D5b, ISSUE-052, ISSUE-053
DECISÃO: Excel e PDF | lista de controle e fila no mesmo documento (`governance_document`), com a coluna Projeto no Portfólio (HU-016); a trilha fica só na tela, como no app | D12, HU-016, ISSUE-053
DECISÃO: demonstração | o app não tem pedidos no mock (`solicitacoes: []`); a cópia convertida ganhou três, escritos pela própria fachada com as datas deslocadas, para a fila e a trilha não nascerem vazias — o aplicado reabre `CAL-TUB-012` e o oráculo da 052 mudou de 48 para 47 publicadas/aprovado com 1 publicada/pendente | D6, D10, ISSUE-052, ISSUE-053
DECISÃO: rota de download | `governance_excel` recebe `req` sem usá-lo (contrato V2 do Azure Functions); o `ARG001` no `routes.py` do módulo ficou no per-file-ignore com comentário, como o dos blueprints | D14, ISSUE-053
DECISÃO: glossário | CONTEXT.md ganhou "Pedido de alteração"; `glossario.json` regerado sem sigla nova | D10, ISSUE-053
