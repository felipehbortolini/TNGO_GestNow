---
id: ISSUE-036
title: "EAP em árvore com dicionário, avanço calculado pelo critério e visão carteira"
status: done
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

- [x] A regra dos 100% vale, e o peso de cada nível é a soma dos filhos.
- [x] O real de cada pacote é calculado pelo critério, com um teste por critério.
- [x] O desvio usa as faixas dos parâmetros.
- [x] A demonstração traz 38 pacotes, a Rev 2 vigente, o desdobramento 5.2.1 > 5.2.2 e os dois pacotes com término vencido.
- [x] No Portfólio, a árvore é somente leitura.
- [x] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [x] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [x] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [x] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo (avanço por critério e somas ponderadas) e conferência do cenário da demonstração.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `eap.html`, `GI.api.planejamento.eap`, `GI.regras.avancoPacoteEap`,
`mock-planejamento`; README, "EAP: regras".

## Registro de execução

- Data: 2026-10-07.
- Feito: as etapas 1 a 3 (commits `38a7a08`, `a55de31`, `118b91f`) entregaram a migração `m036_eap_arvore_e_dicionario`, o cálculo do avanço por critério (com um teste por critério), os parâmetros da EAP (faixas `faixasDesvioPP` −2 e −5 p.p., pesos máximos e modelos de etapas), a fachada (`service.eap_overview` com a carteira somente leitura, o dicionário, as revisões e os desdobramentos), as rotas `/api/planejamento/eap` (tela, dicionário de resposta multi-alvo, Excel e imprimível), o documento de exportação e a carga de demonstração. Nesta etapa de fechamento, a tela `planejamento/eap` trocou o esqueleto pela tela real: KPIs, árvore com recuo e recolhimento e as colunas do protótipo (peso, previsto, real com barra, desvio em p.p. com a faixa, datas, critério e situação), tabelas de Revisões e Desdobramentos, dicionário no alvo `eap-formulario` com o histórico de medições e botões Excel/PDF; o comportamento carrega o fragmento no boot, mapeia os estados pelo marcador `data-situacao`, recolhe e expande a árvore, mantém 422 e 409 no lugar (o conteúdo e o formulário vêm na resposta) e trata 403 como sem-permissão; o estilo escopado cobre o recolhimento, o recuo, a barra do real, a linha da revisão vigente e o histórico de medições; o `LEIA-ME.md` do módulo recebeu a seção "EAP (ISSUE-036)".
- Ajuste mínimo em arquivos da fatia: `_eap_arvore.html` ganhou o botão de recolhimento (`linha.has_children`, calculado por `routes._has_children` pelo prefixo do código) e a barra do real (`linha.real_num`); `_eap_dicionario_campos.html` ganhou a lista de Medições (`routes._measurement_lines`, da mais nova para a mais antiga, com o estorno marcado); as linhas de KPI trocaram os ícones `trendingUp`, `listTree`, `flag` e `fileText`, que não existem em `ds/icons.js`, por `chartLine`, `layers`, `warning` e `file` (o ícone da ação do dicionário virou `file`).
- Divergência 37×38 do mock: o mock conta 35 pacotes na Rev 0 e 37 na Rev 2 do projeto 1, enquanto a EAP corrente tem 38 pacotes, porque o mock não guarda o histórico de pesos; a revisão congela o peso corrente de cada pacote (D5b) e a contagem sai dos pesos congelados, como registra `seed.py`. A EAP vigente fica com os 38 do critério.
- Divergências do protótipo: os filtros da barra (busca, nível, critério e situação) não entram nesta fatia — a árvore vem inteira do servidor e o recolhimento é local; não há botões de inclusão nem de importação (revisão e desdobramento são da ISSUE-038), então não há formulário que peça o projeto no Portfólio; a barra do real é a da página (trilho + valor), sem o componente `progress` do protótipo; o dicionário usa a resposta multi-alvo `eap-conteudo` + `eap-formulario` em vez do modal do protótipo.
- Fica para a ISSUE-037: o registro de medições com estorno e a importação do avanço (a tela desta fatia só lê o histórico). Fica para a ISSUE-038: a nova revisão da EAP e o desdobramento de pacotes de planejamento pela tela, com o efeito nos pesos.
- Porta de qualidade (`node scripts/verificar.mjs`, cinco etapas) verde e a suíte completa de pytest (2.290 testes, 0 falhas, 0 erros) passou em 07/10/2026.
