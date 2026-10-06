# Spec — Multi-ambiente, seletor de clientes e API de leitura

> Rótulo de triagem: `ready-for-agent`
> Revisão 2 — incorpora as 32 decisões da sessão de grilling. A revisão 1
> está preservada em `SPEC-MULTI-AMBIENTE.v1.bak.md`; o que caiu dela caiu
> por decisão, e está anotado na seção **O que mudou da revisão 1**.
> Revisão 2.1 — o `HttpOnly` sai dos atributos do cookie de ambiente; a
> anotação está no texto da decisão 5.

---

## Problem Statement

A Programação Semanal de Serviços foi construída para um cliente e hoje serve
a um cliente por instalação. Toda a base vive num único arquivo de programação,
e a porta de persistência é resolvida **uma vez por processo** — de modo que
todo mundo que entra na aplicação lê e escreve o mesmo dado.

Isso significa que atender Suzano, Alcoa e McCain exigiria **três implantações
separadas**: três publicações, três conjuntos de variáveis, três telas de
configuração para manter em sincronia e três versões do mesmo código
divergindo com o tempo. Cada cliente novo do portfólio multiplicaria o custo
de manutenção em vez de diluí-lo.

A configuração já é flexível o bastante para os segmentos: a unidade de medida
é um cadastro de apoio, e quem produz bobina de papel cadastra `bobina` do
mesmo jeito que quem produz batata cadastra `kg`. **O que falta não é a
configuração — é o isolamento.** Como existe uma base só, o cadastro de
unidades da mineração apareceria para a produção alimentícia, os locais e
frentes de um cliente apareceriam no filtro do outro, e o cadastro de
colaboradores — que é a própria autenticação da aplicação — seria
compartilhado entre empresas que não podem se enxergar.

Além disso, os parâmetros padrão do projeto nascem com o nome de um cliente
específico escrito no código, o que denuncia a premissa de instância única em
qualquer ambiente novo.

Por fim, os dados só saem da aplicação por planilha ou relatório em papel. Não
há como um Power BI, um data warehouse ou um sistema do cliente consumir a
programação por requisição HTTPS — o que impede a ferramenta de participar do
ecossistema de dados de quem a contrata.

**O momento é este.** A aplicação ainda não está publicada em lugar nenhum: o
que existe em `data/` é carga de demonstração, não planejamento real. Não há
usuário para avisar, sessão para preservar nem dado para migrar. Toda decisão
de layout de armazenamento e de formato de identificador pode ser tomada
agora ao custo de escrevê-la — e depois do primeiro cliente real, não pode.

---

## Solution

A aplicação passa a hospedar vários **ambientes** dentro de uma única
instalação. Um ambiente é a instância de dados de um cliente: sua programação,
seus cadastros, suas janelas, seus colaboradores e sua trilha de auditoria,
sem nenhum ponto de contato com os demais.

Depois do SSO, a pessoa cai numa **tela de seleção de ambientes**: uma caixa
por ambiente que ela pode acessar, com o nome do projeto e do cliente. Ao
escolher, ela entra na aplicação que já existe — mesma sidebar, mesma matriz,
mesmo dashboard — só que apontada para a base daquele cliente. Uma faixa na
sidebar mostra em qual ambiente ela está e oferece a troca a qualquer momento.

Quem tem acesso a um ambiente é decidido em duas camadas:

1. **Registro de ambientes** (global, acima de todos os clientes) — diz quais
   ambientes existem e quais e-mails podem entrar em cada um. É o que monta a
   tela de seleção.
2. **Cadastro de colaboradores** (dentro de cada ambiente, como hoje) — diz com
   qual perfil a pessoa entra ali. A regra que já vale continua valendo: um
   e-mail fora do cadastro não entra, com ou sem sessão do Azure.

Acima das duas camadas existe um perfil global — **operador** — que administra
o registro: cria ambientes, concede e revoga acesso, emite e revoga tokens. Ele
é definido na configuração da implantação, não no dado, e é a única coisa que
enxerga todos os clientes. O perfil `admin` de hoje continua sendo o
administrador **daquele** ambiente e não ganha visão dos outros.

Criar um ambiente novo copia do ambiente base apenas o que não pertence a
cliente nenhum — as unidades de medida e os parâmetros numéricos do projeto. O
resto nasce vazio: sem atividades, sem locais, sem empresas, sem janelas e sem
colaboradores além de quem criou. Um cliente novo do portfólio abre com as
unidades do segmento prontas para ajuste e sem um único dado do cliente que
serviu de base.

E os dados passam a sair por HTTPS: uma **API de leitura em JSON**, autenticada
por **token por ambiente**, entrega a programação da semana, o resumo e os
indicadores para quem for consumi-los depois — Power BI, data warehouse ou o
sistema do cliente.

---

## Entrega em três fases

A entrega tem quatro assuntos com riscos diferentes: isolamento de dado, telas
de administração, exposição pública de API e configuração de borda. Juntá-los
significa revisá-los ao mesmo tempo, e o mais perigoso perde a atenção para o
mais visível. Por isso vão ao ar separados.

| Fase | O que entra | Critério de aceite |
|---|---|---|
| **1 — Isolamento** | Ambiente como conceito, resolução por requisição, seletor, cookie e cabeçalho, `RegistroAmbientes`, script de linha de comando, modo demonstração com dois ambientes, **primeira publicação com SSO real** | O teste de isolamento por agregado passa, e duas pessoas em dois ambientes não se enxergam em nenhuma tela |
| **2 — Administração** | Tela do registro: criar, clonar, conceder, revogar, arquivar, listar membros | A tela não escreve regra nova — só chama o que a Fase 1 já fez rodar |
| **3 — API** | Espaço de rotas versionado, tokens, contrato de leitura, liberação anônima no Static Web Apps | Nenhuma rota de escrita existe no espaço de nomes, e o teste do prefixo passa |

A Fase 1 sobe sem tela de administração: os ambientes nascem e o acesso é
concedido por `scripts/ambiente.py`, que chama exatamente as mesmas funções que
a tela da Fase 2 vai chamar. Assim a regra nasce e roda antes de existir tela,
e a Fase 2 só desenha.

---

## User Stories

### Seleção de ambiente · Fase 1

1. Como usuário autenticado por SSO, quero ver uma primeira tela com uma caixa
   por cliente que posso acessar, para escolher em qual base vou trabalhar.
2. Como usuário, quero que cada caixa mostre o nome do projeto e o nome do
   cliente, para reconhecer o ambiente sem precisar abri-lo.
3. Como usuário com acesso a um único ambiente, quero entrar direto nele, para
   não precisar de um clique que não tem alternativa.
4. Como usuário com acesso a um único ambiente, quero mesmo assim conseguir
   ver qual ambiente estou usando, para nunca duvidar de onde estou.
5. Como usuário sem acesso a nenhum ambiente, quero uma tela que explique isso
   e diga a quem pedir liberação, em vez de uma tela vazia.
6. Como usuário, quero ver na sidebar o nome do ambiente ativo, para não
   lançar produção no cliente errado.
7. Como usuário com acesso a mais de um ambiente, quero trocar de ambiente a
   qualquer momento pela sidebar, sem sair e entrar de novo na aplicação.
8. Como usuário, quero que ao trocar de ambiente a aplicação volte para a tela
   inicial daquele ambiente, para não ficar numa tela cujo filtro pertence ao
   ambiente anterior.
9. Como usuário, quero que meu acesso revogado a um ambiente me devolva à tela
   de seleção com uma mensagem clara, e não uma tela quebrada.
10. Como usuário, quero que meu ambiente escolhido continue valendo se eu
    recarregar a página, abrir uma aba nova ou abrir um link direto, para não
    reescolher a cada navegação.
11. Como usuário, quero **reescolher o ambiente quando abro o navegador de
    novo**, para nunca começar o dia já apontado para um cliente que eu não
    escolhi hoje.
12. Como usuário que abriu um link direto sem ter ambiente escolhido, quero
    chegar naquele endereço depois de escolher, e não na tela inicial.
13. Como usuário, quero que exportar a planilha e imprimir o relatório tragam o
    dado do ambiente ativo, porque download é navegação normal do navegador e
    não pode perder o contexto.
14. Como usuário com duas abas abertas em ambientes diferentes, quero que a aba
    velha **me avise** ao ser usada, em vez de gravar silenciosamente no
    ambiente que a outra aba escolheu.

### Isolamento de dados · Fase 1

15. Como cliente Suzano, quero que minha programação não seja visível a nenhum
    usuário de outro cliente, para que meu dado de produção não vaze.
16. Como administrador de um ambiente, quero que meu cadastro de locais e
    frentes contenha só os meus, para que o filtro da matriz seja útil.
17. Como administrador de um ambiente de papel e celulose, quero cadastrar
    `bobina` e `rolo` como unidades sem que elas apareçam para o ambiente de
    produção alimentícia.
18. Como administrador de um ambiente de mineração, quero cadastrar minhas
    empresas contratadas sem que elas apareçam na janela de programação de
    outro cliente.
19. Como administrador de um ambiente, quero que meu cadastro de colaboradores
    contenha só as pessoas do meu projeto — **mais as pessoas da Timenow que
    operam a plataforma, marcadas como tais e que eu não posso remover** —
    porque ele é a lista de acesso e precisa ser completa para ser verdadeira.
20. Como auditor, quero que a trilha de auditoria de um ambiente registre só os
    eventos daquele ambiente, para que a trilha sirva de prova.
21. Como planejador, quero que a numeração de item e a ID exclusiva sejam
    únicas dentro do meu ambiente e da minha semana, sem colidir com as de
    outro cliente.
22. Como fornecedor com vínculo de empresa contratada, quero continuar vendo
    apenas a minha empresa dentro do ambiente, porque o recorte por vínculo
    continua valendo por cima do recorte por ambiente.
23. Como responsável pelo produto, quero que um erro de configuração jamais
    faça uma requisição cair no ambiente errado — prefiro a requisição ser
    recusada a ela ser respondida com dado alheio.
24. Como desenvolvedor, quero que **nenhum código consiga tocar a base sem
    dizer de qual ambiente** — nem um script, nem um teste, nem a carga
    inicial — para que o isolamento não dependa de disciplina.

### Diagnóstico de acesso · Fase 1

25. Como pessoa recusada na entrada, quero saber **qual e-mail** o Azure
    entregou, para descobrir que a recusa é de identidade e não de permissão.
26. Como pessoa recusada, quero que as quatro causas tenham quatro mensagens
    diferentes — nenhum e-mail na sessão, e-mail fora do registro, e-mail fora
    do cadastro daquele ambiente, ambiente arquivado — porque uma mensagem só
    para quatro causas não diagnostica nenhuma.

### Administração de ambientes · Fase 1 (script) e Fase 2 (tela)

27. Como operador, quero listar todos os ambientes existentes, com cliente,
    situação e quantidade de pessoas com acesso.
28. Como operador, quero criar um ambiente novo informando o identificador, o
    nome do projeto e o nome do cliente, para atender um cliente novo do
    portfólio sem publicar outra instalação.
29. Como operador, quero escolher um ambiente existente como base ao criar um
    novo, para herdar as unidades de medida do mesmo segmento.
30. Como operador, quero que a criação copie **as unidades de medida e os
    parâmetros do projeto** do ambiente base, porque é o que se repete entre
    clientes sem pertencer a nenhum.
31. Como operador, quero que a criação **não** copie atividade, realizado,
    solicitação de governança, trilha, local, empresa contratada, janela de
    programação nem colaborador, para que dado de um cliente nunca entre no
    ambiente de outro.
32. Como operador, quero que a tela diga explicitamente o que será copiado e o
    que não será, antes de eu confirmar.
33. Como operador, quero que o nome do projeto e do cliente do ambiente novo
    venham do formulário e não do ambiente base, para não herdar o nome errado.
34. Como operador, quero que o identificador do ambiente seja imutável depois
    de criado, para que pasta, cookie, trilha e integração nunca precisem ser
    reescritos.
35. Como operador, quero conceder acesso a um ambiente informando o e-mail da
    pessoa, para liberar quem precisa entrar.
36. Como operador, quero revogar o acesso de alguém a um ambiente e que isso
    valha na requisição seguinte, sem esperar a sessão expirar.
37. Como operador, quero ver, por ambiente, a lista de quem tem acesso, para
    revisar periodicamente quem enxerga o quê.
38. Como operador, quero arquivar um ambiente encerrado para que ele suma da
    tela de seleção sem que o dado seja apagado.
39. Como operador, quero que arquivar seja **reversível e não apague nada**,
    para que o histórico do contrato encerrado continue recuperável e possa
    voltar a funcionar sem reconfigurar integração.
40. Como usuário dentro de um ambiente que acabou de ser arquivado, quero ser
    devolvido ao seletor com a mensagem "este ambiente foi arquivado", e não
    com "você não tem acesso" — porque são coisas diferentes.
41. Como operador, quero que a criação do ambiente me cadastre automaticamente
    como administrador dele, para conseguir concluir a configuração inicial.
42. Como operador, quero que toda criação, arquivamento, concessão e revogação
    fiquem registradas numa trilha própria do registro de ambientes.
43. Como administrador de um ambiente, quero continuar administrando apenas o
    meu — cadastros, janelas, colaboradores — sem enxergar nem tocar nos
    outros.
44. Como administrador de um ambiente, quero que a tela de configurações mostre
    de qual ambiente ela está falando, para não configurar o cliente errado.
45. Como operador, quero fazer tudo isso **por linha de comando na Fase 1**,
    para que os ambientes existam e a entrega seja demonstrável antes de a tela
    ser escrita.

### API de leitura · Fase 3

46. Como analista de dados do cliente, quero consumir a programação por
    requisição HTTPS em JSON, para alimentar meu Power BI sem exportar planilha
    à mão.
47. Como operador, quero emitir um token de leitura vinculado a um ambiente,
    para liberar o consumo do dado daquele cliente.
48. Como operador, quero ver o token completo apenas uma vez no momento da
    emissão, para que ele não fique legível na tela depois.
49. Como operador, quero identificar cada token por um rótulo e pelos primeiros
    caracteres, para saber qual integração usa qual.
50. Como operador, quero revogar um token e que ele pare de funcionar na
    requisição seguinte.
51. Como operador, quero ver **aproximadamente** quando cada token foi usado
    pela última vez — com precisão de hora, não de segundo — para revogar os
    que ninguém consome sem que a leitura custe uma escrita.
52. Como operador, quero definir uma data de validade opcional para o token,
    para que uma integração temporária expire sozinha.
53. Como consumidor da API, quero receber a lista de atividades de uma semana
    em JSON, com previsto e realizado por dia, para reproduzir o cálculo no meu
    lado.
54. Como consumidor da API, quero receber o resumo da semana com aderência, PPC
    e as faixas, para não reimplementar o cálculo do domínio.
55. Como consumidor da API, quero filtrar por semana, empresa, local e situação,
    para trazer só o que me interessa.
56. Como consumidor da API, quero receber a unidade de medida junto de cada
    atividade, porque as unidades não são somáveis entre si.
57. Como consumidor da API, quero receber a lista de cadastros do ambiente
    (locais, empresas, unidades), para montar meus próprios filtros.
58. Como consumidor da API, quero uma mensagem de erro clara quando meu token é
    inválido, expirado, revogado ou pertence a ambiente arquivado, para saber o
    que resolver.
59. Como consumidor da API, quero que meu token nunca me dê acesso a outro
    ambiente, mesmo que eu descubra o identificador dele.
60. Como consumidor da API, quero que a resposta traga o identificador do
    ambiente e o momento em que foi gerada, para conferir de onde e de quando é
    o dado que carreguei.
61. Como responsável pela segurança, quero que a API de leitura não permita
    nenhuma escrita, para que o fluxo de aprovação nunca seja contornado por
    integração.
62. Como responsável pela segurança, quero que os tokens não sejam armazenados
    em texto puro, para que o vazamento do arquivo de configuração não vire
    vazamento de acesso.
63. Como responsável pela segurança, quero que a semana seja obrigatória ao
    pedir atividades, para que ninguém puxe a base inteira numa requisição.
64. Como operador, quero que os acessos pela API fiquem registrados, para
    auditar o consumo do dado do cliente.

### Operação e desenvolvimento

65. Como responsável pelo produto, quero que o nome do projeto e do cliente
    deixem de morar nos parâmetros do ambiente, para que exista uma fonte só e
    o seletor nunca discorde da sidebar.
66. Como desenvolvedor, quero rodar a aplicação localmente com **dois**
    ambientes de demonstração, para revisar a troca de ambiente sem publicar.
67. Como desenvolvedor, quero que a carga inicial de demonstração popule apenas
    os ambientes de demonstração, para que um ambiente novo em produção nunca
    nasça com atividades fictícias.
68. Como desenvolvedor, quero que as telas, blueprints e regras de domínio
    existentes não precisem saber que existem ambientes, para que a mudança não
    se espalhe pelo código todo.
69. Como desenvolvedor, quero uma forma de escrever teste que fixe o ambiente
    ativo, para testar isolamento sem subir servidor.
70. Como responsável pelo produto, quero que trocar a porta de persistência
    para o SharePoint continue sendo uma variável de ambiente depois desta
    mudança, para não perder a decisão de arquitetura que já existe.

---

## Implementation Decisions

### 1. Ambiente vira conceito de primeira classe

Entra no glossário do domínio, junto com os termos que ele traz:

| Termo | Significado |
|---|---|
| **Ambiente** | A instância de dados de um cliente. Tem identificador estável e imutável, nome de projeto, nome de cliente e situação (ativo ou arquivado). |
| **Registro de ambientes** | O cadastro global, acima de todos os ambientes: quais existem e quem pode entrar em cada um. |
| **Ambiente ativo** | O ambiente resolvido para a requisição corrente. |
| **Membro do ambiente** | E-mail com direito de entrar. Decide o que aparece no seletor — não decide o perfil. |
| **Operador** | Perfil global da Timenow que administra o registro de ambientes. Vem da configuração da implantação, nunca do dado. |
| **Seletor de ambientes** | A primeira tela depois do SSO. |
| **Token de leitura** | Credencial da API JSON, vinculada a um ambiente e somente leitura. |

### 2. Duas camadas de acesso, e as duas são obrigatórias

> **Revisão 3 — o pertencimento passa a ter uma edição só.** O que está
> descrito abaixo continua valendo na leitura: o registro é quem responde
> "quais caixas aparecem no seletor", e o cadastro de colaboradores é quem
> responde "com qual perfil a pessoa entra". O que muda é **onde se edita**:
> conceder acesso deixa de ser um ato do operador no registro e passa a ser
> consequência de cadastrar a pessoa na tela de Colaboradores **daquele
> ambiente**. O registro vira um índice mantido pela própria aplicação.
>
> O motivo é o mesmo da decisão 4: duas moradas para o mesmo fato, editadas
> por gente diferente, produzem discordância. Hoje a pessoa nova exige duas
> edições — membro no registro e colaborador no ambiente — e esquecer a
> primeira produz alguém que existe no ambiente e não o enxerga no seletor.
>
> O índice permanece porque a alternativa é abrir a base de todos os
> ambientes a cada login, que é exatamente o custo que a decisão 4 recusou.
> Ver **Revisão 3 — o que mudou** no fim do documento.

O registro de ambientes decide **quais caixas aparecem** no seletor. O cadastro
de colaboradores do ambiente decide **com qual perfil a pessoa entra**. Um
e-mail que consta no registro mas não no cadastro de colaboradores daquele
ambiente **não entra** — a decisão de que o cadastro de colaboradores é a
autenticação continua intacta, apenas passa a ser consultada dentro do ambiente
escolhido.

Isso resolve um ovo-e-galinha real: a resolução do usuário lê o cadastro de
colaboradores, que passa a viver dentro de cada ambiente; logo a pergunta
"quais ambientes esta pessoa vê?" precisa ser respondida por um registro que
existe **antes** de qualquer ambiente ser escolhido.

A exceção é o operador, e ela está na decisão 11.

### 3. O identificador do ambiente é um slug curto e imutável

Formato `^[a-z0-9-]{2,32}$` — `mccain`, `suzano-mucuri`, `alcoa-pocos`. Campo
próprio do formulário, não derivado do nome do cliente.

Ele vaza para sete lugares de uma vez: nome da pasta em `data/`, valor do
cookie, valor do cabeçalho conferido contra o cookie, prefixo do conjunto de
listas na implementação SharePoint, chave do cache de portas, campo do envelope
de resposta da API e identificador na trilha do registro. Por isso é
**imutável** depois de criado e **nunca reaproveitado** depois de arquivado —
reaproveitar um slug faz o histórico de dois contratos se confundir.

Legível, e não opaco, porque quem abre `data/` precisa entender o que está
vendo sem consultar o registro. Renomear o cliente muda o nome exibido, nunca o
slug.

### 4. O registro é dono do nome do projeto e do cliente

`projeto` e `cliente` **saem** de `PARAMETROS_PADRAO` e da tela de
Configurações. O registro de ambientes é a única fonte; a sidebar, o seletor e
a tela de Configurações leem de lá, e Configurações exibe o nome em leitura, só
para a pessoa saber onde está.

Duas moradas para o mesmo fato, editadas por gente diferente — o operador no
registro, o admin em Configurações — produziriam um seletor discordando da
sidebar. E a alternativa (os parâmetros mandarem) obrigaria a abrir a base de
cada ambiente só para desenhar as caixas do seletor: N leituras de arquivo por
login.

Isso também dissolve o problema dos "parâmetros padrão com nome de cliente": não
há campo para neutralizar, porque o campo deixou de existir ali.

### 5. O ambiente ativo viaja em cookie **e** em cabeçalho, e os dois são conferidos

O seletor grava um cookie ao escolher o ambiente. O decorador `com_usuario` —
a costura única por onde toda requisição de fragmento já passa — ganha um
quarto passo, antes da resolução do usuário: **resolver e validar o ambiente
ativo**.

A ordem passa a ser: gate do fragmento → ambiente ativo → usuário → permissão.

O cookie é uma **pista, nunca uma autorização**. Em toda requisição ele é
conferido contra o registro: o ambiente existe, está ativo, e o e-mail
autenticado é membro dele. Falhando qualquer uma, a resposta é a recusa da
decisão 9.

**O cabeçalho existe por causa das abas.** Cookie é estado por navegador, não
por aba: quem abre Suzano numa aba e Alcoa noutra tem um cookie só, e trocar de
ambiente na segunda aba re-aponta a primeira em silêncio — a tela continua
mostrando a matriz da Suzano e o próximo POST grava na Alcoa. É exatamente o
"lançar produção no cliente errado" da história 6, causado pelo mecanismo
escolhido para preveni-lo.

Então: a view carrega o slug em que foi renderizada e o envia num cabeçalho em
toda requisição do Alpine AJAX. Cabeçalho divergindo do cookie é **recusa**, com
a mensagem "esta aba está em outro ambiente". Os dois downloads e o relatório
para impressão, que não têm cabeçalho do Alpine, levam o slug na query e são
conferidos do mesmo jeito.

Atributos do cookie: `SameSite=Lax`, `Secure` fora do modo local, caminho
raiz e **sem `Max-Age`** — cookie de sessão. Ele sobrevive a
recarregamento, a aba nova e a link direto, que é tudo o que a história 10 pede;
o que ele não sobrevive é a fechar o navegador, e isso é de propósito. Quem tem
um ambiente só entra direto de qualquer forma, então o único beneficiado por um
cookie longo seria quem tem vários — que é exatamente quem mais precisa escolher
conscientemente.

*Anotação da implementação (ISSUE-006, revisão 2.1): `HttpOnly` saiu desta
lista.* O boot do shell é um documento estático e precisa decidir **no
cliente** se já existe escolha feita; com `HttpOnly`, o JavaScript não enxerga
o cookie e o boot entraria em laço reconsultando o seletor para sempre. A
perda é nula: o slug não é segredo — ele já viaja no cabeçalho `X-TN-Ambiente`
e na query dos downloads — e o cookie continua sendo só uma pista, conferida
contra o registro em toda requisição. O precedente citado abaixo (o cookie do
perfil da demonstração) já é legível por JS.

Há precedente no código: o modo demonstração já lê um cookie para trocar de
perfil.

**Por que cookie e não só cabeçalho:** os dois downloads (planilha da semana e
modelo em Excel) e o relatório para impressão são navegações reais do
navegador, sem o cabeçalho do Alpine AJAX. Um esquema baseado só em cabeçalho
perderia o ambiente exatamente neles.

**Por que não prefixo de rota nem subdomínio:** o prefixo tocaria as cerca de
quarenta rotas dos dez blueprints, o servidor de desenvolvimento local, a
configuração de rotas do Static Web Apps e todos os alvos e links das views.
O subdomínio exigiria DNS e certificado por cliente e mataria a troca de
ambiente em tela. Ambos espalham o custo; o cookie o concentra em um lugar.

### 6. Um segundo decorador para o que roda sem ambiente

A ordem "ambiente → usuário" tem um buraco: o próprio seletor não tem ambiente
ativo, e a administração do registro vive acima de todos. Esses endpoints não
podem usar `com_usuario`, e não podem resolver a pessoa pelo cadastro de
colaboradores, porque não se sabe de qual.

Entra **`com_sessao`**, decorador irmão em `blueprints/_comum.py`: resolve só a
identidade do SSO — o e-mail do `x-ms-client-principal` — e consulta o registro.
Não toca cadastro de colaboradores e não exige ambiente. Serve o seletor e a
administração do registro, e nada mais.

`com_usuario` fica como está e passa a exigir ambiente.

### 7. A porta de persistência deixa de ser um singleton de processo, por `ContextVar`

Hoje a porta é construída uma vez e guardada num módulo. Passa a ser
**resolvida por ambiente ativo**.

O mecanismo é `contextvars.ContextVar`, e a escolha não é estilística. Em Azure
Functions o handler síncrono roda num pool de threads do mesmo processo, com
requisições concorrentes vivas ao mesmo tempo: uma variável global de módulo
vazaria entre elas e produziria o pior defeito possível da entrega — responder
Suzano com dado da Alcoa. `threading.local` funcionaria hoje e apodreceria no
dia em que algum endpoint virasse assíncrono.

**A única forma de existir ambiente ativo em todo o código é um gerenciador de
contexto:**

```python
with ambiente_ativo("mccain"):
    ...
```

Ele seta o `ContextVar` na entrada e faz `reset()` na saída, inclusive com
exceção. O decorador o usa por dentro; os testes, a carga inicial e os scripts
o usam direto. **Fora dele, `repositorio.obter()` levanta** — nunca cai num
ambiente padrão, nunca adivinha. É a história 23 e a história 24 virando código,
e é o que torna o teste de isolamento duas linhas: escreve dentro de um `with`,
lê dentro do outro.

Nenhuma chamada da facade de domínio muda de assinatura — ela continua pedindo
"a porta" e recebendo a do ambiente corrente. Entre o decorador e a porta, a
facade, os dez blueprints, os templates e as views seguem sem saber que
ambientes existem.

O ponto de troca usado pelos testes (`repositorio.definir`) ganha a chave de
ambiente e continua sendo a costura de teste.

### 8. O cache de portas é correção, não otimização

Uma `RepositorioJson` é quase nada: um `Path` e um `threading.RLock`. Economizar
o objeto não justificaria cache nenhum. **O que justifica é a trava**: duas
instâncias para o mesmo ambiente são duas travas diferentes, e aí o
`_ler` → modificar → `_gravar` de duas threads deixa de ser serializado. O
rename continua atômico, mas uma das gravações simplesmente some.

Logo: um `dict` de slug para instância, criado sob trava própria com dupla
checagem, **sem expiração e sem limite**. A entrada vive enquanto o processo
viver; com dezenas de ambientes o custo total é um `Path` e um `RLock` por
cliente. Descarte por menos-usado reintroduziria exatamente o defeito que o
cache existe para evitar.

Arquivar não remove a entrada — nem precisa, porque a validação do ambiente
acontece antes de a porta ser pedida.

### 9. Recusa de ambiente responde redirecionamento, não fragmento

`_sem_permissao` renderiza a guarda **no alvo que o chamador pediu**, e o
comentário no código explica por quê: Alpine AJAX esvazia qualquer alvo
declarado que não venha na resposta.

A recusa de ambiente é diferente das outras. Acesso revogado (história 9),
ambiente arquivado (história 40) ou aba velha (decisão 5) não podem ser
desenhados dentro do `#drawer` ou do `#prog-tabela`: o resto da tela continuaria
mostrando a matriz do ambiente errado, com a sidebar dizendo o nome errado.

Então a recusa **de ambiente, e só ela**, responde com o redirecionamento que o
gate de fragmento já usa. O shell recarrega, o boot roda de novo e o seletor
aparece com a mensagem. Reaproveita `redirect_to` e o `@ajax:redirect` que já
estão escritos. Trabalho não salvo na aba se perde — que é o correto, já que ele
pertencia a outro ambiente.

### 10. A trilha de auditoria lê o mesmo `ContextVar`

`auditoria._arquivo()` passa a resolver `data/<slug>/auditoria.jsonl` a partir do
mesmo `ambiente_ativo`, e levanta pelo mesmo caminho quando não há ambiente: a
trilha nunca escreve sem saber de quem é.

Fica fora da porta de persistência de propósito. A trilha é barata por
construção — um `open(..., "a")` que nunca lê o conteúdo anterior, chamado em
toda mutação, engolindo `OSError` para que uma falha de trilha não derrube a
operação que ela observa. Movê-la para dentro da porta a transformaria numa
operação de persistência como as outras, com o custo que as outras têm.

O buraco do SharePoint (um `.jsonl` em disco local não existe lá, e num Azure
Function nem sobrevive a uma reiniciação) **já existe hoje, idêntico**. Não é
desta entrega consertá-lo, e misturar as duas coisas engorda a fase mais
arriscada.

O registro de ambientes tem **trilha própria**, separada: criação, arquivamento,
concessão e revogação de acesso, emissão e revogação de token e acesso pela API
são eventos do registro, não de nenhum cliente.

### 11. Perfil operador — configuração como piso, tela como complemento

> **Revisão 3 — a tela passa a promover operador.** O que está descrito
> abaixo continua valendo como **piso**: a variável de ambiente garante que
> exista ao menos um operador mesmo com o registro vazio, apagado ou
> corrompido, e ninguém a remove pela tela. O que muda é que a área de
> administração passa a **promover e rebaixar operadores adicionais**,
> guardados no registro, ao lado da configuração de tokens.
>
> As três razões originais continuam de pé e é por isso que a variável não
> sai: o ovo-e-galinha da instalação limpa, a porta de entrada que sobrevive
> a um registro corrompido, e o poder máximo que não pode ser fabricado por
> quem comprometer o dado. O que a revisão 3 acrescenta é conveniência
> operacional acima desse piso — quem já é operador promove outro sem
> reiniciar a instalação.
>
> **Um operador da variável nunca é rebaixado pela tela.** A tela mostra a
> origem de cada um — configuração ou registro — e só oferece remoção para
> os do registro. Ver **Revisão 3 — o que mudou** no fim do documento.

Os operadores vêm de uma variável de ambiente:

```
PROGRAMACAO_OPERADORES=felipe.bortolini@timenow.com.br;leonardo.gomes@timenow.com.br
```

**Só dela.** A tela da Fase 2 não promove operador. Três razões: não há segundo
ovo-e-galinha para resolver (numa implantação limpa o registro nasce vazio e
ainda assim existe operador); um registro apagado ou corrompido não deixa a
instalação sem porta de entrada; e um registro comprometido não consegue
fabricar o papel que enxerga todos os clientes, porque o poder máximo mora fora
do dado.

Não existe regra de "último operador" — não há remoção. Trocar quem opera é
trocar a variável e reiniciar.

**O operador entra em todo ambiente, implicitamente.** Isto reverte a decisão da
revisão 1, e a consequência está assumida: quem é operador é membro e
administrador de qualquer ambiente, presente e futuro, sem depender de
concessão.

Com qual perfil ele entra:

- Se o e-mail já constar no cadastro de colaboradores daquele ambiente, **vale o
  cadastro** — o que permite a um operador que também é fiscal de um projeto
  entrar como fiscal lá.
- Se não constar, entra como `admin`, vínculo `timenow`.

**E ele é visível.** Em qualquer dos dois casos o operador aparece na tela de
Colaboradores do ambiente como linha marcada **"Operador Timenow"**, somente
leitura: o admin do cliente vê que existe e não pode removê-la. Sem isso, a
história 37 ("a lista de quem tem acesso") e a história 27 ("quantidade de
pessoas com acesso") mentiriam, e a tela que o cliente abre para auditar o
próprio acesso omitiria justamente quem tem mais poder.

As permissões novas cobrem: administrar o registro, conceder e revogar acesso,
emitir e revogar token.

### 12. Clonagem na criação — só o que não pertence a cliente nenhum

**Copiado do ambiente base:** unidades de medida e parâmetros do projeto (metas
de aderência e PPC, regra e limite de justificativa de desvio).

**Nunca copiado:** atividades, realizado, solicitações de governança, trilha de
auditoria, sequência e contagem de itens por semana, **locais**, **empresas
contratadas**, **janelas de programação** e **cadastro de colaboradores**.

**Vindo do formulário:** identificador, nome do projeto e nome do cliente.

**Criado automaticamente:** quem criou, como administrador do ambiente novo.

A revisão 1 mandava copiar cadastros, janelas e colaboradores, e isso se
contradizia com a própria promessa de "sem um único dado do cliente que serviu
de base". Empresas contratadas e locais são dado operacional do cliente;
colaboradores são a lista de acesso, e copiá-la não é cadastro sujo, é acesso
concedido por engano.

**Janela também sai, e por um motivo estrutural:** janela é registro por
empresa — `gravar_janela` casa por `janela["empresa"]` — e carrega
`semanas_liberadas` com semanas da obra do cliente base. Copiá-la levaria a
lista de fornecedores e o calendário de outro cliente, e produziria janelas
órfãs: regras de escrita apontando para empresas que não existem no cadastro
(agora vazio) do ambiente novo.

O que sobra — unidades e parâmetros — é pouco e é exatamente o que se repete: o
segundo cliente de papel e celulose quer as unidades do primeiro.

A tela enuncia essa divisão antes da confirmação.

### 13. Arquivar suspende, e é reversível

Arquivar é estado, não exclusão:

- O ambiente some do seletor.
- Quem está dentro cai na guarda no clique seguinte, com a mensagem **"este
  ambiente foi arquivado"** — que é diferente de "você não tem acesso", e a
  pessoa merece saber qual das duas foi.
- Os tokens daquele ambiente passam a responder recusa com o mesmo motivo,
  **sem serem revogados**.

Desarquivar devolve tudo, inclusive as integrações, sem reemitir nada. Nada é
apagado. Um contrato encerrado que continua alimentando o Power BI do cliente
seria o oposto do motivo de arquivar; revogar de vez tornaria desarquivar caro
do lado do cliente, sem ganho real enquanto o estado for reversível.

### 14. Layout de armazenamento e casa do registro

Uma pasta por ambiente dentro do diretório de dados, cada uma com o mesmo par
de arquivos que existe hoje (a base em JSON e a trilha em linhas). O registro
fica na raiz do diretório, ao lado das pastas — nunca dentro de nenhuma delas.

```
data/
  registro.json
  registro-trilha.jsonl
  mccain/
    programacao.json
    auditoria.jsonl
  suzano-mucuri/
    programacao.json
    auditoria.jsonl
```

**O registro é lido e escrito por uma porta própria**, `RegistroAmbientes`,
irmã de `Repositorio` e não parte dela: listar os ambientes de um e-mail, criar,
arquivar, conceder, revogar, e os tokens na Fase 3. Implementação JSON hoje,
com a mesma escrita atômica (temporário e renomeação) e a mesma trava.

Fica fora de `Repositorio` porque `Repositorio` é **por ambiente**: pedir a um
ambiente a lista de ambientes inverte a hierarquia, e alargaria a interface que
o próprio arquivo diz manter estreita de propósito. E fica atrás de uma porta —
em vez de um módulo lendo o arquivo direto — porque a decisão 15 promete que
trocar para SharePoint continua sendo uma variável de ambiente: sem porta, os
ambientes migrariam para listas e o registro ficaria preso num arquivo local
que, num Azure Function, nem persiste entre reiniciações.

A escrita atômica continua valendo por arquivo, e continua sendo o que sustenta
o modo em rede.

### 15. A origem da persistência continua global

`PROGRAMACAO_ORIGEM` segue valendo para a instalação inteira: uma tecnologia de
persistência por implantação. O ambiente é um **espaço de nomes dentro dela**,
não uma tecnologia diferente por cliente. Na implementação sobre listas do
SharePoint, o ambiente entra como prefixo do conjunto de listas, preservando o
mapa de colunas que já está escrito e a decisão de arquitetura que promete a
troca por variável de ambiente.

### 16. A sequência de boot ganha um passo, e a escolha recarrega

> **Revisão 3 — o seletor vira a tela inicial permanente.** O passo 4 descrito
> abaixo ("com um único ambiente, seguir direto para ele") e a entrada
> automática por cookie **saem**. Toda visita nova à aplicação — navegador
> aberto, aba nova — começa no seletor, inclusive para quem tem um ambiente só.
> O cookie continua existindo e continua sendo conferido a cada requisição; o
> que ele deixa de fazer é **decidir o boot sozinho**. Ver **Revisão 3, item 3**
> no fim do documento, que também resolve o laço que essa mudança criaria.

O shell hoje confere o sentinela do Design System, consulta a sessão e, com
sessão, revela a sidebar e carrega a navegação e a view inicial. Passa a:

1. conferir o sentinela;
2. consultar a sessão — sem sessão, o portão de login, como hoje;
3. **pedir o seletor de ambientes**;
4. com um único ambiente, seguir direto para ele; com vários, aguardar a
   escolha; com nenhum, mostrar a tela que explica;
5. escolhido o ambiente, revelar a sidebar e carregar a navegação e a view
   inicial — o comportamento atual, sem alteração.

**A escolha grava o cookie e recarrega, com destino explícito.** Duas coisas que
a spec pede parecem a mesma e são opostas: o link direto é preservado através da
**primeira escolha** (história 12), e a **troca** descarta o destino e volta para
a tela inicial (história 8).

O recarregamento distingue as duas em uma linha: a primeira escolha recarrega a
URL atual — e o `location.pathname` nunca mudou, porque o seletor é um fragmento
dentro do `#app-shell` — enquanto a troca navega para `/`. Um caminho de boot só,
idêntico ao da recusa de ambiente, e a sidebar do ambiente novo se remonta
sozinha porque `/api/nav` roda de novo. Continuar o boot sem recarregar exigiria
lembrar de re-buscar a navegação à mão, e esquecer disso deixaria a sidebar com o
nome do ambiente anterior — o defeito da história 6.

### 17. O seletor é uma view e um blueprint novos

Segue o padrão da aplicação: view autocontida em `_views`, fragmento servido
por blueprint, sub-navegação e telas de guarda reaproveitadas do Design System.
Nenhuma classe visual nova é criada fora do Design System, e o contrato visual
continua valendo — fragmento não traz estilo nem script.

A administração do registro (criar, arquivar, membros, tokens) vive numa área
própria do seletor, visível apenas ao operador, e **não** entra na tela de
Configurações — que continua sendo a administração *daquele* ambiente.

### 18. A sidebar mostra o ambiente ativo

O nome do projeto que a sidebar já exibe passa a vir do ambiente ativo — do
registro, pela decisão 4. Quem tem mais de um ambiente ganha ali o caminho para
trocar. Quem tem um só não recebe o controle — o item some do DOM, como já
acontece com todo item de menu que o perfil não abre.

### 19. A guarda nomeia o e-mail e a causa

A mensagem única de hoje — "Sua sessão expirou ou o seu e-mail não tem acesso
liberado" — é verdadeira e inútil: cobre igualmente quatro causas, e três delas
são mecanismos que esta entrega escreve. A tela de recusa passa a dizer qual
e-mail o Azure entregou e qual barreira recusou:

| Causa | Mensagem |
|---|---|
| Nenhum e-mail na sessão | "A sua sessão do Azure não trouxe um endereço de e-mail." |
| E-mail fora do registro | "O e-mail *fulano@x* não consta no registro de ambientes." |
| E-mail fora do cadastro do ambiente | "O e-mail *fulano@x* não consta no cadastro de colaboradores de *Projeto McCain*." |
| Ambiente arquivado | "Este ambiente foi arquivado." |

Não vaza nada: o e-mail exibido é o da própria pessoa, e os nomes das barreiras
não revelam ambiente alheio. Isto existe porque o SSO estreia junto da Fase 1
(ver **Riscos aceitos**) e o modo de falha é previsível e mudo.

### 20. Carga inicial de demonstração e o modo demonstração

A primeira leitura de uma base inexistente hoje semeia um histórico
determinístico. Isso passa a valer **apenas** para os ambientes de demonstração,
no modo demonstração. Um ambiente criado em produção nasce com a configuração
clonada e **zero** atividades — nunca com o histórico fictício.

O modo demonstração quebra sem tratamento explícito. `com_sessao` resolve a
pessoa pelo `x-ms-client-principal`, que não existe sem provedor de identidade;
o contorno de hoje (`auth._usuario_demo` lendo o cadastro de colaboradores) deixa
de funcionar exatamente no lugar novo, porque o cadastro passou a viver dentro de
um ambiente e o seletor roda antes de qualquer ambiente existir.

Então, em modo demonstração:

- `com_sessao` devolve uma identidade fixa, `demo@timenow.local`, sempre
  operadora;
- o registro nasce com **dois** ambientes semeados — `demo-obra` e
  `demo-planta` — cada um com o histórico determinístico da `carga_inicial`;
- o seletor de perfil da sidebar continua trocando o papel **dentro** do
  ambiente escolhido.

Assim a troca de ambiente é revisável no duplo clique do `run.bat`, e o caminho
local continua parecido com o de produção justamente no passo que a entrega
adiciona.

### 21. `scripts/ambiente.py` — a administração antes da tela

Um script de linha de comando com `criar`, `conceder`, `revogar`, `arquivar`,
`desarquivar` e `listar`, chamando a porta `RegistroAmbientes` e o
`with ambiente_ativo(...)` — os mesmos caminhos que a tela da Fase 2 vai usar.

```
python scripts/ambiente.py criar --id suzano-mucuri \
    --projeto "Programação Suzano Mucuri" --cliente "Suzano S.A." --base mccain
python scripts/ambiente.py conceder --id suzano-mucuri --email fulano@timenow.com.br
```

A regra nasce e roda na Fase 1; a Fase 2 só desenha. Serve também para preparar
demonstração e para consertar o registro sem editar JSON à mão — onde um slug
digitado errado criaria uma pasta fantasma silenciosamente.

### 22. API de leitura em JSON, autenticada por token

Nova decisão de arquitetura, registrada ao lado das que já existem: **a API de
leitura devolve JSON, não fragmento**. É a terceira exceção consciente à
decisão de hipermídia, junto do health check e do payload dos gráficos, e a
justificativa é a mesma em espírito: o consumidor não é o navegador da
aplicação.

Características:

- **Espaço de rotas próprio e versionado: `/api/dados/v1/*`**, separado das
  rotas de fragmento.
- **Não passa pelo decorador de fragmento** — o gate do Alpine AJAX e a sessão
  do SWA não se aplicam. A credencial é o token, apresentado como *bearer*.
- **A configuração de rotas do Static Web Apps precisa liberar esse espaço como
  anônimo, e a entrada precisa ficar ACIMA de `/api/*` no array.** O SWA avalia
  as rotas na ordem em que aparecem e a primeira que casa vence; colocada
  abaixo, a entrada anônima nunca é alcançada e o consumidor leva um
  redirecionamento para o login do Azure AD em vez de JSON. *Esta é a mudança de
  configuração mais fácil de esquecer e a que quebra a integração em produção
  sem quebrar nada em desenvolvimento* — nem o `run.bat` nem o `dev_local.py`
  aplicam esse arquivo.
- **A palavra `dados` está no caminho de propósito**, para que nenhum endpoint
  de fragmento caia no espaço sem sessão por acidente de nome. E um teste
  automatizado varre as rotas registradas em `function_app.py` afirmando que
  nenhuma rota de fragmento começa com o prefixo — assim a porta de qualidade
  pega o erro antes do deploy, que é o único outro lugar onde ele seria pego.
- **Somente leitura.** Nenhuma rota de escrita. Escrita continua passando pelo
  fluxo com janela, validação e aprovação.
- **O token é vinculado a um ambiente** e resolve o ambiente ativo por conta
  própria, sem cookie. Um token nunca alcança outro ambiente.
- **O token não carrega identidade de pessoa**, logo o recorte por vínculo de
  fornecedor não se aplica: ele lê o ambiente inteiro. Emitir token é, na
  prática, publicar a base daquele cliente para quem tiver a credencial — e a
  tela de emissão diz isso em palavras, o que é parte da entrega e não enfeite.
  Escopo opcional por empresa fica de fora desta entrega e é barato de
  acrescentar depois, porque `dados._escopo` já aplica esse corte.

Contrato inicial:

| Recurso | O que devolve | Filtros |
|---|---|---|
| Ambiente | Identificação do ambiente do token e a semana de referência | — |
| Atividades da semana | Uma lista com item, ID exclusiva, atividade, local, empresa, encarregado, fiscal, unidade, previsto por dia, realizado por dia e noite, situação, aprovação do realizado e PPC | semana (**obrigatória**), empresa, local, situação |
| Resumo da semana | Aderência, PPC médio, totais de previsto e realizado e as faixas | semana (obrigatória) |
| Cadastros | Locais, empresas e unidades do ambiente | — |
| Geral (**Revisão 5**) | As mesmas linhas de "Atividades", com o identificador, o projeto e o cliente do ambiente repetidos em **cada linha** | semana (opcional), empresa, local, situação |

A semana é obrigatória nas atividades por decisão: sem ela, uma requisição
puxaria a base inteira do cliente. É também o teto de volume que torna
desnecessário limitar requisição (ver **Out of Scope**).

> **Revisão 4 — a semana deixa de ser obrigatória.** Decisão de produto:
> `/atividades` sem o parâmetro `semana` devolve **todas** as atividades de
> todas as semanas daquele ambiente, para consumidores que constroem o
> próprio agregado histórico (Power BI, data warehouse) em vez de um recorte
> por período. `/cadastros` já não dependia de semana. `/resumo` sem semana
> devolve um agregado geral — aderência, PPC médio, totais e faixas sobre a
> base inteira — mas **sem** a quebra "por dia": segunda-feira de semanas
> diferentes não pertence ao mesmo balde, e um agregado que as somasse mentiria.
> Com semana informada, os dois recursos continuam exatamente como descritos
> acima. Ver **Revisão 4 — o que mudou** no fim do documento — ela também
> registra o que isto muda no risco aceito nº 3 e no raciocínio contra limite
> de requisição, porque os dois dependiam da semana ser obrigatória.

### 23. Envelope fino em toda resposta

```json
{
  "ambiente": { "id": "mccain", "projeto": "Projeto McCain", "cliente": "McCain Alimentos" },
  "gerado_em": "2026-08-25T14:03:00Z",
  "dados": [ ... ]
}
```

Atende a história 60 sem repetir o identificador em cada linha, deixa lugar para
paginação e avisos futuros sem quebrar o contrato, e o `gerado_em` responde a
pergunta que todo painel faz. Custa ao consumidor um passo de expansão no Power
BI — um passo, não um obstáculo.

Pôr o ambiente num cabeçalho HTTP cumpriria a história 60 no papel e não na
prática: o conector padrão do Power BI descarta cabeçalho, então a conferência
prometida nunca chegaria a quem carregou o dado.

Versão no caminho: campo novo não quebra e não muda a versão; remover ou
renomear campo exige `v2`.

### 24. Guarda e ciclo de vida do token

Formato `tn_<prefixo>_<segredo>`, com o segredo vindo de
`secrets.token_urlsafe(32)` — cerca de 190 bits. O registro guarda o **prefixo
em claro** (rótulo para a tela e índice para a busca, evitando comparar contra
todos os tokens) e o **SHA-256 do valor inteiro**. A verificação localiza pelo
prefixo e compara os digests com `hmac.compare_digest`, em tempo constante.

**Sem sal e sem derivação lenta, de propósito, com o porquê escrito no código
para que ninguém "conserte" isso depois.** Token de máquina não é senha de
gente: sal e derivação lenta existem para proteger segredo que humano escolheu e
que cabe num dicionário. Um segredo aleatório de 190 bits não é adivinhável nem
com o hash em mãos, e pôr `bcrypt` nele significa pagar dezenas de
milissegundos em cada chamada do Power BI — mais uma dependência nova — para
comprar segurança que a entropia já deu.

O registro do token conserva: rótulo, prefixo visível, ambiente, quem emitiu,
quando, validade opcional e último uso. A emissão mostra o valor completo **uma
vez**; depois, só o prefixo. Revogar remove a capacidade na requisição seguinte.

### 25. O que a API escreve por requisição

Duas histórias pedem escrita a cada leitura — ver o último uso do token (51) e
registrar os acessos (64) — e juntas criariam um problema que nenhuma tem
sozinha: `RegistroAmbientes` em JSON lê o arquivo inteiro, modifica e reescreve
sob trava. Um refresh de Power BI chamando quatro recursos viraria quatro
reescritas completas do registro, cada uma serializando contra qualquer outra
operação — inclusive um operador concedendo acesso. O arquivo que, se corromper,
derruba todo mundo passaria a ser o mais escrito da instalação, no ritmo de uma
integração automatizada e não no de gente.

Então:

- **O acesso vira uma linha append-only** na trilha do registro — mesmo
  mecanismo barato de `auditoria.registrar`, que nunca lê o conteúdo anterior.
- **O carimbo de último uso é amortizado**: só reescreve o registro quando o
  valor guardado tiver mais de uma hora. A tela continua respondendo "usado há
  X" com precisão suficiente para decidir revogar, e o registro deixa de ser
  reescrito por requisição.

### 26. Erros e recusas mantêm o canal atual

As duas exceções que cruzam a linha do domínio continuam sendo as mesmas, com
os mesmos códigos. Ambiente inválido, inexistente, arquivado, sem pertencimento
ou divergente entre cabeçalho e cookie é uma **recusa**, e devolve o
redirecionamento da decisão 9. Na API, a recusa é uma resposta JSON com motivo
legível.

### 27. Não há migração

A revisão 1 previa converter a base existente no primeiro ambiente. Não há o que
converter: nada está publicado, e o conteúdo de `data/` é carga de demonstração.
A Fase 1 apaga e semeia no layout novo.

Isto tem uma contrapartida: a Fase 1 é também a **primeira publicação com SSO
real**. Ver **Riscos aceitos**.

---

## Testing Decisions

### O que é um bom teste aqui

Os testes existentes do domínio cobrem exatamente o que quebra em silêncio —
aritmética de semana, janela de programação, cálculo de avanço, recorte por
empresa e ordenação do fluxo — e são funções puras, sem HTTP e sem disco. Esta
entrega segue a mesma régua: **testar comportamento observável na fronteira,
nunca a forma interna**.

Concretamente: um teste afirma que um dado escrito no ambiente A não aparece na
consulta do ambiente B. Ele **não** afirma em qual pasta o arquivo caiu, nem
como a chave do cache foi montada. Se o layout de armazenamento mudar amanhã,
esse teste tem de continuar passando.

### Módulos testados — Fase 1

**Registro de ambientes** — a listagem de ambientes de um e-mail devolve só os
ativos onde ele é membro; um e-mail sem pertencimento recebe lista vazia;
arquivar tira do seletor sem apagar; desarquivar devolve; o slug é validado e
recusado quando fora do formato.

**Resolução do ambiente ativo** — cookie ausente, apontando para ambiente
inexistente, para ambiente arquivado ou para ambiente do qual a pessoa não é
membro: os quatro casos recusam. Cabeçalho divergindo do cookie recusa. Cookie
válido resolve. Este é o teste que impede o pior defeito possível da entrega:
responder com dado alheio.

**Concorrência do `ContextVar`** — duas threads dentro de dois `ambiente_ativo`
diferentes ao mesmo tempo, cada uma escrevendo e lendo a própria base. Sem este
teste, a garantia do `ContextVar` é promessa e não fato — e é justamente a
garantia que substitui o singleton.

**Falha fechada** — `repositorio.obter()` fora de qualquer `ambiente_ativo`
levanta. `auditoria.registrar` idem. Nenhum dos dois cai num ambiente padrão.

**Isolamento pela porta de persistência** — escrever atividade, cadastro,
janela, colaborador e parâmetro no ambiente A e confirmar ausência em B, para
cada um dos agregados da porta. Um caso por agregado, porque a porta tem poucos
métodos justamente para que essa cobertura caiba. **Obrigatório, não opcional.**

**Operador** — um e-mail da variável entra em ambiente onde não é colaborador,
como `admin`; entra com o perfil do cadastro quando o cadastro existe; aparece
na listagem de colaboradores marcado e não removível; conta na quantidade de
pessoas com acesso.

**Clonagem** — o ambiente novo recebe unidades e parâmetros do base; **não**
recebe atividade, solicitação, evento de trilha, local, empresa, janela nem
colaborador; identificador, nome de projeto e cliente vêm do formulário; o
criador é cadastrado como admin.

**Carga inicial** — um ambiente criado fora do modo demonstração nasce sem
atividades.

### Módulos testados — Fase 3

**Token de leitura** — token válido resolve o ambiente; token revogado,
expirado, malformado e ausente recusam; token de ambiente arquivado recusa com
motivo próprio; token do ambiente A não alcança o ambiente B; o valor não é
recuperável depois da emissão.

**API de leitura** — a resposta traz o envelope com ambiente e `gerado_em`;
pedir atividades sem semana é recusado; os filtros restringem; nenhuma rota de
escrita existe no espaço de nomes.

**Guarda do prefixo** — varredura das rotas registradas em `function_app.py`
afirmando que nenhuma rota de fragmento começa com `/api/dados/`. É o teste que
substitui a revisão humana da configuração do Static Web Apps.

### Costura de teste

A porta de persistência já expõe um ponto de troca usado pelos testes; ele
ganha a chave de ambiente. Combinado com `with ambiente_ativo(...)`, é **a única
costura necessária**: todos os testes acima rodam em memória ou em diretório
temporário, sem subir servidor e sem tocar a base real.

Os testes de fluxo HTTP completo (login, escolha de ambiente, navegação)
continuam sendo revisão de tela, como já é a prática do projeto. O caminho para
ponta a ponta já está anotado na arquitetura e não é aberto aqui.

### Porta de qualidade

As cinco etapas obrigatórias antes do commit continuam valendo integralmente e
precisam passar: lint e formatação do Python, verificação de tipos, testes de
domínio, lint de JS/CSS/HTML e o verificador do padrão Timenow. Nenhuma
supressão solta de regra: falso positivo estrutural se resolve na configuração,
com comentário explicando.

---

## Riscos aceitos

Três decisões desta spec compram simplicidade ao preço de um risco conhecido.
Estão aqui para que ninguém precise redescobri-las depois.

**1. SSO e multi-ambiente estreiam juntos.** A aplicação nunca rodou com um
provedor de identidade real: `auth._principal` tenta três claims em ordem
(`email`, `preferred_username`, `userDetails`) contra a documentação, não contra
uma resposta do tenant da Timenow. Se o Azure AD devolver o e-mail noutra claim
ou devolver UPN, o sintoma na Fase 1 será "ninguém entra em ambiente nenhum" —
com quatro mecanismos novos por trás para suspeitar primeiro. Publicar antes o
código atual teria isolado a variável; optou-se por não fazê-lo. A mitigação é a
decisão 19: a guarda nomeia o e-mail recebido e a barreira que recusou, o que
transforma uma depuração às cegas numa leitura de tela.

**2. O operador é implícito e não removível pelo cliente.** O admin de um
ambiente vê que existe gente da Timenow com acesso, e não pode tirá-la. Isso é
verdadeiro para a operação de uma consultoria que administra a carteira inteira,
e é uma concessão real de isolamento. A compensação é a visibilidade — a linha
"Operador Timenow" na tela de Colaboradores — e a trilha, que registra o que o
operador fez dentro do ambiente com o e-mail dele.

**3. O token entrega a base do cliente inteira.** É a única porta da aplicação
onde o recorte de `dados._escopo` não se aplica, porque não há pessoa atrás da
credencial. Torna impossível, por ora, o cliente dar um token à própria
contratada para ela puxar só os próprios números. A tela de emissão diz isso, e
o escopo opcional por empresa é barato de acrescentar depois.

> **Revisão 4 — o risco cresce.** Antes, "a base inteira" era limitada pela
> semana obrigatória: um token vazado entregava um período por chamada. Agora
> `/atividades` sem semana devolve o histórico completo numa chamada só, o que
> a tela de emissão passa a dizer também — não é mais só "esta credencial lê
> este cliente", é "esta credencial lê a história inteira deste cliente, de
> uma vez". A compensação de sempre — trilha e revogação em um clique —
> continua sendo a resposta, e passou a ser a única linha de defesa depois do
> vazamento, não mais uma de duas.

---

## Out of Scope

- **Escrita pela API.** A API desta entrega é somente leitura. Criar ou alterar
  atividade por HTTPS exigiria repetir fora da facade as regras de janela,
  validação e fluxo — ou tratar o token como usuário sem tela, que é uma
  decisão de processo ainda não tomada.
- **Escopo de token por empresa contratada.** Ver **Riscos aceitos**, item 3.
- **Webhook de saída** ao publicar a semana. Fica para depois de a API de
  leitura estar em uso.
- **Dashboard consolidado entre ambientes.** Um painel que some Suzano com
  Alcoa contraria o isolamento que esta entrega estabelece, e as unidades não
  são somáveis entre si. Se for pedido, é spec própria.
- **Marca e tema por ambiente** (logo, cores do cliente). O Design System é
  camada visual única e a decisão de tematizar por cliente não foi tomada.
- **RBAC customizável por ambiente.** Os perfis e a matriz de permissões
  continuam os mesmos em todos os ambientes; o que varia é quem carrega cada
  perfil.
- **Sincronização de pertencimento com grupos do Azure AD.** O pertencimento é
  mantido à mão no registro. Ver notas.
- **Ligar a persistência em SharePoint.** A aquisição de token daquela
  integração continua pendente, como já está registrado; esta entrega apenas
  não a atrapalha.
- **Cobrança, medição de uso ou limite de requisição por cliente.** O corte foi
  reexaminado depois da decisão de liberar o espaço de rotas como anônimo, e
  mantido. Força bruta de token deixou de ser preocupação com 190 bits de
  entropia — limitar requisição para impedi-la seria teatro. O que resta é token
  vazado consumindo em excesso e refresh mal configurado batendo em laço.
  **Revisão 4:** o teto deixou de ser a semana obrigatória — `/atividades` sem
  semana devolve o histórico inteiro, de propósito. O volume real de uma
  instalação com dezenas de clientes ao longo de anos ainda não sustenta abuso
  por força bruta, mas o cálculo "a semana já é o teto" não vale mais. A trilha
  registra o consumo e revogar é um clique — detecção em vez de prevenção, que
  é a troca certa nesta
  escala.
- **Mudança no fluxo da programação.** Os cinco estados, as seis transições, a
  janela e o cálculo de PPC e aderência ficam exatamente como estão.

---

## O que mudou da revisão 1

| Peça da revisão 1 | O que houve |
|---|---|
| Decisão 11 — operador não acessa telas de cliente | **Revertida.** Operador entra em todo ambiente, implicitamente (decisão 11 nova). |
| História 16 — cadastro é a lista de acesso | **Reescrita** (história 19): a lista inclui o operador, marcado e não removível. |
| Decisão 12 — clonar cadastros, janelas e colaboradores | **Encolhida** para unidades e parâmetros. Janela é registro por empresa e carrega semanas do cliente base; copiá-la vazaria fornecedor e criaria janela órfã. |
| Decisão 13 — parâmetros padrão neutros | **Dissolvida.** `projeto` e `cliente` saem dos parâmetros; o registro é dono do nome (decisão 4). |
| Decisão 18 e história 56 — migração sem perda de dado | **Removidas.** Nada publicado, nenhum dado real (decisão 27). |
| Teste "o último operador não pode ser removido" | **Removido.** Operador vem só de variável de ambiente; não há remoção. |
| Decisão 3 — ordem no decorador | **Completada** com `com_sessao`, para o que roda sem ambiente (decisão 6). |
| Decisão 8 (link direto) vs história 8 (troca volta à home) | **Conciliadas** por destino explícito no recarregamento (decisão 16). |
| Decisão 4 — "um cache de instâncias por ambiente" | **Justificada e fechada**: o cache existe pela trava, logo não pode ter descarte (decisão 8). |
| "Cookie, `SameSite=Lax`, `Secure`" | **Ganha duração** (cookie de sessão) e **cabeçalho conferido**, por causa de multi-aba (decisão 5). |
| `/api/v1/*` anônimo | Virou `/api/dados/v1/*`, **acima** de `/api/*` no array, com teste guardando o prefixo (decisão 22). |
| "Token guardado como hash" | **Especificado**: SHA-256, busca por prefixo, sem sal e sem derivação lenta, com o porquê (decisão 24). |
| Histórias 42 e 55 — último uso e registro de acesso | **Amortizadas**, para o registro não virar o arquivo mais escrito da instalação (decisão 25). |
| Entrega única | **Três fases**, com o isolamento sozinho na primeira. |

---

## Further Notes

**O risco principal desta entrega continua sendo o singleton.** A porta de
persistência sendo resolvida uma vez por processo é o que hoje garantiria o
vazamento e o que, mal convertido, garantiria o pior defeito possível: uma
requisição respondida com o dado de outro cliente por causa de estado
compartilhado. É por isso que a resolução do ambiente ativo é **por
requisição**, por isso o mecanismo é `ContextVar` e não variável de módulo, e
por isso o teste de isolamento por agregado e o teste de concorrência são
obrigatórios e não opcionais.

**A configuração de unidades de medida não precisa de mudança.** O cadastro já
aceita qualquer forma de medir produção. O que a tornaria imprestável é a base
compartilhada; separada, ela resolve o caso da bobina de papel e o do quilo de
batata sem uma linha de código nova. Vale registrar isso para que a entrega não
invente configuração que já existe.

**A ordem dos passos no decorador importa.** O ambiente precisa ser resolvido
**antes** do usuário, porque a resolução do usuário lê o cadastro de
colaboradores — que agora vive dentro do ambiente. Invertida, a ordem produz um
erro difícil de enxergar: o usuário resolvido contra o ambiente errado.

**O modo demonstração precisa continuar funcionando por duplo clique**, e ele
não sobrevive sozinho a esta entrega — ver decisão 20. Dois ambientes semeados,
não um: a troca de ambiente é a tela mais nova da entrega, e com um ambiente só
ela seria a única que ninguém consegue ver antes de publicar.

**A liberação anônima do espaço de rotas da API é o detalhe que quebra em
produção e não quebra em desenvolvimento**, porque o servidor local não aplica
a configuração de rotas do Static Web Apps. Além da ordem no array, merece
verificação explícita no deploy e uma linha na documentação de produção — e o
teste do prefixo existe porque revisão humana de arquivo de configuração não é
uma garantia.

**Pertencimento por grupo do Azure AD** é a evolução natural do registro:
trocar a lista de e-mails por um grupo por ambiente elimina a manutenção
manual. Ficou de fora porque exige decisão de identidade corporativa que não
é da alçada da aplicação, mas o registro deve ser modelado de forma a aceitar
essa origem depois sem reescrita.

**Nomenclatura.** O glossário do domínio proíbe termos ambíguos, e "ambiente"
tem um significado concorrente em infraestrutura (desenvolvimento, homologação,
produção). Como foi o termo escolhido pelo negócio, ele entra no glossário com
a definição explícita — e a documentação de infraestrutura passa a dizer
"implantação" quando quiser falar da outra coisa.

---

## Revisão 3 — o que mudou

Duas decisões tomadas depois da primeira revisão de tela da Entrega 2, com as
Entregas 1 a 3 já implementadas. Nenhuma delas contraria o objetivo das
decisões originais; as duas mudam **onde se edita**, não o que a aplicação lê.

### 1. O pertencimento tem uma edição só (decisões 2 e 4)

**Antes:** conceder acesso era ato do operador na área de administração, e a
lista de membros vivia no registro. Cadastrar a pessoa como colaboradora do
ambiente era um segundo passo, separado.

**Agora:** cadastrar a pessoa na tela de Colaboradores do ambiente **é**
conceder o acesso. A aplicação mantém o índice do registro em sincronia; o
seletor continua lendo um arquivo só no login.

**Por quê:** duas edições para o mesmo fato produziam a falha silenciosa mais
provável da operação — alguém cadastrado no ambiente que não o enxerga no
seletor, sem nenhuma mensagem explicando. É a mesma razão da decisão 4, agora
aplicada ao pertencimento.

**O que não muda:** o registro continua sendo a fonte que o seletor lê, e
continua sendo uma porta própria. Remover a pessoa do cadastro remove o acesso
na requisição seguinte. O recorte por vínculo de empresa contratada continua
valendo por cima do recorte por ambiente.

**O que fica em aberto e é resolvido na issue:** conceder acesso a alguém que
ainda não tem cadastro em ambiente nenhum continua precisando de um caminho
para o operador — é o caso do primeiro colaborador de um ambiente novo, que a
decisão 12 deixa vazio de propósito.

### 2. A tela promove operador, com a variável como piso (decisão 11)

**Antes:** operador vinha só da variável de ambiente. Trocar quem opera era
editar a variável e reiniciar a instalação.

**Agora:** a variável continua sendo o piso — sempre existe operador, mesmo com
o registro vazio ou corrompido, e ninguém a remove pela tela. Acima dela, a
área de administração promove e rebaixa operadores adicionais, guardados no
registro, ao lado da configuração de tokens.

**Por quê:** as três razões originais protegem contra registro corrompido e
escalação de privilégio, e nenhuma delas exige que a lista seja *imutável* — só
que exista um piso fora do dado.

**O que não muda:** o operador continua entrando em todo ambiente
implicitamente, continua aparecendo na tela de Colaboradores como linha marcada
e não removível pelo cliente, e continua sendo o único perfil que enxerga o
registro. Promoção e rebaixamento entram na trilha do registro.

**O que a tela precisa dizer:** a origem de cada operador — configuração ou
registro — porque só os do registro podem ser rebaixados, e uma tela que
oferece um botão inerte para os outros mente sobre o que consegue fazer.

### 3. O seletor é a tela inicial permanente (decisões 5 e 16)

**Antes:** escolhido o ambiente, o cookie levava a pessoa direto para dentro
dele em toda visita seguinte, e quem tinha um ambiente só nunca via o seletor.

**Agora:** toda visita nova à aplicação começa no seletor — navegador aberto,
aba nova —, **inclusive para quem tem um ambiente só**. A aplicação passa a ter
uma tela inicial de escolha, como um portfólio de projetos, e não uma tela de
trabalho que se abre sozinha no último cliente usado.

**Por quê:** foi decisão de produto, tomada olhando a tela. O ganho é que a
pessoa nunca começa o dia apontada para um cliente que não escolheu hoje, e a
área de administração fica a um passo de todo mundo que tem acesso a ela. O
custo está assumido abaixo.

**O laço que isso cria, e como se resolve.** Se o boot ignorar o cookie
*sempre*, a própria escolha nunca entra: ela grava o cookie e recarrega, o boot
mostra o seletor de novo, e a pessoa fica presa numa tela que não leva a lugar
nenhum. E a recusa de ambiente da decisão 9, que também recarrega, cairia no
mesmo poço.

Então "sempre" tem um limite preciso: o boot mostra o seletor **quando a visita
é nova**, e honra a escolha quando a navegação corrente é consequência dela.
A marca de entrada é **por aba** e morre com ela — aba nova e navegador novo
não a têm, e recarregar no meio do trabalho não devolve ninguém ao seletor,
porque isso perderia trabalho não salvo a cada F5.

**Três histórias mudam:**

| História | O que acontece |
|---|---|
| 3 — quem tem um ambiente só entra direto | **Revogada.** Passa a ver o seletor com uma caixa e clicar nela. O "clique sem alternativa" deixa de ser defeito e passa a ser a confirmação consciente de onde a pessoa vai trabalhar. |
| 10 — a escolha vale em aba nova | **Encolhida.** Continua valendo em recarregamento e em link direto **dentro da mesma aba**; deixa de valer em aba nova, que é o caso que a mudança existe para pegar. |
| 12 — link direto preservado através da escolha | **Preservada, e fica mais importante:** como agora todo link direto passa pelo seletor, o destino precisa sobreviver à escolha em 100% dos casos, e não só na primeira visita. |

**O que não muda:** o cookie continua sendo pista e nunca autorização,
continua conferido contra o registro a cada requisição, continua carregando o
ambiente nos dois downloads e no relatório de impressão, e o cabeçalho
continua sendo conferido contra ele.

**Efeito colateral aceito:** com toda aba nova escolhendo, a colisão de
multi-aba da decisão 5 fica mais frequente — duas abas em ambientes diferentes
compartilham um cookie só, e a aba mais velha é recusada com "esta aba está em
outro ambiente". O mecanismo que trata isso já existe e continua correto; o que
muda é que ele passa a ser exercitado com frequência, em vez de raramente.

---

## Revisão 4 — o que mudou

Uma decisão, tomada depois de a Entrega 3 estar no ar e o primeiro consumo real
da API ser tentado: quem consome não quer um período por chamada, quer o
histórico inteiro para montar o próprio agregado do lado de lá.

### A semana deixa de ser obrigatória (decisão 22)

**Antes:** `/atividades` e `/resumo` recusavam sem `semana`, porque uma
requisição sem ela puxaria a base inteira do cliente — e era exatamente essa
recusa que tornava desnecessário limitar requisição (ver **Out of Scope**).

**Agora:**

- `/atividades` sem `semana` devolve **todas** as atividades do ambiente, de
  todas as semanas. Com `semana` informada, continua exatamente como antes —
  o parâmetro deixou de ser obrigatório, não deixou de existir.
- `/resumo` sem `semana` devolve um agregado geral: aderência, PPC médio,
  totais de previsto e realizado, faixas, situação e a quebra por empresa —
  todos calculados sobre a base inteira, com as mesmas funções do domínio que
  já calculam isso por semana. **Não traz "por dia".** Um balde "segunda-feira"
  que somasse a segunda de toda semana do histórico misturaria datas
  diferentes sob um rótulo comum e mentiria sobre o que está ali. Com
  `semana` informada, `/resumo` continua trazendo o "por dia" de sempre.
- `/cadastros` e `/ambiente` não mudam — já não dependiam de semana.

**Por quê:** o consumo real (Power BI, data warehouse) monta o próprio
agregado histórico a partir do dado bruto; pedir para chamar a API uma vez por
semana e concatenar do lado de fora é fricção sem função — o servidor já tem o
dado todo, e recusar-se a entregá-lo não protege nada que a trilha e a
revogação não protejam melhor.

### O que isso custa, e por que foi aceito assim mesmo

Os dois lugares que apoiavam a decisão anterior na semana obrigatória
precisaram de ajuste, e os dois estão anotados onde vivem:

- **Risco aceito nº 3** cresce: um token vazado agora lê o histórico inteiro
  numa chamada, não um período por vez. A compensação continua a mesma —
  trilha e revogação em um clique — e passa a ser a única linha de defesa
  depois de um vazamento, não mais uma de duas.
- **O raciocínio contra limite de requisição** (Out of Scope) perde o piso
  "a semana já é o teto de volume". Ele continua de pé pelo mesmo motivo de
  sempre — força bruta contra 190 bits de entropia é teatro — mas o volume de
  uma chamada deixou de ter teto embutido pelo contrato. Se o catálogo crescer
  a um tamanho onde isso pesa (milhares de atividades por ambiente, não
  dezenas), limite de requisição volta a ser uma pergunta legítima, e não mais
  uma resposta descartada.

### O que não muda

Somente leitura continua valendo — nenhuma rota de escrita nasce aqui. O
envelope, a guarda do token, o ciclo de vida e a escrita amortizada do consumo
continuam exatamente como estão. O teste do prefixo continua a única garantia
de que nenhuma rota de fragmento cai neste espaço.

---

## Revisão 5 — recurso `geral`, atividades com o ambiente em cada linha

Decisão tomada consumindo a API de verdade pela primeira vez: quem monta um
modelo no Power BI combinando **mais de um ambiente** numa tabela só perde a
origem de cada linha assim que as respostas de `/atividades` de tokens
diferentes são empilhadas — o identificador do ambiente mora no envelope,
uma vez por chamada, não em cada atividade. Reconstruir isso à mão em cada
consulta M é fricção que a própria API pode resolver.

### O recurso novo

`/api/dados/v1/geral` — mesmas linhas de `/atividades` (mesmos campos, mesmos
filtros, mesma semana opcional da Revisão 4), com três colunas a mais em
**cada linha**: `ambiente_id`, `ambiente_projeto`, `ambiente_cliente` — os
mesmos três valores que já vêm uma vez no envelope, prefixados para não
colidir com nenhum campo existente da atividade.

**Por que um recurso novo, e não um parâmetro em `/atividades`:** os dois
formatos servem públicos diferentes. Quem consome um ambiente por vez continua
com o envelope enxuto de sempre — repetir o mesmo identificador em toda linha
seria peso sem função. Quem combina ambientes quer exatamente esse peso. Um
parâmetro (`?comAmbiente=true`) resolveria tecnicamente, mas esconderia essa
segunda forma atrás de uma flag que ninguém procura na documentação; um
caminho próprio aparece sozinho ao listar os recursos.

**O que não muda:** o token continua vinculado a **um** ambiente — a decisão 22
não muda aqui, e `geral` não é uma porta para ler vários ambientes com um
token só. O identificador que aparece em cada linha é sempre o mesmo, o do
token que autenticou a chamada; o recurso resolve o incômodo de **combinar
várias respostas do lado de fora**, não cria acesso cruzado entre ambientes.
Nenhum cálculo novo: as linhas continuam vindo de `dados.listar_atividades` /
`dados.listar_todas_atividades`, sem reimplementação.

**O que muda:** o consumidor que hoje faz um loop de tokens/ambientes e
concatena tabelas no Power Query deixa de precisar adicionar a coluna de
origem à mão em cada chamada — `geral` já a entrega pronta, e `Table.Combine`
das respostas de vários tokens produz uma tabela utilizável direto.

Ver [`docs/tasks/multi-ambiente/026-recurso-geral-com-ambiente-por-linha.md`](tasks/multi-ambiente/026-recurso-geral-com-ambiente-por-linha.md)
para o plano de implementação.
