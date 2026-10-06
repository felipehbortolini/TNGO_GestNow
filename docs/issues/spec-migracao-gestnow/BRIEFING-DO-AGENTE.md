# Briefing do subagente (versão rápida, padrão da execução)

> Este é o texto que o orquestrador envia a cada subagente de issue, trocando
> `NNN` pelo número da issue e informando a pasta do worktree. A velocidade é
> requisito: leia pouco, escreva direto, sem cerimônia.

Você vai implementar a ISSUE-NNN do Timenow GestNow, sozinho, sem perguntar
nada a ninguém (nunca use AskUserQuestion).

## Política de testes (decisão do dono)

**Não rode** `npm run verificar`, pytest, servidor local nem capturas de tela.
Os testes rodam só no fim de cada entrega, pelo orquestrador. Você **escreve**
o código e os testes da fatia (toda fórmula com caso de fronteira, fachada,
rota), sem rodá-los. Única checagem permitida, por ser instantânea:
`ruff format` e `ruff check` (com `--config api/pyproject.toml` quando rodar da
raiz) nos arquivos `.py` que você mexeu, usando o Python do ambiente do
projeto (`api/.venv`).

Exceção, só para issue visual (biblioteca de gráficos): **uma** captura da
página de exemplo para ver se renderiza e se há erro de console, sem iterar em
pixel.

## Onde você trabalha

- O orquestrador informa a pasta do seu **worktree**, que é a raiz do
  repositório GestNow (o produto É a raiz; onde o prompt original diz
  "Timenow - GestNow/...", leia "a raiz do worktree"). Trabalhe só ali, com
  caminhos absolutos. **Nunca** edite o checkout principal nem o worktree de
  outro agente.
- Outros agentes rodam em paralelo, cada um no seu worktree. Fique no escopo da
  sua issue. Em arquivos compartilhados (`api/function_app.py`,
  `app/index.html`, `eslint.config.mjs`, `scripts/verificar-padrao.mjs`,
  `api/pyproject.toml`, `docs/DIVERGENCIAS-DO-PROTOTIPO.md`) faça só mudanças
  mínimas e **aditivas** (acrescentar; nunca reordenar nem reformatar).
- **Git:** nada de `commit`, `stash`, `checkout`, `reset` nem `worktree`; deixe
  tudo como mudança não commitada. O orquestrador commita e integra.
- **Migração Alembic**, se a issue exigir: **uma só**, com `down_revision` igual
  à última migração do seu worktree e o próximo id numérico; informe no
  relatório (o orquestrador reencadeia se outra issue também criar migração).

## Fontes

Na raiz do repositório, **só leitura**: `fontes/Sistema/` (protótipo: `data/mock-*.js`, `js/services/{api,regras}.js`, `js/pages/<módulo>/`, `js/i18n/en.js`), `fontes/Timenow - Programação Semanal/` (código do app), `Graficos HTML/` (visuais-padrão) e as cópias em `docs/referencia/`. Regra, número e texto saem do código do protótipo do seu módulo (grep por termo, sem ler a pasta inteira). A carga (todas as coleções dos mocks já em `api/src/carga/dados/prototipo.json`, lidas por `src.carga.prototype_collection`; cada módulo só escreve o `seed.py`) e as afirmações do oráculo fazem parte da issue. Nunca invente regra, dado de demonstração nem número do oráculo.

## Leia só isto (três chamadas bastam)

1. `python scripts/execucao/contexto_da_issue.py NNN`: imprime a issue, as
   decisões da spec que ela cita, as histórias e a Definição de pronto.
   **Não leia a spec, o `index.md` nem o `MODELO-DE-DADOS.md` inteiros**: para
   o detalhe de uma tabela use
   `grep -n -A12 '`tabela`' docs/MODELO-DE-DADOS.md`; para uma regra do
   protótipo, `grep -n -i -B2 -A15 'termo' docs/referencia/prototipo/README.md`.
2. `docs/issues/spec-migracao-gestnow/GUIA-RAPIDO-DO-AGENTE.md` e a saída de
   `python scripts/execucao/gerar_api_sheet.py`: a plataforma pronta (receita
   de fatia, assinaturas do `api/src/core`, o que derruba a porta de qualidade).
3. O `LEIA-ME.md` do seu módulo e, **se for mexer em tela**, as skills
   `.agents/skills/{timenow-design-system,alpine-ajax,padrao-de-codigo}/SKILL.md`.
   Abra código existente só do que for tocar.

## Como implementar

- Exatamente o "O que construir", como fatia vertical (banco, fachada, rota,
  tela, exportação, testes, o que couber). Nada além; o Out of Scope da spec
  continua fora.
- Critérios de aceite: `[x]` quando a implementação cobre de verdade. Critério
  que depende de fonte ausente (carga dos mocks, número do oráculo, código do
  app) fica `[ ]` com nota curta no registro. O critério "A porta de qualidade
  passa" fica `[ ]`: o orquestrador o marca quando a entrega passa.
- Não altere `index.md`, nem o `status:` da issue, nem a spec, e não commite.
- Idioma: Python em inglês; interface, CSS, JS, rotas, HTML e tabelas em
  português, com acento correto. Dependência nova só de fonte oficial
  (pip/npm), registrada como o Padrão manda; prefira a biblioteca padrão.
- **Documentação, o mínimo exigido:** (a) o `## Registro de execução` no fim do
  arquivo da issue, **até 12 linhas** (Data, Feito, Pendências); (b) o
  `LEIA-ME.md` do módulo (o que a fatia trouxe: telas, rotas, fórmulas com o
  nome no código, fluxos, onde mexer); (c) `docs/MODELO-DE-DADOS.md` só se o
  modelo mudou. **Não** atualize `CONTEXT.md` (salvo termo novo de domínio),
  `MAPA-DE-MODULOS`, `ONDE-ESTA`, `COMPONENTES`, `CHECKLIST` nem `README`: o
  orquestrador consolida no fim da entrega.
- **Decisões** que a spec não cobre: escolha a mais conservadora e escreva no
  registro, uma por linha, neste formato exato (o orquestrador as leva ao
  Histórico de decisões da spec): `DECISÃO: tema | decisão | D?, ISSUE-NNN`.
  Se algo **contraria** a spec, avise no relatório final em vez de codificar.
- Divergência com o protótipo (Q31): acrescente em
  `docs/DIVERGENCIAS-DO-PROTOTIPO.md` a regra, o número do protótipo, o número
  correto, o motivo e a situação "pendente de aceite".
- Fragmento HTML sem `<link>`, `<style>` nem `<script>`; sem valor visual fixo
  fora dos tokens; sem recurso externo em `app/`.
- Pode usar até 2 subagentes para partes independentes (por exemplo backend e
  front) se acelerar; eles não editam o mesmo arquivo.

## Relatório final (até 10 linhas)

O que foi feito; arquivos principais; critérios não atendidos e por quê; as
linhas `DECISÃO:`; migração criada (arquivo e revisão); arquivos compartilhados
tocados.
