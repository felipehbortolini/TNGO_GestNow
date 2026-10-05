---
id: ISSUE-024
title: "Análise de impacto obrigatória com alçada mínima calculada"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 3
onda: 6
blocked_by:
  - ISSUE-023
blocks:
  - ISSUE-025
labels:
  - ready-for-agent
source_requirements:
  - HU-126
spec_decisions:
  - D7
  - D9
---

# Análise de impacto obrigatória com alçada mínima calculada

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D7, D9.
> Entrega 3 (Central de Ações e Governança), onda 6 (08 Governança).
> Histórias: 126. Bloqueada por: ISSUE-023.

## O que construir

**Iniciar análise** leva a SM a Em análise de impacto, com o prazo padrão do
parâmetro. O formulário de análise exige custo (centavos, negativo para
redução), prazo (dias no caminho crítico, negativo para antecipação), marco
contratual, escopo, qualidade, riscos, SMS e contrato (texto ou "Sem
impacto"), e os itens da EAC e as atividades do cronograma afetados. Com custo
positivo, a fonte do recurso (aditivo de orçamento, reserva de contingência ou
reserva gerencial) é obrigatória. Remanejamento de orçamento tem custo zero e
as transferências entre itens (origem, destino, valor); Liberação de reserva
tem custo zero, a reserva e o valor.

A **alçada mínima** é calculada no servidor (regra `alcadaMudanca` do
protótipo): Gerente do projeto quando o custo cabe no percentual do orçamento
do parâmetro e a mudança não afeta marco contratual; senão, Comitê. Liberação
de reserva e fonte Reserva gerencial vão sempre ao Comitê. O analista pode
elevar a alçada, nunca rebaixar. Concluir a análise leva a SM a Aguardando
comitê, com a Próxima etapa dizendo quem decide.

Dois pontos dependem de módulos que chegam depois e ficam marcados para eles:
a validação dos itens contra a EAC (ISSUE-030) e o saldo das reservas
(ISSUE-041).

## Critérios de aceite

- [ ] Análise sem os campos obrigatórios é recusada com 422 por campo.
- [ ] A alçada calculada tem teste de fronteira no percentual do orçamento e no marco contratual.
- [ ] Elevar a alçada é aceito; rebaixar é recusado.
- [ ] Remanejamento e Liberação de reserva têm custo zero e os seus campos próprios.
- [ ] A ficha mostra a aba Análise de impacto preenchida e a próxima etapa.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo (alçada) e de fachada (obrigatoriedade, elevação e tipos
especiais).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `GI.regras.alcadaMudanca`, `GI.api.governanca.iniciarAnalise` e
`salvarAnalise`; parâmetros de Mudanças da seção 7.4. O orçamento de
referência da alçada é o que o protótipo usa.
