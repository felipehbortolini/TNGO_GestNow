---
id: ISSUE-022
title: Documentação de produção e contrato da API para o analista do cliente
status: proposed
type: task
parent: docs/PLANO-MULTI-AMBIENTE.md
spec: docs/SPEC-MULTI-AMBIENTE.md
entrega: 3
blocked_by:
  - ISSUE-016
  - ISSUE-019
blocks: []
labels:
  - ready-for-agent
source_requirements:
  - HU-46
  - HU-53
  - HU-58
  - HU-60
plan_tasks:
  - E3.10
spec_decisions:
  - 22
  - 23
---

# Documentação de produção e contrato da API para o analista do cliente

## O que construir

Duas coisas que fecham a Entrega 3.

**No roteiro de publicação**, uma linha de verificação explícita: conferir a
ordem das rotas no arquivo de configuração da borda, com a entrada anônima da
API acima da entrada geral. É a mudança de configuração que quebra em produção
sem quebrar em desenvolvimento, e o teste de prefixo da ISSUE-016 não alcança a
ordem dentro do array — ele guarda o outro lado do risco.

**No material para o cliente**, o contrato da API: quais são os quatro
recursos, quais filtros cada um aceita, que a semana é obrigatória nas
atividades, como a credencial é apresentada, o que o envelope traz e o que cada
recusa significa. O leitor é o analista de dados do cliente, que vai montar o
painel dele — não o desenvolvedor da aplicação.

## Critérios de aceite

- [ ] Existe, no roteiro de publicação, uma linha dizendo para conferir a ordem
      das rotas no arquivo de configuração da borda.
- [ ] O contrato dos quatro recursos está documentado, com filtros,
      obrigatoriedade da semana e formato do envelope.
- [ ] As recusas estão documentadas com o significado de cada uma.
- [ ] A regra de versionamento está escrita: campo novo não quebra e não muda a
      versão; remover ou renomear campo exige versão nova.
- [ ] A documentação diz explicitamente que a API é somente leitura e que o
      token entrega a base inteira do ambiente.
- [ ] Um analista consegue montar a primeira consulta lendo só esse material.

## Verificação

Alguém que não participou da implementação monta uma consulta funcionando
usando apenas a documentação e um token emitido — sem perguntar nada a quem
escreveu o código.

A porta de qualidade das cinco etapas passa.

## Decisões humanas em aberto

Nenhuma.

## Notas

Esta issue **fecha a Entrega 3** e, com ela, o escopo completo da spec.
