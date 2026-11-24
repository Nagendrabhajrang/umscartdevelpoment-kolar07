"""Payment API views.

SECURITY NOTE: authentication is not implemented in this phase. Approval and
rejection endpoints are especially sensitive - they must NOT be reachable
publicly until admin authentication and RBAC ship.
"""

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.payments import selectors, services
from apps.payments.filters import PaymentFilter, RefundFilter
from apps.payments.models import PaymentVerification
from apps.payments.serializers import (
    CodCollectedSerializer,
    PaymentApprovalSerializer,
    PaymentReferenceSerializer,
    PaymentProofSerializer,
    PaymentRejectionSerializer,
    PaymentSerializer,
    PaymentStatsSerializer,
    PaymentVerificationSerializer,
    RefundCreateSerializer,
    RefundSerializer,
)
from common.views import BaseModelViewSet, BaseReadOnlyViewSet


class PaymentViewSet(BaseModelViewSet):
    """CRUD-style access to payments plus the verification workflow."""

    http_method_names = ["get", "post", "patch", "head", "options"]
    filterset_class = PaymentFilter
    search_fields = (
        "payment_number", "transaction_id", "order__order_number",
        "customer__full_name", "customer__mobile_number",
    )
    ordering_fields = ("created_at", "amount", "payment_status")
    ordering = ("-created_at",)
    # Accepts a numeric id, a UUID, or a payment number such as PAY-20261109-A1B2C3.
    lookup_value_regex = r"[A-Za-z0-9-]{1,64}"

    def get_queryset(self):
        params = self.request.query_params
        return selectors.list_payments(
            {
                "status": params.get("status") or params.get("payment_status"),
                "method": params.get("method") or params.get("payment_method"),
                "customer": params.get("customer"),
                "order": params.get("order"),
                "order_number": params.get("order_number"),
                "date_from": params.get("date_from"),
                "date_to": params.get("date_to"),
                "search": params.get("search"),
            }
        )

    def get_serializer_class(self):
        return PaymentSerializer

    def get_object(self):
        payment = services.get_payment_or_404(self.kwargs["pk"])
        self.check_object_permissions(self.request, payment)
        return payment

    def create(self, request, *args, **kwargs):
        return Response(
            {
                "error": {
                    "code": "method_not_allowed",
                    "message": "Payments are created automatically at checkout.",
                    "status": 405,
                }
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @extend_schema(
        responses={400: dict},
        description="Store UPI ID, payee name, QR image and the amount due for this payment.",
    )
    @action(detail=True, methods=["get"], url_path="upi-details")
    def upi_details(self, request, pk=None):
        payment = self.get_object()
        return Response(services.get_upi_details(payment))

    @extend_schema(
        request=PaymentProofSerializer,
        responses={200: PaymentSerializer},
        description="Store UPI ID, payee name, QR image and the amount due for this payment.",
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="submit-proof",
        parser_classes=[MultiPartParser, FormParser, JSONParser],
    )
    def submit_proof(self, request, pk=None):
        payment = self.get_object()
        serializer = PaymentProofSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        updated = services.submit_payment_proof(
            payment,
            transaction_reference=data["transaction_reference"],
            proof=data.get("payment_proof"),
            payer_name=data.get("payer_name", ""),
            payer_upi_id=data.get("upi_id", ""),
            payer_mobile=data.get("payer_mobile", ""),
            notes=data.get("notes", ""),
        )
        return Response(PaymentSerializer(updated, context={"request": request}).data)

    @extend_schema(
        request=PaymentApprovalSerializer,
        responses={200: PaymentSerializer},
        description="Store UPI ID, payee name, QR image and the amount due for this payment.",
    )
    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        payment = self.get_object()
        serializer = PaymentApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = services.approve_payment(
            payment,
            verified_by=serializer.validated_data.get("verified_by", "admin"),
            remarks=serializer.validated_data.get("remarks", ""),
        )
        return Response(PaymentSerializer(updated, context={"request": request}).data)

    @extend_schema(
        request=PaymentRejectionSerializer,
        responses={200: PaymentSerializer},
        description="Store UPI ID, payee name, QR image and the amount due for this payment.",
    )
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        payment = self.get_object()
        serializer = PaymentRejectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = services.reject_payment(
            payment,
            reason=serializer.validated_data["reason"],
            verified_by=serializer.validated_data.get("verified_by", "admin"),
        )
        return Response(PaymentSerializer(updated, context={"request": request}).data)

    @extend_schema(
        request=CodCollectedSerializer,
        responses={200: PaymentSerializer},
        description="Record cash received. Moves payment_status to 'paid'.",
    )
    @action(detail=True, methods=["post"], url_path="cod-collected")
    def cod_collected(self, request, pk=None):
        payment = self.get_object()
        serializer = CodCollectedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = services.mark_cod_collected(
            payment,
            amount=serializer.validated_data.get("amount"),
            collected_by=serializer.validated_data.get("collected_by", ""),
            remarks=serializer.validated_data.get("remarks", ""),
            transaction_id=serializer.validated_data.get("transaction_id", ""),
            mobile_number=serializer.validated_data.get("mobile_number", ""),
            feedback=serializer.validated_data.get("feedback", ""),
            upi_id=serializer.validated_data.get("upi_id", ""),
        )
        return Response(PaymentSerializer(updated, context={"request": request}).data)

    @action(detail=True, methods=["patch"], url_path="reference")
    @extend_schema(
        request=PaymentReferenceSerializer,
        responses={200: PaymentSerializer},
        description=(
            "Correct the payer's mobile number / UPI id on a payment. "
            "Does not change the payment status."
        ),
    )
    def reference(self, request, pk=None):
        payment = self.get_object()
        serializer = PaymentReferenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        editable = ("transaction_id", "mobile_number", "feedback")
        fields = [name for name in editable if name in data]
        if not fields:
            return Response(
                {
                    "error": {
                        "code": "nothing_to_update",
                        "message": "Send transaction_id, mobile_number or feedback.",
                        "status": 400,
                    }
                },
                status=400,
            )
        for name in fields:
            setattr(payment, name, data[name])
        payment.save(update_fields=[*fields, "updated_at"])
        return Response(PaymentSerializer(payment, context={"request": request}).data)

    @extend_schema(
        request=RefundCreateSerializer,
        responses={201: RefundSerializer},
        description="Record a (manual) refund against a settled payment.",
    )
    @action(detail=True, methods=["post"], url_path="refund")
    def refund(self, request, pk=None):
        payment = self.get_object()
        serializer = RefundCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        refund = services.create_refund(
            payment,
            amount=serializer.validated_data["amount"],
            reason=serializer.validated_data.get("reason", ""),
            feedback=serializer.validated_data.get("feedback", ""),
            processed_by=serializer.validated_data.get("processed_by", "admin"),
        )
        return Response(
            RefundSerializer(refund, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        responses={200: PaymentVerificationSerializer(many=True)},
        description="Full verification history for this payment.",
    )
    @action(detail=True, methods=["get"], url_path="verifications")
    def verifications(self, request, pk=None):
        payment = self.get_object()
        return Response(
            PaymentVerificationSerializer(
                selectors.list_verifications(payment), many=True,
                context={"request": request},
            ).data
        )

    @extend_schema(
        responses={200: PaymentSerializer(many=True)},
        description="ADMIN: payments waiting for manual verification.",
    )
    @action(detail=False, methods=["get"], url_path="pending-verification")
    def pending_verification(self, request):
        queryset = selectors.pending_verifications()
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(
                PaymentSerializer(page, many=True, context={"request": request}).data
            )
        return Response(
            PaymentSerializer(queryset, many=True, context={"request": request}).data
        )

    @extend_schema(responses={200: PaymentStatsSerializer})
    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        return Response(PaymentStatsSerializer(selectors.payment_stats()).data)


class OrderPaymentView(APIView):
    """Convenience view: the payment record for a given order."""

    @extend_schema(responses={200: PaymentSerializer}, tags=["Payments"])
    def get(self, request, order_id):
        from apps.orders.services import get_order_or_404

        order = get_order_or_404(order_id)
        payment = selectors.get_payment_for_order(order)
        if payment is None:
            return Response(
                {
                    "error": {
                        "code": "payment_not_found",
                        "message": "No payment exists for this order.",
                        "status": 404,
                    }
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(PaymentSerializer(payment, context={"request": request}).data)


@extend_schema_view(
    list=extend_schema(
        tags=["Payments"],
        operation_id="payments_verification_log_list",
        summary="List every verification event",
        description=(
            "Global audit log of payment verification events. Filter with "
            "`?payment=<id>` and `?action=submitted|approved|rejected|resubmitted`."
        ),
    ),
    retrieve=extend_schema(
        tags=["Payments"],
        operation_id="payments_verification_log_retrieve",
        summary="Retrieve one verification event",
    ),
)
class PaymentVerificationViewSet(BaseReadOnlyViewSet):
    """Read-only audit log of payment verification decisions."""

    ordering = ("-created_at",)
    lookup_value_regex = r"[0-9a-fA-F-]{1,36}|[0-9]+"

    def get_queryset(self):
        queryset = PaymentVerification.objects.select_related("payment").all()
        payment_id = self.request.query_params.get("payment")
        if payment_id:
            queryset = queryset.filter(payment_id=payment_id)
        action_filter = self.request.query_params.get("action")
        if action_filter:
            queryset = queryset.filter(action=action_filter)
        return queryset

    def get_serializer_class(self):
        return PaymentVerificationSerializer


class RefundViewSet(BaseModelViewSet):
    """CRUD API for refunds."""

    filterset_class = RefundFilter
    ordering_fields = ("created_at", "amount")
    ordering = ("-created_at",)
    lookup_value_regex = r"[0-9a-fA-F-]{1,36}|[0-9]+"

    def get_queryset(self):
        params = self.request.query_params
        return selectors.list_refunds(
            {"status": params.get("status"), "payment": params.get("payment")}
        )

    def get_serializer_class(self):
        return RefundSerializer

    def get_object(self):
        refund = services.get_refund_or_404(self.kwargs["pk"])
        self.check_object_permissions(self.request, refund)
        return refund

    def create(self, request, *args, **kwargs):
        return Response(
            {
                "error": {
                    "code": "method_not_allowed",
                    "message": (
                        "Create refunds via POST /payments/{id}/refund/ so the "
                        "amount can be validated against the settled payment."
                    ),
                    "status": 405,
                }
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )
