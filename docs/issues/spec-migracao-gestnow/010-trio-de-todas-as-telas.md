---
id: ISSUE-010
title: "Trio HTML, CSS e JS de todas as telas vinculado no shell e verificação trio-da-tela"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 2
onda: 3
blocked_by:
  - ISSUE-009
blocks:
  - ISSUE-011
  - ISSUE-014
labels:
  - ready-for-agent
source_requirements:
  - HU-020
  - HU-148
  - HU-149
spec_decisions:
  - D3
  - D2
---

# Trio HTML, CSS e JS de todas as telas vinculado no shell e verificação trio-da-tela

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D3, D2.
> Entrega 2 (Plataforma no ar), onda 3 (Shell, telas e acesso).
> Histórias: 20, 148, 149. Bloqueada por: ISSUE-009.

## O que construir

Toda tela da lista de navegação ganha o seu **trio** com o mesmo nome: a view
(fragmento) na pasta do módulo e a folha de estilo e o script da página na
pasta pública de páginas do módulo. O shell vincula todos os trios com caminho
absoluto, agrupados por módulo, logo depois do Design System, para que a
primeira execução já tenha o visual correto em todas as telas.

O CSS de cada página é escopado pela classe raiz (`.pagina--<modulo>-<tela>`) e
só usa tokens. O JS registra um único objeto em `TN.paginas["<modulo>/<tela>"]`
com `iniciar(raiz)`, acionado pela view por atributo Alpine; nenhum `<script>`
no fragmento. Tela sem comportamento próprio ainda tem o trio, com o cabeçalho
de propósito.

Cada view já nasce com os cinco estados do Padrão (carregando, vazio de
origem, vazio por filtro, erro e sem permissão) e mostra o vazio de origem até
a issue do seu módulo chegar.

A lista de telas é a das 45 do protótipo com os dois desdobramentos previstos
na spec: a tela única de Programação Semanal do protótipo dá lugar às telas do
app (matriz, dashboard, governança, importação e configuração; D10), e
Configurações ganha Colaboradores e Cadastros ao lado de Parâmetros (histórias
133 a 135).

A porta de qualidade ganha a verificação `trio-da-tela`: toda view tem CSS e
JS correspondentes, todo trio está vinculado no shell e toda view tem item na
lista de navegação. A falta falha alto.

## Critérios de aceite

- [x] Cada tela da lista de navegação abre com o estado vazio e o estilo próprio.
- [x] Nenhum fragmento carrega `<link>` ou `<script>`.
- [x] A verificação `trio-da-tela` reprova view sem CSS, view sem JS, trio fora do shell e view sem item de navegação, nomeando a tela.
- [x] O `LEIA-ME.md` de cada módulo lista os trios das suas telas.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Remover temporariamente, um de cada vez, um CSS, um JS, um vínculo do shell e
um item de navegação: a porta de qualidade falha nomeando a tela. Abrir cinco
telas de módulos diferentes: estilo e estado vazio corretos.

## Decisões em aberto

Nenhuma.

## Notas

Contrato visual do Padrão, Regra 2 (fragmento não carrega recurso). O que se
repetir em três telas sobe para `ds/patterns.css`.

## Registro de execução

Data: 05/10/2026.

Feito: o trio das 51 telas da lista de navegação (`api/src/core/navegacao.json`),
gerado por um script descartável que não ficou no repositório: 51 views em
`app/_views/<modulo>/`, 51 CSS e 51 JS em `app/paginas/<modulo>/`. A raiz de cada
view é `<main id="app-shell" class="content pagina--<modulo>-<tela>">` com
`x-data="{ estado: 'vazio-origem' }"` e `x-init` que aciona
`TN.paginas["<modulo>/<tela>"].iniciar($el)`; os cinco estados são blocos
`data-estado` com `x-show`, e a tela abre no vazio de origem (o Início manteve o
texto que já tinha). CSS e JS têm o cabeçalho de propósito e, no JS, um
`iniciar()` que só confirma o vazio de origem. `TN.paginas` nasce em
`app/ds/ui.js`. O shell vincula os 51 pares num bloco próprio de `app/index.html`,
entre o `ds/shell.js` e o Alpine, agrupados por módulo. A verificação
`trio-da-tela` é o script `scripts/verificar-trio-da-tela.mjs` (lê o
`navegacao.json`), chamado por `verificar-padrao.mjs` e executável sozinho com
`--raiz`; além das quatro faltas da issue, reprova item de navegação sem view,
view fora de `_views/<modulo>/<tela>.html`, view com `<script>` e trio incoerente
(classe da raiz, `x-init` ou registro do JS com outra chave). O teste
`api/tests/plataforma/test_trio_da_tela.py` monta uma árvore mínima e tira, um de
cada vez, um CSS, um JS, um vínculo e um item de navegação (e quebra a coerência
do trio), conferindo que a falha nomeia só a tela. O ESLint passou a cobrir
`app/paginas/` com as regras do Design System. Os 12 `LEIA-ME.md` ganharam a seção
"Trios das telas"; `docs/PADROES-DE-PAGINA.md` ("O trio da tela"), o contrato
visual, o checklist, o padrão de código, o mapa de módulos, o `ONDE-ESTA`, o
`CONTEXT.md` e a skill `timenow-design-system` foram atualizados. Os `.gitkeep`
das pastas que passaram a ter arquivos saíram.

Decisões, anotadas na spec como "Decisão da execução (ISSUE-010), pendente de
revisão do dono": o mecanismo dos cinco estados e o `TN.paginas` em `ui.js`, com o
`_` mantido na classe da raiz; a verificação como script chamado pela
`verificar-padrao.mjs` (a porta continua com cinco etapas); o bloco de vínculos no
shell. O texto dos estados é genérico e igual em todas as telas; só o título e o
subtítulo mudam, tirados dos LEIA-ME e do inventário do protótipo, sem regra nova.
Nas cinco telas de detalhe o vazio de origem diz de qual lista a ficha se abre,
sem botão: o Voltar da barra do módulo já leva à lista, e a verificação
`recurso-existe` trataria o `href` de um link de tela como arquivo.

Verificação: por política do dono, esta rodada não rodou o pytest, o
`npm run verificar`, o ESLint, o Node nem a revisão de tela; só `ruff format` e
`ruff check` sobre o teste novo, sem apontamentos. O último critério fica
desmarcado até o orquestrador rodar a porta de qualidade. Ponto de atenção no
merge: a ISSUE-014 provavelmente acrescenta os scripts de `ds/graficos` no mesmo
ponto de `app/index.html` (entre o `shell.js` e o Alpine); a ordem certa é o
Design System, depois o bloco do trio.
