---
id: ISSUE-009
title: "Shell com barra lateral sempre visível, navegação de dois níveis, abas do módulo, escopo Portfólio ou projeto e dicas de siglas"
status: in-progress
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

- [ ] A barra lateral está visível em 1280, 1100 e 760 px; em 760 px é trilho de ícones com dica.
- [ ] O item ativo fica destacado; numa tela de detalhe, o módulo de origem fica destacado e o Voltar retorna à lista.
- [ ] O escopo vai para a URL e para o cookie, e um link copiado abre no mesmo escopo.
- [ ] Recarregar uma URL profunda abre a mesma tela no mesmo escopo.
- [ ] Trocar o escopo numa tela de detalhe volta para a lista do módulo.
- [ ] No Portfólio, o mecanismo de inclusão pede o projeto e reabre a tela no projeto com o formulário aberto.
- [ ] Passar o mouse sobre uma sigla mostra o significado.
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
