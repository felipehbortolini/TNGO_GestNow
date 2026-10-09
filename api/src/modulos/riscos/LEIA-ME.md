# Gestão de Riscos

Módulo `riscos`. Mantém ameaças e oportunidades, avaliações, respostas, revisões e encerramentos.
Score e severidade são calculados no servidor a partir da escala vigente (ISSUE-064, D6); o plano
de resposta, as revisões, o encerramento e a reabertura vivem na ficha (ISSUE-065).

## Telas

| Tela | Conteúdo | Issue | Situação |
|---|---|---|---|
| Registro de riscos | Contexto, KPIs, alternador Inerente/Residual, filtros, tabela, avaliação e exclusão lógica | ISSUE-064 | pronta |
| Matriz P x I | Contagem e navegação por probabilidade e impacto | ISSUE-066 | prevista |
| Ficha do risco | Alertas, faixa com inerente e residual, plano de resposta, revisões, encerramento, reabertura e histórico | ISSUE-065 | pronta |
| Painel de riscos | Exposição, tendência residual e pauta de escalonamento | ISSUE-066 | prevista |

As integrações que chegam de Suprimentos, Contratos e Financeiro são ligadas na ISSUE-067.

## Trios das telas

Cada tela da lista de navegação (`api/src/core/navegacao.json`) tem um trio com o mesmo nome: a
view, o estilo e o comportamento da página. O CSS é escopado pela classe raiz da view
(`.pagina--<modulo>-<tela>`, com o `_` do identificador mantido), o JS registra
`TN.paginas["<modulo>/<tela>"]` e o shell (`app/index.html`) vincula o CSS e o JS de todos. A
verificação `trio-da-tela` confere o conjunto. Convenção completa em `docs/PADROES-DE-PAGINA.md`,
seção "O trio da tela".

| Tela | View | CSS | JS |
|---|---|---|---|
| Registro de riscos | `app/_views/riscos/registro.html` | `app/paginas/riscos/registro.css` | `app/paginas/riscos/registro.js` |
| Matriz de riscos 5x5 | `app/_views/riscos/matriz.html` | `app/paginas/riscos/matriz.css` | `app/paginas/riscos/matriz.js` |
| Ficha do risco | `app/_views/riscos/ficha.html` | `app/paginas/riscos/ficha.css` | `app/paginas/riscos/ficha.js` |
| Painel de riscos | `app/_views/riscos/painel.html` | `app/paginas/riscos/painel.css` | `app/paginas/riscos/painel.js` |

A ficha é **tela de detalhe** (`detalhe_de: riscos/registro`): não tem aba na barra lateral e o
Voltar leva ao Registro. Ela abre por `?codigo=RSK-...`, o mesmo parâmetro que o registro usa em
`_record_link`; o conteúdo é o fragmento `ficha-conteudo`, carregado pela view e atualizado por
cada gravação dos modais. O `registro.js` só abre os modais do registro e cuida dos cinco estados.

## Rotas

Prefixo: `/api/riscos/`. No registro, a tela inteira é um fragmento só, `registro-conteudo`.
Na ficha, a tela é `ficha-conteudo` e cada modal é um formulário do servidor (`ficha-modal-corpo`).

| Rota | Uso |
|---|---|
| `GET registro` | A tela do registro: contexto, KPIs, aviso, chips, barra e tabela |
| `GET registro/excel` e `registro/imprimivel` | As duas exportações do filtro aplicado |
| `GET/POST novo` | Novo risco; no Portfólio o projeto é pedido antes |
| `GET/POST {codigo}/editar` | Edição da identificação |
| `GET/POST {codigo}/avaliar` e `GET previa` | Avaliação e a prévia do score |
| `GET/POST {codigo}/excluir` | Exclusão lógica (Gestor) |
| `POST {codigo}/restaurar` | Restauração (Admin) |
| `GET categorias/nova` e `POST categorias` | Cadastro rápido da RBS |
| `GET ficha` | A ficha: alertas, faixa, botões e as cinco abas |
| `GET ficha/excel` e `ficha/imprimivel` | As duas exportações da ficha (ISSUE-065) |
| `GET/POST {codigo}/ficha/editar` e `{codigo}/ficha/avaliar` | Identificação e avaliação, respondidas na ficha |
| `GET/POST {codigo}/plano` | Plano de resposta |
| `GET/POST {codigo}/plano/aprovacao` | Aprovação da gerência (Gestor; o responsável pelo plano não aprova) |
| `GET/POST {codigo}/acoes` | Ação de mitigação, pela costura da Central (origem Risco) |
| `GET/POST {codigo}/revisoes` | Revisão periódica |
| `GET/POST {codigo}/encerramento` | Encerramento (Gestor) |
| `GET/POST {codigo}/reabertura` | Reabertura (Gestor) |

Os formulários abrem em modal; uma recusa (403, 409, 422) volta no próprio modal com a mensagem ao
lado do campo, e o sucesso atualiza a ficha atrás dele. O fragmento do registro traz um `<template>`
com os filtros completos e, depois de "Salvar e avaliar", um marcador oculto que reabre a avaliação;
o da ficha usa o mesmo marcador para reabrir a avaliação, o encerramento de um risco materializado
ou a próxima ação de "Salvar e nova".

## Fórmulas e nomes no código

| Termo de negócio | Definição | Nome no código |
|---|---|---|
| Score | Probabilidade multiplicada pelo impacto (1 a 25) | `calculations.risk_score` |
| Severidade | Faixa da escala vigente para o score; risco à vida é sempre a mais alta na CIPM | `calculations.risk_severity` |
| Impacto resultante | Maior das seis dimensões (pior caso); pode ser elevado, nunca reduzido | `calculations.resulting_impact` |
| VME | Probabilidade média da faixa multiplicada pelo impacto em custo, em centavos | `calculations.expected_monetary_value` |
| Exposição | Soma do VME só das ameaças | `calculations.threat_exposure` |
| Cadência de revisão | Dias entre revisões da faixa; a maior quando a faixa não tem valor | `calculations.review_cadence` |
| Limite da próxima revisão | Data da revisão mais a cadência da faixa; antecipar é permitido, postergar não | `calculations.next_review_limit` |
| Situação apurada | Reduzido, agravado, sem mudança ou avaliação inicial, pelo score antes e depois | `calculations.assessed_situation` |
| Sem redução | Ameaça cujo residual não caiu abaixo do inerente | `calculations.has_no_reduction` |
| Ação obrigatória | Ameaça inerente Alto ou mais pesada exige ação, exceto na estratégia Aceitar | `calculations.requires_response_action` |
| Aprovação obrigatória | Plano de inerente na faixa mais alta (ou marcado) aguarda a gerência | `calculations.is_top_band` |
| Pauta de escalonamento | Motivos calculados do risco (sem avaliação, topo sem plano, alvo a menos de 30 dias, sem redução, aprovação pendente, revisão vencida, gatilho) | `calculations.pauta_reasons` |
| Alvo acima da inerente | Proibido para ameaça | `calculations.is_target_above` |
| Numeração | Próximo sufixo numérico do projeto: ``RSK-0001``; sufixos não numéricos não movem a série | `calculations.next_code_number` e `service.reserve_code` |
| Histórico da ficha | Linhas da trilha de auditoria (`risco`, `risco_avaliacao`, `risco_revisao`, `risco_plano_aprovacao`, `risco.historico`), com o antes e o depois lidos por coluna | `ficha_service._history_of` |

## Fluxos

Identificado → Em análise → Em tratamento → Monitorado → Materializado ou Encerrado. A avaliação
residual só habilita depois do plano de resposta; para ameaças o residual não supera o inerente e
um score novo exige justificativa. Exclusão lógica é do Gestor, bloqueada com ação aberta e para
risco encerrado, e só o Admin vê e restaura.

**Plano de resposta** (`ficha_service.save_plan`): o residual só habilita depois do plano; para
ameaça o alvo não supera a inerente; o prazo é futuro; Evitar exige 80 caracteres e SM (existente
ou "nova", que gera ação na Central); Transferir exige instrumento; Aceitar exige 30 caracteres;
ameaça inerente Alto ou Crítico exige ao menos uma ação, exceto Aceitar. Inerente na faixa mais
alta (ou o campo marcado) cria a aprovação **Pendente** e o risco vai a Em análise; a aprovação é
do Gestor e o **responsável pelo plano não pode aprová-la** (D7, 403). Devolvida, a ficha avisa e o
plano pode ser reenviado. Salvar plano em risco encerrado é 422.

**Revisão periódica** (`ficha_service.review_risk`): a data não pode ser futura nem anterior à
última revisão; a próxima revisão não passa da cadência da faixa do novo score (antecipa, nunca
posterga); a situação apurada precisa bater com a variação do score; o comentário é obrigatório
(10 a 1000 caracteres). A revisão grava a nova avaliação vigente (inerente ou residual) e a linha
da linha do tempo, ambas fatos; o gatilho ocorrido força a reavaliação e entra na pauta. O
"notificar" passa pela porta de notificação (`notification.RISK_REVIEW`), sem e-mail cadastrado a
ficha avisa que nada foi enviado.

**Encerramento** (`ficha_service.close_risk`, Gestor): bloqueado com ação aberta, salvo
Materializado; Duplicado exige o risco original do mesmo projeto; a lição aprendida é sempre
obrigatória (20 a 1000 caracteres) e nasce em **Rascunho** pela fachada de Lições, com origem
`Risco`; Materializado de ameaça cria a ação do problema na Central (grupo `Problema`) e, se
marcado, a **SM Registrada** no 08 — tudo na mesma transação (D9). Para oportunidade materializada
o motivo aparece como "Capturada" e não há problema nem SM. O risco vai a Materializado ou
Encerrado e a próxima revisão é limpa.

**Reabertura** (`ficha_service.reopen_risk`, Gestor): exige justificativa (10 a 500 caracteres);
a situação volta à que a trilha guardou antes do encerramento (com o fallback do protótipo) e os
campos de encerramento são limpos, inclusive o vínculo com a lição e a SM; a lição permanece no
acervo. A justificativa entra no histórico pela entidade `risco.historico`.

**Ação de mitigação** (`ficha_service.create_risk_action`): registro da Central de Ações com
origem `Risco`, item sequencial dentro do risco, grupo `Plano de resposta`; o risco Monitorado com
estratégia volta a Em tratamento. "Salvar e nova" reabre o formulário.

## Integrações (D9)

- **Central de Ações** (`central_acoes.service`): a ação nasce por `create_action` (a costura
  única); a ficha lê as ações por `actions_of_origin` e conta por `count_actions_of_origin`. A
  origem `Risco` aponta de volta para `riscos/ficha?codigo=...` (`origin_links`).
- **Governança** (`governanca.service`): as SMs do projeto para o plano vêm de `change_options`;
  o encerramento materializado cria a SM por `create_change` (situação Registrada) e o vínculo
  fica em `risco.encerramento_mudanca_id`; a estratégia Evitar guarda a SM em `risco.mudanca_id`.
- **Lições** (`lessons_service`): o encerramento sempre abre a lição em Rascunho por
  `create_draft_lesson`, com origem `Risco` e o número do risco; a ficha lê a lição por
  `lesson_options`. O módulo registra `register_origin("Risco", ...)` para a fachada de Lições
  conferir o número.
- **Notificação** (`core.notification`): a revisão com "notificar" envia pela porta (tipo
  `revisao_risco`) ao dono e ao gestor do projeto; sem o envio real, fica simulada na trilha.
- **Configurações**: projetos, pessoas, RBS e o grupo Riscos dos parâmetros; a ficha usa
  `pautaDiasAntesDoPrazo` (30) na pauta e `revisaoAlertaDias` no registro.

Recebe sugestões do diligenciamento, claims, lições aplicadas e dados de exposição na ISSUE-067;
somente a fachada dona grava em cada módulo.

## Parâmetros

Escala ativa (Timenow de 4 faixas ou CIPM de 3), probabilidades médias por faixa, cadência de
revisão por faixa, impactos, os dias do alerta de revisão e os dias antes do prazo da pauta, no
grupo Riscos dos parâmetros em `Configurações > Parâmetros` (ISSUE-076).

## Carga de demonstração

A parte `riscos` (ISSUE-064) carrega os 19 riscos do protótipo com avaliações, revisões e
aprovação; a ISSUE-065 liga a ata de origem, a SM do Evitar, a lição e a SM do encerramento
materializado pelos ids que as fachadas de Central de Ações e Governança devolveram. As ações com
origem `Risco` entram pela parte `central_acoes`. Datas deslocadas da âncora (25/09/2026) para a
data do run, idempotente pela tabela `carga_demonstracao`.

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas e templates do registro | `routes.py`; `api/src/templates/riscos/` |
| Rotas da ficha (plano, aprovação, ação, revisão, encerramento, reabertura) | `ficha_routes.py` |
| Fluxo do registro, exclusão e numeração | `service.py` |
| Ficha: plano, revisões, encerramento, reabertura e histórico | `ficha_service.py` |
| Score, severidade, VME, cadência, pauta e transições | `calculations.py` |
| Validação de identificação, avaliação, plano, revisão, encerramento e reabertura | `validation.py` |
| Exportação (Excel e imprimível do registro e da ficha) | `export.py` |
| Persistência | `models.py`; entidades em `docs/MODELO-DE-DADOS.md` |
| Carga de demonstração | `seed.py` |
| Tela, estilo e comportamento | `app/_views/riscos/` e `app/paginas/riscos/` |
| Testes | `api/tests/riscos/` e `api/tests/oraculo/test_oraculo_riscos.py` |

A ISSUE-066 completa matriz e painel; a ISSUE-067 liga as integrações de chegada.
