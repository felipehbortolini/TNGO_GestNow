---
id: ISSUE-051
title: "Matriz da programação semanal portada: semana de segunda a domingo, janela e programação pelo fornecedor"
status: in-progress
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

- [ ] Os testes de domínio do app sobre semanas, janela e programação estão portados e verdes.
- [ ] O fornecedor vê e grava só atividades da própria empresa; tentar outra empresa devolve 403.
- [ ] Programar fora da janela é recusado com a mensagem do app.
- [ ] No Portfólio, a matriz é somente leitura e pede um projeto para gravar.
- [ ] A matriz tem as mesmas colunas e a mesma grade de dias do app.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A demonstração da programação vem da carga de demonstração do app, convertida para as tabelas, num projeto do portfólio, com as datas deslocadas para hoje.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
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
