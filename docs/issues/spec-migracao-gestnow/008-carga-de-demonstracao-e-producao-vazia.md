---
id: ISSUE-008
title: "Carga de demonstração deslocada para hoje, base de produção vazia com o primeiro Admin e harness do oráculo"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 2
onda: 2
blocked_by:
  - ISSUE-006
  - ISSUE-007
blocks:
  - ISSUE-009
labels:
  - ready-for-agent
source_requirements:
  - HU-027
  - HU-151
spec_decisions:
  - D6
  - D7
---

# Carga de demonstração deslocada para hoje, base de produção vazia com o primeiro Admin e harness do oráculo

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D6, D7.
> Entrega 2 (Plataforma no ar), onda 2 (Dados).
> Histórias: 27, 151. Bloqueada por: ISSUE-006, ISSUE-007.

## O que construir

O modo do app (demonstração ou produção) vem de variável de ambiente.

Em **demonstração**, a carga inicial é aplicada por um mecanismo de
plataforma. Cada módulo registra a sua parte, lida dos mocks do protótipo
convertidos para dados de carga gravados dentro do GestNow, e o carregador
desloca todas as datas pela diferença entre hoje e 25/09/2026, preservando a
coerência do cenário. A carga é idempotente (rodar de novo não duplica) e só
existe no modo demonstração. Nesta issue entra a parte da plataforma: os 3
projetos do portfólio (TN-2026-014, TN-2026-021 e TN-2026-027, com as notas de
ponderação), empresas, pessoas, cadastros de apoio e colaboradores de
demonstração cobrindo os perfis gerais, os papéis da Programação Semanal e os
três vínculos.

Em **produção**, a base nasce vazia, só com os cadastros mínimos e o primeiro
Admin, cujo e-mail vem de variável de ambiente.

O **harness do teste-oráculo** nasce aqui: carrega a demonstração com a data
injetada em 25/09/2026, sem deslocamento, num banco de teste, e oferece a cada
módulo um lugar para afirmar os números conhecidos do protótipo. Nesta issue
ele afirma só o que já existe (projetos e cadastros); cada issue de módulo
acrescenta os seus números.

## Critérios de aceite

- [ ] Em demonstração, o `run.bat` carrega a base com as datas deslocadas para hoje, e rodar de novo não duplica nada.
- [ ] Em produção, a base sobe vazia com o Admin da variável e nenhum dado fictício.
- [ ] O harness do oráculo roda com a data 25/09/2026 e passa com os números da plataforma.
- [ ] Os dados convertidos ficam dentro do GestNow, e o `LEIA-ME.md` da carga explica como cada módulo registra a sua parte.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Teste da carga (deslocamento de uma data conhecida e idempotência), teste do
modo produção (base vazia mais o Admin) e harness do oráculo verde.
`npm run verificar` passa.

## Decisões em aberto

Nenhuma.

## Notas

Fontes: `mock-base`, `mock-config` e `mock-portfolio`. Partes dos mocks são
geradas por código com semente fixa (jornadas, amostragens, ocorrências):
converta a partir do resultado já gerado (executando o mock e gravando os
dados), nunca reimplementando o gerador, para que os números batam. Deslocar
datas pode cair em fim de semana, sem efeito nos cálculos (risco aceito).
