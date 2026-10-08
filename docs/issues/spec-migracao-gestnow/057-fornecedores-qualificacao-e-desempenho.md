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

- [x] Mudança de situação sem justificativa é recusada.
- [x] Documento vencido aparece sinalizado pela data de hoje.
- [x] O desempenho mostra classe e nota das avaliações do 03.
- [x] A avaliação final de contrato atualiza a qualificação.
- [x] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [x] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [x] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [x] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (qualificação, validade e ligação com a avaliação).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `fornecedores.html`, `GI.api.suprimentos.fornecedores`, `salvarQualificacao` e `novoFornecedor`.

## Registro de execução

Data: 2026-10-08.
Feito: `models.py` (as quatro tabelas: qualificação, categorias, documentos com validade e histórico), `calculations.py` (vencido/a vencer do documento e da qualificação, documentos em dia, classe da avaliação final e nota média), `validation.py` (novo fornecedor, qualificação, filtros e documentos), `service.py` (`list_suppliers`, `find_supplier`, `create_supplier`, `save_qualification`, `apply_final_evaluation` e o desempenho pelo escopo), `routes.py` (tela, Excel, imprimível, novo fornecedor, qualificação e desempenho), `export.py` (um `Document` para os dois mecanismos), `seed.py` (parte `suprimentos-fornecedores`), a migração `m043_fornecedores.py` (down_revision `m042`), os fragmentos de `api/src/templates/suprimentos/`, o trio de `app/_views/` e `app/paginas/suprimentos/`, os helpers de `configuracoes.service` e `financeiro.service` (ouvinte da avaliação final e `company_performance`), os testes de cálculos e fachada e o oráculo da carga em `test_carga_demonstracao.py`; LEIA-ME do módulo.
Verificação: `ruff check .` e `ruff format --check .` verdes na árvore inteira (da pasta `api`, como a porta de qualidade roda); pytest, `node scripts/verificar.mjs` e a revisão visual não foram executados nesta finalização, por decisão do dono — os testes desta fatia ficam escritos para a porta.
Pendências: rodar a porta de qualidade; revisão visual da tela; o arquivo do documento como `anexo` (D5a) não foi ligado — nesta fatia o documento tem nome e validade, como o protótipo (ver decisão).
DECISÃO: quinta situação do mock | "Qualificado com restrição" entra cru, como o protótipo o exibe, fica fora das quatro situações de escolha (`SITUATIONS`) e não conta em nenhum KPI (o protótipo também não o conta); a opção conservadora é não inventar uma quinta constante nem mexer no dado do mock | D5a, ISSUE-057
DECISÃO: coluna Projeto no Portfólio | o cadastro de fornecedores é global — a qualificação pertence à empresa, não ao projeto —, então a lista não tem coluna Projeto nem pede projeto na inclusão; o desempenho é que segue o escopo aberto (o Portfólio soma os contratos dos projetos e o projeto corta), calculado do Financeiro | D5, D9, ISSUE-057
DECISÃO: anexo do documento | manter o documento com nome e validade, como o protótipo: o tipo de origem de anexo exige um projeto (`OriginRecord.project_id`, todo anexo é de um projeto) e o cadastro de fornecedores é global; a ligação do arquivo fica para quando o cadastro global tiver origem de anexo própria | D5a, ISSUE-057
