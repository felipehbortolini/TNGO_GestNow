---
id: ISSUE-020
title: Consumo da API registrado em trilha append-only, com último uso amortizado
status: done
type: task
parent: docs/PLANO-MULTI-AMBIENTE.md
spec: docs/SPEC-MULTI-AMBIENTE.md
entrega: 3
blocked_by:
  - ISSUE-018
blocks: []
labels:
  - ready-for-agent
source_requirements:
  - HU-51
  - HU-64
plan_tasks:
  - E3.6
spec_decisions:
  - 25
---

# Consumo da API registrado em trilha append-only, com último uso amortizado

## O que construir

Duas necessidades pedem escrita a cada leitura — saber quando cada token foi
usado pela última vez, e registrar os acessos para auditar o consumo do dado do
cliente. Juntas, elas criariam um problema que nenhuma tem sozinha: o registro
em JSON é lido inteiro, modificado e reescrito sob trava, e um refresh de
painel chamando quatro recursos viraria quatro reescritas completas do arquivo
— cada uma serializando contra qualquer outra operação, inclusive um operador
concedendo acesso. O arquivo que, se corromper, derruba todo mundo passaria a
ser o mais escrito da instalação, no ritmo de uma integração automatizada e não
no de gente.

Então:

- **O acesso vira uma linha acrescentada na trilha do registro** — o mesmo
  mecanismo barato da trilha de auditoria, que nunca lê o conteúdo anterior.
- **O carimbo de último uso é amortizado**: só reescreve o registro quando o
  valor guardado já tiver mais de uma hora. A tela continua respondendo "usado
  há X" com precisão suficiente para decidir revogar, e o registro deixa de ser
  reescrito por requisição.

## Critérios de aceite

- [x] Cada requisição autenticada da API acrescenta uma linha na trilha do
      registro, com o ambiente, o prefixo do token e o recurso pedido.
- [x] A trilha nunca é lida para ser escrita.
- [x] **Cem chamadas seguidas produzem cem linhas de trilha e no máximo uma
      reescrita do registro.**
- [x] O último uso exibido tem precisão de hora, e não de segundo.
- [x] Uma falha ao escrever a trilha não derruba a resposta da API.
- [x] Requisições recusadas também deixam rastro, distinguíveis das aceitas.

## Verificação

Teste automatizado que dispara cem chamadas seguidas e afirma as duas coisas:
cem linhas na trilha e no máximo uma reescrita do arquivo do registro.

Conferência do valor de último uso exibido depois de uma sequência de chamadas.

A porta de qualidade das cinco etapas passa.

## Decisões humanas em aberto

Nenhuma.

## Notas

Este é o risco explícito da Entrega 3 na tabela de riscos do plano: se o
carimbo de último uso voltar a ser por requisição, o arquivo do registro vira o
mais escrito da instalação. O teste das cem chamadas é o que protege isso ao
longo do tempo.

Limite de requisição por cliente continua fora de escopo: a semana obrigatória
já é o teto de volume, a trilha registra o consumo e revogar é um clique —
detecção em vez de prevenção, que é a troca certa nesta escala.
