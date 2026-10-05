# Suprimentos

Módulo `suprimentos`. Planeja compras, conduz concorrências e acompanha aquisição, fabricação e entrega. O Mapa de Suprimentos (MAS) é uma projeção dos registros do módulo, não um cadastro duplicado.

## Telas previstas

| Tela | Conteúdo | Issue |
|---|---|---|
| Painel de suprimentos | Indicadores, curva de contratação, avanço do MAS e pedidos críticos | ISSUE-063 |
| Plano de compras | Pacotes, datas de linha de base, ROS e vínculo à EAC | ISSUE-058 |
| Processos de compra | RFx, equalizações, ranking, alçada e emissão | ISSUE-059, ISSUE-060 |
| MAS | Doze marcos de aquisição, fabricação e entrega | ISSUE-062 |
| Diligenciamento e recebimento | Marcos, folga, riscos sugeridos, ação e recebimento | ISSUE-061 |
| Fornecedores | Qualificação, documentos com validade e desempenho | ISSUE-057 |

## Rotas previstas

Prefixo: `/api/suprimentos/`.

| Grupo previsto | Uso | Issue |
|---|---|---|
| `fornecedores` | Consultar, qualificar e atualizar fornecedores | ISSUE-057 |
| `plano-de-compras` | Pacotes planejados e importação | ISSUE-058 |
| `processos` | Etapas e decisões de compra | ISSUE-059, ISSUE-060 |
| `pedidos` | Marcos, recebimento e diligenciamento | ISSUE-061 |
| `mas` | Consultar mapa calculado dos doze marcos | ISSUE-062 |
| `painel` | Consultar indicadores do módulo | ISSUE-063 |

Os grupos são planejamento; cada issue fixa métodos e paths concretos conforme D14.

## Fórmulas e nomes no código

| Termo de negócio | Definição | Nome previsto |
|---|---|---|
| Aderência ao plano de compras | Pacotes adjudicados até a data divididos pelos pacotes planejados até a data | `calculations.purchase_plan_adherence` |
| Avanço de suprimentos | Pesos dos marcos realizados/aplicáveis, ponderados pelo valor do pacote; previsto usa a linha de base | `calculations.procurement_progress` |
| Folga ROS | Dias entre a data necessária no local (ROS) e a previsão de entrega | `calculations.required_on_site_slack` |
| OTD | Entregas até a data contratual divididas pelas entregas realizadas | `calculations.on_time_delivery` |

## Fluxos

Processo de compra: Planejado → Requisição → RFx emitida → Propostas recebidas → Equalização técnica → Equalização comercial → Negociação → Recomendação → Aprovação por alçada → Pedido/contrato emitido. A equalização técnica sempre precede a comercial. Diligenciamento atualiza marcos em ordem; entrega exige recebimento ou importação. O MAS exibe linha de base, previsão e realizado por marco.

## Integrações

Pacotes se vinculam à EAC do Financeiro. Pedido ou contrato emitido cria compromisso via fachada Financeira. Folga negativa gera ação na Central e risco sugerido em Riscos. FAT realizado registra inspeção em Qualidade. O cadastro de fornecedor e colaboradores é compartilhado com Configurações.

## Parâmetros

Mínimo de propostas (3 inicialmente), dias de alerta de folga (7), alçadas de aprovação e pesos dos marcos do MAS (soma 100). Valores são versionados em Configurações; regras próprias de fornecedores e compras entram nas ISSUE-057 a ISSUE-063 e ISSUE-076.

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas | `routes.py` |
| Processo de compra e integrações | `service.py` |
| Folga, OTD e avanço do MAS | `calculations.py` |
| Validações de pacote/proposta/marco | `validation.py` |
| Excel e PDF imprimível | `export.py` |
| Persistência | `models.py`; entidades em `docs/MODELO-DE-DADOS.md` |
| Fragmentos | `api/src/templates/suprimentos/` |
| Tela, estilo e comportamento | `app/_views/suprimentos/` e `app/paginas/suprimentos/` |
| Testes | `api/tests/suprimentos/` |

Todos os arquivos Python são stubs intencionais na ISSUE-002. As ISSUE-057 a ISSUE-063 completam este documento e acrescentam testes de fronteira.
