# Central de Ações

Módulo `central_acoes`. É o ponto único para acompanhar ações originadas nos demais módulos e atas de reunião. As regras de ação chegam nas ISSUE-019 e ISSUE-020; as atas, nas ISSUE-021 e ISSUE-022.

## Telas previstas

| Tela | Conteúdo | Issue |
|---|---|---|
| Ações | Lista, kanban, filtros, KPIs, replanejamento justificado e origem | ISSUE-019 |
| Painel de ações | Indicadores por origem, responsável e projeto; follow-up e PDF | ISSUE-020 (pronta) |
| Atas | Lista e revisão mais recente de cada ata | ISSUE-021 |
| Ficha da ata | Dados da reunião, participantes, anotações, ações e histórico | ISSUE-021, ISSUE-022 |

O status de uma ação é calculado pelo servidor. A origem registrada aponta de volta para a ficha que criou a ação.

## Trios das telas

Cada tela da lista de navegação (`api/src/core/navegacao.json`) tem um trio com o mesmo nome: a view, o estilo e o comportamento da página. O CSS é escopado pela classe raiz da view (`.pagina--<modulo>-<tela>`, com o `_` do identificador mantido), o JS registra `TN.paginas["<modulo>/<tela>"]` e o shell (`app/index.html`) vincula o CSS e o JS de todos. A verificação `trio-da-tela` confere o conjunto. Convenção completa em `docs/PADROES-DE-PAGINA.md`, seção "O trio da tela".

| Tela | View | CSS | JS |
|---|---|---|---|
| Ações | `app/_views/central_acoes/acoes.html` | `app/paginas/central_acoes/acoes.css` | `app/paginas/central_acoes/acoes.js` |
| Dashboards e KPIs | `app/_views/central_acoes/dashboard.html` | `app/paginas/central_acoes/dashboard.css` | `app/paginas/central_acoes/dashboard.js` |
| Atas | `app/_views/central_acoes/atas.html` | `app/paginas/central_acoes/atas.css` | `app/paginas/central_acoes/atas.js` |
| Ata | `app/_views/central_acoes/ata.html` | `app/paginas/central_acoes/ata.css` | `app/paginas/central_acoes/ata.js` |

## Rotas previstas

Prefixo: `/api/central-acoes/`.

| Grupo previsto | Uso | Issue |
|---|---|---|
| `acoes` | Listar, filtrar, replanejar e consultar ações | ISSUE-019 |
| `painel` | Consultar indicadores e gerar follow-up/PDF | ISSUE-020 |
| `atas` | Listar, criar e consultar atas | ISSUE-021 |
| `atas/{codigo}` | Revisar ata e manter anotações e ações | ISSUE-022 |

Os grupos são planejamento; cada issue fixa métodos e paths concretos conforme D14.

## Fórmulas e nomes no código

| Termo de negócio | Definição | Nome previsto |
|---|---|---|
| Status da ação | Concluída se há data de conclusão; caso contrário, Atrasada se a data replanejada ou prevista passou da data de referência; nos demais casos, Em andamento | `calculations.action_status` |
| Total de ações atrasadas | Contagem de ações cujo status calculado é Atrasada no escopo consultado | `calculations.overdue_action_count` |

A data de referência é recebida pela função; o status não é persistido como resultado. As integrações mantêm sincronizados o item e seu registro de origem.

## Fluxos

Uma ação aberta pode ser replanejada com justificativa. Concluir exige data de conclusão. Atas são numeradas por projeto; uma revisão nova mantém a linhagem e o histórico. A retirada de participante é recusada enquanto houver ação aberta sob sua responsabilidade.

## Integrações

Recebe ações de Planejamento, Financeiro, Suprimentos, Riscos, Qualidade, HSE e Governança. Oferece a fachada única de criação de ação para esses módulos; cada módulo continua dono do seu registro de origem. Links de retorno são resolvidos pela plataforma.

## Parâmetros

Não há grupo de parâmetros próprio definido nesta issue. Numeração, data de referência e permissões vêm das fachadas de plataforma; filtros e ordenação não são parâmetros versionados.

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas das ações | `routes.py` |
| Rotas do painel e do follow-up | `panel_routes.py` |
| Rotas das atas | `minutes_routes.py` |
| Fluxo, permissões e integrações das ações | `service.py` |
| Painel, agrupamentos e follow-up | `panel_service.py` e `follow_up.py` |
| Fluxo, permissões e integrações das atas | `minutes_service.py` |
| Status e indicadores | `calculations.py` |
| Validação de formulários | `validation.py` |
| Exportação | `export.py` (ações), `panel_export.py` (painel), `minutes_export.py` (atas) |
| Persistência | `models.py`; entidades desenhadas em `docs/MODELO-DE-DADOS.md` |
| Fragmentos | `api/src/templates/central_acoes/` |
| Tela, estilo e comportamento | `app/_views/central_acoes/` e `app/paginas/central_acoes/` |
| Testes | `api/tests/central_acoes/` |

A ISSUE-022 completa este documento com as anotações e ações da ata.

## O que a ISSUE-019 trouxe

Tela Ações (`app/_views/central_acoes/acoes.html`): KPIs clicáveis (Em dia, Atrasadas, Concluídas, Total), filtros em modal (busca, origem, status, responsável) com chips removíveis, lista paginada, kanban por status, replanejar com justificativa, concluir, histórico de replanejamentos, Excel e versão imprimível (PDF). No Portfólio a lista traz a coluna Projeto.

### Rotas (`/api/central-acoes/acoes`)

| Rota | Uso |
|---|---|
| `GET acoes` | Tela; filtros na consulta (`busca`, `origem`, `status`, `responsavel`, `pagina`, `visao=kanban`) |
| `GET acoes/excel`, `GET acoes/imprimivel` | Exportações do mesmo filtro |
| `GET/POST acoes/{acao_id}/replanejar` | Formulário e gravação; 422 sem justificativa, 409 se a versão mudou |
| `GET/POST acoes/{acao_id}/concluir` | Conclusão com data (não futura) |
| `GET acoes/{acao_id}/historico` | Justificativas dos replanejamentos |

### Fórmulas (`calculations.py`)

| Termo | Nome no código |
|---|---|
| Status da ação (Informação, Concluída, Atrasada, Em andamento) | `action_status` |
| Prazo vigente (replanejada, senão prevista) | `effective_due_date` |
| Dias de atraso | `days_overdue` |
| Atrasadas / Em dia / Concluídas / Total | `overdue_action_count`, `counts_by_status`, `due_by_reference_count` |
| Filtro Em andamento inclui atrasadas | `matches_status_filter` |

A fronteira é a prevista igual à data de referência: ainda em andamento.

### API pública da costura (para os demais módulos)

| Função | Quando chamar |
|---|---|
| `service.create_action(session, user=, new=NewAction(...), reference_date=)` | Única forma de gravar uma ação; exige origem (uma de `origins.ORIGINS`), referência do registro de origem, assunto e, para Ação, data prevista |
| `service.close_from_origin(session, user=, origin=OriginRef, completed_on=, reference_date=)` | O registro de origem foi encerrado na tela do módulo dono: conclui as ações abertas dele |
| `service.reopen_from_origin(session, user=, origin=OriginRef, reference_date=)` | O registro de origem foi reaberto |
| `origins.register_reaction(origem, reacao)` | O módulo dono diz como reage quando a ação é replanejada ou concluída na Central (`reacao(session, user, action, ActionEvent)`, mesma transação; pode recusar) |
| `origin_links.register(OriginLinkType(kind=, build=))` (`src/core/origin_links.py`) | O módulo dono registra o link de volta; sem registro, a tela mostra só a referência |

Ligações pendentes: cada módulo de origem registra o seu tipo de link e a sua reação na issue dele (Riscos, Qualidade, HSE, Mudanças, Lições, Produtividade, Contratos, Suprimentos); a Ata, na ISSUE-021. Ação da Punch list é tratada no registro de origem (replanejar e concluir ficam fora da Central).

### Carga e oráculo

`seed.py` grava as 60 ações do protótipo e as 19 derivadas da Punch list pela costura. `api/tests/oraculo/test_oraculo_acoes.py` afirma 8 atrasadas no projeto TN-2026-014 em 25/09/2026 (portfólio: 14 atrasadas, 36 em dia, 26 concluídas).

## O que a ISSUE-020 trouxe

Tela **Dashboards e KPIs** (`app/_views/central_acoes/dashboard.html`): cinco indicadores do motor de status único (Total, Em dia, Atrasadas, Concluídas e Concluídas no prazo original), filtro de origem, os gráficos da biblioteca (status por origem, abertas por responsável, status por projeto no Portfólio e previstas x concluídas por mês), a tabela **Status por projeto** (Portfólio) e **Desempenho por responsável**, com Excel e PDF. As contagens saem da mesma listagem da tela Ações, então batem com ela no mesmo escopo. Na tela Ações, **Enviar follow-up** abre o modal com quem recebe o quê e dispara a notificação por responsável (Gestor/Admin).

### Rotas (`/api/central-acoes`)

| Rota | Uso |
|---|---|
| `GET painel` | A tela; filtro `origem` na consulta |
| `GET painel/excel`, `GET painel/imprimivel` | Exportações do mesmo filtro |
| `GET acoes/followup` | Prévia: uma linha por responsável, com assunto e mensagem, e o aviso "simulado" |
| `POST acoes/followup` | Envia pela porta de notificação; resposta com o que foi registrado |

### Fórmulas e nomes no código

| Termo | Nome no código |
|---|---|
| Percentual de atrasadas sobre as abertas | `calculations.overdue_share_of_open` |
| Concluídas no prazo original (contagem e percentual) | `calculations.completed_on_planned_count`, `calculations.whole_percent` |
| Números por responsável (abertas, atrasadas, concluídas, maior atraso) | `calculations.responsible_tally` |
| Ranking por atraso; previstas x concluídas por mês | `calculations.top_open_responsibles`, `calculations.monthly_planned_vs_completed` |
| Agrupamento do follow-up por responsável e o texto do envio | `calculations.group_for_follow_up`, `follow_up.message_subject`, `follow_up.message_body`, `follow_up.result_notice` |

### Fluxos

O follow-up lê as ações em aberto do filtro da lista (origem, responsável e busca), agrupa por responsável e, no envio, registra uma notificação por responsável com e-mail pela porta (`src/core/notification.py`), com uma linha na trilha de cada uma. Quem não tem e-mail aparece na prévia e é nomeado no aviso, nunca ignorado em silêncio. Enquanto `GESTNOW_ENVIO_EMAIL` estiver desligado o envio é **simulado** e a tela diz isso.

### Testes

`api/tests/central_acoes/test_painel.py`: as contagens do painel contra a lista no mesmo escopo, o recorte por origem, o agrupamento do follow-up e o envio simulado (uma notificação por responsável), e as rotas do PDF e do Excel com filtro.

## O que a ISSUE-021 trouxe

Tela **Atas** (`app/_views/central_acoes/atas.html`): busca, lista paginada só com a revisão mais recente de cada ata (Número, Rev, Data, Assunto, Empresa principal, Tipo de reunião, Ações abertas e Atrasadas), Excel e PDF, e **Gerar nova ata** (formulário no modal; no Portfólio o botão pede o projeto antes). **Ficha da ata** (`ata.html`): faixa (número, revisão, data, tipo, projeto, elaborador e a contagem das ações), abas Dados da Reunião e Lista de Presença (Anotações e Ações chegam na ISSUE-022), modais Empresas executoras (com a principal), Buscar convidado e Retirar participante, Excel e PDF da ficha. A ficha de uma revisão anterior abre só para leitura, com o link da vigente.

### Rotas (`/api/central-acoes`)

| Rota | Uso |
|---|---|
| `GET atas` | Lista (`busca`, `pagina`) |
| `GET atas/excel`, `GET atas/imprimivel` | Exportações da lista |
| `GET atas/nova`, `POST atas` | Formulário e gravação; 422 por campo; sucesso redireciona para a ficha; sem projeto no escopo, 422 |
| `GET ata?id=` | Ficha (`aba=dados` ou `presenca`); 404 com o aviso se a ata não existe |
| `GET ata/excel`, `GET ata/imprimivel` | Exportações da ficha (dados, empresas e presença) |
| `GET/POST ata/empresas` | Empresa principal e executoras |
| `GET/POST ata/convidados` | Busca e inclusão de convidados |
| `GET/POST ata/retirar` | Retirar participante; 422 com a mensagem se há ação aberta dele nesta ata; 409 se a versão mudou |

### Regras e nomes no código

| Termo de negócio | Definição | Nome no código |
|---|---|---|
| Revisão mais recente de cada ata | A linhagem é o número dentro do projeto; vale a maior revisão | `calculations.latest_revision_ids` |
| Numeração da ata | Próximo número do padrão do projeto (`TN-2026-0000`) pela sequência da plataforma, sem buraco | `minutes_service.create_minutes` (`numbering.next_number`, tipo `ata`) |
| Retirada bloqueada (HU-054) | Participante com ação aberta (tipo Ação, sem conclusão) da ata sob sua responsabilidade não sai da lista; empresa não sai se alguém dela tem ação aberta da ata | `minutes_service.remove_attendee`, `minutes_service.set_companies` |

Empresas e participantes não têm versão própria: a versão da ata os protege, e toda mudança de lista a avança e deixa a trilha (`ata_empresa`, `ata_participante`). Só a revisão vigente se altera. O autor entra na lista de presença ao gerar a ata, e a empresa principal entra sozinha entre as executoras.

### API pública (fachada `minutes_service`)

`create_minutes`, `list_minutes`, `find_minutes`, `set_companies`, `add_guests`, `remove_attendee` e `guest_candidates`. A ISSUE-022 acrescenta `list_items`, `find_item`, `next_item_number`, `save_item`, `replan_item`, `item_justifications`, `generate_revision` e `revision_history` (fachada `minutes_service`).

### Integrações

O link de origem **Ata** está registrado (`origin_links`, no fim de `minutes_service.py`): a ação de uma ata abre a ficha dela. `acao.ata_id` agora é chave estrangeira para `ata`. A ata não registra reação a replanejar ou concluir: o item da ata é a própria ação.

### Carga e oráculo

`seed.py` grava as 9 revisões do protótipo antes das ações (número, revisão, empresas e presença como no mock) e continua a sequência de numeração de cada projeto (a próxima ata do TN-2026-014 é a 0039). `api/tests/oraculo/test_oraculo_atas.py` afirma 8 atas vigentes (5, 2 e 1 por projeto), as ações abertas e atrasadas de cada uma e o tamanho de cada lista de presença em 25/09/2026.

## O que a ISSUE-022 trouxe

**Telas.** Na ficha da ata, a aba **Anotações e Ações**: itens por grupo / área, numerados 1 / 1.1 na ordem, com as colunas Item, Tipo, Assunto / Descrição, Solicitante, Responsável, Prevista, Replanejada, Conclusão e Status (a linha atrasada sai destacada), o modal **Colunas da tabela** (alterna as colunas opcionais sem ir ao servidor) e os KPIs Itens, Em dia, Atrasadas, Concluídas e Informações no rodapé. Na faixa, **Gerar nova revisão** (só na vigente) e **Histórico da ata**. Os modais **Nova anotação/ação**, **Registrar replanejamento** e **Justificativas** completam a rastreabilidade.

**Rotas** (`/api/central-acoes`, `minutes_routes.py`):

| Rota | Uso |
|---|---|
| `GET/POST ata/itens/novo` e `ata/itens` | Formulário e gravação de uma anotação ou ação; a ação nasce pela costura da Central (origem `Ata`) |
| `GET/POST ata/itens/{item_id}/editar` | Edição do item; mudar o grupo renumera |
| `GET/POST ata/itens/{item_id}/replanejar` | Replanejamento com justificativa, pelas mesmas regras da Central (HU-053) |
| `GET ata/itens/{item_id}/justificativas` | Os replanejamentos do item, com autor e data |
| `GET ata/historico` | As revisões da linhagem, da mais nova para a mais antiga |
| `GET/POST ata/revisao` | Nova revisão: copia listas e itens e redireciona para a ficha nova |

**Fórmulas e nomes no código** (`minutes_service.py`): `next_item_number` (próximo número do grupo: `1.1` quando o grupo é novo, senão um a mais no grupo), `list_items` (agrupa e ordena pelo número do item; KPIs), `save_item` (cria pela costura `service.create_action` ou edita por `recording.update`), `generate_revision` (nova linha de `ata` com a mesma linhagem, cópia das empresas, da presença e dos itens com os replans) e `revision_history`. O status de cada item continua sendo o do motor único (`calculations.action_status`).

**Fluxos.** A anotação (`Informação`) é um item da ata e não entra na lista da Central; a ação (`Ação`) entra na lista com origem `Ata`, referência no número da ata e o link de volta para a ficha. Só a revisão vigente se altera: a nova revisão leva as listas e os itens, a anterior fica somente leitura, e a lista de atas passa a mostrar só a nova. O replanejamento de um item guarda autor, data, de/para e justificativa em `acao_replanejamento`; a edição do item não muda a data vigente quando já há replanejamento.

**Carga e oráculo.** A carga da ISSUE-019 já trazia os itens das atas (a coleção `acoes` do protótipo tem 28 itens com `ataId`, todos de origem `Ata`), então nada novo entrou no `seed.py`. `api/tests/oraculo/test_oraculo_atas_itens.py` afirma os 28 itens, a numeração 1.1 a 3.1 e os grupos da ata TN-2026-0028.

**Testes.** `api/tests/central_acoes/test_atas_itens.py`: numeração por grupo e renumeração ao mudar o grupo, a ação na lista da Central com link de volta (e a anotação fora dela), a nova revisão com linhagem, cópia e somente leitura, o histórico com a vigente marcada, o replanejamento com autor e justificativa, a validação (data prevista e pessoa da presença) e as rotas da aba e do formulário.
