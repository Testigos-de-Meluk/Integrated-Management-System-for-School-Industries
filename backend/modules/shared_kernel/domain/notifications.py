"""Messages sent to people outside the application (emails)."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EmailMessage:
    to: tuple[str, ...]
    subject: str
    body: str  # plain text, in Spanish
