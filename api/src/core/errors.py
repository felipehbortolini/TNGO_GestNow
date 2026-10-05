"""Domain errors the route layer turns into HTTP responses (D14).

Only three shapes cross the facade line: the caller may not (403), the
data does not hold up (422) and the record changed since the screen
opened it (409). Facades raise them; ``routing.fragment_route`` renders
them into the fragment the screen expects.

The exception carries the message the person reads — that is the
architecture (D14), so the message is born at the raise site.
"""

from __future__ import annotations

from collections.abc import Mapping


class DomainError(Exception):
    """Base of every error a facade raises to the route layer."""


class AccessDeniedError(DomainError):
    """The caller's profile, role or bond does not allow the operation."""

    def __init__(self, message: str = "Seu perfil não permite esta operação."):
        super().__init__(message)


class InvalidDataError(DomainError):
    """The submitted data does not satisfy the rules of the domain.

    Carries one message per field when the problem is field-specific, or
    a single message when it is not. The route re-renders the form with
    the messages next to the fields.
    """

    def __init__(self, detail: Mapping[str, str] | str):
        self.detail = detail
        super().__init__(detail)

    def messages(self) -> list[str]:
        """The messages to show, without the empty ones."""
        if isinstance(self.detail, Mapping):
            return [message for message in self.detail.values() if message]
        return [str(self.detail)]

    def __str__(self) -> str:
        return " ".join(self.messages())


class VersionConflictError(DomainError):
    """Someone else saved the record since the screen opened it (D5)."""
