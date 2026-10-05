# Prompt de execução contínua: ISSUE-001 a ISSUE-093

Um prompt só executa a migração inteira, issue por issue, na ordem do
[`index.md`](./index.md), sem pedir licença para passar de uma para a outra. A
única pergunta da execução é a confirmação da exclusão das pastas de origem, no
último passo (decisão Q32).

**Padrão de velocidade (a partir de 05/10/2026):** as issues independentes
rodam em paralelo, cada uma num worktree git; a porta de qualidade e os testes
rodam só no fim de cada entrega e no fim geral, e não a cada issue; o subagente
lê um contexto enxuto (`scripts/execucao/contexto_da_issue.py`, o
[`GUIA-RAPIDO-DO-AGENTE.md`](./GUIA-RAPIDO-DO-AGENTE.md) e
`scripts/execucao/gerar_api_sheet.py`) e escreve a documentação mínima; o
briefing é o [`BRIEFING-DO-AGENTE.md`](./BRIEFING-DO-AGENTE.md). Critério que
depende de fonte indisponível vira pendência em
[`PENDENCIAS-DE-FONTE.md`](./PENDENCIAS-DE-FONTE.md).

---

## Antes de colar (uma vez, por você)

1. **Instale o PostgreSQL** pelo instalador oficial para Windows (versão 17, em
   postgresql.org). No instalador, defina a senha do usuário `postgres` só com
   letras e números (assim ela entra na URL sem conversão), mantenha a porta 5432
   e o serviço automático. O Stack Builder não é necessário.
2. **Crie a variável de administração do banco** como variável de usuário do
   Windows. Ela não fica dentro de uma pasta: vale em todas, inclusive no
   GestNow, e fica fora do OneDrive.
   * Tecla Windows, digite "variáveis de ambiente" e abra **Editar as variáveis
     de ambiente para sua conta**.
   * Em "Variáveis de usuário", clique em **Novo**. Nome:
     `GESTNOW_PG_ADMIN_URL`. Valor:
     `postgresql://postgres:SUA_SENHA@localhost:5432/postgres`, trocando
     `SUA_SENHA` pela senha do passo 1. **OK** e **OK**.
   * Alternativa no PowerShell, com aspas simples (com aspas duplas, um `$` na
     senha seria trocado por outro texto):

     ```powershell
     setx GESTNOW_PG_ADMIN_URL 'postgresql://postgres:SUA_SENHA@localhost:5432/postgres'
     ```

   * Se a senha tiver caracteres especiais, troque cada um na URL: `@` por
     `%40`, `:` por `%3A`, `/` por `%2F`, `%` por `%25`, `#` por `%23` e `?` por
     `%3F`.

   Não grave a senha em arquivo dentro da pasta do projeto: ela está no
   OneDrive, que sincroniza com a biblioteca compartilhada. A execução confere
   que a variável existe, mas nunca a imprime nem a grava em arquivo do projeto.
3. **Feche e reabra o Claude Code**, para a variável valer, e abra a sessão na
   pasta raiz **`Timenow - Gestao de Projetos`** (não dentro do GestNow): a
   execução lê as pastas de origem, que ficam ao lado.
4. **Permissões:** escolha o modo de permissão que aceita edições e comandos sem
   confirmar cada um. Em outro modo, a execução para a cada pedido de permissão.
5. **Deixe o computador ligado e sem suspensão.** São 93 issues: muitas horas de
   trabalho. Se algo interromper, cole o mesmo prompt de novo: a fila retoma de
   onde parou.

Já verificado nesta máquina (05/10/2026): Python 3.13, Node 22, git e SWA CLI
instalados. A execução precisa de internet para instalar pacotes (pip, npm) e o
navegador do Playwright (ISSUE-090).

---

## O prompt

Copie o bloco inteiro e cole como primeira mensagem de uma sessão nova.

````
Você vai executar, do começo ao fim e sem parar, a migração do protótipo Gestão Integrada AMT para o Timenow GestNow.

Pasta de trabalho: a raiz "Timenow - Gestao de Projetos". O produto fica em "Timenow - GestNow". As pastas "Sistema", "Padrao Desenvolvimento", "Graficos HTML" e "Timenow - Programação Semanal" são só fontes de leitura até a ISSUE-093. (Execução só com o GitHub: o repositório GestNow é a própria raiz do produto e essas pastas podem não existir; vale a regra E abaixo.)

Fontes, em ordem de autoridade:
1. Timenow - GestNow/docs/SPEC-MIGRACAO-GESTNOW.md. A spec vence qualquer outro documento.
2. Timenow - GestNow/docs/issues/spec-migracao-gestnow/index.md: registro, ordem, definição de pronto e decisões Q30 a Q35.
3. O arquivo de cada issue: o que construir, critérios de aceite, verificação e notas.
4. Timenow - GestNow/docs/issues/spec-migracao-gestnow/ENTREGAS.md: agrupamento e produto final.

REGRA DE OURO: NÃO PARE E NÃO PERGUNTE.
Não me peça confirmação para passar de uma issue para a outra, nem para nada dentro delas. A única pergunta permitida em toda a execução é a confirmação da exclusão das pastas de origem, no fim da ISSUE-093 (decisão Q32), por pop-up (AskUserQuestion). Fora dela, quando houver dúvida, decida pela spec; se a spec não cobrir, escolha a opção mais conservadora, siga e registre a decisão.

PASSO 0. PRÉ-VOO (uma vez)
Confira: serviço do PostgreSQL rodando; variável de ambiente GESTNOW_PG_ADMIN_URL definida (confira só que existe, nunca mostre o valor); Python 3.13 ou superior; Node 20 ou superior. Se faltar o Postgres ou a variável, pare antes da primeira issue e diga exatamente o que fazer: é a única parada permitida, e só antes de a fila começar. Se o repositório tiver remoto (GitHub), confira que o push da branch de trabalho funciona. Depois leia o index.md e o ENTREGAS.md; a spec você consulta por seção, pelo script de contexto (regra C).

COMO TRABALHAR (padrão de velocidade; vale para a execução inteira)
A. TESTES SÓ POR ENTREGA. A porta de qualidade (npm run verificar) e a suíte de testes NÃO rodam a cada issue. Rodam no fim de cada entrega e, uma última vez, no fim geral, com correção dos erros. Os subagentes escrevem o código e os testes da fatia, mas não os rodam (só ruff format e ruff check nos arquivos que mexeram). O orquestrador também não roda a porta de qualidade nem a suíte entre issues.
B. PARALELISMO COM WORKTREES. Rodam ao mesmo tempo, até 4 subagentes, as issues cujas bloqueadoras já estão "done" (as issues-raiz de módulo 019, 023, 029, 044, 045, 064 e 072 são independentes entre si e podem ir juntas). Cada subagente trabalha num worktree git próprio, criado do último commit: `git worktree add <pasta-fora-do-OneDrive>/ISSUE-NNN -b exec/ISSUE-NNN`. Ligue `api/.venv` e `node_modules` do worktree aos do checkout principal por link simbólico (ou junção no Windows) e acrescente `api/.venv` e `node_modules` ao `.git/info/exclude`, para o link não entrar no commit. Acrescente ao `.git/info/attributes` a linha `merge=union` para `docs/SPEC-MIGRACAO-GESTNOW.md` e `docs/DIVERGENCIAS-DO-PROTOTIPO.md` (arquivos só de acréscimo). Não espere a onda inteira: integre cada issue assim que o subagente terminar e lance as que ficaram prontas.
C. CONTEXTO ENXUTO. O subagente lê só `python scripts/execucao/contexto_da_issue.py NNN` (a issue, as decisões da spec que ela cita, as histórias e a definição de pronto), o docs/issues/spec-migracao-gestnow/GUIA-RAPIDO-DO-AGENTE.md e a saída de `python scripts/execucao/gerar_api_sheet.py`. Nunca a spec, o index.md nem o MODELO-DE-DADOS.md inteiros: para uma tabela, grep em docs/MODELO-DE-DADOS.md.
D. DOCUMENTAÇÃO MÍNIMA POR ISSUE. O subagente escreve só o Registro de execução (até 12 linhas), o LEIA-ME.md do módulo e, se o modelo mudou, o MODELO-DE-DADOS.md. As decisões vêm em linhas `DECISÃO: tema | decisão | D?, ISSUE-NNN`; o orquestrador as leva ao Histórico de decisões da spec ("Decisão da execução (ISSUE-NNN), pendente de revisão do dono") e consolida CONTEXT.md, MAPA-DE-MODULOS, ONDE-ESTA e COMPONENTES no fim de cada entrega.
E. PENDÊNCIAS DE FONTE. Critério de aceite que depende de fonte indisponível (carga a partir dos mocks, número do oráculo, código do app de Programação Semanal, dicionário en.js) fica "[ ]" com nota no Registro de execução e entra em docs/issues/spec-migracao-gestnow/PENDENCIAS-DE-FONTE.md; a issue fecha como "done" com essa pendência listada, para a fila não parar. A conciliação (converter os mocks, escrever o seed.py e as afirmações do oráculo, remover a linha) roda quando as fontes estiverem ao lado da raiz, antes da ISSUE-089. Issue cujo próprio código é a fonte ausente (Programação Semanal, 051 a 056, e o que depende delas) espera as pastas.

A FILA
Percorra as issues em ordem numérica, de ISSUE-001 a ISSUE-093, lançando em paralelo as que estiverem prontas (regra B). Para cada uma:
1. Pule as que estão "done" (retomada). Se uma estiver "in-progress" de uma execução anterior, ela foi interrompida: guarde as mudanças do worktree ou ramo exec/ISSUE-NNN num ramo "falha/ISSUE-NNN-<data>", volte ao último commit e recomece a issue.
2. Se algum item de blocked_by não estiver "done", a issue espera (ela só entra quando as bloqueadoras estiverem integradas). Se a bloqueadora ficou "blocked", marque esta como "blocked", acrescente no fim do arquivo dela a seção "## Registro de execução" com "Bloqueada porque ISSUE-XXX não fechou" e atualize o index.md.
3. Marque "status: in-progress" no arquivo da issue e na coluna Situação do index.md e faça um commit "Fila: ISSUE-... em andamento" ANTES de criar os worktrees (eles nascem desse commit).
4. Lance um subagente por issue (ferramenta Agent, tipo general-purpose, em segundo plano) com o texto de docs/issues/spec-migracao-gestnow/BRIEFING-DO-AGENTE.md, trocando NNN e informando a pasta do worktree, mais as dicas específicas da issue (que fontes faltam, que arquivos compartilhados ela toca, que issues rodam ao lado).
5. Ao receber o relatório: confira só que os critérios marcados [x] correspondem ao que existe (git diff --stat do worktree e uma olhada nos arquivos principais) e que o git status mostra só mudanças coerentes com a issue. Não rode a porta de qualidade nem a suíte (regra A).
6. Integre: no worktree, `git add -A` e `git commit -m "wip ISSUE-NNN"`; no checkout principal, `git cherry-pick -n exec/ISSUE-NNN`. Integre sempre na ordem das dependências. Resolva conflitos mantendo as duas partes (função de blueprint em function_app.py, links em app/index.html); migração Alembic duplicada se reencadeia ajustando o down_revision.
7. Integrou: "status: done" no arquivo e no index.md; commit no git do GestNow com a mensagem "ISSUE-NNN: <título da issue>", incluindo o arquivo da issue e o index.md; se houver remoto, envie a branch de trabalho (a main só a pedido do dono); remova o worktree e o ramo exec/ISSUE-NNN. Siga para a próxima.
8. Subagente que volta com critério não atendido (que não seja de fonte ausente): lance um subagente de correção no mesmo worktree com o briefing, o que falta e os critérios pendentes. No máximo 3 tentativas. Se ainda faltar: guarde as mudanças no ramo "falha/ISSUE-NNN-<data>", marque a issue "blocked", escreva no "## Registro de execução" a causa, o que foi tentado e o nome do ramo, faça o commit dessa anotação e siga. As que dependem dela ficam "blocked" pelo item 2; as outras seguem.

FIM DE ENTREGA (ao fechar a última issue de cada entrega: 004, 018, 028, 043, 056, 067, 078, 086 e 093)
1. Rode a porta de qualidade completa (npm run verificar) e a suíte de testes inteira contra o banco de teste, mais as verificações negativas e manuais que as issues da entrega pedem (por exemplo, a trio-da-tela reprovando um CSS, um JS, um vínculo e um item de navegação removidos um de cada vez), e uma abertura rápida das telas novas no navegador conferindo erro de console.
2. Corrija o que falhar com subagentes de correção, até 3 rodadas por grupo de falhas. Nunca desligue regra de lint, nunca pule nem apague teste para passar.
3. Com a entrega verde, marque "[x]" no critério "A porta de qualidade passa" das issues da entrega.
4. Consolide: leve as linhas `DECISÃO:` das issues da entrega ao Histórico de decisões da spec e atualize CONTEXT.md, MAPA-DE-MODULOS, ONDE-ESTA e COMPONENTES com o que a entrega trouxe.
5. Acrescente ao RELATORIO-DE-EXECUCAO.md, na pasta das issues, o que a entrega trouxe e o que ficou bloqueado ou pendente de fonte, atualize o PROGRESSO.md, faça o commit e siga direto para a próxima entrega.

ETAPA FINAL
Depois da ISSUE-093, rode de novo a porta de qualidade e a suíte inteira, o oráculo e a varredura de telas; corrija todos os erros que aparecerem; só então escreva o fechamento (ver FIM).

BRIEFING DO SUBAGENTE
O briefing é o arquivo docs/issues/spec-migracao-gestnow/BRIEFING-DO-AGENTE.md: envie o texto dele a cada subagente. Ele define a política de testes, o contexto enxuto, a documentação mínima, o formato das decisões e o relatório final de até 10 linhas.

REGRAS QUE VALEM O TEMPO TODO
- Nada do produto fora de "Timenow - GestNow". As pastas de origem só são lidas; nunca escreva nelas nem as apague antes da confirmação da ISSUE-093.
- Decisões já tomadas, que valem sem perguntar: Q30 (modelo de dados aceito para execução, revisão no fim), Q31 (divergências: reproduz o número do protótipo e registra em docs/DIVERGENCIAS-DO-PROTOTIPO.md como pendente de aceite), Q32 (só a exclusão final é perguntada), Q33 (git: um commit por issue; com o GitHub em uso, envie a branch de trabalho a cada issue integrada e atualize a main só a pedido do dono), Q34 (skills grill-me e grilling: fica a versão da raiz), Q35 (LGPD do HSE: Membro preenche, só Gestor e Admin leem).
- Nunca mostre nem grave em arquivo versionado senhas ou URLs com senha.
- Dependências novas só das fontes oficiais (pip, npm, o navegador do Playwright), registradas como o Padrão manda.
- Se o contexto for compactado, releia o index.md: ele é o estado da fila.

FIM
Depois da ISSUE-093, inclusive a resposta do pop-up e a etapa final, complete o RELATORIO-DE-EXECUCAO.md com: issues done e blocked (com a causa), pendências de fonte, divergências pendentes, decisões da execução pendentes de revisão do dono e o que o dono precisa fazer (revisar o modelo de dados, decidir as divergências, conciliar as pendências de fonte, seguir o roteiro manual de aceite, publicar no Azure). Então me mostre um resumo curto e o caminho do relatório.
````

---

## Como acompanhar

* **Situação de cada issue:** coluna Situação do [`index.md`](./index.md) e o
  campo `status` de cada arquivo (`proposed`, `in-progress`, `done`,
  `blocked`).
* **Pendências de fonte:** [`PENDENCIAS-DE-FONTE.md`](./PENDENCIAS-DE-FONTE.md),
  com o que ficou `[ ]` por falta das pastas de origem e como conciliar.
* **Histórico:** `git log` dentro de `Timenow - GestNow`, um commit por issue
  fechada.
* **Resumo por entrega:** `RELATORIO-DE-EXECUCAO.md`, nesta pasta, atualizado
  ao fim de cada entrega, e o `PROGRESSO.md` da raiz do produto.

## Se algo der errado

* **Interrupção** (queda de energia, janela fechada, limite de uso): cole o
  mesmo prompt numa sessão nova, na mesma pasta raiz. A fila pula o que está
  `done` e recomeça a issue que estava `in-progress` a partir do último commit
  (as mudanças parciais ficam num ramo `falha/...`).
* **Issue `blocked`:** leia o "Registro de execução" no fim do arquivo dela.
  Resolva a causa, volte o `status` dela e das que ficaram bloqueadas por ela
  para `proposed` e cole o prompt de novo.
* **Quer parar no meio:** interrompa a sessão a qualquer momento. Cada issue
  `done` já está commitada, e a retomada é pelo mesmo prompt.
