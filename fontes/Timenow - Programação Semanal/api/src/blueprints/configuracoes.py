"""Configurações — four subjects that do not belong on one screen.

* **Geral** — identificação do ambiente (em leitura), metas, regra de
  justificativa de desvio.
* **Cadastros** — locais, empresas e unidades. As listas digitadas.
* **Janelas** — quando cada contratada pode escrever a própria semana.
* **Colaboradores** — quem entra e com qual perfil. Vive em
  ``colaboradores.py``, com permissão própria.

The split is not cosmetic. Each sub-tab is its own endpoint with its own
permission check, so a planner who configures windows never reaches the
screen that grants access — and the menu simply does not show it.
"""

from dataclasses import dataclass, replace

import azure.functions as func

from src.blueprints._comum import (
    campos_do_formulario,
    com_usuario,
    erro_de_dominio,
    registro_do_ambiente_ativo,
)
from src.core import auditoria, auth, calculos, dados, janela, rbac, semanas
from src.core.responses import AlpineAjaxResponse

bp = func.Blueprint()

ANOS_DO_SELETOR = 3


@dataclass(frozen=True)
class Aba:
    """One sub-tab of Configurações.

    Dataclass e não dicionário porque ``permissao`` é consultada pelo
    RBAC e ``restrito`` é um sinal visual — dois tipos diferentes no
    mesmo registro, que num dicionário viram uma união e escondem a
    troca de um pelo outro.
    """

    id: str
    rotulo: str
    icone: str
    href: str
    permissao: str
    restrito: bool = False
    ativa: bool = False


ABAS = (
    Aba("geral", "Geral", "gear", "/api/configuracoes-geral", rbac.VER_CONFIGURACOES),
    Aba(
        "cadastros",
        "Cadastros de apoio",
        "listaPontos",
        "/api/configuracoes-cadastros",
        rbac.VER_CONFIGURACOES,
    ),
    Aba(
        "janelas",
        "Janelas de programação",
        "calendar",
        "/api/configuracoes-janelas",
        rbac.GERIR_JANELAS,
    ),
    # Restrita: é aqui que se concede e revoga acesso à aplicação.
    Aba(
        "colaboradores",
        "Colaboradores",
        "userPlus",
        "/api/colaboradores",
        rbac.GERIR_COLABORADORES,
        restrito=True,
    ),
)


def _abas(user: auth.Usuario, ativa: str) -> list[Aba]:
    """The sub-navigation, already filtered by what the profile may open."""
    return [replace(aba, ativa=aba.id == ativa) for aba in ABAS if user.pode(aba.permissao)]


def _resposta(
    req: func.HttpRequest,
    user: auth.Usuario,
    aba: str,
    contexto: dict,
    *,
    toast: str = "",
) -> func.HttpResponse:
    """Renderiza uma subaba com a sub-navegação já montada.

    O template sai do nome da aba (`configuracoes/janelas.html`) em vez de
    ser passado à parte: eram sempre o mesmo par, e o segundo argumento
    só existia para poder discordar do primeiro.
    """
    return AlpineAjaxResponse(
        template_name=f"configuracoes/{aba}.html",
        context={"user": user, "abas": _abas(user, aba), "aba": aba, **contexto},
        request=req,
        toast=toast or None,
    )


# ── Geral ───────────────────────────────────────────────────────────────


@bp.route(route="configuracoes-geral", methods=["GET"])
@com_usuario(rbac.VER_CONFIGURACOES)
def geral(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    return _resposta(req, user, "geral", _contexto_geral())


def _contexto_geral() -> dict:
    config = dados.parametros()
    return {
        "config": config,
        "ambiente": registro_do_ambiente_ativo(),
        "semanas": dados.horizonte_de_semanas(),
        "semana_atual": semanas.atual(),
        "origem": dados.repositorio_ativo(),
    }


@bp.route(route="configuracoes-geral", methods=["POST"])
@com_usuario(rbac.GERIR_CADASTROS)
def salvar_geral(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    form = req.form
    valores = {
        "meta_aderencia": calculos.numero(form.get("meta_aderencia"), 60.0),
        "meta_ppc": calculos.numero(form.get("meta_ppc"), 75.0),
        "semana_referencia": (form.get("semana_referencia") or "").strip(),
        "exige_justificativa_desvio": form.get("exige_justificativa_desvio") == "sim",
        "limite_desvio_justificativa": calculos.numero(
            form.get("limite_desvio_justificativa"), 15.0
        ),
    }
    try:
        dados.salvar_parametros(user, valores)
    except (dados.InvalidoError, dados.RecusadoError) as erro:
        return erro_de_dominio(erro, req)

    auditoria.registrar("parametros", user.email, "parâmetros do projeto", valores)
    return _resposta(
        req,
        user,
        "geral",
        _contexto_geral(),
        toast="Parâmetros salvos.",
    )


# ── Cadastros de apoio ──────────────────────────────────────────────────

# Só o que é digitado à mão. Fiscais e encarregados saíram daqui: são
# pessoas, e pessoas já são cadastradas em Colaboradores, com perfil,
# vínculo e e-mail. Mantê-los nos dois lugares criava duas listas dos
# mesmos nomes — e a que ficava desatualizada era sempre esta, porque o
# acesso da pessoa é o que alguém lembra de mexer.
ROTULOS_CADASTRO = {
    "locais": ("Locais e frentes", "Onde a atividade acontece."),
    "empresas": ("Empresas contratadas", "Quem executa. Também define a janela."),
    "unidades": ("Unidades de medida", "kg, m², m³, m, und, h."),
}


def _contexto_cadastros(user: auth.Usuario) -> dict:
    atuais = dados.cadastros()
    return {
        "grupos": [
            {
                "nome": nome,
                "titulo": ROTULOS_CADASTRO[nome][0],
                "texto": ROTULOS_CADASTRO[nome][1],
                "valores": atuais.get(nome, []),
            }
            for nome in ROTULOS_CADASTRO
        ],
        # As duas listas que agora vêm de gente, para a tela poder mostrar
        # quem está lá e mandar para o lugar certo de mexer.
        "pessoas": [
            {
                "titulo": "Fiscais",
                "texto": "Quem aprova o realizado.",
                "perfil": "Fiscal",
                "valores": dados.listar_fiscais(),
            },
            {
                "titulo": "Encarregados",
                "texto": "Quem responde pela frente em campo.",
                "perfil": "Encarregado",
                "valores": dados.listar_encarregados(),
            },
        ],
        # O atalho para Colaboradores só aparece para quem consegue abrir
        # a tela. Mandar um planejador para uma porta que o RBAC fecha é
        # pior do que não oferecer o caminho.
        "pode_gerir_pessoas": user.pode(rbac.GERIR_COLABORADORES),
    }


@bp.route(route="configuracoes-cadastros", methods=["GET"])
@com_usuario(rbac.VER_CONFIGURACOES)
def cadastros(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    return _resposta(req, user, "cadastros", _contexto_cadastros(user))


@bp.route(route="configuracoes-cadastro-adicionar", methods=["POST"])
@com_usuario(rbac.GERIR_CADASTROS)
def adicionar(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    campos = campos_do_formulario(req.form, ("tipo", "valor"))
    try:
        valor = dados.adicionar_ao_cadastro(user, campos["tipo"], campos["valor"])
    except (dados.InvalidoError, dados.RecusadoError) as erro:
        return erro_de_dominio(erro, req)

    auditoria.registrar("cadastro", user.email, f"adicionou em {campos['tipo']}: {valor}")
    return _resposta(
        req,
        user,
        "cadastros",
        _contexto_cadastros(user),
        toast=f"“{valor}” cadastrado.",
    )


@bp.route(route="configuracoes-cadastro-remover", methods=["POST"])
@com_usuario(rbac.GERIR_CADASTROS)
def remover(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    campos = campos_do_formulario(req.form, ("tipo", "valor"))
    try:
        valor = dados.remover_do_cadastro(user, campos["tipo"], campos["valor"])
    except (dados.InvalidoError, dados.RecusadoError) as erro:
        return erro_de_dominio(erro, req)

    auditoria.registrar("cadastro", user.email, f"removeu de {campos['tipo']}: {valor}")
    return _resposta(
        req,
        user,
        "cadastros",
        _contexto_cadastros(user),
        toast=f"“{valor}” removido.",
    )


# ── Janelas de programação ──────────────────────────────────────────────


def _anos_do_seletor() -> list[dict]:
    """The years a window may release, with every ISO week of each."""
    inicio = semanas.partes(semanas.atual())[0]
    return [
        {"ano": ano, "semanas": semanas.listar_ano(ano)}
        for ano in range(inicio, inicio + ANOS_DO_SELETOR)
    ]


def _contexto_janelas() -> dict:
    semana_atual = semanas.atual()
    empresas = dados.listar_empresas()
    existentes = {j.get("empresa"): j for j in dados.listar_janelas()}
    return {
        "semana_atual": semana_atual,
        "hoje": semanas.descrever(semana_atual),
        "dias_semana": janela.DIAS_SEMANA,
        "anos": _anos_do_seletor(),
        "janelas": [
            janela.resumo(existentes.get(empresa) or janela.janela_vazia(empresa), semana_atual)
            for empresa in empresas
        ],
    }


@bp.route(route="configuracoes-janelas", methods=["GET"])
@com_usuario(rbac.GERIR_JANELAS)
def janelas(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    return _resposta(req, user, "janelas", _contexto_janelas())


def _semanas_do_formulario(form) -> list[str]:
    """Read the week pills, whichever way the browser sent them."""
    if hasattr(form, "getlist"):
        marcadas = form.getlist("semanas")
    else:
        bruto = form.get("semanas") or ""
        marcadas = bruto.split(",")
    return sorted({s.strip() for s in marcadas if s and s.strip()}, key=semanas.ordem)


@bp.route(route="configuracoes-janela", methods=["POST"])
@com_usuario(rbac.GERIR_JANELAS)
def salvar_janela(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    form = req.form
    empresa = (form.get("empresa") or "").strip()
    atual = dados.obter_janela(empresa) or janela.janela_vazia(empresa)

    dia = (form.get("dia") or "").strip()
    nova = {
        "empresa": empresa,
        "dias": (
            [
                {
                    "dia": dia,
                    "abre": (form.get("abre") or "00:01").strip(),
                    "fecha": (form.get("fecha") or "23:59").strip(),
                }
            ]
            if dia
            else []
        ),
        "semanas_liberadas": _semanas_do_formulario(form),
        "extra": list(atual.get("extra") or []),
    }

    extra_semana = (form.get("extra_semana") or "").strip()
    extra_abre = (form.get("extra_abre") or "").strip()
    extra_fecha = (form.get("extra_fecha") or "").strip()
    if extra_semana and extra_abre and extra_fecha:
        nova["extra"] = [e for e in nova["extra"] if e.get("semana") != extra_semana]
        nova["extra"].append({"semana": extra_semana, "abre": extra_abre, "fecha": extra_fecha})
    if form.get("remover_extra"):
        alvo = form.get("remover_extra")
        nova["extra"] = [e for e in nova["extra"] if e.get("semana") != alvo]

    try:
        dados.salvar_janela(user, nova)
    except (dados.InvalidoError, dados.RecusadoError) as erro:
        return erro_de_dominio(erro, req)

    auditoria.registrar(
        "janela",
        user.email,
        empresa,
        {"dias": nova["dias"], "semanas": len(nova["semanas_liberadas"])},
    )
    return _resposta(
        req,
        user,
        "janelas",
        _contexto_janelas(),
        toast=f"Janela de {empresa} atualizada.",
    )
