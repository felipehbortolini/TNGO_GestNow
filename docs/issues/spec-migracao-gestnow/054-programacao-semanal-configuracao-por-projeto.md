---
id: ISSUE-054
title: "Subpágina de configuração da programação, uma por projeto"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 5
onda: 11
blocked_by:
  - ISSUE-051
blocks:
  - ISSUE-077
  - ISSUE-078
labels:
  - ready-for-agent
source_requirements:
  - HU-079
  - HU-080
  - HU-081
spec_decisions:
  - D10
  - D7
---

# Subpágina de configuração da programação, uma por projeto

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D10, D7.
> Entrega 5 (Planejamento de campo e Programação Semanal), onda 11 (02 Programação Semanal (o app existente, adaptado)).
> Histórias: 79, 80, 81. Bloqueada por: ISSUE-051.

## O que construir

Dentro do submódulo nasce a **subpágina de configuração**, uma por projeto (o
"ambiente" do app). Reúne o que o app tinha em Configurações e é da
programação: os parâmetros (limite de desvio que exige justificativa, faixas de
PPC e aderência e afins), as janelas de programação por empresa, as semanas
liberadas e as liberações extraordinárias. Cadastros de empresas e pessoas e o
de Colaboradores não ficam aqui: são os do GestNow.

Projeto novo nasce com os valores padrão do app, por uma função da fachada que
a criação de projeto (ISSUE-078) vai chamar. Edita quem tem papel de
Planejador no projeto ou é Admin; a mudança vale na hora, e a trilha guarda o
antes e o depois (sem o versionamento com justificativa dos parâmetros gerais).
No Portfólio, a subpágina só pode ser lida e pede para escolher um projeto.

## Critérios de aceite

- [x] Planejador do projeto e Admin editam; Planejador de outro projeto recebe 403.
- [x] A mudança vale na próxima requisição, e a trilha guarda antes e depois.
- [x] A função de padrões cria a configuração de um projeto novo com os valores do app.
- [x] No Portfólio, a subpágina é somente leitura e pede um projeto.
- [x] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (permissão por papel no projeto, efeito imediato, padrões e trilha).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: telas de configurações do app (geral, janelas, cadastros) e o domínio de janela; D10.

## Registro de execução

Data: 2026-10-06.
Feito: fachada `configuration.py` (parâmetros, janela por empresa, padrões `create_default_settings`, trilha antes e depois), `config_screen.py`, `permissions.can_configure`, consultas novas em `repository.py`, rotas `configuracoes`, `configuracoes/parametros` e `configuracoes/janelas` em `routes.py`, fragmento `configuracao.html`, trio da tela (view, CSS, JS), testes de fachada e de rotas (`api/tests/programacao_semanal/test_programacao_configuracao_*.py`), LEIA-ME. Nada foi executado (política de testes): só `ruff` e a leitura sintática do template.
Falta: execução da porta de qualidade pelo orquestrador. Sem migração (as tabelas e a carga da 051 já cobrem) e sem mudança no modelo de dados; sem oráculo (a fatia não tem número novo do protótipo).
DECISÃO: leitura da configuração | quem alcança o módulo lê; o fornecedor lê só a janela da própria empresa; no Portfólio, resumo somente leitura por projeto | D10, ISSUE-054
DECISÃO: limites dos parâmetros | metas e limite de 0 a 100, vazio é o padrão do app, fora disso 422; o app aceitava qualquer número | D10, ISSUE-054
DECISÃO: janela com vários dias | a tela marca qualquer dos sete dias, cada um com horário (o app só permitia um dia); sem dia marcado vale qualquer dia | D10, ISSUE-054
