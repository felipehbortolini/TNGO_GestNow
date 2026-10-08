---
id: ISSUE-043
title: "Cronograma de desembolso e envio à tesouraria"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 4
onda: 9
blocked_by:
  - ISSUE-031
  - ISSUE-033
blocks: []
labels:
  - ready-for-agent
source_requirements:
  - HU-091
spec_decisions:
  - D12
---

# Cronograma de desembolso e envio à tesouraria

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D12.
> Entrega 4 (Custo e avanço físico), onda 9 (03 Financeiro, desempenho).
> Histórias: 91. Bloqueada por: ISSUE-031, ISSUE-033.

## O que construir

A tela **Cronograma de desembolso** é gerada a partir do mapa de controle: o
saldo a pagar de cada item (projeção no término menos realizado) é distribuído
nos meses depois do corte, pelos marcos de pagamento e contratos quando
existem e, senão, pelo perfil da projeção. Mostra o histograma mensal previsto
x realizado e a tabela item x mês com totais. **Enviar à tesouraria** passa
pela porta de notificação (simulado enquanto desligada).

## Critérios de aceite

- [x] A soma dos meses futuros de cada item é igual à projeção menos o realizado (teste).
- [x] Contrato com marcos de pagamento usa os marcos na distribuição.
- [x] O envio à tesouraria fica na trilha com o aviso "simulado".
- [x] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [x] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo da distribuição e de fachada do envio.

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `desembolso.html`, `GI.api.financeiro.desembolso`. A tela do protótipo
também usa o histograma de mão de obra (derivado do HHT e da Curva S); ele
passa a ser calculado no servidor e é ligado na ISSUE-072, quando o HHT existir.

## Registro de execução

- Data: 2026-10-07.
- Feito: as etapas 1 e 2 (commits `2ef5de5` e `d0db6e7`) entregaram os cálculos da distribuição e do histograma (`calculations.monthly_amounts`, `disbursement_histogram`, `distribute_balance`, `share_percent` e o rateio centavo a centavo pelo maior resto) com testes de fronteira (marco maior que o saldo, marco fora dos meses, sem perfil), o serviço (`disbursement_overview`, no projeto e no Portfólio, e `send_to_treasury` pela porta de notificação), as rotas `GET /api/financeiro/desembolso` (alvo `desembolso-conteudo`; o parâmetro `nivel` de 1 a 3, padrão 2, inválido 422) com `/excel` e `/imprimivel`, e `GET/POST /api/financeiro/desembolso/enviar` (alvo `desembolso-modal`), os fragmentos `desembolso.html` e `desembolso_envio.html`, o documento de exportação (`export.desembolso_document`) e os testes de cálculo, serviço e rotas. Esta etapa de fechamento entregou a tela (trio `app/_views/financeiro/desembolso.html`, `app/paginas/financeiro/desembolso.css` e `.js`): a toolbar **Mostrar até** (1 pacotes, 2 subpacotes — o padrão — e 3 itens) recarrega o fragmento com o `nivel` e mantém o nível nas exportações; **Enviar à tesouraria** abre o modal (`GET /enviar` no alvo `desembolso-modal`), com o fechamento pelo atributo `data-desembolso-fechar-modal`, e o formulário grava pelo `POST`; Excel e PDF saem pelos mecanismos genéricos (D12) e o `LEIA-ME.md` do módulo ganhou a seção da fatia.
- Oráculos: no projeto 1, o saldo a desembolsar é R$ 16.555.000,00 (realizado de R$ 28,7 mi no corte de 25/09/2026); na carteira, R$ 33.995.000,00. O histograma mensal desenha as três séries no visual **Curva S Barra e Linha** (`curva-s-barra-linha`, D11; em R$ mil) e o Excel traz as folhas "Resumo", "Desembolso mensal" e "Saldo a pagar por mês".
- Fora desta fatia: o histograma de mão de obra do protótipo (derivado do HHT e da Curva S) fica para a ISSUE-072, quando o HHT existir; a tela é só de leitura — a curva muda pelas revisões da EAC e pelos fechamentos do ERP; o envio fica na trilha como simulado enquanto `GESTNOW_ENVIO_EMAIL` estiver desligado.
- Porta de qualidade (`node scripts/verificar.mjs`, cinco etapas) verde e a suíte completa de pytest (2.660 testes, 0 falhas, 0 erros) passou em 07/10/2026.
