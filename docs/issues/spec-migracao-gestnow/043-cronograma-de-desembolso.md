---
id: ISSUE-043
title: "Cronograma de desembolso e envio à tesouraria"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 4
onda: 9
blocked_by:
  - ISSUE-031
  - ISSUE-033
blocks: []
labels:
  - ready-for-agent
source_requirements:
  - HU-091
spec_decisions:
  - D12
---

# Cronograma de desembolso e envio à tesouraria

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D12.
> Entrega 4 (Custo e avanço físico), onda 9 (03 Financeiro, desempenho).
> Histórias: 91. Bloqueada por: ISSUE-031, ISSUE-033.

## O que construir

A tela **Cronograma de desembolso** é gerada a partir do mapa de controle: o
saldo a pagar de cada item (projeção no término menos realizado) é distribuído
nos meses depois do corte, pelos marcos de pagamento e contratos quando
existem e, senão, pelo perfil da projeção. Mostra o histograma mensal previsto
x realizado e a tabela item x mês com totais. **Enviar à tesouraria** passa
pela porta de notificação (simulado enquanto desligada).

## Critérios de aceite

- [ ] A soma dos meses futuros de cada item é igual à projeção menos o realizado (teste).
- [ ] Contrato com marcos de pagamento usa os marcos na distribuição.
- [ ] O envio à tesouraria fica na trilha com o aviso "simulado".
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo da distribuição e de fachada do envio.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `desembolso.html`, `GI.api.financeiro.desembolso`. A tela do protótipo
também usa o histograma de mão de obra (derivado do HHT e da Curva S); ele
passa a ser calculado no servidor e é ligado na ISSUE-072, quando o HHT existir.
