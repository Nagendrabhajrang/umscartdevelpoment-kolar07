"""Store settings API views.

SECURITY NOTE: authentication is not implemented in this phase. These
endpoints are unrestricted and must NOT be exposed publicly until the
authentication layer ships.
"""

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.store_settings import selectors, services
from apps.store_settings.serializers import (
    DeliveryChargeQuoteResultSerializer,
    DeliveryChargeQuoteSerializer,
    DeliverySlabSerializer,
    StoreHolidaySerializer,
    StoreSettingsSerializer,
    StoreSettingsUpdateSerializer,
)
from common.views import BaseModelViewSet


class StoreSettingsView(APIView):
    """Retrieve or update the singleton store configuration."""

    @extend_schema(responses={200: StoreSettingsSerializer}, tags=["Store Settings"])
    def get(self, request):
        settings_obj = selectors.get_store_settings()
        return Response(
            StoreSettingsSerializer(settings_obj, context={"request": request}).data
        )

    @extend_schema(
        request=StoreSettingsUpdateSerializer,
        responses={200: StoreSettingsSerializer},
        tags=["Store Settings"],
    )
    def patch(self, request):
        settings_obj = selectors.get_store_settings()
        serializer = StoreSettingsUpdateSerializer(
            settings_obj, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        updated = services.update_store_settings(settings_obj, **serializer.validated_data)
        return Response(
            StoreSettingsSerializer(updated, context={"request": request}).data
        )


class GenerateUpiQrView(APIView):
    """Draw the store's UPI QR from the configured UPI ID.

    The alternative is uploading a PNG exported from a UPI app; this endpoint
    exists so an admin can change the UPI ID and get a matching, scannable QR
    in one click without touching a phone.
    """

    @extend_schema(
        request=None,
        responses={200: StoreSettingsSerializer},
        tags=["Store Settings"],
        description=(
            "Regenerate the store UPI QR image from `upi_id` (optionally baking in "
            "a fixed amount via ?amount=). Returns the updated settings."
        ),
    )
    def post(self, request):
        settings_obj = selectors.get_store_settings()
        amount = request.data.get("amount") or None
        # BusinessRuleError is an APIException, so the global handler renders it
        # as the usual {"error": {...}} envelope.
        name = services.generate_upi_qr_image(
            settings_obj,
            amount=amount,
            note=str(request.data.get("note") or ""),
        )
        if not name:
            return Response(
                {
                    "error": {
                        "code": "qr_unavailable",
                        "message": "QR generation is unavailable on this server.",
                        "status": 400,
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        settings_obj.refresh_from_db()
        return Response(
            StoreSettingsSerializer(settings_obj, context={"request": request}).data
        )


class DeliveryQuoteView(APIView):
    """Quote the delivery charge for a given cart subtotal."""

    @extend_schema(
        request=DeliveryChargeQuoteSerializer,
        responses={200: DeliveryChargeQuoteResultSerializer},
        tags=["Store Settings"],
        description=(
            "Resolve the delivery charge for a subtotal using the store "
            "configuration and delivery slabs."
        ),
    )
    def post(self, request):
        serializer = DeliveryChargeQuoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subtotal = serializer.validated_data["subtotal"]
        settings_obj = selectors.get_store_settings()
        quote = services.calculate_delivery_charge(subtotal, settings_obj)
        payload = {
            "subtotal": str(subtotal),
            **{key: str(value) if hasattr(value, "as_tuple") else value
               for key, value in quote.items()},
            "eta_minutes": settings_obj.delivery_eta_minutes,
            "minimum_order_value": str(settings_obj.minimum_order_value),
        }
        return Response(DeliveryChargeQuoteResultSerializer(payload).data)


class DeliverySlabViewSet(BaseModelViewSet):
    """CRUD API for graduated delivery charges."""

    search_fields = ("name",)
    ordering_fields = ("min_order_value", "delivery_charge")
    ordering = ("min_order_value",)
    lookup_value_regex = r"[0-9a-fA-F-]{1,36}|[0-9]+"

    def get_queryset(self):
        active_only = str(self.request.query_params.get("active_only", "")).lower() in {
            "1", "true", "yes"
        }
        return selectors.list_delivery_slabs(active_only=active_only)

    def get_serializer_class(self):
        return DeliverySlabSerializer

    def get_object(self):
        slab = services.get_slab_or_404(self.kwargs["pk"])
        self.check_object_permissions(self.request, slab)
        return slab

    def create(self, request, *args, **kwargs):
        serializer = DeliverySlabSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        slab = services.create_delivery_slab(**serializer.validated_data)
        return Response(
            DeliverySlabSerializer(slab).data, status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        return self._update(request, partial=False)

    def partial_update(self, request, *args, **kwargs):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        slab = self.get_object()
        serializer = DeliverySlabSerializer(slab, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        updated = services.update_delivery_slab(slab, **serializer.validated_data)
        return Response(DeliverySlabSerializer(updated).data)

    def destroy(self, request, *args, **kwargs):
        services.delete_delivery_slab(self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        responses={200: DeliveryChargeQuoteResultSerializer},
        description="Preview which slab applies to a given subtotal.",
        parameters=[],
    )
    @action(detail=False, methods=["get"], url_path="resolve")
    def resolve(self, request):
        from decimal import Decimal, InvalidOperation

        raw = request.query_params.get("subtotal", "0")
        try:
            subtotal = Decimal(str(raw))
        except (InvalidOperation, TypeError):
            return Response(
                {"error": {"code": "invalid_subtotal", "message": "Invalid subtotal.", "status": 400}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        settings_obj = selectors.get_store_settings()
        quote = services.calculate_delivery_charge(subtotal, settings_obj)
        payload = {
            "subtotal": str(subtotal),
            **{key: str(value) if hasattr(value, "as_tuple") else value
               for key, value in quote.items()},
            "eta_minutes": settings_obj.delivery_eta_minutes,
            "minimum_order_value": str(settings_obj.minimum_order_value),
        }
        return Response(DeliveryChargeQuoteResultSerializer(payload).data)


class StoreHolidayViewSet(BaseModelViewSet):
    """CRUD API for store holidays."""

    search_fields = ("reason",)
    ordering_fields = ("date",)
    ordering = ("date",)
    lookup_value_regex = r"[0-9a-fA-F-]{1,36}|[0-9]+"

    def get_queryset(self):
        upcoming = str(self.request.query_params.get("upcoming_only", "")).lower() in {
            "1", "true", "yes"
        }
        return selectors.list_holidays(upcoming_only=upcoming)

    def get_serializer_class(self):
        return StoreHolidaySerializer

    def get_object(self):
        holiday = services.get_holiday_or_404(self.kwargs["pk"])
        self.check_object_permissions(self.request, holiday)
        return holiday

    def create(self, request, *args, **kwargs):
        serializer = StoreHolidaySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        holiday = services.create_holiday(**serializer.validated_data)
        return Response(
            StoreHolidaySerializer(holiday).data, status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        return self._update(request, partial=False)

    def partial_update(self, request, *args, **kwargs):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        holiday = self.get_object()
        serializer = StoreHolidaySerializer(holiday, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        updated = services.update_holiday(holiday, **serializer.validated_data)
        return Response(StoreHolidaySerializer(updated).data)

    def destroy(self, request, *args, **kwargs):
        services.delete_holiday(self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)
