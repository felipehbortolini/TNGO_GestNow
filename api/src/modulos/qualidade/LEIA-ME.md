# Gestão da Qualidade

Módulo `qualidade`. Registra não conformidades (RNC), inspeções/ITP e auditorias, com controle
de tratamento e eficácia. A ISSUE-068 entrega a tela **Não conformidades (RNC)** ponta a ponta;
o Painel (ISSUE-071), as Inspeções/ITP (ISSUE-069) e as Auditorias (ISSUE-070) entram nas
issues seguintes e, nesta fatia, os trios delas continuam vazios.

## Telas

| Tela | Conteúdo | Situação |
|---|---|---|
| Não conformidades (RNC) | Filtros (busca, situação, severidade, disciplina e origem), cinco KPIs, lista com a próxima etapa e as ações, ficha em modal (contenção, causa raiz, disposição e concessão, verificação, ações da Central, evidências e histórico) e os formulários do fluxo | Entregue na ISSUE-068 |
| Painel da qualidade | RNC, inspeções, auditorias, Pareto, custo e pauta | Previsto para a ISSUE-071 |
| Inspeções e ITP | Planos com pontos H/W/R e registros por ponto | Previsto para a ISSUE-069 |
| Auditorias | Programa, resultado, constatações e reprogramação | Previsto para a ISSUE-070 |

## Trios das telas

Cada tela da lista de navegação (`api/src/core/navegacao.json`) tem um trio com o mesmo nome: a
view, o estilo e o comportamento da página. O CSS é escopado pela classe raiz da view
(`.pagina--<modulo>-<tela>`, com o `_` do identificador mantido), o JS registra
`TN.paginas["<modulo>/<tela>"]` e o shell (`app/index.html`) vincula o CSS e o JS de todos. A
verificação `trio-da-tela` confere o conjunto. Convenção completa em
`docs/PADROES-DE-PAGINA.md`, seção "O trio da tela".

| Tela | View | CSS | JS |
|---|---|---|---|
| Painel da qualidade | `app/_views/qualidade/painel.html` | `app/paginas/qualidade/painel.css` | `app/paginas/qualidade/painel.js` |
| Não conformidades (RNC) | `app/_views/qualidade/rnc.html` | `app/paginas/qualidade/rnc.css` | `app/paginas/qualidade/rnc.js` |
| Inspeções e ITP | `app/_views/qualidade/inspecoes.html` | `app/paginas/qualidade/inspecoes.css` | `app/paginas/qualidade/inspecoes.js` |
| Auditorias | `app/_views/qualidade/auditorias.html` | `app/paginas/qualidade/auditorias.css` | `app/paginas/qualidade/auditorias.js` |

O JS da RNC chama os fragmentos do servidor: a lista carrega no alvo `rnc-conteudo` e a ficha e
os formulários abrem no modal do Design System, no alvo `rnc-modal-corpo`. Depois de uma
gravação, o fragmento da lista traz um marcador oculto que reabre a ficha com o estado novo.

## Rotas

Prefixo: `/api/qualidade/`. Todas passam pelo `fragment_route` (gate do Alpine, usuário, escopo
e permissão) e desenham fragmentos; as exportações usam os mecanismos genéricos (D12).

| Rota | Método | Uso | Permissão |
|---|---|---|---|
| `rnc` | GET | A lista (`busca`, `situacao`, `severidade`, `disciplina`, `origem`, `empresa`, `pagina`) | Ver |
| `rnc/excel` e `rnc/imprimivel` | GET | Excel e PDF do mesmo filtro (KPIs + tabela) | Ver |
| `rnc/{codigo}/ficha` | GET | A ficha, com as ações da Central, as evidências e o histórico | Ver |
| `rnc/nova` | GET/POST | Abrir a RNC (no Portfólio pede o projeto antes) | Membro |
| `rnc/{codigo}/responsavel` | GET/POST | Atribuir a análise de causa | Membro |
| `rnc/{codigo}/analise` | GET/POST | Registrar causa raiz, disposição, concessão, custo e as ações (Central) | Membro |
| `rnc/{codigo}/acoes` | GET/POST | Nova ação corretiva na etapa Ação corretiva | Membro |
| `rnc/{codigo}/verificacao` | GET/POST | Enviar para verificação de eficácia | Membro |
| `rnc/{codigo}/eficacia` | GET/POST | Verificar a eficácia (encerra ou volta para Ação corretiva) | Gestor |
| `rnc/{codigo}/cancelamento` | GET/POST | Cancelar a RNC (só antes da ação corretiva) | Gestor |
| `rnc/{codigo}/custo` | GET/POST | Atualizar o custo da não qualidade | Membro |

## Fórmulas e nomes no código

| Termo de negócio | Definição | Nome no código |
|---|---|---|
| Prazo de tratamento | Data da constatação + `prazoTratamentoDias` da severidade (parâmetro) | `calculations.treatment_deadline` |
| RNC ativa | Situação fora de `Encerrada` e `Cancelada` | `calculations.is_active` |
| Prazo vencido | Em tratamento (Aberta a Ação corretiva) e prazo **anterior** à data de referência (a fronteira: o dia do prazo ainda não vence) | `calculations.is_overdue`, `days_overdue` |
| Verificação vencida | Em verificação de eficácia e prevista anterior à data de referência | `calculations.is_verification_overdue` |
| Dias aberta | Da data da constatação até o encerramento, ou até a data de referência | `calculations.days_open` |
| Próxima etapa | O degrau do fluxo que a situação aguarda | `calculations.next_step` |
| Reincidência | Quantas verificações **ineficazes** a RNC já teve: as transições da trilha de auditoria (`rnc`) que voltam de Verificação de eficácia para Ação corretiva; não há coluna (D5b) | `calculations.recurrence_count` |
| Tempo médio de tratamento | Média dos dias das RNC encerradas, arredondada para cima na metade (a regra do protótipo) | `calculations.average_treatment_days` |
| Custo da não qualidade | Soma dos custos das RNC do universo da lista (o KPI do protótipo soma todas) | `service._summary` |
| Aprovação em inspeções | Inspeções aprovadas ou com ressalva divididas pelo total | `calculations.inspection_approval_rate` (ISSUE-069) |
| Conformidade em auditorias | Itens conformes divididos pelos itens verificados | `calculations.audit_conformity_rate` (ISSUE-070) |

## Fluxos

RNC: **Aberta → Em análise de causa → Ação corretiva → Verificação de eficácia → Encerrada**;
**Cancelada** só antes da ação corretiva (Gestor, com motivo). A abertura exige a descrição (o
que, onde e o requisito) e a contenção imediata; o prazo de tratamento vem da severidade e vale
até a ação corretiva concluída. A análise (5 porquês, Ishikawa ou árvore de causas; causa raiz;
disposição) cria ao menos uma **ação corretiva na Central** (origem `RNC`), na mesma transação;
Reparo e Usar como está exigem a **concessão do cliente** (documento e data). Com as ações
concluídas, a RNC vai para a verificação, prevista para `verificacaoEficaciaDias` à frente. A
verificação é do **Gestor** e não pode ser feita por quem respondeu pela análise (segregação,
403); eficaz encerra e pode abrir a **lição em Rascunho** no 08 (origem `RNC <código>`, gravando
`rnc.licao_id`); ineficaz volta para Ação corretiva e conta reincidência. O custo da não
qualidade é atualizável com a composição enquanto a RNC está ativa.

Permissões (D7): ver a lista e a ficha, qualquer perfil; abrir e gravar, Membro; verificar a
eficácia e cancelar, Gestor; o vínculo Fornecedor não alcança o módulo (403).

## Integrações

* **Central de Ações (saída):** as ações corretivas nascem pela fachada da Central
  (`create_action`), na transação da análise ou da ação nova, com origem `RNC`, referência do
  número e item sequencial; a ficha lê as ações por `actions_of_origin`.
* **Central de Ações (entrada):** `origin_links.register("RNC", ...)` resolve o link de volta
  para `qualidade/rnc?busca=<código>`.
* **Governança (saída):** a lição do encerramento eficaz entra pela fachada
  (`lessons_service.create_draft_lesson`), em Rascunho, origem `RNC`, na mesma transação.
* **Governança (entrada):** o módulo registra `register_origin("RNC", ...)`, então o formulário
  de lição passa a oferecer a origem RNC e confere o número pela fachada da Qualidade.
* **Anexos (D5a):** `attachment_origins.register(table="rnc", ...)`; a ficha carrega o painel
  genérico de anexos (evidências da abertura, concessão e verificação) e o download checa a
  permissão do registro de origem.
* **Diligenciamento (entrada futura):** o FAT de Suprimentos grava a inspeção na ISSUE-069; a
  reprovação abrirá a RNC com origem `Inspeção de fabricação` (já aceita pelo CHECK e pelo
  formulário).
* **Auditorias (entrada futura):** a constatação Não conformidade abrirá a RNC com origem
  `Auditoria` na ISSUE-070.

## Parâmetros

Grupo `qualidade` em Configurações > Parâmetros, versionado: `prazoTratamentoDias`
`{critica: 15, maior: 30, menor: 45}` (crescentes de Crítica para Menor, entre 1 e 180 dias),
`verificacaoEficaciaDias` (30; entre 0 e 180), `metaAprovacaoInspecaoPct` (95) e
`metaConformidadeAuditoriaPct` (90) — entre 0 e 100% — e `notificacaoClienteHoras` (48; entre 0 e
240). As metas e a antecedência valem para as telas das ISSUE-069/070/071.

## Onde mexer

| Alteração | Arquivo ou pasta |
|---|---|
| Rotas e fragmentos da RNC | `routes.py` e `api/src/templates/qualidade/` |
| Transições, permissões e integrações | `service.py` |
| Fórmulas da RNC | `calculations.py` |
| Validações e mensagens do formulário | `validation.py` |
| Exportação (Excel e PDF) | `export.py` |
| Persistência | `models.py`; entidade `rnc` em `docs/MODELO-DE-DADOS.md` |
| Carga de demonstração | `seed.py` (parte `qualidade-rnc`) |
| Tela, estilo e comportamento | `app/_views/qualidade/` e `app/paginas/qualidade/` |
| Testes | `api/tests/qualidade/` e `api/tests/oraculo/test_oraculo_qualidade.py` |
