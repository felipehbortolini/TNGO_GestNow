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

## Registro de execução

Fatia entregue em 10/10/2026: a tela **Configurações > Parâmetros**, sobre a camada de
versionamento da ISSUE-007 (nada de esquema novo; **sem migração**). O `forms.py` novo é o porte
de `grupos(p)` e do `exibir(c, v)` do protótipo: os **10 grupos da tela** sobre os 14 grupos de
parâmetros (`GROUP_SOURCES` — Planejamento agrega punch + produtividade + eap; Governança agrega
mudanças + lições; Contratadas agrega a avaliação + claims), com os campos construídos **dos
valores vigentes** (critérios e classes, alçadas e pesos dos marcos, probabilidades, modelos de
etapas da EAP, critérios do portfólio), o caminho da folha como identidade (o id no formulário
troca os pontos por `__`), a digitação tipada (número, inteiro quando o vigente é inteiro, moeda
em reais → centavos, select pelas opções) e o `parse_group_form`, que devolve os payloads por
grupo de origem, os campos mudados e os erros por caminho — inclusive a recusa da troca da escala
sem o `confirmar_escala`. A fachada ganhou a leitura da tela (`parameter_overview`: grupos
filtrados no servidor, linhas já formatadas, versão vigente de cada grupo de origem com autor,
vigência e justificativa) e o **histórico** (`parameter_history`: versões desc com as alterações
contra a versão anterior do MESMO grupo, o selo Vigente pela data de referência e a primeira
versão de cada grupo sem alterações). As rotas (`parameters_*`, `Access(module="configuracoes")`
— só Gestor e Admin; nomes únicos no app) desenham a tela (filtro pela query `busca`/`modulo`),
o modal de edição, o modal do histórico (o Ver é um GET do mesmo fragmento com `grupo` e
`versao`), e a gravação cria a versão **só dos grupos de origem que mudaram**, num savepoint da
transação, com vigência de hoje e autor; a recusa volta no formulário com 422 (o erro de um
campo sob o campo, o de um bloco no topo; "Nenhum valor foi alterado." quando nada mudou) e o
sucesso devolve a tela com o toast "Versão N gravada: X parâmetros alterados." e fecha o modal.
O `export.py` monta o documento das duas tabelas do protótipo (Parâmetros vigentes:
Grupo/Parâmetro/Valor/Módulo; Histórico de versões com a coluna Grupo), sem a coluna Projeto
porque os parâmetros são globais, e o Excel e o PDF saem pelos mecanismos genéricos. O trio foi
reescrito no padrão das telas com modal (cinco estados, filtros pela query, `TN.modal`). Os 20
testes novos (`test_parametros_rotas.py`, com o conftest reusando o cenário dos riscos): 403 para
Membro e Visualizador, filtros no servidor, modal com os campos vigentes, gravações (sem
justificativa, sem alteração, não numérico por campo, bloco inválido, versão só do grupo que
mudou, autor e vigência) e a troca da escala de riscos — sem confirmação recusa; com confirmação
grava e a severidade do risco P5×I4 muda de crítico para alto na ficha seguinte. Divergências
registradas: o versionamento por grupo (o protótipo versionava o conjunto inteiro) e o filtro no
servidor com o grupo Anexos na tela. `ruff check`, `ruff format --check` e `ty check` limpos; as
rodadas do fechamento (configurações, plataforma e riscos — 1.146 testes cada, duas vezes)
passam; a porta de qualidade, 5/5. Defeito corrigido pelo principal: o botão do histórico usava o
ícone `history`, que não existe em `app/ds/icons.js` — trocado por `clock`, o padrão das telas de
histórico.

- DECISAO: versionamento por grupo na tela | o card mostra a versão mais recente entre os grupos e o histórico compara cada versão com a anterior do MESMO grupo; um grupo da tela agrega vários grupos de parâmetros e a gravação cria versão só dos grupos de origem cujos valores mudaram | modelo "uma linha por grupo e versão" (D5, ISSUE-007), ISSUE-076
- DECISAO: confirmação da troca de escala | o formulário do grupo Riscos traz o campo `confirmar_escala` e o servidor recusa a gravação sem ele (422), no lugar do modal de confirmação do protótipo | ISSUE-076
- DECISAO: filtro da tela | busca e módulo recarregam o fragmento pela query e o servidor re-renderiza (o protótipo filtrava localmente) | D6/D11, ISSUE-076
- DECISAO: grupo Anexos na tela | entra com o limite editável e os tipos aceitos somente leitura (o protótipo não o mostrava; o GestNow o versiona) | D5a, ISSUE-076
