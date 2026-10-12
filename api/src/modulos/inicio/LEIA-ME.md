# Início

Módulo `inicio`. É a tela padrão do app (a rota `/` resolve para `inicio/home`): o resumo
consolidado do projeto ou do Portfólio — a barra de contexto em etiquetas com a exportação à
direita, um indicador-chave por módulo, a carteira de projetos (só no Portfólio), os pontos de
atenção calculados e os cards dos oito módulos. É uma **leitura**: cada número sai da fachada do
módulo dono, com a data de referência injetada, e nenhuma tabela alheia é lida (D9). A exceção é
a **ponderação da carteira**: o modal lê os critérios e as notas do grupo `portfolio` dos
parâmetros e grava uma versão nova por `configuracoes.service.save_parameter_group`, com
`replace_portfolio_grades` para as notas — a edição da ISSUE-080.

## Telas

| Tela | Conteúdo |
|---|---|
| Início | Contexto do projeto ou do Portfólio em etiquetas (projeto, data de referência, orçamento, término) com Excel e PDF; os oito indicadores-chave clicáveis (ações atrasadas, SPI, CPI, pedidos críticos, riscos críticos, RNC abertas, dias sem afastamento, mudanças aguardando comitê); a **carteira de projetos** (Portfólio) com peso, orçamento, avanço previsto e real, SPI, CPI, projeção e VAC, término pela tendência, riscos no topo, pedidos críticos, ações atrasadas, situação e Abrir, mais o rodapé "Portfólio" com as somas e os índices consolidados; os pontos de atenção calculados; e os cards dos oito módulos com os selos calculados |

O protótipo chama a tela inicial de Home. No GestNow ela é o módulo Início; o relatório
gerencial é o módulo separado `relatorio`.

## A carteira de projetos (ISSUE-080)

No Portfólio, entre os indicadores e os pontos de atenção, a tela mostra a **Carteira de
projetos**: uma linha por projeto, do maior peso para o menor, com o peso da carteira (a barra
e o percentual com duas casas), o orçamento vigente, o avanço real x previsto, o SPI e o CPI
(com a cor da faixa de leitura), a projeção no término com o VAC entre parênteses (sobrecusto
em vermelho, com `+`), o término pela tendência (e a linha de base em "LB"), os riscos no topo,
os pedidos críticos, as ações atrasadas, a **situação** e o **Abrir** — que navega para o
Início daquele projeto (`/inicio/home?projeto=<id>`, `data-tn-tela`). O rodapé "Portfólio" traz
o peso 100,00%, as somas em reais (orçamento e projeção) e os índices consolidados (SPI, CPI),
além das contagens somadas; o VAC entra só na exportação, em coluna própria (o protótipo o
mostrava inline na projeção de cada linha e não o somava).

Cada linha sai da **mesma fachada dona** que o Início do projeto lê, no mesmo corte: o peso de
`financeiro.service.portfolio_weights`; o BAC, o CPI, a projeção e o VAC de
`cost_kpis_overview`; o previsto, o real, o SPI e os términos de `planning_kpis_overview`; os
riscos no topo de `risk_panel`; os pedidos críticos de `list_panel`; e as ações atrasadas de
`count_by_status` — todas com `Scope(project_id=...)`. Os **totais** não releem nada: reusam as
leituras consolidadas que os indicadores do Portfólio já fizeram. Custo medido na demonstração
(25/09/2026, 3 projetos): ~0,68 s para a visão do Portfólio contra ~0,19 s para a do projeto.

## A ponderação da carteira (ISSUE-080)

O botão **Ponderação** (só Gestor ou Admin: `pode_ponderar`) abre o modal, que o servidor
desenha em `inicio/ponderacao.html`. O formulário edita:

* o **peso de cada critério** (`peso_<id>`, 0 a 100, soma 100) — os critérios vigentes do grupo
  `portfolio` (valor financeiro pelo orçamento vigente da EAC, criticidade estratégica e
  complexidade/exposição a risco);
* a **nota de cada projeto por critério de fonte "nota"** (`nota_<projetoId>_<critérioId>`,
  inteira, de `notaMinima` a `notaMaxima`);
* a **justificativa** (mínimo de 10 caracteres).

A **soma dos pesos** acompanha o que se digita (o JS soma os campos; sem gravar) e o botão
**Prévia** manda o formulário para `POST /api/inicio/ponderacao/previa`, que devolve o mesmo
modal com os **pesos resultantes** — calculados pela fórmula do dono
(`financeiro.calculations.portfolio_weights`) com os orçamentos vigentes
(`financeiro.service.current_budgets`), sem gravar versão nenhuma e com campo vazio ou inválido
valendo zero, como o protótipo. **Gravar** (`POST /api/inicio/ponderacao/gravar`) valida, cria a
**versão nova** do grupo `portfolio` com os critérios trocados e a justificativa
(`save_parameter_group`) e substitui as notas da versão nova pelas digitadas
(`configuracoes.service.replace_portfolio_grades`, com a trilha). A resposta traz a marca
`data-ponderacao-salva` (que o JS usa para fechar o modal) e a **carteira atualizada**, no alvo
`carteira-conteudo`.

A prévia e a gravação exigem `Permission.MANAGE` na rota (`Access(module="inicio",
permission=Permission.MANAGE)`) e a fachada repete o `rbac.require` (defesa em profundidade):
Membro recebe 403. A leitura do modal é a do Início (`Access(module="inicio")`).

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
permissão; o fragmento (servidor) traz a barra de contexto, os indicadores, a carteira, a
atenção, os cards e o vazio de origem. Os links de indicador, atenção e card são âncoras com
`data-tn-tela`: a navegação é a do shell. O JS guarda o modal da ponderação (`TN.modal`, corpo
`#ponderacao-modal`) e a soma ao vivo dos pesos.

## Rotas

Prefixo: `/api/inicio/`.

| Rota | Método | Uso |
|---|---|---|
| `resumo` | GET | O fragmento do Início no escopo do request (o alvo `inicio-conteudo`), com a data de referência de hoje |
| `resumo/excel` | GET | Baixar a planilha do resumo (download, `file_route`) |
| `resumo/imprimivel` | GET | Obter a folha imprimível para o PDF do navegador |
| `ponderacao` | GET | O modal da ponderação (o alvo `ponderacao-modal`): critérios, notas e pesos atuais |
| `ponderacao/previa` | POST | Re-renderiza o modal com os pesos resultantes, sem gravar (MANAGE) |
| `ponderacao/gravar` | POST | Grava a versão nova e responde a marca + a carteira (MANAGE; 422 por campo) |

As rotas de `resumo` são READ (`Access(module="inicio")`): o Visualizador vê o resumo. A
`ponderacao` (GET) também é READ; a prévia e a gravação são
`Access(module="inicio", permission=Permission.MANAGE)`. O Fornecedor não alcança o módulo (D7)
e recebe 403.

## Fórmulas e nomes no código

| Termo de negócio | Definição | Nome |
|---|---|---|
| Resumo do escopo | O contexto, os oito indicadores, a carteira, os pontos de atenção e os cards, montados das fachadas donas na data de referência | `service.home_overview` |
| Contexto do escopo | O projeto (código, nome, orçamento e término) ou o Portfólio; no Portfólio o orçamento soma os projetos e o término é o mais distante | `service._scope_budget`, `service._scope_end_date` |
| Indicador-chave | O texto da tela (valor, referência e rodapé) e o valor cru com o tipo da exportação | `service.HomeKpi` (o valor sai da fachada dona; a tela não calcula) |
| Referência de gestão | O que o indicador é lido contra: `Esperado 0`, `Meta ≥ 1,00`, `Limite 0 vencidas` ou `Esperado desde o início do projeto` | `service._kpis` |
| Leitura do índice | 1,00 ou mais é o plano; de 0,95 a 0,99 é atenção; abaixo disso, crítico | `calculations.index_tone`, `calculations.ATTENTION_INDEX` |
| Delta do índice | `0,01 acima vs. mês anterior`, `0,02 abaixo vs. mês anterior` ou `estável vs. mês anterior` | `calculations.delta_text` |
| Dinheiro compacto | `R$ 44,6 mi`, `R$ 12 mil`, `R$ 950` | `calculations.compact_brl` |
| Ponto de atenção | O nível (danger/warning), o texto e o link para a tela dona; a ordem é a do protótipo e o título abre com o código do projeto no Portfólio | `service.HomeAttention`, `service._attention` |
| Prefixo do Portfólio | `TN-2026-014 · ` no título do alerta; no projeto, vazio | `service._prefixer` |
| Selo do card | O indicador resumido de cada módulo (N atrasadas, N itens A abertos, N claims, aderência, N revisão vencida, N RNC, TRIF, N em análise) | `service._cards` |
| Linha da carteira | O projeto, o peso, o BAC, o previsto/real/SPI, o CPI, a projeção/VAC, os términos, as contagens e a situação, lidos das fachadas donas por projeto | `service.PortfolioRow`, `service._portfolio_rows` |
| Rodapé da carteira | As somas em reais e os índices consolidados do Portfólio, reusando as leituras consolidadas dos indicadores | `service.PortfolioTotals`, `service._portfolio_totals` |
| Situação da carteira | O pior entre o SPI e o CPI, pelas faixas do protótipo: SPI no plano a partir de 0,95 e crítico abaixo de 0,90; CPI a partir de 0,98 e abaixo de 0,93 — `Em dia`, `Atenção` ou `Crítico` | `calculations.health_band`, `calculations.health_label`, `calculations.index_band` |
| Nota da carteira | `Peso na carteira pela ponderação composta: Valor financeiro (orçamento vigente) 60% · Criticidade estratégica 25% · Complexidade e exposição a risco 15%. Posição na data de referência.` | `service._portfolio_note` |
| Visão da ponderação | Os critérios e as notas vigentes, a faixa de notas, os pesos atuais da carteira e quem pode salvar | `service.PonderationView`, `service.ponderation_view`, `service._criteria_views` |
| Prévia da ponderação | Os pesos resultantes dos valores digitados, pela fórmula do dono e sem gravar (campo inválido vale zero) | `service.PonderationPreview`, `service.ponderation_preview` |
| Gravação da ponderação | Valida (justificativa, peso 0–100 com soma 100 — a mensagem do dono `portfolio_weights_error` — e nota inteira na faixa), cria a versão nova do grupo `portfolio` e substitui as notas digitadas com a trilha | `service.save_ponderation`, `configuracoes.service.replace_portfolio_grades` |
| Campos do modal | `peso_<critérioId>`, `nota_<projetoId>_<critérioId>` e `justificativa`; a leitura do formulário e as mensagens | `validation.read_form`, `validation.PonderationForm`, `validation.weight_field`, `validation.grade_field` |
| Documento de exportação | A carteira (no Portfólio, a primeira das tabelas, com a linha de totais), os KPIs (com a referência e o rodapé), a tabela dos pontos de atenção e a tabela dos módulos | `export.build_document`, `export._carteira_table` |

Os formatadores usam o `format_value` de `core.export_document` (o mesmo formato da tela, do
Excel e do papel) e o `compact_brl` duplica a leitura compacta da Governança, porque módulo não
importa a apresentação de outro.

## Fluxos

Abrir o Início → o shell carrega a view → a view pede `GET /api/inicio/resumo` no alvo
`inicio-conteudo` → o servidor resolve o escopo (URL, cookie, Portfólio), lê as fachadas donas na
data de hoje e desenha o fragmento. O clique num indicador, num ponto de atenção ou num card
navega para a tela dona com o filtro da leitura (`?status=atrasada`, `?faixa=critico`,
`sistema=<id>`, `?revisao=vencidas`, `?busca=<código>`, `?hipo=1`, `?situacao=Aguardando comitê`);
o **Abrir** de uma linha da carteira troca o escopo pelo projeto.

**Ponderação**: o botão abre o modal (`GET /api/inicio/ponderacao` no alvo `ponderacao-modal`);
**Prévia** posta o formulário para `/api/inicio/ponderacao/previa` e o modal é redesenhado com
os pesos resultantes; **Gravar ponderação** posta para `/api/inicio/ponderacao/gravar` e a
resposta traz `data-ponderacao-salva` (o JS fecha o modal), o toast pelo cabeçalho e a carteira
atualizada no alvo `carteira-conteudo`. O formulário declara `x-target="ponderacao-modal
carteira-conteudo"`, `x-target.422="ponderacao-modal"` e `x-target.error="ponderacao-modal"`: no
sucesso os dois alvos são trocados, em qualquer recusa (422, 403 ou 5xx) só o modal — a recusa
não pode esvaziar a carteira nem cair no reenvio nativo do Alpine AJAX.

Excel e PDF saem pelos mecanismos genéricos da plataforma (`data-tn-excel`, `data-tn-pdf`).

## Integrações

A fachada lê, uma vez por request, as leituras das fachadas donas (D9): Central de Ações
(`count_by_status`, `list_actions`), Planejamento (`planning_kpis_overview`, `punch_overview`),
Financeiro (`cost_kpis_overview`, `contracts_overview`, `portfolio_weights`, `current_budgets`),
Suprimentos (`list_panel`, `list_orders`), Riscos (`panel_service.risk_panel`), Qualidade
(`painel_service.quality_indicators`, `list_rncs`), HSE (`painel_service.panel`) e Governança
(`register_overview`). No Portfólio, a carteira repete as leituras de custo e planejamento por
projeto, além de `risk_panel`, `list_panel` e `count_by_status`; os totais reusam os
consolidados. Nenhuma fórmula de dono é duplicada e nenhuma tabela alheia é lida — a exceção é
a gravação da ponderação, que grava pela fachada dona (`save_parameter_group` e
`replace_portfolio_grades`, do módulo Configurações). Os cards usam a primeira tela de cada
módulo da lista de navegação (`core.navigation`).

## Parâmetros

A ponderação lê e grava o grupo **`portfolio`** dos parâmetros vigentes: `criterios` (id, nome,
peso e fonte), `notaMinima` e `notaMaxima` (1 a 5) e as notas por projeto e critério, que vivem
dentro da versão (`portfolio_ponderacao`). A meta do SPI e do CPI exibida nos cards é a leitura
≥ 1,00 do Início; as demais referências vêm das fachadas. O Portfólio usa o orçamento do
cadastro dos projetos (a soma) e o término previsto mais distante no contexto, e o orçamento
vigente da EAC no peso e na carteira.

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas | `routes.py` |
| Agregação, indicadores, atenção, cards, carteira e ponderação | `service.py` (`home_overview`, `_portfolio_rows`, `ponderation_view`, `ponderation_preview`, `save_ponderation` e os `_*_kpi`/`_attention_*`) |
| Formatação, tons e faixas da situação | `calculations.py` |
| Definição e leitura dos campos do modal da ponderação | `validation.py` |
| Documento de exportação | `export.py` |
| Fragmentos | `api/src/templates/inicio/` (`home.html`, `_carteira.html`, `ponderacao.html`, `ponderacao_salvo.html`) |
| Tela, estilo e comportamento | `app/_views/inicio/` e `app/paginas/inicio/` |
| Testes | `api/tests/inicio/` |

O módulo não tem tabela própria (`models.py` vazio): a tela só lê, e a ponderação grava pelos
parâmetros de Configurações.

## Idioma (ISSUE-087)

A fatia do inglês (D13) traduz no servidor: o catálogo é `api/src/core/translations.py`
(namespace `inicio`), o idioma vem do cookie `gestnow_idioma` (`pt` é o padrão) e a rota
`POST /api/idioma` grava a escolha; o seletor PT | EN fica na barra lateral. O `t` e o `idioma`
entram no contexto de todo fragmento por `core/responses.py`, então os templates chamam
`{{ t('inicio', 'Texto') }}` e as funções de apresentação do módulo (`service.py`,
`calculations.py`, `export.py`, `routes.py`, `validation.py`) recebem `idioma` e usam
`translations.translate('inicio', ...)`. O que é estático nas views (`app/_views/inicio/home.html`)
usa `data-i18n` e o `TN.t` do cliente (`app/ds/i18n.js`); datas seguem o idioma
(`translations.format_date`), número e moeda continuam pt-BR. Para acrescentar tradução, some a
chave ao namespace `inicio` do catálogo; a cobertura em
`api/tests/plataforma/test_traducoes.py` reprova chave marcada sem tradução.
