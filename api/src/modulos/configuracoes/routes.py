"""Rotas das telas de Configurações: Parâmetros (ISSUE-076), Colaboradores (ISSUE-077) e Cadastros (ISSUE-078).

**Parâmetros** (``/api/configuracoes/parametros``): a tela é um fragmento
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

**Colaboradores** (``/api/configuracoes/colaboradores``, só Admin): a tela é um
fragmento (``colaboradores-conteudo``) com os avisos, os KPIs por perfil, a
barra de filtros (busca, perfil e vínculo por query — o servidor filtra) e a
lista de quem tem acesso, com Editar e Revogar. O modal abre em
``colaboradores-modal-corpo``: um GET desenha o corpo do novo acesso ou da
edição, um POST grava e devolve a tela atualizada (o modal fecha no sucesso), e
uma recusa (422, 403) devolve o formulário preenchido com a mensagem no campo.
A revogação confirma no cliente e volta como a tela com o toast.

* ``GET  colaboradores``                                  a tela (busca, perfil e vínculo por query);
* ``GET  colaboradores/excel`` e ``colaboradores/imprimivel`` os dois exports;
* ``GET  colaboradores/novo`` e ``colaboradores/{id}/editar`` o corpo do modal;
* ``POST colaboradores`` e ``colaboradores/{id}``         cria e atualiza o acesso;
* ``POST colaboradores/{id}/revogar``                     apaga o acesso (a pessoa permanece no cadastro).

**Cadastros** (``/api/configuracoes/cadastros``, Gestor e Admin): a tela é um
fragmento (``cadastros-conteudo``) com sete cartões — empresas, pessoas,
projetos, sistemas, unidades, locais e disciplinas —, cada um com a contagem, o
Incluir, a tabela e Editar/Excluir por linha. O corpo do modal
(``cadastros-modal-corpo``) é desenhado por GET conforme o tipo; a gravação
(POST) devolve a tela atualizada (o modal fecha no sucesso) e a recusa volta no
formulário (422). A exclusão confirma no cliente e volta como a tela com o
toast; um cadastro em uso é recusado com a mensagem de onde ele é usado.

* ``GET  cadastros``                                      a tela com os sete cadastros;
* ``GET  cadastros/excel`` e ``cadastros/imprimivel``     os dois exports;
* ``GET  cadastros/{tipo}/novo`` e ``cadastros/{tipo}/{id}/editar`` o corpo do modal;
* ``POST cadastros/{tipo}`` e ``cadastros/{tipo}/{id}``   cria e atualiza o cadastro;
* ``POST cadastros/{tipo}/{id}/excluir``                  apaga o cadastro, ou recusa se está em uso.

Só Gestor e Admin alcançam o módulo (``rbac.MODULE_PERMISSION``) e só o Admin
alcança Colaboradores (``rbac.SCREEN_PERMISSION``, aqui pedido como
``Permission.ADMINISTER``); as regras são de ``service``, e as rotas só leem a
requisição, chamam e desenham.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any, TypedDict
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
from src.core.routing import (
    Access,
    ErrorRenderer,
    RequestContext,
    file_route,
    fragment_route,
)
from src.modulos.configuracoes import export, forms, service
from src.modulos.configuracoes.models import ParameterVersion

bp = func.Blueprint()

MODULE = "configuracoes"
ACCESS = Access(module=MODULE)
COLLABORATORS_ACCESS = Access(module=MODULE, permission=Permission.ADMINISTER)

CONTENT_TARGET = "parametros-conteudo"
MODAL_TARGET = "parametros-modal-corpo"
ROUTE = "/api/configuracoes/parametros"
NOT_FOUND = "Grupo de parâmetros desconhecido."

SCREEN_TEMPLATE = "configuracoes/parametros.html"
FORM_TEMPLATE = "configuracoes/parametros_form.html"
HISTORY_TEMPLATE = "configuracoes/parametros_historico.html"

COLLABORATORS_ROUTE = "/api/configuracoes/colaboradores"
COLLABORATORS_CONTENT_TARGET = "colaboradores-conteudo"
COLLABORATORS_MODAL_TARGET = "colaboradores-modal-corpo"

COLLABORATORS_SCREEN_TEMPLATE = "configuracoes/colaboradores.html"
COLLABORATORS_FORM_TEMPLATE = "configuracoes/colaboradores_form.html"

REGISTERS_ROUTE = "/api/configuracoes/cadastros"
REGISTERS_CONTENT_TARGET = "cadastros-conteudo"
REGISTERS_MODAL_TARGET = "cadastros-modal-corpo"

REGISTERS_SCREEN_TEMPLATE = "configuracoes/cadastros.html"
REGISTERS_FORM_TEMPLATE = "configuracoes/cadastros_form.html"


def _status(error: DomainError) -> int:
    if isinstance(error, AccessDeniedError):
        return 403
    return 409 if isinstance(error, VersionConflictError) else 422


def _modal_error_em(target_id: str) -> ErrorRenderer:
    """A recusa dentro de um modal: a mensagem no corpo daquele modal, onde a pessoa está olhando.

    Cada tela tem o seu alvo de modal (``parametros-modal-corpo``,
    ``colaboradores-modal-corpo``), e a resposta precisa voltar para o modal que
    fez a pergunta.
    """

    def render(req: func.HttpRequest, error: DomainError) -> func.HttpResponse:
        messages = error.messages() if isinstance(error, InvalidDataError) else [str(error)]
        return AlpineAjaxResponse(
            template_name="comum/erro.html",
            context={"mensagens": messages},
            request=req,
            target_id=target_id,
            status_code=_status(error),
            toast=messages[0] if messages else "Não foi possível concluir.",
            toast_tipo="erro",
        )

    return render


_modal_error = _modal_error_em(MODAL_TARGET)
_collaborator_modal_error = _modal_error_em(COLLABORATORS_MODAL_TARGET)
_registers_modal_error = _modal_error_em(REGISTERS_MODAL_TARGET)


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


# ── Tela de Colaboradores (ISSUE-077) ────────────────────────────────────
#
# Só o Admin chega aqui (``Permission.ADMINISTER``): é a tela que concede e
# revoga o acesso. A lista e o formulário são fragmentos; o filtro é um GET com
# o estado na query e o modal de novo/editar carrega o corpo por GET, como o
# módulo já faz na tela de Parâmetros. A revogação volta como a tela com o
# toast: a recusa do último Admin não pode esvaziar a lista, então a tela é
# re-renderizada com o motivo no toast (o formulário de revogação não existe
# no DOM).


class _CollaboratorFilters(TypedDict):
    """Os filtros da tela que o formulário carregou de volta (``busca=...&vinculo=Timenow``)."""

    search: str
    profile: str
    bond: str


def _route_int(req: func.HttpRequest, name: str) -> int:
    raw = (req.route_params.get(name) or "").strip()
    return int(raw) if raw.isdecimal() else 0


def _collaborator_query_state(consulta: str) -> _CollaboratorFilters:
    state = dict(parse_qsl(consulta))
    return _CollaboratorFilters(
        search=(state.get("busca") or "").strip(),
        profile=(state.get("perfil") or "").strip(),
        bond=(state.get("vinculo") or "").strip(),
    )


def _collaborator_screen_response(
    req: func.HttpRequest,
    session: Session,
    *,
    search: str = "",
    profile: str = "",
    bond: str = "",
    notice: str | None = None,
    status_code: int = 200,
    toast_tipo: str = "ok",
) -> func.HttpResponse:
    """A tela de Colaboradores: os KPIs, os filtros e a lista, já filtrada pelo servidor."""
    overview = service.list_collaborators_overview(
        session, search=search, profile=profile, bond=bond
    )
    state = {
        key: value
        for key, value in {"busca": search, "perfil": profile, "vinculo": bond}.items()
        if value
    }
    return AlpineAjaxResponse(
        template_name=COLLABORATORS_SCREEN_TEMPLATE,
        context={
            "visao": overview,
            "busca": search,
            "perfil": profile,
            "vinculo": bond,
            "perfis": service.PROFILE_OPTIONS,
            "vinculos": service.BOND_OPTIONS,
            "consulta": urlencode(state),
            "url_tela": COLLABORATORS_ROUTE,
            "url_excel": f"{COLLABORATORS_ROUTE}/excel",
            "url_pdf": f"{COLLABORATORS_ROUTE}/imprimivel",
            "url_novo": f"{COLLABORATORS_ROUTE}/novo",
            "situacao": (
                "vazio-filtro" if (search or profile or bond) and not overview.rows else "conteudo"
            ),
            **_helpers(),
        },
        request=req,
        target_id=COLLABORATORS_CONTENT_TARGET,
        status_code=status_code,
        toast=notice,
        toast_tipo=toast_tipo,
    )


def _collaborator_form_values(form: Mapping[str, Any]) -> dict[str, Any]:
    """O que a pessoa digitou no formulário, como a fachada e o template o leem."""
    return {
        "nome": (form.get("nome") or "").strip(),
        "email": (form.get("email") or "").strip(),
        "funcao": (form.get("funcao") or "").strip(),
        "perfil": (form.get("perfil") or "").strip(),
        "vinculo": (form.get("vinculo") or "").strip(),
        "empresa": (form.get("empresa") or "").strip(),
        "ativo": (form.get("ativo") or "") == "sim",
    }


def _values_of(registro: service.CollaboratorRow) -> dict[str, Any]:
    return {
        "nome": registro.name,
        "email": registro.email,
        "funcao": registro.role or "",
        "perfil": registro.general_profile,
        "vinculo": registro.bond,
        "empresa": str(registro.company_id) if registro.company_id is not None else "",
        "ativo": registro.active,
    }


def _company_id(raw: Any) -> int | None:
    text = str(raw or "").strip()
    return int(text) if text.isdecimal() else None


def _posted_roles(form: Any) -> list[tuple[int, str]]:
    """Os pares ``(projeto_id, papel)`` dos campos repetidos ``papeis`` (``"<id>:<papel>"``)."""
    roles: list[tuple[int, str]] = []
    for raw in form.getlist("papeis"):
        project, _, papel = str(raw).partition(":")
        roles.append((int(project) if project.strip().isdecimal() else 0, papel.strip()))
    return roles


def _roles_data(roles: Sequence[tuple[int, str]]) -> list[dict[str, Any]]:
    """Os pares que o editor do modal lê de ``data-papeis`` (JSON no atributo)."""
    return [{"projeto_id": project_id, "papel": papel} for project_id, papel in roles]


def _projects_data(session: Session) -> list[dict[str, Any]]:
    return [
        {"id": project.id, "label": f"{project.code} · {project.name}"}
        for project in service.list_projects(session)
    ]


def _collaborator_form_response(
    req: func.HttpRequest,
    session: Session,
    *,
    registro: service.CollaboratorRow | None,
    values: Mapping[str, Any],
    roles: Sequence[tuple[int, str]],
    errors: Mapping[str, str],
    status_code: int,
    consulta: str,
) -> func.HttpResponse:
    """O corpo do modal: os campos (do registro, do digitado ou vazios) e os papéis por projeto."""
    editando = registro is not None
    messages = [message for message in errors.values() if message]
    return AlpineAjaxResponse(
        template_name=COLLABORATORS_FORM_TEMPLATE,
        context={
            "registro": registro,
            "editando": editando,
            "valores": values,
            "papeis_dados": _roles_data(roles),
            "projetos_dados": _projects_data(session),
            "papeis_rotulos": list(service.SCHEDULE_ROLE_OPTIONS),
            "perfis": service.PROFILE_OPTIONS,
            "vinculos": service.BOND_OPTIONS,
            "empresas": service.list_company_options(session),
            "erros": dict(errors),
            "erros_gerais": [message for key, message in errors.items() if key == "geral"],
            "consulta": consulta,
            "url_acao": (
                f"{COLLABORATORS_ROUTE}/{registro.collaborator_id}"
                if editando
                else COLLABORATORS_ROUTE
            ),
        },
        request=req,
        target_id=COLLABORATORS_MODAL_TARGET,
        status_code=status_code,
        toast=messages[0] if messages else None,
        toast_tipo="erro",
    )


def _collaborator_write(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    collaborator_id: int | None,
) -> func.HttpResponse:
    """Grava o acesso pela fachada: o sucesso devolve a tela, a recusa devolve o formulário."""
    form = req.form
    consulta = form.get("consulta", "")
    values = _collaborator_form_values(form)
    roles = _posted_roles(form)
    try:
        with session.begin_nested():
            service.save_collaborator(
                session,
                author_id=context.user.id,
                collaborator_id=collaborator_id,
                name=values["nome"],
                email=values["email"],
                role=values["funcao"],
                profile=values["perfil"],
                bond=values["vinculo"],
                company_id=_company_id(values["empresa"]),
                active=values["ativo"],
                roles=roles,
            )
    except InvalidDataError as error:
        registro = service.find_collaborator(session, collaborator_id) if collaborator_id else None
        return _collaborator_form_response(
            req,
            session,
            registro=registro,
            values=values,
            roles=roles,
            errors=_field_errors(error),
            status_code=422,
            consulta=consulta,
        )
    return _collaborator_screen_response(
        req,
        session,
        **_collaborator_query_state(consulta),
        notice=f"Acesso de {values['nome']} {'liberado' if collaborator_id is None else 'atualizado'}.",
    )


def _collaborator_document(session: Session, context: RequestContext) -> Document:
    """O documento dos exports: a lista inteira, sem o filtro da tela."""
    return export.colaboradores_document(
        rows=service.list_collaborators_overview(session).rows,
        scope=context.scope,
        projects=service.list_projects(session),
        today=calendario.today(),
    )


@bp.route(route="configuracoes/colaboradores", methods=["GET"])
@fragment_route(access=COLLABORATORS_ACCESS)
def collaborators_screen(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A tela: os avisos, os KPIs por perfil, os filtros e a lista de quem tem acesso."""
    del context
    return _collaborator_screen_response(
        req,
        session,
        search=(req.params.get("busca") or "").strip(),
        profile=(req.params.get("perfil") or "").strip(),
        bond=(req.params.get("vinculo") or "").strip(),
    )


@bp.route(route="configuracoes/colaboradores/excel", methods=["GET"])
@file_route(access=COLLABORATORS_ACCESS)
def collaborators_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Excel da tela: a lista de quem tem acesso."""
    del req
    return excel_response(_collaborator_document(session, context))


@bp.route(route="configuracoes/colaboradores/imprimivel", methods=["GET"])
@fragment_route(access=COLLABORATORS_ACCESS)
def collaborators_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A versão imprimível do mesmo documento: o que o botão PDF monta e imprime."""
    return printable_response(_collaborator_document(session, context), req)


@bp.route(route="configuracoes/colaboradores/novo", methods=["GET"])
@fragment_route(access=COLLABORATORS_ACCESS, on_error=_collaborator_modal_error)
def collaborators_new_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O corpo do modal de novo acesso: os campos vazios e a seção de papéis."""
    del context
    return _collaborator_form_response(
        req,
        session,
        registro=None,
        values={},
        roles=[],
        errors={},
        status_code=200,
        consulta=req.params.get("consulta", ""),
    )


@bp.route(route="configuracoes/colaboradores/{id}/editar", methods=["GET"])
@fragment_route(access=COLLABORATORS_ACCESS, on_error=_collaborator_modal_error)
def collaborators_edit_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O corpo do modal de edição: os campos do colaborador e os papéis atuais."""
    del context
    registro = service.find_collaborator(session, _route_int(req, "id"))
    if registro is None:
        raise InvalidDataError({"geral": service.COLLABORATOR_NOT_FOUND})
    return _collaborator_form_response(
        req,
        session,
        registro=registro,
        values=_values_of(registro),
        roles=[(line.project_id, line.role) for line in registro.schedule_roles],
        errors={},
        status_code=200,
        consulta=req.params.get("consulta", ""),
    )


@bp.route(route="configuracoes/colaboradores", methods=["POST"])
@fragment_route(access=COLLABORATORS_ACCESS, on_error=_collaborator_modal_error)
def collaborators_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Cria um acesso: o sucesso devolve a tela (o modal fecha) e a recusa volta no formulário."""
    return _collaborator_write(req, session, context, collaborator_id=None)


@bp.route(route="configuracoes/colaboradores/{id}", methods=["POST"])
@fragment_route(access=COLLABORATORS_ACCESS, on_error=_collaborator_modal_error)
def collaborators_update(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Atualiza um acesso: o sucesso devolve a tela (o modal fecha) e a recusa volta no formulário."""
    return _collaborator_write(req, session, context, collaborator_id=_route_int(req, "id"))


@bp.route(route="configuracoes/colaboradores/{id}/revogar", methods=["POST"])
@fragment_route(access=COLLABORATORS_ACCESS)
def collaborators_revoke(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Revoga o acesso: a recusa do último Admin volta na própria tela, com o motivo no toast."""
    consulta = req.form.get("consulta", "")
    registro = service.find_collaborator(session, _route_int(req, "id"))
    if registro is None:
        return _collaborator_screen_response(
            req,
            session,
            **_collaborator_query_state(consulta),
            notice=service.COLLABORATOR_NOT_FOUND,
            status_code=422,
            toast_tipo="erro",
        )
    try:
        with session.begin_nested():
            service.revoke_collaborator(
                session, author_id=context.user.id, collaborator_id=registro.collaborator_id
            )
    except InvalidDataError as error:
        messages = error.messages()
        return _collaborator_screen_response(
            req,
            session,
            **_collaborator_query_state(consulta),
            notice=messages[0] if messages else "Não foi possível revogar o acesso.",
            status_code=422,
            toast_tipo="erro",
        )
    return _collaborator_screen_response(
        req,
        session,
        **_collaborator_query_state(consulta),
        notice=f"Acesso de {registro.email} revogado.",
    )


# ── Tela de Cadastros (ISSUE-078) ────────────────────────────────────────
#
# A tela mantém os sete cadastros de apoio (D5): empresas, pessoas, projetos,
# sistemas, unidades, locais e disciplinas. O corpo do modal é desenhado pelo
# servidor por GET conforme o tipo; a gravação (POST) devolve a tela inteira e
# o modal fecha no sucesso, e a recusa (422) volta no modal com a mensagem de
# cada campo. A exclusão confirma no cliente e volta como a tela com o toast:
# um cadastro em uso não pode esvaziar a lista, então a tela é re-renderizada
# com o motivo no toast de erro.


def _register_kind(req: func.HttpRequest) -> str:
    kind = (req.route_params.get("tipo") or "").strip()
    if kind not in service.REGISTER_KINDS:
        raise InvalidDataError({"geral": service.REGISTER_NOT_FOUND})
    return kind


def _register_defaults(kind: str, project_id: int | None) -> dict[str, str]:
    """O projeto do escopo já vem escolhido no formulário de sistemas e locais."""
    if kind in ("sistema", "local") and project_id is not None:
        return {"projeto": str(project_id)}
    return {}


def _registers_screen_response(
    req: func.HttpRequest,
    session: Session,
    *,
    notice: str | None = None,
    status_code: int = 200,
    toast_tipo: str = "ok",
) -> func.HttpResponse:
    """A tela de Cadastros: os sete cartões com a contagem e as tabelas."""
    overview = service.registers_overview(session, reference_date=calendario.today())
    return AlpineAjaxResponse(
        template_name=REGISTERS_SCREEN_TEMPLATE,
        context={
            "visao": overview,
            "url_tela": REGISTERS_ROUTE,
            "url_excel": f"{REGISTERS_ROUTE}/excel",
            "url_pdf": f"{REGISTERS_ROUTE}/imprimivel",
            **_helpers(),
        },
        request=req,
        target_id=REGISTERS_CONTENT_TARGET,
        status_code=status_code,
        toast=notice,
        toast_tipo=toast_tipo,
    )


def _registers_form_response(
    req: func.HttpRequest,
    session: Session,
    *,
    kind: str,
    register_id: int | None,
    values: Mapping[str, Any],
    errors: Mapping[str, str],
    status_code: int,
) -> func.HttpResponse:
    """O corpo do modal: os campos do tipo, as listas dos selects e os erros por campo."""
    messages = [message for message in errors.values() if message]
    return AlpineAjaxResponse(
        template_name=REGISTERS_FORM_TEMPLATE,
        context={
            "tipo": kind,
            "rotulo": service.REGISTER_LABELS[kind],
            "editando": register_id is not None,
            "valores": dict(values),
            "opcoes": service.register_form_options(session, reference_date=calendario.today()),
            "erros": {key: message for key, message in errors.items() if key != "geral"},
            "erros_gerais": [message for key, message in errors.items() if key == "geral"],
            "url_salvar": (
                f"{REGISTERS_ROUTE}/{kind}/{register_id}"
                if register_id is not None
                else f"{REGISTERS_ROUTE}/{kind}"
            ),
        },
        request=req,
        target_id=REGISTERS_MODAL_TARGET,
        status_code=status_code,
        toast=messages[0] if messages else None,
        toast_tipo="erro",
    )


def _registers_write(
    req: func.HttpRequest,
    session: Session,
    context: RequestContext,
    *,
    kind: str,
    register_id: int | None,
) -> func.HttpResponse:
    """Grava o cadastro: o sucesso devolve a tela (o modal fecha) e a recusa volta no formulário."""
    try:
        with session.begin_nested():
            label = service.save_register(
                session,
                kind=kind,
                author_id=context.user.id,
                register_id=register_id,
                form=req.form,
                reference_date=calendario.today(),
            )
    except InvalidDataError as error:
        return _registers_form_response(
            req,
            session,
            kind=kind,
            register_id=register_id,
            values=req.form,
            errors=_field_errors(error),
            status_code=422,
        )
    return _registers_screen_response(
        req,
        session,
        notice=f"Cadastro de {service.REGISTER_LABELS[kind].lower()} gravado: “{label}”.",
    )


def _registers_document(session: Session, context: RequestContext) -> Document:
    """O documento dos exports: os sete cadastros, sem filtro."""
    today = calendario.today()
    return export.registers_document(
        overview=service.registers_overview(session, reference_date=today),
        scope=context.scope,
        projects=service.list_projects(session),
        today=today,
    )


@bp.route(route="configuracoes/cadastros", methods=["GET"])
@fragment_route(access=ACCESS)
def registers_screen(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A tela: os sete cadastros com a contagem, as tabelas e o Incluir/Editar/Excluir."""
    del context
    return _registers_screen_response(req, session)


@bp.route(route="configuracoes/cadastros/excel", methods=["GET"])
@file_route(access=ACCESS)
def registers_excel(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O Excel da tela: as sete tabelas de cadastro."""
    del req
    return excel_response(_registers_document(session, context))


@bp.route(route="configuracoes/cadastros/imprimivel", methods=["GET"])
@fragment_route(access=ACCESS)
def registers_printable(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """A versão imprimível do mesmo documento: o que o botão PDF monta e imprime."""
    return printable_response(_registers_document(session, context), req)


@bp.route(route="configuracoes/cadastros/{tipo}/novo", methods=["GET"])
@fragment_route(access=ACCESS, on_error=_registers_modal_error)
def registers_new_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O corpo do modal de novo cadastro, conforme o tipo."""
    kind = _register_kind(req)
    return _registers_form_response(
        req,
        session,
        kind=kind,
        register_id=None,
        values=_register_defaults(kind, context.scope.project_id),
        errors={},
        status_code=200,
    )


@bp.route(route="configuracoes/cadastros/{tipo}/{id}/editar", methods=["GET"])
@fragment_route(access=ACCESS, on_error=_registers_modal_error)
def registers_edit_form(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """O corpo do modal de edição, com o registro carregado."""
    del context
    kind = _register_kind(req)
    register_id = _route_int(req, "id")
    values = service.register_form_values(
        session, kind, register_id, reference_date=calendario.today()
    )
    if values is None:
        raise InvalidDataError({"geral": service.REGISTER_RECORD_NOT_FOUND})
    return _registers_form_response(
        req,
        session,
        kind=kind,
        register_id=register_id,
        values=values,
        errors={},
        status_code=200,
    )


@bp.route(route="configuracoes/cadastros/{tipo}", methods=["POST"])
@fragment_route(access=ACCESS, on_error=_registers_modal_error)
def registers_save(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Cria um cadastro: o sucesso devolve a tela (o modal fecha) e a recusa volta no formulário."""
    return _registers_write(req, session, context, kind=_register_kind(req), register_id=None)


@bp.route(route="configuracoes/cadastros/{tipo}/{id}", methods=["POST"])
@fragment_route(access=ACCESS, on_error=_registers_modal_error)
def registers_update(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Atualiza um cadastro: o sucesso devolve a tela e a recusa volta no formulário."""
    return _registers_write(
        req, session, context, kind=_register_kind(req), register_id=_route_int(req, "id")
    )


@bp.route(route="configuracoes/cadastros/{tipo}/{id}/excluir", methods=["POST"])
@fragment_route(access=ACCESS)
def registers_delete(
    req: func.HttpRequest, session: Session, context: RequestContext
) -> func.HttpResponse:
    """Exclui um cadastro: em uso, a recusa volta na própria tela, com o motivo no toast."""
    kind = _register_kind(req)
    register_id = _route_int(req, "id")
    try:
        with session.begin_nested():
            label = service.delete_register(
                session, kind=kind, author_id=context.user.id, register_id=register_id
            )
    except InvalidDataError as error:
        messages = error.messages()
        return _registers_screen_response(
            req,
            session,
            notice=messages[0] if messages else "Não foi possível excluir o cadastro.",
            status_code=422,
            toast_tipo="erro",
        )
    return _registers_screen_response(
        req,
        session,
        notice=f"Cadastro de {service.REGISTER_LABELS[kind].lower()} excluído: “{label}”.",
    )
