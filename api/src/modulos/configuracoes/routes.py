"""Rotas da tela Parâmetros do sistema (ISSUE-076, D6, D14).

Prefixo ``/api/configuracoes/parametros``. A tela é um fragmento
(``parametros-conteudo``): o card da versão vigente, a barra com a busca e o
filtro por módulo e os grupos por módulo com a tabela de parâmetro x valor
vigente e o botão Editar. O filtro é um GET do próprio fragmento com o estado na
query (o servidor filtra). O modal de edição e o histórico abrem em
``parametros-modal-corpo``: um GET desenha o corpo, um POST grava e devolve a
tela atualizada (o modal fecha no sucesso); uma recusa (422, 403) devolve o
formulário preenchido, com a mensagem no campo. A troca da escala de riscos pede
confirmação no próprio formulário (o campo ``confirmar_escala``).

* ``GET  parametros``                                  a tela (busca e módulo por query);
* ``GET  parametros/excel`` e ``parametros/imprimivel`` os dois exports;
* ``GET  parametros/{grupo}/editar``                   o corpo do modal de edição;
* ``POST parametros/{grupo}``                          grava a nova versão (uma por grupo de origem que mudou);
* ``GET  parametros/historico``                        o corpo do modal do histórico (o detalhe por ``grupo`` e ``versao``).

Só Gestor e Admin alcançam o módulo (``rbac.MODULE_PERMISSION``); as regras são
de ``service`` e ``forms``, e as rotas só leem a requisição, chamam e desenham.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any
from urllib.parse import parse_qsl, urlencode

import azure.functions as func
from sqlalchemy.orm import Session

from src.core import calendario, rbac
from src.core.errors import (
    AccessDeniedError,
    DomainError,
    InvalidDataError,
    VersionConflictError,
)
from src.core.excel import excel_response
from src.core.export_document import Document, ValueKind, format_value
from src.core.printable import printable_response
from src.core.rbac import Permission
from src.core.responses import AlpineAjaxResponse
from src.core.routing import Access, RequestContext, file_route, fragment_route
from src.modulos.configuracoes import export, forms, service
from src.modulos.configuracoes.models import ParameterVersion

bp = func.Blueprint()

MODULE = "configuracoes"
ACCESS = Access(module=MODULE)

CONTENT_TARGET = "parametros-conteudo"
MODAL_TARGET = "parametros-modal-corpo"
ROUTE = "/api/configuracoes/parametros"
NOT_FOUND = "Grupo de parâmetros desconhecido."

SCREEN_TEMPLATE = "configuracoes/parametros.html"
FORM_TEMPLATE = "configuracoes/parametros_form.html"
HISTORY_TEMPLATE = "configuracoes/parametros_historico.html"


def _status(error: DomainError) -> int:
    if isinstance(error, AccessDeniedError):
        return 403
    return 409 if isinstance(error, VersionConflictError) else 422


def _modal_error(req: func.HttpRequest, error: DomainError) -> func.HttpResponse:
    """A recusa dentro do modal: a mensagem no corpo do modal, onde a pessoa está olhando."""
    messages = error.messages() if isinstance(error, InvalidDataError) else [str(error)]
    return AlpineAjaxResponse(
        template_name="comum/erro.html",
        context={"mensagens": messages},
        request=req,
        target_id=MODAL_TARGET,
        status_code=_status(error),
        toast=messages[0] if messages else "Não foi possível concluir.",
        toast_tipo="erro",
    )


def _field_errors(error: DomainError) -> Mapping[str, str]:
    if isinstance(error, InvalidDataError) and isinstance(error.detail, Mapping):
        return dict(error.detail)
    return {"geral": str(error)}


def _helpers() -> dict[str, Any]:
    """O que os templates formatam: a data no padrão de Brazil."""
    return {"data": lambda value: format_value(ValueKind.DATE, value)}


def _form_errors(
    group: forms.ParameterGroupForm, errors: Mapping[str, str]
) -> tuple[dict[str, str], list[str]]:
    """Os erros por campo do formulário e os que não têm campo (no topo do formulário)."""
    by_path = {field.caminho: field for field in group.campos}
    por_campo: dict[str, str] = {}
    gerais: list[str] = []
    for chave, mensagem in errors.items():
        if chave == "justificativa":
            por_campo["justificativa"] = mensagem
        elif chave in by_path:
            por_campo[by_path[chave].field_id] = mensagem
        else:
            gerais.append(mensagem)
    return por_campo, gerais


def _group_or_refuse(
    values: Mapping[str, Mapping[str, Any]], group_id: str
) -> forms.ParameterGroupForm:
    group = forms.find_group(forms.group_forms(values), group_id)
    if group is None:
        raise InvalidDataError({"geral": NOT_FOUND})
    return group


def _query_state(consulta: str) -> dict[str, str]:
    """Os filtros que o formulário carregou de volta (``busca=...&modulo=05``)."""
    state = dict(parse_qsl(consulta))
    return {
        "search": (state.get("busca") or "").strip(),
        "module": (state.get("modulo") or "").strip(),
    }


def _screen_response(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    search: str = "",
    module: str = "",
    notice: str | None = None,
) -> func.HttpResponse:
    today = calendario.today()
    overview = service.parameter_overview(
        session, reference_date=today, search=search, module=module
    )
    state = {key: value for key, value in {"busca": search, "modulo": module}.items() if value}
    return AlpineAjaxResponse(
        template_name=SCREEN_TEMPLATE,
        context={
            "visao": overview,
            "busca": search,
            "modulo": module,
            "modulos": forms.MODULE_OPTIONS,
            "consulta": urlencode(state),
            "hoje": today,
            "url_tela": ROUTE,
            "url_historico": f"{ROUTE}/historico",
            "url_excel": f"{ROUTE}/excel",
            "url_pdf": f"{ROUTE}/imprimivel",
            "pode_gravar": rbac.can(context.user, Permission.CONFIGURE),
            "situacao": "vazio-filtro" if not overview.groups else "conteudo",
            **_helpers(),
        },
        request=req,
        target_id=CONTENT_TARGET,
        toast=notice,
    )


def _form_response(
    req: func.HttpRequest,
    *,
    group: forms.ParameterGroupForm,
    values: Mapping[str, Mapping[str, Any]],
    form: Mapping[str, str],
    errors: Mapping[str, str],
    status_code: int,
    consulta: str,
) -> func.HttpResponse:
    """O corpo do modal de edição: os campos vigentes (ou digitados) e a mensagem de cada erro."""
    por_campo, gerais = _form_errors(group, errors)
    return AlpineAjaxResponse(
        template_name=FORM_TEMPLATE,
        context={
            "grupo": group,
            "campos": forms.field_views(group, values, form),
            "justificativa": form.get("justificativa", ""),
            "erros": por_campo,
            "erros_gerais": gerais,
            "consulta": consulta,
            "confirmar_escala": (form.get("confirmar_escala") or "") == "sim",
            **_helpers(),
        },
        request=req,
        target_id=MODAL_TARGET,
        status_code=status_code,
    )


def _save_groups(
    session: Session,
    *,
    context: RequestContext,
    group: forms.ParameterGroupForm,
    parsed: forms.ParsedGroupForm,
    form: Mapping[str, str],
    today: date,
) -> tuple[list[ParameterVersion], DomainError | None]:
    """Grava uma versão por grupo de origem que mudou, tudo num savepoint da transação da requisição."""
    touched = {field.grupo_parametro for field in parsed.changed}
    created: list[ParameterVersion] = []
    try:
        with session.begin_nested():
            for service_group in forms.group_sources(group.id):
                if service_group not in touched:
                    continue
                created.append(
                    service.save_parameter_group(
                        session,
                        author_id=context.user.id,
                        group=service_group,
                        values=parsed.values[service_group],
                        effective_from=today,
                        justification=form.get("justificativa", ""),
                    )
                )
    except InvalidDataError as error:
        return [], error
    return created, None


def _notice(versions: Sequence[ParameterVersion], count: int) -> str:
    """O aviso da gravação: a versão (ou as versões) criadas e quantos parâmetros mudaram."""
    if len(versions) == 1:
        target = f"Versão {versions[0].version} gravada"
    else:
        target = "Versões " + ", ".join(f"v{version.version}" for version in versions) + " gravadas"
    what = "parâmetro alterado" if count == 1 else "parâmetros alterados"
    return f"{target}: {count} {what}."


def _document(session: Session, context: RequestContext) -> Document:
    """O documento dos exports: todos os grupos e todas as versões, sem o filtro da tela."""
    today = calendario.today()
    return export.parametros_document(
        overview=service.parameter_overview(session, reference_date=today),
        history=service.parameter_history(session, reference_date=today),
        scope=context.scope,
        projects=service.list_projects(session),
        today=today,
    )


@bp.route(route="configuracoes/parametros", methods=["GET"])
@fragment_route(access=ACCESS)
def parameters_screen(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A tela: o card da versão, os filtros e os grupos com os valores vigentes."""
    return _screen_response(
        req,
        session,
        context,
        search=(req.params.get("busca") or "").strip(),
        module=(req.params.get("modulo") or "").strip(),
    )


@bp.route(route="configuracoes/parametros/excel", methods=["GET"])
@file_route(access=ACCESS)
def parameters_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Excel da tela: as tabelas de parâmetros vigentes e do histórico de versões."""
    del req
    return excel_response(_document(session, context))


@bp.route(route="configuracoes/parametros/imprimivel", methods=["GET"])
@fragment_route(access=ACCESS)
def parameters_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A versão imprimível do mesmo documento: o que o botão PDF monta e imprime."""
    return printable_response(_document(session, context), req)


@bp.route(route="configuracoes/parametros/{grupo}/editar", methods=["GET"])
@fragment_route(access=ACCESS, on_error=_modal_error)
def parameters_edit_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O corpo do modal de edição: os campos do grupo com os valores vigentes."""
    del context
    today = calendario.today()
    values = service.current_parameters(session, reference_date=today)
    group = _group_or_refuse(values, (req.route_params.get("grupo") or "").strip())
    return _form_response(
        req,
        group=group,
        values=values,
        form={},
        errors={},
        status_code=200,
        consulta=req.params.get("consulta", ""),
    )


@bp.route(route="configuracoes/parametros/{grupo}", methods=["POST"])
@fragment_route(access=ACCESS, on_error=_modal_error)
def parameters_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Grava a nova versão do grupo: uma por grupo de origem que mudou, na mesma transação."""
    form = req.form
    consulta = form.get("consulta", "")
    today = calendario.today()
    values = service.current_parameters(session, reference_date=today)
    group = _group_or_refuse(values, (req.route_params.get("grupo") or "").strip())
    parsed = forms.parse_group_form(group, values, form)
    errors = dict(parsed.errors)
    if not errors and not parsed.changed:
        errors["geral"] = forms.NO_CHANGE_MESSAGE
    if errors:
        return _form_response(
            req,
            group=group,
            values=values,
            form=form,
            errors=errors,
            status_code=422,
            consulta=consulta,
        )
    versions, error = _save_groups(
        session, context=context, group=group, parsed=parsed, form=form, today=today
    )
    if error is not None:
        return _form_response(
            req,
            group=group,
            values=values,
            form=form,
            errors=_field_errors(error),
            status_code=422,
            consulta=consulta,
        )
    return _screen_response(
        req,
        session,
        context,
        **_query_state(consulta),
        notice=_notice(versions, len(parsed.changed)),
    )


def _detail_of(
    entries: Sequence[service.HistoryEntry], params: Mapping[str, str]
) -> service.HistoryEntry | None:
    """A versão que o ``Ver`` pediu (``grupo`` e ``versao`` na query), ou ``None``.

    A primeira versão de cada grupo não tem alterações e não tem detalhe.
    """
    group = (params.get("grupo") or "").strip()
    raw = (params.get("versao") or "").strip()
    if not group or not raw.isdecimal():
        return None
    return next(
        (
            entry
            for entry in entries
            if entry.group == group and entry.version == int(raw) and entry.changes
        ),
        None,
    )


@bp.route(route="configuracoes/parametros/historico", methods=["GET"])
@fragment_route(access=ACCESS, on_error=_modal_error)
def parameters_history(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O corpo do modal do histórico: as versões, e as alterações da versão pedida."""
    del context
    entries = service.parameter_history(session, reference_date=calendario.today())
    return AlpineAjaxResponse(
        template_name=HISTORY_TEMPLATE,
        context={
            "versoes": entries,
            "detalhe": _detail_of(entries, req.params),
            "url_historico": f"{ROUTE}/historico",
            **_helpers(),
        },
        request=req,
        target_id=MODAL_TARGET,
    )
