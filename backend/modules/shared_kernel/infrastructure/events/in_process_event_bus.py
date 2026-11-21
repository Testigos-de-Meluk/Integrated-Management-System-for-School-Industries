"""In-process event bus: the Observer pattern of NFR-05-01.

Handlers run synchronously, inside the same database transaction as the use case that published
the event, so a failing handler rolls everything back. Modules subscribe in their
``AppConfig.ready()``.
"""

import logging
from collections import defaultdict
from collections.abc import Callable

from modules.shared_kernel.domain.events import DomainEvent
from modules.shared_kernel.ports.outbound.event_publisher import EventPublisher

logger = logging.getLogger("imsi.events")

Handler = Callable[[DomainEvent], None]


class InProcessEventBus(EventPublisher):
    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: type[DomainEvent], handler: Handler) -> None:
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)

    def publish(self, event: DomainEvent) -> None:
        handlers = self._handlers.get(type(event), [])
        logger.debug("%s -> %d handler(s)", type(event).__name__, len(handlers))
        for handler in handlers:
            handler(event)


#: Single bus for the whole process (Singleton).
event_bus = InProcessEventBus()
