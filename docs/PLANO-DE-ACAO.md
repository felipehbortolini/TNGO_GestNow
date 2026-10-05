# Plano de Ação — Padrão de Desenvolvimento Timenow

**Objetivo:** unificar Design System, framework tecnológico e padrões visuais de página
em um único kit executável na pasta `Modelo desenvolvimento/`, a partir do qual qualquer
aplicativo novo seja clonado.

**Data:** 13/08/2026
**Fontes:** `Design-system/`, `Projeto_Piloto/`, `Template_Framework_Desenvolvimento/`

> ## ⚠ Documento histórico
>
> Este plano foi escrito **durante** a consolidação e descreve a estrutura de
> então: três pastas de origem lado a lado com uma pasta `Modelo desenvolvimento/`
> sendo montada.
>
> **Essa estrutura não existe mais.** Ao fim do trabalho, em 13/08/2026:
>
> - o conteúdo de `Modelo desenvolvimento/` foi promovido para a raiz do
>   repositório — o que este documento chama de `Modelo desenvolvimento/algo`
>   hoje é apenas `algo`;
> - `Design-system/`, `Projeto_Piloto/` e `Template_Framework_Desenvolvimento/`
>   foram **removidos**, por decisão registrada em §13.
>
> Todo caminho citado daqui para baixo deve ser lido com esse deslocamento.
> O documento é mantido pelo registro de decisões e defeitos, não como guia de
> navegação — para isso, use o [README](../README.md).

---

## Estado da execução — 13/08/2026

**Fases 0 a 6 executadas.** O modelo está em `Modelo desenvolvimento/` (166 arquivos).

| Fase | Estado | Verificação |
|---|---|---|
| 0 — Fundação | ✅ | 111 arquivos herdados, `diff` limpo |
| 1 — Design System | ✅ | 0 colisões de seletor, 0 UUID, 0 prefixo de app |
| 2 — Porte para o DS | ✅ | 0 classe Tailwind/DaisyUI, 0 CDN |
| 3 — Padrões de página | ✅ | `patterns.css` com 9 composições |
| 4 — Exemplo CRUD | ✅ | 10 rotas, 18 checagens de endpoint passam |
| 5 — Documentação | ✅ | 10 documentos + skill de agente |
| 6 — Validação | ✅ | **App rodando e percorrido no navegador**, console limpo |

**O app subiu e foi percorrido de ponta a ponta:** login simulado, sidebar servida
pela API, criação, validação 422, busca, filtro vazio, exclusão com modal, toasts,
alias de `x-target`, Esc no modal e foco no diálogo. Console sem nenhum erro.

**Paridade confirmada:** os 28 arquivos marcados `=` passam em `diff` contra o
template; os 73 do DaisyUI estão íntegros em `docs/referencia/daisyui/`.
**Nenhum dos 117 arquivos foi perdido.**

### Achados que surgiram durante a execução

| # | Achado | Onde ficou |
|---|---|---|
| E1 | **7 pares de cor reprovam contraste AA**, incluindo texto branco sobre o verde do botão primário (3,02:1) | `docs/ACESSIBILIDADE.md` |
| E2 | `ui.js` gerava markup estilizado por 15 classes que viviam no CSS do app-piloto, não no DS | Extraídas para `tokens.css` |
| E3 | `.toast--erro` e `.toast--aviso` eram aplicadas pelo `ui.js` e **nunca definidas** — toast de erro saía verde | Definidas em `tokens.css` |
| E4 | `.guard-center` e `.guard-msg` idem — usadas pelo `modals.js`, nunca definidas | Definidas em `tokens.css` |
| E5 | Mais 2 colisões de seletor não previstas (`.modal`, `.modal-backdrop` em `prefers-reduced-motion`) | Consolidadas em `tokens.css` |
| E6 | **A Regra 3 não é implementável para `_views/` no Azure SWA** — o roteamento decide por caminho, não por cabeçalho | §4, Regra 3, reescrita |
| E7 | Os 10 assets sem nome semântico **não são referenciados em lugar nenhum**; um deles é o hero que o piloto removeu de propósito | Quarentena + `docs/ASSETS.md` |

### Achados da execução no navegador (Fase 6)

Só apareceram com o app rodando. Todos corrigidos e verificados.

| # | Achado | Correção |
|---|---|---|
| E8 | **Alvo do `x-target` ausente na resposta é esvaziado.** Criar um registro apagava o formulário da tela e deixava os KPIs congelados | `exemplo/multi.html` devolve os três blocos; miolo extraído para partials |
| E9 | **`{{ x \| tojson }}` em expressão Alpine quebra o atributo.** O filtro marca a saída como segura, as aspas duplas fecham o `@click` e o Alpine recebe expressão truncada — o botão de excluir não fazia nada | Texto passa por `data-*`, expressão lê de `$el.dataset` |
| E10 | **`ds/ui.js` lia `e.detail.xhr`, que não existe** no Alpine AJAX 0.12.7 — nenhum toast jamais dispararia. E ouvia `ajax:after`, que também não existe, então o overlay de carregamento nunca fecharia | Ponte reescrita sobre `detail.headers.get()` e `ajax:sent` |
| E11 | **`ajax:error` dispara no 422**, não só em falha de rede — um toast vermelho cobria os erros de validação inline | `ds/ui.js` ignora 4xx; só avisa em falha de rede ou 5xx |
| E12 | O instalador npm do `azure-functions-core-tools` baixa o binário truncado (288 MB de 588 MB) e falha com `ENOENT` | `scripts/dev_local.py` — equivalente local que roteia para os handlers reais |
| E13 | Deep link direto a `/_views/*.html` serve fragmento cru sem estilo — **confirmado empiricamente**, era previsão em E6 | Documentado; sem correção possível no roteamento do SWA |
| E14 | As mensagens de validação de `api_routes.py` estão em inglês, contra a convenção de interface em pt-BR | **Mantido de propósito** — o arquivo é `=` na matriz de paridade |

### Pendências

| # | Item | Estado |
|---|---|---|
| P1 | `uv lock` após remover `httpx2` | ✅ **resolvida** — 6 pacotes removidos da árvore |
| P2 | Contraste AA | ✅ **resolvida** — de 7 reprovações para **0** |
| P3 | Montserrat | ✅ **resolvida** — fonte variável hospedada, 38 KB, sem CDN |
| P4 | App rodando e percorrido no navegador | ✅ **resolvida** |
| P5 | Navegação por teclado | ✅ **resolvida** — 2 defeitos achados e corrigidos (E15, E16) |
| P5b | Auditoria automatizada + região viva | ✅ **resolvida** — axe-core em 5 telas/estados, 2 defeitos corrigidos (E18, E19) |
| P5c | Anel de foco e árvore de acessibilidade | ✅ **resolvida** — 24 paradas medidas, 3 defeitos corrigidos (E25–E27) |
| P5d | Escuta com NVDA | ⏳ pendente — **teste de gente**, ver §12 |
| P6 | `func` oficial | ✅ **resolvida** — 4.12.1 pelo winget; o npm não serve |
| P7 | `requirements.txt`, instalador e script de execução | ✅ **resolvida** — ver §10 |
| P8 | Padrão de código: ruff, ty, ESLint e skills de orquestração | ✅ **resolvida** — ver §11 |

### Achados da auditoria automatizada (P5b)

axe-core 4.13.0, regras `wcag2a`/`wcag2aa`/`wcag21a`/`wcag21aa`/`best-practice`,
em 5 telas e estados. Resultado final: **0 violações**.

| # | Achado | Impacto | Correção |
|---|---|---|---|
| E18 | **`heading-order`** — a tela de exemplo tinha `H1 → H3 → H2 → H2`. O componente `dica.html` entrava com `h3` e os estados vazios com `h4` dentro de card `h2`. Quem navega por cabeçalho recebia índice com buracos | moderado | Níveis corrigidos; `.empty h4` virou `.empty :is(h1..h6)` para não amarrar nível |
| E19 | **`aria-dialog-name`** — o modal tinha `role="dialog"` e `aria-modal` mas **nenhum nome acessível**. O leitor anunciava só "diálogo". Na guarda de saída, sem título visível, não havia nome nenhum | **sério** | Título ganhou `id` e o diálogo `aria-labelledby`; sem título, `aria-label` descritivo |

A causa de E18 é conceitual e virou regra na checklist: **`.h-card4`/`.h-card5`
descrevem tamanho visual, não nível de cabeçalho.** Quem escreve tende a pegar a
tag do mesmo número.

Também verificado que `#toast-root` existe vazio desde o carregamento com
`role="status"` e `aria-live="polite"`, e que o toast é inserido dentro dela —
leitor de tela só anuncia o que entra numa região já observada.

### Decisões de design tomadas em 13/08/2026

| Item | Escolha | Efeito |
|---|---|---|
| Verde de superfície com texto branco | `--brand-primary` `#006457` | Botão primário, hover, cabeçalho de modal e mini-avatar saem de 3,02:1 para **7,09:1 (AAA)**; o hover chega a 9,39:1 |
| Escala de cinza | Escurecer os três | `--text-secondary` → `#767676`, `--text-dimmed` → `#6C757D`, e o auxiliar ganhou token próprio `--text-hint` `#767676` |
| Montserrat | Hospedar | Fonte variável, 38 KB, subset latin, servida pelo próprio app |

O `--verde-500` **continua na paleta**, restrito a elemento não textual — trilho de
KPI, ícone, anel de foco, toggle, sublinhado de aba — onde o mínimo é 3:1 e ele
passa. A distinção entre ele e o `--brand-primary` virou regra documentada.

Para o auxiliar não foi escurecido o `--neutro-400`: ele é degrau da rampa neutra e
existe para superfície, não para letra. Escurecê-lo desfiguraria a progressão. Os
cinco usos como texto passaram para `--text-hint` e a rampa ficou intacta.

### Achados da auditoria de teclado (P5)

| # | Achado | Correção |
|---|---|---|
| E15 | **`.btn`, `.iconbtn`, `.tab`, `.seg__btn` e `.toggle` não tinham indicador de foco nenhum** — os componentes mais usados do sistema eram invisíveis para quem navega por teclado (WCAG 2.4.7) | Regra única de `:focus-visible` em `tokens.css`, cobrindo os seis |
| E16 | **Nenhum item de navegação nascia marcado.** Na carga inicial a rota é `/` e o item de início aponta para `/_views/home.html`; sem equivalência, o `aria-current="page"` nunca aparecia | `ativo()` em `nav/sidebar.html` trata `/` e `/index.html` como o primeiro item |
| E17 | O instalador **npm** do `azure-functions-core-tools` é inviável: baixa o binário truncado. O **winget** funciona (`Microsoft.Azure.FunctionsCoreTools`, 4.12.1) | `README.md` passa a indicar winget |

O que **não** deu para verificar: a renderização visual do anel de foco. O painel do
navegador ficou com `visibilityState: "hidden"` durante a auditoria, e nesse estado o
motor não recalcula estilo — dá para confirmar que a regra existe e que o seletor
casa, não que o anel aparece na tela.

### §10 — Instalação e execução (P7)

Três artefatos, pedidos depois de a Fase 6 já ter validado o app rodando:

| Arquivo | Papel |
|---|---|
| `api/requirements.txt` | Dependências de produção, exportadas do `uv.lock` (`uv export --format requirements.txt --no-dev --no-hashes`). Não é redundante com `uv.lock`: é o arquivo que o **deploy real do Azure Functions em Linux consome** — o build do Oryx procura `requirements.txt` na raiz de `api/` e roda `pip install` sozinho, enquanto `uv.lock` está em `.funcignore` e nem vai para o pacote implantado. |
| `scripts/instalar.ps1` | Confere Python e Node (pré-requisitos, não instalados pelo script), instala SWA CLI via npm, Azure Functions Core Tools via **winget** e sincroniza `api/` com `uv sync`. Idempotente — cada passo checa antes de agir. |
| `scripts/rodar.ps1` | Detecta se `swa`/`func` estão instalados **e funcionando** (roda `--version` de verdade, não só confere se o comando existe) e escolhe: `swa start` se os dois passam, senão cai para `scripts/dev_local.py`. Tem `-ForcarFallback` para testar o próprio fallback e `-Porta` para trocar a porta padrão. |

**Achado no caminho:** os dois `.ps1` foram salvos sem BOM UTF-8, e o PowerShell 5.1
não detecta UTF-8 sem BOM — leu os acentos como bytes soltos e isso quebrou o parser
(`Token ')' inesperado`, `Argumento ausente na lista de parâmetros`, e mais). Corrigido
prependendo `EF BB BF` aos dois arquivos. **Vale como nota geral para qualquer `.ps1`
com texto em português neste repositório:** salvar com BOM, ou o script quebra em
qualquer máquina rodando PowerShell 5.1 (que ainda é o padrão do Windows 10/11 fora do
PowerShell 7).

**Verificado nesta sessão:**

- `requirements.txt` instala limpo em venv isolado; `pip show` confere as 4 versões
  exatas do `uv.lock` (`azure-functions 2.2.0`, `jinja2 3.1.6`, `markupsafe 3.0.3`,
  `werkzeug 3.1.8` — os dois últimos são transitivos, não declarados em
  `pyproject.toml`).
- `instalar.ps1` rodado do zero: achou Python, Node, uv, swa e func já presentes
  (idempotência confirmada) e sincronizou `api/` com sucesso.
- `rodar.ps1` sintaticamente validado por `[Parser]::ParseFile` e, em execução real
  em segundo plano, escolheu corretamente o caminho `swa start` (processo filho
  confirmado com o `--config-name` certo) quando `swa`/`func` estão saudáveis.

Documentação atualizada em `README.md` (raiz) e `api/README.md`, incluindo a
correção de uma pendência que já estava obsoleta ali — a nota antiga dizia que
`uv.lock` ainda continha `httpx2`, mas isso tinha sido resolvido numa sessão anterior
(P1) sem que o texto fosse atualizado.

### §11 — Padrão de código (P8)

Ferramentas de qualidade e skills de orquestração, com imposição mecânica.

**Descobertas antes de instalar:**

- **`ruff` e `ty` já estavam no projeto** (`api/pyproject.toml`, grupo dev),
  instalados via `uv` e presos no `uv.lock`. O trabalho não era instalar, era
  **configurar** — rodavam só com os defaults mínimos (E4, E7, E9, F).
  Deliberadamente **não** foram instalados globalmente pelos scripts do
  astral.sh: versão global depende da máquina, e a mesma base passaria num
  lugar e reprovaria no outro.
- **`npm init @eslint/config@latest` é interativo** e não roda em sessão
  automatizada. Os pacotes foram instalados direto e a configuração escrita à
  mão, o que deu controle preciso sobre cada regra.
- **As duas skills pedidas estavam incompletas.** `grill-me` tem duas linhas e
  só diz "Run a `/grilling` session"; `improve-codebase-architecture` invoca
  `/codebase-design`, `/grilling` e `/domain-modeling`. Nenhuma dessas três
  veio junto — foram instaladas para fechar o grafo de dependências.

**Limite importante:** `grill-me` e `improve-codebase-architecture` trazem
`disable-model-invocation: true` no próprio frontmatter. **Um agente não
consegue dispará-las sozinho** — por decisão dos autores, só o usuário invoca.
O pedido de "obrigar a sempre passar" não pode, portanto, ser cumprido por
elas. A imposição real ficou onde ela funciona: num comando que falha.

**O que foi construído:**

| Peça | Papel |
|---|---|
| `scripts/verificar.mjs` | **Porta de qualidade única** — ruff check, ruff format, ty check, eslint e o padrão Timenow. Sai com código 1 se qualquer etapa falhar |
| `eslint.config.mjs` | ESLint 10 plano, cobrindo JS, CSS e HTML |
| `[tool.ruff]` e `[tool.ty]` | Conjunto de regras rigoroso mas prático, comentado regra a regra |
| `.agents/skills/padrao-de-codigo/` | Skill **model-invocável** que orquestra o fluxo — esta sim pode ser disparada automaticamente |
| `CONTEXT.md` | Glossário de domínio que as skills do Matt Pocock esperam encontrar |
| `docs/PADRAO-DE-CODIGO.md` | Documentação do fluxo e das decisões de configuração |

`rodar.ps1` passou a rodar a porta **antes** de subir o servidor, com escape
consciente (`-SemVerificar`). `instalar.ps1` instala o ESLint e valida a porta
ao final.

**Falsos positivos estruturais resolvidos na configuração, com comentário:**

| Regra | Por que era falso positivo |
|---|---|
| `ARG001` em `src/blueprints/` | O modelo V2 do Azure Functions **exige** `req` na assinatura de todo handler, mesmo sem uso (`/api/health`). "Corrigir" quebraria o registro da função |
| `allowUnknownVariables` no CSS | Tokens moram em `tokens.css` e são consumidos por `shell.css`/`patterns.css`; a regra valida arquivo por arquivo. Sem a opção: **99 falsos positivos** |
| Regras de formatação do html-eslint | O preset `recommended` traz `indent`, `quotes`, `require-closing-tags` — **458 reprovações**, quase todas por indentação de 2 espaços e por `<img />`, válido em HTML5 |
| `E501` no ruff | Comprimento de linha é assunto do formatador; linter e formatador brigando é ruído |
| `*.md` fora do `ruff format` | O ruff formata blocos Python dentro de Markdown e reescreveria os exemplos da documentação |

**Correções no código, decorrentes das ferramentas:**

| # | Achado | Correção |
|---|---|---|
| E20 | 44 declarações `var` no Design System | Convertidas para `const`/`let` — escopo de bloco evita uma classe de bug de closure. App revalidado no navegador, console limpo |
| E21 | `icons.js` exportava `icon`, `LOGO_FULL` e `logoAtom` por **vazamento implícito** do escopo de script | Exportação explícita via `window.X`, como `ui.js` já fazia. Envolver o arquivo num IIFE quebraria tudo em silêncio |
| E22 | `catch (err)` com binding não usado | `catch {}` — binding opcional |
| E23 | `datetime.now()` sem fuso em `api_routes.py` (DTZ005) | `datetime.now(UTC)` — hora ingênua não carrega o fuso consigo |
| E24 | 5 achados de espaço em branco e ordenação de import | Auto-corrigidos |

**Decisão de paridade:** os 6 achados restantes estavam em 4 arquivos marcados
`=`. Escolha registrada: **corrigir**. O motivo — uma porta de qualidade que
nasce vermelha não serve para nada, e 4 dos 6 eram espaço em branco (1 byte
cada).

Paridade recontada ao fim: **23 idênticos, 5 alterados** (era 28/0).

| Arquivo | Saiu de `=` porque |
|---|---|
| `src/blueprints/api_routes.py` | `datetime.now(UTC)` + quebra de linha no fim |
| `src/blueprints/health.py` | `timezone.utc` → `UTC` + quebra de linha no fim |
| `src/core/jinja_env.py` | espaço em branco sobrando |
| `src/core/responses.py` | quebra de linha no fim |
| `api/.funcignore` | passou a excluir `.ruff_cache/` do pacote de deploy |

**Armadilhas de plataforma encontradas:**

- `Join-String` é cmdlet do PowerShell 7 e **não existe no 5.1** — mesma
  família do problema de BOM registrado em §10. Trocado pelo operador `-join`.
- `spawnSync` com `shell: true` no Windows reparte caminho com espaço:
  "Padrao Desenvolvimento" e "Program Files" quebravam. A porta usa
  `shell: false` e chama o ESLint pelo seu entrypoint em JS, não por `npx`
  (que é `.cmd` e exige shell desde a correção de CVE-2024-27980).
- `@eslint/js` está na **10.0.1**, não acompanha a versão do ESLint (10.8.1).

### §12 — Anel de foco e leitor de tela (P5c / P5d)

**O bloqueio anterior era meu engano.** Eu havia registrado que o painel oculto
impedia medir o anel de foco. Revendo as notas, o teste com o skip-link **tinha
retornado** `outline: solid 2px rgb(0, 167, 147)` corretamente — o que falhou ali
foi só a transição de `top`, que é animação. `getComputedStyle` funciona com o
documento oculto; **transições CSS é que não rodam**.

Com isso, o anel de foco foi medido de verdade: **24 paradas de Tab real, todas
com anel, todas casando `:focus-visible`.**

| Componente | Indicador medido |
|---|---|
| Botões, links, navegação, KPIs | `outline: solid 2px rgb(0, 167, 147)`, offset 2px |
| Campos de formulário | borda `rgb(0, 167, 147)` + halo `rgba(0, 167, 147, 0.12) 0 0 0 3px` |

**Dois erros de método no caminho, que valem registro:**

1. Os campos deram falso negativo porque `.input` tem
   `transition: border-color .15s, box-shadow .15s` — com o documento oculto o
   valor fica congelado no repouso, por mais que se espere. Só neutralizando a
   transição os valores reais aparecem.
2. O primeiro teste tratava `box-shadow !== 'none'` como "tem anel". Uma sombra
   `rgba(0,0,0,0) 0px 0px 0px 0px` é transparente e de tamanho zero — passava no
   teste sem desenhar nada.

**Achados da revisão da árvore de acessibilidade** — que é o que o leitor de tela
consome, e nem o axe nem o teste de teclado alcançam:

| # | Achado | Correção |
|---|---|---|
| E25 | Os 5 `<th>` sem `scope`. Para tabela simples o navegador infere do `<thead>`, mas inferência não é garantia — declarado, o leitor anuncia "Responsável: Ana Souza" em vez do valor solto | `scope="col"` nos cinco |
| E26 | Tabela **sem nome**. Quem salta de tabela em tabela ouvia "tabela, 5 colunas" sem saber de quê; o `<h2>` ao lado não viaja com a tabela | `<caption class="sr-only">` |
| E27 | O indicador de saúde troca de "API online" para "API offline" **em silêncio** — quem usa leitor de tela não percebia a API cair | `role="status"` |

axe subiu de 38 para **43 aprovados**, zero violações, com quatro regras novas de
tabela passando.

**Sobre o NVDA (P5d).** Foi tentada a automação. O instalador oficial
(2026.1.1, SHA-1 conferido contra o publicado pela NV Access) **inicia uma
instância viva do leitor** para qualquer operação, inclusive criar cópia
portátil — ou seja, começa a falar pelos alto-falantes. Isso ocorreu duas vezes
durante a tentativa; os processos foram encerrados e nada ficou rodando.

Mesmo com a portátil criada, a cadeia teria um elo quebrado: seria preciso
**dirigir o app** e **ler o Speech Viewer** ao mesmo tempo, com o painel do
navegador oculto e a extensão do Chrome desconectada.

Conclusão registrada: **é teste de gente, não de automação.** Roteiro de 6 passos
e hash de verificação do instalador estão em `docs/ACESSIBILIDADE.md`.

---

## 1. Decisões congeladas

Estas três decisões orientam todo o plano. Não são reabertas durante a execução.

| # | Decisão | Escolha | Consequência |
|---|---|---|---|
| D1 | Camada de estilo | **CSS do Design System como camada única** | Tailwind CDN e DaisyUI saem do template. `tokens.css` + `shell.css` passam a ser a única fonte de verdade visual. |
| D2 | Modelo de renderização | **Fragmentos Jinja2 no servidor** (Alpine AJAX + `x-target`) | O padrão hipermídia do template é mantido. O router por hash do Piloto não vai para o modelo — seus padrões visuais vão. |
| D3 | Escopo do entregável | **Kit executável completo** | Shell + sidebar + DS + API Functions + auth SWA + 1 exemplo CRUD ponta a ponta + documentação + skills de agente. |
| D4 | Fidelidade ao template | **Núcleo tecnológico preservado integralmente** | Todo arquivo do `Template_Framework_Desenvolvimento` é herdado, salvo os que D1/D2 tornam contraditórios. Nada é omitido por esquecimento — ver a matriz de rastreabilidade em §3.1. |

**Fora de escopo nesta rodada:** galeria de componentes navegável (`/styleguide`), tema
escuro, migração do Projeto_Piloto para o novo modelo. Ver §7 (Dívidas registradas).

---

## 2. Auditoria — o que existe hoje

### 2.1 Panorama

| Pasta | Stack | Shell | Estilo |
|---|---|---|---|
| `Template_Framework_Desenvolvimento` | Azure SWA + Functions V4 (Python ≥3.13) + Alpine.js 3.14.8 + Alpine AJAX 0.12.7 + Jinja2 | Topbar (navbar DaisyUI), servida como fragmento `/api/nav` | Tailwind CDN + DaisyUI 5 CDN + `data-theme="kyno"` |
| `Design-system` | — | Sidebar 300px (documentada como "padrão Timenow") | `tokens.css` + `shell.css`, classes BEM (`.btn--primary`, `.card`, `.pill`) |
| `Projeto_Piloto` | Vanilla JS, sem build, router por hash | Sidebar 300px | Mesmo CSS do DS + 825 linhas específicas do app |

O `Design-system` é uma extração do `Projeto_Piloto`: `tokens.css` é idêntico byte a byte
entre os dois (só muda o comentário de cabeçalho) e `Design-system/js/icons.js` é idêntico
a `Projeto_Piloto/js/icons.js`. Isso é bom — significa que o DS já foi validado em 12 telas
reais. O que falta é consolidação, documentação e integração com o framework.

### 2.2 Achados — bloqueadores

**A1. O template não conecta as páginas ao visual.** *(bloqueador principal)*

- `app/index.html:13` referencia `/kyno-theme.css` — **o arquivo não existe** em `app/`.
  O `<link>` retorna 404 silenciosamente e o `data-theme="kyno"` do `<html>` nunca é
  definido. Todo o estilo que hoje aparece vem do DaisyUI CDN com o tema padrão.
- Nenhum fragmento de página carrega estilo próprio. `app/_views/home.html`,
  `app/_views/page2.html`, `app/login.html` e os templates Jinja2 em
  `api/src/templates/` dependem 100% de o shell já ter carregado Tailwind. Abertos
  direto na URL, renderizam sem estilo nenhum.
- Não há mecanismo que garanta isso. Uma página nova criada por qualquer pessoa
  simplesmente não fica estilizada, e nada acusa o erro.
- `ARCHITECTURE.md:18-20` documenta `app/_components/` e `app/_shared/data-layer.js`.
  **Nenhum dos dois existe.** A documentação descreve uma estrutura que não foi criada.

**A2. Duas camadas de estilo incompatíveis.** `btn btn-primary` (DaisyUI) vs.
`btn btn--primary` (DS) — mesmo nome de classe base, semânticas diferentes. Sete arquivos
do template usam classes Tailwind/DaisyUI e precisam ser reescritos:
`app/index.html`, `app/login.html`, `app/_views/home.html`, `app/_views/page2.html`,
`api/src/templates/items/list.html`, `api/src/templates/items/greet_form.html`,
`api/src/templates/nav/main_nav.html`.

**A3. Dois shells de navegação incompatíveis.** O template usa topbar horizontal
(`navbar` DaisyUI); o DS documenta sidebar de 300px com medidas justificadas em
comentário (`shell.css:34-43`, `:67`, `:81-90`). O DS vence por D1.

### 2.3 Achados — consolidação do Design System

**B1. `icons.js` duplicado e divergente.** Existem duas cópias:
`Design-system/icons.js` (87 linhas) e `Design-system/js/icons.js` (93 linhas).
A cópia de `js/` é superset estrito — a da raiz está desatualizada e não tem
`file`, `fileAdd`, `taskList`, `info`, `listaPontos`, `listaNumeros`.

**B2. Assets duplicados.** `Design-system/assets/` tem 32 arquivos (4,9 MB), sendo
21 com nome UUID e 11 com nome semântico. **Os 11 semânticos são cópias byte a byte
de 11 dos UUID**, que continuam na pasta. Sobram 10 arquivos UUID sem nome semântico —
incluindo `84c87e11-…svg` (1600×900, aparentemente o fundo do hero) e 5 ícones SVG soltos.

**C1. Colisões de CSS entre `tokens.css` e `shell.css`.** Resolvidas hoje por ordem de
carga, o que é frágil:

| Classe | `tokens.css` | `shell.css` | Canônico |
|---|---|---|---|
| `.app` | `height:100vh; overflow-y:auto` (linha 102) | `display:flex; height:100vh; overflow:hidden` (linha 24) | `shell.css` — sidebar é o padrão |
| `.card` | sem borda (linha 189) | `border: 1px solid var(--borda)` (linha 131) | `shell.css` — "elevação vem da borda, não da sombra" |
| `.card__head` | linha 191 | linha 132 (idêntico) | duplicação pura, remover uma |

**C2. `--font-label: "Montserrat"` nunca é carregada.** Não há `@font-face`, `<link>` para
Google Fonts nem arquivo de fonte em nenhuma das três pastas. Toda tipografia com
`var(--font-label)` (aglutinador, cabeçalho de tabela, título de tela de guarda) cai
silenciosamente no fallback `"Segoe UI"`.

**C3. Assets referenciados por UUID dentro do código.** Ex.: `Projeto_Piloto/js/ui.js:77`
fixa `assets/85be19f1-….gif` para o overlay de loading, e `index.html:8` usa
`assets/5984a587-….png` como favicon. Nomes ilegíveis, impossíveis de auditar.

**C4. Prefixo `CAA_` é específico do app.** `CAA_UI`, `CAA_Router`, `CAA`, `CAA_Modais`,
`CAA_UI_Guard`, `CAA_Teardown`, `CAA_DEV` — "Central de Ações e Atas". Precisa virar
prefixo neutro no modelo.

**C5. Cabeçalho errado em `Projeto_Piloto/css/tokens.css:3`:** diz `App: Envio de Horas
Extras`, mas o app é a Central de Ações e Atas. Sinal de cópia entre projetos sem revisão —
exatamente o problema que este modelo resolve.

**C6. `--verde-100` (#C2DAE5) não pertence à rampa verde** — é azulado, e o próprio
`tokens.css:35-36` já registra que isso derruba o contraste de `--verde-700` para 3,76:1.

**C7. Verificar a dependência `httpx2>=2.9.1`** em `api/pyproject.toml:10`. O pacote HTTP
padrão do ecossistema Python é `httpx`. Confirmar se `httpx2` é intencional e legítimo
antes de levar para o modelo — nenhum código do template importa qualquer cliente HTTP.

**C8. `api/src/core/__init__.py` não existe.** `src/__init__.py` e
`src/blueprints/__init__.py` existem, mas `src/core/` não tem. Funciona por *namespace
package* (PEP 420), então nada quebra hoje — mas é inconsistente com os outros dois
pacotes e frágil diante de empacotamento ou de ferramenta que não suporte PEP 420.

**C9. `api/README.md` está vazio** (0 bytes), embora seja declarado como `readme` em
`pyproject.toml:5`.

---

## 3. Estrutura-alvo

Legenda: `=` idêntico ao template · `~` herdado com alteração · `+` novo
**Nada leva `−`: nenhum arquivo do template é descartado.**

```
Modelo desenvolvimento/
├── skills-lock.json                       ~ raiz (como no template); daisyui marcado arquivado
├── swa-cli.config.json                    = 
├── README.md                              + como clonar e criar um app novo em 5 passos
├── .gitignore                             + raiz
│
├── docs/
│   ├── ARCHITECTURE.md                    ~ reescrito (sem Tailwind/DaisyUI; + sidebar e DS)
│   ├── architecture-reviews/              = processo do template, preservado
│   │   └── 2025-08-10.html                = (usa CDN — é documento, isento da Regra 5)
│   ├── referencia/
│   │   └── daisyui/                       = 73 arquivos preservados, inativos (§3.3)
│   ├── CONTRATO-VISUAL.md                 + como o CSS/JS chega em cada página (§4)
│   ├── DESIGN-SYSTEM.md                   + tokens, rampas, contraindicações
│   ├── COMPONENTES.md                     + inventário com markup copiável
│   ├── PADROES-DE-PAGINA.md               + anatomia de página, estados, responsivo
│   ├── CONVENCOES.md                      + nomenclatura, idioma, estrutura
│   ├── CHECKLIST-NOVA-PAGINA.md           + porta de aceite de PR
│   ├── ASSETS.md                          + mapa UUID → nome semântico
│   ├── ACESSIBILIDADE.md                  + auditoria da tarefa 6.3
│   └── AUDITORIA-BASELINE.md              + achados da §2
│
├── scripts/
│   └── verificar-padrao.mjs               + porta automatizada (Regra 5)
│
├── .agents/
│   └── skills/
│       ├── alpine-ajax/                   = 11 arquivos; skill é CSS-agnóstica (verificado)
│       └── timenow-design-system/         + skill ativa do padrão visual
│
├── app/
│   ├── index.html                         ~ reescrito: sidebar + DS, sem CDN
│   ├── login.html                         ~ reescrito: .guard do DS, pt-BR
│   ├── staticwebapp.config.json           ~ + regra 3 (fragmento direto → shell)
│   ├── lib/
│   │   ├── alpine-ajax-0.12.7.min.js      =
│   │   └── alpinejs-3.14.8.min.js         =
│   ├── ds/                                + DESIGN SYSTEM — fonte única
│   │   ├── tokens.css · shell.css · patterns.css
│   │   ├── icons.js · ui.js
│   │   └── assets/                        nomes semânticos, sem UUID
│   ├── _views/
│   │   ├── home.html                      ~ reescrito (hero do DS)
│   │   ├── page2.html                     ~ nome preservado; só reestilizado
│   │   └── exemplo.html                   + view do CRUD da Fase 4
│   └── _components/                       + documentado no template, nunca criado (A1)
│
└── api/                                   NÚCLEO TECNOLÓGICO — preservado
    ├── .funcignore                        =
    ├── .gitignore                         =
    ├── .python-version                    = 3.13
    ├── .vscode/extensions.json            =
    ├── README.md                          ~ vazio no template (C9) → preencher
    ├── host.json                          =
    ├── local.settings.json                =
    ├── pyproject.toml                     ~ revisar httpx2 (C7)
    ├── uv.lock                            ~ regerar só se pyproject mudar
    ├── function_app.py                    ~ +1 linha: registra exemplo_bp (nada removido)
    └── src/
        ├── __init__.py                    =
        ├── blueprints/
        │   ├── __init__.py                =
        │   ├── health.py                  =
        │   ├── api_routes.py              = rotas items/greet preservadas
        │   ├── nav.py                     ~ template_name → nav/sidebar.html
        │   └── exemplo.py                 + CRUD da Fase 4 (aditivo)
        ├── core/
        │   ├── __init__.py                + ausente no template (C8)
        │   ├── jinja_env.py               =
        │   └── responses.py               =
        └── templates/
            ├── base_fragment.html         =
            ├── items/                     ~ nomes preservados; só reestilizados
            │   ├── list.html · greet.html · greet_form.html
            ├── nav/sidebar.html           ~ main_nav.html reescrito
            └── exemplo/                   + list.html · form.html · row.html
```

### 3.1 Rastreabilidade — os 117 arquivos do template

Todo arquivo do `Template_Framework_Desenvolvimento` tem destino declarado. Nenhum é
omitido em silêncio.

| Área | Arquivos | `=` | `~` | arquivado | perdido | Observação |
|---|---:|---:|---:|---:|---:|---|
| `api/` | 22 | 13 | 9 | 0 | **0** | Núcleo intacto. As 9 alterações são reestilização e uma linha de registro — **nenhuma muda arquitetura**. |
| `app/` | 7 | 2 | 5 | 0 | **0** | Alpine e Alpine AJAX idênticos; os outros 5 são reestilizados, **sem renomear**. |
| `docs/` | 2 | 1 | 1 | 0 | **0** | `architecture-reviews/` preservado como processo. |
| `.agents/skills/alpine-ajax/` | 11 | 11 | 0 | 0 | **0** | Verificado: a skill não cita Tailwind nem DaisyUI. Carrega limpa. |
| `.agents/skills/daisyui/` | 73 | 0 | 0 | 73 | **0** | Movido para `docs/referencia/daisyui/` (§3.3) |
| raiz | 2 | 1 | 1 | 0 | **0** | `swa-cli.config.json` intacto; `skills-lock.json` marca o daisyui como arquivado. |
| **Total** | **117** | **28** | **16** | **73** | **0** | **Nenhum arquivo perdido.** |

### 3.2 Rastreabilidade dos padrões

Os 13 *Key Design Decisions*, as 4 convenções e as 5 rotas declaradas em
`docs/ARCHITECTURE.md`, um a um:

| # | Padrão do template | No modelo | Como |
|---|---|---|---|
| 1 | Hipermídia: fragmentos HTML, não JSON | **mantido** | D2 |
| 2 | Jinja2 com `base_fragment.html` | **mantido** | Arquivo byte a byte idêntico |
| 3 | `AlpineAjaxResponse` centraliza a renderização | **mantido** | `responses.py` byte a byte idêntico |
| 4 | Cliente é dono do `target_id` (`x-target`) | **mantido** | Inclusive a forma alias `page2-list:fragment-list` |
| 5 | Alpine AJAX em vez de HTMX | **mantido** | Skill preservada e verificada |
| 6 | Sem bundler, sem build | **mantido e reforçado** | D1 remove o Tailwind CDN, que era justamente o item que `ARCHITECTURE.md:501` previa precisar de build |
| 7 | Carga declarativa com `x-init` + `$ajax` | **mantido** | `_components/` finalmente criado (tarefa 4.6) |
| 8 | Bibliotecas vendorizadas | **mantido e estendido** | O DS também é local; zero CDN em `app/` |
| 9 | Navegação como fragmento do servidor | **mantido** | `/api/nav` segue servindo — agora a sidebar |
| 10 | Portão de login | **mantido** | `login.html` reestilizado, comportamento igual |
| 11 | Autenticação delegada ao Azure SWA | **mantido** | `/.auth/me`, `/.auth/login/aad`, `/.auth/logout` |
| 12 | Gate de fragmento (`is_alpine_request`) | **mantido e estendido** | Regra 3 leva o gate também aos fragmentos estáticos |
| 13 | `/api/health` em JSON | **mantido** | `health.py` byte a byte idêntico |
| C1 | Convenção de blueprints | **mantida** | `exemplo.py` segue o mesmo formato |
| C2 | Convenção de templates Jinja2 | **mantida** | Todos estendem `base_fragment.html` |
| C3 | Convenção de `_views/` | **mantida** | Raiz `<main id="app-shell">`, sem `<script>` |
| C4 | Convenção de `_components/` | **mantida** | Agora com pasta de verdade |
| R1-5 | `/api/health`, `/api/nav`, `/api/items`, `/api/greet-form`, `/api/greet` | **as 5 mantidas** | `api_routes.py` preservado; o CRUD da Fase 4 é **aditivo**, não substitui |

**Nenhum dos 22 padrões é abandonado.** Três são estendidos (6, 8, 12) e nenhum é
enfraquecido. A única alteração de comportamento visível é o shell: topbar → sidebar (D1).

### 3.3 A única contradição real, e como fica resolvida

`.agents/skills/daisyui/` é o único ponto onde "preservar todos os arquivos" e a decisão
D1 se chocam de frente: uma skill ativa ensinando `btn btn-primary` instruiria os agentes a
violar o padrão visual que o modelo existe para impor.

**Resolução:** os 73 arquivos são movidos íntegros para `docs/referencia/daisyui/`, com um
`README.md` explicando que são referência histórica, não orientação ativa. `skills-lock.json`
registra a entrada como arquivada. Nada é apagado; o padrão ativo fica sem ambiguidade.

> Se a intenção for manter o DaisyUI **ativo**, isso reabre a D1 — e as duas camadas de
> estilo voltam a conviver. É decisão sua; o plano hoje assume o arquivamento.

**Os 4 arquivos que definem o padrão hipermídia ficam byte a byte idênticos:**
`api/src/core/responses.py` (`AlpineAjaxResponse`, `is_alpine_request`, `redirect_to`),
`api/src/core/jinja_env.py`, `api/src/templates/base_fragment.html` e
`api/src/blueprints/health.py`. É a garantia concreta de que o padrão tecnológico não
sofreu deriva.

**As 9 alterações em `api/`, uma a uma:**

| Arquivo | Alteração | Por quê |
|---|---|---|
| `function_app.py` | **+1 linha**: registra `exemplo_bp` junto dos três existentes | Fase 4; nada é removido |
| `blueprints/nav.py` | `template_name="nav/main_nav.html"` → `"nav/sidebar.html"` | D1 (sidebar no lugar da topbar) |
| `templates/nav/main_nav.html` → `nav/sidebar.html` | Reescrito com markup do DS | D1 |
| `templates/items/list.html` | Reestilizado; nome e rota preservados | D1 |
| `templates/items/greet.html` | Reestilizado; nome e rota preservados | D1 |
| `templates/items/greet_form.html` | Reestilizado; validação 422 preservada | D1 |
| `pyproject.toml` | Revisar `httpx2` | C7 |
| `uv.lock` | Regerar apenas se `pyproject.toml` mudar | Reprodutibilidade |
| `README.md` | Preencher | C9 |

`blueprints/api_routes.py` **não muda** — só os templates que ele renderiza são
reestilizados. As rotas `/api/items`, `/api/greet-form` e `/api/greet` continuam
funcionando exatamente como hoje.

**Alterações estruturais fora de `api/`:** `app/index.html`, `app/login.html`,
`app/_views/*` e `app/staticwebapp.config.json` — todas decorrentes de D1 e da Regra 3
do contrato visual. `docs/ARCHITECTURE.md` é reescrito, inclusive para corrigir as pastas
que ele descreve e que não existem (A1).

---

## 4. Contrato de carregamento visual

> Resposta direta ao achado **A1**. É a regra que impede uma página nova de nascer sem estilo.

### Regra 1 — O shell é o único lugar que carrega o Design System

`app/index.html` carrega, **com caminho absoluto**, nesta ordem:

```html
<link rel="stylesheet" href="/ds/tokens.css">
<link rel="stylesheet" href="/ds/shell.css">
<link rel="stylesheet" href="/ds/patterns.css">
<script defer src="/ds/icons.js"></script>
<script defer src="/ds/ui.js"></script>
<script defer src="/lib/alpine-ajax-0.12.7.min.js"></script>
<script defer src="/lib/alpinejs-3.14.8.min.js"></script>
```

Caminho absoluto, não relativo: com `navigationFallback` reescrevendo qualquer rota para
`/index.html`, um deep link em `/exemplo/42` resolveria `ds/tokens.css` como
`/exemplo/ds/tokens.css` e quebraria. Nenhum CDN — o kit inteiro é servido pelo próprio app.

### Regra 2 — Fragmentos nunca carregam estilo próprio

Vale para `app/_views/*.html`, `app/_components/*.html` e todos os templates Jinja2.
Sem `<link>`, sem `<style>`, sem `<script src>`. O Alpine AJAX injeta o fragmento no DOM;
tags de recurso duplicadas seriam rebaixadas ou reexecutadas a cada navegação.
Estilo local, quando inevitável, vira classe no `ds/patterns.css`.

### Regra 3 — Fragmento acessado diretamente devolve o shell

Para `/api/*` o mecanismo já existe e foi preservado: `is_alpine_request()` em
`api/src/core/responses.py:15` redireciona para o shell quem chega sem o cabeçalho
`X-Alpine-Request`.

**Para os fragmentos estáticos de `_views/`, isso não é implementável no Azure SWA.**
O roteamento de Static Web Apps decide por caminho, não por cabeçalho de requisição —
não há como distinguir uma busca do Alpine AJAX de alguém digitando a URL. E o
`navigationFallback` não ajuda: ele só age em rota sem arquivo correspondente, e o
arquivo existe.

O que fica valendo:

| Situação | Comportamento | Avaliação |
|---|---|---|
| Sem sessão, acesso direto a `/_views/x.html` | 401 → redireciona para login | Resolvido — é o caso de segurança |
| Com sessão, acesso direto a `/_views/x.html` | Serve o fragmento cru, sem estilo | Residual cosmético |

O residual é cosmético, não uma falha de segurança: o conteúdo já é visível a quem
está autenticado, e a página apenas aparece sem estilo. Não vale distorcer a
arquitetura para eliminá-lo.

Quem quiser fechar isso por completo tem o caminho aberto pelo próprio template:
servir as views pela API (`/api/views/{nome}`), como já é feito com `/api/nav`, e
aí o gate de `is_alpine_request()` passa a cobri-las. O custo é abandonar a
convenção `app/_views/*.html` documentada em `ARCHITECTURE.md` — por isso o modelo
não faz isso por padrão.

### Regra 4 — A ausência de estilo falha alto, não em silêncio

`tokens.css` define um sentinela; o shell verifica no boot e, se não encontrar, mostra erro
visível em vez de renderizar uma página branca:

```css
/* tokens.css */
:root { --ds-carregado: 1; }
```

```js
/* verificação no boot do shell */
if (!getComputedStyle(document.documentElement).getPropertyValue('--ds-carregado').trim()) {
  document.body.innerHTML = '<pre style="padding:24px;font:14px monospace;color:#D03636">' +
    'Design System não carregou. Confira os &lt;link&gt; de /ds/ em index.html.</pre>';
}
```

Isso é exatamente o que faltou para o `/kyno-theme.css` faltante passar despercebido.

### Regra 5 — Porta automatizada

`scripts/verificar-padrao.mjs`, rodado no aceite de cada página e no CI:

| Verificação | Falha quando |
|---|---|
| Sem CDN | qualquer `href`/`src` externo **em `app/`** (`docs/` é isento: `architecture-reviews/2025-08-10.html` usa Tailwind e mermaid via CDN e é documento, não app) |
| Sem Tailwind/DaisyUI | classe `bg-base-*`, `btn-primary`, `navbar`, `card-body`, `text-base-content` |
| Fragmento limpo | `<link>`, `<style>` ou `<script src>` dentro de `_views/`, `_components/`, `templates/` |
| Recurso resolve | todo `href`/`src` local existe no disco (pegaria o `kyno-theme.css`) |
| Sem UUID | nome de asset em formato UUID |
| Sem prefixo de app | ocorrência de `CAA_` |
| Raiz do fragmento | todo `_views/*.html` começa com `<main id="app-shell" class="content">` |
| Paridade com o template | algum dos 28 arquivos marcados `=` em §3.1 divergiu do original |

---

## 5. Fases de execução

### Fase 0 — Fundação  ·  ~0,5 dia

| # | Tarefa | Critério de aceite |
|---|---|---|
| 0.1 | Criar `Modelo desenvolvimento/` com a árvore de §3 (pastas vazias com `.gitkeep`) | `swa-cli.config.json` aponta para `app/` e `api/` |
| 0.2 | Copiar `api/` **inteiro** do template — os 22 arquivos, incluindo `.funcignore`, `.gitignore`, `.python-version`, `.vscode/extensions.json`, `README.md` e `uv.lock` | `swa start` sobe e `/api/health` responde `{"status":"ok"}` |
| 0.3 | Copiar `app/lib/`, `.agents/skills/alpine-ajax/`, `swa-cli.config.json`, `skills-lock.json` e `docs/architecture-reviews/` | Arquivos servidos localmente, zero CDN |
| 0.4 | **C8** — criar `api/src/core/__init__.py` | Os três pacotes de `src/` declarados de forma consistente |
| 0.5 | Gravar `docs/AUDITORIA-BASELINE.md` com os achados da §2 | Cada achado com arquivo:linha |
| 0.6 | Resolver **C7** — confirmar ou remover `httpx2` de `pyproject.toml`; regerar `uv.lock` se mudar | Dependência justificada ou removida |
| 0.7 | Conferir a cópia contra a matriz de §3.1 | Os 44 arquivos herdados presentes; `diff` limpo nos 28 marcados `=` |

### Fase 1 — Consolidar o Design System  ·  ~1,5 dia

| # | Tarefa | Critério de aceite |
|---|---|---|
| 1.1 | **B1** — adotar `Design-system/js/icons.js` (superset) como `app/ds/icons.js`; descartar a cópia da raiz | 1 arquivo, 6 ícones a mais que a versão obsoleta |
| 1.2 | **B2** — renomear os 10 UUID restantes para nomes semânticos; excluir os 11 duplicados; gravar `docs/ASSETS.md` com o mapa UUID → nome | `assets/` sem nome UUID; tamanho cai de 4,9 MB |
| 1.3 | **C1** — eliminar as colisões: `.app` e `.card`/`.card__head` definidos uma única vez, na versão canônica da tabela de §2.3 | Nenhuma classe declarada em dois arquivos |
| 1.4 | **C2** — decidir Montserrat: hospedar `.woff2` em `ds/assets/fonts/` com `@font-face`, ou remover `--font-label` e assumir Segoe UI | Tipografia renderiza como especificado, ou o token some |
| 1.5 | **C6** — corrigir `--verde-100` para um tom da rampa verde e revalidar contraste de `--verde-700` | AA (≥4,5:1) sobre `--verde-50` **e** `--verde-100` |
| 1.6 | **C3/C4** — portar `Projeto_Piloto/js/ui.js` para `app/ds/ui.js`: prefixo `CAA_UI` → `TN`, asset de loading por nome semântico | Zero UUID e zero `CAA_` no arquivo |
| 1.7 | Extrair de `js/modals.js` só o genérico (guarda de saída com dados não salvos); o resto fica documentado como exemplo | `ds/ui.js` sem regra de negócio de ata/ação |
| 1.8 | Implementar o sentinela `--ds-carregado` (Regra 4) | Renomear `tokens.css` derruba o app com erro legível |

### Fase 2 — Portar o template para o Design System  ·  ~2 dias

| # | Tarefa | Critério de aceite |
|---|---|---|
| 2.1 | **A1/A2** — reescrever `app/index.html`: remover CDN Tailwind, CDN DaisyUI, `data-theme` e o `<link>` fantasma `/kyno-theme.css`; aplicar o bloco da Regra 1 | `grep -r "cdn\." app/` não retorna nada |
| 2.2 | **A3** — trocar topbar por sidebar: `<aside class="sidebar">` com `#main-nav` como alvo, `<main id="app-shell" class="content">`, `#modal-root`, `#toast-root`, skip-link | Layout idêntico ao `Projeto_Piloto/index.html` |
| 2.3 | Reescrever `api/src/templates/nav/main_nav.html` → `nav/sidebar.html` com o markup do DS (marca, divisor, rótulo de seção, itens de 52px, card de usuário) | Sidebar servida por `/api/nav`, item ativo marcado |
| 2.4 | Preservar do nav antigo: leitura de `/.auth/me`, indicador de health, entrar/sair. **Remover o alternador de tema** (ver Dívida R1) | Nome do usuário e status verde/vermelho aparecem |
| 2.5 | Reescrever `login.html` com `.guard` + ilustração + `.btn--primary`, em português | Sem classe Tailwind; texto em pt-BR |
| 2.6 | Reescrever `_views/home.html` com o hero do DS (`.home`, `.home__eyebrow`, `.home__titulo`, `.home__sub`, `.home__acoes`) | Bate com `Projeto_Piloto/pages/homepage.html` |
| 2.7 | Reestilizar `api/src/templates/items/*.html` com classes do DS — **nomes e rotas preservados** | Sem `card-body`/`badge`/`list`; `/api/items` e `/api/greet` seguem respondendo |
| 2.8 | Mover `.agents/skills/daisyui/` (73 arquivos) para `docs/referencia/daisyui/` + README de contexto; marcar como arquivada em `skills-lock.json` | Os 73 arquivos íntegros no destino; nenhuma skill ativa contradiz D1 |
| 2.9 | Aplicar a Regra 3 no `staticwebapp.config.json` | `/_views/home.html` no navegador carrega o shell inteiro |

### Fase 3 — Padrões visuais de página  ·  ~1,5 dia

> É aqui que o CSS/JS do Projeto_Piloto vira padrão reutilizável.

| # | Tarefa | Critério de aceite |
|---|---|---|
| 3.1 | Triar as 825 linhas de `Projeto_Piloto/css/app.css` em **genérico** vs. **específico do app** | Cada bloco classificado por escrito |
| 3.2 | Promover os genéricos para `app/ds/patterns.css`: tiles de KPI, toolbar de período/busca com lupa, facepile de avatares, micro-rótulo de grupo, linhas de lista, painel de filtros, barra de ações fixa no rodapé, telas de guarda, splash de carregamento | Cada padrão sem referência a ata/ação/kanban |
| 3.3 | Deixar de fora, documentando o porquê: kanban, formulário de ata, editor de notas, agenda do Teams, reincidência | Registrado em `docs/PADROES-DE-PAGINA.md` |
| 3.4 | Escrever `docs/PADROES-DE-PAGINA.md`: anatomia canônica (`.page` → `.page-head` → conteúdo), grid de formulário, tabela, os 5 estados (vazio, carregando, erro, sem permissão, sucesso), breakpoints 1100/760px | Uma pessoa monta uma tela nova só com o documento |
| 3.5 | Escrever `docs/COMPONENTES.md` — inventário com markup copiável dos 14 componentes do DS | Todo componente de `tokens.css` documentado |
| 3.6 | Escrever `docs/DESIGN-SYSTEM.md` — tokens, rampas, espaçamento, tipografia, contraindicações | Cada token com quando usar e quando não |

### Fase 4 — Exemplo CRUD ponta a ponta  ·  ~1,5 dia

| # | Tarefa | Critério de aceite |
|---|---|---|
| 4.1 | `api/src/blueprints/exemplo.py` — listar, formulário, criar, excluir, retornando fragmentos. **Aditivo**: `api_routes.py` continua registrado e funcionando | Todos via `AlpineAjaxResponse`, gated por `is_alpine_request`; as 5 rotas originais intactas |
| 4.2 | Templates Jinja2 `exemplo/{list,form,row}.html` estendendo `base_fragment.html`, com classes do DS | Sem `id` fixo: usa `{{ target_id }}` |
| 4.3 | `_views/exemplo.html` com `.page-head`, ações, `.card`, `.tbl` e estado vazio | Raiz é `<main id="app-shell" class="content">` |
| 4.4 | Ligar `ds/ui.js` aos eventos do Alpine AJAX (`ajax:success`, `ajax:error`) para toast e modal de confirmação | Excluir abre confirmação; sucesso dispara toast |
| 4.5 | Validação de formulário devolvendo 422 com o formulário reexibido e mensagens de erro | Erro de campo aparece sem recarregar a página |
| 4.6 | Criar `app/_components/` de fato, com ao menos um fragmento reutilizável | Some a divergência entre docs e disco (**A1**) |

### Fase 5 — Documentação e skills de agente  ·  ~1 dia

| # | Tarefa | Critério de aceite |
|---|---|---|
| 5.1 | Reescrever `docs/ARCHITECTURE.md` a partir do original: fora Tailwind/DaisyUI, dentro sidebar + DS + contrato visual; corrigir a estrutura descrita para bater com o disco | Nenhuma pasta documentada que não exista |
| 5.2 | `docs/CONTRATO-VISUAL.md` — as 5 regras da §4 | Cada regra com o exemplo de código |
| 5.3 | `docs/CONVENCOES.md` — nomenclatura BEM, prefixo global, idioma (pt-BR na interface), organização de arquivo | Explica por que `CAA_` não se repete |
| 5.4 | `docs/CHECKLIST-NOVA-PAGINA.md` — porta de aceite de PR | Executável em menos de 5 minutos |
| 5.5 | `.agents/skills/timenow-design-system/SKILL.md` — tokens, componentes, padrões de página e as regras do contrato visual | Agente gera página no padrão sem instrução extra |
| 5.6 | `README.md` da raiz — "criar um app novo a partir deste modelo" em 5 passos | Alguém de fora sobe o app na primeira tentativa |
| 5.7 | **C9** — preencher `api/README.md`, hoje vazio e declarado em `pyproject.toml:5` | Descreve blueprints, templates e como rodar só a API |

### Fase 6 — Validação  ·  ~0,5 dia

| # | Tarefa | Critério de aceite |
|---|---|---|
| 6.1 | Implementar `scripts/verificar-padrao.mjs` com as 7 verificações da Regra 5 | Roda limpo sobre o modelo |
| 6.2 | Subir com `swa start` e percorrer login → home → exemplo → CRUD → estados | Nenhum erro no console; nenhuma requisição externa |
| 6.3 | Acessibilidade: contraste AA em toda a paleta, foco visível, skip-link, `prefers-reduced-motion`, navegação só por teclado | Auditoria registrada em `docs/ACESSIBILIDADE.md` |
| 6.4 | Teste de deep link: recarregar em `/_views/exemplo.html` e navegar direto para `/api/exemplo` | Ambos carregam o shell estilizado |
| 6.5 | Teste de clonagem: copiar o modelo, renomear e criar uma tela nova em 30 minutos | Se falhar, é a documentação que está errada |

---

## 6. Ordem e dependências

```
Fase 0 ─┬─► Fase 1 (Design System) ─┐
        │                            ├─► Fase 3 (Padrões) ─► Fase 4 (CRUD) ─► Fase 5 ─► Fase 6
        └─► Fase 2 (Porte) ─────────┘
```

Fases 1 e 2 são paralelizáveis por pessoas diferentes; 3 depende das duas.
**Total: 8 a 9 dias** de trabalho focado.

Cada fase deixa a pasta em estado utilizável — não há big bang. Ao fim da Fase 2 já dá para
desenvolver no padrão; as Fases 3 a 5 aumentam a velocidade de quem chega depois.

---

## 7. Dívidas registradas

| # | Item | Decisão | Reavaliar |
|---|---|---|---|
| R1 | **Tema escuro** — o template tinha alternador kyno/kyno-dark; o DS não tem paleta escura, e inventá-la agora seria decisão de marca sem respaldo | Sai do modelo. O alternador é removido, não desativado | Quando o Figma publicar a paleta escura |
| R2 | **Galeria de componentes** (`/styleguide`) | Fora desta rodada (opção B não escolhida) | Após o primeiro app real nascer do modelo |
| R3 | **Migrar o Projeto_Piloto** para o novo modelo | Fora de escopo. O Piloto continua como está e serve de referência visual | Quando o modelo tiver rodado em um app novo |
| R4 | **Tokens de tipografia** — tamanhos de fonte hoje são valores fixos dentro das classes, não variáveis (`--fs-*`) | Documentar a escala existente, não criar tokens agora | Se surgir um segundo tema |
| R5 | **Tailwind compilado** — `ARCHITECTURE.md:501` sugeria CSS purgado para produção | Não se aplica mais: o DS puro tem ~18 KB sem build | — |

---

## 8. Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| Reescrever 7 arquivos de Tailwind para o DS revela componente sem equivalente | Trava a Fase 2 | Fazer o inventário de equivalência **antes** de codificar (tarefa 3.5 antecipada) |
| `ds/ui.js` é imperativo; o modelo servidor é orientado a evento | Toast/modal não disparam no fluxo hipermídia | Tarefa 4.4 é design de verdade, não integração trivial — reservar tempo |
| A triagem do `app.css` vira discussão sem fim | Atrasa a Fase 3 | Regra de corte: se o seletor cita ata, ação ou kanban, é específico do app |
| Perda de fidelidade visual em relação ao Piloto | Retrabalho | Comparação lado a lado tela a tela na tarefa 6.2 |

---

## 9. Definição de pronto

O padrão está pronto quando, partindo de `Modelo desenvolvimento/`:

1. `swa start` sobe o app com login, sidebar, home e CRUD funcionando.
2. Nenhuma requisição sai para host externo.
3. `scripts/verificar-padrao.mjs` passa nas 7 verificações.
4. Uma pessoa que nunca viu o projeto cria uma tela nova em até 30 minutos usando só `docs/`.
5. Um agente com a skill `timenow-design-system` gera uma tela no padrão sem instrução extra.
6. Toda página renderiza estilizada, inclusive por deep link — e, se o DS não carregar, o app falha de forma visível em vez de servir uma tela branca.
7. **Paridade com o template:** os 117 arquivos têm destino verificável pela matriz de §3.1, os 28 marcados `=` passam em `diff` contra o original, os 22 padrões de §3.2 estão presentes e as 5 rotas originais respondem.

---

## §13 — Consolidação em pasta única

Encerramento do trabalho, em 13/08/2026. Três decisões do usuário, todas
irreversíveis, tomadas depois de uma verificação de completude por hash de
conteúdo (SHA-256) de cada arquivo das pastas de origem contra o modelo.

### O que a verificação mostrou

| Pasta | Conteúdo ausente no modelo | Natureza |
|---|---:|---|
| `Design-system` | 4 | Versões **antigas** de arquivos já melhorados (tokens v2.3 vs v2.4, `icons.js` desatualizado) |
| `Template_Framework_Desenvolvimento` | 20 | Versões **antigas** dos arquivos reescritos, mais `uv.lock` regerado |
| `Projeto_Piloto` | **30** | **Conteúdo único** — 12 telas, router, store, modals, seed, `app.css` de 825 linhas |

Ou seja: as duas primeiras não tinham nada a perder, porque o que nelas existia
ou já estava no modelo, ou estava lá numa versão melhor. Só o Piloto tinha
material que não existia em nenhum outro lugar.

### Decisões

| Item | Escolha | Consequência |
|---|---|---|
| Projeto_Piloto | **Apagar de vez** | Os 30 arquivos deixaram de existir. Os padrões genéricos já haviam sido extraídos para `app/ds/patterns.css`; o que ficou de fora está documentado com o motivo em `PADROES-DE-PAGINA.md` |
| Histórico git do template | **Apagar sem preservar** | Os 16 commits foram perdidos junto com a pasta. O conteúdo dos 117 arquivos estava integralmente no modelo, verificado por hash — só o registro da evolução anterior se foi |
| Estrutura | **Promover à raiz** | `Modelo desenvolvimento/*` subiu para a raiz do repositório. Não há mais aninhamento: a pasta do projeto **é** o template |

### Execução

A ordem foi escolhida para permitir recuperação: promover e verificar primeiro,
apagar só depois.

1. `node_modules/`, `api/.venv/`, `.ruff_cache/` e `__pycache__/` removidos antes
   de mover — são regeneráveis, e o venv tem caminho absoluto embutido que não
   sobrevive a mudança de pasta.
2. Conteúdo promovido para a raiz.
3. As três pastas de origem removidas.
4. Ambientes restaurados (`uv sync`, `npm ci`) e symlinks de skill recriados —
   eles apontavam por caminho absoluto para dentro da pasta antiga.
5. `.claude/launch.json` e as referências de caminho na documentação corrigidas.
6. Porta de qualidade, testes de API e app no navegador revalidados.

**A partir daqui não há mais paridade a manter:** o template original não existe.
A matriz de §3.1 vira registro histórico. O que passa a valer como garantia é a
porta de qualidade — `node scripts/verificar.mjs`.
