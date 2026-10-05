# Timenow GestNow

Aplicação de gestão integrada de projetos de capital, construída sobre o Padrão de Desenvolvimento Timenow.

**Azure Static Web Apps** · **Azure Functions V4 (Python)** · **Alpine.js + Alpine AJAX** · **Jinja2** · **Timenow Design System**

Sem bundler, sem etapa de build e sem CDN.

## Estado desta entrega

O repositório contém o shell inicial do GestNow, a navegação lateral do Padrão e a estrutura documentada dos 12 módulos. As telas de demonstração e suas rotas foram removidas; a tela de Início permanece vazia. Os stubs ainda não implementam regras nem persistência de negócio; o modelo de dados e o preparo do Postgres chegam nas ISSUE-003 a ISSUE-005.

## Rodar localmente

Dê dois cliques em `run.bat`. Na primeira execução, ele cria `api/.venv`, instala as dependências da API e inicia `scripts/dev_local.py`. O app abre em `http://localhost:4280` e não depende do Azure Functions Core Tools.

Também é possível escolher outra porta pelo terminal:

```bat
run.bat 8080
```

O modo local simula uma sessão de demonstração e serve apenas para desenvolvimento. Ele não representa a configuração de produção no Azure.

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

## Onde está o quê

| Procurando | Está em |
|---|---|
| Shell e carregamento do Design System | `app/index.html` |
| Tela inicial vazia | `app/_views/inicio/home.html` |
| Design System | `app/ds/` |
| Navegação e rota de saúde | `api/src/blueprints/` |
| Templates da navegação | `api/src/templates/nav/` |
| Servidor local sem Functions Core Tools | `scripts/dev_local.py` e `run.bat` |
| Padrões herdados e documentação | `docs/` |
| Especificação e execução das issues | `docs/SPEC-MIGRACAO-GESTNOW.md` e `docs/issues/` |
| Referências preservadas das fontes | `docs/referencia/` |
| Skills de agente | `.agents/skills/` e `.claude/skills/` |
| Mapa “quero mudar X, abro Y” | [docs/MAPA-DE-MODULOS.md](docs/MAPA-DE-MODULOS.md) |

O mapa detalhado está em [docs/ONDE-ESTA.md](docs/ONDE-ESTA.md). As referências em `docs/referencia/` são cópias de consulta; as pastas de origem não são alteradas por esta execução.

## Regras do repositório

- Código Python em inglês; interface, rotas, HTML, CSS e JavaScript em português.
- O shell é o único ponto que carrega os arquivos do Design System.
- Fragmentos não carregam `<link>`, `<style>` ou `<script src>`.
- Sem valores visuais fixos fora dos tokens e sem recursos externos em `app/`.
- A navegação é servida pelo backend; permissão não é decidida pela tela.
- Toda alteração deve respeitar `docs/PADRAO-DE-CODIGO.md` e as skills em `.agents/skills/`.
