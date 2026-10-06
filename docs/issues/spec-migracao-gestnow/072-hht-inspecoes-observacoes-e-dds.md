---
id: ISSUE-072
title: "HHT, inspeções de segurança, observações e DDS"
status: in-progress
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 7
onda: 15
blocked_by:
  - ISSUE-012
  - ISSUE-013
  - ISSUE-016
  - ISSUE-018
blocks:
  - ISSUE-073
  - ISSUE-075
labels:
  - ready-for-agent
source_requirements:
  - HU-121
spec_decisions:
  - D6
---

# HHT, inspeções de segurança, observações e DDS

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D6.
> Entrega 7 (Qualidade, HSE e Configurações), onda 15 (07 HSE).
> Histórias: 121. Bloqueada por: ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018.

## O que construir

A tela **Horas trabalhadas (HHT)** registra horas-homem trabalhadas e efetivo
médio por mês e por empresa, base de todas as taxas, com formulário mensal e
importação Excel. Editar reabre o mesmo registro, com mês e empresa
bloqueados.

A tela **Inspeções e observações** registra inspeções de segurança por
checklist (itens conformes e não conformes), observações comportamentais e DDS
(tema, data, participantes), mais o consolidado mensal (DDS, inspeções,
observações e desvios, um por mês), com importação Excel. O nível 5 da
pirâmide (desvios) vem consolidado daqui.

O **histograma de mão de obra** (previsto, derivado do HHT e da Curva S física)
passa a ser calculado no servidor e aparece onde o protótipo o mostrava: na
tela de HHT e no Cronograma de desembolso.

## Critérios de aceite

- [ ] HHT é um registro por mês e empresa: gravar de novo atualiza, sem duplicar.
- [ ] A importação recusa linhas inválidas e grava as válidas só na confirmação.
- [ ] O consolidado mensal é um por mês.
- [ ] O histograma é calculado do HHT e da Curva S e aparece no HHT e no desembolso.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (registros e importação) e de cálculo (histograma).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `hht.html` e `inspecoes.html` do HSE, `mock-hse`; `histogramaMaoDeObra` gerado no fim de `mock-portfolio` e usado em `js/pages/hse/hht.js` e `js/pages/financeiro/desembolso.js`.
