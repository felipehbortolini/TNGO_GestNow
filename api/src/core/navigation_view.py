"""What the shell prints from the navigation list: sidebar, tabs, Voltar and scope selector.

``build`` crosses the list (``core.navigation``), the scope of the request and
the projects of the portfolio, and returns plain values for the Jinja fragment
to print. All the decisions live here, where a test can reach them without
HTTP: which module is highlighted (the origin one, on a detail screen), what
the tab bar shows (tabs, the sub-tabs of a group, or Voltar on a detail), which
address each link carries (always with the scope, so a copied link opens in
the same scope) and where the scope selector goes when the scope changes (a
detail screen goes back to its list, D8).

Given the ``User`` of the request, the list is also cut to what that person may
open (D7), by the same rules the routes enforce (``core.rbac``): Configurações
only for Gestor and Admin and, for a supplier, one single item — the
Programação Semanal, whose screens become its tabs. A screen that exists but
that the person may not open is not hidden behind a "not found": the shell is
sent to the screen of denied access (HU-019). The sidebar is only a courtesy:
the authority is the server, on every route.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Protocol

from src.core import navigation, rbac
from src.core.auth import DemoSelector
from src.core.navigation import NavModule, Screen
from src.core.rbac import Bond, User
from src.core.scope import PORTFOLIO_PARAMETER, Scope

APP_NAME = "Timenow GestNow"

PORTFOLIO_ICON = "layers"
PROJECT_ICON = "building"

# The single item a supplier sees (D7): the Programação Semanal as a module of
# its own, so its five screens are the tabs and not a group inside "02".
SUPPLIER_MODULE_ID = "programacao_semanal"
SUPPLIER_MODULE_TITLE = "Programação Semanal"
SUPPLIER_MODULE_ICON = "calendar"

# The route that draws the screen of denied access (HU-003, HU-019); the shell
# opens it in the place of a screen the person may not open.
DENIAL_ROUTE = "/api/acesso-negado"
DENIED_PAGE_TITLE = f"Acesso negado · {APP_NAME}"


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
class UserBadge:
    """The user card at the foot of the sidebar: who is signed in, and as what."""

    name: str
    initials: str
    description: str
    email: str


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
    user: UserBadge | None = None
    demo: DemoSelector | None = None

    @property
    def has_bar(self) -> bool:
        """The module bar shows something: more than one tab, or Voltar."""
        return bool(self.tabs) or self.back is not None


@dataclass(frozen=True)
class _Position:
    """Where the person is in what the person may see.

    ``screen`` is the open screen as the person sees it and ``module`` the
    module that holds it. ``denied`` is a screen that exists in the list but
    that the person may not open: then there is no open screen.
    """

    screen: Screen | None
    module: NavModule | None
    denied: Screen | None


def build(
    path: str | None,
    scope: Scope,
    projects: Sequence[ProjectLike],
    user: User | None = None,
    demo: DemoSelector | None = None,
) -> NavigationView:
    """The navigation of the screen at ``path``, in the given scope, for the user.

    An unknown (or missing) path builds the navigation with nothing open: the
    sidebar is complete, the bar is empty and ``current_view`` is ``None`` so
    the shell knows it must choose another screen. A screen the user may not
    open also leaves nothing open, but ``current_view`` is then the route of
    the screen of denied access. Without a ``user`` nothing is cut (the list as
    it is); ``demo`` is the profile selector of the demonstration, when it exists.
    """
    modules = _visible_modules(user)
    where = _position(path, modules, user)
    active_module = where.module
    parameter = scope.parameter
    tabs, subtabs, subtabs_label = _tabs(active_module, where.screen, parameter)
    options = _scope_options(scope, projects)
    selected = next((option for option in options if option.selected), options[0])
    return NavigationView(
        modules=tuple(_module_link(module, active_module, parameter) for module in modules),
        tabs=tabs,
        subtabs=subtabs,
        subtabs_label=subtabs_label,
        tabs_label=f"Telas de {active_module.title}" if tabs and active_module else None,
        back=_back_link(where.screen, parameter),
        scope_options=options,
        scope_parameter=parameter,
        scope_label=selected.label,
        scope_icon=PORTFOLIO_ICON if scope.is_portfolio else PROJECT_ICON,
        scope_destination=_scope_destination(where.screen),
        home_url=_home_url(parameter),
        current_path=_current_path(where),
        current_view=_current_view(where),
        page_title=_page_title(where),
        user=_badge(user),
        demo=demo,
    )


# ── What the user may see ────────────────────────────────────────────────


def _visible_modules(user: User | None) -> tuple[NavModule, ...]:
    """The modules of the list narrowed to what the user may open (D7).

    Every screen goes through ``rbac.can_open_screen``, the same rule the
    routes enforce; a module left with no listed screen disappears. A supplier
    gets the one module made for it.
    """
    if user is None:
        return navigation.modules()
    if user.bond is Bond.SUPPLIER:
        return _supplier_modules(user)
    narrowed = (_narrow(module, user) for module in navigation.modules())
    return tuple(module for module in narrowed if module is not None)


def _narrow(module: NavModule, user: User) -> NavModule | None:
    screens = tuple(screen for screen in module.screens if rbac.can_open_screen(user, screen))
    if not any(not screen.is_detail for screen in screens):
        return None
    return module if len(screens) == len(module.screens) else replace(module, screens=screens)


def _supplier_modules(user: User) -> tuple[NavModule, ...]:
    """The Programação Semanal as the supplier's only module, with its screens as the tabs."""
    screens = tuple(
        replace(screen, group=None, nav_module=SUPPLIER_MODULE_ID)
        for screen in navigation.screens()
        if rbac.can_open_screen(user, screen)
    )
    if not screens:
        return ()
    return (
        NavModule(
            id=SUPPLIER_MODULE_ID,
            title=SUPPLIER_MODULE_TITLE,
            icon=SUPPLIER_MODULE_ICON,
            screens=screens,
        ),
    )


def _position(path: str | None, modules: Sequence[NavModule], user: User | None) -> _Position:
    """Find the screen at ``path`` among the modules the user sees.

    A real screen that is not among them is ``denied``. Início is the entrance
    of the product, so for a person who cannot open it (a supplier) the
    entrance is the first screen the person can: nobody lands on a denial.
    """
    requested = navigation.screen_for_path(path)
    if requested is None:
        return _Position(screen=None, module=None, denied=None)
    found = _locate(modules, requested)
    if found is None and user is not None and requested.key == navigation.HOME_KEY and modules:
        found = _locate(modules, modules[0].landing)
    if found is None:
        return _Position(screen=None, module=None, denied=requested)
    module, screen = found
    return _Position(screen=screen, module=module, denied=None)


def _locate(modules: Sequence[NavModule], target: Screen) -> tuple[NavModule, Screen] | None:
    for module in modules:
        for screen in module.screens:
            if screen.key == target.key:
                return module, screen
    return None


def _current_path(where: _Position) -> str | None:
    shown = where.screen or where.denied
    return navigation.public_path(shown) if shown is not None else None


def _current_view(where: _Position) -> str | None:
    screen, denied = where.screen, where.denied
    if screen is not None:
        return navigation.view_path(screen)
    if denied is not None:
        return f"{DENIAL_ROUTE}?caminho={navigation.public_path(denied)}"
    return None


def _badge(user: User | None) -> UserBadge | None:
    if user is None:
        return None
    return UserBadge(
        name=user.name,
        initials=_initials(user.name),
        description=f"{user.general_profile} · {user.bond}",
        email=user.email,
    )


def _initials(name: str) -> str:
    """The first letter of the first and of the last name, capitalized."""
    words = name.split()
    if not words:
        return "?"
    last = words[-1][0] if len(words) > 1 else ""
    return (words[0][0] + last).upper()


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


def _page_title(where: _Position) -> str:
    """``Ata · Central de Ações · Timenow GestNow``; Início is just ``Início · Timenow GestNow``."""
    if where.denied is not None:
        return DENIED_PAGE_TITLE
    current, module = where.screen, where.module
    if current is None or module is None:
        return APP_NAME
    if current.title == module.title:
        return f"{current.title} · {APP_NAME}"
    return f"{current.title} · {module.title} · {APP_NAME}"
