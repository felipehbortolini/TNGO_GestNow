---
id: ISSUE-010
title: "Trio HTML, CSS e JS de todas as telas vinculado no shell e verificação trio-da-tela"
status: in-progress
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

- [ ] Cada tela da lista de navegação abre com o estado vazio e o estilo próprio.
- [ ] Nenhum fragmento carrega `<link>` ou `<script>`.
- [ ] A verificação `trio-da-tela` reprova view sem CSS, view sem JS, trio fora do shell e view sem item de navegação, nomeando a tela.
- [ ] O `LEIA-ME.md` de cada módulo lista os trios das suas telas.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Remover temporariamente, um de cada vez, um CSS, um JS, um vínculo do shell e
um item de navegação: a porta de qualidade falha nomeando a tela. Abrir cinco
telas de módulos diferentes: estilo e estado vazio corretos.

## Decisões em aberto

Nenhuma.

## Notas

Contrato visual do Padrão, Regra 2 (fragmento não carrega recurso). O que se
repetir em três telas sobe para `ds/patterns.css`.
