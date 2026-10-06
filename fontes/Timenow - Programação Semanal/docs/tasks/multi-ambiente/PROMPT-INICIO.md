# Prompt de início de onda

Copie o bloco abaixo, substitua `{N}` pelo número da onda (1–8) e cole como
mensagem inicial em uma nova sessão do Claude Code, dentro do diretório do
projeto **Programação Semanal de Serviços**.

---

```
Estou entregando o multi-ambiente da Programação Semanal de Serviços (Timenow):
uma única instalação passa a hospedar vários ambientes de cliente, com seletor
depois do SSO, isolamento resolvido por requisição e API de leitura em JSON.

Fonte da verdade: `docs/SPEC-MULTI-AMBIENTE.md` — 70 histórias, 27 decisões e os
riscos aceitos. Se a spec e qualquer outro documento discordarem, a spec vence.
Ordem e critério de pronto: `docs/PLANO-MULTI-AMBIENTE.md` — 35 tarefas.
Issues: `docs/tasks/multi-ambiente/index.md` e `docs/tasks/multi-ambiente/*.md`.

Preciso que você execute a **Onda {N}**.

## Fluxo de trabalho

1. Leia `docs/tasks/multi-ambiente/index.md`, identifique as issues da Onda {N}
   e confirme que todas as issues das ondas anteriores estão com `status: done`.
   Se alguma não estiver, pare e me diga qual.
2. Para cada issue da onda, em ordem numérica crescente:
   a. Leia o arquivo `.md` da issue.
   b. Leia, na spec, as decisões citadas no campo `spec_decisions` do
      frontmatter — elas trazem o porquê, que a issue não repete.
   c. Implemente exatamente o que está em "O que construir". Nada além.
   d. Confira item por item os "Critérios de aceite" — todos precisam passar.
   e. Execute o que está em "Verificação" e rode a porta de qualidade:
      `npm run verificar` (cinco etapas: ruff check, ruff format, tipos, pytest,
      eslint + verificador do padrão Timenow).
   f. Se tudo passar, atualize o `status` no frontmatter da issue de `proposed`
      para `done`.
   g. Se algum critério falhar, ou se "Decisões humanas em aberto" não for
      "Nenhuma", pare e me pergunte antes de prosseguir.
3. Ao terminar todas as issues da onda, atualize a tabela do `index.md` com os
   novos status e me diga o que ficou pronto e o que não ficou.

## Regras

- Respeite `blocked_by`. Não comece uma issue cujo bloqueador não esteja `done`.
- A spec vence a issue e vence o plano. Decisão que contrarie o que está escrito
  na spec é anotada **na spec antes** de ser codificada, nunca depois.
- Falha fechada: nenhum código toca a base sem dizer de qual ambiente. Nunca
  caia num ambiente padrão, nunca adivinhe — recuse a requisição.
- Nenhuma supressão solta de regra de lint. Falso positivo estrutural se resolve
  na configuração, com comentário explicando o porquê.
- Fragmento novo não traz `<link>` nem `<script src>` — contrato visual.
  Classe visual nova, se houver, nasce no Design System e em um só dos três CSS.
- Antes de mexer em tela, carregue as skills do projeto: `timenow-design-system`,
  `alpine-ajax` e `padrao-de-codigo` (em `.agents/skills/`).
- Não invente configuração que já existe. O cadastro de unidades de medida já
  resolve qualquer forma de medir produção — o que faltava era isolamento.
- Não adicione funcionalidade além do que a issue pede. O que está em "Out of
  Scope" na spec continua fora: escrita pela API, escopo de token por empresa,
  webhook, dashboard entre ambientes, tema por cliente, RBAC customizável,
  grupos do Azure AD, ligar o SharePoint e limite de requisição.
- Este projeto **não é um repositório git**. Não tente commitar; ao fechar cada
  issue, registre o status no arquivo dela e no índice.
- Se encontrar conflito com algo entregue numa onda anterior, descreva o
  conflito e pergunte — não contorne.

Comece lendo o `index.md` e a primeira issue da onda.
```

---

## As oito ondas

A numeração das issues **é** a ordem de execução. O grafo de dependências deste
plano é uma fila: de ISSUE-001 a ISSUE-022, sem pular e sem paralelizar, nada
fica pendente fora de sequência.

| Onda | Issues | Entrega | O que fecha | Precisa de gente? |
|---|---|---|---|---|
| 1 — O isolamento existe e está provado | 001, 002 | 1 | Contexto de ambiente, base e trilha por cliente, registro global | Não |
| 2 — Ambientes existem e são operáveis | 003, 004 | 1 | Criação, concessão e revogação por linha de comando; perfil operador | Não |
| 3 — A aplicação volta, multi-ambiente | 005, 006 | 1 | Resolução por requisição, recusas, seletor e boot | Revisão de tela |
| 4 — A tela nunca mente sobre onde você está | 007, 008 | 1 | Sidebar com ambiente ativo; nome do cliente com fonte única | Revisão de tela |
| 5 — Demonstrável e publicado | 009, 010 | **1** | Modo demonstração com dois ambientes; primeira publicação com SSO real | **Sim** — Azure e duas pessoas reais |
| 6 — Administração em tela | 011–015 | **2** | Área do operador: listar, criar, membros, arquivar, marcar operador | Revisão de tela |
| 7 — O dado sai por HTTPS | 016–020 | 3 | Espaço de rotas, token, autenticação, quatro recursos, consumo amortizado | Não |
| 8 — Emissão e documentação | 021, 022 | **3** | Tela de tokens e contrato da API para o analista | Revisão de tela |

## Notas de uso

- **Não há paralelismo neste plano.** Diferente de um plano por camadas, aqui
  cada onda depende da anterior. Rodar duas sessões ao mesmo tempo produz
  conflito garantido nos mesmos arquivos — `_comum.py`, `repositorio.py` e
  `registro.py` são tocados por quase todas as ondas.

- **A janela vermelha.** A partir da ISSUE-001 a aplicação HTTP deixa de
  responder, porque os endpoints ainda não abrem ambiente por requisição e a
  persistência passou a falhar fechada. Isso é esperado, está anotado nas issues
  e **fecha na ISSUE-006**. Não tente "consertar" isso com um ambiente padrão:
  é exatamente a decisão 7 da spec, e um padrão silencioso é o defeito que a
  entrega inteira existe para impedir.

- **Ondas 6 e 7 são as maiores** (cinco issues cada). Se não couberem numa
  sessão, troque "a Onda {N}" por "as issues ISSUE-011 a ISSUE-013 da Onda 6" e
  siga em lotes — a ordem numérica continua valendo.

- **A Onda 5 para e espera por você.** A ISSUE-010 é a primeira publicação com
  SSO real: a sessão prepara tudo, mas o roteiro de seis passos precisa de você
  no portal e de duas pessoas reais entrando. É o risco aceito nº 1 da spec — se
  ninguém entrar em ambiente nenhum, a guarda da ISSUE-005 nomeia o e-mail
  recebido e a barreira que recusou, e o ajuste é na leitura da claim.

- **A ISSUE-022 também depende de gente:** o critério é um analista montar a
  primeira consulta lendo só a documentação.

- **Sem git, sem ponto de retorno.** O projeto não é um repositório. Antes de
  começar a Onda 1, ou rode `git init` e faça um commit inicial, ou copie a
  pasta do projeto — a Onda 1 apaga e semeia `data/` no layout novo (decisão 27:
  não há migração, e o conteúdo atual é carga de demonstração).

- **Cada onda é um ponto de parada seguro.** Dentro dela, a ordem das issues é
  obrigatória; entre elas, você pode parar, revisar e retomar noutro dia.
