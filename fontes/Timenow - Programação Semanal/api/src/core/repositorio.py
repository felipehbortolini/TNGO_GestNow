"""The persistence port — one seam between the domain and where it lives.

Everything above this file talks to :class:`Repositorio` and to nothing
else. Today the only implementation is a JSON file on disk; tomorrow it
is a set of SharePoint lists. Swapping one for the other is an
environment variable, not a refactor::

    PROGRAMACAO_ORIGEM=json         (padrão — data/<ambiente>/programacao.json)
    PROGRAMACAO_ORIGEM=sharepoint   (integracoes/sharepoint.py)

The JSON implementation lives one folder per environment, and the
instance in force is resolved per active environment — never once per
process. See :func:`obter` and :func:`ambiente_ativo`.

The port is written in terms of the domain — activities, windows,
collaborators, registers — and not in terms of tables or documents. That
is what lets the SharePoint implementation map one aggregate to one list
without leaking list ids upward.

Why the methods are so few: every screen of the application is served by
this interface. A wide port would mean a wide SharePoint implementation,
and each extra method is one more thing to keep in sync between the two.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path

from src.core import ambiente

# Os cadastros que são digitados à mão. Fiscais e encarregados NÃO estão
# aqui: são pessoas, e pessoas moram em Colaboradores. ``dados.cadastros``
# devolve os cinco nomes mesmo assim — os dois últimos derivados de quem
# carrega o perfil — porque a planilha de importação valida contra eles.
CADASTROS = ("locais", "empresas", "unidades")

# Os parâmetros digitáveis da aplicação. O nome do projeto e do cliente
# NÃO moram aqui: a fonte única é o registro de ambientes (decisão 4), e
# um nome de cliente escrito como padrão denunciaria a premissa de
# instância única em qualquer ambiente novo.
PARAMETROS_PADRAO = {
    "meta_aderencia": 60.0,
    "meta_ppc": 75.0,
    "semana_referencia": "",
    "exige_justificativa_desvio": True,
    "limite_desvio_justificativa": 15.0,
}


def agora_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def diretorio_de_dados() -> Path:
    """Where the JSON lives. Overridable so the folder can be moved.

    Defaults to ``data/`` beside the repository root. The launcher sets
    ``PROGRAMACAO_DATA_DIR`` when the app runs from a packaged folder,
    where a path relative to ``__file__`` would land inside a temporary
    extraction directory.
    """
    escolhido = os.environ.get("PROGRAMACAO_DATA_DIR")
    if escolhido:
        return Path(escolhido)
    return Path(__file__).resolve().parents[3] / "data"


class Repositorio(ABC):
    """The persistence contract of the whole application."""

    # ── Atividades ─────────────────────────────────────────────────
    @abstractmethod
    def listar_atividades(self, semana: str | None = None) -> list[dict]: ...

    @abstractmethod
    def obter_atividade(self, chave: str) -> dict | None: ...

    @abstractmethod
    def gravar_atividade(self, atividade: dict) -> dict: ...

    @abstractmethod
    def remover_atividade(self, chave: str) -> bool: ...

    @abstractmethod
    def proximo_item(self, semana: str) -> int: ...

    @abstractmethod
    def nova_sequencia(self) -> str: ...

    # ── Cadastros de apoio ─────────────────────────────────────────
    @abstractmethod
    def listar_cadastro(self, nome: str) -> list[str]: ...

    @abstractmethod
    def gravar_cadastro(self, nome: str, valores: list[str]) -> list[str]: ...

    # ── Janelas de programação ─────────────────────────────────────
    @abstractmethod
    def listar_janelas(self) -> list[dict]: ...

    @abstractmethod
    def gravar_janela(self, janela: dict) -> dict: ...

    # ── Colaboradores ──────────────────────────────────────────────
    @abstractmethod
    def listar_colaboradores(self) -> list[dict]: ...

    @abstractmethod
    def gravar_colaborador(self, colaborador: dict) -> dict: ...

    @abstractmethod
    def remover_colaborador(self, email: str) -> bool: ...

    # ── Parâmetros do projeto ──────────────────────────────────────
    @abstractmethod
    def obter_parametros(self) -> dict: ...

    @abstractmethod
    def gravar_parametros(self, parametros: dict) -> dict: ...

    # ── Governança ─────────────────────────────────────────────────
    @abstractmethod
    def listar_solicitacoes(self) -> list[dict]: ...

    @abstractmethod
    def gravar_solicitacao(self, solicitacao: dict) -> dict: ...


class RepositorioJson(Repositorio):
    """One JSON file per environment, written atomically, guarded by a lock.

    Atomic because the network mode puts several people on the same file:
    a half-written ``programacao.json`` would take the whole application
    down, and a crash mid-write is exactly when that happens. The write
    goes to a temporary file in the same directory and is then renamed,
    which is atomic on NTFS and on POSIX alike.

    Without an explicit ``caminho`` the file is resolved from the active
    environment — ``data/<slug>/programacao.json``. Building one outside
    any ``ambiente_ativo`` block raises, so no construction path can
    silently land on the root of ``data/``.
    """

    def __init__(self, caminho: str | Path | None = None):
        if caminho is None:
            caminho = diretorio_de_dados() / ambiente.slug_ativo() / "programacao.json"
        self.caminho = Path(caminho)
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
        """What a missing base is born as, on its first read.

        Only the demonstration gets the deterministic history — and only
        the demonstration's own environments. An environment created in
        production is born with the empty shape: activity that never
        happened would be false data on a real client's planning screen.
        """
        from src.core import auth, carga_inicial

        if auth.modo_demo() and auth.eh_ambiente_demo(ambiente.slug_ativo()):
            dados = self._garantir_forma(carga_inicial.gerar())
            self._gravar(dados)
            return dados
        dados = self._garantir_forma({})
        self._gravar(dados)
        return dados

    def semear(self, dados: dict) -> None:
        """Write the base from scratch, in one atomic write.

        The creation of an environment is the caller: the new base is
        born with the configuration the creation decided — never with
        the demo history that a first READ of a missing file would
        produce.
        """
        with self._trava:
            self._gravar(self._garantir_forma(dados))

    @staticmethod
    def _garantir_forma(dados: dict) -> dict:
        dados.setdefault("atividades", {})
        dados.setdefault("janelas", [])
        dados.setdefault("colaboradores", [])
        dados.setdefault("solicitacoes", [])
        dados.setdefault("cadastros", {})
        for nome in CADASTROS:
            dados["cadastros"].setdefault(nome, [])
        dados.setdefault("parametros", dict(PARAMETROS_PADRAO))
        for chave, valor in PARAMETROS_PADRAO.items():
            dados["parametros"].setdefault(chave, valor)
        dados.setdefault("sequencia", 1000)
        dados.setdefault("itens_por_semana", {})
        return dados

    # -- atividades -------------------------------------------------
    def listar_atividades(self, semana: str | None = None) -> list[dict]:
        with self._trava:
            atividades = list(self._ler()["atividades"].values())
        if semana:
            return [a for a in atividades if a.get("semana") == semana]
        return atividades

    def obter_atividade(self, chave: str) -> dict | None:
        with self._trava:
            atividades = self._ler()["atividades"]
        if chave in atividades:
            return atividades[chave]
        for guardada, atividade in atividades.items():
            if guardada.endswith(f"::{chave}") or atividade.get("id_exclusiva") == chave:
                return atividade
        return None

    def gravar_atividade(self, atividade: dict) -> dict:
        with self._trava:
            dados = self._ler()
            chave = atividade.get("key") or self.montar_chave(
                atividade.get("semana", ""), atividade.get("id_exclusiva", "")
            )
            atividade["key"] = chave
            dados["atividades"][chave] = atividade
            semana = atividade.get("semana", "")
            if semana:
                dados["itens_por_semana"][semana] = max(
                    dados["itens_por_semana"].get(semana, 0),
                    int(atividade.get("item") or 0),
                )
            self._gravar(dados)
        return atividade

    def remover_atividade(self, chave: str) -> bool:
        with self._trava:
            dados = self._ler()
            alvo = chave if chave in dados["atividades"] else None
            if alvo is None:
                for guardada, atividade in dados["atividades"].items():
                    if guardada.endswith(f"::{chave}") or atividade.get("id_exclusiva") == chave:
                        alvo = guardada
                        break
            if alvo is None:
                return False
            del dados["atividades"][alvo]
            self._gravar(dados)
        return True

    def proximo_item(self, semana: str) -> int:
        with self._trava:
            return self._ler()["itens_por_semana"].get(semana, 0) + 1

    def nova_sequencia(self) -> str:
        with self._trava:
            dados = self._ler()
            dados["sequencia"] = int(dados.get("sequencia", 1000)) + 1
            self._gravar(dados)
            return f"EXT-{dados['sequencia']}"

    @staticmethod
    def montar_chave(semana: str, id_exclusiva: str) -> str:
        return f"{str(semana).replace('/', '-')}::{id_exclusiva}"

    # -- cadastros --------------------------------------------------
    def listar_cadastro(self, nome: str) -> list[str]:
        with self._trava:
            return list(self._ler()["cadastros"].get(nome, []))

    def gravar_cadastro(self, nome: str, valores: list[str]) -> list[str]:
        with self._trava:
            dados = self._ler()
            dados["cadastros"][nome] = list(valores)
            self._gravar(dados)
        return list(valores)

    # -- janelas ----------------------------------------------------
    def listar_janelas(self) -> list[dict]:
        with self._trava:
            return list(self._ler()["janelas"])

    def gravar_janela(self, janela: dict) -> dict:
        with self._trava:
            dados = self._ler()
            janelas = dados["janelas"]
            for i, atual in enumerate(janelas):
                if atual.get("empresa") == janela.get("empresa"):
                    janelas[i] = janela
                    break
            else:
                janelas.append(janela)
            self._gravar(dados)
        return janela

    # -- colaboradores ----------------------------------------------
    def listar_colaboradores(self) -> list[dict]:
        with self._trava:
            return [dict(c) for c in self._ler()["colaboradores"]]

    def gravar_colaborador(self, colaborador: dict) -> dict:
        with self._trava:
            dados = self._ler()
            pessoas = dados["colaboradores"]
            colaborador.setdefault("id", f"col-{uuid.uuid4().hex[:8]}")
            colaborador["atualizado_em"] = agora_iso()
            for i, atual in enumerate(pessoas):
                if atual.get("email") == colaborador.get("email"):
                    pessoas[i] = {**atual, **colaborador}
                    break
            else:
                colaborador.setdefault("criado_em", agora_iso())
                pessoas.append(colaborador)
            self._gravar(dados)
        return colaborador

    def remover_colaborador(self, email: str) -> bool:
        with self._trava:
            dados = self._ler()
            restantes = [c for c in dados["colaboradores"] if c.get("email") != email]
            if len(restantes) == len(dados["colaboradores"]):
                return False
            dados["colaboradores"] = restantes
            self._gravar(dados)
        return True

    # -- parâmetros --------------------------------------------------
    def obter_parametros(self) -> dict:
        with self._trava:
            return dict(self._ler()["parametros"])

    def gravar_parametros(self, parametros: dict) -> dict:
        with self._trava:
            dados = self._ler()
            dados["parametros"].update(parametros)
            self._gravar(dados)
            return dict(dados["parametros"])

    # -- governança --------------------------------------------------
    def listar_solicitacoes(self) -> list[dict]:
        with self._trava:
            return [dict(s) for s in self._ler()["solicitacoes"]]

    def gravar_solicitacao(self, solicitacao: dict) -> dict:
        with self._trava:
            dados = self._ler()
            solicitacao.setdefault("id", f"sol-{uuid.uuid4().hex[:10]}")
            solicitacao.setdefault("solicitado_em", agora_iso())
            pendentes = dados["solicitacoes"]
            for i, atual in enumerate(pendentes):
                if atual.get("id") == solicitacao["id"]:
                    pendentes[i] = {**atual, **solicitacao}
                    break
            else:
                pendentes.append(solicitacao)
            self._gravar(dados)
        return solicitacao


# ── Guarda de portas por ambiente ──────────────────────────────────────
#
# The guard exists for the LOCK, not for the object: two instances for
# the same environment are two different locks, and then the
# read → modify → write cycle of two threads stops being serialized —
# the rename stays atomic, but one of the writes silently disappears.
# That is why there is no expiry and no bound, and why an entry must
# never be evicted by "least recently used": discarding one would
# reintroduce exactly the defect the guard exists to prevent. The total
# cost of keeping every entry for the life of the process is one Path
# and one RLock per client.
_instancias: dict[str, Repositorio] = {}
_trava_instancias = threading.Lock()


def origem_ativa() -> str:
    return os.environ.get("PROGRAMACAO_ORIGEM", "json").lower()


def _construir() -> Repositorio:
    if origem_ativa() == "sharepoint":
        from src.integracoes.sharepoint import RepositorioSharePoint

        return RepositorioSharePoint()
    return RepositorioJson()


def obter() -> Repositorio:
    """The port of the active environment — resolved per environment.

    Raises ``SemAmbienteError`` outside any ``ambiente_ativo`` block:
    fail closed, never a default environment, never a guess. Inside one,
    always the same instance for the same environment — one instance
    means one lock, which is what keeps concurrent writes serialized.
    """
    slug = ambiente.slug_ativo()
    instancia = _instancias.get(slug)
    if instancia is None:
        with _trava_instancias:
            instancia = _instancias.get(slug)
            if instancia is None:
                instancia = _construir()
                _instancias[slug] = instancia
    return instancia


def definir(slug: str, repositorio: Repositorio | None) -> None:
    """Replace the port of ONE environment — the test seam.

    ``None`` removes the entry, handing the slug back to the regular
    resolution. Other environments are untouched.
    """
    if repositorio is None:
        _instancias.pop(slug, None)
        return
    _instancias[slug] = repositorio


def inicializar(dados: dict) -> None:
    """Write the active environment's base from scratch.

    Environment creation is the one caller: a created environment is
    born with configuration and its creator — never with the demo
    history that a first read of a missing file would seed. Only the
    JSON implementation has this path today.
    """
    instancia = obter()
    if not isinstance(instancia, RepositorioJson):
        raise NotImplementedError("A base só é inicializada na origem JSON.")
    instancia.semear(dados)
