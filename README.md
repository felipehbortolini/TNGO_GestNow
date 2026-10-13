# Timenow GestNow

Aplicação de gestão integrada de projetos de capital, construída sobre o Padrão de Desenvolvimento Timenow.

**Azure Static Web Apps** · **Azure Functions V4 (Python)** · **Alpine.js + Alpine AJAX** · **Jinja2** · **Timenow Design System**

Sem bundler, sem etapa de build e sem CDN.

## Estado

A migração do protótipo está concluída (93 de 93 issues; `PROGRESSO.md`), e o material de consulta das origens está preservado em `docs/referencia/`. O app sobe em modo demonstração pelo `run.bat`; para publicar no Azure, siga [`docs/PUBLICACAO-AZURE.md`](docs/PUBLICACAO-AZURE.md), e o aceite do dono está em [`docs/ROTEIRO-DE-ACEITE.md`](docs/ROTEIRO-DE-ACEITE.md).

**As sessões de trabalho abrem dentro desta pasta** — o repositório é a raiz do produto, e as skills de agente vivem em `.agents/skills/` e `.claude/skills/`, aqui dentro, com as versões da raiz para `grill-me` e `grilling` (Q34).

## Rodar localmente

Pré-requisitos: PostgreSQL instalado pelo instalador oficial do Windows (serviço na porta 5432) e a variável de usuário `GESTNOW_PG_ADMIN_URL` com a URL de administração do banco. O passo a passo está em [`docs/issues/spec-migracao-gestnow/PROMPT-EXECUCAO.md`](docs/issues/spec-migracao-gestnow/PROMPT-EXECUCAO.md), item 2.

Dê dois cliques em `run.bat`. Na primeira execução, ele cria `api/.venv`, instala as dependências da API, cria o papel `gestnow` e os bancos `gestnow` e `gestnow_teste`, grava a URL da aplicação em `api/local.settings.json` (fora do git), aplica as migrações e inicia `scripts/dev_local.py`. O app abre em `http://localhost:4280` e não depende do Azure Functions Core Tools. `/api/health` mostra o estado do banco e a revisão da migração.

Também é possível escolher outra porta pelo terminal:

```bat
run.bat 8080
```

O modo local simula uma sessão de demonstração e serve apenas para desenvolvimento. Ele não representa a configuração de produção no Azure. Nele, quem está logado é escolhido no **seletor de perfil** da barra lateral, que lista os colaboradores do cadastro; sem escolha, entra o primeiro Admin da demonstração. No Azure o acesso vem do login Microsoft e só entra quem está no cadastro de Colaboradores (`api/README.md`, seção "Acesso e permissões").

## Porta de qualidade

Instale as dependências de desenvolvimento do Python em `api/.venv` e as ferramentas de front na raiz. Com `uv` disponível:

```powershell
cd api
uv sync
cd ..
npm install
npm run verificar
```

As cinco etapas obrigatórias são `ruff check`, `ruff format --check`, `ty check`, ESLint e as verificações do padrão Timenow. Nenhuma regra deve ser desligada para fazer a porta passar.

Os testes rodam no banco `gestnow_teste`, recriado pelas migrações a cada execução; cada teste fica numa transação desfeita no fim:

```powershell
api\.venv\Scripts\python.exe -m pytest  # dentro de api/
```

## Varredura de telas

Com o app no ar, a varredura abre cada tela da lista de navegação em 1280, 1100 e 760 px, com os perfis Admin, Visualizador e Fornecedor, e reprova console com erro, rolagem horizontal, barra lateral ausente ou oculta, tela sem estilo próprio e link quebrado (ISSUE-090):

```powershell
npm run varredura
```

O Playwright e o navegador dele são dependências de desenvolvimento: `npm install` na raiz e `npx playwright install chromium` uma vez. A base padrão é `http://localhost:4280`, trocável por `--base` ou pela variável `GESTNOW_BASE`; `--perfis` e `--larguras` restringem a rodada (ex.: `npm run varredura -- --perfis admin --larguras 1280` para um fumaça). Sai com código 1 se houver qualquer reprovação e imprime a tabela-resumo no fim.

## Acessibilidade

Com o app no ar, a auditoria roda o axe-core 4.13.0 (regras `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa` e `best-practice`) em cada tela da lista de navegação, nas larguras 1280 e 760 px, com o perfil Admin em todas e o Fornecedor nas da Programação Semanal. Em 1280 px vem também a passada de teclado com Tab real: o skip link é a primeira parada e cada parada precisa de nome acessível e de anel de foco computado (ISSUE-091):

```powershell
npm run acessibilidade
```

A base segue a varredura (`--base` ou `GESTNOW_BASE`, padrão `http://localhost:4280`); `--telas` e `--perfil` restringem a rodada (ex.: `npm run acessibilidade -- --telas inicio/home,riscos/registro --perfil admin`). O relatório lista cada violação com regra, severidade e alvo; sai com código 1 se houver qualquer violação ou falha de teclado.

## Onde está o quê

| Procurando | Está em |
|---|---|
| Shell e carregamento do Design System | `app/index.html` |
| Início (visão do projeto e do Portfólio) | `app/_views/inicio/home.html` |
| Design System | `app/ds/` |
| Navegação e rota de saúde | `api/src/blueprints/` |
| Templates da navegação | `api/src/templates/nav/` |
| Servidor local sem Functions Core Tools | `scripts/dev_local.py` e `run.bat` |
| Preparo do banco local | `scripts/prepare_database.py` |
| Camada de banco e modelos | `api/src/core/database.py`, `api/src/core/models.py` e `api/migrations/` |
| Envio de notificações (simulado ou e-mail pelo Microsoft Graph) | `api/src/core/notification.py` e `api/src/core/graph_mail.py`; variáveis em `api/README.md` |
| Testes e banco de teste | `api/tests/conftest.py` |
| Padrões herdados e documentação | `docs/` |
| Especificação e execução das issues | `docs/SPEC-MIGRACAO-GESTNOW.md` e `docs/issues/` |
| Referências preservadas das fontes | `docs/referencia/` |
| Skills de agente | `.agents/skills/` e `.claude/skills/` |
| Mapa “quero mudar X, abro Y” | [docs/MAPA-DE-MODULOS.md](docs/MAPA-DE-MODULOS.md) |

O mapa detalhado está em [docs/ONDE-ESTA.md](docs/ONDE-ESTA.md). As referências em `docs/referencia/` preservam o necessário das pastas de origem, desativadas ao fim da migração (ISSUE-093).

## Regras do repositório

- Código Python em inglês; interface, rotas, HTML, CSS e JavaScript em português.
- O shell é o único ponto que carrega os arquivos do Design System.
- Fragmentos não carregam `<link>`, `<style>` ou `<script src>`.
- Sem valores visuais fixos fora dos tokens e sem recursos externos em `app/`.
- A navegação é servida pelo backend; permissão não é decidida pela tela.
- Toda alteração deve respeitar `docs/PADRAO-DE-CODIGO.md` e as skills em `.agents/skills/`.
