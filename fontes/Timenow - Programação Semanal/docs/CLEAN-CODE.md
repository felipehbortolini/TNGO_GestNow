# Clean code — o que fazer e o que não fazer

Destilação dos três guias de referência para **esta** stack: Python, JavaScript
puro, CSS e HTML. Os guias completos estão em
[`referencia/clean-code/`](referencia/clean-code/) — 7.000 linhas somadas, que
ninguém consulta no meio do desenvolvimento. Este documento é o que se lê.

---

## A regra que organiza todas as outras

**Se dá para verificar sem julgamento, não é sua responsabilidade lembrar.**

Boa parte do que os guias pregam já é imposta por `ruff` e `eslint` — o gate
falha sozinho. O que sobra para a cabeça humana é curto, e é o que está na
segunda metade deste documento.

```bash
node scripts/verificar.mjs
```

---

## O que a máquina já cobre

Não precisa revisar nada disto em PR — se passou no gate, está resolvido.

| Princípio do guia | Quem impõe |
|---|---|
| Funções devem fazer uma coisa | `complexity ≤ 12` (JS) · `C901` com limite 10 (Python) |
| 2 argumentos, idealmente | `max-params ≤ 4` (JS) · `PLR0913` (Python) |
| Use parâmetro com valor padrão, não `x = x \|\| y` | `no-param-reassign` |
| Não use flag booleana como parâmetro | `FBT` (Python) |
| Remova código morto | `no-unused-vars` · `F841` |
| Não deixe código comentado | `ERA001` (Python) |
| Não ignore erro capturado | `TRY` (Python) · `no-empty` |
| Evite aninhamento profundo | `max-depth ≤ 4` · `PLR0912` |
| Nomes consistentes | `N` (pep8-naming) |
| Sintaxe obsoleta | `UP` (pyupgrade) |
| `datetime` sem fuso | `DTZ` |
| Ternário aninhado | `no-nested-ternary` |
| `if/else` que só retorna | `no-else-return` · `RET` |

---

## O que exige julgamento

Aqui a máquina não alcança. É o que se revisa em PR.

### Nomes

**Faça** — nome que responde "o quê" sem precisar do comentário:

```python
registros_filtrados = _filtrar(busca, situacao)
```

**Não faça** — nome que obriga a ler a implementação:

```python
d = f(b, s)          # o que é d? o que f faz?
lista2 = processar(x)  # processar o quê, para quê?
```

**Regra prática:** se o nome precisa de comentário ao lado explicando o que é,
o nome está errado. Corrija o nome, apague o comentário.

**Vocabulário único para a mesma coisa.** Neste repositório, `registro` é
sempre `registro` — nunca `item`, `record` ou `dado` para a mesma entidade. O
glossário é o [CONTEXT.md](../CONTEXT.md); termo novo entra lá.

### Uma função, um nível de abstração

**Não faça** — mistura decisão de negócio com detalhe de formatação:

```python
def criar(req):
    titulo = req.form.get("titulo").strip()
    if len(titulo) < 3: ...                 # regra de negócio
    html = "<tr><td>" + titulo + "</td>"    # detalhe de renderização
    resposta.headers["X-TN-Toast"] = quote("Criado")  # detalhe de transporte
```

**Faça** — cada nível chama o de baixo:

```python
def criar(req):
    valores = _extrair(req)
    erros = _validar(**valores)
    if erros:
        return _resposta_com_erro(valores, erros, req)
    _registros.append(_novo_registro(**valores))
    return _resposta_de_sucesso(req)
```

`api/src/blueprints/atividades.py` segue esse formato — os helpers
`_contexto_lista`, `_contexto_resumo` e `_contexto_form` existem exatamente
para manter o handler num nível só.

### Efeito colateral escondido

**Não faça** — a função promete uma coisa e faz outra:

```javascript
function formatarNome(usuario) {
  usuario.nome = usuario.nome.trim();   // mutou o objeto de quem chamou
  return usuario.nome.toUpperCase();
}
```

**Faça** — devolve o novo valor, não mexe na entrada:

```javascript
function formatarNome(usuario) {
  return usuario.nome.trim().toUpperCase();
}
```

Vale especialmente para o Design System: `TN.avatar()`, `TN.pill()` e
`TN.esc()` **devolvem string** e não tocam no DOM. Quem monta o DOM é quem
chamou. Isso é o que os torna testáveis e combináveis.

### Condicional que se explica

**Não faça:**

```javascript
if (r.status >= 400 && r.status < 500 && !r.headers.get("X-TN-Toast")) { ... }
```

**Faça** — dê nome à condição:

```javascript
const erroTratadoPeloServidor = r.status >= 400 && r.status < 500;
if (erroTratadoPeloServidor) return;
```

É o que `ds/ui.js` faz na ponte com o Alpine AJAX — a condição tem nome e um
comentário dizendo **por que** 4xx fica de fora.

### Números soltos

**Não faça:**

```javascript
setTimeout(() => el.classList.add("is-out"), 3200);
setTimeout(() => el.remove(), 3600);
```

**Faça** — constante nomeada quando o número se repete ou tem razão de ser:

```javascript
const TEMPO_VISIVEL = 3200;
const TEMPO_ATE_REMOVER = TEMPO_VISIVEL + 400;  // 400 = duração da transição
```

**Exceção honesta:** número usado uma vez, num contexto óbvio, não precisa de
constante. `padStart(2, "0")` é claro; `padStart(TAMANHO_DIA, PREENCHIMENTO)`
é pior.

### Comentário: por que, não o quê

Este é o ponto onde os guias mais são mal interpretados.

**Não faça** — comentário que repete o código:

```python
# incrementa o contador
contador += 1
```

**Faça** — comentário que registra a decisão, que o código não consegue contar:

```python
# Fuso explícito: `datetime.now()` sem tz devolve hora ingênua, que depende
# do relógio local e não carrega essa informação consigo. Em Azure Functions
# o host roda em UTC, então o valor exibido não muda em produção — mas passa
# a ser inequívoco (ruff DTZ005).
now = datetime.now(UTC).strftime("%H:%M:%S")
```

**Este repositório é deliberadamente bem comentado**, e isso não contradiz os
guias: eles atacam comentário que restata o código, não o que preserva a
razão de uma escolha. Ver a seção de conflitos, abaixo.

### Duplicação: só depois da terceira vez

**Não faça** — abstrair na segunda ocorrência, antes de saber o que varia.
Abstração cedo demais engessa o eixo errado e custa mais que a duplicação.

**Faça** — duplique, observe o que muda entre os casos, e só então extraia.
`_form.html`, `_lista.html` e `_resumo.html` viraram partials **depois** que
ficou claro que o mesmo miolo servia ao fragmento isolado e à resposta
multi-alvo.

---

## Onde os guias conflitam com este repositório

Quatro pontos em que seguir o guia ao pé da letra pioraria o código daqui. O
que vale é a coluna da direita.

| O guia diz | Aqui vale | Por quê |
|---|---|---|
| "Evite marcadores posicionais" (`════`) | **Usamos** | Arquivos como `dados.py` e `tokens.css` têm blocos longos e claramente separados. O divisor é o índice visual; sem ele, achar a seção de rotas no meio de 260 linhas custa mais. O guia mira decoração sem função, não estrutura. |
| "Comente só complexidade de negócio" | **Comentamos o porquê de toda decisão não óbvia** | Boa parte do valor deste repositório é o registro do motivo — por que `--verde-100` mudou, por que o anel da facepile vai em `box-shadow`, por que `ARG001` é isento. Apagar isso citando clean code destruiria o que mais custou a descobrir. |
| "Não escreva em funções globais" | **`window.icon` e `window.TN` são a interface** | O guia mira monkey-patching de protótipo nativo (`Array.prototype.x = ...`). Aqui são `<script>` clássicos sem sistema de módulo: o global **é** o mecanismo de exportação, e é explícito. |
| "Prefira classes ES6" | **Objeto literal + IIFE** | O DS não tem hierarquia nem estado por instância. Classe traria `new`, `this` e herança sem nada em troca. O guia contrasta com classes ES5 por protótipo — que também não usamos. |

**Se alguém abrir PR citando um desses guias para mudar isto, esta tabela é a
resposta.** Discordar é legítimo; mudar sem discutir, não.

---

## O TypeScript

`referencia/clean-code/clean-code-typescript.md` está aqui por completude, mas
**este projeto não tem TypeScript** — a stack é Python, JavaScript puro, CSS e
HTML. O arquivo serve se um projeto futuro adotar TS; os capítulos de
Variáveis, Funções e SOLID valem igual para JS.

---

## Fluxo

1. Antes de escrever: entendeu o negócio? Na dúvida, `/grill-me`.
2. Escrevendo: os pontos de julgamento acima.
3. Antes de dar por pronto: `node scripts/verificar.mjs`.
4. Antes do PR: [CHECKLIST-NOVA-PAGINA.md](CHECKLIST-NOVA-PAGINA.md).

Detalhes do fluxo em [PADRAO-DE-CODIGO.md](PADRAO-DE-CODIGO.md).

---

## Referência completa

| Guia | Linhas | Quando abrir |
|---|---:|---|
| [clean-code-python.md](referencia/clean-code/clean-code-python.md) | 1.611 | Dúvida em Python, SOLID com classes |
| [clean-code-javascript.md](referencia/clean-code/clean-code-javascript.md) | 2.386 | Dúvida em JS |
| [clean-code-typescript.md](referencia/clean-code/clean-code-typescript.md) | 2.954 | Só se o projeto adotar TypeScript |

Origem: [zedr/clean-code-python](https://github.com/zedr/clean-code-python),
[ryanmcdermott/clean-code-javascript](https://github.com/ryanmcdermott/clean-code-javascript),
[labs42io/clean-code-typescript](https://github.com/labs42io/clean-code-typescript).
