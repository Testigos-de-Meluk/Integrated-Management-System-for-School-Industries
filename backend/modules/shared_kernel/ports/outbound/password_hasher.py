from abc import ABC, abstractmethod


class PasswordHasher(ABC):
    """Outbound port: one-way password hashing (NFR-01-02). Hashes never leave the backend."""

    @abstractmethod
    def hash(self, raw_password: str) -> str: ...

    @abstractmethod
    def matches(self, raw_password: str, password_hash: str) -> bool: ...
