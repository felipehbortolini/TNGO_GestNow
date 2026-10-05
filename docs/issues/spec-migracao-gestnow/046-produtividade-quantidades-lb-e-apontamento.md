---
id: ISSUE-046
title: "Produtividade: plano de quantidades, ciclo da linha de base e apontamento semanal"
status: proposed
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

- [ ] A distribuição por perfil fecha o total pelo maior resto (teste por perfil).
- [ ] Quem elaborou não aprova (403).
- [ ] Revisão sem SM aprovada é recusada; com ela, congela as semanas passadas e redistribui o saldo.
- [ ] Os três limites do apontamento são recusados com a mensagem.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo (distribuição) e de fachada (ciclo, revisão, apontamento e importação).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `produtividade.html` e `js/pages/planejamento/produtividade.js`,
`GI.api.planejamento.produtividade.*`, `mock-planejamento`; README,
"Produtividade: regras".
