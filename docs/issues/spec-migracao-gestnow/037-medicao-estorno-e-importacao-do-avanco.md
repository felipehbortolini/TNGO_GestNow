---
id: ISSUE-037
title: "Medição dos pacotes pelo critério, estorno controlado e importação do avanço"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 4
onda: 8
blocked_by:
  - ISSUE-036
blocks:
  - ISSUE-038
labels:
  - ready-for-agent
source_requirements:
  - HU-057
  - HU-058
  - HU-059
spec_decisions:
  - D6
---

# Medição dos pacotes pelo critério, estorno controlado e importação do avanço

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D6.
> Entrega 4 (Custo e avanço físico), onda 8 (02 Planejamento, avanço físico).
> Histórias: 57, 58, 59. Bloqueada por: ISSUE-036.

## O que construir

**Registrar avanço** por pacote recebe as entradas do critério (% concluído
por etapa, quantidade executada, marcos atingidos ou percentual estimado, este
só para pacotes de até 5% de peso); o real é sempre calculado, nunca digitado
como resultado. O acumulado não regride: **estorno** só com justificativa e
papel Gestor. O executado não passa a quantidade da linha de base (exige SM e
revisão). Cada medição guarda data, de, para, autor e observação, e o
histórico aparece no dicionário do pacote.

A **importação do avanço** por planilha (% acumulado ou quantidade executada)
usa o fluxo genérico, com recusa por linha: pacote de planejamento, marco fora
dos degraus e regressão.

## Critérios de aceite

- [x] Cada critério calcula o real a partir das entradas (teste por critério).
- [x] Regressão sem estorno é recusada; o estorno exige Gestor e justificativa.
- [x] Executado acima da quantidade da linha de base é recusado com a mensagem.
- [x] A importação recusa as linhas inválidas com o motivo e grava as válidas só na confirmação.
- [x] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (medição, estorno, limite e importação) e de rota (403 no estorno sem Gestor).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `GI.api.planejamento.eapRegistrarAvanco` e `eapImportarAvanco`.

## Registro de execução

- Data: 2026-10-07.
- Feito: as etapas 1 a 3 (commits `7ca707c`, `90beb21`, `2074187`) entregaram a conversão por percentual, a regressão, o estorno com Gestor e justificativa, o limite da linha de base, a validação da medição, o cálculo por critério com um teste por critério, a fachada (`service.register_progress` e `service.import_progress`), as rotas do avanço e da importação e o importador `eap-avanco` pelo mecanismo genérico. Nesta etapa de fechamento, a tela `planejamento/eap` ganhou a ação **Registrar avanço** em cada pacote de trabalho (o pacote de planejamento não recebe medição e no Portfólio a ação não aparece) e o botão **Importar avanço** no cabeçalho, que só aparece no projeto editável e abre o formulário do importador no modal do Design System (formulário → conferir → confirmar, no padrão das telas do financeiro); o comportamento mantém os estados existentes e deixa o 422 por campo, o 403 do estorno e o 409 de versão no lugar (a resposta multi-alvo devolve o conteúdo e o formulário); o estilo escopado cobre as ações da linha da árvore, o espaçamento dos formulários do dicionário e do avanço e o campo da data da importação; o `LEIA-ME.md` do módulo recebeu a seção "Medição do avanço (ISSUE-037)".
- Ajuste mínimo em arquivos da fatia exigido pela tela: `_eap_arvore.html` ganhou a ação Registrar avanço e o agrupamento das ações da linha; `_eap_conteudo.html` ganhou o marcador `data-pode-editar` que governa o botão Importar avanço; a conferência e a confirmação da importação passaram a responder o resultado (ou a conferência) e o conteúdo no mesmo pedido (`eap_importacao_conferencia.html` e `eap_importacao_resultado.html`, com `x-target` de sucesso e `x-target.error` no formulário), para a árvore refletir as medições gravadas sem recarregar a tela.
- Divergências do protótipo: os filtros da barra (busca, nível, critério e situação) continuam fora, como na ISSUE-036; o formulário do avanço não faz a simulação ao vivo do novo real nem esconde a justificativa enquanto não há regressão — o campo fica sempre visível, com a dica, e o servidor o exige só na regressão; a importação usa a rota do módulo, com a data da medição no formulário e a conferência (pré-visualização e recusas por linha) depois do envio, e as colunas do modelo só no arquivo modelo, não listadas no formulário.
- Porta de qualidade (`node scripts/verificar.mjs`, cinco etapas) verde e a suíte completa de pytest (2.364 testes, 0 falhas, 0 erros) passou em 07/10/2026.
