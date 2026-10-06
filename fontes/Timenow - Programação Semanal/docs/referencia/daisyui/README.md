# DaisyUI — referência arquivada

**Estes 73 arquivos não são orientação ativa.** Não siga o que está aqui ao escrever
código neste repositório.

---

## O que é

A skill do DaisyUI que vinha em `.agents/skills/daisyui/` no
`Template_Framework_Desenvolvimento`. Preservada íntegra, byte a byte, mas fora do
diretório de skills ativas.

## Por que saiu de `.agents/skills/`

O modelo adotou o Timenow Design System como camada visual única (decisão D1). O
DaisyUI e o Tailwind foram removidos de `app/`.

Uma skill ativa ensinando `class="btn btn-primary"` instruiria os agentes a violar
exatamente o padrão que este modelo existe para impor — e a colisão é literal:
`btn btn-primary` é DaisyUI, `btn btn--primary` é Timenow. Mesmo prefixo, sistemas
diferentes.

Arquivar em vez de apagar preserva o conteúdo sem deixar o padrão ativo ambíguo.

## O que usar no lugar

`.agents/skills/timenow-design-system/SKILL.md`, mais a documentação em `docs/`:

- `CONTRATO-VISUAL.md` — como o CSS chega em cada página
- `DESIGN-SYSTEM.md` — tokens e rampas
- `COMPONENTES.md` — inventário com markup
- `PADROES-DE-PAGINA.md` — anatomia de tela

## Equivalências

| DaisyUI | Timenow |
|---|---|
| `btn btn-primary` | `btn btn--primary` |
| `btn btn-ghost` | `btn btn--ghost` |
| `card` / `card-body` / `card-title` | `card` / `card__body` / `h-card4` |
| `badge badge-success` | `pill pill--ok` |
| `alert alert-error` | `aviso aviso--erro` |
| `navbar` | `sidebar` (ver `shell.css`) |
| `input input-error` | `input input--erro` |
| `loading loading-spinner` | `spinner` |
| `bg-base-100` | `background: var(--branco)` |
| `text-base-content` | `color: var(--text-primary)` |
| `hero` / `hero-content` | `home` / `home__conteudo` |
| `list` / `list-row` | `lista-simples` / `lista-simples__item` |
| `table` | `tbl` dentro de `tbl-wrap` |

## Se a decisão for revertida

Trazer o DaisyUI de volta reabre a decisão D1 e faz as duas camadas de estilo
conviverem. Nesse caso, mova esta pasta de volta para `.agents/skills/`, reative a
entrada em `skills-lock.json` e reveja `scripts/verificar-padrao.mjs`, cuja
verificação `sem-tailwind-daisyui` passaria a reprovar código legítimo.
