---
id: ISSUE-044
title: "Relato do período"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 5
onda: 10
blocked_by:
  - ISSUE-012
  - ISSUE-013
  - ISSUE-016
  - ISSUE-018
blocks:
  - ISSUE-081
  - ISSUE-083
labels:
  - ready-for-agent
source_requirements:
  - HU-046
spec_decisions:
  - D6
---

# Relato do período

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D6.
> Entrega 5 (Planejamento de campo e Programação Semanal), onda 10 (02 Planejamento, campo).
> Histórias: 46. Bloqueada por: ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018.

## O que construir

A tela **Relato do período** registra o relato semanal (semana ISO) e o mensal
(mês civil) do projeto, registros distintos. Período do início do projeto até
o corrente; período futuro é recusado; duplicidade é recusada (edite o
existente); tipo e período não mudam depois de criados.

Campos: **Atividades do período** e **Atividades do próximo período** (uma por
linha, até 20 linhas de 300 caracteres, ao menos uma) e **Pontos de atenção**
(até 12), cada um com o risco atrelado: natureza (Ameaça ou Oportunidade) e
descrição de 10 a 400 caracteres. Esse risco é a leitura do planejamento e não
tem vínculo com o registro do 05 (o modal orienta registrar no 05 para
tratamento formal).

KPIs (semana anterior e mês anterior registrados ou pendentes, pontos de
atenção do último semanal, relatos registrados), filtro Todos, Semanais e
Mensais, busca, e os modais Novo, Editar, Ver, Copiar do período anterior (traz
o próximo período do relato anterior como atividades do período e os pontos de
atenção para revisão) e Excluir. Gravar exige Membro; excluir, Gestor. O
endereço com tipo, período e abrir leva direto ao cadastro (usado pelo modal do
relatório gerencial).

## Critérios de aceite

- [x] Período futuro e duplicado são recusados com a mensagem.
- [x] Os limites de linhas, caracteres e pontos de atenção são validados no servidor (422 por campo).
- [x] Copiar do período anterior traz o próximo período e os pontos de atenção para revisão.
- [x] Membro grava e Gestor exclui; os demais recebem 403.
- [x] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [x] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [x] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [x] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (período, duplicidade, limites e cópia) e de rota (403 e 422).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `relato.html`, `GI.api.planejamento.relatos` e afins; README, "Relato do período: regras". O botão Análise do período desta tela chega na ISSUE-081.

## Registro de execução

Data: 2026-10-06 (retomada do WIP).
Feito: migração m044, modelos, validação, cálculos, fachada, rotas, fragmentos, view/js/css, exportação Excel e PDF, seed (`planejamento_relato`), MODELO-DE-DADOS, LEIA-ME do módulo.
Feito (retomada): testes de cálculos, fachada e rotas (`api/tests/planejamento/test_relato_*.py`) e oráculo (9 relatos, KPIs); nada executado (política de testes).
Falta: porta de qualidade (`npm run verificar`) e execução dos testes, pelo orquestrador.
DECISÃO: relato sem pontos de atenção | os pontos são opcionais; só as duas listas de atividades exigem ao menos uma linha | D6, ISSUE-044
DECISÃO: carga de demonstração dos relatos | os períodos andam em períodos inteiros (semanas e meses) e não em dias, para a última semana e o último mês fechados continuarem os de hoje | D6, ISSUE-044
DECISÃO: copiar do período anterior | traz o relato mais recente do mesmo tipo antes do período (não só o vizinho) e não grava; sem anterior, avisa | D6, ISSUE-044
DECISÃO: projeto sem início cadastrado | a faixa de períodos começa no período corrente | D6, ISSUE-044
