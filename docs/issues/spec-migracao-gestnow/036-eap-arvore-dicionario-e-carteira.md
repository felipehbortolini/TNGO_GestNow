---
id: ISSUE-036
title: "EAP em árvore com dicionário, avanço calculado pelo critério e visão carteira"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 4
onda: 8
blocked_by:
  - ISSUE-029
blocks:
  - ISSUE-037
labels:
  - ready-for-agent
source_requirements:
  - HU-056
spec_decisions:
  - D5
  - D6
  - D8
---

# EAP em árvore com dicionário, avanço calculado pelo critério e visão carteira

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D5, D6, D8.
> Entrega 4 (Custo e avanço físico), onda 8 (02 Planejamento, avanço físico).
> Histórias: 56. Bloqueada por: ISSUE-029.

## O que construir

A tela **EAP** mostra a árvore área (nível 1), subárea (nível 2) e pacote
(nível 3, de trabalho ou de planejamento), com a linha do projeto no topo
(código 0, peso 100%, avanço consolidado e datas extremas). Só os pacotes têm
peso, datas da linha de base, critério de medição e avanço; áreas, subáreas e
o total são somados no servidor (média ponderada pelo peso). Regra dos 100%:
os pesos dos pacotes somam 100% do projeto, e o peso de cada nível é a soma
dos filhos.

O **dicionário** do pacote traz entregável, critério de aceitação, empresa,
responsável e o item da EAC ligado. As colunas previsto, real e desvio (p.p.)
usam as faixas −2 e −5 p.p. dos parâmetros; o real de cada pacote é calculado
pelo critério (`avancoPacoteEap`: etapas, unidades, marco 0/100, marco 50/50 e
percentual estimado) a partir das medições gravadas, que a migração desta fatia
já cria e a carga traz. O registro de medições é da ISSUE-037.

No **Portfólio**, a EAP é somente leitura (portfólio, projeto e pacotes
principais), como a EAC.

## Critérios de aceite

- [ ] A regra dos 100% vale, e o peso de cada nível é a soma dos filhos.
- [ ] O real de cada pacote é calculado pelo critério, com um teste por critério.
- [ ] O desvio usa as faixas dos parâmetros.
- [ ] A demonstração traz 38 pacotes, a Rev 2 vigente, o desdobramento 5.2.1 > 5.2.2 e os dois pacotes com término vencido.
- [ ] No Portfólio, a árvore é somente leitura.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo (avanço por critério e somas ponderadas) e conferência do cenário da demonstração.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `eap.html`, `GI.api.planejamento.eap`, `GI.regras.avancoPacoteEap`,
`mock-planejamento`; README, "EAP: regras".
