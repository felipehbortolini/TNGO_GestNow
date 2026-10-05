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

As telas e rotas de exemplo do Padrão foram removidas. Os módulos de domínio ainda não têm endpoints; o banco Postgres é preparado pelo `run.bat` desde a ISSUE-005.

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

## Testes

O `tests/conftest.py` recria o `gestnow_teste` pelas migrações a cada execução — um banco vazio sobe até a última revisão — e roda cada teste dentro de uma transação desfeita no fim. Nenhum teste toca o banco `gestnow`.

```powershell
cd api
.venv\Scripts\python.exe -m pytest
```

## Desenvolvimento local

Na raiz do repositório, use `run.bat`. Ele prepara `api/.venv` na primeira execução, prepara o banco e inicia `scripts/dev_local.py`, que serve `app/`, simula a sessão local e encaminha `/api/health`, `/api/nav` e as demais rotas de plataforma (`/api/escopo/projetos`, `/api/glossario`, `/api/acesso-negado` e `/api/demonstracao/perfil`) aos blueprints reais. Rota nova de plataforma entra na lista `ROUTES` desse script. Esse caminho não depende do SWA CLI nem do Azure Functions Core Tools. Localmente quem está logado é escolhido no seletor de perfil da barra lateral (modo demonstração); o `/.auth/me` simulado só avisa o shell de que há sessão.

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

`pyproject.toml` é a fonte das dependências Python e `uv.lock` registra suas versões. `requirements.txt` contém apenas as dependências de produção usadas pelo deploy do Azure. Configurações locais, inclusive `local.settings.json`, não devem ser versionadas.
