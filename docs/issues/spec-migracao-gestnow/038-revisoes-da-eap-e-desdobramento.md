---
id: ISSUE-038
title: "Revisões da EAP a partir de SM e desdobramento de pacotes de planejamento"
status: done
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

- [x] O maior resto fecha 100% em toda revisão (teste de fronteira).
- [x] Peso acima do máximo é recusado.
- [x] Revisão sem SM aprovada com impacto em escopo é recusada.
- [x] O desdobramento mantém o total do projeto e encerra o pacote de planejamento zerado.
- [x] O encerramento da SM exige a revisão da EAP e registra "EAP Rev N".
- [x] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo (maior resto) e de fachada (revisão, desdobramento, importação e ligação com a SM).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `GI.api.planejamento.eapNovaRevisao`, `eapNovoPacote` e `eapEditarPacote`; README, "EAP: regras".

## Registro de execução

- Data: 2026-10-07.
- Feito: as etapas 1 a 3 (commits `3dbd701`, `62d3401`, `7cb0926`) entregaram o maior resto (`calculations.eap_rescale_weights`) e o previsto linear (`calculations.eap_linear_predicted`), a validação do pacote e da revisão, a fachada (`service.create_revision` e `service.breakdown_package`, com a SM marcada na mesma transação), a ligação com a Governança (fonte, incorporação, próximo passo e gate do encerramento), o importador `eap-pacotes`, as rotas e os fragmentos. Nesta etapa de fechamento, a tela `planejamento/eap` ganhou **Novo pacote** (marcador `data-pode-editar`), **Nova revisão** e **Importar pacotes** (marcador novo `data-pode-gerir`, de `EapOverview.can_manage`) no cabeçalho, abertos no modal do Design System; o formulário do pacote e o da revisão guardam o alvo `eap-formulario` fora da página e o devolvem ao fechar, o 422 por campo, o 403 sem Gestor e o 409 de versão voltam no próprio formulário, e a importação segue formulário → conferir → confirmar com o alvo `eap-pacotes-importacao-resultado`; a árvore, as revisões e os desdobramentos atualizam pelo `eap-conteudo` da resposta. Na Governança, a ficha mostra o alerta e a linha "Nova revisão da EAP (02)" (com o link `eap_url`), o modal de encerramento lista a pendência da EAP (e a da EAC) na conferência das linhas de base com o aviso de bloqueio, e as novas rotas da ficha e do encerramento passaram a ter teste.
- Divergências do protótipo: o pacote de planejamento encerrado fica com peso 0 em vez de ser removido — a FK do desdobramento precisa do registro para os desdobramentos da revisão vigente continuarem legíveis; o código da planilha é preservado na importação (o formulário do pacote novo é que gera o próximo código); a contagem de pacotes da revisão inclui os pacotes encerrados; o formulário não simula ao vivo o efeito nos pesos e no real — a resposta da gravação devolve a árvore e o 422 marca o campo. Os filtros do protótipo (busca, nível, critério e situação) continuam fora, como na ISSUE-036.
- Ajustes mínimos em arquivos das fatias anteriores: `_eap_conteudo.html` e `routes.py` ganharam `pode_gerir`; `_eap_pacote_campos.html` e `_eap_revisao_campos.html` fecham o modal pelo botão do cabeçalho; `eap.css` esconde as ações do cabeçalho com `hidden` (o `display` do `.btn` sobrepunha o atributo — defeito que também afetava o botão Importar avanço da ISSUE-037).
- Exportações: as tabelas desta fatia (revisões e desdobramentos) já saem pelo Excel e pelo PDF genéricos desde a ISSUE-036; nada novo a exportar.
- Porta de qualidade (`node scripts/verificar.mjs`, cinco etapas) verde e a suíte completa de pytest (2.447 testes, 0 falhas, 0 erros) passou em 07/10/2026.
