---
id: ISSUE-001
title: "O repositório GestNow nasce do Padrão, renomeado, com as referências preservadas e o app subindo localmente"
status: done
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 1
onda: 1
blocked_by: []
blocks:
  - ISSUE-002
labels:
  - ready-for-agent
source_requirements:
  - HU-151
  - HU-157
spec_decisions:
  - D1
  - D4
  - D15
---

# O repositório GestNow nasce do Padrão, renomeado, com as referências preservadas e o app subindo localmente

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D1, D4, D15.
> Entrega 1 (Fundação documentada), onda 1 (Repositório, estrutura e modelo de dados).
> Histórias: 151, 157. Bloqueada por: nenhuma.

## O que construir

A pasta `Timenow - GestNow` deixa de ter só a spec e passa a ser o repositório
do produto. O ponto de partida é uma **cópia** do `Padrao Desenvolvimento`
inteiro (app, api, scripts, configuração de lint, `pyproject`, skills de agente
em `.agents` e `.claude` e a documentação de padrão em `docs/`), renomeada para
GestNow conforme o passo 3 do README do Padrão: nome do pacote, títulos,
configuração do SWA CLI, `launch.json`, README e CONTEXT. A spec e a pasta
`docs/issues/` que já existem são preservadas.

O exemplo do Padrão (telas e rotas de exemplo) sai, porque o GestNow não tem
essas telas; o shell continua abrindo com a view inicial no estado vazio.

O `run.bat` segue o precedente do app de Programação Semanal: cria o ambiente
Python em `api/.venv` na primeira execução, instala as dependências e sobe o
servidor local em Python (`dev_local.py`), sem exigir o Azure Functions Core
Tools, que não está instalado nesta máquina. Ainda não há banco; o preparo do
Postgres entra na ISSUE-005.

Tudo o que as pastas de origem têm e o GestNow vai precisar como referência é
**copiado** para dentro dele agora, para que a exclusão final (ISSUE-093) não
perca nada: os 22 visuais originais de `Graficos HTML` em
`docs/referencia/graficos/`; README, HANDOVER e a pasta `_dev` do protótipo em
`docs/referencia/prototipo/`; README, CONTEXT, COMO-USAR e ENTENDA-O-SISTEMA do
app de Programação Semanal em `docs/referencia/programacao-semanal/`. Um
`LEIA-ME.md` em `docs/referencia/` diz o que é cada pasta e de onde veio.

O git local nasce aqui (decisão Q33): repositório dentro de `Timenow - GestNow`,
`.gitignore` do Padrão revisto para excluir ambiente Python, `node_modules`,
anexos locais e configuração local com segredo, e o primeiro commit com o
estado desta issue. Sem repositório remoto.

## Critérios de aceite

- [x] A pasta tem a árvore do Padrão renomeada para GestNow, sem as telas de exemplo, e a spec e `docs/issues/` intactas.
- [x] Duplo clique no `run.bat` cria o ambiente Python na primeira vez e abre o shell no navegador, com a barra lateral do Padrão e nenhum erro no console.
- [x] Os 22 visuais, o README e o HANDOVER do protótipo e os documentos do app de Programação Semanal estão em `docs/referencia/`, com o `LEIA-ME.md` que explica a origem de cada pasta.
- [x] As skills de `.agents/skills` e `.claude/skills` do Padrão estão dentro do GestNow.
- [x] O repositório git local existe, com `.gitignore` que exclui ambiente, dependências, anexos locais e configuração com segredo, e o primeiro commit foi feito.
- [x] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Dentro de `Timenow - GestNow`: `npm install` e `npm run verificar` (as etapas
da porta de qualidade passam). Rodar o `run.bat` e abrir o endereço local: o
shell abre. `git log` mostra o primeiro commit.

## Decisões em aberto

Nenhuma.

## Notas

O Padrão sobe o app pelo `swa start` com o Functions Core Tools e cai para
`dev_local.py` quando ele falta. Nesta máquina o `func` não está instalado, e
o app de Programação Semanal resolveu isso com um `run.bat` que chama
`dev_local.py` direto: siga esse precedente. Nada é apagado nem movido das
pastas de origem nesta issue: tudo é copiado.

## Registro de execução

- Decisão da execução (ISSUE-001), pendente de revisão do dono: os pacotes foram nomeados `timenow-gestnow` (npm) e `timenow-gestnow-api` (Python); a sessão demonstrativa usa `gestnow.demo@example.invalid`, sem credencial, em vez da identidade nominal do Padrão.
- Decisão da execução (ISSUE-001), pendente de revisão do dono: o servidor local mantém o bind em `127.0.0.1`; a issue pede execução local e não especifica exposição à rede.
