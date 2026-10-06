---
id: ISSUE-025
title: O seletor vira a tela inicial permanente — toda visita nova começa escolhendo o ambiente
status: done
type: task
parent: docs/PLANO-MULTI-AMBIENTE.md
spec: docs/SPEC-MULTI-AMBIENTE.md
entrega: 4
blocked_by:
  - ISSUE-006
  - ISSUE-011
blocks: []
labels:
  - ready-for-agent
source_requirements:
  - HU-03
  - HU-10
  - HU-11
  - HU-12
  - HU-14
spec_decisions:
  - 5
  - 9
  - 16
  - "Revisão 3, item 3"
---

# O seletor vira a tela inicial permanente — toda visita nova começa escolhendo o ambiente

## O que construir

Hoje o boot entra direto no último ambiente escolhido, e quem tem um ambiente
só nunca vê o seletor. Passa a ser o contrário: **toda visita nova à aplicação
começa no seletor** — navegador aberto, aba nova —, inclusive para quem tem
acesso a um ambiente só, que vê a caixa única e clica nela.

A aplicação ganha uma tela inicial de escolha, no espírito de um portfólio de
projetos: ninguém começa o dia apontado para um cliente que não escolheu hoje,
e a área de administração fica a um passo de quem tem acesso a ela.

**O laço que isso cria precisa ser resolvido, e é o miolo desta issue.** Se o
boot ignorar o cookie sempre, a própria escolha nunca entra: ela grava o
cookie e recarrega, o boot mostra o seletor de novo, e a pessoa fica presa. A
recusa de ambiente da decisão 9, que também recarrega, cairia no mesmo poço.

Então o boot mostra o seletor **quando a visita é nova**, e honra a escolha
quando a navegação corrente é consequência dela. A marca de entrada vive **por
aba** e morre com ela: aba nova e navegador novo não a têm; recarregar no meio
do trabalho não devolve ninguém ao seletor, porque um F5 que descarta trabalho
não salvo é pior do que o problema que esta issue resolve.

Voltar ao seletor pela sidebar limpa a marca — trocar de ambiente continua
levando à tela inicial do ambiente novo, como já acontece.

O cookie **não sai**: ele continua sendo pista e nunca autorização, continua
conferido contra o registro a cada requisição, continua carregando o ambiente
nos dois downloads e no relatório de impressão, e o cabeçalho continua sendo
conferido contra ele. O que ele deixa de fazer é decidir o boot sozinho.

## Critérios de aceite

- [x] Abrir a aplicação numa aba nova mostra o seletor, mesmo com o cookie
      gravado e válido.
- [x] Fechar e reabrir o navegador mostra o seletor.
- [x] Quem tem acesso a **um** ambiente só também vê o seletor, com uma caixa,
      e entra clicando nela.
- [x] Escolher entra na aplicação de primeira — **não existe caminho em que a
      escolha devolva o seletor**.
- [x] Recarregar uma tela de trabalho na mesma aba **não** devolve ao seletor.
- [x] Abrir um link direto sem ter escolhido leva ao seletor e, depois da
      escolha, àquele mesmo endereço — em toda visita, não só na primeira.
- [x] Uma recusa de ambiente continua recarregando o shell e mostrando o
      seletor com a mensagem, sem laço.
- [x] Voltar ao seletor pela sidebar mostra o seletor, e escolher de novo entra
      normalmente.
- [x] Os dois downloads e o relatório de impressão continuam trazendo o dado do
      ambiente ativo.
- [x] Duas abas em ambientes diferentes continuam produzindo a recusa própria
      na aba mais velha, com a mensagem de que ela está em outro ambiente.

## Verificação

Revisão de tela cobrindo, nesta ordem, porque a ordem separa os casos:

1. aba nova com cookie válido → seletor;
2. escolher → entra de primeira, sem voltar ao seletor;
3. F5 na tela de trabalho → continua na tela de trabalho;
4. link direto em aba nova → seletor → destino certo depois da escolha;
5. segunda aba escolhendo outro ambiente → a primeira aba recusa com a
   mensagem própria;
6. exportar a planilha e abrir o relatório → dado do ambiente certo;
7. revogar o acesso de quem está dentro → seletor com a mensagem, sem laço.

Teste automatizado do caso 2 e do caso 7 — os dois que, se quebrarem, prendem
a pessoa numa tela sem saída.

A porta de qualidade das cinco etapas passa.

## Decisões humanas em aberto

Nenhuma. Ver **Revisão 3, item 3** na spec: as histórias 3 e 10 mudam por
decisão, e a 12 fica mais importante do que era.

## Notas

Três histórias mudam e estão anotadas na spec: a 3 é **revogada** (quem tem um
ambiente só passa a clicar), a 10 é **encolhida** (a escolha deixa de valer em
aba nova) e a 12 é **preservada e reforçada** — como agora todo link direto
passa pelo seletor, o destino precisa sobreviver à escolha em 100% dos casos.

A colisão de multi-aba da decisão 5 fica mais frequente, porque toda aba nova
escolhe. O mecanismo que trata isso já existe e continua correto; passa a ser
exercitado com frequência em vez de raramente, o que torna o caso 5 da
verificação obrigatório e não opcional.
