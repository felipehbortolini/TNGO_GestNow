---
id: ISSUE-077
title: "Colaboradores: perfil geral, papéis na Programação Semanal por projeto, vínculo e empresa"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 7
onda: 16
blocked_by:
  - ISSUE-054
blocks: []
labels:
  - ready-for-agent
source_requirements:
  - HU-133
spec_decisions:
  - D7
---

# Colaboradores: perfil geral, papéis na Programação Semanal por projeto, vínculo e empresa

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D7.
> Entrega 7 (Qualidade, HSE e Configurações), onda 16 (Configurações).
> Histórias: 133. Bloqueada por: ISSUE-054.

## O que construir

A tela **Configurações > Colaboradores** (Admin) mantém quem entra e o que faz:
e-mail, nome, perfil geral, vínculo, empresa (obrigatória para Fornecedor) e os
papéis da Programação Semanal por projeto. Lista com busca e filtros e
exportação. A mudança vale na requisição seguinte da pessoa e fica na trilha.
O último Admin não pode ser removido nem rebaixado.

## Critérios de aceite

- [ ] Fornecedor sem empresa é recusado.
- [ ] Um colaborador novo entra na requisição seguinte; um removido passa a ver o acesso negado.
- [ ] Papéis da Programação Semanal são gravados por projeto.
- [ ] Remover ou rebaixar o último Admin é recusado.
- [ ] Só o Admin chega à tela (403 para os demais).
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (validações, efeito imediato e último Admin) e de rota (403).

## Decisões em aberto

Nenhuma.

## Notas

Precedente: tela de colaboradores do app de Programação Semanal. Gate de acesso: ISSUE-011.
