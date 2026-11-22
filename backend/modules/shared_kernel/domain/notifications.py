"""Messages sent to people outside the application (emails)."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Attachment:
    filename: str
    content: bytes
    mimetype: str = "application/pdf"


@dataclass(frozen=True, slots=True)
class EmailMessage:
    to: tuple[str, ...]
    subject: str
    body: str  # plain text, in Spanish
    attachments: tuple[Attachment, ...] = field(default_factory=tuple)
