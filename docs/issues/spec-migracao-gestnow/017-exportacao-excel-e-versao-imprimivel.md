---
id: ISSUE-017
title: "Exportação Excel e versão imprimível (PDF pelo navegador) genéricas"
status: in-progress
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 2
onda: 4
blocked_by:
  - ISSUE-011
  - ISSUE-014
blocks:
  - ISSUE-018
labels:
  - ready-for-agent
source_requirements:
  - HU-016
  - HU-136
  - HU-137
  - HU-138
spec_decisions:
  - D12
  - D14
---

# Exportação Excel e versão imprimível (PDF pelo navegador) genéricas

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D12, D14.
> Entrega 2 (Plataforma no ar), onda 4 (Serviços transversais).
> Histórias: 16, 136, 137, 138. Bloqueada por: ISSUE-011, ISSUE-014.

## O que construir

O **Excel** é gerado no servidor com openpyxl, por um construtor genérico que
toda tela usa: logo, título, escopo (Portfólio ou projeto), data de geração,
KPIs com a referência de gestão, tabelas com filtro e cores das células pelos
tokens, valores em reais (integral) e datas formatadas. No Portfólio, a coluna
Projeto entra sempre. A rota de download segue a exceção de download do Padrão
e passa pelo mesmo decorador de permissão.

O **PDF** é a impressão do navegador: o servidor renderiza a versão imprimível
da tela (cabeçalho com logo e contexto, KPIs, gráficos e tabelas) pela folha
de impressão do Design System; o botão PDF a abre e aciona a impressão, e a
pessoa escolhe "Salvar como PDF". `@page` A4 paisagem por padrão, com opção A3
paisagem; sem navegação no papel; cabeçalho de tabela repetido; linha que não
parte entre páginas; fundos preservados. Sem biblioteca de PDF no servidor nem
no navegador.

Os dois mecanismos são demonstrados numa tela de exemplo do styleguide ou numa
rota de teste, para que as issues de módulo só os usem.

## Critérios de aceite

- [ ] O Excel gerado abre e tem logo, título, escopo, data, KPIs com referência e a tabela com filtro; no Portfólio, a coluna Projeto.
- [ ] As cores das células do Excel vêm dos tokens.
- [ ] A versão imprimível não tem barra lateral nem navegação, repete o cabeçalho da tabela em cada página e não parte linha.
- [ ] A3 paisagem funciona quando a tela pede.
- [ ] Nenhuma biblioteca de PDF foi adicionada.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Teste que abre o Excel gerado com openpyxl e confere planilha, cabeçalho, KPIs
e colunas; teste de rota do download (tipo e permissão); teste do template
imprimível sem navegação. `npm run verificar` passa.

## Decisões em aberto

Nenhuma.

## Notas

Precedentes: exportação, planilha, `print.css` e relatório de impressão do app
de Programação Semanal. O conteúdo de cada exportação vem do protótipo
(`js/components/exportar.js` e `logo-pdf.js`): o que o protótipo exporta, o
GestNow exporta, nem uma coluna a menos.
