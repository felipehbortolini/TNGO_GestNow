"""Deterministic first load — what the folder shows before anyone types.

An empty application cannot be evaluated: no chart has a shape, no filter
has anything to filter, and nobody can tell whether the screen works. So
the first run writes a believable week history to ``data/``.

Deterministic on purpose — same day, same numbers — so a screenshot taken
today still matches the screen tomorrow, and so the tests can assert on
real values instead of on "something".

The history is anchored on the **current** ISO week, not on a fixed date:
the demonstration is always about this week, never about a week that has
already passed into irrelevance.

Wiping ``data/programacao.json`` regenerates everything.
"""

import random
import re
import unicodedata

from src.core import calculos, semanas

SEMANAS_DE_HISTORICO = 6
SEMANAS_ADIANTE = 2

LOCAIS = [
    "Potato Storage 1",
    "Potato Storage 2",
    "Potato Storage 3",
    "Prédio de Produção",
    "Subestação",
    "Base Caldeira",
]

EMPRESAS = ["M. Roscoe", "Bremmer", "Elmec Montagens"]

UNIDADES = ["kg", "m²", "m³", "m", "und", "h"]

FISCAIS = ["Ricardo Alves", "Patrícia Nunes", "Marcos Duarte"]

ENCARREGADOS = [
    "Antônio M. Inocêncio",
    "José Santos",
    "Carlos Lima",
    "Maria Fernanda",
    "Paulo Rocha",
]

COLABORADORES = [
    {
        "id": "col-admin",
        "nome": "Gestão Timenow",
        "email": "admin@timenow.com.br",
        "perfil": "admin",
        "vinculo": "timenow",
        "empresa": "",
        "cargo": "Coordenação de planejamento",
        "ativo": True,
    },
    {
        "id": "col-planejador",
        "nome": "Planejamento Timenow",
        "email": "planejador@timenow.com.br",
        "perfil": "planejador",
        "vinculo": "timenow",
        "empresa": "",
        "cargo": "Planejador de obra",
        "ativo": True,
    },
    {
        "id": "col-fiscal",
        "nome": "Ricardo Alves",
        "email": "fiscal@timenow.com.br",
        "perfil": "fiscal",
        "vinculo": "timenow",
        "empresa": "",
        "cargo": "Fiscal de campo",
        "ativo": True,
    },
    {
        "id": "col-cliente",
        "nome": "Visualizador Cliente",
        "email": "visualizador@cliente.demo",
        "perfil": "visualizador",
        "vinculo": "cliente",
        "empresa": "",
        "cargo": "Acompanhamento do contrato",
        "ativo": True,
    },
    {
        "id": "col-mroscoe",
        "nome": "Programação M. Roscoe",
        "email": "programacao@mroscoe.com.br",
        "perfil": "fornecedor",
        "vinculo": "fornecedor",
        "empresa": "M. Roscoe",
        "cargo": "Planejamento da contratada",
        "ativo": True,
    },
    {
        "id": "col-bremmer",
        "nome": "Programação Bremmer",
        "email": "programacao@bremmer.com.br",
        "perfil": "fornecedor",
        "vinculo": "fornecedor",
        "empresa": "Bremmer",
        "cargo": "Planejamento da contratada",
        "ativo": True,
    },
    {
        "id": "col-elmec",
        "nome": "Programação Elmec",
        "email": "programacao@elmec.com.br",
        "perfil": "fornecedor",
        "vinculo": "fornecedor",
        "empresa": "Elmec Montagens",
        "cargo": "Planejamento da contratada",
        "ativo": True,
    },
]


def _slug(nome: str) -> str:
    """`Antônio M. Inocêncio` → `antonio.m.inocencio`, para montar e-mail."""
    limpo = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return ".".join(p for p in re.split(r"[^A-Za-z0-9]+", limpo.lower()) if p)


def _pessoas_de_campo() -> list[dict]:
    """Fiscais e encarregados como colaboradores, que é o que eles são.

    A demonstração precisa que os nomes usados nas atividades existam:
    a validação da atividade confere o fiscal e o encarregado contra o
    cadastro de pessoas, e um nome sem pessoa correspondente reprovaria
    a própria carga inicial.

    O fiscal Ricardo Alves já está em COLABORADORES com e-mail Timenow —
    ele é pulado aqui para não nascer duas vezes.
    """
    ja_existem = {c["nome"] for c in COLABORADORES}
    pessoas = []
    for nome in FISCAIS:
        if nome in ja_existem:
            continue
        pessoas.append(
            {
                "id": f"col-fis-{_slug(nome)}",
                "nome": nome,
                "email": f"{_slug(nome)}@timenow.com.br",
                "perfil": "fiscal",
                "vinculo": "timenow",
                "empresa": "",
                "cargo": "Fiscal de campo",
                "ativo": True,
            }
        )
    for indice, nome in enumerate(ENCARREGADOS):
        empresa = EMPRESAS[indice % len(EMPRESAS)]
        pessoas.append(
            {
                "id": f"col-enc-{_slug(nome)}",
                "nome": nome,
                "email": f"{_slug(nome)}@{_slug(empresa).replace('.', '')}.com.br",
                "perfil": "encarregado",
                "vinculo": "fornecedor",
                "empresa": empresa,
                "cargo": "Encarregado de frente",
                "ativo": True,
            }
        )
    return pessoas


MODELOS = [
    (
        "PS1-ARM-014",
        "Armação das paredes eixo 1 a 10",
        "Potato Storage 1",
        "M. Roscoe",
        "kg",
        1001.4,
    ),
    (
        "PS1-FOR-007",
        "Forma das lajes de piso do bloco B",
        "Potato Storage 1",
        "M. Roscoe",
        "m²",
        850.0,
    ),
    (
        "PS1-CON-021",
        "Concretagem da fundação do eixo 4",
        "Potato Storage 1",
        "M. Roscoe",
        "m³",
        120.0,
    ),
    (
        "PS2-EST-003",
        "Montagem da estrutura metálica da cobertura",
        "Potato Storage 2",
        "M. Roscoe",
        "kg",
        2400.0,
    ),
    ("PS2-PIN-011", "Pintura dos painéis externos", "Potato Storage 2", "M. Roscoe", "m²", 620.0),
    (
        "PS3-MOV-009",
        "Movimentação de solo no pátio oeste",
        "Potato Storage 3",
        "Elmec Montagens",
        "m³",
        3500.0,
    ),
    (
        "PRD-PAV-002",
        "Assentamento de piso industrial",
        "Prédio de Produção",
        "Bremmer",
        "m²",
        480.0,
    ),
    (
        "PRD-ELT-015",
        "Infraestrutura elétrica do prédio principal",
        "Prédio de Produção",
        "Bremmer",
        "m",
        300.0,
    ),
    ("SUB-CAB-006", "Cabeamento de média tensão", "Subestação", "Bremmer", "m", 1500.0),
    ("SUB-TRF-010", "Montagem do transformador de 5 MVA", "Subestação", "Bremmer", "und", 2.0),
    (
        "CAL-TUB-012",
        "Tubulação de vapor da linha 1",
        "Base Caldeira",
        "Elmec Montagens",
        "m",
        900.0,
    ),
    (
        "CAL-ISO-018",
        "Isolamento térmico das caldeiras",
        "Base Caldeira",
        "Elmec Montagens",
        "m²",
        260.0,
    ),
]

# Curva de produção da semana: mais carga no começo, folga no fim de semana.
PESOS_DIA = (0.18, 0.17, 0.17, 0.16, 0.15, 0.11, 0.06)

# Cada contratada tem um comportamento próprio, senão os gráficos ficam
# com três linhas sobrepostas e o dashboard não mostra nada.
VIES_EMPRESA = {"M. Roscoe": 0.07, "Bremmer": 0.0, "Elmec Montagens": -0.09}


def _distribuir(total: float) -> list[float]:
    """Split a weekly total across the seven days, preserving the sum."""
    valores = [round(total * peso, 1) for peso in PESOS_DIA]
    valores[-1] = round(valores[-1] + (total - sum(valores)), 1)
    return valores


def _taxa(indice: int, empresa: str) -> float:
    """Realisation rate that improves week over week."""
    base = 0.46 + 0.055 * indice
    return round(max(0.25, min(0.98, base + VIES_EMPRESA.get(empresa, 0.0))), 3)


def _situacao(indice: int, posicao: int, total_semanas: int, *, futura: bool) -> tuple[str, str]:
    """Where each activity sits in the flow, by how old its week is."""
    if futura:
        return "em_elaboracao", "pendente"
    if indice < total_semanas - 2:
        return "publicada", "aprovado"
    if indice == total_semanas - 2:
        return ("validada", "aprovado") if posicao % 3 else ("validada", "pendente")
    return ("validada", "pendente") if posicao % 2 else ("em_elaboracao", "pendente")


def _atividades_da_semana(semana: str, indice: int, total: int, *, futura: bool) -> list[dict]:
    sorteio = random.Random(f"{semana}|programacao-semanal")  # noqa: S311
    modelos = list(MODELOS)
    sorteio.shuffle(modelos)
    quantidade = 9 if futura else len(modelos)

    atividades = []
    for posicao, modelo in enumerate(modelos[:quantidade], start=1):
        id_exclusiva, descricao, local, empresa, unidade, prevista_base = modelo
        situacao, aprovacao = _situacao(indice, posicao, total, futura=futura)

        # A carga da semana varia: obra não programa a mesma quantidade
        # toda semana, e uma curva de plano perfeitamente reta faria o
        # gráfico parecer quebrado quando ele está certo.
        prevista = round(prevista_base * sorteio.uniform(0.65, 1.35), 1)
        dias_previsto = _distribuir(prevista)
        dias_dia: list[float] = []
        dias_noite: list[float] = []

        if situacao == "em_elaboracao" and futura:
            dias_dia = [0.0] * 7
            dias_noite = [0.0] * 7
        else:
            taxa = round(
                max(0.2, min(1.05, _taxa(indice, empresa) + sorteio.uniform(-0.05, 0.05))),
                3,
            )
            # Turno noite não é todo dia: a obra o abre em dois ou três
            # dias da semana, quando a frente atrasa. Sortear um turno
            # noturno para os sete dias encheria a matriz de marcadores
            # "N" e faria o marcador deixar de significar alguma coisa.
            noites = set(sorteio.sample(range(5), sorteio.choice([0, 1, 2, 3])))
            for dia, previsto in enumerate(dias_previsto):
                # O domingo raramente produz: manter isso deixa o heatmap
                # com a cara de uma obra real, e não de ruído uniforme.
                fator = taxa * (0.25 if dia == 6 else 1.0)
                realizado = round(previsto * fator, 1)
                noite = round(realizado * sorteio.uniform(0.2, 0.4), 1) if dia in noites else 0.0
                dias_dia.append(round(realizado - noite, 1))
                dias_noite.append(noite)

        atividade = {
            "key": f"{semana.replace('/', '-')}::{id_exclusiva}",
            "item": posicao,
            "semana": semana,
            "id_exclusiva": id_exclusiva,
            "atividade": descricao,
            "local": local,
            "empresa": empresa,
            "responsavel": sorteio.choice(FISCAIS) if situacao != "em_elaboracao" else "",
            "encarregado": sorteio.choice(ENCARREGADOS),
            "prod_prevista": prevista,
            "unidade": unidade,
            "dias_previsto": dias_previsto,
            "dias_realizado": dias_dia,
            "dias_noite": dias_noite,
            "situacao": situacao,
            "aprovacao_realizado": aprovacao,
            "observacoes_fornecedor": "",
            "comentarios_timenow": "",
            "criado_em": f"{semanas.inicio(semana)}T08:00:00+00:00",
            "criado_por": f"programacao@{empresa.split()[0].lower()}.com.br",
            "atualizado_em": f"{semanas.fim(semana)}T18:00:00+00:00",
            "atualizado_por": "",
        }
        calculos.preencher_calculados(atividade)
        atividades.append(atividade)
    return atividades


def _janelas(horizonte: list[str], semana_atual: str) -> list[dict]:
    liberadas = [s for s in horizonte if semanas.ordem(s) >= semanas.ordem(semana_atual)]
    return [
        {
            "empresa": "M. Roscoe",
            "dias": [{"dia": "sex", "abre": "00:01", "fecha": "23:59"}],
            "semanas_liberadas": liberadas,
            "extra": [],
        },
        {
            "empresa": "Bremmer",
            "dias": [{"dia": "qui", "abre": "08:00", "fecha": "18:00"}],
            "semanas_liberadas": liberadas,
            "extra": [],
        },
        {
            "empresa": "Elmec Montagens",
            "dias": [{"dia": "ter", "abre": "07:00", "fecha": "17:00"}],
            "semanas_liberadas": liberadas[:2],
            "extra": [],
        },
    ]


def gerar() -> dict:
    """The whole first load, ready to be written to disk."""
    semana_atual = semanas.atual()
    horizonte = semanas.janela_de_semanas(
        semana_atual, atras=SEMANAS_DE_HISTORICO - 1, adiante=SEMANAS_ADIANTE
    )
    passadas = horizonte[:SEMANAS_DE_HISTORICO]
    futuras = horizonte[SEMANAS_DE_HISTORICO:]

    atividades: dict[str, dict] = {}
    itens_por_semana: dict[str, int] = {}

    for indice, semana in enumerate(passadas):
        for atividade in _atividades_da_semana(semana, indice, len(passadas), futura=False):
            atividades[atividade["key"]] = atividade
            itens_por_semana[semana] = max(itens_por_semana.get(semana, 0), atividade["item"])

    for semana in futuras:
        for atividade in _atividades_da_semana(semana, len(passadas), len(passadas), futura=True):
            atividades[atividade["key"]] = atividade
            itens_por_semana[semana] = max(itens_por_semana.get(semana, 0), atividade["item"])

    return {
        "atividades": atividades,
        "janelas": _janelas(horizonte, semana_atual),
        "colaboradores": [dict(c) for c in COLABORADORES + _pessoas_de_campo()],
        "solicitacoes": [],
        "cadastros": {
            "locais": list(LOCAIS),
            "empresas": list(EMPRESAS),
            "unidades": list(UNIDADES),
        },
        "parametros": {
            "meta_aderencia": 60.0,
            "meta_ppc": 75.0,
            "semana_referencia": "",
            "exige_justificativa_desvio": True,
            "limite_desvio_justificativa": 15.0,
        },
        "sequencia": 1000,
        "itens_por_semana": itens_por_semana,
    }
