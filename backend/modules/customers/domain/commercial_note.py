"""Internal commercial note on a customer's profile (US 2.21 … US 2.24).

Notes are private: they never appear in documents or emails sent to customers (US 2.21.5). The
author's name is kept as written at that moment, so the history stays readable even if the account
later changes.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from modules.shared_kernel.domain.exceptions import ValidationError

from .exceptions import NoteEditNotAllowed

CONTENT_MAX_LENGTH = 2000


def _clean_content(text: str) -> str:
    content = (text or "").strip()
    if not content:
        raise ValidationError.for_field("content", "La nota no puede estar vacía.")
    if len(content) > CONTENT_MAX_LENGTH:
        raise ValidationError.for_field("content", f"Máximo {CONTENT_MAX_LENGTH} caracteres.")
    return content


@dataclass(eq=False, slots=True)
class CommercialNote:
    customer_id: UUID
    content: str
    author_id: UUID
    author_name: str
    created_at: datetime
    updated_at: datetime | None = None
    updated_by_id: UUID | None = None
    updated_by_name: str = ""
    id: UUID = field(default_factory=uuid4)

    @classmethod
    def write(
        cls, customer_id: UUID, text: str, author_id: UUID, author_name: str, now: datetime
    ) -> "CommercialNote":
        return cls(
            customer_id=customer_id,
            content=_clean_content(text),
            author_id=author_id,
            author_name=author_name,
            created_at=now,
        )

    @property
    def is_edited(self) -> bool:
        return self.updated_at is not None

    def can_be_edited_by(self, user_id: UUID | None) -> bool:
        return user_id is not None and user_id == self.author_id

    def edit(self, text: str, editor_id: UUID | None, editor_name: str, now: datetime) -> None:
        """Keeps the original date and author; records who edited and when (US 2.23.3)."""
        if not self.can_be_edited_by(editor_id):
            raise NoteEditNotAllowed()
        self.content = _clean_content(text)
        self.updated_at = now
        self.updated_by_id = editor_id
        self.updated_by_name = editor_name
