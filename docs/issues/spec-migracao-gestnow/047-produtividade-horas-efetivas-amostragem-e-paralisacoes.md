---
id: ISSUE-047
title: "Produtividade: horas efetivas, amostragem do trabalho e paralisações"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 5
onda: 10
blocked_by:
  - ISSUE-046
blocks:
  - ISSUE-048
labels:
  - ready-for-agent
source_requirements:
  - HU-066
spec_decisions:
  - D6
---

# Produtividade: horas efetivas, amostragem do trabalho e paralisações

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D6.
> Entrega 5 (Planejamento de campo e Programação Semanal), onda 10 (02 Planejamento, campo).
> Histórias: 66. Bloqueada por: ISSUE-046.

## O que construir

A aba **Horas efetivas** registra a fiscalização de campo:

* **Jornada** por frente (empresa, área, encarregado, efetivo) e dia, com
  chegada, início e término dos dois turnos. Capacidade produtiva (CP) =
  execução da manhã + execução da tarde; utilização = CP ÷ jornada de
  referência do parâmetro; atraso de início; almoço; HH efetivas (CP x
  efetivo) e HH improdutivas ((jornada − CP) x efetivo). Um registro por frente
  e dia.
* **Amostragem do trabalho:** rodadas com pessoas trabalhando, em trânsito e
  paradas, com motivo (catálogo de 12 motivos de parada e 5 de trânsito); %
  por dia, Pareto de motivos e resumo por empresa e encarregado.
* **Paralisações:** de efetivo (Hhora = pessoas x horas) ou de máquina e
  equipamento (Mhora = unidades x horas), com motivo e responsabilidade
  (Contratada, Cliente, Gerenciadora, Clima, Terceiros); para cliente,
  gerenciadora e terceiros, o formulário orienta notificar no prazo contratual
  e avaliar pleito em Contratos.

## Critérios de aceite

- [ ] CP, utilização, HH efetivas e HH improdutivas têm teste da fórmula.
- [ ] Segunda jornada da mesma frente e dia é recusada.
- [ ] O Pareto de motivos sai em ordem decrescente com o acumulado.
- [ ] Hhora e Mhora calculados conforme o tipo da paralisação.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo e de fachada. A demonstração traz as 120 jornadas, 240 rodadas e 25 paralisações do mock.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `GI.api.planejamento.produtividade.horasEfetivas`, `salvarJornada`, `salvarAmostragem` e `salvarParalisacao`.
