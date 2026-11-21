"""Emails sent by the user accounts module (Spanish: the users speak Spanish)."""

from modules.shared_kernel.domain.notifications import EmailMessage
from modules.shared_kernel.domain.security import RoleType

ROLE_NAMES = {
    RoleType.SUPERADMIN: "Superadministrador",
    RoleType.ADMIN: "Administrador",
    RoleType.OPERATOR: "Operador",
}


def new_account_email(
    *, to: str, full_name: str, role: RoleType, password: str, login_url: str
) -> EmailMessage:
    body = f"""Hola, {full_name}:

Se creó tu cuenta en el Sistema de Gestión de Industrias Escolares (IMSI).

  Correo de acceso: {to}
  Contraseña inicial: {password}
  Rol: {ROLE_NAMES[role]}

Para ingresar:
  1. Abre {login_url}
  2. Escribe tu correo y la contraseña inicial.
  3. En tu primer ingreso vincularás una aplicación autenticadora (Google Authenticator,
     Microsoft Authenticator u otra) escaneando un código QR. Desde entonces, cada ingreso pedirá
     el código de 6 dígitos que muestre esa aplicación.

Por seguridad, no compartas este correo. Si no esperabas este mensaje, comunícate con el
administrador del sistema.
"""
    return EmailMessage(to=(to,), subject="IMSI · Tu cuenta de acceso", body=body)


def password_changed_email(
    *, to: str, full_name: str, password: str, login_url: str
) -> EmailMessage:
    body = f"""Hola, {full_name}:

Un administrador actualizó la contraseña de tu cuenta en el Sistema de Gestión de Industrias
Escolares (IMSI).

  Correo de acceso: {to}
  Nueva contraseña: {password}

Ingresa en {login_url}. Tu aplicación autenticadora sigue funcionando como siempre.

Si no solicitaste este cambio, comunícate de inmediato con el administrador del sistema.
"""
    return EmailMessage(to=(to,), subject="IMSI · Tu contraseña fue actualizada", body=body)
