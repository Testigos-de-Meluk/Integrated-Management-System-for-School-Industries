import bcrypt

from modules.shared_kernel.ports.outbound.password_hasher import PasswordHasher


class BcryptPasswordHasher(PasswordHasher):
    """bcrypt with a unique random salt per password (NFR-01-02).

    ``rounds`` is 12 in every real environment; the test settings lower it to keep tests fast.
    """

    def __init__(self, rounds: int = 12) -> None:
        self._rounds = rounds

    def hash(self, raw_password: str) -> str:
        salt = bcrypt.gensalt(rounds=self._rounds)
        return bcrypt.hashpw(raw_password.encode("utf-8"), salt).decode("ascii")

    def matches(self, raw_password: str, password_hash: str) -> bool:
        try:
            return bcrypt.checkpw(raw_password.encode("utf-8"), password_hash.encode("ascii"))
        except ValueError:
            return False
