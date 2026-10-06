"""Colaboradores — the access control, in its own room.

This is a sub-tab of Configurações and a separate blueprint on purpose.
Everything here grants or revokes the ability to enter the application:
the register is what ``core/auth.py`` consults, so an e-mail removed
below stops getting in on the next request, session or no session.

Every route asks for ``GERIR_COLABORADORES``, which today only the
Administrator profile carries. A planner may configure windows and
registers and never reach this file.
"""

import re

import azure.functions as func

from src.blueprints._comum import campos_do_formulario, com_usuario, erro_de_dominio
from src.core import auditoria, auth, dados, pii, rbac
from src.core.responses import AlpineAjaxResponse

bp = func.Blueprint()

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")

CAMPOS = ("nome", "email", "perfil", "vinculo", "empresa", "cargo")


def _contexto(user: auth.Usuario, erros: dict | None = None, valores: dict | None = None) -> dict:
    pessoas = dados.listar_colaboradores()
    return {
        # A lista de acesso precisa ser completa para ser verdadeira: os
        # operadores entram implicitamente e aparecem marcados, uma vez
        # só — quem tem cadastro, com o perfil do cadastro; quem não tem,
        # como linha sintética que nunca é gravada no registro do cliente.
        "colaboradores": pii.aplicar(user, auth.colaboradores_com_operadores(pessoas)),
        "por_perfil": {
            perfil: sum(1 for c in pessoas if c.get("perfil") == perfil) for perfil in rbac.PERFIS
        },
        "perfis": [
            {
                "id": perfil,
                "rotulo": rbac.rotulo(perfil),
                "descricao": rbac.PERFIL_DESCRICAO.get(perfil, ""),
            }
            for perfil in rbac.PERFIS
        ],
        "vinculos": [
            {"id": vinculo, "rotulo": rbac.rotulo_vinculo(vinculo)} for vinculo in rbac.VINCULOS
        ],
        "empresas": dados.listar_empresas(),
        "erros": erros or {},
        "valores": valores or {"perfil": "visualizador", "vinculo": "timenow", "ativo": True},
    }


def _abas(user: auth.Usuario):
    from src.blueprints.configuracoes import _abas as abas_de_configuracoes

    return abas_de_configuracoes(user, "colaboradores")


def _resposta(
    req: func.HttpRequest,
    user: auth.Usuario,
    contexto: dict,
    toast: str = "",
    status: int = 200,
) -> func.HttpResponse:
    return AlpineAjaxResponse(
        template_name="colaboradores/painel.html",
        context={"user": user, "abas": _abas(user), "aba": "colaboradores", **contexto},
        request=req,
        status_code=status,
        toast=toast or None,
    )


def _validar(campos: dict, *, exigir_email: bool) -> dict[str, str]:
    erros: dict[str, str] = {}
    if not campos["nome"]:
        erros["nome"] = "Informe o nome completo."
    if exigir_email and not EMAIL.match(campos["email"]):
        erros["email"] = "Informe um e-mail corporativo válido."
    if campos["perfil"] not in rbac.PERFIS:
        erros["perfil"] = "Escolha um perfil."
    if campos["vinculo"] not in rbac.VINCULOS:
        erros["vinculo"] = "Escolha o vínculo."

    if campos["perfil"] == "fornecedor" and campos["vinculo"] != "fornecedor":
        erros["vinculo"] = "O perfil Fornecedor exige o vínculo de empresa contratada."
    if campos["vinculo"] == "fornecedor":
        if not campos["empresa"]:
            erros["empresa"] = "Escolha a empresa da pessoa."
        elif campos["empresa"] not in dados.listar_empresas():
            erros["empresa"] = "Empresa fora do cadastro."
    return erros


@bp.route(route="colaboradores", methods=["GET"])
@com_usuario(rbac.GERIR_COLABORADORES)
def listar(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    return _resposta(req, user, _contexto(user))


@bp.route(route="colaborador", methods=["POST"])
@com_usuario(rbac.GERIR_COLABORADORES)
def salvar(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    """Create or update one person's access."""
    form = req.form
    campos = campos_do_formulario(form, CAMPOS)
    campos["email"] = campos["email"].lower()
    campos["ativo"] = form.get("ativo") != "nao"
    novo = form.get("novo") == "sim"

    if campos["vinculo"] != "fornecedor":
        campos["empresa"] = ""

    erros = _validar(campos, exigir_email=novo)
    if erros:
        return _resposta(
            req,
            user,
            _contexto(user, erros, campos),
            toast="Confira os campos destacados.",
            status=422,
        )

    try:
        dados.salvar_colaborador(user, campos, novo=novo)
    except (dados.InvalidoError, dados.RecusadoError) as erro:
        detalhe = erro.args[0] if erro.args else ""
        mensagem = detalhe if isinstance(detalhe, str) else str(detalhe)
        if isinstance(erro, dados.RecusadoError):
            return erro_de_dominio(erro, req)
        return _resposta(
            req,
            user,
            _contexto(user, {"email": mensagem}, campos),
            toast=mensagem,
            status=422,
        )

    auditoria.registrar(
        "colaborador",
        user.email,
        f"{'cadastrou' if novo else 'atualizou'} {campos['email']} como {campos['perfil']}",
        {"email": campos["email"], "perfil": campos["perfil"]},
    )
    return _resposta(
        req,
        user,
        _contexto(user),
        toast=f"Acesso de {campos['nome']} {'liberado' if novo else 'atualizado'}.",
    )


@bp.route(route="colaborador-remover", methods=["POST"])
@com_usuario(rbac.GERIR_COLABORADORES)
def remover(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    email = (req.form.get("email") or "").strip().lower()
    try:
        dados.remover_colaborador(user, email)
    except (dados.InvalidoError, dados.RecusadoError) as erro:
        return erro_de_dominio(erro, req)

    auditoria.registrar("colaborador", user.email, f"revogou o acesso de {email}", {"email": email})
    return _resposta(req, user, _contexto(user), toast=f"Acesso de {email} revogado.")
