# Prompt de execução contínua: ISSUE-001 a ISSUE-093

Um prompt só executa a migração inteira, issue por issue, na ordem do
[`index.md`](./index.md), sem pedir licença para passar de uma para a outra. A
única pergunta da execução é a confirmação da exclusão das pastas de origem, no
último passo (decisão Q32).

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

Pasta de trabalho: a raiz "Timenow - Gestao de Projetos". O produto fica em "Timenow - GestNow". As pastas "Sistema", "Padrao Desenvolvimento", "Graficos HTML" e "Timenow - Programação Semanal" são só fontes de leitura até a ISSUE-093.

Fontes, em ordem de autoridade:
1. Timenow - GestNow/docs/SPEC-MIGRACAO-GESTNOW.md. A spec vence qualquer outro documento.
2. Timenow - GestNow/docs/issues/spec-migracao-gestnow/index.md: registro, ordem, definição de pronto e decisões Q30 a Q35.
3. O arquivo de cada issue: o que construir, critérios de aceite, verificação e notas.
4. Timenow - GestNow/docs/issues/spec-migracao-gestnow/ENTREGAS.md: agrupamento e produto final.

REGRA DE OURO: NÃO PARE E NÃO PERGUNTE.
Não me peça confirmação para passar de uma issue para a outra, nem para nada dentro delas. A única pergunta permitida em toda a execução é a confirmação da exclusão das pastas de origem, no fim da ISSUE-093 (decisão Q32), por pop-up (AskUserQuestion). Fora dela, quando houver dúvida, decida pela spec; se a spec não cobrir, escolha a opção mais conservadora, siga e registre a decisão (ver o briefing).

PASSO 0. PRÉ-VOO (uma vez)
Confira: serviço do PostgreSQL rodando; variável de ambiente GESTNOW_PG_ADMIN_URL definida (confira só que existe, nunca mostre o valor); Python 3.13 ou superior; Node 20 ou superior. Se faltar o Postgres ou a variável, pare antes da primeira issue e diga exatamente o que fazer: é a única parada permitida, e só antes de a fila começar. Depois leia a spec inteira, o index.md e o ENTREGAS.md.

A FILA
Percorra as issues em ordem numérica, de ISSUE-001 a ISSUE-093. Para cada uma:
1. Pule as que estão "done" (retomada). Se uma estiver "in-progress" de uma execução anterior, ela foi interrompida: guarde as mudanças não commitadas num ramo "falha/ISSUE-NNN-<data>", volte ao último commit e recomece a issue. Antes da ISSUE-001 não há git; nesse caso, só recomece.
2. Se algum item de blocked_by não estiver "done", marque a issue como "blocked", acrescente no fim do arquivo dela a seção "## Registro de execução" com "Bloqueada porque ISSUE-XXX não fechou", atualize o index.md e siga para a próxima, sem executar.
3. Marque "status: in-progress" no arquivo da issue e na coluna Situação do index.md.
4. Lance UM subagente (ferramenta Agent, tipo general-purpose, em primeiro plano: run_in_background false) com o BRIEFING abaixo, trocando NNN pelo número da issue. Espere o resultado.
5. Confira você mesmo, sem confiar só no relatório do subagente:
   a. todos os critérios de aceite do arquivo estão marcados [x] e correspondem ao que existe no código;
   b. rode a "Verificação" da issue e a porta de qualidade dentro de "Timenow - GestNow" (npm run verificar) e leia a saída;
   c. o git status mostra só mudanças coerentes com a issue.
6. Passou: "status: done" no arquivo e no index.md; commit no git do GestNow (git -C "Timenow - GestNow" add -A e commit) com a mensagem "ISSUE-NNN: <título da issue>", incluindo o arquivo da issue e o index.md; siga para a próxima.
7. Falhou: lance um novo subagente de correção com o mesmo briefing, mais a saída da falha e os critérios pendentes. No máximo 3 tentativas por issue. Se ainda falhar: guarde as mudanças no ramo "falha/ISSUE-NNN-<data>", volte o ramo principal ao último commit verde, marque a issue "blocked", escreva no "## Registro de execução" a causa, o que foi tentado e o nome do ramo, faça o commit dessa anotação e siga. As issues que dependem dela ficam "blocked" pelo item 2; as outras seguem normalmente.

Ao fechar a última issue de cada entrega (004, 018, 028, 043, 056, 067, 078, 086 e 093), acrescente ao RELATORIO-DE-EXECUCAO.md, na pasta das issues, o que a entrega trouxe e o que ficou bloqueado, e siga direto para a próxima entrega.

BRIEFING DO SUBAGENTE (envie este texto, trocando NNN)
---
Você vai implementar a ISSUE-NNN do Timenow GestNow, sozinho, sem perguntar nada a ninguém.
- Pasta de trabalho: a raiz "Timenow - Gestao de Projetos"; o produto fica em "Timenow - GestNow".
- Leia: o arquivo "Timenow - GestNow/docs/issues/spec-migracao-gestnow/NNN-*.md"; na spec (Timenow - GestNow/docs/SPEC-MIGRACAO-GESTNOW.md), as decisões de spec_decisions e as histórias de source_requirements; a "Definição de pronto" e as "Decisões que valem para a execução" do index.md; o CONTEXT.md, o docs/MAPA-DE-MODULOS.md e o LEIA-ME.md do módulo (quando já existirem); e as fontes citadas em "Notas": protótipo em "Sistema", app em "Timenow - Programação Semanal", visuais em "Graficos HTML" (ou docs/referencia/graficos), Padrão em "Padrao Desenvolvimento".
- Antes de mexer em tela ou em código, leia as skills timenow-design-system, alpine-ajax e padrao-de-codigo em "Timenow - GestNow/.agents/skills/" (na ISSUE-001, em "Padrao Desenvolvimento/.agents/skills/").
- Implemente exatamente o que está em "O que construir", como fatia vertical completa: banco, fachada, rota, tela, exportação e testes, o que couber na issue. Nada além. O que está em Out of Scope na spec continua fora.
- Marque cada critério de aceite como [x] só quando ele for verdade. Rode a "Verificação" e o npm run verificar dentro de "Timenow - GestNow" até passarem. Nunca desligue regra de lint, nunca pule nem apague teste para passar.
- Não altere o index.md, não mude o status da issue e não faça commit: isso é do orquestrador.
- Nunca escreva nas pastas de origem. Nunca mostre nem grave em arquivo versionado senhas ou URLs com senha.
- Se precisar decidir algo que a spec não cobre, escolha o mais conservador, siga, e anote em dois lugares: no fim do arquivo da issue, em "## Registro de execução", e na spec, no Histórico de decisões, como "Decisão da execução (ISSUE-NNN), pendente de revisão do dono".
- Divergência com o protótipo (decisão Q31): se for erro de fórmula do protótipo, reproduza o número do protótipo; se for consequência de decisão já tomada na spec, siga a spec. Nos dois casos, registre em Timenow - GestNow/docs/DIVERGENCIAS-DO-PROTOTIPO.md: regra, número do protótipo, número correto, motivo e situação "pendente de aceite".
- Ao terminar, responda em até 15 linhas: o que foi feito, arquivos principais, resultado da verificação e da porta de qualidade, critérios não atendidos (se houver) e decisões tomadas.
---

REGRAS QUE VALEM O TEMPO TODO
- Nada do produto fora de "Timenow - GestNow". As pastas de origem só são lidas; nunca escreva nelas nem as apague antes da confirmação da ISSUE-093.
- Decisões já tomadas, que valem sem perguntar: Q30 (modelo de dados aceito para execução, revisão no fim), Q31 (divergências), Q32 (só a exclusão final é perguntada), Q33 (git local, um commit por issue, sem remoto e sem push), Q34 (skills grill-me e grilling: fica a versão da raiz), Q35 (LGPD do HSE: Membro preenche, só Gestor e Admin leem).
- Dependências novas só das fontes oficiais (pip, npm, o navegador do Playwright), registradas como o Padrão manda.
- Se o contexto for compactado, releia o index.md: ele é o estado da fila.

FIM
Depois da ISSUE-093, inclusive a resposta do pop-up, complete o RELATORIO-DE-EXECUCAO.md com: issues done e blocked (com a causa), divergências pendentes, decisões da execução pendentes de revisão e o que o dono precisa fazer (revisar o modelo de dados, decidir as divergências, seguir o roteiro manual de aceite, publicar no Azure). Então me mostre um resumo curto e o caminho do relatório.
````

---

## Como acompanhar

* **Situação de cada issue:** coluna Situação do [`index.md`](./index.md) e o
  campo `status` de cada arquivo (`proposed`, `in-progress`, `done`,
  `blocked`).
* **Histórico:** `git log` dentro de `Timenow - GestNow`, um commit por issue
  fechada.
* **Resumo por entrega:** `RELATORIO-DE-EXECUCAO.md`, nesta pasta, atualizado
  ao fim de cada entrega.

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
