---
id: ISSUE-034
title: "Avaliação de desempenho da contratada"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 4
onda: 7
blocked_by:
  - ISSUE-032
  - ISSUE-027
blocks:
  - ISSUE-035
  - ISSUE-057
  - ISSUE-075
labels:
  - ready-for-agent
source_requirements:
  - HU-097
spec_decisions:
  - D5b
  - D5a
---

# Avaliação de desempenho da contratada

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D5b, D5a.
> Entrega 4 (Custo e avanço físico), onda 7 (03 Financeiro, base de custo).
> Histórias: 97. Bloqueada por: ISSUE-032, ISSUE-027.

## O que construir

Aba **Avaliação de desempenho** da ficha do contrato: periodicidade mensal
durante a execução e avaliação final no encerramento. Critérios com nota de 1
a 5 e peso dos parâmetros vigentes (HSE, Qualidade, Prazo, Gestão contratual e
comercial, Recursos e mobilização, Documentação e comunicação). Os pesos ficam
**gravados na avaliação**: mudar o parâmetro depois não muda a nota. Nota
ponderada de 0 a 100 e classe A, B, C ou D pelas notas mínimas dos
parâmetros.

Nota 1 ou 2 em qualquer critério exige anexo de evidência e cria plano de
melhoria na Central (origem Contrato). A avaliação final gera lição de
fornecedor em Rascunho pela fachada de Lições. A atualização da qualificação do
fornecedor é ligada na ISSUE-057, e a nota HSE sugerida pelo 07, na ISSUE-075.
O desempenho ao longo do tempo usa o Gráfico de Áreas de Avaliação.

## Critérios de aceite

- [x] Nota ponderada e classe têm testes de fronteira (84 e 85, 69 e 70, 49 e 50).
- [x] Mudar os pesos nos parâmetros não muda avaliação já gravada.
- [x] Nota 1 ou 2 sem anexo é recusada; com anexo, cria ação na Central com origem Contrato.
- [x] A avaliação final cria lição em Rascunho com origem no contrato.
- [x] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [x] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [x] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo (nota e classe) e de fachada (evidência, ação e lição).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: regra de avaliação em `regras.js` e o grupo Avaliação de contratadas da
seção 7.4; README, "Avaliação de desempenho da contratada".

## Registro de execução

- Data: 2026-10-06 a 2026-10-07.
- Feito: as fórmulas puras (nota ponderada com os pesos gravados, classe pelo maior mínimo e o exige-plano), a validação do formulário (período mês, tipo Mensal ou Final, nota de 1 a 5 e comentário de até 400 caracteres), o serviço (avaliação com os pesos congelados em `contrato_avaliacao_criterio`, a evidência obrigatória quando a nota alcança o limite, a ação do plano de melhoria na Central e a lição em Rascunho da avaliação Final, na mesma transação), a migração `m034`, a carga de demonstração `financeiro-contratos-avaliacoes`, os fragmentos da aba e do formulário, o gráfico de áreas e os exports; nesta etapa de fechamento, a tela recebeu a aba **Avaliação de desempenho** (view, comportamento e estilo do trio `financeiro/contrato`, com os botões Excel/PDF, as notas baixas na família de erro, o aviso ao vivo do plano no formulário e a área do gráfico) e o `LEIA-ME.md` do módulo recebeu a seção desta fatia, com as fórmulas e os nomes no código.
- Decisão de execução: a aba carrega por AJAX no mesmo `x-init` das existentes e as operações devolvem a aba e o formulário na resposta multi-alvo; o formulário é um `multipart/form-data` de verdade, pelo mecanismo genérico de anexos (D5a); os pesos da versão vigente dos parâmetros entram gravados na avaliação (D5b) e a avaliação Final cria a lição em Rascunho pela fachada de Lições (D9), na mesma transação.
- Ajuste mínimo em arquivos da própria fatia: o contexto da aba e do formulário passou a levar `limite_plano` (a `notaExigePlano` vigente), a linha da tabela leva `notas_baixas` para destacar a nota no limite ou menor e o formulário ganhou os ganchos (`data-avaliacao`, `data-limite-plano`, `data-nota`, `data-aviso-plano`) do aviso ao vivo; nenhuma regra de negócio mudou.
- Divergências do protótipo: o formulário abre embutido no alvo `contrato-formulario` (o padrão da ISSUE-032/033), não no modal do protótipo; o período é um `type=month`, não o select dos meses do contrato do protótipo (a duplicidade por período e tipo é conferida no servidor); o resultado calculado a cada mudança de nota do protótipo virou o aviso de obrigatoriedade quando alguma nota alcança o limite, com o cálculo final no servidor.
- Porta de qualidade (`npm run verificar`) e a suíte completa de pytest (2.200 testes) passaram em 07/10/2026.
