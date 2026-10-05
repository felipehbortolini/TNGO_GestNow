---
id: ISSUE-067
title: "Integrações que chegam aos Riscos: risco sugerido do diligenciamento, claim, lição aplicada e cobertura da contingência"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 6
onda: 13
blocked_by:
  - ISSUE-066
  - ISSUE-061
  - ISSUE-033
  - ISSUE-027
  - ISSUE-041
blocks: []
labels:
  - ready-for-agent
source_requirements:
  - HU-103
  - HU-128
spec_decisions:
  - D9
---

# Integrações que chegam aos Riscos: risco sugerido do diligenciamento, claim, lição aplicada e cobertura da contingência

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D9.
> Entrega 6 (Suprimentos e Riscos), onda 13 (05 Riscos).
> Histórias: 103, 128. Bloqueada por: ISSUE-066, ISSUE-061, ISSUE-033, ISSUE-027, ISSUE-041.

## O que construir

Liga as integrações cujo segundo ponto é o módulo de Riscos, cada uma ponta a
ponta, pela fachada do dono:

* **Diligenciamento:** Registrar risco sugerido abre o modal pré-preenchido e
  o risco entra como Em análise, categoria Suprimentos, origem
  "Diligenciamento PED-...", sem duplicar.
* **Claim:** claim relacionado a risco fica vinculado ao registro, com link
  nos dois sentidos.
* **Lições:** Aplicar em projeto pode criar risco Identificado (ameaça para "A
  evitar", oportunidade para "A repetir", origem Lições aprendidas), e a lição
  passa a aceitar a origem Risco encerrado com o número conferido.
* **Contingência:** a cobertura do saldo sobre a exposição (VME das ameaças
  ativas, meta do parâmetro) e a lista de ameaças ativas com as SMs
  vinculadas aparecem na tela de Contingência.
* **Links de origem:** os tipos de Risco passam a resolver na Central e nas
  lições.

## Critérios de aceite

- [ ] Cada uma das cinco integrações tem teste de fachada ponta a ponta.
- [ ] O risco sugerido não duplica para o mesmo pedido.
- [ ] A cobertura da contingência usa só as ameaças ativas e a meta do parâmetro.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada das integrações.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `GI.api.suprimentos.registrarRisco`, vínculo de claim a risco, `GI.api.governanca.aplicarLicao`; README, tabela "Integração entre módulos".
