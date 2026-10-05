---
id: ISSUE-009
title: "Shell com barra lateral sempre visível, navegação de dois níveis, abas do módulo, escopo Portfólio ou projeto e dicas de siglas"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 2
onda: 3
blocked_by:
  - ISSUE-008
blocks:
  - ISSUE-010
labels:
  - ready-for-agent
source_requirements:
  - HU-005
  - HU-006
  - HU-007
  - HU-010
  - HU-011
  - HU-012
  - HU-013
  - HU-014
  - HU-015
  - HU-018
spec_decisions:
  - D2
  - D8
  - D1
---

# Shell com barra lateral sempre visível, navegação de dois níveis, abas do módulo, escopo Portfólio ou projeto e dicas de siglas

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D2, D8, D1.
> Entrega 2 (Plataforma no ar), onda 3 (Shell, telas e acesso).
> Histórias: 5, 6, 7, 10, 11, 12, 13, 14, 15, 18. Bloqueada por: ISSUE-008.

## O que construir

O shell do Padrão vira o shell do GestNow. A barra lateral fica à esquerda em
toda view, inclusive detalhe e relatório gerencial, e **nunca some**: acima de
1100 px pode ser recolhida, e abaixo disso vira um trilho de ícones com dica,
nunca uma gaveta escondida. Só o papel impresso não a mostra.

A navegação é servida pelo servidor (`/api/nav`) a partir de uma lista única
de dois níveis: Início, os 8 módulos numerados (01 a 08) com as suas telas,
inclusive as de detalhe, e Configurações. O mesmo fragmento serve as abas do
módulo no topo da página. Numa tela de detalhe (ata, contrato, ficha do risco,
SM), o módulo de origem fica destacado e há um botão Voltar.

O seletor de escopo (Portfólio ou projeto) vive na barra lateral. O escopo é
resolvido por requisição a partir do parâmetro `projeto` da URL ou do cookie,
com Portfólio como padrão, e uma camada de plataforma o entrega às fachadas.
Trocar o escopo numa tela de detalhe volta para a lista do módulo; recarregar
uma URL profunda cai na mesma tela. No Portfólio, o mecanismo de inclusão pede
o projeto antes de abrir o formulário e reabre a tela no projeto com o
formulário aberto (os módulos usam esse mecanismo).

As siglas (SPI, CPI, VME, RNC, TF, S39 e as demais do glossário) ganham dica
ao passar o mouse, pelo componente de dica do Padrão, com o significado vindo
do glossário.

## Critérios de aceite

- [x] A barra lateral está visível em 1280, 1100 e 760 px; em 760 px é trilho de ícones com dica.
- [x] O item ativo fica destacado; numa tela de detalhe, o módulo de origem fica destacado e o Voltar retorna à lista.
- [x] O escopo vai para a URL e para o cookie, e um link copiado abre no mesmo escopo.
- [x] Recarregar uma URL profunda abre a mesma tela no mesmo escopo.
- [x] Trocar o escopo numa tela de detalhe volta para a lista do módulo.
- [x] No Portfólio, o mecanismo de inclusão pede o projeto e reabre a tela no projeto com o formulário aberto.
- [x] Passar o mouse sobre uma sigla mostra o significado.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de rota: `/api/nav` devolve a lista de dois níveis; o escopo resolve por
URL, por cookie e pelo padrão. Revisão de tela nas três larguras (a varredura
automática chega na ISSUE-090). `npm run verificar` passa.

## Decisões em aberto

Nenhuma.

## Notas

Fontes: shell e sidebar do Padrão; `js/layout.js` e `js/siglas.js` do
protótipo; `nav` do app de Programação Semanal. Nesta issue a identidade é um
Admin fixo da demonstração; perfis, recorte por vínculo e itens por permissão
chegam na ISSUE-011.

## Registro de execução

Data: 05/10/2026.

Feito: a lista única de navegação é `api/src/core/navegacao.json` (Início, 01 a
08 e Configurações; 51 telas, com os 5 detalhes apontando a lista de origem e
a Programação Semanal como grupo do 02), lida por `core/navigation.py`
(validação que falha alto, busca por endereço, URLs) e por
`core/navigation_view.py` (o que a barra lateral, as abas, o Voltar e o seletor
de escopo mostram). O Node da ISSUE-010 lê o mesmo JSON. `/api/nav` devolve a
barra lateral e as abas numa resposta multi-alvo, resolve o escopo e grava o
cookie `gestnow_projeto`; `/api/escopo/projetos` é a escolha de projeto do
mecanismo de inclusão e `/api/glossario` alimenta a dica (todas em
`api/src/blueprints/nav.py`). O escopo (`core/scope.py`) resolve por URL, depois
cookie, depois Portfólio, valida contra `configuracoes.service.list_projects` e
entrega às fachadas (`Scope.require_project`). No front: `ds/shell.js` (trilho,
roteador com URL profunda `/<modulo>/<tela>?projeto=`, escopo, inclusão),
`ds/dica.js` (componente de dica e hover das siglas), `.dica` em `tokens.css`,
trilho, abas e seletor em `shell.css`, `index.html` reestruturado e seis ícones
novos. O glossário vem do `CONTEXT.md` por `scripts/generate_glossary.py` para
`api/src/core/glossario.json` (só `api/` vai ao Azure), com teste de sincronia.

Decisões, anotadas na spec como "Decisão da execução (ISSUE-009), pendente de
revisão do dono": lista de navegação em JSON compartilhado; endereço
`/<modulo>/<tela>?projeto=` com o parâmetro vencendo o cookie e valor inválido
caindo na fonte seguinte com aviso; trilho em até 1100 px e recolhível acima;
criação do componente de dica, porque o Padrão só tem `title`; glossário
gerado a partir do `CONTEXT.md`; escolha do projeto da inclusão por fragmento do
servidor com `?acao=`. Fora desta fatia: perfis, recorte por vínculo e itens por
permissão (ISSUE-011); P1 a P5, I1 a I5 e N1 a N5 do protótipo, que não estão no
`CONTEXT.md`; o trio de cada tela (ISSUE-010).

Verificação: por nova política do dono, esta rodada não rodou o pytest, o
`npm run verificar` completo nem a revisão de tela nas três larguras. Os
testes foram escritos (`test_navegacao.py`, `test_escopo.py`,
`test_glossario.py`) e ficam para o orquestrador rodar; o último critério fica
desmarcado até lá. Rodei só ruff, ruff format, ty, eslint e
`verificar-padrao.mjs` sobre os arquivos novos, todos sem apontamento. Ponto de
atenção para a ISSUE-011 ou 092: `routing.fragment_route` usa
`functools.wraps`, e o Azure Functions indexa a assinatura de `__wrapped__`
(`req, session`); se o indexador recusar o parâmetro `session`, basta fixar
`__signature__` com só `req` no decorador.
