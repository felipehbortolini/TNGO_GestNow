---
id: ISSUE-008
title: Nome do projeto e do cliente saem dos parâmetros e passam a ter fonte única no registro
status: done
type: task
parent: docs/PLANO-MULTI-AMBIENTE.md
spec: docs/SPEC-MULTI-AMBIENTE.md
entrega: 1
blocked_by:
  - ISSUE-007
blocks:
  - ISSUE-010
labels:
  - ready-for-agent
source_requirements:
  - HU-44
  - HU-65
plan_tasks:
  - E1.12
spec_decisions:
  - 4
---

# Nome do projeto e do cliente saem dos parâmetros e passam a ter fonte única no registro

## O que construir

Os dois campos deixam de existir nos parâmetros do ambiente e na tela de
Configurações como campos de entrada. O registro de ambientes passa a ser a
única fonte, e todos os leitores apontam para lá: a sidebar, o dashboard, a
planilha exportada, o relatório e a própria tela de Configurações.

Configurações passa a **exibir** o nome do ambiente em leitura, para a pessoa
saber de qual cliente ela está falando antes de mudar uma meta — e perde os
dois campos editáveis.

Duas moradas para o mesmo fato, editadas por gente diferente — o operador no
registro, o administrador em Configurações — produziriam um seletor
discordando da sidebar. E fazer os parâmetros mandarem obrigaria a abrir a base
de cada ambiente só para desenhar as caixas do seletor: uma leitura de arquivo
por ambiente a cada login.

Isso também dissolve o problema dos parâmetros padrão nascerem com o nome de um
cliente específico escrito no código: não há campo para neutralizar, porque o
campo deixou de existir ali.

## Critérios de aceite

- [x] Nenhum nome de cliente específico aparece no código-fonte da aplicação
      (varredura sem resultados).
- [x] Os parâmetros padrão de um ambiente novo não têm os campos de projeto e
      cliente.
- [x] A tela de Configurações mostra, em leitura, de qual ambiente ela está
      falando, e não oferece os dois campos para edição.
- [x] A sidebar, o cabeçalho do dashboard, a planilha exportada e o relatório
      para impressão trazem o nome vindo do registro, correto para o ambiente
      ativo.
- [x] Um ambiente cujo nome de cliente foi alterado no registro passa a exibir
      o nome novo em todos os leitores, sem tocar na base do ambiente.
- [x] O identificador do ambiente continua imutável — renomear o cliente muda
      só o nome exibido.

## Verificação

Varredura no código-fonte por nome de cliente específico, sem resultados.

Revisão de tela em dois ambientes com nomes diferentes: sidebar, dashboard,
Configurações, planilha exportada e relatório para impressão, conferindo que
cada um traz o nome do ambiente em que foi aberto.

A porta de qualidade das cinco etapas passa.

## Decisões humanas em aberto

Nenhuma.

## Notas

São cinco leitores e um template envolvidos; a varredura é curta, mas passa por
template e por exportação, que são os dois lugares fáceis de esquecer.

Com esta issue a Entrega 1 está completa em código: o que falta é publicar
(ISSUE-010) e ter o modo demonstração funcionando (ISSUE-009).
