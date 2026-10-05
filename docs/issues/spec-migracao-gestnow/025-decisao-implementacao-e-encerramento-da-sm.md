---
id: ISSUE-025
title: "Decisão com quórum, ações de implementação na Central, emergencial, reapresentação e encerramento"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 3
onda: 6
blocked_by:
  - ISSUE-024
  - ISSUE-019
blocks:
  - ISSUE-026
  - ISSUE-030
  - ISSUE-038
  - ISSUE-041
  - ISSUE-046
labels:
  - ready-for-agent
source_requirements:
  - HU-127
  - HU-128
spec_decisions:
  - D9
  - D5
  - D7
---

# Decisão com quórum, ações de implementação na Central, emergencial, reapresentação e encerramento

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D9, D5, D7.
> Entrega 3 (Central de Ações e Governança), onda 6 (08 Governança).
> Histórias: 127, 128. Bloqueada por: ISSUE-024, ISSUE-019.

## O que construir

O modal **Decisão** registra participantes, data, justificativa e condições
(ata do comitê opcional, vinculada à Central), exige papel Gestor e confere o
decisor: na alçada do Gerente, o gerente do projeto; no Comitê, o quórum
mínimo do parâmetro. Resultados: Aprovada, Aprovada com condições, Rejeitada
(terminal) ou Adiada (volta à pauta por **Reapresentar**, guardando a decisão
anterior). A emergencial tem a ratificação com prazo do parâmetro contado do
início; vencida, vira alerta na ficha.

A **aprovação**, na mesma transação, cria pela costura da Central as ações de
implementação (origem Mudança) sugeridas pela análise (EAC, linha de base e
Curva S, aditivo, riscos, SMS, qualidade), com responsável pela função e prazo
do parâmetro, e leva a SM a Em implementação. Uma falha provocada no meio
desfaz a aprovação inteira (teste transversal de atomicidade).

O **encerramento** (Gestor) é recusado enquanto houver ação de implementação
aberta; cronograma e Curva S, aditivo e riscos são confirmações obrigatórias
quando a análise apontou impacto. A lição opcional do encerramento é ligada na
ISSUE-027, e as conferências de incorporação na EAC e na EAP nas ISSUE-030 e
038.

## Critérios de aceite

- [ ] Decisão sem quórum ou com decisor errado é recusada com a mensagem.
- [ ] A aprovação cria as ações de implementação na Central na mesma transação, com origem Mudança e link de volta.
- [ ] Uma falha provocada depois da criação das ações desfaz a decisão e as ações.
- [ ] Adiada volta à pauta por Reapresentar, e a decisão anterior fica no histórico.
- [ ] Emergencial com ratificação vencida aparece como alerta na ficha.
- [ ] Encerramento com ação de implementação aberta é recusado.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (quórum, decisor, aprovação com ações, atomicidade,
reapresentação, ratificação e encerramento) e de rota (403 para quem não é
Gestor).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `GI.api.governanca.decidir`, `reapresentar`, `iniciarImplementacao`,
`encerrar` e `conferencia`; README, "08 Governança".
