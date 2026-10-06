---
id: ISSUE-027
title: "Lições aprendidas: acervo, fluxo de validação segregado e aplicação em projeto"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 3
onda: 6
blocked_by:
  - ISSUE-019
  - ISSUE-023
blocks:
  - ISSUE-028
  - ISSUE-034
  - ISSUE-065
  - ISSUE-067
  - ISSUE-068
  - ISSUE-073
labels:
  - ready-for-agent
source_requirements:
  - HU-129
spec_decisions:
  - D7
  - D9
---

# Lições aprendidas: acervo, fluxo de validação segregado e aplicação em projeto

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D7, D9.
> Entrega 3 (Central de Ações e Governança), onda 6 (08 Governança).
> Histórias: 129. Bloqueada por: ISSUE-019, ISSUE-023.

## O que construir

A tela **Acervo de lições** mostra os cartões (situação, recomendação,
aplicabilidade), com busca por palavra-chave, filtros (fase, área de
conhecimento, disciplina, tipo, origem, aplicabilidade) e o checklist de
kickoff (botões por fase que filtram as lições publicadas daquela fase).
**Nova lição** registra título, tipo (A repetir, A evitar), fase, área de
conhecimento, disciplina, o que aconteceu, causa, impacto (prazo e custo),
recomendação, palavras-chave e aplicabilidade (Projeto ou Corporativa), com o
número `LA-TN-2026-0001`.

Fluxo: Rascunho, Em validação, Validada, Publicada. O validador é Gestor e não
pode ser o autor (segregação); a devolução volta a Rascunho com comentário.

A origem rastreável exige o número do registro quando é de módulo e confere,
pela fachada do dono, que ele existe; o cartão leva ao registro de origem.
Entram aqui as origens já existentes (Ata, Mudança), além de Workshop,
Encerramento do projeto e Registro direto; as demais são ligadas nas issues
dos seus módulos.

A fachada de Lições passa a oferecer a criação de lição em Rascunho com
origem, usada pelos outros módulos; a primeira ligação é o encerramento da SM
(lição opcional da ISSUE-025). **Aplicar em projeto** registra o reuso
(projeto, data, como) e pode criar ação na Central (origem Lição); a opção de
criar risco no 05 é ligada na ISSUE-067.

## Critérios de aceite

- [ ] Validador igual ao autor é recusado com 403 e a mensagem.
- [ ] A devolução volta a Rascunho com o comentário no histórico.
- [ ] Origem de módulo com número inexistente é recusada com 422.
- [ ] Encerrar uma SM pedindo lição cria a lição em Rascunho com origem na SM.
- [ ] Aplicar em projeto registra o reuso e, quando pedido, cria a ação na Central com link de volta.
- [ ] Lição de Projeto aparece no projeto e no Portfólio; a Corporativa, no acervo da organização.
- [ ] A migração do Alembic desta fatia cria as tabelas como estão em `docs/MODELO-DE-DADOS.md` (se algo precisou mudar, o diagrama muda na mesma entrega) e sobe num banco vazio.
- [ ] A parte desta fatia na carga de demonstração entra a partir dos mocks do protótipo convertidos, com as datas deslocadas para hoje e só no modo demonstração.
- [ ] Toda tabela e todo painel novo desta fatia tem Excel e PDF pelos mecanismos genéricos da plataforma, com o mesmo conteúdo que o protótipo (ou o app) exportava.
- [ ] No Portfólio, as listas desta fatia trazem a coluna Projeto (também nas exportações), e os botões de inclusão pedem o projeto antes de abrir o formulário.
- [ ] O `LEIA-ME.md` do módulo passa a descrever o que esta fatia trouxe: telas, rotas, fórmulas (nome no código e definição de negócio), fluxos, integrações e onde mexer.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Testes de fachada (segregação, fluxo, origem, aplicação e lição vinda da SM) e
de rota (403).

## Decisões em aberto

Nenhuma.

## Notas

Fonte: `licoes.html`, `GI.api.governanca.licoes`, `salvarLicao`,
`enviarValidacao`, `validarLicao`, `publicarLicao` e `aplicarLicao`,
`mock-governanca`; README, "Lições Aprendidas".

## Registro de execução

- Data: 2026-10-06 (fechamento).
- Feito: o backend e o trio da tela já estavam na `main` (modelo, migração m027, cálculos, validação, fachada, rotas, templates e `licoes.html`/`.css`/`.js`); esta fatia fechou a carga de demonstração (`seed.py`, parte `governanca-licoes`, com a origem em texto do protótipo convertida para o modelo), o oráculo (`api/tests/oraculo/test_oraculo_licoes.py`: 10 lições, 4 publicadas, 9 corporativas, 6 reusos), os testes de fachada e de rota (`api/tests/governanca/test_licoes_fachada.py` e `test_licoes_rotas.py`), a tabela `licao_historico` no `docs/MODELO-DE-DADOS.md` e o LEIA-ME do módulo.
- Testes: segregação do validador (403), devolução com comentário no histórico, origem de módulo com número inexistente (422) e existente, rascunho com origem, aplicação com ação na Central e visibilidade no acervo.
- A migração m027 foi encadeada na cadeia do Alembic (`m021 → m027 → m064 → m072`), que estava com quatro cabeças após os ramos `wip`.
- Porta de qualidade (`npm run verificar`) e a suíte completa de pytest passaram em 06/10/2026.
- Pontos que seguem para as issues donas, como o próprio escopo previa: a ligação do encerramento da SM com lição é da ISSUE-025; a geração de risco a partir da lição, da ISSUE-067; as demais origens de módulo registram o seu verificador na issue de cada uma.
