from abc import ABC, abstractmethod

from modules.shared_kernel.domain.events import DomainEvent


class EventPublisher(ABC):
    """Outbound port: announces a domain event to every subscriber (Observer pattern)."""

    @abstractmethod
    def publish(self, event: DomainEvent) -> None: ...
