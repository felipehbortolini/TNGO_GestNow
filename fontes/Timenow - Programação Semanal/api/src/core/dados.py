"""The domain facade — every rule of the weekly schedule lives here.

Blueprints ask this module; this module asks the repository. Nothing
above it knows whether the data sits in a JSON file or in SharePoint, and
nothing below it knows there is an HTTP request.

The flow of one activity, and who moves it:

    criar/editar  →  Fornecedor dentro da janela (ou Timenow, como apoio)
    validar       →  Planejador, que também nomeia o fiscal
    realizado     →  Fornecedor, dia e noite
    aprovar       →  Fiscal, depois de validada
    publicar      →  Planejador ou Admin

Every transition raises :class:`RecusadoError` when the caller may not do it
and :class:`InvalidoError` when the data does not hold up. The blueprint turns
those two into 403 and 422 — no other error shape crosses this line.
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.core import ambiente, auth, calculos, rbac, repositorio, semanas
from src.core import janela as janela_mod

ORDENACOES = {
    "item": "item",
    "id": "id_exclusiva",
    "atividade": "atividade",
    "local": "local",
    "empresa": "empresa",
    "encarregado": "encarregado",
    "fiscal": "responsavel",
    "situacao": "situacao",
    "previsto": "total_previsto",
    "realizado": "total_realizado",
    "ppc": "ppc",
}

_NUMERICAS = {"item", "previsto", "realizado", "ppc"}

FAIXAS_PPC = {
    "baixa": lambda v: v < calculos.FAIXA_MEDIA,
    "media": lambda v: calculos.FAIXA_MEDIA <= v < calculos.FAIXA_ALTA,
    "alta": lambda v: v >= calculos.FAIXA_ALTA,
}


class RecusadoError(PermissionError):
    """The caller is not allowed to do this."""


class InvalidoError(ValueError):
    """The data does not satisfy the rules of the domain."""


def _repo() -> repositorio.Repositorio:
    return repositorio.obter()


def _agora() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# ── Parâmetros e cadastros ──────────────────────────────────────────────


def parametros() -> dict:
    return _repo().obter_parametros()


def repositorio_ativo() -> dict:
    """Where the data lives right now — shown on the Configurações screen."""
    origem = repositorio.origem_ativa()
    return {
        "origem": origem,
        "rotulo": "Arquivos locais (JSON)" if origem == "json" else "SharePoint",
        "caminho": str(getattr(_repo(), "caminho", "")),
        "local": origem == "json",
    }


def salvar_parametros(user, valores: dict) -> dict:
    if not rbac.pode(user, rbac.GERIR_CADASTROS):
        raise RecusadoError("Seu perfil não altera os parâmetros do projeto.")
    return _repo().gravar_parametros(valores)


def listar_locais() -> list[str]:
    return _repo().listar_cadastro("locais")


def listar_empresas() -> list[str]:
    return _repo().listar_cadastro("empresas")


def listar_unidades() -> list[str]:
    return _repo().listar_cadastro("unidades")


def _nomes_com_perfil(perfil: str) -> list[str]:
    """Names of the active people who carry ``perfil``, alphabetically.

    Nomes, e não e-mails, porque é o nome que a atividade guarda e o que
    aparece na matriz. Só os ativos: revogar o acesso de alguém tira essa
    pessoa das próximas programações sem apagar as antigas, que continuam
    mostrando quem de fato respondeu por elas.
    """
    return sorted(
        (c.get("nome") or "").strip()
        for c in _repo().listar_colaboradores()
        if c.get("perfil") == perfil and c.get("ativo", True) and (c.get("nome") or "").strip()
    )


def listar_fiscais() -> list[str]:
    """Quem aprova o realizado — o perfil Fiscal do cadastro de pessoas."""
    return _nomes_com_perfil("fiscal")


def listar_encarregados() -> list[str]:
    """Quem responde pela frente — o perfil Encarregado do cadastro."""
    return _nomes_com_perfil("encarregado")


def cadastros() -> dict:
    """As listas válidas da aplicação, digitadas e derivadas juntas.

    Fiscais e encarregados entram derivados de Colaboradores. Quem
    consome (a planilha de importação, o modelo em Excel) só precisa de
    "que valores são aceitos neste campo" — de onde eles vêm é assunto
    daqui.
    """
    return {
        **{nome: _repo().listar_cadastro(nome) for nome in repositorio.CADASTROS},
        "fiscais": listar_fiscais(),
        "encarregados": listar_encarregados(),
    }


def adicionar_ao_cadastro(user, nome: str, valor: str) -> str:
    if not rbac.pode(user, rbac.GERIR_CADASTROS):
        raise RecusadoError("Seu perfil não altera os cadastros de apoio.")
    if nome not in repositorio.CADASTROS:
        raise InvalidoError("Cadastro desconhecido.")
    valor = (valor or "").strip()
    if not valor:
        raise InvalidoError("Informe o valor a cadastrar.")
    atuais = _repo().listar_cadastro(nome)
    if any(v.lower() == valor.lower() for v in atuais):
        raise InvalidoError(f"“{valor}” já está cadastrado.")
    _repo().gravar_cadastro(nome, [*atuais, valor])
    return valor


def remover_do_cadastro(user, nome: str, valor: str) -> str:
    if not rbac.pode(user, rbac.GERIR_CADASTROS):
        raise RecusadoError("Seu perfil não altera os cadastros de apoio.")
    if nome not in repositorio.CADASTROS:
        raise InvalidoError("Cadastro desconhecido.")
    atuais = _repo().listar_cadastro(nome)
    if valor not in atuais:
        raise InvalidoError(f"“{valor}” não está cadastrado.")

    campo = {"locais": "local", "empresas": "empresa", "unidades": "unidade"}[nome]
    em_uso = sum(1 for a in _repo().listar_atividades() if a.get(campo) == valor)
    if em_uso:
        raise InvalidoError(
            f"“{valor}” está em uso por {em_uso} atividade(s) e não pode ser removido."
        )

    _repo().gravar_cadastro(nome, [v for v in atuais if v != valor])
    return valor


# ── Colaboradores ───────────────────────────────────────────────────────


def listar_colaboradores() -> list[dict]:
    pessoas = _repo().listar_colaboradores()
    pessoas.sort(key=lambda c: (c.get("perfil", ""), c.get("nome", "")))
    return pessoas


def colaborador_por_email(email: str) -> dict | None:
    alvo = (email or "").strip().lower()
    if not alvo:
        return None
    return next(
        (c for c in _repo().listar_colaboradores() if (c.get("email") or "").lower() == alvo),
        None,
    )


def emails_com_acesso() -> list[str]:
    """The e-mails the collaborator register grants entry to, right now.

    Only the active ones: deactivating somebody is refusing them entry,
    and a member list that kept them would contradict the screen that
    says they are out.
    """
    return [
        (c.get("email") or "").strip().lower()
        for c in _repo().listar_colaboradores()
        if c.get("ativo", True) and (c.get("email") or "").strip()
    ]


def sincronizar_acesso(ator: str = "") -> bool:
    """Push the collaborator register into the environment's member index.

    Membership has one editable home — this environment's Colaboradores
    screen — and the register of environments keeps an index so the
    selector reads one file at login instead of opening every base
    (decision 4, revision 3). Every mutation of the collaborator register
    calls this, and so does entering the environment, which is what makes
    a drifted index heal itself.
    """
    from src.core import registro as registro_ambientes

    return registro_ambientes.obter().sincronizar_membros(
        ambiente.slug_ativo(), emails_com_acesso(), ator
    )


def salvar_colaborador(user, campos: dict, *, novo: bool) -> dict:
    if not rbac.pode(user, rbac.GERIR_COLABORADORES):
        raise RecusadoError("Somente o Administrador cria e categoriza colaboradores.")

    email = (campos.get("email") or "").strip().lower()
    existente = colaborador_por_email(email)
    if novo and existente:
        raise InvalidoError(f"{email} já tem acesso cadastrado.")
    if not novo and not existente:
        raise InvalidoError(f"{email} não está cadastrado.")

    registro = {**(existente or {}), **campos, "email": email}
    gravado = _repo().gravar_colaborador(registro)
    # Cadastrar a pessoa aqui É conceder o acesso (revisão 3, item 1):
    # antes eram duas edições em lugares diferentes, e esquecer a do
    # registro produzia alguém cadastrado que não via o ambiente no
    # seletor, sem nenhuma mensagem explicando.
    sincronizar_acesso(user.email if user else "")
    return gravado


def remover_colaborador(user, email: str) -> str:
    if not rbac.pode(user, rbac.GERIR_COLABORADORES):
        raise RecusadoError("Somente o Administrador revoga acessos.")
    email = (email or "").strip().lower()
    if email == (user.email or "").lower():
        raise InvalidoError("Você não pode revogar o próprio acesso.")
    if auth.eh_operador(email):
        # O operador entra implicitamente, presente e futuro: revogar o
        # registro dele não removeria o acesso, só tornaria a lista falsa
        # — e o papel vem da configuração da implantação, não do dado.
        raise RecusadoError("Operadores da Timenow não podem ser removidos por esta tela.")

    restantes = [
        c
        for c in _repo().listar_colaboradores()
        if c.get("perfil") == "admin" and (c.get("email") or "").lower() != email
    ]
    if not restantes:
        raise InvalidoError(
            "Este é o último administrador. Promova outra pessoa antes de removê-lo."
        )

    if not _repo().remover_colaborador(email):
        raise InvalidoError(f"{email} não está cadastrado.")
    # Sair do cadastro é perder o acesso na requisição seguinte — o
    # índice do registro acompanha, senão o ambiente continuaria
    # aparecendo no seletor de quem já não entra nele.
    sincronizar_acesso(user.email if user else "")
    return email


# ── Semanas e janela ────────────────────────────────────────────────────


def semana_padrao() -> str:
    return parametros().get("semana_referencia") or semanas.atual()


def horizonte_de_semanas() -> list[dict]:
    """Weeks with data plus the ones open for programming, chronological."""
    referencias = {a.get("semana", "") for a in _repo().listar_atividades()}
    for j in _repo().listar_janelas():
        referencias.update(j.get("semanas_liberadas") or [])
    referencias.update(semanas.janela_de_semanas(semana_padrao(), atras=1, adiante=1))
    referencias.discard("")
    return [semanas.descrever(s) for s in sorted(referencias, key=semanas.ordem)]


def listar_janelas() -> list[dict]:
    return _repo().listar_janelas()


def obter_janela(empresa: str) -> dict | None:
    return next((j for j in _repo().listar_janelas() if j.get("empresa") == empresa), None)


def salvar_janela(user, dados_janela: dict) -> dict:
    if not rbac.pode(user, rbac.GERIR_JANELAS):
        raise RecusadoError("Seu perfil não configura janelas de programação.")
    empresa = (dados_janela.get("empresa") or "").strip()
    if not empresa:
        raise InvalidoError("Informe a empresa da janela.")
    if empresa not in listar_empresas():
        raise InvalidoError(f"“{empresa}” não é uma empresa cadastrada.")
    return _repo().gravar_janela(dados_janela)


def pode_programar(user, semana: str) -> tuple[bool, str]:
    """May this user write to this week? Returns (yes, reason)."""
    if not user or not rbac.pode(user, rbac.GERAR):
        return False, "Seu perfil não cria programação."
    if not user.eh_fornecedor():
        return True, "Equipe Timenow — programação liberada como apoio."
    return janela_mod.janela_aberta(semana, obter_janela(user.empresa))


def situacao_da_janela(user, semana: str) -> dict:
    aberta, motivo = pode_programar(user, semana)
    return {
        "aberta": aberta,
        "motivo": motivo,
        "empresa": getattr(user, "empresa", ""),
        "eh_fornecedor": bool(user and user.eh_fornecedor()),
    }


# ── Consulta de atividades ──────────────────────────────────────────────


def _escopo(user) -> str | None:
    """The company a user is confined to. None means "sees everything"."""
    return user.empresa if user and user.eh_fornecedor() else None


def listar_atividades(user, semana: str | None = None, filtros: dict | None = None) -> list[dict]:
    """One week's activities, scoped, filtered and sorted.

    Every screen wants a definite week — programação, dashboard,
    exportação — so an absent ``semana`` falls back to the current one
    rather than meaning "every week". That fallback is exactly wrong for
    ``listar_todas_atividades``, which is why it is a function of its
    own instead of a second meaning bolted onto this parameter.
    """
    return _filtrar_e_ordenar(_repo().listar_atividades(semana or semana_padrao()), user, filtros)


def listar_todas_atividades(user, filtros: dict | None = None) -> list[dict]:
    """Every activity of the environment, regardless of week.

    The one caller today is the read API without a ``semana`` filter
    (spec revision 4): a consumer building its own historical aggregate
    wants the whole environment, not one week concatenated by hand. Kept
    apart from :func:`listar_atividades` so that function's default —
    "no week means the current one" — never has to grow a second meaning.
    """
    return _filtrar_e_ordenar(_repo().listar_atividades(None), user, filtros)


def _filtrar_e_ordenar(brutas: list[dict], user, filtros: dict | None = None) -> list[dict]:
    filtros = filtros or {}
    atividades = [calculos.preencher_calculados(a) for a in brutas]

    escopo = _escopo(user)
    if escopo:
        atividades = [a for a in atividades if a.get("empresa") == escopo]

    for campo, chave in (
        ("local", "local"),
        ("empresa", "empresa"),
        ("encarregado", "encarregado"),
        ("responsavel", "responsavel"),
        ("situacao", "situacao"),
    ):
        valor = (filtros.get(campo) or "").strip()
        if valor:
            atividades = [a for a in atividades if a.get(chave) == valor]

    aprovacao = (filtros.get("aprovacao") or "").strip()
    if aprovacao:
        atividades = [a for a in atividades if a.get("aprovacao_realizado") == aprovacao]

    faixa = (filtros.get("ppc") or "").strip()
    if faixa in FAIXAS_PPC:
        dentro = FAIXAS_PPC[faixa]
        atividades = [a for a in atividades if dentro(a.get("ppc", 0))]

    busca = (filtros.get("busca") or "").strip().lower()
    if busca:
        campos = ("id_exclusiva", "atividade", "local", "empresa", "encarregado", "responsavel")
        atividades = [
            a for a in atividades if any(busca in (a.get(c) or "").lower() for c in campos)
        ]

    return _ordenar(atividades, filtros.get("ordena"), filtros.get("ordem"))


def _ordenar(atividades: list[dict], ordena: str | None, ordem: str | None) -> list[dict]:
    chave = ORDENACOES.get(ordena or "")
    if not chave:
        return sorted(atividades, key=lambda a: a.get("item") or 0)
    invertido = str(ordem).lower() == "desc"
    numerica = ordena in _NUMERICAS

    def criterio(a: dict):
        valor = a.get(chave)
        if numerica:
            return calculos.numero(valor)
        return str(valor or "").lower()

    return sorted(atividades, key=criterio, reverse=invertido)


def proximo_item(semana: str) -> int:
    """The sequence number the next activity of the week will take."""
    return _repo().proximo_item(semana)


def obter_atividade(user, chave: str) -> dict | None:
    atividade = _repo().obter_atividade(chave)
    if not atividade:
        return None
    escopo = _escopo(user)
    if escopo and atividade.get("empresa") != escopo:
        return None
    return calculos.preencher_calculados(atividade)


def exigir_atividade(user, chave: str) -> dict:
    atividade = obter_atividade(user, chave)
    if not atividade:
        raise InvalidoError("Atividade não encontrada.")
    return atividade


# ── Escrita ─────────────────────────────────────────────────────────────


CAMPOS_OBRIGATORIOS = (
    ("semana", "a semana"),
    ("id_exclusiva", "a ID exclusiva"),
    ("atividade", "a descrição da atividade"),
    ("local", "o local"),
    ("empresa", "a empresa"),
    ("encarregado", "o encarregado"),
    ("unidade", "a unidade"),
)


def _validar_obrigatorios(payload: dict) -> dict[str, str]:
    return {
        campo: f"Informe {rotulo}."
        for campo, rotulo in CAMPOS_OBRIGATORIOS
        if not str(payload.get(campo) or "").strip()
    }


def _validar_cadastros(payload: dict) -> dict[str, str]:
    """Every list-backed field has to exist in its register.

    A mensagem diz onde resolver. Fiscal e encarregado saem de
    Colaboradores, e mandar quem errou para "Cadastros de apoio" — onde
    esses nomes não estão mais — seria mandá-lo para a tela errada.
    """
    conferencias = (
        ("local", listar_locais, "Cadastros de apoio, em Locais e frentes"),
        ("empresa", listar_empresas, "Cadastros de apoio, em Empresas contratadas"),
        ("unidade", listar_unidades, "Cadastros de apoio, em Unidades de medida"),
        ("responsavel", listar_fiscais, "Colaboradores, com o perfil Fiscal"),
        ("encarregado", listar_encarregados, "Colaboradores, com o perfil Encarregado"),
    )
    erros: dict[str, str] = {}
    for campo, listar, onde in conferencias:
        valor = str(payload.get(campo) or "").strip()
        if valor and valor not in listar():
            erros[campo] = f"“{valor}” não está cadastrado. Cadastre em {onde}."
    return erros


def _validar_quantidades(payload: dict) -> dict[str, str]:
    """The daily plan has to add up to the weekly figure."""
    erros: dict[str, str] = {}
    soma = round(sum(calculos.sete_dias(payload.get("dias_previsto"))), 2)
    prevista = calculos.numero(payload.get("prod_prevista"))

    if soma <= 0:
        erros["dias_previsto"] = "Distribua a produção prevista ao longo da semana."
    if prevista <= 0:
        erros["prod_prevista"] = "Informe a produção prevista na semana."
    elif soma > 0 and abs(soma - prevista) > 0.51:
        erros["dias_previsto"] = (
            f"A soma dos dias ({soma:g}) não bate com a produção prevista ({prevista:g})."
        )
    return erros


def _validar_id_unica(payload: dict, chave_atual: str) -> dict[str, str]:
    semana = str(payload.get("semana") or "").strip()
    id_exclusiva = str(payload.get("id_exclusiva") or "").strip()
    if not (semana and id_exclusiva):
        return {}
    repetida = any(
        a.get("id_exclusiva") == id_exclusiva and a.get("key") != chave_atual
        for a in _repo().listar_atividades(semana)
    )
    if repetida:
        return {"id_exclusiva": f"A ID “{id_exclusiva}” já existe na semana {semana}."}
    return {}


def _validar(payload: dict, chave_atual: str = "") -> dict[str, str]:
    """Field-by-field validation. Returns {field: message}.

    Split into four passes because they answer different questions —
    preenchido, existe no cadastro, fecha a conta, não repete — and porque
    a versão em bloco único já tinha passado do limite de complexidade
    que a porta de qualidade aceita.
    """
    return {
        **_validar_obrigatorios(payload),
        **_validar_cadastros(payload),
        **_validar_quantidades(payload),
        **_validar_id_unica(payload, chave_atual),
    }


def _texto(payload: dict, campo: str) -> str:
    return str(payload.get(campo) or "").strip()


def criar_atividade(user, payload: dict) -> dict:
    if not rbac.pode(user, rbac.GERAR):
        raise RecusadoError("Seu perfil não cria programação.")

    semana = _texto(payload, "semana") or semana_padrao()
    payload["semana"] = semana
    if user.eh_fornecedor():
        payload["empresa"] = user.empresa

    liberado, motivo = pode_programar(user, semana)
    if not liberado:
        raise RecusadoError(motivo)

    erros = _validar(payload)
    if erros:
        raise InvalidoError(erros)

    agora = _agora()
    atividade = {
        "key": repositorio.RepositorioJson.montar_chave(semana, _texto(payload, "id_exclusiva")),
        "item": _repo().proximo_item(semana),
        "semana": semana,
        "id_exclusiva": _texto(payload, "id_exclusiva"),
        "atividade": _texto(payload, "atividade"),
        "local": _texto(payload, "local"),
        "empresa": _texto(payload, "empresa"),
        "responsavel": _texto(payload, "responsavel"),
        "encarregado": _texto(payload, "encarregado"),
        "prod_prevista": calculos.numero(payload.get("prod_prevista")),
        "unidade": _texto(payload, "unidade"),
        "dias_previsto": calculos.sete_dias(payload.get("dias_previsto")),
        "dias_realizado": [0.0] * 7,
        "dias_noite": [0.0] * 7,
        "situacao": "em_elaboracao",
        "aprovacao_realizado": "pendente",
        "observacoes_fornecedor": _texto(payload, "observacoes"),
        "comentarios_timenow": "",
        "criado_em": agora,
        "criado_por": user.email,
        "atualizado_em": agora,
        "atualizado_por": user.email,
    }
    calculos.preencher_calculados(atividade)
    return _repo().gravar_atividade(atividade)


def salvar_atividade(user, chave: str, payload: dict) -> dict:
    if not rbac.pode(user, rbac.EDITAR):
        raise RecusadoError("Seu perfil não edita programação.")

    atual = exigir_atividade(user, chave)
    if atual.get("situacao") == "publicada" and not rbac.pode(user, rbac.PUBLICAR):
        raise RecusadoError("Programação publicada não pode ser editada.")

    if user.eh_fornecedor():
        liberado, motivo = pode_programar(user, atual["semana"])
        if not liberado:
            raise RecusadoError(motivo)
        payload["empresa"] = atual["empresa"]

    payload = {**atual, **{k: v for k, v in payload.items() if v not in ("", None)}}
    payload["semana"] = atual["semana"]

    erros = _validar(payload, chave_atual=atual["key"])
    if erros:
        raise InvalidoError(erros)

    atual.update(
        {
            "atividade": _texto(payload, "atividade"),
            "local": _texto(payload, "local"),
            "empresa": _texto(payload, "empresa"),
            "encarregado": _texto(payload, "encarregado"),
            "responsavel": _texto(payload, "responsavel"),
            "unidade": _texto(payload, "unidade"),
            "prod_prevista": calculos.numero(payload.get("prod_prevista")),
            "dias_previsto": calculos.sete_dias(payload.get("dias_previsto")),
            "observacoes_fornecedor": _texto(payload, "observacoes"),
            "atualizado_em": _agora(),
            "atualizado_por": user.email,
        }
    )
    calculos.preencher_calculados(atual)
    return _repo().gravar_atividade(atual)


def excluir_atividade(user, chave: str) -> dict:
    if not rbac.pode(user, rbac.EXCLUIR):
        raise RecusadoError("Somente o Administrador exclui atividades.")
    atividade = exigir_atividade(user, chave)
    _repo().remover_atividade(atividade["key"])
    return atividade


def registrar_realizado(
    user,
    chave: str,
    dias_realizado: list,
    dias_noite: list,
    observacoes: str = "",
) -> dict:
    """Report what was actually produced, day and night shift."""
    if not rbac.pode(user, rbac.REGISTRAR_REALIZADO):
        raise RecusadoError("Seu perfil não registra o realizado.")

    atividade = exigir_atividade(user, chave)
    if atividade.get("aprovacao_realizado") == "aprovado":
        raise RecusadoError("O realizado já foi aprovado pelo fiscal e não pode mudar.")
    if atividade.get("situacao") == "em_elaboracao":
        raise RecusadoError(
            "A programação ainda não foi validada pelo planejador — não há o que reportar."
        )

    dia = calculos.sete_dias(dias_realizado)
    noite = calculos.sete_dias(dias_noite)
    if any(v < 0 for v in dia + noite):
        raise InvalidoError({"dias_realizado": "Quantidade realizada não pode ser negativa."})

    total = round(sum(dia) + sum(noite), 2)
    previsto = atividade.get("total_previsto") or 0
    config = parametros()
    limite = calculos.numero(config.get("limite_desvio_justificativa"), 15.0)
    exige = bool(config.get("exige_justificativa_desvio"))
    observacoes = (observacoes or "").strip()

    if exige and previsto > 0 and not observacoes:
        desvio = abs(total - previsto) / previsto * 100
        if desvio > limite:
            raise InvalidoError(
                {
                    "observacoes": (
                        f"O realizado está {desvio:.0f}% distante do previsto "
                        f"(limite de {limite:g}%). Explique o desvio para salvar."
                    )
                }
            )

    atividade["dias_realizado"] = dia
    atividade["dias_noite"] = noite
    if observacoes:
        atividade["observacoes_fornecedor"] = observacoes
    atividade["atualizado_em"] = _agora()
    atividade["atualizado_por"] = user.email
    calculos.preencher_calculados(atividade)
    return _repo().gravar_atividade(atividade)


def validar_atividade(user, chave: str, responsavel: str, comentarios: str = "") -> dict:
    if not rbac.pode(user, rbac.VALIDAR):
        raise RecusadoError("Seu perfil não valida programação.")

    atividade = exigir_atividade(user, chave)
    if atividade.get("situacao") != "em_elaboracao":
        raise InvalidoError("Só programação em elaboração pode ser validada.")
    responsavel = (responsavel or "").strip()
    if responsavel not in listar_fiscais():
        raise InvalidoError(
            {"responsavel": "Escolha um fiscal — a lista vem dos colaboradores com esse perfil."}
        )

    atividade["situacao"] = "validada"
    atividade["responsavel"] = responsavel
    if comentarios:
        atividade["comentarios_timenow"] = _anexar_comentario(atividade, comentarios, user)
    atividade["atualizado_em"] = _agora()
    atividade["atualizado_por"] = user.email
    return _repo().gravar_atividade(atividade)


def aprovar_realizado(user, chave: str, comentarios: str = "") -> dict:
    if not rbac.pode(user, rbac.APROVAR_REALIZADO):
        raise RecusadoError("Seu perfil não aprova o realizado.")

    atividade = exigir_atividade(user, chave)
    if atividade.get("situacao") == "em_elaboracao":
        raise InvalidoError("O realizado só chega ao fiscal depois da validação do planejador.")
    if (atividade.get("total_realizado") or 0) <= 0:
        raise InvalidoError("Não há realizado registrado para aprovar.")

    atividade["aprovacao_realizado"] = "aprovado"
    atividade["aprovado_por"] = user.email
    atividade["aprovado_em"] = _agora()
    if comentarios:
        atividade["comentarios_timenow"] = _anexar_comentario(atividade, comentarios, user)
    atividade["atualizado_em"] = _agora()
    atividade["atualizado_por"] = user.email
    return _repo().gravar_atividade(atividade)


def reabrir_realizado(user, chave: str, motivo: str) -> dict:
    """Undo an approval — the fiscal changed their mind, or found an error."""
    if not rbac.pode(user, rbac.APROVAR_REALIZADO):
        raise RecusadoError("Seu perfil não reabre o realizado.")
    motivo = (motivo or "").strip()
    if not motivo:
        raise InvalidoError({"motivo": "Explique por que está reabrindo o realizado."})

    atividade = exigir_atividade(user, chave)
    if atividade.get("aprovacao_realizado") != "aprovado":
        raise InvalidoError("Este realizado não está aprovado.")

    atividade["aprovacao_realizado"] = "pendente"
    atividade["comentarios_timenow"] = _anexar_comentario(
        atividade, f"Realizado reaberto: {motivo}", user
    )
    atividade["atualizado_em"] = _agora()
    atividade["atualizado_por"] = user.email
    return _repo().gravar_atividade(atividade)


def publicar_atividade(user, chave: str) -> dict:
    if not rbac.pode(user, rbac.PUBLICAR):
        raise RecusadoError("Seu perfil não publica programação.")

    atividade = exigir_atividade(user, chave)
    if atividade.get("situacao") != "validada":
        raise InvalidoError("Só programação validada pode ser publicada.")

    atividade["situacao"] = "publicada"
    atividade["publicado_em"] = _agora()
    atividade["atualizado_em"] = _agora()
    atividade["atualizado_por"] = user.email
    return _repo().gravar_atividade(atividade)


def _anexar_comentario(atividade: dict, texto: str, user) -> str:
    carimbo = datetime.now(UTC).strftime("%d/%m %H:%M")
    novo = f"[{carimbo} · {user.nome}] {texto}"
    return f"{atividade.get('comentarios_timenow', '')}\n{novo}".strip()


def importar_atividades(user, linhas: list[dict]) -> dict:
    """Batch insert from the spreadsheet — one bad row never stops the rest."""
    if not rbac.pode(user, rbac.IMPORTAR):
        raise RecusadoError("Seu perfil não importa planilha.")

    inseridas: list[dict] = []
    recusadas: list[dict] = []
    for linha in linhas:
        try:
            inseridas.append(criar_atividade(user, dict(linha)))
        except InvalidoError as erro:
            recusadas.append({"id": linha.get("id_exclusiva", ""), "motivo": _mensagem(erro)})
        except RecusadoError as erro:
            recusadas.append({"id": linha.get("id_exclusiva", ""), "motivo": str(erro)})
    return {"inseridas": inseridas, "recusadas": recusadas}


def _mensagem(erro: InvalidoError) -> str:
    detalhe = erro.args[0] if erro.args else ""
    if isinstance(detalhe, dict):
        return " ".join(detalhe.values())
    return str(detalhe)


# ── Leituras agregadas ──────────────────────────────────────────────────


def contagem_por_situacao(atividades: list[dict]) -> dict:
    return {
        "em_elaboracao": sum(1 for a in atividades if a.get("situacao") == "em_elaboracao"),
        "validada": sum(1 for a in atividades if a.get("situacao") == "validada"),
        "publicada": sum(1 for a in atividades if a.get("situacao") == "publicada"),
        "aprovadas": sum(1 for a in atividades if a.get("aprovacao_realizado") == "aprovado"),
        "pendentes": sum(
            1
            for a in atividades
            if a.get("aprovacao_realizado") == "pendente" and (a.get("total_realizado") or 0) > 0
        ),
        "sem_realizado": sum(1 for a in atividades if (a.get("total_realizado") or 0) <= 0),
    }


def resumo_semana(user, semana: str | None = None) -> dict:
    """The numbers the home screen leads with."""
    semana = semana or semana_padrao()
    atividades = listar_atividades(user, semana)
    situacao = contagem_por_situacao(atividades)
    config = parametros()

    aguardando = [
        a
        for a in atividades
        if a.get("aprovacao_realizado") == "pendente" and (a.get("total_realizado") or 0) > 0
    ]
    criticas = sorted(
        (a for a in atividades if (a.get("total_previsto") or 0) > 0),
        key=lambda a: a.get("ppc", 0),
    )[:5]

    return {
        "semana": semana,
        "periodo": semanas.periodo(semana),
        "aderencia": calculos.aderencia_geral(atividades),
        "ppc_medio": calculos.ppc_medio(atividades),
        "meta_aderencia": calculos.numero(config.get("meta_aderencia"), 60.0),
        "meta_ppc": calculos.numero(config.get("meta_ppc"), 75.0),
        "total_atividades": len(atividades),
        "empresas_ativas": len({a.get("empresa") for a in atividades if a.get("empresa")}),
        "frentes_ativas": len({a.get("local") for a in atividades if a.get("local")}),
        "situacao": situacao,
        "aguardando_aprovacao": aguardando,
        "criticas": criticas,
        "por_dia": calculos.por_dia(atividades),
        "por_empresa": calculos.quebrar_por(atividades, "empresa"),
    }


# ── Pedidos de alteração (Request → Apply) ──────────────────────────────
#
# Existe porque programação publicada e realizado aprovado deixam de ser
# editáveis — e às vezes precisam mudar mesmo assim. Sem uma fila, o
# caminho vira telefonema para o administrador, que altera direto e sem
# rastro. Aqui o pedido fica escrito, com quem pediu, por quê, e quem
# decidiu.
#
# Aplicar NÃO altera o dado sozinho: registra a decisão, libera o item e
# anota o combinado nos comentários. Quem executa a mudança é a pessoa,
# pela tela normal — um aplicador automático precisaria de um diff que o
# pedido não carrega, e adivinhar o que mudar é pior que não mudar.

SITUACOES_PEDIDO = ("pendente", "aplicado", "rejeitado")


def listar_pedidos(user) -> dict:
    """Pedidos de alteração, separados entre pendentes e resolvidos."""
    pedidos = _repo().listar_solicitacoes()
    escopo = _escopo(user)
    if escopo:
        pedidos = [p for p in pedidos if p.get("empresa") == escopo]
    pedidos.sort(key=lambda p: p.get("solicitado_em") or "", reverse=True)
    return {
        "pendentes": [p for p in pedidos if p.get("situacao") == "pendente"],
        "resolvidos": [p for p in pedidos if p.get("situacao") != "pendente"][:20],
        "total_pendentes": sum(1 for p in pedidos if p.get("situacao") == "pendente"),
    }


def pedir_alteracao(user, chave: str, motivo: str) -> dict:
    """Coloca um pedido na fila. Qualquer perfil que enxerga o item pode."""
    if not rbac.pode(user, rbac.VER):
        raise RecusadoError("Seu perfil não abre pedidos de alteração.")
    motivo = (motivo or "").strip()
    if len(motivo) < 10:
        raise InvalidoError({"motivo": "Explique o que precisa mudar, e por quê, em uma frase."})

    atividade = exigir_atividade(user, chave)
    pedido = {
        "key": atividade["key"],
        "id_exclusiva": atividade["id_exclusiva"],
        "atividade": atividade["atividade"],
        "empresa": atividade["empresa"],
        "semana": atividade["semana"],
        "motivo": motivo,
        "situacao": "pendente",
        "solicitado_por": user.email,
        "solicitado_nome": user.nome,
    }
    return _repo().gravar_solicitacao(pedido)


def resolver_pedido(user, identificador: str, *, aplicar: bool, resposta: str = "") -> dict:
    """Aplica ou rejeita um pedido, e deixa a decisão registrada na atividade."""
    if not rbac.pode(user, rbac.APLICAR):
        raise RecusadoError("Somente o Administrador decide pedidos de alteração.")

    pedido = next((p for p in _repo().listar_solicitacoes() if p.get("id") == identificador), None)
    if not pedido:
        raise InvalidoError("Pedido não encontrado.")
    if pedido.get("situacao") != "pendente":
        raise InvalidoError("Este pedido já foi decidido.")

    resposta = (resposta or "").strip()
    if not aplicar and len(resposta) < 5:
        raise InvalidoError({"resposta": "Diga por que o pedido está sendo recusado."})

    pedido.update(
        {
            "situacao": "aplicado" if aplicar else "rejeitado",
            "decidido_por": user.email,
            "decidido_em": _agora(),
            "resposta": resposta,
        }
    )
    _repo().gravar_solicitacao(pedido)

    atividade = _repo().obter_atividade(pedido["key"])
    if atividade:
        veredito = "liberado para alteração" if aplicar else "recusado"
        atividade["comentarios_timenow"] = _anexar_comentario(
            atividade,
            f"Pedido de alteração {veredito}: {pedido['motivo']}"
            + (f" — {resposta}" if resposta else ""),
            user,
        )
        if aplicar and atividade.get("aprovacao_realizado") == "aprovado":
            # Liberar é o efeito concreto de aplicar: sem isto o pedido
            # seria só um bilhete, e a pessoa continuaria travada.
            atividade["aprovacao_realizado"] = "pendente"
        atividade["atualizado_em"] = _agora()
        atividade["atualizado_por"] = user.email
        _repo().gravar_atividade(atividade)

    return pedido


def governanca(user) -> dict:
    """One row per company and week — who is where in the flow."""
    atividades = [calculos.preencher_calculados(a) for a in _repo().listar_atividades()]
    escopo = _escopo(user)
    if escopo:
        atividades = [a for a in atividades if a.get("empresa") == escopo]

    semana_atual = semana_padrao()
    janelas = _repo().listar_janelas()

    grupos: dict[tuple[str, str], dict] = {}
    for a in atividades:
        chave = (a.get("empresa", ""), a.get("semana", ""))
        grupo = grupos.setdefault(
            chave,
            {
                "empresa": chave[0],
                "semana": chave[1],
                "periodo": semanas.periodo(chave[1]),
                "total": 0,
                "em_elaboracao": 0,
                "validada": 0,
                "publicada": 0,
                "pendencias": 0,
                "responsavel": "",
                "aderencia": 0.0,
                "atualizado_em": "",
                "atividades": [],
            },
        )
        grupo["total"] += 1
        situacao_atividade = a.get("situacao", "em_elaboracao")
        if situacao_atividade in grupo:
            grupo[situacao_atividade] += 1
        if a.get("aprovacao_realizado") == "pendente" and (a.get("total_realizado") or 0) > 0:
            grupo["pendencias"] += 1
        if a.get("responsavel"):
            grupo["responsavel"] = a["responsavel"]
        grupo["atualizado_em"] = max(grupo["atualizado_em"], a.get("atualizado_em") or "")
        grupo["atividades"].append(a)

    linhas = []
    for grupo in grupos.values():
        grupo["aderencia"] = calculos.aderencia_geral(grupo.pop("atividades"))
        linhas.append(grupo)
    linhas.sort(key=lambda g: (semanas.ordem(g["semana"]), g["empresa"]), reverse=True)

    situacao = contagem_por_situacao(atividades)
    return {
        "linhas": linhas,
        "situacao": situacao,
        "total_atividades": len(atividades),
        "fornecedores_ativos": len({a.get("empresa") for a in atividades if a.get("empresa")}),
        "janelas_abertas": sum(1 for j in janelas if janela_mod.janela_aberta(semana_atual, j)[0]),
        "janelas": [janela_mod.resumo(j, semana_atual) for j in janelas],
        "semana": semana_atual,
    }
