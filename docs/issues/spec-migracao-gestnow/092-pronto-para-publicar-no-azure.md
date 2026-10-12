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

## Registro de execução

Fatia entregue em 12/10/2026: o app sai pronto para o Azure, sem publicar. O
`app/staticwebapp.config.json` **já atendia** a D16 e o Padrão (rotas `/api/*`, `/_views/*` e
`/_components/*` protegidas, `401 → 302 /.auth/login/aad`, `404 → index`) e não mudou; o
provedor AAD preconfigurado (qualquer conta Microsoft, em qualquer plano) não vive no JSON —
o guia instrui o passo no portal (Settings > Authentication, não configurar nada; criar `auth`
no JSON desligaria o provedor preconfigurado). O `docs/PUBLICACAO-AZURE.md` (270 linhas) é o
passo a passo: Postgres Flexible, conta de armazenamento + container privado, Function App
Python 3.13 (`func azure functionapp publish`), Static Web Apps com o vínculo, as **15
variáveis** numa tabela com valor local × valor no Azure × o que fazem, as migrações
(`alembic upgrade head` com a URL do Azure), o primeiro Admin (`seed_database.py` com
`GESTNOW_MODO=producao` e `GESTNOW_ADMIN_EMAIL`), a publicação pela SWA CLI (`swa deploy` com o
token) e o e-mail no Entra. A tabela é conferida pelo teste
`api/tests/plataforma/test_variaveis_documentadas.py` (varredura do código do app e dos
scripts — `ast` nos `.py`, regex nos `.mjs`/`.js`/`.ps1`/`.bat` — comparada em igualdade
bilateral com o guia; 5 testes). **Modo produção subiu localmente de verdade**: banco novo
`gestnow_prod` migrado até `m075`, seed de produção com **0 clientes/projetos/empresas, 1
pessoa, 1 colaborador Admin, 14 parâmetros**, host em 7073 (WMI, morto no fim) com `/api/health`
ok, `/api/nav` do Admin sem o seletor de perfil, e-mail fora do cadastro recusado (403) e sem
principal pedindo o login (403 com o link). **Decisão registrada para o dono**: a issue/D16
diziam "plano Free", mas o Functions vinculado exige **Standard** (no Free as Functions são
gerenciadas, Python ≤ 3.11 e a API exige 3.13) — o guia usa Standard com o Function App
vinculado e traz a decisão em destaque. **Testes**: escopo do subagente 97 passed (produção +
variáveis); o principal rodou a **suíte completa (4.240 passed**, 28:10) e a porta de qualidade
(**5/5**).

- DECISAO: guia | o passo a passo no portal cobre Postgres, armazenamento, Function App, SWA, as variáveis, as migrações, o primeiro Admin, a publicação e o e-mail; o staticwebapp.config.json já atendia a D16 e não mudou | D16, ISSUE-092
- DECISAO: plano do SWA | o Functions vinculado exige o plano Standard (no Free as Functions são gerenciadas, Python ≤ 3.11 e a API exige 3.13); o guia cria o SWA em Standard — pendente de revisão do dono | D16, ISSUE-092
- DECISAO: variáveis | a tabela do guia documenta as 15 GESTNOW_* (valor local, valor no Azure e o que faz) e um teste bilateral varre o código e os scripts e reprova diferença para mais ou para menos | D16, ISSUE-092
- DECISAO: modo produção | o fumaça local (banco novo, host 7073) confirmou a base vazia (só parâmetros e o primeiro Admin), o Admin entrando com o principal e o e-mail fora do cadastro recusado | D16, D5a, ISSUE-092
