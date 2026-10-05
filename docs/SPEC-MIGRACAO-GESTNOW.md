# Spec: Migração do Gestão Integrada AMT para o Timenow GestNow

> Rótulo de triagem: `ready-for-agent`
> Revisão 2.1, 05/10/2026. Fonte da verdade da migração. Se uma tarefa derivada
> e esta spec discordarem, **a spec vence**.
>
> A revisão 2 incorpora as 29 decisões tomadas com o dono do produto na sessão
> de discussão de 05/10/2026 (base Postgres, prontidão para o Azure, anexos
> reais, controle de edição simultânea, idioma do código, perfis em dois eixos,
> configuração da Programação Semanal por projeto). A revisão 2.1 quebra a spec
> em 93 issues (seção "Related Issues"), ajusta a ordem de execução da D15 e
> registra as decisões Q30 a Q35, que permitem executar tudo sem paradas. O
> registro está em "Histórico de decisões", no fim do documento.

---

## Problem Statement

O **Gestão Integrada AMT** (pasta `Sistema`) é um protótipo navegável de gestão
de portfólio de projetos de capital: 8 módulos (Central de Ações, Planejamento,
Gestão Financeira, Suprimentos, Riscos, Qualidade, HSE e Governança), mais
Início, Relatório gerencial e Configurações, num total de 45 telas. Ele resolve
o problema de negócio, mas foi construído sem backend:

* Os dados são fictícios, vivem em arquivos `.js` e o que o usuário grava some
  ao fechar a aba (`sessionStorage`). Não há como duas pessoas trabalharem no
  mesmo projeto.
* A **data de referência é fixa em 25/09/2026**. Status, atrasos, folgas, dias
  sem acidente, SPI e CPI são calculados nessa data, para sempre. Nenhum
  indicador acompanha o tempo real.
* Parte dos números é lançada à mão em vez de calculada: o real da Curva S
  física e o avanço por área têm lançamento próprio e só "conciliam" com a EAP;
  a evolução mensal do score de riscos é uma série gravada no mock.
* Toda regra de negócio, permissão e segregação de funções roda no navegador
  (`api.js`, 6.400 linhas). Qualquer pessoa com o console aberto aprova a
  própria SM.
* O visual segue um design system próprio (paleta do PDF de cores, Chart.js,
  botões pílula), diferente do **Padrão de Desenvolvimento Timenow**, que é
  obrigatório para todo app da empresa.
* A estrutura de pastas foi gerada por script (`_dev/telas.py`) e mistura
  todos os módulos num `api.js` e num `en.js` gigantes. Sem uma IA, ninguém
  sabe onde mexer para mudar uma regra.
* A tela de Programação Semanal do protótipo é uma versão reduzida de um
  aplicativo que **já existe e está mais maduro** (`Timenow - Programação
  Semanal`), com janela de programação, turnos dia e noite, fiscal, pedidos de
  alteração, governança, dashboard e planilha. Hoje são duas implementações do
  mesmo assunto, divergindo.
* Os gráficos não usam a coletânea oficial de visuais da empresa
  (`Graficos HTML`).

## Solution

Construir o **Timenow GestNow**, inteiramente dentro da pasta `Timenow -
GestNow`, como aplicação real sobre o Padrão de Desenvolvimento Timenow
(Azure Static Web Apps, Azure Functions V4 em Python, Alpine.js com Alpine
AJAX, Jinja2 e o Timenow Design System), preservando **todas** as telas,
fluxos, regras, integrações entre módulos, impressões, relatórios e
exportações Excel e PDF do protótipo.

Do ponto de vista de quem usa:

* No Azure, entra com a conta Microsoft e só passa quem está no cadastro de
  Colaboradores. O que grava fica gravado para todos, num banco Postgres, com
  trilha de auditoria. Se outra pessoa alterou o mesmo registro antes, é
  avisada em vez de sobrescrever o trabalho dela.
* Anexos e evidências são arquivos de verdade, guardados e baixáveis por quem
  tem permissão, e não mais só um nome.
* Todo número na tela é calculado **na hora**, a partir dos registros que
  existem, com a **data de hoje** como referência. Nada é digitado como
  resultado e nada fica congelado.
* A barra de navegação lateral está à esquerda em **todas** as telas, sempre
  visível, inclusive nas telas de detalhe e no relatório gerencial.
* Toda tela abre já com o visual correto na primeira execução: cada página
  HTML nasce com a sua folha de estilo e o seu script, carregados pelo shell.
* Os gráficos são os da coletânea `Graficos HTML`, recoloridos pelos tokens do
  Design System; o que a coletânea não tem é construído no mesmo padrão
  visual.
* O módulo Programação Semanal **é** o aplicativo `Timenow - Programação
  Semanal`, adaptado para dentro do GestNow (projeto e portfólio, cadastros e
  login do GestNow). Nada é reinventado.

Do ponto de vista de quem mantém:

* Cada módulo é uma pasta autocontida no front e no backend, com um
  `LEIA-ME.md` que diz o que cada arquivo faz e **onde mexer para cada tipo de
  alteração**. Um mapa geral responde "quero mudar X, abro Y" sem precisar de
  IA.
* A porta de qualidade do Padrão (`verificar.mjs`) passa, acrescida das
  verificações que garantem as regras desta spec.
* Localmente, o `run.bat` sobe o app em modo demonstração sobre um Postgres
  instalado na máquina. O mesmo código já nasce pronto para ser publicado no
  Azure com SSO, Postgres e armazenamento de arquivos, seguindo um guia passo
  a passo.

Ao final, as pastas de origem (`Sistema`, `Padrao Desenvolvimento`, `Graficos
HTML` e `Timenow - Programação Semanal`) são excluídas, restando só `Timenow -
GestNow`, que já terá absorvido tudo o que precisa delas. Antes disso, as
pastas ocultas de ferramenta da raiz (`.claude`, `.agents`) e o
`skills-lock.json` passam para dentro do `Timenow - GestNow`.

---

## User Stories

### Acesso, navegação e escopo

1. Como colaborador, cliente ou fornecedor, quero entrar com a minha conta
   Microsoft (corporativa ou pessoal), para não ter mais uma senha.
2. Como administrador, quero que só e-mails cadastrados em Colaboradores
   entrem, para que ter conta na empresa não baste para ver dados de projeto.
3. Como pessoa sem cadastro, quero ver uma tela de acesso negado que explica a
   quem pedir liberação, para não ficar sem saída.
4. Como avaliador do sistema rodando localmente, quero um modo demonstração
   com seletor de perfil na barra lateral, para ver cada tela como cada papel a
   vê. O modo local serve só para demonstração e desenvolvimento; uso real é
   no Azure.
5. Como usuário, quero a barra de navegação sempre à esquerda em todas as
   telas, para nunca perder o caminho de volta.
6. Como usuário em tela estreita, quero que a barra lateral se compacte num
   trilho de ícones em vez de sumir, para continuar navegando com um toque.
7. Como usuário, quero ver na barra lateral os 8 módulos, o Início e (se eu
   for Gestor ou Admin) as Configurações, com o item ativo destacado, para
   saber onde estou.
8. Como fornecedor, quero ver na barra lateral só a Programação Semanal, e
   nela só a minha empresa, para não acessar o que não é meu.
9. Como cliente, quero ver os módulos conforme o meu perfil geral, para
   acompanhar o projeto sem depender de relatório enviado.
10. Como usuário, quero as telas do módulo como abas no topo da página, para
    trocar de tela sem voltar ao menu.
11. Como usuário numa tela de detalhe (ata, contrato, ficha do risco, SM),
    quero o módulo de origem destacado na barra lateral e um botão Voltar, para
    retornar à lista.
12. Como gestor de portfólio, quero escolher entre "Portfólio" e um projeto
    específico num seletor sempre visível, para que todas as telas passem a
    mostrar aquele escopo.
13. Como usuário, quero que o escopo escolhido fique na URL e seja lembrado,
    para compartilhar um link e reabrir no mesmo contexto.
14. Como usuário, quero recarregar a página numa URL profunda e cair na mesma
    tela, para usar favoritos.
15. Como usuário no Portfólio, quero que os botões de inclusão me peçam o
    projeto antes de abrir o formulário, para que todo registro pertença a um
    projeto.
16. Como usuário no Portfólio, quero uma coluna Projeto em todas as listas
    consolidadas e nas exportações, para saber de onde vem cada linha.
17. Como usuário, quero alternar o idioma entre PT e EN, para apresentar o
    sistema a públicos que não leem português.
18. Como usuário, quero passar o mouse sobre uma sigla (SPI, CPI, VME, RNC,
    TF, S39) e ver o significado, para ler os indicadores sem glossário à mão.
19. Como usuário sem permissão para uma tela, quero ver a tela de acesso
    negado do Design System, para entender por que não vejo o conteúdo.
20. Como usuário, quero que toda tela mostre estado de carregando, vazio de
    origem, vazio por filtro, erro e sem permissão, para nunca encarar uma tela
    em branco sem explicação.

### Dados vivos e cálculos reais

21. Como gestor, quero que a data de referência de todos os cálculos seja a
    data de hoje, para que atraso, folga e dias sem acidente andem com o
    calendário.
22. Como gestor, quero que SPI, CPI, VAC, severidade, VME, folga, taxas de HSE,
    PPC e aderência sejam recalculados a cada consulta a partir dos registros,
    para nunca decidir com número velho.
23. Como auditor, quero que nenhum indicador seja digitado como resultado,
    para que todo número tenha origem rastreável.
24. Como planejador, quero que o avanço físico real venha só das medições da
    EAP, para que Curva S, KPIs por área e EAP nunca discordem.
25. Como planejador, quero que a linha de base da Curva S física seja gerada da
    revisão vigente da EAP e congelada naquela revisão, para que baseline mude
    só por SM aprovada.
26. Como analista de riscos, quero que a evolução mensal do score residual
    seja reconstruída do histórico de avaliações e revisões, para não depender
    de série digitada.
27. Como avaliador, quero que a carga de demonstração tenha as datas
    deslocadas para o presente, para ver o cenário com sentido em qualquer dia
    em que eu abrir o app.
28. Como gestor, quero que valores financeiros sejam guardados em centavos e
    formatados só na tela, para não ter erro de arredondamento.
29. Como administrador, quero que toda gravação deixe linha na trilha de
    auditoria (quem, quando, o quê, antes e depois), para responder a qualquer
    questionamento.
30. Como usuário, quero ser avisado quando outra pessoa alterou o registro que
    estou editando, sem perder o que digitei, para não apagar o trabalho dela
    sem saber.
31. Como gestor, quero que uma gravação que mexe em vários módulos (aprovação
    de SM, emissão de pedido, reprovação de inspeção) grave tudo ou nada, para
    nunca ficar com dados pela metade.

### Início e relatório gerencial

32. Como gestor, quero no Início um indicador-chave por módulo, clicável, com a
    referência de gestão (previsto, meta, linha de base) abaixo do valor, para
    ver a saúde do projeto numa olhada.
33. Como gestor, quero pontos de atenção calculados (ações mais atrasadas,
    pedidos com folga negativa, sistemas bloqueados por item A, revisão de
    risco vencida, claim fora do prazo, HiPo no mês), para agir no que importa.
34. Como gestor de portfólio, quero a tabela Carteira de projetos (peso, BAC,
    avanço, SPI, CPI, projeção, VAC, término, riscos e pedidos críticos, ações
    atrasadas), para comparar projetos.
35. Como gestor, quero editar a ponderação da carteira com prévia e
    justificativa, gerando nova versão dos parâmetros, para refletir a
    estratégia.
36. Como gestor, quero emitir o relatório gerencial semanal ou mensal,
    escolhendo escopo, período e seções, para levar à reunião de desempenho.
37. Como gestor, quero que o modal do relatório mostre se cada módulo tem
    relato e análise do período registrados, com link para registrar, para não
    emitir relatório incompleto.
38. Como gestor, quero o relatório em folhas A4 na horizontal, uma por seção,
    com a fonte reduzida até caber, para imprimir ou salvar em PDF.
39. Como gestor, quero exportar o relatório para Excel com indicadores, tabelas,
    análises e desvios com comentários, para trabalhar os números.
40. Como gestor, quero que o período em andamento saia marcado como parcial,
    para não confundir dado incompleto com fechado.
41. Como gestor, quero a linha de tendência da Curva S financeira calculada
    pela EAC por desempenho no mês do relatório, para comparar com a projeção
    da equipe.

### Análise e relato do período

42. Como responsável de módulo, quero registrar a análise do período (150 a
    2.500 caracteres) com um comentário por desvio negativo detectado, para
    explicar causas e tendências.
43. Como responsável de 02, 03 ou 04, quero ser obrigado a comentar cada desvio
    negativo com ao menos 20 caracteres, para que nenhum desvio fique sem
    explicação.
44. Como responsável, quero copiar a análise do período anterior, para revisar
    em vez de reescrever.
45. Como gestor, quero que um desvio novo, surgido porque os dados mudaram,
    apareça como pendente, para manter a análise coerente com os números.
46. Como planejador, quero registrar o relato semanal e mensal (atividades do
    período, do próximo período e pontos de atenção com risco atrelado), para
    alimentar a folha de Planejamento do relatório.

### 01 Central de Ações

47. Como responsável, quero a lista de ações de todas as origens (Ata, Punch
    list, Contrato, Suprimentos, Risco, RNC, HSE, Mudança, Lição e
    Produtividade) com status calculado, para ter um único lugar de pendências.
48. Como usuário, quero KPIs clicáveis (Em dia, Atrasadas, Concluídas, Total),
    filtros em modal com chips e visão em lista ou kanban, para achar o que
    procuro.
49. Como gestor, quero gerar o PDF das ações filtradas e enviar follow-up aos
    responsáveis, para cobrar prazos.
50. Como gestor, quero o painel de ações por origem, responsável e projeto, para
    ver onde as pendências se acumulam.
51. Como secretário de reunião, quero criar ata com numeração do projeto,
    lista de presença, anotações e ações por grupo, para registrar reuniões.
52. Como secretário, quero gerar nova revisão da ata e consultar o histórico e
    as justificativas de replanejamento, para manter a rastreabilidade.
53. Como responsável, quero que replanejar uma ação exija justificativa, para
    que mudança de prazo seja explicada.
54. Como gestor, quero que retirar empresa ou convidado da ata seja bloqueado
    quando houver ação aberta, para não perder dono de pendência.
55. Como usuário, quero clicar na origem de uma ação e cair no registro que a
    gerou, para entender o contexto.

### 02 Planejamento

56. Como planejador, quero a EAP em árvore (área, subárea, pacote) com peso,
    critério de medição, datas da LB, previsto, real e desvio, para controlar
    escopo e avanço físico.
57. Como planejador, quero registrar medição por pacote pelo critério (etapas,
    unidades, marcos, percentual), com o real sempre calculado, para que
    ninguém digite resultado.
58. Como gestor, quero que estorno de medição exija justificativa e papel
    Gestor, para que o acumulado não regrida sem controle.
59. Como planejador, quero importar medições por planilha com recusa por
    linha, para lançar em lote sem perder qualidade.
60. Como gestor, quero criar revisão da EAP só a partir de SM aprovada com
    impacto em escopo, com pesos reescalados pelo maior resto, para manter a
    regra dos 100%.
61. Como planejador, quero desdobrar pacote de planejamento em pacotes de
    trabalho, para detalhar escopo em ondas.
62. Como gestor, quero a Curva S física (baseline, real, tendência) com drill
    de ano, mês e semana e a tabela período a período, para acompanhar o ritmo.
63. Como gestor, quero KPIs de SPI, avanço previsto x real e desvio por
    período e por área, para localizar atrasos.
64. Como planejador, quero o 6WLA com atividades por semana, restrições e
    responsáveis, para preparar o trabalho seis semanas antes.
65. Como planejador, quero controlar produtividade por quantidades da LB por
    empresa e semana, com apontamento, aprovação e revisão por SM, para medir
    SPI de quantidades, aderência e fator de produtividade.
66. Como fiscal de campo, quero registrar jornadas, amostragem do trabalho e
    paralisações, para calcular capacidade produtiva e horas improdutivas.
67. Como gestor, quero gerar plano de ação na Central para empresa fora da
    faixa de produtividade, para tratar o desvio.
68. Como responsável de completação, quero a punch list com categorias A, B e
    C, fluxo com verificação por outra pessoa e evidência obrigatória, para
    liberar sistemas com segurança.
69. Como gestor, quero que sistema com item A aberto fique bloqueado para o
    marco vinculado, para não comissionar com pendência impeditiva.
70. Como gestor, quero o painel da punch list (burndown, aging, por disciplina,
    sistema e empresa, % de sistemas liberados), para acompanhar a completação.

### 02 Planejamento: Programação Semanal (adaptada do app existente)

71. Como fornecedor, quero programar minhas atividades da semana, dia a dia de
    segunda a domingo, dentro da janela de programação, para assumir o
    compromisso da semana.
72. Como fornecedor, quero ver só a minha empresa em toda tela, sempre, para
    não acessar dado de concorrente.
73. Como planejador, quero validar a programação e definir o fiscal, para
    liberar o reporte do realizado.
74. Como encarregado ou fornecedor, quero lançar o realizado por turno dia e
    noite, com "= previsto" e "copiar a semana", e justificativa quando o
    desvio passar do limite, para reportar sem erro.
75. Como fiscal, quero aprovar o realizado das atividades sob minha
    responsabilidade, ou reabrir com motivo, para garantir o que foi medido.
76. Como planejador, quero publicar as atividades validadas, para encerrar a
    edição da semana.
77. Como usuário, quero na matriz um botão com a minha próxima ação em cada
    atividade e um menu só com o que meu perfil pode fazer, para não errar o
    passo.
78. Como fornecedor, quero pedir alteração de atividade já validada e o
    planejador aplicar ou recusar, para corrigir com rastreabilidade.
79. Como planejador do projeto ou administrador, quero uma subpágina de
    configuração dentro da Programação Semanal, com os parâmetros, as janelas
    de programação por empresa, as semanas liberadas e as liberações
    extraordinárias, para controlar quando cada contratada escreve.
80. Como planejador, quero que cada projeto tenha a sua própria configuração da
    programação e que um projeto novo nasça com os valores padrão, para ajustar
    um projeto sem afetar os outros.
81. Como gestor, quero que toda mudança na configuração da programação fique na
    trilha com o antes e o depois, para saber quem abriu uma janela e quando.
82. Como planejador, quero importar a semana pela planilha modelo, com
    conferência linha a linha antes de gravar, para não redigitar.
83. Como planejador, quero baixar a semana em Excel e gerar o relatório para
    imprimir, para distribuir a programação.
84. Como gestor, quero o dashboard da programação (curva S do avanço, previsto
    x realizado, aderência por contratada com drill, rankings, mapa de calor
    dia x frente, turnos e gargalos), para ver quem está no ritmo.
85. Como gestor, quero a governança por contratada e semana com a trilha de
    auditoria, para cobrar disciplina do processo.
86. Como gestor de portfólio, quero que a programação pertença a um projeto do
    GestNow e use as empresas e pessoas cadastradas nele, para não manter
    cadastro duplicado.

### 03 Gestão Financeira

87. Como controller, quero a EAC em árvore com revisões, itens e importação por
    planilha, para controlar o orçamento por pacote.
88. Como controller, quero que remanejamento e item novo virem SM de
    Remanejamento de orçamento e só se apliquem na aprovação, para que nenhum
    valor mude fora da gestão de mudanças.
89. Como controller, quero o mapa de controle em R$ mil com orçado, comprometido,
    realizado, saldo, projeção e desvio em mapa de calor, para ver sobrecusto.
90. Como controller, quero atualizar a projeção por item com justificativa e
    importar custos do ERP no fechamento do mês, para manter a EAC viva.
91. Como tesouraria, quero o cronograma de desembolso (saldo a pagar
    distribuído por mês, previsto x realizado), para planejar caixa.
92. Como gestor, quero KPIs de custo (CPI, SPI, CV, VAC, contingência,
    comprometido, EAC pelo CPI, TCPI) mês a mês, para avaliar desempenho.
93. Como gestor, quero a Curva S financeira (planejado, comprometido,
    realizado, tendência), para ver a evolução do gasto.
94. Como gestor, quero controlar reservas de contingência e gerencial
    (constituição, consumo por SM, liberação pelo Comitê, cobertura da
    exposição a riscos), para garantir fôlego para os riscos.
95. Como gestor de contratos, quero a ficha do contrato com cascata de valor,
    medições, aditivos, marcos de pagamento, claims, EOT e avaliações, para
    administrar o contrato após a adjudicação.
96. Como gestor de contratos, quero alerta de claim notificado fora do prazo
    contratual, para evitar preclusão.
97. Como gestor de contratos, quero que avaliação com nota 1 ou 2 exija
    evidência e crie plano de melhoria na Central, para tratar baixo
    desempenho.
98. Como gestor, quero a visão consolidada de contratos com os indicadores da
    administração contratual, para acompanhar exposição e reconhecimento.

### 04 Suprimentos

99. Como comprador, quero o plano de compras com pacotes vinculados à EAC,
    datas da LB, ROS e folga calculada, para planejar contratações.
100. Como comprador, quero conduzir o processo de compra em 9 etapas, com
     equalização técnica antes da comercial, ranking e aprovação por alçada,
     para comprar com governança.
101. Como gestor, quero que a emissão gere pedido ou contrato no 03 e comprometa
     o valor na EAC, para manter custo e suprimentos integrados.
102. Como gestor, quero o MAS com 12 marcos por pacote (LB, previsão, real),
     situação colorida, desvio em dias e exportação Excel e PDF A3, para ver o
     ciclo completo de suprimentos.
103. Como diligenciador, quero atualizar marcos e registrar recebimento, com
     ação na Central e risco sugerido quando a folga ficar negativa, para agir
     antes do atraso.
104. Como gestor da qualidade, quero que o FAT realizado registre inspeção no 06,
     para não digitar duas vezes.
105. Como comprador, quero o cadastro de fornecedores com qualificação,
     documentos com validade e desempenho, para escolher bem.
106. Como gestor, quero o painel de suprimentos (aderência ao plano, saving,
     OTD, pedidos críticos, curva de contratação, avanço do MAS), para
     acompanhar a área.

### 05 Gestão de Riscos

107. Como analista, quero registrar riscos com causa, evento e consequência, e
     avaliar P e I com score e severidade calculados no servidor, para manter
     o registro consistente.
108. Como analista, quero o plano de resposta com estratégia, custo x VME e
     aprovação pela gerência quando a severidade exigir, para tratar o risco.
109. Como gestor, quero que quem é responsável pelo plano não o aprove, para
     manter segregação de funções.
110. Como analista, quero revisões periódicas com cadência pela severidade, e a
     pauta de escalonamento calculada, para não deixar risco esquecido.
111. Como gestor, quero a matriz P x I inerente e residual com células que
     filtram o registro, para ver a distribuição.
112. Como gestor, quero o painel com exposição VME por categoria, evolução
     mensal e envio da pauta ao gerente, para reportar.
113. Como gestor, quero encerrar risco com lição aprendida obrigatória e, se
     materializado, gerar ação e SM, para transformar risco em aprendizado.

### 06 Gestão da Qualidade

114. Como inspetor, quero abrir RNC com contenção imediata e prazo pela
     severidade, para tratar não conformidades.
115. Como responsável, quero análise de causa, disposição (com concessão do
     cliente quando exigida) e ações corretivas na Central, para fechar a RNC.
116. Como gestor, quero verificar a eficácia (não por quem fez a análise) e ver
     a reincidência, para garantir que o problema acabou.
117. Como inspetor, quero ITP com pontos H, W e R e registros de inspeção que,
     reprovados, abrem RNC, para controlar a qualidade em campo.
118. Como auditor, quero o programa de auditorias com reprogramação justificada
     e constatações que abrem RNC, para manter o sistema auditado.
119. Como gestor, quero o painel da qualidade (RNC, aprovação em inspeções,
     conformidade, Pareto, custo da não qualidade), para acompanhar a área.

### 07 HSE

120. Como técnico de segurança, quero registrar ocorrências com gravidade real
     e potencial, HiPo e fluxo de investigação com prazos, para cumprir os
     prazos legais.
121. Como técnico, quero registrar HHT mensal por empresa, inspeções,
     observações e DDS, para ter a base das taxas.
122. Como gestor, quero o painel HSE com filtro de mês, TF, TRIF, TG e HiPo no
     mês e acumulado, duas pirâmides (mês e acumulado) e dias sem afastamento,
     para acompanhar a segurança.
123. Como técnico, quero registrar APR e HAZOP com recomendações que viram
     ações na Central, para tratar riscos de processo.
124. Como titular de dados, quero que nome e dados médicos fiquem em campo de
     acesso restrito, para atender à LGPD.

### 08 Governança

125. Como solicitante, quero registrar SM com tipo, origem e prioridade, para
     formalizar a mudança.
126. Como analista, quero a análise de impacto obrigatória (custo, prazo,
     escopo, riscos, SMS, contrato, itens da EAC) com a alçada mínima
     calculada, para levar a decisão certa a quem decide.
127. Como Comitê, quero registrar a decisão com quórum, para aprovar ou rejeitar
     com legitimidade.
128. Como gestor, quero que a aprovação gere as ações de implementação e
     atualize EAC, EAP, contratos e riscos, e que o encerramento confira tudo,
     para fechar a mudança só quando estiver incorporada.
129. Como autor, quero registrar lições com fluxo de validação por outra pessoa
     e aplicar lições em projetos, para reaproveitar conhecimento.
130. Como gestor, quero os painéis de mudanças e de lições, para acompanhar a
     governança.

### Configurações

131. Como Gestor ou Admin, quero editar parâmetros por grupo com justificativa,
     criando nova versão com vigência, para mudar critérios sem perder o
     histórico.
132. Como Gestor, quero o histórico de versões com antes e depois, para auditar
     mudanças de critério.
133. Como administrador, quero manter Colaboradores (perfil geral, papéis na
     Programação Semanal, vínculo e empresa), para controlar quem entra e o
     que faz.
134. Como administrador, quero definir o tamanho máximo e os tipos aceitos de
     anexo em Configurações, para controlar o armazenamento sem mexer em código.
135. Como administrador, quero manter os cadastros de apoio (empresas, pessoas,
     projetos, sistemas, unidades, locais), para alimentar os formulários.

### Imprimir, exportar e importar

136. Como usuário, quero exportar para Excel toda tabela e todo painel, com
     logo, contexto e referência de cada KPI, para trabalhar fora do sistema.
137. Como usuário, quero gerar PDF de toda tabela e todo painel, para anexar em
     relatório ou e-mail.
138. Como usuário, quero que o PDF e a impressão escondam a navegação, repitam o
     cabeçalho da tabela e não partam linha entre páginas, para ter um
     documento legível.
139. Como usuário, quero baixar o modelo da planilha e importar em passos com
     validação, pré-visualização e confirmação, para que nada grave antes de eu
     conferir.

### Anexos e envios

140. Como usuário, quero anexar arquivos de verdade (evidência, proposta,
     desenho, laudo) aos registros que pedem anexo, para que a evidência
     exigida exista e possa ser conferida depois.
141. Como usuário, quero baixar o anexo a partir do registro, para consultar o
     documento sem procurar em outra pasta.
142. Como usuário sem permissão no registro de origem, quero que o download do
     anexo seja recusado, para proteger documentos de projeto e dados pessoais.
143. Como usuário, quero ver nome, tamanho, quem enviou e quando em cada anexo,
     para saber se é a versão certa.
144. Como gestor, quero que follow-up de ações, pauta de riscos ao gerente e
     envio à tesouraria fiquem registrados e avisem "simulado" enquanto o envio
     real estiver desligado, para usar os fluxos desde o primeiro dia.
145. Como administrador, quero ligar o envio real de e-mail só por
     configuração quando o app estiver no Azure, para não precisar de nova
     versão do código.

### Manutenção sem IA

146. Como pessoa desenvolvedora, quero que cada módulo tenha uma pasta própria
     no front e no backend com `LEIA-ME.md` explicando cada arquivo, para
     localizar a alteração sem ajuda.
147. Como pessoa desenvolvedora, quero um mapa "quero mudar X, abro Y" cobrindo
     regra, cálculo, tela, estilo, gráfico, exportação, parâmetro, permissão e
     texto, para corrigir em minutos.
148. Como pessoa desenvolvedora, quero que cada tela tenha o trio HTML, CSS e
     JS com o mesmo nome e no mesmo lugar lógico, para saber onde está o estilo
     e o comportamento de cada página.
149. Como pessoa desenvolvedora, quero que a porta de qualidade reprove tela sem
     trio, sem item de navegação ou sem a barra lateral, para que a regra não
     dependa de memória.
150. Como pessoa desenvolvedora, quero que cada cálculo tenha um nome e um teste
     com o caso de fronteira, para mudar a fórmula com segurança.
151. Como pessoa desenvolvedora, quero rodar o app com dois cliques e a carga de
     demonstração, com o Postgres instalado uma única vez na máquina, para ver
     o efeito de uma alteração.
152. Como pessoa desenvolvedora, quero o diagrama de todas as entidades e
     ligações em `docs/`, para entender o banco antes de mexer numa tabela.
153. Como pessoa desenvolvedora, quero que o código Python siga o idioma do
     Padrão (inglês) e que o `LEIA-ME.md` de cada módulo traduza cada nome para
     o termo de negócio, para achar a fórmula sabendo só o nome dela em
     português.
154. Como analista de BI, quero ler as tabelas do Postgres com nomes em
     português do glossário, para montar painéis sem dicionário de dados à
     parte.
155. Como responsável pela publicação, quero a configuração pronta e um guia
     passo a passo para publicar no Azure com SSO, Postgres e armazenamento de
     arquivos, para colocar em produção sem reescrever nada.
156. Como dono do produto, quero que toda divergência entre o GestNow e o
     protótipo no teste-oráculo seja documentada e só entre com o meu aceite,
     para que nenhum número mude sem eu saber.
157. Como dono do produto, quero que, terminada a migração, só a pasta `Timenow -
     GestNow` exista, com as skills e as configurações de ferramenta dentro
     dela, para não haver duas versões da verdade.

---

## Implementation Decisions

### D1. Pilha e padrão: o Padrão de Desenvolvimento Timenow, sem exceção

* Azure Static Web Apps, Azure Functions V4 (Python 3.13 ou superior),
  Alpine.js 3.14.8 e Alpine AJAX 0.12.7 vendorizados, Jinja2, Timenow Design
  System. Sem bundler, sem build, sem CDN.
* Banco: **PostgreSQL** local e no Azure, acessado por SQLAlchemy 2 com
  migrações pelo Alembic (o Padrão já prevê `sqlalchemy` como dependência de
  banco). Detalhes em D5.
* **Idioma do código, como manda o Padrão:** interface, CSS, JS e rotas em
  português; Python (nome de arquivo, função, classe, docstring, comentário)
  em **inglês**. As pastas de módulo usam o identificador em português, igual
  ao prefixo da rota (`riscos`, `central_acoes`), porque são o endereço do
  módulo. O código portado do app de Programação Semanal, que hoje usa nomes
  em português, é renomeado para inglês na portabilidade. Cada `LEIA-ME.md`
  traz a tradução "termo de negócio para nome no código" (por exemplo, score
  residual para `calculations.residual_score`).
* **Hipermídia:** o servidor devolve fragmentos HTML prontos; o cliente não
  monta tela a partir de JSON. Exceções, como no Padrão e no app de
  Programação Semanal: `/api/health` e os downloads (Excel, modelo de planilha).
* O ponto de partida do repositório é uma **cópia** do `Padrao Desenvolvimento`
  (com `scripts/`, `eslint.config.mjs`, `api/pyproject.toml`, skills de agente
  e `docs/` de padrão), renomeado para GestNow conforme o passo 3 do README do
  Padrão.
* Toda regra do Padrão vale: fluxo obrigatório, porta de qualidade com cinco
  etapas, nunca desligar regra, `CONTEXT.md` como glossário, convenções de
  idioma (interface e JS em português, Python em inglês), BEM, namespace `TN`,
  cinco estados de tela, validação no servidor com 422, `TN.confirmarExclusao`
  e `TN.confirmarSaida`, acessibilidade e responsivo em 1280, 1100 e 760 px.
* **O Design System do Padrão substitui o do protótipo.** A paleta extraída do
  PDF, a tipografia Roboto, os botões pílula obrigatórios e o Chart.js saem.
  Mapeamento de estados: Sucesso para `ok`; Atenção para `warn`; Alerta,
  atraso e crítico para `erro`; Informação para `azul`; Neutro para `frio`;
  tipo Informação da ata para `roxo`. A exceção E1 (vermelho financeiro)
  deixa de ser exceção: sobrecusto usa a família `erro`, economia a família
  `ok`. As faixas do mapa de calor do desvio e da matriz P x I são refeitas
  nessas famílias, mantendo o sinal e o ícone além da cor.

### D2. Barra lateral sempre visível

* O shell (único documento completo) mantém a sidebar do Padrão à esquerda em
  todas as views, inclusive detalhe e relatório gerencial.
* A sidebar **nunca é ocultada**: o recolhimento acima de 1100 px e o
  comportamento abaixo dele levam a um **trilho de ícones** com dica, nunca a
  uma gaveta escondida. Única exceção: o papel impresso, onde a navegação não
  tem função.
* A navegação é servida pelo servidor (fragmento `/api/nav`, como no Padrão),
  a partir de uma **lista única de navegação** de dois níveis: Início, os 8
  módulos numerados (01 a 08) e Configurações (só Gestor e Admin). As telas de
  cada módulo, inclusive as de detalhe, são declaradas nessa lista; o mesmo
  fragmento serve as abas do módulo na barra da página.
* O seletor de escopo (Portfólio ou projeto) e o seletor de idioma vivem na
  sidebar, para estarem visíveis em todas as telas.

### D3. Trio da tela: toda página nasce com o seu CSS e o seu JS

O pedido "toda página HTML já com a sua CSS e JS vinculada" é atendido sem
quebrar a Regra 2 do contrato visual do Padrão (fragmento não carrega
recurso):

* Cada tela tem um **trio** com o mesmo nome: a view (fragmento) em
  `_views/<modulo>/`, e a folha de estilo e o script da página numa pasta
  pública de páginas, por módulo, espelhando a mesma árvore. A pasta é pública
  porque o shell carrega os arquivos antes do login, e eles não contêm dado.
* **O shell vincula todos os trios** com caminho absoluto, agrupados por
  módulo, logo depois do Design System. Assim a primeira execução já tem o
  visual correto em todas as telas.
* O CSS da página é **escopado** pela classe raiz da página
  (`.pagina--<modulo>-<tela>`), para não vazar entre telas, e só usa tokens. O
  que se repetir em três telas sobe para `ds/patterns.css` (regra do Padrão).
* O JS da página registra um único objeto em `TN.paginas["<modulo>/<tela>"]`
  com `iniciar(raiz)`; a view o aciona por atributo Alpine (`x-init`). Nenhum
  `<script>` dentro do fragmento.
* Tela sem estilo ou comportamento próprio ainda tem o trio (arquivos com o
  cabeçalho de propósito), para que a regra seja uniforme e verificável.
* A porta de qualidade ganha a verificação `trio-da-tela`: toda view tem CSS e
  JS correspondentes, todo trio está vinculado no shell, toda view tem item na
  lista de navegação. A falta falha alto.

### D4. Estrutura de pastas modular e autoexplicativa (tarefa própria)

A estrutura é a primeira fatia de trabalho e é entregue **antes** de qualquer
tela, com todos os `LEIA-ME.md` escritos. Princípio: **uma pasta por módulo em
cada camada, o mesmo nome em todas as camadas**, e um arquivo de documentação
em cada pasta que diz o que mora ali e onde mexer.

```
Timenow - GestNow/
  README.md, CONTEXT.md, run.bat
  docs/                       esta spec, mapa de módulos, padrões herdados,
                              referência (gráficos originais, protótipo)
  app/
    index.html                shell: DS + trios de todas as telas
    ds/                       Design System (tokens, shell, patterns, icons,
                              ui, print) + graficos/ (biblioteca de visuais)
    _views/<modulo>/          fragmentos das telas
    paginas/<modulo>/         <tela>.css e <tela>.js de cada tela
    _components/              fragmentos estáticos reutilizáveis
    lib/                      Alpine e Alpine AJAX vendorizados
  api/
    function_app.py           registra os blueprints de todos os módulos
    src/core/                 plataforma: respostas, Jinja, banco (sessão,
                              unidade de trabalho, controle de versão),
                              auth, RBAC, auditoria, calendário (hoje,
                              semanas ISO, períodos), escopo, exportação,
                              importação, anexos, notificação
    src/modulos/<modulo>/     routes.py (blueprint), service.py (fachada:
                              fluxos, permissões, integrações),
                              calculations.py (fórmulas puras),
                              validation.py, export.py, models.py
                              (tabelas do módulo), LEIA-ME.md
    src/templates/<modulo>/   fragmentos e partials Jinja2 do módulo
    migrations/               migrações Alembic, uma por fatia de módulo
    tests/<modulo>/           testes do módulo
  data/anexos/                anexos no modo local (no Azure, Blob Storage)
  scripts/                    instalar, rodar, verificar, dev_local, carga,
                              preparar o banco
```

O banco local **não** fica em `data/`: o Postgres guarda os próprios arquivos
na pasta da instalação, fora do OneDrive, porque a sincronização corrompe
arquivos de banco em uso.

Módulos (identificadores usados em todas as camadas): `inicio`,
`central_acoes`, `planejamento`, `programacao_semanal`, `financeiro`,
`suprimentos`, `riscos`, `qualidade`, `hse`, `governanca`, `configuracoes`,
`relatorio`. A Programação Semanal é submódulo do 02 na navegação, mas pasta
própria no código, por ser um subsistema completo.

Documentação de manutenção, obrigatória na fatia de estrutura:

* `docs/MAPA-DE-MODULOS.md`: tabela "quero mudar..." para cada tipo de
  alteração (texto de tela, layout, estilo, gráfico, fórmula, regra de fluxo,
  permissão, parâmetro, exportação, importação, integração entre módulos,
  tradução), apontando a pasta e o arquivo.
* Um `LEIA-ME.md` por módulo: telas do módulo, rotas, fórmulas com a definição
  de negócio, fluxos de estado, integrações de entrada e saída, parâmetros
  usados e "onde mexer".
* `docs/ONDE-ESTA.md` do Padrão, reescrito para o GestNow.
* `docs/MODELO-DE-DADOS.md`: o diagrama de **todas** as entidades e ligações
  (em Mermaid, legível no próprio Markdown), com uma linha por tabela dizendo
  o que ela guarda e qual módulo é o dono. É desenhado inteiro nesta fatia e
  **aceito pelo dono do produto antes de qualquer código de módulo** (D5).
* `CONTEXT.md` unificando o glossário do protótipo (EAC = Estrutura Analítica
  de Custos, Projeção no término, SM, MAS, ROS, VME, FP, CP etc.) com o do
  Padrão e o do app de Programação Semanal.

Ajuste da convenção do Padrão: views ficam em subpastas por módulo
(`_views/<modulo>/<tela>.html`) e blueprints em `src/modulos/<modulo>/`. A
porta de qualidade já percorre subpastas; a mudança é registrada em ADR no
`docs/` do GestNow, conforme a skill `domain-modeling`.

### D5. Camada de dados: PostgreSQL, local e no Azure

* **Um banco só, o mesmo nos dois lugares:** PostgreSQL instalado na máquina
  local (instalador oficial do Windows, uma vez) e Azure Database for
  PostgreSQL no Azure. A conexão vem de uma variável de ambiente; nada no
  código distingue local de nuvem. Sem JSON como base e sem SharePoint.
* **Uma tabela por entidade**, com colunas reais, chaves estrangeiras
  (projeto, empresa, pessoa, pacote, contrato, SM...) e restrições de
  integridade no próprio banco. Nomes de tabela e coluna em **português,
  snake_case**, iguais ao glossário do `CONTEXT.md` (`acao`, `risco`,
  `medicao_pacote`, `projeto_id`, `data_prevista`), para que quem monta o
  Power BI leia sem dicionário. Os modelos Python, em inglês, apontam para
  esses nomes.
* **Modelo inteiro antes, migrações por módulo:** o diagrama de todas as
  entidades sai na fatia 1 (`docs/MODELO-DE-DADOS.md`) e é aceito pelo dono
  do produto. Cada fatia de módulo cria as próprias tabelas por uma migração
  do Alembic que segue o diagrama. Mudança de modelo depois do aceite
  atualiza o diagrama na mesma entrega.
* Cada módulo é dono das próprias tabelas (`models.py` do módulo). Um módulo
  lê ou grava tabela de outro só pela fachada do dono, nunca direto.
* **Unidade de trabalho por requisição:** cada gravação abre uma transação; as
  integrações entre módulos (D9) acontecem dentro dela, e tudo grava ou nada
  grava. A numeração por projeto (ata, SM, RNC, risco...) usa uma tabela de
  sequência com trava de linha, sem buraco por concorrência.
* **Controle de edição simultânea:** todo registro editável tem coluna
  `versao`. A tela envia a versão que abriu; se outra pessoa gravou antes, a
  gravação é recusada com 409 e a mensagem "Este registro foi alterado por
  <nome> às <hora>. Recarregue para ver a versão atual", e o formulário volta
  preenchido com o que a pessoa digitou.
* Valores financeiros em centavos (inteiros) e datas sem hora em `date`,
  como no protótipo.
* Todo registro de projeto carrega `projeto_id`. Uma base por instalação, com
  os projetos do portfólio dentro dela.
* **Preparo local pelo `run.bat`:** confere se o serviço do Postgres está
  rodando (e diz exatamente o que fazer se não estiver), cria os bancos
  `gestnow` e `gestnow_teste` se faltarem, aplica as migrações e carrega a
  demonstração. Os arquivos do banco ficam na pasta da instalação do
  Postgres, fora do OneDrive.

### D5a. Anexos e evidências

* O componente de upload do protótipo (ações, contrato, governança, HSE, punch
  list, qualidade, diligenciamento, processos de compra) guardava só o nome do
  arquivo. No GestNow o arquivo é guardado de verdade.
* **Porta de arquivos** com duas implementações escolhidas por variável de
  ambiente: pasta `data/anexos/` no modo local e Azure Blob Storage no Azure.
* O banco guarda os metadados (nome, tipo, tamanho, hash, quem enviou,
  quando, registro de origem); o arquivo fica no armazenamento.
* O download passa pela API e checa a permissão de leitura do **registro de
  origem**; anexo com dado pessoal (HSE) segue a mesma restrição do campo.
* Limites como parâmetros do grupo Anexos em Configurações (versionados como
  os demais): até 25 MB por arquivo; tipos PDF, JPG, PNG, DOCX, XLSX, PPTX,
  DWG e ZIP. Recusa por tamanho ou tipo devolve 422 com a mensagem no campo.
* Onde o protótipo exige evidência (punch list, avaliação nota 1 ou 2,
  concessão do cliente, verificação de eficácia), "evidência" passa a ser ao
  menos um anexo gravado.

### D5b. O que se grava e a trilha

* **Somente fatos são gravados**: registros, medições, apontamentos, custos,
  eventos de fluxo, decisões, parâmetros versionados. Nenhum indicador derivado
  é persistido. Exceções, por serem fatos históricos por definição: a linha de
  base congelada de cada revisão (EAP, EAC, Curva S financeira, quantidades da
  produtividade), os pesos gravados na avaliação de contratada e o prazo
  vigente gravado na ocorrência HSE.
* Trilha de auditoria numa tabela só de inclusão (sem alteração nem
  exclusão), com quem, quando, o quê, antes e depois, gravada na mesma
  transação da mudança, como a trilha do app de Programação Semanal.

### D6. Data de referência e cálculo vivo

* Uma única função de plataforma devolve **hoje** no fuso
  `America/Sao_Paulo`. Toda fórmula que precisa de "data de referência" a
  recebe como argumento; nenhuma lê o relógio por conta própria. Os testes
  injetam a data.
* Os ~160 pontos `TODO: API` do `api.js` viram funções de `service.py` e
  `calculations.py` por módulo. As regras puras do `regras.js` (status da ação,
  severidade, faixas de desvio, taxas HSE, nível da pirâmide, avaliação,
  validação de parâmetros, alçada, ponderação do portfólio, situação do marco,
  avanço do pacote) são portadas para Python, uma função por regra.
* **Fonte única do avanço físico:** a EAP. O real da Curva S física e o avanço
  por área deixam de ter lançamento próprio e passam a ser calculados das
  medições datadas dos pacotes. Isso fecha a decisão que o protótipo deixou
  pendente.
* A evolução mensal do score residual dos riscos é reconstruída do histórico
  de avaliações e revisões. O histograma de mão de obra é derivado do HHT e da
  Curva S, como já era, mas calculado no servidor.
* **Carga de demonstração:** os mocks do protótipo são convertidos em carga
  inicial com todas as datas deslocadas pela diferença entre hoje e
  25/09/2026, preservando a coerência do cenário. Só entra em modo
  demonstração; em produção a base nasce vazia, com os cadastros mínimos e o
  primeiro Admin.
* **Divergência com o protótipo:** se o teste-oráculo mostrar que o próprio
  protótipo calculava errado, o GestNow não copia o erro em silêncio nem o
  corrige em silêncio. A divergência é registrada em
  `docs/DIVERGENCIAS-DO-PROTOTIPO.md` (regra, número do protótipo, número
  correto, motivo) e só entra com o aceite do dono do produto. Durante a
  execução das issues (Q31): erro de fórmula do protótipo é reproduzido e
  registrado como "pendente de aceite"; diferença causada por decisão já
  tomada nesta spec (como a EAP fonte única, Q3) segue a spec e também é
  registrada.

### D7. Autenticação, perfis e permissões

* **No Azure:** login pela autenticação embutida do Static Web Apps com o
  provedor AAD, aceitando **qualquer conta Microsoft** (corporativa de
  qualquer organização ou pessoal), no plano Free. Ter conta não basta: o
  **cadastro de Colaboradores é a fonte de verdade do acesso**. E-mail fora do
  cadastro vê a tela de acesso negado. Assim cliente e fornecedores entram
  sem virar convidados no tenant da Timenow.
* **No local:** o modo demonstração com seletor de perfil, como no app de
  Programação Semanal. O local serve só para demonstração e desenvolvimento,
  por isso não há login próprio com senha.
* **Perfis em dois eixos**, num motor de permissões por conjunto herdado do app
  de Programação Semanal:

  ```
  Colaborador
    perfil geral : Visualizador | Membro | Gestor | Admin   (um, obrigatório)
    papéis PS    : Planejador, Fiscal, Encarregado, Fornecedor (zero ou mais)
    vínculo      : Timenow | Fornecedor | Cliente
    empresa      : obrigatória quando o vínculo é Fornecedor
  ```

  O perfil geral governa os módulos 01 a 08, Início, relatório e
  Configurações. Os papéis valem só dentro da Programação Semanal e são por
  projeto, como no app, em que os colaboradores eram por ambiente: uma pessoa
  pode ser Fiscal num projeto e não em outro.
* **Vínculo**, aplicado no servidor, na fachada, nunca na tela:
  * **Fornecedor:** vê **só a Programação Semanal**, e nela só a própria
    empresa. A barra lateral mostra apenas esse item; qualquer outra rota
    devolve 403.
  * **Cliente:** vê os módulos conforme o perfil geral (tipicamente
    Visualizador).
  * **Timenow:** conforme o perfil geral e os papéis.
* Toda segregação de funções do protótipo vira checagem do servidor (quem
  elabora a LB não aprova; responsável pelo plano não aprova; validador de
  lição não é autor; verificador da punch list e da RNC não é o executante;
  aprovador da adjudicação não é o comprador nem quem recomendou). Recusa
  devolve 403 com a mensagem para a tela.
* **Campo restrito do HSE (LGPD, Q35):** nome e dados médicos das ocorrências
  ficam em tabela própria; Membro preenche, mas só Gestor e Admin leem esse
  campo e os anexos com esses dados.

### D8. Escopo de projeto e portfólio

* O escopo é resolvido **por requisição** a partir do parâmetro `projeto` da
  URL ou do cookie, com Portfólio como padrão. Uma camada de plataforma
  entrega o escopo à fachada de cada módulo.
* Regras do protótipo mantidas: ponderação configurável da carteira (maior
  resto), Curvas S do portfólio ponderadas, EAP e EAC na visão carteira só
  leitura, cadastro no Portfólio exige escolher o projeto, telas de detalhe
  voltam à lista ao trocar o escopo, análise do período do Portfólio com
  projeto nulo.

### D9. Integrações entre módulos

* Cada integração da tabela "Integração entre módulos" do protótipo vira uma
  chamada de serviço entre fachadas, dentro da mesma transação do banco (ou
  tudo grava, ou nada grava; D5).
* A **Central de Ações é a costura única de ação**: todo módulo que gera ação
  chama a mesma função de criação de ação com origem e referência; status da
  ação e do registro de origem ficam sincronizados por ela.
* Links de volta para a origem (ação para ata, punch, risco, RNC, ocorrência,
  APR, SM, lição, produtividade) são resolvidos por uma função de plataforma.
* Cada integração é ligada na fatia do módulo que chega **por último** na
  ordem de execução; a fatia do módulo que chega primeiro deixa o ponto
  anotado, dizendo em qual issue ele é ligado. Assim nenhuma fatia espera por
  outra posterior.

### D10. Programação Semanal: o app existente, adaptado

* O submódulo é o `Timenow - Programação Semanal` portado: domínio (fachada,
  cálculos, semanas, janela), fluxo de cinco passos, matriz com grade de dias,
  lançamento de realizado, pedidos de alteração, governança, dashboard com
  gráficos com drill, importação e exportação de planilha, relatório de
  impressão e configurações (parâmetros, cadastros de apoio, janelas).
* **Prevalece o app**, não a tela do protótipo: semana de segunda a domingo
  (não segunda a sábado), situação por atividade, PPC por atividade e
  aderência ponderada do conjunto, faixas alta, média e baixa, janela de
  programação, turnos dia e noite.
* Adaptações, e só elas: o "ambiente" do app passa a ser o **projeto** do
  GestNow (escopo D8, com visão Portfólio somente leitura); empresas, pessoas,
  fiscais e encarregados vêm dos cadastros e colaboradores do GestNow;
  perfis entram no RBAC unificado em dois eixos (D7); visual, gráficos e trio
  de tela seguem D1 a D3; a trilha usa a auditoria única; a persistência sai
  do repositório JSON do app e vai para tabelas do Postgres (D5); os nomes do
  código Python são passados para o inglês (D1), sem mudar comportamento.
* **Subpágina de configuração da Programação Semanal**, dentro do próprio
  submódulo, uma **por projeto** (o "ambiente" do app):
  * reúne o que o app tinha em Configurações e é da programação: parâmetros
    (limite de desvio que exige justificativa, faixas de PPC e aderência e
    afins), janelas de programação por empresa, semanas liberadas e
    liberações extraordinárias;
  * cadastros de empresas e pessoas e o cadastro de Colaboradores **não**
    ficam aqui: são os do GestNow, no módulo Configurações;
  * projeto novo nasce com os valores padrão do app;
  * edita quem tem papel de **Planejador no projeto** ou é **Admin**; a
    mudança vale na hora e a trilha de auditoria guarda o antes e o depois
    (sem o versionamento com justificativa dos parâmetros gerais, porque
    janelas e liberações mudam toda semana);
  * no Portfólio, a subpágina só pode ser lida e pede para escolher um
    projeto.
* O que o app tem e não é programação semanal (multi-ambiente com seletor de
  clientes, área do operador, tokens e API JSON de leitura) fica fora (ver Out
  of Scope).
* A tela de Programação Semanal do protótipo é descartada como fonte; a de
  Produtividade e o 6WLA, que são do protótipo, permanecem como telas
  próprias.

### D11. Gráficos: a coletânea `Graficos HTML` como biblioteca do Design System

* Os 22 visuais da coletânea são portados para uma biblioteca de gráficos no
  Design System (um arquivo por tipo de visual), em SVG e JavaScript puro,
  sem dependência externa. Cores fixas viram tokens lidos em tempo de
  execução; dados fictícios saem; o motor de drill ano, mês e semana do app de
  Programação Semanal é a base comum.
* Os dados chegam no fragmento como atributo `data-*` (JSON escapado pelo
  Jinja), nunca por `<script>` no fragmento. O servidor manda **quantidades**
  e o gráfico agrega por período quando o resumo não é soma (lição do app de
  Programação Semanal).
* Mapeamento de uso (todo gráfico do protótipo tem destino):

| Necessidade no GestNow | Visual da coletânea |
|---|---|
| Curva S física e financeira, avanço da programação, Curva S do MAS | Curva S Linha |
| Desembolso previsto x realizado, contratação acumulada, avanço por período com acumulado | Curva S Barra e Linha |
| Avanço por período, real x previsto, comparação entre meses | Comparativo de Barras Entre períodos |
| Pareto de RNC, de origem de mudanças, de motivos de parada | Pareto |
| Cards de KPI com referência de gestão | Card Indicador Único e Card com detalhes |
| Faixa de KPIs com estado | HTML KPI Status |
| SPI, CPI, aderência, conformidade, índice do MAS | Relógios de Indicadores |
| Matriz P x I e severidade de riscos | Matriz Formatada e Separação Severidade Riscos |
| Mapa de calor do desvio da EAC, dia x frente, aging | Tabela Heatmap |
| MAS (12 marcos por pacote), plano de quantidades por semana | Mapa 52 semanas e Tabela Quantitativos por entregável |
| Etapas do processo de compra, fluxo da SM, ciclo da RNC | Etapas |
| 6WLA, cronograma de marcos e auditorias | Gráfico Gantt e HTML Calendário |
| Restrições do 6WLA, acervo de lições | Galeria e Formulário de Cards |
| Desempenho da contratada ao longo do tempo | Gráfico de Áreas de Avaliação |
| Tabelas detalhadas (mapa de controle, EAP, punch) | Tabela formatada, Tabela Formata 2, Tabela Etapa por etapa |

* Sem equivalente na coletânea, construídos **no mesmo padrão visual**
  (tipografia, tooltip escuro, legenda, botões de ano, animação de entrada):
  pirâmide de segurança dupla (mês x acumulado), cascata de valor do contrato,
  rosca de distribuição e linhas múltiplas (TF e TRIF, CPI e SPI mês a mês).
* Os originais da coletânea ficam preservados em `docs/referencia/graficos/`.
* Fato verificado em 05/10/2026: a paleta da coletânea **já é a do Design
  System** (os mesmos hexadecimais, como os verdes `#006357` e `#00a793`, o
  vermelho `#d03636`, o laranja `#eb6100` e os cinzas). Trocar as cores fixas
  por tokens mantém o visual original dos gráficos.

### D12. Imprimir, relatório, Excel e PDF (todas as funções mantidas)

Inventário obrigatório, conferido tela a tela na aceitação: botões Excel e PDF
em toda tabela e painel (inclusive Início, Configurações e relatório); PDF das
ações; PDF A3 paisagem do MAS com células coloridas; relatório gerencial com
Imprimir / PDF, Excel e Alterar período; relatório de impressão e planilha da
Programação Semanal; modelos de importação.

* **Excel no servidor** com openpyxl (precedente do app de Programação
  Semanal): rota de download por tela, com logo, título, escopo, data de
  geração, KPIs com a referência de gestão, tabelas com filtro e cores das
  células pelos tokens. Mesmo conteúdo exportado pelo protótipo, nem uma
  coluna a menos.
* **PDF e impressão pela folha de impressão** do Design System (precedente do
  app de Programação Semanal): o servidor renderiza a versão imprimível da
  tela (cabeçalho com logo e contexto, KPIs, gráficos, tabelas), e o botão PDF
  a abre e aciona a impressão do navegador; a pessoa escolhe "Salvar como PDF"
  e o navegador lembra a escolha. `@page` A4 paisagem por padrão, A3
  paisagem para o MAS, sem navegação no papel, cabeçalho de tabela repetido,
  linha que não parte, fundos preservados. Sem biblioteca de PDF no servidor
  nem no navegador (decisão do dono do produto, 05/10/2026).
* **Relatório gerencial** é view do shell (com a barra lateral na tela) com as
  folhas A4 e o encaixe da fonte (mínimo 6,4 pt); o cálculo é uma única
  função do servidor com as regras de corte da seção 3 do README do protótipo.
* **Importação** no servidor, em passos: baixar modelo, enviar, conferência
  linha a linha (erro bloqueia a linha, aviso não), confirmação. Nada grava
  antes da confirmação. Substitui a leitura de planilha no navegador e elimina
  o risco do SheetJS 0.18.5 registrado no protótipo.
* Envios simulados do protótipo (follow-up, pauta ao gerente, envio à
  tesouraria) passam por uma **porta de notificação** com o envio por e-mail
  via Microsoft Graph **escrito e desligado** por variável de ambiente.
  Desligado, registra na trilha e avisa "simulado", como no gancho de
  notificação do app de Programação Semanal. Ligado (no Azure, com a conta do
  app e a permissão de envio de e-mail concedida no Entra), envia de verdade,
  sem mudança de código.

### D13. Idioma

* Português é o idioma-fonte (Padrão). O alternador PT | EN do protótipo é
  mantido, com tradução **no servidor** por catálogo de mensagens alimentado
  pelo dicionário `en.js` do protótipo; gráficos, Excel e PDF usam o mesmo
  catálogo. Dados cadastrados não são traduzidos. É a última fatia, para não
  atrasar as demais.

### D14. Contratos de rota

* Rotas em português, minúsculas, com hífen, agrupadas por módulo (prefixo do
  módulo). A tabela 7.2 do README do protótipo é o inventário de endpoints a
  cobrir; cada método `GI.api` tem rota correspondente.
* Toda rota de fragmento: gate do Alpine, resolução de usuário e permissão por
  um decorador único (precedente `com_usuario`), resposta por
  `AlpineAjaxResponse`, toast por cabeçalho, 422 com o formulário preenchido,
  409 com o formulário preenchido e o aviso de conflito quando a versão do
  registro mudou (D5), e resposta multi-alvo quando o formulário atualiza
  KPIs e lista juntos.
* Downloads de anexo seguem a exceção de download do Padrão (resposta de
  arquivo, não fragmento), com a checagem de permissão do registro de origem.

### D15. Ordem de execução (fatias verticais)

Cada fatia entrega comportamento completo e verificável, com a porta de
qualidade verde ao final. A ordem detalhada, em 93 issues numeradas na ordem
de execução, está em `docs/issues/spec-migracao-gestnow/` (ver "Related
Issues"); os itens abaixo são o resumo.

1. **Estrutura, documentação de manutenção e modelo de dados** (D4 e D5):
   cópia do Padrão, renomeação, árvore de pastas de todos os módulos,
   `LEIA-ME.md`, mapa de módulos, `CONTEXT.md`, ADR da convenção de subpastas
   e o diagrama de todas as entidades em `docs/MODELO-DE-DADOS.md`.
   **Portão (revisto na Q30):** o diagrama fica "aceito para execução" e a
   execução segue; o dono do produto o revisa no fim, e mudança vira issue
   nova.
2. **Plataforma**: Postgres com SQLAlchemy e Alembic, preparo do banco pelo
   `run.bat`, unidade de trabalho e controle de versão; shell com sidebar
   sempre visível e trios de todas as 45 telas (ainda com o estado vazio),
   navegação de dois níveis, escopo, auditoria, auth e RBAC em dois eixos com
   o recorte por vínculo, calendário (hoje, semana ISO, períodos), porta de
   anexos, porta de notificação, verificação `trio-da-tela`.
3. **Biblioteca de gráficos** (D11) e **exportação/impressão** (D12) genéricas,
   com o styleguide de gráficos em `docs/`.
4. **Carga de demonstração** deslocada para hoje e harness do teste-oráculo:
   o mecanismo e os cadastros entram na plataforma, e cada fatia de módulo
   acrescenta a sua parte da carga e os seus números do oráculo, porque as
   tabelas nascem por módulo (D5). O oráculo completo é consolidado na
   validação final.
5. Módulos, nesta ordem pelas dependências (revista na revisão 2.1): 01
   Central de Ações (costura de ações, para a aprovação da SM já nascer
   criando ações), 08 Governança (SM é pré-requisito de revisões), 03
   Financeiro (EAC, mapa de controle e contratos), 02 Planejamento (EAP e Curva
   S física), 03 Financeiro (contingência, Curva S financeira, KPIs de custo e
   desembolso, que precisam do avanço físico), 02 Planejamento de campo (relato,
   6WLA, produtividade e punch list), 02 Programação Semanal, 04 Suprimentos, 05
   Riscos, 06 Qualidade, 07 HSE e Configurações.
6. **Início, análise do período e relatório gerencial**.
7. **Idioma EN** (D13).
8. **Validação final** nas três larguras, acessibilidade e roteiro manual, e
   **prontidão para o Azure** (D16): configuração, variáveis e guia de
   publicação, com a suíte de testes verde contra o Postgres.
9. **Consolidação e desativação das pastas de origem** (ver Further Notes):
   `.claude`, `.agents` e `skills-lock.json` da raiz passam para dentro do
   GestNow; depois, com a confirmação do dono num pop-up no último passo da
   execução (Q32), as pastas de origem são excluídas.

### D16. Pronto para publicar no Azure

O app roda localmente em modo demonstração e **nasce pronto** para ser
publicado no Azure com SSO; a publicação em si é um passo do dono, seguindo o
guia. Entregáveis:

* `staticwebapp.config.json` com o provedor AAD aberto a qualquer conta
  Microsoft (plano Free), as rotas protegidas do Padrão e o redirecionamento
  de 401 para o login.
* Todas as variáveis de ambiente documentadas numa tabela (conexão do
  Postgres, armazenamento de anexos, envio de e-mail, modo demonstração ou
  produção), com o valor local e o valor no Azure.
* `docs/PUBLICACAO-AZURE.md`, guia passo a passo no portal: criar o Static
  Web Apps com o Functions vinculado, o Azure Database for PostgreSQL, a conta
  de armazenamento para os anexos; preencher as variáveis; aplicar as
  migrações; cadastrar o primeiro Admin; publicar pela SWA CLI (o caminho do
  Padrão); ligar o e-mail quando quiser.
* Sem Bicep e sem pipeline Git (decisão do dono do produto, 05/10/2026): os
  recursos são criados à mão seguindo o guia.

---

## Testing Decisions

### O que é um bom teste aqui

* Testa **comportamento externo** observável: o número que a pessoa lê, o
  registro que passa a existir, a recusa com a mensagem certa. Nunca a forma
  interna de um dicionário ou a ordem de chamadas.
* Tem nome de regra de negócio (`test_estorno_exige_gestor_e_justificativa`),
  cobre o caso de fronteira e injeta a data de referência.
* Usa o banco de teste próprio (`gestnow_teste`), recriado pelas migrações a
  cada rodada, com cada teste dentro de uma transação desfeita no fim. Nunca
  toca o banco `gestnow`. Precedente: o `conftest.py` do app de Programação
  Semanal, que isola os dados de cada teste e roda em modo produção.

### Costuras (seams) propostas, da mais alta para a mais baixa

1. **Fachada de serviço de cada módulo** (costura principal, uma por módulo):
   chamada com usuário, escopo, data e a sessão do banco de teste; asserta
   registros gravados, indicadores calculados e recusas (recusa de permissão,
   dado inválido, conflito de versão). Cobre fluxos, permissões, segregação
   de funções, recorte por vínculo e integrações entre módulos (inclusive que
   uma falha no meio desfaz tudo). Precedente: os testes do `dados.py` do app
   de Programação Semanal.
2. **Rota HTTP** (contrato): handler chamado com `HttpRequest` montado no
   teste; asserta status (200, 302 do gate, 403, 409, 422), cabeçalho de
   toast, alvo do fragmento e tipo do download. Poucos por módulo.
   Precedente: `test_ambientes.py` do app de Programação Semanal.
3. **Cálculos puros**: fórmulas com tabela de casos e fronteiras (SPI, CPI,
   TCPI, VAC, faixa do mapa de calor, severidade, VME, cadência, folga,
   situação do marco, taxas TF, TRIF e TG, PPC, aderência, FP, earned
   schedule, maior resto, alçada). Precedente: `test_dominio.py`.

### Testes transversais obrigatórios

* **Oráculo de paridade com o protótipo:** carregada a demonstração com a data
  injetada em 25/09/2026, os números conhecidos do protótipo precisam sair
  iguais (BAC R$ 44,6 mi, CPI 0,96, SPI 0,94, projeção R$ 45,26 mi, 8 ações
  atrasadas, 3 pedidos críticos, 2 riscos críticos, 4 RNC abertas, 263 dias sem
  afastamento, pirâmide 0/16/31/190/1.240, aderência 92,9%, OTD 66,7%, pesos
  da carteira 55,36/29,34/15,30, exposição R$ 3,4 mi). É a prova de que o
  cálculo foi portado, não inventado. Número diferente é defeito do GestNow,
  **salvo** divergência registrada e aceita pelo dono do produto (D6), caso
  em que o teste passa a afirmar o número correto e cita a divergência.
  Enquanto a divergência está pendente de aceite (Q31), o teste afirma o
  número do protótipo, ou o da spec quando a diferença decorre de decisão já
  tomada, e cita a divergência.
* **Cálculo vivo:** o mesmo cenário com a data de hoje produz atrasos e dias
  sem afastamento diferentes, e uma nova medição muda o SPI na consulta
  seguinte sem nenhum passo de recálculo.
* **Varredura de telas** (precedente: `_dev/crawl.py` do protótipo, com
  Playwright): abre as 45 telas em 1280, 1100 e 760 px e reprova console com
  erro, rolagem horizontal, sidebar ausente ou oculta, tela sem estilo próprio
  e link quebrado.
* **Exportações:** para cada tela, o Excel abre, tem as colunas da tabela da
  tela e os KPIs com referência; a versão imprimível renderiza sem navegação.
* **Porta de qualidade** (`verificar.mjs`) com as cinco etapas do Padrão e a
  verificação `trio-da-tela`.
* **Migrações:** um banco vazio sobe até a última migração sem erro, e o
  esquema resultante bate com os modelos.
* **Edição simultânea:** duas sessões abrem o mesmo registro; a segunda a
  gravar recebe o conflito com o nome de quem gravou antes, e nada se perde.
* **Atomicidade das integrações:** uma falha provocada no meio de uma
  aprovação de SM (ou emissão de pedido) não deixa nenhuma gravação parcial.
* **Vínculo:** um fornecedor só recebe a Programação Semanal da própria
  empresa e 403 em qualquer outra rota; um cliente vê o que o perfil geral
  permite.
* **Anexos:** acima do limite ou de tipo fora da lista é recusado com 422;
  download sem permissão no registro de origem é recusado; com o envio de
  e-mail desligado, a notificação registra na trilha e avisa "simulado".

### Módulos testados

Todos: plataforma (escopo, RBAC, vínculo, auditoria, calendário, banco,
controle de versão, anexos, notificação), os 8 módulos, Programação Semanal
(com os testes do app portados, renomeados e adaptados ao escopo de projeto
e à subpágina de configuração), Configurações, Início e relatório gerencial.

---

## Out of Scope

* **Multi-ambiente, seletor de clientes, área do operador, tokens e API JSON de
  leitura** do app de Programação Semanal: são plataforma multi-cliente, não
  funcionalidade de programação semanal. O projeto do GestNow faz o papel do
  ambiente.
* **O ato de publicar no Azure**: criar os recursos e pôr no ar é um passo do
  dono, seguindo o guia (D16). Ficam fora também a infraestrutura como código
  (Bicep) e o pipeline Git.
* **Integração efetiva com ERP e tesouraria**: continua por planilha e envio
  simulado. O e-mail real fica escrito e desligado (D12).
* **SharePoint e JSON como base**: a base é o Postgres (D5). O gancho de
  SharePoint do app de Programação Semanal não é portado.
* **Login próprio com senha**: o modo local serve só para demonstração e
  desenvolvimento; uso real é no Azure, com SSO.
* **Visão do fornecedor nos módulos 01 a 08**: o fornecedor vê só a
  Programação Semanal (D7).
* **Migração de dados reais**: não há base em produção; só a carga de
  demonstração.
* Telas que o protótipo e o app de Programação Semanal não têm. Nenhuma
  funcionalidade nova além das adaptações declaradas em D10 e das exigidas
  pelo Padrão.
* O `styleguide.html` do protótipo (substituído pela documentação de
  componentes do Padrão e pelo styleguide de gráficos).
* As ferramentas `_dev/` do protótipo (gerador de telas), exceto a ideia da
  varredura, que é reescrita como teste.

---

## Further Notes

* **Fontes lidas para esta spec:** README e HANDOVER do protótipo e todo o
  código de `Sistema` (43 telas de módulo, Início, relatório, 11 mocks,
  `api.js`, `regras.js`, componentes); toda a documentação e o esqueleto de
  `Padrao Desenvolvimento`; os 22 visuais de `Graficos HTML`; README,
  `CONTEXT.md`, `COMO-USAR.md`, domínio, testes e a spec anterior do app
  `Timenow - Programação Semanal` (precedente de formato desta spec e de suas
  tarefas).
* **Conflitos resolvidos a favor do Padrão:** paleta, tipografia, pílula
  obrigatória, Chart.js, SheetJS e jsPDF no navegador, sessionStorage e regras
  no cliente. Conflito resolvido a favor do pedido do usuário, sem violar o
  Padrão: trio de tela vinculado no shell (D3) e sidebar que nunca some (D2).
* **Decisão que estava pendente no protótipo:** EAP como fonte única do avanço
  físico (D6), confirmada pelo dono do produto em 05/10/2026.
* **O banco fica fora da pasta, por natureza:** o Postgres é um serviço
  instalado na máquina e guarda os arquivos na pasta da instalação. Isso não
  contraria "nada fora do `Timenow - GestNow`": todo o código, a configuração,
  as migrações, a carga de demonstração e os anexos locais estão dentro da
  pasta, e o banco pode ser recriado a partir deles pelo `run.bat`.
* **Desativação das pastas de origem (fatia 9).** Pré-condições: tudo o que
  for necessário já copiado para dentro de `Timenow - GestNow` (Padrão e
  skills, visuais originais em `docs/referencia/graficos/`, README do
  protótipo e do app de Programação Semanal em `docs/referencia/`, carga de
  demonstração convertida); oráculo de paridade e varredura de telas verdes;
  porta de qualidade verde. Só então, **com confirmação explícita do dono no
  momento**, excluir `Sistema`, `Padrao Desenvolvimento`, `Graficos HTML` e
  `Timenow - Programação Semanal`. Antes da exclusão, as pastas ocultas de
  ferramenta da raiz (`.claude`, `.agents`) e o `skills-lock.json` são
  **movidos para dentro do `Timenow - GestNow`**, mesclados com as skills do
  Padrão que já foram copiadas. As skills com o mesmo nome (grill-me e
  grilling) diferem pouco, e o dono escolheu a versão da raiz (Q34). A raiz
  termina só com a pasta do projeto.
  A exclusão no OneDrive vai para a lixeira, que fica como rede de segurança.
* **Riscos aceitos:** volume (45 telas e cerca de 160 pontos de API) torna as
  fatias 5 e 6 as mais longas; a tradução EN é a mais trabalhosa e por isso é a
  última; deslocar as datas da demonstração pode empurrar eventos para fins de
  semana, sem efeito nos cálculos; o Postgres local passa a ser
  pré-requisito de quem desenvolve (instalado uma vez); a modelagem
  relacional de todas as entidades é o maior trabalho novo da fatia 1;
  renomear o código do app de Programação Semanal para inglês exige portar
  os testes junto, para provar que o comportamento não mudou.
* **Rastreador de issues:** não há rastreador externo. As issues são arquivos
  Markdown locais em `docs/issues/spec-migracao-gestnow/`, com o registro em
  `index.md`, o agrupamento em entregas em `ENTREGAS.md` e o prompt único de
  execução em `PROMPT-EXECUCAO.md` (ver "Related Issues").

---

## Histórico de decisões

Sessões com o dono do produto em 05/10/2026: a discussão da spec (Q1 a Q29) e
a quebra em issues (Q30 a Q35). Cada linha mostra a pergunta, a resposta e
onde ela entrou nesta spec. Decisões tomadas pela execução das issues entram
no fim desta tabela como "Decisão da execução (ISSUE-NNN), pendente de revisão
do dono".

| # | Pergunta | Decisão | Onde |
|---|---|---|---|
| Q1 | Onde roda e guarda dados | Começa como o app de Programação Semanal (`run.bat`, rede local, modo demonstração), já pronto para o Azure com SSO | Solution, D7, D16 |
| Q2 | O que trazer do app de Programação Semanal | O app inteiro, sem a parte multi-cliente | D10, Out of Scope |
| Q3 | Fonte do avanço físico real | Só as medições da EAP | D6 |
| Q4 | Idioma PT e EN | Mantido, como última fatia | D13, D15 |
| Q5 | Estrutura de pastas | Por camada, como na revisão 1 | D3, D4 |
| Q6 | Barra lateral em tela estreita | Recolhe para trilho de ícones, nunca some | D2 |
| Q7 | Botão PDF | Impressão do navegador, "Salvar como PDF" | D12 |
| Q8 | Base de produção | Relacional, Postgres (no lugar do Azure SQL) | D1, D5 |
| Q9 | Base local | Postgres também local | D5 |
| Q10 | Modelagem | Uma tabela por entidade | D5 |
| Q11 | Quem faz login no Azure | Qualquer conta Microsoft; o cadastro de Colaboradores decide | D7, D16 |
| Q12 | Anexos | Arquivo de verdade: pasta local e Azure Blob | D5a |
| Q13 | Perfis | Dois eixos: perfil geral e papéis na Programação Semanal | D7 |
| Q14 | Pontos de teste | Confirmados; divergência do protótipo vai para o dono aceitar | D6, Testing Decisions |
| Q15 | Demonstração | Datas deslocadas para hoje; produção nasce vazia | D6 |
| Q16 | `.claude`, `.agents`, `skills-lock.json` | Movidos para dentro do GestNow antes da exclusão | D15, Further Notes |
| Q17 | Pronto para publicar | Configuração e guia, sem Bicep e sem pipeline | D16 |
| Q18 | Postgres local | Instalador nativo; o `run.bat` prepara o banco | D5 |
| Q19 | Idioma do Python | O do Padrão: inglês; pastas de módulo em português | D1, D4 |
| Q20 | Nomes de tabela e coluna | Português, snake_case | D5 |
| Q21 | Fornecedor e cliente | Fornecedor só na Programação Semanal; cliente pelo perfil geral | D7 |
| Q22 | Uso real local | Não: o local é só para demonstração e desenvolvimento | D7, Out of Scope |
| Q23 | Edição simultânea | A segunda gravação é recusada com aviso | D5, D14 |
| Q24 | E-mail | Escrito e desligado, liga por configuração | D12 |
| Q25 | Quando modelar | O diagrama inteiro antes, com migrações por módulo | D4, D5, D15 |
| Q26 | Limites de anexo | 25 MB, tipos comuns, editáveis em Configurações | D5a |
| Q27 | Configuração da Programação Semanal | Subpágina dentro do submódulo | D10 |
| Q28 | Escopo dessa configuração | Uma por projeto | D10 |
| Q29 | Quem edita e como registra | Planejador do projeto e Admin, com trilha de antes e depois | D10 |
| Q30 | Aceite do modelo de dados numa execução sem paradas | "Aceito para execução"; o dono revisa no fim, e mudança vira issue nova | D15, ISSUE-003, 004 |
| Q31 | Divergência com o protótipo durante a execução | Reproduz o número do protótipo e registra como pendente; diferença causada por decisão da spec segue a spec e também é registrada | D6, Testing Decisions, ISSUE-089 |
| Q32 | Exclusão das pastas de origem | Única pergunta da execução, num pop-up no último passo | D15, Further Notes, ISSUE-093 |
| Q33 | Ponto de retorno | Git local dentro do GestNow, um commit por issue, sem remoto | ISSUE-001 e o prompt de execução |
| Q34 | Skills repetidas (grill-me e grilling) | Fica a versão da raiz | Further Notes, ISSUE-093 |
| Q35 | Quem lê nome e dados médicos do HSE (LGPD) | Membro preenche; só Gestor e Admin leem, inclusive os anexos | D7, ISSUE-004, 073 |
| Decisão da execução (ISSUE-001), pendente de revisão do dono | Identificadores e sessão local | Pacote npm `timenow-gestnow`, pacote Python `timenow-gestnow-api`; identidade demonstrativa `gestnow.demo@example.invalid`, sem credencial, para não reutilizar a identidade nominal do Padrão. | D1, ISSUE-001 |
| Decisão da execução (ISSUE-001), pendente de revisão do dono | Acesso local à rede | O servidor escuta apenas em `127.0.0.1`; ISSUE-001 exige execução local e não pede exposição à rede local. | ISSUE-001 |
| Decisão da execução (ISSUE-002), pendente de revisão do dono | Views e diretórios ainda vazios | A view vazia de Início foi realocada para `app/_views/inicio/home.html`, com os caminhos de entrada atualizados; diretórios sem artefatos funcionais usam `.gitkeep` para a estrutura D4 permanecer versionada. | D3, D4, ISSUE-002 |
| Decisão da execução (ISSUE-002), pendente de revisão do dono | Local do catálogo PT/EN | O catálogo central do servidor será `api/src/core/translations.py`, implementado nas ISSUE-087/088; a spec exige catálogo no servidor, mas não fixa o nome do arquivo. | D13, ISSUE-087, ISSUE-088 |
| Decisão da execução (ISSUE-002), pendente de revisão do dono | Nomes de fórmulas nos LEIA-ME iniciais | Os identificadores ingleses dos cálculos nos LEIA-ME são nomes previstos com base nas definições existentes; a issue dona confirma/ajusta o nome junto com a fórmula e seu teste. | D1, D4, ISSUE-002 |
| Decisão da execução (ISSUE-003), pendente de revisão do dono | Forma dos parâmetros versionados | `parametro_versao` + `parametro_valor` (chave, tipo, valor, ordem) e `portfolio_ponderacao` para as notas da carteira; a spec pede versões e valores, sem fixar a forma. | D5, D8, ISSUE-003 |
| Decisão da execução (ISSUE-003), pendente de revisão do dono | `projeto_id` e `versao` nas tabelas-filhas | Filhas de um agregado herdam o projeto e a proteção de versão da raiz; não repetem as colunas. | D5, ISSUE-003, ISSUE-004 |
| Decisão da execução (ISSUE-003), pendente de revisão do dono | Coleções que pertencem a outra fatia | `analisesPeriodo` fica com `analise_periodo` na parte 2 (ISSUE-004), e a cobertura da parte 1 aponta para lá; `sistemas` usa a tabela `sistema` desenhada na parte 1. | D5, ISSUE-003, ISSUE-004 |
| Decisão da execução (ISSUE-004), pendente de revisão do dono | Revisões do ITP | `itp` + `itp_revisao` (a revisão aprovada é fato; nova revisão volta a pedir aprovação e não retira ponto com inspeção) + `itp_ponto`; a spec pede pontos e revisões, sem fixar a forma. | D5, D5b, ISSUE-004, ISSUE-069 |
| Decisão da execução (ISSUE-004), pendente de revisão do dono | Campo restrito do HSE e consolidado mensal | Nome e dados médicos em `ocorrencia_restrito` (só Gestor e Admin leem, Q35); o `hse_mensal` é o fechamento mensal declarado/importado (um por mês) e os registros individuais de inspeção, observação e DDS ficam em tabelas próprias; a spec nomeia as entidades, sem fixar a divisão de colunas. | D5b, D7, ISSUE-004, ISSUE-072, ISSUE-073 |
| Decisão da execução (ISSUE-004), pendente de revisão do dono | Camadas dos marcos de Suprimentos | As três camadas (LB, previsão e real) de cada marco ficam na mesma linha (`pacote_compra_marco`, `pedido_marco`), com o antes e o depois na trilha; a spec descreve as camadas, sem fixar a forma. | D5, D5b, ISSUE-004, ISSUE-058, ISSUE-061 |
| Decisão da execução (ISSUE-004), pendente de revisão do dono | Configuração da programação por projeto | `programacao_configuracao` com uma linha por projeto e colunas para os parâmetros do app (metas, semana de referência, limite de desvio), sem o versionamento com justificativa dos parâmetros gerais. | D10, ISSUE-004, ISSUE-054 |
| Decisão da execução (ISSUE-004), pendente de revisão do dono | Avaliação e revisão de risco | `risco_avaliacao` guarda cada avaliação inerente/residual com as seis dimensões e `risco_revisao` a revisão periódica; a linha do tempo da ficha é a composição das duas com a `auditoria`. | D5b, D6, ISSUE-004, ISSUE-065 |
| Decisão da execução (ISSUE-005), pendente de revisão do dono | Papel, URL local e leitura da URL de administração | O papel da aplicação é `gestnow`, com a senha da URL de administração; a URL da aplicação é gravada em `api/local.settings.json` (fora do git) e carregada por `dev_local` e pelos testes; a URL de administração é lida com a senha antes do último `@` antes do host, tolerando caracteres especiais não codificados, e a URL gravada sai codificada. | D5, D16, ISSUE-005 |
| Decisão da execução (ISSUE-005), pendente de revisão do dono | Recriação do banco de teste | Os testes derivam a URL do banco de teste da URL da aplicação com o sufixo `_teste` e recriam o schema `public` pelas migrações a cada rodada, sem exigir a URL de administração nem privilégio de cluster; um guarda recusa qualquer banco de teste que não termine em `_teste`, para nenhum teste tocar o `gestnow`. | Testing Decisions, D5, ISSUE-005 |
| Decisão da execução (ISSUE-005), pendente de revisão do dono | Driver da URL e forma do `/api/health` | A URL `postgresql://` é normalizada para `postgresql+psycopg://` no código, para a mesma variável valer no local e no Azure com o driver psycopg 3; o `/api/health` mantém `status` e ganha `banco: {situacao, revisao}`, com banco fora do ar devolvendo `situacao: erro` sem derrubar a rota. | D5, D14, ISSUE-005 |
| Decisão da execução (ISSUE-005), pendente de revisão do dono | Posição dos modelos e nomes das restrições | As tabelas da plataforma ficam em `api/src/core/models.py` e o projeto e os cadastros de apoio em `api/src/modulos/configuracoes/models.py`, conforme o dono de cada tabela no `MODELO-DE-DADOS.md`; o metadata do `Base` usa convenção de nomes de restrição para as migrações ficarem comparáveis com os modelos. | D5, ISSUE-005 |

---

## Related Issues

The implementation issues for this PRD are stored in [docs/issues/spec-migracao-gestnow/](issues/spec-migracao-gestnow/).
Registro e ordem de execução: [index.md](issues/spec-migracao-gestnow/index.md).
Entregas e produto final: [ENTREGAS.md](issues/spec-migracao-gestnow/ENTREGAS.md).
Prompt único de execução: [PROMPT-EXECUCAO.md](issues/spec-migracao-gestnow/PROMPT-EXECUCAO.md).

| ID | Title | Type | Status | Label | Blocked by | File |
|---|---|---|---|---|---|---|
| ISSUE-001 | O repositório GestNow nasce do Padrão, renomeado, com as referências preservadas e o app subindo localmente | Task | proposed | ready-for-agent | None | [Issue file](issues/spec-migracao-gestnow/001-repositorio-gestnow-a-partir-do-padrao.md) |
| ISSUE-002 | Estrutura modular de pastas com LEIA-ME por módulo, mapa "quero mudar X, abro Y", ONDE-ESTA, CONTEXT unificado e ADR da convenção | Task | proposed | ready-for-agent | ISSUE-001 | [Issue file](issues/spec-migracao-gestnow/002-estrutura-modular-e-documentacao-de-manutencao.md) |
| ISSUE-003 | Modelo de dados, parte 1: plataforma, cadastros, Central de Ações, Governança e Financeiro | Task | proposed | ready-for-agent | ISSUE-002 | [Issue file](issues/spec-migracao-gestnow/003-modelo-de-dados-parte-1.md) |
| ISSUE-004 | Modelo de dados, parte 2: Planejamento, Programação Semanal, Suprimentos, Riscos, Qualidade, HSE, análises e relatório | Task | proposed | ready-for-agent | ISSUE-003 | [Issue file](issues/spec-migracao-gestnow/004-modelo-de-dados-parte-2.md) |
| ISSUE-005 | Postgres local preparado pelo run.bat, migrações Alembic e banco de teste isolado | Task | proposed | ready-for-agent | ISSUE-004 | [Issue file](issues/spec-migracao-gestnow/005-postgres-local-migracoes-e-banco-de-teste.md) |
| ISSUE-006 | Gravação segura: unidade de trabalho, trilha de auditoria, numeração por projeto e aviso de edição simultânea | Task | proposed | ready-for-agent | ISSUE-005 | [Issue file](issues/spec-migracao-gestnow/006-gravacao-segura.md) |
| ISSUE-007 | Data de hoje, calendário de semanas e períodos, e parâmetros versionados | Task | proposed | ready-for-agent | ISSUE-005 | [Issue file](issues/spec-migracao-gestnow/007-data-de-hoje-calendario-e-parametros.md) |
| ISSUE-008 | Carga de demonstração deslocada para hoje, base de produção vazia com o primeiro Admin e harness do oráculo | Task | proposed | ready-for-agent | ISSUE-006, ISSUE-007 | [Issue file](issues/spec-migracao-gestnow/008-carga-de-demonstracao-e-producao-vazia.md) |
| ISSUE-009 | Shell com barra lateral sempre visível, navegação de dois níveis, abas do módulo, escopo Portfólio ou projeto e dicas de siglas | Task | proposed | ready-for-agent | ISSUE-008 | [Issue file](issues/spec-migracao-gestnow/009-shell-sidebar-navegacao-e-escopo.md) |
| ISSUE-010 | Trio HTML, CSS e JS de todas as telas vinculado no shell e verificação trio-da-tela | Task | proposed | ready-for-agent | ISSUE-009 | [Issue file](issues/spec-migracao-gestnow/010-trio-de-todas-as-telas.md) |
| ISSUE-011 | Login Microsoft com o cadastro de Colaboradores, perfis em dois eixos, recorte por vínculo e modo demonstração | Task | proposed | ready-for-agent | ISSUE-010 | [Issue file](issues/spec-migracao-gestnow/011-login-perfis-e-vinculo.md) |
| ISSUE-012 | Anexos de verdade: pasta local ou Blob, limites por parâmetro e download com a permissão do registro de origem | Task | proposed | ready-for-agent | ISSUE-011, ISSUE-007 | [Issue file](issues/spec-migracao-gestnow/012-anexos-de-verdade.md) |
| ISSUE-013 | Porta de notificação: e-mail via Microsoft Graph escrito e desligado, envio simulado registrado na trilha | Task | proposed | ready-for-agent | ISSUE-006 | [Issue file](issues/spec-migracao-gestnow/013-porta-de-notificacao.md) |
| ISSUE-014 | Biblioteca de gráficos 1: motor comum com drill e curvas, barras, Pareto e relógios | Task | proposed | ready-for-agent | ISSUE-010 | [Issue file](issues/spec-migracao-gestnow/014-graficos-1-motor-e-curvas.md) |
| ISSUE-015 | Biblioteca de gráficos 2: cards, faixa de KPI, matrizes, heatmap, mapa de 52 semanas, quantitativos e etapas | Task | proposed | ready-for-agent | ISSUE-014 | [Issue file](issues/spec-migracao-gestnow/015-graficos-2-cards-matrizes-e-tabelas.md) |
| ISSUE-016 | Biblioteca de gráficos 3: Gantt, calendário, galeria, cards de formulário, áreas, tabelas formatadas e os visuais novos | Task | proposed | ready-for-agent | ISSUE-015 | [Issue file](issues/spec-migracao-gestnow/016-graficos-3-cronogramas-galerias-e-novos-visuais.md) |
| ISSUE-017 | Exportação Excel e versão imprimível (PDF pelo navegador) genéricas | Task | proposed | ready-for-agent | ISSUE-011, ISSUE-014 | [Issue file](issues/spec-migracao-gestnow/017-exportacao-excel-e-versao-imprimivel.md) |
| ISSUE-018 | Importação de planilha em passos com conferência linha a linha | Task | proposed | ready-for-agent | ISSUE-017 | [Issue file](issues/spec-migracao-gestnow/018-importacao-de-planilha-em-passos.md) |
| ISSUE-019 | Ações: costura única de criação, status calculado, lista, kanban, filtros, replanejamento com justificativa e link de origem | Task | proposed | ready-for-agent | ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018 | [Issue file](issues/spec-migracao-gestnow/019-acoes-costura-status-e-lista.md) |
| ISSUE-020 | PDF das ações filtradas, follow-up aos responsáveis e painel da Central | Task | proposed | ready-for-agent | ISSUE-019 | [Issue file](issues/spec-migracao-gestnow/020-pdf-das-acoes-follow-up-e-painel.md) |
| ISSUE-021 | Atas: lista, nova ata numerada, dados da reunião e lista de presença com retirada bloqueada | Task | proposed | ready-for-agent | ISSUE-019 | [Issue file](issues/spec-migracao-gestnow/021-atas-lista-nova-ata-e-presenca.md) |
| ISSUE-022 | Anotações e ações da ata por grupo, revisões da ata, histórico e justificativas | Task | proposed | ready-for-agent | ISSUE-021 | [Issue file](issues/spec-migracao-gestnow/022-anotacoes-acoes-e-revisoes-da-ata.md) |
| ISSUE-023 | Solicitação de mudança: registro, nova SM numerada, ficha e cancelamento | Task | proposed | ready-for-agent | ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018 | [Issue file](issues/spec-migracao-gestnow/023-solicitacao-de-mudanca-registro-e-ficha.md) |
| ISSUE-024 | Análise de impacto obrigatória com alçada mínima calculada | Task | proposed | ready-for-agent | ISSUE-023 | [Issue file](issues/spec-migracao-gestnow/024-analise-de-impacto-e-alcada.md) |
| ISSUE-025 | Decisão com quórum, ações de implementação na Central, emergencial, reapresentação e encerramento | Task | proposed | ready-for-agent | ISSUE-024, ISSUE-019 | [Issue file](issues/spec-migracao-gestnow/025-decisao-implementacao-e-encerramento-da-sm.md) |
| ISSUE-026 | Painel de mudanças | Task | proposed | ready-for-agent | ISSUE-025 | [Issue file](issues/spec-migracao-gestnow/026-painel-de-mudancas.md) |
| ISSUE-027 | Lições aprendidas: acervo, fluxo de validação segregado e aplicação em projeto | Task | proposed | ready-for-agent | ISSUE-019, ISSUE-023 | [Issue file](issues/spec-migracao-gestnow/027-licoes-acervo-fluxo-e-aplicacao.md) |
| ISSUE-028 | Painel de lições | Task | proposed | ready-for-agent | ISSUE-027 | [Issue file](issues/spec-migracao-gestnow/028-painel-de-licoes.md) |
| ISSUE-029 | EAC em árvore com itens, visão carteira e ponderação da carteira | Task | proposed | ready-for-agent | ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018 | [Issue file](issues/spec-migracao-gestnow/029-eac-arvore-visao-carteira-e-ponderacao.md) |
| ISSUE-030 | Revisões da EAC, item novo e remanejamento como SM, aplicados só na aprovação, e importação de itens | Task | proposed | ready-for-agent | ISSUE-029, ISSUE-025 | [Issue file](issues/spec-migracao-gestnow/030-revisoes-da-eac-e-remanejamento-por-sm.md) |
| ISSUE-031 | Mapa de controle com projeção, mapa de calor e custos do ERP | Task | proposed | ready-for-agent | ISSUE-030 | [Issue file](issues/spec-migracao-gestnow/031-mapa-de-controle-projecao-e-erp.md) |
| ISSUE-032 | Ficha do contrato: cascata de valor, medições e aditivos | Task | proposed | ready-for-agent | ISSUE-031 | [Issue file](issues/spec-migracao-gestnow/032-ficha-do-contrato-medicoes-e-aditivos.md) |
| ISSUE-033 | Contrato: marcos de pagamento, claims e extensões de prazo | Task | proposed | ready-for-agent | ISSUE-032, ISSUE-023 | [Issue file](issues/spec-migracao-gestnow/033-marcos-de-pagamento-claims-e-eot.md) |
| ISSUE-034 | Avaliação de desempenho da contratada | Task | proposed | ready-for-agent | ISSUE-032, ISSUE-027 | [Issue file](issues/spec-migracao-gestnow/034-avaliacao-de-desempenho-da-contratada.md) |
| ISSUE-035 | Contratos: visão consolidada e indicadores da administração contratual | Task | proposed | ready-for-agent | ISSUE-033, ISSUE-034 | [Issue file](issues/spec-migracao-gestnow/035-contratos-consolidado-e-indicadores.md) |
| ISSUE-036 | EAP em árvore com dicionário, avanço calculado pelo critério e visão carteira | Task | proposed | ready-for-agent | ISSUE-029 | [Issue file](issues/spec-migracao-gestnow/036-eap-arvore-dicionario-e-carteira.md) |
| ISSUE-037 | Medição dos pacotes pelo critério, estorno controlado e importação do avanço | Task | proposed | ready-for-agent | ISSUE-036 | [Issue file](issues/spec-migracao-gestnow/037-medicao-estorno-e-importacao-do-avanco.md) |
| ISSUE-038 | Revisões da EAP a partir de SM e desdobramento de pacotes de planejamento | Task | proposed | ready-for-agent | ISSUE-037, ISSUE-025 | [Issue file](issues/spec-migracao-gestnow/038-revisoes-da-eap-e-desdobramento.md) |
| ISSUE-039 | Curva S física com linha de base congelada, real das medições e drill | Task | proposed | ready-for-agent | ISSUE-038 | [Issue file](issues/spec-migracao-gestnow/039-curva-s-fisica.md) |
| ISSUE-040 | KPIs de planejamento por período e por área | Task | proposed | ready-for-agent | ISSUE-039 | [Issue file](issues/spec-migracao-gestnow/040-kpis-de-planejamento.md) |
| ISSUE-041 | Contingência e reserva gerencial | Task | proposed | ready-for-agent | ISSUE-039, ISSUE-031, ISSUE-025 | [Issue file](issues/spec-migracao-gestnow/041-contingencia-e-reserva-gerencial.md) |
| ISSUE-042 | Curva S financeira e KPIs de custo | Task | proposed | ready-for-agent | ISSUE-041 | [Issue file](issues/spec-migracao-gestnow/042-curva-s-financeira-e-kpis-de-custo.md) |
| ISSUE-043 | Cronograma de desembolso e envio à tesouraria | Task | proposed | ready-for-agent | ISSUE-031, ISSUE-033 | [Issue file](issues/spec-migracao-gestnow/043-cronograma-de-desembolso.md) |
| ISSUE-044 | Relato do período | Task | proposed | ready-for-agent | ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018 | [Issue file](issues/spec-migracao-gestnow/044-relato-do-periodo.md) |
| ISSUE-045 | 6WLA: atividades por semana, restrições e responsáveis | Task | proposed | ready-for-agent | ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018 | [Issue file](issues/spec-migracao-gestnow/045-6wla.md) |
| ISSUE-046 | Produtividade: plano de quantidades, ciclo da linha de base e apontamento semanal | Task | proposed | ready-for-agent | ISSUE-025 | [Issue file](issues/spec-migracao-gestnow/046-produtividade-quantidades-lb-e-apontamento.md) |
| ISSUE-047 | Produtividade: horas efetivas, amostragem do trabalho e paralisações | Task | proposed | ready-for-agent | ISSUE-046 | [Issue file](issues/spec-migracao-gestnow/047-produtividade-horas-efetivas-amostragem-e-paralisacoes.md) |
| ISSUE-048 | Produtividade: KPIs de performance e plano de ação na Central | Task | proposed | ready-for-agent | ISSUE-046, ISSUE-047, ISSUE-019 | [Issue file](issues/spec-migracao-gestnow/048-produtividade-kpis-e-plano-de-acao.md) |
| ISSUE-049 | Punch list: itens, fluxo com verificação e bloqueio de sistema | Task | proposed | ready-for-agent | ISSUE-019 | [Issue file](issues/spec-migracao-gestnow/049-punch-list-itens-verificacao-e-bloqueio.md) |
| ISSUE-050 | Punch list: painel de completação | Task | proposed | ready-for-agent | ISSUE-049 | [Issue file](issues/spec-migracao-gestnow/050-punch-list-painel.md) |
| ISSUE-051 | Matriz da programação semanal portada: semana de segunda a domingo, janela e programação pelo fornecedor | Task | proposed | ready-for-agent | ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018 | [Issue file](issues/spec-migracao-gestnow/051-programacao-semanal-matriz-e-programacao.md) |
| ISSUE-052 | Fluxo de cinco passos: validar com fiscal, realizado por turno, aprovação do fiscal e publicação | Task | proposed | ready-for-agent | ISSUE-051 | [Issue file](issues/spec-migracao-gestnow/052-programacao-semanal-fluxo-de-cinco-passos.md) |
| ISSUE-053 | Pedidos de alteração e governança da programação | Task | proposed | ready-for-agent | ISSUE-052 | [Issue file](issues/spec-migracao-gestnow/053-programacao-semanal-pedidos-de-alteracao-e-governanca.md) |
| ISSUE-054 | Subpágina de configuração da programação, uma por projeto | Task | proposed | ready-for-agent | ISSUE-051 | [Issue file](issues/spec-migracao-gestnow/054-programacao-semanal-configuracao-por-projeto.md) |
| ISSUE-055 | Importação da semana, planilha e relatório de impressão | Task | proposed | ready-for-agent | ISSUE-052 | [Issue file](issues/spec-migracao-gestnow/055-programacao-semanal-importacao-planilha-e-impressao.md) |
| ISSUE-056 | Dashboard da programação | Task | proposed | ready-for-agent | ISSUE-052 | [Issue file](issues/spec-migracao-gestnow/056-programacao-semanal-dashboard.md) |
| ISSUE-057 | Fornecedores com qualificação, documentos com validade e desempenho | Task | proposed | ready-for-agent | ISSUE-034 | [Issue file](issues/spec-migracao-gestnow/057-fornecedores-qualificacao-e-desempenho.md) |
| ISSUE-058 | Plano de compras | Task | proposed | ready-for-agent | ISSUE-031, ISSUE-057 | [Issue file](issues/spec-migracao-gestnow/058-plano-de-compras.md) |
| ISSUE-059 | Processo de compra: da requisição à negociação | Task | proposed | ready-for-agent | ISSUE-058 | [Issue file](issues/spec-migracao-gestnow/059-processo-de-compra-da-requisicao-a-negociacao.md) |
| ISSUE-060 | Processo de compra: recomendação, aprovação por alçada e emissão de pedido ou contrato | Task | proposed | ready-for-agent | ISSUE-059, ISSUE-032 | [Issue file](issues/spec-migracao-gestnow/060-processo-de-compra-alcada-e-emissao.md) |
| ISSUE-061 | Diligenciamento e recebimento | Task | proposed | ready-for-agent | ISSUE-060 | [Issue file](issues/spec-migracao-gestnow/061-diligenciamento-e-recebimento.md) |
| ISSUE-062 | MAS: Mapa de Suprimentos | Task | proposed | ready-for-agent | ISSUE-061 | [Issue file](issues/spec-migracao-gestnow/062-mas-mapa-de-suprimentos.md) |
| ISSUE-063 | Painel de suprimentos | Task | proposed | ready-for-agent | ISSUE-062 | [Issue file](issues/spec-migracao-gestnow/063-painel-de-suprimentos.md) |
| ISSUE-064 | Registro e avaliação de riscos | Task | proposed | ready-for-agent | ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018 | [Issue file](issues/spec-migracao-gestnow/064-riscos-registro-e-avaliacao.md) |
| ISSUE-065 | Ficha do risco: plano de resposta, revisões, encerramento e reabertura | Task | proposed | ready-for-agent | ISSUE-064, ISSUE-019, ISSUE-023, ISSUE-027 | [Issue file](issues/spec-migracao-gestnow/065-ficha-do-risco-plano-revisoes-e-encerramento.md) |
| ISSUE-066 | Matriz P x I e painel de riscos | Task | proposed | ready-for-agent | ISSUE-065 | [Issue file](issues/spec-migracao-gestnow/066-matriz-pxi-e-painel-de-riscos.md) |
| ISSUE-067 | Integrações que chegam aos Riscos: risco sugerido do diligenciamento, claim, lição aplicada e cobertura da contingência | Task | proposed | ready-for-agent | ISSUE-066, ISSUE-061, ISSUE-033, ISSUE-027, ISSUE-041 | [Issue file](issues/spec-migracao-gestnow/067-integracoes-que-chegam-aos-riscos.md) |
| ISSUE-068 | Não conformidades (RNC) | Task | proposed | ready-for-agent | ISSUE-019, ISSUE-027 | [Issue file](issues/spec-migracao-gestnow/068-nao-conformidades-rnc.md) |
| ISSUE-069 | Inspeções e ITP, com o FAT do diligenciamento | Task | proposed | ready-for-agent | ISSUE-068, ISSUE-061 | [Issue file](issues/spec-migracao-gestnow/069-inspecoes-itp-e-fat.md) |
| ISSUE-070 | Auditorias | Task | proposed | ready-for-agent | ISSUE-068 | [Issue file](issues/spec-migracao-gestnow/070-auditorias.md) |
| ISSUE-071 | Painel da qualidade | Task | proposed | ready-for-agent | ISSUE-069, ISSUE-070 | [Issue file](issues/spec-migracao-gestnow/071-painel-da-qualidade.md) |
| ISSUE-072 | HHT, inspeções de segurança, observações e DDS | Task | proposed | ready-for-agent | ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018 | [Issue file](issues/spec-migracao-gestnow/072-hht-inspecoes-observacoes-e-dds.md) |
| ISSUE-073 | Ocorrências com investigação, prazos legais e dados restritos (LGPD) | Task | proposed | ready-for-agent | ISSUE-072, ISSUE-019, ISSUE-027 | [Issue file](issues/spec-migracao-gestnow/073-ocorrencias-investigacao-e-lgpd.md) |
| ISSUE-074 | Análises de risco APR e HAZOP | Task | proposed | ready-for-agent | ISSUE-019 | [Issue file](issues/spec-migracao-gestnow/074-apr-e-hazop.md) |
| ISSUE-075 | Painel HSE | Task | proposed | ready-for-agent | ISSUE-072, ISSUE-073, ISSUE-074, ISSUE-034 | [Issue file](issues/spec-migracao-gestnow/075-painel-hse.md) |
| ISSUE-076 | Parâmetros: edição por grupo com justificativa, versões e histórico | Task | proposed | ready-for-agent | ISSUE-066 | [Issue file](issues/spec-migracao-gestnow/076-configuracoes-parametros.md) |
| ISSUE-077 | Colaboradores: perfil geral, papéis na Programação Semanal por projeto, vínculo e empresa | Task | proposed | ready-for-agent | ISSUE-054 | [Issue file](issues/spec-migracao-gestnow/077-configuracoes-colaboradores.md) |
| ISSUE-078 | Cadastros de apoio: empresas, pessoas, projetos, sistemas, unidades e locais | Task | proposed | ready-for-agent | ISSUE-054 | [Issue file](issues/spec-migracao-gestnow/078-configuracoes-cadastros-de-apoio.md) |
| ISSUE-079 | Início do projeto: indicador-chave por módulo e pontos de atenção | Task | proposed | ready-for-agent | ISSUE-020, ISSUE-026, ISSUE-035, ISSUE-040, ISSUE-042, ISSUE-050, ISSUE-063, ISSUE-066, ISSUE-071, ISSUE-075 | [Issue file](issues/spec-migracao-gestnow/079-inicio-do-projeto.md) |
| ISSUE-080 | Início no Portfólio: carteira de projetos e edição da ponderação | Task | proposed | ready-for-agent | ISSUE-079 | [Issue file](issues/spec-migracao-gestnow/080-inicio-no-portfolio-e-ponderacao.md) |
| ISSUE-081 | Análise do período de 02, 03 e 04, com desvios negativos e comentários obrigatórios | Task | proposed | ready-for-agent | ISSUE-040, ISSUE-042, ISSUE-044, ISSUE-048, ISSUE-063 | [Issue file](issues/spec-migracao-gestnow/081-analise-do-periodo-02-03-04.md) |
| ISSUE-082 | Análise do período de 05, 06, 07 e do Portfólio | Task | proposed | ready-for-agent | ISSUE-081, ISSUE-066, ISSUE-071, ISSUE-075 | [Issue file](issues/spec-migracao-gestnow/082-analise-do-periodo-05-06-07-e-portfolio.md) |
| ISSUE-083 | Relatório gerencial: modal, motor de corte e folhas de Planejamento | Task | proposed | ready-for-agent | ISSUE-082, ISSUE-044 | [Issue file](issues/spec-migracao-gestnow/083-relatorio-gerencial-modal-corte-e-planejamento.md) |
| ISSUE-084 | Relatório: folhas Financeiro (com a linha de tendência) e Suprimentos | Task | proposed | ready-for-agent | ISSUE-083 | [Issue file](issues/spec-migracao-gestnow/084-relatorio-financeiro-e-suprimentos.md) |
| ISSUE-085 | Relatório: folhas Riscos, Qualidade, HSE e Carteira de projetos | Task | proposed | ready-for-agent | ISSUE-084, ISSUE-080 | [Issue file](issues/spec-migracao-gestnow/085-relatorio-riscos-qualidade-hse-e-carteira.md) |
| ISSUE-086 | Relatório: Excel, Imprimir / PDF e Alterar período | Task | proposed | ready-for-agent | ISSUE-085 | [Issue file](issues/spec-migracao-gestnow/086-relatorio-excel-impressao-e-alterar-periodo.md) |
| ISSUE-087 | Inglês, parte 1: catálogo no servidor, seletor PT / EN, shell, Início, Central, Governança e Financeiro | Task | proposed | ready-for-agent | ISSUE-086, ISSUE-078 | [Issue file](issues/spec-migracao-gestnow/087-ingles-parte-1.md) |
| ISSUE-088 | Inglês, parte 2: Planejamento, Programação Semanal, Suprimentos, Riscos, Qualidade, HSE, Configurações e relatório | Task | proposed | ready-for-agent | ISSUE-087 | [Issue file](issues/spec-migracao-gestnow/088-ingles-parte-2.md) |
| ISSUE-089 | Oráculo de paridade completo e prova do cálculo vivo | Task | proposed | ready-for-agent | ISSUE-088 | [Issue file](issues/spec-migracao-gestnow/089-oraculo-de-paridade-e-calculo-vivo.md) |
| ISSUE-090 | Varredura de todas as telas nas três larguras | Task | proposed | ready-for-agent | ISSUE-089 | [Issue file](issues/spec-migracao-gestnow/090-varredura-de-todas-as-telas.md) |
| ISSUE-091 | Exportações tela a tela, acessibilidade e roteiro manual | Task | proposed | ready-for-agent | ISSUE-090 | [Issue file](issues/spec-migracao-gestnow/091-exportacoes-acessibilidade-e-roteiro-manual.md) |
| ISSUE-092 | Pronto para publicar no Azure | Task | proposed | ready-for-agent | ISSUE-091 | [Issue file](issues/spec-migracao-gestnow/092-pronto-para-publicar-no-azure.md) |
| ISSUE-093 | Consolidação dentro do GestNow e desativação das pastas de origem | Task | proposed | ready-for-agent | ISSUE-092 | [Issue file](issues/spec-migracao-gestnow/093-consolidacao-e-desativacao-das-pastas-de-origem.md) |
