"""Reusable field validators (serializer + model level)."""

import re

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

MOBILE_REGEX = r"^\+?[1-9]\d{7,14}$"
PINCODE_REGEX = r"^[1-9][0-9]{5}$"
GST_REGEX = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
UPI_ID_REGEX = r"^[a-zA-Z0-9.\-_]{2,64}@[a-zA-Z]{2,64}$"

validate_mobile_number = RegexValidator(
    regex=MOBILE_REGEX,
    message="Enter a valid mobile number: optional '+' followed by 8 to 15 digits.",
)

validate_pincode = RegexValidator(
    regex=PINCODE_REGEX,
    message="Enter a valid 6 digit PIN code (first digit cannot be 0).",
)

validate_gst_number = RegexValidator(
    regex=GST_REGEX,
    message="Enter a valid 15 character GSTIN.",
)

validate_upi_id = RegexValidator(
    regex=UPI_ID_REGEX,
    message="Enter a valid UPI ID, for example umsmart@okhdfcbank.",
)


def validate_non_negative(value):
    if value is not None and value < 0:
        raise ValidationError("Value cannot be negative.")


def validate_positive(value):
    if value is not None and value <= 0:
        raise ValidationError("Value must be greater than zero.")


def validate_percentage(value):
    if value is None:
        return
    if value < 0 or value > 100:
        raise ValidationError("Percentage must be between 0 and 100.")


def validate_image_file(value):
    """Validate uploaded images by size and extension."""
    from django.conf import settings

    max_mb = getattr(settings, "MAX_UPLOAD_SIZE_MB", 10)
    if value is None:
        return
    size = getattr(value, "size", None)
    if size and size > max_mb * 1024 * 1024:
        raise ValidationError(f"Image must be smaller than {max_mb} MB.")

    allowed = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    name = getattr(value, "name", "")
    if "." in name and ("." + name.rsplit(".", 1)[1].lower()) not in allowed:
        raise ValidationError(
            "Unsupported image format. Allowed: jpg, jpeg, png, webp, gif."
        )


def validate_document_file(value):
    """Validate uploaded payment proofs / documents."""
    from django.conf import settings

    max_mb = getattr(settings, "MAX_UPLOAD_SIZE_MB", 10)
    if value is None:
        return
    size = getattr(value, "size", None)
    if size and size > max_mb * 1024 * 1024:
        raise ValidationError(f"File must be smaller than {max_mb} MB.")
    allowed = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
    name = getattr(value, "name", "")
    if "." in name and ("." + name.rsplit(".", 1)[1].lower()) not in allowed:
        raise ValidationError("Unsupported file format. Allowed: jpg, jpeg, png, webp, pdf.")


def normalise_mobile(value: str) -> str:
    """Strip spaces, dashes and brackets from a mobile number."""
    if not value:
        return value
    cleaned = re.sub(r"[\s\-()]", "", str(value))
    return cleaned


def canonical_mobile(value: str) -> str:
    """Canonicalise an Indian mobile number to E.164 (+91XXXXXXXXXX).

    Strips separators first, then folds the three spellings a person may type
    into one identity:

        9876543210      -> +919876543210
        09876543210     -> +919876543210
        +919876543210   -> +919876543210
        919876543210    -> +919876543210

    Used by the authentication layer. ``normalise_mobile`` keeps its original
    separator-only behaviour because the commerce tables already store numbers
    in that form and changing it would rewrite live data.
    """
    if not value:
        return ""
    cleaned = re.sub(r"[\s\-().]", "", str(value))
    digits = cleaned.lstrip("+")

    if not digits.isdigit():
        return cleaned

    # Drop the Indian trunk '0' prefix (09876543210 -> 9876543210).
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]

    # Fold a bare 10-digit national number into +91 form.
    if len(digits) == 10 and digits[0] in "6789":
        return f"+91{digits}"

    # Already carries the country code.
    if len(digits) == 12 and digits.startswith("91"):
        return f"+{digits}"

    return f"+{digits}" if cleaned.startswith("+") else cleaned


def is_indian_mobile(value: str) -> bool:
    """True for a canonical +91 number with a valid leading digit."""
    canonical = canonical_mobile(value)
    return (
        len(canonical) == 13
        and canonical.startswith("+91")
        and canonical[3] in "6789"
        and canonical[3:].isdigit()
    )


def normalise_pincode(value: str) -> str:
    if not value:
        return value
    return re.sub(r"\s", "", str(value))
