---
id: ISSUE-030
title: "Revisões da EAC, item novo e remanejamento como SM, aplicados só na aprovação, e importação de itens"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 4
onda: 7
blocked_by:
  - ISSUE-029
  - ISSUE-025
blocks:
  - ISSUE-031
labels:
  - ready-for-agent
source_requirements:
  - HU-087
  - HU-088
  - HU-128
spec_decisions:
  - D9
  - D5
---

# Revisões da EAC, item novo e remanejamento como SM, aplicados só na aprovação, e importação de itens

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D9, D5.
> Entrega 4 (Custo e avanço físico), onda 7 (03 Financeiro, base de custo).
> Histórias: 87, 88, 128. Bloqueada por: ISSUE-029, ISSUE-025.

## O que construir

Toda alteração de valor da EAC passa pela gestão de mudanças.

**Remanejamento** entre itens e **item novo** com recurso de outro item viram
SM do tipo Remanejamento de orçamento (aberta também pela tela da EAC), com as
transferências (origem, destino, valor). O remanejamento só tira saldo livre da
origem (orçado atual menos comprometido menos o reservado em outras SMs
abertas). Até a decisão, o valor fica reservado na origem e aparece em
"Remanejamentos" como pendente; a aprovação da SM aplica as transferências na
EAC, na mesma transação da decisão, conferindo o saldo livre de novo. O item
novo não pode superar o custo aprovado na SM.

Acréscimo ao total só por **nova revisão** a partir de SM aprovada com custo
(papel Gestor). Rev 0 é a linha de base; a revisão consolida os
remanejamentos, aplica o valor da SM e grava, congelada, a linha de base da
Curva S financeira daquela revisão (a curva em si aparece na ISSUE-042). A
**importação de itens** por planilha (fluxo da ISSUE-018) também gera revisão e
exige a SM.

Ligações com a Governança: a análise de impacto passa a validar os itens da
EAC (nível 3); a SM aprovada com custo aparece como pendente na EAC; e o
encerramento da SM é recusado enquanto o custo não estiver incorporado
(conferido pela revisão com a SM).

## Critérios de aceite

- [ ] Remanejamento acima do saldo livre é recusado com a mensagem; dentro dele, reserva na origem e aparece como pendente.
- [ ] Aprovar a SM de remanejamento aplica as transferências; rejeitar libera a reserva.
- [ ] Revisão sem SM aprovada com custo é recusada; com a SM, cria a Rev N e congela a linha de base da revisão.
- [ ] A importação de itens passa pela conferência e gera revisão vinculada à SM.
- [ ] Análise de impacto com item inexistente na EAC é recusada, e encerramento de SM com custo não incorporado é recusado.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada: saldo livre, reserva, aplicação na aprovação (com
atomicidade), revisão, importação e as três ligações com a SM.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `GI.api.financeiro.remanejar`, `novaRevisao`, `novoItemEac` e
`proximoCodigoEac`; README, ajuste de 01/10/2026 em "03 Gestão Financeira".
Demonstração: SM-0009 e 0010 aplicadas; 0011 pendente, de R$ 250 mil.

## Registro de execução

- Data: 2026-10-06.
- Feito: o serviço (`service.reallocate` com saldo livre e reserva, `service.apply_reallocations` na aprovação, `service.create_revision` com a linha de base congelada e o custo da SM, `service.item_options`, `subpackage_options`, `revision_source_options` e `next_revision`), as rotas dos painéis e dos formulários (`GET/POST /eac/revisoes`, `GET/POST /eac/remanejamentos`, `POST /eac/itens`, `GET /eac/revisoes/importar/formulario`, `POST .../importar/conferir` e `.../confirmar`), os fragmentos dos dois painéis com os formulários de Nova revisão, Remanejar e Novo item, o modal da importação com o modelo da ISSUE-018 e a resposta multi-alvo da conferência, o importador `eac-itens`, a exportação das duas tabelas, as três ligações com a Governança (análise valida os itens, SM aprovada com custo vira opção da revisão e encerramento é recusado sem a incorporação), a carga e o oráculo (`governanca-eac` e `test_eac_revisoes_oraculo.py`) e os testes de fachada e de rota.
- Decisão de execução: o item novo por remanejamento nasce na abertura da SM com base zero, porque `mudanca_remanejamento.destino_item_id` é FK não nula — registrado em `docs/DIVERGENCIAS-DO-PROTOTIPO.md`; a importação é confirmada pela revisão vinculada à SM (a confirmação genérica recusa a linha da EAC), e o formulário da importação é um fragmento do servidor aberto no modal, com a conferência devolvendo o resultado e os dois painéis no mesmo alvo.
- Porta de qualidade (`npm run verificar`) e a suíte completa de pytest (1.820 testes) passaram em 06/10/2026.

