"""Derived numbers of the weekly schedule — never typed by hand.

Total Semanal, PPC and Aderência Geral are computed by the system. The
activity carries three parallel day arrays, Monday through Sunday:

    dias_previsto:  list[float]   planned
    dias_realizado: list[float]   done, day shift
    dias_noite:     list[float]   done, night shift

Everything else in this module is a projection of those three.
"""

NUM_DIAS = 7

DIAS_ROTULO = ("2ª", "3ª", "4ª", "5ª", "6ª", "Sáb", "Dom")
DIAS_NOME = ("Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo")

# Faixas de desempenho. Uma escala só, usada pela tabela, pelos medidores e
# pelos gráficos — para a tela inteira contar a mesma história.
FAIXA_ALTA = 80.0
FAIXA_MEDIA = 60.0

SITUACOES = ("em_elaboracao", "validada", "publicada")


def numero(valor, padrao: float = 0.0) -> float:
    """Parse a number that may arrive as pt-BR text ("1.234,5")."""
    if valor is None or valor == "":
        return padrao
    if isinstance(valor, bool):
        return padrao
    if isinstance(valor, int | float):
        return float(valor)
    texto = str(valor).strip().replace(" ", "")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return padrao


def _soma(valores) -> float:
    return round(sum(numero(v) for v in (valores or [])), 2)


def sete_dias(valores=None) -> list[float]:
    """Normalise any day array to exactly seven floats."""
    lista = [numero(v) for v in (valores or [])]
    lista = lista[:NUM_DIAS]
    return lista + [0.0] * (NUM_DIAS - len(lista))


def total_previsto(atividade: dict) -> float:
    """Weekly planned total — the day array wins over the header field."""
    valores = atividade.get("dias_previsto")
    if valores:
        return _soma(valores)
    return round(numero(atividade.get("prod_prevista")), 2)


def total_realizado(atividade: dict) -> float:
    """Weekly done total — day shift plus night shift."""
    return round(_soma(atividade.get("dias_realizado")) + _soma(atividade.get("dias_noite")), 2)


def realizado_do_dia(atividade: dict, indice: int) -> float:
    """Done on a single weekday, both shifts."""
    dia = sete_dias(atividade.get("dias_realizado"))[indice]
    noite = sete_dias(atividade.get("dias_noite"))[indice]
    return round(dia + noite, 2)


def ppc(atividade: dict) -> float:
    """Percent Plan Complete of one activity (done / planned)."""
    previsto = total_previsto(atividade)
    if not previsto:
        return 0.0
    return round(total_realizado(atividade) / previsto * 100, 2)


def faixa(valor: float) -> str:
    """Performance band of a percentage: alta | media | baixa."""
    if valor >= FAIXA_ALTA:
        return "alta"
    if valor >= FAIXA_MEDIA:
        return "media"
    return "baixa"


def preencher_calculados(atividade: dict) -> dict:
    """Fill the derived fields in place and return the activity."""
    atividade["dias_previsto"] = sete_dias(atividade.get("dias_previsto"))
    atividade["dias_realizado"] = sete_dias(atividade.get("dias_realizado"))
    atividade["dias_noite"] = sete_dias(atividade.get("dias_noite"))

    previsto = total_previsto(atividade)
    if previsto == 0 and numero(atividade.get("prod_prevista")) > 0:
        previsto = round(numero(atividade["prod_prevista"]), 2)

    atividade["total_previsto"] = previsto
    atividade["total_realizado"] = total_realizado(atividade)
    atividade["ppc"] = ppc(atividade)
    atividade["faixa"] = faixa(atividade["ppc"])
    atividade["dias_total"] = [
        round(atividade["dias_realizado"][i] + atividade["dias_noite"][i], 2)
        for i in range(NUM_DIAS)
    ]
    atividade["tem_realizado"] = atividade["total_realizado"] > 0
    return atividade


# ── Indicadores consolidados ────────────────────────────────────────────


def aderencia_geral(atividades: list[dict]) -> float:
    """Sum of done over sum of planned, as a percentage."""
    previsto = sum(total_previsto(a) for a in atividades)
    if not previsto:
        return 0.0
    realizado = sum(total_realizado(a) for a in atividades)
    return round(realizado / previsto * 100, 2)


def ppc_medio(atividades: list[dict]) -> float:
    """Unweighted mean of the activity PPCs that have a plan."""
    valores = [ppc(a) for a in atividades if total_previsto(a) > 0]
    if not valores:
        return 0.0
    return round(sum(valores) / len(valores), 2)


def situacao_label(situacao: str) -> str:
    return {
        "em_elaboracao": "Em elaboração",
        "validada": "Validada",
        "publicada": "Publicada",
    }.get(situacao, situacao)


def aprovacao_label(aprovacao: str) -> str:
    return {"pendente": "Pendente", "aprovado": "Aprovado"}.get(aprovacao, aprovacao)


def quebrar_por(atividades: list[dict], campo: str) -> list[dict]:
    """Group by one field and compute the whole indicator set per group.

    Returns the groups already sorted by adherence, worst first — a
    breakdown exists to show where to act, and that is the top of the list.
    """
    grupos: dict[str, list[dict]] = {}
    for a in atividades:
        grupos.setdefault(a.get(campo) or "—", []).append(a)

    resultado = [
        {
            "chave": chave,
            "atividades": len(itens),
            "aderencia": aderencia_geral(itens),
            "ppc": ppc_medio(itens),
            "total_previsto": round(sum(total_previsto(a) for a in itens), 2),
            "total_realizado": round(sum(total_realizado(a) for a in itens), 2),
            "pendentes": sum(1 for a in itens if a.get("aprovacao_realizado") == "pendente"),
        }
        for chave, itens in grupos.items()
    ]
    resultado.sort(key=lambda g: (g["aderencia"], g["chave"]))
    return resultado


def por_dia(atividades: list[dict]) -> list[dict]:
    """Planned against done for each weekday of the selected week."""
    return [
        {
            "indice": i,
            "rotulo": DIAS_ROTULO[i],
            "nome": DIAS_NOME[i],
            "previsto": round(sum(sete_dias(a.get("dias_previsto"))[i] for a in atividades), 2),
            "realizado": round(sum(realizado_do_dia(a, i) for a in atividades), 2),
            "dia": round(sum(sete_dias(a.get("dias_realizado"))[i] for a in atividades), 2),
            "noite": round(sum(sete_dias(a.get("dias_noite"))[i] for a in atividades), 2),
        }
        for i in range(NUM_DIAS)
    ]


def numero_semana(semana: str) -> int:
    """Week number out of a "S.30/2026" reference."""
    cabeca = semana.split("/")[0] if "/" in semana else semana
    digitos = "".join(ch for ch in cabeca if ch.isdigit())
    return int(digitos) if digitos else 0


def ano_semana(semana: str) -> int:
    """Year out of a "S.30/2026" reference."""
    if "/" not in semana:
        return 0
    digitos = "".join(ch for ch in semana.split("/")[1] if ch.isdigit())
    return int(digitos) if digitos else 0


def ordem_semana(semana: str) -> tuple[int, int]:
    """Sort key that keeps weeks chronological across year boundaries."""
    return (ano_semana(semana), numero_semana(semana))
