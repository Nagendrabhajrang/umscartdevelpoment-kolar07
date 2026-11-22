"""Banner API views.

SECURITY NOTE: authentication is not implemented in this phase. These
endpoints are unrestricted and must NOT be exposed publicly until the
authentication layer ships.
"""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.banners import selectors, services
from apps.banners.filters import BannerFilter
from apps.banners.serializers import (
    BannerSerializer,
    BannerToggleSerializer,
    BannerWriteSerializer,
)
from common.views import BaseModelViewSet


class BannerViewSet(BaseModelViewSet):
    """CRUD API for homepage and promotional banners."""

    filterset_class = BannerFilter
    search_fields = ("title", "subtitle", "alt_text")
    ordering_fields = ("display_order", "created_at", "start_date")
    ordering = ("display_order", "-created_at")
    lookup_value_regex = r"[0-9a-fA-F-]{1,36}|[0-9]+"

    def get_queryset(self):
        params = self.request.query_params
        return selectors.list_banners(
            {
                "placement": params.get("placement"),
                "is_active": _to_bool(params.get("is_active")),
                "live_only": _to_bool(params.get("live_only")),
                "search": params.get("search"),
            }
        )

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return BannerWriteSerializer
        return BannerSerializer

    def get_object(self):
        banner = services.get_banner_or_404(self.kwargs["pk"])
        self.check_object_permissions(self.request, banner)
        return banner

    def create(self, request, *args, **kwargs):
        serializer = BannerWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        banner = services.create_banner(**serializer.validated_data)
        return Response(
            BannerSerializer(banner, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        return self._update(request, partial=False)

    def partial_update(self, request, *args, **kwargs):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        banner = self.get_object()
        serializer = BannerWriteSerializer(banner, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        updated = services.update_banner(banner, **serializer.validated_data)
        return Response(BannerSerializer(updated, context={"request": request}).data)

    def destroy(self, request, *args, **kwargs):
        services.delete_banner(self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=BannerToggleSerializer, responses={200: BannerSerializer})
    @action(detail=True, methods=["post"], url_path="toggle")
    def toggle(self, request, pk=None):
        banner = self.get_object()
        serializer = BannerToggleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = services.toggle_banner(banner, serializer.validated_data["is_active"])
        return Response(BannerSerializer(updated, context={"request": request}).data)

    @extend_schema(
        parameters=[
            OpenApiParameter("placement", str, required=False),
        ],
        responses={200: BannerSerializer(many=True)},
        description="Banners currently live for a given placement.",
    )
    @action(detail=False, methods=["get"], url_path="live")
    def live(self, request):
        placement = request.query_params.get("placement")
        queryset = selectors.get_live_banners(placement=placement)
        banners = list(queryset)
        return Response(
            BannerSerializer(banners, many=True, context={"request": request}).data
        )

    @extend_schema(
        request=None,
        responses={200: BannerSerializer},
        description="Record a banner click and return the destination URL.",
    )
    @action(detail=True, methods=["post"], url_path="click")
    def click(self, request, pk=None):
        banner = self.get_object()
        link = services.record_click(banner)
        banner.refresh_from_db(fields=["click_count"])
        payload = BannerSerializer(banner, context={"request": request}).data
        payload["redirect_to"] = link
        return Response(payload)


def _to_bool(value):
    if value is None:
        return None
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}
