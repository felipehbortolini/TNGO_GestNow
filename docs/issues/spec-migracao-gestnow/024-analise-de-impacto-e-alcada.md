---
id: ISSUE-024
title: "Análise de impacto obrigatória com alçada mínima calculada"
status: done
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

- [x] Análise sem os campos obrigatórios é recusada com 422 por campo.
- [x] A alçada calculada tem teste de fronteira no percentual do orçamento e no marco contratual.
- [x] Elevar a alçada é aceito; rebaixar é recusado.
- [x] Remanejamento e Liberação de reserva têm custo zero e os seus campos próprios.
- [x] A ficha mostra a aba Análise de impacto preenchida e a próxima etapa.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
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

## Registro de execução

Data: 2026-10-06.
Feito: modelo (reserva e valor da liberação em `mudanca_impacto`) e migração `m024`; `required_change_authority`, `is_authority_lowered`, `analysis_deadline`; validação por campo (`validate_impact`, `validate_analysis_start`); fachada `start_analysis`, `conclude_analysis`, `impact_form`; rotas `mudanca/analise/iniciar` e `mudanca/analise`; modais e aba Análise de impacto da ficha; testes (cálculo, validação, fachada, rotas); LEIA-ME e MODELO-DE-DADOS. Escritos, não executados.
Falta: nada da fatia; o orquestrador roda a porta de qualidade.
Pendências: validar que os itens são da EAC em nível 3 (ISSUE-030); aviso de custo acima do saldo da reserva (ISSUE-041); carga de `remanejamentos` e `eacItens` do protótipo (próxima carga do Financeiro).
DECISÃO: análise salva só ao concluir | não há rascunho: concluir grava o impacto, define a alçada e envia; em Aguardando comitê ou Adiada a mesma ação revisa o impacto e mantém a situação | D7, ISSUE-024
DECISÃO: liberação de reserva | reserva (Contingência/Gerencial) e valor ficam em colunas novas de `mudanca_impacto` (`liberacao_reserva`, `liberacao_valor_centavos`), pois o custo é zero | D5, ISSUE-024
DECISÃO: itens da EAC | o formulário recebe códigos da EAC; a fachada do Financeiro (`eac_item_ids_by_code`, `eac_item_codes`) os resolve no projeto da SM e recusa o código inexistente | D9, ISSUE-024
DECISÃO: alçada exigida | maior entre o custo absoluto e o total remanejado; liberação de reserva e fonte Reserva gerencial vão sempre ao Comitê | D7, ISSUE-024
