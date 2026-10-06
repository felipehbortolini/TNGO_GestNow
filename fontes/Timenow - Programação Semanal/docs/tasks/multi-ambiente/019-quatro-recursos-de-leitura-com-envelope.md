---
id: ISSUE-019
title: Os quatro recursos de leitura em JSON, com envelope e semana obrigatória
status: done
type: task
parent: docs/PLANO-MULTI-AMBIENTE.md
spec: docs/SPEC-MULTI-AMBIENTE.md
entrega: 3
blocked_by:
  - ISSUE-018
blocks:
  - ISSUE-022
  - ISSUE-026
labels:
  - ready-for-agent
source_requirements:
  - HU-46
  - HU-53
  - HU-54
  - HU-55
  - HU-56
  - HU-57
  - HU-60
  - HU-61
  - HU-63
plan_tasks:
  - E3.4
  - E3.5
  - E3.9 (parcial)
spec_decisions:
  - 22
  - 23
  - 26
---

# Os quatro recursos de leitura em JSON, com envelope e semana obrigatória

## O que construir

O contrato de leitura da API, em quatro recursos:

| Recurso | O que devolve | Filtros |
|---|---|---|
| Ambiente | A identificação do ambiente do token e a semana de referência | — |
| Atividades da semana | Item, ID exclusiva, atividade, local, empresa, encarregado, fiscal, unidade, previsto por dia, realizado por dia e noite, situação, aprovação do realizado e PPC | semana (**obrigatória**), empresa, local, situação |
| Resumo da semana | Aderência, PPC médio, totais de previsto e realizado e as faixas | semana (obrigatória) |
| Cadastros | Locais, empresas e unidades do ambiente | — |

A semana é **obrigatória** nas atividades por decisão: sem ela, uma requisição
puxaria a base inteira do cliente. É também o teto de volume que torna
desnecessário limitar requisição.

Os números vêm da facade de domínio que já existe. **A API não reimplementa
cálculo nenhum** — aderência, PPC e avanço continuam tendo uma implementação
só.

A unidade de medida vai junto de cada atividade, porque unidades não são
somáveis entre si e o consumidor precisa saber o que está agregando.

Toda resposta — inclusive as de recurso vazio — vem dentro do mesmo envelope
fino, com a identificação do ambiente e o momento em que foi gerada:

```json
{
  "ambiente": { "id": "...", "projeto": "...", "cliente": "..." },
  "gerado_em": "2026-08-25T14:03:00Z",
  "dados": []
}
```

O envelope atende a conferência de origem sem repetir o identificador em cada
linha, e deixa lugar para paginação e avisos futuros sem quebrar o contrato.
Pôr o ambiente num cabeçalho HTTP cumpriria isso no papel e não na prática: o
conector padrão da ferramenta de painel descarta cabeçalho.

Campo novo não quebra o contrato e não muda a versão; remover ou renomear campo
exige versão nova no caminho.

**Somente leitura.** Nenhuma rota de escrita existe no espaço de nomes — a
escrita continua passando pelo fluxo com janela, validação e aprovação.

## Critérios de aceite

- [x] Os quatro recursos respondem com token válido, no ambiente do token.
- [x] Pedir atividades **sem semana** é recusado com motivo legível.
- [x] Os filtros de empresa, local e situação restringem o resultado.
- [x] Cada atividade traz a unidade de medida.
- [x] O resumo traz aderência, PPC médio, totais e faixas, com os mesmos
      números que a tela mostra para a mesma semana.
- [x] Os cadastros trazem locais, empresas e unidades do ambiente do token.
- [x] As quatro respostas trazem o envelope com identificação do ambiente e
      momento de geração.
- [x] O momento de geração é ISO em UTC.
- [x] Nenhuma resposta de erro devolve HTML.
- [x] **Nenhum verbo de escrita está registrado no espaço de nomes** —
      afirmado varrendo os métodos registrados, não conferindo à mão.
- [x] Nenhum cálculo de domínio é reimplementado na camada da API.

## Verificação

Testes por recurso: resposta com token válido, envelope presente, semana
obrigatória, filtros restringindo e unidade presente em cada atividade.

Teste de varredura afirmando que nenhum verbo de escrita existe no espaço de
nomes.

Comparação de um resumo devolvido pela API com o resumo da mesma semana na
tela — os números precisam ser os mesmos.

A porta de qualidade das cinco etapas passa.

## Decisões humanas em aberto

Nenhuma.

## Notas

O consumidor paga um passo de expansão do envelope na ferramenta de painel — um
passo, não um obstáculo.

Escrita pela API, escopo por empresa e webhook de saída estão fora do escopo
desta entrega.
