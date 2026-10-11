# Relatório Gerencial

Módulo `relatorio`. Consolida dados dos módulos em relatórios semanais ou mensais, por projeto ou Portfólio. O modal de emissão é iniciado no Início; as folhas, exportação e impressão pertencem a este módulo. A **Análise do período** (ISSUE-081) vive aqui: o texto executivo por módulo, tipo e período, com os desvios negativos detectados no servidor e o comentário obrigatório de cada um.

## Telas previstas

| Tela | Conteúdo | Issue |
|---|---|---|
| Análise do período (modal) | Passo 1 (tipo e período) e passo 2 (resumo, texto e desvios), aberta das telas dos módulos 02, 03 e 04 | ISSUE-081 |
| Emissão do relatório | Tipo, período, escopo, seções e estado dos relatos/análises | ISSUE-083 |
| Relatório gerencial | Folhas de Planejamento e dados do período | ISSUE-083 |
| Folhas Financeiro e Suprimentos | Indicadores, análises e projeção financeira | ISSUE-084 |
| Folhas Riscos, Qualidade, HSE e Carteira | Indicadores e consolidados por seção | ISSUE-085 |
| Excel e impressão/PDF | Exportação do relatório e alteração do período | ISSUE-086 |

## Trios das telas

Cada tela da lista de navegação (`api/src/core/navegacao.json`) tem um trio com o mesmo nome: a view, o estilo e o comportamento da página. O CSS é escopado pela classe raiz da view (`.pagina--<modulo>-<tela>`, com o `_` do identificador mantido), o JS registra `TN.paginas["<modulo>/<tela>"]` e o shell (`app/index.html`) vincula o CSS e o JS de todos. A verificação `trio-da-tela` confere o conjunto. Convenção completa em `docs/PADROES-DE-PAGINA.md`, seção "O trio da tela".

O relatório gerencial é tela de detalhe do Início: abre a partir do botão e do modal de emissão que o Início guarda.

| Tela | View | CSS | JS |
|---|---|---|---|
| Relatório gerencial | `app/_views/relatorio/gerencial.html` | `app/paginas/relatorio/gerencial.css` | `app/paginas/relatorio/gerencial.js` |

O modal da Análise do período não é um trio: ele abre de cinco telas (02 KPIs e Relato do período, 03 KPIs de custo e Curva S financeira, 04 Painel de suprimentos), o fragmento do servidor desenha o modal inteiro e o comportamento compartilhado mora no par `app/paginas/relatorio/analise.js` e `analise.css`, carregado pelo shell. Cada tela chama `window.TN.analise.abrirDoEndereco("<modulo>")` no `iniciar()` e o botão é um elemento com `data-analise="<modulo>"`.

## Rotas

Prefixo: `/api/relatorio/`.

| Grupo | Uso | Issue |
|---|---|---|
| `analise/periodo` | Passo 1: tipo e períodos, com a situação de cada um (GET abre; POST redesenha com o tipo trocado) | ISSUE-081 |
| `analise/formulario` | Passo 2: resumo, texto e desvios (GET abre; POST redesenha com o que foi digitado) | ISSUE-081 |
| `analise/copiar` | Copiar do período anterior: o texto do anterior, para revisão (POST) | ISSUE-081 |
| `analise/gravar` | Grava a análise (422 por campo, 409 na versão vencida) e responde `data-analise-salvo` (POST) | ISSUE-081 |
| `analise/excluir` | Exclui (Gestor) e responde `data-analise-excluida` (POST) | ISSUE-081 |
| `gerencial` | Montar relatório por tipo, período, escopo e seções | ISSUE-083 a ISSUE-085 |
| `gerencial/excel` | Baixar planilha do relatório | ISSUE-086 |
| `gerencial/impressao` | Obter folha imprimível para PDF do navegador | ISSUE-086 |

Todas as rotas da análise pedem `Access(module="relatorio", permission=Permission.WRITE)`, exceto `analise/excluir`, que pede `Permission.MANAGE`; a fachada repete a permissão. O Portfólio é recusado com 422 (`scope.require_project`): a análise desta fatia é só de projeto e o Portfólio fica para a ISSUE-082.

## Fórmulas e nomes no código

| Termo de negócio | Definição | Nome |
|---|---|---|
| Detecção do planejamento | Desvios do 02 no corte: `avanco` (desvio acumulado < 0), `avanco_periodo` (real do período < previsto), `termino` (término pela tendência depois da linha de base), `areas` (áreas com desvio negativo) e `produtividade` (SPI de quantidades < 1, FP acima da meta, aderência, pessoas trabalhando e utilização abaixo da meta) | `calculations.planning_deviations` |
| Detecção do financeiro | Desvios do 03 no mês de competência: `cpi` (< 1), `spi_custo` (< 1), `vac` (< 0) e `pacotes` (nível 1 com sobrecusto projetado); sem fechamento, nenhum | `calculations.cost_deviations` |
| Detecção de suprimentos | Desvios do 04 no corte: `aderencia` (< 100%), `otd` (< 100%), `criticos` (folga negativa) e `marcos_atrasados` (marcos realizados no período com atraso) | `calculations.procurement_deviations` |
| Texto numérico do desvio | A descrição no formato do protótipo, por chave (reutilizável pela 083) | `calculations.deviation_description` |
| Resumo do período | Os indicadores do passo 2, por módulo (rotulo, valor e tipo de formatação) | `calculations.analysis_summary` |
| Mês de competência do custo | No Mensal o próprio mês; no Semanal o último mês fechado até o fim do período | `calculations.competence_month` |
| Término pela tendência | O primeiro mês da tendência que chega a 100%; sem chegar, o último mês com valor | `calculations.trend_finish` |
| Limites | Texto de 150 a 2.500 caracteres (trim) e comentário de desvio de 20 a 600 | `validation.MIN_TEXT`, `MAX_TEXT`, `MIN_COMMENT`, `MAX_COMMENT` |
| Corte do período | Fim do período limitado à data de referência | `calculations.report_period_cutoff` (ISSUE-083) |
| Período parcial | Período selecionado ainda não terminou na data de referência | `calculations.is_partial_period` (ISSUE-083) |
| Tendência financeira por desempenho | EAC calculada por CPI no mês do relatório, sem dados posteriores ao corte | Pertence a `financeiro.calculations.financial_eac_trend` |

A detecção não duplica fórmula de dono: ela chama as fachadas públicas de Planejamento (`planning_kpis_overview`, `curva_fisica_overview`, `performance_overview`), Financeiro (`cost_kpis_overview`, `mapa_controle`) e Suprimentos (`list_panel`, `list_orders`) com a data de referência ajustada ao corte do período. Em inglês, o indicador é chamado Estimate at Completion na fonte; no produto o termo é **Projeção no término**, nunca EAC.

## Fluxos

Passo 1: tipo (Semanal ou Mensal, registros distintos) e período (do início do projeto ao corrente, o mais recente primeiro, com a situação: análise registrada, em andamento ou pendente; padrão: período anterior). Passo 2: resumo dos indicadores do período, texto de 150 a 2.500 caracteres e um campo por desvio negativo detectado, com comentário obrigatório de 20 a 600 caracteres nos módulos 02, 03 e 04. Um registro por projeto, módulo, tipo e período; o comentário é gravado pela chave do desvio e um desvio novo, surgido porque os dados mudaram, aparece como pendente. Trocar período volta ao passo 1; Copiar do período anterior traz o texto do período imediatamente anterior do mesmo tipo (só quando há registro), para revisão; Excluir exige Gestor e devolve o período a pendente. O endereço `?analise=1&tipo=&periodo=` abre o modal direto no passo 2 (links do relatório gerencial). Gravar exige Membro; editar mantém módulo, tipo e período e uma versão vencida é recusada com 409.

Selecionar semanal/mensal, projeto/Portfólio, período e seções → consultar se relatos/análises estão registrados → montar folhas no corte → exportar Excel ou abrir a versão imprimível e acionar a impressão do navegador. Período em andamento é marcado como parcial. A 083 lê as análises daqui; a 082 estende as mesmas tabelas para 05/06/07 e o Portfólio.

## Integrações

Lê resumos das fachadas de Planejamento, Financeiro, Suprimentos, Riscos, Qualidade, HSE e Início/Portfólio, além de relatos e análises. O módulo não lê as tabelas alheias diretamente: a Análise do período (ISSUE-081) consome as fachadas públicas dos módulos donos, chamadas com o corte do período, e a fachada da Riscos sugere riscos (ISSUE-067). Exportação comum e impressão seguem a porta genérica da ISSUE-017.

## Parâmetros

Tipo e granularidade do período: semana ISO (segunda a domingo) ou mês civil; corte limitado à data de referência. A lista de seções depende do escopo selecionado. Metas exibidas pertencem aos módulos donos: a produtividade usa o grupo `produtividade` dos parâmetros vigentes.

## Carga de demonstração

A parte `relatorio-analises` (`seed.py`) lê as 22 análises do protótipo dos módulos 02, 03 e 04 (`prototype_collection("analisesPeriodo")`), desloca os períodos em períodos inteiros e os carimbos em dias (`shift_date`) e grava pela fachada, com a trilha. Seis registros são do Portfólio (`projeto_id` nulo) e ficam para a 082. O mock das análises tem chaves de desvio que o motor do próprio protótipo não produz (análise dos projetos 2 e 3); a detecção segue o motor e a divergência está em `docs/DIVERGENCIAS-DO-PROTOTIPO.md`.

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas | `routes.py` |
| Composição, corte e permissões | `service.py` |
| Detecção, textos e resumo | `calculations.py` |
| Validação das opções e dos limites | `validation.py` |
| Persistência de entidades próprias | `models.py` (`analise_periodo`, `analise_periodo_desvio`); entidades em `docs/MODELO-DE-DADOS.md` |
| Fragmentos | `api/src/templates/relatorio/` (`analise_periodo.html`, `analise_formulario.html`, `analise_salvo.html`, `analise_excluido.html`) |
| Comportamento e estilo do modal | `app/paginas/relatorio/analise.js` e `analise.css` (carregados pelo shell; os botões vivem nas views dos módulos 02, 03 e 04) |
| Tela, estilo e comportamento | `app/_views/relatorio/` e `app/paginas/relatorio/` |
| Carga de demonstração | `seed.py` |
| Testes | `api/tests/relatorio/` |
| Excel/impressão | `export.py` |

As ISSUE-083 a ISSUE-086 completam este documento e acrescentam testes de corte, parcialidade e exportação.
