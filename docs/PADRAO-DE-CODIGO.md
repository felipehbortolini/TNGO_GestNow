# Padrão de código

Como o código deve ser escrito neste repositório, e o que impede que ele seja
escrito de outro jeito.

---

## O princípio

**Documentação não impede defeito. O que impede é um comando que falha.**

Por isso este documento é curto e o `scripts/verificar.mjs` é longo. Tudo que
importa está codificado numa verificação executável; o texto aqui só explica o
porquê.

---

## O fluxo obrigatório

```
  entender o negócio  →  desenhar  →  escrever  →  porta de qualidade
      /grill-me                                    verificar.mjs
```

### 1. Antes de escrever — entender

Se o pedido tem ambiguidade sobre regra de negócio, fluxo, permissão ou caso
limite, peça uma entrevista antes de construir:

```
/grill-me
```

A skill conduz uma entrevista em rodadas, mapeando as decisões como uma árvore e
perguntando toda a fronteira de cada vez. Serve para chegar ao código sabendo o
que construir — e não descobrir na revisão que a tela resolve o problema errado.

Sinais de que falta esta etapa: "quando o usuário X, deve acontecer Y" sem dizer
o que ocorre no caso limite; papel de acesso indefinido; nenhuma palavra sobre o
que acontece quando dá erro.

### 2. Antes de mexer na estrutura — desenhar

Para mover módulo, criar camada ou trocar a forma de um dado:

```
/improve-codebase-architecture
```

Varre o código atrás de módulos rasos e costuras vazando, monta um relatório
visual com antes/depois e conduz a discussão da opção escolhida.

Ela se apoia em três skills que entram sozinhas quando necessárias:
`codebase-design` (vocabulário de módulo, interface, profundidade, costura),
`grilling` (aprofundar uma decisão) e `domain-modeling` (manter o `CONTEXT.md`
em dia).

### 3. Enquanto escreve

`CONTEXT.md` é o glossário: termo do domínio significa exatamente o que está
escrito lá. Conceito novo entra no momento em que aparece.

Para o visual, a hierarquia de documentos está em
[PADRAO-DE-PAGINA](PADROES-DE-PAGINA.md) e [CONVENCOES](CONVENCOES.md).

### 4. Antes de dar por pronto

```bash
node scripts/verificar.mjs
```

---

## As ferramentas

### Python — ruff e ty

Ambos são **dependências de desenvolvimento do projeto**, presas em
`api/uv.lock`. Não são instalados globalmente de propósito: versão global
depende da máquina de cada pessoa, e a mesma base de código passaria num lugar e
reprovaria no outro.

| Ferramenta | Papel |
|---|---|
| `ruff check` | Lint — import morto, variável não usada, armadilha de sintaxe, `datetime` sem fuso, risco de segurança |
| `ruff format` | Formatação — uma única forma canônica, sem discussão em revisão |
| `ty check` | Tipos — atributo inexistente, retorno que não bate com a anotação |

O conjunto de regras está em `api/pyproject.toml`, comentado regra a regra.
Rigoroso mas prático: entra o que pega defeito, fica de fora o que só gera
ruído.

Duas decisões que valem destacar:

- **`E501` (comprimento de linha) desligado.** Comprimento é assunto do
  formatador. Linter e formatador brigando por isso rende ruído e nenhum ganho.
- **`ARG001` isento em `src/blueprints/`.** O modelo V2 do Azure Functions
  **exige** o parâmetro `req` na assinatura de todo handler, mesmo quando a rota
  não lê nada dele — o caso de `/api/health`. Não é argumento esquecido; é
  contrato do framework, e "corrigir" quebraria o registro da função.

### Front — ESLint

ESLint 10 em configuração plana, cobrindo as três linguagens:

| Arquivos | Plugin |
|---|---|
| `app/ds/**/*.js`, `scripts/**/*.mjs` | ESLint core |
| `app/ds/**/*.css` | `@eslint/css` |
| `app/index.html`, `_views/`, `_components/` | `@html-eslint` |

Três decisões estruturais em `eslint.config.mjs`:

- **`api/src/templates/` fora do escopo.** São templates Jinja2: `{% if %}` e
  `{{ var }}` não são HTML e nenhum parser de HTML dá conta. Aquele conteúdo é
  coberto pelo teste de renderização, que confere o HTML **depois** de
  produzido.
- **Regras de formatação do html-eslint desligadas.** O preset `recommended`
  traz `indent`, `quotes` e `require-closing-tags` — ligá-lo inteiro rendeu 458
  reprovações neste código, quase todas por indentação de 2 espaços em vez de 4
  e por `<img />`, que é válido em HTML5. Ficaram só as regras de correção,
  acessibilidade e compatibilidade.
- **`allowUnknownVariables` no CSS.** A arquitetura do Design System é
  justamente essa: tokens moram em `tokens.css` e são consumidos por
  `shell.css` e `patterns.css`. A regra valida arquivo por arquivo e não enxerga
  variável declarada em outro — sem a opção, acusava 99 falsos positivos.

**Fragmento continua sem estrutura de documento.** As regras
`require-doctype`, `require-lang` e `require-title` valem só para
`app/index.html`. Nos fragmentos elas reprovariam markup correto, porque por
contrato eles não têm `<html>` (Regra 2 do contrato visual).

### Padrão Timenow — `verificar-padrao.mjs`

As nove verificações que nenhum linter de mercado conhece: contrato visual,
colisão de seletor entre os arquivos do Design System, asset com nome UUID,
raiz de fragmento, paridade com o template. Detalhes em
[CONTRATO-VISUAL](CONTRATO-VISUAL.md), Regra 5.

---

## A porta de qualidade

```bash
node scripts/verificar.mjs             # tudo
node scripts/verificar.mjs --corrigir  # aplica o que é automático antes
node scripts/verificar.mjs --py        # só Python
node scripts/verificar.mjs --front     # só JS/CSS/HTML
```

Também por npm: `npm run verificar`, `npm run verificar:corrigir`.

Sai com código 1 se qualquer etapa falhar — serve para CI e para hook de
pre-commit.

**O `rodar.ps1` roda a porta antes de subir o servidor.** Aplicação rodando com
código reprovando é como testar o carro sem checar o freio: funciona até a hora
que importa. Há escape consciente para o caso legítimo de ver a tela no meio de
uma refatoração:

```powershell
.\scripts\rodar.ps1 -SemVerificar
```

---

## Regra de ouro sobre supressão

**Nunca desligue uma regra para fazer o gate passar.** Se uma regra acusa algo
legítimo, a saída é uma destas, nesta ordem:

1. **Corrigir o código.** Quase sempre é isto.
2. **Se for falso positivo estrutural**, ajustar a configuração **com um
   comentário explicando o porquê**. Os dois casos vivos deste repositório são
   `ARG001` nos blueprints e `allowUnknownVariables` no CSS — ambos
   documentados no arquivo de configuração.
3. **Nunca** `# noqa` ou `eslint-disable` solto, sem justificativa escrita.

A diferença entre 2 e 3: o item 2 é uma decisão de arquitetura registrada, que a
próxima pessoa entende e pode contestar. O item 3 é uma dívida invisível.

---

## O que a porta não cobre

Vale saber onde ela para:

| Não cobre | Cobre quem |
|---|---|
| Se a tela resolve o problema certo | `/grill-me` antes de construir |
| Se o módulo está no lugar certo | `/improve-codebase-architecture` |
| Leitor de tela e anel de foco visual | Teste manual — ver [ACESSIBILIDADE](ACESSIBILIDADE.md) |
| Comportamento em tempo de execução | Percorrer o app; ver o console |
| Templates Jinja2 | Teste de renderização |

Gate verde significa "não há defeito **desta classe**" — não "está pronto".
