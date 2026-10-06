"""Testes das regras que não dá para ver na tela.

Cobrem o que quebra em silêncio: aritmética de semana, a janela de
programação, o cálculo do avanço físico e o recorte por empresa. O resto
do app é conferido percorrendo a tela — estes são os casos em que a tela
mostraria um número plausível e errado.

    api/.venv/Scripts/python.exe -m pytest api/tests -q
"""

from datetime import datetime
from types import SimpleNamespace

import pytest

from src.core import calculos, indicadores, janela, rbac, semanas

# ── Semanas ─────────────────────────────────────────────────────────────


def test_referencia_ida_e_volta():
    assert semanas.partes("S.30/2026") == (2026, 30)
    assert semanas.referencia(2026, 30) == "S.30/2026"


def test_semana_abre_na_segunda_e_fecha_no_domingo():
    abertura = semanas.inicio("S.30/2026")
    fechamento = semanas.fim("S.30/2026")
    assert abertura.weekday() == 0
    assert fechamento.weekday() == 6
    assert (fechamento - abertura).days == 6


def test_referencia_invalida_nao_estoura():
    assert semanas.inicio("qualquer coisa") is None
    assert semanas.partes("") == (0, 0)


def test_ano_de_53_semanas():
    """2026 tem 53 semanas ISO. Fixar 52 quebraria a virada do ano."""
    assert semanas.semanas_no_ano(2026) == 53
    assert semanas.inicio("S.53/2026") is not None


def test_deslocar_atravessa_o_ano():
    assert semanas.deslocar("S.53/2026", 1) == "S.01/2027"
    assert semanas.deslocar("S.01/2027", -1) == "S.53/2026"


def test_ordem_e_cronologica_entre_anos():
    referencias = ["S.02/2027", "S.51/2026", "S.01/2027"]
    assert sorted(referencias, key=semanas.ordem) == [
        "S.51/2026",
        "S.01/2027",
        "S.02/2027",
    ]


# ── Cálculos ────────────────────────────────────────────────────────────


def atividade(previsto, dia=None, noite=None):
    bruta = {
        "dias_previsto": previsto,
        "dias_realizado": dia or [0] * 7,
        "dias_noite": noite or [0] * 7,
        "prod_prevista": sum(previsto),
    }
    return calculos.preencher_calculados(bruta)


def test_ppc_soma_os_dois_turnos():
    a = atividade([10] * 7, dia=[5] * 7, noite=[5] * 7)
    assert a["total_previsto"] == 70
    assert a["total_realizado"] == 70
    assert a["ppc"] == 100


def test_numero_aceita_formato_brasileiro():
    assert calculos.numero("1.234,5") == 1234.5
    assert calculos.numero("1234.5") == 1234.5
    assert calculos.numero("") == 0.0
    assert calculos.numero(None) == 0.0
    assert calculos.numero("não é número") == 0.0


def test_sete_dias_normaliza_qualquer_entrada():
    assert calculos.sete_dias([1, 2]) == [1.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    assert len(calculos.sete_dias(list(range(20)))) == 7
    assert calculos.sete_dias(None) == [0.0] * 7


def test_aderencia_pondera_pelo_tamanho_e_ppc_medio_nao():
    """A diferença entre os dois indicadores, no caso que a expõe.

    Uma atividade grande com 50% e uma pequena com 100%: a aderência
    fica perto de 50 porque a grande domina; o PPC médio dá 75.
    """
    grande = atividade([100] * 7, dia=[50] * 7)
    pequena = atividade([1] * 7, dia=[1] * 7)
    assert calculos.aderencia_geral([grande, pequena]) == pytest.approx(50.5, abs=0.1)
    assert calculos.ppc_medio([grande, pequena]) == 75.0


def test_faixa_nas_fronteiras():
    assert calculos.faixa(80) == "alta"
    assert calculos.faixa(79.9) == "media"
    assert calculos.faixa(60) == "media"
    assert calculos.faixa(59.9) == "baixa"


def test_previsto_zerado_nao_divide_por_zero():
    a = atividade([0] * 7, dia=[10] * 7)
    assert a["ppc"] == 0.0
    assert calculos.aderencia_geral([a]) == 0.0


# ── Janela de programação ───────────────────────────────────────────────

SEXTA = datetime(2026, 7, 24, 10, 0)  # noqa: DTZ001 — relógio fixo do teste
SABADO = datetime(2026, 7, 25, 10, 0)  # noqa: DTZ001

REGULAR = {
    "empresa": "M. Roscoe",
    "dias": [{"dia": "sex", "abre": "08:00", "fecha": "15:00"}],
    "semanas_liberadas": ["S.31/2026"],
    "extra": [],
}


def test_aberta_no_dia_e_no_horario():
    aberta, _ = janela.janela_aberta("S.31/2026", REGULAR, SEXTA)
    assert aberta


def test_fechada_fora_do_horario():
    tarde = SEXTA.replace(hour=16)
    aberta, motivo = janela.janela_aberta("S.31/2026", REGULAR, tarde)
    assert not aberta
    assert "15:00" in motivo


def test_fechada_no_dia_errado():
    aberta, _ = janela.janela_aberta("S.31/2026", REGULAR, SABADO)
    assert not aberta


def test_fechada_para_semana_nao_liberada():
    aberta, motivo = janela.janela_aberta("S.40/2026", REGULAR, SEXTA)
    assert not aberta
    assert "S.40/2026" in motivo


def test_sem_janela_cadastrada_e_fechada():
    aberta, _ = janela.janela_aberta("S.31/2026", None, SEXTA)
    assert not aberta


def test_extraordinaria_abre_no_dia_errado():
    com_extra = {
        **REGULAR,
        "extra": [{"semana": "S.40/2026", "abre": "2026-07-25 00:00", "fecha": "2026-07-26 23:59"}],
    }
    aberta, motivo = janela.janela_aberta("S.40/2026", com_extra, SABADO)
    assert aberta
    assert "extraordinária" in motivo


def test_extraordinaria_fecha_o_que_estava_liberado():
    """A exceção vence nos DOIS sentidos — é o ponto dela."""
    com_extra = {
        **REGULAR,
        "extra": [{"semana": "S.31/2026", "abre": "2026-01-01 00:00", "fecha": "2026-01-02 00:00"}],
    }
    aberta, _ = janela.janela_aberta("S.31/2026", com_extra, SEXTA)
    assert not aberta


def test_sem_dia_configurado_libera_qualquer_dia():
    sem_dia = {**REGULAR, "dias": []}
    aberta, _ = janela.janela_aberta("S.31/2026", sem_dia, SABADO)
    assert aberta


# ── Curva S ─────────────────────────────────────────────────────────────


def semana_de(referencia, id_exclusiva, previsto, realizado):
    return calculos.preencher_calculados(
        {
            "semana": referencia,
            "id_exclusiva": id_exclusiva,
            "key": f"{referencia}::{id_exclusiva}",
            "dias_previsto": [previsto / 7] * 7,
            "dias_realizado": [realizado / 7] * 7,
            "dias_noite": [0] * 7,
        }
    )


def test_curva_fecha_em_cem_por_cento_de_previsto():
    """O previsto acumulado do horizonte inteiro tem de fechar em 100.

    É o teste que pegaria o erro de usar o previsto da SEMANA como
    denominador: ali cada semana marcava 100% e o acumulado ia a 600.
    """
    atividades = [semana_de(f"S.{n}/2026", "A-1", 100, 50) for n in (28, 29, 30)] + [
        semana_de(f"S.{n}/2026", "A-2", 200, 200) for n in (28, 29, 30)
    ]

    curva = indicadores.curva_s(atividades)
    assert len(curva) == 3
    assert curva[-1]["previstoAcumulado"] == pytest.approx(100, abs=0.1)
    assert curva[-1]["baseAcumulado"] == pytest.approx(100, abs=0.1)
    # A-1 entregou metade e A-2 tudo, com peso igual: 75%.
    assert curva[-1]["realizadoAcumulado"] == pytest.approx(75, abs=0.1)


def test_curva_ordena_por_calendario_e_nao_por_texto():
    atividades = [
        semana_de("S.02/2027", "A-1", 10, 10),
        semana_de("S.51/2026", "A-1", 10, 10),
    ]
    assert [p["semana"] for p in indicadores.curva_s(atividades)] == [
        "S.51/2026",
        "S.02/2027",
    ]


def test_curva_sem_dados_devolve_lista_vazia():
    assert indicadores.curva_s([]) == []


def test_unidades_diferentes_nao_sao_somadas():
    """Duas atividades em unidades incompatíveis, uma bem maior em número.

    Se a curva somasse quantidade bruta, os 3.000 m³ afogariam os 2 und.
    Com peso igual por atividade, uma parada e outra completa dão 50%.
    """
    atividades = [
        semana_de("S.30/2026", "SOLO", 3000, 0),
        semana_de("S.30/2026", "TRAFO", 2, 2),
    ]
    curva = indicadores.curva_s(atividades)
    assert curva[-1]["realizadoAcumulado"] == pytest.approx(50, abs=0.1)


# ── Formatação e faixas de leitura ──────────────────────────────────────


def test_medida_respeita_a_unidade():
    """A unidade muda o formato, porque muda o que o número significa."""
    from src.core.jinja_env import _medida

    assert _medida(2, "und") == "2"
    assert _medida(2.4, "und") == "2"  # meia unidade não existe
    assert _medida(2.5, "m³") == "2,5"  # meio metro cúbico existe
    assert _medida(1234.5, "kg") == "1.234"  # acima de 100 o decimal só ocupa espaço
    assert _medida(120000, "kg") == "120 mil"  # senão não cabe na célula
    assert _medida(0, "kg") == "—"  # zero é ausência, e se lê como tal


def test_nivel_de_calor_nas_fronteiras():
    from src.core.jinja_env import _nivel_calor

    assert _nivel_calor(None) == 0
    assert _nivel_calor(0) == 1
    assert _nivel_calor(24.9) == 1
    assert _nivel_calor(25) == 2
    assert _nivel_calor(49.9) == 2
    assert _nivel_calor(50) == 3
    assert _nivel_calor(74.9) == 3
    assert _nivel_calor(75) == 4
    assert _nivel_calor(99.9) == 4
    assert _nivel_calor(100) == 5
    assert _nivel_calor(140) == 5


# ── Evolução por contratada ─────────────────────────────────────────────


def com_empresa(referencia, empresa, previsto, realizado):
    return calculos.preencher_calculados(
        {
            "semana": referencia,
            "empresa": empresa,
            "id_exclusiva": empresa[:3] + referencia,
            "dias_previsto": [previsto / 7] * 7,
            "dias_realizado": [realizado / 7] * 7,
            "dias_noite": [0] * 7,
        }
    )


def test_evolucao_manda_quantidade_e_nao_percentual():
    """O gráfico agrupa semanas em meses, e aderência de mês não é média.

    Com duas semanas de tamanhos diferentes, a média das aderências
    semanais e a aderência do mês dão números distintos. Mandar
    quantidade é o que deixa o desenho fazer a conta certa em qualquer
    nível de agrupamento.
    """
    atividades = [
        com_empresa("S.28/2026", "Alfa", 100, 100),  # 100%
        com_empresa("S.29/2026", "Alfa", 900, 450),  # 50%
    ]
    dados = indicadores.evolucao_por_empresa(atividades)

    assert dados["series"] == ["Alfa"]
    assert len(dados["pontos"]) == 2
    assert dados["pontos"][0]["valores"]["Alfa"] == {"previsto": 100.0, "realizado": 100.0}

    total_previsto = sum(p["valores"]["Alfa"]["previsto"] for p in dados["pontos"])
    total_realizado = sum(p["valores"]["Alfa"]["realizado"] for p in dados["pontos"])
    assert round(total_realizado / total_previsto * 100, 1) == 55.0  # a conta certa
    assert round((100 + 50) / 2, 1) == 75.0  # a média, que seria a errada


def test_evolucao_ignora_empresa_sem_atividade_na_semana():
    atividades = [
        com_empresa("S.28/2026", "Alfa", 100, 50),
        com_empresa("S.29/2026", "Beta", 100, 50),
    ]
    pontos = indicadores.evolucao_por_empresa(atividades)["pontos"]
    assert "Beta" not in pontos[0]["valores"]
    assert "Alfa" not in pontos[1]["valores"]


# ── Próxima ação: o botão principal da linha ────────────────────────────
# O botão verde é resolvido no servidor, e a regra é fácil de quebrar sem
# ninguém notar — a tela continua desenhando um botão, só que o errado.
# Estes testes prendem a matriz de perfil contra estado.


def _usuario(perfil: str):
    return SimpleNamespace(permissions=rbac.resolve([perfil]))


def _atividade(situacao: str, aprovacao: str, *, tem_realizado: bool) -> dict:
    return {
        "situacao": situacao,
        "aprovacao_realizado": aprovacao,
        "tem_realizado": tem_realizado,
    }


def test_fiscal_ve_aprovar_onde_a_contratada_ve_lancar():
    """O mesmo estado, o botão de cada um."""
    pendente = _atividade("validada", "pendente", tem_realizado=True)
    assert rbac.proxima_acao(_usuario("fiscal"), pendente) == "aprovar"
    assert rbac.proxima_acao(_usuario("fornecedor"), pendente) == "lancar"


def test_visualizador_so_ve():
    """Sem permissão de nenhum degrau, o botão é sempre o de leitura."""
    for situacao in ("em_elaboracao", "validada", "publicada"):
        for aprovacao in ("pendente", "aprovado"):
            atividade = _atividade(situacao, aprovacao, tem_realizado=True)
            assert rbac.proxima_acao(_usuario("visualizador"), atividade) == "ver"


def test_realizado_aprovado_vira_publicar():
    """Lançado e aprovado: o que falta é liberar a semana."""
    aprovada = _atividade("validada", "aprovado", tem_realizado=True)
    assert rbac.proxima_acao(_usuario("planejador"), aprovada) == "publicar"
    assert rbac.proxima_acao(_usuario("admin"), aprovada) == "publicar"


def test_publicada_nao_oferece_publicar_de_novo():
    ja_publicada = _atividade("publicada", "aprovado", tem_realizado=True)
    assert rbac.proxima_acao(_usuario("planejador"), ja_publicada) == "ver"


def test_administrador_percorre_a_fila_na_ordem_do_fluxo():
    """Quem pode tudo recebe um degrau de cada vez, na ordem do processo.

    É o caso que a ordem dos testes dentro de `proxima_acao` protege: com
    aprovar depois de lançar, o administrador veria "Lançar" sobre um
    realizado que já está pronto e parado esperando o fiscal.
    """
    admin = _usuario("admin")
    esperado = [
        (_atividade("em_elaboracao", "pendente", tem_realizado=False), "validar"),
        (_atividade("validada", "pendente", tem_realizado=False), "lancar"),
        (_atividade("validada", "pendente", tem_realizado=True), "aprovar"),
        (_atividade("validada", "aprovado", tem_realizado=True), "publicar"),
        (_atividade("publicada", "aprovado", tem_realizado=True), "ver"),
    ]
    assert [rbac.proxima_acao(admin, a) for a, _ in esperado] == [e for _, e in esperado]
