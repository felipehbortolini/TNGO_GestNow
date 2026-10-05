---
id: ISSUE-011
title: "Login Microsoft com o cadastro de Colaboradores, perfis em dois eixos, recorte por vínculo e modo demonstração"
status: done
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

- [x] Com o cabeçalho do principal simulado no teste, e-mail cadastrado entra e e-mail fora do cadastro vê o acesso negado com a orientação.
- [x] Em demonstração, o seletor de perfil troca a pessoa e a tela reflete o perfil escolhido.
- [x] Fornecedor vê só a Programação Semanal na barra lateral e recebe 403 em qualquer outra rota.
- [x] Cliente com perfil Visualizador vê os módulos e não grava.
- [x] Papel da Programação Semanal vale só no projeto em que foi dado.
- [x] Configurações aparece só para Gestor e Admin.
- [x] A função de segregação recusa com 403 e mensagem.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

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

## Registro de execução

Data: 05/10/2026.

Feito: a identidade, o motor de permissões em dois eixos e o recorte por vínculo, no
servidor. `api/src/core/auth.py` resolve quem chama: no Azure, o principal do Static Web
Apps (`x-ms-client-principal`, e-mail em `userDetails`), procurado no cadastro de
Colaboradores (fora do cadastro ou desativado vê o acesso negado); na demonstração e sem
principal, o seletor de perfil (cookie `gestnow_demo_perfil`) ou o primeiro Admin ativo; em
produção, sem principal não se entra. `api/src/core/rbac.py` traz o perfil geral por
conjuntos de permissões (`Permission`), os papéis da Programação Semanal por projeto
(`has_schedule_role`, `require_schedule_role`), o vínculo (`can_use_module`,
`company_scope`, `require_company`) e a segregação de funções (`require_segregation`).
`routing.fragment_route(access=Access(...))` resolve usuário e escopo e confere módulo e
permissão (403 com a mensagem); o handler recebe `(req, session, context)`. A pendência da
ISSUE-009 está resolvida: a assinatura registrada no Azure é fixada só com `req`, com
teste sobre todas as rotas. `navigation_view` recorta a barra lateral e as abas pelas
mesmas regras (Configurações só Gestor e Admin; Colaboradores só Admin; o fornecedor vê um
único item, a Programação Semanal); tela fora do perfil leva a `/api/acesso-negado`
(`blueprints/acesso.py`), que também guarda o `POST /api/demonstracao/perfil`. No front: o
seletor de perfil e o cartão do usuário (desenhado pelo servidor) em `sidebar.html`,
`trocarPerfil` em `ds/shell.js`, estilo em `ds/shell.css`, texto de `login.html`; e o
`dev_local.py`, que ganhou as duas rotas novas e a variável `GESTNOW_DEV_PRINCIPAL`
(e-mail de uma conta Microsoft simulada, para ver o login real e o acesso negado
localmente). A fachada
de Configurações ganhou a leitura do acesso (`find_access_by_email`, `find_access`,
`list_active_access`). Sem migração: a `colaborador` e os papéis já nasceram na 0001.
Documentação: `api/README.md` (seção "Acesso e permissões"), `MAPA-DE-MODULOS.md`,
`ONDE-ESTA.md`, `CONTEXT.md` e os LEIA-ME de Configurações e da Programação Semanal.

Decisões, anotadas na spec como "Decisão da execução (ISSUE-011), pendente de revisão do
dono": principal e desempate com o seletor; cookie e rota do seletor; conjuntos de
permissão por perfil (Configurações exige `configurar`, a tela Colaboradores exige
`administrar`); fornecedor fora do eixo geral, com um único item na barra e entrada pela
Programação; tela de acesso negado que orienta sem listar os administradores; decorador
com `access` (rota sem `access` segue `(req, session)`) e segregação por `person_id`.

Pendências: o último critério (`npm run verificar`) fica desmarcado, pela política do
dono: os testes foram escritos (`test_rbac.py`, `test_autenticacao.py`,
`test_acesso_rotas.py` com o teste transversal de vínculo, `test_navegacao_por_perfil.py`
e `tests/configuracoes/test_acesso_colaborador.py`, mais o fixture de Admin em
`tests/plataforma/conftest.py` e os auxiliares de `tests/identidades.py`) e só rodei
`ruff format` e `ruff check`, sem apontamento (mais um `node --check` de sintaxe no
`ds/shell.js`); falta a revisão de tela trocando perfis no seletor. Para a ISSUE-092: `GESTNOW_MODO=producao` é obrigatório no Azure (sem ele, uma
requisição sem principal entra como o Admin da demonstração) e o guia deve confirmar que a
API só é alcançável pelo Static Web Apps, porque é ele quem grava o cabeçalho do principal.
Para a ISSUE-077: gravar o e-mail em minúsculas (a busca já ignora a caixa) e a rota de
Colaboradores usar `Access(module="configuracoes", permission=Permission.ADMINISTER)`. Para
as issues de módulo: toda rota declara `Access(module=<pasta do módulo>)`, a fachada chama o
`rbac` (o fornecedor não tem permissão geral: na programação age pelos papéis e pelo
`company_scope`) e o `/.auth/me` do `dev_local.py` só avisa o shell de que há sessão.
