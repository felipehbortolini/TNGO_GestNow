# Entregas e produto final

Fonte: [`docs/SPEC-MIGRACAO-GESTNOW.md`](../../SPEC-MIGRACAO-GESTNOW.md).
Registro das issues: [`index.md`](./index.md). Execução contínua:
[`PROMPT-EXECUCAO.md`](./PROMPT-EXECUCAO.md).

A migração está organizada em três níveis:

1. **Atividade** (issue): uma fatia vertical, completa e verificável sozinha,
   do tamanho de uma sessão de trabalho.
2. **Onda** e **entrega**: a onda agrupa issues do mesmo módulo ou tema; a
   entrega agrupa ondas num resultado que se pode mostrar a alguém. A entrega
   é um ponto de conferência, não uma parada: a execução segue direto para a
   próxima.
3. **Produto final**: o Timenow GestNow completo, sozinho na pasta, pronto para
   publicar.

A ordem é uma fila só: entrega 1 a 9, onda 1 a 20, ISSUE-001 a
ISSUE-093. Toda issue depende só de issues anteriores, então a
fila nunca trava esperando algo que vem depois.

```
Entrega 1  Fundação documentada ............ 001 a 004
   |
Entrega 2  Plataforma no ar ................ 005 a 018
   |
Entrega 3  Central de Ações e Governança ... 019 a 028
   |
Entrega 4  Custo e avanço físico ........... 029 a 043   (usa SM da 3)
   |
Entrega 5  Campo e Programação Semanal ..... 044 a 056   (usa Central e SM da 3)
   |
Entrega 6  Suprimentos e Riscos ............ 057 a 067   (usa EAC e contratos da 4)
   |
Entrega 7  Qualidade, HSE e Configurações .. 068 a 078   (usa 3, 5 e 6)
   |
Entrega 8  Visão executiva ................. 079 a 086   (lê todos os módulos)
   |
Entrega 9  Produto final ................... 087 a 093
```

---

## Entregas

### Entrega 1. Fundação documentada (ISSUE-001 a ISSUE-004, 4 issues)

**Valor entregue:** O repositório existe, copiado do Padrão; cada módulo tem a sua pasta e o seu LEIA-ME; o modelo de dados inteiro está desenhado.

**Pronto quando:** Qualquer pessoa abre o `MAPA-DE-MODULOS.md` e acha onde mexer, e o diagrama cobre 100% das coleções do protótipo e do app de Programação Semanal.

**Como ver:** Rodar o `run.bat` (abre o shell vazio) e ler `docs/MODELO-DE-DADOS.md`.

#### Onda 1. Repositório, estrutura e modelo de dados

| Issue | Título | Bloqueada por |
|---|---|---|
| [ISSUE-001](./001-repositorio-gestnow-a-partir-do-padrao.md) | O repositório GestNow nasce do Padrão, renomeado, com as referências preservadas e o app subindo localmente | Nenhuma |
| [ISSUE-002](./002-estrutura-modular-e-documentacao-de-manutencao.md) | Estrutura modular de pastas com LEIA-ME por módulo, mapa "quero mudar X, abro Y", ONDE-ESTA, CONTEXT unificado e ADR da convenção | ISSUE-001 |
| [ISSUE-003](./003-modelo-de-dados-parte-1.md) | Modelo de dados, parte 1: plataforma, cadastros, Central de Ações, Governança e Financeiro | ISSUE-002 |
| [ISSUE-004](./004-modelo-de-dados-parte-2.md) | Modelo de dados, parte 2: Planejamento, Programação Semanal, Suprimentos, Riscos, Qualidade, HSE, análises e relatório | ISSUE-003 |

---

### Entrega 2. Plataforma no ar (ISSUE-005 a ISSUE-018, 14 issues)

**Valor entregue:** O app sobe com Postgres, demonstração deslocada para hoje, barra lateral sempre visível, todas as telas com o seu trio, login com perfis, anexos, notificação, gráficos, Excel, PDF e importação.

**Pronto quando:** Toda tela da navegação abre com estilo próprio e estado vazio, nas três larguras, com o perfil certo; as checagens de trio, estrutura e migração passam.

**Como ver:** Trocar o perfil no seletor da barra lateral e navegar pelos 12 módulos; abrir o styleguide de gráficos.

#### Onda 2. Dados

| Issue | Título | Bloqueada por |
|---|---|---|
| [ISSUE-005](./005-postgres-local-migracoes-e-banco-de-teste.md) | Postgres local preparado pelo run.bat, migrações Alembic e banco de teste isolado | ISSUE-004 |
| [ISSUE-006](./006-gravacao-segura.md) | Gravação segura: unidade de trabalho, trilha de auditoria, numeração por projeto e aviso de edição simultânea | ISSUE-005 |
| [ISSUE-007](./007-data-de-hoje-calendario-e-parametros.md) | Data de hoje, calendário de semanas e períodos, e parâmetros versionados | ISSUE-005 |
| [ISSUE-008](./008-carga-de-demonstracao-e-producao-vazia.md) | Carga de demonstração deslocada para hoje, base de produção vazia com o primeiro Admin e harness do oráculo | ISSUE-006, ISSUE-007 |

#### Onda 3. Shell, telas e acesso

| Issue | Título | Bloqueada por |
|---|---|---|
| [ISSUE-009](./009-shell-sidebar-navegacao-e-escopo.md) | Shell com barra lateral sempre visível, navegação de dois níveis, abas do módulo, escopo Portfólio ou projeto e dicas de siglas | ISSUE-008 |
| [ISSUE-010](./010-trio-de-todas-as-telas.md) | Trio HTML, CSS e JS de todas as telas vinculado no shell e verificação trio-da-tela | ISSUE-009 |
| [ISSUE-011](./011-login-perfis-e-vinculo.md) | Login Microsoft com o cadastro de Colaboradores, perfis em dois eixos, recorte por vínculo e modo demonstração | ISSUE-010 |

#### Onda 4. Serviços transversais

| Issue | Título | Bloqueada por |
|---|---|---|
| [ISSUE-012](./012-anexos-de-verdade.md) | Anexos de verdade: pasta local ou Blob, limites por parâmetro e download com a permissão do registro de origem | ISSUE-011, ISSUE-007 |
| [ISSUE-013](./013-porta-de-notificacao.md) | Porta de notificação: e-mail via Microsoft Graph escrito e desligado, envio simulado registrado na trilha | ISSUE-006 |
| [ISSUE-014](./014-graficos-1-motor-e-curvas.md) | Biblioteca de gráficos 1: motor comum com drill e curvas, barras, Pareto e relógios | ISSUE-010 |
| [ISSUE-015](./015-graficos-2-cards-matrizes-e-tabelas.md) | Biblioteca de gráficos 2: cards, faixa de KPI, matrizes, heatmap, mapa de 52 semanas, quantitativos e etapas | ISSUE-014 |
| [ISSUE-016](./016-graficos-3-cronogramas-galerias-e-novos-visuais.md) | Biblioteca de gráficos 3: Gantt, calendário, galeria, cards de formulário, áreas, tabelas formatadas e os visuais novos | ISSUE-015 |
| [ISSUE-017](./017-exportacao-excel-e-versao-imprimivel.md) | Exportação Excel e versão imprimível (PDF pelo navegador) genéricas | ISSUE-011, ISSUE-014 |
| [ISSUE-018](./018-importacao-de-planilha-em-passos.md) | Importação de planilha em passos com conferência linha a linha | ISSUE-017 |

---

### Entrega 3. Central de Ações e Governança (ISSUE-019 a ISSUE-028, 10 issues)

**Valor entregue:** A costura única de ações funciona, com atas, e a gestão de mudanças e de lições roda de ponta a ponta.

**Pronto quando:** Uma SM vai de registrada a encerrada criando as ações na Central, e uma lição passa pela validação segregada.

**Como ver:** Aprovar uma SM e ver as ações de implementação aparecerem na Central.

#### Onda 5. 01 Central de Ações

| Issue | Título | Bloqueada por |
|---|---|---|
| [ISSUE-019](./019-acoes-costura-status-e-lista.md) | Ações: costura única de criação, status calculado, lista, kanban, filtros, replanejamento com justificativa e link de origem | ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018 |
| [ISSUE-020](./020-pdf-das-acoes-follow-up-e-painel.md) | PDF das ações filtradas, follow-up aos responsáveis e painel da Central | ISSUE-019 |
| [ISSUE-021](./021-atas-lista-nova-ata-e-presenca.md) | Atas: lista, nova ata numerada, dados da reunião e lista de presença com retirada bloqueada | ISSUE-019 |
| [ISSUE-022](./022-anotacoes-acoes-e-revisoes-da-ata.md) | Anotações e ações da ata por grupo, revisões da ata, histórico e justificativas | ISSUE-021 |

#### Onda 6. 08 Governança

| Issue | Título | Bloqueada por |
|---|---|---|
| [ISSUE-023](./023-solicitacao-de-mudanca-registro-e-ficha.md) | Solicitação de mudança: registro, nova SM numerada, ficha e cancelamento | ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018 |
| [ISSUE-024](./024-analise-de-impacto-e-alcada.md) | Análise de impacto obrigatória com alçada mínima calculada | ISSUE-023 |
| [ISSUE-025](./025-decisao-implementacao-e-encerramento-da-sm.md) | Decisão com quórum, ações de implementação na Central, emergencial, reapresentação e encerramento | ISSUE-024, ISSUE-019 |
| [ISSUE-026](./026-painel-de-mudancas.md) | Painel de mudanças | ISSUE-025 |
| [ISSUE-027](./027-licoes-acervo-fluxo-e-aplicacao.md) | Lições aprendidas: acervo, fluxo de validação segregado e aplicação em projeto | ISSUE-019, ISSUE-023 |
| [ISSUE-028](./028-painel-de-licoes.md) | Painel de lições | ISSUE-027 |

---

### Entrega 4. Custo e avanço físico (ISSUE-029 a ISSUE-043, 15 issues)

**Valor entregue:** EAC, contratos, EAP, Curvas S física e financeira, KPIs, contingência e desembolso, todos calculados ao vivo e ligados à gestão de mudanças.

**Pronto quando:** BAC, projeção, SPI e CPI do oráculo batem, e uma medição nova muda a Curva S na consulta seguinte.

**Como ver:** Registrar uma medição na EAP e ver a Curva S, o SPI e o CPI mudarem.

#### Onda 7. 03 Financeiro, base de custo

| Issue | Título | Bloqueada por |
|---|---|---|
| [ISSUE-029](./029-eac-arvore-visao-carteira-e-ponderacao.md) | EAC em árvore com itens, visão carteira e ponderação da carteira | ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018 |
| [ISSUE-030](./030-revisoes-da-eac-e-remanejamento-por-sm.md) | Revisões da EAC, item novo e remanejamento como SM, aplicados só na aprovação, e importação de itens | ISSUE-029, ISSUE-025 |
| [ISSUE-031](./031-mapa-de-controle-projecao-e-erp.md) | Mapa de controle com projeção, mapa de calor e custos do ERP | ISSUE-030 |
| [ISSUE-032](./032-ficha-do-contrato-medicoes-e-aditivos.md) | Ficha do contrato: cascata de valor, medições e aditivos | ISSUE-031 |
| [ISSUE-033](./033-marcos-de-pagamento-claims-e-eot.md) | Contrato: marcos de pagamento, claims e extensões de prazo | ISSUE-032, ISSUE-023 |
| [ISSUE-034](./034-avaliacao-de-desempenho-da-contratada.md) | Avaliação de desempenho da contratada | ISSUE-032, ISSUE-027 |
| [ISSUE-035](./035-contratos-consolidado-e-indicadores.md) | Contratos: visão consolidada e indicadores da administração contratual | ISSUE-033, ISSUE-034 |

#### Onda 8. 02 Planejamento, avanço físico

| Issue | Título | Bloqueada por |
|---|---|---|
| [ISSUE-036](./036-eap-arvore-dicionario-e-carteira.md) | EAP em árvore com dicionário, avanço calculado pelo critério e visão carteira | ISSUE-029 |
| [ISSUE-037](./037-medicao-estorno-e-importacao-do-avanco.md) | Medição dos pacotes pelo critério, estorno controlado e importação do avanço | ISSUE-036 |
| [ISSUE-038](./038-revisoes-da-eap-e-desdobramento.md) | Revisões da EAP a partir de SM e desdobramento de pacotes de planejamento | ISSUE-037, ISSUE-025 |
| [ISSUE-039](./039-curva-s-fisica.md) | Curva S física com linha de base congelada, real das medições e drill | ISSUE-038 |
| [ISSUE-040](./040-kpis-de-planejamento.md) | KPIs de planejamento por período e por área | ISSUE-039 |

#### Onda 9. 03 Financeiro, desempenho

| Issue | Título | Bloqueada por |
|---|---|---|
| [ISSUE-041](./041-contingencia-e-reserva-gerencial.md) | Contingência e reserva gerencial | ISSUE-039, ISSUE-031, ISSUE-025 |
| [ISSUE-042](./042-curva-s-financeira-e-kpis-de-custo.md) | Curva S financeira e KPIs de custo | ISSUE-041 |
| [ISSUE-043](./043-cronograma-de-desembolso.md) | Cronograma de desembolso e envio à tesouraria | ISSUE-031, ISSUE-033 |

---

### Entrega 5. Planejamento de campo e Programação Semanal (ISSUE-044 a ISSUE-056, 13 issues)

**Valor entregue:** Relato, 6WLA, produtividade, punch list e o app de Programação Semanal adaptado ao projeto do GestNow.

**Pronto quando:** Os testes portados do app passam, o fornecedor só enxerga a própria empresa, e os KPIs de produtividade batem com o cenário.

**Como ver:** Entrar como fornecedor, programar a semana e seguir o fluxo de cinco passos.

#### Onda 10. 02 Planejamento, campo

| Issue | Título | Bloqueada por |
|---|---|---|
| [ISSUE-044](./044-relato-do-periodo.md) | Relato do período | ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018 |
| [ISSUE-045](./045-6wla.md) | 6WLA: atividades por semana, restrições e responsáveis | ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018 |
| [ISSUE-046](./046-produtividade-quantidades-lb-e-apontamento.md) | Produtividade: plano de quantidades, ciclo da linha de base e apontamento semanal | ISSUE-025 |
| [ISSUE-047](./047-produtividade-horas-efetivas-amostragem-e-paralisacoes.md) | Produtividade: horas efetivas, amostragem do trabalho e paralisações | ISSUE-046 |
| [ISSUE-048](./048-produtividade-kpis-e-plano-de-acao.md) | Produtividade: KPIs de performance e plano de ação na Central | ISSUE-046, ISSUE-047, ISSUE-019 |
| [ISSUE-049](./049-punch-list-itens-verificacao-e-bloqueio.md) | Punch list: itens, fluxo com verificação e bloqueio de sistema | ISSUE-019 |
| [ISSUE-050](./050-punch-list-painel.md) | Punch list: painel de completação | ISSUE-049 |

#### Onda 11. 02 Programação Semanal (o app existente, adaptado)

| Issue | Título | Bloqueada por |
|---|---|---|
| [ISSUE-051](./051-programacao-semanal-matriz-e-programacao.md) | Matriz da programação semanal portada: semana de segunda a domingo, janela e programação pelo fornecedor | ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018 |
| [ISSUE-052](./052-programacao-semanal-fluxo-de-cinco-passos.md) | Fluxo de cinco passos: validar com fiscal, realizado por turno, aprovação do fiscal e publicação | ISSUE-051 |
| [ISSUE-053](./053-programacao-semanal-pedidos-de-alteracao-e-governanca.md) | Pedidos de alteração e governança da programação | ISSUE-052 |
| [ISSUE-054](./054-programacao-semanal-configuracao-por-projeto.md) | Subpágina de configuração da programação, uma por projeto | ISSUE-051 |
| [ISSUE-055](./055-programacao-semanal-importacao-planilha-e-impressao.md) | Importação da semana, planilha e relatório de impressão | ISSUE-052 |
| [ISSUE-056](./056-programacao-semanal-dashboard.md) | Dashboard da programação | ISSUE-052 |

---

### Entrega 6. Suprimentos e Riscos (ISSUE-057 a ISSUE-067, 11 issues)

**Valor entregue:** Do plano de compras ao recebimento, com o MAS montado sem digitação, e o ciclo completo de riscos, com as integrações que chegam a ele.

**Pronto quando:** Um processo de compra emite pedido ou contrato comprometendo a EAC tudo ou nada, e os números de suprimentos e riscos do oráculo batem.

**Como ver:** Levar o PC-14 da equalização comercial à emissão e ver o pedido no diligenciamento e no MAS.

#### Onda 12. 04 Suprimentos

| Issue | Título | Bloqueada por |
|---|---|---|
| [ISSUE-057](./057-fornecedores-qualificacao-e-desempenho.md) | Fornecedores com qualificação, documentos com validade e desempenho | ISSUE-034 |
| [ISSUE-058](./058-plano-de-compras.md) | Plano de compras | ISSUE-031, ISSUE-057 |
| [ISSUE-059](./059-processo-de-compra-da-requisicao-a-negociacao.md) | Processo de compra: da requisição à negociação | ISSUE-058 |
| [ISSUE-060](./060-processo-de-compra-alcada-e-emissao.md) | Processo de compra: recomendação, aprovação por alçada e emissão de pedido ou contrato | ISSUE-059, ISSUE-032 |
| [ISSUE-061](./061-diligenciamento-e-recebimento.md) | Diligenciamento e recebimento | ISSUE-060 |
| [ISSUE-062](./062-mas-mapa-de-suprimentos.md) | MAS: Mapa de Suprimentos | ISSUE-061 |
| [ISSUE-063](./063-painel-de-suprimentos.md) | Painel de suprimentos | ISSUE-062 |

#### Onda 13. 05 Riscos

| Issue | Título | Bloqueada por |
|---|---|---|
| [ISSUE-064](./064-riscos-registro-e-avaliacao.md) | Registro e avaliação de riscos | ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018 |
| [ISSUE-065](./065-ficha-do-risco-plano-revisoes-e-encerramento.md) | Ficha do risco: plano de resposta, revisões, encerramento e reabertura | ISSUE-064, ISSUE-019, ISSUE-023, ISSUE-027 |
| [ISSUE-066](./066-matriz-pxi-e-painel-de-riscos.md) | Matriz P x I e painel de riscos | ISSUE-065 |
| [ISSUE-067](./067-integracoes-que-chegam-aos-riscos.md) | Integrações que chegam aos Riscos: risco sugerido do diligenciamento, claim, lição aplicada e cobertura da contingência | ISSUE-066, ISSUE-061, ISSUE-033, ISSUE-027, ISSUE-041 |

---

### Entrega 7. Qualidade, HSE e Configurações (ISSUE-068 a ISSUE-078, 11 issues)

**Valor entregue:** RNC, ITP, auditorias, HSE com as taxas e a pirâmide, e as telas de parâmetros, colaboradores e cadastros.

**Pronto quando:** 4 RNC abertas, 263 dias sem afastamento e a pirâmide do oráculo batem; parâmetros versionados mudam as telas na hora.

**Como ver:** Reprovar uma inspeção e ver a RNC nascer; trocar a escala de riscos e ver a contagem de críticos mudar.

#### Onda 14. 06 Qualidade

| Issue | Título | Bloqueada por |
|---|---|---|
| [ISSUE-068](./068-nao-conformidades-rnc.md) | Não conformidades (RNC) | ISSUE-019, ISSUE-027 |
| [ISSUE-069](./069-inspecoes-itp-e-fat.md) | Inspeções e ITP, com o FAT do diligenciamento | ISSUE-068, ISSUE-061 |
| [ISSUE-070](./070-auditorias.md) | Auditorias | ISSUE-068 |
| [ISSUE-071](./071-painel-da-qualidade.md) | Painel da qualidade | ISSUE-069, ISSUE-070 |

#### Onda 15. 07 HSE

| Issue | Título | Bloqueada por |
|---|---|---|
| [ISSUE-072](./072-hht-inspecoes-observacoes-e-dds.md) | HHT, inspeções de segurança, observações e DDS | ISSUE-012, ISSUE-013, ISSUE-016, ISSUE-018 |
| [ISSUE-073](./073-ocorrencias-investigacao-e-lgpd.md) | Ocorrências com investigação, prazos legais e dados restritos (LGPD) | ISSUE-072, ISSUE-019, ISSUE-027 |
| [ISSUE-074](./074-apr-e-hazop.md) | Análises de risco APR e HAZOP | ISSUE-019 |
| [ISSUE-075](./075-painel-hse.md) | Painel HSE | ISSUE-072, ISSUE-073, ISSUE-074, ISSUE-034 |

#### Onda 16. Configurações

| Issue | Título | Bloqueada por |
|---|---|---|
| [ISSUE-076](./076-configuracoes-parametros.md) | Parâmetros: edição por grupo com justificativa, versões e histórico | ISSUE-066 |
| [ISSUE-077](./077-configuracoes-colaboradores.md) | Colaboradores: perfil geral, papéis na Programação Semanal por projeto, vínculo e empresa | ISSUE-054 |
| [ISSUE-078](./078-configuracoes-cadastros-de-apoio.md) | Cadastros de apoio: empresas, pessoas, projetos, sistemas, unidades e locais | ISSUE-054 |

---

### Entrega 8. Visão executiva (ISSUE-079 a ISSUE-086, 8 issues)

**Valor entregue:** Início com um indicador por módulo, carteira de projetos, análises do período e o relatório gerencial completo.

**Pronto quando:** O relatório sai em A4 com todas as folhas, no projeto e no Portfólio, com Excel e impressão.

**Como ver:** Emitir o relatório mensal do Portfólio e imprimir em PDF.

#### Onda 17. Início, análise do período e relatório gerencial

| Issue | Título | Bloqueada por |
|---|---|---|
| [ISSUE-079](./079-inicio-do-projeto.md) | Início do projeto: indicador-chave por módulo e pontos de atenção | ISSUE-020, ISSUE-026, ISSUE-035, ISSUE-040, ISSUE-042, ISSUE-050, ISSUE-063, ISSUE-066, ISSUE-071, ISSUE-075 |
| [ISSUE-080](./080-inicio-no-portfolio-e-ponderacao.md) | Início no Portfólio: carteira de projetos e edição da ponderação | ISSUE-079 |
| [ISSUE-081](./081-analise-do-periodo-02-03-04.md) | Análise do período de 02, 03 e 04, com desvios negativos e comentários obrigatórios | ISSUE-040, ISSUE-042, ISSUE-044, ISSUE-048, ISSUE-063 |
| [ISSUE-082](./082-analise-do-periodo-05-06-07-e-portfolio.md) | Análise do período de 05, 06, 07 e do Portfólio | ISSUE-081, ISSUE-066, ISSUE-071, ISSUE-075 |
| [ISSUE-083](./083-relatorio-gerencial-modal-corte-e-planejamento.md) | Relatório gerencial: modal, motor de corte e folhas de Planejamento | ISSUE-082, ISSUE-044 |
| [ISSUE-084](./084-relatorio-financeiro-e-suprimentos.md) | Relatório: folhas Financeiro (com a linha de tendência) e Suprimentos | ISSUE-083 |
| [ISSUE-085](./085-relatorio-riscos-qualidade-hse-e-carteira.md) | Relatório: folhas Riscos, Qualidade, HSE e Carteira de projetos | ISSUE-084, ISSUE-080 |
| [ISSUE-086](./086-relatorio-excel-impressao-e-alterar-periodo.md) | Relatório: Excel, Imprimir / PDF e Alterar período | ISSUE-085 |

---

### Entrega 9. Produto final (ISSUE-087 a ISSUE-093, 7 issues)

**Valor entregue:** Inglês, conferência final (oráculo, varredura, exportações, acessibilidade), prontidão para o Azure e a consolidação de tudo dentro do GestNow.

**Pronto quando:** Todas as verificações transversais da spec passam, e a raiz tem só `Timenow - GestNow` (com a confirmação do dono).

**Como ver:** Seguir o roteiro manual de aceite e o guia `PUBLICACAO-AZURE.md`.

#### Onda 18. Idioma

| Issue | Título | Bloqueada por |
|---|---|---|
| [ISSUE-087](./087-ingles-parte-1.md) | Inglês, parte 1: catálogo no servidor, seletor PT / EN, shell, Início, Central, Governança e Financeiro | ISSUE-086, ISSUE-078 |
| [ISSUE-088](./088-ingles-parte-2.md) | Inglês, parte 2: Planejamento, Programação Semanal, Suprimentos, Riscos, Qualidade, HSE, Configurações e relatório | ISSUE-087 |

#### Onda 19. Validação final e Azure

| Issue | Título | Bloqueada por |
|---|---|---|
| [ISSUE-089](./089-oraculo-de-paridade-e-calculo-vivo.md) | Oráculo de paridade completo e prova do cálculo vivo | ISSUE-088 |
| [ISSUE-090](./090-varredura-de-todas-as-telas.md) | Varredura de todas as telas nas três larguras | ISSUE-089 |
| [ISSUE-091](./091-exportacoes-acessibilidade-e-roteiro-manual.md) | Exportações tela a tela, acessibilidade e roteiro manual | ISSUE-090 |
| [ISSUE-092](./092-pronto-para-publicar-no-azure.md) | Pronto para publicar no Azure | ISSUE-091 |

#### Onda 20. Consolidação

| Issue | Título | Bloqueada por |
|---|---|---|
| [ISSUE-093](./093-consolidacao-e-desativacao-das-pastas-de-origem.md) | Consolidação dentro do GestNow e desativação das pastas de origem | ISSUE-092 |

---

## Produto final

Ao fim da ISSUE-093:

* **A pasta:** a raiz `Timenow - Gestao de Projetos` tem só `Timenow -
  GestNow` (depois da sua confirmação no pop-up final). Dentro dela estão o
  código, a documentação, as migrações, a carga de demonstração, os anexos
  locais, as referências preservadas (`docs/referencia/`) e as skills e
  configurações de ferramenta (`.claude`, `.agents`, `skills-lock.json`).
* **O app:** roda com dois cliques no `run.bat`, em modo demonstração, sobre o
  Postgres local, com as 45 telas do protótipo (com a Programação Semanal
  desdobrada nas telas do app e Configurações em três telas), todas com a
  barra lateral sempre visível, o trio de CSS e JS, cinco estados, Excel e PDF,
  PT e EN.
* **Os números:** todos calculados na hora, com a data de hoje; o oráculo de
  paridade com o protótipo passa em 25/09/2026, e as divergências estão
  documentadas.
* **A manutenção:** cada módulo tem o seu `LEIA-ME.md`; o
  `MAPA-DE-MODULOS.md` responde "quero mudar X, abro Y"; o diagrama de dados
  está em `docs/MODELO-DE-DADOS.md`.
* **O Azure:** configuração e guia prontos; publicar é um passo seu.

### Verificações que fecham o produto (Testing Decisions da spec)

| Verificação | Issue |
|---|---|
| Oráculo de paridade com o protótipo | ISSUE-089 (com as afirmações de cada módulo) |
| Cálculo vivo | ISSUE-089 |
| Varredura de telas nas três larguras | ISSUE-090 |
| Exportações tela a tela | ISSUE-091 |
| Porta de qualidade com `trio-da-tela` | ISSUE-010 e todas |
| Migrações de um banco vazio | ISSUE-005 e todas as de módulo |
| Edição simultânea | ISSUE-006 |
| Atomicidade das integrações | ISSUE-006, 025 e 060 |
| Vínculo (fornecedor e cliente) | ISSUE-011 e 051 |
| Anexos e notificação | ISSUE-012 e 013 |

### O que fica com você depois da execução

1. Revisar o modelo de dados, aceito para execução (Q30).
2. Decidir cada divergência pendente em `docs/DIVERGENCIAS-DO-PROTOTIPO.md`
   (Q31).
3. Revisar as decisões tomadas pela execução, marcadas no Histórico de
   decisões da spec como pendentes de revisão.
4. Seguir o roteiro manual de aceite (ISSUE-091).
5. Publicar no Azure pelo `docs/PUBLICACAO-AZURE.md` e, quando quiser, ligar o
   e-mail.
6. Reler o `RELATORIO-DE-EXECUCAO.md` que a execução deixa nesta pasta, com o
   que ficou pronto e o que ficou bloqueado.
