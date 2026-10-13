<!-- Progresso da migração: 93 de 93 -->

# Progresso da migração

**93 de 93 issues concluídas** (última fechada: ISSUE-093). Atualizado em 13/10/2026 11:16 UTC por `scripts/execucao/gerar_progresso.py`; a situação oficial é a coluna Situação do `docs/issues/spec-migracao-gestnow/index.md`.

| Situação | Quantidade | Issues |
|---|---|---|
| concluída | 93 | 001, 002, 003, 004, 005, 006, 007, 008, 009, 010, 011, 012, 013, 014, 015, 016, 017, 018, 019, 020, 021, 022, 023, 024, 025, 026, 027, 028, 029, 030, 031, 032, 033, 034, 035, 036, 037, 038, 039, 040, 041, 042, 043, 044, 045, 046, 047, 048, 049, 050, 051, 052, 053, 054, 055, 056, 057, 058, 059, 060, 061, 062, 063, 064, 065, 066, 067, 068, 069, 070, 071, 072, 073, 074, 075, 076, 077, 078, 079, 080, 081, 082, 083, 084, 085, 086, 087, 088, 089, 090, 091, 092, 093 |

## Concluídas

| Issue | Título | Commit |
|---|---|---|
| ISSUE-001 | O repositório GestNow nasce do Padrão, renomeado, com as referências preservadas e o app subindo localmente | `8caa1d4` |
| ISSUE-002 | Estrutura modular de pastas com LEIA-ME por módulo, mapa "quero mudar X, abro Y", ONDE-ESTA, CONTEXT unificado e ADR da convenção | `588064f` |
| ISSUE-003 | Modelo de dados, parte 1: plataforma, cadastros, Central de Ações, Governança e Financeiro | `de0756d` |
| ISSUE-004 | Modelo de dados, parte 2: Planejamento, Programação Semanal, Suprimentos, Riscos, Qualidade, HSE, análises e relatório | `4a421ca` |
| ISSUE-005 | Postgres local preparado pelo run.bat, migrações Alembic e banco de teste isolado | `c3a40d1` |
| ISSUE-006 | Gravação segura: unidade de trabalho, trilha de auditoria, numeração por projeto e aviso de edição simultânea | `838b4be` |
| ISSUE-007 | Data de hoje, calendário de semanas e períodos, e parâmetros versionados | `f9205e0` |
| ISSUE-008 | Carga de demonstração deslocada para hoje, base de produção vazia com o primeiro Admin e harness do oráculo | `9d2e81a` |
| ISSUE-009 | Shell com barra lateral sempre visível, navegação de dois níveis, abas do módulo, escopo Portfólio ou projeto e dicas de siglas | `da3f862` |
| ISSUE-010 | Trio HTML, CSS e JS de todas as telas vinculado no shell e verificação trio-da-tela | `5edec9d` |
| ISSUE-011 | Login Microsoft com o cadastro de Colaboradores, perfis em dois eixos, recorte por vínculo e modo demonstração | `6aaa90d` |
| ISSUE-012 | Anexos de verdade: pasta local ou Blob, limites por parâmetro e download com a permissão do registro de origem | `155d35e` |
| ISSUE-013 | Porta de notificação: e-mail via Microsoft Graph escrito e desligado, envio simulado registrado na trilha | `3662b49` |
| ISSUE-014 | Biblioteca de gráficos 1: motor comum com drill e curvas, barras, Pareto e relógios | `263d5c0` |
| ISSUE-015 | Biblioteca de gráficos 2: cards, faixa de KPI, matrizes, heatmap, mapa de 52 semanas, quantitativos e etapas | `a7a3e3e` |
| ISSUE-016 | Biblioteca de gráficos 3: Gantt, calendário, galeria, cards de formulário, áreas, tabelas formatadas e os visuais novos | `c0e3a90` |
| ISSUE-017 | Exportação Excel e versão imprimível (PDF pelo navegador) genéricas | `128eb77` |
| ISSUE-018 | Importação de planilha em passos com conferência linha a linha | `f332a9a` |
| ISSUE-019 | Ações: costura única de criação, status calculado, lista, kanban, filtros, replanejamento com justificativa e link de origem | `b3da731` |
| ISSUE-020 | PDF das ações filtradas, follow-up aos responsáveis e painel da Central | `fd0378a` |
| ISSUE-021 | Atas: lista, nova ata numerada, dados da reunião e lista de presença com retirada bloqueada | `04bcdb5` |
| ISSUE-022 | Anotações e ações da ata por grupo, revisões da ata, histórico e justificativas | `88e4399` |
| ISSUE-023 | Solicitação de mudança: registro, nova SM numerada, ficha e cancelamento | `faf834f` |
| ISSUE-024 | Análise de impacto obrigatória com alçada mínima calculada | `8e833b8` |
| ISSUE-025 | Decisão com quórum, ações de implementação na Central, emergencial, reapresentação e encerramento | `40041b9` |
| ISSUE-026 | Painel de mudanças | `6673f89` |
| ISSUE-027 | Lições aprendidas: acervo, fluxo de validação segregado e aplicação em projeto | `59164b1` |
| ISSUE-028 | Painel de lições | `0495c74` |
| ISSUE-029 | EAC em árvore com itens, visão carteira e ponderação da carteira | `4aab1f8` |
| ISSUE-030 | Revisões da EAC, item novo e remanejamento como SM, aplicados só na aprovação, e importação de itens | `e9b403b` |
| ISSUE-031 | Mapa de controle com projeção, mapa de calor e custos do ERP | `67694d8` |
| ISSUE-032 | Ficha do contrato: cascata de valor, medições e aditivos | `ff4b373` |
| ISSUE-033 | Contrato: marcos de pagamento, claims e extensões de prazo | `b397107` |
| ISSUE-034 | Avaliação de desempenho da contratada | `8c4f17e` |
| ISSUE-035 | Contratos: visão consolidada e indicadores da administração contratual | `5db9f4e` |
| ISSUE-036 | EAP em árvore com dicionário, avanço calculado pelo critério e visão carteira | `fc281c3` |
| ISSUE-037 | Medição dos pacotes pelo critério, estorno controlado e importação do avanço | `0c63926` |
| ISSUE-038 | Revisões da EAP a partir de SM e desdobramento de pacotes de planejamento | `79c5c65` |
| ISSUE-039 | Curva S física com linha de base congelada, real das medições e drill | `e242c2f` |
| ISSUE-040 | KPIs de planejamento por período e por área | `9e08142` |
| ISSUE-041 | Contingência e reserva gerencial | `b6fdc2f` |
| ISSUE-042 | Curva S financeira e KPIs de custo | `22f1094` |
| ISSUE-043 | Cronograma de desembolso e envio à tesouraria | `38f8d2c` |
| ISSUE-044 | Relato do período | `881a524` |
| ISSUE-045 | 6WLA: atividades por semana, restrições e responsáveis | `8acbf03` |
| ISSUE-046 | Produtividade: plano de quantidades, ciclo da linha de base e apontamento semanal | `72e4e95` |
| ISSUE-047 | Produtividade: horas efetivas, amostragem do trabalho e paralisações | `047f3ec` |
| ISSUE-048 | Produtividade: KPIs de performance e plano de ação na Central | `01796c8` |
| ISSUE-049 | Punch list: itens, fluxo com verificação e bloqueio de sistema | `94864a6` |
| ISSUE-050 | Punch list: painel de completação | `5ec4bf0` |
| ISSUE-051 | Matriz da programação semanal portada: semana de segunda a domingo, janela e programação pelo fornecedor | `ba87520` |
| ISSUE-052 | Fluxo de cinco passos: validar com fiscal, realizado por turno, aprovação do fiscal e publicação | `6599c00` |
| ISSUE-053 | Pedidos de alteração e governança da programação | `d1b3416` |
| ISSUE-054 | Subpágina de configuração da programação, uma por projeto | `83ec550` |
| ISSUE-055 | Importação da semana, planilha e relatório de impressão | `995a5a7` |
| ISSUE-056 | Dashboard da programação | `509045c` |
| ISSUE-057 | Fornecedores com qualificação, documentos com validade e desempenho | `5ab2e28` |
| ISSUE-058 | Plano de compras | `640753e` |
| ISSUE-059 | Processo de compra: da requisição à negociação | `21ca4d0` |
| ISSUE-060 | Processo de compra: recomendação, aprovação por alçada e emissão de pedido ou contrato | `2bdbdde` |
| ISSUE-061 | Diligenciamento e recebimento | `706ecab` |
| ISSUE-062 | MAS: Mapa de Suprimentos | `f2a2830` |
| ISSUE-063 | Painel de suprimentos | `e7d1589` |
| ISSUE-064 | Registro e avaliação de riscos | `cfbe40d` |
| ISSUE-065 | Ficha do risco: plano de resposta, revisões, encerramento e reabertura | `39fdd05` |
| ISSUE-066 | Matriz P x I e painel de riscos | `4946f12` |
| ISSUE-067 | Integrações que chegam aos Riscos: risco sugerido do diligenciamento, claim, lição aplicada e cobertura da contingência | `df6c9e1` |
| ISSUE-068 | Não conformidades (RNC) | `2bd97f3` |
| ISSUE-069 | Inspeções e ITP, com o FAT do diligenciamento | `da1e9b3` |
| ISSUE-070 | Auditorias | `6921b06` |
| ISSUE-071 | Painel da qualidade | `5295da6` |
| ISSUE-072 | HHT, inspeções de segurança, observações e DDS | `adaa947` |
| ISSUE-073 | Ocorrências com investigação, prazos legais e dados restritos (LGPD) | `18b1173` |
| ISSUE-074 | Análises de risco APR e HAZOP | `45883f8` |
| ISSUE-075 | Painel HSE | `8e919ab` |
| ISSUE-076 | Parâmetros: edição por grupo com justificativa, versões e histórico | `e080668` |
| ISSUE-077 | Colaboradores: perfil geral, papéis na Programação Semanal por projeto, vínculo e empresa | `deb8176` |
| ISSUE-078 | Cadastros de apoio: empresas, pessoas, projetos, sistemas, unidades e locais | `fc47838` |
| ISSUE-079 | Início do projeto: indicador-chave por módulo e pontos de atenção | `93322f0` |
| ISSUE-080 | Início no Portfólio: carteira de projetos e edição da ponderação | `f5a4408` |
| ISSUE-081 | Análise do período de 02, 03 e 04, com desvios negativos e comentários obrigatórios | `4eff224` |
| ISSUE-082 | Análise do período de 05, 06, 07 e do Portfólio | `820bd44` |
| ISSUE-083 | Relatório gerencial: modal, motor de corte e folhas de Planejamento | `7fcfb8a` |
| ISSUE-084 | Relatório: folhas Financeiro (com a linha de tendência) e Suprimentos | `ca36c58` |
| ISSUE-085 | Relatório: folhas Riscos, Qualidade, HSE e Carteira de projetos | `5333790` |
| ISSUE-086 | Relatório: Excel, Imprimir / PDF e Alterar período | `f551689` |
| ISSUE-087 | Inglês, parte 1: catálogo no servidor, seletor PT / EN, shell, Início, Central, Governança e Financeiro | `d855a34` |
| ISSUE-088 | Inglês, parte 2: Planejamento, Programação Semanal, Suprimentos, Riscos, Qualidade, HSE, Configurações e relatório | `adc9d04` |
| ISSUE-089 | Oráculo de paridade completo e prova do cálculo vivo | `f30d067` |
| ISSUE-090 | Varredura de todas as telas nas três larguras | `37dbbd0` |
| ISSUE-091 | Exportações tela a tela, acessibilidade e roteiro manual | `5a32edd` |
| ISSUE-092 | Pronto para publicar no Azure | `7a4555a` |
| ISSUE-093 | Consolidação dentro do GestNow e desativação das pastas de origem | `a122717` |

Pendências de fonte: `docs/issues/spec-migracao-gestnow/PENDENCIAS-DE-FONTE.md`. Retrato por entrega: `docs/issues/spec-migracao-gestnow/RELATORIO-DE-EXECUCAO.md`.
