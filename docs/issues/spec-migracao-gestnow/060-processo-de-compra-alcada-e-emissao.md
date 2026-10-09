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

## Registro de execução

- Data: 09/10/2026
- Feito: recomendação de adjudicação (proposta aprovada e fornecedor cadastrado; justificativa de 20 caracteres fora da melhor nota ou sem qualificação), devolução com motivo, aprovação por alçada com segregação de funções (403), gate LLI e limite do saldo da EAC, emissão de pedido (cronograma de fabricação padrão, ação de diligenciamento com folga negativa) e de contrato (fachada do Financeiro), compromisso em `custo_erp` na mesma transação, as quatro telas de modal, a ficha com recomendação/aprovação/documento emitido, a migração `m048_pedidos_de_compra.py` (pedido, pedido_marco e a FK de `contrato.pacote_compra_id`), a carga `suprimentos-pedidos` (14 pedidos e 84 marcos) e os testes de cálculo, fachada (com o transversal de atomicidade), rotas e oráculo.
- Verificação: testes escritos e não executados (política de testes do dono); `ruff check`/`format` e `ty check` passam nos arquivos tocados; a migração não foi executada num banco vazio (política).
- Pendências: ISSUE-061 (diligenciamento e recebimento: carrega o `recebimento` do mock e liga o OTD); a porta de qualidade fica para o dono.
- DECISAO: emissão tudo ou nada | pedido/contrato, compromisso na EAC e ação de diligenciamento na transação do chamador, com as fachadas do Financeiro (`create_purchase_contract`, `commit_purchase_cost`) e da Central (D9) | D9, D5, ISSUE-060
- DECISAO: numeração do pedido e do contrato | série global por ano do maior número existente (`core.numbering.next_series_number`), como o protótipo; na demonstração completa o próximo é `PED-2026-0015`/`CT-2026-029` e não os números do README (divergência registrada) | D5, ISSUE-060
- DECISAO: cronograma de fabricação padrão | as seis proporções do protótipo (15/30/75/85/93/100%) entre a emissão e a data contratual, com arredondamento meio para cima | D5b, ISSUE-060
- DECISAO: aprovador da adjudicação | é um registro de pessoa escolhido no formulário; a segregação compara o aprovador escolhido com o comprador e com quem recomendou (403), como o protótipo, e não o usuário da sessão | D7, ISSUE-060
- DECISAO: devolução sem data | o motivo volta à negociação e a linha da trilha usa a data de referência, como o protótipo (o formulário não coleta data) | D5b, ISSUE-060
- DECISAO: recebimento do mock fora da carga | o `recebimento` (conferência, avarias e pendências) fica para a ISSUE-061; a carga grava só o pedido, os marcos e a `entrega` | D5, ISSUE-060
