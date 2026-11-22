"""Customer API views.

SECURITY NOTE (applies to every view in this module): authentication is not
implemented in this phase. These endpoints are unrestricted and must NOT be
exposed publicly until the authentication layer ships. See
``docs/AUTHENTICATION.md``.
"""

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.customers import selectors, services
from apps.customers.filters import CustomerFilter
from apps.customers.serializers import (
    CustomerDetailSerializer,
    CustomerListSerializer,
    CustomerNoteSerializer,
    CustomerStatusSerializer,
    CustomerSummarySerializer,
    CustomerWriteSerializer,
)
from common.views import BaseModelViewSet


class CustomerViewSet(BaseModelViewSet):
    """CRUD API for customer profiles.

    Customer-scoped resources elsewhere in the API reference customers by
    their numeric id (or public UUID).
    """

    queryset_for_schema = None
    filterset_class = CustomerFilter
    search_fields = ("full_name", "mobile_number", "email")
    ordering_fields = ("created_at", "full_name", "status")
    ordering = ("-created_at",)
    lookup_value_regex = r"[0-9a-fA-F-]{1,36}|[0-9]+"

    def get_queryset(self):
        return selectors.list_customers(
            {
                "status": self.request.query_params.get("status"),
                "search": self.request.query_params.get("search"),
                "created_after": self.request.query_params.get("created_after"),
                "created_before": self.request.query_params.get("created_before"),
            }
        )

    def get_serializer_class(self):
        if self.action == "list":
            return CustomerListSerializer
        if self.action in {"create", "update", "partial_update"}:
            return CustomerWriteSerializer
        if self.action == "set_status":
            return CustomerStatusSerializer
        if self.action == "notes":
            return CustomerNoteSerializer
        return CustomerDetailSerializer

    def get_object(self):
        """Resolve by numeric id or public UUID."""
        instance = services.get_customer_or_404(self.kwargs["pk"])
        self.check_object_permissions(self.request, instance)
        return instance

    def create(self, request, *args, **kwargs):
        serializer = CustomerWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = services.create_customer(**serializer.validated_data)
        return Response(
            CustomerDetailSerializer(customer).data, status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        customer = self.get_object()
        serializer = CustomerWriteSerializer(
            customer, data=request.data, partial=False
        )
        serializer.is_valid(raise_exception=True)
        updated = services.update_customer(customer, **serializer.validated_data)
        return Response(CustomerDetailSerializer(updated).data)

    def partial_update(self, request, *args, **kwargs):
        customer = self.get_object()
        serializer = CustomerWriteSerializer(
            customer, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        updated = services.update_customer(customer, **serializer.validated_data)
        return Response(CustomerDetailSerializer(updated).data)

    def destroy(self, request, *args, **kwargs):
        customer = self.get_object()
        services.delete_customer(customer)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        request=CustomerStatusSerializer,
        responses={200: CustomerDetailSerializer},
        description="Activate, deactivate or block a customer.",
    )
    @action(detail=True, methods=["post"], url_path="status")
    def set_status(self, request, pk=None):
        customer = self.get_object()
        serializer = CustomerStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = services.change_customer_status(
            customer, serializer.validated_data["status"]
        )
        return Response(CustomerDetailSerializer(updated).data)

    @extend_schema(
        request=CustomerNoteSerializer,
        responses={201: CustomerNoteSerializer, 200: CustomerNoteSerializer(many=True)},
        description="List or append internal notes for a customer.",
    )
    @action(detail=True, methods=["get", "post"], url_path="notes")
    def notes(self, request, pk=None):
        customer = self.get_object()
        if request.method == "GET":
            serializer = CustomerNoteSerializer(
                customer.internal_notes.all(), many=True
            )
            return Response(serializer.data)

        serializer = CustomerNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = services.add_customer_note(
            customer,
            note=serializer.validated_data["note"],
            author=serializer.validated_data.get("author", ""),
        )
        return Response(CustomerNoteSerializer(note).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        responses={200: CustomerSummarySerializer},
        parameters=[],
        description="Aggregate customer counters for dashboards.",
    )
    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        return Response(CustomerSummarySerializer(selectors.customer_summary()).data)
