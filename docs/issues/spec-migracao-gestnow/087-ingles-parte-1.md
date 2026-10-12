---
id: ISSUE-087
title: "Inglês, parte 1: catálogo no servidor, seletor PT | EN, shell, Início, Central, Governança e Financeiro"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 9
onda: 18
blocked_by:
  - ISSUE-086
  - ISSUE-078
blocks:
  - ISSUE-088
labels:
  - ready-for-agent
source_requirements:
  - HU-017
spec_decisions:
  - D13
---

# Inglês, parte 1: catálogo no servidor, seletor PT | EN, shell, Início, Central, Governança e Financeiro

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D13.
> Entrega 9 (Produto final), onda 18 (Idioma).
> Histórias: 17. Bloqueada por: ISSUE-086, ISSUE-078.

## O que construir

O alternador PT | EN do protótipo volta, com tradução **no servidor** por um
catálogo de mensagens alimentado pelo dicionário `en.js` do protótipo. O
catálogo tem namespace por módulo, o que resolve as colisões do dicionário
plano do protótipo (Prazo, Desvio, Emissão). O seletor de idioma fica na barra
lateral, e a escolha é lembrada.

Terminologia em inglês do protótipo: EAP vira WBS, SM vira CR, EAC vira CBS,
FP vira PF, CP vira PC, S39 vira W39, e as datas curtas seguem o idioma.
Gráficos, Excel e PDF usam o mesmo catálogo. Dados cadastrados não são
traduzidos.

Esta parte cobre o shell, a navegação, os estados de tela, o Início e os
módulos Central de Ações, Governança e Financeiro.

## Critérios de aceite

- [ ] Trocar o idioma muda tela, gráfico, Excel e PDF das áreas desta parte.
- [ ] Dado cadastrado continua no idioma em que foi gravado.
- [ ] As colisões do dicionário antigo não aparecem (cada módulo com o seu termo).
- [ ] A escolha do idioma é lembrada entre as telas.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Teste que confere que toda chave usada nas áreas desta parte tem tradução, e revisão de tela em EN.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `js/i18n.js` e `js/i18n/en.js` do protótipo; README, seção 6.2 e as notas de tradução de cada módulo.

## Registro de execução

Fatia entregue em 11/10/2026: o **catálogo no servidor**, o **seletor PT | EN** e o inglês do shell,
da navegação, dos estados de tela, do Início, da Central de Ações, da Governança e do Financeiro.
O `api/src/core/translations.py` nasceu com **2.517 entradas** em namespace por módulo (shell 132,
comum 294, inicio 176, central_acoes 351, governanca 671, financeiro 866, graficos 16, exportacao
11), extraídas do `en.js` do protótipo (os blocos por área e as seções "Estrutura e navegação",
"Componentes" e "Home"; os padrões regex ficaram de fora — a composição no GestNow acontece com o
`t()` nas partes). O namespace **resolve as colisões** do dicionário plano do protótipo, onde a
última chave vencia: "Prazo" da Central é "Due date" e o da Governança é o termo do bloco 08;
"Mensal" do Financeiro é "Monthly", não o minúsculo do 05. A tradução acontece **no servidor**:
`translate` devolve o texto intacto em pt (identidade — nenhum teste existente mudou) e o `t`, o
`idioma`, o `data` e o `data_hora` entram no contexto pelo `AlpineAjaxResponse` (e na impressão),
de modo que todo fragmento escreve `{{ t('financeiro', 'Resumo') }}` sem mudar assinatura de rota.
A navegação inteira (títulos de módulo e tela de todos os módulos, abas, Voltar, opções de escopo
compostas, cartão do usuário, rótulos) é traduzida pelo `navigation_view.build(..., idioma=)`. O
idioma vive no cookie `gestnow_idioma` (HttpOnly, 1 ano), gravado por `POST /api/idioma` (rota
`switch_language`, molde da troca de perfil, 422 em texto para valor desconhecido); o seletor
PT | EN fica na barra lateral e recarrega a página, como o protótipo. As **views estáticas**
continuam estáticas: a barra lateral leva `data-idioma` e `data-textos` (só as chaves que os
arquivos estáticos usam, com lista explícita e teste de cobertura) e o novo `app/ds/i18n.js`
(`TN.i18n.aplicar`/`traduzirView`, `TN.t`) aplica os `data-i18n*` depois de cada view; os textos
fixos da DS (`ui.js`, `shell.js`, motor dos gráficos) passam por `TN.t`. Datas seguem o idioma
(`format_date`, `mes_curto`, `data()` no contexto — 13 templates de Governança e Financeiro
deixaram o `strftime` inline); número e moeda continuam pt-BR/R$. Os **gráficos** recebem os
`rotulos` do motor resolvidos no `data-dados` (`rotulos_de_grafico`); o **Excel e o PDF** usam o
`Document.idioma` (e o `namespace` novo, que traduz títulos e colunas de todos os documentos)
para abas, cabeçalhos canônicos ("Resumo", "Indicador/Valor/Referência/Situação", "Escopo",
"Gerado em", "Página X de Y"). Os `LEIA-ME.md` das quatro áreas ganharam a seção "Idioma
(ISSUE-087)". **Divergências registradas**: as colisões do dicionário plano, o número e a moeda
que ficam pt-BR e as mensagens de recusa compostas com dado, que ficam em PT nesta fatia.
**Testes**: `test_traducoes.py` (motor, colisões, terminologia e a varredura "toda chave usada
tem tradução" — views, JS, templates e Python das áreas) e `test_idioma_nas_areas.py` (navegação,
fragmentos das quatro áreas, impressão, Excel, dado cadastrado intocado, rota do idioma) — 39
novos. O subagente rodou o escopo duas vezes (**2.156 passed** em cada); o principal revisou os
diffs, corrigiu três apontamentos do gate (atributo duplicado em `contrato.html`, atribuição
inútil no `shell.js` e o `t` no título/rótulo do acesso negado), rodou a **suíte completa (4.074
passed**, 19:35) e a porta de qualidade (**5/5**).

- DECISAO: catálogo no servidor | `api/src/core/translations.py` com namespace por módulo e chave = texto PT normalizado; em pt `translate` devolve o texto intacto; o `t`/`idioma`/`data` entram no contexto pelo `AlpineAjaxResponse` e pela impressão | D13, ISSUE-087
- DECISAO: views estáticas | as views continuam fragmentos estáticos: a barra lateral leva `data-idioma` e `data-textos` (mapa resolvido só das chaves estáticas) e o `TN.i18n` aplica os `data-i18n*` depois de cada view | D13, ISSUE-087
- DECISAO: cookie e rota | `gestnow_idioma` (HttpOnly, 1 ano) com `POST /api/idioma`; o seletor PT | EN na barra lateral recarrega a página | D13, ISSUE-087
- DECISAO: datas e números | as datas seguem o idioma (`format_date`, `mes_curto`, `data()`); número e moeda continuam pt-BR/R$ nesta fatia | ISSUE-087
- DECISAO: colisões | cada módulo com o seu termo (Prazo da Central "Due date" × o da Governança; Mensal do Financeiro "Monthly" × o minúsculo do 05 que corrompia o protótipo) | D13, ISSUE-087
- DECISAO: gráficos | os `rotulos` do motor viajam no `data-dados` resolvidos pelo servidor, mesclados aos específicos da tela | ISSUE-014, ISSUE-087
- DECISAO: recusas compostas | as mensagens de validação compostas com dado ficam em PT no inglês nesta fatia; as estáticas são traduzidas no render | ISSUE-087, ISSUE-088
- DECISAO: navegação inteira | a navegação (todos os módulos da sidebar, abas, título e Voltar) é traduzida já nesta fatia, embora só as quatro áreas estejam completas | ISSUE-087, ISSUE-088
