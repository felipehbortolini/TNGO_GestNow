<!-- Progresso da migração: ISSUE-008 de ISSUE-093 -->

# Progresso da migração

**Etapa concluída: ISSUE-008 de ISSUE-093** (8 de 93 issues `done`, uma
commitada por issue no git local).

> Este arquivo demarca até onde a execução da migração chegou. Atualizado a cada
> issue fechada; a situação oficial de cada uma é a coluna Situação do
> `docs/issues/spec-migracao-gestnow/index.md` e o campo `status` do arquivo da
> issue.

## Estado

| | |
|---|---|
| Última issue concluída | **ISSUE-008** |
| Primeira pendente | ISSUE-009 (shell, sidebar, navegação e escopo) — execução interrompida, marcadores parciais no ramo `falha/ISSUE-009-20261005`, nada de implementação gravado |
| Entrega 1 (ISSUE-001 a 004) | concluída |
| Entrega 2 (ISSUE-005 a 018) | em andamento (ISSUE-005 a 008 concluídas) |

## Issues concluídas

| Issue | Título | Commit |
|---|---|---|
| ISSUE-001 | O repositório GestNow nasce do Padrão, renomeado, com as referências preservadas e o app subindo localmente | `8caa1d4` |
| ISSUE-002 | Estrutura modular de pastas com LEIA-ME por módulo, mapa "quero mudar X, abro Y", ONDE-ESTA, CONTEXT unificado e ADR da convenção | `588064f` |
| ISSUE-003 | Modelo de dados, parte 1: plataforma, cadastros, Central de Ações, Governança e Financeiro | `de0756d` |
| ISSUE-004 | Modelo de dados, parte 2: Planejamento, Programação Semanal, Suprimentos, Riscos, Qualidade, HSE, análises e relatório | `4a421ca` |
| ISSUE-005 | Postgres local preparado pelo run.bat, migrações Alembic e banco de teste isolado | `c3a40d1` |
| ISSUE-006 | Gravação segura: unidade de trabalho, trilha de auditoria, numeração por projeto e aviso de edição simultânea | `838b4be` |
| ISSUE-007 | Data de hoje, calendário de semanas e períodos, e parâmetros versionados | `f9205e0` |
| ISSUE-008 | Carga de demonstração deslocada para hoje, base de produção vazia com o primeiro Admin e harness do oráculo | `9d2e81a` |

## Fila

A ordem completa, as dependências e o que cada issue entrega estão em
`docs/issues/spec-migracao-gestnow/index.md` e `ENTREGAS.md`. O retrato por
entrega está no `RELATORIO-DE-EXECUCAO.md` (entrega 1 fechada).
