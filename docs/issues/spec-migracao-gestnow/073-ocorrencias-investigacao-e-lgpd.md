---
id: ISSUE-073
title: "Ocorrências com investigação, prazos legais e dados restritos (LGPD)"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 7
onda: 15
blocked_by:
  - ISSUE-072
  - ISSUE-019
  - ISSUE-027
blocks:
  - ISSUE-075
labels:
  - ready-for-agent
source_requirements:
  - HU-120
  - HU-124
spec_decisions:
  - D5a
  - D5b
  - D7
  - D9
---

# Ocorrências com investigação, prazos legais e dados restritos (LGPD)

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D5a, D5b, D7, D9.
> Entrega 7 (Qualidade, HSE e Configurações), onda 15 (07 HSE).
> Histórias: 120, 124. Bloqueada por: ISSUE-072, ISSUE-019, ISSUE-027.

## O que construir

A tela **Ocorrências** registra, investiga e trata. **Nova ocorrência**: data e
hora, área e local, empresa, tipo, descrição, gravidade real e **potencial**
(matriz 5x5), marcação de **alto potencial (HiPo)**, pessoas envolvidas e
função (sem nome no registro geral), dias perdidos e debitados, comunicação
legal quando aplicável, causa imediata e evidências (anexos). O tipo define o
nível da pirâmide; ocorrência Ambiental tem severidade própria e fica fora
dela.

Fluxo: Registrada, Em investigação, Ações definidas, Em tratamento, Encerrada
(eficácia verificada). Prazos de comunicação, investigação preliminar e
relatório final (LTI e HiPo) vêm dos parâmetros e o **prazo vigente fica
gravado na ocorrência** (D5b). Investigação com método registrado; ações
corretivas pela costura da Central (origem HSE; o link distingue ocorrência de
estudo de risco). **HiPo encerrada gera lição obrigatória** em Rascunho.

**LGPD:** nome e dados médicos ficam em tabela de acesso restrito. Membro
preenche, mas só Gestor e Admin leem esse campo e os anexos com esses dados
(decisão Q35).

## Critérios de aceite

- [ ] O prazo vigente fica gravado, e mudar o parâmetro depois não muda a ocorrência.
- [ ] Fluxo com prazos vencidos sinalizados pela data de hoje.
- [ ] Ações corretivas nascem na Central com link de volta à ocorrência.
- [ ] HiPo encerrada sem lição é recusada.
- [ ] Quem não é Gestor ou Admin não lê o campo restrito nem baixa os anexos com dados pessoais (403).
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (fluxo, prazos, ações, lição e acesso restrito) e de rota (403 no campo e no anexo).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `ocorrencias.html`, `js/pages/hse/ocorrencias.js` e `hse.js`; README, "07 HSE" (classificação, campos, fluxo e privacidade).
