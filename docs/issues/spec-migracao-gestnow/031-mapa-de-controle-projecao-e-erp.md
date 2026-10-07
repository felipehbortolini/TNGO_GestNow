---
id: ISSUE-031
title: "Mapa de controle com projeção, mapa de calor e custos do ERP"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 4
onda: 7
blocked_by:
  - ISSUE-030
blocks:
  - ISSUE-032
  - ISSUE-041
  - ISSUE-043
  - ISSUE-058
labels:
  - ready-for-agent
source_requirements:
  - HU-089
  - HU-090
spec_decisions:
  - D11
  - D1
---

# Mapa de controle com projeção, mapa de calor e custos do ERP

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D11, D1.
> Entrega 4 (Custo e avanço físico), onda 7 (03 Financeiro, base de custo).
> Histórias: 89, 90. Bloqueada por: ISSUE-030.

## O que construir

A tela **Mapa de controle** mostra, item a item, com subtotal por pacote e a
linha do projeto, em R$ mil (exportação em reais, valor integral): Orçado
(linha de base), Remanejamentos, Orçado atual, Comprometido, Realizado, Saldo a
comprometer, Projeção no término e Desvio (R$ e %), com mapa de calor no desvio
pelas faixas dos parâmetros, no visual Tabela Heatmap. Sobrecusto usa a família
`erro` e economia a família `ok`, com sinal e ícone além da cor (a exceção E1
deixa de existir, D1).

Fórmulas: Orçado atual = Orçado + Remanejamentos; Saldo a comprometer = Orçado
atual − Comprometido; Desvio = Projeção no término − Orçado atual (positivo é
sobrecusto).

**Atualizar projeção** por item exige justificativa e guarda histórico. A
**importação dos custos do ERP** no fechamento do mês (comprometido, realizado
e projeção, por item e mês) usa o fluxo genérico de importação; os custos ficam
como fatos por mês, base da Curva S financeira e do valor agregado.

## Critérios de aceite

- [ ] As três fórmulas têm teste, e o desvio positivo é sobrecusto.
- [ ] As faixas do mapa de calor seguem os parâmetros vigentes e mudam na hora quando o parâmetro muda.
- [ ] Projeção sem justificativa é recusada; com justificativa, entra no histórico.
- [ ] A importação do ERP grava por item e mês só na confirmação.
- [ ] O oráculo afirma a projeção no término de R$ 45,26 mi.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo (fórmulas e faixas), de fachada (projeção e importação) e o
oráculo da projeção.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `mapa-controle.html`, `GI.api.financeiro.mapaControle`,
`atualizarProjecao` e `importarCustos`; README, seção 2.7 (faixas). A faixa
"Reservas" do mapa entra na ISSUE-041.

## Registro de execução

- Data: 2026-10-06.
- Feito: os cálculos puros (as três fórmulas do mapa, o desvio percentual, a faixa do desvio, a payload `deviation_heatmap_faixas` do visual Tabela Heatmap, a projeção vigente entre o histórico manual e o do ERP e os totais do ERP até o corte), o serviço (`service.update_projection` com histórico e justificativa, `service.import_erp_costs` por item e mês e `service.mapa_controle` no projeto e na carteira), as rotas do mapa, da projeção e da importação dos custos do ERP, o importador `custos-erp`, os fragmentos (KPIs, grade no visual Tabela Heatmap com a tabela servidora em reais integrais dentro, formulário da projeção e modal da importação em dois passos), os exports em reais integrais com a coluna Projeto na carteira, a tela completa (view, estilo e comportamento do trio `financeiro/mapa_controle`, com a célula do desvio abrindo a projeção e o modal genérico da importação), a carga de demonstração `financeiro-custos` e o oráculo da projeção em R$ 45,26 mi.
- Decisão de execução: a grade visível nasce do visual Tabela Heatmap (`data-grafico`/`data-dados`, D11), em R$ mil, com o desvio percentual pintado pelas faixas dos parâmetros vigentes (sobrecusto `erro`, economia `ok`, com sinal e ícone); a tabela servidora em reais integrais vai dentro do elemento do visual — é a versão sem JavaScript e a que os testes de rota leem — e o visual a substitui ao montar. Com escrita, a célula pintada do item carrega o id que abre o formulário da projeção; sem escrita (Portfólio ou Visualizador) não há célula interativa.
- Porta de qualidade (`npm run verificar`) e a suíte completa de pytest (1.895 testes) passaram em 06/10/2026.
