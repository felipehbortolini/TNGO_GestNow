# Plano de execução — Multi-ambiente

> Quebra de [SPEC-MULTI-AMBIENTE.md](SPEC-MULTI-AMBIENTE.md) em entregas e
> tarefas executáveis. A spec diz **o que** e **por quê**; este documento diz
> **em que ordem** e **quando cada pedaço está pronto**.
>
> Toda decisão citada por número (`decisão 7`, `história 23`) refere-se à spec.
> Se este plano e a spec discordarem, a spec vence e o plano é que está velho.

---

## Estado de partida

Sete fatos do código de hoje que dimensionam o trabalho. Foram apurados antes
de escrever as tarefas e explicam por que algumas são de uma linha e outras de
um dia.

| Fato | Onde | Consequência |
|---|---|---|
| `repositorio.obter()` é chamado de **um único lugar** | `dados.py:59`, em `_repo()` | A troca para `ContextVar` tem raio de explosão mínimo na facade |
| `diretorio_de_dados()` é chamado de **dois lugares** | `repositorio.py:139`, `auditoria.py:40` | O layout por pasta toca exatamente esses dois |
| `carga_inicial.gerar()` é chamado de **um lugar** | `repositorio.py:164`, em `_semear()` | Restringir a semeadura ao modo demonstração é uma condição, não um refatoramento |
| `projeto`/`cliente` aparecem em **7 arquivos** | `repositorio.py:39-40`, `carga_inicial.py:412-413`, `configuracoes.py:125-126`, `nav.py:65`, `dashboard.py:108`, `exportacao.py:96-97`, `configuracoes/geral.html:31,36` | Tirar o campo dos parâmetros é uma varredura curta, mas passa por template e por exportação |
| `janela` é registro **por empresa**, com `semanas_liberadas` | `repositorio.py:gravar_janela`, `janela.py` | É por isso que janela saiu da clonagem (decisão 12) |
| **Nenhum teste toca a persistência** | `tests/test_dominio.py` importa só `calculos`, `indicadores`, `janela`, `rbac`, `semanas` | O teste de isolamento **estreia** a infraestrutura de teste com disco. A spec diz que o ponto de troca "já é usado pelos testes" — `definir()` existe, mas ninguém o chama. Tarefa própria, não linha de outra |
| A aplicação **nunca rodou com SSO real** | Nada publicado | E1.17 não é deploy de rotina: é a primeira vez que `x-ms-client-principal` chega |

---

## Como ler uma tarefa

```
### E1.3 — Título
**Depende de:** E1.2
**Toca:** arquivo, arquivo
**Faz:** o que muda, em prosa
**Pronto quando:** o que precisa ser verdade para a tarefa acabar
```

**Pronto quando** é critério observável, não "implementado". Se não dá para
conferir, não é critério.

Toda tarefa termina com a porta de qualidade das cinco etapas passando —
isso não se repete em cada uma.

---

# Entrega 1 — Isolamento

**Objetivo:** dois clientes na mesma instalação sem se enxergarem, com o
ambiente resolvido por requisição.

**Aceite da entrega:** os testes de isolamento por agregado passam, e duas
pessoas em dois ambientes não se encontram em nenhuma tela.

**Não entra:** tela de administração do registro (Entrega 2), API e tokens
(Entrega 3).

---

## Bloco A — Fundação (sem tela)

### E1.1 — Módulo `ambiente` com `ContextVar` e gerenciador de contexto
**Depende de:** —
**Toca:** `api/src/core/ambiente.py` *(novo)*
**Faz:** cria o módulo que define o `ContextVar` do ambiente ativo e o
gerenciador `ambiente_ativo(slug)`, que seta na entrada e faz `reset()` na
saída, inclusive com exceção. Expõe também `slug_ativo()`, que **levanta** se
não houver ambiente — nunca devolve padrão, nunca adivinha (decisão 7).

O módulo não importa nada de `core`, de propósito: `repositorio` e `auditoria`
vão importar dele, e o caminho inverso criaria ciclo.

**Pronto quando:** `with ambiente_ativo("a"):` aninhado dentro de
`with ambiente_ativo("b"):` devolve `"b"` dentro e `"a"` depois; `slug_ativo()`
fora de qualquer `with` levanta; e uma exceção dentro do bloco não deixa o
`ContextVar` sujo.

### E1.2 — Porta `RegistroAmbientes` e implementação JSON
**Depende de:** —
**Toca:** `api/src/core/registro.py` *(novo)*, `data/registro.json` *(gerado)*
**Faz:** a segunda porta, irmã de `Repositorio` e não parte dela (decisão 14).
Interface estreita: listar ambientes de um e-mail, obter um ambiente, criar,
arquivar, desarquivar, conceder acesso, revogar acesso, listar membros. Os
métodos de token ficam para a Entrega 3 e a interface já reserva o lugar.

Implementação `RegistroJson`: mesma escrita atômica (temporário + renomeação) e
mesma trava `RLock` de `RepositorioJson`. O identificador é validado contra
`^[a-z0-9-]{2,32}$` na criação e é imutável depois (decisão 3).

**Pronto quando:** criar e arquivar funcionam; listar por e-mail devolve só os
**ativos** onde a pessoa é membro; e-mail sem pertencimento devolve lista
vazia; slug fora do formato é recusado; slug repetido é recusado, inclusive
contra um ambiente arquivado.

### E1.3 — Layout por ambiente na porta de persistência e na trilha
**Depende de:** E1.1
**Toca:** `api/src/core/repositorio.py`, `api/src/core/auditoria.py`
**Faz:** `RepositorioJson` passa a resolver `data/<slug>/programacao.json` e
`auditoria._arquivo()` passa a resolver `data/<slug>/auditoria.jsonl`, os dois
lendo o slug de `ambiente.slug_ativo()`. Os dois **falham fechados** quando não
há ambiente (decisões 7 e 10).

A trilha continua fora da porta e continua `open(..., "a")` engolindo `OSError`
— o mecanismo barato não muda, só a resolução do caminho (decisão 10).

**Pronto quando:** escrever dentro de `ambiente_ativo("a")` cria
`data/a/programacao.json` e não toca `data/b/`; `auditoria.registrar` fora de
qualquer ambiente levanta em vez de escrever na raiz.

### E1.4 — Cache de portas por slug
**Depende de:** E1.3
**Toca:** `api/src/core/repositorio.py`
**Faz:** substitui o singleton `_ativo` por um `dict` de slug para instância,
criado sob trava própria com dupla checagem, **sem expiração e sem limite**
(decisão 8). `obter()` lê o slug do contexto e devolve a instância daquele
ambiente. `definir()` ganha a chave de ambiente e continua sendo a costura de
teste.

Comentário no código explicando que o cache existe **pela trava** e não pelo
objeto — e que por isso não pode ter descarte. Sem essa linha, alguém
"otimiza" isso em seis meses.

**Pronto quando:** duas chamadas de `obter()` dentro do mesmo ambiente devolvem
a **mesma** instância; dentro de ambientes diferentes devolvem instâncias
diferentes; `definir("a", falsa)` afeta só o ambiente `a`.

### E1.5 — Operadores por variável de ambiente e `Usuario` sintético
**Depende de:** E1.2
**Toca:** `api/src/core/auth.py`, `api/src/core/rbac.py`
**Faz:** lê `PROGRAMACAO_OPERADORES` (e-mails separados por `;`) e acrescenta
as permissões globais de operador em `rbac`. `auth` ganha `eh_operador(email)`
e a resolução de usuário passa a montar um `Usuario` sintético quando o e-mail
é de operador e **não** consta no cadastro daquele ambiente: perfil `admin`,
vínculo `timenow`. Se constar, **vale o cadastro** (decisão 11).

Nenhuma tela promove operador; não existe regra de "último operador".

**Pronto quando:** um e-mail da variável entra num ambiente onde não é
colaborador, como `admin`; entra com o perfil do cadastro quando o cadastro
existe; um e-mail fora da variável e fora do cadastro continua não entrando.

---

## Bloco B — Costura HTTP

### E1.6 — Decorador `com_sessao`
**Depende de:** E1.2, E1.5
**Toca:** `api/src/blueprints/_comum.py`
**Faz:** o decorador irmão que resolve **só** a identidade do SSO — o e-mail do
`x-ms-client-principal` — e consulta o registro. Não toca cadastro de
colaboradores e não exige ambiente (decisão 6). Mantém o gate de fragmento e a
tela de guarda, que é o motivo de ele morar aqui e não ser código solto no
blueprint do seletor.

**Pronto quando:** um endpoint decorado com `com_sessao` responde sem nenhum
ambiente ativo e sem nenhum cadastro de colaboradores existir.

### E1.7 — `com_usuario` ganha o passo do ambiente
**Depende de:** E1.1, E1.2, E1.4
**Toca:** `api/src/blueprints/_comum.py`
**Faz:** insere o quarto passo, **antes** da resolução do usuário — a ordem
importa e está explicada na spec. Lê o cookie, confere contra o registro
(existe, está ativo, o e-mail é membro **ou** é operador) e abre o
`ambiente_ativo` em torno do handler, garantindo o `reset()` no fim.

Confere também o **cabeçalho** contra o cookie: divergência é recusa, com a
mensagem "esta aba está em outro ambiente" (decisão 5). Nos dois downloads e no
relatório, que não têm cabeçalho do Alpine, a conferência é contra a query.

Atributos do cookie: `HttpOnly`, `SameSite=Lax`, `Secure` fora do modo local,
caminho raiz, **sem `Max-Age`**.

**Pronto quando:** os cinco casos de recusa recusam — cookie ausente, ambiente
inexistente, ambiente arquivado, e-mail não membro, cabeçalho divergente — e
cookie válido resolve. Nenhum handler roda com ambiente meio resolvido.

### E1.8 — Recusa por redirecionamento e guarda que nomeia a causa
**Depende de:** E1.7
**Toca:** `api/src/blueprints/_comum.py`, `api/src/templates/comum/recusado.html`
**Faz:** recusa **de ambiente**, e só ela, responde com o redirecionamento que
o gate de fragmento já usa, em vez de fragmento no alvo do chamador (decisão 9).
As demais recusas continuam como estão.

E a guarda passa a nomear o e-mail recebido e qual das quatro barreiras recusou
(decisão 19): nenhum e-mail na sessão, e-mail fora do registro, e-mail fora do
cadastro daquele ambiente, ambiente arquivado.

**Pronto quando:** uma recusa de ambiente disparada de dentro do `#drawer`
recarrega o shell e mostra o seletor, em vez de desenhar a guarda dentro do
painel; e cada uma das quatro causas produz uma mensagem diferente.

---

## Bloco C — Tela

### E1.9 — Blueprint e view do seletor
**Depende de:** E1.6
**Toca:** `api/src/blueprints/ambientes.py` *(novo)*,
`api/src/templates/ambientes/seletor.html` *(novo)*,
`app/_views/ambientes.html` *(novo)*, `api/function_app.py`
**Faz:** o fragmento do seletor — uma caixa por ambiente com nome de projeto e
cliente — mais o endpoint que grava o cookie da escolha. Sem ambiente algum,
serve a tela que explica e diz a quem pedir liberação (história 5).

Segue o padrão da aplicação: fragmento estendendo `base_fragment.html`, sem
`<link>` e sem `<script src>`, nenhuma classe visual nova fora do Design System.

**Pronto quando:** as caixas aparecem, escolher grava o cookie, e quem não é
membro de nada vê a tela explicativa em vez de uma lista vazia.

### E1.10 — Boot do shell com o seletor, e a escolha recarregando
**Depende de:** E1.9
**Toca:** `app/index.html`
**Faz:** insere o passo 3 do boot (decisão 16). Com um único ambiente, segue
direto; com vários, aguarda; com nenhum, mostra a tela que explica.

A escolha grava o cookie e **recarrega, com destino explícito**: a primeira
escolha recarrega a URL atual — o `location.pathname` nunca mudou, porque o
seletor é fragmento dentro do `#app-shell` — e a troca navega para `/`. É o que
concilia a história 12 (link direto preservado) com a história 8 (troca volta
para a home).

Também adiciona o cabeçalho do ambiente em toda requisição do Alpine AJAX, que
é a outra metade da decisão 5.

**Pronto quando:** abrir `/programacao` sem ambiente escolhido leva ao seletor e,
depois da escolha, a `/programacao`; trocar de ambiente leva à home do ambiente
novo; e a sidebar se remonta sozinha nos dois casos.

### E1.11 — Sidebar mostra o ambiente ativo e oferece a troca
**Depende de:** E1.10
**Toca:** `api/src/blueprints/nav.py`, `api/src/templates/nav/sidebar.html`
**Faz:** o nome do projeto passa a vir do **registro**, pelo ambiente ativo, e
não de `dados.parametros()` (decisões 4 e 18). Quem tem mais de um ambiente
ganha ali o caminho para trocar; quem tem um só não recebe o controle — o item
some do DOM, como já acontece com todo item que o perfil não abre.

**Pronto quando:** a faixa mostra o ambiente certo; trocar de ambiente muda a
faixa; e o controle de troca não existe no DOM de quem tem um ambiente só.

### E1.12 — `projeto` e `cliente` saem dos parâmetros
**Depende de:** E1.11
**Toca:** `api/src/core/repositorio.py` (`PARAMETROS_PADRAO`),
`api/src/core/carga_inicial.py`, `api/src/blueprints/configuracoes.py`,
`api/src/blueprints/dashboard.py`, `api/src/blueprints/exportacao.py`,
`api/src/templates/configuracoes/geral.html`
**Faz:** remove os dois campos dos parâmetros e aponta os cinco leitores para o
registro (decisão 4). A tela de Configurações passa a **exibir** o nome em
leitura, para a pessoa saber de qual ambiente ela fala (história 44), e perde os
dois campos de entrada.

Isto também dissolve a antiga "decisão 13": não há parâmetro padrão com nome de
cliente para neutralizar, porque o campo deixou de existir ali.

**Pronto quando:** `grep -rn "Projeto McCain\|McCain Alimentos" api/src` não
devolve nada; a planilha exportada e o cabeçalho do dashboard continuam trazendo
o nome certo; e Configurações mostra de qual ambiente está falando.

---

## Bloco D — Operação

### E1.13 — `scripts/ambiente.py`
**Depende de:** E1.2, E1.4
**Toca:** `scripts/ambiente.py` *(novo)*
**Faz:** linha de comando com `criar`, `conceder`, `revogar`, `arquivar`,
`desarquivar` e `listar`, chamando a porta `RegistroAmbientes` e o
`with ambiente_ativo(...)` — os **mesmos** caminhos que a tela da Entrega 2 vai
chamar (decisão 21). A clonagem da criação já entra aqui: unidades e parâmetros
do base, nada mais, criador como admin (decisão 12).

```
python scripts/ambiente.py criar --id suzano-mucuri \
    --projeto "Programação Suzano Mucuri" --cliente "Suzano S.A." --base mccain
python scripts/ambiente.py conceder --id suzano-mucuri --email fulano@timenow.com.br
```

**Pronto quando:** dá para criar dois ambientes, conceder acesso e ver a lista,
sem editar JSON à mão; e o ambiente criado nasce com as unidades do base e
**zero** atividades, locais, empresas, janelas e colaboradores além do criador.

### E1.14 — Modo demonstração com dois ambientes
**Depende de:** E1.6, E1.13
**Toca:** `api/src/core/auth.py`, `api/src/core/carga_inicial.py`,
`scripts/dev_local.py`
**Faz:** em modo demonstração, `com_sessao` devolve a identidade fixa
`demo@timenow.local`, sempre operadora; o registro nasce com `demo-obra` e
`demo-planta`, cada um com o histórico determinístico da `carga_inicial`
(decisão 20). O seletor de perfil da sidebar continua trocando o papel **dentro**
do ambiente escolhido.

Dois e não um: a troca de ambiente é a tela mais nova da entrega, e com um
ambiente só ela seria a única que ninguém consegue ver antes de publicar.

**Pronto quando:** duplo clique em `run.bat` abre o seletor com duas caixas,
entra em qualquer uma, troca entre elas, e o seletor de perfil continua
funcionando dentro de cada uma.

### E1.15 — Carga inicial restrita à demonstração
**Depende de:** E1.14
**Toca:** `api/src/core/repositorio.py` (`_semear`)
**Faz:** `_semear()` só gera o histórico determinístico quando o modo é
demonstração **e** o ambiente é de demonstração. Fora disso, semeia a forma
vazia (decisão 20). É uma condição em `_semear`, não um refatoramento —
`carga_inicial.gerar()` tem um único chamador.

**Pronto quando:** um ambiente criado com `PROGRAMACAO_MODO=producao` nasce com
zero atividades; `demo-obra` continua nascendo com o histórico de seis semanas.

---

## Bloco E — Verificação

### E1.16 — Infraestrutura de teste com disco e testes de isolamento
**Depende de:** E1.4, E1.5
**Toca:** `api/tests/conftest.py` *(novo)*, `api/tests/test_ambientes.py` *(novo)*
**Faz:** **estreia** a infraestrutura de teste que toca disco — hoje não existe
nenhuma: `test_dominio.py` importa só funções puras e nenhum teste chama
`repositorio.definir()`. Entra um `conftest.py` com fixture de diretório
temporário apontando `PROGRAMACAO_DATA_DIR`, e o arquivo novo com:

| Grupo | O que afirma |
|---|---|
| Registro | Listagem por e-mail devolve só ativos onde é membro; e-mail sem pertencimento recebe lista vazia; arquivar tira do seletor sem apagar; desarquivar devolve; slug fora do formato e slug repetido recusam |
| Ambiente ativo | Cookie ausente, ambiente inexistente, arquivado, não-membro e cabeçalho divergente: os cinco recusam. Cookie válido resolve |
| **Concorrência** | Duas threads dentro de dois `ambiente_ativo` diferentes ao mesmo tempo, cada uma escrevendo e lendo a própria base. Sem este teste, a garantia que substitui o singleton é promessa |
| Falha fechada | `repositorio.obter()` e `auditoria.registrar` fora de qualquer ambiente levantam |
| **Isolamento por agregado** | Escrever atividade, cadastro, janela, colaborador e parâmetro em A e confirmar ausência em B — **um caso por agregado**, obrigatório |
| Operador | Entra onde não é colaborador como `admin`; entra com o perfil do cadastro quando existe; conta na quantidade de pessoas com acesso |
| Clonagem | Recebe unidades e parâmetros; **não** recebe atividade, solicitação, trilha, local, empresa, janela nem colaborador; nome vem do formulário; criador vira admin |
| Carga inicial | Ambiente criado fora do modo demonstração nasce sem atividades |

**Pronto quando:** todos passam, e o de isolamento por agregado passa para os
**cinco** agregados — não quatro.

### E1.17 — Primeira publicação com SSO real
**Depende de:** todas as anteriores
**Toca:** configuração do Static Web App, `app/staticwebapp.config.json`
(sem mudança nesta entrega), `docs/ARCHITECTURE.md`
**Faz:** publica no Azure com Azure AD e `PROGRAMACAO_MODO=producao`. **Não é
deploy de rotina** — é a primeira vez que `x-ms-client-principal` chega de
verdade (risco aceito nº 1).

Roteiro de verificação, nesta ordem, porque a ordem separa as causas:

1. `/.auth/me` responde com principal — a sessão existe.
2. A guarda nomeia o e-mail recebido — se ele vier vazio ou como UPN, a claim é
   outra e `auth._principal` precisa de ajuste. **Este é o passo que E1.8
   existe para tornar barato.**
3. O e-mail nomeado casa com o membro do registro — a camada 1 funciona.
4. Entra no ambiente — a camada 2 funciona.
5. O cookie sobrevive a recarregamento e a aba nova, com `Secure` no domínio do
   SWA.
6. Os dois downloads e o relatório trazem o dado do ambiente certo.

**Pronto quando:** duas pessoas reais, em dois ambientes reais, trabalham sem
se enxergar — e o roteiro acima está registrado com o resultado de cada passo.

---

# Entrega 2 — Administração

**Objetivo:** o que o `scripts/ambiente.py` já faz, em tela, para o operador.

**Aceite da entrega:** a tela **não escreve regra nova** — só chama o que a
Entrega 1 já fez rodar. Se uma tarefa aqui precisar inventar regra, ela está no
lugar errado e volta para a Entrega 1.

### E2.1 — Área do operador dentro do seletor
**Depende de:** Entrega 1
**Toca:** `api/src/blueprints/ambientes.py`,
`api/src/templates/ambientes/_abas.html` *(novo)*
**Faz:** sub-navegação da área de administração, visível **apenas** ao operador
e servida por `com_sessao`. Não entra na tela de Configurações, que continua
sendo a administração *daquele* ambiente (decisão 17).
**Pronto quando:** o item não existe no DOM de quem não é operador.

### E2.2 — Listagem de ambientes
**Depende de:** E2.1
**Toca:** `api/src/blueprints/ambientes.py`,
`api/src/templates/ambientes/lista.html` *(novo)*
**Faz:** todos os ambientes com cliente, situação e quantidade de pessoas com
acesso (história 27). A contagem **inclui os operadores** — senão a tela mente.
**Pronto quando:** um ambiente com 4 colaboradores e 2 operadores mostra 6.

### E2.3 — Criar ambiente
**Depende de:** E2.2
**Toca:** `api/src/blueprints/ambientes.py`,
`api/src/templates/ambientes/criar.html` *(novo)*
**Faz:** formulário com identificador, projeto, cliente e ambiente base,
chamando a mesma função de criação do script. A tela **enuncia o que copia e o
que não copia antes da confirmação** (história 32) — copiar configuração de um
cliente para outro é decisão consciente e precisa parecer uma.
**Pronto quando:** o enunciado lista os dois grupos corretos; slug inválido ou
repetido é recusado na tela com a mensagem da porta, não com erro genérico.

### E2.4 — Membros: conceder, revogar, listar
**Depende de:** E2.2
**Toca:** `api/src/blueprints/ambientes.py`,
`api/src/templates/ambientes/membros.html` *(novo)*
**Faz:** as três operações da história 35 a 37. Os operadores aparecem na lista
marcados e não removíveis.
**Pronto quando:** revogar vale na requisição seguinte — a pessoa revogada cai
no seletor no clique seguinte, sem esperar sessão expirar.

### E2.5 — Arquivar e desarquivar
**Depende de:** E2.2
**Toca:** `api/src/blueprints/ambientes.py`
**Faz:** as duas operações, com confirmação. Arquivar é **estado, reversível**:
some do seletor, quem está dentro cai na guarda com "este ambiente foi
arquivado", nada é apagado (decisão 13).
**Pronto quando:** quem está dentro no momento do arquivamento vê a mensagem
**própria** de arquivado, e não "você não tem acesso"; desarquivar devolve tudo.

### E2.6 — Colaboradores marca o operador
**Depende de:** Entrega 1 (E1.5)
**Toca:** `api/src/blueprints/colaboradores.py`,
`api/src/templates/colaboradores/painel.html`
**Faz:** a tela de Colaboradores do ambiente passa a listar os operadores como
linha **"Operador Timenow"**, somente leitura, não removível pelo admin do
cliente (decisão 11). É a compensação do risco aceito nº 2: o cliente não pode
tirar, mas pode ver.
**Pronto quando:** o admin de um ambiente vê a linha, não consegue removê-la, e
a contagem da tela bate com a da listagem de E2.2.

### E2.7 — Testes da Entrega 2
**Depende de:** E2.3, E2.4, E2.5
**Toca:** `api/tests/test_ambientes.py`
**Faz:** afirma que a tela chama a regra e não a duplica: criar pela tela produz
o mesmo resultado que criar pelo script; a contagem de pessoas inclui operador;
arquivar pela tela recusa quem está dentro.
**Pronto quando:** passam, e nenhuma regra de negócio nova aparece em
`blueprints/ambientes.py`.

---

# Entrega 3 — API de leitura

**Objetivo:** a programação sai por HTTPS em JSON, autenticada por token por
ambiente.

**Aceite da entrega:** nenhuma rota de escrita existe no espaço de nomes, e o
teste do prefixo passa.

### E3.1 — Espaço de rotas e blueprint
**Depende de:** Entrega 1
**Toca:** `api/src/blueprints/dados_api.py` *(novo)*, `api/function_app.py`
**Faz:** o blueprint de `/api/dados/v1/*`, fora do decorador de fragmento — o
gate do Alpine e a sessão do SWA não se aplicam (decisão 22). A palavra `dados`
está no caminho de propósito, para que nenhum endpoint de fragmento caia no
espaço sem sessão por acidente de nome.
**Pronto quando:** o blueprint responde sem cabeçalho do Alpine e sem cookie.

### E3.2 — Token: modelo, emissão e guarda
**Depende de:** E1.2
**Toca:** `api/src/core/registro.py`
**Faz:** os métodos de token na porta do registro. Formato
`tn_<prefixo>_<segredo>`, com `secrets.token_urlsafe(32)`. Guarda o **prefixo
em claro** e o **SHA-256 do valor inteiro**; verifica localizando pelo prefixo e
comparando com `hmac.compare_digest` (decisão 24).

**Sem sal e sem derivação lenta, com o porquê escrito no código** — token de
máquina não é senha de gente, e 190 bits de entropia não precisam de bcrypt.
Sem esse comentário, alguém "conserta" isso e põe dezenas de milissegundos em
cada chamada do Power BI.

Conserva rótulo, prefixo, ambiente, quem emitiu, quando, validade opcional e
último uso.
**Pronto quando:** o valor completo não é recuperável depois da emissão; token
revogado, expirado e malformado recusam; token de A não alcança B.

### E3.3 — Autenticação bearer e resolução de ambiente pelo token
**Depende de:** E3.1, E3.2
**Toca:** `api/src/blueprints/dados_api.py`
**Faz:** o decorador da API: lê o bearer, resolve o token, abre o
`ambiente_ativo` daquele token. Sem cookie e sem cabeçalho de aba — o token
**é** a resolução do ambiente. Token de ambiente arquivado recusa com motivo
próprio (decisão 13).
**Pronto quando:** os cinco casos recusam com mensagem legível — ausente,
malformado, revogado, expirado, ambiente arquivado.

### E3.4 — Os quatro recursos
**Depende de:** E3.3
**Toca:** `api/src/blueprints/dados_api.py`
**Faz:** ambiente, atividades da semana, resumo da semana e cadastros, com os
filtros da tabela da decisão 22. **Semana obrigatória** nas atividades — sem
ela, uma requisição puxaria a base inteira do cliente (história 63).

Os números vêm da facade que já existe: `dados.listar_atividades`,
`dados.resumo_semana`, `dados.cadastros`. A API **não** reimplementa cálculo.
**Pronto quando:** pedir atividades sem semana é recusado; os filtros
restringem; a unidade vem junto de cada atividade.

### E3.5 — Envelope e erros
**Depende de:** E3.4
**Toca:** `api/src/blueprints/dados_api.py`
**Faz:** toda resposta traz `{"ambiente": {...}, "gerado_em": ..., "dados": ...}`
(decisão 23). Recusa é JSON com motivo legível, não fragmento.
**Pronto quando:** as quatro respostas trazem o envelope; o `gerado_em` é ISO
em UTC; nenhuma resposta de erro devolve HTML.

### E3.6 — Escrita amortizada
**Depende de:** E3.3
**Toca:** `api/src/core/registro.py`
**Faz:** o acesso vira **linha append-only** na trilha do registro — mesmo
mecanismo barato de `auditoria.registrar` — e o carimbo de último uso só
reescreve o registro quando o valor guardado tiver **mais de uma hora**
(decisão 25).

Sem isso, um refresh de Power BI chamando quatro recursos vira quatro
reescritas completas do arquivo que, se corromper, derruba todo mundo.
**Pronto quando:** cem chamadas seguidas produzem cem linhas de trilha e **no
máximo uma** reescrita do registro.

### E3.7 — Liberação no Static Web Apps e teste do prefixo
**Depende de:** E3.1
**Toca:** `app/staticwebapp.config.json`, `api/tests/test_ambientes.py`
**Faz:** acrescenta a entrada anônima de `/api/dados/v1/*` **acima** de
`/api/*` no array — o SWA avalia na ordem e a primeira que casa vence; abaixo,
ela nunca é alcançada e o consumidor leva redirecionamento para o login em vez
de JSON.

E o teste que varre as rotas registradas em `function_app.py` afirmando que
nenhuma rota de fragmento começa com `/api/dados/`. **Este teste substitui a
revisão humana do arquivo de configuração**, que é a coisa que a spec avisa que
quebra em produção sem quebrar em desenvolvimento — nem `run.bat` nem
`dev_local.py` aplicam esse arquivo.
**Pronto quando:** o teste passa, e a entrada anônima está acima de `/api/*` no
array — conferido lendo o arquivo, não de memória.

### E3.8 — Tela de tokens
**Depende de:** E3.2, E2.1
**Toca:** `api/src/blueprints/ambientes.py`,
`api/src/templates/ambientes/tokens.html` *(novo)*
**Faz:** emitir, listar e revogar, dentro da área do operador. A emissão mostra
o valor **uma vez** e diz em palavras o que a credencial entrega: a base
daquele cliente inteira, sem recorte por fornecedor (risco aceito nº 3). Essa
frase é parte da entrega, não enfeite.
**Pronto quando:** o valor completo aparece uma vez e nunca mais; a lista mostra
rótulo, prefixo e último uso aproximado.

### E3.9 — Testes da Entrega 3
**Depende de:** E3.5, E3.6, E3.7
**Toca:** `api/tests/test_ambientes.py`
**Faz:** token válido resolve; os cinco casos de recusa recusam; token de A não
alcança B; envelope presente; semana obrigatória; **nenhuma rota de escrita
existe no espaço de nomes** — afirmado varrendo os métodos registrados, não
conferindo à mão.
**Pronto quando:** passam.

### E3.10 — Documentação de produção
**Depende de:** E3.7
**Toca:** `docs/ARCHITECTURE.md`, `README.md`
**Faz:** registra a liberação anônima como item de verificação explícita no
deploy, e documenta o contrato da API para o analista do cliente.
**Pronto quando:** existe uma linha no roteiro de publicação dizendo para
conferir a ordem das rotas no `staticwebapp.config.json`.

---

# Documentação — transversal

Estas não pertencem a nenhuma entrega e são feitas **junto** da que as torna
verdadeiras, nunca depois.

| Tarefa | Quando | O que muda |
|---|---|---|
| `CONTEXT.md` — glossário | Com E1.2 | Entram Ambiente, Registro, Ambiente ativo, Membro, Operador, Seletor, Token. "Ambiente" entra com a definição explícita, e a documentação de infraestrutura passa a dizer "implantação" para a outra coisa |
| `docs/ARCHITECTURE.md` — decisões | Com E1.7, E1.6 e E3.1 | Hoje lista 17 decisões e **nenhuma** desta entrega. Precisa das três novas: porta por ambiente (a 16 muda), `com_sessao` (a 12 ganha irmã) e JSON como terceira exceção à hipermídia (a 1 ganha exceção) |
| `docs/ONDE-ESTA.md` | Com E1.13 | `registro.py`, `ambiente.py`, `scripts/ambiente.py` |
| `README.md` | Com E1.14 | O duplo clique agora abre um seletor com duas caixas — o texto atual descreve o boot antigo |

---

# Grafo de dependências

```
Entrega 1
  E1.1 ─┬─► E1.3 ──► E1.4 ─┬─► E1.7 ──► E1.8 ─────────────┐
        │                   │                              │
  E1.2 ─┼─► E1.5 ──► E1.6 ──┴─► E1.9 ──► E1.10 ──► E1.11 ──┴─► E1.12
        │            │
        └─► E1.13 ───┴─► E1.14 ──► E1.15
                              
  E1.4 + E1.5 ──► E1.16 ──► E1.17  (E1.17 depende de TODAS)

Entrega 2   (depende de Entrega 1 fechada)
  E2.1 ──► E2.2 ─┬─► E2.3 ─┐
                 ├─► E2.4 ─┼─► E2.7
                 └─► E2.5 ─┘
  E1.5 ──► E2.6

Entrega 3   (depende de Entrega 1 fechada; E3.8 depende de E2.1)
  E3.1 ─┬─► E3.3 ─┬─► E3.4 ──► E3.5 ─┐
  E3.2 ─┘         └─► E3.6 ──────────┼─► E3.9
  E3.1 ──► E3.7 ─────────────────────┘
  E3.7 ──► E3.10
  E3.2 + E2.1 ──► E3.8
```

**Caminho crítico da Entrega 1:** E1.1 → E1.3 → E1.4 → E1.7 → E1.8 → E1.9 →
E1.10 → E1.11 → E1.12 → E1.17. Os blocos A e D correm em paralelo com o C
depois que E1.4 fecha.

**Quatro tarefas destravam quase tudo:** E1.1, E1.2, E1.4 e E1.6. Enquanto elas
não fecharem, o resto da Entrega 1 fica esperando.

---

# Definição de pronto

Vale para toda tarefa, em cima do "Pronto quando" de cada uma.

1. As cinco etapas da porta de qualidade passam: lint e formatação do Python,
   verificação de tipos, testes de domínio, lint de JS/CSS/HTML e o verificador
   do padrão Timenow.
2. Nenhuma supressão solta de regra. Falso positivo estrutural se resolve na
   configuração, com comentário explicando.
3. Fragmento novo não traz `<link>` nem `<script src>` — contrato visual.
4. Classe visual nova, se houver, nasce no Design System e em um só dos três
   CSS.
5. Decisão que contraria o que está escrito na spec é anotada na spec **antes**
   de ser codificada, não depois.

---

# Riscos por entrega

| Entrega | Risco | Sinal de que aconteceu | O que fazer |
|---|---|---|---|
| 1 | **Vazamento entre ambientes por estado compartilhado** | Um teste de isolamento passa isolado e falha junto com outros | Não contornar reordenando teste — é `ContextVar` mal resetado ou cache com chave errada |
| 1 | **Claim de e-mail diferente do esperado** (risco aceito nº 1) | Ninguém entra em ambiente nenhum, depois de E1.17 | A guarda de E1.8 nomeia o e-mail recebido: se vier vazio ou como UPN, ajustar `auth._principal` |
| 1 | O `com_usuario` passa a fazer quatro coisas e cresce demais | O decorador vira difícil de ler | A resolução do ambiente é função própria chamada pelo decorador, não código inline |
| 2 | Regra de negócio nascendo no blueprint da tela | `blueprints/ambientes.py` cresce com validação | Toda regra desce para `registro.py`; a tela só chama — é o aceite da entrega |
| 3 | **Liberação anônima esquecida ou na ordem errada** | Funciona local, o consumidor recebe redirecionamento de login em produção | E3.7 tem teste; a ordem no array é conferida lendo o arquivo |
| 3 | O carimbo de último uso volta a ser por requisição | O `registro.json` vira o arquivo mais escrito da instalação | O teste de E3.6 (cem chamadas, no máximo uma reescrita) protege isso |

---

# O que este plano não faz

Está em Out of Scope na spec e não vira tarefa aqui: escrita pela API, escopo
de token por empresa, webhook de saída, dashboard entre ambientes, tema por
cliente, RBAC customizável, grupos do Azure AD, ligar o SharePoint, limite de
requisição e qualquer mudança no fluxo da programação.

**Não há tarefa de migração** — nada está publicado e o conteúdo de `data/` é
carga de demonstração (decisão 27). A Entrega 1 apaga e semeia no layout novo.

---

# Issues relacionadas

As issues de implementação deste plano estão em
[`docs/tasks/multi-ambiente/`](tasks/multi-ambiente/index.md), em **26 fatias
verticais** derivadas das 35 tarefas acima. O índice traz o mapa completo
tarefa → issue, o grafo de dependências e a **ordem de execução em oito ondas
de valor** — a numeração das issues é a ordem de execução, e seguir de
ISSUE-001 a ISSUE-022 sem paralelizar não deixa pendência fora de sequência.

| ID | Título | Entrega | Tipo | Situação | Rótulo | Bloqueada por | Arquivo |
|---|---|---|---|---|---|---|---|
| ISSUE-001 | Ambiente ativo por contexto, com base e trilha isoladas e falha fechada | 1 | Task | proposed | ready-for-agent | — | [Issue](tasks/multi-ambiente/001-ambiente-ativo-e-isolamento-na-persistencia.md) |
| ISSUE-002 | Registro de ambientes como porta própria, com slug validado e arquivamento reversível | 1 | Task | proposed | ready-for-agent | — | [Issue](tasks/multi-ambiente/002-registro-de-ambientes.md) |
| ISSUE-003 | Administração do registro por linha de comando, com clonagem enxuta na criação | 1 | Task | proposed | ready-for-agent | ISSUE-001, ISSUE-002 | [Issue](tasks/multi-ambiente/003-script-de-administracao-do-registro.md) |
| ISSUE-004 | Perfil operador vindo da configuração da implantação, com acesso implícito a todo ambiente | 1 | Task | proposed | ready-for-agent | ISSUE-001, ISSUE-002 | [Issue](tasks/multi-ambiente/004-perfil-operador-global.md) |
| ISSUE-005 | Costura HTTP do ambiente ativo — resolução por requisição, recusa por redirecionamento e guarda que nomeia a causa | 1 | Task | proposed | ready-for-agent | ISSUE-001, ISSUE-002, ISSUE-004 | [Issue](tasks/multi-ambiente/005-costura-http-do-ambiente-ativo.md) |
| ISSUE-006 | Seletor de ambientes depois do SSO, com a escolha recarregando para o destino certo | 1 | Task | proposed | ready-for-agent | ISSUE-005 | [Issue](tasks/multi-ambiente/006-seletor-de-ambientes-e-boot.md) |
| ISSUE-007 | Sidebar mostra o ambiente ativo e oferece a troca a quem tem mais de um | 1 | Task | proposed | ready-for-agent | ISSUE-006 | [Issue](tasks/multi-ambiente/007-sidebar-com-ambiente-ativo.md) |
| ISSUE-008 | Nome do projeto e do cliente saem dos parâmetros e passam a ter fonte única no registro | 1 | Task | proposed | ready-for-agent | ISSUE-007 | [Issue](tasks/multi-ambiente/008-projeto-e-cliente-saem-dos-parametros.md) |
| ISSUE-009 | Modo demonstração com dois ambientes semeados e carga inicial restrita à demonstração | 1 | Task | proposed | ready-for-agent | ISSUE-003, ISSUE-006 | [Issue](tasks/multi-ambiente/009-modo-demonstracao-com-dois-ambientes.md) |
| ISSUE-010 | Primeira publicação com SSO real e dois clientes isolados em produção | 1 | Task | proposed | ready-for-agent | ISSUE-008, ISSUE-009 | [Issue](tasks/multi-ambiente/010-primeira-publicacao-com-sso-real.md) |
| ISSUE-011 | Área do operador dentro do seletor, com a listagem de todos os ambientes | 2 | Task | proposed | ready-for-agent | ISSUE-010 | [Issue](tasks/multi-ambiente/011-area-do-operador-e-listagem-de-ambientes.md) |
| ISSUE-012 | Criar ambiente pela tela, enunciando o que é copiado e o que não é | 2 | Task | proposed | ready-for-agent | ISSUE-003, ISSUE-011 | [Issue](tasks/multi-ambiente/012-criar-ambiente-pela-tela.md) |
| ISSUE-013 | Membros do ambiente pela tela — conceder, revogar e listar quem tem acesso | 2 | Task | proposed | ready-for-agent | ISSUE-011 | [Issue](tasks/multi-ambiente/013-membros-conceder-revogar-listar.md) |
| ISSUE-014 | Arquivar e desarquivar ambiente pela tela, com a mensagem própria para quem está dentro | 2 | Task | proposed | ready-for-agent | ISSUE-011 | [Issue](tasks/multi-ambiente/014-arquivar-e-desarquivar-pela-tela.md) |
| ISSUE-015 | Tela de Colaboradores mostra o operador da Timenow como linha marcada e não removível | 2 | Task | proposed | ready-for-agent | ISSUE-004, ISSUE-011 | [Issue](tasks/multi-ambiente/015-colaboradores-marca-o-operador.md) |
| ISSUE-016 | Espaço de rotas versionado da API, liberado como anônimo na borda e guardado por teste de prefixo | 3 | Task | proposed | ready-for-agent | ISSUE-010 | [Issue](tasks/multi-ambiente/016-espaco-de-rotas-da-api-e-liberacao-anonima.md) |
| ISSUE-017 | Token de leitura por ambiente — emissão, guarda por hash e ciclo de vida | 3 | Task | proposed | ready-for-agent | ISSUE-002, ISSUE-010 | [Issue](tasks/multi-ambiente/017-token-de-leitura-modelo-e-guarda.md) |
| ISSUE-018 | Autenticação por token na API, com o ambiente resolvido pela própria credencial | 3 | Task | proposed | ready-for-agent | ISSUE-016, ISSUE-017 | [Issue](tasks/multi-ambiente/018-autenticacao-bearer-e-ambiente-pelo-token.md) |
| ISSUE-019 | Os quatro recursos de leitura em JSON, com envelope e semana obrigatória | 3 | Task | proposed | ready-for-agent | ISSUE-018 | [Issue](tasks/multi-ambiente/019-quatro-recursos-de-leitura-com-envelope.md) |
| ISSUE-020 | Consumo da API registrado em trilha append-only, com último uso amortizado | 3 | Task | proposed | ready-for-agent | ISSUE-018 | [Issue](tasks/multi-ambiente/020-escrita-amortizada-do-consumo-da-api.md) |
| ISSUE-021 | Tela de tokens na área do operador — emitir uma vez, listar e revogar | 3 | Task | proposed | ready-for-agent | ISSUE-011, ISSUE-017 | [Issue](tasks/multi-ambiente/021-tela-de-tokens.md) |
| ISSUE-022 | Documentação de produção e contrato da API para o analista do cliente | 3 | Task | proposed | ready-for-agent | ISSUE-016, ISSUE-019 | [Issue](tasks/multi-ambiente/022-documentacao-de-producao-e-contrato-da-api.md) |
| ISSUE-023 | Cadastrar a pessoa no ambiente passa a ser o ato de conceder acesso, com o registro como índice | 4 | Task | proposed | ready-for-agent | ISSUE-013, ISSUE-015 | [Issue](tasks/multi-ambiente/023-pertencimento-com-uma-edicao-so.md) |
| ISSUE-024 | Promover e rebaixar operadores pela área de administração, com a variável de ambiente como piso | 4 | Task | proposed | ready-for-agent | ISSUE-011, ISSUE-021 | [Issue](tasks/multi-ambiente/024-promover-operador-pela-tela.md) |
| ISSUE-025 | O seletor vira a tela inicial permanente — toda visita nova começa escolhendo o ambiente | 4 | Task | proposed | ready-for-agent | ISSUE-006, ISSUE-011 | [Issue](tasks/multi-ambiente/025-seletor-como-tela-inicial-permanente.md) |
| ISSUE-026 | Recurso /api/dados/v1/geral — as atividades de sempre, com o ambiente repetido em cada linha | 5 | Task | proposed | ready-for-agent | ISSUE-019 | [Issue](tasks/multi-ambiente/026-recurso-geral-com-ambiente-por-linha.md) |
