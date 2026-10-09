---
id: ISSUE-059
title: "Processo de compra: da requisição à negociação"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 6
onda: 12
blocked_by:
  - ISSUE-058
blocks:
  - ISSUE-060
labels:
  - ready-for-agent
source_requirements:
  - HU-100
spec_decisions:
  - D7
  - D5a
---

# Processo de compra: da requisição à negociação

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D7, D5a.
> Entrega 6 (Suprimentos e Riscos), onda 12 (04 Suprimentos).
> Histórias: 100. Bloqueada por: ISSUE-058.

## O que construir

A tela **Processos de compra** lista os processos com a etapa (barra de 9
segmentos no visual Etapas), propostas, melhor proposta e alçada. A **ficha do
processo** mostra as 9 etapas, o resumo, o mapa de equalização (notas técnica,
comercial e final, ranking, desvios, anexos) e o histórico.

Ações desta issue, validadas no servidor: **Nova requisição**; **Emitir RFx**
(convidados; mínimo de propostas do parâmetro ou fornecedor único com
justificativa; fornecedor Bloqueado não é convidado); **Registrar proposta**
(PDF anexo); **Encerrar recebimento** (abaixo do mínimo exige justificativa);
**Equalização técnica** (notas e aprovação; proposta reprovada não segue);
**Equalização comercial** (prévia do ranking; técnica sempre antes);
**Negociação** (nota comercial = menor preço tecnicamente aprovado ÷ preço x
100; nota final ponderada pelos pesos). Cada ação grava a data realizada do
marco correspondente no pacote (base do MAS) e o histórico do processo.

## Critérios de aceite

- [x] RFx abaixo do mínimo sem justificativa é recusada, e fornecedor Bloqueado não entra como convidado.
- [x] Comercial antes da técnica é recusada; proposta reprovada não segue.
- [x] Nota comercial e final têm teste com fronteira.
- [x] Cada ação grava a data do marco no pacote e uma linha no histórico.
- [x] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [x] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [x] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo (ranking) e de fachada (cada ação e as recusas). A demonstração traz o PC-14 em equalização comercial.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `processos.html`, `GI.api.suprimentos.acaoProcesso`; README, "Fluxo do processo de compra".

## Registro de execução

- Data: 08/10/2026
- Feito: tela Processos de compra (régua Etapas, KPIs, ficha com resumo, mapa de equalização e histórico), as sete ações até a negociação, o PDF da proposta como anexo (D5a), Excel/PDF, a carga `suprimentos-processos` e a migração `m047_processos_de_compra.py`.
- Verificação: testes de cálculo, fachada, rotas e oráculo da carga escritos e não executados (política de testes do dono); `ruff check`/`format` passam nos arquivos tocados; a migração não foi executada num banco vazio (política).
- Pendências: ISSUE-060 (recomendação, aprovação por alçada e emissão); a porta de qualidade fica para o dono.
- DECISAO: fornecedor sem cadastro | convidado, proposta e negociação guardam `nome` com `empresa_id` vazio; o diagrama mudou na mesma entrega | D5, ISSUE-059
- DECISAO: etapa do processo | sai da última linha do histórico (o PC-14 fica em equalização comercial), com a etapa das datas reais do pacote como fallback | D5b, ISSUE-059
- DECISAO: numeração da RFx | série global por tipo e ano (RFQ/RFP), como o protótipo; o `core.numbering` é por projeto e não cobre a série | D5, ISSUE-059
- DECISAO: justificativas sem coluna | fornecedor único e exceção ao mínimo viajam na linha do histórico, como a emergência da ISSUE-058 | D5b, ISSUE-059
- DECISAO: Nova requisição | documento e observação vão na trilha do pacote; o arquivo da especificação não é coletado (sem anexo do pacote) | D5a, ISSUE-059
