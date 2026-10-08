---
id: ISSUE-058
title: "Plano de compras"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 6
onda: 12
blocked_by:
  - ISSUE-031
  - ISSUE-057
blocks:
  - ISSUE-059
labels:
  - ready-for-agent
source_requirements:
  - HU-099
spec_decisions:
  - D9
---

# Plano de compras

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D9.
> Entrega 6 (Suprimentos e Riscos), onda 12 (04 Suprimentos).
> Histórias: 99. Bloqueada por: ISSUE-031, ISSUE-057.

## O que construir

A tela **Plano de compras** mostra os pacotes: código, escopo, tipo
(Equipamento, Material, Serviço, EPC), modalidade, disciplina, LLI, item da EAC,
estimativa, comprador, datas planejadas (linha de base) e ROS; etapa, folga e
adjudicado. **Novo pacote** calcula na hora o saldo a comprometer do item e a
folga planejada; edição e importação Excel.

Regras: todo pacote nasce vinculado a um item de nível 3 da EAC; compra
emergencial é marcada e justificada; o plano não nasce com folga negativa; a
linha de base fica congelada a partir da requisição, e depois disso só escopo,
comprador, estimativa e ROS mudam, com justificativa e histórico.

## Critérios de aceite

- [x] Pacote sem item de nível 3 da EAC é recusado.
- [x] Pacote com folga negativa no plano é recusado.
- [x] Depois da requisição, mudar a linha de base é recusado, e as mudanças permitidas exigem justificativa.
- [x] O saldo a comprometer do item vem da EAC no momento da consulta.
- [x] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [x] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [x] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [x] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (vínculo, folga, congelamento e importação).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `plano-compras.html`, `GI.api.suprimentos.pacotes`, `salvarPacote` e `importarPacotes`.

## Registro de execução

- Data: 08/10/2026
- Feito: tela `suprimentos/plano_compras` (KPIs, filtros, tabela com Projeto no Portfólio, paginação), formulário completo/congelado com saldo e folga ao vivo, importação Excel genérica, exports Excel/PDF, fachada, migração `m046_pacotes_de_compra.py` (revision `m046`, down `m043` — o head real; `m044`/`m045` já existiam), carga `suprimentos-pacotes` (28 pacotes) e testes de fórmula, fachada, rota e oráculo.
- Verificação: ruff format e ruff check nos arquivos tocados; a porta completa fica para o dono.
- Pendências: adjudicado, fornecedor e saving ficam "—" até a ISSUE-059 (processo) e ISSUE-061 (pedido); conferência/execução dos testes não rodadas por decisão do dono.
- DECISAO: folga planejada | fim = marco `pedido` para todos os tipos, porque o modelo não tem `prazo_entrega_dias` e o mock não traz o dado; coluna removida do formulário e da planilha | D9, ISSUE-058
- DECISAO: adjudicado/fornecedor/saving | vazio/— até a 059/061, calculados dos registros quando existirem; o plano não guarda o adjudicado | D5b, ISSUE-058
- DECISAO: histórico e justificativas | trilha na entidade `pacote_compra.historico` (campos e justificativa), com a justificativa da emergência que não tem coluna | ISSUE-004, ISSUE-058
- DECISAO: migração | id `m046` (m044 e m045 já usados), down_revision `m043`, o head conferido | ISSUE-058
- DECISAO: coluna Prazo de entrega (dias) | fora do formulário e da importação, pela mesma ausência de coluna | Q31, ISSUE-058
