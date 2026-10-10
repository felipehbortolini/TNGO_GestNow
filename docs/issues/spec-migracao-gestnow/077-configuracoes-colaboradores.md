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

## Registro de execução

Fatia entregue em 10/10/2026: a tela **Configurações > Colaboradores**, sobre as tabelas da
0001 (`pessoa`, `colaborador` e `colaborador_papel_programacao`) — **sem migração**. A fachada
(`service.py`) ganhou a leitura da tela (`list_collaborators_overview`: as linhas com pessoa,
e-mail, função, empresa, perfil geral, vínculo, situação e os papéis por projeto, filtradas no
servidor por busca — nome, e-mail, função e empresa, sem diferenciar maiúsculas — e por perfil e
vínculo exatos; os KPIs contam os quatro perfis sobre o universo completo, como o app), a
gravação (`save_collaborator`: cria a pessoa e o acesso ou atualiza; nome obrigatório; e-mail
com formato, minúsculo e único entre quem já tem acesso — o e-mail de uma pessoa sem acesso
reusa a pessoa; perfil em `GeneralProfile` e vínculo em `Bond`; empresa do cadastro obrigatória
no vínculo Fornecedor e limpa nos demais; papéis de projeto existente e papel em
`ScheduleRole`, substituídos pelo conjunto enviado, com a UK sem duplicar; a trilha com
`recording`) e a revogação (`revoke_collaborator`: apaga os papéis e o acesso com a trilha; a
pessoa permanece no cadastro). O **último Admin ativo** não pode ser desativado, rebaixado nem
revogado (422 com a mensagem, no campo `ativo`/`perfil` ou no topo). A tela (`routes.py`, nomes
`collaborators_*` únicos; `Access(module="configuracoes", permission=Permission.ADMINISTER)` —
só Admin, o Gestor recebe 403) traz os dois avisos do precedente adaptados, os KPIs por perfil,
os filtros pela query, o botão Liberar acesso e o Editar de cada linha no mesmo modal
(`colaboradores-modal-corpo`, o editor dos papéis por projeto lê os projetos e os rótulos de
`data-*` e posta um campo repetido `papeis` com `"<projeto_id>:<papel>"`), o Revogar confirmado
por `TN.confirmarExclusao` (a recusa do último Admin volta na própria tela, com o motivo no
toast) e o Excel e o PDF pelos mecanismos genéricos (`colaboradores_document`). O trio foi
reescrito no padrão das telas com modal. Os 35 testes novos
(`test_colaboradores_rotas.py`) cobrem o 403 para Gestor, Membro e Visualizador, a tela com
KPIs e filtros, as validações (fornecedor sem empresa, e-mail inválido e repetido, perfil e
vínculo fora da lista, papel e projeto inválidos), a criação com a entrada na requisição
seguinte (o gate pelo `auth.resolve_user`), a atualização de acesso e pessoa, os papéis sem
duplicar e com remoção pontual, o último Admin nas três formas (rebaixar, desativar, revogar —
e as duas com dois Admins passando), a revogação com a pessoa ficando e o acesso negado, o
modal e os exports. Duas decisões de execução: o **revogar exclui** o acesso e os papéis e a
pessoa permanece no cadastro de apoio (ISSUE-078), mas **quem já deixou trilha de auditoria não
é excluído** — a FK `auditoria.usuario_id → colaborador.id` não tem `ondelete` e a trilha
perderia o autor; a recusa orienta suspender o acesso (`ativo = False`), que nega a entrada na
requisição seguinte do mesmo jeito (registrado em DIVERGENCIAS); e os KPIs contam o universo
completo, como o app precedente. A tela não existe no protótipo do Sistema: foi composta do
precedente do app de Programação Semanal adaptado ao D7 (registrado em DIVERGENCIAS). Defeito
corrigido pelo principal: o erro de modal reusava o alvo da tela de Parâmetros
(`parametros-modal-corpo`); o `_modal_error` virou uma fábrica por alvo
(`_collaborator_modal_error`) e o teste do modal fora do cadastro passou a conferir o alvo.
`ruff check`, `ruff format --check` e `ty check` limpos; as rodadas do fechamento (configurações,
plataforma e programação semanal — 1.315 testes cada, duas vezes) passam; a porta de qualidade,
5/5.

- DECISAO: papéis da Programação Semanal na tela | o modal posta um campo repetido `papeis` com `"<projeto_id>:<papel>"` e o conjunto enviado substitui o atual (o que sai e o que entra ficam na trilha; a UK colaborador+projeto+papel não duplica) | D7, ISSUE-077
- DECISAO: revogação e a trilha de auditoria | revogar exclui o acesso e os papéis, e a pessoa permanece no cadastro de apoio; quem já deixou trilha de auditoria é recusado com a orientação de suspender (`ativo = False`), porque a FK `auditoria.usuario_id` perderia o autor — o gate nega a entrada na requisição seguinte dos dois jeitos | ISSUE-077
- DECISAO: KPIs da tela | a contagem por perfil geral é do universo completo (como o app precedente); os filtros mudam só a lista | ISSUE-077
- DECISAO: tela sem protótipo | composta do precedente do app de Programação Semanal adaptado ao D7 (perfil geral + papéis por projeto, sem operadores e sem multi-ambiente; busca, filtros e exportação novos) | D7, ISSUE-077
