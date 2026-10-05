---
id: ISSUE-089
title: "Oráculo de paridade completo e prova do cálculo vivo"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 9
onda: 19
blocked_by:
  - ISSUE-088
blocks:
  - ISSUE-090
labels:
  - ready-for-agent
source_requirements:
  - HU-022
  - HU-023
  - HU-156
spec_decisions:
  - D6
  - D5b
---

# Oráculo de paridade completo e prova do cálculo vivo

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D6, D5b.
> Entrega 9 (Produto final), onda 19 (Validação final e Azure).
> Histórias: 22, 23, 156. Bloqueada por: ISSUE-088.

## O que construir

O **teste-oráculo** é consolidado num teste só: carregada a demonstração com a
data injetada em 25/09/2026, os números conhecidos do protótipo saem iguais
(BAC R$ 44,6 mi, CPI 0,96, SPI 0,94, projeção R$ 45,26 mi, 8 ações atrasadas,
3 pedidos críticos, 2 riscos críticos, 4 RNC abertas, 263 dias sem
afastamento, pirâmide 0/16/31/190/1.240, aderência 92,9%, OTD 66,7%, pesos
55,36/29,34/15,30 e exposição R$ 3,4 mi), reunindo as afirmações que cada issue
de módulo já fez.

O teste de **cálculo vivo**: o mesmo cenário com a data de hoje produz atrasos
e dias sem afastamento diferentes, e uma medição nova muda o SPI na consulta
seguinte, sem nenhum passo de recálculo.

**Divergências** (decisão Q31): toda diferença encontrada na execução está em
`docs/DIVERGENCIAS-DO-PROTOTIPO.md`, com regra, número do protótipo, número
correto, motivo e situação "pendente de aceite". Erro de fórmula do protótipo:
o GestNow reproduz o número do protótipo e o teste afirma esse número, citando
a divergência. Diferença causada por decisão já tomada na spec (como a EAP
fonte única, Q3): o GestNow segue a spec, e o teste afirma o número do GestNow
citando a divergência.

Uma checagem confirma que nenhum indicador derivado é persistido além das
exceções da D5b.

## Critérios de aceite

- [ ] O oráculo completo passa num banco recém-carregado.
- [ ] O teste de cálculo vivo passa sem nenhum passo de recálculo.
- [ ] Toda diferença tem linha em `docs/DIVERGENCIAS-DO-PROTOTIPO.md`, com a situação, e o teste cita a divergência.
- [ ] Nenhuma coluna de indicador derivado fora das exceções da D5b.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Rodar o oráculo e o teste de cálculo vivo isoladamente e na suíte; `npm run verificar` passa.

## Decisões em aberto

Nenhuma. A política de divergências foi decidida na Q31: mantém o número do protótipo e registra como pendente.

## Notas

Testing Decisions da spec: "Oráculo de paridade com o protótipo" e "Cálculo vivo".
