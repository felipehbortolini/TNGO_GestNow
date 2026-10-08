"""Apoio dos testes da Produtividade (ISSUE-046): cenário mínimo, formulários e pedidos HTTP.

O cenário tem projeto, empresa, unidade, pessoas com cada perfil e uma SM aprovada, tudo
dentro da transação do teste. Os formulários são montados como a tela os enviaria (o
``previsto_<semana>`` de cada semana), e ``pedido`` monta a requisição como o Alpine AJAX.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlencode

import azure.functions as func
from sqlalchemy.orm import Session

from src.core.rbac import Bond, GeneralProfile, User
from src.core.scope import Scope
from src.modulos.configuracoes.models import (
    Collaborator,
    Company,
    Discipline,
    Project,
    Unit,
)
from src.modulos.governanca.models import ChangeRequest
from src.modulos.planejamento import calculations, validation
from tests.identidades import (
    cabecalho_do_principal,
    criar_colaborador,
    criar_empresa,
    criar_projeto,
)

HOJE = date(2026, 9, 25)
SEMANA_ATUAL = "2026-S39"
SEMANA_PASSADA = "2026-S38"


@dataclass(frozen=True)
class Cenario:
    """O cenário mínimo da produtividade, na transação do teste."""

    projeto: Project
    empresa: Company
    unidade: Unit
    membro: Collaborator
    gestor: Collaborator
    visualizador: Collaborator
    sm: ChangeRequest

    @property
    def escopo(self) -> Scope:
        return Scope(project_id=self.projeto.id, source="url")

    def _usuario(self, colaborador: Collaborator, perfil: GeneralProfile) -> User:
        return User(
            id=colaborador.id,
            person_id=colaborador.person_id,
            name="Pessoa de teste",
            email="pessoa@example.invalid",
            general_profile=perfil,
            bond=Bond.TIMENOW,
        )

    @property
    def usuario_membro(self) -> User:
        return self._usuario(self.membro, GeneralProfile.MEMBER)

    @property
    def usuario_gestor(self) -> User:
        return self._usuario(self.gestor, GeneralProfile.MANAGER)

    @property
    def usuario_visualizador(self) -> User:
        return self._usuario(self.visualizador, GeneralProfile.VIEWER)


def montar_cenario(session: Session) -> Cenario:
    """Cria o cenário mínimo dentro da transação do teste."""
    session.add_all([Discipline(name="Estruturas"), Discipline(name="Elétrica")])
    unidade = Unit(kind="medida", code="t", name="tonelada")
    session.add(unidade)
    empresa = criar_empresa(session, "Montadora Alfa")
    projeto = criar_projeto(session, codigo="TN-PROD-001", nome="Fábrica")
    membro = criar_colaborador(
        session, email="membro-prod@example.invalid", nome="Maria Membro", perfil="Membro"
    )
    gestor = criar_colaborador(
        session, email="gestor-prod@example.invalid", nome="Gabriel Gestor", perfil="Gestor"
    )
    visualizador = criar_colaborador(
        session, email="visualizador-prod@example.invalid", perfil="Visualizador"
    )
    sm = ChangeRequest(
        project_id=projeto.id,
        requester_id=membro.person_id,
        code="SM-TN-2026-9001",
        title="Reforço do escopo",
        kind="Escopo",
        origin="Cliente",
        priority="Normal",
        request_date=date(2026, 9, 1),
        description="Mudança de teste.",
        situation="Aprovada",
    )
    session.add(sm)
    session.flush()
    return Cenario(
        projeto=projeto,
        empresa=empresa,
        unidade=unidade,
        membro=membro,
        gestor=gestor,
        visualizador=visualizador,
        sm=sm,
    )


def campos_do_item(
    cenario: Cenario,
    *,
    inicio: str = SEMANA_PASSADA,
    fim: str = "2026-S42",
    total: str = "100",
    perfil: str = calculations.PROFILE_LINEAR,
    unidade: str = "t",
    tipo: str = "Estrutura metálica",
) -> dict[str, str]:
    """Os campos do formulário do item, como a tela os envia."""
    return {
        validation.FIELD_ITEM_COMPANY: str(cenario.empresa.id),
        validation.FIELD_ITEM_GROUP: "Aço",
        validation.FIELD_ITEM_KIND: tipo,
        validation.FIELD_ITEM_DISCIPLINE: "Estruturas",
        validation.FIELD_ITEM_UNIT: unidade,
        validation.FIELD_ITEM_TOTAL: total,
        validation.FIELD_ITEM_INDEX: "10",
        validation.FIELD_ITEM_START: inicio,
        validation.FIELD_ITEM_FINISH: fim,
        validation.FIELD_ITEM_PROFILE: perfil,
        validation.FIELD_ITEM_NOTES: "",
    }


def form_item(
    cenario: Cenario,
    *,
    item_id: int | None = None,
    version: int | None = None,
    planned: Mapping[str, str] | None = None,
    **overrides: str,
) -> validation.ItemForm:
    """O formulário do item com a grade calculada pelo servidor, como a tela o envia."""
    fields = campos_do_item(cenario, **overrides)
    if item_id is not None:
        fields["id"] = str(item_id)
    if version is not None:
        fields["versao"] = str(version)
    grade = (
        planned
        if planned is not None
        else {line.week: str(line.planned) for line in service_planned(fields)}
    )
    return validation.ItemForm(fields=fields, planned=dict(grade))


def service_planned(fields: Mapping[str, str]) -> tuple[calculations.PlannedWeek, ...]:
    """A grade que a fachada calcula, usada pelos testes para montar o formulário."""
    from src.modulos.planejamento import service

    return service.computed_planned(fields)


def form_revisao(
    cenario: Cenario,
    *,
    version: int,
    planned: Mapping[str, str] | None = None,
    sm: str | None = None,
    total: str = "120",
    fim: str = "2026-S44",
    perfil: str = calculations.PROFILE_LINEAR,
    justificativa: str = "Reforço do escopo aprovado pela SM do cliente.",
) -> validation.RevisionForm:
    """O formulário da revisão, com a grade livre que o teste montar."""
    fields = {
        validation.FIELD_REVISION_CHANGE: sm if sm is not None else cenario.sm.code,
        validation.FIELD_REVISION_TOTAL: total,
        validation.FIELD_REVISION_FINISH: fim,
        validation.FIELD_REVISION_PROFILE: perfil,
        validation.FIELD_REVISION_JUSTIFICATION: justificativa,
        "versao": str(version),
    }
    return validation.RevisionForm(fields=fields, planned=dict(planned or {}))


@dataclass(frozen=True)
class Envio:
    """O que varia de um pedido para outro: método, campos, consulta, rota e alvo."""

    metodo: str = "GET"
    campos: Mapping[str, str] | Sequence[tuple[str, str]] | None = None
    params: Mapping[str, str] | None = None
    rota: Mapping[str, str] | None = None
    alvo: str = "produtividade-filtros produtividade-conteudo"
    alpine: bool = True


def pedido(caminho: str, *, email: str, envio: Envio | None = None) -> func.HttpRequest:
    """O pedido que o navegador faria, com o principal do e-mail."""
    dados = envio or Envio()
    cabecalhos = {"x-ms-client-principal": cabecalho_do_principal(email)}
    if dados.alpine:
        cabecalhos["X-Alpine-Request"] = "true"
        cabecalhos["X-Alpine-Target"] = dados.alvo
    corpo = b""
    if dados.campos is not None:
        cabecalhos["Content-Type"] = "application/x-www-form-urlencoded"
        pares = (
            list(dados.campos.items()) if isinstance(dados.campos, Mapping) else list(dados.campos)
        )
        corpo = urlencode(pares).encode()
    return func.HttpRequest(
        method=dados.metodo,
        url=caminho,
        headers=cabecalhos,
        params=dict(dados.params or {}),
        route_params=dict(dados.rota or {}),
        body=corpo,
    )


# ── Campo: jornada, amostragem e paralisação (ISSUE-047) ───────────────────


def campos_da_jornada(
    cenario: Cenario,
    *,
    data: str = HOJE.isoformat(),
    area: str = "Flotação 310",
    encarregado: str = "Sérgio Pinto",
    efetivo: str = "12",
    manha: tuple[str, str, str] = ("07:30", "08:00", "11:30"),
    tarde: tuple[str, str, str] = ("13:00", "13:10", "17:00"),
) -> dict[str, str]:
    """Os campos do formulário da jornada, como a tela os envia."""
    return {
        validation.FIELD_DAY_DATE: data,
        validation.FIELD_DAY_COMPANY: str(cenario.empresa.id),
        validation.FIELD_DAY_AREA: area,
        validation.FIELD_DAY_FOREMAN: encarregado,
        validation.FIELD_DAY_CREW: efetivo,
        validation.FIELD_DAY_MORNING: manha[0],
        validation.FIELD_DAY_MORNING_START: manha[1],
        validation.FIELD_DAY_MORNING_END: manha[2],
        validation.FIELD_DAY_AFTERNOON: tarde[0],
        validation.FIELD_DAY_AFTERNOON_START: tarde[1],
        validation.FIELD_DAY_AFTERNOON_END: tarde[2],
        validation.FIELD_DAY_NOTES: "",
    }


def form_jornada(cenario: Cenario, **overrides: str) -> validation.FieldDayForm:
    """O formulário da jornada com os campos padrão do cenário."""
    campos = campos_da_jornada(cenario)
    campos.update(overrides)
    return validation.FieldDayForm(fields=campos)


def campos_da_amostra(
    cenario: Cenario,
    *,
    data: str = HOJE.isoformat(),
    hora: str = "09:30",
    area: str = "Flotação 310",
    encarregado: str = "Sérgio Pinto",
    trabalhando: str = "10",
    parado: Mapping[int, str] | None = None,
    transito: Mapping[int, str] | None = None,
) -> tuple[dict[str, str], dict[int, str], dict[int, str]]:
    """Os campos e as duas grades de motivos do formulário da rodada."""
    campos = {
        validation.FIELD_DAY_DATE: data,
        validation.FIELD_SAMPLE_HOUR: hora,
        validation.FIELD_DAY_COMPANY: str(cenario.empresa.id),
        validation.FIELD_DAY_AREA: area,
        validation.FIELD_DAY_FOREMAN: encarregado,
        validation.FIELD_SAMPLE_WORKING: trabalhando,
    }
    return campos, dict(parado or {}), dict(transito or {})


def form_amostra(
    cenario: Cenario,
    *,
    parado: Mapping[int, str] | None = None,
    transito: Mapping[int, str] | None = None,
    **overrides: str,
) -> validation.WorkSampleForm:
    """O formulário da rodada com os campos padrão do cenário."""
    campos, parados, transitos = campos_da_amostra(cenario, parado=parado, transito=transito)
    campos.update(overrides)
    return validation.WorkSampleForm(fields=campos, stopped=parados, transit=transitos)


def campos_da_paralisacao(
    cenario: Cenario,
    *,
    data: str = HOJE.isoformat(),
    area: str = "Terraplenagem",
    tipo: str = "Efetivo",
    recurso: str = "Equipe de terraplenagem",
    quantidade: str = "16",
    inicio: str = "13:20",
    termino: str = "16:40",
    motivo: str = "Falta de material",
    responsabilidade: str = "Contratada",
) -> dict[str, str]:
    """Os campos do formulário da paralisação, como a tela os envia."""
    return {
        validation.FIELD_DAY_DATE: data,
        validation.FIELD_DAY_COMPANY: str(cenario.empresa.id),
        validation.FIELD_DAY_AREA: area,
        validation.FIELD_STOPPAGE_KIND: tipo,
        validation.FIELD_STOPPAGE_RESOURCE: recurso,
        validation.FIELD_STOPPAGE_QUANTITY: quantidade,
        validation.FIELD_STOPPAGE_START: inicio,
        validation.FIELD_STOPPAGE_END: termino,
        validation.FIELD_STOPPAGE_REASON: motivo,
        validation.FIELD_STOPPAGE_RESPONSIBILITY: responsabilidade,
        validation.FIELD_STOPPAGE_DESCRIPTION: "",
    }


def form_paralisacao(cenario: Cenario, **overrides: str) -> validation.StoppageForm:
    """O formulário da paralisação com os campos padrão do cenário."""
    campos = campos_da_paralisacao(cenario)
    campos.update(overrides)
    return validation.StoppageForm(fields=campos)


# ── KPIs de performance: o plano de ação (ISSUE-048) ───────────────────────


def campos_do_plano(
    cenario: Cenario,
    *,
    empresa: int | None = None,
    assunto: str = "Recuperar a produtividade da empresa (S39)",
    responsavel: int | None = None,
    prevista: str = "2026-10-09",
    descricao: str = "Aderência e fator de produtividade fora da faixa na janela de avaliação.",
) -> dict[str, str]:
    """Os campos do formulário do plano de ação, como a tela os envia."""
    return {
        validation.FIELD_PLAN_COMPANY: str(cenario.empresa.id if empresa is None else empresa),
        validation.FIELD_PLAN_SUBJECT: assunto,
        validation.FIELD_PLAN_DESCRIPTION: descricao,
        validation.FIELD_PLAN_RESPONSIBLE: str(
            cenario.gestor.person_id if responsavel is None else responsavel
        ),
        validation.FIELD_PLAN_DATE: prevista,
    }


def form_plano(cenario: Cenario, **overrides: str) -> validation.ActionPlanForm:
    """O formulário do plano de ação com os campos padrão do cenário."""
    campos = campos_do_plano(cenario)
    campos.update(overrides)
    return validation.ActionPlanForm(fields=campos)
