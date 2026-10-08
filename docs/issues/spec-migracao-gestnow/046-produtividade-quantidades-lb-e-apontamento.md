---
id: ISSUE-046
title: "Produtividade: plano de quantidades, ciclo da linha de base e apontamento semanal"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 5
onda: 10
blocked_by:
  - ISSUE-025
blocks:
  - ISSUE-047
  - ISSUE-048
labels:
  - ready-for-agent
source_requirements:
  - HU-065
spec_decisions:
  - D5b
  - D9
---

# Produtividade: plano de quantidades, ciclo da linha de base e apontamento semanal

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D5b, D9.
> Entrega 5 (Planejamento de campo e Programação Semanal), onda 10 (02 Planejamento, campo).
> Histórias: 65. Bloqueada por: ISSUE-025.

## O que construir

A tela **Produtividade** nasce com os filtros globais Empresa e Semana de corte
e a aba **Quantidades**.

**Plano de quantidades:** item por empresa com grupo, tipo, disciplina,
unidade, quantidade total da linha de base, índice orçado (HH por unidade) e
semanas ISO inicial e final. O total é distribuído por semana pelo perfil
(Curva S 20/60/20, linear, concentrado no início ou no fim) e pode ser ajustado
semana a semana; a soma fecha com o total pelo maior resto.

**Ciclo da linha de base:** Em elaboração (editável, fora dos indicadores) e
Aprovada (Gestor; quem elaborou não aprova). Aprovada, a distribuição fica
congelada (fato histórico, D5b); mudança só por **revisão com SM aprovada** e
justificativa: as semanas até a atual ficam congeladas, o saldo é redistribuído
dali em diante e o novo total não pode ser menor que o realizado. Histórico de
revisões na ficha do item. Importação de itens pelo fluxo genérico.

**Apontamento semanal:** a contratada informa realizado e HH apropriadas por
item e semana (atualiza se já existir). Não aponta semana futura; HH
obrigatórias quando há realizado; acumulado acima do total da linha de base é
recusado (exige SM e revisão).

## Critérios de aceite

- [x] A distribuição por perfil fecha o total pelo maior resto (teste por perfil).
- [x] Quem elaborou não aprova (403).
- [x] Revisão sem SM aprovada é recusada; com ela, congela as semanas passadas e redistribui o saldo.
- [x] Os três limites do apontamento são recusados com a mensagem.
- [x] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [x] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [x] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [x] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo (distribuição) e de fachada (ciclo, revisão, apontamento e importação).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `produtividade.html` e `js/pages/planejamento/produtividade.js`,
`GI.api.planejamento.produtividade.*`, `mock-planejamento`; README,
"Produtividade: regras".

## Registro de execução

- Data: 2026-10-07.
- Feito: modelos `ProductivityItem`, `ProductivityRevision`, `ProductivityDistribution` e `ProductivityEntry` e a migração `m040_produtividade` (head anterior `m039`), com as quatro tabelas do diagrama. Cálculos em `calculations.py` (perfis e maior resto, figuras do item, série semanal, gráficos D11, revisão/congelamento e limites do apontamento), validação em `validation.py` (formulário do item, da revisão e do apontamento), fachada em `service.py` (`quantities_overview`, `item_detail`, `save_item`, `approve_item`, `delete_item`, `revise_item`, `register_entries`, `import_item`, `load_item`), rotas em `routes.py` (tela, modais, gravações com resposta multi-alvo, importação pelo fluxo genérico e Excel/PDF), exportação em `export.py`, importador `produtividade-itens` em `importers.py`, carga `planejamento-produtividade` em `seed_produtividade.py` + `seed.py` e o trio da tela (`app/_views/planejamento/produtividade.html`, `app/paginas/planejamento/produtividade.css` e `.js`), com os testes `test_produtividade_calculos.py`, `test_produtividade_servico.py` e `test_produtividade_rotas.py` e o apoio `tests/apoio_produtividade.py`.
- Oráculos: no projeto 1, no corte S39 e sem deslocamento, o avanço por quantidades fecha em 59,2% contra 67,5% previstos (SPI 0,88), FP 1,08 na janela de 4 semanas (acumulado 1,08), aderência da semana 80,7%, 2 apontamentos pendentes e 8 itens com tendência de atraso; os totais por projeto são 173.214 (TN-2026-014), 2.002 (TN-2026-021) e 1.108 (TN-2026-027), com 14 itens, 170 apontamentos e 328 semanas de distribuição. A carteira mistura unidades e a série sai em horas ganhas.
- Decisão (divergência de redação com o protótipo): a issue descreve o saldo da revisão como "novo total − realizado"; foi implementado (e é o que o protótipo calcula) **novo total − previsto das semanas congeladas**, porque a soma da distribuição nova precisa fechar com o novo total — o realizado não é a LB das semanas passadas. O novo total continua não podendo ser menor que o realizado nem que o congelado, com mensagem própria. Sem impacto no oráculo (o mock não revisa item depois de apontar).
- Decisão: a distribuição do mock pertence à revisão vigente de cada item; as revisões anteriores ficam só com o total congelado (`produtividade_revisao.total`), porque o mock não guarda a distribuição antiga; a ficha do item mostra as duas.
- Decisão: a segregação "quem elaborou não aprova" usa a revisão 0 (`produtividade_revisao.por_id`), que nasce com o item — o diagrama não tem `elaborado_por_id` no item, e a revisão 0 é o fato que já registra o autor da LB; nenhuma coluna nova precisou entrar no modelo.
- Verificação: suíte escopada `pytest api/tests/planejamento api/tests/plataforma` verde; migração `m040` sobe num banco vazio (`gestnow_m040_check`) com as quatro tabelas; `ruff check`, `ruff format --check` e `ty check` verdes; porta de qualidade completa (`node scripts/verificar.mjs`) verde nas cinco etapas. Não há pendência nem divergência de protótipo além da registrada acima.
