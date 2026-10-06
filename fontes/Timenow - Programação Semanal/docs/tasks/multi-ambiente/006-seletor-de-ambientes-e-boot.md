---
id: ISSUE-006
title: Seletor de ambientes depois do SSO, com a escolha recarregando para o destino certo
status: done
type: task
parent: docs/PLANO-MULTI-AMBIENTE.md
spec: docs/SPEC-MULTI-AMBIENTE.md
entrega: 1
blocked_by:
  - ISSUE-005
blocks:
  - ISSUE-007
  - ISSUE-009
  - ISSUE-025
labels:
  - ready-for-agent
source_requirements:
  - HU-01
  - HU-02
  - HU-03
  - HU-05
  - HU-08
  - HU-10
  - HU-11
  - HU-12
  - HU-14
plan_tasks:
  - E1.9
  - E1.10
spec_decisions:
  - 5
  - 16
  - 17
---

# Seletor de ambientes depois do SSO, com a escolha recarregando para o destino certo

## O que construir

A primeira tela depois do SSO: uma caixa por ambiente que a pessoa pode
acessar, com o nome do projeto e o nome do cliente, para reconhecer o ambiente
sem precisar abri-lo. Escolher grava o cookie do ambiente e entra na aplicação
que já existe — mesma sidebar, mesma matriz, mesmo dashboard — apontada para a
base daquele cliente.

O boot do shell ganha um passo. Hoje ele confere o sentinela do Design System,
consulta a sessão e, com sessão, revela a sidebar e carrega a navegação e a
view inicial. Passa a, depois da sessão, **pedir o seletor**: com um único
ambiente segue direto, com vários aguarda a escolha, com nenhum mostra a tela
que explica isso e diz a quem pedir liberação — nunca uma lista vazia.

A escolha grava o cookie e **recarrega, com destino explícito**, e é isso que
concilia duas coisas que parecem a mesma e são opostas: a **primeira escolha**
preserva o link direto — quem abriu um endereço específico chega naquele
endereço depois de escolher, porque o caminho da URL nunca mudou (o seletor é
fragmento dentro do shell) — e a **troca** descarta o destino e volta para a
tela inicial do ambiente novo, para não deixar a pessoa numa tela cujo filtro
pertence ao ambiente anterior.

Recarregar é o que faz a sidebar do ambiente novo se remontar sozinha, porque a
navegação é buscada de novo. Continuar o boot sem recarregar exigiria lembrar
de re-buscar a navegação à mão, e esquecer disso deixaria a sidebar com o nome
do ambiente anterior.

Entra também a outra metade da defesa contra multi-aba: toda requisição do
Alpine AJAX passa a levar o identificador do ambiente em que a tela foi
renderizada, no cabeçalho que a ISSUE-005 confere contra o cookie.

Segue o padrão da aplicação: view autocontida, fragmento servido por blueprint,
sub-navegação e telas de guarda reaproveitadas do Design System. O fragmento
não traz `<link>` nem `<script src>`, e nenhuma classe visual nova nasce fora
do Design System.

## Critérios de aceite

- [x] Depois do SSO, quem tem mais de um ambiente vê uma caixa por ambiente,
      com nome do projeto e nome do cliente.
- [x] Quem tem acesso a um único ambiente entra direto nele, sem um clique que
      não tem alternativa.
- [x] Quem não é membro de nenhum ambiente vê a tela que explica a situação e
      diz a quem pedir liberação.
- [x] Escolher grava o cookie e entra na aplicação apontada para aquela base.
- [x] Abrir um endereço direto sem ambiente escolhido leva ao seletor e,
      depois da escolha, àquele mesmo endereço.
- [x] Trocar de ambiente leva à tela inicial do ambiente novo, e não à tela em
      que a pessoa estava.
- [x] A sidebar se remonta sozinha nos dois casos.
- [x] Recarregar a página, abrir aba nova ou abrir link direto mantém o
      ambiente escolhido; fechar o navegador faz a escolha ser refeita.
- [x] Toda requisição do Alpine AJAX leva o identificador do ambiente da tela
      no cabeçalho, e uma aba antiga é recusada com a mensagem própria em vez
      de gravar no ambiente que a outra aba escolheu.
- [x] O fragmento novo não traz `<link>` nem `<script src>` e não cria classe
      visual fora do Design System.

## Verificação

Revisão de tela no navegador **no duplo clique**, sem publicar: a identidade
fixa do modo demonstração vem da ISSUE-005 e os dois ambientes são criados pelo
comando da ISSUE-003. Se qualquer um dos dois faltar, esta issue não é
verificável — pare e resolva antes de continuar.

Com os dois em pé:

1. entrar e ver as duas caixas;
2. escolher e chegar na aplicação com a base certa;
3. abrir um endereço direto sem cookie e conferir que a escolha leva até ele;
4. trocar de ambiente e conferir que caiu na tela inicial do novo;
5. abrir duas abas em ambientes diferentes e conferir que a aba antiga é
   recusada com a mensagem própria.

A porta de qualidade das cinco etapas passa, incluindo o verificador do padrão
Timenow sobre o fragmento e a view novos.

## Decisões humanas em aberto

Nenhuma.

## Notas

Esta issue **fecha a janela vermelha** aberta na ISSUE-001: ao final dela a
aplicação volta a responder, agora multi-ambiente.

A área de administração do registro dentro do seletor — visível só ao operador
— é a Entrega 2 e não entra aqui.
