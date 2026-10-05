---
id: ISSUE-033
title: "Contrato: marcos de pagamento, claims e extensões de prazo"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 4
onda: 7
blocked_by:
  - ISSUE-032
  - ISSUE-023
blocks:
  - ISSUE-035
  - ISSUE-043
  - ISSUE-067
labels:
  - ready-for-agent
source_requirements:
  - HU-095
  - HU-096
spec_decisions:
  - D5a
  - D9
---

# Contrato: marcos de pagamento, claims e extensões de prazo

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D5a, D9.
> Entrega 4 (Custo e avanço físico), onda 7 (03 Financeiro, base de custo).
> Histórias: 95, 96. Bloqueada por: ISSUE-032, ISSUE-023.

## O que construir

Aba **Marcos de pagamento**: Nº, descrição, critério de aceite, % do valor,
valor, data prevista, data de conclusão e retenção; fluxo Previsto, Evidência
enviada, Aprovado (fiscal e gestor), Faturado, Pago. O marco só é aprovado com
anexo de evidência, e a soma dos % de um contrato é 100.

Aba **Claims**: número `CLM-TN-2026-0001`; direção (da contratada ou do
contratante); tipo (Prazo, Custo, Prazo e custo); causa; datas do evento e da
notificação, com **alerta de notificação fora do prazo contratual**; valor e
dias pleiteados e reconhecidos; cláusula; documentos. Fluxo Notificado, Em
análise, Em negociação, Acordado (total ou parcial) ou Rejeitado, Em disputa,
Encerrado. O claim acordado cria SM na Governança pela fachada dela, na mesma
transação; o vínculo com risco é ligado na ISSUE-067.

Aba **Extensões de prazo**: número `EOT-TN-2026-0001`; evento causador (pode
vir de um claim); dias solicitados e concedidos; marco afetado; classificação
(Justificável e compensável, Justificável não compensável, Não justificável);
análise de atraso (método, atividades e caminho crítico). Fluxo Solicitada, Em
análise, Concedida (total ou parcial) ou Negada; a concedida prorroga o término
vigente e cria SM para a linha de base do cronograma.

## Critérios de aceite

- [ ] Marco sem anexo não é aprovado, e soma de % diferente de 100 é recusada.
- [ ] Claim notificado depois do prazo contratual aparece com alerta (teste de fronteira no último dia).
- [ ] Claim acordado e EOT concedida criam SM na Governança na mesma transação.
- [ ] EOT concedida prorroga o término vigente do contrato.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada de cada fluxo, do alerta de prazo e das SMs criadas.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `GI.api.financeiro.claims` e `decidirEot`; README, "Claims",
"Extensões de prazo" e "Marcos de pagamento".
