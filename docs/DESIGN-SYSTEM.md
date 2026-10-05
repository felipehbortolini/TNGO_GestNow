# Design System Timenow — v2.4

Tokens, rampas e regras de uso. Referência de componentes em
[COMPONENTES.md](COMPONENTES.md); composições em
[PADROES-DE-PAGINA.md](PADROES-DE-PAGINA.md).

---

## Os três arquivos

| Arquivo | O que mora ali | Exemplo |
|---|---|---|
| `ds/tokens.css` | Variáveis e componentes atômicos | `.btn`, `.card`, `.pill`, `.input` |
| `ds/shell.css` | Estrutura de tela | `.sidebar`, `.page`, `.guard` |
| `ds/patterns.css` | Composições | `.kpis`, `.toolbar`, `.facepile` |

**Nenhuma classe é declarada em dois arquivos.** Isso é verificado por
`scripts/verificar-padrao.mjs` — antes da v2.4, `.app`, `.card` e `.card__head`
existiam nos dois primeiros com valores diferentes, e qual valia dependia da ordem
de carga.

A biblioteca de gráficos (`ds/graficos/`, D11) traz um quarto CSS, `graficos.css`,
carregado pelo shell logo depois de `patterns.css`. Todas as classes dele começam
com `.graf`, e ele não entra na verificação de colisão: essa verificação trata os
`from`, `to` e `0%` de um `@keyframes` como seletores, e obrigaria as animações dos
gráficos a morar em `tokens.css`. Cores, espaçamento e raio saem de `var(--token)`,
como nos outros três. Uso em [COMPONENTES.md](COMPONENTES.md) e
[styleguide-graficos.html](styleguide-graficos.html).

---

## Cor

### Verde Timenow — a rampa da marca

| Token | Valor | Uso |
|---|---|---|
| `--verde-50` | `#E6F8F4` | Fundo de realce, hover de linha |
| `--verde-100` | `#D2F1EB` | Borda de avatar, botão desabilitado |
| `--verde-200` | `#91D9D1` | Divisores em superfície tintada |
| `--verde-500` | `#00A793` | Ícone, trilho, anel de foco — **nunca sob texto** |
| `--verde-600` | `#008A7D` | Rótulo de KPI |
| `--verde-700` | `#00776A` | Texto sobre fundo verde claro |
| `--brand-primary` | `#006457` | **Toda superfície com texto branco** |
| `--brand-primary-hover` | `#005046` | Hover dessas superfícies |
| `--brand-title` | `#006357` | **Todo título** |

**A distinção entre `--verde-500` e `--brand-primary` é a regra de contraste, não
gosto.** Texto branco sobre `--verde-500` dá 3,02:1 e reprova o mínimo de 4,5:1 da
WCAG. Sobre `--brand-primary` dá 7,09:1 e aprova AAA. Por isso botão primário,
cabeçalho de modal, mini-avatar e toast usam `--brand-primary`; o `--verde-500`
fica em elemento não textual, onde o mínimo é 3:1 e ele passa.

> `--verde-100` era `#C2DAE5` — um tom azulado que não pertencia a esta rampa e
> derrubava o contraste de `--verde-700` para 3,76:1. Corrigido na v2.4 para
> `#D2F1EB`, que dá 4,55:1 e aprova AA.

### Semânticos

| Família | 50 | 500 | 700/800 | Quando |
|---|---|---|---|---|
| `ok` | `#DDF8F0` | `#4EB76D` | `#2B6533` | Sucesso, concluído |
| `warn` | `#FDF8E5` | `#E8B43B` | `#806320` | Atenção, rascunho |
| `erro` | `#FAEBEB` | `#D03636` | `#942826` | Erro, exclusão |
| `azul` | `#E9F3F9` | `#2288C3` | `#134568` | Informação, em andamento |
| `frio` | `#F0F4F6` | `#648FA0` | `#476672` | Neutro, cancelado |
| `roxo` | `#F1EBF7` | `#7438B0` | `#522870` | Categoria |

Regra: **50 no fundo, 700/800 no texto**. É o par que garante contraste AA. Os
tons 500 são para trilho, ícone e borda — não para texto sobre fundo claro.

### Contraindicações

- **Nunca escreva cor fixa.** Se falta um tom, ele entra na rampa em `tokens.css`.
- **Nunca use 500 como texto sobre fundo claro.** `--verde-500` sobre branco dá
  3,03:1 — reprova. Para texto, `--verde-700` ou `--brand-title`.
- **Nunca comunique estado só por cor.** Toda pill traz rótulo em texto.

---

## Tipografia

| Classe | Tamanho | Peso | Uso |
|---|---|---|---|
| `.h-dash` | 40px (24px em `.page-head`) | 700 | Título de página |
| `.h-card1` | 28px | 600 | Destaque em hero |
| `.h-card3` | 20px | 600 | Seção |
| `.h-card4` | 16px | 600 | Título de card |
| `.h-card5` | 14px | 600 | Sub-bloco |
| `.body-txt` | 13px | 400 | Corpo |
| `.hint` | 11px | 400 | Auxiliar |
| `.aglutinador` | 14px | 600, caixa alta | Rótulo de agrupamento |

Base do `body`: 14px. Títulos usam `--brand-title`, não preto.

### Duas famílias

```css
--font: "Segoe UI", system-ui, sans-serif;           /* corpo */
--font-label: "Montserrat", "Segoe UI", sans-serif;  /* rótulos */
```

A **Montserrat é hospedada no próprio app**: `ds/assets/fonts/Montserrat-latin.woff2`,
38 KB, fonte variável cobrindo os pesos 100 a 900 num arquivo só. Sem CDN.

Antes ela era declarada sem existir arquivo nenhum no projeto — o navegador
procurava a fonte instalada na máquina de cada pessoa, e o mesmo app renderizava
tipografias diferentes conforme quem abrisse. Detalhes em
`app/ds/assets/fonts/LEIA-ME.md`.

---

## Espaçamento

```css
--space-xxs: 2px;   --space-xs: 4px;    --space-sm: 8px;
--space-md: 12px;   --space-lg: 16px;   --space-xl: 24px;   --space-xxl: 32px;
```

Ritmo praticado: 8px entre elementos irmãos, 16px dentro de um bloco, 24px entre
blocos, 32px entre seções principais.

---

## Elevação

**No padrão Timenow a elevação vem da borda, não da sombra.**

```css
--borda: #DEE2E6;
--shadow: 0 1px 2px 0 rgba(16, 40, 36, 0.06);
--shadow-hover: 0 2px 8px 0 rgba(16, 40, 36, 0.10);
```

O `.card` tem borda de 1px e sombra quase imperceptível. A sombra existe para
assentar o card, não para levantá-lo. Sombra forte é só para o que flutua de fato:
modal, painel de filtro, toast.

---

## Raio e movimento

```css
--r-sm: 4px;    /* chip, caixa de ícone, campo pequeno */
--r-md: 8px;    /* botão, card, campo */
--r-lg: 12px;   /* modal, hero, painel */
--ease: cubic-bezier(0.2, 0.7, 0.2, 1);
```

Transições entre 0,15s e 0,3s. Tudo que anima respeita
`prefers-reduced-motion: reduce` — regra única em `tokens.css`.

---

## Sentinela

```css
:root { --ds-carregado: 1; }
```

Não remover. O shell confere no boot e derruba o app com erro legível se o Design
System não tiver carregado. Ver [CONTRATO-VISUAL.md](CONTRATO-VISUAL.md), Regra 4.

---

## Tema escuro

**Não existe.** O template original tinha alternador `kyno`/`kyno-dark`, mas o Design
System não tem paleta escura, e inventar uma seria decisão de marca sem respaldo. O
alternador foi removido, não desativado.

Quando o Figma publicar a paleta, o caminho é redefinir os tokens sob
`:root[data-theme="dark"]` — nenhum componente precisa mudar, porque nenhum tem cor
fixa.

---

## Ícones

Não são arquivos: são SVG inline de `ds/icons.js`, 44 ícones Fluent System em
viewBox 20×20, traço 1,5.

```js
elemento.innerHTML = icon("checkCircle", 18);
```

```html
<span class="kpi__icone" x-init="$el.innerHTML = window.icon('taskList', 16)"></span>
```

Herdam `currentColor`, então acompanham o estado do componente sem variante por cor.

Disponíveis: `add`, `arrowLeft`, `arrowRight`, `at`, `building`, `calendar`, `check`,
`checkCircle`, `chevronDown`, `chevronRight`, `clock`, `copy`, `dismiss`, `download`,
`edit`, `errorCircle`, `eye`, `eyeOff`, `file`, `fileAdd`, `filter`, `gear`, `info`,
`key`, `layers`, `listaNumeros`, `listaPontos`, `lock`, `mail`, `money`, `person`,
`pin`, `play`, `refresh`, `search`, `send`, `shield`, `signout`, `sort`, `sparkle`,
`table`, `taskList`, `trash`, `userPlus`, `warning`.
