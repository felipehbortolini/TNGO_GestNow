---
id: ISSUE-038
title: "Revisões da EAP a partir de SM e desdobramento de pacotes de planejamento"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 4
onda: 8
blocked_by:
  - ISSUE-037
  - ISSUE-025
blocks:
  - ISSUE-039
labels:
  - ready-for-agent
source_requirements:
  - HU-060
  - HU-061
  - HU-128
spec_decisions:
  - D9
---

# Revisões da EAP a partir de SM e desdobramento de pacotes de planejamento

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D9.
> Entrega 4 (Custo e avanço físico), onda 8 (02 Planejamento, avanço físico).
> Histórias: 60, 61, 128. Bloqueada por: ISSUE-037, ISSUE-025.

## O que construir

Estrutura, pesos, quantidades e términos só mudam por **nova revisão** a
partir de SM aprovada com impacto em escopo ainda não incorporada (papel
Gestor): o pacote afetado recebe o novo peso (e quantidade ou término), os
pacotes novos entram com o peso informado e uma cópia das etapas do modelo dos
parâmetros, e os demais pesos são reescalados pelo maior resto para fechar
100%. Peso máximo por pacote: o do parâmetro (10%). A importação de pacotes
também gera revisão.

**Desdobramento**: o pacote de planejamento é desdobrado em pacotes de
trabalho; o peso sai dele para o pacote novo, o previsto é mantido e o total do
projeto não muda; com peso zero, ele é encerrado. Os desdobramentos da revisão
vigente ficam listados com justificativa. O indicador "SMs a incorporar"
aparece na tela.

Ligação com a Governança: a ficha da SM aprovada com impacto em escopo mostra
o alerta, a próxima etapa e a linha "Nova revisão da EAP (02)", o encerramento
exige a revisão, e o encerramento registra "EAP Rev N" nas linhas de base
conferidas.

## Critérios de aceite

- [ ] O maior resto fecha 100% em toda revisão (teste de fronteira).
- [ ] Peso acima do máximo é recusado.
- [ ] Revisão sem SM aprovada com impacto em escopo é recusada.
- [ ] O desdobramento mantém o total do projeto e encerra o pacote de planejamento zerado.
- [ ] O encerramento da SM exige a revisão da EAP e registra "EAP Rev N".
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo (maior resto) e de fachada (revisão, desdobramento, importação e ligação com a SM).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `GI.api.planejamento.eapNovaRevisao`, `eapNovoPacote` e `eapEditarPacote`; README, "EAP: regras".
