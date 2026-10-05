# Componentes

Inventário com markup copiável. Tudo em `ds/tokens.css`, salvo indicação.

---

## Botões

```html
<button class="btn btn--primary">Salvar</button>
<button class="btn btn--secondary">Cancelar</button>
<button class="btn btn--ghost">Ver mais</button>
<button class="btn btn--danger">Excluir</button>

<button class="btn btn--primary btn--sm">Pequeno</button>
<button class="btn btn--primary btn--lg">Grande</button>
<button class="btn btn--primary" disabled>Desabilitado</button>
```

Botão só de ícone precisa de `aria-label`:

```html
<button class="iconbtn" aria-label="Fechar"
        x-init="$el.innerHTML = window.icon('dismiss', 18)"></button>
```

> `.btn--ghost` não sublinha de propósito: botão não deve se passar por link.

---

## Card

```html
<div class="card">
  <div class="card__head">
    <h2 class="h-card4">Título</h2>
    <button class="btn btn--ghost btn--sm">Ação</button>
  </div>
  <div class="card__body">…</div>
</div>
```

---

## Pills

```html
<span class="pill pill--ok">Concluído</span>
<span class="pill pill--warn">Rascunho</span>
<span class="pill pill--erro">Em atraso</span>
<span class="pill pill--fix">Em andamento</span>
<span class="pill pill--neutral">Cancelado</span>
```

Sempre com rótulo em texto — estado nunca se comunica só por cor.

---

## Tabela

```html
<div class="tbl-wrap">
  <table class="tbl">
    <thead>
      <tr><th>Título</th><th class="td-num">Valor</th><th class="td-center">Ações</th></tr>
    </thead>
    <tbody>
      <tr><td class="fw-600">Item</td><td class="num">42</td><td class="td-center">…</td></tr>
    </tbody>
  </table>
</div>
```

`.tbl-wrap` é obrigatório: é o que dá rolagem horizontal no celular sem empurrar a
página. `.num` aplica `tabular-nums`, para os dígitos alinharem entre linhas.

---

## Formulário

```html
<div class="fgrid">
  <div class="field field--full">
    <label for="titulo">Título</label>
    <input id="titulo" class="input" placeholder="…" />
  </div>

  <div class="field">
    <label for="resp">Responsável</label>
    <input id="resp" class="input input--erro"
           aria-invalid="true" aria-describedby="erro-resp" />
    <span id="erro-resp" class="field__erro">Informe o responsável.</span>
  </div>

  <div class="field">
    <label for="sit">Situação</label>
    <select id="sit" class="input"><option>Rascunho</option></select>
  </div>
</div>
```

`.fgrid` é grade de 2 colunas que vira 1 abaixo de 1100px. `.field--full` ocupa a
linha inteira.

---

## Toggle, segmentado e abas

```html
<button class="toggle is-active">
  <span class="toggle__track"><span class="toggle__thumb"></span></span>
  <span>Ativo</span>
</button>

<div class="seg">
  <button class="seg__btn is-active">Lista</button>
  <button class="seg__btn">Grade</button>
</div>

<div class="tabs">
  <button class="tab is-active">Detalhes</button>
  <button class="tab">Histórico</button>
</div>
```

---

## Avisos em bloco

```html
<div class="aviso aviso--info">
  <h3 class="h-card5">Título</h3>
  <p class="body-txt">Mensagem.</p>
</div>
```

Variantes: `--ok`, `--erro`, `--warn`, `--info`. Persistente na página, ao contrário
do toast, que é efêmero. Borda lateral em vez de fundo saturado.

---

## Lista simples

```html
<ul class="lista-simples">
  <li class="lista-simples__item">
    <span class="pill pill--neutral">1</span>
    <span class="body-txt">Conteúdo</span>
  </li>
</ul>
```

Para conjuntos pequenos que não justificam tabela.

---

## Estado vazio

```html
<div class="empty">
  <img src="/ds/assets/ilustra-em-construcao.png" alt="" />
  <h4>Nenhum registro ainda</h4>
  <p>Crie o primeiro para ver a listagem tomar forma.</p>
</div>
```

Distinga **vazio de origem** de **vazio por filtro** — as saídas são diferentes:
uma convida a criar, a outra a limpar a busca.

---

## Tela de guarda

```html
<div class="guard">
  <img src="/ds/assets/ilustra-acesso-negado.png" alt="" />
  <h1>Acesso negado</h1>
  <p>Você não tem permissão para ver esta página.</p>
  <a href="/" class="btn btn--primary">Voltar ao início</a>
</div>
```

Ilustrações disponíveis em [ASSETS.md](ASSETS.md).

---

## Componentes imperativos — `ds/ui.js`

Expostos no objeto global `TN`.

### Toast

```js
TN.toast("Registro salvo.");
TN.toast("Não foi possível salvar.", "erro");
TN.toast("Sessão expirando.", "aviso");
```

Do servidor, por cabeçalho de resposta — a página não precisa saber:

```python
resposta.headers["X-TN-Toast"] = quote("Registro criado.")
resposta.headers["X-TN-Toast-Tipo"] = "ok"
```

O `quote()` não é opcional: cabeçalho HTTP é latin-1, e "Registro criado." sem
codificar já quebra no acento.

### Contrato de eventos do Alpine AJAX

Verificado no navegador, versão 0.12.7 — a documentação não é explícita e a
suposição errada custa caro:

| Evento | `detail` |
|---|---|
| `ajax:before` | `null` |
| `ajax:success` | `{ ok, redirected, url, status, html, raw, headers }` |
| `ajax:sent` | idem — **dispara por último**, inclusive em erro |
| `ajax:error` | idem — dispara em **todo** status fora de 2xx, não só falha de rede |

Três armadilhas:

- **Não existe `detail.xhr`.** Ler cabeçalho é `detail.headers.get(nome)` — é um
  objeto `Headers` nativo, não responde a acesso por propriedade.
- **Não existe `ajax:after`.** Para fechar overlay, use `ajax:sent`.
- **`ajax:error` inclui o 422.** Toast automático de erro ali é ruído: a validação já
  devolveu a mensagem em cada campo. Por isso `ds/ui.js` ignora 4xx e só avisa em
  falha de rede ou 5xx.

### Modal

```js
const m = TN.modal({ title: "Detalhes", subtitle: "Opcional", width: 600, body: "<p>…</p>" });
m.close();
```

Fecha com Esc, devolve o foco a quem abriu e prende o foco no primeiro campo.

### Confirmação

```js
const ok = await TN.confirmarExclusao({
  mensagem: "Você confirma a exclusão do registro abaixo?",
  rows: [{ label: "Título", valor: "Exemplo" }],
});
if (ok) { /* … */ }
```

### Guarda de saída

```js
if (temAlteracaoNaoSalva) {
  const sair = await TN.confirmarSaida();
  if (!sair) return;
}
```

### Carregamento

```js
TN.loading(true, "Salvando...");
TN.loading(false);
```

Automático em qualquer elemento com `data-tn-loading`:

```html
<form data-tn-loading="Salvando...">…</form>
```

### Utilitários

```js
TN.esc(texto)              // escapa HTML
TN.fmtDate(data, comHora)  // 13/08/2026 14:30
TN.fmtMesAno(8, 2026)      // Agosto de 2026
TN.avatar("Ana Souza", 38) // markup do avatar com iniciais
TN.pill("Ativo", "ok")     // markup da pill
```

---

## Dica (tooltip) — `ds/dica.js` e `.dica`

Balão de texto curto que aparece ao passar o mouse **e ao focar pelo teclado**.
O Padrão só tinha o atributo `title`, que demora, não tem estilo e não aparece
no foco; a dica o substitui onde o texto importa.

```html
<!-- em qualquer elemento -->
<a class="tab" href="…" data-dica="Cronograma de desembolso">Desembolso</a>

<!-- só enquanto a barra lateral é trilho de ícones (o rótulo some) -->
<a class="sidebar__item" href="…" aria-label="02 Planejamento"
   data-dica-trilho="02 Planejamento">…</a>
```

Quem tem só ícone continua precisando de `aria-label`: a dica é auxílio visual,
não nome acessível. Do JavaScript: `TN.dica.mostrar([{ titulo, texto }], retangulo, "baixo")`
e `TN.dica.esconder()`.

### Siglas

Toda sigla do glossário (SPI, CPI, VME, RNC, TF, `S39`...) ganha a dica ao passar
o mouse, em qualquer tela, sem marcar nada no HTML: a palavra sob o ponteiro é
achada pela posição e o significado vem do `CONTEXT.md` (`/api/glossario`).
Texto dentro de gráfico e de lista de seleção não tem a dica; `data-sem-dica` a
desliga num trecho. Sigla nova: o termo no `CONTEXT.md` e
`api/.venv/bin/python scripts/generate_glossary.py`.

## Inclusão no Portfólio — `data-tn-incluir`

Todo registro pertence a um projeto. No Portfólio, o botão de inclusão precisa
pedir o projeto antes de abrir o formulário:

```html
<button type="button" class="btn btn--primary" data-tn-incluir="nova" @click="abrirFormulario()">
  Nova ação
</button>
```

No Portfólio o shell intercepta o clique, abre a escolha do projeto e reabre a
tela no projeto com `?acao=nova`; no projeto o botão segue o `@click` normal.
A tela abre o formulário no `iniciar(raiz)`:

```js
if (TN.escopo.acaoPendente() === "nova") abrirFormulario();
```

`acaoPendente()` devolve a ação e a tira do endereço, para recarregar a tela
não reabrir o formulário. No servidor, `Scope.require_project()` recusa o
registro sem projeto.

## Link de tela — `data-tn-tela`

`<a href="/central-acoes/ata?codigo=TN-2026-0028" data-tn-tela>` troca a view sem
recarregar o documento e mantém o escopo. O endereço é `/<modulo>/<tela>` (com
hífen no lugar do `_`), como na lista de navegação.
