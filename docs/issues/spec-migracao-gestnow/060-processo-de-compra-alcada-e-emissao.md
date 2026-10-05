---
id: ISSUE-060
title: "Processo de compra: recomendação, aprovação por alçada e emissão de pedido ou contrato"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 6
onda: 12
blocked_by:
  - ISSUE-059
  - ISSUE-032
blocks:
  - ISSUE-061
labels:
  - ready-for-agent
source_requirements:
  - HU-100
  - HU-101
spec_decisions:
  - D7
  - D9
  - D5
---

# Processo de compra: recomendação, aprovação por alçada e emissão de pedido ou contrato

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D7, D9, D5.
> Entrega 6 (Suprimentos e Riscos), onda 12 (04 Suprimentos).
> Histórias: 100, 101. Bloqueada por: ISSUE-059, ISSUE-032.

## O que construir

Completa o fluxo. **Recomendação de adjudicação**: só proposta aprovada
tecnicamente e fornecedor cadastrado; outra que não a melhor nota, ou
fornecedor não qualificado, exige justificativa. **Aprovação por alçada**
(faixas do parâmetro): aprovador diferente do comprador e de quem recomendou;
valor limitado ao saldo a comprometer do item da EAC; LLI antes do gate de
investimento exige a aprovação do gate LLI. **Devolver** volta para Negociação
com motivo.

**Emissão**, tudo ou nada numa transação: equipamento e material geram
**pedido** (`PED-2026-0012` em diante na demonstração) com cronograma de
fabricação padrão a partir do prazo da proposta; serviço e EPC geram
**contrato no 03** pela fachada do Financeiro. O valor fica **comprometido na
EAC**. Pedido que já nasce com folga negativa cria a ação de diligenciamento na
Central.

## Critérios de aceite

- [ ] Aprovador igual ao comprador ou a quem recomendou recebe 403.
- [ ] As faixas de alçada e o limite do saldo da EAC têm teste de fronteira.
- [ ] A emissão cria o pedido ou o contrato e compromete a EAC na mesma transação; uma falha provocada no meio não deixa nada gravado.
- [ ] Pedido emitido com folga negativa cria a ação na Central.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (segregação, alçada, LLI, emissão e o teste transversal de atomicidade) e de rota (403).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `GI.api.suprimentos.acaoProcesso` (recomendação, aprovação, emissão); README, "Fluxo do processo de compra".
