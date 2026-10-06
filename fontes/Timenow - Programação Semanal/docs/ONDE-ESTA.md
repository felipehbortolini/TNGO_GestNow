# Onde está o quê

Mapa completo do repositório. Se você está procurando um arquivo e não sabe por
onde começar, é aqui.

---

## As três perguntas mais comuns

### "Onde está o Design System?"

**`app/ds/`** — `ds` é abreviação de *design system*.

```
app/ds/
├── tokens.css      Variáveis, componentes atômicos e TODAS as animações
│                     cores, tipografia, espaçamento, raio, sombra
│                     .btn .card .pill .input .modal .toast .empty
├── shell.css       Estrutura de tela
│                     .sidebar .page .guard .content .skip-link
│                     inclui o modo faixa horizontal abaixo de 900px
├── patterns.css    Composições prontas
│                     .kpis .toolbar .busca .linha .facepile .filtro-panel
│                     .matriz .painel .lancamento .grafico .heat .subnav
├── print.css       O relatório em papel (Ctrl+P vira o PDF)
├── charts.js       Os quatro gráficos SVG, sem biblioteca externa
│                     curva-s · barras · linhas · rosca
├── icons.js        Ícones Fluent + logo Timenow
│                     uso: window.icon("checkCircle", 16)
├── ui.js           Componentes imperativos, no objeto global TN
│                     TN.toast() TN.modal() TN.confirmarExclusao() TN.loading()
└── assets/
    ├── 11 ilustrações e GIFs em uso
    ├── fonts/Montserrat-latin.woff2
    └── _nao-utilizados/   10 arquivos órfãos, preservados mas fora do kit
```

**Nenhuma classe é declarada em dois dos três CSS principais** — isso é
verificado pela porta de qualidade, não confiado. É também por isso que as
animações moram todas em `tokens.css`: o verificador enxerga `from` e `to`
como seletores, e declará-los em dois arquivos reprovaria.

**Um gráfico não é um arquivo novo.** O servidor emite um
`<div data-grafico="curva-s">` com o payload num
`<script type="application/json">`, e o `charts.js` o encontra sozinho — no
boot, a cada troca de fragmento e a cada mudança de tamanho do container.

Documentação: [DESIGN-SYSTEM.md](DESIGN-SYSTEM.md) e [COMPONENTES.md](COMPONENTES.md).

### "Onde estão as páginas?"

Em **três** lugares, porque servem a papéis diferentes:

| Pasta | O que é | Quando mexer |
|---|---|---|
| **`app/_views/`** | **Páginas.** Cada arquivo é uma tela inteira | Criar ou alterar uma tela |
| `app/_components/` | Pedaços estáticos reutilizáveis entre telas | Extrair algo que repete |
| `api/src/templates/` | HTML que o **servidor** devolve | Mudar o que a API renderiza |

```
app/_views/                 (todas são esqueleto: o dado vem da API)
├── home.html               Estado da semana
├── programacao.html        A matriz — a tela de trabalho
├── dashboard.html          Aderência, avanço, mapa de calor e gargalos
├── importar.html           Importação em três passos
├── governanca.html         Consolidado por contratada e semana
└── configuracoes.html      Abre na subaba Geral

api/src/templates/
├── base_fragment.html      Raiz que todo fragmento estende
├── comum/                  recusado · erro · vazio · _faixa_status
├── nav/                    sidebar · perfil_demo
├── home/resumo.html        O que a tela inicial mostra
├── programacao/            multi · resumo · filtros · janela
│   ├── _tabela.html          a matriz
│   ├── _linha.html           uma atividade  ← partial
│   ├── _resumo.html          a faixa de KPIs ← partial
│   └── _macros.html          cabeçalho ordenável e célula do dia
├── atividade/              form · realizado · validar · aprovar · detalhe
├── dashboard/              painel · filtros · _ranking
├── importacao/             inicio · conferencia · resultado
├── governanca/             painel · trilha
├── configuracoes/          geral · cadastros · janelas · _abas
├── colaboradores/painel.html   a subaba restrita
└── relatorio/folha.html    a folha que vira PDF
```

**`multi.html` é a peça central da tela de programação.** Ela devolve
`#drawer`, `#prog-resumo` e `#prog-tabela` de uma vez, porque alvo declarado
no `x-target` que não vem na resposta é esvaziado pelo Alpine AJAX. O
`#drawer` vazio é o que fecha o painel ao salvar.

### "Por onde começo uma tela nova?"

Use **Governança** como molde simples (uma consulta, uma tabela) ou
**Programação** como molde completo (filtros, indicadores, painéis e o ciclo
de 422).

1. Crie o esqueleto em `app/_views/`
2. Crie o blueprint em `api/src/blueprints/`, decorando com `@com_usuario(...)`
3. Crie os fragmentos em `api/src/templates/`
4. Acrescente o item em `ITENS`, dentro de `api/src/blueprints/nav.py`, com a
   permissão que o libera
5. Rode `node scripts/verificar.mjs`

**Regra de negócio nova vai para `core/dados.py`**, nunca para o blueprint. O
blueprint chama, captura `RecusadoError` e `InvalidoError`, e devolve o
fragmento.

---

## Mapa completo

```
Timenow - Programação Semanal/
│
├── README.md                  Comece aqui
├── CONTEXT.md                 Glossário do domínio — o que cada termo significa
├── package.json               Ferramentas de front (só desenvolvimento)
├── eslint.config.mjs          Regras de JS, CSS e HTML
├── swa-cli.config.json        Configuração do Azure SWA local
├── .gitignore
│
├── app/                       ── FRONT-END (servido como está, sem build)
│   ├── index.html               O shell: único documento HTML completo
│   ├── login.html               Portão de login
│   ├── staticwebapp.config.json Rotas, autenticação, cabeçalhos
│   ├── ds/                      DESIGN SYSTEM
│   ├── _views/                  PÁGINAS
│   ├── _components/             Componentes estáticos
│   └── lib/                     Alpine.js e Alpine AJAX vendorizados
│
├── api/                       ── BACK-END (Azure Functions V4, Python)
│   ├── pyproject.toml           Dependências + regras do ruff e do ty
│   ├── requirements.txt         O que o deploy do Azure instala
│   ├── uv.lock                  Versões travadas
│   ├── function_app.py          Registro dos blueprints
│   └── src/
│       ├── blueprints/          ROTAS — um módulo por assunto
│       │                          _comum.py: gate, usuário, permissão, erro
│       ├── core/                O DOMÍNIO
│       │                          dados.py      a facade — toda regra do fluxo
│       │                          calculos.py   PPC, aderência, faixas
│       │                          semanas.py    calendário ISO
│       │                          janela.py     quando cada contratada escreve
│       │                          rbac.py       perfis e permissões
│       │                          auth.py       quem é o chamador
│       │                          ambiente.py   o ambiente ativo (ContextVar)
│       │                          registro.py   o registro de ambientes + criação com clonagem
│       │                          repositorio.py  a porta de persistência
│       │                          indicadores.py  os números dos gráficos
│       │                          planilha.py   Excel: modelo, leitura, saída
│       │                          auditoria.py  trilha append-only
│       │                          carga_inicial.py  o histórico da 1ª execução
│       ├── integracoes/         GANCHOS EXTERNOS
│       │                          sharepoint.py  a porta sobre listas
│       └── templates/           FRAGMENTOS que o servidor devolve
│
├── data/                      ── BASE LOCAL (criada na 1ª execução)
│   ├── registro.json           o registro de ambientes (quais existem, quem entra)
│   ├── registro-trilha.jsonl   a trilha do registro (criação, acesso, arquivamento)
│   └── <slug>/                 uma pasta por ambiente — programacao.json + auditoria.jsonl
│
├── docs/                      ── DOCUMENTAÇÃO
│   ├── ONDE-ESTA.md             Este arquivo
│   ├── PADRAO-DE-CODIGO.md      Fluxo obrigatório e ferramentas
│   ├── CLEAN-CODE.md            O que fazer e não fazer ao escrever
│   ├── ARCHITECTURE.md          Como o sistema funciona
│   ├── CONTRATO-VISUAL.md       Como o CSS chega em cada página
│   ├── DESIGN-SYSTEM.md         Tokens, rampas, tipografia
│   ├── COMPONENTES.md           Inventário com markup copiável
│   ├── PADROES-DE-PAGINA.md     Anatomia de tela, estados, responsivo
│   ├── CONVENCOES.md            Nomenclatura, idioma, organização
│   ├── CHECKLIST-NOVA-PAGINA.md Aceite antes do PR
│   ├── ACESSIBILIDADE.md        Auditoria de contraste e teclado
│   ├── ASSETS.md                Ilustrações e ícones
│   ├── PLANO-DE-ACAO.md         Histórico de como o template foi construído
│   ├── AUDITORIA-BASELINE.md    De onde cada peça veio
│   ├── architecture-reviews/    Revisões de arquitetura
│   └── referencia/
│       ├── clean-code/          Os 3 guias completos (7.000 linhas)
│       └── daisyui/             DaisyUI arquivado, inativo
│
├── scripts/                   ── FERRAMENTARIA
│   ├── instalar.ps1             Instala tudo e confere
│   ├── rodar.ps1                Sobe o app (roda a porta antes)
│   ├── ambiente.py              Administração do registro: criar, conceder, revogar,
│   │                              arquivar, desarquivar e listar (linha de comando)
│   ├── verificar.mjs            PORTA DE QUALIDADE — ruff, ty, eslint, padrão
│   ├── verificar-padrao.mjs     Só as 9 verificações do padrão Timenow
│   └── dev_local.py             Servidor local sem depender do func
│
└── .agents/skills/            ── SKILLS DE AGENTE (pasta oculta)
    ├── padrao-de-codigo         Fluxo obrigatório — a mais importante
    ├── timenow-design-system    Padrão visual
    ├── alpine-ajax              Fragmentos e x-target
    ├── grill-me                 Entrevista de negócio (só o usuário invoca)
    ├── improve-codebase-architecture  Dívida arquitetural (só o usuário)
    ├── codebase-design          Vocabulário de módulos
    ├── domain-modeling          Manutenção do CONTEXT.md
    └── grilling                 Aprofundar uma decisão
```

---

## Por que alguns nomes são assim

Três convenções que confundem quem chega e existem por um motivo:

**`ds` em vez de `design-system`.** Abreviação usada em todo caminho de
referência (`/ds/tokens.css`, `/ds/assets/...`). Trocar o nome exigiria mexer no
shell, na configuração do ESLint, na porta de qualidade e em toda a
documentação — mudança rastreável, mas sem ganho proporcional.

**`_views` e `_components` com underscore.** É convenção do Azure Static Web
Apps: o prefixo marca pastas que não são servidas como rota direta. Está
declarado em `app/staticwebapp.config.json`, que restringe o acesso a essas
rotas a usuário autenticado. Renomear romperia a compatibilidade com o padrão
herdado do template original.

**`.agents` e `.claude` com ponto.** Convenção de ferramenta — ficam **ocultas
no Explorer do Windows**. Para vê-las, ative "Itens ocultos" na aba Exibir.

---

## Onde NÃO procurar

| Pasta | Por que ignorar |
|---|---|
| `node_modules/` | Dependências do ESLint. Regenerável com `npm ci`, está no `.gitignore` |
| `api/.venv/` | Ambiente Python. Regenerável com `uv sync`, está no `.gitignore` |
| `app/lib/` | Alpine.js e Alpine AJAX minificados, vendorizados. Não editar |
| `docs/referencia/daisyui/` | Arquivo histórico, inativo. Não seguir como orientação |
| `app/ds/assets/_nao-utilizados/` | Arquivos órfãos preservados, fora do kit ativo |
| `data/` | Base local. Cada ambiente vive na própria pasta; o registro fica na raiz |
