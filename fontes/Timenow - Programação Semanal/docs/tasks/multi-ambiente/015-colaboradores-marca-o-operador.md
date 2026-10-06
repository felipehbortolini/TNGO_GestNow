---
id: ISSUE-015
title: Tela de Colaboradores mostra o operador da Timenow como linha marcada e não removível
status: done
type: task
parent: docs/PLANO-MULTI-AMBIENTE.md
spec: docs/SPEC-MULTI-AMBIENTE.md
entrega: 2
blocked_by:
  - ISSUE-004
  - ISSUE-011
blocks:
  - ISSUE-023
labels:
  - ready-for-agent
source_requirements:
  - HU-19
  - HU-37
  - HU-43
plan_tasks:
  - E2.6
spec_decisions:
  - 11
---

# Tela de Colaboradores mostra o operador da Timenow como linha marcada e não removível

## O que construir

A tela de Colaboradores de cada ambiente passa a listar os operadores da
Timenow como linha marcada, somente leitura, que o administrador do cliente
**vê e não pode remover**.

O cadastro de colaboradores é a lista de acesso do ambiente, e ela precisa ser
completa para ser verdadeira: sem essa linha, a tela que o cliente abre para
auditar o próprio acesso omitiria justamente quem tem mais poder, e a contagem
de pessoas com acesso mentiria.

É a compensação explícita do risco aceito nº 2 da spec — o cliente não pode
tirar, mas pode ver.

## Critérios de aceite

- [x] O administrador de um ambiente vê a linha do operador na tela de
      Colaboradores, marcada como operador da Timenow.
- [x] A linha não oferece controle de remoção nem de edição.
- [x] Tentar remover o operador por acesso direto ao endpoint é recusado.
- [x] Um operador que **também** consta no cadastro daquele ambiente aparece
      uma vez só, com o perfil do cadastro e a marcação.
- [x] A contagem de pessoas da tela bate com a contagem da listagem de
      ambientes da área do operador.
- [x] Nenhum e-mail de operador é gravado no cadastro do cliente por efeito
      desta tela.

## Verificação

Revisão de tela como administrador de um ambiente onde há operador que não é
colaborador e outro que também é colaborador — conferir uma linha para cada, a
marcação, a ausência dos controles e a contagem batendo com a da área do
operador.

Tentativa de remoção por acesso direto ao endpoint, recusada.

A porta de qualidade das cinco etapas passa.

## Decisões humanas em aberto

Nenhuma.

## Notas

A resolução e a contagem do operador vêm da ISSUE-004; esta issue é a
apresentação delas na tela do cliente.

Esta issue **fecha a Entrega 2**.
