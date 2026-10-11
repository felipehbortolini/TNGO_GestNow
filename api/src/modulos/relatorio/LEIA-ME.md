# Relatório Gerencial

Módulo `relatorio`. Consolida dados dos módulos em relatórios semanais ou mensais, por projeto ou Portfólio. O modal de emissão é iniciado no Início; as folhas, exportação e impressão pertencem a este módulo. A **Análise do período** (ISSUE-081/ISSUE-082) vive aqui: o texto executivo por módulo (02 a 07), tipo e período, de projeto ou do Portfólio, com os desvios negativos detectados no servidor e o comentário obrigatório de cada um nos módulos 02, 03, 04 e 06.

## Telas previstas

| Tela | Conteúdo | Issue |
|---|---|---|
| Análise do período (modal) | Passo 1 (tipo e período) e passo 2 (resumo, texto e desvios), aberta das telas dos módulos 02 a 07 | ISSUE-081/ISSUE-082 |
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

O modal da Análise do período não é um trio: ele abre de oito telas (02 KPIs e Relato do período, 03 KPIs de custo e Curva S financeira, 04 Painel de suprimentos, 05 Painel de riscos, 06 Painel da qualidade e 07 Painel HSE), o fragmento do servidor desenha o modal inteiro e o comportamento compartilhado mora no par `app/paginas/relatorio/analise.js` e `analise.css`, carregado pelo shell. Cada tela chama `window.TN.analise.abrirDoEndereco("<modulo>")` no `iniciar()` e o botão é um elemento com `data-analise="<modulo>"`.

## Rotas

Prefixo: `/api/relatorio/`.

| Grupo | Uso | Issue |
|---|---|---|
| `analise/periodo` | Passo 1: tipo e períodos, com a situação de cada um (GET abre; POST redesenha com o tipo trocado) | ISSUE-081 |
| `analise/formulario` | Passo 2: resumo, texto e desvios (GET abre; POST redesenha com o que foi digitado) | ISSUE-081 |
| `analise/copiar` | Copiar do período anterior: o texto do anterior, para revisão (POST) | ISSUE-081 |
| `analise/gravar` | Grava a análise (422 por campo, 409 na versão vencida) e responde `data-analise-salvo` (POST) | ISSUE-081 |
| `analise/excluir` | Exclui (Gestor) e responde `data-analise-excluida` (POST) | ISSUE-081 |
| `gerencial` | As folhas do relatório no escopo do request (`?projeto=portfolio|<id>`), no corte do período (`tipo`, `periodo`, `secoes`; sem eles, 422 com a mensagem do formulário) | ISSUE-083 a ISSUE-085 |
| `gerencial/emissao` | O modal de emissão: escopo, tipo, período, situação de relatos e análises e seções (GET abre; POST redesenha com o que foi trocado) | ISSUE-083 |
| `gerencial/excel` | Baixar planilha do relatório | ISSUE-086 |
| `gerencial/impressao` | Obter folha imprimível para PDF do navegador | ISSUE-086 |

Todas as rotas da análise pedem `Access(module="relatorio", permission=Permission.WRITE)`, exceto `analise/excluir`, que pede `Permission.MANAGE`; a fachada repete a permissão. As duas rotas do relatório gerencial (`gerencial` e `gerencial/emissao`) são `Access(module="relatorio")` (READ): o Visualizador vê as folhas e a situação que o modal mostra. No Portfólio a análise nasce com projeto nulo, sobre os números consolidados, e a faixa de períodos vai do início mais antigo da carteira; ela não se mistura com a do projeto (a UK com `NULLS NOT DISTINCT` separa as duas).

## Fórmulas e nomes no código

| Termo de negócio | Definição | Nome |
|---|---|---|
| Detecção do planejamento | Desvios do 02 no corte: `avanco` (desvio acumulado < 0), `avanco_periodo` (real do período < previsto), `termino` (término pela tendência depois da linha de base), `areas` (áreas com desvio negativo) e `produtividade` (SPI de quantidades < 1, FP acima da meta, aderência, pessoas trabalhando e utilização abaixo da meta) | `calculations.planning_deviations` |
| Detecção do financeiro | Desvios do 03 no mês de competência: `cpi` (< 1), `spi_custo` (< 1), `vac` (< 0) e `pacotes` (nível 1 com sobrecusto projetado); sem fechamento, nenhum | `calculations.cost_deviations` |
| Detecção de suprimentos | Desvios do 04 no corte: `aderencia` (< 100%), `otd` (< 100%), `criticos` (folga negativa) e `marcos_atrasados` (marcos realizados no período com atraso) | `calculations.procurement_deviations` |
| Detecção da qualidade | Desvios do 06 no corte: `rnc_vencidas` (prazo de tratamento vencido), `aprovacao_inspecao` e `conformidade_auditoria` (abaixo da meta vigente; no limite, não é desvio) e `auditorias_atrasadas` | `calculations.quality_deviations` |
| Riscos e HSE sem detecção | Em 05 e 07 só o texto é exigido (o protótipo não define regra); o resumo vem do painel de riscos e do painel HSE | `calculations.analysis_summary` |
| Taxas do HSE no resumo | O tipo `num2`: duas casas fixas com vírgula (`6,80`) | `calculations.format_number2` |
| Texto numérico do desvio | A descrição no formato do protótipo, por chave (reutilizável pela 083) | `calculations.deviation_description` |
| Resumo do período | Os indicadores do passo 2, por módulo (rotulo, valor e tipo de formatação) | `calculations.analysis_summary` |
| Mês de competência do custo | No Mensal o próprio mês; no Semanal o último mês fechado até o fim do período | `calculations.competence_month` |
| Término pela tendência | O primeiro mês da tendência que chega a 100%; sem chegar, o último mês com valor | `calculations.trend_finish` |
| Limites | Texto de 150 a 2.500 caracteres (trim) e comentário de desvio de 20 a 600 | `validation.MIN_TEXT`, `MAX_TEXT`, `MIN_COMMENT`, `MAX_COMMENT` |
| Corte do período | Fim do período limitado à data de referência; é o corte de todas as folhas do relatório | `calculations.report_period_cutoff` |
| Período parcial | Período que ainda contém a data de referência (sai marcado parcial, dados até a referência) | `calculations.is_partial_period` |
| Barras do avanço por período | As últimas 8 semanas ou 6 meses até o corte, sem períodos anteriores ao início do projeto; a barra é o incremento entre os pontos acumulados do dono (no semanal, a semana do gráfico da curva; no mensal, o mês da série) | `calculations.bar_periods`, `calculations.period_bars` |
| Situação do relatório no modal | Relato registrado ou pendente por escopo (projeto) ou por projeto (Portfólio), com o endereço que abre o relato; a análise de cada módulo com registrada, desvios sem comentário ou pendente | `service.report_status`, `service._analysis_status` |
| Tendência financeira por desempenho | EAC calculada por CPI no mês do relatório, sem dados posteriores ao corte | Pertence a `financeiro.calculations.financial_eac_trend` |

A detecção não duplica fórmula de dono: ela chama as fachadas públicas de Planejamento (`planning_kpis_overview`, `curva_fisica_overview`, `performance_overview`), Financeiro (`cost_kpis_overview`, `mapa_controle`) e Suprimentos (`list_panel`, `list_orders`) com a data de referência ajustada ao corte do período. No 05 chama o painel de riscos (`panel_service.risk_panel`) e o registro (`service.list_risks`); no 06, `qualidade.service.list_rncs`, `list_inspections` e `list_audits` mais as metas dos parâmetros; no 07, o painel HSE (`painel_service.panel`) e a tela de ocorrências (`service.occurrences_screen`). Em 05 e 07 não há detecção. Em inglês, o indicador é chamado Estimate at Completion na fonte; no produto o termo é **Projeção no término**, nunca EAC.

## Fluxos

Passo 1: tipo (Semanal ou Mensal, registros distintos) e período (do início do escopo ao corrente, o mais recente primeiro, com a situação: análise registrada, em andamento ou pendente; padrão: período anterior; no Portfólio, do início mais antigo da carteira). Passo 2: resumo dos indicadores do período, texto de 150 a 2.500 caracteres e um campo por desvio negativo detectado, com comentário obrigatório de 20 a 600 caracteres nos módulos 02, 03, 04 e 06; em 05 e 07 só o texto é exigido. Um registro por projeto (ou do Portfólio, com projeto nulo), módulo, tipo e período; o comentário é gravado pela chave do desvio e um desvio novo, surgido porque os dados mudaram, aparece como pendente. Trocar período volta ao passo 1; Copiar do período anterior traz o texto do período imediatamente anterior do mesmo tipo (só quando há registro), para revisão; Excluir exige Gestor e devolve o período a pendente. O endereço `?analise=1&tipo=&periodo=` abre o modal direto no passo 2 (links do relatório gerencial). Gravar exige Membro; editar mantém módulo, tipo e período e uma versão vencida é recusada com 409.

Selecionar semanal/mensal, projeto/Portfólio, período e seções → consultar se relatos/análises estão registrados → montar folhas no corte → exportar Excel ou abrir a versão imprimível e acionar a impressão do navegador. Período em andamento é marcado como parcial. A 083 lê as análises daqui.

**Relatório gerencial (ISSUE-083):** o botão **Emitir relatório** da tela — ou `?relatorio=1` no endereço — abre o modal; trocar o escopo, o tipo ou o período o redesenha pelo servidor, que recomputa a situação real do relato (por projeto, no Portfólio) e da análise de cada módulo, com o link para registrar. **Emitir** leva o formulário de agora para `/relatorio/gerencial?projeto=&tipo=&periodo=&secoes=`, que carrega as folhas no alvo `gerencial-conteudo` (o `?projeto=` é o escopo do request). As folhas saem no corte do período: a **1** com a posição do corte (previsto, real, SPI e o SPI anterior, avanço do período, término pela tendência x linha de base e desvio acumulado), a produtividade da janela de semanas (SPI de quantidades, FP, aderência, pessoas trabalhando, utilização e HH paralisadas, com as metas vigentes e as empresas em alerta), a Curva S física mensal do dono, as barras do avanço por período (8 semanas ou 6 meses até o corte) e o avanço por área (por projeto, no Portfólio); a **2** com a análise do período (texto e desvios negativos com o comentário de cada um; sem comentário, "Comentário pendente") e o relato (atividades do período e do próximo, pontos de atenção com o risco atrelado), com o aviso e o link quando falta análise ou relato. No Portfólio a folha 2 traz os relatos dos projetos e os pontos de atenção de todos, com a análise da carteira. A impressão é a do navegador: A4 na horizontal, uma folha por página (a página nomeada `@page relatorio-gerencial`, sem margem — a margem está dentro da folha), a navegação fora pelo mecanismo do DS e a fonte da folha que passar da altura útil encaixada até 6,4 pt. Excel e "Alterar período" chegam na ISSUE-086.

## Integrações

Lê resumos das fachadas de Planejamento, Financeiro, Suprimentos, Riscos, Qualidade, HSE e Início/Portfólio, além de relatos e análises. O módulo não lê as tabelas alheias diretamente: a Análise do período (ISSUE-081/ISSUE-082) consome as fachadas públicas dos módulos donos, chamadas com o corte do período (no 05, `risk_panel` e `list_risks`; no 06, `list_rncs`, `list_inspections` e `list_audits` com as metas dos parâmetros; no 07, `panel` e `occurrences_screen`), e a fachada da Riscos sugere riscos (ISSUE-067). O relatório gerencial lê o relato pela fachada do Planejamento (`find_report` no projeto; `list_reports` no Portfólio, uma vez, para a situação de cada projeto) e a análise pela mesma composição do passo 2 sem exigir WRITE (`service._analysis_reading`), porque a tela e o modal são READ — o Visualizador vê a situação que o modal mostra. Exportação comum e impressão seguem a porta genérica da ISSUE-017.

## Parâmetros

Tipo e granularidade do período: semana ISO (segunda a domingo) ou mês civil; corte limitado à data de referência. A lista de seções do Conteúdo é a de `service.REPORT_SECTIONS` — nesta fatia só Planejamento, em duas páginas; as folhas 3 a 7 e a Carteira chegam nas ISSUE-084/ISSUE-085. Metas exibidas pertencem aos módulos donos: a produtividade usa o grupo `produtividade` dos parâmetros vigentes; a qualidade, as metas de aprovação e conformidade do grupo `qualidade` (sem versão vigente no corte, valem os valores iniciais, como nos demais módulos).

## Carga de demonstração

O `seed.py` tem duas partes, cada uma pinada aos seus módulos. A parte `relatorio-analises` (ISSUE-081) lê as 22 análises do protótipo dos módulos 02, 03 e 04 — inclusive as seis do Portfólio (`projeto_id` nulo) — e a parte `relatorio-analises-050607` (ISSUE-082) lê as 18 dos módulos 05, 06 e 07 (12 de projeto e 6 do Portfólio, a maioria sem desvios, como no mock); juntas são os 40 registros. As duas deslocam os períodos em períodos inteiros e os carimbos em dias (`shift_date`) e gravam pela fachada, com a trilha. O mock das análises tem chaves de desvio que o motor do próprio protótipo não produz (projetos 2 e 3 e o Portfólio); a detecção segue o motor e a divergência está em `docs/DIVERGENCIAS-DO-PROTOTIPO.md`.

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas | `routes.py` |
| Composição, corte e permissões | `service.py` (`report_status`, `report_view`, `report_scope` e os helpers das folhas) |
| Detecção, textos, resumo, corte e barras | `calculations.py` |
| Validação das opções e dos limites | `validation.py` |
| Persistência de entidades próprias | `models.py` (`analise_periodo`, `analise_periodo_desvio`); entidades em `docs/MODELO-DE-DADOS.md` |
| Fragmentos | `api/src/templates/relatorio/` (`analise_periodo.html`, `analise_formulario.html`, `analise_salvo.html`, `analise_excluido.html`; `folhas.html`, `folha_planejamento_kpis.html`, `folha_planejamento_relato.html`, `_folha.html`, `_analise_periodo.html`; `emissao.html`, `emissao_relato.html`, `emissao_analises.html`) |
| Comportamento e estilo do modal da análise | `app/paginas/relatorio/analise.js` e `analise.css` (carregados pelo shell; os botões vivem nas views dos módulos 02 a 07) |
| Tela, estilo e comportamento | `app/_views/relatorio/` e `app/paginas/relatorio/` (`gerencial.html`, `gerencial.css`, `gerencial.js`: modal de emissão, carga das folhas, encaixe da fonte e impressão) |
| Carga de demonstração | `seed.py` |
| Testes | `api/tests/relatorio/` |
| Excel/impressão | `export.py` (Excel, ISSUE-086; a impressão do relatório é a do navegador, pela tela) |

As ISSUE-084 a ISSUE-086 completam este documento e acrescentam as folhas 3 a 7, a exportação e a troca de período.
