---
id: ISSUE-013
title: "Porta de notificação: e-mail via Microsoft Graph escrito e desligado, envio simulado registrado na trilha"
status: done
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

- [x] Desligada, uma notificação deixa linha na trilha e a resposta traz o aviso "simulado".
- [x] Ligada, a porta chama o Graph com destinatários, assunto e corpo (testado com dublê do cliente HTTP).
- [x] Falha do Graph fica registrada na trilha e não desfaz a gravação do registro de origem.
- [x] As variáveis de ambiente do envio estão documentadas no README.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Teste de fachada da porta nos dois modos e teste de falha do envio.
`npm run verificar` passa.

## Decisões em aberto

Nenhuma.

## Notas

Precedente: `integracoes/notificacao.py` do app de Programação Semanal. A
tabela completa de variáveis de ambiente é da ISSUE-092.

## Registro de execução

Data: 05/10/2026.

Feito: a porta de notificação da plataforma. `api/src/core/notification.py` traz a
interface do canal, o pedido (`NotificationRequest`), o envio simulado (o padrão) e
`send`: confere o pedido, entrega pelo canal que `GESTNOW_ENVIO_EMAIL` escolhe, grava
uma linha em `notificacao` e uma linha na trilha (destinatários, assunto, corpo,
situação e, se falhou, o erro) na transação da requisição, e devolve o aviso para a tela
(`notice`) e o tipo do toast (`toast_kind`). `api/src/core/graph_mail.py` é o envio por
Microsoft Graph (`sendMail`), escrito e desligado, com cliente HTTP injetável e o padrão
só na biblioteca padrão (`http.client`, https). Falha de envio não vira exceção: a
situação fica `erro`, o texto vai na trilha e o registro de origem grava como sempre.
As variáveis, com o valor local e o do Azure, estão em `api/README.md` (seção
Notificação). Sem migração: a tabela `notificacao` já nasceu na 0001.

Decisões, anotadas na spec como "Decisão da execução (ISSUE-013), pendente de revisão do
dono": nomes e valores das variáveis (`GESTNOW_ENVIO_EMAIL`, `GESTNOW_GRAPH_TENANT_ID`,
`GESTNOW_GRAPH_CLIENT_ID`, `GESTNOW_GRAPH_CLIENT_SECRET`, `GESTNOW_GRAPH_REMETENTE`, com a
permissão de aplicativo `Mail.Send` consentida pelo administrador); o erro do envio fica
só na trilha, sem coluna nem migração; forma do envio (texto puro, 10 s por chamada, sem
nova tentativa). Para a ISSUE-092: o guia deve orientar o administrador a restringir a
permissão à caixa remetente (política de acesso de aplicativo do Exchange Online). Para as
ISSUE-020, 043 e 066: chamar `notification.send` como último passo do fluxo e levar
`outcome.notice` e `outcome.toast_kind` ao toast.

Verificação: `api/tests/plataforma/test_notificacao.py` (51 testes): porta nos dois modos,
falha do envio em oito formas, cliente HTTP real sem rede e um guarda que reprova qualquer
conexão. Antes da política nova do dono (sem rodar a suíte completa nem o
`npm run verificar` a cada issue), a rodada completa passou: pytest 133 passed e as cinco
etapas da porta de qualidade, sem regra desligada. Depois mudaram só o guarda contra
destinatários numa string, a documentação e a spec; para isso rodei `ruff format`,
`ruff check`, `ty check` e os 51 testes da porta, todos verdes. A suíte inteira e a porta
completa ficam para a rodada do orquestrador. Conferi também, à mão e fora do repositório,
o cliente real contra um servidor TLS local (sucesso, recusa 403, certificado não
confiável e tempo esgotado).
