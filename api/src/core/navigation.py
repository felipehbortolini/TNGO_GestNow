"""The single navigation list (D2): modules, screens and everything derived from them.

The list lives in ``navegacao.json``, in two levels: the navigation modules
(Início, 01 to 08 and Configurações) and, inside each, its screens — detail
screens included. Everything that needs a screen reads it here: ``/api/nav``
(sidebar, module tabs, Voltar), the scope selector, the trio of each screen
(ISSUE-010) and the screen sweep. A screen is added in one place only: a line
of the JSON file.

A screen is identified by its key, ``<module>/<id>``. The module is the folder
of the screen (``app/_views/<module>/<id>.html``, ``app/paginas/<module>/<id>``)
and is not always the navigation module: the Programação Semanal screens live
in their own folder but appear among the tabs of Planejamento (D10). The id
and the module are snake_case; the public address of a screen swaps ``_`` for
``-`` (``/central-acoes/atas``) and the address of Início is ``/``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

NAVIGATION_FILE = Path(__file__).with_name("navegacao.json")

HOME_KEY = "inicio/home"
HOME_PATH = "/"

# Addresses that also open Início: the shell file itself and the module name.
HOME_ALIASES = frozenset({"/", "/index.html", "/inicio"})


class InvalidNavigationError(RuntimeError):
    """The navigation file breaks one of its own rules; it fails loud, at first use."""

    def __init__(self, problem: str) -> None:
        super().__init__(f"navegacao.json invalido: {problem}")


@dataclass(frozen=True)
class Screen:
    """One screen of the product: where its files live and where it sits in the tabs."""

    module: str
    id: str
    title: str
    nav_module: str
    short_title: str | None = None
    group: str | None = None
    detail_of: str | None = None

    @property
    def key(self) -> str:
        """``<module>/<id>``: the identity of the screen across every layer."""
        return f"{self.module}/{self.id}"

    @property
    def is_detail(self) -> bool:
        """Detail screens (ata, contrato, ficha do risco, SM) have Voltar instead of tabs."""
        return self.detail_of is not None

    @property
    def tab_label(self) -> str:
        """The name of the screen's tab: the short title when the full one is long."""
        return self.short_title or self.title


@dataclass(frozen=True)
class NavModule:
    """A first-level item of the navigation and the screens it owns."""

    id: str
    title: str
    icon: str
    screens: tuple[Screen, ...]
    number: str | None = None

    @property
    def label(self) -> str:
        """The name as the sidebar shows it: ``02 Planejamento``."""
        return f"{self.number} {self.title}" if self.number else self.title

    @property
    def listed_screens(self) -> tuple[Screen, ...]:
        """The screens that have a tab: every one but the details."""
        return tuple(screen for screen in self.screens if not screen.is_detail)

    @property
    def landing(self) -> Screen:
        """The screen the module's sidebar item opens: its first listed screen."""
        return self.listed_screens[0]


# ── The list ─────────────────────────────────────────────────────────────


@cache
def modules() -> tuple[NavModule, ...]:
    """The navigation modules in display order, read and validated once."""
    raw = json.loads(NAVIGATION_FILE.read_text(encoding="utf-8"))
    try:
        built = tuple(_build_module(item) for item in raw["modulos"])
    except KeyError as missing:
        problem = f"campo obrigatorio ausente: {missing}"
        raise InvalidNavigationError(problem) from missing
    _validate(built)
    return built


def screens() -> tuple[Screen, ...]:
    """Every screen of every module, in display order."""
    return tuple(screen for module in modules() for screen in module.screens)


@cache
def _screens_by_key() -> Mapping[str, Screen]:
    return {screen.key: screen for screen in screens()}


def find_screen(key: str) -> Screen | None:
    """The screen with the key ``<module>/<id>``, or ``None``."""
    return _screens_by_key().get(key)


def module_of(screen: Screen) -> NavModule:
    """The navigation module a screen belongs to."""
    return next(module for module in modules() if module.id == screen.nav_module)


def origin_of(screen: Screen) -> Screen:
    """The list screen a detail comes from; any other screen is its own origin."""
    if screen.detail_of is None:
        return screen
    origin = find_screen(screen.detail_of)
    return origin if origin is not None else screen


# ── Addresses ────────────────────────────────────────────────────────────


def slug(identifier: str) -> str:
    """The public spelling of an identifier: snake_case becomes kebab-case."""
    return identifier.replace("_", "-")


def public_path(screen: Screen) -> str:
    """The address the person sees in the browser: ``/central-acoes/atas``; Início is ``/``."""
    if screen.key == HOME_KEY:
        return HOME_PATH
    return f"/{slug(screen.module)}/{slug(screen.id)}"


def view_path(screen: Screen) -> str:
    """Where the static fragment of the screen is served from."""
    return f"/_views/{screen.module}/{screen.id}.html"


def screen_for_path(path: str | None) -> Screen | None:
    """The screen a public address opens, or ``None`` when the address is unknown.

    Case, a trailing slash and a query string are tolerated; the shell file
    and ``/inicio`` open Início. Anything that is not ``/<module>/<screen>``
    of a listed screen is unknown — the caller decides what to show.
    """
    if path is None or not path.strip():
        return None
    cleaned = path.split("?", 1)[0].split("#", 1)[0].strip().lower()
    cleaned = cleaned.rstrip("/") if cleaned != "/" else cleaned
    if cleaned in HOME_ALIASES:
        return find_screen(HOME_KEY)
    parts = cleaned.strip("/").split("/")
    if len(parts) != 2:
        return None
    module, screen_id = (part.replace("-", "_") for part in parts)
    return find_screen(f"{module}/{screen_id}")


def scoped_url(screen: Screen, scope_parameter: str) -> str:
    """The address of a screen carrying the scope, as every navigation link is written."""
    return f"{public_path(screen)}?projeto={scope_parameter}"


# ── Reading and validation ───────────────────────────────────────────────


def _build_module(item: Mapping[str, Any]) -> NavModule:
    module_id = item["id"]
    return NavModule(
        id=module_id,
        title=item["titulo"],
        icon=item["icone"],
        screens=tuple(_build_screen(entry, module_id) for entry in item["telas"]),
        number=item.get("numero"),
    )


def _build_screen(entry: Mapping[str, Any], nav_module: str) -> Screen:
    return Screen(
        module=entry.get("modulo", nav_module),
        id=entry["id"],
        title=entry["titulo"],
        nav_module=nav_module,
        short_title=entry.get("curto"),
        group=entry.get("grupo"),
        detail_of=entry.get("detalhe_de"),
    )


def _validate(built: tuple[NavModule, ...]) -> None:
    """Fail loud on a list the rest of the platform could not render consistently."""
    _require_unique([module.id for module in built], "modulo")
    _require_unique([module.number for module in built if module.number], "numero")
    every_screen = [screen for module in built for screen in module.screens]
    _require_unique([screen.key for screen in every_screen], "tela")
    by_key = {screen.key: screen for screen in every_screen}
    for module in built:
        _validate_module(module, by_key)


def _validate_module(module: NavModule, by_key: Mapping[str, Screen]) -> None:
    if not module.screens or module.screens[0].is_detail:
        problem = f"{module.id}: a primeira tela precisa ser de lista"
        raise InvalidNavigationError(problem)
    for screen in module.screens:
        if screen.detail_of is not None:
            _validate_detail(screen, by_key)
    _validate_groups(module)


def _validate_detail(screen: Screen, by_key: Mapping[str, Screen]) -> None:
    origin = by_key.get(screen.detail_of or "")
    if origin is None or origin.is_detail or origin.nav_module != screen.nav_module:
        problem = f"{screen.key}: detalhe_de precisa apontar uma tela de lista do mesmo modulo"
        raise InvalidNavigationError(problem)
    if screen.group is not None:
        problem = f"{screen.key}: tela de detalhe nao entra em grupo"
        raise InvalidNavigationError(problem)


def _validate_groups(module: NavModule) -> None:
    """The screens of a group sit side by side, so the group is one tab."""
    closed: set[str] = set()
    previous: str | None = None
    for screen in module.screens:
        if previous is not None and screen.group != previous:
            closed.add(previous)
        if screen.group is not None and screen.group in closed:
            problem = f"{module.id}: o grupo {screen.group} nao e contiguo"
            raise InvalidNavigationError(problem)
        previous = screen.group


def _require_unique(values: list[str], what: str) -> None:
    repeated = sorted({value for value in values if values.count(value) > 1})
    if repeated:
        problem = f"{what} repetido: {', '.join(repeated)}"
        raise InvalidNavigationError(problem)
