---
id: ISSUE-061
title: "Diligenciamento e recebimento"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 6
onda: 12
blocked_by:
  - ISSUE-060
blocks:
  - ISSUE-062
  - ISSUE-067
  - ISSUE-069
labels:
  - ready-for-agent
source_requirements:
  - HU-103
spec_decisions:
  - D9
  - D5a
---

# Diligenciamento e recebimento

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D9, D5a.
> Entrega 6 (Suprimentos e Riscos), onda 12 (04 Suprimentos).
> Histórias: 103. Bloqueada por: ISSUE-060.

## O que construir

A tela **Diligenciamento e recebimento** lista os pedidos com o próximo marco,
data contratual, previsão, ROS, folga e situação, e o bloco de pedidos
críticos com tratamento pendente. A **ficha do pedido** mostra os 6 marcos de
fabricação (linha de base contratual, previsão, realizado, desvio), o
recebimento, a ação e o risco vinculados e as últimas atualizações.

**Atualizar marco**: realização exige o marco anterior realizado e data até a
referência; previsão não fica no passado; reprogramação pode deslocar os marcos
seguintes na mesma quantidade de dias. **Registrar recebimento** exige o
embarque realizado antes e registra conferência, avarias com descrição,
pendências e anexos. **Importação do ERP**, uma linha por marco.

Folga negativa cria, sem duplicar, a ação na Central (origem Suprimentos,
grupo Diligenciamento, responsável o comprador, prazo de 7 dias). O OTD dos
pedidos passa a alimentar o desempenho do fornecedor (ISSUE-057). O risco
sugerido é ligado na ISSUE-067, e o FAT no 06, na ISSUE-069.

## Critérios de aceite

- [ ] As regras de realização, previsão e reprogramação são recusadas com a mensagem quando violadas.
- [ ] O recebimento sem embarque realizado é recusado.
- [ ] Folga negativa cria uma única ação na Central, mesmo com várias atualizações.
- [ ] O desempenho do fornecedor passa a mostrar o OTD.
- [ ] O oráculo afirma 3 pedidos críticos (folgas −20, −9 e −5) e OTD de 66,7%.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (marcos, recebimento, importação e ação sem duplicar) e o oráculo.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `diligenciamento.html`, `GI.api.suprimentos.pedidos`, `atualizarMarco`, `registrarRecebimento`, `gerarAcao` e `importarPedidos`.
