"""Taking the week out of the app — spreadsheet and printable report.

Two formats, two purposes. The **workbook** is for someone who will keep
working on the numbers: seven sheets, filters, formulas and the curve
series. The **report** is for someone who will read and sign: one page
setup, no navigation, the week closed as a document.

Neither is a raw dump. An export that has to be reformatted before it can
be used is a file, not a report.
"""

from datetime import UTC, datetime

import azure.functions as func

from src.blueprints._comum import (
    com_download,
    com_usuario,
    filtros_pedidos,
    registro_do_ambiente_ativo,
    semana_pedida,
)
from src.core import auditoria, auth, calculos, dados, indicadores, planilha, rbac, semanas
from src.core.responses import AlpineAjaxResponse, redirect_to

bp = func.Blueprint()

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
SEMANAS_DA_CURVA = 12


def _nome_do_arquivo(semana: str) -> str:
    return "programacao-" + semana.replace("/", "-").replace(".", "") + ".xlsx"


@bp.route(route="exportar-semana", methods=["GET"])
@com_download(rbac.EXPORTAR)
def exportar(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    """The weekly workbook.

    Not behind the fragment gate: a download is a real navigation, the
    browser asks for it without the Alpine header. The environment comes
    from the query and is checked the same way; the permission check
    stays.
    """
    semana = semana_pedida(req)
    atividades = dados.listar_atividades(user, semana, filtros_pedidos(req))
    resumo = dados.resumo_semana(user, semana)

    horizonte: list[dict] = []
    for referencia in semanas.janela_de_semanas(semana, atras=SEMANAS_DA_CURVA, adiante=0):
        horizonte.extend(dados.listar_atividades(user, referencia))

    identificacao = registro_do_ambiente_ativo()
    conteudo = planilha.exportar_semana(
        semana,
        atividades,
        resumo,
        indicadores.curva_s(horizonte),
        (user.nome, datetime.now(UTC).strftime("%d/%m/%Y %H:%M")),
        identificacao=(identificacao.get("projeto", ""), identificacao.get("cliente", "")),
    )
    auditoria.registrar(
        "exportar",
        user.email,
        f"planilha da semana {semana}",
        {"semana": semana, "linhas": len(atividades)},
    )

    return func.HttpResponse(
        body=conteudo,
        status_code=200,
        mimetype=XLSX,
        headers={
            "Content-Disposition": f'attachment; filename="{_nome_do_arquivo(semana)}"',
            "Cache-Control": "no-store",
        },
    )


@bp.route(route="relatorio", methods=["GET"])
@com_usuario(rbac.EXPORTAR)
def relatorio(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    """The printable report — Ctrl+P turns it into the PDF."""
    semana = semana_pedida(req)
    atividades = dados.listar_atividades(user, semana, filtros_pedidos(req))
    resumo = dados.resumo_semana(user, semana)
    identificacao = registro_do_ambiente_ativo()
    return AlpineAjaxResponse(
        template_name="relatorio/folha.html",
        context={
            "user": user,
            "semana": semana,
            "periodo": semanas.periodo(semana),
            "datas": semanas.datas_dos_dias(semana),
            "atividades": atividades,
            "r": resumo,
            "por_empresa": calculos.quebrar_por(atividades, "empresa"),
            "por_local": calculos.quebrar_por(atividades, "local"),
            "por_dia": calculos.por_dia(atividades),
            "projeto": identificacao.get("projeto", ""),
            "cliente": identificacao.get("cliente", ""),
        },
        request=req,
    )


@bp.route(route="modelo-planilha", methods=["GET"])
@com_download(rbac.IMPORTAR)
def modelo(req: func.HttpRequest, user: auth.Usuario) -> func.HttpResponse:
    """The blank template, with the valid registers embedded."""
    if req.headers.get("X-Alpine-Request") == "true":
        return redirect_to("/api/modelo-planilha")

    conteudo = planilha.gerar_modelo(semana_pedida(req), dados.cadastros())
    return func.HttpResponse(
        body=conteudo,
        status_code=200,
        mimetype=XLSX,
        headers={
            "Content-Disposition": 'attachment; filename="modelo-programacao-semanal.xlsx"',
            "Cache-Control": "no-store",
        },
    )
