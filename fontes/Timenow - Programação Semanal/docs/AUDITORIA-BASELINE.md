# Auditoria de linha de base

Estado das três pastas de origem no momento em que o `Modelo desenvolvimento` foi criado.
Registro do ponto de partida — cada achado tem arquivo e linha, para que a correção seja
verificável depois.

**Data:** 13/08/2026
**Origens:** `Design-system/`, `Projeto_Piloto/`, `Template_Framework_Desenvolvimento/`
**Plano correspondente:** `../../PLANO-DE-ACAO.md`

---

## A — Bloqueadores

### A1. O template não conectava as páginas ao visual

| Evidência | Onde |
|---|---|
| `<link rel="stylesheet" href="/kyno-theme.css">` aponta para arquivo inexistente | `app/index.html:13` |
| `data-theme="kyno"` sem o CSS que define o tema | `app/index.html:2` |
| Fragmentos sem qualquer referência de estilo próprio | `app/_views/home.html`, `app/_views/page2.html`, `app/login.html` |
| Templates Jinja2 idem | `api/src/templates/**` |
| `app/_components/` documentado, inexistente no disco | `docs/ARCHITECTURE.md:18` |
| `app/_shared/data-layer.js` documentado, inexistente no disco | `docs/ARCHITECTURE.md:20` |

Consequência: todo o estilo vinha do DaisyUI CDN com tema padrão — não do tema Timenow.
Uma página nova nascia sem estilo e nada acusava.

**Correção:** §4 do plano (Contrato de carregamento visual), Regras 1 a 5.

### A2. Duas camadas de estilo incompatíveis

`btn btn-primary` (DaisyUI) e `btn btn--primary` (Design System) — mesma classe base,
semânticas diferentes. Sete arquivos usavam Tailwind/DaisyUI:

`app/index.html` · `app/login.html` · `app/_views/home.html` · `app/_views/page2.html`
`api/src/templates/items/list.html` · `api/src/templates/items/greet_form.html`
`api/src/templates/nav/main_nav.html`

**Correção:** decisão D1 — Design System como camada única.

### A3. Dois shells de navegação incompatíveis

Template: topbar horizontal (`navbar` DaisyUI). Design System: sidebar de 300px, com
medidas justificadas em comentário — `Design-system/css/shell.css:34-43`, `:67`, `:81-90`.

**Correção:** D1 — a sidebar é o padrão.

---

## B — Consolidação do Design System

### B1. `icons.js` duplicado e divergente

| Arquivo | Linhas | Situação |
|---|---:|---|
| `Design-system/icons.js` | 87 | Desatualizado |
| `Design-system/js/icons.js` | 93 | Superset estrito — canônico |

Faltam na cópia da raiz: `file`, `fileAdd`, `taskList`, `info`, `listaPontos`,
`listaNumeros`. Verificado por `diff`: só há adições, nenhuma remoção.

### B2. Assets duplicados

`Design-system/assets/` — 32 arquivos, 4,9 MB. 21 com nome UUID, 11 com nome semântico.
Os 11 semânticos são cópias byte a byte (md5 conferido) de 11 dos UUID, que permanecem:

| UUID | Nome semântico |
|---|---|
| `83fb9e25-23f5-446f-8305-1840a0ded819.png` | `ilustra-acesso-negado.png` |
| `ab8087c0-667f-45c3-815b-d59e72975325.png` | `ilustra-salvo.png` |
| `5984a587-a397-40b3-995e-efc41e41411a.png` | `favicon-timenow.png` |
| `77f474e5-a0a0-46c6-b80a-4241800b0a29.png` | `ilustra-em-construcao.png` |
| `85be19f1-70be-4141-ada9-4f8ad6d9da4a.gif` | `loading-pequeno.gif` |
| `13235a03-c406-4f37-9849-588f5ddca3fb.png` | `ilustra-sucesso.png` |
| `78dca531-8928-4df1-bff8-e40600157202.png` | `ilustra-erro.png` |
| `6cb10a8b-080b-48be-b55e-8b46c257eda2.png` | `ilustra-aviso.png` |
| `e383ae33-4eb5-4718-9d3e-471ea1bab6d2.png` | `ilustra-atualizacao.png` |
| `c4b39cf5-bf74-408b-b263-d15ea6040db0.gif` | `loading-pagina.gif` |
| `a0001111-94f6-429c-8981-ff6eeffdb786.png` | `ilustra-manutencao.png` |

Restam **10 arquivos UUID sem nome semântico**, a batizar na tarefa 1.2 — entre eles
`84c87e11-…svg` (1600×900, aparentemente o fundo do hero) e 5 ícones SVG soltos.

---

## C — Dívidas técnicas

| # | Achado | Onde |
|---|---|---|
| C1 | `.app`, `.card` e `.card__head` declarados em dois arquivos com valores conflitantes; resolve por ordem de carga | `tokens.css:102,189,191` vs. `shell.css:24,131,132` |
| C2 | `--font-label: "Montserrat"` nunca carregada — sem `@font-face`, sem Google Fonts, sem arquivo de fonte em nenhuma das três pastas. Cai silenciosamente em Segoe UI | `tokens.css:63` |
| C3 | Assets referenciados por UUID dentro do código | `Projeto_Piloto/js/ui.js:77`, `Projeto_Piloto/index.html:8` |
| C4 | Prefixo `CAA_` específico do app em toda a camada de UI: `CAA_UI`, `CAA_Router`, `CAA`, `CAA_Modais`, `CAA_UI_Guard`, `CAA_Teardown`, `CAA_DEV` | `Projeto_Piloto/js/*.js` |
| C5 | Cabeçalho diz `App: Envio de Horas Extras`, mas o app é a Central de Ações e Atas — cópia entre projetos sem revisão | `Projeto_Piloto/css/tokens.css:3` |
| C6 | `--verde-100` (#C2DAE5) é azulado, não pertence à rampa verde; derruba o contraste de `--verde-700` para 3,76:1 — o próprio arquivo já registrava | `tokens.css:32-36` |
| C7 | Dependência `httpx2` — ver abaixo | `api/pyproject.toml:9` |
| C8 | `api/src/core/__init__.py` ausente, enquanto `src/` e `src/blueprints/` têm. Funciona por namespace package (PEP 420), mas é inconsistente | `api/src/core/` |
| C9 | `api/README.md` vazio (0 bytes), embora declarado como `readme` | `api/pyproject.toml:5` |

### C7 em detalhe — dependência `httpx2`

Achados da conferência do `uv.lock`:

- `httpx2` 2.9.1 e `httpcore2` 2.9.1, ambos publicados em **24/07/2026** — cerca de três
  semanas antes desta auditoria.
- Os nomes são adjacentes aos canônicos `httpx` / `httpcore`, e replicam sua árvore de
  dependências (`anyio`, `h11`, `idna`, `truststore`).
- O `httpx` canônico **não consta** do lockfile.
- **Nenhum código Python do projeto importa cliente HTTP** — verificado por `grep`.

Não há aqui afirmação sobre a legitimidade do pacote: pode ser uma reescrita legítima ou
um typosquat, e a auditoria não tem como decidir. Como a dependência **não era usada**, foi
retirada em vez de auditada — o caminho que dispensa a decisão.

**Estado:** removida de `api/pyproject.toml`. `api/uv.lock` ainda contém as entradas e
**precisa ser regerado com `uv lock`** — o `uv` não estava disponível nesta máquina no
momento da execução. Ver Pendências.

---

## Pendências abertas ao fim da Fase 0

| # | Item | Bloqueia |
|---|---|---|
| P1 | Rodar `uv lock` em `api/` para sincronizar o lockfile após a remoção de `httpx2` | Deploy e `uv sync --frozen` |
| P2 | Confirmar com o time se `httpx2` era intencional | Reversão da decisão C7, se for o caso |
| P3 | Decidir Montserrat: hospedar ou abandonar o token (C2) | Tarefa 1.4 |

---

## Paridade com o template na origem

Conferido por `diff` recursivo no momento da cópia:

| Área | Arquivos | Resultado |
|---|---:|---|
| `api/` | 22 | Idêntico (+ `core/__init__.py` novo, C8) |
| `app/lib/` | 2 | Idêntico |
| `.agents/skills/alpine-ajax/` | 11 | Idêntico |
| `docs/architecture-reviews/` | 1 | Idêntico |
| `docs/referencia/daisyui/` | 73 | Idêntico (arquivado, inativo) |
| raiz | 2 | Idêntico |
| **Total copiado** | **111** | **Zero divergência** |

Os 6 restantes — `app/index.html`, `app/login.html`, `app/staticwebapp.config.json`,
`app/_views/home.html`, `app/_views/page2.html`, `docs/ARCHITECTURE.md` — são os marcados
`~` na matriz §3.1 do plano, a serem reescritos nas Fases 2 e 5.
