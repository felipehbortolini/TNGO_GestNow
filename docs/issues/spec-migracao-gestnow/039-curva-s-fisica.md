---
id: ISSUE-039
title: "Curva S física com linha de base congelada, real das medições e drill"
status: proposed
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

- [ ] O real de cada período é a soma ponderada das medições até o fim do período (teste).
- [ ] Uma medição nova muda a curva na consulta seguinte.
- [ ] A base da revisão N continua igual depois da revisão N+1.
- [ ] A curva do Portfólio é ponderada pelos pesos da carteira (teste).
- [ ] O oráculo afirma previsto de 65,7% e real de 61,8% em set/26, ou a divergência fica registrada (ver Notas).
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

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
