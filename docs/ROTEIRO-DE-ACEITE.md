# Roteiro manual de aceite do Timenow GestNow

> Documento da ISSUE-091 (Entrega 9, validação final). É o passo a passo para o
> **dono do produto** aceitar o GestNow executando o app no navegador: o que
> abrir, o que fazer e **o que deve aparecer** em cada módulo e em cada tela.
> Cobre também as revisões que ficam com o dono (Q30 e Q31), a conciliação das
> pendências de fonte e a publicação no Azure, e fecha com as conferências
> transversais (exportações, acessibilidade e varredura de telas).
>
> Este roteiro **não substitui** a porta de qualidade (`npm run verificar`) nem
> os testes; ele é o aceite de gente. O inventário das exportações está em
> [`EXPORTACOES.md`](./EXPORTACOES.md); a auditoria de acessibilidade, em
> [`ACESSIBILIDADE.md`](./ACESSIBILIDADE.md); a publicação no Azure, no guia da
> ISSUE-092, [`PUBLICACAO-AZURE.md`](./PUBLICACAO-AZURE.md).

---

## 1. Como entrar

### 1.1 Subir o app

1. Confira que o serviço do Postgres está rodando e que a variável de usuário
   `GESTNOW_PG_ADMIN_URL` existe (o `run.bat` explica se faltar).
2. Dê dois cliques no **`run.bat`**. Ele prepara o banco, aplica as migrações,
   grava a carga do modo configurado, sobe a API e **abre o navegador** em
   `http://localhost:4280`.
3. Sem `GESTNOW_MODO` definido, o modo é **demonstração** — é o modo deste
   roteiro. A carga de demonstração grava os dados do protótipo com **todas as
   datas deslocadas até hoje**, e rodar de novo não duplica nada.

**Deve aparecer:** o shell do GestNow com a barra lateral à esquerda (marca,
seletor de escopo, seletor de perfil da demonstração, PT | EN, os módulos,
"API online" e o cartão do usuário) e o **Início** carregado.

> Se o seletor de perfil não aparecer, você não está em demonstração (ou há um
> login Microsoft de verdade): pare e confira o modo antes de seguir.

### 1.2 A barra lateral e o trilho

1. Acima de 1100 px, a barra fica cheia. Clique no botão de recolher no topo
   dela e passe o mouse (ou foque com Tab) em cada ícone.
2. Estreite a janela do navegador até menos de 1100 px.

**Deve aparecer:** no trilho, só os ícones, com **dica** ao passar o mouse ou
focar (o nome do item e o significado da sigla); a barra **nunca some** — nem
no trilho nem em 760 px. O botão de recolher volta a expandir.

### 1.3 O escopo: Portfólio × projeto

1. No seletor **Escopo**, veja as opções: `Portfólio (3 projetos)` e os três
   projetos da demonstração (`TN-2026-014 · Construção de uma nova fábrica`,
   `TN-2026-021 · Construção de uma nova caldeira de biomassa` e
   `TN-2026-027 · Construção de uma nova torre de resfriamento`).
2. Troque para um projeto e volte para o Portfólio. Navegue entre módulos nos
   dois escopos.

**Deve aparecer:** o escopo escolhido viaja no endereço (`?projeto=...`) e
vale para todas as telas; sem escolha, o padrão é o **Portfólio**. As telas
consolidadas mudam de recorte (carteira, coluna Projeto, totais), e as telas de
um projeto só fazem sentido nele (EAP, EAC, Programação Semanal, ficha de
contrato etc.). No Portfólio, telas que pedem um projeto avisam ou pedem o
projeto antes de abrir o formulário.

### 1.4 O seletor de perfil (modo demonstração)

1. No seletor **Perfil (demonstração)**, escolha **leonardo.gomes — Admin —
   Timenow** (o padrão) e, depois, **Cliente Horizonte — Visualizador —
   Cliente** (`visualizador@cliente.demo`) e um fornecedor, por exemplo
   **Fabio Teixeira — Membro — Fornecedor**.
2. Em cada perfil, olhe a barra lateral e tente abrir uma tela fora do que ele
   alcança.

**Deve aparecer:**

- **Admin:** todos os módulos e telas, Configurações inclusive.
- **Visualizador (do cliente):** vê os módulos (as telas de leitura), mas
  **não abre Configurações**; as ações de escrita não aparecem ou são recusadas
  (403 com a mensagem no lugar).
- **Fornecedor:** a barra mostra **só a Programação Semanal** (o Início o
  entrega lá); tentar uma tela fora disso mostra a tela de **Acesso negado**
  do Design System, com o Voltar.
- A escolha vale na requisição seguinte e fica no cookie `gestnow_demo_perfil`.

### 1.5 O idioma PT | EN

1. Com a tela do Início aberta, clique em **EN** na barra lateral; depois volte
   para **PT**.

**Deve aparecer:** a tela recarrega **traduzida no servidor** (rótulos,
títulos, colunas, gráficos, exportações Excel e PDF), a semana vira `W38`, os
meses e datas seguem o idioma; **número e moeda continuam pt-BR**
(`R$ 1.234,56`). A escolha fica no cookie `gestnow_idioma`. Alguns rótulos
compostos dentro dos serviços de Riscos, Qualidade, HSE e Suprimentos seguem em
português no inglês — isso é uma divergência **registrada**
(`DIVERGENCIAS-DO-PROTOTIPO.md`), não um defeito novo.

### 1.6 O mapa do roteiro (cobertura da navegação)

Esta é a lista que o roteiro cobre — os 10 módulos da navegação e as **51
telas** (`api/src/core/navegacao.json`). Marque cada tela vista:

| Módulo | Tela | Seção |
|---|---|---|
| Início | Início | 3.1 |
| Início | Relatório gerencial (detalhe do Início) | 3.2 |
| Central de Ações | Ações | 4.1 |
| Central de Ações | Dashboards e KPIs | 4.2 |
| Central de Ações | Atas | 4.3 |
| Central de Ações | Ata (detalhe das Atas) | 4.4 |
| Planejamento | EAP | 5.1 |
| Planejamento | Curva S | 5.2 |
| Planejamento | KPIs | 5.3 |
| Planejamento | Relato do período | 5.4 |
| Planejamento | 6WLA | 5.5 |
| Planejamento | Produtividade | 5.6 |
| Planejamento | Punch list | 5.7 |
| Planejamento | Programação (grupo Programação Semanal) | 6.1 |
| Planejamento | Dashboard da programação (grupo) | 6.2 |
| Planejamento | Governança da programação (grupo) | 6.3 |
| Planejamento | Importação e impressão (grupo) | 6.4 |
| Planejamento | Configuração da programação (grupo) | 6.5 |
| Gestão Financeira | EAC | 7.1 |
| Gestão Financeira | Mapa de controle | 7.2 |
| Gestão Financeira | Cronograma de desembolso | 7.3 |
| Gestão Financeira | KPIs de custo | 7.4 |
| Gestão Financeira | Curva S financeira | 7.5 |
| Gestão Financeira | Contingência | 7.6 |
| Gestão Financeira | Contratos | 7.7 |
| Gestão Financeira | Contrato (detalhe dos Contratos) | 7.8 |
| Suprimentos | Painel de suprimentos | 8.1 |
| Suprimentos | Plano de compras | 8.2 |
| Suprimentos | Processos de compra | 8.3 |
| Suprimentos | Mapa de Suprimentos (MAS) | 8.4 |
| Suprimentos | Diligenciamento e recebimento | 8.5 |
| Suprimentos | Fornecedores | 8.6 |
| Gestão de Riscos | Registro de riscos | 9.1 |
| Gestão de Riscos | Matriz de riscos 5x5 | 9.2 |
| Gestão de Riscos | Ficha do risco (detalhe do Registro) | 9.3 |
| Gestão de Riscos | Painel de riscos | 9.4 |
| Gestão da Qualidade | Painel da qualidade | 10.1 |
| Gestão da Qualidade | Não conformidades (RNC) | 10.2 |
| Gestão da Qualidade | Inspeções e ITP | 10.3 |
| Gestão da Qualidade | Auditorias | 10.4 |
| HSE | Painel HSE | 11.1 |
| HSE | Ocorrências | 11.2 |
| HSE | Inspeções e observações | 11.3 |
| HSE | Análises de risco (APR/HAZOP) | 11.4 |
| HSE | Horas trabalhadas (HHT) | 11.5 |
| Governança | Gestão de mudanças | 12.1 |
| Governança | Solicitação de mudança (detalhe das Mudanças) | 12.2 |
| Governança | Lições aprendidas | 12.3 |
| Configurações | Parâmetros do sistema | 13.1 |
| Configurações | Colaboradores | 13.2 |
| Configurações | Cadastros de apoio | 13.3 |

**Números de referência da demonstração** (para reconhecer a carga): os três
projetos acima, com orçamento de aproximadamente R$ 44,6 mi, R$ 18,2 mi e
R$ 7,4 mi; os pesos da carteira em 55,36% / 29,34% / 15,30%; o projeto
`TN-2026-014` é o principal (é nele que a Programação Semanal, o contrato
`CT-2026-...` e o PC-14 das compras aparecem cheios). Vários números "de
atraso" mudam com a data de hoje — a carga é deslocada para hoje —, então
confira a coerência com a data de referência mostrada na tela, não um número
fixo.

---

## 2. Como usar este roteiro

- Cada módulo tem os passos na ordem de conferência, com **o que deve
  aparecer** logo abaixo. Marque o `[ ]` quando passar.
- As telas com **Excel** e **PDF** (ou "Imprimir / PDF") saem pelos mecanismos
  genéricos: o Excel abre com as colunas da tela e os KPIs com a referência; o
  PDF é a versão imprimível, **sem a navegação**, aberta pela impressão do
  navegador. O inventário tela a tela está em `docs/EXPORTACOES.md`; o que
  faltar lá, anote.
- As telas de **detalhe** (Ata, Contrato, Ficha do risco, Solicitação de
  mudança e o Relatório gerencial) não têm aba: a barra destaca o módulo de
  origem e o **Voltar** leva à lista.
- Toda recusa de operação (422, 409, 403) aparece **no próprio lugar** (campo
  ou modal), nunca em página de erro.

---

## 3. Início (e Relatório gerencial)

Perfil: **Admin** (para a ponderação) e depois **Visualizador** (leitura).

### 3.1 Início

1. Abra **Início** (o item do topo da barra; a rota `/`).
2. Confira a barra de contexto no projeto `TN-2026-014`: projeto, data de
   referência (hoje), orçamento e término previsto. No Portfólio, a etiqueta
   vira "Portfólio de projetos · 3 projetos".
3. Percorra os **oito indicadores-chave** (ações atrasadas, SPI, CPI, pedidos
   críticos, riscos críticos, RNC abertas, dias sem afastamento, mudanças
   aguardando comitê) e leia a referência de gestão de cada um.
4. Clique em dois ou três indicadores e depois num **ponto de atenção** e num
   **card de módulo**.

**Deve aparecer:** cada clique abre a **tela dona do dado**, já filtrada pela
leitura do indicador; os pontos de atenção são calculados na data de referência
(nível danger/warning e o link); os oito cards trazem o selo resumido do módulo.
O **Excel** e o **PDF** da tela baixam o resumo com os KPIs e a referência; o
botão **Relatório gerencial** da barra de contexto abre a tela do relatório já
com o modal de emissão (seção 3.2).

5. No **Portfólio**, confira a **Carteira de projetos**: uma linha por projeto,
   do maior peso para o menor, com peso, orçamento (BAC), avanço real x
   previsto, SPI e CPI com a cor da faixa, projeção no término com o VAC,
   término pela tendência e LB, riscos no topo, pedidos críticos, ações
   atrasadas, situação e **Abrir**; o rodapé "Portfólio" com as somas e os
   índices consolidados.
6. Ainda no Portfólio e como **Gestor/Admin**, clique em **Ponderação**:
   altere um peso ou uma nota, clique em **Prévia** e depois em **Gravar**, com
   a justificativa (mínimo de 10 caracteres).

**Deve aparecer:** a prévia recalcula os pesos resultantes **sem gravar**; a
gravação cria uma **versão nova** do grupo `portfolio` dos parâmetros, fecha o
modal e atualiza a carteira; a linha da trilha guarda o antes e o depois. Com o
perfil **Membro**, tentar gravar recebe 403.

7. Abra a **Carteira** no **Excel/PDF**: o VAC aparece em coluna própria, por
   projeto e no total.

### 3.2 Relatório gerencial

1. No **Início**, clique no botão **Relatório gerencial** da barra de contexto
   (ao lado do Excel e do PDF; ele abre a tela já com o modal de emissão — o
   endereço direto `http://localhost:4280/relatorio/gerencial?relatorio=1`
   também serve, e o **Voltar** da barra traz de volta ao Início).
2. No modal **Emitir relatório**, escolha **Relatório de** (Portfólio ou
   projeto), **Tipo** (Semanal ou Mensal) e **Período** (o padrão é o período
   anterior; o corrente sai marcado como parcial). Leia a **situação** do
   relato e da análise de cada módulo, com os links para registrar.
3. Clique em **Emitir relatório**.

**Deve aparecer:** as folhas **A4 na horizontal**, uma por seção — no
Portfólio, a **Carteira de projetos** como primeira folha; depois Planejamento
(duas: posição/Curva S/produtividade e análise + relato do período),
Financeiro, Suprimentos, Riscos, Qualidade e HSE. Cada folha traz a análise do
período e, sem comentário de desvio, "Comentário pendente"; sem relato ou
análise, o aviso com o link. A fonte encaixa até caber (mínimo 6,4 pt), sem
cortar a folha.

4. Clique em **Imprimir / PDF** e confira a prévia da impressão do navegador:
   uma folha por página, **sem a navegação**. Salve como PDF ou imprima.
5. Clique em **Excel** e abra a planilha.

**Deve aparecer:** a aba **Resumo** com os indicadores de todas as folhas
prefixados pela folha, uma aba por tabela exibida, mais "Análises do período" e
"Desvios negativos e comentários"; colunas tipadas (dinheiro, percentual,
data, inteiro), não texto solto.

6. Clique em **Alterar período** e mude o mês; emita de novo.

---

## 4. Central de Ações

Perfil: **Membro/Gestor** para replanejar e concluir; o Visualizador vê.

### 4.1 Ações

- [ ] Abra **Central de Ações > Ações**.
- [ ] Clique nos KPIs (Em dia, Atrasadas, Concluídas, Total) e confira que cada um filtra a lista.
- [ ] Abra os **filtros** (busca, origem, status, responsável), aplique e remova os chips.
- [ ] Alterne **lista** e **kanban** por status.
- [ ] Numa ação atrasada, use **Replanejar** sem justificativa (deve recusar) e com justificativa; depois **Histórico**.
- [ ] Numa ação aberta, use **Concluir** com a data (data futura é recusada).
- [ ] Baixe **Excel** e **PDF** do filtro de agora.
- [ ] No Portfólio, confira a coluna Projeto.

**Deve aparecer:** o status é calculado (Concluída por data de conclusão;
Atrasada quando o prazo vigente passou da data de referência; senão Em
andamento), a origem de cada ação abre a ficha que a criou, e o replanejamento
guarda autor, data, de/para e justificativa.

### 4.2 Dashboards e KPIs

- [ ] Abra **Dashboards e KPIs**; filtre por origem.
- [ ] Percorra os cinco indicadores (Total, Em dia, Atrasadas, Concluídas, Concluídas no prazo original) e os quatro gráficos.
- [ ] Confira a tabela **Desempenho por responsável** (e **Status por projeto** no Portfólio).
- [ ] Clique em **Enviar follow-up** (na tela Ações): o modal mostra quem recebe o quê; envie.

**Deve aparecer:** as contagens batem com as da lista no mesmo escopo; o
follow-up registra uma notificação por responsável e, com o envio de e-mail
desligado, a tela avisa **"simulado"** (e quem não tem e-mail é nomeado, nunca
ignorado).

### 4.3 Atas

- [ ] Abra **Atas**: a lista mostra **só a revisão mais recente** de cada ata (Número, Rev, Data, Assunto, Empresa principal, Tipo, Ações abertas e atrasadas).
- [ ] Busque, pagine, baixe **Excel** e **PDF**.
- [ ] Clique em **Gerar nova ata** (no Portfólio, o botão pede o projeto antes) e preencha.

**Deve aparecer:** a ata nasce numerada pela sequência do projeto
(`TN-2026-NNNN`, sem buraco), com o autor na lista de presença e a empresa
principal entre as executoras.

### 4.4 Ata (detalhe)

- [ ] Abra uma ata da lista. Na ficha, percorra as abas **Dados da Reunião**, **Lista de Presença** e **Anotações e Ações**.
- [ ] Adicione uma anotação (Informação) e uma ação (`Ação`), com responsável e data.
- [ ] Use **Histórico da ata** e **Gerar nova revisão**; abra a revisão anterior (somente leitura).
- [ ] Tente **Retirar participante** de quem tem ação aberta na ata.
- [ ] Baixe **Excel/PDF** da ficha (dados, empresas, presença, itens).

**Deve aparecer:** os itens são numerados por grupo (1, 1.1...), a ação aparece
na **lista da Central** com origem Ata e link de volta (a anotação, não); a
retirada é recusada com a mensagem quando há ação aberta; a revisão nova copia
listas e itens e a anterior fica só de leitura.

---

## 5. Planejamento

Perfil: **Membro** executa, **Gestor** aprova/reverte. O fornecedor não
alcança o módulo.

### 5.1 EAP

- [ ] Abra **Planejamento > EAP**: leia os KPIs (avanço real com desvio, pacotes com linha de base, término vencido, SMs a incorporar) e recolha/expanda a árvore áreas/subáreas/pacotes.
- [ ] Abra o **dicionário** de um pacote (descrição, entregável, aceitação, empresa, responsável, item da EAC e o histórico de medições).
- [ ] Em **Registrar avanço**, informe as entradas do critério e grave; tente um **estorno** com perfil Membro (deve dar 403) e com Gestor + justificativa.
- [ ] Use **Importar avanço**: baixe o modelo, envie uma planilha, confira linha a linha e confirme.
- [ ] Como Gestor, abra **Nova revisão**, **Novo pacote** (a origem do peso: desdobramento de um pacote de planejamento ou inclusão por nova revisão) e **Importar pacotes**.
- [ ] Baixe **Excel** e **PDF**; no Portfólio, confira a árvore somente leitura com a coluna Projeto.

**Deve aparecer:** o avanço do pacote sai do critério (Etapas, Unidades, Marco
0/100, Marco 50/50, Percentual estimado) e o real nunca regride sem estorno; a
regra dos 100% fecha os pesos no servidor; revisão só nasce de **SM aprovada
com impacto em escopo**; o 422 marca o campo e devolve o formulário preenchido.

### 5.2 Curva S

- [ ] Abra **Curva S**: KPIs (previsto acumulado com a referência "100% em tal mês", real, desvio em p.p., SPI e término pela tendência).
- [ ] Use o **drill** do gráfico (ano, mês e semana).
- [ ] Confira a **tabela período a período** com o mês do corte destacado e, no Portfólio, a composição da carteira.
- [ ] **Experimento do cálculo vivo:** volte à EAP, registre uma medição nova e reabra a Curva S.

**Deve aparecer:** a curva muda **na consulta seguinte**, sem passo de
recálculo; a linha de base vem congelada da revisão vigente da EAP e o real,
das medições. Excel e PDF saem com KPIs, gráfico e tabela.

### 5.3 KPIs

- [ ] Abra **KPIs**: faixa de indicadores (SPI com a meta 1,00, previsto x real, desvio, maior desvio por área, vencidos, SMs a incorporar).
- [ ] Confira os gráficos **SPI por mês** (com a meta) e **previsto x real por área** e a tabela de avanço por área com o rodapé ponderado.
- [ ] No Portfólio, confira as linhas por projeto com peso.
- [ ] Use o botão **Análise do período** (abre o modal do módulo `relatorio`).

**Deve aparecer:** a tabela fecha com a **Curva S** (mesma média ponderada); o
botão abre a análise do 02 no corte, com os desvios detectados.

### 5.4 Relato do período

- [ ] Abra **Relato do período**: KPIs (semana e mês anterior registrados ou pendentes, pontos de atenção e relatos registrados).
- [ ] Filtre **Todos / Semanais / Mensais** e busque.
- [ ] Use **Novo**, **Editar**, **Ver**, **Copiar do período anterior** e **Excluir** (Gestor).
- [ ] Grave um relato com atividades e pontos de atenção; tente um período futuro (deve recusar).
- [ ] Baixe **Excel** e **PDF**.

**Deve aparecer:** um relato por projeto, tipo e período; a cópia traz o
próximo período do relato anterior **sem gravar**; o período recusado mostra a
mensagem no campo.

### 5.5 6WLA

- [ ] Abra **6WLA**: indicadores (atividades no horizonte, prontas nas 2 próximas semanas, restrições abertas, vencidas e índice de remoção).
- [ ] Confira a **grade das seis semanas** seguintes à semana corrente e o filtro (busca, disciplina, só com restrição aberta).
- [ ] Crie uma restrição e depois **remova** com data e comentário; tente remover de novo.
- [ ] No Portfólio, confira a coluna Projeto e baixe **Excel/PDF**.

**Deve aparecer:** a semana programada de atividade com restrição aberta fica
marcada; restrição vencida é a aberta com data necessária anterior à
referência; a segunda remoção é recusada.

### 5.6 Produtividade

- [ ] Abra **Produtividade**, aba **Quantidades**: filtros (Empresa, Semana de corte, Grupo), o aviso dos itens com LB em elaboração, os KPIs (avanço com SPI, aderência, FP, pendentes, tendência) e os gráficos Produção semanal e Avanço acumulado. Use **Apontar semana**, **Novo item da LB** e **Importar Excel**.
- [ ] Aprove uma LB em elaboração como Gestor e tente aprovar a sua própria (quem elaborou não aprova: 403).
- [ ] Aba **Horas efetivas**: alterne **Capacidade produtiva**, **Amostragem do trabalho** e **Paralisações**; registre uma jornada, uma rodada de observação e uma paralisação (repare no aviso do pleito quando a responsabilidade não é da contratada).
- [ ] Use o filtro Período (semana de corte, últimas N semanas ou desde o início) e baixe **Excel/PDF** de cada visão.
- [ ] Aba **KPIs de performance**: confira os indicadores, a tabela **Performance por empresa** com as faixas, a **Tendência semanal** e os gráficos; use **Gerar plano de ação** numa empresa em alerta e tente repetir (deve recusar).

**Deve aparecer:** a LB em elaboração fica fora dos indicadores até a
**aprovação** (que congela a distribuição); mudar total/semanas/perfil exige
**SM aprovada** e revisão; o plano de ação cria a ação na **Central** (origem
Produtividade) e o link aparece na linha; a segunda ação da mesma empresa e
semana recebe 422.

### 5.7 Punch list

- [ ] Abra **Punch list**, aba **Lista**: indicadores clicáveis (Abertos, Categoria A abertos, Aguardando verificação, Vencidos, Fechados), a tabela com o link da ação na Central e as ações do fluxo por linha.
- [ ] Use os filtros (busca, situação, categoria, sistema, disciplina, empresa, vencidos) e **Novo item** e **Importar Excel**.
- [ ] Num item aberto, faça **Tratar** → **Enviar para verificação** → **Verificar**: aprove com **anexo** e depois teste reprovar; teste verificar com quem executou (deve dar 403) e fechar sem evidência (recusa).
- [ ] **Cancele** um item com justificativa.
- [ ] Na **Central de Ações**, conclua a ação de um item e volte: o item deve ter fechado; replaneje a ação e veja o prazo do item mudar.
- [ ] Abra a aba **Painel**: o alerta de sistemas bloqueados, os indicadores de sistemas liberados por marco, o **burndown**, o **aging**, as contagens por disciplina e empresa e a tabela de sistemas.

**Deve aparecer:** item de categoria **A** aberto bloqueia o sistema no marco
vinculado e nos seguintes; o aceite definitivo é bloqueado por qualquer item
aberto; o verificador nunca é o executante; a ação e o item ficam
sincronizados nos dois sentidos. Excel e PDF saem nos dois filtros (lista e
painel).

---

## 6. Programação Semanal

Escolha **um projeto** no escopo (no Portfólio a tela é somente leitura) e
troque para um **Fornecedor** no seletor de perfil para ver o recorte.

### 6.1 Programação

- [ ] Abra **Programação** (a aba do grupo dentro de Planejamento, com as subabas).
- [ ] Leia a faixa da **janela** (aberta ou fechada, com o motivo) e a **semana** em foco; a matriz vai de segunda a domingo com previsto e realizado.
- [ ] Como Fornecedor (Fabio Teixeira, projeto 1), crie/edite uma atividade dentro da janela; tente editar fora dela (deve recusar).
- [ ] Como Planejador, **valide** e defina o fiscal; como Encarregado/Fornecedor, **lance o realizado** por turno (dia e noite) usando os atalhos "= previsto" e "copiar a semana"; force um desvio acima do limite (a observação passa a ser obrigatória).
- [ ] Como Fiscal, **aprove** o realizado e depois **reabra** com motivo; como Planejador, **publique** (e use "Publicar as validadas").
- [ ] Num item publicado ou aprovado, abra **Pedir alteração** com o motivo (mínimo de 10 caracteres).

**Deve aparecer:** cada linha mostra o **botão da próxima ação** de quem está
olhando (validar → lançar → aprovar → publicar → ver) e o menu só com o que o
perfil pode fazer; situação da programação e aprovação do realizado são estados
distintos (uma atividade publicada pode ter realizado pendente); lançar só
sobre programação validada; o realizado aprovado não muda mais sem pedido
aplicado. O fornecedor vê **só a própria empresa**.

### 6.2 Dashboard da programação

- [ ] Abra **Dashboard da programação**; filtre por semana, contratada, frente e encarregado.
- [ ] Percorra a curva S do avanço, o previsto x realizado, a evolução da aderência por contratada (com drill), as distribuições, os rankings, o mapa de calor dia x frente, os turnos e os gargalos.
- [ ] Baixe **Excel** (com o Resumo) e **PDF**.

**Deve aparecer:** os gráficos vêm da biblioteca do Design System e o mês é do
calendário da plataforma; o fornecedor vê só a própria empresa (e nem o seletor
de contratada aparece); semana vazia e filtro vazio são estados distintos.

### 6.3 Governança da programação

- [ ] Abra **Governança da programação**: indicadores, janelas com o motivo, a lista de controle por contratada/semana.
- [ ] Abra a **fila de pedidos** (pendentes e resolvidos) e **aplique** um pedido; depois abra outro e **recuse** com resposta.
- [ ] Abra a **trilha** (só Planejador no projeto ou Admin).
- [ ] Baixe **Excel/PDF** do painel e da fila.

**Deve aparecer:** aplicar um pedido **reabre** a atividade (se o realizado
estava aprovado, volta a pendente) e o efeito fica na trilha com antes e
depois; recusar exige resposta; o fornecedor só vê os pedidos da própria
empresa.

### 6.4 Importação e impressão

- [ ] Abra **Importação e impressão**: baixe o **modelo** (.xlsx), preencha duas linhas (`Prev.` e `Real.`) e envie.
- [ ] Confira a **conferência linha a linha** (o que cada linha vai fazer, sem gravar) e confirme.
- [ ] Baixe o **Excel da semana** e o **relatório** (PDF).

**Deve aparecer:** a confirmação grava **tudo ou nada** com o digest do
arquivo; o Excel tem as abas do app (Resumo, Programação com duas linhas por
atividade, Por contratada, Por frente, Por encarregado, Dia a dia e Curva S);
o relatório sai sem navegação. O fornecedor e o Visualizador recebem 403.

### 6.5 Configuração da programação

- [ ] Abra **Configuração da programação**: parâmetros (meta de aderência 60, meta de PPC 75, semana de referência, regra de desvio de 15%) e as janelas por empresa.
- [ ] Como Planejador no projeto (ou Admin), mude um parâmetro com o antes/depois na trilha e grave uma janela (dias, semanas, liberação extraordinária).
- [ ] Recarregue a **Programação** e confira que a mudança **vale na hora**.
- [ ] No Portfólio, confira o aviso de escolher um projeto; entre como Planejador de outro projeto e verifique o 403.

**Deve aparecer:** a gravação dos parâmetros e da janela deixa a **trilha com o
antes e o depois**; o fornecedor só vê a janela da própria empresa.

---

## 7. Gestão Financeira

Perfil: **Gestor/Admin** para revisões e aprovações; o Visualizador lê.

### 7.1 EAC

- [ ] Abra **EAC**: a árvore (linha 0, pacote, subpacote, item) com filtros (busca, nível, tipo de custo) e o total filtrado.
- [ ] Abra os painéis **Revisões do orçamento** e **Remanejamentos**.
- [ ] Edite o cadastro de um item (descrição, tipo, CAPEX/OPEX, centro de custo, responsável) com justificativa.
- [ ] Use **Remanejar** (origem com saldo livre, destino, valor, justificativa) e veja a SM nascer na Governança; **Novo item** por remanejamento e por nova revisão; **Importar itens** por planilha.
- [ ] Como Gestor, crie uma **Nova revisão** a partir de uma SM aprovada com custo.
- [ ] No Portfólio, confira a árvore somente leitura com a coluna de peso.

**Deve aparecer:** os valores agregados são calculados (base, remanejamento,
comprometido, realizado, projeção); **toda alteração de valor passa por SM** —
até a decisão, o valor fica reservado na origem como pendente; a aprovação
aplica na mesma transação; Excel/PDF levam a árvore e os dois painéis.

### 7.2 Mapa de controle

- [ ] Abra **Mapa de controle**: os cinco KPIs (orçado atual, comprometido, realizado, projeção no término, desvio) e a grade item a item com o **mapa de calor** do desvio (sempre com sinal, ícone e faixa — a cor não é o único sinal).
- [ ] Clique num item e registre uma **Projeção no término** com justificativa; tente valor negativo ou abaixo do realizado (recusa).
- [ ] Use **Importar custos do ERP**: confira a planilha sem gravar e confirme.
- [ ] Baixe **Excel** e **PDF** (valores integrais, com subtotais e a faixa Reservas).

**Deve aparecer:** a projeção vira fato manual datado no histórico do item e o
fato mais recente vale (no empate, o do ERP vence); sem fato, vale o orçado
atual.

### 7.3 Cronograma de desembolso

- [ ] Abra **Cronograma de desembolso**: os quatro indicadores (realizado até o corte, saldo a desembolsar, próximos 3 meses e mês de corte) e o gráfico das três séries.
- [ ] Troque **Mostrar até** 1/2/3 e confira a tabela saldo a pagar por mês, item a item, com o total no pé.
- [ ] Clique em **Enviar à tesouraria**, leia o modal e envie.

**Deve aparecer:** a soma dos meses de cada item é exatamente o saldo; o envio
fica **simulado** na trilha enquanto o e-mail está desligado, e a tela diz
isso; no Portfólio ou sem cronograma, o envio é recusado com mensagem.

### 7.4 KPIs de custo

- [ ] Abra **KPIs de custo**: os cartões (CPI, SPI de custo, CV, VAC, contingência consumida, comprometido), os gráficos de CPI/SPI com a meta 1,00 e do valor agregado (PV, EV, AC) e a tabela-resumo (BAC, PV, EV, AC, CV, SV, EAC pelo CPI, projeção no término, VAC, TCPI).
- [ ] Percorra a tabela período a período com os índices acumulados.
- [ ] Use **Análise do período** e baixe **Excel/PDF**.

**Deve aparecer:** no Portfólio, PV, EV e AC somam os projetos e o CPI/SPI saem
da soma; a tabela **Desempenho de custo por projeto** traz a coluna Projeto.

### 7.5 Curva S financeira

- [ ] Abra **Curva S financeira**: os quatro indicadores do corte e o gráfico com as quatro séries (planejado, comprometido, realizado e tendência).
- [ ] Confira a tabela período a período com o mês do corte destacado.
- [ ] Use **Análise do período** e baixe **Excel/PDF**.

**Deve aparecer:** só o planejado é congelado por revisão; comprometido,
realizado e tendência são calculados dos fatos; a tendência parte do realizado
do mês e não usa dado posterior ao corte.

### 7.6 Contingência

- [ ] Abra **Contingência**: os cinco indicadores (saldo, consumo com o limite, pedido em SMs em análise, cobertura da exposição com o link do painel de riscos, reserva gerencial), os alertas e o gráfico do saldo real x previsto.
- [ ] Percorra a composição (orçado da EAC + contingência = linha de base; + reserva gerencial = orçamento), o extrato de movimentos (com a SM e a situação) e a tabela **Ameaças ativas e cobertura**.
- [ ] No Portfólio, confira a tabela Reservas por projeto com o total.

**Deve aparecer:** a tela é só de leitura — o consumo e a liberação se pedem
pela SM, na Governança; o consumo acima do saldo e a liberação acima do saldo
menos o pedido são recusados lá; a cobertura só considera **ameaças ativas**.

### 7.7 Contratos

- [ ] Abra **Contratos**: os seis cartões (Contratos, Exposição de claims, Notificados fora do prazo, Marcos atrasados, Extensão de prazo, Contratadas C ou D) e as cinco abas com contador.
- [ ] Aplique o filtro de busca e a seleção de contrato; confira que os KPIs **não** filtram.
- [ ] Baixe **Excel/PDF** do filtro (no Portfólio, com a coluna Projeto).

**Deve aparecer:** a tela não tem botões de inclusão — o contrato nasce na
adjudicação de Suprimentos e os registros das abas, na ficha do contrato.

### 7.8 Contrato (detalhe)

- [ ] Abra um contrato pela lista (`?numero=CT-...`): a faixa de identificação e as abas **Resumo** (4 KPIs, cascata de valor, anexos), **Medições**, **Aditivos**, **Marcos de pagamento**, **Claims**, **Extensões de prazo** e **Avaliação de desempenho**.
- [ ] Numa medição, percorra o fluxo Em análise → Aprovada → Faturada → Paga; abra outra e **devolva** com motivo.
- [ ] Registre um **aditivo** (valor negativo é supressão; os dias prorrogam o término).
- [ ] Num marco, envie a **evidência** (arquivo de verdade) e aprove; confira o atraso dos pendentes.
- [ ] Abra um claim: notificação fora do prazo alerta; ao **Acordar**, a SM nasce na Governança e o vínculo aparece; veja o risco vinculado.
- [ ] Numa EOT, **conceda** dias e veja a SM da linha de base.
- [ ] Registre uma **Avaliação de desempenho** (nota baixa exige evidência e abre ação; a final abre a lição).

**Deve aparecer:** cada aba tem **Excel** e **PDF** próprios; o 422 volta no
formulário e o 409 no mesmo lugar; o vínculo claim ↔ risco aparece nos dois
sentidos.

---

## 8. Suprimentos

### 8.1 Painel de suprimentos

- [ ] Abra **Painel de suprimentos**: os nove KPIs (aderência ao plano, ciclo de compra, os dois savings, competitividade, OTD, pedidos críticos com LLI, emergenciais e comprometido x orçado) e os quatro visuais (curva de contratação, avanço físico do MAS, saving acumulado e pacotes por etapa).
- [ ] Clique nos três KPIs que apontam para outras telas (aderência, competitividade e pedidos críticos) e percorra a tabela de pedidos por folga em relação ao ROS.
- [ ] Use **Análise do período** e baixe **Excel** (Resumo + Pedidos por folga) e **PDF** (A4 paisagem).

**Deve aparecer:** o PC-14 aparece em "Equalização comercial" na faixa de
etapas; a tela é só leitura, sem filtros.

### 8.2 Plano de compras

- [ ] Abra **Plano de compras**: cinco KPIs, filtros e a tabela com as datas da linha de base, ROS e folga.
- [ ] Crie um **Novo pacote** vinculado a um item da EAC (as três datas intermediárias são derivadas); marque uma compra emergencial sem justificativa (recusa) e com justificativa (grava).
- [ ] **Edite** um pacote antes da requisição e outro depois (a LB congela; mudança exige justificativa).
- [ ] Use **Importar Excel** e baixe **Excel/PDF**.

**Deve aparecer:** datas crescentes (requisição ≤ RFx ≤ adjudicação ≤ pedido),
plano sem folga negativa, LLI antes do gate exigindo a aprovação específica; o
adjudicado e o saving aparecem vazios no que depende das fatias seguintes (é
uma divergência registrada).

### 8.3 Processos de compra

- [ ] Abra **Processos de compra**: cinco KPIs, filtros e a **régua de nove etapas** de cada processo; clique numa linha e veja a ficha (resumo, mapa de equalização, histórico).
- [ ] Use **Nova requisição** (o marco realizado do pacote).
- [ ] Percorra o fluxo de um processo: **RFx** (convidados do cadastro, mínimo de propostas ou fornecedor único com justificativa), **proposta** (com PDF anexo), **encerrar recebimento**, **equalização técnica**, **equalização comercial** (ranking), **negociação** (não acima do valor original), **recomendar adjudicação**, **aprovar** e **emitir** (pedido ou contrato).
- [ ] Tente aprovar como o mesmo comprador/recomendador (403), acima do saldo da EAC, e emita um serviço/EPC para ver nascer o contrato no 03.

**Deve aparecer:** a alçada é calculada das faixas do parâmetro; a emissão
cria o `PED-...` com o cronograma de fabricação ou o `CT-...` no Financeiro,
grava o compromisso na EAC e, com folga negativa, abre a ação de
diligenciamento — **tudo ou nada**; a ficha mostra o documento emitido com o
atalho.

### 8.4 Mapa de Suprimentos (MAS)

- [ ] Abra **Mapa de Suprimentos (MAS)**: seis KPIs, a tabela dos **doze marcos** de cada pacote em dois grupos, a legenda, o rodapé de realizados/previstos e os segmentos Datas/Desvio e fase.
- [ ] Clique numa célula e veja o detalhe do pacote no modal (com os atalhos para processo, diligenciamento, contrato e plano).
- [ ] Filtre por disciplina, tipo, LLI, comprador, fornecedor, situação, vencidos e ordene.
- [ ] Baixe **Excel** e o **PDF A3 paisagem** com as células coloridas.

**Deve aparecer:** pacote sem pedido estima a fabricação entre o pedido e o
ROS, com o aviso "LB estimada"; o serviço/EPC tem os marcos de fabricação
"não se aplica"; o MAS é só leitura.

### 8.5 Diligenciamento e recebimento

- [ ] Abra **Diligenciamento e recebimento**: cinco KPIs (pedidos em aberto e o valor a receber, críticos com LLI, em atenção, marcos vencidos e o OTD), o bloco de pedidos críticos sem tratamento, a tabela e a ficha do pedido (seis marcos, recebimento, ação e últimas atualizações).
- [ ] Atualize um **marco**: realize o próximo (exige o anterior e data até a referência) e reprograme uma previsão com cascata.
- [ ] No marco **Inspeção / FAT**, registre o resultado: aprovado conclui e grava a inspeção no 06; reprovado exige a nova previsão do reteste.
- [ ] **Registre o recebimento** com a evidência (avarias exigem descrição); tente receber de novo.
- [ ] Use **Gerar ação** num crítico e tente de novo (recusa: já existe ação aberta); use **Registrar risco sugerido** e repita no mesmo pedido (recusa).
- [ ] Use **Importar do ERP** (uma linha por marco) e baixe **Excel/PDF**.

**Deve aparecer:** o pedido crítico mostra a folga negativa; a ação de
diligenciamento nasce **uma só** (a Central responde quantas abertas existem);
o risco sugerido entra **Em análise**, com categoria Suprimentos >
Fornecedores e a origem do pedido; a ficha mostra o risco pela origem.

### 8.6 Fornecedores

- [ ] Abra **Fornecedores**: seis KPIs, busca/filtros e a tabela do cadastro.
- [ ] Use **Novo fornecedor** (nome repetido recusa) e **Atualizar qualificação** (mudar a situação exige justificativa; "Qualificado" exige validade futura; Restrito/Bloqueado exigem motivo; os documentos têm validade).
- [ ] Abra **Desempenho e histórico**: classe e nota da avaliação do 03, contratos, valor contratado e o OTD dos pedidos.
- [ ] Baixe **Excel/PDF**.

**Deve aparecer:** a avaliação final do contrato atualiza a qualificação pela
fachada (A/B qualifica, C restringe, D bloqueia) — altere uma avaliação final
no Financeiro e volte para ver; fornecedor Bloqueado é recusado numa RFx.

---

## 9. Gestão de Riscos

### 9.1 Registro de riscos

- [ ] Abra **Registro de riscos**: contexto, KPIs, o alternador **Inerente/Residual**, os filtros e a tabela.
- [ ] Use **Novo risco** (no Portfólio, pede o projeto antes) e **Salvar e avaliar**: veja a prévia do score.
- [ ] Edite a identificação de um risco; como Gestor, faça a **exclusão lógica** de um e, como Admin, **restaure**.
- [ ] Cadastre uma **categoria** da RBS pelo formulário rápido.
- [ ] Baixe **Excel/PDF** do filtro.

**Deve aparecer:** score (P x I, 1 a 25) e severidade são calculados da escala
vigente; a exclusão é bloqueada com ação aberta.

### 9.2 Matriz de riscos 5x5

- [ ] Abra **Matriz de riscos 5x5**: os mapas inerente e residual, a legenda pelas faixas e a movimentação inerente → residual.
- [ ] Clique numa célula com riscos e confira que o Registro abre filtrado; clique numa vazia.
- [ ] Baixe **Excel/PDF**.

**Deve aparecer:** a célula usa a avaliação escolhida (residual; sem residual,
a inerente); oportunidade inverte a escala; quem não reduziu fica destacado.

### 9.3 Ficha do risco (detalhe)

- [ ] Abra uma ficha pelo Registro (`?codigo=RSK-...`): alertas, faixa com inerente e residual, e as abas (plano de resposta, ações, claims vinculados, revisões, encerramento, histórico).
- [ ] Salve um **Plano de resposta** (estratégia, alvo que não supera a inerente para ameaça, prazo futuro, responsável) e **aprove** como Gestor — teste aprovar como o responsável do plano (403).
- [ ] Crie uma **Ação de mitigação** e veja-a chegar na Central (origem Risco).
- [ ] Registre uma **Revisão periódica** (comentário obrigatório; a próxima revisão não passa da cadência da faixa; a situação apurada bate com a variação).
- [ ] Como Gestor, **encerre** um risco: a lição é obrigatória (nasce em Rascunho) e, se materializado, cria o problema na Central e a SM na Governança; depois **reabra** com justificativa.
- [ ] Baixe **Excel/PDF**.

**Deve aparecer:** o responsável pelo plano não aprova (segregação); o
encerramento é bloqueado com ação aberta, salvo materializado; a reabertura
devolve a situação anterior com a justificativa na trilha.

### 9.4 Painel de riscos

- [ ] Abra **Painel de riscos**: KPIs, exposição por categoria da RBS, a evolução mensal do score residual e a **pauta de escalonamento**.
- [ ] Clique em **Enviar pauta** (num projeto; no Portfólio a tela pede o projeto) e confira o destinatário.
- [ ] Use **Análise do período** e baixe **Excel/PDF**.

**Deve aparecer:** a evolução mensal é reconstruída do histórico (não há série
digitada); o envio vai ao **gerente do cadastro** e fica "simulado" enquanto o
e-mail está desligado.

---

## 10. Gestão da Qualidade

### 10.1 Painel da qualidade

- [ ] Abra **Painel da qualidade**: cinco KPIs, o alerta de auditorias atrasadas e os quatro gráficos (RNC por mês, aprovação em inspeções com a meta, Pareto por disciplina, RNC por origem).
- [ ] Percorra a pauta de tratamento e o desempenho por empresa.
- [ ] Use **Análise do período** e baixe **Excel/PDF** (números dos gráficos em tabela).

**Deve aparecer:** a pauta ordena pelo atraso; no Portfólio, a pauta abre com a
coluna Projeto e a tabela de empresas fica agregada por empresa.

### 10.2 Não conformidades (RNC)

- [ ] Abra **Não conformidades (RNC)**: filtros (busca, situação, severidade, disciplina, origem, empresa), cinco KPIs e a lista com a próxima etapa e as ações.
- [ ] Abra uma RNC nova: preencha a contenção imediata e o prazo (vem da severidade).
- [ ] Percorra o fluxo: **atribuir responsável** → **análise** (causa raiz e disposição; Reparo/Usar como está exigem a concessão do cliente) → as **ações corretivas** nascem na Central (origem RNC) → **verificação de eficácia** (Gestor; teste com quem respondeu pela análise: 403) → **Encerrada**; ineficaz volta à ação corretiva e conta reincidência.
- [ ] **Cancele** uma RNC ainda antes da ação corretiva, com motivo.
- [ ] Anexe **evidências** na ficha e baixe **Excel/PDF**.

**Deve aparecer:** o custo da não qualidade é atualizável; o encerramento
eficaz pode abrir a lição em Rascunho (origem RNC); o fornecedor não alcança o
módulo.

### 10.3 Inspeções e ITP

- [ ] Abra **Inspeções e ITP**: filtros (busca, ITP, resultado, tipo), cinco KPIs e as listas.
- [ ] Crie um **ITP** com pontos **H**, **W** e **R**; faça uma **nova revisão** depois de uma inspeção (não pode retirar ponto com inspeção) e aprove o cliente como Gestor.
- [ ] **Registre uma inspeção** num ponto de ITP aprovado: aprove com ressalva (conta aprovada) e reprove (abre a RNC, com severidade e a contenção do registro).
- [ ] Confira o **aviso da notificação** ao cliente nos pontos H/W (a antecedência mínima é um parâmetro).
- [ ] Baixe **Excel/PDF**.

**Deve aparecer:** a inspeção só entra em ITP aprovado; a reprovação abre a RNC
na mesma transação; o FAT do diligenciamento aparece aqui (sem ponto de ITP,
identificado pelo pedido).

### 10.4 Auditorias

- [ ] Abra **Auditorias**: filtros (busca, situação, tipo), cinco KPIs e a lista do programa.
- [ ] **Planeje** uma auditoria; **reprograme** mudando a data (justificativa obrigatória) e sem mudar.
- [ ] **Registre o resultado**: itens verificados e conformes e as constatações (Não conformidade, Observação, Oportunidade); cada NC abre a RNC (origem Auditoria); tente mais NC que itens não conformes (recusa).
- [ ] Abra a ficha: constatações com o vínculo da RNC e as reprogramações.
- [ ] Baixe **Excel/PDF**.

**Deve aparecer:** auditoria planejada com data anterior à referência fica
**atrasada**; a conformidade e a aderência ao programa saem nas metas do
parâmetro.

---

## 11. HSE

### 11.1 Painel HSE

- [ ] Abra **Painel HSE**: o bloco "No mês selecionado" (TF, TRIF, TG e HiPo), o "Acumulado" (mais dias sem afastamento e ações HSE no prazo) e os proativos (DDS, conformidade, observações, quase acidentes, recomendações, incidentes ambientais).
- [ ] Troque o **ano/mês** e a **referência da pirâmide** (Bird/Heinrich) e confira a recarga.
- [ ] Confira a pirâmide dupla (mês e acumulado), a evolução de TF/TRIF e as listas por área e por empresa (com a **nota HSE sugerida** da contratada).
- [ ] Use **Análise do período** e baixe **Excel/PDF**.

**Deve aparecer:** a troca da referência recarrega o fragmento pela query e o
servidor redesenha; o mês padrão é o último com HHT.

### 11.2 Ocorrências

- [ ] Abra **Ocorrências**: filtros e KPIs; abra a ficha de uma ocorrência.
- [ ] Registre uma **Nova ocorrência** (com o dado restrito na mesma transação). Com **Gestor/Admin**, abra o bloco restrito e os anexos; com **Membro ou Visualizador**, confirme o 403 ao tentar abri-lo.
- [ ] **Investigue** (método, causa raiz e data) → **Ações** na Central (origem HSE) → **Tratamento** → **Encerrar** como Gestor, com as ações concluídas e a eficácia verificada; num **HiPo**, confira a lição obrigatória em Rascunho.
- [ ] Baixe **Excel/PDF** (no Portfólio, com coluna Projeto).

**Deve aparecer:** os prazos legais vigentes ficam **gravados na ocorrência**
(mudar o parâmetro depois não muda o registro); o fluxo é Registrada → Em
investigação → Ações definidas → Em tratamento → Encerrada.

### 11.3 Inspeções e observações

- [ ] Abra **Inspeções e observações**: KPIs e listas.
- [ ] Registre uma **inspeção** de segurança (itens conformes e não conformes), uma **observação** comportamental e um **DDS** (tema, data e participantes).
- [ ] Registre o **fechamento mensal** e confira a aderência aos DDS e a conformidade.
- [ ] Use a **importação** de planilha (HSE mensal) e baixe **Excel/PDF**.

**Deve aparecer:** o nível 5 da pirâmide (desvios) sai do consolidado mensal; o
formulário muda por tipo; a importação confere antes de gravar.

### 11.4 Análises de risco (APR/HAZOP)

- [ ] Abra **Análises de risco (APR/HAZOP)**: busca, tipo e "só abertas"; a lista com o código `APR-...`/`HAZOP-...`.
- [ ] Registre um **novo estudo** com participantes e recomendações repetíveis.
- [ ] Numa recomendação, **crie a ação** na Central (uma por recomendação; a segunda recebe 422) e depois **feche a recomendação** com data e evidência: a ação vinculada conclui junto.
- [ ] Replaneje a ação na Central e volte: o prazo da recomendação muda.
- [ ] Baixe **Excel/PDF**.

**Deve aparecer:** recomendação e ação sincronizadas nos dois sentidos; o link
da Central roteia pelo prefixo (`APR-`/`HAZOP-` para os estudos, `OCR-` para as
ocorrências).

### 11.5 Horas trabalhadas (HHT)

- [ ] Abra **Horas trabalhadas (HHT)**: HHT e efetivo médio por mês e empresa e o **histograma de mão de obra**.
- [ ] Registre um mês novo (upsert por mês e empresa) e edite um existente.
- [ ] Use a **importação** de planilha e baixe **Excel/PDF** (no Portfólio, a importação é recusada).

**Deve aparecer:** gravar o mesmo mês e empresa atualiza o registro; o
histograma (previsto x realizado, com o fator) alimenta o cronograma de
desembolso do Financeiro.

---

## 12. Governança

### 12.1 Gestão de mudanças

- [ ] Abra **Gestão de mudanças**: as abas **Registro** e **Painel**; no Registro, os seis KPIs (os três primeiros filtram a lista), os filtros e a tabela.
- [ ] Use **Nova solicitação** (no Portfólio, pede o projeto antes) e preencha a SM; confira o número `SM-<padrão>-NNNN`.
- [ ] Marque uma prioridade **Emergencial** com execução antecipada e justificativa.
- [ ] No **Painel**, confira a taxa de aprovação, o tempo médio de decisão, os gráficos e a tabela do Pareto por origem.
- [ ] Baixe **Excel/PDF** (registro e painel).

**Deve aparecer:** cancelar só vale antes da decisão e exige justificativa; a
aprovada é recusada com a orientação de registrar uma nova SM; a emergencial
abre a **ratificação** pendente com o prazo do parâmetro.

### 12.2 Solicitação de mudança (detalhe)

- [ ] Abra uma SM pela lista (`?codigo=SM-...`): a barra de etapas e as abas **Solicitação**, **Análise de impacto**, **Decisão**, **Implementação** e **Histórico**, mais os anexos.
- [ ] **Inicie a análise**, **conclua** com custo, prazo, marco contratual, as cinco dimensões e a fonte do recurso (Remanejamento com transferências, ou Liberação de reserva) e veja a **alçada** calculada.
- [ ] Como Gestor, **registre a decisão** (Aprovada / com condições / Rejeitada / Adiada) com os participantes do quórum; veja as **ações de implementação** nascerem na Central (origem Mudança).
- [ ] Numa Adiada, use **Reapresentar**; numa aprovada com custo, faça a **revisão da EAC** (e da EAP, se houver impacto em escopo) antes de **Encerrar**.
- [ ] No encerramento, confira as confirmações que o impacto exige e a lição opcional.
- [ ] Baixe **Excel/PDF** da ficha.

**Deve aparecer:** a alçada só sobe, nunca desce; a decisão e as ações gravam
tudo ou nada; o encerramento é recusado com ação aberta ou linha de base não
incorporada.

### 12.3 Lições aprendidas

- [ ] Abra **Lições aprendidas**: as abas **Acervo** e **Painel**; no acervo, a contagem, os cartões, o **checklist de kickoff** (botões de fase), os filtros e os KPIs.
- [ ] Crie uma **nova lição** (Rascunho) e **envie para validação**; como Gestor que não é o autor, **valide** (ou devolva com comentário) e **publique**; teste validar a própria lição (403).
- [ ] **Aplique em projeto** com "criar ação" e com "gerar risco" (o risco nasce no 05, sem avaliação, com a categoria da RBS).
- [ ] No **Painel**, confira os KPIs (reuso, dias desde a última lição), os gráficos e as tabelas (fases, áreas, mais reusadas, projetos sem registro).
- [ ] Baixe **Excel/PDF**.

**Deve aparecer:** o validador não é o autor (segregação); a origem de módulo
exige o número e o confere pela fachada; a lição aplicada com risco guarda o
vínculo (`licao_aplicacao.risco_id`) e a ficha linka o risco.

---

## 13. Configurações

### 13.1 Parâmetros do sistema

Perfil: **Gestor ou Admin** (Membro e Visualizador recebem 403).

- [ ] Abra **Parâmetros do sistema**: o card da versão vigente, a busca e o filtro por módulo e os grupos (Avaliação de contratadas, Financeiro, Suprimentos, Riscos, Qualidade, HSE, Planejamento, Governança, Portfólio e Anexos), com a tabela parâmetro × valor.
- [ ] Abra **Editar** num grupo, mude um valor e grave **sem justificativa** (recusa) e com justificativa.
- [ ] Grave um grupo sem mudar nada (recusa: "Nenhum valor foi alterado.").
- [ ] Tente trocar a escala de riscos sem a confirmação (recusa).
- [ ] Abra o **Histórico de versões**: o selo **Vigente** por grupo e o **Ver** com o antes/depois contra a versão anterior do mesmo grupo.
- [ ] Mude a **meta de aprovação em inspeções** e volte ao painel da Qualidade: a meta da tela muda na hora.
- [ ] Baixe **Excel/PDF** (parâmetros vigentes e histórico).

**Deve aparecer:** a gravação cria versão nova **só dos grupos de origem cujos
valores mudaram**, com autor, vigência e trilha; a primeira versão de cada
grupo não tem alterações no histórico.

### 13.2 Colaboradores

Perfil: **Admin** (Gestor recebe 403).

- [ ] Abra **Colaboradores**: os dois avisos, os KPIs por perfil (universo completo) e a busca/filtros.
- [ ] Use **Liberar acesso** para uma pessoa nova; abra o **Editar** de alguém e adicione/remova um **papel na Programação Semanal** por projeto.
- [ ] Tente liberar um **Fornecedor sem empresa** (recusa no campo) e com empresa.
- [ ] **Revogue** um acesso; tente revogar o **último Admin** ativo (recusa) e alguém que já deixou trilha (a recusa orienta suspender).
- [ ] **Suspenda** um colaborador e entre com ele: o gate nega a requisição seguinte.
- [ ] Baixe **Excel/PDF**.

**Deve aparecer:** o e-mail normalizado e único; os papéis são substituídos
pelo conjunto enviado; a pessoa revogada permanece no cadastro de apoio; a
tela é a **fonte de verdade do acesso** (o gate lê daqui a cada requisição).

### 13.3 Cadastros de apoio

Perfil: **Gestor ou Admin**.

- [ ] Abra **Cadastros de apoio**: os **sete cartões** (Empresas, Pessoas, Projetos, Sistemas, Unidades, Locais e Disciplinas) com contagem, Incluir e Editar/Excluir.
- [ ] Inclua um **projeto** novo: o cliente entra pelo formulário (sigla só no cliente novo), com orçamento, datas, apetite e notas de ponderação; confirme que o projeto **nasceu com a configuração padrão da Programação Semanal** (60/75/15).
- [ ] Tente **excluir** uma empresa em uso (recusa com a mensagem de onde é usada) e um cadastro livre.
- [ ] Confira nas telas: um sistema novo aparece no filtro da punch list; uma unidade nova, nos formulários da produtividade.
- [ ] Baixe **Excel/PDF** (as sete tabelas).

**Deve aparecer:** a exclusão em uso é recusada com a origem (inclusive "em uso
pela trilha de auditoria" quando o projeto já gravou); cadastro é fonte única,
sem duplicação nos módulos.

---

## 14. As revisões que ficam com o dono

### 14.1 Q30 — revisão do modelo de dados

O modelo de dados foi entregue **"aceito para execução"** (decisão Q30): a
execução andou sem parar e o dono o revisa agora, no fim.

1. Abra `docs/MODELO-DE-DADOS.md` e leia na ordem:
   - **Como ler este documento** e **Regras do desenho** (D5, D5a, D5b, D7, D8,
     D10: uma tabela por entidade, FK e UK no banco, `projeto_id` em todo
     registro de projeto, `versao` em todo registro editável, somente fatos com
     as exceções históricas anotadas, centavos inteiros e datas em `date`,
     módulo dono).
   - **Diagramas**: os 13 grupos (Plataforma e cadastros; 01 Central; 08
     Governança; 03 Financeiro em dois; 02 Planejamento em dois; 02 Programação
     Semanal; 04 Suprimentos; 05 Riscos; 06 Qualidade; 07 HSE; análise do
     período e relatório) e **Ligações entre módulos**.
   - **Tabelas**: a linha de cada tabela com o que guarda e o **módulo dono**.
   - **Exceções da D5b (gravadas)** e as **Tabelas de cobertura** (mocks e
     repositório JSON do app), que mapeiam 100% das coleções e chaves.
2. Compare com o que as telas mostram (este roteiro é o caminho): os números
   que você viu saem do modelo calculados, não gravados.
3. **Registro do aceite:** marque aqui que o modelo está aceito como está
   (o documento já diz que o dono o revisa no fim, e que **mudança depois disso
   vira issue nova**).
4. Encontrando algo a mudar: **não edite o modelo** — abra uma **issue nova**
   em `docs/issues/spec-migracao-gestnow/` descrevendo a mudança, seguindo o
   fluxo da spec; é assim que a decisão Q30 foi desenhada ("aceito para
   execução"; o dono revisa no fim, e mudança vira issue nova).

- [ ] Modelo de dados revisado e aceito (ou com as issues de mudança abertas).

### 14.2 Q31 — decisão das divergências com o protótipo

`docs/DIVERGENCIAS-DO-PROTOTIPO.md` registra cada diferença entre o GestNow e o
protótipo, exigida pela decisão Q31. **Hoje são 82 linhas, todas com a coluna
`Situação` em "pendente de aceite".** A tabela tem cinco colunas: **Regra** (o
que difere), **Número do protótipo**, **Número correto** (o do GestNow),
**Motivo** e **Situação**.

Enquanto a situação for **pendente de aceite**, o teste-oráculo afirma o número
indicado na tabela (o do protótipo, ou o da spec quando a diferença decorre de
decisão já tomada) e cita a divergência; **depois do seu aceite, a linha passa
a "aceita" e o teste passa a afirmar o número correto**.

1. Abra `docs/DIVERGENCIAS-DO-PROTOTIPO.md` e leia a tabela linha a linha. Os
   grupos são: modelo de dados sem indicadores persistidos (D5b), data viva
   (D6), escopo e carga de demonstração, a Programação Semanal do app (D10),
   visuais da biblioteca (D11), inglês (D13) e decisões da execução.
2. Para decidir, apoie-se no que este roteiro mostrou e no **Motivo** de cada
   linha. As linhas com números lidos iguais ao protótipo normalmente são
   aceitação simples; as de carga de demonstração explicam por que o número
   congelado é o do mock e não o da fórmula — confira nas telas.
3. **Como marcar:** na coluna `Situação`, troque **"pendente de aceite"** por
   **"aceita"** na linha aceita. Se quiser recusar, não apague a linha: escreva
   a decisão na própria linha (por exemplo, "recusada em dd/mm/aaaa: ...") e
   abra uma issue de mudança. O aceite das 82 linhas libera o teste-oráculo
   para afirmar os números corretos.
4. Registre a data do aceite no **Histórico** do mesmo arquivo (a tabela do
   fim do documento), sem reescrever as linhas antigas.

- [ ] Linhas de `DIVERGENCIAS-DO-PROTOTIPO.md` decididas e marcadas.

### 14.3 Decisões da execução

A execução tomou decisões registradas no **Histórico de decisões** da
`docs/SPEC-MIGRACAO-GESTNOW.md` como "Decisão da execução (ISSUE-NNN),
pendente de revisão do dono". Revise-as depois do Q30/Q31: são escolhas de
implementação (nomes, visuais, carga, rotas) que não mudam o negócio, mas
ficam registradas para a sua leitura. Encontrando alguma a mudar, o caminho é
o mesmo: issue nova.

- [ ] Decisões da execução revisadas.

---

## 15. Pendências de fonte e publicação no Azure

### 15.1 Conciliação das pendências de fonte

1. Abra `docs/issues/spec-migracao-gestnow/PENDENCIAS-DE-FONTE.md`.

**Deve estar assim:** a tabela "Pendências por issue" **vazia** — desde
06/10/2026 as fontes estão no repositório (`fontes/Sistema` e
`fontes/Timenow - Programação Semanal`), nenhuma issue espera fonte e cada
módulo já fez a sua carga e o seu oráculo. Se alguma linha aparecer, ela diz
qual critério ficou pendente e qual fonte falta: concilie com a execução e
registre a decisão; a issue correspondente fecha como `done` com o critério
ainda `[ ]` (decisão da execução, pendente de revisão do dono).

- [ ] Pendências de fonte conferidas (hoje, nenhuma).

### 15.2 Publicação no Azure (passo do dono)

O app está **pronto para publicar, sem publicar**: criar os recursos e pôr no
ar é o seu passo, seguindo o guia da ISSUE-092, `docs/PUBLICACAO-AZURE.md`.
O guia cobre: o Static Web Apps com o Functions vinculado, o Azure Database
for PostgreSQL, a conta de armazenamento dos anexos, a tabela de variáveis de
ambiente (com o valor local e o do Azure), a aplicação das migrações, o
cadastro do primeiro Admin e a publicação pela SWA CLI; e ainda o envio de
e-mail, que você liga quando quiser (`GESTNOW_ENVIO_EMAIL`). Sem Bicep e sem
pipeline Git (decisão do dono).

Antes de publicar, faça a conferência local do **modo produção**: base vazia,
só o primeiro Admin (`GESTNOW_ADMIN_EMAIL`) e os parâmetros iniciais, sem
demonstração — o próprio guia traz o passo.

- [ ] Guia `docs/PUBLICACAO-AZURE.md` lido e a publicação feita (ou agendada).

---

## 16. Conferências transversais

### 16.1 Exportações tela a tela

O inventário de exportações é `docs/EXPORTACOES.md` (o documento da ISSUE-091):
uma linha por tela, com cada botão **Excel** e **PDF**, o que o documento leva
e o teste que o cobre. Neste roteiro, você já conferiu as exportações de cada
tela; agora faça a passada final:

1. Abra `docs/EXPORTACOES.md` e percorra a lista.
2. Para cada tela, confirme: o botão existe, o arquivo abre, as **colunas são
   as da tabela**, os **KPIs vêm com a referência** e o PDF (imprimível) sai
   **sem a navegação**.
3. Anote qualquer diferença entre o inventário e a tela — é a matéria-prima da
   correção (ou da linha nova no inventário).

- [ ] Exportações conferidas contra `docs/EXPORTACOES.md`.

### 16.2 Acessibilidade

A auditoria de acessibilidade é `docs/ACESSIBILIDADE.md` (teclado, foco,
contraste, rótulos e ARIA). O que a auditoria não conseguiu fechar e você deve
conferir no navegador com o app no ar:

1. **Anel de foco:** dê **Tab** a partir do topo e confirme que cada parada
   (skip link, marca, itens da barra, sair, conteúdo) mostra o contorno verde
   (`:focus-visible`). A auditoria mediu 24 paradas com anel computado; o que
   falta é o olho.
2. **Leitor de tela (NVDA):** instale de nvaccess.org, ligue o Speech Viewer
   (`NVDA+N` → Ferramentas → Visualizador de Fala) e percorra: o Início
   anuncia o título e a navegação; a barra lê cada item e o ativo como "página
   atual"; um formulário anuncia o rótulo e o erro junto do campo; o toast é
   anunciado sem roubar o foco; o modal fecha com Esc e devolve o foco.
3. Confira a orientação da casa: **o estado nunca é só cor** (as pills trazem o
   rótulo em texto) e o **skip link** é o primeiro da tabulação.

- [ ] Acessibilidade conferida (anel de foco e, se possível, a leitura com NVDA).

### 16.3 Varredura de telas

A varredura automatizada das telas é o `scripts/varredura-telas.mjs` (ISSUE-090),
rodada pelo comando `npm run varredura` (Playwright; `npx playwright install
chromium` na primeira vez). Ela abre cada tela da lista de navegação em
**1280, 1100 e 760 px**, com os perfis **Admin, Visualizador e Fornecedor**, e
reprova console com erro, rolagem horizontal, barra lateral ausente ou oculta,
tela sem estilo próprio e link quebrado.

1. Com o app no ar, rode `npm run varredura`.
2. Rode também a porta de qualidade do repositório: `npm run verificar`.

**Deve aparecer:** a varredura passa nas 51 telas × 3 larguras × 3 perfis
(459 navegações) e a porta de qualidade passa com as cinco etapas, sem nenhuma
regra desligada. Na largura de 1100 e 760 px, a barra é o **trilho** (nunca
some); o fornecedor só alcança a Programação Semanal; o Visualizador não abre
Configurações.

- [ ] Varredura e porta de qualidade passaram.

---

## 17. Fechamento do aceite

- [ ] Os 10 módulos e as 51 telas da seção 1.6 foram vistos e conferidos.
- [ ] As operações de escrita que o seu perfil de teste permitiu foram feitas, e as recusas (422/409/403) saíram no lugar certo.
- [ ] As exportações das telas que você usa abrem com as colunas e os KPIs certos, e o PDF sai sem navegação.
- [ ] PT | EN conferido.
- [ ] Q30 revisado (seção 14.1) e Q31 decidido (seção 14.2).
- [ ] Pendências de fonte conferidas (seção 15.1) e o guia do Azure lido (seção 15.2).
- [ ] Aceite registrado: as mudanças que você quer viram **issue nova**; nada é alterado por cima do que foi aceito.
