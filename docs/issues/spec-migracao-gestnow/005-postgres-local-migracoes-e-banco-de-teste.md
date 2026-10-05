---
id: ISSUE-005
title: "Postgres local preparado pelo run.bat, migrações Alembic e banco de teste isolado"
status: done
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

- [x] Num Postgres sem os bancos, o `run.bat` cria `gestnow` e `gestnow_teste`, aplica as migrações e sobe o app; na segunda vez, não recria nada.
- [x] Com o serviço parado ou sem a variável de administração, o `run.bat` para com a instrução de como resolver, sem traceback.
- [x] Um banco vazio sobe até a última migração sem erro, e o esquema resultante bate com os modelos (teste de migrações da spec).
- [x] `/api/health` mostra o estado do banco e a revisão da migração.
- [x] Os testes rodam no `gestnow_teste`, cada um isolado por transação desfeita.
- [x] Nenhuma senha fica em arquivo versionado nem aparece na saída do `run.bat` ou dos testes.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

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

## Registro de execução

- Decisão da execução (ISSUE-005), pendente de revisão do dono: o papel da aplicação chama-se `gestnow`, com a mesma senha da URL de administração; a URL da aplicação é gravada em `api/local.settings.json` (fora do git, o mesmo arquivo que o host do Functions lê) e carregada para o ambiente por `dev_local.py` e pelo `conftest` dos testes. A URL de administração é lida de forma tolerante: a senha é tudo o que fica antes do último `@` antes do host, aceitando caracteres especiais não codificados (a variável desta máquina tem `@` e `#` sem codificar); a URL gravada sai com a senha codificada. Anotado no Histórico de decisões da spec.
- Decisão da execução (ISSUE-005), pendente de revisão do dono: os testes derivam a URL do banco de teste da URL da aplicação com o sufixo `_teste` e recriam o schema `public` pelas migrações a cada rodada, sem exigir a URL de administração nem privilégio de cluster; um guarda recusa qualquer URL de banco de teste que não termine em `_teste`, para nenhum teste tocar o `gestnow`. Anotado no Histórico de decisões da spec.
- Decisão da execução (ISSUE-005), pendente de revisão do dono: a URL `postgresql://` é normalizada para `postgresql+psycopg://` no código, para a mesma variável valer no local e no Azure com o driver psycopg 3; o `/api/health` mantém `status` e ganha `banco: {situacao, revisao}` (banco fora do ar devolve `situacao: erro` sem derrubar a rota). Anotado no Histórico de decisões da spec.
- Decisão da execução (ISSUE-005), pendente de revisão do dono: as tabelas da plataforma ficam em `api/src/core/models.py` e o projeto e os cadastros de apoio em `api/src/modulos/configuracoes/models.py`, conforme o dono de cada tabela no `MODELO-DE-DADOS.md`; o metadata do `Base` usa convenção de nomes de restrição para as migrações ficarem comparáveis com os modelos. Anotado no Histórico de decisões da spec.
- Verificação: `scripts/prepare_database.py` criou o papel e os bancos na primeira execução (migração `0001_plataforma` aplicada) e, repetido, reportou "ja existia" sem recriar nada; o `run.bat` subiu o app duas vezes (portas 4282 e 4283) com `/api/health` devolvendo `{"banco":{"situacao":"ok","revisao":"0001"}}`; com `GESTNOW_PG_ADMIN_URL` ausente e com o serviço simulado como parado, o `run.bat` parou com a instrução, sem traceback.
- Testes: `api/.venv/Scripts/python.exe -m pytest` — 6 testes passaram (migrações, esquema contra os modelos, isolamento por transação e `/api/health`).
- Porta de qualidade: `npm run verificar` passou nas cinco etapas, sem regra desligada.
- Divergência com o protótipo: nenhuma; esta issue não porta fórmula.
