# Planejamento

Módulo `planejamento`. Controla escopo e avanço físico pela EAP e reúne Curva S, indicadores, relato, 6WLA, produtividade e punch list. A Programação Semanal é um módulo próprio. As funcionalidades chegam nas ISSUE-036 a ISSUE-050.

## Telas previstas

| Tela | Conteúdo | Issue |
|---|---|---|
| EAP | Árvore área/subárea/pacote, dicionário e avanço por critério | ISSUE-036, ISSUE-037, ISSUE-038 |
| Curva S física | Linha de base, real e tendência, com drill por período | ISSUE-039 |
| KPIs de planejamento | Previsto x real, SPI e desvios por período e área | ISSUE-040 |
| Relato do período | Atividades feitas/próximas e pontos de atenção | ISSUE-044 |
| 6WLA | Atividades por semana, restrições e responsáveis | ISSUE-045 |
| Produtividade | Quantidades, horas efetivas, amostragem, paradas e KPIs | ISSUE-046 a ISSUE-048 |
| Punch list | Lista de itens, verificação, bloqueios e painel | ISSUE-049, ISSUE-050 |

## 6WLA (ISSUE-045)

Grade das seis semanas seguintes à semana corrente, com atividades, restrições e responsáveis. A janela começa na segunda-feira da semana seguinte à da data de referência (D6: a data entra como argumento; os testes a injetam). Tabelas: `lookahead`, `lookahead_semana`, `lookahead_restricao` (migração `m045_lookahead_6wla.py`; modelo em `docs/MODELO-DE-DADOS.md`).

**Tela:** `planejamento/6wla` (view `app/_views/planejamento/6wla.html`, fragmentos `api/src/templates/planejamento/6wla_*.html`). Indicadores (atividades no horizonte, prontas nas 2 próximas semanas, restrições abertas, vencidas, índice de remoção) contam todas as atividades do escopo; o filtro (busca, disciplina, só com restrição aberta, lista de restrições) mexe na grade e na lista. A semana programada do curto prazo de atividade com restrição aberta recebe a marca laranja. No Portfólio entra a coluna Projeto (tela e exportações) e a inclusão pede o projeto antes de abrir o formulário.

**Rotas** (`/api/planejamento/6wla`, em `routes.py`): `GET` tela; `GET /excel` e `GET /imprimivel` (Excel e PDF pelos mecanismos genéricos, mesmos filtros); `GET /atividades/nova`, `/atividades/{id}/editar`, `/restricoes/nova`, `/restricoes/{id}/editar`, `/restricoes/{id}/remover` (formulários); `POST /atividades`, `/atividades/{id}`, `/restricoes`, `/restricoes/{id}`, `/restricoes/{id}/remocao` (gravações; 422 com mensagem por campo, 409 em conflito de versão, 403 sem permissão de escrita).

| Termo de negócio | Definição | Nome no código |
|---|---|---|
| Início do horizonte | Segunda-feira da semana seguinte à data de referência | `calculations.lookahead_window_start`, `lookahead_weeks` |
| Restrição aberta | Sem data de remoção | `calculations.constraint_is_open` |
| Restrição vencida | Aberta e com data necessária anterior à referência (o próprio dia não vence) | `calculations.constraint_is_overdue` |
| Atividade pronta | Sem restrição aberta | `calculations.activity_is_ready` |
| Risco no curto prazo | Programada nas 2 primeiras semanas com restrição aberta | `calculations.has_open_constraint_in_short_term`, `week_at_risk` |
| Situação da atividade | `vencida`, `com_restricao` ou `pronta` | `calculations.activity_situation` |
| Índice de remoção | Removidas sobre identificadas, em pontos percentuais; vazio sem restrições | `calculations.removal_index` |
| Indicadores do horizonte | Os cinco números da faixa de KPIs | `calculations.lookahead_figures` |
| Código da atividade | Próximo `LA-NN` do projeto | `calculations.next_activity_code` |
| Barra da atividade | Da primeira à última semana programada, até o sábado | `calculations.activity_span` |

**Fluxo:** a restrição nasce aberta; a remoção registra a data (e, opcional, o comentário) e a libera; remover duas vezes é recusado. Toda gravação passa por `service.py` (transação, trilha e versão). **Carga:** `seed.py` grava a coleção `lookahead` do protótipo com as datas deslocadas. **Oráculo:** `api/tests/oraculo/test_oraculo_6wla.py`. **Testes:** `api/tests/planejamento/test_6wla_*.py`, com o apoio em `api/tests/apoio_6wla.py`.

## Punch list (ISSUE-049)

Itens de completação numerados pelo padrão do projeto (`PL-TN-2026-0001`), com a hierarquia Área, Sistema, Subsistema e TAG, disciplina, categoria (A impede o marco seguinte; B fecha até o aceite definitivo; C conforme acordo), marco vinculado, origem, empresa executante, responsável, prazo, identificado por e abertura. Tabela `punch_item` (migração `m049_punch_list.py`; modelo em `docs/MODELO-DE-DADOS.md`). O painel (burndown, aging, % de liberados por marco) é a ISSUE-050.

**Tela:** `planejamento/punch_list` (view `app/_views/planejamento/punch_list.html`, fragmentos `api/src/templates/planejamento/punch_*.html`, comportamento `app/paginas/planejamento/punch_list.js`). Cinco indicadores que filtram a lista (abertos, categoria A abertos, aguardando verificação, vencidos, fechados), alerta dos sistemas bloqueados, a tabela dos itens e a tabela "Sistemas e liberação por marco". Modais: Novo item e Editar, Enviar para verificação, Fechamento com verificação, Cancelar, Filtros, Anexos do item e a Importação de planilha (`/api/importacao/punch-list`, mecanismo da plataforma). No Portfólio entra a coluna Projeto (tela e exportações) e Novo item e Importar pedem o projeto antes.

**Rotas** (`/api/planejamento/punch-list`, em `punch_routes.py`): `GET` tela (filtros `situacao`, `categoria`, `sistema`, `disciplina`, `empresa`, `busca`; `item=` abre a lista no código, o link de volta da Central); `GET /excel` e `GET /imprimivel`; `GET /filtros`; `GET`/`POST /novo`; `GET`/`POST /{id}/editar`; `POST /{id}/tratar`; `GET`/`POST /{id}/enviar`; `GET`/`POST /{id}/verificar`; `GET`/`POST /{id}/cancelar`. Recusas: 422 com a mensagem sob o campo, 409 em conflito de versão, 403 sem permissão de escrita, para o fornecedor e para o verificador igual ao executante.

| Termo de negócio | Definição | Nome no código |
|---|---|---|
| Item aberto | Nem Fechado nem Cancelado | `punch_calculations.is_open` |
| Fluxo | Aberto vai a Em tratamento; este a Aguardando verificação; este a Fechado ou volta a Em tratamento; Cancelado sai de qualquer aberto | `punch_calculations.next_situations`, `can_move` |
| Idade | Dias da abertura até hoje (aberto) ou até o fechamento | `punch_calculations.item_age_days` |
| Vencido | Aberto com o prazo anterior à referência (o próprio dia não vence) | `punch_calculations.is_overdue` |
| Bloqueio | Itens abertos que seguram um sistema num marco: item A cujo marco é o escolhido ou anterior; no Aceite definitivo, qualquer item aberto | `punch_calculations.blocking_count`, `is_system_blocked` |
| Sistemas do alerta | Bloqueados para a Completação mecânica ou o Comissionamento | `punch_calculations.blocked_system_ids` |
| Fechados sobre válidos | Fechados sobre os não cancelados, arredondado na metade para cima | `punch_calculations.closed_percentage` |

**Fluxo e regras (fachada `punch_service.py`):** fechar exige evidência (ao menos um anexo do item, D5a) e verificador diferente do executante, o responsável pelo item (D7: 403 com a mensagem); sem anexo, 422. O verificador é a pessoa logada. Reprovar volta a Em tratamento, conta a reprovação e exige o motivo. Cancelar exige justificativa de 10 caracteres e conclui a ação. Item fechado ou cancelado não se edita. **Integração (D9):** todo item cria a sua ação na Central pela costura única (`central_acoes.create_action`, origem Punch list); cada passo do item repete na ação o assunto, o grupo, o responsável, o prazo e a situação (`central_acoes.update_from_origin`), e fechar ou cancelar conclui a ação (`close_from_origin`). A Central trata a ação da Punch list na origem (concluir e replanejar lá são recusados) e o link da ação volta para o item (`origin_links`, `?item=`). Importador (`punch_importers.py`): uma linha é um item aberto hoje, com a sua ação, pela fachada; linha inválida é recusada e as válidas só gravam na confirmação.

**Carga:** `seed_punch.py` grava os 20 itens do protótipo (códigos e situações do mock, datas deslocadas); as ações vêm da carga da Central. **Oráculo:** `api/tests/oraculo/test_oraculo_punch.py`. **Testes:** `api/tests/planejamento/test_punch_*.py`, com o apoio em `api/tests/apoio_punch.py`.
## EAP (ISSUE-036)

Árvore área (nível 1), subárea (nível 2) e pacote (nível 3, de trabalho ou de planejamento), com a linha do projeto no topo (código 0, peso 100%, avanço consolidado e datas extremas). Só os pacotes têm peso, datas da linha de base, critério de medição e avanço; áreas, subáreas e o total são somados no servidor (média ponderada pelo peso), e os pesos dos pacotes somam 100% (regra dos 100%; a tela avisa quando não fecham). O **real de cada pacote não é gravado** (D5b, D6): é a última medição (`eap_medicao`, por data e depois por id) lida pelo critério. A medição guarda o % acumulado do pacote; ele vira as entradas do critério (etapas em sequência, quantidade executada, estado do marco, estimativa) e o critério devolve o real. O registro de medições, o estorno e a importação do avanço são da ISSUE-037; revisões e desdobramentos, da ISSUE-038.

**Tela:** `planejamento/eap` (view `app/_views/planejamento/eap.html`, fragmentos `api/src/templates/planejamento/eap_conteudo.html` e `eap_dicionario.html`). Indicadores: avanço físico real (ou ponderado, na carteira) com previsto e desvio, pacotes de trabalho com a linha de base da revisão vigente, e término vencido. Filtros: busca, nível, critério de medição e situação (desvio fora da faixa, término vencido, planejamento); os indicadores contam a árvore inteira, o filtro só mexe na tabela. Abaixo da árvore ficam as revisões da EAP e os desdobramentos da revisão vigente. O **dicionário** do pacote (ícone da linha) traz tipo, critério, peso, linha de base, previsto, real e desvio, entregável, critério de aceitação, empresa, responsável, item da EAC ligado, as etapas e o histórico das medições; é somente leitura. No Portfólio a árvore é somente leitura: linha 0 = portfólio, nível 1 = projeto (peso na carteira, vindo da ponderação da EAC) e nível 2 = pacotes principais (peso na carteira e no projeto), com "Abrir" para a EAP do projeto, sem dicionário nem desdobramentos, e a coluna Projeto nas exportações.

**Rotas** (`eap_routes.py`, blueprint próprio registrado em `function_app.py`, prefixo `/api/planejamento/eap`): `GET` tela; `GET /pacotes/{item_id}/dicionario`; `GET /excel` e `GET /imprimivel` (Excel e PDF pelos mecanismos genéricos, mesmos filtros, três tabelas: estrutura, revisões e desdobramentos).

| Termo de negócio | Definição | Nome no código |
|---|---|---|
| Avanço do pacote | Real pelo critério: Etapas (soma dos pesos x % concluído), Unidades (executado ÷ quantidade, até 100), Marco 0/100, Marco 50/50 e Percentual estimado; pacote de planejamento fica em 0; resultado limitado a 0 a 100, duas casas | `eap_calculations.package_progress` |
| Real a partir da medição | O % acumulado da última medição vira as entradas do critério e o critério dá o real; sem medição, 0 | `package_state`, `progress_from_measurement`, `entries_from_percent` |
| Desvio físico | Real menos previsto, em p.p., uma casa | `deviation_pp` |
| Faixa do desvio | Verde até -2 p.p., atenção até -5 p.p. e fora da faixa abaixo disso (parâmetros `eap.faixasDesvioPP`; no limite vale a faixa melhor) | `deviation_band` |
| Término vencido | Pacote de trabalho com término da linha de base antes da data de referência (o próprio dia não vence) e real abaixo de 100 | `package_is_overdue` |
| Regra dos 100% | Os pesos dos pacotes somam exatamente 100 | `weights_close_at_100` |
| Média ponderada | Previsto e real das áreas, subáreas, projeto e carteira, ponderados pelo peso, duas casas | `weighted_average` |
| Árvore do projeto | Linha 0, áreas, subáreas e pacotes por código, com pesos somados e peso no nível acima | `build_project_tree` |
| Árvore da carteira | Projeto (peso da ponderação) e pacotes principais (peso da área x peso do projeto) | `build_portfolio_tree` |
| Indicadores | Avanço, pacotes de trabalho e de planejamento, áreas, subáreas, vencidos e fora da faixa | `summarize`, `portfolio_behind_count` |
| Filtro da árvore | Busca (sem acento e caixa), nível, critério e situação, com os ancestrais dos achados | `filter_tree`, `parent_codes` |
| Pacotes da revisão | Pacotes com peso congelado maior que zero na revisão | `revision_package_count` |
| Arredondamento | Como o `Math.round` do protótipo: a metade vai para cima | `round_places` |

**Fluxos e onde mexer:** a fachada é `eap_service.py` (`eap_view`, `package_dictionary`); a gravação passa por ela com a trilha (`create_item`, `add_stages`, `add_measurement`, `create_revision`, `add_split`), e a ISSUE-037 registra a medição por `add_measurement` e a ISSUE-038 as revisões por `create_revision`. Os cálculos puros estão em `eap_calculations.py` (recebem a data de referência), a exportação em `eap_export.py`. A SM de cada revisão é lida pela fachada da Governança (`change_codes`). **Carga:** `eap_seed.py` grava a árvore do protótipo (`eap`: 110 itens, 38 pacotes no projeto 1), as etapas, as medições (as 3 do protótipo e, para o pacote com avanço e sem medição, uma de zero ao avanço, datada na referência), as revisões (os pesos congelados só na vigente de cada projeto, o do protótipo não guardava os anteriores) e o desdobramento 5.2.1 > 5.2.2, com as datas deslocadas e só no modo demonstração. **Migração:** `m036_eap_arvore` (`eap_item`, `eap_item_etapa`, `eap_medicao`, `eap_revisao`, `eap_revisao_item`, `eap_desdobramento`). **Oráculo:** `api/tests/oraculo/test_oraculo_eap.py`. **Testes:** `api/tests/planejamento/test_eap_*.py`, com o apoio em `api/tests/apoio_eap.py`.

## Trios das telas

Cada tela da lista de navegação (`api/src/core/navegacao.json`) tem um trio com o mesmo nome: a view, o estilo e o comportamento da página. O CSS é escopado pela classe raiz da view (`.pagina--<modulo>-<tela>`, com o `_` do identificador mantido), o JS registra `TN.paginas["<modulo>/<tela>"]` e o shell (`app/index.html`) vincula o CSS e o JS de todos. A verificação `trio-da-tela` confere o conjunto. Convenção completa em `docs/PADROES-DE-PAGINA.md`, seção "O trio da tela".

| Tela | View | CSS | JS |
|---|---|---|---|
| EAP | `app/_views/planejamento/eap.html` | `app/paginas/planejamento/eap.css` | `app/paginas/planejamento/eap.js` |
| Curva S | `app/_views/planejamento/curva_s.html` | `app/paginas/planejamento/curva_s.css` | `app/paginas/planejamento/curva_s.js` |
| KPIs | `app/_views/planejamento/kpis.html` | `app/paginas/planejamento/kpis.css` | `app/paginas/planejamento/kpis.js` |
| Relato do período | `app/_views/planejamento/relato.html` | `app/paginas/planejamento/relato.css` | `app/paginas/planejamento/relato.js` |
| 6WLA | `app/_views/planejamento/6wla.html` | `app/paginas/planejamento/6wla.css` | `app/paginas/planejamento/6wla.js` |
| Produtividade | `app/_views/planejamento/produtividade.html` | `app/paginas/planejamento/produtividade.css` | `app/paginas/planejamento/produtividade.js` |
| Punch list | `app/_views/planejamento/punch_list.html` | `app/paginas/planejamento/punch_list.css` | `app/paginas/planejamento/punch_list.js` |

## Rotas previstas

Prefixo: `/api/planejamento/`.

| Grupo previsto | Uso | Issue |
|---|---|---|
| `eap` | Árvore, dicionário, revisões, pacotes e medições | ISSUE-036 a ISSUE-038 |
| `curva-fisica` e `kpis` | Séries e indicadores físicos | ISSUE-039, ISSUE-040 |
| `relatos`, `6wla` | Relatos de período, lookahead e restrições | ISSUE-044, ISSUE-045 |
| `produtividade` | Plano de quantidades, horas efetivas e desempenho | ISSUE-046 a ISSUE-048 |
| `punch-list` | Itens, transições, consultas e painel | ISSUE-049, ISSUE-050 |

Os grupos são planejamento; cada issue fixa métodos e paths concretos conforme D14.

## Fórmulas e nomes no código

| Termo de negócio | Definição | Nome previsto |
|---|---|---|
| Avanço do pacote | Progresso calculado pelas entradas do critério de medição do pacote | `calculations.package_progress` |
| Avanço da EAP | Soma ponderada do real dos pacotes pela linha de base vigente | `calculations.weighted_wbs_progress` |
| SPI físico | Avanço real dividido pelo avanço previsto no corte | `calculations.physical_schedule_index` |

O avanço físico real vem somente das medições da EAP (D6). Uma fórmula que usa data recebe o corte/data de referência como argumento.

## Fluxos

Rev 0 da EAP é a linha de base. Alterações estruturais e de peso entram em revisão ligada a SM aprovada; medição segue o critério do pacote e não permite regressão sem estorno justificado por Gestor. A punch list segue Aberto → Em tratamento → Aguardando verificação → Fechado; verificação reprovada volta a Em tratamento e Cancelado exige justificativa.

## Integrações

Lê a SM aprovada de Governança para revisões da EAP. O avanço da EAP alimenta Curva S, KPIs, Início e relatório. Itens de punch list criam ações na Central e podem bloquear marcos por item A. Referências de custo usam a EAC do Financeiro, sem leitura direta das tabelas alheias.

## Parâmetros

Incluem critérios/modelos de medição e faixas de desvio da EAP, faixas de produtividade e janelas de cálculo, e limites de aging da punch list (7 e 30 dias inicialmente). A edição versionada pertence a Configurações; os detalhes entram nas ISSUE-036 a ISSUE-050 e ISSUE-076.

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas | `routes.py`; Punch list em `punch_routes.py` |
| Fluxo, permissões e integrações | `service.py`; Punch list em `punch_service.py` |
| Medições, avanço e indicadores | `calculations.py`; Punch list em `punch_calculations.py` |
| Validações | `validation.py`; Punch list em `punch_validation.py` |
| Exportação | `export.py`; Punch list em `punch_export.py` |
| Persistência | `models.py`; entidades em `docs/MODELO-DE-DADOS.md` |
| Fragmentos | `api/src/templates/planejamento/` |
| Tela, estilo e comportamento | `app/_views/planejamento/` e `app/paginas/planejamento/` |
| Testes | `api/tests/planejamento/` |

Todos os arquivos Python são stubs intencionais na ISSUE-002. As ISSUE-036 a ISSUE-050 completam este documento e acrescentam testes das regras.

## Relato do período (ISSUE-044, HU-046)

**Tela** `relato` (trio `relato.html`, `relato.css`, `relato.js`): KPIs (semana anterior e mês anterior registrados ou pendentes, pontos de atenção do último semanal contra o anterior, relatos registrados), filtro Todos, Semanais e Mensais, busca, tabela e os modais Novo, Editar, Ver, Copiar do período anterior e Excluir. Fragmentos em `api/src/templates/planejamento/relato_*.html`. O botão Análise do período chega na ISSUE-081.

**Rotas** (prefixo `/api/planejamento/relatos`, em `routes.py`): `GET` painel (`tipo`, `busca`); `GET ver?id=`; `GET abrir?tipo=&periodo=` (endereço do modal do relatório gerencial: abre o relato do período ou o formulário); `GET|POST formulario` (redesenha com o digitado; `acao=adicionar-ponto` e `remover-ponto&indice=`); `POST copiar`; `POST gravar` (Membro; 422 por campo, 409 versão vencida); `POST excluir` (Gestor); `GET excel` e `GET imprimivel` (indicadores e as tabelas da lista, no Portfólio com a coluna Projeto).

**Regras e nomes no código**

| Termo de negócio | Definição | Nome no código |
|---|---|---|
| Faixa de períodos do relato | Do período do início do projeto ao corrente (sem início, o corrente) | `calculations.report_period_range` |
| Recusa de período | Futuro, anterior ao início ou malformado, com a mensagem | `calculations.report_period_error` |
| Relatos devidos | Períodos fechados desde o início (o corrente não é devido) | `calculations.expected_report_count` |
| Período anterior | Último período fechado antes da data de referência | `calculations.previous_period` |
| Relato a copiar | O mais recente do mesmo tipo antes do período (não precisa ser o vizinho) | `calculations.latest_period_before` |
| Opções do formulário | Períodos do mais recente ao mais antigo, com corrente e já relatados marcados | `calculations.period_options` |
| Deslocamento da carga | Períodos inteiros entre a âncora do protótipo e a data da carga | `calculations.shift_period` |
| Limites | 20 linhas de 300 caracteres, ao menos uma; até 12 pontos, de 10 a 400 caracteres | `validation.validate_activities`, `validation.validate_points` |
| Gravação, duplicidade e cópia | Um registro por projeto, tipo e período; tipo e período não mudam | `service.save_report`, `service.previous_report` |

**Fluxos.** Novo: o tipo escolhe as opções de período; gravar valida tudo e devolve 422 por campo. Copiar traz o próximo período do relato anterior como atividades do período e os pontos para revisão, sem gravar. Excluir devolve o período a pendente. Toda gravação passa por `service.py`, com trilha e versão. O risco do ponto de atenção é leitura do planejamento, sem vínculo com o registro de Riscos (05).

**Carga:** `seed_relato.py` grava os 9 relatos dos mocks pela fachada (`service.insert_report`), com os períodos deslocados em períodos inteiros e só no modo demonstração. **Migração:** `m044_relato_do_periodo` (`relato`, `relato_atividade`, `relato_ponto`). **Testes:** `api/tests/planejamento/test_relato_*.py` (cálculos, fachada, rotas e oráculo).
