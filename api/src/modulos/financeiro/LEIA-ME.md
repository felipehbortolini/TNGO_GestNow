# Financeiro

Módulo `financeiro`. Mantém a Estrutura Analítica de Custos, o desempenho de custo, desembolso, reservas e administração de contratos. Valores persistidos são centavos inteiros; a formatação acontece na saída.

## Telas previstas

| Tela | Conteúdo | Issue |
|---|---|---|
| EAC | Árvore de custo, itens, revisões, remanejamentos e importação | ISSUE-029, ISSUE-030 |
| Mapa de controle | Orçado, comprometido, realizado, saldo, projeção e desvio | ISSUE-031 |
| Cronograma de desembolso | Saldo futuro por item/mês, previsto e realizado | ISSUE-043 |
| KPIs de custo e Curva S financeira | Índices de custo, valor agregado e séries | ISSUE-042 |
| Contingência | Reservas, consumo, liberações, exposição e cobertura | ISSUE-041 |
| Contratos e ficha do contrato | Medições, aditivos, marcos, claims, EOT e avaliações | ISSUE-032 a ISSUE-035 |

## Trios das telas

Cada tela da lista de navegação (`api/src/core/navegacao.json`) tem um trio com o mesmo nome: a view, o estilo e o comportamento da página. O CSS é escopado pela classe raiz da view (`.pagina--<modulo>-<tela>`, com o `_` do identificador mantido), o JS registra `TN.paginas["<modulo>/<tela>"]` e o shell (`app/index.html`) vincula o CSS e o JS de todos. A verificação `trio-da-tela` confere o conjunto. Convenção completa em `docs/PADROES-DE-PAGINA.md`, seção "O trio da tela".

| Tela | View | CSS | JS |
|---|---|---|---|
| EAC | `app/_views/financeiro/eac.html` | `app/paginas/financeiro/eac.css` | `app/paginas/financeiro/eac.js` |
| Mapa de controle | `app/_views/financeiro/mapa_controle.html` | `app/paginas/financeiro/mapa_controle.css` | `app/paginas/financeiro/mapa_controle.js` |
| Cronograma de desembolso | `app/_views/financeiro/desembolso.html` | `app/paginas/financeiro/desembolso.css` | `app/paginas/financeiro/desembolso.js` |
| KPIs de custo | `app/_views/financeiro/kpis.html` | `app/paginas/financeiro/kpis.css` | `app/paginas/financeiro/kpis.js` |
| Curva S financeira | `app/_views/financeiro/curva_s.html` | `app/paginas/financeiro/curva_s.css` | `app/paginas/financeiro/curva_s.js` |
| Contingência | `app/_views/financeiro/contingencia.html` | `app/paginas/financeiro/contingencia.css` | `app/paginas/financeiro/contingencia.js` |
| Contratos | `app/_views/financeiro/contratos.html` | `app/paginas/financeiro/contratos.css` | `app/paginas/financeiro/contratos.js` |
| Contrato | `app/_views/financeiro/contrato.html` | `app/paginas/financeiro/contrato.css` | `app/paginas/financeiro/contrato.js` |

## Rotas previstas

Prefixo: `/api/financeiro/`.

| Grupo previsto | Uso | Issue |
|---|---|---|
| `eac` e `eac/revisoes` | Consultar itens, importar e aplicar revisão aprovada | ISSUE-029, ISSUE-030 |
| `mapa-de-controle` e `custos` | Consultar mapa, importar ERP e atualizar projeções com justificativa | ISSUE-031 |
| `kpis` e `curva-s` | Consultar indicadores, valor agregado e série financeira | ISSUE-042 |
| `contingencia` | Consultar reservas e seus movimentos | ISSUE-041 |
| `desembolso` | Consultar e exportar previsão de caixa | ISSUE-043 |
| `contratos` e `contratos/{codigo}` | Lista, ficha e eventos do contrato | ISSUE-032 a ISSUE-035 |

Os grupos são planejamento; cada issue fixa métodos e paths concretos conforme D14.

## O que a ISSUE-029 trouxe

* **Tela EAC** (`financeiro/eac`): árvore (linha 0 do projeto, pacote, subpacote, item) com recolher e expandir, filtros de busca, nível e tipo de custo, KPIs e total filtrado. Totais de pacote e subpacote somados no servidor, em centavos. No Portfólio a árvore é somente leitura: linha 0 = portfólio, nível 1 = projeto ("código · nome"), nível 2 = pacotes principais, com a coluna de peso na carteira.
* **Rotas** (`routes.py`): `GET /api/financeiro/eac` (conteúdo), `GET /eac/itens/{id}/editar` (formulário cadastral com histórico), `POST /eac/itens/{id}` (grava), `GET /eac/excel` e `GET /eac/imprimivel` (mesmo conteúdo e filtros da tela; no Portfólio com a coluna Projeto).
* **Edição cadastral**: descrição, tipo de custo, classificação CAPEX/OPEX, centro de custo e responsável. Não muda valor, dispensa SM, exige justificativa e fica no histórico do item (`service.edit_item_registry`, `service.item_history`); controle de versão com 409.
* **Ponderação da carteira**: `service.portfolio_weights` lê o orçamento vigente da EAC e as notas dos projetos e aplica `calculations.portfolio_weights` (critérios normalizados) fechado em 100,00 por `calculations.largest_remainder`. A edição da ponderação é da ISSUE-080.
* **Carga e oráculo**: `seed.py` grava a EAC dos mocks; `tests/financeiro/test_eac_oraculo.py` afirma BAC de R$ 44,6 mi no projeto 1 e pesos 55,36 / 29,34 / 15,30.

## O que a ISSUE-030 trouxe

* **Toda alteração de valor passa pela SM.** Remanejamento entre itens e item novo com recurso de outro item abrem uma SM do tipo "Remanejamento de orçamento" (`service.reallocate`); até a decisão o valor fica reservado na origem e aparece em "Remanejamentos" como pendente. A aprovação aplica as transferências na EAC, na mesma transação da decisão, conferindo o saldo livre de novo (`service.apply_reallocations`); a rejeição libera a reserva. O item novo nasce na abertura da SM com base zero e recebe o valor na aprovação.
* **Acréscimo ao total só por revisão** a partir de SM aprovada com custo (papel Gestor): `service.create_revision` exige a SM, confere o custo aprovado, consolida os remanejamentos aplicados e congela a linha de base de todos os itens de nível 3 em `eac_revisao_item`. Rev 0 é a linha de base; `mudanca.eac_revisao_incorporada` guarda a revisão que incorporou o custo da SM e o encerramento da SM é recusado enquanto ela não existir.
* **Painéis e rotas** (`routes.py`): `GET /eac/revisoes` e `GET /eac/remanejamentos` leem as tabelas (no Portfólio, com o projeto em cada linha); `POST /eac/remanejamentos` abre a SM, `POST /eac/revisoes` cria a revisão e `POST /eac/itens` cria o item novo (por remanejamento ou revisão). O erro volta no próprio painel, com 422 e a mensagem.
* **Importação de itens por planilha**: o importador `eac-itens` (`importers.py`) confere linha a linha contra a EAC (código de três níveis, subpacote existente, código livre, unidade e responsável no cadastro); a confirmação da tela (`POST /eac/revisoes/importar/conferir` e `.../confirmar`) checa de novo e cria a revisão vinculada à SM com os itens novos. A confirmação genérica recusa a linha: item da EAC não entra sem revisão.
* **Exportação**: o Excel e a versão imprimível da tela levam as tabelas "Revisões do orçamento" e "Remanejamentos" no mesmo documento da árvore.
* **Carga e oráculo**: a parte `governanca-eac` (`governanca/seed.py`) grava as transferências do protótipo em `mudanca_remanejamento` e chama `financeiro/seed.py::load_revisions`, que grava as revisões com a linha de base congelada e os remanejamentos aplicados apontando para a próxima revisão; `tests/financeiro/test_eac_revisoes_oraculo.py` confere os números do mock.

## Fórmulas e nomes no código

| Termo de negócio | Definição | Nome previsto |
|---|---|---|
| Valor orçado do item | Quantidade x preço unitário, em centavos | `calculations.budgeted_cents` |
| Orçado atual do item | Linha de base da última revisão mais os remanejamentos aplicados e ainda não consolidados | `calculations.current_base_cents` |
| Saldo livre do item | Orçado atual menos comprometido menos o reservado em outras SMs abertas | `calculations.free_balance_cents` |
| Variação da revisão | Total da revisão menos o total da revisão anterior do projeto | `service.revision_rows` |
| Total de pacote e subpacote | Soma dos itens abaixo, no servidor | `calculations.item_totals` |
| Árvore do projeto e da carteira | Linha 0, pacotes, subpacotes e itens; carteira em três níveis | `calculations.build_project_tree`, `calculations.build_portfolio_tree` |
| Maior resto | Fecha os pesos em 100,00 (duas casas) | `calculations.largest_remainder` |
| Peso do projeto na carteira | Soma dos critérios normalizados (valor financeiro, criticidade estratégica, complexidade, exposição a risco) | `calculations.portfolio_weights` |
| CPI | Valor agregado dividido pelo custo real (`EV / AC`) | `calculations.cost_performance_index` |
| SPI de custo | Valor agregado dividido pelo valor planejado (`EV / PV`) | `calculations.cost_schedule_index` |
| VAC | Orçamento no término menos Projeção no término | `calculations.variance_at_completion` |
| Desvio da projeção | Projeção no término menos orçado atual; positivo significa sobrecusto | `calculations.projected_cost_variance` |
| Saldo a pagar | Projeção no término menos realizado, distribuído pelos períodos futuros conforme o perfil previsto | `calculations.remaining_cash_flow` |
| Tendência financeira do relatório | `AC + (BAC - EV) / CPI` no corte do relatório, distribuída pelo perfil planejado e sem dados posteriores ao corte | `calculations.financial_eac_trend` |

`EAC` neste produto significa sempre Estrutura Analítica de Custos. O indicador *Estimate at Completion* é chamado **Projeção no término**. A tendência estatística por CPI do relatório é distinta da projeção bottom-up da equipe.

## Fluxos

Revisões da EAC, itens novos financiados e remanejamentos passam por SM aprovada; a aprovação aplica a mudança. A importação de itens por planilha passa pela conferência e gera uma revisão vinculada à SM aprovada. Medições contratuais avançam Em análise → Aprovada → Faturada → Paga ou Devolvida com motivo. Claims e EOT seguem os ciclos documentados no inventário do protótipo. Consumo ou liberação de reservas exige SM aprovada.

## Integrações

Suprimentos compromete custo quando emite pedido/contrato. Governança fornece SMs aprovadas e a alçada/comitê para remanejamentos e reservas. Contratos alimentam comprometido/realizado e desembolso. Riscos fornece VME para cobertura; Financeiro entrega KPIs à carteira e ao relatório. A comunicação entre módulos passa pelas fachadas donas.

## Parâmetros

Incluem faixas do mapa de calor (1%, 5%, 10% inicialmente), tolerância de consumo da contingência, cobertura mínima de exposição e critérios financeiros de gestão. São versionados em Configurações; o escopo detalhado entra nas ISSUE-041 a ISSUE-043 e ISSUE-076.

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas | `routes.py` |
| Fluxo, permissões e integrações | `service.py` |
| Índices, projeções e desvios | `calculations.py` |
| Validações monetárias e de revisão | `validation.py` |
| Excel/imprimível específico | `export.py` |
| Persistência | `models.py`; entidades em `docs/MODELO-DE-DADOS.md` |
| Fragmentos | `api/src/templates/financeiro/` |
| Tela, estilo e comportamento | `app/_views/financeiro/` e `app/paginas/financeiro/` |
| Testes | `api/tests/financeiro/` |

Todos os arquivos Python são stubs intencionais na ISSUE-002. As issues de Financeiro completam este documento e acrescentam testes de fronteira para cada cálculo.
