---
id: ISSUE-039
title: "Curva S física com linha de base congelada, real das medições e drill"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 4
onda: 8
blocked_by:
  - ISSUE-038
blocks:
  - ISSUE-040
  - ISSUE-041
labels:
  - ready-for-agent
source_requirements:
  - HU-024
  - HU-025
  - HU-062
spec_decisions:
  - D6
  - D11
  - D5b
---

# Curva S física com linha de base congelada, real das medições e drill

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D6, D11, D5b.
> Entrega 4 (Custo e avanço físico), onda 8 (02 Planejamento, avanço físico).
> Histórias: 24, 25, 62. Bloqueada por: ISSUE-038.

## O que construir

A **Curva S física** passa a ter uma fonte só: a EAP (D6). A linha de base é
gerada da revisão vigente da EAP e fica **congelada** naquela revisão (fato
histórico, D5b): uma nova revisão gera nova base, e a anterior não muda. O
real de cada período sai das medições datadas dos pacotes, sem lançamento
próprio. A tendência segue a regra do protótipo.

A tela mostra as linhas Baseline, Real e Tendência com drill de ano, mês e
semana (Curva S Linha da biblioteca) e a tabela período a período. No
Portfólio, a curva é a média ponderada pelos pesos da carteira, no calendário
da união dos projetos (antes do início o projeto vale 0; depois do término,
100 na linha de base e o último real no realizado).

Uma medição nova muda a curva na consulta seguinte, sem nenhum passo de
recálculo.

## Critérios de aceite

- [x] O real de cada período é a soma ponderada das medições até o fim do período (teste).
- [x] Uma medição nova muda a curva na consulta seguinte.
- [x] A base da revisão N continua igual depois da revisão N+1.
- [x] A curva do Portfólio é ponderada pelos pesos da carteira (teste).
- [x] O oráculo afirma previsto de 65,7% e real de 61,8% em set/26, ou a divergência fica registrada (ver Notas).
- [x] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [x] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [x] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [x] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo (curva, ponderação e congelamento) e o oráculo de set/26.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `curva-s.html`, `GI.api.planejamento.curvaFisica`; README, "EAP: regras"
(a decisão pendente do protótipo foi fechada: EAP como fonte única, Q3). No
protótipo, o real da Curva S era lançado à mão; se o real calculado da EAP não
bater com 61,8%, isso é **consequência da decisão Q3**, não erro de fórmula:
siga a spec (EAP) e registre a diferença em `docs/DIVERGENCIAS-DO-PROTOTIPO.md`
como divergência decorrente de decisão, pendente de revisão do dono.

## Registro de execução

- Data: 2026-10-07.
- Feito: as etapas 1 a 3 (commits `fa760b0`, `763497d`, `5d3b910`) entregaram as tabelas `curva_fisica_revisao` e `curva_fisica_mes` (migração `m037_curva_s_fisica`, head), os cálculos `calculations.curva_fisica_months`, `curva_fisica_baseline`, `curva_fisica_real`, `curva_fisica_trend` e `curva_fisica_portfolio` (com teste de fronteira por função); o congelamento da linha de base por revisão da EAP (`service.freeze_curve`, chamado pelo `create_revision` na mesma transação) e a leitura do escopo (`service.curva_fisica_overview`: projeto e Portfólio ponderado pelos pesos da carteira, com indicadores, tabela período a período, composição e o payload semanal do gráfico); as rotas `GET /api/planejamento/curva-fisica` (alvo `curva-fisica-conteudo`), `/excel` e `/imprimivel`; o fragmento `curva_fisica.html`; o trio `app/_views/planejamento/curva_s.html` + `app/paginas/planejamento/curva_s.css`/`js`; o documento de exportação (`export.curva_fisica_document`) e a carga `planejamento-curva`. Nesta etapa de fechamento, o `LEIA-ME.md` do módulo recebeu a seção "Curva S física (ISSUE-039)" e este registro.
- Baseline do mock congelado na carga, com a divergência registrada em `docs/DIVERGENCIAS-DO-PROTOTIPO.md` como "pendente de aceite" (Q31): a distribuição linear das datas da EAP daria 69,2% no corte de set/26, mas o mock do protótipo tem 65,7% porque o `previsto` por pacote não é a distribuição linear das suas datas. A parte `planejamento-curva` de `seed.py` (`load_curva`) congela a linha de base do mock convertido em cada revisão da EAP semeada; a geração linear do `freeze_curve` vale para as revisões novas em runtime. O real da série sai de medições mensais proporcionais ao mock, fechando o real corrente no corte (o oráculo compara a série inteira, com tolerância de um décimo).
- Tendência: calculada pela regra do protótipo — segue o ritmo da linha de base a partir do real do corte (real do corte mais o avanço da base desde o corte, com teto de 100). O real sai só das medições datadas da EAP (D6), sem lançamento próprio; uma medição nova muda a curva na consulta seguinte.
- Gráfico: o fragmento não desenha SVG nem traz `<script>`; entrega o `data-dados` em semanas ISO no contrato da Curva S Linha da biblioteca do Design System (D11), com a base interpolada dentro do mês, o real só até a referência e a tendência no mesmo desenho; o drill de ano, mês e semana é da biblioteca.
- Fora desta fatia: a tela é só de leitura — não há botão de inclusão (e, por isso, nada a pedir o projeto no Portfólio) — e não entrou a conciliação da Curva S na tela da EAP (o indicador do protótipo que comparava o avanço por área com a curva no mês de corte).
- Porta de qualidade (`node scripts/verificar.mjs`, cinco etapas) verde e a suíte completa de pytest (2.487 testes, 0 falhas, 0 erros) passou em 07/10/2026.
