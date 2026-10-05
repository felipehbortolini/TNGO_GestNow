---
name: timenow-design-system
description: >
  Padrão visual e de página da Timenow para apps em Azure SWA + Functions V4 com
  Alpine AJAX. Use ao criar ou alterar qualquer tela, componente, fragmento Jinja2
  ou CSS neste repositório — inclusive ao escolher cor, espaçamento, classe ou
  estrutura de página. Substitui Tailwind e DaisyUI, que não são usados aqui.
---

# Timenow Design System

Camada visual única deste repositório. **Não existe Tailwind nem DaisyUI.** Se você
ia escrever `class="btn btn-primary"` ou `bg-base-100`, pare: é outro sistema.

## Regras que não se negociam

1. **Só o shell carrega estilo.** `app/index.html` carrega `/ds/*.css` e `/ds/*.js`,
   com caminho absoluto. Fragmento nunca traz `<link>`, `<style>` ou `<script src>`.
2. **Nenhum valor de cor, espaçamento, raio ou sombra fixo.** Tudo por token.
3. **Sem CDN.** Nada em `app/` pode apontar para host externo.
4. **Sem prefixo de projeto em nome global.** O namespace JS é `TN`.
5. **Rode a porta antes de entregar:** `node scripts/verificar-padrao.mjs`.

## Onde está cada coisa

| Arquivo | Conteúdo |
|---|---|
| `app/ds/tokens.css` | Variáveis e componentes atômicos |
| `app/ds/shell.css` | Sidebar, layout de página, telas de guarda |
| `app/ds/patterns.css` | KPIs, toolbar, facepile, linhas, filtros |
| `app/ds/icons.js` | `icon(nome, tamanho)` — 44 ícones |
| `app/ds/ui.js` | `TN`: toast, modal, confirmação, loading |

Uma classe **nunca** é declarada em dois desses arquivos.

## Tokens essenciais

```css
--verde-500: #00A793;   /* ação primária, ícone, foco */
--verde-700: #00776A;   /* texto sobre fundo verde claro */
--brand-title: #006357; /* TODO título */
--text-primary: #2A2A2A;
--text-secondary: #7D7D7D;
--borda: #DEE2E6;
--r-sm: 4px; --r-md: 8px; --r-lg: 12px;
--space-sm: 8px; --space-lg: 16px; --space-xl: 24px; --space-xxl: 32px;
```

Semânticos: `--ok-*`, `--warn-*`, `--erro-*`, `--azul-*`, `--frio-*`, `--roxo-*`.
Regra: **50 no fundo, 700/800 no texto**. Tom 500 nunca é texto sobre fundo claro.

Elevação vem da **borda**, não da sombra.

## Anatomia de página

```html
<main id="app-shell" class="content">
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="h-dash">Título</h1>
        <p class="page-head__sub">Contexto em uma linha.</p>
      </div>
      <div class="page-head__actions">
        <button class="btn btn--primary">Ação primária</button>
      </div>
    </div>
    <div class="card">
      <div class="card__head"><h2 class="h-card4">Seção</h2></div>
      <div class="card__body">…</div>
    </div>
  </div>
</main>
```

A raiz de toda view em `_views/` é `<main id="app-shell" class="content">`.

## Classes mais usadas

```
btn btn--primary | btn--secondary | btn--ghost | btn--danger | btn--sm | btn--lg
card card__head card__body | iconbtn
pill pill--ok | --warn | --erro | --fix | --neutral
tbl-wrap tbl | td-num td-center num fw-600
fgrid field field--full input input--erro field__erro
aviso aviso--ok | --erro | --warn | --info
empty guard spinner | lista-simples lista-simples__item
kpis kpi kpi--ok | toolbar busca | linha linha__titulo | facepile mini-avatar
h-dash h-card1 h-card3 h-card4 h-card5 body-txt muted hint sr-only
```

## Ícones

```html
<span x-init="$el.innerHTML = window.icon('checkCircle', 16)" aria-hidden="true"></span>
```

Disponíveis: `add`, `arrowLeft`, `arrowRight`, `at`, `building`, `calendar`, `check`,
`checkCircle`, `chevronDown`, `chevronRight`, `clock`, `copy`, `dismiss`, `download`,
`edit`, `errorCircle`, `eye`, `eyeOff`, `file`, `fileAdd`, `filter`, `gear`, `info`,
`key`, `layers`, `listaNumeros`, `listaPontos`, `lock`, `mail`, `money`, `person`,
`pin`, `play`, `refresh`, `search`, `send`, `shield`, `signout`, `sort`, `sparkle`,
`table`, `taskList`, `trash`, `userPlus`, `warning`.

Ícone fora dessa lista: acrescente em `ds/icons.js`, não use arquivo solto.

## JavaScript

```js
TN.toast("Salvo.", "ok");                 // ok | erro | aviso
await TN.confirmarExclusao({ rows: [...] });
await TN.confirmarSaida();
TN.loading(true, "Salvando...");
TN.esc(txt); TN.fmtDate(d); TN.avatar(nome, 38);
```

Do servidor, por cabeçalho:

```python
resposta.headers["X-TN-Toast"] = quote("Registro criado.")
resposta.headers["X-TN-Toast-Tipo"] = "ok"
```

## Backend

```python
@bp.route(route="exemplo", methods=["GET"])
def listar(req: func.HttpRequest) -> func.HttpResponse:
    if not is_alpine_request(req):
        return redirect_to("/index.html")
    return AlpineAjaxResponse(
        template_name="exemplo/list.html",
        context={"registros": registros},
        request=req,
    )
```

Template Jinja2 estende `base_fragment.html` e usa `{{ target_id }}` — nunca id fixo.
Validação falha com **422** e o formulário volta preenchido com as mensagens.

## Armadilhas verificadas no navegador

**1. Alvo do `x-target` que não vier na resposta é ESVAZIADO.** Se o formulário
declara `x-target="form resumo lista"`, toda resposta — inclusive o 422 — precisa
trazer os três. Use um template com raízes irmãs (ver `exemplo/multi.html`), com o
miolo de cada bloco num partial reaproveitável.

**2. Nunca interpole texto do banco numa expressão Alpine.** `{{ x | tojson }}` é
marcado como seguro, as aspas duplas fecham o atributo e a expressão chega truncada.
Passe por `data-*` e leia de `$el.dataset`.

**3. Eventos do Alpine AJAX 0.12.7:** `detail` tem `{ok, redirected, url, status,
html, raw, headers}`. **Não existe `detail.xhr` nem `ajax:after`.** `headers` é um
objeto `Headers` — use `.get()`. `ajax:sent` é o último a disparar. `ajax:error`
dispara em todo status fora de 2xx, 422 incluído.

**4. Cabeçalho HTTP é latin-1.** Mensagem com acento vai com `quote()`.

## Os cinco estados

Toda tela com dados trata: carregando, vazio de origem, vazio por filtro, erro e sem
permissão. Vazio de origem e vazio por filtro **não são o mesmo estado**.

## Acessibilidade

- Botão só de ícone: `aria-label`
- Campo: `<label for>`; em erro, `aria-invalid` + `aria-describedby`
- Item de navegação ativo: `aria-current="page"`
- Imagem decorativa: `alt=""`
- Estado nunca só por cor

## Antes de entregar

```bash
node scripts/verificar.mjs
```

Roda ruff, ty, eslint e o padrão Timenow — as cinco etapas obrigatórias. O fluxo
completo de desenvolvimento está na skill `padrao-de-codigo`.

Detalhes em `docs/`: `CONTRATO-VISUAL.md`, `DESIGN-SYSTEM.md`, `COMPONENTES.md`,
`PADROES-DE-PAGINA.md`, `CONVENCOES.md`, `PADRAO-DE-CODIGO.md`,
`CHECKLIST-NOVA-PAGINA.md`.
