# API do Timenow GestNow

Backend em Azure Functions V4, modelo de programação V2, com blueprints. Exceto por `/api/health`, as rotas de tela devolvem fragmentos HTML para o Alpine AJAX.

## Estado desta entrega

O backend contém as rotas de plataforma necessárias ao shell e a camada de banco:

| Blueprint | Rota | Resposta |
|---|---|---|
| `health.py` | `GET /api/health` | JSON de saúde, com o estado do banco e a revisão da migração |
| `nav.py` | `GET /api/nav` | Fragmento HTML da sidebar |

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
* `src/core/routing.py` — `fragment_route`: gate do Alpine, unidade de trabalho e o mapa 403/409/422; `on_error` re-renderiza o formulário do módulo com o que a pessoa digitou. A resolução de usuário e a permissão chegam na ISSUE-011.

Os erros de domínio ficam em `src/core/errors.py`: `AccessDeniedError` (403), `InvalidDataError` (422) e `VersionConflictError` (409). O fragmento comum de erro é `src/templates/comum/erro.html`.

## Parâmetros versionados

`src/modulos/configuracoes/service.py` entrega a versão vigente de cada grupo numa data (`current_parameters`, `current_group` e as versões individuais), semeia a versão 1 dos 14 grupos de forma idempotente (`seed_initial_parameters`) e grava uma nova versão do grupo com autor, vigência e justificativa obrigatória (`save_parameter_group`). As regras da seção 7.4 do README do protótipo ficam em `validation.py`, uma função por regra, ligadas ao campo do formulário. A tela e as rotas de parâmetros são da ISSUE-076.

## Testes

O `tests/conftest.py` recria o `gestnow_teste` pelas migrações a cada execução — um banco vazio sobe até a última revisão — e roda cada teste dentro de uma transação desfeita no fim. Nenhum teste toca o banco `gestnow`.

```powershell
cd api
.venv\Scripts\python.exe -m pytest
```

## Desenvolvimento local

Na raiz do repositório, use `run.bat`. Ele prepara `api/.venv` na primeira execução, prepara o banco e inicia `scripts/dev_local.py`, que serve `app/`, simula a sessão local e encaminha `/api/health` e `/api/nav` aos blueprints reais. Esse caminho não depende do SWA CLI nem do Azure Functions Core Tools.

Para rodar o host real do Azure Functions, instale as dependências da API e use `func start`. A validação de deploy continua dependendo do SWA CLI e do host do Functions.

## Adicionar uma rota de fragmento

As rotas de tela devem conferir o cabeçalho Alpine AJAX e renderizar com `AlpineAjaxResponse`. A fachada e os módulos serão introduzidos pelas issues correspondentes; nenhuma regra de negócio deve ser implementada diretamente na rota.

```python
@bp.route(route="minha-rota", methods=["GET"])
def list_records(req: func.HttpRequest) -> func.HttpResponse:
    if not is_alpine_request(req):
        return redirect_to("/index.html")

    return AlpineAjaxResponse(
        template_name="meu_modulo/lista.html",
        context={"registros": records},
        request=req,
    )
```

O template Jinja2 estende `base_fragment.html` e usa `{{ target_id }}` na raiz. Validações de formulário retornam HTTP 422 com os valores digitados e erros por campo.

## Dependências e configuração local

`pyproject.toml` é a fonte das dependências Python e `uv.lock` registra suas versões. `requirements.txt` contém apenas as dependências de produção usadas pelo deploy do Azure. Configurações locais, inclusive `local.settings.json`, não devem ser versionadas.
