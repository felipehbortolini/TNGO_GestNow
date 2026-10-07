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

## EAP (ISSUE-036)

**Tela** `eap` (trio `eap.html`, `eap.css`, `eap.js`): KPIs (avanço físico real com o desvio, pacotes de trabalho com a linha de base, término vencido e SMs a incorporar), árvore de áreas, subáreas e pacotes com recuo e recolhimento, revisões e desdobramentos da revisão vigente. O dicionário e o registro do avanço do pacote abrem no alvo `eap-formulario` (pelos links do fragmento); o dicionário traz descrição, entregável, critério de aceitação, empresa executante, responsável, item da EAC e o histórico de medições; peso, datas e critério são da linha de base e não se editam aqui. No Portfólio a árvore é somente leitura, com a coluna Projeto, e os desdobramentos não entram — cada projeto tem a sua revisão vigente. Excel e PDF saem pelos mecanismos genéricos (`data-tn-excel` e `data-tn-pdf`, com o escopo da tela).

**Rotas** (prefixo `/api/planejamento/eap`, em `routes.py`): `GET` tela (KPIs, árvore, revisões e desdobramentos); `GET /itens/{item_id}/dicionario`; `POST /itens/{item_id}/dicionario` (Membro; 422 por campo e 409 de versão vencida devolvem o conteúdo atualizado e o formulário preenchido na resposta multi-alvo `eap-conteudo` + `eap-formulario`; 403 no Portfólio e abaixo de Membro); `GET /excel` e `GET /imprimivel`.

**Regras e nomes no código**

| Termo de negócio | Definição | Nome no código |
|---|---|---|
| Avanço do pacote | Pelo critério de medição: Etapas, Unidades, Marco 0/100, Marco 50/50 e Percentual estimado, entre 0 e 100 | `calculations.eap_package_progress` (`_steps_progress`, `_units_progress`, `_milestone_half_progress`) |
| Regra dos 100% | O peso do nó é a soma dos filhos; áreas, subáreas e a linha 0 são somadas no servidor | `calculations.eap_node_totals`, `eap_root_totals` |
| Média ponderada | O previsto e o real do nó ponderam os filhos pelo peso | `calculations.eap_weighted_progress` |
| Desvio físico | Real menos previsto, em pontos percentuais | `calculations.eap_deviation_pp` |
| Faixas do desvio | `success` até −2 p.p., `warning` até −5 p.p., `danger` daí para baixo (parâmetros `faixasDesvioPP`) | `calculations.eap_deviation_band` |
| Pacote vencido | De trabalho, término anterior à referência e real abaixo de 100 | `calculations.eap_package_overdue` |
| Pacote não iniciado | De trabalho, já deveria ter começado e real em zero | `calculations.eap_package_not_started` |
| Situação do pacote | `Vencido`, `Não iniciado` ou `Em andamento`; o de planejamento é `Planejamento` e não mede | `export.eap_situation_text`, `export.eap_situation_tone` |
| Árvore do escopo | Projeto (editável) ou carteira somente leitura, com a linha 0, as áreas e o peso na carteira | `service.eap_overview`, `_project_overview`, `_portfolio_overview` |
| Dicionário | Descrição, entregável, aceitação, empresa, responsável e item da EAC; a linha de base não muda | `service.update_dictionary`, `service.dictionary_fields` |
| Revisões e desdobramentos | Revisões com a contagem congelada de pacotes e os desdobramentos da vigente | `service._revisions`, `service._breakdowns` |
| SMs a incorporar | Aprovadas com impacto em escopo que nenhuma revisão incorporou | `service._pending_changes` |

**Fluxos.** Rev 0 é a linha de base; estrutura e pesos só mudam por nova revisão, a partir de SM aprovada com impacto em escopo (ISSUE-038), e o desdobramento tira peso do pacote de planejamento sem mudar o total. O dicionário grava pela fachada (`service.update_dictionary`), com trilha e versão. **Carga:** a parte `planejamento-eap` de `seed.py` grava a árvore, as etapas, as revisões e o desdobramento 5.2.1 > 5.2.2 do mock, com as datas deslocadas; a parte `planejamento-curva` (ISSUE-039) grava a linha de base congelada do mock e as medições proporcionais que fecham a série real da Curva S. **Migração:** `m036_eap_arvore_e_dicionario`. **Testes:** `api/tests/planejamento/test_eap_calculos.py`, `test_eap_validacao.py`, `test_eap_servico.py` e `test_eap_rotas.py`.

O registro de medições, o estorno e a importação do avanço entraram na ISSUE-037 e as novas revisões, o desdobramento e a importação de pacotes, na ISSUE-038 (ver as seções seguintes). A tela não traz os filtros do protótipo (busca, nível, critério e situação).

## Medição do avanço (ISSUE-037)

**Tela** `eap` (mesmo trio): cada pacote de trabalho da árvore ganha a ação **Registrar avanço**, que abre o formulário no alvo `eap-formulario` com as entradas do critério (o % de cada etapa, a quantidade executada, a situação do marco ou o percentual estimado), a data da medição, a observação e a justificativa do estorno. O botão **Importar avanço** do cabeçalho só aparece no projeto editável (marcador `data-pode-editar`) e abre o formulário do importador `eap-avanco` no modal do Design System; a conferência e a confirmação atualizam a árvore no próprio pedido (resposta multi-alvo `eap-conteudo` + resultado). O histórico de medições continua no dicionário do pacote. No Portfólio não há ação de medição.

**Rotas** (prefixo `/api/planejamento/eap`, em `routes.py`): `GET /itens/{item_id}/avanco` (formulário do critério); `POST /itens/{item_id}/avanco` (Membro; 422 por campo, 403 do estorno sem Gestor e 409 de versão vencida devolvem o conteúdo atualizado e o formulário preenchido na resposta multi-alvo `eap-conteudo` + `eap-formulario`); `GET /importar/formulario` (data da medição e planilha), `POST /importar/conferir` (mostra cada linha, não grava nada) e `POST /importar/confirmar` (grava só as linhas sem erro, datadas com a data do formulário, e responde o resultado com a EAP atualizada).

**Regras e nomes no código**

| Termo de negócio | Definição | Nome no código |
|---|---|---|
| Entradas do critério | O % de cada etapa, o executado acumulado, a situação do marco ou o % estimado; o real é sempre calculado, nunca digitado | `validation.parse_progress_form` |
| Medição | Fato imutável com data, de/para, autor e observação; o real acumulado não regride | `service.register_progress`, `_record_measurement` |
| Estorno | Medição abaixo do real corrente: exige papel Gestor (403) e justificativa de 10 a 300 caracteres (422); a justificativa viaja na observação | `validation._require_reversal_terms` |
| Limite da linha de base | O executado não passa a quantidade da linha de base; exige SM e revisão | `validation._executed_error` |
| Estimado restrito | Percentual estimado só vale para pacote de até o peso máximo do parâmetro do grupo `eap` (`estimadoMaximoPct`, inicial 5%) | `validation._estimated_input` |
| Importação do avanço | Linha a linha: pacote inexistente, pacote de planejamento, marco fora dos degraus, executado acima da linha de base e regressão são recusados com o motivo; a linha sem mudança vira aviso | `importers.progress_importer`, `validation.parse_import_rows`, `service.import_progress` |

**Fluxos.** Registrar avanço grava as entradas do critério no item e nas etapas (com trilha e versão) e cria a medição; o 422 marca o campo, o 403 do estorno e o 409 de versão vencida devolvem o formulário preenchido com o digitado no mesmo pedido. A importação usa o fluxo genérico (formulário → conferir → confirmar), recusa as linhas inválidas com o motivo e **nunca estorna**: estorno só pela tela, com justificativa. **Testes:** `api/tests/planejamento/test_eap_medicao_calculos.py`, `test_eap_medicao_validacao.py`, `test_eap_medicao_servico.py` e `test_eap_medicao_rotas.py`.

## Revisões e desdobramento (ISSUE-038)

**Tela** `eap` (mesmo trio): o cabeçalho ganha **Novo pacote** (só no projeto editável, marcador `data-pode-editar`), **Nova revisão** e **Importar pacotes** (só para quem gere, marcador `data-pode-gerir`), todos no modal do Design System e escondidos no vazio de origem. O formulário do pacote novo escolhe a origem do peso — desdobramento de um pacote de planejamento (o total não muda) ou inclusão por nova revisão a partir de SM aprovada com impacto em escopo —; o da revisão ajusta peso, quantidade (só no critério Unidades) e término de um pacote existente. Os dois reescalam os demais pesos pelo maior resto e voltam com o 422 por campo, o 403 sem papel Gestor e o 409 de versão no próprio formulário; a árvore, as revisões e os desdobramentos vêm no `eap-conteudo` da resposta. A importação de pacotes segue o fluxo formulário → conferir → confirmar (importador `eap-pacotes`), cria a revisão vinculada à SM só na confirmação e responde o resultado com a EAP atualizada.

**Rotas** (prefixo `/api/planejamento/eap`, em `routes.py`): `GET /pacotes/novo` (`?recurso=desdobramento|revisao`) e `POST /pacotes` (desdobramento: Membro; revisão: Gestor; resposta multi-alvo `eap-formulario` + `eap-conteudo`); `GET /revisoes/nova` e `POST /revisoes` (Gestor; reescala os pesos e marca a SM na Governança); `GET /pacotes/importar/formulario`, `POST /pacotes/importar/conferir` (prévia linha a linha, nada gravado) e `POST /pacotes/importar/confirmar` (cria a revisão da SM com os pacotes das linhas sem erro).

**Regras e nomes no código**

| Termo de negócio | Definição | Nome no código |
|---|---|---|
| Maior resto | Os pesos livres são reescalados para fechar 100%: cada um fica com o piso da proporção e a sobra de um centésimo vai aos maiores restos (empate na ordem de entrada); sem peso na entrada, todas as chaves saem zeradas | `calculations.eap_rescale_weights` |
| Previsto do pacote novo | Distribuição linear da linha de base: 0 até o início, 100 a partir do término e, no meio, os dias corridos sobre o prazo, com 1 casa | `calculations.eap_linear_predicted` |
| Peso máximo do pacote | O do parâmetro do grupo `eap` (`pesoMaximoPacotePct`, inicial 10%); a soma dos pesos fixados (ajustes + pacotes novos) não pode passar de 100% | `validation.revision_fixed_weight_error`, `validation.hundred_rule_error` |
| Revisão | Ajusta os pacotes afetados, inclui os novos, congela o peso de todos os pacotes de nível 3 e marca a SM na Governança, tudo na mesma transação; exige SM aprovada com impacto em escopo ainda não incorporada | `service.create_revision`, `_revision_source`, `_apply_adjustments`, `_rescale_free_weights`, `_freeze_revision` |
| Desdobramento | Tira o peso da origem para o pacote novo, mantém o previsto e, com peso zero, encerra o pacote de planejamento (peso 0; sai da árvore, mas continua legível nos desdobramentos) | `service.breakdown_package`, `service._is_closed_package` |
| Importação de pacotes | Linha a linha valida código, subárea, existência, critério, modelo, unidade, quantidade, peso, datas e item da EAC; a confirmação cria a revisão com as linhas sem erro e devolve as demais com o motivo | `importers.packages_importer`, `importers.revision_packages` |
| SMs a incorporar | Aprovadas com impacto em escopo que nenhuma revisão incorporou (KPI da tela) | `service._pending_changes`, `governanca.eap_revision_sources` |

**Fluxos.** A revisão só existe a partir de SM aprovada com impacto em escopo; `governanca.incorporate_eap_revision` grava `eap_revisao_incorporada` na SM e o indicador "SMs a incorporar" cai. O desdobramento não cria revisão (pede Membro, como o dicionário) e o código da planilha é preservado na importação. O encerramento da SM exige a incorporação (Governança). **Testes:** `api/tests/planejamento/test_eap_revisao_calculos.py`, `test_eap_revisao_validacao.py`, `test_eap_revisao_servico.py` e `test_eap_revisao_rotas.py`.

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
| Rotas | `routes.py` |
| Fluxo, permissões e integrações | `service.py` |
| Medições, avanço e indicadores | `calculations.py` |
| Validações | `validation.py` |
| Exportação | `export.py` |
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
