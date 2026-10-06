---
id: ISSUE-021
title: "Atas: lista, nova ata numerada, dados da reunião e lista de presença com retirada bloqueada"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 3
onda: 5
blocked_by:
  - ISSUE-019
blocks:
  - ISSUE-022
labels:
  - ready-for-agent
source_requirements:
  - HU-051
  - HU-054
spec_decisions:
  - D5
  - D9
---

# Atas: lista, nova ata numerada, dados da reunião e lista de presença com retirada bloqueada

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D5, D9.
> Entrega 3 (Central de Ações e Governança), onda 5 (01 Central de Ações).
> Histórias: 51, 54. Bloqueada por: ISSUE-019.

## O que construir

A tela **Atas** lista as atas do projeto mostrando só a revisão mais recente de
cada linhagem (Número, Rev, Data, Assunto, Empresa principal, Tipo de reunião).
**Gerar nova ata** abre o formulário com Data, Tipo de reunião, Diretoria,
Unidade, Elaborado por e Assunto (150 caracteres com contador), todos
obrigatórios, e Empresas executoras opcional; a numeração segue o padrão do
projeto (`TN-2026-0000`) pela sequência da plataforma.

A **ficha da ata** abre com a faixa (número, revisão, contexto, contagem de
ações) e as abas Dados da Reunião e Lista de Presença; Anotações e Ações chegam
na ISSUE-022. Os modais Empresas executoras (com a principal), Buscar
convidado e Retirar participante funcionam. Retirar empresa ou convidado é
recusado, com a mensagem, quando houver ação em aberto daquele participante.

## Critérios de aceite

- [x] A lista mostra só a revisão mais recente de cada ata.
- [x] Nova ata exige os campos obrigatórios (422 por campo) e recebe o número do projeto.
- [x] Retirar participante com ação aberta é recusado com a mensagem; sem ação aberta, retira e registra na trilha.
- [x] A ficha destaca a Central na barra lateral, e o Voltar retorna à lista.
- [x] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [x] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [x] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [x] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (numeração e retirada bloqueada) e de rota (422 por campo).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `atas.html`, `ata.html`, `js/pages/central-acoes/atas.js` e `ata.js`,
`mock-central`; README, "01 Central de Ações" (retirada bloqueada com ação em
aberto).

## Registro de execução

Data: 2026-10-06. Feito: modelo e migração m021 (`ata`, `ata_empresa`, `ata_participante`, FK de `acao.ata_id`); fachada `minutes_service`; rotas; fragmentos; telas Atas e Ata; Excel e PDF; carga e oráculo; testes; LEIA-ME. Nada rodado (política de testes). Pendências: a porta de qualidade (o orquestrador); anotações e ações da ata na ISSUE-022.
DECISÃO: empresa principal na nova ata | segue o protótipo: seleção opcional ao lado das executoras, e a principal entra sozinha entre elas | D5, ISSUE-021
DECISÃO: editar dados da reunião | fora desta fatia (a spec pede empresas, convidados e retirada); a ficha mostra os dados em leitura | D5, ISSUE-021
DECISÃO: endereço da ficha | `ata?id=` com o id da revisão, porque as revisões repetem o número | D14, ISSUE-021
DECISÃO: tipos de reunião | lista fixa do protótipo (7 tipos), validada no servidor; Unidade vem do cadastro de unidades organizacionais | D5, ISSUE-021
DECISÃO: retirar empresa | bloqueada quando alguém dela é responsável por ação aberta da ata (regra 11.5 do protótipo) | D5, ISSUE-021
DECISÃO: revisão anterior | só leitura; empresas e presença só mudam na vigente, protegidas pela versão da ata | D5, ISSUE-021
DECISÃO: numeração na carga | a sequência do projeto continua depois do maior número do mock (`numbering.start_after`) | D6, ISSUE-021
