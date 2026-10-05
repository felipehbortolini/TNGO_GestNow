---
id: ISSUE-037
title: "Medição dos pacotes pelo critério, estorno controlado e importação do avanço"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 4
onda: 8
blocked_by:
  - ISSUE-036
blocks:
  - ISSUE-038
labels:
  - ready-for-agent
source_requirements:
  - HU-057
  - HU-058
  - HU-059
spec_decisions:
  - D6
---

# Medição dos pacotes pelo critério, estorno controlado e importação do avanço

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D6.
> Entrega 4 (Custo e avanço físico), onda 8 (02 Planejamento, avanço físico).
> Histórias: 57, 58, 59. Bloqueada por: ISSUE-036.

## O que construir

**Registrar avanço** por pacote recebe as entradas do critério (% concluído
por etapa, quantidade executada, marcos atingidos ou percentual estimado, este
só para pacotes de até 5% de peso); o real é sempre calculado, nunca digitado
como resultado. O acumulado não regride: **estorno** só com justificativa e
papel Gestor. O executado não passa a quantidade da linha de base (exige SM e
revisão). Cada medição guarda data, de, para, autor e observação, e o
histórico aparece no dicionário do pacote.

A **importação do avanço** por planilha (% acumulado ou quantidade executada)
usa o fluxo genérico, com recusa por linha: pacote de planejamento, marco fora
dos degraus e regressão.

## Critérios de aceite

- [ ] Cada critério calcula o real a partir das entradas (teste por critério).
- [ ] Regressão sem estorno é recusada; o estorno exige Gestor e justificativa.
- [ ] Executado acima da quantidade da linha de base é recusado com a mensagem.
- [ ] A importação recusa as linhas inválidas com o motivo e grava as válidas só na confirmação.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (medição, estorno, limite e importação) e de rota (403 no estorno sem Gestor).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `GI.api.planejamento.eapRegistrarAvanco` e `eapImportarAvanco`.
