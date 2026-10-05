---
id: ISSUE-003
title: "Modelo de dados, parte 1: plataforma, cadastros, Central de Ações, Governança e Financeiro"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 1
onda: 1
blocked_by:
  - ISSUE-002
blocks:
  - ISSUE-004
labels:
  - ready-for-agent
source_requirements:
  - HU-152
  - HU-154
spec_decisions:
  - D5
  - D5a
  - D5b
  - D7
  - D8
---

# Modelo de dados, parte 1: plataforma, cadastros, Central de Ações, Governança e Financeiro

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D5, D5a, D5b, D7, D8.
> Entrega 1 (Fundação documentada), onda 1 (Repositório, estrutura e modelo de dados).
> Histórias: 152, 154. Bloqueada por: ISSUE-002.

## O que construir

Desenha em `docs/MODELO-DE-DADOS.md` a primeira metade do diagrama de entidades
do GestNow, em Mermaid legível no próprio Markdown, com uma linha por tabela
dizendo o que ela guarda e qual módulo é o dono.

Cobre a **plataforma** (projeto, empresa, pessoa, colaborador com perfil geral,
vínculo e empresa, papel na Programação Semanal por projeto, versões e valores
de parâmetros, trilha de auditoria só de inclusão, sequência de numeração por
projeto e tipo, anexo com metadados e registro de origem, registro de
notificação), os **cadastros de apoio** (sistemas, unidades, locais,
disciplinas e catálogos), a **01 Central de Ações** (ação com origem e
referência, replanejamentos, ata com revisões e linhagem, participantes,
anotações e itens por grupo), a **08 Governança** (SM, análise de impacto,
transferências de remanejamento, decisão e participantes, lição, aplicação de
lição) e o **03 Financeiro** (EAC em três níveis, revisões, remanejamentos,
projeção com histórico, custos do ERP por item e mês, reservas e movimentos,
linha de base da curva financeira por revisão, contrato, medição, aditivo,
marco de pagamento, claim, extensão de prazo e avaliação com os pesos
gravados).

Regras do desenho (D5): uma tabela por entidade; nomes de tabela e coluna em
português, snake_case, iguais ao glossário do `CONTEXT.md`; chaves estrangeiras
e restrições no banco; `projeto_id` em todo registro de projeto; coluna
`versao` em todo registro editável; centavos (inteiros) e datas sem hora em
`date`; somente fatos (D5b), com as exceções históricas da D5b anotadas.

No fim do documento, uma tabela de cobertura lista cada coleção dos mocks do
protótipo destes módulos e a tabela que a recebe; nenhuma coleção fica sem
destino.

## Critérios de aceite

- [x] O diagrama cobre todas as entidades listadas, com cardinalidade e chaves estrangeiras.
- [x] Cada tabela tem uma linha de descrição com o módulo dono.
- [x] A tabela de cobertura mapeia 100% das coleções dos mocks de base, configuração, Central, Governança e Financeiro, inclusive a parte desses módulos no mock do portfólio.
- [x] Nenhum indicador derivado vira coluna, salvo as exceções da D5b, cada uma anotada.
- [x] O documento registra o estado "aceito para execução" (decisão Q30) e diz que a revisão do dono acontece no fim da execução.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Conferir a tabela de cobertura contra as coleções de `window.MOCK` dos mocks
citados (por script ou leitura); `npm run verificar` passa.

## Decisões em aberto

Nenhuma. O portão de aceite do diagrama foi resolvido na decisão Q30: aceito para execução, com revisão do dono no fim.

## Notas

Fontes: mocks `mock-base`, `mock-config`, `mock-central`, `mock-governanca`,
`mock-financeiro` e a parte correspondente de `mock-portfolio`; README do
protótipo, seções 3 e 7. Mudança posterior de modelo atualiza o diagrama na
mesma entrega (D5).

## Registro de execução

- Decisão da execução (ISSUE-003), pendente de revisão do dono: os parâmetros versionados ficam em `parametro_versao` + `parametro_valor` (chave, tipo, valor, ordem) e as notas da carteira em `portfolio_ponderacao`, filha da versão do grupo portfólio; a spec pede versões e valores, sem fixar a forma. Anotado no Histórico de decisões da spec.
- Decisão da execução (ISSUE-003), pendente de revisão do dono: tabelas-filhas do agregado herdam `projeto_id` e a proteção de `versao` da raiz; não repetem as colunas. Anotado no Histórico de decisões da spec.
- Decisão da execução (ISSUE-003), pendente de revisão do dono: `analisesPeriodo` de `mock-financeiro` tem a tabela `analise_periodo` desenhada na parte 2 (ISSUE-004); a cobertura da parte 1 aponta para lá. Anotado no Histórico de decisões da spec.
- Divergências estruturais com o protótipo (Q31) registradas em `docs/DIVERGENCIAS-DO-PROTOTIPO.md`, todas "pendente de aceite": valores agregados da EAC, séries da Curva S financeira, valor do marco de pagamento, reservas, ponderação da carteira e sessão/referência/escopo.
- Verificação da cobertura: script Node carregou `window.MOCK` dos mocks citados e conferiu 6 + 2 + 2 + 2 + 13 coleções e as 15 da parte desta issue em `mock-portfolio`, todas com destino (40 linhas de cobertura). `npm run verificar` passou nas cinco etapas, sem regra desligada.
