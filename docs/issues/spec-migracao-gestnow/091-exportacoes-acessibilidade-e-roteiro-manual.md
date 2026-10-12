---
id: ISSUE-091
title: "Exportações tela a tela, acessibilidade e roteiro manual"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 9
onda: 19
blocked_by:
  - ISSUE-090
blocks:
  - ISSUE-092
labels:
  - ready-for-agent
source_requirements:
  - HU-136
  - HU-137
  - HU-138
spec_decisions:
  - D12
  - D1
---

# Exportações tela a tela, acessibilidade e roteiro manual

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D12, D1.
> Entrega 9 (Produto final), onda 19 (Validação final e Azure).
> Histórias: 136, 137, 138. Bloqueada por: ISSUE-090.

## O que construir

O **inventário de exportações** da D12 é conferido tela a tela e registrado em
`docs/` (cada tela, cada botão Excel e PDF, o teste que o cobre), e um teste
automatizado por tela confere que o Excel abre, tem as colunas da tabela e os
KPIs com referência, e que a versão imprimível renderiza sem navegação.

A passada de **acessibilidade** segue o `ACESSIBILIDADE.md` do Padrão
(teclado, foco, contraste, rótulos, ARIA), com as correções feitas aqui.

O **roteiro manual de aceite** para o dono do produto fica em `docs/`: passo a
passo por módulo, com o que fazer e o que deve aparecer, incluindo a revisão
do modelo de dados (Q30) e das divergências (Q31).

## Critérios de aceite

- [ ] O inventário lista todas as telas, e cada botão Excel e PDF tem teste.
- [ ] Os critérios de acessibilidade do Padrão passam.
- [ ] O roteiro manual cobre todos os módulos e as revisões pendentes do dono.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Rodar os testes de exportação por tela e a porta de qualidade; conferir o roteiro contra a lista de navegação.

## Decisões em aberto

Nenhuma.

## Notas

Testing Decisions da spec: "Exportações".

## Registro de execução

Fatia entregue em 12/10/2026, em três frentes. **Exportações**: o inventário da D12 virou
`docs/EXPORTACOES.md` (68 entradas — 50 telas da navegação, a página de exemplo, as abas de
ficha e 11 modelos de importação; 125 linhas de rota: 68 Excel + 56 imprimíveis + 1 Imprimir/PDF
do relatório), e um teste parametrizado por rota
(`api/tests/plataforma/test_exportacoes_por_tela.py`, 74 casos) confere que o Excel abre com as
colunas de cada tabela na ordem e os KPIs com a referência de gestão, que o imprimível sai sem
navegação e que nenhum botão das views/templates fica fora do inventário (66 botões Excel + 60
PDF varridos; rota registrada fora do inventário também reprova). **Acessibilidade**:
`scripts/acessibilidade.mjs` (axe-core 4.13.0 como devDependency, injetado por Playwright;
regras do Padrão) audita 51 telas com Admin em 1280 e 760 px, as 5 da Programação com Fornecedor
e faz a passada de teclado em 1280 (3.226 paradas de Tab). A primeira rodada achou 261 nós em 4
regras (contraste em 38 telas, região rolável sem foco, barra do Voltar fora de landmark,
landmark duplicado); as correções foram de token (`tokens.css`, `shell.css`, `patterns.css`,
gráficos, `licoes.css`) e de estrutura (`rolagem.js` novo dá foco ao `.tbl-wrap` que rola;
Voltar virou `<nav aria-label>`), e a rodada final fecha **112 telas, 0 violações**.
**Roteiro**: `docs/ROTEIRO-DE-ACEITE.md` cobre os 10 módulos e as 51 telas com o que fazer e o
que deve aparecer, e fecha com as revisões do dono (Q30, Q31), as pendências de fonte e a
publicação; um teste de guarda confere a cobertura contra `navegacao.json`. **Correção de
paridade**: o Início não tinha entrada para o relatório gerencial (o protótipo tinha o botão na
barra) — ganhou o botão **Relatório gerencial** ao lado do Excel/PDF, abrindo a tela já com o
modal de emissão. **Testes**: escopo do subagente 1.142 passed ×2 (exportações) + 224 passed no
escopo final (plataforma + início); o principal rodou a **suíte completa (4.235 passed**,
29:09), a **varredura (459/459**, 433 s), a **acessibilidade (112/112)** e a porta de qualidade
(**5/5**). Ambiente: os hosts 7071 (que estava em `Error`) e 7072 foram reiniciados com o venv e
o código atual; a varredura inicial acusou 84 links "quebrados" que eram o proxy de revisão
seguindo o 302 do gate de fragmento — o proxy foi corrigido para relayar 3xx como o par da 090.

- DECISAO: inventário | o inventário de exportações lista tela a tela os botões Excel/PDF e os modelos de importação, e um teste por rota confere as colunas, os KPIs com referência e o imprimível sem navegação, com a cobertura varrida das views e dos templates | D12, ISSUE-091
- DECISAO: acessibilidade | a passada usa axe-core 4.13.0 via Playwright nas regras do Padrão, mais a auditoria de teclado; as correções foram de token (contraste) e de estrutura (foco na região rolável, Voltar em landmark) | D1, ISSUE-091
- DECISAO: roteiro | o roteiro manual cobre os 10 módulos e as 51 telas e fecha com as revisões do dono (Q30, Q31), as pendências de fonte e a publicação; um teste de guarda confere a cobertura contra a lista de navegação | Q30, Q31, ISSUE-091
- DECISAO: entrada do relatório | o Início ganhou o botão Relatório gerencial na barra de contexto (como o protótipo), abrindo a tela já com o modal de emissão | D12, ISSUE-091
