# Glossário do domínio

Vocabulário deste repositório. Termo usado em código, documentação e conversa
deve estar aqui — e significar exatamente isto.

Mantido pela skill `domain-modeling`: conceito novo entra no momento em que
aparece, não depois.

---

## O negócio

**Programação semanal** — o compromisso de uma contratada com uma semana:
quanto de cada atividade ela vai produzir, dia a dia, de segunda a domingo.
É o objeto central do aplicativo.

**Atividade** — uma linha da programação. Tem uma **ID exclusiva** que não
repete dentro da semana, uma frente, uma contratada, um encarregado, uma
unidade de medida e sete valores de previsto.

**Semana** — sempre escrita `S.30/2026`, em toda tela, arquivo e planilha.
Segue o calendário ISO: a semana 1 é a que contém a primeira quinta-feira do
ano, e ela abre na segunda. Quem sabe converter é `core/semanas.py`; nenhum
outro módulo faz aritmética de data.

**Previsto** — o que a programação diz que a semana entrega, distribuído
pelos sete dias. A soma dos dias tem de bater com a produção prevista da
semana, com tolerância de 0,5.

**Realizado** — o que foi produzido de fato, separado em **turno dia** e
**turno noite**. Quem reporta é a contratada.

**PPC** — *Percentual do Plano Concluído*. Realizado dividido por previsto,
de UMA atividade. É o indicador do Last Planner, e é por atividade.

**Aderência** — soma do realizado dividida pela soma do previsto de um
conjunto (a semana, uma contratada, uma frente). Diferente do PPC médio:
aderência pondera pelo tamanho, o PPC médio não.

**Faixa** — a leitura de um percentual em três níveis: **alta** (≥ 80%),
**média** (60 a 79%) e **baixa** (< 60%). Uma escala só, usada pela tabela,
pelos medidores, pelos gráficos e pela planilha exportada.

**Avanço físico** — o percentual de conclusão usado na curva S. As unidades
da obra não são somáveis entre si (kg de armação com m³ de solo), então o
avanço é medido por atividade, como fração do escopo dela no horizonte, com
peso igual entre atividades. Está escrito na legenda do gráfico.

---

## Multi-ambiente

**Ambiente** — a instância de dados de um cliente: sua programação, seus
cadastros, suas janelas, seus colaboradores e sua trilha de auditoria, sem
nenhum ponto de contato com os demais. Tem identificador imutável, nome de
projeto, nome de cliente e situação (ativo ou arquivado). É o termo escolhido
pelo negócio — quando a documentação falar do outro "ambiente" (desenvolvimento,
homologação, produção), diz **implantação**.

**Registro de ambientes** — o cadastro global, acima de todos os ambientes:
quais existem e quem pode entrar em cada um. É dono do nome do projeto e do
cliente (fonte única) e tem trilha própria. Vive em `core/registro.py`.

**Ambiente ativo** — o ambiente resolvido para a execução corrente (uma
requisição, um teste, um script). Vive em `core/ambiente.py`. Fora dele
nenhum código toca a base: falha fechada, nunca um ambiente padrão.

**Membro do ambiente** — e-mail com direito de entrar. Decide o que aparece
no seletor — não decide o perfil.

**Operador** — perfil global da Timenow que administra o registro de
ambientes. Vem da configuração da implantação (`PROGRAMACAO_OPERADORES`),
nunca do dado.

**Seletor de ambientes** — a primeira tela depois do SSO: uma caixa por
ambiente acessível.

---

## O fluxo

Cinco estados, sempre nesta ordem. Quem move cada passo está em
`core/rbac.py`; a regra de cada transição, em `core/dados.py`.

| Passo | Quem | O que muda |
|---|---|---|
| Criar / editar | Fornecedor, dentro da janela (Timenow, como apoio) | nasce **em elaboração** |
| Validar | Planejador | vira **validada** e ganha um fiscal |
| Anexar o realizado | Fornecedor | preenche o realizado, aprovação fica **pendente** |
| Aprovar o realizado | Fiscal | aprovação vira **aprovado**, e o realizado congela |
| Publicar | Planejador ou Admin | vira **publicada** e encerra a edição |

**Situação** é onde a programação está no fluxo — em elaboração, validada,
publicada. **Aprovação do realizado** é outra coisa: pendente ou aprovado.
Uma atividade publicada pode ter realizado pendente.

**Janela de programação** — quando uma CONTRATADA pode escrever. Três
camadas, nesta ordem: liberação extraordinária (vence tudo), semana liberada,
dia e horário. Fora disso a contratada consulta, mas não edita. Vive em
`core/janela.py`.

**Liberação extraordinária** — abertura pontual de uma semana por um período
absoluto. Vence a regra nos dois sentidos: dentro do intervalo abre mesmo no
dia errado; fora dele fecha mesmo que a semana estivesse liberada.

---

## Quem usa

**Perfil** — o que a pessoa pode fazer: `admin`, `planejador`, `fiscal`,
`fornecedor`, `visualizador`.

**Vínculo** — o que a pessoa enxerga: `timenow`, `fornecedor`, `cliente`.
Um usuário de vínculo `fornecedor` só vê a própria empresa, em toda tela,
sempre — o recorte é aplicado no servidor, em `dados._escopo`.

**Colaborador** — o registro de acesso de uma pessoa. **É a fonte de verdade
do login**: um e-mail que não está no cadastro não entra, com ou sem sessão
do Azure. Por isso a subaba Colaboradores é restrita ao Administrador.

---

## Estrutura da aplicação

**Shell** — `app/index.html`. O único documento HTML completo da aplicação.
Carrega o Design System, consulta a sessão, monta a sidebar e hospeda a área
de conteúdo. Nunca é substituído; só o conteúdo dentro dele troca.

**View** — arquivo em `app/_views/`. Uma página. É um **fragmento**, não um
documento: sua raiz é `<main id="app-shell" class="content">` e ela substitui
o conteúdo do shell inteiro.

**Componente** — arquivo em `app/_components/`. Pedaço reutilizável e
**estático** de HTML, carregado por uma view. Se precisar de dado do servidor,
não é componente — é fragmento de API.

**Fragmento** — pedaço de HTML que o servidor devolve para ser trocado no DOM.
Estende `base_fragment.html` e carrega `{{ target_id }}` na raiz. É a unidade
de resposta da API: aqui o servidor devolve HTML pronto, nunca JSON.

**Partial** — template Jinja2 sem raiz nem id próprios, existente só para ser
incluído por outro (`{% include %}`). Nunca é alvo de `x-target`. Ex.:
`programacao/_linha.html`.

**Alvo** (*target*) — o elemento do DOM que receberá um fragmento, declarado
pelo cliente em `x-target`. **Quem manda no destino é o cliente**, nunca o
servidor. Alvo declarado que não venha na resposta é **esvaziado** pelo
Alpine AJAX — daí a existência do `programacao/multi.html`.

**Resposta multi-alvo** — resposta que traz vários fragmentos irmãos de uma
vez, cada um com seu id fixo. É a única exceção à regra de não fixar id no
servidor. Aqui ela devolve sempre o mesmo trio: `#drawer`, `#prog-resumo` e
`#prog-tabela`.

**Painel** (*drawer*) — o formulário que desliza pela direita, dentro de
`#drawer`. **Vazio significa fechado**: é assim que ele some ao salvar, e é
por isso que `#drawer` entra no `x-target` de todo formulário.

**Matriz** — a tabela da programação. Sete colunas, e os sete dias vivem numa
delas como grade. A linha inteira cabe na tela: só há rolagem vertical.

**Grade de dias** — dentro da célula dos dias, duas linhas rotuladas `Prev` e
`Real` sobre oito colunas: o rótulo mais os sete dias. Cabeçalho e corpo usam
a mesma grade, com a coluna do rótulo em largura fixa — é o que mantém "4ª"
em cima da coluna de quarta. Os dois números têm o mesmo corpo de fonte, de
propósito: a comparação depende de os dígitos caírem alinhados na vertical.

**Gráfico com drill** — os três gráficos do dashboard que agrupam por mês e
abrem em semanas ao clique, com botões de ano. O motor é um só, em
`ds/charts.js`; cada gráfico entra com um **adaptador** que diz como resumir
um mês. Resumir não é sempre somar: barras de avanço somam, aderência divide
a soma do realizado pela soma do previsto do período. Por isso o servidor
manda **quantidade** e não percentual pronto.

---

## Camada visual

**Design System** (DS) — `app/ds/`. A única fonte visual da aplicação:

- **tokens.css** — variáveis, componentes atômicos (`.btn`, `.card`, `.pill`)
  e todas as animações do kit
- **shell.css** — estrutura de tela (`.sidebar`, `.page`, `.guard`)
- **patterns.css** — composições (`.kpis`, `.matriz`, `.painel`, `.lancamento`)
- **charts.js** — os quatro gráficos SVG (`curva-s`, `barras`, `linhas`, `rosca`)
- **print.css** — o relatório em papel

Nenhuma classe é declarada em dois dos três CSS. Isso é verificado, não
confiado — inclusive `from` e `to`, que o verificador enxerga como seletores
e por isso obrigam as animações a morarem todas em `tokens.css`.

**Token** — variável CSS que carrega uma decisão de design (`--brand-primary`,
`--space-lg`). **Valor de cor, espaçamento, raio ou sombra nunca é escrito
direto no código** — sempre por token. O `charts.js` lê os tokens do `:root`
em tempo de execução, pelo mesmo motivo.

**Contrato visual** — as cinco regras que garantem que toda página nasça
estilizada. Em `docs/CONTRATO-VISUAL.md`. A mais importante: só o shell
carrega estilo; fragmento nunca traz `<link>` nem `<script src>`.

**Sentinela** — a variável `--ds-carregado`, conferida pelo shell no boot. Se
o Design System não carregar, o app falha com mensagem visível em vez de
servir uma tela sem estilo.

---

## Backend

**Blueprint** — módulo em `api/src/blueprints/` que agrupa rotas relacionadas
(`func.Blueprint`). Registrado em `function_app.py`.

**Gate de fragmento** — a checagem `is_alpine_request(req)` no início de todo
endpoint de fragmento. Quem chega sem o cabeçalho do Alpine AJAX — navegador
digitando a URL, cURL — é redirecionado para o shell. As duas exceções são os
downloads (`exportar-semana`, `modelo-planilha`): o navegador pede um arquivo
sem o cabeçalho, e barrá-los devolveria o shell no lugar da planilha.

**`com_usuario`** — o decorador de `blueprints/_comum.py` que faz as três
coisas que todo endpoint repete: gate, resolução do usuário e checagem de
permissão. Se o handler roda, o chamador existe e pode.

**Porta de persistência** — `core/repositorio.py`. A única costura entre o
domínio e onde ele mora. Hoje `RepositorioJson`; amanhã, SharePoint. Trocar é
a variável `PROGRAMACAO_ORIGEM`.

**`RecusadoError` / `InvalidoError`** — as duas únicas exceções que cruzam a
linha do domínio, e viram 403 e 422. Elas carregam a mensagem que a pessoa lê
na tela: são o canal, não só o sinal.

**Toast por cabeçalho** — mensagem ao usuário viaja em `X-TN-Toast` na
resposta; `ds/ui.js` a converte em toast. A página não precisa saber que isso
aconteceu.

**Modo demonstração** — `PROGRAMACAO_MODO=demo` (o padrão fora do Azure). Sem
provedor de identidade, o app entra pelo cadastro de colaboradores e oferece
um seletor de perfil na barra lateral. Desliga sozinho quando existe um
principal do Azure SWA na requisição.

---

## Qualidade

**Porta de qualidade** — `scripts/verificar.mjs`. Cinco etapas obrigatórias
antes de qualquer commit. É o mecanismo real de imposição do padrão; a
documentação apenas explica.

**Falso positivo estrutural** — quando uma regra de linter acusa algo que é
correto pela arquitetura do projeto. Resolve-se na configuração **com
comentário explicando**, nunca com supressão solta. Os casos vivos: `ARG001`
nos blueprints (o Azure Functions exige `req` na assinatura), `TRY003` no
Python (as exceções de domínio SÃO a mensagem) e `allowUnknownVariables` no
CSS (os tokens moram em outro arquivo).

---

## Termos que NÃO usamos

| Não use | Use | Por quê |
|---|---|---|
| `CAA_*` | `TN` | Sigla de um app específico num kit que serve a todos |
| "componente" para fragmento de API | fragmento | Componente é estático, fragmento vem do servidor |
| "usuário" para o cadastro de acesso | colaborador | É o termo da tela e do registro |
| "aderência" para uma atividade só | PPC | Aderência é de conjunto; PPC é de atividade |
| `.ata-row`, `.ma-toolbar` | `.linha`, `.toolbar` | Nome de domínio de um app dentro do Design System |
| "topbar", "navbar" | sidebar | O shell padrão é a barra lateral de 300px |
| Tailwind, DaisyUI | Design System | Removidos pela decisão D1 |
| "ambiente" para dev, homolog e produção | implantação | Ambiente é a instância de dados de um cliente — o outro conceito fica com outro nome |
