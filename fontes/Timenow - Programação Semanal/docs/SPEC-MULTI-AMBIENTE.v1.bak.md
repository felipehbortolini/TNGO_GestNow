# Spec — Multi-ambiente, seletor de clientes e API de leitura

> Rótulo de triagem: `ready-for-agent`

---

## Problem Statement

A Programação Semanal de Serviços foi construída para um cliente e hoje serve
a um cliente por instalação. Toda a base vive num único arquivo de programação,
e a porta de persistência é resolvida **uma vez por processo** — de modo que
todo mundo que entra na aplicação lê e escreve o mesmo dado.

Isso significa que atender Suzano, Alcoa e McCain exige hoje **três
implantações separadas**: três publicações, três conjuntos de variáveis, três
telas de configuração para manter em sincronia e três versões do mesmo código
divergindo com o tempo. Cada cliente novo do portfólio multiplica o custo de
manutenção em vez de diluí-lo.

A configuração já é flexível o bastante para os segmentos: a unidade de medida
é um cadastro de apoio, e quem produz bobina de papel cadastra `bobina` do
mesmo jeito que quem produz batata cadastra `kg`. **O que falta não é a
configuração — é o isolamento.** Como existe uma base só, o cadastro de
unidades da mineração aparece para a produção alimentícia, os locais e frentes
de um cliente aparecem no filtro do outro, e o cadastro de colaboradores — que
é a própria autenticação da aplicação — é compartilhado entre empresas que não
podem se enxergar.

Além disso, os parâmetros padrão do projeto nascem com o nome de um cliente
específico escrito no código, o que denuncia a premissa de instância única em
qualquer ambiente novo.

Por fim, os dados só saem da aplicação por planilha ou relatório em papel. Não
há como um Power BI, um data warehouse ou um sistema do cliente consumir a
programação por requisição HTTPS — o que impede a ferramenta de participar do
ecossistema de dados de quem a contrata.

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

Quem tem acesso a um ambiente só é decidido em duas camadas:

1. **Registro de ambientes** (global, acima de todos os clientes) — diz quais
   ambientes existem e quais e-mails podem entrar em cada um. É o que monta a
   tela de seleção.
2. **Cadastro de colaboradores** (dentro de cada ambiente, como hoje) — diz com
   qual perfil a pessoa entra ali. A regra que já vale continua valendo: um
   e-mail fora do cadastro não entra, com ou sem sessão do Azure.

Um novo perfil global — **operador** — administra o registro: cria ambientes,
concede e revoga acesso, emite e revoga tokens. Ele vive acima dos clientes e é
a única coisa que enxerga todos. O perfil `admin` de hoje continua sendo o
administrador **daquele** ambiente e não ganha visão dos outros.

Criar um ambiente novo parte de um existente: a configuração é copiada
(cadastros, parâmetros, janelas, colaboradores) e a programação nasce vazia. Um
cliente novo do portfólio abre já usável, com as unidades de medida e os perfis
prontos para ajuste, e sem um único dado do cliente que serviu de base.

E os dados passam a sair por HTTPS: uma **API de leitura em JSON**, autenticada
por **token por ambiente**, entrega a programação da semana, o resumo e os
indicadores para quem for consumi-los depois — Power BI, data warehouse ou o
sistema do cliente.

---

## User Stories

### Seleção de ambiente

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
    recarregar a página ou abrir um link direto, para não reescolher a cada
    navegação.
11. Como usuário, quero que exportar a planilha e imprimir o relatório tragam o
    dado do ambiente ativo, porque download é navegação normal do navegador e
    não pode perder o contexto.

### Isolamento de dados

12. Como cliente Suzano, quero que minha programação não seja visível a nenhum
    usuário de outro cliente, para que meu dado de produção não vaze.
13. Como administrador de um ambiente, quero que meu cadastro de locais e
    frentes contenha só os meus, para que o filtro da matriz seja útil.
14. Como administrador de um ambiente de papel e celulose, quero cadastrar
    `bobina` e `rolo` como unidades sem que elas apareçam para o ambiente de
    produção alimentícia.
15. Como administrador de um ambiente de mineração, quero cadastrar minhas
    empresas contratadas sem que elas apareçam na janela de programação de
    outro cliente.
16. Como administrador de um ambiente, quero que meu cadastro de colaboradores
    contenha só as pessoas do meu projeto, porque ele é a lista de acesso.
17. Como auditor, quero que a trilha de auditoria de um ambiente registre só os
    eventos daquele ambiente, para que a trilha sirva de prova.
18. Como planejador, quero que a numeração de item e a ID exclusiva sejam
    únicas dentro do meu ambiente e da minha semana, sem colidir com as de
    outro cliente.
19. Como fornecedor com vínculo de empresa contratada, quero continuar vendo
    apenas a minha empresa dentro do ambiente, porque o recorte por vínculo
    continua valendo por cima do recorte por ambiente.
20. Como responsável pelo produto, quero que um erro de configuração jamais
    faça uma requisição cair no ambiente errado — prefiro a requisição ser
    recusada a ela ser respondida com dado alheio.

### Administração de ambientes

21. Como operador, quero uma tela que liste todos os ambientes existentes, com
    cliente, situação e quantidade de pessoas com acesso.
22. Como operador, quero criar um ambiente novo informando o nome do projeto e
    o nome do cliente, para atender um cliente novo do portfólio sem publicar
    outra instalação.
23. Como operador, quero escolher um ambiente existente como base ao criar um
    novo, para não configurar tudo do zero.
24. Como operador, quero que a criação copie cadastros, parâmetros, janelas e
    colaboradores do ambiente base, porque é isso que faz o ambiente novo
    nascer usável.
25. Como operador, quero que a criação **não** copie nenhuma atividade,
    solicitação de governança ou trilha, para que dado de um cliente nunca
    entre no ambiente de outro.
26. Como operador, quero que a tela diga explicitamente o que será copiado e o
    que não será, antes de eu confirmar.
27. Como operador, quero que o nome do projeto e do cliente do ambiente novo
    venham do formulário e não do ambiente base, para não herdar o nome errado.
28. Como operador, quero conceder acesso a um ambiente informando o e-mail da
    pessoa, para liberar quem precisa entrar.
29. Como operador, quero revogar o acesso de alguém a um ambiente e que isso
    valha na requisição seguinte, sem esperar a sessão expirar.
30. Como operador, quero ver, por ambiente, a lista de quem tem acesso, para
    revisar periodicamente quem enxerga o quê.
31. Como operador, quero arquivar um ambiente encerrado para que ele suma da
    tela de seleção sem que o dado seja apagado.
32. Como operador, quero que arquivar um ambiente não apague nada, para que o
    histórico do contrato encerrado continue recuperável.
33. Como operador, quero que a criação do ambiente me cadastre automaticamente
    como administrador dele, para conseguir concluir a configuração inicial.
34. Como operador, quero que toda criação, arquivamento, concessão e revogação
    fiquem registradas numa trilha própria do registro de ambientes.
35. Como administrador de um ambiente, quero continuar administrando apenas o
    meu — cadastros, janelas, colaboradores — sem enxergar nem tocar nos
    outros.
36. Como administrador de um ambiente, quero que a tela de configurações mostre
    de qual ambiente ela está falando, para não configurar o cliente errado.

### API de leitura

37. Como analista de dados do cliente, quero consumir a programação por
    requisição HTTPS em JSON, para alimentar meu Power BI sem exportar planilha
    à mão.
38. Como operador, quero emitir um token de leitura vinculado a um ambiente,
    para liberar o consumo do dado daquele cliente.
39. Como operador, quero ver o token completo apenas uma vez no momento da
    emissão, para que ele não fique legível na tela depois.
40. Como operador, quero identificar cada token por um rótulo e pelos primeiros
    caracteres, para saber qual integração usa qual.
41. Como operador, quero revogar um token e que ele pare de funcionar na
    requisição seguinte.
42. Como operador, quero ver quando cada token foi usado pela última vez, para
    revogar os que ninguém consome.
43. Como operador, quero definir uma data de validade opcional para o token,
    para que uma integração temporária expire sozinha.
44. Como consumidor da API, quero receber a lista de atividades de uma semana
    em JSON, com previsto e realizado por dia, para reproduzir o cálculo no meu
    lado.
45. Como consumidor da API, quero receber o resumo da semana com aderência, PPC
    e as faixas, para não reimplementar o cálculo do domínio.
46. Como consumidor da API, quero filtrar por semana, empresa, local e situação,
    para trazer só o que me interessa.
47. Como consumidor da API, quero receber a unidade de medida junto de cada
    atividade, porque as unidades não são somáveis entre si.
48. Como consumidor da API, quero receber a lista de cadastros do ambiente
    (locais, empresas, unidades), para montar meus próprios filtros.
49. Como consumidor da API, quero uma mensagem de erro clara quando meu token é
    inválido, expirado ou revogado, para saber o que resolver.
50. Como consumidor da API, quero que meu token nunca me dê acesso a outro
    ambiente, mesmo que eu descubra o identificador dele.
51. Como consumidor da API, quero que a resposta traga o identificador do
    ambiente, para conferir de onde veio o dado que carreguei.
52. Como responsável pela segurança, quero que a API de leitura não permita
    nenhuma escrita, para que o fluxo de aprovação nunca seja contornado por
    integração.
53. Como responsável pela segurança, quero que os tokens não sejam armazenados
    em texto puro, para que o vazamento do arquivo de configuração não vire
    vazamento de acesso.
54. Como responsável pela segurança, quero que a semana seja obrigatória ao
    pedir atividades, para que ninguém puxe a base inteira numa requisição.
55. Como operador, quero que os acessos pela API fiquem registrados, para
    auditar o consumo do dado do cliente.

### Migração e operação

56. Como responsável pelo produto, quero que a base atual vire o primeiro
    ambiente sem perda de dado, para que a mudança não custe uma reimportação.
57. Como responsável pelo produto, quero que os parâmetros padrão deixem de
    citar um cliente específico, para que um ambiente novo não nasça com o nome
    de outro.
58. Como desenvolvedor, quero rodar a aplicação localmente com mais de um
    ambiente de demonstração, para revisar a troca de ambiente sem publicar.
59. Como desenvolvedor, quero que a carga inicial de demonstração popule apenas
    o ambiente de demonstração, para que um ambiente novo em produção nunca
    nasça com atividades fictícias.
60. Como desenvolvedor, quero que as telas, blueprints e regras de domínio
    existentes não precisem saber que existem ambientes, para que a mudança não
    se espalhe pelo código todo.
61. Como desenvolvedor, quero uma forma de escrever teste que fixe o ambiente
    ativo, para testar isolamento sem subir servidor.
62. Como responsável pelo produto, quero que trocar a porta de persistência
    para o SharePoint continue sendo uma variável de ambiente depois desta
    mudança, para não perder a decisão de arquitetura que já existe.

---

## Implementation Decisions

### 1. Ambiente vira conceito de primeira classe

Entra no glossário do domínio, junto com os termos que ele traz:

| Termo | Significado |
|---|---|
| **Ambiente** | A instância de dados de um cliente. Tem identificador estável, nome de projeto, nome de cliente e situação (ativo ou arquivado). |
| **Registro de ambientes** | O cadastro global, acima de todos os ambientes: quais existem e quem pode entrar em cada um. |
| **Ambiente ativo** | O ambiente resolvido para a requisição corrente. |
| **Membro do ambiente** | E-mail com direito de entrar. Decide o que aparece no seletor — não decide o perfil. |
| **Operador** | Perfil global da Timenow que administra o registro de ambientes. |
| **Seletor de ambientes** | A primeira tela depois do SSO. |
| **Token de leitura** | Credencial da API JSON, vinculada a um ambiente e somente leitura. |

### 2. Duas camadas de acesso, e as duas são obrigatórias

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

### 3. O ambiente ativo viaja em cookie e é validado no decorador de endpoint

O seletor grava um cookie ao escolher o ambiente. O decorador `com_usuario` —
a costura única por onde toda requisição de fragmento já passa — ganha um
quarto passo, antes da resolução do usuário: **resolver e validar o ambiente
ativo**.

A ordem passa a ser: gate do fragmento → ambiente ativo → usuário → permissão.

O cookie é uma **pista, nunca uma autorização**. Em toda requisição ele é
conferido contra o registro: o ambiente existe, está ativo, e o e-mail
autenticado é membro dele. Falhando qualquer uma, a resposta é a tela de
guarda que já existe, apontando de volta para o seletor.

Atributos do cookie: `HttpOnly`, `SameSite=Lax`, `Secure` fora do modo local,
e caminho raiz. Há precedente no código: o modo demonstração já lê um cookie
para trocar de perfil.

**Por que cookie e não cabeçalho:** os dois downloads (planilha da semana e
modelo em Excel) e o relatório para impressão são navegações reais do
navegador, sem o cabeçalho do Alpine AJAX. Um esquema baseado só em cabeçalho
perderia o ambiente exatamente neles. O cookie viaja em ambos os casos.

**Por que não prefixo de rota nem subdomínio:** o prefixo tocaria as cerca de
quarenta rotas dos dez blueprints, o servidor de desenvolvimento local, a
configuração de rotas do Static Web Apps e todos os alvos e links das views.
O subdomínio exigiria DNS e certificado por cliente e mataria a troca de
ambiente em tela. Ambos espalham o custo; o cookie o concentra em um lugar.

### 4. A porta de persistência deixa de ser um singleton de processo

Hoje a porta é construída uma vez e guardada num módulo. Passa a ser
**resolvida por ambiente ativo**, com um cache de instâncias por ambiente
dentro do processo. Nenhuma chamada da facade de domínio muda de assinatura —
ela continua pedindo "a porta" e recebendo a do ambiente corrente.

Essa é a **segunda metade da costura única**: o decorador publica o ambiente
ativo; a porta o lê. Entre os dois, a facade de domínio, os dez blueprints, os
templates e as views seguem sem saber que ambientes existem.

O ponto de troca usado pelos testes ganha a mesma chave: passa a ser possível
fixar a porta **de um ambiente específico**, e é isso que permite testar
isolamento sem servidor.

### 5. A trilha de auditoria é por ambiente

A trilha resolve seu arquivo pelo mesmo diretório de dados, então ganha a mesma
chave de ambiente. O registro de ambientes tem **trilha própria**, separada:
criação, arquivamento, concessão e revogação de acesso, emissão e revogação de
token são eventos do registro, não de nenhum cliente.

### 6. Layout de armazenamento

Uma pasta por ambiente dentro do diretório de dados, cada uma com o mesmo par
de arquivos que existe hoje (a base em JSON e a trilha em linhas). O registro
de ambientes fica na raiz do diretório, ao lado das pastas — nunca dentro de
nenhuma delas.

A escrita atômica que já existe (arquivo temporário e renomeação) continua
valendo por arquivo, e continua sendo o que sustenta o modo em rede.

### 7. A origem da persistência continua global

`PROGRAMACAO_ORIGEM` segue valendo para a instalação inteira: uma tecnologia de
persistência por implantação. O ambiente é um **espaço de nomes dentro dela**,
não uma tecnologia diferente por cliente. Na implementação sobre listas do
SharePoint, o ambiente entra como prefixo do conjunto de listas, preservando o
mapa de colunas que já está escrito e a decisão de arquitetura que promete a
troca por variável de ambiente.

### 8. A sequência de boot ganha um passo

O shell hoje confere o sentinela do Design System, consulta a sessão e, com
sessão, revela a sidebar e carrega a navegação e a view inicial. Passa a:

1. conferir o sentinela;
2. consultar a sessão — sem sessão, o portão de login, como hoje;
3. **pedir o seletor de ambientes**;
4. com um único ambiente, seguir direto para ele; com vários, aguardar a
   escolha; com nenhum, mostrar a tela que explica;
5. escolhido o ambiente, revelar a sidebar e carregar a navegação e a view
   inicial — o comportamento atual, sem alteração.

O link direto (deep link) é preservado através da escolha: quem abre um
endereço específico e precisa escolher ambiente vai para lá depois da escolha.

### 9. O seletor é uma view e um blueprint novos

Segue o padrão da aplicação: view autocontida em `_views`, fragmento servido
por blueprint, sub-navegação e telas de guarda reaproveitadas do Design System.
Nenhuma classe visual nova é criada fora do Design System, e o contrato visual
continua valendo — fragmento não traz estilo nem script.

A administração do registro (criar, arquivar, membros, tokens) vive numa área
própria do seletor, visível apenas ao operador, e **não** entra na tela de
Configurações — que continua sendo a administração *daquele* ambiente.

### 10. A sidebar mostra o ambiente ativo

O nome do projeto que a sidebar já exibe passa a vir do ambiente ativo. Quem
tem mais de um ambiente ganha ali o caminho para trocar. Quem tem um só não
recebe o controle — o item some do DOM, como já acontece com todo item de menu
que o perfil não abre.

### 11. Perfil operador

Entra na matriz de permissões como perfil **global**, morando no registro de
ambientes e não em nenhum cadastro de colaboradores. As permissões novas
cobrem: administrar o registro, conceder e revogar acesso, emitir e revogar
token.

Ser operador **não** dá, por si, acesso às telas de um cliente. Para abrir a
programação da Suzano, o operador precisa também ser colaborador de lá. A
criação de um ambiente cadastra automaticamente quem criou como administrador
dele — é o que permite concluir a configuração inicial sem uma exceção na
regra.

### 12. Clonagem na criação

Copiado do ambiente base: cadastros de apoio (locais, empresas, unidades),
parâmetros do projeto, janelas de programação e cadastro de colaboradores.

Nunca copiado: atividades, realizado, solicitações de governança, trilha de
auditoria, sequência e contagem de itens por semana.

Sobrescrito pelo formulário: nome do projeto e nome do cliente.

A tela enuncia essa divisão antes da confirmação — copiar configuração de um
cliente para outro é uma decisão consciente e precisa parecer uma.

### 13. Parâmetros padrão neutros

Os valores padrão do projeto deixam de citar um cliente específico. As metas
numéricas e a regra de justificativa de desvio permanecem como estão; o que sai
é o nome próprio.

### 14. Carga inicial de demonstração fica restrita ao ambiente de demonstração

A primeira leitura de uma base inexistente hoje semeia um histórico
determinístico. Isso passa a valer **apenas** para o ambiente de demonstração,
no modo demonstração. Um ambiente criado em produção nasce com a configuração
clonada e **zero** atividades — nunca com o histórico fictício.

### 15. API de leitura em JSON, autenticada por token

Nova decisão de arquitetura, registrada ao lado das que já existem: **a API de
leitura devolve JSON, não fragmento**. É a terceira exceção consciente à
decisão de hipermídia, junto do health check e do payload dos gráficos, e a
justificativa é a mesma em espírito: o consumidor não é o navegador da
aplicação.

Características:

- **Espaço de rotas próprio e versionado**, separado das rotas de fragmento.
- **Não passa pelo decorador de fragmento** — o gate do Alpine AJAX e a sessão
  do SWA não se aplicam. A credencial é o token, apresentado como *bearer*.
- **A configuração de rotas do Static Web Apps precisa liberar esse espaço como
  anônimo**, porque hoje `/api/*` exige o papel `authenticated` e barraria o
  consumidor antes de a aplicação ver a requisição. A proteção passa a ser o
  token, verificado dentro da aplicação. *Esta é a mudança de configuração mais
  fácil de esquecer e a que quebra a integração em produção sem quebrar nada em
  desenvolvimento.*
- **Somente leitura.** Nenhuma rota de escrita. Escrita continua passando pelo
  fluxo com janela, validação e aprovação.
- **O token é vinculado a um ambiente** e resolve o ambiente ativo por conta
  própria, sem cookie. Um token nunca alcança outro ambiente.
- **O token não carrega identidade de pessoa**, logo o recorte por vínculo de
  fornecedor não se aplica: ele lê o ambiente inteiro. Emitir token é, na
  prática, publicar a base daquele cliente para quem tiver a credencial — a
  tela de emissão diz isso.

Contrato inicial (todas as respostas trazem o identificador do ambiente):

| Recurso | O que devolve | Filtros |
|---|---|---|
| Ambiente | Identificação do ambiente do token e a semana de referência | — |
| Atividades da semana | Uma lista com item, ID exclusiva, atividade, local, empresa, encarregado, fiscal, unidade, previsto por dia, realizado por dia e noite, situação, aprovação do realizado e PPC | semana (**obrigatória**), empresa, local, situação |
| Resumo da semana | Aderência, PPC médio, totais de previsto e realizado e as faixas | semana (obrigatória) |
| Cadastros | Locais, empresas e unidades do ambiente | — |

A semana é obrigatória nas atividades por decisão: sem ela, uma requisição
puxaria a base inteira do cliente.

### 16. Guarda e ciclo de vida do token

Guardado como **hash**, nunca em texto puro. O registro do token conserva:
rótulo, prefixo visível, ambiente, quem emitiu, quando, validade opcional e
último uso. A emissão mostra o valor completo **uma vez**; depois, só o
prefixo.

Revogar remove a capacidade na requisição seguinte. Cada uso atualiza o
carimbo de último uso, e o acesso é registrado na trilha do registro de
ambientes.

### 17. Erros e recusas mantêm o canal atual

As duas exceções que cruzam a linha do domínio continuam sendo as mesmas, com
os mesmos códigos. Ambiente inválido, inexistente, arquivado ou sem
pertencimento é uma **recusa**, e devolve a tela de guarda apontando para o
seletor — não uma tela em branco. Na API, a recusa é uma resposta JSON com
motivo legível.

### 18. Migração da base atual

A base existente vira o primeiro ambiente, movida para dentro da pasta dele,
com o registro de ambientes criado apontando para ela e os colaboradores
atuais promovidos a membros. É um movimento único, não uma reescrita de
formato: o conteúdo do arquivo não muda.

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

### Módulos testados

**Registro de ambientes** — a listagem de ambientes de um e-mail devolve só os
ativos onde ele é membro; um e-mail sem pertencimento recebe lista vazia;
arquivar tira do seletor sem apagar; o último operador não pode ser removido
(mesmo espírito da regra que já protege o último administrador).

**Resolução do ambiente ativo** — cookie ausente, apontando para ambiente
inexistente, para ambiente arquivado ou para ambiente do qual a pessoa não é
membro: os quatro casos recusam. Cookie válido resolve. Este é o teste que
impede o pior defeito possível da entrega: responder com dado alheio.

**Isolamento pela porta de persistência** — escrever atividade, cadastro,
janela, colaborador e parâmetro no ambiente A e confirmar ausência em B, para
cada um dos agregados da porta. Um caso por agregado, porque a porta tem poucos
métodos justamente para que essa cobertura caiba.

**Clonagem** — o ambiente novo recebe cadastros, parâmetros, janelas e
colaboradores do base; não recebe nenhuma atividade, solicitação nem evento de
trilha; nome de projeto e cliente vêm do formulário e não do base.

**Token de leitura** — token válido resolve o ambiente; token revogado,
expirado, malformado e ausente recusam; token do ambiente A não alcança o
ambiente B; o valor não é recuperável depois da emissão.

**API de leitura** — a resposta traz o ambiente do token; pedir atividades sem
semana é recusado; os filtros restringem; nenhuma rota de escrita existe no
espaço de nomes.

**Carga inicial** — um ambiente criado fora do modo demonstração nasce sem
atividades.

### Costura de teste

A porta de persistência já expõe um ponto de troca usado pelos testes; ele
ganha a chave de ambiente e continua sendo **a única costura necessária**. Com
ela, todos os testes acima rodam em memória ou em diretório temporário, sem
subir servidor e sem tocar a base real.

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

## Out of Scope

- **Escrita pela API.** A API desta entrega é somente leitura. Criar ou alterar
  atividade por HTTPS exigiria repetir fora da facade as regras de janela,
  validação e fluxo — ou tratar o token como usuário sem tela, que é uma
  decisão de processo ainda não tomada.
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
- **Cobrança, medição de uso ou limite de requisição por cliente.**
- **Mudança no fluxo da programação.** Os cinco estados, as seis transições, a
  janela e o cálculo de PPC e aderência ficam exatamente como estão.

---

## Further Notes

**O risco principal desta entrega é o singleton.** A porta de persistência
sendo resolvida uma vez por processo é o que hoje garante o vazamento e o que,
mal convertido, garantiria o pior defeito possível: uma requisição respondida
com o dado de outro cliente por causa de cache compartilhado entre ambientes.
É por isso que a resolução do ambiente ativo tem de ser **por requisição**, e
por isso o teste de isolamento por agregado é obrigatório e não opcional.

**A configuração de unidades de medida não precisa de mudança.** O cadastro já
aceita qualquer forma de medir produção. O que a torna imprestável hoje é a
base compartilhada; separada, ela resolve o caso da bobina de papel e o do
quilo de batata sem uma linha de código nova. Vale registrar isso para que a
entrega não invente configuração que já existe.

**A ordem dos passos no decorador importa.** O ambiente precisa ser resolvido
**antes** do usuário, porque a resolução do usuário lê o cadastro de
colaboradores — que agora vive dentro do ambiente. Invertida, a ordem produz um
erro difícil de enxergar: o usuário resolvido contra o ambiente errado.

**O modo demonstração precisa continuar funcionando por duplo clique.** Ele
entra sem provedor de identidade, pelo cadastro de colaboradores, e oferece o
seletor de perfil. Com ambientes, ele passa a ter um ambiente de demonstração
e o seletor de ambiente aparece como aparecerá em produção — de preferência com
dois ambientes semeados, para que a troca seja revisável localmente.

**A liberação anônima do espaço de rotas da API é o detalhe que quebra em
produção e não quebra em desenvolvimento**, porque o servidor local não aplica
a configuração de rotas do Static Web Apps. Merece verificação explícita no
deploy e uma linha na documentação de produção.

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
