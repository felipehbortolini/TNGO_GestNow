---
id: ISSUE-041
title: "Contingência e reserva gerencial"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 4
onda: 9
blocked_by:
  - ISSUE-039
  - ISSUE-031
  - ISSUE-025
blocks:
  - ISSUE-042
  - ISSUE-067
labels:
  - ready-for-agent
source_requirements:
  - HU-094
spec_decisions:
  - D9
  - D5b
---

# Contingência e reserva gerencial

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D9, D5b.
> Entrega 4 (Custo e avanço físico), onda 9 (03 Financeiro, desempenho).
> Histórias: 94. Bloqueada por: ISSUE-039, ISSUE-031, ISSUE-025.

## O que construir

A tela **Contingência** controla a reserva de contingência (riscos
identificados, integra a linha de base de custo) e a reserva gerencial
(imprevistos, fora da linha de base, liberada só pelo Comitê), constituídas na
linha de base com a base de cálculo.

**Consumo** só por SM aprovada com a fonte da reserva (a fonte Reserva
gerencial exige o Comitê). **Liberação** de saldo (risco encerrado, fase
concluída, encerramento) só por SM do tipo Liberação de reserva, com decisão do
Comitê e valor até o saldo menos o pedido em SMs abertas; aparece no extrato
como Liberação e reduz o saldo e o orçamento do projeto.

Indicadores: saldo (com o saldo previsto pelo avanço planejado), consumo x
limite (avanço físico real mais a tolerância do parâmetro), valor pedido em SMs
em análise e saldo se aprovadas, e reserva gerencial. Gráfico do saldo real x
previsto, composição (orçado da EAC + contingência = linha de base de custo; +
gerencial = orçamento do projeto) e extrato de movimentos; no Portfólio, tabela
por projeto. A cobertura sobre a exposição a riscos e a lista de ameaças
ativas com SMs vinculadas são ligadas na ISSUE-067.

Ligações: a análise e a decisão da SM conferem o saldo da reserva (recusam
acima dele); o painel de mudanças ganha o consumo da reserva; o Mapa de
controle ganha a faixa "Reservas" (o saldo cobre o desvio projetado?).

## Critérios de aceite

- [ ] Consumo só por SM aprovada; liberação só pelo Comitê e limitada ao saldo menos o pedido em aberto (teste de fronteira).
- [ ] Decisão de SM acima do saldo da reserva é recusada.
- [ ] Consumo x limite usa a tolerância do parâmetro (teste de fronteira).
- [ ] A composição soma linha de base de custo e orçamento do projeto corretamente.
- [ ] O Mapa de controle mostra a faixa Reservas, e o painel de mudanças mostra o consumo.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo e de fachada (consumo, liberação e saldo na decisão).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `contingencia.html` e as regras de Contingência do README (ajuste de 01/10/2026).
