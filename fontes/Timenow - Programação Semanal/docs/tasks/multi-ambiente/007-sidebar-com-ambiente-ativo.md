---
id: ISSUE-007
title: Sidebar mostra o ambiente ativo e oferece a troca a quem tem mais de um
status: done
type: task
parent: docs/PLANO-MULTI-AMBIENTE.md
spec: docs/SPEC-MULTI-AMBIENTE.md
entrega: 1
blocked_by:
  - ISSUE-006
blocks:
  - ISSUE-008
labels:
  - ready-for-agent
source_requirements:
  - HU-04
  - HU-06
  - HU-07
plan_tasks:
  - E1.11
spec_decisions:
  - 4
  - 18
---

# Sidebar mostra o ambiente ativo e oferece a troca a quem tem mais de um

## O que construir

A faixa da sidebar passa a dizer em qual ambiente a pessoa está, com o nome do
projeto vindo do **registro** e não dos parâmetros do ambiente — uma fonte só,
para que o seletor nunca discorde da sidebar.

Quem tem acesso a mais de um ambiente ganha ali o caminho para trocar a
qualquer momento, sem sair e entrar de novo na aplicação. Quem tem um só não
recebe o controle: o item **some do DOM**, como já acontece hoje com todo item
de menu que o perfil não abre — mas continua vendo o nome do ambiente, para
nunca duvidar de onde está.

Trocar pela sidebar é a mesma troca da ISSUE-006: volta para a tela inicial do
ambiente novo, e a sidebar se remonta com o nome novo.

## Critérios de aceite

- [x] A faixa da sidebar mostra o nome do projeto do ambiente ativo, lido do
      registro.
- [x] Trocar de ambiente muda o nome exibido na faixa.
- [x] O controle de troca **não existe no DOM** de quem tem acesso a um único
      ambiente.
- [x] Quem tem um único ambiente ainda vê qual ambiente está usando.
- [x] A troca pela sidebar leva à tela inicial do ambiente escolhido.
- [x] A lista de ambientes oferecida na troca traz só os ativos onde a pessoa é
      membro — a mesma lista do seletor.

## Verificação

Revisão de tela com duas contas: uma com dois ambientes e outra com um só.
Conferir o nome exibido, a troca funcionando e a ausência do controle no DOM da
segunda conta.

A porta de qualidade das cinco etapas passa.

## Decisões humanas em aberto

Nenhuma.

## Notas

Nesta issue o nome exibido já vem do registro; a **remoção** dos campos de
projeto e cliente dos parâmetros do ambiente e o reapontamento dos demais
leitores são a ISSUE-008.
