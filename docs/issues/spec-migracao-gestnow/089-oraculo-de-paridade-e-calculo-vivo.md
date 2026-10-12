---
id: ISSUE-089
title: "Oráculo de paridade completo e prova do cálculo vivo"
status: proposed
type: task
parent: docs/SPEC-MIGRACAO-GESTNOW.md
entrega: 9
onda: 19
blocked_by:
  - ISSUE-088
blocks:
  - ISSUE-090
labels:
  - ready-for-agent
source_requirements:
  - HU-022
  - HU-023
  - HU-156
spec_decisions:
  - D6
  - D5b
---

# Oráculo de paridade completo e prova do cálculo vivo

> Spec: [SPEC-MIGRACAO-GESTNOW.md](../../SPEC-MIGRACAO-GESTNOW.md), decisões D6, D5b.
> Entrega 9 (Produto final), onda 19 (Validação final e Azure).
> Histórias: 22, 23, 156. Bloqueada por: ISSUE-088.

## O que construir

O **teste-oráculo** é consolidado num teste só: carregada a demonstração com a
data injetada em 25/09/2026, os números conhecidos do protótipo saem iguais
(BAC R$ 44,6 mi, CPI 0,96, SPI 0,94, projeção R$ 45,26 mi, 8 ações atrasadas,
3 pedidos críticos, 2 riscos críticos, 4 RNC abertas, 263 dias sem
afastamento, pirâmide 0/16/31/190/1.240, aderência 92,9%, OTD 66,7%, pesos
55,36/29,34/15,30 e exposição R$ 3,4 mi), reunindo as afirmações que cada issue
de módulo já fez.

O teste de **cálculo vivo**: o mesmo cenário com a data de hoje produz atrasos
e dias sem afastamento diferentes, e uma medição nova muda o SPI na consulta
seguinte, sem nenhum passo de recálculo.

**Divergências** (decisão Q31): toda diferença encontrada na execução está em
`docs/DIVERGENCIAS-DO-PROTOTIPO.md`, com regra, número do protótipo, número
correto, motivo e situação "pendente de aceite". Erro de fórmula do protótipo:
o GestNow reproduz o número do protótipo e o teste afirma esse número, citando
a divergência. Diferença causada por decisão já tomada na spec (como a EAP
fonte única, Q3): o GestNow segue a spec, e o teste afirma o número do GestNow
citando a divergência.

Uma checagem confirma que nenhum indicador derivado é persistido além das
exceções da D5b.

## Critérios de aceite

- [ ] O oráculo completo passa num banco recém-carregado.
- [ ] O teste de cálculo vivo passa sem nenhum passo de recálculo.
- [ ] Toda diferença tem linha em `docs/DIVERGENCIAS-DO-PROTOTIPO.md`, com a situação, e o teste cita a divergência.
- [ ] Nenhuma coluna de indicador derivado fora das exceções da D5b.
- [ ] A porta de qualidade (`npm run verificar`) passa sem nenhuma regra desligada.

## Verificação

Rodar o oráculo e o teste de cálculo vivo isoladamente e na suíte; `npm run verificar` passa.

## Decisões em aberto

Nenhuma. A política de divergências foi decidida na Q31: mantém o número do protótipo e registra como pendente.

## Notas

Testing Decisions da spec: "Oráculo de paridade com o protótipo" e "Cálculo vivo".

## Registro de execução

Fatia entregue em 11/10/2026: o oráculo consolidado ganhou a **manchete** e as checagens
transversais. A afirmação nova `manchete: os numeros do cenario do HANDOVER` (registrada via
`register_check`, roda no `test_oraculo_com_a_data_25_09_2026`) reúne os números da issue pelas
fachadas donas, no cenário da âncora: BAC 4.460.000.000, CPI 0,96, SPI de custo 0,94, projeção
4.525.500.000 centavos (= R$ 45,26 mi com o arredondamento de duas casas do oráculo da 031 —
o literal "4.526.000.000" do enunciado era o arredondamento apresentado, não a soma), 8 ações
atrasadas, 3 pedidos críticos, 2 riscos críticos, 4 RNC abertas, 263 dias sem afastamento,
pirâmide 0/16/31/190/1.240, aderência 92,9%, OTD 66,7%, pesos 55,36/29,34/15,30 e exposição
R$ 3,4 mi. **Nenhum desses números divergiu do protótipo** e nenhuma divergência nova apareceu
na consolidação. O **cálculo vivo** (`test_calculo_vivo.py`): a demonstração ancorada é lida com
o relógio de hoje da plataforma (`calendario.today()`, fuso `America/Sao_Paulo`) e os atrasos e
os dias sem afastamento diferem da âncora — o deslocamento puro da carga preservaria os números,
então a leitura é do cenário ancorado com a data de hoje, que é a leitura do app; e uma **medição
nova** num pacote da EAP (pela fachada do Planejamento, na mesma transação) muda o SPI na leitura
seguinte, sem nenhum passo de recálculo. A checagem da **D5b**
(`test_sem_indicador_persistido.py`) varre o metadata real do SQLAlchemy por segmento de nome com
o vocabulário do indicador derivado (score, severidade, CPI, SPI, VAC, projeção, desvio, taxa,
aderência, PPC, índice, exposição, valor agregado e saldo) e usa allowlist com as exceções da
D5b (linhas de base congeladas, pesos da avaliação e prazos da ocorrência) e com as colisões que
são fatos com nome de indicador (`risco_revisao.score_de/para`, `custo_erp.projecao_centavos`,
`rnc.severidade`, metas da configuração da programação etc.), cada uma com o porquê; a asserção
de igualdade faz uma coluna nova com nome de indicador quebrar o teste. O teste das
**divergências** (`test_divergencias_registradas.py`) lê `docs/DIVERGENCIAS-DO-PROTOTIPO.md` e
confere as cinco colunas da tabela com a situação preenchida, o Histórico com a issue citada
existindo no `index.md` e as contagens mínimas (82 linhas principais e 40 do Histórico).
**Testes**: o oráculo isolado passa (6 testes em 24 s); o escopo do subagente (oráculo +
plataforma) rodou duas vezes com **996 passed**; o principal rodou a **suíte completa (4.095
passed**, 19:35) e a porta de qualidade (**5/5**).

- DECISAO: manchete consolidada | uma afirmação registrada reúne os números da issue pelas fachadas donas; a projeção é 4.525.500.000 centavos (R$ 45,26 mi arredondado, como o protótipo e o oráculo da 031) | ISSUE-031, ISSUE-089
- DECISAO: cálculo vivo | a demonstração ancorada é lida com o relógio de hoje (o deslocamento puro da carga preserva os números da âncora); a medição nova muda o SPI na leitura seguinte, sem passo de recálculo | D6, ISSUE-089
- DECISAO: D5b | a checagem varre o metadata real por segmento de nome e usa allowlist com as exceções da D5b e as colisões que são fatos | D5b, ISSUE-089
- DECISAO: divergências | o teste confere a forma da tabela e do Histórico e que toda issue citada existe no index; nenhuma divergência nova apareceu na consolidação | Q31, ISSUE-089
