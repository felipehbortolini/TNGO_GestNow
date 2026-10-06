---
name: padrao-de-codigo
description: >
  Fluxo obrigatório de desenvolvimento deste repositório: entender o negócio,
  desenhar, escrever, e passar pela porta de qualidade. Use SEMPRE antes de
  escrever ou alterar qualquer código aqui — Python, JavaScript, CSS ou HTML —
  e antes de dar qualquer tarefa por concluída. Define quais ferramentas rodam
  (ruff, ty, eslint), quando cada skill entra e o que precisa passar antes de
  um commit.
---

# Padrão de código — Timenow

Este repositório tem um fluxo obrigatório. Ele existe porque documentação não
impede defeito: o que impede é um comando que falha.

## Antes de escrever a primeira linha

**1. Entendeu o negócio?** Se o pedido tem qualquer ambiguidade sobre regra de
negócio, fluxo, permissão ou estado — pare e peça `/grill-me`. É melhor gastar
dez minutos de entrevista do que construir a tela errada com esmero.

Sinais de que falta entender: "quando o usuário X, deve acontecer Y" sem dizer
o que ocorre no caso limite; papel de acesso não definido; nenhuma menção ao
que acontece quando dá erro.

**2. É mudança estrutural?** Antes de mover módulo, criar camada ou trocar a
forma de um dado, use `/codebase-design` para o vocabulário (módulo, interface,
profundidade, costura) e `/improve-codebase-architecture` quando a pergunta for
"onde isto deveria morar".

**3. Nomeou um conceito novo?** `CONTEXT.md` é o glossário do domínio. Termo
novo entra lá — use `/domain-modeling`.

## Enquanto escreve

Siga os documentos do repositório, nesta ordem de precedência:

| Assunto | Documento |
|---|---|
| **O que fazer e não fazer ao escrever** | **`docs/CLEAN-CODE.md`** |
| Como o CSS chega na página | `docs/CONTRATO-VISUAL.md` |
| Tokens, cores, tipografia | `docs/DESIGN-SYSTEM.md` |
| Markup de componente | `docs/COMPONENTES.md` |
| Anatomia de tela e estados | `docs/PADROES-DE-PAGINA.md` |
| Nomenclatura e idioma | `docs/CONVENCOES.md` |

### Clean code — o essencial

O que a máquina já impõe (complexidade, número de argumentos, parâmetro
reatribuído, código morto, ternário aninhado) **não precisa ser lembrado**: o
gate falha sozinho. O que exige julgamento:

- **Nome que dispensa comentário.** Se precisa de comentário ao lado dizendo o
  que é, corrija o nome e apague o comentário.
- **Uma função, um nível de abstração.** Não misture regra de negócio com
  detalhe de renderização ou transporte.
- **Sem efeito colateral escondido.** Função que promete devolver valor não
  muta a entrada nem toca no DOM.
- **Condição com nome.** Expressão booleana longa vira variável nomeada.
- **Comentário registra o PORQUÊ**, nunca o quê.
- **Duplicação: extraia na terceira vez**, não na segunda — antes disso não se
  sabe qual eixo varia.

**Quatro pontos onde os guias conflitam com este repositório** e a convenção
local vence: marcadores posicionais (`════`) são usados, comentários de
justificativa são desejados, `window.icon`/`window.TN` são a interface de
exportação, e o DS usa objeto literal em vez de classe. A tabela com o
raciocínio está em `docs/CLEAN-CODE.md` — leia antes de "corrigir" qualquer um
deles.

E a skill `timenow-design-system` para o padrão visual.

## Antes de dar por pronto

**Rode a porta de qualidade. Sem exceção.**

```bash
node scripts/verificar.mjs
```

Cinco etapas, todas obrigatórias:

| Etapa | Ferramenta | O que pega |
|---|---|---|
| Lint Python | `ruff check` | Import morto, variável não usada, armadilha de sintaxe, datetime sem fuso, risco de segurança |
| Formato Python | `ruff format --check` | Formatação divergente |
| Tipos Python | `ty check` | Atributo que não existe, retorno que não bate com a anotação |
| Front | `eslint` | JS, CSS e HTML — correção, acessibilidade, compatibilidade |
| Padrão Timenow | `verificar-padrao.mjs` | Contrato visual, Design System, paridade com o template |

Boa parte é automática:

```bash
node scripts/verificar.mjs --corrigir
```

**Nunca desligue uma regra para fazer o gate passar.** Se uma regra acusa algo
legítimo, a saída é uma destas, nesta ordem de preferência:

1. Corrigir o código.
2. Se for **falso positivo estrutural**, ajustar a configuração com um
   comentário explicando o porquê — como já foi feito com `ARG001` nos
   blueprints (o Azure Functions exige o parâmetro `req` mesmo sem uso) e com
   `allowUnknownVariables` no CSS (os tokens moram em outro arquivo).
3. Nunca `# noqa` nem `eslint-disable` solto, sem justificativa escrita.

## O que NÃO é trabalho de linter

Formatação de HTML e comprimento de linha ficam com o formatador, não com o
linter. As duas coisas brigando geram ruído sem valor. Por isso `E501` está
desligado no ruff e as regras de `indent`/`quotes` do html-eslint ficaram de
fora.

## Ao terminar

Antes de abrir PR, além do gate: `docs/CHECKLIST-NOVA-PAGINA.md`.

## Skills deste repositório

| Skill | Quando | Invocação |
|---|---|---|
| `padrao-de-codigo` | Sempre — é esta | automática |
| `timenow-design-system` | Qualquer tela ou componente | automática |
| `alpine-ajax` | Fragmento, `x-target`, formulário | automática |
| `codebase-design` | Desenhar módulo e interface | automática |
| `domain-modeling` | Nomear conceito, escrever ADR | automática |
| `grilling` | Aprofundar uma decisão | automática |
| `grill-me` | Entender o negócio antes de construir | **só o usuário** |
| `improve-codebase-architecture` | Achar dívida arquitetural | **só o usuário** |

As duas últimas são marcadas `disable-model-invocation: true` pelos autores —
um agente não consegue dispará-las sozinho. Peça ao usuário quando forem
necessárias.
