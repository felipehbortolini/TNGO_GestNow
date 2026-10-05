---
id: ISSUE-007
title: "Data de hoje, calendário de semanas e períodos, e parâmetros versionados"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 2
onda: 2
blocked_by:
  - ISSUE-005
blocks:
  - ISSUE-008
  - ISSUE-012
labels:
  - ready-for-agent
source_requirements:
  - HU-021
  - HU-022
  - HU-131
  - HU-150
spec_decisions:
  - D6
---

# Data de hoje, calendário de semanas e períodos, e parâmetros versionados

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D6.
> Entrega 2 (Plataforma no ar), onda 2 (Dados).
> Histórias: 21, 22, 131, 150. Bloqueada por: ISSUE-005.

## O que construir

Uma única função de plataforma devolve **hoje** no fuso `America/Sao_Paulo`.
Toda fórmula que precisa de data de referência a recebe como argumento;
nenhuma lê o relógio por conta própria.

O calendário da plataforma oferece semana ISO (segunda a domingo, `2026-S38`),
mês civil, a lista de períodos do início do projeto até o corrente, a marcação
de período parcial (em andamento) e o corte (fim do período, limitado à data de
referência), como o relatório gerencial do protótipo exige.

Os parâmetros configuráveis da seção 7.4 do README do protótipo passam a ser
versionados no banco: a plataforma entrega a versão vigente numa data, e a
gravação de uma nova versão (vigência, autor e justificativa obrigatória) passa
pela validação portada de `validarParametros`, uma função por regra: cadência
crescente, probabilidades crescentes, pesos que somam 100, alçadas crescentes,
faixas crescentes, prazos e metas nos intervalos da seção 7.4. A versão 1 é
semeada com os valores iniciais da tabela 7.4 e com o grupo Anexos (25 MB;
PDF, JPG, PNG, DOCX, XLSX, PPTX, DWG e ZIP). A tela de edição é da ISSUE-076.

## Critérios de aceite

- [x] Testes com data injetada cobrem semana ISO na virada de ano, período parcial e corte limitado à data de referência.
- [x] Nenhuma função de cálculo lê o relógio; uma checagem automática (teste ou porta de qualidade) garante isso.
- [x] A versão vigente dos parâmetros é lida por data, e gravar nova versão sem justificativa é recusado.
- [x] Cada regra de validação da seção 7.4 tem teste com o caso de fronteira.
- [x] A versão 1 contém todos os grupos da tabela 7.4 e o grupo Anexos.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de cálculo puro (calendário) e de fachada (parâmetros). Busca por
leitura do relógio fora da função de plataforma: nenhuma ocorrência.
`npm run verificar` passa.

## Decisões em aberto

Nenhuma.

## Notas

Fontes: `GI.regras.validarParametros` e `mock-config` do protótipo; seção 7.4
do README. O efeito "daqui em diante" (avaliação guarda os pesos, ocorrência
guarda o prazo) é regra dos módulos 03 e 07.

## Registro de execução

Data: 05/10/2026.

Feito: `api/src/core/calendario.py` é o único leitor do relógio (`today` e
`now`); semana ISO, mês civil, períodos do início do projeto até o corrente,
marcação de parcial e corte recebem a data de referência como argumento.
`api/src/modulos/configuracoes/service.py` traz o payload inicial dos 14 grupos,
a leitura da versão vigente por data (`current_version`, `current_versions`,
`current_group`, `current_parameters`), a semeadura idempotente da versão 1
(`seed_initial_parameters`) e a gravação validada com autor, vigência,
justificativa obrigatória e trilha (`save_parameter_group`).
`api/src/modulos/configuracoes/validation.py` tem uma função por regra da seção
7.4, ligada ao campo do formulário pelo registro `_RULES`. `audit.py`,
`versioning.py` e `health.py` passaram a usar o calendário. Testes em
`api/tests/plataforma/test_calendario.py` (9), `api/tests/configuracoes/test_parametros.py`
(7) e `api/tests/configuracoes/test_validacao_parametros.py` (33).

Decisões tomadas, anotadas na spec como "Decisão da execução (ISSUE-007),
pendente de revisão do dono": forma dos valores versionados no banco (folha por
linha em `parametro_valor`, `chave` com o índice das listas, `tipo`, `valor` e
`ordem`) e semeadura da versão 1 por função idempotente, chamada pela ISSUE-008.
Divergência estrutural registrada em `docs/DIVERGENCIAS-DO-PROTOTIPO.md`: o
protótipo versiona o conjunto inteiro dos parâmetros; o GestNow versiona por
grupo, conforme a decisão da ISSUE-003 (D5).

Fora desta fatia, por desenho da issue: rota, tela e exportação dos parâmetros
são da ISSUE-076; a chamada da semeadura na carga de demonstração e no preparo
de produção é da ISSUE-008.

Verificação: `api/.venv/Scripts/python.exe -m pytest` verde (49 testes novos;
suíte completa verde) e `npm run verificar` com as cinco etapas ok.
