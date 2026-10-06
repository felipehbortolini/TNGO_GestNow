---
id: ISSUE-029
title: "EAC em árvore com itens, visão carteira e ponderação da carteira"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 4
onda: 7
blocked_by:
  - ISSUE-012
  - ISSUE-013
  - ISSUE-016
  - ISSUE-018
blocks:
  - ISSUE-030
  - ISSUE-036
labels:
  - ready-for-agent
source_requirements:
  - HU-087
  - HU-035
spec_decisions:
  - D5
  - D8
  - D6
---

# EAC em árvore com itens, visão carteira e ponderação da carteira

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D5, D8, D6.
> Entrega 4 (Custo e avanço físico), onda 7 (03 Financeiro, base de custo).
> Histórias: 87, 35. Bloqueada por: ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018.

## O que construir

A tela **EAC** mostra a árvore (pacote, subpacote, item) com a linha do projeto
no topo (código 0, nome, total), recolher e expandir, e as colunas código,
descrição, tipo de custo (Material, Mão de obra, Equipamento, Serviço,
Indireto, Contingência), unidade, quantidade, preço unitário, valor orçado
(calculado), CAPEX/OPEX, centro de custo e responsável. Totais de pacote e
subpacote são somados no servidor, em centavos.

Descrição, tipo, classificação, centro de custo e responsável não mudam valor:
dispensam SM, mas exigem justificativa e ficam no histórico de cadastro do
item. Tudo o que muda valor (item novo, remanejamento, revisão, importação) é
da ISSUE-030.

No **Portfólio**, a EAC é somente leitura: linha 0 = portfólio, nível 1 =
projeto ("código · nome"), nível 2 = pacotes principais do projeto.

A **ponderação da carteira** nasce aqui, porque o primeiro critério é o
orçamento vigente da EAC: peso do projeto = soma dos critérios normalizados dos
parâmetros (valor financeiro, criticidade estratégica, complexidade e
exposição a risco, com as notas de 1 a 5), fechada em 100 pelo maior resto
(`ponderarPortfolio`). A edição da ponderação é da ISSUE-080.

## Critérios de aceite

- [x] Valor orçado = quantidade x preço unitário, em centavos, e os totais da árvore somam no servidor.
- [x] Edição cadastral sem justificativa é recusada; com justificativa, fica no histórico do item.
- [x] No Portfólio, a árvore é somente leitura, com os níveis portfólio, projeto e pacote principal.
- [x] O maior resto tem teste de fronteira (a soma sai sempre 100,00).
- [x] O oráculo afirma BAC de R$ 44,6 mi no projeto 1 e os pesos 55,36 / 29,34 / 15,30.
- [x] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [x] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [x] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [x] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo (orçado, maior resto e ponderação) e de fachada (histórico
de cadastro). Oráculo do BAC e dos pesos.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `eac.html`, `GI.api.financeiro.eac`, `GI.regras.ponderarPortfolio`,
`mock-financeiro` e `mock-portfolio`; README, "03 Gestão Financeira" e "Gestão
de portfólio". EAC = Estrutura Analítica de Custos (CBS em inglês); o indicador
é "Projeção no término".

## Registro de execução
- Data: 2026-10-06.
- Feito: modelo, migração m029 (eac_item), serviço (árvore, carteira, ponderação, histórico), rotas, templates, exportação Excel/PDF, seed, testes (cálculo, oráculo, rota, serviço), view/CSS/JS da tela EAC, LEIA-ME, divergência do BAC (projetos 2 e 3).
- Falta: nada da fatia; testes e porta de qualidade rodam no fim da entrega (orquestrador).
- Fora: importação, item novo, revisão e remanejamento (ISSUE-030); edição da ponderação (ISSUE-080).
DECISÃO: EAC no Portfólio | somente leitura, linha 0 = portfólio, nível 1 = projeto, nível 2 = pacotes principais, com coluna de peso na carteira | D8, ISSUE-029
DECISÃO: Valor orçado | calculado como quantidade x preço unitário em centavos, sem usar o `base` arredondado do protótipo (divergência registrada, pendente de aceite) | D6, ISSUE-029
DECISÃO: Edição cadastral do item | descrição, tipo, classificação, centro de custo e responsável exigem justificativa, sem SM, com histórico e controle de versão | D5, ISSUE-029
