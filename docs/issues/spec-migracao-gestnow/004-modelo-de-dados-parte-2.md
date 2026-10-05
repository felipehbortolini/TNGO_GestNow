---
id: ISSUE-004
title: "Modelo de dados, parte 2: Planejamento, Programação Semanal, Suprimentos, Riscos, Qualidade, HSE, análises e relatório"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 1
onda: 1
blocked_by:
  - ISSUE-003
blocks:
  - ISSUE-005
labels:
  - ready-for-agent
source_requirements:
  - HU-152
  - HU-154
spec_decisions:
  - D5
  - D5b
  - D10
---

# Modelo de dados, parte 2: Planejamento, Programação Semanal, Suprimentos, Riscos, Qualidade, HSE, análises e relatório

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D5, D5b, D10.
> Entrega 1 (Fundação documentada), onda 1 (Repositório, estrutura e modelo de dados).
> Histórias: 152, 154. Bloqueada por: ISSUE-003.

## O que construir

Completa o diagrama de `docs/MODELO-DE-DADOS.md` com as mesmas regras da
parte 1:

* **02 Planejamento:** EAP (área, subárea, pacote; critério de medição e
  etapas), medições datadas (de, para, autor), revisões e desdobramentos,
  linha de base da curva física por revisão, relato do período (atividades e
  pontos de atenção), 6WLA (atividades e restrições), produtividade (item de
  quantidade, distribuição semanal, revisões, apontamentos, jornadas,
  amostragens, paralisações) e punch list (sistema, subsistema, TAG).
* **02 Programação Semanal:** as entidades do app portadas (atividade,
  programação por dia, realizado por turno, pedido de alteração, configuração
  por projeto com parâmetros, janelas por empresa, semanas liberadas e
  liberações extraordinárias); o "ambiente" do app vira `projeto_id`.
* **04 Suprimentos:** fornecedor e qualificação, documentos com validade,
  pacote do plano de compras, processo de compra (convidados, propostas,
  equalização, histórico), pedido com marcos de fabricação, recebimento.
* **05 Riscos:** risco, categoria RBS, avaliação com dimensões, plano de
  resposta e aprovação, revisões, linha do tempo, exclusão lógica.
* **06 Qualidade:** RNC (contenção, análise, disposição, concessão,
  verificação, custo da não qualidade), ITP com pontos e revisões, inspeção,
  auditoria e constatações.
* **07 HSE:** HHT mensal por empresa, consolidado mensal, inspeção de
  segurança, observação, DDS, ocorrência com os dados pessoais e médicos em
  tabela separada de acesso restrito, investigação, APR e HAZOP com
  recomendações.
* **Análise do período:** módulo, tipo, período, texto e comentários por chave
  de desvio; projeto nulo no Portfólio.

A tabela de cobertura passa a cobrir todos os mocks e também cada arquivo e
chave do repositório JSON do app de Programação Semanal.

## Critérios de aceite

- [x] O diagrama completo mostra as ligações entre módulos (pacote do plano para item da EAC, pedido para contrato, ação para registro de origem, risco para SM, inspeção para pedido e afins).
- [x] A cobertura mapeia 100% das coleções de todos os mocks e das chaves do repositório JSON do app de Programação Semanal.
- [x] Nome e dados médicos das ocorrências de HSE ficam em tabela própria de acesso restrito, apontada no diagrama.
- [x] Nenhum indicador derivado vira coluna, salvo as exceções da D5b.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Mesma conferência da ISSUE-003, agora para todos os mocks e para o repositório
do app de Programação Semanal; `npm run verificar` passa.

## Decisões em aberto

Nenhuma. Portão de aceite resolvido na decisão Q30.

## Notas

Fontes: mocks `mock-planejamento`, `mock-suprimentos`, `mock-riscos`,
`mock-qualidade`, `mock-hse` e o restante de `mock-portfolio`; domínio e
repositório do app de Programação Semanal. A Programação Semanal segue o app,
não a tela do protótipo (D10). Acesso ao campo restrito do HSE: Gestor e Admin
(decisão Q35).

## Registro de execução

- Decisão da execução (ISSUE-004), pendente de revisão do dono: revisões do ITP em `itp` + `itp_revisao` + `itp_ponto`; o `hse_mensal` é o fechamento mensal declarado/importado e o nome/dado médico fica em `ocorrencia_restrito`; as três camadas dos marcos de Suprimentos ficam na mesma linha (`pacote_compra_marco`, `pedido_marco`); a configuração da programação é `programacao_configuracao` (uma por projeto); a avaliação e a revisão de risco ficam em `risco_avaliacao` e `risco_revisao`. Anotado no Histórico de decisões da spec.
- Divergências com o protótipo (Q31) registradas em `docs/DIVERGENCIAS-DO-PROTOTIPO.md`, todas "pendente de aceite": séries da Curva S física, evolução do score residual, lote semanal da Programação Semanal do protótipo (D10), horizonte do 6WLA e situação das ocorrências de HSE.
- Verificação da cobertura: script Node carregou os 11 mocks na ordem do protótipo (56 coleções distintas, 104 ocorrências de coleção nos arquivos) e conferiu que 100% têm destino nas tabelas de cobertura; no repositório JSON do app, conferiu os 4 arquivos e as 13 chaves (8 de `programacao.json` + 3 de `cadastros` + 2 de `registro.json`), todas com destino.
- `npm run verificar` passou nas cinco etapas, sem regra desligada. `index.md`, status da issue e commit são do orquestrador.
