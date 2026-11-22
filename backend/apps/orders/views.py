"""Order API views: checkout, order lifecycle and reporting.

SECURITY NOTE: authentication is not implemented in this phase. These
endpoints are unrestricted and must NOT be exposed publicly until the
authentication layer ships.
"""

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.addresses.services import get_customer_address_or_404
from apps.cart import services as cart_services
from apps.cart.serializers import CartSummarySerializer
from apps.orders import selectors, services
from apps.orders.filters import OrderFilter
from apps.orders.serializers import (
    GuestCheckoutSerializer,
    CheckoutPreviewSerializer,
    CheckoutSerializer,
    OrderCancelSerializer,
    OrderDetailSerializer,
    OrderListSerializer,
    OrderNotesSerializer,
    OrderStatsSerializer,
    OrderStatusUpdateSerializer,
    ReorderResultSerializer,
)
from apps.payments.serializers import PaymentSerializer
from apps.payments.selectors import get_payment_for_order
from common.identity import resolve_customer
from common.views import BaseModelViewSet


class CheckoutView(APIView):
    """Place an order from the caller's active cart."""

    @extend_schema(
        request=CheckoutSerializer,
        responses={201: OrderDetailSerializer},
        tags=["Orders"],
        description=(
            "Convert the active cart into an order. Runs inside a single "
            "database transaction with row-level locking on stock so concurrent "
            "checkouts cannot oversell."
        ),
    )
    def post(self, request):
        customer = resolve_customer(request)
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        address = get_customer_address_or_404(customer, data["address"])
        order = services.checkout(
            customer=customer,
            address=address,
            payment_method=data["payment_method"],
            customer_notes=data.get("customer_notes", ""),
            coupon_code=data.get("coupon_code"),
        )
        payload = OrderDetailSerializer(order, context={"request": request}).data
        payment = get_payment_for_order(order)
        if payment is not None:
            payload["payment"] = PaymentSerializer(
                payment, context={"request": request}
            ).data
            # UPI is disabled in this build; the checkout response carries the
            # cash-on-delivery payment record only.
        return Response(payload, status=status.HTTP_201_CREATED)


class GuestOrderLookupView(APIView):
    """Look an order up by number + the mobile number it was placed with.

    Public on purpose: the storefront has no login, so this pair is the only
    "proof" a shopper has. Both halves must match, which keeps one order number
    from exposing somebody else's address.
    """

    @extend_schema(
        request=None,
        responses={200: OrderDetailSerializer},
        tags=["Orders"],
        description="Public order lookup for a guest order: order number + mobile.",
    )
    def get(self, request):
        from apps.orders.models import Order

        number = (request.query_params.get("order_number") or "").strip()
        mobile = (request.query_params.get("mobile_number") or "").strip()
        if not number or not mobile:
            return Response(
                {
                    "error": {
                        "code": "order_lookup_incomplete",
                        "message": "Enter your order number and mobile number.",
                        "status": 400,
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        from common.validators import canonical_mobile

        order = (
            Order.objects.select_related("customer", "address")
            .filter(order_number__iexact=number)
            .first()
        )
        if order is None or order.customer.mobile_number != canonical_mobile(mobile):
            return Response(
                {
                    "error": {
                        "code": "order_not_found",
                        "message": (
                            "No order matches that number and mobile number."
                        ),
                        "status": 404,
                    }
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        payload = OrderDetailSerializer(order, context={"request": request}).data
        payment = get_payment_for_order(order)
        if payment is not None:
            payload["payment"] = PaymentSerializer(
                payment, context={"request": request}
            ).data
        return Response(payload)


class GuestCheckoutView(APIView):
    """Place an order from a guest basket - no account, no login.

    Round 25: the customer storefront has no authentication at all. The browser
    identifies its basket with ``X-Guest-Cart``; this endpoint captures the
    delivery details, creates (or reuses) the ``Customer`` record for the given
    mobile number, writes the address, and turns the basket into an order in one
    transaction.
    """

    @extend_schema(
        request=GuestCheckoutSerializer,
        responses={201: OrderDetailSerializer},
        tags=["Orders"],
        description="Check out a guest basket with delivery details, no login.",
    )
    def post(self, request):
        from apps.addresses.services import create_address
        from apps.cart import services as cart_services
        from apps.customers.models import Customer

        serializer = GuestCheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # 1. Who is this? One mobile number == one customer record. A returning
        #    shopper keeps their order history; a new number gets a record so the
        #    order is not an orphan and support can find it.
        customer = Customer.objects.filter(
            mobile_number=data["mobile_number"], is_deleted=False
        ).first()
        if customer is None:
            customer = Customer.objects.create(
                full_name=data["recipient_name"],
                mobile_number=data["mobile_number"],
                is_mobile_verified=False,
            )

        # 2. Where is it going? Reuse an identical saved address, otherwise add it.
        from apps.addresses.models import Address

        address = Address.objects.filter(
            customer=customer,
            line1__iexact=data["line1"],
            pincode=data["pincode"],
            recipient_mobile=data["mobile_number"],
        ).first()
        if address is None:
            address = create_address(
                customer,
                label="home",
                recipient_name=data["recipient_name"],
                recipient_mobile=data["mobile_number"],
                line1=data["line1"],
                line2=data.get("line2", ""),
                landmark=data.get("landmark", ""),
                city=data["city"],
                state=data["state"],
                pincode=data["pincode"],
                delivery_instructions=data.get("delivery_instructions", ""),
            )

        # 3. The basket: guest key first, then the customer's own active cart if
        #    the browser has none (a returning shopper on a new device).
        guest_key = request.META.get("HTTP_X_GUEST_CART", "")
        cart = None
        if guest_key:
            cart = cart_services.get_guest_cart(guest_key)
        if cart is None:
            cart = (
                cart_services.Cart.objects.filter(
                    customer=customer, status=cart_services.CartStatus.ACTIVE
                )
                .order_by("-id")
                .first()
            )
        if cart is None:
            from common.exceptions import EmptyResourceError

            raise EmptyResourceError(
                message="Your cart is empty. Add items before checking out.",
                code="empty_cart",
            )

        # A guest basket has no owner until now: attach it so checkout, which is
        # written against a customer, can operate on it.
        if cart.customer_id is None:
            other = (
                cart_services.Cart.objects.filter(
                    customer=customer, status=cart_services.CartStatus.ACTIVE
                )
                .exclude(pk=cart.pk)
                .order_by("-id")
                .first()
            )
            if other is not None:
                cart_services.merge_carts(cart, other)
                cart = other
            else:
                cart.customer = customer
                cart.guest_key = ""
                cart.save(update_fields=["customer", "guest_key", "updated_at"])

        # Tell the service which cart to use: it is the guest basket we just
        # attached, which may not be the customer's oldest active cart.
        customer._checkout_cart = cart
        order = services.checkout(
            customer=customer,
            address=address,
            payment_method=data["payment_method"],
            customer_notes=data.get("customer_notes", ""),
        )
        payload = OrderDetailSerializer(order, context={"request": request}).data
        payment = get_payment_for_order(order)
        if payment is not None:
            payload["payment"] = PaymentSerializer(
                payment, context={"request": request}
            ).data
        return Response(payload, status=status.HTTP_201_CREATED)


class CheckoutPreviewView(APIView):
    """Return the exact price breakdown that checkout would produce."""

    @extend_schema(
        request=CheckoutPreviewSerializer,
        responses={200: CartSummarySerializer},
        tags=["Orders"],
        description="Preview totals (delivery, taxes, discounts) before placing the order.",
    )
    def post(self, request):
        """
        Round 25: works for a guest basket. The storefront has no login, so the
        preview prices whatever ``X-Guest-Cart`` names; a signed-in customer (the
        dashboard, any external client) still resolves by token first.
        """
        customer = resolve_customer(request, required=False)
        serializer = CheckoutPreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if customer is not None:
            cart = cart_services.get_or_create_active_cart(customer)
        else:
            guest_key = request.META.get("HTTP_X_GUEST_CART", "")
            cart = cart_services.get_guest_cart(guest_key)
            if cart is None:
                return Response(
                    {
                        "error": {
                            "code": "empty_cart",
                            "message": "Your cart is empty. Add items before checking out.",
                            "status": 400,
                        }
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        summary = cart_services.build_cart_summary(cart)
        return Response(CartSummarySerializer(summary).data)


class MyOrdersView(APIView):
    """The caller's order history."""

    @extend_schema(responses={200: OrderListSerializer(many=True)}, tags=["Orders"])
    def get(self, request):
        customer = resolve_customer(request)
        status_filter = request.query_params.get("status")
        orders = selectors.get_orders_for_customer(customer, status=status_filter)
        return Response(
            OrderListSerializer(orders, many=True, context={"request": request}).data
        )


class OrderViewSet(BaseModelViewSet):
    """Full order lifecycle API."""

    filterset_class = OrderFilter
    search_fields = (
        "order_number", "customer__full_name", "customer__mobile_number",
        "delivery_recipient_name", "delivery_recipient_mobile",
    )
    ordering_fields = ("created_at", "grand_total", "status")
    ordering = ("-created_at",)
    # Accepts a numeric id, a UUID, or an order number such as UMS-20261109-A1B2C3.
    lookup_value_regex = r"[A-Za-z0-9-]{1,64}"

    def get_queryset(self):
        params = self.request.query_params
        return selectors.list_orders(
            {
                # Round 27: a signed-in CUSTOMER only ever sees their own orders.
                # Before this, the endpoint was unscoped, so any caller (even
                # one with no token at all) could list every customer's orders.
                # Admins keep the full list; the guest lookup path has its own
                # dedicated endpoint and is untouched.
                "customer": self._scoped_customer() or params.get("customer"),
                "status": params.get("status"),
                "payment_status": params.get("payment_status"),
                "payment_method": params.get("payment_method"),
                "order_number": params.get("order_number"),
                "date_from": params.get("date_from"),
                "date_to": params.get("date_to"),
                "city": params.get("city"),
                "pincode": params.get("pincode"),
                "search": params.get("search"),
            }
        )

    def _scoped_customer(self):
        """The caller's own customer id when a customer account is signed in."""
        user = getattr(self.request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return None
        if getattr(user, "role", None) != "CUSTOMER":
            return None
        link = getattr(user, "customer_profile", None)
        return getattr(link, "customer_id", None)

    def get_serializer_class(self):
        if self.action == "list":
            return OrderListSerializer
        if self.action == "set_status":
            return OrderStatusUpdateSerializer
        if self.action == "cancel":
            return OrderCancelSerializer
        return OrderDetailSerializer

    def get_object(self):
        order = services.get_order_or_404(self.kwargs["pk"])
        self.check_object_permissions(self.request, order)
        return order

    def create(self, request, *args, **kwargs):
        return Response(
            {
                "error": {
                    "code": "method_not_allowed",
                    "message": (
                        "Orders are created through POST /orders/checkout/ using the "
                        "customer's cart."
                    ),
                    "status": 405,
                }
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def update(self, request, *args, **kwargs):
        order = self.get_object()
        serializer = OrderNotesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = services.update_internal_notes(
            order, serializer.validated_data["internal_notes"]
        )
        return Response(OrderDetailSerializer(updated, context={"request": request}).data)

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        return Response(
            {
                "error": {
                    "code": "method_not_allowed",
                    "message": (
                        "Orders cannot be deleted. Cancel the order instead to "
                        "preserve the financial audit trail."
                    ),
                    "status": 405,
                }
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @extend_schema(
        request=OrderStatusUpdateSerializer,
        responses={200: OrderDetailSerializer},
        description="Move the order to its next status, validating the transition.",
    )
    @action(detail=True, methods=["post"], url_path="status")
    def set_status(self, request, pk=None):
        order = self.get_object()
        serializer = OrderStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        updated = services.update_order_status(
            order,
            data["status"],
            note=data.get("note", ""),
            changed_by=data.get("changed_by", "admin"),
        )
        return Response(OrderDetailSerializer(updated, context={"request": request}).data)

    @extend_schema(
        request=OrderCancelSerializer,
        responses={200: OrderDetailSerializer},
        description="Cancel an order, restoring inventory and releasing the coupon.",
    )
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        order = self.get_object()
        serializer = OrderCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        updated = services.cancel_order(
            order,
            reason=data["reason"],
            note=data.get("note", ""),
            changed_by=data.get("changed_by", "customer"),
        )
        return Response(OrderDetailSerializer(updated, context={"request": request}).data)

    @extend_schema(
        request=None, responses={200: OrderDetailSerializer},
        description="Confirm a pending order (admin action).",
    )
    @action(detail=True, methods=["post"], url_path="confirm")
    def confirm(self, request, pk=None):
        order = services.confirm_order(self.get_object(), changed_by="admin")
        return Response(OrderDetailSerializer(order, context={"request": request}).data)

    @extend_schema(
        request=None, responses={200: OrderDetailSerializer},
        description="Mark an out-for-delivery order as delivered.",
    )
    @action(detail=True, methods=["post"], url_path="mark-delivered")
    def mark_delivered(self, request, pk=None):
        order = services.mark_delivered(self.get_object(), changed_by="admin")
        return Response(OrderDetailSerializer(order, context={"request": request}).data)

    @extend_schema(
        responses={200: OrderDetailSerializer(many=True)},
        description="Status transition history for an order.",
    )
    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request, pk=None):
        from apps.orders.serializers import OrderStatusHistorySerializer

        order = self.get_object()
        return Response(
            OrderStatusHistorySerializer(
                selectors.get_status_history(order), many=True
            ).data
        )

    @extend_schema(
        request=None,
        responses={200: ReorderResultSerializer},
        description="Add every available item of this order back to the cart.",
    )
    @action(detail=True, methods=["post"], url_path="reorder")
    def reorder(self, request, pk=None):
        order = self.get_object()
        customer = resolve_customer(request)
        result = services.reorder(customer, order)
        return Response(ReorderResultSerializer(result).data)

    @extend_schema(responses={200: OrderStatsSerializer})
    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        params = request.query_params
        return Response(
            OrderStatsSerializer(
                selectors.order_stats(
                    {"date_from": params.get("date_from"), "date_to": params.get("date_to")}
                )
            ).data
        )

    @extend_schema(
        responses={200: OrderListSerializer(many=True)},
        description="Orders that still have work left (pending → out for delivery).",
    )
    @action(detail=False, methods=["get"], url_path="active")
    def active(self, request):
        from apps.orders.models import ACTIVE_ORDER_STATUSES

        queryset = selectors.list_orders(
            {"status": ",".join(ACTIVE_ORDER_STATUSES)}
        )
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(
                OrderListSerializer(page, many=True, context={"request": request}).data
            )
        return Response(
            OrderListSerializer(queryset, many=True, context={"request": request}).data
        )
