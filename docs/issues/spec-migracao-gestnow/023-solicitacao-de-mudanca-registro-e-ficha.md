---
id: ISSUE-023
title: "Solicitação de mudança: registro, nova SM numerada, ficha e cancelamento"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 3
onda: 6
blocked_by:
  - ISSUE-012
  - ISSUE-013
  - ISSUE-016
  - ISSUE-018
blocks:
  - ISSUE-024
  - ISSUE-027
  - ISSUE-033
  - ISSUE-065
labels:
  - ready-for-agent
source_requirements:
  - HU-125
spec_decisions:
  - D9
  - D5
---

# Solicitação de mudança: registro, nova SM numerada, ficha e cancelamento

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D9, D5.
> Entrega 3 (Central de Ações e Governança), onda 6 (08 Governança).
> Histórias: 125. Bloqueada por: ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018.

## O que construir

A tela **Registro de mudanças** lista as SMs (Nº, Título, Tipo e origem,
Impacto em custo, Impacto em prazo, Situação, Próxima etapa) com os KPIs (em
análise, aguardando comitê, aprovadas no período, valor aprovado acumulado e %
do orçamento, impacto de prazo acumulado, tempo médio de decisão) e filtros.

**Nova solicitação** registra tipo (Escopo, Prazo, Custo,
Qualidade/Especificação, Contratual, Remanejamento de orçamento, Liberação de
reserva), origem (Cliente, Contratada, Engenharia, Interna,
Legal/regulatória), prioridade (Normal, Urgente, Emergencial; a emergencial
marca a execução antecipada com início e justificativa) e a descrição, com o
número `SM-TN-2026-0001` pela sequência do projeto. A SM nasce Registrada.

A migração desta fatia já cria as tabelas de análise e de decisão, e a carga
traz as SMs da demonstração completas, para que a lista, os KPIs e a **ficha
da mudança** (barra de etapas e abas Solicitação, Análise de impacto, Decisão,
Implementação e Histórico) mostrem tudo em leitura. Os fluxos de análise e de
decisão chegam nas ISSUE-024 e 025.

**Cancelamento** só pelo solicitante ou por Gestor, antes da decisão, com
justificativa; mudança aprovada não se cancela (registra-se nova SM para
reverter).

## Critérios de aceite

- [x] A nova SM recebe o número do projeto e nasce Registrada; campo obrigatório faltando devolve 422.
- [x] Lista e KPIs batem com a demonstração (as SMs do mock nas situações do mock).
- [x] A ficha mostra a barra de etapas e as cinco abas em leitura.
- [x] Cancelamento só pelo solicitante ou Gestor e antes da decisão; os demais recebem 403, e SM aprovada é recusada.
- [x] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [x] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [x] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [x] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (numeração, situação inicial e regras de cancelamento) e de
rota (403 e 422). Contagem por situação conferida com o mock.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `mudancas.html`, `mudanca.html`, `js/pages/governanca/*`,
`GI.api.governanca.salvarMudanca` e `cancelar`, `mock-governanca`; README,
"08 Governança" e "Gestão de Mudanças".

## Registro de execução

- 2026-10-06 (retomada). Nada foi executado (política do dono: testes só no fim da entrega).
- Feito: modelo, migração `m023_solicitacao_de_mudanca` (down_revision "0003"), fachada, cálculos, validação, apresentação, exportação, rotas, fragmentos, seed, trio das telas `mudancas` e `mudanca` (view, CSS, JS), testes (`api/tests/governanca/`: cálculos, validação, fachada, rotas), oráculo (`test_oraculo_mudancas.py`), LEIA-ME do módulo.
- Falta: executar a porta de qualidade e os testes (orquestrador); `remanejamentos` e `eacItens` da carga esperam o Financeiro (D9, ISSUE do EAC).
- DECISÃO: itens de EAC e remanejamentos do protótipo | não são gravados na carga desta fatia; entram quando o Financeiro for dono de `eac_item` | D9, ISSUE-023
- DECISÃO: cancelamento | permitido em Registrada, Em análise, Aguardando comitê e Adiada; SM aprovada recusada com orientação de nova SM | D5, ISSUE-023
- DECISÃO: emergência | execução antecipada guarda início em `data_inicio_implementacao` e justificativa; início não pode ser anterior ao registro nem futuro | D5, ISSUE-023
