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

## Fórmulas e nomes no código

| Termo de negócio | Definição | Nome previsto |
|---|---|---|
| CPI | Valor agregado dividido pelo custo real (`EV / AC`) | `calculations.cost_performance_index` |
| SPI de custo | Valor agregado dividido pelo valor planejado (`EV / PV`) | `calculations.cost_schedule_index` |
| VAC | Orçamento no término menos Projeção no término | `calculations.variance_at_completion` |
| Desvio da projeção | Projeção no término menos orçado atual; positivo significa sobrecusto | `calculations.projected_cost_variance` |
| Saldo a pagar | Projeção no término menos realizado, distribuído pelos períodos futuros conforme o perfil previsto | `calculations.remaining_cash_flow` |
| Tendência financeira do relatório | `AC + (BAC - EV) / CPI` no corte do relatório, distribuída pelo perfil planejado e sem dados posteriores ao corte | `calculations.financial_eac_trend` |

`EAC` neste produto significa sempre Estrutura Analítica de Custos. O indicador *Estimate at Completion* é chamado **Projeção no término**. A tendência estatística por CPI do relatório é distinta da projeção bottom-up da equipe.

## Fluxos

Revisões da EAC, itens novos financiados e remanejamentos passam por SM aprovada; a aprovação aplica a mudança. Medições contratuais avançam Em análise → Aprovada → Faturada → Paga ou Devolvida com motivo. Claims e EOT seguem os ciclos documentados no inventário do protótipo. Consumo ou liberação de reservas exige SM aprovada.

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
| Persistência | `models.py`; entidades nas ISSUE-003 e ISSUE-004 |
| Fragmentos | `api/src/templates/financeiro/` |
| Tela, estilo e comportamento | `app/_views/financeiro/` e `app/paginas/financeiro/` |
| Testes | `api/tests/financeiro/` |

Todos os arquivos Python são stubs intencionais na ISSUE-002. As issues de Financeiro completam este documento e acrescentam testes de fronteira para cada cálculo.
