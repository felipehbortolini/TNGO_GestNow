# Arquitetura — Programação Semanal de Serviços

## Visão geral

Aplicação web sobre **Azure Static Web Apps** com backend serverless em
**Azure Functions V4** (Python). Segue o padrão hipermídia do modelo Timenow:
**Alpine.js**, **Alpine AJAX**, **Jinja2** e o **Timenow Design System**. Sem
bundler, sem etapa de build, sem framework pesado.

Herdada do `Modelo de Desenvolvimento Timenow`. As 14 decisões de arquitetura
do modelo foram preservadas; duas ganharam exceção documentada (decisões 1 e
12) e três decisões novas entraram, todas listadas abaixo.

---

## Estrutura

```
.
├── app/                          # Front-end estático
│   ├── index.html                # Shell: sidebar, área de conteúdo, overlays
│   ├── login.html                # Portão de login (público)
│   ├── ds/                       # Design System — fonte visual única
│   │   ├── tokens.css            #   variáveis, componentes base, animações
│   │   ├── shell.css             #   sidebar, layout de página, telas de guarda
│   │   ├── patterns.css          #   KPIs, matriz, painel, lançamento, gráficos
│   │   ├── print.css             #   o relatório em papel
│   │   ├── charts.js             #   curva S, barras, linhas, rosca
│   │   ├── icons.js              #   icon(nome, tamanho) + LOGO_FULL
│   │   ├── ui.js                 #   TN: toast, modal, confirmação, loading
│   │   └── assets/               #   ilustrações e GIFs, nome semântico
│   ├── _views/                   # Páginas — fragmentos de #app-shell
│   ├── lib/                      # Alpine.js e Alpine AJAX vendorizados
│   └── staticwebapp.config.json  # Rotas, auth, cabeçalhos
│
├── api/                          # Back-end (Azure Functions V4, Python ≥3.13)
│   ├── function_app.py           # Registro dos dez blueprints
│   └── src/
│       ├── blueprints/
│       │   ├── _comum.py         # gate + usuário + permissão + erro→status
│       │   ├── health.py         # GET  /api/health → JSON (a exceção)
│       │   ├── nav.py            # sidebar, filtrada por permissão
│       │   ├── programacao.py    # janela, filtros, indicadores, matriz
│       │   ├── atividades.py     # painéis e as seis transições do fluxo
│       │   ├── dashboard.py      # indicadores e payload dos gráficos
│       │   ├── importacao.py     # modelo → conferência → confirmação
│       │   ├── exportacao.py     # planilha e relatório para PDF
│       │   ├── governanca.py     # consolidado e trilha de auditoria
│       │   ├── configuracoes.py  # parâmetros, cadastros, janelas
│       │   └── colaboradores.py  # o controle de acesso (restrito)
│       ├── core/
│       │   ├── dados.py          # A FACADE — toda regra do fluxo
│       │   ├── calculos.py       # PPC, aderência, faixas, quebras
│       │   ├── semanas.py        # calendário ISO; ninguém mais faz data
│       │   ├── janela.py         # quando cada contratada pode escrever
│       │   ├── rbac.py           # perfis, permissões, vínculos
│       │   ├── auth.py           # quem é o chamador
│       │   ├── repositorio.py    # a porta de persistência + JSON local
│       │   ├── carga_inicial.py  # o histórico determinístico da 1ª execução
│       │   ├── indicadores.py    # os números de cada gráfico
│       │   ├── planilha.py       # Excel: modelo, leitura, exportação
│       │   ├── auditoria.py      # trilha append-only
│       │   ├── pii.py            # mascaramento de dado pessoal
│       │   ├── jinja_env.py      # ambiente + filtros e globais dos templates
│       │   └── responses.py      # AlpineAjaxResponse, is_alpine_request
│       ├── integracoes/
│       │   └── sharepoint.py     # a porta implementada sobre listas
│       └── templates/            # Fragmentos Jinja2
│
├── data/                         # base local em JSON (1ª execução cria)
├── docs/                         # Esta documentação
└── scripts/                      # instalar, rodar, verificar, dev_local
```

---

## Pilha

| Camada | Tecnologia | Papel |
|---|---|---|
| Reatividade | Alpine.js 3.14.8 | 15 KB, sem build, declarativo |
| Troca de fragmento | Alpine AJAX 0.12.7 | `x-target`, `$ajax`, formulários |
| Visual | Timenow Design System | CSS próprio, sem build |
| Gráficos | `ds/charts.js` | SVG puro, cores lidas dos tokens |
| Compute | Azure Functions V4 (Python) | Modelo V2, `func.Blueprint` |
| Templates | Jinja2 ≥3.1.6 | Fragmentos com herança |
| Planilha | openpyxl ≥3.1.5 | Modelo, leitura validada, exportação |
| Hospedagem | Azure Static Web Apps | Estáticos + `/api/*` + `/.auth/*` |

---

## As três camadas do servidor

```
blueprints/   HTTP: gate, permissão, forma da resposta
     │        Não conhece regra de negócio.
     ▼
core/dados    Domínio: quem pode mover o quê, e quando.
     │        Não conhece HTTP nem onde o dado mora.
     ▼
core/repositorio   Persistência: JSON hoje, SharePoint amanhã.
                   Não conhece regra nem requisição.
```

Cada seta é atravessada por um tipo só. O domínio devolve `dict` e levanta
`RecusadoError` ou `InvalidoError`; nenhuma outra forma de erro sobe. O
blueprint traduz as duas em 403 e 422 e não inventa uma terceira.

---

## Fluxo de requisição

### Boot

```
Carrega index.html
    │
    ├─ confere o sentinela --ds-carregado
    │     ausente → mostra erro e para (Regra 4)
    │
    ├─ GET /.auth/me
    │     sem sessão  → $ajax('/login.html')
    │     com sessão  → revela a sidebar
    │                   $ajax('/api/nav',   { target: 'main-nav'  })
    │                   $ajax(deep link,    { target: 'app-shell' })
```

### Uma mutação

```
Formulário do painel: x-target="drawer prog-resumo prog-tabela"
    │
    ▼  POST /api/atividade-realizado?chave=…
    ▼  dados.registrar_realizado() aplica a regra
    ▼  programacao/multi.html devolve os TRÊS blocos
    │      200 → #drawer vazio (o painel se fecha)
    │      422 → #drawer com o formulário e os erros
    ▼  Alpine AJAX troca os três de uma vez
```

Os três voltam sempre juntos porque **alvo declarado que não vem na resposta
é esvaziado pelo Alpine AJAX**. Devolver só a tabela apagaria os indicadores.

---

## Decisões de arquitetura

As 14 do modelo Timenow, preservadas, mais três desta aplicação.

**1. Hipermídia: fragmentos HTML, não JSON.** A API devolve HTML pronto.
*Três exceções:* `/api/health` (JSON, herdada do modelo), o payload dos
gráficos (decisão 15) e a API de leitura `/api/dados/v1/*` — JSON para
um consumidor que não é o navegador da aplicação, autenticada por token
de leitura e liberada como anônima na borda.

**2. Jinja2 com fragmento base.** Todo template estende `base_fragment.html`,
que fornece a raiz com o `id` correto por construção.

**3. `AlpineAjaxResponse` centraliza a renderização.** Resolve o `target_id`
do cabeçalho, injeta no contexto, renderiza e ajusta os headers — incluindo o
toast.

**4. O cliente é dono do destino.** Quem declara onde o fragmento vai é o
`x-target`. Exceção documentada: a resposta multi-alvo.

**5. Alpine AJAX, não HTMX.** Integra com a reatividade do Alpine.

**6. Sem bundler, sem build.**

**7. Carga declarativa com `x-init` + `$ajax`.** Cada região da tela se
carrega sozinha, e cada uma se atualiza pelo seu próprio motivo.

**8. Bibliotecas vendorizadas.** `app/` não faz nenhuma requisição externa.

**9. Navegação como fragmento de servidor.** *Estendido:* a sidebar agora
chega **filtrada por permissão** — o que o perfil não abre não está no DOM.

**10. Portão de login.** `/login.html` é estático e público.

**11. Autenticação delegada ao Azure SWA.** `/.auth/me`, `/.auth/login/aad`,
`/.auth/logout`.

**12. Gate de fragmento.** `is_alpine_request()` protege `/api/*`.
*Exceção:* os dois downloads (`exportar-semana`, `modelo-planilha`) ficam de
fora — o navegador pede um arquivo sem o cabeçalho do Alpine, e barrá-los
devolveria o shell no lugar da planilha. A permissão continua sendo checada.

**13. `/api/health` em JSON.** Único endpoint não-HTML da navegação.

**14. Design System como camada visual única.**

**15. Gráfico recebe dado, não SVG pronto.** *Nova.* O payload viaja num
`<script type="application/json">` dentro do fragmento e `ds/charts.js`
desenha. É exceção consciente à decisão 1: a curva S expande o mês ao clique
e se redesenha quando o container muda de tamanho — as duas coisas exigem a
série no navegador. Continua não havendo templating no cliente: o servidor
manda números, não marcação.

**16. Uma porta de persistência, resolvida por ambiente.** *Atualizada.*
`core/repositorio.py` é a única costura entre o domínio e onde o dado
mora. O ambiente ativo — um `ContextVar`, aberto por requisição — decide
**de qual ambiente** a porta é; fora de qualquer ambiente, pedir a porta
levanta. Trocar JSON por SharePoint continua sendo uma variável de
ambiente, e o mapa de colunas já está escrito.

**17. O cadastro de colaboradores é a autenticação.** *Nova.* O Azure prova
quem a pessoa é; o cadastro decide se ela entra e com qual perfil. Um e-mail
removido para de entrar na requisição seguinte.

**18. `com_usuario` ganha um irmão: `com_sessao`.** *Nova.* O decorador
clássico resolve na ordem gate → ambiente ativo → usuário → permissão. O
seletor e a administração do registro rodam **antes** de qualquer ambiente
existir — não podem resolver a pessoa contra um cadastro de colaboradores,
porque o cadastro vive dentro de um ambiente. Para eles, `com_sessao`
resolve só a identidade do provedor (o e-mail) e nada mais. Em modo
demonstração, devolve a identidade fixa `demo@timenow.local`, sempre
operadora.

---

## Convenções

### Blueprints — `api/src/blueprints/`

1. Criam `bp = func.Blueprint()`.
2. Decoram o handler com `@com_usuario(permissao)` — que já faz o gate, a
   resolução do usuário e a checagem.
3. Devolvem `AlpineAjaxResponse` para HTML.
4. Capturam `RecusadoError` e `InvalidoError` e passam para `erro_de_dominio`.
5. Nunca aplicam regra de negócio: isso é da facade.

### Templates Jinja2 — `api/src/templates/`

**Fragmento** — resposta de endpoint: estende `base_fragment.html`, conteúdo
em `{% block fragment %}`, nunca fixa `id` (usa `{{ target_id }}`), sem
`<html>`, `<head>`, `<body>`, `<link>` ou `<script src>`.

**Partial** — só incluído por outro, como `programacao/_linha.html`: sem raiz,
sem id.

**Armadilha registrada:** valor de texto livre nunca é interpolado dentro de
uma expressão Alpine. `| tojson` é marcado como seguro, então as aspas duplas
saem sem escape e fecham o atributo no meio — o componente morre em silêncio.
Vai por `data-*`, onde o autoescape funciona, e a expressão lê de
`$el.dataset`.

### Views — `app/_views/`

Raiz `<main id="app-shell" class="content">`, fragmento puro, autocontida.

---

## Rotas

| Método | Rota | Resposta |
|---|---|---|
| `GET` | `/api/health` | JSON |
| `GET` | `/api/ambientes-seletor` · `POST` `/api/ambiente-escolher` | o seletor e a escolha |
| `GET` | `/api/nav` · `/api/perfil-demo` | sidebar |
| `GET` | `/api/programacao` | indicadores + matriz (multi-alvo) |
| `GET` | `/api/programacao-resumo` · `-filtros` · `-janela` | blocos da tela |
| `GET` | `/api/atividade-form` · `-realizado` · `-validar` · `-aprovar` · `-detalhe` | painéis |
| `POST` | `/api/atividade` · `-realizado` · `-validar` · `-aprovar` · `-reabrir` · `-publicar` · `-excluir` · `-publicar-semana` | multi-alvo |
| `GET` | `/api/dashboard` · `/api/dashboard-filtros` · `/api/home-resumo` | indicadores |
| `GET` | `/api/importar-inicio` · `POST` `/api/importar-conferir` · `-confirmar` | importação |
| `GET` | `/api/exportar-semana` | `.xlsx` (download) |
| `GET` | `/api/modelo-planilha` | `.xlsx` (download) |
| `GET` | `/api/relatorio` | folha para impressão |
| `GET` | `/api/governanca` · `-trilha` | consolidado e auditoria |
| `GET/POST` | `/api/configuracoes-*` | parâmetros, cadastros, janelas |
| `GET/POST` | `/api/colaboradores` · `/api/colaborador` · `-remover` | acessos |

`scripts/dev_local.py` não repete esta lista: ele a lê de `function_app.py`.

---

## Desenvolvimento local

```powershell
.\scripts\rodar.ps1            # swa start, com fallback para o servidor Python
.\scripts\rodar.ps1 -Rede      # publica na rede local
```

---

## Produção

- **App location:** `app/`
- **API location:** `api/`
- **Output location:** `app/` (sem build, a saída é a própria fonte)

Antes de publicar, decida a origem dos dados: `PROGRAMACAO_ORIGEM=sharepoint`
e `PROGRAMACAO_MODO=producao` (qualquer valor diferente de `demo` exige SSO).
`PROGRAMACAO_OPERADORES` recebe os e-mails (separados por `;`) do papel global
que administra o registro de ambientes.

A primeira publicação com SSO real tem roteiro próprio de verificação —
os seis passos que separam as causas quando ninguém entra — em
`docs/PUBLICACAO-ENTREGA-1.md`.

**Item de verificação do deploy (Entrega 3):** confira que a entrada
anônima de `/api/dados/v1/*` está **acima** da entrada geral de `/api/*`
no array `routes` de `app/staticwebapp.config.json`. A borda avalia na
ordem, e a primeira que casa vence; abaixo, o consumidor recebe
redirecionamento de login em vez de JSON — e nada disso aparece no
servidor local, que não aplica esse arquivo.

---

## Caminho de crescimento

| Necessidade | Direção |
|---|---|
| Página nova | Fragmento em `_views/` + blueprint + entrada em `nav.ITENS` |
| Regra nova do fluxo | Uma função em `core/dados.py`; o blueprint só chama |
| Indicador novo | `core/indicadores.py` + um `data-grafico` no template |
| Trocar a base | Implementar `core/repositorio.Repositorio` |
| Aprovação em lote | Já existe o padrão em `atividade-publicar-semana` |
| Notificação por e-mail | Novo módulo em `src/integracoes/`, chamado pela facade |
| Testes | `pytest` na `api/`; Playwright para ponta a ponta |
