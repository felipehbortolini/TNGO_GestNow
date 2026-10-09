---
id: ISSUE-061
title: "Diligenciamento e recebimento"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 6
onda: 12
blocked_by:
  - ISSUE-060
blocks:
  - ISSUE-062
  - ISSUE-067
  - ISSUE-069
labels:
  - ready-for-agent
source_requirements:
  - HU-103
spec_decisions:
  - D9
  - D5a
---

# Diligenciamento e recebimento

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D9, D5a.
> Entrega 6 (Suprimentos e Riscos), onda 12 (04 Suprimentos).
> Histórias: 103. Bloqueada por: ISSUE-060.

## O que construir

A tela **Diligenciamento e recebimento** lista os pedidos com o próximo marco,
data contratual, previsão, ROS, folga e situação, e o bloco de pedidos
críticos com tratamento pendente. A **ficha do pedido** mostra os 6 marcos de
fabricação (linha de base contratual, previsão, realizado, desvio), o
recebimento, a ação e o risco vinculados e as últimas atualizações.

**Atualizar marco**: realização exige o marco anterior realizado e data até a
referência; previsão não fica no passado; reprogramação pode deslocar os marcos
seguintes na mesma quantidade de dias. **Registrar recebimento** exige o
embarque realizado antes e registra conferência, avarias com descrição,
pendências e anexos. **Importação do ERP**, uma linha por marco.

Folga negativa cria, sem duplicar, a ação na Central (origem Suprimentos,
grupo Diligenciamento, responsável o comprador, prazo de 7 dias). O OTD dos
pedidos passa a alimentar o desempenho do fornecedor (ISSUE-057). O risco
sugerido é ligado na ISSUE-067, e o FAT no 06, na ISSUE-069.

## Critérios de aceite

- [ ] As regras de realização, previsão e reprogramação são recusadas com a mensagem quando violadas.
- [ ] O recebimento sem embarque realizado é recusado.
- [ ] Folga negativa cria uma única ação na Central, mesmo com várias atualizações.
- [ ] O desempenho do fornecedor passa a mostrar o OTD.
- [ ] O oráculo afirma 3 pedidos críticos (folgas −20, −9 e −5) e OTD de 66,7%.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (marcos, recebimento, importação e ação sem duplicar) e o oráculo.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `diligenciamento.html`, `GI.api.suprimentos.pedidos`, `atualizarMarco`, `registrarRecebimento`, `gerarAcao` e `importarPedidos`.

## Registro de execução

Entregues: a fachada do diligenciamento (leitura com situação dos marcos, folga do ROS, atraso contratual e OTD; atualização de marco com cascata; recebimento com anexo de verdade; importação do ERP; ação na Central sem duplicar; OTD no desempenho do fornecedor), a migração `m049_recebimento` (down `m048`), as rotas da tela, dos dois modais e da ação, o trio da tela com os fragmentos, a parte `suprimentos-diligenciamento` da carga, os testes de cálculos, fachada, rotas e o oráculo (3 críticos −20/−9/−5 e OTD 66,7% no projeto; o quarto crítico do Portfólio é a caldeira), e a documentação (LEIA-ME, DIVERGENCIAS, este registro). `ruff format` e `ruff check` limpos nos arquivos tocados.

- DECISAO: FAT | o resultado da inspeção em fábrica e o registro no 06 ficam para a ISSUE-069; a realização do marco grava só a data | D5a, ISSUE-061
- DECISAO: evidência da atualização do marco | o modal não coleta anexo (a trilha não é registro de anexo); a evidência de entrega é o anexo do recebimento | D5a, ISSUE-061
- DECISAO: anexo do recebimento | um arquivo por gravação no formulário; o registro aceita mais anexos pela porta genérica de anexos | D5a, ISSUE-061
- DECISAO: importação do ERP | a linha repetida do mesmo pedido e marco é recusada pela unicidade do importador genérico | D12, ISSUE-061
- DECISAO: risco sugerido | o vínculo com o registro de riscos fica para a ISSUE-067; a ficha do pedido mostra "sem risco registrado (ISSUE-067)" | D9, ISSUE-061
- DECISAO: folga do ROS e OTD | `calculations.required_on_site_slack` (a mesma fórmula do `delivery_slack_days`) e `calculations.on_time_delivery` (uma casa, meio para cima) | D6, ISSUE-061
- DECISAO: ficha do pedido | a ficha vive no fragmento da tela; o clique numa linha pede a tela de novo com `pedido`, sem rota de ficha separada | D14, ISSUE-061
- DECISAO: ação sem duplicar | a existência de ação aberta é perguntada à Central (`count_actions_of_origin`), nunca lida da tabela `acao` | D5, ISSUE-061
