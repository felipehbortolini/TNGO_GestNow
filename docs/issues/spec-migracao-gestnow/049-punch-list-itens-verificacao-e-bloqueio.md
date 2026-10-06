---
id: ISSUE-049
title: "Punch list: itens, fluxo com verificação e bloqueio de sistema"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 5
onda: 10
blocked_by:
  - ISSUE-019
blocks:
  - ISSUE-050
labels:
  - ready-for-agent
source_requirements:
  - HU-068
  - HU-069
spec_decisions:
  - D7
  - D9
  - D5a
---

# Punch list: itens, fluxo com verificação e bloqueio de sistema

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D7, D9, D5a.
> Entrega 5 (Planejamento de campo e Programação Semanal), onda 10 (02 Planejamento, campo).
> Histórias: 68, 69. Bloqueada por: ISSUE-019.

## O que construir

A tela **Punch list**, aba Lista, registra itens com numeração
`PL-TN-2026-0001`, hierarquia Área, Sistema, Subsistema e TAG, disciplina,
categoria (A impede o marco seguinte; B fecha até o aceite definitivo; C
conforme acordo), marco vinculado, origem, descrição, empresa executante,
responsável, prazo, identificado por, data de abertura e fotos.

Fluxo: Aberto, Em tratamento, Aguardando verificação, Fechado, voltando para
Em tratamento quando a verificação reprova; Cancelado exige justificativa. O
fechamento exige evidência (anexo) e verificação por pessoa diferente do
executante (segregação). **Sistema com item A aberto fica bloqueado** para o
marco vinculado.

Cada item gera uma ação na Central (origem Punch list) pela costura, e o
status do item e o da ação ficam sincronizados nos dois sentidos. Modais Novo
item, Fechamento com verificação, Filtros e Importação Excel.

## Critérios de aceite

- [x] Fechamento sem anexo é recusado, e o verificador igual ao executante recebe 403.
- [x] Item A aberto bloqueia o sistema para o marco vinculado.
- [x] Item e ação ficam sincronizados nos dois sentidos.
- [x] A importação recusa linhas inválidas e grava as válidas só na confirmação.
- [x] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [x] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [x] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [x] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (fluxo, segregação, bloqueio, sincronização e importação) e de rota (403).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `punch-list.html`, `GI.api.planejamento.punch`; README, "Punch list: regras".

## Registro de execução

Data: 2026-10-06. Feito: `punch_item` e migração `m049` (down_revision `m072`), regras, validação, fachada, importador, exportações, rotas, modais, tela, seed (20 itens), oráculo e testes (cálculo, validação, fachada, rota, importação), LEIA-ME e modelo. Nada foi executado (política do dono).
Pendências: porta de qualidade e execução dos testes pelo orquestrador; painel e gráficos (burndown, aging) são a ISSUE-050; o sentido Central para item é garantido pela regra "tratada na origem" da ISSUE-019 (concluir e replanejar lá são recusados), sem reação registrada.
DECISÃO: modelo do punch_item | 4 colunas a mais (comentario_tratamento, comentario_verificacao, justificativa_cancelamento, reprovacoes); diagrama atualizado | D5, ISSUE-049
DECISÃO: ação do item cancelado | a ação da Central é concluída junto (a Central não apaga ação), em vez de sumir como no protótipo | D9, ISSUE-049
DECISÃO: Central e item | a Central ganhou `update_from_origin` (aditivo) para a ação repetir assunto, grupo, responsável e prazo do item | D9, ISSUE-049
DECISÃO: verificador | é a pessoa logada (não um campo escolhido como no protótipo); 403 se for o responsável pelo item | D7, ISSUE-049
DECISÃO: evidência | exigida ao enviar para verificação e de novo ao aprovar o fechamento (ao menos um anexo do item) | D5a, ISSUE-049
DECISÃO: fotos de abertura e fechamento | são anexos do item (botão Anexos da linha), sem campo no formulário de abertura | D5a, ISSUE-049
DECISÃO: carga | os 20 itens entram sem anexo; as ações vêm da carga da Central; item fechado da demonstração não tem a foto | D6, ISSUE-049
DECISÃO: sistemas na tela | a tabela "Sistemas e liberação por marco" fica na tela da lista, não na aba Painel | D11, ISSUE-049
