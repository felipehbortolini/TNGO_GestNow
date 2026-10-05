---
id: ISSUE-013
title: "Porta de notificação: e-mail via Microsoft Graph escrito e desligado, envio simulado registrado na trilha"
status: in-progress
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 2
onda: 4
blocked_by:
  - ISSUE-006
blocks:
  - ISSUE-019
  - ISSUE-023
  - ISSUE-029
  - ISSUE-044
  - ISSUE-045
  - ISSUE-051
  - ISSUE-064
  - ISSUE-072
labels:
  - ready-for-agent
source_requirements:
  - HU-144
  - HU-145
spec_decisions:
  - D12
---

# Porta de notificação: e-mail via Microsoft Graph escrito e desligado, envio simulado registrado na trilha

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D12.
> Entrega 2 (Plataforma no ar), onda 4 (Serviços transversais).
> Histórias: 144, 145. Bloqueada por: ISSUE-006.

## O que construir

Os envios do protótipo (follow-up de ações, pauta de riscos ao gerente, envio
à tesouraria) passam a usar uma porta de notificação da plataforma.

Desligada por variável de ambiente (o padrão), ela registra o envio na trilha
de auditoria com destinatários e assunto e devolve o aviso "simulado" para a
tela. Ligada (no Azure, com a conta do app e a permissão de envio de e-mail
concedida no Entra), envia de verdade pelo Microsoft Graph, sem mudança de
código. Uma falha no envio não perde o registro que pediu a notificação: fica
na trilha com o erro.

## Critérios de aceite

- [ ] Desligada, uma notificação deixa linha na trilha e a resposta traz o aviso "simulado".
- [ ] Ligada, a porta chama o Graph com destinatários, assunto e corpo (testado com dublê do cliente HTTP).
- [ ] Falha do Graph fica registrada na trilha e não desfaz a gravação do registro de origem.
- [ ] As variáveis de ambiente do envio estão documentadas no README.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Teste de fachada da porta nos dois modos e teste de falha do envio.
`npm run verificar` passa.

## Decisões em aberto

Nenhuma.

## Notas

Precedente: `integracoes/notificacao.py` do app de Programação Semanal. A
tabela completa de variáveis de ambiente é da ISSUE-092.
