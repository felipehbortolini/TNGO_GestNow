# Padrões de página

Como montar uma tela no padrão Timenow. Componentes isolados em
[COMPONENTES.md](COMPONENTES.md).

---

## Anatomia canônica

```html
<main id="app-shell" class="content">
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="h-dash">Título</h1>
        <p class="page-head__sub">Uma linha de contexto.</p>
      </div>
      <div class="page-head__actions">
        <button class="btn btn--primary">Ação primária</button>
      </div>
    </div>

    <!-- conteúdo -->
  </div>
</main>
```

`.page` limita a 1280px, centraliza e aplica 32px de respiro. `.page-head` quebra
sozinho no celular. Exatamente **uma** ação primária por página.

---

## Os cinco estados

Toda tela que carrega dados precisa dos cinco. Estado faltando é o defeito mais
comum em revisão.

| Estado | Como | Quando |
|---|---|---|
| Carregando | `.spinner` ou `TN.loading()` | Enquanto o fragmento não chega |
| Vazio de origem | `.empty` + ilustração + ação | Nada cadastrado ainda |
| Vazio por filtro | `.empty` com texto diferente | Busca sem resultado |
| Erro | `.aviso--erro` ou toast | Falha na operação |
| Sem permissão | `.guard` | Sessão sem o papel exigido |

Vazio de origem e vazio por filtro **não são o mesmo estado**: um convida a criar,
o outro a limpar a busca. Ver `api/src/templates/exemplo/list.html`.

---

## Listagem

Ordem consagrada: **KPIs → barra de ferramentas → lista**.

```html
<div id="resumo" x-init="$ajax('/api/programacao-resumo', { target: 'resumo' })"></div>

<div class="card">
  <div class="card__head"><h2 class="h-card4">Registros</h2></div>
  <div class="card__body">
    <div class="busca mb-16">
      <span class="busca__icone" x-init="$el.innerHTML = window.icon('search', 18)"></span>
      <label class="sr-only" for="busca">Buscar</label>
      <input id="busca" type="search" class="input busca__input" placeholder="Buscar..." />
    </div>
    <div id="lista" x-init="$ajax('/api/programacao', { target: 'lista' })"></div>
  </div>
</div>
```

Busca sempre com `debounce` de 300ms — sem isso, é uma requisição por tecla.

### KPIs

```html
<div class="kpis" style="--kpis-colunas: 3">
  <button class="kpi kpi--neutro">
    <span class="kpi__icone" x-init="$el.innerHTML = window.icon('taskList', 16)"></span>
    <span class="kpi__label">Total</span>
    <span class="kpi__value">42</span>
  </button>
</div>
```

Variantes: `--neutro`, `--ok`, `--warn`, `--erro`, `--info`. O trilho colorido de 4px
é o que torna a faixa varrível antes de a pessoa ler o rótulo. **Os números vêm
contados do servidor** — não some no cliente.

### Tabela ou linhas?

| Use `.tbl` | Use `.linha` |
|---|---|
| Colunas comparáveis entre si | Cada registro tem hierarquia própria |
| Dados homogêneos, muitos por vez | Título + metadados + pessoas + data |
| A pessoa vai comparar valores | A pessoa vai escolher um item |

```html
<div class="linha">
  <span class="linha__icone" x-init="$el.innerHTML = window.icon('file', 16)"></span>
  <div class="linha__main">
    <div class="linha__id">REG-0042</div>
    <div class="linha__titulo">Título do registro</div>
    <div class="linha__meta">Atualizado há 2 dias</div>
  </div>
  <div class="facepile">
    <div class="mini-avatar">AS</div>
    <div class="mini-avatar">BL</div>
    <div class="mini-avatar mini-avatar--mais">+3</div>
  </div>
  <span class="linha__chev" x-init="$el.innerHTML = window.icon('chevronRight', 16)"></span>
</div>
```

---

## Formulário

```html
<form method="post" action="/api/atividade" x-target="form lista" data-tn-loading="Salvando...">
  <div class="fgrid">…</div>
  <div class="acoes-rodape mt-24">
    <button type="reset" class="btn btn--secondary">Limpar</button>
    <button type="submit" class="btn btn--primary">Salvar</button>
  </div>
</form>
```

**A validação é do servidor.** Responde 422 com o formulário reexibido, os valores
digitados de volta e a mensagem no campo. Ninguém redigita nada.

O `x-target` duplo (`"form lista"`) deixa o Alpine AJAX aceitar o que vier: o
formulário com erro ou a lista atualizada.

Validação no cliente é bem-vinda como conveniência (`required`, `maxlength`), mas
nunca como única barreira.

---

## Resposta que atualiza vários blocos

**A regra que pega todo mundo:** alvo declarado no `x-target` que **não vier na
resposta é esvaziado** pelo Alpine AJAX. Não é ignorado — é removido da tela.

Então se o formulário declara três destinos:

```html
<form x-target="exemplo-form exemplo-resumo exemplo-lista">
```

toda resposta precisa trazer os três. Devolver só a lista apaga o formulário e os
KPIs da página.

A solução é um template que emite raízes irmãs, sem estender `base_fragment.html`:

```jinja
{% if incluir_form %}
<div id="exemplo-form">{% include "exemplo/_form.html" %}</div>
{% endif %}
<div id="exemplo-resumo" class="kpis">{% include "exemplo/_resumo.html" %}</div>
<div id="exemplo-lista">{% include "exemplo/_lista.html" %}</div>
```

Ver `api/src/templates/exemplo/multi.html`. É a **exceção** à regra "nunca fixe id no
servidor": aqui o id é fixo de propósito, porque a resposta se destina a lugares
conhecidos que o cliente declarou. Fragmento de destino único continua usando
`{{ target_id }}`.

Para isso funcionar, o miolo de cada bloco vive num partial (`_form.html`,
`_lista.html`, `_resumo.html`), reaproveitado tanto pelo fragmento isolado quanto pela
resposta múltipla.

**Inclusive o 422.** Se a validação devolver só o formulário, a lista e os KPIs
somem da tela.

---

## Interpolar dado em expressão Alpine

Não interpole texto vindo do banco direto numa expressão do Alpine:

```jinja
{# ERRADO — tojson é marcado como seguro, as aspas fecham o atributo #}
@click="TN.confirmarExclusao({ rows: [{ valor: {{ r.titulo | tojson }} }] })"
```

O `tojson` produz `"texto"` com aspas duplas e o Jinja **não** as escapa, porque o
filtro marca a saída como segura. O atributo fecha no meio e o Alpine recebe uma
expressão truncada — `SyntaxError` no console e o botão não faz nada.

Passe por `data-*`, onde o autoescape funciona, e leia de `$el.dataset`:

```jinja
<button
  data-titulo="{{ r.titulo }}"
  @click="TN.confirmarExclusao({ rows: [{ label: 'Título', valor: $el.dataset.titulo }] })"
>
```

---

## Ação destrutiva

```html
<button class="iconbtn" aria-label="Excluir Relatório"
        x-init="$el.innerHTML = window.icon('trash', 16)"
        @click="TN.confirmarExclusao({
          rows: [{ label: 'Título', valor: 'Relatório' }]
        }).then(ok => { if (ok) $ajax('/api/atividade-excluir?chave=' + chave, { method: 'post', target: 'lista' }) })">
</button>
```

A confirmação mostra **o que exatamente** será excluído. "Você tem certeza?" sozinho
não é confirmação — é um obstáculo que se aprende a clicar sem ler.

---

## Sair com dados não salvos

```js
if (formularioAlterado) {
  const sair = await TN.confirmarSaida();
  if (!sair) return;
}
```

---

## Responsivo

| Largura | O que muda |
|---|---|
| > 1100px | Layout cheio; `.fgrid` em 2 colunas; KPIs em 3 |
| ≤ 1100px | `.fgrid` em 1 coluna; KPIs em 2; some o texto do chip de usuário |
| ≤ 760px | Respiro cai para 16px; KPIs em 1; toolbar empilha; some `.linha__data` |

Teste nas três larguras. Sem rolagem horizontal em nenhuma delas.

---

## O que ficou fora do kit

Estes vieram do projeto piloto e **não** entraram no Design System, por serem do
domínio daquele app. Servem de referência, não de padrão:

| Padrão | Por quê |
|---|---|
| Kanban de ações | Fluxo de trabalho específico |
| Formulário de ata | Estrutura de documento própria |
| Editor rich-text de notas | Componente pesado, de um caso só |
| Agenda do Teams | Integração específica |
| Reincidência | Regra de negócio |

**Critério de corte:** se o seletor cita uma entidade do domínio — ata, ação,
kanban — é do app. Se descreve uma forma — linha, tile, pilha, barra — é do kit.
