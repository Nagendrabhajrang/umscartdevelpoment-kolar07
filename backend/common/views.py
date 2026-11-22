"""Reusable view sets and mixins.

Views stay thin: they validate input through serializers, delegate every state
change to ``services.py`` and read data through ``selectors.py``.
"""

from django.db.models import ProtectedError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from common.exceptions import BusinessRuleError
from common.pagination import StandardResultsSetPagination


class BaseViewSetMixin:
    """Common configuration shared by every UMS Mart view set."""

    pagination_class = StandardResultsSetPagination
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    SECURITY_NOTE = (
        "UMS Mart SECURITY NOTE: authentication is not implemented in this "
        "phase. This endpoint is unrestricted and must NOT be exposed publicly "
        "until the authentication layer is delivered. See docs/AUTHENTICATION.md."
    )

    def get_queryset(self):
        """Selectors are the single entry point for reads."""
        selector_name = getattr(self, "selector", None)
        if selector_name is None:
            raise NotImplementedError(
                f"{type(self).__name__} must define a selector or override get_queryset()."
            )
        selector = _import_selector(self.selector_module, selector_name)
        return selector(self.get_selector_kwargs())

    selector_module = None

    def get_selector_kwargs(self) -> dict:
        return {}

    def finalize_response(self, request, response, *args, **kwargs):
        # Give clients a stable marker of where they are in the API surface.
        if isinstance(response, Response):
            response.setdefault("X-API-Version", "v1")
        if not response.get("X-API-Version"):
            response["X-API-Version"] = "v1"
        return super().finalize_response(request, response, *args, **kwargs)


class BaseModelViewSet(BaseViewSetMixin, viewsets.ModelViewSet):
    """CRUD view set base for models with a generated numeric primary key."""

    def perform_destroy(self, instance):  # noqa: D102
        try:
            instance.delete()
        except ProtectedError as exc:
            raise BusinessRuleError(
                message=(
                    "This record cannot be deleted because other records still "
                    "reference it."
                ),
                code="protected_relationship",
                details={"referenced_by": [str(obj) for obj in exc.protected_objects][:10]},
                status_code=status.HTTP_409_CONFLICT,
            ) from exc


class BaseReadOnlyViewSet(BaseViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Read-only view set base."""


class StatusUpdateMixin:
    """Adds a ``POST {detail}/status/`` action that delegates to a service."""

    status_service = None  # dotted path "module:function"

    @action(detail=True, methods=["post"], url_path="status")
    def update_status(self, request, pk=None):
        obj = self.get_object()
        serializer_class = self.get_status_serializer_class()
        serializer = serializer_class(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)

        service = _import_selector(*self.status_service.split(":"))
        updated = service(obj, **serializer.validated_data)

        output = self.get_serializer(updated)
        return Response(output.data, status=status.HTTP_200_OK)

    def get_status_serializer_class(self):
        raise NotImplementedError


def _import_selector(module_path, name):
    import importlib

    if module_path is None:
        raise NotImplementedError("A selector module must be configured.")
    module = importlib.import_module(module_path)
    return getattr(module, name)


def _import_function(dotted_path):
    module_path, name = dotted_path.split(":")
    return _import_selector(module_path, name)
