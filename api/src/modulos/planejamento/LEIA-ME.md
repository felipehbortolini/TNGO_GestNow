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

## Curva S física (ISSUE-039)

**Tela** `curva_s` (trio `curva_s.html`, `curva_s.css`, `curva_s.js`): a faixa de KPIs (previsto acumulado com a referência "100% em <mês da linha de base>", real acumulado com o avanço do mês, desvio em p.p., SPI com o do mês anterior e término pela tendência contra a linha de base), o gráfico da Curva S Linha da biblioteca do Design System com o drill de ano, mês e semana, a tabela período a período (previsto e real do mês e acumulados, tendência e desvio, com o mês do corte destacado) e, no Portfólio, a composição da carteira (peso, previsto, real, desvio, SPI, contribuição para o desvio ponderado e término pela tendência). O fragmento `curva_fisica.html` entra no alvo `curva-fisica-conteudo`; a tela é só de leitura — a curva muda pelas medições da EAP e pelas revisões, sem nenhum passo de recálculo. Excel e PDF saem pelos mecanismos genéricos (`data-tn-excel` e `data-tn-pdf`), com os indicadores, o gráfico, a tabela e a composição (a coluna Projeto incluída pelo mecanismo no Portfólio).

**Rotas** (prefixo `/api/planejamento/curva-fisica`, em `routes.py`): `GET` (fragmento no alvo `curva-fisica-conteudo`; projeto ou Portfólio no mesmo endereço); `GET /excel` e `GET /imprimivel` (o mesmo documento pelos mecanismos genéricos).

**Regras e nomes no código**

| Termo de negócio | Definição | Nome no código |
|---|---|---|
| Calendário da curva e corte | Meses do início mais antigo ao término mais novo dos pacotes com peso e datas; o corte é o mês da referência (o último mês, se a referência passa do término; não existe antes do início) | `calculations.curva_fisica_months` |
| Linha de base congelada | Previsto acumulado de cada mês da revisão: soma ponderada do previsto linear dos pacotes, com 1 casa; congelado por revisão da EAP, nunca recalculado | `calculations.curva_fisica_baseline`, `service.freeze_curve`, tabelas `curva_fisica_revisao` e `curva_fisica_mes` |
| Real das medições | Acumulado de cada mês: soma ponderada da última medição até a data do mês (a referência no mês corrente, o fim do mês nos demais); mês depois do corte sai vazio. Uma medição nova muda a curva na consulta seguinte | `calculations.curva_fisica_real`, `service._frozen_packages` |
| Tendência pela regra do protótipo | Arranca no real do corte e segue o ritmo da linha de base: real do corte mais o avanço da base desde o corte, com teto de 100; sem corte ou sem real no corte, não existe | `calculations.curva_fisica_trend` |
| Curva do Portfólio | Média ponderada das curvas pelos pesos da carteira, no calendário da união dos meses (D8); antes do início o projeto vale 0, depois do término 100 na linha de base e o último real; o corte é o maior e o peso é renormalizado pelos projetos presentes | `calculations.curva_fisica_portfolio`, `financeiro.portfolio_weights` |
| Composição da carteira | Linha por projeto com peso, previsto, real, desvio, SPI, contribuição para o desvio ponderado e término pela tendência, no corte do próprio projeto | `service.CurvaFisicaComposition`, `service._curve_composition` |
| Indicadores da faixa | Previsto, real, desvio, SPI (com o do mês anterior) e término pela tendência | `service._curve_indicators`, `export.curva_fisica_kpis` |
| Gráfico em semanas | Semanas ISO com a linha de base interpolada dentro do mês, o real até a referência e a tendência, no contrato da Curva S Linha (D11) | `service._curve_chart` |

**Fluxos.** A leitura (`service.curva_fisica_overview`) pega a curva vigente de cada projeto — a da maior revisão da EAP — e compõe real e tendência na hora; no Portfólio, pondera as curvas pelos pesos da carteira. O congelamento da base é o gancho `service.freeze_curve` dentro do `create_revision` (ISSUE-038), na mesma transação da revisão: os pacotes de nível 3 saem dos pesos congelados da revisão (`eap_revisao_item`) com as datas do item, e a base da revisão anterior não muda. **Carga:** a parte `planejamento-curva` de `seed.py` (`load_curva`) congela a linha de base do mock convertido em cada revisão da EAP semeada e grava as medições mensais proporcionais à série real do mock — a distribuição linear das datas daria outro número (69,2% contra 65,7%; ver `docs/DIVERGENCIAS-DO-PROTOTIPO.md`). **Migração:** `m037_curva_s_fisica`. **Oráculo:** `api/tests/plataforma/test_carga_demonstracao.py` afirma o previsto de 65,7% e o real de 61,8% em set/26 e compara a série inteira com o mock. **Testes:** `api/tests/planejamento/test_curva_fisica_calculos.py`, `test_curva_fisica_servico.py` e `test_curva_fisica_rotas.py`.

**Onde mexer:** cálculos em `calculations.py` (`curva_fisica_*`); congelamento e leitura em `service.py` (`freeze_curve`, `curva_fisica_overview`); rotas em `routes.py` (bloco Curva S física); exportação em `export.py` (`curva_fisica_document` e `curva_fisica_kpis`); fragmento em `api/src/templates/planejamento/curva_fisica.html`; trio em `app/_views/planejamento/curva_s.html` e `app/paginas/planejamento/curva_s.css`/`js`; carga em `seed.load_curva`; migração `api/migrations/versions/m037_curva_s_fisica.py`; testes em `api/tests/planejamento/test_curva_fisica_*.py` e o oráculo na carga.

## KPIs de planejamento (ISSUE-040)

**Tela** `kpis` (trio `kpis.html`, `kpis.css`, `kpis.js`): a faixa de indicadores (SPI do projeto — ou ponderado da carteira — com a meta de 1,00 e o do mês anterior, previsto x real com o acumulado no corte, desvio acumulado em p.p., o maior desvio por área ou projeto contra o limite da faixa, pacotes com término vencido e SMs a incorporar), os gráficos SPI por mês (linhas múltiplas, com a meta 1,00) e previsto x real por área (comparativo de barras), e a tabela de avanço por área com peso, previsto, real, desvio, SPI e contribuição, fechando no rodapé ponderado que bate com a Curva S. No Portfólio as linhas, o desvio e o gráfico são os projetos, com o peso da carteira, e a tabela ganha a coluna Projeto. O fragmento `kpis.html` entra no alvo `kpis-conteudo`; a tela é só de leitura — o avanço por área vem da EAP (D6), sem botão de atualização — e o botão Análise do período abriu na ISSUE-081: ele abre o modal do módulo `relatorio` (`/api/relatorio/analise/...`). Excel e PDF saem pelos mecanismos genéricos (`data-tn-excel` e `data-tn-pdf`), com os indicadores, os gráficos e a tabela.

**Rotas** (prefixo `/api/planejamento/kpis`, em `routes.py`): `GET` (fragmento no alvo `kpis-conteudo`; projeto ou Portfólio no mesmo endereço); `GET /excel` e `GET /imprimivel` (o mesmo documento pelos mecanismos genéricos).

**Regras e nomes no código**

| Termo de negócio | Definição | Nome no código |
|---|---|---|
| SPI físico | Real acumulado dividido pelo previsto acumulado no corte, com 2 casas; sem previsto (zero ou ausente) não há índice | `calculations.spi_index` |
| SPI por mês | O índice de cada mês até o último com real; os meses seguintes não entram na série | `calculations.spi_series` |
| Contribuição da área | Peso vezes real dividido por 100, em p.p., com 1 casa | `calculations.area_contribution` |
| Avanço por área | As áreas de nível 1 da EAP, lidas como a árvore as lê: a média ponderada dos pacotes fecha com a Curva S (D6) | `service._area_kpi_rows`, `service._area_kpi_row` |
| Avanço por projeto | Na carteira, os projetos da composição da Curva S, com o peso da carteira e o corte do próprio projeto | `service._portfolio_kpi_rows` |
| Indicadores da EAP | Pacotes de trabalho com término vencido e SMs aprovadas com impacto em escopo ainda não incorporadas | `service._kpi_eap`, `service._pending_change_count` |
| Maior desvio | A linha de maior atraso em p.p. entre as que têm previsto, com o limite vindo das faixas de desvio da EAP | `service._worst_row`, `calculations.eap_deviation_band` |
| Visão do escopo | A curva da ISSUE-039, o SPI por mês, as linhas, o pior desvio e os dois gráficos | `service.planning_kpis_overview` |

**Fluxos.** A leitura reaproveita a `curva_fisica_overview` — a revisão vigente no projeto, a média ponderada pelos pesos da carteira no Portfólio — e a árvore da EAP; nada nesta tela grava. O fragmento não desenha SVG nem traz `<script>`: entrega o `data-dados` dos dois gráficos no contrato da biblioteca do Design System (D11). **Oráculo:** `api/tests/plataforma/test_carga_demonstracao.py` afirma, com a mesma data deslocada da Curva S, o SPI de 0,94, o previsto de 65,7% e o real de 61,8% do projeto 1, as áreas da EAP contra o mock de `avancoAreas` (a soma ponderada fecha com a curva) e a carteira com uma linha por projeto e peso. **Testes:** `api/tests/planejamento/test_kpis_servico.py` e `test_kpis_rotas.py`.

**Onde mexer:** cálculos em `calculations.py` (`spi_index`, `spi_series`, `area_contribution`); leitura em `service.py` (`planning_kpis_overview`, `_kpi_rows`, `_kpi_eap`, `_pending_change_count`, `_spi_chart`, `_comparison_chart`); rotas em `routes.py` (bloco KPIs de planejamento); exportação em `export.py` (`planning_kpis_document`, `planning_kpis`); fragmento em `api/src/templates/planejamento/kpis.html`; trio em `app/_views/planejamento/kpis.html` e `app/paginas/planejamento/kpis.css`/`js`; testes em `api/tests/planejamento/test_kpis_servico.py` e `test_kpis_rotas.py` e o oráculo na carga.

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

**Tela** `relato` (trio `relato.html`, `relato.css`, `relato.js`): KPIs (semana anterior e mês anterior registrados ou pendentes, pontos de atenção do último semanal contra o anterior, relatos registrados), filtro Todos, Semanais e Mensais, busca, tabela e os modais Novo, Editar, Ver, Copiar do período anterior e Excluir. Fragmentos em `api/src/templates/planejamento/relato_*.html`. O botão Análise do período abriu na ISSUE-081: ele abre o modal do módulo `relatorio` (`/api/relatorio/analise/...`).

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

## Produtividade: quantidades, LB e apontamento (ISSUE-046, HU-065)

**Tela** `produtividade` (trio `produtividade.html`, `produtividade.css`, `produtividade.js`): filtros globais Empresa, Semana de corte e Grupo na toolbar, com os botões Apontar semana, Novo item da LB e Importar Excel; a aba **Quantidades** traz o aviso dos itens com LB em elaboração, os indicadores (avanço por quantidades com SPI, aderência da semana, fator de produtividade, apontamentos pendentes e tendência de atraso), as quantidades por grupo, os gráficos Produção semanal e Avanço acumulado (D11, com drill por período) e a tabela Plano x realizado por item. A aba Horas efetivas chegou na ISSUE-047 (ver a seção dela abaixo); a de KPIs de performance chega na ISSUE-048. No Portfólio a tabela e as exportações trazem a coluna Projeto e a inclusão pede o projeto antes (`data-tn-incluir`). Fragmentos em `api/src/templates/planejamento/produtividade_*.html` e os parciais `_prod_*.html`; os modais (ficha, formulário, revisão e apontamento) usam o alvo `produtividade-modal`.

**Rotas** (prefixo `/api/planejamento/produtividade`, em `routes.py`): `GET` tela (`empresa`, `corte`, `grupo`); `GET /excel` e `GET /imprimivel` (indicadores, gráficos e as duas tabelas, com o filtro de agora); `GET /itens/novo`, `GET /itens/{id}`, `GET /itens/{id}/editar`, `GET /itens/{id}/revisao`, `GET /apontamento` (modais); `POST /itens` e `POST /itens/{id}` (criar/editar; resposta multi-alvo com modal, filtros e conteúdo; 422 por campo, 409 de versão vencida); `POST /itens/formulario` e `POST /itens/{id}/revisao/formulario` (recalculam a grade da distribuição); `POST /itens/{id}/aprovacao` (Gestor; quem elaborou recebe 403); `POST /itens/{id}/exclusao`; `POST /itens/{id}/revisoes` (SM aprovada obrigatória); `POST /apontamento` (upsert por item e semana; `?acao=recarregar` redesenha a grade). A importação usa o fluxo genérico (ISSUE-018) com a chave `produtividade-itens`.

**Regras e nomes no código**

| Termo de negócio | Definição | Nome no código |
|---|---|---|
| Distribuição pelo perfil | O total vira previsto semanal pelo perfil (Curva S 20/60/20, linear, início, fim) | `calculations.profile_weights`, `s_curve_20_60_20`, `distribute_total` |
| Maior resto | A soma das semanas fecha com o total na menor unidade inteira (as casas da unidade) | `calculations.distribute_total`, `round_quantity`, `item_tolerance` |
| Casas da unidade | Tonelada guarda uma casa; as demais, nenhuma | `calculations.places_for_unit` |
| Código do item | Próximo `QTD-NN` do projeto (o prefixo vem do primeiro item) | `calculations.next_item_code` |
| Indicadores do item | Previsto e realizado acumulados, aderência da semana, FP, saldo e tendência de término (earned schedule) | `calculations.item_figures` |
| Ficha por semana | Previsto, realizado, HH, aderência, FP e acumulados de cada semana | `calculations.item_weeks` |
| Indicadores da aba | Avanço, SPI de quantidades, FP, aderências, pendentes e atraso, somando horas ganhas | `calculations.quantities_indicators` |
| Resumo por grupo | Cada grupo aprovado somado na sua unidade | `calculations.group_summaries` |
| Série semanal | Previsto e realizado por semana em quantidade ou horas ganhas; futura é nula | `calculations.quantities_series`, `weekly_chart`, `accumulated_chart` |
| Revisão da LB | As semanas até a corrente ficam congeladas; o saldo (novo total menos o congelado) é redistribuído pelo perfil | `calculations.revision_distribution`, `frozen_planned`, `first_free_week` |
| Faixa do indicador | `success`, `warning` ou `danger` pelas faixas dos parâmetros, no sentido bom de cada um | `calculations.indicator_band` |
| Limites do apontamento | Semana futura recusada; HH obrigatórias quando há realizado; acumulado acima da LB recusado | `validation.parse_entries`, `calculations.entry_over_limit` |
| Ciclo da LB | Em elaboração (fora dos indicadores) → Aprovada (congelada, D5b); revisão só com SM aprovada | `service.save_item`, `approve_item`, `revise_item` |
| Segregação de funções | Quem elaborou a distribuição (a revisão 0, `por_id`) não aprova | `service._baseline_author`, `approve_item` |

**Fluxos.** O item nasce em elaboração com a revisão 0 (quem elaborou) e a distribuição calculada; a edição recalcula a grade; gravar de novo fecha a soma com o total. A aprovação congela a distribuição e sai dos indicadores (o aviso conta os itens em elaboração). A LB aprovada só aceita observações; mudar total, semanas ou perfil exige **SM aprovada e justificativa**, congela as semanas até a corrente e redistribui o saldo, gravando a revisão e o histórico na ficha. O apontamento semanal atualiza o que já existe e recusa os três limites. Toda gravação passa por `service.py`, com trilha e versão; os filhos congelados (revisões e distribuição) entram na trilha do agregado.

**Carga:** a parte `planejamento-produtividade` de `seed.py` grava os 14 itens do mock por `seed_produtividade.load_items`, com a distribuição da revisão vigente, os apontamentos e as revisões; as semanas andam em semanas inteiras e as datas em dias (`shift_date`), só no modo demonstração. **Migração:** `m040_produtividade` (`produtividade_item`, `produtividade_revisao`, `produtividade_distribuicao`, `produtividade_apontamento`; as três últimas são a exceção da D5b, sem `versao`). **Oráculo:** `api/tests/plataforma/test_carga_demonstracao.py` (14 itens, 170 apontamentos, 328 semanas; avanço 59,2% x 67,5%, SPI 0,88, FP 1,08 no projeto 1). **Testes:** `api/tests/planejamento/test_produtividade_calculos.py`, `test_produtividade_servico.py` e `test_produtividade_rotas.py`, com o apoio em `api/tests/apoio_produtividade.py`.

## Horas efetivas, amostragem e paralisações (ISSUE-047, HU-066)

**Tela** `produtividade` (trio `produtividade.html`, `produtividade.css`, `produtividade.js`): a tela ganhou as **abas Quantidades e Horas efetivas** (a de KPIs de performance chega na ISSUE-048). A aba **Horas efetivas** tem os filtros Empresa, Semana de corte, Área (CWA), Encarregado e Período (semana de corte, últimas N semanas ou desde o início) na própria toolbar, com Excel e PDF do filtro de agora, e as três visões num controle segmentado: **Capacidade produtiva** (KPIs de CP, utilização, atraso médio, HH efetivas e HH improdutivas; a jornada média por turno; CP por área e por dia; os registros de jornada), **Amostragem do trabalho** (KPIs de trabalhando, trânsito, parado e rodadas; o Pareto dos motivos de parada na biblioteca de gráficos; as listas de motivos de parada e de trânsito; o resumo por empresa e encarregado; as rodadas) e **Paralisações** (KPIs de Hhora, Mhora, cliente, clima e eventos; efetivo por motivo e por responsabilidade; os registros). No Portfólio as tabelas e as exportações trazem a coluna Projeto e a inclusão pede o projeto antes (`data-tn-incluir`). Fragmentos em `api/src/templates/planejamento/produtividade_horas.html` e `produtividade_horas_resposta.html`; os modais (jornada, rodada e paralisação) usam o alvo `produtividade-modal` e o partial `_prod_jornada_form.html`, `_prod_amostragem_form.html` e `_prod_paralisacao_form.html`.

**Rotas** (prefixo `/api/planejamento/produtividade/horas-efetivas`, em `routes.py`): `GET` aba (`empresa`, `corte`, `area`, `encarregado`, `periodo`); `GET /excel` e `GET /imprimivel` (indicadores, Pareto e as tabelas, com o filtro de agora); `GET /jornadas/nova`, `/jornadas/{id}/editar`, `/amostragens/nova`, `/amostragens/{id}/editar`, `/paralisacoes/nova`, `/paralisacoes/{id}/editar` (modais); `POST /jornadas` e `/jornadas/{id}` (e os pares de amostragens e paralisações): gravação com resposta multi-alvo (modal + aba; 422 por campo, 409 de versão vencida); a segunda jornada da mesma frente e dia recebe 422.

**Regras e nomes no código**

| Termo de negócio | Definição | Nome no código |
|---|---|---|
| Capacidade produtiva (CP) | Execução da manhã + execução da tarde; utilização = CP ÷ jornada de referência; atraso = do horário de chegada ao início | `calculations.field_day_figures`, `shift_hours`, `minutes_of` |
| HH efetivas e improdutivas | CP x efetivo e (jornada − CP) x efetivo, por jornada e somadas no resumo | `calculations.field_day_figures`, `capacity_summary` |
| Jornada média | Média do efetivo, dos horários, dos atrasos, do almoço e da CP do período | `calculations.capacity_summary`, `_average_times` |
| Percentuais da amostragem | Pessoas trabalhando, em trânsito e paradas sobre o total observado (2 casas) | `calculations.sample_share` |
| Pareto dos motivos | Ordem decrescente do total, com o percentual e o acumulado; empate na ordem do catálogo | `calculations.reason_pareto` |
| Catálogos de motivos | 12 motivos de parada, 5 de trânsito, 10 de paralisação e 5 responsabilidades; vêm do servidor | `calculations.STOP_REASONS`, `TRANSIT_REASONS`, `STOPPAGE_REASONS`, `RESPONSIBILITIES` |
| Hhora e Mhora | Efetivo parado (pessoas x horas) e máquina e equipamento parados (unidades x horas), pelo tipo | `calculations.stoppage_figures`, `stoppage_summary` |
| Tempo potencialmente excusável | Responsabilidade Cliente, Gerenciadora ou Terceiros; o formulário orienta notificar no prazo contratual e avaliar o pleito em Contratos (03) | `calculations.EXTERNAL_RESPONSIBILITIES`; aviso em `_prod_paralisacao_form.html` |
| Janela do período | Semana de corte, últimas N semanas ou desde o início; o fim nunca passa da data de referência | `calculations.hours_window` |
| Faixas dos indicadores | Utilização e % trabalhando pela meta (10 p.p. de atenção); atraso pelos limites do parâmetro | `calculations.utilization_band`, `working_band`, `start_delay_band` |
| Um registro por frente e dia | Segunda jornada da mesma empresa, área e encarregado no dia é recusada | `service._refuse_duplicate_field_day`; UK de `jornada_campo` |
| Encadeamento do campo | O encarregado é o texto digitado pela fiscalização (como no protótipo); o observador e o registrador são pessoas | coluna `encarregado` (texto), `observador_id` e `registrado_por_id` (FK `pessoa`) |

**Fluxos.** Cada visão tem o seu botão de registro (Registrar jornada, Registrar observação, Registrar paralisação) e cada linha tem o lápis para editar; a gravação passa por `service.py`, com trilha e versão, e a resposta atualiza o modal e a aba na mesma requisição (422 com a mensagem por campo, 409 quando outra sessão gravou antes). A jornada recusa data futura, horários fora de ordem e a segunda frente do dia; a rodada exige ao menos uma pessoa observada e troca os motivos junto com ela (o pai guarda os totais de parado e trânsito); a paralisação exige término depois do início e mostra o aviso do pleito quando a responsabilidade não é da contratada. O filtro é do servidor (D6): o corte, a área, o encarregado e o período recalculam todos os painéis.

**Carga:** a parte `planejamento-campo` de `seed.py` grava as 180 jornadas, as 360 rodadas (com os motivos) e as 31 paralisações do mock por `seed_campo.load_field`, com as datas deslocadas em dias (`shift_date`), só no modo demonstração. **Migração:** `m041_jornada_amostragem_paralisacao` (`jornada_campo`, `amostragem`, `amostragem_motivo`, `paralisacao`). **Oráculo:** `api/tests/plataforma/test_carga_demonstracao.py` (projeto 1 desde o início: 120 jornadas, 240 rodadas, 25 paralisações, CP 6,81 h/dia, utilização 77,4%, 22.870 HH efetivas, 6.691 HH improdutivas, 55,26% trabalhando, 750,0 Hhora e 58,5 Mhora). **Testes:** `api/tests/planejamento/test_campo_calculos.py`, `test_campo_servico.py` e `test_campo_rotas.py`, com o apoio em `api/tests/apoio_produtividade.py`.

## KPIs de performance e plano de ação (ISSUE-048, HU-067)

**Tela** `produtividade` (trio `produtividade.html`, `produtividade.css`, `produtividade.js`): a tela ganhou a terceira aba, **KPIs de performance** (Quantidades e Horas efetivas chegaram nas ISSUES 046 e 047). A aba tem os filtros Empresa e Semana de corte na própria toolbar, com Excel e PDF do filtro de agora; a faixa de indicadores do bloco selecionado (geral ou a empresa do filtro) com avanço por quantidades, SPI de quantidades, aderência da janela, FP, tendência de atraso (SPI(t) e semanas), CP, % trabalhando, Hhora, Mhora (com o % das HH disponíveis) e HH improdutivas; a tabela **Performance por empresa** com as faixas dos parâmetros, a situação e o **Gerar plano de ação** (ou o link da ação já aberta); a tabela **Tendência semanal por empresa** (FP, aderência, % trabalhando e CP das últimas 12 semanas); e os gráficos da biblioteca do Design System (D11) de aderência semanal e de % trabalhando por empresa, com a meta tracejada. No Portfólio a tabela e as exportações trazem a coluna Projeto (uma linha por projeto e empresa) e o botão de inclusão pede o projeto antes (`data-tn-incluir="plano"`). Fragmentos em `api/src/templates/planejamento/produtividade_kpis.html`, `produtividade_kpis_resposta.html`, `produtividade_plano_form.html` e `_prod_plano_form.html`; o modal do plano usa o alvo `produtividade-modal`.

**Rotas** (prefixo `/api/planejamento/produtividade/kpis`, em `routes.py`): `GET` aba (`empresa`, `corte`); `GET /excel` e `GET /imprimivel` (indicadores, gráficos e as duas tabelas, com o filtro de agora); `GET /acoes/nova` (modal do plano, com os textos sugeridos pelos indicadores da empresa; no Portfólio pede o projeto antes); `POST /acoes` (cria a ação na Central; a segunda da mesma empresa e semana recebe 422; resposta multi-alvo com o modal e a aba; `X-TN-Toast`).

**Regras e nomes no código**

| Termo de negócio | Definição | Nome no código |
|---|---|---|
| Avanço por quantidades | Horas ganhas (realizado x índice) ÷ HH orçadas; o previsto usa a quantidade prevista x índice | `calculations.quantities_indicators` (`pct_real`, `pct_prev`) |
| SPI de quantidades | HG ÷ horas previstas na LB até o corte | `calculations.item_figures` (`spi`) |
| Aderência da janela | Realizado ÷ previsto, limitado a 100% por item e ponderado pelas HH orçadas | `calculations.item_figures` (`window_capped_hours`, `window_adherence`) |
| Fator de produtividade (FP) | HH apropriadas ÷ horas ganhas; o da janela é o do parâmetro | `calculations.item_figures` (`pf`, `pf_window`) |
| Tendência de atraso / SPI(t) | Semanas da LB equivalentes ao realizado ÷ semanas decorridas; o atraso compara o término projetado com o fim da LB | `calculations.schedule_trend` (`spi_t`, `slip_weeks`, `trend_week`) |
| Tendência semanal | FP, aderência, % trabalhando e CP de cada semana, por empresa | `calculations.weekly_trend`, `TrendInput`, `TrendWeek` |
| Faixas do bloco | `success`, `warning` ou `danger` de cada indicador pelos parâmetros | `calculations.indicator_band`, `working_band`, `utilization_band`, `PerformanceBands`, `performance_alerts` |
| % das HH disponíveis | Hhora ÷ HH disponíveis (efetivo x jornada) da janela | `calculations.stoppage_share` |
| Referência do plano | `PRD-2026-S39-01` = semana e empresa | `calculations.performance_action_reference`, `performance_action_parts` |
| Bloco da performance | Quantidades, campo, tendência, faixas e ação aberta de um recorte | `service.performance_overview`, `PerformanceBlock`, `PerformanceOverview` |
| Plano de ação | Cria a ação na Central pela costura única (D9), uma aberta por empresa e semana; 422 na segunda | `service.create_performance_action`, `performance_action_form`; `validation.parse_action_plan` |
| Link de volta | A Central resolve a ação de Produtividade para a aba KPIs com a empresa e a semana | `service._performance_action_link` (`origin_links.register`) |

**Fluxos.** A leitura calcula o bloco geral e um por empresa (por projeto e empresa no Portfólio) na janela de N semanas do parâmetro até a semana de corte: as quantidades de `item_figures` no corte e o campo da mesma janela de datas (o fim nunca passa da data de referência, D6). O botão + da empresa com indicador fora da faixa abre o formulário com ação, descrição e data sugeridas (empresa, indicadores e prazo de 14 dias); gravar cria a ação na Central (origem Produtividade, grupo Produtividade, item seguinte da referência) e a resposta traz o modal fechado, o toast e a aba atualizada (o link da ação aparece na linha). A segunda tentativa da mesma empresa e semana recebe 422; concluir a ação na Central libera uma nova. A empresa pode ser trocada no próprio formulário (o Portfólio perde a linha ao pedir o projeto).

**Carga:** os KPIs saem dos dados das 046/047 já carregados; nada novo entra. A ação aberta do mock (`PRD-2026-S38-01`) já vem da carga da Central; o seed dela reescreve a referência de Produtividade com o id que o banco deu à empresa do protótipo, como faz com os demais ids, para a aba encontrar a ação e o link de volta levar a empresa certa. **Migração:** nenhuma — a referência usa a coluna `origem_ref` da tabela `acao`, que já existe. **Oráculo:** `api/tests/plataforma/test_carga_demonstracao.py` afirma, no projeto 1 e no corte S39, o avanço de 59,2% x 67,5% (SPI 0,88), o FP de 1,12 na janela, a CP de 6,81 h/dia, 55,26% trabalhando, o SPI(t) de 0,94 (4 semanas de atraso), a Alfa Montagens com SPI 0,83 e FP 1,15 em alerta, a Zeta Civil com 80,7% e a ação de S38 da Alfa. **Testes:** `api/tests/planejamento/test_kpis_calculos.py`, `test_kpis_performance_servico.py` e `test_kpis_performance_rotas.py` (os nomes `test_kpis_servico.py` e `test_kpis_rotas.py` pertencem à ISSUE-040).

**Onde mexer:** cálculos em `calculations.py` (`schedule_trend`, `weekly_trend`, `ratio_chart`, `performance_action_*`, `stoppage_share`, `PerformanceBands`); leitura e plano em `service.py` (`performance_overview`, `create_performance_action`, `_performance_*`); rotas em `routes.py` (bloco KPIs de performance); validação em `validation.py` (`parse_action_plan`); exportação em `export.py` (`performance_document`, `performance_kpis`); fragmentos em `api/src/templates/planejamento/produtividade_kpis.html`, `produtividade_kpis_resposta.html`, `produtividade_plano_form.html` e `_prod_plano_form.html`; trio em `app/_views/planejamento/produtividade.html` e `app/paginas/planejamento/produtividade.css`/`js`; testes em `api/tests/planejamento/test_kpis_calculos.py`, `test_kpis_performance_servico.py` e `test_kpis_performance_rotas.py`, e o oráculo na carga.

## Punch list: itens, verificação e bloqueio (ISSUE-049, HU-068/HU-069)

**Tela** `punch_list` (trio `punch_list.html`, `punch_list.css`, `punch_list.js`): a aba **Lista** com os indicadores clicáveis (Abertos, Categoria A abertos, Aguardando verificação, Vencidos e Fechados com o percentual dos válidos), a tabela de itens (código, sistema, subsistema, TAG, disciplina, categoria, marco, origem, empresa executante, responsável, abertura, prazo, situação e o link da ação na Central) e as ações do fluxo por linha (Editar, Tratar, Enviar para verificação, Verificar, Cancelar); a toolbar tem a busca, a situação, o modal de Filtros (categoria, sistema, disciplina, empresa e vencidos), o Novo item, o Importar Excel e o Excel/PDF do filtro de agora. No Portfólio a tabela e as exportações trazem a coluna Projeto e a inclusão pede o projeto antes (`data-tn-incluir`). Fragmentos em `api/src/templates/planejamento/punch*.html` e os parciais `_punch_*.html`; os modais (item, verificação, cancelamento e filtros) usam o alvo `punch-modal`.

**Rotas** (prefixo `/api/planejamento/punch`, em `routes.py`): `GET` tela (`busca`, `situacao`, `categoria`, `sistema`, `disciplina`, `empresa`, `vencidos`); `GET /excel` e `GET /imprimivel` (indicadores e tabela, com o filtro de agora); `GET /filtros` (modal); `GET /itens/novo` e `GET /itens/{id}/editar` (modal); `POST /itens` e `POST /itens/{id}` (criar/editar; resposta multi-alvo com modal, filtros e conteúdo; 422 por campo, 409 de versão vencida); `POST /itens/{id}/tratar` e `POST /itens/{id}/enviar` (transições de um clique); `GET`/`POST /itens/{id}/verificacao` (resultado Aprovado ou Reprovado com comentário); `GET`/`POST /itens/{id}/cancelamento` (justificativa obrigatória). A importação usa o fluxo genérico (ISSUE-018) com a chave `punch-itens`.

**Regras e nomes no código**

| Termo de negócio | Definição | Nome no código |
|---|---|---|
| Situações do fluxo | Aberto → Em tratamento → Aguardando verificação → Fechado; Reprovado volta a Em tratamento; Cancelado exige justificativa (mínimo 10 caracteres) | `validation.PUNCH_SITUATIONS`, `PUNCH_RESULT_REJECTED`, `PUNCH_JUSTIFICATION_MIN`; `service.treat_punch_item`, `send_punch_item_to_verification`, `verify_punch_item`, `cancel_punch_item` |
| Categoria | A impede o marco seguinte; B fecha até o aceite definitivo; C conforme acordo | `validation.PUNCH_CATEGORIES`, `calculations.PUNCH_BLOCKING_CATEGORY` |
| Marcos vinculados | Completação mecânica, Pré-comissionamento, Comissionamento, Partida, Aceite provisório e Aceite definitivo, na ordem | `validation.PUNCH_MILESTONES`, `calculations.PUNCH_MILESTONE_INDEX` |
| Origem do item | Walkdown, Inspeção, Comissionamento, Cliente ou Auditoria | `validation.PUNCH_ORIGINS` |
| Bloqueio do sistema | Item A aberto bloqueia o marco pedido quando o marco dele é anterior ou igual; o aceite definitivo é bloqueado por qualquer item aberto; calculado, não é coluna | `calculations.punch_system_block_count`, `service._punch_blocks` |
| Vencido e aging | Vencido é o item aberto com prazo antes da data de referência; a idade conta da abertura e nunca é negativa | `calculations.punch_is_overdue`, `punch_age_days` |
| Indicadores da lista | Abertos, A abertos, aguardando verificação, vencidos, fechados e válidos (cancelado fora) | `calculations.punch_kpis`, `service.punch_overview` |
| Numeração | `PL-TN-2026-0001` pelo tipo `punch` do projeto; a carga continua a série do mock | `numbering` (`PUNCH_KIND`), `service.create_punch_item`, `seed_punch.load_punch` |
| Evidência do fechamento | Sem anexo o fechamento é recusado; o anexo entra pelo tipo de origem `punch_item` (D5a) | `service.verify_punch_item` (`has_evidence`), `read_punch_origin`, `PUNCH_ATTACHMENT_TABLE` |
| Segregação de funções | O verificador não pode ser o executante; quem tenta recebe 403 (D7) | `service.verify_punch_item` (`PUNCH_SEGREGATION_MESSAGE`) |
| Ação na Central | Cada item aberto gera uma ação (origem Punch list) pela costura (D9), com prazo, assunto e descrição espelhados | `service._create_punch_action`, `_sync_punch_action`, `calculations.punch_action_description` |
| Sincronização nos dois sentidos | Item → ação: prazo, assunto e fechamento; ação → item: concluir fecha o item na data, replanejar move o prazo | `service._sync_punch_action`, `react_to_punch_action`; `central_acoes.sync_from_origin`, `close_from_origin` |
| Link de volta | A Central resolve a ação de Punch list para a lista com a busca pelo código | `service._punch_action_link` (`origin_links.register`) |

**Fluxos.** O item nasce Aberto com a numeração do projeto, a ação correspondente na Central e o identificador sugerido (quem registra); Tratar o leva a Em tratamento, Enviar o põe Aguardando verificação e a verificação fecha com Aprovado e a evidência anexada ou volta a Em tratamento com o motivo (Reprovado) — o verificador nunca é o executante. O cancelamento encerra a ação e tira o item dos válidos. Editar o prazo espelha a ação aberta; concluir ou replanejar a ação na Central espelha o item. O sistema aparece bloqueado no marco do item A aberto e nos seguintes, e cada indicador recorta a lista por um clique. Toda gravação passa por `service.py`, com trilha e versão; os anexos entram pela porta única (D5a).

**Carga:** a parte `planejamento-punch` de `seed.py` grava os 20 itens do mock (16 no projeto 1 e 4 no projeto 2) por `seed_punch.load_punch`, com as datas deslocadas em dias (`shift_date`) e a numeração de cada projeto continuando depois do maior código; as ações de origem Punch list vêm da parte `central_acoes`, que as deriva do item (o cancelado não gera), só no modo demonstração. **Migração:** `m042_punch_list` (`punch_item`; o cadastro `sistema` existe desde a `0001_plataforma`). **Oráculo:** `api/tests/plataforma/test_carga_demonstracao.py` (20 itens; no projeto 1, 12 abertos, 4 da categoria A, 2 aguardando verificação, 2 vencidos e 3 fechados; 15 ações derivadas; o sistema 420 bloqueado para a Completação mecânica e os sistemas 210, 310 e 420 para o Comissionamento; o PL-TN-2026-0001 com a ação concluída na data do fechamento). **Testes:** `api/tests/planejamento/test_punch_servico.py` e `test_punch_rotas.py`, com o apoio em `api/tests/apoio_punch.py`.

**Onde mexer:** cálculos em `calculations.py` (bloco Punch list: `punch_kpis`, `punch_is_overdue`, `punch_system_block_count`, `punch_action_description`); leitura e fluxo em `service.py` (bloco Punch list: `punch_overview`, `create_punch_item`, `verify_punch_item`, `react_to_punch_action`, `_sync_punch_action`); rotas em `routes.py` (bloco `PUNCH_BASE`); validação em `validation.py` (`parse_punch_item`, `parse_punch_verification`, `parse_punch_cancellation`); importação em `importers.py` (`punch_importer`, chave `punch-itens`); exportação em `export.py` (`punch_document`, `punch_kpis`); fragmentos em `api/src/templates/planejamento/punch*.html` e `_punch_*.html`; trio em `app/_views/planejamento/punch_list.html` e `app/paginas/planejamento/punch_list.css`/`js`; cadastro de sistemas em `configuracoes/registers.py` (`list_systems`, `system_options_by_id`); testes em `api/tests/planejamento/test_punch_servico.py` e `test_punch_rotas.py`, com o apoio em `api/tests/apoio_punch.py`, e o oráculo na carga.

## Painel da completação (ISSUE-050, HU-070)

**Tela** `punch_list`, aba **Painel**: o alerta dos sistemas bloqueados por item A aberto, os indicadores **Sistemas liberados** por marco (Completação mecânica, Comissionamento e Aceite definitivo, com o % e o "x de y sistemas") e **Sistemas bloqueados**, o **burndown** (abertos, fechados e saldo acumulados por semana, no visual Curva S Linha), o **aging** e as contagens por **disciplina** e **empresa** (barras empilhadas por categoria A/B/C no visual Comparativo de Barras, D11), a tabela **Sistemas e liberação por marco** (A/B/C abertos + Liberado/Bloqueado (n) em cada marco) e o Excel/PDF do painel. A aba Lista continua como a ISSUE-049. A aba é endereçável por `?aba=painel`; a tela carrega o painel junto (alvo `punch-painel`) e o refaz pela rota própria quando a lista mudou desde a última leitura. No Portfólio a tabela de sistemas (e as exportações) traz a coluna Projeto; os gráficos agregam os dois projetos, sem coluna. Fragmento em `api/src/templates/planejamento/punch_painel.html`.

**Rotas** (prefixo `/api/planejamento/punch/painel`, em `routes.py`): `GET` painel (fragmento da aba, alvo `punch-painel`); `GET /excel` e `GET /imprimivel` (indicadores, os quatro gráficos na impressão e as cinco tabelas — burndown, aging, disciplina, empresa e sistemas —, no mesmo documento). A tela (`GET /api/planejamento/punch`) passou a devolver também o fragmento do painel.

**Regras e nomes no código**

| Termo de negócio | Definição | Nome no código |
|---|---|---|
| Burndown | Abertos, fechados e saldo acumulados por semana, da abertura mais antiga à semana seguinte à data de referência, com os itens não cancelados; o fechado conta antes da segunda-feira da semana | `calculations.punch_burndown`, `punch_burndown_weeks`, `punch_burndown_week_start`; `service._punch_burndown_chart` |
| Aging | Itens abertos por faixa de idade (as faixas do parâmetro `punch.agingFaixas`, 7 e 30 dias por padrão: "Até 7 dias", "8 a 30 dias" e "Mais de 30 dias") e categoria | `calculations.punch_aging_counts`, `punch_aging_band`, `punch_aging_labels`; `service.punch_parameters`, `_punch_aging_bands` |
| Abertos por disciplina e empresa | Itens abertos empilhados por categoria A/B/C; a disciplina segue a ordem do cadastro e a empresa, a primeira aparição (a ordem do código) | `calculations.punch_discipline_counts`, `punch_company_counts`, `punch_category_count` |
| % de sistemas liberados por marco | Sistemas sem bloqueio no marco divididos pelos sistemas com item no escopo (uma casa); sem sistema, não há percentual | `calculations.punch_released_pct`; `service.PunchMilestoneRelease`, `punch_dashboard` |
| Alerta dos sistemas bloqueados | Sistemas bloqueados para a Completação mecânica ou o Comissionamento, na ordem do código | `service.punch_dashboard` (`blocked_systems`), `PUNCH_DASHBOARD_ALERT_MILESTONES` |
| Tabela de sistemas | Os abertos por categoria e o Liberado/Bloqueado (n) por marco, calculados a cada leitura (a regra de bloqueio é a da ISSUE-049) | `service._punch_blocks`, `_punch_dashboard_system` |
| Gráficos (D11) | Burndown em `curva-s-linha` (modo acumulado); aging, disciplina e empresa em `comparativo-barras` (barras horizontais empilhadas, um painel por grupo) | `service._punch_burndown_chart`, `_punch_stacked_chart` |
| Faixas do aging | O grupo `punch` dos parâmetros vigentes (`agingFaixas`), com os valores iniciais de reserva | `service.punch_parameters`, `configuracoes.current_group` |

**Fluxos.** O painel é só leitura: nasce do escopo (projeto ou Portfólio) e recalcula tudo a cada leitura. A tela o carrega junto com a lista; quando o usuário abre a aba depois de uma gravação (item criado, tratado, verificado ou cancelado), o JS refaz o fragmento pela rota do painel. O fechamento de um item e o bloqueio dos sistemas se refletem sem nenhuma coluna nova (nada é materializado).

**Carga e oráculo:** sem carga nova (a da ISSUE-049 serve) e **sem migração** (nenhuma tabela nova). **Oráculo:** `api/tests/plataforma/test_carga_demonstracao.py` (`test_oraculo_do_painel_da_punch_list`): no projeto 1, na âncora, o aging fecha em 3/7/2 itens abertos ("Até 7", "8 a 30", "Mais de 30"), com a categoria A em 1/3/0; os sistemas 210, 310 e 420 bloqueados para a Completação mecânica ou o Comissionamento (75,0% e 25,0% liberados) e o Aceite definitivo bloqueado nos 4; o burndown de 10 semanas termina em 15 abertos, 3 fechados e 12 em aberto. **Testes:** `api/tests/planejamento/test_punch_painel_calculos.py` (fronteiras do aging, fórmula do % liberado e o burndown), `test_punch_servico.py` e `test_punch_rotas.py` (painel, Portfólio e Excel/PDF).

**Onde mexer:** cálculos em `calculations.py` (bloco Painel da punch list: `punch_aging_*`, `punch_burndown*`, `punch_*_counts`, `punch_released_pct`, `PunchPanelState`); leitura e gráficos em `service.py` (bloco Painel da Punch list: `punch_dashboard`, `punch_parameters`, `_punch_*_chart`); rotas em `routes.py` (bloco `PUNCH_DASHBOARD_BASE`); exportação em `export.py` (`punch_dashboard_document`, `punch_dashboard_kpis`, as tabelas); fragmento `punch_painel.html`; view, CSS e JS do trio em `app/_views/planejamento/punch_list.html` e `app/paginas/planejamento/punch_list.css`/`js`; testes em `api/tests/planejamento/test_punch_painel_calculos.py`, `test_punch_servico.py`, `test_punch_rotas.py` e o oráculo na carga.

## Idioma (ISSUE-088)

A parte 2 do inglês (D13) completa o catálogo: o namespace `planejamento` vive em
`api/src/core/translations.py`, alimentado pelo `en.js` do protótipo (e, na Programação
Semanal, por chaves novas escritas com o inglês da casa). O idioma vem do cookie
`gestnow_idioma`, gravado pela rota `POST /api/idioma`, e o seletor PT | EN fica na barra
lateral. O rótulo do período do relato é montado em `calculations.period_name` (Semana/Week) e o curto em `short_period_name` (`S38`/`W38`); o EAP vira WBS e a SM, CR.
Os templates chamam `{{ t('planejamento', 'Texto') }}`; as views e o JS estáticos usam
`data-i18n`/`TN.t`; as datas saem do `data()`/`data_hora()` do contexto e do
`translations.format_date`/`mes_curto`/`semana_label` (a semana ISO é `S38` em português e
`W38` em inglês). As rotas traduzem avisos, recusas e erros por campo no idioma do request,
e os gráficos passam por `_chart_data`, que traduz os textos do `data-dados` e acrescenta os
`rotulos` do motor de gráficos. Títulos e colunas das planilhas e da folha imprimível são
traduzidos pelo namespace do documento (`Document.namespace`/`Document.idioma`) em
`core/export_document`; o `RequestContext.idioma` leva o idioma resolvido às costuras das
rotas. Para acrescentar tradução, some a chave ao namespace `planejamento`; a cobertura em
`api/tests/plataforma/test_traducoes.py` e a revisão de tela em
`api/tests/plataforma/test_idioma_nas_areas_2.py` reprovam chave marcada sem tradução.
