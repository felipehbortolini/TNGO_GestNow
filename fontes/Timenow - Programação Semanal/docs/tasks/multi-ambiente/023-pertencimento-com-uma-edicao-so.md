---
id: ISSUE-023
title: Cadastrar a pessoa no ambiente passa a ser o ato de conceder acesso, com o registro como índice
status: done
type: task
parent: docs/PLANO-MULTI-AMBIENTE.md
spec: docs/SPEC-MULTI-AMBIENTE.md
entrega: 4
blocked_by:
  - ISSUE-013
  - ISSUE-015
blocks: []
labels:
  - ready-for-agent
source_requirements:
  - HU-19
  - HU-35
  - HU-36
  - HU-37
  - HU-43
spec_decisions:
  - 2
  - 4
  - "Revisão 3, item 1"
---

# Cadastrar a pessoa no ambiente passa a ser o ato de conceder acesso, com o registro como índice

## O que construir

Hoje uma pessoa nova exige **duas** edições em lugares diferentes: membro no
registro, pela área do operador, e colaborador no ambiente, pela tela de
Colaboradores. Esquecer a primeira produz a falha silenciosa mais provável da
operação — alguém cadastrado no ambiente, com perfil e tudo, que não vê aquele
ambiente no seletor e não recebe nenhuma mensagem explicando por quê.

Passa a existir **uma edição só**: cadastrar a pessoa na tela de Colaboradores
do ambiente **é** conceder o acesso. A aplicação mantém o índice de membros do
registro em sincronia — cadastrar acrescenta, remover retira, desativar retira.
O seletor continua lendo o registro, e continua lendo **um arquivo só** no
login: abrir a base de todos os ambientes a cada entrada é o custo que a
decisão 4 recusou, e ele continua recusado.

O operador precisa de um caminho para o **primeiro** colaborador de um ambiente
recém-criado, que nasce sem cadastro nenhum por decisão. Esse caminho continua
na área de administração, e é o único lugar onde conceder acesso é um ato
separado.

A sincronia precisa sobreviver a um registro que divergiu — por edição à mão,
por interrupção no meio de uma gravação, ou por um ambiente criado antes desta
mudança. A entrada no ambiente reconcilia o índice com o cadastro.

## Critérios de aceite

- [x] Cadastrar uma pessoa na tela de Colaboradores de um ambiente faz aquele
      ambiente aparecer no seletor dela, sem nenhum passo na área do operador.
- [x] Remover a pessoa do cadastro tira o ambiente do seletor dela na
      requisição seguinte, sem esperar a sessão expirar.
- [x] Desativar a pessoa no cadastro tem o mesmo efeito que remover, para
      efeito de seletor.
- [x] O seletor continua resolvendo a lista com **uma** leitura do registro,
      sem abrir a base de nenhum ambiente.
- [x] O operador continua conseguindo conceder acesso ao primeiro colaborador
      de um ambiente vazio, pela área de administração.
- [x] Um registro cujo índice divergiu do cadastro é reconciliado na entrada
      do ambiente, e a divergência não impede a pessoa de entrar.
- [x] Conceder e revogar continuam aparecendo na trilha do registro,
      identificando se vieram do cadastro ou da área do operador.
- [x] O recorte por vínculo de empresa contratada continua valendo por cima do
      recorte por ambiente.
- [x] Nenhum e-mail passa a enxergar um ambiente onde não está cadastrado.

## Verificação

Revisão de tela em dois ambientes: cadastrar a mesma pessoa em um deles e
conferir que o seletor dela mostra **um**; cadastrar no segundo e conferir que
mostra dois; remover de um e conferir que volta a mostrar um, no clique
seguinte.

Teste de isolamento afirmando que cadastrar em A não faz B aparecer.

Teste de reconciliação: divergir o índice à mão, entrar no ambiente e conferir
que o seletor volta a bater com o cadastro.

A porta de qualidade das cinco etapas passa.

## Decisões humanas em aberto

Nenhuma. A escolha entre índice mantido e varredura por login já foi feita —
ver **Revisão 3, item 1** na spec.

## Notas

Esta issue muda **onde se edita**, não o que a aplicação lê: o registro
continua sendo a fonte que o seletor consulta e continua atrás da porta
própria, pelas razões da decisão 14.

Quem já é operador continua entrando em todo ambiente implicitamente, sem
depender de cadastro — isso não muda aqui.
