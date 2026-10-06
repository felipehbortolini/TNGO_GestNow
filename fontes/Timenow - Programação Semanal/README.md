# Programação Semanal de Serviços

Aplicação da Timenow Engenharia para programar, reportar e acompanhar a
execução semanal das contratadas de uma obra.

**Azure Static Web Apps** · **Azure Functions V4 (Python)** · **Alpine.js + Alpine AJAX**
· **Jinja2** · **Timenow Design System**

Sem bundler. Sem etapa de build. Sem CDN.

---

## Rodar agora, em arquivos locais

**Dê dois cliques em `run.bat`**, na raiz do projeto. Ele cuida de tudo: cria
o ambiente Python se não existir, instala o que falta, descobre o IP da
máquina, tenta liberar a porta no firewall e sobe o servidor já publicado
para a rede.

```
 Neste computador:  http://localhost:4280
 Na rede local:     http://192.168.15.10:4280
```

O segundo endereço é o que se digita no **celular ou em outro PC**, desde que
estejam na mesma rede. Se de outro aparelho der "não foi possível conectar" e
no próprio PC funcionar, é o firewall: clique com o botão direito no
`run.bat` e escolha *Executar como administrador* — uma vez só, a regra fica
gravada.

Outra porta: `run 8080` no terminal.

O `run.bat` é para quem só quer ver o app rodando. Quem desenvolve tem o
`rodar.ps1`, que roda a porta de qualidade antes de subir e prefere o SWA CLI
quando ele está instalado:

```powershell
.\scripts\rodar.ps1
```

Abre em `http://localhost:4280`. Na primeira execução o app grava em `data/`
um registro de ambientes com **duas caixas de demonstração** — `demo-obra` e
`demo-planta` — cada uma com um histórico de seis semanas mais duas à frente,
ancorado na semana corrente: assim toda tela tem número e todo gráfico tem
forma antes de alguém digitar qualquer coisa, e a troca de ambiente pode ser
vista logo no primeiro clique. Apagar `data/` regenera tudo.

Sem provedor de identidade, o app entra em **modo demonstração**: depois da
entrada, o **seletor de ambientes** oferece as duas caixas, e a barra lateral
traz o trocador que muda de ambiente a qualquer momento — mais um seletor de
perfil, para conferir a tela como cada papel a vê. Os dois somem quando o
Azure passa a autenticar: o seletor de ambiente vira a escolha real do
cliente, e o perfil vem do cadastro.

Para liberar na rede local por esse caminho:

```powershell
.\scripts\rodar.ps1 -Rede
```

Se `swa` e `func` estiverem instalados, o script usa o SWA CLI — o caminho
mais próximo do Azure real. Se não, cai para `scripts/dev_local.py`, um
servidor Python equivalente que lê as rotas do próprio `function_app.py`.

Primeira vez na máquina:

```powershell
.\scripts\instalar.ps1
```

---

## O que o app faz

| Tela | Para quê |
|---|---|
| **Início** | O estado da semana: aderência, PPC, o que espera decisão e o que está travando |
| **Programação** | A matriz da semana — previsto e realizado por dia, com todas as ações do fluxo |
| **Dashboard** | Curva S do avanço físico, previsto × realizado, rankings, mapa de calor e gargalos |
| **Importar planilha** | Modelo, conferência linha a linha e confirmação — nada grava antes da conferência |
| **Governança** | Uma linha por contratada e semana, mais a trilha de auditoria |
| **Configurações** | Parâmetros, cadastros de apoio, janelas de programação e **Colaboradores** (restrito) |

O fluxo de uma atividade e quem move cada passo estão em
[CONTEXT.md](CONTEXT.md).

---

## Onde está o quê

| Procurando… | Está em | O que tem lá |
|---|---|---|
| **Design System** | **`app/ds/`** | `tokens.css`, `shell.css`, `patterns.css`, `charts.js`, `print.css`, `icons.js`, `ui.js`, `assets/` |
| **Páginas** | **`app/_views/`** | uma por tela, todas fragmentos de `#app-shell` |
| **Regras de negócio** | **`api/src/core/dados.py`** | a facade: toda transição do fluxo passa por aqui |
| **Contas do domínio** | `api/src/core/calculos.py` | PPC, aderência, faixas, quebras |
| **Semanas** | `api/src/core/semanas.py` | o único lugar que faz aritmética de calendário |
| **Janela de programação** | `api/src/core/janela.py` | quando cada contratada pode escrever |
| **Persistência** | `api/src/core/repositorio.py` | a porta; hoje JSON, amanhã SharePoint |
| **Gancho do SharePoint** | `api/src/integracoes/sharepoint.py` | mapa de listas e colunas, pronto e desligado |
| **Excel** | `api/src/core/planilha.py` | modelo, leitura validada e exportação de sete abas |
| **Gráficos** | `api/src/core/indicadores.py` + `app/ds/charts.js` | os números no servidor, o desenho no cliente |
| **Rotas da API** | `api/src/blueprints/` | um módulo por assunto |
| **Fragmentos do servidor** | `api/src/templates/` | HTML que a API devolve (Jinja2) |
| **Regras de qualidade** | `api/pyproject.toml`, `eslint.config.mjs` | ruff, ty e ESLint |
| **Skills de agente** | `.agents/skills/` | pasta oculta — comece por `padrao-de-codigo` |

> **Duas pegadinhas de nome**, herdadas do template Azure SWA:
> **`ds`** é *design system*; **`_views`** e **`_components`** começam com
> underscore porque o Azure SWA não serve essas pastas como rota direta.

Mapa completo em [ONDE-ESTA.md](docs/ONDE-ESTA.md).

---

## Onde os dados moram

Por padrão, um arquivo JSON por **ambiente** em `data/<identificador>/programacao.json`,
escrito de forma atômica (arquivo temporário e renomeação) porque o modo rede
coloca várias pessoas no mesmo arquivo. Na raiz de `data/` ficam o
`registro.json` — o cadastro global de ambientes — e a trilha dele. Cada
ambiente tem a própria trilha de auditoria, e nenhum dado cruza de um para o
outro.

Para publicar em listas do SharePoint, o gancho já está escrito:

```powershell
setx PROGRAMACAO_ORIGEM sharepoint
setx SHAREPOINT_SITE_ID "contoso.sharepoint.com,<guid>,<guid>"
setx SHAREPOINT_TENANT_ID "<guid>"
setx SHAREPOINT_CLIENT_ID "<guid>"
```

O mapa de listas e o nome de cada coluna estão em
`api/src/integracoes/sharepoint.py`. Falta só a aquisição de token, isolada
em dois métodos — enquanto ela não existir, a integração recusa a operação
com uma mensagem que diz exatamente o que configurar, em vez de falhar com
500 no meio da tela.

Outras variáveis:

| Variável | Padrão | Para quê |
|---|---|---|
| `PROGRAMACAO_ORIGEM` | `json` | `json` ou `sharepoint` |
| `PROGRAMACAO_MODO` | `demo` | `demo` entra sem SSO; qualquer outro valor exige o Azure |
| `PROGRAMACAO_DATA_DIR` | `data/` | move a pasta de dados |

---

## Antes de dar por pronto

```bash
node scripts/verificar.mjs
```

Cinco etapas obrigatórias — `ruff check`, `ruff format`, `ty check`, `eslint`
e o padrão Timenow. Ver [PADRAO-DE-CODIGO.md](docs/PADRAO-DE-CODIGO.md).

O `rodar.ps1` roda a porta antes de subir. Escape consciente:
`.\scripts\rodar.ps1 -SemVerificar`.

---

## Estrutura

```
run.bat             sobe o app para uso local e na rede (dois cliques)
CONTEXT.md          glossário do domínio — vocabulário do projeto
eslint.config.mjs   regras de JS, CSS e HTML
package.json        ferramentas de front (só desenvolvimento)

app/          front-end estático
  ds/         Design System — a única fonte visual
  _views/     páginas (fragmentos de #app-shell)
  _components/ fragmentos estáticos reutilizáveis
api/          Azure Functions V4 (Python ≥3.13)
  src/core/         domínio: dados, cálculos, semanas, janela, RBAC, planilha
  src/blueprints/   rotas, um módulo por assunto
  src/templates/    fragmentos Jinja2
  src/integracoes/  ganchos externos (SharePoint)
data/         base local em JSON (criada na primeira execução)
docs/         documentação
scripts/
  instalar.ps1        instala tudo e confere a porta de qualidade
  rodar.ps1           sobe o app — roda a porta antes; swa start com fallback
  verificar.mjs       PORTA DE QUALIDADE
  dev_local.py        servidor local; lê as rotas do próprio function_app.py
```

---

## Documentação

| Documento | Para quê |
|---|---|
| [COMO-USAR.md](docs/COMO-USAR.md) | **Para quem opera.** O ciclo da semana, tela a tela |
| [API-DE-LEITURA.md](docs/API-DE-LEITURA.md) | **Para o analista do cliente.** O contrato da API JSON, do token à primeira consulta |
| [CONTEXT.md](CONTEXT.md) | **Para quem desenvolve.** O que cada termo do domínio significa |
| [ONDE-ESTA.md](docs/ONDE-ESTA.md) | Mapa completo das pastas |
| [PADRAO-DE-CODIGO.md](docs/PADRAO-DE-CODIGO.md) | Fluxo obrigatório, ferramentas, porta de qualidade |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Como o sistema funciona, ponta a ponta |
| [CONTRATO-VISUAL.md](docs/CONTRATO-VISUAL.md) | Como o CSS chega em cada página |
| [DESIGN-SYSTEM.md](docs/DESIGN-SYSTEM.md) | Tokens, rampas, tipografia, espaçamento |
| [COMPONENTES.md](docs/COMPONENTES.md) | Inventário com markup copiável |
| [PADROES-DE-PAGINA.md](docs/PADROES-DE-PAGINA.md) | Anatomia de tela, estados, responsivo |
| [CONVENCOES.md](docs/CONVENCOES.md) | Nomenclatura, idioma, organização |
| [CHECKLIST-NOVA-PAGINA.md](docs/CHECKLIST-NOVA-PAGINA.md) | Aceite antes do PR |
| [ACESSIBILIDADE.md](docs/ACESSIBILIDADE.md) | Auditoria de contraste e pendências |
| [CLEAN-CODE.md](docs/CLEAN-CODE.md) | O que fazer e não fazer ao escrever |

---

## As regras

**Do fluxo de trabalho:**

1. **Entendeu o negócio antes de codar?** Na dúvida, `/grill-me`.
2. **`node scripts/verificar.mjs` passa** antes de qualquer PR.
3. **Nunca desligue uma regra para o gate passar.** Corrija o código; se for
   falso positivo estrutural, ajuste a configuração **com comentário
   explicando**.

**Do visual:**

4. **Só o shell carrega estilo.** Fragmento nunca traz `<link>` ou `<script src>`.
5. **Nenhum valor fixo de cor, espaçamento, raio ou sombra.** Tudo por token.
6. **Sem CDN.** Nada em `app/` aponta para host externo.
7. **A falta de estilo falha alto**, com mensagem — nunca em silêncio.

**Do domínio:**

8. **Autorização é decidida no servidor.** A interface esconde botão por
   conveniência; ela nunca decide acesso.
9. **Fornecedor só vê a própria empresa** — o recorte é aplicado na facade,
   não na tela.
10. **Total, PPC e aderência são calculados.** Nunca digitados.
