"""Loading a week from the spreadsheet, in three checked steps.

    1. baixar o modelo   → colunas na ordem certa e listas válidas juntas
    2. conferir          → validação linha a linha, antes de gravar nada
    3. confirmar         → grava só o que passou, com auditoria

Step 2 exists because the alternative — import and then hunt for what
broke — is how a week ends up with duplicate IDs and totals that do not
close. Nothing is written until the person sees what will be written.
"""

import json

import azure.functions as func

from src.blueprints._comum import com_usuario, erro_de_dominio, semana_pedida
from src.core import auditoria, auth, dados, planilha, rbac
from src.core.responses import AlpineAjaxResponse

bp = func.Blueprint()

LIMITE_ARQUIVO = 8 * 1024 * 1024


@bp.route(route="importar-conferir", methods=["POST"])
@com_usuario(rbac.IMPORTAR)
def conferir(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    """Read the upload and report, line by line, what will happen."""
    arquivo = req.files.get("arquivo") if req.files else None
    if arquivo is None:
        return erro_de_dominio(
            dados.InvalidoError("Escolha o arquivo .xlsx antes de conferir."), req
        )

    conteudo = arquivo.read()
    if len(conteudo) > LIMITE_ARQUIVO:
        return erro_de_dominio(
            dados.InvalidoError("O arquivo passa de 8 MB. Divida a importação por semana."),
            req,
        )

    resultado = planilha.ler_planilha(conteudo, dados.cadastros())
    validas = [linha for linha in resultado["linhas"] if linha["valida"]]

    return AlpineAjaxResponse(
        template_name="importacao/conferencia.html",
        context={
            "user": user,
            "arquivo": getattr(arquivo, "filename", "planilha.xlsx"),
            "resultado": resultado,
            "validas": validas,
            "com_erro": [linha for linha in resultado["linhas"] if not linha["valida"]],
            "carga": json.dumps(validas, ensure_ascii=False),
        },
        request=req,
    )


@bp.route(route="importar-confirmar", methods=["POST"])
@com_usuario(rbac.IMPORTAR)
def confirmar(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    """Write the lines that passed, and report what still did not."""
    try:
        linhas = json.loads(req.form.get("carga") or "[]")
    except json.JSONDecodeError:
        linhas = []

    if not linhas:
        return erro_de_dominio(
            dados.InvalidoError("Nada a importar — nenhuma linha passou na conferência."), req
        )

    try:
        resultado = dados.importar_atividades(user, linhas)
    except dados.RecusadoError as erro:
        return erro_de_dominio(erro, req)

    for atividade in resultado["inseridas"]:
        auditoria.registrar(
            "importar",
            user.email,
            atividade["id_exclusiva"],
            {"key": atividade["key"], "semana": atividade["semana"]},
        )

    total = len(resultado["inseridas"])
    return AlpineAjaxResponse(
        template_name="importacao/resultado.html",
        context={"user": user, **resultado, "total": total},
        request=req,
        toast=(
            f"{total} atividade(s) importada(s)." if total else "Nenhuma atividade foi importada."
        ),
        toast_tipo="ok" if total else "aviso",
    )


@bp.route(route="importar-inicio", methods=["GET"])
@com_usuario(rbac.IMPORTAR)
def inicio(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    """The upload step, with the week it will land on already chosen."""
    semana = semana_pedida(req)
    return AlpineAjaxResponse(
        template_name="importacao/inicio.html",
        context={
            "user": user,
            "semana": semana,
            "semanas": dados.horizonte_de_semanas(),
            "cadastros": dados.cadastros(),
        },
        request=req,
    )
