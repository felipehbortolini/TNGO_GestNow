---
id: ISSUE-086
title: "Relatório: Excel, Imprimir / PDF e Alterar período"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 8
onda: 17
blocked_by:
  - ISSUE-085
blocks:
  - ISSUE-087
labels:
  - ready-for-agent
source_requirements:
  - HU-039
spec_decisions:
  - D12
---

# Relatório: Excel, Imprimir / PDF e Alterar período

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D12.
> Entrega 8 (Visão executiva), onda 17 (Início, análise do período e relatório gerencial).
> Histórias: 39. Bloqueada por: ISSUE-085.

## O que construir

A view do relatório ganha os botões **Imprimir / PDF** (impressão do navegador
com as folhas A4), **Excel** (indicadores e tabelas de todas as folhas, mais as
abas "Análises do período" e "Desvios negativos e comentários") e **Alterar
período** (volta ao modal com as escolhas atuais).

## Critérios de aceite

- [ ] O Excel tem uma aba por folha e as abas de análises e de desvios com comentários.
- [ ] Imprimir sai uma folha por página, sem navegação, com os fundos preservados.
- [ ] Alterar período reabre o modal com as escolhas atuais.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Teste que abre o Excel do relatório com openpyxl e confere as abas; teste da versão imprimível.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: README, "Relatório gerencial" (Impressão e Excel).

## Registro de execução

Fatia entregue em 11/10/2026: o **Excel** do relatório, o **Alterar período** e o fecho do
contrato de **impressão**. O `export.py` deixou de ser stub: `build_document(*, sheets, today)`
monta o documento da porta canônica (D12) — a aba **Resumo** com os indicadores de todas as
folhas presentes prefixados pela folha (valores crus tipados, referência de gestão e tom), **uma
aba por tabela exibida** (Projetos da carteira com o rodapé do total, Critérios de ponderação,
Avanço por área/projeto, Relatos dos projetos, Atividades do período e do próximo no projeto,
Pontos de atenção e riscos, Valor agregado mês a mês, EAC por pacote/projeto com total, Pedidos
críticos, Realizado no período, Previsto nas próximas 4 semanas ou no próximo mês, Principais
riscos, Inspeções reprovadas, Pauta de tratamento) e as duas abas de fechamento do protótipo:
**Análises do período** (módulo, tipo, período, texto ou "Não registrada", e a atualização em
dd/mm/aaaa · quem) e **Desvios negativos e comentários** (o comentário gravado ou "Comentário
pendente" nos obrigatórios e "Sem comentário" nos demais). Dinheiro em centavos vira reais
inteiros (D12), percentual em pontos, datas como datas; `per_project=False` porque as linhas já
trazem o código do projeto onde a folha mistura projetos. A rota `gerencial/excel` é de arquivo
(`file_route`, sem o gate do Alpine), espelha o `report_screen` (tipo, período e seções da URL;
corte e referência do relógio) e devolve o `excel_response`; a recusa sai em texto simples com o
status. A função nasceu `report_excel` e **colidiu com a rota homônima do Planejamento**: o
registro do app falhava e cinco testes da plataforma davam erro na suíte completa — virou
**`report_sheets_excel`**, porque nome de função de rota é único no app. Na barra das folhas
entraram **Excel** (`data-tn-excel` com tipo, período e seções no endereço; o download pela
porta do DS) e **Alterar período** (`data-relatorio-alterar` → `abrirModal()`, que já reabre o
modal com as escolhas atuais); a barra virou flex com `.rel-barra__acoes`. A **impressão** ficou
como está — a do navegador, pela tela (decisão da ISSUE-083): a linha `gerencial/impressao` saiu
do LEIA-ME e o contrato (o botão, a página nomeada, uma folha por página e os fundos preservados)
ganhou teste que lê a view, o fragmento e o CSS. O LEIA-ME ganhou a seção "Excel do relatório
(ISSUE-086)". **Divergências registradas** na tabela e no histórico: o Excel tipado contra o
texto do protótipo, a aba Resumo no lugar das abas "X (indicadores)" e da aba "Sobre", as
atividades do relato como abas de uma coluna e o "Sem comentário" dos desvios não obrigatórios
(comportamento da tela desde a 083). **Testes**: o novo `test_relatorio_export.py` (Excel do
Portfólio com as abas e os indicadores afirmados pelo openpyxl, a recusa em texto simples e o
contrato da impressão) levou o escopo a 152 (149 + 3); a **suíte completa fechou 4.030 passed +
5 errors** — a colisão de nome —, corrigida e revalidada com **363 passed** (os três arquivos da
plataforma que quebravam e o escopo do relatório); a porta de qualidade passou **5/5** (antes e
depois da correção). O subagente rodou `ruff check`, `ruff format --check` e `ty check` limpos e
o escopo duas vezes; o principal revisou os diffs, rodou a suíte escopada, a completa e a porta.

- DECISAO: Excel pela porta canônica | o documento sai de `export.build_document` (Document/Table/Kpi do core, ISSUE-017) e a rota de arquivo devolve o `.xlsx`; colunas tipadas em vez do texto da tela, com os rótulos e títulos da tela | D12, ISSUE-017, ISSUE-086
- DECISAO: abas | Resumo com os indicadores de todas as folhas prefixados pela folha; uma aba por tabela exibida; "Análises do período" e "Desvios negativos e comentários" no fechamento, como o protótipo; sem aba "Sobre" (o contexto vai no cabeçalho do Resumo) | ISSUE-086
- DECISAO: rota sem gate | `gerencial/excel` é `file_route` (download), a recusa sai em texto simples com o status e o botão é `data-tn-excel` da barra, com tipo, período e seções no endereço | D12, ISSUE-086
- DECISAO: impressão sem rota | a impressão continua a do navegador, pela tela (ISSUE-083); a linha `gerencial/impressao` saiu do LEIA-ME e o contrato ganhou teste | ISSUE-083, ISSUE-086
- DECISAO: Alterar período | o botão da barra reabre o modal pelo mesmo caminho do Emitir relatório, com as escolhas atuais (tipo, período e seções vêm do endereço) | ISSUE-086
- DECISAO: nome único da rota | `report_excel` colidia com a rota homônima do Planejamento e derrubava o registro do app (cinco erros na suíte completa); a função virou `report_sheets_excel` | ISSUE-086
- DECISAO: atividades do relato no Excel | as listas do relato viram abas de uma coluna ("Atividades do período" e "Atividades do próximo período") para nada exibido na folha faltar | ISSUE-086
