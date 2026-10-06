---
id: ISSUE-019
title: "Ações: costura única de criação, status calculado, lista, kanban, filtros, replanejamento com justificativa e link de origem"
status: in-progress
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 3
onda: 5
blocked_by:
  - ISSUE-012
  - ISSUE-013
  - ISSUE-016
  - ISSUE-018
blocks:
  - ISSUE-020
  - ISSUE-021
  - ISSUE-025
  - ISSUE-027
  - ISSUE-048
  - ISSUE-049
  - ISSUE-065
  - ISSUE-068
  - ISSUE-073
  - ISSUE-074
labels:
  - ready-for-agent
source_requirements:
  - HU-047
  - HU-048
  - HU-053
  - HU-055
spec_decisions:
  - D9
  - D6
  - D14
---

# Ações: costura única de criação, status calculado, lista, kanban, filtros, replanejamento com justificativa e link de origem

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D9, D6, D14.
> Entrega 3 (Central de Ações e Governança), onda 5 (01 Central de Ações).
> Histórias: 47, 48, 53, 55. Bloqueada por: ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018.

## O que construir

A Central de Ações vira a **costura única de ação** do GestNow: uma função da
fachada da Central cria ação com origem (Ata, Punch list, Contrato,
Suprimentos, Risco, RNC, HSE, Mudança, Lição e Produtividade) e referência ao
registro de origem. Todo módulo que gera ação chama essa função, e ela mantém
sincronizados o status da ação e o do registro de origem (cada módulo registra
como reagir).

O status é sempre calculado na consulta, com a data de hoje: Informação;
Concluída quando há data de conclusão; Atrasada quando a Replanejada (ou, sem
ela, a Prevista) é anterior à data de referência; senão Em andamento. O filtro
Em andamento inclui as atrasadas. Só itens do tipo Ação entram na lista.

A tela Ações mostra os KPIs clicáveis (Em dia, Atrasadas, Concluídas, Total),
os filtros em modal (busca, origem, status, responsável) com chips, a tabela
(Origem, Ata, Item, Assunto/Descrição, Responsável, Prevista, Replanejada,
Status) e a visão kanban por status. Replanejar exige justificativa, que fica
no histórico da ação. Ações aceitam anexos.

Clicar na origem leva ao registro que gerou a ação, por uma função de
plataforma de links de origem em que cada módulo registra o seu tipo; os tipos
de módulos que ainda não existem são registrados nas issues deles.

## Critérios de aceite

- [ ] A função de criação é a única forma de gravar ação, e grava origem e referência.
- [ ] O status é calculado com a data injetada nos quatro casos, com teste de fronteira (prevista igual a hoje).
- [ ] Os KPIs filtram a lista, os filtros viram chips removíveis, e o kanban mostra as mesmas ações por status.
- [ ] Replanejar sem justificativa é recusado com 422; com justificativa, a data muda e o histórico guarda a justificativa.
- [ ] O link de origem resolve para os tipos registrados e, para os que ainda não existem, mostra a referência sem link.
- [ ] O oráculo afirma 8 ações atrasadas em 25/09/2026.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo (status), de fachada (criação pela costura, replanejamento,
sincronização com uma origem de teste) e de rota (filtros, 422). Oráculo das 8
atrasadas.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: tela Ações do protótipo, `GI.api.central.acoes` e `resumo`, regra do
status em `regras.js`, `mock-central`; README, seção 3, "01 Central de Ações".
A origem "Pendências" do sistema antigo se chama Punch list.
