"""Accounts: the single custom user model used for authentication.

Design note
-----------
The store was originally built on a standalone ``customers.Customer`` row and
four domain tables (orders, cart, addresses, wishlist) foreign-key to it. This
module introduces the project's custom user model *without* re-pointing those
relationships: ``User`` owns identity and credentials, and each customer gets a
``Customer`` profile row linked one-to-one. ``Customer.user`` is the bridge.

That keeps the existing commerce code untouched while giving authentication a
proper ``AUTH_USER_MODEL`` to build on.
"""

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.core.validators import MinLengthValidator
from django.db import models
from django.utils import timezone

from common.validators import canonical_mobile, validate_mobile_number


class UserRole(models.TextChoices):
    ADMIN = "ADMIN", "Admin"
    CUSTOMER = "CUSTOMER", "Customer"


class UserManager(BaseUserManager):
    """Manager keyed on mobile for customers and username for the admin.

    Mobile numbers are normalised before every lookup and save so that
    ``9876543210``, ``+919876543210`` and ``09876543210`` cannot create three
    accounts for the same person.
    """

    use_in_migrations = True

    def _normalise(self, mobile_number):
        if not mobile_number:
            return None
        canonical = canonical_mobile(mobile_number)
        return canonical or None

    def create_user(self, *, mobile_number=None, username=None, email=None,
                    password=None, role=UserRole.CUSTOMER, **extra_fields):
        if not mobile_number and not username:
            raise ValueError("A user needs either a mobile number or a username.")
        mobile_number = self._normalise(mobile_number)
        username = username.lower().strip() if username else None
        email = self.normalize_email(email) if email else None

        user = self.model(
            mobile_number=mobile_number,
            username=username,
            email=email,
            role=role,
            **extra_fields,
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", UserRole.ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_email_verified", True)
        return self.create_user(
            username=username, email=email, password=password, **extra_fields
        )

    def get_by_mobile(self, mobile_number):
        return self.filter(mobile_number=self._normalise(mobile_number)).first()

    def get_admin(self):
        return self.filter(role=UserRole.ADMIN, is_active=True).first()


class User(AbstractBaseUser, PermissionsMixin):
    """The authentication subject for both admins and customers.

    ``username`` is used only by the single admin account. ``mobile_number`` is
    used only by customers. Each field is unique-when-present, and a database
    check constraint enforces that a row actually carries the identifier its
    role requires - so a customer can never be stored without a mobile number.
    """

    username = models.CharField(
        max_length=150,
        unique=True,
        null=True,
        blank=True,
        validators=[MinLengthValidator(3)],
        help_text="Admin login name. Customers have no username.",
    )
    mobile_number = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        validators=[validate_mobile_number],
        help_text="Customer login identity, stored normalised (+91XXXXXXXXXX).",
    )
    email = models.EmailField(
        max_length=254, null=True, blank=True, db_index=True
    )
    role = models.CharField(
        max_length=20, choices=UserRole.choices, default=UserRole.CUSTOMER, db_index=True
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)
    is_mobile_verified = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "accounts_user"
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ("-date_joined",)
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(role="ADMIN", username__isnull=False)
                    | models.Q(role="CUSTOMER", mobile_number__isnull=False)
                ),
                name="user_role_has_identity",
            ),
            models.CheckConstraint(
                condition=models.Q(role__in=["ADMIN", "CUSTOMER"]),
                name="user_role_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["role", "is_active"], name="user_role_active_idx"),
        ]

    def __str__(self):
        return self.username or self.mobile_number or f"user#{self.pk}"

    # -- convenient role checks ------------------------------------------------
    @property
    def is_admin(self):
        return self.role == UserRole.ADMIN

    @property
    def is_customer(self):
        return self.role == UserRole.CUSTOMER

    @property
    def display_name(self):
        if self.username:
            return self.username
        # customer_profile is the bridge row; the name lives on the Customer.
        link = getattr(self, "customer_profile", None)
        if link is not None:
            customer = getattr(link, "customer", None)
            if customer is not None and customer.full_name:
                return customer.full_name
        return self.mobile_number or self.email or f"user#{self.pk}"

    def save(self, *args, **kwargs):
        if self.username:
            self.username = self.username.lower().strip()
        if self.mobile_number:
            self.mobile_number = canonical_mobile(self.mobile_number)
        super().save(*args, **kwargs)


class CustomerProfile(models.Model):
    """One-to-one bridge from a ``User`` to the existing commerce ``Customer``.

    The store's orders, cart, addresses and wishlist all foreign-key to
    ``customers.Customer``. Rather than re-point four domains (and 924 live
    rows) at a new table, the authentication layer links through here.
    """

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="customer_profile"
    )
    customer = models.OneToOneField(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="auth_profile",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_customer_profile"
        verbose_name = "Customer profile link"
        verbose_name_plural = "Customer profile links"

    def __str__(self):
        return f"{self.user} <-> {self.customer}"
