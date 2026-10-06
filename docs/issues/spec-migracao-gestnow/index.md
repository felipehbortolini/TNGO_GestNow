---
source_prd: docs/SPEC-MIGRACAO-GESTNOW.md
issue_count: 93
status: proposed
---

# Issues: migração do Gestão Integrada AMT para o Timenow GestNow

Fonte da verdade: [`docs/SPEC-MIGRACAO-GESTNOW.md`](../../SPEC-MIGRACAO-GESTNOW.md)
(revisão 2.1, 157 histórias, decisões D1 a D16 e o Histórico de decisões Q1 a
Q35). Se uma issue e a spec discordarem, **a spec vence** e a issue é que está
velha.

Este diretório contém **93 issues**. Cada uma é uma fatia vertical:
entrega um comportamento completo (banco, serviço, rota, tela, exportação e
testes) e verificável por conta própria, em vez de uma camada técnica isolada.
O que é preparação (cópia do Padrão, estrutura, modelo de dados e plataforma)
vem primeiro.

* Agrupamento em entregas e o produto final: [`ENTREGAS.md`](./ENTREGAS.md).
* Prompt único para executar tudo, do começo ao fim, sem paradas:
  [`PROMPT-EXECUCAO.md`](./PROMPT-EXECUCAO.md).

---

## Registro de issues

| ID | Título | Entrega | Tipo | Situação | Rótulo | Bloqueada por | Arquivo |
|---|---|---|---|---|---|---|---|
| ISSUE-001 | O repositório GestNow nasce do Padrão, renomeado, com as referências preservadas e o app subindo localmente | 1 | task | done | ready-for-agent | Nenhuma | [ISSUE-001](./001-repositorio-gestnow-a-partir-do-padrao.md) |
| ISSUE-002 | Estrutura modular de pastas com LEIA-ME por módulo, mapa "quero mudar X, abro Y", ONDE-ESTA, CONTEXT unificado e ADR da convenção | 1 | task | done | ready-for-agent | ISSUE-001 | [ISSUE-002](./002-estrutura-modular-e-documentacao-de-manutencao.md) |
| ISSUE-003 | Modelo de dados, parte 1: plataforma, cadastros, Central de Ações, Governança e Financeiro | 1 | task | done | ready-for-agent | ISSUE-002 | [ISSUE-003](./003-modelo-de-dados-parte-1.md) |
| ISSUE-004 | Modelo de dados, parte 2: Planejamento, Programação Semanal, Suprimentos, Riscos, Qualidade, HSE, análises e relatório | 1 | task | done | ready-for-agent | ISSUE-003 | [ISSUE-004](./004-modelo-de-dados-parte-2.md) |
| ISSUE-005 | Postgres local preparado pelo run.bat, migrações Alembic e banco de teste isolado | 2 | task | done | ready-for-agent | ISSUE-004 | [ISSUE-005](./005-postgres-local-migracoes-e-banco-de-teste.md) |
| ISSUE-006 | Gravação segura: unidade de trabalho, trilha de auditoria, numeração por projeto e aviso de edição simultânea | 2 | task | done | ready-for-agent | ISSUE-005 | [ISSUE-006](./006-gravacao-segura.md) |
| ISSUE-007 | Data de hoje, calendário de semanas e períodos, e parâmetros versionados | 2 | task | done | ready-for-agent | ISSUE-005 | [ISSUE-007](./007-data-de-hoje-calendario-e-parametros.md) |
| ISSUE-008 | Carga de demonstração deslocada para hoje, base de produção vazia com o primeiro Admin e harness do oráculo | 2 | task | done | ready-for-agent | ISSUE-006, ISSUE-007 | [ISSUE-008](./008-carga-de-demonstracao-e-producao-vazia.md) |
| ISSUE-009 | Shell com barra lateral sempre visível, navegação de dois níveis, abas do módulo, escopo Portfólio ou projeto e dicas de siglas | 2 | task | done | ready-for-agent | ISSUE-008 | [ISSUE-009](./009-shell-sidebar-navegacao-e-escopo.md) |
| ISSUE-010 | Trio HTML, CSS e JS de todas as telas vinculado no shell e verificação trio-da-tela | 2 | task | done | ready-for-agent | ISSUE-009 | [ISSUE-010](./010-trio-de-todas-as-telas.md) |
| ISSUE-011 | Login Microsoft com o cadastro de Colaboradores, perfis em dois eixos, recorte por vínculo e modo demonstração | 2 | task | done | ready-for-agent | ISSUE-010 | [ISSUE-011](./011-login-perfis-e-vinculo.md) |
| ISSUE-012 | Anexos de verdade: pasta local ou Blob, limites por parâmetro e download com a permissão do registro de origem | 2 | task | done | ready-for-agent | ISSUE-011, ISSUE-007 | [ISSUE-012](./012-anexos-de-verdade.md) |
| ISSUE-013 | Porta de notificação: e-mail via Microsoft Graph escrito e desligado, envio simulado registrado na trilha | 2 | task | done | ready-for-agent | ISSUE-006 | [ISSUE-013](./013-porta-de-notificacao.md) |
| ISSUE-014 | Biblioteca de gráficos 1: motor comum com drill e curvas, barras, Pareto e relógios | 2 | task | done | ready-for-agent | ISSUE-010 | [ISSUE-014](./014-graficos-1-motor-e-curvas.md) |
| ISSUE-015 | Biblioteca de gráficos 2: cards, faixa de KPI, matrizes, heatmap, mapa de 52 semanas, quantitativos e etapas | 2 | task | done | ready-for-agent | ISSUE-014 | [ISSUE-015](./015-graficos-2-cards-matrizes-e-tabelas.md) |
| ISSUE-016 | Biblioteca de gráficos 3: Gantt, calendário, galeria, cards de formulário, áreas, tabelas formatadas e os visuais novos | 2 | task | done | ready-for-agent | ISSUE-015 | [ISSUE-016](./016-graficos-3-cronogramas-galerias-e-novos-visuais.md) |
| ISSUE-017 | Exportação Excel e versão imprimível (PDF pelo navegador) genéricas | 2 | task | done | ready-for-agent | ISSUE-011, ISSUE-014 | [ISSUE-017](./017-exportacao-excel-e-versao-imprimivel.md) |
| ISSUE-018 | Importação de planilha em passos com conferência linha a linha | 2 | task | done | ready-for-agent | ISSUE-017 | [ISSUE-018](./018-importacao-de-planilha-em-passos.md) |
| ISSUE-019 | Ações: costura única de criação, status calculado, lista, kanban, filtros, replanejamento com justificativa e link de origem | 3 | task | done | ready-for-agent | ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018 | [ISSUE-019](./019-acoes-costura-status-e-lista.md) |
| ISSUE-020 | PDF das ações filtradas, follow-up aos responsáveis e painel da Central | 3 | task | proposed | ready-for-agent | ISSUE-019 | [ISSUE-020](./020-pdf-das-acoes-follow-up-e-painel.md) |
| ISSUE-021 | Atas: lista, nova ata numerada, dados da reunião e lista de presença com retirada bloqueada | 3 | task | in-progress | ready-for-agent | ISSUE-019 | [ISSUE-021](./021-atas-lista-nova-ata-e-presenca.md) |
| ISSUE-022 | Anotações e ações da ata por grupo, revisões da ata, histórico e justificativas | 3 | task | proposed | ready-for-agent | ISSUE-021 | [ISSUE-022](./022-anotacoes-acoes-e-revisoes-da-ata.md) |
| ISSUE-023 | Solicitação de mudança: registro, nova SM numerada, ficha e cancelamento | 3 | task | done | ready-for-agent | ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018 | [ISSUE-023](./023-solicitacao-de-mudanca-registro-e-ficha.md) |
| ISSUE-024 | Análise de impacto obrigatória com alçada mínima calculada | 3 | task | in-progress | ready-for-agent | ISSUE-023 | [ISSUE-024](./024-analise-de-impacto-e-alcada.md) |
| ISSUE-025 | Decisão com quórum, ações de implementação na Central, emergencial, reapresentação e encerramento | 3 | task | proposed | ready-for-agent | ISSUE-024, ISSUE-019 | [ISSUE-025](./025-decisao-implementacao-e-encerramento-da-sm.md) |
| ISSUE-026 | Painel de mudanças | 3 | task | proposed | ready-for-agent | ISSUE-025 | [ISSUE-026](./026-painel-de-mudancas.md) |
| ISSUE-027 | Lições aprendidas: acervo, fluxo de validação segregado e aplicação em projeto | 3 | task | proposed | ready-for-agent | ISSUE-019, ISSUE-023 | [ISSUE-027](./027-licoes-acervo-fluxo-e-aplicacao.md) |
| ISSUE-028 | Painel de lições | 3 | task | proposed | ready-for-agent | ISSUE-027 | [ISSUE-028](./028-painel-de-licoes.md) |
| ISSUE-029 | EAC em árvore com itens, visão carteira e ponderação da carteira | 4 | task | done | ready-for-agent | ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018 | [ISSUE-029](./029-eac-arvore-visao-carteira-e-ponderacao.md) |
| ISSUE-030 | Revisões da EAC, item novo e remanejamento como SM, aplicados só na aprovação, e importação de itens | 4 | task | proposed | ready-for-agent | ISSUE-029, ISSUE-025 | [ISSUE-030](./030-revisoes-da-eac-e-remanejamento-por-sm.md) |
| ISSUE-031 | Mapa de controle com projeção, mapa de calor e custos do ERP | 4 | task | proposed | ready-for-agent | ISSUE-030 | [ISSUE-031](./031-mapa-de-controle-projecao-e-erp.md) |
| ISSUE-032 | Ficha do contrato: cascata de valor, medições e aditivos | 4 | task | proposed | ready-for-agent | ISSUE-031 | [ISSUE-032](./032-ficha-do-contrato-medicoes-e-aditivos.md) |
| ISSUE-033 | Contrato: marcos de pagamento, claims e extensões de prazo | 4 | task | proposed | ready-for-agent | ISSUE-032, ISSUE-023 | [ISSUE-033](./033-marcos-de-pagamento-claims-e-eot.md) |
| ISSUE-034 | Avaliação de desempenho da contratada | 4 | task | proposed | ready-for-agent | ISSUE-032, ISSUE-027 | [ISSUE-034](./034-avaliacao-de-desempenho-da-contratada.md) |
| ISSUE-035 | Contratos: visão consolidada e indicadores da administração contratual | 4 | task | proposed | ready-for-agent | ISSUE-033, ISSUE-034 | [ISSUE-035](./035-contratos-consolidado-e-indicadores.md) |
| ISSUE-036 | EAP em árvore com dicionário, avanço calculado pelo critério e visão carteira | 4 | task | proposed | ready-for-agent | ISSUE-029 | [ISSUE-036](./036-eap-arvore-dicionario-e-carteira.md) |
| ISSUE-037 | Medição dos pacotes pelo critério, estorno controlado e importação do avanço | 4 | task | proposed | ready-for-agent | ISSUE-036 | [ISSUE-037](./037-medicao-estorno-e-importacao-do-avanco.md) |
| ISSUE-038 | Revisões da EAP a partir de SM e desdobramento de pacotes de planejamento | 4 | task | proposed | ready-for-agent | ISSUE-037, ISSUE-025 | [ISSUE-038](./038-revisoes-da-eap-e-desdobramento.md) |
| ISSUE-039 | Curva S física com linha de base congelada, real das medições e drill | 4 | task | proposed | ready-for-agent | ISSUE-038 | [ISSUE-039](./039-curva-s-fisica.md) |
| ISSUE-040 | KPIs de planejamento por período e por área | 4 | task | proposed | ready-for-agent | ISSUE-039 | [ISSUE-040](./040-kpis-de-planejamento.md) |
| ISSUE-041 | Contingência e reserva gerencial | 4 | task | proposed | ready-for-agent | ISSUE-039, ISSUE-031, ISSUE-025 | [ISSUE-041](./041-contingencia-e-reserva-gerencial.md) |
| ISSUE-042 | Curva S financeira e KPIs de custo | 4 | task | proposed | ready-for-agent | ISSUE-041 | [ISSUE-042](./042-curva-s-financeira-e-kpis-de-custo.md) |
| ISSUE-043 | Cronograma de desembolso e envio à tesouraria | 4 | task | proposed | ready-for-agent | ISSUE-031, ISSUE-033 | [ISSUE-043](./043-cronograma-de-desembolso.md) |
| ISSUE-044 | Relato do período | 5 | task | done | ready-for-agent | ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018 | [ISSUE-044](./044-relato-do-periodo.md) |
| ISSUE-045 | 6WLA: atividades por semana, restrições e responsáveis | 5 | task | done | ready-for-agent | ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018 | [ISSUE-045](./045-6wla.md) |
| ISSUE-046 | Produtividade: plano de quantidades, ciclo da linha de base e apontamento semanal | 5 | task | proposed | ready-for-agent | ISSUE-025 | [ISSUE-046](./046-produtividade-quantidades-lb-e-apontamento.md) |
| ISSUE-047 | Produtividade: horas efetivas, amostragem do trabalho e paralisações | 5 | task | proposed | ready-for-agent | ISSUE-046 | [ISSUE-047](./047-produtividade-horas-efetivas-amostragem-e-paralisacoes.md) |
| ISSUE-048 | Produtividade: KPIs de performance e plano de ação na Central | 5 | task | proposed | ready-for-agent | ISSUE-046, ISSUE-047, ISSUE-019 | [ISSUE-048](./048-produtividade-kpis-e-plano-de-acao.md) |
| ISSUE-049 | Punch list: itens, fluxo com verificação e bloqueio de sistema | 5 | task | proposed | ready-for-agent | ISSUE-019 | [ISSUE-049](./049-punch-list-itens-verificacao-e-bloqueio.md) |
| ISSUE-050 | Punch list: painel de completação | 5 | task | proposed | ready-for-agent | ISSUE-049 | [ISSUE-050](./050-punch-list-painel.md) |
| ISSUE-051 | Matriz da programação semanal portada: semana de segunda a domingo, janela e programação pelo fornecedor | 5 | task | in-progress | ready-for-agent | ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018 | [ISSUE-051](./051-programacao-semanal-matriz-e-programacao.md) |
| ISSUE-052 | Fluxo de cinco passos: validar com fiscal, realizado por turno, aprovação do fiscal e publicação | 5 | task | proposed | ready-for-agent | ISSUE-051 | [ISSUE-052](./052-programacao-semanal-fluxo-de-cinco-passos.md) |
| ISSUE-053 | Pedidos de alteração e governança da programação | 5 | task | proposed | ready-for-agent | ISSUE-052 | [ISSUE-053](./053-programacao-semanal-pedidos-de-alteracao-e-governanca.md) |
| ISSUE-054 | Subpágina de configuração da programação, uma por projeto | 5 | task | proposed | ready-for-agent | ISSUE-051 | [ISSUE-054](./054-programacao-semanal-configuracao-por-projeto.md) |
| ISSUE-055 | Importação da semana, planilha e relatório de impressão | 5 | task | proposed | ready-for-agent | ISSUE-052 | [ISSUE-055](./055-programacao-semanal-importacao-planilha-e-impressao.md) |
| ISSUE-056 | Dashboard da programação | 5 | task | proposed | ready-for-agent | ISSUE-052 | [ISSUE-056](./056-programacao-semanal-dashboard.md) |
| ISSUE-057 | Fornecedores com qualificação, documentos com validade e desempenho | 6 | task | proposed | ready-for-agent | ISSUE-034 | [ISSUE-057](./057-fornecedores-qualificacao-e-desempenho.md) |
| ISSUE-058 | Plano de compras | 6 | task | proposed | ready-for-agent | ISSUE-031, ISSUE-057 | [ISSUE-058](./058-plano-de-compras.md) |
| ISSUE-059 | Processo de compra: da requisição à negociação | 6 | task | proposed | ready-for-agent | ISSUE-058 | [ISSUE-059](./059-processo-de-compra-da-requisicao-a-negociacao.md) |
| ISSUE-060 | Processo de compra: recomendação, aprovação por alçada e emissão de pedido ou contrato | 6 | task | proposed | ready-for-agent | ISSUE-059, ISSUE-032 | [ISSUE-060](./060-processo-de-compra-alcada-e-emissao.md) |
| ISSUE-061 | Diligenciamento e recebimento | 6 | task | proposed | ready-for-agent | ISSUE-060 | [ISSUE-061](./061-diligenciamento-e-recebimento.md) |
| ISSUE-062 | MAS: Mapa de Suprimentos | 6 | task | proposed | ready-for-agent | ISSUE-061 | [ISSUE-062](./062-mas-mapa-de-suprimentos.md) |
| ISSUE-063 | Painel de suprimentos | 6 | task | proposed | ready-for-agent | ISSUE-062 | [ISSUE-063](./063-painel-de-suprimentos.md) |
| ISSUE-064 | Registro e avaliação de riscos | 6 | task | proposed | ready-for-agent | ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018 | [ISSUE-064](./064-riscos-registro-e-avaliacao.md) |
| ISSUE-065 | Ficha do risco: plano de resposta, revisões, encerramento e reabertura | 6 | task | proposed | ready-for-agent | ISSUE-064, ISSUE-019, ISSUE-023, ISSUE-027 | [ISSUE-065](./065-ficha-do-risco-plano-revisoes-e-encerramento.md) |
| ISSUE-066 | Matriz P x I e painel de riscos | 6 | task | proposed | ready-for-agent | ISSUE-065 | [ISSUE-066](./066-matriz-pxi-e-painel-de-riscos.md) |
| ISSUE-067 | Integrações que chegam aos Riscos: risco sugerido do diligenciamento, claim, lição aplicada e cobertura da contingência | 6 | task | proposed | ready-for-agent | ISSUE-066, ISSUE-061, ISSUE-033, ISSUE-027, ISSUE-041 | [ISSUE-067](./067-integracoes-que-chegam-aos-riscos.md) |
| ISSUE-068 | Não conformidades (RNC) | 7 | task | proposed | ready-for-agent | ISSUE-019, ISSUE-027 | [ISSUE-068](./068-nao-conformidades-rnc.md) |
| ISSUE-069 | Inspeções e ITP, com o FAT do diligenciamento | 7 | task | proposed | ready-for-agent | ISSUE-068, ISSUE-061 | [ISSUE-069](./069-inspecoes-itp-e-fat.md) |
| ISSUE-070 | Auditorias | 7 | task | proposed | ready-for-agent | ISSUE-068 | [ISSUE-070](./070-auditorias.md) |
| ISSUE-071 | Painel da qualidade | 7 | task | proposed | ready-for-agent | ISSUE-069, ISSUE-070 | [ISSUE-071](./071-painel-da-qualidade.md) |
| ISSUE-072 | HHT, inspeções de segurança, observações e DDS | 7 | task | proposed | ready-for-agent | ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018 | [ISSUE-072](./072-hht-inspecoes-observacoes-e-dds.md) |
| ISSUE-073 | Ocorrências com investigação, prazos legais e dados restritos (LGPD) | 7 | task | proposed | ready-for-agent | ISSUE-072, ISSUE-019, ISSUE-027 | [ISSUE-073](./073-ocorrencias-investigacao-e-lgpd.md) |
| ISSUE-074 | Análises de risco APR e HAZOP | 7 | task | proposed | ready-for-agent | ISSUE-019 | [ISSUE-074](./074-apr-e-hazop.md) |
| ISSUE-075 | Painel HSE | 7 | task | proposed | ready-for-agent | ISSUE-072, ISSUE-073, ISSUE-074, ISSUE-034 | [ISSUE-075](./075-painel-hse.md) |
| ISSUE-076 | Parâmetros: edição por grupo com justificativa, versões e histórico | 7 | task | proposed | ready-for-agent | ISSUE-066 | [ISSUE-076](./076-configuracoes-parametros.md) |
| ISSUE-077 | Colaboradores: perfil geral, papéis na Programação Semanal por projeto, vínculo e empresa | 7 | task | proposed | ready-for-agent | ISSUE-054 | [ISSUE-077](./077-configuracoes-colaboradores.md) |
| ISSUE-078 | Cadastros de apoio: empresas, pessoas, projetos, sistemas, unidades e locais | 7 | task | proposed | ready-for-agent | ISSUE-054 | [ISSUE-078](./078-configuracoes-cadastros-de-apoio.md) |
| ISSUE-079 | Início do projeto: indicador-chave por módulo e pontos de atenção | 8 | task | proposed | ready-for-agent | ISSUE-020, ISSUE-026, ISSUE-035, ISSUE-040, ISSUE-042, ISSUE-050, ISSUE-063, ISSUE-066, ISSUE-071, ISSUE-075 | [ISSUE-079](./079-inicio-do-projeto.md) |
| ISSUE-080 | Início no Portfólio: carteira de projetos e edição da ponderação | 8 | task | proposed | ready-for-agent | ISSUE-079 | [ISSUE-080](./080-inicio-no-portfolio-e-ponderacao.md) |
| ISSUE-081 | Análise do período de 02, 03 e 04, com desvios negativos e comentários obrigatórios | 8 | task | proposed | ready-for-agent | ISSUE-040, ISSUE-042, ISSUE-044, ISSUE-048, ISSUE-063 | [ISSUE-081](./081-analise-do-periodo-02-03-04.md) |
| ISSUE-082 | Análise do período de 05, 06, 07 e do Portfólio | 8 | task | proposed | ready-for-agent | ISSUE-081, ISSUE-066, ISSUE-071, ISSUE-075 | [ISSUE-082](./082-analise-do-periodo-05-06-07-e-portfolio.md) |
| ISSUE-083 | Relatório gerencial: modal, motor de corte e folhas de Planejamento | 8 | task | proposed | ready-for-agent | ISSUE-082, ISSUE-044 | [ISSUE-083](./083-relatorio-gerencial-modal-corte-e-planejamento.md) |
| ISSUE-084 | Relatório: folhas Financeiro (com a linha de tendência) e Suprimentos | 8 | task | proposed | ready-for-agent | ISSUE-083 | [ISSUE-084](./084-relatorio-financeiro-e-suprimentos.md) |
| ISSUE-085 | Relatório: folhas Riscos, Qualidade, HSE e Carteira de projetos | 8 | task | proposed | ready-for-agent | ISSUE-084, ISSUE-080 | [ISSUE-085](./085-relatorio-riscos-qualidade-hse-e-carteira.md) |
| ISSUE-086 | Relatório: Excel, Imprimir / PDF e Alterar período | 8 | task | proposed | ready-for-agent | ISSUE-085 | [ISSUE-086](./086-relatorio-excel-impressao-e-alterar-periodo.md) |
| ISSUE-087 | Inglês, parte 1: catálogo no servidor, seletor PT / EN, shell, Início, Central, Governança e Financeiro | 9 | task | proposed | ready-for-agent | ISSUE-086, ISSUE-078 | [ISSUE-087](./087-ingles-parte-1.md) |
| ISSUE-088 | Inglês, parte 2: Planejamento, Programação Semanal, Suprimentos, Riscos, Qualidade, HSE, Configurações e relatório | 9 | task | proposed | ready-for-agent | ISSUE-087 | [ISSUE-088](./088-ingles-parte-2.md) |
| ISSUE-089 | Oráculo de paridade completo e prova do cálculo vivo | 9 | task | proposed | ready-for-agent | ISSUE-088 | [ISSUE-089](./089-oraculo-de-paridade-e-calculo-vivo.md) |
| ISSUE-090 | Varredura de todas as telas nas três larguras | 9 | task | proposed | ready-for-agent | ISSUE-089 | [ISSUE-090](./090-varredura-de-todas-as-telas.md) |
| ISSUE-091 | Exportações tela a tela, acessibilidade e roteiro manual | 9 | task | proposed | ready-for-agent | ISSUE-090 | [ISSUE-091](./091-exportacoes-acessibilidade-e-roteiro-manual.md) |
| ISSUE-092 | Pronto para publicar no Azure | 9 | task | proposed | ready-for-agent | ISSUE-091 | [ISSUE-092](./092-pronto-para-publicar-no-azure.md) |
| ISSUE-093 | Consolidação dentro do GestNow e desativação das pastas de origem | 9 | task | proposed | ready-for-agent | ISSUE-092 | [ISSUE-093](./093-consolidacao-e-desativacao-das-pastas-de-origem.md) |

---

## Ordem de execução: uma fila só, do começo ao fim

A numeração **é** a ordem de execução, e é uma ordenação válida do grafo de
dependências: toda issue depende só de issues com número menor. Executar de
ISSUE-001 a ISSUE-093 em sequência nunca encontra uma issue travada
por outra que ainda não foi feita.

**Regra de continuidade:** só se avança para a issue seguinte quando todos os
critérios de aceite da atual estão marcados e a porta de qualidade passa. Se
uma issue não fecha depois das tentativas de correção previstas no prompt, ela
fica `blocked` com o motivo escrito no próprio arquivo, e a fila continua com
as issues que não dependem dela (as que dependem também ficam `blocked`, com o
nome da causa). Nada fica "quase pronto" enquanto a seguinte começa.

Integrações entre módulos: cada uma é ligada na issue do módulo que chega por
**último**; a issue do módulo que chega primeiro deixa o ponto anotado e diz
em qual issue ele é ligado. Por isso nenhuma issue espera por uma posterior.

Situações usadas: `proposed`, `ready`, `in-progress`, `blocked`, `done`,
`cancelled`.

---

## Definição de pronto (vale para toda issue)

Em cima dos critérios de aceite de cada uma:

1. A porta de qualidade passa (`npm run verificar`), sem regra desligada. Falso
   positivo estrutural se resolve na configuração, com comentário.
2. Fragmento não traz `<link>` nem `<script>`; toda tela tem o seu trio
   (verificação `trio-da-tela`).
3. Python em inglês; interface, CSS, JS, rotas, pastas de módulo, tabelas e
   colunas em português (D1 e D5).
4. Toda fórmula nova tem nome e teste com o caso de fronteira, e recebe a data
   de referência como argumento.
5. Toda gravação passa pela fachada do módulo dono, numa transação, com a
   trilha e o controle de versão.
6. O `LEIA-ME.md` do módulo e, se o modelo mudou, o `docs/MODELO-DE-DADOS.md`
   são atualizados na mesma issue.
7. Decisão que contraria a spec é anotada **na spec antes** de ser codificada,
   no Histórico de decisões, como "decisão da execução, pendente de revisão do
   dono".
8. Commit local ao fechar a issue (decisão Q33), com a mensagem
   `ISSUE-NNN: título`.

---

## Decisões que valem para a execução

| # | Decisão | Onde |
|---|---|---|
| Q30 | O modelo de dados (ISSUE-003 e 004) fica "aceito para execução"; a revisão do dono acontece no fim, e mudança vira issue nova. | ISSUE-003, 004, 091 |
| Q31 | Erro de fórmula do protótipo: reproduzir o número do protótipo e registrar a divergência como pendente em `docs/DIVERGENCIAS-DO-PROTOTIPO.md`. Diferença causada por decisão já tomada na spec segue a spec e também é registrada. | ISSUE-039, 089 |
| Q32 | A exclusão das pastas de origem é a única pergunta da execução, num pop-up no último passo. | ISSUE-093 |
| Q33 | Git local dentro do GestNow, um commit por issue fechada, sem remoto. | ISSUE-001 e todas |
| Q34 | Nas skills repetidas (grill-me e grilling), fica a versão da raiz. | ISSUE-093 |
| Q35 | Nome e dados médicos das ocorrências de HSE: Membro preenche; só Gestor e Admin leem (inclusive os anexos). | ISSUE-004, 073 |

---

## Cobertura das histórias da spec

Todas as 157 histórias estão cobertas.

| História | Issues |
|---|---|
| HU-001 | ISSUE-011 |
| HU-002 | ISSUE-011 |
| HU-003 | ISSUE-011 |
| HU-004 | ISSUE-011 |
| HU-005 | ISSUE-009, ISSUE-090 |
| HU-006 | ISSUE-009, ISSUE-090 |
| HU-007 | ISSUE-009, ISSUE-011 |
| HU-008 | ISSUE-011 |
| HU-009 | ISSUE-011 |
| HU-010 | ISSUE-009 |
| HU-011 | ISSUE-009 |
| HU-012 | ISSUE-009 |
| HU-013 | ISSUE-009 |
| HU-014 | ISSUE-009 |
| HU-015 | ISSUE-009 |
| HU-016 | ISSUE-017 |
| HU-017 | ISSUE-087, ISSUE-088 |
| HU-018 | ISSUE-009 |
| HU-019 | ISSUE-011 |
| HU-020 | ISSUE-010, ISSUE-090 |
| HU-021 | ISSUE-007 |
| HU-022 | ISSUE-007, ISSUE-089 |
| HU-023 | ISSUE-089 |
| HU-024 | ISSUE-039 |
| HU-025 | ISSUE-039 |
| HU-026 | ISSUE-066 |
| HU-027 | ISSUE-008 |
| HU-028 | ISSUE-006 |
| HU-029 | ISSUE-006 |
| HU-030 | ISSUE-006 |
| HU-031 | ISSUE-006 |
| HU-032 | ISSUE-015, ISSUE-079 |
| HU-033 | ISSUE-079 |
| HU-034 | ISSUE-080 |
| HU-035 | ISSUE-029, ISSUE-080 |
| HU-036 | ISSUE-083 |
| HU-037 | ISSUE-083 |
| HU-038 | ISSUE-083, ISSUE-085 |
| HU-039 | ISSUE-086 |
| HU-040 | ISSUE-083 |
| HU-041 | ISSUE-084 |
| HU-042 | ISSUE-081, ISSUE-082 |
| HU-043 | ISSUE-081 |
| HU-044 | ISSUE-081, ISSUE-082 |
| HU-045 | ISSUE-081 |
| HU-046 | ISSUE-044 |
| HU-047 | ISSUE-019 |
| HU-048 | ISSUE-019 |
| HU-049 | ISSUE-020 |
| HU-050 | ISSUE-020 |
| HU-051 | ISSUE-021 |
| HU-052 | ISSUE-022 |
| HU-053 | ISSUE-019 |
| HU-054 | ISSUE-021 |
| HU-055 | ISSUE-019 |
| HU-056 | ISSUE-036 |
| HU-057 | ISSUE-037 |
| HU-058 | ISSUE-037 |
| HU-059 | ISSUE-037 |
| HU-060 | ISSUE-038 |
| HU-061 | ISSUE-038 |
| HU-062 | ISSUE-014, ISSUE-039 |
| HU-063 | ISSUE-040 |
| HU-064 | ISSUE-016, ISSUE-045 |
| HU-065 | ISSUE-046 |
| HU-066 | ISSUE-047 |
| HU-067 | ISSUE-048 |
| HU-068 | ISSUE-049 |
| HU-069 | ISSUE-049 |
| HU-070 | ISSUE-050 |
| HU-071 | ISSUE-051 |
| HU-072 | ISSUE-051 |
| HU-073 | ISSUE-052 |
| HU-074 | ISSUE-052 |
| HU-075 | ISSUE-052 |
| HU-076 | ISSUE-052 |
| HU-077 | ISSUE-052 |
| HU-078 | ISSUE-053 |
| HU-079 | ISSUE-054 |
| HU-080 | ISSUE-054, ISSUE-078 |
| HU-081 | ISSUE-054 |
| HU-082 | ISSUE-055 |
| HU-083 | ISSUE-055 |
| HU-084 | ISSUE-014, ISSUE-056 |
| HU-085 | ISSUE-053 |
| HU-086 | ISSUE-051 |
| HU-087 | ISSUE-029, ISSUE-030 |
| HU-088 | ISSUE-030 |
| HU-089 | ISSUE-015, ISSUE-031 |
| HU-090 | ISSUE-031 |
| HU-091 | ISSUE-043 |
| HU-092 | ISSUE-042 |
| HU-093 | ISSUE-014, ISSUE-042 |
| HU-094 | ISSUE-041 |
| HU-095 | ISSUE-016, ISSUE-032, ISSUE-033 |
| HU-096 | ISSUE-033 |
| HU-097 | ISSUE-034 |
| HU-098 | ISSUE-035 |
| HU-099 | ISSUE-058 |
| HU-100 | ISSUE-059, ISSUE-060 |
| HU-101 | ISSUE-060 |
| HU-102 | ISSUE-015, ISSUE-062 |
| HU-103 | ISSUE-061, ISSUE-067 |
| HU-104 | ISSUE-069 |
| HU-105 | ISSUE-057 |
| HU-106 | ISSUE-063 |
| HU-107 | ISSUE-064 |
| HU-108 | ISSUE-065 |
| HU-109 | ISSUE-065 |
| HU-110 | ISSUE-065 |
| HU-111 | ISSUE-015, ISSUE-066 |
| HU-112 | ISSUE-066 |
| HU-113 | ISSUE-065 |
| HU-114 | ISSUE-068 |
| HU-115 | ISSUE-068 |
| HU-116 | ISSUE-068 |
| HU-117 | ISSUE-069 |
| HU-118 | ISSUE-070 |
| HU-119 | ISSUE-071 |
| HU-120 | ISSUE-073 |
| HU-121 | ISSUE-072 |
| HU-122 | ISSUE-016, ISSUE-075 |
| HU-123 | ISSUE-074 |
| HU-124 | ISSUE-073 |
| HU-125 | ISSUE-023 |
| HU-126 | ISSUE-024 |
| HU-127 | ISSUE-025 |
| HU-128 | ISSUE-025, ISSUE-030, ISSUE-038, ISSUE-067 |
| HU-129 | ISSUE-027 |
| HU-130 | ISSUE-026, ISSUE-028 |
| HU-131 | ISSUE-007, ISSUE-076 |
| HU-132 | ISSUE-076 |
| HU-133 | ISSUE-077 |
| HU-134 | ISSUE-076 |
| HU-135 | ISSUE-078 |
| HU-136 | ISSUE-017, ISSUE-091 |
| HU-137 | ISSUE-017, ISSUE-091 |
| HU-138 | ISSUE-017, ISSUE-091 |
| HU-139 | ISSUE-018 |
| HU-140 | ISSUE-012 |
| HU-141 | ISSUE-012 |
| HU-142 | ISSUE-012 |
| HU-143 | ISSUE-012 |
| HU-144 | ISSUE-013, ISSUE-020 |
| HU-145 | ISSUE-013, ISSUE-092 |
| HU-146 | ISSUE-002 |
| HU-147 | ISSUE-002 |
| HU-148 | ISSUE-010 |
| HU-149 | ISSUE-010 |
| HU-150 | ISSUE-007 |
| HU-151 | ISSUE-001, ISSUE-005, ISSUE-008 |
| HU-152 | ISSUE-003, ISSUE-004 |
| HU-153 | ISSUE-002 |
| HU-154 | ISSUE-003, ISSUE-004, ISSUE-005 |
| HU-155 | ISSUE-092 |
| HU-156 | ISSUE-089 |
| HU-157 | ISSUE-001, ISSUE-093 |
