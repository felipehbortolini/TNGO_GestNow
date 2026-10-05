# Arquitetura — Timenow GestNow (Azure SWA + Functions V4)

## Visão geral

Esqueleto de aplicação web sobre **Azure Static Web Apps** com backend serverless em
**Azure Functions V4** (Python). Segue o padrão hipermídia: **Alpine.js**,
**Alpine AJAX**, **Jinja2** e o **Timenow Design System**. Sem bundler, sem etapa de
build, sem framework pesado.

Herdado de `Template_Framework_Desenvolvimento`. Os 13 padrões de arquitetura, as 4
convenções e as 5 rotas do template original foram preservados — três saíram
reforçados. A única mudança estrutural é a camada visual: o Tailwind e o DaisyUI
saíram, e o Design System entrou como camada única.

---

## Estrutura

```
.
├── app/                          # Front-end estático
│   ├── index.html                # Shell: sidebar, área de conteúdo, raízes de overlay
│   ├── login.html                # Portão de login (público)
│   ├── ds/                       # Design System — fonte visual única
│   │   ├── tokens.css            #   variáveis + componentes base
│   │   ├── shell.css             #   sidebar, layout de página, telas de guarda
│   │   ├── patterns.css          #   KPIs, toolbar, facepile, linhas, filtros
│   │   ├── icons.js              #   icon(nome, tamanho) + LOGO_FULL
│   │   ├── ui.js                 #   TN: toast, modal, confirmação, loading
│   │   └── assets/               #   ilustrações e GIFs, nome semântico
│   ├── _views/                   # Páginas — fragmentos de #app-shell
│   ├── _components/              # Fragmentos estáticos reutilizáveis
│   ├── lib/                      # Alpine.js e Alpine AJAX vendorizados
│   └── staticwebapp.config.json  # Rotas, auth, cabeçalhos
│
├── api/                          # Back-end (Azure Functions V4, Python ≥3.13)
│   ├── function_app.py           # Registro dos blueprints
│   └── src/
│       ├── blueprints/
│       │   ├── health.py         # GET  /api/health          → JSON (a exceção)
│       │   ├── nav.py            # GET  /api/nav             → sidebar
│       │   ├── api_routes.py     # GET  /api/items
│       │   │                     # GET  /api/greet-form
│       │   │                     # POST /api/greet
│       │   └── exemplo.py        # CRUD de referência
│       ├── core/
│       │   ├── jinja_env.py      # Ambiente Jinja2
│       │   └── responses.py      # AlpineAjaxResponse, is_alpine_request
│       └── templates/            # Fragmentos Jinja2
│
├── docs/                         # Esta documentação
├── scripts/verificar-padrao.mjs  # Porta de qualidade
└── .agents/skills/               # Skills de agente (alpine-ajax, design system)
```

---

## Pilha

| Camada | Tecnologia | Papel |
|---|---|---|
| Reatividade | Alpine.js 3.14.8 | 15 KB, sem build, declarativo |
| Troca de fragmento | Alpine AJAX 0.12.7 | `x-target`, `$ajax`, formulários |
| Visual | Timenow Design System | CSS próprio, ~24 KB, sem build |
| Compute | Azure Functions V4 (Python) | Modelo V2, `func.Blueprint` |
| Templates | Jinja2 ≥3.1.6 | Fragmentos com herança |
| Hospedagem | Azure Static Web Apps | Estáticos + `/api/*` + `/.auth/*` |

---

## Fluxo de requisição

### Boot

```
Carrega index.html
    │
    ├─ confere o sentinela --ds-carregado
    │     ausente → mostra erro e para (Regra 4)
    │
    ├─ GET /.auth/me
    │     sem sessão  → $ajax('/login.html')
    │     com sessão  → revela a sidebar
    │                   $ajax('/api/nav',   { target: 'main-nav'  })
    │                   $ajax(deep link,    { target: 'app-shell' })
```

### Navegação

```
Clique em <a x-target="app-shell" href="/_views/exemplo.html">
    │
    ▼  SWA serve o fragmento estático
    ▼  Alpine AJAX troca o conteúdo de <main id="app-shell">
Sem recarregar a página. Sem rebaixar Alpine nem o Design System.
```

### Chamada de API

```
<a href="/api/items" x-target="page2-list:fragment-list">
    │
    ▼  Cabeçalho X-Alpine-Target: page2-list:fragment-list
    ▼  AlpineAjaxResponse resolve target_id="fragment-list"
    ▼  Renderiza items/list.html sobre base_fragment.html
    ▼  Resposta: <div id="fragment-list">…</div>
    ▼  Alpine AJAX injeta em #page2-list
```

---

## Decisões de arquitetura

As 13 decisões do template, preservadas. Onde há mudança, está anotada.

**1. Hipermídia: fragmentos HTML, não JSON.** A API devolve HTML pronto. Zero
templating no cliente. `/api/health` é a única exceção.

**2. Jinja2 com fragmento base.** Todo template estende `base_fragment.html`, que
fornece a raiz com o `id` correto por construção.

**3. `AlpineAjaxResponse` centraliza a renderização.** Resolve o `target_id` do
cabeçalho, injeta no contexto, renderiza e ajusta os headers.

**4. O cliente é dono do destino.** Quem declara onde o fragmento vai é o `x-target`.
O servidor nunca fixa id. Aceita alias: `x-target="pagina:resposta"`.

**5. Alpine AJAX, não HTMX.** Integra com a reatividade do Alpine, que o app já usa.

**6. Sem bundler, sem build.** *Reforçado:* a saída do Tailwind eliminou o único item
que o template previa vir a precisar de compilação para produção.

**7. Carga declarativa com `x-init` + `$ajax`.** Componentes e sub-seções se carregam
sozinhos. Ver `_views/exemplo.html`.

**8. Bibliotecas vendorizadas.** *Estendido:* o Design System também é local. `app/`
não faz nenhuma requisição externa.

**9. Navegação como fragmento de servidor.** *Alterado:* segue vindo de `/api/nav`,
mas agora é a sidebar de 300px, não a navbar horizontal. Acrescentar página é
acrescentar uma entrada em `ITENS_NAV`.

**10. Portão de login.** `/login.html` é estático e público, para não depender da API
que exige sessão.

**11. Autenticação delegada ao Azure SWA.** `/.auth/me`, `/.auth/login/aad`,
`/.auth/logout`.

**12. Gate de fragmento.** *Estendido:* `is_alpine_request()` protege `/api/*`, e o
`staticwebapp.config.json` restringe `_views/` e `_components/` a sessão
autenticada. Limite conhecido em `CONTRATO-VISUAL.md`, Regra 3.

**13. `/api/health` em JSON.** Único endpoint não-HTML. A sidebar mostra o indicador.

**14. Design System como camada visual única.** *Novo.* Tokens, componentes e padrões
em `app/ds/`. Sem Tailwind, sem DaisyUI, sem CDN. Ver `CONTRATO-VISUAL.md`.

---

## Convenções

### Blueprints — `api/src/blueprints/`

1. Criam `bp = func.Blueprint()`.
2. Definem rotas com `@bp.route(...)`.
3. Devolvem `AlpineAjaxResponse` para HTML, `func.HttpResponse` para JSON (só health).
4. Passam `request=req`, para o `X-Alpine-Target` ser lido.
5. Barram acesso direto com `is_alpine_request()`.

### Templates Jinja2 — `api/src/templates/`

**Fragmento** — resposta de endpoint:

1. Estende `base_fragment.html`.
2. Conteúdo dentro de `{% block fragment %}`.
3. Nunca fixa `id`: usa `{{ target_id }}`.
4. Sem `<html>`, `<head>`, `<body>`, `<link>` ou `<script src>`.
5. Precisa de outra raiz (`<aside>`, `<table>`)? Sobrescreve `{% block root %}`.

**Partial** — só incluído por outro template, como `exemplo/row.html`: não estende a
base, não tem raiz nem id próprio, entra por `{% include %}`.

### Views — `app/_views/`

1. Raiz é `<main id="app-shell" class="content">`.
2. Fragmento puro, sem tag de recurso.
3. Autocontida na área de conteúdo.

### Componentes — `app/_components/`

Estáticos e reutilizáveis, carregados por `x-init="$ajax(...)"`. Se precisar de dados
do servidor, é fragmento de API, não componente. Critério em `_components/dica.html`.

---

## Rotas

| Método | Rota | Resposta | Descrição |
|---|---|---|---|
| `GET` | `/api/health` | JSON | Verificação de saúde |
| `GET` | `/api/nav` | Fragmento | Sidebar |
| `GET` | `/api/items` | Fragmento | Lista de itens *(do template)* |
| `GET` | `/api/greet-form` | Fragmento | Formulário de saudação *(do template)* |
| `POST` | `/api/greet` | Fragmento | 200 saudação, 422 formulário com erro *(do template)* |
| `GET` | `/api/exemplo` | Fragmento | Lista do CRUD; aceita `?busca=` |
| `GET` | `/api/exemplo-resumo` | Fragmento | Faixa de KPIs |
| `GET` | `/api/exemplo-form` | Fragmento | Formulário vazio |
| `POST` | `/api/exemplo` | Fragmento | 200 lista, 422 formulário com erro |
| `DELETE` | `/api/exemplo/{id}` | Fragmento | Exclui e devolve a lista |

---

## Desenvolvimento local

```bash
npm install -g @azure/static-web-apps-cli azure-functions-core-tools@4
```

```bash
cd api && uv sync && cd ..
```

```bash
swa start --config swa-cli.config.json
```

Serve `app/` na porta 4280, encaminha `/api/*` para a 7071 e simula `/.auth/me`.

---

## Produção

- **App location:** `app/`
- **API location:** `api/`
- **Output location:** `app/` (sem build, a saída é a própria fonte)

---

## Caminho de crescimento

| Necessidade | Direção |
|---|---|
| Página nova | Fragmento em `_views/` + entrada em `ITENS_NAV` |
| Quebrar página grande | Extrair para `_components/`, carregar com `x-init` |
| Endpoint novo | Rota no blueprint + template estendendo `base_fragment.html` |
| Banco de dados | `azure-cosmos` ou `sqlalchemy` no `pyproject.toml` |
| API JSON | Endpoints JSON ao lado dos de fragmento, como `health.py` |
| Testes | `pytest` na `api/`; Playwright para ponta a ponta |
| CI/CD | GitHub Actions do Azure SWA + `scripts/verificar-padrao.mjs` |
