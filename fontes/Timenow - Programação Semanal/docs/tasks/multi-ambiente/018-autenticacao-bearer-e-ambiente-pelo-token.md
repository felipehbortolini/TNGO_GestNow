---
id: ISSUE-018
title: Autenticação por token na API, com o ambiente resolvido pela própria credencial
status: done
type: task
parent: docs/PLANO-MULTI-AMBIENTE.md
spec: docs/SPEC-MULTI-AMBIENTE.md
entrega: 3
blocked_by:
  - ISSUE-016
  - ISSUE-017
blocks:
  - ISSUE-019
  - ISSUE-020
labels:
  - ready-for-agent
source_requirements:
  - HU-58
  - HU-59
plan_tasks:
  - E3.3
  - E3.9 (parcial)
spec_decisions:
  - 13
  - 22
  - 26
---

# Autenticação por token na API, com o ambiente resolvido pela própria credencial

## O que construir

A costura de entrada da API: lê a credencial apresentada como *bearer*, resolve
o token pela porta do registro e abre o ambiente ativo daquele token em torno
do handler, fechando-o ao fim da requisição.

Sem cookie e sem cabeçalho de aba — **o token é a resolução do ambiente**. Um
token nunca alcança outro ambiente, mesmo que o consumidor descubra o
identificador dele.

Token de ambiente arquivado é recusado **com motivo próprio e sem ser
revogado**: desarquivar precisa devolver a integração sem reemissão, e um
contrato encerrado que continua alimentando o painel do cliente seria o oposto
do motivo de arquivar.

Toda recusa é resposta JSON com motivo legível — nunca fragmento, nunca HTML —
para que o consumidor saiba o que resolver.

## Critérios de aceite

- [x] Uma requisição com token válido responde dentro do ambiente daquele
      token.
- [x] Os cinco casos recusam com mensagem legível e distinta: credencial
      ausente, malformada, revogada, expirada e de ambiente arquivado.
- [x] Nenhuma resposta de recusa devolve HTML.
- [x] Um token do ambiente A não alcança dado do ambiente B em nenhum recurso.
- [x] O ambiente ativo é sempre fechado ao fim da requisição, inclusive quando
      há exceção.
- [x] A API não lê cookie nem cabeçalho de aba para decidir o ambiente.
- [x] Um token de ambiente arquivado continua existindo depois da recusa, e
      volta a funcionar quando o ambiente é desarquivado.

## Verificação

Testes cobrindo os cinco casos de recusa, o caso que resolve, o cruzamento
entre ambientes e o token de ambiente arquivado antes e depois de desarquivar.

A porta de qualidade das cinco etapas passa.

## Decisões humanas em aberto

Nenhuma.

## Notas

Esta costura vive no espaço de rotas da ISSUE-016 e não passa pelo decorador de
fragmento — o gate do Alpine e a sessão da borda não se aplicam.
