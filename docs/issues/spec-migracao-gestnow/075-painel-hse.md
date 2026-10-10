---
id: ISSUE-075
title: "Painel HSE"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 7
onda: 15
blocked_by:
  - ISSUE-072
  - ISSUE-073
  - ISSUE-074
  - ISSUE-034
blocks:
  - ISSUE-079
  - ISSUE-082
labels:
  - ready-for-agent
source_requirements:
  - HU-122
spec_decisions:
  - D6
  - D11
---

# Painel HSE

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D6, D11.
> Entrega 7 (Qualidade, HSE e Configurações), onda 15 (07 HSE).
> Histórias: 122. Bloqueada por: ISSUE-072, ISSUE-073, ISSUE-074, ISSUE-034.

## O que construir

O **Painel HSE** tem filtro de Ano e Mês e os KPIs reativos (TF, TRIF, TG e
HiPo) em dois blocos, "No mês selecionado" e "Acumulado" (do primeiro mês com
HHT até o mês escolhido); "Dias sem afastamento" e "Ações HSE no prazo" ficam
só no acumulado. Duas pirâmides (mês e acumulado), no visual da ISSUE-016,
comparadas com a proporção de referência do parâmetro (Bird ou Heinrich). Os
proativos (relato de quase acidentes, DDS realizados ÷ programados,
observações por 10 mil HHT com a meta, conformidade em inspeções, ações no
prazo, recomendações fechadas, incidentes ambientais), a evolução mensal de TF
e TRIF (linhas múltiplas) e as ocorrências por empresa e área.

Taxas na base do parâmetro (1.000.000 de HHT, NBR 14280, ou 200.000, OSHA):
TF = (fatalidades + afastamentos) x base ÷ HHT; TRIF = (fatalidades +
afastamentos + trabalho restrito + tratamento médico) x base ÷ HHT; TG = (dias
perdidos + debitados) x base ÷ HHT. Dias sem afastamento: desde a última LTI;
sem LTI, desde o início do projeto.

A nota HSE da contratada alimenta o critério HSE da avaliação de desempenho
(03), como no protótipo.

## Critérios de aceite

- [ ] TF, TRIF e TG têm teste, inclusive HHT zero.
- [ ] Trocar a base ou a referência no parâmetro recalcula na hora.
- [ ] Dias sem afastamento conta da última LTI ou do início do projeto.
- [ ] O oráculo afirma 263 dias sem afastamento e a pirâmide acumulada 0/16/31/190/1.240.
- [ ] A avaliação de desempenho recebe a nota HSE da contratada.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo das taxas, o oráculo do HSE e o teste da ligação com a avaliação.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `painel.html` do HSE, `GI.api.hse.indicadores`, nível da pirâmide em `regras.js`; README, "07 HSE". O botão Análise do período chega na ISSUE-082.

## Registro de execução

Fatia entregue em 10/10/2026: o **Painel HSE** calculado a cada leitura, sem nada gravado (D5b).
A fachada nova (`painel_service.py`) lê o HHT e os fechamentos do próprio módulo e as ações de
HSE pela fachada da Central (leitura nova `actions_of_origin_or_group`: origem `HSE` das
ocorrências/recomendações **ou** grupo `HSE` das atas, nunca a tabela `acao`, D9), e monta as duas
janelas do protótipo — "No mês selecionado" (o mês escolhido) e "Acumulado" (do primeiro mês com
HHT até ele) — com as taxas (TF/TRIF/TG pela `calculations.rate_hse`, sem HHT não há taxa), a
pirâmide de 5 níveis (o 5º, desvios, do consolidado mensal), o HiPo, os ambientais, os dias sem
afastamento (da última LTI ou do início do projeto/carteira, `calculations.days_without_leave`) e
os proativos (DDS, conformidade, observações por 10 mil HHT, relato de quase acidentes com a
referência do parâmetro, recomendações fechadas ÷ emitidas da ISSUE-074 e as ações HSE no prazo —
vencidas até a data de referência e concluídas até o prazo, meta de 90% do protótipo). A base
(`baseTaxa`) e a referência (`referenciaPiramide`) vêm do grupo `hse` dos parâmetros vigentes a
cada leitura: trocar o parâmetro recalcula na hora, e a tela ainda sobrepõe a referência pela
query (`referencia`, o segmentado Bird/Heinrich). Os dois visuais da biblioteca (D11): a pirâmide
dupla `piramide-seguranca` (mês e acumulado, com a proporção de referência e a razão de quase
acidentes de cada leitura) e a evolução mensal de TF e TRIF em `linhas-multiplas` (um ponto por
mês com HHT). A tela (`painel_routes.py`, blueprint `hse_painel_bp`; fragmento
`painel-conteudo`; query `ano`/`mes`/`referencia`; nomes `hse_panel_*` únicos no app) traz a barra
de filtros, a linha de período ("Mês: Set/2026 · Acumulado: Jan/2026 a Set/2026 · base 1.000.000
HHT (NBR 14280)"), os três blocos de indicadores e as listas por área e por empresa (as até 8
maiores, com barra proporcional); o Excel e o PDF saem pelos mecanismos genéricos com o mesmo
conteúdo do protótipo (KPIs com o bloco no rótulo, tabelas das duas pirâmides com os nomes dos
níveis, a evolução e as listas). O trio da tela foi reescrito no padrão do painel da qualidade
(cinco estados, recarga com a query lembrada). **A nota HSE da contratada** (decisão do dono em
10/10/2026, resposta à ambiguidade do protótipo): o painel calcula por empresa a nota sugerida de
1 a 5 — sem HHT da empresa não há sugestão; 5 se a TRIF da empresa é zero, 4 até a do projeto, 3
até o dobro, 2 até o quádruplo, 1 acima (com as TRIF arredondadas como a tela as lê) — e uma LTI
na janela limita a nota a 2; o Financeiro (03) a consome no formulário da avaliação de desempenho
(`_contrato_avaliacao_form_context` chama `hse_painel.company_note_suggestion`; o critério HSE
ganhou o hint "Sugestão do HSE: nota X · TRIF da empresa A contra B do projeto" e a
pré-seleção quando o formulário está novo, e o avaliador pode trocar — a nota gravada é a que ele
confirmar). O `ContractView` ganhou `company_id` (a empresa do contrato) e não há ciclo de
importação (o HSE não importa o Financeiro). Oráculo do projeto 1 em 25/09/2026 (números
conferidos contra o convertido): mês padrão 2026-09, janela 2026-01 a 2026-09; taxas do mês 0,00 /
6,80 / 0,0 com pirâmide 0/2/5/32/189; acumulado 0,00 / 8,88 / 0,0 com pirâmide **0/16/31/190/1.240**
e **263 dias** sem afastamento (sem LTI, desde 05/01/2026); 9 pontos de evolução; topo das listas
Terraplenagem 39 e Zeta Civil 132; ações HSE no prazo 50,0% (1 das 2 vencidas); nota sugerida da
Alfa Montagens 3 (TRIF 11,01 contra 8,88 do projeto). Sem migração (nada é gravado). Divergências
registradas: a nota HSE sugerida (o protótipo nunca a calculava) e a troca da referência na tela
recarregando o fragmento pela query (o protótipo trocava localmente); o botão "Análise do
período" fica para a ISSUE-082. `ruff check`, `ruff format --check`, `ty check` e o eslint dos
arquivos do trio limpos; a suíte (HSE, Financeiro, Central, Governança, Qualidade, plataforma e
oráculo — 2.429 testes nas rodadas do fechamento) passa; a porta de qualidade, 5/5.

- DECISAO: nota HSE sugerida da contratada | o painel calcula por empresa a nota de 1 a 5 pela TRIF contra a do projeto (5 se zero; 4 até a do projeto; 3 até o dobro; 2 até o quádruplo; 1 acima; sem HHT da empresa não há sugestão; LTI na janela limita a 2) e a avaliação de desempenho a exibe e pré-seleciona no critério HSE, com a nota gravada sendo a que o avaliador confirmar | decisão do dono em 10/10/2026, ISSUE-075
- DECISAO: referência da pirâmide na tela | o segmentado Bird/Heinrich recarrega o fragmento pela query (`referencia`), sobrepondo o parâmetro naquela leitura; o servidor redesenha os gráficos como dados (D6/D11) | ISSUE-075
- DECISAO: leitura das ações de HSE | leitura nova na fachada da Central (`actions_of_origin_or_group`, origem `HSE` ou grupo `HSE`, só ações, no escopo) para o card "Ações HSE no prazo"; nenhum módulo lê a tabela `acao` | D9, ISSUE-075
- DECISAO: listas por área e por empresa | barras horizontais escopadas na tela (como o protótipo desenhava), com as até 8 maiores; o `comparativo-barras` da biblioteca compara períodos e não serve aqui | D11, ISSUE-075

