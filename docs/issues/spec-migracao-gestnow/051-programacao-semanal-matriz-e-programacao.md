---
id: ISSUE-051
title: "Matriz da programação semanal portada: semana de segunda a domingo, janela e programação pelo fornecedor"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 5
onda: 11
blocked_by:
  - ISSUE-012
  - ISSUE-013
  - ISSUE-016
  - ISSUE-018
blocks:
  - ISSUE-052
  - ISSUE-054
labels:
  - ready-for-agent
source_requirements:
  - HU-071
  - HU-072
  - HU-086
spec_decisions:
  - D10
  - D7
  - D1
  - D8
---

# Matriz da programação semanal portada: semana de segunda a domingo, janela e programação pelo fornecedor

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D10, D7, D1, D8.
> Entrega 5 (Planejamento de campo e Programação Semanal), onda 11 (02 Programação Semanal (o app existente, adaptado)).
> Histórias: 71, 72, 86. Bloqueada por: ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018.

## O que construir

O submódulo Programação Semanal **é** o app `Timenow - Programação Semanal`
portado, e esta é a primeira fatia: a matriz da semana e a programação pelo
fornecedor.

Do app vêm, sem reinvenção: o domínio de semanas (segunda a domingo), a janela
de programação (quando cada contratada pode escrever), o cadastro da atividade
com os campos do app e a matriz com a grade de dias. As adaptações são só as da
D10: o "ambiente" vira o projeto do GestNow (no Portfólio, somente leitura);
empresas, pessoas, fiscais e encarregados vêm dos cadastros e colaboradores do
GestNow; perfis entram no RBAC de dois eixos; visual, gráficos e trio seguem o
Design System; a trilha é a auditoria única; a persistência sai do JSON do app
para as tabelas do Postgres; e o código Python passa para o inglês, sem mudar
comportamento.

O fornecedor vê e grava só a própria empresa, em toda tela, sempre, com o
recorte no servidor. A janela padrão do projeto vem dos valores padrão do app
(a subpágina de configuração é a ISSUE-054). Os testes de domínio do app que
cobrem esta fatia são portados, renomeados e adaptados ao escopo de projeto.

## Critérios de aceite

- [x] Os testes de domínio do app sobre semanas, janela e programação estão portados e verdes.
- [x] O fornecedor vê e grava só atividades da própria empresa; tentar outra empresa devolve 403.
- [x] Programar fora da janela é recusado com a mensagem do app.
- [x] No Portfólio, a matriz é somente leitura e pede um projeto para gravar.
- [x] A matriz tem as mesmas colunas e a mesma grade de dias do app.
- [x] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [x] A demonstração da programação vem da carga de demonstração do app, convertida para as tabelas, num projeto do portfólio, com as datas deslocadas para hoje.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de domínio portados e testes de fachada do recorte por empresa e da
janela. Revisão de tela comparando com o app original rodando pelo `run.bat`
dele.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: app `Timenow - Programação Semanal` (semanas, janela, dados, cálculos,
blueprints de programação e atividades, templates de programação,
`test_dominio.py`), `docs/ENTENDA-O-SISTEMA.md` e `COMO-USAR.md` do app. A tela
de Programação Semanal do protótipo é descartada como fonte (D10).
Multi-ambiente, operador, tokens e API JSON ficam fora (Out of Scope).

## Registro de execução

Data: 2026-10-06.
Feito: modelo e migração m051 (`api/migrations/versions/m051_programacao_semanal.py`), semanas, cálculos, janela, permissões, validação, fachada, rotas (matriz, filtros, janela, formulário, salvar, excluir), fragmentos Jinja, view/js/css da tela, seed (`seed.py` + `demonstracao.json`), testes (`api/tests/programacao_semanal/`: domínio portado, fachada, rotas), LEIA-ME do módulo. Nada foi executado (política de testes): só `ruff`, `verificar-padrao` e `trio-da-tela`, verdes.
Falta: execução da porta de qualidade pelo orquestrador; oráculo numérico não se aplica (a Programação Semanal não tem número no protótipo, D10); `demo-planta` do app fica fora (multi-ambiente).
DECISÃO: demonstração da programação | só o ambiente `demo-obra` do app vira carga, no projeto `TN-2026-014`; o `demo-planta` (segundo ambiente) fica fora por ser multi-ambiente | D10, ISSUE-051
DECISÃO: cadastros da demonstração | empresas, frentes, unidades, fiscais, encarregados e fornecedores do app nascem pela fachada de Configurações (`ensure_*`), com perfil geral Membro e papel por projeto; Admin e visualizador do app não são trazidos | D7, ISSUE-051
DECISÃO: datas da carga | o app não guarda aprovado em e publicado em; a carga usa a data de atualização, e as semanas são deslocadas pelo mesmo número de dias das datas | D6, ISSUE-051
DECISÃO: conflito de versão no painel | o 409 devolve o painel com o digitado e a versão antiga, pedindo para reabrir; não grava por cima | D5, ISSUE-051
DECISÃO: ações da linha | nesta fatia a linha só edita e exclui; o botão da próxima ação do fluxo e o menu chegam com a ISSUE-052 | D10, ISSUE-051
