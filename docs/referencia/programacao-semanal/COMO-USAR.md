# Como usar

Guia de operação, não de desenvolvimento. Para quem vai **usar** a
Programação Semanal — planejamento, fiscalização e contratadas.

---

## Entrar

O acesso é pelo e-mail corporativo. **Se o seu e-mail não estiver cadastrado
em Configurações → Colaboradores, você não entra**, mesmo tendo conta na
empresa. Peça a liberação ao administrador do sistema.

Rodando em arquivos locais, sem provedor de identidade, o app entra em modo
demonstração: a barra lateral traz um seletor para escolher o perfil ativo.
Ele existe para conferir a tela como cada papel a vê.

---

## O que cada perfil faz

| Perfil | O que pode |
|---|---|
| **Administrador** | Tudo, mais cadastros, janelas, colaboradores e auditoria |
| **Planejador** | Valida a programação, define o fiscal, publica a semana, importa planilha |
| **Fiscal** | Aprova o realizado das atividades sob sua responsabilidade |
| **Encarregado** | Responde pela frente em campo: vê a semana e reporta o realizado |
| **Fornecedor** | Programa e reporta o realizado **da própria empresa**, dentro da janela |
| **Visualizador** | Somente leitura, com exportação |

**Fiscal e Encarregado são também as duas listas de nomes que a atividade
oferece.** Quem aparece nos campos *Fiscal responsável* e *Encarregado* de uma
atividade é exatamente quem está cadastrado em Colaboradores com esse perfil.

Quem tem vínculo de **empresa contratada** só enxerga a própria empresa —
em toda tela, sempre. Não é um filtro que dá para limpar.

---

## O ciclo de uma semana

```
  Fornecedor          Planejador         Fornecedor        Fiscal        Planejador
  ──────────          ──────────         ──────────        ──────        ──────────
  cria a               valida e           anexa o           aprova o      publica
  programação    →     escolhe      →     realizado    →    realizado  →  a semana
  (na janela)          o fiscal           (dia/noite)
```

Duas coisas que costumam confundir:

- **Validar é o que libera o reporte.** Enquanto a programação está "em
  elaboração", o botão de anexar realizado não aparece — não é falha, é o
  gate.
- **Situação e aprovação são independentes.** Uma programação pode estar
  publicada e ainda ter realizado aguardando o fiscal.

---

## Programar a semana

1. Abra **Programação** e confirme a semana no seletor.
2. **Nova atividade** (só aparece com a janela aberta).
3. Preencha a identificação e a execução.
4. Na produção prevista, use **Dividir em 5 dias úteis** ou **Dividir nos 7
   dias** e ajuste o que precisar. O contador embaixo compara a soma dos dias
   com a produção prevista: enquanto os dois não fecharem, o botão de salvar
   fica desabilitado.

A ID exclusiva não pode repetir dentro da mesma semana.

---

## Anexar o realizado

Esta é a tela mais usada, e foi desenhada para ser difícil de errar.

1. Na linha da atividade, clique no botão verde **Lançar**.
2. Cada dia tem um cartão, com **o previsto impresso ao lado do campo**.
3. Se o dia saiu como planejado, clique em **“= previsto”**. Se a semana
   inteira saiu como planejada, **Copiar a semana inteira**.
4. Só ligue **Turno noite** se houver produção noturna — sem isso, são sete
   campos em vez de quatorze.
5. O total, o PPC e o desvio se atualizam enquanto você digita. Ninguém
   precisa somar de cabeça.
6. Se o realizado ficar muito distante do previsto, a **justificativa passa a
   ser obrigatória** e o botão de salvar espera por ela. O limite é
   configurável em Configurações → Geral.

Depois de aprovado pelo fiscal, o realizado congela. Se algo estiver errado,
o fiscal reabre pelo painel de detalhes, informando o motivo — a reabertura
fica na trilha de auditoria.

---

## Ler a matriz

A linha inteira cabe na tela; a rolagem é só vertical. A tela usa toda a
largura do monitor — num monitor grande cabem mais atividades por vez, não
mais espaço em branco nas laterais.

As colunas são: `#` · Atividade · Execução · os sete dias · Situação ·
Semana · PPC · Ações. Em cada dia, o número
de cima é o previsto e o de baixo é o realizado.

Os sete dias vêm em **duas linhas rotuladas**: `Prev` é o que foi programado,
`Real` é o que foi executado. A unidade da atividade aparece ao lado do
`Prev` — kg, m², m³, m, und ou h — e vale para os catorze números da linha.

Os dois números têm o mesmo tamanho e caem na mesma coluna vertical, para
dar para comparar de relance. O que separa as linhas é a cor e o peso: o
previsto é mais claro, o realizado é o destaque.

**A cor marca a exceção, não a regra.** Entregar um pouco abaixo do previsto
é o caso comum de obra e fica neutro. Saltam aos olhos:

| Cor na linha Real | Significa |
|---|---|
| Vermelho | Dia programado que **não produziu** |
| Verde | Dia que **bateu ou passou** a meta |
| Azul | Produção **sem previsão** para o dia |

O `N` ao lado do número indica que aquele dia inclui turno noite.

O número é arredondado para caber na célula: acima de 100 sai sem decimal,
abaixo de 100 com um decimal, e unidade contável (`und`) nunca leva decimal.
O valor cheio está na dica que aparece ao passar o mouse. Um travessão é
zero — e a diferença entre "não produziu" e "não havia previsão" está na cor.

Em tela estreita — celular ou tablet em retrato — cada atividade vira um
cartão, e os sete dias continuam lado a lado.

### Agir sobre uma atividade

**Clique no nome da atividade** para abrir os detalhes — histórico,
comentários e os números do dia. Não altera nada; é a forma segura de olhar.

No fim da linha ficam duas coisas.

**O botão verde é a sua próxima ação naquela atividade.** Ele não é fixo: a
programação anda numa fila — elaborar, validar, lançar o realizado, aprovar,
publicar — e cada degrau tem um dono diferente. O botão mostra o degrau que é
seu, agora:

| Você é | A atividade está | O botão diz |
|---|---|---|
| Planejador | em elaboração | **Validar** |
| Contratada / Encarregado | validada, sem realizado ou com realizado a ajustar | **Lançar** |
| Fiscal | com realizado aguardando aprovação | **Aprovar** |
| Planejador | com o realizado já aprovado | **Publicar** |
| Visualizador (ou nada a fazer) | qualquer uma | **Ver** |

Quando não há passo seu naquela linha, o botão fica cinza e escrito **Ver** —
é a forma de dizer "aqui não tem nada esperando por você" sem esconder a
atividade.

**O botão de três pontos** abre as outras ações. O que virou botão sai do
menu, para não haver dois caminhos iguais lado a lado; e o menu inteiro
desaparece quando não sobra nada nele, que é o caso de quem só visualiza.
Cada item vem escrito por extenso com uma frase dizendo o que faz:

| Ação | O que acontece |
|---|---|
| Ver detalhes | Abre o painel de leitura |
| Editar a programação | Muda o previsto, a frente, o encarregado |
| Validar a programação | Confere e escolhe o fiscal responsável |
| Aprovar o realizado | Confirma o que a contratada lançou |
| Publicar | Libera para todos e encerra a edição |
| Excluir a atividade | Apaga. Não tem como desfazer |

O menu mostra **só o que o seu perfil pode fazer naquela atividade naquele
momento** — uma atividade já publicada não oferece "Editar", e quem não
aprova realizado não vê "Aprovar". Excluir fica separada por uma linha e em
vermelho, no fim, longe das ações do dia a dia.

`Esc` fecha o menu.

---

## Filtrar e achar

A barra de cima tem a **semana**, a **busca** e o botão **Refinar**.

A busca procura em ID, atividade, frente, empresa, encarregado e fiscal ao
mesmo tempo — digite e a matriz responde sozinha, sem apertar nada.

**Refinar** abre um painel sobre a tela com os filtros separados em dois
grupos: *Onde e quem* (frente, contratada, encarregado, fiscal) e *Em que pé
está* (situação, realizado, faixa de PPC). Cada escolha aplica na hora.
Clique fora, aperte `Esc` ou use **Ver o resultado** para fechar.

**O que está filtrando aparece em pastilhas** logo acima da matriz —
"Contratada: Bremmer", "PPC baixo — abaixo de 60%". Clique no `×` de uma
pastilha para tirar só aquele filtro, ou em **Limpar tudo** para voltar à
semana inteira. É o que evita a situação de abrir a tela, ver poucas linhas e
não saber o que sumiu.

Abaixo da barra ficam as ações da semana — **Baixar em Excel**, **Gerar
relatório para imprimir** e **Publicar as validadas** — sempre à vista.

---

## Importar da planilha

Três passos, e **nada é gravado antes do segundo**:

1. **Baixe o modelo.** Ele já vem com as colunas na ordem certa, um exemplo e
   uma aba "Listas válidas" com tudo que o sistema aceita em Local, Empresa e
   Unidade.
2. **Envie e confira.** O sistema valida linha a linha e mostra o que vai
   gravar. Erro impede a linha de entrar; aviso não. Cada mensagem traz o
   **número da linha da planilha**, para você voltar ao Excel e corrigir.
3. **Confirme.** Só o que passou é gravado, com registro na auditoria.

Uma atividade ocupa duas linhas: `Prev.` e `Real.`. A linha `Real.` é
opcional. A soma dos sete dias precisa bater com a produção prevista, com
tolerância de 0,5.

---

## Ler o dashboard

Os gráficos abrem por mês e **expandem em semanas quando você clica no
nome do mês**. Quando o histórico passa de um ano, aparecem botões para
filtrar por ano. O eixo tem três linhas: semanas, meses e anos.

**Evolução da aderência por contratada** — ocupa a largura toda e é o
primeiro gráfico da tela, porque responde à pergunta que traz alguém ao
dashboard: quem está no ritmo e quem não está.

Cada contratada aparece de duas formas:

| Elemento | O que é |
|---|---|
| **Barra** | Aderência **daquele período isolado** — só aquele mês, ou só aquela semana |
| **Linha** | Aderência **acumulada** até ali, do começo do horizonte |
| **Pastilha na ponta** | O número em que a contratada fechou |
| **Tracejada cinza** | A meta de aderência do projeto |

Cada contratada tem uma cor e **um traço** — contínuo, tracejado, pontilhado.
O traço aparece igual na legenda, e é ele que separa as linhas quando as
cores são dois tons próximos do mesmo verde. Vale também no papel em preto e
branco.

Todos os números estão escritos no gráfico: em cima de cada barra e ao lado de
cada ponto de linha. Quando a tela é estreita demais para caber um deles sem
encostar no vizinho, ele é omitido em vez de sobreposto — e o valor continua
disponível ao passar o mouse.

Ler as duas juntas separa **o mês ruim do patamar ruim**: um tropeço isolado
derruba a barra sem mover a linha; uma queda de patamar move as duas. Era a
leitura que faltava quando o gráfico só tinha a linha.

O acumulado **não muda** quando você abre o mês em semanas — é o mesmo
período, fatiado mais fino. O que muda são as barras.

> A aderência de um mês é o realizado do mês dividido pelo previsto do mês —
> **não** a média das aderências semanais. As duas contas dão números
> diferentes sempre que as semanas têm tamanhos diferentes, que é o caso
> normal. O acumulado segue a mesma regra: soma quantidade período a período
> e divide uma vez só, no fim.

**Previsto contra realizado** — duas barras, período a período, em pontos
percentuais. O mês é a soma das suas semanas.

> As unidades da obra não somam entre si — kg de armação com m³ de solo não
> dá volume nenhum. Por isso o avanço é medido como percentual de conclusão
> por atividade, com peso igual entre elas. É a mesma lógica do PPC.

**Mapa de calor** — dia por frente, com o percentual do previsto daquele dia
entregue naquela frente.

A cor é uma **escala contínua**, do vermelho ao verde, sem faixas: 63% e 66%
têm tons ligeiramente diferentes, porque são números ligeiramente diferentes.
Os dois extremos são os tons fortes — o dia que não produziu e o dia que
entregou tudo — e o meio da escala é o tom fraco, porque ficar na média não é
notícia. A barra de gradiente embaixo da tabela é a legenda.

A célula **hachurada** é o único caso fora da escala: não havia nada
programado para aquele dia naquela frente. Não quer dizer que a frente
parou.

**O que travou a semana** — a lista de ação: atividades abaixo de 60% de PPC,
com a contagem de dias programados que não produziram.

---

## Tirar da ferramenta

**Excel** — sete abas: Resumo com os indicadores, Programação com a matriz
(filtro, painéis congelados, PPC colorido por faixa e linha de total), quebras
por contratada, frente e encarregado, o dia a dia e a série do avanço acumulado.

**PDF** — em Programação → **Gerar relatório para imprimir**. A folha abre com
o layout de impressão já aplicado; use Imprimir e salve em PDF. O que você vê
é o que sai: cabeçalho com projeto e emissão, cabeçalho de tabela repetido em
toda página, linha de atividade que não se parte no meio e rodapé de
continuidade.

---

## Configurar

**Geral** — projeto, cliente, metas de aderência e PPC (elas definem a cor dos
indicadores), a regra de justificativa de desvio e a semana que o app abre.

**Cadastros de apoio** — locais, empresas e unidades. São as listas digitadas
que a validação consulta. **Um valor em uso não pode ser removido** — o
sistema recusa e diz por quantas atividades ele está preso.

A mesma tela mostra, em somente leitura, **Fiscais** e **Encarregados**.
Esses dois não se digitam: são as pessoas cadastradas em **Colaboradores**
com o perfil Fiscal ou Encarregado. Quem estiver ativo lá aparece nos campos
*Fiscal responsável* e *Encarregado* da atividade; quem não estiver, não
aparece.

> Antes eram duas listas de nomes soltos, separadas do cadastro de pessoas.
> Quem entrava alguém na equipe tinha de lembrar de digitar o nome nos dois
> lugares — e a lista que ficava velha era sempre a de apoio, porque o acesso
> da pessoa é o que se lembra de mexer. Agora a pessoa existe uma vez só.

**Janelas de programação** — quando cada contratada pode escrever. Três
camadas, nesta ordem:

1. **Liberação extraordinária** vence tudo. Dentro do intervalo abre mesmo no
   dia errado; fora dele fecha mesmo que a semana estivesse liberada.
2. **Semana liberada** — marque as pastilhas. Os atalhos T1 a T4 e "Ano
   inteiro" fazem em um clique o que antes eram treze.
3. **Dia e horário** — deixe o dia em branco para liberar em qualquer dia das
   semanas marcadas.

O topo de cada cartão diz se a janela está aberta **agora**, e por quê.

**Colaboradores** — restrito ao Administrador, porque é aqui que se concede e
se revoga o acesso. O perfil define o que a pessoa faz; o vínculo define o que
ela enxerga. O sistema não deixa remover o último administrador.
