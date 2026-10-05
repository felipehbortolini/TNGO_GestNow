# Contrato de carregamento visual

Como o CSS e o JavaScript do Design System chegam em cada página — e o que
impede uma tela nova de nascer sem estilo.

---

## Por que este documento existe

No template original, `app/index.html` referenciava `/kyno-theme.css`. **O arquivo
não existia.** O `<link>` retornava 404 em silêncio, o `data-theme="kyno"` nunca se
aplicava, e todo o visual que aparecia vinha do DaisyUI via CDN com o tema padrão —
não com o tema Timenow.

Ninguém percebeu porque nada acusava. As cinco regras abaixo existem para que esse
tipo de falha não volte a passar despercebido.

---

## Regra 1 — O shell é o único lugar que carrega o Design System

`app/index.html` carrega, nesta ordem:

```html
<link rel="stylesheet" href="/ds/tokens.css" />
<link rel="stylesheet" href="/ds/shell.css" />
<link rel="stylesheet" href="/ds/patterns.css" />

<script defer src="/ds/icons.js"></script>
<script defer src="/ds/ui.js"></script>
<script defer src="/lib/alpine-ajax-0.12.7.min.js"></script>
<script defer src="/lib/alpinejs-3.14.8.min.js"></script>
```

**A ordem importa:** `tokens.css` define as variáveis que os outros dois consomem, e
`icons.js` define o `window.icon()` que o `ui.js` usa.

**O caminho absoluto importa mais ainda.** O `navigationFallback` reescreve qualquer
rota desconhecida para `/index.html`. Num deep link em `/exemplo/42`, um caminho
relativo `ds/tokens.css` resolveria como `/exemplo/ds/tokens.css` — 404, e a página
volta a nascer sem estilo. Sempre com barra no início.

**Sem CDN.** O kit inteiro é servido pelo próprio app. Isso preserva a decisão 8 da
arquitetura (bibliotecas vendorizadas) e elimina dependência de rede externa em
tempo de execução.

**O trio da tela (GestNow, D3).** Logo depois do Design System, e agrupados por
módulo, o shell vincula também o CSS e o JS de cada tela, em
`app/paginas/<modulo>/<tela>.css` e `.js`, com caminho absoluto. É assim que a
primeira execução já tem o visual de todas as telas sem que a view carregue nada.
Ver [PADROES-DE-PAGINA.md](PADROES-DE-PAGINA.md), "O trio da tela".

---

## Regra 2 — Fragmentos nunca carregam estilo próprio

Vale para `app/_views/`, `app/_components/` e todo template Jinja2 em
`api/src/templates/`.

Sem `<link>`, sem `<style>`, sem `<script src>`, sem `<html>`, `<head>` ou `<body>`.

O motivo é mecânico: o Alpine AJAX injeta o fragmento no DOM a cada navegação. Uma
tag de recurso ali dentro seria reinjetada toda vez — no melhor caso ignorada, no
pior reexecutada.

Precisa de estilo local? Vira classe em `ds/patterns.css`. Precisa de comportamento?
Vai por atributo do Alpine (`x-data`, `x-init`, `@click`), que é inerte até o Alpine
processar o nó.

No GestNow o estilo e o comportamento próprios de uma tela moram no trio da tela
(`app/paginas/<modulo>/<tela>.css` e `.js`), vinculado pelo shell e acionado pela
view por `x-init`; só o que se repete em três telas sobe para `ds/patterns.css`.

---

## Regra 3 — Fragmento acessado diretamente devolve o shell

Para `/api/*`, funciona: `is_alpine_request()` em `api/src/core/responses.py` confere
o cabeçalho `X-Alpine-Request` que o Alpine AJAX manda em toda requisição, e
redireciona para `/index.html` quem chega sem ele.

```python
if not is_alpine_request(req):
    return redirect_to("/index.html")
```

**Para os fragmentos estáticos de `_views/`, isso não é implementável no Azure SWA.**
O roteamento de Static Web Apps decide por caminho, não por cabeçalho — não há como
distinguir uma busca do Alpine AJAX de alguém digitando a URL. E o
`navigationFallback` não ajuda: ele só age quando não existe arquivo para a rota, e
o arquivo existe.

O que fica valendo:

| Situação | Comportamento |
|---|---|
| Sem sessão, acesso direto a `/_views/x.html` | 401 → redireciona para o login |
| Com sessão, acesso direto a `/_views/x.html` | Serve o fragmento cru, sem estilo |

O residual é cosmético, não uma falha de segurança: o conteúdo já é visível a quem
está autenticado; a página apenas aparece sem estilo.

Quem precisar fechar isso por completo tem o caminho aberto pelo próprio template:
servir as views pela API (`/api/views/{nome}`), como já se faz com `/api/nav`, e aí
o gate passa a cobri-las. O custo é abandonar a convenção `app/_views/*.html`
documentada na arquitetura — por isso o modelo não faz isso por padrão.

---

## Regra 4 — A ausência de estilo falha alto, não em silêncio

`ds/tokens.css` declara um sentinela:

```css
:root { --ds-carregado: 1; }
```

E o shell confere no boot. Se a variável não existir, o Design System não carregou,
e a página mostra o erro em vez de uma tela sem estilo:

```js
var carregado = getComputedStyle(document.documentElement)
  .getPropertyValue("--ds-carregado").trim();
if (!carregado) {
  document.body.innerHTML = "<pre>O Design System não carregou...</pre>";
}
```

É exatamente o mecanismo que faltava para o `/kyno-theme.css` faltante ser notado.

Para conferir que funciona: renomeie `app/ds/tokens.css` e recarregue. O app precisa
falhar com mensagem legível.

---

## Regra 5 — Porta automatizada

```bash
node scripts/verificar-padrao.mjs
```

| Verificação | Falha quando |
|---|---|
| `sem-cdn` | há `href`/`src` externo em `app/` (`docs/` é isento) |
| `sem-tailwind-daisyui` | aparece `bg-base-*`, `btn-primary`, `card-body`, `navbar`… |
| `fragmento-limpo` | há `<link>`, `<style>`, `<script src>` ou `<html>` em fragmento |
| `recurso-existe` | algum `href`/`src` local não existe no disco |
| `sem-uuid` | nome de asset em formato UUID |
| `sem-prefixo-de-app` | sobrou prefixo de projeto específico no código |
| `raiz-do-fragmento` | view de `_views/` não começa com `<main id="app-shell">` |
| `contrato-visual` | shell não carrega o DS, ou o sentinela sumiu |
| `colisao-css` | a mesma classe é declarada em dois arquivos do DS |
| `trio-da-tela` | uma tela da lista de navegação não tem view, CSS e JS vinculados no shell, ou uma view não tem item de navegação (`scripts/verificar-trio-da-tela.mjs`) |

A verificação `recurso-existe` é a que teria pego o `/kyno-theme.css` no dia em que
foi escrito. Rode antes de abrir PR e no CI.

---

## Resumo

| Onde | Carrega estilo? | Como |
|---|---|---|
| `app/index.html` | **Sim** | Único lugar; caminho absoluto; sem CDN |
| `app/paginas/<modulo>/<tela>.css` e `.js` | Não: o shell os vincula | O trio da tela; um par por tela, agrupado por módulo, caminho absoluto |
| `app/_views/*.html` | Não | Herda do shell |
| `app/_components/*.html` | Não | Herda do shell |
| `api/src/templates/**` | Não | Herda do shell |
