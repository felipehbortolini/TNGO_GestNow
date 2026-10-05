# Acessibilidade

Auditoria de 13/08/2026 sobre os tokens reais de `app/ds/tokens.css`. Razões de
contraste calculadas pela fórmula WCAG 2.1 de luminância relativa.

---

## Resumo

| | |
|---|---|
| Pares avaliados | 25 |
| Aprovam AA ou AAA | 24 |
| **Reprovam** | **0** |
| Informativo (não se aplica) | 1 |

**Nenhuma combinação de texto reprova.** A auditoria inicial encontrou sete
reprovações; todas foram corrigidas em 13/08/2026 com decisão de design registrada.

---

## Corrigido — contraste de cor

### 1. Texto branco sobre o verde da marca

Afetava os componentes mais usados do sistema. O botão primário tem 14px e peso
600, o que **não** se qualifica como "texto grande" pela WCAG (exige 18,66px em
negrito ou 24px normal), então o mínimo aplicável é 4,5:1 — e nem o hover
alcançava.

| Componente | Antes | Depois |
|---|---|---|
| `.btn--primary` | 3,02:1 sobre `--verde-500` | **7,09:1** sobre `--brand-primary` |
| `.btn--primary:hover` | 4,26:1 sobre `--verde-600` | **9,39:1** sobre `--brand-primary-hover` |
| `.modal--gen .modal__head` | 3,02:1 | **7,09:1** |
| `.mini-avatar` | 3,02:1 | **7,09:1** |

A marca já tinha um verde que funcionava: `--brand-primary` `#006457` era o fundo
do toast, com 7,09:1. Não foi preciso inventar cor — só usá-la onde havia texto.

O `--verde-500` **continua na paleta**, em elemento não textual: trilho de KPI,
caixa de ícone, anel de foco, trilho de toggle, sublinhado de aba. Ali o mínimo é
3:1 (WCAG 1.4.11) e ele passa com 3,02:1.

### 2. Escala de texto cinza

| Token | Antes | Depois | Onde aparece |
|---|---|---|---|
| `--text-secondary` | `#7D7D7D` · 4,12:1 | `#767676` · **4,54:1** | `.muted`, subtítulo, rótulo de campo |
| `--text-dimmed` | `#868E96` · 3,32:1 | `#6C757D` · **4,69:1** | Rótulo de seção, e-mail do usuário |
| `--text-hint` | *(usava `--neutro-400` `#A0A0A0` · 2,61:1)* | `#767676` · **4,54:1** | `.hint`, placeholder, metadado de linha |

O caso do auxiliar a 2,61:1 era o mais grave: ficava abaixo até do mínimo para
texto grande.

Em vez de escurecer o `--neutro-400`, foi criado o token `--text-hint`. O
`--neutro-400` é degrau da rampa neutra e existe para superfície, não para letra —
escurecê-lo desfiguraria a progressão (`300` `#B9B9BC` → `600` `#535358`). Os cinco
usos como texto passaram para o token novo; a rampa ficou intacta.

Os três tokens eram usados exclusivamente como `color`, nunca como fundo ou borda,
então o ajuste não mexeu em nenhum elemento decorativo.

---

## Informativo

**Borda de card** — `--borda` `#DEE2E6` sobre branco dá 1,30:1. A WCAG 1.4.11 exige
3:1 apenas para elementos gráficos necessários para identificar um controle. A borda
do `.card` é decorativa: o card não é interativo e seu conteúdo não depende dela para
ser compreendido. **Não é reprovação.**

Vale notar que o padrão Timenow tira a elevação da borda, não da sombra — então
essa borda é a única separação entre card e fundo. Em monitor de baixo contraste,
ela some. Não é violação, mas é frágil.

---

## Tabela completa

| Combinação | Razão | Nível |
|---|---|---|
| Texto de navegação sobre branco | 15,43:1 | AAA |
| Texto padrão sobre branco | 14,35:1 | AAA |
| Botão primário hover | 9,39:1 | AAA |
| Pill informativa | 8,97:1 | AAA |
| Título de página (`--brand-title`) | 7,19:1 | AAA |
| Botão primário · cabeçalho de modal · mini-avatar · toast | 7,09:1 | AAA |
| Pill de erro | 7,01:1 | AAA |
| Pill de sucesso | 6,23:1 | AA |
| Pill neutra | 5,56:1 | AA |
| Pill de aviso | 5,30:1 | AA |
| Verde 700 sobre verde 50 | 4,96:1 | AA |
| Botão de perigo | 4,93:1 | AA |
| Texto esmaecido | 4,69:1 | AA |
| Verde 700 sobre verde 100 | 4,55:1 | AA |
| Texto secundário · texto auxiliar | 4,54:1 | AA |
| Anel de foco (não texto) | 3,02:1 | AA |
| Trilho de KPI e de toggle (não texto) | 3,02:1 | AA |

Sete pares ficam com folga pequena sobre o mínimo (entre 4,54 e 4,69 para texto,
3,02 para não texto). **Qualquer ajuste futuro na paleta precisa recalcular esses
sete** — não há margem para arredondar.

> `--verde-100` era `#C2DAE5` e dava 3,76:1 com `--verde-700`. Corrigido na v2.4
> para `#D2F1EB`, que sobe para 4,55:1. Passa, mas com folga de 0,05 — qualquer
> ajuste futuro na rampa precisa recalcular este par.

---

## Corrigido na auditoria de teclado

Dois defeitos que a inspeção de código não pegou e só apareceram navegando:

### Componentes interativos sem indicador de foco

`.btn`, `.iconbtn`, `.tab`, `.seg__btn` e `.toggle` **não tinham nenhuma regra de
foco**. Quem navega por teclado passava por eles às cegas — e são os componentes mais
usados do sistema. Violação de WCAG 2.4.7 (Focus Visible).

Havia regra só para `.sidebar__item`, `.sidebar__logo-link`, `.kpi`, `.linha` e
`.input`. Agora existe uma regra única em `tokens.css` cobrindo os seis mais:

```css
.btn:focus-visible, .iconbtn:focus-visible, .tab:focus-visible,
.seg__btn:focus-visible, .toggle:focus-visible, a:focus-visible {
  outline: 2px solid var(--verde-500);
  outline-offset: 2px;
}
```

`:focus-visible` e não `:focus` — o anel aparece no teclado e não no clique de mouse.

### Nenhum item de navegação marcado na carga inicial

Na primeira carga a rota é `/`, enquanto o item de início aponta para
`/_views/inicio/home.html`. Sem equivalência entre os dois, nenhum item nascia com
`aria-current="page"` e leitor de tela não sabia informar onde a pessoa estava.
Corrigido em `nav/sidebar.html`.

## Auditoria automatizada — axe-core 4.13.0

Regras `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa` e `best-practice`, rodadas em cada
tela e em cada estado dinâmico.

| Tela / estado | Aprovados | Violações |
|---|---:|---:|
| Home | 25 | **0** |
| Exemplo | 38 | **0** |
| Página 2 | 31 | **0** |
| Formulário com erro 422 | 38 | **0** |
| Modal de confirmação aberto | 43 | **0** |

Duas violações foram encontradas e corrigidas nesta rodada.

### `heading-order` — esboço de cabeçalhos quebrado (moderado)

A tela de exemplo tinha `H1 → H3 → H2 → H2`. O componente `dica.html` entrava com
`<h3>` logo depois do título da página, e os estados vazios usavam `<h4>` dentro de
um card cujo cabeçalho é `<h2>`.

Quem navega por cabeçalho — atalho básico de leitor de tela — recebia um índice com
buracos.

A causa é conceitual: as classes `.h-card4` e `.h-card5` descrevem **tamanho
visual**, e quem escreve tende a pegar a tag do mesmo número. **Nível de cabeçalho é
semântico e independe do tamanho da fonte.** O seletor `.empty h4` foi trocado por
`.empty :is(h1,h2,h3,h4,h5,h6)`, justamente para não amarrar um nível.

### `aria-dialog-name` — diálogo sem nome acessível (sério)

O modal tinha `role="dialog"` e `aria-modal="true"` mas nada que o nomeasse. Ao
abrir, o leitor de tela anunciava só "diálogo" — sem dizer o que era. Na guarda de
saída, que não tem título visível, não havia nome nenhum.

Corrigido em `ds/ui.js`: o título ganhou `id` e o diálogo passou a apontar para ele
com `aria-labelledby`, de modo que o nome falado é o mesmo texto que está na tela.
Quando não há título visível, entra um `aria-label` descritivo — a guarda de saída
anuncia "Sair sem salvar as alterações".

### Região viva dos toasts

Verificado que `#toast-root` existe **vazio desde o carregamento** com
`role="status"` e `aria-live="polite"`, e que o toast é inserido dentro dela. A
ordem importa: leitor de tela só anuncia o que é inserido numa região que já estava
sendo observada — criar a região junto com o conteúdo não dispara anúncio.

Texto confirmado na região: "Registro criado."

## Corrigido na revisão da árvore de acessibilidade

A árvore de acessibilidade é exatamente o que um leitor de tela consome. Percorrê-la
revelou três lacunas que nem o axe nem o teste de teclado pegam:

### Cabeçalhos de tabela sem `scope`

Os cinco `<th>` não declaravam `scope`. Para tabela simples o navegador infere a
partir do `<thead>`, mas inferência não é garantia. Declarado, o leitor anuncia
"Responsável: Ana Souza" ao percorrer a linha, em vez de ler o valor solto.

### Tabela sem nome

Não havia `<caption>`. Quem navega saltando de tabela em tabela — atalho comum de
leitor de tela — ouvia "tabela, 5 colunas" sem saber de quê: o `<h2>Registros</h2>`
ao lado não viaja junto com a tabela. Resolvido com
`<caption class="sr-only">Registros cadastrados</caption>`, invisível na tela.

### Indicador de saúde da API mudava em silêncio

O texto do indicador troca sozinho de "API online" para "API offline" conforme a
resposta do `/api/health`. Sem região viva, essa mudança não era anunciada — quem
usa leitor de tela não tinha como perceber que a API caiu. Recebeu `role="status"`.

Depois das três, o axe subiu de 38 para **43 aprovados**, com quatro regras novas
de tabela passando (`scope-attr-valid`, `th-has-data-cells`, `table-duplicate-name`,
`empty-table-header`) e nenhuma violação.

## Auditoria de teclado — o que passou

Verificado com Tab real no navegador:

| Item | Resultado |
|---|---|
| Skip link é o primeiro no Tab | ✅ |
| Ordem de foco segue a ordem visual | ✅ skip → marca → 3 itens de navegação → sair → conteúdo |
| Todo elemento focável tem nome acessível | ✅ 8 de 8 |
| Item de navegação ativo com `aria-current="page"` | ✅ após a correção |
| Modal abre, leva o foco ao diálogo e fecha com Esc | ✅ |
| `:focus-visible` casa em foco por teclado | ✅ |

**Não verificado:** a renderização visual do anel de foco. O painel do navegador ficou
com `visibilityState: "hidden"` durante a auditoria, e nesse estado o motor não
recalcula o estilo — dá para confirmar que a regra existe e que o seletor casa, não
que o anel aparece na tela. Falta um passo manual com o navegador aberto.

## O que já está resolvido

Não são só cores. Estes pontos foram implementados e verificados:

- **Skip link** (`.skip-link`) no início do shell, visível ao receber foco
- **Foco visível** em todo componente interativo, com `outline-offset`
- **Modal** fecha com Esc, devolve o foco a quem abriu e leva o foco ao primeiro campo
- **`aria-modal="true"` e `role="dialog"`** no modal
- **`aria-current="page"`** no item de navegação ativo
- **`aria-label`** em todo botão só de ícone
- **`aria-invalid` + `aria-describedby`** em campo com erro
- **`aria-live="polite"`** na raiz de toasts e no overlay de carregamento
- **`prefers-reduced-motion: reduce`** desliga animação de `.anim`, `.toast`,
  `.modal` e `.modal-backdrop` — regra única em `tokens.css`
- **`.sr-only`** para rótulo destinado só a leitor de tela
- **Estado nunca só por cor** — toda pill traz o rótulo em texto
- **Imagem decorativa com `alt=""`** em ilustrações de guarda e estado vazio

---

## O que não foi verificado

Honestamente, esta auditoria é de código e paleta. **Não houve teste com leitor de
tela real** (NVDA, JAWS ou Narrator) nem navegação completa por teclado em navegador,
porque o app não chegou a subir — `func` e `swa` não estavam instalados na máquina
onde o modelo foi montado.

- [x] ~~Percorrer o app pelo teclado~~ — dois defeitos corrigidos
- [x] ~~Conferir a ordem de foco ao abrir e fechar o modal~~
- [x] ~~Rodar auditoria automatizada~~ — axe-core em 5 telas/estados, 2 defeitos corrigidos
- [x] ~~Verificar a região viva dos toasts~~ — estrutura e conteúdo conferidos
- [x] ~~Medir o anel de foco em cada parada de Tab~~ — 24 paradas, todas com anel
- [x] ~~Revisar a árvore de acessibilidade~~ — 3 correções aplicadas
- [ ] **Ouvir a leitura com NVDA**

## Anel de foco — medido, não visto

Percorrido com **Tab real** (evento de teclado, não `.focus()` programático),
lendo o estilo computado em cada parada:

| | |
|---|---|
| Paradas de Tab | 24 |
| Sem anel de foco | **0** |
| Sem casar `:focus-visible` | **0** |

Botões, links, itens de navegação e KPIs computam
`outline: solid 2px rgb(0, 167, 147)` com `outline-offset: 2px` — que é o
`--verde-500` da regra.

Campos de formulário usam outro mecanismo: borda `rgb(0, 167, 147)` mais halo
`rgba(0, 167, 147, 0.12) 0 0 0 3px`.

> **Cuidado ao repetir esta medição.** O primeiro resultado nos campos deu falso
> negativo: com o documento oculto (`visibilityState: "hidden"`) as **transições
> CSS não rodam**, e `.input` tem `transition: border-color .15s, box-shadow .15s`
> — o valor computado fica congelado no estado de repouso, por mais que se espere.
> Só neutralizando a transição (`transition: none`) os valores reais aparecem.
> O mesmo vale para o `top` do skip link.
>
> Houve ainda um erro no primeiro teste: tratar `box-shadow` diferente de `none`
> como "tem anel". Uma sombra `rgba(0,0,0,0) 0px 0px 0px 0px` é transparente e de
> tamanho zero — passa nesse teste e não desenha nada.

O que continua **não** verificado: a renderização em pixels. Estilo computado é o
que o motor usa para pintar, então a evidência é forte — mas não é o olho humano.

## Como fechar o que falta

**Anel de foco (confirmação visual).** Suba o app, dê Tab a partir do topo e
confirme que cada parada mostra o contorno verde. As 24 paradas e seus valores
computados estão acima; falta só o olho.

**NVDA.** Baixe em nvaccess.org, instale e ligue o Speech Viewer
(`NVDA+N` → Ferramentas → Visualizador de Fala), que mostra em texto o que seria
falado. Percorra:

1. Abrir a home — deve anunciar o título e a navegação como landmark
2. Tab pela sidebar — cada item pelo rótulo, o ativo como "página atual"
3. Ir para Exemplo e navegar por cabeçalhos com `H` — deve ler
   "Exemplo" → "Este é o modelo de referência" → "Novo registro" → "Registros"
4. Tab pelo formulário — cada campo deve anunciar o rótulo; envie vazio e confirme
   que o erro é lido junto do campo
5. Salvar um registro válido — o toast deve ser anunciado sem roubar o foco
6. Excluir — o diálogo deve anunciar "Confirmação de Exclusão"; Esc fecha e o foco
   volta ao botão de origem

O que a auditoria automatizada **não** cobre e só o ouvido pega: ordem de leitura
confusa, rótulo tecnicamente presente mas incompreensível em voz, e anúncio
repetido a cada troca de fragmento — este último é risco específico do modelo
hipermídia, onde o Alpine AJAX troca pedaços do DOM o tempo todo.

### Por que isto não foi automatizado

Foi tentado. O instalador oficial do NVDA (2026.1.1, hash SHA-1 conferido contra
o publicado pela NV Access) **inicia uma instância viva do leitor de tela** para
executar qualquer operação, inclusive a criação de cópia portátil — ou seja,
começa a falar pelos alto-falantes da máquina. Isso aconteceu duas vezes durante
a tentativa; os processos foram encerrados em seguida e nada ficou rodando.

Mesmo que a cópia portátil tivesse sido criada, a cadeia teria um elo quebrado:
seria preciso, ao mesmo tempo, **dirigir o app** e **ler o Speech Viewer**. O
painel do navegador estava oculto e a extensão do Chrome não estava conectada,
então não havia como fazer as duas coisas juntas.

A conclusão prática: **este teste é de gente, não de automação.** São 10 minutos
seguindo o roteiro acima.

Se for baixar, confira a integridade:

```
https://download.nvaccess.org/releases/2026.1.1/nvda_2026.1.1.exe
SHA-1: f35e30cd3c1c6375be52d0acaba701c5f6ddc7bd
```

---

## Como manter

As correções de cor foram todas em `tokens.css` — **nenhum componente mudou**. É a
vantagem de não ter valor de cor fixo no código: consertar contraste virou editar
seis linhas em vez de revisar o produto inteiro.

Para não regredir:

1. Nunca escreva cor fixa. Se falta um tom, ele entra na rampa.
2. Texto branco vai sobre `--brand-primary`, nunca sobre `--verde-500`.
3. Texto cinza usa `--text-secondary`, `--text-dimmed` ou `--text-hint` — não
   degraus da rampa neutra.
4. Ao mexer na paleta, recalcule os sete pares que estão no limite.
