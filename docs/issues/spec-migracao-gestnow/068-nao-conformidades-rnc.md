---
id: ISSUE-068
title: "Não conformidades (RNC)"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 7
onda: 14
blocked_by:
  - ISSUE-019
  - ISSUE-027
blocks:
  - ISSUE-069
  - ISSUE-070
labels:
  - ready-for-agent
source_requirements:
  - HU-114
  - HU-115
  - HU-116
spec_decisions:
  - D7
  - D9
  - D5a
---

# Não conformidades (RNC)

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D7, D9, D5a.
> Entrega 7 (Qualidade, HSE e Configurações), onda 14 (06 Qualidade).
> Histórias: 114, 115, 116. Bloqueada por: ISSUE-019, ISSUE-027.

## O que construir

A tela **Não conformidades** mostra filtros (busca, situação, severidade,
disciplina), KPIs e a lista com a próxima etapa e as ações; a ficha abre em
modal com contenção, causa raiz, disposição e concessão, verificação, ações da
Central e histórico. O endereço com a busca por número abre a ficha.

Fluxo: Aberta, Em análise de causa, Ação corretiva, Verificação de eficácia,
Encerrada; Cancelada só antes da ação corretiva (Gestor, com motivo). A
abertura exige descrição (o que, onde, requisito) e **contenção imediata**; o
prazo de tratamento vem da severidade (parâmetros) e vale até a ação corretiva
concluída. A análise (5 porquês, Ishikawa ou árvore de causas; causa raiz;
disposição) cria ao menos uma **ação corretiva na Central** (origem RNC).
Disposição Reparo ou Usar como está exige a **concessão do cliente** (anexo e
data). Com as ações concluídas, a RNC vai para verificação, prevista para N
dias depois (parâmetro). A verificação é do Gestor e **não pode ser feita por
quem respondeu pela análise**; eficaz encerra (lição opcional em Rascunho no
08, origem RNC), ineficaz volta para Ação corretiva e conta reincidência. Custo
da não qualidade (retrabalho, reparo, ensaios, perdas) atualizável com a
composição.

## Critérios de aceite

- [ ] Abertura sem contenção é recusada, e o prazo segue a severidade do parâmetro (teste de fronteira).
- [ ] A análise cria ao menos uma ação corretiva na Central com link de volta.
- [ ] Reparo ou Usar como está sem concessão anexada é recusado.
- [ ] Verificador igual a quem fez a análise recebe 403; ineficaz volta e conta reincidência.
- [ ] Cancelamento depois da ação corretiva é recusado.
- [ ] O oráculo afirma 4 RNC abertas em 25/09/2026.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (fluxo, prazo, concessão, segregação e lição) e o oráculo.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `rnc.html`, `js/pages/qualidade/rnc.js` e `qualidade.js`, `mock-qualidade`; README, "Regras (06 Gestão da Qualidade)". A lição passa a aceitar a origem RNC.
