"""Testes do isolamento por ambiente — o que a tela não pode mostrar.

Cobrem a garantia central da entrega: dado de um cliente não alcança o
outro. Contexto de ambiente, falha fechada, isolamento por agregado,
concorrência e o registro de ambientes — tudo contra diretório
temporário, sem servidor e sem tocar a base real.

Os slugs são únicos por teste de propósito: o guarda de portas mantém
uma instância por ambiente pela vida do processo (decisão 8), então um
slug reaproveitado entre testes devolveria a instância de um teste
anterior, apontando para um diretório temporário já apagado.
"""

import base64
import json
import re
import threading
from io import BytesIO
from urllib.parse import unquote

import azure.functions as func
import pytest
from openpyxl import load_workbook

from src.blueprints import (
    _comum,
    ambientes,
    colaboradores,
    configuracoes,
    dados_api,
    exportacao,
    nav,
)
from src.core import ambiente, auditoria, auth, calculos, dados, rbac, registro, repositorio
from src.core.dados import InvalidoError
from src.core.repositorio import diretorio_de_dados


def _atividade(id_exclusiva: str, semana: str = "S.30/2026") -> dict:
    return {
        "key": f"{semana.replace('/', '-')}::{id_exclusiva}",
        "item": 1,
        "semana": semana,
        "id_exclusiva": id_exclusiva,
        "atividade": f"Atividade {id_exclusiva}",
        "local": "Local de teste",
        "empresa": "Empresa de teste",
        "responsavel": "",
        "encarregado": "",
        "prod_prevista": 7.0,
        "unidade": "und",
        "dias_previsto": [1.0] * 7,
        "dias_realizado": [0.0] * 7,
        "dias_noite": [0.0] * 7,
        "situacao": "em_elaboracao",
        "aprovacao_realizado": "pendente",
    }


# ── Contexto de ambiente ─────────────────────────────────────────────────


def test_bloco_aninhado_devolve_o_ambiente_de_dentro():
    with ambiente.ambiente_ativo("ctx-fora"):
        assert ambiente.slug_ativo() == "ctx-fora"
        with ambiente.ambiente_ativo("ctx-dentro"):
            assert ambiente.slug_ativo() == "ctx-dentro"
        assert ambiente.slug_ativo() == "ctx-fora"
    with pytest.raises(ambiente.SemAmbienteError):
        ambiente.slug_ativo()


def test_excecao_dentro_do_bloco_nao_deixa_o_ambiente_sujo():
    with ambiente.ambiente_ativo("exc-fora"):
        with pytest.raises(RuntimeError, match="boom"), ambiente.ambiente_ativo("exc-dentro"):
            raise RuntimeError("boom")
        assert ambiente.slug_ativo() == "exc-fora"
    with pytest.raises(ambiente.SemAmbienteError):
        ambiente.slug_ativo()


# ── Falha fechada ────────────────────────────────────────────────────────


def test_obter_fora_de_qualquer_ambiente_levanta():
    with pytest.raises(ambiente.SemAmbienteError):
        repositorio.obter()


def test_registrar_na_trilha_fora_de_qualquer_ambiente_levanta():
    with pytest.raises(ambiente.SemAmbienteError):
        auditoria.registrar("criar", "alguem@exemplo.com", "não deveria gravar")


# ── Base e trilha por ambiente ───────────────────────────────────────────


def test_escrever_em_a_nao_toca_em_b():
    with ambiente.ambiente_ativo("esc-a"):
        repositorio.obter().gravar_atividade(_atividade("ESC-A"))
        auditoria.registrar("criar", "alguem@a.com", "evento de a")

    with ambiente.ambiente_ativo("esc-b"):
        assert repositorio.obter().obter_atividade("ESC-A") is None
        assert auditoria.recentes() == []


def test_mesma_instancia_dentro_do_mesmo_ambiente():
    with ambiente.ambiente_ativo("inst-a"):
        primeira = repositorio.obter()
        segunda = repositorio.obter()
    assert primeira is segunda

    with ambiente.ambiente_ativo("inst-b"):
        outra = repositorio.obter()
    assert outra is not primeira


def test_definir_afeta_somente_o_ambiente_da_chave(tmp_path):
    injetado = repositorio.RepositorioJson(tmp_path / "seam" / "programacao.json")
    repositorio.definir("seam-a", injetado)

    with ambiente.ambiente_ativo("seam-a"):
        assert repositorio.obter() is injetado
    with ambiente.ambiente_ativo("seam-b"):
        assert repositorio.obter() is not injetado


# ── Isolamento por agregado — um caso por agregado da porta ──────────────
# Escreve em A e confirma a ausência na consulta de B. Nenhum teste
# afirma em qual pasta o arquivo caiu: o comportamento observável é a
# ausência, e ele continua passando se o layout de armazenamento mudar.


def test_isolamento_de_atividade():
    with ambiente.ambiente_ativo("iso-atv-a"):
        repositorio.obter().gravar_atividade(_atividade("ISO-ATV"))

    with ambiente.ambiente_ativo("iso-atv-b"):
        assert repositorio.obter().obter_atividade("ISO-ATV") is None


def test_isolamento_de_cadastro():
    with ambiente.ambiente_ativo("iso-cad-a"):
        repositorio.obter().gravar_cadastro("locais", ["Local só do A"])

    with ambiente.ambiente_ativo("iso-cad-b"):
        assert "Local só do A" not in repositorio.obter().listar_cadastro("locais")


def test_isolamento_de_janela():
    janela_a = {
        "empresa": "Empresa só do A",
        "dias": [],
        "semanas_liberadas": ["S.31/2026"],
        "extra": [],
    }
    with ambiente.ambiente_ativo("iso-jan-a"):
        repositorio.obter().gravar_janela(janela_a)

    with ambiente.ambiente_ativo("iso-jan-b"):
        janelas_b = repositorio.obter().listar_janelas()
        assert not any(j.get("empresa") == "Empresa só do A" for j in janelas_b)


def test_isolamento_de_colaborador():
    colaborador_a = {
        "nome": "Pessoa do A",
        "email": "pessoa-a@exemplo.com",
        "perfil": "admin",
        "vinculo": "timenow",
        "empresa": "",
        "ativo": True,
    }
    with ambiente.ambiente_ativo("iso-col-a"):
        repositorio.obter().gravar_colaborador(colaborador_a)

    with ambiente.ambiente_ativo("iso-col-b"):
        emails_b = [c.get("email") for c in repositorio.obter().listar_colaboradores()]
        assert "pessoa-a@exemplo.com" not in emails_b


def test_isolamento_de_parametros():
    with ambiente.ambiente_ativo("iso-par-a"):
        repositorio.obter().gravar_parametros({"meta_aderencia": 42.0})

    with ambiente.ambiente_ativo("iso-par-b"):
        assert repositorio.obter().obter_parametros()["meta_aderencia"] != 42.0


# ── Concorrência ─────────────────────────────────────────────────────────


def test_duas_threads_em_dois_ambientes_nao_interferem():
    """Cada thread escreve e lê a própria base, ao mesmo tempo.

    É o teste que transforma a garantia do ``ContextVar`` em fato: se o
    ambiente vazasse entre as threads, uma delas leria as atividades da
    outra e a primeira asserção falharia.
    """

    def trabalhar(slug, propria, leituras):
        with ambiente.ambiente_ativo(slug):
            repo = repositorio.obter()
            for indice in range(20):
                repo.gravar_atividade(_atividade(f"{propria}-{indice}"))
                leituras.append({a.get("id_exclusiva") for a in repo.listar_atividades()})

    leituras_a: list[set[str]] = []
    leituras_b: list[set[str]] = []
    thread_a = threading.Thread(target=trabalhar, args=("cc-a", "CC-A", leituras_a))
    thread_b = threading.Thread(target=trabalhar, args=("cc-b", "CC-B", leituras_b))
    thread_a.start()
    thread_b.start()
    thread_a.join()
    thread_b.join()

    assert leituras_a and leituras_b, "as threads não leram nada"
    assert all(not any(i.startswith("CC-B") for i in leitura) for leitura in leituras_a)
    assert all(not any(i.startswith("CC-A") for i in leitura) for leitura in leituras_b)
    assert all(any(i.startswith("CC-A") for i in leitura) for leitura in leituras_a)
    assert all(any(i.startswith("CC-B") for i in leitura) for leitura in leituras_b)


# ── Registro de ambientes ────────────────────────────────────────────────
# A porta global que decide quais ambientes existem e quem entra em cada
# um. Roda fora de qualquer ambiente — é acima deles que ela mora.

EMAIL = "pessoa@exemplo.com"
OPERADOR = "operador@timenow.com.br"


def _criar(identificador: str, *, membros: tuple[str, ...] = ()) -> dict:
    criado = registro.obter().criar(
        identificador, f"Projeto {identificador}", f"Cliente {identificador}", OPERADOR
    )
    for email in membros:
        registro.obter().conceder(identificador, email, OPERADOR)
    return criado


def test_criar_ambiente_fica_ativo_e_listavel():
    _criar("reg-criado")

    ambiente_criado = registro.obter().obter("reg-criado")
    assert ambiente_criado is not None
    assert ambiente_criado["situacao"] == "ativo"
    assert ambiente_criado["projeto"] == "Projeto reg-criado"
    assert ambiente_criado["cliente"] == "Cliente reg-criado"


def test_listar_por_email_devolve_so_ativos_onde_e_membro():
    _criar("reg-membro", membros=(EMAIL,))
    _criar("reg-alheio")
    _criar("reg-arquivado", membros=(EMAIL,))
    registro.obter().arquivar("reg-arquivado", OPERADOR)

    listados = registro.obter().listar_por_email(EMAIL)
    assert [a["id"] for a in listados] == ["reg-membro"]


def test_email_sem_pertencimento_recebe_lista_vazia():
    _criar("reg-sem-membro")

    assert registro.obter().listar_por_email(EMAIL) == []


@pytest.mark.parametrize(
    "identificador",
    ["MCCAIN", "a", "slug com espaço", "slug_com_sublinhado", "x" * 33, ""],
)
def test_slug_fora_do_formato_e_recusado(identificador):
    with pytest.raises(InvalidoError):
        registro.obter().criar(identificador, "Projeto", "Cliente", OPERADOR)


def test_slug_repetido_e_recusado_inclusive_contra_arquivado():
    _criar("reg-repetido")

    with pytest.raises(InvalidoError):
        registro.obter().criar("reg-repetido", "Outro projeto", "Outro cliente", OPERADOR)

    registro.obter().arquivar("reg-repetido", OPERADOR)
    with pytest.raises(InvalidoError):
        registro.obter().criar("reg-repetido", "Outro projeto", "Outro cliente", OPERADOR)


def test_conceder_e_revogar_refletem_na_listagem_seguinte():
    _criar("reg-membros")

    registro.obter().conceder("reg-membros", EMAIL, OPERADOR)
    assert EMAIL in registro.obter().listar_membros("reg-membros")
    assert [a["id"] for a in registro.obter().listar_por_email(EMAIL)] == ["reg-membros"]

    registro.obter().revogar("reg-membros", EMAIL, OPERADOR)
    assert EMAIL not in registro.obter().listar_membros("reg-membros")
    assert registro.obter().listar_por_email(EMAIL) == []


def test_arquivar_tira_da_listagem_sem_apagar_e_desarquivar_devolve():
    _criar("reg-arquivar", membros=(EMAIL,))

    registro.obter().arquivar("reg-arquivar", OPERADOR)
    assert registro.obter().listar_por_email(EMAIL) == []
    arquivado = registro.obter().obter("reg-arquivar")
    assert arquivado is not None
    assert arquivado["situacao"] == "arquivado"
    assert EMAIL in arquivado["membros"]

    registro.obter().desarquivar("reg-arquivar", OPERADOR)
    desarquivado = registro.obter().obter("reg-arquivar")
    assert desarquivado["situacao"] == "ativo"
    assert [a["id"] for a in registro.obter().listar_por_email(EMAIL)] == ["reg-arquivar"]
    assert EMAIL in desarquivado["membros"]


def test_identificador_nunca_muda():
    _criar("reg-imutavel")
    registro.obter().arquivar("reg-imutavel", OPERADOR)
    registro.obter().desarquivar("reg-imutavel", OPERADOR)

    assert registro.obter().obter("reg-imutavel")["id"] == "reg-imutavel"


def test_trilha_do_registro_recebe_um_evento_por_operacao():
    _criar("reg-trilha")
    registro.obter().conceder("reg-trilha", EMAIL, OPERADOR)
    registro.obter().revogar("reg-trilha", EMAIL, OPERADOR)
    registro.obter().arquivar("reg-trilha", OPERADOR)
    registro.obter().desarquivar("reg-trilha", OPERADOR)

    eventos = registro.obter().recentes()
    assert [e["acao"] for e in reversed(eventos)] == [
        "criar",
        "conceder",
        "revogar",
        "arquivar",
        "desarquivar",
    ]
    for evento in eventos:
        assert evento["ator"] == OPERADOR
        assert evento["quando"]


def test_registro_fica_na_raiz_do_diretorio_de_dados():
    """O arquivo do registro nunca mora dentro da pasta de um ambiente."""
    from src.core.repositorio import diretorio_de_dados

    _criar("reg-raiz")

    raiz = diretorio_de_dados()
    assert (raiz / "registro.json").exists()
    assert not (raiz / "reg-raiz" / "registro.json").exists()


def test_gravacao_interrompida_nao_deixa_o_registro_pela_metade(monkeypatch):
    _criar("reg-intacto")

    def explodir(*_args, **_kwargs):
        raise OSError("disco cheio")

    monkeypatch.setattr(json, "dump", explodir)
    with pytest.raises(OSError, match="disco cheio"):
        registro.obter().criar("reg-perdido", "Projeto", "Cliente", OPERADOR)
    monkeypatch.undo()

    assert registro.obter().obter("reg-intacto") is not None
    assert registro.obter().obter("reg-perdido") is None
    registro.obter().criar("reg-pos", "Projeto", "Cliente", OPERADOR)
    assert registro.obter().obter("reg-pos") is not None


# ── Criação de ambiente com clonagem enxuta ─────────────────────────────
# A mesma função que o comando de linha e a tela da Entrega 2 chamam.
# O ambiente novo nasce com unidades e parâmetros do base e com ZERO
# dado operacional — um caso de teste por agregado que não pode ser
# copiado.


def _preparar_base(slug: str) -> None:
    """Enche um ambiente com dado em TODOS os agregados da porta."""
    registro.obter().criar(slug, f"Projeto {slug}", f"Cliente {slug}", OPERADOR)
    with ambiente.ambiente_ativo(slug):
        repo = repositorio.obter()
        repo.gravar_cadastro("unidades", ["bobina", "rolo"])
        repo.gravar_cadastro("locais", ["Local do base"])
        repo.gravar_cadastro("empresas", ["Empresa do base"])
        repo.gravar_parametros({"meta_aderencia": 42.0, "meta_ppc": 88.0})
        repo.gravar_atividade(_atividade(f"{slug.upper()}-ATV"))
        repo.gravar_janela(
            {"empresa": "Empresa do base", "dias": [], "semanas_liberadas": [], "extra": []}
        )
        repo.gravar_colaborador(
            {
                "nome": "Pessoa do base",
                "email": f"base-{slug}@exemplo.com",
                "perfil": "admin",
                "vinculo": "timenow",
                "empresa": "",
                "ativo": True,
            }
        )
        repo.gravar_solicitacao(
            {"id": f"sol-{slug}", "motivo": "pedido do base", "situacao": "pendente"}
        )
        auditoria.registrar("criar", "alguem@exemplo.com", "evento do base")


def test_clonagem_copia_unidades_e_parametros_do_base():
    _preparar_base("clon-u-b")
    registro.criar_ambiente("clon-u-n", "Projeto Novo", "Cliente Novo", OPERADOR, base="clon-u-b")

    with ambiente.ambiente_ativo("clon-u-n"):
        repo = repositorio.obter()
        assert repo.listar_cadastro("unidades") == ["bobina", "rolo"]
        assert repo.obter_parametros()["meta_aderencia"] == 42.0
        assert repo.obter_parametros()["meta_ppc"] == 88.0


def test_clonagem_nao_copia_atividades():
    _preparar_base("clon-a-b")
    registro.criar_ambiente("clon-a-n", "Projeto", "Cliente", OPERADOR, base="clon-a-b")

    with ambiente.ambiente_ativo("clon-a-n"):
        assert repositorio.obter().listar_atividades() == []


def test_clonagem_nao_copia_solicitacoes():
    _preparar_base("clon-s-b")
    registro.criar_ambiente("clon-s-n", "Projeto", "Cliente", OPERADOR, base="clon-s-b")

    with ambiente.ambiente_ativo("clon-s-n"):
        assert repositorio.obter().listar_solicitacoes() == []


def test_clonagem_nao_copia_trilha():
    _preparar_base("clon-t-b")
    registro.criar_ambiente("clon-t-n", "Projeto", "Cliente", OPERADOR, base="clon-t-b")

    with ambiente.ambiente_ativo("clon-t-n"):
        assert auditoria.recentes() == []


def test_clonagem_nao_copia_locais():
    _preparar_base("clon-l-b")
    registro.criar_ambiente("clon-l-n", "Projeto", "Cliente", OPERADOR, base="clon-l-b")

    with ambiente.ambiente_ativo("clon-l-n"):
        assert repositorio.obter().listar_cadastro("locais") == []


def test_clonagem_nao_copia_empresas():
    _preparar_base("clon-e-b")
    registro.criar_ambiente("clon-e-n", "Projeto", "Cliente", OPERADOR, base="clon-e-b")

    with ambiente.ambiente_ativo("clon-e-n"):
        assert repositorio.obter().listar_cadastro("empresas") == []


def test_clonagem_nao_copia_janelas():
    _preparar_base("clon-j-b")
    registro.criar_ambiente("clon-j-n", "Projeto", "Cliente", OPERADOR, base="clon-j-b")

    with ambiente.ambiente_ativo("clon-j-n"):
        assert repositorio.obter().listar_janelas() == []


def test_clonagem_nao_copia_colaboradores_alem_do_criador():
    _preparar_base("clon-c-b")
    registro.criar_ambiente("clon-c-n", "Projeto", "Cliente", OPERADOR, base="clon-c-b")

    with ambiente.ambiente_ativo("clon-c-n"):
        colaboradores = repositorio.obter().listar_colaboradores()
        assert [c["email"] for c in colaboradores] == [OPERADOR]
        assert colaboradores[0]["perfil"] == "admin"


def test_clonagem_nomes_vem_do_formulario_e_nao_do_base():
    _preparar_base("clon-n-b")
    registro.criar_ambiente(
        "clon-n-n", "Projeto do formulário", "Cliente do formulário", OPERADOR, base="clon-n-b"
    )

    novo = registro.obter().obter("clon-n-n")
    assert novo["projeto"] == "Projeto do formulário"
    assert novo["cliente"] == "Cliente do formulário"


def test_criar_sem_base_produz_ambiente_vazio_e_utilizavel():
    registro.criar_ambiente("clon-vazio", "Projeto Vazio", "Cliente Vazio", OPERADOR)

    with ambiente.ambiente_ativo("clon-vazio"):
        repo = repositorio.obter()
        assert repo.listar_atividades() == []
        assert repo.listar_cadastro("unidades") == []
        assert repo.obter_parametros()["meta_aderencia"] == 60.0
        colaboradores = repo.listar_colaboradores()
        assert [c["email"] for c in colaboradores] == [OPERADOR]
        assert colaboradores[0]["perfil"] == "admin"


def test_criar_com_slug_invalido_nao_deixa_pasta_fantasma():
    from src.core.repositorio import diretorio_de_dados

    with pytest.raises(InvalidoError):
        registro.criar_ambiente("CLONE ERRO", "Projeto", "Cliente", OPERADOR)

    assert not (diretorio_de_dados() / "CLONE ERRO").exists()


# ── Perfil operador ───────────────────────────────────────────────────────
# O papel global vem da configuração da implantação, e só dela. Entra em
# todo ambiente: com o perfil do cadastro quando o cadastro existe, como
# administrador sintético quando não.

OPERADOR_EMAIL = "gestao@timenow.com.br"


def _colaborador(email: str, perfil: str = "fiscal") -> dict:
    return {
        "nome": f"Pessoa {email}",
        "email": email,
        "perfil": perfil,
        "vinculo": "timenow",
        "empresa": "",
        "ativo": True,
    }


def _ambiente_com_colaboradores(slug: str, colaboradores: list[dict]) -> None:
    with ambiente.ambiente_ativo(slug):
        repo = repositorio.obter()
        for colaborador in colaboradores:
            repo.gravar_colaborador(colaborador)


def test_operador_sem_cadastro_entra_como_admin_e_nao_e_gravado(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_OPERADORES", OPERADOR_EMAIL)
    _ambiente_com_colaboradores("op-sem-cadastro", [_colaborador("fiscal@exemplo.com")])

    with ambiente.ambiente_ativo("op-sem-cadastro"):
        usuario = auth.resolver_por_email(OPERADOR_EMAIL)

    assert usuario is not None
    assert usuario.perfil == "admin"
    assert usuario.vinculo == "timenow"
    assert usuario.operador

    with ambiente.ambiente_ativo("op-sem-cadastro"):
        emails = [c["email"] for c in repositorio.obter().listar_colaboradores()]
    assert OPERADOR_EMAIL not in emails


def test_operador_com_cadastro_entra_com_o_perfil_do_cadastro(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_OPERADORES", OPERADOR_EMAIL)
    _ambiente_com_colaboradores("op-com-cadastro", [_colaborador(OPERADOR_EMAIL, "fiscal")])

    with ambiente.ambiente_ativo("op-com-cadastro"):
        usuario = auth.resolver_por_email(OPERADOR_EMAIL)

    assert usuario is not None
    assert usuario.perfil == "fiscal"
    assert usuario.operador
    assert rbac.CONCEDER_ACESSO in usuario.permissions


def test_email_fora_da_variavel_e_fora_do_cadastro_continua_recusado(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_OPERADORES", OPERADOR_EMAIL)
    _ambiente_com_colaboradores("op-recusa", [_colaborador("fiscal@exemplo.com")])

    with ambiente.ambiente_ativo("op-recusa"):
        assert auth.resolver_por_email("ninguem@exemplo.com") is None


def test_operador_conta_na_quantidade_de_pessoas_com_acesso(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_OPERADORES", f"{OPERADOR_EMAIL};outro.operador@timenow.com.br")
    colaboradores = [_colaborador("fiscal@exemplo.com"), _colaborador(OPERADOR_EMAIL, "planejador")]

    assert auth.conta_pessoas_com_acesso(colaboradores) == 3  # 2 + 1 ausente


def test_listagem_marcada_traz_operador_uma_vez_e_sintetico(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_OPERADORES", f"{OPERADOR_EMAIL};outro.operador@timenow.com.br")
    colaboradores = [_colaborador(OPERADOR_EMAIL, "fiscal"), _colaborador("fiscal@exemplo.com")]

    linhas = auth.colaboradores_com_operadores(colaboradores)

    por_email = {linha["email"]: linha for linha in linhas}
    assert len(linhas) == 3
    assert por_email[OPERADOR_EMAIL]["operador"] is True
    assert por_email[OPERADOR_EMAIL]["perfil"] == "fiscal"
    assert por_email["outro.operador@timenow.com.br"]["operador"] is True
    assert por_email["outro.operador@timenow.com.br"]["sintetico"] is True
    assert por_email["fiscal@exemplo.com"].get("operador") is None


def test_permissoes_do_operador_nao_pertencem_a_nenhum_perfil():
    for perfil in rbac.PERFIS:
        assert rbac.PERMISSOES_OPERADOR.isdisjoint(rbac.resolve([perfil]))


def test_variavel_vazia_nao_quebra_a_resolucao(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_OPERADORES", "")
    _ambiente_com_colaboradores("op-vazio", [_colaborador("fiscal@exemplo.com")])

    with ambiente.ambiente_ativo("op-vazio"):
        assert auth.resolver_por_email("ninguem@exemplo.com") is None
        usuario = auth.resolver_por_email("fiscal@exemplo.com")
        assert usuario is not None and usuario.perfil == "fiscal"
    assert auth.operadores() == []


# ── Resolução do ambiente por requisição ─────────────────────────────────
# A costura HTTP: o cookie é pista, nunca autorização — conferido contra o
# registro em toda requisição, com o cabeçalho (ou a query) da aba.


def _requisicao(
    *,
    cookie: str = "",
    cabecalho: str = "",
    email: str = "",
    bearer: str = "",
    sem_alpine: bool = False,
    parametros: dict | None = None,
    metodo: str = "GET",
    corpo: bytes = b"",
) -> func.HttpRequest:
    headers = {} if sem_alpine else {"X-Alpine-Request": "true"}
    if cookie:
        headers["Cookie"] = f"tn_ambiente={cookie}"
    if cabecalho:
        headers["X-TN-Ambiente"] = cabecalho
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    if email:
        principal = {"userDetails": email, "claims": [{"typ": "email", "val": email}]}
        headers["X-MS-CLIENT-PRINCIPAL"] = base64.b64encode(json.dumps(principal).encode()).decode()
    if corpo:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    return func.HttpRequest(
        method=metodo,
        url="/api/qualquer",
        headers=headers,
        params=parametros or {},
        route_params={},
        body=corpo,
    )


def _registrar_env_http(
    slug: str, *, membros: tuple[str, ...] = (), arquivado: bool = False
) -> None:
    """Cria o ambiente e dá acesso a quem for pedido.

    Cadastrar a pessoa como colaboradora do ambiente **é** conceder o
    acesso (revisão 3, item 1), e o índice do registro acompanha. Gravar
    só no índice produziria alguém que vê a caixa no seletor e é recusado
    ao entrar, porque a resolução do usuário lê o cadastro.
    """
    registro.obter().criar(slug, f"Projeto {slug}", f"Cliente {slug}", OPERADOR)
    for membro in membros:
        with ambiente.ambiente_ativo(slug):
            repositorio.obter().gravar_colaborador(
                {"email": membro, "nome": membro, "perfil": "admin", "ativo": True}
            )
            dados.sincronizar_acesso(OPERADOR)
    if arquivado:
        registro.obter().arquivar(slug, OPERADOR)


def test_cookie_ausente_recusa():
    with pytest.raises(_comum.AmbienteRecusadoError):
        _comum.resolver_ambiente(_requisicao(email="pessoa@exemplo.com"))


def test_ambiente_inexistente_recusa():
    with pytest.raises(_comum.AmbienteRecusadoError):
        _comum.resolver_ambiente(_requisicao(cookie="htt-fantasma", email="pessoa@exemplo.com"))


def test_ambiente_arquivado_recusa():
    _registrar_env_http("htt-arq", membros=("pessoa@exemplo.com",), arquivado=True)
    with pytest.raises(_comum.AmbienteRecusadoError, match="arquivado"):
        _comum.resolver_ambiente(_requisicao(cookie="htt-arq", email="pessoa@exemplo.com"))


def test_email_nao_membro_recusa():
    _registrar_env_http("htt-membros", membros=("pessoa@exemplo.com",))
    with pytest.raises(_comum.AmbienteRecusadoError, match=re.escape("nao-membro@fora.com")):
        _comum.resolver_ambiente(_requisicao(cookie="htt-membros", email="nao-membro@fora.com"))


def test_cabecalho_divergente_recusa():
    _registrar_env_http("htt-a", membros=("pessoa@exemplo.com",))
    _registrar_env_http("htt-b", membros=("pessoa@exemplo.com",))
    with pytest.raises(_comum.AmbienteRecusadoError, match="outro ambiente"):
        _comum.resolver_ambiente(
            _requisicao(cookie="htt-a", cabecalho="htt-b", email="pessoa@exemplo.com")
        )
    with pytest.raises(_comum.AmbienteRecusadoError, match="outro ambiente"):
        _comum.resolver_ambiente(
            _requisicao(
                cookie="htt-a", email="pessoa@exemplo.com", parametros={"ambiente": "htt-b"}
            )
        )


def test_cookie_valido_de_membro_resolve():
    _registrar_env_http("htt-ok", membros=("pessoa@exemplo.com",))
    slug = _comum.resolver_ambiente(_requisicao(cookie="htt-ok", email="pessoa@exemplo.com"))
    assert slug == "htt-ok"


def test_operador_passa_sem_ser_membro(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_OPERADORES", OPERADOR_EMAIL)
    _registrar_env_http("htt-operador")

    slug = _comum.resolver_ambiente(_requisicao(cookie="htt-operador", email=OPERADOR_EMAIL))
    assert slug == "htt-operador"


def test_decorador_abre_o_ambiente_certo_e_fecha_no_fim():
    _registrar_env_http("htt-deco", membros=("pessoa@exemplo.com",))
    with ambiente.ambiente_ativo("htt-deco"):
        repositorio.obter().gravar_colaborador(_colaborador("pessoa@exemplo.com", "admin"))

    visto = {}

    @_comum.com_usuario()
    def falso(req, user):
        visto["slug"] = ambiente.slug_ativo()
        visto["email"] = user.email
        return func.HttpResponse("ok")

    resposta = falso(_requisicao(cookie="htt-deco", email="pessoa@exemplo.com"))
    assert resposta.get_body().decode() == "ok"
    assert visto == {"slug": "htt-deco", "email": "pessoa@exemplo.com"}
    with pytest.raises(ambiente.SemAmbienteError):
        ambiente.slug_ativo()


def test_decorador_fecha_o_contexto_mesmo_com_excecao():
    _registrar_env_http("htt-exc", membros=("pessoa@exemplo.com",))
    with ambiente.ambiente_ativo("htt-exc"):
        repositorio.obter().gravar_colaborador(_colaborador("pessoa@exemplo.com", "admin"))

    @_comum.com_usuario()
    def explodir(req, user):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        explodir(_requisicao(cookie="htt-exc", email="pessoa@exemplo.com"))
    with pytest.raises(ambiente.SemAmbienteError):
        ambiente.slug_ativo()


def test_recusa_de_ambiente_redireciona_em_vez_de_preencher_o_alvo():
    _registrar_env_http("htt-redir", membros=("pessoa@exemplo.com",), arquivado=True)

    @_comum.com_usuario()
    def falso(req, user):
        return func.HttpResponse("ok")

    resposta = falso(
        _requisicao(cookie="htt-redir", email="pessoa@exemplo.com", cabecalho="htt-redir")
    )
    assert resposta.status_code == 302
    local = resposta.headers["Location"]
    assert local.startswith("/index.html?recusa=")
    assert "arquivado" in unquote(local)


def test_com_sessao_responde_sem_ambiente_e_sem_cadastro(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_MODO", "producao")

    @_comum.com_sessao
    def falso(req, usuario):
        return func.HttpResponse(usuario.email)

    resposta = falso(_requisicao(email="pessoa@exemplo.com"))
    assert resposta.get_body().decode() == "pessoa@exemplo.com"


def test_com_sessao_demo_devolve_identidade_fixa_operadora(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_MODO", "demo")
    visto = {}

    @_comum.com_sessao
    def falso(req, usuario):
        visto["email"] = usuario.email
        visto["operador"] = usuario.operador
        return func.HttpResponse("demo")

    resposta = falso(_requisicao())
    assert resposta.get_body().decode() == "demo"
    assert visto == {"email": auth.DEMO_EMAIL, "operador": True}


def test_guarda_nomeia_o_email_e_uma_causa_por_barreira(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_MODO", "producao")
    _registrar_env_http("htt-causas", membros=("pessoa@exemplo.com",))
    _registrar_env_http("htt-causas-arq", membros=("pessoa@exemplo.com",), arquivado=True)

    sem_email = _comum.com_sessao(lambda req, u: func.HttpResponse("ok"))(_requisicao())
    assert _comum.MENSAGEM_SEM_EMAIL in sem_email.get_body().decode()

    fora_do_registro = _comum.com_usuario()(lambda req, u: func.HttpResponse("ok"))(
        _requisicao(cookie="htt-causas", email="alguem@fora.com")
    )
    local_registro = unquote(fora_do_registro.headers["Location"])
    assert "alguem@fora.com" in local_registro
    assert "registro de ambientes" in local_registro

    # Índice e cadastro podem divergir por um instante — outra sessão
    # removeu a pessoa, ou o arquivo foi editado à mão. A barreira do
    # cadastro continua sendo a que decide, e é isso que esta parte
    # afirma: membro no índice, ausente do cadastro, recusado.
    registro.obter().conceder("htt-causas", "divergente@exemplo.com", OPERADOR)
    fora_do_cadastro = _comum.com_usuario()(lambda req, u: func.HttpResponse("ok"))(
        _requisicao(cookie="htt-causas", email="divergente@exemplo.com")
    )
    corpo_cadastro = fora_do_cadastro.get_body().decode()
    assert "divergente@exemplo.com" in corpo_cadastro
    assert "Projeto htt-causas" in corpo_cadastro

    arquivado = _comum.com_usuario()(lambda req, u: func.HttpResponse("ok"))(
        _requisicao(cookie="htt-causas-arq", email="pessoa@exemplo.com")
    )
    local_arquivado = unquote(arquivado.headers["Location"])
    assert "arquivado" in local_arquivado

    mensagens = {sem_email.get_body().decode(), local_registro, corpo_cadastro, local_arquivado}
    assert len(mensagens) == 4


def test_download_sem_cabecalho_alpine_confere_a_query():
    _registrar_env_http("htt-dl", membros=("pessoa@exemplo.com",))
    with ambiente.ambiente_ativo("htt-dl"):
        repositorio.obter().gravar_colaborador(_colaborador("pessoa@exemplo.com", "admin"))

    @_comum.com_download(rbac.EXPORTAR)
    def baixar(req, user):
        return func.HttpResponse(user.email)

    valida = baixar(
        _requisicao(
            cookie="htt-dl",
            email="pessoa@exemplo.com",
            sem_alpine=True,
            parametros={"ambiente": "htt-dl"},
        )
    )
    assert valida.get_body().decode() == "pessoa@exemplo.com"

    divergente = baixar(
        _requisicao(
            cookie="htt-dl",
            email="pessoa@exemplo.com",
            sem_alpine=True,
            parametros={"ambiente": "htt-fantasma"},
        )
    )
    assert divergente.status_code == 302


def test_recorte_por_fornecedor_continua_dentro_do_ambiente():
    with ambiente.ambiente_ativo("htt-escopo"):
        repo = repositorio.obter()
        atividade_a = _atividade("ESC-A")
        atividade_a["empresa"] = "Empresa A"
        atividade_b = _atividade("ESC-B")
        atividade_b["empresa"] = "Empresa B"
        repo.gravar_atividade(atividade_a)
        repo.gravar_atividade(atividade_b)
        repo.gravar_colaborador(
            {
                **_colaborador("forn@a.com", "fornecedor"),
                "empresa": "Empresa A",
                "vinculo": "fornecedor",
            }
        )

    with ambiente.ambiente_ativo("htt-escopo"):
        usuario = auth.resolver_por_email("forn@a.com")
        assert usuario is not None and usuario.vinculo == "fornecedor"
        atividades = dados.listar_atividades(usuario, "S.30/2026")
        assert [a["id_exclusiva"] for a in atividades] == ["ESC-A"]


# ── O seletor de ambientes ────────────────────────────────────────────────
# A primeira tela depois do SSO: uma caixa por ambiente acessível, a
# entrada automática de quem tem um só e a explicação de quem não tem
# nenhum. Roda em `com_sessao`, sem ambiente ativo.


def _corpo(resposta: func.HttpResponse) -> str:
    return (resposta.get_body() or b"").decode("utf-8", errors="replace")


def test_seletor_mostra_uma_caixa_por_ambiente():
    _registrar_env_http("sel-a", membros=("pessoa@exemplo.com",))
    _registrar_env_http("sel-b", membros=("pessoa@exemplo.com",))

    resposta = ambientes.seletor(
        _requisicao(email="pessoa@exemplo.com", parametros={"destino": "/_views/home.html"})
    )

    corpo = _corpo(resposta)
    assert resposta.status_code == 200
    assert "Projeto sel-a" in corpo and "Cliente sel-a" in corpo
    assert "Projeto sel-b" in corpo and "Cliente sel-b" in corpo
    assert 'data-ambiente="sel-a"' in corpo
    assert 'data-ambiente="sel-b"' in corpo


def test_seletor_com_um_ambiente_ainda_pede_a_escolha():
    """História 3 revogada: o seletor é a tela inicial permanente.

    Quem tem um ambiente só também escolhe. O clique deixou de ser um
    passo sem alternativa e virou a confirmação consciente de em qual
    cliente a pessoa vai trabalhar (revisão 3, item 3).
    """
    _registrar_env_http("sel-unico", membros=("pessoa@exemplo.com",))

    resposta = ambientes.seletor(
        _requisicao(email="pessoa@exemplo.com", parametros={"destino": "/_views/home.html"})
    )

    corpo = _corpo(resposta)
    assert 'data-ambiente="sel-unico"' in corpo
    assert "escolher($el.dataset.ambiente" in corpo
    assert 'x-init="escolher(' not in corpo  # ninguém entra sem clicar


def test_seletor_sem_ambiente_mostra_a_explicacao():
    resposta = ambientes.seletor(_requisicao(email="sem-nada@exemplo.com"))

    corpo = _corpo(resposta)
    assert "Nenhum ambiente disponível" in corpo
    assert "Peça a liberação" in corpo
    assert "data-ambiente=" not in corpo


def test_seletor_mostra_a_recusa_sem_auto_entrar():
    _registrar_env_http("sel-recusa", membros=("pessoa@exemplo.com",))

    resposta = ambientes.seletor(
        _requisicao(
            email="pessoa@exemplo.com",
            parametros={"destino": "/_views/home.html", "recusa": "Este ambiente foi arquivado."},
        )
    )

    corpo = _corpo(resposta)
    assert "Este ambiente foi arquivado." in corpo
    assert "x-init=" not in corpo  # com recusa, ninguém entra sem clicar


def test_operador_ve_todos_os_ativos_e_nao_os_arquivados(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_OPERADORES", OPERADOR_EMAIL)
    _registrar_env_http("sel-op-a")
    _registrar_env_http("sel-op-b", arquivado=True)

    resposta = ambientes.seletor(_requisicao(email=OPERADOR_EMAIL))

    corpo = _corpo(resposta)
    assert "Projeto sel-op-a" in corpo
    assert "Projeto sel-op-b" not in corpo


def test_escolher_validada_redireciona_para_o_destino():
    _registrar_env_http("sel-valida", membros=("pessoa@exemplo.com",))

    resposta = ambientes.escolher(
        _requisicao(
            email="pessoa@exemplo.com",
            metodo="POST",
            corpo=b"ambiente=sel-valida&destino=%2F_programacao",
        )
    )

    assert resposta.status_code == 302
    assert resposta.headers["Location"] == "/_programacao"


def test_escolher_invalida_recusa_com_a_mensagem():
    resposta = ambientes.escolher(
        _requisicao(
            email="pessoa@exemplo.com",
            metodo="POST",
            corpo=b"ambiente=sel-fantasma&destino=%2F_programacao",
        )
    )

    assert resposta.status_code == 302
    local = resposta.headers["Location"]
    assert local.startswith("/index.html?recusa=")
    assert "inválida" in unquote(local)


def test_cookie_do_seletor_e_de_sessao_e_legivel_por_js():
    _registrar_env_http("sel-cookie", membros=("pessoa@exemplo.com",))

    resposta = ambientes.seletor(
        _requisicao(email="pessoa@exemplo.com", parametros={"destino": "/_views/home.html"})
    )

    corpo = _corpo(resposta)
    assert "tn_ambiente=' + ambiente + ';path=/;SameSite=Lax" in corpo
    assert "Max-Age" not in corpo


# ── A sidebar nunca mente sobre onde você está ────────────────────────────


def _ambiente_com_membro(slug: str, email: str = "pessoa@exemplo.com") -> None:
    _registrar_env_http(slug, membros=(email,))
    with ambiente.ambiente_ativo(slug):
        repositorio.obter().gravar_colaborador(_colaborador(email, "admin"))


def test_sidebar_mostra_o_projeto_do_registro_e_a_troca():
    _ambiente_com_membro("sb-a")
    _registrar_env_http("sb-b", membros=("pessoa@exemplo.com",))

    resposta = nav.main_nav(_requisicao(cookie="sb-a", email="pessoa@exemplo.com"))

    corpo = _corpo(resposta)
    assert "Projeto sb-a" in corpo  # vem do registro, não dos parâmetros
    assert "Projeto McCain" not in corpo
    assert "Trocar de ambiente" in corpo
    assert "Projeto sb-b" in corpo


def test_sidebar_nao_oferece_troca_a_quem_tem_um_ambiente_so():
    _ambiente_com_membro("sb-unica")

    resposta = nav.main_nav(_requisicao(cookie="sb-unica", email="pessoa@exemplo.com"))

    corpo = _corpo(resposta)
    assert "Projeto sb-unica" in corpo
    assert "Trocar de ambiente" not in corpo


def test_sidebar_lista_so_ativos_onde_e_membro():
    _ambiente_com_membro("sb-membro")
    _registrar_env_http("sb-arquivado", membros=("pessoa@exemplo.com",), arquivado=True)
    _registrar_env_http("sb-alheio")

    resposta = nav.main_nav(_requisicao(cookie="sb-membro", email="pessoa@exemplo.com"))

    corpo = _corpo(resposta)
    assert "Trocar de ambiente" not in corpo  # só um ativo onde é membro
    assert "Projeto sb-arquivado" not in corpo
    assert "Projeto sb-alheio" not in corpo


# ── O nome vem só do registro ─────────────────────────────────────────────
# Os campos de projeto e cliente saíram dos parâmetros do ambiente; a
# fonte única é o registro. Todos os leitores — sidebar, dashboard,
# Configurações, planilha e relatório — mostram o nome do registro.


def test_parametros_de_um_ambiente_novo_nao_tem_projeto_nem_cliente():
    registro.criar_ambiente("nome-sem-campos", "Projeto X", "Cliente X", OPERADOR)

    with ambiente.ambiente_ativo("nome-sem-campos"):
        parametros = repositorio.obter().obter_parametros()

    assert "projeto" not in parametros
    assert "cliente" not in parametros


def test_configuracoes_exibe_o_nome_em_leitura():
    _ambiente_com_membro("nome-config")

    resposta = configuracoes.geral(_requisicao(cookie="nome-config", email="pessoa@exemplo.com"))

    corpo = _corpo(resposta)
    assert "Projeto nome-config" in corpo
    assert "Cliente nome-config" in corpo
    assert 'name="projeto"' not in corpo
    assert 'name="cliente"' not in corpo


def test_relatorio_traz_o_nome_do_registro():
    _ambiente_com_membro("nome-relatorio")

    resposta = exportacao.relatorio(
        _requisicao(
            cookie="nome-relatorio",
            email="pessoa@exemplo.com",
            parametros={"semana": "S.30/2026"},
        )
    )

    corpo = _corpo(resposta)
    assert "Projeto nome-relatorio" in corpo
    assert "Cliente nome-relatorio" in corpo


def test_planilha_exportada_traz_o_nome_do_registro():
    _ambiente_com_membro("nome-planilha")

    resposta = exportacao.exportar(
        _requisicao(
            cookie="nome-planilha",
            email="pessoa@exemplo.com",
            sem_alpine=True,
            parametros={"ambiente": "nome-planilha", "semana": "S.30/2026"},
        )
    )

    assert resposta.status_code == 200
    capa = load_workbook(BytesIO(resposta.get_body()))["Resumo"]
    assert capa["A1"].value == "Projeto nome-planilha"
    assert "Cliente nome-planilha" in str(capa["A2"].value)


def test_leitores_refletem_renomeacao_no_registro_sem_tocar_a_base():
    _ambiente_com_membro("nome-renomeado")
    parametros_antes = None
    with ambiente.ambiente_ativo("nome-renomeado"):
        parametros_antes = repositorio.obter().obter_parametros()

    # Renomear o cliente é editar o registro — o JSON é a implementação
    # de hoje, e não existe API de renomeação. O leitor não pode cachear.
    caminho = diretorio_de_dados() / "registro.json"
    registro_cru = json.loads(caminho.read_text(encoding="utf-8"))
    for ambiente_registrado in registro_cru["ambientes"]:
        if ambiente_registrado["id"] == "nome-renomeado":
            ambiente_registrado["projeto"] = "Projeto Renomeado"
            ambiente_registrado["cliente"] = "Cliente Renomeado"
    caminho.write_text(json.dumps(registro_cru), encoding="utf-8")

    resposta = nav.main_nav(_requisicao(cookie="nome-renomeado", email="pessoa@exemplo.com"))
    assert "Projeto Renomeado" in _corpo(resposta)

    with ambiente.ambiente_ativo("nome-renomeado"):
        assert repositorio.obter().obter_parametros() == parametros_antes


# ── Modo demonstração ─────────────────────────────────────────────────────
# O duplo clique abre o seletor com duas caixas, cada uma com o histórico
# determinístico. Fora da demonstração, ambiente novo nasce vazio.


def test_registro_demo_nasce_com_dois_ambientes(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_MODO", "demo")

    ambientes_demo = registro.obter().listar_todos()

    assert [a["id"] for a in ambientes_demo] == ["demo-obra", "demo-planta"]
    assert all(a["situacao"] == "ativo" for a in ambientes_demo)


def test_ambiente_demo_nasce_com_o_historico(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_MODO", "demo")

    with ambiente.ambiente_ativo("demo-obra"):
        atividades = repositorio.obter().listar_atividades()
        colaboradores = repositorio.obter().listar_colaboradores()

    assert len(atividades) > 0
    assert len(colaboradores) > 1


def test_ambiente_criado_fora_da_demonstracao_nasce_vazio(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_MODO", "demo")
    registro.criar_ambiente("demo-criado", "Projeto Criado", "Cliente Criado", OPERADOR)

    with ambiente.ambiente_ativo("demo-criado"):
        assert repositorio.obter().listar_atividades() == []


def test_ambiente_demo_nao_nasce_com_historico_fora_do_modo_demo():
    # Produção (padrão do conftest): um slug de demonstração é só um slug.
    # O slug foi usado por outro teste — a costura devolve a chave à
    # resolução regular, que constrói contra o diretório temporário daqui.
    repositorio.definir("demo-obra", None)
    with ambiente.ambiente_ativo("demo-obra"):
        assert repositorio.obter().listar_atividades() == []


# ── Área do operador — a administração em tela ────────────────────────────
# A tela só chama o que o comando já fazia rodar: nenhuma regra nova no
# blueprint. O operador é quem vê a área; o resto é recusado.


def test_administracao_recusa_quem_nao_e_operador():
    resposta = ambientes.administracao(_requisicao(email="pessoa@exemplo.com"))

    assert resposta.status_code == 403
    assert "não tem acesso" in _corpo(resposta)


def test_listagem_mostra_todos_e_contagem_inclui_operadores(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_OPERADORES", OPERADOR_EMAIL)
    _registrar_env_http("adm-ativo")
    with ambiente.ambiente_ativo("adm-ativo"):
        repositorio.obter().gravar_colaborador(_colaborador("fiscal@exemplo.com"))
    _registrar_env_http("adm-arq", arquivado=True)

    resposta = ambientes.administracao(_requisicao(email=OPERADOR_EMAIL))

    corpo = _corpo(resposta)
    assert resposta.status_code == 200
    assert "Projeto adm-ativo" in corpo
    assert "Projeto adm-arq" in corpo
    assert "Arquivado" in corpo
    # 1 colaborador + 1 operador ausente do cadastro = 2 pessoas
    assert 'td-center">2<' in corpo


def test_seletor_mostra_administracao_so_ao_operador(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_OPERADORES", OPERADOR_EMAIL)
    _registrar_env_http("adm-sel", membros=(OPERADOR_EMAIL,))

    como_operador = ambientes.seletor(_requisicao(email=OPERADOR_EMAIL))
    assert "/api/ambientes-administracao" in _corpo(como_operador)

    como_membro = ambientes.seletor(_requisicao(email="pessoa@exemplo.com"))
    assert "/api/ambientes-administracao" not in _corpo(como_membro)


# ── Criar ambiente pela tela ─────────────────────────────────────────────


def test_formulario_de_criacao_enuncia_o_que_copia_e_o_que_nao(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_OPERADORES", OPERADOR_EMAIL)

    resposta = ambientes.criar_form(_requisicao(email=OPERADOR_EMAIL))

    corpo = _corpo(resposta)
    assert "Copiado do ambiente base" in corpo
    assert "Não copiado" in corpo
    assert "janelas de programação" in corpo
    assert "colaboradores" in corpo


def test_criar_pela_tela_e_pelo_comando_sao_equivalentes(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_OPERADORES", OPERADOR_EMAIL)
    _preparar_base("tela-base")

    registro.criar_ambiente(
        "tela-cmd", "Projeto Igual", "Cliente Igual", OPERADOR_EMAIL, base="tela-base"
    )
    resposta = ambientes.criar_env(
        _requisicao(
            email=OPERADOR_EMAIL,
            metodo="POST",
            corpo=b"identificador=tela-web&projeto=Projeto+Igual&cliente=Cliente+Igual&base=tela-base",
        )
    )
    assert resposta.status_code == 200

    with ambiente.ambiente_ativo("tela-cmd"):
        cmd = repositorio.obter()
        unidades_cmd = cmd.listar_cadastro("unidades")
        parametros_cmd = cmd.obter_parametros()
        emails_cmd = [c["email"] for c in cmd.listar_colaboradores()]
    with ambiente.ambiente_ativo("tela-web"):
        web = repositorio.obter()
        assert web.listar_cadastro("unidades") == unidades_cmd
        assert web.obter_parametros() == parametros_cmd
        assert [c["email"] for c in web.listar_colaboradores()] == emails_cmd
    assert registro.obter().obter("tela-web")["projeto"] == "Projeto Igual"


def test_criar_pela_tela_recusa_slug_invalido_com_a_mensagem_da_porta(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_OPERADORES", OPERADOR_EMAIL)

    resposta = ambientes.criar_env(
        _requisicao(
            email=OPERADOR_EMAIL,
            metodo="POST",
            corpo=b"identificador=SLUG+ERRADO&projeto=P&cliente=C",
        )
    )

    assert resposta.status_code == 422
    assert "é inválido" in _corpo(resposta)


# ── Membros pela tela ────────────────────────────────────────────────────


def test_membros_conceder_revogar_e_operadores_marcados(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_OPERADORES", OPERADOR_EMAIL)
    _registrar_env_http("mem-a")

    concedido = ambientes.conceder_membro(
        _requisicao(
            email=OPERADOR_EMAIL,
            metodo="POST",
            corpo=b"ambiente=mem-a&email=novo%40exemplo.com",
        )
    )
    corpo_concedido = _corpo(concedido)
    assert concedido.status_code == 200
    assert "novo@exemplo.com" in corpo_concedido
    assert OPERADOR_EMAIL in corpo_concedido
    assert "Operador Timenow" in corpo_concedido
    assert registro.obter().listar_membros("mem-a") == ["novo@exemplo.com"]

    revogado = ambientes.revogar_membro(
        _requisicao(
            email=OPERADOR_EMAIL,
            metodo="POST",
            corpo=b"ambiente=mem-a&email=novo%40exemplo.com",
        )
    )
    assert "novo@exemplo.com" not in _corpo(revogado)
    assert registro.obter().listar_membros("mem-a") == []


def test_revogar_operador_pelo_registro_e_recusado(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_OPERADORES", OPERADOR_EMAIL)
    _registrar_env_http("mem-op")

    resposta = ambientes.revogar_membro(
        _requisicao(
            email=OPERADOR_EMAIL,
            metodo="POST",
            corpo=f"ambiente=mem-op&email={OPERADOR_EMAIL}".encode(),
        )
    )

    assert resposta.status_code == 422
    assert "não são revogados" in _corpo(resposta)


def test_conceder_duas_vezes_nao_duplica():
    _registrar_env_http("mem-dup")
    registro.obter().conceder("mem-dup", "pessoa@exemplo.com", OPERADOR)
    registro.obter().conceder("mem-dup", "pessoa@exemplo.com", OPERADOR)

    assert registro.obter().listar_membros("mem-dup").count("pessoa@exemplo.com") == 1


# ── Arquivar e desarquivar pela tela ─────────────────────────────────────


def test_arquivar_e_desarquivar_pela_tela(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_OPERADORES", OPERADOR_EMAIL)
    _registrar_env_http("arq-tela", membros=("pessoa@exemplo.com",))

    arquivado = ambientes.arquivar(
        _requisicao(email=OPERADOR_EMAIL, metodo="POST", corpo=b"ambiente=arq-tela")
    )
    corpo_arquivado = _corpo(arquivado)
    assert "Arquivado" in corpo_arquivado
    guardado = registro.obter().obter("arq-tela")
    assert guardado is not None and "pessoa@exemplo.com" in guardado["membros"]

    desarquivado = ambientes.desarquivar(
        _requisicao(email=OPERADOR_EMAIL, metodo="POST", corpo=b"ambiente=arq-tela")
    )
    assert "Ativo" in _corpo(desarquivado)
    assert [a["id"] for a in registro.obter().listar_por_email("pessoa@exemplo.com")] == [
        "arq-tela"
    ]


# ── Colaboradores marca o operador ───────────────────────────────────────


def test_colaboradores_mostra_operador_marcado(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_OPERADORES", OPERADOR_EMAIL)
    _ambiente_com_membro("col-op")

    resposta = colaboradores.listar(_requisicao(cookie="col-op", email="pessoa@exemplo.com"))

    corpo = _corpo(resposta)
    assert OPERADOR_EMAIL in corpo
    assert "Operador Timenow" in corpo
    assert "Acesso de operação da Timenow" in corpo


def test_remover_operador_pelo_endpoint_e_recusado(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_OPERADORES", OPERADOR_EMAIL)
    _ambiente_com_membro("col-op-rem")

    resposta = colaboradores.remover(
        _requisicao(
            cookie="col-op-rem",
            email="pessoa@exemplo.com",
            metodo="POST",
            corpo=f"email={OPERADOR_EMAIL}".encode(),
        )
    )

    assert resposta.status_code == 403
    assert "não podem ser removidos" in _corpo(resposta)


def test_tela_de_colaboradores_nao_grava_operador_no_cadastro(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_OPERADORES", OPERADOR_EMAIL)
    _ambiente_com_membro("col-nao-grava")

    colaboradores.listar(_requisicao(cookie="col-nao-grava", email="pessoa@exemplo.com"))

    with ambiente.ambiente_ativo("col-nao-grava"):
        emails = [c["email"] for c in repositorio.obter().listar_colaboradores()]
    assert OPERADOR_EMAIL not in emails


def test_contagem_da_tela_bate_com_a_da_listagem(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_OPERADORES", OPERADOR_EMAIL)
    _ambiente_com_membro("col-contagem")
    with ambiente.ambiente_ativo("col-contagem"):
        repositorio.obter().gravar_colaborador(_colaborador("outra@exemplo.com"))

    resposta = colaboradores.listar(_requisicao(cookie="col-contagem", email="pessoa@exemplo.com"))

    # 2 colaboradores + 1 operador ausente = 3, igual ao da listagem
    assert "3 pessoa(s)" in _corpo(resposta)


# ── O espaço de rotas da API de leitura ──────────────────────────────────
# `/api/dados/v1/*` é um espaço à parte: nenhuma rota de fragmento pode
# cair ali, e nenhum verbo de escrita pode existir dentro. A varredura
# substitui a revisão humana da configuração de rotas da borda.


ROTAS_DA_API = {
    "dados/v1/saude",
    "dados/v1/ambiente",
    "dados/v1/atividades",
    "dados/v1/resumo",
    "dados/v1/cadastros",
    "dados/v1/geral",
}


def _tabela_de_rotas() -> list[tuple[str, set[str]]]:
    from function_app import app

    rotas = []
    for construtor in app._function_builders:
        gatilho = construtor._function.get_trigger().get_dict_repr()
        if gatilho.get("type") != "httpTrigger":
            continue
        rota = gatilho.get("route") or ""
        metodos = {str(getattr(m, "value", m)).upper() for m in gatilho.get("methods") or ["GET"]}
        rotas.append((rota, metodos))
    return rotas


def test_nenhuma_rota_de_fragmento_vive_sob_o_prefixo_da_api():
    """O espaço da API contém só as rotas da API — e nada de escrita."""
    rotas = _tabela_de_rotas()

    da_api = [rota for rota, _ in rotas if rota.startswith("dados/")]
    assert set(da_api) == ROTAS_DA_API

    for rota, metodos in rotas:
        if rota.startswith("dados/"):
            assert metodos <= {"GET"}, f"{rota} não pode ter verbo de escrita"

    for rota, _ in rotas:
        assert not (rota.startswith("dados/") and rota not in ROTAS_DA_API)


# ── Token de leitura ──────────────────────────────────────────────────────
# Emitido pelo operador, vinculado a um ambiente, guardado só como hash.
# O valor completo existe uma vez, na emissão.


def _emitir(identificador: str, rotulo: str = "Power BI", validade: str = "") -> dict:
    return registro.obter().emitir_token(identificador, rotulo, OPERADOR, validade=validade)


def test_emissao_devolve_o_valor_uma_vez_e_guarda_so_hash():
    _registrar_env_http("tok-a")
    emitido = _emitir("tok-a")

    assert emitido["valor"].startswith("tn_") and "_" in emitido["valor"]
    cru = (diretorio_de_dados() / "registro.json").read_text(encoding="utf-8")
    assert emitido["valor"] not in cru
    listados = registro.obter().listar_tokens("tok-a")
    assert "hash" not in json.dumps(listados)
    assert "valor" not in json.dumps(listados)
    assert listados[0]["prefixo"] == emitido["prefixo"]
    assert listados[0]["rotulo"] == "Power BI"


def test_verificacao_resolve_o_ambiente_e_recusa_com_motivo():
    _registrar_env_http("tok-b")
    emitido = _emitir("tok-b")

    assert registro.obter().verificar_token(emitido["valor"])["ambiente"] == "tok-b"

    with pytest.raises(InvalidoError, match="malformado"):
        registro.obter().verificar_token("nao-e-token")
    with pytest.raises(InvalidoError, match="inexistente"):
        registro.obter().verificar_token("tn_ab12cd34_segredo_errado")


def test_token_revogado_e_expirado_recusam():
    _registrar_env_http("tok-c")

    vencido = _emitir("tok-c", "Vencido", validade="2020-01-01")
    with pytest.raises(InvalidoError, match="expirado"):
        registro.obter().verificar_token(vencido["valor"])

    revogavel = _emitir("tok-c", "Revogável")
    registro.obter().revogar_token("tok-c", revogavel["prefixo"], OPERADOR)
    with pytest.raises(InvalidoError, match="revogado"):
        registro.obter().verificar_token(revogavel["valor"])

    eventos = registro.obter().recentes(limite=200)
    acoes = [e["acao"] for e in eventos]
    assert "token_emitido" in acoes and "token_revogado" in acoes


def test_token_de_a_nao_alcanca_o_ambiente_b():
    _registrar_env_http("tok-x")
    _registrar_env_http("tok-y")

    emitido = _emitir("tok-x")
    token = registro.obter().verificar_token(emitido["valor"])
    assert token["ambiente"] == "tok-x"


# ── A API de leitura ──────────────────────────────────────────────────────


def test_api_saude_responde_sem_alpine_e_sem_cookie():
    resposta = dados_api.saude(_requisicao(sem_alpine=True))

    assert resposta.status_code == 200
    assert resposta.mimetype == "application/json"
    assert json.loads(resposta.get_body()) == {"status": "ok"}


def test_api_token_valido_responde_no_ambiente_do_token():
    _registrar_env_http("api-a")
    with ambiente.ambiente_ativo("api-a"):
        repositorio.obter().gravar_atividade(_atividade("API-A"))
    _registrar_env_http("api-b")
    emitido = _emitir("api-a")

    resposta = dados_api.recurso_atividades(
        _requisicao(sem_alpine=True, bearer=emitido["valor"], parametros={"semana": "S.30/2026"})
    )

    assert resposta.status_code == 200
    ids = [a["id_exclusiva"] for a in json.loads(resposta.get_body())["dados"]]
    assert "API-A" in ids


def test_api_recusas_sao_json_com_motivo_distinto():
    sem_credencial = dados_api.recurso_ambiente(_requisicao(sem_alpine=True))
    assert sem_credencial.status_code == 401
    assert sem_credencial.mimetype == "application/json"
    assert "Credencial ausente" in json.loads(sem_credencial.get_body())["erro"]

    _registrar_env_http("api-recusa")
    emitido = _emitir("api-recusa")
    registro.obter().revogar_token("api-recusa", emitido["prefixo"], OPERADOR)
    revogado = dados_api.recurso_ambiente(_requisicao(sem_alpine=True, bearer=emitido["valor"]))
    assert revogado.status_code == 401
    assert json.loads(revogado.get_body())["erro"] == "Token revogado."

    malformado = dados_api.recurso_ambiente(_requisicao(sem_alpine=True, bearer="lixo"))
    assert json.loads(malformado.get_body())["erro"] == "Token malformado."


def test_api_token_de_ambiente_arquivado_recusa_e_volta_ao_desarquivar():
    _registrar_env_http("api-arq")
    emitido = _emitir("api-arq")
    registro.obter().arquivar("api-arq", OPERADOR)

    recusado = dados_api.recurso_ambiente(_requisicao(sem_alpine=True, bearer=emitido["valor"]))
    assert recusado.status_code == 403
    assert json.loads(recusado.get_body())["erro"] == "Este ambiente foi arquivado."

    # o token continua existindo — desarquivar devolve a integração
    assert registro.obter().verificar_token(emitido["valor"])["prefixo"] == emitido["prefixo"]
    registro.obter().desarquivar("api-arq", OPERADOR)
    de_volta = dados_api.recurso_ambiente(_requisicao(sem_alpine=True, bearer=emitido["valor"]))
    assert de_volta.status_code == 200


def test_api_nao_le_cookie_nem_cabecalho_de_aba():
    _registrar_env_http("api-tok")
    emitido = _emitir("api-tok")

    resposta = dados_api.recurso_ambiente(
        _requisicao(
            sem_alpine=True, bearer=emitido["valor"], cookie="outro-ambiente", cabecalho="outro"
        )
    )

    corpo = json.loads(resposta.get_body())
    assert resposta.status_code == 200
    assert corpo["ambiente"]["id"] == "api-tok"


def test_api_fecha_o_ambiente_ao_fim_da_requisicao():
    _registrar_env_http("api-fecha")
    emitido = _emitir("api-fecha")

    dados_api.recurso_ambiente(_requisicao(sem_alpine=True, bearer=emitido["valor"]))

    with pytest.raises(ambiente.SemAmbienteError):
        ambiente.slug_ativo()


def test_atividades_sem_semana_devolve_todo_o_historico():
    """Revisão 4: a semana é filtro, não obrigação. Sem ela, tudo."""
    _registrar_env_http("api-sem-semana")
    with ambiente.ambiente_ativo("api-sem-semana"):
        repo = repositorio.obter()
        repo.gravar_atividade(_atividade("HIST-A", semana="S.30/2026"))
        repo.gravar_atividade(_atividade("HIST-B", semana="S.31/2026"))
    emitido = _emitir("api-sem-semana")

    resposta = dados_api.recurso_atividades(_requisicao(sem_alpine=True, bearer=emitido["valor"]))

    assert resposta.status_code == 200
    ids = {a["id_exclusiva"] for a in json.loads(resposta.get_body())["dados"]}
    assert ids == {"HIST-A", "HIST-B"}


def test_atividades_com_semana_continua_filtrando_uma_so():
    _registrar_env_http("api-com-semana")
    with ambiente.ambiente_ativo("api-com-semana"):
        repo = repositorio.obter()
        repo.gravar_atividade(_atividade("FLT-30", semana="S.30/2026"))
        repo.gravar_atividade(_atividade("FLT-31", semana="S.31/2026"))
    emitido = _emitir("api-com-semana")

    resposta = dados_api.recurso_atividades(
        _requisicao(sem_alpine=True, bearer=emitido["valor"], parametros={"semana": "S.30/2026"})
    )

    ids = {a["id_exclusiva"] for a in json.loads(resposta.get_body())["dados"]}
    assert ids == {"FLT-30"}


def test_atividades_filtram_e_trazem_a_unidade():
    _registrar_env_http("api-filtros")
    with ambiente.ambiente_ativo("api-filtros"):
        repo = repositorio.obter()
        alfa = _atividade("FLT-A")
        alfa["empresa"] = "Empresa Alfa"
        alfa["unidade"] = "m³"
        repo.gravar_atividade(alfa)
        beta = _atividade("FLT-B")
        beta["empresa"] = "Empresa Beta"
        beta["unidade"] = "und"
        repo.gravar_atividade(beta)
    emitido = _emitir("api-filtros")

    todas = dados_api.recurso_atividades(
        _requisicao(sem_alpine=True, bearer=emitido["valor"], parametros={"semana": "S.30/2026"})
    )
    dados_todas = json.loads(todas.get_body())["dados"]
    assert len(dados_todas) == 2
    assert {a["unidade"] for a in dados_todas} == {"m³", "und"}

    filtradas = dados_api.recurso_atividades(
        _requisicao(
            sem_alpine=True,
            bearer=emitido["valor"],
            parametros={"semana": "S.30/2026", "empresa": "Empresa Alfa"},
        )
    )
    assert [a["id_exclusiva"] for a in json.loads(filtradas.get_body())["dados"]] == ["FLT-A"]


# ── /geral — Revisão 5: atividades com o ambiente em cada linha ──────────


def test_geral_traz_as_mesmas_linhas_de_atividades_mais_o_ambiente():
    _registrar_env_http("api-geral")
    with ambiente.ambiente_ativo("api-geral"):
        repo = repositorio.obter()
        repo.gravar_atividade(_atividade("GER-A", semana="S.30/2026"))
        repo.gravar_atividade(_atividade("GER-B", semana="S.31/2026"))
    emitido = _emitir("api-geral")

    resposta = dados_api.recurso_geral(_requisicao(sem_alpine=True, bearer=emitido["valor"]))
    corpo = json.loads(resposta.get_body())
    linhas = corpo["dados"]

    assert resposta.status_code == 200
    assert {a["id_exclusiva"] for a in linhas} == {"GER-A", "GER-B"}
    for linha in linhas:
        assert linha["ambiente_id"] == "api-geral"
        assert linha["ambiente_projeto"] == corpo["ambiente"]["projeto"]
        assert linha["ambiente_cliente"] == corpo["ambiente"]["cliente"]
        # As mesmas colunas de /atividades continuam presentes.
        assert "unidade" in linha
        assert "ppc" in linha
        assert "total_previsto" in linha


def test_geral_sem_semana_bate_com_atividades_sem_semana():
    _registrar_env_http("api-geral-hist")
    with ambiente.ambiente_ativo("api-geral-hist"):
        repo = repositorio.obter()
        repo.gravar_atividade(_atividade("GH-A", semana="S.30/2026"))
        repo.gravar_atividade(_atividade("GH-B", semana="S.31/2026"))
        repo.gravar_atividade(_atividade("GH-C", semana="S.32/2026"))
    emitido = _emitir("api-geral-hist")

    geral = dados_api.recurso_geral(_requisicao(sem_alpine=True, bearer=emitido["valor"]))
    atividades = dados_api.recurso_atividades(_requisicao(sem_alpine=True, bearer=emitido["valor"]))

    ids_geral = {a["id_exclusiva"] for a in json.loads(geral.get_body())["dados"]}
    ids_atividades = {a["id_exclusiva"] for a in json.loads(atividades.get_body())["dados"]}
    assert ids_geral == ids_atividades == {"GH-A", "GH-B", "GH-C"}


def test_geral_com_semana_e_filtro_continua_restringindo():
    _registrar_env_http("api-geral-filtro")
    with ambiente.ambiente_ativo("api-geral-filtro"):
        repo = repositorio.obter()
        alfa = _atividade("GF-A", semana="S.30/2026")
        alfa["empresa"] = "Empresa Alfa"
        repo.gravar_atividade(alfa)
        beta = _atividade("GF-B", semana="S.30/2026")
        beta["empresa"] = "Empresa Beta"
        repo.gravar_atividade(beta)
        repo.gravar_atividade(_atividade("GF-C", semana="S.31/2026"))
    emitido = _emitir("api-geral-filtro")

    resposta = dados_api.recurso_geral(
        _requisicao(
            sem_alpine=True,
            bearer=emitido["valor"],
            parametros={"semana": "S.30/2026", "empresa": "Empresa Alfa"},
        )
    )

    ids = [a["id_exclusiva"] for a in json.loads(resposta.get_body())["dados"]]
    assert ids == ["GF-A"]


def test_geral_token_de_um_ambiente_nao_traz_ambiente_id_de_outro():
    _registrar_env_http("api-geral-a")
    _registrar_env_http("api-geral-b")
    with ambiente.ambiente_ativo("api-geral-a"):
        repositorio.obter().gravar_atividade(_atividade("GA-A"))
    with ambiente.ambiente_ativo("api-geral-b"):
        repositorio.obter().gravar_atividade(_atividade("GB-A"))
    token_a = _emitir("api-geral-a")
    token_b = _emitir("api-geral-b")

    resposta_a = dados_api.recurso_geral(
        _requisicao(sem_alpine=True, bearer=token_a["valor"], parametros={"semana": "S.30/2026"})
    )
    resposta_b = dados_api.recurso_geral(
        _requisicao(sem_alpine=True, bearer=token_b["valor"], parametros={"semana": "S.30/2026"})
    )

    ambientes_vistos_a = {a["ambiente_id"] for a in json.loads(resposta_a.get_body())["dados"]}
    ambientes_vistos_b = {a["ambiente_id"] for a in json.loads(resposta_b.get_body())["dados"]}
    assert ambientes_vistos_a == {"api-geral-a"}
    assert ambientes_vistos_b == {"api-geral-b"}


def test_resumo_da_api_bate_com_o_da_tela():
    _registrar_env_http("api-resumo")
    with ambiente.ambiente_ativo("api-resumo"):
        repo = repositorio.obter()
        a = _atividade("RSM-A")
        a["dias_realizado"] = [0.5] * 7
        repo.gravar_atividade(a)
    emitido = _emitir("api-resumo")

    resposta = dados_api.recurso_resumo(
        _requisicao(sem_alpine=True, bearer=emitido["valor"], parametros={"semana": "S.30/2026"})
    )
    corpo = json.loads(resposta.get_body())

    with ambiente.ambiente_ativo("api-resumo"):
        da_tela = dados.resumo_semana(None, "S.30/2026")

    assert corpo["dados"]["aderencia"] == da_tela["aderencia"]
    assert corpo["dados"]["ppc_medio"] == da_tela["ppc_medio"]
    assert corpo["dados"]["faixa_aderencia"] == calculos.faixa(da_tela["aderencia"])
    assert corpo["ambiente"]["id"] == "api-resumo"
    assert corpo["gerado_em"].endswith("Z")


def test_resumo_sem_semana_agrega_o_historico_sem_por_dia():
    """Revisão 4: agregado geral, sem o balde 'por dia' que misturaria semanas."""
    _registrar_env_http("api-resumo-geral")
    with ambiente.ambiente_ativo("api-resumo-geral"):
        repo = repositorio.obter()
        a = _atividade("RSG-A", semana="S.30/2026")
        a["dias_realizado"] = [0.5] * 7
        repo.gravar_atividade(a)
        b = _atividade("RSG-B", semana="S.31/2026")
        b["dias_realizado"] = [1.0] * 7
        repo.gravar_atividade(b)
    emitido = _emitir("api-resumo-geral")

    resposta = dados_api.recurso_resumo(_requisicao(sem_alpine=True, bearer=emitido["valor"]))
    corpo = json.loads(resposta.get_body())["dados"]

    assert resposta.status_code == 200
    assert corpo["total_atividades"] == 2
    assert corpo["semana"] is None
    assert "por_dia" not in corpo
    assert corpo["por_empresa"]

    with ambiente.ambiente_ativo("api-resumo-geral"):
        todas = dados.listar_todas_atividades(None)
    assert corpo["aderencia"] == calculos.aderencia_geral(todas)
    assert corpo["ppc_medio"] == calculos.ppc_medio(todas)


def test_resumo_com_semana_continua_com_por_dia():
    _registrar_env_http("api-resumo-semanal")
    with ambiente.ambiente_ativo("api-resumo-semanal"):
        repositorio.obter().gravar_atividade(_atividade("RSS-A", semana="S.30/2026"))
    emitido = _emitir("api-resumo-semanal")

    resposta = dados_api.recurso_resumo(
        _requisicao(sem_alpine=True, bearer=emitido["valor"], parametros={"semana": "S.30/2026"})
    )
    corpo = json.loads(resposta.get_body())["dados"]

    assert corpo["semana"] == "S.30/2026"
    assert "por_dia" in corpo


def test_cadastros_do_ambiente_do_token():
    _registrar_env_http("api-cadastros")
    with ambiente.ambiente_ativo("api-cadastros"):
        repositorio.obter().gravar_cadastro("locais", ["Local A"])
    emitido = _emitir("api-cadastros")

    resposta = dados_api.recurso_cadastros(_requisicao(sem_alpine=True, bearer=emitido["valor"]))

    corpo = json.loads(resposta.get_body())
    assert corpo["dados"]["locais"] == ["Local A"]
    assert set(corpo["dados"]) == {"locais", "empresas", "unidades", "fiscais", "encarregados"}


# ── O consumo registrado, com escrita amortizada ──────────────────────────


def test_cem_chamadas_produzem_cem_linhas_e_no_maximo_uma_reescrita(monkeypatch):
    _registrar_env_http("api-cem")
    emitido = _emitir("api-cem")
    porta = registro.obter()

    escritas = {"total": 0}
    original = porta._gravar

    def _contando(dados_registro):
        escritas["total"] += 1
        original(dados_registro)

    monkeypatch.setattr(porta, "_gravar", _contando)

    for _ in range(100):
        resposta = dados_api.recurso_ambiente(_requisicao(sem_alpine=True, bearer=emitido["valor"]))
        assert resposta.status_code == 200

    assert escritas["total"] <= 1
    consumos = [e for e in porta.recentes(limite=200) if e["acao"] == "api"]
    assert len(consumos) == 100
    assert all(e["contexto"]["prefixo"] == emitido["prefixo"] for e in consumos)


def test_recusas_tambem_deixam_rastro_distinguivel():
    dados_api.recurso_ambiente(_requisicao(sem_alpine=True))

    consumos = [e for e in registro.obter().recentes(limite=200) if e["acao"] == "api"]
    assert any(e["contexto"]["recusado"] == "credencial ausente" for e in consumos)


def test_falha_na_trilha_nao_derruba_a_resposta(monkeypatch):
    _registrar_env_http("api-trilha")
    emitido = _emitir("api-trilha")
    porta = registro.obter()

    def _trilha_quebrada():
        raise OSError("disco cheio")

    monkeypatch.setattr(porta, "_trilha", _trilha_quebrada)
    resposta = dados_api.recurso_ambiente(_requisicao(sem_alpine=True, bearer=emitido["valor"]))
    assert resposta.status_code == 200


# ── A tela de tokens do operador ──────────────────────────────────────────


def test_tela_de_tokens_emissao_mostra_o_valor_uma_vez(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_OPERADORES", OPERADOR_EMAIL)
    _registrar_env_http("tkt-a")

    emitido = ambientes.emitir_token(
        _requisicao(
            email=OPERADOR_EMAIL,
            metodo="POST",
            corpo=b"ambiente=tkt-a&rotulo=Power+BI&validade=",
        )
    )
    corpo_emissao = _corpo(emitido)
    assert emitido.status_code == 200
    assert "não será exibido de novo" in corpo_emissao
    assert "histórico inteiro" in _corpo(ambientes.tokens(_requisicao(email=OPERADOR_EMAIL)))

    valor = re.search(r"<code[^>]*>(tn_[^<]+)</code>", corpo_emissao).group(1)
    assert "_" in valor

    # recarregar a tela não mostra o valor em lugar nenhum — só o prefixo
    recarregada = _corpo(ambientes.tokens(_requisicao(email=OPERADOR_EMAIL)))
    assert valor not in recarregada
    segredo = valor.split("_", 2)[2]
    assert segredo not in recarregada


def test_tela_de_tokens_listagem_e_revogacao(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_OPERADORES", OPERADOR_EMAIL)
    _registrar_env_http("tkt-b")
    emitido = registro.obter().emitir_token("tkt-b", "ETL Semanal", OPERADOR_EMAIL)

    listada = _corpo(ambientes.tokens(_requisicao(email=OPERADOR_EMAIL)))
    assert "ETL Semanal" in listada
    assert emitido["prefixo"] in listada
    assert "tkt-b" in listada
    assert "nunca usado" in listada
    assert emitido["valor"] not in listada

    revogado = ambientes.revogar_token(
        _requisicao(
            email=OPERADOR_EMAIL,
            metodo="POST",
            corpo=f"ambiente=tkt-b&prefixo={emitido['prefixo']}".encode(),
        )
    )
    assert "revogado" in _corpo(revogado).lower()
    assert registro.obter().listar_tokens("tkt-b")[0]["revogado"] is True


# ── Revisão 3 · pertencimento com uma edição só (ISSUE-023) ──────────────


def _cadastrar(slug: str, email: str, perfil: str = "fiscal", *, ativo: bool = True) -> None:
    with ambiente.ambiente_ativo(slug):
        repositorio.obter().gravar_colaborador(
            {"email": email, "nome": email, "perfil": perfil, "ativo": ativo}
        )
        dados.sincronizar_acesso(OPERADOR)


def test_cadastrar_colaborador_concede_o_acesso():
    """Uma edição só: cadastrar no ambiente é conceder o acesso."""
    registro.obter().criar("rev3-a", "Projeto A", "Cliente A", OPERADOR)
    assert registro.obter().listar_por_email("nova@exemplo.com") == []

    _cadastrar("rev3-a", "nova@exemplo.com")

    vistos = [a["id"] for a in registro.obter().listar_por_email("nova@exemplo.com")]
    assert vistos == ["rev3-a"]


def test_cadastro_de_um_ambiente_nao_vaza_para_o_outro():
    registro.obter().criar("rev3-b", "Projeto B", "Cliente B", OPERADOR)
    registro.obter().criar("rev3-c", "Projeto C", "Cliente C", OPERADOR)

    _cadastrar("rev3-b", "so-no-b@exemplo.com")

    assert [a["id"] for a in registro.obter().listar_por_email("so-no-b@exemplo.com")] == ["rev3-b"]


def test_desativar_e_remover_tiram_o_ambiente_do_seletor():
    registro.obter().criar("rev3-d", "Projeto D", "Cliente D", OPERADOR)
    _cadastrar("rev3-d", "sai@exemplo.com")
    assert registro.obter().listar_por_email("sai@exemplo.com")

    _cadastrar("rev3-d", "sai@exemplo.com", ativo=False)
    assert registro.obter().listar_por_email("sai@exemplo.com") == []

    _cadastrar("rev3-d", "sai@exemplo.com", ativo=True)
    with ambiente.ambiente_ativo("rev3-d"):
        repositorio.obter().remover_colaborador("sai@exemplo.com")
        dados.sincronizar_acesso(OPERADOR)
    assert registro.obter().listar_por_email("sai@exemplo.com") == []


def test_indice_divergente_e_reconciliado_na_entrada():
    """Um índice que divergiu não tranca do lado de fora quem está cadastrado."""
    registro.obter().criar("rev3-e", "Projeto E", "Cliente E", OPERADOR)
    _cadastrar("rev3-e", "dentro@exemplo.com")

    # Divergência: alguém apaga o índice à mão, sem tocar no cadastro.
    registro.obter().revogar("rev3-e", "dentro@exemplo.com", OPERADOR)
    assert registro.obter().listar_por_email("dentro@exemplo.com") == []

    resposta = ambientes.escolher(
        _requisicao(
            email="dentro@exemplo.com",
            metodo="POST",
            corpo=b"ambiente=rev3-e&destino=%2F_views%2Fhome.html",
        )
    )

    assert resposta.status_code == 302
    assert resposta.headers["Location"] == "/_views/home.html"
    assert [a["id"] for a in registro.obter().listar_por_email("dentro@exemplo.com")] == ["rev3-e"]


def test_sincronizar_so_grava_quando_diverge():
    registro.obter().criar("rev3-f", "Projeto F", "Cliente F", OPERADOR)
    _cadastrar("rev3-f", "estavel@exemplo.com")

    with ambiente.ambiente_ativo("rev3-f"):
        assert dados.sincronizar_acesso(OPERADOR) is False


def test_quem_nao_esta_no_cadastro_nao_entra_mesmo_com_indice():
    registro.obter().criar("rev3-g", "Projeto G", "Cliente G", OPERADOR)
    registro.obter().conceder("rev3-g", "fantasma@exemplo.com", OPERADOR)

    resposta = ambientes.escolher(
        _requisicao(
            email="fantasma@exemplo.com",
            metodo="POST",
            corpo=b"ambiente=rev3-g&destino=%2F",
        )
    )

    assert resposta.headers["Location"].startswith("/index.html?recusa=")


# ── Revisão 3 · operadores promovidos em tela (ISSUE-024) ────────────────


def test_operador_promovido_soma_ao_piso_da_configuracao(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_OPERADORES", "piso@timenow.com.br")
    registro.obter().promover_operador("promovido@timenow.com.br", OPERADOR)

    efetivos = auth.operadores()
    assert "piso@timenow.com.br" in efetivos
    assert "promovido@timenow.com.br" in efetivos
    assert auth.eh_operador("promovido@timenow.com.br")


def test_operador_promovido_enxerga_todos_os_ambientes(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_OPERADORES", "")
    registro.obter().criar("rev3-op", "Projeto Op", "Cliente Op", OPERADOR)
    registro.obter().promover_operador("chefe@timenow.com.br", OPERADOR)

    usuario = auth.Usuario(
        email="chefe@timenow.com.br", operador=auth.eh_operador("chefe@timenow.com.br")
    )
    vistos = [a["id"] for a in _comum.ambientes_da_pessoa(usuario)]

    assert "rev3-op" in vistos


def test_origem_distingue_configuracao_de_promocao(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_OPERADORES", "fixo@timenow.com.br")
    registro.obter().promover_operador("movel@timenow.com.br", OPERADOR)

    origens = {linha["email"]: linha["origem"] for linha in auth.operadores_com_origem()}

    assert origens["fixo@timenow.com.br"] == "configuracao"
    assert origens["movel@timenow.com.br"] == "registro"


def test_operador_da_configuracao_nao_e_rebaixado(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_OPERADORES", "intocavel@timenow.com.br")

    with pytest.raises(InvalidoError):
        registro.obter().rebaixar_operador("intocavel@timenow.com.br", OPERADOR)

    assert auth.eh_operador("intocavel@timenow.com.br")


def test_rebaixar_promovido_tira_o_papel(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_OPERADORES", "")
    registro.obter().promover_operador("temporario@timenow.com.br", OPERADOR)
    assert auth.eh_operador("temporario@timenow.com.br")

    registro.obter().rebaixar_operador("temporario@timenow.com.br", OPERADOR)

    assert not auth.eh_operador("temporario@timenow.com.br")


def test_promover_duas_vezes_e_recusado(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_OPERADORES", "")
    registro.obter().promover_operador("unico@timenow.com.br", OPERADOR)

    with pytest.raises(InvalidoError):
        registro.obter().promover_operador("unico@timenow.com.br", OPERADOR)


def test_promocao_e_rebaixamento_entram_na_trilha(monkeypatch):
    monkeypatch.setenv("PROGRAMACAO_OPERADORES", "")
    registro.obter().promover_operador("trilha@timenow.com.br", OPERADOR)
    registro.obter().rebaixar_operador("trilha@timenow.com.br", OPERADOR)

    acoes = [evento["acao"] for evento in registro.obter().recentes(20)]
    assert "promover" in acoes
    assert "rebaixar" in acoes
