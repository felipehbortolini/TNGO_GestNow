---
id: ISSUE-062
title: "MAS: Mapa de Suprimentos"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 6
onda: 12
blocked_by:
  - ISSUE-061
blocks:
  - ISSUE-063
labels:
  - ready-for-agent
source_requirements:
  - HU-102
spec_decisions:
  - D11
  - D12
---

# MAS: Mapa de Suprimentos

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D11, D12.
> Entrega 6 (Suprimentos e Riscos), onda 12 (04 Suprimentos).
> Histórias: 102. Bloqueada por: ISSUE-061.

## O que construir

O **MAS** não tem cadastro próprio: é montado no servidor a partir do plano de
compras, dos processos e do diligenciamento. Uma linha por pacote e 12 marcos
em dois grupos (Aquisição e Fabricação e entrega), cada um com linha de base,
previsão e realizado.

Situação do marco (`situacaoMarco`): realizado no prazo; realizado com atraso;
vencido sem realização; previsão após a linha de base; a vencer; não se aplica
(fabricação de serviço e EPC). Desvio em dias em relação à linha de base.
Pacote ainda sem pedido tem a linha de base de fabricação **estimada** (itálico
e aviso "LB estimada"), pelas proporções da emissão.

Alternância Datas / Desvio em dias; filtro de fase; filtros por disciplina,
tipo, LLI, comprador, fornecedor e situação, com ordenação; ROS, previsão de
entrega, folga, avanço (real x linha de base) e situação; rodapé com
realizados x previstos por marco; clique na célula abre o detalhe. Avanço de
suprimentos pelos pesos dos marcos do parâmetro (serviço renormaliza só a
aquisição), ponderado pelo valor do pacote; índice = real ÷ previsto.

Exportação Excel (linha de base, previsão ou real e situação de cada marco) e
**PDF A3 paisagem com as células coloridas**.

## Critérios de aceite

- [ ] A situação do marco tem um teste para cada uma das seis regras.
- [ ] Pacote sem pedido mostra a linha de base estimada com o aviso.
- [ ] O avanço de suprimentos e o índice têm teste da fórmula.
- [ ] O PDF sai em A3 paisagem com as células coloridas, e o Excel tem as colunas do protótipo.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo (situação, estimativa e avanço) e teste do Excel e da versão imprimível em A3.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `mas.html`, `GI.api.suprimentos.mas`, `GI.regras.situacaoMarco`; README, "MAS (Mapa de Suprimentos): regras".

## Registro de execução

Fatia entregue em 09/10/2026: a fachada do mapa (uma linha por pacote e os doze marcos nos dois
grupos, com a situação de cada marco, a folga, a situação da linha e o avanço ponderado pelo
valor), as rotas (`mas`, `mas/excel`, `mas/imprimivel` e `mas/pacote/{pacote_id}`), a tela (trio
preenchido com o DS: filtros, segmentos, legenda, rodapé e o detalhe em modal), as exportações
(Excel com as colunas do protótipo e PDF A3 paisagem com as células coloridas) e os testes
(cálculos, fachada, rotas e o oráculo da carga). Não houve migração: o MAS é uma visão calculada
do plano, dos processos e do diligenciamento.

- DECISAO: LB estimada do pacote sem pedido | Sem a coluna da entrega planejada (decisão da ISSUE-058), a LB e a previsão dos marcos de fabricação interpolam entre o pedido e o ROS pelas proporções da emissão, em itálico e com o aviso "LB estimada" | ISSUE-062
- DECISAO: valor do pacote no avanço | O valor é o do pedido ou o da recomendação da adjudicação; sem nenhum, vale a estimativa com o aviso "estimado" | ISSUE-062
- DECISAO: alternância e fase na consulta | Datas/Desvio e Todos/Aquisição/Fabricação são parâmetros da URL, como os demais filtros, e cada mudança é um GET do mesmo fragmento | ISSUE-062
- DECISAO: detalhe do pacote | O clique na célula abre um modal cujo corpo o servidor entrega por GET (`mas/pacote/{pacote_id}`), sem recarregar a tela | ISSUE-062
- DECISAO: tons das células | O Excel e o A3 usam o mesmo mapa de tons do diligenciamento; "a vencer" e "sem data" ficam sem tom, como no protótipo | D12, ISSUE-062
