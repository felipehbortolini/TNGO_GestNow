---
id: ISSUE-090
title: "Varredura de todas as telas nas três larguras"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 9
onda: 19
blocked_by:
  - ISSUE-089
blocks:
  - ISSUE-091
labels:
  - ready-for-agent
source_requirements:
  - HU-005
  - HU-006
  - HU-020
spec_decisions:
  - D2
  - D3
---

# Varredura de todas as telas nas três larguras

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D2, D3.
> Entrega 9 (Produto final), onda 19 (Validação final e Azure).
> Histórias: 5, 6, 20. Bloqueada por: ISSUE-089.

## O que construir

A varredura de telas vira teste automatizado com Playwright (precedente: o
`_dev/crawl.py` do protótipo, preservado em `docs/referencia/prototipo/`): abre
cada tela da lista de navegação em 1280, 1100 e 760 px, com os perfis Admin,
Visualizador e Fornecedor, e reprova console com erro, rolagem horizontal,
barra lateral ausente ou oculta, tela sem estilo próprio (classe raiz e CSS da
página aplicados) e link quebrado. Playwright e o navegador dele entram como
dependência de desenvolvimento.

O que a varredura encontrar é corrigido nesta issue.

## Critérios de aceite

- [ ] A varredura cobre todas as telas da lista de navegação nas três larguras e nos três perfis.
- [ ] Nenhuma tela reprova em console, rolagem, barra lateral, estilo ou link.
- [ ] O fornecedor só alcança as telas da Programação Semanal.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Rodar a varredura (comando documentado no README) e a porta de qualidade.

## Decisões em aberto

Nenhuma.

## Notas

Testing Decisions da spec: "Varredura de telas".

## Registro de execução

Fatia entregue em 12/10/2026: a varredura de telas virou teste automatizado com Playwright
(`scripts/varredura-telas.mjs`, precedente do `_dev/crawl.py` do protótipo). Abre cada tela da
lista de navegação (`api/src/core/navegacao.json`, 51 telas) em 1280, 1100 e 760 px, com os
perfis Admin, Visualizador e Fornecedor, e reprova console com erro, rolagem horizontal, barra
lateral ausente ou oculta (em 1280 a barra cheia; em 1100 e 760 o trilho, que nunca some), tela
sem estilo próprio (classe raiz e CSS da página) e link quebrado (`a[href]` de mesma origem
responde < 400 e `data-tn-tela` aponta tela conhecida). O Playwright e o navegador dele entram
como dependência de desenvolvimento (`devDependencies` + `npx playwright install chromium`); o
comando está no `npm run varredura` e na seção "Varredura de telas" do README. A primeira
rodada reprovou 30 das 459 navegações (84 falhas: 63 de console, 9 de estilo, 9 de conteúdo e 3
de permissão) e tudo foi corrigido nesta issue: as telas de detalhe sem parâmetro no endereço
(`central_acoes/ata`, `financeiro/contrato`, `riscos/ficha` e `governanca/mudanca`) disparavam
as chamadas da ficha e recebiam 404/422 — agora mostram o vazio de origem (mesmo padrão das
demais telas), sem sujar o console; e a expectativa do script espelha o RBAC real
(`api/src/core/rbac.py`): o fornecedor só alcança a Programação Semanal (e o Início o entrega
lá, `navigation_view._position`) e o Visualizador não abre Configurações. A rodada final passou
**459/459** navegações (424 s). O teste que bania bibliotecas de PDF por nome
(`api/tests/plataforma/test_ativos_da_exportacao.py`) passou a ler o `package.json` estruturado
e tolera o Playwright **só** em devDependencies — o servidor e as dependências de execução
seguem banidos. **Testes**: escopo do subagente (plataforma + central_acoes + financeiro +
riscos + governanca) com **2.286 passed**; o principal rodou a **suíte completa (4.095
passed**, 19:48) e a porta de qualidade (**5/5**). Operacional: a varredura rodou contra o host
7072 e o proxy 4281 (o host 7071 estava em `Error` de um boot antigo e não recarrega sozinho —
reiniciar para o `npm run varredura` sem `--base`).

- DECISAO: varredura | o teste automatizado percorre as 51 telas × 3 larguras × 3 perfis pela lista de navegação e reprova console, rolagem, barra, estilo e link; Playwright como dependência de desenvolvimento | D2, D3, ISSUE-090
- DECISAO: telas de detalhe | sem o parâmetro no endereço, ata, contrato, ficha e mudança mostram o vazio de origem em vez de disparar chamadas que responderiam 404/422 | D2, ISSUE-090
- DECISAO: playwright × D12 | o teste das bibliotecas de PDF lê o package.json estruturado e tolera o playwright só em devDependencies; o servidor e as dependências de execução seguem banidos | D12, ISSUE-090
- DECISAO: expectativa de perfil | a varredura espelha o rbac: fornecedor só a Programação Semanal (o Início o entrega lá) e o Visualizador não abre Configurações | D7, ISSUE-090
