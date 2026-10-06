# API — Azure Functions V4 (Python)

Backend serverless do modelo. Modelo de programação V2, com `func.Blueprint`.

Salvo `/api/health`, **todo endpoint devolve fragmento de HTML**, não JSON. É a
decisão 1 da arquitetura: o servidor é dono da renderização e o cliente só troca
pedaços de DOM. Ver `../docs/ARCHITECTURE.md`.

---

## Estrutura

```
api/
├── function_app.py          registro dos blueprints
├── host.json                extension bundle [4.*, 5.0.0)
├── local.settings.json      configuração de desenvolvimento
├── pyproject.toml           dependências (Python ≥3.13) — fonte de verdade
├── uv.lock                  versões travadas — não editar à mão
├── requirements.txt         export do lock, para deploy sem uv (ver Dependências)
└── src/
    ├── blueprints/
    │   ├── health.py        GET  /api/health          → JSON
    │   ├── nav.py           GET  /api/nav             → sidebar
    │   ├── api_routes.py    GET  /api/items
    │   │                    GET  /api/greet-form
    │   │                    POST /api/greet
    │   └── exemplo.py       CRUD de referência
    ├── core/
    │   ├── jinja_env.py     ambiente Jinja2
    │   └── responses.py     AlpineAjaxResponse, is_alpine_request, redirect_to
    └── templates/           fragmentos e partials
```

---

## Rodar

Da raiz do modelo, `.\scripts\rodar.ps1` cobre os dois casos abaixo sozinho —
detecta se `swa`/`func` funcionam e escolhe. Os comandos diretos, para quem
prefere rodar à mão:

Junto com o front, pelo SWA CLI (recomendado — é o que simula `/.auth/me`):

```bash
swa start --config swa-cli.config.json
```

Só a API:

```bash
uv sync && func start
```

---

## Acrescentar um endpoint

```python
@bp.route(route="minha-rota", methods=["GET"])
def minha_rota(req: func.HttpRequest) -> func.HttpResponse:
    if not is_alpine_request(req):
        return redirect_to("/index.html")

    return AlpineAjaxResponse(
        template_name="meu_recurso/list.html",
        context={"registros": registros},
        request=req,
    )
```

Quatro pontos obrigatórios:

1. **Gate primeiro.** `is_alpine_request()` barra acesso direto do navegador.
2. **`AlpineAjaxResponse`**, nunca `HttpResponse` com HTML na mão.
3. **`request=req`**, para o `X-Alpine-Target` ser lido.
4. **Sem `target_id` fixo** — só quando a resposta muda de destino de propósito,
   como o POST que devolve a lista no lugar do formulário.

O template estende `base_fragment.html` e usa `{{ target_id }}` na raiz.

---

## Validação

Falha responde **422** com o formulário reexibido, os valores digitados de volta e
as mensagens nos campos:

```python
if erros:
    return AlpineAjaxResponse(
        template_name="exemplo/form.html",
        context={"valores": valores, "erros": erros},
        request=req,
        status_code=422,
    )
```

O Alpine AJAX troca o fragmento igual, sem tratamento especial no cliente.

---

## Feedback ao usuário

Por cabeçalho de resposta — a página não precisa saber:

```python
resposta.headers["X-TN-Toast"] = quote("Registro criado.")
resposta.headers["X-TN-Toast-Tipo"] = "ok"   # ok | erro | aviso
```

`app/ds/ui.js` escuta `ajax:success` e converte em toast.

---

## Dependências

Fonte de verdade: `pyproject.toml`. `uv.lock` trava as versões exatas;
`requirements.txt` é a exportação desse lock para quem faz deploy sem `uv`.

| Pacote | Papel | Direto ou transitivo |
|---|---|---|
| `azure-functions` | Runtime | direto |
| `jinja2` | Templates | direto |
| `markupsafe` | Escape de HTML | transitivo (jinja2, werkzeug) |
| `werkzeug` | Usado internamente pelo `azure-functions` | transitivo |
| `ruff` (dev) | Lint e formatação | direto, só em desenvolvimento |
| `ty` (dev) | Verificação de tipos | direto, só em desenvolvimento |

`ruff` e `ty` ficam **no projeto**, não no sistema. Instalá-los globalmente
faria a versão depender da máquina de cada pessoa, e a mesma base de código
passaria num lugar e reprovaria no outro. Presos no `uv.lock`, todo mundo roda
exatamente a mesma versão. Suas regras estão configuradas neste
`pyproject.toml`, comentadas uma a uma — ver
[PADRAO-DE-CODIGO.md](../docs/PADRAO-DE-CODIGO.md).

`requirements.txt` existe porque o **deploy real do Azure Functions em Linux
precisa dele**: o build do Oryx procura esse arquivo na raiz de `api/` e roda
`pip install -r requirements.txt` sozinho — não é um artefato de conveniência,
é o que o deploy consome. `uv.lock`, ao contrário, está listado em `.funcignore`
e não vai para o pacote implantado.

**Ao mudar uma dependência**, regenere os dois na mesma hora:

```bash
uv lock
uv export --format requirements.txt --no-dev --no-hashes -o requirements.txt
```

Esquecer o segundo comando deixa `requirements.txt` desatualizado em relação ao
`pyproject.toml` sem nenhum aviso — o deploy simplesmente instala a versão antiga.

> **`httpx2` foi removida em 13/08/2026** (histórico). Nenhum código importava
> cliente HTTP, e o pacote — publicado em 24/07/2026 junto de `httpcore2` — tem
> nome adjacente ao canônico `httpx`, que não constava do lockfile. Como não era
> usada, foi retirada em vez de auditada. `uv.lock` e `requirements.txt` já
> refletem a remoção. Se for intencional, reinsira a linha em `pyproject.toml` e
> regenere os dois arquivos acima. Ver C7 em `../docs/AUDITORIA-BASELINE.md`.

---

## Persistência

`exemplo.py` guarda tudo em memória, e o estado se perde quando o worker recicla.
É de propósito: deixa o exemplo rodar sem provisionar nada.

Para valer, acrescente `azure-cosmos` ou `sqlalchemy` ao `pyproject.toml` e a string
de conexão em `local.settings.json` e no portal do Azure.
