---
id: ISSUE-080
title: "Início no Portfólio: carteira de projetos e edição da ponderação"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 8
onda: 17
blocked_by:
  - ISSUE-079
blocks:
  - ISSUE-085
labels:
  - ready-for-agent
source_requirements:
  - HU-034
  - HU-035
spec_decisions:
  - D8
  - D6
---

# Início no Portfólio: carteira de projetos e edição da ponderação

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D8, D6.
> Entrega 8 (Visão executiva), onda 17 (Início, análise do período e relatório gerencial).
> Histórias: 34, 35. Bloqueada por: ISSUE-079.

## O que construir

No **Portfólio**, o Início mostra os indicadores consolidados, a tabela
**Carteira de projetos** (peso, BAC, avanço previsto e real, SPI, CPI, projeção
e VAC, término, riscos críticos, pedidos críticos, ações atrasadas, situação e
Abrir) e os pontos de atenção com o código do projeto.

O botão **Ponderação** (Gestor ou Admin) abre a edição dos critérios e das
notas com prévia dos pesos e justificativa obrigatória; gravar cria nova
versão dos parâmetros (grupo Portfólio).

## Critérios de aceite

- [ ] A carteira mostra os números de cada projeto iguais aos do Início do projeto.
- [ ] A prévia não grava; gravar cria nova versão com justificativa.
- [ ] Membro recebe 403 ao gravar a ponderação.
- [ ] O oráculo afirma os pesos 55,36 / 29,34 / 15,30.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (carteira e ponderação) e de rota (403).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: Home no Portfólio e o modal de ponderação do protótipo; README, "Gestão de portfólio".
