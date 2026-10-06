---
id: ISSUE-024
title: Promover e rebaixar operadores pela área de administração, com a variável de ambiente como piso
status: done
type: task
parent: docs/PLANO-MULTI-AMBIENTE.md
spec: docs/SPEC-MULTI-AMBIENTE.md
entrega: 4
blocked_by:
  - ISSUE-011
  - ISSUE-021
blocks: []
labels:
  - ready-for-agent
source_requirements:
  - HU-27
  - HU-37
  - HU-42
  - HU-43
spec_decisions:
  - 11
  - "Revisão 3, item 2"
---

# Promover e rebaixar operadores pela área de administração, com a variável de ambiente como piso

## O que construir

Hoje trocar quem administra a carteira é editar uma variável de ambiente e
reiniciar a instalação. Passa a existir uma tela, ao lado da configuração de
tokens, onde quem já é operador promove e rebaixa outros.

**A variável continua sendo o piso, e é isso que mantém as três razões da
decisão 11 de pé:** numa instalação limpa existe operador antes de existir
registro; um registro apagado ou corrompido não deixa a instalação sem porta de
entrada; e quem comprometer o dado não fabrica o perfil que enxerga todos os
clientes, porque o poder mínimo mora fora do dado.

Acima desse piso, operadores adicionais vivem no registro. A consequência
prática é que a tela precisa **mostrar a origem de cada operador** —
configuração da implantação ou registro — porque só os do registro podem ser
rebaixados. Uma tela que oferece um botão inerte para os da variável mente
sobre o que consegue fazer.

Promover é conceder o perfil que enxerga todos os clientes. Isso pede o mesmo
cuidado da emissão de token: a tela diz em palavras o que a promoção entrega,
antes de confirmar.

## Critérios de aceite

- [x] Um operador promove outro e-mail pela área de administração, e o
      promovido passa a enxergar todos os ambientes na requisição seguinte.
- [x] Rebaixar retira o perfil na requisição seguinte.
- [x] A tela mostra a origem de cada operador — configuração ou registro.
- [x] Um operador que vem da variável de ambiente **não** oferece controle de
      rebaixamento, nem por acesso direto ao endpoint.
- [x] Remover a variável de ambiente e reiniciar não apaga os operadores do
      registro.
- [x] Esvaziar o registro não deixa a instalação sem operador: os da variável
      continuam entrando.
- [x] Quem não é operador não vê a tela e é recusado no acesso direto.
- [x] Promoção e rebaixamento aparecem na trilha do registro, com quem fez.
- [x] A tela enuncia, antes de confirmar, que a promoção dá acesso à base de
      todos os clientes.
- [x] Os operadores promovidos pela tela também aparecem na tela de
      Colaboradores de cada ambiente como linha marcada e não removível, e
      contam na quantidade de pessoas com acesso.

## Verificação

Revisão de tela com dois e-mails: um da variável e um promovido pela tela.
Conferir a origem exibida, a ausência do controle de rebaixamento no primeiro,
e o efeito na requisição seguinte para o segundo.

Teste afirmando que a lista efetiva de operadores é a união das duas origens, e
que remover o registro inteiro não remove os da variável.

Tentativa de rebaixar um operador da variável por acesso direto ao endpoint,
recusada.

A porta de qualidade das cinco etapas passa.

## Decisões humanas em aberto

Nenhuma. A escolha entre piso mais tela e só tela já foi feita — ver
**Revisão 3, item 2** na spec.

## Notas

O risco aceito nº 2 da spec fica maior: mais gente pode virar operador, e
operador enxerga todo cliente. A compensação continua sendo a mesma —
visibilidade na tela de Colaboradores de cada ambiente e a trilha do registro,
que agora também registra quem promoveu quem.
