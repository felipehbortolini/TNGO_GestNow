---
id: ISSUE-092
title: "Pronto para publicar no Azure"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 9
onda: 19
blocked_by:
  - ISSUE-091
blocks:
  - ISSUE-093
labels:
  - ready-for-agent
source_requirements:
  - HU-155
  - HU-145
spec_decisions:
  - D16
  - D7
  - D12
  - D5a
---

# Pronto para publicar no Azure

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D16, D7, D12, D5a.
> Entrega 9 (Produto final), onda 19 (Validação final e Azure).
> Histórias: 155, 145. Bloqueada por: ISSUE-091.

## O que construir

O app sai pronto para o Azure, sem publicar (a publicação é um passo do dono).

* O `staticwebapp.config.json` tem o provedor AAD aberto a qualquer conta
  Microsoft (plano Free), as rotas protegidas do Padrão e o redirecionamento de
  401 para o login.
* Todas as variáveis de ambiente ficam documentadas numa tabela (conexão do
  Postgres, armazenamento de anexos, envio de e-mail, modo demonstração ou
  produção, primeiro Admin), com o valor local e o valor no Azure.
* O `docs/PUBLICACAO-AZURE.md` é o guia passo a passo no portal: criar o
  Static Web Apps com o Functions vinculado, o Azure Database for PostgreSQL e
  a conta de armazenamento dos anexos; preencher as variáveis; aplicar as
  migrações; cadastrar o primeiro Admin; publicar pela SWA CLI (o caminho do
  Padrão); ligar o e-mail quando quiser.
* O modo produção é verificado localmente: base vazia, primeiro Admin, sem
  demonstração.

Sem Bicep e sem pipeline Git (decisão do dono).

## Critérios de aceite

- [ ] A configuração do SWA tem o provedor, as rotas protegidas e o redirecionamento de 401.
- [ ] A tabela de variáveis cobre todas as variáveis que o código lê (teste ou checagem automática).
- [ ] O guia cobre cada recurso, as variáveis, as migrações, o primeiro Admin, a publicação e o e-mail.
- [ ] O modo produção sobe localmente vazio, com o primeiro Admin.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Checagem que compara as variáveis lidas pelo código com a tabela; subir em modo produção localmente; porta de qualidade.

## Decisões em aberto

Nenhuma.

## Notas

D16 da spec. Precedente: `PUBLICACAO-ENTREGA-1.md` do app de Programação Semanal.
