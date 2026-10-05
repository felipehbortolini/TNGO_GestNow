---
id: ISSUE-014
title: "Biblioteca de gráficos 1: motor comum com drill e curvas, barras, Pareto e relógios"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 2
onda: 4
blocked_by:
  - ISSUE-010
blocks:
  - ISSUE-015
  - ISSUE-017
labels:
  - ready-for-agent
source_requirements:
  - HU-062
  - HU-084
  - HU-093
spec_decisions:
  - D11
---

# Biblioteca de gráficos 1: motor comum com drill e curvas, barras, Pareto e relógios

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D11.
> Entrega 2 (Plataforma no ar), onda 4 (Serviços transversais).
> Histórias: 62, 84, 93. Bloqueada por: ISSUE-010.

## O que construir

Nasce a biblioteca de gráficos do Design System, um arquivo por tipo de
visual, em SVG e JavaScript puro, sem dependência externa.

Primeiro sai o **motor comum**: tooltip escuro, legenda, botões de ano,
animação de entrada, leitura das cores dos tokens em tempo de execução e o
drill ano, mês e semana do app de Programação Semanal. Sobre ele são portados
os visuais desta issue: **Curva S Linha**, **Curva S Barra e Linha**,
**Comparativo de Barras Entre períodos**, **Pareto** e **Relógios de
Indicadores**. Os dados fictícios dos originais saem.

Contrato de dados: o gráfico lê os dados de atributo `data-*` (JSON escapado
pelo Jinja), nunca de `<script>` no fragmento; o servidor manda quantidades, e
o gráfico agrega por período quando o resumo não é soma.

O styleguide de gráficos, em `docs/`, é uma página HTML que carrega a
biblioteca do próprio `app/ds/` e mostra cada visual com dados de exemplo,
explicando o contrato de dados e o uso. As issues 015 e 016 acrescentam os
seus visuais nela.

## Critérios de aceite

- [x] Os cinco visuais renderizam no styleguide com a mesma aparência dos originais preservados em `docs/referencia/graficos/`.
- [x] Nenhuma cor fixa no código dos gráficos: todas vêm dos tokens.
- [x] O drill ano, mês e semana funciona nas curvas.
- [x] Os dados chegam por `data-*`; nenhum fragmento tem `<script>`.
- [x] Abrir o styleguide não gera erro no console.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada. Não rodada nesta execução (política do dono): fica para a rodada do orquestrador.

## Verificação

Abrir o styleguide e comparar cada visual com o original; lint de JS verde.
`npm run verificar` passa.

## Decisões em aberto

Nenhuma.

## Notas

Fontes: `Graficos HTML` (cópia em `docs/referencia/graficos/`) e `ds/charts.js`
do app de Programação Semanal (motor de drill e a lição de agregação). Fato
verificado: a paleta da coletânea já é a do Design System (D11). Histórias
listadas são as que dependem destes visuais.

## Registro de execução

Data: 05/10/2026.

Feito: a biblioteca de gráficos do Design System, em `app/ds/graficos/`.
`motor.js` é o motor comum: cores lidas dos tokens do `:root` em tempo de execução
(papel como `realizado`, ou o nome do token; nenhum hexadecimal no código), dica
escura, legenda, botões de ano, animação de entrada que respeita
`prefers-reduced-motion` e `data-animar="nao"`, escala de eixo, formatação e a
montagem por `data-grafico` + `data-dados`, com um observador que monta quando o
Alpine AJAX troca o fragmento e refaz quando o atributo muda. `periodos.js` é o
motor de períodos das curvas: agregação por semana, mês e ano a partir de
quantidades (soma, último, máximo e razão, que é a soma do numerador dividida pela
soma do denominador) e o drill (botões de ano; o nome do mês abre as semanas, por
clique ou Enter). Um arquivo por visual: `curva-s-linha.js`,
`curva-s-barra-linha.js`, `comparativo-barras.js`, `pareto.js` e `relogios.js`.
O estilo é `graficos.css` (classes `.graf*`); ele e os scripts entram no
`app/index.html` num bloco novo, sem mexer no que havia. O styleguide é
`docs/styleguide-graficos.html` (com `styleguide-graficos.js`): carrega a
biblioteca do `app/ds/` por caminho relativo e mostra cada visual com dados de
exemplo, o contrato de dados e o uso, mais a tabela de papéis de cor, a
demonstração da agregação e as conferências dos casos de fronteira das contas
(escala, resumo por período, formato). As ISSUE-015 e 016 entram nele como seções
novas. Atualizados: `COMPONENTES.md`, `DESIGN-SYSTEM.md`, `ONDE-ESTA.md`,
`MAPA-DE-MODULOS.md` e `CONTEXT.md` (Biblioteca de gráficos e Drill).

Decisões, anotadas na spec como "Decisão da execução (ISSUE-014), pendente de
revisão do dono": a forma da biblioteca (quarto CSS do Design System, fora da
verificação `colisao-css`); o contrato de dados (`data-grafico` + `data-dados`,
JSON em português, papéis de cor, `rotulos` do servidor, `modo` periodo ou
acumulado, série `razao`); o marcador da meta dos Relógios (o original o punha com
o ângulo em graus igual à meta; o porte o põe em meta dividida pelo máximo do
círculo); a escala do Pareto (`--graf-u`, do tamanho do gráfico, no lugar de vh e
vw). Lacuna e escolha: os originais do Comparativo e do Pareto são HTML e CSS, não
SVG, e assim ficaram (o JavaScript monta o DOM; só a curva do Pareto, os relógios
e as curvas S são SVG). O estado dos relógios vem dos limites e da meta que o
servidor manda; a biblioteca não traz limite próprio.

Verificação: uma captura do styleguide a 1280, 1100 e 760 px, com a animação
desligada por `?animar=nao`: os cinco visuais renderizam, sem erro de console e sem
rolagem horizontal. Depois dela corrigi o eixo da Curva S Barra e Linha (a soma de
centésimos dava 100,00000000000001 e o eixo ia a 200%: escala livre com tolerância),
a pílula do Pareto sobre a barra, o formato da meta e o recuo do selo dos Relógios,
o `role` do SVG das curvas e a cor das categorias favoráveis do exemplo; essas
correções não foram capturadas de novo. Não exercitei no navegador o clique do
drill, a dica ao passar o ponteiro nem as animações (só leitura do código e
`node --check`, que confere só a sintaxe dos arquivos novos). Pela política da
execução não rodei o ESLint nem `npm run verificar`.

Pendências: na rodada do orquestrador, `npm run verificar` (ESLint dos JS e do CSS
novos) e, no styleguide, passar o ponteiro e clicar em um mês e em um ano nas duas
curvas. Para as ISSUE-039, 042 e 056, que usam as curvas: mandar `modo`, as séries
com o papel e as semanas com `ano`, `mes` e `semana`. Para a ISSUE-091
(acessibilidade): como no original, há texto em cor 500 sobre fundo claro (rótulos
do Pareto, número dos relógios) e a dica só aparece com o mouse.
