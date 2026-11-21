"""Password rules (FR-01-11): minimum 8 characters with an uppercase letter, a lowercase letter,
a number and a special character. Also generates random passwords that satisfy them."""

import secrets
import string

from modules.shared_kernel.domain.exceptions import ValidationError

MIN_LENGTH = 8
MAX_LENGTH = 64  # bcrypt only uses the first 72 bytes; 64 characters keeps a safe margin
GENERATED_LENGTH = 12
SPECIAL_CHARACTERS = "!@#$%&*?-_+=."

POLICY_MESSAGE = (
    "La contraseña debe tener mínimo 8 caracteres, con al menos una mayúscula, una minúscula, "
    "un número y un carácter especial."
)


class PasswordPolicy:
    def is_satisfied_by(self, raw: str) -> bool:
        return (
            MIN_LENGTH <= len(raw) <= MAX_LENGTH
            and len(raw.encode("utf-8")) <= 72
            and any(c.isupper() for c in raw)
            and any(c.islower() for c in raw)
            and any(c.isdigit() for c in raw)
            and any(not c.isalnum() and not c.isspace() for c in raw)
        )

    def validate(self, raw: str, field_name: str = "password") -> None:
        if len(raw) > MAX_LENGTH or len(raw.encode("utf-8")) > 72:
            raise ValidationError.for_field(
                field_name, f"La contraseña no puede superar {MAX_LENGTH} caracteres."
            )
        if not self.is_satisfied_by(raw):
            raise ValidationError.for_field(field_name, POLICY_MESSAGE)

    def generate(self) -> str:
        """Cryptographically random password that always satisfies the policy."""
        alphabet = string.ascii_letters + string.digits + SPECIAL_CHARACTERS
        required = [
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.digits),
            secrets.choice(SPECIAL_CHARACTERS),
        ]
        rest = [secrets.choice(alphabet) for _ in range(GENERATED_LENGTH - len(required))]
        characters = required + rest
        secrets.SystemRandom().shuffle(characters)
        return "".join(characters)
