"""A D5b em conferência (ISSUE-089): nenhum indicador derivado além das exceções.

A varredura é sobre o metadata real do SQLAlchemy — os modelos da plataforma e de
todos os módulos, como as migrações os veem. O vocabulário do indicador derivado é
o da D5b e do ``MODELO-DE-DADOS.md`` ("não são colunas": CPI, SPI, VAC, PPC, score,
severidade, projeção, desvio, taxa, aderência, índice, exposição, valor agregado e
saldo), casado por segmento do nome da coluna. Calibrado contra os modelos reais
ele alcança só colunas que são fatos com nome de indicador — a allowlist diz o
porquê de cada uma —; as exceções da D5b, que podem persistir linha de base
congelada (spec, linhas 752-762), também entram na allowlist com o porquê, e a
asserção final confere que toda entrada é uma coluna de verdade.
"""

from __future__ import annotations

from src.core import database

# O vocabulário do indicador derivado (D5b, MODELO-DE-DADOS "não são colunas").
DERIVED_INDICATOR_PATTERNS = (
    "score",
    "severidade",
    "severity",
    "cpi",
    "spi",
    "vac",
    "projecao",
    "desvio",
    "taxa",
    "aderencia",
    "ppc",
    "indice",
    "exposicao",
    "valor_agregado",
    "saldo",
)

# As exceções da D5b (spec, linhas 752-762; MODELO-DE-DADOS §Exceções da D5b):
# linha de base congelada das revisões (EAP, EAC, Curva S física, Curva S
# financeira e quantidades da produtividade), os pesos gravados na avaliação de
# contratada e o prazo vigente gravado na ocorrência HSE.
D5B_EXCEPTIONS: dict[str, str] = {
    "eac_revisao_item.base_centavos": "linha de base congelada da EAC por revisão",
    "eap_revisao_item.peso": "pesos congelados de cada pacote na revisão da EAP",
    "curva_fisica_mes.baseline_pct": "linha de base congelada da Curva S física",
    "curva_financeira_mes.planejado_centavos": ("linha de base congelada da Curva S financeira"),
    "produtividade_revisao.total": "total congelado da LB de quantidades",
    "produtividade_revisao.total_anterior": "o comparativo congelado da revisão da LB",
    "produtividade_distribuicao.previsto": (
        "distribuição semanal congelada dentro da revisão da LB"
    ),
    "contrato_avaliacao_criterio.peso": "pesos gravados na avaliação de contratada",
    "ocorrencia.prazo_comunicacao_horas": "prazo vigente gravado na ocorrência HSE",
    "ocorrencia.prazo_investigacao_horas": "prazo vigente gravado na ocorrência HSE",
    "ocorrencia.prazo_relatorio_dias": "prazo vigente gravado na ocorrência HSE",
}

# As colunas que o vocabulário alcança e que são fatos com nome de indicador: não
# são indicador derivado persistido e ficam na allowlist para a varredura seguir
# honesta (se o nome de uma delas mudar para um indicador de verdade, a asserção
# de igualdade abaixo quebra e a entrada tem de ser revista).
FACT_NAME_COLLISIONS: dict[str, str] = {
    "custo_erp.projecao_centavos": (
        "a projeção é o fato importado do ERP (como o comprometido e o realizado "
        "da mesma tabela); a projeção no término do mapa é calculada na leitura"
    ),
    "ocorrencia.severidade_ambiental": (
        "classificação tipada da ocorrência ambiental (fato do evento); a "
        "severidade da matriz de risco é calculada"
    ),
    "lookahead_semana.indice": "o ordinal da semana no 6WLA, não um indicador",
    "produtividade_item.indice_hh": (
        "o índice HH do item é a entrada do plano de quantidades (fato da LB)"
    ),
    "programacao_configuracao.meta_aderencia": "a meta configurada do projeto",
    "programacao_configuracao.meta_ppc": "a meta configurada do projeto",
    "programacao_configuracao.exige_justificativa_desvio": (
        "a regra booleana da configuração, não o desvio calculado"
    ),
    "programacao_configuracao.limite_desvio_justificativa": (
        "a tolerância configurada da justificativa de desvio"
    ),
    "rnc.severidade": (
        "a severidade escolhida no fluxo da RNC (fato tipado); a crítica é calculada na leitura"
    ),
    "risco.severidade_alvo": (
        "o alvo do plano de resposta (decisão do Gestor); o score e a severidade "
        "do risco são calculados da avaliação vigente"
    ),
    "risco_revisao.score_de": (
        "o score de partida da revisão periódica, gravado como fato datado da "
        "linha do tempo (o risco não tem coluna de score)"
    ),
    "risco_revisao.score_para": (
        "o score de chegada da revisão periódica, gravado como fato datado da "
        "linha do tempo (o risco não tem coluna de score)"
    ),
}


def _matches(column_name: str) -> tuple[str, ...]:
    """Os padrões do vocabulário que o nome da coluna casa, por segmento."""
    segments = column_name.split("_")
    return tuple(pattern for pattern in DERIVED_INDICATOR_PATTERNS if pattern in segments)


def _all_columns() -> dict[str, tuple[str, ...]]:
    """Cada ``tabela.coluna`` do metadata com os padrões que ela casa."""
    database.import_all_models()
    found: dict[str, tuple[str, ...]] = {}
    for table in database.Base.metadata.tables.values():
        for column in table.columns:
            hits = _matches(column.name)
            if hits:
                found[f"{table.name}.{column.name}"] = hits
    return found


def test_nenhum_indicador_derivado_vira_coluna_alem_das_excecoes() -> None:
    flagged = _all_columns()

    assert set(flagged) == set(FACT_NAME_COLLISIONS), (
        "toda coluna alcancada pelo vocabulario e um fato com nome de indicador "
        "e esta na allowlist com o porque"
    )

    allowed = {**D5B_EXCEPTIONS, **FACT_NAME_COLLISIONS}
    assert set(flagged) <= set(allowed), "nenhum indicador derivado fora das excecoes"

    all_columns = {
        f"{table.name}.{column.name}"
        for table in database.Base.metadata.tables.values()
        for column in table.columns
    }
    assert set(allowed) <= all_columns, "a allowlist so lista colunas de verdade"
