---
id: ISSUE-015
title: "Biblioteca de gráficos 2: cards, faixa de KPI, matrizes, heatmap, mapa de 52 semanas, quantitativos e etapas"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 2
onda: 4
blocked_by:
  - ISSUE-014
blocks:
  - ISSUE-016
labels:
  - ready-for-agent
source_requirements:
  - HU-032
  - HU-089
  - HU-102
  - HU-111
spec_decisions:
  - D11
---

# Biblioteca de gráficos 2: cards, faixa de KPI, matrizes, heatmap, mapa de 52 semanas, quantitativos e etapas

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D11.
> Entrega 2 (Plataforma no ar), onda 4 (Serviços transversais).
> Histórias: 32, 89, 102, 111. Bloqueada por: ISSUE-014.

## O que construir

Porta para a biblioteca, sobre o motor comum da ISSUE-014, os visuais **Card
Indicador Único**, **Card Indicador Único com detalhes** (com a referência de
gestão abaixo do valor), **HTML KPI Status**, **Matriz Formatada**, **Separação
Severidade Riscos**, **Tabela Heatmap**, **Mapa 52 semanas**, **Tabela
Quantitativos por entregável** e **Etapas**.

As faixas de cor do mapa de calor e da matriz P x I são refeitas nas famílias
do Design System (`ok`, `warn`, `erro`, `azul`, `frio`, `roxo`), mantendo o
sinal e o ícone além da cor (D1). Cada visual entra no styleguide de gráficos
com dados de exemplo.

## Critérios de aceite

- [x] Os nove visuais renderizam no styleguide com a aparência dos originais.
- [x] As faixas do heatmap e da matriz usam as famílias do Design System e mostram sinal e ícone além da cor.
- [x] Os cards mostram a referência de gestão (previsto, meta, linha de base) abaixo do valor.
- [x] Nenhuma cor fixa e nenhum erro no console.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Abrir o styleguide e comparar cada visual com o original. `npm run verificar`
passa.

## Decisões em aberto

Nenhuma.

## Notas

Mapeamento de uso da D11: cards no Início e nos painéis; heatmap no mapa de
controle, no dia x frente e no aging; Mapa 52 semanas no MAS e no plano de
quantidades; Etapas no processo de compra, na SM e na RNC.

## Registro de execução

Data: 06/10/2026 (conclusão da retomada; os visuais e o estilo vieram do trabalho anterior, que parou por limite de uso).

Feito: os nove visuais em `app/ds/graficos/` (`card-indicador`, `card-indicador-detalhes`, `kpi-status`, `severidade-riscos`, `tabela-heatmap`, `matriz-formatada`, `mapa-52-semanas`, `tabela-quantitativos`, `etapas`), sobre o motor da ISSUE-014, com as peças comuns em `pecas.js`, `cards.js` e `detalhe.js` e o estilo em `graficos-cartoes-e-tabelas.css` (`graficos.css` não foi tocado).
Ligados no `app/index.html` (o `<link>` e os 12 scripts, depois de `relogios.js` e antes de `shell.js`) e no `docs/styleguide-graficos.html`: uma seção por visual com o exemplo (números do original no Heatmap), a dica de uso, o contrato de dados e o começo do JSON; mais a tabela dos tons e a linha do último `grafico:selecionar`.
Faixas com ícone e nome: Heatmap (contagem e desvio da EAC, limites 1, 5 e 10 do protótipo), matriz P x I de ameaças e de oportunidades (escala de 4 faixas do protótipo, nas famílias ok, warn, laranja, erro, frio, azul e roxo) e Quantitativos. Cards com previsto, meta e linha de base abaixo do valor, com seta e sinal.
Conferências de fronteira das peças (faixa, estado pelos limites, percentual, diferença, soma e árvore) rodam ao abrir o styleguide, junto com as da ISSUE-014.
Pendências (orquestrador): `npm run verificar` (ESLint dos 12 JS e do CSS novos); abrir o styleguide ao lado de `docs/referencia/graficos/` para conferir a fidelidade visual e o console, porque nenhum visual rodou no navegador nesta execução (só `node --check`); a nota final do styleguide ainda cita a ISSUE-015 (a ISSUE-016 a ajusta); não há `LEIA-ME.md`, pois a biblioteca não é módulo (o contrato vive no styleguide e no cabeçalho de cada arquivo).
DECISÃO: Cor da letra nos visuais da ISSUE-015 | onde o original usava a cor forte da família como letra (valor, selo, contagem, estado), o porte usa o token escuro da mesma família (ok-800, warn-800, erro-700, azul-800, frio-700, roxo-700) ou o texto auxiliar do DS, para fechar 4,5:1; fundo, faixa, barra, ponto e traço seguem o token forte | D1, ISSUE-015
DECISÃO: Severidade de riscos | cartão de fundo suave, faixa forte em cima e texto escuro, no lugar do gradiente cheio com texto branco do original (só o vermelho e o roxo do DS passam de 4,5:1 com branco); geometria, tipografia e círculo do canto são os do original, com o vw trocado por --graf-u (1cqw) | D1, ISSUE-015
DECISÃO: Painel de detalhe dos gráficos | um painel só, feito de blocos (campos, textos, tabela, cartões) no TN.modal do DS, no lugar do modal próprio de cada original (Mapa 52, Etapas, Quantitativos), com os tamanhos de fonte do DS | D11, ISSUE-015
DECISÃO: Sinal além da cor nos mapas de calor | célula e legenda do Heatmap, da Matriz e dos Quantitativos levam o ícone da faixa e o nome para o leitor de tela; Etapas, Mapa 52 e cartões não levam ícone novo e usam legenda de pontos, como no original | D1, ISSUE-015
DECISÃO: Quantitativos sem ajuste automático de escala | o ajuste da escala ao quadro (fit) do original não foi portado; a tabela usa a escala maior do original, a compacta dentro de uma linha e, com altura fixa, rola por dentro com cabeçalho e total fixos | D11, ISSUE-015
DECISÃO: Extensões do contrato de dados | Heatmap aceita coluna sem calor (`calor: false`, total também sem pintar), só linha de total (`total.coluna: false`) e `cabecalho: "horizontal"`; Mapa 52 aceita `rotulo_total` na legenda e `depois_da_data` no chip; Etapas e Quantitativos mostram a data com o ano de quatro dígitos, como o original | D11, ISSUE-015
