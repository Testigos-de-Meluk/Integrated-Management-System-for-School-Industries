"""``TwoFactorProvider`` with pyotp (TOTP, 6 digits, 30 s) and an SVG QR code."""

import base64
import hmac
import io
from datetime import datetime, timedelta

import pyotp
import qrcode
from qrcode.image.svg import SvgPathImage

from modules.authentication.ports.outbound.security import TwoFactorProvider

ISSUER_NAME = "IMSI Industrias Escolares"
PERIOD = timedelta(seconds=30)


class PyotpTwoFactorProvider(TwoFactorProvider):
    def new_secret(self) -> str:
        return pyotp.random_base32()  # 160 bits

    def qr_code(self, secret: str, account_name: str) -> str:
        uri = pyotp.TOTP(secret).provisioning_uri(name=account_name, issuer_name=ISSUER_NAME)
        image = qrcode.make(uri, image_factory=SvgPathImage, box_size=10, border=2)
        buffer = io.BytesIO()
        image.save(buffer)
        return "data:image/svg+xml;base64," + base64.b64encode(buffer.getvalue()).decode()

    def matching_step(self, secret: str, code: str, now: datetime) -> int | None:
        if not (code.isdigit() and len(code) == 6):
            return None
        totp = pyotp.TOTP(secret)
        # Current step first, then ±1 step to tolerate up to 30 s of clock drift on the phone.
        for offset in (0, -1, 1):
            moment = now + offset * PERIOD
            if hmac.compare_digest(totp.at(moment), code):
                return totp.timecode(moment)
        return None
