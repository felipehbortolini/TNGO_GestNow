---
id: ISSUE-033
title: "Contrato: marcos de pagamento, claims e extensões de prazo"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 4
onda: 7
blocked_by:
  - ISSUE-032
  - ISSUE-023
blocks:
  - ISSUE-035
  - ISSUE-043
  - ISSUE-067
labels:
  - ready-for-agent
source_requirements:
  - HU-095
  - HU-096
spec_decisions:
  - D5a
  - D9
---

# Contrato: marcos de pagamento, claims e extensões de prazo

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D5a, D9.
> Entrega 4 (Custo e avanço físico), onda 7 (03 Financeiro, base de custo).
> Histórias: 95, 96. Bloqueada por: ISSUE-032, ISSUE-023.

## O que construir

Aba **Marcos de pagamento**: Nº, descrição, critério de aceite, % do valor,
valor, data prevista, data de conclusão e retenção; fluxo Previsto, Evidência
enviada, Aprovado (fiscal e gestor), Faturado, Pago. O marco só é aprovado com
anexo de evidência, e a soma dos % de um contrato é 100.

Aba **Claims**: número `CLM-TN-2026-0001`; direção (da contratada ou do
contratante); tipo (Prazo, Custo, Prazo e custo); causa; datas do evento e da
notificação, com **alerta de notificação fora do prazo contratual**; valor e
dias pleiteados e reconhecidos; cláusula; documentos. Fluxo Notificado, Em
análise, Em negociação, Acordado (total ou parcial) ou Rejeitado, Em disputa,
Encerrado. O claim acordado cria SM na Governança pela fachada dela, na mesma
transação; o vínculo com risco é ligado na ISSUE-067.

Aba **Extensões de prazo**: número `EOT-TN-2026-0001`; evento causador (pode
vir de um claim); dias solicitados e concedidos; marco afetado; classificação
(Justificável e compensável, Justificável não compensável, Não justificável);
análise de atraso (método, atividades e caminho crítico). Fluxo Solicitada, Em
análise, Concedida (total ou parcial) ou Negada; a concedida prorroga o término
vigente e cria SM para a linha de base do cronograma.

## Critérios de aceite

- [x] Marco sem anexo não é aprovado, e soma de % diferente de 100 é recusada.
- [x] Claim notificado depois do prazo contratual aparece com alerta (teste de fronteira no último dia).
- [x] Claim acordado e EOT concedida criam SM na Governança na mesma transação.
- [x] EOT concedida prorroga o término vigente do contrato.
- [x] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [x] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [x] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada de cada fluxo, do alerta de prazo e das SMs criadas.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `GI.api.financeiro.claims` e `decidirEot`; README, "Claims",
"Extensões de prazo" e "Marcos de pagamento".

## Registro de execução

- Data: 2026-10-06 a 2026-10-07.
- Feito: as fórmulas puras (valor e retenção do marco, soma dos percentuais, atraso do marco, prazo de notificação do claim e prorrogação da EOT), as validações dos formulários e das transições, o serviço (marco com evidência por anexo e fluxo até Pago, claim com o alerta de notificação e a SM da Governança no Acordado, EOT com a prorrogação do término vigente e a SM da linha de base), a migração `m033`, a carga de demonstração `financeiro-contratos-fluxos`, os fragmentos das três abas com os formulários, o export por aba e as rotas correspondentes; nesta etapa de fechamento, a tela recebeu as abas **Marcos de pagamento**, **Claims** e **Extensões de prazo** (view, comportamento e estilo do trio `financeiro/contrato`, com os botões Excel/PDF por aba, o destaque de linha dos alertas de prazo e a faixa sincronizada nas operações) e o `LEIA-ME.md` do módulo recebeu a seção desta fatia, com as fórmulas e os nomes no código.
- Decisão de execução: as abas novas carregam por AJAX no mesmo `x-init` das existentes e as operações devolvem os painéis atualizados na resposta multi-alvo, com o formulário vazio; o formulário da evidência é um `multipart/form-data` de verdade, pelo mecanismo genérico de anexos (D5a); a linha atrasada do marco e a do claim com notificação fora do prazo ganham a classe `contrato-linha-alerta` (fundo `--erro-50` e barra `--erro-500`), além do texto; a raiz da faixa de identificação carrega `x-sync` nas respostas para o vínculo de sincronização sobreviver à troca do elemento e valer nas respostas seguintes.
- Ajuste mínimo em templates existentes: a resposta dos fluxos passou a devolver a faixa de identificação (o término vigente muda com a EOT concedida) e as três respostas que trazem a faixa carregam `x-sync` na raiz; o ajuste não muda nenhuma regra de negócio.
- Divergências do protótipo: os formulários abrem embutidos no alvo `contrato-formulario` (o padrão da ISSUE-032), não no modal do protótipo; o claim não recebe documentos no formulário (o tipo de origem `contrato_claim` já aceita anexos, mas o campo não entrou no backend desta fatia); os botões Excel/PDF do cabeçalho da ficha continuam exportando o Resumo, as Medições e os Aditivos, e cada aba nova tem os seus próprios botões, sobre os exports por aba.
- Porta de qualidade (`npm run verificar`) e a suíte completa de pytest (2.135 testes) passaram em 07/10/2026.
