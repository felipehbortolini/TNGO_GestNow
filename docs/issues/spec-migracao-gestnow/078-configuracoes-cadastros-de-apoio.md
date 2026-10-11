---
id: ISSUE-078
title: "Cadastros de apoio: empresas, pessoas, projetos, sistemas, unidades e locais"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 7
onda: 16
blocked_by:
  - ISSUE-054
blocks:
  - ISSUE-087
labels:
  - ready-for-agent
source_requirements:
  - HU-135
  - HU-080
spec_decisions:
  - D8
  - D10
---

# Cadastros de apoio: empresas, pessoas, projetos, sistemas, unidades e locais

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D8, D10.
> Entrega 7 (Qualidade, HSE e Configurações), onda 16 (Configurações).
> Histórias: 135, 80. Bloqueada por: ISSUE-054.

## O que construir

A tela **Configurações > Cadastros** mantém os cadastros que alimentam os
formulários: empresas, pessoas, projetos (código, nome, cliente, orçamento,
datas, padrões de numeração e as notas de ponderação), sistemas (hierarquia da
punch list), unidades, locais e disciplinas. Exclusão de cadastro em uso é
recusada com a mensagem de onde ele é usado. Um **projeto novo** nasce com a
configuração padrão da Programação Semanal (função da ISSUE-054).

## Critérios de aceite

- [ ] Cada cadastro tem inclusão, edição e exclusão com validação no servidor.
- [ ] Excluir cadastro em uso é recusado com a mensagem.
- [ ] O projeto novo já tem a configuração padrão da programação.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (validação, exclusão em uso e projeto novo).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `GI.api.cadastros` e `mock-base` do protótipo; cadastros de apoio do app de Programação Semanal.

## Registro de execução

Fatia entregue em 10/10/2026: a tela **Configurações > Cadastros**, sobre as tabelas da 0001
(`empresa`, `pessoa`, `projeto`, `sistema`, `unidade`, `local`, `disciplina`, `portfolio_ponderacao`
e `cliente`) — **sem migração**. A fachada (`service.py`) ganhou a leitura da tela
(`registers_overview`: sete cadastros com a empresa, o projeto e o gerente de cada linha e as
notas de ponderação como selos), o carregamento e as listas dos formulários
(`register_form_values`, `register_form_options` — empresas, pessoas, projetos, os dois tipos de
empresa e unidade, as faixas de apetite da escala de riscos vigente e os critérios de nota da
carteira vigente), a gravação (`save_register`, uma validação por campo em `InvalidDataError`) e
a exclusão (`delete_register`). Regras: **empresa** com nome único sem diferenciar maiúsculas e
tipo Contratada/Fornecedor/Gerenciadora; **pessoa** com e-mail de formato único (normalizado);
**projeto** com código único, **cliente pelo próprio formulário** (reusado pelo nome sem
diferenciar maiúsculas; sigla obrigatória só no cliente novo), gerente do cadastro, apetite de
uma faixa da escala vigente, datas com término não anterior ao início, orçamento em reais
(`forms.parse_money`), padrões de numeração opcionais e as **notas de ponderação**
(`nota_<criterio>`, na faixa `notaMinima..notaMaxima`) substituídas na versão vigente do grupo
`portfolio`; **sistema** e **local** com código único no projeto; **unidade** com tipo
medida/organizacional e código único no tipo; **disciplina** com nome único. O **projeto novo
nasce com a configuração padrão da Programação Semanal** pela fachada dona
(`programacao_semanal.service.ensure_settings`, 60/75/15 e a regra de desvio ligada) e a edição
não a toca; a exclusão do projeto chama a fachada nova `remove_settings` antes do delete. A
**exclusão em uso** é recusada com a mensagem de onde o registro é usado: as referências do
próprio módulo são contadas antes (empresa ← pessoas/colaboradores; pessoa ← colaborador/gerente;
projeto ← sistemas/papéis/notas) e, para as demais, a exclusão roda num savepoint e a chave
estrangeira decide — a tabela bloqueadora sai do diagnóstico da violação (ou da mensagem do
banco) e vira o rótulo em português pelo mapa `_USED_BY_LABELS` ("item da EAP", "contrato",
"risco", "item da punch list", "ITP", "atividade da Programação Semanal"...), com a trilha de
auditoria em mensagem própria. As rotas (`routes.py`, nomes `registers_*` únicos;
`Access(module="configuracoes")` — Gestor e Admin; Membro, Visualizador e Fornecedor recebem 403)
trazem a tela num fragmento (`cadastros-conteudo`), um **modal por tipo** desenhado pelo servidor
em `cadastros-modal-corpo` (GET novo/editar, POST grava e devolve a tela — o modal fecha no
sucesso; a recusa volta no formulário), a exclusão confirmada por `TN.confirmarExclusao` (a
recusa volta na tela com o toast), e Excel e PDF pelos mecanismos genéricos
(`registers_document`: as sete tabelas com as mesmas colunas da tela). O trio foi reescrito no
padrão das telas com modal. Os 68 testes novos (`test_cadastros_rotas.py`) cobrem o 403 por
perfil e vínculo, a tela, os modais por tipo, a criação/edição/exclusão de cada cadastro, as
validações, as exclusões em uso do módulo e de outros módulos (EAP e ITP por FK), o projeto que
cria cliente, configuração e notas, o reuso do cliente, a edição que não mexe na configuração, o
projeto descartável excluído e o que já gravou recusado pela trilha, e os exports. **Correção da
ISSUE-076 achada no levantamento**: `_create_version` não copiava as `PortfolioWeight` para a
versão nova do grupo `portfolio` — uma gravação na tela de Parâmetros zeraria a ponderação de
todos os projetos; agora `_copy_portfolio_weights` copia as notas da versão anterior (teste novo
em `test_parametros_rotas.py`). **Divergência registrada**: a trilha de auditoria é só de inclusão
(o gatilho do banco recusa apagar) e a linha de `programacao_configuracao` do projeto novo deixa
trilha com `projeto_id`, então **um projeto que já gravou não sai do cadastro** — a recusa diz "em
uso pela trilha de auditoria" (DIVERGENCIAS). `ruff check`, `ruff format --check` e `ty check`
limpos; as rodadas do fechamento (configurações, programação semanal, plataforma, financeiro e
central de ações — 2.344 testes cada, duas vezes) passam; a porta de qualidade, 5/5.

- DECISAO: cliente pelo formulário do projeto | sem cadastro de clientes próprio: o projeto reusa o cliente pelo nome (sem diferenciar maiúsculas) ou cria um novo com a sigla, obrigatória só no cliente novo | D8, ISSUE-078
- DECISAO: unidades dos dois tipos | medida (Programação Semanal) e organizacional (Central de Ações) no mesmo cadastro, com o tipo no formulário e na lista | ISSUE-078
- DECISAO: exclusão em uso | contagens do próprio módulo e, para os demais, a chave estrangeira dentro do savepoint com a tabela → rótulo em português; um projeto que já gravou é recusado pela trilha de auditoria, que é só de inclusão e aponta para ele | D5b, ISSUE-078
- DECISAO: projeto novo | nasce com a configuração padrão da Programação Semanal pela fachada dona (`ensure_settings`), a edição não a toca e a exclusão a remove por `remove_settings` antes do delete | D9, D10, ISSUE-054, ISSUE-078
- DECISAO: notas de ponderação | a gravação do projeto substitui as notas dele na versão vigente do grupo `portfolio` e a versão nova copia as notas da anterior (correção da ISSUE-076: a ponderação da carteira não zera ao gravar parâmetros) | D8, ISSUE-076, ISSUE-078
- DECISAO: tela sem protótipo | composta do precedente do app (cadastros de apoio) e do `mock-base`: sete cartões, um modal por tipo, sem filtros nem KPIs; Excel e PDF novos | ISSUE-078
