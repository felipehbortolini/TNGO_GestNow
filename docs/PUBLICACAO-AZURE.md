# Publicação no Azure

Guia da ISSUE-092 (decisão D16; e D5, D5a, D7 e D12). O GestNow sai **pronto
para publicar, sem publicar**: montar os recursos e pôr no ar é um passo do
dono, feito à mão pelo portal — sem Bicep e sem pipeline Git (decisão de
05/10/2026). Nenhum segredo entra neste documento: onde aparecer `<...>`, o
valor é preenchido na hora e guardado fora do repositório.

Faça os passos na ordem. O passo 10 confere o **modo produção localmente**,
sem Azure nenhum, antes de qualquer publicação.

> **Decisão da execução (ISSUE-092), pendente de revisão do dono — plano do
> Static Web Apps.** O login que a D7 pede (Microsoft Entra ID aceitando
> qualquer conta Microsoft, corporativa ou pessoal) é o provedor
> **preconfigurado** do Static Web Apps: existe em todos os planos, inclusive o
> Free, e não vive no `app/staticwebapp.config.json`. Já o **Functions
> vinculado** (Bring your own) é recurso do plano **Standard**; no plano Free
> só existem Functions gerenciadas, cujo runtime Python vai até a 3.11 —
> abaixo do Python 3.13 que a API exige (`api/pyproject.toml`). Por isso este
> guia cria o Static Web Apps no plano **Standard** com o Function App
> vinculado (o mesmo desenho do app de Programação Semanal, cujas variáveis
> ficam no Function App). Se um dia a API for portada para Python ≤ 3.11, o
> mesmo passo a passo vale no plano Free com Functions gerenciadas.

## 0. Antes de começar

Na sua máquina: o `run.bat` já criou o `api\.venv` (Python 3.13), e o
`scripts\instalar.ps1` instalou o **SWA CLI** (`swa`) e o **Azure Functions
Core Tools 4** (`func`). Para conferir o banco, use o `psql` do PostgreSQL
instalado.

Os recursos que o guia cria, todos no mesmo grupo de recursos `<grupo>` e na
mesma região:

| Recurso | Nome (marque o seu) | Para quê |
|---|---|---|
| Azure Database for PostgreSQL — Flexible Server | `<servidor-pg>` | O banco `gestnow` da aplicação |
| Storage account | `<conta-anexos>` | O container privado `anexos` (arquivos dos anexos) |
| Function App | `<app-funcoes>` | A API (Python 3.13, Linux) |
| Static Web Apps | `<swa>` | O site, o login e o vínculo com a API |

## 1. O banco (Azure Database for PostgreSQL)

1. Portal > **Azure Database for PostgreSQL** > *Create* > **Flexible
   server**. Preencha: assinatura, grupo `<grupo>`, nome `<servidor-pg>`,
   região, carga de trabalho; usuário administrador `<usuario-admin>` e uma
   senha forte (guarde no cofre, nunca aqui). Anote a senha para a URL.
2. Na aba **Networking**, marque **Allow public access from any Azure service
   within Azure to this server** e adicione o seu IP atual (*Add current
   client IP address*) — é por ele que as migrações do passo 5 vão rodar.
   Mantenha o TLS exigido (padrão).
3. Depois de criado, no servidor: **Databases > Add**, nome `gestnow`.
4. A URL de conexão fica assim (senha com caracteres especiais
   percent-encoded; é a mesma forma do `GESTNOW_PG_ADMIN_URL` local):

   ```
   postgresql://<usuario-admin>:<senha>@<servidor-pg>.postgres.database.azure.com:5432/gestnow?sslmode=require
   ```

   Essa é a `GESTNOW_DATABASE_URL` do Azure (passo 4) e a URL das migrações
   (passo 5).

## 2. O armazenamento dos anexos

1. Portal > **Storage accounts** > *Create*: `<conta-anexos>`, mesmo grupo e
   região, redundância LRS. Nada de acesso anônimo.
2. No recurso: **Containers > + Container**, nome `anexos`, nível de acesso
   **Private**. Todo download passa pela API, que confere a permissão do
   registro — nenhum endereço do Blob chega à tela.
3. Em **Security + networking > Access keys**, copie a **Connection string**
   (chave 1): é a `GESTNOW_BLOB_CONEXAO`. É segredo: só nas configurações do
   aplicativo (passo 4), nunca no repositório.

## 3. A API (Function App) e o site (Static Web Apps)

**Function App** — a API:

1. Portal > **Function App** > *Create*: `<app-funcoes>`, *Publish* **Code**,
   *Runtime stack* **Python**, *Version* **3.13**, sistema operacional
   **Linux**, plano **Consumption** (ou Flex Consumption).
2. Publique a API da sua máquina, na pasta `api` (o Core Tools faz o build
   remoto e instala o `api/requirements.txt`; `api/.funcignore` deixa
   `uv.lock`, testes e `.venv` fora do pacote):

   ```
   cd api
   func azure functionapp publish <app-funcoes>
   ```

**Static Web Apps** — o site:

1. Portal > **Static Web Apps** > *Create*: `<swa>`, plano **Standard**
   (decisão do cabeçalho). Em *Deployment details*, origem **Other** — sem
   GitHub: a publicação é pela SWA CLI (passo 7).
2. Depois de criado, **Settings > APIs**: na linha *Production*, **Link** >
   *Backend resource type* **Function App**, escolha `<app-funcoes>` >
   *Link*. O `/api/*` do site passa a ir para o Function App; o prefixo `api`
   do `host.json` não muda. O vínculo cria no Function App o provedor de
   autenticação *Azure Static Web Apps (Linked)*, que é o que garante que a
   API só é alcançável pelo site — não remova esse provedor.
3. **Settings > Authentication**: não configure nada. O provedor **Microsoft
   Entra ID preconfigurado** já aceita qualquer conta Microsoft (de qualquer
   organização ou pessoal) e é ele que atende `/.auth/login/aad` — o mesmo
   endereço do `401` do `staticwebapp.config.json`. Criar um *custom
   registration* desligaria esse provedor, restringiria o login a um tenant e
   mudaria o desenho; não faça.

## 4. As variáveis (Function App > Settings > Environment variables)

Todas as variáveis do produto, com o valor local típico e o que preencher no
Azure. Preencha no Function App as da coluna **No Azure** que não disserem
"não se usa". As três últimas são só da máquina local.

| Variável | Valor local típico | No Azure (Function App) | O que faz |
|---|---|---|---|
| `GESTNOW_MODO` | ausente (vale `demonstracao`) | `producao` (obrigatória) | Escolhe entre demonstração e produção. Ausente vale demonstração; outro valor falha alto. Em produção não há seletor de perfil e sem login não se entra — sem esta variável, uma requisição sem principal entraria como o Admin da demonstração. |
| `GESTNOW_DATABASE_URL` | gravada pelo `run.bat` em `api/local.settings.json` — `postgresql://gestnow:<senha>@localhost:5432/gestnow` | `postgresql://<usuario-admin>:<senha>@<servidor-pg>.postgres.database.azure.com:5432/gestnow?sslmode=require` | Conexão do Postgres, lida pela API e pelas migrações (Alembic) em todo ambiente (D5). |
| `GESTNOW_ADMIN_EMAIL` | ausente (a demonstração não usa) | `<e-mail-do-primeiro-admin>` (passo 6) | E-mail do primeiro Admin que a carga de produção cria. Só é lida pelo `scripts/seed_database.py`; pode ficar preenchida ou ser removida depois do preparo. |
| `GESTNOW_ENVIO_EMAIL` | ausente (vale `desligado`, envio simulado) | `desligado`, ou `ligado` depois do passo 9 | Liga o envio real de e-mail pela porta de notificação. Outro valor falha alto, como o `GESTNOW_MODO`. |
| `GESTNOW_GRAPH_TENANT_ID` | ausente | ID do diretório (tenant) do registro do Entra (passo 9) | Só é lida com o envio ligado. |
| `GESTNOW_GRAPH_CLIENT_ID` | ausente | ID do aplicativo (cliente) do registro | Só é lida com o envio ligado. |
| `GESTNOW_GRAPH_CLIENT_SECRET` | ausente | Segredo do registro — só como configuração do aplicativo, nunca no repositório | Só é lida com o envio ligado. |
| `GESTNOW_GRAPH_REMETENTE` | ausente | `<caixa-remetente>@<dominio>` (a conta do app, com `Mail.Send` consentido) | Só é lida com o envio ligado. |
| `GESTNOW_ARMAZENAMENTO_ANEXOS` | ausente (vale `local`) | `blob` | Escolhe onde o arquivo dos anexos mora. Outro valor falha alto. |
| `GESTNOW_PASTA_ANEXOS` | ausente (vale `data/anexos/` na raiz) | não se usa com `blob` | Troca a pasta do adaptador local. |
| `GESTNOW_BLOB_CONEXAO` | ausente | Cadeia de conexão de `<conta-anexos>` — segredo, só configuração do aplicativo | Só é lida com `blob`: por onde o container é alcançado. |
| `GESTNOW_BLOB_CONTAINER` | ausente (vale `anexos`) | `anexos` (o container privado do passo 2), ou omita | Só é lida com `blob`: nome do container. |
| `GESTNOW_PG_ADMIN_URL` | variável de usuário do Windows, criada uma vez: `postgresql://postgres:<senha>@localhost:5432/postgres` | não se usa no Azure | O `run.bat` e o `scripts/prepare_database.py` usam para criar o papel e os bancos locais. |
| `GESTNOW_DEV_PRINCIPAL` | ausente; com o e-mail de uma conta Microsoft simula o login no servidor local | não se usa no Azure | Faz o `scripts/dev_local.py` mandar o cabeçalho do principal do Static Web Apps, para ver o login de verdade e o acesso negado sem publicar. |
| `GESTNOW_BASE` | ausente (vale `http://localhost:4280`) | não se usa no Azure | Base das ferramentas `npm run varredura` e `npm run acessibilidade`, para apontá-las a outro endereço. |

Esta tabela é conferida pelo teste
`api/tests/plataforma/test_variaveis_documentadas.py`: o código do app e os
scripts são varridos pelas variáveis `GESTNOW_*` que leem, e a diferença —
para mais ou para menos — reprova.

## 5. As migrações contra o banco do Azure

Com a URL da seção 1, do seu computador (o IP já está liberado):

```powershell
cd api
$env:GESTNOW_DATABASE_URL = "postgresql://<usuario-admin>:<senha>@<servidor-pg>.postgres.database.azure.com:5432/gestnow?sslmode=require"
.venv\Scripts\python.exe -m alembic upgrade head
```

Ao terminar, o banco tem o esquema completo. Confira com o `psql` (opcional):

```sql
SELECT version_num FROM alembic_version;
```

## 6. O primeiro Admin

Ainda com a `GESTNOW_DATABASE_URL` da seção anterior na sessão, rode a carga
de produção. Ela é idempotente: cria a pessoa e o colaborador do e-mail
informado (perfil Admin, vínculo Timenow), os parâmetros iniciais e mais nada
— a base nasce vazia, sem demonstração:

```powershell
$env:GESTNOW_MODO = "producao"
$env:GESTNOW_ADMIN_EMAIL = "<e-mail-do-primeiro-admin>"
api\.venv\Scripts\python.exe scripts\seed_database.py
```

Saída esperada: `base de producao pronta: primeiro Admin e parametros
iniciais`. Esse e-mail é a pessoa que entra primeiro e cadastra os demais em
Configurações > Colaboradores.

## 7. Publicar o site (SWA CLI)

O token de publicação está no portal, no Static Web App: **Overview >
Manage deployment token**. Na raiz do repositório:

```
swa deploy --app-location app --output-location app --env production --deployment-token <token-de-publicacao>
```

O comando envia `app/` inteiro — inclusive o `staticwebapp.config.json` — e
publica em produção. **Não** passe `--api-location`: a API já foi publicada no
Function App (passo 3) e é o vínculo que a serve em `/api/*`. Para não deixar o
token no histórico, use `SWA_CLI_DEPLOYMENT_TOKEN` no ambiente.

## 8. Conferir

1. Abra `https://<endereço-do-swa>`. Sem sessão, o site manda para o login
   Microsoft (`/.auth/login/aad`).
2. Entre com o e-mail do primeiro Admin: a sidebar, os módulos e o Início
   abrem; o seletor de perfil **não** existe (modo produção).
3. Entre com uma conta Microsoft fora do cadastro: a tela de acesso negado
   aparece, nomeando a conta usada.
4. `https://<endereço-do-swa>/api/health` responde com o banco em `ok` e a
   revisão das migrações.
5. Anexe um arquivo em qualquer registro com anexos e confira o container
   `anexos` no portal — e que o download só funciona para quem alcança o
   registro.

## 9. Ligar o e-mail (quando quiser)

1. No **Microsoft Entra** (portal do Entra > *App registrations* > *New
   registration*): um registro de tenant único, nome `<registro-email>`.
2. Em **Certificates & secrets**, crie um segredo de cliente e guarde o
   **valor** na hora (só aparece uma vez).
3. Em **API permissions > Add a permission > Microsoft Graph > Application
   permissions**, escolha `Mail.Send` e clique em **Grant admin consent**.
   O envio sai da caixa `GESTNOW_GRAPH_REMETENTE`, que precisa existir.
4. No Function App (passo 4), preencha `GESTNOW_GRAPH_TENANT_ID`,
   `GESTNOW_GRAPH_CLIENT_ID`, `GESTNOW_GRAPH_CLIENT_SECRET` e
   `GESTNOW_GRAPH_REMETENTE`, e ponha `GESTNOW_ENVIO_EMAIL=ligado`.
5. O próximo envio (follow-up de ações, pauta de riscos ou tesouraria) sai de
   verdade e é registrado na trilha. Para voltar ao envio simulado, ponha a
   variável em `desligado`. Com o envio ligado e alguma variável vazia, a
   falha fica na trilha com o **nome** da variável que falta, nunca com o
   valor.

## 10. Conferência local do modo produção

Sem Azure: um banco descartável, as migrações, a carga de produção e o host
do Functions. O banco `gestnow` local já tem a demonstração; use outro nome
para ver a base de produção nascer vazia.

```powershell
psql -U postgres -p 5432 -c "CREATE DATABASE gestnow_prod OWNER gestnow"
$env:GESTNOW_DATABASE_URL = "postgresql://gestnow:<senha>@localhost:5432/gestnow_prod"
cd api
.venv\Scripts\python.exe -m alembic upgrade head
cd ..
$env:GESTNOW_MODO = "producao"
$env:GESTNOW_ADMIN_EMAIL = "<seu-e-mail>"
api\.venv\Scripts\python.exe scripts\seed_database.py
cd api
func start --port 7073
```

(O `func start` usa o `api\.venv` do projeto e lê o `api/local.settings.json`;
as variáveis de ambiente que você definiu na sessão têm precedência sobre o
arquivo — por isso o host sobe apontado para o banco descartável.)

No navegador ou no `curl`, com o host no ar:

* `GET http://localhost:7073/api/health` responde `ok` com a revisão.
* `GET http://localhost:7073/api/nav?caminho=/&projeto=portfolio` com o
  cabeçalho `x-ms-client-principal` (base64 do principal do e-mail cadastrado)
  devolve a sidebar; com um e-mail fora do cadastro, devolve 403 e a mensagem
  de e-mail não cadastrado; sem cabeçalho nenhum, 403 de login.

Ao terminar, `Ctrl+C` no `func` e remova o banco descartável:

```powershell
psql -U postgres -p 5432 -c "DROP DATABASE gestnow_prod"
```

## 11. Atualizar uma publicação

1. Migração nova: `cd api` e `GESTNOW_DATABASE_URL=<a do Azure>` +
   `.venv\Scripts\python.exe -m alembic upgrade head` (passo 5).
2. Carga nova: `scripts\seed_database.py` com `GESTNOW_MODO` e as demais
   variáveis da carga (passo 6) — é idempotente.
3. API nova: `cd api` e `func azure functionapp publish <app-funcoes>`.
4. Site novo: `swa deploy` do passo 7.

## Referências (Microsoft Learn)

* Provedor preconfigurado e login: *Authenticate and authorize Static Web
  Apps*.
* Vínculo com o Function App (plano Standard): *Bring your own functions to
  Azure Static Web Apps*.
* Runtimes das Functions gerenciadas (Python até 3.11): *Supported languages
  and runtimes in Azure Static Web Apps* e *Azure Static Web Apps hosting
  plans*.
