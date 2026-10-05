---
id: ISSUE-011
title: "Login Microsoft com o cadastro de Colaboradores, perfis em dois eixos, recorte por vínculo e modo demonstração"
status: in-progress
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 2
onda: 3
blocked_by:
  - ISSUE-010
blocks:
  - ISSUE-012
  - ISSUE-017
labels:
  - ready-for-agent
source_requirements:
  - HU-001
  - HU-002
  - HU-003
  - HU-004
  - HU-007
  - HU-008
  - HU-009
  - HU-019
spec_decisions:
  - D7
  - D14
---

# Login Microsoft com o cadastro de Colaboradores, perfis em dois eixos, recorte por vínculo e modo demonstração

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D7, D14.
> Entrega 2 (Plataforma no ar), onda 3 (Shell, telas e acesso).
> Histórias: 1, 2, 3, 4, 7, 8, 9, 19. Bloqueada por: ISSUE-010.

## O que construir

A identidade passa a vir do Static Web Apps no Azure (cabeçalho do principal,
provedor AAD aberto a qualquer conta Microsoft) e, no modo demonstração, do
seletor de perfil na barra lateral, como no app de Programação Semanal. O
**cadastro de Colaboradores é a fonte de verdade do acesso**: e-mail fora do
cadastro vê a tela de acesso negado, que explica a quem pedir liberação.

O motor de permissões por conjunto herdado do app de Programação Semanal passa
a ter dois eixos: o **perfil geral** (Visualizador, Membro, Gestor ou Admin;
um, obrigatório), que governa os módulos 01 a 08, Início, relatório e
Configurações; e os **papéis da Programação Semanal** (Planejador, Fiscal,
Encarregado, Fornecedor; zero ou mais), por projeto. O **vínculo** (Timenow,
Fornecedor ou Cliente) e a **empresa** (obrigatória para Fornecedor) completam
o colaborador.

Um decorador único resolve gate do fragmento, escopo, usuário e permissão em
toda rota e recusa com 403 e a mensagem para a tela. O recorte por vínculo é
aplicado no servidor, na fachada: o fornecedor vê só a Programação Semanal (a
barra lateral mostra só esse item e qualquer outra rota devolve 403); o
cliente vê os módulos conforme o perfil geral. Configurações aparece só para
Gestor e Admin.

Uma função de plataforma de segregação de funções (quem elabora não aprova e
afins) fica disponível para os módulos, recusando com 403 e mensagem.

## Critérios de aceite

- [ ] Com o cabeçalho do principal simulado no teste, e-mail cadastrado entra e e-mail fora do cadastro vê o acesso negado com a orientação.
- [ ] Em demonstração, o seletor de perfil troca a pessoa e a tela reflete o perfil escolhido.
- [ ] Fornecedor vê só a Programação Semanal na barra lateral e recebe 403 em qualquer outra rota.
- [ ] Cliente com perfil Visualizador vê os módulos e não grava.
- [ ] Papel da Programação Semanal vale só no projeto em que foi dado.
- [ ] Configurações aparece só para Gestor e Admin.
- [ ] A função de segregação recusa com 403 e mensagem.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada e de rota do gate, dos perfis, dos papéis por projeto e do
vínculo (o teste transversal de vínculo da spec). Revisão de tela trocando
perfis no seletor. `npm run verificar` passa.

## Decisões em aberto

Nenhuma.

## Notas

Precedente: `auth.py`, `rbac.py`, o decorador `com_usuario` e o
`perfil_demo.html` do app de Programação Semanal. A configuração do provedor no
`staticwebapp.config.json` é da ISSUE-092. Sem login com senha (Out of Scope).
