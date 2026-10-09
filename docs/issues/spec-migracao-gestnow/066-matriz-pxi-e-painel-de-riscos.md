---
id: ISSUE-066
title: "Matriz P x I e painel de riscos"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 6
onda: 13
blocked_by:
  - ISSUE-065
blocks:
  - ISSUE-067
  - ISSUE-076
  - ISSUE-079
  - ISSUE-082
labels:
  - ready-for-agent
source_requirements:
  - HU-026
  - HU-111
  - HU-112
spec_decisions:
  - D6
  - D11
  - D12
---

# Matriz P x I e painel de riscos

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D6, D11, D12.
> Entrega 6 (Suprimentos e Riscos), onda 13 (05 Riscos).
> Histórias: 26, 111, 112. Bloqueada por: ISSUE-065.

## O que construir

A **Matriz P x I** mostra o mapa 5x5 inerente e residual com contagem, fórmula
e números por célula (a célula leva ao registro filtrado; vazia fica
esmaecida), a natureza (oportunidades com a escala invertida em verde), a
legenda pelas faixas da escala ativa e a movimentação de inerente para
residual com barras sobrepostas e o destaque de "sem redução".

O **Painel** mostra os KPIs (faixa mais alta, segunda faixa, exposição VME,
revisão vencida, redução média), a exposição por categoria da RBS (barras que
abrem o registro filtrado), a **evolução mensal do score residual das ameaças
reconstruída do histórico** de avaliações e revisões (sem série gravada) e a
**pauta de escalonamento** (acima do alvo a 30 dias ou menos do prazo do alvo,
sem redução após o plano, plano aguardando aprovação, revisão vencida, gatilho
ocorrido, identificado sem avaliação ou faixa mais alta sem plano), com envio
ao gerente do projeto pela porta de notificação.

## Critérios de aceite

- [ ] As contagens da matriz batem com o registro, e a célula leva ao registro filtrado.
- [ ] A evolução mensal é reconstruída do histórico (teste com histórico conhecido).
- [ ] Cada regra da pauta tem teste com a data injetada.
- [ ] O envio da pauta fica na trilha com o aviso "simulado".
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo (matriz, evolução e pauta) e de fachada (envio).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `matriz.html` e `painel.html` de Riscos, `GI.api.riscos.matriz` e `painel`. A série mensal gravada no mock deixa de ser fonte (D6).

## Registro de execução

Fatia entregue em 09/10/2026: a fachada da matriz e do painel (`panel_service`: as células 5×5 com a legenda das faixas e a movimentação inerente→residual; os cinco KPIs, a exposição por categoria da RBS, a evolução mensal reconstruída do histórico e a pauta com o envio pela porta de notificação), as rotas e os fragmentos (`panel_routes`, `riscos/matriz.html`, `riscos/painel.html` e o modal do envio), os trios das duas telas com os visuais da biblioteca (matriz-formatada grade e linhas-múltiplas), o Excel e o PDF pelos mecanismos genéricos, e os testes (cálculos com a data injetada, fachada com o envio simulado, rotas e o oráculo da evolução). Sem migração: matriz e painel são leitura calculada e o gatilho já vive na `risco_revisao`. As integrações que chegam de fora ficam na ISSUE-067.

- DECISAO: filtro da célula | a célula usa `celula=p3|i4` (o parâmetro do exemplo do styleguide), que `parse_filters` traduz para probabilidade, impacto e tipo de avaliação; o link leva ao Registro filtrado | D11, ISSUE-066
- DECISAO: evolução mensal | reconstruída das avaliações e revisões (D6): por mês, a soma do evento mais recente de cada ameaça ativa ao fim do mês, com o corte na data de referência | D6, ISSUE-066
- DECISAO: visual da evolução | Linhas Múltiplas com `suavizar: false`, porque não há barras de uma série só por mês na biblioteca | D11, ISSUE-066
- DECISAO: envio da pauta | pela porta de notificação (tipo `pauta_riscos`), destinatário o gerente do projeto no cadastro; no Portfólio a tela pede o projeto antes do modal; simulado na trilha enquanto o envio real está desligado | ISSUE-013, D8/D12, ISSUE-066
- DECISAO: KPI de exposição | sem o "Limite" do protótipo, que vinha da cobertura da contingência e chega com a integração da ISSUE-067; no lugar entra "Ameaças ativas" | ISSUE-067, ISSUE-066
