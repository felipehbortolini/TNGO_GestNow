---
id: ISSUE-016
title: "Biblioteca de gráficos 3: Gantt, calendário, galeria, cards de formulário, áreas, tabelas formatadas e os visuais novos"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 2
onda: 4
blocked_by:
  - ISSUE-015
blocks:
  - ISSUE-019
  - ISSUE-023
  - ISSUE-029
  - ISSUE-044
  - ISSUE-045
  - ISSUE-051
  - ISSUE-064
  - ISSUE-072
labels:
  - ready-for-agent
source_requirements:
  - HU-064
  - HU-095
  - HU-122
spec_decisions:
  - D11
---

# Biblioteca de gráficos 3: Gantt, calendário, galeria, cards de formulário, áreas, tabelas formatadas e os visuais novos

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D11.
> Entrega 2 (Plataforma no ar), onda 4 (Serviços transversais).
> Histórias: 64, 95, 122. Bloqueada por: ISSUE-015.

## O que construir

Completa a coletânea na biblioteca: **Gráfico Gantt**, **HTML Calendário**,
**Galeria**, **Formulário de Cards**, **Gráfico de Áreas de Avaliação**,
**Tabela formatada**, **Tabela Formata 2** e **Tabela Etapa por etapa**.

E constrói, no mesmo padrão visual (tipografia, tooltip escuro, legenda, botões
de ano, animação de entrada), os quatro visuais que a coletânea não tem:
**pirâmide de segurança dupla** (mês x acumulado, com a proporção de
referência Bird ou Heinrich), **cascata de valor do contrato**, **rosca de
distribuição** e **linhas múltiplas** (TF e TRIF, CPI e SPI mês a mês).

O styleguide de gráficos fica completo, com a tabela de mapeamento da D11
("necessidade no GestNow" para "visual") e o exemplo de cada um.

## Critérios de aceite

- [x] Os oito visuais da coletânea renderizam no styleguide com a aparência dos originais.
- [x] Os quatro visuais novos seguem tipografia, tooltip, legenda e animação da coletânea.
- [x] O styleguide traz os 22 visuais da coletânea e os 4 novos, com a tabela de mapeamento da D11.
- [x] Nenhuma cor fixa e nenhum erro no console.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Abrir o styleguide completo e comparar com os originais. `npm run verificar`
passa.

## Decisões em aberto

Nenhuma.

## Notas

Fonte da pirâmide dupla: `GI.charts.pyramidPair` do protótipo (faixas de
altura fixa, rótulos na coluna central, proporção real abaixo de cada pirâmide,
referência no rodapé), redesenhada no padrão da coletânea.

## Registro de execução

Data: 06/10/2026 (retomada de uma execução interrompida por limite de uso).
Feito: os 12 visuais em `app/ds/graficos/` (gantt, calendario, galeria, formulario-cards, areas-avaliacao, tabela-formatada, tabela-formatada-2, tabela-etapa-por-etapa, piramide-seguranca, cascata-contrato, rosca, linhas-multiplas) mais `apoio.js` (datas ISO, lupa, seta e camadas dos originais, barra de busca, tons) e o estilo `graficos-3.css` (só tokens, sem cor fixa nem `!important`).
Feito: `docs/styleguide-graficos.html` e `.js` com as 12 seções (14 exemplos: a pirâmide em Bird e Heinrich, as linhas em TF e TRIF e em CPI e SPI), o contrato de dados de cada uma, 44 casos de fronteira novos (todas as fórmulas com nome: `situacaoDaAcao`, `proporcaoReal`, `agrupar`, `zonaDoValor`...) e a seção `#mapeamento` com a tabela da D11 (15 linhas mais os 4 visuais novos) e a contagem de visuais com exemplo na página. `app/index.html` carrega o CSS e os scripts num bloco novo.
Feito: conferido sem navegador (cálculo em Node): os 44 casos passam; com um DOM mínimo, os 14 exemplos montam, os 996 ouvintes de evento rodam e as 60 conferências da página passam, sem exceção nem `console.error`; complexidade (máx. 12), parâmetros e demais regras de clean code conferidos por script próprio.
Pendências: captura única do styleguide ao lado dos originais (`docs/referencia/graficos/`) e leitura do console no navegador; `npm run verificar` (orquestrador).
Pendências: ao integrar depois da ISSUE-015, juntar os blocos próprios (CSS e scripts entre `pareto.js` e `relogios.js`; seções entre "Papéis de cor" e "Conferências"; funções dos exemplos depois do objeto `EXEMPLOS`) e reescrever a nota final do styleguide ("Próximos visuais...").

DECISÃO: CSS dos visuais da ISSUE-016 | arquivo próprio `app/ds/graficos/graficos-3.css`, carregado depois do `graficos.css`, para as ISSUE-015 e 016 não editarem o mesmo CSS | D11, ISSUE-016
DECISÃO: prefixo da Tabela Formata 2 | classes `graf-tabela2` no lugar de `graf-mapa`, que colidia com o Mapa 52 semanas da ISSUE-015; o ícone de apoio é `graf-desenho` pelo mesmo motivo | D11, ISSUE-016
DECISÃO: ícones dos originais | a lupa, a seta de voltar e as camadas são os SVG dos originais (apoio.js); o glifo ☌ da busca do Formulário de Cards vira a lupa SVG da Tabela formatada, porque o glifo depende da fonte do sistema | D11, ISSUE-016
DECISÃO: Gantt | a zebra da lista e a do calendário sombreiam as mesmas linhas (o original as desencontrava por contar filhos diferentes) e o 24vw da lista vira 24% da largura do visual (`--graf-u`) | D11, ISSUE-016
DECISÃO: acréscimos ao original | dica escura no Gantt, no Calendário e nas Áreas, legenda das situações no Calendário e botões de ano nas Áreas (o original tem botões de unidade estáticos) | D11, ISSUE-016
DECISÃO: Áreas de Avaliação em pixels | o original desenha num viewBox de 1150 que escala o texto com a largura; o porte desenha em pixels reais, como as curvas da ISSUE-014 | D11, ISSUE-016
DECISÃO: Tabela Etapa por etapa | o detalhe das ações abre numa sobreposição dentro do próprio visual (o original usa modal fixo na página); a situação da ação sai das datas, do estado e do `hoje` que o servidor manda; os rótulos do cartão e os filtros viram `marcadores` do dado | D11, ISSUE-016
