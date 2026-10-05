# Divergências entre o GestNow e o protótipo

> Registro exigido pela decisão D6/Q31. Cada linha traz a regra, o número do
> protótipo, o número correto do GestNow, o motivo e a situação. Enquanto a
> situação for **pendente de aceite**, o teste-oráculo afirma o número indicado
> nesta tabela e cita a divergência; depois do aceite do dono, a linha passa a
> "aceita" e o teste afirma o número correto.
>
> Erro de fórmula do protótipo: o GestNow reproduz o número do protótipo.
> Diferença causada por decisão já tomada na spec: o GestNow segue a spec.
> Nos dois casos a divergência fica registrada aqui.

| Regra | Número do protótipo | Número correto | Motivo | Situação |
|---|---|---|---|---|
| Valores agregados do item da EAC: base, remanejamento, comprometido, realizado e projeção persistidos na linha do item. | Item `1.1.1` com base 70.000.000 centavos; item `2.1.3` com remanejamento de −15.000.000 centavos. | Os mesmos valores, calculados: base de `eac_revisao_item`, remanejamento de `eac_remanejamento`, comprometido/realizado das medições e contratos, projeção da última `eac_projecao`. | D5b grava somente fatos: indicador derivado não vira coluna. O valor lido continua o mesmo. | pendente de aceite |
| Séries da Curva S financeira: planejado, comprometido, realizado e projeção persistidos em `curvaFinanceira`. | Planejado de `2026-01` = 93.660.000 centavos; realizado de `2026-08` = 2.280.000.000 centavos. | Somente o planejado é gravado (`curva_financeira_mes`); comprometido, realizado e projeção são calculados dos fatos. | D5b: a linha de base congelada por revisão é a única exceção; as demais séries são calculadas. | pendente de aceite |
| Valor do marco de pagamento. | Marco `M1` do contrato `CT-2026-011`: 34.500.000 centavos (10% de 345.000.000). | O mesmo valor, calculado: `pct` (10) sobre o valor vigente do contrato (345.000.000). | D5b: o valor é derivado do percentual contratual; gravar seria duplicar o fato. | pendente de aceite |
| Reservas de contingência e gerencial. | Uma linha por projeto com `contingenciaCentavos` = 200.000.000, `gerencialCentavos` = 90.000.000, `constituidaEm` e `base`. | Duas reservas (uma por tipo) em `reserva`; a constituição vira o primeiro `reserva_movimento` com o mesmo valor e data. | D5: uma tabela por entidade; o saldo é a soma dos movimentos. Os valores lidos continuam os mesmos. | pendente de aceite |
| Notas da ponderação da carteira. | `projetos[].ponderacao` gravada no próprio projeto (ex.: projeto 1, estratégico 5 e complexidade 5). | `portfolio_ponderacao` dentro da versão de parâmetros do grupo portfólio; a edição gera nova versão. | D8 e README 7.4: a edição da ponderação grava nova versão dos parâmetros, com justificativa. As notas e os pesos resultantes não mudam (projeto 1 = 55,36%). | pendente de aceite |
| Sessão, data de referência e escopo corrente. | `sessao`, `referencia` (25/09/2026) e `projetoAtualId` em `window.MOCK`. | Não persistidos: o modo demonstração vem do seletor de perfil, a data é a de hoje (fuso do produto) e o escopo vive na URL e no cookie (Portfólio quando ausente). | D6 (data viva) e D8 (escopo por requisição). | pendente de aceite |

## Histórico

| Data | Issue | Alteração |
|---|---|---|
| 05/10/2026 | ISSUE-003 | Registro inicial das divergências estruturais da modelagem (D5, D5b, D6, D8). |
