# Central de Ações

Módulo `central_acoes`. É o ponto único para acompanhar ações originadas nos demais módulos e atas de reunião. As regras de ação chegam nas ISSUE-019 e ISSUE-020; as atas, nas ISSUE-021 e ISSUE-022.

## Telas previstas

| Tela | Conteúdo | Issue |
|---|---|---|
| Ações | Lista, kanban, filtros, KPIs, replanejamento justificado e origem | ISSUE-019 |
| Painel de ações | Indicadores por origem, responsável e projeto; follow-up e PDF | ISSUE-020 |
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
| Rotas das atas | `minutes_routes.py` |
| Fluxo, permissões e integrações das ações | `service.py` |
| Fluxo, permissões e integrações das atas | `minutes_service.py` |
| Status e indicadores | `calculations.py` |
| Validação de formulários | `validation.py` |
| Exportação | `export.py` (ações), `minutes_export.py` (atas) |
| Persistência | `models.py`; entidades desenhadas em `docs/MODELO-DE-DADOS.md` |
| Fragmentos | `api/src/templates/central_acoes/` |
| Tela, estilo e comportamento | `app/_views/central_acoes/` e `app/paginas/central_acoes/` |
| Testes | `api/tests/central_acoes/` |

As ISSUE-020 e ISSUE-022 completam este documento com o painel e as anotações e ações da ata.

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

`create_minutes`, `list_minutes`, `find_minutes`, `set_companies`, `add_guests`, `remove_attendee` e `guest_candidates`. A ISSUE-022 cria as revisões novas pela mesma fachada (`NewMinutes.revision`).

### Integrações

O link de origem **Ata** está registrado (`origin_links`, no fim de `minutes_service.py`): a ação de uma ata abre a ficha dela. `acao.ata_id` agora é chave estrangeira para `ata`. A ata não registra reação a replanejar ou concluir: o item da ata é a própria ação.

### Carga e oráculo

`seed.py` grava as 9 revisões do protótipo antes das ações (número, revisão, empresas e presença como no mock) e continua a sequência de numeração de cada projeto (a próxima ata do TN-2026-014 é a 0039). `api/tests/oraculo/test_oraculo_atas.py` afirma 8 atas vigentes (5, 2 e 1 por projeto), as ações abertas e atrasadas de cada uma e o tamanho de cada lista de presença em 25/09/2026.

## O que a ISSUE-020 trouxe

Tela **Dashboards e KPIs** (`painel.html`): KPIs do motor de status único (Em andamento, Atrasadas, Concluídas, % atrasadas, concluídas no prazo original), quebra por origem, por responsável (mais atrasado primeiro), os 10 com mais abertas, previstas x concluídas por mês e, no Portfólio, por projeto (com a coluna Projeto). Filtro de origem; Excel e PDF do painel. Na tela Ações, **Enviar follow-up** (só Gestor/Admin) abre a prévia com um aviso por responsável e envia pela porta de notificação; o texto sai de `follow_up.py` (o mesmo na prévia e no envio). Enquanto `GESTNOW_ENVIO_EMAIL` estiver desligado, a tela avisa "simulado" e cada envio fica em `notificacao` e na trilha. O **PDF das ações** é o `acoes/imprimivel` da ISSUE-019, com o filtro da tela.

### Rotas (`/api/central-acoes`, em `panel_routes.py`)

| Rota | Uso |
|---|---|
| `GET painel`, `painel/excel`, `painel/imprimivel` | Tela e exportações (consulta `origem`) |
| `GET/POST acoes/followup` | Prévia e envio, com o filtro da lista na consulta; 422 sem ação aberta ou sem e-mail cadastrado |

### Fórmulas e fachada

| Termo | Nome no código |
|---|---|
| Totais de um grupo (em dia, atrasadas, concluídas, maior atraso) | `calculations.responsible_tally` |
| Percentual inteiro (meio para cima) | `calculations.whole_percent` |
| Concluídas no prazo original | `calculations.completed_on_planned_count` |
| Previstas x concluídas por mês | `calculations.monthly_planned_vs_completed` |
| Top de responsáveis com abertas | `calculations.top_open_responsibles` |
| Agrupamento do follow-up | `calculations.group_for_follow_up` |
| Painel / prévia / envio | `panel_service.dashboard`, `plan_follow_up`, `send_follow_up` |

O painel lê a mesma lista da tela Ações (`service.list_actions`), então a contagem é a da lista no mesmo escopo. Onde mexer: texto da mensagem em `follow_up.py`; exportação do painel em `panel_export.py`. Testes: `api/tests/central_acoes/test_painel_*.py`; oráculo "painel da Central de Ações".
