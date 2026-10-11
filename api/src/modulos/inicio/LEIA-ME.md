# Início

Módulo `inicio`. É a tela padrão do app (a rota `/` resolve para `inicio/home`): o resumo
consolidado do projeto ou do Portfólio — a barra de contexto em etiquetas com a exportação à
direita, um indicador-chave por módulo, os pontos de atenção calculados e os cards dos oito
módulos. É uma **leitura**: cada número sai da fachada do módulo dono, com a data de referência
injetada, e nenhuma tabela alheia é lida (D9). A tabela Carteira de projetos e a edição da
ponderação pertencem à ISSUE-080.

## Telas

| Tela | Conteúdo |
|---|---|
| Início | Contexto do projeto ou do Portfólio em etiquetas (projeto, data de referência, orçamento, término) com Excel e PDF; os oito indicadores-chave clicáveis (ações atrasadas, SPI, CPI, pedidos críticos, riscos críticos, RNC abertas, dias sem afastamento, mudanças aguardando comitê); os pontos de atenção calculados; e os cards dos oito módulos com os selos calculados |

O protótipo chama a tela inicial de Home. No GestNow ela é o módulo Início; o relatório
gerencial é o módulo separado `relatorio`.

## Trios das telas

Cada tela da lista de navegação (`api/src/core/navegacao.json`) tem um trio com o mesmo nome: a
view, o estilo e o comportamento da página. O CSS é escopado pela classe raiz da view
(`.pagina--<modulo>-<tela>`, com o `_` do identificador mantido), o JS registra
`TN.paginas["<modulo>/<tela>"]` e o shell (`app/index.html`) vincula o CSS e o JS de todos. A
verificação `trio-da-tela` confere o conjunto. Convenção completa em
`docs/PADROES-DE-PAGINA.md`, seção "O trio da tela".

| Tela | View | CSS | JS |
|---|---|---|---|
| Início | `app/_views/inicio/home.html` | `app/paginas/inicio/home.css` | `app/paginas/inicio/home.js` |

A view guarda o `page-head` e o container `#inicio-conteudo`, e trata carregando, erro e sem
permissão; o fragmento (servidor) traz a barra de contexto, os indicadores, a atenção, os cards
e o vazio de origem. Os links de indicador, atenção e card são âncoras com `data-tn-tela`: a
navegação é a do shell.

## Rotas

Prefixo: `/api/inicio/`.

| Rota | Método | Uso |
|---|---|---|
| `resumo` | GET | O fragmento do Início no escopo do request (o alvo `inicio-conteudo`), com a data de referência de hoje |
| `resumo/excel` | GET | Baixar a planilha do resumo (download, `file_route`) |
| `resumo/imprimivel` | GET | Obter a folha imprimível para o PDF do navegador |

As três são READ (`Access(module="inicio")`): o Visualizador vê o resumo. O Fornecedor não
alcança o módulo (D7) e recebe 403.

## Fórmulas e nomes no código

| Termo de negócio | Definição | Nome |
|---|---|---|
| Resumo do escopo | O contexto, os oito indicadores, os pontos de atenção e os cards, montados das fachadas donas na data de referência | `service.home_overview` |
| Contexto do escopo | O projeto (código, nome, orçamento e término) ou o Portfólio; no Portfólio o orçamento soma os projetos e o término é o mais distante | `service._scope_budget`, `service._scope_end_date` |
| Indicador-chave | O texto da tela (valor, referência e rodapé) e o valor cru com o tipo da exportação | `service.HomeKpi` (o valor sai da fachada dona; a tela não calcula) |
| Referência de gestão | O que o indicador é lido contra: `Esperado 0`, `Meta ≥ 1,00`, `Limite 0 vencidas` ou `Esperado desde o início do projeto` | `service._kpis` |
| Leitura do índice | 1,00 ou mais é o plano; de 0,95 a 0,99 é atenção; abaixo disso, crítico | `calculations.index_tone`, `calculations.ATTENTION_INDEX` |
| Delta do índice | `0,01 acima vs. mês anterior`, `0,02 abaixo vs. mês anterior` ou `estável vs. mês anterior` | `calculations.delta_text` |
| Dinheiro compacto | `R$ 44,6 mi`, `R$ 12 mil`, `R$ 950` | `calculations.compact_brl` |
| Ponto de atenção | O nível (danger/warning), o texto e o link para a tela dona; a ordem é a do protótipo e o título abre com o código do projeto no Portfólio | `service.HomeAttention`, `service._attention` |
| Prefixo do Portfólio | `TN-2026-014 · ` no título do alerta; no projeto, vazio | `service._prefixer` |
| Selo do card | O indicador resumido de cada módulo (N atrasadas, N itens A abertos, N claims, aderência, N revisão vencida, N RNC, TRIF, N em análise) | `service._cards` |
| Documento de exportação | Os KPIs (com a referência e o rodapé), a tabela dos pontos de atenção e a tabela dos módulos | `export.build_document` |

Os formatadores usam o `format_value` de `core.export_document` (o mesmo formato da tela, do
Excel e do papel) e o `compact_brl` duplica a leitura compacta da Governança, porque módulo não
importa a apresentação de outro.

## Fluxos

Abrir o Início → o shell carrega a view → a view pede `GET /api/inicio/resumo` no alvo
`inicio-conteudo` → o servidor resolve o escopo (URL, cookie, Portfólio), lê as fachadas donas na
data de hoje e desenha o fragmento. O clique num indicador, num ponto de atenção ou num card
navega para a tela dona com o filtro da leitura (`?status=atrasada`, `?faixa=critico`,
`sistema=<id>`, `?revisao=vencidas`, `?busca=<código>`, `?hipo=1`, `?situacao=Aguardando comitê`).
Excel e PDF saem pelos mecanismos genéricos da plataforma (`data-tn-excel`, `data-tn-pdf`).

## Integrações

A fachada lê, uma vez por request, 13 leituras das fachadas donas (D9): Central de Ações
(`count_by_status`, `list_actions`), Planejamento (`planning_kpis_overview`, `punch_overview`),
Financeiro (`cost_kpis_overview`, `contracts_overview`), Suprimentos (`list_panel`,
`list_orders`), Riscos (`panel_service.risk_panel`), Qualidade
(`painel_service.quality_indicators`, `list_rncs`), HSE (`painel_service.panel`) e Governança
(`register_overview`). Nenhuma fórmula de dono é duplicada e nenhuma tabela alheia é lida. Os
cards usam a primeira tela de cada módulo da lista de navegação (`core.navigation`).

## Parâmetros

Nenhum parâmetro próprio: as metas e os limites exibidos são dos donos (a meta do SPI e do CPI é
a leitura ≥ 1,00 do Início; as demais referências vêm das fachadas). O Portfólio usa o orçamento
do cadastro dos projetos (a soma) e o término previsto mais distante.

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas | `routes.py` |
| Agregação, indicadores, atenção e cards | `service.py` (`home_overview` e os `_*_kpi`/`_attention_*`) |
| Formatação e tons | `calculations.py` |
| Documento de exportação | `export.py` |
| Fragmento | `api/src/templates/inicio/home.html` |
| Tela, estilo e comportamento | `app/_views/inicio/` e `app/paginas/inicio/` |
| Testes | `api/tests/inicio/` |

O módulo não tem tabela própria (`models.py` vazio) e não tem validação de entrada
(`validation.py` vazio): a tela só lê.
