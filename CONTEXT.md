# Glossário do domínio do Timenow GestNow

Vocabulário do Timenow GestNow. Termo usado em código, documentação e conversa
deve estar aqui — e significar exatamente isto.

Mantido pela skill `domain-modeling`: conceito novo entra no momento em que
aparece, não depois.

---

## Estrutura da aplicação

**Shell** — `app/index.html`. O único documento HTML completo da aplicação.
Carrega o Design System, consulta a sessão, monta a sidebar e hospeda a área de
conteúdo. Nunca é substituído; só o conteúdo dentro dele troca.

**View** — arquivo em `app/_views/`. Uma página. É um **fragmento**, não um
documento: sua raiz é `<main id="app-shell" class="content">` e ela substitui o
conteúdo do shell inteiro.

**Componente** — arquivo em `app/_components/`. Pedaço reutilizável e
**estático** de HTML, carregado por uma view. Se precisar de dado do servidor,
não é componente — é fragmento de API.

**Fragmento** — pedaço de HTML que o servidor devolve para ser trocado no DOM.
Estende `base_fragment.html` e carrega `{{ target_id }}` na raiz. É a unidade de
resposta da API: aqui o servidor devolve HTML pronto, nunca JSON.

**Partial** — template Jinja2 sem raiz nem id próprios, existente só para ser
incluído por outro (`{% include %}`). Nunca é alvo de `x-target`. Ex.:
um fragmento de linha compartilhado por uma lista.

**Alvo** (*target*) — o elemento do DOM que receberá um fragmento, declarado
pelo cliente em `x-target`. **Quem manda no destino é o cliente**, nunca o
servidor. Alvo declarado que não venha na resposta é **esvaziado** pelo Alpine
AJAX — por isso respostas com vários alvos precisam devolver cada fragmento esperado.

**Resposta multi-alvo** — resposta que traz vários fragmentos irmãos de uma vez,
cada um com seu id fixo, para atualizar mais de um bloco numa requisição. É a
única exceção à regra de não fixar id no servidor.

---

## Camada visual

**Design System** (DS) — `app/ds/`. A única fonte visual da aplicação. Três
arquivos, com fronteira nítida:

- **tokens.css** — variáveis e componentes atômicos (`.btn`, `.card`, `.pill`)
- **shell.css** — estrutura de tela (`.sidebar`, `.page`, `.guard`)
- **patterns.css** — composições (`.kpis`, `.toolbar`, `.facepile`, `.linha`)

Nenhuma classe é declarada em dois deles. Isso é verificado, não confiado.

**Token** — variável CSS que carrega uma decisão de design (`--brand-primary`,
`--space-lg`). **Valor de cor, espaçamento, raio ou sombra nunca é escrito
direto no código** — sempre por token.

**Contrato visual** — as cinco regras que garantem que toda página nasça
estilizada. Em `docs/CONTRATO-VISUAL.md`. A mais importante: só o shell carrega
estilo; fragmento nunca traz `<link>` nem `<script src>`.

**Sentinela** — a variável `--ds-carregado`, conferida pelo shell no boot. Se o
Design System não carregar, o app falha com mensagem visível em vez de servir
uma tela sem estilo.

---

## Backend

**Blueprint** — módulo em `api/src/blueprints/` que agrupa rotas relacionadas
(`func.Blueprint`). Registrado em `function_app.py`.

**Gate de fragmento** — a checagem `is_alpine_request(req)` no início de todo
endpoint de fragmento. Quem chega sem o cabeçalho do Alpine AJAX — navegador
digitando a URL, cURL — é redirecionado para o shell.

**AlpineAjaxResponse** — o único caminho pelo qual um fragmento sai do servidor.
Resolve o `target_id` a partir do cabeçalho, injeta no contexto e renderiza.

**Toast por cabeçalho** — mensagem ao usuário viaja em `X-TN-Toast` na resposta;
`ds/ui.js` a converte em toast. A página não precisa saber que isso aconteceu.

---

## Qualidade

**Porta de qualidade** — `scripts/verificar.mjs`. Cinco etapas obrigatórias
antes de qualquer commit. É o mecanismo real de imposição do padrão; a
documentação apenas explica.

**Paridade** — a garantia de que os arquivos herdados do
`Template_Framework_Desenvolvimento` continuam idênticos ao original. Rastreada
numa matriz no plano de ação, com cada arquivo marcado `=` (idêntico),
`~` (alterado) ou `+` (novo).

**Falso positivo estrutural** — quando uma regra de linter acusa algo que é
correto pela arquitetura do projeto. Resolve-se na configuração **com
comentário explicando**, nunca com supressão solta. Dois casos vivos: `ARG001`
nos blueprints (o Azure Functions exige `req` na assinatura) e
`allowUnknownVariables` no CSS (os tokens moram em outro arquivo).

---

## Termos que NÃO usamos

Vocabulário que já circulou por aqui e foi aposentado — se aparecer, é resquício:

| Não use | Use | Por quê |
|---|---|---|
| `CAA_*` | `TN` | Sigla de um app específico num kit que serve a todos |
| "componente" para fragmento de API | fragmento | Componente é estático, fragmento vem do servidor |
| `.ata-row`, `.ma-toolbar` | `.linha`, `.toolbar` | Nome de domínio de um app dentro do Design System |
| "topbar", "navbar" | sidebar | O shell padrão é a barra lateral de 300px |
| Tailwind, DaisyUI | Design System | Removidos pela decisão D1 |
