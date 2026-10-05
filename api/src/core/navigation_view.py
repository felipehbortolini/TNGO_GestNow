"""What the shell prints from the navigation list: sidebar, tabs, Voltar and scope selector.

``build`` crosses the list (``core.navigation``), the scope of the request and
the projects of the portfolio, and returns plain values for the Jinja fragment
to print. All the decisions live here, where a test can reach them without
HTTP: which module is highlighted (the origin one, on a detail screen), what
the tab bar shows (tabs, the sub-tabs of a group, or Voltar on a detail), which
address each link carries (always with the scope, so a copied link opens in
the same scope) and where the scope selector goes when the scope changes (a
detail screen goes back to its list, D8).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from src.core import navigation
from src.core.navigation import NavModule, Screen
from src.core.scope import PORTFOLIO_PARAMETER, Scope

APP_NAME = "Timenow GestNow"

PORTFOLIO_ICON = "layers"
PROJECT_ICON = "building"


class ProjectLike(Protocol):
    """What the scope selector reads of a project: identity and label."""

    @property
    def id(self) -> int: ...

    @property
    def code(self) -> str: ...

    @property
    def name(self) -> str: ...


@dataclass(frozen=True)
class ModuleLink:
    """A first-level item of the sidebar."""

    label: str
    number: str | None
    title: str
    icon: str
    url: str
    active: bool


@dataclass(frozen=True)
class TabLink:
    """A tab of the module bar. ``current`` is the ``aria-current`` value when it is the open one."""

    label: str
    title: str
    url: str
    current: str | None = None

    @property
    def is_active(self) -> bool:
        """Whether the tab is highlighted."""
        return self.current is not None

    @property
    def is_abbreviated(self) -> bool:
        """The label is a short name: the full title goes in the hint and the accessible name."""
        return self.label != self.title


@dataclass(frozen=True)
class BackLink:
    """Voltar of a detail screen: back to the list it came from."""

    title: str
    url: str


@dataclass(frozen=True)
class ScopeOption:
    """An option of the scope selector: the Portfólio or one project."""

    value: str
    label: str
    selected: bool


@dataclass(frozen=True)
class NavigationView:
    """Everything the navigation fragment prints, already decided."""

    modules: tuple[ModuleLink, ...]
    tabs: tuple[TabLink, ...]
    subtabs: tuple[TabLink, ...]
    subtabs_label: str | None
    tabs_label: str | None
    back: BackLink | None
    scope_options: tuple[ScopeOption, ...]
    scope_parameter: str
    scope_label: str
    scope_icon: str
    scope_destination: str
    home_url: str
    current_path: str | None
    current_view: str | None
    page_title: str

    @property
    def has_bar(self) -> bool:
        """The module bar shows something: more than one tab, or Voltar."""
        return bool(self.tabs) or self.back is not None


def build(path: str | None, scope: Scope, projects: Sequence[ProjectLike]) -> NavigationView:
    """The navigation of the screen at ``path``, in the given scope.

    An unknown (or missing) path builds the navigation with nothing open: the
    sidebar is complete, the bar is empty and ``current_view`` is ``None`` so
    the shell knows it must choose another screen.
    """
    current = navigation.screen_for_path(path)
    active_module = navigation.module_of(current) if current is not None else None
    parameter = scope.parameter
    tabs, subtabs, subtabs_label = _tabs(active_module, current, parameter)
    options = _scope_options(scope, projects)
    selected = next((option for option in options if option.selected), options[0])
    return NavigationView(
        modules=tuple(
            _module_link(module, active_module, parameter) for module in navigation.modules()
        ),
        tabs=tabs,
        subtabs=subtabs,
        subtabs_label=subtabs_label,
        tabs_label=f"Telas de {active_module.title}" if tabs and active_module else None,
        back=_back_link(current, parameter),
        scope_options=options,
        scope_parameter=parameter,
        scope_label=selected.label,
        scope_icon=PORTFOLIO_ICON if scope.is_portfolio else PROJECT_ICON,
        scope_destination=_scope_destination(current),
        home_url=_home_url(parameter),
        current_path=navigation.public_path(current) if current is not None else None,
        current_view=navigation.view_path(current) if current is not None else None,
        page_title=_page_title(current, active_module),
    )


def _home_url(parameter: str) -> str:
    home = navigation.find_screen(navigation.HOME_KEY)
    return navigation.scoped_url(home, parameter) if home is not None else navigation.HOME_PATH


def _module_link(module: NavModule, active: NavModule | None, parameter: str) -> ModuleLink:
    return ModuleLink(
        label=module.label,
        number=module.number,
        title=module.title,
        icon=module.icon,
        url=navigation.scoped_url(module.landing, parameter),
        active=active is not None and module.id == active.id,
    )


def _tabs(
    module: NavModule | None, current: Screen | None, parameter: str
) -> tuple[tuple[TabLink, ...], tuple[TabLink, ...], str | None]:
    """Tabs of the open module, the sub-tabs of the open group and the group's name.

    A detail screen has no tabs (it has Voltar), and a module with a single
    listed screen has nothing to switch between.
    """
    if module is None or current is None or current.is_detail:
        return (), (), None
    listed = module.listed_screens
    if len(listed) < 2:
        return (), (), None
    tabs: list[TabLink] = []
    seen_groups: set[str] = set()
    for screen in listed:
        if screen.group is None:
            tabs.append(_tab(screen, parameter, current))
        elif screen.group not in seen_groups:
            seen_groups.add(screen.group)
            tabs.append(_group_tab(screen, parameter, current))
    return tuple(tabs), _subtabs(listed, current, parameter), current.group


def _tab(screen: Screen, parameter: str, current: Screen) -> TabLink:
    return TabLink(
        label=screen.tab_label,
        title=screen.title,
        url=navigation.scoped_url(screen, parameter),
        current="page" if screen.key == current.key else None,
    )


def _group_tab(first: Screen, parameter: str, current: Screen) -> TabLink:
    """One tab for a whole group: it opens the group's first screen and is lit inside it."""
    group = first.group or ""
    return TabLink(
        label=group,
        title=group,
        url=navigation.scoped_url(first, parameter),
        current="true" if current.group == group else None,
    )


def _subtabs(listed: Sequence[Screen], current: Screen, parameter: str) -> tuple[TabLink, ...]:
    if current.group is None:
        return ()
    return tuple(
        _tab(screen, parameter, current) for screen in listed if screen.group == current.group
    )


def _back_link(current: Screen | None, parameter: str) -> BackLink | None:
    if current is None or not current.is_detail:
        return None
    origin = navigation.origin_of(current)
    return BackLink(title=origin.title, url=navigation.scoped_url(origin, parameter))


def _scope_options(scope: Scope, projects: Sequence[ProjectLike]) -> tuple[ScopeOption, ...]:
    portfolio = ScopeOption(
        value=PORTFOLIO_PARAMETER,
        label=_portfolio_label(len(projects)),
        selected=scope.is_portfolio,
    )
    chosen = tuple(
        ScopeOption(
            value=str(project.id),
            label=f"{project.code} · {project.name}",
            selected=scope.project_id == project.id,
        )
        for project in projects
    )
    return (portfolio, *chosen)


def _portfolio_label(count: int) -> str:
    noun = "projeto" if count == 1 else "projetos"
    return f"Portfólio ({count} {noun})"


def _scope_destination(current: Screen | None) -> str:
    """Where the selector goes on a change: the same screen, or the list a detail came from."""
    if current is None:
        return navigation.HOME_PATH
    return navigation.public_path(navigation.origin_of(current))


def _page_title(current: Screen | None, module: NavModule | None) -> str:
    """``Ata · Central de Ações · Timenow GestNow``; Início is just ``Início · Timenow GestNow``."""
    if current is None or module is None:
        return APP_NAME
    if current.title == module.title:
        return f"{current.title} · {APP_NAME}"
    return f"{current.title} · {module.title} · {APP_NAME}"
