"""URL routes for the promotions app."""

from rest_framework.routers import SimpleRouter

from apps.promotions.views import (
    CouponRedemptionViewSet,
    CouponViewSet,
    PromotionViewSet,
)

app_name = "promotions"

router = SimpleRouter(trailing_slash=True)
router.register("", PromotionViewSet, basename="promotion")
router.register("coupons", CouponViewSet, basename="coupon")
router.register("redemptions", CouponRedemptionViewSet, basename="redemption")

urlpatterns = router.urls
