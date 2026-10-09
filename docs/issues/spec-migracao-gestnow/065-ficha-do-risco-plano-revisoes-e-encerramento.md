---
id: ISSUE-065
title: "Ficha do risco: plano de resposta, revisões, encerramento e reabertura"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 6
onda: 13
blocked_by:
  - ISSUE-064
  - ISSUE-019
  - ISSUE-023
  - ISSUE-027
blocks:
  - ISSUE-066
labels:
  - ready-for-agent
source_requirements:
  - HU-108
  - HU-109
  - HU-110
  - HU-113
spec_decisions:
  - D7
  - D9
---

# Ficha do risco: plano de resposta, revisões, encerramento e reabertura

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D7, D9.
> Entrega 6 (Suprimentos e Riscos), onda 13 (05 Riscos).
> Histórias: 108, 109, 110, 113. Bloqueada por: ISSUE-064, ISSUE-019, ISSUE-023, ISSUE-027.

## O que construir

A **ficha do risco** mostra a faixa com inerente e residual e a situação, os
alertas (sem avaliação, plano aguardando aprovação, gatilho, revisão vencida,
pauta, encerrado ou excluído), os botões com o próximo passo em destaque e as
abas Identificação, Avaliação (somente leitura, dimensões, VME inerente e
atual), Resposta e ações, Monitoramento (linha do tempo das revisões e
cadência) e Histórico.

**Plano de resposta**: residual só depois do plano; alvo não maior que a
inerente (ameaça); prazo futuro; ação obrigatória para inerente Alto ou
Crítico, exceto Aceitar (justificativa de 30 caracteres); Evitar exige 80
caracteres e SM (existente ou nova); Transferir exige instrumento. Inerente na
faixa mais alta exige aprovação do Gestor, e **o responsável pelo plano não
aprova**. **Ação de mitigação** pela costura da Central (origem Risco; Salvar e
nova).

**Revisão periódica** com cadência pela severidade atual (parâmetro): o gestor
antecipa, nunca posterga. Toda avaliação e revisão grava a linha do tempo com
antes e depois; gatilho ocorrido força reavaliação e entra na pauta.

**Encerramento** (Gestor): bloqueado com ação aberta, salvo Materializado;
lição aprendida sempre obrigatória (lição em Rascunho pela fachada de Lições).
Materializado gera ação na Central (grupo Problema, origem Risco) e, se exigir
alterar escopo, prazo ou custo, SM Registrada no 08, tudo na mesma transação;
para oportunidade, o motivo é "Capturada", sem problema nem SM. **Reabertura**
pelo Gestor com justificativa.

## Critérios de aceite

- [ ] O responsável pelo plano não consegue aprovar (403).
- [ ] Cada regra do plano de resposta tem teste com a recusa e a mensagem.
- [ ] A cadência nunca é postergada, e o gatilho força reavaliação.
- [ ] Encerrar sem lição é recusado; materializado cria ação e SM na mesma transação.
- [ ] Reabertura exige Gestor e justificativa.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (plano, aprovação, revisões, encerramento e reabertura) e de rota (403).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `ficha.html`, modais 12 a 16 em `js/pages/riscos/riscos.js`, `GI.api.riscos.plano`, `aprovarPlano`, `novaAcao`, `revisar`, `encerrar` e `reabrir`; README, regras e o ajuste ao mockup 15.

## Registro de execução

Fatia entregue em 09/10/2026: a fachada da ficha (`ficha_service`: a folha com a faixa, os alertas, a pauta e as abas; a linha do tempo e o histórico reconstruído da trilha; as escritas do plano, da aprovação, da revisão, do encerramento, da reabertura e da ação), as rotas e os fragmentos (`ficha_routes`, `riscos/ficha.html` e os modais), o trio da tela, o Excel e o PDF pelos mecanismos genéricos, a migração `m065` (as quatro FKs que o MODELO já desenhava), a parte da carga (ata de origem, SM do Evitar, lição e SM do encerramento materializado pelos ids das fachadas donas) e os testes (fachada e rotas, incluindo os 403 da segregação). As integrações que chegam de fora ficam na ISSUE-067.

- DECISAO: fachada e rotas separadas | a ficha vive em `ficha_service.py` e `ficha_routes.py`, no padrão de `minutes_routes`/`lessons_routes`; a fatia da 064 fica intacta exceto os ganchos de destino dos modais | ISSUE-065
- DECISAO: editar e avaliar na ficha | a edição e a avaliação abertas da ficha respondem à própria ficha (`ficha/editar` e `ficha/avaliar`), com o destino no estado | ISSUE-065
- DECISAO: origem da SM do materializado | a SM nasce com origem Interna (o "Risco materializado" não existe no vocabulário do 08); a rastreabilidade fica em `risco.encerramento_mudanca_id` | D9, ISSUE-065
- DECISAO: histórico e encerramentos anteriores | reconstruídos da trilha de auditoria (`risco`, `risco_avaliacao`, `risco_revisao`, `risco_plano_aprovacao` e `risco.historico`), sem texto gravado em coluna | D5b, ISSUE-065
- DECISAO: notificação da revisão | a revisão vencida avisa dono e gestor pela porta de notificação (tipo `revisao_risco`); sem e-mail cadastrado a ficha avisa que nada saiu, sem bloquear | ISSUE-013, ISSUE-065
- DECISAO: situação "Não exigida" | quando o plano deixa de exigir a gerência, a aprovação ganha a linha "Não exigida" em vez de sumir da linha do tempo | ISSUE-065
