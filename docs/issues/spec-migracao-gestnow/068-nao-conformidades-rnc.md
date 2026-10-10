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

## Registro de execução

Fatia entregue em 09/10/2026: a migração `m068` cria a tabela `rnc` conforme
`docs/MODELO-DE-DADOS.md` (FKs de projeto, disciplina, empresa, responsável, abertura, eficácia
e lição; UK projeto + código; CHECKs de situação, origem, severidade, disposição e método) e
sobe/desce/sobe num banco vazio. A fachada (`service.py`) cobre o fluxo inteiro: abertura com a
contenção obrigatória e o prazo da severidade (parâmetro), atribuição e registro da análise
criando ao menos uma ação corretiva na Central com origem `RNC` e link de volta
(`origin_links.register`), concessão obrigatória para Reparo e Usar como está, envio para a
verificação recusado com ação aberta e previsto para `verificacaoEficaciaDias` à frente,
verificação do Gestor com segregação de quem respondeu pela análise (403), encerramento que
abre a lição opcional em Rascunho pela fachada da Governança gravando `rnc.licao_id`, volta
para Ação corretiva quando ineficaz (reincidência contada da trilha), cancelamento só antes da
ação corretiva e custo da não qualidade atualizável na RNC ativa — tudo na mesma transação
(D9). As rotas e os fragmentos seguem D14, com a ficha em modal, as evidências na porta
genérica de anexos (D5a) e Excel/PDF pelos mecanismos genéricos (D12); o trio da tela
(view/CSS/JS) registra `TN.paginas["qualidade/rnc"]`. Os parâmetros do grupo `qualidade` já
estavam vigentes em Configurações com as validações do README (prazos crescentes de 1 a 180
dias, espera de 0 a 180, metas de 0 a 100% e antecedência de 0 a 240 h); a fatia os cobre com
testes. A carga `qualidade-rnc` traz os relatórios convertidos do protótipo (10: os 6 do
`mock-qualidade` e os 4 do `mock-portfolio`) com as datas deslocadas e a numeração de cada
projeto continuando depois do maior número; o oráculo afirma as **4 RNC abertas do projeto 1 em
25/09/2026** (0002, 0004, 0005 e 0006), com os números, as severidades e os prazos do mock, e a
0004 vencida. As divergências do protótipo desta fatia estão registradas em
`docs/DIVERGENCIAS-DO-PROTOTIPO.md` ("pendente de aceite").

- DECISAO: reincidência pela trilha | o MODELO não tem coluna e o protótipo incrementava um contador; a contagem sai das transições de `auditoria` da entidade `rnc` que voltam de Verificação de eficácia para Ação corretiva (só a verificação ineficaz faz isso, então atualizações seguintes não contam de novo), em `calculations.recurrence_count` | D5b, ISSUE-068
- DECISAO: evidências da abertura na ficha | o upload genérico pertence a um registro gravado; o formulário de abertura grava a RNC e as evidências entram na ficha, com o registro de origem `rnc` | D5a, ISSUE-068
- DECISAO: carga com os 10 relatórios convertidos | `prototype_collection("rncs")` reúne os 6 de `mock-qualidade` e os 4 de `mock-portfolio`; a numeração de cada projeto continua depois do maior número (`numbering.start_after`) para a primeira RNC nova não colidir | D6, ISSUE-068
- DECISAO: verificação prevista da data de referência | a prevista é a data de referência da requisição + `verificacaoEficaciaDias` (o protótipo usava a referência), como o parâmetro manda | D6, ISSUE-068
- DECISAO: prazo gravado na carga | usa o prazo do mock convertido (o protótipo já o calculava de data + severidade); a abertura em runtime calcula pelo parâmetro vigente | D6, ISSUE-068
- DECISAO: botões de Gestor por permissão | cancelar e verificar a eficácia só aparecem para Gestor e o servidor recusa com 403; a segregação usa `rbac.require_segregation` com o responsável pela análise | D7, ISSUE-068

