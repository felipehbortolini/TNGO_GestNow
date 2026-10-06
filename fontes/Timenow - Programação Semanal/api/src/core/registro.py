"""The register of environments — the global record above every client.

One installation hosts several environments; this is the record that
says which ones exist, what each is called and which e-mails may enter
each. It is a **port of its own**, sibling of :class:`Repositorio` and
not part of it: the persistence port is per environment, and asking an
environment for the list of environments would invert the hierarchy.

It sits behind a port — instead of a module reading the file directly —
because swapping the persistence technology keeps being an environment
variable (decision 15); without the port, the environments would migrate
to SharePoint lists while the register stayed stuck in a local file.

The record lives at the root of the data directory, beside the
environment folders and never inside one::

    data/
      registro.json
      registro-trilha.jsonl
      mccain/
        programacao.json
        auditoria.jsonl

The register has a trail of its own, separate from every environment's:
creating, archiving, granting and revoking are events of the register,
not of any client. Token methods enter in delivery 3 (ISSUE-017) — the
surface is reserved below so the register remains the single owner of
members and credentials.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import tempfile
import threading
from abc import ABC, abstractmethod
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from src.core import ambiente, repositorio
from src.core.dados import InvalidoError
from src.core.repositorio import diretorio_de_dados

SLUG_FORMATO = re.compile(r"^[a-z0-9-]{2,32}$")

# O que a criação de um ambiente copia do base. É o que se repete entre
# clientes sem pertencer a nenhum — e é uma lista fechada de propósito:
# o resto é dado operacional de um cliente e nunca pode entrar no outro.
PARAMETROS_CLONAVEIS = (
    "meta_aderencia",
    "meta_ppc",
    "exige_justificativa_desvio",
    "limite_desvio_justificativa",
)

ACOES_REGISTRO = {
    "criar": "Criou o ambiente",
    "arquivar": "Arquivou o ambiente",
    "desarquivar": "Desarquivou o ambiente",
    "conceder": "Concedeu acesso ao ambiente",
    "revogar": "Revogou o acesso ao ambiente",
    "sincronizar": "Sincronizou os membros com o cadastro",
    "promover": "Promoveu a operador",
    "rebaixar": "Rebaixou de operador",
    "token_emitido": "Emitiu token de leitura",
    "token_revogado": "Revogou token de leitura",
    "api": "Consumiu a API",
}


def _normalizar_email(email: str) -> str:
    return (email or "").strip().lower()


def _hash_do_token(valor: str) -> str:
    """SHA-256 do token inteiro — sem sal, sem derivação lenta, de propósito.

    Token de máquina não é senha de gente: sal e derivação lenta existem
    para proteger segredo que humano escolheu e que cabe num dicionário.
    Um segredo aleatório de ~190 bits não é adivinhável nem com o hash em
    mãos, e uma derivação lenta custaria dezenas de milissegundos em cada
    chamada do consumidor — mais uma dependência — para comprar segurança
    que a entropia já deu. Não "conserte" isto para bcrypt.
    """
    return hashlib.sha256(valor.encode("utf-8")).hexdigest()


class RegistroAmbientes(ABC):
    """The contract of the register of environments.

    Narrow on purpose: the selector, the HTTP resolution and the
    operator screens all live on this surface, and each extra method is
    one more thing to keep in sync when the register migrates with the
    persistence port.
    """

    @abstractmethod
    def listar_por_email(self, email: str) -> list[dict]:
        """The ACTIVE environments where ``email`` is a member."""

    @abstractmethod
    def listar_todos(self) -> list[dict]:
        """Every environment that exists, active and archived alike."""

    @abstractmethod
    def obter(self, identificador: str) -> dict | None:
        """One environment, in any situation — None when it never existed."""

    @abstractmethod
    def criar(self, identificador: str, projeto: str, cliente: str, ator: str) -> dict:
        """Create an active environment with no members."""

    @abstractmethod
    def arquivar(self, identificador: str, ator: str) -> dict:
        """Suspend an environment. State, not deletion — nothing is erased."""

    @abstractmethod
    def desarquivar(self, identificador: str, ator: str) -> dict:
        """Bring an archived environment back, members included."""

    @abstractmethod
    def conceder(self, identificador: str, email: str, ator: str) -> dict:
        """Grant one e-mail the right to enter one environment."""

    @abstractmethod
    def revogar(self, identificador: str, email: str, ator: str) -> dict:
        """Take that right back — effective on the next listing."""

    @abstractmethod
    def listar_membros(self, identificador: str) -> list[str]:
        """The e-mails who may enter one environment."""

    @abstractmethod
    def sincronizar_membros(self, identificador: str, emails: list[str], ator: str) -> bool:
        """Make the index match the environment's collaborator register.

        Membership has one editable home — the Colaboradores screen of
        the environment — and this index exists so the selector reads one
        file at login instead of opening every environment's base
        (decision 4). Writes only when the two actually diverge, so the
        reconciliation on entry costs a read in the common case.

        Returns whether anything changed.
        """

    @abstractmethod
    def recentes(self, limite: int = 60) -> list[dict]:
        """Last events of the register's own trail, newest first."""

    # ── Operadores promovidos ─────────────────────────────────────────
    # O piso continua na variável de ambiente (decisão 11): sempre existe
    # operador, mesmo com o registro vazio ou corrompido. Estes são os
    # ADICIONAIS, promovidos em tela, e só eles podem ser rebaixados.

    @abstractmethod
    def listar_operadores(self) -> list[str]:
        """The e-mails promoted to operator through the screen."""

    @abstractmethod
    def promover_operador(self, email: str, ator: str) -> list[str]:
        """Promote one e-mail — effective on the next request."""

    @abstractmethod
    def rebaixar_operador(self, email: str, ator: str) -> list[str]:
        """Take the promotion back. Never touches the ones from the config."""

    # ── Tokens de leitura ─────────────────────────────────────────────
    # A credencial da API: emitida pelo operador, vinculada a UM
    # ambiente, somente leitura. O registro guarda o hash — nunca o
    # valor — e a emissão devolve o valor completo uma única vez.

    @abstractmethod
    def emitir_token(self, identificador: str, rotulo: str, ator: str, validade: str = "") -> dict:
        """Issue one token. Returns the record WITH the full value, once."""

    @abstractmethod
    def listar_tokens(self, identificador: str) -> list[dict]:
        """The tokens of one environment — never their values."""

    @abstractmethod
    def revogar_token(self, identificador: str, prefixo: str, ator: str) -> dict:
        """Kill one token — effective on the next request."""

    @abstractmethod
    def verificar_token(self, valor: str) -> dict:
        """Resolve one credential to its record, or refuse with a reason."""

    @abstractmethod
    def registrar_uso(self, prefixo: str) -> bool:
        """Stamp the last use — rewrites the record at most once an hour."""

    @abstractmethod
    def registrar_acesso_api(
        self, ambiente: str, prefixo: str, recurso: str, recusado: str = ""
    ) -> None:
        """Append one consumption line to the register's own trail."""


class RegistroJson(RegistroAmbientes):
    """The register as one JSON file, written atomically, guarded by a lock.

    Same atomicity as ``RepositorioJson`` — temporary file and rename,
    one ``RLock`` — because the network mode puts several people on the
    same file, and a half-written ``registro.json`` would take the whole
    installation down, selector included.
    """

    def __init__(self, caminho: str | Path | None = None):
        self.caminho = Path(caminho or diretorio_de_dados() / "registro.json")
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self._trava = threading.RLock()

    # -- arquivo ----------------------------------------------------
    def _ler(self) -> dict:
        try:
            with self.caminho.open(encoding="utf-8") as arquivo:
                dados = json.load(arquivo)
        except (FileNotFoundError, json.JSONDecodeError):
            return self._semear()
        return self._garantir_forma(dados)

    def _gravar(self, dados: dict) -> None:
        destino = self.caminho
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=destino.parent, delete=False, suffix=".tmp"
        ) as tmp:
            json.dump(dados, tmp, indent=2, ensure_ascii=False)
            temporario = Path(tmp.name)
        temporario.replace(destino)

    def _semear(self) -> dict:
        # A demonstração nasce pronta: dois ambientes no registro, para o
        # duplo clique abrir o seletor com duas caixas sem nenhum comando
        # prévio. Fora dela, um registro limpo nasce vazio — ambientes são
        # criados pelo operador, nunca aparecem sozinhos.
        from src.core import auth

        ambientes = []
        if auth.modo_demo():
            ambientes = [
                {
                    "id": "demo-obra",
                    "projeto": "Obra de demonstração",
                    "cliente": "Cliente demonstração",
                    "situacao": "ativo",
                    "membros": [],
                },
                {
                    "id": "demo-planta",
                    "projeto": "Planta de demonstração",
                    "cliente": "Cliente demonstração",
                    "situacao": "ativo",
                    "membros": [],
                },
            ]
        dados = self._garantir_forma({"ambientes": ambientes})
        self._gravar(dados)
        return dados

    @staticmethod
    def _garantir_forma(dados: dict) -> dict:
        dados.setdefault("ambientes", [])
        dados.setdefault("operadores", [])
        return dados

    def _trilha(self) -> Path:
        return self.caminho.parent / "registro-trilha.jsonl"

    def _registrar_evento(
        self, acao: str, ator: str, identificador: str, resumo: str, email: str = ""
    ) -> None:
        evento = {
            "quando": datetime.now(UTC).isoformat(timespec="seconds"),
            "acao": acao,
            "rotulo": ACOES_REGISTRO[acao],
            "ator": ator,
            "resumo": resumo,
            "contexto": {"id": identificador, "email": email},
        }
        try:
            with self._trilha().open("a", encoding="utf-8") as trilha:
                trilha.write(json.dumps(evento, ensure_ascii=False) + "\n")
        except OSError:
            # Trilha indisponível não pode derrubar a operação que ela observa.
            return

    # -- consulta ----------------------------------------------------
    def listar_por_email(self, email: str) -> list[dict]:
        alvo = _normalizar_email(email)
        with self._trava:
            ambientes = self._ler()["ambientes"]
        return [
            dict(a)
            for a in ambientes
            if a.get("situacao") == "ativo" and alvo in a.get("membros", [])
        ]

    def listar_todos(self) -> list[dict]:
        with self._trava:
            ambientes = self._ler()["ambientes"]
        return [dict(a) for a in ambientes]

    def obter(self, identificador: str) -> dict | None:
        with self._trava:
            ambientes = self._ler()["ambientes"]
        alvo = next((a for a in ambientes if a.get("id") == identificador), None)
        return dict(alvo) if alvo else None

    def listar_membros(self, identificador: str) -> list[str]:
        ambiente = self._exigir(identificador)
        return list(ambiente.get("membros", []))

    # -- mutação -----------------------------------------------------
    def criar(self, identificador: str, projeto: str, cliente: str, ator: str) -> dict:
        identificador = (identificador or "").strip()
        projeto = (projeto or "").strip()
        cliente = (cliente or "").strip()
        if not identificador:
            raise InvalidoError("Informe o identificador do ambiente.")
        self._validar_slug(identificador)
        if not projeto:
            raise InvalidoError("Informe o nome do projeto.")
        if not cliente:
            raise InvalidoError("Informe o nome do cliente.")

        with self._trava:
            dados = self._ler()
            if any(a.get("id") == identificador for a in dados["ambientes"]):
                # Nunca reaproveitado, inclusive depois de arquivado: o slug
                # vaza para pasta, cookie, cabeçalho e trilhas, e reaproveitá-lo
                # faria o histórico de dois contratos se confundir.
                raise InvalidoError(
                    f"O identificador “{identificador}” já existe — inclusive arquivado — "
                    "e identificador de ambiente nunca é reaproveitado."
                )
            ambiente = {
                "id": identificador,
                "projeto": projeto,
                "cliente": cliente,
                "situacao": "ativo",
                "membros": [],
            }
            dados["ambientes"].append(ambiente)
            self._gravar(dados)

        self._registrar_evento(
            "criar", ator, identificador, f"Ambiente “{identificador}” ({projeto} — {cliente})."
        )
        return dict(ambiente)

    def arquivar(self, identificador: str, ator: str) -> dict:
        self._exigir(identificador)
        with self._trava:
            dados = self._ler()
            ambiente = self._localizar(dados, identificador)
            ambiente["situacao"] = "arquivado"
            self._gravar(dados)
        self._registrar_evento(
            "arquivar", ator, identificador, f"Ambiente “{identificador}” arquivado."
        )
        return dict(ambiente)

    def desarquivar(self, identificador: str, ator: str) -> dict:
        self._exigir(identificador)
        with self._trava:
            dados = self._ler()
            ambiente = self._localizar(dados, identificador)
            ambiente["situacao"] = "ativo"
            self._gravar(dados)
        self._registrar_evento(
            "desarquivar", ator, identificador, f"Ambiente “{identificador}” desarquivado."
        )
        return dict(ambiente)

    def conceder(self, identificador: str, email: str, ator: str) -> dict:
        self._exigir(identificador)
        alvo = _normalizar_email(email)
        if not alvo:
            raise InvalidoError("Informe o e-mail do membro.")
        with self._trava:
            dados = self._ler()
            ambiente = self._localizar(dados, identificador)
            if alvo not in ambiente["membros"]:
                ambiente["membros"].append(alvo)
                self._gravar(dados)
        self._registrar_evento(
            "conceder",
            ator,
            identificador,
            f"Acesso de {alvo} ao ambiente “{identificador}”.",
            alvo,
        )
        return dict(ambiente)

    def revogar(self, identificador: str, email: str, ator: str) -> dict:
        self._exigir(identificador)
        alvo = _normalizar_email(email)
        if not alvo:
            raise InvalidoError("Informe o e-mail do membro.")
        with self._trava:
            dados = self._ler()
            ambiente = self._localizar(dados, identificador)
            if alvo in ambiente["membros"]:
                ambiente["membros"] = [m for m in ambiente["membros"] if m != alvo]
                self._gravar(dados)
        self._registrar_evento(
            "revogar",
            ator,
            identificador,
            f"Acesso de {alvo} ao ambiente “{identificador}” revogado.",
            alvo,
        )
        return dict(ambiente)

    def sincronizar_membros(self, identificador: str, emails: list[str], ator: str) -> bool:
        """Reconcile the index with the environment's collaborator register.

        The index can drift: a base edited by hand, a write interrupted
        halfway, an environment created before membership moved to the
        register of collaborators. Reconciling on entry means the drift
        never outlives one visit — and comparing before writing means the
        common case (no drift) costs a read and nothing else.
        """
        self._exigir(identificador)
        alvos = sorted({_normalizar_email(e) for e in emails if _normalizar_email(e)})
        with self._trava:
            dados = self._ler()
            ambiente_registrado = self._localizar(dados, identificador)
            if sorted(ambiente_registrado.get("membros", [])) == alvos:
                return False
            ambiente_registrado["membros"] = alvos
            self._gravar(dados)
        self._registrar_evento(
            "sincronizar",
            ator,
            identificador,
            f"Membros de “{identificador}” alinhados ao cadastro de colaboradores.",
        )
        return True

    # -- operadores promovidos ---------------------------------------
    def listar_operadores(self) -> list[str]:
        with self._trava:
            return list(self._ler().get("operadores", []))

    def promover_operador(self, email: str, ator: str) -> list[str]:
        alvo = _normalizar_email(email)
        if not alvo:
            raise InvalidoError("Informe o e-mail de quem será promovido.")
        with self._trava:
            dados = self._ler()
            if alvo in dados["operadores"]:
                raise InvalidoError(f"{alvo} já é operador.")
            dados["operadores"].append(alvo)
            self._gravar(dados)
            promovidos = list(dados["operadores"])
        self._registrar_evento(
            "promover", ator, "", f"{alvo} promovido a operador da instalação.", alvo
        )
        return promovidos

    def rebaixar_operador(self, email: str, ator: str) -> list[str]:
        alvo = _normalizar_email(email)
        with self._trava:
            dados = self._ler()
            if alvo not in dados["operadores"]:
                # Quem vem da variável de ambiente não está aqui, e é
                # exatamente por isso que a tela não o rebaixa: o piso
                # mora fora do dado (decisão 11).
                raise InvalidoError(
                    f"{alvo} não foi promovido por esta tela e não pode ser rebaixado por ela."
                )
            dados["operadores"] = [o for o in dados["operadores"] if o != alvo]
            self._gravar(dados)
            promovidos = list(dados["operadores"])
        self._registrar_evento(
            "rebaixar", ator, "", f"{alvo} deixou de ser operador da instalação.", alvo
        )
        return promovidos

    # -- trilha ------------------------------------------------------
    def recentes(self, limite: int = 60) -> list[dict]:
        try:
            linhas = self._trilha().read_text(encoding="utf-8").splitlines()
        except OSError:
            return []

        eventos = []
        for linha in reversed(linhas):
            if not linha.strip():
                continue
            try:
                eventos.append(json.loads(linha))
            except json.JSONDecodeError:
                continue
            if len(eventos) >= limite:
                break
        return eventos

    # -- tokens de leitura --------------------------------------------
    def emitir_token(self, identificador: str, rotulo: str, ator: str, validade: str = "") -> dict:
        self._exigir(identificador)
        rotulo = (rotulo or "").strip()
        if not rotulo:
            raise InvalidoError("Informe o rótulo do token.")
        if validade:
            try:
                date.fromisoformat(validade)
            except ValueError:
                raise InvalidoError("Validade inválida — use AAAA-MM-DD.") from None

        segredo = secrets.token_urlsafe(32)
        prefixo = "tn_" + secrets.token_hex(4)
        valor = f"{prefixo}_{segredo}"
        registro_token = {
            "rotulo": rotulo,
            "prefixo": prefixo,
            "hash": _hash_do_token(valor),
            "ambiente": identificador,
            "emitido_por": ator,
            "emitido_em": datetime.now(UTC).isoformat(timespec="seconds"),
            "validade": validade,
            "revogado": False,
            "ultimo_uso": "",
        }
        with self._trava:
            dados = self._ler()
            self._localizar(dados, identificador).setdefault("tokens", []).append(registro_token)
            self._gravar(dados)
        self._registrar_evento(
            "token_emitido",
            ator,
            identificador,
            f"Token “{rotulo}” ({prefixo}) emitido para o ambiente “{identificador}”.",
        )
        devolvido = {chave: valor for chave, valor in registro_token.items() if chave != "hash"}
        return {"valor": valor, **devolvido}

    def listar_tokens(self, identificador: str) -> list[dict]:
        ambiente = self._exigir(identificador)
        return [
            {chave: valor for chave, valor in token.items() if chave != "hash"}
            for token in ambiente.get("tokens", [])
        ]

    def revogar_token(self, identificador: str, prefixo: str, ator: str) -> dict:
        self._exigir(identificador)
        with self._trava:
            dados = self._ler()
            token = self._localizar_token(dados, identificador, prefixo)
            token["revogado"] = True
            self._gravar(dados)
        self._registrar_evento(
            "token_revogado",
            ator,
            identificador,
            f"Token “{token.get('rotulo', prefixo)}” ({prefixo}) revogado.",
        )
        return {chave: valor for chave, valor in token.items() if chave != "hash"}

    def verificar_token(self, valor: str) -> dict:
        """Resolve one credential to its record, or refuse with the reason.

        Locates by the visible prefix and compares digests in constant
        time. Refusals name their cause — malformed, unknown, revoked,
        expired. The archived-environment case is NOT decided here: the
        token stays alive while its environment is suspended, and the
        HTTP seam answers that refusal (decision 13).
        """
        valor = (valor or "").strip()
        partes = valor.split("_")
        if len(partes) < 3 or not valor.startswith("tn_"):
            raise InvalidoError("Token malformado.")
        # `tn_<prefixo>_<segredo>`: o prefixo são as DUAS primeiras partes
        # (hex, sem sublinhado); o segredo é base64url e PODE conter `_`,
        # então o resto inteiro pertence a ele.
        prefixo = "_".join(partes[:2])

        with self._trava:
            dados = self._ler()
        token = next(
            (
                token
                for ambiente in dados["ambientes"]
                for token in ambiente.get("tokens", [])
                if token.get("prefixo") == prefixo
            ),
            None,
        )
        if not token or not hmac.compare_digest(token.get("hash", ""), _hash_do_token(valor)):
            raise InvalidoError("Token inexistente ou incorreto.")
        if token.get("revogado"):
            raise InvalidoError("Token revogado.")
        validade = token.get("validade") or ""
        if validade:
            try:
                vencimento = date.fromisoformat(validade)
            except ValueError:
                raise InvalidoError("Token com validade inválida.") from None
            if vencimento < datetime.now(UTC).date():
                raise InvalidoError("Token expirado.")
        return token

    def registrar_uso(self, prefixo: str) -> bool:
        """Stamp the last use — amortized to at most one rewrite an hour.

        Rewriting the register on every read would turn the one file
        that takes everyone down into the most-written file of the
        installation, at the pace of an automated refresh. The screen
        only needs hour precision to decide what to revoke.
        """
        with self._trava:
            dados = self._ler()
            token = next(
                (
                    token
                    for ambiente in dados["ambientes"]
                    for token in ambiente.get("tokens", [])
                    if token.get("prefixo") == prefixo
                ),
                None,
            )
            if not token:
                return False
            agora = datetime.now(UTC)
            guardado = token.get("ultimo_uso") or ""
            if guardado:
                try:
                    anterior = datetime.fromisoformat(guardado.replace("Z", "+00:00"))
                    if agora - anterior < timedelta(hours=1):
                        return False
                except ValueError:
                    pass
            token["ultimo_uso"] = agora.isoformat(timespec="seconds")
            self._gravar(dados)
        return True

    def registrar_acesso_api(
        self, ambiente: str, prefixo: str, recurso: str, recusado: str = ""
    ) -> None:
        """One consumption line, appended — the trail is never read to write.

        Same cheap mechanism as the audit trail: a single open-for-append
        that never looks at the previous content. A trail failure must
        not take down the API response it observes.
        """
        evento = {
            "quando": datetime.now(UTC).isoformat(timespec="seconds"),
            "acao": "api",
            "rotulo": ACOES_REGISTRO["api"],
            "ator": prefixo,
            "resumo": f"{recurso} — {prefixo}{' (recusado)' if recusado else ''}",
            "contexto": {
                "id": ambiente,
                "prefixo": prefixo,
                "recurso": recurso,
                "recusado": recusado,
            },
        }
        try:
            with self._trilha().open("a", encoding="utf-8") as trilha:
                trilha.write(json.dumps(evento, ensure_ascii=False) + "\n")
        except OSError:
            # Trilha indisponível não pode derrubar a resposta da API.
            return

    @staticmethod
    def _localizar_token(dados: dict, identificador: str, prefixo: str) -> dict:
        ambiente = next(a for a in dados["ambientes"] if a.get("id") == identificador)
        token = next(t for t in ambiente.get("tokens", []) if t.get("prefixo") == prefixo)
        if not token:
            raise InvalidoError(f"Token “{prefixo}” não encontrado.")
        return token

    # -- apoio -------------------------------------------------------
    def _validar_slug(self, identificador: str) -> None:
        if not SLUG_FORMATO.fullmatch(identificador):
            raise InvalidoError(
                f"O identificador “{identificador}” é inválido: use de 2 a 32 letras "
                "minúsculas, números e hífens."
            )

    def _exigir(self, identificador: str) -> dict:
        ambiente = self.obter(identificador)
        if not ambiente:
            raise InvalidoError(f"Ambiente “{identificador}” não encontrado.")
        return ambiente

    @staticmethod
    def _localizar(dados: dict, identificador: str) -> dict:
        return next(a for a in dados["ambientes"] if a.get("id") == identificador)


_ativo: RegistroAmbientes | None = None


def obter() -> RegistroAmbientes:
    """The register in force — one per installation, not per environment.

    Unlike the persistence port, this is a plain process singleton: the
    register sits above every environment and has no active-environment
    dimension to resolve. The SharePoint implementation plugs in here
    when the register migrates along with the port (decision 15).
    """
    global _ativo
    if _ativo is None:
        _ativo = RegistroJson()
    return _ativo


def definir(registro: RegistroAmbientes | None) -> None:
    """Replace the active register — the test seam."""
    global _ativo
    _ativo = registro


def criar_ambiente(
    identificador: str,
    projeto: str,
    cliente: str,
    ator: str,
    base: str | None = None,
) -> dict:
    """Create an environment end to end — the one function both the
    command line and the screen call.

    The record goes through the port (which validates the slug); the
    base is born in a single write with the configuration the creation
    decided — the units and numeric parameters cloned from ``base``, or
    the project defaults when there is none — plus the creator as the
    only collaborator, as administrator. Everything else is zero:
    activities, requests, trail events, locations, companies, windows.
    """
    if base and not obter().obter(base):
        raise InvalidoError(f"Ambiente base “{base}” não encontrado.")

    criado = obter().criar(identificador, projeto, cliente, ator)

    parametros = {campo: repositorio.PARAMETROS_PADRAO[campo] for campo in PARAMETROS_CLONAVEIS}
    unidades: list[str] = []
    if base:
        with ambiente.ambiente_ativo(base):
            base_porta = repositorio.obter()
            herdados = base_porta.obter_parametros()
            parametros = {
                campo: herdados.get(campo, parametros[campo]) for campo in PARAMETROS_CLONAVEIS
            }
            unidades = base_porta.listar_cadastro("unidades")

    with ambiente.ambiente_ativo(identificador):
        repositorio.inicializar(
            {
                "atividades": {},
                "janelas": [],
                "colaboradores": [
                    {
                        "nome": ator,
                        "email": ator,
                        "perfil": "admin",
                        "vinculo": "timenow",
                        "empresa": "",
                        "ativo": True,
                    }
                ],
                "solicitacoes": [],
                "cadastros": {"locais": [], "empresas": [], "unidades": list(unidades)},
                "parametros": parametros,
                "sequencia": 1000,
                "itens_por_semana": {},
            }
        )
    return criado
