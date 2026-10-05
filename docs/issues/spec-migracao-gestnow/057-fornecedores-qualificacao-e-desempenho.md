---
id: ISSUE-057
title: "Fornecedores com qualificação, documentos com validade e desempenho"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 6
onda: 12
blocked_by:
  - ISSUE-034
blocks:
  - ISSUE-058
labels:
  - ready-for-agent
source_requirements:
  - HU-105
spec_decisions:
  - D5a
  - D9
---

# Fornecedores com qualificação, documentos com validade e desempenho

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D5a, D9.
> Entrega 6 (Suprimentos e Riscos), onda 12 (04 Suprimentos).
> Histórias: 105. Bloqueada por: ISSUE-034.

## O que construir

A tela **Fornecedores** mostra situação (Qualificado, Em qualificação,
Restrito, Bloqueado), categorias, validade da qualificação, documentos com
validade (anexos), desempenho (classe e nota das avaliações de contrato do 03;
o OTD dos pedidos entra na ISSUE-061) e valor contratado. **Novo fornecedor**
cria a empresa no cadastro; **Atualizar qualificação** exige justificativa na
mudança de situação (Restrito e Bloqueado exigem o motivo); o modal Desempenho
e histórico mostra a evolução.

Ligação com o Financeiro: a avaliação final de contrato (ISSUE-034) passa a
atualizar a qualificação do fornecedor.

## Critérios de aceite

- [ ] Mudança de situação sem justificativa é recusada.
- [ ] Documento vencido aparece sinalizado pela data de hoje.
- [ ] O desempenho mostra classe e nota das avaliações do 03.
- [ ] A avaliação final de contrato atualiza a qualificação.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (qualificação, validade e ligação com a avaliação).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `fornecedores.html`, `GI.api.suprimentos.fornecedores`, `salvarQualificacao` e `novoFornecedor`.
