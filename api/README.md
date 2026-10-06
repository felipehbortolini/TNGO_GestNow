# API do Timenow GestNow

Backend em Azure Functions V4, modelo de programação V2, com blueprints. Exceto por `/api/health`, as rotas de tela devolvem fragmentos HTML para o Alpine AJAX.

## Estado desta entrega

O backend contém as rotas de plataforma necessárias ao shell e a camada de banco:

| Blueprint | Rota | Resposta |
|---|---|---|
| `health.py` | `GET /api/health` | JSON de saúde, com o estado do banco e a revisão da migração |
| `nav.py` | `GET /api/nav` | Fragmento HTML da sidebar e das abas, recortado pelo perfil e pelo vínculo de quem chama |
| `acesso.py` | `GET /api/acesso-negado` | Tela de acesso negado (403): e-mail fora do cadastro, sessão ausente ou tela que o perfil ou o vínculo não abre |
| `acesso.py` | `POST /api/demonstracao/perfil` | Seletor de perfil do modo demonstração: guarda no cookie quem o avaliador escolheu |
| `attachments.py` | `GET /api/anexos` | Fragmento dos anexos de um registro: o componente de envio do Design System e a lista (nome, tamanho, quem enviou, quando) |
| `attachments.py` | `POST /api/anexos/enviar` | Recebe o arquivo (`multipart/form-data`) e devolve o mesmo fragmento atualizado; 422 com a mensagem sob o campo quando passa do limite ou o tipo está fora da lista |
| `attachments.py` | `GET /api/anexos/{anexo_id}/baixar` | Download do arquivo com o nome original, depois de checar a permissão do registro de origem (a exceção de download do Padrão: resposta de arquivo, não fragmento) |
| `exports.py` | `GET /api/exportacao/exemplo/excel` | Exemplo do Excel de uma tela (download do `.xlsx`, a exceção de download do Padrão); dados fictícios, só no modo demonstração (403 em produção) |
| `exports.py` | `GET /api/exportacao/exemplo/imprimivel` | Exemplo da versão imprimível (fragmento que o botão PDF monta e imprime); `?papel=a3` pede A3 paisagem; só no modo demonstração |

As telas e rotas de exemplo do Padrão foram removidas; ficam só as duas de exportação acima, o exemplo que um módulo copia (seção "Exportação"). Os módulos de domínio ainda não têm endpoints; o banco Postgres é preparado pelo `run.bat` desde a ISSUE-005.

## Banco de dados

A conexão vem da variável de ambiente `GESTNOW_DATABASE_URL` em todo ambiente (decisão D5): nada no código distingue o Postgres local do Azure Database for PostgreSQL. No local, o `run.bat` chama `scripts/prepare_database.py`, que usa a variável de usuário `GESTNOW_PG_ADMIN_URL` para criar o papel `gestnow` e os bancos `gestnow` e `gestnow_teste`, grava a URL da aplicação em `api/local.settings.json` (fora do git) e aplica as migrações.

* `src/core/database.py` — engine, sessão, `Base` dos modelos, normalização do driver `psycopg` e o relatório usado pelo `/api/health`.
* `src/core/models.py` — tabelas da plataforma (cliente, sequência, auditoria, anexo e notificação).
* `src/modulos/configuracoes/models.py` — projeto e cadastros de apoio.
* `migrations/` — Alembic. Cada fatia de módulo cria a própria revisão, em ordem, com:

  ```powershell
  cd api
  .venv\Scripts\python.exe -m alembic revision --autogenerate --rev-id 0002 -m central_acoes
  ```

Nomes de tabela e coluna em português snake_case; classes e atributos Python em inglês (D1, D5).

## Gravação segura

Toda gravação passa por uma transação por requisição e deixa trilha (D5, D5b):

* `src/core/database.py` — `unidade_de_trabalho()` abre a sessão e a transação da requisição; a fachada do módulo recebe a sessão e grava tudo junto.
* `src/core/recording.py` — `create`, `update` e `delete`: a forma única de gravar registro editável, com instantâneo, controle de versão e linha de trilha na mesma transação. A entidade da trilha é o nome da tabela do registro.
* `src/core/audit.py` — trilha só de inclusão (`auditoria`), com antes e depois por nome de coluna; a migração `0002_gravacao_segura` instala o gatilho que recusa `UPDATE` e `DELETE` na tabela.
* `src/core/versioning.py` — a versão que a tela abriu é conferida com trava de linha; divergência devolve 409 com o nome de quem gravou e a hora, lidos da trilha.
* `src/core/numbering.py` — numeração por projeto (`SM-TN-2026-0001`, `RSK-...`, `PL-...`, `PED-2026-001`) com `sequencia_numeracao` e trava de linha, sem repetir nem deixar buraco por concorrência.
* `src/core/money.py` — valores financeiros em centavos (`Centavos`, `bigint`); `format_brl` e o filtro Jinja `brl` formatam em reais só na apresentação.
* `src/core/calendario.py` — calendário da plataforma (D6): `today()` no fuso `America/Sao_Paulo` e `now()` são os únicos leitores do relógio; semana ISO, períodos, parcial e corte recebem a data de referência como argumento.
* `src/core/routing.py` — `fragment_route`: gate do Alpine, unidade de trabalho e o mapa 403/409/422; `on_error` re-renderiza o formulário do módulo com o que a pessoa digitou. Com `access=Access(...)`, resolve também o usuário, o escopo e a permissão (seção "Acesso e permissões", abaixo).

Os erros de domínio ficam em `src/core/errors.py`: `AccessDeniedError` (403), `InvalidDataError` (422) e `VersionConflictError` (409). O fragmento comum de erro é `src/templates/comum/erro.html`.

## Parâmetros versionados

`src/modulos/configuracoes/service.py` entrega a versão vigente de cada grupo numa data (`current_parameters`, `current_group` e as versões individuais), semeia a versão 1 dos 14 grupos de forma idempotente (`seed_initial_parameters`) e grava uma nova versão do grupo com autor, vigência e justificativa obrigatória (`save_parameter_group`). As regras da seção 7.4 do README do protótipo ficam em `validation.py`, uma função por regra, ligadas ao campo do formulário. A tela e as rotas de parâmetros são da ISSUE-076.

## Notificação

O follow-up de ações, a pauta de riscos ao gerente e o envio à tesouraria saem pela **porta de notificação** (D12, ISSUE-013). Quem chama não sabe se o e-mail é de verdade: a variável de ambiente decide, sem mudança de código.

* `src/core/notification.py` — a porta e o envio simulado, que é o padrão. `send(session, user_id=..., request=NotificationRequest(...))` confere o pedido, entrega pelo canal escolhido e grava, na transação da requisição, uma linha em `notificacao` e uma linha na trilha (`auditoria`, entidade `notificacao`) com destinatários, assunto, corpo e situação. Devolve o aviso para a tela (`notice`) e o tipo do toast (`toast_kind`).
* `src/core/graph_mail.py` — o envio de verdade, pelo Microsoft Graph (`sendMail`), escrito e desligado. O cliente HTTP é injetável (`HttpClient`); o padrão usa só a biblioteca padrão (`http.client`, só https), sem dependência nova.
* `notificacao.situacao`: `simulado` (envio desligado: nada saiu e a tela avisa "simulado", toast `aviso`), `enviado` (o Graph aceitou, toast `ok`) e `erro` (toast `erro`).
* Uma falha no envio (configuração incompleta, rede, recusa do Entra ou do Graph) **não** vira exceção: a linha fica em `erro`, o texto do erro vai na trilha (`depois.erro`) e o registro que pediu a notificação grava como sempre.

```python
outcome = notification.send(
    session,
    user_id=user.id,
    request=notification.NotificationRequest(
        kind=notification.FOLLOW_UP,  # ou RISK_AGENDA, TREASURY
        project_id=project.id,
        recipients=[person.email],  # dos cadastros, nunca de campo livre da tela
        subject="Follow-up das ações",
        body=text,
        reference_entity="acao",
        reference_record_id=action.id,
    ),
)
return AlpineAjaxResponse(..., toast=outcome.notice, toast_tipo=outcome.toast_kind)
```

Chame `send` como último passo do fluxo da fachada: e-mail que já saiu não volta com o rollback. Pedido sem destinatário, com e-mail malformado, sem assunto ou sem corpo devolve 422 (`InvalidDataError`) antes de gravar qualquer coisa. O corpo vai como texto puro.

### Variáveis de ambiente do envio

| Variável | Local (demonstração) | Azure | Para quê |
|---|---|---|---|
| `GESTNOW_ENVIO_EMAIL` | ausente (vale `desligado`) | `desligado` até o envio real ser liberado; `ligado` para enviar de verdade | Liga o envio real. Valor diferente de `desligado` e `ligado` falha alto, como o `GESTNOW_MODO`. |
| `GESTNOW_GRAPH_TENANT_ID` | ausente | ID do diretório (tenant) do Microsoft Entra onde o app está registrado | Só é lida com `ligado`. |
| `GESTNOW_GRAPH_CLIENT_ID` | ausente | ID do aplicativo (cliente) do registro | Só é lida com `ligado`. |
| `GESTNOW_GRAPH_CLIENT_SECRET` | ausente | Segredo do registro, só como configuração do aplicativo no Azure, nunca no repositório | Só é lida com `ligado`. |
| `GESTNOW_GRAPH_REMETENTE` | ausente | Caixa de correio da conta do app, de onde o e-mail sai | Só é lida com `ligado`. |

No local o envio fica desligado: nada a configurar. Para um teste manual, as variáveis podem ir em `api/local.settings.json` (fora do git). Para ligar no Azure:

1. No Microsoft Entra, registre o app, crie um segredo e conceda ao registro a permissão de **aplicativo** `Mail.Send` do Microsoft Graph, com o consentimento do administrador.
2. No Azure, preencha as quatro variáveis do Graph e `GESTNOW_ENVIO_EMAIL=ligado`.
3. Para voltar ao envio simulado, ponha `GESTNOW_ENVIO_EMAIL` em `desligado` ou remova-a.

Com `ligado` e alguma variável do Graph vazia, o envio falha e a falha fica na trilha com o **nome** da variável que falta, nunca com o valor. A tabela completa de variáveis do produto e o guia de publicação são da ISSUE-092.

## Anexos

O arquivo de um anexo é guardado de verdade (D5a, ISSUE-012): o banco fica com os metadados (`anexo`: nome, tipo, tamanho, hash, quem enviou, quando e o registro de origem) e o arquivo vai para o armazenamento que a variável de ambiente escolhe, sem mudança de código. A tela de cada módulo só reserva o lugar do componente; a plataforma cuida do resto.

* `src/core/file_storage.py` — a **porta de arquivos** (`FileStorage`: `save` e `read` sobre uma chave) e o adaptador da **pasta local** (`LocalFolderStorage`: `data/anexos/` na raiz do repositório, fora do git). `configured_storage()` escolhe o adaptador pelo ambiente.
* `src/core/blob_storage.py` — o adaptador do **Azure Blob Storage** (`BlobStorage`). O SDK oficial (`azure-storage-blob`) só é importado em `BlobStorage.from_environment`; o adaptador fala com uma costura de duas chamadas (`BlobContainer`), que os testes trocam por um dublê, sem rede e sem o SDK instalado.
* `src/core/attachments.py` — a fachada: `upload`, `panel` (a lista de um registro), `open_download` e `has_evidence`, mais os limites do grupo `anexos` dos parâmetros vigentes (`current_limits`, `file_problem`).
* `src/core/attachment_origins.py` — o registro de **tipos de origem**: cada módulo registra a tabela dos seus registros, a sua pasta e a **função de leitura**, a resposta da sua fachada a "esta pessoa pode ler este registro?".
* `src/blueprints/attachments.py` e `src/templates/comum/anexos.html` — as três rotas e o fragmento (o componente de envio do Design System e a tabela). O estilo são as classes `.upload` e `.anexos` de `app/ds/patterns.css`.
* `src/core/routing.py` — `file_route(access=...)`, o decorador do download: a mesma resolução de usuário, escopo e permissão do `fragment_route`, sem o gate do Alpine, com a recusa em texto simples (403, 404 ou 422).

### Variáveis de ambiente do armazenamento

| Variável | Local (demonstração) | Azure | Para quê |
|---|---|---|---|
| `GESTNOW_ARMAZENAMENTO_ANEXOS` | ausente (vale `local`) | `blob` | Escolhe o adaptador. Valor diferente de `local` e `blob` falha alto, como o `GESTNOW_MODO`. |
| `GESTNOW_PASTA_ANEXOS` | ausente (vale `data/anexos/` na raiz do repositório) | não se usa | Troca a pasta do adaptador local. |
| `GESTNOW_BLOB_CONEXAO` | ausente | Cadeia de conexão da conta de armazenamento, só como configuração do aplicativo no Azure, nunca no repositório | Só é lida com `blob`. |
| `GESTNOW_BLOB_CONTAINER` | ausente | Nome do container; sem a variável vale `anexos` | Só é lida com `blob`. |

No local nada precisa ser configurado: os arquivos vão para `data/anexos/<projeto>/<anexo>`. Para ligar o Blob no Azure:

1. Crie a conta de armazenamento e um container **privado** (`anexos`): todo download passa pela API, que checa a permissão do registro de origem, e nenhum endereço do Blob chega à tela.
2. Preencha, como configurações do aplicativo, `GESTNOW_ARMAZENAMENTO_ANEXOS=blob`, `GESTNOW_BLOB_CONEXAO` e, se o nome for outro, `GESTNOW_BLOB_CONTAINER`.
3. `azure-storage-blob` está em `pyproject.toml`, `uv.lock` e `requirements.txt`: o deploy o instala. Para voltar à pasta local, ponha `GESTNOW_ARMAZENAMENTO_ANEXOS` em `local` ou remova-a.

Com `blob` e a cadeia de conexão ausente a requisição falha alto, com o **nome** da variável que falta (nunca o valor), e nada é gravado. O guia de publicação e a tabela completa de variáveis são da ISSUE-092.

### Como um módulo usa os anexos

1. **Registre o tipo de origem** no fim do `service.py` do módulo, com a função de leitura. Ela devolve o `OriginRecord` quando o registro existe e a pessoa pode lê-lo, `None` quando o registro não existe, e levanta `AccessDeniedError` (403) quando existe e a pessoa não pode ler. A plataforma pergunta antes de listar, enviar e baixar, depois de conferir que a pessoa alcança o módulo; assim a permissão do anexo é sempre a do registro.

   ```python
   def read_punch_item(session: Session, *, user: User, record_id: int) -> OriginRecord | None:
       item = session.get(PunchItem, record_id)
       if item is None:
           return None
       # Aqui entra a regra de leitura do módulo (recorte por empresa, por exemplo).
       return OriginRecord(project_id=item.project_id)


   attachment_origins.register(
       OriginType(table="punch_item", module="planejamento", read=read_punch_item)
   )
   ```

2. **Reserve o lugar na view** e peça o fragmento. O id do registro vem da própria tela; o `id` do lugar é o alvo do `$ajax` (o formulário do fragmento troca o fragmento inteiro):

   ```html
   <div id="anexos-punch"
        x-init="$ajax('/api/anexos?origem=punch_item&registro=12', { target: 'anexos-punch' })">
     <div class="spinner" role="status" aria-label="Carregando os anexos"></div>
   </div>
   ```

3. **Evidência obrigatória** é ao menos um anexo gravado. A fachada pergunta no passo que exige a evidência e recusa com 422 na mensagem do módulo:

   ```python
   if not attachments.has_evidence(session, origin_table="punch_item", origin_record_id=item.id):
       raise InvalidDataError({"evidencia": "Anexe ao menos uma evidência para fechar o item."})
   ```

4. **Dado pessoal** (Q35: nome e dados médicos do HSE). A função de leitura devolve `OriginRecord(project_id=..., restricted=True)`: quem tem `Permission.VIEW_RESTRICTED` (Gestor e Admin) lista e baixa; quem só grava (Membro) envia o arquivo e vê no lugar da lista o aviso de que o anexo é restrito. Se só alguns anexos de um registro são dado pessoal, o módulo registra um segundo tipo de origem (outro nome em `table`) para eles.

### Regras

* **Limites** são o grupo `anexos` dos parâmetros vigentes na data (no início, 25 MB e PDF, JPG, PNG, DOCX, XLSX, PPTX, DWG e ZIP). Nova versão do grupo muda o próximo envio, nunca os anexos já guardados. Sem versão do grupo valem os valores iniciais. 1 MB são 1.048.576 bytes: o arquivo do tamanho exato do limite passa e um byte a mais não. O tipo vem da extensão do nome, sem diferenciar maiúsculas (`.jpeg` vale como JPG), e o tipo MIME do download é o do servidor, a partir do tipo, nunca o que o navegador disse. Arquivo vazio, sem extensão ou de tipo fora da lista é recusado. Toda recusa é 422 e a mensagem vai no campo `arquivo`.
* **Nome**: o original (sem pasta e sem caracteres de controle, com os acentos compostos) fica só no banco e volta no download (`Content-Disposition`, com `filename*` em UTF-8). No armazenamento a chave é `<projeto_id>/<anexo_id>`.
* **Ordem do envio**: confere o acesso e o registro, valida o arquivo e só então grava os metadados com a linha de trilha (`auditoria`, entidade `anexo`) na transação da requisição; o arquivo é guardado por último, e se isso falhar a requisição inteira é desfeita. Se o commit falhar depois de o arquivo ser guardado, sobra um arquivo sem referência, inofensivo.
* **Download**: `GET /api/anexos/{anexo_id}/baixar` é um link comum do navegador (sem o cabeçalho do Alpine) e passa por `file_route(access=Access())`: resolve o usuário, pergunta ao módulo dono do registro e, se o anexo é restrito, exige `VIEW_RESTRICTED`. Recusa é 403, anexo ou arquivo inexistente é 404 e identificador malformado é 422, sempre em texto simples.
* Fora desta fatia: remover anexo (a tabela não tem `versao`: o anexo é um fato gravado uma vez) e conferir o conteúdo do arquivo contra a extensão.

| Termo de negócio | Nome no código |
|---|---|
| Anexo (metadados) | `models.Attachment` (tabela `anexo`) |
| Porta de arquivos | `file_storage.FileStorage`; adaptadores `LocalFolderStorage` e `blob_storage.BlobStorage` |
| Limites do grupo Anexos | `attachments.AttachmentLimits`, lidos por `current_limits` |
| Recusa por tamanho ou tipo | `attachments.file_problem(nome, tamanho, limites)`: a mensagem do campo ou `None` |
| Enviar anexo | `attachments.upload` |
| Lista de anexos de um registro | `attachments.panel` |
| Baixar anexo | `attachments.open_download` e a rota `download_attachment` |
| Evidência (ao menos um anexo) | `attachments.has_evidence` |
| Tipo de origem do anexo | `attachment_origins.OriginType`, registrado por `attachment_origins.register` |
| Função de leitura do módulo dono | `attachment_origins.OriginReader` (devolve `OriginRecord`, `None` ou levanta `AccessDeniedError`) |
| Anexo de dado pessoal | `OriginRecord(restricted=True)` e `Permission.VIEW_RESTRICTED` |

## Importação

Toda importação de planilha é o **mesmo fluxo do servidor, em passos** (D12, HU-139, ISSUE-018); o módulo só registra o seu `Importer` com as colunas, a validação de uma linha e a gravação de uma linha pela própria fachada. A planilha **nunca é lida no navegador** (o SheetJS do protótipo e o risco dele saíram): o arquivo vai ao servidor, é conferido antes de qualquer biblioteca abri-lo e lido com o openpyxl em modo de leitura contínua.

| Passo | O que acontece | Nome no código |
|---|---|---|
| 1. Modelo | o Excel vazio, gerado pelo construtor da exportação: cabeçalho na aba `Dados` e a aba `Instruções` (obrigatória, formato e exemplo de cada coluna). O exemplo **não** vai em `Dados`, para não ser importado por engano | `importing.model_document` + `excel.excel_response`; rota `GET /api/importacao/{chave}/modelo` |
| 2. Envio e conferência | lê o arquivo, acha o cabeçalho, converte cada célula para o tipo da coluna e pede a validação de cada linha. **Erro bloqueia a linha, aviso não**; cada motivo vem com o número da linha do Excel. **Não grava nada** | `importing.check` devolve `ImportPreview`; rota `POST /api/importacao/{chave}/conferir` |
| 3. Confirmação | lê e confere **o mesmo arquivo de novo** e grava toda linha sem erro, **tudo ou nada**, numa transação só | `importing.confirm` devolve `ImportResult`; rota `POST /api/importacao/{chave}/confirmar` |
| Cancelar | fechar a conferência: nenhum passo antes da confirmação guarda coisa alguma, no banco ou fora dele | (sem rota: não há o que desfazer) |

O servidor **não guarda estado entre os passos**. A tela `GET /api/importacao/{chave}` (fragmento `comum/importacao.html`) tem um formulário só, e o lugar do resultado fica **dentro** dele: o arquivo continua escolhido, o botão de confirmar (que vem na conferência, com `formaction`) o reenvia, e `conferido` (o SHA-256 do arquivo conferido) garante que a confirmação vale só para ele. Escolher outro arquivo limpa a conferência.

### Como um módulo registra o seu importador

```python
# no fim do service.py do módulo, como o tipo de origem dos anexos
def validate_punch_row(session, *, values, context):
    errors = ("Responsável: não encontrado",) if not _person_exists(session, values["owner"]) else ()
    warnings = ("Prazo no passado",) if values["due"] and values["due"] < context.reference_date else ()
    return RowCheck(errors=errors, warnings=warnings)


def save_punch_row(session, *, values, context):
    create_punch(session, user=context.user, scope=context.scope, data=values)  # a fachada grava com recording


importing.register(
    Importer(
        key="punch-list",                      # o endereço: /api/importacao/punch-list
        title="Punch list",
        module="qualidade",                    # a pasta do módulo: quem importa precisa alcançá-lo
        columns=(
            ImportColumn("title", "Título", required=True, example="Trinca no piso"),
            ImportColumn("owner", "Responsável", required=True, example="Ana Souza"),
            ImportColumn("due", "Prazo", ValueKind.DATE, example="31/10/2026"),
            ImportColumn("status", "Situação", options=("Aberto", "Fechado"), example="Aberto"),
        ),
        validate=validate_punch_row,
        save=save_punch_row,
        unique=("title",),                     # não repete na planilha; o que já existe é da validate
    )
)
```

A tela do módulo pede o fragmento onde quer a importação, dando ao lugar um id e o mesmo id como alvo (o exemplo está no cabeçalho de `comum/importacao.html`). O servidor guarda só a lista dos importadores registrados; quem registra é o módulo, ao ser importado.

### API pública (estável)

| Termo de negócio | Nome no código |
|---|---|
| Importador de um módulo | `importing.Importer(key, title, module, columns, validate, save, permission=Permission.WRITE, unique=())` e `importing.register`, `find`, `registered`, `require` |
| Coluna do modelo | `importing.ImportColumn(field, header, kind=ValueKind.TEXT, required=False, options=(), example="", digits=2)`; `options` faz uma lista (ignora caixa e acento) |
| O que o módulo diz de uma linha | `importing.RowCheck(errors=(), warnings=())` (`importing.VALID` para a linha sem nada a dizer) |
| Quem importa, onde e quando | `importing.ImportContext(user, scope, reference_date)`: a data vem da rota (`calendario.today()`) |
| Validação de uma linha | `RowValidator`: `validate(session, *, values, context) -> RowCheck`; recebe os valores **já convertidos** (todos os campos, `None` onde a célula está vazia) e **só lê**; a linha com erro de tipo nem chega a ela |
| Gravação de uma linha | `RowWriter`: `save(session, *, values, context)`; grava **pela fachada do módulo dono** (`core.recording`: trilha e versão); `InvalidDataError` aqui recusa a importação inteira, com o número da linha |
| Modelo para baixar | `importing.model_document(session, *, importer, context)` (um `Document` com `Table` sem linhas) |
| Conferência | `importing.check(session, *, importer, upload, context)` devolve `ImportPreview` (`rows`, `writable_rows`, `error_rows`, `warning_rows`, `missing`, `ignored`, `can_confirm`, `digest`) |
| Confirmação | `importing.confirm(session, *, importer, upload, context, confirmation)` devolve `ImportResult` (`written`, `skipped`); `Confirmation(checked_digest, acknowledged)` |
| Arquivo enviado | `importing.Upload(name, content)` |
| Conversão de célula | `import_values.convert(cell, kind, options=())`: texto, número, percentual, dinheiro em centavos, data |
| Leitura do `.xlsx` | `spreadsheet_reader.read_rows(file_name, content)` |

### Regras

* **Só `.xlsx`.** Outra extensão, bytes que não são do Excel, arquivo corrompido, acima de 5 MB, que expandiria além de 50 MB ou com mais de 5.000 linhas de dados é **422** com a mensagem no lugar da conferência. O `.xls` e o `.csv` que o protótipo aceitava saem: o modelo baixado já é `.xlsx`.
* **O cabeçalho é achado pelo nome**, entre as 30 primeiras linhas (o modelo traz logo, título, escopo e data acima dele): sem diferença de caixa, acento ou espaço. Coluna fora do modelo é ignorada e listada; coluna obrigatória ausente bloqueia a conferência inteira.
* **Conversão** como no protótipo (`importar.js`): `1.234,56` e `1234,56` são 1234,56; sem vírgula o ponto é decimal; `R$` e `%` são aceitos; dinheiro vira **centavos inteiros** (metade para cima); célula formatada como percentual guarda fração e volta em pontos (`0,453` é 45,3); data é `dd/mm/aaaa`, `aaaa-mm-dd` ou o número de série do Excel, e `31/02/2026` não existe.
* **Linha numerada como no Excel**, linha vazia é espaçamento (não é conferida) e o erro de uma linha diz a coluna (`Valor: valor inválido`).
* **Tudo ou nada**: a confirmação grava dentro de um *savepoint*; se o módulo recusar uma linha, as anteriores são desfeitas, mesmo com o chamador mantendo a transação.
* **Quem importa** alcança o módulo do importador e tem a permissão dele (`WRITE` por padrão); o fornecedor não importa.

## Acesso e permissões

Quem entra, o que vê e o que grava é decidido **no servidor**, nunca na tela (D7, ISSUE-011). O **cadastro de Colaboradores é a fonte de verdade do acesso**: ter conta Microsoft não basta.

* `src/core/auth.py` — quem está chamando. No Azure é o principal que o Static Web Apps entrega no cabeçalho `x-ms-client-principal` (base64 de um JSON; o e-mail é `userDetails`). E-mail fora do cadastro, ou de colaborador desativado, recebe 403 e a **tela de acesso negado**, que diz a quem pedir liberação e qual conta foi usada. Cabeçalho presente decide sempre, mesmo na demonstração; cabeçalho malformado é recusado, nunca trocado pelo seletor. O cabeçalho é confiável porque a API só é alcançável pelo Static Web Apps, que o grava (o guia da ISSUE-092 confere isso). No **modo demonstração** (`GESTNOW_MODO` ausente ou `demonstracao`) e sem principal, a identidade vem do **seletor de perfil** da barra lateral: o cookie `gestnow_demo_perfil` guarda o id do colaborador escolhido (`POST /api/demonstracao/perfil`), e sem escolha a demonstração entra como o primeiro Admin ativo. Em produção o seletor não existe, o cookie é ignorado e não ter principal é não entrar.
* `src/core/rbac.py` — os dois eixos, em funções puras sobre o `User` que o login resolveu. O **perfil geral** (`GeneralProfile`: Visualizador, Membro, Gestor, Admin) governa os módulos 01 a 08, Início, o relatório e Configurações por **conjuntos de permissões** (`Permission`); os **papéis da Programação Semanal** (`ScheduleRole`) são por projeto e valem só no projeto em que foram dados; o **vínculo** (`Bond`) corta antes de qualquer permissão: o fornecedor só abre a Programação Semanal, e nela só a própria empresa; o cliente e o colaborador da Timenow veem o que o perfil geral permite.
* `src/core/routing.py` — o decorador único. `fragment_route(access=Access(...))` resolve o usuário (`core.auth`), o escopo (`core.scope`), o módulo e a permissão (`core.rbac`) antes do handler, que recebe `(req, session, context)` com `context.user` e `context.scope`. Quem não pode recebe 403 e a mensagem para a tela. Rota sem `access` (ou com `OPEN`) não resolve usuário: é só para as rotas de plataforma que precisam funcionar para quem o cadastro ainda não conhece (a troca de perfil); toda rota de módulo declara o seu `Access`, e um teste confere isso.
* `src/core/navigation_view.py` — a barra lateral e as abas já saem recortadas pelo mesmo `rbac` que as rotas usam: Configurações só para Gestor e Admin, a tela Colaboradores só para o Admin e, para o fornecedor, um único item, a Programação Semanal, com as suas cinco telas como abas. Tela que existe e a pessoa não pode abrir leva o shell à tela de acesso negado (`/api/acesso-negado`); a barra é cortesia, a autoridade é a rota.

| Termo de negócio | Nome no código |
|---|---|
| Colaborador logado | `rbac.User` (`id` é o colaborador; `person_id` é a pessoa do cadastro) |
| Perfil geral | `rbac.GeneralProfile` (`VIEWER`, `MEMBER`, `MANAGER`, `ADMIN`) |
| Papel da Programação Semanal | `rbac.ScheduleRole` (`PLANNER` Planejador, `INSPECTOR` Fiscal, `FOREMAN` Encarregado, `SUPPLIER` Fornecedor) |
| Vínculo | `rbac.Bond` (`TIMENOW`, `SUPPLIER` Fornecedor, `CLIENT` Cliente) |
| Permissão do perfil geral | `rbac.Permission`: `VIEW` ver, `WRITE` gravar (Membro, Gestor, Admin), `MANAGE` gerir (Gestor, Admin: aprovar, decidir, encerrar, excluir, estornar), `VIEW_RESTRICTED` ler o campo restrito do HSE (Gestor, Admin; Q35), `CONFIGURE` Configurações (Gestor, Admin), `ADMINISTER` (só Admin) |
| O perfil tem a permissão? | `rbac.can(user, permission)`, `rbac.require(user, permission)` |
| O módulo abre para a pessoa? | `rbac.can_use_module`, `rbac.require_module` (pelo identificador da pasta do módulo) |
| A tela abre para a pessoa? | `rbac.can_open_screen`, `rbac.require_screen` |
| Recorte da empresa do fornecedor | `rbac.company_scope(user)` (a empresa do fornecedor; `None` para os demais) e `rbac.require_company(user, company_id)` |
| Papel da programação no projeto | `rbac.schedule_roles_in`, `rbac.has_schedule_role`, `rbac.require_schedule_role(user, project_id, *roles)` |
| Segregação de funções | `rbac.require_segregation(user, *conflicts)` com `rbac.Conflict(person_id, message)`: quem elabora não aprova, o responsável pelo plano não aprova, o validador não é o autor, o verificador não é o executante |
| O que o decorador exige | `routing.Access(module=..., permission=...)`; `routing.OPEN` para a rota sem usuário |

A fachada de cada módulo chama as funções de `rbac` ela mesma (o recorte por vínculo e a segregação são regra da fachada, não da rota). Exemplo de rota de módulo:

```python
@bp.route(route="financeiro/contratos", methods=["POST"])
@fragment_route(access=Access(module="financeiro", permission=Permission.WRITE))
def save_contract(req: func.HttpRequest, session: Session, context: RequestContext):
    service.save_contract(session, user=context.user, scope=context.scope, data=req.form)
    ...
```

O fornecedor não tem permissão geral nenhuma (`rbac.can` é sempre falso para ele): na Programação Semanal a fachada decide pelos papéis por projeto e pelo `company_scope`. O cadastro de Colaboradores é lido pela fachada de Configurações (`find_access_by_email`, `find_access`, `list_active_access`); a tela que o mantém é da ISSUE-077.

## Exportação

Toda tela exporta para **Excel** e para **PDF** pelos mesmos dois mecanismos genéricos (D12, ISSUE-017); o módulo só descreve o conteúdo. O Excel é gerado no servidor com openpyxl (o pillow entra só porque o openpyxl precisa dele para inserir o logo). O PDF **é a impressão do navegador**: o servidor renderiza a versão imprimível e a pessoa escolhe "Salvar como PDF". Não há biblioteca de PDF, nem no servidor nem no navegador.

A tela monta **um `Document`** (`src/core/export_document.py`) e dele saem as duas saídas, de modo que o que o Excel exporta não falta no papel e o contrário ("nem uma coluna a menos"). O documento guarda **dados, nunca pixels**: uma célula é um valor com um `Tone` opcional (as cores de situação do Design System), e cada saída o desenha com os tokens de `app/ds/tokens.css`.

### API pública (estável)

Estes nomes e assinaturas são o contrato que os módulos e a importação (ISSUE-018) usam; mudar um deles exige issue própria, e campo novo entra sempre com valor padrão.

| Termo de negócio | Nome no código |
|---|---|
| O que a tela entrega à exportação | `export_document.Document(title, scope_label, generated_on, portfolio=False, context=(), kpis=(), charts=(), tables=(), paper=Paper.A4)` |
| Escopo e linha de escopo do cabeçalho | `describe_scope(scope, projects)` (`Portfólio` ou `TN-001 · Nome`), `project_label(project)`; `portfolio=scope.is_portfolio` |
| Data de geração | argumento `generated_on`; só a rota lê o relógio (`calendario.today()`) |
| Indicador com a referência de gestão | `Kpi(label, value, reference, kind=TEXT, digits=2, tone=None, status="")`; `reference` vem escrita como na tela (`Meta: 95%`) e `status` é a situação em palavras |
| Tabela | `Table(title, columns, rows=(), totals=None, per_project=True)`; `Column(header, kind=TEXT, digits=2, width=None)` |
| Linha e célula | `row(*valores, project=None)` e `Cell(value, tone=None)`; `Row(cells, project)` |
| Coluna Projeto (HU-016) | no Portfólio (`portfolio=True`) toda tabela com `per_project=True` abre com `Projeto`, preenchida por `row(..., project=project_label(p))`; tabela que não é por projeto diz `per_project=False` |
| Tipo do valor | `ValueKind`: `TEXT`, `INTEGER`, `DECIMAL`, `PERCENT` (pontos percentuais: `45.3` é `45,3%`), `MONEY` (**centavos inteiros**, sempre em reais cheios), `DATE` (`datetime.date`) |
| Cor de situação | `Tone`: `OK`, `WARN`, `ERROR`, `INFO`, `NEUTRAL` |
| Gráfico da versão imprimível | `Chart(title, kind, data)`: o `data-grafico` e o `data-dados` do motor de gráficos; o Excel não leva gráfico (quem quer os números põe uma tabela) |
| Papel | `Paper.A4` (padrão, paisagem) ou `Paper.A3` (paisagem, a tela pede no `Document`, como o MAS) |
| Texto como a pessoa lê | `export_document.format_value(kind, value, digits)` (`1.234,50`, `45,3%`, `R$ 1.234,56`, `05/10/2026`) |
| Documento fora do contrato | `InvalidDocumentError` (linha com o número errado de células, linha sem projeto no Portfólio, texto em coluna numérica): erro da tela que montou, achado no teste dela |
| Bytes do `.xlsx` | `excel.build_workbook(document) -> bytes` |
| Resposta de download do Excel | `excel.excel_response(document)`; nome do arquivo `excel.file_name(document)` (`mapa-de-controle-2026-10-05.xlsx`) |
| Versão imprimível | `printable.printable_response(document, req)` (fragmento `comum/imprimivel.html`); o que o template imprime é `printable.build_sheet(document)` |
| Resposta de arquivo | `responses.file_response(content, filename=..., content_type=...)` (acentos no nome pelo RFC 5987; `private, no-store`) |
| Rota de download | `routing.file_route(access=Access(...))`: usuário, escopo e permissão como na rota de fragmento, sem o gate do Alpine e com a recusa em texto simples |
| Botões da tela | `data-tn-excel="/api/<modulo>/<tela>/excel"` e `data-tn-pdf="/api/<modulo>/<tela>/imprimivel"` (tratados por `app/ds/ui.js`) |

### O que o Excel tem

* Em toda planilha: o logo, o título, `Escopo: ...`, `Gerado em: dd/mm/aaaa` e as linhas de `context` (`Período: S39/2026`).
* A planilha **Resumo**, quando o documento tem KPIs: um indicador por linha, com o valor, a **referência de gestão** e a situação em palavras.
* Uma planilha por tabela, com o nome limpo para o Excel (31 caracteres, sem `\ / ? * [ ] :`, sem repetir). Dentro dela, de cima para baixo: logo (`A1`), título, escopo, data, contexto, uma linha em branco, o título da tabela, o **cabeçalho** (com filtro ligado em `auto_filter` e painel congelado), as linhas e a linha de totais abaixo do filtro. Quem lê o arquivo de volta acha o cabeçalho por `sheet.auto_filter.ref`.
* Número e data são **células de verdade** (ordenam, filtram e somam): dinheiro em reais cheios (`"R$" #,##0.00`), percentual como fração com formato de percentual, data com `DD/MM/YYYY`. Texto entra como texto: o que começa com `=` nunca vira fórmula, e os caracteres que a planilha recusa são descartados.
* **Cores só pelos tokens**: cabeçalho, bordas, título e as cinco situações vêm de `app/ds/tokens.css` (`src/core/design_tokens.py`). Como só `api/` vai para o Azure, as cores e o logo viajam em cópias geradas (`src/core/tokens_ds.json` e `src/core/logo_timenow.png`) por `scripts/generate_ds_assets.py`; um teste falha se a cópia defasar. Cor nova: acrescente o token no `tokens.css` e rode o script.
* Impressão da planilha: paisagem, uma página de largura, A4 ou o papel do documento, cabeçalho da tabela repetido em cada página.

Um **modelo de importação** (ISSUE-018) é um `Document` com uma `Table` de colunas e sem linhas: `build_workbook(Document(title=..., scope_label=..., generated_on=hoje, tables=(Table(titulo, colunas),)))` devolve o `.xlsx` com o cabeçalho pronto, sem planilha Resumo.

### O que a versão imprimível tem

O fragmento `comum/imprimivel.html` (sem `<link>`, `<style>` nem `<script>`) traz o cabeçalho com o logo e o contexto, os KPIs com a referência, os gráficos e as tabelas (cabeçalho num `thead`, totais num `tfoot`). O papel é a folha `app/ds/print.css`, ligada em `index.html` com `media="print"`: `@page` A4 paisagem (A3 paisagem quando o documento é `Paper.A3`), só a folha sai no papel (sem barra lateral nem navegação), o cabeçalho de tabela se repete em cada página, a linha não parte entre páginas e os fundos são preservados. O botão PDF (`TN.imprimir` em `app/ds/ui.js`) busca o fragmento, monta no fim do `<body>`, espera os gráficos desenharem e as fontes carregarem, chama `window.print()` e desfaz tudo em `afterprint`; o título da página enquanto imprime (`Título - Escopo - data`) é o nome que o navegador sugere para o PDF.

### Receita de uma tela

A rota monta o documento e entrega às duas respostas. Cada rota declara o `Access` da própria tela (exportar é ler: quem pode ver pode exportar):

```python
@bp.route(route="financeiro/desembolso/excel", methods=["GET"])
@file_route(access=Access(module="financeiro"))
def disbursement_excel(req: func.HttpRequest, session: Session, context: RequestContext):
    return excel_response(_document(session, context))


@bp.route(route="financeiro/desembolso/imprimivel", methods=["GET"])
@fragment_route(access=Access(module="financeiro"))
def disbursement_printable(req: func.HttpRequest, session: Session, context: RequestContext):
    return printable_response(_document(session, context), req)


def _document(session: Session, context: RequestContext) -> Document:
    data = service.disbursement(session, user=context.user, scope=context.scope)  # a fachada do módulo
    return Document(
        title="Desembolso",
        scope_label=describe_scope(context.scope, configuracoes.list_projects(session)),
        generated_on=calendario.today(),
        portfolio=context.scope.is_portfolio,
        kpis=(Kpi("Desembolso", data.total_cents, "Orçado: R$ 1.500.000,00", ValueKind.MONEY),),
        tables=(Table("Parcelas", (Column("Parcela"), Column("Valor", ValueKind.MONEY)), rows=data.rows),),
    )
```

Na tela, os dois botões e mais nada: `<button type="button" class="btn btn--secondary" data-tn-excel="/api/financeiro/desembolso/excel">Excel</button>` e o mesmo com `data-tn-pdf` e a rota `imprimivel`. O botão leva o escopo (`?projeto=`) como o shell faz com as chamadas do Alpine AJAX; se o servidor recusar, o motivo vira toast. As rotas de exemplo (`src/blueprints/exports.py`) e a página `app/exemplos/exportacao.html` mostram os dois botões com todos os tipos de valor, tons, KPIs, um gráfico e a coluna Projeto no Portfólio.

Uma `Table` com `rows=()` é válida (planilha só com o cabeçalho); um documento sem KPIs e sem tabelas gera só a planilha Resumo, vazia.

## Testes

O `tests/conftest.py` recria o `gestnow_teste` pelas migrações a cada execução — um banco vazio sobe até a última revisão — e roda cada teste dentro de uma transação desfeita no fim. Nenhum teste toca o banco `gestnow`.

```powershell
cd api
.venv\Scripts\python.exe -m pytest
```

## Desenvolvimento local

Na raiz do repositório, use `run.bat`. Ele prepara `api/.venv` na primeira execução, prepara o banco e inicia `scripts/dev_local.py`, que serve `app/`, simula a sessão local e encaminha `/api/health`, `/api/nav` e as demais rotas de plataforma (`/api/escopo/projetos`, `/api/glossario`, `/api/acesso-negado`, `/api/demonstracao/perfil` as três de `/api/anexos` e as duas de `/api/exportacao/exemplo`) aos blueprints reais. Rota nova de plataforma entra na lista `ROUTES` desse script. Esse caminho não depende do SWA CLI nem do Azure Functions Core Tools. Localmente quem está logado é escolhido no seletor de perfil da barra lateral (modo demonstração); o `/.auth/me` simulado só avisa o shell de que há sessão.

Para ver o **login de verdade** localmente, defina `GESTNOW_DEV_PRINCIPAL` com o e-mail de uma conta Microsoft (variável de ambiente, ou em `api/local.settings.json`, fora do git) antes de subir o `run.bat`: o servidor local passa a mandar o cabeçalho do principal que o Static Web Apps mandaria, o seletor de perfil some, e-mail que está no cadastro de Colaboradores entra com o perfil dele e qualquer outro vê a tela de acesso negado.

Para rodar o host real do Azure Functions, instale as dependências da API e use `func start`. A validação de deploy continua dependendo do SWA CLI e do host do Functions.

## Adicionar uma rota de fragmento

Toda rota de tela passa pelo decorador único `fragment_route`, que confere o cabeçalho Alpine AJAX, abre a transação, resolve o usuário e o escopo, confere o acesso e devolve o 403, o 409 ou o 422 com a mensagem. Renderize com `AlpineAjaxResponse`; nenhuma regra de negócio deve ser implementada diretamente na rota: ela chama a fachada do módulo com o usuário, o escopo e a sessão.

```python
@bp.route(route="meu-modulo/registros", methods=["GET"])
@fragment_route(access=Access(module="meu_modulo"))
def list_records(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    records = service.list_records(session, user=context.user, scope=context.scope)
    return AlpineAjaxResponse(
        template_name="meu_modulo/lista.html",
        context={"registros": records},
        request=req,
    )
```

O `Access` diz o módulo (a pasta, `meu_modulo`) e, se a rota grava ou aprova, a permissão: `Access(module="meu_modulo", permission=Permission.WRITE)`. A função da rota é registrada no Azure só com `req` na assinatura (o decorador fixa isso); `session` e `context` chegam pelo decorador.

O template Jinja2 estende `base_fragment.html` e usa `{{ target_id }}` na raiz. Validações de formulário retornam HTTP 422 com os valores digitados e erros por campo.

## Dependências e configuração local

`pyproject.toml` é a fonte das dependências Python e `uv.lock` registra suas versões. `requirements.txt` contém apenas as dependências de produção usadas pelo deploy do Azure. O Excel usa `openpyxl` (e o `pillow`, que ele exige para inserir o logo); não há biblioteca de PDF. Configurações locais, inclusive `local.settings.json`, não devem ser versionadas.
