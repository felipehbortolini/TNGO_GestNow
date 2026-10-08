---
id: ISSUE-047
title: "Produtividade: horas efetivas, amostragem do trabalho e paralisações"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 5
onda: 10
blocked_by:
  - ISSUE-046
blocks:
  - ISSUE-048
labels:
  - ready-for-agent
source_requirements:
  - HU-066
spec_decisions:
  - D6
---

# Produtividade: horas efetivas, amostragem do trabalho e paralisações

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D6.
> Entrega 5 (Planejamento de campo e Programação Semanal), onda 10 (02 Planejamento, campo).
> Histórias: 66. Bloqueada por: ISSUE-046.

## O que construir

A aba **Horas efetivas** registra a fiscalização de campo:

* **Jornada** por frente (empresa, área, encarregado, efetivo) e dia, com
  chegada, início e término dos dois turnos. Capacidade produtiva (CP) =
  execução da manhã + execução da tarde; utilização = CP ÷ jornada de
  referência do parâmetro; atraso de início; almoço; HH efetivas (CP x
  efetivo) e HH improdutivas ((jornada − CP) x efetivo). Um registro por frente
  e dia.
* **Amostragem do trabalho:** rodadas com pessoas trabalhando, em trânsito e
  paradas, com motivo (catálogo de 12 motivos de parada e 5 de trânsito); %
  por dia, Pareto de motivos e resumo por empresa e encarregado.
* **Paralisações:** de efetivo (Hhora = pessoas x horas) ou de máquina e
  equipamento (Mhora = unidades x horas), com motivo e responsabilidade
  (Contratada, Cliente, Gerenciadora, Clima, Terceiros); para cliente,
  gerenciadora e terceiros, o formulário orienta notificar no prazo contratual
  e avaliar pleito em Contratos.

## Critérios de aceite

- [x] CP, utilização, HH efetivas e HH improdutivas têm teste da fórmula.
- [x] Segunda jornada da mesma frente e dia é recusada.
- [x] O Pareto de motivos sai em ordem decrescente com o acumulado.
- [x] Hhora e Mhora calculados conforme o tipo da paralisação.
- [x] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [x] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [x] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo e de fachada. A demonstração traz as 120 jornadas, 240 rodadas e 25 paralisações do mock.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `GI.api.planejamento.produtividade.horasEfetivas`, `salvarJornada`, `salvarAmostragem` e `salvarParalisacao`.

## Registro de execução

- Data: 2026-10-08.
- Feito: modelos `FieldDay`, `WorkSample`, `WorkSampleReason` e `Stoppage` e a migração `m041_jornada_amostragem_paralisacao` (head anterior `m040`), com as quatro tabelas do diagrama. Cálculos em `calculations.py` (seção "Horas efetivas e campo", ISSUE-047: CP, utilização, atraso, almoço, HH efetivas/improdutivas, resumo de capacidade, percentuais e Pareto da amostragem, Hhora/Mhora, faixas e janela do período), validação em `validation.py` (formulários da jornada, da rodada com a grade de motivos e da paralisação), fachada em `service.py` (`hours_overview`, `field_form_options`, `field_day_form`, `work_sample_form`, `stoppage_form`, `save_field_day`, `save_work_sample`, `save_stoppage` e os `load_*` da carga), rotas em `routes.py` (aba, modais, gravações com resposta multi-alvo e Excel/PDF), exportação em `export.py` (`hours_document`, KPIs, Pareto e tabelas), carga `planejamento-campo` em `seed_campo.py` + `seed.py` e a aba Horas efetivas no trio da tela (`app/_views/planejamento/produtividade.html`, `app/paginas/planejamento/produtividade.css` e `.js`), com os testes `test_campo_calculos.py`, `test_campo_servico.py` e `test_campo_rotas.py`, o apoio estendido em `tests/apoio_produtividade.py` e o oráculo em `test_carga_demonstracao.py`.
- Oráculos: no projeto 1 (TN-2026-014), desde o início e sem deslocamento, são 120 jornadas, 240 rodadas, 1.647 motivos e 25 paralisações; CP média 6,81 h/dia (utilização 77,4%), 22.870 HH efetivas e 6.691 HH improdutivas (arredondadas por jornada, como o protótipo soma), atraso médio de 32 min na manhã e 7 min na tarde, almoço de 88 min; 55,26% trabalhando, 9,93% em trânsito e 34,81% parado; o Pareto de paradas começa no direcionamento da liderança (686, acumulado 34,5%) e fecha no direito de recusa (47); 750,0 Hhora, 58,5 Mhora, 372,0 Hhora do cliente e 127,3 Hhora de clima. A carteira soma 180 jornadas, 360 rodadas, 2.411 motivos e 31 paralisações.
- Decisão (divergência de diagrama, registrada): o `encarregado` da jornada e da rodada ficou como **texto** digitado pela fiscalização, como no protótipo (o formulário oferece sugestões dos valores já lançados), e não a FK para `pessoa` que o diagrama trazia — o mock tem os encarregados só como nome (sem cadastro) e o filtro/resumo por encarregado é de tela. O diagrama de `docs/MODELO-DE-DADOS.md` foi atualizado na mesma entrega (`text encarregado` em `jornada_campo` e `amostragem`; `observador_id` e `registrado_por_id` seguem FK de `pessoa`). A UK da jornada ficou `projeto + data + empresa + área + encarregado` ("um registro por frente e dia", como o protótipo recusa), ajustada na nota da tabela no mesmo documento.
- Decisão: o cabeçalho de HH soma os valores arredondados por jornada (1 casa), como o protótipo calcula cada linha antes de somar; a média da CP usa a CP já arredondada de cada dia, como o protótipo exibe. O oráculo afirma esses números (22.870 e 6.691) e não a soma exata antes do arredondamento (22.869 e 6.690).
- Decisão (interação): a tela ganhou as abas Quantidades e Horas efetivas (a de KPIs de performance segue para a ISSUE-048). Cada aba tem a própria toolbar e o próprio filtro (a de Horas com Empresa, Semana de corte, Área, Encarregado e Período), porque no app cada fragmento se atualiza sozinho; os filtros globais da fatia continuam no servidor e a URL carrega a escolha. No Portfólio a aba mostra a coluna Projeto e os botões de inclusão usam o mecanismo `data-tn-incluir` (`jornada`, `amostragem`, `paralisacao`).
- Decisão: o Pareto dos motivos de parada usa a biblioteca de gráficos (`data-grafico="pareto"`, D11); os demais painéis do protótipo viraram tabelas e listas com os mesmos números, e as exportações levam o Pareto (gráfico) e todas as tabelas.
- Verificação: suíte escopada `pytest api/tests/planejamento api/tests/plataforma` verde (1.411 testes; a suíte inteira da API também verde); migração `m041` sobe num banco vazio (`gestnow_m041_check`) com as quatro tabelas; `ruff check`, `ruff format --check` e `ty check` verdes; porta de qualidade completa (`node scripts/verificar.mjs`) verde nas cinco etapas. Sem pendência.
