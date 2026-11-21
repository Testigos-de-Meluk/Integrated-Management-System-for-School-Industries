"""Domain events (Observer pattern, NFR-05-01).

A module announces that something happened (e.g. "a user was deactivated") without knowing who
reacts. Other modules subscribe to the event type through the infrastructure event bus.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class DomainEvent:
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
