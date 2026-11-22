"""Input validation for the authentication endpoints.

Serializers validate shape and format only. Business rules live in the service
layer so they can be reused by the management commands and the tests.
"""

from rest_framework import serializers

OTP_FIELD_HELP = "The 6-digit code that was sent to you."


class AdminLoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, trim_whitespace=True)
    password = serializers.CharField(max_length=128, trim_whitespace=False, style={"input_type": "password"})


class OTPCodeSerializer(serializers.Serializer):
    code = serializers.RegexField(
        regex=r"^\d{6}$",
        max_length=6,
        error_messages={"invalid": "Enter the 6-digit code."},
        help_text=OTP_FIELD_HELP,
    )


class AdminForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class AdminVerifyResetOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    code = serializers.RegexField(regex=r"^\d{6}$", max_length=6)


class AdminResetPasswordSerializer(serializers.Serializer):
    reset_token = serializers.CharField(max_length=256)
    new_password = serializers.CharField(max_length=128, trim_whitespace=False, style={"input_type": "password"})
    confirm_password = serializers.CharField(max_length=128, trim_whitespace=False, style={"input_type": "password"})

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "The two passwords do not match."}
            )
        return attrs


class AdminChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(max_length=128, trim_whitespace=False, style={"input_type": "password"})
    code = serializers.RegexField(regex=r"^\d{6}$", max_length=6)
    new_password = serializers.CharField(max_length=128, trim_whitespace=False, style={"input_type": "password"})
    confirm_password = serializers.CharField(max_length=128, trim_whitespace=False, style={"input_type": "password"})

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "The two passwords do not match."}
            )
        return attrs


class MobileSerializer(serializers.Serializer):
    mobile_number = serializers.CharField(
        max_length=20,
        help_text="Indian mobile number. 9876543210, +919876543210 and 09876543210 are equivalent.",
    )


class CustomerVerifyOTPSerializer(serializers.Serializer):
    mobile_number = serializers.CharField(max_length=20)
    code = serializers.RegexField(regex=r"^\d{6}$", max_length=6, help_text=OTP_FIELD_HELP)


class RefreshTokenSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class CustomerProfileSerializer(serializers.Serializer):
    """Profile fields a customer owns. Identity fields stay read-only."""

    # `display_name` is what the read payload calls this field, so accept the
    # same spelling on write instead of making callers translate.
    full_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    display_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True, write_only=True
    )
    email = serializers.EmailField(max_length=254, required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs):
        alias = attrs.pop("display_name", None)
        if alias is not None and "full_name" not in attrs:
            attrs["full_name"] = alias
        return attrs
