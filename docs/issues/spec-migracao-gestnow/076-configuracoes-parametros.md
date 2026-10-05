---
id: ISSUE-076
title: "Parâmetros: edição por grupo com justificativa, versões e histórico"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 7
onda: 16
blocked_by:
  - ISSUE-066
blocks: []
labels:
  - ready-for-agent
source_requirements:
  - HU-131
  - HU-132
  - HU-134
spec_decisions:
  - D6
  - D7
---

# Parâmetros: edição por grupo com justificativa, versões e histórico

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D6, D7.
> Entrega 7 (Qualidade, HSE e Configurações), onda 16 (Configurações).
> Histórias: 131, 132, 134. Bloqueada por: ISSUE-066.

## O que construir

A tela **Configurações > Parâmetros** mostra a versão vigente (versão,
vigência, autor, justificativa) e os grupos por módulo (Avaliação de
contratadas, Financeiro, Suprimentos, Riscos, Qualidade, HSE, Planejamento,
Governança, Portfólio e Anexos) com os valores vigentes, busca e filtro por
módulo.

**Editar** por grupo abre o modal com justificativa obrigatória; gravar cria
nova versão com vigência, pela validação da ISSUE-007 (erro por campo em 422).
A troca de escala de riscos pede confirmação, porque muda a contagem de
críticos em todo o sistema. **Histórico de versões** mostra as alterações
(antes e depois) de cada versão. Só Gestor e Admin chegam à tela e gravam.

Efeito: pesos e prazos valem para registros novos (avaliações e ocorrências
guardam o que valia); critérios de exibição (base das taxas, referência da
pirâmide, escala de severidade, faixas do mapa de calor) recalculam as telas na
hora.

## Critérios de aceite

- [ ] Gravar cria nova versão com vigência, e sem justificativa é recusado.
- [ ] Erros de validação voltam por campo com 422.
- [ ] A troca de escala de riscos pede confirmação e muda a contagem de críticos na consulta seguinte.
- [ ] O histórico mostra antes e depois de cada versão.
- [ ] Quem não é Gestor ou Admin recebe 403.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (versão, validação, efeito daqui em diante e recálculo de exibição) e de rota (403 e 422).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `parametros.html` e `js/pages/configuracoes/parametros.js`, `GI.api.parametros`, `salvarParametros` e `historicoParametros`; README, seção 7.4.
