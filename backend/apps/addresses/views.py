"""Address API views.

SECURITY NOTE: authentication is not implemented in this phase. These
endpoints are unrestricted and must NOT be exposed publicly until the
authentication layer ships.
"""

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.addresses import selectors, services
from apps.addresses.filters import AddressFilter
from apps.addresses.serializers import AddressSerializer, AddressWriteSerializer
from common.identity import resolve_customer
from common.views import BaseModelViewSet


class MyAddressListView(APIView):
    """The caller's own address book."""

    @extend_schema(responses={200: AddressSerializer(many=True)}, tags=["Addresses"])
    def get(self, request):
        customer = resolve_customer(request)
        addresses = selectors.get_addresses_for_customer(customer)
        return Response(
            AddressSerializer(addresses, many=True, context={"request": request}).data
        )


class MyAddressCreateView(APIView):
    @extend_schema(
        request=AddressWriteSerializer,
        responses={201: AddressSerializer},
        tags=["Addresses"],
        description="Add an address for the caller. The first one becomes the default.",
    )
    def post(self, request):
        customer = resolve_customer(request)
        serializer = AddressWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        address = services.create_address(customer, **serializer.validated_data)
        return Response(
            AddressSerializer(address, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class AddressViewSet(BaseModelViewSet):
    """CRUD API for delivery addresses (admin scope) plus customer actions."""

    filterset_class = AddressFilter
    search_fields = ("recipient_name", "line1", "line2", "city", "pincode")
    ordering_fields = ("created_at", "city", "is_default")
    ordering = ("-is_default", "-updated_at")
    lookup_value_regex = r"[0-9a-fA-F-]{1,36}|[0-9]+"

    def get_queryset(self):
        params = self.request.query_params
        return selectors.list_addresses(
            {
                "customer": params.get("customer"),
                "city": params.get("city"),
                "pincode": params.get("pincode"),
                "is_default": _to_bool(params.get("is_default")),
                "search": params.get("search"),
            }
        )

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return AddressWriteSerializer
        return AddressSerializer

    def get_object(self):
        address = services.get_address_or_404(self.kwargs["pk"])
        self.check_object_permissions(self.request, address)
        return address

    def create(self, request, *args, **kwargs):
        customer = resolve_customer(request)
        serializer = AddressWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        address = services.create_address(customer, **serializer.validated_data)
        return Response(
            AddressSerializer(address, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        return self._update(request, partial=False)

    def partial_update(self, request, *args, **kwargs):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        address = self.get_object()
        serializer = AddressWriteSerializer(address, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        updated = services.update_address(address, **serializer.validated_data)
        return Response(AddressSerializer(updated, context={"request": request}).data)

    def destroy(self, request, *args, **kwargs):
        services.delete_address(self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        request=None, responses={200: AddressSerializer},
        description="Make this the customer's default delivery address.",
    )
    @action(detail=True, methods=["post"], url_path="set-default")
    def set_default(self, request, pk=None):
        address = services.set_default_address(self.get_object())
        return Response(AddressSerializer(address, context={"request": request}).data)


def _to_bool(value):
    if value is None:
        return None
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}
