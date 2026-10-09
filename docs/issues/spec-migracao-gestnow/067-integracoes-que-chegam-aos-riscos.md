---
id: ISSUE-067
title: "Integrações que chegam aos Riscos: risco sugerido do diligenciamento, claim, lição aplicada e cobertura da contingência"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 6
onda: 13
blocked_by:
  - ISSUE-066
  - ISSUE-061
  - ISSUE-033
  - ISSUE-027
  - ISSUE-041
blocks: []
labels:
  - ready-for-agent
source_requirements:
  - HU-103
  - HU-128
spec_decisions:
  - D9
---

# Integrações que chegam aos Riscos: risco sugerido do diligenciamento, claim, lição aplicada e cobertura da contingência

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D9.
> Entrega 6 (Suprimentos e Riscos), onda 13 (05 Riscos).
> Histórias: 103, 128. Bloqueada por: ISSUE-066, ISSUE-061, ISSUE-033, ISSUE-027, ISSUE-041.

## O que construir

Liga as integrações cujo segundo ponto é o módulo de Riscos, cada uma ponta a
ponta, pela fachada do dono:

* **Diligenciamento:** Registrar risco sugerido abre o modal pré-preenchido e
  o risco entra como Em análise, categoria Suprimentos, origem
  "Diligenciamento PED-...", sem duplicar.
* **Claim:** claim relacionado a risco fica vinculado ao registro, com link
  nos dois sentidos.
* **Lições:** Aplicar em projeto pode criar risco Identificado (ameaça para "A
  evitar", oportunidade para "A repetir", origem Lições aprendidas), e a lição
  passa a aceitar a origem Risco encerrado com o número conferido.
* **Contingência:** a cobertura do saldo sobre a exposição (VME das ameaças
  ativas, meta do parâmetro) e a lista de ameaças ativas com as SMs
  vinculadas aparecem na tela de Contingência.
* **Links de origem:** os tipos de Risco passam a resolver na Central e nas
  lições.

## Critérios de aceite

- [ ] Cada uma das cinco integrações tem teste de fachada ponta a ponta.
- [ ] O risco sugerido não duplica para o mesmo pedido.
- [ ] A cobertura da contingência usa só as ameaças ativas e a meta do parâmetro.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada das integrações.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `GI.api.suprimentos.registrarRisco`, vínculo de claim a risco, `GI.api.governanca.aplicarLicao`; README, tabela "Integração entre módulos".

## Registro de execução

Fatia entregue em 09/10/2026: as cinco integrações de chegada ligadas pela fachada do dono, na mesma transação (D9): o risco sugerido do diligenciamento (modal e rota no pedido; risco Em análise com a avaliação inerente, sem duplicar; o vínculo é lido pela origem, sem coluna no pedido), o claim vinculado ao risco nos dois sentidos, a lição aplicada que gera o risco Identificado e grava `licao_aplicacao.risco_id`, a cobertura da contingência (KPI, alerta e a tabela "Ameaças ativas e cobertura" com as SMs que citam o risco, na tela e nas exportações) e a conferência dos links de origem da Central e das lições (já ligados desde 064/065). A migração `m067` fecha a FK `licao_aplicacao.risco_id` que o MODELO desenhava. A carga não mudou; o oráculo do diligenciamento passou a afirmar o bloco de pendências novo (o 0002 tem a ação, mas ainda não o risco).

- DECISAO: risco sugerido sem coluna no pedido | o vínculo é resolvido pela origem "Diligenciamento PED-..." (`riscos.diligence_risks`), como o MODELO desenha; o mesmo pedido não sugere duas vezes | D9, ISSUE-067
- DECISAO: pendências do diligenciamento | o crítico entra na pendência quando falta a ação ou o risco (o protótipo: `critico && (!acaoAberta || !risco)`), com o botão do que falta | ISSUE-067
- DECISAO: cobertura da contingência | exposição = soma do VME das ameaças ativas (`riscos.active_threats`); cobertura = saldo ÷ exposição, comparada à meta `coberturaMinimaPct` do grupo financeiro; as SMs vêm da análise de impacto da Governança (`change_codes_citing_risks`) | D9, ISSUE-067
- DECISAO: natureza do risco da lição | ameaça para "A evitar" e oportunidade para "A repetir", com a categoria da RBS escolhida no aplicar; entra Identificado, sem avaliação | D9, ISSUE-067
- DECISAO: categoria do risco sugerido | "Suprimentos > Fornecedores" da RBS, criada pela fachada da Riscos se o catálogo não a tiver (produção pode nascer sem RBS) | ISSUE-067
- DECISAO: leitura do risco pela origem | igualdade exata do número ("Diligenciamento PED-..."), não o `contains` do protótipo — o número do pedido é único | ISSUE-067
