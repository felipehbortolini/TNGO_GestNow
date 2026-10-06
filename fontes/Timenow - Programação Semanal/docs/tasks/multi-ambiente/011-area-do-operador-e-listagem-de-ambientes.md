---
id: ISSUE-011
title: Área do operador dentro do seletor, com a listagem de todos os ambientes
status: done
type: task
parent: docs/PLANO-MULTI-AMBIENTE.md
spec: docs/SPEC-MULTI-AMBIENTE.md
entrega: 2
blocked_by:
  - ISSUE-010
blocks:
  - ISSUE-012
  - ISSUE-013
  - ISSUE-014
  - ISSUE-015
  - ISSUE-021
  - ISSUE-024
  - ISSUE-025
labels:
  - ready-for-agent
source_requirements:
  - HU-27
  - HU-43
plan_tasks:
  - E2.1
  - E2.2
spec_decisions:
  - 11
  - 17
---

# Área do operador dentro do seletor, com a listagem de todos os ambientes

## O que construir

A administração do registro ganha casa: uma área própria dentro do seletor,
servida pelo decorador que não exige ambiente e visível **apenas ao operador**.
Ela **não** entra na tela de Configurações, que continua sendo a administração
*daquele* ambiente.

A primeira tela da área é a listagem de todos os ambientes existentes, com o
nome do cliente, a situação e a quantidade de pessoas com acesso. A contagem
**inclui os operadores** — senão a tela mente justamente sobre quem tem mais
poder.

Como toda tela da aplicação, a sub-navegação e as telas de guarda vêm do Design
System, e o fragmento não traz estilo nem script próprios.

## Critérios de aceite

- [x] O operador vê a área de administração a partir do seletor.
- [x] O item da área **não existe no DOM** de quem não é operador.
- [x] Um acesso direto ao endereço da área por quem não é operador é recusado.
- [x] A listagem mostra todos os ambientes, ativos e arquivados, com a situação
      de cada um.
- [x] Cada linha traz nome do projeto, nome do cliente, situação e quantidade
      de pessoas com acesso.
- [x] Um ambiente com 4 colaboradores e 2 operadores mostra 6.
- [x] A tela de Configurações de um ambiente continua sem qualquer referência à
      administração do registro.
- [x] O fragmento novo não traz `<link>` nem `<script src>` e não cria classe
      visual fora do Design System.

## Verificação

Revisão de tela com duas contas: um operador e um administrador de ambiente.
Conferir a presença da área para o primeiro, a ausência no DOM para o segundo e
a recusa no acesso direto.

Teste automatizado da contagem de pessoas com acesso incluindo operadores.

A porta de qualidade das cinco etapas passa.

## Decisões humanas em aberto

Nenhuma.

## Notas

O aceite da Entrega 2 vale a partir daqui: **a tela não escreve regra nova** —
ela só chama o que a Entrega 1 já fez rodar. Se uma tarefa desta entrega
precisar inventar regra, a regra está no lugar errado e desce para a porta do
registro.
