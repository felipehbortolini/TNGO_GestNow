---
id: ISSUE-063
title: "Painel de suprimentos"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 6
onda: 12
blocked_by:
  - ISSUE-062
blocks:
  - ISSUE-079
  - ISSUE-081
labels:
  - ready-for-agent
source_requirements:
  - HU-106
spec_decisions:
  - D11
---

# Painel de suprimentos

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D11.
> Entrega 6 (Suprimentos e Riscos), onda 12 (04 Suprimentos).
> Histórias: 106. Bloqueada por: ISSUE-062.

## O que construir

O **Painel de suprimentos** mostra os 9 KPIs do protótipo (entre eles aderência
ao plano de compras, saving sobre a estimativa e de negociação, OTD, pedidos
críticos e avanço do MAS), a curva de contratação (pacotes adjudicados
acumulados, plano x realizado), o avanço físico de suprimentos (Curva S do MAS:
linha de base, real e tendência), o saving acumulado, os pacotes por etapa e os
pedidos por folga em relação ao ROS. As fórmulas seguem a tabela de
indicadores do README.

## Critérios de aceite

- [ ] Cada indicador do painel tem teste da fórmula.
- [ ] O oráculo afirma aderência de 92,9%, saving de 5,2% sobre a estimativa e 4,7% na negociação, e avanço de 90,9% x 97,3% (índice 0,93).
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo e o oráculo de suprimentos.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `painel.html` de Suprimentos, `GI.api.suprimentos.indicadores`; README, indicadores de Suprimentos. O botão Análise do período chega na ISSUE-081.

## Registro de execução

Fatia entregue em 09/10/2026: a fachada do painel (`list_panel`: os nove indicadores, as três curvas acumuladas, a distribuição por etapa e a tabela dos pedidos por folga, sobre o plano, o mapa, os processos, os pedidos e os contratos), as rotas (`painel`, `painel/excel` e `painel/imprimivel`), a tela (trio preenchido com o DS: KPIs, os quatro visuais da biblioteca, a tabela e as exportações), o Excel e o PDF A4 pelos mecanismos genéricos, a migração `m050` (os agregados comerciais do processo no pacote, para a carga histórica), a parte `suprimentos-painel` da carga (fecha o vínculo dos contratos com os pacotes e carrega os agregados) e os testes (cálculos, fachada, rotas e o oráculo da carga com 92,9% de aderência, 5,2% e 4,7% de saving e 90,9% x 97,3%, índice 0,93). O oráculo do Financeiro da carga passou a afirmar o vínculo do contrato CT-2026-011 com o PC-01, que a parte nova fecha.

- DECISAO: agregados comerciais do pacote | a primeira proposta vencedora, as propostas válidas e o fornecedor único ganham as colunas `primeira_proposta_centavos`, `propostas_validas` e `fornecedor_unico` (m050) para a carga histórica; o painel prefere o processo vivo quando existe | D5b, ISSUE-063
- DECISAO: valor adjudicado do serviço | o MAS e o painel leem o contrato nascido do pacote (`financeiro.purchase_contracts_by_package`, D9) depois do pedido e da recomendação; a parte do painel liga os contratos do mock ao pacote | D9, ISSUE-063
- DECISAO: curva do avanço | a curva do painel usa a mesma regra do avanço do MAS (o peso dos marcos não aplicáveis fica fora do total), o que difere do protótipo nos serviços | D6, ISSUE-063
- DECISAO: pacotes por etapa | o visual é a faixa `kpi-status` da biblioteca (D11); a etapa de um pacote com processo é a da última ação registrada, como na tela de processos | D11, ISSUE-063
- DECISAO: metas do painel | as metas de aderência e de OTD são parâmetros do grupo `suprimentos` (`metaAderenciaPct` e `metaOtdPct`, 90 e 90 nos iniciais), validados de 0 a 100%, nunca no código | D6, ISSUE-063
- DECISAO: exportações | Excel com as abas Resumo (KPIs) e Pedidos por folga; PDF A4 paisagem com os KPIs, os quatro gráficos e a tabela, pelos mecanismos genéricos | D12, ISSUE-063
