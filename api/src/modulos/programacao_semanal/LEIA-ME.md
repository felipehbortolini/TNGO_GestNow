# Programação Semanal

Módulo `programacao_semanal`. É a aplicação `Timenow - Programação Semanal` adaptada ao escopo de projeto, aos cadastros e aos perfis do GestNow (D10). Não é a tela reduzida do protótipo.

## Telas

| Tela | Conteúdo | Issue |
|---|---|---|
| Programação | Matriz de atividades de segunda a domingo, previsto e realizado; criar, editar e excluir (051), lançar realizado e fluxo (052) | ISSUE-051, ISSUE-052 |
| Governança da programação | Pedidos de alteração e histórico por empresa/semana | ISSUE-053 |
| Configuração da programação | Parâmetros e janelas, por projeto | ISSUE-054 |
| Importação e impressão | Conferência da planilha, exportação Excel e relatório imprimível | ISSUE-055 |
| Dashboard | Curva do avanço programado, aderência, ranking, heatmap, turnos e gargalos | ISSUE-056 |

## Trios das telas

Cada tela da lista de navegação (`api/src/core/navegacao.json`) tem um trio com o mesmo nome: a view, o estilo e o comportamento da página. O CSS é escopado pela classe raiz da view (`.pagina--<modulo>-<tela>`, com o `_` do identificador mantido), o JS registra `TN.paginas["<modulo>/<tela>"]` e o shell (`app/index.html`) vincula o CSS e o JS de todos. A verificação `trio-da-tela` confere o conjunto. Convenção completa em `docs/PADROES-DE-PAGINA.md`, seção "O trio da tela".

As cinco telas aparecem como abas do grupo Programação Semanal no módulo 02 Planejamento, mas têm pasta própria (D10).

| Tela | View | CSS | JS |
|---|---|---|---|
| Programação | `app/_views/programacao_semanal/programacao.html` | `app/paginas/programacao_semanal/programacao.css` | `app/paginas/programacao_semanal/programacao.js` |
| Dashboard da programação | `app/_views/programacao_semanal/dashboard.html` | `app/paginas/programacao_semanal/dashboard.css` | `app/paginas/programacao_semanal/dashboard.js` |
| Governança da programação | `app/_views/programacao_semanal/governanca.html` | `app/paginas/programacao_semanal/governanca.css` | `app/paginas/programacao_semanal/governanca.js` |
| Importação e impressão | `app/_views/programacao_semanal/importacao.html` | `app/paginas/programacao_semanal/importacao.css` | `app/paginas/programacao_semanal/importacao.js` |
| Configuração da programação | `app/_views/programacao_semanal/configuracao.html` | `app/paginas/programacao_semanal/configuracao.css` | `app/paginas/programacao_semanal/configuracao.js` |

## Rotas (ISSUE-051 a ISSUE-054)

Prefixo `/api/programacao-semanal/`. Todas declaram `Access(module="programacao_semanal")` (o fornecedor alcança o módulo; o recorte por empresa e o papel são da fachada) e respondem fragmento com alvos de id fixo: `prog-janela`, `prog-filtros`, `prog-resumo`, `prog-tabela` e `drawer`. A governança (ISSUE-053) usa `gov-painel`, `gov-pedidos` e `gov-trilha`; a configuração (ISSUE-054) usa `config-painel`, `config-parametros` e `config-janelas`.

| Rota | Método | O que devolve |
|---|---|---|
| `programacoes` | GET | Faixa de indicadores + matriz da semana (`semana`, `local`, `empresa`, `encarregado`, `responsavel`, `situacao`, `aprovacao`, `ppc`, `busca`, `ordena`, `ordem`) |
| `programacoes/filtros` | GET | Barra de ferramentas: semana, busca, painel de refino e a ação "Publicar as validadas" (Planejador) |
| `programacoes/janela` | GET | Faixa da janela (aberta, fechada e o motivo; no Portfólio, "só leitura") |
| `atividades/formulario` | GET | Painel de nova atividade (`semana`) ou de edição (`atividade`) |
| `atividades` | POST | Cria (sem `atividade_id`) ou salva; 422 e 409 devolvem o painel preenchido |
| `atividades/excluir` | POST | Exclui (só Admin, e só sem pedidos de alteração) e redesenha a matriz |
| `atividades/detalhe` | GET | Painel de leitura da atividade: ficha, grade dos dias, histórico e "Pedir alteração" onde a edição fecha |
| `validacoes/formulario` | GET | Painel de validar: o fiscal responsável e os comentários ao fornecedor |
| `validacoes` | POST | Valida a programação e define o fiscal; 422 e 409 devolvem o painel e a matriz |
| `realizados/formulario` | GET | Painel de anexar o realizado: os dois turnos e os atalhos |
| `realizados` | POST | Grava o realizado por turno/dia; o desvio acima do limite exige observação |
| `aprovacoes/formulario` | GET | Painel do fiscal: aprovar o realizado ou reabrir com motivo |
| `aprovacoes` | POST | Aprova o realizado (congela para o fornecedor) |
| `reaberturas` | POST | Reabre o realizado aprovado, com motivo |
| `publicacoes` | POST | Publica uma atividade validada e encerra a edição dela |
| `publicacoes/semana` | POST | Publica todas as validadas da semana que a pessoa vê |
| `governanca` | GET | Painel da governança (`gov-painel`): indicadores, janelas, lista de controle por contratada/semana e os pontos de carga da fila e da trilha |
| `governanca/trilha` | GET | Trilha de auditoria da programação (`gov-trilha`), só Planejador no projeto e Admin |
| `governanca/excel` | GET | Excel do painel e da fila (download, `file_route`) |
| `governanca/imprimivel` | GET | PDF do painel e da fila (`data-tn-pdf`, imprimível genérico) |
| `pedidos` | GET | Fila de pedidos de alteração (`gov-pedidos`): pendentes e resolvidos |
| `pedidos/formulario` | GET | Painel de abrir um pedido (`atividade`), com o motivo |
| `pedidos` | POST | Abre o pedido (qualquer perfil que enxerga o item; motivo de 10 caracteres); 422 devolve o painel e a matriz |
| `pedidos/{id}/decisao` | POST | Aplica ou recusa o pedido (Planejador); 422/409 devolvem a fila e a trilha |
| `configuracao` | GET | Painel da configuração (`config-painel`): parâmetros e janelas por empresa; no Portfólio, o aviso de escolher um projeto |
| `configuracao/parametros` | POST | Grava os parâmetros (Planejador no projeto ou Admin); 422/409 devolvem `config-parametros` preenchido |
| `configuracao/janela` | POST | Grava a janela de uma empresa (dias, semanas e extras); 422/409 devolvem `config-janelas` com o cartão recusado preenchido |
| `importacao` | GET | Aba de importação e impressão (`importacao-painel`): os passos, os cadastros aceitos e os botões da semana |
| `importacao/modelo` | GET | Modelo da planilha do app (.xlsx, download pelo `file_route`, sem gate de fragmento) |
| `importacao/conferir` | POST | Conferência linha a linha (`importacao-conferencia`), sem gravar; 422 quando o arquivo não é planilha |
| `importacao/confirmar` | POST | Grava só o que passou, tudo ou nada, com o digest do `core.importing` |
| `semana/excel` | GET | Excel da semana com as abas do app (download) |
| `semana/imprimivel` | GET | Folha imprimível da semana (`data-tn-pdf`, imprimível genérico) |

Os painéis do fluxo declaram `x-target="drawer prog-resumo prog-tabela"`: no 422/409 a resposta traz o painel **e** a faixa e a matriz, porque alvo declarado que não vem na resposta é esvaziado pelo Alpine AJAX. O formulário de decisão da fila declara `x-target="gov-pedidos gov-trilha"`, e a resposta (`fila_resposta.html`) traz os dois. Na configuração, cada formulário declara o seu próprio bloco (`config-parametros` ou `config-janelas`) e a resposta traz só ele — o `422/409` volta com o digitado e as mensagens ao lado dos campos.

Na importação, o formulário do envio declara `x-target="importacao-conferencia"` e a conferência volta nesse alvo com o botão de confirmar (o mesmo formulário, que reenvia o arquivo e o resumo conferido); os fragmentos da conferência e do resultado são os do fluxo genérico (`comum/_importacao_conferencia.html` e o resultado do módulo). Prevista na próxima issue: `dashboard` (056).

## Estrutura portada do app

| Arquivo | O que tem | Origem no app |
|---|---|---|
| `weeks.py` | Semana `S.30/2026`, segunda a domingo, ISO (2026 tem 53), `week_dates`, `shift`, `horizon` | `core/semanas.py` |
| `calculations.py` | Os sete dias, total, PPC, faixa, aderência, PPC médio, `figures_of` e a curva S (`CurveActivity`, `CurvePoint`, `curve_points`) | `core/calculos.py` |
| `window.py` | `decide`: extraordinária vence, depois semana liberada, depois dia e hora | `core/janela.py` |
| `permissions.py` | Quem cria, edita, valida, lança, aprova, publica, exclui (papel por projeto, D7) e `next_action`, a fila dos cinco degraus | `core/rbac.py` |
| `validation.py` | Formulário da atividade (obrigatórios, soma dos dias com tolerância de 0,51) e os painéis do fluxo (validar, realizado, aprovar/reabrir) | `blueprints/atividades.py` |
| `importers.py` | Importador da planilha do app (`programacao-semanal`): colunas, `_Conferencia` linha a linha e a gravação pela fachada | `core/planilha.py` (leitura) + `blueprints/importacao.py` |
| `service.py` | Fachada: recorte por empresa, janela, Portfólio somente leitura, gravação pelo `recording`, as transições do fluxo e a regra do desvio | `core/registro.py`, `core/dados.py` |
| `repository.py`, `models.py` | Consultas e tabelas `programacao_*` (migração `m051`); a trilha de uma atividade para o painel de detalhe | `core/repositorio.py` (JSON) |
| `views.py`, `presentation.py`, `screen.py` | Linha da matriz com os textos e as ações decididos no Python, grade dos dias, pastilhas, cabeçalhos, contextos dos painéis | `templates/programacao/*` |
| `seed.py`, `demonstracao.json` | Carga: o ambiente `demo-obra` do app no projeto `TN-2026-014`, datas e semanas deslocadas | `data/demo-obra` |

Tradução de termos do app: ambiente = projeto, empresa = `company`, encarregado = `foreman`, responsável (fiscal) = `inspector`, atividade = `Activity`, `dias_previsto` = `planned_days`, `dias_realizado` = turno dia (`day_shift`), `dias_noite` = `night_shift`, `id_exclusiva` = `unique_id`, situação = `situation`, aprovação do realizado = `approval`.

## Fluxo de estado (ISSUE-052)

Fornecedor cria/edita na janela → **Planejador valida e define o fiscal** → Encarregado/Fornecedor informa o realizado por turno dia/noite → **Fiscal aprova (o realizado congela) ou reabre com motivo** → **Planejador publica** (a edição da semana encerra). Situação da programação (`em_elaboracao`, `validada`, `publicada`) e aprovação do realizado (`pendente`, `aprovado`) são estados distintos: uma atividade publicada pode ter realizado pendente.

Cada transição só é aceita do papel certo no projeto (D7) — validar e publicar do Planejador, lançar do Encarregado ou Fornecedor, aprovar/reabrir do Fiscal, e o Admin faz tudo; os demais recebem 403. Só se lança sobre programação validada, e o realizado aprovado não muda mais.

O realizado entra por turno, dia a dia, com os atalhos **"= previsto"** e **"copiar a semana"** na tela. Quando o desvio do total passa do parâmetro `limite_desvio_justificativa` e `exige_justificativa_desvio` está ligado, a **observação é obrigatória**; a conta é `abs(total − previsto) / previsto × 100`, a mesma do app (`calculations.deviation_percent`). A matriz mostra, em cada linha, o **botão da próxima ação** de quem está olhando e o menu só com o que o perfil pode fazer: a regra é `permissions.next_action`, a fila validar → lançar → aprovar → publicar → ver. "Publicar as validadas" publica a semana inteira de uma vez.

Um pedido aprovado pode reabrir uma programação publicada com trilha (ISSUE-053).

## Pedidos de alteração e governança (ISSUE-053)

Publicado ou com o realizado aprovado, o item fecha para edição; o caminho para mudar
continua sendo um **pedido de alteração**: o fornecedor — na verdade, qualquer perfil que
enxergue o item — escreve o motivo (mínimo 10 caracteres) no painel de detalhe ou pelo
menu de ações da matriz, e o Planejador aplica ou recusa na fila da Governança. Aplicar
**reabre** a atividade (se o realizado estava aprovado, volta a pendente) e deixa o
combinado nos comentários; recusar exige resposta (mínimo 5 caracteres). O estado do
pedido é `pendente`, `aplicado` ou `rejeitado` (`service.REQUEST_*`); o fornecedor só vê
os da própria empresa e o Planejador vê os do projeto. Cada passo grava a trilha única
(`core/audit`) com antes e depois — a do pedido e a do efeito na atividade —, e a
Governança mostra a trilha filtrada pelas entidades do módulo
(`service.TRAIL_ENTITIES`), sem as linhas de dia (um lançamento de sete dias viraria sete
entradas de uma vez).

A tela **Governança da programação** é o painel por contratada e semana com os mesmos
números do app (regra de `dados.governanca` em `service.governance_panel`): total,
contagens por situação, pendências (aprovação pendente com realizado), o último fiscal
não vazio do grupo, a aderência ponderada e a última alteração; mais os indicadores
gerais (contratadas ativas, janelas abertas hoje, aguardando fiscal e total no histórico)
e a lista de janelas com o motivo de estar aberta ou fechada. No Portfólio a lista abre a
coluna Projeto, na tela e nas exportações. A lista de controle e a fila saem em Excel e
PDF pelo documento único (`export.py` + `core.export_document`); a trilha fica só na
tela, como no app.

Regras no código: o pedido só abre em item fechado para edição (`_closed_for_editing`);
decidir é do Planejador ou do Admin (`permissions.can_decide_requests`); a trilha é do
Planejador no projeto e do Admin fora dele (`permissions.can_view_trail`); a fila corta
por empresa do fornecedor e a decisão passa pelo controle de versão do pedido (409).

## Configuração da programação (ISSUE-054)

A subpágina **Configuração da programação** é uma por projeto: os **parâmetros** da
programação e as **janelas por empresa**. É o que o app tinha em Configurações e é da
programação; os cadastros de empresas e pessoas e o de Colaboradores **não** ficam aqui —
são os do GestNow, no módulo Configurações.

| Termo de negócio | Nome no código |
|---|---|
| Parâmetros do projeto | `ScheduleSettingsForm` (form), `service.ScheduleParameters` (leitura), `service.save_parameters` (gravação) |
| Padrões de um projeto novo | `service.ensure_settings` (linha com 60/75/15 e a regra de desvio ligada) |
| Janela de uma empresa | `WindowForm` (form), `window_rules.Window` (domínio), `service.save_window` (gravação) |
| Quem edita | `permissions.can_manage_settings` (Planejador no projeto ou Admin) |
| Configuração do escopo | `service.configuration_of` (`ScheduleConfiguration` + `SettingsWindow`) |

Os parâmetros são a meta de aderência (padrão 60), a meta de PPC (75), a semana de
referência (vazia = semana corrente) e a regra de desvio: `exige_justificativa_desvio`
ligada com o limite de 15%. A **semana de referência** é o que `service.default_week`
devolve para a matriz, o dashboard e a própria configuração. A janela é a do app, com
as três camadas de `window.py`: liberação extraordinária (vence tudo), semana liberada
e dia/horário; o formulário oferece o dia com abre/fecha, as pastilhas de semana de três
anos com os atalhos de trimestre e de ano, e as liberações extraordinárias (uma por
semana, com início e fim absolutos).

Regras: só o **Planejador do projeto ou o Admin** editam (`can_manage_settings`; os
demais recebem 403 — inclusive o Planejador de outro projeto, porque o papel é por
projeto); a mudança **vale na hora** (a próxima requisição lê o novo valor) e a **trilha
única** (`core/audit`) guarda o antes e o depois — sem o versionamento com justificativa
dos parâmetros gerais do GestNow. A janela é gravada como um conjunto: os dias, as
semanas e os extras substituem os anteriores, e o `save_window` compõe a linha da trilha
com as regras (não só a linha da tabela). A gravação dos parâmetros passa pelo controle
de versão da linha (409); a da janela, pela versão da janela. Um projeto sem linha lê os
padrões do app; a gravação dos parâmetros cria a linha. No **Portfólio** a subpágina é
somente leitura e pede um projeto (`configuration_of` não monta os formulários e a
gravação recusa com 422); o **fornecedor** só vê a janela da própria empresa (D7).

## Importação, planilha e impressão (ISSUE-055)

A subpágina **Importação e impressão** fecha o ciclo da semana: importar a programação pela
planilha modelo do app, baixar a semana em Excel com as abas do app e gerar o relatório para
imprimir (a folha do app) pela folha de impressão do Design System. O importador é o
`importers.programacao_importer` (chave `programacao-semanal`), registrado com
`importers.register_importers()` e rodado pelo fluxo genérico do `core.importing` (D12): o
modelo é um `Document` (download pelo `file_route`), a conferência lê a planilha e responde o
que cada linha vai fazer **sem gravar**, e a confirmação reenvia o arquivo, confere de novo e
grava tudo ou nada, com o digest do arquivo conferido.

| Termo de negócio | Nome no código |
|---|---|
| Importador da semana | `importers.programacao_importer()` (`KEY = "programacao-semanal"`) |
| Conferência linha a linha | `core.importing.check` com o `Importer` do módulo |
| Confirmação | `core.importing.confirm` (digest e "estou ciente") |
| Linha `Prev.` | a atividade (`service.store_activity`, situação em elaboração) |
| Linha `Real.` | o turno dia do realizado (`service.import_done_days`) |
| Curva S da semana | `calculations.curve_points` + `service.week_curve` |
| Planilha da semana | `export.week_document` (Excel) |
| Folha do relatório | `export.week_report_document` (imprimível) |

As colunas do modelo são as do app na ordem dele (Item, Semana, ID Exclusiva, Atividade
Detalhada, Local, Empresa, Fiscal, Encarregado, Prod. Prevista, Unidade, Prev/Real e os sete
dias), com as regras da `_Conferencia` do app: Semana e ID Exclusiva obrigatórias (e a ID sem
repetir na semana, no arquivo e no banco), Local/Empresa/Unidade/Encarregado/Fiscal dos
cadastros do projeto (o Fiscal é opcional; o Encarregado é validado porque a atividade guarda
`foreman_id`), Produção Prevista maior que zero e a soma dos sete dias batendo com ela
(tolerância de 0,51). A coluna **Prev/Real** aceita `Prev.` e `Real.` (ignorando caixa,
acentos e espaços); a linha `Prev.` cria a atividade e a `Real.` completa o turno dia da
atividade de mesma semana e ID — sem a `Prev.`, a linha `Real.` é ignorada, como no app. A
coluna `Item` é informativa: o item da semana é o próximo do projeto. O papel é o do projeto
(D7): **Planejador no projeto ou Admin** (`permissions.can_import`), como o `importar` do app;
o fornecedor e o visualizador recebem 403; no Portfólio a tela pede um projeto (D8). O modelo
do GestNow é o genérico (`Dados` e `Instruções` com obrigatoriedade, formato e exemplo), não o
arquivo de exemplo do app — os cadastros aceitos aparecem no próprio painel da aba.

O **Excel** (`semana/excel`, download) tem as sete abas do app: `Resumo` (os indicadores e as
contagens de situação, gerados dos KPIs do documento), `Programação` (duas linhas por
atividade, Previsto e Realizado, com as vinte colunas do app), `Por contratada`, `Por frente`,
`Por encarregado`, `Dia a dia` e `Curva S`. A curva é a do app (`indicadores.curva_s`): peso
igual por atividade e o denominador da atividade é o escopo no horizonte de treze semanas (a
semana e as doze anteriores), com base, previsto, realizado e os acumulados. O **relatório**
(`semana/imprimivel`, botão `data-tn-pdf`) sai da mesma fonte: quatro indicadores (aderência,
PPC médio, atividades e contratadas), a matriz com as mesmas linhas do Excel e as tabelas de
contratada, frente e dia a dia, sem navegação no papel — a folha é a do Design System
(`comum/imprimivel.html` + `print.css`). No Portfólio as listas levam a coluna Projeto
(HU-016); as tabelas de quebra e de dia a dia são de conjunto e não são por projeto.

Regras no código: a permissão genérica do importador é a leitura do módulo, e
`permissions.can_import` decide (o `core.importing` não conhece papéis por projeto); a semana
é canônica antes de gravar (`S.1/2026` vira `S.01/2026`) e a gravação repete a checagem de ID
no banco, para que uma repetição que escapou da conferência vire 422 com a linha, não um erro
de banco; a trilha é a única (`core.audit`), pela fachada.

## Integrações

Projeto, empresas, colaboradores, fiscais e encarregados vêm de Configurações. A identidade e o papel da pessoa vêm da plataforma GestNow; fornecedor só acessa a própria empresa. Para isso as rotas declaram `Access(module="programacao_semanal")` e a fachada chama `core.rbac`: `company_scope(user)` corta a consulta pela empresa do fornecedor (e `require_company` recusa a de outra), e `has_schedule_role` / `require_schedule_role(user, project_id, *roles)` conferem o papel no projeto em que a pessoa o recebeu (Planejador, Fiscal, Encarregado, Fornecedor; o papel não vale em outro projeto). O fornecedor não tem permissão geral nenhuma: na programação ele age pelos papéis. O módulo não mantém cadastro paralelo de pessoas/empresas: a configuração lista as empresas do cadastro de Configurações. A saída alimenta o dashboard da programação e os relatórios previstos.

## Parâmetros

Cada projeto tem seus parâmetros e janelas: metas de PPC/aderência, semana de referência, limite de desvio que exige justificativa, semanas/dias/horários liberados e liberações extraordinárias. Projeto novo recebe os padrões do app por `service.ensure_settings` (a criação de projeto, ISSUE-078, chama essa função); a alteração vale na hora e deixa a trilha com antes e depois (ISSUE-054).

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas | `routes.py` (e `screen.py` para o que a tela imprime) |
| Fluxo, recorte por empresa e janela | `service.py`, `window.py`, `permissions.py` |
| PPC, aderência e faixas | `calculations.py` |
| Validações da atividade/planilha | `validation.py` |
| Importação da semana | `importers.py` |
| Planilha e impressão | `export.py` |
| Persistência | `models.py`; entidades em `docs/MODELO-DE-DADOS.md` |
| Fragmentos | `api/src/templates/programacao_semanal/` (`_tabela.html` é a matriz; `formulario.html` o painel da atividade; `_validar.html`, `_realizado.html`, `_aprovacao.html` e `_detalhe.html` os painéis do fluxo; `_painel.html`, `_fila.html` e `_trilha.html` a governança; `_pedido.html` o painel do pedido de alteração; `configuracao.html`, `_parametros.html` e `_janelas.html` a configuração, com os invólucros `parametros.html` e `janelas.html` para as respostas de gravação; `importacao.html` o painel da importação, `importacao_conferencia.html` a conferência e `importacao_resultado.html` o resultado) |
| Carga de demonstração | `seed.py` e `demonstracao.json` |
| Tela, estilo e comportamento | `app/_views/programacao_semanal/` e `app/paginas/programacao_semanal/` |
| Testes | `api/tests/programacao_semanal/` |

O app de origem e seu glossário ficam somente para consulta em `docs/referencia/programacao-semanal/`. Multi-ambiente, seletor de clientes, área do operador, login próprio, SharePoint/JSON e API JSON de leitura permanecem fora de escopo. A ISSUE-051 trouxe a matriz e a programação pelo fornecedor; a ISSUE-052, o fluxo de cinco passos; a ISSUE-053, os pedidos de alteração e a governança; a ISSUE-054, a configuração por projeto; a ISSUE-055, a importação, a planilha e o relatório de impressão; a ISSUE-056 completa o dashboard.

## Testes

- `test_programacao_dominio.py`: semanas, cálculos (incluindo o oráculo de PPC e aderência com a semana S.34/2026 da demonstração) e janela.
- `test_programacao_fachada.py`: recorte por empresa, janela, Portfólio e gravação.
- `test_programacao_rotas.py`: o HTTP da matriz e do formulário, e o `Access` de toda rota.
- `test_programacao_fluxo.py`: a fila da próxima ação por perfil (portada do app), as transições, a regra do desvio e a trilha.
- `test_programacao_fluxo_rotas.py`: os 403 de cada papel, o fornecedor só da própria empresa, 422/409 e o botão/menu por perfil na matriz.
- `test_programacao_governanca.py`: os números do painel como o app calcula, a fila por empresa, abrir/aplicar/recusar com trilha de antes e depois, a reabertura e os papéis.
- `test_programacao_governanca_rotas.py`: o HTTP do painel, da fila, da trilha e dos pedidos, os 403, os 422/409 e as exportações.
- `test_programacao_configuracao.py`: os padrões de `ensure_settings`, a permissão por papel no projeto (Planejador e Admin editam; o Planejador de outro projeto, não), o efeito imediato, a trilha de antes e depois dos parâmetros e das janelas (com os extras entrando, trocando e saindo), o corte do fornecedor e o Portfólio somente leitura.
- `test_programacao_configuracao_rotas.py`: o HTTP do painel, dos parâmetros e das janelas, os 403 por papel, os 422/409 preenchidos e o aviso de escolher um projeto no Portfólio.
- `test_programacao_importacao.py`: o modelo com as colunas do app (gerado e lido de volta), a conferência linha a linha com o motivo e sem gravar, a confirmação gravando só o que passou (tudo ou nada), a linha `Real.` no turno dia, o digest e o "estou ciente", e os papéis e o Portfólio.
- `test_programacao_importacao_rotas.py`: o HTTP da aba, do modelo (download sem gate), da conferência e da confirmação, os 403 de quem não importa e os 422 do arquivo trocado, do Portfólio e do que não é planilha; e as exportações da semana.
- `test_programacao_exportacao.py`: o oráculo da curva S (peso igual por atividade e escopo no horizonte), as sete abas do Excel com as colunas do app e duas linhas por atividade, o Resumo, a coluna Projeto no Portfólio e o documento do relatório.
- `api/tests/plataforma/test_carga_demonstracao.py`: os oráculos do fluxo (estados e próximas ações) e da governança (painel por empresa/semana, pedidos e trilha na carga); a carga da configuração (parâmetros e janelas do app) não mudou com a ISSUE-054.
