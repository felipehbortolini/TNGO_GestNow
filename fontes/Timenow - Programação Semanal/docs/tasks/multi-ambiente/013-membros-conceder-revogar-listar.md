---
id: ISSUE-013
title: Membros do ambiente pela tela — conceder, revogar e listar quem tem acesso
status: done
type: task
parent: docs/PLANO-MULTI-AMBIENTE.md
spec: docs/SPEC-MULTI-AMBIENTE.md
entrega: 2
blocked_by:
  - ISSUE-011
blocks:
  - ISSUE-023
labels:
  - ready-for-agent
source_requirements:
  - HU-09
  - HU-35
  - HU-36
  - HU-37
  - HU-42
plan_tasks:
  - E2.4
  - E2.7 (parcial)
spec_decisions:
  - 2
  - 11
---

# Membros do ambiente pela tela — conceder, revogar e listar quem tem acesso

## O que construir

A tela de membros de um ambiente, dentro da área do operador: conceder acesso
informando o e-mail, revogar o acesso de alguém e ver a lista completa de quem
enxerga aquele ambiente, para revisar periodicamente quem tem acesso a quê.

Os operadores aparecem na lista **marcados e não removíveis** — eles entram em
todo ambiente implicitamente, e omiti-los faria a tela mentir.

Revogar vale **na requisição seguinte**, sem esperar sessão expirar: a pessoa
revogada é devolvida ao seletor no clique seguinte, com a mensagem clara de que
o acesso foi retirado — e não com uma tela quebrada.

Cada concessão e cada revogação vira evento na trilha do registro.

## Critérios de aceite

- [x] Conceder acesso por e-mail põe a pessoa na lista e no seletor dela.
- [x] Revogar tira a pessoa da lista.
- [x] A pessoa revogada cai no seletor **no clique seguinte**, com a mensagem
      de acesso retirado, sem esperar a sessão expirar.
- [x] A lista mostra todos os membros do ambiente.
- [x] Os operadores aparecem marcados e sem controle de remoção.
- [x] Conceder um e-mail que já é membro não duplica a linha.
- [x] Concessão e revogação aparecem na trilha do registro, com quem fez e
      quando.
- [x] A tela chama as funções da porta do registro e não implementa regra
      própria.

## Verificação

Revisão de tela: conceder a um e-mail, entrar com ele, revogar de outra sessão
e conferir que o clique seguinte devolve ao seletor com a mensagem certa.

Conferência da trilha do registro depois das duas operações.

A porta de qualidade das cinco etapas passa.

## Decisões humanas em aberto

Nenhuma.

## Notas

Conceder acesso no registro não basta para a pessoa trabalhar: ela também
precisa constar no cadastro de colaboradores daquele ambiente, que é o que
decide o perfil. As duas camadas continuam obrigatórias, e a guarda da
ISSUE-005 diz qual das duas recusou.
