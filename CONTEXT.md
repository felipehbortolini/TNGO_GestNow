# Glossário do domínio do Timenow GestNow

Vocabulário do Timenow GestNow. Termo usado em código, documentação e conversa
deve estar aqui — e significar exatamente isto.

Mantido pela skill `domain-modeling`: conceito novo entra no momento em que
aparece, não depois.

---

## Escopo, custos e mudanças

**EAP** — Estrutura Analítica do Projeto. Decompõe o escopo em áreas,
subáreas e pacotes com pesos; suas medições são a única fonte do avanço físico
do projeto.

**EAC** — Estrutura Analítica de Custos. Decompõe o orçamento em pacotes e
itens. Neste produto a sigla nunca significa Estimate at Completion.

**Projeção no término** — estimativa do custo total do projeto ao término.
Substitui o uso ambíguo da sigla inglesa EAC para Estimate at Completion.

**SM** — Solicitação de Mudança. Registro formal para analisar, decidir e
incorporar uma mudança de escopo, prazo, custo ou contrato; linha de base só
muda pela SM aprovada.

**MAS** — Mapa de Suprimentos. Visão calculada dos marcos de aquisição,
fabricação e entrega dos pacotes de compra; não é um cadastro separado.

**ROS** — *Required On Site*. Data em que o item de compra é necessário no
local do projeto. A folga compara essa data com a previsão de entrega.

**VME** — Valor Monetário Esperado de um risco: probabilidade média da faixa
multiplicada pelo impacto em custo, em centavos.

**RNC** — Registro de Não Conformidade. Descreve um requisito não atendido,
sua contenção, causa, disposição, ação corretiva e verificação de eficácia.

**ITP** — *Inspection and Test Plan*, ou plano de inspeção e testes. Declara
pontos de espera (H), testemunho (W) e revisão documental (R) antes da
execução/aceitação.

## Programação Semanal

**Programação Semanal** — compromisso de uma contratada para uma semana ISO,
com quantidades previstas por atividade e por dia, de segunda a domingo. No
GestNow ela pertence a um projeto; não usa o isolamento multi-ambiente do app
de origem.

**Atividade** — uma linha da Programação Semanal, com ID exclusiva dentro da
semana, frente, empresa, encarregado, unidade e sete quantidades previstas.

**Semana ISO** — período de segunda a domingo. A semana 1 contém a primeira
quinta-feira do ano; o calendário de semanas tem uma definição única na
plataforma.

**Previsto** — quantidade comprometida para a atividade, distribuída pelos
sete dias. **Realizado** — quantidade executada, separada em turno dia e
turno noite.

**PPC** — Percentual do Plano Concluído: realizado dividido pelo previsto de
uma atividade. É específico da atividade; não é o indicador consolidado da
semana.

**Aderência da programação** — soma do realizado dividida pela soma do previsto
de um conjunto (semana, empresa ou frente). Pondera pela quantidade e não é a
média dos PPCs.

**Aderência ao plano de compras** — pacotes adjudicados até a data de corte
divididos pelos pacotes planejados até a mesma data.

**Aderência ao programa de auditorias** — auditorias realizadas divididas
pelas auditorias previstas até a data de referência.

**Faixa da programação** — classificação de PPC ou aderência (alta, média,
baixa) pelos limites configurados no projeto. Os limites iniciais vêm do app
de Programação Semanal.

**Janela de programação** — períodos em que uma contratada pode editar a
programação de um projeto. A liberação extraordinária prevalece; depois são
verificadas as semanas liberadas e o dia/horário.

**FP** — Fator de Produtividade: horas-homem apropriadas divididas pelas horas
ganhas; 1,00 corresponde ao índice da proposta.

**CP** — Capacidade Produtiva: horas produtivas do dia, calculadas a partir
das execuções dos turnos.

## Indicadores de custo e HSE

**EV** — Valor Agregado; **PV** — Valor Planejado; **AC** — Custo Real.
São valores acumulados na data de corte.

**CPI** — índice de desempenho de custo, EV dividido por AC.
**SPI de custo** — índice de prazo do valor agregado, EV dividido por PV.
**SPI físico** — avanço real da EAP dividido pelo avanço previsto da EAP.
O qualificador é obrigatório para não confundir os dois domínios.

**BAC** — orçamento no término. **VAC** — BAC menos Projeção no término;
valor negativo indica projeção acima do orçamento.

**HHT** — Horas-Homem Trabalhadas, base para as taxas de segurança.
**TF** — taxa de frequência com afastamento. **TRIF** — taxa de lesões
registráveis. **TG** — taxa de gravidade por dias perdidos/debitados. A base
de normalização é um parâmetro.

**HSE** — Saúde, Segurança e Meio Ambiente (Health, Safety and Environment).
**HiPo** — ocorrência de alto potencial, classificada pela consequência
potencial além da gravidade real.

## Pessoas e implantação

**Colaborador** — pessoa cadastrada para acesso ao GestNow. O cadastro é a
fonte de verdade de quem pode entrar.

**Perfil geral** — capacidade nos módulos 01 a 08, Início, relatório e
Configurações: Visualizador, Membro, Gestor ou Admin.

**Papel da Programação Semanal** — Planejador, Fiscal, Encarregado ou
Fornecedor, atribuído por projeto. Pode coexistir com o perfil geral.

**Vínculo** — relação do colaborador com a organização: Timenow, Fornecedor
ou Cliente. Fornecedor só vê a própria empresa e somente a Programação
Semanal.

**Implantação** — ambiente técnico em que o app roda (local ou Azure). Para o
escopo dos dados usa-se **projeto**, nunca “ambiente”.

---

## Estrutura da aplicação

**Shell** — `app/index.html`. O único documento HTML completo da aplicação.
Carrega o Design System, consulta a sessão, monta a sidebar e hospeda a área de
conteúdo. Nunca é substituído; só o conteúdo dentro dele troca.

**View** — arquivo em `app/_views/<modulo>/`. Uma página. É um **fragmento**,
não um documento: sua raiz é `<main id="app-shell" class="content">` e ela
substitui o conteúdo do shell inteiro.

**Componente** — arquivo em `app/_components/`. Pedaço reutilizável e
**estático** de HTML, carregado por uma view. Se precisar de dado do servidor,
não é componente — é fragmento de API.

**Fragmento** — pedaço de HTML que o servidor devolve para ser trocado no DOM.
Estende `base_fragment.html` e carrega `{{ target_id }}` na raiz. É a unidade de
resposta da API: aqui o servidor devolve HTML pronto, nunca JSON.

**Partial** — template Jinja2 sem raiz nem id próprios, existente só para ser
incluído por outro (`{% include %}`). Nunca é alvo de `x-target`. Ex.:
um fragmento de linha compartilhado por uma lista.

**Alvo** (*target*) — o elemento do DOM que receberá um fragmento, declarado
pelo cliente em `x-target`. **Quem manda no destino é o cliente**, nunca o
servidor. Alvo declarado que não venha na resposta é **esvaziado** pelo Alpine
AJAX — por isso respostas com vários alvos precisam devolver cada fragmento esperado.

**Resposta multi-alvo** — resposta que traz vários fragmentos irmãos de uma vez,
cada um com seu id fixo, para atualizar mais de um bloco numa requisição. É a
única exceção à regra de não fixar id no servidor.

---

## Navegação e escopo

**Lista de navegação** — arquivo único (`api/src/core/navegacao.json`) com os
módulos e as telas, em dois níveis. Alimenta a barra lateral, as abas do módulo,
o Voltar e a verificação trio-da-tela; tela nova entra ali e em nenhum outro
lugar.

**Tela de detalhe** — tela que se abre de uma lista (ata, contrato, ficha do
risco, SM, relatório gerencial). Não tem aba: a barra lateral destaca o módulo
de origem e o botão Voltar leva à lista.

**Escopo** — de onde vêm os dados da requisição: o Portfólio ou um projeto.
Resolvido por requisição, pelo parâmetro `projeto` da URL, depois pelo cookie,
com o Portfólio como padrão.

**Portfólio** — o conjunto de todos os projetos; é o escopo padrão. Todo
registro novo pertence a um projeto, por isso a inclusão pede o projeto antes.

**Trilho** — a barra lateral reduzida a ícones, com dica. É o que ela vira até
1100 px ou quando recolhida; a barra nunca some.

**Dica** — balão de texto curto (`.dica`, `TN.dica`): o nome do item no trilho e
o significado de uma sigla.

---

## Camada visual

**Design System** (DS) — `app/ds/`. A única fonte visual da aplicação. Três
arquivos, com fronteira nítida:

- **tokens.css** — variáveis e componentes atômicos (`.btn`, `.card`, `.pill`)
- **shell.css** — estrutura de tela (`.sidebar`, `.page`, `.guard`)
- **patterns.css** — composições (`.kpis`, `.toolbar`, `.facepile`, `.linha`)

Nenhuma classe é declarada em dois deles. Isso é verificado, não confiado.

**Token** — variável CSS que carrega uma decisão de design (`--brand-primary`,
`--space-lg`). **Valor de cor, espaçamento, raio ou sombra nunca é escrito
direto no código** — sempre por token.

**Contrato visual** — as cinco regras que garantem que toda página nasça
estilizada. Em `docs/CONTRATO-VISUAL.md`. A mais importante: só o shell carrega
estilo; fragmento nunca traz `<link>` nem `<script src>`.

**Sentinela** — a variável `--ds-carregado`, conferida pelo shell no boot. Se o
Design System não carregar, o app falha com mensagem visível em vez de servir
uma tela sem estilo.

---

## Backend

**Blueprint** — `func.Blueprint` que agrupa rotas relacionadas e é registrado
em `function_app.py`. Rotas de domínio ficam em
`api/src/modulos/<modulo>/routes.py`; as rotas de plataforma permanecem em
`api/src/blueprints/`.

**Gate de fragmento** — a checagem `is_alpine_request(req)` no início de todo
endpoint de fragmento. Quem chega sem o cabeçalho do Alpine AJAX — navegador
digitando a URL, cURL — é redirecionado para o shell.

**AlpineAjaxResponse** — o único caminho pelo qual um fragmento sai do servidor.
Resolve o `target_id` a partir do cabeçalho, injeta no contexto e renderiza.

**Toast por cabeçalho** — mensagem ao usuário viaja em `X-TN-Toast` na resposta;
`ds/ui.js` a converte em toast. A página não precisa saber que isso aconteceu.

## Carga e modos

**Modo do app** — demonstração ou produção, vindo de `GESTNOW_MODO`
(ausente vale demonstração, o modo local; valor desconhecido falha alto).

**Carga de demonstração** — a base que o modo demonstração grava a partir dos
mocks do protótipo já convertidos, com todas as datas deslocadas de
25/09/2026 (a **âncora**) até a data de hoje. Cada módulo registra a sua parte
(`seed.py`); a tabela `carga_demonstracao` marca o que já entrou, então rodar
de novo não duplica. Em produção a base nasce vazia: só o primeiro Admin, de
`GESTNOW_ADMIN_EMAIL`, e os parâmetros iniciais. Vive em `api/src/carga/`.

## Notificações

**Porta de notificação** — o ponto único por onde saem o follow-up de ações, a
pauta de riscos ao gerente e o envio à tesouraria. Registra cada envio e diz à
tela o que aconteceu. Quem liga o envio real de e-mail é `GESTNOW_ENVIO_EMAIL`.

**Envio simulado** — notificação registrada na trilha de auditoria, com
destinatários e assunto, sem sair por e-mail. É o que acontece enquanto o envio
real está desligado, e a tela avisa "simulado".

---

## Qualidade

**Porta de qualidade** — `scripts/verificar.mjs`. Cinco etapas obrigatórias
antes de qualquer commit. É o mecanismo real de imposição do padrão; a
documentação apenas explica.

**Paridade** — a garantia de que os arquivos herdados do
`Template_Framework_Desenvolvimento` continuam idênticos ao original. Rastreada
numa matriz no plano de ação, com cada arquivo marcado `=` (idêntico),
`~` (alterado) ou `+` (novo).

**Falso positivo estrutural** — quando uma regra de linter acusa algo que é
correto pela arquitetura do projeto. Resolve-se na configuração **com
comentário explicando**, nunca com supressão solta. Dois casos vivos: `ARG001`
nos blueprints (o Azure Functions exige `req` na assinatura) e
`allowUnknownVariables` no CSS (os tokens moram em outro arquivo).

---

## Termos que NÃO usamos

Vocabulário que já circulou por aqui e foi aposentado — se aparecer, é resquício:

| Não use | Use | Por quê |
|---|---|---|
| `CAA_*` | `TN` | Sigla de um app específico num kit que serve a todos |
| "componente" para fragmento de API | fragmento | Componente é estático, fragmento vem do servidor |
| `.ata-row`, `.ma-toolbar` | `.linha`, `.toolbar` | Nome de domínio de um app dentro do Design System |
| "topbar", "navbar" | sidebar | O shell padrão é a barra lateral de 300px |
| Tailwind, DaisyUI | Design System | Removidos pela decisão D1 |
| `EAC` para *Estimate at Completion* | Projeção no término | EAC significa Estrutura Analítica de Custos neste produto |
| PPC para um conjunto de atividades | Aderência da programação | PPC é de uma atividade; aderência agrega quantidades |
| "ambiente" para projeto ou dados | projeto | "Implantação" nomeia local/Azure; multi-ambiente está fora de escopo |
