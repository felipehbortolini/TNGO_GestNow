---
id: ISSUE-014
title: Arquivar e desarquivar ambiente pela tela, com a mensagem própria para quem está dentro
status: done
type: task
parent: docs/PLANO-MULTI-AMBIENTE.md
spec: docs/SPEC-MULTI-AMBIENTE.md
entrega: 2
blocked_by:
  - ISSUE-011
blocks: []
labels:
  - ready-for-agent
source_requirements:
  - HU-38
  - HU-39
  - HU-40
  - HU-42
plan_tasks:
  - E2.5
  - E2.7 (parcial)
spec_decisions:
  - 13
---

# Arquivar e desarquivar ambiente pela tela, com a mensagem própria para quem está dentro

## O que construir

As duas operações na área do operador, com confirmação. Arquivar é **estado,
reversível, e não apaga nada**: o ambiente some do seletor, quem está dentro
cai na guarda no clique seguinte e o histórico do contrato encerrado continua
recuperável.

A mensagem que quem está dentro recebe é **"este ambiente foi arquivado"**, e
não "você não tem acesso" — são coisas diferentes e a pessoa merece saber qual
das duas aconteceu.

Desarquivar devolve tudo como estava, inclusive os membros — e, quando a
Entrega 3 existir, inclusive as integrações, sem reemitir nada.

As duas operações viram evento na trilha do registro.

## Critérios de aceite

- [x] Arquivar pede confirmação antes de agir.
- [x] O ambiente arquivado some do seletor de todos os membros.
- [x] Quem está dentro no momento do arquivamento vê, no clique seguinte, a
      mensagem **própria** de arquivado — e não a de acesso negado.
- [x] Nada é apagado: os dados do ambiente continuam no lugar.
- [x] Desarquivar devolve o ambiente ao seletor com os mesmos membros.
- [x] O identificador de um ambiente arquivado continua indisponível para
      reaproveitamento.
- [x] As duas operações aparecem na trilha do registro.
- [x] A tela chama as funções da porta do registro e não implementa regra
      própria.

## Verificação

Revisão de tela com duas sessões: uma pessoa trabalhando dentro do ambiente e o
operador arquivando de outra sessão. Conferir a mensagem específica no clique
seguinte, a ausência no seletor e a volta completa depois de desarquivar.

Teste automatizado afirmando que arquivar recusa quem está dentro com o motivo
próprio.

A porta de qualidade das cinco etapas passa.

## Decisões humanas em aberto

Nenhuma.

## Notas

Quando a Entrega 3 estiver no ar, os tokens de um ambiente arquivado passam a
recusar com o mesmo motivo **sem serem revogados** — desarquivar devolve as
integrações sem reemissão. O comportamento do token é implementado na
ISSUE-018.
