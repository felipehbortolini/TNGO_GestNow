# Carga de demonstração e início de produção

Esta pasta é o mecanismo de carga da plataforma (ISSUE-008, D6/Q15). O modo do
app vem da variável de ambiente `GESTNOW_MODO`:

| Modo | Valor | O que acontece |
|---|---|---|
| Demonstração (padrão local) | `demonstracao` (ou ausente) | A base nasce da conversão dos mocks do protótipo, com todas as datas deslocadas para hoje, e cada módulo registra a sua parte. |
| Produção | `producao` | A base nasce vazia: só os parâmetros iniciais e o primeiro Admin, cujo e-mail vem de `GESTNOW_ADMIN_EMAIL`. |

Valor diferente dos dois falha alto (`config.app_mode`), para uma base de
demonstração nunca subir por engano em produção. O `run.bat` chama
`scripts/seed_database.py` depois de preparar o banco; o script lê o modo e
aplica a carga numa transação, sem imprimir senha nem URL de conexão.

## Arquivos

| Arquivo | O que faz |
|---|---|
| `registro.py` | O registro das partes (`register`, `registered`) e o deslocamento de datas (`DEMO_ANCHOR`, `shift_date`): a âncora é **25/09/2026**, a data fixa do protótipo. |
| `runner.py` | `run_for_mode` decide pelo modo; `run_demonstration` roda cada parte registrada que ainda não está em `carga_demonstracao` (idempotência); `run_production` delega ao `producao.py`. |
| `plataforma.py` | A parte da plataforma: cliente, 3 projetos do portfólio e as notas da ponderação, empresas, pessoas, colaboradores de demonstração, papéis da Programação Semanal, cadastros de apoio e a versão 1 dos parâmetros. Lê `dados/plataforma.json`. |
| `producao.py` | Início de produção: cria a pessoa e o colaborador do primeiro Admin e semeia os parâmetros iniciais. Rodar de novo não duplica. |
| `prototipo.py` | `prototype_collection("acoes")`: lê qualquer coleção dos mocks do protótipo (todas, sem recorte) de `dados/prototipo.json`. É daqui que cada `seed.py` de módulo tira os dados; não precisa mexer no conversor. |
| `dados/prototipo.json` | Todas as coleções dos 11 mocks, como o protótipo as gera (`node scripts/converter_mocks.mjs`). |
| `dados/plataforma.json` | Os mocks convertidos, gerados por `scripts/converter_mocks.mjs`. É a fonte versionada dentro do GestNow; o protótipo é só leitura. |
| `api/tests/oraculo/` | O harness do teste-oráculo: carrega a demonstração com a data injetada em 25/09/2026 (sem deslocamento) e roda as afirmações de número conhecido de cada módulo. |

`carga_demonstracao` (plataforma, `src/core/models.py`) guarda uma linha por
parte já aplicada: rodar a carga de novo não duplica nada. A parte
`plataforma` roda sempre primeiro, porque os projetos e cadastros que os
módulos consomem nascem nela.

## Como um módulo registra a sua parte

Cada módulo cria `api/src/modulos/<modulo>/seed.py` com uma função que recebe
a sessão e a data de referência, e registra no import:

```python
"""Parte do módulo na carga de demonstração (ISSUE-NNN)."""

from datetime import date

from sqlalchemy.orm import Session

from src.carga import register, shift_date


def load(session: Session, reference_date: date) -> None:
    # Lê os dados convertidos da sua parte, grava com a fachada do módulo
    # e desloca cada data do protótipo com shift_date(original, reference_date).
    ...


register("central_acoes", load)
```

O runner descobre o arquivo sozinho (importa o `seed.py` de cada módulo) e
roda cada parte uma única vez. O nome registrado é o identificador do módulo
e não pode repetir. A carga inteira roda dentro da transação que o script
abriu: se uma parte falhar, nada grava e nenhuma marca fica na tabela.

## Como converter os mocks

`scripts/converter_mocks.mjs` executa os mocks do protótipo na ordem de carga
do `MODELO-DE-DADOS.md`, num `window` isolado, e grava o resultado já gerado —
inclusive o das coleções produzidas com semente fixa (jornadas, amostragens,
ocorrências). **Nunca reimplemente o gerador**: acrescente as coleções da sua
parte à seleção do script, rode-o e versione o JSON resultante. Assim os
números batem com o protótipo.

O deslocamento é feito na leitura da carga, não no JSON: `shift_date` soma a
diferença entre a data de referência da execução e a âncora 25/09/2026. O
oráculo usa a própria âncora como data de referência, então não há
deslocamento e os números do protótipo aparecem inteiros.
