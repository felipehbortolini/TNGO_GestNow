# Convenções

---

## Idioma

| Onde | Idioma |
|---|---|
| Interface, texto ao usuário | **Português** |
| Nome de classe CSS | Português (`.linha`, `.busca`, `.acoes-rodape`) |
| Nome de variável e função em JS | Português |
| Código Python: nome de função, docstring, comentário | **Inglês** |
| Nome de rota | Português, minúsculo, com hífen (`/api/atividade-form`) |

O Python fica em inglês porque convive com a API do Azure Functions, que é em
inglês — misturar os dois no mesmo arquivo lê pior do que assumir um.

Comentário explica **por que**, não o que. Se o código precisa de comentário para
dizer o que faz, reescreva o código.

---

## Nomenclatura CSS — BEM

```
.bloco
.bloco__elemento
.bloco--variante
.is-estado
```

```css
.linha { }
.linha__titulo { }
.kpi--warn { }
.tab.is-active { }
```

Estado usa o prefixo `is-` como classe separada, porque é alternado por JavaScript:
`is-active`, `is-out`, `is-vazio`.

**Nada de nome de domínio no kit.** `.ata-row` virou `.linha`, `.ma-toolbar` virou
`.toolbar`. O Design System não pertence a nenhum projeto, e um app que fala de
"ata" não deve emprestar seu vocabulário para o próximo.

---

## Namespace JavaScript

Um único global: **`TN`**, definido em `ds/ui.js`.

```js
TN.toast("Salvo.");
TN.confirmarExclusao({ ... });
```

Mais `window.icon()` e `window.LOGO_FULL`, de `ds/icons.js`.

O piloto usava `CAA_UI`, `CAA_Router`, `CAA_Modais` e mais quatro — a sigla do app
"Central de Ações e Atas". Sete globais carregando o nome de um projeto num kit que
serve a todos. Se precisar de mais superfície, ela entra dentro de `TN`.

---

## Arquivos e pastas

| Tipo | Convenção | Exemplo |
|---|---|---|
| View | `snake_case.html` em `_views/` | `minhas_atas.html` |
| Componente | `snake_case.html` em `_components/` | `dica.html` |
| Fragmento Jinja2 | `pasta/nome.html` por recurso | `exemplo/list.html` |
| Blueprint | `snake_case.py` | `atividades.py` |
| Doc | `MAIUSCULA-COM-HIFEN.md` | `PADROES-DE-PAGINA.md` |
| Asset | `tipo-descricao.ext` | `ilustra-acesso-negado.png` |

**Asset nunca com nome UUID.** Não dá para auditar, e ninguém lê
`85be19f1-70be-….gif` e entende que é o spinner.

---

## Fragmento, partial e componente

Três coisas diferentes, e confundi-las gera bug:

| Tipo | Onde | Estende a base? | Tem id? | Como chega |
|---|---|---|---|---|
| **View** | `app/_views/` | — | `app-shell` | `$ajax` do shell |
| **Componente** | `app/_components/` | — | próprio | `x-init` da view |
| **Fragmento** | `api/src/templates/` | sim | `{{ target_id }}` | resposta de endpoint |
| **Partial** | `api/src/templates/` | **não** | nenhum | `{% include %}` |

Partial não tem raiz nem id porque nunca é alvo de `x-target` — só existe para ser
incluído. Ver `exemplo/row.html`.

**Componente estático ou fragmento de API?** Se precisa de dados do servidor, é
fragmento de API. Se é fixo e reaparece em várias views, é componente. Critério
completo em `app/_components/dica.html`.

---

## Valor do servidor dentro de expressão Alpine

**Nunca interpole texto livre dentro de um atributo `x-data`, `@click` ou
`:class`.** Vai por `data-*`, e a expressão lê de `$el.dataset`.

```html
<!-- ERRADO — a primeira aspa do valor fecha o atributo -->
<div x-data="{ justificativa: {{ atividade.observacoes | tojson }} }">

<!-- CERTO -->
<div data-justificativa="{{ atividade.observacoes }}"
     x-data="{ justificativa: $el.dataset.justificativa }">
```

O motivo é mecânico: `| tojson` marca o resultado como seguro, então o
autoescape do Jinja não toca nas aspas duplas — elas saem cruas e encerram o
atributo no meio. O Alpine recebe uma expressão truncada, o componente inteiro
não inicializa e **nada avisa**: a tela abre, os campos aparecem e nenhum
cálculo funciona. Em `data-*` o autoescape faz o trabalho certo.

Isso já aconteceu duas vezes neste repositório — em `exemplo/row.html`, no
modelo, e no painel de realizado desta aplicação.

**A exceção é o payload de gráfico**, que vai dentro de
`<script type="application/json">`. Ali é conteúdo de elemento, não valor de
atributo, e `| tojson` é exatamente a ferramenta certa.

---

## Rotas de API

```python
@bp.route(route="exemplo", methods=["GET"])
def listar(req: func.HttpRequest) -> func.HttpResponse:
    if not is_alpine_request(req):
        return redirect_to("/index.html")
    return AlpineAjaxResponse(template_name="exemplo/list.html",
                              context={...}, request=req)
```

Toda rota de fragmento: gate primeiro, `AlpineAjaxResponse` depois, `request=req`
sempre. Nunca fixe `target_id` — exceto quando a resposta muda de destino de
propósito, como o POST que devolve a lista em vez do formulário.

---

## Feedback ao usuário

Do servidor, por cabeçalho — a página não precisa saber:

```python
resposta.headers["X-TN-Toast"] = quote("Registro criado.")
resposta.headers["X-TN-Toast-Tipo"] = "ok"   # ok | erro | aviso
```

`ds/ui.js` escuta `ajax:success` e transforma em toast. Erro de rede vira toast
automaticamente em `ajax:error`.

---

## Git

Mensagem de commit no imperativo, em português:

```
Adiciona filtro por situação na listagem de exemplo
Corrige contraste do verde-100 na rampa da marca
```

Antes de abrir PR: `node scripts/verificar-padrao.mjs` e a
[CHECKLIST-NOVA-PAGINA.md](CHECKLIST-NOVA-PAGINA.md).
