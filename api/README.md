# API do Timenow GestNow

Backend em Azure Functions V4, modelo de programação V2, com blueprints. Exceto por `/api/health`, as rotas de tela devolvem fragmentos HTML para o Alpine AJAX.

## Estado desta entrega

O backend contém apenas as rotas de plataforma necessárias ao shell:

| Blueprint | Rota | Resposta |
|---|---|---|
| `health.py` | `GET /api/health` | JSON de saúde para o indicador da navegação |
| `nav.py` | `GET /api/nav` | Fragmento HTML da sidebar |

As telas e rotas de exemplo do Padrão foram removidas. Ainda não há módulos de domínio nem persistência; o banco Postgres será preparado na ISSUE-005.

## Desenvolvimento local

Na raiz do repositório, use `run.bat`. Ele prepara `api/.venv` na primeira execução e inicia `scripts/dev_local.py`, que serve `app/`, simula a sessão local e encaminha `/api/health` e `/api/nav` aos blueprints reais. Esse caminho não depende do SWA CLI nem do Azure Functions Core Tools.

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
