---
id: ISSUE-008
title: "Carga de demonstração deslocada para hoje, base de produção vazia com o primeiro Admin e harness do oráculo"
status: done
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

- [x] Em demonstração, o `run.bat` carrega a base com as datas deslocadas para hoje, e rodar de novo não duplica nada.
- [x] Em produção, a base sobe vazia com o Admin da variável e nenhum dado fictício.
- [x] O harness do oráculo roda com a data 25/09/2026 e passa com os números da plataforma.
- [x] Os dados convertidos ficam dentro do GestNow, e o `LEIA-ME.md` da carga explica como cada módulo registra a sua parte.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

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

## Registro de execução

Data: 05/10/2026.

Feito: `api/src/carga/` é o mecanismo da carga — `registro.py` (registro das
partes e `shift_date`, âncora 25/09/2026), `runner.py` (`run_for_mode`,
`run_demonstration` idempotente por `carga_demonstracao`, `run_production`),
`plataforma.py` (cliente, 3 projetos e notas da ponderação, empresas, pessoas,
colaboradores cobrindo os 4 perfis gerais, os 4 papéis da Programação Semanal
por projeto e os 3 vínculos, sistemas, locais, disciplinas, unidades e a
versão 1 dos parâmetros) e `producao.py` (base vazia + primeiro Admin).
`scripts/converter_mocks.mjs` executa os mocks do protótipo na ordem de carga e
grava `api/src/carga/dados/plataforma.json`, que é a fonte versionada dentro do
GestNow. `scripts/seed_database.py` aplica o modo configurado e o `run.bat` o
chama depois de preparar o banco. Modo por variável de ambiente: `GESTNOW_MODO`
(ausente = `demonstracao`; valor desconhecido falha alto) e
`GESTNOW_ADMIN_EMAIL` para o primeiro Admin. Harness do oráculo em
`api/tests/oraculo/` (data injetada 25/09/2026, sem deslocamento) com as
afirmações da plataforma; as issues de módulo acrescentam as suas via
`register_check`. Migração `0003_carga_demonstracao` e modelo `SeedRun`; o
`MODELO-DE-DADOS.md` foi atualizado na mesma issue.

Decisões tomadas, anotadas na spec como "Decisão da execução (ISSUE-008),
pendente de revisão do dono": nomes/valores de `GESTNOW_MODO` e
`GESTNOW_ADMIN_EMAIL`; mecanismo de registro por módulo (`seed.py` descoberto no
import) com a tabela `carga_demonstracao`; conversão por script gerando JSON; e
o elenco de demonstração (18 pessoas do mock como colaboradores + 1 pessoa de
demonstração para o vínculo Cliente, que o mock não tem; locais, disciplinas e
unidades derivados dos campos de texto dos mocks). Divergência registrada em
`docs/DIVERGENCIAS-DO-PROTOTIPO.md`: a pessoa de demonstração a mais.

Fora desta fatia, por desenho da issue: a parte de cada módulo na carga (cada
issue de módulo registra a sua) e o oráculo consolidado completo (ISSUE-089);
o seletor de perfis que usa esses colaboradores é da ISSUE-011.

Verificação: `api/.venv/Scripts/python.exe -m pytest` verde (83 testes; 14
novos: 13 da carga e produção, 1 do oráculo); `scripts/seed_database.py`
aplicou a demonstração no `gestnow` (3 projetos, 18 empresas, 19 pessoas, 9
sistemas; início do TN-2026-014 em 15/01/2026, dez dias após a âncora, batendo
com hoje 05/10/2026) e, repetido, reportou "já aplicada; nada foi duplicado".
`npm run verificar` passou nas cinco etapas, sem regra desligada.
