---
id: ISSUE-054
title: "Subpágina de configuração da programação, uma por projeto"
status: proposed
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

- [ ] Planejador do projeto e Admin editam; Planejador de outro projeto recebe 403.
- [ ] A mudança vale na próxima requisição, e a trilha guarda antes e depois.
- [ ] A função de padrões cria a configuração de um projeto novo com os valores do app.
- [ ] No Portfólio, a subpágina é somente leitura e pede um projeto.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (permissão por papel no projeto, efeito imediato, padrões e trilha).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: telas de configurações do app (geral, janelas, cadastros) e o domínio de janela; D10.
