---
id: ISSUE-080
title: "Início no Portfólio: carteira de projetos e edição da ponderação"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 8
onda: 17
blocked_by:
  - ISSUE-079
blocks:
  - ISSUE-085
labels:
  - ready-for-agent
source_requirements:
  - HU-034
  - HU-035
spec_decisions:
  - D8
  - D6
---

# Início no Portfólio: carteira de projetos e edição da ponderação

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D8, D6.
> Entrega 8 (Visão executiva), onda 17 (Início, análise do período e relatório gerencial).
> Histórias: 34, 35. Bloqueada por: ISSUE-079.

## O que construir

No **Portfólio**, o Início mostra os indicadores consolidados, a tabela
**Carteira de projetos** (peso, BAC, avanço previsto e real, SPI, CPI, projeção
e VAC, término, riscos críticos, pedidos críticos, ações atrasadas, situação e
Abrir) e os pontos de atenção com o código do projeto.

O botão **Ponderação** (Gestor ou Admin) abre a edição dos critérios e das
notas com prévia dos pesos e justificativa obrigatória; gravar cria nova
versão dos parâmetros (grupo Portfólio).

## Critérios de aceite

- [ ] A carteira mostra os números de cada projeto iguais aos do Início do projeto.
- [ ] A prévia não grava; gravar cria nova versão com justificativa.
- [ ] Membro recebe 403 ao gravar a ponderação.
- [ ] O oráculo afirma os pesos 55,36 / 29,34 / 15,30.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (carteira e ponderação) e de rota (403).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: Home no Portfólio e o modal de ponderação do protótipo; README, "Gestão de portfólio".

## Registro de execução

Fatia entregue em 11/10/2026: o **Início no Portfólio** — a **carteira de projetos** e a
**edição da ponderação**. A fachada `home_overview` ganhou `portfolio_rows`, `portfolio_totals` e
`portfolio_note` (só no Portfólio): `_portfolio_rows` lê os donos **por projeto** no mesmo corte
(D9) — o peso de `financeiro.portfolio_weights` (uma leitura só para a carteira), o previsto, o
real, o SPI e os términos de `planning_kpis_overview`, o BAC, o CPI, a projeção e o VAC de
`cost_kpis_overview`, os riscos no topo de `risk_panel`, os pedidos críticos de `list_panel` e as
ações atrasadas de `count_by_status` — e ordena do maior peso para o menor; `_portfolio_totals`
não releu nada (reusa os consolidados que os indicadores já leram) e `_portfolio_note` repete a
nota do protótipo ("Peso na carteira pela ponderação composta: … 60% · … 25% · … 15%. Posição na
data de referência."). `calculations.py` ganhou as funções puras `index_band`/`health_band`
(a **situação** é o pior entre o SPI — faixas 0,95/0,90 — e o CPI — 0,98/0,93, como o
`faixaIndiceSaude` do protótipo) e `input_number`. A **ponderação**: `ponderation_view` (critérios
e notas vigentes, faixa de notas, pesos atuais e `can_save`), `ponderation_preview` (a fórmula do
dono, `financeiro.calculations.portfolio_weights`, com os orçamentos vigentes de
`current_budgets`, **sem gravar**; campo vazio ou inválido vale zero, como o protótipo) e
`save_ponderation` (valida a justificativa — mínimo 10 —, o peso de cada critério 0–100 com a
soma 100 pela mensagem do dono `portfolio_weights_error`, e a nota inteira na faixa; cria a
**versão nova** do grupo `portfolio` pela fachada do dono `configuracoes.save_parameter_group`
— que copia as notas da versão anterior — e **substitui na versão nova as notas digitadas** pela
função pública nova `configuracoes.replace_portfolio_grades`, com a trilha do que sai e do que
entra, tudo na transação da requisição; `rbac.require(Permission.MANAGE)` na fachada, além da
rota — Membro recebe 403). Rotas (`routes.py`): `GET /api/inicio/ponderacao` (READ, o modal no
alvo `ponderacao-modal`), `POST /api/inicio/ponderacao/previa` e `POST /api/inicio/ponderacao/gravar`
(MANAGE); a gravação responde **multi-alvo** (a marca `data-ponderacao-salva`, que o JS usa para
fechar o modal, e `#carteira-conteudo` com a carteira nova) com o toast no cabeçalho, e a recusa
(422 por campo, 403 e 5xx) fica só no modal (`x-target.422`/`x-target.error`), para não esvaziar a
carteira. O fragmento `home.html` ganhou a seção **Carteira de projetos** entre os indicadores e a
atenção (só no Portfólio), com o botão **Ponderação** quando `pode_ponderar`, a parcial
`_carteira.html` (peso com barra, avanço real x previsto, SPI/CPI com o tom de leitura, projeção
com o VAC inline — `+` no sobrecusto, como o protótipo —, término pela tendência com "LB", as
contagens, a situação e o "Abrir") e o rodapé "Portfólio" (peso 100,00%, somas e índices
consolidados); `ponderacao.html` (modal) e `ponderacao_salvo.html` (a resposta da gravação). A
tela (`home.js`): o modal pelo `TN.modal`, a **soma ao vivo** dos pesos e o fechamento pela marca;
`home.css`: a carteira e o modal. `export.py`: `_carteira_table` entra como **primeira tabela** do
`Document` no Portfólio (`per_project=False`, o código já vai no título da linha), com o VAC em
coluna própria. **Correções do fechamento (principal)**: o gate acusou cinco `var` novos no
`home.js` (`no-var`) — viraram `const`/`let`; a frase do LEIA-ME sobre o VAC no rodapé foi
corrigida (o VAC entra só na exportação); e as divergências foram registradas na tabela e no
histórico de `docs/DIVERGENCIAS-DO-PROTOTIPO.md`. O **oráculo** (`test_inicio_oraculo.py`) afirma
na demonstração os **pesos 55,36 / 29,34 / 15,30** (TN-2026-014/021/027, soma 100,00%) e a prévia
com os critérios vigentes os devolve iguais; a linha do projeto 1 fecha com 8 ações atrasadas,
SPI 0,94, CPI 0,96, 3 pedidos críticos, 2 riscos no topo e situação "Atenção", e o rodapé com o
orçamento de R$ 7,02 bi (44,6 + 18,2 + 7,4 mi). `ruff check`, `ruff format --check` e `ty check`
limpos; o subagente rodou 201 testes (início + configurações) ×2 e o oráculo; no fechamento a
suíte completa passou (**4.020 testes** em 17:55) e a porta de qualidade, **5/5**.

- DECISAO: cada célula da carteira pela fachada dona | peso de `portfolio_weights`, prazo de `planning_kpis_overview`, custo de `cost_kpis_overview`, riscos/pedidos/ações dos seus donos, por projeto no mesmo corte; os totais reusam os consolidados dos indicadores | D9, ISSUE-080
- DECISAO: situação pelo pior índice | as faixas do protótipo (SPI 0,95/0,90 e CPI 0,98/0,93) com `Em dia`/`Atenção`/`Crítico`, e a cor do SPI/CPI pela faixa de leitura (1,00/0,95) | D6, ISSUE-080
- DECISAO: gravação composta da ponderação | critérios pela `save_parameter_group` (a versão nova copia as notas) e as notas digitadas substituídas na versão nova pela `replace_portfolio_grades` pública nova, na mesma transação, com a trilha | D8, D9, ISSUE-080
- DECISAO: prévia pela fórmula do dono | `financeiro.calculations.portfolio_weights` com os orçamentos vigentes (`current_budgets`), sem gravar versão; campo vazio ou inválido vale zero | D9, ISSUE-080
- DECISAO: MANAGE na prévia e na gravação | `Access(module="inicio", permission=Permission.MANAGE)` na rota e `rbac.require` na fachada (defesa em profundidade); Membro recebe 403 e a leitura do modal segue READ | D7, ISSUE-080
- DECISAO: recusa só no modal | `x-target.422` e `x-target.error` apontam para `ponderacao-modal`; o sucesso responde a marca `data-ponderacao-salva` e a carteira (`#carteira-conteudo`), sem esvaziar alvo ausente | D11, ISSUE-080
- DECISAO: divergências registradas | término pela tendência em data completa (o protótipo usava o mês curto), "Abrir" navega por `data-tn-tela` (o protótipo trocava o escopo por JS) e o VAC entra em coluna própria na exportação (o protótipo o mostrava inline e não o somava) | Q31, ISSUE-080
- DECISAO: correção no fechamento | os cinco `var` do `home.js` viraram `const`/`let` (o gate acusou `no-var`) e a frase do LEIA-ME sobre o VAC no rodapé foi corrigida | ISSUE-080
