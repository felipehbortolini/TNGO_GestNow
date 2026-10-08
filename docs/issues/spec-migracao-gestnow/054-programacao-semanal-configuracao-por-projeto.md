---
id: ISSUE-054
title: "Subpágina de configuração da programação, uma por projeto"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 5
onda: 11
blocked_by:
  - ISSUE-051
blocks:
  - ISSUE-077
  - ISSUE-078
labels:
  - ready-for-agent
source_requirements:
  - HU-079
  - HU-080
  - HU-081
spec_decisions:
  - D10
  - D7
---

# Subpágina de configuração da programação, uma por projeto

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D10, D7.
> Entrega 5 (Planejamento de campo e Programação Semanal), onda 11 (02 Programação Semanal (o app existente, adaptado)).
> Histórias: 79, 80, 81. Bloqueada por: ISSUE-051.

## O que construir

Dentro do submódulo nasce a **subpágina de configuração**, uma por projeto (o
"ambiente" do app). Reúne o que o app tinha em Configurações e é da
programação: os parâmetros (limite de desvio que exige justificativa, faixas de
PPC e aderência e afins), as janelas de programação por empresa, as semanas
liberadas e as liberações extraordinárias. Cadastros de empresas e pessoas e o
de Colaboradores não ficam aqui: são os do GestNow.

Projeto novo nasce com os valores padrão do app, por uma função da fachada que
a criação de projeto (ISSUE-078) vai chamar. Edita quem tem papel de
Planejador no projeto ou é Admin; a mudança vale na hora, e a trilha guarda o
antes e o depois (sem o versionamento com justificativa dos parâmetros gerais).
No Portfólio, a subpágina só pode ser lida e pede para escolher um projeto.

## Critérios de aceite

- [x] Planejador do projeto e Admin editam; Planejador de outro projeto recebe 403.
- [x] A mudança vale na próxima requisição, e a trilha guarda antes e depois.
- [x] A função de padrões cria a configuração de um projeto novo com os valores do app.
- [x] No Portfólio, a subpágina é somente leitura e pede um projeto.
- [x] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio — **sem migração**: a `m051` já cria `programacao_configuracao` e as quatro tabelas de janela como o diagrama mostra, e a seção 8 de `docs/MODELO-DE-DADOS.md` não mudou.
- [x] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (permissão por papel no projeto, efeito imediato, padrões e trilha).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: telas de configurações do app (geral, janelas, cadastros) e o domínio de janela; D10.

## Registro de execução

Data: 2026-10-08.
Feito: `validation.py` (`ScheduleSettingsForm`, `WindowForm`, os padrões 60/75/15 que a fachada importa, `parse_settings`, `parse_window` com as `semanas` repetidas, `settings_errors`, `window_errors`, `window_of` e `merge_extras`), `service.py` (`SettingsWindow`, `ScheduleConfiguration`, `configuration_of` com o corte do fornecedor, `ensure_settings`, `save_parameters` pelo `recording` com a versão da linha, `save_window` com a substituição do conjunto e a trilha composta pelas regras — `_write_window_rules`, `_clear_window_rules`, `_window_snapshot` —, `_configuration_companies`; o `store_window` da carga passou a reusar `_write_window_rules`), `permissions.py` (`can_manage_settings`), `repository.py` (`window_row_of` e `window_of_row`; `window_of` reusa), `screen.py` (`configuration_context`, `SettingsSubmission`, `WindowSubmission`, os blocos de parâmetros e janelas, o seletor de semanas de três anos em pastilhas com trimestre), `routes.py` (`configuracao` GET, `configuracao/parametros` POST e `configuracao/janela` POST, com `config-painel`, `config-parametros` e `config-janelas`), fragmentos (`configuracao.html`, `_parametros.html`, `_janelas.html`, `parametros.html`, `janelas.html`); a tela `app/_views/programacao_semanal/configuracao.html` e o trio CSS/JS (`.cfg-*` escopadas, `marcar` do atalho de semanas); testes `test_programacao_configuracao.py` e `test_programacao_configuracao_rotas.py`; `test_programacao_rotas.py` (o `Access` das rotas novas); `tests/identidades.py` (`urlencode(corpo, doseq=True)` para as `semanas` repetidas); LEIA-ME do módulo; CONTEXT.md ("Configuração da programação"; `glossario.json` regerado sem sigla nova).
Verificação: pytest de `programacao_semanal`, `plataforma` e `configuracoes` — 1172 passaram; `ruff check`, `ruff format --check` e `ty check` verdes; `node scripts/verificar.mjs` com as cinco etapas verdes, sem regra desligada e sem `per-file-ignore` novo (o `PLR0913` do módulo já estava justificado na `routes.py`); sem migração (conferência da `m051` e da seção 8 do MODELO-DE-DADOS).
DECISÃO: forma da configuração | uma linha por projeto (`programacao_configuracao`) com os padrões do app (60/75/15) quando não existe; os parâmetros são gravados pelo `recording` (versão da linha, 409) e a trilha guarda antes e depois, sem o `parametro_versao` com justificativa dos parâmetros gerais | D10, D5b, ISSUE-054
DECISÃO: gravação da janela | a gravação substitui o conjunto (dias, semanas e extras), como o app salva; a linha da trilha da janela compõe o snapshot com as regras (`_window_snapshot`), porque a linha sozinha não muda; os extras entram, trocam pela mesma semana e saem pelo `remover_extra` | D10, D5b, ISSUE-054
DECISÃO: alvos e fragmentos | `config-painel` no GET e `config-parametros`/`config-janelas` nas gravações, cada formulário com o seu alvo; o 422/409 volta só o bloco recusado, com o digitado e as mensagens ao lado dos campos | D14, ISSUE-054
DECISÃO: Portfólio e fornecedor | no Portfólio a tela só pede um projeto (somente leitura) e a gravação recusa com 422; o fornecedor vê apenas a janela da própria empresa e lê os parâmetros do projeto sem editá-los | D8, D7, ISSUE-054
DECISÃO: lista de empresas e seletor de semanas | todas as empresas do cadastro, um cartão por empresa, e o seletor do app (três anos em pastilhas, com os atalhos de trimestre e de ano, via `TN.paginas[...].marcar`); sem Excel/PDF, porque a issue não pede e não há painel ou tabela a exportar | D10, D12, ISSUE-054
DECISÃO: sem migração | a `m051` já cria `programacao_configuracao` e as quatro tabelas de janela como a seção 8 do `docs/MODELO-DE-DADOS.md` mostra; o esquema não mudou | D5, ISSUE-054
DECISÃO: demonstração | a carga da 051 já grava os parâmetros (60/75/15) e as três janelas do app; o oráculo de `test_carga_demonstracao.py` não mudou | D6, D10, ISSUE-051, ISSUE-054
DECISÃO: glossário | CONTEXT.md ganhou "Configuração da programação"; `glossario.json` regerado sem sigla nova | D10, ISSUE-054
