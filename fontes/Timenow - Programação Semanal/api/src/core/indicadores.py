"""What the dashboard draws — every chart payload, computed server side.

## Por que existe um módulo só para isto

A tabela responde "o que aconteceu nesta atividade". O dashboard responde
"para onde a obra está indo". São perguntas diferentes e agregações
diferentes: uma percorre a semana, a outra percorre o horizonte inteiro.
Misturar as duas em `dados.py` faria a facade carregar um segundo assunto.

## A unidade do avanço físico

As atividades vivem em unidades incompatíveis — kg de armação, m² de
pintura, m³ de solo, unidades de transformador. **Somar quantidade bruta
entre elas não significa nada.** Toda curva daqui é construída sobre
percentual de conclusão por atividade:

    avanço da atividade na semana = realizado na semana / previsto total

com **peso igual por atividade**. É a leitura que o PPC do Last Planner
já usa na obra, e é a única que não exige uma tabela de custo ou de
homem-hora que este app não tem. Está escrito na legenda de cada gráfico
para ninguém ler a curva como volume.
"""

from __future__ import annotations

from src.core import calculos, semanas

MESES_CURTOS = (
    "jan",
    "fev",
    "mar",
    "abr",
    "mai",
    "jun",
    "jul",
    "ago",
    "set",
    "out",
    "nov",
    "dez",
)


def _peso_por_atividade(chaves: set[str]) -> float:
    return 100.0 / len(chaves) if chaves else 0.0


def _identidade(atividade: dict) -> str:
    """An activity followed across weeks is the same ID, not the same key."""
    return atividade.get("id_exclusiva") or atividade.get("key") or ""


def curva_s(atividades: list[dict]) -> list[dict]:
    """Physical S-curve, one point per week, with the running totals.

    Three series, matching the Timenow curve visual:

    * **base** — ritmo de referência: o escopo distribuído por igual entre
      as semanas do horizonte. Responde "se andássemos parelho, onde
      estaríamos".
    * **previsto** — o que a programação diz que a semana entrega.
    * **realizado** — o que a semana entregou de fato.

    A mesma atividade reaparece semana após semana com uma parcela nova —
    é assim que a obra programa. Então o denominador de cada atividade é
    o **escopo dela no horizonte inteiro**, não o da semana: sem isso toda
    semana marcaria 100% de previsto e a curva do plano seria uma reta a
    45 graus, que não diz nada.
    """
    por_semana: dict[str, list[dict]] = {}
    for atividade in atividades:
        por_semana.setdefault(atividade.get("semana", ""), []).append(atividade)
    por_semana.pop("", None)
    if not por_semana:
        return []

    escopo: dict[str, float] = {}
    for atividade in atividades:
        chave = _identidade(atividade)
        escopo[chave] = escopo.get(chave, 0.0) + calculos.total_previsto(atividade)

    ordenadas = sorted(por_semana, key=semanas.ordem)
    peso = _peso_por_atividade({c for c, total in escopo.items() if total > 0})
    passo_base = 100.0 / len(ordenadas)

    pontos: list[dict] = []
    acumulado = {"base": 0.0, "previsto": 0.0, "realizado": 0.0}

    for indice, semana in enumerate(ordenadas):
        do_periodo = por_semana[semana]
        previsto = 0.0
        realizado = 0.0
        for atividade in do_periodo:
            total = escopo.get(_identidade(atividade), 0.0)
            if total <= 0:
                continue
            previsto += peso * (calculos.total_previsto(atividade) / total)
            realizado += peso * (calculos.total_realizado(atividade) / total)

        acumulado["base"] = round(passo_base * (indice + 1), 2)
        acumulado["previsto"] = round(acumulado["previsto"] + previsto, 2)
        acumulado["realizado"] = round(acumulado["realizado"] + realizado, 2)

        descricao = semanas.descrever(semana)
        pontos.append(
            {
                "semana": semana,
                "ano": descricao["ano"],
                "mes": descricao["mes"],
                "mesNome": MESES_CURTOS[descricao["mes"] - 1] if descricao["mes"] else "",
                "numero": descricao["numero"],
                "periodo": descricao["periodo"],
                "base": round(passo_base, 2),
                "previsto": round(previsto, 2),
                "realizado": round(realizado, 2),
                "baseAcumulado": acumulado["base"],
                "previstoAcumulado": acumulado["previsto"],
                "realizadoAcumulado": min(acumulado["realizado"], 999.0),
                "atividades": len(do_periodo),
            }
        )
    return pontos


def previsto_realizado_por_semana(atividades: list[dict]) -> list[dict]:
    """Paired bars per week — plan against delivery, in percentage points.

    Carrega os campos de calendário porque o gráfico agrupa por mês e
    abre em semanas ao clique: o desenho precisa saber a que mês e a que
    ano cada ponto pertence, e somar semanas para formar o mês. Pontos
    percentuais são somáveis entre semanas — cada um é a fatia do escopo
    do horizonte entregue naquele período —, e é por isso que o mês
    consolidado é a soma pura das suas semanas.
    """
    return [
        {
            "rotulo": f"S{p['numero']:02d}",
            "detalhe": f"{p['semana']} · {p['periodo']}",
            "semana": p["semana"],
            "periodo": p["periodo"],
            "ano": p["ano"],
            "mes": p["mes"],
            "mesNome": p["mesNome"],
            "numero": p["numero"],
            "previsto": p["previsto"],
            "realizado": p["realizado"],
            "atividades": p["atividades"],
        }
        for p in curva_s(atividades)
    ]


def distribuicao_por_situacao(atividades: list[dict]) -> list[dict]:
    """Segmented bars: where the week sits in the release flow."""
    contagem = {
        "em_elaboracao": 0,
        "validada": 0,
        "publicada": 0,
    }
    aprovacao = {"aprovado": 0, "pendente": 0, "sem_realizado": 0}

    for a in atividades:
        situacao = a.get("situacao", "em_elaboracao")
        if situacao in contagem:
            contagem[situacao] += 1
        if (a.get("total_realizado") or 0) <= 0:
            aprovacao["sem_realizado"] += 1
        elif a.get("aprovacao_realizado") == "aprovado":
            aprovacao["aprovado"] += 1
        else:
            aprovacao["pendente"] += 1

    faixas = {"alta": 0, "media": 0, "baixa": 0}
    for a in atividades:
        faixas[calculos.faixa(a.get("ppc", 0))] += 1

    return [
        {
            "titulo": "Situação da programação",
            "segmentos": [
                {"nome": "Publicada", "valor": contagem["publicada"], "cor": "ok"},
                {"nome": "Validada", "valor": contagem["validada"], "cor": "info"},
                {"nome": "Em elaboração", "valor": contagem["em_elaboracao"], "cor": "warn"},
            ],
        },
        {
            "titulo": "Aprovação do realizado",
            "segmentos": [
                {"nome": "Aprovado", "valor": aprovacao["aprovado"], "cor": "ok"},
                {"nome": "Aguardando fiscal", "valor": aprovacao["pendente"], "cor": "warn"},
                {"nome": "Sem realizado", "valor": aprovacao["sem_realizado"], "cor": "neutro"},
            ],
        },
        {
            "titulo": "Faixa de PPC",
            "segmentos": [
                {"nome": "≥ 80%", "valor": faixas["alta"], "cor": "ok"},
                {"nome": "60 a 79%", "valor": faixas["media"], "cor": "warn"},
                {"nome": "< 60%", "valor": faixas["baixa"], "cor": "erro"},
            ],
        },
    ]


def ranking(atividades: list[dict], campo: str) -> list[dict]:
    """Adherence by company, front or foreman — worst first."""
    return [
        {
            "rotulo": grupo["chave"],
            "valor": grupo["aderencia"],
            "ppc": grupo["ppc"],
            "atividades": grupo["atividades"],
            "pendentes": grupo["pendentes"],
            "previsto": grupo["total_previsto"],
            "realizado": grupo["total_realizado"],
        }
        for grupo in calculos.quebrar_por(atividades, campo)
    ]


def heatmap_dia_frente(atividades: list[dict]) -> dict:
    """Day by front: how much of the day's plan each front delivered."""
    frentes = sorted({a.get("local") or "—" for a in atividades})
    linhas = []
    for frente in frentes:
        do_local = [a for a in atividades if (a.get("local") or "—") == frente]
        celulas = []
        for i in range(calculos.NUM_DIAS):
            previsto = sum(calculos.sete_dias(a.get("dias_previsto"))[i] for a in do_local)
            realizado = sum(calculos.realizado_do_dia(a, i) for a in do_local)
            percentual = round(realizado / previsto * 100, 1) if previsto else None
            celulas.append(
                {
                    "previsto": round(previsto, 1),
                    "realizado": round(realizado, 1),
                    "percentual": percentual,
                }
            )
        linhas.append({"rotulo": frente, "celulas": celulas})
    return {"colunas": list(calculos.DIAS_ROTULO), "linhas": linhas}


def turnos(atividades: list[dict]) -> list[dict]:
    """Day shift against night shift, per weekday."""
    return [
        {
            "rotulo": dia["rotulo"],
            "nome": dia["nome"],
            "dia": dia["dia"],
            "noite": dia["noite"],
            "previsto": dia["previsto"],
        }
        for dia in calculos.por_dia(atividades)
    ]


def gargalos(atividades: list[dict], limite: int = 8) -> list[dict]:
    """Activities that are dragging the week down — the action list."""
    candidatas = [
        a
        for a in atividades
        if (a.get("total_previsto") or 0) > 0 and a.get("ppc", 0) < calculos.FAIXA_MEDIA
    ]
    candidatas.sort(key=lambda a: (a.get("ppc", 0), -(a.get("total_previsto") or 0)))
    return [
        {
            "key": a.get("key"),
            "id_exclusiva": a.get("id_exclusiva"),
            "atividade": a.get("atividade"),
            "empresa": a.get("empresa"),
            "local": a.get("local"),
            "encarregado": a.get("encarregado"),
            "ppc": a.get("ppc", 0),
            "previsto": a.get("total_previsto", 0),
            "realizado": a.get("total_realizado", 0),
            "unidade": a.get("unidade", ""),
            "dias_sem_producao": sum(
                1
                for i in range(calculos.NUM_DIAS)
                if calculos.sete_dias(a.get("dias_previsto"))[i] > 0
                and calculos.realizado_do_dia(a, i) == 0
            ),
        }
        for a in candidatas[:limite]
    ]


def evolucao_por_empresa(atividades: list[dict]) -> dict:
    """One adherence line per contractor, week by week — with drill.

    Manda **quantidade**, não percentual pronto. A diferença importa
    quando o gráfico agrupa: aderência de um mês é a soma do realizado
    dividida pela soma do previsto do mês, e **não** a média das
    aderências semanais. As duas contas dão resultados diferentes sempre
    que as semanas têm tamanhos diferentes — que é o caso normal.

    Com previsto e realizado brutos em cada ponto, o desenho refaz a
    divisão em qualquer nível de agrupamento e acerta nos três.
    """
    referencias = sorted(
        {a.get("semana", "") for a in atividades if a.get("semana")}, key=semanas.ordem
    )
    empresas = sorted({a.get("empresa") or "—" for a in atividades})

    pontos = []
    for semana in referencias:
        descricao = semanas.descrever(semana)
        valores: dict[str, dict] = {}
        for empresa in empresas:
            do_grupo = [
                a
                for a in atividades
                if a.get("semana") == semana and (a.get("empresa") or "—") == empresa
            ]
            if not do_grupo:
                continue
            valores[empresa] = {
                "previsto": round(sum(calculos.total_previsto(a) for a in do_grupo), 2),
                "realizado": round(sum(calculos.total_realizado(a) for a in do_grupo), 2),
            }
        pontos.append(
            {
                "semana": semana,
                "ano": descricao["ano"],
                "mes": descricao["mes"],
                "mesNome": MESES_CURTOS[descricao["mes"] - 1] if descricao["mes"] else "",
                "numero": descricao["numero"],
                "periodo": descricao["periodo"],
                "valores": valores,
            }
        )

    return {"series": empresas, "pontos": pontos}


def painel(atividades_semana: list[dict], atividades_horizonte: list[dict], config: dict) -> dict:
    """Everything the dashboard needs, in one object ready for the template."""
    meta_aderencia = calculos.numero(config.get("meta_aderencia"), 60.0)
    meta_ppc = calculos.numero(config.get("meta_ppc"), 75.0)
    aderencia = calculos.aderencia_geral(atividades_semana)
    ppc = calculos.ppc_medio(atividades_semana)

    return {
        "aderencia": aderencia,
        "ppc_medio": ppc,
        "meta_aderencia": meta_aderencia,
        "meta_ppc": meta_ppc,
        "atinge_aderencia": aderencia >= meta_aderencia,
        "atinge_ppc": ppc >= meta_ppc,
        "total_atividades": len(atividades_semana),
        "fornecedores": len({a.get("empresa") for a in atividades_semana if a.get("empresa")}),
        "frentes": len({a.get("local") for a in atividades_semana if a.get("local")}),
        # A curva S saiu do dashboard — a evolução da aderência responde a
        # mesma pergunta por contratada. `curva_s` continua aqui: é uma
        # função do domínio, testada, e o desenho `curva-s` segue no DS
        # para quem precisar dela. O que não faz mais sentido é serializar
        # o payload dela em toda carga de uma tela que não a desenha.
        "barras_semana": previsto_realizado_por_semana(atividades_horizonte),
        "status": distribuicao_por_situacao(atividades_semana),
        "por_empresa": ranking(atividades_semana, "empresa"),
        "por_local": ranking(atividades_semana, "local"),
        "por_encarregado": ranking(atividades_semana, "encarregado"),
        "heatmap": heatmap_dia_frente(atividades_semana),
        "turnos": turnos(atividades_semana),
        "gargalos": gargalos(atividades_semana),
        # A meta viaja junto com a série porque o gráfico desenha a linha
        # de referência dela. Sem isso o desenho teria de descobrir a meta
        # por conta própria, e a única forma seria repetir aqui um valor
        # que já está na configuração do projeto.
        "evolucao": {
            **evolucao_por_empresa(atividades_horizonte),
            "meta": meta_aderencia,
        },
    }
