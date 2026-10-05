---
id: ISSUE-005
title: "Postgres local preparado pelo run.bat, migrações Alembic e banco de teste isolado"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 2
onda: 2
blocked_by:
  - ISSUE-004
blocks:
  - ISSUE-006
  - ISSUE-007
labels:
  - ready-for-agent
source_requirements:
  - HU-151
  - HU-154
spec_decisions:
  - D1
  - D5
---

# Postgres local preparado pelo run.bat, migrações Alembic e banco de teste isolado

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D1, D5.
> Entrega 2 (Plataforma no ar), onda 2 (Dados).
> Histórias: 151, 154. Bloqueada por: ISSUE-004.

## O que construir

O GestNow passa a ter banco. A conexão da aplicação vem de uma variável de
ambiente (`GESTNOW_DATABASE_URL`); nada no código distingue o Postgres local do
Azure Database for PostgreSQL. A camada de banco da plataforma oferece a sessão
do SQLAlchemy 2, a base dos modelos (classes em inglês apontando para tabelas e
colunas em português) e o Alembic configurado para migrações por módulo.

O `run.bat` ganha o preparo do banco, com mensagens sem acento como no app de
Programação Semanal. Ele confere se o serviço do Postgres está rodando e, se
não estiver, diz exatamente o que fazer. Com a URL de administração
(`GESTNOW_PG_ADMIN_URL`, variável de usuário que o dono cria uma vez antes da
execução), cria o papel da aplicação e os bancos `gestnow` e `gestnow_teste`
quando faltam, grava a URL da aplicação na configuração local (fora do git) e
aplica as migrações. Os arquivos do banco ficam na pasta da instalação do
Postgres, fora do OneDrive.

A primeira migração cria as tabelas de plataforma do diagrama (projeto,
empresa, pessoa, colaborador e papéis, parâmetros, auditoria, sequência,
anexo, notificação e cadastros de apoio). O `/api/health` passa a dizer se o
banco responde e em que revisão de migração está.

A infraestrutura de teste nasce aqui: o `conftest` recria o `gestnow_teste`
pelas migrações a cada rodada e roda cada teste dentro de uma transação
desfeita no fim. Nenhum teste toca o banco `gestnow`.

## Critérios de aceite

- [ ] Num Postgres sem os bancos, o `run.bat` cria `gestnow` e `gestnow_teste`, aplica as migrações e sobe o app; na segunda vez, não recria nada.
- [ ] Com o serviço parado ou sem a variável de administração, o `run.bat` para com a instrução de como resolver, sem traceback.
- [ ] Um banco vazio sobe até a última migração sem erro, e o esquema resultante bate com os modelos (teste de migrações da spec).
- [ ] `/api/health` mostra o estado do banco e a revisão da migração.
- [ ] Os testes rodam no `gestnow_teste`, cada um isolado por transação desfeita.
- [ ] Nenhuma senha fica em arquivo versionado nem aparece na saída do `run.bat` ou dos testes.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Teste de migrações (banco vazio até a última, esquema igual aos modelos).
Rodar o `run.bat` duas vezes. Parar o serviço do Postgres e rodar: aparece a
instrução. `npm run verificar` passa.

## Decisões em aberto

Nenhuma.

## Notas

Pré-requisito do dono, antes da execução: Postgres instalado pelo instalador
oficial e a variável `GESTNOW_PG_ADMIN_URL` criada (ver `PROMPT-EXECUCAO.md`).
Dependências novas (`sqlalchemy`, `alembic` e o driver `psycopg`) entram no
`pyproject` e no `requirements.txt`, como manda o Padrão.
