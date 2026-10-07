---
id: ISSUE-035
title: "Contratos: visão consolidada e indicadores da administração contratual"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 4
onda: 7
blocked_by:
  - ISSUE-033
  - ISSUE-034
blocks:
  - ISSUE-079
labels:
  - ready-for-agent
source_requirements:
  - HU-098
spec_decisions:
  - D11
---

# Contratos: visão consolidada e indicadores da administração contratual

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D11.
> Entrega 4 (Custo e avanço físico), onda 7 (03 Financeiro, base de custo).
> Histórias: 98. Bloqueada por: ISSUE-033, ISSUE-034.

## O que construir

A tela **Contratos: registros** mostra, em abas, Contratos, Claims, Extensões
de prazo, Marcos de pagamento e Avaliações de todos os contratos do escopo, com
filtros e exportação; os registros novos nascem na ficha.

Os KPIs da administração contratual seguem a tabela do protótipo: exposição de
claims por direção, taxa de reconhecimento, tempo médio de resolução,
notificações fora do prazo, extensão de prazo acumulada, dias solicitados x
concedidos, marcos atrasados, aprovado não faturado, pago x previsto e
desempenho das contratadas (nota média, classe, tendência e número de
contratadas C ou D).

## Critérios de aceite

- [x] Cada um dos dez indicadores tem teste da fórmula.
- [x] As abas filtram e exportam no escopo escolhido.
- [x] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [x] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo dos indicadores com a data injetada.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `contratos.html`, `GI.api.financeiro.resumoContratos` e `consolidadoContratos`.

## Registro de execução

- Data: 2026-10-07.
- Feito: os dez indicadores da administração contratual como funções puras com a data injetada (`calculations.contracts_summary` e `calculations.contract_indicators`), a leitura do escopo (`service.contracts_overview`, com as linhas das cinco abas e os fatos), o fragmento consolidado com os seis cartões e as cinco abas (`contratos_consolidado.html`, `_contratos_kpis.html`, `_contratos_tabelas.html`), as rotas `GET /api/financeiro/contratos/consolidado`, `.../excel` e `.../imprimivel`, com os filtros `busca` e `contrato` (e as partes `contratos-kpis contratos-tabelas` quando o formulário de filtros pede) e o documento do Excel/imprimível (`export.contratos_consolidado_document`); nesta etapa de fechamento, a tela `financeiro/contratos` trocou o esqueleto pela visão real (view com os alvos `contratos-conteudo`, `contratos-kpis` e `contratos-tabelas`; comportamento que carrega o fragmento no boot, sincroniza os botões Excel/PDF com os filtros e trata os estados; estilo escopado para as abas com contador, a barra de filtros e os cartões) e o `LEIA-ME.md` do módulo recebeu a seção desta fatia com os dez indicadores e os nomes no código.
- Nota do protótipo: a tela **não tem botões de inclusão**. O contrato nasce na adjudicação de Suprimentos e os registros das cinco abas nascem na ficha do contrato (ISSUE-032 a ISSUE-034); a visão consolidada só lê, filtra e exporta. A coluna **Projeto** entra quando o escopo é o Portfólio: `view.is_portfolio` vira `carteira` no contexto e cada tabela (e o Excel e o imprimível) abre com a coluna Projeto pelo `project_label` do registro.
- Decisão de execução: o fragmento inteiro carrega no alvo `contratos-conteudo`; o formulário de filtros vive dentro dele e pede só `contratos-kpis` e `contratos-tabelas`, então o campo de busca fica fora dos blocos substituídos e não perde o foco; a troca de aba é estado local do Alpine no próprio fragmento e os cartões falam do escopo inteiro, nunca do filtro.
- Ajuste mínimo em arquivos da própria fatia: nenhum no backend nesta etapa; a tela lê o vazio de origem do próprio fragmento (o cartão `data-estado="vazio-origem"` de `_contratos_tabelas.html`) para escolher entre conteúdo e vazio.
- Divergências do protótipo: a coluna Medido mostra o percentual medido (`calculations.contract_measured_percent`) sem a barra de progresso do protótipo; o filtro de contrato é uma seleção resolvida no servidor e a exportação leva os filtros da tela pela URL, enquanto no protótipo os botões exportavam o que estava filtrado na memória; a tela não usa o marcador `data-resultado` das irmãs (EAC, Mapa de controle), porque o fragmento desta fatia já marca o vazio de origem com `data-estado`.
- Porta de qualidade (`npm run verificar`) e a suíte completa de pytest (2.235 testes) passaram em 07/10/2026.
