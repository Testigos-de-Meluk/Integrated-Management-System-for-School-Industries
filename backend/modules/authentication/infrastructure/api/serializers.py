"""DTOs of the Authentication REST API."""

from rest_framework import serializers

SIX_DIGITS_MESSAGE = "El código debe contener 6 dígitos."


class LoginSerializer(serializers.Serializer):
    email = serializers.CharField(max_length=254)
    password = serializers.CharField(max_length=128, write_only=True, trim_whitespace=False)


class PreAuthSerializer(serializers.Serializer):
    pre_auth_token = serializers.CharField()


class CodeSerializer(PreAuthSerializer):
    # US 1.3.3: a malformed code is rejected without consuming an attempt.
    code = serializers.RegexField(
        r"^\d{6}$", error_messages={"invalid": SIX_DIGITS_MESSAGE, "blank": SIX_DIGITS_MESSAGE}
    )


class LoginChallengeSerializer(serializers.Serializer):
    step = serializers.ChoiceField(choices=["VERIFY_CODE", "ENROLL_AUTHENTICATOR"])
    pre_auth_token = serializers.CharField()
    expires_at = serializers.DateTimeField()


class EnrollmentSerializer(serializers.Serializer):
    qr_code = serializers.CharField(help_text="data URI of an SVG image")
    secret = serializers.CharField(help_text="Base32 key to type it manually")
    account_name = serializers.CharField()
    expires_at = serializers.DateTimeField()


class CurrentUserSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    full_name = serializers.CharField()
    email = serializers.EmailField()
    role = serializers.CharField()
    permissions = serializers.ListField(child=serializers.CharField())


class SessionSerializer(serializers.Serializer):
    """The refresh token is NOT here: it is sent only as an httpOnly cookie."""

    access_token = serializers.CharField()
    access_expires_at = serializers.DateTimeField()
    user = CurrentUserSerializer()
